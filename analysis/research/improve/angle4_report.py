"""ANGLE 4 report: the full-frame precision bracket, and how much of it is measurement.

Reads angle4_fullframe.json. Prints the three ends of the bracket, the per-frame spread,
and -- the number that decides how much any of it is worth -- how concentrated the
refereed negative evidence is.
"""
import os, sys, json, statistics

OUT = os.environ.get("A4OUT", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                              "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/angle4")
rows = [r for r in json.load(open(os.path.join(OUT, "fullframe.json"))) if "error" not in r]
bad = [r for r in json.load(open(os.path.join(OUT, "fullframe.json"))) if "error" in r]

T = {k: sum(r["pred"][k] for r in rows) for k in ("area", "c0", "c1", "c2", "c3")}
corr = {v: sum(r["corr_counts"][v] for r in rows) for v in "0123"}
px = sum(r["shape"][0] * r["shape"][1] for r in rows)

print(f"{len(rows)} frames scored, {len(bad)} skipped {[b['frame'] for b in bad]}")
print(f"total image area            {px:,} px")
print(f"hand-marked CRACK   (1)     {corr['1']:>14,}   {100*corr['1']/px:6.2f}% of corpus")
print(f"hand-marked NOT-CRACK (2)   {corr['2']:>14,}   {100*corr['2']/px:6.2f}%")
print(f"hand-ERASED           (3)   {corr['3']:>14,}   {100*corr['3']/px:6.2f}%")
print(f"UNREVIEWED            (0)   {corr['0']:>14,}   {100*corr['0']/px:6.2f}%")

ref = T["c1"] + T["c2"] + T["c3"]
print(f"\nSHIPPED v1.49.1 marks       {T['area']:>14,} px "
      f"({100*T['area']/px:.2f}% of the corpus)")
print(f"  on hand-marked CRACK      {T['c1']:>14,}")
print(f"  on hand-marked NOT-CRACK  {T['c2']+T['c3']:>14,}  (state 2 {T['c2']:,} + "
      f"state 3 {T['c3']:,})")
print(f"  on UNREVIEWED             {T['c0']:>14,}  "
      f"({100*T['c0']/max(T['area'],1):.1f}% of everything it marks)")

print("\n" + "=" * 72)
print("FULL-FRAME PRECISION BRACKET")
print("=" * 72)
print(f"  P_pessimistic  every unreviewed px counted as error      "
      f"{T['c1']/max(T['area'],1):.4f}")
print(f"  P_refereed     refereed pixels only (THE MEASUREMENT)    "
      f"{T['c1']/max(ref,1):.4f}")
print(f"  P_credit       every unreviewed px counted as crack      "
      f"{(T['c1']+T['c0'])/max(T['area'],1):.4f}")

ps = [(r["pred"]["c1"] / max(r["pred"]["c1"] + r["pred"]["c2"] + r["pred"]["c3"], 1),
       r["pred"]["c1"] + r["pred"]["c2"] + r["pred"]["c3"], r["frame"]) for r in rows]
have = [p for p in ps if p[1] >= 1000]
print(f"\n  per-frame P_refereed, {len(have)} frames with >=1,000 refereed predicted px:")
print(f"    median {statistics.median(p[0] for p in have):.4f}   "
      f"min {min(p[0] for p in have):.4f}   max {max(p[0] for p in have):.4f}")
print(f"    frames with NO refereed not-crack under the mask at all: "
      f"{sum(1 for r in rows if r['pred']['c2']+r['pred']['c3'] == 0)} of {len(rows)}")

neg = sorted(((r["pred"]["c2"] + r["pred"]["c3"], r["frame"]) for r in rows), reverse=True)
tot_neg = sum(n for n, _ in neg)
print(f"\n  CONCENTRATION of the refereed negative evidence ({tot_neg:,} px total):")
for n, f in neg[:5]:
    print(f"    {f:<34} {n:>10,}  {100*n/max(tot_neg,1):5.1f}%")
print(f"    top 1 frame {100*neg[0][0]/max(tot_neg,1):.1f}%, "
      f"top 3 {100*sum(n for n,_ in neg[:3])/max(tot_neg,1):.1f}%, "
      f"top 5 {100*sum(n for n,_ in neg[:5])/max(tot_neg,1):.1f}%")

print(f"\n  ASCERTAINMENT: the referee did not sample the frame at random.")
cov_pred = T["c1"] + T["c2"] + T["c3"]
print(f"    share of PREDICTED px that carry any verdict      "
      f"{cov_pred/max(T['area'],1):.4f}")
print(f"    share of UNPREDICTED px that carry any verdict    "
      f"{(corr['1']+corr['2']+corr['3']-cov_pred)/max(px-T['area'],1):.4f}")
print(f"    -> a predicted pixel is "
      f"{(cov_pred/max(T['area'],1))/max((corr['1']+corr['2']+corr['3']-cov_pred)/max(px-T['area'],1),1e-9):.1f}x "
      f"more likely to have been refereed than an unpredicted one.")
print(f"    Of all hand-marked NOT-CRACK, the detector marks "
      f"{100*(T['c2'])/max(corr['2'],1):.1f}% (state 2) and "
      f"{100*T['c3']/max(corr['3'],1):.1f}% (state 3).")
print(f"    Of all hand-marked CRACK, the detector marks "
      f"{100*T['c1']/max(corr['1'],1):.1f}%  <- full-frame recall over refereed crack")

print(f"\n  SPECIMEN-MASK INSTRUMENT (coarse blur+Otsu body mask) -- positive control:")
cob = sum(r["crack_off_body"] for r in rows); ct = sum(r["crack_total"] for r in rows)
nob = sum(r["notc_off_body"] for r in rows); nt = sum(r["notc_total"] for r in rows)
print(f"    hand-marked CRACK placed OFF the specimen body:     "
      f"{cob:,}/{ct:,} = {100*cob/max(ct,1):.1f}%   <- must be ~0 for the mask to mean "
      f"anything")
print(f"    hand-marked NOT-CRACK placed OFF the specimen body: "
      f"{nob:,}/{nt:,} = {100*nob/max(nt,1):.1f}%")
