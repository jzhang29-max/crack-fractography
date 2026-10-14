"""Stage 1 for the SEM figures, run against WHAT THE APPLICATION ACTUALLY RUNS (v1.49.2).

`sem_fullframe.py` is the companion to this file and runs the ARCHIVED published pipeline:
one flattening radius (sigma = 40) and then the logistic region classifier at its bundled
threshold. Production runs neither. This file runs the production path instead, and the
two are kept side by side on purpose, because the paper's subject is the published
pipeline and the application's subject is the deployed one.

WHAT "PRODUCTION" MEANS HERE, precisely, and where each piece comes from:

  * the candidate stage is `angle4_shipped.shipped_clean`, which does not reimplement the
    seven-radius union -- it calls `detector_overrides.install()` on a stand-in module and
    uses the function that install() binds, so it cannot drift from the app. Its
    ladder-collapse control (SCALE_LADDER -> (40,) must reproduce the stock single-radius
    cut bit for bit) runs here before any number below is written.
  * the EMITTED mask is `unified_pipeline.run_unified_pipeline` driven exactly as
    `analysis/detect_one.py` drives it: `DO.install(up)`, corrections suppressed, hard
    overrides suppressed, and then every row of `df` kept because
    `USE_REGION_CLASSIFIER` is False. That is Pass 1 candidates AND Pass 2's concavity,
    bridge-corridor and interior-fill additions. The candidate stage alone is NOT the
    app's output and panels built on it must say which they drew.

WHAT IS STILL LEARNED ON THIS PATH, which is the thing to check before claiming otherwise:
`USE_REGION_CLASSIFIER = False` is applied by detect_one.py at EMISSION -- it ignores the
`IsCrack` column. It does not stop the artefacts being loaded or consulted:
  * `score_pass1_candidates` still loads `models/crack_classifier.joblib` and writes
    `IsCrack`, and `run_unified_pipeline` builds Pass 2's seed `crack_mask` from exactly
    that column. So the disabled classifier still decides WHICH Pass-2 candidates exist
    and what their two context features measure against.
  * Pass 2 scores every candidate it generates with `models/unified_model.joblib` and
    drops the ones it rejects, so the 11-feature model gates every pixel Pass 2 adds.
Both are measured below (`archived_*`, `pass2_*`) rather than asserted.

Writes `semp_*.npy` and `sem_production.json` into FIG_CACHE. No absolute paths; see
`_paths.py`.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths

S = _paths.require(_paths.SEM_REPO, "the sem-crack-detector checkout", "SEM_REPO")
A = _paths.require(os.path.join(_paths.REPO, "analysis"), "this repo's analysis/ directory",
                   "(it is part of crack-fractography)")
# The SEM repo resolves its inputs from ORIGINAL_DIR. Pin it explicitly and read-only;
# nothing in this script writes there, and the archived repo must not be staged into.
os.environ.setdefault("SEMCRACK_ORIGINAL_DIR", os.path.join(S, "original"))
os.environ.setdefault("SEM_REPO", S)
os.environ.setdefault("APP_REPO", _paths.REPO)
for p in (os.path.join(A, "research", "improve"), A,
          os.path.join(S, "interior_active_learning", "code"), os.path.join(S, "code")):
    sys.path.insert(0, p)

import json, time
import numpy as np
from scipy import ndimage as ndi
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

import detect_cracks as D
import angle4_shipped as A4
import detector_overrides as DO

# IS THE CHECKOUT WHAT THE APPLICATION ACTUALLY RUNS? A figure captioned "as the app runs
# it" is a claim about the built bundle, not about the source tree, and this repository has
# shipped a bundle four commits stale before. If a build is present, the two detector files
# this figure depends on must be byte-identical to the ones imported above; if no build is
# present the check reports that it could not run, rather than passing silently.
import hashlib
def _md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()
BUNDLE_CHECK = []
for _rel in ("analysis/detector_overrides.py", "analysis/detect_one.py"):
    _src = os.path.join(_paths.REPO, _rel)
    for _root in (os.path.join(_paths.REPO, "dist", "Crack Fractography", "_internal"),
                  os.path.join(_paths.REPO, "dist", "Crack Fractography.app",
                               "Contents", "Resources")):
        _built = os.path.join(_root, _rel)
        if not os.path.exists(_built):
            continue
        assert _md5(_src) == _md5(_built), (
            f"the built bundle's {_rel} differs from the one this figure imported; "
            f"a caption saying 'as the application runs it' would be false")
        BUNDLE_CHECK.append(os.path.relpath(_built, _paths.REPO))
if not BUNDLE_CHECK:
    BUNDLE_CHECK = ["no build found under dist/; the source tree was NOT checked "
                    "against a packaged bundle"]

OUT = _paths.FIG_CACHE
FRAME, X0, Y0, SIDE = "MAR_H_AS_CBS_0004", 400, 1600, 1200
t0 = time.time()
def tick(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

# ---------------------------------------------------------------- production load
import common
img8_full = D.load_as_uint8(os.path.join(common.ORIGINAL_DIR, f"{FRAME}.tif"),
                            **common.contrast_kwargs_for(FRAME))
fx0, fy0, fx1, fy1 = D.find_field_of_view(img8_full)
img8 = img8_full[fy0:fy1, fx0:fx1]
tick(f"loaded {img8_full.shape} -> field of view {img8.shape} at ({fx0},{fy0})")

# ---------------------------------------------------------------- the two controls
# Run the ladder-collapse control on the WINDOW this figure draws, not on a toy array:
# a control that never sees the data it certifies is not one.
A4.selfcheck([img8[Y0:Y0+SIDE, X0:X0+SIDE]])
tick("ladder-collapse control")

# ---------------------------------------------------------------- candidate stage
flat = D.flatten_background(img8, sigma=40)
ves = D.compute_vesselness(flat)
seg_union = A4.seg_fn()                 # the function detector_overrides.install() binds
dark_union = seg_union(flat, img8=img8, mad_k=5.0)
dark_single = D.segment_dark_regions(flat, mad_k=5.0, img8=img8)
tick(f"dark: union {100*dark_union.mean():.3f}%  single-radius {100*dark_single.mean():.3f}%")
assert (dark_union | dark_single == dark_union).all(), "the union must be a superset"

MIN_AREA_CLEAN = 13                     # run_unified_pipeline's own literal
clean = D.clean_mask(dark_union, min_area_px=MIN_AREA_CLEAN)
clean_single = D.clean_mask(dark_single, min_area_px=MIN_AREA_CLEAN)
cand_lab, cand_df = D.extract_candidates(clean, flat, ves, min_area_px=40)
cand_lab_s, cand_df_s = D.extract_candidates(clean_single, flat, ves, min_area_px=40)
cand = cand_lab > 0
cand_s = cand_lab_s > 0
tick(f"candidates: union {len(cand_df)} regions {100*cand.mean():.3f}%  "
     f"single {len(cand_df_s)} regions {100*cand_s.mean():.3f}%")

# ---------------------------------------------------------------- what the app EMITS
# Driven exactly as analysis/detect_one.py drives it.
import unified_pipeline as up
# WHICH LEARNED ARTEFACTS ACTUALLY LOAD. The claim "the shipped SEM detector has no
# learned model" is checkable and this is the check: trace every joblib.load the
# production call makes, rather than reading USE_REGION_CLASSIFIER and assuming.
import joblib as _jl
LOADED = []
_real_load = _jl.load
def _traced(path, *a, **k):
    LOADED.append(os.path.relpath(str(path), S) if str(path).startswith(S) else str(path))
    return _real_load(path, *a, **k)
_jl.load = _traced
up.joblib.load = _traced
import detect_cracks as _dc
if hasattr(_dc, "joblib"):
    _dc.joblib.load = _traced
up.load_correction_mask = lambda *a, **k: None
common.load_correction_mask = lambda *a, **k: None
up.load_hard_overrides = lambda *a, **k: {}
applied = DO.install(up)
tick(f"detector_overrides.install -> {applied}")
st = up.run_unified_pipeline(FRAME)
_jl.load = _real_load
labeled, df = st["labeled"], st["df"]
tick(f"joblib artefacts loaded on the production path: {LOADED}")
assert not DO.USE_REGION_CLASSIFIER, "this script describes the classifier-off path"
emitted = np.isin(labeled, df["Label"].tolist())
tick(f"run_unified_pipeline: {len(df)} rows, emitted {100*emitted.mean():.3f}%")
assert emitted.shape == cand.shape, (emitted.shape, cand.shape)

# WHAT THE DISABLED CLASSIFIER WOULD HAVE DONE, on the production candidate set -- the
# measurement that justifies drawing it as switched off rather than deleting the panel.
is_pass2 = ~df["CandidateType"].isin([None, ""]) & df["CandidateType"].isin(
    ["concavity", "bridge_corridor", "interior_fill"])
p1 = df[~is_pass2]
archived_keep = p1.loc[p1["IsCrack"] == True, "Label"].tolist()          # noqa: E712
archived = np.isin(labeled, archived_keep)
pass2_added = emitted & ~np.isin(labeled, p1["Label"].tolist())
pass1_all = np.isin(labeled, p1["Label"].tolist())
tick(f"pass1 rows {len(p1)}  pass2 rows {int(is_pass2.sum())}  "
     f"archived classifier would keep {len(archived_keep)}")

# ---------------------------------------------------------------- the human reference
g = np.asarray(Image.open(os.path.join(
    S, "crack_export", "derived", "gated_masks", f"{FRAME}_gated.png")).convert("L")) < 128
h = min(img8.shape[0], g.shape[0]); w = min(img8.shape[1], g.shape[1])

def crop(a):
    return a[Y0:Y0+SIDE, X0:X0+SIDE]

sl_ok = (Y0+SIDE <= h) and (X0+SIDE <= w)
assert sl_ok, "the drawn window must lie inside the extent shared with the mask"
gs = g[:h, :w][Y0:Y0+SIDE, X0:X0+SIDE]

for nm, a in [("img8", crop(img8)), ("flat", crop(flat)), ("ves", crop(ves)),
              ("clean", crop(clean)), ("clean_single", crop(clean_single)),
              ("cand", crop(cand)), ("cand_single", crop(cand_s)),
              ("archived", crop(archived)), ("pass1", crop(pass1_all)),
              ("emitted", crop(emitted)), ("gated", gs)]:
    np.save(os.path.join(OUT, f"semp_{nm}.npy"), a)
Image.fromarray(img8).resize((img8.shape[1]//8, img8.shape[0]//8),
                             Image.LANCZOS).save(os.path.join(OUT, "semp_frame_thumb.png"))

c_cand, c_em, c_p1, c_arch = crop(cand), crop(emitted), crop(pass1_all), crop(archived)
stats = dict(
  version="v1.49.2", frame=FRAME, crop=[X0, Y0, SIDE],
  bundle_check=BUNDLE_CHECK,
  full=[int(img8.shape[1]), int(img8.shape[0])],
  raw_full=[int(img8_full.shape[1]), int(img8_full.shape[0])],
  field_of_view=[int(fx0), int(fy0), int(fx1), int(fy1)],
  nm_per_px=51.883, min_area_clean=MIN_AREA_CLEAN, min_area_candidate=40,
  scale_ladder=list(DO.SCALE_LADDER), decimate_above_sigma=DO.DECIMATE_ABOVE_SIGMA,
  mad_k=5.0, absolute_dark_thresh=DO.ABSOLUTE_DARK_THRESH,
  use_region_classifier=bool(DO.USE_REGION_CLASSIFIER),
  installed=applied,
  # frame-wide, on the field of view the app itself works on
  frame_dark_union_pct=100*float(dark_union.mean()),
  frame_dark_single_pct=100*float(dark_single.mean()),
  frame_clean_pct=100*float(clean.mean()),
  frame_candidates=int(len(cand_df)), frame_candidates_single=int(len(cand_df_s)),
  frame_cand_pct=100*float(cand.mean()), frame_cand_single_pct=100*float(cand_s.mean()),
  frame_emitted_pct=100*float(emitted.mean()),
  frame_pass1_rows=int(len(p1)), frame_pass2_rows=int(is_pass2.sum()),
  frame_pass2_added_px=int((emitted & ~pass1_all).sum()),
  frame_pass2_added_pct=100*float((emitted & ~pass1_all).mean()),
  learned_artefacts_loaded=sorted(set(LOADED)),
  pass2_candidates_generated=int(st["n_interior_total"]),
  pass2_candidates_accepted=int(is_pass2.sum()),
  frame_archived_kept=int(len(archived_keep)),
  frame_archived_pct=100*float(archived.mean()),
  # the measurement that justifies drawing the classifier as switched OFF
  frame_archived_would_drop_px=int((emitted & ~archived).sum()),
  frame_archived_would_drop_frac=float((emitted & ~archived).sum()/max(emitted.sum(), 1)),
  frame_archived_drops_painted_px=int((g[:h, :w] & ~archived[:h, :w] & emitted[:h, :w]).sum()),
  frame_painted_px=int(g[:h, :w].sum()),
  frame_recall_emitted=float((g[:h, :w] & emitted[:h, :w]).sum()/max(g[:h, :w].sum(), 1)),
  frame_recall_archived=float((g[:h, :w] & archived[:h, :w]).sum()/max(g[:h, :w].sum(), 1)),
  frame_recall_single=float((g[:h, :w] & cand_s[:h, :w]).sum()/max(g[:h, :w].sum(), 1)),
  frame_recall_cand=float((g[:h, :w] & cand[:h, :w]).sum()/max(g[:h, :w].sum(), 1)),
  # the drawn window
  crop_cand_pct=100*float(c_cand.mean()), crop_emitted_pct=100*float(c_em.mean()),
  crop_pass1_pct=100*float(c_p1.mean()), crop_archived_pct=100*float(c_arch.mean()),
  crop_gated_pct=100*float(gs.mean()),
  crop_pass2_added_pp=100*float((c_em & ~c_p1).mean()),
  crop_ladder_added_pp=100*float((c_cand & ~crop(cand_s)).mean()),
  crop_components=int(ndi.label(gs)[1]),
  crack_dn=float(np.median(crop(img8)[gs])), matrix_dn=float(np.median(crop(img8)[~gs])),
  matrix_sd=float(crop(img8)[~gs].std()),
  ves_crack=float(crop(ves)[gs].mean()), ves_matrix=float(crop(ves)[~gs].mean()),
  ves_ratio=float(crop(ves)[gs].mean()/max(crop(ves)[~gs].mean(), 1e-12)),
  sep_raw_sd=float((np.median(crop(img8)[~gs])-np.median(crop(img8)[gs]))/crop(img8)[~gs].std()),
  sep_flat_sd=float((np.median(crop(flat)[~gs])-np.median(crop(flat)[gs]))/crop(flat)[~gs].std()),
  seconds=round(time.time()-t0, 1))
print(json.dumps(stats, indent=1))
json.dump(stats, open(os.path.join(OUT, "sem_production.json"), "w"), indent=1)
tick("done")
