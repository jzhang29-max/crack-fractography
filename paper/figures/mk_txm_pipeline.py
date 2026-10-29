#!/usr/bin/env python3
"""The SEM detector's own stages, run on a TXM frame. The counterpart of P6.

Section 4.1 shows the TXM collection's OWN detector stage by stage. Section 4.3 carries
the SEM detector across and, until now, showed only its finished mask. That leaves the
reader unable to see WHERE the transfer breaks: a mask that is wrong can be wrong because
the flattening removed the crack, because the darkness cut never proposed it, or because
a component filter deleted it, and those are different failures with different fixes.
These are the real intermediate arrays from the same code path the application runs, on a
TXM frame instead of an SEM one, so the two pipelines can be compared panel for panel.

WHICH FRAME. Of the frames with at least 5,000 refereed pixels of each verdict AND an
annotation that is a trace rather than a filled region -- at most MAX_DEEP_SHARE of the
painted pixels more than DEEP_PX inside the paint, the rule `mk_txm_transfer_figure.py`
uses and the reason it uses it -- the one whose accuracy margin at k = 6 is closest to the
median of that set. Typical rather than flattering, which is the rule Figure 8 already
uses for the collection's own detector. The frame, the rule and the runners-up are
printed when this runs.

SCALE BARS. 29.24 nm/px, derived from operator-supplied mosaic geometry and not read from
instrument metadata; see Section 4 and the docstring of mk_txm_transfer_figure.py.
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths

SEM_REPO = _paths.SEM_REPO
TXM_REPO = _paths.TXM_REPO
sys.path.insert(0, os.path.join(SEM_REPO, "code"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "analysis"))
sys.dont_write_bytecode = True

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scipy import ndimage as ndi
from skimage import measure as skm, morphology as morph

import detect_cracks as D
import detector_overrides as DO
import journal_style as J
from scalebar import scalebar

J.use()
OUT = _paths.FIG_DIR
NM_PER_PX = 29.24
MADK = 6.0
DEEP_PX, MAX_DEEP_SHARE = 50, 0.25
DETAIL = 700
NAME = "T6 - the SEM detector's stages on TXM"


class U:
    pass


u = U()
DO.install(u)
CORR = os.path.join(TXM_REPO, "paint", "corrections")


def stages(img8):
    """The shipped path, keeping every intermediate. Mirrors mk_pipeline_visual.stages."""
    flat = D.flatten_background(img8)
    raw = u.segment_dark_regions(flat, img8=img8, mad_k=MADK)
    cleaned = D.clean_mask(raw, min_area_px=13)
    lab = skm.label(cleaned, connectivity=2)
    if lab.max():
        sz = np.bincount(lab.ravel())
        keep = np.where(sz >= 40)[0]
        final = np.isin(lab, keep[keep > 0])
    else:
        final = np.zeros_like(cleaned, bool)
    return flat, raw, cleaned, final


def mask_on_field(img8, mask, colour=None):
    rgb = np.dstack([img8.astype(np.float32)] * 3) / 255.0
    rgb[mask] = np.array(colour if colour is not None else J.rgb(J.MASK))
    return np.clip(rgb, 0, 1)


def pick():
    """Typical, by a stated rule, among frames whose annotation is a trace."""
    rows = []
    for f in sorted(os.listdir(CORR)):
        if not f.endswith("_correction.npy"):
            continue
        stem = f[: -len("_correction.npy")]
        tif = os.path.join(TXM_REPO, "images", stem + ".tif")
        if not os.path.exists(tif):
            continue
        corr = np.load(os.path.join(CORR, f))
        crack, notc = corr == 1, ((corr == 2) | (corr == 3))
        if crack.sum() < 5000 or notc.sum() < 5000:
            continue
        dt = ndi.distance_transform_edt(crack)
        if float((dt[crack] > DEEP_PX).mean()) > MAX_DEEP_SHARE:
            continue
        img8 = D.load_as_uint8(tif)
        if img8.shape != corr.shape:
            continue
        *_, final = stages(img8)
        c, n = int(crack.sum()), int(notc.sum())
        tp, fp = int((final & crack).sum()), int((final & notc).sum())
        acc = 100.0 * (tp + (n - fp)) / (c + n)
        rows.append({"stem": stem, "tif": tif, "corr": corr, "img8": img8,
                     "margin": acc - 100.0 * n / (c + n),
                     "recall": tp / max(c, 1)})
        print(f"  eligible {stem[14:52]:<40} margin {rows[-1]['margin']:+7.2f} pp  "
              f"recall {rows[-1]['recall']:.3f}", flush=True)
    if not rows:
        raise SystemExit("no eligible TXM frame")
    med = float(np.median([r["margin"] for r in rows]))
    best = min(rows, key=lambda r: abs(r["margin"] - med))
    print(f"\n  median margin over {len(rows)} eligible frames {med:+.2f} pp -> showing "
          f"{best['stem'][14:60]} at {best['margin']:+.2f} pp")
    return best, len(rows), med


def main():
    best, n_elig, med = pick()
    img, corr = best["img8"], best["corr"]
    flat, raw, cleaned, final = stages(img)
    crack = corr == 1
    ref = crack | ((corr == 2) | (corr == 3))

    # WHERE THE DETAIL IS, and why it is not the median painted pixel. The median landed
    # against the right edge of this mosaic, where a black padding bar runs the full
    # height: the detector marks that bar, so the crop filled with a rectangle of mask and
    # the stages could not be read. The window is instead the one with the MOST painted
    # crack in it, constrained to sit at least a quarter of its own width inside the
    # frame. The padding bar is a real failure and is reported in the text; it is not what
    # this plate is for.
    H = min(DETAIL, img.shape[0], img.shape[1])
    dens = ndi.uniform_filter(crack.astype(np.float32), H)
    m = H // 4
    edge = np.zeros_like(dens, bool)
    edge[:H // 2 + m, :] = edge[-(H // 2 + m):, :] = True
    edge[:, :H // 2 + m] = edge[:, -(H // 2 + m):] = True
    dens[edge] = -1.0
    if dens.max() <= 0:
        raise SystemExit("mk_txm_pipeline: no interior window holds painted crack -- "
                         "do not fall back to the frame edge, pick another frame")
    cy, cx = (int(v) for v in np.unravel_index(int(np.argmax(dens)), dens.shape))
    y0 = max(min(cy - H // 2, img.shape[0] - H), 0)
    x0 = max(min(cx - H // 2, img.shape[1] - H), 0)
    sl = (slice(y0, y0 + H), slice(x0, x0 + H))
    print(f"  detail {H} px at ({y0}, {x0}); it holds "
          f"{int(crack[sl].sum()):,} of the frame's {int(crack.sum()):,} painted pixels")

    # DISPLAY ONLY, and the caption says so: load_as_uint8 stretches the whole frame, so
    # a crop of one corner of a TXM mosaic renders nearly flat. The detector ran on the
    # unstretched array; every mask panel below is that run, not a rerun on this crop.
    det = img[sl].astype(np.float32)
    lo, hi = np.percentile(det, [1, 99])
    det8 = (255 * np.clip((det - lo) / max(hi - lo, 1e-6), 0, 1)).astype(np.uint8)

    ann = np.dstack([det8.astype(np.float32)] * 3) / 255.0
    ann[~ref[sl]] *= 0.62
    ann[crack[sl]] = np.array(J.rgb(J.PAINT_CRACK))
    ann = np.clip(ann, 0, 1)

    step = max(1, img.shape[1] // 1600)
    panels = [det8,
              flat[sl],
              mask_on_field(det8, raw[sl]),
              mask_on_field(det8, cleaned[sl]),
              mask_on_field(det8, final[sl]),
              ann]

    fig = plt.figure(figsize=(J.PAGEW, 5.35))
    gs = fig.add_gridspec(3, 3, height_ratios=[1.32, 1, 1], hspace=0.016, wspace=0.016)
    axw = fig.add_subplot(gs[0, :])
    axw.imshow(img[::step, ::step], cmap="gray", interpolation="nearest", aspect="equal")
    axw.add_patch(Rectangle((x0 / step, y0 / step), H / step, H / step, fill=False,
                            edgecolor=J.ROI, linewidth=1.2))
    J.micrograph(axw)
    J.panel_label(axw, "a", inside=True)
    scalebar(axw, NM_PER_PX * step, img.shape[1] / step)

    for i, arr in enumerate(panels):
        ax = fig.add_subplot(gs[1 + i // 3, i % 3])
        ax.imshow(arr, cmap="gray" if arr.ndim == 2 else None, interpolation="nearest")
        J.micrograph(ax)
        J.panel_label(ax, "bcdefg"[i], inside=True)
        scalebar(ax, NM_PER_PX, H)

    p = os.path.join(OUT, NAME + ".png")
    fig.subplots_adjust(left=0.004, right=0.996, top=0.996, bottom=0.004)
    J.save(fig, p, printed_width=J.COLUMN_CLASS.get(NAME, ("double", J.W2))[1])
    json.dump({"figure": NAME + ".png", "frame": best["stem"], "nm_per_px": NM_PER_PX,
               "frame_px": [int(img.shape[0]), int(img.shape[1])],
               "detail_px": H, "crop_origin": [int(y0), int(x0)],
               "selection_rule": f"of the {n_elig} frames with at least 5,000 refereed "
                                 f"pixels of each verdict and at most "
                                 f"{100 * MAX_DEEP_SHARE:.0f}% of the annotation more "
                                 f"than {DEEP_PX} px inside itself, the one whose "
                                 f"accuracy margin is closest to the median "
                                 f"({med:+.2f} pp); this frame is at "
                                 f"{best['margin']:+.2f} pp",
               "frame_margin_pp": best["margin"], "frame_recall": best["recall"],
               "settings": {"scale_ladder": list(DO.SCALE_LADDER),
                            "absolute_dark_thresh": DO.ABSOLUTE_DARK_THRESH,
                            "mad_k": MADK,
                            "use_region_classifier": DO.USE_REGION_CLASSIFIER},
               "display": "panels (b)-(g) are contrast-stretched 1-99 percentile for "
                          "display; the detector ran on the unstretched frame and every "
                          "mask shown is that run",
               "note": "panels are the real intermediate arrays, not illustrations"},
              open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
