"""Cache, once per full frame, everything an ANGLE-2 specimen-mask variant needs.

Rationale: the primary gate (48 hand-painted frames) must be re-runnable for every
candidate specimen mask, and the expensive part -- the v1.49 seven-radius darkness union
on a 25 Mpx frame -- does not depend on the variant at all. So compute it once and store:

    clean    the SHIPPED candidate mask (bit-packed), i.e. what the classifier-off,
             multi-scale-union path keeps. Its intersection with hand-painted crack is
             the DENOMINATOR for every deletion figure. Taken from
             detector_overrides.install() itself, never reimplemented.
    crack/notc/erase   the hand paint, 1/2/3. 0 (unreviewed, 91% of the corpus) is never
             stored and never counted, in either numerator or denominator.
    bmean/bstd   8x8 block mean and block standard deviation of the FOV-cropped img8.
             A specimen mask is a coarse-scale object; these two are a sufficient
             statistic for any coarse texture-energy variant and are 1/64 the size.
    dark8    8x8 block max of the shipped candidate mask, for coarse-scale diagnostics.

Nothing is written outside the scratchpad. sem-crack-detector is READ ONLY.
"""
import os, sys, time, json
import warnings; warnings.filterwarnings("ignore")

SC = "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad"
WORK = os.path.join(SC, "specseg")
os.environ.setdefault("MPLCONFIGDIR", os.path.join(WORK, "mpl"))
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
APP = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
for p in (APP + "/analysis", APP + "/analysis/research", SEM + "/code",
          SEM + "/interior_active_learning/code"):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True

import numpy as np, tifffile
from PIL import Image
from skimage import exposure
Image.MAX_IMAGE_PIXELS = None
import detect_cracks as D
from common import contrast_kwargs_for

PAINT = os.path.join(SEM, "interior_active_learning", "paint")
CACHE = os.path.join(WORK, "framecache")
B = 8          # block factor for the coarse statistics


def frame_names():
    names = sorted(f[: -len("_correction_mask.png")] for f in os.listdir(PAINT)
                   if f.endswith("_correction_mask.png"))
    return [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]


def _shipped_segmenter():
    """The candidate stage that ACTUALLY SHIPS, taken from detector_overrides.install().

    Not reimplemented: install() is called on a stand-in module and the function it binds
    is used directly, so this cannot drift from what the app runs.
    """
    import detector_overrides as DO

    class _Stub:
        pass

    up = _Stub()
    DO.install(up, use_multiscale_union=True)
    return up.segment_dark_regions


def _single_scale_segmenter():
    import detector_overrides as DO

    class _Stub:
        pass

    up = _Stub()
    DO.install(up, use_multiscale_union=True, scale_ladder=(40,))
    return up.segment_dark_regions


def load_frame(name):
    """img8 and the correction mask, both in FOV coordinates, exactly as the app sees."""
    raw = tifffile.imread(os.path.join(SEM, "original", name + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    ck = contrast_kwargs_for(name)
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]
    corr = np.array(Image.open(os.path.join(PAINT, name + "_correction_mask.png")))
    while corr.ndim > 2:
        corr = corr[..., 0]
    if corr.shape != img8.shape:
        if corr.shape[0] >= y1 and corr.shape[1] >= x1:
            corr = corr[y0:y1, x0:x1]
        else:
            return None
    return img8, corr, (x0, y0, x1, y1)


def blocks(img8, b=B):
    """Block mean and block std at factor b -- the coarse texture statistic."""
    h, w = img8.shape
    hh, ww = h // b * b, w // b * b
    a = img8[:hh, :ww].astype(np.float32).reshape(hh // b, b, ww // b, b)
    m = a.mean(axis=(1, 3))
    s = np.sqrt(np.maximum(a.var(axis=(1, 3)), 0))
    return m.astype(np.float32), s.astype(np.float32)


def build(names=None, verbose=True):
    os.makedirs(CACHE, exist_ok=True)
    seg = _shipped_segmenter()
    names = names or frame_names()
    t0 = time.time()
    for i, n in enumerate(names, 1):
        out = os.path.join(CACHE, n + ".npz")
        if os.path.exists(out):
            if verbose:
                print(f"  [{i}/{len(names)}] {n}  cached", flush=True)
            continue
        got = load_frame(n)
        if got is None:
            if verbose:
                print(f"  [{i}/{len(names)}] {n}  SKIP (paint does not fit the image)", flush=True)
            continue
        img8, corr, fov = got
        flat = D.flatten_background(img8, sigma=40)
        clean = D.clean_mask(seg(flat, img8=img8), open_radius=1, close_radius=3, min_area_px=13)
        bm, bs = blocks(img8)
        np.savez_compressed(
            out, shape=np.array(img8.shape), fov=np.array(fov),
            clean=np.packbits(clean), crack=np.packbits(corr == 1),
            notc=np.packbits(corr == 2), erase=np.packbits(corr == 3),
            bmean=bm, bstd=bs)
        if verbose:
            print(f"  [{i}/{len(names)}] {n:<36} {img8.shape}  clean {int(clean.sum()):>10,}  "
                  f"crack {int((corr == 1).sum()):>10,}  {time.time() - t0:5.0f}s", flush=True)
    return CACHE


def load(name):
    z = np.load(os.path.join(CACHE, name + ".npz"))
    sh = tuple(int(v) for v in z["shape"])
    n = sh[0] * sh[1]

    def un(k):
        return np.unpackbits(z[k])[:n].astype(bool).reshape(sh)

    return dict(name=name, shape=sh, clean=un("clean"), crack=un("crack"),
                notc=un("notc"), erase=un("erase"),
                bmean=z["bmean"], bstd=z["bstd"])


def cached_names():
    return sorted(f[:-4] for f in os.listdir(CACHE) if f.endswith(".npz"))


if __name__ == "__main__":
    build()
    print(f"\n{len(cached_names())} frames cached in {CACHE}")
