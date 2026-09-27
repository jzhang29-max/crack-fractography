#!/usr/bin/env python3
"""Split a skeleton at its junctions and measure each branch.

WHY THE UNIT OF ANALYSIS IS THE SEGMENT, NOT THE COMPONENT. Three quantities the app
reported were computed on whole connected components, and all three are wrong at that scale:

  * Orientation was the second-moment major axis of the component. For a branched network
    that is noise, and for a symmetric 4-way junction it is arbitrary. Le Roux et al.
    (Micron 2013) measure heat-checking on crack BRANCHES for exactly this reason.
  * The rose was weighted by component AREA, which makes it a width-weighted rose: one short
    wide crack outvotes a long thin one, though the long one is more of a crack.
  * Tortuosity was path/chord gated on a component having exactly 2 skeleton endpoints and 0
    branch points. Measured on this corpus that gate admits 43.7% of regions holding 2.6% of
    the crack area, and 0 of 285 TXM regions. It describes almost nothing.

R_L REPLACES TORTUOSITY, and it is a different quantity, not a rename. Quantitative
fractography's roughness parameter (Underwood & Banerji) is true length / length PROJECTED ON
A DECLARED AXIS. Projecting on the crack's own chord -- what path/chord does -- measures how
bent a crack is relative to itself, which is undefined for a branched one. Projecting on a
stated specimen axis is defined for every profile and is what the fatigue literature reports.
The axis is an input, defaulting to image x, and it is recorded in the output so a reader
knows what the number is relative to.

R_L >= 1 by construction and that is asserted, not hoped: this project has already published
impossible sub-1 tortuosities from a pixel-count numerator.
"""
import numpy as np
from scipy import ndimage as ndi
from skimage import morphology

#: A short skeleton branch cannot point anywhere except along the pixel lattice, so its
#: angle and its R_L are digitisation, not geometry. Measured on MAR_H_AS_CBS_0001: the
#: median branch is 5.24 px, 24.6% of branches have R_L within 0.001 of sqrt(2) and 10.6%
#: sit at exactly 1.0 -- 35% on two lattice values -- and the chord-angle histogram spikes
#: at 0/45/90/135 deg. For a chord of n px the angular quantisation is about atan(1/n), so
#: 5 deg resolution needs n >= 11 and 20 px gives margin. Counts and junctions still use
#: every branch; only DIRECTION-dependent quantities are gated, and the retained length
#: share is reported so the gate is visible rather than silent.
MIN_DIRECTIONAL_PX = 20

#: 8-connectivity neighbour count kernel, centre excluded.
_K = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], np.uint8)


def _neighbours(skel):
    return ndi.convolve(skel.astype(np.uint8), _K, mode="constant", cval=0)


