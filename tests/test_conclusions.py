#!/usr/bin/env python3
"""The read-out must stay silent when the data cannot support a sentence.

Suppression is most of this module's value. An app that says "preferentially oriented at
32 degrees" on a frame whose resultant does not beat its own isotropy null is worse than an
app that says nothing, because the sentence is more citable than the number.
"""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "analysis"))
import conclusions as C   # noqa: E402


def frame(**kw):
    base = dict(arm="sem/gated", scale_known=True, n_cracks_measured=50,
                largest_share_of_area=0.5, censored_share=0.02,
                censored_share_by_length=0.05, rose_beats_null=None,
                rose_R=None, rose_R_null=None, rose_theta_deg=None)
    base.update(kw)
    return base


def texts(sts):
    return " || ".join(s["text"] for s in sts)


# --- the word cap is enforced, not aspirational ------------------------------------
def test_every_statement_is_within_the_word_cap():
    for f in (frame(), frame(largest_share_of_area=0.97), frame(scale_known=False),
              frame(arm="txm"), frame(n_cracks_measured=0),
              frame(rose_beats_null=True, rose_R=0.6, rose_R_null=0.2, rose_theta_deg=32),
              frame(rose_beats_null=False, rose_R=0.2, rose_R_null=0.3),
              frame(censored_share_by_length=0.9, mcl_um=500, mcl_um_uncensored_only=100),
              frame(p21_skeleton_mm_per_mm2=40, probe={"p21_buffon_mm_per_mm2": 18})):
        for s in C.for_frame(f):
            assert len(s["text"].split()) <= 15, s["text"]
            assert s["basis"], f"no basis for {s['text']!r}"


# --- orientation: the whole point of the null ---------------------------------------
def test_orientation_is_claimed_only_when_it_beats_its_null():
    yes = C.for_frame(frame(rose_beats_null=True, rose_R=0.61, rose_R_null=0.22,
                            rose_theta_deg=32.4))
    assert "oriented near" in texts(yes).lower()
    no = C.for_frame(frame(rose_beats_null=False, rose_R=0.24, rose_R_null=0.31))
    assert "not resolvably oriented" in texts(no).lower()
    assert "oriented near" not in texts(no).lower()


def test_no_orientation_statement_at_all_without_a_null():
    """A frame measured before the null existed must produce no orientation claim, rather
    than defaulting to either answer."""
    out = texts(C.for_frame(frame(rose_beats_null=None, rose_R=0.61)))
    assert "oriented" not in out.lower(), out


# --- suppression -------------------------------------------------------------------
def test_an_empty_frame_says_one_thing_and_stops():
    out = C.for_frame(frame(n_cracks_measured=0, largest_share_of_area=None))
    assert len(out) == 1 and "No crack pixels" in out[0]["text"]


def test_missing_scale_is_stated_and_no_micrometre_claim_is_made():
    out = C.for_frame(frame(scale_known=False))
    assert "No scale" in texts(out)
    assert "µm" not in texts(out) and "um" not in texts(out).replace("micrometre", "")


def test_txm_carries_its_arm_wide_caveat():
    assert "3 px" in texts(C.for_frame(frame(arm="txm")))
    assert "3 px" not in texts(C.for_frame(frame(arm="sem/gated")))


def test_censoring_is_silent_when_small_and_loud_when_large():
    assert "touches an edge" not in texts(C.for_frame(frame(censored_share_by_length=0.05)))
    loud = texts(C.for_frame(frame(censored_share_by_length=0.94, mcl_um=968,
                                   mcl_um_uncensored_only=59)))
    assert "touches an edge" in loud and "bound" in loud


def test_length_trust_fires_only_on_a_real_disagreement():
    ok = C.for_frame(frame(p21_skeleton_mm_per_mm2=40, probe={"p21_buffon_mm_per_mm2": 36}))
    assert "unreliable" not in texts(ok)
    bad = C.for_frame(frame(p21_skeleton_mm_per_mm2=40, probe={"p21_buffon_mm_per_mm2": 18}))
    assert "unreliable" in texts(bad)
    assert any(s["level"] == "bad" for s in bad)


# --- specimen level ----------------------------------------------------------------
def test_relative_accuracy_failure_is_stated_against_the_e562_target():
    r = {"area_fraction_ci": {"pct_relative_accuracy": 138.0, "n_fields": 6,
                              "ci95_lo_clamped": True}, "n_fields": 6}
    out = texts(C.for_specimen(r))
    assert "wider than E562" in out
    assert "below zero" in out
    # It must NOT speak about ranking. Relative accuracy is a within-patch precision
    # statistic with no between-specimen term, and gating the word "rank" on ra > 10
    # taught the reader that a narrower interval earns a comparison.
    assert "rank this specimen" not in out


def test_a_good_interval_makes_no_precision_complaint():
    r = {"area_fraction_ci": {"pct_relative_accuracy": 6.0, "n_fields": 12,
                              "ci95_lo_clamped": False}, "n_fields": 12}
    assert "precision target" not in texts(C.for_specimen(r))


# --- ranking. Unconditional on precision, because precision is not what is missing ---
def test_ranking_is_refused_however_narrow_the_interval():
    tight = {"area_fraction_ci": {"pct_relative_accuracy": 6.0, "n_fields": 12,
                                  "ci95_lo_clamped": False}, "n_fields": 12,
             "specimen": "MAR_H_AS", "arm": "sem/gated"}
    assert "Ranking specimens is not supported" in texts(C.for_specimen(tight))


def test_ranking_is_refused_with_no_interval_at_all():
    """The eleven thinnest records carry no interval and were still being ordered by their
    bare median in the comparison table, so this is exactly where the refusal must fire."""
    thin = {"area_fraction_median": 0.013, "n_fields": 2,
            "specimen": "MAR_Amb_Cast", "arm": "sem/gated"}
    assert "Ranking specimens is not supported" in texts(C.for_specimen(thin))


def test_the_ranking_refusal_quotes_no_number_and_no_unit():
    """Basis and hedge render on screen OUTSIDE the fifteen-word assert. A refusal to
    compare that ships figures beside itself hands the reader the comparison back."""
    r = {"area_fraction_median": 0.013, "n_fields": 2, "specimen": "MAR_H_HIP"}
    st = [s for s in C.for_specimen(r) if s["text"].startswith("Ranking specimens")][0]
    body = (st["basis"] or "") + " " + (st.get("hedge") or "")
    assert not any(c.isdigit() for c in body), body
    assert not any(u in body for u in ("µm", "mm", "nm/px", "%", "×")), body


def test_a_second_imaged_site_switches_the_ranking_refusal_off():
    """n_patches >= 2 is the off-switch, and it must be reachable without a code edit."""
    r = {"area_fraction_median": 0.013, "n_fields": 12, "specimen": "MAR_H_AS"}
    assert "Ranking specimens is not supported" in texts(C.for_specimen(dict(r, n_patches=1)))
    assert "Ranking specimens is not supported" in texts(C.for_specimen(dict(r, n_patches=None)))
    assert "Ranking specimens is not supported" not in texts(
        C.for_specimen(dict(r, n_patches=2)))


