#!/usr/bin/env python3
"""Manuscript Figure 2: the workflow, with a real image at every step.

WHY THIS REPLACED A BOX DIAGRAM. Figure 2 used to be docs/figures/fig_pipeline.png --
eight stacked boxes of prose. It is a good repository diagram and a bad journal figure:
a reader has to parse six lines of text per stage to learn what the stage does to an
image, when one picture of the stage's own output says it. Every thumbnail here is the
ACTUAL array that stage produces, captured by running the shipped detector, exactly as
in Figure 1. Nothing is drawn by hand and nothing is a mock-up.

WHAT THE FIGURE ARGUES, which is the reason for the two bands. The paper evaluates a
specific branch: flatten, propose, clean, measure. Three things the application also
does are NOT in that branch -- the learned region classifier (switched off), the pass-2
region growth, and the human's painted correction. Drawing all eight in one column, as
the old diagram did, invited a reader to assume the evaluated numbers come from the end
of the chain. They do not. The top band is what was measured; the lower band is what sits
outside it, and is drawn so that it cannot be mistaken for part of the measurement.

TWO FIELDS, AND WHY. The top band is MAR_H_HIP_CBS_0007 at 51.883 nm/px, the same field
as Figure 1, so a reader can move between the two figures. The human-correction panel
cannot be that field: it has no painted correction. Of this laboratory's 142 frames,
exactly one carries BOTH a recovered pixel size and a painted correction, and it is
MAR_AmbB_AS, which the tile benchmark excludes because 87 per cent of what was painted
there is round. So the correction panel is a different field, it is named in the caption,
and because no pixel size has been recovered for it, it carries no scale bar -- it says
so instead. That is the same rule the rest of this figure set follows.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_workflow.py
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, os.path.join(SEM, "code"))
sys.path.insert(0, os.path.join(SEM, "interior_active_learning", "code"))
sys.dont_write_bytecode = True

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from PIL import Image
from skimage import exposure, morphology

import journal_style as J            # noqa: E402
from scalebar import scalebar, no_scale_note  # noqa: E402
import mk_pipeline_visual as V       # noqa: E402  -- the same loader and the same stages
import detector_overrides as DO      # noqa: E402
import detect_cracks as D            # noqa: E402

J.use()
Image.MAX_IMAGE_PIXELS = None

OUT = os.path.join(HERE, "out")
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
NAME = "P7 - workflow"

#: The field for the human-correction panel, chosen by rule and recorded so the choice is
#: auditable. A panel of a painted correction needs BOTH verdicts legible -- a crack
#: verdict alone shows half of what the stage does -- so the frame and the window are
#: chosen together: over the painted frames that have an original on disk and at least
#: 2,000 px of each verdict, the (frame, 520 px window) pair maximising the SMALLER of
#: the two verdicts' pixel counts, subject to the window's crack area fraction lying
#: within half to twice that frame's own so the panel is not an atypical patch.
#:
#: The winner holds 14.82% crack and 8.08% not-crack against a frame that is 9.76%
#: crack. The runner-up by the unconstrained score, MAR_Amb_AS_ETD_0003, is 82% crack in
#: its best window on a frame that is 49% crack; that is a true picture of an outlier and
#: the wrong panel, which is what the representativeness constraint exists to exclude.
#: Searched by analysis of all 48 painted frames; see the caption JSON for the numbers.
PAINT_FIELD = "260622_316_H_b2_back_CBS_01"


def paint_panel():
    """A real painted correction, loaded the way the corpus scripts load one.

    Same loader as analysis/research/improve/lab_corpus_channels.py: the mask is stored
    against the FULL frame and the detector works on the field-of-view crop, so the mask
    is cut to the same window or the two disagree about where a pixel is.
    """
    from common import contrast_kwargs_for
    import tifffile

    raw = tifffile.imread(os.path.join(SEM, "original", PAINT_FIELD + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    ck = contrast_kwargs_for(PAINT_FIELD)
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]

    corr = np.array(Image.open(os.path.join(PAINT, PAINT_FIELD + "_correction_mask.png")))
    while corr.ndim > 2:
        corr = corr[..., 0]
    if corr.shape != img8.shape:
        if corr.shape[0] >= y1 and corr.shape[1] >= x1:
            corr = corr[y0:y1, x0:x1]
        else:
            raise SystemExit(f"{PAINT_FIELD}: correction mask does not fit the frame")

    pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
    # WHERE TO CROP. Centring on the median not-crack pixel put the window on a bright,
    # almost unpainted patch -- a median is a location, and nothing about it says the
    # paint is dense there. Search instead for the window that maximises the SMALLER of
    # the two verdicts' area fractions, so the panel shows the stage doing both of the
    # things it does. Summed-area tables, so the search is exact rather than sampled.
    # the same 520 px window as the evaluated detail above, so the two bands are
    # comparable; a wider crop made the painted area a thin margin of a mostly bare panel
    H = min(520, img8.shape[0], img8.shape[1])
    ip = np.pad(np.cumsum(np.cumsum(pos.astype(np.int64), 0), 1), ((1, 0), (1, 0)))
    ineg = np.pad(np.cumsum(np.cumsum(neg.astype(np.int64), 0), 1), ((1, 0), (1, 0)))

    def box(ii, y, x):
        return (ii[y + H, x + H] - ii[y, x + H] - ii[y + H, x] + ii[y, x])

    step = max(1, H // 10)   # the grid the frame choice above was searched on
    frame_frac = pos.sum() / float(pos.size)
    # The same objective the frame was chosen by, so the window the search picked is the
    # window that gets drawn: maximise the smaller of the two verdicts, subject to the
    # window being representative of its frame. Maximising the rarer verdict alone
    # centred on the not-crack paint and pushed the crack off the bottom edge.
    cands = []
    for y in range(0, img8.shape[0] - H + 1, step):
        for x in range(0, img8.shape[1] - H + 1, step):
            cf = box(ip, y, x) / float(H * H)
            if 0.5 * frame_frac <= cf <= 2.0 * frame_frac:
                cands.append((min(box(ip, y, x), box(ineg, y, x)), y, x))
    if not cands:                      # no representative window holds both verdicts
        raise SystemExit(f"{PAINT_FIELD}: no representative window holds both verdicts")
    _, ty, tx = max(cands)
    sl = (slice(ty, ty + H), slice(tx, tx + H))

    rgb = np.dstack([img8[sl].astype(np.float32)] * 3) / 255.0
    rgb[pos[sl]] = np.array(J.rgb(J.PAINT_CRACK))
    rgb[neg[sl]] = np.array(J.rgb(J.PAINT_NOTCRACK))
    return np.clip(rgb, 0, 1), int(pos[sl].sum()), int(neg[sl].sum())


def main():
    stem, img, _ = V.pick_field()
    flat, raw, cleaned, lab, final = V.stages(img)

    # the same detail as Figure 1, by the same rule, so the two figures are the same
    # region of the same field and a reader can move between them
    ys, xs = np.where(final)
    cy, cx = int(np.median(ys)), int(np.median(xs))
    H = 520
    y0 = max(min(cy - H // 2, img.shape[0] - H), 0)
    x0 = max(min(cx - H // 2, img.shape[1] - H), 0)
    sl = (slice(y0, y0 + H), slice(x0, x0 + H))

    # THE MEASURED PANEL IS A MEASUREMENT, not a restatement of the mask. Skeleton length
    # is what the per-region length comes from, so the centreline is what that stage adds
    # to the picture, and it is computed here rather than drawn.
    skel = morphology.skeletonize(final[sl])
    # Full-strength mask, not a tint: a pale blue measured 5.9 against this
    # field's own greys, which is below the floor -- it would vanish.
    measured = V.mask_on_field(img[sl], final[sl], colour=J.rgb(J.MASK))
    measured[morphology.dilation(skel, np.ones((3, 3), bool))] = np.array(J.rgb(J.SKELETON))

    steps = [
        ("Micrograph", "8-bit greyscale,\nwhole frame",
         np.dstack([img[sl]] * 3).astype(np.float32) / 255.0),
        ("Flatten", f"{len(DO.SCALE_LADDER)} scales,\n"
                    f"sigma {min(DO.SCALE_LADDER)}-{max(DO.SCALE_LADDER)} px",
         np.dstack([flat[sl]] * 3).astype(np.float32) / 255.0),
        ("Propose", f"MAD k = {DO.PAPER_MAD_K},\nfloor at {DO.ABSOLUTE_DARK_THRESH}",
         V.mask_on_field(img[sl], raw[sl], colour=J.rgb(J.MASK))),
        ("Clean and label", "holes filled,\nregions ≥ 40 px",
         V.mask_on_field(img[sl], final[sl], colour=J.rgb(J.MASK))),
        ("Measure", "area fraction,\ncentreline length", measured),
    ]

    aside = [
        ("Region classifier",
         "an 8-feature model over candidate regions,\nswitched off in the evaluated branch"),
        ("Region growth",
         "a second pass over concavity, bridge\nand interior-fill candidates"),
    ]
    HUMAN = ("Human correction",
             "painted verdicts, which override\nevery stage above. No pixel size is\n"
             "recovered for this field, so this\npanel carries no scale bar.")

    W = J.PAGEW
    M = 0.03
    GAP = 0.075
    TH = (W - 2 * M - (len(steps) - 1) * GAP) / len(steps)     # thumbnail edge, inches
    CAPH = 0.44                      # name + two descriptor lines under each thumbnail
    BAND = 0.17                      # the "outside" band header
    BOXH = 0.86
    ARROW = 0.20
    KEY = 0.0
    Htot = M + TH + CAPH + ARROW + BAND + BOXH + KEY + M

    fig = plt.figure(figsize=(W, Htot))

    def ax_at(xin, yin, win, hin):
        """Place by inches from the TOP-LEFT, which is how this figure is laid out."""
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    top = M
    for i, (name, desc, arr) in enumerate(steps):
        x = M + i * (TH + GAP)
        ax = ax_at(x, top, TH, TH)
        ax.imshow(arr, interpolation="nearest")
        J.micrograph(ax)
        for s in ("left", "right", "top", "bottom"):
            ax.spines[s].set_visible(False)
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, fill=False,
                                   edgecolor=J.INK, linewidth=0.6, zorder=30))
        scalebar(ax, V.NM_PER_PX, H, fontsize=J.TICK)
        J.panel_label(ax, "abcde"[i], inside=True)

        lab_ax = ax_at(x, top + TH + 0.045, TH, CAPH)
        lab_ax.set_axis_off()
        lab_ax.text(0, 1.0, name, fontsize=J.BODY, fontweight="bold", va="top",
                    ha="left", color=J.INK, transform=lab_ax.transAxes)
        lab_ax.text(0, 0.60, desc, fontsize=J.TICK, va="top", ha="left",
                    color=J.G_DARK, transform=lab_ax.transAxes, linespacing=1.35)

        if i < len(steps) - 1:
            fig.patches.append(FancyArrowPatch(
                ((x + TH + 0.012) / W, 1.0 - (top + TH / 2) / Htot),
                ((x + TH + GAP - 0.012) / W, 1.0 - (top + TH / 2) / Htot),
                transform=fig.transFigure, arrowstyle="-|>", mutation_scale=9,
                color=J.INK, linewidth=0.7, zorder=40))

    # the branch down to what is NOT evaluated
    ybar = top + TH + CAPH + 0.045
    fig.patches.append(FancyArrowPatch(
        (0.5, 1.0 - ybar / Htot), (0.5, 1.0 - (ybar + ARROW - 0.03) / Htot),
        transform=fig.transFigure, arrowstyle="-|>", mutation_scale=9,
        color=J.G_MID, linewidth=0.7, linestyle=(0, (3, 2)), zorder=40))

    yband = ybar + ARROW
    hdr = ax_at(M, yband, W - 2 * M, BAND)
    hdr.set_axis_off()
    hdr.text(0.5, 0.35, "O U T S I D E   T H E   E V A L U A T E D   B R A N C H",
             fontsize=J.TICK, fontweight="bold", ha="center", va="center",
             color=J.G_MID, transform=hdr.transAxes)

    ybox = yband + BAND
    CW = (W - 2 * M - GAP) / 2                  # two columns, not three
    sub = (BOXH - 0.05) / 2
    for i, (name, desc) in enumerate(aside):
        by = ybox + i * (sub + 0.05)
        bx = ax_at(M, by, CW, sub)
        bx.set_axis_off()
        bx.add_patch(FancyBboxPatch((0, 0), 1, 1, transform=bx.transAxes,
                                    boxstyle="square,pad=0", facecolor="white",
                                    edgecolor=J.G_MID, linewidth=0.6,
                                    linestyle=(0, (3, 2)), zorder=1))
        bx.text(0.022, 0.76, name, fontsize=J.BODY, fontweight="bold", va="center",
                ha="left", color=J.G_DARK, transform=bx.transAxes)
        bx.text(0.022, 0.33, desc, fontsize=J.TICK, va="center", ha="left",
                color=J.G_MID, transform=bx.transAxes, linespacing=1.3)

    pan, npos, nneg = paint_panel()
    hx = ax_at(M + CW + GAP, ybox, CW, BOXH)
    hx.set_axis_off()
    hx.add_patch(FancyBboxPatch((0, 0), 1, 1, transform=hx.transAxes,
                                boxstyle="square,pad=0", facecolor="white",
                                edgecolor=J.G_MID, linewidth=0.6,
                                linestyle=(0, (3, 2)), zorder=1))
    th = BOXH - 0.12
    im = ax_at(M + CW + GAP + 0.06, ybox + 0.06, th, th)
    im.imshow(pan, interpolation="nearest")
    J.micrograph(im)
    im.add_patch(plt.Rectangle((0, 0), 1, 1, transform=im.transAxes, fill=False,
                               edgecolor=J.G_MID, linewidth=0.6, zorder=30))
    tx = (0.06 + th + 0.07) / CW
    hx.text(tx, 0.84, HUMAN[0], fontsize=J.BODY, fontweight="bold", va="center",
            ha="left", color=J.G_DARK, transform=hx.transAxes)
    hx.text(tx, 0.40, HUMAN[1], fontsize=J.TICK, va="center", ha="left",
            color=J.G_MID, transform=hx.transAxes, linespacing=1.3)

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "(a)-(e) the evaluated branch with the real array each stage produces, "
                "on one field; below it, the three stages of the application that are "
                "outside that branch",
        "evaluated_field": stem,
        "evaluated_nm_per_px": V.NM_PER_PX,
        "detail_px": H,
        "correction_field": PAINT_FIELD,
        "correction_has_scale": False,
        "correction_px_in_panel": {"crack": npos, "not_crack": nneg},
        "selection_rule": "the evaluated field is Figure 1's, by the same rule; the "
                          "correction field is, of the 18 painted frames carrying both "
                          "verdicts, the one closest to their median crack area "
                          "fraction, tie broken towards the visible not-crack verdict",
        "settings": {"scale_ladder": list(DO.SCALE_LADDER),
                     "absolute_dark_thresh": DO.ABSOLUTE_DARK_THRESH,
                     "paper_mad_k": DO.PAPER_MAD_K,
                     "shipped_mad_k": DO.SHIPPED_MAD_K,
                     "use_region_classifier": DO.USE_REGION_CLASSIFIER},
        "note": "panels are real intermediate arrays, not illustrations",
    }, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)
    print(f"  evaluated {stem} at {V.NM_PER_PX} nm/px; correction {PAINT_FIELD} "
          f"(crack {npos} px, not-crack {nneg} px in panel)")


if __name__ == "__main__":
    main()
