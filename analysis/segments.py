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

THERE IS NO PATH-ROUGHNESS READ-OUT HERE, AND THAT IS DELIBERATE. R_L (Underwood &
Banerji) is true length over length projected on a DECLARED specimen axis, so it needs an
axis someone declared. This app has nowhere to declare one. It shipped R_L anyway with the
axis defaulted to image x, and the default was never once overridden: R_L_axis_deg was 0.0
on all 356 frames. Against a fixed image axis the projection is chord * |cos(theta)|, so

    R_L  ==  (length / chord) * sec(theta)

identically -- algebra, not a measurement. The shipped column was median sec(chord angle)
times a small digitisation factor, and its corpus median AND 75th percentile were both
exactly 1.4142: sec(45 deg), which is at once a lattice diagonal, a straight 45-degree
crack and the isotropy expectation, three things the number cannot tell apart. It also
ran -0.78 (gated) / -0.83 (machine) / -0.45 (txm) against rose_R, which answers the same
orientation question and, unlike R_L, carries a per-frame permutation null.

So the metric is gone rather than fixed, and the app states the removal (see
conclusions.REFUSALS) instead of printing an em-dash. If a declared axis is ever available
it belongs on the rose, which already has the null: re-expressing rose_theta_deg in a
declared frame re-expresses a tested number instead of creating an untested one.
"""
import numpy as np
from scipy import ndimage as ndi
from skimage import morphology

#: A short skeleton branch cannot point anywhere except along the pixel lattice, so its
#: angle is digitisation, not geometry. Measured on MAR_H_AS_CBS_0001: the median branch is
#: 22.7 px, the chord-angle histogram spikes hard at 0/45/90/135 deg, and 63.6% of all
#: branches have a chord indistinguishable from a lattice direction -- 43.1% even among
#: those long enough to pass the gate below.
#: For a chord of n px the angular quantisation is about atan(1/n), so
#: 5 deg resolution needs n >= 11 and 20 px gives margin. Counts and junctions still use
#: every branch; only DIRECTION-dependent quantities are gated, and the retained length
#: share is reported so the gate is visible rather than silent.
MIN_DIRECTIONAL_PX = 20

#: Transverse uncertainty on a skeleton branch's end-to-end chord, in pixels. Two, not one,
#: and not a tuned figure: the chord runs between two endpoints and skeletonisation places
#: each to within about a pixel, so their connecting direction carries a pixel of wobble at
#: each end. One pixel is also the wrong number arithmetically -- a chord exactly one pixel
#: off a lattice direction subtends exactly asin(1/c), so a one-pixel threshold puts the
#: commonest case precisely ON the boundary and lets float error decide it.
CHORD_WOBBLE_PX = 2.0

#: Permutation draws for the anisotropy null. 1000 is enough for a 95th
#: percentile and is vectorised, so it costs a few ms per frame.
ROSE_NULL_DRAWS = 1000

#: 8-connectivity neighbour count kernel, centre excluded.
_K = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], np.uint8)


#: The summary's field set, with every value None, so a frame with no skeleton returns the
#: SAME SHAPE as one with cracks. Two early returns used to hand back a two-key dict, so any
#: consumer reading a real field -- rose_beats_null -- raised KeyError on the 8 zero-crack
#: frames in this corpus instead of reading "no verdict".
def _empty_summary(note):
    keys = ("total_segment_length_px", "median_segment_length_px", "n_segments_directional",
            "directional_length_share", "lattice_chord_share_all_segments",
            "n_junctions", "n_triple", "n_quadruple_plus",
            "characteristic_length_px", "rose_bin_deg", "rose_length_share", "rose_R",
            "rose_theta_deg", "rose_R_null95", "rose_beats_null")
    out = {k: None for k in keys}
    out.update(n_segments=0, note=note, min_directional_px=MIN_DIRECTIONAL_PX,
               rose_weighted_by="segment length",
               junction_order_counted_per="cluster (branches meeting), not per skeleton pixel",
               rose_null=None)
    return out


def _neighbours(skel):
    return ndi.convolve(skel.astype(np.uint8), _K, mode="constant", cval=0)


def skeleton_segments(mask):
    """Branch-level measurement of one mask.

    Returns (segments, summary). A segment is a maximal run of skeleton pixels between
    junctions/endpoints. Angles are in 0-180 (an axis, not a direction).
    """
    skel = morphology.skeletonize(mask)
    if not skel.any():
        return [], _empty_summary("no skeleton")

    nb = _neighbours(skel)
    junction = skel & (nb >= 3)
    # Removing junction pixels splits the skeleton into its branches. Junctions are counted
    # separately rather than assigned to a branch, so no branch borrows another's length.
    branches = skel & ~junction
    lab, n = ndi.label(branches, structure=np.ones((3, 3), np.uint8))

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
        # Is this chord's angle DISTINGUISHABLE from a lattice direction? Not "exactly on
        # one" -- over a 318 px chord a single-pixel tip wobble is 0.18 deg off axis, and
        # an equality test calls that off-lattice where no reader would. The tolerance is
        # the angle subtended by CHORD_WOBBLE_PX of transverse deviation over this chord,
        # asin(w/c), so it is the chord's own angular resolution rather than a fixed
        # degree figure: a 5 px stub is locked within 24 deg (at that length every
        # direction is within 22.5 deg of a lattice one, which is the honest answer -- it
        # cannot point anywhere else), a 300 px branch within 0.4 deg. Relative to the
        # PIXEL lattice, the thing being diagnosed. Nothing here is relative to a specimen
        # axis, because this app has none to declare.
        lat = min(abs(ang - t) for t in (0.0, 45.0, 90.0, 135.0, 180.0))
        segs.append({"n_px": npx, "length_px": round(length, 3),
                     "chord_px": round(chord, 3),
                     "angle_deg": round(ang, 2),
                     "chord_on_lattice": bool(
                         np.deg2rad(lat) <= np.arcsin(
                             min(1.0, CHORD_WOBBLE_PX / max(chord, 1.0))))})

    if not segs:
        return [], _empty_summary("skeleton had no measurable branch")

    L_all = np.array([s["length_px"] for s in segs])
    # Direction-dependent quantities use only branches long enough to HAVE a direction.
    keep = [s for s in segs if s["length_px"] >= MIN_DIRECTIONAL_PX]
    L = np.array([s["length_px"] for s in keep]) if keep else np.zeros(0)
    A = np.array([s["angle_deg"] for s in keep]) if keep else np.zeros(0)

    # LENGTH-weighted rose over 12 bins of 15 deg. Length, not area: a rose weighted by area
    # is a rose weighted by width.
    if len(A):
        hist, edges = np.histogram(A, bins=12, range=(0, 180), weights=L)
    else:
        hist, edges = np.zeros(12), np.linspace(0, 180, 13)
    tot = hist.sum()

    # ANISOTROPY, WITH A NULL. A bare rose is uninterpretable and this one was shipped
    # without a null for weeks. The reason it matters here, measured: a synthetic mask of
    # perfectly straight 3-px lines at UNIFORM RANDOM angles returns R = 0.267-0.285, which
    # is at or ABOVE this corpus's median R of 0.257. So the observed R alone cannot
    # distinguish "preferentially oriented" from "random", and a reader looking at a lopsided
    # rose would conclude the former every time.
    #
    # Axial statistics, on DOUBLED angles: a crack has an axis, not a direction, so 10 deg
    # and 170 deg are nearly the same orientation and must not cancel. Mardia & Jupp,
    # Directional Statistics, for the construction.
    #
    # The null is a permutation: uniform random directions carrying the OBSERVED segment
    # lengths. That is the right null because R depends on the length distribution -- a few
    # long segments give a high R by chance, which is exactly how a rose over 103 segments
    # can look anisotropic and mean nothing. Deterministic seed so a frame's verdict does
    # not change between runs.
    R = theta = R_null95 = None
    if len(A) and L.sum() > 0:
        w = L / L.sum()
        two = np.deg2rad(2.0 * A)
        C, S = float((w * np.cos(two)).sum()), float((w * np.sin(two)).sum())
        R = float(np.hypot(C, S))
        theta = float((np.rad2deg(np.arctan2(S, C)) / 2.0) % 180.0)
        rng = np.random.default_rng(0)
        draws = rng.uniform(0.0, 2.0 * np.pi, size=(ROSE_NULL_DRAWS, len(w)))
        Rn = np.hypot((w * np.cos(draws)).sum(axis=1), (w * np.sin(draws)).sum(axis=1))
        R_null95 = float(np.percentile(Rn, 95))

    # How much of the skeleton the directional gate kept. A rose built on 8% of the length
    # is a different claim from one built on 80%.
    kept_share = float(L.sum() / L_all.sum()) if L_all.sum() else 0.0
    # Digitisation diagnostic on ALL branches: if this is high the skeleton, not the crack,
    # is setting the directions. The share whose chord is indistinguishable from a lattice
    # axis or diagonal, per the CHORD_WOBBLE_PX tolerance above -- so it is relative to the
    # pixel grid and to nothing anyone declares. The version it replaces counted R_L near
    # 1.0 or sqrt(2), which measured the same thing only while the declared axis sat on the
    # lattice and collapsed by ~100x otherwise.
    # NO THRESHOLD IS ATTACHED. Nothing consumes this; it is here to be read in the JSON.
    lattice = (round(float(np.mean([s["chord_on_lattice"] for s in segs])), 4)
               if segs else None)

    # Junction ORDER is counted per cluster, not per pixel. Counting pixels reported 3,074
    # junctions alongside "10,359 triple, 5,156 quad+" -- 15,515 pixels against 3,074
    # clusters, two different units printed as if they were one, which reads as a
    # contradiction. A junction is a place where branches meet, so its order is the number of
    # distinct branches touching it. This also matters because skeletonisation manufactures
    # nodes: a true 4-way crossing usually thins to two adjacent 3-way pixels, and only the
    # cluster view sees that as one crossing.
    jlab, njunc = (ndi.label(junction, structure=np.ones((3, 3), np.uint8))
                   if junction.any() else (np.zeros_like(lab), 0))
    n_triple = n_quad = 0
    if njunc:
        # Dilate each junction cluster by one pixel and count the distinct branch labels it
        # touches. That count is the cluster's order.
        for i, sl in enumerate(ndi.find_objects(jlab), start=1):
            if sl is None:
                continue
            pad = (slice(max(0, sl[0].start - 1), sl[0].stop + 1),
                   slice(max(0, sl[1].start - 1), sl[1].stop + 1))
            here = jlab[pad] == i
            grown = ndi.binary_dilation(here, np.ones((3, 3), bool))
            touching = np.unique(lab[pad][grown & (lab[pad] > 0)])
            order = int(touching.size)
            if order == 3:
                n_triple += 1
            elif order >= 4:
                n_quad += 1
    summary = {
        "n_segments": len(segs),
        "total_segment_length_px": round(float(L_all.sum()), 1),
        "median_segment_length_px": round(float(np.median(L_all)), 2),
        "min_directional_px": MIN_DIRECTIONAL_PX,
        "n_segments_directional": len(keep),
        "directional_length_share": round(kept_share, 4),
        "lattice_chord_share_all_segments": lattice,
        "n_junctions": njunc,
        "n_triple": n_triple,
        "n_quadruple_plus": n_quad,
        "junction_order_counted_per": "cluster (branches meeting), not per skeleton pixel",
        # DiameterJ's characteristic length: centreline length per junction.
        "characteristic_length_px": (round(float(L.sum() / njunc), 2) if njunc else None),
        "rose_bin_deg": [int(e) for e in edges[:-1]],
        "rose_length_share": ([round(float(h / tot), 4) for h in hist] if tot else None),
        "rose_weighted_by": "segment length",
        # The rose's own verdict. rose_beats_null is the only one of these safe to read on
        # its own; R without R_null95 beside it means nothing on this corpus.
        "rose_R": (round(R, 4) if R is not None else None),
        "rose_theta_deg": (round(theta, 1) if theta is not None else None),
        "rose_R_null95": (round(R_null95, 4) if R_null95 is not None else None),
        "rose_beats_null": (bool(R > R_null95) if (R is not None and R_null95 is not None)
                            else None),
        "rose_null": (f"uniform random directions with the observed segment lengths, "
                      f"{ROSE_NULL_DRAWS} draws, 95th percentile"),
    }
    return segs, summary