def skeleton_segments(mask, axis_deg=0.0):
    """Branch-level measurement of one mask.

    Returns (segments, summary). A segment is a maximal run of skeleton pixels between
    junctions/endpoints. Angles are in 0-180 (an axis, not a direction).
    """
    skel = morphology.skeletonize(mask)
    if not skel.any():
        return [], {"n_segments": 0, "note": "no skeleton"}

    nb = _neighbours(skel)
    junction = skel & (nb >= 3)
    # Removing junction pixels splits the skeleton into its branches. Junctions are counted
    # separately rather than assigned to a branch, so no branch borrows another's length.
    branches = skel & ~junction
    lab, n = ndi.label(branches, structure=np.ones((3, 3), np.uint8))

    ax = np.deg2rad(axis_deg)
    ux, uy = np.cos(ax), np.sin(ax)

    segs = []
    objs = ndi.find_objects(lab)
    for i, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        sub = lab[sl] == i
        npx = int(sub.sum())
        if npx < 2:
            continue                      # a single pixel has no direction and no length
        ys, xs = np.nonzero(sub)
        ys = ys + sl[0].start
        xs = xs + sl[1].start
        # Path length by Euclidean steps along the branch, via its two extreme points'
        # geodesic. For a simple branch the pixel run IS the path, so the step sum over the
        # ordered run is the length; ordering a thin run by projection on its own principal
        # axis is stable and avoids a graph walk.
        pts = np.stack([xs, ys], 1).astype(np.float64)
        c = pts.mean(0)
        d = pts - c
        # principal direction of the branch
        u, s_, vt = np.linalg.svd(d, full_matrices=False)
        dirv = vt[0]
        order = np.argsort(d @ dirv)
        p = pts[order]
        steps = np.hypot(*(p[1:] - p[:-1]).T)
        length = float(steps.sum())
        chord = float(np.hypot(*(p[-1] - p[0])))
        if length <= 0:
            continue
        # Angle of the branch's end-to-end chord, folded to 0-180.
        v = p[-1] - p[0]
        ang = float(np.degrees(np.arctan2(v[1], v[0])) % 180.0)
        # R_L: true length over length projected on the DECLARED axis.
        proj = abs(float(v[0] * ux + v[1] * uy))
        r_l = (length / proj) if proj > 1e-9 else None
        segs.append({"n_px": npx, "length_px": round(length, 3),
                     "chord_px": round(chord, 3),
                     "angle_deg": round(ang, 2),
                     "R_L": (round(r_l, 4) if r_l is not None else None),
                     "R_L_axis_deg": axis_deg})

    if not segs:
        return [], {"n_segments": 0, "note": "skeleton had no measurable branch"}

    L_all = np.array([s["length_px"] for s in segs])
    # Direction-dependent quantities use only branches long enough to HAVE a direction.
    keep = [s for s in segs if s["length_px"] >= MIN_DIRECTIONAL_PX]
    L = np.array([s["length_px"] for s in keep]) if keep else np.zeros(0)
    A = np.array([s["angle_deg"] for s in keep]) if keep else np.zeros(0)
    rl = np.array([s["R_L"] for s in keep if s["R_L"] is not None], float)

    # R_L is >= 1 by construction. A value below it means the length or the projection is
    # wrong; this project shipped impossible sub-1 tortuosities once and must not again.
    bad = int((rl < 0.999).sum()) if rl.size else 0

    # LENGTH-weighted rose over 12 bins of 15 deg. Length, not area: a rose weighted by area
    # is a rose weighted by width.
    if len(A):
        hist, edges = np.histogram(A, bins=12, range=(0, 180), weights=L)
    else:
        hist, edges = np.zeros(12), np.linspace(0, 180, 13)
    tot = hist.sum()

    # How much of the skeleton the directional gate kept. A rose built on 8% of the length
    # is a different claim from one built on 80%.
    kept_share = float(L.sum() / L_all.sum()) if L_all.sum() else 0.0
    # Lattice diagnostic on ALL branches: if this is high the skeleton, not the crack, is
    # setting the directions.
    rl_all = np.array([s["R_L"] for s in segs if s["R_L"] is not None], float)
    lattice = (float(((np.abs(rl_all - np.sqrt(2)) < 1e-3) | (np.abs(rl_all - 1.0) < 1e-3)).mean())
               if rl_all.size else None)

    njunc = int(ndi.label(junction, structure=np.ones((3, 3), np.uint8))[1]) if junction.any() else 0
    nb_j = nb[junction]
    summary = {
        "n_segments": len(segs),
        "total_segment_length_px": round(float(L_all.sum()), 1),
        "median_segment_length_px": round(float(np.median(L_all)), 2),
        "min_directional_px": MIN_DIRECTIONAL_PX,
        "n_segments_directional": len(keep),
        "directional_length_share": round(kept_share, 4),
        "lattice_locked_share_all_segments": (round(lattice, 4) if lattice is not None else None),
        "R_L_median": (round(float(np.median(rl)), 4) if rl.size else None),
        "R_L_n": int(rl.size),
        "R_L_axis_deg": axis_deg,
        "R_L_below_one": bad,
        "n_junctions": njunc,
        "n_triple": int((nb_j == 3).sum()),
        "n_quadruple_plus": int((nb_j >= 4).sum()),
        # DiameterJ's characteristic length: centreline length per junction.
        "characteristic_length_px": (round(float(L.sum() / njunc), 2) if njunc else None),
        "rose_bin_deg": [int(e) for e in edges[:-1]],
        "rose_length_share": ([round(float(h / tot), 4) for h in hist] if tot else None),
        "rose_weighted_by": "segment length",
    }
    return segs, summary
