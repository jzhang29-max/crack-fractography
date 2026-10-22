"""Every score this detector has, shown next to the number that makes it mean something.

This project has two kinds of result and they get confused constantly. Some scores count
the background and some do not, and the ones that count the background look excellent for a
reason that has nothing to do with the detector: on an image that is 1.8% crack, 98.2% of
the pixels are background and leaving them alone is free. Some scores on our own corpus look
excellent for the mirror-image reason: 99.1% of the pixels a human actually refereed there
are crack, so marking everything is nearly right.

So this plate draws no score on its own. Every bar carries the baseline a reader needs:

  MARK NOTHING      the score for an empty mask. Anything at or below this line is
                    a number the detector did not earn.
  MARK EVERYTHING   the score for a full mask. The same test from the other side.
  CHANCE            0.5 for balanced accuracy, 0 for MCC.

Where the detector's bar clears its baseline by a wide margin, the result is real and this
plate says so. Where it does not, no amount of presentation will fix it, and a reviewer
will find it in a minute.
"""
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
OUT = os.path.join(REPO, "paper/figures/out/scores_with_baselines.png")
PA = json.load(open(os.path.join(REPO, "docs/figures/pixel_accounting.json")))["sets"]
LC = json.load(open(os.path.join(REPO,
                                 "docs/figures/lab_scoring_positive_control.json")))
W = PA["Inconel 718, whole fields"]["detector"]
M = PA["MetalDAM voids (not cracks)"]["detector"]

plt.rcParams.update({"font.size": 8.5, "font.family": "DejaVu Sans",
                     "axes.linewidth": 0.7})
GOOD, BAD, BASE = "#1a7f4b", "#b3401a", "#555555"

prev = W["labelled_pct"] / 100.0           # crack prevalence on the public whole fields
# what an empty mask and a full mask score, derived from prevalence alone
mark_nothing = {"accuracy": (1 - prev) * 100, "specificity": 100.0,
                "balanced_accuracy": 50.0, "mcc": 0.0, "f1": 0.0, "iou": 0.0,
                "precision": 0.0, "recall": 0.0}
mark_all = {"accuracy": prev * 100, "specificity": 0.0, "balanced_accuracy": 50.0,
            "mcc": 0.0, "precision": prev, "recall": 1.0,
            "f1": 2 * prev / (1 + prev), "iou": prev}

fig, axes = plt.subplots(1, 3, figsize=(11.6, 4.5),
                         gridspec_kw={"width_ratios": [1.15, 1.15, 0.95]})

# ---- panel 1: the scores that COUNT the background -------------------------------------
ax = axes[0]
rows = [("accuracy", W["accuracy"] * 100, mark_nothing["accuracy"], "mark nothing", "%"),
        ("specificity", W["specificity"] * 100, 100.0, "mark nothing", "%"),
        ("balanced\naccuracy", W["balanced_accuracy"] * 100, 50.0, "chance", "%"),
        ("MCC x100", W["mcc"] * 100, 0.0, "chance", "")]
y = np.arange(len(rows))[::-1]
for i, (name, val, base, blabel, unit) in zip(y, rows):
    earned = val > base + 1e-9
    ax.barh(i, val, color=GOOD if earned else BAD, height=0.52, zorder=2)
    ax.plot([base, base], [i - 0.33, i + 0.33], color=BASE, lw=2.2, zorder=4)
    ax.text(val + 1.5, i, f"{val:.1f}{unit}", va="center", fontsize=8.5,
            color=GOOD if earned else BAD, fontweight="bold")
    ax.text(base, i + 0.40, blabel, ha="center", va="bottom", fontsize=6.3, color=BASE)
ax.set_yticks(y, [r[0] for r in rows], fontsize=8.5)
ax.set_xlim(0, 118)
ax.set_title("Scores that COUNT the background\nInconel 718, 31 whole fields",
             fontsize=9.5)
ax.text(0.5, -0.17, "red = at or below a baseline that detects nothing",
        transform=ax.transAxes, ha="center", fontsize=7.5, color=BAD)
ax.spines[["top", "right"]].set_visible(False)

# ---- panel 2: the scores that IGNORE the background ------------------------------------
ax = axes[1]
rows = [("precision", W["precision"], mark_all["precision"]),
        ("recall", W["recall"], None),
        ("F1", W["f1"], mark_all["f1"]),
        ("IoU", W["iou"], mark_all["iou"])]
