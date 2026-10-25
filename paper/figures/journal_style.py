"""House style for the paper's figures, from the target journals' own rules.

Every constant here traces to a published instruction from Elsevier (Materials
Characterization, Engineering Failure Analysis) or IOP (Measurement Science and
Technology), not to taste. The rules that changed these figures most:

  NO TITLE INSIDE THE ARTWORK.  IOP: "Do not title a figure, the description of it goes
  in the figure caption." Elsevier: a caption is a brief title "(not displayed on the
  figure itself)" plus a description. Our plates each carried a declarative sentence as an
  in-figure title, which is a slide convention and the clearest single tell that a figure
  did not come from a journal. It travels with a family -- chatty annotations inside the
  axes -- and those go too.

  NO NUMERIC LABELS ON BARS.  The figure shows the shape of a comparison; the numbers,
  with their precision, belong in a table.

  BARS START AT ZERO.  A truncated value axis under bars is the one thing in this set a
  reviewer will call a misrepresentation. Where a difference is too small to see from
  zero, the answer is a different chart, not a cropped axis.

  FULL BOX, NO GRID.  All four spines, ticks on the left and bottom, no gridlines.

  COLOUR ENCODES IDENTITY, NOT VERDICT.  Which specimen, which method -- never
  pass/fail. A reader in greyscale must lose nothing, so both publishers' colour policies
  are satisfied by designing greyscale-first and letting colour be optional.

  (a), (b), (c).  Lower case, in parentheses, at the panel corner; the caption addresses
  panels by letter.

  ARIAL, EMBEDDED.  Elsevier names Arial/Helvetica. matplotlib's PDF default is Type 3,
  which Elsevier rejects; fonttype 42 embeds TrueType instead.

  COLUMN WIDTHS.  Elsevier: 90 mm single, 140 mm 1.5-column, 190 mm double. Design at one
  of them so no rescaling happens and the type size specified is the type size printed.
"""
import os

import matplotlib
import matplotlib.pyplot as plt

MM = 1 / 25.4
W1, W15, W2 = 90 * MM, 140 * MM, 190 * MM      # Elsevier column widths, inches
PAGEW = 6.37                                    # our own page text block, inches

#: Lettering must finish at >= 7 pt printed; both publishers ask for 8-12 pt at final
#: size. These are the sizes AT PRINT SIZE, so a plate must be drawn at its printed width.
BODY, LABEL, TICK, PANEL = 8.5, 8.5, 8.0, 9.0
#: Lettering must FINISH at 8 pt or larger at the width the journal prints the figure.
#: 6 pt is the separate, lower floor for sub- and superscripts only. The floor was 7 pt
#: until the convention audit; both publishers ask for 8-12 pt at final size.
FLOOR = 8.0
SCRIPT_FLOOR = 6.0

#: Elsevier's Guide for Authors asks the author to state each figure's column class, so
#: it is recorded per figure rather than left for a production editor to guess.
COLUMN_CLASS = {
    "P1 - public scores": ("1.5-column", W15),
    "P2 - operating curve": ("1.5-column", W15),
    "P3 - width sensitivity": ("1.5-column", W15),
    "P4 - baselines": ("1.5-column", W15),
    "P5 - pixel budget": ("1.5-column", W15),
    "P6 - pipeline in pictures": ("double", W2),
    "txm_transfer": ("double", W2),
}

#: Greyscale-first. The three greys separate in print without colour; the single accent is
#: used only where one series must be picked out, never to mean pass or fail.
INK = "#000000"
G_DARK, G_MID, G_LIGHT = "#333333", "#808080", "#c8c8c8"
ACCENT = "#1f4e9c"          # one blue, for the series under discussion
SERIES = [G_DARK, G_MID, G_LIGHT, "#5a5a5a", "#9e9e9e", "#e0e0e0"]


