"""Tuned detector constants, applied WITHOUT writing to the archived detector repo.

sem-crack-detector is archived, public and read-only, so a constant measured to be wrong
there cannot simply be corrected in place. It does not have to be: run_unified_pipeline
calls its stage functions by BARE NAME, which Python resolves through the module's globals
at call time, so rebinding `unified_pipeline.<name>` intercepts the call. detect_one.py
already relies on exactly this to suppress corrections (`up.load_correction_mask = ...`),
so this is the established route in this codebase, not a new trick.

Verified by ast in tests/test_detector_overrides.py: all four stage functions
(flatten_background, segment_dark_regions, clean_mask, compute_vesselness) are bare-name
calls inside run_unified_pipeline, and none is an attribute call, which would not be
interceptable.

EVERY constant here must carry the measurement that set it and the held-out score, because
a number tuned on the 26 hand-labelled tiles and then quoted against those same tiles is
fitted on itself. See analysis/tilebench.py for the instrument that enforces the split.
"""

# --- provenance ------------------------------------------------------------------------
# Measured 2026-10-11 on the 26 hand-labelled tiles (MAR_AmbB_AS excluded: 87% of its paint
# is round, i.e. porosity). Selection is leave-one-SPECIMEN-out over 13 specimens.
#
#   shipped (mad_k=5.0)        precision 0.3378  recall 0.3696  IoU 0.2143
#
# Decomposing every missed pixel by the stage that dropped it showed the loss is not the
# classifier: 45.7% of marked crack is never proposed as a candidate, against 16.3% lost at
# the classifier, so a perfect classifier caps at recall 0.5326. Marked-but-missed crack
# sits at a median robust z of -1.73 against a background median of +0.01 -- darker than
# background, nowhere near the 5-MAD bar the code demands.
# WHAT SHIPS: the region classifier is switched OFF. Nothing else is changed.
#
# Three independent searches converged on the same conclusion -- the shipped
# LogisticRegression over 8 region features is worse than not having it. On the 26 tiles,
# keeping every candidate region the classifier would have rejected:
#
#                            precision  recall     IoU      F1
#     shipped                   0.3378  0.3696  0.2143  0.3530
#     classifier deleted        0.4033  0.5326  0.2979  0.4590
#
# All four metrics rise, with ZERO free parameters, so there is nothing here to overfit:
# fitted and held-out are the same number by construction. Paired across the 13 specimens
# the median IoU gain is +0.1753 (11 of 13 better, 2 worse, Wilcoxon p = 0.0061). With the
# one pathological tile removed -- an off-specimen void that owns 82% of all false
# positives -- it is IoU 0.3550 -> 0.4812 and F1 0.5240 -> 0.6498 on the other 25.
# At the 2 px tolerance the literature reports, IoU 0.3423 and F1 0.5100.
#
# It also ends the dead zone. Three ETD specimens scored recall 0.0000 at EVERY candidate
# setting ever tried, which looked like the cracks being invisible to intensity. They were
# not invisible: the candidate stage proposed them and the classifier rejected all of them.
#     MAR_Amb_AS    recall 0.0000 -> 0.3792        MAR_Amb_HIP  recall 0.0000 -> 0.6827
#     MAR_Amb_Cast  recall 0.0000 -> 0.3537
#
# Confirmed on FULL frames, which is where this actually runs, against the hand-painted
# correction masks on 12 frames (1 = crack, 2 = not-crack, 0 = unreviewed and excluded
# from both, since 91% of the corpus is unreviewed and counting it as error would invent
# a precision collapse):
#     recall on hand-marked CRACK      0.6740 -> 0.6817   (+48,974 px)
#     rate on hand-marked NOT-crack    0.5987 -> 0.5987   (+0 px)
# Caveat on that second line: those 12 frames carry only 32,351 hand-verified not-crack
# pixels against 6,326,983 crack pixels, so it is weak evidence of no precision cost, not
# strong evidence of none. The tiles are the better precision evidence.
#
# Safe by construction, and checked rather than assumed: across the 26 tiles the number of
# pixels the shipped detector marks that this does NOT mark is exactly 0. It only ever
# keeps more regions, so it cannot delete a pixel a human marked.
#
# WHAT DELIBERATELY DOES NOT SHIP: any region-level precision rule.
#
# Two were found that score far better on the tiles -- a texture veto (keep a region only
# if it is at least as textured as its own frame's median, tiles IoU 0.4940) and a
# thickness excision (cut out blob bodies thicker than any crack, tiles IoU 0.3853). Both
# are disqualified. Measured against the hand-painted masks on the frames
# unified_pipeline.py names in its own source:
#     texture veto floor=1.0          deletes 43.46% of all hand-marked crack
#     thickness excision r_big=50     deletes 41.00%
#     thickness excision r_big=100    deletes 40.28%
# On 260708_316_H_b2_front_CBS_003 the texture veto removes 167,607 hand-marked pixels --
# the exact figure unified_pipeline.py cites for exclude_border_background(), the rule the
# repo already tried and removed for this reason. The tiles cannot see this because they
# are 512 px crops and a wide-open main crack does not fit in one; the repo's comment says
# it plainly ("the main crack is DARKER and SMOOTHER than the off-specimen background").
# Do not reintroduce a region-level rule here without re-running
# analysis/research/improve/voidkiller_safety.py against the paint.
#
# A THIRD rule has now died the same way, and it is the most important of the three
# because it did not look like a precision rule at all. The region classifier was
# RETRAINED on the 26 tiles with 24 extra geometry/context/raw-uint16 features and scores
# nested held-out tile IoU 0.5318 -- nearly double the 0.2979 that ships here. On the 48
# full frames that carry a hand-painted correction mask (70,041,625 marked crack px, vs
# the 10-12 frames and 6.3M px earlier runs used) it deletes, of the hand-marked crack
# this classifier-off path delivers:
#     retrained region classifier    deletes 72.67% of kept hand-marked crack
#     texture veto floor=1.0         deletes 67.54%   <- re-measured on the SAME 48 frames
#     thickness excision r_big=50    deletes 62.43%      through the SAME denominator, so
#     thickness excision r_big=100   deletes 54.62%      the four are comparable
# It is the worst of the four, and it is worse than the shipped classifier it was meant to
# replace: it removes 143,252 hand-marked NOT-crack px while deleting 12,518,382
# hand-marked crack px -- 87 px of real crack per px of false positive -- where the
# shipped classifier removes MORE not-crack (150,293 px) for 14x less crack damage.
# (The 43.46%/41.00%/40.28% figures above are four frames against "% of all painted" and
# are NOT comparable to these; one unit set and one denominator at a time.)
#
# The cause is structural, so no retraining fixes it. MeanWidth is the retrained model's
# top feature by permutation importance; over the tile training POSITIVES it spans
# 2.61-29.34 px, because a crack wider than that does not fit in a 512 px labelling crop.
# The regions holding painted crack on a full frame span MeanWidth 18-236 px and MaxWidth
# 42-654 px: disjoint support. 88.0% of every deleted crack pixel lies in a region wider
# than ANY training positive, and only 8 of 31 such regions are rejected -- so this is not
# even a learned width rule, it is unconstrained extrapolation into a corner of feature
# space the training set never visited, where the stakes are the whole main crack.
# Read at MATCHED mad_k with the one off-specimen void tile removed, its tile advantage at
# the shipped mad_k=5.0 is -0.0063 -- a REGRESSION -- and it loses 3.8% of tile true
# positives too. The pooled tile IoU reported that as a win because the precision it
# bought on one void region outweighed it.
# Bolting on production's force_keep_area=50000 cuts the deletion to 8.74%, still 28 of 48
# frames losing >1% of their kept crack, and the tiles cannot even evaluate it: 1 of 228
# tile regions reaches 50,000 px and it is the void, so on tiles a force-keep scores
# IoU 0.5318 -> 0.3324. The tile and full-frame rankings of one rule point opposite ways.
# Full record and the gate to re-run:
# analysis/research/improve/fullframe_lever4_safety.py, guarded by
# tests/test_region_rules_rejected.py.
USE_REGION_CLASSIFIER = False

