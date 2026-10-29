#!/usr/bin/env python3
"""A walkthrough of the crack-path measurement, for a reader who is not a programmer.

One real frame, every panel a real array from the pipeline, every caption in plain words.
The last section is the part that matters: what the number at the end can and cannot be
read as, with the control that decides it.
"""
import json
import os
import textwrap

import numpy as np
from scipy import ndimage as ndi
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle, FancyArrowPatch

HERE = os.path.dirname(os.path.abspath(__file__))
A = np.load(os.path.join(HERE, "arrays.npz"))
F = json.load(open(os.path.join(HERE, "facts.json")))
NULLF = os.path.join(HERE, "decisive.json")
NULL = json.load(open(NULLF)) if os.path.exists(NULLF) else {}

NM = F["nm_per_px"]
CROP = F["crop"]
INK, MUT, RULE = "#111111", "#5a5a60", "#d4d4d0"
BLUE, ORANGE, GREEN, RED = "#1F4E9C", "#D95F02", "#00A53B", "#D7301F"

matplotlib.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial"],
    "pdf.fonttype": 42, "figure.facecolor": "white", "savefig.facecolor": "white",
})
PAGE = (8.27, 11.69)          # A4 portrait, inches



def fat(m, r=2):
    """Thicken a one-pixel structure so it survives being printed at 2 inches wide."""
    return ndi.binary_dilation(m, np.ones((2 * r + 1, 2 * r + 1), bool))

def stretch(a, lo=1, hi=99):
    a = a.astype(float)
    p, q = np.percentile(a, [lo, hi])
    return np.clip((a - p) / max(q - p, 1e-6), 0, 1)


def pagetop(fig, title, sub=None):
    fig.text(0.07, 0.962, title, fontsize=15, fontweight="bold", color=INK, va="top")
    if sub:
        fig.text(0.07, 0.936, sub, fontsize=8.6, color=MUT, va="top")
    fig.add_artist(plt.Line2D([0.07, 0.93], [0.925, 0.925], color=RULE, lw=1.0))


def block(fig, top, n, head, body, draw, *, h=0.205, scalebar_um=None):
    """One step: a panel on the left, the explanation on the right."""
    ax = fig.add_axes([0.07, top - h, 0.345, h])
    draw(ax)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(RULE); s.set_linewidth(0.8)
    if scalebar_um:
        px = scalebar_um * 1000.0 / NM
        W = A["img"].shape[1]
        ax.add_patch(Rectangle((W * 0.06, A["img"].shape[0] * 0.92), px,
                               A["img"].shape[0] * 0.018, color="black", zorder=5))
        ax.text(W * 0.06 + px / 2, A["img"].shape[0] * 0.905, f"{scalebar_um:g} µm",
                ha="center", va="bottom", fontsize=7.5, color="black", zorder=6,
                bbox=dict(facecolor="white", edgecolor="none", pad=1.0))
    fig.text(0.445, top - 0.012, f"{n}.  {head}", fontsize=10.6, fontweight="bold",
             color=INK, va="top")
    y = top - 0.045
    for para in body:
        wrapped = textwrap.fill(para, 64)
        fig.text(0.445, y, wrapped, fontsize=8.5, color=INK, va="top", linespacing=1.45)
        y -= 0.0152 * (wrapped.count("\n") + 1) + 0.010
    return top - h - 0.035


