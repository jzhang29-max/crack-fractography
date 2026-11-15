#!/usr/bin/env python3
"""Plates for the paper draft, all from measured JSON and none of them hand-drawn.

Sources, all written by a measuring script and never edited by hand:
    docs/figures/sem_originals_metrics.json  P/R/F1/IoU + controls, SEM whole fields
    docs/figures/sem_public_metrics.json     the same, on the released crops
    docs/figures/sem_baselines.json          seven classical arms on the crops
    docs/figures/sem_width_ceiling.json      constant-width reconstruction curves
    <scratch>/paperfigs/width_ceiling.json  constant-width trace vs label, both datasets
    docs/figures/metric_figures.json      the same width construction on the 26 corpus tiles

Run with the SEM repo's interpreter (this one has matplotlib):
    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_paper_plates.py

Greyscale only, one house style: journal_style.J, applied once by J.use() and never
overridden here. This module used to re-apply its own rcParams after J.use(), which put
axes.spines.top/right back to False and so drew every plate WITHOUT the four-sided box the
house style specifies. The type-size floor is asserted by J.save, after the write, because
the page rescales whatever width comes out.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths                  # noqa: E402
import journal_style as J          # noqa: E402  -- the target journals' own rules

J.use()

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SCRATCH = os.path.join(REPO, "docs", "figures")   # the measurement files live here
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)



def load(path, what):
    if not os.path.exists(path):
        raise SystemExit(f"missing {what}: {path} -- run its measuring script first")
    return json.load(open(path))


PM = load(os.path.join(REPO, "docs/figures/public_metrics.json"), "public metrics")["datasets"]
SEM_PM = load(os.path.join(REPO, "docs/figures/sem_public_metrics.json"), "SEM metrics")["datasets"]
SEM_WC = load(os.path.join(REPO, "docs/figures/sem_width_ceiling.json"), "SEM width ceiling")
SEM_OR = load(os.path.join(REPO, "docs/figures/sem_originals_metrics.json"),
              "SEM originals")["datasets"]
# The sweep EXTENDED above the shipped constant. Every older file stops at mad_k = 5.0,
# which is the shipped value, so a plate drawn from one of them cannot show a peak.
MK = load(os.path.join(REPO, "docs/figures/madk_above_five.json"),
          "mad_k above five")["sets"]
# Everything this paper plots is now computed over every pixel of the frame. These three
# carry the sweep, the classical arms and the constant-width construction in those units.
BC = load(os.path.join(REPO, "docs/figures/background_counting_table.json"),
          "background-counting table")
TXMM = load(os.path.join(REPO, "docs/figures/txm_model_scores.json"),
            "the TXM model comparison")
#: THE WHOLE CORPUS, not the published b2/b3 subset: see mk_txm_plates.load.
#: The example micrographs stay b2/b3; every score is over everything measured.
TXB4 = load(_paths.scoped("txm_background_units.json", scope=False),
            "the arms carried over to the TXM data")
#: The operating point the paper reports at, named once.
BM_K = 6.0
AB = load(os.path.join(REPO, "docs/figures/arms_background_units.json"),
          "arms in background units")["sets"]
WBG = load(os.path.join(REPO, "docs/figures/width_ceiling_background_units.json"),
           "width ceiling, background units")["sets"]
PAX = load(os.path.join(REPO, "docs/figures/pixel_accounting.json"),
           "pixel accounting")["sets"]
# SEM ONLY. Pavement is out of the paper: the application is micrographs, and a road-surface
# benchmark says nothing about one. The primary numbers are the ORIGINAL 1024x1024 fields
# rather than the released crops -- every source image behind the crops also appears among
# the originals, so the two are not independent, and the crops are cut around cracks, which
# lifts prevalence from 1.80% to 4.53% and the score with it.
# INCONEL 718 ALONE. The EBC coating is out of the paper: it is a ceramic barrier
# coating, not a metal, and the application is cracks in alloys. Its measurements stay in
# docs/figures/sem_originals_metrics.json and sem_baselines.json as a record.
ALL = {"Inconel 718\n(SEM alloy, whole fields)": SEM_OR["Inconel718_crack"]}
WC = load(os.path.join(SCRATCH, "width_ceiling.json"), "width ceiling")
MF = load(os.path.join(REPO, "docs/figures/metric_figures.json"), "corpus metric figures")


# ---------------------------------------------------------------- plate: public scores
def plate_scores():
    """Pixel accuracy against the accuracy an all-background mask reaches, and the gap.

    TWO PANELS, AND THE SECOND IS THE POINT. With accuracy alone the plate is four bars
    that all reach 95 to 99 and a reference marker sitting on top of each of them: at
    this prevalence the detector and a prediction that marks nothing are indistinguishable
    to the eye, which IS the paper's argument and is exactly why the argument could not be
    read off the figure. Panel (b) plots the difference the text discusses -- accuracy
    minus the accuracy an all-background mask reaches on the same pixels -- zero-based, so
    the quantity that separates the collections is drawn at the size it actually is.

    A DIFFERENCE AXIS IS NOT A TRUNCATED ONE. Panel (a) keeps its full 0-100 range,
    because a cropped value axis under bars is the one thing in this set a reviewer will
    call a misrepresentation. Panel (b) is a different quantity, drawn from its own zero,
    and it is the same encoding the TXM transfer plate and the baseline plate already use.

    A reported/annotated crack-area panel stood here in an earlier version and was
    withdrawn: its axis had to run to 100 to hold the withdrawn EBC coating at 80x, which
    left the three reported collections stacked on the unity line, and the area ratio is
    the subject of the operating-curve figure, where it is drawn against the constant that
    moves it.

    No title and no prose inside the axes: IOP forbids a figure title outright and
    Elsevier's caption rule says the title is "not displayed on the figure itself".
    Colour carries identity only.
    """
    order = [("Inconel 718\nwhole fields", "Inconel 718, whole fields"),
             ("Inconel 718\nreleased crops", "Inconel 718, released crops"),
             ("MetalDAM\nvoids", "MetalDAM voids (not cracks)"),
             ("EBC coating\nwithdrawn", "EBC coating, whole fields")]
    fig, (ax2, ax3) = plt.subplots(
        1, 2, figsize=(J.W15, 2.5), layout="constrained",
        gridspec_kw={"width_ratios": [1.35, 1.0]})
    y = list(range(len(order)))[::-1]
    lab = [o[0] for o in order]

    acc = [100 * PAX[k]["detector"]["accuracy"] for _, k in order]
    emp = [100 - PAX[k]["detector"]["labelled_pct"] for _, k in order]
    ax2.barh(y, acc, 0.55, color=J.G_LIGHT, edgecolor=J.INK, linewidth=0.5, zorder=2,
             label="detector")
    ax2.plot(emp, y, linestyle="none", marker="|", color=J.INK, markersize=11,
             markeredgewidth=1.4, zorder=5, label="all-background mask")
    ax2.set_xlim(0, 105)
    ax2.set_xticks([0, 25, 50, 75, 100])
    ax2.set_yticks(y, lab)
    ax2.set_xlabel("Pixel accuracy (%)")
    ax2.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2,
               fontsize=J.TICK, handlelength=1.4, columnspacing=1.4,
               borderpad=0.0, handletextpad=0.5)
    J.panel_label(ax2, "a")

    # THE WITHDRAWN COLLECTION IS IN (a) AND NOT IN (b), and that is the same lesson the
    # withdrawn area-ratio panel taught: the EBC coating sits 20 points below an
    # all-background mask, and on a shared axis it squashes the three collections the
    # paper actually reports into slivers a millimetre wide. A 0-100 accuracy axis
    # absorbs it; a difference axis cannot. The caption says it is left out and why.
    gap = [a_ - e_ for a_, e_ in zip(acc, emp)]
    keep = [i for i, (l, _) in enumerate(order) if "EBC" not in l]
    ax3.barh([y[i] for i in keep], [gap[i] for i in keep], 0.55,
             color=[J.ACCENT if gap[i] > 0 else J.G_LIGHT for i in keep],
             edgecolor=J.INK, linewidth=0.5, zorder=2)
    ax3.axvline(0.0, color=J.INK, lw=0.9, zorder=3)
    ax3.set_ylim(min(y) - 0.6, max(y) + 0.6)
    ax3.set_yticks(y, ["" for _ in lab])
    ax3.set_xlabel("Accuracy minus the\nall-background mask (points)")
    J.panel_label(ax3, "b")

    J.save(fig, os.path.join(OUT, "P1 - public scores.png"))
    json.dump({"what": "(a) pixel accuracy against the accuracy an all-background mask "
                       "reaches, for every collection scored; (b) the difference between "
                       "them, which is the quantity the text discusses and the only one "
                       "at which the collections are distinguishable",
               "why_two_panels": "with (a) alone the plate is four bars that all reach 95 "
                                 "to 99 with the reference marker on top of each; that "
                                 "indistinguishability is the paper's argument and could "
                                 "not be read off the figure",
               "axis_note": "(a) keeps a full 0-100 range because a cropped value axis "
                            "under bars misrepresents; (b) is a DIFFERENCE, drawn from "
                            "its own zero, the same encoding the baseline and TXM "
                            "transfer plates use",
               "ebc_left_out_of_b": "the withdrawn EBC coating is 20 points below an "
                                    "all-background mask and on a shared difference axis "
                                    "it reduces the three reported collections to "
                                    "slivers; it is shown in (a), where a 0-100 axis "
                                    "absorbs it",
               "withdrawn_panel": "a reported/annotated crack-area panel stood beside "
                                  "this one. Its log axis had to reach 100 to hold the "
                                  "withdrawn EBC coating at 80x, which left the three "
                                  "reported collections unreadable on the unity line, "
                                  "and the area ratio it showed is the subject of the "
                                  "operating-curve figure, drawn there against the "
                                  "constant that moves it.",
               "values": {k: {"accuracy_pct": 100 * PAX[k]["detector"]["accuracy"],
                              "all_background_accuracy_pct":
                                  100 - PAX[k]["detector"]["labelled_pct"],
                              "gap_points": (100 * PAX[k]["detector"]["accuracy"]
                                             - (100 - PAX[k]["detector"]["labelled_pct"]))}
                          for _, k in order},
               "source": "pixel_accounting.json"},
              open(os.path.join(OUT, "P1 - public scores.caption.json"), "w"), indent=1)


# ------------------------------------------------------- plate: one constant transfers
def plate_transfer():
    """Reported/annotated crack area against the detector's one free constant.

    The shaded band marking the earlier draft's grid and the sentence that labelled it
    are gone from the artwork: the band is a claim about this paper's own history, which
    is caption material, and prose inside the axes is the convention being corrected.
    What survives inside the frame is data, a reference line at unity, and two markers.
    """
    fig, ax = plt.subplots(figsize=(J.W15, 2.9), layout="constrained")
    wf, cr = BC["sweeps"]["whole_fields"], BC["sweeps"]["crops"]
    ks = [r["mad_k"] for r in wf]
    ax.plot(ks, [r["area_agreement_corpus"] for r in wf], marker="o", color=J.ACCENT,
            label="whole fields")
    ax.plot([r["mad_k"] for r in cr], [r["area_agreement_corpus"] for r in cr],
            marker="s", linestyle="--", color=J.ACCENT2, markerfacecolor="white",
            label="released crops")
    ax.axhline(1.0, color=J.INK, lw=0.7)
    best = min(wf, key=lambda r: abs(r["area_agreement_corpus"] - 1.0))
    ax.plot([best["mad_k"]], [best["area_agreement_corpus"]], marker="D",
            color=J.INK, markersize=5.5, zorder=6)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks([1, 10])
    ax.set_yticks([0.1, 1, 10])
    for a in (ax.get_xaxis(), ax.get_yaxis()):
        a.set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xlabel("MAD multiplier, $k$")
    ax.set_ylabel("Reported / annotated crack area")
    ax.legend(loc="upper right")
    J.save(fig, os.path.join(OUT, "P2 - operating curve.png"),
           printed_width=J.W15)
    json.dump({"what": "reported crack area divided by annotated, against the detector's "
                       "single free constant, on whole fields and on crops of them",
               "whole_fields": {str(r["mad_k"]): r["area_agreement_corpus"] for r in wf},
               "crops": {str(r["mad_k"]): r["area_agreement_corpus"] for r in cr},
               "marker": {"mad_k": best["mad_k"],
                          "ratio": best["area_agreement_corpus"]},
               "source": "docs/figures/background_counting_table.json"},
              open(os.path.join(OUT, "P2 - operating curve.caption.json"), "w"), indent=1)


def plate_width():
    """Accuracy of the annotation redrawn at a fixed width, against drawn width."""
    fig, ax = plt.subplots(figsize=(J.W15, 2.9), layout="constrained")
    wf, cr = WBG["whole_fields"], WBG["crops"]
    ws = sorted(int(k) for k in wf["by_width"])
    ax.plot(ws, [wf["by_width"][str(w)]["accuracy_pct"] for w in ws], marker="o",
            color=J.ACCENT, label=f"whole fields ($n$ = {wf['n']})")
    ax.plot(ws, [cr["by_width"][str(w)]["accuracy_pct"] for w in ws], marker="s",
            linestyle="--", color=J.ACCENT2, markerfacecolor="white",
            label=f"released crops ($n$ = {cr['n']})")
    ax.axhline(wf["empty_mask_accuracy_pct"], color=J.ACCENT, lw=0.7, linestyle=":",
               label="all-background mask, same corpus")
    ax.axhline(cr["empty_mask_accuracy_pct"], color=J.ACCENT2, lw=0.7, linestyle=":")
    for d, col in ((wf, J.INK), (cr, J.INK)):
        bw = d["best_accuracy_width"]
        ax.plot([bw], [d["by_width"][str(bw)]["accuracy_pct"]], marker="D", color=col,
                markersize=5.5, zorder=6)
    ax.set_xscale("log")
    ax.set_xticks([1, 10])
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xlabel("Width the centreline is redrawn at (px)")
    ax.set_ylabel("Pixel accuracy (%)")
    ax.legend(loc="lower center", ncol=1)
    J.save(fig, os.path.join(OUT, "P3 - width sensitivity.png"), printed_width=J.W15)
    json.dump({"what": "accuracy of the annotation reduced to its centreline and redrawn "
                       "at a fixed width; dotted lines are all-background accuracy",
               "whole_fields": wf, "crops": cr,
               "source": "docs/figures/width_ceiling_background_units.json"},
              open(os.path.join(OUT, "P3 - width sensitivity.caption.json"), "w"),
              indent=1)


def plate_baselines():
    """Seven classical arms on the SEM whole fields, and the three TXM models.

    WHOLE FIELDS ONLY. This plate used to draw each arm twice, once on the 31 whole
    fields and once on the 26 released crops cut from them, because the two framings
    disagree and that disagreement is a real result. It is no longer drawn here: the
    paper reports whole fields, the crops are not an independent collection (every
    source image behind a crop also appears among the originals) and they are cut
    around cracks, so a reader comparing the two marker types was comparing a corpus
    with itself under a selection. The reversal that pairing showed -- this detector
    moving from below an all-background mask on whole fields to above it on the crops
    -- is kept in the caption record rather than drawn.

    PANEL (c) IS THE OTHER ARM'S MODEL CHOICE, which the plate had no counterpart for.
    Three transmission models under one cross-validation: seventeen hand-built channels
    alone, those channels concatenated with a frozen SAM ViT-H encoder, and the mean of
    the two, which is what the application ships. Its caveats are on the panel because
    they are not small: the folds are grouped by IMAGE and not by specimen, so no whole
    specimen is ever held out, and the artefact covers all 71 labelled frames rather
    than the b2 and b3 series the rest of the paper reports.
    """
    WF, CR = AB["whole_fields"], AB["crops"]
    short = {"DETECTOR (shipped)": "this detector",
             "UNION darkness OR Sato": "darkness OR Sato",
             "global threshold (Otsu on flat)": None}
    rank = sorted(((short.get(k, k), k) for k in WF["arms"]
                   if short.get(k, k) is not None),
                  key=lambda kv: abs(WF["arms"][kv[1]]["area_agreement"] - 1.0))
    names = [a for a, _ in rank]
    keys = [k for _, k in rank]
    y = list(range(len(rank)))
    HERO = names.index("this detector")

    fig, (ax1, ax2, ax3) = plt.subplots(
        1, 3, figsize=(J.PAGEW, 2.75), layout="constrained",
        gridspec_kw={"width_ratios": [1.0, 0.80, 0.78]})

    def dots(ax, wf, ref, label):
        ax.axhspan(HERO - 0.5, HERO + 0.5, color="#eef2f8", zorder=0)
        ax.axvline(ref, color=J.INK, lw=0.9, zorder=3)
        for i, a in enumerate(wf):
            ax.plot([ref, a], [i, i], color=J.G_LIGHT, lw=1.6,
                    solid_capstyle="round", zorder=2)
        ax.plot(wf, y, "o", ms=5.0, mfc=J.ACCENT, mec="white", mew=0.6,
                linestyle="none", zorder=4)
        ax.set_ylim(len(rank) - 0.5, -0.5)
        ax.set_xlabel(label)

    a_wf = [WF["arms"][k]["area_agreement"] for k in keys]
    dots(ax1, a_wf, 1.0, "Reported / annotated area")
    ax1.set_yticks(y, names)
    for t, n in zip(ax1.get_yticklabels(), names):
        if n == "this detector":
            t.set_fontweight("bold")
    J.panel_label(ax1, "a")
    ax1.set_title(f"SEM, {WF['n']} whole fields" if "n" in WF else "SEM, whole fields",
                  fontsize=J.TICK, pad=2.0)

    m_wf = [WF["arms"][k]["accuracy_pct"] - WF["empty_mask_accuracy_pct"] for k in keys]
    m_cr = [CR["arms"][k]["accuracy_pct"] - CR["empty_mask_accuracy_pct"] for k in keys]
    dots(ax2, m_wf, 0.0, "Pixel accuracy relative to an\nall-background mask (points)")
    ax2.set_yticks(y, ["" for _ in rank])
    J.panel_label(ax2, "b")

    # --- (c) everything that has been tried on the transmission data -------------
    # TWO CONVENTIONS IN ONE PANEL, and the divider says so. The carried-over arms are
    # scored pooled over the refereed pixels of the 18 b2/b3 frames, where IoU is
    # tp/(tp+fp+fn) and every term is in the record. The three TXM models come from a
    # 5-fold cross-validation grouped by image over all 71 labelled frames. They are
    # drawn on one axis because the question is which to deploy, but they are NOT
    # interchangeable numbers and the panel must not let a reader read them as a
    # single ranking.
    cv = TXMM["cross_validated"]
    pooled = TXB4["pooled"]

    def iou_of(a):
        return a["tp_pct"] / max(a["tp_pct"] + a["fp_pct"] + a["fn_pct"], 1e-9)

    carried = [("mark everything", iou_of(pooled["control: mark everything"])),
               ("Otsu, no model", iou_of(pooled["control: Otsu, no model"])),
               (f"SEM detector, k = {BM_K:g}",
                iou_of(pooled[f"SEM detector, mad_k={BM_K:g}"]))]
    models = [("17 channels", cv["f17_mean_iou"], None),
              ("+ frozen SAM", cv["hybrid_mean_iou"], None),
              ("mean of the two\n(shipped)", cv["ens_mean_iou"], cv["ens_std_iou"])]

    rows3 = [(n, v, None, J.G_LIGHT) for n, v in carried] + \
            [(n, v, sd, J.ACCENT2 if "shipped" in n else J.G_MID)
             for n, v, sd in models]
    yy = list(range(len(rows3)))
    ax3.barh(yy, [r[1] for r in rows3], height=0.60,
             color=[r[3] for r in rows3], edgecolor=J.INK, linewidth=0.6, zorder=3)
    for i, (_, v, sd, _c) in enumerate(rows3):
        if sd:
            ax3.errorbar(v, i, xerr=sd, color=J.INK, lw=0.9, capsize=2.0, zorder=4)
        ax3.text(0.025, i, f"{v:.3f}", va="center", ha="left", fontsize=J.TICK,
                 color="white" if v > 0.45 else J.INK, fontweight="bold", zorder=5)
    ax3.axhline(len(carried) - 0.5, color=J.INK, lw=0.8, ls=(0, (3, 2)), zorder=6)
    bb = dict(boxstyle="square,pad=0.12", fc="white", ec="none", alpha=0.9)
    ax3.text(0.98, -0.55, f"carried over, {TXB4['n_frames']} b2/b3 frames",
             fontsize=J.TICK, ha="right", va="center", color=J.G_DARK, zorder=7,
             bbox=bb)
    ax3.text(0.98, len(carried) - 0.44,
             f"TXM models, {cv['labelled_images_used']} frames",
             fontsize=J.TICK, ha="right", va="center", color=J.G_DARK, zorder=7,
             bbox=bb)
    ax3.set_yticks(yy, [r[0] for r in rows3], fontsize=J.TICK)
    ax3.set_ylim(len(rows3) - 0.5, -0.95)
    ax3.set_xlim(0, 1.0)
    ax3.set_xticks([0.0, 0.5, 1.0])
    ax3.set_xlabel("IoU on transmission data")
    J.panel_label(ax3, "c")

    J.save(fig, os.path.join(OUT, "P4 - baselines.png"))
    json.dump({
        "what": "(a, b) seven arms on the SEM whole fields, ranked by agreement in "
                "total marked area; (c) the three transmission models under one "
                "cross-validation",
        "crops_not_drawn": "the 26 released crops are cut from the same 31 fields and "
                           "around cracks, so they are not an independent collection; "
                           "the plate reports whole fields only",
        "reversal_kept_for_the_record": {
            "this detector, whole fields": round(m_wf[HERO], 3),
            "this detector, released crops": round(m_cr[HERO], 3)},
        "arms_whole_fields": WF["arms"],
        "all_background_accuracy_pct": {"whole_fields": WF["empty_mask_accuracy_pct"],
                                        "crops": CR["empty_mask_accuracy_pct"]},
        "txm_carried_over_arms": {n: round(v, 4) for n, v in carried},
        "txm_two_conventions": "the carried-over arms are pooled over the refereed "
                               "pixels of the b2/b3 frames; the three models are a "
                               "5-fold cross-validation grouped by image over all 71 "
                               "labelled frames. One axis, two corpora: the panel "
                               "answers which to deploy, not which scores higher",
        "txm_models": {k: cv[k] for k in
                       ("f17_mean_iou", "hybrid_mean_iou", "ens_mean_iou",
                        "ens_std_iou", "ens_min_iou", "mean_precision", "mean_recall",
                        "labelled_images_used", "convention", "grouped_by",
                        "model_version", "not_specimen_independent", "not_restricted")},
        "omitted": "Otsu on the flattened image, which marks 55x the annotated area on "
                   "the whole fields and would set the axis alone",
        "source": ["docs/figures/arms_background_units.json",
                   "docs/figures/txm_model_scores.json",
                   os.path.basename(_paths.scoped("txm_background_units.json", scope=False))]},
        open(os.path.join(OUT, "P4 - baselines.caption.json"), "w"), indent=1)


def plate_budget_both():
    """The pixel budget in BOTH arms on one plate, with the area ratio shared.

    WHAT THIS REPLACES. Two plates drew the same accounting twice: P5 for the public SEM
    collections, T4 for the transmission collection, each a pair of panels. They answer
    the same question -- where does the marked area go, and how far is the reported area
    fraction from the annotated one -- so a reader who has parsed one has parsed the
    other, and the review's note was that figures of that kind should be combined.

    WHAT CANNOT BE SHARED, AND IS NOT. The two budgets are percentages of different
    things. The SEM collections are scored over every pixel of the frame; the
    transmission collection is scored over the pixels an operator adjudicated, which is
    about a fifth of it. Those are different denominators and they are kept in separate
    panels with separate axis labels, because putting them on one axis would invite a
    comparison that is not available. The area ratio in (c) IS commensurable -- it is
    dimensionless and its reference is one in both arms -- so that panel carries all four
    collections and is the only place in the figure where they meet.
    """
    PA = load(os.path.join(REPO, "docs/figures/pixel_accounting.json"),
              "pixel accounting")["sets"]
    TXB = load(_paths.scoped("txm_background_units.json", scope=False),
               "the TXM budget")
    K6 = "SEM detector, mad_k=6"
    # EBC is out of the paper, so it is out of this plate: 20.29% marked against 0.27%
    # labelled is 76.65x and would set the axis by itself.
    sem = [k for k in ("Inconel 718, whole fields",)
           if PA.get(k)]
    # All four specimen groups, not just the two whose images are published: the plate
    # reports what the detector does on everything measured. B3 and B2 lead because the
    # example micrographs elsewhere in the paper are cut from them.
    txm = [g for g in ("B3", "B2", "Wrought", "AM/HC") if g in TXB["by_group"]]
    _missing = sorted(set(TXB["by_group"]) - set(txm))
    if _missing:
        raise SystemExit(f"specimen groups {_missing} are in the record and not drawn")

    fig = plt.figure(figsize=(J.PAGEW, 2.78), layout="constrained")
    gs = fig.add_gridspec(1, 3, width_ratios=[1.30, 1.00, 1.15], wspace=0.06)
    ax1, ax2, ax3 = (fig.add_subplot(g) for g in gs)

    def budget(ax, rows, get, labels, xlabel):
        for i, k in enumerate(rows):
            r = get(k)
            ax.barh(i + 0.16, r["labelled_pct"], 0.26, facecolor="none",
                    edgecolor=J.INK, linewidth=0.9, zorder=2)
            ax.barh(i - 0.16, r["tp_pct"], 0.26, color=J.ACCENT, edgecolor=J.INK,
                    linewidth=0.5, zorder=2)
            ax.barh(i - 0.16, r["fp_pct"], 0.26, left=r["tp_pct"], color=J.ACCENT2,
                    edgecolor=J.INK, linewidth=0.5, zorder=2)
        ax.set_yticks(range(len(rows)), labels)
        ax.set_ylim(len(rows) - 0.5, -0.5)
        ax.set_xlabel(xlabel)

    def _sem(k):
        r = PA[k]["detector"]
        return {"labelled_pct": r["labelled_pct"], "tp_pct": r["tp_pct"],
                "fp_pct": r["fp_pct"]}

    def _txm(g):
        r = TXB["by_group"][g]["arms"][K6]
        return {"labelled_pct": r["tp_pct"] + r["fn_pct"], "tp_pct": r["tp_pct"],
                "fp_pct": r["fp_pct"]}

    budget(ax1, sem, _sem, ["Inconel 718\nwhole fields"],
           "Percent of all image pixels")
    budget(ax2, txm, _txm, [f"TXM {g}" for g in txm], "Percent of reviewed area")
    J.panel_label(ax1, "a")
    J.panel_label(ax2, "b")
    # OUTSIDE, UNDER ALL THREE PANELS. Inside (a) it covered a bar whichever corner it
    # was put in: that panel has four bars in a 4.6-unit axis and no free corner.
    fig.legend(handles=[Patch(facecolor="none", edgecolor=J.INK, label="annotated"),
                        Patch(facecolor=J.ACCENT, edgecolor=J.INK, label="marked, agrees"),
                        Patch(facecolor=J.ACCENT2, edgecolor=J.INK,
                              label="marked, disagrees")],
               loc="outside lower center", ncol=3, handletextpad=0.4, borderpad=0.2,
               columnspacing=1.6)

    # (c) the one quantity both arms share: dimensionless, reference one
    names = ["Inconel 718, whole fields"] + \
            [f"TXM {g}" for g in txm]
    ratios = [PA[k]["detector"]["marked_pct"] / PA[k]["detector"]["labelled_pct"]
              for k in sem] + \
             [TXB["by_group"][g]["arms"][K6]["area_agreement"] for g in txm]
    # ONE NEUTRAL COLOUR HERE, deliberately. Blue and orange already mean "agrees" and
    # "disagrees" in (a) and (b); using them again for the arm would give the same two
    # hues two meanings inside one figure. The rows are named instead.
    ax3.barh(range(len(names)), ratios, 0.55, color=J.G_MID, edgecolor=J.INK,
             linewidth=0.5, zorder=2)
    ax3.axvline(1.0, color=J.INK, lw=0.9, zorder=3)
    short = ["IN-718 fields"] + [f"TXM {g}" for g in txm]
    ax3.set_yticks(range(len(names)), short)
    ax3.tick_params(axis="y", labelsize=J.TICK)
    ax3.set_ylim(len(names) - 0.5, -0.5)
    ax3.set_xlabel("Reported / annotated\ncrack area")
    J.panel_label(ax3, "c")

    J.save(fig, os.path.join(OUT, "P5 - the pixel budget in both arms.png"))
    json.dump({
        "what": "(a) the detector's marked area on the public SEM collections, split "
                "into the part that agrees with the annotation and the part that does "
                "not, with the annotated area as an outline, as a percentage of ALL "
                "image pixels; (b) the same accounting on the transmission collection's "
                "two specimen series, as a percentage of the REVIEWED area; (c) marked "
                "area divided by annotated area for all four, which is dimensionless "
                "and is the only quantity the two arms share",
        "why one plate": "two plates drew the same accounting on two collections; the "
                         "denominators differ and are kept apart, the dimensionless "
                         "ratio is shared",
        "denominators": {"a": "every pixel of the frame",
                         "b": "only the pixels an operator adjudicated, which is "
                              f"{100 * TXB['refereed_coverage_frac']:.1f}% of the frame"},
        "ratios": dict(zip(names, [round(r, 4) for r in ratios])),
        "omitted": "the EBC coating, 20.29% marked against 0.27% labelled, which would "
                   "set the axis by itself",
        "sources": ["docs/figures/pixel_accounting.json",
                    os.path.basename(_paths.scoped("txm_background_units.json", scope=False))],
    }, open(os.path.join(OUT, "P5 - the pixel budget in both arms.caption.json"), "w"),
        indent=1)


def plate_budget():
    """What the detector marks, as a share of the image, beside what the human marked.

    P/R/F1/IoU all discard the true negatives. On a 1.8%-crack image that is 98% of the
    evidence, and it lets two very different detectors share a score: one marking 0.3% of
    the frame and one marking 5% can land on the same IoU. The quantity a user of this tool
    reads off the screen IS a pixel percentage -- area fraction -- so the figure reports it
    in those units, and the over-marking ratio says directly how wrong that read-out is.
    """
    PA = load(os.path.join(REPO, "docs/figures/pixel_accounting.json"),
              "pixel accounting")["sets"]
    # EBC is out of the paper, so it is out of this plate. Its budget is the most
    # dramatic -- 20.29% marked against 0.27% labelled, 76.65x -- and it lives in
    # docs/figures/pixel_accounting.json and in Section 7 instead.
    sets = [k for k in ("Inconel 718, whole fields", "Inconel 718, released crops")
            if PA.get(k)]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(J.PAGEW, 2.4), layout="constrained",
                                  gridspec_kw={"width_ratios": [1.35, 1]})
    y = range(len(sets))
    for i, k in enumerate(sets):
        r = PA[k]["detector"]
        # the human's share, as an outline above the detector's stacked bar
        ax.barh(i + 0.15, r["labelled_pct"], 0.24, facecolor="none", edgecolor=J.INK,
                linewidth=0.9, zorder=2)
        ax.barh(i - 0.15, r["tp_pct"], 0.24, color=J.ACCENT, edgecolor=J.INK,
                linewidth=0.5, zorder=2)
        ax.barh(i - 0.15, r["fp_pct"], 0.24, left=r["tp_pct"], color=J.ACCENT2,
                edgecolor=J.INK, linewidth=0.5, zorder=2)
    ax.set_yticks(list(y), [k.replace(", ", "\n") for k in sets])
    ax.set_xlabel("Percent of all image pixels")
    ax.set_xlim(0, max(max(PA[k]["detector"]["marked_pct"],
                           PA[k]["detector"]["labelled_pct"]) for k in sets) * 1.30)
    # The percentages were printed beside the bars. They are in the caption and in the
    # table; a legend identifies the three quantities without putting numbers in the art.
    ax.legend(handles=[
        Patch(facecolor="none", edgecolor=J.INK, linewidth=1.0, label="Annotated"),
        Patch(facecolor=J.ACCENT, edgecolor=J.INK, linewidth=0.5,
              label="Marked, annotated"),
        Patch(facecolor=J.ACCENT2, edgecolor=J.INK, linewidth=0.5,
              label="Marked, not annotated")], loc="lower right", fontsize=J.TICK)
    ax.set_ylim(-0.62, len(sets) - 0.38)
    J.panel_label(ax, "a")

    # the over-marking ratio, which is the number a user of the tool actually feels
    ratios = [PA[k]["detector"]["marked_pct"] / PA[k]["detector"]["labelled_pct"]
              for k in sets]
    # LINEAR, not log: with two values between 0.78 and 1.30 a log axis adds nothing.
    # One fill for both bars -- they are the same detector, and the y axis says which
    # corpus each is; shading them by whether the ratio passes a threshold would make
    # colour mean verdict.
    ax2.barh(list(y), ratios, 0.3, color=J.ACCENT, edgecolor=J.INK, linewidth=0.5,
             zorder=2)
    ax2.axvline(1.0, color=J.INK, lw=0.9, zorder=3)
    ax2.set_yticks(list(y), ["" for _ in sets])
    ax2.set_xlim(0, max(max(ratios) * 1.25, 1.5))
    ax2.set_ylim(-0.62, len(sets) - 0.38)
    ax2.set_xlabel("Reported / annotated crack area")
    J.panel_label(ax2, "b")

    J.save(fig, os.path.join(OUT, "P5 - pixel budget.png"))
    json.dump({
        "what": "(a) the detector's marked area split into the part that agrees with the "
                "annotation and the part that does not, with the annotated area as an "
                "outline, both as a percentage of all image pixels; (b) marked area "
                "divided by annotated area, with unity marked",
        "why": "P/R/F1/IoU discard the true negatives, which are 98% of a 1.8%-crack "
               "image; and area fraction is what this tool actually reports to a user, so "
               "the over-marking ratio is the error they feel",
        # WITHOUT balanced accuracy and MCC. The source record carries both and this
        # dumped it wholesale, so the two measures the author asked be dropped shipped
        # in the caption JSON of the one plate nobody re-read.
        "values": {k: {m: v for m, v in PA[k]["detector"].items()
                       if m not in ("balanced_accuracy", "mcc")} for k in sets},
        "read this first": "on whole fields the detector marks 2.34% where the human "
                           "marked 1.80%, so an area fraction read off this tool is about "
                           "1.30x too high. On the released crops it marks 3.53% against "
                           "4.53%, so there it UNDER-reports at 0.78x -- the same "
                           "detector, opposite bias, and the only difference is how the "
                           "images were cut.",
        "EBC, withdrawn from the paper": "20.29% marked against 0.27% labelled, 76.65x",
        "source": "docs/figures/pixel_accounting.json"},
        open(os.path.join(OUT, "P5 - pixel budget.caption.json"), "w"), indent=1)


# ------------------------------------------------- plate: the two sensitivity curves
#: The TXM sweep, pooled over frames, read in the same ratio units as the SEM sweep. The
#: file is named explicitly rather than discovered, and recorded in the caption JSON,
#: because a plate that silently falls back to a different corpus is the hardest kind of
#: error to see afterwards.
TXM_SWEEP_FILE = "txm_background_units.json"


def plate_sensitivity():
    """Both of the paper's sensitivity curves on one plate, in two panels.

    WHY THEY ARE ONE FIGURE NOW. They were two, each a single line plot alone on a
    1.5-column plate, and a reviewer's note was that the pair is too large for what it
    says. They are the same kind of statement -- what moves the reported area, and what
    moves the accuracy -- drawn on the same two collections with the same two markers, so
    a reader who has parsed one panel has already parsed the other. Side by side they
    occupy a little over half the page the pair used to.

    (a) adds the transmission collection to the sweep, which neither plate carried. The
    quantity is a RATIO in both -- reported crack area over annotated crack area -- so
    the three series are commensurable, but the TXM denominator is the area an operator
    adjudicated rather than the whole frame, and the caption says so. What the panel is
    for is the comparison the review asked for: the two microscopies against the one
    constant, and where each of them crosses agreement.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(J.PAGEW, 2.45), layout="constrained")

    # --- (a) the one free constant --------------------------------------------------
    wf, cr = BC["sweeps"]["whole_fields"], BC["sweeps"]["crops"]
    tx = load(os.path.join(REPO, "docs", "figures", TXM_SWEEP_FILE),
              "the TXM sweep")["pooled"]
    tk = sorted(float(k.rsplit("=", 1)[1]) for k in tx if k.startswith("SEM detector"))
    ax1.plot([r["mad_k"] for r in wf], [r["area_agreement_corpus"] for r in wf],
             marker="o", ms=3.6, color=J.ACCENT, label="SEM, whole fields")
    ax1.plot([r["mad_k"] for r in cr], [r["area_agreement_corpus"] for r in cr],
             marker="s", ms=3.4, linestyle="--", color=J.ACCENT2,
             markerfacecolor="white", label="SEM, released crops")
    ax1.plot(tk, [tx[f"SEM detector, mad_k={k:g}"]["area_agreement"] for k in tk],
             marker="^", ms=3.6, linestyle=":", color=J.G_DARK,
             label="TXM, reviewed pixels")
    ax1.axhline(1.0, color=J.INK, lw=0.7)
    best = min(wf, key=lambda r: abs(r["area_agreement_corpus"] - 1.0))
    ax1.plot([best["mad_k"]], [best["area_agreement_corpus"]], marker="D", color=J.INK,
             markersize=5.0, zorder=6)
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_xticks([1, 10])
    ax1.set_yticks([0.1, 1, 10])
    for a in (ax1.get_xaxis(), ax1.get_yaxis()):
        a.set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax1.set_xlabel("MAD multiplier, $k$")
    ax1.set_ylabel("Reported / annotated crack area")
    ax1.legend(loc="upper right", handletextpad=0.4, borderpad=0.25, labelspacing=0.25)
    J.panel_label(ax1, "a")

    # --- (b) the width the annotation is drawn at -----------------------------------
    wbw, cbw = WBG["whole_fields"], WBG["crops"]
    ws = sorted(int(k) for k in wbw["by_width"])
    ax2.plot(ws, [wbw["by_width"][str(w)]["accuracy_pct"] for w in ws], marker="o",
             ms=3.6, color=J.ACCENT, label=f"whole fields ($n$ = {wbw['n']})")
    ax2.plot(ws, [cbw["by_width"][str(w)]["accuracy_pct"] for w in ws], marker="s",
             ms=3.4, linestyle="--", color=J.ACCENT2, markerfacecolor="white",
             label=f"released crops ($n$ = {cbw['n']})")
    ax2.axhline(wbw["empty_mask_accuracy_pct"], color=J.ACCENT, lw=0.7, linestyle=":")
    ax2.axhline(cbw["empty_mask_accuracy_pct"], color=J.ACCENT2, lw=0.7, linestyle=":",
                label="all-background, same corpus")
    for d in (wbw, cbw):
        bw = d["best_accuracy_width"]
        ax2.plot([bw], [d["by_width"][str(bw)]["accuracy_pct"]], marker="D", color=J.INK,
                 markersize=5.0, zorder=6)
    ax2.set_xscale("log")
    ax2.set_xticks([1, 10])
    ax2.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax2.set_xlabel("Width the centreline is redrawn at (px)")
    ax2.set_ylabel("Pixel accuracy (%)")
    # headroom at the bottom so the key sits on white rather than across the curves. The
    # axis is NOT cropped at the top to separate the series -- the range still reaches
    # both all-background lines, which is what the panel is read against.
    lo = min(cbw["by_width"][str(w)]["accuracy_pct"] for w in ws)
    ax2.set_ylim(lo - 1.35, None)
    ax2.legend(loc="lower left", handletextpad=0.4, borderpad=0.25, labelspacing=0.25)
    J.panel_label(ax2, "b")

    J.save(fig, os.path.join(OUT, "P2 - the two sensitivities.png"))
    json.dump({
        "what": "(a) reported crack area divided by annotated, against the detector's "
                "single free constant, on the two public SEM collections and on the "
                "transmission collection; (b) pixel accuracy of the annotation reduced "
                "to its centreline and redrawn at a fixed width, against that width",
        "why one plate": "the two curves were two 1.5-column plates with one line each; "
                         "they make the same kind of statement on the same collections "
                         "with the same markers, and the pair was larger than what it "
                         "said",
        "units warning": "panel (a)'s three series are all the ratio reported/annotated "
                         "crack area, but the SEM series are over every pixel of the "
                         "frame and the TXM series is over the pixels an operator "
                         "adjudicated. The ratio is commensurable; the denominators "
                         "cover different things, and the caption says so.",
        "whole_fields": {str(r["mad_k"]): r["area_agreement_corpus"] for r in wf},
        "crops": {str(r["mad_k"]): r["area_agreement_corpus"] for r in cr},
        "txm_pooled": {f"{k:g}": tx[f"SEM detector, mad_k={k:g}"]["area_agreement"]
                       for k in tk},
        "marker": {"mad_k": best["mad_k"], "ratio": best["area_agreement_corpus"]},
        "width_whole_fields": wbw, "width_crops": cbw,
        "sources": ["docs/figures/background_counting_table.json",
                    "docs/figures/width_ceiling_background_units.json",
                    "docs/figures/" + TXM_SWEEP_FILE],
    }, open(os.path.join(OUT, "P2 - the two sensitivities.caption.json"), "w"), indent=1)


if __name__ == "__main__":
    plate_scores()
    plate_transfer()
    plate_width()
    plate_sensitivity()
    plate_baselines()
    plate_budget()
    plate_budget_both()
    print("\nplates in", OUT)
