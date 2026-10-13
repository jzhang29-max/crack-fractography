"""Is the remaining false-positive budget boundary bleed (fixable by reshaping a
proposal) or whole wrong objects (fixable only by rejecting one)?  And a tightened,
area-matched sabotage control for the >=100 px feature filter."""
import sys
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
import tilebench as TB
import numpy as np
from scipy import ndimage as ndi

tiles = TB.load(with_raw=True)
caches = [A.scale_cache(t["img8"]) for t in tiles]
FL = TB.FLOODED
ship = [A.area_filter(A.clean(A.union_at(c, t["img8"], 5.0, 10), 1, 3, 13), 40)
        for t, c in zip(tiles, caches)]
st = ndi.generate_binary_structure(2, 2)

print("=== how far is each false-positive pixel from the nearest hand-marked crack? ===")
print(f"  {'set':<26} {'FP total':>10} {'<=2px':>10} {'<=5px':>10} {'<=10px':>10} {'>10px':>12}")
for label, idx in (("all 26 tiles", range(len(tiles))),
                   ("25 tiles, void removed", [i for i, t in enumerate(tiles) if t["frame"] != FL])):
    tot = [0, 0, 0, 0, 0]
    for i in idx:
        g, m = tiles[i]["gt"], ship[i]
        fp = m & ~g
        if not fp.any():
            continue
        d = ndi.distance_transform_edt(~g) if g.any() else np.full(g.shape, 1e9)
        v = d[fp]
        tot[0] += v.size
        tot[1] += int((v <= 2).sum()); tot[2] += int((v <= 5).sum())
        tot[3] += int((v <= 10).sum()); tot[4] += int((v > 10).sum())
    print(f"  {label:<26} {tot[0]:>10,} {tot[1]:>10,} {tot[2]:>10,} {tot[3]:>10,} {tot[4]:>12,}"
          f"   ({100*tot[4]/max(tot[0],1):.1f}% are >10 px from any crack)")

print("\n=== TIGHTENED sabotage: remove random regions from the SAME size band (40-99 px) ===")
print("  The real filter removes every region of 40-99 px. If the band carries")
print("  information, removing a random HALF of it must not reproduce the gain.")


def score(masks):
    tp = sum(int((m & t["gt"]).sum()) for m, t in zip(masks, tiles))
    fp = sum(int((m & ~t["gt"]).sum()) for m, t in zip(masks, tiles))
    fn = sum(int((~m & t["gt"]).sum()) for m, t in zip(masks, tiles))
    return tp / max(tp + fp, 1), tp / max(tp + fn, 1)


real = [A.area_filter(m, 100) for m in ship]
p0, r0 = score(ship); p1, r1 = score(real)
print(f"  shipped                         P {p0:.4f} R {r0:.4f}")
print(f"  real filter >=100               P {p1:.4f} R {r1:.4f}   "
      f"dP {p1-p0:+.4f} dR {r1-r0:+.4f}")
rng = np.random.default_rng(7)
for trial in range(3):
    sab = []
    for m in ship:
        lab, n = ndi.label(m)
        if n == 0:
            sab.append(m); continue
        sz = np.bincount(lab.ravel()); sz[0] = 0
        band = np.flatnonzero((sz >= 40) & (sz < 100))
        drop = rng.permutation(band)[:len(band) // 2]
        keep = np.ones(n + 1, bool); keep[0] = False; keep[drop] = False
        sab.append(keep[lab])
    ps, rs = score(sab)
    removed = sum(int((s & ~b).sum()) for s, b in zip(ship, sab))
    print(f"  sabotage half the band, seed {trial}  P {ps:.4f} R {rs:.4f}   "
          f"dP {ps-p0:+.4f} dR {rs-r0:+.4f}   ({removed:,} px removed)")
removed_real = sum(int((s & ~b).sum()) for s, b in zip(ship, real))
print(f"  (the real filter removes {removed_real:,} px)")