def use():
    """Apply the house style. Call once at the top of a plate module."""
    matplotlib.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica"],
        "font.size": BODY,
        "axes.labelsize": LABEL,
        "axes.titlesize": BODY,
        "xtick.labelsize": TICK,
        "ytick.labelsize": TICK,
        "legend.fontsize": TICK,
        "axes.linewidth": 0.6,
        "axes.grid": False,
        # all four spines, which is the majority convention in these journals
        "axes.spines.top": True,
        "axes.spines.right": True,
        # ticks on all four sides, one direction chosen once for the whole paper
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.top": True,
        "ytick.right": True,
        "xtick.minor.visible": True,
        "ytick.minor.visible": True,
        "xtick.minor.size": 1.7,
        "ytick.minor.size": 1.7,
        "xtick.minor.width": 0.5,
        "ytick.minor.width": 0.5,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 3.0,
        "ytick.major.size": 3.0,
        "lines.linewidth": 1.1,
        "lines.markersize": 4.0,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        # Elsevier rejects Type 3; 42 embeds TrueType
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def panel_label(ax, letter, *, inside=False, color=None):
    """(a) at the panel corner.

    PLACEMENT IS A HOUSE CHOICE, NOT A VENUE RULE, and the two target venues disagree.
    Checked on the publishers' own image CDN: Jiao (Mater. Charact. 2026,
    10.1016/j.matchar.2026.116319) puts the letters outside, below, centred, for both its
    micrograph plate and its chart plate; Zheng (Eng. Fail. Anal. 2026,
    10.1016/j.engfailanal.2026.111235) puts a black letter on an opaque white patch inside
    the top-left of each micrograph. What both do, and what matters, is use ONE placement
    consistently through the paper.

    So: charts get the letter outside above-left, micrographs get Zheng's black-on-white
    patch inside, and nothing in the submission deviates from that pairing. The earlier
    white-letter-with-a-black-stroke form is dropped -- it is a screenshot-overlay look and
    neither venue uses it.
    """
    if inside:
        return ax.text(0.02, 0.98, f"({letter})", transform=ax.transAxes,
                       fontsize=PANEL, fontweight="bold", va="top", ha="left",
                       color=color or INK,
                       bbox=dict(facecolor="white", edgecolor="none",
                                 boxstyle="square,pad=0.22"))
    return ax.text(-0.02, 1.04, f"({letter})", transform=ax.transAxes, fontsize=PANEL,
                   fontweight="bold", va="bottom", ha="left", color=color or INK)


def micrograph(ax):
    """Strip a micrograph panel of every axes decoration.

    No spines, no ticks, no tick labels, no axis title. A micrograph is an image, and the
    pixel grid is not a measurement axis; the stage or specimen name belongs in the
    caption or beside the panel letter. Chart panels keep their full box.
    """
    ax.set_axis_off()


def save(fig, path, *, dpi=600, printed_width=PAGEW, vector=True):
    """Write the raster and the VECTOR, then check the type at the size it will print.

    Two outputs, because they serve different readers. The PNG at 600 dpi clears
    Elsevier's 500 dpi combination-art minimum and is what the draft embeds. The PDF is
    the one a production editor or a co-author actually wants: IOP states that vector EPS
    or PDF is preferred for anything that is not a photograph, and a vector file is the
    only form in which a figure stays EDITABLE -- every label, rule and bar can be
    adjusted in Illustrator or Inkscape without redrawing it.

    The type check has to run after the write: bbox trimming and page rescaling both
    happen outside the figure's own coordinates, and a floor applied there passes plates
    that reach the page at half scale.
    """
    import matplotlib.image as mpimg
    fig.savefig(path, dpi=dpi, facecolor="white")
    if vector:
        fig.savefig(os.path.splitext(path)[0] + ".pdf", facecolor="white")
    sizes = [t.get_fontsize() for t in fig.findobj(plt.Text) if t.get_text().strip()]
    plt.close(fig)
    saved_in = mpimg.imread(path).shape[1] / float(dpi)
    scale = printed_width / saved_in
    if sizes and min(sizes) * scale < FLOOR - 1e-9:
        raise SystemExit(
            f"{path}: smallest type prints at {min(sizes) * scale:.1f} pt (floor "
            f"{FLOOR}). Saved {saved_in:.2f} in, printed {printed_width:.2f} in, scale "
            f"{scale:.2f}. Relay the plate out at the printed width.")
    print(f"wrote {path} (+.pdf)  ({saved_in:.2f} in, {dpi} dpi, prints at {scale:.2f}x, "
          f"smallest type {min(sizes) * scale:.1f} pt)")
