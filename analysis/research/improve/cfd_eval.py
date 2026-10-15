"""v1.49.2 on CrackForest, frozen -- no parameter fitted on this dataset.

The last time this project met a public benchmark the SHIPPED detector scored F1 0.0000:
mad_k=5.0 is a five-MAD outlier test, and on a low-contrast road photo it flagged 0.10% of
the image against a 1.30% label. Two things have changed since, and both target exactly
that failure -- the darkness cut is now unioned over seven flattening radii, and the region
classifier (which rejected thin cracks, because it was fitted on broad-brush labels and had
learned that a crack is broad) is switched off.

So this is a real question, not a formality. Frozen means frozen: every constant is the one
the app ships, nothing is selected on CrackForest.

Reported at 0 px and at 2 px tolerance because the literature reports both and they differ
by ~22 F1 points on this very dataset (Kompanets 2024: 75.35 at 0 px, 97.10 at 2 px).
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
from skimage.morphology import skeletonize
from PIL import Image
import detect_cracks as D
import detector_overrides as DO

DATA = sys.argv[1]
ST = ndi.generate_binary_structure(2, 2)


def arm(multi=True):
    """install() with multiscale off and no constant override installs NOTHING -- its
    second branch only fires when a mad_k/absolute_dark_thresh is being passed. So the
    single-scale arm is the stock archived function, which is exactly what v1.47 ran."""
    class U:
        pass
    u = U()
    DO.install(u, use_multiscale_union=multi)
    if not hasattr(u, "segment_dark_regions"):
        u.segment_dark_regions = D.segment_dark_regions
    return u


U_NEW = arm(True)
U_OLD = arm(False)
assert U_NEW.segment_dark_regions is not D.segment_dark_regions, "multiscale not installed"
assert U_OLD.segment_dark_regions is D.segment_dark_regions, "single-scale arm is not stock"


def emit(u, img8, classifier=False):
    raw = u.segment_dark_regions(D.flatten_background(img8), img8=img8)
    clean = D.clean_mask(raw, min_area_px=13)
    lab = skm.label(clean, connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    keep = np.isin(lab, k[k > 0])
    if not classifier:
        return keep
    import joblib
    B = joblib.load(os.path.join(SEM, "models", "crack_classifier.joblib"))
    ves = D.compute_vesselness(D.flatten_background(img8))
    l2, df = D.region_features_from_labeled(ndi.label(clean)[0], D.flatten_background(img8), ves)
    if not len(df):
        return np.zeros(lab.shape, bool)
    p = B["clf"].predict_proba(B["scaler"].transform(df[B["feature_names"]].values))[:, 1]
    pm = np.zeros(int(l2.max()) + 1, np.float32)
    for l, v in zip(df["Label"].values, p):
        pm[int(l)] = v
    return (pm[l2] >= B["threshold"]) & (l2 > 0)


def sc(pred, gt, tol=0):
    p, g = np.asarray(pred, bool), np.asarray(gt, bool)
    if tol:
        gd = ndi.binary_dilation(g, ST, iterations=tol); pd = ndi.binary_dilation(p, ST, iterations=tol)
        tp, fp, fn = int((p & gd).sum()), int((p & ~gd).sum()), int((~pd & g).sum())
    else:
        tp, fp, fn = int((p & g).sum()), int((p & ~g).sum()), int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return dict(p=pr, r=rc, f1=2 * pr * rc / max(pr + rc, 1e-12), iou=tp / max(tp + fp + fn, 1))


names = sorted(f[:-4] for f in os.listdir(os.path.join(DATA, "groundTruth")) if f.endswith(".mat"))
print(f"{len(names)} CrackForest images with pixel ground truth\n")
ARMS = ["v1.49.2 FROZEN (ships)", "v1.47 single scale + classifier", "mark everything",
        "random, area-matched"]
R = {a: {0: [], 2: []} for a in ARMS}
rng = np.random.default_rng(0)
prev = []
for i, n in enumerate(names, 1):
    ip = os.path.join(DATA, "image", n + ".jpg")
    if not os.path.exists(ip):
        continue
    img8 = np.array(Image.open(ip).convert("L"))
    seg = np.array(sio.loadmat(os.path.join(DATA, "groundTruth", n + ".mat"))
                   ["groundTruth"][0, 0]["Segmentation"])
    gt = seg == 2
    if gt.sum() < 50:
        continue
    prev.append(gt.mean())
    new = emit(U_NEW, img8); old = emit(U_OLD, img8, classifier=True)
    rnd = np.zeros(gt.size, bool)
    rnd[rng.choice(gt.size, max(int(new.sum()), 1), replace=False)] = True
    for a, m in zip(ARMS, [new, old, np.ones_like(gt), rnd.reshape(gt.shape)]):
        for tol in (0, 2):
            R[a][tol].append(sc(m, gt, tol))
    if i % 20 == 0:
        print(f"  [{i}/{len(names)}] {n}  marked {100*new.mean():.2f}%  gt {100*gt.mean():.2f}%", flush=True)

n = len(R[ARMS[0]][0])
print(f"\nCRACKFOREST, {n} images, crack prevalence {100*np.mean(prev):.2f}% of pixels")
for tol in (0, 2):
    print(f"\n  --- {tol} px tolerance ---")
    print(f"  {'arm':<34} {'prec':>7} {'recall':>7} {'F1':>7} {'IoU':>7}")
    for a in ARMS:
        v = R[a][tol]
        print(f"  {a:<34} " + " ".join(f"{np.median([x[k] for x in v]):7.4f}"
                                       for k in ("p", "r", "f1", "iou")))
print("\n  published reference on CrackForest: F1 75.35 at 0 px, 97.10 at 2 px")
print("  (Kompanets 2024, a model TRAINED on this dataset; both arms above are frozen)")
json.dump({a: {str(t): R[a][t] for t in (0, 2)} for a in ARMS},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cfd.json"), "w"))
