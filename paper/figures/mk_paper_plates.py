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
    """Reported against annotated crack area, and accuracy against an all-background mask.

    No title and no prose inside the axes: IOP forbids a figure title outright and
    Elsevier's caption rule says the title is "not displayed on the figure itself". Both
    panels start at zero, because a truncated value axis under bars is the one thing in
    this set a reviewer will call a misrepresentation -- which is why panel (b) now shows
    the all-background reference as a marker on a full-range axis rather than as a tick on
    a 20-point crop. Colour carries identity only.
    """
    order = [("Inconel 718\nwhole fields", "Inconel 718, whole fields"),
             ("Inconel 718\nreleased crops", "Inconel 718, released crops"),
             ("MetalDAM\nvoids", "MetalDAM voids (not cracks)"),
             ("EBC coating\nwithdrawn", "EBC coating, whole fields")]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(J.PAGEW, 2.6), layout="constrained",
                                   gridspec_kw={"width_ratios": [1.0, 1.0]})
    y = list(range(len(order)))[::-1]
    lab = [o[0] for o in order]
    rat = [PAX[k]["detector"]["marked_pct"] / PAX[k]["detector"]["labelled_pct"]
           for _, k in order]
    best = min(BC["sweeps"]["whole_fields"],
               key=lambda r: abs(r["area_agreement_corpus"] - 1.0))

    for yi, r in zip(y, rat):
        ax1.plot([min(r, 1.0), max(r, 1.0)], [yi, yi], color=J.G_MID, lw=0.9,
                 zorder=2, solid_capstyle="butt")
    ax1.plot(rat, y, linestyle="none", marker="o", markersize=7,
             markerfacecolor=J.ACCENT, markeredgecolor=J.INK, markeredgewidth=0.6,
             zorder=4, clip_on=False)
    ax1.axvline(1.0, color=J.INK, lw=0.9, zorder=3)
    ax1.plot([best["area_agreement_corpus"]], [y[0]], marker="D", color=J.INK,
             markersize=4.5, zorder=6, clip_on=False)
    ax1.set_xscale("log")
    ax1.set_xticks([1, 10, 100])
    ax1.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax1.set_yticks(y, lab)
    ax1.set_xlabel("Reported / annotated crack area")
    J.panel_label(ax1, "a")

    acc = [100 * PAX[k]["detector"]["accuracy"] for _, k in order]
    emp = [100 - PAX[k]["detector"]["labelled_pct"] for _, k in order]
    ax2.barh(y, acc, 0.55, color=J.G_LIGHT, edgecolor=J.INK, linewidth=0.5, zorder=2,
             label="detector")
    ax2.plot(emp, y, linestyle="none", marker="|", color=J.INK, markersize=11,
             markeredgewidth=1.4, zorder=5, label="all-background mask")
    ax2.set_xlim(0, 105)
    ax2.set_xticks([0, 25, 50, 75, 100])
    ax2.set_yticks(y, ["" for _ in order])
    ax2.set_xlabel("Pixel accuracy (%)")
    ax2.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2,
               fontsize=J.TICK, handlelength=1.4, columnspacing=1.4,
               borderpad=0.0, handletextpad=0.5)
    J.panel_label(ax2, "b")

    J.save(fig, os.path.join(OUT, "P1 - public scores.png"))
    json.dump({"what": "reported vs annotated crack area, and pixel accuracy vs an "
                       "all-background mask, for every collection scored",
               "values": {k: {"area_agreement": PAX[k]["detector"]["marked_pct"]
                              / PAX[k]["detector"]["labelled_pct"],
                              "accuracy_pct": 100 * PAX[k]["detector"]["accuracy"],
                              "all_background_accuracy_pct":
                                  100 - PAX[k]["detector"]["labelled_pct"]}
                          for _, k in order},
               "source": "pixel_accounting.json + background_counting_table.json"},
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
    """Eight arms, ranked by reported/annotated crack area, with accuracy beside them.

    Panel (b) previously ran from 97.4 to 98.5 so the differences between arms would show.
    That is a truncated axis under bars and it is the clearest misrepresentation available
    in this figure set, so it now runs from zero and the arms are, correctly, almost
    indistinguishable on accuracy -- which is the paper's point about accuracy at this
    prevalence, not a defect of the chart.
    """
    arms = AB["whole_fields"]["arms"]
    empty = AB["whole_fields"]["empty_mask_accuracy_pct"]
    short = {"DETECTOR (shipped)": "this detector",
             "UNION darkness OR Sato": "darkness OR Sato",
             "global threshold (Otsu on flat)": None}
    rank = sorted(((short.get(k, k), v) for k, v in arms.items()
                   if short.get(k, k) is not None),
                  key=lambda kv: -abs(kv[1]["area_agreement"] - 1.0))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(J.PAGEW, 2.9), layout="constrained",
                                   gridspec_kw={"width_ratios": [1.0, 0.78]})
    y = list(range(len(rank)))
    cols = [J.ACCENT if k == "this detector" else J.G_LIGHT for k, _ in rank]

    ax1.barh(y, [v["area_agreement"] for _, v in rank], 0.6, color=cols,
             edgecolor=J.INK, linewidth=0.5, zorder=2)
    ax1.axvline(1.0, color=J.INK, lw=0.9, zorder=3)
    ax1.set_yticks(y, [k for k, _ in rank])
    ax1.set_xlim(0, 1.35)
    ax1.set_xlabel("Reported / annotated crack area")
    J.panel_label(ax1, "a")

    # THE SIGNED DIFFERENCE, not the accuracy itself. Drawn from zero, every arm's
    # accuracy is 97-98% and the bars are indistinguishable -- true, and the paper's point,
    # but unreadable. Cropping the axis to show it would be the misrepresentation the
    # convention exists to prevent. The difference from an all-background mask is the
    # quantity actually at issue, it is signed, and zero is its natural origin.
    d = [v["accuracy_pct"] - empty for _, v in rank]
    ax2.barh(y, d, 0.6, color=cols, edgecolor=J.INK, linewidth=0.5, zorder=2)
    ax2.axvline(0.0, color=J.INK, lw=0.9, zorder=3)
    ax2.set_yticks(y, ["" for _ in rank])
    ax2.set_xlabel("Pixel accuracy relative to an\nall-background mask (points)")
    J.panel_label(ax2, "b")

    J.save(fig, os.path.join(OUT, "P4 - baselines.png"))
    json.dump({"what": "eight arms ranked by reported/annotated crack area, with pixel "
                       "accuracy and the all-background reference",
               "arms": arms, "all_background_accuracy_pct": empty,
               "source": "docs/figures/arms_background_units.json"},
              open(os.path.join(OUT, "P4 - baselines.caption.json"), "w"), indent=1)


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


if __name__ == "__main__":
    plate_scores()
    plate_transfer()
    plate_width()
    plate_baselines()
    plate_budget()
    print("\nplates in", OUT)
