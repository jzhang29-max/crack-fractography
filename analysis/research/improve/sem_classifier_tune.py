#!/usr/bin/env python3
"""Tune the SEM region classifier on THIS laboratory's own frames, honestly.

WHAT THE EVIDENCE SAYS BEFORE TUNING STARTS, because it sets the bar. On the 18 frames
that carry enough of both verdicts to be scored, leave-one-frame-out:

    no classifier at all   P 0.9486  R 0.5525  F1 0.6470
    deployed classifier    P 0.9586  R 0.5341  F1 0.6363   (LOFO refit)

The classifier as deployed COSTS F1 at frame scale. It is run at a threshold of 0.5538
that was calibrated on a different question, and the obvious thing nobody has tried is
to choose that threshold for this corpus. A lower threshold keeps more regions, trading
the precision the classifier buys back for the recall it costs.

THE PROTOCOL IS NESTED, which is the whole reason this file is careful. For each frame:
the model is refitted without that frame's training rows, AND the threshold is chosen by
maximising mean F1 over the OTHER frames only. The held-out frame contributes to neither
the fit nor the threshold. A threshold picked on all 18 and then reported on all 18
would be selection on the test set and would beat everything here by construction.

ARMS
    floor          the area floor alone, no classifier
    deployed       the shipped bundle at its shipped threshold
    tuned_logistic the shipped recipe, threshold chosen nested
    tuned_gbt      a gradient-boosted tree, threshold chosen nested

    <sem venv>/python -B sem_classifier_tune.py
"""
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
sys.path.insert(0, os.path.join(REPO, "analysis", "research", "improve"))
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from skimage import measure as skm

import overlap_means_sem_txm as OV
import both_modalities as BM
import detect_cracks as D
import detector_overrides as DO
import sem_classifier_lofo as LF
from common import PROD_MODEL_PATH

OUT = os.path.join(REPO, "docs", "figures", "sem_classifier_tuned.json")
CACHE = os.path.join(REPO, "docs", "figures", "_tunecache")
GRID = np.linspace(0.05, 0.95, 91)
t0 = time.time()
tick = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)


def harvest():
    """Per scorable frame: region map, features, paint. Cached, because it is the
    expensive half and the tuning below is run more than once."""
    os.makedirs(CACHE, exist_ok=True)
    out = []
    for nm, img8, corr in OV.sem_frames():
        pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
        if pos.sum() < OV.MIN_PX or neg.sum() < OV.MIN_PX:
            continue
        p = os.path.join(CACHE, nm + ".npz")
        if os.path.exists(p):
            z = np.load(p, allow_pickle=True)
            out.append(dict(name=nm, labeled=z["labeled"], ids=z["ids"], X=z["X"],
                            pos=z["pos"], neg=z["neg"], floor=z["floor"],
                            tp_r=z["tp_r"], fp_r=z["fp_r"],
                            pos_n=int(z["pos_n"])))
            tick(f"  cached {nm[:46]}")
            continue
        flat = D.flatten_background(img8)
        proposed = OV.u.segment_dark_regions(flat, img8=img8, mad_k=OV.MADK)
        cleaned = D.clean_mask(proposed, min_area_px=13)
        lab = skm.label(cleaned, connectivity=2)
        ves = D.compute_vesselness(flat)
        labeled, df = D.region_features_from_labeled(lab, flat, ves, min_area_px=40)
        was = DO.USE_REGION_CLASSIFIER
        DO.USE_REGION_CLASSIFIER = False
        try:
            floor = BM.emit(cleaned, flat, img8)
        finally:
            DO.USE_REGION_CLASSIFIER = was
        ids_ = (df["Label"].to_numpy() if len(df) else np.array([], int))
        #: PER-REGION OVERLAPS, COMPUTED ONCE. The tuning below evaluates tens of
        #: thousands of (fold, threshold) pairs, and rebuilding a 25-megapixel mask
        #: for each one takes hours. tp and fp are additive over disjoint regions, so
        #: the score of ANY kept set is a sum of these two vectors and fn follows from
        #: the painted total. Exact, not an approximation.
        #: ONE PASS, NOT ONE PER REGION. `(labeled == i)` inside a loop is
        #: O(regions x pixels) -- 572 regions over a 25-megapixel frame is fourteen
        #: billion comparisons, and the first version of this file sat there silently.
        #: bincount over the labels under each verdict is the same answer in one pass.
        _nl = int(labeled.max()) + 1
        _tp = np.bincount(labeled[pos].ravel(), minlength=_nl)
        _fp = np.bincount(labeled[neg].ravel(), minlength=_nl)
        tp_r = _tp[ids_].astype(np.int64) if len(ids_) else np.zeros(0, np.int64)
        fp_r = _fp[ids_].astype(np.int64) if len(ids_) else np.zeros(0, np.int64)
        d = dict(name=nm, labeled=labeled.astype(np.int32),
                 tp_r=tp_r, fp_r=fp_r, pos_n=np.int64(pos.sum()),
                 ids=ids_,
                 X=(df[LF.FEATURES].to_numpy() if len(df)
                    else np.zeros((0, len(LF.FEATURES)))),
                 pos=pos, neg=neg, floor=floor)
        np.savez_compressed(p, **{k: v for k, v in d.items() if k != "name"})
        out.append(d)
        tick(f"  harvested {nm[:46]}  ({len(d['ids'])} regions)")
    return out


