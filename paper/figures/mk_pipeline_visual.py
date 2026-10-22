#!/usr/bin/env python3
"""The pipeline with real pictures at every step, not boxes of text.

Each panel is the ACTUAL array that stage produces, captured by running the shipped
detector on one public micrograph. Nothing is drawn by hand and nothing is a mock-up; if a
stage changes, the panel changes.

The image is a CC BY 4.0 Inconel 718 field from Zenodo 23045328, chosen so the figure
publishes no specimen imagery of its own.

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
from matplotlib.patches import FancyArrowPatch
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


def pick_field():
    """The field with the most labelled crack, so every stage has something to show."""
    best, best_frac = None, -1.0
    for f in sorted(os.listdir(os.path.join(SRC, "image"))):
        stem = os.path.splitext(f)[0]
        mp = os.path.join(SRC, "mask", stem + ".png")
        if not os.path.exists(mp):
            continue
        gt = np.array(Image.open(mp).convert("L")) > 127
        if gt.mean() > best_frac:
            a = np.array(Image.open(os.path.join(SRC, "image", f)))
            img = (a >> 8).astype(np.uint8) if a.dtype == np.uint16 else \
                np.array(Image.open(os.path.join(SRC, "image", f)).convert("L"))
            if img.shape == gt.shape:
                best, best_frac = (stem, img, gt), gt.mean()
    if best is None:
        raise SystemExit(f"no usable field under {SRC}")
    return best


def stages(img8):
    """Run the shipped path, keeping every intermediate."""
    flat = D.flatten_background(img8)
    raw = u.segment_dark_regions(flat, img8=img8, mad_k=5.0)
    cleaned = D.clean_mask(raw, min_area_px=13)
    lab = skm.label(cleaned, connectivity=2)
    if lab.max():
        sz = np.bincount(lab.ravel())
        keep = np.where(sz >= 40)[0]
        final = np.isin(lab, keep[keep > 0])
    else:
        final = np.zeros_like(cleaned, bool)
    return flat, raw, cleaned, lab, final


def overlay(img8, mask, gt=None):
    """Grey image with the mask hatched in white, and the label outlined if given."""
    rgb = np.dstack([img8.astype(np.float32)] * 3) / 255.0
    rgb[mask] = rgb[mask] * 0.25 + np.array([1.0, 1.0, 1.0]) * 0.75
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
    stem, img, gt = pick_field()
    flat, raw, cleaned, lab, final = stages(img)
    # a crop that actually contains crack, so the panels are legible at print size
    ys, xs = np.where(gt)
    cy, cx = int(np.median(ys)), int(np.median(xs))
    H = 360
    y0 = max(min(cy - H // 2, img.shape[0] - H), 0)
    x0 = max(min(cx - H // 2, img.shape[1] - H), 0)
    sl = (slice(y0, y0 + H), slice(x0, x0 + H))

    panels = [
        ("1  Micrograph", img[sl], "grey",
         "the field as acquired, 8-bit"),
        ("2  Flatten the background", flat[sl], "grey",
         f"multi-scale estimate at sigma {DO.SCALE_LADDER[0]}-{DO.SCALE_LADDER[-1]} px,\\nsubtracted"),
        ("3  Propose dark candidates", raw[sl], "binary",
         f"dark at ANY of {len(DO.SCALE_LADDER)} scales: robust MAD cut\\nplus an absolute floor at {DO.ABSOLUTE_DARK_THRESH}"),
        ("4  Clean and label", cleaned[sl], "binary",
         "holes filled, blobs under 13 px dropped,\\n8-connected labelling"),
        ("5  Drop small regions", final[sl], "binary",
         "regions under 40 px removed.\\nPass 1's classifier is OFF, so nothing else is"),
        ("6  The answer, against the label", overlay(img[sl], final[sl], gt[sl]), "rgb",
         "white = what the detector marked,\\nblack outline = what the human marked"),
    ]

    ncol = 2
    nrow = 3
    # 3 x 2 at the printed width: six panels across 10.2 in reached the page at
    # 0.62x and took the captions to 4.7 pt. Two columns of three keeps each panel
    # about 2.6 in wide at scale 1.
    fig, axes = plt.subplots(nrow, ncol, figsize=(PAGEW - 0.25, 8.6))
    for ax, (title, arr, kind, cap) in zip(axes.ravel(), panels):
        if kind == "grey":
            ax.imshow(arr, cmap="gray", interpolation="nearest")
        elif kind == "binary":
            ax.imshow(~np.asarray(arr, bool), cmap="gray", vmin=0, vmax=1,
                      interpolation="nearest")
        else:
            ax.imshow(arr, interpolation="nearest")
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("0.6"); sp.set_linewidth(0.8)
        ax.set_title(title, fontsize=LAB, fontweight="bold", pad=5, loc="left")
        ax.set_xlabel(cap.replace("\\n", "\n"), fontsize=CAP, color="0.25", labelpad=4,
                      linespacing=1.45)
    # arrows between the panels, so it reads as a flow and not a contact sheet
    for r in range(nrow):
        for c in range(ncol - 1):
            a, b = axes[r][c], axes[r][c + 1]
            # the VERTICAL CENTRE of the image axes. y0 + 0.30 in figure coordinates put
            # the arrows above the panels, floating, where they read as decoration.
            pa, pb = a.get_position(), b.get_position()
            ymid = (pa.y0 + pa.y1) / 2
            fig.add_artist(FancyArrowPatch(
                (pa.x1 + 0.005, ymid), (pb.x0 - 0.005, ymid),
                arrowstyle="-|>", mutation_scale=13, color="0.35", linewidth=1.2,
                transform=fig.transFigure))
    # NO WRAP ARROW. A curved 3 -> 4 connector was tried and it swept across three panels,
    # which is worse than leaving the reading order to the numbers on the titles.
    fig.suptitle("Every step, on one public Inconel 718 field", fontsize=TITLE,
                 fontweight="bold", y=0.975)
    fig.text(0.5, 0.022,
             f"{H} x {H} px detail of {stem}.tif (Zenodo 23045328, CC BY 4.0).\n"
             f"Each panel is the array that stage actually produces, captured by\n"
             f"running the shipped detector. No scale bar: the collection\n"
             f"publishes no pixel size.",
             ha="center", va="bottom", fontsize=CAP, color="0.35",
             linespacing=1.45)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.165, wspace=0.09,
                        hspace=0.62)
    p = os.path.join(OUT, "P6 - pipeline in pictures.png")
    save_checked(fig, p)
    plt.close(fig)
    json.dump({"figure": "P6 - pipeline in pictures.png",
               "field": stem, "detail_px": H, "crop_origin": [int(y0), int(x0)],
               "source": "Zenodo 23045328 (CC BY 4.0), Inconel718_crack/image",
               "panels": [t for t, *_ in panels],
               "settings": {"scale_ladder": list(DO.SCALE_LADDER),
                            "absolute_dark_thresh": DO.ABSOLUTE_DARK_THRESH,
                            "mad_k": 5.0,
                            "use_region_classifier": DO.USE_REGION_CLASSIFIER},
               "note": "panels are the real intermediate arrays, not illustrations"},
              open(os.path.join(OUT, "P6 - pipeline in pictures.caption.json"), "w"),
              indent=1)
    print("wrote", p)
    print(f"  field {stem}, crack {100*gt.mean():.2f}% of frame, detail at ({y0},{x0})")


if __name__ == "__main__":
    main()
