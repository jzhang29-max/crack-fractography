"""THE FULL-FRAME PAINT GATE for approach 3. State the deletion number before any gain.

The operator is `mask = shipped | added`, so it cannot delete and the gate's number is 0
by construction. That is an argument, not a measurement, and six rules have died here on
the difference. So this ASSERTS it per frame on the real micrographs at full size,
against the hand paint, and fails loudly if any frame loses a single painted pixel.

It also reports the number the gate CAN answer for an additive arm: the PURITY of what
was added -- added hand-marked crack against added hand-marked not-crack, over reviewed
pixels only. Unreviewed pixels (91% of the corpus) are excluded from numerator and
denominator; counting them either way invents a result.

    1 = hand-marked CRACK      -> losing one is the disqualifying harm
    2,3 = hand-marked NOT-crack / ERASE
    0 = UNREVIEWED             -> excluded

The paint under sem-crack-detector/interior_active_learning is irreplaceable hand label
and is opened READ ONLY. Nothing here writes outside the scratchpad.

Env: NFRAMES to limit, OUT for the json path.
"""
import os, sys, json, time, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C, ctx_method as M
from ctx_matched import grow_to_area, dilate_to_area
import numpy as np, tifffile
from scipy import ndimage as ndi
from skimage import exposure, filters
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
import detect_cracks as D
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/interior_active_learning/code")
from common import contrast_kwargs_for

SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
ALPHA = 1.0          # the multiple leave-one-specimen-out selected for the context arm


def load_frame(name):
    raw = tifffile.imread(os.path.join(SEM, "original", name + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    ck = contrast_kwargs_for(name)
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]
    del raw
    corr = np.array(Image.open(os.path.join(PAINT, name + "_correction_mask.png")))
    while corr.ndim > 2:
        corr = corr[..., 0]
    if corr.shape != img8.shape:
        if corr.shape[0] >= y1 and corr.shape[1] >= x1:
            corr = corr[y0:y1, x0:x1]
        else:
            return None
    return img8, corr


def main():
    names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
                   if f.endswith("_correction_mask.png"))
    names = [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
    names = names[:int(os.environ.get("NFRAMES", "0")) or len(names)]
    out_path = os.environ.get("OUT", os.path.join(C.MY, "gate.json"))
    print(f"{len(names)} frames have both a micrograph and a correction mask\n", flush=True)
    rows, t0 = [], time.time()
    for i, n in enumerate(names, 1):
        try:
            got = load_frame(n)
        except Exception as e:
            print(f"[{i}/{len(names)}] {n}  ERROR {type(e).__name__}: {e}", flush=True)
            rows.append(dict(frame=n, error=f"{type(e).__name__}: {e}")); continue
        if got is None:
            print(f"[{i}/{len(names)}] {n}  SKIPPED (paint does not fit)", flush=True)
            rows.append(dict(frame=n, error="shape_mismatch")); continue
        img8, corr = got
        crack, notc = corr == 1, (corr == 2) | (corr == 3)
        del corr
        flat = D.flatten_background(img8)
        sm = filters.gaussian(flat, sigma=1.0, preserve_range=True)
        ship = C.cand(C.SEG(flat, img8=img8))
        kept = int((ship & crack).sum())
        fr = filters.frangi(flat.astype(float), sigmas=range(1, 7), black_ridges=True)
        cost = M.cost_field(sm, fr)
        del fr, sm, flat
        e = int(round(ALPHA * ship.sum()))
        ctx, _ = grow_to_area(ship, cost, e)
        del cost
        dil = dilate_to_area(ship, e)
        rec = dict(frame=n, shape=list(img8.shape), painted_crack=int(crack.sum()),
                   painted_notc=int(notc.sum()), shipped_kept=kept, arms={})
        for nm, m in (("CONTEXT", ctx), ("DILATE null", dil)):
            rec["arms"][nm] = dict(
                deleted=int((ship & ~m & crack).sum()),
                added_crack=int((m & ~ship & crack).sum()),
                added_notc=int((m & ~ship & notc).sum()),
                added_area=int((m & ~ship).sum()))
        rows.append(rec)
        msg = "  ".join(f"{nm} del {rec['arms'][nm]['deleted']:,} "
                        f"({100*rec['arms'][nm]['deleted']/max(kept,1):.2f}%)"
                        for nm in rec["arms"])
        print(f"[{i}/{len(names)}] {n:<34} painted {rec['painted_crack']:>10,} "
              f"kept {kept:>10,} | {msg}  {time.time()-t0:5.0f}s", flush=True)
        json.dump(rows, open(out_path, "w"))
        del img8, crack, notc, ship, ctx, dil
    json.dump(rows, open(out_path, "w"))

    good = [r for r in rows if "arms" in r]
    kt = sum(r["shipped_kept"] for r in good)
    print("\n" + "=" * 92)
    print(f"{len(good)} frames scored, {kt:,} hand-painted crack px kept by the shipped path\n")
    print(f"{'arm':<14} {'DELETED':>12} {'% of kept':>10} {'frames >1%':>11} "
          f"{'added crack':>13} {'added notc':>11} {'purity':>8}")
    for nm in ("CONTEXT", "DILATE null"):
        d = sum(r["arms"][nm]["deleted"] for r in good)
        over = sum(1 for r in good
                   if r["arms"][nm]["deleted"] > 0.01 * max(r["shipped_kept"], 1))
        ac = sum(r["arms"][nm]["added_crack"] for r in good)
        an = sum(r["arms"][nm]["added_notc"] for r in good)
        print(f"{nm:<14} {d:>12,} {100*d/max(kt,1):9.4f}% {over:>11} {ac:>13,} {an:>11,} "
              f"{ac/max(ac+an,1):8.4f}")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
