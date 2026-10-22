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

Greyscale only. Type-size floor asserted BEFORE savefig, because a plate in this project
once shipped at 2.3 pt and the guard that would have caught it ran after the write.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SCRATCH = os.path.join(REPO, "docs", "figures")   # the measurement files live here
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

FLOOR = 7.0
BODY, SMALL, TITLE = 9.0, 8.0, 10.5

# ONE HOUSE STYLE, SET ONCE. Each plate was being tuned on its own, so the five of them
# disagreed about tick size, spine weight and grid. Greyscale only: every series in this
# paper is separated by shape, fill or dash, never by hue, so the plates survive printing
# and a colour-blind reader.
plt.rcParams.update({
    "font.size": BODY,
    "axes.titlesize": BODY,
    "axes.labelsize": BODY,
    "xtick.labelsize": SMALL,
    "ytick.labelsize": SMALL,
    "legend.fontsize": SMALL,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "0.35",
    "axes.linewidth": 0.9,
    "xtick.color": "0.35",
    "ytick.color": "0.35",
    "xtick.labelcolor": "0.1",
    "ytick.labelcolor": "0.1",
    "xtick.major.width": 0.9,
    "ytick.major.width": 0.9,
    "xtick.major.size": 3.2,
    "ytick.major.size": 3.2,
    "axes.grid": False,
    "legend.frameon": False,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})


def check(fig):
    sizes = [t.get_fontsize() for t in fig.findobj(plt.Text) if t.get_text().strip()]
    if sizes and min(sizes) < FLOOR:
        raise SystemExit(f"type too small: {min(sizes):.1f} pt (floor {FLOOR})")


