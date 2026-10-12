"""Joint (mad_k, classifier threshold) sweep, scored leave-one-specimen-out.

Two parameters were each set for specificity: the 5-MAD candidate bar and the 0.5538
classifier cut. Tuning them together on 26 tiles and quoting the result would be fitting
on the data; every number below is scored on a specimen whose tiles never saw the choice.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
SC = "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad"
os.environ["MPLCONFIGDIR"] = SC + "/mpl"
S = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
sys.path.insert(0, S + "/code"); sys.dont_write_bytecode = True
import numpy as np, tifffile, joblib
from PIL import Image
from skimage import exposure, filters
from scipy import ndimage as ndi
import detect_cracks as D
Image.MAX_IMAGE_PIXELS = None
UP = "/Users/jiamingzhang/Library/Application Support/Crack Fractography/uploads"
ORIG = os.path.join(S, "original"); MACH = os.path.join(S, "crack_export", "derived", "machine_masks")
B = joblib.load(os.path.join(S, "models", "crack_classifier.joblib"))
FEATS, SCALER, CLF = B["feature_names"], B["scaler"], B["clf"]
tiles = [t for t in json.load(open(SC + "/tiles_meta.json")) if t["specimen"] != "MAR_AmbB_AS"]
def as_uint8(a):
    lo, hi = np.percentile(a, [1.0, 99.5])
    return exposure.rescale_intensity(a.astype(np.float32), in_range=(lo, hi), out_range=(0, 255)).astype(np.uint8)
MADK = [5.0, 4.0, 3.0, 2.5, 2.0]
THRS = [round(v, 2) for v in np.arange(0.10, 0.96, 0.05)]
cells = {}          # (k, thr) -> list of per-tile (spec, tp, fp, fn)
for k in MADK:
    for th in THRS: cells[(k, th)] = []
for i, t in enumerate(tiles, 1):
    n, par = t["frame"], t["parent"]; x, y, w, h = t["box"]
    gt = np.array(Image.open(os.path.join(UP, n + "_gated.png")).convert("L")) < 128
    src = next(os.path.join(ORIG, par + e) for e in (".tif", ".tiff", ".png")
               if os.path.exists(os.path.join(ORIG, par + e)))
    mh, mw = np.array(Image.open(os.path.join(MACH, par + "_machine.png"))).shape
    a = tifffile.imread(src)
    if a.ndim == 3: a = a[..., 0]
    if a.shape[1] == mw and a.shape[0] > mh: a = a[:mh, :]
    img8 = as_uint8(a[y:y+h, x:x+w]); flat = D.flatten_background(img8)
    smooth = filters.gaussian(flat, sigma=1.0, preserve_range=True)
    med = np.median(smooth); mad = np.median(np.abs(smooth - med)) * 1.4826
    otsu = filters.threshold_otsu(smooth); ves = D.compute_vesselness(flat)
    for k in MADK:
        dark = (smooth < min(otsu, med - k * mad)) | (img8 < 10)
        lab, _ = ndi.label(D.clean_mask(dark, min_area_px=13))
        labeled, df = D.region_features_from_labeled(lab, flat, ves)
        if len(df):
            p = CLF.predict_proba(SCALER.transform(df[FEATS].values))[:, 1]
            pm = np.zeros(labeled.max() + 1)
            for l, v in zip(df["Label"].values, p): pm[int(l)] = v
            prob = pm[labeled] * (labeled > 0)
        else:
            prob = np.zeros_like(gt, float)
        for th in THRS:
            pr = prob >= th
            cells[(k, th)].append((t["specimen"], int((pr & gt).sum()),
                                   int((pr & ~gt).sum()), int((~pr & gt).sum())))
    print(f"[{i:>2}/{len(tiles)}] {t['specimen'][:14]:<15} done", flush=True)
json.dump({f"{k}|{th}": v for (k, th), v in cells.items()}, open(SC + "/joint.json", "w"))
print("wrote joint.json")
