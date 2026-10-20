"""The detector on SEM materials cracks with pixel ground truth.

Zenodo 23045328, test split: SEM micrographs of metals and coatings with binary masks.
Two of its eighteen target folders are cracks -- EBC_crack (environmental barrier coating)
and Inconel718_crack (nickel superalloy). This is the first public crack benchmark in this
project that is MICROSCOPY rather than pavement.

Same instrument as docs/figures/public_metrics.json: emit() copied from pubeval.py, the
same score(), the same controls, mad_k chosen leave-one-image-out.

MASK POLARITY AND TYPE WERE CHECKED, NOT ASSUMED. EBC masks are strictly {0,255}. Inconel
masks carry the full 0-255 range but are anti-aliased binary: 94.7% exactly 0, 4.3% at 246
or above, 0.52% in between. A 127 threshold is therefore safe, and the check is repeated
here so a future file that is NOT bimodal fails loudly.
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

ROOT = sys.argv[1]
class U: pass
u = U(); DO.install(u)
KS = [5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0]


def emit(img8, k):
    raw = u.segment_dark_regions(D.flatten_background(img8), img8=img8, mad_k=k)
    lab = skm.label(D.clean_mask(raw, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); kk = np.where(sz >= 40)[0]
    return np.isin(lab, kk[kk > 0])


def score(p, g):
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return dict(precision=pr, recall=rc, f1=2 * pr * rc / max(pr + rc, 1e-12),
                iou=tp / max(tp + fp + fn, 1))


def mean_of(rows, k):
    return float(np.mean([r[k] for r in rows])) if rows else None


def load_pairs(cls):
    idir = os.path.join(ROOT, cls, "image_cropped")
    mdir = os.path.join(ROOT, cls, "mask_cropped")
    out = []
    hist = np.zeros(256, dtype=np.int64)
    for f in sorted(os.listdir(idir)):
        im = np.array(Image.open(os.path.join(idir, f)).convert("L"))
        mk = np.array(Image.open(os.path.join(mdir, f)).convert("L"))
        hist += np.bincount(mk.ravel(), minlength=256)
        out.append((f, im, mk > 127))
    mid = hist[10:246].sum() / max(hist.sum(), 1)
    if mid > 0.02:
        raise SystemExit(f"{cls}: masks are not bimodal ({100*mid:.2f}% mid-range) -- a "
                         "127 threshold would be a guess, refusing to score")
    return out, float(mid)


RES = {}
for cls in ("EBC_crack", "Inconel718_crack"):
    pairs, mid = load_pairs(cls)
    rng = np.random.default_rng(0)
    per_k = {k: [] for k in KS}
    me, er, orc, prev = [], [], [], []
    for f, im, gt in pairs:
        if gt.sum() < 50:
            continue
        prev.append(float(gt.mean()))
        for k in KS:
            per_k[k].append(score(emit(im, k), gt))
        me.append(score(np.ones_like(gt, bool), gt))
        orc.append(score(gt, gt))
        m = emit(im, KS[0])
        r = np.zeros(gt.size, bool)
        r[rng.choice(gt.size, max(int(m.sum()), 1), replace=False)] = True
        er.append(score(r.reshape(gt.shape), gt))
    N = len(per_k[KS[0]])
    loo = []
    for i in range(N):
        best = max(KS, key=lambda k: np.mean([per_k[k][j]["f1"] for j in range(N) if j != i]))
        loo.append(per_k[best][i])
    o = mean_of(orc, "f1")
    assert abs(o - 1.0) < 1e-9, f"oracle is not 1.0: {o}"
    RES[cls] = {
        "n": N, "prevalence": float(np.mean(prev)), "mask_midrange_fraction": mid,
        "loo": {m: mean_of(loo, m) for m in ("precision", "recall", "f1", "iou")},
        "per_k": {str(k): {m: mean_of(per_k[k], m) for m in
                           ("precision", "recall", "f1", "iou")} for k in KS},
        "best_k_pooled": max(KS, key=lambda k: mean_of(per_k[k], "f1")),
        "controls": {"mark_everything": {m: mean_of(me, m) for m in
                                         ("precision", "recall", "f1", "iou")},
                     "equal_area_random": {m: mean_of(er, m) for m in
                                           ("precision", "recall", "f1", "iou")},
                     "oracle": {m: mean_of(orc, m) for m in
                                ("precision", "recall", "f1", "iou")}},
    }
    r = RES[cls]
    print(f"\n{cls}  n={r['n']}  prevalence {100*r['prevalence']:.2f}%  best k={r['best_k_pooled']}")
    for nm, d in (("detector (LOO k)", r["loo"]),
                  ("mark everything", r["controls"]["mark_everything"]),
                  ("equal-area random", r["controls"]["equal_area_random"])):
        print(f"   {nm:20s} P {d['precision']:.4f}  R {d['recall']:.4f}  "
              f"F1 {d['f1']:.4f}  IoU {d['iou']:.4f}")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sem_public_metrics.json")
json.dump({"source": "Zenodo 23045328 (CC BY 4.0), test split, folders EBC_crack and "
                     "Inconel718_crack",
           "modality": "SEM micrographs of metals and coatings",
           "metric": "mean per image, 0 px tolerance, mad_k leave-one-image-out",
           "datasets": RES}, open(out, "w"), indent=1)
print("\nwrote", out)
