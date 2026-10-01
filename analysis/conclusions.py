#!/usr/bin/env python3
"""Turn measured numbers into the short sentences a researcher would actually write.

WHAT THIS IS NOT. It is not a classifier and it invents no thresholds. Every statement below
is either (a) a restatement of a measured quantity with its unit and its caveat, or (b) a
refusal. Where the literature supplies a number it is cited; where it does not, the rule is
relative or the statement is not made. This is fitness for purpose, not a contribution --
thresholded restatement of stereological measurements is standard in commercial image
analysis packages.

WHAT SURVIVED, AND WHY SO LITTLE. An adversarial review tested the obvious list against
this corpus's measured limits and most of it failed, because it turned out to be a statement
about the instrument rather than the material. On the 56 fields imaged through both CBS and
ETD, the paired median ratio is:

    largest_share_of_area   0.870  (p = 0.084, not significant)  <- POOLED. SEE BELOW.
    n_cracks_measured       1.226  (p = 4.2e-4)
    area_fraction           2.286  (p = 8.1e-9)
    n_junctions             3.071  (p = 2.1e-6)                  <- rejected outright

AND THE ONE THAT "SURVIVED" DID NOT. Those 56 pairs span three scale strata -- 36 fields at
51.883 nm/px, 16 whose nm/px was never recovered, and 4 at the 337.2396 overview -- which is
the pooling this app refuses in every other aggregate it computes. Restricted to the modal
magnification the share MOVES: median 0.790, CBS lower on 29 of 36 fields, Wilcoxon on log
ratios p = 3.1e-4. The excluded strata run the other way (1.08 and 1.11) and that is what
dragged the pooled figure to 0.870 and its p to 0.084. So no metric tested here is
detector-invariant; the appearance of one was an artefact of mixing scales.

So junction density cannot carry a conclusion here: it moves threefold depending on which
detector looked at the same piece of metal. Tortuosity and R_L were rejected for a
different reason and are no longer computed at all (REFUSALS below, and segments.py):
R_L's corpus median WAS exactly 1.4142 = sec(45 deg), which is the isotropy null, a
lattice diagonal and a straight 45-degree crack at once. Width-length
scaling is rejected as algebra: MeanWidth is defined as Area/Length, so its slope is the
area slope minus one.

EVERY STATEMENT CARRIES ITS OWN SUPPRESSION RULE, and the rules do most of the work here.
A statement with no condition under which it must stay silent is not ready to ship.
"""

#: The one cut point this module uses that no standard supplies. Labelled as the app's own
#: wherever it is shown, and the underlying value is always printed beside the verdict so a
#: reader can apply their own.
DOMINANT_CUT = 0.90

#: Detector-discordance rate for the regime call, RECOMPUTED from the dataset rather than
#: quoted: the call flips between CBS and ETD on 4 of the 56 double-imaged fields at this
#: cut point -- 4/56 on the gated arm and 4/56 on machine, 7.1% either way.
#:
#: It shipped as 0.18, which would need 10 of 56. That number came from a research summary
#: and I put it in a constant without recomputing it against analysis/out/frames.json, and
#: it then appeared in the "when it lies" hedge under every dominance verdict in the app.
#: tests/test_conclusions.py recomputes it from the dataset so it cannot drift again.
REGIME_DISCORDANCE = 4 / 56

#: ASTM E562's usual relative-accuracy target. Below it the answer is more fields.
E562_RA_TARGET = 10.0

#: Buffon/skeleton P21 disagreement beyond which skeleton length is not a measurement. No
#: literature threshold exists for this; 1.5x is the app's own and is labelled as such. The
#: TXM median is 0.466, i.e. a 2.1x overestimate, which is self-disqualifying either way.
LENGTH_TRUST_RATIO = 1.5

#: WHY THIS APP STATES NO WIDTH RESULT UNDER THE DETECTOR SWAP, in numbers, on the 36
#: paired fields at 51.883 nm/px. Three instruments, none of which can answer the question:
#:
#:   "naive"        per-field area-weighted mean of a per-region calibre, median over pairs.
#:                  Reads 1.26x and 1.67x -- which LOOKS like the opposite sign to
#:                  area/length's 0.92x, and shipped briefly as exactly that argument.
#:   "size_matched" the same comparison inside 20 equal-count region-area bins, geometric
#:                  mean over bins. Both collapse to unity.
#:
#: The naive figures are SIZE, not width. Both instruments are strongly monotone in region
#: area -- log-log slope 0.426 (r 0.952) for the distance transform, which is a maximum, and
#: 0.561 (r 0.950) for the ellipse minor axis, which is a second moment -- so area-weighting
#: them on a detector that marks bigger regions manufactures a ratio. Measured: size-matched
#: strata put both at unity, and a size-only null (each CBS region handed the calibre an ETD
#: region of the same area had, knowing nothing about width) OVERSHOOTS the distance
#: transform, 1.53x null against 1.26x observed.
#:
#: THE TWO INSTRUMENTS ARE NOT EQUALLY ACCOUNTED FOR, and flattening them into one verdict
#: would overstate the case. That same null lands 1.54x against the ellipse's 1.67x
#: observed, i.e. slightly UNDER -- so size alone does not fully explain the ellipse, and
#: for it the decisive facts are the size-matched unity and the near-unity unweighted
#: median rather than the null. Neither instrument supports a width claim; they fail to
#: support it for partly different reasons. The unweighted median over regions is
#: already 1.02x and 1.08x, so the area weighting was doing all of the work, and pooling
#: regions across pairs inverts both below 1 (0.84x, 0.96x). An instrument whose answer
#: moves 0.84x -> 1.67x with the weighting choice is not measuring width.
#:
#: So: area/length is log(area)-log(length) by construction, and the two non-area/length
#: instruments are size proxies. NO instrument in this dataset can referee a width change
#: here, in either direction, and the statement below asserts none. Stored rather than
#: computed live because for_arm() is handed frames.json only and the region table is 40 MB;
#: tests/test_conclusions.py recomputes all four from analysis/out/cracks.json, and fails if
#: the size-matched pair stops straddling unity or the naive pair stops being confounded.
DETECTOR_CALIBRE_RATIOS = {
    "naive": {"max_inscribed_width": 1.26, "ellipse_minor_axis": 1.67},
    "size_matched": {"max_inscribed_width": 0.97, "ellipse_minor_axis": 1.02},
}


def _s(text, basis, hedge=None, level="info", value=None):
    """One read-out line. `text` is what appears on screen and is capped at 15 words."""
    words = len(text.split())
    assert words <= 15, f"on-screen text is {words} words, cap is 15: {text!r}"
    return {"text": text, "basis": basis, "hedge": hedge, "level": level, "value": value}


