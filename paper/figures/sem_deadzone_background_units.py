"""The region-classifier ablation, re-scored over every pixel instead of by IoU.

Section 2 reports that switching the bundled region classifier off improved every metric at
no cost in free parameters: paired median IoU +0.1753 over thirteen specimens, 11 of 13,
Wilcoxon p = 0.0061. That was the last measurement in the paper still quoted in overlap
units, which discard every pixel correctly left alone -- and on these tiles that is most of
the frame. This re-runs the identical three arms on the identical tiles and reports them in
the units Section 3.3 now uses.

  A  v1.47      candidates, then the bundled logistic region classifier at its threshold.
  B  ablation   the SAME candidates with the classifier bypassed and every region kept.
                Exactly one variable differs from A, so A -> B is the classifier's own
                effect and nothing else's.
  C  v1.49.2    the shipped path: seven flattening radii AND the classifier off. TWO
                variables differ from A, so its larger delta is not the classifier's.

The arm-B IoU values are asserted against the stored record before anything else is
computed. If the arms have drifted, every number below would be measuring something other
than what Section 2 claims, and the assertion is the only thing that would notice.

Measures, all over every pixel of the tile:
  accuracy        with the accuracy of an EMPTY MASK printed beside it, because leaving the
                  background alone is free and an accuracy below that line was not earned.
  specificity     the share of background correctly left alone.
  area agreement  marked area divided by labelled area; 1.000 is exact.
Paired per specimen with an exact Wilcoxon, one pair per specimen, as the original did.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import json
import time

import numpy as np

TB = _paths.tilebench()
import angle4_shipped as A4        # noqa: E402  (on sys.path via _paths.tilebench)
import crackpipe as CP             # noqa: E402
from scipy.stats import wilcoxon   # noqa: E402

# this file lives in paper/figures/, so the repository root is three levels up
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
assert os.path.isdir(os.path.join(REPO, "docs", "figures")), REPO
t0 = time.time()
tick = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)
ARMS = ("v147", "ablation", "v1492")
NICE = {"v147": "A  classifier ON (v1.47)",
        "ablation": "B  classifier OFF, same candidates",
        "v1492": "C  v1.49.2: 7 radii AND classifier off"}

if not os.path.isdir(_paths.TILE_CACHE) or not os.listdir(_paths.TILE_CACHE):
    TB.build_cache()
tiles = TB.load()
SPECS = sorted({t["specimen"] for t in tiles})
tick(f"{len(tiles)} tiles, {len(SPECS)} specimens")
assert TB.controls(), "tilebench controls failed; every number below would be unreadable"

pred = {a: [] for a in ARMS}
for i, t in enumerate(tiles):
    st = CP.stages(t["img8"])                        # computed once, shared by A and B
    pred["v147"].append(CP.probability(st) >= CP.THR)
    pred["ablation"].append(st["labeled"] > 0)       # same candidates, classifier bypassed
    pred["v1492"].append(A4.shipped_clean(t["img8"]))
    tick(f"predicted {i + 1}/{len(tiles)} {t['frame']}")

cnt = {a: [TB.counts(p, t["gt"]) for p, t in zip(pred[a], tiles)] for a in ARMS}
npx = [int(t["gt"].size) for t in tiles]

# --- GUARD: the arms must still be the arms Section 2 describes -------------------------
_iou = {a: TB._agg(cnt[a])["iou"] for a in ARMS}
_per = {a: {s: TB._agg([c for c, t in zip(cnt[a], tiles) if t["specimen"] == s])
            for s in SPECS} for a in ARMS}
_d = np.array([_per["ablation"][s]["iou"] - _per["v147"][s]["iou"] for s in SPECS])
_med, _better = float(np.median(_d)), int((_d > 0).sum())
_p = float(wilcoxon(_d).pvalue)
print(f"\nGUARD, arm B against the stored record: median dIoU {_med:+.4f} (want +0.1753), "
      f"{_better}/{len(SPECS)} better (want 11), p = {_p:.4f} (want 0.0061)")
assert abs(_med - 0.1753) < 5e-4 and _better == 11 and abs(_p - 0.0061) < 5e-4, (
    "the arms have drifted from what Section 2 reports; fix that before reading anything "
    "below")
print("  arms reproduce. Proceeding.\n")


def bg(rows, sizes):
    """Pooled background-counting measures over a set of tiles."""
    tp = sum(r["tp"] for r in rows); fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows); n = sum(sizes)
    tn = n - tp - fp - fn
    lab, mark = tp + fn, tp + fp
    return {"labelled_pct": 100.0 * lab / n, "marked_pct": 100.0 * mark / n,
            "tp_pct": 100.0 * tp / n, "fp_pct": 100.0 * fp / n,
            "fn_pct": 100.0 * fn / n, "tn_pct": 100.0 * tn / n,
            "accuracy_pct": 100.0 * (tp + tn) / n,
            "empty_mask_accuracy_pct": 100.0 * (n - lab) / n,
            "specificity_pct": 100.0 * tn / max(tn + fp, 1),
            "area_agreement": mark / max(lab, 1)}


POOL = {a: bg(cnt[a], npx) for a in ARMS}
PSPEC = {a: {s: bg([c for c, t in zip(cnt[a], tiles) if t["specimen"] == s],
                   [z for z, t in zip(npx, tiles) if t["specimen"] == s])
             for s in SPECS} for a in ARMS}

print(f"POOLED over {len(tiles)} tiles. Labelled crack "
      f"{POOL['v147']['labelled_pct']:.3f}%, an empty mask scores "
      f"{POOL['v147']['empty_mask_accuracy_pct']:.3f}% accuracy.\n")
print(f"  {'arm':38s} {'marked%':>8s} {'right%':>7s} {'wrong%':>7s} {'accuracy%':>10s} "
      f"{'vs empty':>9s} {'spec%':>7s} {'area':>6s}")
for a in ARMS:
    v = POOL[a]
    m = v["accuracy_pct"] - v["empty_mask_accuracy_pct"]
    print(f"  {NICE[a]:38s} {v['marked_pct']:8.3f} {v['tp_pct']:7.3f} {v['fp_pct']:7.3f} "
          f"{v['accuracy_pct']:9.3f}{'+' if m > 0 else '-'} {m:+9.3f} "
          f"{v['specificity_pct']:7.3f} {v['area_agreement']:6.3f}")

print(f"\nPAIRED against arm A, one pair per specimen, {len(SPECS)} specimens, "
      f"exact Wilcoxon")
OUT = {}
for a in ("ablation", "v1492"):
    row = {}
    for key, label, lower in (("accuracy_pct", "accuracy (pp)", False),
                              ("specificity_pct", "specificity (pp)", False),
                              ("area_err", "|area agreement - 1|", True)):
        if key == "area_err":
            x = np.array([abs(PSPEC[a][s]["area_agreement"] - 1) for s in SPECS])
            y = np.array([abs(PSPEC["v147"][s]["area_agreement"] - 1) for s in SPECS])
        else:
            x = np.array([PSPEC[a][s][key] for s in SPECS])
            y = np.array([PSPEC["v147"][s][key] for s in SPECS])
        d = (y - x) if lower else (x - y)        # positive = the arm is better
        p = 1.0 if np.allclose(x, y) else float(wilcoxon(x, y).pvalue)
        row[label] = {"median_gain": float(np.median(d)),
                      "specimens_better": int((d > 0).sum()),
                      "specimens_worse": int((d < 0).sum()),
                      "n": len(SPECS), "wilcoxon_p": p,
                      "resolved_at_0.05": bool(p < 0.05)}
        print(f"  {NICE[a][:34]:36s} {label:22s} median {d.mean() * 0 + np.median(d):+8.4f}"
              f"  {int((d > 0).sum())}/{len(SPECS)} better  p = {p:.4f}"
              f"  {'RESOLVED' if p < 0.05 else 'not resolved'}")
    OUT[a] = row

# WHY POOLED AND PER-SPECIMEN DISAGREE. The pooled area ratio and the per-specimen median
# move in opposite directions, so the share of labelled crack each specimen carries is
# recorded: a pooled ratio is a weighted mean and two large specimens can own it.
_lab = {s: sum(c["tp"] + c["fn"] for c, t in zip(cnt["v147"], tiles)
               if t["specimen"] == s) for s in SPECS}
_tot = sum(_lab.values())
SHARE = {s: _lab[s] / _tot for s in SPECS}
print("\nshare of all labelled crack, by specimen (the pooled ratio is weighted by this)")
for s in sorted(SPECS, key=lambda k: -SHARE[k])[:5]:
    print(f"  {s:28s} {100 * SHARE[s]:5.1f}%   area agreement "
          f"A {PSPEC['v147'][s]['area_agreement']:.3f} -> "
          f"B {PSPEC['ablation'][s]['area_agreement']:.3f}")

p = os.path.join(REPO, "docs/figures/sem_deadzone_background_units.json")
json.dump({"n_tiles": len(tiles), "n_specimens": len(SPECS), "specimens": SPECS,
           "arms": NICE, "pooled": POOL, "per_specimen": PSPEC, "paired_vs_v147": OUT,
           "guard": {"arm_b_median_delta_iou": _med, "arm_b_better": _better,
                     "arm_b_wilcoxon_p": _p,
                     "note": "asserted against the stored record before anything else was "
                             "computed, so a drift in the arms cannot pass silently"},
           "labelled_share_by_specimen": SHARE,
           "measures": "accuracy with the empty-mask baseline, specificity, and area "
                       "agreement -- all over every pixel of the tile"},
          open(p, "w"), indent=1)
print("\nwrote", p)
