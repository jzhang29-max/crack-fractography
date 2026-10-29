"""The decisive form: decidability is GEOMETRIC, so both arms see identical pixels.

Three populations have now been used for this null and all three are defensible-sounding:

  the library     recomputes decidability under each SHIFTED map. That admits points lying
                  inside the real crack, where the two flanks are far apart and land in
                  different grains whatever map is read, so the null is inflated by exactly
                  the width effect under study. Null 28.5%, z = 0.52.
  my first run    requires decidability under BOTH maps, conditioning on a property of the
                  shifted map. Null 7.9%, z large.
  this file       removes the confound instead of choosing between them.

The grain map is made TOTAL before anything is shifted: the crack region, which the
watershed leaves unlabelled, is filled with its nearest grain label. A total map has no
unlabelled region to wander into, so a point is decidable if and only if both of its flank
samples are inside the frame and outside the real crack -- a property of the CRACK's
geometry alone, identical for the real map and for every shift of it.

The real reading cannot be changed by the fill, because its flank samples are outside the
crack by construction. Only the null changes, and it changes by becoming evaluable at the
same pixels the real reading uses.

Both arms are then also reported WIDTH-RESOLVED, because the whole reason the three
populations disagreed is that the statistic depends on crack opening.
"""
import json, os, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import filters, morphology, segmentation
Image.MAX_IMAGE_PIXELS = None
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
OUT = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/flow")
sys.path.insert(0, os.path.join(REPO, "analysis")); sys.dont_write_bytecode = True
import crackmode as CM

SO, N_SHIFT, MIN_PTS = 2, 48, 400
FRAMES = [("260622_316_H_b2_front_CBS_01", 42.15),
          ("260622_316_H_b2_front_CBS_02", 28.16)]
PARTS = [(20, 0.4), (30, 0.6), (40, 1.0)]
BINS = np.array([0.0, 0.05, 0.1, 0.2, 0.35, 0.5, 1e9])

RES = {}
for stem, nm in FRAMES:
    img = np.array(Image.open(f"{SEM}/original/{stem}.tif")).astype(np.float32)[:4096]
    crack = np.array(Image.open(
        f"{SEM}/crack_export/derived/machine_masks/{stem}_machine.png").convert("L")) < 128
    h = min(img.shape[0], crack.shape[0]); img, crack = img[:h], crack[:h]
    flat = img - ndi.gaussian_filter(img, 200)
    fb = flat.copy(); fb[crack] = np.median(flat[~crack])
    geo = CM.flank_geometry(crack); mask = geo["mask"]
    H, W = mask.shape
    ys, xs, n, ey, ex = geo["ys"], geo["xs"], geo["wall_dist"], geo["ey"], geo["ex"]
    off = n + SO
    ay = np.rint(ys + ey * off).astype(int); ax = np.rint(xs + ex * off).astype(int)
    by = np.rint(ys - ey * off).astype(int); bx = np.rint(xs - ex * off).astype(int)
    inside = ((ay >= 0) & (ay < H) & (ax >= 0) & (ax < W)
              & (by >= 0) & (by < H) & (bx >= 0) & (bx < W))
    ay, ax, by, bx = ay[inside], ax[inside], by[inside], bx[inside]
    # DECIDABLE = geometric only. No grain map appears in this condition.
    use = ~mask[ay, ax] & ~mask[by, bx]
    halfw_um = n[inside] * nm / 1000.0
    print(f"\n=== {stem}   usable points {int(use.sum()):,} of {int(inside.sum()):,} "
          f"({100 * use.mean():.1f}%, geometric criterion only)", flush=True)
    ay, ax, by, bx = ay[use], ax[use], by[use], bx[use]
    halfw_um = halfw_um[use]

    for smooth, hrel in PARTS:
        grad = filters.sobel(ndi.gaussian_filter(fb, smooth))
        mk = ndi.label(morphology.h_minima(grad, hrel * grad.std()),
                       structure=np.ones((3, 3)))[0]
        g = segmentation.watershed(grad, mk, mask=~crack)
        D = CM.grain_geometry(g, nm)["median_grain_diameter_um"]
        # make the map TOTAL: fill the unlabelled crack region with its nearest grain label
        _d, (iy, ix) = ndi.distance_transform_edt(g == 0, return_indices=True)
        gt = g[iy, ix]
        assert (gt != 0).all(), "the filled map still has unlabelled pixels"
        ratio = 2.0 * halfw_um / D

        real = 100.0 * (gt[ay, ax] != gt[by, bx]).mean()
        rng = np.random.default_rng(0)
        nulls = []
        bn = {i: [0, 0] for i in range(len(BINS) - 1)}
        for _ in range(N_SHIFT):
            sy = int(rng.integers(H // 12, H - H // 12))
            sx = int(rng.integers(W // 12, W - W // 12))
            g2 = np.roll(gt, (sy, sx), axis=(0, 1))
            d2 = (g2[ay, ax] != g2[by, bx])
            nulls.append(100.0 * d2.mean())
            for i in range(len(BINS) - 1):
                sel = (ratio >= BINS[i]) & (ratio < BINS[i + 1])
                if sel.sum():
                    bn[i][0] += int(d2[sel].sum()); bn[i][1] += int(sel.sum())
        nulls = np.array(nulls)
        z = (real - nulls.mean()) / max(nulls.std(ddof=1), 1e-9)
        print(f"  partition {D:.2f} um   real {real:.2f}%   shifted {nulls.mean():.2f}% "
              f"(sd {nulls.std(ddof=1):.2f}, {N_SHIFT} shifts, range "
              f"{nulls.min():.1f}-{nulls.max():.1f})   z = {z:+.1f}", flush=True)
        rows = []
        print(f"    {'opening/grain':>14} {'points':>9} {'real%':>8} {'shifted%':>9} "
              f"{'gap pp':>8}", flush=True)
        for i in range(len(BINS) - 1):
            sel = (ratio >= BINS[i]) & (ratio < BINS[i + 1])
            if sel.sum() < MIN_PTS:
                continue
            r = 100.0 * (gt[ay[sel], ax[sel]] != gt[by[sel], bx[sel]]).mean()
            q = 100.0 * bn[i][0] / bn[i][1]
            hi = "inf" if BINS[i + 1] > 1e8 else f"{BINS[i+1]:.2f}"
            print(f"    {BINS[i]:>6.2f}-{hi:<7} {int(sel.sum()):>9,} {r:>7.1f}% "
                  f"{q:>8.1f}% {r - q:>+7.1f}", flush=True)
            rows.append({"lo": float(BINS[i]), "hi": float(BINS[i + 1]),
                         "points": int(sel.sum()), "real_pct": r, "shifted_pct": q,
                         "gap_pp": r - q})
        RES[f"{stem}|{D:.2f}"] = {"frame": stem, "grain_um": float(D),
                                  "real_pct": float(real),
                                  "shifted_mean_pct": float(nulls.mean()),
                                  "shifted_sd": float(nulls.std(ddof=1)),
                                  "n_shifts": N_SHIFT, "z": float(z),
                                  "usable_points": int(len(ay)), "bins": rows}
json.dump(RES, open(os.path.join(OUT, "decisive.json"), "w"), indent=1)
print("\nwrote decisive.json")
