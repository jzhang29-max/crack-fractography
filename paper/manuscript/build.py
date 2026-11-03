"""Build the revised manuscript with the two added parts.

This renders `Revised_Manuscript` as supplied, plus the material it was missing:

  the restored comparison figures -- the operating-setting sweep and the width-sensitivity
  ceiling, both of which the supplied manuscript asserts in prose and does not show; and

  a new cross-modality section carrying the SEM detector to transmission X-ray microscopy,
  scored in the same area units.

It reuses `paper/make_paper.py` for page layout, text wrapping, tables and placeholder
resolution, so every number here comes from the same measurement files as the longer draft
and an unresolved name fails the build rather than rendering as a brace. Figures are
referenced as `[FIGURE key | caption]` so each one carries a real caption instead of a file
name -- a manuscript needs the caption to say which collection the panel is from, and the
longer draft's auto-generated captions cannot.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.dirname(HERE)
REPO = os.path.dirname(PAPER)
sys.path.insert(0, PAPER)
sys.dont_write_bytecode = True

import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_pdf import PdfPages

import make_paper as MP          # noqa: E402  -- Doc, resolve, VALUES, metrics, layout

OUT = os.path.join(HERE, "Revised_Manuscript_v2.pdf")
SECT = os.path.join(HERE, "sections")
# --- THE FIGURE PROGRAMME ----------------------------------------------------------
# Rebuilt after review. Five things changed, each in answer to a specific comment:
#
#   1. THE WORKFLOW COMES FIRST. `workflow` is Figure 1 and sits in the introduction. It
#      shows both modalities entering, converging on one detection rule, and diverging
#      into two readings that mean different physical things. The old Figure 1 was a row
#      of five SEM panels and said nothing about the second modality, which is half of
#      the paper.
#
#   2. HOW THE TWO MICROSCOPIES SEE A CRACK, in the introduction, because the reason the
#      paper carries a detector from one to the other cannot be judged without it.
#
#   3. PANELS THAT LOOKED THE SAME ARE COMBINED. The old stage plate had seven panels of
#      which four were indistinguishable at print size, and its whole-frame micrograph and
#      whole-frame result sat at opposite corners. `stages` has three columns -- the three
#      things that actually differ -- and what the combined stages removed is drawn in a
#      second colour inside a magnified inset.
#
#   4. BOTH MODALITIES IN ONE FIGURE WHEREVER THEY WERE TWO. `stages` replaces BOTH the
#      SEM stage plate (P6) and the TXM one (T6): 14 panels became 6.
#
#   5. TWO FIGURES THE PAPER DID NOT HAVE: what each measurand is, measured on one real
#      crack; and what over-counting and under-counting actually look like.
FIGS = {
    "workflow": os.path.join(PAPER, "figures/out/F1 - workflow.png"),
    "modality": os.path.join(
        PAPER, "figures/out/F2 - how each modality sees a crack.png"),
    "stages": os.path.join(
        PAPER, "figures/out/F3 - detection stages, both modalities.png"),
    "measurands": os.path.join(PAPER, "figures/out/F4 - what is measured.png"),
    "parameters": os.path.join(
        PAPER, "figures/out/F6 - how the parameters were determined.png"),
    "counting": os.path.join(PAPER, "figures/out/F5 - over- and under-counting.png"),
    "areabars": os.path.join(PAPER, "figures/out/P1 - public scores.png"),
    # ONE PLATE, NOT TWO. The sweep over the detector's free constant and the sweep
    # over the width the annotation is drawn at were a 1.5-column plate each, one line
    # apiece, and the review's note was that the pair is larger than what it says. They
    # are the same kind of statement on the same collections with the same markers.
    "sensitivity": os.path.join(PAPER, "figures/out/P2 - the two sensitivities.png"),
    "arms": os.path.join(PAPER, "figures/out/P4 - baselines.png"),
    "budget": os.path.join(PAPER, "figures/out/P5 - pixel budget.png"),
    # the overlap measures for the crack class, shown rather than only mentioned. It is
    # LAST in the results because the paper's primary endpoints are the ones computed
    # over every pixel of the frame, and this one is explicitly secondary to them.
    "overlap": os.path.join(PAPER, "figures/out/P8 - crack overlap.png"),
    "txm": os.path.join(PAPER, "figures/out/txm_transfer.png"),
    # the TXM collection has its OWN detector, which the supplied manuscript never
    # showed. T1 is its three rungs on one window; T2 is what its score measures.
    "txmstages": os.path.join(PAPER, "figures/out/T1 - TXM stages.png"),
    "txmceiling": os.path.join(PAPER, "figures/out/T2 - TXM ceiling.png"),
    # the SEM arm carried across got one plate where the SEM arm itself gets five. T3-T5
    # are the three it was missing: its operating curve, its pixel budget beside the two
    # no-information arms, and the overlap measures on both of this laboratory's own
    # collections with the ceiling each is read against.
    "txmcurve": os.path.join(PAPER, "figures/out/T3 - TXM operating curve.png"),
    "txmbudget": os.path.join(PAPER, "figures/out/T4 - TXM pixel budget.png"),
    "txmoverlap": os.path.join(PAPER, "figures/out/T5 - overlap with its ceiling.png"),
    # T6, the SEM detector's stages on a TXM frame, is RETIRED: `stages` now shows the
    # same three stages for both modalities side by side, and `counting` shows the
    # comparison with the operator's annotation that was T6's last panel.
}

# --- values this manuscript needs that the longer draft does not define ----------------
TX = MP._f(os.path.join(REPO, "docs/figures/txm_background_units.json"), "TXM")
TM = MP._f(os.path.join(REPO, "docs/figures/txm_model_scores.json"), "TXM model scores")
_cv, _ld, _wf, _ws = TM["cross_validated"], TM["labelled_domain"], TM["whole_frame"], TM["window_stages"]
_k6 = "SEM detector, mad_k=6"
_pool = TX["pooled"][_k6]


#: The two sweeps compared over the k values BOTH collections were run at, so neither
#: series is given a range the other was never measured on. The transmission grid is the
#: shorter of the two and sets the comparison.
_SWGRID = sorted(float(k.rsplit("=", 1)[1]) for k in TX["pooled"]
                 if k.startswith("SEM detector, mad_k="))
_SWSEM = {r["mad_k"]: r["area_agreement_corpus"]
          for r in MP._f(os.path.join(REPO, "docs/figures/background_counting_table.json"),
                         "background counting")["sweeps"]["whole_fields"]}
_missing = [k for k in _SWGRID if k not in _SWSEM]
if _missing:
    raise SystemExit(
        f"the transmission sweep was run at k = {_missing} and the SEM sweep was not, so "
        f"the two cannot be compared over a common grid. Shorten _SWGRID deliberately "
        f"rather than letting the comparison quietly span different ranges.")
_SWSPAN = ([_SWSEM[k] for k in _SWGRID],
           [TX["pooled"][f"SEM detector, mad_k={k:g}"]["area_agreement"]
            for k in _SWGRID])


#: The shipped detector's accuracy margin on each of the two cuts of the same images.
_AB = MP._f(os.path.join(REPO, "docs/figures/arms_background_units.json"),
            "arms in background units")["sets"]
_ARM = tuple(_AB[k]["arms"]["DETECTOR (shipped)"]["accuracy_pct"]
             - _AB[k]["empty_mask_accuracy_pct"] for k in ("whole_fields", "crops"))
if not (_ARM[0] < 0 < _ARM[1]):
    raise SystemExit(
        f"the baselines reversal is quoted as a sign change and the measured margins are "
        f"{_ARM} -- rewrite the sentence in Section 3.2 rather than letting it assert a "
        f"reversal that is no longer in the data")


def _rec(d):
    return d["tp_pct"] / max(d["tp_pct"] + d["fn_pct"], 1e-12)


MP.VALUES.update({
    # the false-negative share of the frame, which the longer draft does not
    # expose because its own limitations section quotes it differently
    "in_fn_pct": MP._n(MP.PA_W["fn_pct"], 2),
    # the share of the frame that is background in BOTH the prediction and the
    # annotation: the pixels every overlap measure discards, which Section 3.6 now names
    "in_tn_pct": MP._n(MP.PA_W["tn_pct"], 1),
    # THE SCORES PLATE AND TABLE 2 USE DIFFERENT AGGREGATIONS, and that is why both are
    # named. The plate reads pixel_accounting.json, whose own `metric` field says "mean
    # per image, mad_k leave-one-image-out": the whole fields come out 0.77 points below
    # an all-background prediction. Table 2's accuracy is the sweep row at the fixed
    # selected k, pooled over pixels, where the same deficit is 0.41 points. The
    # all-background value is identical in both, so the gap is entirely the aggregation.
    # A sentence beside the plate that quoted Table 2's number would describe bars the
    # plate does not draw.
    "wf_margin_img": MP._n(abs(100 * MP.PA_W["accuracy"]
                               - (100 - MP.PA_W["labelled_pct"])), 2),
    "crop_margin_img": MP._n(abs(100 * MP.PA_C["accuracy"]
                                 - (100 - MP.PA_C["labelled_pct"])), 2),
    "wf_margin_pool": MP._n(abs(MP._WFK(6.0)["accuracy_margin_pp"]), 2),
    # THE SWEEP'S LEVERAGE, ONE MICROSCOPY AGAINST THE OTHER. Both ratios are read off
    # the same seven values of k, so the comparison is of how far each collection's
    # reported-over-annotated area moves, not of where it sits. Computed here rather
    # than typed, because the transmission file is the one that changes when the corpus
    # is restricted and a typed number would not follow it.
    "sw_sem_lo": MP._n(min(_SWSPAN[0]), 2),
    "sw_sem_hi": MP._n(max(_SWSPAN[0]), 2),
    "sw_sem_span": MP._n(max(_SWSPAN[0]) / min(_SWSPAN[0]), 1),
    "sw_txm_lo": MP._n(min(_SWSPAN[1]), 2),
    "sw_txm_hi": MP._n(max(_SWSPAN[1]), 2),
    "sw_txm_span": MP._n(max(_SWSPAN[1]) / min(_SWSPAN[1]), 1),
    "sw_grid": f"{min(_SWGRID):g} to {max(_SWGRID):g}",
    # the reversal the baselines plate now draws: the same detector, the same images,
    # two cuts, opposite signs against an all-background prediction
    "arm_rev_wf": MP._n(abs(_ARM[0]), 2),
    "arm_rev_cr": MP._n(abs(_ARM[1]), 2),
    "tx_n": str(TX["n_frames"]),
    "tx_cov": MP._n(100 * TX["refereed_coverage_frac"], 1),
    "tx_crack_px": f"{TX['refereed_crack_px']:,}",
    "tx_notc_px": f"{TX['refereed_notcrack_px']:,}",
    "tx_ratio_pn": MP._n(TX["refereed_notcrack_px"] / TX["refereed_crack_px"], 1),
    "tx_prev": MP._n(_pool["tp_pct"] + _pool["fn_pct"], 3),
    "tx_empty": MP._n(_pool["empty_mask_accuracy_pct"], 3),
    "tx_acc": MP._n(_pool["accuracy_pct"], 3),
    "tx_margin": MP._n(_pool["margin_pp"], 2),
    "tx_area": MP._n(_pool["area_agreement"], 3),
    "tx_recall": MP._n(_rec(_pool), 3),
    "tx_otsu_acc": MP._n(TX["pooled"]["control: Otsu, no model"]["accuracy_pct"], 1),
    "tx_all_acc": MP._n(TX["pooled"]["control: mark everything"]["accuracy_pct"], 1),
    # --- the TXM collection's own detector -------------------------------------
    "tm_cv_n": str(_cv["labelled_images_used"]),
    "tm_cv_ens": MP._n(_cv["ens_mean_iou"], 4),
    "tm_cv_sd": MP._n(_cv["ens_std_iou"], 4),
    "tm_cv_min": MP._n(_cv["ens_min_iou"], 4),
    "tm_cv_f17": MP._n(_cv["f17_mean_iou"], 4),
    "tm_cv_hyb": MP._n(_cv["hybrid_mean_iou"], 4),
    "tm_cv_prec": MP._n(_cv["mean_precision"], 4),
    "tm_cv_rec": MP._n(_cv["mean_recall"], 4),
    "tm_ld_n": str(_ld["n_frames"]),
    "tm_ld_iou": MP._n(_ld["median_iou"], 4),
    "tm_ld_ceil": MP._n(_ld["median_3px_ceiling"], 4),
    "tm_ld_ratio": MP._n(_ld["ratio_of_medians"], 2),
    "tm_ld_width": MP._n(_ld["median_label_width_px"], 1),
    "tm_ld_wmin": MP._n(_ld["label_width_min_px"], 1),
    "tm_ld_wmax": MP._n(_ld["label_width_max_px"], 1),
    "tm_ld_wins": str(_ld["frames_where_correct_3px_trace_wins"]),
    "tm_rho_sh": MP._n(_ld["spearman_model_iou_vs_label_width"], 2),
    "tm_rho_c3": MP._n(_ld["spearman_3px_ceiling_vs_label_width"], 2),
    "tm_wf_n": str(_wf["n_frames"]),
    "tm_wf_iou": MP._n(_wf["median_iou"], 3),
    "tm_wf_q1": MP._n(_wf["q1"], 2),
    "tm_wf_q3": MP._n(_wf["q3"], 3),
    "tm_wf_rec": MP._n(_wf["example_frame_recall"], 3),
    "tm_wf_fp": MP._n(100 * _wf["example_frame_fp_on_painted_notcrack"], 2),
    "tm_ws_paint": MP._n(_ws["operator_paint_pct"], 1),
    "tm_ws_f17": MP._n(_ws["f17_iou"], 3),
    "tm_ws_hyb": MP._n(_ws["hybrid_iou"], 3),
    "tm_ws_ens": MP._n(_ws["ensemble_iou"], 3),
    "tm_ws_pct": MP._n(_ws["deployed_mask_pct"], 1),
    "tm_ws_f17pct": MP._n(_ws["f17_pct"], 1),
    "tm_ws_ab": MP._n(_ws["agreement_f17_vs_hybrid"], 3),
    "tm_ws_bc": MP._n(_ws["agreement_hybrid_vs_ensemble"], 3),
    "tm_nm": MP._n(TM["scale"]["nm_per_px"], 2),
})

# --- the overlap measures for the crack class, Section 3.6 and its figure --------------
# The longer draft reports F1, recall and IoU and never defines a precision placeholder,
# so the three bars in the plate could not all be named in prose. These come from the same
# two files the plate reads, through make_paper's own loaders, so the figure and the
# sentence beside it cannot drift apart. Floors are the mark-everything control, whose
# precision is the annotated crack fraction by construction.
_OV_W, _OV_C = MP.IN, MP.IN_CROP
_OV_WME = _OV_W["controls"]["mark_everything"]
_OV_CME = _OV_C["controls"]["mark_everything"]
MP.VALUES.update({
    "ov_prec": MP._n(_OV_W["loo"]["precision"]),
    "ov_crop_prec": MP._n(_OV_C["loo"]["precision"]),
    "ov_crop_recall": MP._n(_OV_C["loo"]["recall"]),
    "ov_crop_n": str(_OV_C["n"]),
    "ov_prec_floor": MP._n(_OV_WME["precision"]),
    "ov_crop_prec_floor": MP._n(_OV_CME["precision"]),
    "ov_lift": MP._n(_OV_W["loo"]["precision"] / _OV_WME["precision"], 1),
    "ov_crop_lift": MP._n(_OV_C["loo"]["precision"] / _OV_CME["precision"], 1),
    "ov_prec_ratio": MP._n(_OV_C["loo"]["precision"] / _OV_W["loo"]["precision"], 2),
    "ov_recall_ratio": MP._n(_OV_C["loo"]["recall"] / _OV_W["loo"]["recall"], 2),
    "ov_prev_ratio": MP._n(_OV_C["prevalence"] / _OV_W["prevalence"], 2),
    "ov_me_recall": MP._n(_OV_WME["recall"], 3),
    "ov_crop_me_f1": MP._n(_OV_CME["f1"]),
    "ov_k_lo": MP._n(min(float(k) for k in _OV_W["per_k"]), 1),
    "ov_k_hi": MP._n(max(float(k) for k in _OV_W["per_k"]), 1),
    "ov_prec_lo": MP._n(_OV_W["per_k"][min(_OV_W["per_k"], key=float)]["precision"]),
    "ov_recall_lo": MP._n(_OV_W["per_k"][min(_OV_W["per_k"], key=float)]["recall"]),
})
for g in ("B3", "B2", "Wrought", "AM/HC"):
    d = TX["by_group"][g]["arms"][_k6]
    tag = g.replace("/", "").lower()
    MP.VALUES.update({
        # how much reviewed not-crack is marked for every pixel of crack found: the
        # single number that separates "finds it and over-marks" from "does not find it"
        f"tx_{tag}_fpratio": MP._n(d["fp_pct"] / max(d["tp_pct"], 1e-9), 1),
        # the group's crack share of its reviewed area, and what the detector marks of
        # it; both were typed into the Section 4.3 table by hand
        f"tx_{tag}_prev": MP._n(d["tp_pct"] + d["fn_pct"], 1),
        f"tx_{tag}_marked": MP._n(d["marked_pct"], 1),
        f"tx_{tag}_n": str(TX["by_group"][g]["frames"]),
        f"tx_{tag}_acc": MP._n(d["accuracy_pct"], 1),
        f"tx_{tag}_empty": MP._n(d["empty_mask_accuracy_pct"], 1),
        f"tx_{tag}_margin": MP._n(d["margin_pp"], 1),
        f"tx_{tag}_recall": MP._n(_rec(d), 3),
        f"tx_{tag}_area": MP._n(d["area_agreement"], 2),
    })

# --- the sweep and the arms, for the two plates added to Section 4.3 ------------------
_gk = lambda g, k: TX["by_group"][g]["arms"][f"SEM detector, mad_k={k:g}"]
_pk = lambda k: TX["pooled"][f"SEM detector, mad_k={k:g}"]
_grid = TX["grid"]
_pool_margins = [_pk(k)["margin_pp"] for k in _grid]
_b2_areas = [(abs(_gk("B2", k)["area_agreement"] - 1.0), k) for k in _grid]
_b2_best_k = min(_b2_areas)[1]
MP.VALUES.update({
    "tx_k3_b3": MP._n(_gk("B3", _grid[0])["margin_pp"], 1),
    "tx_k10_b3": MP._n(_gk("B3", _grid[-1])["margin_pp"], 1),
    "tx_pool_best": MP._n(max(_pool_margins), 1),
    "tx_pool_bestk": f"{_grid[_pool_margins.index(max(_pool_margins))]:g}",
    "tx_b2_bestarea": MP._n(_gk("B2", _b2_best_k)["area_agreement"], 2),
    "tx_b2_bestareak": f"{_b2_best_k:g}",
    "tx_b2_bestareamargin": MP._n(abs(_gk("B2", _b2_best_k)["margin_pp"]), 1),
    "tx_vs_otsu": MP._n(_pool["margin_pp"] - TX["pooled"]["control: Otsu, no model"]
                        ["margin_pp"], 1),
    "tx_vs_all": MP._n(_pool["margin_pp"] - TX["pooled"]["control: mark everything"]
                       ["margin_pp"], 1),
})

# --- the overlap measures on THIS LABORATORY's own two collections, Section 4.4 -------
# Averaged over frames, one vote per frame. The pooled alternative lets a single frame
# carry a collection: in the TXM set one B3 frame holds 61% of its group's refereed crack
# pixels. Each collection is reported beside the score a geometrically correct 3 px trace
# of its OWN paint earns against that same paint, because both collections are painted
# with a stroke far wider than the feature and an overlap score against such a stroke
# pays for covering the stroke.
OVM = MP._f(os.path.join(REPO, "docs/figures/overlap_means_sem_txm.json"),
            "per-frame overlap means")
for _tag in ("SEM", "TXM"):
    _d = OVM[_tag]
    _p = _tag.lower()
    MP.VALUES.update({
        f"om_{_p}_n": str(_d["n_frames"]),
        f"om_{_p}_prec": MP._n(_d["mean_precision"], 3),
        f"om_{_p}_rec": MP._n(_d["mean_recall"], 3),
        f"om_{_p}_f1": MP._n(_d["mean_f1"], 3),
        f"om_{_p}_f1sd": MP._n(_d["sd_f1"], 3),
        f"om_{_p}_precsd": MP._n(_d["sd_precision"], 3),
        f"om_{_p}_recsd": MP._n(_d["sd_recall"], 3),
        f"om_{_p}_f1med": MP._n(_d["median_f1"], 3),
        f"om_{_p}_cprec": MP._n(_d["ceiling_mean_precision"], 3),
        f"om_{_p}_crec": MP._n(_d["ceiling_mean_recall"], 3),
        f"om_{_p}_cf1": MP._n(_d["ceiling_mean_f1"], 3),
        f"om_{_p}_width": MP._n(_d["mean_paint_width_p90_px"], 0),
        f"om_{_p}_above": str(sum(1 for r in _d["per_frame"]
                                  if r["f1"] > r["ceiling_f1"])),
        # the other end of the bracket: every marked pixel nobody refereed counted wrong
        f"om_{_p}_lo": MP._n(_d["mean_precision_if_unrefereed_wrong"], 3),
        f"om_{_p}_f1lo": MP._n(_d["mean_f1_if_unrefereed_wrong"], 3),
    })
MP.VALUES["om_k"] = MP._n(OVM["mad_k"], 1)

# --- trace or region: what the annotation IS, Sections 4.3 and 4.4 --------------------
PRT = MP._f(os.path.join(REPO, "docs/figures/paint_region_vs_trace.json"),
            "paint region vs trace")
_pct = lambda v: MP._n(100 * v, 1)
MP.VALUES.update({
    "pr_px": str(PRT["deep_px"]),
    "pr_txm_n": str(PRT["TXM"]["n_frames"]),
    "pr_txm_med": _pct(PRT["TXM"]["median_deep_share"]),
    "pr_txm_max": _pct(PRT["TXM"]["max_deep_share"]),
    "pr_txm_zero": str(PRT["TXM"]["frames_at_zero"]),
    "pr_txm_above": str(PRT["TXM"]["frames_above_25pct"]),
    "pr_sem_n": str(PRT["SEM"]["n_frames"]),
    "pr_sem_med": _pct(PRT["SEM"]["median_deep_share"]),
    "pr_sem_max": _pct(PRT["SEM"]["max_deep_share"]),
    "pr_sem_above": str(PRT["SEM"]["frames_above_25pct"]),
})
for _g, _t in (("B3", "b3"), ("B2", "b2"), ("Wrought", "wrought"), ("AM/HC", "amhc")):
    _r = PRT["TXM_by_group"][_g]
    MP.VALUES.update({
        f"pr_{_t}_med": _pct(_r["median_deep_share"]),
        f"pr_{_t}_max": _pct(_r["max_deep_share"]),
        f"pr_{_t}_above": str(_r["frames_above_25pct"]),
        f"pr_{_t}_zero": str(_r["frames_at_zero"]),
    })

# --- the per-frame TXM rows, so Section 4.3 can say what one frame is worth ------------
# The pooled numbers weight each frame by its refereed area, so a frame with a large
# painted region counts for many frames with small ones. Giving every frame one vote is a
# different estimand, not a correction of the pooled one, and the two disagree here by
# enough that reporting either alone would be a choice the reader cannot see.
TPF = MP._f(os.path.join(REPO, "docs/figures/txm_per_frame.json"), "TXM per frame")
_K6 = "SEM detector, mad_k=6"
_allm = [f["arms"][_K6]["margin_pp"] for f in TPF["frames"]]
_allm_sorted = sorted(_allm)
_med = (_allm_sorted[len(_allm_sorted) // 2] if len(_allm_sorted) % 2
        else 0.5 * (_allm_sorted[len(_allm_sorted) // 2 - 1]
                    + _allm_sorted[len(_allm_sorted) // 2]))
_cpx = [f["crack_px"] for f in TPF["frames"]]
MP.VALUES.update({
    "tpf_n": str(TPF["n_frames"]),
    "tpf_area_spread": MP._n(max(_cpx) / min(_cpx), 0),
    "tpf_mean_all": MP._n(sum(_allm) / len(_allm), 2),
    "tpf_med_all": MP._n(_med, 2),
    "tpf_pos_all": str(sum(1 for x in _allm if x > 0)),
})
for _g, _t in (("B3", "b3"), ("B2", "b2"), ("Wrought", "wrought"), ("AM/HC", "amhc")):
    _r = TPF["per_group"][_g]
    MP.VALUES.update({
        f"tpf_{_t}_n": str(_r["n"]),
        f"tpf_{_t}_pool": MP._n(_r["pooled_margin_pp"], 1),
        f"tpf_{_t}_cut": MP._n(_r["margin_without_largest_frame_pp"], 1),
        f"tpf_{_t}_share": MP._n(100 * _r["largest_frame_share_of_group_crack_px"], 0),
        f"tpf_{_t}_mean": MP._n(_r["mean_of_per_frame_margins_pp"], 1),
    })

# --- what the narrative plates actually drew, read from their own caption files -------
# Everything the review took OUT of the artwork has to be stated in the caption instead,
# and a caption that retypes a number the plate computed is a second copy of it. These
# are read back from the files the generators write, so the figure and the sentence
# beside it cannot drift apart.
WF = MP._f(os.path.join(PAPER, "figures/out/F1 - workflow.caption.json"),
           "the workflow plate's caption")
ST = MP._f(os.path.join(PAPER, "figures/out/F3 - detection stages, both modalities"
                              ".caption.json"), "the stage plate's caption")
for _t in ("sem", "txm"):
    _a = WF["arms"][_t]
    _px, _nm = _a["frame_px"], _a["nm_per_px"]
    MP.VALUES.update({
        f"wf_{_t}_w": f"{_px[1]:,}", f"wf_{_t}_h": f"{_px[0]:,}",
        f"wf_{_t}_nm": f"{_nm:g}",
        f"wf_{_t}_umw": MP._n(_px[1] * _nm / 1000.0, 0),
        f"wf_{_t}_umh": MP._n(_px[0] * _nm / 1000.0, 0),
        f"wf_{_t}_marked": MP._n(_a["area_fraction_pct"], 2),
        f"st_{_t}_fov": f"{ST['rows'][_t]['fov_um']:g}",
    })
MP.VALUES["st_zoom"] = f"{ST['inset_magnification']:g}"

MD = MP._f(os.path.join(PAPER, "figures/out/F2 - how each modality sees a crack"
                              ".caption.json"), "the modality plate's caption")
MP.VALUES["fig_modality_fov"] = f"{MD['matched_fov_um']:g}"

# --- what the over/under-counting figure actually drew, read from its own caption ------
# The prose beside Figure 11 quotes how concentrated each error is. Those shares are
# computed when the plate is drawn, so they are read back from the plate's caption file
# rather than retyped: a figure and the sentence beside it that are maintained separately
# drift, and this project has shipped that drift before.
CNT = MP._f(os.path.join(PAPER, "figures/out/F5 - over- and under-counting.caption.json"),
            "the over/under-counting plate's caption")
MP.VALUES.update({
    "cnt_txm_over_share": MP._n(
        100 * CNT["frames"]["TXM"]["over-counted"]["share_of_collection"], 0),
    "cnt_med_over": MP._n(
        min(p["over_pct"] for p in CNT["panels"] if p["kind"] == "over-counted"), 2),
})

# --- the detector's own axis, for the introduction's second figure --------------------
# How dark the operator's painted crack actually is, in the units the proposal stage
# thresholds in, per frame, for both collections. The reconstruction of the real proposal
# mask from this axis is checked pixel for pixel against the installed detector on every
# frame, so the number below is the detector's own margin and not a proxy for it.
MC = MP._f(os.path.join(REPO, "docs/figures/modality_contrast.json"),
           "modality contrast on the detector's axis")
_mc_n = MC["SEM"]["n_frames"] + MC["TXM"]["n_frames"]
_mc_below = (MC["SEM"]["frames_median_critical_k_below_k"]
             + MC["TXM"]["frames_median_critical_k_below_k"])
MP.VALUES.update({
    "fig_modality_n": str(_mc_n),
    "fig_modality_below": str(_mc_below),
    "mc_sem_k": MP._n(MC["SEM"]["median_of_median_critical_k_crack"], 2),
    "mc_txm_k": MP._n(MC["TXM"]["median_of_median_critical_k_crack"], 2),
    "mc_sem_prop": MP._n(100 * MC["SEM"]["median_crack_px_proposed_frac"], 1),
    "mc_txm_prop": MP._n(100 * MC["TXM"]["median_crack_px_proposed_frac"], 1),
    "mc_sem_below": str(MC["SEM"]["frames_median_critical_k_below_k"]),
    "mc_txm_below": str(MC["TXM"]["frames_median_critical_k_below_k"]),
    "mc_sem_n": str(MC["SEM"]["n_frames"]),
    "mc_txm_n": str(MC["TXM"]["n_frames"]),
    "mc_recon": str(max(MC["SEM"]["max_reconstruction_mismatch_px"],
                        MC["TXM"]["max_reconstruction_mismatch_px"])),
})
for _g, _t in (("B3", "b3"), ("B2", "b2"), ("Wrought", "wrought"), ("AM/HC", "amhc")):
    _r = MC["TXM"]["by_group"][_g]
    MP.VALUES.update({
        f"mc_{_t}_k": MP._n(_r["median_of_median_critical_k_crack"], 2),
        f"mc_{_t}_prop": MP._n(100 * _r["median_crack_px_proposed_frac"], 0),
    })


FIG_RE = re.compile(r"^\[FIGURE ([a-z]+)\s*\|\s*(.+)\]$")
#: `[TABLE key | caption]` on its own line, IMMEDIATELY BEFORE a pipe table. The same
#: shape as the figure directive, and for the same reason -- see `number_the_tables`.
TBL_RE = re.compile(r"^\[TABLE ([a-z0-9_]+)\s*\|\s*(.+)\]$")


def number_the_figures(files):
    """Assign figure numbers from the order the directives appear, and publish them.

    WHY THIS EXISTS. Every figure number in the prose used to be typed: "Figure 1 shows
    the microscopy example", "the ceiling in Figure 6". Inserting a figure at the front
    silently redirects every one of them, and nothing in the build can tell -- a dangling
    reference check passes cleanly while "Figure 6" now points at a different plate. The
    review moved two new figures to the front of the paper, which is exactly that edit.

    So the prose writes `{fig_ceiling}` and gets the number this function assigns. A name
    with no `[FIGURE ...]` directive never enters VALUES, so `resolve` fails the build on
    it, and a figure that is referenced but not placed cannot ship.
    """
    seen, order = set(), []
    for src in files:
        for raw in open(os.path.join(SECT, src), encoding="utf-8"):
            m = FIG_RE.match(raw.strip())
            if not m:
                continue
            key = m.group(1)
            if key in seen:
                raise SystemExit(f"figure key {key!r} is placed twice")
            if key not in FIGS:
                raise SystemExit(f"unknown figure key {key!r}")
            seen.add(key)
            order.append(key)
    MP.VALUES.update({f"fig_{k}": str(i + 1) for i, k in enumerate(order)})
    # AND A GUARD, so a typed number cannot come back. Checked on the RAW source, before
    # the placeholders resolve, because after resolution every legitimate reference reads
    # "Figure 7" too and the check would have nothing to see.
    typed = []
    for src in files:
        for n, raw in enumerate(open(os.path.join(SECT, src), encoding="utf-8"), 1):
            for m in re.finditer(r"Figures?\s+\d", raw):
                typed.append(f"{src}:{n}: {raw.strip()[max(0, m.start() - 30):m.end() + 20]}")
    if typed:
        raise SystemExit(
            "figure numbers typed into the prose, which silently point at the wrong plate "
            "the next time a figure moves. Use {fig_<key>}:\n  " + "\n  ".join(typed))
    unused = sorted(set(FIGS) - seen)
    if unused:
        print(f"  NOTE: {len(unused)} plate(s) defined and not placed: "
              f"{', '.join(unused)}")
    return order


def number_the_tables(files):
    """Assign table numbers from the order the `[TABLE ...]` directives appear.

    EXACTLY THE DISCIPLINE `number_the_figures` IMPOSES ON FIGURES, and for the same
    reason: a typed "Table 2" silently points at a different table the moment a table is
    inserted ahead of it, and no dangling-reference check can see that. The prose writes
    `{tbl_<key>}` and gets the number this function assigns; a key with no directive
    never enters VALUES, so `resolve` fails the build on it.

    Unlike figures there is no registry of known keys -- a table has no plate on disk --
    so the key is only a label, and its only constraint is that it is placed once.
    """
    seen, order = set(), []
    for src in files:
        for raw in open(os.path.join(SECT, src), encoding="utf-8"):
            m = TBL_RE.match(raw.strip())
            if not m:
                continue
            key = m.group(1)
            if key in seen:
                raise SystemExit(f"table key {key!r} is placed twice")
            seen.add(key)
            order.append(key)
    MP.VALUES.update({f"tbl_{k}": str(i + 1) for i, k in enumerate(order)})
    # AND THE GUARD, on the RAW source before the placeholders resolve, because after
    # resolution every legitimate reference reads "Table 3" too.
    typed = []
    for src in files:
        for n, raw in enumerate(open(os.path.join(SECT, src), encoding="utf-8"), 1):
            for m in re.finditer(r"Tables?\s+\d", raw):
                typed.append(f"{src}:{n}: {raw.strip()[max(0, m.start() - 30):m.end() + 20]}")
    if typed and order:
        raise SystemExit(
            "table numbers typed into the prose, which silently point at the wrong table "
            "the next time a table moves. Use {tbl_<key>}:\n  " + "\n  ".join(typed))
    if typed:
        # NOT YET FATAL, and only because no table carries a directive yet: with no
        # `{tbl_<key>}` published there is nothing the author could write instead, and
        # raising here would mean the manuscript could not be built at all. The first
        # `[TABLE ...]` directive added to the sections turns this into the hard failure
        # above, which is the state the figures are already in.
        print(f"  WARNING: {len(typed)} typed table number(s) in the prose. These become "
              f"a hard build failure as soon as one [TABLE ...] directive exists:")
        for t in typed:
            print(f"    {t}")
    return order


def paragraphs(text):
    """Yield the file's lines with consecutive body lines joined into one.

    A body line is anything that is not blank, not a heading, not a bullet, not a table
    row and not a figure or table directive. Those keep their own lines because each of
    them is a single unit the renderer handles separately.
    """
    def structural(t):
        st = t.strip()
        return (not st or st.startswith(("#", "* ", "|"))
                or FIG_RE.match(st) is not None or TBL_RE.match(st) is not None)

    buf = []
    for raw in text.split("\n"):
        line = raw.rstrip()
        if structural(line):
            if buf:
                yield " ".join(buf)
                buf = []
            yield line
        else:
            buf.append(line.strip())
    if buf:
        yield " ".join(buf)


def main():
    files = sorted(f for f in os.listdir(SECT) if f.endswith(".md"))
    if not files:
        raise SystemExit(f"{SECT} is empty")
    order = number_the_figures(files)
    torder = number_the_tables(files)
    laid, undirected = [], []
    with PdfPages(OUT) as pdf:
        doc = MP.Doc(pdf)
        fign = 0
        pending, directive, src = [], None, None

        def flush_table():
            """Render the pipe rows collected so far, with the directive's caption and
            number when one preceded them and with neither when none did."""
            nonlocal pending, directive
            body = [r for r in pending
                    if not all(set(c) <= set("-: ") for c in r)]
            pending = []
            if not body:
                directive = None
                return
            if directive:
                n, cap, key = directive
                got = doc.table(body, MP.SMALL, caption=cap, number=n)
                laid.append((f"Table {n} ({key})", got))
            else:
                undirected.append((src, " | ".join(body[0])))
                got = doc.table(body, MP.SMALL,
                                name=f"{src}: the undirected table headed "
                                     f"{' | '.join(body[0])!r}")
                laid.append((f"(no directive) {src}: {body[0][0][:28]}", got))
            directive = None

        for src in files:
            whole = MP.resolve(open(os.path.join(SECT, src), encoding="utf-8").read())
            # JOIN A PARAGRAPH'S LINES BEFORE RENDERING. `Doc.text` wraps whatever it is
            # given, and the sections are hard-wrapped at about 88 characters, so every
            # source line was being wrapped on its own: the page break fell wherever the
            # author's editor had broken the line, and a line holding a placeholder came
            # out visibly short once the placeholder resolved to one digit. Joining the
            # consecutive body lines of a paragraph and wrapping once puts the breaks
            # where the page width puts them. Headings, bullets, tables and figure
            # directives are left alone -- each of those IS one line.
            for raw in paragraphs(whole):
                line = raw.rstrip()
                mt = TBL_RE.match(line.strip())
                if mt:
                    if pending:
                        raise SystemExit(
                            f"{src}: [TABLE {mt.group(1)}] sits INSIDE a pipe table; the "
                            f"directive goes immediately before the first row")
                    if directive:
                        raise SystemExit(
                            f"{src}: [TABLE {directive[2]}] is not followed by a pipe "
                            f"table")
                    directive = (torder.index(mt.group(1)) + 1, mt.group(2), mt.group(1))
                    continue
                m = FIG_RE.match(line.strip())
                if m:
                    fign += 1
                    key, cap = m.group(1), m.group(2)
                    if key not in FIGS:
                        raise SystemExit(f"unknown figure key {key!r}")
                    if not os.path.exists(FIGS[key]):
                        raise SystemExit(f"missing plate for {key!r}: {FIGS[key]}")
                    doc.figure(FIGS[key], f"Figure {fign}.  {cap}")
                    continue
                if line.lstrip().startswith("|"):
                    pending.append([c.strip() for c in line.strip().strip("|").split("|")])
                    continue
                if pending:
                    flush_table()
                    doc.y -= 0.06
                if directive and line.strip():
                    raise SystemExit(
                        f"{src}: [TABLE {directive[2]}] must sit immediately before a "
                        f"pipe table, and the next content is {line.strip()[:60]!r}")
                if not line.strip():
                    doc.y -= 0.07
                elif line.startswith("### "):
                    doc.text(line[4:], MP.H3, "bold", MP.LEAD["h3"], gap=0.14, wrap="h3")
                elif line.startswith("## "):
                    doc.text(line[3:], MP.H2, "bold", MP.LEAD["h2"], gap=0.20, wrap="h2")
                elif line.startswith("# "):
                    doc.text(line[2:], MP.H1, "bold", MP.LEAD["h1"], gap=0.0, wrap="h1")
                elif line.lstrip().startswith("* "):
                    doc.bullet(line.lstrip()[2:], MP.BODY)
                else:
                    doc.text(line, MP.BODY, lead=MP.LEAD["body"])
        if pending:
            flush_table()
        if directive:
            raise SystemExit(f"[TABLE {directive[2]}] is not followed by a pipe table")
        doc.close()
    print("wrote", OUT)
    print(f"resolved {len(MP.VALUES)} values; sections: {len(files)}; figures: {fign}; "
          f"tables: {len(laid)}")
    print("  " + "; ".join(f"{i + 1} {k}" for i, k in enumerate(order)))
    for nm, got in laid:
        print(f"  {nm}: {got['size']:.1f} pt, columns "
              f"{'/'.join(f'{w:.0f}' for w in got['widths_pt'])} pt "
              f"({''.join(got['align'])})")
    if undirected:
        # THE PROSE AUTHOR NEEDS THE LIST, not a silent omission. These render with no
        # caption and no number, which is correct but is not the finished state.
        print(f"  WARNING: {len(undirected)} table(s) carry no [TABLE key | caption] "
              f"directive and so ship with no number and no caption:")
        for s, hdr in undirected:
            print(f"    {s}: | {hdr} |")


if __name__ == "__main__":
    main()
