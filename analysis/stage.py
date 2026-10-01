#!/usr/bin/env python3
"""Where on the specimen each frame was taken, and whether the fields form a gradient.

WHY THIS MATTERS MORE THAN IT SOUNDS. ASTM E562 presumes fields placed OVER a surface, so
that between-field variance is sampling error. The 2026-09-15 batch is not that: it is a 3x3
raster per cell, all nine fine fields on one small patch of one specimen, and the stage
coordinates were sitting in the metadata unused. Not "contiguous" and not a stated size:
the centre-to-centre step is about 1.5 field widths across and 2 field heights down, so
the fields do not touch; and position() below refuses to assert that the stage unit is the
metre, so no extent in millimetres is quoted here or anywhere on screen.

Measured on all four scaled MAR specimens, area fraction against stage Y, over the NINE
fields of the 51.883 nm/px determination, as the MEAN of the two simultaneously-acquired
detectors per field:

                   field mean          CBS only            ETD only         max/min
    MAR_AmbB_AS    rho +0.867 p 0.0025  +0.750 p 0.0199    +0.683 p 0.0424    4.9x
    MAR_AmbB_HIP   rho +0.883 p 0.0016  +0.867 p 0.0025    +0.650 p 0.0581   18.8x
    MAR_H_AS       rho +0.867 p 0.0025  +0.867 p 0.0025    +0.883 p 0.0016    5.3x
    MAR_H_HIP      rho +0.833 p 0.0053  +0.833 p 0.0053    +0.883 p 0.0016   12.4x

THE FIELD-MEAN COLUMN IS NEW AND THE SHIPPED COLUMN WAS CBS. The caller passed
`_one_frame_per_field`, which keeps the alphabetically first frame per field, and the
detector token sorts CBS before ETD on every pair in this corpus -- so eight shipped
records carried a CBS-only rank correlation (+0.750..+0.867) on the same card as an
interval computed from a real detector mean. Corrected to field means the range is
+0.833..+0.883. The per-detector columns are published beside it as the check that matters
here: two channels of ONE simultaneous scan over the same physical fields agree in sign on
all four specimens, so the trend is not a property of the CBS channel -- but ETD's
significance fails on MAR_AmbB_HIP (p 0.058) and its max/min spread reaches 294x there,
because ETD nearly empties on the low fields.

So the E562 interval on those specimens is largely describing a SPATIAL GRADIENT across one
patch rather than sampling error, and the consequence is practical: "measure more fields"
is the wrong remedy there, because more tiles in the same patch will not narrow an interval
that is tracking a trend.

WHAT THIS FILE MUST NOT SAY, AND SAID FOR THREE REVISIONS. "More patches would." That is an
assertion with no supporting measurement anywhere in this corpus: n_patches is 1 on the
eight positioned specimen-arms and None on the other 26, and never reaches 2, so no
between-patch variance has ever been observed here. It is a hypothesis -- the one this
result argues is worth testing, and the experiment it asks for is nine more fields at a
second patch on each specimen -- and it is stated as such below rather than as a remedy the
data supports.

TWICE-CORRECTED, AND THIS DOCSTRING HELD THE UNCORRECTED VALUES BOTH TIMES. The figures
above replace +0.537/+0.752/+0.755/+0.782, which were computed over 20 FRAMES rather than
10 fields -- CBS and ETD sit at byte-identical stage coordinates, so every point was
doubled and every p-value was up to 27x too small. specimen_stats.py fixed the caller and
this file went on printing the old numbers. They then changed again when the caller stopped
passing the 337.2396 nm/px overview field: its area fraction is measured at a 6.5x coarser
detection limit and its field of view is 10.6x a fine field's, spanning much of the raster,
so it has no position comparable to theirs. Every rho got STRONGER without it
(+0.648..+0.830 over ten fields against +0.750..+0.867 over nine), which is the check that
matters -- dropping a point must not be what creates the trend.

THE TWO FIELDS ARE NOW NAMED FOR WHAT THEY COMPUTE. Grouping is on the raw stage
coordinate rounded to six places, and the nine fields of a 3x3 raster differ in the sixth
place, so every field lands in its own group: the count is n_distinct_stage_coords (9 on a
3x3 raster, not 3) and the ratio is field_max_min_ratio, max field over min field. Both
were once called rows, and the basis line on screen said "in 9 stage rows" about a
three-row raster. A row-clustering tolerance is deliberately NOT introduced to rescue the
old names: that would be a new constant in an unasserted stage unit, invented to keep a
statistic nothing reads. The ratio is still a real spread across the patch, which is all
the sentence above it ever claimed.

The coordinates exist for the 80-frame 2026-09-15 session only. Every 316 specimen has none,
so this is reported where it can be and silent where it cannot.
"""
import csv
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

#: Minimum fields before a rank correlation over stage position means anything.
MIN_FIELDS = 6

_CACHE = {}


def _table():
    """frame stem -> (StageX, StageY), from the SEM repo's extracted FEI metadata."""
    if _CACHE:
        return _CACHE
    try:
        from app import paths as P
        sem = P.sem_repo()
    except Exception:
        sem = None
    if not sem:
        return _CACHE
    p = os.path.join(sem, "crack_export", "analysis", "fei_metadata_260915.csv")
    if not os.path.exists(p):
        return _CACHE
    for r in csv.DictReader(open(p)):
        try:
            _CACHE[os.path.splitext(r["frame"])[0]] = (float(r["StageX"]),
                                                       float(r["StageY"]))
        except (ValueError, TypeError, KeyError):
            continue
    return _CACHE


