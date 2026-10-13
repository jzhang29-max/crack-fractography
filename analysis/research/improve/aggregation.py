"""The same masks, the same labels, under every legitimate way of aggregating them.

Nothing below changes a single predicted pixel. The spread across these rows is larger
than the difference between any two methods tested in this project, which is why every
number must be quoted with its aggregation AND its tolerance or it means nothing.

F1 is shown twice on purpose: computed FROM the aggregated precision and recall, and as
the median of the per-unit F1s. They are not the same number and the gap is not small --
the specimens with high precision are not the ones with high recall, so combining the two
medians invents a frame that does not exist.
"""
import sys
import numpy as np
from scipy import ndimage as ndi

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R); sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP
import detect_cracks as D
import detector_overrides as DO
ST = ndi.generate_binary_structure(2, 2)


class U:
    pass


up = U(); DO.install(up)
tiles = TB.load()
print("CONTROLS"); assert TB.controls(); print()


def cand(m):
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def counts(pred, gt, tol):
    p, g = np.asarray(pred, bool), np.asarray(gt, bool)
    if tol:
        gd = ndi.binary_dilation(g, ST, iterations=tol)
        pd = ndi.binary_dilation(p, ST, iterations=tol)
        return int((p & gd).sum()), int((p & ~gd).sum()), int((~pd & g).sum())
    return int((p & g).sum()), int((p & ~g).sum()), int((~p & g).sum())


def prf(tp, fp, fn):
    p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
    return p, r, (2 * p * r / max(p + r, 1e-12)), tp / max(tp + fp + fn, 1)


preds = [cand(up.segment_dark_regions(D.flatten_background(t["img8"]), img8=t["img8"])) for t in tiles]
specs = sorted({t["specimen"] for t in tiles})
print(f"  {'aggregation':<38} {'prec':>7} {'recall':>7} {'F1*':>7} {'IoU':>7}   {'medF1':>7}")
print("  " + "-" * 82)
for tol in (0, 2):
    C = [counts(p, t["gt"], tol) for p, t in zip(preds, tiles)]
    rows = []
    # (a) pooled over every pixel in the corpus
    tp, fp, fn = (sum(c[i] for c in C) for i in range(3))
    rows.append(("pooled over all pixels", prf(tp, fp, fn), None))
    # (b) per-TILE: median of each tile's own score
    per = [prf(*c) for c in C]
    rows.append(("median over the 26 TILES", tuple(np.median([x[i] for x in per]) for i in range(4)),
                 np.median([x[2] for x in per])))
    # (c) per-SPECIMEN, each specimen pooled over its own tiles, then median
    sp = []
    for s in specs:
        idx = [i for i, t in enumerate(tiles) if t["specimen"] == s]
        sp.append(prf(*(sum(C[i][k] for i in idx) for k in range(3))))
    rows.append(("median over 13 SPECIMENS (pooled in)", tuple(np.median([x[i] for x in sp]) for i in range(4)),
                 np.median([x[2] for x in sp])))
    # (d) per-SPECIMEN as the median of its tiles' scores, then median
    sp2 = []
    for s in specs:
        idx = [i for i, t in enumerate(tiles) if t["specimen"] == s]
        sp2.append(tuple(np.median([per[i][k] for i in idx]) for k in range(4)))
    rows.append(("median over 13 SPECIMENS (median in)", tuple(np.median([x[i] for x in sp2]) for i in range(4)),
                 np.median([x[2] for x in sp2])))
    print(f"  --- {'exact (0 px tolerance)' if tol == 0 else '2 px tolerance'} ---")
    for name, v, medf1 in rows:
        star = f"{v[2]:7.4f}" if medf1 is None else f"{2*v[0]*v[1]/max(v[0]+v[1],1e-12):7.4f}"
        mf = "      -" if medf1 is None else f"{medf1:7.4f}"
        print(f"  {name:<38} {v[0]:7.4f} {v[1]:7.4f} {star} {v[3]:7.4f}   {mf}")
    print()
print("  F1* = computed FROM the precision and recall on that row.")
print("  medF1 = the median of the per-unit F1s. Where the two differ, F1* describes a")
print("  unit that does not exist, because the high-precision units are not the")
print("  high-recall ones. Quote medF1.")
