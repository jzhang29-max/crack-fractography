#!/usr/bin/env python3
"""The TXM counterparts of the SEM plates, from measured JSON and none of them hand-drawn.

Section 4 had three figures where Section 3 has five, and two of the three were about the
TXM collection's OWN detector. The SEM detector carried across had one plate, which showed
two frames and two bars. The things the SEM arm gets -- the operating curve over its one
free constant, the pixel budget, the no-information arms it has to beat, and the overlap
measures with the ceiling they are read against -- it did not get on TXM. These are those.

Sources, each written by a measuring script and never edited by hand:
    docs/figures/txm_background_units.json   the sweep, the arms and the budget, by group
    docs/figures/txm_per_frame.json          the same per frame, so one frame cannot carry
                                             a group
    docs/figures/overlap_means_sem_txm.json  precision/recall/F1 per frame, with the score
                                             a correct 3 px trace of the same paint earns

Run with an interpreter that has matplotlib:
    python3 -B paper/figures/mk_txm_plates.py
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths                                   # noqa: E402
import journal_style as J          # noqa: E402

J.use()

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

#: One hue per claim, never per rank. The two specimen series the paper reports on are
#: separated by MARKER as well as by colour, so nothing here depends on colour alone.
GCOL = {"B3": J.ACCENT, "B2": J.ACCENT2}
GMRK = {"B3": "o", "B2": "s"}
K6 = "SEM detector, mad_k=6"


def load(name, what, scope=True):
    """Read a measurement file, by default the b2/b3 record rather than the full corpus.

    `_paths.scoped` raises if the restricted record is missing instead of falling back,
    because a plate that silently drew the wider corpus would carry a caption naming the
    narrower one and nothing in the output would show it.
    """
    try:
        p = _paths.scoped(name, scope=scope)
    except SystemExit:
        raise
    if not os.path.exists(p):
        raise SystemExit(f"missing {what}: {p} -- run its measuring script first")
    return json.load(open(p))


BG = load("txm_background_units.json", "TXM background units")

#: Driven by the measurement file, not hard-coded: when the corpus is restricted the
#: plates follow without an edit here, and a group still in the data cannot be dropped
#: from a plate by forgetting to list it.
GROUPS = [g for g in ("B3", "B2", "Wrought", "AM/HC") if g in BG["by_group"]]
_unlisted = sorted(set(BG["by_group"]) - set(GROUPS))
if _unlisted:
    raise SystemExit(f"groups {_unlisted} are in the measurement file and not in GROUPS")
GRID = BG["grid"]


# ------------------------------------------------- plate: the operating curve, on TXM
def plate_curve():
    """What the detector's one free constant does on TXM, in both reported units.

    The SEM operating curve (Figure 5) shows that the shipped constant sat at the edge of
    its own grid and that the area ratio was still falling when the grid ran out. The same
    sweep on TXM answers a different question: whether ANY value of the constant makes the
    carried-over detector worth more than marking nothing. Panel (b) is drawn through
    zero for that reason -- zero is the all-background prediction, and a curve that never
    crosses it has no operating point.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(J.PAGEW, 2.7), layout="constrained")
    for g in GROUPS:
        a = BG["by_group"][g]["arms"]
        ax1.plot(GRID, [a[f"SEM detector, mad_k={k:g}"]["area_agreement"] for k in GRID],
                 marker=GMRK[g], color=GCOL[g], markersize=3.6, label=g, clip_on=False)
        ax2.plot(GRID, [a[f"SEM detector, mad_k={k:g}"]["margin_pp"] for k in GRID],
                 marker=GMRK[g], color=GCOL[g], markersize=3.6, label=g, clip_on=False)
    pa = BG["pooled"]
    ax1.plot(GRID, [pa[f"SEM detector, mad_k={k:g}"]["area_agreement"] for k in GRID],
             color=J.INK, lw=1.6, linestyle=(0, (4, 1.6)), label="pooled")
    ax2.plot(GRID, [pa[f"SEM detector, mad_k={k:g}"]["margin_pp"] for k in GRID],
             color=J.INK, lw=1.6, linestyle=(0, (4, 1.6)), label="pooled")

    ax1.axhline(1.0, color=J.INK, lw=0.9, zorder=1)
    ax1.set_yscale("log")
    # plain numbers on the log axis: matplotlib's default renders these as "6 x 10^0",
    # which is a scientific-notation form for values between 1 and 7 and reads as noise
    ax1.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax1.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax1.set_yticks([1, 2, 3, 4, 6])
    ax1.set_xlabel("MAD multiplier $k$")
    ax1.set_ylabel("Reported / annotated crack area")
    ax1.set_xticks(GRID)
    ax1.legend(loc="upper right", ncol=1, handlelength=1.7, borderpad=0.0,
               labelspacing=0.25)
    J.panel_label(ax1, "a")

    ax2.axhline(0.0, color=J.INK, lw=0.9, zorder=1)
    ax2.set_xlabel("MAD multiplier $k$")
    ax2.set_ylabel("Pixel accuracy relative to an\nall-background mask (points)")
    ax2.set_xticks(GRID)
    J.panel_label(ax2, "b")

    J.save(fig, os.path.join(OUT, "T3 - TXM operating curve.png"))
    json.dump({"what": "the SEM detector's one free constant swept on TXM: (a) reported "
                       "over annotated crack area, logarithmic, unity marked; (b) pixel "
                       "accuracy minus the accuracy of an all-background mask, over "
                       "refereed pixels only",
               "why": "the SEM sweep asks where the area ratio crosses unity; this one "
                      "asks whether any value of the constant beats marking nothing",
               "grid": GRID,
               "values": {g: {str(k): BG["by_group"][g]["arms"]
                              [f"SEM detector, mad_k={k:g}"] for k in GRID}
                          for g in GROUPS},
               "pooled": {str(k): pa[f"SEM detector, mad_k={k:g}"] for k in GRID},
               "source": "docs/figures/txm_background_units.json"},
              open(os.path.join(OUT, "T3 - TXM operating curve.caption.json"), "w"),
              indent=1)