def test_uploads_are_not_told_they_cannot_be_ranked():
    """They already say something stronger: they are not one specimen at all."""
    from specimen_stats import PSEUDO_SPECIMEN
    r = {"specimen": PSEUDO_SPECIMEN, "area_fraction_median": 0.02, "n_fields": 4,
         "no_ci_reason": "uploaded images are unrelated"}
    assert "Ranking specimens is not supported" not in texts(C.for_specimen(r))


def test_the_detector_effect_is_never_a_footnote():
    r = {"n_fields": 10, "detector_sensitivity":
         {"cbs_over_etd_median": 2.45, "n_fields_both_detectors": 10}}
    out = C.for_specimen(r)
    assert "Detector alone moves" in texts(out)
    assert any(s["level"] == "bad" for s in out), "a 2.45x instrument effect is not 'info'"


def test_a_detector_ratio_near_one_is_not_reported():
    r = {"n_fields": 10, "detector_sensitivity":
         {"cbs_over_etd_median": 1.05, "n_fields_both_detectors": 10}}
    assert "Detector moves" not in texts(C.for_specimen(r))


def test_no_corrections_is_distinguished_from_no_effect():
    none = {"n_fields": 5, "arm_sensitivity": {"n_frames_corrected": 0, "n_paired_frames": 20}}
    assert "Unreviewed" in texts(C.for_specimen(none))
    some = {"n_fields": 5, "arm_sensitivity": {"n_frames_corrected": 11, "n_paired_frames": 13,
                                               "gated_over_machine_where_corrected": 1.435}}
    assert "Corrections change area" in texts(C.for_specimen(some))


def test_regime_is_a_tally_over_fields_not_a_median():
    """Frame names matter: the tally collapses detector replicates, so the records need
    stems it can key on. Four distinct fields here, two of them dominated."""
    r = {"n_fields": 4}
    fs = [{"frame": f"S_CBS_000{i}", "largest_share_of_area": v}
          for i, v in enumerate((0.97, 0.95, 0.3, 0.1), 1)]
    assert "2 of 4 fields are single-crack dominated" in texts(C.for_specimen(r, fs))


# --- the refusals ------------------------------------------------------------------
def test_the_mode_question_is_answered_with_a_measured_budget():
    """The answer used to be "Not determinable from a crack mask." True, and it pointed at
    the wrong thing: it reads as "this app only has masks", and the app holds 154
    micrographs with the grain structure plainly visible. A user objected on exactly that
    ground. Both micrograph routes were then built and measured, so the refusal states a
    NUMBER -- the resolution budget that blocks the call -- instead of a limitation."""
    q = [r for r in C.REFUSALS if "ransgranular" in r["question"]][0]
    assert any("EBSD" in w for w in q["would_need"])
    assert q["not_this"] and "ortuosity" in q["not_this"]
    # A quantity in the answer itself, not a category of ignorance.
    assert "\u00b5m" in q["answer"], q["answer"]
    assert "determinable" not in q["answer"].lower(), (
        f"the answer still names a limitation rather than a measurement: {q['answer']}")
    # And the two things that make it a budget rather than an opinion: the scale needed and
    # the scale available.
    assert "13 \u00b5m" in q["answer"] and "3.0 \u00b5m" in q["answer"]


def test_the_refusal_reports_the_positive_control_that_killed_the_route():
    """THE RESULT THAT MATTERS, and the one a reader has to be able to check. Real labels
    score z = +2.0 to +3.4 for boundary coincidence, which is publishable-looking. A
    synthetic path built FROM the boundary skeleton -- following boundaries by construction
    -- reaches at most z = +0.62 under any legitimate exclusion. The real data beats the
    ground-truth ceiling, which is impossible for a path signal, so the apparent result is
    self-reference. Without that control this app would have shipped the opposite claim, so
    the control is part of the finding and not part of the workings."""
    q = [r for r in C.REFUSALS if "ransgranular" in r["question"]][0]
    why = q["why"]
    assert "+0.62" in why, "the ground-truth ceiling is not stated"
    assert "+2.0 to +3.4" in why or "+3.4" in why, "the real-data score is not stated"
    assert "positive control" in why.lower()
    # The decay that identifies the artefact's source.
    assert "80" in why and "0.0%" in why, "the contamination sweep is not reported"


def test_the_refusal_reports_why_the_linearity_route_failed_specifically():
    """The user proposed linearity, and the honest answer is not "no" but "here is the
    number". Three pre-stated kill criteria fired; each has to be recoverable."""
    why = [r for r in C.REFUSALS if "ransgranular" in r["question"]][0]["why"]
    assert "+0.891" in why, "the brush-width confound is not quantified"
    assert "30 of\n               30" in why or "30 of 30" in why, (
        "the smooth-path false-positive rate is not stated")
    assert "0.778" in why, "the frames-as-units result is not stated"


def test_the_refusal_still_reports_what_is_positively_true():
    """A refusal that only says no is less useful than one that says what IS established.
    Where the label is thin enough to carry a facet signal, there is none."""
    why = [r for r in C.REFUSALS if "ransgranular" in r["question"]][0]["why"]
    assert "0.7555" in why, "the half-normal reference is not stated"
    assert "341" in why, "the admissible-branch count is not stated"


def test_the_field_tally_counts_fields_not_frames():
    """Said "0 of 20 fields" for a specimen with 10 fields, because it counted the frames
    handed in. Same error as the figure's n, made an hour after fixing that one, in the code
    written to replace it — so it is asserted here rather than trusted."""
    r = {"n_fields": 2}
    frames = [
        {"frame": "S_CBS_0001", "largest_share_of_area": 0.97},
        {"frame": "S_ETD_0001", "largest_share_of_area": 0.95},   # same field as above
        {"frame": "S_CBS_0002", "largest_share_of_area": 0.10},
        {"frame": "S_ETD_0002", "largest_share_of_area": 0.12},   # same field as above
    ]
    out = texts(C.for_specimen(r, frames))
    assert "1 of 2 fields" in out, out
    assert "of 4" not in out, "four frames are two fields"


# --- the spatial gradient, and what it does to the advice ---------------------------
GRAD = {"significant": True, "spearman_rho": 0.755, "p_value": 0.00012,
        "axis": "stage_y", "n_frames_with_position": 9,
        "n_distinct_stage_coords": 9,
        "field_max_min_ratio": 5.3, "note": "E562 presumes fields placed over a surface."}


def test_a_spatial_gradient_is_stated():
    r = {"n_fields": 10, "stage_gradient": GRAD}
    out = texts(C.for_specimen(r))
    assert "not independent" in out and "5×" in out


