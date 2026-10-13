"""Do the scored masks equal what the APP actually produces?

Production calls extract_candidates, which labels with measure.label(connectivity=2) --
8-connected. Every score in this project used ndi.label's DEFAULT structure, which is
4-connected, so two pixels touching only at a corner become separate components and each
is then measured against the >=40 px filter on its own. A thin diagonal crack is exactly
the shape that breaks into corner-touching pieces, so this is not a rounding difference.

If they differ, every number quoted so far describes a mask the app does not emit.
"""
import sys
import numpy as np
from scipy import ndimage as ndi
from skimage import measure as skm

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


def scored(mask):
    """What every score in this project used: ndi.label default = 4-connected."""
    lab, _ = ndi.label(D.clean_mask(mask, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def production(mask):
    """What the app emits: extract_candidates -> measure.label(connectivity=2), >=40 px,
    and with the classifier off detect_one keeps EVERY surviving label."""
    clean = D.clean_mask(mask, min_area_px=13)
    lab = skm.label(clean, connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def prf(tp, fp, fn):
    p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
    return p, r, 2 * p * r / max(p + r, 1e-12), tp / max(tp + fp + fn, 1)


def counts(pred, gt, tol=0):
    p, g = np.asarray(pred, bool), np.asarray(gt, bool)
    if tol:
        gd = ndi.binary_dilation(g, ST, iterations=tol); pd = ndi.binary_dilation(p, ST, iterations=tol)
        return int((p & gd).sum()), int((p & ~gd).sum()), int((~pd & g).sum())
    return int((p & g).sum()), int((p & ~g).sum()), int((~p & g).sum())


tiles = TB.load()
print("CONTROLS"); assert TB.controls(); print()
diff_px = extra = 0
CS, CP_ = [], []
for i, t in enumerate(tiles, 1):
    raw = up.segment_dark_regions(D.flatten_background(t["img8"]), img8=t["img8"])
    a, b = scored(raw), production(raw)
    diff_px += int((a ^ b).sum()); extra += int((b & ~a).sum())
    CS.append(counts(a, t["gt"])); CP_.append(counts(b, t["gt"]))
    if (a ^ b).any():
        print(f"  [{i:>2}] {t['frame'][:40]:<42} differ {int((a^b).sum()):>6} px "
              f"(production keeps {int((b&~a).sum()):>6} more)", flush=True)

print(f"\n  total pixels where the scored mask != the app's mask: {diff_px:,}")
print(f"  of which the app KEEPS and the scoring dropped:        {extra:,}")
specs = sorted({t["specimen"] for t in tiles})
print(f"\n  {'':<34} {'prec':>7} {'recall':>7} {'F1':>7} {'IoU':>7}")
for nm, C in (("as scored all week (4-connected)", CS), ("AS THE APP EMITS (8-connected)", CP_)):
    for tol in (0, 2):
        Ct = [counts(scored(up.segment_dark_regions(D.flatten_background(t["img8"]), img8=t["img8"]))
                     if nm.startswith("as scored") else
                     production(up.segment_dark_regions(D.flatten_background(t["img8"]), img8=t["img8"])),
                     t["gt"], tol) for t in tiles]
        per = [prf(*c) for c in Ct]
        med = tuple(np.median([x[k] for x in per]) for k in range(4))
        lab = nm + ("" if tol == 0 else ", 2 px tol")
        print(f"  {lab:<34} " + " ".join(f"{med[k]:7.4f}" for k in range(4)))
