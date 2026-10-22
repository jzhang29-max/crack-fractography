"""Can the lab-corpus scoring tell a detector from a bucket of paint?

The channel comparison on this lab's own frames put the shipped detector first by a wide
margin -- F1 0.8451 against Sato's 0.6635 -- and that result should not be believed until
this script runs, for two reasons visible in its own output. Precision came out at 0.95 to
0.97 for every single arm, which is not what five different detectors marking between 4%
and 21% of the specimen body should produce; and the winning arm was selected at mad_k = 1.0,
the most permissive rung on the grid, marking a fifth of the body.

Both point at the same thing. These correction masks are region assertions: a frame may
carry millions of painted-crack pixels and only a few thousand refereed not-crack pixels.
Precision measured over refereed pixels alone therefore has almost no negative evidence to
work with, so it stays near 1 however much an arm marks, the F1 collapses to recall, and
recall is maximised by marking everything.

So this is the positive control the ranking needed: arms that cannot possibly be good
detectors, scored by the identical rule.

  EVERYTHING ON THE BODY   marks the whole specimen. Recall 1.0 by construction.
  HALF THE BODY, RANDOM    a random half of the body, carrying no image information.
  MATCHED-AREA RANDOM      random pixels, same area as the shipped detector marks.

If any of these outranks a real detector, the instrument is measuring marked area rather
than detection and no ranking from it means anything. Opens the paint READ-ONLY.
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
rng = np.random.default_rng(0)
ACC, POSN, NEGN = {}, [], []

for nm in names:
    try:
        got = load_frame(nm)
    except Exception:
        continue
    if got is None:
        continue
    img8, corr = got
    pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
    if pos.sum() < 200 or neg.sum() < 200:
        continue
    body = body_of(img8)
    flatv = D.flatten_background(img8)
    POSN.append(int(pos.sum())); NEGN.append(int(neg.sum()))

    det1 = clean(u.segment_dark_regions(flatv, img8=img8, mad_k=1.0))
    det5 = clean(u.segment_dark_regions(flatv, img8=img8, mad_k=5.0))
    half = body & (rng.random(body.shape) < 0.5)
    matched = np.zeros(body.shape, bool)
    k = int(det5.sum())
    if k:
        idx = rng.choice(body.size, size=min(k, body.size), replace=False)
        matched.ravel()[idx] = True

    for label, m in (("DETECTOR mad_k=1.0 (the 'winner')", det1),
                     ("DETECTOR mad_k=5.0 (shipped)", det5),
                     ("CONTROL: everything on the body", body),
                     ("CONTROL: random half of the body", half),
                     ("CONTROL: random, area of shipped", matched)):
        tp = int((m & pos).sum()); fp = int((m & neg).sum()); fn = int((~m & pos).sum())
        pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
        ACC.setdefault(label, []).append(
            (pr, rc, 2 * pr * rc / max(pr + rc, 1e-12),
             100.0 * (m & body).sum() / max(body.sum(), 1)))
    print(f"  {nm}", flush=True)

n = len(POSN)
print(f"\n{n} frames. Refereed crack {sum(POSN):,} px; refereed NOT-crack "
      f"{sum(NEGN):,} px -- a ratio of {sum(POSN) / max(sum(NEGN), 1):.0f} to 1.")
print("Precision can only be wrong about the second number, and there is almost none "
      "of it.\n")
print(f"  {'arm':36s} {'prec':>7s} {'recall':>7s} {'F1':>7s} {'marked% body':>13s}")
rows = {k: tuple(float(np.mean([x[i] for x in v])) for i in range(4))
        for k, v in ACC.items()}
for k, r in sorted(rows.items(), key=lambda kv: -kv[1][2]):
    tag = "   <-- CANNOT DETECT ANYTHING" if k.startswith("CONTROL") else ""
    print(f"  {k:36s} {r[0]:7.4f} {r[1]:7.4f} {r[2]:7.4f} {r[3]:13.3f}{tag}")

top = max(rows.items(), key=lambda kv: kv[1][2])
print()
if top[0].startswith("CONTROL"):
    print(f"  VERDICT: the top arm is a control that reads nothing ({top[0]}, "
          f"F1 {top[1][2]:.4f}).")
    print("  This scoring cannot rank detectors on this corpus. Any ordering it produced "
          "is an ordering of marked area, and the channel comparison built on it is void.")
else:
    print(f"  VERDICT: every control ranks below a real detector; the ordering survives.")

p = os.path.join(REPO, "docs/figures/lab_scoring_positive_control.json")
json.dump({"n_frames": n, "refereed_crack_px": sum(POSN),
           "refereed_notcrack_px": sum(NEGN),
           "positive_to_negative_ratio": sum(POSN) / max(sum(NEGN), 1),
           "arms": {k: {"precision": r[0], "recall": r[1], "f1": r[2],
                        "marked_pct_of_body": r[3]} for k, r in rows.items()},
           "top_arm": top[0], "top_is_a_control": top[0].startswith("CONTROL"),
           "question": "can precision measured over refereed pixels alone penalise an arm "
                       "that marks everything"},
          open(p, "w"), indent=1)
print("\nwrote", p)