pdf_path = os.path.join(HERE, "crack_path_walkthrough.pdf")
with PdfPages(pdf_path) as pdf:
    # =============================================================== page 1: the flow
    fig = plt.figure(figsize=PAGE)
    pagetop(fig, "How a crack picture becomes a number",
            "A step-by-step walkthrough on one real scanning-electron image of stainless "
            "steel, written for a reader who is not a programmer.")
    steps = ["the photograph", "find the crack", "tidy the edge", "thin to a line",
             "find where it splits", "keep the real splits", "the crack as a network",
             "divide the metal into grains", "look left and right at every point",
             "same grain or different?", "test it against controls"]
    ax = fig.add_axes([0.07, 0.40, 0.86, 0.50]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    for i, s in enumerate(steps):
        yy = 0.95 - i * 0.088
        col = BLUE if i < 7 else ORANGE
        ax.add_patch(Rectangle((0.06, yy - 0.035), 0.62, 0.062, facecolor="white",
                               edgecolor=col, lw=1.3, zorder=2))
        ax.text(0.085, yy - 0.004, f"{i + 1}.  {s}", fontsize=9.6, color=INK,
                va="center", zorder=3)
        if i < len(steps) - 1:
            ax.add_patch(FancyArrowPatch((0.37, yy - 0.035), (0.37, yy - 0.053),
                                         arrowstyle="-|>", mutation_scale=9,
                                         color=MUT, lw=0.9, zorder=1))
    ax.text(0.72, 0.95 - 3 * 0.088, "steps 1-7\nwhere did the\ncrack GO?",
            fontsize=8.8, color=BLUE, va="center", linespacing=1.5)
    ax.text(0.72, 0.95 - 8.5 * 0.088, "steps 8-11\ndid it go THROUGH\ngrains or BETWEEN\nthem?",
            fontsize=8.8, color=ORANGE, va="center", linespacing=1.5)
    fig.text(0.07, 0.345,
             textwrap.fill(
                 "Two words you will need. A GRAIN is one small crystal of metal; a "
                 "polished piece of steel is a mosaic of them, packed together like a "
                 "dry-stone wall, each at a slightly different angle. A crack can either "
                 "cut straight THROUGH a grain, which is called TRANSGRANULAR (trans = "
                 "across), or run along the join BETWEEN two of them, which is called "
                 "INTERGRANULAR (inter = between). Which of the two happens tells a "
                 "metallurgist a great deal about why the part failed, so measuring the "
                 "split between them is the point of everything that follows.", 108),
             fontsize=9, color=INK, va="top", linespacing=1.5)
    fig.text(0.07, 0.205,
             textwrap.fill(
                 "What is standard here and what is not. Steps 1 to 10 are established "
                 "methods, and two of them deserve naming because this project reinvented "
                 "them before discovering they existed: the test in step 6 is Erosion "
                 "Thickness (Shaked & Bruckstein 1998; exact definition Liu et al. 2011), "
                 "and the control in step 11 is the torus-translation test (Harms et al. "
                 "2001). Neither is this project's. What is this project's own is the set "
                 "of numbers measured on this material, and the finding in the closing "
                 "section about what those numbers can be read as.", 108),
             fontsize=8.6, color=MUT, va="top", linespacing=1.5)
    fig.text(0.07, 0.075,
             f"Frame {F['stem']}, {F['frame_px'][1]} × {F['frame_px'][0]} pixels at "
             f"{NM:g} nanometres per pixel. The crack covers "
             f"{F['crack_pct_of_frame']:.1f}% of it. Panels show a "
             f"{CROP[2]}-pixel detail; every number quoted is from the whole frame.",
             fontsize=7.8, color=MUT, va="top")
    pdf.savefig(fig); plt.close(fig)

    # ================================================= page 2: steps 1-4, the geometry
    fig = plt.figure(figsize=PAGE)
    pagetop(fig, "Part one: where did the crack go?",
            "Finding the crack, and reducing it to a path.")
    t = 0.895
    img = stretch(A["img"])

    def d1(ax):
        small = stretch(A["img_small"])
        ax.imshow(small, cmap="gray", interpolation="nearest")
        s = 8
        ax.add_patch(Rectangle((CROP[1] / s, CROP[0] / s), CROP[2] / s, CROP[2] / s,
                               fill=False, edgecolor=RED, lw=1.4))
    t = block(fig, t, 1, "The photograph", [
        "A scanning electron microscope does not take a photograph the way a camera does. "
        "It sweeps a fine beam of electrons across a polished surface and counts what comes "
        "back from each spot, so brightness here means how the surface scatters electrons, "
        "not colour.",
        "The dark line wandering across the middle is the crack. The red box marks the "
        "small region used for every later panel, so that the detail is large enough to "
        "see.",
    ], d1)

    def d2(ax):
        rgb = np.dstack([img] * 3)
        rgb[A["crack"]] = matplotlib.colors.to_rgb(BLUE)
        ax.imshow(rgb, interpolation="nearest")
    t = block(fig, t, 2, "Finding the crack", [
        "'Segmentation' is a long word for a simple decision: for every single dot in the "
        "picture, is this crack, or is this not crack? The answer is a stencil, drawn here "
        "in blue.",
        f"On this frame the stencil covers {F['crack_pct_of_frame']:.1f}% of the image. "
        "From this point on the photograph itself is never used again — only the "
        "stencil.",
    ], d2, scalebar_um=20)

    def d3(ax):
        rgb = np.dstack([img] * 3)
        added = A["reg"] & ~A["crack"]
        rgb[A["crack"]] = matplotlib.colors.to_rgb(BLUE)
        rgb[added] = matplotlib.colors.to_rgb(ORANGE)
        ax.imshow(rgb, interpolation="nearest")
    t = block(fig, t, 3, "Tidying the edge", [
        "A real crack edge is ragged, and raggedness causes trouble at the next step, where "
        "small bumps on the wall turn into imaginary side-branches.",
        "So small nicks along the wall are filled in — shown in orange. This step can "
        "only ever ADD material, never remove it, so no piece of crack can be lost here. On "
        f"this frame it added {F['regularise']['area_added_pct']:.2f}% to the area and "
        f"joined {F['regularise']['components_merged']} pieces that were nearly touching.",
    ], d3, scalebar_um=20)

    def d4(ax):
        rgb = np.dstack([0.35 + 0.65 * img] * 3)
        rgb[A["crack"]] = np.array(matplotlib.colors.to_rgb(BLUE)) * 0.30 + 0.60
        rgb[A["skel"]] = matplotlib.colors.to_rgb(RED)
        ax.imshow(rgb, interpolation="nearest")
    t = block(fig, t, 4, "From a ribbon to a line", [
        "The crack is a ribbon: it has length and it has width. For the question 'where did "
        "it go', the width is a distraction.",
        "So the ribbon is thinned down to a line one dot wide running along its middle, like "
        "the centre line painted down a road. Everything after this treats the crack as that "
        f"line. On this frame the line is {F['centreline_px']:,} dots long, which at "
        f"{NM:g} nanometres per dot is about "
        f"{F['centreline_px'] * NM / 1e6:.1f} millimetres of crack.",
    ], d4, scalebar_um=20)
    pdf.savefig(fig); plt.close(fig)

    # ============================================ page 3: steps 5-7, splits and network
    fig = plt.figure(figsize=PAGE)
    pagetop(fig, "Part one, continued: where the crack splits",
            "Counting the places the crack divides — and why the obvious way is wrong.")
    t = 0.895
    c = F["census"]

    def d5(ax):
        rgb = np.dstack([0.55 + 0.45 * img] * 3)
        rgb[fat(A["skel"], 1)] = (0.10, 0.18, 0.42)
        rgb[fat(A["cand"], 4)] = matplotlib.colors.to_rgb(RED)
        ax.imshow(rgb, interpolation="nearest")
    t = block(fig, t, 5, "Where the line meets itself — the wrong answer first", [
        "A crack can split in two. Where it splits, three or more arms of the line meet. The "
        "obvious way to find those places is to look at each dot on the line and ask how "
        "many neighbouring dots it has: three or more means a meeting point.",
        f"Done that way, this frame reports {c['candidate_pixels']:,} dots, drawn in red. "
        "That cannot be right. A simple X-crossing lights up its own centre AND all four "
        "arms — five dots for one crossing — so the count is several times too "
        "high, and a diagram that puts a marker on each dot stacks five markers on the same "
        "spot.",
    ], d5, scalebar_um=20)

    def d6(ax):
        rgb = np.dstack([0.55 + 0.45 * img] * 3)
        rgb[fat(A["skel"], 1)] = (0.10, 0.18, 0.42)
        rgb[fat(A["jlab"], 4)] = matplotlib.colors.to_rgb(ORANGE)
        ax.imshow(rgb, interpolation="nearest")
        nd = A["nodes"]
        if len(nd):
            ax.plot(nd[:, 1] - CROP[1], nd[:, 0] - CROP[0], "o", mfc="none",
                    mec=GREEN, mew=1.8, ms=13)
    t = block(fig, t, 6, "Grouping the dots, then keeping only the real splits", [
        f"First, dots that touch each other are one meeting point, not several. Grouping "
        f"them drops the count from {c['candidate_pixels']:,} to {c['clusters']:,} "
        f"— the simple method over-counted by {c['overmark_factor']:.1f} times.",
        "Second, most of those groups are still not real splits. Inside a WIDE crack the "
        "centre line wanders from one wall to the other and crosses itself, which looks like "
        "a split but is only a consequence of the crack being wide. The test that removes "
        "them: a meeting point counts only if the arms leaving it run FURTHER than the crack "
        "is WIDE at that spot. An arm shorter than the local width has no room to be a real "
        "branch.",
        f"That leaves {c['nodes']:,} real meeting points, circled in green, and demotes "
        f"{c['demoted']:,}. This test is not new — see the note on page 1.",
    ], d6, scalebar_um=20, h=0.235)

    def d7(ax):
        rgb = np.dstack([0.68 + 0.32 * img] * 3)
        b = A["branches"]
        rng = np.random.default_rng(3)
        for lab in np.unique(b):
            if lab == 0:
                continue
            col = rng.random(3) * 0.45 + 0.08         # dark enough to read on a light field
            rgb[fat(b == lab, 1)] = col
        ax.imshow(rgb, interpolation="nearest")
        nd = A["nodes"]
        if len(nd):
            ax.plot(nd[:, 1] - CROP[1], nd[:, 0] - CROP[0], "o", mfc="white",
                    mec="black", mew=1.1, ms=8)
    t = block(fig, t, 7, "The crack as a network", [
        f"What is left is a map: {c['nodes']:,} meeting points joined by "
        f"{c['branches']:,} separate segments, each drawn here in its own shade with the "
        "meeting points as white circles.",
        "This is the same kind of description as a road map — junctions, and the "
        "stretches of road between them. Almost every meeting point has exactly three arms "
        f"({c['degree_histogram'].get('3', 0):,} of them); only "
        f"{c['degree_histogram'].get('4', 0)} have four. A crack splits in two at a time.",
    ], d7, scalebar_um=20)
    pdf.savefig(fig); plt.close(fig)

    # ======================================= page 4: steps 8-10, the grains and the rule
    fig = plt.figure(figsize=PAGE)
    pagetop(fig, "Part two: through the grains, or between them?",
            "The actual measurement, and the rule it turns on.")
    t = 0.895
    gr = F["grains"]

    def d8(ax):
        g = A["grains"]
        rng = np.random.default_rng(7)
        lut = rng.random((int(g.max()) + 2, 3)) * 0.6 + 0.35
        lut[0] = (0.12, 0.12, 0.14)
        ax.imshow(lut[g], interpolation="nearest")
    t = block(fig, t, 8, "Dividing the metal into grains", [
        "Grain boundaries show up as faint lines where the brightness changes. The software "
        "follows those changes and fills in each enclosed patch, giving every grain its own "
        "shade. The dark region is the crack itself, which is not metal and belongs to no "
        "grain.",
        f"On this frame that gives {gr['n_grains']:,} grains with a typical width of "
        f"{gr['median_grain_diameter_um']:.2f} micrometres — roughly one-twelfth the "
        "width of a human hair. This partition is a judgement, not a fact: asking for "
        "coarser or finer grains changes it, which is why the measurement below is repeated "
        "at three different settings.",
    ], d8, scalebar_um=20)

    def d9(ax):
        # Show the SAMPLING GEOMETRY, not just a scatter: for a handful of centreline
        # points, the point itself and a line out to each of its two flank samples.
        rgb = np.dstack([0.55 + 0.45 * img] * 3)
        rgb[A["crack"]] = (0.74, 0.79, 0.88)
        rgb[fat(A["skel"], 1)] = (0.10, 0.18, 0.42)
        ax.imshow(rgb, interpolation="nearest")
        ys, xs = A["fys"], A["fxs"]
        dec, same = A["fdec"], A["fsame"]
        dt = ndi.distance_transform_edt(A["crack"])
        sel = np.where((ys >= CROP[0]) & (ys < CROP[0] + CROP[2])
                       & (xs >= CROP[1]) & (xs < CROP[1] + CROP[2]) & dec)[0]
        if len(sel):
            step = max(1, len(sel) // 14)
            for i in sel[::step]:
                y, x = int(ys[i] - CROP[0]), int(xs[i] - CROP[1])
                if not (0 <= y < CROP[2] and 0 <= x < CROP[2]):
                    continue
                # the local wall distance sets how far out the two samples sit
                r = float(dt[y, x]) + F["standoff_px"]
                gy, gx = np.gradient(ndi.gaussian_filter(dt.astype(float), 3))
                ny, nx = gy[y, x], gx[y, x]
                nn = float(np.hypot(ny, nx)) or 1.0
                ny, nx = ny / nn, nx / nn
                col = GREEN if not same[i] else ORANGE
                for sgn in (+1, -1):
                    ax.plot([x, x + sgn * nx * r], [y, y + sgn * ny * r], "-",
                            color=col, lw=1.6, alpha=0.95)
                    ax.plot([x + sgn * nx * r], [y + sgn * ny * r], "o", color=col,
                            ms=7.0, mec="white", mew=0.9)
                ax.plot([x], [y], "o", color="white", ms=4.6, mec="black", mew=0.9)
        ax.set_xlim(0, CROP[2]); ax.set_ylim(CROP[2], 0)
    t = block(fig, t, 9, "Looking left and right at every point", [
        "Here is the measurement itself. Take one point on the crack's centre line. Step "
        "outwards to the LEFT until you are past the crack wall, plus a small margin, and "
        "note which grain you landed in. Then do the same to the RIGHT.",
        f"The margin is {F['standoff_px']} dots, about "
        f"{F['standoff_px'] * NM:.0f} nanometres — just enough to clear the wall "
        "without stepping into the next grain. Every point on the line gets two answers: "
        "the grain on this side, and the grain on that side.",
    ], d9, scalebar_um=20)

    fl = F["flank"]
    def d10(ax):
        ax.axis("off")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        rows = [("both sides the SAME grain", ORANGE,
                 "the crack cut THROUGH a grain", "TRANSGRANULAR"),
                ("the two sides are DIFFERENT grains", GREEN,
                 "it ran along the join BETWEEN two", "INTERGRANULAR"),
                ("one side unreadable", "#9a9a9a",
                 "no answer; the point is discarded", "UNDECIDABLE")]
        for i, (lead, col, mean, name) in enumerate(rows):
            yy = 0.84 - i * 0.30
            ax.add_patch(Rectangle((0.04, yy - 0.17), 0.92, 0.22, facecolor="white",
                                   edgecolor=col, lw=1.4))
            ax.plot(0.11, yy - 0.06, "o", color=col, ms=9)
            ax.text(0.18, yy - 0.015, lead, fontsize=8.4, color=INK, va="center")
            ax.text(0.18, yy - 0.075, mean, fontsize=8.0, color=MUT, va="center")
            ax.text(0.18, yy - 0.130, name, fontsize=8.4, color=col, va="center",
                    fontweight="bold")
    t = block(fig, t, 10, "The rule", [
        "If both sides are the same grain, the crack went through the middle of that grain. "
        "If they are two different grains, the crack ran along the join between them. If "
        "either side lands back inside the crack, or in a patch the software could not "
        "assign, the point gives no answer and is thrown away.",
        f"On this frame {fl['decidable_pct']:.1f}% of the centre line could be answered at "
        f"all, and of those points {fl['different_grain_pct_of_decidable']:.1f}% had "
        "different grains on the two sides.",
    ], d10, scalebar_um=None)
    pdf.savefig(fig); plt.close(fig)

    # ================================================= page 5: thresholds and controls
    fig = plt.figure(figsize=PAGE)
    pagetop(fig, "Every threshold, and the controls that decide whether to believe it",
            "A measurement is only as good as the comparison it is read against.")
    ctl = F["controls"]
    rows = [
        ("What counts as a meeting point", "three or more arms",
         "two arms is a bend in one path, not a split"),
        ("How long an arm must be", "longer than the crack is wide there",
         "a shorter arm has no room to be a real branch"),
        ("How far out to look for a grain",
         f"past the wall, plus {F['standoff_px']} dots ({F['standoff_px'] * NM:.0f} nm)",
         "far enough to clear the wall, near enough to stay in the adjacent grain"),
        ("Same grain or different", "exact identity, no tolerance",
         "two grains either are the same patch or they are not"),
        ("How much of the crack must be answerable",
         "at least half, or the result is withheld",
         f"here only {fl['decidable_pct']:.0f}% could be answered"),
        ("How far apart the controls must sit",
         "at least 50 percentage points",
         f"here {F['verdict']['resolution_pp']:.0f} points"),
    ]
    ax = fig.add_axes([0.07, 0.575, 0.86, 0.315]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.text(0.0, 0.97, "The thresholds, in one place", fontsize=10.6,
            fontweight="bold", color=INK, va="top")
    for i, (a_, b_, c_) in enumerate(rows):
        yy = 0.83 - i * 0.142
        ax.add_artist(plt.Line2D([0, 1], [yy + 0.055, yy + 0.055], color=RULE, lw=0.7))
        ax.text(0.0, yy, a_, fontsize=8.6, color=INK, va="top")
        ax.text(0.40, yy, b_, fontsize=8.6, color=BLUE, va="top", fontweight="bold")
        ax.text(0.40, yy - 0.050, c_, fontsize=7.8, color=MUT, va="top")

    ax2 = fig.add_axes([0.26, 0.300, 0.40, 0.205])
    names = ["a path built to FOLLOW\ngrain boundaries", "the crack itself",
             "a path placed AWAY from\nboundaries", "the grain map slid off\nthe crack"]
    key = f"{F['stem']}|{F['grains']['median_grain_diameter_um']:.2f}"
    DEC = NULL.get(key, {})
    shifted = DEC.get("shifted_mean_pct")
    vals = [ctl["positive_control"], ctl["real_intergranular_pct"],
            ctl["negative_control"], shifted if shifted is not None else np.nan]
    cols = [GREEN, BLUE, ORANGE, MUT]
    y = np.arange(len(vals))[::-1]
    ax2.barh(y, vals, 0.6, color=cols, edgecolor=INK, lw=0.6)
    for yy, v in zip(y, vals):
        if np.isfinite(v):
            ax2.text(v + 1.5, yy, f"{v:.1f}%", va="center", fontsize=8.4, color=INK)
    ax2.set_yticks(y, names, fontsize=8.2)
    ax2.set_xlim(0, 108)
    ax2.set_xlabel("reads 'different grains either side'", fontsize=8.4)
    ax2.tick_params(labelsize=8)
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)

    fig.text(0.70, 0.498, textwrap.fill(
        "Why the controls come first. The crack reads "
        f"{ctl['real_intergranular_pct']:.1f}%. On its own that number means nothing, "
        "because the method might return it for almost any path. So the same measurement "
        "is run on paths whose answer is known in advance.", 29),
        fontsize=8.3, color=INK, va="top", linespacing=1.5)

    fig.text(0.07, 0.238, textwrap.fill(
        "A path deliberately built to follow grain boundaries should come back near 100%, "
        f"and it does: {ctl['positive_control']:.1f}%. A path placed as far from boundaries "
        f"as its own shape allows should come back low: {ctl['negative_control']:.1f}%. "
        "Those two are far enough apart that the instrument can tell the cases apart at "
        "all. The fourth bar is the one that matters most: the grain map is slid sideways "
        "and wrapped around, which keeps every grain exactly the same size and shape but "
        "destroys any relationship with the crack. Whatever the crack scores against that "
        "is the score a path with no preference at all would get.", 108),
        fontsize=8.8, color=INK, va="top", linespacing=1.5)
    fig.text(0.07, 0.125, textwrap.fill(
        "Two cautions about this chart. The first three bars and the fourth are counted "
        "over slightly different sets of points \u2014 the first three over the points the "
        "software could answer with the real grain map, the fourth over the points that are "
        "answerable from the crack's shape alone, which is the stricter and fairer basis "
        "and the one the next page uses. They should not be read off against each other to "
        "the last decimal. And by the fifth threshold above this result would be WITHHELD: "
        f"only {fl['decidable_pct']:.0f}% of the crack could be answered, against a "
        "requirement of half. What follows is therefore reported as a measurement with a "
        "stated limitation, not as a settled figure for this material.", 108),
        fontsize=8.3, color=MUT, va="top", linespacing=1.5)
    pdf.savefig(fig); plt.close(fig)

    # ===================================================== page 6: what it came out as
    fig = plt.figure(figsize=PAGE)
    pagetop(fig, "What the measurement says, and the two mistakes on the way",
            "The result, the control it is read against, and why the answer moved three "
            "times before it settled.")
    rows = sorted(NULL.values(), key=lambda r: (r["frame"], r["grain_um"]))
    ax = fig.add_axes([0.16, 0.635, 0.48, 0.250])
    y = np.arange(len(rows))[::-1]
    ax.barh(y + 0.19, [r["real_pct"] for r in rows], 0.36, color=BLUE,
            edgecolor=INK, lw=0.5, label="the crack")
    ax.barh(y - 0.19, [r["shifted_mean_pct"] for r in rows], 0.36, color=MUT,
            edgecolor=INK, lw=0.5, label="grain map slid off the crack")
    for i, r in zip(y, rows):
        lo = min(b["shifted_pct"] for b in r["bins"]) if r["bins"] else r["shifted_mean_pct"]
        ax.errorbar([r["shifted_mean_pct"]], [i - 0.19],
                    xerr=[[2 * r["shifted_sd"]], [2 * r["shifted_sd"]]], fmt="none",
                    ecolor=INK, elinewidth=0.9, capsize=2.5)
    ax.set_yticks(y, [f"{r['frame'][-6:]}\ngrains {r['grain_um']:.1f} \u00b5m"
                      for r in rows], fontsize=7.6)
    ax.set_xlabel("reads 'different grains either side' (%)", fontsize=8.4)
    ax.set_xlim(0, 75)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=7.8, loc="lower right", frameon=False)
    for sname in ("top", "right"):
        ax.spines[sname].set_visible(False)
    fig.text(0.68, 0.878, textwrap.fill(
        "Six measurements: two images, three settings of the grain-size knob each. The "
        "crack is 2.3 to 4.1 times its own comparison every time. The bars either side of "
        "the grey are two standard deviations over 48 slides of the map.", 29),
        fontsize=8.0, color=INK, va="top", linespacing=1.5)

    fig.text(0.07, 0.578, "The finding", fontsize=10.6, fontweight="bold", color=INK)
    fig.text(0.07, 0.542, textwrap.fill(
        "This crack ran along grain boundaries far more than a path of its own shape laid "
        "over unrelated metal would. In every one of the six measurements the crack's "
        "reading falls completely outside the range of all 48 comparison slides \u2014 at "
        "the coarsest grain setting the slides span 5.7 to 10.1 per cent and the crack "
        "reads 29.9 per cent, twenty points clear of the furthest one. That is as strong as "
        "this kind of test can be made on a single image.", 108),
        fontsize=8.8, color=INK, va="top", linespacing=1.5)

    fig.text(0.07, 0.425, "The catch, which is as important as the finding",
             fontsize=10.6, fontweight="bold", color=INK)
    fig.text(0.07, 0.402, textwrap.fill(
        "The size of the effect depends on how WIDE the crack is where you measure it. A "
        "narrow crack's two flanks sit close together and usually fall in the same grain; a "
        "wide crack's flanks are pushed far apart and fall in different grains whatever "
        "metal lies underneath. So part of any such measurement is geometry rather than "
        "metallurgy. Split by crack opening divided by grain width, the gap between the "
        "crack and its comparison runs from about +8 points where the crack is thinnest to "
        "+50 points where it is a third of a grain wide, and then closes again as the "
        "comparison itself approaches certainty. The effect is still clearly present in the "
        "thinnest band, where geometry explains least \u2014 which is why it survives. But "
        "a single headline percentage, quoted without the crack opening beside it, is not "
        "an interpretable number.", 108),
        fontsize=8.8, color=INK, va="top", linespacing=1.5)

    fig.text(0.07, 0.205, "Two mistakes found while checking this",
             fontsize=10.6, fontweight="bold", color=INK)
    fig.text(0.07, 0.182, textwrap.fill(
        "First, the comparison was not sliding the map at all. It moved the sampling "
        "positions and then pushed any that fell outside the picture back to the nearest "
        "edge, so on a typical slide between 81 and 99 per cent of the comparison was read "
        "from a single row at the border. Second, and larger, the comparison was being "
        "scored on a different set of points from the crack: it allowed points lying inside "
        "the crack, where the two flanks are furthest apart and so differ most often, which "
        "is the geometry above leaking into the thing meant to control for it. With both "
        "corrected the answer reversed, from 'no preference for boundaries' to a factor of "
        "two to four. Every number on this page was recomputed afterwards.", 108),
        fontsize=8.8, color=MUT, va="top", linespacing=1.5)
    pdf.savefig(fig); plt.close(fig)

print("wrote", pdf_path)
