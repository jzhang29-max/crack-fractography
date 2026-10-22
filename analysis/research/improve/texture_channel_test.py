"""Is the crack interior separable by TEXTURE, where it is not separable by darkness?

The panels settled what the missing 42.1% is. These cracks are open wide enough to see down
into, and the annotator's band covers the whole opening: a shadowed void at the near edge
and, beside it, the exposed fracture surface, lit and rough. The darkness channel marks the
shadow and nothing else. The fracture surface is BRIGHTER than matrix -- grey level 127
against 82 -- so no darkness threshold will ever reach it, which is the ceiling measured
earlier and the reason an added ridge filter helped so little: a ridge filter looks for thin
dark lines, and this is a wide bright region.

But a fracture surface is not smooth. That is the hypothesis this tests: the crack interior
differs from the matrix in LOCAL VARIANCE rather than in level. If it does, there is a real
improvement available that reads the image -- unlike the dilation, which reads nothing -- and
if it does not, the ceiling stands.

Three groups are compared on the same fields: matrix, the dark core the detector reaches,
and the interior it never reaches. Separability is reported as the AUC of local roughness
between the missed interior and the matrix, since AUC needs no threshold and cannot be
flattered by a scale choice. The same statistic is computed for raw grey level, which is
known to fail, so the comparison has a floor to beat rather than only a number.
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
SCALES = (3, 5, 9, 15)


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


def local_sd(im, w):
    f = im.astype(np.float32)
    m = ndi.uniform_filter(f, w)
    m2 = ndi.uniform_filter(f * f, w)
    return np.sqrt(np.maximum(m2 - m * m, 0))


def auc(pos, neg, rng, cap=60000):
    """Probability a random positive outranks a random negative. No threshold to choose."""
    if len(pos) < 50 or len(neg) < 50:
        return float("nan")
    if len(pos) > cap:
        pos = rng.choice(pos, cap, replace=False)
    if len(neg) > cap:
        neg = rng.choice(neg, cap, replace=False)
    allv = np.concatenate([pos, neg])
    r = np.empty(len(allv))
    r[np.argsort(allv, kind="mergesort")] = np.arange(1, len(allv) + 1)
    # average ranks for ties, else a flat feature scores above 0.5 by accident
    order = np.argsort(allv, kind="mergesort")
    sv = allv[order]
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            r[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    n1, n2 = len(pos), len(neg)
    return float((r[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * n2))


data = load()
rng = np.random.default_rng(0)
res = {f"sd{w}": [] for w in SCALES}
res["grey"] = []
res_core = {f"sd{w}": [] for w in SCALES}

for stem, im, gt in data:
    flatv = D.flatten_background(im)
    opened = u.segment_dark_regions(flatv, img8=im, mad_k=0.5, absolute_dark_thresh=0)
    missed, found = gt & ~opened, gt & opened
    matrix = ~ndi.binary_dilation(gt, iterations=12)
    if missed.sum() < 200 or matrix.sum() < 5000:
        continue
    res["grey"].append(auc(im[missed].astype(float), im[matrix].astype(float), rng))
    for w in SCALES:
        s = local_sd(im, w)
        res[f"sd{w}"].append(auc(s[missed], s[matrix], rng))
        if found.sum() > 200:
            res_core[f"sd{w}"].append(auc(s[found], s[matrix], rng))
    print(f"  {stem}", flush=True)

print(f"\n{'=' * 76}")
print("Separating the crack interior the detector NEVER reaches from the matrix.")
print("AUC 0.5 = the feature carries no information. Higher = interior scores higher.\n")
print(f"  {'feature':24s} {'AUC':>7s}   {'reading'}")
g = float(np.nanmean(res["grey"]))
print(f"  {'raw grey level':24s} {g:7.4f}   "
      f"{'the known failure -- the interior is BRIGHTER, so a darkness cut inverts here'}")
best, bestv = None, 0
for w in SCALES:
    v = float(np.nanmean(res[f"sd{w}"]))
    if v > bestv:
        best, bestv = w, v
    print(f"  {'local SD, ' + str(w) + ' px window':24s} {v:7.4f}")
print(f"\n  for comparison, the same roughness on the DARK CORE vs matrix: "
      f"{float(np.nanmean(res_core[f'sd{best}'])):.4f} at {best} px")
print(f"\n  best roughness scale: {best} px, AUC {bestv:.4f}")
if bestv > 0.80:
    print("  => the interior IS strongly separable by texture where it is invisible to "
          "darkness.\n     A texture channel is a real improvement route, not a dilation.")
elif bestv > 0.65:
    print("  => partially separable. Worth a prototype, but it will not close the gap "
          "alone.")
else:
    print("  => NOT separable by texture either. The ceiling stands.")

p = os.path.join(REPO, "docs/figures/texture_channel_test.json")
json.dump({"n_fields": len(res["grey"]),
           "auc_missed_interior_vs_matrix": {
               "raw_grey_level": g,
               **{f"local_sd_{w}px": float(np.nanmean(res[f"sd{w}"])) for w in SCALES}},
           "auc_dark_core_vs_matrix_same_feature": {
               f"local_sd_{w}px": float(np.nanmean(res_core[f"sd{w}"])) for w in SCALES},
           "best_scale_px": best, "best_auc": bestv,
           "what_the_missed_region_is": "the lit, rough fracture surface visible inside a "
                                        "wide-open crack; the detector marks only the "
                                        "shadowed void beside it"},
          open(p, "w"), indent=1)
print("\nwrote", p)
