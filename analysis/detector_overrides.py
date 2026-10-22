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
# READ EVERY TILE NUMBER IN THIS FILE AS: POOLED OVER ALL PIXELS, ZERO TOLERANCE. That is
# the most pessimistic of five legitimate aggregations and none of the rows below said so.
# The arms are compared within that one aggregation, which is what makes the comparisons
# valid; what is NOT valid is lifting a single cell out as "the detector's precision". The
# shipped path's own figures in every aggregation are tilebench.SHIPPED_V1491 and
# docs/REPORTING_GUIDE.md §1.
#
#   v1.47 baseline (mad_k=5.0, classifier ON)
#                              precision 0.3378  recall 0.3696  IoU 0.2143
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
#     v1.47, classifier ON      0.3378  0.3696  0.2143  0.3530
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
# Second caveat, on BOTH lines: the 12 are the ALPHABETICALLY FIRST painted frames and come
# from two specimens. They are a paired before/after and nothing else -- the corpus
# full-frame recall over all 41 painted frames is 0.2983 pooled / 0.6464 per-frame median.
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
# It is the worst of the four, and it is worse than the v1.47 classifier it was meant to
# replace: it removes 143,252 hand-marked NOT-crack px while deleting 12,518,382
# hand-marked crack px -- 87 px of real crack per px of false positive -- where the
# v1.47 classifier removes MORE not-crack (150,293 px) for 14x less crack damage.
# (The 43.46%/41.00%/40.28% figures above are four frames against "% of all painted" and
# are NOT comparable to these; one unit set and one denominator at a time.)
#
# Re-measured against the v1.49 multi-scale candidate stage that ships now, rather than
# the v1.48 single-scale cut those figures used: 76.72% of kept, and the force-keep remedy
# degrades from 28 to 33 of 48 frames losing >1%. The union is a strict superset, so it
# hands the classifier more crack to reject and the verdict gets WORSE, not better.
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
# THE 0.7911 IS NOT THIS DETECTOR'S FULL-FRAME RECALL, and it was quoted as if it were.
# Those 12 frames are the ALPHABETICALLY FIRST 12 and come from two specimens. Over all 41
# painted frames the same quantity is 0.2983 pooled and 0.6464 per-frame median (p25 0.358,
# p75 0.808) -- five frames hold 57.9% of all painted crack and every one of them sits at
# 0.10-0.36, so the pooled figure is essentially those five. docs/REPORTING_GUIDE.md §2.
# The 0.6697 -> 0.7911 pair is a before/after on one subset through one instrument, which
# is the only thing it may be used for; neither end of it is a corpus figure.
#
# The four tile numbers above are POOLED OVER EVERY PIXEL at zero tolerance, which is the
# most pessimistic of five legitimate aggregations and was never stated. Same masks, same
# labels: median over the 26 tiles reads P 0.8056 R 0.7623 F1 0.5922 IoU 0.4208, and median
# over the 13 specimens at 2 px tolerance reads 0.8988 / 0.8025 / 0.6633 / 0.4962. A
# perfectly placed trace caps at IoU 0.4993 on these tiles, so 0.4208 is 84% of what these
# labels permit. The before/after above is read within one aggregation and is unaffected,
# but no single row of it may be lifted out as "the detector's precision" or "its recall".
# Reproduce: analysis/research/improve/aggregation.py.
#
# It is a STRICT SUPERSET of the shipped mask, not merely "safe in testing": the union
# contains the sigma=40 term unchanged, so it cannot drop a pixel the old build kept. That
# is proved by construction and checked anyway -- 0 pixels lost across the 26 tiles and
# across 6,669,145 hand-painted pixels on 12 full frames.
#
# Rejected alternative, and the reason this is a union and not a vote: requiring a pixel to
# be dark at >= 3 of the 7 radii scores slightly better on the tiles (IoU 0.3394 vs 0.3334)
# but it is subtractive, and on full frames it deletes 0.65% of hand-marked crack -- up to
# 2.00% on a single frame -- while reaching LOWER full-frame recall (0.7114 vs 0.7962, both
# on the same alphabetically-first 12 frames as above, so comparable to each other and to
# nothing else). The tile ranking and the full-frame ranking disagree, and the full frame
# is where this runs.
#
# Cost: seven flattening passes per image instead of one. The two largest radii dominate,
# because scipy truncates a gaussian at 4 sigma and so convolves with a ~2561 px kernel for
# sigma=320 -- that one scale was 36 s of a 64 s union on a 25 Mpx frame. But a background
# estimate has no detail finer than its own sigma by construction, so for sigma > 64 it is
# computed on a decimated copy and resampled back: 67.2 s -> 14.5 s per full frame. Checked
# rather than assumed -- across the 26 tiles the two masks differ by 347 px out of 6.8 M
# (0.005%), the fast path is still a strict superset of the stock mask, and the numbers
# quoted above are the FAST path's, which is what actually runs.
# A THIRD KNOB, MEASURED AND DELIBERATELY LEFT AT ITS SHIPPED VALUE.
#
# `absolute_dark_thresh` supplies HALF of all recall the detector has -- it proposes
# 13,907,547 of the 20,923,398 painted px that reach a candidate at frame scale, 10.5M of
# them reached by no ladder rung at all -- and it is an integer with no provenance here.
# Raising it is additive by construction (img8 < 20 contains img8 < 10), verified: 0 px
# lost at every threshold on every tile. So it cannot delete a human label, which is why
# it is exposed rather than buried.
#
# It is left at 10 because THREE instruments disagree and the two with real negative
# evidence both say no.
#
#   SEM FULL FRAMES, 41 frames / 70M painted px -- says YES, strongly.
#     recall on painted crack   0.2983 -> 0.4049 at t=20, 0.4338 at t=30
#     the 10->20 step adds 8,149,543 px of which 7,461,863 (91.6%) is inside paint,
#     for +1,916 px of painted not-crack.
#   TILES, 26 precise labels -- says NO.
#     P 0.4182 -> 0.3863, IoU 0.3344 -> 0.3177, F1 0.5012 -> 0.4823; area fraction
#     against the hand labels overshoots 0.951 -> 1.083 and length 1.095 -> 1.170.
#     Leave-one-specimen-out picks t=10 in 12 of 13 folds.
#   TXM, 31 frames, 11.3:1 refereed not-crack -- says NO, mildly.
#     recall 0.6707 -> 0.6929 but precision 0.2602 -> 0.2464, so F1 0.3750 -> 0.3635.
#
# The SEM frame "yes" is the weakest evidence despite being the largest: that paint has a
# median width of 192 px, so "inside painted crack" sweeps up whatever sits beside a crack.
# The tile "no" is also compromised -- the 26 crops contain only 33,673 of the 8,149,543
# pixels this moves (0.41%), and 56% of those sit in one porosity-heavy tile reading 0.5%
# purity. The TXM "no" rests on the only large body of certified not-crack in the project.
#
# What the shape test says, which is the part that is NOT about anybody's labels: the
# regions t=20 adds are indistinguishable from the ones already kept -- median elongation
# 2.57 against 2.69, 30.6% below elongation 2.0 against 29.4%, median area 78 against 89
# (painted crack elsewhere is 3.27, porosity 1.51). So the added material is NOT
# disproportionately pores; it is the same population the detector already accepts. That
# refutes the obvious objection and is why this is a judgement call rather than a closed
# one.
#
# To try it: install(up, absolute_dark_thresh=20). Expect area fraction to rise by roughly
# a seventh and crack counts with it; re-measure anything already reported.
# TWO VALUES, AND THEY ARE NOT THE SAME. OVERRIDES below is empty, so the running
# detector takes mad_k from segment_dark_regions' own default, which is 5.0. The paper
# evaluates at 6.0, where the reported crack area fraction agrees with the annotation to
# 1.3% on 31 public whole fields -- but that is 31 images of one alloy and the shipped
# default has NOT been changed on it.
#
# Both names exist because a figure generator that fell back to its own literal printed
# 5.0 while the manuscript had moved to 6.0, and the plate silently contradicted the text
# beside it. Anything that draws or documents either value reads it from here, so the two
# cannot drift apart again, and a reader of this file can see at a glance that the paper's
# setting is not the app's.
SHIPPED_MAD_K = 5.0        # what the application actually runs
PAPER_MAD_K = 6.0          # what the manuscript evaluates and reports

