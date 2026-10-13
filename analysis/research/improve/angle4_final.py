"""ANGLE 4 final: the precision ceiling, with the adjudicator's own error carried.

VERDICT. Precision is already near its measurable ceiling and further precision work on
this corpus is close to wasted. The quoted 0.4153 is not a measurement of how often the
detector is wrong; it is a measurement of how little has been refereed, plus one void.

  TILES (26, held-out, shipped v1.49.1, classifier off). Pessimistic P 0.4153. Stroke-edge
  correction -- unmarked predicted pixels within 2 px of painted crack excluded as
  unknown -- gives 0.4302, and 0.4384 at 16 px. That lift passes its decoy: a sham paint
  of identical area and geometry, shifted or rotated, excuses 0.76-0.79% of the FP mass
  where the real paint excuses 5.95%. BRACKET [0.4153, 0.4384].
  But 78.6% of ALL tile false-positive mass is ONE object: the off-specimen void on
  MAR_H_HIP_CBS_0002. Drop that tile and the bracket is [0.7674, 0.8486], and the
  stroke-edge band alone accounts for 27.19% of the remaining FP against 1.10% for the
  decoys. Headroom for any future rule: removing every non-void, non-stroke-edge FP
  pixel perfectly and for free moves 26-tile precision 0.4153 -> 0.4570, +0.0417.
  Removing only the void moves it to 0.7681, +0.3529.

  FULL FRAMES (48, hand paint, 1/2/3 refereed, 0 excluded). The detector marks 69,576,538
  px: 21,116,721 on refereed crack, 386,125 on refereed not-crack, 48,073,692 (69.1%)
  never refereed at all. P_pessimistic 0.3035, P_refereed 0.9820, P_credit 0.9945.
  Neither end is a measurement: the referee is 4.7x more likely to have looked at a
  predicted pixel than an unpredicted one, the detector covers 85.5% of every
  hand-marked not-crack pixel in the corpus (the state-2 paint is a correction OF the
  detector, so the refereed negatives are by construction its known errors), 28 of 48
  frames carry no refereed not-crack under the mask at all, and one frame supplies 34.5%
  of all refereed negative evidence.

  THE CENSUS locates the truth between them. A PPS-by-area blind sample of unreviewed
  predicted components, adjudicated against criteria fixed in advance and scored against
  an independently calibrated adjudicator (round 2: sensitivity 0.778 on 18 human-verified
  crack components, false-call rate 0.273 on 22 human-verified not-crack, Fisher one-sided
  p = 0.0018), puts the real-crack share of the unreviewed mass at 0.780, 95% CI
  [0.295, 1.000]. Full-frame precision 0.8424, CI [0.5072, 0.9945]. The census population
  covers 53.5% of the unreviewed mass; making NO assumption about the rest brackets it
  [0.5916, 0.9132], and 34.0% of that remainder sits in components the human already
  refereed as crack in part.

  WHAT IS NOT MEASURABLE: class (a), the off-specimen void. The VOID control arm -- real
  components from the frame whose void owns 78.6% of tile FP -- was called "plausibly
  real crack" 4 times in 5, and 3 of 18 human-verified CRACK components were called
  "off-specimen". A human adjudicator with full frame context cannot separate them
  either. The 0.780 is therefore crack-OR-void and an upper bound on crack.

  FIFTH DEAD RULE: keep-only-on-specimen-body, the obvious implementation of the one
  discriminator unified_pipeline.py calls untried ("whether the region is ENCLOSED BY
  SPECIMEN"). Coarse blur + Otsu + hole fill. It deletes 75.47% of the hand-marked crack
  the shipped path keeps, 41 of 48 frames losing >1%, 149.6 px of real crack per px of
  refereed false positive removed -- worse than all four rules already buried here. A
  sigma sweep from 25 to 800 does not rescue it: 82.7-94.0% of hand-marked crack lands
  off-body at every scale. The idea may still be right; this implementation of it is not.


Round 2 calibrated the adjudicator on an independent, size-matched, blind pool of
components the human had already refereed: sensitivity 0.778 (18 known-crack), false-call
rate 0.273 (22 known-not-crack), Fisher one-sided p = 0.0018. So the round-1 PPS census
of the unreviewed mass can be corrected for it:

    true crack share = (observed b-rate - fpr) / (sensitivity - fpr)

and the uncertainty in all three terms is carried by bootstrapping the three samples
together. Sabotage tests below: break each input and the estimate must collapse.
"""
import os, sys, json, random

OUT = os.environ.get("A4OUT", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                              "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/angle4")
rows = [r for r in json.load(open(os.path.join(OUT, "fullframe.json"))) if "error" not in r]
T = {k: sum(r["pred"][k] for r in rows) for k in ("area", "c0", "c1", "c2", "c3")}
cen = json.load(open(os.path.join(OUT, "census.json")))["UNREV"]
cal = json.load(open(os.path.join(OUT, "calib.json")))


