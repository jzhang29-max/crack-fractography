"""LEVER 1 -- CANDIDATE GENERATION. Can a better `dark` mask recover the 45.7% of marked
crack that never becomes a candidate?

The shipped generator is one GLOBAL cut on the flattened image:

    dark = (smooth < min(otsu, median - 5.0*MAD)) | (img8 < 10)

Everything downstream of it (clean_mask -> connected components -> the >=40 px feature
filter -> the shipped logistic classifier at its shipped threshold) is held FIXED here,
so any score change is attributable to the candidate mask and nothing else. The one
exception is the `feat_sigma` arm, which also moves the image the FEATURES are computed
on; it is labelled as such and reported separately.

Two numbers are reported for every generator, because they answer different questions:

  * the CANDIDATE CEILING -- what fraction of marked crack survives into a >=40 px
    labelled region, and what fraction of background it costs. This is an upper bound on
    recall and it is NOT a result: the shipped classifier computes its features on
    whatever regions we hand it and is free to reject the bigger ones.
  * the FULL END-TO-END score through CP.probability at the shipped threshold, run
    through tilebench so it is the same instrument that produced the 0.2143 baseline.

The classifier threshold is NEVER tuned here. Tuning mad_k and thr together was already
measured at held-out IoU 0.2180 -- worse than mad_k alone at 0.2382 -- so a second free
parameter is a known trap on 26 tiles, and this file spends its one parameter on the
candidate mask.
"""
import os, sys, json, time, warnings
warnings.filterwarnings("ignore")

SC = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
      "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
os.environ.setdefault("MPLCONFIGDIR", SC + "/mpl")
AN = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis"
if AN not in sys.path:
    sys.path.insert(0, AN)
sys.dont_write_bytecode = True

import numpy as np
from scipy import ndimage as ndi
from skimage import filters, morphology
import tilebench as TB
import crackpipe as CP
import detect_cracks as D

OUT = os.path.join(SC, "lever1")
os.makedirs(OUT, exist_ok=True)


# --------------------------------------------------------------------------- precompute
def precompute(sigmas=(40,), feat_sigmas=(40,)):
    """Per tile: the raw/uint8 image, and `flat`/`smooth` at each flattening sigma plus a
    Frangi map for each sigma whose image will carry the FEATURES. Frangi is the
    expensive stage, so it is computed only where it is actually consumed."""
    tiles = TB.load(with_raw=True)
    pre = []
    for i, t in enumerate(tiles, 1):
        img8 = t["img8"]
        P = dict(frame=t["frame"], specimen=t["specimen"], img8=img8, raw=t["raw"],
                 gt=t["gt"], flat={}, smooth={}, ves={}, stat={})
        for s in sorted(set(sigmas) | set(feat_sigmas)):
            f = D.flatten_background(img8, sigma=s)
            sm = filters.gaussian(f, sigma=1.0, preserve_range=True)
            P["flat"][s], P["smooth"][s] = f, sm
            med = float(np.median(sm))
            mad = float(np.median(np.abs(sm - med)) * 1.4826)
            P["stat"][s] = dict(otsu=float(filters.threshold_otsu(sm)), med=med, mad=mad)
        for s in feat_sigmas:
            P["ves"][s] = D.compute_vesselness(P["flat"][s])
        pre.append(P)
        print(f"  precomputed [{i:>2}/{len(tiles)}] {t['frame'][:46]}", flush=True)
    return pre


# ------------------------------------------------------------------- candidate generators
def g_mad(P, k=5.0, sigma=40, absolute=10):
    """The shipped generator with mad_k exposed. k=5.0 IS the shipped mask."""
    sm, st = P["smooth"][sigma], P["stat"][sigma]
    return (sm < min(st["otsu"], st["med"] - k * st["mad"])) | (P["img8"] < absolute)


def g_local(P, block=75, offset=4.0, method="gaussian", sigma=40, absolute=10):
    """skimage.threshold_local: a per-pixel cut `local_mean - offset`. The point of a
    local cut here is that a missed crack pixel sits at global robust-z about -1.7 --
    darker than background but nowhere near the 5-MAD bar -- while being much darker than
    its OWN neighbourhood."""
    sm = P["smooth"][sigma]
    th = filters.threshold_local(sm, block_size=block, method=method, offset=offset)
    return (sm < th) | (P["img8"] < absolute)


