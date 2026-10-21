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
    mets = ["precision", "recall", "f1", "iou"]
    fig, axes = plt.subplots(1, 1, figsize=(4.6, 3.3), squeeze=False)
    axes = axes[0]
    for ax, (name, r) in zip(axes, ALL.items()):
        det = [r["loo"][m] for m in mets]
        floor = [r["controls"]["mark_everything"][m] for m in mets]
        rnd = [r["controls"]["equal_area_random"][m] for m in mets]
        x = range(len(mets))
        ax.bar([i - 0.26 for i in x], det, 0.26, color="0.25", label="detector")
        ax.bar(list(x), floor, 0.26, color="0.62", label="mark everything")
        ax.bar([i + 0.26 for i in x], rnd, 0.26, color="0.85", edgecolor="0.4",
               linewidth=.6, label="equal-area random")
        for i, v in enumerate(det):
            ax.text(i - 0.26, v + .02, f"{v:.2f}", ha="center", fontsize=SMALL)
        ax.set_xticks(list(x)); ax.set_xticklabels(["P", "R", "F1", "IoU"], fontsize=BODY)
        ax.set_ylim(0, 1.0)
        ax.set_title(f"n={r['n']} whole fields, prevalence "
                     f"{100 * r['prevalence']:.2f}%", fontsize=SMALL)
        ax.tick_params(labelsize=SMALL)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("score", fontsize=BODY)
    axes[0].legend(fontsize=SMALL, frameon=False, loc="upper left")
    fig.suptitle("Inconel 718 against its own no-information floors",
                 fontsize=TITLE, y=1.02)
    save(fig, "P1 - public scores", {
        "what": "P/R/F1/IoU at 0 px tolerance, mad_k leave-one-image-out, three controls",
        "values": {k: {"detector": v["loo"], "mark_everything":
                       v["controls"]["mark_everything"], "n": v["n"],
                       "prevalence": v["prevalence"]} for k, v in ALL.items()},
        "source": "sem_public_metrics.json + public_metrics.json"})


# ------------------------------------------------------- plate: one constant transfers
def plate_transfer():
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    # ONE SERIES NOW. This plate used to carry two datasets and the sentence "one refitted
    # constant transfers". With CrackForest out of the paper there is one dataset left and
    # no transfer can be shown, so the plate is an operating curve and the claim is gone.
    # WHOLE FIELDS. This read SEM_PM -- the crops -- for one build, so both series on this
    # plate were the same data drawn twice and the curves lay exactly on top of each other
    # while the legend claimed they were different sets.
    sem = SEM_OR["Inconel718_crack"]["per_k"]
    ks = sorted((float(k) for k in sem), reverse=True)
    def pick(d, k):
        for cand in (str(k), f"{k:g}", f"{k:.1f}"):
            if cand in d:
                return d[cand]
        raise KeyError(f"{k} not in {sorted(d)}")

    ax.plot(ks, [pick(sem, k)["f1"] for k in ks], marker="^", linestyle="-",
            color="0.0", label="Inconel 718, whole fields", markersize=4.5, linewidth=1.6)
    # THE SAME IMAGES, CROPPED. Not a second dataset: the released crops come from these
    # very fields, cut around the cracks, and that alone lifts F1 by about 0.15 at every
    # setting. It is the clearest statement in the paper of how much a benchmark's framing
    # is worth, and it costs one extra line to show.
    crop = SEM_PM["Inconel718_crack"]["per_k"]
    ax.plot(ks, [pick(crop, k)["f1"] for k in ks], marker="s", linestyle="--",
            color="0.55", label="the same images, cropped around cracks", markersize=4,
            linewidth=1.3)
    ax.axvline(5.0, color="0.7", linewidth=1, linestyle=":")
    ax.text(5.0, 0.03, " shipped (fitted on SEM steel)", fontsize=SMALL, color="0.4",
            rotation=90, va="bottom")
    ax.set_xlabel("mad_k  (robust outlier threshold)", fontsize=BODY)
    ax.set_ylabel("mean F1 per image", fontsize=BODY)
    ax.invert_xaxis()
    ax.tick_params(labelsize=SMALL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=SMALL, frameon=False)
    ax.set_title("The one free constant on SEM: the shipped value is the best one",
                 fontsize=TITLE)
    # RENAMED. It was "P2 - transfer" while it carried two datasets and argued that a
    # refitted constant transfers between them. With one dataset it is an operating curve
    # and the old name would print under a figure that no longer shows transfer.
    save(fig, "P2 - operating curve", {
        "what": "mean F1 against the detector's single free constant, on whole SEM "
                "fields and on the released crops of those same fields",
        "per_k": {d: {k: v["f1"] for k, v in PM[d]["per_k"].items()} for d in PM},
        "source": "docs/figures/public_metrics.json"})


