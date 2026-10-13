"""IS CONTEXT WORTH ANYTHING ON TOP OF ISOTROPIC GROWTH? A nested family settles it.

ctx_matched.py's answer was negative and sharp: at every matched added area, plain
dilation beat geodesic growth over the darkness/ridge cost field on clDice (e.g. at
alpha=1.0, 0.7601 vs 0.7025). The decomposition says why. Context wins the half of
clDice it was built for and loses the other half:

        alpha=1.0        tprec    tsens   clDice
        CONTEXT         0.6184   0.9404   0.7025
        DILATE          0.7999   0.9209   0.7601

Context covers MORE of the label's centreline. It pays for it by running tendrils down
dark structure the human never painted, and each tendril is new skeleton outside the
label, which is what tprec counts.

So the question is not context-or-dilation, it is whether any mixture beats the ends.
Make the cost field a convex blend

        cost = lam * 1  +  (1 - lam) * context_cost

lam = 1 is a constant cost field, whose geodesic ball IS the Euclidean dilation -- the
winning control is now literally a member of the family. lam = 0 is pure context. Every
arm is matched to the same added area per tile, so lam only decides WHERE the pixels go.

If the best lam is 1.0 under leave-one-specimen-out, spatial context buys nothing here
and the honest answer is a negative result.
"""
import os, sys, json, itertools
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C, ctx_method as M
from ctx_matched import grow_to_area

LAMS = (0.0, 0.25, 0.5, 0.75, 0.9, 1.0)
ALPHAS = (0.25, 0.5, 1.0, 2.0)


def arm_mask(seed, ctxcost, lam, extra):
    cost = lam * np.ones_like(ctxcost) + (1.0 - lam) * ctxcost
    m, _ = grow_to_area(seed, cost, extra)
    return m


def main():
    ts = C.tiles()
    keys = list(itertools.product(LAMS, ALPHAS))
    rows = {k: [] for k in keys}
    base = []
    for i, t in enumerate(ts, 1):
        d = C.prep(t); gt = t["gt"]; seed = d["cur"]
        ctxcost = M.cost_field(d["sm"], d["fr"])
        base.append(C.row(seed, gt))
        n = int(seed.sum())
        for lam, al in keys:
            rows[(lam, al)].append(C.row(arm_mask(seed, ctxcost, lam, int(round(al * n))), gt))
        print(f"  [{i:>2}/{len(ts)}] {t['frame'][:44]}", flush=True)

    m = C.pooled(base)
    print(f"\nshipped v1.49.1   clDice {m['cldice']:.4f}  IoU {m['iou']:.4f}  "
          f"P {m['precision']:.4f} R {m['recall']:.4f}")
    print(f"\n{'':>6}" + "".join(f"{'alpha=' + str(a):>12}" for a in ALPHAS)
          + "      (clDice, pooled over all 26 tiles)")
    for lam in LAMS:
        tag = "lam=1 DIL" if lam == 1.0 else ("lam=0 CTX" if lam == 0.0 else f"lam={lam}")
        print(f"{tag:>10}" + "".join(f"{C.pooled(rows[(lam, a)])['cldice']:12.4f}" for a in ALPHAS))
    print(f"\n{'':>10}" + "".join(f"{'a=' + str(a):>12}" for a in ALPHAS) + "   (tprec / tsens medians)")
    for lam in LAMS:
        print(f"{lam:>10}" + "".join(
            f"{np.median([r['tprec'] for r in rows[(lam, a)]]):6.3f}/"
            f"{np.median([r['tsens'] for r in rows[(lam, a)]]):5.3f}" for a in ALPHAS))

    json.dump({f"{k[0]}|{k[1]}": v for k, v in rows.items()},
              open(os.path.join(C.MY, "lambda.json"), "w"))
    json.dump(base, open(os.path.join(C.MY, "base.json"), "w"))
    print(f"\nwrote {C.MY}/lambda.json")


if __name__ == "__main__":
    main()
