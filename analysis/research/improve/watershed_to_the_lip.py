"""Grow the dark seed out to the crack lip, stopping at the edge rather than at a threshold.

Three channels have now failed the same way. A ridge filter, a texture filter and a plain
dilation all raise recall by letting the mask get bigger, all drive the reported area
fraction to two or three times the labelled value, and none beats a control fed the WRONG
IMAGE by more than 0.025 F1. The common fault is that every one of them stops on a threshold
of some filter response, and a threshold has no reason to coincide with the edge of a crack.

The panels show what the right stopping rule is. These cracks are wide open and their
boundary against the matrix is crisp: a strong intensity gradient runs along the lip. So this
arm marks the crack by watershed, seeded by the dark core the detector already finds and by
matrix well away from it, with the gradient magnitude as the barrier. The region grows until
it meets the lip and then stops, because that is where the barrier is -- not because a
percentile ran out. If the area fraction is going to be right, it will be right here.

Same decoys as before, and they matter more each time:
  WRONG-IMAGE gradient  the barrier taken from a different field. If the result barely moves,
                        the arm is not reading this image, which is how the ridge filter died.
  equal-area DILATION   no information at all. It has beaten every arm so far.
Reported as a pixel budget, with precision/recall/F1/IoU beside it.
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
from skimage import measure as skm, filters, morphology as morph, segmentation as seg
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None

SCR = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
FIELDS = os.path.join(SCR, "pub_ebc_download/train_subset/Inconel718_crack")
CROPS = os.path.join(SCR, "pub_ebc_download/extracted/testsem/Inconel718_crack")
MADK = 5.0


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


def budget(p, g):
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    n = p.size
    tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    lab_pct, mark_pct = 100.0 * g.sum() / n, 100.0 * p.sum() / n
    return {"labelled_pct": lab_pct, "marked_pct": mark_pct,
            "tp_pct": 100.0 * tp / n, "fp_pct": 100.0 * fp / n,
            "area_ratio": mark_pct / lab_pct if lab_pct else float("nan"),
            "area_err_pp": abs(mark_pct - lab_pct),
            "precision": pr, "recall": rc,
            "f1": 2 * pr * rc / max(pr + rc, 1e-12),
            "iou": tp / max(tp + fp + fn, 1)}


def mean_width(m):
    m = np.asarray(m, bool)
    L = int(morph.skeletonize(m).sum())
    return (m.sum() / L) if L else float("nan")


def grad(im):
    return filters.sobel(filters.gaussian(im.astype(float), 1.2, preserve_range=True))


def water(seed, g, standoff):
    """Watershed from the dark core outward, the gradient ridge along the lip as barrier."""
    if not seed.any():
        return np.zeros(seed.shape, bool)
    far = ~ndi.binary_dilation(seed, iterations=standoff)
    mk = np.zeros(seed.shape, np.int32)
    mk[far] = 1          # matrix
    mk[seed] = 2         # crack
    if not (mk == 1).any():
        return clean(seed)
    return clean(seg.watershed(g, markers=mk) == 2)


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


def load_crops():
    idir, mdir = os.path.join(CROPS, "image_cropped"), os.path.join(CROPS, "mask_cropped")
    out = []
    for f in sorted(os.listdir(idir)):
        im = np.array(Image.open(os.path.join(idir, f)).convert("L"))
        gt = np.array(Image.open(os.path.join(mdir, f)).convert("L")) > 127
        if im.shape == gt.shape and gt.sum() >= 50:
            out.append((im, gt))
    return out


def run(name, loader):
    data = loader()
    n = len(data)
    print(f"\n{'=' * 100}\n{name}: {n} images\n{'=' * 100}", flush=True)
    seeds = [clean(u.segment_dark_regions(D.flatten_background(im), img8=im, mad_k=MADK))
             for im, _ in data]
    grads = [grad(im) for im, _ in data]
    SO = (10, 20, 40, 80)
    DIL = (1, 2, 3, 4)

    ARMS = {
        "shipped detector": ([None], lambda i, p: seeds[i], 1),
        "WATERSHED to the lip": (SO, lambda i, p: water(seeds[i], grads[i], p), 2),
        "decoy: WRONG-IMAGE gradient": (SO, lambda i, p: water(
            seeds[i], grads[(i + 1) % n][:grads[i].shape[0], :grads[i].shape[1]]
            if grads[(i + 1) % n].shape >= grads[i].shape else grads[i], p), 2),
        "decoy: equal-area DILATION": (DIL, lambda i, p: clean(
            ndi.binary_dilation(seeds[i], iterations=p)), 2),
    }
    out = {}
    for nm, (grid, fn, npar) in ARMS.items():
        by, wid = {}, {}
        for p in grid:
            rows, ws = [], []
            for i in range(n):
                try:
                    m = fn(i, p)
                except Exception:
                    m = seeds[i]
                rows.append(budget(m, data[i][1]))
                ws.append(mean_width(m))
            by[p], wid[p] = rows, ws
        if len(grid) == 1:
            pk_f = pk_a = [(grid[0], i) for i in range(n)]
        else:
            pk_f = [(max(grid, key=lambda p: np.mean(
                [by[p][j]["f1"] for j in range(n) if j != i])), i) for i in range(n)]
            pk_a = [(min(grid, key=lambda p: np.mean(
                [by[p][j]["area_err_pp"] for j in range(n) if j != i])), i)
                for i in range(n)]
        gw = [mean_width(g) for _, g in data]

        def agg(pk):
            a = {k: float(np.mean([by[p][i][k] for p, i in pk])) for k in by[grid[0]][0]}
            w = [wid[p][i] for p, i in pk]
            ok = [j for j in range(n) if not (np.isnan(w[j]) or np.isnan(gw[j]))]
            a["width_ratio"] = float(np.mean([w[j] for j in ok])
                                     / np.mean([gw[j] for j in ok])) if ok else float("nan")
            return a
        out[nm] = {"free_params": npar, "sel_by_f1": agg(pk_f), "sel_by_area": agg(pk_a)}

    lab = out["shipped detector"]["sel_by_f1"]["labelled_pct"]
    for sel, title in (("sel_by_f1", "by F1"), ("sel_by_area", "by area-fraction error")):
        print(f"\n  PIXEL BUDGET, % of image. Labelled {lab:.3f}%. Parameter chosen {title}.\n")
        print(f"  {'arm':30s} {'pp':>3s} {'marked%':>8s} {'right%':>8s} {'wrong%':>8s} "
              f"{'ratio':>6s} {'width':>6s} {'prec':>6s} {'recall':>6s} {'F1':>6s} {'IoU':>6s}")
        for nm in ARMS:
            a = out[nm][sel]
            print(f"  {nm:30s} {out[nm]['free_params']:3d} {a['marked_pct']:8.3f} "
                  f"{a['tp_pct']:8.3f} {a['fp_pct']:8.3f} {a['area_ratio']:6.2f} "
                  f"{a['width_ratio']:6.2f} {a['precision']:6.3f} {a['recall']:6.3f} "
                  f"{a['f1']:6.3f} {a['iou']:6.3f}")
    w = out["WATERSHED to the lip"]
    print(f"\n  WATERSHED vs wrong-image gradient, F1: "
          f"{w['sel_by_f1']['f1'] - out['decoy: WRONG-IMAGE gradient']['sel_by_f1']['f1']:+.4f}")
    print(f"  WATERSHED vs equal-area dilation,  F1: "
          f"{w['sel_by_f1']['f1'] - out['decoy: equal-area DILATION']['sel_by_f1']['f1']:+.4f}")
    print(f"  area ratio, tuned for area: shipped "
          f"{out['shipped detector']['sel_by_area']['area_ratio']:.2f}x -> watershed "
          f"{w['sel_by_area']['area_ratio']:.2f}x")
    return out


RES = {"whole_fields": run("WHOLE FIELDS (the primary set)", load_fields),
       "crops": run("RELEASED CROPS", load_crops)}
p = os.path.join(REPO, "docs/figures/watershed_to_the_lip.json")
json.dump({"mad_k": MADK, "sets": RES,
           "idea": "stop at the crack lip, where the gradient barrier is, instead of at a "
                   "percentile of some filter response",
           "decoys": "wrong-image gradient and an equal-area dilation"},
          open(p, "w"), indent=1)
print("\nwrote", p)
