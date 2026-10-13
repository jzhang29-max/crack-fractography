"""APPROACH 3, FINAL SCORE: leave-one-specimen-out, paired across the 13 specimens,
sabotaged, and priced against the control that reads nothing.

Selection rule, mirroring tilebench: for each specimen, pick the variant with the best
MEDIAN clDice on the OTHER twelve specimens' tiles, score it on the held-out tiles, pool
every held-out row and take the median. Train-on-all is reported beside it and the gap
between them is the overfit. clDice is the criterion everywhere; IoU is reported and
never selected on.

Three families, each asked the same question:

  CONTEXT       geodesic growth over the darkness/ridge cost field. The method the angle
                is about. Parameters: added-area multiple alpha.
  NESTED        the same operator over a cost field blended lam towards a CONSTANT, so
                lam=1 is the Euclidean dilation and the control is a MEMBER of the family
                that leave-one-specimen-out is free to pick.
  NULL          isotropic dilation, matched per tile to the context arm's own added area.
                No information. This is the number any context claim has to clear.

SABOTAGE: shuffled labels, labels rotated 90 degrees, and a constant input image. A
method that still scores well with these is not reading the data.
"""
import os, sys, json, itertools
import numpy as np
from scipy import ndimage as ndi
from scipy import stats

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C, ctx_method as M
from ctx_matched import grow_to_area, dilate_to_area

ALPHAS = (0.25, 0.5, 1.0, 2.0)
LAMS = (0.0, 0.25, 0.5, 0.75, 0.9, 1.0)


def med(rows):
    return float(np.median([r["cld"] for r in rows]))


def loso(name, variants, tiles, specs, quiet=False):
    """variants: {key: [row per tile]}. Returns held-out pooled rows, fitted, picks."""
    keys = list(variants)
    fitted_key = max(keys, key=lambda k: med(variants[k]))
    held, picks, byspec = [], {}, {}
    for sp in specs:
        tr = [i for i, t in enumerate(tiles) if t["specimen"] != sp]
        te = [i for i, t in enumerate(tiles) if t["specimen"] == sp]
        best = max(keys, key=lambda k: med([variants[k][i] for i in tr]))
        picks[sp] = best
        rows = [variants[best][i] for i in te]
        byspec[sp] = float(np.mean([r["cld"] for r in rows]))
        held.extend(rows)
    r = dict(name=name, fitted_key=str(fitted_key), fitted=C.pooled(variants[fitted_key]),
             heldout=C.pooled(held), picks={k: str(v) for k, v in picks.items()},
             byspec=byspec, n_variants=len(keys))
    r["gap"] = r["fitted"]["cldice"] - r["heldout"]["cldice"]
    if not quiet:
        h, f = r["heldout"], r["fitted"]
        print(f"\n=== {name}  ({len(keys)} variant(s), {len(tiles)} tiles, {len(specs)} specimens, "
              f"selected on clDice) ===")
        print(f"  {'':<22} {'clDice':>8} {'IoU':>8} {'prec':>8} {'recall':>8} {'F1':>8}")
        for lab, m in [("FITTED (optimistic)", f), ("HELD-OUT (quote this)", h)]:
            print(f"  {lab:<22} {m['cldice']:8.4f} {m['iou']:8.4f} {m['precision']:8.4f} "
                  f"{m['recall']:8.4f} {m['f1']:8.4f}")
        print(f"  overfit gap on clDice: {r['gap']:+.4f}    fitted pick: {r['fitted_key']}")
        if len(keys) > 1:
            from collections import Counter
            print("  held-out picks: " + ", ".join(f"{k} x{v}" for k, v in
                                                   Counter(r["picks"].values()).most_common()))
    return r


