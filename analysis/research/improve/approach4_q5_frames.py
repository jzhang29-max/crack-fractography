"""Q5 -- DOES THE TILE CEILING SURVIVE AT FRAME SCALE? The 48 hand-painted frames.

Q1 measured the ceiling on 26 crops of 512 px. The product does not run on crops. If the
paint on a whole frame is far wider than the paint on a crop -- and the brief says it is,
192 px against roughly 12 -- then the trace width that maximises IoU is a different number
at the two scales, and any method tuned for IoU on tiles is tuned for the wrong thickness
where it actually runs.

READ ONLY. Nothing here opens a file for writing under sem-crack-detector, and this script
produces no mask, so it cannot delete a hand label. Correction-mask values follow
interior_candidates.apply_pixel_corrections: 1 = force CRACK, 2 = force NOT-crack,
3 = erase, 0 = unreviewed. Only 1 is used.

The curve is computed from one chessboard distance transform per frame rather than by
repeated dilation: a pixel is inside the width-(2r+1) trace exactly when its chessboard
distance to the centreline is <= r, which is what r iterations of a 3x3 square dilation
means. One pass gives every width at once.
"""
import os, sys, json, glob
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import approach4_lib as L

Image.MAX_IMAGE_PIXELS = None
PAINT = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/interior_active_learning/paint"
RADII = list(range(0, 301))


def main():
    files = sorted(glob.glob(os.path.join(PAINT, "*_correction_mask.png")))
    print(f"{len(files)} hand-painted correction masks (read only)\n")
    hin = np.zeros(len(RADII) + 1, np.int64)
    hout = np.zeros(len(RADII) + 1, np.int64)
    total_gt = 0
    per = []
    for i, f in enumerate(files, 1):
        a = np.array(Image.open(f))
        gt = a == 1
        n = int(gt.sum())
        if n == 0:
            print(f"  [{i}/{len(files)}] {os.path.basename(f)[:46]:<46} no painted crack")
            continue
        sk = skeletonize(gt)
        ns = int(sk.sum())
        d = ndi.distance_transform_cdt(~sk, metric="chessboard")
        d = np.clip(d, 0, len(RADII))
        hin += np.bincount(d[gt].ravel(), minlength=len(RADII) + 1)[:len(RADII) + 1]
        hout += np.bincount(d[~gt].ravel(), minlength=len(RADII) + 1)[:len(RADII) + 1]
        total_gt += n
        per.append(dict(frame=os.path.basename(f), area=n, skel=ns, mean_width=n / max(ns, 1)))
        print(f"  [{i}/{len(files)}] {os.path.basename(f)[:46]:<46} "
              f"paint {n:>10,} px  centreline {ns:>8,} px  mean width {n / max(ns, 1):7.1f} px",
              flush=True)

    w = np.array([p["mean_width"] for p in per])
    print(f"\nPAINT WIDTH ON FULL FRAMES ({len(per)} frames with paint, {total_gt:,} px)")
    print(f"  median {np.median(w):.1f} px   mean {w.mean():.1f} px   "
          f"range {w.min():.1f} - {w.max():.1f} px")
    print(f"  pooled (total area / total centreline): "
          f"{total_gt / sum(p['skel'] for p in per):.1f} px")

    cin = np.cumsum(hin); cout = np.cumsum(hout)
    print("\nA PERFECTLY PLACED TRACE AT FRAME SCALE (pooled over all 48 frames)")
    print(f"  {'trace width':>12}{'prec':>9}{'recall':>9}{'F1':>9}{'IoU':>9}")
    curve = []
    for r in RADII:
        tp = int(cin[r]); fp = int(cout[r]); fn = total_gt - tp
        p = tp / max(tp + fp, 1); rec = tp / max(total_gt, 1)
        c = dict(width=2 * r + 1, precision=p, recall=rec, iou=tp / max(tp + fp + fn, 1),
                 f1=2 * p * rec / max(p + rec, 1e-12))
        curve.append(c)
        if c["width"] in (1, 3, 5, 11, 21, 41, 61, 81, 101, 151, 201, 301, 401, 501, 601):
            print(f"  {c['width']:>12}{p:9.4f}{rec:9.4f}{c['f1']:9.4f}{c['iou']:9.4f}")
    best = max(curve, key=lambda c: c["iou"])
    bf1 = max(curve, key=lambda c: c["f1"])
    print(f"\n  IoU is maximised at width {best['width']} px: IoU {best['iou']:.4f}")
    print(f"  F1  is maximised at width {bf1['width']} px: F1 {bf1['f1']:.4f}")
    t3 = curve[1]
    print(f"  a 3 px trace scores IoU {t3['iou']:.4f} -- {best['iou'] / max(t3['iou'], 1e-9):.0f}x "
          f"below the same perfectly placed answer drawn at {best['width']} px")

    q1 = json.load(open(os.path.join(L.WORK, "q1_ceiling.json")))
    tb = max(q1["curve"], key=lambda c: c["iou"])
    print(f"\n  THE TWO SCALES DISAGREE ABOUT HOW THICK TO DRAW:")
    print(f"    512 px tiles : IoU peaks at width {tb['width']:>3} px (IoU {tb['iou']:.4f})")
    print(f"    full frames  : IoU peaks at width {best['width']:>3} px (IoU {best['iou']:.4f})")
    print(f"    ratio {best['width'] / tb['width']:.0f}x. A predictor tuned to maximise IoU on the")
    print(f"    tiles is tuned to draw {best['width'] / tb['width']:.0f}x too thin for the frames it runs on.")

    json.dump(dict(per=per, curve=curve, total_gt=int(total_gt)),
              open(os.path.join(L.WORK, "q5_frames.json"), "w"), indent=1)
    print("\nwrote", os.path.join(L.WORK, "q5_frames.json"))


if __name__ == "__main__":
    main()
