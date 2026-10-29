"""Re-extract the walkthrough panels at a crop a reader can actually read.

The first crop maximised centreline density, which put the window INSIDE a near-solid
crack region: the panels came out as flat blue and flat black with no metal visible. The
rule now also requires the window to contain METAL -- the crack must cover between 12% and
45% of it -- so the reader can see the crack against the material it is in. Among windows
that qualify, the one with the most centreline wins.

Everything expensive (the controls) is reused from facts.json; only the arrays are redone.
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

F = json.load(open(os.path.join(OUT, "facts.json")))
STEM, NM, SO = F["stem"], F["nm_per_px"], F["standoff_px"]
W = 1100
LO, HI = 0.12, 0.45          # the crack must be this share of the window

img = np.array(Image.open(f"{SEM}/original/{STEM}.tif")).astype(np.float32)[:4096]
crack = np.array(Image.open(
    f"{SEM}/crack_export/derived/machine_masks/{STEM}_machine.png").convert("L")) < 128
h = min(img.shape[0], crack.shape[0]); img, crack = img[:h], crack[:h]
flat = img - ndi.gaussian_filter(img, 200)
fb = flat.copy(); fb[crack] = np.median(flat[~crack])
grad = filters.sobel(ndi.gaussian_filter(fb, 40))
mk = ndi.label(morphology.h_minima(grad, 1.0 * grad.std()), structure=np.ones((3, 3)))[0]
grains = segmentation.watershed(grad, mk, mask=~crack)
reg_mask, reg = CM.regularise(crack, CM.REGULARISE_PX)
skel = morphology.skeletonize(reg_mask)
cand, _ = CM._junction_candidates(skel)
jlab, nj = ndi.label(cand, structure=np.ones((3, 3), np.uint8))
g = CM._skeleton_graph(crack)
geo = CM.flank_geometry(crack)
fl = CM.flank_ids(crack, grains, standoff_px=SO, geometry=geo)

frac = ndi.uniform_filter(crack.astype(np.float32), W)
dens = ndi.uniform_filter(skel.astype(np.float32), W)
m = W // 2 + 30
ok = (frac >= LO) & (frac <= HI)
ok[:m, :] = ok[-m:, :] = ok[:, :m] = ok[:, -m:] = False
if not ok.any():
    raise SystemExit("no window holds between 12% and 45% crack -- widen the band")
score = np.where(ok, dens, -1.0)
cy, cx = (int(v) for v in np.unravel_index(int(np.argmax(score)), score.shape))
y0 = int(np.clip(cy - W // 2, 0, img.shape[0] - W))
x0 = int(np.clip(cx - W // 2, 0, img.shape[1] - W))
sl = (slice(y0, y0 + W), slice(x0, x0 + W))
print(f"crop {W} px at ({y0}, {x0}); the window is "
      f"{100 * crack[sl].mean():.1f}% crack and holds "
      f"{int(skel[sl].sum()):,} centreline dots and "
      f"{int((jlab[sl] > 0).sum()):,} candidate junction dots")

ys, xs = g["nodes"][0], g["nodes"][1]
nodes_in = [(int(a), int(b)) for a, b in zip(ys, xs)
            if y0 <= a < y0 + W and x0 <= b < x0 + W]
print(f"  {len(nodes_in)} kept meeting points fall inside it")

np.savez_compressed(
    os.path.join(OUT, "arrays.npz"),
    img=img[sl].astype(np.float32), img_small=img[::8, ::8].astype(np.float32),
    crack=crack[sl], crack_small=crack[::8, ::8],
    reg=reg_mask[sl], skel=skel[sl], cand=cand[sl], jlab=(jlab[sl] > 0),
    branches=g["branch_labels"][sl], grains=grains[sl],
    fys=fl["ys"], fxs=fl["xs"], fdec=fl["decidable"], fsame=fl["same_grain"],
    nodes=np.array(nodes_in, int).reshape(-1, 2), crop=np.array([y0, x0, W]))
F["crop"] = [y0, x0, W]
F["crop_rule"] = (f"the {W}-pixel window with the most centreline among those that are "
                  f"between {100*LO:.0f}% and {100*HI:.0f}% crack, so that metal is "
                  f"visible beside it")
F["crop_crack_pct"] = float(100 * crack[sl].mean())
json.dump(F, open(os.path.join(OUT, "facts.json"), "w"), indent=1, default=str)
print("rewrote arrays.npz and facts.json")
