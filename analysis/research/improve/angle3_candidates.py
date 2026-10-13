"""ANGLE 3 -- raise PRECISION by proposing better candidates, never by deleting regions.

VERDICT: NO GAIN EXISTS IN THE CANDIDATE STAGE, and the reason is arithmetic rather than
a failure to search. Shared machinery lives here; the experiments import it so there is
exactly one definition of "the shipped candidate stage" in this angle, lifted from
detector_overrides.install() itself (including its _flatten closure) rather than
reimplemented. Scored through analysis/research/tilebench.py, leave-one-SPECIMEN-out, and
gated against the hand paint by angle3_paint_gate.py.

--------------------------------------------------------------------------------------
1. THE TILE PRECISION NUMBER IS ONE OBJECT.

Of the 176,225 false-positive pixels the shipped path produces over the 26 tiles,
140,415 -- 79.7% -- are a SINGLE connected region, the off-specimen void on
MAR_H_HIP_CBS_0002, which contains zero true positives. The next largest tile contributes
2.4%. Purity by component size over the same masks:

      <100 px      132 regions      3,005 TP     5,638 FP   purity 0.348
      100-1k       139 regions     24,305 TP    17,971 FP   purity 0.575
      1k-10k        29 regions     75,166 TP    11,781 FP   purity 0.865
      10k-100k       2 regions     24,216 TP       420 FP   purity 0.983
      >100k          1 region            0 TP   140,415 FP  purity 0.000   <- the void

Large regions are the PURE ones here, which is the same fact that killed the thickness
excisions. Pooled tile precision 0.4182 is therefore not a property of the proposal rule;
it is "does the void flood". Off that one tile precision is already 0.7833.

--------------------------------------------------------------------------------------
2. NO ADDITIVE CHANGE CAN RAISE PRECISION, AND THIS IS CHECKABLE WITHOUT SEARCHING.

A strict superset raises precision if and only if the pixels it adds are purer than the
operating point it adds them to. Shipped operating purity is 0.4182 pooled, 0.7833 off
the void. Every superset reachable from the candidate stage, measured (exp7_purity):

      feature filter 40 -> 13        adds     4,928 px at purity 0.2601
      feature filter 40 -> 1         adds     5,920 px at purity 0.2350
      mad_k 5.0 -> 4.0               adds    26,760 px at purity 0.3709
      mad_k 5.0 -> 3.0               adds   102,824 px at purity 0.2258
      close_radius 3 -> 5            adds     7,619 px at purity 0.3930
      open_radius 1 -> 0             adds    11,849 px at purity 0.2818

All six are below 0.4182 and every one is far below 0.7833. Loosening the proposal rule
in ANY direction lowers precision; that is why this angle has no additive answer. The
only pixels pure enough to raise precision are ones nothing currently proposes, which is
the recall problem and is owned elsewhere.

Nor is the remaining error boundary bleed that a reshaped proposal could trim: 62.7% of
the off-void false-positive pixels (92.5% with the void) lie MORE than 10 px from any
hand-marked crack. They are whole wrong objects, not fat edges.

--------------------------------------------------------------------------------------
3. THE ONE BIG APPARENT WIN IS THE FIFTH DEAD RULE: DROPPING `img8 < 10`.

Removing the absolute darkness term is the only change that moves pooled tile precision
at all, and it moves it a long way -- P 0.4181 -> 0.6910, IoU 0.3344 -> 0.4522. It is a
deleter, and unusually it can be convicted on the TILES, before the paint:

  * The gain is the void and nothing else. Off that tile it is P 0.7833 -> 0.8254 for
    R 0.6250 -> 0.5661, i.e. IoU 0.5329 -> 0.5056, a REGRESSION.
  * Per specimen it is catastrophic. 260622_316_H_b2, 260622_316_amb_b3 and
    MAR_Amb_Cast each lose 100% of their true positives; MAR_Amb_AS loses 91.9%,
    HIP_24hr 56.5%. The repo already knew the term carries half of full-frame recall
    (fullframe_recall_recovery.py: 10,516,306 of 20,923,398 proposed painted crack px are
    found by that term and no ladder rung); what is new here is that on five specimens it
    carries nearly all of it, and that its precision benefit is one region on one tile.
  * Leave-one-specimen-out puts the benefit and the cost on DISJOINT specimens and so
    prices it correctly. Over a 48-cell knob grid, 12 of 13 folds select an abs-off
    variant; the thirteenth -- the fold holding out MAR_H_HIP, the only specimen the gain
    exists on -- selects abs=10, so the void floods anyway and that fold scores P 0.1505.
    Held-out IoU for the whole family is 0.3338 against the shipped 0.3344, with a fitted
    gap of +0.1443. The grid winner (mad_k 4.0, abs off, open 2, close 5, filter 100)
    reads P 0.6724 R 0.6229 IoU 0.4779 fitted and buys nothing held-out.

--------------------------------------------------------------------------------------
4. THE REMAINING KNOBS ARE NOISE, AND THE BEST OF THEM FAILS ITS OWN SABOTAGE TEST.

mad_k is already at its optimum with the union (P peaks at 5.0; 6.0 is P 0.4075,
4.0 is P 0.4088 with more recall). Leave-one-scale-out of the ladder moves precision by
at most +0.0025 and loses recall every time. clean_mask's radii, never tuned before, are
at or beside their optimum: close_radius 3 vs 0 is +0.0017 P for -0.0117 R; open_radius 2
is +0.0054 P for -0.0304 R. The best of them, moving the feature filter 40 -> 100, is
+0.0021 P for -0.0148 R and -0.0030 IoU -- and it does not survive a sabotage test:
removing a RANDOM HALF of the 40-99 px band it targets delivers +0.0015/+0.0016/+0.0019 P
for half the pixels. Per pixel removed, random is as good. The threshold carries no
information beyond "delete some low-purity small regions".
"""
import os, sys, json
import numpy as np

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
for p in (R, R + "/improve",
          "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code",
          "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/interior_active_learning/code",
          "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis"):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True

