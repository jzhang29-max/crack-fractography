#!/usr/bin/env python3
"""Figure 2: what each microscopy actually records, and what a crack looks like in it.

WHY THE PAPER NEEDS THIS. The paper measures the same quantity -- the fraction of a field
that is crack -- in two microscopies, and treats a detector written for one as a candidate
for the other. Whether that is a reasonable thing to do depends entirely on how the two
form an image, and until now the paper asserted the difference in a clause and never
showed it. A reader who does not already know the two techniques cannot tell whether the
transfer in Section 4.3 is nearly trivial or nearly hopeless.

WHAT IS DRAWN AND WHAT IS MEASURED, kept strictly apart:

  (a) and (b) are SCHEMATICS -- geometry, drawn by hand, not to scale. They carry the one
      thing that is certain and that governs every measurement in this paper: scanning
      electron microscopy records a signal that leaves a shallow volume at a polished
      surface, so a pixel reports the specimen in ONE plane; transmission X-ray microscopy
      records a beam that has crossed the whole specimen, so a pixel reports everything
      along a line of sight.

  (c) and (d) are REAL micrographs at a matched physical field of view, so the two
      appearances can be compared without a reader having to convert pixel sizes.

  (e) is a MEASUREMENT over both corpora, on the detector's own axis. The tempting caption
      for (b) -- a void crosses less material, so it transmits more, so it reads bright --
      does not describe this corpus at all: a crack reads DARKER than the not-crack a human
      painted on the same frame on 23 of 31 TXM frames too, and the radiometric convention
      of the stored arrays is not recorded anywhere in the three repositories, so no
      mechanism is offered for that.

      What (e) plots instead is the quantity the detector actually thresholds: per pixel,
      the largest MAD multiplier at which the multiscale darkness union would still propose
      it, summarised per frame over the pixels a human painted as crack. The operating
      point is drawn as a line, so the panel says directly how much of each collection's
      annotated crack the proposal stage can even reach. A standardised intensity contrast
      was plotted here first and withdrawn: the two collections' NOT-crack verdicts were
      painted to different conventions -- adversarially in one, as broad context strokes in
      the other -- so a contrast measured against them is not comparable across the two, and
      a panel inviting that comparison would have been the figure's main claim.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_modality.py
"""
import json
import os
import textwrap
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


# ------------------------------------------------------------------ the two schematics
def sem_schematic(ax):
    """Beam in, signal back out of a shallow volume at a polished surface."""
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 62)
    ax.set_axis_off()
    SURF = 36.0
    ax.add_patch(Rectangle((6, 4), 88, SURF - 4, facecolor=J.G_LIGHT,
                           edgecolor=J.G_DARK, linewidth=0.7, zorder=1))
    ax.plot([6, 94], [SURF, SURF], color=J.INK, lw=1.1, zorder=3)
    ax.text(94, SURF + 1.5, "polished surface", fontsize=J.TICK, ha="right",
            va="bottom", color=J.G_DARK, zorder=6)
    ax.text(8, 9.0, "bulk", fontsize=J.TICK, ha="left", va="bottom", color=J.G_DARK,
            zorder=6)
    ax.text(26, SURF - 10.5, "interaction\nvolume", fontsize=J.TICK, ha="center",
            va="top", color=J.ACCENT, linespacing=1.2, zorder=8)

    # the crack: a wedge opening at the surface and closing with depth
    ax.add_patch(Polygon([(54, SURF), (60.5, SURF), (57.6, 16), (56.4, 16)],
                         closed=True, facecolor=J.INK, edgecolor="none", zorder=4))

    # incident beam on matrix, and the signal that escapes
    ax.add_patch(FancyArrowPatch((26, 60), (26, SURF + 0.6), arrowstyle="-|>",
                                 mutation_scale=9, color=J.ACCENT, lw=1.1, zorder=5))
    ax.add_patch(Polygon([(26, SURF), (21.5, SURF - 5.0), (26, SURF - 8.5),
                          (30.5, SURF - 5.0)], closed=True, facecolor="white",
                         edgecolor=J.ACCENT, linewidth=0.7, linestyle=(0, (2, 1.4)),
                         zorder=4))
    for dx in (-9, 9):
        ax.add_patch(FancyArrowPatch((26, SURF + 0.6), (26 + dx * 1.5, 56),
                                     arrowstyle="-|>", mutation_scale=8, color=J.INK,
                                     lw=0.8, zorder=5))

    # incident beam into the crack mouth: what leaves is intercepted by the crack walls
    ax.add_patch(FancyArrowPatch((57, 60), (57, SURF - 0.4), arrowstyle="-|>",
                                 mutation_scale=9, color=J.ACCENT, lw=1.1, zorder=5))
    ax.add_patch(FancyArrowPatch((57.4, 22), (66, 31), arrowstyle="-|>",
                                 mutation_scale=8, color=J.G_MID, lw=0.8, zorder=3))
    ax.plot([64.4, 67.6], [29.4, 32.6], color=J.ROI, lw=1.0, zorder=6)
    ax.plot([64.4, 67.6], [32.6, 29.4], color=J.ROI, lw=1.0, zorder=6)
    ax.text(69.5, 31, "blocked by\nthe crack wall", fontsize=J.TICK, ha="left",
            va="center", color=J.G_DARK, linespacing=1.2, zorder=8)
    ax.text(57, 12.5, "crack", fontsize=J.TICK, ha="center", va="top", color=J.INK,
            zorder=8)

    ax.add_patch(Rectangle((8, 53), 22, 7, facecolor="white", edgecolor=J.INK,
                           linewidth=0.7, zorder=7))
    ax.text(19, 56.5, "detector", fontsize=J.TICK, ha="center", va="center",
            color=J.INK, zorder=8)
    ax.text(63, 58, "electron beam", fontsize=J.TICK, ha="left", va="center",
            color=J.ACCENT, zorder=8)