def test_the_gradient_basis_does_not_claim_a_row_count():
    """It said "in 9 stage rows" for a 3x3 raster: rows are grouped on the raw coordinate
    and the nine fields differ in the sixth decimal, so each was its own row."""
    out = C.for_specimen({"n_fields": 10, "stage_gradient": GRAD})
    basis = [s for s in out if "not independent" in s["text"]][0]["basis"]
    assert "stage row" not in basis, basis
    assert "9 fields" in basis, basis


def test_a_gradient_suppresses_the_measure_more_fields_advice():
    """More tiles in the SAME patch cannot narrow an interval that is tracking a trend, so
    the standard remedy becomes wrong advice exactly when the gradient fires."""
    ci = {"pct_relative_accuracy": 93.0, "n_fields": 9, "ci95_lo_clamped": False}
    flat = C.for_specimen({"n_fields": 9, "area_fraction_ci": ci})
    grad = C.for_specimen({"n_fields": 9, "area_fraction_ci": ci, "stage_gradient": GRAD})
    hedges = lambda o: " ".join(s["hedge"] or "" for s in o)
    assert "remedy is more fields" in hedges(flat)
    assert "remedy is more fields" not in hedges(grad)


def test_a_nonsignificant_gradient_says_nothing():
    r = {"n_fields": 10, "stage_gradient": dict(GRAD, significant=False, p_value=0.4)}
    assert "not independent" not in texts(C.for_specimen(r))


def test_the_relative_accuracy_basis_does_not_pool_arms():
    """It quoted "0 of 22 specimen-arms", which pools all four arms — the one thing this app
    refuses to do anywhere else, since the arms are different instruments or different
    definitions of the object."""
    r = {"n_fields": 6, "area_fraction_ci": {"pct_relative_accuracy": 138.0, "n_fields": 6,
                                             "ci95_lo_clamped": False}}
    basis = " ".join(s["basis"] or "" for s in C.for_specimen(r))
    assert "0 of 22" not in basis
    assert "this arm" in basis


# --- a blank is not an answer -------------------------------------------------------
def test_an_unmeasured_detector_effect_is_stated_not_left_blank():
    """28 of 34 specimen-arms have no field imaged both ways. Silence there reads as "no
    detector effect", which is a control that reads nothing."""
    out = texts(C.for_specimen({"n_fields": 5}))
    assert "effect unmeasured" in out
    out2 = texts(C.for_specimen({"n_fields": 5, "detector_sensitivity":
                                 {"cbs_over_etd_median": 2.4,
                                  "n_fields_both_detectors": 10}}))
    assert "effect unmeasured" not in out2 and "Detector alone moves" in out2


# --- the refusal text must not quote this app's retired estimator as its own --------
def test_the_refusal_attributes_the_tortuosity_numbers_to_the_sibling_repo():
    q = [r for r in C.REFUSALS if "ransgranular" in r["question"]][0]
    nt = q["not_this"]
    assert "sibling" in nt.lower() or "SIBLING" in nt
    assert "retired" in nt.lower()
    # And the branching argument must not be asserted with the wrong sign.
    assert "COMMON" in nt or "common" in nt


def test_the_refusal_does_not_make_an_unfalsifiable_negative_claim():
    """It may not claim that no proxy EXISTS -- that is unfalsifiable. It used to say "we
    know of no validated proxy", which was the honest form while nothing had been tested.
    Two proxies have now been built and measured, so the claim is stronger and narrower:
    named routes, with the numbers that killed them and the conditions that would revive
    them. A universal negative would still be wrong."""
    q = [r for r in C.REFUSALS if "ransgranular" in r["question"]][0]
    why = q["why"]
    for forbidden in ("No geometric proxy from a binary mask is validated",
                      "no proxy exists", "cannot be measured", "is impossible"):
        assert forbidden not in why, f"unfalsifiable claim: {forbidden!r}"
    # Falsifiable instead: it names what would change the answer.
    assert "No frame in this corpus reaches that" in why, (
        "the budget must be stated as a corpus fact, which a better corpus could falsify")
    assert any("EBSD" in w for w in q["would_need"])


def test_the_grain_size_is_measured_with_its_method_not_estimated():
    """It used to be a visual estimate of 300-500 px, explicitly labelled as one. It is now
    a measurement with a bracket and a stated scale: 9 um (7-12) on the frames whose FEI
    databar survives, and 140 px (125-165) counted on the unscaled set. The refusal's
    geometric budget rests on this number, so it may not go back to being an eyeball."""
    why = [r for r in C.REFUSALS if "ransgranular" in r["question"]][0]["why"]
    assert "9 um (7-12)" in why or "9 um" in why, "the measured grain diameter is missing"
    assert "42.15 nm/px" in why, "the scale the grain size was measured at is missing"
    assert "300-500" not in why, "the superseded visual estimate is still being quoted"
    # The budget itself: blanking radius as a fraction of a grain.
    assert "0.38-0.57" in why, "the radius-to-grain ratio is missing"


# --- MCL after the geodesic fix ------------------------------------------------------
def test_the_network_share_distinguishes_a_crack_from_a_network():
    """mcl_um used to be max(SkeletonLength_px), the total centreline of a whole branched
    network, under the label "Longest crack". It is now a tip-to-tip geodesic, and the share
    of its own network that path represents is the information that reading was missing."""
    one = C.for_frame(frame(mcl_um=400.0, mcl_share_of_its_network=1.0))
    assert "whole of its region" in texts(one)
    net = C.for_frame(frame(mcl_um=400.0, mcl_share_of_its_network=0.21))
    assert "21% of its network" in texts(net)
    assert any(s["level"] == "warn" for s in net)


def test_a_looping_skeleton_is_hedged():
    out = C.for_frame(frame(mcl_um=400.0, mcl_share_of_its_network=0.4, mcl_has_cycles=True))
    hedges = " ".join(s["hedge"] or "" for s in out)
    assert "shorter way round" in hedges
    out2 = C.for_frame(frame(mcl_um=400.0, mcl_share_of_its_network=0.4, mcl_has_cycles=False))
    assert "shorter way round" not in " ".join(s["hedge"] or "" for s in out2)


def test_no_network_share_statement_without_an_mcl():
    assert "own network" not in texts(C.for_frame(frame(mcl_share_of_its_network=0.3)))


# --- the ingest assertion must reach the reader ------------------------------------
def test_an_inverted_mask_is_the_first_thing_said():
    """measure.py detects inversion; the old layout showed it under the frame title, and
    that element was deleted in the restructure. The warning then had no consumer at all:
    an inverted mask measures the matrix, reports it as crack, and the read-out said "One
    crack holds 100% of the crack area" in green."""
    f = frame(largest_share_of_area=1.0,
              ingest={"warnings": ["75.0% of the frame reads as crack. Crack should be "
                                   "BLACK and the minority phase -- this looks inverted"]})
    out = C.for_frame(f)
    assert "inverted" in texts(out).lower()
    assert out[0]["level"] == "bad", "it must outrank the cheerful statements"


