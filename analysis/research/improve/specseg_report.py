"""ANGLE 2 (segment the specimen first) -- VERDICT: REJECTED. It is the fifth dead rule.

A specimen mask IS computable, it IS safe at the right settings, and it is worth EXACTLY
NOTHING: across a 198-variant grid, every variant that passes the full-frame safety gate
scores the shipped tile IoU to four decimals, and every variant that improves the tile
score destroys hand-painted main crack. The two sets do not intersect anywhere.

THE PRIMARY GATE FIRST, as required. 48 frames carrying a hand-painted correction mask,
70,041,625 painted crack px, of which the shipped path (classifier off, multi-scale
union) keeps 21,162,207 -- that is the denominator, the same one
fullframe_lever4_safety.py used, so these are comparable to the four dead rules.

    arm                                   % of KEPT hand-marked crack DELETED   frames >1%
    coarse/thr0.1/R600/g200  (best safe)              0.072%  (15,175 px)            0
    fine/thr0.1/R400/g400                             0.000%  (0 px)                 0
    fine/thr0.3/R400/g0                               9.031%  (1,911,152 px)         7
    fine/thr0.5/R200/g0      (best on tiles)         27.298%  (5,776,910 px)        16
    ---- for scale, re-measured on these same 48 frames by the earlier work ----
    retrained region classifier (lever 4)            72.67%
    texture veto floor=1.0                           67.54%
    thickness excision r_big=50                      62.43%

THE TWO NUMBERS THE BRIEF ASKED FOR, for the best gate-passing arm
(coarse texture energy, threshold 0.1x the frame median, closing 600 px, grow 200 px):
    hand-marked crack OUTSIDE the specimen mask   15,175 px = 0.072% of kept,
                                                  0.022% of all painted, worst frame 0.96%,
                                                  0 of 48 frames over 1%        <- ~0, PASS
    void tile false-positive area removed         0.00%                         <- nothing

THE ANTICORRELATION IS THE RESULT. 89 of 198 variants pass the gate. All 89 score tile
IoU 0.3341, which is the shipped number: dIoU +0.0000, not approximately.

    variant                 gate %kept deleted   frames>1%   tile IoU    dIoU   void FP removed
    fine/thr0.5/R200/g0            27.298%          16        0.4771   +0.1430      81.10%
    fine/thr0.3/R200/g0            21.964%          13        0.4698   +0.1357
    fine/thr0.2/R200/g0             8.811%           8        0.4471   +0.1130
    fine/thr0.3/R400/g0             9.031%           7        0.4311   +0.0970      60.88%
    ...
    every one of the 89 safe arms  < 1.0%            0        0.3341   +0.0000       0.00%

+0.1430 tile IoU is the largest tile gain any precision rule has produced in this project
-- larger than the retrained region classifier's. It costs 5,776,910 px of hand-painted
crack, 16 of 48 frames losing more than 1% and one losing 85.26%. Priced the way lever 4
was priced: it destroys 101.9 px of real crack per px of REFEREED false positive it
removes (states 2 and 3 pooled, 386,214 px available). Lever 4, the worst of the four dead
rules, was 87. This is worse.

THE TILE INSTRUMENT, RUN HONESTLY, ALREADY SAYS ZERO. Leave-one-SPECIMEN-out over the
whole grid: fitted 0.4771, HELD-OUT 0.3341, overfit gap +0.1430. The held-out number is
the shipped number because the entire apparent gain is ONE tile -- the off-specimen void
on MAR_H_HIP_CBS_0002, which owns 78.4% of all candidate false positives on the 26 tiles
-- and when its specimen is held out, nothing in the remaining 25 tiles can pick the
variant that fixes it. A fitted 0.4771 is what a run without the specimen split reports.

AND THE TILE GAIN IS NOT ABOUT SPECIMENS AT ALL (specseg_sabotage.py):

    arm                         P        R      IoU   tp lost  cand px rm   void FP removed
    shipped                0.4147   0.6321   0.3341         0           0            0.00%
    SAFE arm               0.4147   0.6321   0.3341         0           0            0.00%
    REAL (top tile scorer) 0.6605   0.6321   0.4771         0     114,912           81.10%
    WRONG-FRAME mask       0.4123   0.6254   0.3307     1,360       1,513            0.00%
    SHIFTED mask           0.4041   0.6018   0.3188     6,140       7,063            0.00%
    AREA-MATCHED NOISE, per tile
                           0.6585   0.6302   0.4750       387     114,913           80.83%
    AREA-MATCHED NOISE, global
                           0.4122   0.3932   0.2519    48,406     115,547           37.27%

Wrong-frame and shifted both collapse, so the construction really is reading this frame's
specimen. But random coarse blocks removing the same 114,912 candidate px from that same
tile score 0.4750 against the real mask's 0.4771. On the tile instrument the measurement
is "delete 115k px from the one tile that is 100% false positive", not "know where the
material is". (The global null, told only the total budget, lands at 0.2519 and destroys
48,406 true positives, so deleting that much area blindly is much worse than doing
nothing -- the localisation is the whole content, and only one tile out of 26 has any.)

WHAT THE SAFE ARM ACTUALLY DOES, and why it still cannot be called a precision gain. It
fires on 3 of 48 frames, removing 8,263,872 candidate px (11.85% of all candidate area):
    260708_316_H_b2_front_CBS_005   5,119,872 px removed, 100.00% of its kept crack spared
    MAR_Amb_Cast_CBS_0005           2,588,864 px removed,  99.04% spared
    260708_316_H_b2_front_CBS_006     555,136 px removed, 100.00% spared
MAR_Amb_Cast_CBS_0005 is the frame unified_pipeline.py names as the one where the crack
and the background are a single connected component, and the mask separates them while
keeping 99.04% of the human's paint -- which no region-level rule could do. But all three
frames carry ZERO hand-marked not-crack, so every one of those 8,263,872 px is UNREVIEWED.
Across all 198 variants the safe arms remove 0.00% of the 386,214 refereed not-crack px.
There is no evidence that what the safe mask removes is background; there is only the
absence of evidence that it is crack. Shipping it would be shipping an unmeasured change.

WHY THIS IS STRUCTURAL, i.e. why a sixth setting will not fix it. The closing radius R is
the only thing separating "bridge the crack" from "bridge the background", and the two
demands point opposite ways on this corpus:
  * the off-specimen void on MAR_H_HIP_CBS_0002 is bridged into the specimen at R >= 600,
    so fixing the void needs R <= 400;
  * painted crack on MAR_Amb_AS_ETD_0003, MAR_Amb_HIP_CBS_0003 and MAR_Amb_AS_CBS_0003 is
    NOT bridged at R = 400 and is excised (62.23%, 51.29%, 32.66% of their kept crack).
The widest painted crack regions are wider than the narrowest off-specimen background, so
no single R orders them. That is the same disjoint-support failure that killed lever 4 by
MeanWidth, reached here through a topological operator instead of a fitted coefficient --
which is the honest answer to "is this the fifth dead rule?". It is, and the new thing it
contributes is that ENCLOSURE, the one discriminator unified_pipeline.py's comment named
as untried, has now been tried and does not separate either: the enclosure_axis() control
arm (material on both sides along some axis, no radius at all) reaches at best 2.20% void
FP removal while deleting 0.752% of kept crack, and at the settings where it removes real
void area it deletes 8.554% of the crack.

WHAT WOULD CHANGE THE ANSWER: a referee on the 8.26M px the safe arm removes. Three
frames painted with state 2 over their off-specimen background would turn "0.00% of
refereed not-crack removed" into a real precision measurement, and the safe arm would
then be either a measured 11.85% candidate-area reduction at 0.072% crack cost, or dead.
Right now it is neither.

Code: specimen_mask.py (the operator + its controls), specseg_cache.py (per-frame cache),
specseg_gate.py (PRIMARY GATE, 48 frames), specseg_tiles.py (tilebench, frame-scale mask
cropped to tiles), specseg_sabotage.py (break it), this file (cross-read).
Nothing writes outside the scratchpad. sem-crack-detector was never written to.

Run:
    .../sem-crack-detector/.venv/bin/python -B specseg_cache.py     # ~8 min, 48 frames
    ... specseg_tiles.py ; ... specseg_gate.py ; ... specseg_report.py ; ... specseg_sabotage.py

----------------------------------------------------------------------------------------
Cross-read the two instruments for every variant of the ANGLE-2 specimen mask.

One row per variant, the full-frame SAFETY number next to the tile SCORE. This is the
table the four dead rules never had: four rules scored well on 512 px tiles and were then
measured to destroy 54-77% of the hand-painted crack on full frames, and nobody could see
the contradiction in one place because the two numbers were produced by different runs
against different unit sets.

Both columns come from the shared grid in specimen_mask.GRID, so every row is the same
object measured twice. The gate column is the one that decides.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
sys.dont_write_bytecode = True
import tilebench as TB
import specseg_cache as FC

GATE = os.path.join(FC.WORK, "gate.json")
TILE = os.path.join(FC.WORK, "tilecounts.json")


def main():
    g = json.load(open(GATE))
    t = json.load(open(TILE))
    base = TB.evaluate("b", {"b": t["shipped (no specimen mask)"]}, quiet=True)["loso"]
    rows = []
    for k, rs in g.items():
        if k not in t:
            continue
        kept = sum(r["kept"] for r in rs); dele = sum(r["del_kept"] for r in rs)
        cand = sum(r["cand"] for r in rs); rmc = sum(r["rm_cand"] for r in rs)
        notc = sum(r["notc_in"] for r in rs); rmn = sum(r["rm_notc"] for r in rs)
        nbad = sum(1 for r in rs if r["del_kept"] / max(r["kept"], 1) > 0.01)
        worst = max(r["del_kept"] / max(r["kept"], 1) for r in rs)
        nfire = sum(1 for r in rs if r["rm_cand"] > 0)
        m = TB.evaluate(k, {k: t[k]}, quiet=True)["loso"]
        rows.append(dict(k=k, pct=100 * dele / max(kept, 1), nbad=nbad,
                         worst=100 * worst, nfire=nfire, rmc=rmc,
                         pcand=100 * rmc / max(cand, 1), rmn=rmn,
                         pnotc=100 * rmn / max(notc, 1), **m))
    tot_kept = sum(r["kept"] for r in next(iter(g.values())))
    tot_cand = sum(r["cand"] for r in next(iter(g.values())))
    tot_notc = sum(r["notc_in"] for r in next(iter(g.values())))
    tot_crack = sum(r["crack"] for r in next(iter(g.values())))
    print(f"48 full frames: {tot_crack:,} hand-painted crack px, of which the shipped path"
          f" keeps {tot_kept:,} (the GATE DENOMINATOR).")
    print(f"  candidate area {tot_cand:,} px;  hand-marked NOT-crack (2 pooled with 3) "
          f"inside candidates {tot_notc:,} px")
    print(f"26 tiles, shipped baseline: P {base['precision']:.4f} R {base['recall']:.4f} "
          f"IoU {base['iou']:.4f} F1 {base['f1']:.4f}\n")

    hdr = (f"{'':4}{'variant':<30}{'GATE %kept DEL':>15}{'fr>1%':>6}{'worst':>8}"
           f"{'fires':>6}{'cand rm':>8}{'notc rm':>8}{'tile P':>8}{'tile R':>8}"
           f"{'tile IoU':>9}{'dIoU':>8}")

    print("=== ranked by tile IoU (the view that killed four rules) ===")
    print(hdr)
    for r in sorted(rows, key=lambda r: -r["iou"])[:14]:
        f = "PASS" if (r["pct"] < 1.0 and r["nbad"] == 0) else "FAIL"
        print(f"{f:<4}{r['k']:<30}{r['pct']:>14.3f}%{r['nbad']:>6}{r['worst']:>7.2f}%"
              f"{r['nfire']:>6}{r['pcand']:>7.2f}%{r['pnotc']:>7.2f}%"
              f"{r['precision']:>8.4f}{r['recall']:>8.4f}{r['iou']:>9.4f}"
              f"{r['iou'] - base['iou']:>+8.4f}")

    print("\n=== PASS the gate (<1% deleted AND no frame over 1%), ranked by area removed ===")
    print(hdr)
    ok = [r for r in rows if r["pct"] < 1.0 and r["nbad"] == 0]
    for r in sorted(ok, key=lambda r: -r["rmc"])[:14]:
        print(f"{'PASS':<4}{r['k']:<30}{r['pct']:>14.3f}%{r['nbad']:>6}{r['worst']:>7.2f}%"
              f"{r['nfire']:>6}{r['pcand']:>7.2f}%{r['pnotc']:>7.2f}%"
              f"{r['precision']:>8.4f}{r['recall']:>8.4f}{r['iou']:>9.4f}"
              f"{r['iou'] - base['iou']:>+8.4f}")
    print(f"\n{len(ok)} of {len(rows)} variants pass the gate. "
          f"Best tile IoU among them: {max((r['iou'] for r in ok), default=0):.4f} "
          f"(shipped {base['iou']:.4f}).")
    best_tile = max(rows, key=lambda r: r["iou"])
    print(f"Best tile IoU overall: {best_tile['k']} at {best_tile['iou']:.4f}, which "
          f"deletes {best_tile['pct']:.3f}% of kept hand-marked crack on the full frames "
          f"with {best_tile['nbad']} frames over 1% (worst {best_tile['worst']:.2f}%).")


if __name__ == "__main__":
    main()
