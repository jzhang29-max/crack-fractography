"""Every array the walkthrough document needs, from one real frame, saved once.

The frame is 260622_316_H_b2_front_CBS_01 at 42.15 nm/px -- one of the two 316 plan views
that carry BOTH a crack and visible grain contrast, which is what the flank measurement
needs. Numbers are computed on the WHOLE frame so they are frame-scale; the document draws
them on a crop and says so.

Nothing here is invented or redrawn: every panel is an array this pipeline actually
produces, at the settings the pipeline actually uses.
"""
import json
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

OUT = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/flow")
STEM, NM = "260622_316_H_b2_front_CBS_01", 42.15
STANDOFF = 2
# the partition that cleared the controls in the earlier sweep
SMOOTH, HREL = 40, 1.0

print("loading", flush=True)
img = np.array(Image.open(f"{SEM}/original/{STEM}.tif")).astype(np.float32)[:4096]
crack = np.array(Image.open(
    f"{SEM}/crack_export/derived/machine_masks/{STEM}_machine.png").convert("L")) < 128
h = min(img.shape[0], crack.shape[0])
img, crack = img[:h], crack[:h]
print(f"  frame {img.shape}, crack {100 * crack.mean():.2f}% of it", flush=True)

# ---- the grain partition, exactly as the flank runs used it -------------------------
print("grain partition", flush=True)
flat = img - ndi.gaussian_filter(img, 200)
f = flat.copy()
f[crack] = np.median(flat[~crack])
grad = filters.sobel(ndi.gaussian_filter(f, SMOOTH))
mk = ndi.label(morphology.h_minima(grad, HREL * grad.std()),
               structure=np.ones((3, 3)))[0]
grains = segmentation.watershed(grad, mk, mask=~crack)
geom = CM.grain_geometry(grains, NM)
print(f"  {geom.get('n_grains')} grains, median diameter "
      f"{geom.get('median_grain_diameter_um', 0):.2f} um", flush=True)

# ---- the skeleton graph, and the counts at each stage -------------------------------
print("skeleton graph", flush=True)
reg_mask, reg = CM.regularise(crack, CM.REGULARISE_PX)
skel = morphology.skeletonize(reg_mask)
cand, _nb = CM._junction_candidates(skel)
jlab, nj = ndi.label(cand, structure=np.ones((3, 3), np.uint8))
g = CM._skeleton_graph(crack)
census = CM._census_from_graph(g)
print(f"  centreline {int(skel.sum()):,} px; candidate junction pixels "
      f"{int(cand.sum()):,}; clusters {int(nj):,}; nodes kept "
      f"{len(g['nodes'][0]):,}", flush=True)

# ---- the flanks ----------------------------------------------------------------------
print("flanks", flush=True)
geo = CM.flank_geometry(crack)
fl = CM.flank_ids(crack, grains, standoff_px=STANDOFF, geometry=geo)
dec = fl["decidable"]
same = fl["same_grain"]
print(f"  centreline points {dec.size:,}; decidable {100 * dec.mean():.1f}%; "
      f"of those, different grains either side "
      f"{100 * (~same[dec]).mean():.1f}%", flush=True)

# ---- the controls ---------------------------------------------------------------------
print("controls (slow)", flush=True)
ctl = CM.flank_controls(crack, grains, standoff_px=STANDOFF, n_null=60, n_reps=6)
rd = CM.read_flank_controls(ctl)
print(f"  positive {ctl.get('positive_control')}  negative "
      f"{ctl.get('negative_control')}  Z' {ctl.get('z_prime')}  "
      f"quotable {rd['quotable']}", flush=True)

# ---- a crop where the document can actually be read ------------------------------------
# the densest window of centreline, kept off the frame edge
W = 900
dens = ndi.uniform_filter(skel.astype(np.float32), W)
m = W // 2 + 40
dens[:m, :] = dens[-m:, :] = dens[:, :m] = dens[:, -m:] = -1.0
cy, cx = (int(v) for v in np.unravel_index(int(np.argmax(dens)), dens.shape))
y0 = int(np.clip(cy - W // 2, 0, img.shape[0] - W))
x0 = int(np.clip(cx - W // 2, 0, img.shape[1] - W))
sl = (slice(y0, y0 + W), slice(x0, x0 + W))
print(f"  crop {W} px at ({y0}, {x0})", flush=True)

ys, xs = g["nodes"][0], g["nodes"][1]
nodes_in = [(int(a), int(b)) for a, b in zip(ys, xs)
            if y0 <= a < y0 + W and x0 <= b < x0 + W]
jy, jx = np.nonzero(jlab[sl] > 0)

np.savez_compressed(
    os.path.join(OUT, "arrays.npz"),
    img=img[sl].astype(np.float32),
    img_small=img[::8, ::8].astype(np.float32),
    crack=crack[sl], crack_small=crack[::8, ::8],
    reg=reg_mask[sl], skel=skel[sl], cand=cand[sl],
    jlab=(jlab[sl] > 0),
    branches=g["branch_labels"][sl],
    grains=grains[sl],
    fys=fl["ys"], fxs=fl["xs"], fdec=dec, fsame=same,
    nodes=np.array(nodes_in, int).reshape(-1, 2),
    crop=np.array([y0, x0, W]),
)
json.dump({
    "stem": STEM, "nm_per_px": NM, "standoff_px": STANDOFF,
    "frame_px": [int(img.shape[0]), int(img.shape[1])],
    "crop": [int(y0), int(x0), int(W)],
    "crack_pct_of_frame": float(100 * crack.mean()),
    "centreline_px": int(skel.sum()),
    "candidate_junction_px": int(cand.sum()),
    "clusters": int(nj),
    "nodes_kept": int(len(g["nodes"][0])),
    "resolve_passes": int(g.get("resolve_passes", 0)),
    "regularise": reg,
    "census": census,
    "grains": {k: geom.get(k) for k in
               ("n_grains", "median_grain_diameter_um", "median_grain_area_um2")},
    "flank": {"points": int(dec.size), "decidable_pct": float(100 * dec.mean()),
              "different_grain_pct_of_decidable":
                  float(100 * (~same[dec]).mean()) if dec.any() else None},
    "controls": ctl, "verdict": rd,
}, open(os.path.join(OUT, "facts.json"), "w"), indent=1, default=str)
print("\nwrote arrays.npz and facts.json")
