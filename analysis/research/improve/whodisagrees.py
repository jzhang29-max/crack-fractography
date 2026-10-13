"""Tiles say the 10->20 band is 12.4% crack; full frames say 91.6%. Both cannot be right.

The band is pixels with img8 in [10,20) -- essentially black after the 1/99.5 percentile
stretch. The question is whether the tiles sample that population at all, or whether their
estimate is really a measurement of the one off-specimen void.
"""
import sys
import numpy as np
from scipy import ndimage as ndi

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R); sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP
import detect_cracks as D
import detector_overrides as DO


def arm(t):
    class U:
        pass
    u = U(); DO.install(u, absolute_dark_thresh=t); return u


def cand(m):
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


u10, u20 = arm(10), arm(20)
tiles = TB.load()
tot = hit = void_add = void_hit = 0
rows = []
for t in tiles:
    flat = D.flatten_background(t["img8"])
    a = cand(u10.segment_dark_regions(flat, img8=t["img8"]))
    b = cand(u20.segment_dark_regions(flat, img8=t["img8"]))
    add = b & ~a
    n = int(add.sum()); h = int((add & t["gt"]).sum())
    tot += n; hit += h
    if t["frame"] == TB.FLOODED:
        void_add, void_hit = n, h
    if n:
        rows.append((t["frame"], n, h, h / n))

print(f"THE 10->20 BAND ON THE TILES: {tot:,} px total, {hit:,} inside painted crack "
      f"({100*hit/max(tot,1):.1f}%)")
print(f"  of which the ONE off-specimen void tile:  {void_add:,} px ({100*void_add/max(tot,1):.1f}% of the band), "
      f"{void_hit:,} crack")
rest, resth = tot - void_add, hit - void_hit
print(f"  the other 25 tiles:                       {rest:,} px, {resth:,} crack "
      f"= {100*resth/max(rest,1):.1f}% purity")
print()
print(f"  tiles that contain ANY of the band: {len(rows)} of 26")
for f, n, h, p in sorted(rows, key=lambda r: -r[1])[:6]:
    print(f"    {f[:44]:<46} {n:>7,} px  {100*p:5.1f}% crack")
print()
area_tiles = sum(t["img8"].size for t in tiles)
print(f"SAMPLING: the 26 tiles hold {tot:,} band px over {area_tiles/1e6:.1f} Mpx of image.")
print(f"  the 41 full frames hold 8,149,543 band px -- {8149543/max(tot,1):.0f}x as many.")
print(f"  so the tiles observe {100*tot/8149543:.2f}% of the population this parameter moves,")
print(f"  and {100*void_add/max(tot,1):.0f}% of what they DO observe is the one off-specimen void.")
