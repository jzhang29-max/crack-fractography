"""SAFETY TEST: does the texture veto delete main cracks on FULL frames?

unified_pipeline.py's own source carries a measured warning against exactly this class of
rule. exclude_border_background() was removed because it deleted main cracks -- 69,497
hand-marked px on 260708_316_H_b2_front_CBS_004 (35% of that frame's marks). The comment
names three discriminators that all overlap, and one of them is mine, inverted:

    "raw darkness INVERTED -- the main crack on ..._front_CBS_004 is mean 1.44 /
     local std 0.53, DARKER and SMOOTHER than the off-specimen background at 5.02 / 2.09"

My veto keeps a region only if its local std is at least the frame's median. On that frame
the main crack is SMOOTHER than the background, so the veto should delete exactly the thing
it must never delete. The 26 tiles are 512 px crops and may simply not contain a wide-open
main crack, which would make a tile-validated veto unsafe the moment it meets a full frame.

Scored against the human correction masks (1=crack, 2=not-crack, 3=erased, 0=unreviewed),
read only. A veto that removes hand-marked crack is disqualified however well it scores.
"""
import os, sys
import numpy as np
from scipy import ndimage as ndi
from PIL import Image

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.dont_write_bytecode = True
import crackpipe as CP
import detect_cracks as D
Image.MAX_IMAGE_PIXELS = None

SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
FRAMES = ["260708_316_H_b2_front_CBS_004", "260708_316_H_b2_front_CBS_003",
          "260708_316_H_b2_front_CBS_005", "MAR_Amb_Cast_CBS_0001", "MAR_Amb_Cast_CBS_0005"]


def local_std(a, r=16):
    a = np.asarray(a, np.float32)
    m = ndi.uniform_filter(a, 2 * r + 1); m2 = ndi.uniform_filter(a * a, 2 * r + 1)
    return np.sqrt(np.maximum(m2 - m * m, 0)).astype(np.float32)


print(f"{'frame':<34} {'hand-marked':>12} {'cand hits':>10} {'VETO DELETES':>13} {'% of marks':>11}")
print("-" * 86)
tot_marks = tot_del = 0
for name in FRAMES:
    cm = os.path.join(PAINT, name + "_correction_mask.png")
    tif = os.path.join(SEM, "original", name + ".tif")
    if not (os.path.exists(cm) and os.path.exists(tif)):
        print(f"{name:<34}   (no correction mask on disk -- skipped)")
        continue
    img8 = D.load_as_uint8(tif)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]
    corr = np.array(Image.open(cm))
    if corr.ndim == 3:
        corr = corr[..., 0]
    if corr.shape != img8.shape:          # the paint is stored on the untrimmed raster
        corr = corr[y0:y1, x0:x1] if corr.shape[0] >= y1 and corr.shape[1] >= x1 else None
    if corr is None or corr.shape != img8.shape:
        print(f"{name:<34}   (paint {np.shape(corr)} does not fit image {img8.shape} -- skipped)")
        continue
    marked = corr == 1                                     # 1 = hand-marked CRACK
    flat = D.flatten_background(img8)
    dark = D.segment_dark_regions(flat, img8=img8)
    clean = D.clean_mask(dark, min_area_px=13)
    s = local_std(flat)
    base = max(float(np.median(s)), 1e-6)
    lab, n = ndi.label(clean)
    deleted = np.zeros_like(clean)
    if n:
        keep = np.zeros(n + 1, bool)
        objs = ndi.find_objects(lab)
        for i in range(1, n + 1):
            sl = objs[i - 1]
            m = lab[sl] == i
            keep[i] = (float(np.median(s[sl][m])) / base) >= 1.0
        deleted = (~keep)[lab] & clean
    hit = int((clean & marked).sum()); dele = int((deleted & marked).sum())
    tot_marks += int(marked.sum()); tot_del += dele
    print(f"{name:<34} {int(marked.sum()):>12,} {hit:>10,} {dele:>13,} "
          f"{100*dele/max(int(marked.sum()),1):10.2f}%")
print("-" * 86)
print(f"{'TOTAL':<34} {tot_marks:>12,} {'':>10} {tot_del:>13,} {100*tot_del/max(tot_marks,1):10.2f}%")
print()
print("VERDICT: the veto is SAFE to ship only if it deletes ~0 hand-marked crack here.")
