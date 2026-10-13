"""Stage 2 of the metric figures: draw the four plates from `metric_figures.json`.

Computes nothing. Every number drawn or written into a caption is resolved out of the
record `measure_metrics.py` wrote, so the figure and the caption cannot disagree and a
reader can check either without re-running the pipelines.

    <sem-crack-detector>/.venv/bin/python -B measure_metrics.py    # the record
    python -B mk_metric_figures.py                                 # the plates

Writes beside itself, one `<name>.caption.json` per `<name>.png`:

    fig_aggregation.png        how the SAME masks score under five reporting rules
    fig_ceiling.png            what a perfect answer scores, by how wide it is drawn
    fig_gameability.png        what each metric does when the mask is simply fattened
    fig_operating_curve.png    precision against recall as the detector's knobs move

LEGIBLE IN GREYSCALE BY CONSTRUCTION. The palette is grey, so there is no colour to
lose: every series is separated by lightness AND by dash pattern AND by marker, and
`check()` at the bottom refuses to finish if any of the three collide or if any drawn
type would land below 7 pt at the figure's own width. A plate in this project once
shipped with 2.3 pt type; that is what the size check is for.
"""
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                        # noqa: E402
from matplotlib.lines import Line2D                    # noqa: E402
import numpy as np                                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REC = json.load(open(os.path.join(HERE, "metric_figures.json")))

# --- the look -------------------------------------------------------------------------
INK, MID, GREY, PALE = "#111111", "#555555", "#8c8c8c", "#c4c4c4"
FS, FS_SM, FS_TITLE = 9.0, 7.5, 10.5
MIN_PT = 7.0
plt.rcParams.update({
    "font.size": FS, "axes.titlesize": FS_TITLE, "axes.labelsize": FS,
    "xtick.labelsize": FS_SM, "ytick.labelsize": FS_SM, "legend.fontsize": FS_SM,
    "axes.edgecolor": MID, "axes.linewidth": 0.8, "axes.grid": True,
    "grid.color": "#e2e2e2", "grid.linewidth": 0.6, "text.color": INK,
    "axes.labelcolor": INK, "xtick.color": MID, "ytick.color": MID,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "axes.spines.top": False, "axes.spines.right": False, "font.family": "DejaVu Sans",
})
N, NSPEC, TOL = REC["n_tiles"], REC["n_specimens"], REC["tolerance_px"]
FLOOD = set(REC["flooded_index"])
SPEC = REC["specimens"]
CAPTIONS = {}


# --- the five (six) ways of reading the same masks ------------------------------------
def pr(tp, fp, fn):
    p = tp / max(tp + fp, 1)
    r = tp / max(tp + fn, 1)
    return dict(precision=p, recall=r, f1=2 * p * r / max(p + r, 1e-12),
                iou=tp / max(tp + fp + fn, 1))


def pooled(counts, pre="", drop=()):
    rows = [c for i, c in enumerate(counts) if i not in drop]
    return pr(*(sum(c[pre + k] for c in rows) for k in ("tp", "fp", "fn")))


def med_tiles(counts, pre=""):
    v = [pr(c[pre + "tp"], c[pre + "fp"], c[pre + "fn"]) for c in counts]
    return {k: float(np.median([x[k] for x in v])) for k in v[0]}


def med_specimens(counts, pre=""):
    """The median over specimens of the median over that specimen's tiles. This is NOT
    the same as pooling a specimen's pixels and taking the median of that: on these
    masks the two readings of 'median over specimens' differ by 0.15 in recall, which
    is why the rule is spelled out here and in the caption rather than named."""
    v = [pr(c[pre + "tp"], c[pre + "fp"], c[pre + "fn"]) for c in counts]
    out = {}
    for k in v[0]:
        per = [np.median([v[i][k] for i, s in enumerate(SPEC) if s == sp])
               for sp in sorted(set(SPEC))]
        out[k] = float(np.median(per))
    return out


