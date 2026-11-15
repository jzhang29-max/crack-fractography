"""How much of the SEM mask the model is actually allowed to decide.

`detect_cracks.classify_with_model` force-keeps any region of at least `force_keep_area`
(50,000 px by default) whatever the model says, because a dark region that large is in
practice never anything but a real crack or void. On 512 px tiles almost nothing reaches
that size. On a whole micrograph the main crack is one component of millions of pixels.
If the force-keep rule covers most of the mask's AREA at frame scale, then the classifier
is nearly inert there, and that -- not the model being good -- is why the frame-scale
scores barely move when it is switched on.
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
sys.path.insert(0, os.path.join(REPO, "analysis", "research", "improve"))
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))
sys.dont_write_bytecode = True
import json
import numpy as np
from skimage import measure as skm
import overlap_means_sem_txm as OV
import detect_cracks as D
from common import PROD_MODEL_PATH

FORCE = 50000
rows = []
#: NAMED FRAMES ARE FOR DEBUGGING ONLY. The committed record is written by running this
#: with no arguments, over every frame `overlap_means_sem_txm.sem_frames()` yields that
#: carries enough paint to be scored -- the same frame set the scores are computed on.
#: A pooled share over a hand-picked handful would be a selection, and the first version
#: of this file was run that way on four frames chosen partly BECAUSE one of them showed
#: the largest classifier effect. The record records which it was.
want = set(sys.argv[1:]) or None
for nm, img8, corr in OV.sem_frames():
    if want and nm not in want:
        continue
    pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
    if pos.sum() < OV.MIN_PX or neg.sum() < OV.MIN_PX:
        continue        # the same frames the scores are computed on, and no others
    flat = D.flatten_background(img8)
    proposed = OV.u.segment_dark_regions(flat, img8=img8, mad_k=OV.MADK)
    cleaned = D.clean_mask(proposed, min_area_px=13)
    lab = skm.label(cleaned, connectivity=2)
    ves = D.compute_vesselness(flat)
    labeled, df = D.region_features_from_labeled(lab, flat, ves, min_area_px=40)
    if not len(df):
        continue
    sc = D.classify_with_model(df, PROD_MODEL_PATH, proba_threshold=None)
    forced = sc["Area"] >= FORCE
    model_yes = sc["CrackProbability"] >= 0.5537592016924066
    kept = sc["IsCrack"] == True                                    # noqa: E712
    area = sc["Area"].astype(float)
    r = dict(frame=nm, n_regions=int(len(sc)),
             n_forced=int(forced.sum()), n_kept=int(kept.sum()),
             candidate_px=float(area.sum()),
             kept_px=float(area[kept].sum()),
             forced_px=float(area[forced].sum()),
             model_rejected_but_forced_px=float(area[forced & ~model_yes].sum()),
             model_rejected_but_forced_n=int((forced & ~model_yes).sum()))
    r["forced_share_of_kept_area"] = r["forced_px"] / max(r["kept_px"], 1)
    r["forced_share_of_regions"] = r["n_forced"] / max(r["n_regions"], 1)
    rows.append(r)
    print(f"  {nm[:44]:<46} regions {r['n_regions']:>6}  forced {r['n_forced']:>4} "
          f"({100*r['forced_share_of_regions']:5.2f}% of regions, "
          f"{100*r['forced_share_of_kept_area']:6.2f}% of kept AREA); "
          f"the model rejected {r['model_rejected_but_forced_n']} of those, "
          f"{r['model_rejected_but_forced_px']:,.0f} px kept over its objection",
          flush=True)

if rows:
    ka = sum(r["kept_px"] for r in rows)
    fa = sum(r["forced_px"] for r in rows)
    print(f"\npooled over {len(rows)} frames: {100*fa/ka:.2f}% of the kept area is "
          f"force-kept, so the model decides {100*(1-fa/ka):.2f}% of it")
    json.dump({"force_keep_area": FORCE, "frames": rows,
               "frame_selection": ("every scorable SEM frame" if want is None else
                                   "NAMED FRAMES ONLY, a selection: "
                                   + ", ".join(sorted(want))),
               "is_the_whole_frame_set": want is None,
               "n_frames": len(rows),
               "pooled_forced_share_of_kept_area": fa / ka},
              open(os.path.join(REPO, "docs", "figures",
                                "sem_force_keep_share.json"), "w"), indent=1)
    print("wrote docs/figures/sem_force_keep_share.json")
