"""Per-scale decomposition of the shipped union, and the mad_k sweep."""
import sys, time, json
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
import tilebench as TB
import numpy as np

tiles = TB.load(with_raw=True)
print("CONTROLS"); assert A.selfcheck_sweep(tiles); print()

t0 = time.time()
caches = [A.scale_cache(t["img8"]) for t in tiles]
print(f"cached 7 scales x {len(tiles)} tiles in {time.time()-t0:.1f}s\n")

LAD = A.DO.SCALE_LADDER


def ev(name, mk, scales=None, absd=10, **cl):
    cs = [TB.counts(A.clean(A.union_at(c, t["img8"], mk, absd, scales), **cl), t["gt"])
          for t, c in zip(tiles, caches)]
    r = TB.evaluate(name, {"x": cs}, quiet=True)
    m = r["loso"]
    print(f"  {name:<46} P {m['precision']:.4f}  R {m['recall']:.4f}  "
          f"IoU {m['iou']:.4f}  F1 {m['f1']:.4f}")
    return cs, m


print("=== A. single scale alone (mad_k=5.0, abs=10, clean 1/3/13) ===")
for s in LAD:
    ev(f"sigma={s} only", 5.0, scales=(s,))
print()
print("=== B. leave one scale out of the union ===")
_, base = ev("FULL union (shipped)", 5.0)
for s in LAD:
    rest = tuple(x for x in LAD if x != s)
    _, m = ev(f"union minus sigma={s}", 5.0, scales=rest)
    print(f"      -> dP {m['precision']-base['precision']:+.4f}  "
          f"dR {m['recall']-base['recall']:+.4f}  dIoU {m['iou']-base['iou']:+.4f}")
print()
print("=== C. mad_k sweep on the full union ===")
for mk in (3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 15.0, 20.0):
    ev(f"union mad_k={mk}", mk)
print()
print("=== D. absolute darkness term img8<10 ===")
ev("union mad_k=5.0, abs ON  (shipped)", 5.0, absd=10)
ev("union mad_k=5.0, abs OFF", 5.0, absd=0)
