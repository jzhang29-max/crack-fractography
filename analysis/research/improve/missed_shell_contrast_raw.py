"""Re-measure the missed crack's contrast on the RAW image, not the flattened one.

The first pass reported Cohen's d = -3.556 for the labelled crack the darkness channel never
reaches -- brighter than background, strongly -- against +1.954 for the crack it does reach.
That would mean the missing 42.1% is not a darkness feature at all.

But it was measured on `flatten_background(img)`, and flattening subtracts a locally
estimated background. Beside a wide dark crack that estimate is dragged down, so pixels near
the crack come out bright relative to it. A flat-fielded image has manufactured a halo in
this project before. If the bright shell is an artefact of the flattening, it disappears on
the raw grey levels; if it survives there, it is really in the micrograph.

Both are reported here side by side, with the background band taken at a fixed standoff from
the label so neither measurement can be accused of choosing its own comparison region.
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
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None

FIELDS = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
          "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/"
          "pub_ebc_download/train_subset/Inconel718_crack")


class U:
    pass


u = U()
DO.install(u)


def load():
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


def d_vs(a, b):
    """Cohen's d, positive = group a is DARKER than group b."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    va, vb = np.var(a, ddof=1), np.var(b, ddof=1)
    s = np.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    return float((np.mean(b) - np.mean(a)) / s) if s > 0 else float("nan")


data = load()
rng = np.random.default_rng(0)
acc = {k: [] for k in ("raw_found", "raw_missed", "flat_found", "flat_missed",
                       "raw_missed_vs_found", "lvl_bg", "lvl_found", "lvl_missed")}

for stem, im, gt in data:
    flatv = D.flatten_background(im)
    opened = u.segment_dark_regions(flatv, img8=im, mad_k=0.5, absolute_dark_thresh=0)
    missed, found = gt & ~opened, gt & opened
    if missed.sum() < 10 or found.sum() < 10:
        continue
    # background: a fixed standoff ring, same region for every arm, so no measurement
    # gets to pick a comparison that flatters it
    band = ndi.binary_dilation(gt, iterations=12)
    bgm = ~band
    if bgm.sum() < 1000:
        continue
    idx = rng.choice(np.flatnonzero(bgm), size=min(int(bgm.sum()), 200000), replace=False)
    rb, fb = im.ravel()[idx].astype(float), flatv.ravel()[idx].astype(float)
    acc["raw_found"].append(d_vs(im[found].astype(float), rb))
    acc["raw_missed"].append(d_vs(im[missed].astype(float), rb))
    acc["flat_found"].append(d_vs(flatv[found].astype(float), fb))
    acc["flat_missed"].append(d_vs(flatv[missed].astype(float), fb))
    acc["raw_missed_vs_found"].append(d_vs(im[missed].astype(float),
                                           im[found].astype(float)))
    acc["lvl_bg"].append(float(rb.mean()))
    acc["lvl_found"].append(float(im[found].mean()))
    acc["lvl_missed"].append(float(im[missed].mean()))

n = len(acc["raw_found"])
print(f"{n} fields with both a found and a missed part\n")
print("Cohen's d against the same background ring (positive = DARKER than background)")
print(f"  {'':24s} {'RAW grey levels':>18s} {'FLATTENED':>14s}")
print(f"  {'crack the gate found':24s} {np.nanmean(acc['raw_found']):>18.3f} "
      f"{np.nanmean(acc['flat_found']):>14.3f}")
print(f"  {'crack it never found':24s} {np.nanmean(acc['raw_missed']):>18.3f} "
      f"{np.nanmean(acc['flat_missed']):>14.3f}")
print(f"\nmean grey level   background {np.mean(acc['lvl_bg']):6.1f}   "
      f"found {np.mean(acc['lvl_found']):6.1f}   missed {np.mean(acc['lvl_missed']):6.1f}")
print(f"missed vs found directly, raw: d = {np.nanmean(acc['raw_missed_vs_found']):+.3f} "
      f"(positive = missed is darker than found)")

flat_m, raw_m = np.nanmean(acc["flat_missed"]), np.nanmean(acc["raw_missed"])
print(f"\nVERDICT: the flattening moves the missed region's contrast by "
      f"{flat_m - raw_m:+.3f} d.")
if raw_m < -0.3:
    print("  The bright shell is REAL: it is brighter than background in the raw grey "
          "levels too.")
elif abs(raw_m) <= 0.3:
    print("  The missed crack is at BACKGROUND level in the raw image -- not dark, not "
          "bright. The flattened figure was largely an artefact of the flattening.")
else:
    print("  The missed crack IS darker than background in the raw image; the flattened "
          "figure inverted the sign and must not be used.")

p = os.path.join(REPO, "docs/figures/missed_shell_contrast_raw.json")
json.dump({"n_fields": n,
           "cohens_d_vs_background": {
               "raw": {"found": float(np.nanmean(acc["raw_found"])),
                       "missed": float(np.nanmean(acc["raw_missed"]))},
               "flattened": {"found": float(np.nanmean(acc["flat_found"])),
                             "missed": float(np.nanmean(acc["flat_missed"]))}},
           "mean_grey_level": {"background": float(np.mean(acc["lvl_bg"])),
                               "found": float(np.mean(acc["lvl_found"])),
                               "missed": float(np.mean(acc["lvl_missed"]))},
           "missed_vs_found_raw_d": float(np.nanmean(acc["raw_missed_vs_found"])),
           "note": "the flattened figure is reported only so the artefact is on record; "
                   "the raw grey levels are the measurement"},
          open(p, "w"), indent=1)
print("\nwrote", p)
