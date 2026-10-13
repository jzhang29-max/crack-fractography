"""APPROACH 3 -- CONTEXT WITHOUT DEEP LEARNING. THE WHOLE RESULT ON ONE PAGE.

VERDICT ON THE METHOD: NEGATIVE, and convicted by its own control rather than by a
missing parameter. Three independent context formulations were built and every one lost
to an isotropic dilation given exactly the same number of pixels on exactly the same
tile:

    geodesic growth over a darkness/ridge cost field   ctx_matched.py
    minimum-cost gap bridging between fragments        ctx_bridge.py   (0 of 27 cells won)
    orientation-coherent growth (tensor-voting-lite)   ctx_orient.py

ctx_lambda.py made the control a MEMBER of the method's own family -- cost = lam*1 +
(1-lam)*context_cost, so lam=1 is the constant field whose geodesic ball is exactly the
Euclidean dilation -- and clDice rose monotonically in lam at every added area. Leave-
one-specimen-out then picked lam=1, no context at all, in 13 folds of 13.

The sabotage says it outright: the context arm run on a CONSTANT INPUT IMAGE scores
clDice 0.7590 against the real method's 0.7025. Feeding the method a blank image makes
it better. (The label sabotages behave: shuffled 0.0215, rotated 0.0116.)

WHAT THE ANGLE DID FIND, and it survives every test applied to it:

  1. clDice ON THESE LABELS IS REACHED BY WIDTH. One line -- dilate until the mask has
     1.5x the area -- moves clDice +0.0478 on 13 specimens of 13, p=0.0002, from the
     shipped mask, and +0.0413 on 12 specimens of 13 with none worse, p=0.0005, from
     the one-line threshold. It adds no information whatsoever. The brief's premise that clDice "ignores how thickly
     it was drawn" holds for its tprec half and fails for its tsens half, which asks
     whether the LABEL's medial axis was covered. The label's median width at its own
     centreline is 8.7 px on these tiles, so a prediction a few px off that axis reaches
     it by getting fatter and by nothing else.

  2. SKELETON-F1 AT A TOLERANCE DOES NOT HAVE THE FAULT. Same masks, same tiles: the
     same dilation moves it +0.0015 (p=0.68) and +0.0028 (p=0.20). Floors are right --
     oracle 1.0000, a correct 3 px trace 1.0000, mark-everything 0.0000, random
     area-matched 0.0488 -- and the adversarial controls hold too (ctx_gamecheck.py): a
     lattice of single pixels spaced inside the tolerance, which has recall 1 by
     construction, scores 0.0199 at tau=2. USE tau=2, the tolerance tilebench already
     uses: a tolerance forgives gaps up to about 2*tau, so at tau=5 a DASHED correct
     trace scores a perfect 1.0000 while at tau=2 it is held to 0.8501. At tau=2 the
     shipped model reads 0.5507 and the one-line threshold 0.4492.

  3. THE PIPELINE DOES NOT TIE THE ONE-LINE THRESHOLD. The brief's 0.0012 IoU is pooled
     over 26 tiles, where one flooded tile owns 80% of all false positives. Paired over
     the 13 specimens -- the unit the brief itself requires of a claim -- the shipped
     model beats the threshold on every instrument: IoU +0.0539 on 11 of 13 (p=0.0105),
     clDice +0.0661 on 10 of 13 (p=0.0327), skelF1@5 +0.0818 on 10 of 13 (p=0.0215).

  4. The context arm is strictly additive (mask = shipped | added), so the full-frame
     paint gate reads 0 deleted px on all 48 frames, 0 frames over 1% -- asserted, not
     argued, by ctx_gate.py, whose kept-crack denominator comes out at 20,903,694 px,
     the same figure angle3_paint_gate.py and fullframe_lever4_safety.py reach by two
     other implementations. What it ADDS on frames is no purer than what a blind ring
     adds: 0.9981 against 0.9981, identical to four decimals. (That purity is against
     the biased reviewed denominator angle3 already flagged -- hand-marked not-crack is
     0.61% of the reviewed pool -- so it is a tie, not a quality score.)

Run order: ctx_core (reproduces the brief's table) -> ctx_matched -> ctx_lambda ->
ctx_bridge -> ctx_orient -> ctx_union -> ctx_final -> ctx_metric -> ctx_skelf1 ->
ctx_nullclaim -> ctx_tiecheck -> ctx_gate. This file just reads their json back.
"""
import json, os, sys
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C


