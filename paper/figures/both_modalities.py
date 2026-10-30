#!/usr/bin/env python3
"""One SEM field and one TXM field, loaded and staged the way the application does it.

WHY THIS MODULE EXISTS. Four figures now show the two modalities beside each other, and
each of them needs the same arrays: the frame, the flattened frame, the proposed pixels,
the cleaned mask, and the operator's painted verdicts where there are any. Re-deriving
those in four scripts invites the four to drift -- a different field, a different
`mad_k`, a different crop -- and a reader comparing panels across figures would be
comparing different runs. They come from here instead, so every figure that shows "the
SEM arm" shows the same pixels of the same field, and likewise for TXM.

WHICH FIELDS, AND WHY THESE. Both are chosen by the rules the single-modality figures
already used and recorded, not re-picked to suit a new layout:

  SEM  MAR_H_HIP_CBS_0007 at 51.883 nm/px -- of the 80 frames with a recovered pixel size
       and an original on disk, the one whose crack area fraction is closest to the
       median (mk_pipeline_visual.py). The evaluated public collection publishes no pixel
       size, so a panel drawn from it could carry no scale bar.

  TXM  b2_341_88_take2 at 29.24 nm/px -- of the frames with at least 5,000 refereed pixels
       of each verdict AND an annotation that is a trace rather than a filled region, the
       one whose accuracy margin is closest to the median of that set
       (mk_txm_pipeline.py). Typical rather than flattering.

The TXM pixel size is derived from operator-supplied mosaic geometry, not read from
instrument metadata; the SEM one is read from the databar. The caption of every figure
built on this module has to say so, because the two are not equally well founded.

CACHE. Loading and staging a 4096 x 6144 SEM frame takes about a minute, and five figure
scripts would pay it five times over. The staged arrays are written to FIG_CACHE as a
single .npz per modality, keyed by the settings that produced them: change `mad_k` or the
scale ladder and the key changes and the cache is rebuilt, so a stale cache cannot
silently answer for a changed detector.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/both_modalities.py
"""
import hashlib
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths                                      # noqa: E402

sys.path.insert(0, os.path.join(_paths.SEM_REPO, "code"))
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "interior_active_learning", "code"))
sys.path.insert(0, _paths.ANALYSIS)            # detector_overrides lives with the analysis
sys.dont_write_bytecode = True

import numpy as np                                 # noqa: E402
from skimage import measure as skm                  # noqa: E402

import detect_cracks as D                           # noqa: E402
import detector_overrides as DO                     # noqa: E402

#: The two fields, with the pixel size each is reported at and where that size came from.
SEM_FIELD = "MAR_H_HIP_CBS_0007"
SEM_NM_PER_PX = 51.883
SEM_SCALE_SOURCE = "read from the instrument databar"
TXM_FIELD = ("Average_mosaic_260618_b2_341_88_take2_idx00000_mosaictileAA_img001of010"
             ".xrm.bim.bim")
TXM_NM_PER_PX = 29.24
TXM_SCALE_SOURCE = "derived from operator-supplied mosaic geometry, not instrument metadata"

#: The detection setting the paper evaluates at. One constant, read by every figure.
MAD_K = 6.0
MIN_AREA_PX = 40
CLEAN_MIN_PX = 13


class _U:
    pass


_u = _U()
DO.install(_u)


def _key(tag):
    h = hashlib.sha1(json.dumps({
        "ladder": list(DO.SCALE_LADDER), "floor": DO.ABSOLUTE_DARK_THRESH,
        "mad_k": MAD_K, "min_area": MIN_AREA_PX, "clean_min": CLEAN_MIN_PX,
        "field": SEM_FIELD if tag == "sem" else TXM_FIELD,
    }, sort_keys=True).encode()).hexdigest()[:10]
    return os.path.join(_paths.FIG_CACHE, f"both_{tag}_{h}.npz")


