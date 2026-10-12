"""Push all three numbers, keeping the safety property that made today's change shippable.

Every arm is classified by whether it can DELETE a pixel the current build marks:

  ADDITIVE    - can only add (lower mad_k, union of scales). Cannot destroy a human label,
                so a tile score is sufficient evidence.
  SUBTRACTIVE - can remove (vote>=n, any veto, any classifier). A tile score is NOT
                sufficient: both of today's best-scoring precision rules deleted 40-43% of
                hand-marked crack on full frames, and one reproduced to the pixel the
                damage of a rule this repo already removed.

So the additive arms are measured first and can be believed; anything subtractive that
wins has to go to the paint before it means anything.
"""
import os, sys
import numpy as np
from scipy import ndimage as ndi
from skimage import filters

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R); sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP
import detect_cracks as D

SIGMAS = (5, 10, 20, 40, 80, 160, 320)
tiles = TB.load()
print("CONTROLS"); assert TB.controls(); print()

pre = []
for i, t in enumerate(tiles, 1):
    P = dict(frame=t["frame"], img8=t["img8"], gt=t["gt"], smooth={}, stat={})
    for s in SIGMAS:
        f = D.flatten_background(t["img8"], sigma=s)
        sm = filters.gaussian(f, sigma=1.0, preserve_range=True)
        med = float(np.median(sm)); mad = float(np.median(np.abs(sm - med)) * 1.4826)
        P["smooth"][s] = sm
        P["stat"][s] = dict(otsu=float(filters.threshold_otsu(sm)), med=med, mad=mad)
    pre.append(P)
    print(f"  precompute [{i:>2}/26] {t['frame'][:44]}", flush=True)

def cut(P, s, k):
    st = P["stat"][s]
    return P["smooth"][s] < min(st["otsu"], st["med"] - k * st["mad"])

def candidates(mask):
    """clean_mask then the >=40 px feature filter -- the same two stages the real path
    runs, so these masks are what detect_one.py would emit with the classifier off."""
    lab, _ = ndi.label(D.clean_mask(mask, min_area_px=13))
    out = np.zeros(lab.shape, bool)
    if lab.max():
        sizes = np.bincount(lab.ravel())
        keep = np.where(sizes >= 40)[0]
        out = np.isin(lab, keep[keep > 0])
    return out

C = lambda ms: [TB.counts(m, t["gt"]) for m, t in zip(ms, tiles)]
res = {}

res["ship v1.48 (classifier off, mad_k 5)"] = TB.evaluate(
    "ship v1.48.0  [ADDITIVE, 0 params]",
    {"x": C([candidates(cut(P, 40, 5.0) | (P["img8"] < 10)) for P in pre])})

g = {}
for k in (5.0, 4.0, 3.0, 2.5, 2.0, 1.5):
    g[f"k{k}"] = C([candidates(cut(P, 40, k) | (P["img8"] < 10)) for P in pre])
    print(f"  mad_k {k}", flush=True)
res["+ mad_k swept"] = TB.evaluate("+ mad_k swept  [ADDITIVE, 1 param]", g)

u = {}
for k in (5.0, 4.0, 3.0, 2.5):
    for nmax in (2, 3, 4, 7):
        ss = SIGMAS[:nmax] if nmax < 7 else SIGMAS
        m = [candidates(np.logical_or.reduce([cut(P, s, k) for s in ss]) | (P["img8"] < 10))
             for P in pre]
        u[f"k{k}_u{nmax}"] = C(m)
    print(f"  union k {k}", flush=True)
res["+ multi-scale UNION"] = TB.evaluate(
    "+ multi-scale UNION of scales  [ADDITIVE, 2 params]", u)

v = {}
for k in (5.0, 4.0, 3.0, 2.5, 2.0):
    for nv in (2, 3, 4):
        vv = np.zeros(1)
        m = []
        for P in pre:
            acc = np.zeros(P["img8"].shape, np.uint8)
            for s in SIGMAS:
                acc += cut(P, s, k).astype(np.uint8)
            m.append(candidates((acc >= nv) | (P["img8"] < 10)))
        v[f"k{k}_n{nv}"] = C(m)
    print(f"  vote k {k}", flush=True)
res["+ multi-scale VOTE (subtractive!)"] = TB.evaluate(
    "+ multi-scale VOTE  [SUBTRACTIVE -- needs the paint test, 2 params]", v)

print("\n" + "=" * 94)
print("HELD-OUT, leave-one-specimen-out")
print(f"  {'arm':<40} {'prec':>7} {'recall':>7} {'IoU':>7} {'F1':>7} {'gap':>8}")
for n, r in res.items():
    m = r["loso"]
    print(f"  {n:<40} {m['precision']:7.4f} {m['recall']:7.4f} {m['iou']:7.4f} {m['f1']:7.4f} "
          f"{r['overfit_gap']:+8.4f}")
import json
json.dump({k: dict(loso=v2["loso"], loso_tol2=v2["loso_tol2"], gap=v2["overfit_gap"],
                   picks=v2["picks"], per_specimen=v2["per_specimen"]) for k, v2 in res.items()},
          open(os.path.join(TB.SC, "best_additive.json"), "w"), indent=1)
