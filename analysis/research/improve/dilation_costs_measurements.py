"""What ranking first costs the numbers the lab actually reports.

Dilating the shipped mask lifts pixel F1 from 0.4958 to 0.6307 on the released crops and
takes the detector from third place to first, past Sauvola's 0.5145. It also lifts the
width-blind skeleton F1. Nothing in that step detects anything: it is a morphological
dilation of the detector's own output.

The question this asks is not whether the gain is real -- it is real, under the same
leave-one-image-out protocol every baseline gets -- but what it does to the two quantities
the lab puts in papers: the crack area fraction and the crack width. A detector is not
scored on F1 in the lab; it is read for how much of the field cracked and how wide the
cracks are. If the step that wins the benchmark makes both of those worse, then the
benchmark and the measurement point in opposite directions, and the ranking is not a
reason to ship it.

Each arm is given its best single setting in-sample, which is the most generous choice
available and favours the arm being tested.
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
from skimage import measure as skm, morphology as morph
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


def f1(p, g):
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return 2 * pr * rc / max(pr + rc, 1e-12)


def mean_width(m):
    """Area divided by centreline length -- the width a reader would quote."""
    m = np.asarray(m, bool)
    L = int(morph.skeletonize(m).sum())
    return (m.sum() / L) if L else float("nan")


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


def seed(im, k):
    return clean(u.segment_dark_regions(D.flatten_background(im), img8=im, mad_k=k))


ARMS = {
    "shipped detector": ([(k,) for k in (5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0)],
                         lambda im, p: seed(im, p[0])),
    "detector DILATED (ranks 1st)": ([(k, r) for k in (5.0, 3.0) for r in (1, 2, 3, 4)],
                                     lambda im, p: clean(ndi.binary_dilation(
                                         seed(im, p[0]), iterations=p[1]))),
}


def run(name, loader):
    data = loader()
    print(f"\n=== {name}: {len(data)} images ===", flush=True)
    out = {}
    for nm, (grid, fn) in ARMS.items():
        cache = {p: [fn(im, p) for im, _ in data] for p in grid}
        best = max(grid, key=lambda p: np.mean([f1(m, g) for m, (_, g) in
                                                zip(cache[p], data)]))
        masks = cache[best]
        af_p = np.array([100.0 * m.sum() / m.size for m in masks])
        af_g = np.array([100.0 * g.sum() / g.size for _, g in data])
        w_p = np.array([mean_width(m) for m in masks])
        w_g = np.array([mean_width(g) for _, g in data])
        ok = ~(np.isnan(w_p) | np.isnan(w_g))
        v = {"setting": str(best),
             "pixel_f1": float(np.mean([f1(m, g) for m, (_, g) in zip(masks, data)])),
             "area_fraction_pred_pct": float(af_p.mean()),
             "area_fraction_label_pct": float(af_g.mean()),
             "area_fraction_ratio": float(af_p.mean() / af_g.mean()),
             "mean_width_pred_px": float(w_p[ok].mean()),
             "mean_width_label_px": float(w_g[ok].mean()),
             "width_ratio": float(w_p[ok].mean() / w_g[ok].mean())}
        out[nm] = v
        print(f"  {nm:30s} F1 {v['pixel_f1']:.4f} at {v['setting']}")
        print(f"    area fraction  {v['area_fraction_pred_pct']:6.3f}% vs labelled "
              f"{v['area_fraction_label_pct']:6.3f}%   ratio {v['area_fraction_ratio']:.2f}x")
        print(f"    mean width    {v['mean_width_pred_px']:7.2f} px vs labelled "
              f"{v['mean_width_label_px']:6.2f} px   ratio {v['width_ratio']:.2f}x", flush=True)
    a, b = out["shipped detector"], out["detector DILATED (ranks 1st)"]
    print(f"\n  F1 bought            : {b['pixel_f1'] - a['pixel_f1']:+.4f}")
    print(f"  area-fraction error  : {a['area_fraction_ratio']:.2f}x -> "
          f"{b['area_fraction_ratio']:.2f}x")
    print(f"  width error          : {a['width_ratio']:.2f}x -> {b['width_ratio']:.2f}x")
    return out


RES = {"crops": run("released crops", load_crops),
       "whole_fields": run("WHOLE FIELDS", load_fields)}
p = os.path.join(REPO, "docs/figures/dilation_costs_measurements.json")
json.dump({"sets": RES, "note": "each arm given its best single setting IN SAMPLE, which "
                                "favours it; area fraction and mean width are the two "
                                "quantities the lab reports"}, open(p, "w"), indent=1)
print("\nwrote", p)
