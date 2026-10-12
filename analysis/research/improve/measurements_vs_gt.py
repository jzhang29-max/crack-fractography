"""Do the MEASUREMENTS match the ground truth, not just the pixels?

IoU is a pixel-overlap score, and this project's output is not pixels -- it is area
fraction, crack width, crack length and crack count. A mask can gain IoU and still get the
numbers that go in the paper wrong, so the detector's measurements are compared directly
against the same measurements taken on the hand labels.

Length is computed as the SUM OF SKELETON EDGE LENGTHS (1 orthogonal, sqrt(2) diagonal),
not the skeleton pixel count. Counting pixels understates a diagonal run by 41% and has
previously made 54.5% of cracks in this project report a tortuosity below 1, which is
geometrically impossible.

Width is 2 x the mean Euclidean distance transform ON the skeleton -- the standard
local-thickness estimate -- rather than area/length, which conflates the two.
"""
import os, sys
import numpy as np
from scipy import ndimage as ndi
from scipy import stats
from skimage.morphology import skeletonize

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R)
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP
import detect_cracks as D
import detector_overrides as DO


class FakeUP:
    pass


up = FakeUP(); DO.install(up)

NB = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], bool)


def skeleton_length(sk):
    """Sum of edge lengths in the 8-connected skeleton graph, halved because each edge is
    counted from both ends."""
    if not sk.any():
        return 0.0
    orth = sum(int((sk & np.roll(sk, s, axis=a)).sum()) for a in (0, 1) for s in (1, -1))
    diag = 0
    for da in (1, -1):
        for db in (1, -1):
            diag += int((sk & np.roll(np.roll(sk, da, 0), db, 1)).sum())
    return (orth + diag * np.sqrt(2.0)) / 2.0


def measure(m):
    m = np.asarray(m, bool)
    if not m.any():
        return dict(area_frac=0.0, n=0, length=0.0, width=0.0)
    sk = skeletonize(m)
    dt = ndi.distance_transform_edt(m)
    lab, n = ndi.label(m, structure=NB)
    return dict(area_frac=float(m.mean()), n=int(n), length=skeleton_length(sk),
                width=float(2.0 * dt[sk].mean()) if sk.any() else 0.0)


def candidates(mask):
    lab, _ = ndi.label(D.clean_mask(mask, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); keep = np.where(sz >= 40)[0]
    return np.isin(lab, keep[keep > 0])


tiles = TB.load()
rows = []
for i, t in enumerate(tiles, 1):
    img8 = t["img8"]
    flat = D.flatten_background(img8)
    old = CP.predict(img8)                                              # v1.47 and earlier
    mid = candidates(D.segment_dark_regions(flat, img8=img8))           # v1.48
    new = candidates(up.segment_dark_regions(flat, img8=img8))          # v1.49
    rows.append(dict(frame=t["frame"], gt=measure(t["gt"]), old=measure(old),
                     mid=measure(mid), new=measure(new)))
    print(f"  [{i:>2}/26] {t['frame'][:42]}", flush=True)

print("\nMEASUREMENTS vs THE HAND LABELS, 26 tiles")
print("  'ratio' is the detector's value over the hand-labelled value; 1.000 is perfect.")
print("  'rho' is Spearman across tiles: does it RANK the tiles the way the labels do?")
print(f"\n  {'measurement':<16} {'arm':<22} {'median ratio':>13} {'IQR of ratio':>22} {'rho':>7} {'p':>9}")
print("-" * 98)
for key, nm in (("area_frac", "area fraction"), ("length", "crack length"),
                ("width", "crack width"), ("n", "crack count")):
    g = np.array([r["gt"][key] for r in rows], float)
    for arm, lab in (("old", "v1.47 shipped"), ("mid", "v1.48 no classifier"),
                     ("new", "v1.49 + multiscale")):
        v = np.array([r[arm][key] for r in rows], float)
        ok = g > 0
        ratio = np.divide(v[ok], g[ok])
        rho, p = stats.spearmanr(g[ok], v[ok])
        q1, q3 = np.percentile(ratio, [25, 75])
        print(f"  {nm if arm=='old' else '':<16} {lab:<22} {np.median(ratio):13.3f} "
              f"{'[' + format(q1, '.3f') + ', ' + format(q3, '.3f') + ']':>22} {rho:7.3f} {p:9.2g}")
    print()
print("POOLED TOTALS (what a corpus-level number in a paper would be)")
print(f"  {'measurement':<16} {'hand labels':>14} {'v1.47':>12} {'v1.48':>12} {'v1.49':>12}")
for key, nm in (("area_frac", "area fraction"), ("length", "total length px"), ("n", "crack count")):
    g = sum(r["gt"][key] for r in rows)
    vals = [sum(r[a][key] for r in rows) for a in ("old", "mid", "new")]
    f = (lambda x: f"{x:.5f}") if key == "area_frac" else (lambda x: f"{x:,.0f}")
    print(f"  {nm:<16} {f(g):>14} " + " ".join(f"{f(v):>12}" for v in vals))
