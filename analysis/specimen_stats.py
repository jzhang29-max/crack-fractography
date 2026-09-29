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

AND ONE MAGNIFICATION PER DETERMINATION. E562 fixes the magnification before the fields
are counted: the estimate is of the features that magnification RESOLVES, so fields taken
at different nm/px estimate different populations and their mean is not a measurement of
either. This repo already states the same rule in its own words -- docs/
PRACTICE_AND_PRIOR_ART.md: "this corpus spans a 249x magnification range, so pooling frames
of unequal physical area is the error the standards exist to prevent" -- and the interval
was the one place that broke it.

Eight specimen-arms did: MAR_AmbB_AS, MAR_AmbB_HIP, MAR_H_AS and MAR_H_HIP, identically in
sem/gated and sem/machine. Each holds nine fields at 51.883 nm/px plus ONE overview at
337.2396 -- a 6.5x coarser pixel, so a 6.5x coarser minimum resolvable width and a speck
cutoff of 2.84 um2 against 0.067. It is also 3072x2048 against 6144x4096, so its field of
view is 10.6x the area of a fine field while taking 1/10 of the weight in a mean over ten
fields; E562's fields are equal-area by construction, and that objection stands even if
the detection limits had matched.

So the interval is computed over the MODAL magnification group only -- the scale the most
fields were taken at -- and refuses when no group reaches three fields. What it moves:

    MAR_AmbB_AS    53.0% -> 62.0%    overview area fraction 0.03235, 1.5x the fine mean
    MAR_AmbB_HIP  117.9% -> 84.2%                           0.06513, 10.8x
    MAR_H_AS       42.4% -> 49.1%                           0.03576, 1.2x
    MAR_H_HIP      81.7% -> 93.0%                           0.03525, 1.0x

Three of the four get WORSE, which is why this is not a cleanup. On AmbB_HIP the overview
is a 10.8x outlier and was inflating the interval; on the other three it sits near the fine
mean and was diluting it. Both directions are the same error, and 117.9% was substantially
that one frame. It was NOT the app's worst SEM number -- MAR_Amb_AS reports 138.0% gated
and 125.8% machine, has no recoverable nm/px at all, and is untouched by any of this. None
of the four meets E562's +/-10% either way; nothing in either SEM arm does.

Removing the overview also un-clamps MAR_AmbB_HIP: its lower bound was reaching below zero
only because that one frame was widening the interval faster than it moved the mean.

The dropped fields are not hidden: magnification_groups is on every record, including the
single-magnification ones, because "all ten fields at one scale" is part of what the
interval asserts and should be checkable rather than assumed. The stage gradient is
computed over the same determination, for the same reason plus a second one -- the
overview's field of view spans much of the raster, so it has no position comparable to a
fine field's. It gets STRONGER without it: rho +0.648..+0.830 over ten fields against
+0.750..+0.867 over nine.