# ---------------------------------------------------------------------------------------
# Frame-level read-out.
def for_frame(f):
    """Read-out for one frame. Returns a list of statements, possibly empty."""
    out = []
    arm = f.get("arm", "")
    scaled = bool(f.get("scale_known"))
    n = f.get("n_cracks_measured") or 0

    if n == 0:
        return [_s("No crack pixels in this frame.",
                   "n_cracks_measured = 0", level="warn")]

    # THE INGEST ASSERTION, FIRST AND LOUDEST. measure.py detects an inverted mask, a
    # greyscale image posing as one, and an all-crack frame, and the old layout showed those
    # warnings under the frame title. That element is gone, so the warnings had NO CONSUMER:
    # an inverted mask measured the matrix, reported it as crack, and the read-out said
    # "One crack holds 100% of the crack area" in green. A warning with no reader is not a
    # warning. Level "bad" so the severity sort puts it above every other statement.
    for w in ((f.get("ingest") or {}).get("warnings") or []):
        if "inverted" in w:
            out.append(_s(
                "This mask looks inverted: it may be measuring the matrix.",
                w, hedge="Crack should be BLACK and the minority phase. An inverted mask "
                         "produces entirely plausible numbers about the wrong phase.",
                level="bad"))
        elif "two-valued" in w:
            out.append(_s(
                "Not a two-valued mask: it was thresholded at 128.",
                w, hedge="Every area statistic here depends on that threshold rather than "
                         "on a segmentation decision anyone made.",
                level="bad"))
        else:
            out.append(_s(w if len(w.split()) <= 15 else "Ingest check failed on this mask.",
                          w, level="bad"))

    # --- REGIME. NOT detector-invariant; see the module docstring. --------------------
    share = f.get("largest_share_of_area")
    if share is not None:
        if share >= DOMINANT_CUT:
            out.append(_s(
                f"One crack holds {100 * share:.0f}% of the crack area.",
                "largest_share_of_area. This used to be introduced as the one metric the "
                "CBS/ETD detector does not move, on a paired ratio of 0.870 at p = 0.084 -- "
                "which pooled 36 fields at 51.883 nm/px with 16 of unrecovered scale and 4 "
                "at the 337.2396 overview. At the modal magnification alone the share DOES "
                "move: 0.790, CBS lower on 29 of 36, p = 3.1e-4. What can honestly be said "
                "about THIS verdict is narrower: no field at 51.883 nm/px reaches the cut "
                "at all (the highest is 0.800), and on the 7 double-imaged fields that do "
                "reach it -- every one unscaled or at the overview scale -- the ratio is "
                "1.05 at p = 0.30, which at n = 7 is a statement about power and not about "
                "invariance.",
                hedge=f"Per-field, not per-specimen, and confounded with field size "
                      f"(Spearman +0.49 with nm/px: coarser pixels merge separate cracks "
                      f"into one). The {DOMINANT_CUT:.0%} cut is this app's, not a "
                      f"standard's, and the call flips between detectors on "
                      f"{REGIME_DISCORDANCE:.0%} of double-imaged fields.",
                level="good", value=share))
        else:
            out.append(_s(
                f"Distributed: largest crack is {100 * share:.0f}% of the area.",
                "largest_share_of_area", hedge="Per-field. See the size distribution.",
                value=share))

    # --- ORIENTATION, only against its own null. --------------------------------------
    beats = f.get("rose_beats_null")
    R, Rnull, th = f.get("rose_R"), f.get("rose_R_null"), f.get("rose_theta_deg")
    if beats is True and th is not None:
        out.append(_s(
            f"Oriented near {th:.0f}° to image x.",
            f"length-weighted axial resultant R = {R:.3f} against its own permutation "
            f"null Rnull = {Rnull:.3f} (1000 draws, uniform directions, observed segment "
            f"lengths). Construct: ASTM E1268-19 line-intercept anisotropy; axial "
            f"statistics per Mardia & Jupp.",
            hedge="Direction to no better than ±10°, and relative to IMAGE x -- "
                  "the mapping to a build or loading axis is not in the data and must be "
                  "declared.",
            level="good", value=th))
    elif beats is False:
        out.append(_s(
            "Not resolvably oriented.",
            f"R = {R:.3f} does not exceed its permutation null Rnull = {Rnull:.3f}. The null "
            f"is computed for THIS frame from its own segment lengths, which is why it is "
            f"quoted beside the value: across this corpus it runs 0.04 to 1.00, median "
            f"0.14, because it scales with how many segments there are. A fixed threshold "
            f"would call 12 frames strongly oriented that do not beat their own null.",
            level="warn", value=R))

    # --- LENGTH TRUST. Two estimators of one quantity disagreeing is self-disqualifying.
    # Prefer the pixel-unit pair: the ratio is dimensionless and identical either way, and
    # the pixel pair exists on every frame while the millimetre pair needs a scale. The
    # millimetre values stay as the fallback so a frame measured before this change still
    # produces the statement.
    pr = f.get("probe") or {}
    sk = f.get("p21_skeleton_per_px")
    bf = pr.get("p21_buffon_per_px")
    unit = "px/px\u00b2"
    if not (sk and bf):
        sk, bf = f.get("p21_skeleton_mm_per_mm2"), pr.get("p21_buffon_mm_per_mm2")
        unit = "mm/mm\u00b2"
    if sk and bf and sk > 0:
        ratio = bf / sk
        if ratio and (ratio < 1 / LENGTH_TRUST_RATIO or ratio > LENGTH_TRUST_RATIO):
            out.append(_s(
                f"Length unreliable: two estimators differ {max(ratio, 1 / ratio):.1f}×.",
                f"skeleton P21 = {sk:.3g} against Buffon (π/2)·mean(P_L) = "
                f"{bf:.3g} {unit} -- two estimators of the same centreline length per "
                f"unit area, the second skeleton-free. Underwood, Quantitative Stereology.",
                hedge="Treat length, MCL, TCL and characteristic length on this frame as "
                      "skeletonisation artefact rather than measurement. No literature "
                      "threshold exists for acceptable disagreement; 1.5× is this "
                      "app's own.",
                level="bad", value=ratio))

    # --- IS THE LONGEST CRACK A CRACK, OR A NETWORK? ----------------------------------
    #
    # mcl_um used to be max(SkeletonLength_px) over regions, which is the TOTAL centreline
    # of a whole branched network and was labelled "Longest crack". It is now the longest
    # tip-to-tip geodesic, and the share of its own network that path represents is the
    # thing that reading was missing: 1.0 means the region is a single unbranched crack,
    # 0.2 means the longest route through it is a fifth of the centreline present.
    share = f.get("mcl_share_of_its_network")
    if share is not None and f.get("mcl_um"):
        if share >= 0.95:
            out.append(_s(
                "Longest crack is the whole of its region.",
                f"tip-to-tip geodesic is {100 * share:.0f}% of that region's total "
                f"centreline length, so the region is one unbranched crack rather than a "
                f"network.",
                value=share))
        else:
            out.append(_s(
                f"Longest crack is {100 * share:.0f}% of its network.",
                f"the longest tip-to-tip geodesic against the total centreline of the same "
                f"region. The remainder is other branches of the same connected network, "
                f"which a single length cannot represent.",
                hedge=("That region's skeleton loops, so the tip-to-tip route is the "
                       "shorter way round and sits below the longest simple path through "
                       "it." if f.get("mcl_has_cycles") else None),
                level="warn", value=share))

    # --- CENSORING, weighted by what it bears on. -------------------------------------
    cl = f.get("censored_share_by_length")
    if cl is not None and cl >= 0.25:
        mcl, unc = f.get("mcl_um"), f.get("mcl_um_uncensored_only")
        out.append(_s(
            f"{100 * cl:.0f}% of length touches an edge: MCL is a bound.",
            f"length-weighted censored share. The count share is "
            f"{100 * (f.get('censored_share') or 0):.1f}%, which understates this several "
            f"times over and is why the weighting is named.",
            hedge=(f"MCL {mcl:.0f} µm with censored regions, {unc:.0f} µm "
                   f"without -- the pair brackets, neither is the value."
                   if (mcl and unc) else
                   "Report MCL as the bracket the frame card shows, never as one number."),
            level="warn", value=cl))

    # --- NO SCALE. Not a caveat, a limit on what exists. ------------------------------
    if not scaled:
        out.append(_s(
            "No scale: micrometre values withheld, not defaulted.",
            "nm_per_px is unknown for this frame, and the SEM corpus spans a 249× "
            "magnification range, so there is no defensible default.",
            level="warn"))

    # --- TXM SPECIFIC. Whole-arm caveat stated once. ----------------------------------
    if arm == "txm":
        out.append(_s(
            "TXM cracks are ~3 px wide; path geometry is mostly artefact.",
            "the TXM skeleton overestimates length by ~2.1× against the Buffon "
            "estimator (median ratio 0.466 over 63 frames), consistent with cracks only a "
            "few pixels across.",
            level="warn"))
    return out


def _mag_clause(ci):
    """" at X nm/px, excluding N field(s) at a different scale" -- or nothing at all."""
    n = (ci or {}).get("n_fields_off_determination") or 0
    if not n:
        return ""
    return (f" at {ci.get('nm_per_px')} nm/px, excluding {n} field"
            f"{'' if n == 1 else 's'} acquired at a coarser pixel, whose minimum "
            f"resolvable crack width is different")


