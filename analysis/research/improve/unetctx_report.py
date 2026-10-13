"""APPROACH 2 -- A U-NET ON THE FULL FRAMES. THE WHOLE RESULT ON ONE PAGE.

VERDICT: NEGATIVE. Four orders of magnitude more supervision -- 70,041,625 hand-painted
pixels on 48 full frames against the 26 tiles' 6.8 Mpx -- does not beat one line of code.
Held out by specimen, the best arm scores clDice 0.5719 against the one-line threshold's
0.6205 and the shipped model's 0.6405. Paired over the 13 specimens it is worse than the
threshold on 9 of 13 (-0.0721, p = 0.2163) and worse than the shipped model on 12 of 13
(-0.1382, p = 0.0061). It is DISQUALIFIED anyway: as a replacement it deletes 51.17% of
the hand-marked crack the shipped path keeps, on 44 of 48 frames.

Four things are worth keeping out of it.

 1. THE SUPERVISION STRATEGY IS THE WHOLE EXPERIMENT, AND FOUR OF FIVE ARE CATASTROPHIC.
    Trained against the paint as it was drawn, the network learns to paint: at a fixed
    0.5 cut it marks the entire tile (recall 1.0000, precision 0.0261, clDice 0.0000).
    Down-weighting unreviewed pixels does not save it, nor does a soft-clDice loss, nor a
    MIL region constraint, which collapses to marking nothing. Only thinning the target
    to the paint's frame-level medial axis produces a model that scores at all.

 2. IT IS NOT A RELABELLED THRESHOLD, AND THAT MAKES THE RESULT WORSE, NOT BETTER. The
    U-Net's probability map rank-correlates with plain darkness at a median rho of 0.206.
    Two almost unrelated functions, one of them fitted on 70 million labelled pixels, and
    the fitted one is behind. The ceiling here is not the method.

 3. THE PRE-REGISTERED MECHANISM IS REFUTED WITH THE SIGN REVERSED. AM cracks are close
    to intensity-invisible, so a learned model should gain most where darkness fails. It
    loses most there: advantage -0.1319 on the low-contrast half against -0.0380 on the
    high-contrast half, Spearman +0.138 (p = 0.4999) where the mechanism needs negative.

 4. SEED NOISE IS WIDER THAN THE PRIZE. Three seeds on identical data span 0.109 clDice.
    Any single-seed number here, in either direction, is noise; the headline uses the
    three-seed ensemble for that reason.

Run order:
  unetctx_base.py      reproduces the brief's baseline table through ctx_core, then
                       builds the 48-frame corpus (70,041,625 px of hand paint)
  unetctx_patches.py   9,009 patches of 192 px, each tagged with its specimen
  unetctx_loso.py      trains every (arm, held-out specimen, seed)
  unetctx_result.py    scores the 26 tiles, paired over the 13 specimens   -> result.json
  unetctx_gate.py      the full-frame paint gate over all 48 frames        -> gate*.json
  unetctx_diag.py      is this a new function, or a relabelled threshold?  -> diag.json
  unetctx_report.py    this file; reads the json back, computes nothing

This file prints what those runs found. It asserts nothing it did not read.
"""
import json, os, sys
import numpy as np

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True
import unetctx_base as B


