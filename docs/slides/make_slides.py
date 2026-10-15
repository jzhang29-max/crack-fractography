#!/usr/bin/env python3
"""Every figure on slides, as a PDF.

A PDF rather than a web page, for the same reason the flow diagram is one: this gets
printed, attached and presented. Landscape 16:9 so it projects.

Each plate gets a slide carrying ONE claim as its title and the caveat it must never be
shown without. The caveats are not decoration -- most of this project's results were
over-read at some point for exactly the reason stated on the slide, and three of the eight
plates exist only because a previous version of a number turned out to be wrong.

Figures are read from the directories that generate them; nothing is recomputed here, and
the comparison table is the measurement in docs/slides/comparison.json.
"""
import json
import os
import textwrap
import json as _json  # noqa: F401

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.image import imread

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
FLOW = os.path.join(os.path.dirname(HERE), "flowchart")
REPO = os.path.dirname(os.path.dirname(HERE))      # .../crack-fractography
PF = os.path.join(REPO, "paper", "figures", "out")
DF = os.path.join(REPO, "docs", "figures")
OUT = os.path.join(HERE, "all_figures.pdf")
SIZE = (13.333, 7.5)          # 16:9
INK, MUTED, WARN = "#15181c", "#59606a", "#8a4b00"
MIN_PT = 9.0

SLIDES = [
    dict(img=os.path.join(PF, "1 - what each stage does.png"),
         title="What each stage does",
         claim=["The pipeline the app runs, panel by panel.",
                "Seven flattening radii, unioned.",
                "Every candidate region kept."],
         caveat="The retired classifier would have deleted 21.6% of this."),
    dict(img=os.path.join(PF, "3 - method comparison, identical data.png"),
         title="Every method, identical data",
         claim=["11 arms, same 15 tiles, same budget.",
                "The ranking REVERSES between the two metrics."],
         caveat="Dashed line = a correct 3 px trace. Above it means fatter, not better."),
    dict(img=os.path.join(PF, "6 - SEM, what deleting the region classifier recovers.png"),
         title="What deleting the classifier recovers",
         claim=["Three specimens went from recall 0.000 to 0.35-0.68.",
                "The cracks were always found; the model rejected them."],
         caveat="It costs precision on clean fields: 0.89 to 0.78."),
    dict(img=os.path.join(DF, "fig_aggregation.png"),
         title="How you report it matters more than the method",
         claim=["One set of masks, six ways of reporting it.",
                "IoU spans 0.1985 across them."],
         caveat="That span is larger than any method change measured here."),
    dict(img=os.path.join(DF, "fig_ceiling.png"),
         title="A correct answer caps at IoU 0.50",
         claim=["A perfectly placed trace peaks at 0.4993.",
                "So IoU 0.42 is ~75% of possible, not 42%."],
         caveat="Always quote IoU with this ceiling."),
    dict(img=os.path.join(DF, "fig_gameability.png"),
         title="The metrics reward thickness",
         claim=["Dilating the mask adds no information.",
                "It still moves clDice +0.048 on 13 of 13.",
                "Skeleton-F1 moves +0.0015."],
         caveat="IoU, clDice and the paint gate all have this fault."),
    dict(img=os.path.join(DF, "fig_public_scores.png"),
         title="On public datasets",
         claim=["Frozen: 0.631 on DeepCrack, 0.087 on CrackForest.",
                "Refitting one constant: 0.793 and 0.450."],
         caveat="CrackForest's fitted value reaches 95% of refitting on DeepCrack."),
    dict(img=os.path.join(DF, "fig_public_baselines.png"),
         title="Against six classical baselines",
         claim=["1st of 7 on DeepCrack (0.821 vs 0.730).",
                "3rd of 7 on CrackForest, behind two ridge filters."],
         caveat="Better on wide bright cracks, worse on thin faint ones. Panels are 118 and 120 images -- don't read across."),
    dict(img=os.path.join(DF, "fig_public_examples.png"),
         title="The same, on the images",
         claim=["Ground truth, frozen, and refitted.",
                "One typical image per dataset."],
         caveat="Images picked by rule (nearest the mean), not by eye."),
    dict(img=os.path.join(DF, "fig_operating_curve.png"),
         title="Recall alone is not a score",
         claim=["The loosest setting reaches recall 0.98.",
                "Its F1 is 0.162 and its precision equals plain Otsu."],
         caveat="Read precision against the floor: 0.081 on TXM, 0.030 on your tiles."),
]


