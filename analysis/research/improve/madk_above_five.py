"""Is mad_k = 5.0 the optimum, or the edge of the grid?

The paper's strongest claim is that its one free constant, fitted years ago on SEM steel in
another laboratory, lands on this dataset's optimum without refitting -- "the best of the
seven values tested, and the curve falls away monotonically below it". Two independent
readers of the draft noticed the same thing: the seven values are 1.0, 1.5, 2.0, 2.5, 3.0,
4.0 and 5.0. The sweep STOPS at the shipped value. F1 is still climbing when the grid runs
out, so "the optimum" may simply be the largest number anyone tried.

This runs the sweep upward: 5 through 40. It settles two separate questions at once. If F1
turns over just above 5.0 the paper's claim survives and gets a proper two-sided curve. If it
keeps climbing, the claim is an artefact of the grid AND there is a free improvement sitting
inside the single parameter the method already has -- no new channel, no new constant.

Scored as a pixel budget with precision/recall/F1/IoU beside it, on the whole fields and on
the released crops, because the area fraction is what a reader of the tool gets and a higher
mad_k marks less.
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
from skimage import measure as skm
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None

SCR = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
FIELDS = os.path.join(SCR, "pub_ebc_download/train_subset/Inconel718_crack")
CROPS = os.path.join(SCR, "pub_ebc_download/extracted/testsem/Inconel718_crack")
GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 16.0, 20.0, 30.0, 40.0]


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
            "precision": pr, "recall": rc,
            "f1": 2 * pr * rc / max(pr + rc, 1e-12),
            "iou": tp / max(tp + fp + fn, 1)}


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
    print(f"\n{'=' * 92}\n{name}: {n} images\n{'=' * 92}", flush=True)
    per = {}
    for k in GRID:
        rows = []
        for im, gt in data:
            m = clean(u.segment_dark_regions(D.flatten_background(im), img8=im, mad_k=k))
            rows.append(budget(m, gt))
        per[k] = rows
        a = {x: float(np.mean([r[x] for r in rows])) for x in rows[0]}
        flag = "  <-- SHIPPED" if k == 5.0 else ""
        print(f"  mad_k {k:5.1f}   marked {a['marked_pct']:7.3f}%  ratio {a['area_ratio']:6.2f}  "
              f"P {a['precision']:.4f}  R {a['recall']:.4f}  F1 {a['f1']:.4f}  "
              f"IoU {a['iou']:.4f}{flag}", flush=True)

    mean_f1 = {k: float(np.mean([r["f1"] for r in per[k]])) for k in GRID}
    best_k = max(GRID, key=lambda k: mean_f1[k])
    # honest selection: leave one image out, over the FULL grid
    loo = float(np.mean([per[max(GRID, key=lambda k: np.mean(
        [per[k][j]["f1"] for j in range(n) if j != i]))][i]["f1"] for i in range(n)]))
    loo5 = float(np.mean([r["f1"] for r in per[5.0]]))
    print(f"\n  best in-sample mad_k      : {best_k}  (F1 {mean_f1[best_k]:.4f})")
    print(f"  shipped mad_k 5.0         : F1 {loo5:.4f}")
    print(f"  LOO over the FULL grid    : F1 {loo:.4f}   ({loo - loo5:+.4f} vs shipped)")
    if best_k > 5.0:
        print(f"  => 5.0 was the EDGE OF THE GRID, not the optimum. The curve keeps "
              f"climbing to {best_k}.")
    else:
        print(f"  => 5.0 survives: the curve does turn over above it.")
    return {"mean_f1": mean_f1, "best_in_sample": best_k,
            "loo_full_grid_f1": loo, "shipped_f1": loo5,
            "per_k": {str(k): {x: float(np.mean([r[x] for r in per[k]]))
                               for x in per[k][0]} for k in GRID},
            # per-IMAGE values, so the gap between two rungs can be tested paired
            # rather than asserted from two means
            "per_image": {str(k): {x: [float(r[x]) for r in per[k]]
                                   for x in ("f1", "marked_pct", "labelled_pct",
                                             "precision", "recall", "iou")}
                          for k in GRID}}


RES = {"whole_fields": run("WHOLE FIELDS (the paper's primary set)", load_fields),
       "crops": run("RELEASED CROPS", load_crops)}
p = os.path.join(REPO, "docs/figures/madk_above_five.json")
json.dump({"grid": GRID, "sets": RES,
           "why": "the published sweep stopped at the shipped value 5.0 with F1 still "
                  "rising, so the claimed optimum may have been the edge of the grid"},
          open(p, "w"), indent=1)
print("\nwrote", p)
