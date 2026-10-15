"""Frozen fails on CrackForest. What does ONE refitted constant buy?

Frozen, v1.49.2 produces no overlap at all on 60% of the images and a mean F1 of 0.0868.
mad_k is a five-MAD outlier test calibrated to SEM steel; on a low-contrast road photo it
demands a darkness that is simply not there. Every published arm on this dataset is allowed
to fit its parameters to it, so the fair comparison is: give this one the same courtesy and
nothing more.

Selection is leave-one-IMAGE-out so the quoted number is not fitted on itself.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
import scipy.io as sio
from scipy import ndimage as ndi
from skimage import measure as skm
from PIL import Image
import detect_cracks as D
import detector_overrides as DO

DATA = sys.argv[1]


class U:
    pass


u = U(); DO.install(u)
KS = [5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5]


def emit(img8, k, min_area=13, floor=40):
    raw = u.segment_dark_regions(D.flatten_background(img8), img8=img8, mad_k=k)
    lab = skm.label(D.clean_mask(raw, min_area_px=min_area), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); kk = np.where(sz >= floor)[0]
    return np.isin(lab, kk[kk > 0])


def f1(p, g):
    tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return 2 * pr * rc / max(pr + rc, 1e-12)


names = sorted(f[:-4] for f in os.listdir(os.path.join(DATA, "groundTruth")) if f.endswith(".mat"))
cache = {k: [] for k in KS}
for i, n in enumerate(names, 1):
    ip = os.path.join(DATA, "image", n + ".jpg")
    if not os.path.exists(ip):
        continue
    img8 = np.array(Image.open(ip).convert("L"))
    gt = np.array(sio.loadmat(os.path.join(DATA, "groundTruth", n + ".mat"))
                  ["groundTruth"][0, 0]["Segmentation"]) == 2
    if gt.sum() < 50:
        continue
    for k in KS:
        cache[k].append(f1(emit(img8, k), gt))
    if i % 30 == 0:
        print(f"  [{i}/{len(names)}]", flush=True)

N = len(cache[KS[0]])
print(f"\nCRACKFOREST, {N} images -- one constant swept, everything else frozen")
print(f"  {'mad_k':>6} {'mean F1':>9} {'median':>9} {'images with F1=0':>18}")
for k in KS:
    v = np.array(cache[k])
    print(f"  {k:>6} {v.mean():9.4f} {np.median(v):9.4f} {int((v == 0).sum()):>14} / {N}")
loo = []
for i in range(N):
    best = max(KS, key=lambda k: np.mean([cache[k][j] for j in range(N) if j != i]))
    loo.append(cache[best][i])
loo = np.array(loo)
print(f"\n  leave-one-IMAGE-out (the honest adapted number): mean F1 {loo.mean():.4f}, "
      f"median {np.median(loo):.4f}")
print(f"  frozen at the shipped mad_k=5.0:                  mean F1 {np.mean(cache[5.0]):.4f}")
print(f"  published, a model TRAINED on this dataset:       F1 0.7535 at 0 px tolerance")
json.dump({str(k): cache[k] for k in KS} | {"loo": loo.tolist()},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfd_sweep.json"), "w"))