def test_a_greyscale_image_posing_as_a_mask_is_said():
    f = frame(ingest={"warnings": ["not a two-valued mask (9 grey levels) -- it was "
                                   "thresholded at 128"]})
    assert "two-valued" in texts(C.for_frame(f))


def test_a_clean_mask_adds_no_ingest_line():
    assert "inverted" not in texts(C.for_frame(frame(ingest={"warnings": []})))
    assert "inverted" not in texts(C.for_frame(frame()))


# --- constants must match the dataset, not a summary someone wrote ------------------
def test_the_discordance_rate_matches_the_dataset():
    """REGIME_DISCORDANCE shipped as 0.18 because I copied it from a research summary into a
    constant without recomputing it. The dataset gives 4 of 56 double-imaged fields, 7.1%,
    on both SEM arms. It appears in the hedge under every dominance verdict, so a wrong
    value there is a wrong number in front of a researcher."""
    import json
    out = os.path.join(REPO, "analysis", "out", "frames.json")
    if not os.path.exists(out):
        pytest.skip("no dataset built")
    sys.path.insert(0, os.path.join(REPO, "analysis"))
    from specimen_stats import detector_of, field_key
    fr = json.load(open(out, encoding="utf-8"))
    for arm in ("sem/gated", "sem/machine"):
        byf = {}
        for f in fr:
            if f["arm"] != arm:
                continue
            d = detector_of(f["frame"])
            if d:
                byf.setdefault(field_key(f["frame"]), {})[d] = f
        pairs = [v for v in byf.values() if {"CBS", "ETD"} <= set(v)]
        if not pairs:
            continue
        flips = 0
        for v in pairs:
            a = (v["CBS"].get("largest_share_of_area") or 0) >= C.DOMINANT_CUT
            b = (v["ETD"].get("largest_share_of_area") or 0) >= C.DOMINANT_CUT
            if a != b:
                flips += 1
        assert C.REGIME_DISCORDANCE == pytest.approx(flips / len(pairs), abs=0.005), (
            f"{arm}: constant is {C.REGIME_DISCORDANCE:.4f}, dataset gives "
            f"{flips}/{len(pairs)} = {flips / len(pairs):.4f}")


def test_the_detector_calibre_ratios_match_the_dataset():
    """DETECTOR_CALIBRE_RATIOS is stored, not computed live, because for_arm() is handed
    frames.json only. Stored means it can drift from the corpus, which is exactly how
    REGIME_DISCORDANCE shipped wrong, so all four are recomputed here from the region table.

    THE POINT OF THE SIZE-MATCHED PAIR. An earlier version of this test asserted that the
    two naive ratios EXCEED 1, on the reasoning that they were independent calibres moving
    opposite to area/length. They are not independent: both are monotone in region area, so
    area-weighting them on a detector that marks bigger regions manufactures the ratio. That
    test would now be pinning a confounded number in place. What is asserted instead is the
    confound itself -- naive away from unity, size-matched AT unity -- because that pair of
    facts is what licenses the statement's "no instrument here can referee width".
    """
    import json, math, statistics
    from collections import Counter, defaultdict
    fp = os.path.join(REPO, "analysis", "out", "frames.json")
    cp = os.path.join(REPO, "analysis", "out", "cracks.json")
    if not (os.path.exists(fp) and os.path.exists(cp)):
        pytest.skip("no dataset built")
    from specimen_stats import detector_of, field_key
    frames = [f for f in json.load(open(fp, encoding="utf-8"))
              if f.get("arm") == "sem/gated"]
    byframe = defaultdict(list)
    for c in json.load(open(cp, encoding="utf-8")):
        byframe[c["frame"]].append(c)

    pairs = {}
    for f in frames:
        if not f.get("nm_per_px") or not f.get("total_skeleton_length_px"):
            continue
        d = detector_of(f.get("frame", ""))
        if d in ("CBS", "ETD"):
            pairs.setdefault((field_key(f["frame"]), f["nm_per_px"]), {})[d] = f
    ready = [(k, v) for k, v in pairs.items() if len(v) == 2]
    if not ready:
        pytest.skip("no detector pairs")
    modal = Counter(k[1] for k, _ in ready).most_common(1)[0][0]
    both = [v for k, v in ready if k[1] == modal]
    names = [v[d]["frame"] for v in both for d in ("CBS", "ETD")]

    def area_weighted(frame_name, key):
        """Per-field area-weighted mean of a per-region calibre. PER FIELD, because pooling
        regions across fields breaks the pairing -- and it is not cosmetic: pooled, both
        ratios come out BELOW 1, which is part of why neither is a width measurement."""
        rg = [x for x in byframe[frame_name]
              if x.get(key) is not None and x.get("Area_px")]
        if not rg:
            return None
        tot = sum(x["Area_px"] for x in rg)
        return sum(x[key] * x["Area_px"] for x in rg) / tot

    KEYS = (("MaxWidth_px", "max_inscribed_width"),
            ("EllipseMinorAxis_px", "ellipse_minor_axis"))

    # --- the naive figures, and the assertion that they are STILL confounded -------------
    for key, name in KEYS:
        rs = [area_weighted(v["CBS"]["frame"], key) / area_weighted(v["ETD"]["frame"], key)
              for v in both
              if area_weighted(v["CBS"]["frame"], key)
              and area_weighted(v["ETD"]["frame"], key)]
        got = statistics.median(rs)
        assert C.DETECTOR_CALIBRE_RATIOS["naive"][name] == pytest.approx(got, abs=0.02), (
            f"naive {name}: constant is {C.DETECTOR_CALIBRE_RATIOS['naive'][name]}, "
            f"dataset gives {got:.4f} over {len(rs)} pairs at {modal} nm/px")
        # Each instrument must still be size-monotone, or the whole withdrawal is moot.
        xs, ys = [], []
        for n in names:
            for x in byframe[n]:
                if x.get(key) and x.get("Area_px"):
                    xs.append(math.log(x["Area_px"]))
                    ys.append(math.log(x[key]))
        mx, my = statistics.fmean(xs), statistics.fmean(ys)
        slope = (sum((a - mx) * (b - my) for a, b in zip(xs, ys))
                 / sum((a - mx) ** 2 for a in xs))
        assert slope > 0.2, (
            f"{key} is no longer strongly size-monotone (log-log slope {slope:.3f}); the "
            f"size confound is the stated reason the naive ratio was withdrawn")

    # --- size-matched: equal-count area bins, geometric mean of within-bin ratios --------
    for key, name in KEYS:
        allr = [(x["Area_px"], x[key], ("CBS" if "_CBS_" in n else "ETD"))
                for n in names for x in byframe[n]
                if x.get(key) and x.get("Area_px")]
        srt = sorted(a for a, _, _ in allr)
        edges = sorted({srt[min(len(srt) - 1, round(i * len(srt) / 20))]
                        for i in range(21)})
        logs = []
        for lo, hi in zip(edges, edges[1:]):
            c = [w for a, w, d in allr if lo <= a < hi and d == "CBS"]
            e = [w for a, w, d in allr if lo <= a < hi and d == "ETD"]
            if len(c) >= 5 and len(e) >= 5:
                logs.append(math.log(statistics.median(c) / statistics.median(e)))
        assert len(logs) >= 10, f"only {len(logs)} usable area bins for {key}"
        got = math.exp(statistics.fmean(logs))
        assert C.DETECTOR_CALIBRE_RATIOS["size_matched"][name] == pytest.approx(
            got, abs=0.03), (
            f"size-matched {name}: constant is "
            f"{C.DETECTOR_CALIBRE_RATIOS['size_matched'][name]}, dataset gives {got:.4f} "
            f"over {len(logs)} area bins")
        assert abs(math.log(got)) < math.log(1.15), (
            f"size-matched {name} is {got:.4f}, no longer at unity -- the statement says "
            f"size-matched strata put both at unity and would need re-wording")
        naive = C.DETECTOR_CALIBRE_RATIOS["naive"][name]
        assert abs(math.log(naive)) > abs(math.log(got)), (
            f"{name}: the naive ratio {naive} is no further from unity than the "
            f"size-matched {got:.4f}, so there is no confound left to report")


