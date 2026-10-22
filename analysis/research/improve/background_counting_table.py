"""The detector scored only in measures that count the background.

This paper reports a crack area fraction. Precision, recall, F1 and IoU all throw away the
true negatives, which on a 1.8%-crack micrograph is 98% of the evidence and the larger part
of what a reader is being told. So this table drops them and keeps only quantities computed
over every pixel in the frame:

  the pixel budget   labelled%, marked%, and the frame split four ways -- right-and-marked,
                     wrong-and-marked, missed, and correctly left alone -- each as a
                     percentage of the whole image.
  accuracy           the share of all pixels decided correctly.
  specificity        the share of background correctly left alone.
  area agreement     marked% against labelled%, the quantity the tool actually outputs.

One baseline is carried with them and cannot be dropped: an EMPTY MASK scores accuracy
(100 - labelled)% and specificity 100%, because leaving the background alone is free. Any
accuracy below that line is a number an empty file would beat, so the line is printed in
the same row. Algebraically accuracy clears it only where precision exceeds 0.5, which is
the honest short form of the whole problem.

Everything is computed PER IMAGE and then averaged. Deriving a budget from mean precision
and mean recall gives a different and wrong answer, because a mean of ratios is not the
ratio of means.
"""
import json
import os
import sys

import numpy as np

REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
MK = json.load(open(os.path.join(REPO, "docs/figures/madk_above_five.json")))["sets"]
PA = json.load(open(os.path.join(REPO, "docs/figures/pixel_accounting.json")))["sets"]


def budget_from(marked, labelled, precision):
    """Per-image four-way split of the frame, as percentages of the whole image."""
    marked, labelled = np.asarray(marked), np.asarray(labelled)
    tp = marked * np.asarray(precision)
    fp = marked - tp
    fn = labelled - tp
    tn = 100.0 - tp - fp - fn
    return tp, fp, fn, tn


def rows_for(setname, d):
    pi = d["per_image"]
    out = []
    for k in sorted(pi, key=float):
        v = pi[k]
        tp, fp, fn, tn = budget_from(v["marked_pct"], v["labelled_pct"], v["precision"])
        acc = tp + tn
        spec = tn / np.maximum(tn + fp, 1e-12) * 100.0
        lab = np.asarray(v["labelled_pct"])
        empty_acc = 100.0 - lab
        out.append({
            "mad_k": float(k),
            "labelled_pct": float(lab.mean()),
            "marked_pct": float(np.mean(v["marked_pct"])),
            "tp_pct": float(tp.mean()), "fp_pct": float(fp.mean()),
            "fn_pct": float(fn.mean()), "tn_pct": float(tn.mean()),
            "accuracy_pct": float(acc.mean()),
            "empty_mask_accuracy_pct": float(empty_acc.mean()),
            "beats_empty_mask": bool(acc.mean() > empty_acc.mean()),
            "accuracy_margin_pp": float(acc.mean() - empty_acc.mean()),
            "specificity_pct": float(spec.mean()),
            # corpus-level agreement: the total crack area fraction a reader would quote
            "area_agreement_corpus": float(np.sum(v["marked_pct"]) / np.sum(lab)),
            "area_agreement_per_image": float(np.mean(
                np.asarray(v["marked_pct"]) / np.maximum(lab, 1e-12))),
        })
    return out


ALL = {}
for setname, d in MK.items():
    ALL[setname] = rows_for(setname, d)
    print(f"\n{'=' * 112}\n{setname}\n{'=' * 112}")
    print(f"  {'mad_k':>6s} {'marked%':>8s} {'right%':>7s} {'wrong%':>7s} {'missed%':>8s} "
          f"{'left alone%':>12s} {'accuracy%':>10s} {'empty mask':>11s} {'spec%':>7s} "
          f"{'area':>6s}")
    for r in ALL[setname]:
        flag = "  <-- SHIPPED" if r["mad_k"] == 5.0 else ""
        mark = "+" if r["beats_empty_mask"] else "-"
        print(f"  {r['mad_k']:6.1f} {r['marked_pct']:8.3f} {r['tp_pct']:7.3f} "
              f"{r['fp_pct']:7.3f} {r['fn_pct']:8.3f} {r['tn_pct']:12.3f} "
              f"{r['accuracy_pct']:9.3f}{mark} {r['empty_mask_accuracy_pct']:11.3f} "
              f"{r['specificity_pct']:7.3f} {r['area_agreement_corpus']:6.3f}{flag}")

    best_acc = max(ALL[setname], key=lambda r: r["accuracy_pct"])
    best_area = min(ALL[setname], key=lambda r: abs(r["area_agreement_corpus"] - 1.0))
    print(f"\n  best accuracy      : {best_acc['accuracy_pct']:.3f}% at mad_k "
          f"{best_acc['mad_k']:g}  (an empty mask scores "
          f"{best_acc['empty_mask_accuracy_pct']:.3f}%, margin "
          f"{best_acc['accuracy_margin_pp']:+.3f} pp)")
    print(f"  best area agreement: {best_area['area_agreement_corpus']:.4f}x the labelled "
          f"area fraction at mad_k {best_area['mad_k']:g} "
          f"({best_area['marked_pct']:.3f}% marked against "
          f"{best_area['labelled_pct']:.3f}% labelled)")

