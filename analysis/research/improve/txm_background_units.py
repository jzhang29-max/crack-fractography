"""The SEM detector on TXM, scored in the units this paper reports.

TXM is a BETTER substrate for this question than our own SEM corpus, and that is why it is
worth running. Its hand-made corrections carry 263,692,695 not-crack pixels against
8,518,853 crack -- a 31:1 ratio the other way round from the SEM paint, where certified
not-crack is a fraction of a percent of the refereed pool and cannot price a false positive
at all. On TXM a false positive costs something, so accuracy and specificity mean what they
say.

Scored over REFEREED PIXELS ONLY: 1 = crack, 2 or 3 = not-crack, 0 = unreviewed and
excluded from both ends. Every percentage below is therefore a percentage of the refereed
area, not of the whole frame, and the refereed coverage of each frame is reported beside
it so the denominator is never implicit.

Measures, as elsewhere in the paper: the four-way pixel budget, accuracy with the
EMPTY-MASK baseline, specificity, and the agreement between the crack area fraction
reported and the one painted. Overlap scores are not reported and must not be computed
from this set: a prior measurement puts the TXM IoU ceiling for a correct 3 px crack at
0.0498, because the paint is far wider than the feature, so overlap here rewards imitating
the brush.

Swept over mad_k, because the SEM optimum moved from 5.0 to 6.0 when its sweep was
extended and there is no reason the TXM optimum should be the same one. Two controls that
a useful arm has to beat: mark everything, and a plain Otsu darkness cut with no model.
Split by specimen group, because the four groups are different materials and a pooled
number over them is a weighted mean of four different answers.
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
TXM = "/Users/jiamingzhang/Desktop/APP/TXM_Crack_Detection_Pipeline"
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from skimage import filters, measure as skm
import detect_cracks as D
import detector_overrides as DO

GRID = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0]


def group_of(name):
    """The four specimen groups, by the TXM project's own rule."""
    n = name.lower()
    if "_b3_" in n:
        return "B3"
    if "wrought" in n:
        return "Wrought"
    if "hc_316l" in n:
        return "AM/HC"
    if "_b2_" in n or "b2_" in n:
        return "B2"
    return "other"


def arm(k):
    class U:
        pass
    u = U()
    DO.install(u)
    return u


U = arm(None)


