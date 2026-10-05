"""Every SEM panel, produced by calling the shipped detector's own functions.

Nothing here is a reimplementation: load_as_uint8, flatten_background,
segment_dark_regions, clean_mask, compute_vesselness, region_features_from_labeled
and classify_with_model are imported from code/detect_cracks.py, and the classifier
is the deployed bundle models/crack_classifier.joblib at its own threshold.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import os, sys, json
import numpy as np
S = _paths.require(_paths.SEM_REPO, "the sem-crack-detector checkout", "SEM_REPO")
sys.path.insert(0, os.path.join(S, "code"))
import detect_cracks as D
import joblib
from skimage import measure
from scipy import ndimage as ndi
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
OUT = os.path.dirname(os.path.abspath(__file__))
FRAME, X0, Y0, SIDE = "MAR_H_AS_CBS_0004", 400, 1600, 1200
MODEL = f"{S}/models/crack_classifier.joblib"

img8 = D.load_as_uint8(f"{S}/original/{FRAME}.tif")
g = np.asarray(Image.open(f"{S}/crack_export/derived/gated_masks/{FRAME}_gated.png").convert("L")) < 128
m = np.asarray(Image.open(f"{S}/crack_export/derived/machine_masks/{FRAME}_machine.png").convert("L")) < 128
h = min(img8.shape[0], g.shape[0], m.shape[0]); w = min(img8.shape[1], g.shape[1], m.shape[1])
sl = (slice(Y0, Y0+SIDE), slice(X0, X0+SIDE))
full8 = img8[:h, :w]
sub, gs, ms = full8[sl], g[:h, :w][sl], m[:h, :w][sl]

flat = D.flatten_background(sub)
ves  = D.compute_vesselness(flat)
dark = D.segment_dark_regions(flat, img8=sub)
clean = D.clean_mask(dark)
lab_raw, n_raw = ndi.label(clean)
labeled, df = D.region_features_from_labeled(lab_raw, flat, ves)

b = joblib.load(MODEL)
thr = float(b["threshold"])
scored = D.classify_with_model(df, MODEL)
proba = np.zeros(labeled.max()+1, dtype=np.float32)
for lb, p in zip(scored["Label"].values, scored["CrackProbability"].values):
    proba[int(lb)] = p
prob_map = proba[labeled]                       # 0 on background
keep = np.zeros(labeled.max()+1, dtype=bool)
for lb, k in zip(scored["Label"].values, scored["IsCrack"].values):
    keep[int(lb)] = bool(k)
pass1 = keep[labeled]

for nm, a in [("img8", sub), ("flat", flat), ("ves", ves), ("clean", clean),
              ("prob", prob_map), ("pass1", pass1), ("mach", ms), ("gated", gs),
              ("labeled", labeled)]:
    np.save(f"{OUT}/sem_{nm}.npy", a)

# a thumbnail of the whole frame with the crop box, for a "where is this" inset
th = Image.fromarray(full8).resize((full8.shape[1]//8, full8.shape[0]//8), Image.LANCZOS)
th.save(f"{OUT}/sem_frame_thumb.png")

st = dict(
    frame=FRAME, crop=[X0, Y0, SIDE], full=[int(w), int(h)],
    nm_per_px=51.883, threshold=thr,
    crack_dn=float(np.median(sub[gs])), matrix_dn=float(np.median(sub[~gs])),
    matrix_std=float(sub[~gs].std()),
    dark_pct=100*float(dark.mean()), clean_pct=100*float(clean.mean()),
    n_raw_components=int(n_raw), n_candidates=int(len(df)),
    n_kept=int(scored["IsCrack"].sum()),
    kept_pct=100*float(pass1.mean()),
    mach_pct=100*float(ms.mean()), gated_pct=100*float(gs.mean()),
    pass2_added_pct=100*float((ms & ~pass1).mean()),
    ves_crack=float(ves[gs].mean()), ves_matrix=float(ves[~gs].mean()),
    ves_ratio=float(ves[gs].mean()/max(ves[~gs].mean(),1e-9)),
    prob_median_kept=float(np.median(scored.loc[scored["IsCrack"], "CrackProbability"])) if scored["IsCrack"].any() else None,
    prob_median_dropped=float(np.median(scored.loc[~scored["IsCrack"], "CrackProbability"])) if (~scored["IsCrack"]).any() else None,
    crop_components=int(ndi.label(gs)[1]),
)
# how separable is crack from matrix, in matrix standard deviations, before and after?
st["sep_raw_sd"] = float((np.median(sub[~gs]) - np.median(sub[gs])) / sub[~gs].std())
st["sep_flat_sd"] = float((np.median(flat[~gs]) - np.median(flat[gs])) / flat[~gs].std())
st["sep_ves_sd"] = float((ves[gs].mean() - ves[~gs].mean()) / ves[~gs].std())
print(json.dumps(st, indent=1))
json.dump(st, open(f"{OUT}/sem_stats.json","w"), indent=1)
