#!/usr/bin/env python3
"""Intergranular versus transgranular, from a crack mask AND a co-registered grain map.

WHY THIS NEEDS A SECOND IMAGE, AND WHY THE MASK-ONLY VERSION IS NOT HERE. The distinction is
defined by the crack path's relationship to grain boundaries, so the boundaries have to be
visible and registered with the crack. Both routes from the micrograph alone were built and
measured in this project and both died on a geometric budget rather than on tuning
(`analysis/conclusions.REFUSALS`, question "Transgranular or intergranular?"):

  * boundary coincidence computed from the SEM image itself reads its own input -- a median
    72.8% of labelled pixels are saturated at DN 0, a ~215 DN silhouette step against the
    15-25 DN step that defines a grain edge -- and the crack's self-response reaches zero
    only beyond 80 px, which is 0.38-0.57 grain diameters here;
  * the facet-vertex route needs facets of >= 250 px (>= 13 um) and this corpus's largest
    resolvable microstructural intercept is 3.02 um.

The positive control is what settled it: a synthetic path built FROM the frame's own boundary
skeleton caps at z = +0.62 under any legitimate exclusion, while the real labels scored
z = +2.0 to +3.4 -- above the ceiling a known-true path can reach, so that was contamination.
`docs/CLAIMS.md` names the one open route: EBSD on the same fields, or an etched
co-registered image. This module is that route and refuses to run without it.

WHAT IT REPORTS, AND WHY IT IS NOT ONE NUMBER. A bare "62% intergranular" is unreadable
without three things beside it, so all three ship on every run:

  SATURATION -- the share of the WHOLE FIELD already within tolerance of a boundary. This is
      what a path scores by being anywhere at all. It is the floor, and it is the statistic
      that killed the image-only route: with a large enough tolerance a perfect grain
      partition puts 85-100% of the material within reach of a boundary and the answer is
      decided before the crack is looked at. `verdict` refuses above SATURATION_CEILING.
  THE THREE CONTROLS -- all geometry-matched to the real crack, because a control that does
      not hold path shape and length fixed is testing the wrong thing:
        positive  a walk along the boundary skeleton of the same length. Must score ~1.
        negative  the same crack path placed where its mean distance to a boundary is
                  greatest. Must score near the floor.
        null      the same crack path at many random placements and lattice orientations.
                  The real score is reported as a z against this, not in isolation.
  THE DISTRIBUTION of per-segment boundary fraction, not only the binned percentages. If that
      distribution is unimodal, the two classes are an artefact of the threshold and the
      binned numbers should not be quoted; `verdict` says so.

UNITS. Percentages are LENGTH-weighted over the skeleton by default and AREA-weighted
alongside, because the two disagree whenever width covaries with mode and a reader cannot
tell which was meant. Both are always emitted.

TOLERANCE. `tau_px` is the distance from a boundary at which a centreline pixel still counts
as on it. It is a declared input, not a tuned one: it should be the registration error
between the two images plus the boundary's own rendered width. It is swept on every run and
the sweep ships, because a conclusion that holds only at one tau is a conclusion about tau.

THE THRESHOLDS, IN ONE PLACE. Every number this module can be argued with, what it does, and
whether it was chosen or counted:

  WHAT IS A JUNCTION
    >= 3 neighbours      a skeleton pixel with three or more of its eight neighbours also
                         skeleton is a CANDIDATE. A count, not a choice: a pixel on a line has
                         two, so three is the first value that can mean a branch.
    MIN_JUNCTION_DEGREE  a connected CLUSTER of candidates is one node, and is a node when at
                         least this many branches leave it. Also a count. The per-pixel test
                         over-marks by about 5x -- an axis-aligned crossing lights its centre
                         and all four arms -- so nodes are clusters, and a cluster's degree is
                         the number of distinct branches incident on it.
    REGULARISE_PX        the first of the two tunable numbers here. Clustering the pixels
                         exposed a second fault underneath it: inside a wide crack with a
                         pixel-rough wall the medial axis is a WEB of members running wall to
                         wall, and every intersection is a real node of that skeleton, so
                         clustering cannot help. A closing of the wall at this radius removes
                         the cause. It is additive -- no crack pixel is ever lost -- and both
                         the area it adds and any fragments it bridges are reported on every
                         run. See the constant for the five families this was chosen over and
                         the synthetic they were measured against.
    MIN_BRANCH_WIDTHS    the second, and the width-scaled answer to "how far apart must two
                         junctions be". A node needs MIN_JUNCTION_DEGREE branches at least this
                         multiple of the LOCAL CRACK WIDTH long, because two paths are not
                         distinguishable over a run shorter than the channel is wide. After the
                         closing, 96.7% of the surviving nodes on one frame still failed this.
                         It deletes nothing: a demoted cluster's pixels go back to the skeleton
                         and the branches rejoin.

  HOW FAR APART TWO JUNCTIONS MUST BE
    MIN_SEGMENT_PX       absolute floor on branch length. Removes many branches and little
                         length: 896 of 2,218 branches but 4.1% of the skeleton on
                         260622_316_H_b2_front_CBS_02.
    MIN_SEGMENT_WIDTHS   floor relative to the branch's OWN crack width. Defaults OFF; see the
                         constant for the measured reason, which is that it is a deleter.

  WHAT MAKES A BRANCH INTERGRANULAR -- note that this is NOT a distance between junctions
    tau_px               coincidence route only: how close to a boundary still counts as on
                         it. Declared per run from the registration error, and swept.
    standoff_px          flank route only: how far past the crack wall the two flank samples
                         are taken. A geometric budget, not a knob -- it has to clear the
                         local crack half-width and stay inside the flanking grain -- and it
                         is swept, because where no value does both the answer tracks it.
    THETA_HI / THETA_LO  a branch is intergranular at or above 0.70 of its length on a
                         boundary and transgranular at or below 0.30. Two thresholds rather
                         than one so the mixed population stays visible instead of being
                         forced to a side.

  WHEN THE ANSWER MAY NOT BE QUOTED
    SATURATION_CEILING       0.50 of the field already within tau of a boundary.
    FLANK_MIN_POSITIVE       80%, by flank comparison, for a path on the partition's own
                             boundaries.
    FLANK_MIN_RESOLUTION_PP  50 points between the positive and negative controls.
    FLANK_SPAN_CEILING_PP    10 points of movement across the standoff sweep.
    FLANK_MIN_DECIDABLE      0.50 of the centreline with indexed material on both flanks.
    MIN_SEGMENTS             8 branches before per-segment percentages are a distribution.
    MIN_PER_CLASS_FOR_AUC    12 per class before the shortcut AUC is computed at all.
"""
import argparse
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from skimage import morphology

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

#: Above this share of the field lying within tau of a boundary, the measurement has no room
#: to discriminate and the run is refused. 0.50 is where a coin flip and a perfect
#: boundary-follower are within one doubling of each other.
SATURATION_CEILING = 0.50

#: A segment is called intergranular at or above this fraction of its length on a boundary,
#: transgranular at or below (1 - this), and MIXED between. Two thresholds rather than one,
#: because a forced binary call hides the mixed population, which on a real crack is large.
THETA_HI = 0.70
THETA_LO = 0.30

#: Placements drawn for the null. The z is reported with this n so it can be read.
NULL_DRAWS = 200

#: Below this many segments, per-segment percentages are not reported as a distribution.
MIN_SEGMENTS = 8

#: Per class, below this the shortcut AUC is refused: it would describe the imbalance.
MIN_PER_CLASS_FOR_AUC = 12

#: Replicates drawn for each flank control, so the controls have a SPREAD and not just a value.
#: Without it the resolution gate compares two single numbers and is blind to their variance,
#: which is the specific failure Z' was invented to catch.
FLANK_CONTROL_REPLICATES = 8

#: Z' below this is refused. Z' = 1 - 3(sd_pos + sd_neg) / |mean_pos - mean_neg| is the
#: screening-assay separation statistic of Zhang, Chung & Oldenburg (J. Biomol. Screen.
#: 4:67-73, 1999), where >= 0.5 is the conventional "excellent assay" line and <= 0 means the
#: two control populations overlap. It is reported ALONGSIDE the percentage-point gate below
#: rather than replacing it: the pp gate is this project's own invented number, Z' is the
#: field's, and a reader is owed both. A prior-art sweep of this module's gating turned Z' up
#: as the published form of exactly the rule the pp gate states informally.
FLANK_MIN_Z_PRIME = 0.5

#: How many branches must leave a connected cluster of junction pixels for it to be a
#: junction. A pixel with three skeleton neighbours is a CANDIDATE, not a node: on
#: 260622_316_H_b2_back_CBS_01 the >=3-neighbour test fires on 11,638 pixels that form only
#: 2,201 connected clusters -- an over-mark factor of 5.29, because an axis-aligned crossing
#: lights its centre and all four arms. Of those clusters 132 (6.0%) have only two branches
#: leaving them: those are skeleton staircase artefacts, and cutting at them splits one
#: branch in two for no reason.
MIN_JUNCTION_DEGREE = 3

#: A branch must be at least this many pixels long to be classified. It is the inter-junction
#: distance threshold, and it is an absolute floor only; `min_segment_widths` below scales
#: with the crack, which is what actually matters.
MIN_SEGMENT_PX = 5

#: A branch shorter than this multiple of its own local crack WIDTH is, in principle, skeleton
#: noise inside a wide region rather than a piece of path: the centreline of a blob is not
#: localised to better than the blob, and a fixed pixel floor cannot express that, since the
#: same 5 px is generous on a 3 px crack and meaningless on a 40 px one.
#:
#: IT DEFAULTS OFF, because it is a deleter at every value worth having. Measured on
#: 260622_316_H_b2_front_CBS_02 (2,218 branches, 49,340 skeleton px): a 0.5x floor removes
#: 16.3% of the skeleton LENGTH, 1.0x removes 47.3% and 2.0x removes 66.2%. Half the
#: centreline is not noise, and a rule that deletes it is reading out the thin parts of the
#: crack and calling the result the crack. The honest handling of wide regions is the one the
#: flank measurement already uses -- report the decidable fraction and the half-width of the
#: part that cannot be decided -- not a quiet removal. Available as a diagnostic; what it
#: removes is always reported in `dropped`.
MIN_SEGMENT_WIDTHS = 0.0


