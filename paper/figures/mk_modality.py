#!/usr/bin/env python3
"""Figure 2: one crack, two measurement geometries, and what the criterion can reach.

WHY. The paper measures the same quantity in two microscopies and carries a detector
written for one across to the other. Whether that is reasonable depends entirely on what
each instrument records, and the paper asserted the difference in a clause.

ONE SCHEMATIC, NOT TWO. An earlier version drew the two geometries as separate pictures
side by side, which left the comparison to the reader. They are drawn on ONE block of
material containing ONE crack: the electron beam arrives at the polished top face and the
signal has to escape back out of it, so what that instrument records is the line where the
crack cuts that face; the X-ray beam crosses the whole thickness to a detector behind, so
what IT records is the crack's silhouette along the beam. The same crack, two different
measurands. The two are in practice different specimen preparations -- a polished section
and a transmission specimen -- and the caption says so; drawing them on one block is what
makes the two measurands comparable at a glance.

NO SENTENCES INSIDE THE ARTWORK. The labels on the schematic are part of the drawing. The
description of the figure is in the manuscript caption.

(d) IS A MEASUREMENT AND IS HERE BECAUSE THE OBVIOUS CAPTION FOR THE SCHEMATIC IS WRONG.
"A void crosses less material, so it transmits more, so it reads bright" does not describe
this corpus: a crack reads DARKER than the painted not-crack on 23 of 31 TXM frames too,
and the radiometric convention of the stored arrays is not recorded anywhere in the three
repositories, so no mechanism is offered for that. What (d) plots is the quantity the
detector actually thresholds: per pixel, the largest MAD multiplier at which the
multiscale darkness union would still propose it, summarised per frame over the pixels a
human painted as crack, against the operating point.

A standardised intensity contrast was plotted here first and withdrawn: the two
collections' NOT-crack verdicts were painted to different conventions -- adversarially in
one, as broad context strokes in the other -- so a contrast measured against them is not
comparable across the two, and a panel inviting that comparison would have been the
figure's main claim.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_modality.py
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

import both_modalities as BM                        # noqa: E402
import journal_style as J                           # noqa: E402
from scalebar import scalebar                       # noqa: E402

J.use()
OUT = _paths.FIG_DIR
NAME = "F2 - how each modality sees a crack"
CONTRAST = os.path.join(os.path.dirname(os.path.dirname(HERE)), "docs", "figures",
                        "modality_contrast.json")

#: The matched field of view the two micrograph panels are shown at. 15 um is 289 px of
#: SEM and 513 px of TXM; showing both at the same number of PIXELS, as a naive side by
#: side would, compares a 27 um field with a 15 um one and makes the TXM crack look
#: 1.8x wider than it is.
FOV_UM = 15.0


def crop_at(d, um):
    """A window of `um` micrometres centred on the largest marked region the frame holds.

    Same rule and same centre as Figure 1, so a reader moving between the two figures is
    looking at the same crack.
    """
    from scipy import ndimage as ndi
    nm = float(d["nm_per_px"])
    H = int(round(um * 1000.0 / nm))
    f = d["final"]
    lab, _ = ndi.label(f, np.ones((3, 3), bool))
    sz = np.bincount(lab.ravel())
    sz[0] = 0
    for b in set(np.unique(np.concatenate(
            [lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}:
        sz[b] = 0
    cy, cx = ndi.center_of_mass(lab == int(sz.argmax()))
    y0 = max(min(int(cy) - H // 2, f.shape[0] - H), 0)
    x0 = max(min(int(cx) - H // 2, f.shape[1] - H), 0)
    return (slice(y0, y0 + H), slice(x0, x0 + H)), H, nm


def stretch(arr):
    """Display stretch, 2nd-98th percentile, identical for both modalities."""
    from skimage import exposure
    lo, hi = np.percentile(arr, [2, 98])
    if hi <= lo:
        return arr.astype(np.float32) / 255.0
    return exposure.rescale_intensity(arr.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0.0, 1.0))


# ----------------------------------------------------------------- the one schematic
#: The oblique projection the block is drawn in. A point (x, y, z) in the specimen's own
#: coordinates -- x across, y up, z into the depth -- lands at (x + KZ*z, y + KY*z).
KZ, KY = 0.40, 0.30
#: The block, in those coordinates, and where its near-bottom-left corner sits on the
#: canvas. The canvas is 100 x 34 and the panel is drawn at that aspect.
BW, BH, BD = 30.0, 16.0, 13.0
OX, OY = 26.0, 3.5
#: How far the detector sits behind the block, and how thick it is drawn.
DGAP, DTHICK = 11.0, 1.6


def _p(x, y, z):
    return (OX + x + KZ * z, OY + y + KY * z)


def _poly(ax, pts, **kw):
    from matplotlib.patches import Polygon as _P
    ax.add_patch(_P([_p(*q) for q in pts], closed=True, **kw))


def _crack(n=140):
    """The crack as one analytic sheet: a plan-view track and a depth below the face.

    One object, three views -- the trace on the top face, the sheet inside the block and
    the silhouette on the detector are all computed from these arrays, so they cannot
    disagree with one another.
    """
    t = np.linspace(0.0, 1.0, n)
    x = 4.0 + t * (BW - 8.0)
    z = 2.0 + 9.0 * (0.5 + 0.44 * np.sin(2.4 * np.pi * t + 0.5))
    # A CURTAIN, NOT A BOWL. The depth used to be a half-sine -- zero at both ends and
    # deepest in the middle -- which draws a lens-shaped cavity, and that is what the
    # first version looked like. A crack is a sheet of roughly constant extent with a
    # ragged lower edge, so the depth is nearly constant and the raggedness is what
    # varies. It is a drawing choice; the caption says the schematic is not to scale.
    depth = (5.6 + 1.1 * np.sin(5.1 * np.pi * t + 1.0) + 0.5 * np.sin(9.3 * np.pi * t)
             ) * np.clip(np.sin(np.pi * t) ** 0.18, 0.0, 1.0)
    return x, z, depth


def _silhouette(z, depth, nbins=44):
    """The crack's outline as the X-ray beam sees it: its extent in (depth, height).

    Binned over z and reduced with a minimum, because the track doubles back on itself --
    several points of the crack lie on one ray, and what the beam records is their union.
    Taking the samples in their own order instead drew a sawtooth, which is an artefact of
    the parameterisation and not of the crack.
    """
    zg = np.linspace(z.min(), z.max(), nbins)
    lo = np.full(nbins, np.nan)
    idx = np.clip(np.searchsorted(zg, z) - 1, 0, nbins - 1)
    for i, d in zip(idx, depth):
        lo[i] = d if np.isnan(lo[i]) else max(lo[i], d)
    ok = ~np.isnan(lo)
    lo = np.interp(zg, zg[ok], lo[ok])
    return zg, BH - lo


def combined_schematic(ax):
    """One block, one crack, both instruments, so the two measurands can be compared."""
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 30)
    ax.set_axis_off()
    x, z, depth = _crack()

    # the crack first, then the block's two near faces over it at partial opacity, so the
    # sheet reads as being INSIDE the solid rather than painted on it
    sheet = ([(xx, BH, zz) for xx, zz in zip(x, z)]
             + [(xx, BH - dd, zz) for xx, zz, dd in zip(x[::-1], z[::-1], depth[::-1])])
    _poly(ax, [(0, BH, 0), (BW, BH, 0), (BW, BH, BD), (0, BH, BD)],
          facecolor="#f2f2f2", edgecolor=J.G_DARK, lw=0.7, zorder=2)
    _poly(ax, [(BW, 0, 0), (BW, 0, BD), (BW, BH, BD), (BW, BH, 0)],
          facecolor="#cfcfcf", edgecolor=J.G_DARK, lw=0.7, zorder=2)
    # ABOVE the front face, below the top face: at zorder 3 the sheet sat under both and
    # two translucent greys over it left the crack a mid grey. Here only the sliver that
    # is genuinely under the polished surface is softened, which is the depth cue wanted.
    _poly(ax, sheet, facecolor="#2b2b2b", edgecolor="none", zorder=4.5)
    _poly(ax, [(0, 0, 0), (BW, 0, 0), (BW, BH, 0), (0, BH, 0)],
          facecolor="#dcdcdc", edgecolor=J.G_DARK, lw=0.7, alpha=0.58, zorder=4)
    _poly(ax, [(0, BH, 0), (BW, BH, 0), (BW, BH, BD), (0, BH, BD)],
          facecolor="#f2f2f2", edgecolor=J.G_DARK, lw=0.7, alpha=0.62, zorder=5)
    tr = np.array([_p(xx, BH, zz) for xx, zz in zip(x, z)])
    ax.plot(tr[:, 0], tr[:, 1], color=J.ACCENT, lw=2.0, solid_capstyle="round", zorder=6)

    # --- the electron column: in at the surface, out to a detector above --------------
    bx, bz = x[len(x) // 2], z[len(z) // 2]
    hit = _p(bx, BH, bz)
    ax.add_patch(FancyArrowPatch((hit[0], hit[1] + 8.2), (hit[0], hit[1] + 0.5),
                                 arrowstyle="-|>", mutation_scale=9, color=J.ACCENT,
                                 lw=1.1, zorder=8))
    ax.text(hit[0] + 1.4, hit[1] + 8.0, "electron beam", fontsize=J.TICK, ha="left",
            va="top", color=J.ACCENT, zorder=9)
    dcx, dcy = hit[0] - 17.0, hit[1] + 6.4
    ax.add_patch(Rectangle((dcx - 7.2, dcy - 1.9), 14.4, 3.8, facecolor="white",
                           edgecolor=J.INK, lw=0.7, zorder=9))
    ax.text(dcx, dcy, "detector", fontsize=J.TICK, ha="center", va="center",
            color=J.INK, zorder=10)
    # a small fan of escaping signal rather than one arrow: it is what the detector
    # collects, and one arrow reads as a reflection
    for fx_, fy_ in ((4.4, -2.4), (6.6, -3.0), (2.2, -1.6)):
        ax.add_patch(FancyArrowPatch((hit[0] - 0.8, hit[1] + 0.5),
                                     (dcx + fx_, dcy + fy_), arrowstyle="-|>",
                                     mutation_scale=7, color=J.INK, lw=0.7, zorder=8))

    # --- the X-ray beam: through the whole block to a detector behind it --------------
    # AT THE HEIGHT OF THE CRACK, not below it. The first version put the three rays
    # under the sheet entirely, so they crossed nothing and the silhouette drawn on the
    # detector contradicted the picture that was meant to produce it.
    ybeam = BH - 0.55 * float(depth.mean())
    for zz in (2.5, 6.5, 10.5):
        ax.add_patch(FancyArrowPatch(_p(-15.0, ybeam, zz),
                                     _p(BW + DGAP - 1.6, ybeam, zz),
                                     arrowstyle="-|>", mutation_scale=8,
                                     color=J.ACCENT2, lw=1.0, zorder=7))
    lx, ly = _p(-15.0, ybeam, 10.5)
    # BELOW the rays, not above them: above, it landed inside the SEM annotation that
    # occupies the top-left corner.
    ax.text(lx, _p(-15.0, ybeam, 2.5)[1] - 1.4, "X-ray beam", fontsize=J.TICK,
            ha="left", va="top", color=J.ACCENT2, zorder=9)

    # the detector, and the crack's silhouette recorded on it
    _poly(ax, [(BW + DGAP, 0, 0), (BW + DGAP, 0, BD), (BW + DGAP, BH, BD),
               (BW + DGAP, BH, 0)], facecolor="white", edgecolor=J.INK, lw=0.7, zorder=7)
    _poly(ax, [(BW + DGAP, 0, 0), (BW + DGAP + DTHICK, 0, 0),
               (BW + DGAP + DTHICK, BH, 0), (BW + DGAP, BH, 0)],
          facecolor="#eeeeee", edgecolor=J.INK, lw=0.7, zorder=7)
    zg, ylo = _silhouette(z, depth)
    sil = ([(BW + DGAP, BH, zz) for zz in zg]
           + [(BW + DGAP, yy, zz) for zz, yy in zip(zg[::-1], ylo[::-1])])
    _poly(ax, sil, facecolor=J.ACCENT2, edgecolor="none", zorder=8)

    # --- what each instrument records -------------------------------------------------
    t0 = _p(x[6], BH, z[6])
    ax.annotate("what SEM records:\nthe crack where it cuts\nthe polished surface",
                xy=(t0[0], t0[1]), xytext=(1.5, 26.5), fontsize=J.TICK, ha="left",
                va="top", color=J.ACCENT, linespacing=1.25, zorder=10,
                arrowprops=dict(arrowstyle="-", color=J.ACCENT, lw=0.7, shrinkA=2,
                                shrinkB=2))
    s0 = _p(BW + DGAP, BH - 3.5, float(np.median(zg)))
    ax.annotate("what TXM records:\nits silhouette along\nthe whole thickness",
                xy=(s0[0], s0[1]), xytext=(99.0, 26.5), fontsize=J.TICK, ha="right",
                va="top", color=J.ACCENT2, linespacing=1.25, zorder=10,
                arrowprops=dict(arrowstyle="-", color=J.ACCENT2, lw=0.7, shrinkA=2,
                                shrinkB=2))
    pf = _p(BW * 0.88, BH, BD * 0.72)
    ax.annotate("polished surface", xy=pf, xytext=(_p(BW, BH, BD)[0] + 1.5,
                                                   _p(BW, BH, BD)[1] + 2.4),
                fontsize=J.TICK, ha="left", va="bottom", color=J.G_DARK, zorder=9,
                arrowprops=dict(arrowstyle="-", color=J.G_DARK, lw=0.7, shrinkA=2,
                                shrinkB=2))
    k = len(x) // 5
    cf = _p(x[k], BH - 0.55 * depth[k], z[k])
    ax.annotate("crack", xy=cf, xytext=(cf[0] - 2.0, cf[1] - 7.5), fontsize=J.TICK,
                ha="right", va="top", color=J.INK, zorder=10,
                arrowprops=dict(arrowstyle="-", color=J.INK, lw=0.7, shrinkA=2,
                                shrinkB=2))


def main():
    data = {t: BM.load(t) for t in ("sem", "txm")}
    if not os.path.exists(CONTRAST):
        raise SystemExit(
            f"{CONTRAST} is missing. Run analysis/research/improve/modality_contrast.py "
            f"first -- panel (d) reports a measurement and must not be drawn from a "
            f"remembered number.")
    con = json.load(open(CONTRAST))

    W = J.PAGEW
    M = 0.03
    GAP = 0.13
    SCH = (W - 2 * M) * 30.0 / 100.0          # the schematic's own aspect
    IMG = 1.45
    ROWGAP = 0.20
    Htot = M + SCH + ROWGAP + IMG + M

    fig = plt.figure(figsize=(W, Htot))

    def ax_at(xin, yin, win, hin):
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    sx = ax_at(M, M, W - 2 * M, SCH)
    combined_schematic(sx)
    sx.text(0.0, 0.985, "(a)", transform=sx.transAxes, fontsize=J.PANEL,
            fontweight="bold", va="top", ha="left", color=J.INK)

    yrow = M + SCH + ROWGAP
    notes = {}
    for i, (tag, letter) in enumerate((("sem", "b"), ("txm", "c"))):
        d = data[tag]
        sl, H, nm = crop_at(d, FOV_UM)
        ix = ax_at(M + i * (IMG + GAP), yrow, IMG, IMG)
        ix.imshow(stretch(d["img"][sl]), cmap="gray", vmin=0, vmax=1,
                  interpolation="nearest")
        J.micrograph(ix)
        ix.add_patch(Rectangle((0, 0), 1, 1, transform=ix.transAxes, fill=False,
                               edgecolor=J.INK, linewidth=0.8, zorder=30))
        J.panel_label(ix, letter, inside=True)
        scalebar(ix, nm, H, fontsize=J.TICK)
        notes[tag] = {"fov_um": FOV_UM, "window_px": int(H), "nm_per_px": nm,
                      "field": str(d["field"])}

    # --- (d) the detector's own axis ------------------------------------------------
    cx0 = M + 2 * (IMG + GAP)
    ax = ax_at(cx0 + 0.52, yrow + 0.03, W - M - cx0 - 0.58, IMG - 0.38)
    cols = [("SEM", con["SEM"]["per_frame"], J.ACCENT)]
    for g in ("B3", "B2", "Wrought", "AM/HC"):
        rows = [r for r in con["TXM"]["per_frame"] if r.get("group") == g]
        if rows:
            cols.append((f"TXM\n{g}", rows, J.ACCENT2))
    rng = np.random.default_rng(0)
    nbelow = 0
    for k, (lab, rows, colour) in enumerate(cols):
        ks = [r["median_critical_k_crack"] for r in rows]
        nbelow += sum(1 for v in ks if v < con["mad_k"])
        jit = rng.uniform(-0.17, 0.17, len(ks))
        ax.plot(k + jit, ks, "o", ms=2.6, mfc=colour, mec="white", mew=0.3,
                linestyle="none", zorder=3)
        ax.plot([k - 0.30, k + 0.30], [np.median(ks)] * 2, color=J.INK, lw=1.4, zorder=4)
    # LOGARITHMIC, because one SEM frame's painted crack sits at 52 MAD multiples and on
    # a linear axis it flattens every other frame onto the baseline. The quantity is a
    # ratio to a frame's own spread, so a log axis is its natural one.
    ax.set_yscale("log")
    ax.axhline(con["mad_k"], color=J.ROI, lw=1.0, zorder=2)
    ax.text(len(cols) - 0.45, con["mad_k"] * 1.16, f"k = {con['mad_k']:g}",
            fontsize=J.TICK, va="bottom", ha="right", color=J.ROI)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([c[0] for c in cols], fontsize=J.TICK)
    ax.set_xlim(-0.6, len(cols) - 0.4)
    ax.set_ylabel("darkness, in\nMAD multiples", fontsize=J.TICK, linespacing=1.2)
    ax.tick_params(labelsize=J.TICK)
    ax.set_yticks([1, 2, 5, 10, 20, 50])
    ax.set_yticklabels(["1", "2", "5", "10", "20", "50"], fontsize=J.TICK)
    ax.minorticks_off()
    J.panel_label(ax, "d")

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "(a) one schematic of both measurement geometries on one crack, drawn "
                "by hand and not to scale; (b), (c) real micrographs at a matched field "
                "of view; (d) a measurement over both corpora",
        "micrographs": notes,
        "matched_fov_um": FOV_UM,
        "panel_e": {
            "plots": "median over each frame's painted-crack pixels of the largest MAD "
                     "multiplier at which the deployed multiscale darkness union would "
                     "still propose that pixel",
            "definition": con["critical_k_definition"],
            "operating_point": con["mad_k"],
            "reconstruction_check": "every frame's reconstruction of the real proposal "
                                    "mask from this axis is checked pixel for pixel "
                                    "against the installed segment_dark_regions; the "
                                    "largest disagreement over all frames is "
                                    f"{max(con['SEM']['max_reconstruction_mismatch_px'], con['TXM']['max_reconstruction_mismatch_px'])} pixels",
            "SEM": {k: con["SEM"][k] for k in
                    ("n_frames", "median_of_median_critical_k_crack",
                     "frames_median_critical_k_below_k",
                     "median_crack_px_proposed_frac")},
            "TXM": {k: con["TXM"][k] for k in
                    ("n_frames", "median_of_median_critical_k_crack",
                     "frames_median_critical_k_below_k",
                     "median_crack_px_proposed_frac")},
            "TXM_by_group": con["TXM"]["by_group"],
        },
        "intensity_contrast_withdrawn_from_the_panel": {
            "why": "the two collections' NOT-crack verdicts were painted to different "
                   "conventions, so a standardised contrast against them is not "
                   "comparable between the modalities; kept here as a record, not shown",
            "definition": con["definition"],
            "SEM_median_d": con["SEM"]["median_d"],
            "TXM_median_d": con["TXM"]["median_d"],
            "SEM_frames_crack_brighter": con["SEM"]["frames_d_negative"],
            "TXM_frames_crack_brighter": con["TXM"]["frames_d_negative"],
        },
        "scale_provenance": {"sem": BM.SEM_SCALE_SOURCE, "txm": BM.TXM_SCALE_SOURCE},
        "note": "panel (a) is a schematic and is labelled as such in the caption; the "
                "two geometries are drawn on one block although they are in practice "
                "different specimen preparations, which the caption states. No mechanism "
                "is claimed for the sign of the TXM contrast, because the radiometric "
                "convention of the stored arrays is not recorded in any of the three "
                "repositories. No sentence appears inside the artwork.",
    }, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)
    for tag in ("SEM", "TXM"):
        c = con[tag]
        print(f"  {tag}  n = {c['n_frames']:<3} median critical k "
              f"{c['median_of_median_critical_k_crack']:+.2f}, below k = {con['mad_k']:g} "
              f"on {c['frames_median_critical_k_below_k']}, median "
              f"{100 * c['median_crack_px_proposed_frac']:.1f}% of painted crack proposed")
    for g, r in con["TXM"]["by_group"].items():
        print(f"       {g:<8} n = {r['n']:<3} median k "
              f"{r['median_of_median_critical_k_crack']:+.2f}, "
              f"{100 * r['median_crack_px_proposed_frac']:.0f}% proposed")


if __name__ == "__main__":
    main()
