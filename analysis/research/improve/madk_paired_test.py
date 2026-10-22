"""Is mad_k = 6.0 actually better than 5.0, or is the gap inside the noise?

The extended sweep puts the optimum at 6.0 on both framings: whole fields F1 0.3444 -> 0.3564,
released crops 0.4958 -> 0.4992. The paper elsewhere calls a 0.0186 F1 gap irresolvable at
this sample size and tells its own readers not to rank inside one, so quoting +0.0120 as an
improvement without a paired test would break the paper's own rule in the paper's own voice.

This runs the test the rule asks for: per-image paired differences, an exact Wilcoxon
signed-rank p, and the count of images favouring each value, for the neighbours 4.0, 6.0 and
7.0 against the shipped 5.0.

It is run on two quantities, because they are not the same question and the answer differs:

  F1                  what the benchmark rewards.
  |area error|        how far the reported crack area fraction sits from the labelled one, in
                      percentage points. This is the number the tool puts in front of a
                      reader, and the sweep moves it from 1.65x the labelled value at k=5.0
                      to 1.06x at k=7.0 on whole fields.

A change unresolvable on F1 and decisive on area error is still worth making -- but only if
it is reported as what it is, so both are tested rather than whichever one wins.
"""
import json
import os

import numpy as np
from scipy import stats

REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
S = json.load(open(os.path.join(REPO, "docs/figures/madk_above_five.json")))["sets"]
SHIP, NB = "5.0", ("4.0", "6.0", "7.0")
OUT = {}

for setname, d in S.items():
    pi = d["per_image"]
    n = len(pi[SHIP]["f1"])
    lab = np.array(pi[SHIP]["labelled_pct"])
    print(f"\n{'=' * 78}\n{setname}: n = {n} images\n{'=' * 78}")
    OUT[setname] = {"n": n}

    def area_err(k):
        return np.abs(np.array(pi[k]["marked_pct"]) - lab)

    for metric, get, better_is in (("F1", lambda k: np.array(pi[k]["f1"]), "higher"),
                                   ("|area error| pp", area_err, "lower")):
        base = get(SHIP)
        print(f"\n  {metric}  (shipped k=5.0 mean {base.mean():.4f})")
        for k in NB:
            v = get(k)
            diff = (v - base) if better_is == "higher" else (base - v)   # positive = k wins
            wins = int((diff > 0).sum()); losses = int((diff < 0).sum())
            if np.allclose(diff, 0):
                p = 1.0
            else:
                p = float(stats.wilcoxon(v, base, zero_method="wilcox").pvalue)
            verdict = ("RESOLVED" if p < 0.05 else "not resolved")
            print(f"    k={k:>4}  mean {v.mean():.4f}  paired median {np.median(diff):+.4f}  "
                  f"{wins}/{n} images favour it  p = {p:.4f}  {verdict}")
            OUT[setname].setdefault(metric, {})[k] = {
                "mean": float(v.mean()), "paired_median_gain": float(np.median(diff)),
                "images_favouring": wins, "images_against": losses,
                "wilcoxon_p": p, "resolved_at_0.05": bool(p < 0.05)}

print(f"\n{'=' * 78}\nREADING")
wf = OUT["whole_fields"]
f1_6 = wf["F1"]["6.0"]
ae_6, ae_7 = wf["|area error| pp"]["6.0"], wf["|area error| pp"]["7.0"]
print(f"  whole fields, F1 at k=6 vs k=5 : p = {f1_6['wilcoxon_p']:.4f} -> "
      f"{'a real gain' if f1_6['resolved_at_0.05'] else 'NOT resolvable at n=31'}")
print(f"  whole fields, area error k=6   : p = {ae_6['wilcoxon_p']:.4f} -> "
      f"{'a real gain' if ae_6['resolved_at_0.05'] else 'not resolvable'}")
print(f"  whole fields, area error k=7   : p = {ae_7['wilcoxon_p']:.4f} -> "
      f"{'a real gain' if ae_7['resolved_at_0.05'] else 'not resolvable'}")

p = os.path.join(REPO, "docs/figures/madk_paired_test.json")
json.dump({"shipped": SHIP, "neighbours": list(NB), "tests": OUT,
           "test": "exact Wilcoxon signed-rank on per-image paired differences",
           "why_two_metrics": "F1 is what the benchmark rewards; the absolute area-fraction "
                              "error in percentage points is what the tool reports to a "
                              "reader, and the two do not have to agree"},
          open(p, "w"), indent=1)
print("\nwrote", p)
