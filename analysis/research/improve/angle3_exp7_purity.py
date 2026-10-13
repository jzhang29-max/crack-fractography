"""Can an ADDITIVE change raise precision at all?

Arithmetic: a strict superset raises precision iff the pixels it adds are purer than the
operating point it adds them to. So measure the purity of every candidate addition, and
of every candidate removal, against the 0.4182 pooled / 0.7840 off-void bar it must beat.
Plus the sabotage control for the one knob that survives the paint gate.
"""
import sys
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
import tilebench as TB
import numpy as np
from scipy import ndimage as ndi

tiles = TB.load(with_raw=True)
caches = [A.scale_cache(t["img8"]) for t in tiles]
FL = TB.FLOODED
k25 = [i for i, t in enumerate(tiles) if t["frame"] != FL]


def build(mk=5.0, absd=10, op=1, cl=3, ma=13, af=40):
    return [A.area_filter(A.clean(A.union_at(c, t["img8"], mk, absd), op, cl, ma), af)
            for t, c in zip(tiles, caches)]


ship = build()
gt = [t["gt"] for t in tiles]
tp = sum(int((m & g).sum()) for m, g in zip(ship, gt))
fp = sum(int((m & ~g).sum()) for m, g in zip(ship, gt))
tp25 = sum(int((ship[i] & gt[i]).sum()) for i in k25)
fp25 = sum(int((ship[i] & ~gt[i]).sum()) for i in k25)
print(f"SHIPPED operating purity   pooled {tp/(tp+fp):.4f} (26 tiles)   "
      f"{tp25/(tp25+fp25):.4f} (25 tiles, void removed)")
print("An addition raises pooled precision only if its own purity exceeds the first "
      "number,\nand raises the off-void precision only if it exceeds the second.\n")


def delta(name, other):
    ac = sum(int((o & ~s & g).sum()) for o, s, g in zip(other, ship, gt))
    af_ = sum(int((o & ~s & ~g).sum()) for o, s, g in zip(other, ship, gt))
    rc = sum(int((s & ~o & g).sum()) for o, s, g in zip(other, ship, gt))
    rf = sum(int((s & ~o & ~g).sum()) for o, s, g in zip(other, ship, gt))
    ntp, nfp = tp + ac - rc, fp + af_ - rf
    kind = ("strict SUPERSET" if rc + rf == 0 else
            "strict SUBSET" if ac + af_ == 0 else "NEITHER")
    print(f"  {name:<34} {kind:<16} P {ntp/max(ntp+nfp,1):.4f}  "
          f"R {ntp/max(tp+sum(int((~s & g).sum()) for s, g in zip(ship, gt)),1):.4f}")
    if ac + af_:
        print(f"      adds    {ac+af_:>9,} px at purity {ac/max(ac+af_,1):.4f}"
              f"   ({ac:,} crack / {af_:,} not)")
    if rc + rf:
        print(f"      removes {rc+rf:>9,} px at purity {rc/max(rc+rf,1):.4f}"
              f"   ({rc:,} crack / {rf:,} not)")


print("=== ADDITIVE arms (strict supersets) ===")
delta("feature filter 40 -> 13", build(af=13))
delta("feature filter 40 -> 1", build(af=1))
delta("mad_k 5.0 -> 4.0", build(mk=4.0))
delta("mad_k 5.0 -> 3.0", build(mk=3.0))
delta("close_radius 3 -> 5", build(cl=5))
delta("open_radius 1 -> 0", build(op=0))

print("\n=== SUBTRACTIVE arms ===")
delta("feature filter 40 -> 100", build(af=100))
delta("feature filter 40 -> 300", build(af=300))
delta("open_radius 1 -> 2", build(op=2))
delta("absolute term OFF", build(absd=0))

print("\n=== SABOTAGE control for the feature filter ===")
print("  If '>=100 px' carries information, removing a RANDOM set of regions of the same")
print("  total area must not reproduce its precision gain.")
rng = np.random.default_rng(0)
real = build(af=100)
removed_area = sum(int((s & ~r).sum()) for s, r in zip(ship, real))
for trial in range(3):
    sab = []
    for s, r in zip(ship, real):
        lab, n = ndi.label(s)
        if n == 0:
            sab.append(s); continue
        sz = np.bincount(lab.ravel()); sz[0] = 0
        target = int((s & ~r).sum())
        idx = rng.permutation(np.arange(1, n + 1))
        drop, acc = [], 0
        for l in idx:
            if acc >= target:
                break
            drop.append(l); acc += sz[l]
        keep = np.ones(n + 1, bool); keep[0] = False
        keep[drop] = False
        sab.append(keep[lab])
    delta(f"sabotage: random regions, trial {trial}", sab)
print(f"  (real filter removes {removed_area:,} px in total)")
