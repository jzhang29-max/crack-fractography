"""clean_mask's open/close/fill radii and the production >=40 px feature filter.

close_radius and fill_holes are ADDITIVE steps: they mark pixels that were never dark.
If those invented pixels are mostly false positives, trimming them raises precision while
removing nothing the evidence ever supported. That is the only subtraction this angle
will consider, and it still faces the paint gate.
"""
import sys, itertools
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
import tilebench as TB
import numpy as np

tiles = TB.load(with_raw=True)
caches = [A.scale_cache(t["img8"]) for t in tiles]
darks = [A.union_at(c, t["img8"], 5.0, 10) for t, c in zip(tiles, caches)]
FL = TB.FLOODED
keep25 = [i for i, t in enumerate(tiles) if t["frame"] != FL]


def line(name, cs, base=None):
    r = TB.evaluate(name, {"x": cs}, quiet=True)["loso"]
    tp = sum(c["tp"] for i, c in enumerate(cs) if i in keep25)
    fp = sum(c["fp"] for i, c in enumerate(cs) if i in keep25)
    fn = sum(c["fn"] for i, c in enumerate(cs) if i in keep25)
    p25 = tp / max(tp + fp, 1); r25 = tp / max(tp + fn, 1)
    d = ""
    if base:
        d = (f"   dP {r['precision']-base['precision']:+.4f} "
             f"dR {r['recall']-base['recall']:+.4f} dIoU {r['iou']-base['iou']:+.4f}")
    print(f"  {name:<40} P {r['precision']:.4f} R {r['recall']:.4f} IoU {r['iou']:.4f} "
          f"F1 {r['f1']:.4f} | 25t P {p25:.4f} R {r25:.4f}{d}")
    return r


def run(op, cl, ma, fill=True, af=0):
    out = []
    for d, t in zip(darks, tiles):
        m = A.clean(d, open_radius=op, close_radius=cl, min_area=ma, fill=fill)
        if af:
            m = A.area_filter(m, af)
        out.append(TB.counts(m, t["gt"]))
    return out


print("=== baseline ===")
base = line("SHIPPED open1 close3 min13 fill", run(1, 3, 13))

print("\n=== the two ADDITIVE steps, removed one at a time ===")
line("close_radius 3 -> 0", run(1, 0, 13), base)
line("fill_holes OFF", run(1, 3, 13, fill=False), base)
line("close 0 AND fill OFF", run(1, 0, 13, fill=False), base)

print("\n=== close_radius sweep ===")
for cl in (0, 1, 2, 3, 4, 5, 7):
    line(f"close_radius={cl}", run(1, cl, 13), base)

print("\n=== open_radius sweep ===")
for op in (0, 1, 2, 3):
    line(f"open_radius={op}", run(op, 3, 13), base)

print("\n=== min_area inside clean_mask ===")
for ma in (1, 13, 40, 100, 300):
    line(f"clean min_area={ma}", run(1, 3, ma), base)

print("\n=== production's extract_candidates(min_area_px=N) on top of clean(1,3,13) ===")
for af in (0, 40, 100, 300, 1000):
    line(f"feature filter >={af} px", run(1, 3, 13, af=af), base)