import warnings
warnings.filterwarnings("ignore")
from scipy import ndimage as ndi
from skimage import filters, morphology
import detect_cracks as D
import detector_overrides as DO

SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
MY = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
      "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/angle3")
WORK = MY + "/work"
os.makedirs(WORK, exist_ok=True)


# ----------------------------------------------------------------- the shipped stage
class _FakeUP:
    pass


_SEGCACHE = {}


def seg_fn(**kw):
    """The shipped multi-scale segment_dark_regions, straight out of install()."""
    key = tuple(sorted((k, v) for k, v in kw.items()))
    if key not in _SEGCACHE:
        up = _FakeUP()
        DO.install(up, use_multiscale_union=True, **kw)
        _SEGCACHE[key] = up.segment_dark_regions
    return _SEGCACHE[key]


def flat40(img8):
    return D.flatten_background(img8, sigma=40)


def dark_single(img8, flat=None, mad_k=5.0, absolute_dark=10, denoise_sigma=1.0):
    """The v1.48 single-scale cut, for the collapse control."""
    flat = flat40(img8) if flat is None else flat
    sm = filters.gaussian(flat, sigma=denoise_sigma, preserve_range=True)
    med = np.median(sm)
    mad = np.median(np.abs(sm - med)) * 1.4826
    cut = sm < min(filters.threshold_otsu(sm), med - mad_k * mad)
    return cut | (img8 < absolute_dark)


def dark_shipped(img8, flat=None, mad_k=5.0, absolute_dark=10, ladder=None):
    flat = flat40(img8) if flat is None else flat
    kw = {}
    if ladder is not None:
        kw["scale_ladder"] = ladder
    f = seg_fn(**kw)
    return f(flat, img8=img8, mad_k=mad_k, absolute_dark_thresh=absolute_dark)


def clean(dark, open_radius=1, close_radius=3, min_area=13, fill=True):
    """detect_cracks.clean_mask, with every step exposed so each can be moved.

    Reproduces D.clean_mask exactly at the shipped settings -- asserted in selfcheck().
    """
    m = morphology.remove_small_objects(dark, max_size=min_area)
    if open_radius:
        m = morphology.opening(m, morphology.disk(open_radius))
    if close_radius:
        m = morphology.closing(m, morphology.disk(close_radius))
    if fill:
        m = ndi.binary_fill_holes(m)
    return m