# SECOND CHANGE: union the darkness cut across a ladder of flattening radii.
#
# flatten_background is a high-pass filter, so sigma=40 erases any feature wider than its
# own blur radius -- segment_dark_regions' docstring already says this about voids. The
# consequence is broader than voids: a crack is only reliably dark at the scales near its
# own width, and one radius sees one band. Taking the SAME cut at seven radii and unioning
# them costs nothing in parameters and recovers the bands sigma=40 cannot see.
#
# mad_k stays at the shipped 5.0 and the ladder is every scale, not a chosen subset, so
# this introduces NO new tuned constant. On the 26 tiles (held-out == fitted, 0 params):
#
#                            precision  recall     IoU      F1
#     v1.48 (single scale)      0.4033  0.5326  0.2979  0.4590
#     multi-scale union         0.4182  0.6252  0.3344  0.5012
#
# All four rise again. Excluding the one off-specimen void tile: IoU 0.4812 -> 0.5314,
# F1 0.6498 -> 0.6940. Driving THIS code (not a reference copy) over 12 full frames
# against the paint: recall on hand-marked crack 0.6697 -> 0.7911, +809,540 px, with the
# hand-marked not-crack rate 0.5987 -> 0.6077 and 0 hand-marked pixels deleted. Mean cost
# 7.1 s per full frame.
#
# It is a STRICT SUPERSET of the shipped mask, not merely "safe in testing": the union
# contains the sigma=40 term unchanged, so it cannot drop a pixel the old build kept. That
# is proved by construction and checked anyway -- 0 pixels lost across the 26 tiles and
# across 6,669,145 hand-painted pixels on 12 full frames.
#
# Rejected alternative, and the reason this is a union and not a vote: requiring a pixel to
# be dark at >= 3 of the 7 radii scores slightly better on the tiles (IoU 0.3394 vs 0.3334)
# but it is subtractive, and on full frames it deletes 0.65% of hand-marked crack -- up to
# 2.00% on a single frame -- while reaching LOWER full-frame recall (0.7114 vs 0.7962). The
# tile ranking and the full-frame ranking disagree, and the full frame is where this runs.
#
# Cost: seven flattening passes per image instead of one. The two largest radii dominate,
# because scipy truncates a gaussian at 4 sigma and so convolves with a ~2561 px kernel for
# sigma=320 -- that one scale was 36 s of a 64 s union on a 25 Mpx frame. But a background
# estimate has no detail finer than its own sigma by construction, so for sigma > 64 it is
# computed on a decimated copy and resampled back: 67.2 s -> 14.5 s per full frame. Checked
# rather than assumed -- across the 26 tiles the two masks differ by 347 px out of 6.8 M
# (0.005%), the fast path is still a strict superset of the stock mask, and the numbers
# quoted above are the FAST path's, which is what actually runs.
SCALE_LADDER = (5, 10, 20, 40, 80, 160, 320)
DECIMATE_ABOVE_SIGMA = 64
USE_MULTISCALE_UNION = True

