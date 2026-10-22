"""Scale bars for micrograph panels, and an honest refusal where no scale exists.

Three of the image collections this project draws figures from have three different
scale situations, and a figure that treats them alike is lying about one of them:

  TXM          every frame has a pixel size, but it is DERIVED from operator-supplied
               mosaic geometry (a 30 um window at 0.35 overlap, 9x5 tiles over
               6367x3691 px -> 29.24 nm/px), not read from instrument metadata. The TXM
               repository marks it [TODO-AUTHOR] and records that two frames close only
               at 0.30 overlap. A bar may be drawn, and its caption must say where the
               number came from.
  our own SEM  80 of 142 frames carry a recoverable databar; 51.883 nm/px at the modal
               magnification. A bar may be drawn on those and must not be drawn on the
               other 62.
  public SEM   the Inconel 718 collection (Zenodo 23045328) publishes no pixel size at
               all: no resolution tag, no databar, no magnification in the record, and
               its subsets come from different microscopes. No bar can be drawn, and the
               panel should say so rather than leave a reader to assume one scale.

`no_scale_note` exists so that the absence is visible in the figure instead of being an
omission a reader has to notice. The paper's primary quantity is an area FRACTION, which
is dimensionless and unaffected by this -- that point belongs in the caption too.
"""
import matplotlib.patheffects as pe

# A bar should be a round number of physical units and roughly a fifth of the panel.
_NICE_NM = [50, 100, 200, 500, 1_000, 2_000, 5_000, 10_000, 20_000, 50_000,
            100_000, 200_000, 500_000, 1_000_000]


def pick_length_nm(nm_per_px, width_px, target_frac=0.22):
    """The roundest bar close to `target_frac` of the panel width."""
    want = nm_per_px * width_px * target_frac
    return min(_NICE_NM, key=lambda v: abs(v - want))


def fmt_nm(nm):
    if nm >= 1_000_000:
        return f"{nm / 1_000_000:g} mm"
    if nm >= 1_000:
        return f"{nm / 1_000:g} µm"
    return f"{nm:g} nm"


def scalebar(ax, nm_per_px, width_px, *, loc="lower right", color="white",
             pad_frac=0.045, height_frac=0.016, fontsize=7, length_nm=None):
    """Draw a scale bar on an imshow axes whose x units are pixels.

    Returns the bar length in nanometres, so a caller can state it in the caption
    instead of re-deriving it and risking the two disagreeing.
    """
    if not nm_per_px or nm_per_px <= 0:
        raise ValueError("scalebar needs a real nm_per_px; use no_scale_note instead")
    nm = length_nm or pick_length_nm(nm_per_px, width_px)
    px = nm / nm_per_px
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()                      # imshow gives y inverted
    W, H = abs(x1 - x0), abs(y1 - y0)
    pad = pad_frac * W
    bh = max(height_frac * H, 2.0)
    right = "right" in loc
    lower = "lower" in loc
    bx = (max(x0, x1) - pad - px) if right else (min(x0, x1) + pad)
    by = (max(y0, y1) - pad - bh) if not lower else (min(y0, y1) + pad)
    # imshow's y axis runs top-down, so "lower" is the larger y
    by = (max(y0, y1) - pad - bh) if lower else (min(y0, y1) + pad)
    ax.add_patch(__import__("matplotlib").patches.Rectangle(
        (bx, by), px, bh, facecolor=color, edgecolor="none", zorder=20))
    t = ax.text(bx + px / 2, by - 0.012 * H, fmt_nm(nm), color=color, fontsize=fontsize,
                ha="center", va="bottom", zorder=21)
    t.set_path_effects([pe.withStroke(linewidth=1.6, foreground="black", alpha=0.65)])
    return nm


def no_scale_note(ax, text="no pixel size published for this collection",
                  color="white", fontsize=6.4, pad_frac=0.03):
    """Say so on the panel. An absent scale bar is otherwise indistinguishable from a
    scale bar someone forgot to draw."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    W, H = abs(x1 - x0), abs(y1 - y0)
    t = ax.text(max(x0, x1) - pad_frac * W, max(y0, y1) - pad_frac * H, text,
                color=color, fontsize=fontsize, ha="right", va="bottom", zorder=21,
                style="italic")
    t.set_path_effects([pe.withStroke(linewidth=1.6, foreground="black", alpha=0.65)])