def cand(m):
    lab = skm.label(D.clean_mask(m, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel())
    k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


names = []
cdir = os.path.join(TXM, "paint", "corrections")
for f in sorted(os.listdir(cdir)):
    if not f.endswith("_correction.npy"):
        continue
    stem = f[: -len("_correction.npy")]
    tif = os.path.join(TXM, "images", stem + ".tif")
    if os.path.exists(tif):
        names.append((stem, tif, os.path.join(cdir, f)))
print(f"{len(names)} TXM frames have both an image and a correction mask\n", flush=True)

ARMS = [f"SEM detector, mad_k={k:g}" for k in GRID] + \
       ["control: Otsu, no model", "control: mark everything"]
ACC = {a: {"tp": 0, "fp": 0} for a in ARMS}
BYGRP = {}
tot_c = tot_n = tot_px = 0
used = 0

for i, (stem, tif, cpath) in enumerate(names, 1):
    try:
        corr = np.load(cpath)
        crack = corr == 1
        notc = (corr == 2) | (corr == 3)
        if int(crack.sum()) < 5000 or int(notc.sum()) < 5000:
            continue
        img8 = D.load_as_uint8(tif)
        if img8.shape != corr.shape:
            print(f"  [{i}] shape mismatch {img8.shape} vs {corr.shape} -- skipped",
                  flush=True)
            continue
        g = group_of(stem)
        flat = D.flatten_background(img8)
        masks = {}
        for k in GRID:
            masks[f"SEM detector, mad_k={k:g}"] = cand(
                U.segment_dark_regions(flat, img8=img8, mad_k=k))
        sm = filters.gaussian(flat, sigma=1.0, preserve_range=True)
        masks["control: Otsu, no model"] = sm < filters.threshold_otsu(sm)
        masks["control: mark everything"] = np.ones(img8.shape, bool)

        tot_c += int(crack.sum()); tot_n += int(notc.sum()); tot_px += int(corr.size)
        used += 1
        gb = BYGRP.setdefault(g, {"c": 0, "n": 0, "arms": {a: {"tp": 0, "fp": 0}
                                                           for a in ARMS}, "frames": 0})
        gb["c"] += int(crack.sum()); gb["n"] += int(notc.sum()); gb["frames"] += 1
        for a, m in masks.items():
            tp = int((m & crack).sum()); fp = int((m & notc).sum())
            ACC[a]["tp"] += tp; ACC[a]["fp"] += fp
            gb["arms"][a]["tp"] += tp; gb["arms"][a]["fp"] += fp
        r6 = masks["SEM detector, mad_k=6"]
        print(f"  [{i:>2}/{len(names)}] {g:<8} {stem[:40]:<42} refereed "
              f"{100 * (crack.sum() + notc.sum()) / corr.size:5.1f}% of frame   "
              f"crack {int(crack.sum()):>9,}   k6 reaches "
              f"{int((r6 & crack).sum()) / max(int(crack.sum()), 1):.3f}", flush=True)
    except Exception as e:
        print(f"  [{i}] {stem[:40]} ERROR {type(e).__name__}: {e}", flush=True)


def report(label, c, n, arms):
    ref = c + n
    prev = 100.0 * c / max(ref, 1)
    empty = 100.0 - prev
    print(f"\n{'=' * 104}\n{label}: {c:,} crack and {n:,} not-crack refereed px "
          f"({n / max(c, 1):.1f}:1)")
    print(f"crack is {prev:.3f}% of the refereed area, so an EMPTY MASK scores "
          f"{empty:.3f}% accuracy there\n{'=' * 104}")
    print(f"  {'arm':<28} {'marked%':>8} {'right%':>7} {'wrong%':>7} {'accuracy%':>10} "
          f"{'vs empty':>9} {'spec%':>8} {'area':>7}")
    out = {}
    for a in arms:
        tp, fp = arms[a]["tp"], arms[a]["fp"]
        fn = c - tp
        tn = n - fp
        acc = 100.0 * (tp + tn) / max(ref, 1)
        row = {"marked_pct": 100.0 * (tp + fp) / max(ref, 1),
               "tp_pct": 100.0 * tp / max(ref, 1), "fp_pct": 100.0 * fp / max(ref, 1),
               "fn_pct": 100.0 * fn / max(ref, 1), "tn_pct": 100.0 * tn / max(ref, 1),
               "accuracy_pct": acc, "empty_mask_accuracy_pct": empty,
               "margin_pp": acc - empty,
               "specificity_pct": 100.0 * tn / max(n, 1),
               "area_agreement": (tp + fp) / max(c, 1)}
        out[a] = row
        print(f"  {a:<28} {row['marked_pct']:8.3f} {row['tp_pct']:7.3f} "
              f"{row['fp_pct']:7.3f} {acc:9.3f}{'+' if row['margin_pp'] > 0 else '-'} "
              f"{row['margin_pp']:+9.3f} {row['specificity_pct']:8.3f} "
              f"{row['area_agreement']:7.3f}")
    det = {a: v for a, v in out.items() if a.startswith("SEM detector")}
    if det:
        ba = min(det.items(), key=lambda kv: abs(kv[1]["area_agreement"] - 1.0))
        bc = max(det.items(), key=lambda kv: kv[1]["accuracy_pct"])
        print(f"\n  closest area fraction : {ba[0]} at {ba[1]['area_agreement']:.3f}x")
        print(f"  highest accuracy      : {bc[0]} at {bc[1]['accuracy_pct']:.3f}% "
              f"({bc[1]['margin_pp']:+.3f} pp vs an empty mask)")
    return out


POOL = report(f"POOLED over {used} TXM frames", tot_c, tot_n, ACC)
PER = {}
for g in sorted(BYGRP):
    gb = BYGRP[g]
    PER[g] = {"frames": gb["frames"], "crack_px": gb["c"], "notcrack_px": gb["n"],
              "arms": report(f"{g}  ({gb['frames']} frames)", gb["c"], gb["n"],
                             gb["arms"])}

print(f"\nrefereed coverage: {100 * (tot_c + tot_n) / max(tot_px, 1):.1f}% of all "
      f"pixels in the {used} frames were ruled on by a human. Every percentage above is "
      f"of the refereed area, not of the frame.")

p = os.path.join(REPO, "docs/figures/txm_background_units.json")
json.dump({"n_frames": used, "refereed_crack_px": tot_c, "refereed_notcrack_px": tot_n,
           "refereed_coverage_frac": (tot_c + tot_n) / max(tot_px, 1),
           "pooled": POOL, "by_group": PER, "grid": GRID,
           "scoring": "refereed pixels only: 1 = crack, 2 or 3 = not-crack, 0 excluded. "
                      "Percentages are of the refereed area.",
           "why_no_overlap_scores": "the TXM paint is far wider than the feature; a prior "
                                    "measurement puts the IoU ceiling for a correct 3 px "
                                    "crack at 0.0498, so overlap here ranks brush "
                                    "imitation"},
          open(p, "w"), indent=1)
print("\nwrote", p)
