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
    assert "preferentially oriented" in texts(yes).lower()
    no = C.for_frame(frame(rose_beats_null=False, rose_R=0.24, rose_R_null95=0.31))
    assert "not resolvably oriented" in texts(no).lower()
    assert "preferentially" not in texts(no).lower()


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
    assert "No physical scale" in texts(out)
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
    assert "Detector moves this" in texts(out)
    assert any(s["level"] == "bad" for s in out), "a 2.45x instrument effect is not 'info'"


def test_a_detector_ratio_near_one_is_not_reported():
    r = {"n_fields": 10, "detector_sensitivity":
         {"cbs_over_etd_median": 1.05, "n_fields_both_detectors": 10}}
    assert "Detector moves" not in texts(C.for_specimen(r))


def test_no_corrections_is_distinguished_from_no_effect():
    none = {"n_fields": 5, "arm_sensitivity": {"n_frames_corrected": 0, "n_paired_frames": 20}}
    assert "unreviewed" in texts(C.for_specimen(none))
    some = {"n_fields": 5, "arm_sensitivity": {"n_frames_corrected": 11, "n_paired_frames": 13,
                                               "gated_over_machine_where_corrected": 1.435}}
    assert "Operator corrections change" in texts(C.for_specimen(some))


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
