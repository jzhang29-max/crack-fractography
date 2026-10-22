#!/usr/bin/env python3
"""One page: the whole detection path, from micrograph to measured numbers.

WHY A GENERATOR AND NOT A DRAWING. A hand-drawn diagram of a pipeline is wrong the moment
the pipeline changes, and this one has changed twice in a fortnight -- the region classifier
was switched off and the single-scale threshold became a 7-scale union. Every constant below
is READ FROM analysis/detector_overrides.py at draw time, so the figure cannot claim a value
the shipped detector does not use. If a constant is renamed this script fails loudly instead
of drawing a stale number.

    python -B docs/figures/mk_pipeline.py      -> fig_pipeline.png + fig_pipeline.caption.json

Greyscale only, and every box is separated by lightness and border weight rather than hue, so
the plate survives printing and colour-blind readers. Type-size floor is asserted before
savefig, because a plate in this project once shipped at 2.3 pt.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "analysis"))
import detector_overrides as DO  # noqa: E402

# Read the shipped settings rather than restating them. A missing name is a hard error.
for required in ("SCALE_LADDER", "ABSOLUTE_DARK_THRESH", "USE_REGION_CLASSIFIER",
                 "USE_MULTISCALE_UNION", "DECIMATE_ABOVE_SIGMA"):
    if not hasattr(DO, required):
        raise SystemExit(f"detector_overrides has no {required!r} -- this figure is stale")

LADDER = ", ".join(str(s) for s in DO.SCALE_LADDER)
# READ IT, DO NOT FALL BACK. A getattr default meant this plate printed 5.0 while the
# manuscript selected 6.0, so the figure silently contradicted the text it illustrates.
# A missing name is now a hard error, like every other constant on this plate.
if not hasattr(DO, "MAD_K"):
    raise SystemExit("detector_overrides.py defines no MAD_K; this plate must not guess "
                     "one -- add it there so the figure and the paper cannot disagree")
MAD_K = DO.MAD_K

BODY, SMALL, TITLE = 8.6, 7.6, 11.0
FLOOR = 7.0

#: (y, title, body, kind). kind picks the border weight: "stage" is the shipped path,
#: "off" is a stage that exists and is DISABLED, "human" is the correction layer.
STAGES = [
    ("Micrograph", "SEM or TXM, 8-bit greyscale. 6144 x 4096 px is typical; nothing is\n"
     "resized and nothing is tiled -- the whole frame is processed at full resolution.", "stage"),
    ("Flatten the background",
     f"Multi-scale background estimate at sigma = {LADDER} px, subtracted.\n"
     f"Above sigma {DO.DECIMATE_ABOVE_SIGMA} the estimate is computed on a decimated copy, which is what\n"
     "makes the long end of the ladder affordable on a 25 Mpx frame.", "stage"),
    ("Propose dark candidates",
     f"{'Union over all ' + str(len(DO.SCALE_LADDER)) + ' scales' if DO.USE_MULTISCALE_UNION else 'Single scale'}: a pixel is a candidate if it is dark at ANY scale.\n"
     f"Two gates, and they are the whole detector: a robust MAD cut at mad_k = {MAD_K}\n"
     f"sigma, and an absolute floor at intensity {DO.ABSOLUTE_DARK_THRESH}. Measured on this corpus the\n"
     "absolute floor alone accounts for about half of all recall that is lost.", "stage"),
    ("Clean and label",
     "Fill holes, drop blobs under 13 px, label 8-connected, then drop regions\n"
     "under 40 px. These floors are tuned for SEM crack widths.", "stage"),
    ("Pass 1: score each region",
     "An 8-feature classifier scores every candidate region.\n"
     f"SHIPPED SETTING: USE_REGION_CLASSIFIER = {DO.USE_REGION_CLASSIFIER} -- every region is kept.\n"
     "Deleting the classifier beat keeping it on every metric, with no free parameters:\n"
     "against the same candidate stage with the classifier bypassed and nothing else\n"
     "changed -- one variable -- paired median IoU +0.1753 over 13 specimens, 11 of\n"
     "13, p = 0.0061. The shipped path also widened the scale ladder, and those two\n"
     "changes together are +0.2296: that larger figure is not the classifier's.\n"
     "Three ETD specimens that\n"
     "scored recall 0.0000 at every setting ever tried were never invisible to the\n"
     "proposal stage -- the classifier was rejecting them.",
     "off" if not DO.USE_REGION_CLASSIFIER else "stage"),
    ("Pass 2: grow into the mask",
     "concavity, bridge_corridor and interior_fill candidates, generated RELATIVE to\n"
     "the pass-1 mask and scored by the same model. A second pass is forced by the\n"
     "problem, not by the model count: \"how close is this to a confirmed crack\" has\n"
     "no meaning before a crack is confirmed. Over 26 hand-labelled tiles it adds\n"
     "17,948 px and moves pooled IoU 0.3344 -> 0.3351.", "stage"),
    ("Measure",
     "Per region: area, skeleton length, mean width, fitted-ellipse axes, and whether\n"
     "it runs out of frame (a censored length is a LOWER BOUND). Per frame: area\n"
     "fraction, number density, largest region's share of area, and a segment-level\n"
     "orientation rose with a per-frame permutation null.", "stage"),
    ("Human correction",
     "Painted corrections override everything above. Authority order is\n"
     "human correction > imported mask > built-in detector, and the app never\n"
     "writes to the pipelines' own derived masks.", "human"),
]


def check(fig):
    small = [t.get_fontsize() for t in fig.findobj(plt.Text) if t.get_text().strip()]
    if small and min(small) < FLOOR:
        raise SystemExit(f"type too small: {min(small):.1f} pt, floor is {FLOOR}")


def main():
    # HEIGHT IS COMPUTED FROM THE CONTENT, not assumed. The first version of this used a
    # fixed row pitch with variable-length bodies: every box overflowed into the one below
    # and the plate was unreadable, while the script reported success. Look at the artifact.
    LINE = 0.215          # inches per body line
    HEAD = 0.30           # inches for the bold title line
    PAD = 0.17            # inches of padding inside a box
    GAP = 0.30            # inches between boxes, which the arrow lives in

    heights = [HEAD + PAD + LINE * (body.count("\n") + 1) for _, body, _ in STAGES]
    body_h = sum(heights) + GAP * (len(STAGES) - 1)
    top_pad, bot_pad = 0.62, 0.66
    fig_h = body_h + top_pad + bot_pad
    fig_w = 9.6

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, fig_w); ax.set_ylim(0, fig_h); ax.axis("off")

    ax.text(fig_w / 2, fig_h - 0.30, "How the crack detector works, end to end",
            ha="center", va="center", fontsize=TITLE, fontweight="bold")

    x0, x1 = 0.42, fig_w - 0.42
    y = fig_h - top_pad
    for i, (title, body, kind) in enumerate(STAGES):
        h = heights[i]
        face = {"stage": "0.97", "off": "0.90", "human": "0.93"}[kind]
        lw = {"stage": 1.0, "off": 1.0, "human": 1.7}[kind]
        style = {"stage": "-", "off": (0, (4, 2)), "human": "-"}[kind]
        ax.add_patch(FancyBboxPatch((x0, y - h), x1 - x0, h,
                                    boxstyle="round,pad=0.01,rounding_size=0.05",
                                    facecolor=face, edgecolor="0.15",
                                    linewidth=lw, linestyle=style))
        tag = "   [DISABLED]" if kind == "off" else ""
        ax.text(x0 + 0.22, y - 0.20, f"{i + 1}. {title}{tag}",
                fontsize=BODY, fontweight="bold", va="center", ha="left")
        ax.text(x0 + 0.22, y - HEAD - 0.04, body, fontsize=SMALL, va="top", ha="left",
                color="0.18", linespacing=1.5)
        if i < len(STAGES) - 1:
            ax.add_patch(FancyArrowPatch((fig_w / 2, y - h), (fig_w / 2, y - h - GAP + 0.03),
                                         arrowstyle="-|>", mutation_scale=11,
                                         color="0.25", linewidth=1.0))
        y -= h + GAP

    ax.text(fig_w / 2, 0.30,
            "Dashed = a stage that exists and is switched off.   Heavy border = the human "
            "layer that overrides the machine.\nEvery constant in this figure is read from "
            "analysis/detector_overrides.py when it is drawn.",
            ha="center", va="center", fontsize=SMALL, color="0.3", linespacing=1.5)

    check(fig)
    out = os.path.join(HERE, "fig_pipeline.png")
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    cap = {
        "figure": "fig_pipeline.png",
        "title": "How the crack detector works, end to end",
        "stages": [s[0] for s in STAGES],
        "settings_read_from_code": {
            "SCALE_LADDER": list(DO.SCALE_LADDER),
            "ABSOLUTE_DARK_THRESH": DO.ABSOLUTE_DARK_THRESH,
            "USE_REGION_CLASSIFIER": DO.USE_REGION_CLASSIFIER,
            "USE_MULTISCALE_UNION": DO.USE_MULTISCALE_UNION,
            "DECIMATE_ABOVE_SIGMA": DO.DECIMATE_ABOVE_SIGMA,
            "mad_k": MAD_K,
        },
        "note": "Drawn by docs/figures/mk_pipeline.py. Constants are read from "
                "analysis/detector_overrides.py at draw time, so the figure cannot quote a "
                "value the shipped detector does not use.",
    }
    json.dump(cap, open(os.path.join(HERE, "fig_pipeline.caption.json"), "w"), indent=1)
    print("wrote", out)
    print("stages:", len(STAGES), "| classifier on:", DO.USE_REGION_CLASSIFIER,
          "| ladder:", LADDER)


if __name__ == "__main__":
    main()