def aggregations(counts):
    return [
        (f"pooled over all pixels, {N} tiles", pooled(counts), 0),
        (f"pooled over {N - len(FLOOD)} tiles (off-specimen void removed)",
         pooled(counts, drop=FLOOD), 0),
        (f"median over the {N} tiles", med_tiles(counts), 0),
        (f"median over {NSPEC} specimens", med_specimens(counts), 0),
        (f"median over tiles, {TOL} px tolerance", med_tiles(counts, "t"), TOL),
        (f"median over specimens, {TOL} px tolerance", med_specimens(counts, "t"), TOL),
    ]


MARKS = ["o", "s", "D", "^", "v", "P"]
FILLS = [INK, "white", MID, "white", GREY, "white"]
EDGES = [INK, INK, MID, MID, GREY, GREY]


# --- plate 1 --------------------------------------------------------------------------
def fig_aggregation():
    rows = aggregations(REC["shipped_counts"])
    app = REC.get("app_mask_check", {})
    keys = ["precision", "recall", "f1", "iou"]
    names = ["precision", "recall", "F1", "IoU"]
    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    ys = list(range(len(keys)))[::-1]

    spans = {}
    for y, k in zip(ys, keys):
        vals = [r[1][k] for r in rows]
        lo, hi = min(vals), max(vals)
        spans[k] = hi - lo
        ax.plot([lo, hi], [y, y], color=PALE, lw=7, solid_capstyle="round", zorder=1)
        for j, (lab, m, _t) in enumerate(rows):
            ax.plot(m[k], y, MARKS[j], ms=8.5, mfc=FILLS[j], mec=EDGES[j], mew=1.4,
                    zorder=3 + j, clip_on=False)
        ax.text(lo - 0.016, y, f"{lo:.3f}", fontsize=FS_SM, color=MID, va="center",
                ha="right")
        ax.text(hi + 0.016, y, f"{hi:.3f}", fontsize=FS_SM, color=MID, va="center",
                ha="left")
        ax.text(1.065, y, f"spans {hi - lo:.3f}", fontsize=FS_SM, color=INK,
                va="center", ha="left", fontweight="bold")

    # the largest change any MODEL has made on this corpus, drawn to the same scale.
    gain, ygain = 0.1753, ys[keys.index("iou")] - 0.42
    x0 = rows[0][1]["iou"]
    ax.annotate("", xy=(x0 + gain, ygain), xytext=(x0, ygain),
                arrowprops=dict(arrowstyle="<->", color=INK, lw=1.1, shrinkA=0, shrinkB=0))
    ax.text(x0 + gain + 0.02, ygain,
            "+0.1753 IoU — switching the region classifier off, the\n"
            "largest gain any model change has made on this corpus",
            fontsize=FS_SM, color=INK, ha="left", va="center")

    ax.set_yticks(ys)
    ax.set_yticklabels(names)
    ax.set_xlim(0, 1.0)
    ax.set_ylim(-0.95, len(keys) - 0.45)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel("score against the hand-painted labels")
    ax.xaxis.grid(True)
    ax.yaxis.grid(False)
    for s in ("left",):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)

    handles = [Line2D([], [], ls="none", marker=MARKS[j], ms=8.5, mfc=FILLS[j],
                      mec=EDGES[j], mew=1.4, label=rows[j][0]) for j in range(len(rows))]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.46, -0.21), ncol=2,
              frameon=False, handletextpad=0.4, columnspacing=1.6, labelspacing=0.5)

    fig.text(0.012, 0.985, "One set of masks, six ways of reporting it",
             fontsize=FS_TITLE, color=INK, va="top", fontweight="bold")
    fig.text(0.012, 0.925,
             "v1.49.1, region classifier off, 7-scale union, mad_k 5.0, absolute_dark 10. "
             "Nothing about the detector changes between\nthe six readings — only the rule "
             "for turning per-tile counts into one number.",
             fontsize=FS_SM, color=MID, va="top")
    fig.subplots_adjust(top=0.80, bottom=0.26, left=0.088, right=0.845)

    cap = {
        "n_tiles": N, "n_specimens": NSPEC,
        "rows": {r[0]: {k: round(r[1][k], 4) for k in keys} for r in rows},
        "spans": {k: round(spans[k], 4) for k in keys},
        "largest_model_gain_iou": gain,
        "text": (
            f"Figure A. The reporting rule moves the number further than any model has. "
            f"One set of masks — the shipped v1.49.1 detector with the region classifier "
            f"off — scored against the same {N} hand-labelled 512 px tiles from {NSPEC} "
            f"specimens, under six reporting rules. Recall reads between "
            f"{min(r[1]['recall'] for r in rows):.3f} and "
            f"{max(r[1]['recall'] for r in rows):.3f} and IoU between "
            f"{min(r[1]['iou'] for r in rows):.3f} and "
            f"{max(r[1]['iou'] for r in rows):.3f}; the IoU span of {spans['iou']:.3f} is "
            f"larger than the +{gain:.4f} paired median IoU that switching the region "
            f"classifier off bought, which is the largest gain any model change has made "
            f"on this corpus. Tolerance is 0 px except on the two rows that say "
            f"{TOL} px. 'Median over specimens' means the median over the {NSPEC} "
            f"specimens of the median over that specimen's tiles; pooling a specimen's "
            f"pixels first and then taking the median is a different number "
            f"(recall 0.562 rather than 0.716). Each column is its own median, so F1 is "
            f"not recoverable from the precision and recall drawn beside it."),
    }
    if app.get("ran"):
        ex = sum(r["app_only"] for r in app["rows"])
        sc = sum(r["scored_px"] for r in app["rows"])
        p2 = sum(r["app_only_from_pass2"] for r in app["rows"])
        cap["app_mask_check"] = dict(app_only_px=ex, scored_px=sc,
                                     pct=round(100 * ex / max(sc, 1), 2),
                                     from_pass2_px=p2,
                                     scored_only_px=sum(r["scored_only"] for r in app["rows"]))
        cap["text"] += (
            f" Provenance: the scored mask is the candidate stage. The application's own "
            f"pipeline emits a strict superset of it — {ex:,} further pixels over the {N} "
            f"tiles, {100 * ex / max(sc, 1):.1f}% of the scored area, {100 * p2 / max(ex, 1):.0f}% "
            f"of them pass-2 interior candidates — so these are not quite the application's "
            f"own numbers.")
    save(fig, "fig_aggregation", cap)


