#!/usr/bin/env python3
"""The metric words, in plain language, with a picture.

Every number in this project is one of these, and all of them get misread. The point of
the picture is that precision, recall, F1 and IoU are four different fractions of the SAME
three areas -- once you can see the three areas, the four names stop being jargon.
"""
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle

INK, MUTED, WARN = "#15181c", "#59606a", "#8a4b00"
GREEN, BLUE, GREY = "#2ca02c", "#1f77b4", "#9aa3ad"
SIZE = (13.333, 7.5)

# term, the one-line plain meaning, when it misleads, and this project's own example
TERMS = [
    ("Precision",
     "Of everything the computer marked as crack, how much really was crack.",
     "High precision with low recall just means it only marked the easy bits.",
     "Yours on your tiles: 0.90 at a 2 px tolerance. Of what it marks, 9 in 10 is crack."),
    ("Recall",
     "Of all the crack that is really there, how much the computer found.",
     "MARKING THE WHOLE IMAGE SCORES A PERFECT 1.0. Recall alone is never a score.",
     "Yours: 0.80. It finds four fifths of the crack you painted."),
    ("F1",
     "The two above combined into one number, in a way that punishes being bad at either.",
     "You cannot cheat it by marking everything -- that destroys precision, so F1 collapses.",
     "Yours: 0.66. Marking everything would score 0.06."),
    ("IoU  (intersection over union)",
     "The overlap divided by everything that either of you marked. The strictest of the four.",
     "It rewards drawing THICK. A perfectly placed thin line scores badly against a thick "
     "label, so a fatter, less accurate answer can beat a correct one.",
     "Yours: 0.50 at 2 px. A PERFECT answer caps at 0.50 here -- so you are near the limit, "
     "not at half marks."),
    ("clDice",
     "Did you find the crack along its LENGTH -- following the path, ignoring how thick you "
     "drew it.",
     "On these labels it is still partly cheatable by thickening: a no-information "
     "dilation moved it +0.048 on 13 of 13 specimens.",
     "Yours: 0.64."),
    ("Skeleton-F1 at 2 px",
     "The same idea as clDice but done properly: compare the two centre-lines, allowing a "
     "2 pixel wobble.",
     "The one metric here that a thicker mask does NOT improve (+0.0015, p=0.68).",
     "Yours: 0.55. This is the honest headline number."),
    ("Tolerance",
     "How many pixels of slack before a pixel counts as wrong. '2 px' forgives being two "
     "pixels off.",
     "It changes the answer enormously, so a score without a stated tolerance is unreadable.",
     "On CrackForest the published F1 is 0.75 at 0 px and 0.97 at 2 px -- same model."),
    ("The floor  (no-information level)",
     "What a method that knows nothing would score, by marking at random.",
     "A precision of 0.26 sounds poor; if the floor is 0.08 it is 3x better than guessing.",
     "Crack covers ~3% of your tiles, so random marking scores about 0.03."),
]


def wrap(ax, y, text, size, color=INK, weight="normal", width=104, style="normal", x=0.0):
    for line in textwrap.wrap(text, width=width) or [""]:
        ax.text(x, y, line, fontsize=size, color=color, fontweight=weight,
                fontstyle=style, va="top", ha="left", transform=ax.transAxes)
        y -= (size + 3.6) / 540.0
    return y


def picture(pdf, sizes):
    """Two overlapping blobs. Everything above is a fraction of these three areas."""
    fig = plt.figure(figsize=SIZE); fig.patch.set_facecolor("white")
    ax = fig.add_axes([0.055, 0.04, 0.89, 0.92]); ax.axis("off")
    ax.text(0, 1.0, "All four scores are fractions of the same three areas",
            fontsize=22, fontweight="bold", color=INK, va="top",
            transform=ax.transAxes); sizes.append(22)
    y = wrap(ax, 0.925,
             "Green is the crack you painted. Blue is what the computer marked. Everything "
             "else is just which part of this picture you divide by.", 12.5, color=MUTED)
    sizes.append(12.5)

    axd = fig.add_axes([0.06, 0.30, 0.44, 0.50]); axd.set_aspect("equal"); axd.axis("off")
    axd.set_xlim(-1.7, 2.1); axd.set_ylim(-1.35, 1.35)
    axd.add_patch(Circle((-0.35, 0), 0.95, facecolor=GREEN, alpha=0.40, edgecolor=GREEN, lw=2))
    axd.add_patch(Circle((0.45, 0), 0.95, facecolor=BLUE, alpha=0.40, edgecolor=BLUE, lw=2))
    axd.text(-1.05, 0, "missed\n(FN)", ha="center", va="center", fontsize=12,
             color="#1a6b1a"); sizes.append(12)
    axd.text(0.05, 0, "both\n(TP)", ha="center", va="center", fontsize=13,
             fontweight="bold", color=INK); sizes.append(13)
    axd.text(1.15, 0, "false\nalarm (FP)", ha="center", va="center", fontsize=12,
             color="#13507d")
    axd.text(-0.35, 1.08, "really crack", ha="center", fontsize=12.5, color=GREEN,
             fontweight="bold"); sizes.append(12.5)
    axd.text(0.45, -1.18, "computer marked", ha="center", fontsize=12.5, color=BLUE,
             fontweight="bold")

    axt = fig.add_axes([0.54, 0.26, 0.42, 0.56]); axt.axis("off")
    rows = [("Precision", "both  /  everything BLUE", "did it cry wolf?"),
            ("Recall", "both  /  everything GREEN", "did it miss things?"),
            ("F1", "balances the two above", "one number, not cheatable"),
            ("IoU", "both  /  the WHOLE picture above", "strictest; rewards thickness")]
    yy = 0.96
    for nm, frac, note in rows:
        axt.text(0, yy, nm, fontsize=15, fontweight="bold", color=INK,
                 transform=axt.transAxes, va="top"); sizes.append(15)
        axt.text(0, yy - 0.075, frac, fontsize=13, color=INK,
                 transform=axt.transAxes, va="top"); sizes.append(13)
        axt.text(0, yy - 0.142, note, fontsize=11, color=MUTED, fontstyle="italic",
                 transform=axt.transAxes, va="top"); sizes.append(11)
        yy -= 0.25
    pdf.savefig(fig); plt.close(fig)


def pages(pdf, sizes):
    picture(pdf, sizes)
    per = 3
    for pg in range(0, len(TERMS), per):
        chunk = TERMS[pg:pg + per]
        fig = plt.figure(figsize=SIZE); fig.patch.set_facecolor("white")
        ax = fig.add_axes([0.055, 0.04, 0.89, 0.92]); ax.axis("off")
        ax.text(0, 1.0, f"The words, in plain English  ({pg // per + 1} of "
                        f"{(len(TERMS) + per - 1) // per})",
                fontsize=22, fontweight="bold", color=INK, va="top",
                transform=ax.transAxes); sizes.append(22)
        y = 0.915
        for name, plain, trap, mine in chunk:
            ax.text(0, y, name, fontsize=16, fontweight="bold", color=INK, va="top",
                    transform=ax.transAxes); sizes.append(16)
            y -= 0.048
            y = wrap(ax, y, plain, 13.0); sizes.append(13.0)
            y -= 0.008
            y = wrap(ax, y, "Watch out:  " + trap, 11.5, color=WARN); sizes.append(11.5)
            y -= 0.006
            y = wrap(ax, y, "Here:  " + mine, 11.5, color=MUTED); sizes.append(11.5)
            y -= 0.030
        pdf.savefig(fig); plt.close(fig)