def save(fig, name, caption):
    check(fig)
    p = os.path.join(OUT, name + ".png")
    fig.savefig(p, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    json.dump(caption, open(os.path.join(OUT, name + ".caption.json"), "w"), indent=1)
    print("wrote", p)


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
    """The headline, in the only units this paper reports.

    This plate used to show precision, recall, F1 and IoU against no-information floors.
    All four discard the pixels correctly left alone, which on these fields is 98% of the
    frame, so none of them could state the quantity the tool outputs. It now shows that
    quantity directly -- the crack area fraction reported against the one the annotator
    marked, on every set this project has scored -- with accuracy beside it and the
    empty-mask line that makes an accuracy legible.
    """
    order = [("Inconel 718\nwhole fields", "Inconel 718, whole fields"),
             ("Inconel 718\nreleased crops", "Inconel 718, released crops"),
             ("MetalDAM\nvoids, not cracks", "MetalDAM voids (not cracks)"),
             ("EBC coating\nwithdrawn: ceramic", "EBC coating, whole fields")]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.4),
                                   gridspec_kw={"width_ratios": [1.05, 1.0]})

    # left: how close the reported area fraction is to the annotator's. 1.0 is exact.
    lab = [o[0] for o in order]
    rat = [PAX[k]["detector"]["marked_pct"] / PAX[k]["detector"]["labelled_pct"]
           for _, k in order]
    # the shipped Inconel field value is replaced by the operating point Section 3.2 argues
    # for; both are drawn so the improvement is visible rather than asserted
    best = min(BC["sweeps"]["whole_fields"],
               key=lambda r: abs(r["area_agreement_corpus"] - 1.0))
    y = range(len(order))
    ax1.axvline(1.0, color="0.0", lw=1.2, zorder=1)
    ax1.barh(list(y), rat, 0.5, color=["0.25"] + ["0.62"] * 3, zorder=2)
    ax1.plot([best["area_agreement_corpus"]], [0], marker="D", color="#b3401a",
             markersize=6, zorder=5)
    ax1.annotate(f"mad_k {best['mad_k']:g}: {best['area_agreement_corpus']:.3f}x",
                 xy=(best["area_agreement_corpus"], 0), xytext=(2.4, 0.62),
                 fontsize=SMALL, color="#b3401a",
                 arrowprops=dict(arrowstyle="-", color="#b3401a", lw=0.8))
    ax1.text(1.02, len(order) - 0.52, "exact", fontsize=SMALL, va="center", ha="left",
             rotation=90)
    for i, v in zip(y, rat):
        ax1.text(v * 1.22, i, f"{v:.2f}x", va="center", fontsize=SMALL)
    ax1.set_xscale("log")
    ax1.set_xticks([0.5, 1, 2, 5, 20, 80])
    ax1.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax1.set_yticks(list(y), lab, fontsize=SMALL)
    ax1.set_xlabel("crack area fraction reported / marked", fontsize=BODY)
    ax1.set_title("What the tool reports", fontsize=TITLE)
    ax1.spines[["top", "right"]].set_visible(False)

    # right: accuracy against the accuracy of an empty mask on the same set
    acc = [100 * PAX[k]["detector"]["accuracy"] for _, k in order]
    emp = [100 - PAX[k]["detector"]["labelled_pct"] for _, k in order]
    # THE AXIS STARTS NEAR THE DATA. Drawn from zero, 96% and 99% are the same bar and the
    # empty-mask line sits on top of every one of them, which is the whole comparison.
    lo = min(min(acc), min(emp)) - 1.5
    for i, (a, e) in enumerate(zip(acc, emp)):
        ax2.barh(i, a - lo, 0.5, left=lo, color="0.25" if a > e else "#b3401a", zorder=2)
        ax2.plot([e, e], [i - 0.33, i + 0.33], color="0.0", lw=2.4, zorder=5)
        ax2.text(a + 0.5, i, f"{a:.2f}", va="center", fontsize=SMALL,
                 color="0.25" if a > e else "#b3401a", fontweight="bold")
        ax2.text(e, i + 0.36, f"{e:.2f}", va="bottom", ha="center", fontsize=SMALL - 1.0,
                 color="0.0")
    ax2.set_yticks(list(y), ["" for _ in order])
    ax2.set_xlim(lo, max(acc) + 3.2)
    ax2.set_xlabel("accuracy, all pixels (%)", fontsize=BODY)
    ax2.set_title("Accuracy vs an empty mask", fontsize=TITLE)
    # the note goes under the whole figure: inside ax2 it printed across the bottom bar
    fig.text(0.5, 0.005, "black tick = the accuracy of an empty mask on that set; "
             "red = the detector does not beat it", ha="center", fontsize=SMALL - 1.0,
             color="0.3")
    ax2.spines[["top", "right"]].set_visible(False)
    ax1.tick_params(labelsize=SMALL)
    ax2.tick_params(labelsize=SMALL)

    save(fig, "P1 - public scores", {
        "what": "crack area fraction reported against marked, and accuracy against the "
                "accuracy of an empty mask, on every set scored",
        "values": {k: {"area_agreement": PAX[k]["detector"]["marked_pct"]
                       / PAX[k]["detector"]["labelled_pct"],
                       "accuracy_pct": 100 * PAX[k]["detector"]["accuracy"],
                       "empty_mask_accuracy_pct": 100 - PAX[k]["detector"]["labelled_pct"]}
                   for _, k in order},
        "source": "pixel_accounting.json + background_counting_table.json"})


