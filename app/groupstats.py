"""Aggregate crack statistics over a chosen set of frames, and compare two such sets.

WHY THIS IS NOT A FEW CALLS TO mean(). Four of the six quantities a user asks for here have
a way of being quietly wrong on this data, and each one has already been wrong somewhere in
this project:

  ANGLE is axial, not directional. A crack at 179 deg and one at 1 deg are two degrees
  apart, not 178. The arithmetic mean of the two is 90 deg -- perpendicular to both. Angles
  are therefore averaged on the DOUBLED angle and halved back, which is the standard axial
  circular mean, and a resultant length R is returned with it: R near 0 means the mean
  direction is meaningless because the cracks point every way, and quoting the angle
  without R invites exactly that mistake.

  LENGTH is censored. A crack running out of the frame is measured only as far as the frame
  goes, so its length is a lower bound. Elsewhere in this project, dropping edge-touching
  cracks cut the mean length by 78%. The mean over everything and the mean over uncensored
  cracks only are therefore BOTH returned, as a bracket, and the censored count comes with
  them.

  AREA is heavily skewed. One network routinely holds 70-97% of a frame's crack area, so a
  mean area is a statement about that one object. The median and the largest-share come
  back beside the mean.

  DENSITY needs an area to divide by, and half this corpus has no recovered pixel size. Per
  megapixel is always available; per square millimetre only where the scale is known, and
  it is reported as null rather than guessed when it is not.

The unit of analysis is the FRAME, and frames are not independent samples: two frames of one
specimen share a specimen, and a CBS/ETD pair is one physical field recorded twice. The
comparison therefore reports a per-frame distribution and names its own n, and refuses to
emit a p-value when either side has fewer than three frames.
"""
import math

#: A crack whose skeleton is shorter than this is a speck, not a crack with a direction.
MIN_SKELETON_PX = 10.0
#: Below this resultant length the mean axis is not a direction, it is noise.
R_MEANINGFUL = 0.15


def _f(v):
    try:
        x = float(v)
        return None if math.isnan(x) or math.isinf(x) else x
    except (TypeError, ValueError):
        return None


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def _mean(xs):
    return (sum(xs) / len(xs)) if xs else None


def axial_mean_deg(angles, weights=None):
    """Mean ORIENTATION of a set of axes, plus how concentrated they are.

    Doubling maps an axis to a direction (0 and 180 become the same point), so the circular
    mean is well defined; halving brings it back. R is the resultant length in [0,1]: 1 is
    every crack parallel, 0 is no preferred direction at all.
    """
    if not angles:
        return {"mean_deg": None, "R": None, "n": 0, "meaningful": False}
    w = weights if weights and len(weights) == len(angles) else [1.0] * len(angles)
    tw = sum(w)
    if tw <= 0:
        return {"mean_deg": None, "R": None, "n": len(angles), "meaningful": False}
    sx = sum(wi * math.cos(2 * math.radians(a)) for a, wi in zip(angles, w)) / tw
    sy = sum(wi * math.sin(2 * math.radians(a)) for a, wi in zip(angles, w)) / tw
    R = math.hypot(sx, sy)
    m = math.degrees(math.atan2(sy, sx)) / 2.0
    if m < 0:
        m += 180.0
    return {"mean_deg": round(m, 2), "R": round(R, 4), "n": len(angles),
            "meaningful": bool(R >= R_MEANINGFUL)}


