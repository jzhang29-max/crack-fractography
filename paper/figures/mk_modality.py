#!/usr/bin/env python3
"""Figure 2: one crack, two measurement geometries, and what the criterion can reach.

WHY. The paper measures the same quantity in two microscopies and carries a detector
written for one across to the other. Whether that is reasonable depends entirely on what
each instrument records, and the paper asserted the difference in a clause.

ONE SCHEMATIC, NOT TWO. The two geometries are drawn on ONE block of material containing
ONE crack: the electron beam arrives at the polished top face and the signal has to
escape back out of it, so what that instrument records is the line where the crack cuts
that face; the X-ray beam crosses the whole thickness to a detector behind, so what IT
records is the crack's silhouette along the beam. The same crack, two different
measurands. The two are in practice different specimen preparations -- a polished section
and a transmission specimen -- and the caption says so; drawing them on one block is what
makes the two measurands comparable at a glance.

THE REAL MICROGRAPHS ARE MOUNTED ON THE SCHEMATIC, which is the change this revision
makes. They used to be two separate panels underneath it, so a reader had to carry the
drawing in their head down to the photographs and decide for themselves which part of the
drawing each one corresponded to. Each is now at the instrument that produces it: the SEM
field sits where the electron detector was drawn, with the escaping signal arriving at
it, and the TXM field sits beside the transmission detector the beam is drawn reaching.
They are REAL ARRAYS of the same two fields the rest of the paper uses, at a matched 15
micrometre field of view so that the two appearances can be compared without converting
pixel sizes, and they carry their own scale bars. Nothing about them is schematic.

NO SENTENCES INSIDE THE ARTWORK. What is left on the plate is naming: the two beams, the
polished surface, the crack, the two things each instrument records, and the two
instrument names over their images. Two three-line annotations that explained the
geometry in prose have gone to the caption, which is where the review asked for them.

(b) IS A MEASUREMENT AND IS HERE BECAUSE THE OBVIOUS CAPTION FOR THE SCHEMATIC IS WRONG.
"A void crosses less material, so it transmits more, so it reads bright" does not
describe this corpus: a crack reads DARKER than the painted not-crack on most TXM frames
too, and the radiometric convention of the stored arrays is not recorded anywhere in the
three repositories, so no mechanism is offered for that. What (b) plots is the quantity
the detector actually thresholds: per pixel, the largest MAD multiplier at which the
multiscale darkness union would still propose it, summarised per frame over the pixels a
human painted as crack, against the operating point.

(c) IS WHAT THAT AXIS COSTS. The same per-frame quantity against the share of the painted
crack the deployed rule actually proposes, which turns (b) from a diagnostic into a
consequence: below the operating point the share collapses, and the frames that sit below
it are not evenly distributed between the two microscopies.

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
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

import both_modalities as BM                        # noqa: E402
import journal_style as J                           # noqa: E402

J.use()
OUT = _paths.FIG_DIR
NAME = "F2 - how each modality sees a crack"
# The restricted record: the paper reports on specimen series b2 and b3. `scoped()`
# raises rather than falling back, so this panel cannot silently draw 31 frames under a
# caption that says 18.
CONTRAST = _paths.scoped("modality_contrast.json")
MU = "µ"

#: The matched field of view the two mounted micrographs are shown at. 15 um is 289 px of
#: SEM and 513 px of TXM; showing both at the same number of PIXELS, as a naive side by
#: side would, compares a 27 um field with a 15 um one and makes the TXM crack look
#: 1.8x wider than it is.
FOV_UM = 15.0
#: The scale bar drawn on each mounted micrograph, in micrometres. One value for both,
#: because the two are at a matched field of view and the bar is the proof of it.
BAR_UM = 5.0

#: The specimen groups the TXM arm is reported in, in the order they are drawn. Set from
#: the data rather than hard-coded, so a group that leaves the corpus leaves the figure.
GROUP_ORDER = ("B3", "B2")


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
    """Display stretch, identical for both modalities and shared with Figure 1.

    The range comes from `both_modalities.display_range`: median plus and minus
    three robust standard deviations, which tracks the matrix and lets a crack
    saturate. A 2nd-to-98th percentile pair, which this used to be, puts its low
    end inside the crack on a frame with a large dark tail and washes the matrix
    out. DISPLAY ONLY: the detector ran on the unstretched array.
    """
    from skimage import exposure
    lo, hi = BM.display_range(arr)
    return exposure.rescale_intensity(arr.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0.0, 1.0))


# ----------------------------------------------------------------- the one schematic
#: The canvas panel (a) is drawn on. The panel is laid out at exactly this aspect, so one
#: unit across is one unit up and a square in these coordinates prints square.
CANVAS = (100.0, 33.0)
#: The oblique projection the block is drawn in. A point (x, y, z) in the specimen's own
#: coordinates -- x across, y up, z into the depth -- lands at (x + KZ*z, y + KY*z).
KZ, KY = 0.40, 0.30
#: The block, in those coordinates, and where its near-bottom-left corner sits on the
#: canvas.
BW, BH, BD = 30.0, 16.0, 13.0
OX, OY = 31.5, 1.0
#: How far the transmission detector sits behind the block, and how thick it is drawn.
DGAP, DTHICK = 6.0, 1.6
#: The two mounted micrographs, as (left, bottom, side) on the canvas. Square, equal, and
#: at the same height, so neither instrument is given the larger picture.
IMSIDE = 21.5
SEM_BOX = (1.0, 6.3)
TXM_BOX = (77.5, 6.3)


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

    Binned over z and reduced with a maximum, because the track doubles back on itself --
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


def mount(ax, arr, box, colour, title, nm_per_px, win_px):
    """Put one REAL micrograph on the schematic, framed, titled and with a scale bar.

    The schematic's axes are in canvas units, not pixels, so `scalebar()` -- which assumes
    an imshow axes whose x units are pixels -- cannot be used here and the bar is drawn in
    canvas units from the window's own field of view. Its length is returned so the
    caption can state it instead of re-deriving it.
    """
    x0, y0 = box
    s = IMSIDE
    ax.imshow(arr, cmap="gray", vmin=0, vmax=1, interpolation="nearest",
              extent=(x0, x0 + s, y0, y0 + s), aspect="auto", zorder=9)
    ax.add_patch(Rectangle((x0, y0), s, s, fill=False, edgecolor=colour, lw=1.1,
                           zorder=11))
    ax.text(x0 + s / 2, y0 + s + 0.7, title, fontsize=J.BODY, fontweight="bold",
            ha="center", va="bottom", color=colour, zorder=11)
    # the bar, in canvas units, from the window's own field of view
    blen = s * (BAR_UM * 1000.0 / nm_per_px) / win_px
    bx1 = x0 + s - 0.055 * s
    by = y0 + 0.055 * s
    ax.add_patch(Rectangle((bx1 - blen - 0.3, by - 0.3), blen + 0.6, 2.1,
                           facecolor="white", edgecolor="none", zorder=12))
    ax.add_patch(Rectangle((bx1 - blen, by), blen, 0.42, facecolor=J.INK,
                           edgecolor="none", zorder=13))
    ax.text(bx1 - blen / 2, by + 0.62, f"{BAR_UM:g} {MU}m", fontsize=J.TICK,
            ha="center", va="bottom", color=J.INK, zorder=13)
    return blen


def combined_schematic(ax, data, crops):
    """One block, one crack, both instruments, and the real image each one produces."""
    ax.set_xlim(0, CANVAS[0])
    ax.set_ylim(0, CANVAS[1])
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

    # --- the electron column: in at the surface, out to the image it produces ---------
    bx, bz = x[len(x) // 2], z[len(z) // 2]
    hit = _p(bx, BH, bz)
    ax.add_patch(FancyArrowPatch((hit[0], hit[1] + 9.0), (hit[0], hit[1] + 0.5),
                                 arrowstyle="-|>", mutation_scale=9, color=J.ACCENT,
                                 lw=1.1, zorder=8))
    ax.text(hit[0] + 1.3, hit[1] + 8.8, "electron beam", fontsize=J.TICK, ha="left",
            va="top", color=J.ACCENT, zorder=9)
    # a small fan of escaping signal rather than one arrow: it is what the detector
    # collects, and one arrow reads as a reflection. It now lands on the SEM image,
    # because the image IS what the detector produces.
    sx0, sy0 = SEM_BOX
    for fy_ in (0.66, 0.40):
        ax.add_patch(FancyArrowPatch((hit[0] - 1.2, hit[1] + 0.6),
                                     (sx0 + IMSIDE + 0.4, sy0 + fy_ * IMSIDE),
                                     arrowstyle="-|>", mutation_scale=7, color=J.INK,
                                     lw=0.7, zorder=8))

    # --- the X-ray beam: through the whole block to a detector behind it --------------
    # AT THE HEIGHT OF THE CRACK, not below it. An early version put the three rays under
    # the sheet entirely, so they crossed nothing and the silhouette drawn on the
    # detector contradicted the picture that was meant to produce it.
    ybeam = BH - 0.55 * float(depth.mean())
    for zz in (2.5, 6.5, 10.5):
        ax.add_patch(FancyArrowPatch(_p(-5.0, ybeam, zz),
                                     _p(BW + DGAP - 1.4, ybeam, zz),
                                     arrowstyle="-|>", mutation_scale=8,
                                     color=J.ACCENT2, lw=1.0, zorder=7))
    lx = _p(-5.0, ybeam, 10.5)[0]
    ax.text(lx, _p(-5.0, ybeam, 2.5)[1] - 1.2, "X-ray beam", fontsize=J.TICK,
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
    # and from that detector plane to the image it produces
    # TO THE IMAGE IT PRODUCES. Drawn at the same weight as the fan on the electron
    # side, so the two instruments read symmetrically: each one has its output attached
    # to it. At the lighter weight it was a stub a reader could miss entirely.
    dtop = _p(BW + DGAP + DTHICK, BH * 0.62, BD * 0.5)
    tx0, ty0 = TXM_BOX
    ax.add_patch(FancyArrowPatch((dtop[0] + 0.3, dtop[1]),
                                 (tx0 - 0.5, ty0 + 0.52 * IMSIDE),
                                 arrowstyle="-|>", mutation_scale=9, color=J.INK,
                                 lw=1.0, zorder=8))

    # --- the two measurands, named rather than described ------------------------------
    t0 = _p(x[18], BH, z[18])
    ax.annotate("surface trace", xy=(t0[0], t0[1]), xytext=(t0[0] - 3.0, 31.5),
                fontsize=J.TICK, ha="center", va="top", color=J.ACCENT, zorder=10,
                arrowprops=dict(arrowstyle="-", color=J.ACCENT, lw=0.7, shrinkA=2,
                                shrinkB=2))
    s0 = _p(BW + DGAP, BH - 3.0, float(np.median(zg)))
    ax.annotate("projected silhouette", xy=(s0[0], s0[1]),
                xytext=(s0[0] + 2.0, 31.5), fontsize=J.TICK, ha="center", va="top",
                color=J.ACCENT2, zorder=10,
                arrowprops=dict(arrowstyle="-", color=J.ACCENT2, lw=0.7, shrinkA=2,
                                shrinkB=2))
    k = len(x) // 5
    cf = _p(x[k], BH - 0.55 * depth[k], z[k])
    ax.annotate("crack", xy=cf, xytext=(cf[0] - 1.5, cf[1] - 8.0), fontsize=J.TICK,
                ha="right", va="top", color=J.INK, zorder=10,
                arrowprops=dict(arrowstyle="-", color=J.INK, lw=0.7, shrinkA=2,
                                shrinkB=2))

    # --- and the two real images, at the instruments that produce them ----------------
    bars = {}
    for tag, box, colour, title in (("sem", SEM_BOX, J.ACCENT, "SEM"),
                                    ("txm", TXM_BOX, J.ACCENT2, "TXM")):
        d = data[tag]
        sl, win, nm = crops[tag]
        bars[tag] = mount(ax, stretch(d["img"][sl]), box, colour, title, nm, win)
    return bars


def groups_present(con):
    """The TXM groups the measurement file actually holds, in the reported order.

    Driven by the data. When the corpus is restricted to a subset of specimen series the
    figure follows without an edit here, and a group that is still present cannot be
    dropped from the plate by forgetting to list it.
    """
    have = {r.get("group") for r in con["TXM"]["per_frame"]}
    out = [g for g in GROUP_ORDER if g in have]
    extra = sorted(have - set(GROUP_ORDER) - {None})
    if extra:
        raise SystemExit(f"TXM groups {extra} are in the measurement file but not in "
                         f"GROUP_ORDER -- add them rather than letting them vanish")
    return out


def main():
    data = {t: BM.load(t) for t in ("sem", "txm")}
    crops = {t: crop_at(data[t], FOV_UM) for t in ("sem", "txm")}
    if not os.path.exists(CONTRAST):
        raise SystemExit(
            f"{CONTRAST} is missing. Run analysis/research/improve/modality_contrast.py "
            f"first -- panels (b) and (c) report a measurement and must not be drawn "
            f"from a remembered number.")
    con = json.load(open(CONTRAST))
    order = groups_present(con)

    W = J.PAGEW
    M = 0.03
    SCH = (W - 2 * M) * CANVAS[1] / CANVAS[0]
    ROWGAP = 0.26
    PH = 1.26                      # the two chart panels
    XL = 0.36
    YL = 0.52                      # the y label and tick labels of each chart
    CGAP = 0.52
    PW = (W - 2 * M - 2 * YL - CGAP) / 2.0
    Htot = M + SCH + ROWGAP + PH + XL + M

    fig = plt.figure(figsize=(W, Htot))

    def ax_at(xin, yin, win, hin):
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    sx = ax_at(M, M, W - 2 * M, SCH)
    bars = combined_schematic(sx, data, crops)
    sx.text(0.0, 0.995, "(a)", transform=sx.transAxes, fontsize=J.PANEL,
            fontweight="bold", va="top", ha="left", color=J.INK)

    yrow = M + SCH + ROWGAP

    # --- (b) the detector's own axis, per frame ---------------------------------------
    ax = ax_at(M + YL, yrow, PW, PH)
    cols = [("SEM", con["SEM"]["per_frame"], J.ACCENT)]
    for g in order:
        rows = [r for r in con["TXM"]["per_frame"] if r.get("group") == g]
        cols.append((f"TXM\n{g}", rows, J.ACCENT2))
    rng = np.random.default_rng(0)
    for k, (lab, rows, colour) in enumerate(cols):
        ks = [r["median_critical_k_crack"] for r in rows]
        jit = rng.uniform(-0.17, 0.17, len(ks))
        ax.plot(k + jit, ks, "o", ms=2.8, mfc=colour, mec="white", mew=0.3,
                linestyle="none", zorder=3)
        ax.plot([k - 0.30, k + 0.30], [np.median(ks)] * 2, color=J.INK, lw=1.4, zorder=4)
    # LOGARITHMIC, because one SEM frame's painted crack sits at 52 MAD multiples and on
    # a linear axis it flattens every other frame onto the baseline. The quantity is a
    # ratio to a frame's own spread, so a log axis is its natural one.
    ax.set_yscale("log")
    ax.axhline(con["mad_k"], color=J.ROI, lw=1.0, zorder=2)
    ax.text(len(cols) - 0.45, con["mad_k"] * 1.14, f"k = {con['mad_k']:g}",
            fontsize=J.TICK, va="bottom", ha="right", color=J.ROI)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([c[0] for c in cols], fontsize=J.TICK)
    ax.set_xlim(-0.6, len(cols) - 0.4)
    ax.set_ylabel("darkness of painted crack,\nin MAD multiples", fontsize=J.TICK,
                  linespacing=1.2)
    ax.tick_params(labelsize=J.TICK)
    ax.set_yticks([1, 2, 5, 10, 20, 50])
    ax.set_yticklabels(["1", "2", "5", "10", "20", "50"], fontsize=J.TICK)
    ax.minorticks_off()
    J.panel_label(ax, "b")

    # --- (c) and what that axis costs -------------------------------------------------
    cx = ax_at(M + 2 * YL + PW + CGAP - YL, yrow, PW, PH)
    for lab, rows, colour, mark in (
            ("SEM", con["SEM"]["per_frame"], J.ACCENT, "o"),
            ("TXM", con["TXM"]["per_frame"], J.ACCENT2, "s")):
        xs = [r["median_critical_k_crack"] for r in rows]
        ys = [100.0 * r["crack_px_proposed_frac"] for r in rows]
        cx.plot(xs, ys, mark, ms=3.2, mfc=colour, mec="white", mew=0.3,
                linestyle="none", label=lab, zorder=3)
    cx.axvline(con["mad_k"], color=J.ROI, lw=1.0, zorder=2)
    cx.set_xscale("log")
    cx.set_xticks([1, 2, 5, 10, 20, 50])
    cx.set_xticklabels(["1", "2", "5", "10", "20", "50"], fontsize=J.TICK)
    cx.minorticks_off()
    cx.set_ylim(-4, 104)
    cx.set_xlabel("darkness of painted crack, in MAD multiples", fontsize=J.TICK)
    cx.set_ylabel("painted crack proposed (%)", fontsize=J.TICK)
    cx.tick_params(labelsize=J.TICK)
    cx.legend(loc="upper left", fontsize=J.TICK, handletextpad=0.3, borderpad=0.2)
    J.panel_label(cx, "c")

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "(a) one schematic of both measurement geometries on one crack, drawn "
                "by hand and not to scale, with the REAL micrograph each instrument "
                "produces mounted at that instrument; (b) and (c) measurements over "
                "both corpora",
        "mounted_micrographs": {
            t: {"field": str(data[t]["field"]), "fov_um": FOV_UM,
                "window_px": int(crops[t][1]), "nm_per_px": crops[t][2],
                "scale_bar_um": BAR_UM, "scale_bar_canvas_units": round(bars[t], 3),
                "display": "2nd-98th percentile stretch, identical for both; the "
                           "detector ran on the unstretched array"}
            for t in ("sem", "txm")},
        "matched_fov_um": FOV_UM,
        "panel_b": {
            "plots": "median over each frame's painted-crack pixels of the largest MAD "
                     "multiplier at which the deployed multiscale darkness union would "
                     "still propose that pixel",
            "definition": con["critical_k_definition"],
            "operating_point": con["mad_k"],
            "groups_drawn": order,
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
        "panel_c": {
            "plots": "the same per-frame quantity against the share of that frame's "
                     "painted crack pixels the deployed rule proposes, one point per "
                     "frame, both corpora on one pair of axes",
            "note": "the share is of PAINTED crack only; pixels no operator ruled on "
                    "are excluded from both axes",
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
                "different specimen preparations, which the caption states. The two "
                "images mounted on it are not schematic: they are real arrays of the "
                "two fields the rest of the paper uses, at a matched field of view. No "
                "mechanism is claimed for the sign of the TXM contrast, because the "
                "radiometric convention of the stored arrays is not recorded in any of "
                "the three repositories. No sentence appears inside the artwork.",
    }, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)
    for tag in ("SEM", "TXM"):
        c = con[tag]
        print(f"  {tag}  n = {c['n_frames']:<3} median critical k "
              f"{c['median_of_median_critical_k_crack']:+.2f}, below k = {con['mad_k']:g} "
              f"on {c['frames_median_critical_k_below_k']}, median "
              f"{100 * c['median_crack_px_proposed_frac']:.1f}% of painted crack proposed")
    for g in order:
        r = con["TXM"]["by_group"][g]
        print(f"       {g:<8} n = {r['n']:<3} median k "
              f"{r['median_of_median_critical_k_crack']:+.2f}, "
              f"{100 * r['median_crack_px_proposed_frac']:.0f}% proposed")


if __name__ == "__main__":
    main()
