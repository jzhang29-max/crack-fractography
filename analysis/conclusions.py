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

    largest_share_of_area   0.870  (p = 0.084, not significant)  <- survives
    n_cracks_measured       1.226  (p = 4.2e-4)
    area_fraction           2.286  (p = 8.1e-9)
    n_junctions             3.071  (p = 2.1e-6)                  <- rejected outright

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

    # --- REGIME. The only metric tested that the detector does not move. ---------------
    share = f.get("largest_share_of_area")
    if share is not None:
        if share >= DOMINANT_CUT:
            out.append(_s(
                f"One crack holds {100 * share:.0f}% of the crack area.",
                "largest_share_of_area; the only metric tested that the CBS/ETD detector "
                "difference does not move (paired ratio 0.870, p = 0.084 n.s.)",
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
    R, R95, th = f.get("rose_R"), f.get("rose_R_null95"), f.get("rose_theta_deg")
    if beats is True and th is not None:
        out.append(_s(
            f"Oriented near {th:.0f}° to image x.",
            f"length-weighted axial resultant R = {R:.3f} against its own permutation "
            f"null R95 = {R95:.3f} (1000 draws, uniform directions, observed segment "
            f"lengths). Construct: ASTM E1268-19 line-intercept anisotropy; axial "
            f"statistics per Mardia & Jupp.",
            hedge="Direction to no better than ±10°, and relative to IMAGE x -- "
                  "the mapping to a build or loading axis is not in the data and must be "
                  "declared.",
            level="good", value=th))
    elif beats is False:
        out.append(_s(
            "Not resolvably oriented.",
            f"R = {R:.3f} does not exceed its permutation null R95 = {R95:.3f}. The null "
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

    return out


REFUSALS = [
    {
        "question": "Transgranular or intergranular?",
        "label": "crack mode",
        "answer": "Not determinable from a crack mask.",
        "why": "The distinction is defined by the crack path's relationship to GRAIN "
               "BOUNDARIES, so the boundaries have to be visible and co-registered with "
               "the crack. We know of no validated proxy for this input -- a binary mask "
               "with no grain partition. This corpus's own test, that if a crack follows "
               "boundaries the islands it encloses are grains, fails because the detected "
               "band is far wider than the crack and never closes a loop around one: "
               "enclosed islands run 10-100 px against grains estimated by eye at 300-500 "
               "px in the sibling repo's crops. Treat that grain figure as a visual "
               "estimate, not a measurement -- it is one reading across a 3.1x intra-set "
               "pixel-scale spread, and no 316 CBS frame in this dataset has a recoverable "
               "nm/px at all.",
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
        "not_this": "Tortuosity, turn angles or branching as a mode index. The tortuosity "
                    "figures behind that -- ~1.09 across every set, against 1.048 for a "
                    "mathematically straight line -- come from the SIBLING repo's "
                    "estimator, which this app retired after it produced impossible "
                    "sub-one values; they are quoted as its findings, not as this app's "
                    "measurements. Turn angles showed no population near the 60° deviation "
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
