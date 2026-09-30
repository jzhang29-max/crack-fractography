#!/usr/bin/env python3
"""The longest single crack, against a reference that shares none of its machinery.

Run: ../.venv/bin/python3 tests/test_geodesic.py

The thing at risk here is not the idea -- "longest shortest path between two skeleton
tips" is one sentence -- it is the two optimisations underneath it, each of which fails
silently and plausibly:

  THE GRAPH. If the edge set drifts from the one skeleton_path_length sums over, the
  geodesic measures a different skeleton from the length it is reported beside, and could
  return a "longest crack" longer than the network containing it. Checked by summing the
  graph's own weights against the shared implementation, on every random shape below.

  THE REDUCTION. Collapsing degree-2 runs into weighted edges is exact only if each chain
  carries its two boundary edges and parallel chains between the same pair of anchors keep
  the MINIMUM, not the sum -- and coo_matrix sums duplicates by default, so the wrong
  behaviour is the default one. A summed pair inflates every route through it, which looks
  like nothing at all: a slightly longer longest crack. Checked against a brute-force
  Dijkstra over the FULL pixel graph, which does no reduction of any kind.

Every guard here is run against a case that makes it fail, so a guard that has stopped
measuring anything says so instead of printing PASS.
"""
import math
import os
import sys

import numpy as np
from scipy import sparse
from scipy.sparse import csgraph

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, REPO)
import geodesic as G                                   # noqa: E402
from measure import measure_frame                      # noqa: E402
from shared_impl import skeleton_stats                 # noqa: E402
from _vendor.extended_features import skeleton_path_length as _vendor_len  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))
    if not cond:
        FAILED.append(name)


def mk(rows):
    return np.array([[ch == "#" for ch in r] for r in rows], bool)


def _reachable(obj):
    """Every key anywhere in the nested record -- same helper as test_no_stranded_fields."""
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            out |= _reachable(v)
    return out


def s_frame(_rows):
    """The frame summary for a TXM stem, whose scale is a constant, so the micrometre
    fields exist. Measuring an unscaled frame would compare against an empty field set and
    pass for the wrong reason."""
    m = np.zeros((160, 160), bool)
    m[78:82, 10:150] = True
    for x in range(14, 146, 12):
        m[30:130, x:x + 3] = True
    return measure_frame(m, "Average_mosaic_260618_B2_2_1", "txm")[1]


def brute_tip_geodesic(skel):
    """Reference: Dijkstra on the FULL pixel graph, from every degree-1 pixel.

    Shares the edge builder and nothing else -- no anchor set, no chain collapsing, no
    duplicate handling. If the reduction in geodesic.py is wrong in either direction this
    disagrees with it.
    """
    S = np.asarray(skel, bool)
    r, c, w = G.skeleton_edges(S)
    px = np.flatnonzero(S.ravel())
    loc = np.full(S.size, -1, np.int64)
    loc[px] = np.arange(px.size)
    r, c = loc[r], loc[c]
    if w.size == 0:
        return None
    deg = np.bincount(np.concatenate([r, c]), minlength=px.size)
    tips = np.flatnonzero(deg == 1)
    if tips.size < 2:
        return None
    # coo->csr sums duplicates, so the reference is only a reference if the pixel edge
    # list has none. The four edge types produce four disjoint sets of unordered pairs;
    # asserted rather than assumed, because a reference that shares the bug proves nothing.
    key = np.minimum(r, c).astype(np.int64) * px.size + np.maximum(r, c)
    assert np.unique(key).size == key.size, "duplicate pixel edges: reference is unsound"
    g = sparse.coo_matrix((w, (r, c)), shape=(px.size, px.size)).tocsr()
    d = csgraph.dijkstra(g, directed=False, indices=tips)[:, tips]
    d = d[np.isfinite(d)]
    return float(d.max()) if d.size else None


def random_blobs(n, rng):
    """Shapes that actually branch and loop. A random-noise mask skeletonises to dust and
    would let a reduction bug through on regions that have no chains to collapse."""
    out = []
    for _ in range(n):
        H = W = int(rng.integers(24, 56))
        m = np.zeros((H, W), bool)
        for _ in range(int(rng.integers(3, 9))):
            y0, x0 = rng.integers(2, H - 4), rng.integers(2, W - 4)
            y1, x1 = rng.integers(2, H - 2), rng.integers(2, W - 2)
            n_step = max(abs(int(y1) - int(y0)), abs(int(x1) - int(x0))) + 1
            ys = np.linspace(y0, y1, n_step).round().astype(int)
            xs = np.linspace(x0, x1, n_step).round().astype(int)
            m[ys, xs] = True
        m = np.pad(m, 2)
        if m.sum() > 8:
            out.append(m)
    return out


