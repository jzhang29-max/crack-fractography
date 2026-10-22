"""The 42.1% the darkness channel cannot reach: what is it, and can anything else see it?

With both proposal gates opened to their limits the detector still reaches only 0.579 recall
on the 31 Inconel 718 whole fields, so 42.1% of the labelled crack is not dark at any scale.
That is a ceiling on the darkness channel. It is NOT automatically a ceiling on the method,
and the difference decides whether this detector can be improved at all:

  if the missed crack is invisible to every channel, the ceiling is the data and the honest
  answer is that no amount of work on the proposal stage helps;

  if the missed crack is visible to a DIFFERENT channel -- a ridge filter responds to a thin
  dark line whether or not its absolute level clears a darkness threshold -- then the ceiling
  is the channel, and a second channel is a real improvement rather than the width inflation
  that every post-processing attempt has turned out to be.

Three things are measured.

COVERAGE WITH A CHANCE CONTROL. How much of the missed crack a ridge filter marks, divided
by how much of the image that filter marks. A filter that marks 10% of the image covers 10%
of anything by accident, so coverage alone is not evidence; the lift over that is.

CONTRAST. Cohen's d of the missed crack against local background, beside the same figure for
the crack the detector did find. If the missed crack's contrast is near zero it is genuinely
not a darkness feature, which would explain the ceiling mechanically rather than by assertion.

REACHABILITY. How much of the missed crack lies within a few pixels of crack the detector
did find. That part is the thin extremity of a crack already detected and might be reached by
bridging; the rest is separate structure and needs the proposal stage to see it.
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
FIELDS = os.path.join(SCR, "pub_ebc_download/train_subset/Inconel718_crack")
RQ = (0.5, 1, 2, 4, 8)


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


def cohens_d(a, b):
    """Positive means the first group is DARKER than the second."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    va, vb = np.var(a, ddof=1), np.var(b, ddof=1)
    s = np.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    return float((np.mean(b) - np.mean(a)) / s) if s > 0 else float("nan")


data = load()
print(f"{len(data)} Inconel 718 whole fields\n", flush=True)

tot = {"gt": 0, "open": 0, "missed": 0, "reach2": 0, "reach5": 0, "reach10": 0}
cov = {q: {"hit": 0, "marked": 0, "px": 0} for q in RQ}
d_missed, d_found, d_open_all = [], [], []

for stem, im, gt in data:
    flatv = D.flatten_background(im)
    # both gates open to their limits: the darkness channel's own ceiling
    opened = u.segment_dark_regions(flatv, img8=im, mad_k=0.5, absolute_dark_thresh=0)
    missed = gt & ~opened
    found = gt & opened
    tot["gt"] += int(gt.sum()); tot["open"] += int(opened.sum())
    tot["missed"] += int(missed.sum())

    if missed.any() and found.any():
        dist_to_found = ndi.distance_transform_edt(~found)
        for t in (2, 5, 10):
            tot[f"reach{t}"] += int((dist_to_found[missed] <= t).sum())

    # contrast against background, on the flattened image the detector actually thresholds
    bg = flatv[~ndi.binary_dilation(gt, iterations=12)]
    if bg.size > 1000:
        s = np.random.default_rng(0).choice(bg, size=min(bg.size, 200000), replace=False)
        if missed.sum() > 10:
            d_missed.append(cohens_d(flatv[missed], s))
        if found.sum() > 10:
            d_found.append(cohens_d(flatv[found], s))

    R = filters.sato(im.astype(float), sigmas=range(1, 5), black_ridges=True)
    for q in RQ:
        rm = R >= np.percentile(R, 100 - q)
        cov[q]["hit"] += int((rm & missed).sum())
        cov[q]["marked"] += int(rm.sum())
        cov[q]["px"] += rm.size
    print(f"  {stem}: labelled {gt.sum():>8d}  open-gate found {found.sum():>8d}  "
          f"missed {missed.sum():>8d}", flush=True)

miss_frac = tot["missed"] / tot["gt"]
print(f"\n{'=' * 78}")
print(f"labelled crack           {tot['gt']:>10d} px")
print(f"reached, both gates open {tot['gt'] - tot['missed']:>10d} px  "
      f"({100 * (1 - miss_frac):.1f}% of labelled)")
print(f"NEVER reached            {tot['missed']:>10d} px  ({100 * miss_frac:.1f}% of labelled)")

print(f"\n--- is the missed crack a darkness feature at all? (Cohen's d vs background, "
      f"positive = darker) ---")
print(f"  crack the open gate DID find : d = {np.nanmean(d_found):+.3f}  "
      f"(n={len(d_found)} fields)")
print(f"  crack it NEVER found         : d = {np.nanmean(d_missed):+.3f}  "
      f"(n={len(d_missed)} fields)")

print(f"\n--- can a ridge filter see what the darkness channel cannot? ---")
print(f"  {'ridge top q%':>12s} {'covers missed':>14s} {'marks image':>12s} "
      f"{'LIFT over chance':>17s}")
for q in RQ:
    c = cov[q]
    coverage = c["hit"] / max(tot["missed"], 1)
    marked = c["marked"] / max(c["px"], 1)
    print(f"  {q:>11}% {100 * coverage:>13.2f}% {100 * marked:>11.2f}% "
          f"{coverage / max(marked, 1e-9):>16.2f}x")

print(f"\n--- how much of the missed crack sits beside crack that WAS found? ---")
for t in (2, 5, 10):
    print(f"  within {t:>2d} px of found crack : "
          f"{100 * tot[f'reach{t}'] / max(tot['missed'], 1):5.1f}%")

out = {
    "n_fields": len(data),
    "labelled_px": tot["gt"],
    "never_reached_px": tot["missed"],
    "never_reached_frac": miss_frac,
    "contrast_vs_background_cohens_d": {
        "found_by_open_gate": float(np.nanmean(d_found)),
        "never_found": float(np.nanmean(d_missed))},
    "ridge_coverage_of_missed": {
        str(q): {"coverage": cov[q]["hit"] / max(tot["missed"], 1),
                 "image_marked": cov[q]["marked"] / max(cov[q]["px"], 1),
                 "lift_over_chance": (cov[q]["hit"] / max(tot["missed"], 1))
                 / max(cov[q]["marked"] / max(cov[q]["px"], 1), 1e-9)} for q in RQ},
    "missed_within_px_of_found": {str(t): tot[f"reach{t}"] / max(tot["missed"], 1)
                                  for t in (2, 5, 10)},
    "reading": "lift over chance is the only honest form of the coverage number: a filter "
               "that marks x% of the image covers x% of anything for free",
}
p = os.path.join(REPO, "docs/figures/unproposed_crack_anatomy.json")
json.dump(out, open(p, "w"), indent=1)
print("\nwrote", p)
