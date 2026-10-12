"""The union family in detail: which setting is best on all three numbers at once?

Union is additive by construction -- it can only add scales to the single-scale cut -- and
that was confirmed on full frames: 0 hand-marked pixels deleted across 5.77M. So unlike
every subtractive arm, a tile score here is sufficient evidence and the choice is just
where on the precision/recall curve to sit.
"""
import os, sys
import numpy as np
from scipy import ndimage as ndi
from skimage import filters

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R); sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP  # crackpipe puts the detector on sys.path
import detect_cracks as D

SIGMAS = (5, 10, 20, 40, 80, 160, 320)
tiles = TB.load()
pre = []
for t in tiles:
    P = dict(img8=t["img8"], smooth={}, stat={})
    for s in SIGMAS:
        f = D.flatten_background(t["img8"], sigma=s)
        g = filters.gaussian(f, sigma=1.0, preserve_range=True)
        med = float(np.median(g)); mad = float(np.median(np.abs(g - med)) * 1.4826)
        P["smooth"][s] = g
        P["stat"][s] = dict(otsu=float(filters.threshold_otsu(g)), med=med, mad=mad)
    pre.append(P)
print("precomputed", flush=True)


def cut(P, s, k):
    st = P["stat"][s]
    return P["smooth"][s] < min(st["otsu"], st["med"] - k * st["mad"])


def candidates(mask):
    lab, _ = ndi.label(D.clean_mask(mask, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); keep = np.where(sz >= 40)[0]
    return np.isin(lab, keep[keep > 0])


keep25 = [i for i, t in enumerate(tiles) if t["frame"] != TB.FLOODED]
print(f"\n{'variant':<16} {'prec':>7} {'recall':>7} {'IoU':>7} {'F1':>7} |"
      f" {'P(25)':>7} {'R(25)':>7} {'IoU(25)':>8} {'F1(25)':>7} | {'addsOK':>7}")
print("-" * 104)
base = [candidates(cut(P, 40, 5.0) | (P["img8"] < 10)) for P in pre]
rows_all = {}
for k in (5.0, 4.5, 4.0, 3.5, 3.0):
    for nmax in (3, 5, 7):
        ss = SIGMAS[:nmax]
        ms = [candidates(np.logical_or.reduce([cut(P, s, k) for s in ss]) | (P["img8"] < 10))
              for P in pre]
        r = [TB.counts(m, t["gt"]) for m, t in zip(ms, tiles)]
        rows_all[f"k{k}_u{nmax}"] = r
        a, b = TB._agg(r), TB._agg([r[i] for i in keep25])
        lost = sum(int((s0 & ~m).sum()) for s0, m in zip(base, ms))
        print(f"  k{k}_u{nmax:<9} {a['precision']:7.4f} {a['recall']:7.4f} {a['iou']:7.4f} {a['f1']:7.4f} |"
              f" {b['precision']:7.4f} {b['recall']:7.4f} {b['iou']:8.4f} {b['f1']:7.4f} | {lost:>7}",
              flush=True)
rs = [TB.counts(m, t["gt"]) for m, t in zip(base, tiles)]
a, b = TB._agg(rs), TB._agg([rs[i] for i in keep25])
print("-" * 104)
print(f"  {'SHIPPED v1.48':<14} {a['precision']:7.4f} {a['recall']:7.4f} {a['iou']:7.4f} {a['f1']:7.4f} |"
      f" {b['precision']:7.4f} {b['recall']:7.4f} {b['iou']:8.4f} {b['f1']:7.4f} |       0")
print("\n('addsOK' = pixels the shipped build marks that this does NOT. Must be 0 to be additive.)")
for crit in ("iou", "f1"):
    TB.evaluate(f"union family, selected by {crit.upper()}", rows_all, criterion=crit)
