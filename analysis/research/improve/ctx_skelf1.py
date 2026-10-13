"""THE RESULT, UNDER AN INSTRUMENT THAT IS ACTUALLY WIDTH-INSENSITIVE.

Under clDice the answer in this angle is negative and unambiguous: context loses to an
isotropic dilation given the same pixels (ctx_final.py, paired p=0.0171, 10 specimens of
13), and the dilation beats everything (held-out clDice 0.7573) while reading nothing at
all. That is a fact about clDice against these labels, which ctx_metric.py localises:

    clDice has two halves. tprec reads the PREDICTION's skeleton and is width-insensitive
    as advertised. tsens asks whether the LABEL's medial axis is covered, and the label's
    median width at its own centreline is 8.7 px on these tiles -- so a prediction that
    sits a few px off that axis reaches it by getting FATTER and by nothing else. tsens
    is width-SEEKING, and against an 8.7 px brush it is the half that moves.

So this file re-reads the same masks through skeleton-to-skeleton F1 at a tolerance:
match skel(pred) to skel(gt) within tau px in both directions. Thickening the prediction
does not move its skeleton, so the information-free null MUST read flat -- and that is
tested here, with floors, before any arm is ranked by it.

NOTHING IS SELECTED ON THIS INSTRUMENT THAT WAS NOT ALREADY SELECTED ON clDice. The
clDice result stands as the primary answer; this says what it was unable to see.
"""
import os, sys, json
import numpy as np
from scipy import ndimage as ndi
from scipy import stats
from skimage.morphology import skeletonize

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C, ctx_method as M
from ctx_matched import dilate_to_area, grow_to_area
from ctx_metric import skelf1
from ctx_final import loso

TAU = 5
ALPHAS = (0.25, 0.5, 1.0, 2.0)


def mk(pred, gt):
    """A row the LOSO harness can pool. `cld` carries the skeleton F1 so the same
    selector code runs unchanged; clDice travels alongside and is never selected on."""
    r = C.row(pred, gt)
    r["clDice_real"] = r["cld"]
    r["cld"] = skelf1(pred, gt, TAU)
    return r


