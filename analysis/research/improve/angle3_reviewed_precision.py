import sys, json
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
import angle3_paint_gate as G
rows = [r for r in json.load(open(A.WORK + "/angle3_paint.json")) if "error" not in r]
PC = sum(r["painted_crack"] for r in rows); PN = sum(r["painted_notc"] for r in rows)
print(f"hand-marked CRACK {PC:,}   hand-marked NOT-CRACK {PN:,}   "
      f"not-crack is {100*PN/(PC+PN):.2f}% of the reviewed pool")
print("\nPRECISION ON REVIEWED FULL-FRAME PIXELS ONLY -- read the caveat below the table")
print(f"  {'arm':<10} {'marked crack':>13} {'marked notc':>12} {'reviewed P':>11} {'recall':>9}")
for nm in G.ARMS:
    c = sum(r["arms"][nm]["crack"] for r in rows)
    n = sum(r["arms"][nm]["notc"] for r in rows)
    print(f"  {nm:<10} {c:>13,} {n:>12,} {c/max(c+n,1):>11.4f} {c/PC:>9.4f}")
print(f"\n  CAVEAT: the hand-marked not-crack pool is {PN:,} px against {PC:,} px of crack,")
print(f"  i.e. {PN/PC:.4f} not-crack per crack pixel. A mask that marked EVERY reviewed")
print(f"  pixel would score reviewed-precision {PC/(PC+PN):.4f}. So this column cannot")
print("  rank precision; it is a floor check, not a measurement. The tiles are the only")
print("  instrument with a real negative class, and they cannot hold a wide-open crack.")
print("\n  control -- mark-everything-reviewed:", f"{PC/(PC+PN):.4f}")
