#!/usr/bin/env python3
"""Figure 1: the study in one figure -- two modalities in, one rule, one reading out.

WHAT CHANGED AND WHY, THIRD REVISION. The first version put the three operations in a
bordered block of descriptive prose across the middle of the plate. The review called it
a big black box. The second replaced the prose with three chevrons and four arrows that
converged into them and diverged out again; the review's verdict on that was the same.
Both were the same mistake in different clothing: a FLOW DIAGRAM pasted between two rows
of micrographs, describing in words and arrowheads a left-to-right order that the panels
themselves already have.

So there is no middle any more. The figure is a grid. Reading order is left to right
because that is where the panels are, the stage names are column headings, and the only
marks on the plate that are not data are the panel letters, the scale bars, the detail
rectangle and the axis furniture of the last column. No arrow appears anywhere in it.

THE GRID, which is also the argument:

                  Field              Crack            Detected          Measured
      SEM     whole frame,        detail, as       detail, with       width of the
                split              acquired          the mask          marked area
      TXM        ...                 ...               ...                ...

The two rows are the two microscopies, run with the SAME constants and nothing retuned,
and they are aligned column for column so that the second review's request -- show the
same steps for SEM and TXM side by side -- is the layout rather than a claim in the text.

THE LAST COLUMN IS NEW, AND IT IS WHY THIS IS A WORKFLOW FIGURE AND NOT A STAGE FIGURE.
What this application emits is not a mask, it is a measurement, and the first three
columns stopped at the mask. Column four is what comes out: for every marked region in
the frame, the shipped `crack_shape_measurements` is called and its MeanWidth is binned
with the region's own area as the weight, so the curve reads as the fraction of reported
crack area lying at each width. That is the quantity a materials reader would take from
this software, it is measured on the whole frame rather than on the illustrated window,
and drawn on one shared logarithmic axis it carries the modality argument of Figure 2 in
numbers: the SEM trace and the TXM shadow are not the same measurand and do not live at
the same width.

AREA-WEIGHTED, NOT COUNTED. A count of regions is not a mass of crack. This SEM frame
holds over 1500 marked regions and one of them holds a large share of the marked area;
an unweighted histogram would be a picture of the specks and would say nothing about the
crack. Weighting by area answers the question a reader actually has.

EVERY PANEL IS A REAL ARRAY, AND EVERY NUMBER COMES FROM THE SHIPPED CODE. Both frames
are loaded and staged by `both_modalities.py`, the single source of these arrays for the
whole figure set, and the widths come from the application's own measurement function
rather than from a formula retyped here. No pixel is added for visibility.

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
sys.path.insert(0, os.path.join(_paths.ANALYSIS, "_vendor"))
sys.dont_write_bytecode = True

import numpy as np                                  # noqa: E402
import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.patches import Rectangle            # noqa: E402
from scipy import ndimage as ndi                    # noqa: E402
from skimage import exposure                        # noqa: E402

import extended_features as EF                      # noqa: E402  -- the shipped measurands
import both_modalities as BM                        # noqa: E402
import detector_overrides as DO                     # noqa: E402
import journal_style as J                           # noqa: E402
from scalebar import scalebar                       # noqa: E402

J.use()
OUT = _paths.FIG_DIR
NAME = "F1 - workflow"

#: The detail window per modality, in MICROMETRES rather than in pixels, so that a
#: change of field or of magnification cannot silently change what the panel shows. The
#: two differ because the two cracks differ in scale by about that factor.
DETAIL_UM = {"sem": 90.0, "txm": 20.0}
ARMS = (("sem", "SEM"), ("txm", "TXM"))
COLS = ("Field", "Crack", "Detected", "Measured")

#: The shared axes of column four, in micrometres. One pair of limits for both rows:
#: the comparison between the two microscopies is the point, two axes would hide it.
WLIM = (0.06, 8.0)
LLIM = (0.3, 3000.0)

#: THE WINDOW RULE, shared by Figures 1 and 3. Not "the most marked pixels": on a field
#: whose crack is wider than the window, the densest position is solid mask and the panel
#: shows no boundary at all. Capping the marked fraction does not fix it either -- the
#: maximiser then sits exactly at the cap, and on the b2 field that put the window on the
#: crack mouth with half the panel one flat colour. What a detection panel is FOR is the
#: line the detector drew, so the window is the one containing the most mask-BOUNDARY
#: pixels. A solid block has almost none, an empty region has none, and the maximiser is
#: therefore a window where mask meets matrix across the panel. No cap is needed.
#: A marked region whose own outline is more than this fraction frame border is a region
#: the FIELD cut off, not one the detector drew a boundary around, and its edge is the
#: limit of the image rather than a decision. Measured, not guessed: on the SEM field the
#: main crack runs out of both sides and 2.3% of its perimeter is on the border, while on
#: the TXM field the two largest marked objects sit at 37.9% and 50.1%. Any cut between
#: those separates them, and the panels either side of it are a crack and a frame edge.
MAX_EDGE_PERIMETER = 0.15


def boundary_window(final, H):
    """Top-left corner of the H x H window holding the most mask-boundary pixels.

    Boundary pixels belonging to a region the field of view cut off are not counted; see
    MAX_EDGE_PERIMETER. Without that exclusion both TXM rows of this figure set landed on
    the same object: a wedge flush with the right-hand edge of the mosaic holding 57.6% of
    that frame's marked area, which is the largest thing the detector marks there and is
    not a crack. The exclusion is on the WINDOW CHOICE only -- no pixel is removed from
    any mask, and nothing here changes a number.
    """
    lab, n = ndi.label(final, np.ones((3, 3), bool))
    per = final & ~ndi.binary_erosion(final, np.ones((3, 3), bool))
    on = np.zeros_like(final)
    on[0, :] = on[-1, :] = on[:, 0] = on[:, -1] = True
    pc = np.bincount(lab[per].ravel(), minlength=n + 1).astype(float)
    ec = np.bincount(lab[per & on].ravel(), minlength=n + 1).astype(float)
    cut = np.zeros(n + 1, bool)
    cut[1:] = ec[1:] > MAX_EDGE_PERIMETER * np.maximum(pc[1:], 1.0)
    edge = per & ~cut[lab]
    if not edge.any():
        raise SystemExit(
            f"every marked region on this frame has more than "
            f"{MAX_EDGE_PERIMETER:.0%} of its outline on the frame border, so there is no "
            f"detector boundary to show. Choose a different field rather than relaxing "
            f"the bound -- a panel of the field's own edge is not a detection.")
    ii = np.pad(np.cumsum(np.cumsum(edge.astype(np.int64), 0), 1), ((1, 0), (1, 0)))
    box = ii[H:, H:] - ii[:-H, H:] - ii[H:, :-H] + ii[:-H, :-H]
    if not box.size or box.max() <= 0:
        raise SystemExit(f"no {H} px window contains any usable mask boundary -- the "
                         f"field or the window size needs revisiting, not a fallback")
    y0, x0 = np.unravel_index(int(box.argmax()), box.shape)
    return int(y0), int(x0)


def detail_of(d, tag):
    """The window this arm is shown at, found by measurement and the same rule for both.

    WHAT THIS REPLACES. The rule used to be "centre on the largest marked region the
    frame CONTAINS", with border-touching regions censored because on the TXM frame the
    single largest marked region is the mosaic's own right-hand edge. On the b2 SEM field
    the paper is now drawn from, that rule fails in the opposite direction: the main
    crack runs out of both sides of the field, so the censor removes the very object the
    figure exists to show, and the window landed on a secondary region of 1.5 um while
    87.7% of the marked area sat elsewhere. `boundary_window` above says what replaced
    it and why neither "the most marked pixels" nor a cap on that was the answer. The
    region the measurement panel rings is the largest one inside the chosen window, so
    the four panels of a row are about the same object.
    """
    f = d["final"]
    H = int(round(DETAIL_UM[tag] * 1000.0 / float(d["nm_per_px"])))
    H = min(H, f.shape[0], f.shape[1])
    y0, x0 = boundary_window(f, H)
    lab, _ = ndi.label(f, np.ones((3, 3), bool))
    win = lab[y0:y0 + H, x0:x0 + H]
    sz = np.bincount(win.ravel())
    sz[0] = 0
    main = int(sz.argmax()) if sz.size > 1 and sz.max() > 0 else 0
    return y0, x0, H, main


def measure_regions(final, nm_per_px, want=None):
    """Every marked region, measured by the shipped function: width, length, area.

    THE SHIPPED FUNCTION IS CALLED, not a formula retyped here. `MeanWidth_px` is defined
    in `extended_features` as area divided by skeleton LENGTH, with a diagonal step
    counted as sqrt(2); dividing by the pixel COUNT instead -- which is the obvious
    reimplementation -- overstates the width of a diagonal crack by up to 41%. The same
    module falls back to sqrt(area) for a region too small to skeletonise, and the count
    of regions that took that fallback is recorded in the caption JSON rather than hidden.
    """
    lab, n = ndi.label(final, np.ones((3, 3), bool))
    w_um, l_um, area, fallback, wanted = [], [], [], 0, None
    for i, sl in enumerate(ndi.find_objects(lab)):
        if sl is None:
            continue
        sub = lab[sl] == (i + 1)
        m = EF.crack_shape_measurements(sub)
        a = float(m["Area_px"])
        skel = float(m["SkeletonLength_px"])
        if not skel > 0:
            fallback += 1
        w = float(m["MeanWidth_px"]) * nm_per_px / 1000.0
        ln = max(skel, 1.0) * nm_per_px / 1000.0
        if want is not None and (i + 1) == want:
            wanted = (w, ln)
        w_um.append(w)
        l_um.append(ln)
        area.append(a)
    w_um, l_um = np.asarray(w_um), np.asarray(l_um)
    area = np.asarray(area)
    # the reconstruction check every derived quantity in this figure set carries: the
    # areas the measurement function reports must add up to the mask it was handed
    if abs(area.sum() - float(final.sum())) > 1.0:
        raise SystemExit(
            f"region areas sum to {area.sum():.0f} px but the mask holds "
            f"{float(final.sum()):.0f} px -- the per-region loop is not measuring the "
            f"same object the panels draw")
    return w_um, l_um, area, n, fallback, wanted


def weighted_median(x, w):
    o = np.argsort(x)
    c = np.cumsum(w[o]) / w.sum()
    return float(np.interp(0.5, c, x[o]))


def limits(arr):
    """The display range of a whole frame, used for every panel drawn from that frame.

    ONE RANGE PER ROW, NOT ONE PER PANEL, and the rule itself lives in
    `both_modalities.display_range` so that every figure in the set renders a given
    frame identically. Stretching each panel to its own percentiles renders the detail
    under a different convention from the field it was cut out of.
    """
    return BM.display_range(arr)


def stretched(arr, rng=None):
    """Display stretch, 2nd-98th percentile of the frame, for every panel of both arms.

    The TXM frames are mosaic averages with a broad, low-contrast attenuation gradient
    across them; printed as loaded, the crack is a grey smudge on grey. The stretch is
    DISPLAY ONLY -- the detector ran on the unstretched array and every mask drawn here is
    that run -- and it is applied identically to both modalities so the two rows are not
    rendered under different conventions.
    """
    lo, hi = rng if rng is not None else limits(arr)
    if hi <= lo:
        return arr.astype(np.float32) / 255.0
    return exposure.rescale_intensity(arr.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0.0, 1.0))


def main():
    data = {tag: BM.load(tag) for tag, _ in ARMS}
    crops = {tag: detail_of(data[tag], tag) for tag, _ in ARMS}

    W = J.PAGEW
    M = 0.03
    LAB = 0.17                       # the row-label strip
    HDR = 0.20                       # the column headings
    G1, G2, G3 = 0.10, 0.045, 0.34   # field|crack, crack|detected, detected|measured
    RGAP = 0.07
    XL = 0.36                        # x tick labels and axis label under the last column
    # Column one is WIDER than the two detail columns because the SEM field is
    # landscape and the TXM field is square: at the detail columns' width the SEM frame
    # would stand 0.9 in tall in a 1.3 in cell and the plate would carry a band of white
    # across its left edge. Sized this way the landscape frame fills its cell's width
    # and the square one fills its height, and both rows still align column for column.
    C1 = 1.62
    S = 1.30                                            # a detail panel, square
    P = W - 2 * M - LAB - G1 - G2 - G3 - C1 - 2 * S     # the measurement panel
    Htot = M + HDR + 2 * S + RGAP + XL + M

    X = [M + LAB,
         M + LAB + C1 + G1,
         M + LAB + C1 + S + G1 + G2,
         M + LAB + C1 + 2 * S + G1 + G2 + G3]
    CW = [C1, S, S, P]

    fig = plt.figure(figsize=(W, Htot))

    def ax_at(xin, yin, win, hin):
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    for c, name in enumerate(COLS):
        hx = ax_at(X[c], M, CW[c], HDR)
        hx.set_axis_off()
        hx.text(0.5, 0.30, name, fontsize=J.BODY, fontweight="bold", ha="center",
                va="bottom", color=J.INK, transform=hx.transAxes)

    letters = iter("abcdefgh")
    notes, dists, paxes = {}, {}, []
    for r, (tag, rowname) in enumerate(ARMS):
        d = data[tag]
        img, final = d["img"], d["final"]
        y0, x0, H, main = crops[tag]
        nm = float(d["nm_per_px"])
        ytop = M + HDR + r * (S + RGAP)

        lx = ax_at(M, ytop, LAB, S)
        lx.set_axis_off()
        lx.text(0.55, 0.5, rowname, fontsize=J.BODY, fontweight="bold", rotation=90,
                ha="center", va="center", color=J.INK, transform=lx.transAxes)

        # --- column 1: the whole field, ONE panel split down the middle ---------------
        # left as acquired, right with the finished mask. Panels that differ only by an
        # overlay have to be adjacent to be compared at all, and splitting one frame is
        # the most adjacent two such panels can be.
        rng = limits(img)
        step = max(1, img.shape[1] // 1400)
        thumb = stretched(img[::step, ::step], rng)
        rgb = np.dstack([thumb] * 3)
        half = thumb.shape[1] // 2
        rgb[:, half:][final[::step, ::step][:, half:]] = np.array(J.rgb(J.MASK))
        fw = S * thumb.shape[1] / thumb.shape[0]
        if fw > C1:                      # a landscape frame is limited by the column
            fw, fh = C1, C1 * thumb.shape[0] / thumb.shape[1]
        else:
            fh = S
        ax = ax_at(X[0] + (C1 - fw) / 2, ytop + (S - fh) / 2, fw, fh)
        ax.imshow(rgb, interpolation="nearest", aspect="equal")
        ax.plot([half, half], [0, thumb.shape[0] - 1], color="white", lw=0.9, zorder=20)
        ax.plot([half, half], [0, thumb.shape[0] - 1], color=J.INK, lw=0.4,
                linestyle=(0, (2, 2)), zorder=21)
        ax.add_patch(Rectangle((x0 / step, y0 / step), H / step, H / step, fill=False,
                               edgecolor=J.ROI, linewidth=0.9, zorder=22))
        J.micrograph(ax)
        J.panel_label(ax, next(letters), inside=True)
        scalebar(ax, nm * step, thumb.shape[1], fontsize=J.TICK)

        # --- columns 2 and 3: the detail, before and after ----------------------------
        sl = (slice(y0, y0 + H), slice(x0, x0 + H))
        grey = np.dstack([stretched(img[sl], rng)] * 3)
        marked = grey.copy()
        marked[final[sl]] = np.array(J.rgb(J.MASK))
        for c, arr in ((1, grey), (2, marked)):
            ax = ax_at(X[c], ytop, S, S)
            ax.imshow(arr, interpolation="nearest")
            J.micrograph(ax)
            ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes, fill=False,
                                   edgecolor=J.ROI if c == 1 else J.INK,
                                   linewidth=0.9, zorder=30))
            J.panel_label(ax, next(letters), inside=True)
            scalebar(ax, nm, H, fontsize=J.TICK)

        # --- column 4: what comes out -------------------------------------------------
        # THE EXPORTED MEASUREMENT TABLE, DRAWN. One point per marked region, its
        # network length against its mean width, both from the shipped measurement
        # function, with the marker area carrying the region's own area so that the
        # plot reads as where the reported crack MASS is. A count of regions is not a
        # mass of crack, and the two rows differ in exactly that: the largest marked
        # region holds 3% of the SEM frame's marked area and 58% of the TXM frame's, so
        # a plot that gave every region the same dot would describe the two frames as
        # though they were the same kind of object. The whole frame is measured here,
        # not the window columns 2 and 3 show.
        w_um, l_um, area, nreg, fallback, one = measure_regions(final, nm, want=main)
        med = weighted_median(w_um, area)
        colour = J.ACCENT if tag == "sem" else J.ACCENT2
        px = ax_at(X[3], ytop, P, S)
        px.scatter(w_um, l_um, s=1.2 + 26.0 * np.sqrt(area / area.max()),
                   facecolor=colour, edgecolor="none", alpha=0.40, zorder=3)
        if one is None:
            raise SystemExit("the illustrated region was not measured by the per-region "
                             "loop -- the two are not labelling the same mask")
        px.scatter([one[0]], [one[1]], s=58, facecolor="none", edgecolor=J.ROI,
                   linewidth=1.1, zorder=6)
        px.set_xscale("log")
        px.set_yscale("log")
        px.set_xlim(*WLIM)
        px.set_ylim(*LLIM)
        px.tick_params(labelsize=J.TICK)
        J.panel_label(px, next(letters), inside=True)
        if r == 0:
            px.set_xticklabels([])
        else:
            px.set_xlabel("mean width (µm)", fontsize=J.LABEL)
        paxes.append(px)

        dists[tag] = {"regions": int(nreg), "sqrt_area_fallbacks": int(fallback),
                      "area_weighted_median_width_um": round(med, 4),
                      "illustrated_region_width_um": round(one[0], 4),
                      "illustrated_region_length_um": round(one[1], 4),
                      "largest_region_share_of_marked_area": round(
                          float(area.max() / area.sum()), 4)}
        notes[tag] = dict(frame_px=[int(img.shape[0]), int(img.shape[1])],
                          nm_per_px=nm, crop=[int(y0), int(x0)], detail_px=int(H),
                          detail_um=DETAIL_UM[tag],
                          display_range=[round(rng[0], 1), round(rng[1], 1)],
                          area_fraction_pct=round(100 * float(final.mean()), 3),
                          window_area_fraction_pct=round(
                              100 * float(final[sl].mean()), 2))

    fig.text((X[3] - 0.27) / W, 1.0 - (M + HDR + S + RGAP / 2) / Htot,
             "network length (µm)", rotation=90, fontsize=J.LABEL, ha="center",
             va="center", color=J.INK)

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "two modalities in, one detection rule, one measurement out; four "
                "columns left to right and one row per microscopy, with no arrow, no "
                "chevron and no sentence anywhere on the plate",
        "columns": list(COLS),
        "arms": {tag: {"field": str(data[tag]["field"]), **notes[tag], **dists[tag]}
                 for tag, _ in ARMS},
        "scale_provenance": {"sem": BM.SEM_SCALE_SOURCE, "txm": BM.TXM_SCALE_SOURCE},
        "selection_rule": "each detail window is the position holding the most mask-boundary "
                          "pixels, found exactly by a box sum over the summed-area "
                          "table of the mask's own BOUNDARY pixels, so the panel is a "
                          "place where mask meets matrix rather than a block of flat "
                          "colour; the same rule for both rows. The ringed region "
                          "in the last column is the largest one inside that window.",
        "display": "one 2nd-98th percentile range per frame, applied to the field and "
                   "to the detail cut from it, so the detail is the field magnified "
                   "and not a differently rendered picture",
        "measurement_panel": {
            "measurands": "MeanWidth_px and SkeletonLength_px from the shipped "
                          "extended_features.crack_shape_measurements, called once per "
                          "connected region of the WHOLE FRAME, not of the window",
            "marker_area": "proportional to the square root of the region's own area, "
                           "so the panel reads as where the reported crack mass is and "
                           "not as a count of regions",
            "ring": "the red ring is the one region columns 2 and 3 are centred on",
            "axes": "both logarithmic, and shared by the two rows",
            "check": "the per-region areas must sum to the mask the panels draw, to "
                     "within one pixel, or the script aborts"},
        "settings": {"scale_ladder": list(DO.SCALE_LADDER),
                     "absolute_dark_thresh": DO.ABSOLUTE_DARK_THRESH,
                     "mad_k": BM.MAD_K, "min_area_px": BM.MIN_AREA_PX,
                     "use_region_classifier": DO.USE_REGION_CLASSIFIER},
        "note": "every micrograph panel is a real intermediate array; no pixel is added "
                "for visibility and nothing is drawn by hand. No sentence appears inside "
                "the artwork.",
    }, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)
    for tag, _ in ARMS:
        n, w = notes[tag], dists[tag]
        print(f"  {tag.upper():<4} {str(data[tag]['field'])[:40]:<40} "
              f"detail {n['detail_px']} px at {tuple(n['crop'])}, marked "
              f"{n['area_fraction_pct']}%, {w['regions']} regions, area-weighted median "
              f"width {w['area_weighted_median_width_um']} um; illustrated region "
              f"{w['illustrated_region_width_um']} x "
              f"{w['illustrated_region_length_um']} um; largest region holds "
              f"{100 * w['largest_region_share_of_marked_area']:.1f}% of marked area")


if __name__ == "__main__":
    main()
