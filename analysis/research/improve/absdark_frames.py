"""The same threshold on FULL FRAMES, where the tiles are known to be blind.

The 26 crops are 0.84% of corpus area, actively selected, and cannot contain a wide crack
(tile paint tops out at 43.7 px mean width; frame paint reaches 178). The claim to test is
that raising absolute_dark_thresh widens cracks already found -- which a crop mostly cannot
see, because the wide ones are not in it.

Scored on the correction masks: 1 = crack, 2 = not-crack, 0 = unreviewed, excluded from
both. Read only.
"""
import os, sys, time
import numpy as np
from scipy import ndimage as ndi
from PIL import Image

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code")
sys.dont_write_bytecode = True
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
THRS = (10, 20, 30)


def arm(t):
    class U:
        pass
    u = U(); DO.install(u, absolute_dark_thresh=t); return u


ups = {t: arm(t) for t in THRS}


def cand(m):
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
               if f.endswith("_correction_mask.png"))
names = [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
LIMIT = int(os.environ.get("NFRAMES", "16"))
A = {t: dict(tp=0, fp=0, area=0) for t in THRS}
A["crack"] = 0; A["notc"] = 0; A["px"] = 0; A["n"] = 0
print(f"{'frame':<34} {'painted':>10} | " + " ".join(f"{'R t='+str(t):>9}" for t in THRS))
print("-" * 86)
for n in names:
    if A["n"] >= LIMIT:
        break
    try:
        img8 = D.load_as_uint8(os.path.join(SEM, "original", n + ".tif"))
        x0, y0, x1, y1 = D.find_field_of_view(img8); img8 = img8[y0:y1, x0:x1]
        corr = np.array(Image.open(os.path.join(PAINT, n + "_correction_mask.png")))
        corr = corr[..., 0] if corr.ndim == 3 else corr
        if corr.shape != img8.shape:
            if corr.shape[0] >= y1 and corr.shape[1] >= x1:
                corr = corr[y0:y1, x0:x1]
            else:
                continue
        crack, notc = corr == 1, corr == 2
        if crack.sum() < 20000:
            continue
        flat = D.flatten_background(img8)
        A["crack"] += int(crack.sum()); A["notc"] += int(notc.sum()); A["px"] += img8.size; A["n"] += 1
        cells = []
        base = None
        for t in THRS:
            m = cand(ups[t].segment_dark_regions(flat, img8=img8))
            if base is None:
                base = m
            elif (base & ~m).any():
                print("   !! NOT A SUPERSET on", n)
            A[t]["tp"] += int((m & crack).sum()); A[t]["fp"] += int((m & notc).sum())
            A[t]["area"] += int(m.sum())
            cells.append(f"{int((m&crack).sum())/int(crack.sum()):9.4f}")
        print(f"{n:<34} {int(crack.sum()):>10,} | " + " ".join(cells), flush=True)
    except Exception as e:
        print(f"{n:<34}  ERROR {type(e).__name__}: {e}", flush=True)
print("-" * 86)
print(f"{'POOLED, ' + str(A['n']) + ' frames':<34} {A['crack']:>10,} | "
      + " ".join(f"{A[t]['tp']/max(A['crack'],1):9.4f}" for t in THRS))
print()
print(f"  {'threshold':<12} {'recall on painted crack':>24} {'rate on painted NOT-crack':>26} {'% of frame marked':>19}")
for t in THRS:
    print(f"  t={t:<10} {A[t]['tp']/max(A['crack'],1):24.4f} {A[t]['fp']/max(A['notc'],1):26.4f} "
          f"{100*A[t]['area']/max(A['px'],1):18.2f}%")
print(f"\n  (hand-marked not-crack is only {A['notc']:,} px against {A['crack']:,} painted crack,")
print(f"   so the middle column is weak evidence -- it is 0.6% of the refereed pool.)")
print("\n  MARGINAL COST per step, on full frames:")
for a, b in zip(THRS, THRS[1:]):
    dtp = A[b]["tp"] - A[a]["tp"]; dfp = A[b]["fp"] - A[a]["fp"]; da = A[b]["area"] - A[a]["area"]
    print(f"    {a} -> {b}: +{da:,} px marked, of which +{dtp:,} painted crack "
          f"({100*dtp/max(da,1):.1f}%), +{dfp:,} painted not-crack")
