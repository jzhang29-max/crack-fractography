"""Does the multi-scale VOTE delete hand-marked crack on full frames?

The vote beats everything on all three numbers (P 0.4093 R 0.6652 IoU 0.3394 against the
shipped 0.4033 / 0.5326 / 0.2979) but it is SUBTRACTIVE: requiring a pixel to be dark at
>= 3 of 7 flattening radii can drop a pixel that the single-scale cut kept. That is the
same property that disqualified today's two precision rules, both of which looked better
than this on the tiles and removed 40-43% of hand-marked crack on full frames.

The UNION arm is the control: it is additive by construction, so if the vote's extra
precision turns out to be bought by deleting paint, the union is what ships instead.

Scored on the correction masks (1 = crack, 2 = not-crack, 0 = unreviewed, excluded from
both). Read only -- these are irreplaceable hand labels.
"""
import os, sys
import numpy as np
from scipy import ndimage as ndi
from skimage import filters
from PIL import Image

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code")
sys.dont_write_bytecode = True
import detect_cracks as D
Image.MAX_IMAGE_PIXELS = None
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
SIGMAS = (5, 10, 20, 40, 80, 160, 320)
K_VOTE, NVOTE, K_UNION = 3.0, 3, 5.0   # union now at the SHIPPED k, so it is a strict superset


def candidates(mask):
    lab, _ = ndi.label(D.clean_mask(mask, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sizes = np.bincount(lab.ravel())
    keep = np.where(sizes >= 40)[0]
    return np.isin(lab, keep[keep > 0])


names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
               if f.endswith("_correction_mask.png"))
names = [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
LIMIT = int(os.environ.get("NFRAMES", "8"))

agg = dict(crack=0, notc=0)
for a in ("ship", "vote", "union"):
    agg[a + "_tp"] = 0; agg[a + "_fp"] = 0
agg["vote_deletes"] = 0; agg["union_deletes"] = 0
print(f"{'frame':<34} {'painted':>10} | {'ship R':>7} {'vote R':>7} {'union R':>8} | "
      f"{'VOTE deletes paint':>19} {'UNION deletes':>14}")
print("-" * 118)
done = 0
for n in names:
    if done >= LIMIT:
        break
    try:
        img8 = D.load_as_uint8(os.path.join(SEM, "original", n + ".tif"))
        x0, y0, x1, y1 = D.find_field_of_view(img8)
        img8 = img8[y0:y1, x0:x1]
        corr = np.array(Image.open(os.path.join(PAINT, n + "_correction_mask.png")))
        if corr.ndim == 3:
            corr = corr[..., 0]
        if corr.shape != img8.shape:
            if corr.shape[0] >= y1 and corr.shape[1] >= x1:
                corr = corr[y0:y1, x0:x1]
            else:
                continue
        crack, notc = corr == 1, corr == 2
        if crack.sum() < 50000:
            continue
        sm, stat = {}, {}
        for s in SIGMAS:
            f = D.flatten_background(img8, sigma=s)
            g = filters.gaussian(f, sigma=1.0, preserve_range=True)
            med = float(np.median(g)); mad = float(np.median(np.abs(g - med)) * 1.4826)
            sm[s] = g; stat[s] = dict(otsu=float(filters.threshold_otsu(g)), med=med, mad=mad)
        cut = lambda s, k: sm[s] < min(stat[s]["otsu"], stat[s]["med"] - k * stat[s]["mad"])
        absd = img8 < 10
        ship = candidates(cut(40, 5.0) | absd)
        acc = np.zeros(img8.shape, np.uint8)
        for s in SIGMAS:
            acc += cut(s, K_VOTE).astype(np.uint8)
        vote = candidates((acc >= NVOTE) | absd)
        union = candidates(np.logical_or.reduce([cut(s, K_UNION) for s in SIGMAS]) | absd)
        c, nn = int(crack.sum()), int(notc.sum())
        vd = int((ship & crack & ~vote).sum()); ud = int((ship & crack & ~union).sum())
        agg["crack"] += c; agg["notc"] += nn
        agg["vote_deletes"] += vd; agg["union_deletes"] += ud
        for a, m in (("ship", ship), ("vote", vote), ("union", union)):
            agg[a + "_tp"] += int((m & crack).sum()); agg[a + "_fp"] += int((m & notc).sum())
        print(f"{n:<34} {c:>10,} | {int((ship&crack).sum())/c:7.4f} {int((vote&crack).sum())/c:7.4f} "
              f"{int((union&crack).sum())/c:8.4f} | {vd:>12,} {100*vd/c:5.2f}% {ud:>8,} {100*ud/c:5.2f}%",
              flush=True)
        done += 1
    except Exception as e:
        print(f"{n:<34}  ERROR {type(e).__name__}: {e}", flush=True)
a = agg
print("-" * 118)
print(f"{'POOLED':<34} {a['crack']:>10,} | {a['ship_tp']/max(a['crack'],1):7.4f} "
      f"{a['vote_tp']/max(a['crack'],1):7.4f} {a['union_tp']/max(a['crack'],1):8.4f} | "
      f"{a['vote_deletes']:>12,} {100*a['vote_deletes']/max(a['crack'],1):5.2f}% "
      f"{a['union_deletes']:>8,} {100*a['union_deletes']/max(a['crack'],1):5.2f}%")
print(f"\nhand-marked NOT-crack rate   ship {a['ship_fp']/max(a['notc'],1):.4f}   "
      f"vote {a['vote_fp']/max(a['notc'],1):.4f}   union {a['union_fp']/max(a['notc'],1):.4f}"
      f"   (on only {a['notc']:,} px -- weak evidence)")
print("\nVERDICT")
for arm in ("vote", "union"):
    pct = 100 * a[arm + "_deletes"] / max(a["crack"], 1)
    print(f"  {'SAFE  ' if pct < 0.5 else 'UNSAFE'}  multi-scale {arm:<6} deletes {pct:.2f}% "
          f"of hand-marked crack that the current build keeps")
