"""absolute_dark_thresh 10 -> 20: what does it actually cost and buy?

Raising it can only ADD pixels (img8 < 20 contains img8 < 10), so the candidate mask is a
strict superset and the rule cannot delete a human label -- the property that separates
every change shipped here from the six that died. Checked, not assumed.

Three readings, because they are known to disagree and the disagreement is the point:
  TILES          26 hand-labelled 512px crops, leave-one-specimen-out through tilebench
  MEASUREMENTS   area fraction / length / width against the same hand labels -- what the
                 paper actually reports, and not the same question as IoU
  (full frames run separately; the crops are 0.84% of corpus area and hold the pores this
   catches rather than the wide cracks it widens)
"""
import sys
import numpy as np
from scipy import ndimage as ndi
from scipy import stats
from skimage.morphology import skeletonize

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R); sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP
import detect_cracks as D
import detector_overrides as DO

THRS = (10, 15, 20, 25, 30, 40)
NB = np.ones((3, 3), bool)


def arm(t):
    class U:
        pass
    u = U(); DO.install(u, absolute_dark_thresh=t)
    return u


def cand(m):
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def skel_len(sk):
    if not sk.any():
        return 0.0
    o = sum(int((sk & np.roll(sk, s, axis=a)).sum()) for a in (0, 1) for s in (1, -1))
    d = sum(int((sk & np.roll(np.roll(sk, a, 0), b, 1)).sum()) for a in (1, -1) for b in (1, -1))
    return (o + d * np.sqrt(2.0)) / 2.0


def measure(m):
    m = np.asarray(m, bool)
    if not m.any():
        return dict(area_frac=0.0, length=0.0, width=0.0)
    sk = skeletonize(m); dt = ndi.distance_transform_edt(m)
    return dict(area_frac=float(m.mean()), length=skel_len(sk),
                width=float(2 * dt[sk].mean()) if sk.any() else 0.0)


tiles = TB.load()
print("CONTROLS"); assert TB.controls(); print()
ups = {t: arm(t) for t in THRS}
masks = {t: [] for t in THRS}
for i, tile in enumerate(tiles, 1):
    flat = D.flatten_background(tile["img8"])
    for t in THRS:
        masks[t].append(cand(ups[t].segment_dark_regions(flat, img8=tile["img8"])))
    print(f"  [{i:>2}/26] {tile['frame'][:42]}", flush=True)

print("\nSUPERSET CHECK -- raising the threshold must never remove a pixel")
for t in THRS[1:]:
    lost = sum(int((a & ~b).sum()) for a, b in zip(masks[10], masks[t]))
    print(f"  t={t:<3} pixels present at t=10 and absent at t={t}: {lost}   {'OK' if lost == 0 else 'NOT A SUPERSET'}")

rows = {t: [TB.counts(m, x["gt"]) for m, x in zip(masks[t], tiles)] for t in THRS}
keep25 = [i for i, x in enumerate(tiles) if x["frame"] != TB.FLOODED]
print(f"\nTILES, pooled over 26     {'prec':>8} {'recall':>8} {'IoU':>8} {'F1':>8}  |  excluding the void tile (25)")
for t in THRS:
    a = TB._agg(rows[t]); b = TB._agg([rows[t][i] for i in keep25])
    star = "  <- shipped" if t == 10 else ""
    print(f"  absolute_dark={t:<3} {a['precision']:8.4f} {a['recall']:8.4f} {a['iou']:8.4f} {a['f1']:8.4f}  |  "
          f"P {b['precision']:.4f} R {b['recall']:.4f} IoU {b['iou']:.4f} F1 {b['f1']:.4f}{star}")

print(f"\n  held-out (leave-one-specimen-out over the six thresholds):")
r = TB.evaluate("absolute_dark_thresh swept", {f"t{t}": rows[t] for t in THRS}, quiet=True)
m = r["loso"]
print(f"    P {m['precision']:.4f} R {m['recall']:.4f} IoU {m['iou']:.4f} F1 {m['f1']:.4f}   picks: "
      + ", ".join(f"{k}x{v}" for k, v in __import__("collections").Counter(r["picks"].values()).most_common()))

print("\nMARGINAL COST OF EACH STEP, on the tiles")
print(f"  {'step':<14} {'px added':>10} {'of which real crack':>20} {'marginal purity':>16}")
for a, b in zip(THRS, THRS[1:]):
    add = sum(int((y & ~x).sum()) for x, y in zip(masks[a], masks[b]))
    hit = sum(int((y & ~x & tl["gt"]).sum()) for x, y, tl in zip(masks[a], masks[b], tiles))
    print(f"  {a} -> {b:<9} {add:>10,} {hit:>20,} {hit/max(add,1):16.4f}")
print(f"  (the stage's running precision is {TB._agg(rows[10])['precision']:.4f}; "
      f"crack prevalence, i.e. the chance null, is 0.0297)")

print("\nMEASUREMENTS vs the hand labels -- per-tile ratio, 1.000 is perfect")
g = {k: np.array([measure(x["gt"])[k] for x in tiles]) for k in ("area_frac", "length", "width")}
print(f"  {'threshold':<12} {'area fraction':>14} {'crack length':>14} {'crack width':>13}")
for t in THRS:
    mm = [measure(m) for m in masks[t]]
    out = []
    for k in ("area_frac", "length", "width"):
        v = np.array([x[k] for x in mm]); ok = g[k] > 0
        out.append(np.median(v[ok] / g[k][ok]))
    print(f"  t={t:<10} {out[0]:14.3f} {out[1]:14.3f} {out[2]:13.3f}" + ("   <- shipped" if t == 10 else ""))