OVERRIDES = {}      # stage-function constants; empty -- mad_k is NOT changed, see below.
# mad_k was measured to be badly set (relaxing 5.0 -> 2.5 lifts held-out recall 0.3696 ->
# 0.4460 with the classifier in place) but it is NOT shipped, because with the classifier
# switched off it stops paying: held-out IoU 0.3005 with mad_k free to move versus 0.3005
# pinned, and every variant that spends a free parameter here lands inside the noise of
# the zero-parameter arm. A tuned constant that buys nothing is pure overfitting risk.


def install(up, **extra):
    """Rebind the tuned stages on an imported `unified_pipeline` module.

    Call immediately after `import unified_pipeline as up` and before
    `up.run_unified_pipeline(...)`. Returns the names actually overridden, so a caller can
    log what it changed rather than assuming.
    """
    import numpy as np
    from scipy import ndimage as _ndi
    from skimage import exposure as _exp, filters
    import detect_cracks as dc

    def _flatten(img8, sigma):
        """flatten_background, with the background estimated on a decimated copy for the
        large radii where full resolution buys nothing but time."""
        if sigma <= DECIMATE_ABOVE_SIGMA:
            return dc.flatten_background(img8, sigma=sigma)
        f = max(1, int(round(sigma / 32.0)))
        small = _ndi.uniform_filter(img8.astype(np.float32), f)[::f, ::f]
        bg_s = _ndi.gaussian_filter(small, sigma / f, mode="nearest")
        bg = _ndi.zoom(bg_s, (img8.shape[0] / bg_s.shape[0], img8.shape[1] / bg_s.shape[1]),
                       order=1, mode="nearest")[:img8.shape[0], :img8.shape[1]]
        if bg.shape != img8.shape:                 # zoom can land a pixel short
            bg = np.pad(bg, ((0, img8.shape[0] - bg.shape[0]),
                             (0, img8.shape[1] - bg.shape[1])), mode="edge")
        flat = img8.astype(np.float32) - bg
        lo, hi = np.percentile(flat, [0.5, 99.5])
        if hi <= lo:
            lo, hi = flat.min(), flat.max()
        return _exp.rescale_intensity(flat, in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)

    applied = []
    params = {**OVERRIDES, **extra}
    base = dc.segment_dark_regions
    kw = {k: params[k] for k in ("mad_k", "absolute_dark_thresh") if k in params}
    mad_k = params.get("mad_k", 5.0)
    absolute = params.get("absolute_dark_thresh", 10)
    ladder = params.get("scale_ladder", SCALE_LADDER)
    multiscale = params.get("use_multiscale_union", USE_MULTISCALE_UNION)

    if multiscale:
        def segment_dark_regions(flat, img8=None, **call_kw):
            # img8 is required to re-flatten at other radii. unified_pipeline always passes
            # it; if some other caller does not, fall back to the stock single-scale cut
            # rather than silently returning something different from what was measured.
            if img8 is None:
                return base(flat, **{**call_kw, **kw})
            k = call_kw.get("mad_k", mad_k)
            absd = call_kw.get("absolute_dark_thresh", absolute)
            out = None
            for sigma in ladder:
                f = flat if sigma == 40 else _flatten(img8, sigma)
                sm = filters.gaussian(f, sigma=call_kw.get("denoise_sigma", 1.0),
                                      preserve_range=True)
                med = np.median(sm)
                mad = np.median(np.abs(sm - med)) * 1.4826
                cut = sm < min(filters.threshold_otsu(sm), med - k * mad)
                out = cut if out is None else (out | cut)
            return out | (img8 < absd)

        up.segment_dark_regions = segment_dark_regions
        applied.append(f"segment_dark_regions(multiscale union over {ladder}, mad_k={mad_k})")
    elif kw:
        def segment_dark_regions(flat, **call_kw):
            return base(flat, **{**call_kw, **kw})

        up.segment_dark_regions = segment_dark_regions
        applied.append(f"segment_dark_regions({', '.join(f'{k}={v}' for k, v in kw.items())})")
    return applied
