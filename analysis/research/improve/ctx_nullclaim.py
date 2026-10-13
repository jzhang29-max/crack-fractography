"""THE ONE CLAIM IN THIS ANGLE THAT SURVIVES ITS OWN TESTS, WITH ITS p-VALUES.

Not a detector. A fact about the instrument the angle was told to optimise:

  ON THESE LABELS clDice IS REACHED BY WIDTH. A single line -- dilate the existing mask
  until it has twice the area -- adds no information of any kind and moves clDice further
  than any method tried on this corpus. Tested here on BOTH seeds, paired across the 13
  specimens, so it is not a property of the shipped detector in particular.

  SKELETON-F1 AT A TOLERANCE DOES NOT HAVE THE FAULT. Same masks, same tiles: the
  dilation moves it by nothing. Its floors are right (mark-everything 0.0000, random
  0.0488) and a correct thin trace scores 1.0000, which clDice also does -- so the
  replacement keeps what clDice got right and drops what it got wrong.

Both halves are stated as paired tests across specimens because a pooled median over 26
tiles is not one: in this same angle the context arm's pooled median beat the dilation
null while losing to it on 8 specimens of 13.
"""
import os, sys, json
import numpy as np
from scipy import stats

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C
from ctx_matched import dilate_to_area
from ctx_metric import skelf1

ALPHAS = (0.5, 1.0, 2.0)


def main():
    tiles = C.tiles()
    specs = sorted({t["specimen"] for t in tiles})
    seeds = ("shipped v1.49.1", "one-line threshold")
    cl = {(s, a): [] for s in seeds for a in (0.0,) + ALPHAS}
    sf = {(s, a): [] for s in seeds for a in (0.0,) + ALPHAS}
    for i, t in enumerate(tiles, 1):
        gt = t["gt"]; d = C.prep(t)
        for s, m0 in zip(seeds, (d["cur"], d["thr"])):
            n = int(m0.sum())
            for a in (0.0,) + ALPHAS:
                m = dilate_to_area(m0, int(round(a * n)))
                cl[(s, a)].append(C.cldice(m, gt))
                sf[(s, a)].append(skelf1(m, gt, 5))
        print(f"  [{i:>2}/{len(tiles)}] {t['frame'][:44]}", flush=True)

    def byspec(v):
        o = {}
        for t, x in zip(tiles, v):
            o.setdefault(t["specimen"], []).append(x)
        return np.array([np.mean(o[s]) for s in specs])

    print(f"\n{'='*100}")
    print("ONE LINE OF CODE, NO INFORMATION: dilate the mask until it has alpha x more area.")
    print(f"{'seed':<22} {'alpha':>6} | {'clDice':>8} {'d vs a=0':>9} {'up':>3} {'dn':>3} "
          f"{'p':>8} | {'skelF1@5':>9} {'d vs a=0':>9} {'up':>3} {'dn':>3} {'p':>8}")
    print("-" * 100)
    rows = []
    for s in seeds:
        b_cl, b_sf = byspec(cl[(s, 0.0)]), byspec(sf[(s, 0.0)])
        print(f"{s:<22} {0.0:6.2f} | {np.median(cl[(s,0.0)]):8.4f} {'':>9} {'':>3} {'':>3} "
              f"{'':>8} | {np.median(sf[(s,0.0)]):9.4f}")
        for a in ALPHAS:
            x_cl, x_sf = byspec(cl[(s, a)]), byspec(sf[(s, a)])
            d1, d2 = x_cl - b_cl, x_sf - b_sf
            p1 = float(stats.wilcoxon(x_cl, b_cl).pvalue) if np.any(d1 != 0) else 1.0
            p2 = float(stats.wilcoxon(x_sf, b_sf).pvalue) if np.any(d2 != 0) else 1.0
            print(f"{'':<22} {a:6.2f} | {np.median(cl[(s,a)]):8.4f} {d1.mean():+9.4f} "
                  f"{int((d1>0).sum()):3d} {int((d1<0).sum()):3d} {p1:8.4f} | "
                  f"{np.median(sf[(s,a)]):9.4f} {d2.mean():+9.4f} {int((d2>0).sum()):3d} "
                  f"{int((d2<0).sum()):3d} {p2:8.4f}")
            rows.append(dict(seed=s, alpha=a, cldice=float(np.median(cl[(s, a)])),
                             d_cldice=float(d1.mean()), p_cldice=p1,
                             up_cldice=int((d1 > 0).sum()), dn_cldice=int((d1 < 0).sum()),
                             skelf1=float(np.median(sf[(s, a)])), d_skelf1=float(d2.mean()),
                             p_skelf1=p2, up_skelf1=int((d2 > 0).sum()),
                             dn_skelf1=int((d2 < 0).sum())))
    print("\nREAD: wherever clDice moves and skelF1 does not, the pixels bought width, not crack.")
    json.dump(rows, open(os.path.join(C.MY, "nullclaim.json"), "w"))


if __name__ == "__main__":
    main()