# ----------------------------------------------------------------- boundary construction
def _aligned(arr, dy, dx):
    """Two aligned views of `arr` one step (dy, dx) apart, plus the window they cover.

    Written out rather than done with np.roll because roll wraps, and a wrapped comparison
    invents a boundary along every edge of the map.
    """
    H, W = arr.shape
    y0, y1 = max(0, dy), H + min(0, dy)
    x0, x1 = max(0, dx), W + min(0, dx)
    win = (slice(y0, y1), slice(x0, x1))
    back = (slice(y0 - dy, y1 - dy), slice(x0 - dx, x1 - dx))
    return win, back


def boundaries_from_grain_ids(grain_ids, *, ignore=(0,)):
    """Boundary pixels of a grain-ID map: a pixel whose 8-neighbourhood holds another ID.

    This is exact and has no threshold in it, which is the reason a grain-ID export is the
    preferred input over a rendered boundary image. IDs in `ignore` are treated as
    unindexed (EBSD zero-solution points) and never create a boundary on their own: a hole
    in the index is missing information, not a grain edge.
    """
    g = np.asarray(grain_ids)
    if g.ndim != 2:
        raise ValueError(f"grain_ids must be a 2-D label image, got shape {g.shape}")
    valid = ~np.isin(g, ignore)
    edge = np.zeros(g.shape, bool)
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        win, back = _aligned(g, dy, dx)
        diff = (g[win] != g[back]) & valid[win] & valid[back]
        edge[win] |= diff
        edge[back] |= diff
    return edge


def grain_geometry(grain_ids, nm_per_px=None, *, ignore=(0,)):
    """Grain count and equivalent diameter, so tau can be read against a grain."""
    g = np.asarray(grain_ids)
    ids, counts = np.unique(g[~np.isin(g, ignore)], return_counts=True)
    if ids.size == 0:
        return {"n_grains": 0}
    d_px = np.sqrt(4.0 * counts / np.pi)
    out = {"n_grains": int(ids.size),
           "median_grain_area_px": float(np.median(counts)),
           "median_grain_diameter_px": float(np.median(d_px)),
           "grain_diameter_iqr_px": [float(np.percentile(d_px, 25)),
                                     float(np.percentile(d_px, 75))],
           "unindexed_frac": float(np.isin(g, ignore).mean())}
    if nm_per_px:
        out["median_grain_diameter_um"] = float(np.median(d_px) * nm_per_px / 1000.0)
    return out


# ---------------------------------------------------------------------- the measurement
def _dist_to_boundary(boundary):
    """Euclidean distance from every pixel to the nearest boundary pixel."""
    if not boundary.any():
        return np.full(boundary.shape, np.inf, np.float64)
    return ndi.distance_transform_edt(~boundary)


def saturation(boundary, tau_px, *, within=None):
    """Share of the field already within tau of a boundary.

    This is the score a path gets for existing, so it is the floor every other number here
    is read against. `within` restricts it to a region of interest (e.g. the indexed area).
    """
    d = _dist_to_boundary(boundary)
    sel = np.ones(boundary.shape, bool) if within is None else np.asarray(within, bool)
    if not sel.any():
        return float("nan")
    return float((d[sel] <= tau_px).mean())


#: 8-connectivity for ndi.label. Note the CENTRE IS 1 here and must be 0 in _NEIGHBOURS: a
#: neighbour count convolved with a centre-1 kernel counts the pixel itself, which makes every
#: pixel on a plain line read as a 3-neighbour junction candidate.
#: A cluster is a node only if MIN_JUNCTION_DEGREE of its branches are at least this multiple
#: of the LOCAL CRACK WIDTH long. This is the width-scaled form of "how far apart must two
#: junctions be", and it is the second half of the over-marking cure.
#:
#: WHY IT IS NEEDED ON TOP OF THE WALL CLOSING. A junction is a place where three or more
#: DISTINGUISHABLE paths meet, and two paths are not distinguishable over a run shorter than
#: the channel is wide -- the medial axis of a channel cannot separate features finer than the
#: disc inscribed in it. Measured after the closing on 260622_316_H_b2_front_CBS_02, 96.7% of
#: the 332 surviving nodes still had a third incident branch shorter than the local width
#: (median 9 px against a 28.3 px channel), so almost all of them were places the image cannot
#: resolve as a three-way division at all.
#:
#: WHY 0.5. Chosen as the largest safe value with margin, on the same synthetic. Every k up to
#: and including 0.8 returns the true count of 4 at half-widths 2, 5, 15 and 40 with a smooth
#: or 1 px-rough wall; at k = 0.9 a real junction is lost on a SMOOTH wall at half-width 40.
#: 0.5 therefore sits a factor 1.6 inside the breaking point. It also fixes the one case the
#: closing alone misses, half-width 40 at 1 px roughness, where the closing leaves 6.
#:
#: WHAT IT COSTS. Nothing is deleted: no mask pixel, no skeleton pixel, no branch. A demoted
#: cluster's pixels go back to the skeleton and the branches either side rejoin, exactly as
#: for a two-branch cluster. On the real frames it takes 332 -> 68 and 575 -> 143 nodes, which
#: is one node per 15.3 and 14.5 um of centreline -- about one branch point per grain. 0
#: disables it. The demotion iterates, because rejoining branches lengthens them and can
#: rescue a neighbouring node; it converges in 3-5 passes on these frames.
MIN_BRANCH_WIDTHS = 0.5

#: Passes of the resolvability demotion before it is reported as not having converged.
MAX_RESOLVE_PASSES = 12

#: Radius of the morphological CLOSING applied to the crack wall before the skeleton is taken.
#:
#: WHY THE SKELETON NEEDS THIS. Clustering junction pixels into nodes fixed one fault and
#: exposed a second one underneath it. Inside a crack that is wide and whose wall is rough at
#: the pixel scale, the medial axis is not a centreline at all: it is a WEB of short members
#: running wall to wall, one between every pair of adjacent wall concavities, and every
#: intersection of that web is a genuine topological node of that skeleton. No amount of
#: clustering touches it, because the nodes are real -- the skeleton is what is wrong.
#:
#: WHY CLOSING AND NOT SOMETHING CLEVERER. Six families were measured against a synthetic tree
#: with four junctions by construction, grown to half-widths 2-40 px and roughened by
#: displacing its wall 1-2 px. At 1 px of roughness the baseline returns 4, 7, 7, 10 nodes for
#: half-widths 2, 5, 15, 40; a closing of radius 2 returns 4, 4, 4, 6 -- it recovers the exact
#: truth over most of the range. Hole filling barely moves it, spur pruning gives 4, 5, 4, 5
#: and collapsing nodes within an inscribed radius gives 4, 7, 7, 7. On the real frames the
#: node-collapse rule looks far stronger than it is (907 -> 410 on
#: 260622_316_H_b2_front_CBS_02) while recovering nothing on the synthetic: it suppresses
#: nodes by fiat rather than removing the cause, so it is NOT shipped.
#:
#: WHAT IT COSTS. A closing is extensive, so the result always CONTAINS the input and no crack
#: pixel can ever be removed. It bridges fragments up to r px apart, not 2r -- a dilation from
#: each side meets with no thickness in the middle of a 2r gap and does not survive the
#: erosion. On front_CBS_02 at r = 2 it adds 0.18% of crack area, merges no
#: connected components (226 -> 226) and takes the node count from 907 to 332; on
#: front_CBS_01 it adds 0.27%, merges 2 of 260 components and takes 1312 to 575. The skeleton
#: gets about 25% SHORTER, which is the point: that length was web, not centreline.
#:
#: r = 3 is slightly worse than r = 2 on both frames (406 and 603 nodes), because a larger
#: structuring element creates new concavities of its own in the complement. 0 disables it.
REGULARISE_PX = 2

_EIGHT = np.ones((3, 3), np.uint8)
_NEIGHBOURS = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], np.uint8)


def regularise(mask, r=REGULARISE_PX):
    """Close the crack wall at radius `r`. Returns (mask, report).

    PURELY ADDITIVE: a morphological closing is extensive, so the result contains the input and
    no crack pixel is ever removed. What it can do is bridge two mask fragments that are close
    together, which is reported as `components_merged` and never left silent.

    The reach is r, not 2r: a dilation by r from each side meets in the middle of a 2r gap
    with zero thickness and does not survive the erosion. Measured on a pair of bars, r = 1
    and r = 2 bridge gaps of 1-2 px and r = 3 bridges 3-4 px. At 42.15 nm/px that is 84 nm at
    the shipped radius, which is a ligament or a break in the mask rather than two cracks --
    but it is the caller's call and not this function's.
    """
    mask = np.asarray(mask, bool)
    if not r:
        return mask, {"regularise_px": 0, "area_added_pct": 0.0, "components_merged": 0}
    before = int(ndi.label(mask, structure=_EIGHT)[1])
    out = ndi.binary_closing(mask, morphology.disk(r), border_value=0) | mask
    after = int(ndi.label(out, structure=_EIGHT)[1])
    a0 = int(mask.sum())
    return out, {"regularise_px": int(r),
                 "area_added_pct": round(100.0 * (int(out.sum()) - a0) / a0, 3) if a0 else 0.0,
                 "components_before": before, "components_after": after,
                 "components_merged": before - after}


def _junction_candidates(skel):
    """Skeleton pixels with three or more skeleton neighbours in the 8-neighbourhood.

    THIS IS THE ONLY THRESHOLD IN THE JUNCTION TEST, and it is a count, not a tuned number:
    a pixel on a line has two neighbours, so three is the first value that can mean a branch.
    It is nonetheless a CANDIDATE set and not the junction list, because one node lights
    several pixels -- see `junction_clusters`.
    """
    nb = ndi.convolve(skel.astype(np.uint8), _NEIGHBOURS, mode="constant", cval=0)
    return skel & (nb >= 3), nb


