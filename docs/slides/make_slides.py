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

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.image import imread

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
REPO = os.path.dirname(os.path.dirname(HERE))      # .../crack-fractography
PF = os.path.join(REPO, "paper", "figures", "out")
DF = os.path.join(REPO, "docs", "figures")
OUT = os.path.join(HERE, "all_figures.pdf")
SIZE = (13.333, 7.5)          # 16:9
INK, MUTED, WARN = "#15181c", "#59606a", "#8a4b00"
MIN_PT = 9.0

SLIDES = [
    dict(img=os.path.join(PF, "1 - what each stage does.png"),
         title="What each stage of the detector does",
         claim="The SEM row is v1.49.2, the pipeline the app runs: seven flattening radii "
               "unioned, every candidate region kept.",
         caveat="Panel 6 is the candidate stage; panel 8 is the full pipeline including "
                "Pass 2. The retired region classifier would have removed 21.6% "
                "(207,448 px) of what now ships."),
    dict(img=os.path.join(PF, "3 - method comparison, identical data.png"),
         title="Every method on identical data",
         claim="Eleven arms, the same 15 tiles from the same 9 frames, the same "
               "leave-one-frame-out budget. The ranking REVERSES between the two metrics, "
               "and that is the result.",
         caveat="The dashed line at IoU 0.166 is what a physically correct 3 px trace "
                "scores. Arms above it are not more accurate; they are fatter."),
    dict(img=os.path.join(PF, "6 - SEM, what deleting the region classifier recovers.png"),
         title="What deleting the region classifier recovers",
         claim="Three ETD specimens scored recall 0.0000 at every candidate setting ever "
               "tried. The candidates covered those cracks all along; the classifier was "
               "rejecting them.",
         caveat="It also COSTS precision on ordinary fields, 0.8925 to 0.7840 pooled off "
                "the one off-specimen void tile. Shown on the same plate."),
    dict(img=os.path.join(DF, "fig_aggregation.png"),
         title="The reporting choice moves the number more than any method does",
         claim="One set of masks, six legitimate ways of reporting it. The IoU span across "
               "readings is 0.1985 -- larger than the +0.1753 that switching the classifier "
               "off actually bought.",
         caveat="Always state the aggregation AND the tolerance. The pooled row and the "
                "per-specimen-at-2px row describe the same pixels."),
    dict(img=os.path.join(DF, "fig_ceiling.png"),
         title="A correct answer caps at IoU 0.50 against these labels",
         claim="A perfectly placed trace -- the label's own centreline, zero localisation "
               "error -- peaks at IoU 0.4993 pooled at an 11 px width, and 0.5498 as a "
               "median over tiles at 7 px.",
         caveat="So IoU 0.42 is 67-77% of what is achievable, not 42% of perfect. The "
                "ceiling is aggregation-dependent too and must be read in the same units "
                "as the score."),
    dict(img=os.path.join(DF, "fig_gameability.png"),
         title="Both headline metrics reward being fatter than a crack",
         claim="Dilating the mask to 1.5x its area adds no information and moves clDice "
               "+0.0478 on 13 of 13 specimens (p=0.0002). Skeleton-F1 at 2 px moves "
               "+0.0015 (p=0.68).",
         caveat="The full-frame paint gate has the same disease: a correct 3 px trace of "
                "the human's own paint deletes 94.63% of it, because the paint is 154 px "
                "wide. Three instruments, one failure mode."),
    dict(img=os.path.join(DF, "fig_public_scores.png"),
         title="The same detector on public crack datasets",
         claim="Frozen -- every constant as the app ships, nothing fitted -- it scores "
               "0.631 on DeepCrack (237 images) and 0.087 on CrackForest (118). Refitting "
               "ONE constant, mad_k, takes those to 0.793 and 0.450.",
         caveat="CrackForest's fitted value carried BLIND to DeepCrack reaches 0.753, "
                "95% of refitting there -- so one road-calibrated constant serves road "
                "imagery and the SEM-calibrated 5.0 is the outlier. Still below the 0.753 "
                "a model trained on CrackForest reports."),
    dict(img=os.path.join(DF, "fig_public_baselines.png"),
         title="Against six classical baselines, on the same images",
         claim="Every arm run here, same images, same scorer, and EVERY arm's parameter "
               "chosen leave-one-image-out so none is handicapped. It ranks 1 of 7 on "
               "DeepCrack (0.821 against 0.730) and 3 of 7 on CrackForest, behind the "
               "Meijering and Sato ridge filters at 0.495.",
         caveat="So the claim is not 'better than classical methods' but 'better on wide "
                "high-contrast cracks, behind a ridge filter on thin faint ones' -- which "
                "is what a darkness detector should do. The two panels are 118 and 120 "
                "images; do not read across them."),
    dict(img=os.path.join(DF, "fig_public_examples.png"),
         title="What that looks like on the public images",
         claim="Ground truth against the frozen and refitted masks, on one typical image "
               "from each dataset.",
         caveat="Each image is chosen by RULE -- the one whose mad_k 2.5 score is nearest "
                "that dataset's mean -- not by eye. The first draft hand-picked a "
                "CrackForest image where frozen beat the refit, the reverse of the "
                "aggregate."),
    dict(img=os.path.join(DF, "fig_operating_curve.png"),
         title="Recall alone is not a score",
         claim="The loosest setting reaches recall 0.98 and scores F1 0.162. Its precision, "
               "0.0883, is identical to a plain Otsu threshold and is 1.09x a coin flip.",
         caveat="Read precision against the no-information floor -- the prevalence of crack "
                "among refereed pixels, 0.0810 on TXM and 0.0297 on the SEM tiles."),
]


