"""The U-Net judged on the metrics it was never judged on.

It was built and scored under an instruction of mine to optimise clDice, and its decision
threshold was picked to maximise clDice. On clDice it ties. On IoU, F1 and precision the
cached held-out predictions say it is clearly ahead, and nobody ran those paired tests or
re-picked the operating point for them. This does both.

Threshold selection stays NESTED: for specimen s, tau is chosen on the held-out predictions
of the other 12 specimens, so no tile's threshold ever saw its own score.

Also sweeps evaluation tolerance, because the crack literature reports tolerant scores
(CrackForest F1 75.35 at 0 px vs 97.10 at 2 px) and the honest question "can these numbers
reach 0.8" cannot be answered without saying at what tolerance.
"""
import sys
import numpy as np
from scipy import ndimage as ndi
from scipy import stats

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R); sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP
import detect_cracks as D
import detector_overrides as DO

SC = "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad"
ST = ndi.generate_binary_structure(2, 2)


class U:
    pass


up = U(); DO.install(up)
tiles = TB.load()
print("CONTROLS"); assert TB.controls()
prob = np.load(f"{SC}/scl/prob_main_thin4.npy")
print(f"cached held-out probabilities: {prob.shape} {prob.dtype}\n")
assert prob.shape[0] == len(tiles)
gts = [t["gt"] for t in tiles]
specs = [t["specimen"] for t in tiles]
uspec = sorted(set(specs))


def cand(m):
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


ship = [cand(up.segment_dark_regions(D.flatten_background(t["img8"]), img8=t["img8"]))
        for t in tiles]


def score(pred, gt, tol=0):
    p, g = np.asarray(pred, bool), np.asarray(gt, bool)
    if tol:
        gd = ndi.binary_dilation(g, ST, iterations=tol)
        pd = ndi.binary_dilation(p, ST, iterations=tol)
        tp = int((p & gd).sum()); fp = int((p & ~gd).sum()); fn = int((~pd & g).sum())
    else:
        tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return dict(precision=pr, recall=rc, iou=tp / max(tp + fp + fn, 1),
                f1=2 * pr * rc / max(pr + rc, 1e-12))


TAUS = np.round(np.arange(0.10, 0.95, 0.05), 2)


def nested(metric, tol=0):
    """Per specimen: pick tau on the OTHER specimens, apply to this one."""
    cache = {}
    for tau in TAUS:
        cache[tau] = [score(prob[i] >= tau, gts[i], tol) for i in range(len(tiles))]
    out = []
    picks = []
    for s in uspec:
        tr = [i for i in range(len(tiles)) if specs[i] != s]
        te = [i for i in range(len(tiles)) if specs[i] == s]
        best = max(TAUS, key=lambda tau: np.median([cache[tau][i][metric] for i in tr]))
        picks.append(best)
        out.append(np.median([cache[best][i][metric] for i in te]))
    return np.array(out), picks


print(f"{'':<34} {'prec':>7} {'recall':>7} {'F1':>7} {'IoU':>7}")
for tol in (0, 2):
    lab = "" if tol == 0 else f", {tol} px tolerance"
    sh = [score(ship[i], gts[i], tol) for i in range(len(tiles))]
    for m in ("precision", "recall", "f1", "iou"):
        pass
    shm = {k: np.median([x[k] for x in sh]) for k in ("precision", "recall", "f1", "iou")}
    print(f"  {'SHIPPED v1.49.1' + lab:<32} " + " ".join(f"{shm[k]:7.4f}" for k in ("precision", "recall", "f1", "iou")))
    for sel in ("iou", "f1"):
        vals, picks = nested(sel, tol)
        # recompute all four metrics at the per-specimen chosen tau
        allm = {k: [] for k in ("precision", "recall", "f1", "iou")}
        for s, tau in zip(uspec, picks):
            te = [i for i in range(len(tiles)) if specs[i] == s]
            for k in allm:
                allm[k].append(np.median([score(prob[i] >= tau, gts[i], tol)[k] for i in te]))
        print(f"  {'U-Net, tau picked for ' + sel.upper() + lab:<32} "
              + " ".join(f"{np.median(allm[k]):7.4f}" for k in ("precision", "recall", "f1", "iou")))
    print()

print("PAIRED across the 13 specimens, U-Net (tau picked for IoU) vs shipped")
_, picks = nested("iou", 0)
for k in ("precision", "recall", "f1", "iou"):
    a, b = [], []
    for s, tau in zip(uspec, picks):
        te = [i for i in range(len(tiles)) if specs[i] == s]
        a.append(np.median([score(ship[i], gts[i])[k] for i in te]))
        b.append(np.median([score(prob[i] >= tau, gts[i])[k] for i in te]))
    a, b = np.array(a), np.array(b)
    print(f"  {k:<10} shipped {np.median(a):.4f} -> U-Net {np.median(b):.4f}   "
          f"median delta {np.median(b-a):+.4f}  {int((b>a).sum())} up / {int((b<a).sum())} down  "
          f"p={stats.wilcoxon(a,b).pvalue:.4f}")

print("\nWHAT TOLERANCE WOULD BE NEEDED TO REACH 0.8?  (U-Net, tau picked for F1)")
print(f"  {'tol px':>7} {'prec':>8} {'recall':>8} {'F1':>8} {'IoU':>8}")
for tol in (0, 1, 2, 3, 4, 6, 8, 12):
    _, pk = nested("f1", tol)
    allm = {k: [] for k in ("precision", "recall", "f1", "iou")}
    for s, tau in zip(uspec, pk):
        te = [i for i in range(len(tiles)) if specs[i] == s]
        for k in allm:
            allm[k].append(np.median([score(prob[i] >= tau, gts[i], tol)[k] for i in te]))
    print(f"  {tol:>7} " + " ".join(f"{np.median(allm[k]):8.4f}" for k in ("precision", "recall", "f1", "iou")))