def stages(img8):
    """The shipped path, every intermediate kept. The one copy of this in the figure set.

    `mk_pipeline_visual.stages` and `mk_txm_pipeline.stages` were two transcriptions of
    these six lines that had already diverged by one argument.
    """
    flat = D.flatten_background(img8)
    proposed = _u.segment_dark_regions(flat, img8=img8, mad_k=MAD_K)
    cleaned = D.clean_mask(proposed, min_area_px=CLEAN_MIN_PX)
    lab = skm.label(cleaned, connectivity=2)
    if lab.max():
        sz = np.bincount(lab.ravel())
        keep = np.where(sz >= MIN_AREA_PX)[0]
        final = np.isin(lab, keep[keep > 0])
    else:
        final = np.zeros_like(cleaned, bool)
    return flat, proposed, cleaned, final


def _load_sem():
    import tifffile
    from skimage import exposure
    from common import contrast_kwargs_for

    raw = tifffile.imread(os.path.join(_paths.SEM_REPO, "original", SEM_FIELD + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    ck = contrast_kwargs_for(SEM_FIELD)
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    return img8[y0:y1, x0:x1], (x0, y0, x1, y1)


def _load_txm():
    tif = os.path.join(_paths.TXM_REPO, "images", TXM_FIELD + ".tif")
    _paths.require(tif, f"TXM frame {TXM_FIELD}", "TXM_REPO")
    return D.load_as_uint8(tif), None


def _paint(tag, shape):
    """The operator's painted verdicts for this field, cut to the staged frame.

    Returns (crack, not_crack) boolean arrays, or (None, None) where the field carries no
    painted correction. State 1 is "this is crack"; 2 and 3 are both "this is not crack"
    -- 3 is the eraser, which is a not-crack verdict and not an absence of one.
    """
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    if tag == "sem":
        p = os.path.join(_paths.SEM_REPO, "interior_active_learning", "paint",
                         SEM_FIELD + "_correction_mask.png")
        if not os.path.exists(p):
            return None, None
        corr = np.array(Image.open(p))
        while corr.ndim > 2:
            corr = corr[..., 0]
    else:
        p = os.path.join(_paths.TXM_REPO, "paint", "corrections", TXM_FIELD + "_correction.npy")
        if not os.path.exists(p):
            return None, None
        corr = np.load(p)
    if corr.shape != shape:
        if corr.shape[0] >= shape[0] and corr.shape[1] >= shape[1]:
            corr = corr[: shape[0], : shape[1]]
        else:
            return None, None
    return corr == 1, (corr == 2) | (corr == 3)


def load(tag):
    """`load("sem")` or `load("txm")` -> dict of arrays, from cache where one is valid."""
    if tag not in ("sem", "txm"):
        raise ValueError(tag)
    path = _key(tag)
    if os.path.exists(path):
        z = np.load(path)
        return {k: z[k] for k in z.files if z[k].shape != ()} | {
            k: z[k].item() for k in z.files if z[k].shape == ()}
    img8, _fov = (_load_sem() if tag == "sem" else _load_txm())
    flat, proposed, cleaned, final = stages(img8)
    crack, notc = _paint(tag, img8.shape)
    out = {"img": img8, "flat": flat, "proposed": proposed, "cleaned": cleaned,
           "final": final,
           "nm_per_px": np.array(SEM_NM_PER_PX if tag == "sem" else TXM_NM_PER_PX),
           "field": np.array(SEM_FIELD if tag == "sem" else TXM_FIELD)}
    if crack is not None:
        out["paint_crack"], out["paint_notcrack"] = crack, notc
    os.makedirs(_paths.FIG_CACHE, exist_ok=True)
    np.savez_compressed(path, **out)
    return {k: (v.item() if v.shape == () else v) for k, v in out.items()}


def main():
    for tag in ("sem", "txm"):
        d = load(tag)
        px = float(d["nm_per_px"])
        h, w = d["img"].shape
        print(f"{tag.upper():<4} {str(d['field'])[:46]:<46} {w} x {h} px at {px} nm/px "
              f"= {w*px/1000:.0f} x {h*px/1000:.0f} um")
        print(f"     proposed {100*d['proposed'].mean():5.2f}%  cleaned "
              f"{100*d['cleaned'].mean():5.2f}%  final {100*d['final'].mean():5.2f}%"
              + ("  painted crack %.2f%% / not-crack %.2f%%"
                 % (100 * d["paint_crack"].mean(), 100 * d["paint_notcrack"].mean())
                 if "paint_crack" in d else "  no painted correction"))


if __name__ == "__main__":
    main()