#: Every arm-level finding this app ships on the real corpus, as (arm, phrase that must
#: appear in exactly one statement). NOT a wording test -- each phrase is a fragment chosen
#: to survive re-wording -- it is a CENSUS, and its job is to fail when a finding silently
#: stops being produced.
ARM_FINDINGS_CENSUS = {
    "sem/gated": ["one edge of the raster", "resolution artefact", "E562", "Detector alone",
                  "crack centreline", "cannot be ordered", "no scale", "Operator corrections"],
    "sem/machine": ["one edge of the raster", "resolution artefact", "E562", "Detector alone",
                    "crack centreline", "cannot be ordered", "no scale",
                    "Operator corrections"],
    # "Operator corrections" appeared on both TXM arms the day txm/machine was built. It
    # could not appear before: paired_arm_ratio had no TXM counterpart to pair against, so
    # the corrections block returned None and the statement was absent -- not swallowed, but
    # genuinely unanswerable. The census is the record of that, which is why the entry is
    # added here rather than the count being relaxed.
    "txm": ["one magnification", "Crack width separates", "E562", "cannot be ordered",
            "Operator corrections"],
    # THE MACHINE ARM SAYS THE SAME FIVE THINGS, and that is the point rather than an
    # oversight: the corrections statement is a property of the PAIR, so it is true of
    # whichever side you are looking at, and a reader on the model-only arm needs to know
    # how far the other arm sits from it just as much.
    "txm/machine": ["one magnification", "Crack width separates", "E562",
                    "cannot be ordered", "Operator corrections"],
}


def test_no_arm_level_finding_disappears_silently():
    """for_arm() wraps each of its five finding blocks in a bare `except Exception: pass`.
    That is deliberate -- /api/readout must not 500 because one statement cannot be built
    for one arm -- but it means ANY error inside ~100 lines of pairing, stratification and
    formatting deletes a shipped finding from the card with nothing to show it happened.

    THIS IS THE FAILURE MODE THAT IS WORSE THAN A WRONG NUMBER, because nothing looks
    broken: the card simply has one fewer sentence and still reads as complete. Exactly one
    of the five blocks previously had its existence pinned anywhere (by the width-invariance
    test, as a side effect). A stale positional index, a renamed field in frames.json or a
    changed dict shape would silently retire any of the other four.

    So: census, not wording. Each phrase is a short fragment chosen to survive re-wording,
    and the count is asserted too, so a finding cannot vanish and be replaced unnoticed.
    """
    import json
    fp = os.path.join(REPO, "analysis", "out", "frames.json")
    sp = os.path.join(REPO, "analysis", "out", "specimens.json")
    if not (os.path.exists(fp) and os.path.exists(sp)):
        pytest.skip("no dataset built")
    frames = json.load(open(fp, encoding="utf-8"))
    specs = json.load(open(sp, encoding="utf-8"))
    for arm, phrases in ARM_FINDINGS_CENSUS.items():
        said = C.for_arm([r for r in specs if r.get("arm") == arm],
                         [f for f in frames if f.get("arm") == arm])
        texts = [s["text"] for s in said]
        for phrase in phrases:
            hits = [t for t in texts if phrase in t]
            assert len(hits) == 1, (
                f"{arm}: expected exactly one statement containing {phrase!r}, got "
                f"{len(hits)}. Either a finding was silently swallowed by one of the bare "
                f"`except Exception: pass` blocks in for_arm(), or it was re-worded past "
                f"this fragment. Statements present: {texts}")
        assert len(said) == len(phrases), (
            f"{arm}: the read-out has {len(said)} statements, the census expects "
            f"{len(phrases)}. If a finding was added on purpose, add it to "
            f"ARM_FINDINGS_CENSUS; if one vanished, a swallowed exception is the first "
            f"place to look. Statements present: {texts}")