# ---------------------------------------------------------------------------------------
# Specimen-level read-out.
def for_specimen(r, frames=None):
    """Read-out for one specimen-arm record, optionally with its frames for field tallies."""
    out = []
    ci = r.get("area_fraction_ci")
    grad = r.get("stage_gradient")
    # When the fields form a spatial trend, "measure more fields" is the WRONG advice: more
    # tiles in the same patch cannot narrow an interval that is tracking a gradient, so the
    # remedy clause is suppressed whenever the gradient statement fires.
    grad_fires = bool(grad and grad.get("significant"))

    if ci:
        ra = ci.get("pct_relative_accuracy")
        if ra is not None and ra > E562_RA_TARGET:
            out.append(_s(
                # NOT "too coarse to rank this specimen". Relative accuracy is a
                # within-patch precision statistic with no between-specimen term, so it
                # cannot speak to ranking either way, and gating that word on ra > 10
                # taught the reader that a narrower interval buys a comparison. It does
                # not: see the ranking refusal below, which is unconditional on width.
                f"±{ra:.0f}%: wider than E562's ±{E562_RA_TARGET:.0f}% precision target.",
                f"ASTM E562-19e1 95% CI from between-field variance over {ci['n_fields']} "
                # WHICH fields, when the specimen holds more than the interval used. E562
                # fixes the magnification before the fields are counted, so an overview at
                # a coarser pixel is not a replicate of the fine fields; saying "over 9
                # fields" on a 10-field specimen without saying why reads as a miscount.
                f"fields{_mag_clause(ci)}. E562's usual target is "
                f"±{E562_RA_TARGET:.0f}%, and nothing in this arm reaches it.",
                # "0 of 22" pooled all four arms, which is the one thing this app refuses
                # to do anywhere else: the arms are different instruments, or different
                # definitions of the object. Per arm the count is 0 of 9.
                hedge=("This is a sampling interval for this specimen's surface, not a "
                       "confidence interval for the material."
                       if grad_fires else
                       "The remedy is more fields, not more decimal places. This is a "
                       "sampling interval for this specimen's surface, not a confidence "
                       "interval for the material."),
                level="bad", value=ra))
        if ci.get("ci95_lo_clamped"):
            out.append(_s(
                "Interval reaches below zero: no lower bound.",
                "the normal-theory interval reaches negative area fraction, which cannot "
                "occur, so it is clamped for display only.",
                level="warn"))
    elif r.get("no_ci_reason"):
        out.append(_s(
            "Uploads are not one specimen: no interval over them.",
            r["no_ci_reason"] + ". Each uploaded image is measured on its own; the numbers "
            "on a single frame are unaffected.",
            level="warn"))
    elif r.get("n_fields", 0) < 3:
        out.append(_s(
            f"Only {r.get('n_fields', 0)} field(s): no interval.",
            "ASTM E562 needs enough fields for the between-field variance to mean "
            "something; below three the interval is unstable enough to mislead.",
            level="warn"))

    # --- RANKING. The comparison table puts these specimens in one list, so the question
    # "which is worse" is asked by the layout whether or not any sentence invites it.
    #
    # It is not answerable here and no amount of measuring makes it so, which is why this
    # is unconditional on the interval's width and on the interval existing at all. Each
    # specimen was imaged at ONE site, so the between-field and the between-specimen
    # variance are the same component and nothing in the data separates them. It fires on
    # 33 of 34 records -- every specimen-arm except uploads, including the eleven thin
    # ones that carry no interval and were, until this release, silently ordered by their
    # bare median. n_patches >= 2 switches it off with no code edit; nothing reaches that
    # today. NO DIGIT AND NO UNIT below the headline: the basis and hedge render outside
    # the fifteen-word assert, and a refusal to compare that ships two numbers beside
    # itself hands the reader the comparison back.
    from specimen_stats import PSEUDO_SPECIMEN  # local, as everywhere else in this file
    if (r.get("specimen") != PSEUDO_SPECIMEN
            and (ci is not None or r.get("area_fraction_median") is not None)
            and (r.get("n_patches") is None or r["n_patches"] < 2)):
        out.append(_s(
            "Ranking specimens is not supported by this sampling design.",
            "each specimen here was imaged at a single site, so the scatter between its "
            "fields and the difference between specimens are the same variance "
            "component, and no test on these data can separate them -- spatial "
            "pseudoreplication in Hurlbert's sense.",
            hedge="A second imaged site on a specimen would make the question "
                  "answerable. Until then a narrower interval buys precision on the one "
                  "site, not a comparison with any other specimen.",
            level="warn"))

    # --- SPATIAL GRADIENT. Are these fields a sample, or a raster across one patch? ---
    if grad_fires:
        rr = grad.get("field_max_min_ratio")
        out.append(_s(
            (f"Cracking varies {rr:.0f}× across this patch; fields are not independent."
             if rr else
             "Cracking trends across this patch; fields are not independent."),
            f"Spearman rho = {grad['spearman_rho']:+.3f}, p = {grad['p_value']:.5f} against "
            # NO ROW COUNT. It used to say "in 9 stage rows" for a 3x3 raster: rows are
            # grouped on the raw coordinate and the nine fields differ in the sixth
            # decimal, so each was its own row. The headline is unaffected -- max field
            # over min field IS a spread across the patch, and it never claimed rows.
            f"{grad['axis'].replace('_', ' ')} over {grad['n_frames_with_position']} "
            f"fields. {grad['note']}",
            hedge="The interval above is then describing a spatial trend rather than "
                  "sampling error, so more tiles in the SAME patch will not narrow it. "
                  "Stage units are the instrument's and are not asserted to be "
                  "millimetres, so the patch extent is not quoted.",
            level="bad", value=grad["spearman_rho"]))

    # --- DETECTOR. Confounded with specimen, so it is never a footnote. ---------------
    ds = r.get("detector_sensitivity")
    if ds is None or not ds.get("cbs_over_etd_median"):
        # A BLANK READS AS "NO DETECTOR EFFECT", which is a control that reads nothing. 28
        # of 34 specimen-arms have no field imaged both ways, so silence here would be both
        # the common case and the wrong inference.
        out.append(_s(
            "Detector effect unmeasured here.",
            "the CBS/ETD comparison needs the same physical field through both detectors. "
            "Where it exists corpus-wide the median is 2.29×, so an unmeasured effect is "
            "not a small one.",
            level="warn"))
    else:
        ratio = ds["cbs_over_etd_median"]
        if abs(ratio - 1) > 0.2:
            out.append(_s(
                f"Detector alone moves this {ratio:.1f}×.",
                f"CBS against ETD on {ds['n_fields_both_detectors']} fields imaged both "
                f"ways. Corpus-wide the median is 2.29×, CBS higher in 50 of 56, "
                f"paired Wilcoxon p = 8e-9.",
                hedge="Detector is confounded with specimen here -- four specimens are "
                      "CBS-only. Part of any difference between two specimens is which "
                      "detector looked at them.",
                level="bad", value=ratio))

    # --- OPERATOR CORRECTIONS. Whether a human touched this at all. -------------------
    a = r.get("arm_sensitivity")
    if a:
        if not a.get("n_frames_corrected"):
            out.append(_s(
                "Unreviewed: detector output, no operator corrections.",
                f"the gated and machine arms are identical on all "
                f"{a['n_paired_frames']} frames of this specimen.",
                level="warn"))
        else:
            out.append(_s(
                f"Corrections change area {a['gated_over_machine_where_corrected']}× "
                f"on {a['n_frames_corrected']} frames.",
                f"gated against machine on identical frames, "
                f"{a['n_frames_corrected']} of {a['n_paired_frames']} carrying a stroke.",
                value=a["gated_over_machine_where_corrected"]))

    # --- REGIME, as a tally over fields rather than a median. -------------------------
    #
    # COLLAPSED TO FIELDS FIRST. Counting the frames handed in and calling them fields said
    # "0 of 20 fields" for a specimen with 10 fields -- the same error as the figure's n,
    # made an hour after fixing it, in the code written to replace it. Routed through
    # specimen_stats.field_key so there is one definition of a field in the whole app.
    if frames:
        try:
            from specimen_stats import collapse_to_fields
            vals = collapse_to_fields(frames, "largest_share_of_area")
        except ImportError:
            vals = [f.get("largest_share_of_area") for f in frames
                    if f.get("largest_share_of_area") is not None]
        if vals:
            dom = sum(1 for v in vals if v >= DOMINANT_CUT)
            out.append(_s(
                f"{dom} of {len(vals)} fields are single-crack dominated.",
                f"largest_share_of_area at or above {DOMINANT_CUT:.0%}. Reported as a tally "
                f"because specimen explains only 37% of the variance (eta² = 0.370) -- "
                f"one specimen spans 0.050 to 0.965 across its own fields, so a median "
                f"would invent a specimen-level regime that does not exist.",
                hedge=f"The {DOMINANT_CUT:.0%} cut is this app's, not a standard's.",
                value=dom / len(vals)))
    return out


# ---------------------------------------------------------------------------------------
# What this app will not conclude, and what would change that.
#
# Stated in the UI rather than silently omitted. The transgranular/intergranular question
# recurs precisely because nothing on screen addresses it, and a decline that names the
# image to acquire is worth more than a label with no evidence behind it.
# ---------------------------------------------------------------------------------------
# ARM-LEVEL READ-OUT: what the whole comparison supports, as opposed to one specimen.
#
# WHY THIS EXISTS. The Compare tab showed fourteen specimens by seven columns and left the
# reading entirely to the reader -- ingredients, no conclusion -- while hiding 540 words of
# explanation in 43 hover tooltips over a pane showing 126. The numbers that actually
# characterise a corpus are not in any single row: how many specimens reach the precision
# target, how far the detector moves the answer, how much of the corpus has no scale at
# all. Each of those is computed here from the same records the table renders.
#
# EVERY ONE IS COMPUTED, none is a constant. An earlier version of this file shipped a
# regime figure copied out of a research summary without recomputing it, and it was wrong
# by a factor of two and a half. So each statement below derives its own numbers from the
# records passed in, and each says how many records it is speaking for.
#
# AND NONE OF THEM RANKS. One imaged site per specimen makes the between-field and the
# between-specimen variance the same component, so the ordering question the table's shape
# invites is refused here, once, where the table is.
def _partition_for_conclusions(frames):
    """The modal-magnification group, or everything if the partition is unavailable."""
    try:
        from specimen_stats import _partition_by_magnification
        g = _partition_by_magnification(frames)
        return g[0][1] if g else frames
    except Exception:
        return frames


