"""Every public set re-scored as a PIXEL BUDGET, not only as P/R/F1/IoU.

WHY. Precision, recall, F1 and IoU all discard the true negatives. On an image that is
1.80% crack, that throws away 98% of the evidence, and it makes two very different
detectors look alike: one that marks 0.3% of the frame and one that marks 5% can land on
the same IoU. For a tool whose job is "how much of this specimen is cracked", the quantity
a user reads off the screen IS a pixel percentage, so the scores should be reported in the
same units as the answer.

So each set gets, as a percentage of all pixels:
    labelled      what the human called crack
    marked        what the detector called crack
    tp / fp / fn / tn
and the measures that USE the true negatives:
    accuracy, specificity, balanced accuracy, Matthews correlation

Balanced accuracy and MCC are the two worth reading. Plain accuracy is nearly useless here
and is printed anyway, because seeing 98% accuracy next to an IoU of 0.21 is the clearest
possible demonstration of why it must not be quoted.

    <sem-crack-detector>/.venv/bin/python -I analysis/research/improve/pixel_accounting.py
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


class U:
    pass


u = U()
DO.install(u)
KS = [5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0]


def emit(img8, k):
    raw = u.segment_dark_regions(D.flatten_background(img8), img8=img8, mad_k=k)
    lab = skm.label(D.clean_mask(raw, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel())
    kk = np.where(sz >= 40)[0]
    return np.isin(lab, kk[kk > 0])


def budget(p, g):
    """The whole confusion matrix, in percent of image, plus the measures that use TN."""
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    n = p.size
    tp = int((p & g).sum()); fp = int((p & ~g).sum())
    fn = int((~p & g).sum()); tn = int((~p & ~g).sum())
    pr = tp / max(tp + fp, 1)
    rc = tp / max(tp + fn, 1)
    sp = tn / max(tn + fp, 1)
    den = float(np.sqrt(float(tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))) or 1.0
    return {
        "labelled_pct": 100 * (tp + fn) / n,
        "marked_pct": 100 * (tp + fp) / n,
        "tp_pct": 100 * tp / n, "fp_pct": 100 * fp / n,
        "fn_pct": 100 * fn / n, "tn_pct": 100 * tn / n,
        "precision": pr, "recall": rc, "specificity": sp,
        "f1": 2 * pr * rc / max(pr + rc, 1e-12),
        "iou": tp / max(tp + fp + fn, 1),
        "accuracy": (tp + tn) / n,
        "balanced_accuracy": (rc + sp) / 2,
        "mcc": (tp * tn - fp * fn) / den,
    }


def mean_of(rows, k):
    return float(np.mean([r[k] for r in rows]))


def score_set(name, pairs):
    if not pairs:
        return None
    per_k = {k: [] for k in KS}
    me, oracle = [], []
    for img, gt in pairs:
        for k in KS:
            per_k[k].append(budget(emit(img, k), gt))
        me.append(budget(np.ones_like(gt, bool), gt))
        oracle.append(budget(gt, gt))
    N = len(pairs)
    loo = []
    for i in range(N):
        best = max(KS, key=lambda k: np.mean([per_k[k][j]["f1"] for j in range(N) if j != i]))
        loo.append(per_k[best][i])
    keys = list(loo[0])
    assert abs(mean_of(oracle, "f1") - 1.0) < 1e-9, "oracle is not 1.0"
    out = {"n": N,
           "detector": {k: mean_of(loo, k) for k in keys},
           "mark_everything": {k: mean_of(me, k) for k in keys},
           "per_k": {str(k): {m: mean_of(per_k[k], m) for m in keys} for k in KS}}
    r = out["detector"]
    print(f"\n{name}  n={N}")
    print(f"   labelled {r['labelled_pct']:6.3f}%   marked {r['marked_pct']:6.3f}%   "
          f"ratio {r['marked_pct']/max(r['labelled_pct'],1e-9):5.2f}x")
    print(f"   tp {r['tp_pct']:6.3f}%   fp {r['fp_pct']:6.3f}%   fn {r['fn_pct']:6.3f}%   "
          f"tn {r['tn_pct']:7.3f}%")
    print(f"   accuracy {100*r['accuracy']:6.2f}%   specificity {100*r['specificity']:6.2f}%   "
          f"balanced acc {100*r['balanced_accuracy']:5.2f}%   MCC {r['mcc']:.4f}")
    print(f"   (P {r['precision']:.4f}  R {r['recall']:.4f}  F1 {r['f1']:.4f}  "
          f"IoU {r['iou']:.4f})")
    return out


def load_sem(root, cls, sub_img, sub_mask, tif16=False):
    idir, mdir = os.path.join(root, cls, sub_img), os.path.join(root, cls, sub_mask)
    if not os.path.isdir(idir):
        return []
    mstem = {os.path.splitext(f)[0]: f for f in os.listdir(mdir)}
    out = []
    for f in sorted(os.listdir(idir)):
        stem = os.path.splitext(f)[0]
        if stem not in mstem:
            continue
        a = np.array(Image.open(os.path.join(idir, f)))
        img = (a >> 8).astype(np.uint8) if a.dtype == np.uint16 else \
            np.array(Image.open(os.path.join(idir, f)).convert("L"))
        gt = np.array(Image.open(os.path.join(mdir, mstem[stem])).convert("L")) > 127
        if img.shape == gt.shape and gt.sum() >= 50:
            out.append((img, gt))
    return out


RES = {}
tr = os.path.join(SCR, "pub_ebc_download/train_subset")
te = os.path.join(SCR, "pub_ebc_download/extracted/testsem")
RES["Inconel 718, whole fields"] = score_set(
    "Inconel 718, whole fields", load_sem(tr, "Inconel718_crack", "image", "mask"))
RES["Inconel 718, released crops"] = score_set(
    "Inconel 718, released crops",
    load_sem(te, "Inconel718_crack", "image_cropped", "mask_cropped"))
RES["EBC coating, whole fields"] = score_set(
    "EBC coating, whole fields", load_sem(tr, "EBC_crack", "image", "mask"))

out = os.path.join(REPO, "docs/figures/pixel_accounting.json")
json.dump({"what": "the full confusion matrix as a percentage of image pixels, plus the "
                   "measures that use true negatives, for every SEM set",
           "why": "P/R/F1/IoU all discard the true negatives; on a 1.80%-crack image that "
                  "is 98% of the evidence, and a tool whose answer is a pixel percentage "
                  "should be scored in the same units",
           "metric": "mean per image, 0 px tolerance, mad_k leave-one-image-out",
           "sets": RES}, open(out, "w"), indent=1)
print("\nwrote", out)
