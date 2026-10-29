"""Every TXM frame on its own, in the units the TXM section reports.

WHY. `txm_background_units.json` pools pixels inside each specimen group, and one frame
can then carry the group. It does: of B3's 2,431,104 refereed crack pixels, 1,472,046 --
61% -- are in a single frame, and the paint in that frame is 483 px wide at the 90th
percentile, 14 um at the derived 29.24 nm/px. That is a region, not a crack. The group's
headline number is therefore a statement about that one frame, and nobody reading the
pooled file can tell.

This writes the per-frame rows the pooled file never kept, so three things become
checkable: whether a group's margin survives dropping its largest frame, which frame a
figure is entitled to show, and how wide the operator painted in each one.

Also emits the SELECTION RULE a figure panel should use. The transfer plate picked
`max(crack pixels)` per group, which is the rule that selects the widest blob in the set
and did. The rule here is max SKELETON LENGTH of the painted crack: the longest painted
crack rather than the largest painted area, which a blob cannot win because its medial
axis is short relative to its area.

Refereed pixels only: 1 = crack, 2 or 3 = not-crack, 0 excluded. Opens the paint READ-ONLY.
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
from skimage import filters, measure as skm, morphology as morph
import detect_cracks as D
import detector_overrides as DO

CORR = os.path.join(TXM, "paint", "corrections")
GRID = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0]
NM_PER_PX = 29.24


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


def group_of(n):
    n = n.lower()
    if "_b3_" in n:
        return "B3"
    if "wrought" in n:
        return "Wrought"
    if "hc_316l" in n:
        return "AM/HC"
    return "B2"


rows = []
files = sorted(f for f in os.listdir(CORR) if f.endswith("_correction.npy"))
for i, f in enumerate(files, 1):
    stem = f[: -len("_correction.npy")]
    tif = os.path.join(TXM, "images", stem + ".tif")
    if not os.path.exists(tif):
        continue
    corr = np.load(os.path.join(CORR, f))
    crack = corr == 1
    notc = (corr == 2) | (corr == 3)
    c, n = int(crack.sum()), int(notc.sum())
    if c < 5000 or n < 5000:
        continue
    img8 = D.load_as_uint8(tif)
    if img8.shape != corr.shape:
        print(f"  skip {stem[:44]}: shape mismatch", flush=True)
        continue
    flat = D.flatten_background(img8)
    dt = ndi.distance_transform_edt(crack)
    sk = morph.skeletonize(crack)
    row = {"frame": stem, "group": group_of(stem),
           "crack_px": c, "notcrack_px": n,
           "refereed_frac": float((c + n) / corr.size),
           "crack_share_of_refereed_pct": 100.0 * c / (c + n),
           "paint_width_p90_px": float(2 * np.percentile(dt[crack], 90)),
           "paint_width_median_px": float(2 * np.median(dt[crack])),
           "skeleton_px": int(sk.sum()),
           "arms": {}}
    sm = filters.gaussian(flat, sigma=1.0, preserve_range=True)
    masks = {f"SEM detector, mad_k={k:g}":
             clean(u.segment_dark_regions(flat, img8=img8, mad_k=k)) for k in GRID}
    masks["control: Otsu, no model"] = sm < filters.threshold_otsu(sm)
    masks["control: mark everything"] = np.ones(img8.shape, bool)
    empty = 100.0 * n / (c + n)
    for a, m in masks.items():
        tp, fp = int((m & crack).sum()), int((m & notc).sum())
        acc = 100.0 * (tp + (n - fp)) / (c + n)
        row["arms"][a] = {"tp_pct": 100.0 * tp / (c + n), "fp_pct": 100.0 * fp / (c + n),
                          "accuracy_pct": acc, "empty_mask_accuracy_pct": empty,
                          "margin_pp": acc - empty,
                          "recall": tp / max(c, 1),
                          "precision": tp / max(tp + fp, 1),
                          "area_agreement": (tp + fp) / max(c, 1)}
    rows.append(row)
    r6 = row["arms"]["SEM detector, mad_k=6"]
    print(f"  [{i:>2}] {row['group']:<8} {stem[:38]:<40} crack {c:>9,} "
          f"({row['crack_share_of_refereed_pct']:5.1f}% of refereed)  paint p90 "
          f"{row['paint_width_p90_px']:6.1f} px  skel {row['skeleton_px']:>7,}  "
          f"k6 margin {r6['margin_pp']:+7.2f} pp  area {r6['area_agreement']:6.2f}x",
          flush=True)

K6 = "SEM detector, mad_k=6"
print(f"\n{'=' * 104}\nPER GROUP: pooled margin, and the margin with the single largest "
      f"frame dropped\n{'=' * 104}")
SUMM = {}
for g in ("B3", "B2", "Wrought", "AM/HC"):
    sub = [r for r in rows if r["group"] == g]
    if not sub:
        continue

    def pooled(rs):
        c = sum(r["crack_px"] for r in rs)
        n = sum(r["notcrack_px"] for r in rs)
        tp = sum(r["arms"][K6]["tp_pct"] / 100 * (r["crack_px"] + r["notcrack_px"])
                 for r in rs)
        fp = sum(r["arms"][K6]["fp_pct"] / 100 * (r["crack_px"] + r["notcrack_px"])
                 for r in rs)
        acc = 100.0 * (tp + (n - fp)) / (c + n)
        return acc - 100.0 * n / (c + n), (tp + fp) / max(c, 1)

    big = max(sub, key=lambda r: r["crack_px"])
    m_all, a_all = pooled(sub)
    rest = [r for r in sub if r is not big]
    m_cut, a_cut = pooled(rest) if rest else (float("nan"), float("nan"))
    mean_margin = float(np.mean([r["arms"][K6]["margin_pp"] for r in sub]))
    SUMM[g] = {"n": len(sub), "pooled_margin_pp": m_all, "pooled_area": a_all,
               "margin_without_largest_frame_pp": m_cut,
               "area_without_largest_frame": a_cut,
               "mean_of_per_frame_margins_pp": mean_margin,
               "largest_frame": big["frame"],
               "largest_frame_share_of_group_crack_px":
                   big["crack_px"] / sum(r["crack_px"] for r in sub),
               "longest_skeleton_frame": max(sub, key=lambda r: r["skeleton_px"])["frame"]}
    print(f"  {g:<8} n={len(sub):<3} pooled {m_all:+7.2f} pp | drop largest "
          f"({big['largest' if False else 'frame'][:34]}, "
          f"{100 * SUMM[g]['largest_frame_share_of_group_crack_px']:.0f}% of the group's "
          f"crack px) -> {m_cut:+7.2f} pp | mean of per-frame margins {mean_margin:+7.2f} pp")
    print(f"           longest painted crack in the group: "
          f"{SUMM[g]['longest_skeleton_frame'][:60]}")

p = os.path.join(REPO, "docs/figures/txm_per_frame.json")
json.dump({"mad_k_grid": GRID, "nm_per_px": NM_PER_PX,
           "scoring": "refereed pixels only: 1 = crack, 2 or 3 = not-crack, 0 excluded",
           "panel_selection_rule": "max skeleton_px within a group: the longest painted "
                                   "crack, not the largest painted area",
           "n_frames": len(rows), "per_group": SUMM, "frames": rows},
          open(p, "w"), indent=1)
print("\nwrote", p)
