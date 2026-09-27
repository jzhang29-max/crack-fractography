#!/usr/bin/env python3
"""The longest single crack in a region, as a geodesic on the skeleton graph.

WHY THIS FILE EXISTS. `SkeletonLength_px` is summed over the skeleton's adjacency EDGES,
not along one ordered path (see extended_features.skeleton_path_length, which says so in
its own docstring). For an unbranched crack that is the crack's length. For a branching
network it is the TOTAL centreline length of the whole network -- every arm, every spur,
every loop, added together. The frame metric `mcl_um` used to be max(SkeletonLength_px)
over regions and was labelled "Longest crack (MCL)", which is the one reading it cannot
have: measured over the 143 scaled frames, the region that set it had a median of 594
branch points, its skeleton length was a median 5.2x its own ellipse major axis, and the
result exceeded the short side of the field on 89 of 143 frames -- 4893.9 um of "longest
crack" inside a 107.9 um field in the worst case. A network total cannot be compared with
the Varestraint/hot-cracking MCL the label invites, which is one crack, tip to tip.

WHAT IS COMPUTED. The longest TIP-TO-TIP GEODESIC: over all pairs of skeleton tips, the
shortest path between them, maximised. Tip = degree 1 in the pruned edge graph below.

  - For an unbranched skeleton this equals SkeletonLength_px exactly, not approximately:
    such a skeleton is a single path, its two tips are the path's ends, and the only route
    between them is the whole path. So the two columns agree exactly on the simple case and
    separate only where the topology is the reason they should.
  - For an acyclic skeleton (a tree) it is the tree diameter, i.e. the longest simple path
    in the skeleton -- the standard graph-theoretic answer.
  - For a skeleton with cycles it is the longest tip-to-tip SHORTEST route. Where a crack
    bifurcates and rejoins, the measure takes the shorter arm, which is what "the length of
    the crack from this tip to that tip" means. It is therefore a LOWER bound on the
    longest simple path (finding which is NP-hard), and it can also fall below the geodesic
    diameter taken over every skeleton pixel rather than over tips, because on a cyclic
    component the mutually-farthest pair of points can lie mid-arc. Both gaps are measured
    in tests/test_geodesic.py rather than asserted away.
  - A component with fewer than two tips -- an isolated closed loop, a single pixel -- has
    no tip-to-tip path at all. It returns None with a reason, never 0, because 0 would read
    as "a crack of no length" and land in a max() as though it had been measured.

THE MEASURE IS NOT NEW AND IS NOT CLAIMED. "Largest shortest path" per skeleton ships in
Fiji AnalyzeSkeleton (contributed by Huub Hovens; Polder, Hovens & Zweers, ImageJ User and
Developer Conference 2010), the same plugin this repo already credits for endpoint/slab/
junction classification. In morphology it is the geodesic diameter (Lantuejoul & Beucher,
J. Microscopy 121:39-49, 1981). What this file fixes is a wrong label on a column of this
app's own, not a gap in the literature. It exists here rather than as a call into that
plugin only because the length it has to stay consistent with is computed here.

THE GRAPH IS THE ONE THE LENGTH IS SUMMED OVER, not a second definition of adjacency. Same
orthogonal edges (weight 1), same sqrt(2) diagonals, and the same pruning rule: a diagonal
whose two pixels share an orthogonal neighbour in the skeleton is dropped, because it cuts
a staircase corner or a 4-connected junction and runs parallel to a route already counted.
Getting that wrong in either direction would be invisible and wrong -- a graph with the
unpruned diagonals lets a geodesic take sqrt(2) shortcuts no length was ever charged for,
and could return a "longest crack" longer than the network containing it. So the total
weight of the graph built here is compared against the shared implementation's
skeleton_path_length() on every region, and a region whose two disagree emits no geodesic
at all (`graph_length_mismatch`) rather than a plausible number from the wrong graph.

DEGREE HERE IS PRUNED DEGREE, which is not the 8-neighbour count that skeleton_stats uses
for BranchPointCount and endpoints, and the difference is not small: on the largest region
in the corpus, 3175 pixels have pruned degree >= 3 against 8248 with >= 3 eight-neighbours,
and 1076 have pruned degree 1 against 1051 eight-neighbour endpoints. The 8-neighbour count
sees a staircase corner as a fork -- three of its neighbours, two of the three edges
pruned. The pruned graph is the one the length lives on, so it is the one a path length on
that skeleton has to be computed on; BranchPointCount is left exactly as it was.
"""
import math

import numpy as np
from scipy import sparse
from scipy.sparse import csgraph

_SQRT2 = math.sqrt(2.0)

