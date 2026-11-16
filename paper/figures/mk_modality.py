#!/usr/bin/env python3
"""Figure 2: one crack, two measurement geometries.

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

THE REAL MICROGRAPHS ARE MOUNTED ON THE SCHEMATIC. They used to be two separate panels
underneath it, so a reader had to carry the drawing in their head down to the photographs
and decide for themselves which part of the drawing each one corresponded to. Each is now
at the instrument that produces it: the SEM field sits where the escaping signal arrives,
and the TXM field sits beside the transmission detector the beam is drawn reaching. They
are REAL ARRAYS of the same two fields the rest of the paper uses, at a matched field of
view so that the two appearances can be compared without converting pixel sizes, and they
carry their own scale bars. Nothing about them is schematic.

NO SENTENCES INSIDE THE ARTWORK. What is left on the plate is naming: the load axis and
the gauge section it came from, the two beams, the polished surface, the crack, the
detector, the two things each instrument records, and the two instrument names over their
images. Each mounted image repeats the name of the measurand it shows, so the photograph
and the part of the drawing that produces it carry the same words.

THE DRAWING IS BUILT, NOT SKETCHED. Every face of the block, the specimen and the
detector is filled with a gradient under one light direction (upper left, front), and
every solid casts the same soft shadow, so the oblique projection reads as a solid rather
than as flat polygons. Line weights are from one ladder -- 1.0 for an object's outline,
0.7 for an internal edge, 0.55 for a leader -- and leaders end in a dot on the thing they
name. The two output arrows are explicit cubic Beziers rather than straight lines,
because the only straight route from the beam's impact point to the SEM image passes
through the solid, which is what the first version drew.

(b) AND (c) ARE NOT DRAWN IN THIS REVISION. They plotted the detector's own darkness axis
over both corpora. The measurement is still read here and still recorded in the caption
file beside the plate -- the manuscript quotes it from the restricted record, and the
numbers must not drift apart -- but the plate itself is the schematic alone.

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
from matplotlib.patches import (FancyArrowPatch, PathPatch,  # noqa: E402
                                Polygon, Rectangle)

import both_modalities as BM                        # noqa: E402
import journal_style as J                           # noqa: E402

J.use()
#: SECTION HATCHING IS TYPE-WEIGHT LINE WORK, not a texture. matplotlib's default hatch
#: stroke is 1.0 pt, which at this plate's size fills the foil in solid grey and reads
#: as a grey block rather than as a cut through material.
matplotlib.rcParams["hatch.linewidth"] = 0.35
OUT = _paths.FIG_DIR
NAME = "F2 - how each modality sees a crack"
# The restricted record: the paper reports on specimen series b2 and b3. `scoped()`
# raises rather than falling back, so this panel cannot silently draw 31 frames under a
# caption that says 18.
CONTRAST = _paths.scoped("modality_contrast.json", scope=False)
MU = "µ"

#: The matched field of view the two mounted micrographs are shown at. The two windows
#: are DIFFERENT pixel counts, because the two recovered pixel sizes differ -- the
#: caption file written beside the plate records both, from the data, rather than
#: repeating them here where they go stale, as the pair of counts that used to stand in
#: this comment had. The difference is the point: showing the two at the same number of
#: PIXELS, as a naive side by side would, puts two different physical fields next to
#: each other and makes one crack look wider than the other when it is not.
FOV_UM = 35.0
#: The scale bar drawn on each mounted micrograph, in micrometres. One value for both,
#: because the two are at a matched field of view and the bar is the proof of it.
BAR_UM = 5.0

#: The specimen groups the TXM arm is reported in, in the order they are recorded. Set
#: from the data rather than hard-coded, so a group that leaves the corpus leaves the
#: record. `CONTRAST` is the FULL-corpus file, which carries the two public-benchmark
#: groups as well as the paper's own b2 and b3; all four are listed so the guard below
#: cannot pass by silence.
GROUP_ORDER = ("B3", "B2", "AM/HC", "Wrought")


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
    # AND THE BIGGEST MARKED REGION IS NOT ALWAYS A CRACK. On the SEM field the
    # detector's largest interior region is the void BEYOND the specimen edge -- far
    # larger than any crack on the frame -- so the window centred on it and the panel
    # came out as a grey band with no crack in it. Darkness cannot tell the two apart,
    # because this detector finds cracks BY their darkness and a crack is dark too.
    # SHAPE can: a crack is long and thin, a void is a blob. Regions elongated at
    # least this much are preferred, and the largest of those wins; if none qualifies
    # the rule falls back to the largest region of any shape.
    from skimage.measure import regionprops
    MIN_ELONG = 3.0
    slim = np.zeros_like(sz)
    for r in regionprops(lab):
        if sz[r.label] == 0:
            continue
        minor = max(float(r.minor_axis_length), 1e-6)
        if float(r.major_axis_length) / minor >= MIN_ELONG:
            slim[r.label] = sz[r.label]
    if slim.any():
        sz = slim
    cy, cx = ndi.center_of_mass(lab == int(sz.argmax()))
    y0 = max(min(int(cy) - H // 2, f.shape[0] - H), 0)
    x0 = max(min(int(cx) - H // 2, f.shape[1] - H), 0)
    # NO SLIDING AWAY FROM THE DARK. An earlier edition slid this window to the
    # position holding the least no-signal area, to get the flat dark band out of the
    # bottom of the SEM panel. On this frame that band is the detector's largest
    # region by two orders of magnitude -- 2.4 million pixels running the full width --
    # and it is the main crack opening, excluded from CENTRING only because it touches
    # the border. Sliding the window off it left a panel of plain grain texture with no
    # crack in it, which is worse than a panel with a wide crack low in the frame.
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


# ----------------------------------------------------------------- the schematic
#: THE LAYOUT, SIXTH EDITION, AND THE AUTHOR DESCRIBED IT: one big dogbone under
#: tension, a region taken from the middle of it, and what each microscope makes of
#: that region.
#:
#: Everything else is subordinate to that sentence. The specimen is the largest object
#: on the plate and it is unmistakably under load. One box in the middle of the gauge
#: is the region. Two leaders run from that box to two panels, and each panel is the
#: REAL micrograph that instrument produces of such a field, with one line saying what
#: that instrument is actually recording.
#:
#: WHAT THIS DROPS, AND WHY THAT IS THE POINT. Five earlier editions put the apparatus
#: at the centre: shaded solids, engineering line art, two full ray diagrams, a
#: four-element geometry, an isometric cut-away. Each of them answered "how does the
#: instrument work" when the question the figure is for is "where did these two
#: pictures come from, and why do they disagree". The specimen-to-region-to-two-views
#: chain answers that in one read, and the measurand difference survives as one line
#: of text under each panel rather than as a drawing of its own.
CANVAS = (100.0, 78.5)

LW_OUT, LW_EDGE, LW_LEAD = 1.0, 0.6, 0.6

#: The specimen. It is the figure, so it gets the full width and a real thickness.
DB_Y = 66.5
DB_CX, DB_HALF = 50.0, 38.0
DB_WGRIP, DB_WGAUGE = 7.0, 3.1
#: The region taken out of the middle of the gauge.
ROI_W, ROI_H = 7.0, 7.4

#: The two panels the region opens onto, and above each of them the geometry of the
#: instrument that produced it. Four elements per arm and no more: a source, the beam
#: as a filled cone, the foil, and a detector. That is enough to say how the two
#: machines work and why they cannot record the same thing, and it is what published
#: figures of this kind draw -- see docs/FIGURE_CONVENTIONS_FROM_PUBLISHED_WORK.md.
PAN_Y, PAN_SIDE = 3.0, 24.0
PAN_X = (9.0, 65.5)
GEO_Y0, GEO_H = 31.8, 16.5        # the how-it-works strip, between region and panel
FOIL_T = 2.6                      # the foil, in the little geometry drawing

FOIL_UM = 22.0


def _dogbone_h(cx, x0, x1, wg, wn):
    """The specimen in plan: two grips, filleted shoulders, a waisted gauge."""
    from matplotlib.path import Path as MPath
    s1, s2 = x0 + 0.27 * (x1 - x0), x1 - 0.27 * (x1 - x0)
    f = 3.4
    v, c = [], []

    def M(p):
        v.append(p); c.append(MPath.MOVETO)

    def L(p):
        v.append(p); c.append(MPath.LINETO)

    def C(a, b, p):
        v.extend([a, b, p]); c.extend([MPath.CURVE4] * 3)

    M((x0, DB_Y + wg))
    L((s1 - f, DB_Y + wg))
    C((s1 - f * 0.3, DB_Y + wg), (s1 + f * 0.3, DB_Y + wn), (s1 + f, DB_Y + wn))
    L((s2 - f, DB_Y + wn))
    C((s2 - f * 0.3, DB_Y + wn), (s2 + f * 0.3, DB_Y + wg), (s2 + f, DB_Y + wg))
    L((x1, DB_Y + wg))
    L((x1, DB_Y - wg))
    L((s2 + f, DB_Y - wg))
    C((s2 + f * 0.3, DB_Y - wg), (s2 - f * 0.3, DB_Y - wn), (s2 - f, DB_Y - wn))
    L((s1 + f, DB_Y - wn))
    C((s1 + f * 0.3, DB_Y - wn), (s1 - f * 0.3, DB_Y - wg), (s1 - f, DB_Y - wg))
    L((x0, DB_Y - wg))
    v.append((x0, DB_Y + wg)); c.append(MPath.CLOSEPOLY)
    return MPath(v, c)


def cell(ax):
    """The electrochemical cell the specimen sits in WHILE the transmission arm images.

    WHY THIS IS ON THE PLATE AT ALL. Without it the schematic says the two
    microscopies look at one loaded specimen, and that is not the experiment. The load
    and the hydrogen charging belong to the transmission measurement, which is in situ:
    the specimen is pulled and charged while it is being imaged, so the series records
    an evolving crack. The electron measurement is post mortem -- it looks at the
    specimen afterwards, unloaded, and sees one final state. Drawing one loaded
    specimen feeding both arms asserted that both were in situ, which is wrong and is
    exactly the kind of error a schematic makes silently.
    """
    #: DRAWN AS A VESSEL, NOT AS A COLOURED BLOCK. The first version of this was a
    #: saturated flat rectangle behind the specimen with its label floating inside it,
    #: and the author's verdict was "very cartoonish". It was: a filled block of colour
    #: is the heaviest mark on a sheet whose every other element is thin grey line art,
    #: so the cell read as the subject of the figure rather than as the condition the
    #: specimen is under. The information it carries is unchanged; the weight is not.
    #:
    #: Three changes do it. The electrolyte is a faint tint with NO edge of its own
    #: instead of a saturated fill with a hard border. The vessel is open at the top
    #: and drawn on three sides, which is how a cell cross-section is drawn and which
    #: stops the box from reading as a sealed container floating around the gauge. And
    #: the electrode is a slim bar with a lead leaving the cell, rather than a thick
    #: slab, so it reads as an electrode and not as part of the specimen.
    cy0, cy1 = DB_Y - 9.6, DB_Y + 9.6
    cx0, cx1 = DB_CX - 17.0, DB_CX + 17.0
    surf = DB_Y + 7.4                      # the electrolyte surface, below the rim
    ax.add_patch(Rectangle((cx0, cy0), cx1 - cx0, surf - cy0, facecolor="#eef4f9",
                           edgecolor="none", zorder=1))
    ax.plot([cx0, cx1], [surf, surf], color=J.G_MID, lw=LW_EDGE, zorder=2)
    ax.plot([cx0, cx0, cx1, cx1], [cy1, cy0, cy0, cy1], color=J.G_DARK,
            lw=LW_EDGE, zorder=2, solid_joinstyle="miter")
    #: THE COUNTER ELECTRODE LIES BELOW THE SPECIMEN, parallel to it. Drawn upright
    #: beside the gauge it crossed the dogbone, which is painted over it, so it came
    #: out as two disconnected grey stubs above and below the specimen -- a bar that
    #: appears to pass THROUGH the thing being tested. A counter electrode parallel to
    #: the working electrode is also what the cell actually contains.
    #:
    #: Its lead leaves through the left wall at a height below the specimen's widest
    #: point, which is the one line out of this cell that crosses nothing.
    ey = cy0 + 1.4
    ax.add_patch(Rectangle((cx0 + 3.2, ey), 12.0, 0.85, facecolor="#8d99a1",
                           edgecolor=J.G_DARK, lw=0.4, zorder=3))
    ax.plot([cx0 + 3.2, cx0 - 2.2], [ey + 0.42, ey + 0.42], color=J.G_DARK,
            lw=LW_LEAD, zorder=3)
    #: the label names the electrolyte from inside it, in the clear strip under the
    #: specimen's shoulder -- the one pocket of this sheet nothing else occupies.
    ax.text(cx1 - 1.5, ey - 0.3, "H charging", fontsize=J.TICK, ha="right",
            va="bottom", color=J.G_DARK, zorder=7)
    return cy1


def specimen(ax):
    """The dogbone, gripped and pulled, with the imaged region boxed in its gauge."""
    x0, x1 = DB_CX - DB_HALF, DB_CX + DB_HALF
    ax.add_patch(PathPatch(_dogbone_h(DB_CX, x0, x1, DB_WGRIP, DB_WGAUGE),
                           facecolor="#e4e4e4", edgecolor=J.G_DARK, lw=LW_OUT,
                           zorder=3, joinstyle="round"))
    # the stage's jaws, and the load
    for jx in (x0 - 4.6, x1 + 0.6):
        ax.add_patch(Rectangle((jx, DB_Y - DB_WGRIP - 2.0), 4.0,
                               2 * (DB_WGRIP + 2.0), facecolor="#b4b4b4",
                               edgecolor=J.G_DARK, lw=LW_EDGE, zorder=4))
    for xt, xp, ha in ((x0 - 5.4, x0 - 11.0, "right"), (x1 + 5.4, x1 + 11.0, "left")):
        ax.add_patch(FancyArrowPatch((xt, DB_Y), (xp, DB_Y), arrowstyle="-|>",
                                     mutation_scale=11, lw=1.5, color=J.INK,
                                     zorder=5, shrinkA=0, shrinkB=0))

    rx0, ry0 = DB_CX - ROI_W / 2.0, DB_Y - ROI_H / 2.0
    ax.add_patch(Rectangle((rx0, ry0), ROI_W, ROI_H, fill=False, edgecolor=J.ROI,
                           lw=1.4, zorder=7))
    return rx0, ry0


def leaders(ax, rx0, ry0):
    """From the two bottom corners of the region to the two panels below it."""
    for (cx_, cy_), px in (((rx0, ry0), PAN_X[0] + PAN_SIDE),
                           ((rx0 + ROI_W, ry0), PAN_X[1])):
        ax.plot([cx_, px], [cy_, GEO_Y0 + GEO_H], color=J.ROI, lw=LW_LEAD,
                dashes=(2.6, 1.8), zorder=2)


def how_it_works(ax, x0, colour, kind):
    """Four elements: source, beam, foil, detector. The whole of how each arm works.

    `kind` is "surface" for the electron arm -- the beam lands on the polished face
    and an off-axis detector collects what comes back out of it -- or "through" for
    the transmission arm, where the beam crosses the foil to a detector behind it.
    The two drawings share the foil and differ only in where the detector is, which
    is the entire reason the two arms record different quantities.
    """
    cx = x0 + PAN_SIDE / 2.0
    fy = GEO_Y0 + 5.2                       # the foil's bottom edge
    sy = GEO_Y0 + GEO_H - 2.6               # the source
    fw = PAN_SIDE * 0.88
    fx = cx - fw / 2.0

    ax.add_patch(Rectangle((cx - 3.4, sy), 6.8, 1.1, facecolor=colour,
                           edgecolor="none", zorder=6))
    ax.text(cx + 4.4, sy + 0.5,
            "electron\nsource" if kind == "surface" else "X-ray\nsource",
            fontsize=J.TICK, ha="left", va="center", color=J.INK, zorder=7,
            linespacing=1.15)

    if kind == "surface":
        ax.add_patch(Polygon([(cx - 2.6, sy), (cx + 2.6, sy),
                              (cx + 0.5, fy + FOIL_T), (cx - 0.5, fy + FOIL_T)],
                             closed=True, facecolor=colour, alpha=0.30,
                             edgecolor="none", zorder=4))
        dx0, dx1 = fx - 0.5, fx + 7.2
        dy = fy + FOIL_T + 3.4
        ax.add_patch(Rectangle((dx0, dy), dx1 - dx0, 2.4, facecolor="#c9c9c9",
                               edgecolor=J.G_DARK, lw=LW_EDGE, zorder=6))
        ax.text(0.5 * (dx0 + dx1), dy + 1.2, "detector", fontsize=J.TICK,
                ha="center", va="center", color=J.INK, zorder=7)
        ax.add_patch(FancyArrowPatch((cx - 0.4, fy + FOIL_T + 0.2),
                                     (dx1 - 0.6, dy - 0.3), arrowstyle="-|>",
                                     mutation_scale=6, color=colour, lw=0.7,
                                     zorder=7, shrinkA=0, shrinkB=0,
                                     connectionstyle="arc3,rad=0.25"))
        note = "the signal escapes the surface"
    else:
        ax.add_patch(Polygon([(cx - 2.6, sy), (cx + 2.6, sy),
                              (cx + fw / 2.0, GEO_Y0 + 1.4),
                              (cx - fw / 2.0, GEO_Y0 + 1.4)],
                             closed=True, facecolor=colour, alpha=0.22,
                             edgecolor="none", zorder=4))
        ax.add_patch(Rectangle((fx, GEO_Y0), fw, 1.6, facecolor="#c9c9c9",
                               edgecolor=J.G_DARK, lw=LW_EDGE, zorder=6))
        ax.text(fx + fw + 0.8, GEO_Y0 + 0.8, "detector", fontsize=J.TICK,
                ha="left", va="center", color=J.INK, zorder=7)
        note = "the beam crosses the whole foil"

    ax.add_patch(Rectangle((fx, fy), fw, FOIL_T, facecolor="#e8e8e8",
                           edgecolor=J.G_DARK, lw=LW_EDGE, zorder=5))
    ax.text(fx - 0.8, fy + FOIL_T / 2.0, f"{FOIL_UM:g} {MU}m\nfoil", fontsize=J.TICK,
            ha="right", va="center", color=J.G_DARK, zorder=7, linespacing=1.15)
    ax.text(cx, GEO_Y0 - 1.1, note, fontsize=J.TICK, ha="center", va="top",
            color=colour, zorder=7, linespacing=1.2)


#: Where each micrograph was placed, so the check below can tell whether any label
#: ended up underneath one. A plate's text check that only compares text against text
#: cannot see a caption drawn behind an image at a higher zorder: the words are in the
#: file, at the position the code chose, and invisible. That is exactly how the two
#: how-it-works notes shipped with their second line hidden.
MOUNTED = []


def mount(ax, arr, x0, colour, nm_per_px, win_px, name, records):
    """One REAL micrograph of such a field, named, with what it records under it."""
    s = PAN_SIDE
    MOUNTED.append((x0, PAN_Y, x0 + s, PAN_Y + s))
    #: a PHOTOGRAPH, resampled smoothly for display. Nearest neighbour here only
    #: hardens the edges of whatever source pixels the panel happens to land on,
    #: and nothing is measured off this panel.
    ax.imshow(arr, cmap="gray", vmin=0, vmax=1, interpolation="bilinear",
              extent=(x0, x0 + s, PAN_Y, PAN_Y + s), aspect="auto", zorder=9)
    ax.add_patch(Rectangle((x0, PAN_Y), s, s, fill=False, edgecolor=colour,
                           lw=1.4, zorder=11))
    ax.text(x0, PAN_Y - 0.5, name + " \u2014 " + records, fontsize=J.TICK,
            ha="left", va="top", color=colour, zorder=11)
    blen = s * (BAR_UM * 1000.0 / nm_per_px) / win_px
    pad, bh = 0.016 * s, 0.022 * s
    bx1, by = x0 + s - 0.055 * s, PAN_Y + 0.055 * s
    ax.add_patch(Rectangle((bx1 - blen - pad, by - pad), blen + 2 * pad,
                           bh + pad + 2.30, facecolor="white", edgecolor="none",
                           alpha=0.90, zorder=12))
    ax.add_patch(Rectangle((bx1 - blen, by), blen, bh, facecolor=J.INK,
                           edgecolor="none", zorder=13))
    ax.text(bx1 - blen / 2, by + bh + 0.30, f"{BAR_UM:g} {MU}m", fontsize=J.TICK,
            ha="center", va="bottom", color=J.INK, zorder=13)
    return blen


def combined_schematic(ax, data, crops):
    ax.set_xlim(0, CANVAS[0])
    ax.set_ylim(0, CANVAS[1])
    ax.set_axis_off()
    cell_top = cell(ax)
    rx0, ry0 = specimen(ax)
    leaders(ax, rx0, ry0)
    #: the load and the charging are the TRANSMISSION experiment's conditions, so they
    #: are labelled as such rather than left to look like the shared setting.
    ax.text(DB_CX, CANVAS[1] - 2.3,
            "pulled and hydrogen-charged WHILE the X-ray images it",
            fontsize=J.TICK, ha="center", va="bottom", color=J.ACCENT2, zorder=8)
    bars = {}
    #: WHEN each arm looks, beside WHAT it is -- the one correction that matters most
    #: here. The electron arm is post mortem and sees one final state; the transmission
    #: arm images while the specimen is loaded and charged, so its series is an
    #: evolution. Two words each, on the title line; the caption carries the rest.
    for tag, x0, colour, name, when, kind, records in (
            ("sem", PAN_X[0], J.ACCENT, "SEM", "post mortem", "surface",
             "the crack where it cuts the surface"),
            ("txm", PAN_X[1], J.ACCENT2, "TXM", "in situ, under load", "through",
             f"the crack through all {FOIL_UM:g} {MU}m")):
        ax.text(x0, GEO_Y0 + GEO_H + 0.6, name, fontsize=12.0, fontweight="bold",
                ha="left", va="bottom", color=colour, zorder=11)
        ax.text(x0 + PAN_SIDE, GEO_Y0 + GEO_H + 0.9, when, fontsize=J.TICK,
                ha="right", va="bottom", color=colour, zorder=11)
        how_it_works(ax, x0, colour, kind)
        d = data[tag]
        sl, win, nm = crops[tag]
        bars[tag] = mount(ax, stretch(d["img"][sl]), x0, colour, nm, win, name,
                          records)
    return bars


def groups_present(con):
    """The TXM groups the measurement file actually holds, in the recorded order.

    Driven by the data. When the corpus is restricted to a subset of specimen series the
    record follows without an edit here, and a group that is still present cannot be
    dropped from the caption by forgetting to list it.
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
            f"first -- the caption reports a measurement and must not be written from a "
            f"remembered number.")
    con = json.load(open(CONTRAST))
    order = groups_present(con)

    W = J.PAGEW
    M = 0.03
    SCH = (W - 2 * M) * CANVAS[1] / CANVAS[0]
    Htot = M + SCH + M

    fig = plt.figure(figsize=(W, Htot))
    sx = fig.add_axes([M / W, M / Htot, (W - 2 * M) / W, SCH / Htot])
    bars = combined_schematic(sx, data, crops)

    # NO TWO LABELS MAY PRINT THROUGH EACH OTHER, AND THAT IS MEASURED. This plate had
    # no text check at all, and it shipped with "X-ray beam" drawn underneath the SEM
    # photograph -- the words were in the file, at a position the code chose, and
    # invisible. Every string is measured where the renderer puts it; 1 pt of real
    # overlap in both directions is the threshold, so labels that merely touch pass.
    fig.canvas.draw()
    _r = fig.canvas.get_renderer()
    _w, _h = fig.canvas.get_width_height()
    _tol = fig.dpi / 72.0
    _items = []
    for _t in fig.findobj(plt.Text):
        if not _t.get_text().strip() or not _t.get_visible():
            continue
        try:
            _e = _t.get_window_extent(renderer=_r)
        except Exception:
            continue
        _items.append((_t.get_text().strip().replace("\n", " ")[:40], _e))
    _bad = []
    for _i in range(len(_items)):
        for _k in range(_i + 1, len(_items)):
            _a, _b = _items[_i][1], _items[_k][1]
            if (min(_a.x1, _b.x1) - max(_a.x0, _b.x0) > _tol
                    and min(_a.y1, _b.y1) - max(_a.y0, _b.y0) > _tol):
                _bad.append(f"{_items[_i][0]!r} x {_items[_k][0]!r}")
    _off = [f"{n!r}" for n, _e in _items
            if _e.x0 < -_tol or _e.x1 > _w + _tol or _e.y0 < -_tol or _e.y1 > _h + _tol]
    if _bad or _off:
        raise SystemExit(
            (f"{len(_bad)} overlapping label(s): " + "; ".join(_bad[:5]) if _bad else "")
            + (f"  {len(_off)} off the sheet: " + "; ".join(_off[:5]) if _off else ""))
    print(f"  CONTROL {len(_items)} labels, none overlapping, none off the sheet: PASS")

    # AND NO LABEL MAY BE DRAWN UNDERNEATH A MICROGRAPH. The text-against-text check
    # above cannot see this: an image at a higher zorder simply covers the words, and
    # the saved PNG contains neither of them. The two how-it-works notes shipped that
    # way once. Measured as EXTENTS in display space, not as anchor points -- a
    # two-line label whose anchor is clear of the panel can still have its second line
    # inside it, which is precisely the case that got through. The scale-bar labels
    # are deliberately inside their own panel and are named rather than exempted by
    # position.
    _INSIDE_ON_PURPOSE = {f"{BAR_UM:g} {MU}m"}
    _boxes = [sx.transData.transform([(x0, y0), (x1, y1)])
              for x0, y0, x1, y1 in MOUNTED]
    _buried = []
    for _t in fig.findobj(plt.Text):
        _txt = _t.get_text().strip()
        if not _txt or _txt in _INSIDE_ON_PURPOSE or not _t.get_visible():
            continue
        try:
            _e = _t.get_window_extent(renderer=_r)
        except Exception:
            continue
        for (bx0, by0), (bx1, by1) in _boxes:
            if (min(_e.x1, bx1) - max(_e.x0, bx0) > _tol
                    and min(_e.y1, by1) - max(_e.y0, by0) > _tol):
                _buried.append(_txt.replace("\n", " ")[:40])
    if _buried:
        raise SystemExit(f"{len(_buried)} label(s) overlap a micrograph and are drawn "
                         f"underneath it: " + "; ".join(repr(b) for b in _buried))
    print(f"  CONTROL no label is drawn underneath a micrograph: PASS")

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "one schematic of both measurement geometries on one crack, drawn by "
                "hand and not to scale, with the REAL micrograph each instrument "
                "produces mounted at that instrument; one panel, no letter",
        "mounted_micrographs": {
            t: {"field": str(data[t]["field"]), "fov_um": FOV_UM,
                "window_px": int(crops[t][1]), "nm_per_px": crops[t][2],
                "scale_bar_um": BAR_UM, "scale_bar_canvas_units": round(bars[t], 3),
                "display": "median +/- 3 robust SD stretch, identical for both; the "
                           "detector ran on the unstretched array"}
            for t in ("sem", "txm")},
        "matched_fov_um": FOV_UM,
        #: The thickness the section is dimensioned at. Recorded so the manuscript's
        #: caption quotes the number the plate draws rather than a second copy of it.
        "foil_thickness_um": FOIL_UM,
        "labels_on_the_plate": [
            "tensile axis", "F", "gauge section",
            "one 35 um field of the gauge, imaged in both instruments",
            "a SEM", "the crack where it cuts the surface", "electron source",
            "detector", "22 um", "records the surface trace",
            "b TXM", "the crack through the whole thickness", "X-ray source",
            "detector", "22 um", "records the whole projection", "5 um"],
        "measurement_geometry": {
            "copied_from": "docs/FIGURE_CONVENTIONS_FROM_PUBLISHED_WORK.md, which "
                           "records what two real published figures of this kind do, "
                           "with their citations. Nothing is reproduced from them; "
                           "what is copied is convention.",
            "the_finding": "neither reference draws the microscope. Both draw the "
                           "measurement GEOMETRY in four or five elements -- a source, "
                           "a beam as a filled cone or band, the specimen as a plain "
                           "filled shape, and the detector as a plain filled bar -- "
                           "with the parts named in horizontal sans-serif beside them. "
                           "One of them draws a whole laboratory X-ray microtomograph "
                           "in four elements.",
            "so_what_came_off": "the previous edition's full ray diagrams: electron "
                                "gun, condenser, crossover, scan coils, objective, "
                                "condenser and objective zone plates, optic axes. None "
                                "of that appears in either reference. The edition "
                                "before THAT contributed section hatching, a "
                                "fixed-support symbol and dimension lines with "
                                "extension lines and arrow terminators, which are "
                                "mechanical-drawing conventions and appear in neither.",
            "SEM": "source, converging beam, specimen, and an off-axis detector "
                   "collecting what comes back out of the entry face",
            "TXM": "source, beam crossing the whole thickness, and a detector behind "
                   "the foil carrying the crack's shadow",
            "not_to_scale": "the geometry is schematic. The foil thickness is the real "
                            "one and is stated on the specimen; nothing else on the "
                            "drawing is dimensioned."},
        "drawing_conventions": {
            "fills": "flat, no gradient and no drop shadow; the beam is a filled "
                     "translucent cone, as in both references",
            "labels": "horizontal sans-serif beside the element, one type size, with a "
                      "short straight leader only where the words cannot touch the "
                      "thing they name",
            "features": "what each instrument records is marked with one leader and a "
                        "few words, which is how both references mark a feature -- not "
                        "with a dimension",
            "panel_letters": "lowercase, bold, no parentheses, top left",
            "scale_bars": "a plain filled bar with its length beside it, bottom right "
                          "of each micrograph",
            "callout": "the gauge box is enlarged into the two columns by two dashed "
                       "leader lines"},
        "geometry_correction": {
            "what_was_wrong": "an earlier edition sent the X-ray beam ACROSS the "
                              "section, left to right, to a detector standing on edge "
                              "-- a path through the foil's width, under a label "
                              "reading 'through the thickness'",
            "now": "both beams arrive at the broad face and the transmission optics "
                   "and detector lie behind the foil, which is the only geometry "
                   "either instrument has",
            "why_it_matters": "the two recorded spans are different ON THE PLATE: the "
                              "drawn crack opens over a narrow mouth and runs sideways "
                              "beneath it, so the electron column's span is the mouth "
                              "and the transmission column's is the whole sheet in "
                              "projection, about six times wider. An earlier edition "
                              "drew both dimensions over the same span."},
        "detector_axis_measurement": {
            "drawn": False,
            "why_here": "two panels plotted this and were withdrawn from the plate; the "
                        "measurement is still read and recorded so the plate and the "
                        "sentence beside it cannot be maintained separately",
            "plots": "median over each frame's painted-crack pixels of the largest MAD "
                     "multiplier at which the deployed multiscale darkness union would "
                     "still propose that pixel",
            "definition": con["critical_k_definition"],
            "operating_point": con["mad_k"],
            "groups_recorded": order,
            "reconstruction_check": "every frame's reconstruction of the real proposal "
                                    "mask from this axis is checked pixel for pixel "
                                    "against the installed segment_dark_regions; the "
                                    "largest disagreement over all frames is "
                                    f"{max(con['SEM']['max_reconstruction_mismatch_px'], con['TXM']['max_reconstruction_mismatch_px'])} pixels",
            "scope": "FULL corpus, not the b2/b3 restriction the manuscript quotes",
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
        "note": "the plate is a schematic and is labelled as such in the caption; the "
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
