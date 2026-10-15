"""v1.49.2 across public crack datasets: frozen, at CrackForest's fitted k, and swept.

THE POINT IS WHETHER A FITTED CONSTANT TRANSFERS. mad_k=2.5 was selected on CrackForest.
Carrying it to another dataset asks whether "refit per corpus" means one refit or one per
corpus -- and those imply very different things about the method.

Three arms per dataset, plus the floors:
    k=5.0   what the app ships, calibrated on SEM steel
    k=2.5   CrackForest's fitted value, applied blind here
    swept   leave-one-IMAGE-out over k, this dataset's own best, the fair upper bound
Nothing else is touched: ladder, cleaning, area floor and the classifier-off decision are
all as shipped.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from skimage import measure as skm
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None


class U:
    pass


u = U(); DO.install(u)
KS = [5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0]
ST = ndi.generate_binary_structure(2, 2)


def emit(img8, k):
    raw = u.segment_dark_regions(D.flatten_background(img8), img8=img8, mad_k=k)
    lab = skm.label(D.clean_mask(raw, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); kk = np.where(sz >= 40)[0]
    return np.isin(lab, kk[kk > 0])


def sc(p, g, tol=0):
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    if tol:
        gd = ndi.binary_dilation(g, ST, iterations=tol); pd = ndi.binary_dilation(p, ST, iterations=tol)
        tp, fp, fn = int((p & gd).sum()), int((p & ~gd).sum()), int((~pd & g).sum())
    else:
        tp, fp, fn = int((p & g).sum()), int((p & ~g).sum()), int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return 2 * pr * rc / max(pr + rc, 1e-12), pr, rc


def run(name, pairs, limit=250):
    cache = {k: [] for k in KS}
    prev, rnd_f1 = [], []
    rng = np.random.default_rng(0)
    for i, (ip, gp) in enumerate(pairs[:limit], 1):
        img8 = np.array(Image.open(ip).convert("L"))
        g = np.array(Image.open(gp).convert("L"))
        gt = g > 127
        if gt.sum() < 50 or gt.mean() > 0.6:
            continue
        prev.append(gt.mean())
        for k in KS:
            cache[k].append(sc(emit(img8, k), gt))
        m = emit(img8, 2.5)
        r = np.zeros(gt.size, bool)
        r[rng.choice(gt.size, max(int(m.sum()), 1), replace=False)] = True
        rnd_f1.append(sc(r.reshape(gt.shape), gt)[0])
        if i % 60 == 0:
            print(f"    [{i}/{min(len(pairs), limit)}]", flush=True)
    N = len(cache[KS[0]])
    if not N:
        print(f"  {name}: no usable pairs"); return None
    loo = []
    for i in range(N):
        best = max(KS, key=lambda k: np.mean([cache[k][j][0] for j in range(N) if j != i]))
        loo.append(cache[best][i][0])
    out = dict(n=N, prevalence=float(np.mean(prev)),
               frozen=float(np.mean([x[0] for x in cache[5.0]])),
               k25=float(np.mean([x[0] for x in cache[2.5]])),
               k25_p=float(np.mean([x[1] for x in cache[2.5]])),
               k25_r=float(np.mean([x[2] for x in cache[2.5]])),
               loo=float(np.mean(loo)),
               best_k=max(KS, key=lambda k: np.mean([x[0] for x in cache[k]])),
               zeros_frozen=int(sum(1 for x in cache[5.0] if x[0] == 0)),
               zeros_k25=int(sum(1 for x in cache[2.5] if x[0] == 0)),
               random=float(np.mean(rnd_f1)),
               per_k={str(k): float(np.mean([x[0] for x in cache[k]])) for k in KS})
    print(f"  {name}: n={N} prevalence {100*out['prevalence']:.2f}%  "
          f"frozen {out['frozen']:.4f}  k=2.5 {out['k25']:.4f}  LOO {out['loo']:.4f} "
          f"(best k={out['best_k']})  random {out['random']:.4f}")
    return out


RES = {}
SCR = os.environ["SCR"]
dc = f"{SCR}/pub_deepcrack/DeepCrack-master/dataset"
if os.path.isdir(dc + "/test_img"):
    pairs = []
    for f in sorted(os.listdir(dc + "/test_img")):
        g = os.path.join(dc, "test_lab", os.path.splitext(f)[0] + ".png")
        if os.path.exists(g):
            pairs.append((os.path.join(dc, "test_img", f), g))
    print(f"DeepCrack: {len(pairs)} test pairs")
    RES["DeepCrack"] = run("DeepCrack", pairs)
json.dump(RES, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pub.json"), "w"), indent=1)
