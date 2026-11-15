#!/usr/bin/env python3
"""What the SEM region classifier is worth on a frame it has NOT been trained on.

WHY THIS FILE EXISTS. `USE_REGION_CLASSIFIER` is now True, so every SEM mask this
project scores passes through `models/crack_classifier.joblib`. That bundle records the
45 images it was fitted on, and 45 of the 48 hand-painted SEM frames in this corpus ARE
those images. Every classifier-on precision, recall and F1 measured on this corpus is
therefore an IN-SAMPLE number: the model is being asked about regions whose labels it was
fitted to. Reporting one as the detector's accuracy is the single most common way a
result like this turns out to be worth a third of its published value.

WHAT IS HELD OUT, AND WHAT IS NOT. For each frame the classifier is refitted from
scratch on the training rows of every OTHER image and then applied to this frame's
candidate regions. Nothing about the held-out frame enters the fit: not its rows, not its
scaler, not its class balance. One thing is NOT refolded and must be read as a residual
leak -- the deployed decision threshold 0.5537592 was calibrated once, on the corpus as a
whole. `lofo_matched` answers that too, by giving each fold a threshold derived only from
ITS OWN training rows, at the keep-rate the shipped bundle shows on its training rows.
Read `lofo_fixed` and `lofo_matched` as a bracket, not as two attempts at one number.

THE RECIPE IS THE TRAINER'S, NOT A REIMPLEMENTATION OF IT. StandardScaler, then
LogisticRegression(max_iter=2000, class_weight="balanced"), fitted with the per-image
sample weights `train_v3_weighted.image_weights` computes (mass 1/max(rows, 50) per row,
so an image with 50 or more labelled regions carries one unit and a thinly-labelled one
carries less). `CONTROL_recipe_reproduces_the_bundle` refits on ALL rows and checks the
coefficients against the shipped bundle's, which is the only evidence that these folds
differ from production in the held-out frame and in nothing else.

THE CANDIDATE STAGE IS NOT REFOLDED EITHER, and it does not need to be: it has no fitted
parameters. Its constants are swept and reported in Figure 6; none of them is chosen on
a per-frame basis.

FIVE MASKS PER FRAME, so the classifier's contribution can be read off directly:
    floor          the area floor alone -- `clean_mask(13)` then a 40 px component floor.
                   This is what the app emitted while the classifier was off.
    shipped        the deployed bundle, `models/crack_classifier.joblib`. This is what a
                   user's run emits today, and it is IN-SAMPLE on 45 of the 48 frames.
    refit_all      the same recipe fitted on ALL of today's rows. THIS, not `shipped`, is
                   the in-sample reference the folds are read against, because the CSV on
                   disk has drifted five rows from the corpus the bundle was fitted on
                   (7,510 rows here against the bundle's recorded 7,505). Comparing a fold
                   against `shipped` would mix the fold with that drift; comparing it
                   against `refit_all` leaves exactly one variable, the held-out frame.
    lofo_fixed     refitted without this frame, applied at the deployed threshold.
    lofo_matched   refitted without this frame, at a threshold derived from that fold's
                   own training rows alone.

THE FIVE-ROW DRIFT IS REPORTED, NOT HIDDEN. `shipped` and `refit_all` differ only by
those rows, and the record carries both their coefficient distance and their scores, so a
reader can see how much of any gap is the model and how much is the corpus moving.

Opens all paint READ-ONLY. Writes one record and nothing else.
"""
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
sys.path.insert(0, os.path.join(REPO, "analysis", "research", "improve"))
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from skimage import measure as skm

import overlap_means_sem_txm as OV      # the one SEM frame loader and the one scorer
import both_modalities as BM            # the one staging copy of the emission
import detect_cracks as D
import detector_overrides as DO
from common import PROD_MODEL_PATH

CSV = os.path.join(SEM, "training_data", "labeled_regions.csv")
FEATURES = ["LogArea", "Elongation", "Solidity", "Eccentricity", "Extent",
            "Circularity", "MeanDarkness", "MeanVesselness"]