def txm_schematic(ax):
    """Beam through the whole specimen, recorded behind it."""
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 62)
    ax.set_axis_off()
    L, R = 30.0, 68.0
    ax.add_patch(Rectangle((L, 12), R - L, 44, facecolor=J.G_LIGHT, edgecolor=J.G_DARK,
                           linewidth=0.7, zorder=1))
    ax.text((L + R) / 2, 1.0, "specimen,\nwhole thickness", fontsize=J.TICK,
            ha="center", va="bottom", color=J.G_DARK, linespacing=1.2, zorder=6)

    # a crack INSIDE the specimen -- it never reaches a surface, and that is the point
    ax.add_patch(Polygon([(38, 34), (52, 38.5), (60, 36.5), (52, 35.7), (38, 32.6)],
                         closed=True, facecolor=J.INK, edgecolor="none", zorder=4))

    ax.add_patch(Rectangle((80, 12), 6, 44, facecolor="white", edgecolor=J.INK,
                           linewidth=0.7, zorder=7))
    ax.text(88.5, 34, "detector", fontsize=J.TICK, ha="left", va="center", rotation=90,
            color=J.INK, zorder=8)
    ax.text(2, 52, "X-ray\nbeam", fontsize=J.TICK, ha="left", va="center",
            color=J.ACCENT, linespacing=1.25, zorder=8)

    for y, through in ((44.0, False), (35.5, True)):
        ax.add_patch(FancyArrowPatch((6, y), (79.4, y), arrowstyle="-|>",
                                     mutation_scale=9, lw=1.1, zorder=5,
                                     color=J.ACCENT if through else J.G_MID))
    ax.annotate("crosses the crack", xy=(50, 35.5), xytext=(45, 23.0),
                fontsize=J.TICK, ha="center", va="top", color=J.ACCENT, zorder=8,
                arrowprops=dict(arrowstyle="-", color=J.ACCENT, lw=0.7,
                                shrinkA=1, shrinkB=1))
    ax.text(49, 57.5, "crosses solid material only", fontsize=J.TICK, ha="center",
            va="bottom", color=J.G_DARK, zorder=8)


