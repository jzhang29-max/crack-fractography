#!/usr/bin/env python3
"""Line-intercept sampling: the measurement materials papers actually report.

WHY THIS IS THE BIGGEST GAP. The app reported "crack density" as skeleton length per
megapixel. Dershowitz & Herda (1992) name six incompatible densities -- P10, P20, P21, P30,
P32, P33 -- and converting between them needs a stochastic-geometry model, not a unit
change. An unlabelled "crack density" is comparable to nothing published. Worse, the form
most often quoted in the coatings and hot-cracking literature is P10, cracks per millimetre
along a test line, and this app could not compute it at all.

ASTM B456 specifies microcracked chromium as "more than 30 cracks/mm in ANY direction". That
is a MINIMUM OVER DIRECTIONS, not an average: a specimen can pass on the mean and fail the
standard. So P10 is returned as a full curve over angle, and min/mean/max are reported
separately with the angle at which the minimum occurs.

Everything here is a different reduction of ONE transition table -- lay parallel test lines
at an angle, walk them across the mask, record where they enter and leave crack:

    P10(theta)  intercepts per unit test-line length      cracks/mm
    P21         total crack length per unit area          mm/mm^2
    spacing     1 / P10(theta)                            mm
    S_V = 2*P_L crack surface per unit volume             mm^2/mm^3   (assumption-laden)

P21 is ALSO estimable from P10 by Buffon: L_A = (pi/2) * mean_theta(P_L). That is worth
computing even though the skeleton gives L_A directly, because the two disagreeing is a free
readout of skeletonisation error on thin features -- and 84.9% of regions here are under
10 px wide, where skeletonisation is least trustworthy.

S_V = 2*P_L is correct only for isotropic-uniform-random probes. From ONE section plane with
in-plane isotropic lines it holds only if crack-surface orientation is isotropic with respect
to that plane, which nobody has shown here. It is returned with that caveat attached as data,
not buried in a docstring.
"""
import numpy as np

#: 18 angles over 0-180 deg. A crack has an axis, not a direction, so 180 is the period.
N_ANGLES = 18
#: Test-line spacing in pixels. Dense enough that a 5 px crack cannot slip between lines.
LINE_SPACING_PX = 4


def _transitions_along(mask, theta_deg, spacing=LINE_SPACING_PX):
    """Walk parallel lines at theta across the mask.

    Returns (n_intercepts, total_line_length_px, in_crack_px). Sampling is done by rotating
    the COORDINATES rather than the image: rotating a binary image resamples it, which
    invents or destroys thin features -- exactly the ones this corpus is made of.
    """
    h, w = mask.shape
    t = np.deg2rad(theta_deg)
    dx, dy = np.cos(t), np.sin(t)
    # Perpendicular direction, along which the parallel lines are spaced.
    px, py = -dy, dx
    diag = float(np.hypot(h, w))
    n_lines = max(2, int(diag / spacing))
    # Centre the family on the image so coverage is symmetric.
    offsets = (np.arange(n_lines) - n_lines / 2.0) * spacing
    cx, cy = w / 2.0, h / 2.0
    steps = int(diag)
    s = np.arange(-steps / 2, steps / 2, dtype=np.float32)

    n_int = 0
    total_len = 0.0
    in_crack = 0
    for off in offsets:
        x = cx + px * off + dx * s
        y = cy + py * off + dy * s
        inside = (x >= 0) & (x < w) & (y >= 0) & (y < h)
        if not inside.any():
            continue
        xi = x[inside].astype(np.int32)
        yi = y[inside].astype(np.int32)
        v = mask[yi, xi]
        if v.size < 2:
            continue
        # A 0->1 transition is one intercept: entering a crack. Counting 1->0 as well would
        # double it; counting |diff| would too.
        n_int += int(np.count_nonzero((v[1:].astype(np.int8) - v[:-1].astype(np.int8)) == 1))
        # A crack already under the line at its first sample was entered outside the frame;
        # it is a real intercept for P10 but its entry point is censored.
        if v[0]:
            n_int += 1
        total_len += float(v.size)          # one sample per pixel step, so length == count
        in_crack += int(v.sum())
    return n_int, total_len, in_crack


