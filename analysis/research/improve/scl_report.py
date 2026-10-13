"""One table for the whole experiment: reference arms, every loss, both deliverables,
the paired tests over the 13 specimens, the overfit gaps and the sabotage runs.

Reads the json written by scl_score.py and scl_gate.py. Computes nothing new except the
head-to-head tests, so this file cannot disagree with the ones that measured.

    python -B scl_report.py --score score_main.json --sabotage score_sab.json
"""
import os, sys, json, argparse
import numpy as np

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True
import scl_cldice as C   # noqa: E402

OUT = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/scl")


def row(lab, m, extra=""):
    print(f"  {lab:<34}{m['precision']:8.4f}{m['recall']:8.4f}{m['f1']:8.4f}"
          f"{m['iou']:8.4f}{m['cldice']:9.4f}{m['cldice_mean']:9.4f}"
          f"{m['cldice_pooled']:10.4f}  {extra}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", default="score_main.json")
    ap.add_argument("--sabotage", default="")
    ap.add_argument("--gates", default="")
    a = ap.parse_args()
    S = json.load(open(os.path.join(OUT, a.score)))

    print("=" * 118)
    print("HELD-OUT (leave-one-SPECIMEN-out, 13 folds; threshold chosen on the other "
          "specimens' held-out predictions)")
    print(f"  {'arm':<34}{'prec':>8}{'recall':>8}{'F1':>8}{'IoU':>8}{'clDice':>9}"
          f"{'(mean)':>9}{'(pooled)':>10}")
    for k, v in S["reference"].items():
        row(k, v)
    keys = [k for k in S if "|" in k]
    for k in keys:
        row(k, S[k]["heldout"], f"gap {S[k]['gap']:+.4f}")

    print("\nPAIRED OVER THE 13 SPECIMENS (clDice, median within specimen)")
    print(f"  {'arm':<34}{'vs':<28}{'median d':>10}{'up':>4}{'dn':>4}"
          f"{'wilcoxon':>10}{'sign':>8}")
    for k in keys:
        for ref in S["reference"]:
            p = S[k].get(f"paired_vs::{ref}")
            if p:
                print(f"  {k:<34}{ref:<28}{p['median_delta']:+10.4f}{p['improved']:4d}"
                      f"{p['regressed']:4d}{p['wilcoxon_p']:10.4f}{p['sign_p']:8.4f}")

    print("\nOVERFIT GAP (train-on-all minus held-out, clDice)")
    for k in keys:
        print(f"  {k:<34}held-out {S[k]['heldout']['cldice']:.4f}   "
              f"train-on-all {S[k]['train_on_all']['cldice']:.4f}   "
              f"gap {S[k]['gap']:+.4f}")

    print("\nPER-SPECIMEN clDice")
    specs = sorted(S["per_spec_ref"]["CURRENT MODEL (v1.49.1)"])
    hdr = ["CURRENT", "1-LINE"] + [k.split("|")[0][:7] + "/" + k.split("|")[1][:3] for k in keys]
    print(f"  {'specimen':<24}" + "".join(f"{h:>12}" for h in hdr))
    cols = [S["per_spec_ref"]["CURRENT MODEL (v1.49.1)"],
            S["per_spec_ref"]["one-line global threshold"]] + [S[k]["per_spec"] for k in keys]
    for sp in specs:
        print(f"  {sp:<24}" + "".join(f"{c[sp]:12.4f}" for c in cols))

    if a.sabotage:
        B = json.load(open(os.path.join(OUT, a.sabotage)))
        print("\nSABOTAGE -- a broken version must collapse, or the number is not coming "
              "from the method")
        print(f"  {'arm':<34}{'prec':>8}{'recall':>8}{'F1':>8}{'IoU':>8}{'clDice':>9}"
              f"{'(mean)':>9}{'(pooled)':>10}")
        for k, v in B["reference"].items():
            row(k, v)
        for k in [k for k in B if "|" in k]:
            row(k, B[k]["heldout"])

    if a.gates:
        print("\nFULL-FRAME PAINT GATE (48 hand-painted frames, 70,041,625 painted crack px)")
        for g in a.gates.split(","):
            rows = json.load(open(os.path.join(OUT, g)))
            ok = [r for r in rows if "error" not in r]
            K = sum(r["kept"] for r in ok)
            for arm in ("standalone", "additive"):
                Dl = sum(r["del_" + arm] for r in ok)
                bad = [r for r in ok if r["del_" + arm] > 0.01 * max(r["kept"], 1)]
                print(f"  {g:<28} {arm:<11} deletes {100*Dl/max(K,1):7.4f}% of kept "
                      f"hand-marked crack   frames >1%: {len(bad)}/{len(ok)}   "
                      f"{'PASS' if 100*Dl/max(K,1) < 1.0 and not bad else 'FAIL'}")


if __name__ == "__main__":
    main()
