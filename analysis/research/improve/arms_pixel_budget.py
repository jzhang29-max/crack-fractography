"""Every arm scored as a pixel budget first, and as precision/recall/F1/IoU alongside.

The baseline tables in this project have ranked arms by F1. F1 discards the true negatives,
which on a 1.8% crack field is 98% of the evidence, and it says nothing about the quantity
this tool actually reports to a reader: the crack area fraction, a pixel percentage. Two
detectors can share an F1 while one marks 0.3% of a frame and the other 5%.

So this scores all eight arms in both currencies at once. The pixel budget -- labelled%,
marked%, and the marked area split into the part that is right and the part that is wrong,
all as a percentage of the whole image -- is the primary table. Precision, recall, F1 and
IoU are reported beside it, because they answer a different and still useful question: of
what was marked, how much was crack, and of the crack, how much was found.

Each arm's parameter is chosen leave-one-image-out TWICE, because the choice depends on what
you are optimising and pretending otherwise hides a real decision:

  by F1               -- what the benchmark rewards
  by area-fraction    -- what a reader of this tool needs: the marked percentage closest to
                         the labelled percentage

An arm can reach area-fraction parity by marking the right AMOUNT in the wrong PLACES, so
the ratio is never reported without the true-positive and false-positive percentages beside
it. That pairing is the whole point of the budget view.
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
    """The full confusion matrix as a percentage of the image, plus the ratio metrics."""
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    n = p.size
    tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    f1 = 2 * pr * rc / max(pr + rc, 1e-12)
    iou = tp / max(tp + fp + fn, 1)
    lab_pct = 100.0 * g.sum() / n
    mark_pct = 100.0 * p.sum() / n
    return {"labelled_pct": lab_pct, "marked_pct": mark_pct,
            "tp_pct": 100.0 * tp / n, "fp_pct": 100.0 * fp / n, "fn_pct": 100.0 * fn / n,
            "area_ratio": mark_pct / lab_pct if lab_pct else float("nan"),
            "area_err_pp": abs(mark_pct - lab_pct),
            "precision": pr, "recall": rc, "f1": f1, "iou": iou}


def mean_width(m):
    m = np.asarray(m, bool)
    L = int(morph.skeletonize(m).sum())
    return (m.sum() / L) if L else float("nan")


def ridge(im, sig, q, kind):
    f = {"frangi": filters.frangi, "sato": filters.sato, "meijering": filters.meijering}[kind]
    r = f(im.astype(float), sigmas=sig, black_ridges=True)
    return clean(r >= np.percentile(r, 100 - q))


def flat(im):
    return D.flatten_background(im)


def dark(im, k):
    return clean(u.segment_dark_regions(flat(im), img8=im, mad_k=k))


ARMS = [
    # THE FULL GRID. An earlier version of this table capped mad_k at 5.0 while giving
    # every classical arm its whole range -- the same truncation that made the paper's
    # headline look true. A comparison that grids the competitors further than the method
    # measures the grid, not the method.
    ("DETECTOR (shipped)",
     [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0],
     lambda im, k: dark(im, k)),
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
    # the one combination that is not a decoy: two evidence channels, unioned. It spends a
    # second free parameter, which the table has to show.
    ("UNION darkness OR Sato", [(6.0, 0.5), (6.0, 1), (6.0, 2), (6.0, 4),
                                (5.0, 0.5), (5.0, 1), (5.0, 2), (5.0, 4),
                                (3.0, 1), (3.0, 2)],
     lambda im, p: dark(im, p[0]) | ridge(im, range(1, 5), p[1], "sato")),
]


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
    n = len(data)
    print(f"\n{'=' * 104}\n{name}: {n} images\n{'=' * 104}", flush=True)
    out = {}
    for nm, grid, fn in ARMS:
        by, wid = {}, {}
        for p in grid:
            rows, ws = [], []
            for im, gt in data:
                try:
                    m = fn(im, p)
                except Exception:
                    m = np.zeros_like(gt)
                rows.append(budget(m, gt))
                ws.append(mean_width(m))
            by[p], wid[p] = rows, ws

        def loo(key, lower_is_better=False):
            sign = 1 if lower_is_better else -1
            picks = []
            for i in range(n):
                best = min(grid, key=lambda p: sign * np.mean(
                    [by[p][j][key] for j in range(n) if j != i]))
                picks.append((best, i))
            return picks

        res = {"free_params": 2 if isinstance(grid[0], tuple) else 1}
        for sel_key, sel_name, lower in (("f1", "sel_by_f1", False),
                                         ("area_err_pp", "sel_by_area", True)):
            picks = loo(sel_key, lower)
            agg = {k: float(np.mean([by[p][i][k] for p, i in picks]))
                   for k in by[grid[0]][0]}
            w = [wid[p][i] for p, i in picks]
            gw = [mean_width(g) for _, g in data]
            ok = [j for j in range(n) if not (np.isnan(w[j]) or np.isnan(gw[j]))]
            agg["width_ratio"] = float(np.mean([w[j] for j in ok])
                                       / np.mean([gw[j] for j in ok])) if ok else float("nan")
            res[sel_name] = agg
        out[nm] = res

    lab = out["DETECTOR (shipped)"]["sel_by_f1"]["labelled_pct"]
    print(f"\nPIXEL BUDGET, as a percentage of the image. Labelled crack = {lab:.3f}%")
    print(f"  parameter chosen leave-one-image-out BY AREA-FRACTION ERROR "
          f"(what a reader of this tool needs)\n")
    print(f"  {'arm':32s} {'pp':>3s} {'marked%':>8s} {'right%':>8s} {'wrong%':>8s} "
          f"{'ratio':>6s} {'width':>6s} {'prec':>6s} {'recall':>6s} {'F1':>6s} {'IoU':>6s}")
    for nm, r in sorted(out.items(), key=lambda kv: kv[1]["sel_by_area"]["area_err_pp"]):
        a = r["sel_by_area"]
        print(f"  {nm:32s} {r['free_params']:3d} {a['marked_pct']:8.3f} {a['tp_pct']:8.3f} "
              f"{a['fp_pct']:8.3f} {a['area_ratio']:6.2f} {a['width_ratio']:6.2f} "
              f"{a['precision']:6.3f} {a['recall']:6.3f} {a['f1']:6.3f} {a['iou']:6.3f}")

    print(f"\n  the same arms with the parameter chosen BY F1 (what the benchmark rewards)\n")
    print(f"  {'arm':32s} {'pp':>3s} {'marked%':>8s} {'right%':>8s} {'wrong%':>8s} "
          f"{'ratio':>6s} {'width':>6s} {'prec':>6s} {'recall':>6s} {'F1':>6s} {'IoU':>6s}")
    for nm, r in sorted(out.items(), key=lambda kv: -kv[1]["sel_by_f1"]["f1"]):
        a = r["sel_by_f1"]
        print(f"  {nm:32s} {r['free_params']:3d} {a['marked_pct']:8.3f} {a['tp_pct']:8.3f} "
              f"{a['fp_pct']:8.3f} {a['area_ratio']:6.2f} {a['width_ratio']:6.2f} "
              f"{a['precision']:6.3f} {a['recall']:6.3f} {a['f1']:6.3f} {a['iou']:6.3f}")
    return out


RES = {"whole_fields": run("WHOLE FIELDS (the paper's primary set)", load_fields),
       "crops": run("RELEASED CROPS", load_crops)}
p = os.path.join(REPO, "docs/figures/arms_pixel_budget.json")
json.dump({"sets": RES,
           "primary_measure": "pixel percentage: labelled%, marked%, and the marked area "
                              "split into right and wrong, all as a percentage of the image",
           "also_reported": "precision, recall, F1, IoU -- a different and still useful "
                            "question, not a replacement",
           "selection": "each arm picks its own parameter leave-one-image-out, once by F1 "
                        "and once by area-fraction error, because the choice depends on what "
                        "is being optimised",
           "caution": "area-fraction parity can be reached by marking the right AMOUNT in "
                      "the wrong PLACES, so ratio is never read without right% and wrong%"},
          open(p, "w"), indent=1)
print("\nwrote", p)