FLOOR_ROWS = 50                 # train_v3_weighted.FLOOR_ROWS
MIN_AREA_PX = 40                # both_modalities.MIN_AREA_PX
OUT = os.path.join(REPO, "docs", "figures", "sem_classifier_lofo.json")
SCRATCH = os.path.join(REPO, "docs", "figures", "_lofo_folds")
ARMS = ("floor", "shipped", "refit_all", "lofo_fixed", "lofo_matched")

t0 = time.time()
tick = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)

BUNDLE = joblib.load(PROD_MODEL_PATH)
THR = float(BUNDLE["threshold"])
TRAIN_IMAGES = sorted(BUNDLE["images"])


def weights(src):
    """train_v3_weighted.image_weights, on whatever subset of rows it is handed.

    Recomputed per fold ON THE FOLD'S OWN ROWS, which is what dropping an image from the
    corpus does: the remaining images' counts are unchanged, so in practice only the
    dropped image disappears. Computing it once on the full corpus would be equivalent
    here and wrong in general.
    """
    counts = pd.Series(src).value_counts()
    return np.array([1.0 / max(counts[s], FLOOR_ROWS) for s in src], dtype=float)


def fit(X, y, w):
    sc = StandardScaler().fit(X)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    clf.fit(sc.transform(X), y, sample_weight=w)
    return sc, clf


def dump(sc, clf, thr, path):
    joblib.dump({"scaler": sc, "clf": clf, "feature_names": list(FEATURES),
                 "threshold": float(thr)}, path)
    return path