def g_sauvola(P, window=51, k=0.2, sigma=40, absolute=10):
    sm = P["smooth"][sigma]
    return (sm < filters.threshold_sauvola(sm, window_size=window, k=k)) | (P["img8"] < absolute)


def g_niblack(P, window=51, k=0.2, sigma=40, absolute=10):
    sm = P["smooth"][sigma]
    return (sm < filters.threshold_niblack(sm, window_size=window, k=k)) | (P["img8"] < absolute)


def g_hysteresis(P, hi=5.0, lo=2.0, sigma=40, absolute=10):
    """Classic two-level fix for exactly this trade: keep every connected component of
    the PERMISSIVE mask that contains at least one pixel of the STRICT one. The strict
    seed is the shipped mask, so this can only ever ADD pixels, and only ones physically
    attached to something the shipped detector already believed."""
    strict = g_mad(P, k=hi, sigma=sigma, absolute=absolute)
    loose = g_mad(P, k=lo, sigma=sigma, absolute=absolute)
    lab, n = ndi.label(loose, structure=np.ones((3, 3)))
    if n == 0:
        return strict
    keep = np.zeros(n + 1, bool)
    keep[np.unique(lab[strict])] = True
    keep[0] = False
    return keep[lab]


def g_multiscale(P, k=5.0, sigmas=(10, 20, 40, 80), absolute=10):
    """Union of the shipped cut taken at several flattening radii. flatten_background is
    a high-pass: a feature wider than the blur radius is erased by its own flattening, so
    a wide crack that vanishes at sigma=40 can survive at sigma=160, and a hairline that
    needs the tight background estimate survives at sigma=10."""
    m = P["img8"] < absolute
    for s in sigmas:
        sm, st = P["smooth"][s], P["stat"][s]
        m = m | (sm < min(st["otsu"], st["med"] - k * st["mad"]))
    return m


def g_mad_hyst_local(P, hi=5.0, block=75, offset=4.0, sigma=40, absolute=10):
    """Hysteresis whose permissive level is the LOCAL cut rather than a looser global
    one. Same containment rule: only components already seeded by the shipped mask."""
    strict = g_mad(P, k=hi, sigma=sigma, absolute=absolute)
    loose = g_local(P, block=block, offset=offset, sigma=sigma, absolute=absolute)
    lab, n = ndi.label(loose | strict, structure=np.ones((3, 3)))
    if n == 0:
        return strict
    keep = np.zeros(n + 1, bool)
    keep[np.unique(lab[strict])] = True
    keep[0] = False
    return keep[lab]


def g_twosided(P, k=5.0, kb=5.0, sigma=40, absolute=10):
    """Dark OR BRIGHT outliers. Three specimens (MAR_Amb_AS / _Cast / _HIP, all ETD) sit
    at recall 0.000 at every dark-threshold setting because their marked crack is
    BRIGHTER than the background median -- no one-sided dark test can ever reach them."""
    sm, st = P["smooth"][sigma], P["stat"][sigma]
    dark = (sm < min(st["otsu"], st["med"] - k * st["mad"])) | (P["img8"] < absolute)
    return dark | (sm > st["med"] + kb * st["mad"])


GENS = dict(mad=g_mad, local=g_local, sauvola=g_sauvola, niblack=g_niblack,
            hyst=g_hysteresis, multi=g_multiscale, hystlocal=g_mad_hyst_local,
            twosided=g_twosided)


# ------------------------------------------------------------------------------ scoring
def downstream(P, dark, feat_sigma=40, min_area=13, thr=CP.THR):
    """clean_mask -> components -> >=40 px feature filter -> shipped logistic -> cut.
    Byte-for-byte the shipped tail; only `dark` is ours."""
    flat, ves = P["flat"][feat_sigma], P["ves"][feat_sigma]
    clean = D.clean_mask(dark, open_radius=1, close_radius=3, min_area_px=min_area)
    lab, _ = ndi.label(clean)
    labeled, df = D.region_features_from_labeled(lab, flat, ves)
    prob = CP.probability(dict(labeled=labeled, df=df))
    return (prob >= thr), (labeled > 0)


