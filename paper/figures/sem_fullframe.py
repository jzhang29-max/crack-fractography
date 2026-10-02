"""The same stages, but computed on the WHOLE 25 MP frame and then cropped.

Why bother: segment_dark_regions picks its threshold from the frame's own histogram
(Otsu, and median/MAD), and region features are per-component. Running those on a
1200 px window is NOT the deployed computation, so a Pass-1-vs-deployed-mask
difference measured that way confounds "what Pass 2 adds" with "what a different
threshold does". Computing on the full frame removes the confound.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import os, sys, json, time
import numpy as np
S = _paths.SEM_REPO
sys.path.insert(0, os.path.join(S, "code"))
import detect_cracks as D
import joblib
from scipy import ndimage as ndi
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
OUT = os.path.dirname(os.path.abspath(__file__))
FRAME, X0, Y0, SIDE = "MAR_H_AS_CBS_0004", 400, 1600, 1200
MODEL = f"{S}/models/crack_classifier.joblib"
t0 = time.time()
def tick(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

img8 = D.load_as_uint8(f"{S}/original/{FRAME}.tif"); tick(f"loaded {img8.shape}")
g = np.asarray(Image.open(f"{S}/crack_export/derived/gated_masks/{FRAME}_gated.png").convert("L")) < 128
m = np.asarray(Image.open(f"{S}/crack_export/derived/machine_masks/{FRAME}_machine.png").convert("L")) < 128
h = min(img8.shape[0], g.shape[0], m.shape[0]); w = min(img8.shape[1], g.shape[1], m.shape[1])
img8, g, m = img8[:h,:w], g[:h,:w], m[:h,:w]

flat = D.flatten_background(img8); tick("flatten_background")
ves = D.compute_vesselness(flat); tick("compute_vesselness")
dark = D.segment_dark_regions(flat, img8=img8); tick(f"segment_dark_regions {100*dark.mean():.3f}%")
# THE PRODUCTION VALUE, not the function default. main() calls
# clean_mask(..., min_area_px=max(5, min_area_px // 3)) with min_area_px=40, i.e. 13 px.
# This script passed the bare default of 15 for three figure revisions, so the caption
# said 15 while the shipped detector used 13.
MIN_AREA_CLEAN = max(5, 40 // 3)
clean = D.clean_mask(dark, min_area_px=MIN_AREA_CLEAN)
tick(f"clean_mask(min_area_px={MIN_AREA_CLEAN}) {100*clean.mean():.3f}%")
lab_raw, n_raw = ndi.label(clean); tick(f"{n_raw} components")
labeled, df = D.region_features_from_labeled(lab_raw, flat, ves); tick(f"{len(df)} candidates")
scored = D.classify_with_model(df, MODEL); tick(f"{int(scored['IsCrack'].sum())} kept")

proba = np.zeros(labeled.max()+1, np.float32); keep = np.zeros(labeled.max()+1, bool)
for lb, p, k in zip(scored["Label"].values, scored["CrackProbability"].values, scored["IsCrack"].values):
    proba[int(lb)] = p; keep[int(lb)] = bool(k)
pass1 = keep[labeled]; prob_map = proba[labeled]

sl = (slice(Y0, Y0+SIDE), slice(X0, X0+SIDE))
for nm, a in [("img8", img8[sl]), ("flat", flat[sl]), ("ves", ves[sl]), ("clean", clean[sl]),
              ("prob", prob_map[sl]), ("pass1", pass1[sl]), ("mach", m[sl]), ("gated", g[sl])]:
    np.save(f"{OUT}/sem_{nm}.npy", a)
Image.fromarray(img8).resize((w//8, h//8), Image.LANCZOS).save(f"{OUT}/sem_frame_thumb.png")

gs, ms, p1 = g[sl], m[sl], pass1[sl]
bundle = joblib.load(MODEL)
st = dict(frame=FRAME, crop=[X0,Y0,SIDE], full=[int(w),int(h)], nm_per_px=51.883,
  min_area_clean=MIN_AREA_CLEAN, min_area_candidate=40,
  extent_note=f"stages computed on the {h}x{w} extent common to the frame and its masks; "
              f"the TIFF is 4376 rows and the masks 4096, and the global Otsu/MAD threshold "
              f"depends on which is used",
  threshold=float(bundle["threshold"]), n_train=int(bundle["n_train"]), n_images=len(bundle["images"]),
  pooled_auc=bundle["cv_results"]["LogisticRegression"]["pooled_auc"],
  pooled_auc_sd=bundle["cv_results"]["LogisticRegression"]["pooled_auc_std"],
  frame_dark_pct=100*float(dark.mean()), frame_clean_pct=100*float(clean.mean()),
  frame_components=int(n_raw), frame_candidates=int(len(df)), frame_kept=int(scored["IsCrack"].sum()),
  frame_pass1_pct=100*float(pass1.mean()), frame_mach_pct=100*float(m.mean()), frame_gated_pct=100*float(g.mean()),
  prob_median_kept=float(np.median(scored.loc[scored["IsCrack"],"CrackProbability"])),
  prob_median_dropped=float(np.median(scored.loc[~scored["IsCrack"],"CrackProbability"])),
  crop_gated_pct=100*float(gs.mean()), crop_mach_pct=100*float(ms.mean()), crop_pass1_pct=100*float(p1.mean()),
  crop_pass2_added_pp=100*float((ms & ~p1).mean()), crop_pass1_not_mach_pp=100*float((p1 & ~ms).mean()),
  crack_dn=float(np.median(img8[sl][gs])), matrix_dn=float(np.median(img8[sl][~gs])),
  matrix_sd=float(img8[sl][~gs].std()),
  ves_crack=float(ves[sl][gs].mean()), ves_matrix=float(ves[sl][~gs].mean()),
  ves_ratio=float(ves[sl][gs].mean()/max(ves[sl][~gs].mean(),1e-12)),
  sep_raw_sd=float((np.median(img8[sl][~gs])-np.median(img8[sl][gs]))/img8[sl][~gs].std()),
  sep_flat_sd=float((np.median(flat[sl][~gs])-np.median(flat[sl][gs]))/flat[sl][~gs].std()),
  crop_components=int(ndi.label(gs)[1]),
  seconds=round(time.time()-t0,1))
print(json.dumps(st, indent=1))
json.dump(st, open(f"{OUT}/sem_stats.json","w"), indent=1)
tick("done")