def for_arm(records, frames=None):
    """Read-out for one arm's whole set of specimen records."""
    import statistics as _st

    out = []
    recs = list(records or [])
    frames = list(frames or [])
    if not recs:
        return out

    # --- PRECISION, over the specimens that have an interval at all -------------------
    with_ci = [r for r in recs if r.get("area_fraction_ci")
               and r["area_fraction_ci"].get("pct_relative_accuracy") is not None]
    if with_ci:
        ras = sorted(r["area_fraction_ci"]["pct_relative_accuracy"] for r in with_ci)
        meet = [x for x in ras if x <= E562_RA_TARGET]
        out.append(_s(
            f"{len(meet)} of {len(with_ci)} specimens reach E562's "
            f"±{E562_RA_TARGET:.0f}% precision target.",
            f"ASTM E562-19e1 95% CI from between-field variance, per specimen, over the "
            f"fields of one magnification. Relative accuracy runs ±{ras[0]:.1f}% to "
            f"±{ras[-1]:.1f}%, median ±{_st.median(ras):.1f}%. The other "
            f"{len(recs) - len(with_ci)} specimen-arm(s) here have no interval at all.",
            hedge="Relative accuracy is precision within one imaged site. Reaching the "
                  "target would not make two specimens comparable; see the statement "
                  "below.",
            level=("good" if len(meet) == len(with_ci) else "bad"),
            value=round(_st.median(ras), 1)))

    # --- ONE MAGNIFICATION, EVERY FRAME SCALED ---------------------------------------
    # WHY THIS EXISTS. The txm arm had TWO statements, both negative, and no finding at all
    # -- so its Analysis pane said "Nothing is established" while the sem arm showed three
    # findings. That was not a property of the data. Every arm finding in this function is
    # gated on something only the SEM corpus has (a CBS/ETD detector swap, a 3x3 stage
    # raster, a specific calibrated magnification), and nobody had ever written a finding
    # for the other arm. The asymmetry was in the engine, not in the microscope.
    #
    # GUARDED ON THE DATA, NOT ON THE ARM NAME. "arm == 'txm'" would be a lie the moment a
    # second single-magnification corpus is loaded, and it would hide the fact that this is
    # a statement about scale coverage rather than about a machine.
    scaled = [f for f in frames if f.get("scale_known") and f.get("nm_per_px")]
    if frames and len(scaled) == len(frames) and len(frames) >= 8:
        mags = {round(float(f["nm_per_px"]), 4) for f in scaled}
        if len(mags) == 1:
            only = next(iter(mags))
            out.append(_s(
                "Every frame is scaled at one magnification, so micrometres are comparable.",
                f"{len(frames)} frames, all with a recoverable nm/px, all at {only} nm/px. "
                f"Every physical column is populated and no aggregate here pools across "
                f"scales -- the two things that most often make a micrometre value in this "
                f"app either absent or meaningless. For contrast the SEM corpus withholds "
                f"micrometres on 62 of 142 frames and spans a 249x magnification range, "
                f"which is why its physical aggregates are computed per determination.",
                hedge="One magnification means one resolution: a crack narrower than a "
                      "pixel is unresolved, not absent. It says nothing about accuracy, "
                      "only that the unit is defined and consistent.",
                level="good", value=only))

    # --- WIDTH, WHICH IS THE ONE PHYSICAL QUANTITY THIS ARM MEASURES WELL -------------
    # Width = crack area / centreline length, both in physical units. Reported for this arm
    # specifically because its length is NOT trustworthy -- skeleton and Buffon estimators
    # differ about 2.1x where cracks are a few pixels wide -- while its width is tens of
    # pixels and survives that. Measuring the thing the modality is good at rather than
    # repeating the thing it is bad at.
    #
    # A SEPARATION CLAIM, NEVER AN ORDERING. Each specimen here is one imaged site, so the
    # named extremes are not a result; the same rule the figure read-out follows.
    try:
        import statistics as _st2
        # ONE MAGNIFICATION, or this is the pooling the app forbids everywhere else.
        # Nothing in the first version of this block required it: it happened to be
        # correct for the txm arm, where all 71 frames sit at 29.24 nm/px, and would have
        # silently compared widths across a 249x scale range on any corpus that did not.
        # A statement that is true only because of the data in front of me is a defect
        # waiting for the next import.
        from collections import Counter as _C2
        usable = [f for f in frames
                  if f.get("crack_area_um2") and f.get("total_length_um")
                  and f["total_length_um"] > 0 and f.get("nm_per_px")]
        wid = {}
        if usable:
            modal_w = _C2(round(float(f["nm_per_px"]), 4) for f in usable).most_common(1)[0][0]
            for f in usable:
                if round(float(f["nm_per_px"]), 4) != modal_w:
                    continue
                wid.setdefault(f.get("specimen", "unparsed"), []).append(
                    f["crack_area_um2"] / f["total_length_um"])
        multi = {k: v for k, v in wid.items() if len(v) >= 2}
        if len(multi) >= 3:
            meds = {k: _st2.median(v) for k, v in multi.items()}
            between = max(meds.values()) - min(meds.values())
            within = _st2.median([max(v) - min(v) for v in multi.values()])
            allw = sorted(x for v in multi.values() for x in v)
            if within > 0 and between > within:
                out.append(_s(
                    "Crack width separates these specimens by more than each one varies.",
                    f"width = crack area / centreline length, both in micrometres, over "
                    f"{len(allw)} frames in {len(multi)} specimens. Specimen medians "
                    f"{min(meds.values()):.3f} to {max(meds.values()):.3f} um, a spread of "
                    f"{between:.3f} um against a typical specimen's own range of "
                    f"{within:.3f} um -- between exceeds within by {between / within:.1f}x. "
                    f"Individual frames run {allw[0]:.3f} to {allw[-1]:.3f} um "
                    f"({allw[-1] / allw[0]:.1f}x). Width is used rather than length because "
                    f"this arm's two length estimators disagree about 2.1x at these crack "
                    f"widths, while the widths themselves are tens of pixels across. "
                    f"All of these frames sit at {modal_w} nm/px: a width median over "
                    f"frames at different scales would be the pooling refused elsewhere.",
                    hedge="Separated is not ordered. Each specimen is ONE imaged site, so "
                          "material difference and site difference are the same variance "
                          "component here and the named extremes are not a ranking.",
                    level="good", value=round(between / within, 2)))
    except Exception:
        pass

    # --- RANKING, once, where the table that invites it is ----------------------------
    from specimen_stats import PSEUDO_SPECIMEN
    real = [r for r in recs if r.get("specimen") != PSEUDO_SPECIMEN]
    if len(real) > 1:
        out.append(_s(
            "These specimens cannot be ordered by this sampling design.",
            "each was imaged at a single site, so the scatter between its fields and the "
            "difference between specimens are the same variance component, and no test on "
            "these data separates them -- spatial pseudoreplication in Hurlbert's sense. "
            "The table below is in name order for that reason.",
            hedge="A second imaged site on a specimen would make the question answerable. "
                  "Until then a narrower interval buys precision on the one site.",
            level="warn"))

    # --- THE DETECTOR, which is confounded with the specimen --------------------------
    ds = [r["detector_sensitivity"]["cbs_over_etd_median"] for r in recs
          if (r.get("detector_sensitivity") or {}).get("cbs_over_etd_median")]
    if ds:
        med = _st.median(ds)
        out.append(_s(
            f"Detector alone moves the answer {med:.1f}× across this arm.",
            f"CBS against ETD on the SAME physical fields, in {len(ds)} specimen(s) imaged "
            f"both ways. Per-specimen medians run {min(ds):.2f}× to {max(ds):.2f}×.",
            hedge="Detector is confounded with specimen here -- some specimens were imaged "
                  "one way only, so part of any difference between two of them is which "
                  "detector looked.",
            level="bad", value=round(med, 3)))

    # --- WHAT THE DETECTOR SWAP MOVES. CONTROLLED, REAL, AND NOT ONE NUMBER ----------
    #
    # The design is the sound part and it stays: the SAME physical field through two
    # detectors is one of exactly two properly controlled contrasts in the corpus, and
    # the centreline excess is real -- CBS carries more skeleton than ETD on 35 of 36
    # fields. Three things this statement used to say are withdrawn.
    #
    # 1. "NOT WIDTH" WAS A PROPERTY OF THE ESTIMATOR, NOT OF THE DETECTOR. The width
    #    term here is area/length, so log(width ratio) IS log(area ratio) minus
    #    log(length ratio) by construction: it is pinned near 1 whenever area and length
    #    move by similar factors, which they do here (2.72x and 2.79x). That is one
    #    decomposition of a single area change, not an independent calibre, and
    #    mean_width_px_median cannot referee it because it is the same construction per
    #    region. The two instruments in cracks.json that ARE independent calibres both
    #    disagree with the old claim: see DETECTOR_CALIBRE_RATIOS. So the app now states
    #    no width result here in either direction -- not "narrower", not "the same".
    #
    # 2. THE CONTROL DID NOT SAY WHAT IT CLAIMED, and its own numbers showed it. Between
    #    two DIFFERENT fields with the SAME detector, length still moves MORE than width
    #    at the median (|log| 0.427 against 0.369) and on 165 of 288 such pairs -- and
    #    the "only 69 of 144 and 96 of 144" this comment used to cite as the contrast ARE
    #    that 165 of 288, split by detector and read as if a majority were a minority.
    #    The ETD half alone is 96 of 144 with median |log length| 0.713 against |log
    #    width| 0.352. The detector swap is a more extreme version of the same pattern,
    #    not a different routing, so it is no longer offered as a control.
    #
    # 3. THE MEDIAN IS NOT THE EFFECT. Stratified by how much crack ETD found, the length
    #    ratio runs 6.0x / 4.9x / 3.4x / 1.8x from the emptiest ETD fields to the fullest
    #    (n = 4 / 6 / 18 / 8; Spearman -0.61, p = 8e-5), and inside MAR_AmbB_HIP alone --
    #    nine fields, one stage raster, one gain pair -- it spans 0.11x to 31.1x. A single
    #    multiplier reads as a calibration constant and there is no constant here.
    #
    # LEVEL IS "bad", NOT "good". What is established is that this pipeline's measured
    # crack LENGTH depends on which detector looked -- the mechanism of the sibling
    # statement above, not a positive result about the material. Much of it is traceable
    # to one uncalibrated constant in the segmenter (mad_k=5.0, whose own docstring names
    # this dataset's ETD captures as the case it exists to cap) and to the two channels
    # having run at different amplifier gains: see docs/PRACTICE_AND_PRIOR_ART.md.
    try:
        from specimen_stats import detector_of, field_key
        pairs = {}
        for f in frames:
            if not f.get("nm_per_px") or not f.get("total_skeleton_length_px"):
                continue
            d = detector_of(f.get("frame", ""))
            if d in ("CBS", "ETD"):
                # ARM IS PART OF THE KEY. for_arm() takes no arm argument and reads
                # f["arm"] nowhere else: it scopes nothing internally and trusts its
                # caller, which today is app/server.py's /api/readout and does filter to
                # one arm before calling. So this is DEFENSIVE and changes no current
                # number -- gated-only, machine-only and all-arms-mixed all give 36 pairs
                # at 51.883 nm/px with median length 2.788x and area 2.722x. Without the
                # arm in the key, a caller that passed two arms would have one record per
                # (field, detector) silently overwrite the other.
                #
                # It is not luck that the numbers agree. All 142 frame stems appear in
                # both SEM arms; 98 are byte-identical on area and length and 44 differ
                # under operator correction. The 72 frames behind these 36 pairs contain
                # ZERO of the 44, because the paired specimens (MAR_AmbB_AS/HIP,
                # MAR_H_AS/HIP, 9 fields each) and the operator-corrected ones
                # (260708_316_H_b2, MAR_Amb_HIP, MAR_Amb_AS, ...) are DISJOINT SETS --
                # note MAR_AmbB_HIP and MAR_Amb_HIP are different specimens. Add a
                # corrected specimen to the paired set and the collision becomes live.
                pairs.setdefault(
                    (f.get("arm"), field_key(f["frame"]), f["nm_per_px"]), {})[d] = f
        # ONE MAGNIFICATION ACROSS ALL THE PAIRS, not one per pair. Keying on
        # (arm, field, nm_per_px) already guarantees both members of a pair share a scale,
        # but taking a median over pairs at DIFFERENT scales is the pooling this app forbids
        # everywhere else -- and it moves the answer: including the 337.2396 nm/px overview
        # pairs, where the ratio is about 1.0, pulled 2.79x down to 2.5x. Modal scale only.
        from collections import Counter as _C
        ready = [(k, v) for k, v in pairs.items() if len(v) == 2]
        if ready:
            # nm_per_px is key[NM], named rather than indexed: it was k[1] until the arm
            # went in front of it, and a stale literal index here would have silently
            # taken the modal FIELD NAME as the magnification and dropped every pair.
            NM = 2
            modal = _C(k[NM] for k, _ in ready).most_common(1)[0][0]
            both = [v for k, v in ready if k[NM] == modal]
        else:
            both, modal = [], None
        if len(both) >= 8:
            import statistics as _st
            rows = []
            for v in both:
                c, e = v["CBS"], v["ETD"]
                Lc, Le = c["total_skeleton_length_px"], e["total_skeleton_length_px"]
                Ac, Ae = c.get("crack_area_px"), e.get("crack_area_px")
                if not (Lc and Le and Ac and Ae):
                    continue
                rows.append({"lr": Lc / Le, "ar": Ac / Ae,
                             "etd_af": e.get("area_fraction"),
                             "spec": c.get("specimen")})
            lr = [r["lr"] for r in rows]
            # THE RANGE, FROM THE EXTREME STRATA RATHER THAN THE EXTREME FIELDS. Binning
            # on what the ETD channel found is the stratification that makes the spread
            # legible instead of alarming: the single 31x field is one raster position,
            # while "emptiest ETD fields against fullest" is a reproducible contrast.
            # Edges are decades of ETD area fraction, not tuned.
            strata, EDGES = [], [(0.0, 0.001), (0.001, 0.005), (0.005, 0.02),
                                 (0.02, float("inf"))]
            for lo, hi in EDGES:
                g = [r["lr"] for r in rows
                     if r["etd_af"] is not None and lo <= r["etd_af"] < hi]
                if g:
                    strata.append((lo, hi, len(g), _st.median(g)))
            if len(lr) >= 8 and len(strata) >= 2:
                # min/max of the stratum medians, NOT the first and last stratum. The
                # trend is currently monotone (6.0x down to 1.8x), but keying the headline
                # on position would print the range backwards as "6.0x to 1.8x" the moment
                # a rebuilt corpus broke that monotonicity, and a reversed range is the
                # kind of thing a reader corrects rather than disbelieves.
                lo_med = min(s[3] for s in strata)
                hi_med = max(s[3] for s in strata)
                worst = max(({"spec": s,
                              "lo": min(r["lr"] for r in rows if r["spec"] == s),
                              "hi": max(r["lr"] for r in rows if r["spec"] == s)}
                             for s in {r["spec"] for r in rows}),
                            key=lambda d: d["hi"] / d["lo"] if d["lo"] else 0)
                out.append(_s(
                    f"CBS carries {lo_med:.1f}× to {hi_med:.1f}× ETD's crack centreline, "
                    f"depending how much ETD found.",
                    f"{len(lr)} physical fields imaged both ways at {modal} nm/px -- one "
                    f"magnification, because a median over pairs at different scales "
                    f"would be the pooling this app refuses elsewhere. CBS carries the "
                    f"longer centreline on {sum(x > 1 for x in lr)} of {len(lr)} fields, "
                    f"so the DIRECTION is established; the SIZE is not a constant. "
                    f"Stratified by the ETD channel's own area fraction it runs "
                    + " / ".join(f"{m:.1f}× (ETD area fraction "
                                 + (f"over {lo:g}" if hi == float("inf")
                                    else f"{lo:g}-{hi:g}") + f", n={n})"
                                 for lo, hi, n, m in reversed(strata)) +
                    f". Inside {worst['spec']} alone -- one specimen, one stage raster, "
                    f"one gain pair -- it spans {worst['lo']:.2f}× to {worst['hi']:.2f}×, "
                    f"so the stratum medians are a trend and not an interval. The overall "
                    f"median is {_st.median(lr):.2f}× and is reported here only as the "
                    f"midpoint of that trend. NO WIDTH CLAIM is made, in either direction: "
                    f"area/length width is log(area)-log(length) by construction, and the "
                    f"two per-region instruments that are not area/length (maximum "
                    f"inscribed width, ellipse minor axis) are each strongly monotone in "
                    f"region area, so on a detector that marks bigger regions they read as "
                    f"width change when they are reporting size -- a size-only null "
                    f"overshoots them and size-matched strata put both at unity "
                    f"({DETECTOR_CALIBRE_RATIOS['size_matched']['max_inscribed_width']:.2f}×"
                    f" and "
                    f"{DETECTOR_CALIBRE_RATIOS['size_matched']['ellipse_minor_axis']:.2f}×)."
                    f" No instrument here can referee width.",
                    hedge="It does NOT say CBS sees more real crack. A binary mask cannot "
                          "say whether the extra centreline is crack ETD missed or "
                          "segmentation gain on a noisier backscatter image, and nothing "
                          "here referees these fields. What it is NOT confounded by is "
                          "acquisition: across the 40 pairs carrying FEI metadata, dwell, "
                          "HV, beam current, working distance, field size, pixel width, "
                          "every stage axis and the timestamp are bit-identical, so this "
                          "is a clean detection-mode contrast and each detector's own gain "
                          "is part of what using it means. Two real caveats remain: ETD's "
                          "own gain was re-adjusted field to field (ContrastDB 27.1-37.5) "
                          "while CBS sat fixed at 45.3, so the ETD arm carries operator "
                          "variation the CBS arm does not; and a large share of the gap is "
                          "reproduced by this repository's own segmenter before any "
                          "detector physics is invoked. This is not a correction factor.",
                    level="bad", value=round(_st.median(lr), 2)))
    except Exception:
        pass

    # --- SPATIAL STRUCTURE, AS A FINDING RATHER THAN A NUISANCE -----------------------
    #
    # The gradient was already reported, per specimen, as a reason the E562 interval is
    # unreliable. That is true and it is half the story: the trend is CONSISTENT IN
    # DIRECTION across every specimen that has stage coordinates, which makes it a
    # statement about the material and not only about the sampling. And it is actionable --
    # blocking the interval on the stage row roughly halves the relative accuracy.
    #
    # Computed live from the records rather than stored, so it tracks the corpus.
    try:
        import stage as _stage
        from specimen_stats import field_key as _fk
        import statistics as _st2
        rows_ok, ratios = 0, []
        for spec in sorted({r.get("specimen") for r in recs}):
            ff = [f for f in frames
                  if f.get("specimen") == spec and f.get("scale_known")
                  and f.get("area_fraction") is not None]
            groups = _partition_for_conclusions(ff)
            by = {}
            for f in groups:
                pos = _stage.position(f.get("frame", ""))
                if pos:
                    by.setdefault(_fk(f["frame"]), []).append((pos, f["area_fraction"]))
            fields = [(v[0][0], _st2.mean([x[1] for x in v])) for v in by.values()]
            if len(fields) != 9:
                continue
            fields.sort(key=lambda z: z[0][1])
            vals = [v for _, v in fields]
            r0, r1, r2 = vals[0:3], vals[3:6], vals[6:9]
            if _st2.mean(r2) > _st2.mean(r1) > _st2.mean(r0):
                rows_ok += 1
                ratios.append(_st2.mean(r2) / _st2.mean(r0 + r1))
        if len(ratios) >= 3 and rows_ok == len(ratios):
            out.append(_s(
                f"Cracking rises toward one edge of the raster in all "
                f"{len(ratios)} positioned specimens.",
                f"nine fields per specimen on a 3x3 stage raster at one magnification, "
                f"collapsed to fields. The three highest-stage-Y fields carry "
                f"{min(ratios):.1f}x to {max(ratios):.1f}x the area fraction of the lower "
                f"six, and the three row means fall in the same order in all "
                f"{rows_ok} of {len(ratios)}. Exact permutation of a specimen's own nine "
                f"values over its nine positions reaches p = 0.0119 on three of them -- "
                f"which is the FLOOR of that test (1 of 84 arrangements), not a small "
                f"p-value. Stage X carries nothing by the same test.",
                hedge="The consequence is practical: block the interval on the stage row "
                      "and relative accuracy roughly halves. The caution is that the "
                      "high-stage-Y row is also the FIRST-ACQUIRED row in every specimen, "
                      "so position and acquisition order cannot be separated here; that "
                      "stage Y maps to no declared build or loading direction; and that "
                      "whether this is a step or a smooth ramp is undecidable at nine "
                      "points -- a perfect ramp built from the same values passes every "
                      "test above identically.",
                level="good", value=round(_st2.median(ratios), 2)))
    except Exception:
        pass

    # --- THE MEASUREMENT'S VALIDITY ENVELOPE, stated as a positive ---------------------
    #
    # A CALIBRATION, not a per-corpus recomputation, and labelled as one. Re-binarising 36
    # scaled fields from 51.9 to 311 nm/px with an area-preserving 50% rule preserved total
    # crack area to a median ratio of 1.000 (bootstrap 95% CI 0.998-1.001), every field
    # inside +/-10%. The null is what earns it: synthetic cracks 1 and 2 px wide, run
    # through the identical operation, retain 0.04 of their area at 3x and 0.00 at 6x. So
    # the crack mass this app measures genuinely sits above the resolution limit -- the area
    # fraction is not a thing that appears because the pixels are small enough to see it.
    # SCOPED TO WHERE IT WAS MEASURED. It was calibrated on SEM fields at 51.883 nm/px,
    # and firing it on txm -- a different instrument at 29.24 nm/px -- would be asserting a
    # result for an arm it was never tested on, which is the one thing this app refuses
    # most consistently. It stays silent there rather than generalising.
    CALIBRATED_AT = 51.883
    if any(abs((f.get("nm_per_px") or 0) - CALIBRATED_AT) < 0.01 for f in frames):
        out.append(_s(
            "Crack area is not a resolution artefact: it survives a 6× coarser pixel.",
            f"a calibration at {CALIBRATED_AT} nm/px, not a recount: re-binarising 36 "
            "scaled fields from 51.9 to "
            "311 nm/px with an area-preserving rule left total crack area at a median "
            "ratio of 1.000 (95% CI 0.998-1.001), all 36 within ±10%. Synthetic cracks 1 "
            "and 2 px wide put through the same operation retain 0.04 of their area at 3× "
            "and none at 6×, so the test can fail and this mask does not.",
            hedge="True of an area-preserving binarisation only. A dilating rule -- coarse "
                  "pixel is crack if ANY sub-pixel is -- inflates the same fields to 1.47× "
                  "at 6×, so at coarse pixels the rule matters more than the pixel size. "
                  "It says nothing about the crack COUNT, which does not survive.",
            level="good"))

    # --- HOW MUCH OF THE CORPUS CAN BE SPOKEN ABOUT IN MICROMETRES --------------------
    if frames:
        ns = sum(1 for f in frames if not f.get("scale_known"))
        if ns:
            out.append(_s(
                f"{ns} of {len(frames)} frames have no scale: µm withheld.",
                f"a frame gets micrometres only from a recoverable nm/px -- a databar, the "
                f"TIFF's own metadata, or one you set. Without it every physical column is "
                f"null rather than defaulted, and the corpus spans a 249× magnification "
                f"range, so there is no defensible default to fall back on.",
                hedge="Those frames are still measured; it is the unit that is missing, "
                      "not the measurement. Set a scale per frame to recover them.",
                level="warn", value=ns))

    # --- WHAT THE OPERATOR CONTRIBUTED, where both arms exist -------------------------
    sens = [r["arm_sensitivity"] for r in recs if r.get("arm_sensitivity")]
    touched = [a for a in sens if a.get("n_frames_corrected")]
    ratios = [a["gated_over_machine_where_corrected"] for a in touched
              if a.get("gated_over_machine_where_corrected")]
    if sens and ratios:
        med = _st.median(ratios)
        out.append(_s(
            f"Operator corrections change {len(touched)} of {len(sens)} specimens.",
            f"the gated and machine arms are the same frames with and without the "
            f"operator's strokes. Where a correction exists the gated area fraction is "
            f"{med:.2f}× the machine's at the median, running {min(ratios):.2f}× to "
            f"{max(ratios):.2f}×.",
            hedge="A specimen with no correction is not a specimen the detector got "
                  "right; it is one nobody reviewed.",
            level="info", value=round(med, 3)))

    # FINDINGS FIRST, LIMITS AFTER. Every statement this engine could make was written to
    # fire on FAILURE, and the result was a read-out that only ever said what could not be
    # known -- true line by line and useless as a whole. The two established results now
    # lead, and the limits follow them as qualifications rather than standing in for them.
    # Severity order within each group, so nothing serious is buried.
    ORDER = {"good": 0, "bad": 1, "warn": 2, "info": 3}
    out.sort(key=lambda st: ORDER.get(st["level"], 9))
    return out