def test_the_detector_pairing_key_does_not_collide_across_arms():
    """for_arm() takes no arm argument and reads f["arm"] nowhere in its body -- it scopes
    nothing and trusts its caller. The pairing key therefore has to carry the arm itself,
    or two arms' records for one physical field overwrite each other per (field, detector).

    THIS WAS UNOBSERVABLE ON THE REAL CORPUS AND ON THE OLD FIXTURES. All 142 SEM frame
    stems appear in both arms, but the 72 frames behind the 36 modal pairs contain zero of
    the 44 stems that differ between arms, because the paired specimens and the
    operator-corrected ones are disjoint sets -- so gated-only, machine-only and all-arms
    give byte-identical statements. The other fixtures do not differ across arms at all.
    This one does: same field, two arms, deliberately different area and length, with the
    WRONG arm carrying a 1.0 ratio that would drag the median if it won the key.
    """
    import statistics
    frames = []
    for i in range(10):
        # ETD area fraction straddles two stratification bins (0.001-0.005 and
        # 0.005-0.02), because the statement needs at least two strata to fire. The
        # length ratio is 3.0 in BOTH strata, so the headline range is 3.0x to 3.0x and
        # the median is unambiguous.
        etd_af = 0.003 if i < 5 else 0.01
        # sem/gated: CBS is 3x ETD in length. This is the arm being summarised.
        frames.append({"arm": "sem/gated", "specimen": "S", "scale_known": True,
                       "nm_per_px": 51.883, "frame": f"S_CBS_{i:04d}",
                       "crack_area_px": 30000.0, "total_skeleton_length_px": 3000.0,
                       "area_fraction": etd_af * 3})
        frames.append({"arm": "sem/gated", "specimen": "S", "scale_known": True,
                       "nm_per_px": 51.883, "frame": f"S_ETD_{i:04d}",
                       "crack_area_px": 10000.0, "total_skeleton_length_px": 1000.0,
                       "area_fraction": etd_af})
        # sem/machine: SAME field stems, ratio 1.0. If the arm is missing from the key
        # these overwrite the gated records and the statement reports 1.0x.
        frames.append({"arm": "sem/machine", "specimen": "S", "scale_known": True,
                       "nm_per_px": 51.883, "frame": f"S_CBS_{i:04d}",
                       "crack_area_px": 10000.0, "total_skeleton_length_px": 1000.0,
                       "area_fraction": etd_af})
        frames.append({"arm": "sem/machine", "specimen": "S", "scale_known": True,
                       "nm_per_px": 51.883, "frame": f"S_ETD_{i:04d}",
                       "crack_area_px": 10000.0, "total_skeleton_length_px": 1000.0,
                       "area_fraction": etd_af})
    recs = [{"specimen": "S", "arm": "sem/gated"}]

    def ratio(fr):
        st = next((x for x in C.for_arm(recs, fr) if "crack centreline" in x["text"]), None)
        return st

    # Each arm alone is unambiguous: 10 pairs, and the ratio each arm was built with.
    for arm, expect in (("sem/gated", 3.0), ("sem/machine", 1.0)):
        st = ratio([f for f in frames if f["arm"] == arm])
        assert st, f"{arm} alone produced no detector statement"
        assert st["value"] == pytest.approx(expect), f"{arm}: {st['value']} != {expect}"
        assert "10 physical fields" in st["basis"], st["basis"][:90]

    # THE DISCRIMINATING OBSERVABLE IS THE PAIR COUNT. Handed both arms, a correct key
    # yields 20 distinct pairs -- 10 per arm. A key without the arm yields 10, because
    # each (field, detector) is written twice and the last arm read wins. The median then
    # silently becomes that arm's ratio instead of a figure covering both.
    got = ratio(frames)
    assert got, "mixed arms produced no detector statement at all"
    assert "20 physical fields" in got["basis"], (
        f"expected 20 pairs across two arms; a colliding key would report 10. Basis says: "
        f"{got['basis'][:120]!r}")
    # With 10 pairs at 3.0x and 10 at 1.0x, the median sits between them. A collision
    # would pin it to exactly one arm's value, which is the failure this guards.
    assert 1.0 < got["value"] < 3.0, (
        f"mixed-arm median is {got['value']}, i.e. exactly one arm's ratio: the pairing "
        f"key is colliding across arms and one arm's records were overwritten")


def test_the_detector_statement_asserts_no_width_invariance():
    """The statement used to say the detector changes "LENGTH, not width". The width term
    it rested on is area/length, which is log(area) - log(length) by construction and so
    cannot referee width independently. Three phrasings of that claim are forbidden, and
    the statement must still carry the range and the direction that survived."""
    import json
    fp = os.path.join(REPO, "analysis", "out", "frames.json")
    sp = os.path.join(REPO, "analysis", "out", "specimens.json")
    if not (os.path.exists(fp) and os.path.exists(sp)):
        pytest.skip("no dataset built")
    frames = json.load(open(fp, encoding="utf-8"))
    specs = json.load(open(sp, encoding="utf-8"))
    said = C.for_arm([r for r in specs if r["arm"] == "sem/gated"],
                     [f for f in frames if f["arm"] == "sem/gated"])
    st = next((s for s in said if "crack centreline" in s["text"]), None)
    assert st, "the detector-swap statement is gone entirely; it was meant to be re-worded"
    whole = " ".join(filter(None, (st["text"], st["basis"], st["hedge"]))).lower()
    # "move the other way" / "opposite sign" shipped for part of one session as the
    # REPLACEMENT for "not width", quoting 1.26x and 1.67x as independent calibres. They
    # are size proxies, so that phrasing asserted a direction too and is banned with the
    # rest. Anything claiming a width DIRECTION here is wrong, whichever way it points.
    for banned in ("not width", "not in width", "width is unchanged",
                   "same width", "width is not identical",
                   "move the other way", "moves the other way", "opposite sign",
                   "wider", "narrower"):
        assert banned not in whole, (
            f"the width-invariance claim is back as {banned!r}: {whole!r}")
    # It must not offer the between-field comparison as a control either -- at the median
    # length moves more than width there too (0.427 vs 0.369, 165 of 288 pairs).
    assert "control" not in whole, (
        f"the between-field control is back; it does not hold: {whole!r}")
    # And what survived must still be there: a range, not a single multiplier.
    assert "\u00d7 to " in st["text"] or "x to " in st["text"], (
        f"the statement quotes a single multiplier again: {st['text']!r}")
    assert st["level"] != "good", (
        "the detector-swap statement is a positive finding again; what it establishes is "
        "that measured length depends on the detector, which is a limit")


def test_no_fixed_orientation_null_range_is_quoted():
    """The null is per-frame and spans 0.04–1.00 on this corpus; only 31% of frames fall in
    the 0.16–0.29 that was being quoted as though it were the null, and 12 frames exceed 0.29
    while still failing their own. Quoting a fixed range invites exactly that misreading."""
    src = open(os.path.join(REPO, "analysis", "conclusions.py"), encoding="utf-8").read()
    js = open(os.path.join(REPO, "app", "static", "app.js"), encoding="utf-8").read()
    for where, text in (("conclusions.py", src), ("app.js", js)):
        assert "0.16-0.29" not in text and "0.16–0.29" not in text, (
            f"{where} still quotes a fixed null range")


# --- the Buffon cross-check must work without a scale -------------------------------
def test_the_length_trust_check_needs_no_scale():
    """It was computed only inside `if um_px:`, so the app ran two independent estimators
    of one quantity on 63% of frames and neither on the rest -- including every upload,
    which is the only arm a downloaded copy has. The ratio is dimensionless."""
    import numpy as np
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "analysis"))
    from measure import measure_frame

    # NEGATIVE CONTROL: a straight bar, where skeletonisation is reliable and the two
    # estimators should agree, so nothing is said.
    m = np.zeros((400, 400), bool); m[190:200, 20:380] = True
    _, clean = measure_frame(m, "unscaled_probe", "sem")
    assert clean["scale_known"] is False
    assert clean["p21_skeleton_per_px"] and clean["probe"]["p21_buffon_per_px"], (
        "both estimators must exist on an unscaled frame")
    assert "unreliable" not in texts(C.for_frame(clean))

    # POSITIVE CONTROL: a solid block. Its skeleton is a short spine while the intercept
    # count is high, so the estimators must disagree and the app must say so.
    m2 = np.zeros((400, 400), bool); m2[100:300, 100:300] = True
    _, blob = measure_frame(m2, "unscaled_blob", "sem")
    r = blob["probe"]["p21_buffon_per_px"] / blob["p21_skeleton_per_px"]
    assert r > 1.5 or r < 1 / 1.5, f"expected disagreement on a solid block, got {r:.2f}"
    assert "unreliable" in texts(C.for_frame(blob)), (
        "a factor disagreement between two estimators of one quantity must be reported")


