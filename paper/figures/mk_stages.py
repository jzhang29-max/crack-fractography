#!/usr/bin/env python3
"""Figure 3: the detection stages, both modalities, with the differences magnified.

WHAT THIS REPLACES, AND WHY. Two figures became one. The paper carried a seven-panel SEM
stage plate and, in Section 4, a seven-panel TXM stage plate drawn to the same recipe. In
both, four of the seven panels were visually indistinguishable at print size -- propose,
open, fill, area-filter differ by a few hundred pixels in a half-million-pixel window --
and the whole-frame micrograph and the whole-frame result sat at opposite corners of the
plate, so the one comparison a reader most wants to make was the one the layout made
hardest. A reviewer reading the two plates learns three facts and looks at fourteen
panels.

THE THREE THINGS THAT ACTUALLY DIFFER, one column each:

  as loaded                    the array the detector is given
  background removed           the array the darkness criterion is applied to
  proposed, cleaned, filtered  the mask that is scored

and the stages that LOOK the same are combined into the third column rather than given
panels of their own. What they removed is not thereby hidden: it is drawn, in a second
colour, inside a magnified inset, which is the only size at which it is visible at all.
The inset window is chosen by rule -- the position holding the most removed pixels -- not
by eye, and the rectangle on the main panel says where it came from.

BOTH MODALITIES IN ONE FIGURE, one row each, so the same three stages can be compared
across the two microscopies without turning a page. The two rows are at different pixel
sizes and the scale bars say so; the windows are chosen to cover a comparable physical
field.

Every panel is the real intermediate array from `both_modalities.py`, which is the one
place in the figure set that loads and stages these two fields. No pixel is added for
visibility: the removed pixels are shown at magnification instead of being dilated, which
is what an earlier draft of this plate did.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_stages.py
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
from matplotlib.patches import Rectangle          # noqa: E402
from scipy import ndimage as ndi                    # noqa: E402
from skimage import exposure                        # noqa: E402

import both_modalities as BM                        # noqa: E402
import detector_overrides as DO                     # noqa: E402
import journal_style as J                           # noqa: E402
from scalebar import scalebar                       # noqa: E402

J.use()
OUT = _paths.FIG_DIR
NAME = "F3 - detection stages, both modalities"

#: The window each row is shown at, in micrometres. NOT the same number for the two rows,
#: and the caption says both. The SEM value was 27 um when the illustrated field was one
#: whose cracks are a line one or two micrometres across. On the b2 field the paper now
#: draws from, the main crack is twenty to thirty micrometres across, so a 27 um window
#: is inside the crack whatever rule chooses it and both the micrograph and the mask come
#: out as flat blocks. 60 um shows that crack with the matrix on either side of it, which
#: is what a stage panel has to show. The TXM value is unchanged: that crack is a band a
#: few micrometres wide and the same 60 um field would reduce it to a smudge. Matching
#: the field of view between the two matters where their appearances are being compared,
#: which is Figure 2's job; here each row has to be legible on its own terms.
FOV_UM = {"sem": 60.0, "txm": 14.0}
#: The side of the magnified inset, as a fraction of that row's own field.
INSET_FRAC = 4.0 / 27.0
#: The colour the pixels that cleaning removed are drawn in. Red is this figure set's
#: annotation colour everywhere else, which is what it is doing here: it marks what a
#: stage did, over a mask that keeps its own blue.
REMOVED = J.ROI

ROWS = (("sem", "SEM"), ("txm", "TXM"))
COLS = ("as loaded", "background removed", "proposed, cleaned, filtered")


def stretch(a):
    """Display stretch, 2nd-98th percentile. Identical for both rows and every column."""
    lo, hi = np.percentile(a, [2, 98])
    if hi <= lo:
        return a.astype(np.float32) / 255.0
    return exposure.rescale_intensity(a.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0.0, 1.0))


#: THE WINDOW RULE, shared by Figures 1 and 3. Not "the most marked pixels": on a field
#: whose crack is wider than the window, the densest position is solid mask and the panel
#: shows no boundary at all. Capping the marked fraction does not fix it either -- the
#: maximiser then sits exactly at the cap, and on the b2 field that put the window on the
#: crack mouth with half the panel one flat colour. What a detection panel is FOR is the
#: line the detector drew, so the window is the one containing the most mask-BOUNDARY
#: pixels. A solid block has almost none, an empty region has none, and the maximiser is
#: therefore a window where mask meets matrix across the panel. No cap is needed.
def boundary_window(final, H):
    """Top-left corner of the H x H window holding the most mask-boundary pixels."""
    edge = final & ~ndi.binary_erosion(final, np.ones((3, 3), bool))
    ii = np.pad(np.cumsum(np.cumsum(edge.astype(np.int64), 0), 1), ((1, 0), (1, 0)))
    box = ii[H:, H:] - ii[:-H, H:] - ii[H:, :-H] + ii[:-H, :-H]
    if not box.size or box.max() <= 0:
        raise SystemExit(f"no {H} px window contains any mask boundary -- the field or "
                         f"the window size needs revisiting, not a silent fallback")
    y0, x0 = np.unravel_index(int(box.argmax()), box.shape)
    return int(y0), int(x0)


def window(d, um):
    """The position holding the most mask boundary -- Figure 1's rule exactly.

    The rule used to be "centred on the largest marked region the frame CONTAINS", with
    border-touching regions censored. On the b2 SEM field the paper is now drawn from
    that fails: the main crack runs out of both sides of the field, so the censor removes
    the object the figure exists to show. `boundary_window` above is the replacement and
    is the rule Figure 1 states -- the two figures say they share it, so they have to.
    """
    nm = float(d["nm_per_px"])
    f = d["final"]
    H = min(int(round(um * 1000.0 / nm)), f.shape[0], f.shape[1])
    y0, x0 = boundary_window(f, H)
    return (slice(int(y0), int(y0) + H), slice(int(x0), int(x0) + H)), H, nm


def densest(mask, side):
    """Top-left corner of the `side` x `side` window holding the most True pixels.

    Exact rather than sampled: a box sum over the summed-area table. The window is pulled
    inside the panel so the inset is a crop of what is shown and not of its surroundings.
    """
    ii = np.pad(np.cumsum(np.cumsum(mask.astype(np.int64), 0), 1), ((1, 0), (1, 0)))
    H, W = mask.shape
    s = min(side, H, W)
    box = (ii[s:, s:] - ii[:-s, s:] - ii[s:, :-s] + ii[:-s, :-s])
    y, x = np.unravel_index(int(box.argmax()), box.shape)
    return int(y), int(x), s, int(box[y, x])


def main():
    data = {tag: BM.load(tag) for tag, _ in ROWS}

    W = J.PAGEW
    M = 0.03
    LAB = 0.28                       # the row label strip on the left
    GAP = 0.055
    HDR = 0.24
    PAN = (W - 2 * M - LAB - 2 * GAP) / 3
    Htot = M + HDR + 2 * PAN + GAP + M

    fig = plt.figure(figsize=(W, Htot))

    def ax_at(xin, yin, win, hin):
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    for c, name in enumerate(COLS):
        hx = ax_at(M + LAB + c * (PAN + GAP), M, PAN, HDR)
        hx.set_axis_off()
        hx.text(0.5, 0.45, name, fontsize=J.BODY, fontweight="bold", ha="center",
                va="center", color=J.INK, transform=hx.transAxes)

    letters = iter("abcdef")
    rec = {}
    for r, (tag, rowname) in enumerate(ROWS):
        d = data[tag]
        fov = FOV_UM[tag]
        sl, H, nm = window(d, fov)
        y0 = M + HDR + r * (PAN + GAP)

        lx = ax_at(M, y0, LAB, PAN)
        lx.set_axis_off()
        lx.text(0.55, 0.5, rowname, fontsize=J.BODY, fontweight="bold", rotation=90,
                ha="center", va="center", color=J.INK, transform=lx.transAxes)

        img = stretch(d["img"][sl])
        flat = stretch(d["flat"][sl])
        final = d["final"][sl]
        removed = d["proposed"][sl] & ~final

        result = np.dstack([img] * 3)
        result[final] = np.array(J.rgb(J.MASK))
        result[removed] = np.array(J.rgb(REMOVED))

        iy, ix, iside, nrem = densest(removed, max(int(round(INSET_FRAC * H)), 16))
        rec[tag] = {"field": str(d["field"]), "nm_per_px": nm, "fov_um": fov,
                    "window_px": int(H), "crop": [int(sl[0].start), int(sl[1].start)],
                    "inset_um": round(fov * INSET_FRAC, 2), "inset_px": iside,
                    "inset_origin_in_window": [iy, ix],
                    "pixels_removed_by_cleaning_in_window": int(removed.sum()),
                    "pixels_removed_in_inset": nrem,
                    "pixels_kept_in_window": int(final.sum())}

        for c, arr in enumerate((np.dstack([img] * 3), np.dstack([flat] * 3), result)):
            ax = ax_at(M + LAB + c * (PAN + GAP), y0, PAN, PAN)
            ax.imshow(arr, interpolation="nearest")
            J.micrograph(ax)
            ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes, fill=False,
                                   edgecolor=J.INK, linewidth=0.7, zorder=30))
            J.panel_label(ax, next(letters), inside=True)
            scalebar(ax, nm, H, fontsize=J.TICK)

            if c == 2:
                # the magnified inset: what the cleaning stages removed, at a size where
                # it can be seen, with a rectangle on the panel saying where it is from
                ax.add_patch(Rectangle((ix, iy), iside, iside, fill=False,
                                       edgecolor=REMOVED, linewidth=0.9, zorder=31))
                side = 0.40
                inax = ax.inset_axes([0.015, 0.015, side, side])
                inax.imshow(result[iy:iy + iside, ix:ix + iside], interpolation="nearest")
                inax.set_xticks([])
                inax.set_yticks([])
                for sp in inax.spines.values():
                    sp.set_edgecolor(REMOVED)
                    sp.set_linewidth(0.9)

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "three stages that differ, in columns; two modalities, in rows; the "
                "stages that look alike combined into the third column with what they "
                "removed drawn in red and magnified",
        "rows": rec,
        "columns": list(COLS),
        "scale_provenance": {"sem": BM.SEM_SCALE_SOURCE, "txm": BM.TXM_SCALE_SOURCE},
        "inset_magnification": round(1.0 / INSET_FRAC, 1),
        "selection_rule": "each window is the position holding the most mask-boundary "
                          "pixels, found exactly by a box sum over the summed-area "
                          "table, the same rule as "
                          "Figure 1; each inset is the "
                          "position holding the most removed pixels, found exactly by a "
                          "box sum over the summed-area table",
        "settings": {"scale_ladder": list(DO.SCALE_LADDER),
                     "absolute_dark_thresh": DO.ABSOLUTE_DARK_THRESH,
                     "mad_k": BM.MAD_K, "min_area_px": BM.MIN_AREA_PX},
        "note": "real intermediate arrays; removed pixels are magnified, never dilated. "
                "No sentence appears inside the artwork: the colour key and the inset "
                "magnification are in the manuscript caption.",
    }, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)
    for tag, _ in ROWS:
        n = rec[tag]
        print(f"  {tag.upper():<4} window {n['window_px']} px ({n['fov_um']:g} um) at "
              f"{tuple(n['crop'])}; kept {n['pixels_kept_in_window']:,} px, cleaning "
              f"removed {n['pixels_removed_by_cleaning_in_window']:,} "
              f"({n['pixels_removed_in_inset']:,} of them in the inset)")


if __name__ == "__main__":
    main()
