#!/usr/bin/env python3
"""Figure: what correcting the model by hand actually buys, round by round.

THE OBVIOUS VERSION OF THIS FIGURE IS CIRCULAR AND IS NOT WHAT IS DRAWN. "Correct the
mask, re-run, and see that it matches the correction better" scores a mask that has the
human's answer pasted into it AGAINST the human's answer. It can only go up, it would go
up by construction, and it would measure nothing about the model.

WHAT IS DRAWN INSTEAD is the deployment record: each time the owner's corrections grew,
a new model was fitted and scored by FIVE-FOLD CROSS-VALIDATION GROUPED BY IMAGE, so no
frame the model was fitted on appears in its own score. That is a real held-out number
and it is the one the deployment gate reads.

WHAT IS NOT ON THIS AXIS, AND WHY. Three of the seven recorded rounds cannot be put
beside the rest:

  2026-08-18 reports IoU 0.936 and is IN SAMPLE -- the record says it was fitted on the
  reference frames it was scored on.

  2026-08-19 reports a grouped held-out 0.8151, which LOOKS like the best score in the
  file and is not comparable to any other: it is a FOUR-fold split over 60,000 rows per
  fold, where every later round is a five-fold split over about 250,000. Plotting it
  would say the model peaked on day two and has been worse ever since, which is an
  artefact of the test changing, not of the model.

THE REFERENCE ALSO CHANGED PART-WAY, and the plate marks where. The 08-20 and 08-21
rounds were scored against "ground truth + owner corrections"; from 08-22 the reference
is "owner corrections only". A rise across that boundary is partly a change of what the
model is being marked against, so the two regimes are drawn as separate segments and
only the last three are a like-for-like series.

AND IT IS NOT A CURVE OF "MORE CORRECTIONS, BETTER MODEL", which is what this figure was
first built to show. Across the three comparable rounds the corrected pixel count barely
moves -- 31.27, 31.27 and 31.32 million -- while the IoU climbs 0.776 to 0.811. What
improved over those rounds was the RECIPE, not the amount of correction, and the figure
says so rather than letting the reader infer the flattering version.

ONE ROUND WAS REJECTED AND IT IS SHOWN. On 2026-08-20 a candidate regressed and the gate
refused to deploy it. A figure that quietly dropped it would be claiming the process
only ever improves.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_retrain.py
"""
import json
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths                                       # noqa: E402
sys.dont_write_bytecode = True

import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402

import journal_style as J                           # noqa: E402

J.use()
OUT = _paths.FIG_DIR
NAME = "F10 - retraining rounds"
HIST = os.path.join(_paths.TXM_REPO, "app_data", "models", "retrain_history.json")

SHORT = {"hgb_hybrid_nogt": "hgb hybrid", "mlp_ens_nogt": "mlp ensemble",
         "corrections_only_v3": "corrections v3",
         "corrections_only_v4_overlap": "corrections v4",
         "thincore_v5": "thincore v5"}


def rounds():
    hist = json.load(open(_paths.require(HIST, "the TXM retraining history", "TXM_REPO")))
    out = []
    for r in hist:
        h = r.get("heldout") or {}
        if h.get("grouped_by") != "image" or "mean_iou" not in h:
            continue                      # in-sample rounds are excluded, see docstring
        if int(h.get("k") or 0) != 5:
            continue                      # the k=4 round is a different test entirely
        out.append(dict(
            stamp=r["stamp"][:8], recipe=(r.get("gate_detail") or {}).get("recipe")
            or r.get("recipe") or "?",
            iou=float(h["mean_iou"]), std=float(h.get("std_iou") or 0.0),
            lo=float(h.get("min_iou") or h["mean_iou"]),
            prec=h.get("mean_precision"), rec=h.get("mean_recall"),
            m17=h.get("mean_iou_17_only"), mhy=h.get("mean_iou_hybrid_only"),
            deployed=bool(r.get("deployed")), reason=r.get("reason"),
            corr_px=r.get("correction_crack_px"), k=h.get("k"),
            ref=str(h.get("label_source") or "?"),
            n_img=h.get("labelled_images_used")))
    if len(out) < 3:
        raise SystemExit(f"only {len(out)} grouped held-out rounds in {HIST}; the "
                         f"figure would not show a trend")
    return out


