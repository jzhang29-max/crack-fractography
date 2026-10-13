"""Does a higher number mean better? Put every arm on one curve with the floor drawn in.

Recall alone is not a score: marking every pixel scores recall 1.0. The only way to read
recall is against what it costs, and the only way to read precision is against the
NO-INFORMATION FLOOR -- the precision a coin would get, which equals the prevalence of
crack among refereed pixels. An arm at the floor has learned nothing, whatever its recall.

So: a sweep of the darkness cut from very strict to very loose, which traces the whole
trade-off the detector can reach, with the named arms placed on it and the floor marked.
Per-frame spread too, because a pooled number carried by one frame is not a performance.
"""
import os, sys, json
import numpy as np
from scipy import ndimage as ndi
from skimage import filters

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code")
sys.dont_write_bytecode = True
import detect_cracks as D
import detector_overrides as DO

TXM = "/Users/jiamingzhang/Desktop/APP/TXM_Crack_Detection_Pipeline"


def arm(t, multi=True):
    class U:
        pass
    u = U(); DO.install(u, absolute_dark_thresh=t, use_multiscale_union=multi); return u


U = arm(10, True)
MADK = [8.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5]


def cand(m):
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


names = []
for f in sorted(os.listdir(os.path.join(TXM, "paint", "corrections"))):
    if not f.endswith("_correction.npy"):
        continue
    stem = f[: -len("_correction.npy")]
    tif = os.path.join(TXM, "images", stem + ".tif")
    if os.path.exists(tif):
        names.append((stem, tif, os.path.join(TXM, "paint", "corrections", f)))

ARMS = [f"mad_k {k}" for k in MADK] + ["Otsu (no model)", "mark everything"]
A = {a: dict(tp=0, fp=0) for a in ARMS}
per = {a: [] for a in ARMS}
tot_c = tot_n = 0
used = 0
for i, (stem, tif, cp) in enumerate(names, 1):
    corr = np.load(cp)
    if int((corr == 1).sum()) < 5000:
        continue
    img8 = D.load_as_uint8(tif)
    if img8.shape != corr.shape:
        continue
    crack, notc = corr == 1, corr == 2
    tot_c += int(crack.sum()); tot_n += int(notc.sum()); used += 1
    flat = D.flatten_background(img8)
    sm = filters.gaussian(flat, sigma=1.0, preserve_range=True)
    masks = {}
    for k in MADK:
        u = arm(10, True)
        masks[f"mad_k {k}"] = cand(u.segment_dark_regions(flat, img8=img8, mad_k=k))
    masks["Otsu (no model)"] = sm < filters.threshold_otsu(sm)
    masks["mark everything"] = np.ones_like(crack)
    for a in ARMS:
        m = masks[a]
        tp = int((m & crack).sum()); fp = int((m & notc).sum())
        A[a]["tp"] += tp; A[a]["fp"] += fp
        per[a].append((tp / max(int(crack.sum()), 1), tp / max(tp + fp, 1)))
    print(f"  [{used:>2}] {stem[:44]}", flush=True)

floor = tot_c / max(tot_c + tot_n, 1)
print(f"\nTXM, {used} frames, refereed pixels only: {tot_c:,} crack / {tot_n:,} not-crack")
print(f"NO-INFORMATION FLOOR (prevalence) = {floor:.4f}  -- precision at or below this means nothing learned\n")
print(f"  {'arm':<20} {'recall':>8} {'precision':>10} {'LIFT':>7} {'F1':>8}   per-frame precision")
print(f"  {'':<20} {'':>8} {'':>10} {'xfloor':>7} {'':>8}   {'p25':>6} {'med':>6} {'p75':>6}")
for a in ARMS:
    tp, fp = A[a]["tp"], A[a]["fp"]
    p = tp / max(tp + fp, 1); r = tp / max(tot_c, 1)
    pf = np.array([x[1] for x in per[a]])
    print(f"  {a:<20} {r:8.4f} {p:10.4f} {p/floor:7.2f} {2*p*r/max(p+r,1e-9):8.4f}   "
          f"{np.percentile(pf,25):6.3f} {np.median(pf):6.3f} {np.percentile(pf,75):6.3f}")
print(f"\n  Read it as: an arm is useful only if LIFT is well above 1.00.")
json.dump({a: A[a] for a in ARMS} | {"crack": tot_c, "notc": tot_n, "floor": floor},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "curve.json"), "w"), indent=1)
