"""THE DECISIVE EXPERIMENT: is context worth anything AT MATCHED ADDED AREA?

Any additive operator raises recall, and on labels this wide almost any added area raises
clDice a little. So "context grew the mask and clDice went up" proves nothing. The only
readable comparison holds the added area fixed and asks WHERE the area went:

    CONTEXT   geodesic growth from the shipped mask over the darkness/ridge cost field,
              budget tuned per tile so the mask grows by exactly alpha x its own area.
    DILATE    isotropic binary dilation of the same mask, radius grown until the mask
              grows by the same alpha. This is the geodesic ball on a CONSTANT cost
              field, i.e. the same operator with the context removed.
    EDT       keep the alpha cheapest pixels by their own darkness rank, no connectivity
              at all -- a region-local control at matched area.

Each arm is given the same number of pixels on each tile and we read clDice. If CONTEXT
does not beat DILATE here, spatial context buys nothing on this corpus and no amount of
tuning will change that.
"""
import os, sys, json
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C, ctx_method as M


def grow_to_area(seed, cost, target_extra, lo=0.0, hi=60.0, iters=24):
    """Geodesic growth with the budget bisected so exactly `target_extra` pixels are
    added. Matching area per tile, not pooled, so one easy tile cannot pay for a hard
    one."""
    from skimage.graph import MCP_Geometric
    if target_extra <= 0 or not seed.any():
        return seed.copy(), 0.0
    mcp = MCP_Geometric(cost, fully_connected=True)
    cc, _ = mcp.find_costs(list(zip(*np.nonzero(seed))))
    cc = np.where(np.isfinite(cc), cc, np.inf)
    out = cc[~seed]
    out = out[np.isfinite(out)]
    if out.size == 0:
        return seed.copy(), 0.0
    k = min(int(target_extra), out.size)
    b = float(np.partition(out, k - 1)[k - 1])
    return seed | (cc <= b), b


def dilate_to_area(seed, target_extra):
    """Isotropic growth to the same added area. Fractional radii are reached by taking
    the nearest `target_extra` pixels of the Euclidean distance transform, which is the
    exact area-matched dilation."""
    if target_extra <= 0 or not seed.any():
        return seed.copy()
    d = ndi.distance_transform_edt(~seed)
    out = d[~seed]
    k = min(int(target_extra), out.size)
    if k <= 0:
        return seed.copy()
    thr = float(np.partition(out, k - 1)[k - 1])
    m = seed | ((d <= thr) & ~seed)
    return m


def darkest_to_area(seed, sm, target_extra):
    """Region-local control: just take the darkest unmarked pixels. No connectivity."""
    if target_extra <= 0:
        return seed.copy()
    r = M.rank01(sm).reshape(sm.shape)
    v = r[~seed]
    k = min(int(target_extra), v.size)
    if k <= 0:
        return seed.copy()
    thr = float(np.partition(v, k - 1)[k - 1])
    return seed | ((r <= thr) & ~seed)


ALPHAS = (0.10, 0.25, 0.50, 1.00, 2.00)


def main():
    ts = C.tiles()
    arms = ["CONTEXT geodesic", "DILATE isotropic", "DARKEST region-local"]
    res = {a: {al: [] for al in ALPHAS} for a in arms}
    res["shipped"] = {0.0: []}
    for i, t in enumerate(ts, 1):
        d = C.prep(t); gt = t["gt"]; seed = d["cur"]
        cost = M.cost_field(d["sm"], d["fr"])
        res["shipped"][0.0].append(C.row(seed, gt))
        n = int(seed.sum())
        for al in ALPHAS:
            extra = int(round(al * n))
            g, _ = grow_to_area(seed, cost, extra)
            res["CONTEXT geodesic"][al].append(C.row(g, gt))
            res["DILATE isotropic"][al].append(C.row(dilate_to_area(seed, extra), gt))
            res["DARKEST region-local"][al].append(C.row(darkest_to_area(seed, d["sm"], extra), gt))
        print(f"  [{i:>2}/{len(ts)}] {t['frame'][:44]}", flush=True)

    print(f"\n{'arm':<24} {'alpha':>6} {'area x':>7} {'prec':>7} {'recall':>7} {'IoU':>7} "
          f"{'clDice':>8} {'tprec':>7} {'tsens':>7}")
    print("-" * 92)
    m = C.pooled(res["shipped"][0.0])
    print(f"{'shipped v1.49.1':<24} {'-':>6} {1.0:7.2f} {m['precision']:7.4f} {m['recall']:7.4f} "
          f"{m['iou']:7.4f} {m['cldice']:8.4f} "
          f"{np.median([r['tprec'] for r in res['shipped'][0.0]]):7.4f} "
          f"{np.median([r['tsens'] for r in res['shipped'][0.0]]):7.4f}")
    base_area = sum(r["area"] for r in res["shipped"][0.0])
    for a in arms:
        for al in ALPHAS:
            rows = res[a][al]; m = C.pooled(rows)
            print(f"{a:<24} {al:6.2f} {sum(r['area'] for r in rows)/base_area:7.2f} "
                  f"{m['precision']:7.4f} {m['recall']:7.4f} {m['iou']:7.4f} {m['cldice']:8.4f} "
                  f"{np.median([r['tprec'] for r in rows]):7.4f} "
                  f"{np.median([r['tsens'] for r in rows]):7.4f}")
        print()
    json.dump({a: {str(k): v for k, v in d_.items()} for a, d_ in res.items()},
              open(os.path.join(C.MY, "matched.json"), "w"))


if __name__ == "__main__":
    main()
