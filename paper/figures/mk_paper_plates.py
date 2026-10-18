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
WC = load(os.path.join(SCRATCH, "width_ceiling.json"), "width ceiling")
MF = load(os.path.join(REPO, "docs/figures/metric_figures.json"), "corpus metric figures")


# ---------------------------------------------------------------- plate: public scores
def plate_scores():
    ds = ["DeepCrack", "CrackForest"]
    mets = ["precision", "recall", "f1", "iou"]
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.3))
    for ax, d in zip(axes, ds):
        r = PM[d]
        det = [r["loo"][m] for m in mets]
        floor = [r["controls"]["mark_everything"][m] for m in mets]
        rnd = [r["controls"]["equal_area_random"][m] for m in mets]
        x = range(len(mets))
        ax.bar([i - 0.26 for i in x], det, 0.26, color="0.25", label="detector")
        ax.bar([i for i in x], floor, 0.26, color="0.62", label="mark everything")
        ax.bar([i + 0.26 for i in x], rnd, 0.26, color="0.85", edgecolor="0.4",
               linewidth=.6, label="equal-area random")
        for i, v in enumerate(det):
            ax.text(i - 0.26, v + .02, f"{v:.2f}", ha="center", fontsize=SMALL)
        ax.set_xticks(list(x)); ax.set_xticklabels(["P", "R", "F1", "IoU"], fontsize=BODY)
        ax.set_ylim(0, 1.0)
        ax.set_title(f"{d}  (n={r['n']}, prevalence {100 * r['prevalence']:.2f}%)",
                     fontsize=BODY)
        ax.tick_params(labelsize=SMALL)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("score", fontsize=BODY)
    axes[0].legend(fontsize=SMALL, frameon=False, loc="upper right")
    fig.suptitle("The detector on public crack datasets, against its own no-information "
                 "floors", fontsize=TITLE, y=1.02)
    save(fig, "P1 - public scores", {
        "what": "precision, recall, F1 and IoU at 0 px tolerance, mad_k chosen "
                "leave-one-image-out, against two controls",
        "values": {d: {"detector": PM[d]["loo"],
                       "mark_everything": PM[d]["controls"]["mark_everything"],
                       "equal_area_random": PM[d]["controls"]["equal_area_random"],
                       "n": PM[d]["n"], "prevalence": PM[d]["prevalence"]} for d in ds},
        "source": "docs/figures/public_metrics.json"})


# ------------------------------------------------------- plate: one constant transfers
def plate_transfer():
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    marks = {"DeepCrack": ("o", "-", "0.2"), "CrackForest": ("s", "--", "0.5")}
    for d, (mk, ls, col) in marks.items():
        pk = PM[d]["per_k"]
        ks = sorted((float(k) for k in pk), reverse=True)
        ax.plot(ks, [pk[str(k) if str(k) in pk else f"{k:g}"]["f1"] for k in ks],
                marker=mk, linestyle=ls, color=col, label=d, markersize=4, linewidth=1.4)
    ax.axvline(5.0, color="0.7", linewidth=1, linestyle=":")
    ax.text(5.0, 0.03, " shipped (fitted on SEM steel)", fontsize=SMALL, color="0.4",
            rotation=90, va="bottom")
    ax.set_xlabel("mad_k  (robust outlier threshold)", fontsize=BODY)
    ax.set_ylabel("mean F1 per image", fontsize=BODY)
    ax.invert_xaxis()
    ax.tick_params(labelsize=SMALL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=SMALL, frameon=False)
    ax.set_title("One free constant, two datasets", fontsize=TITLE)
    save(fig, "P2 - transfer", {
        "what": "mean F1 against the detector's single free constant on each dataset",
        "per_k": {d: {k: v["f1"] for k, v in PM[d]["per_k"].items()} for d in PM},
        "source": "docs/figures/public_metrics.json"})


# ------------------------------------------------- plate: what width alone does to IoU
def plate_width():
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    series = []
    for d, (mk, ls, col) in {"DeepCrack": ("o", "-", "0.2"),
                             "CrackForest": ("s", "--", "0.5")}.items():
        c = WC[d]["iou_by_trace_width"]
        ws = sorted(int(k) for k in c)
        ax.plot(ws, [c[str(w)] for w in ws], marker=mk, linestyle=ls, color=col,
                markersize=4, linewidth=1.4,
                label=f"{d}  (label {WC[d]['label_stroke_px_median']:.0f} px)")
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
    for d, col in (("DeepCrack", "0.2"), ("CrackForest", "0.5")):
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
    bl = load(os.path.join(SCRATCH, "baselines_full.json"), "full-split baselines")["results"]
    order = ["YOUR DETECTOR", "percentile threshold", "Sato ridge", "Meijering ridge",
             "Sauvola local", "global threshold (Otsu on flat)", "Frangi ridge"]
    nice = {"YOUR DETECTOR": "this detector",
            "global threshold (Otsu on flat)": "Otsu on flattened"}
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.4))
    for ax, d in zip(axes, ["DeepCrack", "CrackForest"]):
        vals = [bl[d][k] for k in order]
        names = [nice.get(k, k) for k in order]
        ypos = list(range(len(order)))[::-1]
        cols = ["0.2" if k == "YOUR DETECTOR" else "0.72" for k in order]
        ax.barh(ypos, vals, 0.62, color=cols)
        for y, v in zip(ypos, vals):
            ax.text(v + .012, y, f"{v:.3f}", va="center", fontsize=SMALL)
        ax.set_yticks(ypos); ax.set_yticklabels(names, fontsize=SMALL)
        ax.set_xlim(0, 1.0); ax.set_xlabel("mean F1 per image", fontsize=BODY)
        n = PM[d]["n"]
        ax.set_title(f"{d}  (n={n})", fontsize=BODY)
        ax.tick_params(labelsize=SMALL)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Against classical detectors, every arm tuned the same way on the same "
                 "images", fontsize=TITLE, y=1.03)
    save(fig, "P4 - baselines", {
        "what": "every arm's own best parameter chosen leave-one-image-out, 0 px "
                "tolerance, same images, same scoring function",
        "values": bl,
        "FIXES A PRIOR NUMBER": "docs/figures/public_baselines.json reports the detector "
                                "at 0.8209 on DeepCrack. That run scored the FIRST 120 of "
                                "the 237 test images and omitted k=1.0 from the "
                                "detector's grid. On the full split the detector is "
                                "0.7932, which agrees with public_metrics.json to four "
                                "decimals. The ranking is unchanged -- 1 of 7 on "
                                "DeepCrack, 3 of 7 on CrackForest -- but the number is "
                                "not the same and must not be quoted from the old file.",
        "source": "baselines_full.json, re-run on the complete test splits"})


if __name__ == "__main__":
    plate_scores()
    plate_transfer()
    plate_width()
    plate_baselines()
    print("\nplates in", OUT)