def main():
    data = {t: BM.load(t) for t in ("sem", "txm")}
    con = json.load(open(CONTRAST)) if os.path.exists(CONTRAST) else None
    if con is None:
        raise SystemExit(
            f"{CONTRAST} is missing. Run analysis/research/improve/modality_contrast.py "
            f"first -- panel (e) reports a measurement and must not be drawn from a "
            f"remembered number.")

    W = J.PAGEW
    M = 0.03
    GAP = 0.16
    CW = (W - 2 * M - GAP) / 2
    HDR = 0.36
    SCH = 1.66
    NOTE = 0.80
    IMG = 1.42
    CAPG = 0.30
    CHART = 1.24
    Htot = M + HDR + SCH + NOTE + IMG + CAPG + CHART + 0.30 + M

    fig = plt.figure(figsize=(W, Htot))

    def ax_at(xin, yin, win, hin):
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    arms = (
        ("sem", "Scanning electron microscopy", sem_schematic,
         "The signal escapes from a shallow volume just under the polished surface, so "
         "a pixel reports ONE plane. A crack is seen where it cuts that plane; how far "
         "it runs below is invisible."),
        ("txm", "Transmission X-ray microscopy", txm_schematic,
         "The beam crosses the whole specimen and is recorded behind it, so a pixel "
         "reports everything along one line of sight. A crack anywhere in the thickness "
         "changes it, and its apparent opening is the widest along the ray."),
    )

    letters = iter("abcd")
    notes = {}
    for i, (tag, title, draw, prose) in enumerate(arms):
        x0 = M + i * (CW + GAP)
        hx = ax_at(x0, M, CW, HDR)
        hx.set_axis_off()
        hx.text(0.5, 0.9, title, fontsize=J.BODY, fontweight="bold", ha="center",
                va="top", color=J.INK, transform=hx.transAxes)

        sx = ax_at(x0, M + HDR, CW, SCH)
        draw(sx)
        # placed by hand, not J.panel_label: its outside form sits at x = -0.02 of the
        # axes, which for the left column of a full-width figure is off the page
        sx.text(0.0, 1.03, f"({next(letters)})", transform=sx.transAxes,
                fontsize=J.PANEL, fontweight="bold", va="bottom", ha="left", color=J.INK)

        nx = ax_at(x0, M + HDR + SCH, CW, NOTE)
        nx.set_axis_off()
        # WRAPPED BY HAND. matplotlib's own `wrap=True` wraps to the FIGURE, not to the
        # axes, so in a two-column layout the left column's prose ran straight across the
        # right column's. 54 characters is the width of this column at 8 pt Arial.
        nx.text(0, 1.0, textwrap.fill(prose, 54), fontsize=J.TICK, ha="left", va="top",
                color=J.G_DARK, transform=nx.transAxes, linespacing=1.32)

    for i, (tag, title, _draw, _prose) in enumerate(arms):
        d = data[tag]
        sl, H, nm = crop_at(d, FOV_UM)
        x0 = M + i * (CW + GAP)
        ix = ax_at(x0 + (CW - IMG) / 2, M + HDR + SCH + NOTE, IMG, IMG)
        ix.imshow(stretch(d["img"][sl]), cmap="gray", vmin=0, vmax=1,
                  interpolation="nearest")
        J.micrograph(ix)
        ix.add_patch(Rectangle((0, 0), 1, 1, transform=ix.transAxes, fill=False,
                               edgecolor=J.INK, linewidth=0.8, zorder=30))
        J.panel_label(ix, next(letters), inside=True)
        scalebar(ix, nm, H, fontsize=J.TICK)
        notes[tag] = {"fov_um": FOV_UM, "window_px": int(H), "nm_per_px": nm,
                      "field": str(d["field"])}

    cg = ax_at(M, M + HDR + SCH + NOTE + IMG, W - 2 * M, CAPG)
    cg.set_axis_off()
    cg.text(0.5, 0.95,
            f"(c) and (d) are the same {FOV_UM:g} µm field of view, so the two "
            f"appearances are directly comparable.", fontsize=J.TICK, ha="center",
            va="top", color=J.G_DARK, transform=cg.transAxes)

    # --- (e) the detector's own axis ------------------------------------------------
    ax = ax_at(M + 0.56, M + HDR + SCH + NOTE + IMG + CAPG, W - 2 * M - 0.66,
               CHART - 0.34)
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
        ax.plot(k + jit, ks, "o", ms=2.8, mfc=colour, mec="white", mew=0.3,
                linestyle="none", zorder=3)
        ax.plot([k - 0.30, k + 0.30], [np.median(ks)] * 2, color=J.INK, lw=1.4, zorder=4)
    # LOGARITHMIC, because one SEM frame's painted crack sits at 52 MAD multiples and on
    # a linear axis it flattens every other frame onto the baseline. The quantity is a
    # ratio to a frame's own spread, so a log axis is its natural one.
    ax.set_yscale("log")
    ax.axhline(con["mad_k"], color=J.ROI, lw=1.0, zorder=2)
    ax.text(-0.52, con["mad_k"] * 1.18, f"k = {con['mad_k']:g}", fontsize=J.TICK,
            va="bottom", ha="left", color=J.ROI)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([c[0] for c in cols], fontsize=J.TICK)
    ax.set_xlim(-0.6, len(cols) - 0.4)
    ax.set_ylabel("darkness, in\nMAD multiples", fontsize=J.TICK, linespacing=1.2)
    ax.tick_params(labelsize=J.TICK)
    ax.set_yticks([1, 2, 5, 10, 20, 50])
    ax.set_yticklabels(["1", "2", "5", "10", "20", "50"], fontsize=J.TICK)
    ax.minorticks_off()
    J.panel_label(ax, "e")

    ex = ax_at(M, Htot - M - 0.30, W - 2 * M, 0.30)
    ex.set_axis_off()
    ntot = len(con["SEM"]["per_frame"]) + len(con["TXM"]["per_frame"])
    ex.text(0.5, 0.92,
            f"(e) one point per frame, bar at the median; {nbelow} of {ntot} frames "
            f"fall below the line.",
            fontsize=J.TICK, ha="center", va="top", color=J.G_DARK,
            transform=ex.transAxes)

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "(a), (b) schematics of image formation, drawn by hand and not to scale; "
                "(c), (d) real micrographs at a matched field of view; (e) a measurement "
                "over both corpora",
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
        "note": "panels (a) and (b) are schematics and are labelled as such; no "
                "mechanism is claimed for the sign of the TXM contrast, because the "
                "radiometric convention of the stored arrays is not recorded in any of "
                "the three repositories",
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
