"""The classical-arm comparison, re-expressed in measures that count the background.

The baseline table ranked eight arms by F1, which discards every pixel correctly left
alone. On a 1.8%-crack field that is 98% of the frame and the larger part of what the
detector is being asked to get right. Re-ranked here by the two quantities that do count it:

  accuracy        the share of ALL pixels decided correctly, with the score an empty mask
                  would get printed beside it, because leaving the background alone is free
                  and an accuracy below that line was not earned.
  area agreement  marked% divided by labelled%, pooled over the set -- the crack area
                  fraction a reader of this tool would quote, against the one the annotator
                  marked. 1.000 is exact.

Both are linear in the four cells of the per-image budget, so they are computed from the
stored tp%/fp%/marked%/labelled% means exactly, with no mean-of-ratios error.
"""
import json
import os

import numpy as np

REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
A = json.load(open(os.path.join(REPO, "docs/figures/arms_pixel_budget.json")))["sets"]
OUT = {}

for setname, arms in A.items():
    lab = arms["DETECTOR (shipped)"]["sel_by_f1"]["labelled_pct"]
    empty = 100.0 - lab
    print(f"\n{'=' * 104}\n{setname}: labelled crack {lab:.3f}%, "
          f"an empty mask scores accuracy {empty:.3f}%\n{'=' * 104}")
    rows = {}
    for nm, r in arms.items():
        best = None
        for sel in ("sel_by_f1", "sel_by_area"):
            v = r[sel]
            fn = v["labelled_pct"] - v["tp_pct"]
            tn = 100.0 - v["tp_pct"] - v["fp_pct"] - fn
            acc = v["tp_pct"] + tn
            spec = 100.0 * tn / max(tn + v["fp_pct"], 1e-12)
            cand = {"tuned_by": sel, "marked_pct": v["marked_pct"],
                    "tp_pct": v["tp_pct"], "fp_pct": v["fp_pct"], "fn_pct": fn,
                    "tn_pct": tn, "accuracy_pct": acc, "specificity_pct": spec,
                    "area_agreement": v["marked_pct"] / max(v["labelled_pct"], 1e-12),
                    "free_params": r["free_params"]}
            # keep whichever tuning gives this arm its best ACCURACY: every arm is shown
            # at its own best, so the comparison cannot be accused of handicapping one
            if best is None or cand["accuracy_pct"] > best["accuracy_pct"]:
                best = cand
        best["beats_empty_mask"] = bool(best["accuracy_pct"] > empty)
        best["accuracy_margin_pp"] = best["accuracy_pct"] - empty
        rows[nm] = best
    OUT[setname] = {"labelled_pct": lab, "empty_mask_accuracy_pct": empty, "arms": rows}

    print(f"  {'arm':32s} {'pp':>3s} {'marked%':>8s} {'right%':>7s} {'wrong%':>7s} "
          f"{'left alone%':>12s} {'accuracy%':>10s} {'vs empty':>9s} {'spec%':>7s} "
          f"{'area':>6s}")
    for nm, v in sorted(rows.items(), key=lambda kv: -kv[1]["accuracy_pct"]):
        mark = "+" if v["beats_empty_mask"] else "-"
        print(f"  {nm:32s} {v['free_params']:3d} {v['marked_pct']:8.3f} {v['tp_pct']:7.3f} "
              f"{v['fp_pct']:7.3f} {v['tn_pct']:12.3f} {v['accuracy_pct']:9.3f}{mark} "
              f"{v['accuracy_margin_pp']:+9.3f} {v['specificity_pct']:7.3f} "
              f"{v['area_agreement']:6.3f}")

    ba = min(rows.items(), key=lambda kv: abs(kv[1]["area_agreement"] - 1.0))
    aa = max(rows.items(), key=lambda kv: kv[1]["accuracy_pct"])
    print(f"\n  closest area fraction : {ba[0]} at {ba[1]['area_agreement']:.3f}x")
    print(f"  highest accuracy      : {aa[0]} at {aa[1]['accuracy_pct']:.3f}% "
          f"({aa[1]['accuracy_margin_pp']:+.3f} pp vs an empty mask)")

p = os.path.join(REPO, "docs/figures/arms_background_units.json")
json.dump({"sets": OUT,
           "ranking_measures": "accuracy and area agreement, both computed over every "
                               "pixel; each arm shown at whichever of its two tunings "
                               "gives it the higher accuracy",
           "baseline": "an empty mask scores accuracy (100 - labelled)%"},
          open(p, "w"), indent=1)
print("\nwrote", p)