def run_variant(pre, gen, feat_sigma=40, **kw):
    """-> (per-tile count rows for tilebench, candidate-ceiling totals)."""
    rows, cap = [], dict(gt=0, bg=0, gt_dark=0, bg_dark=0, gt_cand=0, bg_cand=0)
    for P in pre:
        dark = gen(P, **kw)
        pred, cand = downstream(P, dark, feat_sigma=feat_sigma)
        gt = P["gt"]
        cap["gt"] += int(gt.sum()); cap["bg"] += int((~gt).sum())
        cap["gt_dark"] += int((gt & dark).sum()); cap["bg_dark"] += int((~gt & dark).sum())
        cap["gt_cand"] += int((gt & cand).sum()); cap["bg_cand"] += int((~gt & cand).sum())
        rows.append(TB.counts(pred, gt))
    return rows, cap


def per_specimen(rows, tiles):
    """IoU per specimen, so a gain that lives in one specimen cannot hide in the pool."""
    out = {}
    for r, t in zip(rows, tiles):
        d = out.setdefault(t["specimen"], dict(tp=0, fp=0, fn=0))
        for k in ("tp", "fp", "fn"):
            d[k] += r[k]
    return {s: v["tp"] / max(v["tp"] + v["fp"] + v["fn"], 1) for s, v in out.items()}


# ----------------------------------------------- phase-4 generators: recover the precision
def g_vote(P, k=3.0, sigmas=(5, 10, 20, 40, 80, 160, 320), nvote=2, absolute=10):
    """Dark at at least `nvote` of the flattening radii, instead of at any one of them.
    The union buys recall by trusting a single scale; a vote asks the scales to agree,
    which is the cheapest way to ask for the precision back without touching the
    classifier. nvote=1 IS the union."""
    c = np.zeros(P["img8"].shape, np.uint8)
    for s in sigmas:
        sm, st = P["smooth"][s], P["stat"][s]
        c += (sm < min(st["otsu"], st["med"] - k * st["mad"]))
    return (c >= nvote) | (P["img8"] < absolute)


def g_ms_hyst(P, hi=5.0, lo=2.0, sigmas=(5, 10, 20, 40, 80, 160, 320), absolute=10):
    """Multi-scale union as the permissive level, the SHIPPED single-scale mask as the
    strict seed. Only components the shipped detector already touched can grow."""
    strict = g_mad(P, k=hi, sigma=40, absolute=absolute)
    loose = g_multiscale(P, k=lo, sigmas=sigmas, absolute=absolute)
    lab, n = ndi.label(loose | strict, structure=np.ones((3, 3)))
    if n == 0:
        return strict
    keep = np.zeros(n + 1, bool)
    keep[np.unique(lab[strict])] = True
    keep[0] = False
    return keep[lab]


def g_ms_raw(P, k=3.0, sigmas=(5, 10, 20, 40, 80, 160, 320), raw_frac=0.05):
    """Multi-scale union whose absolute-darkness term reads the RAW uint16 instead of the
    percentile-stretched uint8. img8 is clipped at the 1st percentile, so `img8 < 10` is a
    test on a quantity the stretch already destroyed; raw < raw_frac * median(raw) is the
    same intent measured where the number still means something."""
    thr = raw_frac * float(np.median(P["raw"]))
    m = P["raw"] < thr
    for s in sigmas:
        sm, st = P["smooth"][s], P["stat"][s]
        m = m | (sm < min(st["otsu"], st["med"] - k * st["mad"]))
    return m


def g_ms_two(P, k=3.0, kb=8.0, sigmas=(5, 10, 20, 40, 80, 160, 320), absolute=10):
    """Multi-scale union plus a multi-scale BRIGHT-outlier term, for the three ETD
    specimens whose marked crack is brighter than their background median."""
    m = g_multiscale(P, k=k, sigmas=sigmas, absolute=absolute)
    for s in sigmas:
        sm, st = P["smooth"][s], P["stat"][s]
        m = m | (sm > st["med"] + kb * st["mad"])
    return m


