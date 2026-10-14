"""Four classifier families on ONE frame, out of sample for every one of them.

MAR_H_AS_CBS_0004 contributes 0 rows to training_data/labeled_regions.csv, so no model here
has seen it -- which is what makes a side-by-side ladder on it honest.

Each family is built by the TRAINER's own factory (MODELS in train_v3_weighted.py) and fitted
with the trainer's per-image weights and a StandardScaler, so the only thing that varies
across panels is the model family. Candidate regions come from the published pipeline.

THIS LADDER'S RUNGS ARE THE WRONG AXIS, AND IT WAS CHECKED RATHER THAN ASSUMED. The
question asked of this file was whether its rungs are classifier variants or candidate-
stage settings. They are classifier variants: MODELS is {LogisticRegression, RandomForest,
GradientBoosting, SVC (RBF)}, every rung is a region classifier, and the one thing held
fixed across the rungs -- the candidate stage they all score -- is the single-radius cut.
So it is wrong twice over for v1.49.2:

  * the substrate is `D.segment_dark_regions(flat)` at sigma = 40 alone, where production
    unions seven radii (451 candidate regions against 1,347 on this frame);
  * the axis it varies is a component production does not consult at all --
    USE_REGION_CLASSIFIER is False, so swapping LogisticRegression for RandomForest here
    would change nothing the application emits.

ADDING A "PRODUCTION RUNG" WOULD NOT FIX IT. A production rung on this axis is not a
fifth model, it is the ABSENCE of the axis, so it would be a bar with no family on it
sitting beside four that have one -- a comparison whose control is the thing being
compared. See sem_specificity.py for the same premise failing the same way.

WHAT IT SHOULD BECOME: a ladder over the axis production still has, which is the
candidate stage. That ladder exists -- `sem_rungs.py`, which decomposes the seven-radius
union by the rung that first marks each pixel, through
`angle4_shipped.seg_fn(ladder=(sigma,))` so no rung can drift from the app, and which
asserts both the ladder-collapse control and that the seven one-rung cuts partition the
union. `sem_rungs.json` is its record. This file should not be rewritten into that; it
already exists, and two runners computing the same quantity is how they come to disagree.

WHAT THIS FILE IS FOR, now: it remains a correct measurement of the ARCHIVED published
pipeline, which is a legitimate subject for the paper, and it is the evidence behind
figure 2's "why linear" panel -- the comparison that chose the family whose verdict is now
discarded. Nothing in the shipped figure chain reads its `lad_*.npy`; it is a research
runner, not a figure stage. A caption built on it may say "the published region
classifier"; it may not say deployed, shipped, or what the app runs.

Scope, for the avoidance of doubt: ARCHIVED v1.47 SEM pipeline -- one flattening radius
(sigma = 40) and the logistic region classifier. v1.49.2 runs neither. Deleting the
classifier won on every metric with zero free parameters (paired median IoU +0.1753 over
13 specimens, 11 of 13 better, Wilcoxon p = 0.0061), and it ended a dead zone in which
three ETD specimens scored recall 0.0000 at every candidate setting ever tried. See
analysis/detector_overrides.py and paper/figures/sem_production.json.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import os, sys, json
import numpy as np
S = _paths.require(_paths.SEM_REPO, "the sem-crack-detector checkout", "SEM_REPO")
sys.path.insert(0, os.path.join(S, "code"))
sys.path.insert(0, os.path.join(S, "interior_active_learning", "code"))
import detect_cracks as D
from train_v3_weighted import MODELS, image_weights, FEATURES, held_out_images
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, confusion_matrix
from scipy import ndimage as ndi
from PIL import Image
import pandas as pd
Image.MAX_IMAGE_PIXELS = None
OUT = os.path.dirname(os.path.abspath(__file__))
FRAME, X0, Y0, SIDE = "MAR_H_AS_CBS_0004", 400, 1600, 1200

print("FEATURES:", FEATURES)
df = pd.read_csv(f"{S}/training_data/labeled_regions.csv").dropna(subset=FEATURES)
X = df[FEATURES].values
y = df["IsCrack"].astype(bool).values
groups = df["SourceImage"].values
W = image_weights(groups)
print(f"training rows {len(df)}  crack {int(y.sum())}  not {int((~y).sum())}  images {len(set(groups))}")
assert FRAME not in set(groups), f"{FRAME} is IN the training set; the ladder would not be out of sample"

# ---- the frame's candidate regions, from the shipped pipeline on the FULL frame ----
img8 = D.load_as_uint8(f"{S}/original/{FRAME}.tif")
gated = np.asarray(Image.open(f"{S}/crack_export/derived/gated_masks/{FRAME}_gated.png").convert("L")) < 128
h = min(img8.shape[0], gated.shape[0]); w = min(img8.shape[1], gated.shape[1])
img8, gated = img8[:h, :w], gated[:h, :w]
flat = D.flatten_background(img8)
ves = D.compute_vesselness(flat)
clean = D.clean_mask(D.segment_dark_regions(flat, img8=img8))
labeled, cand = D.region_features_from_labeled(ndi.label(clean)[0], flat, ves)
print(f"frame {w}x{h}: {len(cand)} candidate regions")
Xf = cand[FEATURES].values

# ---- each family, fitted identically, scored on the frame ----
sl = (slice(Y0, Y0+SIDE), slice(X0, X0+SIDE))
np.save(f"{OUT}/lad_img8.npy", img8[sl]); np.save(f"{OUT}/lad_gated.npy", gated[sl])
np.save(f"{OUT}/lad_clean.npy", clean[sl])

held, how = held_out_images(groups)
te = np.isin(groups, held)
print(f"holdout for the reported AUC: {how}  ({int(te.sum())} rows, "
      f"{int(y[te].sum())} crack / {int((~y[te]).sum())} not)")

rows = []
for name, factory in MODELS.items():
    sc = StandardScaler().fit(X)
    clf = factory()
    clf.fit(sc.transform(X), y, sample_weight=W)
    p = clf.predict_proba(sc.transform(Xf))[:, 1]
    keep = p >= 0.5
    pm = np.zeros(labeled.max()+1, np.float32); km = np.zeros(labeled.max()+1, bool)
    for lb, pp, kk in zip(cand["Label"].values, p, keep):
        pm[int(lb)] = pp; km[int(lb)] = bool(kk)
    mask = km[labeled]
    np.save(f"{OUT}/lad_mask_{name.split()[0]}.npy", mask[sl])
    np.save(f"{OUT}/lad_prob_{name.split()[0]}.npy", pm[labeled][sl])

    # the honest held-out score for this family, refit without the exhaustive image
    sc2 = StandardScaler().fit(X[~te]); c2 = factory()
    c2.fit(sc2.transform(X[~te]), y[~te], sample_weight=W[~te])
    pte = c2.predict_proba(sc2.transform(X[te]))[:, 1]
    auc = float(roc_auc_score(y[te], pte))
    tn, fp, fn, tp = confusion_matrix(y[te], pte >= 0.5, labels=[False, True]).ravel()
    g = gated[sl]; m = mask[sl]
    rows.append(dict(model=name,
                     loio_auc=round(auc, 4),
                     loio_recall=round(tp/max(tp+fn, 1), 4),
                     loio_spec=round(tn/max(tn+fp, 1), 4),
                     loio_fp=int(fp), loio_n=int(te.sum()),
                     frame_kept=int(keep.sum()), frame_candidates=int(len(cand)),
                     frame_area_pct=round(100*float(mask.mean()), 4),
                     window_area_pct=round(100*float(m.mean()), 3),
                     window_iou=round(float((m & g).sum()/max((m | g).sum(), 1)), 4),
                     window_recall=round(float((m & g).sum()/max(g.sum(), 1)), 4),
                     window_precision=round(float((m & g).sum()/max(m.sum(), 1)), 4)))
    print(f"  {name:22} LOIO AUC {auc:.4f}  spec {tn/max(tn+fp,1):.3f}  fp {fp:5}  |  "
          f"frame keeps {int(keep.sum()):3}/{len(cand)}  window IoU {rows[-1]['window_iou']:.3f}  "
          f"area {rows[-1]['window_area_pct']:.2f}%")

meta = dict(frame=FRAME, crop=[X0, Y0, SIDE], full=[int(w), int(h)], nm_per_px=51.883,
            n_candidates=int(len(cand)), holdout=how,
            holdout_rows=int(te.sum()), holdout_neg=int((~y[te]).sum()),
            train_rows=len(df), train_pos=int(y.sum()), train_neg=int((~y).sum()),
            train_images=len(set(groups)),
            window_gated_pct=round(100*float(gated[sl].mean()), 3),
            rows=rows)
json.dump(meta, open(f"{OUT}/sem_ladder.json", "w"), indent=1)
print("\nwrote", f"{OUT}/sem_ladder.json")
