"""The shifted-grain-map null, computed two ways on the same frame and the same shifts.

`_flank_share` offsets the sampling coordinates and then np.clip()s them back inside the
frame. That is not a torus shift. A torus shift wraps: a point leaving the right edge comes
back at the left, so every grain keeps its size and shape and the map stays stationary in
the sense the test requires (Harms et al. 2001). Clipping instead PINS every out-of-range
point onto the border, so a large share of the null's sample is evaluated at one row or
column of the map rather than at a random place in it.

This measures both, on identical shifts, and reports what fraction of points clipping moves
to the border.
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import filters, morphology, segmentation

Image.MAX_IMAGE_PIXELS = None
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.dont_write_bytecode = True
import crackmode as CM

STEM, NM, STANDOFF = "260622_316_H_b2_front_CBS_01", 42.15, 2
img = np.array(Image.open(f"{SEM}/original/{STEM}.tif")).astype(np.float32)[:4096]
crack = np.array(Image.open(
    f"{SEM}/crack_export/derived/machine_masks/{STEM}_machine.png").convert("L")) < 128
h = min(img.shape[0], crack.shape[0]); img, crack = img[:h], crack[:h]
flat = img - ndi.gaussian_filter(img, 200)
f = flat.copy(); f[crack] = np.median(flat[~crack])
grad = filters.sobel(ndi.gaussian_filter(f, 40))
mk = ndi.label(morphology.h_minima(grad, 1.0 * grad.std()), structure=np.ones((3, 3)))[0]
grains = segmentation.watershed(grad, mk, mask=~crack)
geo = CM.flank_geometry(crack)
mask = geo["mask"]
H, W = grains.shape

ys, xs, n, ey, ex = geo["ys"], geo["xs"], geo["wall_dist"], geo["ey"], geo["ex"]
off = n + STANDOFF
pay = np.rint(ys + ey * off).astype(int); pax = np.rint(xs + ex * off).astype(int)
pby = np.rint(ys - ey * off).astype(int); pbx = np.rint(xs - ex * off).astype(int)
inside = ((pay >= 0) & (pay < H) & (pax >= 0) & (pax < W)
          & (pby >= 0) & (pby < H) & (pbx >= 0) & (pbx < W))
pay, pax, pby, pbx = pay[inside], pax[inside], pby[inside], pbx[inside]

real, nd_r, _ = CM._flank_share(grains, geo, STANDOFF, (0,))
print(f"real intergranular share {real:.2f}%  ({nd_r:,} decidable)\n")
print(f"{'shift (dy,dx)':>16} {'clip %':>8} {'roll %':>8} {'clipped pts':>12} "
      f"{'of sample':>10}")
rng = np.random.default_rng(0)
cl, rl = [], []
for _ in range(12):
    sy = int(rng.integers(H // 10, H - H // 10))
    sx = int(rng.integers(W // 10, W - W // 10))
    # --- as shipped: offset then clip
    ay = np.clip(pay + sy, 0, H - 1); ax = np.clip(pax + sx, 0, W - 1)
    by = np.clip(pby + sy, 0, H - 1); bx = np.clip(pbx + sx, 0, W - 1)
    ga, gb = grains[ay, ax], grains[by, bx]
    ok = (ga != 0) & (gb != 0)
    c = 100.0 * (ga[ok] != gb[ok]).sum() / max(ok.sum(), 1)
    pinned = int(((pay + sy > H - 1) | (pax + sx > W - 1)
                  | (pby + sy > H - 1) | (pbx + sx > W - 1)).sum())
    # --- a real torus shift: roll the map, sample at the untouched coordinates
    g2 = np.roll(grains, (sy, sx), axis=(0, 1))
    ga2, gb2 = g2[pay, pax], g2[pby, pbx]
    ok2 = (ga2 != 0) & (gb2 != 0)
    r = 100.0 * (ga2[ok2] != gb2[ok2]).sum() / max(ok2.sum(), 1)
    cl.append(c); rl.append(r)
    print(f"  ({sy:>5},{sx:>5}) {c:>8.2f} {r:>8.2f} {pinned:>12,} "
          f"{100.0 * pinned / pay.size:>9.1f}%")

print(f"\n  clip (as shipped)  mean {np.mean(cl):.2f}%  sd {np.std(cl, ddof=1):.2f}")
print(f"  roll (torus shift) mean {np.mean(rl):.2f}%  sd {np.std(rl, ddof=1):.2f}")
print(f"  real                    {real:.2f}%")
print(f"\n  z against clip  {(real - np.mean(cl)) / max(np.std(cl, ddof=1), 1e-9):+.2f}")
print(f"  z against roll  {(real - np.mean(rl)) / max(np.std(rl, ddof=1), 1e-9):+.2f}")