def L(n):
    p = os.path.join(C.MY, n)
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    fin, nc, tc, sk, gate = L("final.json"), L("nullclaim.json"), L("tiecheck.json"), \
        L("skelf1.json"), L("gate.json")

    if fin:
        print("=" * 96)
        print("1. THE METHOD, PRIMARY METRIC (clDice), LEAVE-ONE-SPECIMEN-OUT over 13 specimens")
        print(f"   {'arm':<34} {'clDice':>8} {'IoU':>8} {'prec':>8} {'recall':>8} {'gap':>8}")
        print(f"   {'shipped v1.49.1':<34} {fin['base'] and C.pooled(fin['base'])['cldice']:8.4f} "
              f"{C.pooled(fin['base'])['iou']:8.4f} {C.pooled(fin['base'])['precision']:8.4f} "
              f"{C.pooled(fin['base'])['recall']:8.4f} {0.0:8.4f}")
        print(f"   {'one-line global threshold':<34} {C.pooled(fin['thr'])['cldice']:8.4f} "
              f"{C.pooled(fin['thr'])['iou']:8.4f} {C.pooled(fin['thr'])['precision']:8.4f} "
              f"{C.pooled(fin['thr'])['recall']:8.4f} {0.0:8.4f}")
        for k, lab in (("ctx", "CONTEXT geodesic (held-out)"),
                       ("null", "NULL dilation, reads nothing")):
            h = fin[k]["heldout"]
            print(f"   {lab:<34} {h['cldice']:8.4f} {h['iou']:8.4f} {h['precision']:8.4f} "
                  f"{h['recall']:8.4f} {fin[k]['gap']:+8.4f}")
        print("\n   SABOTAGE of the context arm:")
        for k, v in fin["sab"].items():
            print(f"     {k:<24} clDice {v['cldice']:.4f}")
        print("\n   PAIRED over the 13 specimens (clDice):")
        for p in fin["pairs"]:
            print(f"     {p['a']:<24} vs {p['b']:<24} {p['mean_delta']:+8.4f}  "
                  f"{p['up']:>2}up/{p['down']:>2}dn  p={p['p']:.4f}")

    if nc:
        print("\n" + "=" * 96)
        print("2. THE INSTRUMENT. One line of dilation, no information, paired over 13 specimens")
        print(f"   {'seed':<22} {'alpha':>6} {'d clDice':>9} {'p':>8} | {'d skelF1@5':>11} {'p':>8}")
        for r in nc:
            print(f"   {r['seed']:<22} {r['alpha']:6.2f} {r['d_cldice']:+9.4f} "
                  f"{r['p_cldice']:8.4f} | {r['d_skelf1']:+11.4f} {r['p_skelf1']:8.4f}")

    if sk:
        print("\n" + "=" * 96)
        print(f"   floors for skelF1@{sk['tau']} (the instrument is unreadable without them):")
        for k, v in sk["floors"].items():
            print(f"     {k:<24} {v['cldice']:.4f}")

    if tc:
        print("\n" + "=" * 96)
        print("3. SHIPPED vs ONE-LINE THRESHOLD, paired over 13 specimens (the brief says they tie)")
        print(f"   {'instrument':<14} {'shipped':>9} {'one-line':>9} {'paired d':>9} "
              f"{'up':>4} {'dn':>4} {'p':>8}")
        for r in tc:
            print(f"   {r['instrument']:<14} {r['shipped']:9.4f} {r['threshold']:9.4f} "
                  f"{r['paired']:+9.4f} {r['up']:4d} {r['down']:4d} {r['p']:8.4f}")

    if gate:
        good = [r for r in gate if "arms" in r]
        kt = sum(r["shipped_kept"] for r in good)
        print("\n" + "=" * 96)
        print(f"4. FULL-FRAME PAINT GATE -- {len(good)} frames, {kt:,} hand-painted crack px "
              f"kept by the shipped path")
        print(f"   {'arm':<14} {'DELETED':>12} {'% of kept':>11} {'frames >1%':>11} "
              f"{'added crack':>13} {'added notc':>12} {'purity':>8}")
        for nm in ("CONTEXT", "DILATE null"):
            d = sum(r["arms"][nm]["deleted"] for r in good)
            over = sum(1 for r in good
                       if r["arms"][nm]["deleted"] > 0.01 * max(r["shipped_kept"], 1))
            ac = sum(r["arms"][nm]["added_crack"] for r in good)
            an = sum(r["arms"][nm]["added_notc"] for r in good)
            print(f"   {nm:<14} {d:>12,} {100*d/max(kt,1):10.4f}% {over:>11} {ac:>13,} "
                  f"{an:>12,} {ac/max(ac+an,1):8.4f}")
    else:
        print("\n   (gate.json not present yet -- ctx_gate.py still running)")


if __name__ == "__main__":
    main()