def line_probe(mask, nm_per_px=None, n_angles=N_ANGLES):
    """Full directional line-intercept probe of a boolean mask.

    Physical values appear only when nm_per_px is known; otherwise the px forms stand alone
    and the mm fields are None. A crack density in mm is meaningless without a scale and a
    default would be indistinguishable from a measurement.
    """
    if mask.sum() == 0:
        return {"n_angles": n_angles, "p10_per_mm": None, "note": "no crack in this mask"}

    um_px = (nm_per_px / 1000.0) if nm_per_px else None
    angles = np.linspace(0, 180, n_angles, endpoint=False)
    pl_px, frac = [], []
    for a in angles:
        n_int, tot, inc = _transitions_along(mask, float(a))
        pl_px.append((n_int / tot) if tot else 0.0)      # intercepts per px of test line
        frac.append((inc / tot) if tot else 0.0)         # lineal fraction, Delesse/Rosiwal
    pl_px = np.asarray(pl_px)
    frac = np.asarray(frac)

    out = {
        "n_angles": int(n_angles),
        "angles_deg": [round(float(a), 1) for a in angles],
        "p10_per_px": [round(float(v), 8) for v in pl_px],
        # BUFFON IN PIXEL UNITS, ALWAYS. L_A = (pi/2) * mean(P_L) is a length per unit
        # area, so in px it is px/px^2 = 1/px, and the RATIO against the skeleton estimate
        # is dimensionless -- identical whether computed in pixels or millimetres.
        #
        # It was computed only inside `if um_px:`, so the app ran two independent
        # estimators of one quantity on 63% of frames and neither on the rest, including
        # every upload -- which is the only arm a downloaded copy has. The disagreement
        # between them IS the skeletonisation-error readout, and it was switched off
        # exactly where there is least other evidence about the mask.
        "p21_buffon_per_px": round(float(np.pi / 2 * pl_px.mean()), 10),
        "lineal_fraction_mean": round(float(frac.mean()), 6),
        "scale_known": um_px is not None,
    }
    if um_px:
        # intercepts per px -> per mm: divide by (um/px) then x1000
        per_mm = pl_px / um_px * 1000.0
        i_min = int(np.argmin(per_mm))
        out.update({
            "p10_per_mm": [round(float(v), 3) for v in per_mm],
            "p10_min_per_mm": round(float(per_mm.min()), 3),
            "p10_min_at_deg": round(float(angles[i_min]), 1),
            "p10_mean_per_mm": round(float(per_mm.mean()), 3),
            "p10_max_per_mm": round(float(per_mm.max()), 3),
            # Buffon: L_A = (pi/2) * mean P_L. An INDEPENDENT estimate of P21, to be compared
            # with the skeleton's; disagreement measures skeletonisation error, it does not
            # mean one of them is broken.
            "p21_buffon_mm_per_mm2": round(float(np.pi / 2 * per_mm.mean()), 4),
            # Mean spacing at the direction that sees the most cracks.
            "spacing_min_mm": round(float(1.0 / per_mm.max()), 5) if per_mm.max() else None,
            # S_V = 2 P_L. Caveat travels WITH the number.
            "sv_mm2_per_mm3": round(float(2 * per_mm.mean()), 3),
            "sv_assumption": ("2*P_L estimates S_V only for isotropic-uniform-random probes; "
                              "from one section plane this holds only if crack-surface "
                              "orientation is isotropic w.r.t. that plane, which is not "
                              "established for this corpus"),
        })
    else:
        out["p10_per_mm"] = None
        out["note"] = "no nm/px for this frame, so every per-mm form is withheld"
    return out
