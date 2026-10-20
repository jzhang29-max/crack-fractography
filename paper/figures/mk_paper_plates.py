#!/usr/bin/env python3
"""Plates for the paper draft, all from measured JSON and none of them hand-drawn.

Sources, all written by a measuring script and never edited by hand:
    docs/figures/public_metrics.json      P/R/F1/IoU + controls, CrackForest + DeepCrack
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
# One table for all three sets, SEM first: the application is micrographs and the pavement
# set is the cross-modality check, not the headline.
ALL = {"Inconel 718\n(SEM alloy)": SEM_PM["Inconel718_crack"],
       "EBC\n(SEM coating)": SEM_PM["EBC_crack"],
       "DeepCrack\n(pavement)": PM["DeepCrack"]}
WC = load(os.path.join(SCRATCH, "width_ceiling.json"), "width ceiling")
MF = load(os.path.join(REPO, "docs/figures/metric_figures.json"), "corpus metric figures")


# ---------------------------------------------------------------- plate: public scores
def plate_scores():
    mets = ["precision", "recall", "f1", "iou"]
    fig, axes = plt.subplots(1, 3, figsize=(11.0, 3.3))
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
        ax.set_title(f"{name}\nn={r['n']}, prevalence {100 * r['prevalence']:.2f}%",
                     fontsize=SMALL)
        ax.tick_params(labelsize=SMALL)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("score", fontsize=BODY)
    axes[0].legend(fontsize=SMALL, frameon=False, loc="upper left")
    fig.suptitle("The detector on three public crack sets, against its own "
                 "no-information floors", fontsize=TITLE, y=1.04)
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
    marks = {"DeepCrack": ("o", "-", "0.55")}
    sem = SEM_PM["Inconel718_crack"]["per_k"]
    ks = sorted((float(k) for k in sem), reverse=True)
    def pick(d, k):
        for cand in (str(k), f"{k:g}", f"{k:.1f}"):
            if cand in d:
                return d[cand]
        raise KeyError(f"{k} not in {sorted(d)}")

    ax.plot(ks, [pick(sem, k)["f1"] for k in ks], marker="^", linestyle="-",
            color="0.0", label="Inconel 718 (SEM alloy)", markersize=4.5, linewidth=1.6)
    for d, (mk, ls, col) in marks.items():
        pk = PM[d]["per_k"]
        ks = sorted((float(k) for k in pk), reverse=True)
        ax.plot(ks, [pick(pk, k)["f1"] for k in ks],
                marker=mk, linestyle="--", color=col, label=d + " (pavement)",
                markersize=4, linewidth=1.4)
    ax.axvline(5.0, color="0.7", linewidth=1, linestyle=":")
    ax.text(5.0, 0.03, " shipped (fitted on SEM steel)", fontsize=SMALL, color="0.4",
            rotation=90, va="bottom")
    ax.set_xlabel("mad_k  (robust outlier threshold)", fontsize=BODY)
    ax.set_ylabel("mean F1 per image", fontsize=BODY)
    ax.invert_xaxis()
    ax.tick_params(labelsize=SMALL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=SMALL, frameon=False)
    ax.set_title("The one free constant: optimal unchanged on SEM, not on pavement",
                 fontsize=TITLE)
    # RENAMED. It was "P2 - transfer" while it carried two datasets and argued that a
    # refitted constant transfers between them. With one dataset it is an operating curve
    # and the old name would print under a figure that no longer shows transfer.
    save(fig, "P2 - operating curve", {
        "what": "mean F1 against the detector's single free constant",
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
    for d, (mk, ls, col) in {"DeepCrack": ("o", "--", "0.55")}.items():
        c = WC[d]["iou_by_trace_width"]
        ws = sorted(int(k) for k in c)
        ax.plot(ws, [c[str(w)] for w in ws], marker=mk, linestyle=ls, color=col,
                markersize=4, linewidth=1.4,
                label=f"{d}, pavement  (label {WC[d]['label_stroke_px_median']:.0f} px)")
        series.append((d, ws, [c[str(w)] for w in ws]))
    ce, cw = MF["ceiling"], MF["ceiling_widths"]
    corpus = [sum(ce[str(w)]["iou"]) / len(ce[str(w)]["iou"]) for w in cw]
    # NO STROKE WIDTH ON THIS SERIES. An earlier draft annotated it "label 35 px" from a
    # number measured by a different instrument on a different set of frames; the curve's
    # own peak at 9 px contradicts it, and a 35 px label is best reconstructed by a 35 px
    # redraw. The tile cache that would let it be re-measured with half_width() is not on
    # this machine, so the annotation is dropped rather than guessed.
    ax.plot(cw, corpus, marker="^", linestyle="-.", color="0.0", markersize=4,
            linewidth=1.4, label="this corpus, 26 tiles")
    ax.axhline(SEM_PM["Inconel718_crack"]["loo"]["iou"], color="0.0", linewidth=.9,
               linestyle=":")
    ax.text(40, SEM_PM["Inconel718_crack"]["loo"]["iou"] + .012, "detector on Inconel 718",
            fontsize=SMALL, ha="right", color="0.0")
    for d, col in (("DeepCrack", "0.55"),):
        ax.axhline(PM[d]["loo"]["iou"], color=col, linewidth=.9, linestyle=":")
        ax.text(40, PM[d]["loo"]["iou"] - .028, f"detector on {d}", fontsize=SMALL,
                ha="right", color=col)
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
                         "tracks that variation can and does score ABOVE this curve -- "
                         "the detector reaches IoU 0.681 on DeepCrack where the best "
                         "constant-width redraw reaches 0.554.",
        "peaks": {d: {"iou": WC[d]["ceiling_iou"], "at_width_px": WC[d]["ceiling_at_width"],
                      "label_stroke_px": WC[d]["label_stroke_px_median"]} for d in WC},
        "corpus_peak": {"iou": max(corpus), "at_width_px": cw[corpus.index(max(corpus))]},
        "corpus_stroke_width": "NOT MEASURED HERE. The tile cache tilebench.load() needs "
                               "is absent on this machine, so no stroke width is claimed "
                               "for the corpus series.",
        "the finding": "the corpus and DeepCrack curves nearly coincide (peaks 0.547 at "
                       "9 px and 0.554 at 7 px), so label stroke width does NOT explain "
                       "why the detector scores IoU 0.68 on DeepCrack and about 0.33-0.42 "
                       "on the corpus.",
        "source": "width_ceiling.json + docs/figures/metric_figures.json"})


# ----------------------------------------------------- plate: against classical methods
def plate_baselines():
    bl = load(os.path.join(SCRATCH, "baselines_full.json"), "pavement baselines")["results"]
    sb = load(os.path.join(REPO, "docs/figures/sem_baselines.json"), "SEM baselines")["results"]
    sets = [("Inconel 718 (SEM alloy)", sb["Inconel718_crack"], SEM_PM["Inconel718_crack"]["n"]),
            ("EBC (SEM coating)", sb["EBC_crack"], SEM_PM["EBC_crack"]["n"]),
            ("DeepCrack (pavement)", bl["DeepCrack"], PM["DeepCrack"]["n"])]
    nice = {"YOUR DETECTOR": "this detector",
            "global threshold (Otsu on flat)": "Otsu on flattened"}
    # WIDE GUTTERS. At the default spacing each panel's value labels ran into the next
    # panel's arm names and the plate was unreadable at the right-hand edge.
    fig, axes = plt.subplots(1, 3, figsize=(13.6, 3.5))
    fig.subplots_adjust(wspace=0.62)
    for ax, (name, r, n) in zip(axes, sets):
        # SORTED BY SCORE, not by a fixed arm order. The detector is first on pavement and
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
        ax.set_title(f"{name}\nn={n} \u2014 this detector ranks {pos} of {len(rank)}",
                     fontsize=SMALL)
        ax.tick_params(labelsize=SMALL)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Against classical detectors: first on pavement, not on either SEM set",
                 fontsize=TITLE, y=1.05)
    save(fig, "P4 - baselines", {
        "what": "every arm's own best parameter chosen leave-one-image-out, same images, "
                "same scoring function",
        "ranks": {name: {"detector": r["YOUR DETECTOR"],
                         "rank": len(r) - sorted(r.items(), key=lambda kv: kv[1]).index(
                             ("YOUR DETECTOR", r["YOUR DETECTOR"])),
                         "all": r} for name, r, _ in sets},
        "THE RESULT": "the detector leads on pavement and does not lead on either SEM "
                      "set: 3 of 7 on Inconel 718, beaten by Sauvola and Sato, and 5 of 7 "
                      "on the EBC coating. It was built for micrographs.",
        "FIXES A PRIOR NUMBER": "docs/figures/public_baselines.json reports the detector "
                                "at 0.8209 on DeepCrack; that run scored the first 120 of "
                                "237 images and omitted k=1.0. The full split gives "
                                "0.7932.",
        "source": "sem_baselines.json + baselines_full.json"})


if __name__ == "__main__":
    plate_scores()
    plate_transfer()
    plate_width()
    plate_baselines()
    print("\nplates in", OUT)