def frame_stats(frame_rec, cracks):
    """Everything derivable for ONE frame. Returns None for a quantity the data cannot give."""
    nm = _f(frame_rec.get("nm_per_px")) if frame_rec.get("scale_known") else None
    mpx = _f(frame_rec.get("megapixels")) or 0.0
    W, H = _f(frame_rec.get("width_px")) or 0, _f(frame_rec.get("height_px")) or 0
    area_mm2 = (W * H * (nm * 1e-6) ** 2) if nm else None     # nm -> mm

    areas = [a for a in (_f(c.get("Area_px")) for c in cracks) if a]
    lens_all = [l for l in (_f(c.get("SkeletonLength_px")) for c in cracks) if l]
    unc = [c for c in cracks if not c.get("length_is_censored")]
    lens_unc = [l for l in (_f(c.get("SkeletonLength_px")) for c in unc) if l]

    # aspect: the fitted ellipse's major over minor. Falls back to skeleton over mean width,
    # which is a different quantity -- so which one was used is reported.
    asp, asp_src = [], None
    for c in cracks:
        a, b = _f(c.get("EllipseMajorAxis_px")), _f(c.get("EllipseMinorAxis_px"))
        if a and b and b > 0:
            asp.append(a / b); asp_src = "ellipse major/minor"
    if not asp:
        for c in cracks:
            l, w_ = _f(c.get("SkeletonLength_px")), _f(c.get("MeanWidth_px"))
            if l and w_ and w_ > 0:
                asp.append(l / w_); asp_src = "skeleton length / mean width"

    # orientation: only cracks long enough to HAVE one, weighted by area
    ang, angw = [], []
    for c in cracks:
        o, sk, ar = _f(c.get("Orientation_deg")), _f(c.get("SkeletonLength_px")), _f(c.get("Area_px"))
        if o is not None and sk and sk >= MIN_SKELETON_PX:
            ang.append(o % 180.0); angw.append(ar or 1.0)

    tot_area = sum(areas) if areas else 0.0
    n = len(cracks)
    return {
        "frame": frame_rec.get("frame"), "arm": frame_rec.get("arm"),
        "specimen": frame_rec.get("specimen"), "modality": frame_rec.get("modality"),
        "megapixels": round(mpx, 3) if mpx else None,
        "scale_known": bool(nm), "nm_per_px": nm, "frame_area_mm2": area_mm2,
        "n_cracks": n,
        "density_per_Mpx": round(n / mpx, 2) if mpx else None,
        "density_per_mm2": round(n / area_mm2, 1) if area_mm2 else None,
        "total_area_px": round(tot_area, 1),
        "total_area_um2": round(tot_area * (nm * 1e-3) ** 2, 1) if nm else None,
        "area_fraction_pct": round(100 * _f(frame_rec.get("area_fraction") or 0), 4),
        "mean_area_px": round(_mean(areas), 1) if areas else None,
        "median_area_px": round(_median(areas), 1) if areas else None,
        "largest_share_of_area": _f(frame_rec.get("largest_share_of_area")),
        "mean_length_px": round(_mean(lens_all), 1) if lens_all else None,
        "mean_length_uncensored_px": round(_mean(lens_unc), 1) if lens_unc else None,
        "median_length_px": round(_median(lens_all), 1) if lens_all else None,
        "n_censored": sum(1 for c in cracks if c.get("length_is_censored")),
        "mean_length_um": round(_mean(lens_all) * nm * 1e-3, 3) if (lens_all and nm) else None,
        "mean_aspect": round(_mean(asp), 2) if asp else None,
        "median_aspect": round(_median(asp), 2) if asp else None,
        "aspect_source": asp_src,
        "orientation": axial_mean_deg(ang, angw),
    }


#: (key, label, how to combine across frames, unit)
SUMMARY = [
    ("n_cracks", "Crack count", "sum", "cracks"),
    # the px and physical-unit variants need DISTINCT labels: with the same label the table
    # shows two rows called "Number density", one of them blank, and a reader cannot tell
    # whether that is a missing value or a duplicate.
    ("density_per_Mpx", "Number density (per megapixel)", "mean", "cracks / Mpx"),
    ("density_per_mm2", "Number density (per mm2, scale needed)", "mean", "cracks / mm2"),
    ("total_area_px", "Total crack area (pixels)", "sum", "px2"),
    ("total_area_um2", "Total crack area (um2, scale needed)", "sum", "um2"),
    ("area_fraction_pct", "Crack area fraction", "mean", "% of frame"),
    ("mean_area_px", "Average crack area", "mean", "px2"),
    ("median_area_px", "Median crack area", "mean", "px2"),
    ("mean_length_px", "Average length (all)", "mean", "px"),
    ("mean_length_uncensored_px", "Average length (uncensored only)", "mean", "px"),
    ("mean_aspect", "Average aspect ratio", "mean", "length / width"),
]


def group_summary(frames, cracks_by_frame):
    """Aggregate a set of frames. Per-frame rows come back too, because the spread between
    frames is usually larger than any difference between groups."""
    rows = [frame_stats(f, cracks_by_frame.get((f.get("arm"), f.get("frame")), []))
            for f in frames]
    out = {"n_frames": len(rows), "per_frame": rows,
           "specimens": sorted({r["specimen"] for r in rows if r.get("specimen")}),
           "scale_known_frames": sum(1 for r in rows if r["scale_known"])}
    for key, label, how, unit in SUMMARY:
        vals = [r[key] for r in rows if r.get(key) is not None]
        if not vals:
            out[key] = {"value": None, "n": 0, "label": label, "unit": unit,
                        "why_none": "no frame in this group can supply it"}
            continue
        v = sum(vals) if how == "sum" else _mean(vals)
        out[key] = {"value": round(v, 4), "n": len(vals), "label": label, "unit": unit,
                    "how": how, "spread_min": round(min(vals), 4),
                    "spread_max": round(max(vals), 4),
                    "median_over_frames": round(_median(vals), 4)}
    # orientation is pooled over CRACKS, area-weighted, not averaged over frame means
    ang, angw = [], []
    for f in frames:
        for c in cracks_by_frame.get((f.get("arm"), f.get("frame")), []):
            o, sk, ar = _f(c.get("Orientation_deg")), _f(c.get("SkeletonLength_px")), _f(c.get("Area_px"))
            if o is not None and sk and sk >= MIN_SKELETON_PX:
                ang.append(o % 180.0); angw.append(ar or 1.0)
    out["orientation"] = axial_mean_deg(ang, angw)
    out["orientation"]["note"] = (
        "axial circular mean, area-weighted, over cracks with a skeleton of at least "
        f"{MIN_SKELETON_PX:g} px. R is the resultant length: below {R_MEANINGFUL} there is "
        "no preferred direction and the mean angle should not be quoted.")
    tot_c = sum(r["n_cracks"] for r in rows)
    tot_cen = sum(r["n_censored"] for r in rows)
    out["censoring"] = {
        "n_cracks": tot_c, "n_censored": tot_cen,
        "pct_censored": round(100 * tot_cen / tot_c, 2) if tot_c else None,
        "note": "a censored crack runs out of the frame, so its length is a LOWER BOUND. "
                "Compare 'all' against 'uncensored only' -- if they differ a lot, no single "
                "average length is defensible for this group."}
    return out


