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
detector looked at the same piece of metal. Tortuosity/R_L is rejected for a different
reason -- a mathematically straight line measures 1.048 through this pipeline and R_L's
corpus median of 1.4142 is exactly sec(45 deg), which IS the isotropy null. Width-length
scaling is rejected as algebra: MeanWidth is defined as Area/Length, so its slope is the
area slope minus one.

EVERY STATEMENT CARRIES ITS OWN SUPPRESSION RULE, and the rules do most of the work here.
A statement with no condition under which it must stay silent is not ready to ship.
"""

#: The one cut point this module uses that no standard supplies. Labelled as the app's own
#: wherever it is shown, and the underlying value is always printed beside the verdict so a
#: reader can apply their own.
DOMINANT_CUT = 0.90

#: Detector-discordance rate for the regime call, measured on the 56 double-imaged fields:
#: the call flips between CBS and ETD on 10 of them at this cut point.
REGIME_DISCORDANCE = 0.18

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
            f"R = {R:.3f} does not exceed its permutation null R95 = {R95:.3f}. A "
            f"synthetic mask of straight lines at uniform random angles returns "
            f"R = 0.16-0.29 on this pipeline, so a lopsided rose is the default "
            f"appearance of randomness here.",
            level="warn", value=R))

    # --- LENGTH TRUST. Two estimators of one quantity disagreeing is self-disqualifying.
    sk = f.get("p21_skeleton_mm_per_mm2")
    bf = (f.get("probe") or {}).get("p21_buffon_mm_per_mm2")
    if sk and bf and sk > 0:
        ratio = bf / sk
        if ratio and (ratio < 1 / LENGTH_TRUST_RATIO or ratio > LENGTH_TRUST_RATIO):
            out.append(_s(
                f"Length unreliable: two estimators differ {max(ratio, 1 / ratio):.1f}×.",
                f"skeleton P21 = {sk:.3g} against Buffon (π/2)·mean(P_L) = "
                f"{bf:.3g} mm/mm² -- two estimators of the same centreline length per "
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
                f"±{ra:.0f}%: too coarse to rank this specimen.",
                f"ASTM E562-19e1 95% CI from between-field variance over {ci['n_fields']} "
                f"fields. E562's usual target is ±{E562_RA_TARGET:.0f}%, and nothing in "
                f"this arm reaches it.",
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
    elif r.get("n_fields", 0) < 3:
        out.append(_s(
            f"Only {r.get('n_fields', 0)} field(s): no interval.",
            "ASTM E562 needs enough fields for the between-field variance to mean "
            "something; below three the interval is unstable enough to mislead.",
            level="warn"))

    # --- SPATIAL GRADIENT. Are these fields a sample, or a raster across one patch? ---
    if grad_fires:
        rr = grad.get("row_mean_ratio")
        out.append(_s(
            (f"Cracking varies {rr:.0f}× across this patch; fields are not independent."
             if rr else
             "Cracking trends across this patch; fields are not independent."),
            f"Spearman rho = {grad['spearman_rho']:+.3f}, p = {grad['p_value']:.5f} against "
            f"{grad['axis'].replace('_', ' ')} over {grad['n_frames_with_position']} frames "
            f"in {grad['n_stage_rows']} stage rows. {grad['note']}",
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
REFUSALS = [
    {
        "question": "Transgranular or intergranular?",
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
        "question": "Ductile or brittle? Dimples, cleavage, striations?",
        "answer": "Wrong image type.",
        "why": "Those are grayscale texture on a FRACTURE surface. This corpus is "
               "polished-section plan views, and the input here is a binary mask.",
        "would_need": ["Fracture-surface micrographs, analysed as grayscale texture rather "
                       "than as a crack mask."],
        "not_this": None,
    },
    {
        "question": "Crack depth, or aspect ratio a/c?",
        "answer": "Needs a section geometry this app does not have.",
        "why": "Depth needs a defined free surface and a cross-section. A 2D inertia-ellipse "
               "ratio is an unrelated number a materials reader would misread as a/c.",
        "would_need": ["A cross-section through the crack, or tomography with a declared "
                       "surface datum."],
        "not_this": None,
    },
]