def position(stem):
    """(StageX, StageY) for a frame, or None. Units are the instrument's and are NOT
    asserted to be millimetres -- the extent is deliberately never printed in physical
    units because that has not been confirmed."""
    return _table().get(stem)


def gradient(frames, field="area_fraction"):
    """Is `field` trending across the stage for these frames?

    Returns None when the coordinates are absent, when there are too few fields, or when
    the frames sit on a single stage row -- in each case the question is not answerable
    rather than answered negatively.
    """
    import numpy as np
    from scipy import stats

    pts = []
    for f in frames:
        pos = position(f.get("frame", ""))
        v = f.get(field)
        if pos and v is not None:
            pts.append((pos[0], pos[1], float(v)))
    if len(pts) < MIN_FIELDS:
        return None

    x = np.array([p[0] for p in pts])
    y = np.array([p[1] for p in pts])
    v = np.array([p[2] for p in pts])
    out = {"n_frames_with_position": len(pts), "field": field}

    best = None
    for axis, coord in (("stage_y", y), ("stage_x", x)):
        if len(set(coord.tolist())) < 2:
            continue
        rho, pv = stats.spearmanr(coord, v)
        if rho is None or not np.isfinite(rho):
            continue
        if best is None or abs(rho) > abs(best[1]):
            best = (axis, float(rho), float(pv))
    if best is None:
        return None
    out.update(axis=best[0], spearman_rho=round(best[1], 3),
               p_value=round(best[2], 6))

    # HOW BIG THE SPREAD IS, grouped on the axis that trends. Reported because a rho says
    # "monotonic" and this says "by how much", and only the second is actionable.
    #
    # NOT a row-to-row ratio, whatever it may once have been called. Grouping is on the raw
    # coordinate rounded to six places and the nine fields of a 3x3 raster differ in the
    # sixth, so each lands in its own group: these are DISTINCT COORDINATES, nine of them,
    # and the ratio is max field over min field. The docstring above explains why the old
    # names were wrong; this was the last comment in the file still making the old claim,
    # and the local was still called `rows`.
    coord = y if best[0] == "stage_y" else x
    at_coord = {}
    for c, val in zip(coord.tolist(), v.tolist()):
        at_coord.setdefault(round(c, 6), []).append(val)
    means = np.array([float(np.mean(g)) for g in at_coord.values()])
    lo = float(means.min())
    out["n_distinct_stage_coords"] = len(at_coord)
    out["field_max_min_ratio"] = (round(float(means.max()) / lo, 1) if lo > 0 else None)
    out["significant"] = bool(best[2] < 0.05)
    # The note says what the trend DOES to the interval and stops there. It used to end
    # "more patches would", which is a remedy this corpus cannot support: n_patches is 1 on
    # every positioned arm, so between-patch variance is unobserved here. Naming it as an
    # untested hypothesis is the same discipline the rest of the app applies to a claim it
    # cannot measure -- and the alternative, asserting the fix, is exactly the kind of
    # sentence the refusal engine exists to block.
    out["note"] = ("ASTM E562 presumes fields placed over a surface. A gradient means the "
                   "between-field variance is partly a trend across one patch, so more "
                   "tiles in the same patch will not narrow the interval. Whether separated "
                   "patches would is UNTESTED here: every specimen in this corpus has one "
                   "imaged patch, so no between-patch variance has been measured.")
    return out


#: How far apart two field centres may sit and still count as one imaged site, in units of
#: the largest field's diagonal. Generous on purpose, and the direction matters: too large
#: merges two real sites and the ranking refusal keeps firing; too small splits one raster
#: and the refusal switches OFF, which is the failure that costs something. The measured
#: margin is 3.6x -- the widest nearest-neighbour gap in this corpus is 0.55 diagonals, on
#: MAR_H_AS. It also makes the rule robust to the stage unit, which position() will not
#: assert: only a stage unit larger than the metre could split these rasters.
SAME_PATCH_DIAGONALS = 2.0


def n_patches(frames):
    """How many separated imaged sites these frames cover, or None if unanswerable.

    Single-linkage on the field centres, linking at SAME_PATCH_DIAGONALS times the largest
    field diagonal. None -- not 1 -- when any frame lacks a stage coordinate or a pixel
    scale, because "one site" and "we cannot tell" are different answers and only the
    first one should ever be allowed to switch a refusal off.

    Today: 1 on the eight positioned SEM specimen-arms, None on the other twenty-six. It
    exists as the off-switch a genuinely second site would trip with no code edit, and it
    is never displayed -- comparing a stage distance to a pixel scale assumes both are the
    same length unit, which is fine for an internal gate and is not fine on screen.
    """
    import math

    centres, diag = [], 0.0
    for f in frames:
        pos = position(f.get("frame", ""))
        nm, w, h = f.get("nm_per_px"), f.get("width_px"), f.get("height_px")
        if not pos or not nm or not w or not h:
            return None
        centres.append(pos)
        diag = max(diag, math.hypot(nm * 1e-9 * w, nm * 1e-9 * h))
    if not centres:
        return None

    link = SAME_PATCH_DIAGONALS * diag
    unseen, groups = list(dict.fromkeys(centres)), 0
    while unseen:
        stack, groups = [unseen.pop()], groups + 1
        while stack:
            a = stack.pop()
            near = [b for b in unseen if math.dist(a, b) <= link]
            for b in near:
                unseen.remove(b)
            stack.extend(near)
    return groups