def expand(d):
    return [k for k, v in d.items() for _ in range(v)]


UN = expand(cen)
POS = expand(cal["by"]["REFPOS"])
NEG = expand(cal["by"]["REFNEG"])


def rate(s):
    return s.count("b") / len(s)


def corrected(un, pos, neg):
    o, se, fp = rate(un), rate(pos), rate(neg)
    if se - fp <= 0:
        return None
    return min(max((o - fp) / (se - fp), 0.0), 1.0)


def boot(un, pos, neg, n=20000, seed=11):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        v = corrected([rng.choice(un) for _ in un], [rng.choice(pos) for _ in pos],
                      [rng.choice(neg) for _ in neg])
        if v is not None:
            out.append(v)
    out.sort()
    return out


pt = corrected(UN, POS, NEG)
bs = boot(UN, POS, NEG)
lo, hi = bs[len(bs) // 40], bs[-len(bs) // 40]


def P(share):
    return (T["c1"] + share * T["c0"]) / T["area"]


print("=" * 74)
print("WHAT FRACTION OF THE UNREVIEWED PREDICTED MASS IS REAL CRACK")
print("=" * 74)
print(f"  observed (b) rate, PPS census of unreviewed components   {rate(UN):.3f} (n={len(UN)})")
print(f"  adjudicator sensitivity, round-2 known-crack             {rate(POS):.3f} (n={len(POS)})")
print(f"  adjudicator false-call rate, round-2 known-not-crack     {rate(NEG):.3f} (n={len(NEG)})")
print(f"  Fisher one-sided p that the adjudicator separates them   {cal['p']:.4f}")
print(f"\n  CALIBRATION-CORRECTED crack share of the unreviewed mass "
      f"{pt:.3f}   95% CI [{lo:.3f}, {hi:.3f}]")
print(f"  ({100*(bs.count(1.0)/len(bs)):.1f}% of bootstrap draws saturate at 1.0)")

print("\n" + "=" * 74)
print("FULL-FRAME PRECISION OF THE SHIPPED v1.49.1 PATH, 48 frames")
print("=" * 74)
print(f"  predicted {T['area']:,} px: {T['c1']:,} on refereed crack, "
      f"{T['c2']+T['c3']:,} on refereed not-crack, {T['c0']:,} unreviewed")
print(f"\n  P_pessimistic   unreviewed all counted as error     {T['c1']/T['area']:.4f}")
print(f"  P_corrected     census + calibration                {P(pt):.4f}   "
      f"95% CI [{P(lo):.4f}, {P(hi):.4f}]")
print(f"  P_refereed      refereed pixels only                "
      f"{T['c1']/(T['c1']+T['c2']+T['c3']):.4f}")
print(f"  P_credit        unreviewed all counted as crack     "
      f"{(T['c1']+T['c0'])/T['area']:.4f}")

print("\n" + "=" * 74)
print("SABOTAGE TESTS -- each must collapse the estimate")
print("=" * 74)
allb = ["b"] * len(NEG)
# The pooled arms must be SHUFFLED before resplitting. Slicing the concatenation in order
# hands back the original POS and NEG lists and reproduces the real answer exactly --
# which is what the first version of this test did, and it "passed".
_pool = POS + NEG
random.Random(3).shuffle(_pool)
tests = [
    ("adjudicator cannot tell: POS and NEG pooled and reshuffled",
     UN, _pool[:len(POS)], _pool[len(POS):]),
    ("unreviewed mass looks exactly like verified NOT-crack",
     NEG * 3, POS, NEG),
    ("unreviewed mass looks exactly like verified crack",
     POS * 3, POS, NEG),
    ("adjudicator calls everything crack (no information)",
     ["b"] * len(UN), ["b"] * len(POS), allb),
]
for name, u, p, n in tests:
    v = corrected(u, p, n)
    print(f"  {name:<56} -> "
          + ("undefined (sens <= fpr), estimate refuses to compute" if v is None
             else f"crack share {v:.3f}, precision {P(v):.4f}"))

print("\n" + "=" * 74)
print("THE (a) CLASS CANNOT BE MEASURED BY THIS INSTRUMENT")
print("=" * 74)
r1 = json.load(open(os.path.join(OUT, "census.json")))
print(f"  VOID control (components on the off-specimen void frame, known class a):")
print(f"    called (a) {r1['VOID'].get('a',0)} of {sum(r1['VOID'].values())}, "
      f"called (b) real crack {r1['VOID'].get('b',0)} of {sum(r1['VOID'].values())}")
print(f"  REFPOS round 2 (human-verified CRACK) called (a): "
      f"{cal['by']['REFPOS'].get('a',0)} of {sum(cal['by']['REFPOS'].values())}")
print("  -> the adjudicator calls known void 'crack' 4 times in 5 and known crack 'void'")
print("     1 time in 6. (a) and (b) are not separable here by a human with full frame")
print("     context, which is the same wall unified_pipeline.py documents for the code.")
