"""Does ridge-growing carry information, or is it a dilation wearing a filter's name?

Growing the darkness proposal through the Sato ridge response reached F1 0.6169 / recall
0.9128 on the released crops, against 0.4958 / 0.4567 shipped. That is a large enough jump
to be suspicious: every previous time a post-processing step in this project produced a
jump like it, the step turned out to be inflating mask width, and the metric was rewarding
the inflation rather than the localisation.

So this run refuses to believe the arm without decoys. Three controls, each keeping
something and destroying something:

  FLIPPED RIDGE  the ridge response mirrored left-right. Identical response statistics,
                 identical area, registration destroyed. If growing through it scores the
                 same, the gain is not about where the ridges are.
  OTHER IMAGE    the ridge response of a different crop. Real ridge texture, wrong field.
  DILATED        the seed dilated step by step; the step closest in area to the ridge-grown
                 result is reported. Carries no information whatsoever beyond the seed.

An arm that cannot beat its own decoys has measured nothing. And because a rule validated
on crops has silently deleted real crack on whole frames twice in this project, every arm
is scored on the 31 whole fields as well, and marked% is printed beside F1 so the pixel
budget is visible rather than inferred.
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
MADK, RQ = 5.0, 2.0          # held fixed across every arm so only the mask-source differs


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
    return {"f1": 2 * pr * rc / max(pr + rc, 1e-12), "precision": pr, "recall": rc,
            "marked_pct": 100.0 * p.sum() / p.size, "labelled_pct": 100.0 * g.sum() / g.size}


def ridge_response(im):
    return filters.sato(im.astype(float), sigmas=range(1, 5), black_ridges=True)


def seed_of(im):
    return clean(u.segment_dark_regions(D.flatten_background(im), img8=im, mad_k=MADK))


def grow(seed, allow):
    return clean(ndi.binary_propagation(seed, mask=seed | allow))


def dilate_to(seed, target):
    """Walk the dilation ladder and return the step closest in area to `target`."""
    best, cur = seed, seed
    for _ in range(60):
        nxt = ndi.binary_dilation(cur)
        if nxt.sum() == cur.sum():
            break
        cur = nxt
        if abs(cur.sum() - target) < abs(best.sum() - target):
            best = cur
        if cur.sum() > target:
            break
    return clean(best)


def load_crops():
    idir, mdir = os.path.join(CROPS, "image_cropped"), os.path.join(CROPS, "mask_cropped")
    out = []
    for f in sorted(os.listdir(idir)):
        im = np.array(Image.open(os.path.join(idir, f)).convert("L"))
        gt = np.array(Image.open(os.path.join(mdir, f)).convert("L")) > 127
        if im.shape == gt.shape and gt.sum() >= 50:
            out.append((f, im, gt))
    return out


def load_fields():
    """The whole fields are 16-bit TIFFs whose masks are named separately. Reading them
    with convert("L") returns a mean of 254.8 and a recall of 0.0012; the authors' own
    PNGs are reproduced exactly by >>8, so that is what this uses."""
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
            out.append((stem, im, gt))
    return out


def run(name, loader):
    data = loader()
    print(f"\n=== {name}: {len(data)} images "
          f"({data[0][1].shape[1]}x{data[0][1].shape[0]} first) ===", flush=True)
    acc = {}
    for i, (f, im, gt) in enumerate(data):
        R = ridge_response(im)
        cut = np.percentile(R, 100 - RQ)
        ridge = clean(R >= cut)
        flipped = clean(R[:, ::-1] >= cut)
        # the ridge response of the NEXT image, resized by cropping/padding to fit
        o = data[(i + 1) % len(data)][1]
        Ro = ridge_response(o)
        oth = np.zeros_like(R)
        h = min(R.shape[0], Ro.shape[0]); w = min(R.shape[1], Ro.shape[1])
        oth[:h, :w] = Ro[:h, :w]
        other = clean(oth >= np.percentile(Ro, 100 - RQ))

        s = seed_of(im)
        real = grow(s, ridge)
        arms = {
            "A shipped darkness only": s,
            "B grown through REAL ridge": real,
            "C grown through FLIPPED ridge": grow(s, flipped),
            "D grown through ANOTHER FIELD ridge": grow(s, other),
            "E seed DILATED to B area": dilate_to(s, int(real.sum())),
            "F ridge alone (no seed)": ridge,
        }
        for k, m in arms.items():
            acc.setdefault(k, []).append(stats(m, gt))
    print(f"  {'arm':38s} {'F1':>7s} {'prec':>7s} {'recall':>7s} {'marked%':>8s}")
    lab = np.mean([x["labelled_pct"] for x in acc["A shipped darkness only"]])
    out = {}
    for k in arms:
        v = {m: float(np.mean([x[m] for x in acc[k]])) for m in
             ("f1", "precision", "recall", "marked_pct")}
        out[k] = v
        print(f"  {k:38s} {v['f1']:7.4f} {v['precision']:7.4f} {v['recall']:7.4f} "
              f"{v['marked_pct']:8.3f}")
    print(f"  {'(labelled)':38s} {'':7s} {'':7s} {'':7s} {lab:8.3f}")
    b = out["B grown through REAL ridge"]["f1"]
    print(f"\n  real ridge minus FLIPPED ridge : {b - out['C grown through FLIPPED ridge']['f1']:+.4f}")
    print(f"  real ridge minus OTHER image   : {b - out['D grown through ANOTHER FIELD ridge']['f1']:+.4f}")
    print(f"  real ridge minus EQUAL-AREA DIL: {b - out['E seed DILATED to B area']['f1']:+.4f}")
    out["_labelled_pct"] = float(lab)
    out["_n"] = len(data)
    return out


RES = {"crops": run("released crops (what the ranking used)", load_crops),
       "whole_fields": run("WHOLE FIELDS", load_fields)}
p = os.path.join(REPO, "docs/figures/ridge_grow_controls.json")
json.dump({"fixed": {"mad_k": MADK, "ridge_percentile": RQ}, "sets": RES,
           "question": "does growing the darkness proposal through the ridge response carry "
                       "information, or is the gain width inflation that any equal-area "
                       "dilation would reproduce"}, open(p, "w"), indent=1)
print("\nwrote", p)