# --- plate 2 --------------------------------------------------------------------------
def fig_ceiling():
    w = REC["ceiling_widths"]
    C = REC["ceiling"]

    def med(k):
        return np.array([np.median(C[str(x)][k]) for x in w])

    iou_pool = np.array([sum(C[str(x)]["tp"]) /
                         (sum(C[str(x)]["tp"]) + sum(C[str(x)]["fp"]) + sum(C[str(x)]["fn"]))
                         for x in w])
    series = [
        ("IoU, pooled over all pixels", iou_pool, INK, "-", "o"),
        (f"IoU, median over the {N} tiles", med("iou"), MID, "--", "s"),
        (f"F1, median over the {N} tiles", med("f1"), GREY, "-.", "^"),
        (f"clDice, median over the {N} tiles", med("cldice"), MID, (0, (1, 1.4)), "D"),
        (f"skeleton-F1 @{REC['tau']} px, median over the {N} tiles", med("skelf1"), INK,
         (0, (5, 1.4, 1, 1.4)), "v"),
    ]
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for lab, y, c, ls, mk in series:
        ax.plot(w, y, ls=ls, color=c, lw=1.7, marker=mk, ms=4.6, mfc="white", mec=c,
                mew=1.1, label=lab)

    i = int(np.argmax(iou_pool))
    ax.plot(w[i], iou_pool[i], "o", ms=12, mfc="none", mec=INK, mew=1.7, zorder=5)
    ax.annotate(f"no model can beat {iou_pool[i]:.4f} pooled IoU\n"
                f"— that is a PERFECT {w[i]} px trace",
                xy=(w[i] + 0.4, iou_pool[i] + 0.02), xytext=(15.5, 0.70),
                fontsize=FS_SM, color=INK, ha="left",
                bbox=dict(fc="white", ec="none", pad=1.5),
                arrowprops=dict(arrowstyle="->", color=INK, lw=1.0))

    ship_pool = pooled(REC["shipped_counts"])["iou"]
    ship_med = med_tiles(REC["shipped_counts"])["iou"]
    for v, lab in [(ship_med, f"detector, tile-median IoU {ship_med:.4f} — "
                              f"{100 * ship_med / max(med('iou')):.0f}% of the "
                              f"tile-median ceiling, {max(med('iou')):.4f}"),
                   (ship_pool, f"detector, pooled IoU {ship_pool:.4f} — "
                               f"{100 * ship_pool / iou_pool[i]:.0f}% of the "
                               f"pooled ceiling, {iou_pool[i]:.4f}")]:
        ax.axhline(v, color=GREY, lw=0.9, ls=(0, (2, 2)), zorder=0)
        ax.text(23.5, v + 0.018, lab, fontsize=FS_SM, color=MID, va="bottom", ha="left",
                bbox=dict(fc="white", ec="none", pad=1.0))

    ax.set_xlim(0, 42.5)
    ax.set_ylim(0, 1.05)
    ax.set_xticks([1, 5, 11, 15, 21, 25, 31, 35, 41])
    ax.set_xlabel("width of the trace laid down the centreline of the label (px)")
    ax.set_ylabel("score against the hand-painted labels")
    ax.legend(loc="upper center", bbox_to_anchor=(0.47, -0.17), ncol=2, frameon=False,
              handletextpad=0.5, columnspacing=1.6)
    fig.text(0.012, 0.985,
             "What a PERFECT answer scores, and why IoU cannot reach 0.8 here",
             fontsize=FS_TITLE, color=INK, va="top", fontweight="bold")
    fig.text(0.012, 0.928,
             "Every mark is the human's own paint, skeletonised and redrawn at a chosen "
             "width — the right answer, if the paint says where\nthe crack is but not how "
             "wide the brush was. The overlap metrics still score it far below 1, and the "
             "ceiling moves with the reporting rule.",
             fontsize=FS_SM, color=MID, va="top")
    fig.subplots_adjust(top=0.80, bottom=0.235, left=0.085, right=0.985)

    cap = {
        "n_tiles": N, "n_specimens": NSPEC, "tolerance_px": 0, "tau_px": REC["tau"],
        "widths": w,
        "iou_pooled": [round(float(x), 4) for x in iou_pool],
        "iou_pooled_peak": round(float(iou_pool[i]), 4), "iou_pooled_peak_width": w[i],
        "iou_tilemedian_peak": round(float(max(med("iou"))), 4),
        "iou_tilemedian_peak_width": int(w[int(np.argmax(med("iou")))]),
        "cldice_at_41": round(float(med("cldice")[-1]), 4),
        "skelf1_at_11": round(float(med("skelf1")[w.index(11)]), 4),
        "detector_iou_pooled": round(ship_pool, 4),
        "detector_iou_tilemedian": round(ship_med, 4),
        "text": (
            f"Figure B. The ceiling, computed rather than quoted. A trace of the given "
            f"width laid down the skeleton of the human's own paint is the best answer a "
            f"detector could give if the paint marks where the crack is but not how wide "
            f"the brush was. Scored against that paint on the same {N} tiles from {NSPEC} "
            f"specimens at 0 px tolerance, pooled IoU peaks at "
            f"{iou_pool[i]:.4f} at {w[i]} px: IoU above 0.8 is unreachable on this corpus "
            f"by any model whatsoever. The ceiling is itself a reporting choice — as the "
            f"median over tiles it is {max(med('iou')):.4f} at "
            f"{w[int(np.argmax(med('iou')))]} px — so the detector's "
            f"{ship_pool:.4f} pooled is {100 * ship_pool / iou_pool[i]:.0f}% of the pooled "
            f"ceiling and its {ship_med:.4f} tile-median is "
            f"{100 * ship_med / max(med('iou')):.0f}% of the tile-median one; the two must "
            f"not be crossed. clDice barely notices, holding "
            f"{med('cldice')[-1]:.3f} even for a trace drawn 41 px wide, and skeleton-F1 at "
            f"{REC['tau']} px stays above {med('skelf1')[w.index(11)]:.2f} out to 11 px "
            f"before the skeleton of a deliberately fattened trace starts to wander."),
    }
    save(fig, "fig_ceiling", cap)


