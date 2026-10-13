"""Q4 -- CALIBRATE THE BAR AGAINST CHANGES THIS PROJECT ALREADY ACCEPTED.

Q3 says what size of gain n = 13 can resolve. That number is abstract until it is held
against the two changes this repo already shipped on the strength of these same tiles:

    v1.47   the archived detector: single-scale darkness cut + region classifier
    v1.48   USE_REGION_CLASSIFIER = False                     (accepted, +0.0836 IoU)
    v1.49.1 + the seven-radius multi-scale union              (accepted, +0.0365 IoU)

If those two -- the largest improvements anyone has made here -- do not themselves clear a
paired test at n = 13, then the bar this workflow is being asked to clear is higher than
the bar the shipped product cleared, and that has to be said out loud.

Also answers two questions that decide how any of today's arms should be read:
  * do IoU and clDice even RANK methods the same way here? (Spearman over every variant)
  * how much of each score is the 0 px exactness nobody believes? (2 px tolerant clDice)
"""
import os, sys, json
import numpy as np
from scipy import ndimage as ndi, stats
from skimage import filters
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import approach4_lib as L
import approach4_q3_power as Q3
import crackpipe as CP
import detect_cracks as D


def tol_cldice(pred, gt, sgt, tol=2):
    """clDice with a `tol` px tolerance on BOTH memberships: a centreline pixel counts as
    hit if the other mask is within tol px. Same tolerance convention as tilebench.counts."""
    st = ndi.generate_binary_structure(2, 2)
    pred = np.asarray(pred, bool)
    if pred.sum() == 0 or pred.mean() > 0.25:
        return 0.0
    gd = ndi.binary_dilation(gt, st, iterations=tol)
    pd = ndi.binary_dilation(pred, st, iterations=tol)
    sp = L.skel(pred)
    tp = (sp & gd).sum() / max(sp.sum(), 1)
    ts = (sgt & pd).sum() / max(sgt.sum(), 1)
    return float(2 * tp * ts / max(tp + ts, 1e-12))


