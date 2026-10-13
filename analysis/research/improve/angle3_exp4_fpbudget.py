"""Where does the tile false-positive budget actually live? Precision cannot be a target
until this is known, because a pooled precision is whatever its biggest tile says."""
import sys
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
import tilebench as TB
import numpy as np
from scipy import ndimage as ndi

tiles = TB.load(with_raw=True)
caches = [A.scale_cache(t["img8"]) for t in tiles]


def shipped(t, c, absd=10):
    m = A.clean(A.union_at(c, t["img8"], 5.0, absd), open_radius=1, close_radius=3, min_area=13)
    return A.area_filter(m, 40)


ms = [shipped(t, c) for t, c in zip(tiles, caches)]
fps = [int((m & ~t["gt"]).sum()) for m, t in zip(ms, tiles)]
tot = sum(fps)
print(f"total FP over 26 tiles: {tot:,}   total TP: {sum(int((m & t['gt']).sum()) for m, t in zip(ms, tiles)):,}")
order = np.argsort(fps)[::-1]
cum = 0
print(f"\n  {'rank':>4} {'tile':<46} {'FP':>10} {'% of all FP':>11} {'cum %':>7}")
for r, i in enumerate(order[:8], 1):
    cum += fps[i]
    print(f"  {r:>4} {tiles[i]['frame'][:45]:<46} {fps[i]:>10,} {100*fps[i]/tot:>10.1f}% "
          f"{100*cum/tot:>6.1f}%")

print("\n=== how much FP does each TERM contribute (pixels only that term proposes)? ===")
rob = [A.clean(A.union_at(c, t["img8"], 5.0, 0), 1, 3, 13) for t, c in zip(tiles, caches)]
rob = [A.area_filter(m, 40) for m in rob]
abs_only_fp = sum(int(((m & ~r) & ~t["gt"]).sum()) for m, r, t in zip(ms, rob, tiles))
abs_only_tp = sum(int(((m & ~r) & t["gt"]).sum()) for m, r, t in zip(ms, rob, tiles))
print(f"  pixels the absolute term img8<10 adds on top of the robust union:")
print(f"     FP {abs_only_fp:,}  ({100*abs_only_fp/tot:.1f}% of all FP)   TP {abs_only_tp:,}")

print("\n=== FP by connected-component size in the shipped mask ===")
bins = [(0, 100), (100, 1000), (1000, 10000), (10000, 100000), (100000, 10**12)]
acc = {b: [0, 0, 0] for b in bins}
for m, t in zip(ms, tiles):
    lab, n = ndi.label(m)
    if not n:
        continue
    sz = np.bincount(lab.ravel())
    tpc = np.bincount(lab[t["gt"]].ravel(), minlength=len(sz))
    for l in range(1, n + 1):
        for b in bins:
            if b[0] <= sz[l] < b[1]:
                acc[b][0] += 1; acc[b][1] += int(tpc[l]); acc[b][2] += int(sz[l] - tpc[l])
                break
print(f"  {'size band':<22} {'regions':>8} {'TP px':>12} {'FP px':>12} {'purity':>8}")
for b in bins:
    n, tp, fp = acc[b]
    print(f"  {str(b):<22} {n:>8} {tp:>12,} {fp:>12,} {tp/max(tp+fp,1):>8.3f}")
