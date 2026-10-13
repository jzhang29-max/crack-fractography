"""THE SECOND CONTEXT OPERATOR, AND THE NULL THAT PRICES IT.

ctx_lambda.py killed context as a GROWTH rule: at every matched area the blend's clDice
rose monotonically with lam and peaked at lam=1, the constant cost field, i.e. plain
dilation. Context growth leaks down dark structure outside the paint and each leak is new
skeleton, which is what tprec counts.

Gap BRIDGING is a different operator and deserves its own test. It cannot leak: it only
ever lays a route BETWEEN two pixels the shipped detector was already confident about,
and only if that route is cheap. It is the narrowest possible use of context.

THE NULL IS NOT THE SHIPPED MODEL. An information-free operator already beats the
shipped model on clDice by a wide margin (dilation, +0.126), so "bridging raised clDice"
is not evidence. Every bridging arm here is therefore priced against an isotropic
dilation given EXACTLY the same number of added pixels on EXACTLY the same tile. The
question is only whether a pixel spent on a bridge is worth more than a pixel spent on
width.
"""
import os, sys, json, itertools
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C, ctx_method as M
from ctx_matched import dilate_to_area

GRID = list(itertools.product((0.15, 0.30, 0.60), (40, 80, 160), (1, 2, 4)))   # tau, max_gap, radius


def main():
    ts = C.tiles()
    rows = {k: [] for k in GRID}
    null = {k: [] for k in GRID}
    base = []
    for i, t in enumerate(ts, 1):
        d = C.prep(t); gt = t["gt"]; seed = d["cur"]
        cost = M.cost_field(d["sm"], d["fr"])
        base.append(C.row(seed, gt))
        line = []
        for tau, gap, rad in GRID:
            p, kept = M.complete_paths(seed, cost, max_gap=gap, tau=tau, radius=rad)
            m = seed | p
            extra = int((m & ~seed).sum())
            rows[(tau, gap, rad)].append(C.row(m, gt))
            null[(tau, gap, rad)].append(C.row(dilate_to_area(seed, extra), gt))
            line.append(f"{len(kept)}/{extra}")
        print(f"  [{i:>2}/{len(ts)}] {t['frame'][:38]:<40} bridges/px " + " ".join(line[:4]), flush=True)

    b = C.pooled(base)
    print(f"\nshipped v1.49.1    clDice {b['cldice']:.4f}  IoU {b['iou']:.4f}  "
          f"P {b['precision']:.4f}  R {b['recall']:.4f}\n")
    print(f"{'tau':>5} {'gap':>5} {'r':>3} {'added x':>8} | {'BRIDGE clD':>11} {'IoU':>7} "
          f"| {'DILATE clD':>11} {'IoU':>7} | {'bridge-dilate':>14} {'vs shipped':>11}")
    print("-" * 104)
    out = {}
    ba = sum(r["area"] for r in base)
    for k in GRID:
        mb, mn = C.pooled(rows[k]), C.pooled(null[k])
        ax = sum(r["area"] for r in rows[k]) / ba
        out["|".join(map(str, k))] = dict(bridge=rows[k], dilate=null[k])
        print(f"{k[0]:5.2f} {k[1]:5d} {k[2]:3d} {ax:8.3f} | {mb['cldice']:11.4f} {mb['iou']:7.4f} "
              f"| {mn['cldice']:11.4f} {mn['iou']:7.4f} | {mb['cldice']-mn['cldice']:+14.4f} "
              f"{mb['cldice']-b['cldice']:+11.4f}")
    json.dump(dict(base=base, arms=out), open(os.path.join(C.MY, "bridge.json"), "w"))
    print(f"\nwrote {C.MY}/bridge.json")


if __name__ == "__main__":
    main()