#: Axis pairs whose relationship is ARITHMETIC, with the reason. Plotting one against the
#: other produces a tidy correlation that is a restatement of a definition, and this app's
#: own module docstring already rejects one such finding ("MeanWidth is defined as
#: Area/Length, so its slope is the area slope minus one"). A user about to put a scatter
#: in a paper should be told before, not after.
ALGEBRAIC_PAIRS = {
    frozenset(("area_fraction", "crack_area_px")):
        "area fraction IS crack area divided by frame area, and within one magnification "
        "the frame area is a constant -- so this plots a quantity against a rescaling of "
        "itself",
    frozenset(("p21_skeleton_mm_per_mm2", "tcl_um")):
        "P21 is total centreline length per unit area and TCL is that same total length, "
        "so they share a numerator",
    frozenset(("p20_per_mm2", "n_cracks_measured")):
        "P20 is the crack count per unit area and this is that same count, so they share "
        "a numerator",
    frozenset(("area_analysed_mm2", "p21_skeleton_mm_per_mm2")):
        "area analysed is the DENOMINATOR of P21, so any trend here is partly the "
        "definition",
    frozenset(("area_analysed_mm2", "p20_per_mm2")):
        "area analysed is the DENOMINATOR of P20, so any trend here is partly the "
        "definition",
}