#: extract_candidates labels with measure.label(connectivity=2), i.e. 8-connected, so
#: this must too. scipy's ndi.label defaults to 4-connected, which is a different filter.
#: selfcheck() asserts this reproduces detect_cracks.extract_candidates bit-for-bit.
_CONN8 = ndi.generate_binary_structure(2, 2)


def area_filter(mask, min_area_px=40):
    """unified_pipeline's extract_candidates(min_area_px=40) -- the production filter
    that crackpipe.stages omits. Region-level, but PURELY by size and it only ever
    removes small things, so it is in scope for an additive angle only as a knob to
    MOVE, never as a new rejection rule.

    MEASURED connectivity caveat: angle3_paint_gate.py's 48-frame run was made with the
    4-connected ndi.label default. Across the 26 tiles the two spellings differ by 242 px
    of 303,159 (0.08%) and the tile scores are P 0.4182/0.4181, R 0.6252/0.6255, IoU
    0.3344 both -- identical to four decimals. The gate's verdicts (99.95% and 99.36%
    deletion) cannot turn on 0.08%, so that run was not repeated; anything quoted from
    here on is the 8-connected, production-identical filter.
    """
    if min_area_px <= 1:
        return mask
    lab, n = ndi.label(mask, structure=_CONN8)
    if n == 0:
        return mask
    sizes = np.bincount(lab.ravel())
    keep = sizes >= min_area_px
    keep[0] = False
    return keep[lab]


def shipped_mask(img8, flat=None, **kw):
    """What v1.49.1 marks on a tile: multi-scale union -> clean_mask -> (no classifier).
    min_area_px defaults to 13 here, matching crackpipe/tilebench's shipped arm."""
    ma = kw.pop("min_area", 13)
    oc = dict(open_radius=kw.pop("open_radius", 1), close_radius=kw.pop("close_radius", 3),
              fill=kw.pop("fill", True))
    return clean(dark_shipped(img8, flat, **kw), min_area=ma, **oc)


# ----------------------------------------------------------------- controls
def selfcheck(verbose=True):
    import tilebench as TB
    t = TB.load(with_raw=True)[0]
    img8 = t["img8"]
    f = flat40(img8)
    ok = True

    a = clean(dark_single(img8, f), min_area=13)
    b = D.clean_mask(dark_single(img8, f), open_radius=1, close_radius=3, min_area_px=13)
    same = np.array_equal(a, b)
    ok &= same
    if verbose:
        print(f"  CONTROL clean() == detect_cracks.clean_mask: {'PASS' if same else 'FAIL'}")

    a = dark_shipped(img8, f, ladder=(40,))
    b = dark_single(img8, f)
    same = np.array_equal(a, b)
    ok &= same
    if verbose:
        print(f"  CONTROL ladder=(40,) reproduces the single-scale cut: "
              f"{'PASS' if same else 'FAIL'}")

    full = dark_shipped(img8, f)
    sup = bool((b & ~full).sum() == 0)
    ok &= sup
    if verbose:
        print(f"  CONTROL full ladder is a superset of single scale: "
              f"{'PASS' if sup else 'FAIL'}  ({int(b.sum()):,} -> {int(full.sum()):,} px)")

    lifted = _shipped_flatten()
    if lifted is None:
        ok = False
        print("  CONTROL lifted install()._flatten: FAIL (closure layout changed)")
    else:
        bad = [s for s in DO.SCALE_LADDER
               if not np.array_equal(lifted(img8, s), _flatten_like_shipped(img8, s))]
        ok &= not bad
        print(f"  CONTROL mirror == install()'s own _flatten at every radius: "
              f"{'PASS' if not bad else 'FAIL ' + str(bad)}")

    cl = clean(dark_shipped(img8, f), min_area=13)
    lab, _ = D.extract_candidates(cl, np.zeros_like(cl, np.uint8),
                                  np.zeros(cl.shape, np.float64), min_area_px=40)
    same = np.array_equal(area_filter(cl, 40), lab > 0)
    ok &= same
    if verbose:
        print(f"  CONTROL area_filter == detect_cracks.extract_candidates(40): "
              f"{'PASS' if same else 'FAIL'}")
    return ok




