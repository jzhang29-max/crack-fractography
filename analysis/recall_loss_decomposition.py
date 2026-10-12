"""WHERE DOES RECALL GO? Decompose every missed pixel by the stage that lost it.

The detector is a chain: threshold dark pixels -> drop small components -> keep
components big enough to feature -> classify each. A crack pixel the human marked can be
lost at ANY of those, and the fix is different for each one. Pooling them into a single
"recall 0.37" hides which lever matters.

Also sweeps the classifier threshold, because the shipped one (0.5538) was chosen for
specificity on a held-out frame, not for this ground truth.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
SC = "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad"
os.environ["MPLCONFIGDIR"] = SC + "/mpl"
S = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
sys.path.insert(0, S + "/code"); sys.dont_write_bytecode = True
import numpy as np, tifffile, joblib
from PIL import Image
from skimage import exposure
from scipy import ndimage as ndi
import detect_cracks as D
Image.MAX_IMAGE_PIXELS = None

UP = "/Users/jiamingzhang/Library/Application Support/Crack Fractography/uploads"
ORIG = os.path.join(S, "original"); MACH = os.path.join(S, "crack_export", "derived", "machine_masks")
B = joblib.load(os.path.join(S, "models", "crack_classifier.joblib"))
FEATS = B["feature_names"]; SCALER = B["scaler"]; CLF = B["clf"]; THR = B["threshold"]
print(f"model: {B['model_family']}  threshold {THR:.4f}  features {FEATS}")

tiles = [t for t in json.load(open(SC + "/tiles_meta.json")) if t["specimen"] != "MAR_AmbB_AS"]
def as_uint8(a, low=1.0, high=99.5):
    lo, hi = np.percentile(a, [low, high])
    return exposure.rescale_intensity(a.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)

GRID = np.round(np.arange(0.02, 1.00, 0.02), 2)
agg = dict(gt=0, lost_threshold=0, lost_clean=0, lost_small=0, lost_classifier=0, kept=0)
sweep = {float(t): dict(tp=0, fp=0, fn=0) for t in GRID}
per = []
for i, t in enumerate(tiles, 1):
    n, par = t["frame"], t["parent"]; x, y, w, h = t["box"]
    gt = np.array(Image.open(os.path.join(UP, n + "_gated.png")).convert("L")) < 128
    src = next(os.path.join(ORIG, par + e) for e in (".tif", ".tiff", ".png")
               if os.path.exists(os.path.join(ORIG, par + e)))
    mh, mw = np.array(Image.open(os.path.join(MACH, par + "_machine.png"))).shape
    a = tifffile.imread(src)
    if a.ndim == 3: a = a[..., 0]
    if a.shape[1] == mw and a.shape[0] > mh: a = a[:mh, :]
    img8 = as_uint8(a[y:y+h, x:x+w])
    flat = D.flatten_background(img8)
    dark = D.segment_dark_regions(flat, img8=img8)
    clean = D.clean_mask(dark, min_area_px=13)
    ves = D.compute_vesselness(flat)
    lab, _ = ndi.label(clean)
    labeled, df = D.region_features_from_labeled(lab, flat, ves)
    cand = labeled > 0                       # survived the >=40 px feature filter

    if len(df):
        Xs = SCALER.transform(df[FEATS].values)
        proba = CLF.predict_proba(Xs)[:, 1]
        pmap = np.zeros(labeled.max() + 1)
        for l, p in zip(df["Label"].values, proba): pmap[int(l)] = p
        probimg = pmap[labeled]
    else:
        probimg = np.zeros_like(img8, float)

    kept = (probimg >= THR) & cand
    agg["gt"] += int(gt.sum())
    agg["lost_threshold"] += int((gt & ~dark).sum())
    agg["lost_clean"]     += int((gt & dark & ~clean).sum())
    agg["lost_small"]     += int((gt & clean & ~cand).sum())
    agg["lost_classifier"]+= int((gt & cand & ~kept).sum())
    agg["kept"]           += int((gt & kept).sum())
    for th in GRID:
        p = (probimg >= th) & cand
        s = sweep[float(th)]
        s["tp"] += int((p & gt).sum()); s["fp"] += int((p & ~gt).sum()); s["fn"] += int((~p & gt).sum())
    per.append(dict(frame=n, specimen=t["specimen"], gt=int(gt.sum()),
                    dark=int(dark.sum()), cand=int(cand.sum()), kept=int(kept.sum()),
                    gt_in_cand=int((gt & cand).sum()), n_regions=int(len(df))))
    print(f"[{i:>2}/{len(tiles)}] {t['specimen'][:15]:<16} gt {int(gt.sum()):>7,} "
          f"of which reached a candidate {int((gt&cand).sum()):>7,} "
          f"({100*(gt&cand).sum()/max(gt.sum(),1):5.1f}%)", flush=True)
json.dump(dict(agg=agg, sweep={str(k): v for k, v in sweep.items()}, per=per),
          open(SC + "/diag.json", "w"), indent=1)
print("\nwrote diag.json")