def compare(a, b, label_a="A", label_b="B"):
    """Two groups side by side. Differences only; no p-value unless the design can carry one."""
    diffs = []
    for key, label, how, unit in SUMMARY:
        va, vb = a.get(key, {}).get("value"), b.get(key, {}).get("value")
        if va is None or vb is None:
            diffs.append({"key": key, "label": label, "unit": unit, "a": va, "b": vb,
                          "delta": None, "ratio": None,
                          "note": "not available on both sides"})
            continue
        diffs.append({"key": key, "label": label, "unit": unit,
                      "a": va, "b": vb, "delta": round(vb - va, 4),
                      "ratio": round(vb / va, 3) if va else None,
                      "how": how})
    oa, ob = a.get("orientation", {}), b.get("orientation", {})
    da = None
    if oa.get("mean_deg") is not None and ob.get("mean_deg") is not None:
        d = abs(ob["mean_deg"] - oa["mean_deg"]) % 180.0
        da = round(min(d, 180.0 - d), 2)          # axial separation, never more than 90
    na, nb = a.get("n_frames", 0), b.get("n_frames", 0)
    spec_overlap = sorted(set(a.get("specimens", [])) & set(b.get("specimens", [])))
    return {
        "label_a": label_a, "label_b": label_b, "n_frames_a": na, "n_frames_b": nb,
        "rows": diffs,
        "orientation": {"a_deg": oa.get("mean_deg"), "b_deg": ob.get("mean_deg"),
                        "a_R": oa.get("R"), "b_R": ob.get("R"),
                        "axial_separation_deg": da,
                        "meaningful": bool(oa.get("meaningful") and ob.get("meaningful")),
                        "note": "axial separation is at most 90 degrees by construction. If "
                                "either R is low the two mean angles are not comparable."},
        "caveats": _caveats(a, b, na, nb, spec_overlap),
    }


def _caveats(a, b, na, nb, spec_overlap):
    """What would make this comparison unreadable. Stated before the numbers are read."""
    out = []
    if na < 3 or nb < 3:
        out.append(f"{label_n(na, nb)} fewer than 3 frames, so no interval and no test is "
                   f"available for this comparison -- read it as a description, not a result.")
    if spec_overlap:
        out.append("Both groups contain frames from the same specimen "
                   f"({', '.join(spec_overlap)}). Those frames are not independent of each "
                   "other, so a difference here is partly a within-specimen difference.")
    if a.get("scale_known_frames", 0) != a.get("n_frames") or \
       b.get("scale_known_frames", 0) != b.get("n_frames"):
        out.append("Not every frame has a recovered pixel size, so the micrometre and "
                   "per-mm2 rows are computed over a SUBSET. The pixel rows use every frame.")
    sa = {r.get("modality") for r in a.get("per_frame", [])}
    sb = {r.get("modality") for r in b.get("per_frame", [])}
    if (sa | sb) - {None} and sa != sb:
        out.append(f"The groups are not the same modality ({sorted(sa - {None})} against "
                   f"{sorted(sb - {None})}). A pixel is a different physical size in each, "
                   "so only the dimensionless rows -- area fraction, aspect ratio, angle -- "
                   "can be compared directly.")
    cen_a = a.get("censoring", {}).get("pct_censored") or 0
    cen_b = b.get("censoring", {}).get("pct_censored") or 0
    if max(cen_a, cen_b) >= 10:
        out.append(f"Censoring differs or is high ({cen_a}% against {cen_b}% of cracks "
                   "running out of frame). Every length here is a lower bound.")
    return out


def label_n(na, nb):
    if na < 3 and nb < 3:
        return "Both groups have"
    return "One group has"
