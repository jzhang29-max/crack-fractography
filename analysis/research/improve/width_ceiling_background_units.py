"""The constant-width reconstruction, scored over every pixel instead of by IoU.

Section 4's construction takes the annotator's own mask, reduces it to its centreline, and
redraws it at a fixed width. The result is exactly right about where every crack is and
wrong only about how wide. Scored by IoU it fell well short of 1.0, which was the section's
point -- most of the available overlap is spent agreeing about width.

That point has to be remade in the units the rest of the paper now uses, because IoU
discards the background. So each redraw is scored here by accuracy, specificity and area
agreement, against the empty-mask baseline, exactly as every other table in the paper.

The question the plate then answers is sharper than the IoU version was: at what drawn
width does a perfectly-localised mask reproduce the annotator's own area fraction, and how
far is that from the width the detector actually draws?
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from skimage import morphology as morph
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

SCR = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
SETS = {
    "whole_fields": (os.path.join(SCR, "pub_ebc_download/train_subset/Inconel718_crack"),
                     "image", "mask", True),
    "crops": (os.path.join(SCR,
                           "pub_ebc_download/extracted/testsem/Inconel718_crack"),
              "image_cropped", "mask_cropped", False),
}
WIDTHS = [1, 3, 5, 7, 9, 13, 17, 21, 25, 31, 41, 51]


def load(root, idir, mdir, sixteen_bit):
    out = []
    ip, mp = os.path.join(root, idir), os.path.join(root, mdir)
    if sixteen_bit:
        stem = {os.path.splitext(f)[0]: f for f in os.listdir(mp)}
        for f in sorted(os.listdir(ip)):
            s = os.path.splitext(f)[0]
            if s not in stem:
                continue
            gt = np.array(Image.open(os.path.join(mp, stem[s])).convert("L")) > 127
            if gt.sum() >= 50:
                out.append(gt)
    else:
        for f in sorted(os.listdir(ip)):
            gt = np.array(Image.open(os.path.join(mp, f)).convert("L")) > 127
            if gt.sum() >= 50:
                out.append(gt)
    return out


RES = {}
for name, (root, idir, mdir, sb) in SETS.items():
    gts = load(root, idir, mdir, sb)
    print(f"\n{'=' * 86}\n{name}: {len(gts)} masks\n{'=' * 86}")
    lab = float(np.mean([100.0 * g.sum() / g.size for g in gts]))
    empty = 100.0 - lab
    print(f"  labelled {lab:.3f}%, an empty mask scores accuracy {empty:.3f}%\n")
    print(f"  {'drawn width':>12s} {'marked%':>9s} {'area rep./true':>15s} "
          f"{'accuracy%':>10s} {'spec%':>8s}")
    rows = {}
    skels = [morph.skeletonize(g) for g in gts]
    for w in WIDTHS:
        r = max((w - 1) // 2, 0)
        accs, specs, marks = [], [], []
        for g, sk in zip(gts, skels):
            m = ndi.binary_dilation(sk, morph.disk(r)) if r else sk
            tp = float((m & g).sum()); fp = float((m & ~g).sum())
            fn = float((~m & g).sum()); tn = g.size - tp - fp - fn
            accs.append(100.0 * (tp + tn) / g.size)
            specs.append(100.0 * tn / max(tn + fp, 1e-12))
            marks.append(100.0 * m.sum() / m.size)
        rows[w] = {"marked_pct": float(np.mean(marks)),
                   "area_agreement": float(np.mean(marks) / lab),
                   "accuracy_pct": float(np.mean(accs)),
                   "specificity_pct": float(np.mean(specs))}
        print(f"  {w:12d} {rows[w]['marked_pct']:9.3f} {rows[w]['area_agreement']:15.3f} "
              f"{rows[w]['accuracy_pct']:10.3f} {rows[w]['specificity_pct']:8.3f}")
    best_a = max(rows.items(), key=lambda kv: kv[1]["accuracy_pct"])
    best_r = min(rows.items(), key=lambda kv: abs(kv[1]["area_agreement"] - 1.0))
    print(f"\n  a PERFECTLY LOCALISED redraw peaks at accuracy "
          f"{best_a[1]['accuracy_pct']:.3f}% at {best_a[0]} px "
          f"(an empty mask scores {empty:.3f}%)")
    print(f"  it reproduces the labelled area fraction at {best_r[0]} px "
          f"({best_r[1]['area_agreement']:.3f}x)")
    RES[name] = {"labelled_pct": lab, "empty_mask_accuracy_pct": empty,
                 "n": len(gts), "by_width": rows,
                 "best_accuracy_width": best_a[0],
                 "best_accuracy_pct": best_a[1]["accuracy_pct"],
                 "area_match_width": best_r[0]}

p = os.path.join(REPO, "docs/figures/width_ceiling_background_units.json")
json.dump({"widths": WIDTHS, "sets": RES,
           "construction": "the annotator's own mask reduced to its centreline and redrawn "
                           "at a fixed width: exactly right about location, wrong only "
                           "about width",
           "measures": "accuracy, specificity and area agreement, all over every pixel"},
          open(p, "w"), indent=1)
print("\nwrote", p)
