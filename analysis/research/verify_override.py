"""Does the OVERRIDE SHIPPED IN THE APP reproduce the mask that was measured?

The measurement and the override are different code written at different times. If they
disagree, the number in the provenance block describes something the app does not do.
Checks, in order: the override is actually installed, its mask is identical to the
measured one, it is a strict superset of the stock mask, and it scores what is claimed.
"""
import os, sys, time
import numpy as np
from scipy import ndimage as ndi
from skimage import filters

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R)
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP
import detect_cracks as D
import detector_overrides as DO


class FakeUP:
    pass


up = FakeUP()
print("install() reports:", DO.install(up))
assert hasattr(up, "segment_dark_regions"), "nothing was installed"
print("USE_REGION_CLASSIFIER =", DO.USE_REGION_CLASSIFIER,
      "| USE_MULTISCALE_UNION =", DO.USE_MULTISCALE_UNION)
print()


def candidates(mask):
    lab, _ = ndi.label(D.clean_mask(mask, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); keep = np.where(sz >= 40)[0]
    return np.isin(lab, keep[keep > 0])


def measured_union(img8, k=5.0):
    """The reference implementation, written during the measurement."""
    out = None
    for s in DO.SCALE_LADDER:
        f = D.flatten_background(img8, sigma=s)
        sm = filters.gaussian(f, sigma=1.0, preserve_range=True)
        med = np.median(sm); mad = np.median(np.abs(sm - med)) * 1.4826
        cut = sm < min(filters.threshold_otsu(sm), med - k * mad)
        out = cut if out is None else (out | cut)
    return out | (img8 < 10)


tiles = TB.load()
print("CONTROLS"); assert TB.controls(); print()
mism = superset_violations = 0
rows_new, rows_old = [], []
t0 = time.time()
for i, t in enumerate(tiles, 1):
    img8 = t["img8"]
    flat = D.flatten_background(img8)                      # what unified_pipeline passes
    shipped_mask = up.segment_dark_regions(flat, img8=img8)
    ref = measured_union(img8)
    stock = D.segment_dark_regions(flat, img8=img8)
    if not np.array_equal(shipped_mask, ref):
        mism += 1
        print(f"  MISMATCH on {t['frame']}: {int((shipped_mask ^ ref).sum())} px differ")
    if (stock & ~shipped_mask).any():
        superset_violations += 1
    rows_new.append(TB.counts(candidates(shipped_mask), t["gt"]))
    rows_old.append(TB.counts(candidates(stock), t["gt"]))
    print(f"  [{i:>2}/26] {t['frame'][:42]:<44} ok", flush=True)
dt = time.time() - t0

print(f"\n  override == measured reference on all 26 tiles: {'YES' if mism == 0 else f'NO ({mism} differ)'}")
print(f"  strict superset of the stock mask everywhere:   "
      f"{'YES' if superset_violations == 0 else f'NO ({superset_violations} tiles lose pixels)'}")
a, b = TB._agg(rows_old), TB._agg(rows_new)
print(f"\n  {'':<22} {'prec':>7} {'recall':>7} {'IoU':>7} {'F1':>7}")
print(f"  {'stock single scale':<22} {a['precision']:7.4f} {a['recall']:7.4f} {a['iou']:7.4f} {a['f1']:7.4f}")
print(f"  {'SHIPPED override':<22} {b['precision']:7.4f} {b['recall']:7.4f} {b['iou']:7.4f} {b['f1']:7.4f}")
claim = dict(precision=0.4175, recall=0.6234, iou=0.3334, f1=0.5001)
bad = [k for k, v in claim.items() if abs(b[k] - v) > 5e-4]
print(f"  matches the number in detector_overrides.py: {'YES' if not bad else 'NO -- ' + str(bad)}")
print(f"\n  cost: {dt/len(tiles):.2f} s per 512x512 tile for the 7-scale union")
sys.exit(0 if (mism == 0 and superset_violations == 0 and not bad) else 1)