#: Sources per Dijkstra call. Caps peak memory at CHUNK x n_anchors floats regardless of
#: how many tips a region has, which matters: the largest region here has 1076 tips over
#: 4251 reduced nodes, and an all-at-once dense result grows as the product.
_CHUNK = 256

#: Tolerance on "my graph sums to the same length the shared implementation reports".
#: Both sum the same float64 terms in a different order; observed disagreement on real
#: regions is ~1e-11 on lengths of ~7e4, i.e. pure summation order. Anything above this is
#: a different edge set, not rounding.
_LEN_TOL = 1e-6


def skeleton_edges(skel):
    """(rows, cols, weights) of the pruned skeleton adjacency graph, pixels as flat indices.

    Mirrors extended_features.skeleton_path_length term for term: the sum of `weights` is
    that function's return value. Kept as one vectorised pass so it cannot drift into a
    per-pixel neighbour loop that handles the pruning "almost" the same way.
    """
    S = np.asarray(skel, dtype=bool)
    H, W = S.shape
    idx = np.arange(S.size, dtype=np.int64).reshape(H, W)
    parts = []
    m = S[:, :-1] & S[:, 1:]
    parts.append((idx[:, :-1][m], idx[:, 1:][m], 1.0))
    m = S[:-1, :] & S[1:, :]
    parts.append((idx[:-1, :][m], idx[1:, :][m], 1.0))
    # Both diagonals of every 2x2 window, kept only when neither of the window's other two
    # corners is skeleton -- i.e. only when the diagonal is the sole route between its ends.
    m = S[:-1, :-1] & S[1:, 1:] & ~(S[:-1, 1:] | S[1:, :-1])
    parts.append((idx[:-1, :-1][m], idx[1:, 1:][m], _SQRT2))
    m = S[:-1, 1:] & S[1:, :-1] & ~(S[:-1, :-1] | S[1:, 1:])
    parts.append((idx[:-1, 1:][m], idx[1:, :-1][m], _SQRT2))
    r = np.concatenate([a for a, _, _ in parts])
    c = np.concatenate([b for _, b, _ in parts])
    w = np.concatenate([np.full(len(a), q, float) for a, _, q in parts])
    return r, c, w


def _min_dedup(n, er, ec, ew):
    """CSR from an edge list, keeping the MINIMUM over parallel edges, never the sum.

    Two anchors can be joined by a direct edge AND by a chain, or by two different chains.
    coo_matrix -> csr SUMS duplicate entries by default, which would lengthen the route
    between them and silently inflate every geodesic that passes through.
    """
    key = er.astype(np.int64) * n + ec
    order = np.lexsort((ew, key))
    key, er, ec, ew = key[order], er[order], ec[order], ew[order]
    first = np.ones(key.size, bool)
    first[1:] = key[1:] != key[:-1]
    return sparse.coo_matrix((ew[first], (er[first], ec[first])), shape=(n, n)).tocsr()


def _reduce(n, r, c, w, deg):
    """Collapse runs of degree-2 nodes into single weighted edges between ANCHORS.

    Indices are skeleton-local (0..n-1). Anchors are the nodes of pruned degree != 2: tips
    (1), junctions (>=3), isolated pixels (0). Every path between two anchors runs through
    whole chains, so the reduction is exact for anchor-to-anchor distance while shrinking
    the largest region here from 57560 nodes to 4251.

    Returns (anchor_ids, csr over anchor positions, position lookup).
    """
    is_anchor = deg != 2
    anchor = np.flatnonzero(is_anchor)
    if anchor.size == 0:
        return anchor, None, None
    pos = np.full(n, -1, np.int64)
    pos[anchor] = np.arange(anchor.size)

    ar, ac = is_anchor[r], is_anchor[c]
    both = ar & ac
    er = [pos[r[both]]]
    ec = [pos[c[both]]]
    ew = [w[both]]

    chain = np.flatnonzero(deg == 2)
    if chain.size:
        cpos = np.full(n, -1, np.int64)
        cpos[chain] = np.arange(chain.size)
        inner = (~ar) & (~ac)
        g = sparse.coo_matrix((np.ones(int(inner.sum())), (cpos[r[inner]], cpos[c[inner]])),
                              shape=(chain.size, chain.size)).tocsr()
        ncomp, lab = csgraph.connected_components(g, directed=False)
        tot = np.zeros(ncomp)
        np.add.at(tot, lab[cpos[r[inner]]], w[inner])
        # Boundary edges: exactly one end an anchor. A chain has exactly two of them --
        # each of its interior nodes spends both its edges inside the run -- unless it is a
        # closed loop touching no anchor, which is dropped because it carries no tip.
        bnd = ar ^ ac
        b_anchor = np.where(ar[bnd], r[bnd], c[bnd])
        b_lab = lab[cpos[np.where(ar[bnd], c[bnd], r[bnd])]]
        np.add.at(tot, b_lab, w[bnd])
        order = np.argsort(b_lab, kind="stable")
        b_lab, b_anchor = b_lab[order], b_anchor[order]
        lo = np.searchsorted(b_lab, np.arange(ncomp), "left")
        hi = np.searchsorted(b_lab, np.arange(ncomp), "right")
        keep = (hi - lo) == 2
        u = b_anchor[lo[keep]]
        v = b_anchor[lo[keep] + 1]
        ok = u != v                      # a chain that leaves an anchor and returns to it
        er.append(pos[u[ok]]); ec.append(pos[v[ok]]); ew.append(tot[keep][ok])

    er = np.concatenate(er); ec = np.concatenate(ec); ew = np.concatenate(ew)
    if ew.size == 0:
        return anchor, None, pos
    return anchor, _min_dedup(anchor.size, er, ec, ew), pos


