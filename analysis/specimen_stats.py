#!/usr/bin/env python3
"""Per-specimen aggregation with an ASTM E562 confidence interval.

ASTM E562-19e1 computes the 95% CI of a volume/area fraction from the FIELD-TO-FIELD
variance -- s over the fields measured, times Student's t, over sqrt(n). The interval is the
product; a fraction quoted to six decimals with no uncertainty is not a measurement. E562 is
written for manual point counting on a grid, and applying it to area fraction from image
analysis is the analogy the coatings literature makes routinely, so the construct is stated
on the output rather than implied.

TWO THINGS ABOUT n THAT ARE EASY TO GET WRONG HERE, and both inflate confidence:

  A FRAME IS NOT A FIELD. 142 SEM frames in the gated arm are 86 distinct fields: 56 of them
  were imaged twice, once through CBS and once through ETD. Counting frames would put up to
  sqrt(2) of spurious precision into every interval. So detector replicates are averaged
  into one value per field FIRST, and n is the number of fields.

  FRAMES WITHIN A SPECIMEN ARE NOT INDEPENDENT ANYWAY. Nine fields per cell tile ~1.2 x 1.1
  mm of one specimen. The interval below describes the spread of fields WITHIN a specimen --
  it is a sampling interval for that specimen's surface, not a confidence interval for the
  material. Comparing two specimens needs the specimen to be the unit, not these intervals.

AND THE DETECTOR IS NOT A NUISANCE HERE. On the 56 fields imaged both ways, CBS reports 2.29x
the crack area of ETD (median; CBS higher in 50 of 56; paired Wilcoxon p = 8e-9). Detector is
also confounded with specimen -- four specimens are CBS-only, seven are CBS+ETD mixes -- so a
difference in area fraction between two specimens is partly a difference in detector. The
composition is reported on every specimen for that reason, and the within-specimen CBS/ETD
ratio is reported wherever both exist, as a sensitivity number rather than a footnote.
"""
import re

import numpy as np

#: Detector token in a frame stem. The same physical field appears once per detector.
DETECTOR = re.compile(r"_(CBS|ETD|BSE|SE|TLD)(?=_|$)", re.I)


def detector_of(stem):
    m = DETECTOR.search(stem)
    return m.group(1).upper() if m else None


def field_key(stem):
    """The physical field a frame images -- its stem with the detector token removed."""
    return DETECTOR.sub("", stem)


def _t95(n):
    """Two-sided 95% Student's t. Not 1.96: n here is typically 3 to 20, where the normal
    approximation understates the interval by 30% at n=3."""
    from scipy import stats
    return float(stats.t.ppf(0.975, n - 1))


def _ci(values):
    """ASTM E562 95% CI of a mean from between-field variance, plus its % relative accuracy.

    Returns None below 3 fields. E562 asks for enough fields to make s meaningful; two give
    an interval so wide and so unstable that quoting it implies a precision the data cannot
    support, and the app already gates dispersion at 3 elsewhere.
    """
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    n = v.size
    if n < 3:
        return None
    mean = float(v.mean())
    s = float(v.std(ddof=1))
    half = _t95(n) * s / np.sqrt(n)
    return {
        "mean": round(mean, 6),
        "sd_between_fields": round(s, 6),
        "n_fields": n,
        "ci95_halfwidth": round(float(half), 6),
        "ci95_lo": round(max(0.0, mean - half), 6),
        "ci95_hi": round(float(mean + half), 6),
        # E562's own headline: the interval as a percentage of the mean. Under 10% is the
        # usual target; above it the answer is "measure more fields", not "round harder".
        "pct_relative_accuracy": round(100.0 * half / mean, 1) if mean > 0 else None,
        "t95": round(_t95(n), 3),
        "method": "ASTM E562-19e1 between-field variance, t(0.975, n-1)*s/sqrt(n); "
                  "n = FIELDS, detector replicates averaged within a field",
    }


def _median(vals):
    v = [x for x in vals if x is not None and np.isfinite(x)]
    return round(float(np.median(v)), 4) if v else None


def collapse_to_fields(frames, key):
    """One value per physical field, averaging detector replicates of the same field."""
    groups = {}
    for f in frames:
        groups.setdefault(field_key(f["frame"]), []).append(f)
    out = []
    for _, fs in sorted(groups.items()):
        vals = [f.get(key) for f in fs if f.get(key) is not None]
        if vals:
            out.append(float(np.mean(vals)))
    return out


def detector_sensitivity(frames):
    """Within this specimen, how much does the detector move the answer?

    Only from fields imaged BOTH ways -- a ratio of two specimen means over different fields
    would confound the detector with which fields each detector happened to cover.
    """
    byfield = {}
    for f in frames:
        d = detector_of(f["frame"])
        if d:
            byfield.setdefault(field_key(f["frame"]), {})[d] = f
    pairs = [(v["CBS"]["area_fraction"], v["ETD"]["area_fraction"])
             for v in byfield.values() if {"CBS", "ETD"} <= set(v)]
    if not pairs:
        return None
    c = np.array([p[0] for p in pairs], float)
    e = np.array([p[1] for p in pairs], float)
    ok = e > 0
    if not ok.any():
        return None
    return {"n_fields_both_detectors": int(ok.sum()),
            "cbs_over_etd_median": round(float(np.median(c[ok] / e[ok])), 3),
            "note": "same physical field, two detectors; a ratio away from 1 is instrument, "
                    "not material"}