def main():
    tiles = C.tiles()
    specs = sorted({t["specimen"] for t in tiles})
    rng = np.random.default_rng(0)

    base, thr = [], []
    ctxv = {a: [] for a in ALPHAS}
    nest = {(l, a): [] for l in LAMS for a in ALPHAS}
    nullv = {a: [] for a in ALPHAS}
    sab = {k: [] for k in ("shuffled labels", "labels rotated 90", "constant input")}

    for i, t in enumerate(tiles, 1):
        d = C.prep(t); gt = t["gt"]; seed = d["cur"]
        cost = M.cost_field(d["sm"], d["fr"])
        base.append(C.row(seed, gt)); thr.append(C.row(d["thr"], gt))
        n = int(seed.sum())
        for a in ALPHAS:
            e = int(round(a * n))
            g, _ = grow_to_area(seed, cost, e)
            ctxv[a].append(C.row(g, gt))
            nullv[a].append(C.row(dilate_to_area(seed, e), gt))
            for l in LAMS:
                cb = l * np.ones_like(cost) + (1 - l) * cost
                m, _ = grow_to_area(seed, cb, e)
                nest[(l, a)].append(C.row(m, gt))
        # --- sabotage, at the single alpha the method would ship at (1.0)
        e = int(round(1.0 * n))
        gs = gt.ravel().copy(); rng.shuffle(gs); gshuf = gs.reshape(gt.shape)
        g, _ = grow_to_area(seed, cost, e)
        sab["shuffled labels"].append(C.row(g, gshuf))
        sab["labels rotated 90"].append(C.row(g, np.rot90(gt)))
        flatc = np.zeros_like(d["sm"]) + float(d["sm"].mean())
        cc = M.cost_field(flatc, np.zeros_like(d["fr"]))
        gc, _ = grow_to_area(seed, cc, e)
        sab["constant input"].append(C.row(gc, gt))
        print(f"  [{i:>2}/{len(tiles)}] {t['frame'][:44]}", flush=True)

    print("\n" + "=" * 96)
    print("REFERENCE ROWS (parameter-free, so held-out == fitted by construction)")
    for nm, rows in [("shipped v1.49.1", base), ("one-line global threshold", thr)]:
        m = C.pooled(rows)
        print(f"  {nm:<28} clDice {m['cldice']:.4f}  IoU {m['iou']:.4f}  "
              f"P {m['precision']:.4f}  R {m['recall']:.4f}")

    r_ctx = loso("CONTEXT geodesic (the method)", {f"alpha={a}": v for a, v in ctxv.items()},
                 tiles, specs)
    r_nest = loso("NESTED family (dilation is lam=1, a member)",
                  {f"lam={l},alpha={a}": v for (l, a), v in nest.items()}, tiles, specs)
    r_null = loso("NULL isotropic dilation (reads nothing)",
                  {f"alpha={a}": v for a, v in nullv.items()}, tiles, specs)

    print("\n" + "=" * 96)
    print("SABOTAGE (context arm at alpha=1.0; the real score is clDice 0.7025 fitted)")
    for k, rows in sab.items():
        m = C.pooled(rows)
        print(f"  {k:<24} clDice {m['cldice']:.4f}   IoU {m['iou']:.4f}")

    print("\n" + "=" * 96)
    print("PAIRED TESTS across the 13 specimens (mean clDice per specimen, Wilcoxon signed-rank)")

    def byspec(rows):
        o = {}
        for t, r in zip(tiles, rows):
            o.setdefault(t["specimen"], []).append(r["cld"])
        return np.array([np.mean(o[s]) for s in specs])

    pairs = [("CONTEXT held-out", np.array([r_ctx["byspec"][s] for s in specs]),
              "one-line threshold", byspec(thr)),
             ("CONTEXT held-out", np.array([r_ctx["byspec"][s] for s in specs]),
              "shipped v1.49.1", byspec(base)),
             ("CONTEXT held-out", np.array([r_ctx["byspec"][s] for s in specs]),
              "NULL dilation held-out", np.array([r_null["byspec"][s] for s in specs])),
             ("NULL dilation held-out", np.array([r_null["byspec"][s] for s in specs]),
              "one-line threshold", byspec(thr))]
    out_pairs = []
    print(f"  {'A':<26} {'vs B':<26} {'mean dA-B':>10} {'A>B':>5} {'A<B':>5} {'p':>9}")
    for na, a, nb, b in pairs:
        d = a - b
        p = float(stats.wilcoxon(a, b).pvalue) if np.any(d != 0) else 1.0
        print(f"  {na:<26} {nb:<26} {d.mean():+10.4f} {int((d>0).sum()):5d} "
              f"{int((d<0).sum()):5d} {p:9.4f}")
        out_pairs.append(dict(a=na, b=nb, mean_delta=float(d.mean()),
                              up=int((d > 0).sum()), down=int((d < 0).sum()), p=p))

    json.dump(dict(base=base, thr=thr, ctx=r_ctx, nest=r_nest, null=r_null,
                   sab={k: C.pooled(v) for k, v in sab.items()}, pairs=out_pairs,
                   specs=specs,
                   ctx_byspec={s: r_ctx["byspec"][s] for s in specs},
                   null_byspec={s: r_null["byspec"][s] for s in specs},
                   thr_byspec=dict(zip(specs, byspec(thr).tolist())),
                   base_byspec=dict(zip(specs, byspec(base).tolist()))),
              open(os.path.join(C.MY, "final.json"), "w"), default=float)
    print(f"\nwrote {C.MY}/final.json")


if __name__ == "__main__":
    main()