def main():
    tiles = C.tiles()
    specs = sorted({t["specimen"] for t in tiles})
    rng = np.random.default_rng(0)

    floors = {k: [] for k in ("oracle (gt itself)", "empty", "mark everything",
                              "random, area-matched", "a correct 3 px trace")}
    base, thr = [], []
    ctxv = {a: [] for a in ALPHAS}
    nullv = {a: [] for a in ALPHAS}
    sab = {k: [] for k in ("shuffled labels", "labels rotated 90", "constant input")}

    for i, t in enumerate(tiles, 1):
        gt = t["gt"]; d = C.prep(t); seed = d["cur"]
        cost = M.cost_field(d["sm"], d["fr"])
        base.append(mk(seed, gt)); thr.append(mk(d["thr"], gt))
        rn = np.zeros(gt.size, bool)
        rn[rng.choice(gt.size, int(seed.sum()), replace=False)] = True
        for k, m in (("oracle (gt itself)", gt), ("empty", np.zeros_like(gt)),
                     ("mark everything", np.ones_like(gt)),
                     ("random, area-matched", rn.reshape(gt.shape)),
                     ("a correct 3 px trace", C.correct_trace(gt))):
            floors[k].append(mk(m, gt))
        n = int(seed.sum())
        for a in ALPHAS:
            e = int(round(a * n))
            g, _ = grow_to_area(seed, cost, e)
            ctxv[a].append(mk(g, gt))
            nullv[a].append(mk(dilate_to_area(seed, e), gt))
        e = int(round(1.0 * n))
        g, _ = grow_to_area(seed, cost, e)
        gs = gt.ravel().copy(); rng.shuffle(gs)
        sab["shuffled labels"].append(mk(g, gs.reshape(gt.shape)))
        sab["labels rotated 90"].append(mk(g, np.rot90(gt)))
        cc = M.cost_field(np.zeros_like(d["sm"]) + float(d["sm"].mean()),
                          np.zeros_like(d["fr"]))
        gc, _ = grow_to_area(seed, cc, e)
        sab["constant input"].append(mk(gc, gt))
        print(f"  [{i:>2}/{len(tiles)}] {t['frame'][:44]}", flush=True)

    def M_(rows):
        return float(np.median([r["cld"] for r in rows]))

    def Mc(rows):
        return float(np.median([r["clDice_real"] for r in rows]))

    print(f"\n{'='*92}\nCONTROLS for skeleton F1 @ tau={TAU} px. The instrument is unreadable "
          f"if these are not right.")
    print(f"  {'':<24} {'skelF1':>8} {'clDice':>8}")
    for k in floors:
        print(f"  {k:<24} {M_(floors[k]):8.4f} {Mc(floors[k]):8.4f}")
    ok = (abs(M_(floors["oracle (gt itself)"]) - 1.0) < 1e-9
          and M_(floors["empty"]) == 0.0
          and M_(floors["a correct 3 px trace"]) > 0.98
          and M_(floors["random, area-matched"]) < 0.15
          and M_(floors["mark everything"]) < 0.30)
    print(f"  -> {'PASS' if ok else 'FAIL'}: a correct thin answer scores ~1, and the "
          f"information-free arms score near the floor")

    print(f"\n{'='*92}\nTHE WIDTH NULL UNDER BOTH INSTRUMENTS")
    print(f"  {'arm':<26} {'skelF1':>8} {'clDice':>8}")
    print(f"  {'shipped v1.49.1':<26} {M_(base):8.4f} {Mc(base):8.4f}")
    print(f"  {'one-line threshold':<26} {M_(thr):8.4f} {Mc(thr):8.4f}")
    for a in ALPHAS:
        print(f"  {'  shipped + dilation x' + str(a):<26} {M_(nullv[a]):8.4f} {Mc(nullv[a]):8.4f}")
    for a in ALPHAS:
        print(f"  {'  shipped + CONTEXT x' + str(a):<26} {M_(ctxv[a]):8.4f} {Mc(ctxv[a]):8.4f}")

    r_ctx = loso(f"CONTEXT geodesic, scored by skelF1@{TAU}",
                 {f"alpha={a}": v for a, v in ctxv.items()}, tiles, specs, quiet=True)
    r_null = loso(f"NULL isotropic dilation, scored by skelF1@{TAU}",
                  {f"alpha={a}": v for a, v in nullv.items()}, tiles, specs, quiet=True)
    print(f"\n{'='*92}\nLEAVE-ONE-SPECIMEN-OUT (selected on skelF1@{TAU}; IoU never selected on)")
    print(f"  {'arm':<34} {'fitted':>8} {'HELD-OUT':>9} {'gap':>8}   picks")
    for r in (r_ctx, r_null):
        from collections import Counter
        pk = ", ".join(f"{k} x{v}" for k, v in Counter(r["picks"].values()).most_common())
        print(f"  {r['name'][:33]:<34} {r['fitted']['cldice']:8.4f} "
              f"{r['heldout']['cldice']:9.4f} {r['gap']:+8.4f}   {pk}")
    print(f"  {'shipped v1.49.1 (no parameters)':<34} {M_(base):8.4f} {M_(base):9.4f} "
          f"{0.0:+8.4f}")
    print(f"  {'one-line threshold (no params)':<34} {M_(thr):8.4f} {M_(thr):9.4f} {0.0:+8.4f}")

    print(f"\n{'='*92}\nSABOTAGE (context arm at alpha=1.0, real skelF1 {M_(ctxv[1.0]):.4f})")
    for k, v in sab.items():
        print(f"  {k:<24} skelF1 {M_(v):8.4f}   clDice {Mc(v):8.4f}")

    def byspec(rows):
        o = {}
        for t, r in zip(tiles, rows):
            o.setdefault(t["specimen"], []).append(r["cld"])
        return np.array([np.mean(o[s]) for s in specs])

    print(f"\n{'='*92}\nPAIRED across the 13 specimens, skelF1@{TAU} (Wilcoxon signed-rank)")
    print(f"  {'A':<26} {'vs B':<26} {'mean dA-B':>10} {'A>B':>5} {'A<B':>5} {'p':>9}")
    ca = np.array([r_ctx["byspec"][s] for s in specs])
    na = np.array([r_null["byspec"][s] for s in specs])
    pairs = [("CONTEXT held-out", ca, "one-line threshold", byspec(thr)),
             ("CONTEXT held-out", ca, "shipped v1.49.1", byspec(base)),
             ("CONTEXT held-out", ca, "NULL dilation held-out", na),
             ("NULL dilation held-out", na, "one-line threshold", byspec(thr)),
             ("NULL dilation held-out", na, "shipped v1.49.1", byspec(base))]
    outp = []
    for nm_a, a, nm_b, b in pairs:
        dd = a - b
        p = float(stats.wilcoxon(a, b).pvalue) if np.any(dd != 0) else 1.0
        print(f"  {nm_a:<26} {nm_b:<26} {dd.mean():+10.4f} {int((dd>0).sum()):5d} "
              f"{int((dd<0).sum()):5d} {p:9.4f}")
        outp.append(dict(a=nm_a, b=nm_b, mean_delta=float(dd.mean()),
                         up=int((dd > 0).sum()), down=int((dd < 0).sum()), p=p))

    json.dump(dict(tau=TAU, floors={k: C.pooled(v) for k, v in floors.items()},
                   base=base, thr=thr, ctx=r_ctx, null=r_null, pairs=outp, specs=specs,
                   ctx_rows={str(k): v for k, v in ctxv.items()},
                   null_rows={str(k): v for k, v in nullv.items()},
                   sab={k: M_(v) for k, v in sab.items()}),
              open(os.path.join(C.MY, "skelf1.json"), "w"), default=float)
    print(f"\nwrote {C.MY}/skelf1.json")


if __name__ == "__main__":
    main()