def main():
    R = rounds()
    xs = list(range(len(R)))
    W = J.PAGEW
    fig = plt.figure(figsize=(W, 4.05))
    ax = fig.add_axes([0.115, 0.345, 0.620, 0.615])

    #: ONE LINE PER REFERENCE. Joining across the point where the thing the model is
    #: marked against changed would draw a rise that is partly a change of ruler.
    regimes = []
    for i, r in enumerate(R):
        if not regimes or r["ref"] != R[regimes[-1][-1]]["ref"]:
            regimes.append([i])
        else:
            regimes[-1].append(i)
    _SHADE = []
    for grp in regimes:
        dep = [i for i in grp if R[i]["deployed"]]
        if len(dep) > 1:
            ax.plot([xs[i] for i in dep], [R[i]["iou"] for i in dep], "-",
                    color=J.ACCENT2, lw=1.2, zorder=3)
    if len(regimes) > 1:
        cut = regimes[1][0] - 0.5
        #: A DASHED LINE WAS NOT ENOUGH. The rounds left of it are scored against a
        #: different reference -- ground truth plus corrections, rather than
        #: corrections alone -- so their heights cannot be compared with the rounds on
        #: the right, which is the one thing a shared y-axis invites a reader to do.
        #: Shading the earlier regime says "different measurement" before the caption
        #: gets a chance to, and the connecting line already stops at the boundary.
        #: SHADED AFTER THE LIMITS ARE SET. Reading get_xlim() here, before
        #: ax.set_xlim() runs further down, returns matplotlib's autoscale default and
        #: puts the band in the wrong place -- which is exactly what the first version
        #: of this did, shading a sliver on the wrong side of the divider.
        ax.axvline(cut, color=J.G_MID, lw=0.7, dashes=(3.0, 2.0), zorder=2)
        ax.text(cut + 0.10, ax.get_ylim()[1], "reference changes:\ncorrections only",
                fontsize=J.TICK, color=J.G_MID, ha="left", va="top",
                linespacing=1.15, zorder=6)
        _SHADE.append(cut)
    for i, r in enumerate(R):
        ax.errorbar(i, r["iou"], yerr=r["std"], color=J.ACCENT2, lw=0.9, capsize=2.2,
                    zorder=4)
        if r["deployed"]:
            ax.plot(i, r["iou"], "o", ms=6.0, color=J.ACCENT2, mec="white", mew=0.8,
                    zorder=5)
        else:
            ax.plot(i, r["iou"], "o", ms=7.0, mfc="white", mec=J.G_DARK, mew=1.2,
                    zorder=5)
            ax.annotate("rejected by the\ndeployment gate", xy=(i, r["iou"]),
                        xytext=(i + 0.22, r["iou"] - 0.040), fontsize=J.TICK,
                        color=J.G_DARK, ha="left", va="top", linespacing=1.15,
                        arrowprops=dict(arrowstyle="-", lw=0.5, color=J.G_DARK,
                                        shrinkA=1, shrinkB=3))
    best = R[-1]
    ax.annotate(f"{best['iou']:.3f}", xy=(xs[-1], best["iou"]),
                xytext=(xs[-1] - 0.12, best["iou"] + 0.028), fontsize=J.TICK,
                color=J.ACCENT2, fontweight="bold", ha="center")

    ax.set_xticks(xs)
    ax.set_xticklabels([f"{SHORT.get(r['recipe'], r['recipe'])}\n{r['stamp'][4:6]}"
                        f"/{r['stamp'][6:8]}" for r in R], fontsize=J.TICK)
    ax.set_ylabel("held-out IoU\n(5-fold, grouped by image)", fontsize=J.LABEL)
    ax.set_xlabel("retraining round", fontsize=J.LABEL, labelpad=3)
    ax.set_xlim(-0.45, len(R) - 0.30)
    #: the earlier regime is scored against a different reference, so its heights
    #: cannot be read against the rounds on the right -- which a shared y-axis is an
    #: open invitation to do. The band says so before the caption can.
    for _c in _SHADE:
        ax.axvspan(-0.45, _c, color=J.G_LIGHT, alpha=0.5, lw=0, zorder=0)
        ax.text((-0.45 + _c) / 2.0, ax.get_ylim()[1] - 0.004,
                "different reference:\nnot comparable with the rounds on the right",
                fontsize=J.TICK, color=J.G_DARK, ha="center", va="top",
                linespacing=1.15, zorder=6)
    lo = min(r["iou"] - r["std"] for r in R)
    hi = max(r["iou"] + r["std"] for r in R)
    #: the side panel's bars must fit this range too, or sharing the axis clips them
    lo = min(lo, min(v for v in (best["m17"], best["mhy"], best["iou"])
                     if v is not None))
    ax.set_ylim(lo - 0.055, hi + 0.055)
    ax.tick_params(labelsize=J.TICK)
    for sp in ax.spines.values():
        sp.set_linewidth(0.6)

    # the side panel: what the deployed model is made of, on the same held-out folds
    bx = fig.add_axes([0.825, 0.345, 0.160, 0.575])
    parts = [("17-ch", best["m17"]), ("hybrid", best["mhy"]), ("both", best["iou"])]
    parts = [(n, v) for n, v in parts if v is not None]
    #: POINTS, NOT BARS. Sharing the main panel's zoomed y-axis is right -- one
    #: quantity, one scale -- but it leaves a bar standing on a baseline of 0.66
    #: rather than zero, and a truncated bar exaggerates the very differences this
    #: panel is there to let a reader judge. A marker has no baseline to truncate.
    for i, (n, v) in enumerate(parts):
        last = i == len(parts) - 1
        bx.plot(i, v, "o", ms=6.5 if last else 5.5,
                color=J.ACCENT2 if last else J.G_MID,
                mec="white" if last else J.G_DARK, mew=0.8, zorder=5)
        bx.text(i, v + 0.006, f"{v:.3f}", fontsize=J.TICK, ha="center",
                va="bottom", color=J.ACCENT2 if last else J.G_DARK, zorder=6)
    bx.set_xticks(range(len(parts)))
    bx.set_xticklabels([n for n, _ in parts], fontsize=J.TICK, linespacing=1.1)
    #: THE SIDE PANEL SHARES THE MAIN PANEL'S Y-AXIS. It used to run 0 to 1 beside a
    #: main panel running 0.70 to 0.85, so the same quantity -- held-out IoU -- was
    #: drawn at two scales a centimetre apart and the bars towered over the points
    #: they are meant to be read against. One quantity, one scale: a bar and a point
    #: at the same height on this sheet are now the same number.
    bx.set_ylim(*ax.get_ylim())
    bx.set_yticks(ax.get_yticks())
    bx.set_yticklabels([])
    bx.set_xlim(-0.6, len(parts) - 0.4)
    bx.set_title("what the deployed\nmodel is made of", fontsize=J.TICK,
                 color=J.G_DARK, pad=2, linespacing=1.15)
    bx.tick_params(labelsize=J.TICK)
    for sp in bx.spines.values():
        sp.set_linewidth(0.6)

    foot = (f"{best['k']}-fold cross-validation over {best['n_img']} corrected frames, "
            f"grouped by image so no frame scores a model fitted on it. Deployed "
            f"model: precision {best['prec']:.3f}, recall {best['rec']:.3f}, worst "
            f"fold {best['lo']:.3f}.")
    note = ("Three recorded rounds are not plotted: one was scored in sample, one used "
            "a 4-fold split over 60,000 rows where these use 5 folds over 250,000. "
            "Across the three like-for-like rounds the corrected pixel count is flat, "
            "so what improved is the recipe and not the amount of correction.")
    texts = []
    y = 0.215
    for body, col in ((foot, J.INK), (note, J.G_MID)):
        for line in textwrap.wrap(body, 118):
            y -= 0.038
            texts.append(fig.text(0.012, y, line, fontsize=J.TICK, color=col,
                                  ha="left", va="bottom"))

    # NO STRING MAY LEAVE THE SHEET. Both footnotes ran off the right edge on the
    # first build and nothing complained: a line that is not on the page cannot be
    # read, and the saved PNG simply did not contain the end of either sentence.
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    pw, ph = fig.canvas.get_width_height()
    tol = fig.dpi / 72.0
    off = []
    for t in list(texts) + [t for a in (ax, bx)
                            for t in list(a.texts) + a.get_xticklabels()
                            + a.get_yticklabels() + [a.xaxis.label, a.yaxis.label]]:
        if not t.get_text().strip():
            continue
        e = t.get_window_extent(renderer=rend)
        if e.x0 < -tol or e.x1 > pw + tol or e.y0 < -tol or e.y1 > ph + tol:
            off.append(t.get_text().strip().replace("\n", " ")[:40])
    if off:
        raise SystemExit(f"{len(off)} string(s) off the sheet: "
                         + "; ".join(repr(o) for o in off))

    #: AND NO TWO STRINGS MAY PRINT THROUGH EACH OTHER. This check measured only
    #: whether a string had left the sheet, so it reported PASS on a plate where a
    #: new annotation was printing straight through "rejected by the deployment gate".
    #: Off-sheet and overlapping are two different faults and only one was being
    #: looked for. 1 pt of real overlap in BOTH directions, so labels that merely
    #: touch are allowed.
    items = []
    for t in fig.findobj(plt.Text):
        if not t.get_text().strip() or not t.get_visible():
            continue
        try:
            items.append((t.get_text().strip().replace("\n", " ")[:40],
                          t.get_window_extent(renderer=rend)))
        except Exception:
            continue
    bad = []
    for i in range(len(items)):
        for k in range(i + 1, len(items)):
            a, b = items[i][1], items[k][1]
            if (min(a.x1, b.x1) - max(a.x0, b.x0) > tol
                    and min(a.y1, b.y1) - max(a.y0, b.y0) > tol):
                bad.append(f"{items[i][0]!r} x {items[k][0]!r}")
    if bad:
        raise SystemExit(f"{len(bad)} overlapping label(s): " + "; ".join(bad[:6]))
    print(f"  CONTROL {len(items)} strings, none off the sheet, none overlapping: PASS")

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({"figure": NAME + ".png",
               "what": "held-out IoU per retraining round as the operator's "
                       "corrections grew, five-fold grouped by image",
               "source": os.path.relpath(HIST, _paths.TXM_REPO),
               "excluded_in_sample_rounds": 2,
               "why_excluded": "the record states those rounds were fitted on the "
                               "reference frames they were then scored on, so their "
                               "0.94 is not comparable with a grouped held-out score",
               "circular_version_not_drawn": "scoring a corrected mask against the "
                                             "corrections that were pasted into it "
                                             "rises by construction and measures "
                                             "nothing about the model",
               "rounds": R}, open(os.path.join(OUT, NAME + ".caption.json"), "w"),
              indent=1)
    for r in R:
        print(f"  {r['stamp']}  {SHORT.get(r['recipe'], r['recipe']):<16} "
              f"IoU {r['iou']:.4f} +/- {r['std']:.4f}  "
              f"{'deployed' if r['deployed'] else 'REJECTED'}")


if __name__ == "__main__":
    main()