def _incident_branches(jlab, blab, index):
    """For each cluster id in `index`, the distinct branch labels it touches."""
    out = {}
    objs = ndi.find_objects(jlab)
    H, W = jlab.shape
    for i in index:
        sl = objs[i - 1]
        if sl is None:
            out[i] = set()
            continue
        pad = (slice(max(0, sl[0].start - 1), min(H, sl[0].stop + 1)),
               slice(max(0, sl[1].start - 1), min(W, sl[1].stop + 1)))
        grown = ndi.binary_dilation(jlab[pad] == i, np.ones((3, 3), bool))
        touched = blab[pad][grown & (blab[pad] > 0)]
        out[i] = set(np.unique(touched).tolist())
    return out


def _skeleton_graph(mask, *, min_degree=MIN_JUNCTION_DEGREE, regularise_px=REGULARISE_PX,
                    min_branch_widths=MIN_BRANCH_WIDTHS):
    """Skeleton, its topological junctions, and the branches between them.

    WHY A JUNCTION PIXEL IS NOT A JUNCTION. The >=3-neighbour test is correct per pixel and
    wrong per node. A crossing of two axis-aligned arms lights its centre AND all four arms,
    five pixels for one node; a T lights four. On this project's own 316 frame the test fires
    on 11,638 pixels forming 2,201 connected clusters, so a per-pixel junction list
    over-counts by 5.29x and a figure drawing one marker per pixel draws five on top of each
    other. The nodes are therefore the CLUSTERS, and a cluster's degree is the number of
    distinct branches leaving it -- which is the textbook definition of a vertex degree and
    has no threshold in it at all.

    WHY SOME CLUSTERS ARE DROPPED. A cluster with two branches leaving it is not a node; it is
    a staircase artefact of the skeletonizer, and cutting there splits one branch in two. 132
    of the 2,201 clusters on that frame are of this kind. Their pixels are given back to the
    skeleton so the branches either side rejoin.

    Degree is read off the candidate cut (every cluster removed), because that is the LOCAL
    topology of the node; incidence is read off the final cut, because that is which branches
    a reader is actually holding. One consequence is worth stating: a branch that leaves a
    node and returns to it is one label, so the incidence count sees a self-loop once.
    """
    mask, reg = regularise(mask, regularise_px)
    skel = morphology.skeletonize(mask)
    empty = (np.array([], int), np.array([], int), np.array([], int))
    base = {"regularise": reg, "mask": mask,
            "skel": skel, "junction_labels": np.zeros(skel.shape, np.int32),
            "n_clusters": 0, "degree": np.zeros(1, int), "kept": np.zeros(1, bool),
            "branch_labels": np.zeros(skel.shape, np.int32), "n_branches": 0,
            "incidence": {}, "nodes": empty, "n_candidate_px": 0}
    if not skel.any():
        return base

    cand, _nb = _junction_candidates(skel)
    jlab, nj = ndi.label(cand, structure=_EIGHT)
    if nj == 0:
        lab, n = ndi.label(skel, structure=_EIGHT)
        base.update(branch_labels=lab, n_branches=int(n),
                    incidence={i: set() for i in range(1, int(n) + 1)})
        return base

    blab0, _n0 = ndi.label(skel & ~cand, structure=_EIGHT)
    inc0 = _incident_branches(jlab, blab0, range(1, nj + 1))
    degree = np.zeros(nj + 1, int)
    for i, s in inc0.items():
        degree[i] = len(s)

    # A representative pixel OF each cluster, so the local width is read on the skeleton.
    objs = ndi.find_objects(jlab)
    cy, cx = np.zeros(nj + 1, int), np.zeros(nj + 1, int)
    for i in range(1, nj + 1):
        sl = objs[i - 1]
        if sl is None:
            continue
        sy, sx = np.nonzero(jlab[sl] == i)
        j = int(np.argmin((sy - sy.mean()) ** 2 + (sx - sx.mean()) ** 2))
        cy[i], cx[i] = sy[j] + sl[0].start, sx[j] + sl[1].start
    hw = ndi.distance_transform_edt(mask)

    # Demote until stable. Rejoining the branches at a demoted cluster lengthens them, which
    # can rescue a neighbour, so one pass is not enough and the pass count is reported.
    kept = np.zeros(nj + 1, bool)
    kept[1:] = True
    passes = 0
    lab, n, inc = None, 0, {}
    for passes in range(1, MAX_RESOLVE_PASSES + 1):
        lab, n = ndi.label(skel & ~kept[jlab], structure=_EIGHT)
        ids = [i for i in range(1, nj + 1) if kept[i]]
        inc = _incident_branches(jlab, lab, ids)
        blen = np.bincount(lab.ravel(), minlength=n + 1)
        changed = False
        for i in ids:
            lens = sorted((int(blen[b]) for b in inc[i]), reverse=True)
            if len(lens) < min_degree:
                kept[i] = False
                changed = True
                continue
            if min_branch_widths and lens[min_degree - 1] < \
                    min_branch_widths * 2.0 * float(hw[cy[i], cx[i]]):
                kept[i] = False
                changed = True
        if not changed:
            break
    keep_ids = [i for i in range(1, nj + 1) if kept[i]]
    inc = _incident_branches(jlab, lab, keep_ids)
    per_branch = {i: set() for i in range(1, int(n) + 1)}
    for cid, branches in inc.items():
        for b in branches:
            per_branch.setdefault(b, set()).add(cid)

    ys = [int(cy[i]) for i in keep_ids]
    xs = [int(cx[i]) for i in keep_ids]

    base.update(resolve_passes=int(passes),
                resolve_converged=bool(passes < MAX_RESOLVE_PASSES),
                min_branch_widths=float(min_branch_widths or 0.0),
                junction_labels=jlab, n_clusters=int(nj), degree=degree, kept=kept,
                branch_labels=lab, n_branches=int(n), incidence=per_branch,
                nodes=(np.array(ys, int), np.array(xs, int),
                       np.array([degree[i] for i in keep_ids], int)),
                n_candidate_px=int(cand.sum()))
    return base


def _segment_pixels(mask, *, regularise_px=REGULARISE_PX):
    """Skeleton split at its topological junctions. Returns (skeleton, labelled branches, n)."""
    g = _skeleton_graph(mask, regularise_px=regularise_px)
    return g["skel"], g["branch_labels"], g["n_branches"]


def junctions(mask, *, regularise_px=REGULARISE_PX, min_branch_widths=MIN_BRANCH_WIDTHS):
    """Topological junctions and their degree: ONE ROW PER NODE, not per pixel.

    Junctions are used by this module ONLY to cut the skeleton into branches. They are not
    evidence of crack mode: a junction's degree says how many ways the crack divides, not
    whether the division happened at a grain corner. Whether degree carries any mode signal
    is a question with an answer, and `degree_separates` measures it rather than assuming.

    Four thresholds stand behind this list, all of them in `_skeleton_graph` and all with
    their measured justification on the constants: a candidate pixel has >= 3 skeleton
    neighbours; a cluster of candidates is a node when >= MIN_JUNCTION_DEGREE branches leave
    it; the wall is closed at REGULARISE_PX first so the medial axis of a wide crack is a
    centreline rather than a web; and MIN_BRANCH_WIDTHS of the local crack width is how long
    those branches have to be for the node to be resolvable at all. The first two are counts.
    The last two are the only tunable numbers here, and neither can delete crack.
    """
    return _skeleton_graph(mask, regularise_px=regularise_px,
                           min_branch_widths=min_branch_widths)["nodes"]


def _census_from_graph(g):
    """The over-marking census of a graph that has already been built.

    Taken from the graph rather than recomputed, so the census cannot describe a different
    rule from the one the caller actually ran -- and so a 4096 x 6144 frame is not
    skeletonized twice to report on itself.
    """
    nj, kept = g["n_clusters"], g["kept"]
    deg = g["degree"][1:]
    u, c = (np.unique(deg, return_counts=True) if deg.size else (np.array([]), np.array([])))
    return {"candidate_pixels": g["n_candidate_px"],
            "clusters": nj,
            "overmark_factor": round(g["n_candidate_px"] / nj, 2) if nj else None,
            "nodes": int(kept.sum()),
            "demoted": int(nj - kept.sum()),
            "resolve_passes": g.get("resolve_passes"),
            "resolve_converged": g.get("resolve_converged"),
            "min_branch_widths": g.get("min_branch_widths"),
            "regularise": g.get("regularise"),
            "degree_histogram": {int(a): int(b) for a, b in zip(u, c)},
            "branches": g["n_branches"]}


def junction_census(mask, *, regularise_px=REGULARISE_PX,
                    min_branch_widths=MIN_BRANCH_WIDTHS):
    """How much the per-pixel test over-marks on THIS image, so a reader can check it."""
    return _census_from_graph(_skeleton_graph(mask, regularise_px=regularise_px,
                                              min_branch_widths=min_branch_widths))


