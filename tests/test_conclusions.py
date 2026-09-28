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
                rose_R=None, rose_R_null95=None, rose_theta_deg=None)
    base.update(kw)
    return base


def texts(sts):
    return " || ".join(s["text"] for s in sts)


# --- the word cap is enforced, not aspirational ------------------------------------
def test_every_statement_is_within_the_word_cap():
    for f in (frame(), frame(largest_share_of_area=0.97), frame(scale_known=False),
              frame(arm="txm"), frame(n_cracks_measured=0),
              frame(rose_beats_null=True, rose_R=0.6, rose_R_null95=0.2, rose_theta_deg=32),
              frame(rose_beats_null=False, rose_R=0.2, rose_R_null95=0.3),
              frame(censored_share_by_length=0.9, mcl_um=500, mcl_um_uncensored_only=100),
              frame(p21_skeleton_mm_per_mm2=40, probe={"p21_buffon_mm_per_mm2": 18})):
        for s in C.for_frame(f):
            assert len(s["text"].split()) <= 15, s["text"]
            assert s["basis"], f"no basis for {s['text']!r}"


# --- orientation: the whole point of the null ---------------------------------------
def test_orientation_is_claimed_only_when_it_beats_its_null():
    yes = C.for_frame(frame(rose_beats_null=True, rose_R=0.61, rose_R_null95=0.22,
                            rose_theta_deg=32.4))
    assert "oriented near" in texts(yes).lower()
    no = C.for_frame(frame(rose_beats_null=False, rose_R=0.24, rose_R_null95=0.31))
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
def test_relative_accuracy_failure_is_stated_as_unrankable():
    r = {"area_fraction_ci": {"pct_relative_accuracy": 138.0, "n_fields": 6,
                              "ci95_lo_clamped": True}, "n_fields": 6}
    out = texts(C.for_specimen(r))
    assert "too coarse to rank" in out
    assert "below zero" in out


def test_a_good_interval_makes_no_complaint():
    r = {"area_fraction_ci": {"pct_relative_accuracy": 6.0, "n_fields": 12,
                              "ci95_lo_clamped": False}, "n_fields": 12}
    assert "too coarse" not in texts(C.for_specimen(r))


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
def test_the_mode_question_is_answered_with_a_shopping_list():
    q = [r for r in C.REFUSALS if "ransgranular" in r["question"]][0]
    assert "Not determinable" in q["answer"]
    assert any("EBSD" in w for w in q["would_need"])
    assert q["not_this"] and "ortuosity" in q["not_this"]
    # It must name the corpus-specific reason, not just wave at "needs grain data".
    assert "enclosed islands" in q["why"].lower() or "islands it encloses" in q["why"].lower()


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
        "axis": "stage_y", "n_frames_with_position": 20, "n_stage_rows": 10,
        "row_mean_ratio": 5.3, "note": "E562 presumes fields placed over a surface."}


def test_a_spatial_gradient_is_stated():
    r = {"n_fields": 10, "stage_gradient": GRAD}
    out = texts(C.for_specimen(r))
    assert "not independent" in out and "5×" in out


def test_a_gradient_suppresses_the_measure_more_fields_advice():
    """More tiles in the SAME patch cannot narrow an interval that is tracking a trend, so
    the standard remedy becomes wrong advice exactly when the gradient fires."""
    ci = {"pct_relative_accuracy": 81.7, "n_fields": 10, "ci95_lo_clamped": False}
    flat = C.for_specimen({"n_fields": 10, "area_fraction_ci": ci})
    grad = C.for_specimen({"n_fields": 10, "area_fraction_ci": ci, "stage_gradient": GRAD})
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
    q = [r for r in C.REFUSALS if "ransgranular" in r["question"]][0]
    assert "No geometric proxy from a binary mask is validated" not in q["why"]
    assert "know of no validated proxy" in q["why"]


def test_the_grain_size_is_labelled_an_estimate():
    q = [r for r in C.REFUSALS if "ransgranular" in r["question"]][0]
    assert "visual estimate" in q["why"] or "by eye" in q["why"]


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
    fr = json.load(open(out))
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


def test_no_fixed_orientation_null_range_is_quoted():
    """The null is per-frame and spans 0.04–1.00 on this corpus; only 31% of frames fall in
    the 0.16–0.29 that was being quoted as though it were the null, and 12 frames exceed 0.29
    while still failing their own. Quoting a fixed range invites exactly that misreading."""
    src = open(os.path.join(REPO, "analysis", "conclusions.py")).read()
    js = open(os.path.join(REPO, "app", "static", "app.js")).read()
    for where, text in (("conclusions.py", src), ("app.js", js)):
        assert "0.16-0.29" not in text and "0.16–0.29" not in text, (
            f"{where} still quotes a fixed null range")
