#!/usr/bin/env python3
"""Plate P8: precision, recall and F1 for the CRACK class, and the curve they sit on.

WHY THIS PLATE EXISTS. The paper leads with measures computed over every pixel of the
frame -- area agreement, pixel accuracy against an all-background prediction, the four-way
pixel budget -- because at 1.80% crack prevalence the overlap measures throw away the 98%
of the frame that is background. That ordering is not changed by this plate. What this
plate does is SHOW the overlap measures for the crack class rather than only mention them,
so a reader who wants precision, recall and F1 can read them off a figure instead of
taking the paper's word that they were computed.

WHAT IS AND IS NOT DRAWN, and why each is a rule rather than a preference:

  THE COLLECTION IS THE FULLY ANNOTATED PUBLIC ONE. Both panels are Zenodo 23045328
  `Inconel718_crack`, whose masks are anti-aliased binary and cover every pixel
  (analysis/research/improve/sem_originals_eval.py checks the histogram rather than
  assuming it: 94.7% exactly 0, 4.3% at 246 or above, 0.52% in between). Because every
  pixel carries a verdict, precision here is a point estimate against that annotation and
  is drawn as a bar.

  THIS LABORATORY'S OWN FRAMES ARE NOT DRAWN, AND THAT IS THE POINT OF THE CAPTION NOTE.
  On the lab corpus only part of each frame was ever refereed, so a predicted pixel
  outside the painted region has no verdict at all; precision there is a bracket, not a
  number (docs/DATASET_RELEASE_SCOPE.md records [0.29, 0.99]), and recall and precision
  are measured on DIFFERENT frame sets and are never pooled into an F1
  (docs/figures/lab_madk_sweep.json, "scoring"). Nothing from that corpus can be put on
  these axes without inventing a denominator, so none of it is. The caption JSON carries
  the bracket and its source instead.

  WHAT WAS SCORED IS THE DETECTOR'S OWN MASK. `emit()` in sem_originals_eval.py is the
  multiscale darkness cut, cleaned at min_area_px = 13, components under 40 px dropped,
  region classifier off. No human annotation is unioned in and none is subtracted, so this
  is not a gated mask and the score is not partly a score of the human.

  THE SELECTION RULE IS NAMED. mad_k is chosen leave-one-IMAGE-out. On this collection the
  rule returns the same k for every held-out image, so the leave-one-out value is
  numerically identical to the fixed k = 5.0 value -- asserted below, not assumed -- and
  5.0 is the LARGEST value in the grid, which is the same grid-edge caveat Section 3.4
  makes for the area endpoint.

  NO BALANCED ACCURACY AND NO MCC. Both are in the source files and both are excluded here
  at the author's direction.

House style is journal_style.py and is applied once by J.use(): no title in the artwork,
bars from zero, (a)/(b) outside above-left, colour for identity only, and the 8 pt type
floor asserted by J.save after the write.

Run with the SEM repo's interpreter (this one has matplotlib):
    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_crack_overlap.py
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import journal_style as J          # noqa: E402  -- the target journals' own rules

J.use()

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

NAME = "P8 - crack overlap"
MEASURES = [("precision", "Precision"), ("recall", "Recall"), ("f1", "F1")]


def load(rel, what):
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        raise SystemExit(f"missing {what}: {path} -- run its measuring script first")
    return json.load(open(path))


ORIG = load("docs/figures/sem_originals_metrics.json", "SEM whole fields")
CROPS = load("docs/figures/sem_public_metrics.json", "SEM released crops")
PAX = load("docs/figures/pixel_accounting.json", "pixel accounting")["sets"]

# EBC_crack is measured in both files and is NOT drawn: it is a ceramic barrier coating,
# withdrawn from this paper, and its numbers (F1 0.0201 on whole fields) would be read as
# this detector's performance on a metal. DeepCrack and CrackForest are not drawn either:
# they are road surfaces, and the paper is about micrographs.
SETS = [
    ("whole fields", ORIG["datasets"]["Inconel718_crack"],
     "Inconel 718, whole fields", J.ACCENT, "o", "-"),
    ("released crops", CROPS["datasets"]["Inconel718_crack"],
     "Inconel 718, released crops", J.ACCENT2, "s", "--"),
]


def selected_k(d):
    """The grid point the leave-one-image-out rule lands on, found rather than assumed.

    If the two files ever disagree -- a re-measurement that changes `loo` without changing
    `per_k`, or a selection that genuinely varies by held-out image -- this raises instead
    of letting the plate label a fixed-k point as the selected one.
    """
    hit = [k for k in d["per_k"]
           if all(abs(d["per_k"][k][m] - d["loo"][m]) < 1e-12 for m, _ in MEASURES)]
    if len(hit) != 1:
        raise SystemExit(
            f"the leave-one-image-out value matches {len(hit)} grid points {hit}; it is "
            "no longer a single fixed k, so panel (b) must not mark one")
    return hit[0]


def check_against_pixel_accounting():
    """The same three numbers live in a second file. Read both and require agreement.

    pixel_accounting.json is written by a different script from the two metrics files, so
    this is the one cheap check available that would actually fail if one of them were
    re-measured and the other left behind.
    """
    for (_, d, pk, _, _, _) in SETS:
        for m, _lab in MEASURES:
            a, b = d["loo"][m], PAX[pk]["detector"][m]
            if abs(a - b) > 1e-9:
                raise SystemExit(f"{pk}: {m} is {a} in the metrics file and {b} in "
                                 "pixel_accounting.json -- one of them is stale")


def plate():
    check_against_pixel_accounting()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(J.PAGEW, 2.85), layout="constrained",
                                   gridspec_kw={"width_ratios": [1.0, 1.0]})

    # ---- (a) the three measures, from zero, with the no-information control on each ----
    # THE LEGEND IS IN PANEL (b), NOT HERE. Both panels use the same two colours, so one
    # legend serves both; and the mark-everything control reaches recall 1.000, which puts
    # a marker exactly where a legend in this panel would sit. The first draft of this
    # plate had that collision -- the tick struck through the word "31" in the legend.
    x = list(range(len(MEASURES)))
    w = 0.34
    for i, (short, d, _pk, col, _mk, _ls) in enumerate(SETS):
        off = (i - 0.5) * w
        ax1.bar([xx + off for xx in x], [d["loo"][m] for m, _ in MEASURES], w,
                color=col, edgecolor=J.INK, linewidth=0.5, zorder=2)
        # mark-everything: recall 1.000 by construction, precision equal to prevalence.
        # It is the floor each bar has to clear, and on recall it is the ceiling too.
        ax1.plot([xx + off for xx in x],
                 [d["controls"]["mark_everything"][m] for m, _ in MEASURES],
                 linestyle="none", marker="_", color=J.INK, markersize=8,
                 markeredgewidth=1.3, zorder=5)
    ax1.set_xticks(x, [lab for _, lab in MEASURES])
    ax1.set_xlim(-0.55, len(MEASURES) - 0.45)
    ax1.set_ylim(0, 1.06)
    ax1.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax1.set_ylabel("Score, crack class")
    J.panel_label(ax1, "a")

    # ---- (b) the operating curve the three numbers are one point of --------------------
    for short, d, _pk, col, mk, ls in SETS:
        ks = sorted(d["per_k"], key=float)
        ax2.plot([d["per_k"][k]["recall"] for k in ks],
                 [d["per_k"][k]["precision"] for k in ks],
                 marker=mk, linestyle=ls, color=col,
                 markerfacecolor="white" if mk == "s" else col, markersize=3.6)
        sel = selected_k(d)
        ax2.plot([d["per_k"][sel]["recall"]], [d["per_k"][sel]["precision"]],
                 marker="D", color=J.INK, markersize=5.0, linestyle="none", zorder=6)
        me = d["controls"]["mark_everything"]
        ax2.plot([me["recall"]], [me["precision"]], marker="_", color=J.INK,
                 markersize=8, markeredgewidth=1.3, linestyle="none", zorder=6)
    ax2.set_xlim(0, 1.04)
    ax2.set_ylim(0, 0.64)
    ax2.set_xlabel("Recall, crack class")
    ax2.set_ylabel("Precision, crack class")
    # ONE legend for both panels, in the quadrant of this one that carries no data.
    ax2.legend(handles=[
        Line2D([], [], color=c, marker=m, linestyle=l, markersize=3.6,
               markerfacecolor="white" if m == "s" else c,
               label=f"{s} ($n$ = {d['n']})")
        for s, d, _pk, c, m, l in SETS] + [
        Line2D([], [], color=J.INK, marker="D", linestyle="none", markersize=5.0,
               label="selected setting"),
        Line2D([], [], color=J.INK, marker="_", linestyle="none", markersize=8,
               markeredgewidth=1.3, label="mark everything")],
        loc="lower left", handlelength=1.6, handletextpad=0.5, borderpad=0.25,
        labelspacing=0.32)
    J.panel_label(ax2, "b")

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    caption(ORIG, CROPS)


def caption(orig, crops):
    wf, cr = SETS[0][1], SETS[1][1]
    vals = {}
    for short, d, pk, _c, _m, _l in SETS:
        sel = selected_k(d)
        vals[pk] = {
            "n_images": d["n"],
            "annotated_crack_fraction": d["prevalence"],
            "precision": d["loo"]["precision"],
            "recall": d["loo"]["recall"],
            "f1": d["loo"]["f1"],
            "iou_not_drawn": d["loo"]["iou"],
            "selection": "mad_k leave-one-IMAGE-out; identical to fixed mad_k = "
                         f"{sel} on this collection, and {sel} is the largest value in "
                         "the grid",
            "mark_everything_control": d["controls"]["mark_everything"],
            "equal_area_random_control": d["controls"]["equal_area_random"],
            "precision_over_its_floor":
                d["loo"]["precision"] / d["controls"]["mark_everything"]["precision"],
            "operating_curve_drawn_in_panel_b":
                {k: {"recall": d["per_k"][k]["recall"],
                     "precision": d["per_k"][k]["precision"]}
                 for k in sorted(d["per_k"], key=float)},
        }
    json.dump({
        "what": "(a) precision, recall and F1 for the crack class on the public Inconel "
                "718 collection, whole fields beside the released crops cut from them, "
                "with the score a mask that marks every pixel would reach drawn on each "
                "bar; (b) the same two collections as precision against recall over the "
                "seven values of the detector's one free constant, with the selected "
                "setting and the mark-everything control marked",
        "why": "the paper's primary endpoints are computed over every pixel of the frame "
               "because the overlap measures discard the 98% of a 1.80%-crack image that "
               "is background. This plate does not replace them; it shows the overlap "
               "measures for the crack class instead of only mentioning them, which is "
               "what was asked for twice.",
        "what was scored": "the detector's own emitted mask -- multiscale darkness cut, "
                           "clean_mask(min_area_px=13), components under 40 px dropped, "
                           "region classifier OFF (emit() in "
                           "analysis/research/improve/sem_originals_eval.py). NOT a gated "
                           "mask: no human paint is unioned in and none is subtracted, so "
                           "the score is not partly a score of the annotator.",
        "tolerance": "0 px. Every pixel must land exactly. docs/CLAIMS.md R5 records 2 px "
                     "of slack as worth +0.09 F1 on this project's own tiles and roughly "
                     "22 F1 points in the literature, so these values are not comparable "
                     "with a published number measured at 2 px.",
        "pooled or held out": "mean per image of a leave-one-IMAGE-out selection of "
                              "mad_k. Not a pooled-over-all-pixels figure, and not a "
                              "value fitted on the images it is reported on.",
        "values": vals,
        "the crop-versus-field gap is a finding, not an inconsistency":
            "precision is {:.4f} on the whole fields and {:.4f} on crops cut from those "
            "same fields, a factor of {:.2f}, while recall moves only {:.2f}x. Cropping "
            "around the subject raises annotated prevalence from {:.2f}% to {:.2f}%, a "
            "factor of {:.2f}, and precision's no-information floor rises with it. "
            "Measured against that floor the whole fields are the better result "
            "({:.1f}x the floor against {:.1f}x). No external citation is attached to "
            "this: the reference this repository cites for cropped evaluation, "
            "docs/CLAIMS.md R5, is cited there for the tolerance effect and not for "
            "this one, and the factor above is measured here.".format(
                wf["loo"]["precision"], cr["loo"]["precision"],
                cr["loo"]["precision"] / wf["loo"]["precision"],
                cr["loo"]["recall"] / wf["loo"]["recall"],
                100 * wf["prevalence"], 100 * cr["prevalence"],
                cr["prevalence"] / wf["prevalence"],
                wf["loo"]["precision"] / wf["controls"]["mark_everything"]["precision"],
                cr["loo"]["precision"] / cr["controls"]["mark_everything"]["precision"]),
        "why no bracket is drawn on these panels":
            "on a collection whose masks adjudicate every pixel, precision is a point "
            "estimate against that annotation. On THIS LABORATORY's own SEM frames it is "
            "not: only part of each frame was ever refereed, the great majority of the "
            "pixels counted as false positives have no human verdict either way, and the "
            "defensible statement is the bracket [0.29, 0.99] recorded in "
            "docs/DATASET_RELEASE_SCOPE.md. That corpus also measures recall and "
            "precision on different frame sets and never pools them into an F1 "
            "(docs/figures/lab_madk_sweep.json). None of it can be placed on these axes, "
            "so none of it is drawn, and no number here should be read as applying to it.",
        "deliberately absent": "balanced accuracy and MCC, excluded at the author's "
                               "direction. IoU is recorded above but not drawn: within "
                               "one image it is an exact monotone transform of F1, "
                               "IoU = F1 / (2 - F1), so a bar of it would repeat the F1 "
                               "bar's ordering (the two means differ a little because "
                               "each is averaged over images). EBC_crack is a ceramic "
                               "withdrawn from the paper; DeepCrack and CrackForest are "
                               "road surfaces.",
        "source": ["docs/figures/sem_originals_metrics.json",
                   "docs/figures/sem_public_metrics.json",
                   "docs/figures/pixel_accounting.json (cross-check only)"],
    }, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)


if __name__ == "__main__":
    plate()
    print("plate in", OUT)