def for_figure(kind, x, y, rows, label_of=None):
    """What the figure on screen actually shows, from the rows it was drawn from.

    Takes the FIELD-COLLAPSED rows the renderer used, so a statement can never disagree
    with the picture beside it -- the same rule the frame and specimen read-outs follow.

    Deliberately modest. It reports a rank correlation with its p, the spread of the
    specimen medians, and how concentrated a distribution is. It does NOT order specimens,
    and it does not name a cause: this corpus is one imaged site per specimen, and a
    figure cannot fix that.
    """
    import statistics as _st

    out = []
    rows = [r for r in (rows or [])]
    if not rows:
        return out
    lab = label_of or (lambda k: k)

    # --- SCATTER: a rank correlation, on fields, with its null ------------------------
    if kind == "scatter" and x and y:
        warn = ALGEBRAIC_PAIRS.get(frozenset((x, y)))
        if warn:
            out.append(_s(
                "These two axes are related by definition, not by the material.",
                f"{warn}. A correlation here is arithmetic: it would hold on random data "
                f"that satisfied the same definitions.",
                hedge="Plot one of them against something measured independently if the "
                      "question is about the material.",
                level="bad"))
        xs = [r[x] for r in rows if r.get(x) is not None and r.get(y) is not None]
        ys = [r[y] for r in rows if r.get(x) is not None and r.get(y) is not None]
        if len(xs) >= 4:
            from scipy import stats as _sp
            rho, pv = _sp.spearmanr(xs, ys)
            if rho is not None and rho == rho:
                sig = pv < 0.05
                out.append(_s(
                    (f"{lab(y)} rises with {lab(x)}." if sig and rho > 0 else
                     f"{lab(y)} falls as {lab(x)} rises." if sig else
                     f"No monotonic relationship at this sample size."),
                    f"Spearman rho = {rho:+.3f}, p = {pv:.4f}, over {len(xs)} fields "
                    f"(not frames: a field imaged through two detectors is one point). "
                    f"Rank-based, so it does not assume a straight line or normal errors.",
                    hedge="Fields within a specimen are not independent -- on the "
                          "2026-09-15 batch they are a raster across one patch -- so this "
                          "p is optimistic. It describes these images, not the material.",
                    level=("warn" if sig else "info"), value=round(float(rho), 3)))

    # --- BY SPECIMEN: how far apart the groups are, and the refusal to order ----------
    if kind in ("box_by_specimen", "bar_by_specimen") and (y or x):
        f = y or x
        g = {}
        for r in rows:
            if r.get(f) is not None:
                g.setdefault(r.get("specimen", "unparsed"), []).append(r[f])
        meds = {k: _st.median(v) for k, v in g.items() if v}
        if len(meds) >= 2:
            lo_k = min(meds, key=meds.get)
            hi_k = max(meds, key=meds.get)
            lo, hi = meds[lo_k], meds[hi_k]
            # WITHIN against BETWEEN, because a spread of medians means nothing until you
            # know how wide one specimen already is.
            widths = [max(v) - min(v) for v in g.values() if len(v) > 1]
            spread = (hi - lo)
            typical = _st.median(widths) if widths else None
            # WITHIN vs BETWEEN IS THE FINDING, AND IT USED TO BE BURIED IN THE BASIS.
            # This block emitted exactly one statement, always at level "warn", reading
            # "Specimen medians span 39.5x." -- which is a number, not a conclusion, and
            # amber, so the whole Figure tab showed a single complaint. The comparison a
            # box-by-specimen plot actually answers was already computed one line above
            # and only appeared in the basis text: is the gap BETWEEN specimens bigger
            # than the range INSIDE one? That question has a verdict either way, so it is
            # stated as a finding, and the confound that stops it becoming a ranking is
            # stated separately as its own limit rather than as this line's hedge.
            if typical is not None and spread > 0:
                resolved = spread > typical
                out.append(_s(
                    ("Specimen differences exceed the variation inside one specimen."
                     if resolved else
                     "Specimen differences are smaller than the variation inside one."),
                    f"{len(meds)} specimens. Between the extreme medians: {spread:.4g} "
                    f"{lab(f)}. The typical specimen's own range: {typical:.4g}. "
                    + ("Between is the larger, so the groups are separated by more than "
                       "one group's own width."
                       if resolved else
                       "Within is the larger, so this figure does not show a specimen "
                       "effect -- the boxes overlap by more than they differ."),
                    hedge="Separated is not ordered: see the limit on this figure. A "
                          "verdict either way is about these images, not the material.",
                    level="good",
                    value=round(spread / typical, 3) if typical > 0 else None))
            out.append(_s(
                (f"Specimen medians span {hi / lo:.1f}×." if lo > 0 else
                 "Specimen medians differ."),
                f"{len(meds)} specimens, median {lab(f)} from {lo:.4g} ({lo_k}) to "
                f"{hi:.4g} ({hi_k})"
                + (f"; the typical specimen's own range is {typical:.4g}, against "
                   f"{spread:.4g} between the extremes." if typical is not None else "."),
                hedge="Each specimen here is ONE imaged site, so this spread cannot be "
                      "separated into material difference and site difference. It is not "
                      "a ranking and the named extremes are not a result.",
                level="warn", value=(round(hi / lo, 2) if lo > 0 else None)))

    # --- STAGE RASTER: the gradient, per specimen, from the drawn rows ----------------
    # A chart with no statement under it is what the figure tab used to be, and these two
    # kinds arrived that way: 36 cells on screen and an empty conclusion strip. The
    # statement is the gradient itself, which is the reason the figure exists.
    #
    # PER SPECIMEN, NEVER POOLED. Each raster is one patch on one specimen; a Spearman over
    # all four stacked together would be testing whether four unrelated patches happen to
    # share a direction in instrument stage coordinates, which is not a question about the
    # material and would borrow significance from the sample size.
    if kind in ("stage_map", "stage_surface") and (y or x):
        f = y or x
        try:
            import sys as _sys
            import os as _os
            _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__))))
            import stage as _stage
            bysp = {}
            for r in rows:
                bysp.setdefault(r.get("specimen", "unparsed"), []).append(r)
            grads = {}
            for spec, frs in bysp.items():
                g = _stage.gradient(frs, field=f)
                if g and g.get("spearman_rho") is not None:
                    grads[spec] = g
            if grads:
                sig = {k: g for k, g in grads.items() if (g.get("p_value") or 1) < 0.05}
                same = {g["spearman_rho"] > 0 for g in sig.values()}
                rhos = sorted(g["spearman_rho"] for g in grads.values())
                ps = sorted(g.get("p_value") or 1 for g in grads.values())
                if len(sig) == len(grads) and len(same) == 1 and len(grads) >= 2:
                    out.append(_s(
                        f"Every raster trends across the patch, all in one direction.",
                        f"Spearman of {lab(f)} against the trending stage axis, computed "
                        f"SEPARATELY for each of {len(grads)} specimens and never pooled: "
                        f"rho {rhos[0]:+.3f} to {rhos[-1]:+.3f}, every p below "
                        f"{ps[-1]:.4f}. Each raster is one patch on one specimen, so a "
                        f"Spearman over all of them stacked together would be asking "
                        f"whether unrelated patches share a direction in instrument stage "
                        f"coordinates, and would borrow significance from the sample size. "
                        f"The axis is chosen per specimen as the stronger of stage X and "
                        f"stage Y, so each p is uncorrected for a best-of-two selection: "
                        f"doubling them leaves every one below {min(2 * max(ps), 1.0):.4f}.",
                        hedge="A gradient means these fields are not a sample OVER a "
                              "surface, so the E562 interval on them is largely describing "
                              "a trend rather than sampling error -- and more tiles in the "
                              "SAME patch will not narrow it. Whether separated patches "
                              "would is untested: every specimen here has one imaged "
                              "patch, so between-patch variance has never been measured. "
                              "That is the experiment this result asks for, not a remedy "
                              "it supports.",
                        level="good", value=round(rhos[-1], 3)))
                else:
                    out.append(_s(
                        f"{len(sig)} of {len(grads)} rasters trend across the patch.",
                        f"Spearman of {lab(f)} against the trending stage axis, per "
                        f"specimen, never pooled: rho {rhos[0]:+.3f} to {rhos[-1]:+.3f}. "
                        f"{len(sig)} reach p < 0.05"
                        + ("" if len(same) <= 1 else " and they do not agree on direction")
                        + ".",
                        hedge="Where a raster does trend, its fields are not a sample over "
                              "a surface and more tiles in the same patch will not narrow "
                              "its interval.",
                        level=("warn" if sig else "info"),
                        value=round(rhos[-1], 3)))
        except Exception:
            pass

    # --- HISTOGRAM: is the total carried by a few values? -----------------------------
    if kind == "histogram" and (y or x):
        f = y or x
        vals = sorted((r[f] for r in rows if r.get(f) is not None), reverse=True)
        if len(vals) >= 5 and sum(vals) > 0:
            k = max(1, len(vals) // 10)
            share = sum(vals[:k]) / sum(vals)
            out.append(_s(
                f"The largest {k} of {len(vals)} fields hold {share * 100:.0f}% of the total.",
                f"{lab(f)} summed over {len(vals)} fields; the top decile is "
                f"{share * 100:.1f}% of that sum. A histogram shows the shape but not "
                f"which end carries the mass.",
                hedge="A concentrated total means the mean is describing the few, not the "
                      "many. It does not by itself mean those fields are wrong.",
                level=("warn" if share > 0.5 else "info"), value=round(share, 4)))

    return out


REFUSALS = [
    {
        "question": "Transgranular or intergranular?",
        "label": "crack mode",
        # THE ANSWER NAMES A MEASUREMENT NOW, not the mask. "Not determinable from a
        # crack mask" was true and it pointed at the wrong thing: it read as "this
        # app only has masks", and the app has 154 micrographs with the grain
        # structure plainly visible in them. A user said so. Both micrograph routes
        # were then built and measured, and the budget below is what blocks the
        # call -- so the refusal can state a number instead of a limitation.
        "answer": "Needs 13 \u00b5m facets; this corpus resolves 3.0 \u00b5m.",
        "why": "The distinction is defined by the crack path's relationship to GRAIN "
               "BOUNDARIES, so the boundaries have to be visible and co-registered with "
               "the crack. This refusal used to say only that, arguing from the mask and "
               "never opening the micrograph -- a fair objection, since the app holds 154 "
               "originals in which the grain structure is plainly visible. Both routes "
               "from the micrograph have now been built and measured, and both die on a "
               "GEOMETRIC BUDGET rather than on tuning. "
               "ROUTE 1, boundary coincidence: segment the grain-boundary network from the "
               "image and ask what share of crack centreline lies on it. The crack is "
               "itself the strongest boundary in the image -- a median 72.8% of labelled "
               "pixels are saturated DN 0 on the 316 frames, a ~215 DN silhouette step "
               "against the 15-25 DN step that defines a grain edge -- so the boundary map "
               "must be blanked near the label or the measurement reads its own input. Its "
               "self-response decays to the far field only at 20-40 px, and an inpaint test "
               "puts the crack's contribution at 0.0% only beyond 80 px. THAT RADIUS IS A "
               "LARGE FRACTION OF A GRAIN: grain diameter measured from the databar frames "
               "is 9 um (7-12), i.e. 213 px (166-285) at 42.15 nm/px, and 140 px (125-165) "
               "counted on the unscaled 260708 set -- so the blanking radius is 0.38-0.57 "
               "grain diameters, and a PERFECT, error-free grain partition already places "
               "85-100% of the material within it of a boundary. The statistic is saturated "
               "before any segmentation, labelling or detector question arises. "
               "THE POSITIVE CONTROL IS WHAT SETTLED IT, and without it this app would have "
               "shipped the opposite claim. A synthetic path built FROM the frame's own "
               "boundary skeleton -- following boundaries by construction -- was pushed "
               "through the identical pipeline: at zero exclusion it scores 100% against a "
               "12% null, so the instrument detects boundary-following when it is there, "
               "but under any legitimate exclusion its best score over 54 (brush, radius, "
               "tolerance) cells is z = +0.62. The REAL labels score z = +2.0 to +3.4, "
               "which is above the ceiling a ground-truth-positive path can reach and is "
               "therefore impossible as a path signal. Sweeping the radius confirms the "
               "source: z decays +1.99, +0.58, -0.70, ~0 at R = 6, 20, 40, 80 px, tracking "
               "the independently measured contamination and vanishing exactly where it is "
               "verified zero. "
               "ROUTE 2, turning angle at a scale above the staircase floor -- the refined "
               "form of the linearity idea, the earlier version having failed because it "
               "was computed at one pixel where digitisation dominates. The turning "
               "measurement itself is sound: digitised arcs of known radius return 0.89-0.96 "
               "of their true turning at s >= 32 px, with a floor decaying as ~17 deg/s. The "
               "DISCRIMINATOR is not. Three pre-stated kill criteria all fired. Concentration "
               "of turning ranks branches by painted stroke width, not by path geometry, "
               "Spearman +0.891 (p = 0.0005). A digitised SMOOTH wander with no vertices "
               "anywhere -- which a facet detector must reject -- is called faceted on 30 of "
               "30 branches, and 30 of 30 again after dilation to the corpus's 59 px median "
               "stroke. And with frames as the unit inside a matched width band the set "
               "separation is Kruskal-Wallis p = 0.778; the branch-level p = 0.030 was "
               "pseudoreplication across about 43 fields with one specimen per set. "
               "THE FACET SCALE, measured from crack-free matrix only so the crack cannot "
               "enter its own reference: the largest resolvable microstructural intercept is "
               "58.1 px median (IQR 51.0-71.9) and 122.4 px ANYWHERE in the corpus, which is "
               "3.02 um (2.28-4.27) at a common 51.883 nm/px. A facet-vertex call from a mask "
               "centreline needs facets of at least ~250 px, i.e. >= 13 um, given the measured "
               "staircase floor. No frame in this corpus reaches that. "
               "WHAT IS POSITIVELY TRUE, rather than merely unmeasurable: on the 341 branches "
               "whose painted stroke is 32 px or less -- thin enough to carry a facet signal "
               "at all -- the turn-magnitude distribution IS that of a smooth random curve, "
               "cv 0.758 against the universal half-normal 0.7555 and top-decile share 0.299 "
               "against a matched null of 0.267, about 9% of the effect a synthetic faceted "
               "path produces. Where the label is good enough to see facets, there are none "
               "to see. "
               "The instrument vendor's own documentation agrees with the refusal: EDAX/AMETEK's "
               "note on EBSD analysis of cracking states that it is often not apparent from a "
               "standard SEM micrograph whether a segment follows boundaries or cuts them, and "
               "that EBSD is what makes the call unambiguous. "
               "Only the 316 CBS family shows any boundary network at all -- 25 of 62 labelled "
               "frames; the MAR frames return a partition gain of +0.00 to +0.03 against a "
               "granularity-matched Voronoi control and a semivariogram range of 8 px, i.e. "
               "featureless speckle -- and the APP can extract a nm/px for 0 of the 62 "
               "labelled frames, so every tolerance above is stated in pixels and none of "
               "them can be converted. THAT IS ABOUT THE EXTRACTION PATH, NOT THE FILES, "
               "and the distinction matters because the next sentences quote scales: "
               "scale.from_tiff finds no FEI metadata block in any of these 62 tails and "
               "fei_metadata_260915.csv has no row for any of them, so frames.json "
               "honestly records nm_per_px null and scale_known false for every one -- "
               "while ten of them DO carry a databar a human can read, quoted next and "
               "used as a scale nowhere in this app. Ten of the 25 hand-masked 316 CBS "
               "frames DO carry a legible FEI databar in the original TIFF, and the app "
               "cannot see it. The nine 260622-session frames keep it in the trailing 280 "
               "rows, which the 6144x4096 masks crop off a 6144x4376 original: HFW 259, 173 "
               "and 82.9 um, so 42.15, 28.16 and 13.49 nm/px -- a 3.1x spread inside one "
               "session, which is where that figure came from. 260708_316_H_b2_front_CBS_001 "
               "keeps it in a 144-row band at HFW 2.59 mm, so 843.1 nm/px, and the spread "
               "across all ten is 62.5x rather than 3.1x -- 843.1 over 13.49. NOT 31x, "
               "which this said for several releases: 31x is 2590/82.9, the ratio of the "
               "two HFW values, and it differs from the nm/px ratio because that frame is "
               "3072 px wide while the others are 6144. The sentence names nm/px, so "
               "anyone quoting 31x from the API response quoted a number a factor of two "
               "out for the quantity it was attached to. Each reading cross-checks against "
               "the scale bar drawn in the same band to better than 0.1%. So the true claim "
               "is narrower than the one this refusal used to make, and it is about the "
               "EXTRACTION PATH, not the files: scale.from_tiff returns None for all 25 "
               "because the FEI metadata block is absent from these files' tails, and "
               "fei_metadata_260915.csv has no row for any hand-masked frame, so "
               "frames.json honestly records nm_per_px null and scale_known false for all "
               "50 rows. The other 15, the rest of the 260708 set, are the genuinely "
               "unrecoverable case: their originals end in specimen image with no databar "
               "anywhere. These ten values are NOT used as a scale anywhere in the app -- "
               "reading databar pixels is a source scale.py deliberately does not own, so "
               "adopting it is a change there with its own verification, and two things "
               "weigh on it. First, OCR may not be needed: the SEM repo already ships "
               "crack_export/analysis/scale_hfw.csv, 45 databar-read rows in the same "
               "directory scale.py already reads fei_metadata_260915.csv from, and it "
               "carries exactly these ten frames and none of the other fifteen, at HFW "
               "values matching an independent read of the pixels. Second, CBS_001's mask "
               "is a 1490x1490 crop of a 3072x2044 field whose provenance does not record "
               "whether it was resampled, so 843.1 nm/px may not transfer to that mask.",
        "would_need": [
            "EBSD on one or two of the SAME fields, then score crack centreline length "
            "coincident with a reconstructed boundary. The only direct route.",
            "An etched image of the same field, co-registered.",
            "A much thinner segmentation of the 316 steel CBS frames, where grains are "
            "already visible through backscatter channelling contrast. This covers only "
            "part of the corpus: most CBS frames show no grain contrast, the visible "
            "grains carry heavy twin and slip striations that a naive boundary detector "
            "would read as boundaries, and channelling contrast cannot separate a "
            "coherent annealing twin from a general boundary -- so this route needs a "
            "declared misorientation threshold just as the EBSD route does.",
        ],
        "not_this": "Tortuosity, LINEARITY or branching as a mode index -- and linearity "
                    "specifically, because it is the obvious idea and this app has now "
                    "measured it. Per-branch length/chord over seven MAR specimens "
                    "spanning as-sprayed, HIP and cast: medians 1.011 to 1.055, a 4.4% "
                    "spread, with every specimen's own interquartile range about "
                    "1.00-1.08. It varies more BETWEEN BRANCHES OF ONE SPECIMEN than "
                    "between specimens. And the null kills it outright: a mathematically "
                    "straight line pushed through this same pipeline measures 1.001 to "
                    "1.082 depending only on its ANGLE TO THE PIXEL GRID, median 1.0605 "
                    "-- so the observed values sit inside the straight-line range and "
                    "their median is LOWER than a straight line's. What linearity "
                    "measures here is staircasing, not path. The older tortuosity figures "
                    "(~1.09 against 1.048) came from the SIBLING repo's estimator, which "
                    "this app retired after it produced impossible sub-one values. Turn angles showed no population near the 60° deviation "
                    "expected at 120° triple junctions, but that test cannot register one: "
                    "the branch extraction deletes junction pixels first, so a "
                    "triple-junction deviation is absent by construction rather than "
                    "measured to be absent. And branching does not carry the sign it is "
                    "assumed to: Wale, SKI 2006:24 §6.3.3 reports microscopic branching at "
                    "half to one grain diameter as COMMON for intergranular SCC in "
                    "austenitic stainless -- the same scale this app measures.",
    },
    {
        "question": "How rough is the crack path? (R_L, tortuosity)",
        "label": "path roughness",
        "answer": "R_L needs a declared axis; against the raster it is sec(angle).",
        "why": "Quantitative fractography's R_L is true length over length projected on a "
               "DECLARED specimen axis -- loading, transverse, build. This app has nowhere "
               "to declare one, and the R_L column it shipped until now had its axis "
               "defaulted to the image x-raster on all 356 frames, never once set. Against "
               "a fixed image axis the projection is the chord times cos(angle), so the "
               "ratio reduces to (length/chord) x sec(angle) -- an identity, not a "
               "measurement of the material. Its corpus median AND upper quartile were "
               "both exactly 1.4142, and sec(45 deg) is simultaneously a pixel-lattice "
               "diagonal, a straight 45-degree crack and the isotropic expectation, three "
               "states the number cannot separate. The predecessor, tortuosity, was "
               "retired for a different reason: its 2-endpoint gate described 2.6% of the "
               "crack area here and none of the TXM regions, and it once produced "
               "impossible sub-one values.",
        "would_need": [
            "A declared loading or transverse axis per specimen, recorded with the "
            "specimen rather than defaulted to the image raster.",
            "Then prefer the rose: it already answers the orientation question with a "
            "per-frame permutation null, and re-expressing its angle against a declared "
            "axis re-expresses a tested number instead of adding an untested one.",
        ],
        "not_this": "The image raster as a stand-in for the specimen axis. That is what "
                    "produced the deleted column, and it also makes the number track the "
                    "digitisation: a third of skeleton branches have a chord lying exactly "
                    "on a lattice axis or diagonal. Nor is a per-crack path/chord ratio a "
                    "substitute -- it measures a crack against itself and is undefined for "
                    "a branched one, which is most of the crack area here.",
    },
    {
        "question": "Ductile or brittle? Dimples, cleavage, striations?",
        "label": "fracture mode",
        "answer": "Wrong image type.",
        "why": "Those are grayscale texture on a FRACTURE surface. This corpus is "
               "polished-section plan views, and the input here is a binary mask.",
        "would_need": ["Fracture-surface micrographs, analysed as grayscale texture rather "
                       "than as a crack mask."],
        "not_this": None,
    },
    {
        "question": "Crack depth, or aspect ratio a/c?",
        "label": "depth",
        "answer": "Needs a section geometry this app does not have.",
        "why": "Depth needs a defined free surface and a cross-section. A 2D inertia-ellipse "
               "ratio is an unrelated number a materials reader would misread as a/c.",
        "would_need": ["A cross-section through the crack, or tomography with a declared "
                       "surface datum."],
        "not_this": None,
    },
]
