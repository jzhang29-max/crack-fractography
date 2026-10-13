"""DOES THE SHIPPED PIPELINE REALLY TIE A SINGLE LINE OF CODE?

The brief's first fact is that it does: 0.0012 IoU separates them, 0.0200 clDice. Both
of those instruments were just shown to be width contests against an 8.7 px brush --
IoU by the brief's own correct-trace row, clDice by ctx_nullclaim.py, where one line of
dilation moves it +0.065 on 12 specimens of 13 at p=0.0007 while adding nothing.

So re-run the comparison the brief makes, on the same 26 tiles and the same two masks,
under the instrument whose null reads flat. Paired across the 13 specimens, because that
is what the brief requires of a claim and a pooled median is not one.
"""
import os, sys, json
import numpy as np
from scipy import stats

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C
from ctx_metric import skelf1

TAUS = (2, 3, 5, 10)


def main():
    tiles = C.tiles()
    specs = sorted({t["specimen"] for t in tiles})
    cur = {k: [] for k in ("clDice", "IoU") + tuple(f"skelF1@{t}" for t in TAUS)}
    thr = {k: [] for k in cur}
    for i, t in enumerate(tiles, 1):
        gt = t["gt"]; d = C.prep(t)
        for acc, m in ((cur, d["cur"]), (thr, d["thr"])):
            r = C.row(m, gt)
            acc["clDice"].append(r["cld"])
            acc["IoU"].append(r["tp"] / max(r["tp"] + r["fp"] + r["fn"], 1))
            for ta in TAUS:
                acc[f"skelF1@{ta}"].append(skelf1(m, gt, ta))
        print(f"  [{i:>2}/{len(tiles)}] {t['frame'][:44]}", flush=True)

    def byspec(v):
        o = {}
        for t, x in zip(tiles, v):
            o.setdefault(t["specimen"], []).append(x)
        return np.array([np.mean(o[s]) for s in specs])

    print(f"\n{'='*94}")
    print("SHIPPED v1.49.1  vs  ONE-LINE GLOBAL THRESHOLD, 26 tiles, paired over 13 specimens")
    print(f"{'instrument':<14} {'shipped':>9} {'one-line':>9} {'median d':>9} | "
          f"{'paired d':>9} {'ship>thr':>9} {'ship<thr':>9} {'p':>8}")
    print("-" * 94)
    out = []
    for k in cur:
        a, b = byspec(cur[k]), byspec(thr[k])
        d = a - b
        p = float(stats.wilcoxon(a, b).pvalue) if np.any(d != 0) else 1.0
        print(f"{k:<14} {np.median(cur[k]):9.4f} {np.median(thr[k]):9.4f} "
              f"{np.median(cur[k])-np.median(thr[k]):+9.4f} | {d.mean():+9.4f} "
              f"{int((d>0).sum()):9d} {int((d<0).sum()):9d} {p:8.4f}")
        out.append(dict(instrument=k, shipped=float(np.median(cur[k])),
                        threshold=float(np.median(thr[k])), paired=float(d.mean()),
                        up=int((d > 0).sum()), down=int((d < 0).sum()), p=p))
    json.dump(out, open(os.path.join(C.MY, "tiecheck.json"), "w"))


if __name__ == "__main__":
    main()