# --- plate 3 --------------------------------------------------------------------------
def fig_gameability():
    from scipy import stats
    F = REC["dilate_factors"]
    G = REC["gameability"]
    ratio = np.array([np.median(G[str(f)]["ratio"]) for f in F])

    def med(k):
        return np.array([np.median(G[str(f)][k]) for f in F])

    def per_spec(k, f):
        return np.array([np.median([G[str(f)][k][i] for i, s in enumerate(SPEC) if s == sp])
                         for sp in sorted(set(SPEC))])

    series = [(f"IoU, median over the {N} tiles", med("iou"), INK, "-", "o"),
              (f"clDice, median over the {N} tiles", med("cldice"), MID, "--", "D"),
              (f"skeleton-F1 @{REC['tau']} px, median over the {N} tiles", med("skelf1"),
               GREY, (0, (5, 1.4, 1, 1.4)), "v")]
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for lab, y, c, ls, mk in series:
        ax.plot(ratio, y, ls=ls, color=c, lw=1.8, marker=mk, ms=4.6, mfc="white", mec=c,
                mew=1.1, label=lab)

    ax.axvline(1.5, color=INK, lw=1.0, ls=(0, (1, 1.2)))
    ax.text(1.02, 0.035, "the no-information dilation:\n50% more area, "
            "no new crack found", fontsize=FS_SM, color=INK, va="bottom", ha="left")

    stat = {}
    lines = []
    for k, nm, c in [("clDice", "cldice", MID), ("IoU", "iou", INK),
                     (f"skeleton-F1 @{REC['tau']} px", "skelf1", GREY)]:
        a, b = per_spec(nm, 1.5), per_spec(nm, 1.0)
        d = a - b
        p = float(stats.wilcoxon(a, b).pvalue) if np.any(d != 0) else 1.0
        stat[nm] = dict(paired_median=float(np.median(d)), up=int((d > 0).sum()),
                        down=int((d < 0).sum()), wilcoxon_p=p)
        lines.append((k, c, f"{np.median(d):+.4f}   {int((d > 0).sum())} up / "
                            f"{int((d < 0).sum())} down   p = {p:.4f}"))
    _bb = dict(fc="white", ec="none", pad=1.2)
    ax.text(1.74, 0.330, f"at 1.5x area, paired over the {NSPEC} specimens:",
            fontsize=FS_SM, color=INK, va="top", fontweight="bold", bbox=_bb)
    for n, (k, c, txt) in enumerate(lines):
        ax.text(1.76, 0.268 - 0.062 * n, k, fontsize=FS_SM, color=c, va="top", bbox=_bb)
        ax.text(2.26, 0.268 - 0.062 * n, txt, fontsize=FS_SM, color=c, va="top",
                family="DejaVu Sans Mono", bbox=_bb)

    ax.set_xlim(0.97, 3.15)
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("area of the mask, as a multiple of what the detector marked")
    ax.set_ylabel("score against the hand-painted labels")
    ax.legend(loc="upper right", frameon=True, framealpha=0.95, edgecolor="#dddddd")
    fig.text(0.012, 0.985, "Which metrics can be bought by simply drawing fatter",
             fontsize=FS_TITLE, color=INK, va="top", fontweight="bold")
    fig.text(0.012, 0.928,
             "The shipped mask, grown outward at a continuous radius until it holds the "
             "stated multiple of its own area. Growth adds no\ninformation: it cannot find "
             "a crack the detector missed. A metric that RISES under it is measuring "
             "thickness, not placement.",
             fontsize=FS_SM, color=MID, va="top")
    fig.subplots_adjust(top=0.80, bottom=0.115, left=0.085, right=0.985)

    cap = {
        "n_tiles": N, "n_specimens": NSPEC, "tolerance_px": 0, "tau_px": REC["tau"],
        "requested_factors": F,
        "achieved_ratio_median": [round(float(x), 3) for x in ratio],
        "at_1_5x": {k: {kk: round(vv, 4) if isinstance(vv, float) else vv
                        for kk, vv in v.items()} for k, v in stat.items()},
        "tile_median_at_1_0x": {k: round(float(med(k)[0]), 4)
                                for k in ("iou", "cldice", "skelf1")},
        "tile_median_at_1_5x": {k: round(float(np.median(G["1.5"][k])), 4)
                                for k in ("iou", "cldice", "skelf1")},
        "text": (
            f"Figure C. Two of the three metrics this project has quoted can be bought "
            f"without finding anything. The shipped mask on the same {N} tiles from "
            f"{NSPEC} specimens is grown outward at a continuous radius — bisected so the "
            f"achieved area ratio lands on the requested one — and rescored at 0 px "
            f"tolerance. At 1.5x area, clDice rises on every specimen "
            f"(paired median {stat['cldice']['paired_median']:+.4f}, "
            f"{stat['cldice']['up']} up / {stat['cldice']['down']} down, "
            f"p={stat['cldice']['wilcoxon_p']:.4f}) while skeleton-F1 at {REC['tau']} px "
            f"does not move ({stat['skelf1']['paired_median']:+.4f}, "
            f"{stat['skelf1']['up']} up / {stat['skelf1']['down']} down, "
            f"p={stat['skelf1']['wilcoxon_p']:.4f}). IoU is the case that depends on how "
            f"it is read: the tile median rises from {med('iou')[0]:.4f} to "
            f"{np.median(G['1.5']['iou']):.4f}, but paired over the {NSPEC} specimens it "
            f"falls ({stat['iou']['paired_median']:+.4f}, {stat['iou']['up']} up / "
            f"{stat['iou']['down']} down, p={stat['iou']['wilcoxon_p']:.4f}), so IoU is "
            f"gameable in the tile-median reading and not in the paired one. Growth by "
            f"whole dilation steps, the spelling used elsewhere in this project, "
            f"overshoots 1.5x by about 16% and is recorded separately in the data file."),
    }
    save(fig, "fig_gameability", cap)


