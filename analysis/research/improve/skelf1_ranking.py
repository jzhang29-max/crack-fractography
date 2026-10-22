"""Re-rank every arm under a metric that width cannot buy.

The ranking on this dataset can be lifted without detecting anything. Dilating the shipped
mask -- two parameters, no new evidence, a morphological operation that cannot find a crack
it did not already have -- scores F1 0.6307 on the released crops against Sauvola's 0.5145
and the shipped 0.4958. It would rank first by a wide margin while marking 7.05% of the
image against a labelled 4.53%. Pixel F1 against a broad-brush label rewards covering the
brush, and covering the brush is free.

So the ranking question has to be asked under a metric that is blind to width. This scores
every arm by skeleton F1: both masks are reduced to centrelines, a predicted centreline
pixel counts if it lies within tau of the labelled centreline, and a labelled centreline
pixel counts if some predicted centreline lies within tau of it. Widening a mask leaves its
centreline where it was, so the dilation decoy is carried through every table as the proof
that the metric is not buyable -- an arm that still wins by dilating would mean this metric
is gameable too and the whole comparison needs rethinking again.

Two tolerances are reported because tolerance is not a free choice: on a corpus whose
labels are painted at a 25.8 px stroke, declaring a 2 px tolerance asserts a localisation
precision the label does not have.
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
import numpy as np
from scipy import ndimage as ndi
from skimage import measure as skm, filters, morphology as morph
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None

SCR = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
CROPS = os.path.join(SCR, "pub_ebc_download/extracted/testsem/Inconel718_crack")
FIELDS = os.path.join(SCR, "pub_ebc_download/train_subset/Inconel718_crack")
TAUS = (2, 5)


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


def skel_f1(p, g, tau):
    """Centreline agreement within tau. Blind to how wide either mask is drawn."""
    sp, sg = morph.skeletonize(np.asarray(p, bool)), morph.skeletonize(np.asarray(g, bool))
    if not sp.any() or not sg.any():
        return 0.0, 0.0, 0.0
    dg = ndi.distance_transform_edt(~sg)      # distance to the labelled centreline
    dp = ndi.distance_transform_edt(~sp)      # distance to the predicted centreline
    pr = float((dg[sp] <= tau).mean())
    rc = float((dp[sg] <= tau).mean())
    return (2 * pr * rc / max(pr + rc, 1e-12)), pr, rc


def pixel_f1(p, g):
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return 2 * pr * rc / max(pr + rc, 1e-12)


def ridge(im, sig, q, kind):
    f = {"frangi": filters.frangi, "sato": filters.sato, "meijering": filters.meijering}[kind]
    r = f(im.astype(float), sigmas=sig, black_ridges=True)
    return clean(r >= np.percentile(r, 100 - q))


def load_crops():
    idir, mdir = os.path.join(CROPS, "image_cropped"), os.path.join(CROPS, "mask_cropped")
    out = []
    for f in sorted(os.listdir(idir)):
        im = np.array(Image.open(os.path.join(idir, f)).convert("L"))
        gt = np.array(Image.open(os.path.join(mdir, f)).convert("L")) > 127
        if im.shape == gt.shape and gt.sum() >= 50:
            out.append((im, gt))
    return out


def load_fields():
    mdir = os.path.join(FIELDS, "mask")
    mstem = {os.path.splitext(f)[0]: f for f in os.listdir(mdir)}
    out = []
    for f in sorted(os.listdir(os.path.join(FIELDS, "image"))):
        stem = os.path.splitext(f)[0]
        if stem not in mstem:
            continue
        a = np.array(Image.open(os.path.join(FIELDS, "image", f)))
        im = (a >> 8).astype(np.uint8) if a.dtype == np.uint16 else \
            np.array(Image.open(os.path.join(FIELDS, "image", f)).convert("L"))
        gt = np.array(Image.open(os.path.join(mdir, mstem[stem])).convert("L")) > 127
        if im.shape == gt.shape and gt.sum() >= 50:
            out.append((im, gt))
    return out


def flat(im):
    return D.flatten_background(im)


ARMS = [
    ("DETECTOR (shipped, 1 param)", [5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0],
     lambda im, k: clean(u.segment_dark_regions(flat(im), img8=im, mad_k=k))),
    ("DECOY: detector DILATED", [(5.0, 1), (5.0, 2), (5.0, 3), (5.0, 4),
                                 (3.0, 1), (3.0, 2), (3.0, 3), (3.0, 4)],
     lambda im, p: clean(ndi.binary_dilation(
         clean(u.segment_dark_regions(flat(im), img8=im, mad_k=p[0])), iterations=p[1]))),
    ("global threshold (Otsu on flat)", [0.0],
     lambda im, _: clean(filters.gaussian(flat(im), 1, preserve_range=True)
                         < filters.threshold_otsu(
                             filters.gaussian(flat(im), 1, preserve_range=True)))),
    ("percentile threshold", [0.5, 1, 2, 4, 8], lambda im, q: clean(im <= np.percentile(im, q))),
    ("Sauvola local", [15, 25, 51, 101],
     lambda im, w: clean(im < filters.threshold_sauvola(im, window_size=w))),
    ("Frangi ridge", [0.5, 1, 2, 4, 8], lambda im, q: ridge(im, range(1, 5), q, "frangi")),
    ("Sato ridge", [0.5, 1, 2, 4, 8], lambda im, q: ridge(im, range(1, 5), q, "sato")),
    ("Meijering ridge", [0.5, 1, 2, 4, 8], lambda im, q: ridge(im, range(1, 5), q, "meijering")),
]


def loo_pick(by, n, col):
    return [by[max(by, key=lambda p: np.mean([by[p][j][col] for j in range(n) if j != i]))][i]
            for i in range(n)]


def run(name, loader):
    data = loader()
    n = len(data)
    print(f"\n{'=' * 78}\n{name}: {n} images\n{'=' * 78}", flush=True)
    rows = {}
    for nm, grid, fn in ARMS:
        by = {}
        for p in grid:
            vals = []
            for im, gt in data:
                try:
                    m = fn(im, p)
                except Exception:
                    m = np.zeros_like(gt)
                v = [pixel_f1(m, gt)]
                for t in TAUS:
                    v.append(skel_f1(m, gt, t)[0])
                vals.append(tuple(v))
            by[p] = vals
        # each metric selects its own parameter, LOO -- a metric must not inherit
        # another metric's tuning
        r = {}
        for col, key in enumerate(["pixel_f1"] + [f"skel_f1_tau{t}" for t in TAUS]):
            r[key] = float(np.mean([x[col] for x in loo_pick(by, n, col)]))
        rows[nm] = r
        print(f"  {nm:34s} pixelF1 {r['pixel_f1']:.4f}   "
              + "   ".join(f"skelF1@{t} {r[f'skel_f1_tau{t}']:.4f}" for t in TAUS), flush=True)

    for key, lbl in [("pixel_f1", "PIXEL F1 (what the paper ranked by)")] + \
                    [(f"skel_f1_tau{t}", f"SKELETON F1 at tau={t} (width-blind)") for t in TAUS]:
        order = sorted(rows.items(), key=lambda kv: -kv[1][key])
        print(f"\n  --- {lbl} ---")
        for i, (nm, r) in enumerate(order, 1):
            tag = ""
            if nm.startswith("DECOY"):
                tag = "   <-- buys nothing; if it ranks high the metric is gameable"
            if nm.startswith("DETECTOR"):
                tag = "   <-- the method"
            print(f"   {i}. {nm:34s} {r[key]:.4f}{tag}")
    return rows


RES = {"crops": run("RELEASED CROPS (the set the paper's table used)", load_crops),
       "whole_fields": run("WHOLE FIELDS", load_fields)}
p = os.path.join(REPO, "docs/figures/skelf1_ranking.json")
json.dump({"taus": list(TAUS), "sets": RES,
           "selection": "every arm and every metric picks its own parameter "
                        "leave-one-image-out",
           "why": "pixel F1 against a broad-brush label can be lifted by dilation alone, "
                  "so the decoy arm is carried through every ranking as a check on the "
                  "metric rather than on the method"}, open(p, "w"), indent=1)
print("\nwrote", p)