def test_the_basis_names_the_unit_it_used():
    """The basis string said mm/mm2 while the values could now be in pixel units."""
    import numpy as np
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "analysis"))
    from measure import measure_frame
    m = np.zeros((400, 400), bool); m[100:300, 100:300] = True
    _, blob = measure_frame(m, "unscaled_blob", "sem")
    line = [x for x in C.for_frame(blob) if "unreliable" in x["text"]][0]
    assert "px/px" in line["basis"] and "mm/mm" not in line["basis"], line["basis"]


def test_the_accuracy_badge_is_never_rendered_without_its_record():
    """The tooltip's advice depends on whether that specimen's fields trend across a patch.
    Called without the record it silently falls back to the generic "more fields" line --
    which is the wrong instruction for exactly the specimens that have a gradient, and the
    read-out already suppresses it for them. A call site that forgets the argument loses
    the correction without any error."""
    import re
    js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "app", "static", "app.js"), encoding="utf-8").read()
    # Check the ARGUMENT IS IN SCOPE, not merely that one was passed. The first version of
    # this guard only looked for a comma, so raBadge(ci, r) inside renderStrip(rec) --
    # where r does not exist -- sailed through it. A guard that cannot see the bug in front
    # of it is not a guard.
    fn, bad = None, []
    for ln in js.splitlines():
        m = re.match(r"(?:async )?function (\w+)\(([^)]*)\)", ln)
        if m:
            fn, params = m.group(1), [x.strip() for x in m.group(2).split(",") if x.strip()]
        if "raBadge(" in ln and "function raBadge" not in ln:
            call = re.search(r"raBadge\(\s*\w+\s*,\s*(\w+)\s*\)", ln)
            if not call:
                bad.append(f"{fn}: no record argument")
                continue
            name = call.group(1)
            # In scope if it is a parameter of the enclosing function, or bound by a map
            # callback inside it, or a module-level name.
            if name not in params and f"({name})" not in js and f"let {name}" not in js:
                bad.append(f"{fn}: passes {name!r}, which is not a parameter of it")
    assert not bad, "raBadge called with an out-of-scope record: " + "; ".join(bad)


def test_the_basis_says_which_fields_the_interval_used():
    """A specimen holding 10 fields whose interval covers 9 must say why, in the basis, at
    the number. "over 9 fields" on a 10-field card reads as a miscount; the reason is that
    E562 fixes the magnification before the fields are counted and the tenth field is an
    overview at a 6.5x coarser pixel."""
    ci = {"pct_relative_accuracy": 93.0, "n_fields": 9, "ci95_lo_clamped": False,
          "nm_per_px": 51.883, "n_fields_off_determination": 1}
    basis = " ".join(s["basis"] or "" for s in
                     C.for_specimen({"n_fields": 10, "area_fraction_ci": ci}))
    assert "over 9 fields at 51.883 nm/px" in basis
    assert "excluding 1 field" in basis and "coarser pixel" in basis
    # A single-magnification specimen says nothing extra -- the clause is not boilerplate.
    clean = dict(ci, n_fields_off_determination=0)
    basis = " ".join(s["basis"] or "" for s in
                     C.for_specimen({"n_fields": 9, "area_fraction_ci": clean}))
    assert "over 9 fields." in basis and "excluding" not in basis


def test_every_refusal_carries_a_short_label():
    """The summary line used to derive its labels from the questions with a chain of
    regexes, one per refusal, so a new refusal leaked its whole question onto a line the
    user reads before deciding to expand it. The label lives on the record instead."""
    for r in C.REFUSALS:
        assert r.get("label"), r["question"]
        assert len(r["label"].split()) <= 3, r["label"]
        assert "?" not in r["label"]


# --- the engine must be able to say what IS the case, not only what is not ----------
def test_the_arm_readout_leads_with_an_established_finding():
    """Every statement in this engine was originally written to fire on FAILURE, so the
    read-out could only ever say what was unknown: "cannot be ordered", "not determinable",
    "no relationship", "0 of 9 reach the target". Each was true and the whole was useless,
    and the owner said so.

    Two results survived adversarial verification and belong at the top: the detector
    changes crack LENGTH rather than width (36 same-field pairs at one magnification, with
    a same-detector control showing the difference routes through width instead), and the
    crack area survives a 6x coarser pixel (against a null where 1-2 px synthetic cracks
    lose everything). This asserts the engine still states them, and states them first.
    """
    import json, os
    from collections import defaultdict
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fp = os.path.join(repo, "analysis", "out", "frames.json")
    sp = os.path.join(repo, "analysis", "out", "specimens.json")
    if not (os.path.exists(fp) and os.path.exists(sp)):
        pytest.skip("no dataset built")
    frames = json.load(open(fp, encoding="utf-8"))
    specs = json.load(open(sp, encoding="utf-8"))

    said = C.for_arm([r for r in specs if r["arm"] == "sem/gated"],
                     [f for f in frames if f["arm"] == "sem/gated"])
    assert said, "the gated arm produced no statements at all"
    good = [s for s in said if s["level"] == "good"]
    assert good, ("the arm read-out contains no established finding -- every statement is "
                  "a caveat or a refusal, which is the state the owner rejected")
    assert said[0]["level"] == "good", (
        f"the read-out opens with {said[0]['level']!r}: {said[0]['text']!r}. Findings lead, "
        f"limits follow.")
    # Each one still carries its null and the condition under which it misleads.
    for s in good:
        assert s["basis"] and len(s["basis"].split()) > 12, s["text"]
        assert s["hedge"], f"a positive finding with no hedge: {s['text']!r}"


def test_a_calibrated_finding_is_not_asserted_for_an_arm_it_was_not_measured_on():
    """The coarse-pixel calibration was measured on SEM fields at 51.883 nm/px. Firing it
    for txm -- a different instrument at 29.24 nm/px -- would assert a result for an arm it
    was never tested on. I made exactly that mistake writing it."""
    import json, os
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fp = os.path.join(repo, "analysis", "out", "frames.json")
    sp = os.path.join(repo, "analysis", "out", "specimens.json")
    if not (os.path.exists(fp) and os.path.exists(sp)):
        pytest.skip("no dataset built")
    frames = json.load(open(fp, encoding="utf-8"))
    specs = json.load(open(sp, encoding="utf-8"))
    txm = C.for_arm([r for r in specs if r["arm"] == "txm"],
                    [f for f in frames if f["arm"] == "txm"])
    joined = " ".join(s["text"] for s in txm)
    assert "resolution artefact" not in joined, (
        "the coarse-pixel calibration is being asserted for txm, which it was not "
        "measured on")
    # The phrase this used to look for ("LENGTH, not width") was withdrawn from the
    # statement, which would have left this guard passing while measuring nothing. Key on
    # what the statement says NOW, and on the arm-independent fact that txm has no
    # detector pair at all, so the line cannot be rebuilt around a new phrasing either.
    assert "crack centreline" not in joined, (
        "the detector finding is being asserted for txm, which has no detector pair")
    assert "CBS" not in joined and "ETD" not in joined, (
        f"a detector is named in the txm read-out, which has no detector pair: {joined!r}")


