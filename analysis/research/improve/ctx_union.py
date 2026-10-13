"""THE LAST FAIR TEST FOR CONTEXT, AND THE SHAPE OF THE NULL IT HAS TO BEAT.

Three context formulations have now lost to an isotropic dilation given the same number
of pixels (ctx_matched, ctx_bridge, ctx_orient). ctx_lambda blended the two COST FIELDS
and found the blend monotone in favour of no context at all. One fair test is left: a
blend of the two MASKS, each with its own budget, because a union is not a blended cost
field -- context could be adding exactly the pixels dilation cannot reach even if it is a
worse way to spend the whole budget.

    MIX(beta)   dilation given (1-beta) of the added-pixel budget, UNIONed with context
                growth given beta of it. beta = 0 is pure dilation, beta = 1 is pure
                context, and the total added area is held at alpha x the seed either way.

And the null's own shape, which decides how any future clDice claim here must be read:
dilation is swept out to alpha = 8 to find where pure width stops paying.
"""
import os, sys, json
import numpy as np

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C, ctx_method as M
from ctx_matched import grow_to_area, dilate_to_area

BETAS = (0.0, 0.25, 0.5, 0.75, 1.0)
ALPHAS = (0.5, 1.0, 2.0)
DIL_ALPHAS = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0)


def main():
    ts = C.tiles()
    mix = {(b, a): [] for b in BETAS for a in ALPHAS}
    dil = {a: [] for a in DIL_ALPHAS}
    thr_dil = {a: [] for a in DIL_ALPHAS}
    for i, t in enumerate(ts, 1):
        d = C.prep(t); gt = t["gt"]; seed = d["cur"]; cost = M.cost_field(d["sm"], d["fr"])
        n = int(seed.sum())
        for a in DIL_ALPHAS:
            dil[a].append(C.row(dilate_to_area(seed, int(round(a * n))), gt))
            nt = int(d["thr"].sum())
            thr_dil[a].append(C.row(dilate_to_area(d["thr"], int(round(a * nt))), gt))
        for a in ALPHAS:
            e = int(round(a * n))
            for b in BETAS:
                g, _ = grow_to_area(seed, cost, int(round(b * e)))
                m = g | dilate_to_area(seed, int(round((1 - b) * e)))
                # the union overshoots the budget; trim back to it by dropping the
                # dilation's outermost ring so every beta spends the same area
                over = int(m.sum()) - (n + e)
                if over > 0:
                    from scipy import ndimage as ndi
                    dd = ndi.distance_transform_edt(~seed)
                    cands = np.where(m & ~seed & ~g, dd, -np.inf)
                    v = cands[np.isfinite(cands) & (cands > 0)]
                    if v.size >= over:
                        cut = float(np.partition(v, v.size - over)[v.size - over])
                        m = m & ~((cands >= cut) & ~g)
                mix[(b, a)].append(C.row(m, gt))
        print(f"  [{i:>2}/{len(ts)}] {t['frame'][:44]}", flush=True)

    base = C.pooled(dil[0.0])
    print(f"\nshipped v1.49.1   clDice {base['cldice']:.4f}  IoU {base['iou']:.4f}  "
          f"P {base['precision']:.4f}  R {base['recall']:.4f}")

    print("\nMIX: dilation + context, total added area held fixed   (clDice)")
    print(f"{'beta (share spent on CONTEXT)':<32}" + "".join(f"{'alpha=' + str(a):>12}" for a in ALPHAS))
    for b in BETAS:
        tag = "0.00  pure DILATION" if b == 0 else ("1.00  pure CONTEXT" if b == 1 else f"{b:.2f}")
        print(f"{tag:<32}" + "".join(
            f"{C.pooled(mix[(b, a)])['cldice']:12.4f}" for a in ALPHAS))

    print("\nTHE NULL'S OWN SHAPE -- pure isotropic dilation, no information added at all")
    print(f"{'alpha':>7} {'area x':>8} {'clDice':>9} {'IoU':>8} {'prec':>8} {'recall':>8} "
          f"{'tprec':>7} {'tsens':>7} | {'thr+dil clDice':>15}")
    ba = sum(r["area"] for r in dil[0.0])
    for a in DIL_ALPHAS:
        m = C.pooled(dil[a]); mt = C.pooled(thr_dil[a])
        print(f"{a:7.2f} {sum(r['area'] for r in dil[a])/ba:8.2f} {m['cldice']:9.4f} {m['iou']:8.4f} "
              f"{m['precision']:8.4f} {m['recall']:8.4f} "
              f"{np.median([r['tprec'] for r in dil[a]]):7.4f} "
              f"{np.median([r['tsens'] for r in dil[a]]):7.4f} | {mt['cldice']:15.4f}")
    json.dump(dict(mix={f"{k[0]}|{k[1]}": v for k, v in mix.items()},
                   dil={str(k): v for k, v in dil.items()},
                   thr_dil={str(k): v for k, v in thr_dil.items()}),
              open(os.path.join(C.MY, "union.json"), "w"))


if __name__ == "__main__":
    main()