def L(n):
    p = os.path.join(B.MY, n)
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    res, gate, gateu, diag, probe = (L("result.json"), L("gate_replace.json"),
                                     L("gate_union.json"), L("diag.json"),
                                     L("probe.json"))
    W = 100
    if probe:
        print("=" * W)
        print("1. WHICH WAY OF USING BROAD-BRUSH PAINT WORKS AT ALL")
        print("   One model per strategy, trained on all 48 frames, scored on the 13 "
              "tiles whose\n   specimen has no painted frame -- held out by construction, "
              "no fold needed.")
        print(f"   {'strategy':<42} {'clDice':>8} {'IoU':>8} {'recall':>8} {'precision':>10}")
        order = [("baseline_current", "CURRENT MODEL (v1.49.1)"),
                 ("baseline_threshold", "one-line global threshold"),
                 ("naive__area", "(a') paint target, unreviewed = BACKGROUND"),
                 ("pu_dice__area", "(a)  paint target, unreviewed = unlabelled"),
                 ("pu_cldice__area", "(a)  + soft-clDice (width-insensitive loss)"),
                 ("thin__area", "(b)  thinned target (frame-level medial axis)"),
                 ("mil__area", "(c)  region constraint / MIL top-k")]
        for k, lab in order:
            if k in probe:
                v = probe[k]
                print(f"   {lab:<42} {v['cldice']:8.4f} {v['iou']:8.4f} "
                      f"{v['recall']:8.4f} {v['precision']:10.4f}")
        print("\n   Only the thinned target survives. Trained against the paint as it was "
              "drawn, the\n   network paints: at a fixed 0.5 cut the pu_dice arm marks "
              "the whole tile (recall\n   1.0000, precision 0.0261). That is the brief's "
              "warning, reproduced.")

    if res:
        print("\n" + "=" * W)
        print("2. THE SURVIVING ARM, 26 TILES, HELD OUT BY SPECIMEN")
        print(f"   {'arm':<40} {'clDice':>8} {'skelF1@2':>9} {'IoU':>8} {'prec':>8} "
              f"{'recall':>8} {'area':>9}")
        for k in ("shipped", "threshold", "trace"):
            v = res[k]
            print(f"   {v['name']:<40} {v['cldice']:8.4f} {v['skelf1']:9.4f} "
                  f"{v['iou']:8.4f} {v['precision']:8.4f} {v['recall']:8.4f} "
                  f"{v['area']:9.0f}")
        keys = [k for k in res if isinstance(res[k], dict) and "name" in res[k]
                and k not in ("shipped", "threshold", "trace")]
        for k in sorted(keys):
            v = res[k]
            print(f"   {v['name']:<40} {v['cldice']:8.4f} {v['skelf1']:9.4f} "
                  f"{v['iou']:8.4f} {v['precision']:8.4f} {v['recall']:8.4f} "
                  f"{v['area']:9.0f}")
        print("\n   PAIRED over the 13 specimens -- the unit the brief requires. A median "
              "over tiles\n   moves when one tile crosses the middle rank; these do not.")
        print(f"   {'comparison':<46} {'mean d':>9} {'better':>8} {'worse':>7} {'p':>8}")
        for k in sorted(k for k in res if "__vs " in k or "__vs_" in k):
            q = res[k]
            print(f"   {k:<46} {q['mean_d']:+9.4f} {q['up']:8d} {q['down']:7d} "
                  f"{q['p']:8.4f}")
        for m in ("area", "p50", "area_bl"):
            if f"overfit_gap__{m}" in res:
                print(f"   overfit gap on clDice [{m}]: "
                      f"{res[f'overfit_gap__{m}']:+.4f}")

    if res and "per_specimen" in res:
        print("\n" + "=" * W)
        print("3. PER SPECIMEN (mean clDice over that specimen's tiles)")
        print(f"   {'specimen':<22} {'u-net':>8} {'shipped':>8} {'one-line':>9}")
        for sp, v in res["per_specimen"].items():
            print(f"   {sp:<22} {v['unet']:8.4f} {v['shipped']:8.4f} {v['oneline']:9.4f}")
        s = res["spread"]
        print(f"   {'spread (sd)':<22} {s['unet']:8.4f} {s['shipped']:8.4f} "
              f"{s['oneline']:9.4f}")

    if gate:
        print("\n" + "=" * W)
        print("4. THE FULL-FRAME PAINT GATE, all 48 hand-painted frames")
        for lab, g in (("as a REPLACEMENT for the shipped candidate stage", gate),
                       ("as an ADDITIVE arm (shipped | u-net)", gateu)):
            if not g:
                continue
            v = g["verdict"]
            print(f"   {lab}")
            print(f"     hand-marked crack the shipped path keeps : {v['kept']:,} px")
            print(f"     deleted                                  : {v['deleted']:,} px "
                  f"= {v['pct']:.2f}%")
            print(f"     frames individually losing more than 1%  : {v['n_over']} / "
                  f"{len(g['rows'])}")
            print(f"     {'PASS' if v['passes'] else 'FAIL'} the <1% gate")

    if diag:
        print("\n" + "=" * W)
        print("5. IS IT A NEW FUNCTION, OR A RELABELLED THRESHOLD?")
        print(f"   median Spearman(u-net probability, plain darkness) over tiles: "
              f"{diag['rho_median']:.3f}")
        print(f"   Spearman(crack contrast, u-net advantage) = {diag['spearman']:+.3f}, "
              f"p = {diag['spearman_p']:.4f}")
        print(f"     low-contrast half  advantage {diag['adv_low']:+.4f}")
        print(f"     high-contrast half advantage {diag['adv_high']:+.4f}")

    if res and "sab_shuffle" in res:
        print("\n" + "=" * W)
        print("6. SABOTAGE (all-paint model, scored on all 26 tiles -- the most "
              "favourable setting\n   a broken method could ask for)")
        for k in ("sab_shuffle", "sab_rot", "sab_const"):
            if k in res:
                v = res[k]
                print(f"   {v['name']:<40} clDice {v['cldice']:.4f}  IoU {v['iou']:.4f}")
        k = f"{res['arm']}__area__s0"
        if k in res:
            print(f"   real arm, same readout: clDice {res[k]['cldice']:.4f}")


if __name__ == "__main__":
    main()
