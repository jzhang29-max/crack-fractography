"""Read fullframe_lever4_safety.py's json and answer the one question that decides it.

The denominators, stated once so no arm quietly changes them:
  * "of kept"    = hand-marked crack pixels the no-classifier path keeps at the SAME
                   mad_k. This isolates the classifier: it is the only thing that can
                   remove a pixel from that set, so anything missing is its deletion.
  * "of painted" = all hand-marked crack pixels on the frame. This is the denominator
                   voidkiller_safety.py used for the texture veto (43.46%) and the
                   thickness excision (41.00%), so it is the one that makes this
                   comparable to the two rules already rejected.
"""
import os, sys, json
MY = os.environ.get("MYSC", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                            "35618087-5532-4f31-9699-5f1551304d41/scratchpad")
P = os.environ.get("OUT", MY + "/work/fullframe_lever4.json")
D = json.load(open(P))
ok = [r for r in D if "error" not in r]
bad = [r for r in D if "error" in r]
MKS = sorted({k for r in ok for k in r["arms"]}, key=float, reverse=True)
ARMS = ["keepall", "lever4", "lever4_fk", "shipped_clf", "shipped_clf_fk", "bigonly", "rejectall"]
print(f"{len(ok)} frames scored, {len(bad)} skipped{': ' + str([b['frame'] for b in bad]) if bad else ''}")
print(f"mad_k arms present: {MKS}\n")


def tot(rows, mk, arm, field):
    return sum(r["arms"][mk][arm][field] for r in rows)


for mk in MKS:
    P_, N_, E_ = (sum(r[k] for r in ok) for k in ("crack", "notc", "erase"))
    print("=" * 112)
    print(f"mad_k = {mk}   |   {len(ok)} frames, {P_:,} hand-marked CRACK px, "
          f"{N_:,} NOT-crack(2), {E_:,} ERASE(3)")
    kept = tot(ok, mk, "keepall", "crack")
    print(f"  {'arm':<16} {'crack px':>13} {'% of painted':>12} {'% of kept':>10} | "
          f"{'DELETED vs keepall':>18} {'% of kept':>10} | {'notcrack':>9} {'erase':>8}")
    for a in ARMS:
        c = tot(ok, mk, a, "crack")
        d = kept - c
        print(f"  {a:<16} {c:>13,} {100*c/max(P_,1):11.2f}% {100*c/max(kept,1):9.2f}% | "
              f"{d:>18,} {100*d/max(kept,1):9.2f}% | "
              f"{tot(ok, mk, a, 'notc'):>9,} {tot(ok, mk, a, 'erase'):>8,}")
    print(f"\n  CONTROLS: keepall deletion must be 0 -> {kept - tot(ok, mk, 'keepall', 'crack'):,}"
          f"   |   rejectall deletion must be 100.00% of kept -> "
          f"{100*(kept - tot(ok, mk, 'rejectall', 'crack'))/max(kept,1):.2f}%")
    print(f"  alignment: the no-classifier path covers "
          f"{100*kept/max(P_,1):.1f}% of hand-marked crack (if ~0 the paint is misaligned)")

mk = MKS[0]
print("\n" + "=" * 112)
print(f"PER FRAME at mad_k={mk}, worst deletions first. A pooled number can hide in one frame.")
print(f"  {'frame':<34} {'painted':>11} {'kept':>11} {'lever4':>11} {'deleted':>11} "
      f"{'%kept':>7} {'+fk':>11} {'%kept':>7}")
rows = sorted(ok, key=lambda r: -(r["arms"][mk]["keepall"]["crack"] - r["arms"][mk]["lever4"]["crack"]))
for r in rows:
    a = r["arms"][mk]; k = a["keepall"]["crack"]
    d = k - a["lever4"]["crack"]; dfk = k - a["lever4_fk"]["crack"]
    print(f"  {r['frame']:<34} {r['crack']:>11,} {k:>11,} {a['lever4']['crack']:>11,} "
          f"{d:>11,} {100*d/max(k,1):6.1f}% {dfk:>11,} {100*dfk/max(k,1):6.1f}%")

print("\n" + "=" * 112)
print(f"PER SPECIMEN at mad_k={mk} -- the grouping the model was held out by")
print(f"  {'specimen':<18} {'n':>2} {'painted':>12} {'kept':>12} {'deleted':>12} {'%kept':>7} "
      f"{'+fk deleted':>12} {'%kept':>7}")
for sp in sorted({r["specimen"] for r in ok}):
    g = [r for r in ok if r["specimen"] == sp]
    pa = sum(r["crack"] for r in g); k = tot(g, mk, "keepall", "crack")
    d = k - tot(g, mk, "lever4", "crack"); dfk = k - tot(g, mk, "lever4_fk", "crack")
    print(f"  {sp:<18} {len(g):>2} {pa:>12,} {k:>12,} {d:>12,} {100*d/max(k,1):6.1f}% "
          f"{dfk:>12,} {100*dfk/max(k,1):6.1f}%")
print(f"\n  frames where lever4 deletes >1% of kept crack: "
      f"{sum(1 for r in ok if (r['arms'][mk]['keepall']['crack'] - r['arms'][mk]['lever4']['crack']) > 0.01*max(r['arms'][mk]['keepall']['crack'],1))}"
      f" of {len(ok)}")
print(f"  frames where lever4+force-keep deletes >1% of kept crack: "
      f"{sum(1 for r in ok if (r['arms'][mk]['keepall']['crack'] - r['arms'][mk]['lever4_fk']['crack']) > 0.01*max(r['arms'][mk]['keepall']['crack'],1))}"
      f" of {len(ok)}")