def summarise(arm, specimen, frames):
    """One specimen-arm record."""
    af_fields = collapse_to_fields(frames, "area_fraction")
    scaled = [f for f in frames if f.get("scale_known")]

    rec = {
        "arm": arm,
        "specimen": specimen,
        "n_frames": len(frames),
        "n_fields": len({field_key(f["frame"]) for f in frames}),
        "n_cracks_total": int(sum(f["n_cracks_measured"] for f in frames)),
        "scale_known_frames": len(scaled),

        # Kept: the existing UI reads these.
        "area_fraction_median": _median([f["area_fraction"] for f in frames]),
        "area_fraction_min": round(min(f["area_fraction"] for f in frames), 6),
        "area_fraction_max": round(max(f["area_fraction"] for f in frames), 6),
        "density_median": _median([f["crack_density_px_per_Mpx"] for f in frames]),
        "estimable_dispersion": len(af_fields) >= 3,

        # The E562 interval, over fields.
        "area_fraction_ci": _ci(af_fields),

        # Physical quantities, over SCALED fields only, and null when none are scaled.
        "p10_min_per_mm": _median([(f.get("probe") or {}).get("p10_min_per_mm")
                                   for f in scaled]),
        "p10_mean_per_mm": _median([(f.get("probe") or {}).get("p10_mean_per_mm")
                                    for f in scaled]),
        "p21_skeleton_mm_per_mm2": _median([f.get("p21_skeleton_mm_per_mm2")
                                            for f in scaled]),
        "p21_buffon_mm_per_mm2": _median([(f.get("probe") or {}).get("p21_buffon_mm_per_mm2")
                                          for f in scaled]),
        "p20_per_mm2": _median([f.get("p20_per_mm2") for f in scaled]),
        "mcl_um": _median([f.get("mcl_um") for f in scaled]),
        # ADDITIVE quantities are summed over FIELDS, not over frames. Summing over frames
        # double-counts every field that was imaged through two detectors: it reported
        # 2.650 mm2 analysed for a specimen holding 10 fields of ~0.13 mm2, and a total
        # crack length of 67 mm for 33 mm of crack. Collapsing the mean handled this and
        # the totals did not, which is the same error one line lower down.
        "tcl_um_total": (round(float(sum(collapse_to_fields(scaled, "tcl_um"))), 1)
                         if scaled else None),
        "area_analysed_mm2": (round(float(sum(collapse_to_fields(scaled,
                                                                 "area_analysed_mm2"))), 6)
                              if scaled else None),
        "n_fields_scaled": len({field_key(f["frame"]) for f in scaled}),

        # The detector, because it is confounded with the specimen and moves the answer.
        "detectors": {},
        "detector_sensitivity": detector_sensitivity(frames),
    }
    for f in frames:
        d = detector_of(f["frame"]) or "unlabelled"
        rec["detectors"][d] = rec["detectors"].get(d, 0) + 1
    return rec


def paired_arm_ratio(frames_by_arm, specimen, a="sem/gated", b="sem/machine"):
    """Segmentation sensitivity: the two SEM arms on the SAME frames.

    Paired on the frame stem rather than compared as specimen means, so the number is not
    contaminated by the two arms covering different frames.
    """
    fa = {f["frame"]: f for f in frames_by_arm.get(a, []) if f["specimen"] == specimen}
    fb = {f["frame"]: f for f in frames_by_arm.get(b, []) if f["specimen"] == specimen}
    both = sorted(set(fa) & set(fb))
    r = [fa[k]["area_fraction"] / fb[k]["area_fraction"]
         for k in both if fb[k]["area_fraction"] > 0]
    if not r:
        return None
    # HOW MANY FRAMES THE OPERATOR ACTUALLY TOUCHED, because a median of 1.000 has two
    # completely different meanings and the card was showing the wrong one. Only 44 of 142
    # frames carry any correction; five specimens carry none. Without this count, "x1 on 20
    # identical frames" reads as "the corrections made no difference" when the truth is
    # that there are no corrections on those frames at all.
    corrected = [k for k in both if fa[k]["area_fraction"] != fb[k]["area_fraction"]]
    rc = [fa[k]["area_fraction"] / fb[k]["area_fraction"]
          for k in corrected if fb[k]["area_fraction"] > 0]
    return {"n_paired_frames": len(r),
            "n_frames_corrected": len(corrected),
            "gated_over_machine_median": round(float(np.median(r)), 3),
            "gated_over_machine_where_corrected": (round(float(np.median(rc)), 3)
                                                   if rc else None),
            "note": "same frames; the operator's strokes against the detector alone"}
