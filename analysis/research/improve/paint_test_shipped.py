"""Full-frame paint test driving the SHIPPED override itself, not a reference copy.

Everything measured so far used reference implementations written alongside the
measurement. This runs detector_overrides.install() -- the exact code the app will load --
against the hand-painted correction masks, so the final number describes the shipped
artifact. 1 = crack, 2 = not-crack, 0 = unreviewed (excluded from both).
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


class FakeUP:
    pass


up = FakeUP()
print("install():", DO.install(up), "\n")


def candidates(m):
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); keep = np.where(sz >= 40)[0]
    return np.isin(lab, keep[keep > 0])


names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
               if f.endswith("_correction_mask.png"))
names = [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
LIMIT = int(os.environ.get("NFRAMES", "12"))
A = dict(crack=0, notc=0, s_tp=0, s_fp=0, u_tp=0, u_fp=0, deleted=0, secs=0.0, n=0)
print(f"{'frame':<34} {'painted':>10} | {'v1.48 R':>8} {'union R':>8} | {'DELETES':>8} {'sec':>6}")
print("-" * 86)
for n in names:
    if A["n"] >= LIMIT:
        break
    try:
        img8 = D.load_as_uint8(os.path.join(SEM, "original", n + ".tif"))
        x0, y0, x1, y1 = D.find_field_of_view(img8); img8 = img8[y0:y1, x0:x1]
        corr = np.array(Image.open(os.path.join(PAINT, n + "_correction_mask.png")))
        if corr.ndim == 3:
            corr = corr[..., 0]
        if corr.shape != img8.shape:
            if corr.shape[0] >= y1 and corr.shape[1] >= x1:
                corr = corr[y0:y1, x0:x1]
            else:
                continue
        crack, notc = corr == 1, corr == 2
        if crack.sum() < 20000:
            continue
        flat = D.flatten_background(img8)
        ship = candidates(D.segment_dark_regions(flat, img8=img8))
        t0 = time.time()
        uni = candidates(up.segment_dark_regions(flat, img8=img8))
        dt = time.time() - t0
        c, nn = int(crack.sum()), int(notc.sum())
        dele = int((ship & crack & ~uni).sum())
        for k, v in (("crack", c), ("notc", nn), ("deleted", dele), ("secs", dt), ("n", 1),
                     ("s_tp", int((ship & crack).sum())), ("s_fp", int((ship & notc).sum())),
                     ("u_tp", int((uni & crack).sum())), ("u_fp", int((uni & notc).sum()))):
            A[k] += v
        print(f"{n:<34} {c:>10,} | {int((ship&crack).sum())/c:8.4f} {int((uni&crack).sum())/c:8.4f} | "
              f"{dele:>8,} {dt:6.1f}", flush=True)
    except Exception as e:
        print(f"{n:<34}  ERROR {type(e).__name__}: {e}", flush=True)
print("-" * 86)
print(f"{'POOLED':<34} {A['crack']:>10,} | {A['s_tp']/max(A['crack'],1):8.4f} "
      f"{A['u_tp']/max(A['crack'],1):8.4f} | {A['deleted']:>8,} {A['secs']/max(A['n'],1):6.1f}")
print(f"\n  recall on hand-marked CRACK    {A['s_tp']/max(A['crack'],1):.4f} -> {A['u_tp']/max(A['crack'],1):.4f}"
      f"   (+{A['u_tp']-A['s_tp']:,} px over {A['n']} frames)")
print(f"  rate on hand-marked NOT-crack  {A['s_fp']/max(A['notc'],1):.4f} -> {A['u_fp']/max(A['notc'],1):.4f}"
      f"   (on {A['notc']:,} px -- weak evidence)")
print(f"  hand-marked crack DELETED:     {A['deleted']:,}  ({100*A['deleted']/max(A['crack'],1):.3f}%)")
print(f"  mean union cost per full frame: {A['secs']/max(A['n'],1):.1f} s")
