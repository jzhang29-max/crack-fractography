"""Does "delete the region classifier" hold up on FULL frames, where it would actually run?

Both precision rules are dead: the texture veto and the thickness excision each delete
40-43% of hand-marked crack on full frames, reproducing the failure unified_pipeline.py
already documents for exclude_border_background(). What is left is the half that cannot
delete anything -- keeping the candidate regions the classifier rejected only ADDS pixels.

But "only adds" is not automatically safe: it can add background. The correction masks give
both answers, because a human reviewed both ways:
    1 = hand-marked CRACK      -> extra coverage here is a real recall gain
    2 = hand-marked NOT-crack  -> extra coverage here is a real false positive
    0 = unreviewed             -> excluded from BOTH, since it is not evidence either way
That last line matters: 91% of this corpus is unreviewed, so scoring against "everything not
painted crack" would count unexamined matrix as error and make any recall gain look like a
precision collapse.
"""
import os, sys, json
import numpy as np
from scipy import ndimage as ndi
from PIL import Image

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code")
sys.dont_write_bytecode = True
import joblib
import detect_cracks as D
Image.MAX_IMAGE_PIXELS = None
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
B = joblib.load(os.path.join(SEM, "models", "crack_classifier.joblib"))
FEATS, SCALER, CLF, THR = B["feature_names"], B["scaler"], B["clf"], B["threshold"]

cms = sorted(f for f in os.listdir(PAINT) if f.endswith("_correction_mask.png"))
names = [f[:-len("_correction_mask.png")] for f in cms]
names = [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
LIMIT = int(os.environ.get("NFRAMES", "10"))
print(f"{len(names)} frames have both a micrograph and a correction mask; using {LIMIT}\n")

rows = []
agg = dict(crack=0, notc=0, s_tp=0, s_fp=0, n_tp=0, n_fp=0)
print(f"{'frame':<36} {'painted crack':>13} {'painted not':>12} | {'recall ship':>11} {'recall NOcls':>12} | "
      f"{'FPrate ship':>11} {'FPrate NOcls':>12}")
print("-" * 124)
for name in names[:LIMIT]:
    try:
        img8 = D.load_as_uint8(os.path.join(SEM, "original", name + ".tif"))
        x0, y0, x1, y1 = D.find_field_of_view(img8)
        img8 = img8[y0:y1, x0:x1]
        corr = np.array(Image.open(os.path.join(PAINT, name + "_correction_mask.png")))
        if corr.ndim == 3:
            corr = corr[..., 0]
        if corr.shape != img8.shape:
            if corr.shape[0] >= y1 and corr.shape[1] >= x1:
                corr = corr[y0:y1, x0:x1]
            else:
                print(f"{name:<36}   (paint does not fit the image -- skipped)"); continue
        crack, notc = corr == 1, corr == 2
        if crack.sum() < 1000:
            continue
        flat = D.flatten_background(img8)
        clean = D.clean_mask(D.segment_dark_regions(flat, img8=img8), min_area_px=13)
        ves = D.compute_vesselness(flat)
        lab, _ = ndi.label(clean)
        labeled, df = D.region_features_from_labeled(lab, flat, ves)
        nocls = labeled > 0
        if len(df):
            p = CLF.predict_proba(SCALER.transform(df[FEATS].values))[:, 1]
            pm = np.zeros(int(labeled.max()) + 1, np.float32)
            for l, v in zip(df["Label"].values, p):
                pm[int(l)] = v
            ship = (pm[labeled] >= THR) & nocls
        else:
            ship = np.zeros_like(nocls)
        c, nn = int(crack.sum()), int(notc.sum())
        s_tp, s_fp = int((ship & crack).sum()), int((ship & notc).sum())
        n_tp, n_fp = int((nocls & crack).sum()), int((nocls & notc).sum())
        for k, v in zip(("crack", "notc", "s_tp", "s_fp", "n_tp", "n_fp"), (c, nn, s_tp, s_fp, n_tp, n_fp)):
            agg[k] += v
        rows.append(dict(frame=name, crack=c, notc=nn, s_tp=s_tp, s_fp=s_fp, n_tp=n_tp, n_fp=n_fp))
        print(f"{name:<36} {c:>13,} {nn:>12,} | {s_tp/max(c,1):11.4f} {n_tp/max(c,1):12.4f} | "
              f"{s_fp/max(nn,1):11.4f} {n_fp/max(nn,1):12.4f}", flush=True)
    except Exception as e:
        print(f"{name:<36}   ERROR {type(e).__name__}: {e}")
print("-" * 124)
a = agg
print(f"{'POOLED':<36} {a['crack']:>13,} {a['notc']:>12,} | {a['s_tp']/max(a['crack'],1):11.4f} "
      f"{a['n_tp']/max(a['crack'],1):12.4f} | {a['s_fp']/max(a['notc'],1):11.4f} {a['n_fp']/max(a['notc'],1):12.4f}")
print()
print("Reading the two columns together:")
print(f"  recall on hand-marked CRACK      {a['s_tp']/max(a['crack'],1):.4f} -> {a['n_tp']/max(a['crack'],1):.4f}"
      f"   ({a['n_tp']-a['s_tp']:+,} px)")
print(f"  rate on hand-marked NOT-crack    {a['s_fp']/max(a['notc'],1):.4f} -> {a['n_fp']/max(a['notc'],1):.4f}"
      f"   ({a['n_fp']-a['s_fp']:+,} px)")
gain, cost = a['n_tp'] - a['s_tp'], a['n_fp'] - a['s_fp']
print(f"  crack px gained per not-crack px gained: {gain/max(cost,1):.2f}")
json.dump(rows, open("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                     "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/fullframe.json", "w"), indent=1)