def main():
    tiles = L.tiles_with_arms()
    specs = sorted({t["specimen"] for t in tiles})

    # ------------------------------------------------------- the three shipped versions
    print("THE THREE VERSIONS, scored through one instrument")
    vers = {}
    v147, v148 = [], []
    for t in tiles:
        st = CP.stages(t["img8"])            # shipped single-scale candidate stage
        v148.append(st["labeled"] > 0)       # classifier off
        v147.append(CP.probability(st) >= CP.THR)
    vers["v1.47 shipped (classifier ON)"] = v147
    vers["v1.48 (classifier OFF)"] = v148
    vers["v1.49.1 (+ multi-scale union)"] = [t["arms"]["current"] for t in tiles]

    rows = {k: [L.score_tile(m, t["gt"], sgt=t["skel_gt"]) for m, t in zip(v, tiles)]
            for k, v in vers.items()}
    print(f"  {'version':<34}{'prec':>8}{'recall':>8}{'IoU':>8}{'clDice':>9}{'Tsens':>8}{'Tprec':>8}")
    for k, r in rows.items():
        m = L.pool(r)
        print(f"  {k:<34}{m['precision']:8.4f}{m['recall']:8.4f}{m['iou']:8.4f}"
              f"{m['cldice_mean']:9.4f}{m['tsens_mean']:8.4f}{m['tprec_mean']:8.4f}")

    sv_cl = {k: Q3.per_specimen(tiles, r, "cldice")[1] for k, r in rows.items()}
    sv_io = {}
    for k, r in rows.items():
        v = []
        for sp in specs:
            idx = [i for i, t in enumerate(tiles) if t["specimen"] == sp]
            tp = sum(r[i]["tp"] for i in idx); fp = sum(r[i]["fp"] for i in idx)
            fn = sum(r[i]["fn"] for i in idx)
            v.append(tp / max(tp + fp + fn, 1))
        sv_io[k] = np.array(v)

    print("\nDID THE CHANGES THIS REPO ALREADY ACCEPTED CLEAR A PAIRED TEST AT n = 13?")
    ks = list(vers)
    tests = {}
    for metric, sv in (("clDice", sv_cl), ("IoU", sv_io)):
        for a, b in ((ks[1], ks[0]), (ks[2], ks[1]), (ks[2], ks[0])):
            d = sv[a] - sv[b]
            try:
                p = stats.wilcoxon(sv[a], sv[b], zero_method="wilcox", method="exact").pvalue
            except Exception:
                p = float("nan")
            rng = np.random.default_rng(5)
            bs = np.array([d[rng.integers(0, 13, 13)].mean() for _ in range(20000)])
            lo, hi = np.percentile(bs, [2.5, 97.5])
            tests[f"{metric}: {a} - {b}"] = dict(mean=float(d.mean()), p=float(p),
                                                 ci=[float(lo), float(hi)],
                                                 better=int((d > 0).sum()), worse=int((d < 0).sum()))
            print(f"  {metric:>7}  {a.split('(')[0].strip():<22} - {b.split('(')[0].strip():<22}"
                  f" {d.mean():+.4f}  CI [{lo:+.4f},{hi:+.4f}]  {int((d>0).sum())}/{int((d<0).sum())} "
                  f"better/worse  Wilcoxon p {p:.4f}"
                  f"{'  SIGNIFICANT' if p < 0.05 else '  not significant'}")

    # ------------------------------------------------------- do the metrics agree at all?
    print("\nDO IoU AND clDice RANK METHODS THE SAME WAY? every variant built today")
    allv = {}
    for k in tiles[0]["arms"]:
        if k in ("empty",):
            continue
        allv[k] = [L.score_tile(t["arms"][k], t["gt"], sgt=t["skel_gt"]) for t in tiles]
    for mk in Q3.MAD_GRID:
        masks = []
        for t in tiles:
            sm = filters.gaussian(t["flat40"], sigma=1, preserve_range=True)
            med = np.median(sm); mad = np.median(np.abs(sm - med)) * 1.4826
            masks.append(Q3.region40((sm < min(filters.threshold_otsu(sm), med - mk * mad))
                                     | (t["img8"] < L.ABSOLUTE_DARK)))
        allv["mad_%.1f" % mk] = [L.score_tile(m, t["gt"], sgt=t["skel_gt"])
                                 for m, t in zip(masks, tiles)]
    for q in (0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10):
        masks = [Q3.region40(t["flat40"] <= np.quantile(t["flat40"], q)) for t in tiles]
        allv["quantile_%.2f" % q] = [L.score_tile(m, t["gt"], sgt=t["skel_gt"])
                                     for m, t in zip(masks, tiles)]
    for k, v in vers.items():
        allv[k] = rows[k]
    pooled = {k: L.pool(r) for k, r in allv.items()}
    names = [k for k in pooled if k not in ("markall", "random")]
    io = np.array([pooled[k]["iou"] for k in names])
    cl = np.array([pooled[k]["cldice_mean"] for k in names])
    rho = stats.spearmanr(io, cl)
    print(f"  {len(names)} variants.  Spearman(IoU, clDice) = {rho.statistic:+.3f}  "
          f"(p {rho.pvalue:.3g})")
    bi = names[int(np.argmax(io))]; bc = names[int(np.argmax(cl))]
    print(f"  best by IoU    : {bi:<32} IoU {pooled[bi]['iou']:.4f}  clDice {pooled[bi]['cldice_mean']:.4f}")
    print(f"  best by clDice : {bc:<32} IoU {pooled[bc]['iou']:.4f}  clDice {pooled[bc]['cldice_mean']:.4f}")
    print("  top 6 by IoU, with where clDice puts them:")
    order_cl = {k: i for i, k in enumerate(sorted(names, key=lambda k: -pooled[k]["cldice_mean"]), 1)}
    for i, k in enumerate(sorted(names, key=lambda k: -pooled[k]["iou"])[:6], 1):
        print(f"    IoU rank {i}  {k:<30} IoU {pooled[k]['iou']:.4f}   "
              f"clDice {pooled[k]['cldice_mean']:.4f} (clDice rank {order_cl[k]})")

    # ------------------------------------------------------- tolerance
    print("\nHOW MUCH OF THE SCORE IS 0 px EXACTNESS? clDice at a 2 px tolerance")
    print(f"  {'arm':<34}{'clDice 0 px':>13}{'clDice 2 px':>13}{'gain':>8}")
    for k in ("v1.47 shipped (classifier ON)", "v1.48 (classifier OFF)",
              "v1.49.1 (+ multi-scale union)", "mad_3.5", "quantile_0.04", "trace3"):
        m0 = L.pool(allv[k])["cldice_mean"]
        masks = (vers[k] if k in vers else None)
        if masks is None:
            if k == "trace3":
                masks = [t["arms"]["trace3"] for t in tiles]
            elif k.startswith("mad_"):
                mk = float(k.split("_")[1]); masks = []
                for t in tiles:
                    sm = filters.gaussian(t["flat40"], sigma=1, preserve_range=True)
                    med = np.median(sm); mad = np.median(np.abs(sm - med)) * 1.4826
                    masks.append(Q3.region40((sm < min(filters.threshold_otsu(sm), med - mk * mad))
                                             | (t["img8"] < L.ABSOLUTE_DARK)))
            else:
                q = float(k.split("_")[1])
                masks = [Q3.region40(t["flat40"] <= np.quantile(t["flat40"], q)) for t in tiles]
        m2 = float(np.mean([tol_cldice(m, t["gt"], t["skel_gt"]) for m, t in zip(masks, tiles)]))
        print(f"  {k:<34}{m0:13.4f}{m2:13.4f}{m2 - m0:+8.4f}")

    json.dump(dict(tests=tests, spearman=float(rho.statistic),
                   pooled={k: {m: float(v[m]) for m in ("iou", "cldice_mean", "precision", "recall")}
                           for k, v in pooled.items()}),
              open(os.path.join(L.WORK, "q4_yardstick.json"), "w"), indent=1)
    print("\nwrote", os.path.join(L.WORK, "q4_yardstick.json"))


if __name__ == "__main__":
    main()
