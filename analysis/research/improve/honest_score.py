"""How good is the detector on an instrument that is NOT width-gameable?

Every number quoted in this project comes from IoU or clDice, and both are now shown to be
reachable by fattening: against these labels a no-information dilation to 1.5x area moves
clDice +0.0478 on 13 of 13 specimens, and a PERFECTLY placed trace peaks at IoU 0.4993, so
IoU > 0.8 is arithmetically unreachable here no matter what model is built.

skeleton-F1 at a tolerance does not have the fault -- the same dilation moves it +0.0015.
So the question nobody has answered is simply: ON THAT INSTRUMENT, what does the shipped
detector score? If the answer is high, the detector was always better than its headline and
the metric was the problem. If it is low, the detector is genuinely mediocre. Either way it
is the number that belongs in a paper.

Reported at tau = 1, 2, 3, 5 px, with every floor and ceiling, because a tolerance forgives
gaps of about 2*tau and a loose tau would manufacture the answer.
"""
import sys
import numpy as np
from scipy import ndimage as ndi
from scipy import stats
from skimage import filters
from skimage.morphology import skeletonize

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
rng = np.random.default_rng(0)


def skelf1(pred, gt, tau=2):
    pred = np.asarray(pred, bool); gt = np.asarray(gt, bool)
    if not pred.any() or not gt.any():
        return 0.0
    sp, sg = skeletonize(pred), skeletonize(gt)
    if not sp.any() or not sg.any():
        return 0.0
    dg = ndi.distance_transform_edt(~sg); dp = ndi.distance_transform_edt(~sp)
    p = float((dg[sp] <= tau).mean()); r = float((dp[sg] <= tau).mean())
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def cand(m):
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def trace(gt, w=3):
    return ndi.binary_dilation(skeletonize(gt), ST, iterations=max(0, (w - 1) // 2))


def dilate_to(m, factor):
    """The no-information control: grow the mask until it has `factor` times the area."""
    out = m.copy(); target = m.sum() * factor
    for _ in range(60):
        if out.sum() >= target:
            break
        out = ndi.binary_dilation(out, ST)
    return out


TAUS = (1, 2, 3, 5)
tiles = TB.load()
print("CONTROLS"); assert TB.controls(); print()
ARMS = ["CURRENT MODEL (v1.49.1)", "one-line global threshold", "+ no-info dilation to 1.5x",
        "a correct 3 px trace", "a correct trace, 1 px", "mark everything",
        "random, area-matched", "the labels themselves"]
S = {a: {t: [] for t in TAUS} for a in ARMS}
for i, t in enumerate(tiles, 1):
    gt = t["gt"]; img8 = t["img8"]
    flat = D.flatten_background(img8)
    sm = filters.gaussian(flat, sigma=1.0, preserve_range=True)
    cur = cand(up.segment_dark_regions(flat, img8=img8))
    thr = cand(sm < np.percentile(sm, 100 * float(cur.mean())))
    rnd = np.zeros(gt.size, bool); rnd[rng.choice(gt.size, int(cur.sum()), replace=False)] = True
    masks = [cur, thr, dilate_to(cur, 1.5), trace(gt, 3), trace(gt, 1),
             np.ones_like(gt), rnd.reshape(gt.shape), gt]
    for a, m in zip(ARMS, masks):
        for tau in TAUS:
            S[a][tau].append(skelf1(m, gt, tau))
    print(f"  [{i:>2}/26] {t['frame'][:42]}", flush=True)

print(f"\nskeleton-F1 (median over the 26 tiles) -- width-insensitive")
print(f"  {'arm':<30} " + " ".join(f"{'tau='+str(t):>8}" for t in TAUS))
print("  " + "-" * 66)
for a in ARMS:
    print(f"  {a:<30} " + " ".join(f"{np.median(S[a][t]):8.4f}" for t in TAUS))

print(f"\n  the dilation control is the test of the instrument:")
for tau in TAUS:
    d = np.median(S["+ no-info dilation to 1.5x"][tau]) - np.median(S["CURRENT MODEL (v1.49.1)"][tau])
    print(f"    tau={tau}: adding 50% more area with no information moves it {d:+.4f}")

specs = sorted({t["specimen"] for t in tiles})
idx = {s: [i for i, t in enumerate(tiles) if t["specimen"] == s] for s in specs}
print(f"\n  per-SPECIMEN skeleton-F1 at tau=2 (median of its tiles)")
cur_s = np.array([np.median([S["CURRENT MODEL (v1.49.1)"][2][i] for i in idx[s]]) for s in specs])
thr_s = np.array([np.median([S["one-line global threshold"][2][i] for i in idx[s]]) for s in specs])
for s, a, b in sorted(zip(specs, cur_s, thr_s), key=lambda r: -r[1]):
    print(f"    {s:<20} model {a:.4f}   threshold {b:.4f}")
print(f"    {'MEDIAN of specimens':<20} model {np.median(cur_s):.4f}   threshold {np.median(thr_s):.4f}")
print(f"    paired model vs threshold: {np.median(cur_s-thr_s):+.4f}, "
      f"{int((cur_s>thr_s).sum())} up / {int((cur_s<thr_s).sum())} down, "
      f"p={stats.wilcoxon(cur_s, thr_s).pvalue:.4f}")
print(f"\n  specimens at or above 0.80: {int((cur_s>=0.8).sum())} of {len(specs)}")
