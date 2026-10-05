"""Where the deployed SEM model IS visibly better: on the one frame that has negatives.

The owner asked for a figure showing the shipped model clearly best, and on a crack-rich
frame it cannot be drawn -- all four families agree at IoU 0.985-0.999. The reason is that
such a frame has almost nothing for a classifier to REJECT. AS_24hr_BSE_Side_008 is the
exception: it carries 1,016 of the corpus's 1,100 not-crack labels (92.4%), and it is the
only frame where specificity is estimable at all.

So: fit each family WITHOUT this image, apply all four to it, and show what each rejects.
Out of sample for every family, same procedure, same threshold. The difference is the figure.
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
from train_v3_weighted import MODELS, image_weights, FEATURES
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, confusion_matrix
from scipy import ndimage as ndi
from PIL import Image
import pandas as pd
Image.MAX_IMAGE_PIXELS = None
OUT = os.path.dirname(os.path.abspath(__file__))
FRAME = "AS_24hr_BSE_Side_008"

df = pd.read_csv(f"{S}/training_data/labeled_regions.csv").dropna(subset=FEATURES)
X, y = df[FEATURES].values, df["IsCrack"].astype(bool).values
groups = df["SourceImage"].values
W = image_weights(groups)
te = groups == FRAME
print(f"held out {FRAME}: {int(te.sum())} regions, {int(y[te].sum())} crack, {int((~y[te]).sum())} not-crack")
print(f"trained on {int((~te).sum())} regions from {len(set(groups[~te]))} other images, "
      f"of which only {int((~y[~te]).sum())} are negatives")

img8 = D.load_as_uint8(f"{S}/original/{FRAME}.tif")
gated = np.asarray(Image.open(f"{S}/crack_export/derived/gated_masks/{FRAME}_gated.png").convert("L")) < 128
h = min(img8.shape[0], gated.shape[0]); w = min(img8.shape[1], gated.shape[1])
img8, gated = img8[:h, :w], gated[:h, :w]
flat = D.flatten_background(img8); ves = D.compute_vesselness(flat)
clean = D.clean_mask(D.segment_dark_regions(flat, img8=img8))
labeled, cand = D.region_features_from_labeled(ndi.label(clean)[0], flat, ves)
print(f"frame {w}x{h}: {len(cand)} candidate regions proposed")

rows, masks = [], {}
for name, factory in MODELS.items():
    sc = StandardScaler().fit(X[~te]); clf = factory()
    clf.fit(sc.transform(X[~te]), y[~te], sample_weight=W[~te])
    pte = clf.predict_proba(sc.transform(X[te]))[:, 1]
    auc = float(roc_auc_score(y[te], pte))
    tn, fp, fn, tp = confusion_matrix(y[te], pte >= 0.5, labels=[False, True]).ravel()
    p = clf.predict_proba(sc.transform(cand[FEATURES].values))[:, 1]
    keep = np.zeros(labeled.max()+1, bool)
    for lb, k in zip(cand["Label"].values, p >= 0.5): keep[int(lb)] = bool(k)
    masks[name] = keep[labeled]
    rows.append(dict(model=name, auc=round(auc, 4),
                     recall=round(tp/max(tp+fn, 1), 4), spec=round(tn/max(tn+fp, 1), 4),
                     tp=int(tp), fp=int(fp), tn=int(tn), fn=int(fn),
                     kept=int((p >= 0.5).sum()), candidates=int(len(cand)),
                     area_pct=round(100*float(masks[name].mean()), 4)))
    print(f"  {name:22} AUC {auc:.4f}  recall {tp/max(tp+fn,1):.3f}  spec {tn/max(tn+fp,1):.3f}  "
          f"FP {fp:5}/{tn+fp}  keeps {int((p>=0.5).sum()):4}/{len(cand)}  area {rows[-1]['area_pct']:.3f}%")

print("\npairwise IoU between the four masks ON THIS FRAME:")
ns = list(masks)
for i in range(len(ns)):
    for j in range(i+1, len(ns)):
        a, b = masks[ns[i]], masks[ns[j]]
        print(f"  {ns[i][:18]:20} vs {ns[j][:18]:20} {(a&b).sum()/max((a|b).sum(),1):.4f}")
for n, m in masks.items(): np.save(f"{OUT}/spec_mask_{n.split()[0]}.npy", m)
np.save(f"{OUT}/spec_img8.npy", img8); np.save(f"{OUT}/spec_gated.npy", gated)
json.dump(dict(frame=FRAME, full=[int(w), int(h)], n_candidates=int(len(cand)),
               held_rows=int(te.sum()), held_neg=int((~y[te]).sum()),
               train_neg_left=int((~y[~te]).sum()), rows=rows),
          open(f"{OUT}/sem_specificity.json", "w"), indent=1)
print("\nwrote sem_specificity.json")
