"""ANGLE 4, the PRIMARY GATE, plus the precision headroom the ceiling leaves.

Two things, both on the 48 frames carrying a correction mask.

1. THE GATE. This angle is a measurement, so the shipped mask is scored unmodified and
   deletes 0.00% by construction. That is a vacuous zero, so the gate is also run on the
   one rule this work actually produced: keep only candidates that lie on a coarse
   SPECIMEN BODY mask. That is the obvious implementation of the one discriminator
   unified_pipeline's own comment calls untried -- "whether the region is ENCLOSED BY
   SPECIMEN". It is reported here because it fails, and a fifth dead rule measured
   properly is worth more than a fabricated win.

2. THE HEADROOM. On the 26 tiles, how much of the false-positive mass is left once the
   single off-specimen void tile and the stroke-edge band are set aside -- i.e. the most
   any future precision rule could buy, even if it were perfect and free.
"""
import os, sys, json

OUT = os.environ.get("A4OUT", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                              "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/angle4")
rows = [r for r in json.load(open(os.path.join(OUT, "fullframe.json"))) if "error" not in r]

print("=" * 74)
print("PRIMARY GATE -- hand-marked crack deleted, 48 frames, as a share of the crack")
print("the SHIPPED path currently keeps")
print("=" * 74)
kept = sum(r["pred"]["c1"] for r in rows)
print(f"  crack px the shipped v1.49.1 path keeps:  {kept:,}")
print(f"  hand-marked crack on these frames:        "
      f"{sum(int(r['corr_counts']['1']) for r in rows):,}")

arms = [("ANGLE 4 as measured (shipped mask, unmodified)",
         lambda r: r["pred"]["c1"]),
        ("keep-on-specimen-body (blur+Otsu enclosure)",
         lambda r: r["pred_on_body"]["c1"])]
for name, f in arms:
    k = sum(f(r) for r in rows)
    d = kept - k
    lose = sum(1 for r in rows
               if r["pred"]["c1"] > 0 and (r["pred"]["c1"] - f(r)) > 0.01 * r["pred"]["c1"])
    print(f"\n  {name}")
    print(f"    keeps {k:>12,}   DELETES {d:>12,}  = {100*d/max(kept,1):6.2f}% "
          f"{'PASS (<1%)' if 100*d/max(kept,1) < 1 else 'FAIL'}")
    print(f"    frames losing >1% of their own kept crack: {lose} of {len(rows)}")
    if "body" in name:
        notc = sum(r["pred"]["c2"] + r["pred"]["c3"] for r in rows)
        notc_k = sum(r["pred_on_body"]["c2"] + r["pred_on_body"]["c3"] for r in rows)
        print(f"    hand-marked NOT-crack it removes: {notc - notc_k:,} of {notc:,}")
        print(f"    -> {(d) / max(notc - notc_k, 1):.1f} px of real crack destroyed per px "
              f"of refereed false positive removed")

print("\n" + "=" * 74)
print("HEADROOM -- what is left for any precision rule to win, on the 26 tiles")
print("=" * 74)
tb = json.load(open(os.path.join(OUT, "tile_bracket.json")))
FL = "MAR_H_HIP_CBS_0002__crop_3122_120_512x512"
tp = sum(r["real"]["tp"] for r in tb)
fp = sum(r["real"]["fp_pess"] for r in tb)
void = next(r for r in tb if r["frame"] == FL)["real"]["fp_pess"]
rest = [r for r in tb if r["frame"] != FL]
fp_rest = sum(r["real"]["fp_pess"] for r in rest)
edge = fp_rest - sum(r["real"]["fp_adj2"] for r in rest)
hard = fp_rest - edge
print(f"  total FP                                   {fp:>9,}  100.0%")
print(f"    the one off-specimen void tile           {void:>9,}  {100*void/fp:5.1f}%")
print(f"    within 2 px of painted crack (25 tiles)  {edge:>9,}  {100*edge/fp:5.1f}%  "
      f"(decoys reach 1.1%, so this is real)")
print(f"    everything else                          {hard:>9,}  {100*hard/fp:5.1f}%")
print()
print(f"  precision now                                           {tp/(tp+fp):.4f}")
print(f"  a PERFECT rule that removes 'everything else', free     "
      f"{tp/(tp+fp-hard):.4f}   (+{tp/(tp+fp-hard) - tp/(tp+fp):.4f})")
print(f"  the same rule if it also removed the void               "
      f"{tp/(tp+fp-hard-void):.4f}   (+{tp/(tp+fp-hard-void) - tp/(tp+fp):.4f})")
print(f"  removing ONLY the void, nothing else                    "
      f"{tp/(tp+fp-void):.4f}   (+{tp/(tp+fp-void) - tp/(tp+fp):.4f})")

print("\n" + "=" * 74)
print("CENSUS-CORRECTED full-frame precision")
print("=" * 74)
T = {k: sum(r["pred"][k] for r in rows) for k in ("area", "c0", "c1", "c2", "c3")}
cen = json.load(open(os.path.join(OUT, "census.json")))
u = cen["UNREV"]; n = sum(u.values())
pb = u.get("b", 0) / n
import random
random.seed(7)
calls = ["b"] * u.get("b", 0) + ["a"] * u.get("a", 0) + ["c"] * u.get("c", 0) \
        + ["u"] * u.get("u", 0)
bs = []
for _ in range(20000):
    s = [random.choice(calls) for _ in calls]
    p = s.count("b") / len(s)
    bs.append((T["c1"] + p * T["c0"]) / T["area"])
bs.sort()
print(f"  unreviewed predicted mass            {T['c0']:,} px")
print(f"  blind PPS census calls (b) on        {pb:.3f} of it (n={n})")
print(f"  => precision                         "
      f"{(T['c1'] + pb*T['c0'])/T['area']:.4f}   "
      f"95% CI from the census bootstrap [{bs[500]:.4f}, {bs[19500]:.4f}]")
print(f"  (bracket ends, for reference: pessimistic "
      f"{T['c1']/T['area']:.4f}, refereed-only "
      f"{T['c1']/(T['c1']+T['c2']+T['c3']):.4f})")
print("  This credits every (b) call as crack. (b) cannot be separated from an")
print("  off-specimen void -- the VOID control arm was called (b) 4 times in 5 -- so it")
print("  is an upper bound on crack and the interval is a census interval only: it does")
print("  not carry the adjudicator's own error, which the control arms bound at")
print("  sensitivity 0.625 and false-call rate 0.250.")