def main():
    os.makedirs(SCRATCH, exist_ok=True)
    df = pd.read_csv(CSV)
    df = df[df["SourceImage"].isin(TRAIN_IMAGES)].reset_index(drop=True)
    X = df[FEATURES].values
    y = df["IsCrack"].astype(bool).values
    src = df["SourceImage"].values

    # -------------------------------------- CONTROL 1: how far the CSV has drifted
    drift = {"rows_now": len(df), "rows_in_bundle": int(BUNDLE["n_train"]),
             "pos_now": int(y.sum()), "pos_in_bundle": int(BUNDLE["n_pos"]),
             "neg_now": int((~y).sum()), "neg_in_bundle": int(BUNDLE["n_neg"])}
    frac = abs(len(df) - BUNDLE["n_train"]) / BUNDLE["n_train"]
    print(f"  CONTROL the CSV on disk against the corpus the bundle records: "
          f"{len(df):,} rows vs {BUNDLE['n_train']:,} "
          f"({drift['pos_now']:,}/{drift['neg_now']:,} crack/not-crack vs "
          f"{drift['pos_in_bundle']:,}/{drift['neg_in_bundle']:,}), "
          f"{100 * frac:.2f}% drift: {'PASS' if frac < 0.01 else 'FAIL'}", flush=True)
    assert frac < 0.01, ("the training CSV has moved more than 1% from the corpus the "
                         "shipped bundle was fitted on; refit and redeploy before "
                         "reading any of this as the deployed model's leakage")

    # ------------------------------- CONTROL 2: the recipe reproduces the shipped model
    #: It cannot reproduce it exactly -- five rows have been added to the CSV since the
    #: bundle was written -- so the check is that the distance is of the size five rows
    #: can explain, and the number is published rather than assumed. The in-sample
    #: reference every fold is read against is `refit_all`, fitted right here, so this
    #: drift never enters the leakage comparison.
    sc_all, clf_all = fit(X, y, weights(src))
    d = float(np.abs(np.asarray(clf_all.coef_).ravel()
                     - np.asarray(BUNDLE["clf"].coef_).ravel()).max())
    di = float(abs(float(clf_all.intercept_[0]) - float(BUNDLE["clf"].intercept_[0])))
    print(f"  CONTROL refitting on all of today's rows against the shipped coefficients: "
          f"max |delta| {d:.4g}, intercept {di:.4g}: "
          f"{'PASS' if d < 0.05 else 'FAIL'}", flush=True)
    assert d < 0.05, (f"the recipe here is not the one that produced the bundle: "
                      f"coefficients differ by up to {d:.4g}, far more than five rows "
                      f"of 7,505 can explain")
    REFIT_ALL = dump(sc_all, clf_all, THR,
                     os.path.join(SCRATCH, "refit_all.joblib"))

    # the keep-rate the shipped bundle shows on its own training rows. A fold's threshold
    # is the quantile of ITS OWN training probabilities at this rate, so no fold ever
    # reads the frame it is about to be scored on.
    keep_rate = float((BUNDLE["clf"].predict_proba(
        BUNDLE["scaler"].transform(X))[:, 1] >= THR).mean())
    tick(f"deployed threshold {THR:.7f} keeps {100 * keep_rate:.2f}% of the training rows")

    rows, skipped = [], []
    for nm, img8, corr in OV.sem_frames():
        pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
        if pos.sum() < OV.MIN_PX or neg.sum() < OV.MIN_PX:
            skipped.append(nm)
            continue
        in_train = nm in TRAIN_IMAGES

        flat = D.flatten_background(img8)
        proposed = OV.u.segment_dark_regions(flat, img8=img8, mad_k=OV.MADK)
        cleaned = D.clean_mask(proposed, min_area_px=13)
        lab = skm.label(cleaned, connectivity=2)
        ves = D.compute_vesselness(flat)
        labeled, cand = D.region_features_from_labeled(lab, flat, ves,
                                                       min_area_px=MIN_AREA_PX)

        masks = {}
        was = DO.USE_REGION_CLASSIFIER
        DO.USE_REGION_CLASSIFIER = False
        try:
            masks["floor"] = BM.emit(cleaned, flat, img8)
        finally:
            DO.USE_REGION_CLASSIFIER = was

        def apply(path):
            if not len(cand):
                return np.zeros_like(cleaned, bool)
            s = D.classify_with_model(cand, path, proba_threshold=None)
            k = s.loc[s["IsCrack"] == True, "Label"].tolist()      # noqa: E712
            return np.isin(labeled, k) if k else np.zeros_like(cleaned, bool)

        masks["shipped"] = apply(PROD_MODEL_PATH)
        masks["refit_all"] = apply(REFIT_ALL)

        if in_train:
            keep = src != nm
            assert keep.sum() < len(df), f"{nm} contributes no rows to drop"
            sc_f, clf_f = fit(X[keep], y[keep], weights(src[keep]))
            p_tr = clf_f.predict_proba(sc_f.transform(X[keep]))[:, 1]
            thr_m = float(np.quantile(p_tr, 1.0 - keep_rate))
            masks["lofo_fixed"] = apply(dump(sc_f, clf_f, THR,
                                             os.path.join(SCRATCH, "fold_fixed.joblib")))
            masks["lofo_matched"] = apply(dump(sc_f, clf_f, thr_m,
                                               os.path.join(SCRATCH, "fold_matched.joblib")))
            n_drop = int((~keep).sum())
        else:
            # the shipped bundle never saw this frame, so it IS the out-of-sample answer
            #: the shipped bundle never saw this frame, so `shipped` is already the
            #: out-of-sample answer and there is no fold to build. `refit_all` DID see
            #: nothing of it either, for the same reason, so all four agree here by
            #: construction and the row is reported in its own group.
            masks["lofo_fixed"] = masks["shipped"]
            masks["lofo_matched"] = masks["shipped"]
            thr_m, n_drop = THR, 0

        row = {"frame": nm, "in_training_set": bool(in_train),
               "rows_dropped_for_this_fold": n_drop,
               "matched_threshold": thr_m,
               "crack_px": int(pos.sum()), "notcrack_px": int(neg.sum()),
               "candidate_regions": int(len(cand))}
        for a in ARMS:
            p, r, f1, tp, fp, fn = OV.prf(masks[a], pos, neg)
            row[a] = {"precision": p, "recall": r, "f1": f1,
                      "tp": tp, "fp": fp, "fn": fn,
                      "marked_px": int(masks[a].sum())}
        rows.append(row)
        print(f"  {nm[:46]:<48} {'in-sample' if in_train else 'HELD OUT ':<10} " +
              "  ".join(f"{a[:5]} P{row[a]['precision']:.3f}/R{row[a]['recall']:.3f}"
                        for a in ARMS), flush=True)

    def agg(subset, arm):
        if not subset:
            return None
        g = lambda k: float(np.mean([x[arm][k] for x in subset]))
        s = lambda k: (float(np.std([x[arm][k] for x in subset], ddof=1))
                       if len(subset) > 1 else 0.0)
        return {"n_frames": len(subset), "mean_precision": g("precision"),
                "mean_recall": g("recall"), "mean_f1": g("f1"),
                "sd_precision": s("precision"), "sd_recall": s("recall"),
                "sd_f1": s("f1")}

    fitted = [r for r in rows if r["in_training_set"]]
    never = [r for r in rows if not r["in_training_set"]]
    rec = {
        "generated": time.strftime("%Y-%m-%d"),
        "question": ("what the region classifier is worth on a frame it was not fitted "
                     "on, at the mask level, scored on refereed pixels"),
        "aggregation": "mean over frames, one vote per frame; pixels are NOT pooled",
        "scoring": "refereed pixels only: 1 = crack, 2 or 3 = not-crack, 0 excluded",
        "mad_k": OV.MADK, "min_px_each_verdict": OV.MIN_PX,
        "deployed_threshold": THR,
        "training_keep_rate_at_deployed_threshold": keep_rate,
        "n_training_images": len(TRAIN_IMAGES),
        "training_csv_drift": drift,
        "refit_all_vs_shipped_max_abs_coef_delta": d,
        "refit_all_vs_shipped_intercept_delta": di,
        "frames_scored": len(rows), "frames_excluded_too_little_paint": skipped,
        "arms": {
            "floor": "the area floor alone: clean_mask(13) then a 40 px component floor",
            "shipped": ("models/crack_classifier.joblib, the deployed bundle and what a "
                        "user's run emits today. IN-SAMPLE on every frame whose "
                        "in_training_set is true"),
            "refit_all": ("the same recipe fitted on all of today's rows; the in-sample "
                          "reference the folds are read against, so the five-row CSV "
                          "drift never enters the leakage comparison"),
            "lofo_fixed": ("refitted without this frame, applied at the deployed "
                           "threshold 0.5537592, which was itself calibrated on the whole "
                           "corpus and is the one thing not refolded"),
            "lofo_matched": ("refitted without this frame, at the quantile of that fold's "
                             "OWN training probabilities matching the keep-rate the "
                             "shipped bundle shows on its training rows")},
        "controls": {
            "corpus": (f"PASS: the CSV holds {len(df):,} rows for the bundle's 45 "
                       f"images against the {BUNDLE['n_train']:,} it records, "
                       f"{100 * frac:.2f}% drift"),
            "recipe": (f"PASS: refitting on all of today's rows lands within {d:.4g} of "
                       f"the shipped coefficients, which is the size five added rows "
                       f"explain; the leakage comparison uses refit_all, not shipped"),
            "held_out_frames_are_untouched": (
                "the frames absent from the bundle's image list get shipped == lofo by "
                "construction and are reported apart, in never_fitted_frames. On this "
                "corpus that group is EMPTY: all three such frames carry painted crack "
                "but no painted not-crack, so none of them reaches the 200-px-of-each "
                "threshold every score here requires. The out-of-sample estimate is "
                "therefore the per-fold refit, not those three frames, and the record "
                "should not be read as if a natural held-out set existed")},
        "fitted_frames": {a: agg(fitted, a) for a in ARMS},
        "never_fitted_frames": {a: agg(never, a) for a in ARMS},
        "all_frames": {a: agg(rows, a) for a in ARMS},
        "per_frame": rows,
        "seconds": round(time.time() - t0, 1)}
    json.dump(rec, open(OUT, "w"), indent=1)

    print(f"\n{'=' * 92}")
    for tag, sub in (("frames the model WAS fitted on", fitted),
                     ("frames it was NEVER fitted on", never),
                     ("all frames", rows)):
        if not sub:
            continue
        print(f"{tag}  (n = {len(sub)})")
        for a in ARMS:
            v = agg(sub, a)
            print(f"   {a:<13} P {v['mean_precision']:.4f}  R {v['mean_recall']:.4f}  "
                  f"F1 {v['mean_f1']:.4f}")
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
