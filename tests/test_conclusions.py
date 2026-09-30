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
                           "app", "static", "app.js")).read()
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
    frames = json.load(open(fp))
    specs = json.load(open(sp))

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
    frames = json.load(open(fp))
    specs = json.load(open(sp))
    txm = C.for_arm([r for r in specs if r["arm"] == "txm"],
                    [f for f in frames if f["arm"] == "txm"])
    joined = " ".join(s["text"] for s in txm)
    assert "resolution artefact" not in joined, (
        "the coarse-pixel calibration is being asserted for txm, which it was not "
        "measured on")
    assert "LENGTH, not width" not in joined, (
        "the detector finding is being asserted for txm, which has no detector pair")


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
