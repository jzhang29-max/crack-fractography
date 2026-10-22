"""Can the ranking be improved, and what does each attempt cost in free parameters?

The decomposition says 42.1% of labelled crack on Inconel 718 is not dark at ANY scale --
with both gates wide open, marking 53% of the image, the proposal stage still only reaches
recall 0.579. So the missing recall is not behind a threshold; it is outside what a
darkness threshold can see at all. Tuning cannot reach it.

This prices the alternatives on the SAME set the published ranking uses (the released
crops, where Sauvola local reaches 0.5145 and Sato ridge 0.4985 against the shipped
0.4958), every arm choosing its own parameters leave-one-image-out, exactly as the
baseline table does. The column that matters as much as F1 is `free params`: the paper's
claim is one free parameter and no training, and an arm that wins by spending four of them
has not improved the method, it has changed what the method is.
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import itertools
import numpy as np
from scipy import ndimage as ndi
from skimage import measure as skm, filters
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None

SCR = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
SRC = os.path.join(SCR, "pub_ebc_download/extracted/testsem/Inconel718_crack")


class U:
    pass


u = U()
DO.install(u)


def clean(m):
    lab = skm.label(D.clean_mask(m, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel())
    k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def f1_of(p, g):
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return 2 * pr * rc / max(pr + rc, 1e-12), pr, rc


def load():
    idir, mdir = os.path.join(SRC, "image_cropped"), os.path.join(SRC, "mask_cropped")
    out = []
    for f in sorted(os.listdir(idir)):
        img = np.array(Image.open(os.path.join(idir, f)).convert("L"))
        gt = np.array(Image.open(os.path.join(mdir, f)).convert("L")) > 127
        if img.shape == gt.shape and gt.sum() >= 50:
            out.append((img, gt))
    return out


def dark(im, k):
    return clean(u.segment_dark_regions(D.flatten_background(im), img8=im, mad_k=k))


def sato(im, q):
    r = filters.sato(im.astype(float), sigmas=range(1, 5), black_ridges=True)
    return clean(r >= np.percentile(r, 100 - q))


ARMS = {
    # name: (list of parameter tuples, builder, how many free parameters it spends)
    "SHIPPED: darkness only":
        ([(k,) for k in (5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0)], lambda im, p: dark(im, p[0]), 1),
    "Sato ridge only":
        ([(q,) for q in (0.5, 1, 2, 4, 8)], lambda im, p: sato(im, p[0]), 1),
    "UNION: darkness OR ridge":
        ([(k, q) for k in (5.0, 3.0, 2.0) for q in (0.5, 1, 2, 4)],
         lambda im, p: dark(im, p[0]) | sato(im, p[1]), 2),
    "INTERSECT: darkness AND ridge":
        ([(k, q) for k in (5.0, 3.0, 2.0) for q in (1, 2, 4, 8)],
         lambda im, p: dark(im, p[0]) & sato(im, p[1]), 2),
    "darkness, then ridge-grown":
        ([(k, q) for k in (5.0, 3.0) for q in (1, 2, 4, 8)],
         lambda im, p: clean(ndi.binary_propagation(dark(im, p[0]),
                                                    mask=dark(im, p[0]) | sato(im, p[1]))), 2),
}

data = load()
print(f"{len(data)} Inconel 718 released crops (the set the published ranking uses)\n")
RES = {}
for name, (grid, fn, nparam) in ARMS.items():
    by = {p: [] for p in grid}
    for im, gt in data:
        for p in grid:
            try:
                by[p].append(f1_of(fn(im, p), gt))
            except Exception:
                by[p].append((0.0, 0.0, 0.0))
    n = len(data)
    # leave-one-image-out choice of this arm's own parameters
    loo = []
    for i in range(n):
        best = max(grid, key=lambda p: np.mean([by[p][j][0] for j in range(n) if j != i]))
        loo.append(by[best][i])
    f1 = float(np.mean([x[0] for x in loo]))
    pr = float(np.mean([x[1] for x in loo]))
    rc = float(np.mean([x[2] for x in loo]))
    RES[name] = {"f1": f1, "precision": pr, "recall": rc, "free_params": nparam,
                 "grid_size": len(grid)}
    print(f"  {name:32s} F1 {f1:.4f}  P {pr:.4f}  R {rc:.4f}  "
          f"params {nparam}  grid {len(grid)}", flush=True)

print(f"\n{'arm':34s} {'F1':>7s} {'recall':>8s} {'params':>7s}  verdict")
TARGET = 0.5145   # Sauvola local, the leader on this set
for name, r in sorted(RES.items(), key=lambda kv: -kv[1]["f1"]):
    v = "BEATS Sauvola" if r["f1"] > TARGET else "below Sauvola"
    print(f"{name:34s} {r['f1']:7.4f} {r['recall']:8.4f} {r['free_params']:7d}  {v}")

out = os.path.join(REPO, "docs/figures/recall_fix_attempts.json")
json.dump({"set": "Inconel 718 released crops", "n": len(data),
           "selection": "each arm's own parameters, leave-one-image-out",
           "target_to_beat": {"Sauvola local": TARGET, "Sato ridge": 0.4985},
           "arms": RES,
           "why": "42.1% of labelled crack is not dark at any scale, so the missing recall "
                  "is outside what a darkness threshold can reach; these arms price the "
                  "alternatives in free parameters as well as in F1"},
          open(out, "w"), indent=1)
print("\nwrote", out)
