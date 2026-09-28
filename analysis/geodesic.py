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
for BranchPointCount and endpoints, and the difference is not small. On the largest region
in the corpus (Cast_24hr_SE_Side_006, a 929,304 px skeleton) 342,813 pixels have pruned
degree >= 3 against 617,051 with >= 3 eight-neighbours, and 44,263 have pruned degree 1
against 39,849 eight-neighbour endpoints. It moves both ways, for one reason: the
8-neighbour count sees a staircase corner as a fork -- three neighbours, two of the three
edges pruned -- so it invents junctions, and it hides the tips those same corners are. The
pruned graph is the one the length lives on, so it is the one a path length on that
skeleton has to be computed on; BranchPointCount is left exactly as it was.

WHERE THE THIRD METHOD IS NOT EXACT, AND BY HOW MUCH -- MEASURED, NOT ARGUED. A region
that is both cyclic and too large to sweep from every tip gets an iterated sweep plus an
evenly spaced sample, which is a lower bound and is labelled one. Against the exact
all-pairs answer on every cyclic region where exact is computable -- 168 of them, 4 to
1076 tips, 1 to 1095 independent cycles -- it agreed on 168 of 168, exactly, with a median
of 3 sweeps. Forced on synthetic cyclic shapes at an eighth of the shipped source budget
it is still exact on all 35; starved to 4 sources one shape falls 7.8% short, which is how
the test knows the spread sample is doing work rather than decorating a result the sweep
had already found. That is evidence, not a guarantee: the two regions that actually need
the fallback have 159,751 and 101,300 cycles, far outside the range any of this was
checked over, and their values carry geodesic_method = "sampled_sources_lower_bound" so a
reader can see which number they are holding. On the corpus as re-measured it is 4 regions
of 61,154: 47,747 take the exact tree sweep, 13,193 the exact all-pairs, and 210 have no
tip-to-tip path at all (all tiny -- the largest is 282 px of centreline, and not one of the
210 has a network longer than its own frame's MCL, so none of them could have set it). All
4 approximated regions are on UNSCALED frames, so no micrometre number this app publishes
rests on the approximation -- which is true of this budget and was not true of the one
before it, where a 5,543-tip TXM region on a scaled frame fell to the sampled path.
"""
import math

import numpy as np
from scipy import sparse
from scipy.sparse import csgraph

_SQRT2 = math.sqrt(2.0)

#: TWO SEPARATE BUDGETS, because they bound different things and collapsing them into one
#: constant is what made the first version of this file unusable.
#:
#: _MEM is source-rows x nodes in one scipy call -- a MEMORY bound. 2e7 float64 is ~160 MB.
#:
#: _EXACT_WORK is tips x edges, and it answers the only question that matters at the top of
#: the dispatch: can this region afford an exact all-pairs sweep? Asking it that way rather
#: than "how many sources fit in a time budget" is not cosmetic. The earlier form capped
#: sources at ~460 and sent a 5,543-tip TXM region -- 7.5e8 work, 4.0 s -- down the
#: approximate path, which put the one and only "lower bound" caveat in the whole corpus on
#: a SCALED frame's headline MCL. (Its sampled answer was 7423.79 px. So is its exact one.)
#: At 2e9 that region is exact in ~10 s, while the dense SEM mats stay 20x above the line.
#:
#: THESE ARE NOT TUNING KNOBS, THEY ARE THE REASON THIS FILE HAS THREE METHODS. The largest
#: region in the corpus has a 929,304 px skeleton with 44,263 tips -- 16x the skeleton of
#: the largest region in the first frame, which is what an early version of this file was
#: profiled on and sized for. An all-pairs sweep over 44,263 tips is not slow, it is
#: intractable, and a version of this code that only did all-pairs turned a 35-minute batch
#: into one that had not finished 20 of 142 masks in 25 minutes.
_MEM = 2e7
_EXACT_WORK = 2e9
_MIN_CHUNK = 16
_MAX_SWEEPS = 12
#: Sources to spend once a region is over _EXACT_WORK. A FLAT cap, not a budget, because
#: the iterated sweep above it is what actually finds the answer -- on every cyclic region
#: where the exact value is computable it already had it, and the spread sample has never
#: improved on it. More sources here would buy insurance, not accuracy, and would buy it
#: on exactly the regions where each source is most expensive.
_SAMPLE_SOURCES = 256

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
    whole chains, so the reduction is exact for anchor-to-anchor distance. How much it
    buys depends on how junction-dense the region is, and both extremes are here: a long
    wandering crack goes 57,560 nodes -> 4,251, while the largest region of all, a dense
    mat, only goes 929,304 -> 387,076. The reduction was never going to make that one
    tractable on its own, which is why there is a budget below it.

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
    info["n_reduced_nodes"] = int(anchor.size)

    # THREE METHODS, AND WHICH ONE RAN TRAVELS WITH THE VALUE. Two of them are exact and
    # one is not, and a reader cannot tell from the number which they got.
    if info["is_tree"]:
        # A tree's diameter is two sweeps: the farthest node from anywhere is an end of
        # some diameter, and the farthest node from THAT is the other end. Exact, O(E log
        # V), and it does not care that the region has a million skeleton pixels. Both
        # endpoints come out tips, because on a tree the farthest node from any node is a
        # leaf -- so this is the tip-to-tip maximum and not merely a bound on it.
        info["method"] = "double_sweep_exact"
        best, src = _iterated_sweep(g, tips)
        info["n_dijkstra_sources"] = src
        return best, info

    info["exact_work"] = int(tips.size) * int(w.size)
    if info["exact_work"] <= _EXACT_WORK:
        info["method"] = "all_pairs_exact"
        info["n_dijkstra_sources"] = int(tips.size)
        return _sweep_from(g, tips, tips)[0], info

    # Cyclic AND too large to sweep from every tip. A LOWER BOUND, and it says so.
    # Iterated sweep first -- hop to the farthest tip and sweep again until it stops
    # improving, which on a graph whose cycles are small and local converges on the true
    # pair in a handful of hops -- then evenly spaced tips to spend the rest of the
    # budget. Evenly spaced and not random: the same mask must measure the same twice.
    info["method"] = "sampled_sources_lower_bound"
    best, used = _iterated_sweep(g, tips)
    spread = tips[np.unique(np.linspace(0, tips.size - 1,
                                        max(0, _SAMPLE_SOURCES - used)).round().astype(int))]
    if spread.size:
        best = max(best, _sweep_from(g, spread, tips)[0])
    info["n_dijkstra_sources"] = int(used + spread.size)
    return best, info


def _sweep_from(g, sources, tips):
    """(max distance from any source to any tip, the tip that attained it). Memory-chunked."""
    best, arg = 0.0, None
    step = max(_MIN_CHUNK, int(_MEM // max(g.shape[0], 1)))
    for i in range(0, sources.size, step):
        d = csgraph.dijkstra(g, directed=False,
                             indices=sources[i:i + step])[:, tips]
        d = np.where(np.isfinite(d), d, -np.inf)
        if d.size and d.max() > best:
            best = float(d.max())
            arg = int(tips[int(np.unravel_index(int(d.argmax()), d.shape)[1])])
    return best, arg


def _iterated_sweep(g, tips):
    """Hop to the farthest tip and sweep again until it stops improving. (value, n_runs).

    Two hops is the classic double sweep, exact on a tree. Continuing past two costs one
    Dijkstra each and can only raise a lower bound, so it is not a heuristic with a
    downside -- every value it reports is a real tip-to-tip route that exists in the graph.

    ONCE PER CONNECTED COMPONENT, which an all-pairs sweep gets for free and this does not:
    hopping from the farthest tip can only ever reach tips in the component it started in,
    so a seed in the wrong one silently reports that component's diameter as the region's.
    A region from regionprops is connected and its skeleton is too, so in the pipeline
    there is exactly one component and this loop runs once -- but "the caller always hands
    me a connected graph" is not a thing this function can check, and a test that feeds it
    two blobs at once found the shortfall at 76%.
    """
    if tips.size < 2:
        return 0.0, 0
    ncomp, lab = csgraph.connected_components(g, directed=False)
    best, runs = 0.0, 0
    for comp in np.unique(lab[tips]):
        ctips = tips[lab[tips] == comp]
        if ctips.size < 2:
            continue
        cur = ctips[0]
        cbest = 0.0
        for _ in range(_MAX_SWEEPS):
            v, nxt = _sweep_from(g, np.array([cur]), ctips)
            runs += 1
            if nxt is None or v <= cbest + 1e-12:
                break
            cbest, cur = v, nxt
        best = max(best, cbest)
    return best, runs


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
    step = max(_MIN_CHUNK, int(_MEM // max(n, 1)))
    for i in range(0, n, step):
        d = csgraph.dijkstra(g, directed=False, indices=np.arange(i, min(i + step, n)))
        finite = np.isfinite(d)
        if finite.any():
            best = max(best, float(d[finite].max()))
    return best
