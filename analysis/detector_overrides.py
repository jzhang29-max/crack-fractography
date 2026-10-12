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
# analysis/improve/voidkiller_safety.py against the paint.
USE_REGION_CLASSIFIER = False

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
    import detect_cracks as dc
    applied = []
    params = {**OVERRIDES, **extra}
    if "mad_k" in params or "absolute_dark_thresh" in params:
        base = dc.segment_dark_regions
        kw = {k: params[k] for k in ("mad_k", "absolute_dark_thresh") if k in params}

        def segment_dark_regions(flat, **call_kw):
            return base(flat, **{**call_kw, **kw})

        up.segment_dark_regions = segment_dark_regions
        applied.append(f"segment_dark_regions({', '.join(f'{k}={v}' for k, v in kw.items())})")
    return applied
