"""Final check on the one arm worth shipping: delete the classifier, add a texture veto.

Zero free parameters. Before believing it, break it on purpose: a check that passes on a
sabotaged method measured nothing. Also report what it looks like WITHOUT the one
pathological tile, because a pooled number carried by a single catastrophic failure is
not a description of normal behaviour.
"""
import sys
import numpy as np
from scipy import ndimage as ndi
from scipy import stats
from skimage import filters

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research")
sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP
import detect_cracks as D


def local_std(a, r=16):
    a = np.asarray(a, np.float32)
    m = ndi.uniform_filter(a, 2 * r + 1); m2 = ndi.uniform_filter(a * a, 2 * r + 1)
    return np.sqrt(np.maximum(m2 - m * m, 0)).astype(np.float32)


def predict(img8, mad_k=5.0, floor=1.0, veto_radius=16, _std_src="flat"):
    st = CP.stages(img8, mad_k=mad_k)
    mask = st["clean"]
    if floor <= 0:
        return mask
    s = local_std(st["flat"] if _std_src == "flat" else np.zeros_like(st["flat"]), veto_radius)
    base = max(float(np.median(s)), 1e-6)
    lab, n = ndi.label(mask)
    if n == 0:
        return mask
    keep = np.zeros(n + 1, bool)
    for i in range(1, n + 1):
        keep[i] = (float(np.median(s[lab == i])) / base) >= floor
    return keep[lab]


tiles = TB.load()
print("CONTROLS"); assert TB.controls()
print()
ship = [CP.predict(t["img8"]) for t in tiles]
win = [predict(t["img8"]) for t in tiles]
rs, rw = [TB.counts(m, t["gt"]) for m, t in zip(ship, tiles)], [TB.counts(m, t["gt"]) for m, t in zip(win, tiles)]
TB.evaluate("WINNER: classifier deleted + texture veto [0 free parameters]", {"x": rw})

print("\nSABOTAGE -- each must collapse or the score was not coming from the method")
sab = {
  "veto reads a constant image (no texture info)":
      [predict(t["img8"], _std_src="zero") for t in tiles],
  "scored against another tile's labels":
      None,
  "random mask at matched pixel count": None,
}
rows = [TB.counts(m, t["gt"]) for m, t in zip(sab["veto reads a constant image (no texture info)"], tiles)]
print(f"  constant-texture veto   IoU {TB._agg(rows)['iou']:.4f}   (vetoes everything -> must be ~0)")
rot = [TB.counts(m, np.rot90(t["gt"], 2)) for m, t in zip(win, tiles)]
print(f"  labels rotated 180      IoU {TB._agg(rot)['iou']:.4f}")
rng = np.random.default_rng(0)
rnd = []
for m, t in zip(win, tiles):
    f = np.zeros(m.size, bool); f[rng.choice(m.size, int(m.sum()), replace=False)] = True
    rnd.append(TB.counts(f.reshape(m.shape), t["gt"]))
print(f"  random, matched area    IoU {TB._agg(rnd)['iou']:.4f}")

print("\nWITHOUT the one pathological tile (the off-specimen void)")
keep = [i for i, t in enumerate(tiles) if t["frame"] != TB.FLOODED]
for nm, r in [("shipped", rs), ("winner", rw)]:
    m = TB._agg([r[i] for i in keep])
    print(f"  {nm:<10} n=25  P {m['precision']:.4f}  R {m['recall']:.4f}  IoU {m['iou']:.4f}  F1 {m['f1']:.4f}")

print("\nTHE DEAD ZONE -- were those cracks ever invisible?")
for sp in ("MAR_Amb_AS", "MAR_Amb_Cast", "MAR_Amb_HIP"):
    i = [j for j, t in enumerate(tiles) if t["specimen"] == sp]
    a, b = TB._agg([rs[j] for j in i]), TB._agg([rw[j] for j in i])
    print(f"  {sp:<15} shipped recall {a['recall']:.4f} -> {b['recall']:.4f}   IoU {a['iou']:.4f} -> {b['iou']:.4f}")

print("\nHOW MUCH DOES IT MARK?  (a detector that marks everything would also score high recall)")
pa = sum(int(m.sum()) for m in win); ga = sum(int(t["gt"].sum()) for t in tiles)
tot = sum(m.size for m in win)
print(f"  predicted {pa:,} px = {100*pa/tot:.3f}% of area;  hand-marked {ga:,} px = {100*ga/tot:.3f}%")
print(f"  ratio predicted/marked {pa/ga:.3f}   (mark-everything would be {tot/ga:.1f}x)")

print("\nPAIRED across the 13 specimens, shipped vs winner")
specs = sorted({t["specimen"] for t in tiles})
x = np.array([TB._agg([rs[j] for j, t in enumerate(tiles) if t["specimen"] == s])["iou"] for s in specs])
y = np.array([TB._agg([rw[j] for j, t in enumerate(tiles) if t["specimen"] == s])["iou"] for s in specs])
print(f"  median paired delta {np.median(y-x):+.4f}   better {int((y>x).sum())}/13  worse {int((y<x).sum())}"
      f"   Wilcoxon p={stats.wilcoxon(x, y).pvalue:.4f}")