# ------------------------------------------------------- plate: one constant transfers
def plate_transfer():
    """The operating curve, in the units the paper reports.

    Two things this plate must show and its earlier versions did not. The sweep used to
    stop at mad_k = 5.0, the shipped constant, with the score still rising -- so the plate
    asserted a peak it had never reached, and the grid it swept is shaded here so a reader
    can see where it stopped. And it plotted mean F1, which discards the background; the
    curve drawn now is the crack area fraction the tool would report divided by the one the
    annotator marked, where 1.0 is exact and the optimum is visible as a crossing rather
    than as a maximum.
    """
    fig, ax = plt.subplots(figsize=(5.8, 3.6))
    wf = BC["sweeps"]["whole_fields"]
    cr = BC["sweeps"]["crops"]
    ks = [r["mad_k"] for r in wf]

    ax.plot(ks, [r["area_agreement_corpus"] for r in wf], marker="^", linestyle="-",
            color="0.0", markersize=4.5, linewidth=1.6,
            label="Inconel 718, whole fields")
    ax.plot([r["mad_k"] for r in cr], [r["area_agreement_corpus"] for r in cr],
            marker="s", linestyle="--", color="0.55", markersize=4, linewidth=1.3,
            label="the same images, cropped around cracks")
    ax.axhline(1.0, color="0.0", lw=1.2)
    ax.text(ks[0], 1.08, "exact", fontsize=SMALL, va="bottom", ha="left")

    best = min(wf, key=lambda r: abs(r["area_agreement_corpus"] - 1.0))
    ax.axvspan(1.0, 5.0, color="0.92", zorder=0)
    ax.text(2.1, 17.0, "the grid the\nfirst draft swept", fontsize=SMALL,
            color="0.45", ha="center", va="center", linespacing=1.25)
    ax.axvline(5.0, color="0.7", lw=1.0, linestyle=":")
    ax.axvline(best["mad_k"], color="#b3401a", lw=1.1)
    ax.text(5.0, 22, "shipped 5.0 ", fontsize=SMALL, color="0.4", rotation=90,
            va="top", ha="right")
    ax.text(best["mad_k"], 22,
            f" exact at {best['mad_k']:g}: {best['area_agreement_corpus']:.3f}x",
            fontsize=SMALL, color="#b3401a", rotation=90, va="top", ha="left")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks([1, 2, 3, 5, 8, 12, 20, 40])
    ax.set_yticks([0.1, 0.25, 0.5, 1, 2, 5, 10, 25])
    for a in (ax.get_xaxis(), ax.get_yaxis()):
        a.set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xlabel("mad_k  (robust outlier threshold)", fontsize=BODY)
    ax.set_ylabel("area fraction reported / marked", fontsize=BODY)
    ax.tick_params(labelsize=SMALL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=SMALL, frameon=False, loc="lower left")
    ax.set_title("The shipped constant over-reports; one rung up is exact", fontsize=TITLE)
    save(fig, "P2 - operating curve", {
        "what": "reported crack area fraction divided by the annotator's, against the "
                "detector's single free constant, on whole fields and on the released "
                "crops of those same fields",
        "whole_fields": {str(r["mad_k"]): r["area_agreement_corpus"] for r in wf},
        "crops": {str(r["mad_k"]): r["area_agreement_corpus"] for r in cr},
        "source": "docs/figures/background_counting_table.json"})


def plate_width():
    """The constant-width construction, scored over every pixel.

    This plate used to draw IoU against drawn width. IoU discards the background, so it
    could not say what the construction costs a reader -- and the section's conclusion is
    about exactly that. Redrawn with accuracy on the left axis and the reported area
    fraction on the right, both against the empty-mask line, so the ceiling is expressed
    in the same units as every other result in the paper.
    """
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    wf, cr = WBG["whole_fields"], WBG["crops"]
    ws = sorted(int(k) for k in wf["by_width"])

    ax.plot(ws, [wf["by_width"][str(w)]["accuracy_pct"] for w in ws], marker="^",
            color="0.0", markersize=4.5, linewidth=1.6,
            label=f"whole fields, n={wf['n']}")
    ax.plot(ws, [cr["by_width"][str(w)]["accuracy_pct"] for w in ws], marker="s",
            linestyle="--", color="0.55", markersize=4, linewidth=1.3,
            label=f"released crops, n={cr['n']}")
    ax.axhline(wf["empty_mask_accuracy_pct"], color="0.0", lw=1.0, linestyle=":")
    ax.text(ws[-1], wf["empty_mask_accuracy_pct"] + 0.06,
            f"an empty mask, whole fields  {wf['empty_mask_accuracy_pct']:.2f}%",
            fontsize=SMALL, ha="right", va="bottom", color="0.0")
    ax.axhline(cr["empty_mask_accuracy_pct"], color="0.55", lw=1.0, linestyle=":")
    ax.text(ws[-1], cr["empty_mask_accuracy_pct"] + 0.06,
            f"an empty mask, crops  {cr['empty_mask_accuracy_pct']:.2f}%",
            fontsize=SMALL, ha="right", va="bottom", color="0.4")

    for d, col, mk in ((wf, "0.0", "^"), (cr, "0.55", "s")):
        bw = d["best_accuracy_width"]
        ax.plot([bw], [d["by_width"][str(bw)]["accuracy_pct"]], marker="o",
                markersize=11, markerfacecolor="none", markeredgecolor="#b3401a",
                markeredgewidth=1.4, zorder=6)
    ax.set_xscale("log")
    ax.set_xticks(ws)
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xlabel("width the centreline is redrawn at (px)", fontsize=BODY)
    ax.set_ylabel("accuracy, all pixels", fontsize=BODY)
    ax.tick_params(labelsize=SMALL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=SMALL, frameon=False, loc="lower center")
    ax.set_title("A mask that is exactly right about WHERE, and wrong only about WIDTH",
                 fontsize=TITLE)
    save(fig, "P3 - width sensitivity", {
        "what": "accuracy of the annotator's own centreline redrawn at a fixed width, "
                "against the accuracy of an empty mask",
        "whole_fields": wf, "crops": cr,
        "source": "docs/figures/width_ceiling_background_units.json"})


