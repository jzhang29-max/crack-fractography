"""Does resolution-matching actually fix the SEM->TXM transfer, or just sound like it should?

The gap measurement says TXM cracks are 3.84x NARROWER in pixels than SEM ones (median
painted width 7.90 px vs 30.34), while contrast is essentially identical (Cohen's d 1.62 vs
1.76, same sign). Every constant in this detector is denominated in pixels -- the seven
flattening radii, clean_mask's 13 px floor, the 40 px region floor -- so on TXM they are all
roughly 4x too coarse. That is a hypothesis with an obvious remedy, and remedies that sound
obvious have failed six times in this project, so it is tested rather than asserted.

Scored on refereed pixels only (1 = crack, 2 = not-crack, 0 = unreviewed, excluded), against
the shipped setting and the no-information floor.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
TXM = "/Users/jiamingzhang/Desktop/APP/TXM_Crack_Detection_Pipeline"
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from skimage import measure as skm
import detect_cracks as D
import detector_overrides as DO

SCALE = 7.90 / 30.34          # measured width ratio, TXM / SEM = 0.260


def arm(ladder, absd=10):
    class U:
        pass
    u = U(); DO.install(u, scale_ladder=ladder, absolute_dark_thresh=absd); return u


def emit(u, img8, min_area, floor, mad_k=5.0):
    raw = u.segment_dark_regions(D.flatten_background(img8), img8=img8, mad_k=mad_k)
    clean = D.clean_mask(raw, min_area_px=min_area)
    lab = skm.label(clean, connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= floor)[0]
    return np.isin(lab, k[k > 0])


SHIP = (5, 10, 20, 40, 80, 160, 320)
SCALED = tuple(max(1, int(round(s * SCALE))) for s in SHIP)
print(f"  shipped ladder {SHIP}")
print(f"  scaled  ladder {SCALED}   (x{SCALE:.3f}, the measured width ratio)")
print(f"  min_area 13 -> {max(1, int(round(13 * SCALE**2)))}, region floor 40 -> "
      f"{max(1, int(round(40 * SCALE**2)))}  (areas scale as the square)\n")
MA_S, FL_S = max(1, int(round(13 * SCALE ** 2))), max(1, int(round(40 * SCALE ** 2)))

ARMS = {
    "shipped (SEM constants)": (arm(SHIP), 13, 40),
    "ladder scaled only": (arm(SCALED), 13, 40),
    "areas scaled only": (arm(SHIP), MA_S, FL_S),
    "FULLY resolution-matched": (arm(SCALED), MA_S, FL_S),
}
A = {k: dict(tp=0, fp=0) for k in ARMS}
A["mark everything"] = dict(tp=0, fp=0)
tot_c = tot_n = 0
names = sorted(f[:-len("_correction.npy")] for f in os.listdir(os.path.join(TXM, "paint", "corrections"))
               if f.endswith("_correction.npy"))
used = 0
for n in names:
    tif = os.path.join(TXM, "images", n + ".tif")
    cp = os.path.join(TXM, "paint", "corrections", n + "_correction.npy")
    if not os.path.exists(tif):
        continue
    corr = np.load(cp)
    if int((corr == 1).sum()) < 5000:
        continue
    img8 = D.load_as_uint8(tif)
    if img8.shape != corr.shape:
        continue
    crack, notc = corr == 1, corr == 2
    tot_c += int(crack.sum()); tot_n += int(notc.sum()); used += 1
    for k, (u, ma, fl) in ARMS.items():
        m = emit(u, img8, ma, fl)
        A[k]["tp"] += int((m & crack).sum()); A[k]["fp"] += int((m & notc).sum())
    A["mark everything"]["tp"] += int(crack.sum()); A["mark everything"]["fp"] += int(notc.sum())
    print(f"   [{used:>2}] {n[:46]}", flush=True)

floor = tot_c / max(tot_c + tot_n, 1)
print(f"\nTXM, {used} frames, refereed px only ({tot_c:,} crack / {tot_n:,} not-crack)")
print(f"no-information floor = {floor:.4f}\n")
print(f"  {'arm':<28} {'recall':>8} {'precision':>10} {'LIFT':>7} {'F1':>8}")
for k in list(ARMS) + ["mark everything"]:
    tp, fp = A[k]["tp"], A[k]["fp"]
    p = tp / max(tp + fp, 1); r = tp / max(tot_c, 1)
    print(f"  {k:<28} {r:8.4f} {p:10.4f} {p/floor:7.2f} {2*p*r/max(p+r,1e-9):8.4f}")
json.dump(A | {"crack": tot_c, "notc": tot_n, "floor": floor, "n": used},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scale_fix.json"), "w"), indent=1)
