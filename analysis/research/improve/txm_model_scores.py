"""Collect the TXM detector's OWN scores into one file the manuscript can resolve against.

Three numbers exist for one model and they differ by 0.29 IoU. That is not a contradiction,
it is three scoring conventions, and the manuscript has to name which one it is quoting:

  grouped cross-validation   0.7921  -- 5 folds grouped by image, 250,000 sampled rows per
                                        fold drawn from HAND-PAINTED pixels, not whole frames
  labelled domain only       0.6748  -- median over 61 frames, IoU restricted to painted
                                        crack OR painted not-crack
  whole frame                0.507   -- median over 58 labelled frames at full resolution

Grouping is by IMAGE, not by specimen, and the labelled frames are four specimen groups, so
the cross-validated figure is not specimen-independent.

NOT CARRIED OVER: a triple of 0.726 / 0.786 / 0.811 appears in the caption of the legacy
generator paper/figures/mk_txm.py. No file in either repository reproduces it; the only
grouped-CV artefact is member_split_v4.json, whose members are v4 while the deployed models
are v5. It is therefore unsourced and is not quoted.

Writes docs/figures/txm_model_scores.json.
"""
import json
import os
import math
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))
import _paths  # noqa: E402

TXM = _paths.require(_paths.TXM_REPO, "the TXM_Crack_Detection_Pipeline checkout", "TXM_REPO")
CV = json.load(open(os.path.join(TXM, "research", "member_split_v4.json")))
CEIL = json.load(open(os.path.join(REPO, "paper", "figures", "txm_iou_ceiling_v2.json")))
STATS = json.load(open(os.path.join(REPO, "paper", "figures", "txm_stats.json")))

R = CEIL["per_frame"]
w = [r["label_width_px"] for r in R]
sh = [r["iou_shipped"] for r in R]
c3 = [r["iou_w3"] for r in R]


def _spearman(x, y):
    rx = {v: i for i, v in enumerate(sorted(range(len(x)), key=lambda k: x[k]))}
    ry = {v: i for i, v in enumerate(sorted(range(len(y)), key=lambda k: y[k]))}
    ax = [rx[i] for i in range(len(x))]
    ay = [ry[i] for i in range(len(y))]
    mx, my = st.mean(ax), st.mean(ay)
    num = sum((a - mx) * (b - my) for a, b in zip(ax, ay))
    den = math.sqrt(sum((a - mx) ** 2 for a in ax) * sum((b - my) ** 2 for b in ay))
    return num / den

out = {
    "what": "The TXM collection's own detector, scored three ways, plus the overlap ceiling "
            "its reference labels impose.",
    "generator": "analysis/research/improve/txm_model_scores.py",
    "cross_validated": {
        "convention": "5-fold grouped by IMAGE; 250,000 sampled rows per fold drawn from "
                      "hand-painted pixels, not whole frames; owner corrections only",
        "labelled_images_used": CV["labelled_images_used"],
        "grouped_by": CV["grouped_by"],
        "label_source": CV["label_source"],
        "model_version": "v4 members (member_split_v4.json); the deployed joblibs are v5 and "
                         "no v5 grouped-CV artefact exists in either repository",
        "ens_mean_iou": CV["mean_iou"],
        "ens_std_iou": CV["std_iou"],
        "ens_min_iou": CV["min_iou"],
        "f17_mean_iou": CV["mean_iou_17_only"],
        "hybrid_mean_iou": CV["mean_iou_hybrid_only"],
        "mean_precision": CV["mean_precision"],
        "mean_recall": CV["mean_recall"],
        "not_specimen_independent": "grouping is by image; the labelled frames span four "
                                    "specimen groups, so a whole specimen is never held out",
    },
    "labelled_domain": {
        "convention": CEIL["iou_convention"],
        "mask": 'effective_mask(corrections="none", tight=True) -- human paint excluded',
        "n_frames": CEIL["n_frames"],
        "median_iou": round(st.median(sh), 4),
        "median_3px_ceiling": round(st.median(c3), 4),
        "ratio_of_medians": round(st.median(sh) / st.median(c3), 2),
        "median_label_width_px": round(st.median(w), 2),
        "label_width_min_px": round(min(w), 1),
        "label_width_max_px": round(max(w), 1),
        "frames_where_correct_3px_trace_wins": sum(1 for r in R if r["iou_w3"] > r["iou_shipped"]),
        "spearman_model_iou_vs_label_width": round(_spearman(sh, w), 3),
        "spearman_3px_ceiling_vs_label_width": round(_spearman(c3, w), 3),
        "per_group": {g: CEIL["per_group"][g] for g in sorted(CEIL["per_group"])},
    },
    "whole_frame": {
        "convention": "full-resolution IoU against the operator's painted crack, whole frame",
        "n_frames": STATS["corpus_n"],
        "median_iou": STATS["corpus_median_iou"],
        "q1": STATS["corpus_q1"],
        "q3": STATS["corpus_q3"],
        "example_frame_iou": round(STATS["frame_iou"], 4),
        "example_frame_recall": round(STATS["frame_recall"], 4),
        "example_frame_fp_on_painted_notcrack": round(STATS["frame_fp_on_not"], 5),
    },
    "window_stages": {
        "note": "one 1100 px window of the example frame; these are not corpus figures",
        "threshold": STATS["threshold"],
        "operator_paint_pct": round(STATS["crop_label_pct"], 2),
        "f17_iou": round(STATS["p17_iou"], 4),
        "hybrid_iou": round(STATS["ph_iou"], 4),
        "ensemble_iou": round(STATS["crop_iou"], 4),
        "deployed_mask_pct": round(STATS["crop_mask_pct"], 2),
        "f17_pct": 59.23,
        "agreement_f17_vs_hybrid": 0.1324,
        "agreement_hybrid_vs_ensemble": 0.9377,
        "_agreement_source": "measured from the cached arrays by "
                             "paper/figures/mk_txm_stages.py; see its caption JSON",
    },
    "scale": {
        "nm_per_px": STATS["nm_per_px"],
        "provenance": "DERIVED from operator-supplied mosaic geometry, not read from "
                      "instrument metadata; marked [TODO-AUTHOR] in the TXM repository",
    },
}

dst = os.path.join(REPO, "docs", "figures", "txm_model_scores.json")
json.dump(out, open(dst, "w"), indent=1, ensure_ascii=False)
print("wrote", dst)
for k in ("cross_validated", "labelled_domain", "whole_frame"):
    print(f"  {k}: ", {kk: vv for kk, vv in out[k].items() if isinstance(vv, (int, float))})
