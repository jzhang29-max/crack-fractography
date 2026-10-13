"""How does the SEM detector do on TXM, across the model versions shipped today?

TXM is a BETTER precision benchmark than SEM and that is the point of running it. Its
corrections carry 263,692,695 hand-marked NOT-crack px against 8,518,853 crack -- a 31:1
ratio -- where the SEM paint's certified not-crack is 0.6% of the refereed pool and cannot
price a false positive at all. Only refereed pixels (1 = crack, 2 = not-crack) are scored;
0 = unreviewed is excluded from both ends.

IoU is reported but must not be ranked on: a prior measurement puts the TXM IoU ceiling for
a correct 3 px crack at 0.0498, because the paint is far wider than the feature, so IoU here
rewards imitating the brush rather than finding the crack. Recall and precision on refereed
pixels are the readable numbers.

Two controls, because a model that ties them has shown nothing: mark-everything, and a
plain Otsu darkness cut with no model at all.
"""
import os, sys, json, time
import numpy as np
from scipy import ndimage as ndi
from skimage import filters

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code")
sys.dont_write_bytecode = True
import joblib
import detect_cracks as D
import detector_overrides as DO

TXM = "/Users/jiamingzhang/Desktop/APP/TXM_Crack_Detection_Pipeline"
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
B = joblib.load(os.path.join(SEM, "models", "crack_classifier.joblib"))
FEATS, SCALER, CLF, THR = B["feature_names"], B["scaler"], B["clf"], B["threshold"]


def arm(t, multi=True):
    class U:
        pass
    u = U(); DO.install(u, absolute_dark_thresh=t, use_multiscale_union=multi); return u


U_single10 = arm(10, multi=False)
U_multi10 = arm(10, multi=True)
U_multi20 = arm(20, multi=True)


def cand(m):
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool), None
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    keep = np.isin(lab, k[k > 0])
    return keep, lab * keep


names = []
for f in sorted(os.listdir(os.path.join(TXM, "paint", "corrections"))):
    if not f.endswith("_correction.npy"):
        continue
    stem = f[: -len("_correction.npy")]
    tif = os.path.join(TXM, "images", stem + ".tif")
    if os.path.exists(tif):
        names.append((stem, tif, os.path.join(TXM, "paint", "corrections", f)))
print(f"{len(names)} TXM frames have both an image and a correction mask")

ARMS = ["v1.47 classifier+single", "v1.48 no-cls single", "v1.49 no-cls multi",
        "v1.49 + absdark 20", "control: Otsu, no model", "control: mark everything"]
A = {a: dict(tp=0, fp=0) for a in ARMS}
tot_c = tot_n = 0
n_used = 0
for i, (stem, tif, cpath) in enumerate(names, 1):
    try:
        corr = np.load(cpath)
        if int((corr == 1).sum()) < 5000:
            continue
        img8 = D.load_as_uint8(tif)
        if img8.shape != corr.shape:
            print(f"  [{i}] shape mismatch {img8.shape} vs {corr.shape} -- skipped"); continue
        crack, notc = corr == 1, corr == 2
        tot_c += int(crack.sum()); tot_n += int(notc.sum()); n_used += 1
        flat = D.flatten_background(img8)
        m_single, lab_s = cand(U_single10.segment_dark_regions(flat, img8=img8))
        m_multi, _ = cand(U_multi10.segment_dark_regions(flat, img8=img8))
        m_m20, _ = cand(U_multi20.segment_dark_regions(flat, img8=img8))
        # v1.47 needs the classifier, which needs vesselness
        ves = D.compute_vesselness(flat)
        lab2, _ = ndi.label(D.clean_mask(U_single10.segment_dark_regions(flat, img8=img8),
                                         min_area_px=13))
        labeled, df = D.region_features_from_labeled(lab2, flat, ves)
        if len(df):
            p = CLF.predict_proba(SCALER.transform(df[FEATS].values))[:, 1]
            pm = np.zeros(int(labeled.max()) + 1, np.float32)
            for l, v in zip(df["Label"].values, p):
                pm[int(l)] = v
            m_cls = (pm[labeled] >= THR) & (labeled > 0)
        else:
            m_cls = np.zeros_like(m_single)
        sm = filters.gaussian(flat, sigma=1.0, preserve_range=True)
        m_otsu = sm < filters.threshold_otsu(sm)
        for a, m in zip(ARMS, [m_cls, m_single, m_multi, m_m20, m_otsu,
                               np.ones_like(m_single)]):
            A[a]["tp"] += int((m & crack).sum()); A[a]["fp"] += int((m & notc).sum())
        print(f"  [{i:>2}/{len(names)}] {stem[:46]:<48} crack {int(crack.sum()):>9,} "
              f"R(v1.49) {int((m_multi&crack).sum())/max(int(crack.sum()),1):.3f}", flush=True)
    except Exception as e:
        print(f"  [{i}] {stem[:40]} ERROR {type(e).__name__}: {e}", flush=True)

print(f"\nPOOLED over {n_used} TXM frames -- refereed pixels only "
      f"({tot_c:,} crack, {tot_n:,} not-crack, {tot_n/max(tot_c,1):.1f}:1)")
print(f"  {'arm':<28} {'recall':>8} {'precision':>10} {'F1':>8} {'IoU':>8}")
for a in ARMS:
    tp, fp = A[a]["tp"], A[a]["fp"]; fn = tot_c - tp
    p = tp / max(tp + fp, 1); r = tp / max(tot_c, 1)
    print(f"  {a:<28} {r:8.4f} {p:10.4f} {2*p*r/max(p+r,1e-9):8.4f} {tp/max(tp+fp+fn,1):8.4f}")
print(f"\n  prevalence of crack among refereed px = {tot_c/max(tot_c+tot_n,1):.4f}"
      f"  (that is mark-everything's precision, the no-information floor)")
json.dump({a: A[a] for a in ARMS} | {"crack": tot_c, "notc": tot_n, "n": n_used},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "txm.json"), "w"), indent=1)
