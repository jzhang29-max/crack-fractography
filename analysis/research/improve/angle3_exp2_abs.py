"""The absolute darkness term img8 < T: per-specimen, per-tile, and a threshold sweep."""
import sys, time
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
import tilebench as TB
import numpy as np
from collections import defaultdict

tiles = TB.load(with_raw=True)
caches = [A.scale_cache(t["img8"]) for t in tiles]
FLOODED = TB.FLOODED


def masks(absd):
    return [A.clean(A.union_at(c, t["img8"], 5.0, absd), min_area=13)
            for t, c in zip(tiles, caches)]


print("=== per-TILE: shipped (abs=10) vs abs OFF ===")
on, off = masks(10), masks(0)
print(f"  {'tile':<46} {'spec':<18} {'gt':>8} {'P_on':>6} {'P_off':>6} {'R_on':>6} {'R_off':>6}"
      f" {'px lost':>9}")
rows = []
for t, a, b in zip(tiles, on, off):
    ca, cb = TB.counts(a, t["gt"], tol=0), TB.counts(b, t["gt"], tol=0)
    pa = ca["tp"] / max(ca["tp"] + ca["fp"], 1); pb = cb["tp"] / max(cb["tp"] + cb["fp"], 1)
    ra = ca["tp"] / max(ca["tp"] + ca["fn"], 1); rb = cb["tp"] / max(cb["tp"] + cb["fn"], 1)
    lost = int((a & ~b).sum())
    rows.append((t, ca, cb))
    mark = " <-FLOODED" if t["frame"] == FLOODED else ""
    print(f"  {t['frame'][:45]:<46} {t['specimen']:<18} {int(t['gt'].sum()):>8,} "
          f"{pa:>6.3f} {pb:>6.3f} {ra:>6.3f} {rb:>6.3f} {lost:>9,}{mark}")

print("\n=== per-SPECIMEN: recall and TP loss from removing the absolute term ===")
agg = defaultdict(lambda: dict(tpa=0, fpa=0, fna=0, tpb=0, fpb=0, fnb=0))
for t, ca, cb in rows:
    d = agg[t["specimen"]]
    d["tpa"] += ca["tp"]; d["fpa"] += ca["fp"]; d["fna"] += ca["fn"]
    d["tpb"] += cb["tp"]; d["fpb"] += cb["fp"]; d["fnb"] += cb["fn"]
print(f"  {'specimen':<20} {'gt px':>9} {'R_on':>7} {'R_off':>7} {'TP lost':>9} {'%TP lost':>9}"
      f" {'P_on':>7} {'P_off':>7}")
for s in sorted(agg):
    d = agg[s]
    ra = d["tpa"] / max(d["tpa"] + d["fna"], 1); rb = d["tpb"] / max(d["tpb"] + d["fnb"], 1)
    pa = d["tpa"] / max(d["tpa"] + d["fpa"], 1); pb = d["tpb"] / max(d["tpb"] + d["fpb"], 1)
    lost = d["tpa"] - d["tpb"]
    print(f"  {s:<20} {d['tpa']+d['fna']:>9,} {ra:>7.4f} {rb:>7.4f} {lost:>9,} "
          f"{100*lost/max(d['tpa'],1):>8.1f}% {pa:>7.4f} {pb:>7.4f}")

print("\n=== threshold sweep on the absolute term (full union, mad_k=5.0) ===")
variants = {}
for T in (0, 1, 2, 3, 5, 8, 10, 15, 20):
    ms = masks(T)
    variants[T] = [TB.counts(m, t["gt"]) for m, t in zip(ms, tiles)]
    r = TB.evaluate(f"abs<{T}", {"x": variants[T]}, quiet=True)["loso"]
    print(f"  abs_thresh={T:<3} P {r['precision']:.4f}  R {r['recall']:.4f}  "
          f"IoU {r['iou']:.4f}  F1 {r['f1']:.4f}")

print("\n=== LOSO SELECTION over the absolute threshold (honest held-out) ===")
TB.evaluate("absolute-threshold family", variants, criterion="iou")
TB.evaluate("absolute-threshold family", variants, criterion="f1")

print("\n=== excluding the flooded off-specimen void tile ===")
keep = [i for i, t in enumerate(tiles) if t["frame"] != FLOODED]
for T in (0, 10):
    c = [variants[T][i] for i in keep]
    tp = sum(x["tp"] for x in c); fp = sum(x["fp"] for x in c); fn = sum(x["fn"] for x in c)
    p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
    print(f"  abs<{T:<3} (25 tiles)  P {p:.4f}  R {r:.4f}  IoU {tp/max(tp+fp+fn,1):.4f}"
          f"  F1 {2*p*r/max(p+r,1e-12):.4f}")