ABSOLUTE_DARK_THRESH = 10

SCALE_LADDER = (5, 10, 20, 40, 80, 160, 320)
DECIMATE_ABOVE_SIGMA = 64
USE_MULTISCALE_UNION = True

# WHERE THE REMAINING RECALL GOES, and why no third change ships.
#
# After the union above, the candidate stage still never proposes 70.13% of the hand-painted
# crack on the 48 frames that carry a correction mask. Every argument above is about the
# other 29.87%. Decomposed at FRAME scale for the first time -- the same quantity reads
# 45.7% on the 512 px tiles, so the tiles understate it by 24 points -- each missed pixel
# attributed to the FIRST step that dropped it and did not give it back (closing and
# fill_holes are extensive and can only add):
#
#     stage                                               px   % of painted  % of the loss
#     reaches a candidate                         20,923,398         29.87%              -
#     not dark at ANY ladder radius               47,165,748         67.34%         96.02%
#     dark, but component <= 13 px (clean_mask)    1,130,323          1.61%          2.30%
#     erased by clean_mask's opening, disk(1)        583,347          0.83%          1.19%
#     in the clean mask, component < 40 px           238,809          0.34%          0.49%
#
# The buckets are disjoint, exhaustive and asserted to sum to the painted crack on every
# frame. 29.87% reproduces the 29.84% measured by a separate instrument above; the residual
# is connectivity -- production labels candidates with measure.label(connectivity=2) while
# crackpipe.stages and fullframe_lever4_safety.py use ndi.label (4-conn), which fragments
# more and so drops more at min_area_px=40 (2,711,438 px vs 2,710,974 on one frame).
# So MORPHOLOGY AND THE AREA FILTERS ARE 4% OF THE PROBLEM; the darkness cut is all of it.
# Per specimen the coverage runs 14.15% (MAR_Amb_AS) to 100% (260622_316_H_b4, n=1), per
# frame 6.1% to 100%, and two frames hold 45.97% of the loss, so nothing here may be quoted
# pooled alone. The one place morphology does matter is Cast_24hr_SE_Side_006: 17.09% of its
# paint to the small-object filter plus 8.80% to the opening. The pooled 2.30%/1.19% is that
# frame and MAR_Amb_HIP_ETD_0003, not a property of the corpus.
#
# HALF OF ALL RECALL IS absolute_dark_thresh=10, an integer with no provenance here. It
# proposes 13,907,547 of the 20,923,398 painted crack px, 10,516,306 of them reached by no
# ladder rung at all; dropping the term deletes 47.50% of kept hand-marked crack. Raising it
# is additive by construction (the whole chain after the darkness cut preserves inclusion)
# and recovers a lot: img8<20 lifts painted-crack coverage 29.87% -> 40.51%, img8<30 ->
# 43.41%, and with mad_k 3.0 as well -> 53.31%, for 12.64% of the frame marked against
# 8.43%. It also behaves unlike relaxing mad_k: img8<20 adds 8.3 Mpx for only +196 regions
# (42,476 px each -- it WIDENS cracks already found, and 89.5% of what it adds is inside
# hand-painted crack), where mad_k 3.0 adds +53,223 regions at 445 px each with 34.3% of its
# area painted, which is the pore/speck signature this stage's docstring names.
#
# IT STILL DOES NOT SHIP, because nothing here can price it and two instruments disagree.
#   * The paint cannot: 258,352 px of hand-marked NOT-crack and 170,922 of ERASE against
#     70,041,625 of crack, and they are ALREADY 85.5%/96.7% proposed at the shipped setting.
#     There is no headroom in which a precision cost could appear.
#   * The 26 tiles can, and they say no. Through analysis/research/tilebench.py with the
#     classifier off, leave-one-specimen-out over the grid picks t=10 in 13 of 13 folds:
#     IoU 0.3246 at t=10, 0.3056 at 20, 0.2622 at 30, 0.1603 at 50. Going to 20 buys +1,227
#     true px and costs +27,473 false px -- 22.4 px of false positive per px of real crack,
#     the mirror of the 87-to-1 that killed the retrained classifier. Identical without the
#     off-specimen void tile, so it is not that tile.
#   * But a BUDGET-MATCHED RANDOM CONTROL says the tile verdict is not "it is noise": at the
#     2.97% tile prevalence the null fp/tp is 81.6, so the measured 22.4 is a 3.53x
#     enrichment over chance. The added area is real signal whose MARGINAL precision (4.3%)
#     sits far below the stage's running 41%, which is why every IoU-like metric falls.
#   * And the two instruments are blind in opposite directions. img8<20 raises the tile
#     region count 14.6% at 700 px per new region and the frame count 0.4% at 42,476 px per
#     new region -- 60x. The tiles are 6.8 Mpx of 811 Mpx, actively selected, and 3x less
#     painted than the corpus (2.97% vs 8.6%): they hold the pores the threshold also
#     catches and not the wide-open cracks it widens. The frames hold the cracks but score
#     them against paint 192 px wide at the median. Neither can say whether the added dark
#     pixels are crack. What would settle it is certified NOT-crack at frame scale on
#     MAR_Amb_AS_CBS_0003, MAR_Amb_AS_ETD_0003 and Cast_24hr_SE_Side_006, which hold 29% of
#     the loss and are exactly where the two instruments disagree -- the same labelling gap
#     the region-classifier rejection above reached from the other side.
#
# A THIRD CORPSE, and it was the most promising-looking of the three. flatten_background
# rescales the residual onto 0-255 by its 0.5/99.5 percentiles, which pins the flattened
# image's MAD at 24-43 grey levels with a median near 130 -- so `med - 5*mad` lands NEGATIVE
# and the rung proposes nothing at all. That is not a rounding curiosity: 56 of 336
# frame-rungs (16.7%) are dead this way, 17 of 48 frames have at least one and they hold
# 45.49% of the entire loss, MAR_Amb_Cast_ETD_0004 has all seven dead and reaches 6.1% of
# its paint. The cut is affine-invariant in exact arithmetic, so the remedy looked free:
# same cut, same mad_k, same ladder, on the UNCLIPPED float residual, from a background
# asserted bit-identical to _flatten's. It is worth +0.14 points (29.87% -> 30.01% as a
# union) and in raw form it is not even a superset -- it deletes 444,839 px of hand-painted
# crack, caught by the instrument's own additivity guard. On k_max the two representations
# agree to within 0.4 points at every threshold. THE NEGATIVE BAR IS A SYMPTOM, NOT A CAUSE:
# at those radii the residual genuinely has no 5-MAD outliers, because flattening at a
# radius larger than the feature removes the feature -- exactly what segment_dark_regions'
# docstring already says about voids. Do not re-propose it.
#
# AND THE BOUND THE 70.13% CANNOT BE READ WITHOUT. The paint asserts "there is crack in this
# region", not "this pixel is crack": from its own distance transform, 2*EDT inside the
# paint is p50 = 192 px over all 70M painted crack px (467.6 px on MAR_Amb_AS_CBS_0003,
# where the paint covers 50.8% of the frame), so half of all painted crack pixels are more
# than 96 px from the nearest unpainted pixel. Measured on img8 -- the only quantity that is
# not blinded here, because the flattened robust z puts the never-proposed paint
# indistinguishable from matrix (p25/p50 -0.75/+0.00 vs -0.75/+0.00) for the structural
# reason that a crack wider than the blur radius lands near neutral, "~122 out of 255" by
# the docstring's own measurement -- a one-sided mixture bound needing no crack-like
# reference puts AT LEAST 19.72% of the never-proposed paint darker than matrix can account
# for, so AT MOST about 80% of the 70.13% is paint lying over genuine matrix. That bound
# first read 88.16% because it was maximised over the threshold, where the denominator goes
# to zero; its own control (distant matrix measured against near matrix, which must read ~0)
# read 96.22% and caught it. At fixed, decision-relevant thresholds both matrix controls
# read exactly 0.00%.
#
# Full record: analysis/research/improve/fullframe_recall_decomposition.py,
# fullframe_recall_recovery.py and absdark_tiles.py, with their report_*.py.
# Guard: tests/test_candidate_recall_decomposition.py.

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
    absolute = params.get("absolute_dark_thresh", ABSOLUTE_DARK_THRESH)
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