def wrap(ax, y, text, size, color=INK, weight="normal", width=118, style="normal"):
    for line in textwrap.wrap(text, width=width) or [""]:
        ax.text(0.0, y, line, fontsize=size, color=color, fontweight=weight,
                fontstyle=style, va="top", ha="left", transform=ax.transAxes)
        y -= (size + 4.0) / 540.0
    return y


def slide(pdf, sizes, title, claim, caveat, img=None, table=None):
    fig = plt.figure(figsize=SIZE); fig.patch.set_facecolor("white")
    ax = fig.add_axes([0.055, 0.04, 0.89, 0.92]); ax.axis("off")
    y = 1.0
    ax.text(0, y, title, fontsize=22, fontweight="bold", color=INK, va="top",
            transform=ax.transAxes); sizes.append(22)
    y -= 0.075
    y = wrap(ax, y, claim, 12.5, color=INK); sizes.append(12.5)
    y -= 0.012
    if caveat:
        y = wrap(ax, y, "Caveat.  " + caveat, 11.0, color=WARN); sizes.append(11.0)
        y -= 0.010
    top = 0.04 + 0.92 * y
    if img and os.path.exists(img):
        arr = imread(img)
        avail_h, avail_w = top - 0.055, 0.89
        ih = avail_w * (arr.shape[0] / arr.shape[1]) * (SIZE[0] / SIZE[1])
        if ih > avail_h:
            ih, iw = avail_h, avail_h / ((arr.shape[0] / arr.shape[1]) * (SIZE[0] / SIZE[1]))
        else:
            iw = avail_w
        axi = fig.add_axes([0.055 + (0.89 - iw) / 2, top - ih, iw, ih])
        axi.imshow(arr); axi.axis("off")
    elif table:
        rows, hdr = table
        axt = fig.add_axes([0.055, 0.055, 0.89, max(0.12, top - 0.065)]); axt.axis("off")
        t = axt.table(cellText=rows, colLabels=hdr, loc="upper center", cellLoc="left")
        t.auto_set_font_size(False); t.set_fontsize(11.5); sizes.append(11.5)
        t.scale(1, 1.75)
        for (r, c), cell in t.get_celld().items():
            cell.set_edgecolor("#d7dbe0")
            if r == 0:
                cell.set_text_props(fontweight="bold", color=INK)
                cell.set_facecolor("#eef1f4")
            elif rows[r - 1][0].startswith(">>>"):
                cell.set_facecolor("#fff4e3")
                cell.set_text_props(fontweight="bold")
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