y = np.arange(len(rows))[::-1]
for i, (name, val, base) in zip(y, rows):
    ax.barh(i, val, color=GOOD, height=0.52, zorder=2)
    ax.text(val + 0.012, i, f"{val:.3f}", va="center", fontsize=8.5, color=GOOD,
            fontweight="bold")
    if base is not None:
        ax.plot([base, base], [i - 0.33, i + 0.33], color=BASE, lw=2.2, zorder=4)
        ax.text(base, i + 0.40, f"mark everything {base:.3f}", ha="left", va="bottom",
                fontsize=6.3, color=BASE)
        ax.text(0.52, i, f"{val / max(base, 1e-9):.0f}x its baseline", va="center",
                fontsize=7.4, color=GOOD, style="italic")
ax.set_yticks(y, [r[0] for r in rows], fontsize=8.5)
ax.set_xlim(0, 0.78)
ax.set_title("Scores that IGNORE the background\nsame images, same masks", fontsize=9.5)
ax.text(0.5, -0.17, "these are earned: 9.8x and 11.9x a mask that marks every pixel",
        transform=ax.transAxes, ha="center", fontsize=7.5, color=GOOD)
ax.spines[["top", "right"]].set_visible(False)

# ---- panel 3: our own corpus, where the high numbers live ------------------------------
ax = axes[2]
pos, neg = LC["refereed_crack_px"], LC["refereed_notcrack_px"]
pr_all = pos / (pos + neg)
f1_all = 2 * pr_all / (1 + pr_all)
det = LC["arms"]["DETECTOR mad_k=1.0 (the 'winner')"]
rows = [("precision", det["precision"], pr_all),
        ("recall", det["recall"], 1.0),
        ("F1", det["f1"], f1_all)]
y = np.arange(len(rows))[::-1]
for i, (name, val, base) in zip(y, rows):
    ax.barh(i, val, color=BAD, height=0.52, zorder=2)
    ax.text(val - 0.02, i, f"{val:.3f}", va="center", ha="right", fontsize=8.5,
            color="white", fontweight="bold")
    ax.plot([base, base], [i - 0.33, i + 0.33], color=BASE, lw=2.2, zorder=4)
    ax.text(base, i + 0.40, f"{base:.3f}", ha="center", va="bottom", fontsize=6.5,
            color=BASE)
ax.set_yticks(y, [r[0] for r in rows], fontsize=8.5)
ax.set_xlim(0, 1.14)
ax.set_title("Our own 18 refereed frames\nthe high numbers, and why", fontsize=9.5)
ax.text(0.5, -0.17,
        f"{100 * pr_all:.1f}% of refereed pixels are crack, so\n"
        f"marking EVERY pixel scores F1 {f1_all:.3f} (grey)",
        transform=ax.transAxes, ha="center", fontsize=7.5, color=BAD)
ax.spines[["top", "right"]].set_visible(False)

fig.suptitle("Every score, next to the number that makes it mean something", fontsize=11.5)
fig.tight_layout(rect=(0, 0.04, 1, 0.95))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT, dpi=200)
print("wrote", OUT)
print(f"\n  accuracy        {W['accuracy']*100:.2f}%  vs mark-nothing {mark_nothing['accuracy']:.2f}%")
print(f"  specificity     {W['specificity']*100:.2f}%  vs mark-nothing 100.00%")
print(f"  balanced acc    {W['balanced_accuracy']*100:.2f}%  vs chance 50.00%")
print(f"  MCC             {W['mcc']:.4f}  vs chance 0")
print(f"  F1              {W['f1']:.4f}  vs mark-everything {mark_all['f1']:.4f}"
      f"  ({W['f1']/mark_all['f1']:.1f}x)")
print(f"  IoU             {W['iou']:.4f}  vs mark-everything {mark_all['iou']:.4f}"
      f"  ({W['iou']/mark_all['iou']:.1f}x)")
print(f"  MetalDAM MCC    {M['mcc']:.4f}   <- the project's best score anywhere")
print(f"  lab corpus F1   {det['f1']:.4f}  vs mark-every-pixel {f1_all:.4f}")
