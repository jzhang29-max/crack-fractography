#!/usr/bin/env python3
"""Where on the specimen each frame was taken, and whether the fields form a gradient.

WHY THIS MATTERS MORE THAN IT SOUNDS. ASTM E562 presumes fields placed OVER a surface, so
that between-field variance is sampling error. The 2026-09-15 batch is not that: it is a 3x3
contiguous raster per cell, tiling roughly 1.2 x 1.1 mm of one specimen, and the stage
coordinates were sitting in the metadata unused.

Measured on all four scaled MAR specimens, area fraction against stage Y:

    MAR_AmbB_AS    rho +0.537  p 0.0146   row-to-row mean ratio  4.9x
    MAR_AmbB_HIP   rho +0.752  p 0.0001                         68.4x
    MAR_H_AS       rho +0.755  p 0.0001                          5.3x
    MAR_H_HIP      rho +0.782  p 0.00005                        12.4x

All four are monotonic and significant. So the E562 interval on those specimens is largely
describing a SPATIAL GRADIENT across one patch rather than sampling error -- and the
consequence is practical: "measure more fields" is the wrong remedy there, because more
tiles in the same patch will not narrow an interval that is tracking a trend. More patches
would.

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

    # Row-to-row ratio, grouped on the axis that trends. Reported because a rho says
    # "monotonic" and this says "by how much", and only the second is actionable.
    coord = y if best[0] == "stage_y" else x
    rows = {}
    for c, val in zip(coord.tolist(), v.tolist()):
        rows.setdefault(round(c, 6), []).append(val)
    means = np.array([float(np.mean(r)) for r in rows.values()])
    lo = float(means.min())
    out["n_stage_rows"] = len(rows)
    out["row_mean_ratio"] = (round(float(means.max()) / lo, 1) if lo > 0 else None)
    out["significant"] = bool(best[2] < 0.05)
    out["note"] = ("ASTM E562 presumes fields placed over a surface. A gradient means the "
                   "between-field variance is partly a trend across one patch, so more "
                   "tiles in the same patch will not narrow the interval -- more patches "
                   "would.")
    return out
