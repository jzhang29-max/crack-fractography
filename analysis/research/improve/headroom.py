"""How much precision is actually left to win? Independent check of the workflow's claim.

Four angles all concluded the same thing, so the number that decides whether any further
precision work is worth doing is the HEADROOM: what would a perfect, free rule buy? Taken
apart into the three things the "false positives" actually are.

The stroke-edge term needs a decoy or it proves nothing -- dilating any label excuses some
error. So the same band is computed around the real paint and around a 180-rotated sham
paint of identical area and geometry. If the real one does not excuse far more, the band is
measuring dilation, not the painter's brush.
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


class U:
    pass


up = U(); DO.install(up)
ST = ndi.generate_binary_structure(2, 2)


def cand(m):
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


tiles = TB.load()
print("CONTROLS"); assert TB.controls(); print()
TP = FP = 0
fp_void = fp_edge = fp_edge_decoy = fp_other = 0
per_tile_fp = []
for t in tiles:
    m = cand(up.segment_dark_regions(D.flatten_background(t["img8"]), img8=t["img8"]))
    gt = t["gt"]
    tp = int((m & gt).sum()); fp_m = m & ~gt; fp = int(fp_m.sum())
    TP += tp; FP += fp
    per_tile_fp.append((t["frame"], fp, tp))
    band = ndi.binary_dilation(gt, ST, iterations=2) & ~gt
    sham = np.rot90(gt, 2)
    band_d = ndi.binary_dilation(sham, ST, iterations=2) & ~sham
    e = int((fp_m & band).sum()); ed = int((fp_m & band_d).sum())
    fp_edge += e; fp_edge_decoy += ed
    if t["frame"] == TB.FLOODED:
        fp_void += fp
    else:
        fp_other += fp - e

print(f"TOTAL over 26 tiles:  TP {TP:,}   FP {FP:,}   precision {TP/(TP+FP):.4f}")
print()
worst = sorted(per_tile_fp, key=lambda r: -r[1])[:3]
print("WHAT THE FALSE POSITIVES ARE")
print(f"  the single void tile ({TB.FLOODED[:34]})")
print(f"      {fp_void:>9,} px = {100*fp_void/FP:5.1f}% of ALL false positives   (its TP: {dict((f,t) for f,_,t in per_tile_fp)[TB.FLOODED]:,})")
print(f"  within 2 px of painted crack (the painter's brush edge)")
print(f"      {fp_edge:>9,} px = {100*fp_edge/FP:5.1f}%     DECOY (same band on 180-rotated paint): "
      f"{fp_edge_decoy:,} = {100*fp_edge_decoy/FP:.1f}%   ratio {fp_edge/max(fp_edge_decoy,1):.1f}x")
print(f"  everything else, on the other 25 tiles")
print(f"      {fp_other:>9,} px = {100*fp_other/FP:5.1f}%")
print()
print("  next worst tiles after the void:")
for f, fp, tp in worst[1:]:
    print(f"      {f[:46]:<48} {fp:>8,} px = {100*fp/FP:4.1f}%")
print()
print("HEADROOM -- precision after a PERFECT, FREE rule removing each class")
base = TP / (TP + FP)
for lab, rem in (("remove the void tile's FP only", fp_void),
                 ("remove the brush-edge FP only", fp_edge),
                 ("remove everything EXCEPT void and brush edge", fp_other),
                 ("remove ALL false positives (oracle)", FP)):
    print(f"  {lab:<46} precision {base:.4f} -> {TP/(TP+FP-rem):.4f}   ({TP/(TP+FP-rem)-base:+.4f})")
print()
print(f"  So every precision point outside that one void object is worth "
      f"{TP/(TP+FP-fp_other)-base:+.4f}, against the {0.4182-0.3378:+.4f} v1.49.1 already delivered.")