def wrap(ax, y, text, size, color=INK, weight="normal", width=118, style="normal"):
    for line in textwrap.wrap(text, width=width) or [""]:
        ax.text(0.0, y, line, fontsize=size, color=color, fontweight=weight,
                fontstyle=style, va="top", ha="left", transform=ax.transAxes)
        y -= (size + 4.0) / 540.0
    return y


def slide(pdf, sizes, title, claim, caveat, img=None, table=None):
    """One figure, filling the slide, with a SHORT note beside it.

    The figure is the slide. Text sits in a narrow right-hand column as a few short lines,
    not as paragraphs above the picture -- an earlier version put three wrapped paragraphs
    on top and the figure ended up as a strip at the bottom.
    """
    fig = plt.figure(figsize=SIZE); fig.patch.set_facecolor("white")
    TXT_W = 0.235
    fig_w = 1.0 - TXT_W - 0.055

    if img and os.path.exists(img):
        arr = imread(img)
        avail_h, avail_w = 0.90, fig_w
        ih = avail_w * (arr.shape[0] / arr.shape[1]) * (SIZE[0] / SIZE[1])
        if ih > avail_h:
            ih, iw = avail_h, avail_h / ((arr.shape[0] / arr.shape[1]) * (SIZE[0] / SIZE[1]))
        else:
            iw = avail_w
        axi = fig.add_axes([0.025 + (fig_w - iw) / 2, 0.5 - ih / 2, iw, ih])
        axi.imshow(arr); axi.axis("off")
    elif table:
        rows, hdr = table
        axt = fig.add_axes([0.035, 0.06, fig_w, 0.88]); axt.axis("off")
        t = axt.table(cellText=rows, colLabels=hdr, loc="upper center", cellLoc="left")
        t.auto_set_font_size(False); t.set_fontsize(10.5); sizes.append(10.5)
        t.scale(1, 1.55)
        for (r, c), cell in t.get_celld().items():
            cell.set_edgecolor("#d7dbe0")
            if r == 0:
                cell.set_text_props(fontweight="bold", color=INK)
                cell.set_facecolor("#eef1f4")
            elif rows[r - 1][0].startswith(">>>"):
                cell.set_facecolor("#fff4e3"); cell.set_text_props(fontweight="bold")

    ax = fig.add_axes([1.0 - TXT_W - 0.03, 0.06, TXT_W, 0.88]); ax.axis("off")
    y = 1.0
    for line in textwrap.wrap(title, 26):
        ax.text(0, y, line, fontsize=15, fontweight="bold", color=INK, va="top",
                transform=ax.transAxes); y -= 0.042
    sizes.append(15)
    y -= 0.022
    for b in ([claim] if isinstance(claim, str) else list(claim)):
        for line in textwrap.wrap("\u2022  " + b, 32):
            ax.text(0, y, line, fontsize=10.5, color=INK, va="top",
                    transform=ax.transAxes); y -= 0.031
        y -= 0.013
    sizes.append(10.5)
    if caveat:
        y -= 0.012
        for b in ([caveat] if isinstance(caveat, str) else list(caveat)):
            for line in textwrap.wrap("\u26a0  " + b, 32):
                ax.text(0, y, line, fontsize=9.6, color=WARN, va="top",
                        transform=ax.transAxes); y -= 0.029
            y -= 0.012
        sizes.append(9.6)
    pdf.savefig(fig); plt.close(fig)


