"""The shipped detector, with its hard-coded constants turned into arguments.

sem-crack-detector is archived and read-only, so nothing here edits it. Every stage calls
the real `detect_cracks` functions where the parameter is already exposed, and
re-implements only `segment_dark_regions`, whose mad_k and absolute_dark_thresh are
baked in. The defaults reproduce the shipped behaviour exactly -- verified against the
independently measured P 0.3378 / R 0.3696 / IoU 0.2143 by tilebench_verify.py.
"""
import os, sys
import numpy as np
from scipy import ndimage as ndi

SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
if SEM + "/code" not in sys.path:
    sys.path.insert(0, SEM + "/code")
import joblib
from skimage import filters
import detect_cracks as D

_B = joblib.load(os.path.join(SEM, "models", "crack_classifier.joblib"))
FEATS, SCALER, CLF, THR = _B["feature_names"], _B["scaler"], _B["clf"], _B["threshold"]

SHIPPED_PARAMS = dict(mad_k=5.0, absolute_dark=10, flat_sigma=40, denoise_sigma=1.0,
                      min_area=13, open_radius=1, close_radius=3, thr=THR)


def stages(img8, flat_sigma=40, denoise_sigma=1.0, mad_k=5.0, absolute_dark=10,
           min_area=13, open_radius=1, close_radius=3):
    """Everything up to (not including) the classifier. Returns the intermediates too,
    because which stage dropped a pixel is the only way to tell a threshold problem from
    a classifier problem."""
    flat = D.flatten_background(img8, sigma=flat_sigma)
    smooth = filters.gaussian(flat, sigma=denoise_sigma, preserve_range=True)
    otsu = filters.threshold_otsu(smooth)
    med = np.median(smooth)
    mad = np.median(np.abs(smooth - med)) * 1.4826
    # min(otsu, robust) keeps Otsu where the histogram really is bimodal and caps the
    # damage where it is not: Otsu alone flags 51.8% of background on these tiles.
    dark = (smooth < min(otsu, med - mad_k * mad)) | (img8 < absolute_dark)
    clean = D.clean_mask(dark, open_radius=open_radius, close_radius=close_radius,
                         min_area_px=min_area)
    ves = D.compute_vesselness(flat)
    lab, _ = ndi.label(clean)
    labeled, df = D.region_features_from_labeled(lab, flat, ves)
    return dict(flat=flat, smooth=smooth, ves=ves, dark=dark, clean=clean,
                labeled=labeled, df=df, otsu=float(otsu), med=float(med), mad=float(mad))


def probability(st):
    """Per-pixel crack probability from the shipped logistic model. 0 outside candidates."""
    labeled, df = st["labeled"], st["df"]
    if not len(df):
        return np.zeros(labeled.shape, np.float32)
    p = CLF.predict_proba(SCALER.transform(df[FEATS].values))[:, 1]
    pm = np.zeros(int(labeled.max()) + 1, np.float32)
    for l, v in zip(df["Label"].values, p):
        pm[int(l)] = v
    return pm[labeled] * (labeled > 0)


def predict(img8, thr=THR, **kw):
    return probability(stages(img8, **kw)) >= thr
