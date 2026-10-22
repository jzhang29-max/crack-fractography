"""Do the classical channels beat the shipped detector on THIS LAB's own micrographs?

On the public Inconel 718 whole fields, Sato ridge beat the shipped darkness detector on
precision, recall, F1 and area-fraction fidelity at once, at the same single free parameter,
and Sauvola reported an area fraction 1.08x the labelled value against the detector's 1.65x.
That is the first improvement in this whole investigation that is not a disguised dilation:
these are independent detectors that read the image, so they need no decoy.

But a public-data win has failed to transfer in this project more than once, and the
shipped constant was fitted on SEM steel in a different laboratory. The question that
decides whether anything should change in the app is whether the same ordering holds on the
48 hand-corrected frames of this lab's own corpus.

SCORING DISCIPLINE, which is different here and matters more than the arms:

  The correction masks are REGION ASSERTIONS over part of the frame, not a complete
  segmentation. State 1 is painted crack, states 2 and 3 are both not-crack verdicts
  (3 is erase), and state 0 is UNREFEREED -- nobody looked. Scoring state 0 as negative is
  what produced a precision bracket of [0.29, 0.99] in this project once before, because
  99.4% of the apparent false positives had never been refereed by anyone. So every pixel
  with corr == 0 is excluded from the confusion matrix entirely, and precision and recall
  here mean "among pixels a human actually ruled on".

  For the same reason NO area-fraction ratio is reported on this corpus. The true crack
  area fraction of these frames is not known -- only a fraction of each frame was refereed
  -- so a ratio would be inventing its own denominator. The marked percentage of the
  specimen body is printed instead, as a descriptive number, and the public set remains the
  only place an area-fraction error can honestly be quoted.

Selection is leave-one-SPECIMEN-out, not leave-one-frame-out: there are 48 frames but only
11 specimens, and frames of the same specimen are not independent observations.

Opens the paint READ-ONLY and writes nothing outside docs/figures.
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
sys.path.insert(0, os.path.join(SEM, "interior_active_learning", "code"))
sys.dont_write_bytecode = True
import re
import numpy as np
import tifffile
from scipy import ndimage as ndi
from skimage import exposure, filters, measure as skm
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
from common import contrast_kwargs_for
Image.MAX_IMAGE_PIXELS = None

PAINT = os.path.join(SEM, "interior_active_learning", "paint")
ST8 = np.ones((3, 3), bool)


class U:
    pass


u = U()
DO.install(u)


def load_frame(name):
    """The project's own loader: same stretch, same field-of-view crop, same alignment.
    A second loader would make these numbers incomparable with everything measured before."""
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


def specimen_mask(img8, sigma=25):
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


def ridge(im, q, kind):
    f = {"frangi": filters.frangi, "sato": filters.sato,
         "meijering": filters.meijering}[kind]
    r = f(im.astype(float), sigmas=range(1, 5), black_ridges=True)
    return clean(r >= np.percentile(r, 100 - q))


ARMS = [
    ("DETECTOR (shipped)", [5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0],
     lambda im, k: clean(u.segment_dark_regions(D.flatten_background(im), img8=im, mad_k=k))),
    ("Sato ridge", [0.5, 1, 2, 4, 8], lambda im, q: ridge(im, q, "sato")),
    ("Meijering ridge", [0.5, 1, 2, 4, 8], lambda im, q: ridge(im, q, "meijering")),
    ("Frangi ridge", [0.5, 1, 2, 4, 8], lambda im, q: ridge(im, q, "frangi")),
    ("Sauvola local", [15, 25, 51, 101],
     lambda im, w: clean(im < filters.threshold_sauvola(im, window_size=w))),
]

names = sorted(f[:-len("_correction_mask.png")]
               for f in os.listdir(PAINT) if f.endswith("_correction_mask.png"))
frames = []
for nm in names:
    try:
        got = load_frame(nm)
    except Exception as e:
        print(f"  skip {nm}: {e}", flush=True)
        continue
    if got is None:
        print(f"  skip {nm}: correction mask does not fit the frame", flush=True)
        continue
    img8, corr = got
    pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
    if pos.sum() < 200 or neg.sum() < 200:
        print(f"  skip {nm}: too little refereed area "
              f"(crack {int(pos.sum())}, not-crack {int(neg.sum())})", flush=True)
        continue
    frames.append((nm, re.sub(r"_(CBS|ETD)_\d+$", "", nm), img8, pos, neg,
                   specimen_mask(img8)))
    print(f"  {nm}: refereed crack {int(pos.sum()):>9d} px, "
          f"not-crack {int(neg.sum()):>10d} px", flush=True)

specs = sorted({f[1] for f in frames})
print(f"\n{len(frames)} frames across {len(specs)} specimens\n", flush=True)

RES = {}
for nm, grid, fn in ARMS:
    by = {}
    for p in grid:
        rows = []
        for _, _, img8, pos, neg, body in frames:
            try:
                m = fn(img8, p)
            except Exception:
                m = np.zeros(img8.shape, bool)
            tp = int((m & pos).sum()); fp = int((m & neg).sum())
            fnn = int((~m & pos).sum())
            pr = tp / max(tp + fp, 1); rc = tp / max(tp + fnn, 1)
            rows.append({"precision": pr, "recall": rc,
                         "f1": 2 * pr * rc / max(pr + rc, 1e-12),
                         "iou": tp / max(tp + fp + fnn, 1),
                         "marked_pct_of_body": 100.0 * (m & body).sum() / max(body.sum(), 1)})
        by[p] = rows
    # leave-one-SPECIMEN-out: 48 frames but only 11 independent specimens
    picks = []
    for i, f in enumerate(frames):
        other = [j for j, g in enumerate(frames) if g[1] != f[1]]
        best = max(grid, key=lambda p: np.mean([by[p][j]["f1"] for j in other]))
        picks.append((best, i))
    agg = {k: float(np.mean([by[p][i][k] for p, i in picks])) for k in by[grid[0]][0]}
    agg["modal_param"] = str(max(set(p for p, _ in picks),
                                 key=[p for p, _ in picks].count))
    RES[nm] = agg

print(f"{'arm':24s} {'prec':>7s} {'recall':>7s} {'F1':>7s} {'IoU':>7s} "
      f"{'marked% body':>13s}  param")
for nm, r in sorted(RES.items(), key=lambda kv: -kv[1]["f1"]):
    print(f"{nm:24s} {r['precision']:7.4f} {r['recall']:7.4f} {r['f1']:7.4f} "
          f"{r['iou']:7.4f} {r['marked_pct_of_body']:13.3f}  {r['modal_param']}")

s = RES["DETECTOR (shipped)"]["f1"]
best = max(RES.items(), key=lambda kv: kv[1]["f1"])
print(f"\nshipped {s:.4f}; best is {best[0]} at {best[1]['f1']:.4f} "
      f"({best[1]['f1'] - s:+.4f})")
print("precision and recall are over REFEREED pixels only; unrefereed area is excluded, "
      "and no area-fraction ratio is quoted on this corpus because the true crack area "
      "fraction of these frames is not known.")

p = os.path.join(REPO, "docs/figures/lab_corpus_channels.json")
json.dump({"n_frames": len(frames), "n_specimens": len(specs), "specimens": specs,
           "selection": "leave-one-SPECIMEN-out", "arms": RES,
           "scoring": "positives corr==1; negatives corr==2 or 3; corr==0 unrefereed and "
                      "EXCLUDED from the confusion matrix",
           "no_area_ratio_because": "only part of each frame was refereed, so the true "
                                    "crack area fraction is unknown and a ratio would "
                                    "invent its denominator"},
          open(p, "w"), indent=1)
print("\nwrote", p)