def build():
    sizes, missing = [], []
    cmp_path = os.path.join(HERE, "comparison.json")
    C = json.load(open(cmp_path, encoding="utf-8")) if os.path.exists(cmp_path) else None
    with PdfPages(OUT) as pdf:
        slide(pdf, sizes, "Crack Fractography — where the measurements stand",
              "v1.49.2. Every figure here is generated from a committed record by a script "
              "in this repository; none is drawn by hand and none carries a number that was "
              "not measured.",
              "Eight slides. Read each one with its caveat: most of these results were "
              "over-read at some point for exactly the reason stated underneath.")
        import metrics_plain
        metrics_plain.pages(pdf, sizes)

        for s in SLIDES:
            if os.path.exists(s["img"]):
                slide(pdf, sizes, s["title"], s["claim"], s["caveat"], img=s["img"])
            else:
                missing.append(s["img"])
        # --- what each measurement means, straight out of the app ------------------
        try:
            from crack_fractography.app import groupstats as GS   # noqa: F401
        except Exception:
            GS = None
        if GS is None:
            sys.path.insert(0, os.path.dirname(HERE))
            try:
                from app import groupstats as GS
            except Exception:
                GS = None
        if GS is not None:
            defs = [(lab, unit, d) for _k, lab, _h, unit, d in GS.SUMMARY]
            per = 4
            for pg in range(0, len(defs), per):
                chunk = defs[pg:pg + per]
                fig = plt.figure(figsize=SIZE); fig.patch.set_facecolor("white")
                ax = fig.add_axes([0.055, 0.04, 0.89, 0.92]); ax.axis("off")
                y = 1.0
                n = f"  ({pg // per + 1} of {(len(defs) + per - 1) // per})"
                ax.text(0, y, "What each measurement means" + n, fontsize=22,
                        fontweight="bold", color=INK, va="top", transform=ax.transAxes)
                sizes.append(22)
                y -= 0.075
                y = wrap(ax, y, "Read straight out of app/groupstats.py, so this slide "
                                "cannot drift from what the application shows.", 11.5,
                         color=MUTED); sizes.append(11.5)
                y -= 0.030
                for lab, unit, d in chunk:
                    ax.text(0, y, lab, fontsize=15, fontweight="bold", color=INK,
                            va="top", transform=ax.transAxes); sizes.append(15)
                    ax.text(1.0, y, unit, fontsize=11, color=MUTED, va="top", ha="right",
                            transform=ax.transAxes); sizes.append(11)
                    y -= 0.042
                    y = wrap(ax, y, d, 12.0, color=INK, width=112); sizes.append(12.0)
                    y -= 0.026
                pdf.savefig(fig); plt.close(fig)
        else:
            raise SystemExit("could not import app.groupstats -- refusing to ship a deck "
                             "whose definitions are hand-copied")

        if C:
            rows = [[r["arm"], f"{r['iou']:.4f}" if r["iou"] is not None else "n/a",
                     f"{r['cldice']:.4f}" if r["cldice"] is not None else "n/a", r["note"]]
                    for r in C["rows"]]
            slide(pdf, sizes, "How good is this model, against published ones?",
                  C["claim"], C["caveat"],
                  table=(rows, ["arm", "IoU", "clDice", "basis"]))
        # --- the pipeline, stage by stage, at deck proportions ----------------------
        cj = os.path.join(FLOW, "flow_content.json")
        if os.path.exists(cj):
            flow = json.load(open(cj, encoding="utf-8"))
            st = json.load(open(os.path.join(FLOW, "_stats.json"), encoding="utf-8"))
            slide(pdf, sizes, "The pipeline, one real image per stage",
                  f"Frame {st['frame']}, window {st['crop_px']:,} px. Every panel is a real "
                  f"array from the real pipeline -- no mock-ups, no schematic boxes.",
                  "The frame is chosen by a rule that works against the detector: the lower "
                  "of the two central tiles by IoU, tie broken downward, so the pages cannot "
                  "flatter it.")
            for i, stg in enumerate(flow, 1):
                figs = [f for f in stg["figs"] if os.path.exists(os.path.join(FLOW, f[0]))]
                bullets = []
                for d_ in stg["does"]:
                    bullets.append(d_ if len(d_) < 150 else d_[:147] + "...")
                for c_ in stg["cost"][:1]:
                    bullets.append(c_ if len(c_) < 150 else c_[:147] + "...")
                note = stg["note"][0] if stg["note"] else None
                if note and len(note) > 170:
                    note = note[:167] + "..."
                if len(figs) == 1:
                    slide(pdf, sizes, f"{i}. {stg['title']}", bullets, note,
                          img=os.path.join(FLOW, figs[0][0]))
                    continue
                # several panels: lay them out in the figure column, same side text
                fig = plt.figure(figsize=SIZE); fig.patch.set_facecolor("white")
                TXT_W = 0.235
                fw = 1.0 - TXT_W - 0.055
                ncol = min(len(figs), 4)
                nrow = (len(figs) + ncol - 1) // ncol
                cw = fw / ncol
                ch = 0.90 / nrow
                for k, (fn, cap) in enumerate(figs[:8]):
                    arr = imread(os.path.join(FLOW, fn))
                    r, c = divmod(k, ncol)
                    cs = 9.0
                    lines = textwrap.wrap(cap, max(18, int(26 * 4 / ncol)))[:2]
                    caph = len(lines) * (cs + 2.2) / 540.0
                    aw = cw * 0.93
                    ah = aw * (arr.shape[0] / arr.shape[1]) * (SIZE[0] / SIZE[1])
                    ah = min(ah, ch - caph - 0.02)
                    aw = ah / ((arr.shape[0] / arr.shape[1]) * (SIZE[0] / SIZE[1]))
                    ctop = 0.95 - r * ch
                    axi = fig.add_axes([0.025 + c * cw, ctop - ah - 0.004, aw, ah])
                    axi.imshow(arr); axi.axis("off")
                    fig.text(0.025 + c * cw, ctop - ah - 0.012, "\n".join(lines),
                             fontsize=cs, color=MUTED, va="top", ha="left")
                    sizes.append(cs)
                ax = fig.add_axes([1.0 - TXT_W - 0.03, 0.06, TXT_W, 0.88]); ax.axis("off")
                yy = 1.0
                for line in textwrap.wrap(f"{i}. {stg['title']}", 24):
                    ax.text(0, yy, line, fontsize=15, fontweight="bold", color=INK,
                            va="top", transform=ax.transAxes); yy -= 0.042
                sizes.append(15)
                yy -= 0.022
                for b in bullets:
                    for line in textwrap.wrap("\u2022  " + b, 32):
                        ax.text(0, yy, line, fontsize=10.5, color=INK, va="top",
                                transform=ax.transAxes); yy -= 0.031
                    yy -= 0.013
                sizes.append(10.5)
                if note:
                    yy -= 0.012
                    for line in textwrap.wrap("\u26a0  " + note, 32):
                        ax.text(0, yy, line, fontsize=9.6, color=WARN, va="top",
                                transform=ax.transAxes); yy -= 0.029
                    sizes.append(9.6)
                pdf.savefig(fig); plt.close(fig)

        d = pdf.infodict()
        d["Title"] = "Crack Fractography - all figures"
        d["Author"] = "Jiaming Zhang"
    if missing:
        raise SystemExit("refusing to ship a deck with missing figures:\n  "
                         + "\n  ".join(missing))
    smallest = min(sizes)
    assert smallest >= MIN_PT, f"type at {smallest} pt, below the {MIN_PT} pt floor"
    print(f"wrote {OUT}")
    print(f"  {os.path.getsize(OUT)/1024:.0f} KB, smallest type {smallest} pt")


if __name__ == "__main__":
    build()
