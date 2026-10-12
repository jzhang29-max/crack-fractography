"""Can the big radii be computed cheaply without moving the result?

A gaussian at sigma=320 truncates at 4 sigma, so scipy convolves with a ~2561 px kernel --
that single scale costs 36 s of the union's 64 s on a 25 Mpx frame. But the thing being
computed is a BACKGROUND estimate: by construction it has no detail finer than sigma, so
evaluating it at full resolution is wasted work. Decimate by f, filter at sigma/f, resample
back.

This must be checked, not assumed: an approximation inside the candidate stage changes the
mask, and the mask is what every number in the provenance block describes. Accept it only
if the tile scores are unchanged to 4 decimals AND the superset property survives.
"""
import os, sys, time
import numpy as np
from scipy import ndimage as ndi
from skimage import exposure, filters

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R); sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP
import detect_cracks as D

LADDER = (5, 10, 20, 40, 80, 160, 320)
BIG = 64            # above this, estimate the background on a decimated copy


def flatten_fast(img8, sigma):
    if sigma <= BIG:
        return D.flatten_background(img8, sigma=sigma)
    f = max(1, int(round(sigma / 32.0)))
    small = ndi.uniform_filter(img8.astype(np.float32), f)[::f, ::f]
    bg_s = ndi.gaussian_filter(small, sigma / f, mode="nearest")
    bg = ndi.zoom(bg_s, (img8.shape[0] / bg_s.shape[0], img8.shape[1] / bg_s.shape[1]),
                  order=1, mode="nearest")
    bg = bg[:img8.shape[0], :img8.shape[1]]
    if bg.shape != img8.shape:                      # zoom can land a pixel short
        bg = np.pad(bg, ((0, img8.shape[0] - bg.shape[0]), (0, img8.shape[1] - bg.shape[1])),
                    mode="edge")
    flat = img8.astype(np.float32) - bg
    lo, hi = np.percentile(flat, [0.5, 99.5])
    if hi <= lo:
        lo, hi = flat.min(), flat.max()
    return exposure.rescale_intensity(flat, in_range=(lo, hi), out_range=(0, 255)).astype(np.uint8)


def union(img8, flatten, k=5.0):
    out = None
    for s in LADDER:
        sm = filters.gaussian(flatten(img8, s), sigma=1.0, preserve_range=True)
        med = np.median(sm); mad = np.median(np.abs(sm - med)) * 1.4826
        cut = sm < min(filters.threshold_otsu(sm), med - k * mad)
        out = cut if out is None else (out | cut)
    return out | (img8 < 10)


def candidates(m):
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); keep = np.where(sz >= 40)[0]
    return np.isin(lab, keep[keep > 0])


tiles = TB.load()
print("CONTROLS"); assert TB.controls(); print()
ex, fa, st = [], [], []
diff = lost = 0
for i, t in enumerate(tiles, 1):
    img8 = t["img8"]
    me = union(img8, lambda a, s: D.flatten_background(a, sigma=s))
    mf = union(img8, flatten_fast)
    stock = D.segment_dark_regions(D.flatten_background(img8), img8=img8)
    diff += int((me ^ mf).sum()); lost += int((stock & ~mf).sum())
    ex.append(TB.counts(candidates(me), t["gt"])); fa.append(TB.counts(candidates(mf), t["gt"]))
    st.append(TB.counts(candidates(stock), t["gt"]))
    print(f"  [{i:>2}/26] {t['frame'][:40]:<42} differ {int((me ^ mf).sum()):>6} px", flush=True)

print(f"\n  {'':<24} {'prec':>7} {'recall':>7} {'IoU':>7} {'F1':>7}")
for n, r in (("stock single scale", st), ("union, exact flatten", ex), ("union, FAST flatten", fa)):
    m = TB._agg(r)
    print(f"  {n:<24} {m['precision']:7.4f} {m['recall']:7.4f} {m['iou']:7.4f} {m['f1']:7.4f}")
a, b = TB._agg(ex), TB._agg(fa)
same = all(abs(a[k] - b[k]) < 5e-4 for k in ("precision", "recall", "iou", "f1"))
print(f"\n  fast == exact to 4 dp: {'YES' if same else 'NO'}   (masks differ by {diff:,} px total)")
print(f"  fast still a strict superset of the stock mask: {'YES' if lost == 0 else f'NO ({lost} px lost)'}")

f = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/original/MAR_Amb_Cast_CBS_0005.tif"
img8 = D.load_as_uint8(f); x0, y0, x1, y1 = D.find_field_of_view(img8); img8 = img8[y0:y1, x0:x1]
for n, fn in (("exact", lambda a, s: D.flatten_background(a, sigma=s)), ("fast", flatten_fast)):
    t0 = time.time(); m = union(img8, fn); print(f"  full frame, {n:<6} union: {time.time()-t0:6.1f} s")