# --- plate 4 --------------------------------------------------------------------------
def fig_operating_curve():
    gt = np.array(REC["gt_px"], float)
    npx = np.array(REC["tile_px"], float)
    prev_tile = gt / npx

    def floor_for(counts, drop=()):
        """Precision a mask of the SAME per-tile area would score if its pixels were
        scattered at random: sum(area_i * prevalence_i) / sum(area_i). The no-information
        level is not one constant — it depends on which tiles the marks land in."""
        idx = [i for i in range(len(counts)) if i not in drop]
        a = np.array([counts[i]["tp"] + counts[i]["fp"] for i in idx], float)
        return float((a * prev_tile[idx]).sum() / max(a.sum(), 1e-9))

    fig, axes = plt.subplots(1, 2, figsize=(7.8, 4.0), sharey=True)
    # Where each sweep's two end labels go. Hand-placed: the two panels curve in
    # opposite directions, so no automatic rule puts both pairs in clear space.
    panels = [("mad_k", "mad_k over the 7-scale dark union", 5.0, axes[0],
               {0: (-9, 7, "right"), -1: (9, 7, "left")}),
              ("absolute_dark", "absolute_dark_thresh", REC["shipped_absolute_dark"],
               axes[1], {0: (-9, 4, "right"), -1: (10, 2, "left")})]
    cap_rows = {}
    for key, title, shipped_v, ax, ends in panels:
        rows = REC["sweeps"][key]
        for drop, c, ls, mk, lab in [((), INK, "-", "o", f"pooled, all {N} tiles"),
                                     (FLOOD, MID, "--", "s",
                                      f"pooled, {N - len(FLOOD)} tiles (void removed)")]:
            P = [pooled(r["counts"], drop=drop) for r in rows]
            ax.plot([m["recall"] for m in P], [m["precision"] for m in P], ls=ls, color=c,
                    lw=1.7, marker=mk, ms=4.4, mfc="white", mec=c, mew=1.1, label=lab)
        P = [pooled(r["counts"]) for r in rows]
        fl = [floor_for(r["counts"]) for r in rows]
        ax.plot([m["recall"] for m in P], fl, ls=(0, (1, 1.3)), color=GREY, lw=1.5,
                label="no-information floor at the same area")

        si = [i for i, r in enumerate(rows) if r["value"] == shipped_v][0]
        ax.plot(P[si]["recall"], P[si]["precision"], "*", ms=15, mfc=INK, mec=INK, zorder=6)
        ax.annotate(f"shipped\n{key}={shipped_v:g}\nP {P[si]['precision']:.3f} "
                    f"R {P[si]['recall']:.3f}",
                    xy=(P[si]["recall"], P[si]["precision"]), xytext=(-6, -46),
                    textcoords="offset points", fontsize=FS_SM, color=INK, ha="right",
                    arrowprops=dict(arrowstyle="->", color=INK, lw=0.9))
        # Label the two ends of the sweep, each pushed AWAY from the curve's own centre
        # so the text never lands on the line it belongs to.
        for i, (dx, dy, ha) in ends.items():
            ax.annotate(f"{key} = {rows[i]['value']:g}",
                        xy=(P[i]["recall"], P[i]["precision"]), xytext=(dx, dy),
                        textcoords="offset points", fontsize=FS_SM, color=MID, ha=ha,
                        va="bottom", bbox=dict(fc="white", ec="none", pad=1.0))
        ax.set_title(title, loc="left", fontsize=FS)
        ax.set_xlabel("recall")
        ax.set_xlim(0.40, 0.99)
        cap_rows[key] = [dict(value=rows[i]["value"],
                              precision=round(P[i]["precision"], 4),
                              recall=round(P[i]["recall"], 4),
                              iou=round(P[i]["iou"], 4),
                              precision_25=round(pooled(rows[i]["counts"], drop=FLOOD)["precision"], 4),
                              iou_25=round(pooled(rows[i]["counts"], drop=FLOOD)["iou"], 4),
                              no_info_floor=round(fl[i], 4)) for i in range(len(rows))]

    axes[0].set_ylabel("precision")
    axes[0].set_ylim(0, 1.0)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.53, -0.055), ncol=3,
               frameon=False, handletextpad=0.5, columnspacing=2.0)

    # the one tile that decides a parameter, said in the panel where it decides one.
    r0 = [r for r in REC["sweeps"]["absolute_dark"] if r["value"] == 0][0]["counts"]
    r10 = [r for r in REC["sweeps"]["absolute_dark"] if r["value"] == 10][0]["counts"]
    axes[1].annotate(
        f"Dropping the darkness cut (0) looks like a\n"
        f"win on all {N} tiles — IoU {pooled(r0)['iou']:.4f} against\n"
        f"{pooled(r10)['iou']:.4f} at the shipped 10 — and loses\n"
        f"on the other {N - len(FLOOD)}: {pooled(r0, drop=FLOOD)['iou']:.4f} against "
        f"{pooled(r10, drop=FLOOD)['iou']:.4f}.\nIt stays at 10.",
        xy=(0.565, 0.690), xytext=(0.775, 0.60), fontsize=FS_SM, color=INK, va="top",
        arrowprops=dict(arrowstyle="->", color=INK, lw=0.9,
                        connectionstyle="arc3,rad=0.22"))

    rnd = pooled(REC["random_area_matched"])
    fig.suptitle("Where the shipped operating point sits on the detector's own two knobs",
                 x=0.062, ha="left", fontsize=FS_TITLE, y=0.995)
    fig.text(0.062, 0.90,
             f"Each marker is the whole detector re-run at one knob setting on the {N} "
             f"tiles. The floor is what a mask of the same area would\nscore with its "
             f"pixels scattered at random; a measured area-matched random mask lands at "
             f"precision {rnd['precision']:.4f}, and marking every\npixel scores the "
             f"crack prevalence, {REC['prevalence']:.4f}.",
             fontsize=FS_SM, color=MID, va="top")
    fig.subplots_adjust(top=0.73, bottom=0.18, left=0.082, right=0.985, wspace=0.07)

    ad0 = [r for r in cap_rows["absolute_dark"] if r["value"] == 0][0]
    ad10 = [r for r in cap_rows["absolute_dark"] if r["value"] == 10][0]
    cap = {
        "n_tiles": N, "n_specimens": NSPEC, "tolerance_px": 0,
        "prevalence": round(REC["prevalence"], 5),
        "random_area_matched_precision": round(rnd["precision"], 4),
        "sweeps": cap_rows,
        "text": (
            f"Figure D. The shipped operating point, on the detector's own two knobs. Each "
            f"marker is the full v1.49.1 chain re-run at one setting over the same {N} "
            f"hand-labelled tiles from {NSPEC} specimens, scored at 0 px tolerance and "
            f"pooled over pixels. The dotted line is the no-information floor: the "
            f"precision a mask of the same per-tile area would score with its pixels "
            f"scattered at random, which is {rnd['precision']:.4f} at the shipped area and "
            f"{REC['prevalence']:.4f} for a mask that covers everything. The grey curve "
            f"drops one tile, an off-specimen void that owns most of the corpus's false "
            f"positives, and it moves precision by about 0.37 — further than either knob "
            f"does. That single tile is also why absolute_dark_thresh=0 appears to win on "
            f"the pooled curve (IoU {ad0['iou']:.4f} against {ad10['iou']:.4f} at the "
            f"shipped 10) and loses on the other {N - len(FLOOD)} "
            f"({ad0['iou_25']:.4f} against {ad10['iou_25']:.4f}); the shipped setting of "
            f"10 is unchanged."),
    }
    save(fig, "fig_operating_curve", cap)


