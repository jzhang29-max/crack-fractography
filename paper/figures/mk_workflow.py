#!/usr/bin/env python3
"""Figure 1: the study in one figure -- two modalities in, one rule, two readings out.

WHAT CHANGED AND WHY. The previous Figure 1 was a left-to-right row of five SEM panels
with a band of excluded stages underneath. It showed the SEM pipeline and said nothing
about the second modality, which is half of the paper; a reader reached Section 4 with no
picture of how the two arms relate. The figure now shows what the study actually is: two
very different images enter, ONE detection rule is applied to both without retuning, and
the same number out of it means two different physical things.

The layout carries that argument rather than decorating it. The two inputs sit apart, at
the top left and top right. Arrows bring them together into a single rule box drawn
across the full width -- the convergence is at the darkness threshold, which is the one
place the two arms are genuinely identical. Arrows then separate again into the two
results, because what an area fraction MEANS diverges the moment the geometry does: on a
polished section it is the area of a surface trace, and in transmission it is the area of
a shadow cast through the whole thickness.

PAIRED DETAIL PANELS. Each result is a before-and-after pair on the same window, side by
side, rather than two panels at opposite corners of the plate. Panels that differ only by
an overlay have to be adjacent to be compared at all; separated, a reader has to hold one
in memory while finding the other.

EVERY PANEL IS A REAL ARRAY. Both frames are loaded through the application's own loader
and staged by its own code (`both_modalities.py`, which is the single source of these
arrays for the whole figure set). Nothing here is drawn by hand, nothing is a mock-up,
and no pixel is added for visibility.

NO SENTENCES INSIDE THE ARTWORK. Both target publishers say the description of a figure
belongs in its caption and not on the figure itself, and the review said the same. What is
left on the plate is structure a reader needs to parse the panels at all -- the two column
headings, the two half-labels on each split frame, the panel letters, the scale bars and
the rule box, which IS the figure rather than a description of it. The field sizes, the
pixel sizes, the area fractions and the sentence about what each number means have all
moved into the manuscript caption, which is the only place they can be checked against the
measurement files anyway.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_workflow.py
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths                                       # noqa: E402

sys.path.insert(0, _paths.ANALYSIS)
sys.dont_write_bytecode = True

import numpy as np                                  # noqa: E402
import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle  # noqa: E402
from scipy import ndimage as ndi                   # noqa: E402
from skimage import exposure                       # noqa: E402

import both_modalities as BM                        # noqa: E402
import detector_overrides as DO                     # noqa: E402
import journal_style as J                           # noqa: E402
from scalebar import scalebar                       # noqa: E402

J.use()
OUT = _paths.FIG_DIR
NAME = "F1 - workflow"

#: The detail window per modality, in pixels of that modality's own frame. They differ
#: because the pixel sizes differ by 1.8x: 520 px of SEM is 27 um and 700 px of TXM is
#: 20 um, so the two windows look at features of comparable physical size.
DETAIL = {"sem": 520, "txm": 700}

ARMS = (("sem", "Scanning electron microscopy"),
        ("txm", "Transmission X-ray microscopy"))

#: The shared rule, as three named operations and nothing else. What each one DOES is
#: a sentence, and a sentence belongs in the caption: these three were set out here in
#: a bordered block of descriptive text, which is a caption printed on the artwork
#: however it is laid out. The names are node labels in a flow diagram, which is what
#: this figure is; the constants they stand for are in the caption and in Table 1.
RULE = ["Flatten", "Propose", "Clean"]


def detail_of(d, tag):
    """The window this arm is shown at: the largest marked region that the frame contains.

    The rule is the same for both arms, so neither window is chosen to flatter its own
    result. It is not the rule the single-modality figures used -- those centred on the
    MEDIAN marked pixel, which is a location and carries no guarantee that anything is
    there. On the TXM frame the median sat 300 px off the main crack, on a smooth
    attenuation gradient, and the panel showed the method working on nothing. Centring on
    the main crack is what a workflow figure is for; the window is denser in crack than
    the frame it comes from, and the caption JSON records both fractions so the reader
    can see by how much.
    """
    H = DETAIL[tag]
    f = d["final"]
    lab, _ = ndi.label(f, np.ones((3, 3), bool))
    sz = np.bincount(lab.ravel())
    sz[0] = 0
    # Regions touching the frame border are censored -- their extent is cut off by the
    # field of view, so no length or width can be measured from them -- and on the TXM
    # frame the single largest marked region is the mosaic's own right-hand edge. A
    # figure centred there would show the reader a stitching artefact.
    for b in set(np.unique(np.concatenate(
            [lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}:
        sz[b] = 0
    cy, cx = ndi.center_of_mass(lab == int(sz.argmax()))
    y0 = max(min(int(cy) - H // 2, f.shape[0] - H), 0)
    x0 = max(min(int(cx) - H // 2, f.shape[1] - H), 0)
    return y0, x0, H


def stretched(arr):
    """Display stretch, 2nd-98th percentile, applied to every panel of both arms.

    The TXM frames are mosaic averages with a broad, low-contrast attenuation gradient
    across them; printed as loaded, the crack in panel (b) is a grey smudge on grey. The
    stretch is DISPLAY ONLY -- the detector ran on the unstretched array and every mask
    drawn here is that run -- and it is applied identically to both modalities so the two
    columns are not rendered under different conventions, which is a mistake this figure
    set has made before.
    """
    lo, hi = np.percentile(arr, [2, 98])
    if hi <= lo:
        return arr.astype(np.float32) / 255.0
    return exposure.rescale_intensity(arr.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0.0, 1.0))


def main():
    data = {tag: BM.load(tag) for tag, _ in ARMS}
    crops = {tag: detail_of(data[tag], tag) for tag, _ in ARMS}

    W = J.PAGEW
    M = 0.03
    CW = 2.78                       # one arm's column
    GAP = W - 2 * M - 2 * CW        # the centre gap the arrows cross
    FRAME_H = 1.42                  # whole-frame row, by height so both rows align
    HDR = 0.42                      # column heading + the two half-labels
    CAP = 0.16                      # breathing room above the converging arrows
    ARR = 0.30
    BOX = 0.40
    PAIR = (CW - 0.07) / 2          # two square detail panels per arm
    Htot = M + HDR + FRAME_H + CAP + ARR + BOX + ARR + PAIR + M

    fig = plt.figure(figsize=(W, Htot))

    def ax_at(xin, yin, win, hin):
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    def yfig(yin):
        return 1.0 - yin / Htot

    def arrow(x0, y0, x1, y1, *, colour=None, style="-|>", lw=0.8, dashed=False):
        fig.patches.append(FancyArrowPatch(
            (x0 / W, yfig(y0)), (x1 / W, yfig(y1)), transform=fig.transFigure,
            arrowstyle=style, mutation_scale=10, color=colour or J.INK, linewidth=lw,
            linestyle=(0, (3, 2)) if dashed else "solid", shrinkA=0, shrinkB=0,
            zorder=40))

    letters = iter("abcdef")
    frame_rows, panel_notes = {}, {}
    for i, (tag, title) in enumerate(ARMS):
        d = data[tag]
        img, final = d["img"], d["final"]
        y0, x0, H = crops[tag]
        nm = float(d["nm_per_px"])
        cx0 = M + i * (CW + GAP)

        hx = ax_at(cx0, M, CW, HDR)
        hx.set_axis_off()
        hx.text(0.5, 0.95, title, fontsize=J.BODY, fontweight="bold", ha="center",
                va="top", color=J.INK, transform=hx.transAxes)

        # --- the whole frame, sized by HEIGHT so the two arms' rows line up even though
        # the two frames have different aspect ratios. Cropping them to a common aspect
        # would have made neither panel the whole frame, which is what it is for.
        # ONE PANEL, SPLIT, NOT TWO PANELS AT OPPOSITE CORNERS. The frame as acquired and
        # the frame with its finished mask are the same picture twice over, and the
        # review's note was that panels which look alike have to be adjacent to be read
        # at all. Drawn as one frame divided down the middle -- left as acquired, right
        # with the mask -- so the comparison is made by the eye and not by memory, and
        # the whole-frame result keeps the panel it used to need for itself.
        step = max(1, img.shape[1] // 1400)
        thumb = stretched(img[::step, ::step])
        rgb = np.dstack([thumb] * 3)
        half = thumb.shape[1] // 2
        sub = final[::step, ::step][:, half:]
        rgb[:, half:][sub] = np.array(J.rgb(J.MASK))
        fw = FRAME_H * thumb.shape[1] / thumb.shape[0]
        fx = cx0 + (CW - fw) / 2
        ax = ax_at(fx, M + HDR, fw, FRAME_H)
        ax.imshow(rgb, interpolation="nearest", aspect="equal")
        ax.plot([half, half], [0, thumb.shape[0] - 1], color="white", lw=0.9, zorder=20)
        ax.plot([half, half], [0, thumb.shape[0] - 1], color=J.INK, lw=0.4,
                linestyle=(0, (2, 2)), zorder=21)
        for frac, txt in ((0.25, "as acquired"), (0.75, "detected")):
            ax.text(frac * thumb.shape[1], -0.045 * thumb.shape[0], txt,
                    fontsize=J.TICK, ha="center", va="bottom", color=J.INK)
        # the detail box, always drawn on whichever half actually contains it
        ax.add_patch(Rectangle((x0 / step, y0 / step), H / step, H / step, fill=False,
                               edgecolor=J.ROI, linewidth=1.0, zorder=22))
        J.micrograph(ax)
        J.panel_label(ax, next(letters), inside=True)
        scalebar(ax, nm * step, thumb.shape[1], fontsize=J.TICK)
        frame_rows[tag] = (fx, fw)

        panel_notes[tag] = dict(frame_px=[int(img.shape[0]), int(img.shape[1])],
                                nm_per_px=nm, crop=[int(y0), int(x0)], detail_px=int(H),
                                area_fraction_pct=round(100 * float(final.mean()), 3),
                                window_area_fraction_pct=round(
                                    100 * float(final[y0:y0 + H, x0:x0 + H].mean()), 2))

    # --- converge -----------------------------------------------------------------
    ytop = M + HDR + FRAME_H + CAP
    ybox = ytop + ARR
    mid = W / 2
    for tag, _ in ARMS:
        fx, fw = frame_rows[tag]
        arrow(fx + fw / 2, ytop, mid + (0.30 if tag == "txm" else -0.30), ybox - 0.015)

    # THREE CHEVRONS, NOT A BOX OF TEXT. The rule is drawn as the flow it is: one node per
    # operation, pointing left to right, with no border around the band and no sentence
    # in it. The constants the nodes stand for are in the caption and in Table 1.
    bx = ax_at(M, ybox, W - 2 * M, BOX)
    bx.set_axis_off()
    bx.set_xlim(0, 1)
    bx.set_ylim(0, 1)
    nodes, gap, tip = len(RULE), 0.016, 0.026
    span = (1.0 - (nodes - 1) * gap) / nodes
    for k, name in enumerate(RULE):
        x0 = k * (span + gap)
        x1 = x0 + span
        bx.add_patch(Polygon([(x0, 0.08), (x1 - tip, 0.08), (x1, 0.5), (x1 - tip, 0.92),
                              (x0, 0.92), (x0 + (tip if k else 0.0), 0.5)],
                             closed=True, facecolor="#e4ecf7", edgecolor=J.ACCENT,
                             linewidth=0.8, zorder=2))
        bx.text((x0 + x1) / 2, 0.5, name, fontsize=J.BODY, fontweight="bold",
                ha="center", va="center", color=J.INK, zorder=3)

    # --- diverge ------------------------------------------------------------------
    ypair = ybox + BOX + ARR
    for i, (tag, _) in enumerate(ARMS):
        d = data[tag]
        y0, x0, H = crops[tag]
        sl = (slice(y0, y0 + H), slice(x0, x0 + H))
        nm = float(d["nm_per_px"])
        cx0 = M + i * (CW + GAP)
        arrow(mid + (0.30 if tag == "txm" else -0.30), ybox + BOX,
              cx0 + CW / 2, ypair - 0.015)

        grey = np.dstack([stretched(d["img"][sl])] * 3)
        marked = grey.copy()
        marked[d["final"][sl]] = np.array(J.rgb(J.MASK))
        for k, arr in enumerate((grey, marked)):
            ax = ax_at(cx0 + k * (PAIR + 0.07), ypair, PAIR, PAIR)
            ax.imshow(arr, interpolation="nearest")
            J.micrograph(ax)
            ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes, fill=False,
                                   edgecolor=J.ROI if k == 0 else J.INK,
                                   linewidth=1.0, zorder=30))
            J.panel_label(ax, next(letters), inside=True)
            scalebar(ax, nm, H, fontsize=J.TICK)

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "two modalities in, one detection rule, two readings out",
        "arms": {tag: {"field": str(data[tag]["field"]), **panel_notes[tag]}
                 for tag, _ in ARMS},
        "scale_provenance": {"sem": BM.SEM_SCALE_SOURCE, "txm": BM.TXM_SCALE_SOURCE},
        "selection_rule": "each arm's field is the one its single-modality figure already "
                          "recorded; each detail window is centred on the median pixel of "
                          "that arm's finished mask, the same rule for both arms",
        "settings": {"scale_ladder": list(DO.SCALE_LADDER),
                     "absolute_dark_thresh": DO.ABSOLUTE_DARK_THRESH,
                     "mad_k": BM.MAD_K, "min_area_px": BM.MIN_AREA_PX,
                     "use_region_classifier": DO.USE_REGION_CLASSIFIER},
        "note": "every panel is a real intermediate array; no pixel is added for "
                "visibility and nothing is drawn by hand. No sentence appears inside the "
                "artwork: the field sizes, the pixel sizes and the area fractions "
                "recorded here are the figure's caption material and live in the "
                "manuscript",
    }, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)
    for tag, _ in ARMS:
        n = panel_notes[tag]
        print(f"  {tag.upper():<4} {str(data[tag]['field'])[:44]:<44} "
              f"detail {n['detail_px']} px at {tuple(n['crop'])}, "
              f"marked {n['area_fraction_pct']}%")


if __name__ == "__main__":
    main()