# ----------------------------------------------------------------- cheap sweeps
def scale_cache(img8, ladder=DO.SCALE_LADDER):
    """Per-sigma (smoothed flat, otsu, median, mad) so any mad_k is then free.

    This is the same arithmetic install()'s segment_dark_regions does, factored so a
    sweep over mad_k does not re-flatten seven times per setting. cut_at() below is
    asserted bit-identical to the shipped function in selfcheck_sweep().
    """
    up = _FakeUP()
    DO.install(up)                      # only to reuse the module's own _flatten
    out = []
    for sigma in ladder:
        f = D.flatten_background(img8, sigma=40) if sigma == 40 else _flatten_like_shipped(img8, sigma)
        sm = filters.gaussian(f, sigma=1.0, preserve_range=True)
        med = float(np.median(sm))
        mad = float(np.median(np.abs(sm - med)) * 1.4826)
        out.append(dict(sigma=sigma, sm=sm, otsu=float(filters.threshold_otsu(sm)),
                        med=med, mad=mad))
    return out


def _shipped_flatten():
    """detector_overrides.install()'s own `_flatten`, lifted out of the closure it is
    defined in rather than copied. install() builds segment_dark_regions over it, so the
    function object is reachable through __closure__ and cannot drift from what the app
    runs. Falls back to the mirror below only if the closure layout ever changes, and
    selfcheck() asserts the two agree."""
    fn = seg_fn()
    for name, cell in zip(fn.__code__.co_freevars, fn.__closure__ or ()):
        if name == "_flatten":
            return cell.cell_contents
    return None


def _flatten_like_shipped(img8, sigma):
    """A mirror of that closure, kept only so the lift above has something to be checked
    against. selfcheck() asserts they are bit-identical at every ladder radius."""
    from scipy import ndimage as _ndi
    from skimage import exposure as _exp
    if sigma <= DO.DECIMATE_ABOVE_SIGMA:
        return D.flatten_background(img8, sigma=sigma)
    f = max(1, int(round(sigma / 32.0)))
    small = _ndi.uniform_filter(img8.astype(np.float32), f)[::f, ::f]
    bg_s = _ndi.gaussian_filter(small, sigma / f, mode="nearest")
    bg = _ndi.zoom(bg_s, (img8.shape[0] / bg_s.shape[0], img8.shape[1] / bg_s.shape[1]),
                   order=1, mode="nearest")[:img8.shape[0], :img8.shape[1]]
    if bg.shape != img8.shape:
        bg = np.pad(bg, ((0, img8.shape[0] - bg.shape[0]),
                         (0, img8.shape[1] - bg.shape[1])), mode="edge")
    flat = img8.astype(np.float32) - bg
    lo, hi = np.percentile(flat, [0.5, 99.5])
    if hi <= lo:
        lo, hi = flat.min(), flat.max()
    return _exp.rescale_intensity(flat, in_range=(lo, hi), out_range=(0, 255)).astype(np.uint8)


def cut_at(sc, mad_k):
    return sc["sm"] < min(sc["otsu"], sc["med"] - mad_k * sc["mad"])


def union_at(cache, img8, mad_k=5.0, absolute_dark=10, scales=None):
    out = None
    for sc in cache:
        if scales is not None and sc["sigma"] not in scales:
            continue
        c = cut_at(sc, mad_k)
        out = c if out is None else (out | c)
    if out is None:
        out = np.zeros(img8.shape, bool)
    if absolute_dark is not None and absolute_dark > 0:
        out = out | (img8 < absolute_dark)
    return out


def selfcheck_sweep(tiles, verbose=True):
    ok = True
    for t in tiles[:3]:
        cache = scale_cache(t["img8"])
        a = union_at(cache, t["img8"], 5.0)
        b = dark_shipped(t["img8"])
        same = np.array_equal(a, b)
        ok &= same
        if verbose:
            print(f"  CONTROL cached union == shipped segment_dark_regions on "
                  f"{t['frame'][:28]}: {'PASS' if same else 'FAIL'}")
        a1 = union_at(cache, t["img8"], 5.0, scales=(40,))
        b1 = dark_single(t["img8"])
        same = np.array_equal(a1, b1)
        ok &= same
        if verbose:
            print(f"  CONTROL cached scales=(40,) == v1.48 cut: {'PASS' if same else 'FAIL'}")
    return ok


if __name__ == "__main__":
    print("CONTROLS")
    print("ok" if selfcheck() else "FAILED")
