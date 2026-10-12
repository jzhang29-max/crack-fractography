"""Crack COUNT over-reports 1.50x. Is that real fragmentation, or dust?

A count is not a mass: this project has already had 305 components read as fragmentation
when the largest held 97.45% of the area. So before treating the count as a defect, find
out how much area the extra components carry and what size they are.
"""
import sys
import numpy as np
from scipy import ndimage as ndi
from scipy import stats

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R)
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP
import detect_cracks as D
import detector_overrides as DO


class FakeUP:
    pass


up = FakeUP(); DO.install(up)
NB = np.ones((3, 3), bool)


def candidates(mask):
    lab, _ = ndi.label(D.clean_mask(mask, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); keep = np.where(sz >= 40)[0]
    return np.isin(lab, keep[keep > 0])


def comps(m):
    lab, n = ndi.label(m, structure=NB)
    if not n:
        return np.array([], int)
    return np.sort(np.bincount(lab.ravel())[1:])[::-1]


tiles = TB.load()
MINS = (0, 100, 250, 500, 1000)
tot = {k: dict(gt=0, new=0) for k in MINS}
gt_area_small = new_area_small = gt_area = new_area = 0
for t in tiles:
    flat = D.flatten_background(t["img8"])
    new = candidates(up.segment_dark_regions(flat, img8=t["img8"]))
    cg, cn = comps(t["gt"]), comps(new)
    for k in MINS:
        tot[k]["gt"] += int((cg >= max(k, 1)).sum()); tot[k]["new"] += int((cn >= max(k, 1)).sum())
    gt_area += cg.sum(); new_area += cn.sum()
    gt_area_small += cg[cg < 500].sum(); new_area_small += cn[cn < 500].sum()

print("CRACK COUNT at a minimum component size")
print(f"  {'min size px':>12} {'hand labels':>12} {'v1.49':>8} {'ratio':>8}")
for k in MINS:
    g, n = tot[k]["gt"], tot[k]["new"]
    print(f"  {k if k else 'none (>=1)':>12} {g:>12} {n:>8} {n/max(g,1):8.2f}")
print()
print(f"  area in components SMALLER than 500 px:")
print(f"    hand labels {100*gt_area_small/max(gt_area,1):5.2f}% of marked area")
print(f"    v1.49       {100*new_area_small/max(new_area,1):5.2f}% of predicted area")
print()
print("  So the extra components are " +
      ("DUST -- they carry almost no area, and the count converges once tiny fragments are "
       "excluded." if tot[500]["new"] / max(tot[500]["gt"], 1) < 1.25 else
       "REAL -- the count stays high even for sizeable components, so the mask is genuinely "
       "fragmenting cracks."))