# the other sets, at their shipped operating point only
print(f"\n{'=' * 112}\nTHE OTHER SETS, shipped operating point\n{'=' * 112}")
print(f"  {'set':34s} {'marked%':>8s} {'accuracy%':>10s} {'empty mask':>11s} "
       f"{'spec%':>7s} {'area':>7s}")
OTHER = {}
for k, v in PA.items():
    t = v["detector"]
    empty = 100.0 - t["labelled_pct"]
    acc = 100.0 * t["accuracy"]
    OTHER[k] = {"marked_pct": t["marked_pct"], "labelled_pct": t["labelled_pct"],
                "tp_pct": t["tp_pct"], "fp_pct": t["fp_pct"], "fn_pct": t["fn_pct"],
                "tn_pct": t["tn_pct"], "accuracy_pct": acc,
                "empty_mask_accuracy_pct": empty,
                "accuracy_margin_pp": acc - empty, "beats_empty_mask": bool(acc > empty),
                "specificity_pct": 100.0 * t["specificity"],
                "area_agreement_corpus": t["marked_pct"] / t["labelled_pct"]}
    mark = "+" if acc > empty else "-"
    print(f"  {k:34s} {t['marked_pct']:8.3f} {acc:9.3f}{mark} {empty:11.3f} "
          f"{100 * t['specificity']:7.3f} {t['marked_pct'] / t['labelled_pct']:7.3f}")

print(f"\n{'=' * 112}\nBEST BACKGROUND-COUNTING NUMBERS ANYWHERE IN THIS PROJECT\n{'=' * 112}")
cands = [(k, v) for k, v in OTHER.items()] + \
        [(f"Inconel 718 whole fields, mad_k {r['mad_k']:g}", r)
         for r in ALL["whole_fields"]] + \
        [(f"Inconel 718 released crops, mad_k {r['mad_k']:g}", r) for r in ALL["crops"]]
for label, key, fmt in (("highest accuracy", "accuracy_pct", "{:.3f}%"),
                        ("highest specificity", "specificity_pct", "{:.3f}%")):
    w = max(cands, key=lambda kv: kv[1][key])
    print(f"  {label:22s} {fmt.format(w[1][key]):>10s}  on {w[0]}"
          f"   (empty mask {w[1]['empty_mask_accuracy_pct']:.3f}%, margin "
          f"{w[1]['accuracy_margin_pp']:+.3f} pp)")
w = min(cands, key=lambda kv: abs(kv[1]["area_agreement_corpus"] - 1.0))
print(f"  {'closest area fraction':22s} {w[1]['area_agreement_corpus']:10.4f}x  on {w[0]}"
      f"   ({w[1]['marked_pct']:.3f}% marked vs {w[1]['labelled_pct']:.3f}% labelled)")
earned = [c for c in cands if c[1]["beats_empty_mask"]]
print(f"\n  {len(earned)} of {len(cands)} operating points have an accuracy an empty mask "
      f"does not beat.")
for label, v in sorted(earned, key=lambda kv: -kv[1]["accuracy_margin_pp"])[:6]:
    print(f"    {v['accuracy_margin_pp']:+.3f} pp  {label}")

p = os.path.join(REPO, "docs/figures/background_counting_table.json")
json.dump({"sweeps": ALL, "other_sets": OTHER,
           "measures": "pixel budget, accuracy, specificity, area agreement -- all "
                       "computed over every pixel in the frame",
           "excluded": "precision, recall, F1 and IoU discard the true negatives; "
                       "balanced accuracy and MCC excluded at the author's direction",
           "baseline": "an empty mask scores accuracy (100 - labelled)% and specificity "
                       "100%; accuracy clears it only where precision exceeds 0.5"},
          open(p, "w"), indent=1)
print("\nwrote", p)