def _auc(score, positive):
    """Rank AUC of `score` against a boolean label. 0.5 is chance."""
    score = np.asarray(score, float)
    positive = np.asarray(positive, bool)
    npos, nneg = int(positive.sum()), int((~positive).sum())
    if npos == 0 or nneg == 0:
        return None
    from scipy import stats
    r = stats.rankdata(score)
    return float((r[positive].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


def degree_separates(cls, mask=None):
    """Can branch LENGTH or adjacent JUNCTION DEGREE predict the EBSD-derived class?

    Asked because it is the obvious thing to try and because, if it worked, the grain map
    would not be needed. Reported as an AUC against the class the grain map assigns, with
    0.5 meaning the feature carries nothing. This is a measurement of the shortcut, not an
    endorsement of it: a high AUC on one specimen is a property of that specimen's
    microstructure, not a transferable rule.
    """
    rows = [r for r in (cls.get("segments") or []) if r["mode"] in ("intergranular",
                                                                    "transgranular")]
    pos = np.array([r["mode"] == "intergranular" for r in rows], bool)
    npos, nneg = int(pos.sum()), int((~pos).sum())
    out = {"n_intergranular": npos, "n_transgranular": nneg}
    # An AUC on a handful of one class is not evidence, however high it reads. Measured on a
    # synthetic demo built with a dense boundary network against four smooth interior runs,
    # junction degree scored AUC 0.970 on 4 branches against 151 -- a property of how the
    # demo was drawn, not of cracks. The counts are therefore a gate, not a footnote.
    if min(npos, nneg) < MIN_PER_CLASS_FOR_AUC:
        out["note"] = (f"not computed: {npos} intergranular against {nneg} transgranular "
                       f"branches, and the smaller class needs at least "
                       f"{MIN_PER_CLASS_FOR_AUC}. An AUC here would describe the imbalance.")
        return out
    out["auc_branch_length"] = _auc([r["length_px"] for r in rows], pos)
    out["auc_branch_width"] = _auc([r["mean_width_px"] for r in rows], pos)
    if "max_adjacent_degree" in rows[0]:
        out["auc_junction_degree"] = _auc([r["max_adjacent_degree"] for r in rows], pos)
    return out


def _on_boundary_frac(coords, d, tau_px):
    if coords[0].size == 0:
        return float("nan")
    return float((d[coords] <= tau_px).mean())


def classify(mask, boundary, *, tau_px, theta_hi=THETA_HI, theta_lo=THETA_LO,
             nm_per_px=None, min_segment_px=MIN_SEGMENT_PX,
             min_segment_widths=MIN_SEGMENT_WIDTHS, evaluable=None):
    """Per-segment and per-image intergranular / transgranular shares.

    Returns a dict. `segments` carries one row per branch with its own boundary fraction, so
    the binned percentages can always be recomputed at another threshold from the shipped
    rows rather than from a rerun.

    TWO LENGTH FLOORS, and the second is the one that matters. `min_segment_px` is an absolute
    floor. `min_segment_widths` requires a branch to be at least that multiple of its OWN local
    crack width long: the centreline of a blob is not localised to better than the blob, so a
    branch shorter than the crack is wide is an artefact of skeletonizing a wide region, not a
    piece of path. A fixed pixel floor cannot express that, because the same 5 px is generous
    on a 3 px crack and meaningless on a 40 px one. What both floors remove is reported in
    `dropped`, never silently.
    """
    mask = np.asarray(mask, bool)
    boundary = np.asarray(boundary, bool)
    if mask.shape != boundary.shape:
        raise ValueError(f"mask {mask.shape} and grain map {boundary.shape} differ; the two "
                         "images must be co-registered and the same size")
    d = _dist_to_boundary(boundary)
    g = _skeleton_graph(mask)
    skel, lab, n = g["skel"], g["branch_labels"], g["n_branches"]
    if n == 0:
        return {"n_segments": 0, "note": "no skeleton to classify"}
    degree, inc = g["degree"], g["incidence"]

    dist_map = ndi.distance_transform_edt(mask)        # half-width at each centreline pixel
    rows = []
    drop_short, drop_narrow, drop_px = 0, 0, 0
    objs = ndi.find_objects(lab)
    for i, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        sub = lab[sl] == i
        npx = int(sub.sum())
        ys, xs = np.nonzero(sub)
        ys, xs = ys + sl[0].start, xs + sl[1].start
        coords = (ys, xs)
        hw = float(np.median(dist_map[coords]))        # median half-width along the branch
        if npx < min_segment_px:
            drop_short += 1
            drop_px += npx
            continue
        if min_segment_widths and npx < min_segment_widths * 2.0 * hw:
            drop_narrow += 1
            drop_px += npx
            continue
        f = _on_boundary_frac(coords, d, tau_px)
        cids = inc.get(i, ())
        rows.append({
            "segment": i,
            "length_px": npx,
            "max_adjacent_degree": int(max((degree[c] for c in cids), default=0)),
            "n_adjacent_junctions": len(cids),
            "mean_width_px": round(2.0 * hw, 2),
            "area_px": round(npx * 2.0 * hw, 1),
            "boundary_frac": round(f, 4),
            "median_dist_to_boundary_px": round(float(np.median(d[coords])), 2),
            "mode": ("intergranular" if f >= theta_hi
                     else "transgranular" if f <= theta_lo else "mixed"),
        })
    if not rows:
        return {"n_segments": 0,
                "note": f"no branch cleared the floors ({min_segment_px} px absolute, "
                        f"{min_segment_widths} x its own width)",
                "dropped": {"below_absolute_floor": drop_short,
                            "shorter_than_own_width": drop_narrow,
                            "skeleton_px_dropped": drop_px}}

    L = np.array([r["length_px"] for r in rows], float)
    A = np.array([r["area_px"] for r in rows], float)
    F = np.array([r["boundary_frac"] for r in rows], float)
    modes = [r["mode"] for r in rows]

    def share(weight, want):
        sel = np.array([m == want for m in modes])
        tot = weight.sum()
        return float(100.0 * weight[sel].sum() / tot) if tot else float("nan")

    out = {
        "n_segments": len(rows),
        "tau_px": tau_px,
        "theta_hi": theta_hi,
        "theta_lo": theta_lo,
        "by_length_pct": {m: round(share(L, m), 2)
                          for m in ("intergranular", "transgranular", "mixed")},
        "by_area_pct": {m: round(share(A, m), 2)
                        for m in ("intergranular", "transgranular", "mixed")},
        # the pooled fraction is NOT the mean of the per-segment fractions; both are given
        "pooled_boundary_frac": round(float((F * L).sum() / L.sum()), 4),
        "mean_segment_boundary_frac": round(float(F.mean()), 4),
        "boundary_frac_quartiles": [round(float(np.percentile(F, q)), 4) for q in (25, 50, 75)],
        "total_skeleton_px": int(L.sum()),
        "segments": rows,
    }
    if nm_per_px:
        out["total_skeleton_um"] = round(float(L.sum()) * nm_per_px / 1000.0, 3)
    out["bimodality"] = _bimodality(F, L)
    out["regularise"] = g["regularise"]
    out["junctions"] = _census_from_graph(g)
    out["dropped"] = {"below_absolute_floor": drop_short,
                      "shorter_than_own_width": drop_narrow,
                      "skeleton_px_dropped": drop_px,
                      "skeleton_px_dropped_frac": round(
                          drop_px / float(int(skel.sum()) or 1), 4)}
    if evaluable is not None:
        ev = np.asarray(evaluable, bool)
        out["skeleton_in_evaluable_frac"] = round(float(ev[np.nonzero(skel)].mean()), 4)
    W = np.array([r["mean_width_px"] for r in rows], float)
    out["confounds"] = _confounds(F, L, W)
    return out


def _spearman(x, y):
    """Rank correlation with TIED RANKS AVERAGED, via scipy.

    Not argsort(argsort(.)): that hands tied values arbitrary distinct ranks, and the
    boundary fraction is overwhelmingly tied -- on a boundary-following crack most branches
    score exactly 1.0. Measured on one 71-branch frame where 66 of 71 fractions were tied,
    the three candidate implementations returned -0.105 (correct), +0.014 and -0.260. A
    guard that cannot reproduce its own number is worse than no guard.
    """
    from scipy import stats
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.size < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    r = stats.spearmanr(x, y).statistic
    return None if not np.isfinite(r) else float(r)


def _confounds(F, L, W):
    """Is the boundary fraction ranking branches by their GEOMETRY or by their SIZE?

    This project's earlier, image-only attempt at the same question died here and nowhere
    else: its discriminator turned out to rank branches by painted stroke width at Spearman
    +0.891 rather than by path shape. The same two confounds are therefore measured on every
    run of this module and reported whether or not they are large.

    Branch LENGTH matters because junction-adjacent branches are short and, in a boundary
    network, sit on a boundary by construction; a strong negative rho means the
    intergranular share is being carried by stubs. Branch WIDTH matters because a wider
    crack's centreline is no better localised but its skeleton is longer and more branched.
    """
    return {"spearman_boundary_frac_vs_length": _spearman(F, L),
            "spearman_boundary_frac_vs_width": _spearman(F, W)}


def _bimodality(F, L):
    """Is the per-segment boundary fraction two populations, or one the threshold cut in half?

    Reported as the length-weighted share sitting in the middle third. A distribution with
    most of its mass at the ends supports a two-class description; one with most of its mass
    in the middle does not, whatever the binned percentages say.
    """
    mid = (F > 1.0 / 3.0) & (F < 2.0 / 3.0)
    tot = L.sum()
    return {"middle_third_length_share": round(float(L[mid].sum() / tot), 4) if tot else None,
            "reads_as_two_populations": bool(tot and (L[mid].sum() / tot) < 0.34)}


# --------------------------------------------------------------------- flank comparison
def flank_geometry(mask, *, regularise_px=REGULARISE_PX):
    """The part of the flank measurement that does not depend on the standoff.

    Split out because the standoff sweep is run on every frame and the skeleton plus the
    nearest-matrix-pixel field are by far the expensive part; recomputing them once per
    standoff made `flank_verdict` five times slower than it needs to be on a 4096 x 6144
    frame, which is the size these are.
    """
    # The SAME regularisation as _skeleton_graph, and for the same reason. It also has to be
    # the same here or `flank_mode` reads branch labels from one skeleton at coordinates taken
    # from another: the arrays are the same shape, so nothing would raise.
    mask, reg = regularise(mask, regularise_px)
    skel = morphology.skeletonize(mask)
    ys, xs = np.nonzero(skel)
    if ys.size == 0:
        return {"skel": skel, "ys": ys, "xs": xs, "wall_dist": ys.astype(float),
                "ey": ys.astype(float), "ex": ys.astype(float), "regularise": reg,
                "mask": mask}
    _d, (iy, ix) = ndi.distance_transform_edt(mask, return_indices=True)
    dy, dx = iy[ys, xs] - ys, ix[ys, xs] - xs            # step to the nearest wall, wall A
    n = np.hypot(dy, dx)
    n[n == 0] = 1.0
    return {"skel": skel, "ys": ys, "xs": xs, "wall_dist": n, "ey": dy / n, "ex": dx / n,
            "regularise": reg, "mask": mask}


def flank_ids(mask, grain_ids, *, standoff_px=2, ignore=(0,), geometry=None):
    """For every centreline pixel, the grain on each side of the crack.

    WHY THIS AND NOT BOUNDARY COINCIDENCE. Asking whether the centreline lies on a boundary
    assumes the boundary still exists where the crack is. It does not: a crack wide enough
    to measure has destroyed or opened whatever it ran along, so inside the crack there is
    nothing left to coincide with. On this project's own frames the crack is 11-20% of the
    field, far wider than a boundary, and a coincidence test there answers a question about
    the crack's edge rather than its path.

    Comparing FLANKS does not have that problem. If the material on the two sides of the
    crack belongs to one grain, the crack cut through that grain; if it belongs to two, the
    crack ran between them. The crack's own width is irrelevant, which is the property that
    makes this the measurement EBSD is normally used for.

    The two flanks are found geometrically rather than by tracing a normal: the nearest
    non-crack pixel to a centreline point lies on one wall, and reflecting that offset
    through the centreline point lands on the other. No tangent estimate is needed, so
    nothing depends on how noisy the skeleton is.
    """
    mask = np.asarray(mask, bool)
    g = np.asarray(grain_ids)
    if mask.shape != g.shape:
        raise ValueError(f"mask {mask.shape} and grain map {g.shape} differ; the two images "
                         "must be co-registered and the same size")
    geo = geometry if geometry is not None else flank_geometry(mask)
    if geo["ys"].size == 0:
        return {}
    mask = geo.get("mask", mask)
    ys, xs, n, ey, ex = geo["ys"], geo["xs"], geo["wall_dist"], geo["ey"], geo["ex"]
    off = n + standoff_px
    H, W = mask.shape
    pay = np.clip(np.rint(ys + ey * off).astype(int), 0, H - 1)
    pax = np.clip(np.rint(xs + ex * off).astype(int), 0, W - 1)
    pby = np.clip(np.rint(ys - ey * off).astype(int), 0, H - 1)
    pbx = np.clip(np.rint(xs - ex * off).astype(int), 0, W - 1)
    ga, gb = g[pay, pax], g[pby, pbx]
    ok = ~np.isin(ga, ignore) & ~np.isin(gb, ignore) & ~mask[pay, pax] & ~mask[pby, pbx]
    return {"ys": ys, "xs": xs, "flank_a": ga, "flank_b": gb, "decidable": ok,
            "same_grain": (ga == gb)}


def flank_mode(mask, grain_ids, *, standoff_px=2, ignore=(0,), nm_per_px=None,
               min_segment_px=MIN_SEGMENT_PX, geometry=None, graph=None,
               regularise_px=REGULARISE_PX):
    """Per-image intergranular / transgranular share by flank comparison, plus per branch."""
    geometry = (geometry if geometry is not None
                else flank_geometry(mask, regularise_px=regularise_px))
    mask = geometry.get("mask", mask)
    f = flank_ids(mask, grain_ids, standoff_px=standoff_px, ignore=ignore, geometry=geometry)
    if not f:
        return {"n_centreline_px": 0, "note": "no skeleton"}
    ok, same = f["decidable"], f["same_grain"]
    nd = int(ok.sum())
    out = {"n_centreline_px": int(ok.size),
           "n_decidable_px": nd,
           "decidable_frac": round(float(ok.mean()), 4),
           "standoff_px": standoff_px}
    if nd == 0:
        out["note"] = ("no centreline pixel had indexed material on both flanks; the grain "
                       "map does not cover the crack's surroundings")
        return out
    inter = int((~same[ok]).sum())
    out["intergranular_pct_by_centreline"] = round(100.0 * inter / nd, 2)
    out["transgranular_pct_by_centreline"] = round(100.0 * (nd - inter) / nd, 2)

    # per branch, so the figure can colour them and the split carries a distribution
    g = graph if graph is not None else _skeleton_graph(mask, regularise_px=0)
    lab, n = g["branch_labels"], g["n_branches"]
    rows = []
    if n:
        bid = lab[f["ys"], f["xs"]]
        for i in range(1, n + 1):
            sel = (bid == i) & ok
            if int(sel.sum()) < min_segment_px:
                continue
            frac = float((~same[sel]).mean())
            rows.append({"segment": i, "length_px": int(sel.sum()),
                         "boundary_frac": round(frac, 4),
                         "mode": ("intergranular" if frac >= THETA_HI
                                  else "transgranular" if frac <= THETA_LO else "mixed")})
    out["segments"] = rows
    out["n_segments"] = len(rows)
    if rows:
        L = np.array([r["length_px"] for r in rows], float)
        F = np.array([r["boundary_frac"] for r in rows], float)
        out["by_length_pct"] = {
            m: round(float(100.0 * L[[r["mode"] == m for r in rows]].sum() / L.sum()), 2)
            for m in ("intergranular", "transgranular", "mixed")}
        out["bimodality"] = _bimodality(F, L)
    if nm_per_px:
        out["decidable_centreline_um"] = round(nd * nm_per_px / 1000.0, 2)
    return out


def flank_verdict(mask, grain_ids, *, standoffs=(1, 2, 4, 8, 16), ignore=(0,),
                  nm_per_px=None, controls=None, regularise_px=REGULARISE_PX):
    """Run the flank comparison across standoffs and say whether the answer is a property
    of the crack or of the standoff.

    THE STANDOFF IS THE WHOLE DIFFICULTY and it is a geometric budget, not a tuning knob.
    The sample points must clear the crack wall, so the standoff has to exceed the local
    crack half-width; they must also stay inside the flanking grain, so it has to stay well
    under a grain radius. Where the crack is a large fraction of a grain there is no value
    that does both, and the share then tracks the standoff rather than the crack. Measured
    on one 316 frame: 11.8% intergranular at standoff 0 rising to 66.3% at 16 px, a 54-point
    swing, with the undecidable 87% of the centreline sitting at a median half-width of
    13.0 px against 3.6 px for the decidable part -- the wide part of the crack is exactly
    the part that cannot be decided.
    """
    rows = []
    geo = flank_geometry(mask, regularise_px=regularise_px)
    graph = _skeleton_graph(mask, regularise_px=regularise_px)
    for so in standoffs:
        r = flank_mode(mask, grain_ids, standoff_px=so, ignore=ignore, nm_per_px=nm_per_px,
                       geometry=geo, graph=graph)
        rows.append({"standoff_px": so,
                     "decidable_frac": r.get("decidable_frac"),
                     "intergranular_pct": r.get("intergranular_pct_by_centreline")})
    out = read_flank_sweep(rows)
    if controls is not None:
        cv = read_flank_controls(controls)
        out["controls_verdict"] = cv
        out["reasons"] = cv["reasons"] + out["reasons"]
        out["quotable"] = bool(out["quotable"] and cv["quotable"])
    return out


def _flank_share(g, geo, standoff_px, ignore, shift=(0, 0), flip=(False, False)):
    """Intergranular share by flank comparison, with the GRAIN MAP optionally moved.

    Moving the map rather than the crack is what makes the null affordable: the crack's
    skeleton and wall-distance field are the expensive part and they do not change, so a
    null draw costs two array lookups instead of a fresh skeletonization of a 4096 x 6144
    frame. It is the same comparison seen from the other side.
    """
    ys, xs, n, ey, ex = geo["ys"], geo["xs"], geo["wall_dist"], geo["ey"], geo["ex"]
    H, W = g.shape
    off = n + standoff_px
    pay = np.rint(ys + ey * off).astype(int)
    pax = np.rint(xs + ex * off).astype(int)
    pby = np.rint(ys - ey * off).astype(int)
    pbx = np.rint(xs - ex * off).astype(int)
    inside = ((pay >= 0) & (pay < H) & (pax >= 0) & (pax < W)
              & (pby >= 0) & (pby < H) & (pbx >= 0) & (pbx < W))
    pay, pax, pby, pbx = pay[inside], pax[inside], pby[inside], pbx[inside]
    qy = lambda v: (H - 1 - v) if flip[0] else v
    qx = lambda v: (W - 1 - v) if flip[1] else v
    # WRAP, DO NOT CLIP. np.clip pinned every out-of-range coordinate onto the frame
    # border, so on a typical shift 81-99% of the null's sample was read at one row or
    # column of the grain map instead of at a random place in it. Measured on
    # 260622_316_H_b2_front_CBS_01 over 12 shifts: the clipped null returned 14.32% with a
    # standard deviation of 9.78, a wrapped one 29.84% with 3.21 -- the clip corrupted both
    # the mean and the spread, and the spread is the denominator of the z this function
    # reports. A torus shift must wrap (Harms et al. 2001): a point leaving the right edge
    # re-enters at the left, which is what keeps every grain's size and shape intact.
    ay = (qy(pay) + shift[0]) % H; ax = (qx(pax) + shift[1]) % W
    by = (qy(pby) + shift[0]) % H; bx = (qx(pbx) + shift[1]) % W
    ga, gb = g[ay, ax], g[by, bx]
    ok = ~np.isin(ga, ignore) & ~np.isin(gb, ignore)
    nd = int(ok.sum())
    if nd == 0:
        return None, 0, int(inside.sum())
    return float(100.0 * (ga[ok] != gb[ok]).sum() / nd), nd, int(inside.sum())


def flank_controls(mask, grain_ids, *, standoff_px=2, ignore=(0,), seed=0,
                   n_null=NULL_DRAWS, regularise_px=REGULARISE_PX,
                   n_reps=FLANK_CONTROL_REPLICATES):
    """Positive, negative and null for the FLANK measurement itself.

    THIS IS NOT THE SAME CONTROL AS `controls`. That one validates boundary coincidence: a
    path walking the boundary skeleton scores ~1 on a distance-to-boundary test. It says
    nothing about whether comparing FLANKS works, because flank comparison can fail in a way
    coincidence cannot -- a crack wide relative to a grain has both of its sample points in
    neighbouring grains no matter where its centreline runs, so an interior crack reads as
    intergranular from width alone.

    WIDTH IS MATCHED, which is the point. The positive and negative paths are dilated to the
    real crack's own median width before being measured, so the three numbers differ only in
    where the path runs. An unmatched control would be measuring width, which is the confound
    that killed this project's earlier attempt at the same question.

    The positive and negative paths are put through the SAME wall regularisation as the real
    crack. They were not, briefly, and the controls then carried a treatment the measurement
    did not: a control processed differently from the data is not a control.

      positive  the partition's own boundary skeleton, walked. Must read near 100%.
      negative  the real crack's path placed where its mean distance to a boundary is
                greatest. Reads the rate at which a grain-blind path crosses boundaries.
      null      the grain map shifted and flipped at random under the same crack. The real
                share is reported as a z against this, not on its own.
    """
    mask = np.asarray(mask, bool)
    g = np.asarray(grain_ids)
    boundary = boundaries_from_grain_ids(g, ignore=ignore)
    geo = flank_geometry(mask, regularise_px=regularise_px)
    if geo["ys"].size == 0:
        return {"note": "no skeleton"}
    mask = geo.get("mask", mask)
    out_reg = geo.get("regularise")
    rng = np.random.default_rng(seed)
    hw = int(round(float(np.median(ndi.distance_transform_edt(mask)[geo["skel"]]))))
    hw = max(hw, 1)
    out = {"standoff_px": standoff_px, "matched_half_width_px": hw, "regularise": out_reg}

    real, nd, _ = _flank_share(g, geo, standoff_px, ignore)
    out["real_intergranular_pct"] = None if real is None else round(real, 2)
    out["real_decidable_px"] = nd

    # The BOUNDARY BUDGET, reported whether or not the control can be built. A crack cannot
    # have followed boundaries for a length the partition does not contain, and when the
    # positive control fails this is almost always why: measured on
    # 260622_316_H_b2_front_CBS_01 at a 7.45 um partition, the whole frame holds 50,096 px of
    # boundary skeleton against 61,156 px of crack centreline, and its largest connected
    # component is 7,049 px. An earlier version of this reported "no boundary skeleton to
    # walk", which was simply false and sent the reader looking for the wrong fault.
    bskel = morphology.skeletonize(boundary)
    ncrack = int(geo["ys"].size)
    out["crack_centreline_px"] = ncrack
    out["boundary_skeleton_px"] = int(bskel.sum())
    if bskel.any():
        _bl, _bn = ndi.label(bskel, structure=_EIGHT)
        out["largest_boundary_component_px"] = int(np.bincount(_bl.ravel())[1:].max())
    else:
        out["largest_boundary_component_px"] = 0
    out["boundary_to_crack_length_ratio"] = (round(out["boundary_skeleton_px"] / ncrack, 2)
                                             if ncrack else None)

    # REPLICATES. _boundary_walk starts from a random boundary pixel and _placements draws
    # random rigid placements, so both controls are already random variables; drawing one of
    # each and reporting it as a value throws the spread away.
    def _dilate_path(coords):
        syn = np.zeros(mask.shape, bool)
        syn[coords] = True
        return ndi.binary_dilation(syn, morphology.disk(hw))

    pos_reps, neg_reps = [], []
    for _ in range(max(1, n_reps)):
        w = _boundary_walk(boundary, ncrack, rng)
        if w is None:
            break
        v, _nd, _ = _flank_share(g, flank_geometry(_dilate_path(w),
                                                   regularise_px=regularise_px),
                                 standoff_px, ignore)
        if v is not None:
            pos_reps.append(v)
    d_rep = _dist_to_boundary(boundary)
    places_rep = _placements(np.nonzero(geo["skel"]), mask.shape, rng,
                             8 * max(1, n_reps))
    if places_rep:
        order = np.argsort([-float(np.mean(d_rep[c])) for c in places_rep])
        for j in order[:max(1, n_reps)]:
            v, _nd, _ = _flank_share(g, flank_geometry(_dilate_path(places_rep[int(j)]),
                                                       regularise_px=regularise_px),
                                     standoff_px, ignore)
            if v is not None:
                neg_reps.append(v)
    # BOTH GATES MUST READ THE SAME CONTROL. The percentage-point gap used to read a single
    # draw -- for the negative, the placement with the greatest MEAN DISTANCE to a boundary --
    # while Z' read the replicate mean. Worse, the replicates show that mean distance does not
    # rank placements by the flank share it is selecting for: on one 316 frame the two
    # furthest placements read 35.8 and 36.9% while less-far ones read 19.3 and 19.5%. So the
    # single draw was an arbitrary point in a wide distribution presented as "the" control.
    # The headline control is now the replicate MEAN, which is also what Z' is defined on, and
    # the furthest-placement value is kept beside it under its own name.
    out["positive_replicates"] = [round(v, 2) for v in pos_reps]
    out["negative_replicates"] = [round(v, 2) for v in neg_reps]
    for nm_, reps in (("positive", pos_reps), ("negative", neg_reps)):
        if reps:
            out[nm_ + "_min"] = round(float(np.min(reps)), 2)
            out[nm_ + "_max"] = round(float(np.max(reps)), 2)
    if len(pos_reps) > 1 and len(neg_reps) > 1:
        pm, nm_ = float(np.mean(pos_reps)), float(np.mean(neg_reps))
        ps, ns = float(np.std(pos_reps, ddof=1)), float(np.std(neg_reps, ddof=1))
        out["positive_sd"], out["negative_sd"] = round(ps, 2), round(ns, 2)
        gap = abs(pm - nm_)
        out["z_prime"] = (round(1.0 - 3.0 * (ps + ns) / gap, 3) if gap > 0 else None)

    walk = _boundary_walk(boundary, ncrack, rng)
    if walk is None:
        out["positive_control"] = None
        if out["boundary_skeleton_px"] == 0:
            out["positive_note"] = ("the grain map has no boundary at all: it is one region, "
                                    "or every region is in `ignore`.")
        else:
            out["positive_note"] = (
                f"a length-matched positive control cannot be built: the crack centreline is "
                f"{ncrack} px and the longest CONNECTED boundary path in the whole frame is "
                f"{out['largest_boundary_component_px']} px, against the "
                f"{max(8, ncrack // 4)} px the walk needs. The partition does not contain "
                f"enough connected boundary for this crack to have followed one.")
    else:
        syn = np.zeros(mask.shape, bool)
        syn[walk] = True
        syn = ndi.binary_dilation(syn, morphology.disk(hw))
        v, ndp, _ = _flank_share(g, flank_geometry(syn, regularise_px=regularise_px), standoff_px, ignore)
        out["positive_control_single"] = None if v is None else round(v, 2)
        out["positive_control"] = (round(float(np.mean(pos_reps)), 2) if pos_reps
                                   else out["positive_control_single"])
        out["positive_decidable_px"] = ndp

    d = _dist_to_boundary(boundary)
    places = _placements(np.nonzero(geo["skel"]), mask.shape, rng, 24)
    if places:
        far = places[int(np.argmax([float(np.mean(d[c])) for c in places]))]
        syn = np.zeros(mask.shape, bool)
        syn[far] = True
        syn = ndi.binary_dilation(syn, morphology.disk(hw))
        v, ndn, _ = _flank_share(g, flank_geometry(syn, regularise_px=regularise_px), standoff_px, ignore)
        out["negative_control_furthest"] = None if v is None else round(v, 2)
        out["negative_control"] = (round(float(np.mean(neg_reps)), 2) if neg_reps
                                   else out["negative_control_furthest"])
        out["negative_decidable_px"] = ndn

    H, W = mask.shape
    vals = []
    for _ in range(n_null):
        sh = (int(rng.integers(-H // 3, H // 3 + 1)), int(rng.integers(-W // 3, W // 3 + 1)))
        fl = (bool(rng.random() < 0.5), bool(rng.random() < 0.5))
        v, ndk, _ = _flank_share(g, geo, standoff_px, ignore, shift=sh, flip=fl)
        if v is not None and ndk >= 64:
            vals.append(v)
    a = np.array(vals, float)
    out["null_n"] = int(a.size)
    if a.size:
        out["null_mean"] = round(float(a.mean()), 2)
        out["null_sd"] = round(float(a.std(ddof=1)), 2) if a.size > 1 else None
        if a.size > 1 and a.std(ddof=1) > 0 and real is not None:
            out["z_vs_null"] = round(float((real - a.mean()) / a.std(ddof=1)), 2)
            out["null_p_one_sided"] = round(float((1 + (a >= real).sum()) / (1 + a.size)), 4)
    return out


#: The share may move this many percentage points across the standoff sweep before it is a
#: property of the standoff rather than of the crack.
FLANK_SPAN_CEILING_PP = 10.0
#: At least this share of the centreline must be decidable for the result to be the crack's.
FLANK_MIN_DECIDABLE = 0.50


#: A path built along the partition's own boundaries must score at least this, or the flank
#: comparison is not detecting boundary-following and no other number from it means anything.
FLANK_MIN_POSITIVE = 80.0

#: The positive control must exceed the negative by at least this many points. This is the
#: instrument's RESOLUTION: everything between the two is scale the measurement cannot
#: distinguish, so a share quoted on a 0-100 axis carries at least (100 - resolution) points
#: of systematic uncertainty. Measured on 260622_316_H_b2_front_CBS_01, a path placed as far
#: from the partition's boundaries as its own shape allows still reads 69.9-89.6%
#: intergranular, because the regions are smaller than the crack is wide and both flank
#: samples land in different regions wherever the centreline runs. A 29-point resolution
#: cannot support a share.
FLANK_MIN_RESOLUTION_PP = 50.0


def read_flank_controls(ctl):
    """Whether the flank instrument is working on THIS grain map, before any share is read.

    Separate from the standoff sweep because the two fail independently: a sweep can be
    beautifully stable at a value the instrument could not have resolved, and a resolved
    instrument can still have no standoff that works.
    """
    reasons, notes = [], []
    pos, neg = ctl.get("positive_control"), ctl.get("negative_control")
    real, z = ctl.get("real_intergranular_pct"), ctl.get("z_vs_null")
    if pos is None:
        reasons.append("the positive control could not be built. "
                       + (ctl.get("positive_note") or "No reason was recorded."))
    elif pos < FLANK_MIN_POSITIVE:
        reasons.append(f"the positive control reaches only {pos:.1f}%; a path built along the "
                       f"partition's own boundaries must read near 100% intergranular by flank "
                       f"comparison, so the instrument is not detecting boundary-following.")
    nmin, nmax = ctl.get("negative_min"), ctl.get("negative_max")
    if nmin is not None and nmax is not None and nmax - nmin > 10.0:
        notes.append(f"the negative control spans {nmin:.1f}-{nmax:.1f}% across replicates; "
                     f"the gap below is read against its mean, not against one draw")
    if pos is not None and neg is not None:
        res = pos - neg
        ctl_res = round(float(res), 1)
        notes.append(f"resolution {ctl_res} pp (positive {pos:.1f}, negative {neg:.1f})")
        if res < FLANK_MIN_RESOLUTION_PP:
            reasons.append(
                f"the instrument resolves only {res:.1f} percentage points: a path placed as "
                f"far from boundaries as its own shape allows still reads {neg:.1f}% "
                f"intergranular. That happens when the crack is wide relative to a grain, "
                f"because both flank samples then land in different grains wherever the "
                f"centreline runs -- the share is reading crack width, not crack path.")
    if real is not None and neg is not None and real < neg:
        reasons.append(
            f"the crack reads {real:.1f}%, BELOW the negative control's {neg:.1f}%. Whatever "
            f"that number is, it is not how much of this crack followed a boundary.")
    zp = ctl.get("z_prime")
    if zp is not None:
        notes.append(f"Z' = {zp:.3f} (Zhang/Chung/Oldenburg 1999; >= 0.5 is their 'excellent' "
                     f"line, <= 0 means the control populations overlap)")
        if zp < FLANK_MIN_Z_PRIME:
            reasons.append(
                f"Z' = {zp:.3f}, below {FLANK_MIN_Z_PRIME}. The positive and negative controls "
                f"do not separate by enough relative to their own spread, which is the test "
                f"the percentage-point gap cannot make: a 60 point gap between two controls "
                f"that each vary by 15 points is not a resolved instrument.")

    ratio = ctl.get("boundary_to_crack_length_ratio")
    if ratio is not None:
        notes.append(f"the partition holds {ratio:.2f}x as much boundary as there is crack "
                     f"centreline")
        if ratio < 1.0:
            reasons.append(
                f"the whole frame's boundary network is {ratio:.2f}x the length of this one "
                f"crack's centreline. A high intergranular share is not geometrically "
                f"available: there is less boundary in the field than there is crack.")
    if z is not None and z < 2.0:
        notes.append(f"z = {z} against the shifted-grain-map null; the crack is not placed on "
                     f"boundaries more than the same path over a randomly placed map would be.")
    return {"quotable": not reasons, "reasons": reasons, "notes": notes,
            "resolution_pp": (round(float(pos - neg), 1)
                              if pos is not None and neg is not None else None)}


def read_flank_sweep(rows):
    """The decision, separated from the sweep so it can be tested on known numbers.

    Kept apart because the synthetic tessellation the rest of the tests use CANNOT
    reproduce the real failure: a crack drawn along a grid line has different grains on
    either side at every standoff, so it reads 100% at all of them. The failure needs an
    irregular partition and a crack a large fraction of a grain wide, which is what the real
    316 frame is. Testing the rule on recorded numbers is honest; contriving a synthetic
    that happens to fail would not be.
    """
    vals = [r["intergranular_pct"] for r in rows if r["intergranular_pct"] is not None]
    dec = [r["decidable_frac"] for r in rows if r["decidable_frac"] is not None]
    out = {"sweep": rows,
           "intergranular_span_pp": round(max(vals) - min(vals), 1) if vals else None,
           "max_decidable_frac": round(max(dec), 4) if dec else None}
    reasons = []
    if out["intergranular_span_pp"] is not None and \
            out["intergranular_span_pp"] > FLANK_SPAN_CEILING_PP:
        reasons.append(
            f"the intergranular share moves {out['intergranular_span_pp']:.0f} percentage "
            f"points across the standoff sweep, so it is a property of the standoff and not "
            f"of the crack. The standoff must clear the crack wall and stay inside the "
            f"flanking grain; where the crack is a large fraction of a grain, no value does "
            f"both.")
    if out["max_decidable_frac"] is not None and \
            out["max_decidable_frac"] < FLANK_MIN_DECIDABLE:
        reasons.append(
            f"at best {100 * out['max_decidable_frac']:.0f}% of the centreline can be "
            f"decided at all; the rest has the crack, or unindexed material, on at least one "
            f"flank. A share computed over that minority is not a share of the crack.")
    out["quotable"] = not reasons
    out["reasons"] = reasons
    return out


# -------------------------------------------------------------------------- the controls
def _boundary_walk(boundary, n_px, rng):
    """A connected path along the boundary skeleton, n_px long. The positive control."""
    bskel = morphology.skeletonize(boundary)
    if not bskel.any():
        return None
    lab, n = ndi.label(bskel, structure=np.ones((3, 3), np.uint8))
    if n == 0:
        return None
    sizes = ndi.sum_labels(np.ones_like(lab), lab, index=np.arange(1, n + 1))
    big = int(np.argmax(sizes)) + 1
    comp = lab == big
    ys, xs = np.nonzero(comp)
    if ys.size == 0:
        return None
    start = rng.integers(ys.size)
    # breadth-first order from the start point gives a connected set of the required size
    seen = np.zeros(comp.shape, bool)
    frontier = [(int(ys[start]), int(xs[start]))]
    seen[frontier[0]] = True
    order = []
    while frontier and len(order) < n_px:
        y, x = frontier.pop(0)
        order.append((y, x))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = y + dy, x + dx
                if (0 <= ny < comp.shape[0] and 0 <= nx < comp.shape[1]
                        and comp[ny, nx] and not seen[ny, nx]):
                    seen[ny, nx] = True
                    frontier.append((ny, nx))
    if len(order) < max(8, n_px // 4):
        return None
    a = np.array(order)
    return (a[:, 0], a[:, 1])


def _placements(skel_coords, shape, rng, n):
    """Random rigid placements of the same path: lattice rotations, flips and shifts.

    Only 90-degree rotations and flips are used. An arbitrary rotation resamples a binary
    skeleton and changes its length and its staircase statistics, so it would not be the
    same path any more.
    """
    ys, xs = skel_coords
    H, W = shape
    out = []
    for _ in range(n):
        y, x = ys.copy(), xs.copy()
        if rng.random() < 0.5:
            y = -y
        if rng.random() < 0.5:
            x = -x
        if rng.random() < 0.5:
            y, x = x, y
        y = y - y.min()
        x = x - x.min()
        h, w = int(y.max()) + 1, int(x.max()) + 1
        if h > H or w > W:
            continue
        oy = int(rng.integers(0, H - h + 1))
        ox = int(rng.integers(0, W - w + 1))
        out.append((y + oy, x + ox))
    return out


def controls(mask, boundary, *, tau_px, seed=0, n_null=NULL_DRAWS, within=None):
    """Positive, negative and null, all matched to the real crack's own path.

    The real score alone is not readable: it has to be placed against what the same path
    scores somewhere else (null), what a path that genuinely follows boundaries scores
    (positive), and what one placed to avoid them scores (negative).
    """
    rng = np.random.default_rng(seed)
    d = _dist_to_boundary(boundary)
    skel = morphology.skeletonize(np.asarray(mask, bool))
    coords = np.nonzero(skel)
    if coords[0].size == 0:
        return {"note": "no skeleton"}
    real = _on_boundary_frac(coords, d, tau_px)
    n_px = int(coords[0].size)

    pos_c = _boundary_walk(np.asarray(boundary, bool), n_px, rng)
    positive = _on_boundary_frac(pos_c, d, tau_px) if pos_c is not None else float("nan")

    places = _placements(coords, skel.shape, rng, n_null)
    null = np.array([_on_boundary_frac(c, d, tau_px) for c in places], float)
    null = null[np.isfinite(null)]

    # the negative control is the same path placed where it is FURTHEST from boundaries
    negative = float("nan")
    if places:
        means = np.array([float(np.mean(d[c])) for c in places])
        negative = _on_boundary_frac(places[int(np.argmax(means))], d, tau_px)

    out = {
        "real_boundary_frac": round(float(real), 4),
        "positive_control": None if np.isnan(positive) else round(float(positive), 4),
        "negative_control": None if np.isnan(negative) else round(float(negative), 4),
        "null_n": int(null.size),
        "null_mean": round(float(null.mean()), 4) if null.size else None,
        "null_sd": round(float(null.std(ddof=1)), 4) if null.size > 1 else None,
        "saturation": round(saturation(boundary, tau_px, within=within), 4),
    }
    if null.size > 1 and null.std(ddof=1) > 0:
        out["z_vs_null"] = round(float((real - null.mean()) / null.std(ddof=1)), 2)
        out["null_p_one_sided"] = round(float((1 + (null >= real).sum()) / (1 + null.size)), 4)
    return out


# ------------------------------------------------------------------------------ verdict
def verdict(cls, ctl, geom, tau_px):
    """Whether this run may be quoted, and if not, which input to change.

    TWO VERDICTS, NOT ONE, because the two outputs fail for different reasons. The POOLED
    boundary fraction can be a sound measurement on a crack with three branches; the
    intergranular/transgranular SPLIT cannot, and a unimodal distribution makes the split a
    property of the thresholds while leaving the pooled figure untouched. Collapsing them
    would either refuse good measurements or wave through bad splits.

    A refusal that names the number is worth more than a percentage with nothing behind it,
    which is the standing rule for this question in `analysis/conclusions.REFUSALS`.
    """
    reasons, split_reasons, warnings = [], [], []

    sat = ctl.get("saturation")
    if sat is not None and not np.isnan(sat) and sat > SATURATION_CEILING:
        reasons.append(
            f"saturated: {100 * sat:.1f}% of the field is already within {tau_px} px of a "
            f"boundary, so any path scores about that before the crack is looked at. "
            f"Reduce tau, or the grain map is too finely partitioned for this pixel size.")

    pos = ctl.get("positive_control")
    if pos is None:
        reasons.append(
            "the positive control could not be built: this grain map has no boundary "
            "skeleton to walk, so there is nothing for a crack to follow and no number "
            "here means anything. Check that the grain map is a label image with more "
            "than one grain and that it is the right field.")
    elif pos < 0.80:
        reasons.append(
            f"the positive control only reaches {pos:.2f}; a path built along the boundary "
            f"skeleton should score near 1.0, so the instrument is not detecting "
            f"boundary-following and nothing else here can be trusted.")

    gd = geom.get("median_grain_diameter_px")
    if gd and tau_px > 0.2 * gd:
        reasons.append(
            f"tau is {tau_px / gd:.2f} grain diameters ({tau_px} px against a median grain of "
            f"{gd:.0f} px); at this ratio a boundary's catchment is a large fraction of the "
            f"grain and the classes stop being separable.")

    ev = cls.get("skeleton_in_evaluable_frac")
    if ev is not None and ev < 0.5:
        reasons.append(
            f"only {100 * ev:.1f}% of the crack centreline lies where a boundary could have "
            f"been detected at all. A boundary map derived from the same micrograph has to "
            f"blank the crack, or it reads the crack as its own strongest boundary -- and "
            f"blanking removes exactly the ground the measurement needs. A boundary fraction "
            f"of 0 here means the question was not asked, not that the crack avoided "
            f"boundaries. This is the contradiction that closes the image-only route; an "
            f"independent grain map (EBSD, or an etched image of the same field) does not "
            f"have it.")

    z = ctl.get("z_vs_null")
    if z is not None and z < 2.0:
        reasons.append(f"z = {z} against the geometry-matched null; the path is not placed on "
                       f"boundaries more than the same path placed at random would be. That "
                       f"is a finding about this crack, not a fault -- a transgranular crack "
                       f"SHOULD sit at its null -- but the intergranular share must not then "
                       f"be quoted as though the crack sought boundaries out.")

    n = cls.get("n_segments", 0)
    if n < MIN_SEGMENTS:
        split_reasons.append(
            f"only {n} measurable branches; the percentages are coarse and there is no "
            f"distribution behind them. The pooled boundary fraction is unaffected.")

    bim = cls.get("bimodality") or {}
    if bim.get("reads_as_two_populations") is False:
        split_reasons.append(
            f"the per-segment boundary fraction is one population, not two "
            f"({100 * bim['middle_third_length_share']:.0f}% of length sits in the middle "
            f"third), so the binned percentages are a property of the thresholds rather than "
            f"of the crack. Quote the distribution, not the split.")

    conf = cls.get("confounds") or {}
    rl = conf.get("spearman_boundary_frac_vs_length")
    rw = conf.get("spearman_boundary_frac_vs_width")
    if rl is not None and rl < -0.5:
        split_reasons.append(
            f"the boundary fraction ranks branches by LENGTH, Spearman {rl:+.2f}: the "
            f"intergranular share is being carried by short junction-adjacent stubs, which "
            f"lie on a boundary by construction, not by path geometry.")
    if rw is not None and abs(rw) > 0.5:
        split_reasons.append(
            f"the boundary fraction ranks branches by WIDTH, Spearman {rw:+.2f}. This is the "
            f"confound that killed this project's image-only attempt at the same question "
            f"(it reached +0.891 there); the split is reading crack width, not crack path.")
    for nm, rho in (("length", rl), ("width", rw)):
        if rho is not None and 0.3 < abs(rho) <= 0.5:
            warnings.append(f"boundary fraction correlates with branch {nm} at Spearman "
                            f"{rho:+.2f}; not disqualifying, but check it is not the result.")

    # The transgranular floor is not zero and a reader will otherwise think it should be.
    pooled = cls.get("pooled_boundary_frac")
    if pooled is not None and sat is not None and not np.isnan(sat) and pooled <= sat * 1.2:
        warnings.append(
            f"the pooled boundary fraction ({pooled}) is at or below the saturation floor "
            f"({round(float(sat), 4)}), which is what a path scores for merely crossing "
            f"boundaries as it goes. This reads as transgranular.")

    return {"pooled_quotable": not reasons,
            "split_quotable": not reasons and not split_reasons,
            "reasons": reasons,
            "split_reasons": split_reasons,
            "warnings": warnings}


# ---------------------------------------------------------------------------- top level
def measure(mask, grain_ids=None, boundary=None, *, tau_px, nm_per_px=None, seed=0,
            n_null=NULL_DRAWS, theta_hi=THETA_HI, theta_lo=THETA_LO, ignore=(0,),
            tau_sweep=(1, 2, 3, 5, 8, 12), evaluable=None):
    """The whole measurement for one image. Give grain_ids OR an explicit boundary mask."""
    if grain_ids is None and boundary is None:
        raise ValueError(
            "this measurement needs a co-registered grain reference. Pass grain_ids (an "
            "EBSD grain-ID map, preferred) or boundary (a boundary mask). There is no "
            "mask-only mode: see the module docstring and analysis/conclusions.REFUSALS.")
    if boundary is None:
        boundary = boundaries_from_grain_ids(grain_ids, ignore=ignore)
    geom = grain_geometry(grain_ids, nm_per_px, ignore=ignore) if grain_ids is not None else {}
    within = None
    if grain_ids is not None:
        within = ~np.isin(np.asarray(grain_ids), ignore)

    cls = classify(mask, boundary, tau_px=tau_px, theta_hi=theta_hi, theta_lo=theta_lo,
                   nm_per_px=nm_per_px, evaluable=evaluable)
    ctl = controls(mask, boundary, tau_px=tau_px, seed=seed, n_null=n_null, within=within)
    sweep = []
    for t in tau_sweep:
        c = classify(mask, boundary, tau_px=t, theta_hi=theta_hi, theta_lo=theta_lo)
        sweep.append({"tau_px": t,
                      "saturation": round(saturation(boundary, t, within=within), 4),
                      "intergranular_pct_by_length": (c.get("by_length_pct") or {}).get(
                          "intergranular"),
                      "pooled_boundary_frac": c.get("pooled_boundary_frac")})
    out = {"grain_geometry": geom, "controls": ctl, "tau_sweep": sweep,
           "classification": cls, "nm_per_px": nm_per_px,
           "shortcut_test": degree_separates(cls)}
    out["verdict"] = verdict(cls, ctl, geom, tau_px)
    return out


def _load_grey(path):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    return np.array(Image.open(path))


def measure_path(mask_path, grain_path, *, tau_px, nm_per_px=None, seed=0, **kw):
    """Load a crack mask (crack = BLACK, the convention this app emits) and a grain map."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    m = np.array(Image.open(mask_path).convert("L")) < 128
    g = _load_grey(grain_path)
    if g.ndim == 3:
        # an RGB grain/IPF export: collapse distinct colours to integer ids
        flat = g.reshape(-1, g.shape[2])
        _, ids = np.unique(flat, axis=0, return_inverse=True)
        g = ids.reshape(g.shape[:2]) + 1
    out = measure(m, grain_ids=g, tau_px=tau_px, nm_per_px=nm_per_px, seed=seed, **kw)
    out["inputs"] = {"mask": os.path.abspath(mask_path),
                     "grain_map": os.path.abspath(grain_path)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Intergranular vs transgranular share for one image, from a crack mask "
                    "and a co-registered EBSD grain map.")
    ap.add_argument("--mask", required=True, help="crack mask PNG/TIF, crack = black")
    ap.add_argument("--grains", required=True,
                    help="co-registered grain-ID map (preferred) or boundary/IPF image")
    ap.add_argument("--tau-px", type=float, required=True,
                    help="distance from a boundary still counted as on it, in pixels: the "
                         "registration error plus the rendered boundary half-width. Declared, "
                         "not tuned; it is swept on every run.")
    ap.add_argument("--nm-per-px", type=float, default=None)
    ap.add_argument("--theta-hi", type=float, default=THETA_HI)
    ap.add_argument("--theta-lo", type=float, default=THETA_LO)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--null-draws", type=int, default=NULL_DRAWS)
    ap.add_argument("--json", default=None, help="write the full record here")
    ap.add_argument("--segments", action="store_true",
                    help="include the per-segment rows in stdout (always in --json)")
    a = ap.parse_args(argv)

    r = measure_path(a.mask, a.grains, tau_px=a.tau_px, nm_per_px=a.nm_per_px, seed=a.seed,
                     n_null=a.null_draws, theta_hi=a.theta_hi, theta_lo=a.theta_lo)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=1)
        print("wrote", a.json)

    c, ct, v = r["classification"], r["controls"], r["verdict"]
    g = r["grain_geometry"]
    print(f"\ngrains        {g.get('n_grains', 0)}, median diameter "
          f"{g.get('median_grain_diameter_px', float('nan')):.0f} px"
          + (f" ({g['median_grain_diameter_um']:.2f} um)" if "median_grain_diameter_um" in g
             else ""))
    print(f"branches      {c.get('n_segments', 0)}  "
          f"({c.get('total_skeleton_px', 0)} skeleton px)")
    print(f"tau           {a.tau_px} px   saturation {100 * ct.get('saturation', float('nan')):.1f}%"
          f"  (the floor: what any path scores)")
    print(f"controls      positive {ct.get('positive_control')}   "
          f"negative {ct.get('negative_control')}   "
          f"null {ct.get('null_mean')} +/- {ct.get('null_sd')} (n={ct.get('null_n')})")
    print(f"real          {ct.get('real_boundary_frac')}   z = {ct.get('z_vs_null')}   "
          f"p = {ct.get('null_p_one_sided')}")
    if c.get("by_length_pct"):
        bl, ba = c["by_length_pct"], c["by_area_pct"]
        print(f"\n{'':14s}{'by length':>12s}{'by area':>12s}")
        for m in ("intergranular", "transgranular", "mixed"):
            print(f"  {m:12s}{bl[m]:11.2f}%{ba[m]:11.2f}%")
    print(f"\nVERDICT       pooled fraction: "
          f"{'quotable' if v['pooled_quotable'] else 'NOT quotable'}   "
          f"inter/trans split: {'quotable' if v['split_quotable'] else 'NOT quotable'}")
    for why in v["reasons"]:
        print(f"  - {why}")
    for why in v["split_reasons"]:
        print(f"  - (split only) {why}")
    for why in v["warnings"]:
        print(f"  ! {why}")
    if a.segments:
        print("\nsegments:")
        for row in c.get("segments", []):
            print(f"  {row['segment']:4d} len {row['length_px']:5d} px  "
                  f"w {row['mean_width_px']:6.2f}  f {row['boundary_frac']:.3f}  {row['mode']}")
    return 0 if v["pooled_quotable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
