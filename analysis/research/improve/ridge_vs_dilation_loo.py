"""Matched-arity test: is the ridge-grown arm's win a dilation in disguise?

Growing the darkness proposal through the Sato ridge response scored F1 0.6169 under
leave-one-image-out selection over two parameters -- far past Sauvola's 0.5145 and the
shipped 0.4958 -- which would have made the detector rank first.

The fixed-parameter controls already showed the ridge carries almost nothing: on whole
fields, growing through ANOTHER FIELD's ridge response scored 0.4043 against the real
field's 0.4065, and an equal-area dilation of the seed beat both. But those ran at one
fixed setting, while the 0.6169 came from choosing two parameters per image. A gain that
only appears under selection has to be tested under selection.

So this gives a plain dilation of the same seed exactly the same budget: two parameters,
an eight-point grid, chosen leave-one-image-out by the same rule. An oracle or a decoy
that gets fewer parameters than the arm it is testing is not a decoy, it is a handicap.
If the dilation reaches the same score, the ridge filter is decoration and the ranking
gain is the mask getting wider.
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
from skimage import measure as skm, filters
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None

SCR = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
CROPS = os.path.join(SCR, "pub_ebc_download/extracted/testsem/Inconel718_crack")
FIELDS = os.path.join(SCR, "pub_ebc_download/train_subset/Inconel718_crack")


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


def stats(p, g):
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return (2 * pr * rc / max(pr + rc, 1e-12), pr, rc, 100.0 * p.sum() / p.size)


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


def run(name, loader):
    data = loader()
    print(f"\n=== {name}: {len(data)} images ===", flush=True)
    # cache the two expensive per-image pieces once per mad_k / once per image
    seeds, ridges = {}, []
    for i, (im, gt) in enumerate(data):
        ridges.append(filters.sato(im.astype(float), sigmas=range(1, 5), black_ridges=True))
        for k in (5.0, 3.0):
            seeds[(i, k)] = clean(
                u.segment_dark_regions(D.flatten_background(im), img8=im, mad_k=k))

    ARMS = {
        # exactly one parameter -- what the paper claims the method spends
        "SHIPPED darkness (1 param)":
            ([(k,) for k in (5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0)],
             lambda i, p: clean(u.segment_dark_regions(
                 D.flatten_background(data[i][0]), img8=data[i][0], mad_k=p[0]))),
        # two parameters: the arm that appeared to win
        "grown through RIDGE (2 params)":
            ([(k, q) for k in (5.0, 3.0) for q in (1, 2, 4, 8)],
             lambda i, p: clean(ndi.binary_propagation(
                 seeds[(i, p[0])],
                 mask=seeds[(i, p[0])] | clean(
                     ridges[i] >= np.percentile(ridges[i], 100 - p[1]))))),
        # two parameters, same grid size, no information beyond the seed
        "just DILATED (2 params)":
            ([(k, r) for k in (5.0, 3.0) for r in (1, 2, 3, 4)],
             lambda i, p: clean(ndi.binary_dilation(seeds[(i, p[0])], iterations=p[1]))),
    }

    out = {}
    for nm, (grid, fn) in ARMS.items():
        by = {p: [] for p in grid}
        for i in range(len(data)):
            for p in grid:
                by[p].append(stats(fn(i, p), data[i][1]))
        n = len(data)
        loo = [by[max(grid, key=lambda p: np.mean([by[p][j][0] for j in range(n) if j != i]))][i]
               for i in range(n)]
        v = {m: float(np.mean([x[c] for x in loo]))
             for c, m in enumerate(("f1", "precision", "recall", "marked_pct"))}
        v["grid_size"] = len(grid)
        out[nm] = v
        print(f"  {nm:34s} F1 {v['f1']:.4f}  P {v['precision']:.4f}  "
              f"R {v['recall']:.4f}  marked {v['marked_pct']:.3f}%", flush=True)
    d = out["grown through RIDGE (2 params)"]["f1"] - out["just DILATED (2 params)"]["f1"]
    print(f"\n  RIDGE minus DILATION, matched arity and grid size: {d:+.4f}")
    print(f"  labelled area: {100.0 * np.mean([g.sum() / g.size for _, g in data]):.3f}%")
    out["_ridge_minus_dilation"] = float(d)
    return out


RES = {"crops": run("released crops (the set the ranking used)", load_crops),
       "whole_fields": run("WHOLE FIELDS", load_fields)}
p = os.path.join(REPO, "docs/figures/ridge_vs_dilation_loo.json")
json.dump({"sets": RES, "baseline_to_beat_on_crops": {"Sauvola local": 0.5145},
           "question": "under identical leave-one-image-out selection and identical "
                       "parameter count, does growing through the ridge response beat a "
                       "plain dilation of the same seed"}, open(p, "w"), indent=1)
print("\nwrote", p)