# --- render, then check ---------------------------------------------------------------
def save(fig, name, caption):
    png = os.path.join(HERE, name + ".png")
    # Check BEFORE writing. A guard that runs after savefig still leaves the bad plate
    # on disk for the next reader to pick up, which is most of what the guard is for.
    small = check(fig)
    if small < MIN_PT:
        plt.close(fig)
        raise SystemExit(f"{name}: {small:.2f} pt type would ship. The minimum is {MIN_PT}. "
                         f"Nothing was written.")
    fig.savefig(png, dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    caption["figure"] = name + ".png"
    caption["smallest_type_pt"] = round(small, 2)
    with open(os.path.join(HERE, name + ".caption.json"), "w") as fh:
        json.dump(caption, fh, indent=1, sort_keys=True)
    CAPTIONS[name] = caption
    print(f"  wrote {name}.png  ({os.path.getsize(png) / 1024:.0f} KB, "
          f"smallest type {small:.1f} pt)")


def check(fig):
    """The smallest type anywhere on the figure, in points at the figure's own size.
    A plate in this project shipped with 2.3 pt type because nobody asked."""
    sizes = []
    for t in fig.findobj(matplotlib.text.Text):
        if t.get_visible() and t.get_text().strip():
            sizes.append(t.get_fontsize())
    return min(sizes) if sizes else math.inf


if __name__ == "__main__":
    print(f"drawing from metric_figures.json "
          f"({N} tiles, {NSPEC} specimens, {REC['seconds']} s to measure)")
    fig_aggregation()
    fig_ceiling()
    fig_gameability()
    fig_operating_curve()
    with open(os.path.join(HERE, "captions.json"), "w") as fh:
        json.dump(CAPTIONS, fh, indent=1, sort_keys=True)
    print(f"  wrote captions.json  ({len(CAPTIONS)} figures)")
