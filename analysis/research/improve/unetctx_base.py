"""APPROACH 2 -- U-Net on the FULL FRAMES. Shared setup.

Scoring is NOT redefined here. It is imported from ctx_core, which already reproduces the
task's baseline table to 4 dp (clDice = MEDIAN over tiles, P/R/F1/IoU pooled over pixels,
every arm passed through the same clean_mask+40px candidate filter). Two scorers make a
gain unreadable, so there is exactly one.

The only thing this module changes about ctx_core is WHERE its per-tile cache lives: a
peer session is writing ctx_core's own cache directory right now, and reading a
half-written npz out of it is how you get a BadZipFile mid-sweep. Same code, own cache.

What this module adds is the full-frame corpus: 48 hand-painted frames, 70,041,625 px of
crack paint, read-only. Everything about those frames that the U-Net needs -- the
field-of-view crop, the alignment of the correction mask to it, the specimen each frame
belongs to -- is defined once, here.
"""
import os, sys
import numpy as np

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
for p in (R, R + "/improve"):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True

MY = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
      "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/unet")
os.makedirs(MY, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", MY + "/mpl")

import ctx_core as CC
CC.MY = MY                      # own cache; never touch the peer session's
CC._CACHE = {}
os.makedirs(MY, exist_ok=True)

from PIL import Image
from scipy import ndimage as ndi
import detect_cracks as D
Image.MAX_IMAGE_PIXELS = None

SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
ORIG = os.path.join(SEM, "original")
FRAMEDIR = os.path.join(MY, "frames")
os.makedirs(FRAMEDIR, exist_ok=True)


def frame_names():
    return sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
                  if f.endswith("_correction_mask.png"))


def specimen_of(name):
    """The specimen key tilebench uses, derived from the frame name the same way.

    tiles_meta.json already carries the mapping for the frames it crops; this reproduces
    it for the painted frames, which tiles_meta does not cover. A frame is <specimen>_
    <detector>_<index>, where the detector token is CBS / ETD / SE / BSE.
    """
    parts = name.split("_")
    for i, p in enumerate(parts):
        if p in ("CBS", "ETD", "SE", "BSE"):
            parts = parts[:i]
            break
    else:
        parts = parts[:-1]
    # tiles_meta calls 260622_316_H_b2_front_CBS_03 specimen "260622_316_H_b2": the
    # fracture-surface side is not a specimen. Eight tile parents ARE painted frames, so
    # getting this wrong would put the same micrograph in train and test.
    if parts and parts[-1] in ("front", "back"):
        parts = parts[:-1]
    return "_".join(parts)


def load_frame(name):
    """uint8 micrograph cropped to its field of view, plus the aligned correction mask.

    Returns (img8, corr) with corr in {0 unreviewed, 1 crack, 2 not-crack}, or None if
    the pair cannot be aligned. READ ONLY -- the paint is irreplaceable research data.
    """
    c = os.path.join(FRAMEDIR, name + ".npz")
    if os.path.exists(c):
        try:
            z = np.load(c)
            return z["img8"], z["corr"]
        except Exception:
            os.remove(c)
    cm = os.path.join(PAINT, name + "_correction_mask.png")
    src = next((os.path.join(ORIG, name + e) for e in (".tif", ".tiff", ".png")
                if os.path.exists(os.path.join(ORIG, name + e))), None)
    if src is None or not os.path.exists(cm):
        return None
    img8 = D.load_as_uint8(src)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]
    corr = np.array(Image.open(cm))
    if corr.ndim == 3:
        corr = corr[..., 0]
    if corr.shape != img8.shape:
        if corr.shape[0] >= y1 and corr.shape[1] >= x1:
            corr = corr[y0:y1, x0:x1]
        else:
            return None
    np.savez_compressed(c, img8=img8, corr=corr.astype(np.uint8))
    return img8, corr.astype(np.uint8)


if __name__ == "__main__":
    print("BASELINE REPRODUCTION through ctx_core (own cache)")
    ok, _ = CC.selfcheck()
    print("reproduced\n" if ok else "FAILED -- do not trust anything built on this\n")

    from collections import Counter
    names = frame_names()
    print(f"{len(names)} painted frames")
    tot_c = tot_n = tot_px = 0
    bad = []
    spec = Counter()
    for n in names:
        r = load_frame(n)
        if r is None:
            bad.append(n); continue
        img8, corr = r
        tot_c += int((corr == 1).sum()); tot_n += int((corr == 2).sum())
        tot_px += corr.size
        spec[specimen_of(n)] += 1
    print(f"  loaded {len(names)-len(bad)}, unalignable {len(bad)}: {bad}")
    print(f"  crack paint   {tot_c:,} px")
    print(f"  not-crack     {tot_n:,} px")
    print(f"  unreviewed    {tot_px-tot_c-tot_n:,} px  ({100*(tot_px-tot_c-tot_n)/tot_px:.1f}%)")
    print(f"  frame specimens: {dict(spec)}")
    ts = CC.tiles()
    tspec = sorted({t["specimen"] for t in ts})
    print(f"  tile specimens ({len(tspec)}): {tspec}")
    print(f"  tile specimens WITH paint   : {sorted(set(tspec) & set(spec))}")
    print(f"  tile specimens WITHOUT paint: {sorted(set(tspec) - set(spec))}")
