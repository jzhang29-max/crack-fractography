"""Score the SHIPPED v1.49.2 detector on the same 15 tiles the method comparison uses.

The comparison plate carries OmniCrack30k's nnU-Net, SAM 3, SERD, four classical filters and
two models trained on this corpus -- but the arm labelled "logistic regression" is the OLD
region classifier, and the pipeline that actually ships is not on the plate at all. Adding it
requires scoring it on THE SAME 15 TILES, not on the 26-tile set every other number in this
project uses: comparing across unit sets is how this project has produced false rankings.

Inputs are the tiles' own *_gray.png (read from the raw original at the aligned offset) and
*_gt.png. The overlay file is deliberately never touched -- an early version of that
experiment built its input from the overlay's green channel, which encoded the answer, and a
bare threshold then "recovered" the ground truth at recall 1.000.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
B = os.path.join(SEM, "crack_export", "analysis", "sam3")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import measure as skm
from skimage.morphology import skeletonize
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None


class U:
    pass


up = U(); print("install():", DO.install(up))


def emitted(img8):
    raw = up.segment_dark_regions(D.flatten_background(img8), img8=img8)
    lab = skm.label(D.clean_mask(raw, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def cldice(p, g):
    if not p.any() or not g.any():
        return 0.0
    sp, sg = skeletonize(p), skeletonize(g)
    if not sp.any() or not sg.any():
        return 0.0
    a = (sp & g).sum() / max(sp.sum(), 1); b = (sg & p).sum() / max(sg.sum(), 1)
    return 0.0 if a + b == 0 else float(2 * a * b / (a + b))


tiles = sorted(f[:-len("_gray.png")] for f in os.listdir(os.path.join(B, "tiles"))
               if f.endswith("_gray.png"))
print(f"{len(tiles)} tiles\n")
ious, clds = [], []
for t in tiles:
    g = np.array(Image.open(os.path.join(B, "tiles", t + "_gray.png")).convert("L"))
    gt = np.array(Image.open(os.path.join(B, "tiles", t + "_gt.png")).convert("L")) > 127
    m = emitted(g)
    tp = int((m & gt).sum()); fp = int((m & ~gt).sum()); fn = int((~m & gt).sum())
    iou = tp / max(tp + fp + fn, 1); cd = cldice(m, gt)
    ious.append(iou); clds.append(cd)
    print(f"  {t[:46]:<48} IoU {iou:.4f}  clDice {cd:.4f}", flush=True)

print(f"\nSHIPPED v1.49.2 on the 15-tile comparison set")
print(f"  median IoU    {np.median(ious):.4f}")
print(f"  median clDice {np.median(clds):.4f}")
json.dump({"shipped v1.49.2|IoU": ious, "shipped v1.49.2|clDice": clds, "tiles": tiles},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "shipped15.json"), "w"),
          indent=1)

mb = json.load(open(os.path.join(B, "methods_bench.json")))


def lofo(v):
    """The plate scores every parameterised arm leave-one-FRAME-out; that is the field to
    read. These entries also carry OIS and ODS (oracle selections), and averaging across
    the three silently mixes estimators."""
    if isinstance(v, dict):
        return v.get("LOFO")
    if isinstance(v, list):
        return float(np.median(v))
    return v


print("\n  the plate's own arms on these same tiles (LOFO):")
for k in sorted(mb):
    if k.endswith("|IoU"):
        nm = k[:-4]
        a, b = lofo(mb[k]), lofo(mb.get(nm + "|clDice"))
        if a is None:
            continue
        print(f"    {nm:<26} IoU {a:.4f}" + (f"  clDice {b:.4f}" if b is not None else ""))