# ------------------------------------------- plate: the pixel budget and the two arms
def plate_budget():
    """Where every refereed pixel goes, and what the two no-information arms score.

    The SEM pixel budget (Figure P5) is drawn as a percentage of ALL image pixels. Here
    the denominator is the REFEREED area, because on TXM only part of each frame carries a
    human verdict and a percentage of the frame would be a percentage of a number nobody
    measured. The annotated crack fraction is drawn as an outline on each bar so the
    marked area can be read against the area that was there to find.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(J.PAGEW, 2.7), layout="constrained",
                                   gridspec_kw={"width_ratios": [1.25, 1.0]})
    y = np.arange(len(GROUPS))[::-1]
    tp = [BG["by_group"][g]["arms"][K6]["tp_pct"] for g in GROUPS]
    fp = [BG["by_group"][g]["arms"][K6]["fp_pct"] for g in GROUPS]
    fn = [BG["by_group"][g]["arms"][K6]["fn_pct"] for g in GROUPS]
    lab = [t + f for t, f in zip(tp, fn)]

    ax1.barh(y, tp, 0.5, color=J.ACCENT, edgecolor=J.INK, linewidth=0.5, zorder=3,
             label="marked, annotated crack")
    ax1.barh(y, fp, 0.5, left=tp, color=J.ACCENT2, edgecolor=J.INK, linewidth=0.5,
             zorder=3, label="marked, annotated not-crack")
    ax1.barh(y + 0.0, lab, 0.78, facecolor="none", edgecolor=J.INK, linewidth=0.9,
             linestyle=(0, (2.5, 1.2)), zorder=4, label="annotated crack")
    ax1.set_yticks(y, GROUPS)
    ax1.set_xlabel("Percentage of refereed area")
    ax1.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=1, handlelength=1.4,
               borderpad=0.0, handletextpad=0.5, labelspacing=0.25)
    J.panel_label(ax1, "a")

    arms = [(K6, "SEM detector"), ("control: Otsu, no model", "Otsu, no model"),
            ("control: mark everything", "mark everything")]
    ya = np.arange(len(arms))[::-1]
    marg = [BG["pooled"][a]["margin_pp"] for a, _ in arms]
    ax2.barh(ya, marg, 0.5, color=[J.ACCENT, J.G_MID, J.G_LIGHT], edgecolor=J.INK,
             linewidth=0.5, zorder=3)
    ax2.axvline(0.0, color=J.INK, lw=0.9, zorder=4)
    ax2.set_yticks(ya, [n for _, n in arms])
    ax2.set_xlabel("Pixel accuracy relative to an\nall-background mask (points)")
    J.panel_label(ax2, "b")

    J.save(fig, os.path.join(OUT, "T4 - TXM pixel budget.png"))
    json.dump({"what": "(a) the carried-over SEM detector's marked area on TXM split "
                       "into the part that agrees with the annotation and the part that "
                       "does not, with the annotated crack area as a dashed outline, all "
                       "as a percentage of the REFEREED area; (b) the same detector and "
                       "the two no-information arms, pooled, as pixel accuracy minus the "
                       "accuracy an all-background mask reaches",
               "denominator": "refereed pixels only (1 = crack, 2 or 3 = not-crack); "
                              "0 is unreviewed and is excluded at both ends",
               "values": {g: BG["by_group"][g]["arms"][K6] for g in GROUPS},
               "arms_pooled": {a: BG["pooled"][a] for a, _ in arms},
               "source": "docs/figures/txm_background_units.json"},
              open(os.path.join(OUT, "T4 - TXM pixel budget.caption.json"), "w"), indent=1)


# -------------------------------------- plate: the overlap measures, with their ceiling
def plate_overlap():
    """Precision, recall and F1 on both collections, each beside its own brush ceiling.

    THE CEILING IS THE POINT. Both collections are painted with a stroke far wider than
    the feature, so an overlap score against that stroke pays for covering the stroke. The
    reference drawn on every bar is what the frame's OWN paint, skeletonised and redrawn
    three pixels wide, scores against itself: a detector exactly right about where the
    crack runs and right about its width. Where the measured bar stands above that
    reference, the mask resembles the brush more closely than a correct trace would.
    """
    OV = load("overlap_means_sem_txm.json", "per-frame overlap means")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(J.PAGEW, 3.05), layout="constrained",
                                   gridspec_kw={"width_ratios": [1.0, 1.15]})
    meas = ["precision", "recall", "f1"]
    names = ["Precision", "Recall", "F1"]
    x = np.arange(len(meas))
    w = 0.36
    for i, (coll, col) in enumerate((("SEM", J.ACCENT), ("TXM", J.ACCENT2))):
        d = OV[coll]
        v = [d[f"mean_{m}"] for m in meas]
        e = [d[f"sd_{m}"] for m in meas]
        ax1.bar(x + (i - 0.5) * w, v, w, color=col, edgecolor=J.INK, linewidth=0.5,
                zorder=3, label=f"{coll}  (n = {d['n_frames']})")
        ax1.errorbar(x + (i - 0.5) * w, v, yerr=e, fmt="none", ecolor=J.INK,
                     elinewidth=0.8, capsize=2.2, zorder=5)
        c = [d[f"ceiling_mean_{m}"] for m in meas]
        for xi, ci in zip(x + (i - 0.5) * w, c):
            ax1.plot([xi - w / 2, xi + w / 2], [ci, ci], color=J.INK, lw=1.5, zorder=6,
                     solid_capstyle="butt")
        # THE OTHER END OF THE PRECISION BRACKET. Neither collection adjudicates the whole
        # frame, so the bar assumes every marked pixel nobody looked at is correct. The
        # open marker is the value when every one of them is counted wrong. Recall is
        # unaffected -- it needs no verdict outside the painted crack -- so only precision
        # and F1 carry one.
        lo = [d["mean_precision_if_unrefereed_wrong"], None,
              d["mean_f1_if_unrefereed_wrong"]]
        for xi, li in zip(x + (i - 0.5) * w, lo):
            if li is None:
                continue
            ax1.plot([xi], [li], marker="v", markersize=5.5, markerfacecolor="white",
                     markeredgecolor=J.INK, markeredgewidth=0.9, zorder=7,
                     linestyle="none")
    ax1.set_xticks(x, names)
    ax1.set_ylabel("Mean over frames")
    # 1.05, not 1.0: the 3 px-trace rule sits at precision 0.998 on both collections and
    # a top of exactly 1.0 draws it under the spine, where it cannot be read
    ax1.set_ylim(0, 1.05)
    # the rule needs a key of its own or it is an unexplained mark on every bar
    h, lb = ax1.get_legend_handles_labels()
    h.append(matplotlib.lines.Line2D([], [], color=J.INK, lw=1.5))
    lb.append("correct 3 px trace of the same paint")
    h.append(matplotlib.lines.Line2D([], [], color=J.INK, lw=0, marker="v",
                                     markerfacecolor="white", markeredgecolor=J.INK,
                                     markeredgewidth=0.9, markersize=5.5))
    lb.append("every unreviewed marked pixel counted wrong")
    # 1.13, not 1.01: with four entries the key is two rows deep and its lower row ran
    # through the (a) that J.panel_label puts at 1.04
    ax1.legend(h, lb, loc="lower center", bbox_to_anchor=(0.5, 1.13), ncol=2,
               handlelength=1.3, borderpad=0.0, columnspacing=1.2, handletextpad=0.5,
               labelspacing=0.2)
    J.panel_label(ax1, "a")

    for coll, col, mk in (("SEM", J.ACCENT, "o"), ("TXM", J.ACCENT2, "s")):
        rows = OV[coll]["per_frame"]
        ax2.plot([r["recall"] for r in rows], [r["precision"] for r in rows],
                 linestyle="none", marker=mk, markersize=4.2, markerfacecolor=col,
                 markeredgecolor=J.INK, markeredgewidth=0.4, label=coll, clip_on=False)
    for f1 in (0.2, 0.4, 0.6, 0.8):
        r = np.linspace(f1 / (2 - f1) + 1e-4, 1.0, 200)
        ax2.plot(r, f1 * r / (2 * r - f1), color=J.G_LIGHT, lw=0.7, zorder=1)
        ax2.annotate(f"F1 {f1:.1f}", (1.0, f1 / (2 - f1)), fontsize=J.TICK,
                     color=J.G_MID, va="bottom", ha="right", xytext=(0, 1.5),
                     textcoords="offset points")
    ax2.set_xlim(0, 1.0)
    ax2.set_ylim(0, 1.0)
    ax2.set_xlabel("Recall")
    ax2.set_ylabel("Precision")
    ax2.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2, handlelength=1.0,
               borderpad=0.0, columnspacing=1.2, handletextpad=0.4)
    J.panel_label(ax2, "b")

    J.save(fig, os.path.join(OUT, "T5 - overlap with its ceiling.png"))
    json.dump({"what": "(a) mean precision, recall and F1 over frames for this "
                       "laboratory's SEM frames and for the TXM collection, the error "
                       "bar one standard deviation over frames, the horizontal rule on "
                       "each bar the score a geometrically correct 3 px trace of that "
                       "collection's own paint earns against that same paint; (b) every "
                       "frame as one point, precision against recall, with iso-F1 curves",
               "aggregation": "mean over frames, one vote per frame; pixels are NOT "
                              "pooled, because one frame otherwise carries the number",
               "precision_bracket": "the bar assumes every marked pixel outside the "
                                    "reviewed area is correct; the open triangle assumes "
                                    "every one of them is wrong. Recall carries no "
                                    "bracket because it needs no verdict outside the "
                                    "painted crack.",
               "scoring": OV["scoring"], "ceiling": OV["ceiling"], "mad_k": OV["mad_k"],
               "values": {c: {k: v for k, v in OV[c].items() if k != "per_frame"}
                          for c in ("SEM", "TXM")},
               "source": "docs/figures/overlap_means_sem_txm.json"},
              open(os.path.join(OUT, "T5 - overlap with its ceiling.caption.json"), "w"),
              indent=1)


if __name__ == "__main__":
    plate_curve()
    plate_budget()
    if os.path.exists(os.path.join(REPO, "docs/figures/overlap_means_sem_txm.json")):
        plate_overlap()
    else:
        print("skipping T5: overlap_means_sem_txm.json not written yet")
    print("\nplates in", OUT)
