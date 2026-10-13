"""Headline tile table, with the production-identical 8-connected feature filter."""
import sys
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
import tilebench as TB
import numpy as np

tiles = TB.load(with_raw=True)
print("CONTROLS"); assert A.selfcheck(); print()
caches = [A.scale_cache(t["img8"]) for t in tiles]
FL = TB.FLOODED
k25 = [i for i, t in enumerate(tiles) if t["frame"] != FL]


def build(mk=5.0, absd=10, op=1, cl=3, ma=13, af=40):
    return [A.area_filter(A.clean(A.union_at(c, t["img8"], mk, absd), op, cl, ma), af)
            for t, c in zip(tiles, caches)]


def row(name, **kw):
    ms = build(**kw)
    cs = [TB.counts(m, t["gt"]) for m, t in zip(ms, tiles)]
    m = TB.evaluate("x", {"x": cs}, quiet=True)["loso"]
    tp = sum(cs[i]["tp"] for i in k25); fp = sum(cs[i]["fp"] for i in k25)
    fn = sum(cs[i]["fn"] for i in k25)
    p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
    print(f"  {name:<40} {m['precision']:8.4f} {m['recall']:7.4f} {m['iou']:7.4f} "
          f"{m['f1']:7.4f} | {p:7.4f} {r:7.4f} {tp/max(tp+fp+fn,1):7.4f}")
    return cs


print(f"  {'variant':<40} {'P':>8} {'R':>7} {'IoU':>7} {'F1':>7} |"
      f" {'P25':>7} {'R25':>7} {'IoU25':>7}")
ship = row("SHIPPED v1.49.1")
row("absolute term OFF")                      if 0 else row("absolute term OFF", absd=0)
row("feature filter >=100", af=100)
row("open_radius 2", op=2)
row("grid winner (4.0, abs off, 2, 5, 100)", mk=4.0, absd=0, op=2, cl=5, af=100)
print("\n  (P25/R25/IoU25 exclude the one off-specimen void tile, which owns 80.3% of all"
      "\n   false-positive pixels at the shipped settings.)")
