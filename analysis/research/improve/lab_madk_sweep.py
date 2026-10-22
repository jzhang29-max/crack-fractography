"""Does mad_k = 6.0 beat the shipped 5.0 on THIS LAB's own frames?

On the public Inconel 718 whole fields the extended sweep is decisive: 5.0 was the edge of
the grid, 6.0 wins on F1 in 27 of 31 images (p < 0.0001) and on area-fraction error in 23 of
31 (p = 0.0124). On the released crops the same change is a wash on F1 and worse on area,
which is what cropping around the cracks should do.

Neither of those is this laboratory's material, and the constant is the one thing in the app
a change would actually alter for its users. So the same sweep is run on the 48 hand-corrected
frames, with the scoring discipline this corpus requires:

  positives are corr == 1, negatives are corr == 2 or 3 (both are not-crack verdicts, 3 is
  erase), and corr == 0 is UNREFEREED and excluded from the confusion matrix entirely.
  Scoring unrefereed area as negative is what once turned a precision of 0.99 into 0.29.

Recall needs only positives, so it is measured on every frame that has painted crack.
Precision needs refereed negatives, so it is measured only on the frames that have them, and
the two frame sets are reported separately and never silently pooled -- a precision from one
set of frames and a recall from another do not combine into an F1.

Paired across frames with an exact Wilcoxon, because a difference of means between two
settings on the same images is not evidence. Opens the paint READ-ONLY.
"""
import json
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, os.path.join(SEM, "code"))
sys.path.insert(0, os.path.join(SEM, "interior_active_learning", "code"))
sys.dont_write_bytecode = True
import numpy as np
import tifffile
from scipy import ndimage as ndi, stats
from skimage import exposure, filters, measure as skm
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
from common import contrast_kwargs_for
Image.MAX_IMAGE_PIXELS = None

PAINT = os.path.join(SEM, "interior_active_learning", "paint")
GRID = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0]
ST8 = np.ones((3, 3), bool)


class U:
    pass


u = U()
DO.install(u)


def load_frame(name):
    raw = tifffile.imread(os.path.join(SEM, "original", name + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    ck = contrast_kwargs_for(name)
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]
    corr = np.array(Image.open(os.path.join(PAINT, name + "_correction_mask.png")))
    while corr.ndim > 2:
        corr = corr[..., 0]
    if corr.shape != img8.shape:
        if corr.shape[0] >= y1 and corr.shape[1] >= x1:
            corr = corr[y0:y1, x0:x1]
        else:
            return None
    return img8, corr


def body_of(img8, sigma=25):
    b = ndi.gaussian_filter(img8.astype(np.float32), sigma)
    body = ndi.binary_fill_holes(b >= filters.threshold_otsu(b))
    lab, n = ndi.label(body, structure=ST8)
    if n > 1:
        sz = np.bincount(lab.ravel()); sz[0] = 0
        keep = np.where(sz >= 0.02 * img8.size)[0]
        body = np.isin(lab, keep) if len(keep) else body
    return ndi.binary_fill_holes(body)


def clean(m):
    lab = skm.label(D.clean_mask(m, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel())
    k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


names = sorted(f[:-len("_correction_mask.png")]
               for f in os.listdir(PAINT) if f.endswith("_correction_mask.png"))
REC, PRE, MARK = {k: [] for k in GRID}, {k: [] for k in GRID}, {k: [] for k in GRID}
rec_names, pre_names = [], []

for nm in names:
    try:
        got = load_frame(nm)
    except Exception as e:
        print(f"  skip {nm}: {e}", flush=True)
        continue
    if got is None:
        print(f"  skip {nm}: mask does not fit the frame", flush=True)
        continue
    img8, corr = got
    pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
    if pos.sum() < 200:
        continue
    body = body_of(img8)
    flatv = D.flatten_background(img8)
    has_neg = neg.sum() >= 200
    rec_names.append(nm)
    if has_neg:
        pre_names.append(nm)
    for k in GRID:
        m = clean(u.segment_dark_regions(flatv, img8=img8, mad_k=k))
        REC[k].append(float((m & pos).sum() / max(pos.sum(), 1)))
        MARK[k].append(float(100.0 * (m & body).sum() / max(body.sum(), 1)))
        if has_neg:
            tp, fp = int((m & pos).sum()), int((m & neg).sum())
            PRE[k].append(tp / max(tp + fp, 1))
    print(f"  {nm}  crack {int(pos.sum()):>9d} px  "
          f"{'+neg ' + str(int(neg.sum())) if has_neg else 'no refereed negatives'}",
          flush=True)

print(f"\n{len(rec_names)} frames with painted crack (recall set)")
print(f"{len(pre_names)} of them also have refereed not-crack (precision set)\n")
print(f"  {'mad_k':>6s} {'recall':>8s} {'precision':>10s} {'marked% of body':>16s}")
for k in GRID:
    pr = np.mean(PRE[k]) if PRE[k] else float("nan")
    flag = "  <-- SHIPPED" if k == 5.0 else ""
    print(f"  {k:6.1f} {np.mean(REC[k]):8.4f} {pr:10.4f} {np.mean(MARK[k]):16.3f}{flag}")

print(f"\npaired against the shipped 5.0, exact Wilcoxon over the SAME frames")
OUT = {}
for k in GRID:
    if k == 5.0:
        continue
    row = {}
    for label, store, names_ in (("recall", REC, rec_names),
                                 ("precision", PRE, pre_names),
                                 ("marked% of body", MARK, rec_names)):
        a, b = np.array(store[k]), np.array(store[5.0])
        if len(a) < 3 or np.allclose(a, b):
            row[label] = {"n": len(a), "p": 1.0, "median_delta": 0.0}
            continue
        p = float(stats.wilcoxon(a, b, zero_method="wilcox").pvalue)
        row[label] = {"n": len(a), "p": p, "median_delta": float(np.median(a - b)),
                      "frames_up": int((a > b).sum()), "frames_down": int((a < b).sum())}
    OUT[str(k)] = row
    r, pq = row["recall"], row["precision"]
    print(f"  k={k:4.1f}  recall {r['median_delta']:+.4f} (p {r['p']:.4f}, n={r['n']})"
          f"   precision {pq['median_delta']:+.4f} (p {pq['p']:.4f}, n={pq['n']})")

p = os.path.join(REPO, "docs/figures/lab_madk_sweep.json")
json.dump({"grid": GRID, "n_recall_frames": len(rec_names),
           "n_precision_frames": len(pre_names),
           "recall_frames": rec_names, "precision_frames": pre_names,
           "means": {str(k): {"recall": float(np.mean(REC[k])),
                              "precision": float(np.mean(PRE[k])) if PRE[k] else None,
                              "marked_pct_of_body": float(np.mean(MARK[k]))} for k in GRID},
           "paired_vs_shipped_5": OUT,
           "scoring": "positives corr==1; negatives corr==2 or 3; corr==0 unrefereed and "
                      "excluded. Recall and precision use DIFFERENT frame sets and are "
                      "never pooled into an F1."},
          open(p, "w"), indent=1)
print("\nwrote", p)
