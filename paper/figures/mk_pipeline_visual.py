#!/usr/bin/env python3
"""The pipeline with real pictures at every step, not boxes of text.

Each panel is the ACTUAL array that stage produces, captured by running the shipped
detector. Nothing is drawn by hand and nothing is a mock-up; if a stage changes, the panel
changes.

THE FIELD IS THIS LABORATORY'S OWN, AND THAT IS A DELIBERATE TRADE. The public Inconel 718
collection this paper evaluates on publishes no pixel size -- no resolution tag, no
databar, nothing in the record -- so a panel drawn from it cannot carry a scale bar, and
Materials Characterization lists a missing scale bar on a micrograph as grounds for return
without review. Our own frames carry a recoverable databar: 80 of 142, all at 51.883 nm/px
at the modal magnification. So the method figure is drawn from one of ours and the caption
says plainly that it is not from the evaluated collection.

The field is chosen by rule, not by eye: of the 80 scaled frames with an original on disk,
the one whose crack area fraction is closest to the median. Picking the most heavily
cracked field, which an earlier version of this plate did without saying so, flatters every
stage. MAR_AmbB_AS is excluded for the reason the tile benchmark excludes it -- 87% of what
was painted there is round.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_pipeline_visual.py
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import journal_style as J          # noqa: E402

J.use()
from matplotlib.patches import FancyArrowPatch, Rectangle
from scalebar import scalebar
from scipy import ndimage as ndi
from skimage import measure as skm
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None

SCR = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
SRC = os.path.join(SCR, "pub_ebc_download/train_subset/Inconel718_crack")
OUT = os.path.join(HERE, "out")
FLOOR = 7.0
# the width this plate is printed at on the page: PAGE[0] - ML - MR in make_paper.py.
# Drawn wider, it is scaled down and every type size shrinks with it.
PAGEW = 6.37
TITLE, LAB, CAP = 9.6, 8.2, 7.4


class U:
    pass


u = U()
DO.install(u)


#: The frame this plate is drawn from, and why. Selected by the rule in the docstring;
#: recorded here so the choice is auditable rather than a literal someone has to trust.
FIELD = "MAR_H_HIP_CBS_0007"
NM_PER_PX = 51.883


def pick_field():
    """Load this laboratory's own field through the project's own loader.

    The same stretch, field-of-view crop and 8-bit conversion the application uses, so the
    panels are what the detector actually sees rather than a separate rendering of the
    same file.
    """
    import tifffile
    from skimage import exposure
    sys.path.insert(0, os.path.join(SEM, "interior_active_learning", "code"))
    from common import contrast_kwargs_for

    raw = tifffile.imread(os.path.join(SEM, "original", FIELD + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    ck = contrast_kwargs_for(FIELD)
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    return FIELD, img8[y0:y1, x0:x1], None


def stages(img8):
    """Run the shipped path, keeping every intermediate."""
    flat = D.flatten_background(img8)
    # read, never hardcoded: a literal here printed 5.0 while the paper had
    # moved to 6.0 and the figure contradicted the text beside it
    raw = u.segment_dark_regions(flat, img8=img8, mad_k=DO.SHIPPED_MAD_K)
    cleaned = D.clean_mask(raw, min_area_px=13)
    lab = skm.label(cleaned, connectivity=2)
    if lab.max():
        sz = np.bincount(lab.ravel())
        keep = np.where(sz >= 40)[0]
        final = np.isin(lab, keep[keep > 0])
    else:
        final = np.zeros_like(cleaned, bool)
    return flat, raw, cleaned, lab, final


def mask_on_field(img8, mask, colour=(0.12, 0.31, 0.61)):
    """A stage's binary output drawn over the field it came from.

    Drawn bare, a binary stage is black-on-WHITE, and on a white page it has no edge: the
    panel bleeds into the paper and the six-panel grid stops reading as a grid. Removing
    the axes spines, which micrograph panels must not have, makes that worse rather than
    better. Both target-venue papers checked for this figure set show segmentation over
    the micrograph instead, which fixes the bleed, keeps every panel in the same tonal
    range, and shows the reader where on the field the stage is acting.
    """
    rgb = np.dstack([img8.astype(np.float32)] * 3) / 255.0
    rgb[mask] = np.array(colour)
    return np.clip(rgb, 0, 1)


def overlay(img8, mask, gt=None):
    """Grey image with the mask in the house accent, and the label outlined if given."""
    # the same accent as the stage panels, so the six panels read as one sequence
    # rather than as two different figures
    rgb = np.dstack([img8.astype(np.float32)] * 3) / 255.0
    rgb[mask] = np.array([0.12, 0.31, 0.61])
    if gt is not None:
        edge = gt & ~ndi.binary_erosion(gt, np.ones((3, 3)))
        rgb[edge] = np.array([0.0, 0.0, 0.0])
    return np.clip(rgb, 0, 1)


def save_checked(fig, path, dpi=200):
    """Write, then check the type size at the size it will PRINT.

    Checking the figure's own coordinates passes plates that reach the page at half
    scale. bbox_inches trims the width, and the page then rescales whatever comes out to
    PAGEW, so the only honest moment to apply the floor is after the file exists.
    """
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    sizes = [t.get_fontsize() for t in fig.findobj(plt.Text) if t.get_text().strip()]
    import matplotlib.image as _mpimg
    saved_in = _mpimg.imread(path).shape[1] / float(dpi)
    scale = PAGEW / saved_in
    if sizes and min(sizes) * scale < FLOOR - 1e-9:
        raise SystemExit(
            f"smallest type prints at {min(sizes) * scale:.1f} pt (floor {FLOOR}); the "
            f"plate saves {saved_in:.2f} in and the page gives it {PAGEW} in. Relay it "
            f"out at about {PAGEW} in wide.")
    print(f"wrote {path}  ({saved_in:.2f} in saved, prints at {scale:.2f}x, "
          f"smallest type {min(sizes) * scale:.1f} pt)")


def main():
    stem, img, _ = pick_field()
    flat, raw, cleaned, lab, final = stages(img)

    # the detail is centred on the detected crack, since this frame carries no hand
    # annotation to centre on; chosen from the final mask so it shows what the figure is
    # about rather than a corner of matrix
    ys, xs = np.where(final)
    cy, cx = int(np.median(ys)), int(np.median(xs))
    H = 520
    y0 = max(min(cy - H // 2, img.shape[0] - H), 0)
    x0 = max(min(cx - H // 2, img.shape[1] - H), 0)
    sl = (slice(y0, y0 + H), slice(x0, x0 + H))

    step = max(1, img.shape[1] // 1600)
    panels = [
        img[sl],
        flat[sl],
        mask_on_field(img[sl], raw[sl]),
        mask_on_field(img[sl], cleaned[sl]),
        mask_on_field(img[sl], final[sl]),
    ]
    # the sixth panel closes the loop: the scored mask over the WHOLE field, at frame
    # scale. Five stage panels leave a ragged third cell in a 3 x 2 grid, and the result
    # in context is worth more than the gap -- it is also the only panel that shows what
    # an area fraction is computed over.
    whole_result = mask_on_field(img[::step, ::step], final[::step, ::step])

    # (a) is the whole field with the detail boxed; (b)-(f) are the stages on that detail.
    # Showing the field as well as the crop is how these journals indicate what a detail
    # is a detail OF, and it is the panel that carries the frame-scale bar.
    fig = plt.figure(figsize=(J.PAGEW, 5.35))
    gs = fig.add_gridspec(3, 3, height_ratios=[1.32, 1, 1], hspace=0.016, wspace=0.016)
    axw = fig.add_subplot(gs[0, :])
    axw.imshow(img[::step, ::step], cmap="gray", interpolation="nearest", aspect="equal")
    axw.add_patch(Rectangle((x0 / step, y0 / step), H / step, H / step, fill=False,
                            edgecolor=J.ACCENT, linewidth=1.0))
    J.micrograph(axw)
    J.panel_label(axw, "a", inside=True)
    scalebar(axw, NM_PER_PX * step, img.shape[1] / step)

    for i, arr in enumerate(panels):
        ax = fig.add_subplot(gs[1 + i // 3, i % 3])
        ax.imshow(arr, cmap="gray" if arr.ndim == 2 else None, interpolation="nearest")
        J.micrograph(ax)
        J.panel_label(ax, "bcdef"[i], inside=True)
        if i == 0:
            scalebar(ax, NM_PER_PX, H)
    axr = fig.add_subplot(gs[2, 2])
    axr.imshow(whole_result, interpolation="nearest")
    J.micrograph(axr)
    J.panel_label(axr, "g", inside=True)
    scalebar(axr, NM_PER_PX * step, img.shape[1] / step)

    p = os.path.join(OUT, "P6 - pipeline in pictures.png")
    fig.subplots_adjust(left=0.004, right=0.996, top=0.996, bottom=0.004)
    J.save(fig, p)
    json.dump({"figure": "P6 - pipeline in pictures.png",
               "field": stem, "nm_per_px": NM_PER_PX,
               "field_px": [int(img.shape[0]), int(img.shape[1])],
               "field_um": [round(img.shape[0] * NM_PER_PX / 1000, 1),
                            round(img.shape[1] * NM_PER_PX / 1000, 1)],
               "detail_px": H, "crop_origin": [int(y0), int(x0)],
               "source": "this laboratory's own SEM corpus; NOT the evaluated public "
                         "collection, which publishes no pixel size and so cannot carry "
                         "a scale bar",
               "selection_rule": "of the 80 scaled frames with an original on disk, the "
                                 "one whose crack area fraction is closest to the median; "
                                 "MAR_AmbB_AS excluded as in the tile benchmark",
               "settings": {"scale_ladder": list(DO.SCALE_LADDER),
                            "absolute_dark_thresh": DO.ABSOLUTE_DARK_THRESH,
                            "mad_k": DO.SHIPPED_MAD_K,
                            "use_region_classifier": DO.USE_REGION_CLASSIFIER},
               "note": "panels are the real intermediate arrays, not illustrations"},
              open(os.path.join(OUT, "P6 - pipeline in pictures.caption.json"), "w"),
              indent=1)
    print(f"  field {stem}, {img.shape[1]}x{img.shape[0]} px at {NM_PER_PX} nm/px "
          f"= {img.shape[1]*NM_PER_PX/1000:.0f}x{img.shape[0]*NM_PER_PX/1000:.0f} um, "
          f"detail {H} px at ({y0},{x0})")


if __name__ == "__main__":
    main()
