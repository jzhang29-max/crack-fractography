"""The whole candidate-stage knob family, selected leave-one-SPECIMEN-out.

If the gap between fitted and held-out eats the gain, the family is not a lever.
"""
import sys, itertools, json
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
import tilebench as TB
import numpy as np

tiles = TB.load(with_raw=True)
caches = [A.scale_cache(t["img8"]) for t in tiles]
FL = TB.FLOODED
keep25 = [i for i, t in enumerate(tiles) if t["frame"] != FL]

SHIP = (5.0, 10, 1, 3, 13, 40)
grid = {}
for mk in (4.0, 5.0, 6.0):
    for absd in (0, 10):
        for op in (1, 2):
            for cl in (3, 5):
                for af in (40, 100):
                    grid[(mk, absd, op, cl, 13, af)] = None
grid[SHIP] = None

print(f"{len(grid)} variants x {len(tiles)} tiles")
for k in list(grid):
    mk, absd, op, cl, ma, af = k
    cs = []
    for t, c in zip(tiles, caches):
        m = A.clean(A.union_at(c, t["img8"], mk, absd), open_radius=op, close_radius=cl,
                    min_area=ma)
        cs.append(TB.counts(A.area_filter(m, af), t["gt"]))
    grid[k] = cs

base = TB.evaluate("shipped", {"x": grid[SHIP]}, quiet=True)["loso"]
print(f"\nSHIPPED {SHIP}: P {base['precision']:.4f} R {base['recall']:.4f} "
      f"IoU {base['iou']:.4f} F1 {base['f1']:.4f}")

print("\n=== top 10 variants by POOLED (fitted) precision -- optimistic, do not quote ===")
rk = sorted(grid, key=lambda k: TB.evaluate("x", {"x": grid[k]}, quiet=True)["loso"]["precision"],
            reverse=True)
for k in rk[:10]:
    m = TB.evaluate("x", {"x": grid[k]}, quiet=True)["loso"]
    print(f"  {str(k):<32} P {m['precision']:.4f} R {m['recall']:.4f} IoU {m['iou']:.4f} "
          f"F1 {m['f1']:.4f}")

print("\n=== HELD-OUT selection over the whole family (this is the number) ===")
for crit in ("iou", "f1", "precision"):
    TB.evaluate(f"candidate-stage knob family [{crit}]", grid, criterion=crit)

print("\n=== best variant that does NOT lose recall vs shipped, by precision ===")
cand = []
for k in grid:
    m = TB.evaluate("x", {"x": grid[k]}, quiet=True)["loso"]
    if m["recall"] >= base["recall"] - 0.005:
        cand.append((m["precision"], k, m))
for p, k, m in sorted(cand, reverse=True)[:5]:
    print(f"  {str(k):<32} P {m['precision']:.4f} R {m['recall']:.4f} IoU {m['iou']:.4f}")
json.dump({str(k): v for k, v in grid.items()}, open(A.WORK + "/grid.json", "w"))