def fast_prf(f, keep_bool):
    """precision, recall, F1 for a kept set, from the cached per-region overlaps."""
    tp = int(f["tp_r"][keep_bool].sum()); fp = int(f["fp_r"][keep_bool].sum())
    fn = int(f["pos_n"]) - tp
    p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def CONTROL_fast_scorer_agrees(frames):
    """The fast scorer must equal the pixel scorer, or every number below is fiction."""
    for f in frames[:3]:
        if not len(f["ids"]):
            continue
        kb = np.ones(len(f["ids"]), bool)
        m = np.isin(f["labeled"], f["ids"])
        a, b = fast_prf(f, kb), OV.prf(m, f["pos"], f["neg"])[:3]
        assert max(abs(x - y) for x, y in zip(a, b)) < 1e-9, (f["name"], a, b)
    print("  CONTROL the per-region scorer reproduces the pixel scorer: PASS",
          flush=True)


def main():
    frames = harvest()
    tick(f"{len(frames)} scorable frames")

    csv = pd.read_csv(LF.CSV)
    csv = csv[csv["SourceImage"].isin(LF.TRAIN_IMAGES)].reset_index(drop=True)
    X, y = csv[LF.FEATURES].values, csv["IsCrack"].astype(bool).values
    src = csv["SourceImage"].values

    def fold_probs(kind):
        """Per frame, region probabilities from a model refitted without that frame."""
        P = {}
        for f in frames:
            keep = src != f["name"]
            if not len(f["ids"]):
                P[f["name"]] = np.zeros(0)
                continue
            if kind == "logistic":
                sc, clf = LF.fit(X[keep], y[keep], LF.weights(src[keep]))
                P[f["name"]] = clf.predict_proba(sc.transform(f["X"]))[:, 1]
            else:
                sc = StandardScaler().fit(X[keep])
                clf = HistGradientBoostingClassifier(max_iter=200, random_state=0,
                                                     class_weight="balanced")
                clf.fit(sc.transform(X[keep]), y[keep],
                        sample_weight=LF.weights(src[keep]))
                P[f["name"]] = clf.predict_proba(sc.transform(f["X"]))[:, 1]
        return P

    def score_at(f, p, thr):
        if not len(f["ids"]):
            return 0.0, 0.0, 0.0
        return fast_prf(f, p >= thr)

    res = {}
    # ---- the two reference arms
    CONTROL_fast_scorer_agrees(frames)
    res["floor"] = [OV.prf(f["floor"], f["pos"], f["neg"])[:3] for f in frames]
    dep = []
    for f in frames:
        if not len(f["ids"]):
            dep.append((0.0, 0.0, 0.0))
            continue
        s = D.classify_with_model(
            pd.DataFrame(f["X"], columns=LF.FEATURES).assign(
                Label=f["ids"], Area=0.0), PROD_MODEL_PATH, proba_threshold=None)
        k = s.loc[s["IsCrack"] == True, "Label"].tolist()          # noqa: E712
        m = np.isin(f["labeled"], k) if k else np.zeros(f["pos"].shape, bool)
        dep.append(OV.prf(m, f["pos"], f["neg"])[:3])
    res["deployed"] = dep

    # ---- the tuned arms, threshold chosen on the OTHER frames
    chosen = {}
    for kind in ("logistic", "gbt"):
        tick(f"refitting {len(frames)} folds, {kind}")
        P = fold_probs(kind)
        rows, picks = [], []
        for i, f in enumerate(frames):
            others = [g for j, g in enumerate(frames) if j != i]
            best, bt = -1.0, 0.5
            for thr in GRID:
                s = float(np.mean([score_at(g, P[g["name"]], thr)[2] for g in others]))
                if s > best:
                    best, bt = s, float(thr)
            picks.append(bt)
            rows.append(score_at(f, P[f["name"]], bt))
        res["tuned_" + kind] = rows
        chosen["tuned_" + kind] = picks
        tick(f"  {kind}: thresholds chosen per fold, median {np.median(picks):.2f}")

    def agg(rows):
        return dict(precision=float(np.mean([r[0] for r in rows])),
                    recall=float(np.mean([r[1] for r in rows])),
                    f1=float(np.mean([r[2] for r in rows])))

    summary = {k: agg(v) for k, v in res.items()}
    best = max(summary, key=lambda k: summary[k]["f1"])
    rec = dict(generated=time.strftime("%Y-%m-%d"),
               n_frames=len(frames), mad_k=OV.MADK,
               protocol=("nested leave-one-frame-out: the model is refitted without "
                         "the held-out frame and the threshold is chosen on the other "
                         "frames only, so neither is selected on what it is scored on"),
               deployed_threshold=LF.THR,
               thresholds_chosen=chosen,
               arms=summary, best_arm=best,
               honest_conclusion=(
                   "the best arm is %s at F1 %.4f; the deployed configuration scores "
                   "%.4f and no classifier at all scores %.4f"
                   % (best, summary[best]["f1"], summary["deployed"]["f1"],
                      summary["floor"]["f1"])),
               per_frame={k: [dict(frame=f["name"], precision=r[0], recall=r[1],
                                   f1=r[2]) for f, r in zip(frames, v)]
                          for k, v in res.items()},
               seconds=round(time.time() - t0, 1))
    json.dump(rec, open(OUT, "w"), indent=2)
    print(f"\n{'=' * 72}\nmean over {len(frames)} frames, nested LOFO")
    for k in ("floor", "deployed", "tuned_logistic", "tuned_gbt"):
        v = summary[k]
        star = "  <-- best" if k == best else ""
        print(f"  {k:<16} P {v['precision']:.4f}  R {v['recall']:.4f}  "
              f"F1 {v['f1']:.4f}{star}")
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