def main():
    # ---- 1. The simple case must not merely be close. --------------------------------
    # An unbranched skeleton is a single path, so its two tips are the path's ends and the
    # only route between them is the whole thing. If these are ever unequal, the two
    # columns have a discontinuity at exactly the topology where they should agree.
    for name, S in (("horizontal", mk([".....", "#####", "....."])),
                    ("diagonal", mk(["#....", ".#...", "..#..", "...#.", "....#"])),
                    ("staircase", mk(["##...", ".##..", "..##.", "...##"])),
                    ("L-corner", mk(["##...", ".#...", ".#..."]))):
        r, c, w = G.skeleton_edges(S)
        net = float(w.sum())
        val, info = G.longest_tip_geodesic(S, net)
        check(f"unbranched '{name}': geodesic IS the whole centreline, exactly",
              val is not None and val == net, f"{val} vs {net}")

    # A branched one where the answer is arithmetic: a 5-wide cross is two 5-px arms
    # crossing, so the longest single crack is 4 and the network is 8.
    S = mk(["..#..", "..#..", "#####", "..#..", "..#.."])
    val, _ = G.longest_tip_geodesic(S, float(G.skeleton_edges(S)[2].sum()))
    check("branched cross: 4 (one arm pair), not 8 (the network)",
          val == 4.0 and float(G.skeleton_edges(S)[2].sum()) == 8.0, f"{val}")

    # ---- 2. The graph is the one the length is summed over. --------------------------
    rng = np.random.default_rng(11)
    blobs = random_blobs(160, rng)
    worst = 0.0
    for m in blobs:
        sl, _, _, skel, _, _ = skeleton_stats(m)
        worst = max(worst, abs(float(G.skeleton_edges(skel)[2].sum()) - sl))
    check("graph weight == the shared implementation's skeleton_path_length",
          worst < 1e-9, f"{len(blobs)} shapes, worst |diff| {worst:.3e} px")
    # ...and the check is live: a length that is not the graph's suppresses the value.
    S = mk(["..#..", "..#..", "#####", "..#..", "..#.."])
    bad, info = G.longest_tip_geodesic(S, 999.0)
    check("a length that is not this graph's emits NOTHING, not a plausible number",
          bad is None and info["reason"] == "graph_length_mismatch", str(info["reason"]))

    # ---- 3. The reduction, against a reference that does not reduce. -----------------
    # TOLERANCE, and why it is not zero: the reduction adds a chain's steps up once and
    # the reference adds the same steps up again inside Dijkstra, in a different order, so
    # the two disagree in the last bits of a float. Measured worst case over these shapes
    # is ~1e-13 px on lengths of order 10-100 px. The tolerance is set five orders above
    # that and eight below anything a min-vs-sum or a dropped-boundary-edge bug could
    # produce -- those move a chain by whole pixels, which is why 1e-9 still catches them.
    TOL = 1e-9
    n_ok = n_cmp = 0
    worst = 0.0
    for m in blobs:
        sl, _, _, skel, _, _ = skeleton_stats(m)
        val, _ = G.longest_tip_geodesic(skel, sl)
        ref = brute_tip_geodesic(skel)
        if val is None and ref is None:
            continue
        n_cmp += 1
        if val is not None and ref is not None:
            worst = max(worst, abs(val - ref))
            n_ok += abs(val - ref) <= TOL
    check("chain collapsing + min-dedup reproduce full-pixel Dijkstra",
          n_cmp > 40 and n_ok == n_cmp,
          f"{n_ok}/{n_cmp} shapes within {TOL:g}, worst |diff| {worst:.3e}")
    # The comparison is live: perturbing one reduced chain by a single pixel must break it.
    _real = G._min_dedup
    try:
        G._min_dedup = lambda n, er, ec, ew: _real(n, er, ec, ew + 1.0)
        n_bad = 0
        for m in blobs[:40]:
            sl, _, _, skel, _, _ = skeleton_stats(m)
            val, _ = G.longest_tip_geodesic(skel, sl)
            ref = brute_tip_geodesic(skel)
            if val is not None and ref is not None and abs(val - ref) > TOL:
                n_bad += 1
    finally:
        G._min_dedup = _real
    check("...and it would notice: +1 px on every reduced edge breaks it",
          n_bad > 20, f"{n_bad} of 40 shapes disagree once the reduction is wrong")

    # The dedup specifically. A ring with a tail at each of two opposite corners gives two
    # parallel chains between the same pair of anchors; summing them instead of taking the
    # minimum sends the only route the long way round.
    S = mk(["#........",
            ".#######.",
            ".#.....#.",
            ".#.....#.",
            ".#######.",
            "........#"])
    sl = float(G.skeleton_edges(S)[2].sum())
    val, info = G.longest_tip_geodesic(S, sl)
    ref = brute_tip_geodesic(S)
    check("two chains between one pair of anchors: the SHORTER is the route",
          val is not None and ref is not None and val == ref and val < sl,
          f"geodesic {val}, brute {ref}, network {sl}, cycles {info['n_cycles']}")

    # ---- 4. On a tree it is not a lower bound, it is the answer. ---------------------
    # The all-pixel geodesic diameter can beat a tip-to-tip route on a cyclic skeleton, so
    # the value ships with geodesic_is_lower_bound. That flag has to be FALSE for a reason.
    n_tree = n_tree_eq = n_cyc = n_cyc_lt = 0
    for m in blobs:
        sl, _, _, skel, _, _ = skeleton_stats(m)
        val, info = G.longest_tip_geodesic(skel, sl)
        if val is None or skel.sum() > 1500:
            continue
        ex = G.all_pixel_geodesic_diameter(skel)
        if info["is_tree"]:
            n_tree += 1
            n_tree_eq += abs(ex - val) < 1e-9
        else:
            n_cyc += 1
            n_cyc_lt += ex > val + 1e-9
        if ex + 1e-9 < val:
            check("all-pixel diameter is never below tip-to-tip", False, f"{ex} < {val}")
    check("acyclic skeleton: tip-to-tip == the exact all-pixel geodesic diameter",
          n_tree > 20 and n_tree_eq == n_tree, f"{n_tree_eq}/{n_tree} tree shapes")
    check("cyclic skeletons exist in the sample, and some ARE lower bounds",
          n_cyc > 0 and n_cyc_lt > 0,
          f"{n_cyc_lt} of {n_cyc} cyclic shapes read below the all-pixel diameter -- "
          f"this is what geodesic_is_lower_bound marks")

    # ---- 4b. The fallback for regions too large to sweep exhaustively. --------------
    # It is a lower bound by construction and labelled one. Two things are checked, and
    # the second is the one that matters: that it is not a LOOSE bound, and that the part
    # of it doing the work is actually doing work.
    #
    # Forced on by dropping the exact-work budget to nothing -- these shapes are far too
    # small to trigger it for real, which is the point: a region is approximated only when
    # tips x edges exceeds _EXACT_WORK, so the fallback has to be provoked to be measured.
    cyc = []
    for m in blobs:
        sl, _, _, skel, _, _ = skeleton_stats(m)
        nn, r, c, w, deg = G._local_graph(skel)
        if w.size == 0 or w.size - nn + 1 <= 0:      # trees are exact by construction
            continue
        anchor, g, _ = G._reduce(nn, r, c, w, deg)
        if g is None:
            continue
        tp = np.flatnonzero(deg[anchor] == 1)
        if tp.size < 4:
            continue
        ex = G._sweep_from(g, tp, tp)[0]             # all-pairs: the truth
        if ex > 0:
            cyc.append((skel, sl, ex))
    check("there are cyclic shapes to test the fallback on at all", len(cyc) >= 20,
          f"{len(cyc)} cyclic shapes with >= 4 tips")

    def forced(n_sources):
        keep = (G._EXACT_WORK, G._SAMPLE_SOURCES)
        out = []
        try:
            G._EXACT_WORK, G._SAMPLE_SOURCES = 0, n_sources
            for skel, sl, ex in cyc:
                v, info = G.longest_tip_geodesic(skel, sl)
                if info.get("method") == "sampled_sources_lower_bound":
                    out.append((ex, v))
        finally:
            G._EXACT_WORK, G._SAMPLE_SOURCES = keep
        return np.array(out) if out else np.zeros((0, 2))

    thin, fat = forced(4), forced(8)
    for name, a in (("thin budget", thin), ("realistic budget", fat)):
        check(f"{name}: the fallback is a LOWER bound, never above exact",
              a.size and not (a[:, 1] > a[:, 0] + 1e-9).any(), f"n={len(a)}")
    # At 8 sources -- an eighth of what ships -- it already finds the exact answer every
    # time. (On the real corpus: 168 of 168 cyclic regions, median 3 sweeps.)
    check("fallback at 8 sources == exact all-pairs on every cyclic shape",
          len(fat) >= 20 and bool((np.abs(fat[:, 0] - fat[:, 1]) < 1e-9).all()),
          f"{int((np.abs(fat[:, 0] - fat[:, 1]) < 1e-9).sum())}/{len(fat)}")
    # ...and starve it, and it degrades. Without this the check above cannot distinguish
    # "the spread sample closes the gap" from "these shapes were easy and it never
    # mattered" -- the spread sample would be decoration and nothing would say so.
    shortfall = (thin[:, 0] - thin[:, 1]) / thin[:, 0]
    check("starved of sources it DOES fall short, so the sample is not decoration",
          len(thin) >= 20 and bool((shortfall > 1e-6).any()),
          f"worst shortfall at 4 sources: {100 * shortfall.max():.3f}% "
          f"(vs {100 * ((fat[:, 0] - fat[:, 1]) / fat[:, 0]).max():.3f}% at 8)")

    # ---- 5. A closed loop has no tip-to-tip crack, and does not pretend to. ----------
    S = mk([".###.", ".#.#.", ".###."])
    val, info = G.longest_tip_geodesic(S, float(G.skeleton_edges(S)[2].sum()))
    check("a closed loop returns None with a reason, never 0",
          val is None and info["n_tips"] == 0 and "no skeleton tips" in info["reason"],
          str(info["reason"]))

    # ---- 6. The frame level: the fix, stated as an inequality. -----------------------
    # A branched network in a small frame. Before the change, "Longest crack (MCL)" was the
    # network total and could not be bounded by anything the frame contains.
    m = np.zeros((120, 120), bool)
    m[58:62, 10:110] = True                        # one long backbone
    for x in range(14, 106, 8):                    # 12 ribs off it
        m[20:100, x:x + 3] = True
    rows, s = measure_frame(m, "synthetic_comb", "sem")
    r0 = rows[0]
    check("per-region: the longest crack is a fraction of the network's centreline",
          r0["TipToTipGeodesic_px"] < 0.5 * r0["SkeletonLength_px"],
          f"geodesic {r0['TipToTipGeodesic_px']} of network {r0['SkeletonLength_px']} px")
    n_reg = over = 0
    for m in blobs:
        sl, _, _, skel, _, _ = skeleton_stats(m)
        val, _ = G.longest_tip_geodesic(skel, sl)
        if val is None:
            continue
        n_reg += 1
        over += val > sl + 1e-9
    check("the geodesic can never exceed the network containing it",
          n_reg > 100 and over == 0 and
          all((r["TipToTipGeodesic_px"] or 0) <= r["SkeletonLength_px"] + 1e-6
              for r in rows), f"{n_reg} random shapes + {len(rows)} comb regions, {over} over")
    # A comb of 12 ribs 80 px tall on a 100 px backbone: the longest single crack runs up
    # one rib, along the backbone and down another -- order 260 px, not the ~1200 px of
    # centreline the network holds.
    check("per-region: and it is bounded by the frame, which the network total is not",
          r0["TipToTipGeodesic_px"] < 300 and r0["SkeletonLength_px"] > 900,
          f"geodesic {r0['TipToTipGeodesic_px']} px, network {r0['SkeletonLength_px']} px, "
          f"frame 120x120")

    # The two frame-level fields, and the bracket on each.
    for key in ("mcl", "largest_network_centreline"):
        vals = np.array([r["TipToTipGeodesic_px"] if key == "mcl" else r["SkeletonLength_px"]
                         for r in rows], float)
        from measure import _bracket
        b = _bracket(key, vals, rows, 0.05)
        check(f"{key}: value, uncensored bracket and censored flag all present",
              b[f"{key}_um"] is not None and b[f"{key}_censored"] is not None,
              str(b))
    from measure import _bracket
    geos = np.array([r["TipToTipGeodesic_px"] for r in rows], float)
    nets = np.array([r["SkeletonLength_px"] for r in rows], float)
    a = _bracket("mcl", geos, rows, 0.05)
    b = _bracket("largest_network_centreline", nets, rows, 0.05)
    check("frame: MCL never exceeds the largest network's centreline",
          a["mcl_um"] <= b["largest_network_centreline_um"],
          f"MCL {a['mcl_um']} um vs network {b['largest_network_centreline_um']} um")
    # The bracket is a bracket: dropping edge-touching regions can only lower a max.
    check("frame: the uncensored end of each bracket is never the larger one",
          all(x[f"{k}_um_uncensored_only"] is None
              or x[f"{k}_um_uncensored_only"] <= x[f"{k}_um"] + 1e-9
              for k, x in (("mcl", a), ("largest_network_centreline", b))),
          f"{a['mcl_um_uncensored_only']} <= {a['mcl_um']}")

    # ---- 6b. The skeleton memo returns the shared implementation's own answer. ------
    # It exists for speed: measuring a region skeletonizes it twice, and on the corpus's
    # big frames skeletonize IS the measurement. A cache that returned anything other than
    # what the SEM repo's function returns would silently decouple this app's numbers from
    # that repo's, which is the one thing shared_impl exists to prevent.
    import shared_impl as SI
    mod = SI._resolve()["module"]
    raw = getattr(mod.skeleton_stats, "_raw", None)
    check("the memo is installed on the shared module", raw is not None)
    if raw is not None:
        agree = miss = 0
        for m in blobs[:30]:
            a, b = raw(m), SI.skeleton_stats(m)
            same = (a[0] == b[0] and a[1] == b[1] and a[2] == b[2] and a[5] == b[5]
                    and bool((a[3] == b[3]).all()) and bool((a[4] == b[4]).all()))
            agree += same
            miss += not same
        check("memoized skeleton_stats == the raw function, on every field",
              miss == 0, f"{agree}/{agree + miss} shapes")
        # Distinct masks must not collide, and the second look at one mask must be a hit.
        one, two = blobs[0], blobs[1]
        SI.skeleton_stats(one)
        hit = SI.skeleton_stats(one)
        check("a repeat call returns the cached object (so it was a hit)",
              hit[3] is SI.skeleton_stats(one)[3])
        check("a different mask evicts rather than returning the wrong skeleton",
              SI.skeleton_stats(two)[0] == raw(two)[0])
        # A cached array a caller writes to would poison the next region silently.
        try:
            SI.skeleton_stats(one)[3][0, 0] = True
            wrote = True
        except ValueError:
            wrote = False
        check("a cached skeleton cannot be written to", not wrote)

    # ---- 6c. The two region counters exist WITHOUT a physical scale. ----------------
    # They sat inside measure_frame's micrometre block for one run. Everything looked
    # right -- the fields were on every frame the app shows a MCL for -- but the only
    # frames the approximation has ever fired on are unscaled, so the counter for
    # "regions measured approximately" was absent from all 127 of them and read as a
    # clean zero from the scaled ones. The guard is the unscaled frame, not the scaled.
    m = np.zeros((160, 160), bool)
    m[78:82, 10:150] = True
    for x in range(14, 146, 12):
        m[30:130, x:x + 3] = True
    unscaled = measure_frame(m, "no_scale_at_all", "sem")[1]
    check("an UNSCALED frame has no micrometre fields (the premise of this guard)",
          not unscaled["scale_known"] and unscaled.get("mcl_um") is None)
    for k in ("n_regions_geodesic_undefined", "n_regions_geodesic_sampled"):
        check(f"...and still carries '{k}'",
              isinstance(unscaled.get(k), int), f"{k}={unscaled.get(k)!r}")

    # ---- 7. Nothing computed here may be silently discarded. ------------------------
    # Same failure as tests/test_no_stranded_fields.py catches for segments.py: a field
    # produced on every frame of every run that no reader ever looks at. The two
    # *_definition strings are the ones most likely to rot -- they are prose, so nothing
    # breaks when they stop being rendered, and a reader then meets the number with the
    # label alone, which is the whole defect this change exists to fix.
    js = open(os.path.join(REPO, "app", "static", "app.js"), encoding="utf-8").read()
    rendered = [k for k in sorted(_reachable(s_frame(rows)))
                if k.startswith(("mcl", "largest_network_centreline"))]
    missing = [k for k in rendered if k not in js]
    check("every frame-level MCL/network field is read by the frame card",
          not missing, f"{len(rendered)} fields, stranded: {missing}")
    check("both definitions reach the reader, not just the CSV",
          "mcl_definition" in js and "largest_network_centreline_definition" in js)
    # Per-region columns ride the generic CSV writer, which takes every non-dict key -- so
    # the guard there is that they are actually ON the row, under the names the docs use.
    for k in ("TipToTipGeodesic_px", "geodesic_has_cycles", "geodesic_method",
              "geodesic_undefined_reason"):
        check(f"per-region column '{k}' is on every row", all(k in r for r in rows))
    # Which method produced the headline number is part of the number.
    check("every measured region records HOW its geodesic was computed",
          all(r["geodesic_method"] in ("double_sweep_exact", "all_pairs_exact",
                                       "sampled_sources_lower_bound")
              for r in rows if r["TipToTipGeodesic_px"] is not None),
          str({r["geodesic_method"] for r in rows}))

    print()
    if FAILED:
        print(f"{len(FAILED)} FAILED: " + ", ".join(FAILED))
        return 1
    print("all geodesic guards pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