def _local_graph(skel):
    """Skeleton-local (n, r, c, w, deg) plus the flat pixel ids, or None if too small."""
    S = np.asarray(skel, dtype=bool)
    r, c, w = skeleton_edges(S)
    px = np.flatnonzero(S.ravel())
    loc = np.full(S.size, -1, np.int64)
    loc[px] = np.arange(px.size)
    r, c = loc[r], loc[c]
    deg = np.bincount(np.concatenate([r, c]), minlength=px.size)
    return px.size, r, c, w, deg


def longest_tip_geodesic(skel, network_length=None):
    """Longest shortest-path between two skeleton tips, in pixel-length units.

    Returns (value_or_None, info). `network_length`, when given, is the shared
    implementation's skeleton_path_length for this same skeleton; the graph built here must
    sum to it or no value is emitted.
    """
    S = np.asarray(skel, dtype=bool)
    info = {"n_tips": 0, "n_junctions": 0, "n_cycles": None, "reason": None}
    if S.ndim != 2 or S.size == 0 or S.sum() < 2:
        info["reason"] = "fewer than two skeleton pixels"
        return None, info

    n, r, c, w, deg = _local_graph(S)
    info["graph_length_px"] = round(float(w.sum()), 4)
    if network_length is not None and abs(w.sum() - float(network_length)) > _LEN_TOL:
        info["reason"] = "graph_length_mismatch"
        return None, info
    if w.size == 0:
        info["reason"] = "no skeleton edges"
        return None, info

    info["n_tips"] = int((deg == 1).sum())
    info["n_junctions"] = int((deg >= 3).sum())
    ncomp = csgraph.connected_components(
        sparse.coo_matrix((np.ones(w.size), (r, c)), shape=(n, n)).tocsr(), directed=False)[0]
    # E - V + C, the count of independent cycles. 0 means a tree, where this measure is the
    # exact longest simple path; > 0 means it is a lower bound on it.
    info["n_cycles"] = int(w.size - n + ncomp)
    info["is_tree"] = info["n_cycles"] == 0
    if info["n_tips"] < 2:
        info["reason"] = ("closed loop: no skeleton tips" if info["n_tips"] == 0
                          else "only one skeleton tip")
        return None, info

    anchor, g, _ = _reduce(n, r, c, w, deg)
    if g is None:
        info["reason"] = "no reducible anchor graph"
        return None, info
    tips = np.flatnonzero(deg[anchor] == 1)
    best = 0.0
    for i in range(0, tips.size, _CHUNK):
        d = csgraph.dijkstra(g, directed=False, indices=tips[i:i + _CHUNK])[:, tips]
        finite = np.isfinite(d)
        if finite.any():
            best = max(best, float(d[finite].max()))
    return best, info


def all_pixel_geodesic_diameter(skel):
    """Exact geodesic diameter over EVERY skeleton pixel, not just tips. Reference only.

    This is the quantity the tip-to-tip measure can fall below on a cyclic component, and
    it is here so the gap can be measured on real regions instead of argued about. O(V.E
    log V) -- usable on small and medium regions, not on the 57560-pixel ones.
    """
    n, r, c, w, _ = _local_graph(np.asarray(skel, bool))
    if w.size == 0:
        return None
    g = _min_dedup(n, r, c, w)
    best = 0.0
    for i in range(0, n, _CHUNK):
        d = csgraph.dijkstra(g, directed=False, indices=np.arange(i, min(i + _CHUNK, n)))
        finite = np.isfinite(d)
        if finite.any():
            best = max(best, float(d[finite].max()))
    return best
