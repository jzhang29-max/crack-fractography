"""Does averaging the four loss arms help? One pre-declared arm, the rest descriptive.

The four losses disagree per specimen in both directions -- thin4 takes Cast_24hr from
0.5361 to 0.8076 and HIP_24hr from 0.5879 to 0.3386 -- which is the signature of variance,
not of one loss being right. An equal-weight mean of the four probability maps is the
cheapest thing that can reduce it, and it costs no extra training: the maps already exist
and every one of them was produced by a net that never saw the specimen it is predicting.

PRE-DECLARED PRIMARY ARM: the equal-weight mean of ALL FOUR arms, threshold chosen
leave-one-specimen-out. Everything else printed here is descriptive and is NOT the arm
the verdict is read from -- picking the best subset after seeing the table would be
selecting a parameter on the test set, which is the thing this harness exists to prevent.

    python -B scl_ensemble.py --tag main --save ens.json
"""
import os, sys, json, argparse, itertools, warnings
warnings.filterwarnings("ignore")
import numpy as np

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True
import scl_cldice as C   # noqa: E402
import scl_score as SC   # noqa: E402
import tilebench as TB   # noqa: E402

OUT = SC.OUT
LOSSES = ["dice", "cldice", "thin4", "thin8"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="main")
    ap.add_argument("--save", default="")
    a = ap.parse_args()
    tiles = TB.load()
    gs = [C.skel(t["gt"]) for t in tiles]
    specs = sorted({t["specimen"] for t in tiles})
    z = np.load(os.path.join(OUT, "ref_masks.npz"))
    cur = z["cur"].astype(bool)
    P = {L: np.load(os.path.join(OUT, f"prob_{a.tag}_{L}.npy")) for L in LOSSES}
    ref = {k: [C.cl_counts(m, t["gt"], g) for m, t, g in zip(v.astype(bool), tiles, gs)]
           for k, v in (("CURRENT MODEL (v1.49.1)", z["cur"]),
                        ("one-line global threshold", z["thr"]))}
    base_cur = C.per_specimen(ref["CURRENT MODEL (v1.49.1)"], tiles)
    base_thr = C.per_specimen(ref["one-line global threshold"], tiles)

    combos = [("MEAN of all 4 (PRE-DECLARED)", LOSSES)]
    for r in (2, 3):
        for cb in itertools.combinations(LOSSES, r):
            combos.append((f"mean {'+'.join(cb)}", list(cb)))
    print(f"  {'arm':<40}{'prec':>8}{'recall':>8}{'F1':>8}{'IoU':>8}{'clDice':>9}"
          f"{'(mean)':>9}{'(pooled)':>10}  {'vs CURRENT':>22}  {'vs 1-LINE':>22}")
    for k, v in ref.items():
        SC.line(k, C.agg(v))
    res = {}
    for name, cb in combos:
        Pm = np.mean([P[L] for L in cb], 0)
        for mode, b in (("standalone", None), ("additive", cur)):
            grid = SC.counts_grid(Pm, tiles, gs, b)
            ho, tr, picks, tau_all, held = SC.nested(grid, tiles, specs)
            ps = C.per_specimen(held, tiles)
            p1 = C.paired(ps, base_cur, name, "current")
            p2 = C.paired(ps, base_thr, name, "threshold")
            res[f"{name}|{mode}"] = dict(heldout=ho, train_on_all=tr,
                                         gap=tr["cldice"] - ho["cldice"], per_spec=ps,
                                         paired_vs_current=p1, paired_vs_threshold=p2,
                                         taus={k: float(x) for k, x in picks.items()})
            print(f"  {name + ' ' + mode:<40}{ho['precision']:8.4f}{ho['recall']:8.4f}"
                  f"{ho['f1']:8.4f}{ho['iou']:8.4f}{ho['cldice']:9.4f}"
                  f"{ho['cldice_mean']:9.4f}{ho['cldice_pooled']:10.4f}  "
                  f"{p1['median_delta']:+7.4f} {p1['improved']:2d}/{p1['regressed']:2d} "
                  f"p={p1['wilcoxon_p']:.3f}  {p2['median_delta']:+7.4f} "
                  f"{p2['improved']:2d}/{p2['regressed']:2d} p={p2['wilcoxon_p']:.3f}")
    if a.save:
        json.dump(res, open(os.path.join(OUT, a.save), "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