def g_ms_abs(P, k=3.0, sigmas=(40,), absolute=10, raw_frac=None):
    """One generator covering the whole 2x2: single- or multi-scale relative term, and an
    absolute-darkness term that is either the shipped `img8 < absolute`, a raw-uint16 test,
    or NONE at all (absolute=None, raw_frac=None).

    Why `img8 < 10` is worth ablating. load_as_uint8 stretches on the 1st and 99.5th
    PERCENTILES, so about 1% of every image is clipped to 0 whatever the image contains.
    `img8 < absolute_dark_thresh` therefore fires on roughly a fixed share of every frame
    by construction, not because anything in it is dark -- it is a percentile dressed as an
    absolute test. The raw uint16 is where "absolute darkness" still means something."""
    m = np.zeros(P["img8"].shape, bool)
    if absolute is not None:
        m |= P["img8"] < absolute
    if raw_frac is not None:
        m |= P["raw"] < raw_frac * float(np.median(P["raw"]))
    for s in sigmas:
        sm, st = P["smooth"][s], P["stat"][s]
        m = m | (sm < min(st["otsu"], st["med"] - k * st["mad"]))
    return m


# ============================================================================== THE RESULT
#
# HEADLINE (leave-one-specimen-out over the 9-value k grid, 26 tiles, 13 specimens):
#
#   generator                        precision  recall     IoU      F1
#   shipped mad_k=5.0 (baseline)        0.3378  0.3696  0.2143  0.3530
#   mad_k swept alone (known best)      0.3383  0.4460  0.2382  0.3847
#   SCALE VOTE >=3 of 7, k swept        0.3708  0.4984  0.2700  0.4252   <- this file
#
#   fitted-on-all-26 IoU 0.2700, overfit gap +0.0000: all 13 folds picked k=2.5, so the
#   held-out number and the fitted number are the same by outcome, not by construction.
#   8 specimens improve, 4 unchanged, 1 regresses (260622_316_amb_b3, -0.0442, one tile).
#   2 px tolerant: IoU 0.3018, F1 0.4636 (baseline 0.2355 / 0.3813).
#
# THE CAVEAT THAT HAS TO TRAVEL WITH IT. Pooled precision rises 0.3378 -> 0.3708, but on
# the 25 tiles WITHOUT MAR_H_HIP_CBS_0002__crop_3122_120 it FALLS, 0.8925 -> 0.7519, while
# recall rises 0.3709 -> 0.5001. That one tile contributes ~138,000 false positives at
# both settings; holding that constant mass fixed while true positives grow 35% is what
# makes the pooled precision go up. IoU and F1 improve on both populations
# (IoU 0.3550 -> 0.4293, F1 0.5240 -> 0.6007 on the clean 25); precision does not.
#
# WHAT DIED, and the control that killed it. Replacing `img8 < 10` with a raw-uint16
# absolute test scored a held-out IoU of 0.3566 -- and it is not real. The test is
# `raw < f * median(raw)`, and the flooded tile is more than half void, so ITS OWN median
# is 0; `raw < 0` marks nothing and the tile's 139,730 false positives vanish. Swapping
# the reference for any statistic the void cannot zero -- p75, p90, p99, mean, or a fixed
# DN as low as 50 -- brings them all back and the score falls to 0.2442. Reported as a
# negative result, not a gain.
# ============================================================================================

def headline(k_grid=(4.0, 3.5, 3.0, 2.75, 2.5, 2.0, 1.5, 1.0), nvote=3,
             ladder=(5, 10, 20, 40, 80, 160, 320)):
    """Reproduce the headline from scratch. ~2 minutes."""
    pre = precompute(sigmas=ladder, feat_sigmas=(40,))
    variants = {"shipped mad_k=5.0": run_variant(pre, g_mad, k=5.0)[0]}
    grid = {}
    for k in k_grid:
        grid[f"vote{nvote}_k{k}"] = run_variant(pre, g_vote, k=k, sigmas=ladder, nvote=nvote)[0]
        print(f"  scored vote{nvote} k={k}", flush=True)
    TB.evaluate("SHIPPED baseline", variants)
    return TB.evaluate(f"scale vote >={nvote} of {len(ladder)}, k swept", grid)


if __name__ == "__main__":
    print("CONTROLS"); assert TB.controls(), "harness controls failed"
    headline()
