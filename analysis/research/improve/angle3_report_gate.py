import sys, json
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
import angle3_paint_gate as G

rows = [r for r in json.load(open(A.WORK + "/angle3_paint.json")) if "error" not in r]
bad = [r for r in json.load(open(A.WORK + "/angle3_paint.json")) if "error" in r]
print(f"{len(rows)} frames scored, {len(bad)} skipped {[b['frame'] for b in bad]}")
K = sum(r["arms"]["shipped"]["crack"] for r in rows)
PC = sum(r["painted_crack"] for r in rows)
PN = sum(r["painted_notc"] for r in rows)
print(f"hand-painted crack over these frames: {PC:,} px   hand-painted not-crack: {PN:,} px")
print(f"hand-marked crack the SHIPPED path keeps: {K:,} px  (the gate denominator)\n")

print(f"  {'arm':<12} {'kept crack':>12} {'DELETED':>12} {'% of kept':>10} "
      f"{'frames >1%':>11} {'notc removed':>13} {'crack per notc':>15}")
for nm in G.ARMS:
    if nm == "shipped":
        print(f"  {'shipped':<12} {K:>12,} {0:>12,} {0.0:>9.2f}% {0:>11} {0:>13,} {'--':>15}")
        continue
    d = sum(r["arms"][nm]["deleted"] for r in rows)
    nr = sum(r["arms"][nm]["notc_removed"] for r in rows)
    kc = sum(r["arms"][nm]["crack"] for r in rows)
    over = sum(1 for r in rows
               if r["arms"][nm]["deleted"] > 0.01 * max(r["arms"]["shipped"]["crack"], 1))
    ratio = f"{d/nr:.1f}" if nr else ("inf" if d else "--")
    print(f"  {nm:<12} {kc:>12,} {d:>12,} {100*d/K:>9.2f}% {over:>11} {nr:>13,} {ratio:>15}")

print("\n=== ADDITIVE arms: purity of what they ADD, over reviewed pixels only ===")
ship_pur = sum(r["arms"]["shipped"]["crack"] for r in rows) / max(
    sum(r["arms"]["shipped"]["crack"] + r["arms"]["shipped"]["notc"] for r in rows), 1)
print(f"  shipped operating purity on reviewed full-frame pixels: {ship_pur:.4f}")
for nm in G.SUPERSETS:
    ac = sum(r["arms"][nm]["added_crack"] for r in rows)
    an = sum(r["arms"][nm]["added_notc"] for r in rows)
    aa = sum(r["arms"][nm]["added_area"] for r in rows)
    de = sum(r["arms"][nm]["deleted"] for r in rows)
    print(f"  {nm:<10} adds {aa:>12,} px, of which {ac + an:>10,} reviewed, "
          f"purity {ac/max(ac+an,1):.4f}   (deleted {de} -> superset {'HOLDS' if de==0 else 'VIOLATED'})")

print("\n=== per-frame worst losses, absoff ===")
w = sorted(rows, key=lambda r: -r["arms"]["absoff"]["deleted"] /
           max(r["arms"]["shipped"]["crack"], 1))
for r in w[:5]:
    k = r["arms"]["shipped"]["crack"]
    print(f"  {r['frame']:<36} kept {k:>10,}  deleted {r['arms']['absoff']['deleted']:>10,}"
          f"  ({100*r['arms']['absoff']['deleted']/max(k,1):5.1f}%)")
print("\n=== per-frame worst losses, filt100 (the only arm that could pass) ===")
w = sorted(rows, key=lambda r: -r["arms"]["filt100"]["deleted"] /
           max(r["arms"]["shipped"]["crack"], 1))
for r in w[:5]:
    k = r["arms"]["shipped"]["crack"]
    print(f"  {r['frame']:<36} kept {k:>10,}  deleted {r['arms']['filt100']['deleted']:>10,}"
          f"  ({100*r['arms']['filt100']['deleted']/max(k,1):6.3f}%)")

print("\n=== per-SPECIMEN deletion, absoff and filt100 (frames grouped by name prefix) ===")
import json as _j, os as _o
specs = sorted({t["specimen"] for t in _j.load(open(A.SC_TILES))} if hasattr(A, "SC_TILES")
               else set(), key=len, reverse=True)
if not specs:
    SCT = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
           "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/tiles_meta.json")
    specs = sorted({t["specimen"] for t in _j.load(open(SCT))}, key=len, reverse=True)
from collections import defaultdict
g = defaultdict(lambda: defaultdict(int))
for r in rows:
    sp = next((s for s in specs if r["frame"].startswith(s)), "(other)")
    g[sp]["kept"] += r["arms"]["shipped"]["crack"]
    g[sp]["n"] += 1
    for nm in ("absoff", "filt100", "open2", "gridbest"):
        g[sp][nm] += r["arms"][nm]["deleted"]
print(f"  {'specimen':<22} {'frames':>6} {'kept crack':>12} {'absoff':>9} {'filt100':>9}"
      f" {'open2':>9} {'gridbest':>9}")
for sp in sorted(g, key=lambda s: -g[s]["kept"]):
    d = g[sp]; k = max(d["kept"], 1)
    print(f"  {sp:<22} {d['n']:>6} {d['kept']:>12,} "
          f"{100*d['absoff']/k:>8.1f}% {100*d['filt100']/k:>8.2f}% "
          f"{100*d['open2']/k:>8.1f}% {100*d['gridbest']/k:>8.1f}%")