# --- THE OTHER ARM GETS FINDINGS TOO ---------------------------------------------------
def _txm_like(n_spec=4, per=4, nm=29.24, widths=(0.34, 0.45, 1.21, 0.55)):
    """A single-magnification corpus with a real between-specimen width difference."""
    out = []
    for i in range(n_spec):
        for j in range(per):
            w = widths[i % len(widths)] * (1 + 0.06 * j)
            L = 1000.0
            out.append({"arm": "txm", "specimen": f"S{i}", "frame": f"S{i}_f{j}",
                        "scale_known": True, "nm_per_px": nm,
                        "total_length_um": L, "crack_area_um2": w * L,
                        "area_fraction": 0.02 + 0.01 * i, "n_cracks_measured": 9})
    return out


def test_a_single_magnification_corpus_gets_the_scale_finding():
    """The txm arm shipped with TWO statements, both negative, and no finding at all -- its
    pane said "Nothing is established" while sem showed three. Every arm finding was gated
    on something only the SEM corpus has (a CBS/ETD swap, a 3x3 stage raster, one
    calibrated magnification). The asymmetry was in the engine, not the microscope."""
    fr = _txm_like()
    sts = C.for_arm([{"specimen": f"S{i}"} for i in range(4)], fr)
    good = [s for s in sts if s["level"] == "good"]
    assert good, "a fully scaled single-magnification arm must establish something"
    assert any("one magnification" in s["text"] for s in good), [s["text"] for s in good]


def test_the_scale_finding_is_guarded_on_the_data_not_the_arm_name():
    """`arm == "txm"` would be a lie the moment a second single-magnification corpus loads,
    and it would hide that this is a claim about scale coverage, not about a machine."""
    fr = _txm_like()
    for f in fr:
        f["arm"] = "some/other/corpus"
    sts = C.for_arm([{"specimen": f"S{i}"} for i in range(4)], fr)
    assert any("one magnification" in s["text"] for s in sts if s["level"] == "good")


def test_one_unscaled_frame_withdraws_the_scale_finding():
    fr = _txm_like()
    fr[0]["scale_known"] = False
    sts = C.for_arm([{"specimen": f"S{i}"} for i in range(4)], fr)
    assert not any("one magnification" in s["text"] for s in sts), (
        "'every frame is scaled' must not survive a frame that is not")


def test_the_width_finding_refuses_to_pool_across_magnifications():
    """Nothing in the first version required one magnification. It was correct for txm by
    accident -- all 71 frames sit at 29.24 nm/px -- and would have compared widths across a
    249x scale range on any corpus that did not."""
    fr = _txm_like()
    # Give one specimen a different scale, with a width that would swing the spread.
    for f in fr:
        if f["specimen"] == "S2":
            f["nm_per_px"] = 337.2396
            f["crack_area_um2"] = f["total_length_um"] * 9.0
    sts = C.for_arm([{"specimen": f"S{i}"} for i in range(4)], fr)
    w = [s for s in sts if "width separates" in s["text"]]
    for s in w:
        assert "9.0" not in s["basis"], "an off-magnification specimen entered the spread"
        assert "29.24 nm/px" in s["basis"], s["basis"]


def test_the_width_finding_is_a_separation_not_a_ranking():
    """The app's own established limit is that these specimens cannot be ordered: each is
    one imaged site, so material difference and site difference are one variance
    component."""
    sts = C.for_arm([{"specimen": f"S{i}"} for i in range(4)], _txm_like())
    w = [s for s in sts if "width separates" in s["text"]]
    assert w, "the width finding did not fire on a corpus built to trigger it"
    for s in w:
        assert "not a ranking" in (s["hedge"] or ""), s["hedge"]
        for banned in ("highest", "lowest", "worst", "best", "most cracked"):
            assert banned not in s["text"].lower()


def test_no_between_specimen_width_difference_means_no_finding():
    """A separation claim has to be able to fail, or it is decoration."""
    fr = _txm_like(widths=(0.45, 0.45, 0.45, 0.45))
    for i, f in enumerate(fr):          # wide within, identical between
        f["crack_area_um2"] = f["total_length_um"] * (0.2 + 0.5 * (i % 4))
    sts = C.for_arm([{"specimen": f"S{i}"} for i in range(4)], fr)
    assert not any("width separates" in s["text"] for s in sts), (
        "width must not 'separate' specimens whose medians are identical")


def test_the_refusal_does_not_contradict_itself_about_scale():
    """It said "0 of the 62 labelled frames has a recoverable nm/px" and then, 71
    characters later, "Ten ... DO carry a legible FEI databar ... so 42.15, 28.16 and 13.49
    nm/px". Both are true under a distinction the sentence did not carry -- the APP cannot
    extract a scale from any of them, a human can read the databar off ten -- so quoting
    either sentence quoted a claim the other appeared to refute. This card exists to be
    quoted."""
    w = [r for r in C.REFUSALS if "ransgranular" in r["question"]][0]["why"]
    assert "0 of the 62 labelled frames has a recoverable nm/px" not in w
    i = w.index("0 of the 62")
    claim = w[max(0, i - 120):i + 120]
    assert "app" in claim.lower() or "extract" in claim.lower(), (
        f"the nm/px claim does not say whose recovery it is about: {claim!r}")
    assert "EXTRACTION PATH" in w, "the distinction is not stated where it is needed"


def test_the_scale_spread_is_the_ratio_of_the_quantity_it_names():
    """"the spread across all ten is 31x" followed a list of nm/px values, but 31x is
    2590/82.9 -- the ratio of the two HFW values. In nm/px, the quantity the sentence is
    about, it is 843.1/13.49 = 62.5x. They differ because that frame is 3072 px wide and
    the others 6144, so a reader quoting 31x was a factor of two out."""
    w = [r for r in C.REFUSALS if "ransgranular" in r["question"]][0]["why"]
    assert "62.5x" in w
    assert "is 31x rather than 3.1x" not in w, "the HFW ratio is still given as the nm/px spread"
    # The numbers it rests on must still be present and must still produce 62.5.
    for v in ("843.1", "13.49"):
        assert v in w
    assert round(843.1 / 13.49, 1) == 62.5