# ------------------------------------------------- plate: what width alone does to IoU
def plate_width():
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    series = []
    sw = SEM_WC["Inconel718_crack"]
    ws = sorted(int(k) for k in sw["iou_by_trace_width"])
    ax.plot(ws, [sw["iou_by_trace_width"][str(w)] for w in ws], marker="^", linestyle="-",
            color="0.0", markersize=4.5, linewidth=1.6,
            label=f"Inconel 718, SEM  (label {sw['label_stroke_px_median']:.0f} px)")

    ce, cw = MF["ceiling"], MF["ceiling_widths"]
    corpus = [sum(ce[str(w)]["iou"]) / len(ce[str(w)]["iou"]) for w in cw]
    # NO STROKE WIDTH ON THIS SERIES. An earlier draft annotated it "label 35 px" from a
    # number measured by a different instrument on a different set of frames; the curve's
    # own peak at 9 px contradicts it, and a 35 px label is best reconstructed by a 35 px
    # redraw. The tile cache that would let it be re-measured with half_width() is not on
    # this machine, so the annotation is dropped rather than guessed.
    ax.plot(cw, corpus, marker="o", linestyle="-.", color="0.3", markersize=3.6,
            linewidth=1.3, markerfacecolor="white", label="this corpus, 26 tiles")
    ax.axhline(SEM_OR["Inconel718_crack"]["loo"]["iou"], color="0.0", linewidth=.9,
               linestyle=":")
    ax.text(1.5, SEM_OR["Inconel718_crack"]["loo"]["iou"] - .030,
            "detector on Inconel 718, whole fields", fontsize=SMALL, ha="left",
            color="0.0")

    ax.set_xlabel("width the centreline is redrawn at (px)", fontsize=BODY)
    ax.set_ylabel("IoU against the label", fontsize=BODY)
    ax.tick_params(labelsize=SMALL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=SMALL, frameon=False, loc="upper right")
    ax.set_title("Right place, wrong width: what IoU costs for width alone",
                 fontsize=TITLE)
    save(fig, "P3 - width sensitivity", {
        "what": "the label's own centreline redrawn at a fixed width and scored against "
                "the label. Zero localisation error by construction.",
        "NOT A CEILING": "this is a constant-width reconstruction, not an oracle. A real "
                         "label varies in width along its length, so a detector that "
                         "tracks that variation can score ABOVE this curve.",
        "peaks": {d: {"iou": WC[d]["ceiling_iou"], "at_width_px": WC[d]["ceiling_at_width"],
                      "label_stroke_px": WC[d]["label_stroke_px_median"]} for d in WC},
        "corpus_peak": {"iou": max(corpus), "at_width_px": cw[corpus.index(max(corpus))]},
        "corpus_stroke_width": "NOT MEASURED HERE. The tile cache tilebench.load() needs "
                               "is absent on this machine, so no stroke width is claimed "
                               "for the corpus series.",
        "the finding": "the two curves peak at different widths -- 21 px for Inconel 718's "
                       "labels and 9 px for this project's corpus tiles -- so an IoU is not "
                       "comparable across corpora whose annotation differs. The stronger "
                       "version of this argument, two SEM sets four times apart in brush "
                       "width reaching the same ceiling to within 0.007, used the EBC "
                       "coating and was withdrawn with it.",
        "source": "width_ceiling.json + docs/figures/metric_figures.json"})


# ----------------------------------------------------- plate: against classical methods
def plate_baselines():
    sb = load(os.path.join(REPO, "docs/figures/sem_baselines.json"), "SEM baselines")["results"]
    # The baseline sweep was run on the released CROPS, which is the only set every arm has
    # been scored on. It is labelled as such: the detector's own whole-field score is lower
    # (F1 0.3444 against 0.4958), so this panel flatters every arm equally and must not be
    # read as a whole-field result.
    sets = [("Inconel 718 (SEM alloy)", sb["Inconel718_crack"],
             SEM_PM["Inconel718_crack"]["n"])]
    nice = {"YOUR DETECTOR": "this detector",
            "global threshold (Otsu on flat)": "Otsu on flattened"}
    # WIDE GUTTERS. At the default spacing each panel's value labels ran into the next
    # panel's arm names and the plate was unreadable at the right-hand edge.
    fig, axes = plt.subplots(1, 1, figsize=(5.6, 3.5), squeeze=False)
    axes = axes[0]
    for ax, (name, r, n) in zip(axes, sets):
        # SORTED BY SCORE, not by a fixed arm order. The detector is
        # third and fifth on the two SEM sets; a fixed order would bury that.
        rank = sorted(r.items(), key=lambda kv: kv[1])
        vals = [v for _, v in rank]
        names = [nice.get(k, k) for k, _ in rank]
        cols = ["0.15" if k == "YOUR DETECTOR" else "0.72" for k, _ in rank]
        ypos = list(range(len(rank)))
        ax.barh(ypos, vals, 0.62, color=cols)
        for y, v in zip(ypos, vals):
            ax.text(v + .012, y, f"{v:.3f}", va="center", fontsize=SMALL)
        pos = len(rank) - [k for k, _ in rank].index("YOUR DETECTOR")
        ax.set_yticks(ypos); ax.set_yticklabels(names, fontsize=SMALL)
        ax.set_xlim(0, max(vals) * 1.34)
        ax.set_xlabel("mean F1 per image", fontsize=BODY)
        ax.set_title(f"{name}, released crops\nn={n} \u2014 this detector ranks "
                     f"{pos} of {len(rank)}",
                     fontsize=SMALL)
        ax.tick_params(labelsize=SMALL)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Against classical detectors on Inconel 718: this detector does not lead",
                 fontsize=TITLE, y=1.05)
    save(fig, "P4 - baselines", {
        "what": "every arm's own best parameter chosen leave-one-image-out, same images, "
                "same scoring function",
        "ranks": {name: {"detector": r["YOUR DETECTOR"],
                         "rank": len(r) - sorted(r.items(), key=lambda kv: kv[1]).index(
                             ("YOUR DETECTOR", r["YOUR DETECTOR"])),
                         "all": r} for name, r, _ in sets},
        "THE RESULT": "the detector ranks 3 of 7 on Inconel 718, beaten by Sauvola local "
                      "thresholding and a Sato ridge filter. It was built for micrographs "
                      "and does not lead on them.",
        "SCOPE": "run on the released crops, the only set all seven arms share. The "
                 "detector's whole-field score is lower (0.3444 against 0.4958), so every "
                 "arm here is flattered by the same cropping.",
        "source": "sem_baselines.json"})


# --------------------------------------------------- plate: the pixel budget
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
