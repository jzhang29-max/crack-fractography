"""Your detector against the classical baselines, on the SAME public images.

Published numbers from papers are not a comparison -- different splits, different
tolerances, different pre-processing. These arms are all run here, on the same images,
scored by the same function, at 0 px tolerance.

Each parameterised baseline is given the same courtesy your detector gets: its parameter
is chosen leave-one-IMAGE-out on that dataset, so nothing is fitted on the image it is
scored on and no arm is handicapped relative to another.
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
from skimage import filters, measure as skm
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None
SCR = os.environ["SCR"]


class U:
    pass


u = U(); DO.install(u)


def clean(m):
    lab = skm.label(D.clean_mask(m, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def f1(p, g):
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return 2 * pr * rc / max(pr + rc, 1e-12)


# every arm is (name, list of parameter values, predictor) so all are LOO-selected alike
def ridge(img8, sigmas, q, which):
    f = {"frangi": filters.frangi, "sato": filters.sato,
         "meijering": filters.meijering}[which]
    r = f(img8.astype(float), sigmas=sigmas, black_ridges=True)
    return clean(r >= np.percentile(r, 100 - q))


ARMS = [
    ("YOUR DETECTOR (v1.49.2)", [5.0, 4.0, 3.0, 2.5, 2.0, 1.5],
     lambda im, k: clean(u.segment_dark_regions(D.flatten_background(im), img8=im, mad_k=k))),
    ("global threshold (Otsu on flat)", [0.0],
     lambda im, _: clean(filters.gaussian(D.flatten_background(im), 1, preserve_range=True)
                         < filters.threshold_otsu(
                             filters.gaussian(D.flatten_background(im), 1, preserve_range=True)))),
    ("percentile threshold", [0.5, 1, 2, 4, 8],
     lambda im, q: clean(im <= np.percentile(im, q))),
    ("Sauvola local", [15, 25, 51, 101],
     lambda im, w: clean(im < filters.threshold_sauvola(im, window_size=w))),
    ("Frangi ridge", [0.5, 1, 2, 4, 8],
     lambda im, q: ridge(im, range(1, 5), q, "frangi")),
    ("Sato ridge", [0.5, 1, 2, 4, 8],
     lambda im, q: ridge(im, range(1, 5), q, "sato")),
    ("Meijering ridge", [0.5, 1, 2, 4, 8],
     lambda im, q: ridge(im, range(1, 5), q, "meijering")),
]


def loo(scores_by_param, N):
    """Pick the parameter on the other N-1 images, score on this one."""
    ps = list(scores_by_param)
    out = []
    for i in range(N):
        best = max(ps, key=lambda p: np.mean([scores_by_param[p][j] for j in range(N) if j != i]))
        out.append(scores_by_param[best][i])
    return float(np.mean(out))


def load_cfd(limit):
    d = f"{SCR}/pub_cfd/CrackForest-dataset-master"
    out = []
    for n in sorted(x[:-4] for x in os.listdir(d + "/groundTruth") if x.endswith(".mat")):
        ip = f"{d}/image/{n}.jpg"
        if not os.path.exists(ip):
            continue
        gt = np.array(sio.loadmat(f"{d}/groundTruth/{n}.mat")
                      ["groundTruth"][0, 0]["Segmentation"]) == 2
        if gt.sum() > 50:
            out.append((np.array(Image.open(ip).convert("L")), gt))
        if len(out) >= limit:
            break
    return out


def load_dc(limit):
    d = f"{SCR}/pub_deepcrack/DeepCrack-master/dataset"
    out = []
    for f in sorted(os.listdir(d + "/test_img")):
        gp = f"{d}/test_lab/{os.path.splitext(f)[0]}.png"
        if not os.path.exists(gp):
            continue
        gt = np.array(Image.open(gp).convert("L")) > 127
        if gt.sum() > 50:
            out.append((np.array(Image.open(f"{d}/test_img/{f}").convert("L")), gt))
        if len(out) >= limit:
            break
    return out


RES = {}
for dsname, loader, lim in (("CrackForest", load_cfd, 118), ("DeepCrack", load_dc, 120)):
    data = loader(lim)
    print(f"\n{dsname}: {len(data)} images")
    RES[dsname] = {}
    for name, params, fn in ARMS:
        by = {p: [] for p in params}
        for im, gt in data:
            for p in params:
                try:
                    by[p].append(f1(fn(im, p), gt))
                except Exception:
                    by[p].append(0.0)
        v = loo(by, len(data)) if len(params) > 1 else float(np.mean(by[params[0]]))
        RES[dsname][name] = v
        print(f"   {name:<32} {v:.4f}", flush=True)

print("\n" + "=" * 72)
print("MEAN F1 PER IMAGE, 0 px tolerance, parameter chosen leave-one-IMAGE-out")
print(f"  {'arm':<34} {'CrackForest':>12} {'DeepCrack':>11}")
for name, _, _ in ARMS:
    print(f"  {name:<34} {RES['CrackForest'][name]:12.4f} {RES['DeepCrack'][name]:11.4f}")
json.dump(RES, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "baselines.json"), "w"), indent=1)
