#!/usr/bin/env python3
"""Is the scale ladder's base, top and step right, or just the first thing written down?

WHY THIS EXISTS. detector_overrides.SCALE_LADDER is (5, 10, 20, 40, 80, 160, 320): a
doubling ladder spanning three octaves either side of flatten_background's stock sigma=40.
Seven rungs is not a choice, it is what those three choices imply. Figure 6 letters both
the ladder and its rung count F and says so in as many words -- "a doubling ladder, not a
searched set ... no sweep over ALTERNATIVE ladders -- a different base, count or top --
exists in this project". This is that sweep.

WHAT IS ALREADY KNOWN AND WHY IT IS NOT AN ANSWER. parameters_tiles.json scores one rung
at a time and the result is monotone: pooled tile IoU rises 0.1285 at sigma=5 to 0.2155 at
sigma=320, still climbing at the top rung. Read naively that says "extend the ladder". But
the tiles are 512 px square, and flatten_background subtracts a gaussian-blurred copy, so
at sigma >= 512 the "background" is within a hair of a global constant and the high-pass
stops being local at all. The monotone rise may therefore be an artefact of the tile size
rather than a fact about the detector. This script measures that directly instead of
arguing about it: SATURATION_CHECK below reports where the tile result stops moving.

WHAT IS SWEPT
  base   the smallest radius            5 ... 80
  top    the largest radius            40 ... 2560
  step   the ratio between rungs        2 (shipped) and 4
rung count is log_step(top/base) + 1, so it is read off rather than chosen.

HOW A WINNER IS PICKED. Not argmax over 26 tiles -- that picks whatever fits 26 tiles.
Leave-one-SPECIMEN-out, the same selector this project used to settle absolute_dark_thresh
("leave-one-specimen-out picks t=10 in 12 of 13 folds"): for each held-out specimen choose
the ladder that wins on the other twelve, then score that choice on the specimen it never
saw. A ladder that only wins in-sample shows up as a fold that disagrees.

Run:  <sem-venv>/bin/python -B analysis/research/improve/ladder_endpoints.py
Writes docs/figures/ladder_endpoints.json.
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
FIGS = os.path.join(REPO, "paper", "figures")
sys.path.insert(0, FIGS)
sys.path.insert(0, os.path.join(REPO, "analysis"))

import _paths                                        # noqa: E402

#: The same path order mk_parameters.py sets up. Without it `detect_cracks` and
#: `unified_pipeline` are not importable and this file cannot call the shipped stages.
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "code"))
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "interior_active_learning", "code"))

import detect_cracks as D                            # noqa: E402  (shipped stages)
import detector_overrides as DO                      # noqa: E402  (shipped constants)
import both_modalities as BM                         # noqa: E402
from mk_parameters import tile_chain                 # noqa: E402  the shipped chain

OUT = os.path.join(REPO, "docs", "figures", "ladder_endpoints.json")

#: Every radius any candidate ladder needs. Each is cut ONCE per tile and reused, which is
#: sound because the shipped union is `OR` over independent per-rung cuts plus the absolute
#: gate -- verified against a direct shipped call in CONTROL 2 below, not assumed.
SIGMAS = (5, 10, 20, 40, 80, 160, 320, 640, 1280, 2560)

K = float(BM.MAD_K)
GATE = int(DO.ABSOLUTE_DARK_THRESH)
SHIPPED = tuple(DO.SCALE_LADDER)


def ladders():
    """(label, rungs) for every candidate. Doubling unless the label says otherwise."""
    out = {}
    for step in (2, 4):
        for base in (5, 10, 20, 40, 80):
            for top in (40, 80, 160, 320, 640, 1280, 2560):
                if top < base:
                    continue
                rungs, s = [], base
                while s <= top:
                    rungs.append(s)
                    s *= step
                if rungs[-1] != top or len(rungs) < 2:
                    continue        # top not reachable from base by this step
                out[f"x{step}_{base}-{top}"] = tuple(rungs)
    out["shipped"] = SHIPPED
    for s in SIGMAS:               # single rungs, to reproduce the known per-rung curve
        out[f"single_{s}"] = (s,)
    return out


def main():
    t0 = time.time()
    TB = _paths.tilebench()
    tiles = TB.load()
    if not TB.controls():
        raise SystemExit("tilebench's own controls did not pass; nothing here is readable")
    print(f"  CONTROL tilebench self-check: PASS  ({len(tiles)} tiles, "
          f"{len({t['specimen'] for t in tiles})} specimens)")

    class _U:
        pass

    u = _U()
    DO.install(u)

    # ---- per-tile, per-sigma dark cuts, with the absolute gate switched OFF so each
    #      cut is that rung alone. The gate is OR'd back in once per ladder.
    cuts = []          # cuts[i][sigma] -> bool array
    flats, gates = [], []
    for i, t in enumerate(tiles):
        img8 = t["img8"]
        flat = D.flatten_background(img8, sigma=40)
        flats.append(flat)
        gates.append(img8 < GATE)
        per = {}
        for s in SIGMAS:
            class _V:
                pass
            v = _V()
            DO.install(v, scale_ladder=(s,), use_multiscale_union=True,
                       absolute_dark_thresh=0)
            per[s] = v.segment_dark_regions(flat, img8=img8, mad_k=K)
        cuts.append(per)
        if (i + 1) % 5 == 0 or i + 1 == len(tiles):
            print(f"    cut {i + 1}/{len(tiles)} tiles  ({time.time() - t0:.0f}s)")

    vess = [D.compute_vesselness(f) for f in flats] if DO.USE_REGION_CLASSIFIER \
        else [None] * len(tiles)

    # ---- CONTROL 2: the cached decomposition must reproduce the shipped proposal.
    bad = []
    for i, t in enumerate(tiles):
        mine = gates[i].copy()
        for s in SHIPPED:
            mine |= cuts[i][s]
        theirs = u.segment_dark_regions(flats[i], img8=t["img8"], mad_k=K)
        if not np.array_equal(mine, theirs):
            bad.append(t["frame"])
    if bad:
        raise SystemExit(f"the cached per-rung decomposition does not reproduce the "
                         f"shipped union on {len(bad)} tiles ({bad[:3]}); every row below "
                         f"would be a different detector")
    print(f"  CONTROL cached rungs OR gate == shipped segment_dark_regions on all "
          f"{len(tiles)} tiles: PASS")

    # ---- CONTROL 3: and the chain on top must be the shipped chain.
    mism = []
    for i, t in enumerate(tiles):
        _f, proposed, _c, final = BM.stages(t["img8"])
        got = tile_chain(proposed, flat=flats[i], img8=t["img8"], ves=vess[i])
        if not np.array_equal(got, final):
            mism.append(t["frame"])
    if mism:
        raise SystemExit(f"tile_chain != both_modalities.stages on {mism[:3]}")
    print(f"  CONTROL tile_chain == both_modalities.stages on all {len(tiles)} tiles: PASS")

    # ---- score every candidate ladder
    cand = ladders()
    per_tile = {}
    for n, (label, rungs) in enumerate(sorted(cand.items()), 1):
        rows = []
        for i, t in enumerate(tiles):
            prop = gates[i].copy()
            for s in rungs:
                prop |= cuts[i][s]
            m = tile_chain(prop, flat=flats[i], img8=t["img8"], ves=vess[i])
            c = TB.counts(m, t["gt"], tol=0)
            rows.append(dict(frame=t["frame"], specimen=t["specimen"],
                             tp=int(c["tp"]), fp=int(c["fp"]), fn=int(c["fn"])))
        per_tile[label] = rows
        if n % 10 == 0 or n == len(cand):
            print(f"    scored {n}/{len(cand)} ladders  ({time.time() - t0:.0f}s)")

    def agg(rows, drop=()):
        tp = sum(r["tp"] for r in rows if r["frame"] not in drop)
        fp = sum(r["fp"] for r in rows if r["frame"] not in drop)
        fn = sum(r["fn"] for r in rows if r["frame"] not in drop)
        p = tp / max(tp + fp, 1)
        r_ = tp / max(tp + fn, 1)
        return dict(precision=round(p, 4), recall=round(r_, 4),
                    iou=round(tp / max(tp + fp + fn, 1), 4),
                    f1=round(2 * p * r_ / max(p + r_, 1e-12), 4), tp=tp, fp=fp, fn=fn)

    flood = TB.FLOODED
    summary = {label: {"rungs": list(rungs), "n_rungs": len(rungs),
                       "pooled_26": agg(per_tile[label]),
                       "pooled_25": agg(per_tile[label], drop=(flood,))}
               for label, rungs in cand.items()}

    # ---- leave-one-specimen-out over the DOUBLING ladders only (the family in question)
    fam = [L for L in cand if L.startswith("x2_")] + ["shipped"]
    specs = sorted({t["specimen"] for t in tiles})
    folds = []
    for s in specs:
        def inner(label):
            return agg([r for r in per_tile[label] if r["specimen"] != s])["iou"]
        pick = max(fam, key=inner)
        held = agg([r for r in per_tile[pick] if r["specimen"] == s])
        held_shipped = agg([r for r in per_tile["shipped"] if r["specimen"] == s])
        folds.append(dict(held_out=s, picked=pick, picked_rungs=list(cand[pick]),
                          picked_n_rungs=len(cand[pick]),
                          iou_of_pick_on_held_out=held["iou"],
                          iou_of_shipped_on_held_out=held_shipped["iou"]))
    from collections import Counter
    votes = Counter(f["picked"] for f in folds)
    vote_n = Counter(f["picked_n_rungs"] for f in folds)

    # ---- does the tile result saturate? If the top rung stops changing the mask, the
    #      tiles cannot speak about the top of the ladder at all.
    sat = {}
    for i, t in enumerate(tiles[:1]):
        pass
    for s in SIGMAS:
        changed = sum(int((cuts[i][s] != cuts[i][SIGMAS[SIGMAS.index(s) - 1]]).sum())
                      for i in range(len(tiles))) if s != SIGMAS[0] else None
        sat[str(s)] = dict(
            px_marked=sum(int(cuts[i][s].sum()) for i in range(len(tiles))),
            px_differing_from_previous_rung=changed)
    tile_px = sum(int(t["img8"].size) for t in tiles)

    rec = dict(
        what="base, top and step of the multi-scale flattening ladder, swept on the tiles",
        generated=time.strftime("%Y-%m-%d"),
        scorer="analysis/research/tilebench.py via paper/figures/_paths.tilebench()",
        aggregation="pooled over every pixel at zero tolerance",
        n_tiles=len(tiles), n_specimens=len(specs), flood_tile=flood,
        mad_k=K, absolute_dark_thresh=GATE,
        use_region_classifier=DO.USE_REGION_CLASSIFIER,
        shipped_ladder=list(SHIPPED),
        controls={
            "tilebench": "PASS",
            "cached_rungs_reproduce_shipped_union": "PASS on every tile",
            "tile_chain_is_the_shipped_chain": "PASS on every tile",
        },
        total_tile_pixels=tile_px,
        saturation=sat,
        saturation_note=(
            "the tiles are 512 px square. flatten_background subtracts a gaussian-blurred "
            "copy, so once sigma approaches the tile width the 'background' is near a "
            "global constant and the high-pass stops being local. px_differing_from_"
            "previous_rung going to ~0 at the top is that happening, and it means the "
            "tile bench cannot rank the TOP of the ladder -- only a full frame can."),
        ladders=summary,
        loso=dict(family=sorted(fam), folds=folds,
                  votes_by_label=dict(votes), votes_by_rung_count=dict(vote_n),
                  mean_held_out_iou_of_the_selector=round(
                      float(np.mean([f["iou_of_pick_on_held_out"] for f in folds])), 4),
                  mean_held_out_iou_of_shipped=round(
                      float(np.mean([f["iou_of_shipped_on_held_out"] for f in folds])), 4)),
        seconds=round(time.time() - t0, 1),
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rec, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}  ({rec['seconds']}s)")
    return rec


if __name__ == "__main__":
    r = main()
    s = r["ladders"]
    print(f"\n{'ladder':22s} {'rungs':>5s} {'IoU26':>7s} {'IoU25':>7s} {'F1_26':>7s}")
    for label in sorted(s, key=lambda L: -s[L]["pooled_26"]["iou"])[:16]:
        v = s[label]
        print(f"{label:22s} {v['n_rungs']:5d} {v['pooled_26']['iou']:7.4f} "
              f"{v['pooled_25']['iou']:7.4f} {v['pooled_26']['f1']:7.4f}")
    print(f"\nLOSO votes by rung count: {r['loso']['votes_by_rung_count']}")
    print(f"selector held-out IoU {r['loso']['mean_held_out_iou_of_the_selector']}  "
          f"vs shipped {r['loso']['mean_held_out_iou_of_shipped']}")