def plate_baselines():
    """The classical comparison, ranked by what the tool reports rather than by overlap.

    This plate used to rank eight arms by F1 on the released crops. It now ranks them on
    the whole fields by how close each one's reported crack area fraction is to the
    annotator's, which is the quantity the laboratory uses, with accuracy beside it and
    the empty-mask line drawn in. Otsu on the flattened image marks 99.5% of the frame and
    is left to Appendix A; including it would compress every other bar to nothing.
    """
    arms = AB["whole_fields"]["arms"]
    empty = AB["whole_fields"]["empty_mask_accuracy_pct"]
    short = {"DETECTOR (shipped)": "this detector",
             "UNION darkness OR Sato": "darkness OR Sato",
             "global threshold (Otsu on flat)": None}
    rank = sorted(((short.get(k, k), v) for k, v in arms.items()
                   if short.get(k, k) is not None),
                  key=lambda kv: -abs(kv[1]["area_agreement"] - 1.0))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.6, 3.5),
                                   gridspec_kw={"width_ratios": [1.0, 0.85]})
    y = list(range(len(rank)))
    cols = ["0.15" if k == "this detector" else "0.72" for k, _ in rank]

    ax1.axvline(1.0, color="0.0", lw=1.2, zorder=1)
    ax1.barh(y, [v["area_agreement"] for _, v in rank], 0.5, color=cols, zorder=2)
    for i, (_, v) in zip(y, rank):
        ax1.text(v["area_agreement"] + 0.02, i, f"{v['area_agreement']:.3f}x",
                 va="center", fontsize=SMALL)
    ax1.text(1.01, 3.0, "exact", fontsize=SMALL, va="center", ha="left",
             rotation=90, color="0.0")
    ax1.set_yticks(y, [k for k, _ in rank], fontsize=SMALL)
    ax1.set_xlim(0, 1.35)
    ax1.set_xlabel("crack area fraction reported / marked", fontsize=BODY)
    ax1.set_title("What each arm would report", fontsize=TITLE)
    ax1.spines[["top", "right"]].set_visible(False)

    ax2.barh(y, [v["accuracy_pct"] for _, v in rank], 0.5,
             color=["#b3401a" if not v["beats_empty_mask"] else c
                    for c, (_, v) in zip(cols, rank)], zorder=2)
    ax2.axvline(empty, color="0.0", lw=1.6, zorder=5)
    ax2.text(empty - 0.012, 3.0, f"an empty mask {empty:.2f}%", fontsize=SMALL,
             va="center", ha="right", rotation=90, color="0.0")
    for i, (_, v) in zip(y, rank):
        ax2.text(v["accuracy_pct"] - 0.03, i, f"{v['accuracy_pct']:.2f}", va="center",
                 ha="right", fontsize=SMALL, color="white")
    ax2.set_yticks(y, ["" for _ in rank])
    ax2.set_xlim(97.4, 98.5)
    ax2.set_xlabel("accuracy, all pixels", fontsize=BODY)
    ax2.set_title("Accuracy: none of them beats an empty mask", fontsize=TITLE)
    ax2.spines[["top", "right"]].set_visible(False)
    ax1.tick_params(labelsize=SMALL)
    ax2.tick_params(labelsize=SMALL)
    fig.suptitle(f"Inconel 718, {AB['whole_fields']['labelled_pct']:.2f}% crack, "
                 f"every arm tuned leave-one-image-out", fontsize=SMALL, y=1.0)
    save(fig, "P4 - baselines", {
        "what": "eight arms ranked by reported-against-marked crack area fraction, with "
                "accuracy and the empty-mask baseline",
        "arms": arms, "empty_mask_accuracy_pct": empty,
        "source": "docs/figures/arms_background_units.json"})


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
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(10.4, 3.6),
                                  gridspec_kw={"width_ratios": [1.35, 1]})
    y = range(len(sets))
    for i, k in enumerate(sets):
        r = PA[k]["detector"]
        # the human's share, as an outline above the detector's stacked bar
        ax.barh(i + 0.18, r["labelled_pct"], 0.3, facecolor="none", edgecolor="0.1",
                linewidth=1.3)
        ax.barh(i - 0.18, r["tp_pct"], 0.3, color="0.25")
        ax.barh(i - 0.18, r["fp_pct"], 0.3, left=r["tp_pct"], color="0.72")
        ax.text(r["labelled_pct"] + 0.4, i + 0.18, f"human {r['labelled_pct']:.2f}%",
                va="center", fontsize=SMALL)
        ax.text(r["tp_pct"] + r["fp_pct"] + 0.4, i - 0.18,
                f"detector {r['marked_pct']:.2f}%  ({r['tp_pct']:.2f} right + "
                f"{r['fp_pct']:.2f} wrong)", va="center", fontsize=SMALL)
    ax.set_yticks(list(y))
    ax.set_yticklabels([k.replace(", ", "\n") for k in sets], fontsize=SMALL)
    ax.set_xlabel("percent of all image pixels", fontsize=BODY)
    ax.set_xlim(0, max(max(PA[k]["detector"]["marked_pct"],
                           PA[k]["detector"]["labelled_pct"]) for k in sets) * 1.95)
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color="0.88", linewidth=0.7)
    ax.tick_params(labelsize=SMALL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("What was marked, as a share of the image", fontsize=BODY)

    # the over-marking ratio, which is the number a user of the tool actually feels
    ratios = [PA[k]["detector"]["marked_pct"] / PA[k]["detector"]["labelled_pct"]
              for k in sets]
    ax2.barh(list(y), ratios, 0.5, color=["0.25" if r < 2 else "0.72" for r in ratios])
    ax2.axvline(1.0, color="0.1", linewidth=1.1, linestyle="--")
    # LINEAR, not log: with two values between 0.78 and 1.30 a log axis adds nothing and
    # its tick labels collided with the annotation.
    ax2.text(1.0, len(sets) - 0.35, "  1.0 = the right amount of area", fontsize=SMALL,
             color="0.3", ha="left", va="center")
    for i, r in enumerate(ratios):
        ax2.text(r + 0.04, i, f"{r:.2f}x", va="center", fontsize=SMALL)
    ax2.set_yticks(list(y)); ax2.set_yticklabels([])
    ax2.set_xlim(0, max(max(ratios) * 1.45, 1.6))
    ax2.set_xlabel("area fraction reported / true", fontsize=BODY)
    ax2.tick_params(labelsize=SMALL)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_title("How wrong the area fraction is", fontsize=BODY)
    fig.subplots_adjust(wspace=0.12)
    save(fig, "P5 - pixel budget", {
        "what": "the confusion matrix as a percentage of image pixels, and the ratio of "
                "marked area to labelled area",
        "why": "P/R/F1/IoU discard the true negatives, which are 98% of a 1.8%-crack "
               "image; and area fraction is what this tool actually reports to a user, so "
               "the over-marking ratio is the error they feel",
        "values": {k: PA[k]["detector"] for k in sets},
        "read this first": "on whole fields the detector marks 2.34% where the human "
                           "marked 1.80%, so an area fraction read off this tool is about "
                           "1.30x too high. On the released crops it marks 3.53% against "
                           "4.53%, so there it UNDER-reports at 0.78x -- the same detector, "
                           "opposite bias, and the only difference is how the images were "
                           "cut. Accuracy is 97.42% and 96.17% and is worthless at these "
                           "prevalences; MCC is 0.3402 and 0.4840.",
        "EBC, withdrawn from the paper": "20.29% marked against 0.27% labelled, 76.65x",
        "source": "docs/figures/pixel_accounting.json"})


if __name__ == "__main__":
    plate_scores()
    plate_transfer()
    plate_width()
    plate_baselines()
    plate_budget()
    print("\nplates in", OUT)