AND THE DETECTOR IS NOT A NUISANCE HERE. On the 56 fields imaged both ways, CBS reports 2.29x
the crack area of ETD (median; CBS higher in 50 of 56; paired Wilcoxon p = 8e-9). Detector is
also confounded with specimen -- four specimens are CBS-only, seven are CBS+ETD mixes -- so a
difference in area fraction between two specimens is partly a difference in detector. The
composition is reported on every specimen for that reason, and the within-specimen CBS/ETD
ratio is reported wherever both exist, as a sensitivity number rather than a footnote.
"""
import re

import numpy as np

#: Where an uploaded image goes when nothing better is known about it. Frames under this
#: name are unrelated to each other, so no between-field statistic over them is valid.
PSEUDO_SPECIMEN = "uploaded"

#: Detector token in a frame stem. The same physical field appears once per detector.
DETECTOR = re.compile(r"_(CBS|ETD|BSE|SE|TLD)(?=_|$)", re.I)

#: Two fields belong to the same E562 determination when their nm/px agree within this
#: FACTOR. Not tuned: the only specimens that split are 6.5x apart with zero spread inside
#: each group (exactly 51.883 and exactly 337.2396), so every factor from 1.0 to 6.5 gives
#: the identical partition and this constant is not doing hidden work. It is set at 1.2 so
#: that a nominally-equal scale recorded slightly differently -- the corpus holds both
#: 51.883 and 52.0 -- is one determination, while a deliberate magnification change is not.
SAME_MAGNIFICATION = 1.2


def detector_of(stem):
    m = DETECTOR.search(stem)
    return m.group(1).upper() if m else None


def field_key(stem):
    """The physical field a frame images -- its stem with the detector token removed."""
    return DETECTOR.sub("", stem)


def magnification_of(frame):
    """The nm/px a frame was acquired at, or None when the scale was never recovered.

    None is a real answer, not a missing one: every 316 frame has it, and those specimens
    form a single group so nothing below changes for them.
    """
    v = frame.get("nm_per_px")
    return float(v) if v else None


def _partition_by_magnification(frames):
    """[(nm_per_px, [frames]), ...] -- the E562 determination first.

    The determination is the scale the most FIELDS were taken at, ties going to the finer
    scale because it resolves more. Assignment is greedy against each bucket's first
    member, which is exact for well-separated scales and is all this corpus has; a corpus
    with a continuum of magnifications would need a real clustering and should not be
    getting one pooled interval anyway.
    """
    scales, buckets = [], []
    for f in sorted(frames, key=lambda x: x.get("frame", "")):
        m = magnification_of(f)
        for i, s in enumerate(scales):
            if s is None and m is None:
                buckets[i].append(f)
                break
            if s is not None and m is not None and max(s / m, m / s) <= SAME_MAGNIFICATION:
                buckets[i].append(f)
                break
        else:
            scales.append(m)
            buckets.append([f])
    out = list(zip(scales, buckets))
    out.sort(key=lambda sb: (-len({field_key(f["frame"]) for f in sb[1]}),
                             float("inf") if sb[0] is None else sb[0]))
    return out


def magnification_span(frames):
    """Every scale this specimen's fields were acquired at, determination first.

    Reported on single-magnification specimens too. "All ten fields at one scale" is part
    of what the interval asserts, and an assertion that is only recorded when it fails is
    not checkable -- the reader cannot tell a clean specimen from an unexamined one.
    """
    out = []
    for i, (s, g) in enumerate(_partition_by_magnification(frames)):
        vals = collapse_to_fields(g, "area_fraction")
        out.append({
            "nm_per_px": (round(s, 4) if s is not None else None),
            "n_fields": len({field_key(f["frame"]) for f in g}),
            "area_fraction_mean": (round(float(np.mean(vals)), 6) if vals else None),
            # The detection limit is what actually differs, so it is spelled out rather
            # than left for the reader to divide: a crack narrower than one pixel is
            # unresolved, not absent, and that threshold moves with the scale.
            "min_resolvable_width_um": (round(s / 1000.0, 4) if s is not None else None),
            "in_determination": i == 0,
        })
    return out


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
    # A normal-theory interval on a small, skewed, non-negative quantity can reach below
    # zero. Clamping it to 0.0 and printing "0.00%" states a measured lower bound of exactly
    # zero, which is a claim the data does not make -- it is the method running out of
    # validity, not a finding. One of nine gated specimen-arms hits this (MAR_Amb_AS); it
    # was two until the interval stopped pooling magnifications. Clamped, because an
    # area fraction cannot be negative, but FLAGGED so the UI can say which it is.
    raw_lo = mean - half
    return {
        "mean": round(mean, 6),
        "sd_between_fields": round(s, 6),
        "n_fields": n,
        "ci95_halfwidth": round(float(half), 6),
        "ci95_lo": round(max(0.0, raw_lo), 6),
        "ci95_lo_clamped": bool(raw_lo < 0),
        "ci95_lo_note": ("the normal-theory interval extends below zero, which an area "
                         "fraction cannot; the lower bound is not established"
                         if raw_lo < 0 else None),
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


def collapse_to_fields(frames, key, get=None):
    """One value per physical field, averaging detector replicates of the same field.

    `get` reaches values that do not sit at the top level -- the P10 pair live under
    frame["probe"]. Without it those two were the only physical quantities that could not
    be field-collapsed, which is how they stayed frame-medians while everything around
    them was corrected.
    """
    getter = get or (lambda f: f.get(key))
    groups = {}
    for f in frames:
        groups.setdefault(field_key(f["frame"]), []).append(f)
    out = []
    for _, fs in sorted(groups.items()):
        vals = [getter(f) for f in fs if getter(f) is not None]
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


def _one_frame_per_field(frames):
    """One representative frame per physical field, for statistics over stage position.

    Position is a property of the field, not of the frame: two detectors imaging the same
    place report the same coordinates, so passing raw frames doubles every point.
    """
    seen, out = set(), []
    for f in sorted(frames, key=lambda x: x.get("frame", "")):
        k = field_key(f.get("frame", ""))
        if k in seen:
            continue
        seen.add(k)
        out.append(f)
    return out


def _gradient(frames):
    try:
        import stage
        return stage.gradient(frames)
    except Exception:
        return None


def _n_patches(frames):
    # Same local-import guard as _gradient: without the SEM repo's metadata there are no
    # coordinates. Falling to None is the safe direction -- None leaves the ranking
    # refusal switched ON, so a missing stage table cannot silently license a comparison.
    try:
        import stage
        return stage.n_patches(frames)
    except Exception:
        return None


def _ci_over_determination(af_fields, groups):
    """The E562 interval, stamped with the scale it was measured at and what it left out."""
    ci = _ci(af_fields)
    if ci is None:
        return None
    s = groups[0][0] if groups else None
    ci["nm_per_px"] = round(s, 4) if s is not None else None
    ci["n_fields_off_determination"] = sum(
        len({field_key(f["frame"]) for f in g}) for _, g in groups[1:])
    if ci["n_fields_off_determination"]:
        others = ", ".join(str(round(o, 4)) for o, _ in groups[1:] if o is not None)
        ci["magnification_note"] = (
            f"over the {ci['n_fields']} fields at {ci['nm_per_px']} nm/px only; "
            f"{ci['n_fields_off_determination']} field(s) at {others} nm/px are a "
            f"different detection limit and are not averaged in")
        ci["method"] += "; one magnification per determination"
    return ci


def _no_ci_reason(specimen, af_fields, groups):
    """Why there is no interval -- and the three reasons are not interchangeable."""
    if specimen == PSEUDO_SPECIMEN:
        return ("these are unrelated uploaded images, not fields of one specimen, so a "
                "between-field interval over them would not mean anything")
    if len(af_fields) >= 3:
        return None
    if len(groups) > 1:
        # "Only 2 fields" would be a lie on a specimen holding five images: the fields
        # exist, they are just split across magnifications that cannot be pooled.
        n = sum(len({field_key(f["frame"]) for f in g}) for _, g in groups)
        scales = ", ".join(str(round(s, 4)) if s is not None else "unknown"
                           for s, _ in groups)
        return (f"this specimen's {n} fields are split across magnifications ({scales} "
                f"nm/px) and no single magnification has the three fields E562 needs; "
                f"pooling them would average different detection limits")
    return None


def summarise(arm, specimen, frames):
    """One specimen-arm record."""
    # THE DETERMINATION: the fields acquired at the modal magnification. EVERY physical
    # aggregate in this record is computed over these -- averages, medians and totals
    # alike -- because a field at a 6.5x coarser pixel is measuring a different population
    # (see the module docstring).
    #
    # This comment used to exempt the additive quantities, on the grounds that a coarse
    # field really did cover that material so summing it "double-counts nothing". Two
    # reasons that is wrong, and they are not equally well founded:
    #
    #   Stands on its own: a total over fields of unequal DETECTION LIMIT is not a total
    #   of anything. The overview resolves a 6.5x wider minimum crack, so the area it
    #   contributes and the area the fine nine contribute are not the same quantity.
    #
    #   Carries a premise: the overview's field of view is 10.6x a fine field's and,
    #   read against the stage coordinates, covers about 45% and 50% of the fine nine on
    #   the AmbB pair -- so summing really does double-count. A second session recomputed
    #   the same geometry independently (4.07/9 and 4.52/9). But it requires reading the
    #   FEI stage coordinates as METRES, which stage.py deliberately declines to assert,
    #   so it corroborates the decision rather than carrying it.
    #
    # Area-weighting instead of excluding is worse either way: it weights UP the field
    # whose contribution is least comparable. The excluded material is reported under
    # area_off_determination_mm2 and tcl_um_off_determination.
    groups = _partition_by_magnification(frames)
    determination = groups[0][1] if groups else []
    off_mag_fields = (len({field_key(f["frame"]) for f in frames})
                      - len({field_key(f["frame"]) for f in determination}))

    af_fields = collapse_to_fields(determination, "area_fraction")
    scaled = [f for f in frames if f.get("scale_known")]
    # The determination's own scaled frames, and everything scaled that is NOT in it. Every
    # physical aggregate below is over the first; the second is reported separately so the
    # excluded material is stated rather than silently dropped.
    det_scaled = [f for f in determination if f.get("scale_known")]
    _det_ids = {id(f) for f in determination}
    off_scaled = [f for f in scaled if id(f) not in _det_ids]

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

        # The E562 interval, over fields -- BUT NOT FOR UPLOADS.
        #
        # Every uploaded frame is filed under the pseudo-specimen "uploaded", so a user who
        # drops four unrelated images on the app got a 95% CI over them with a method
        # string citing "between-FIELD variance". They are not fields of a specimen; they
        # are four different pieces of metal. The shipped value was +/-156% over a 316
        # steel frame, two demos and a test image, and this is the only path a user who is
        # not the author ever takes -- so the app's loudest statistic was fabricated for
        # everyone but its author, while the README leads with never pooling.
        #
        # Gated on the PSEUDO-SPECIMEN, not on the arm and not on the field count. The
        # count guard cannot tell four fields of one specimen from four unrelated images,
        # and the arm guard was too blunt in the other direction: a mask marked up from a
        # real specimen is filed in the uploads arm but IS a field of that specimen, and
        # suppressing its interval threw away a number that does mean something.
        #
        # AND NOT ACROSS MAGNIFICATIONS. Computed over the determination only; a specimen
        # whose modal group is under three fields gets None with a reason that names the
        # split, so "no interval" is never confused with "too few images".
        "area_fraction_ci": (None if specimen == PSEUDO_SPECIMEN
                             else _ci_over_determination(af_fields, groups)),
        "no_ci_reason": _no_ci_reason(specimen, af_fields, groups),

        # Every acquisition scale in this specimen, determination first. Present even when
        # there is only one, so the card can state the span rather than stay silent.
        "magnification_groups": magnification_span(frames),
        "n_fields_off_determination": off_mag_fields,

        # Physical quantities, over the DETERMINATION's scaled FIELDS. Both halves of that
        # were wrong and they compound. These six were medians over FRAMES, so a field
        # imaged through two detectors voted twice -- and CBS reads 2.29x ETD, so the vote
        # is not a tie. And they pooled every magnification, so the 337.2396 nm/px overview
        # sat in the same median as the nine fine fields at 51.883, at a 6.5x coarser
        # detection limit and 10.6x the field of view. On MAR_AmbB_HIP that put P20 at
        # 2627.6 /mm2 against 1815.7 corrected (1.45x), P10 min at 3.57 against 2.77, and
        # MCL at 15.2 um against 26.5 -- while the card printed them directly under an
        # interval correctly computed over nine fields at one scale. The file's own
        # docstring opens with "A FRAME IS NOT A FIELD" and "ONE MAGNIFICATION PER
        # DETERMINATION"; this block was the third place that rule had been missed.
        "p10_min_per_mm": _median(collapse_to_fields(
            det_scaled, "", get=lambda f: (f.get("probe") or {}).get("p10_min_per_mm"))),
        "p10_mean_per_mm": _median(collapse_to_fields(
            det_scaled, "", get=lambda f: (f.get("probe") or {}).get("p10_mean_per_mm"))),
        "p21_skeleton_mm_per_mm2": _median(collapse_to_fields(
            det_scaled, "p21_skeleton_mm_per_mm2")),
        "p21_buffon_mm_per_mm2": _median(collapse_to_fields(
            det_scaled, "", get=lambda f: (f.get("probe") or {}).get("p21_buffon_mm_per_mm2"))),
        "p20_per_mm2": _median(collapse_to_fields(det_scaled, "p20_per_mm2")),
        # The longest single crack, tip to tip on one region's skeleton -- NOT
        # max(SkeletonLength_px), which is the whole network's centreline and was what this
        # field held while being labelled "the longest crack". The network quantity is kept
        # beside it under its own name. Measured over the 143 scaled frames, the network
        # figure is 3.70x the MCL at the median, and the old value exceeded the short side
        # of its own field on 89 of them against 48 now.
        "mcl_um": _median(collapse_to_fields(det_scaled, "mcl_um")),
        "largest_network_centreline_um": _median(collapse_to_fields(
            det_scaled, "largest_network_centreline_um")),
        # ADDITIVE quantities are summed over FIELDS, not over frames. Summing over frames
        # double-counts every field that was imaged through two detectors: it reported
        # 2.650 mm2 analysed for a specimen holding 10 fields of ~0.13 mm2, and a total
        # crack length of 67 mm for 33 mm of crack. Collapsing the mean handled this and
        # the totals did not, which is the same error one line lower down.
        # ...AND OVER THE DETERMINATION TOO, which was the half of the magnification rule
        # that never landed. The card printed "1.325218 mm2 over 10 fields" two rows under
        # "95% CI ..., 9 fields at 51.883 nm/px", because these three still summed every
        # scale. The defence written for it -- that a coarse field really did cover that
        # material, so summing double-counts nothing -- is false, and the reason that
        # needs no premise is that a total over fields whose detection limits differ 6.5x
        # is not a total of anything. (It is also a double-count: the overview's field of
        # view is 10.6x a fine field's and covers roughly 45% and 50% of the fine nine on
        # the AmbB pair -- but that reads the stage coordinates as metres, which stage.py
        # declines to assert, so it corroborates rather than carries.) Area-weighting is
        # worse than excluding either way: it weights UP the least comparable field. The
        # excluded material is reported under its own name and shown on the card.
        "tcl_um_total": (round(float(sum(collapse_to_fields(det_scaled, "tcl_um"))), 1)
                         if det_scaled else None),
        "area_analysed_mm2": (round(float(sum(collapse_to_fields(
            det_scaled, "area_analysed_mm2"))), 6) if det_scaled else None),
        "n_fields_scaled": len({field_key(f["frame"]) for f in det_scaled}),
        # NOT RENDERED. It needs the stage coordinates to say whether it overlaps what is
        # already counted, and stage.py will not assert the unit those are in.
        "area_off_determination_mm2": (round(float(sum(collapse_to_fields(
            off_scaled, "area_analysed_mm2"))), 6) if off_scaled else None),
        "tcl_um_off_determination": (round(float(sum(collapse_to_fields(
            off_scaled, "tcl_um"))), 1) if off_scaled else None),

        # Are these fields a sample of a surface, or a raster across one patch? E562
        # presumes the former and the 2026-09-15 batch is the latter.
        # COLLAPSED TO FIELDS FIRST, like every other aggregate in this function. It was
        # the one that skipped it: CBS and ETD sit at byte-identical stage coordinates, so
        # all eight shipped records read n=20 for 10 physical fields and every p-value was
        # computed on doubled data -- up to 27x too small. Corrected, the effect is
        # STRONGER and the significance weaker: rho +0.648..+0.830 at p 0.0029..0.0425,
        # against the shipped +0.537..+0.782 at p 0.00005..0.0145. (Those corrected
        # figures are the ten-field ones, which is what the next paragraph then narrows;
        # this line used to quote a third pair that matched neither and no output file.)
        # AND OVER THE DETERMINATION, for the same reason as the interval plus a second
        # one: the 337 nm/px overview's field of view is 10.6x a fine field's and spans
        # much of the raster, so it has no stage position comparable to theirs. Dropping
        # it STRENGTHENS every gradient (rho +0.648..+0.830 -> +0.750..+0.867), so this is
        # not a finding manufactured by removing an inconvenient point.
        "stage_gradient": _gradient(_one_frame_per_field(determination)),

        # HOW MANY SEPARATED SITES, which is the question the gradient above cannot ask.
        # One site per specimen makes the site and the specimen the same variance
        # component, so no ordering of specimens is estimable; this is the field the
        # ranking refusal reads. 1 everywhere it is answerable today, None elsewhere --
        # and None does not switch the refusal off. Over ALL fields, not the
        # determination: a coarse overview still tells you where the microscope was.
        "n_patches": _n_patches(_one_frame_per_field(frames)),

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
