#!/usr/bin/env python3
"""The E562 interval, checked against answers worked out independently of the code."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "analysis"))
import specimen_stats as S   # noqa: E402


def test_ci_matches_the_textbook_formula():
    v = [0.10, 0.12, 0.08, 0.14, 0.11]
    c = S._ci(v)
    a = np.array(v)
    from scipy import stats
    want = stats.t.ppf(0.975, 4) * a.std(ddof=1) / np.sqrt(5)
    assert c["n_fields"] == 5
    assert c["mean"] == pytest.approx(a.mean(), abs=1e-9)
    assert c["ci95_halfwidth"] == pytest.approx(want, rel=1e-4)
    assert c["ci95_lo"] == pytest.approx(a.mean() - want, rel=1e-4)
    # Rounded to one decimal because it is a displayed percentage, so the tolerance is
    # half the last digit rather than a relative one.
    assert c["pct_relative_accuracy"] == pytest.approx(100 * want / a.mean(), abs=0.05)


def test_t_not_normal():
    """At n=3 the normal approximation understates the interval by a third. Using 1.96 here
    would quote a precision the data does not have."""
    assert S._t95(3) == pytest.approx(4.3027, rel=1e-3)
    assert S._t95(3) / 1.96 > 2.1


def test_below_three_fields_there_is_no_interval():
    assert S._ci([0.1, 0.2]) is None
    assert S._ci([0.1]) is None
    assert S._ci([]) is None


def test_lower_bound_cannot_go_negative():
    """An area fraction is non-negative. A wide interval on a small mean must clamp, not
    report a negative fraction."""
    c = S._ci([0.001, 0.05, 0.002])
    assert c["ci95_lo"] == 0.0


def test_a_field_imaged_twice_counts_once():
    """The failure this module exists to prevent: 142 frames are 86 fields, and counting
    frames would put up to sqrt(2) of spurious precision into every interval."""
    frames = [{"frame": "MAR_AmbB_AS_CBS_0001", "area_fraction": 0.04},
              {"frame": "MAR_AmbB_AS_ETD_0001", "area_fraction": 0.02},
              {"frame": "MAR_AmbB_AS_CBS_0002", "area_fraction": 0.06},
              {"frame": "MAR_AmbB_AS_ETD_0002", "area_fraction": 0.04},
              {"frame": "MAR_AmbB_AS_CBS_0003", "area_fraction": 0.08},
              {"frame": "MAR_AmbB_AS_ETD_0003", "area_fraction": 0.06}]
    vals = S.collapse_to_fields(frames, "area_fraction")
    assert vals == [0.03, 0.05, 0.07], "replicates must be averaged, not listed"
    naive = S._ci([f["area_fraction"] for f in frames])
    real = S._ci(vals)
    assert real["n_fields"] == 3 and naive["n_fields"] == 6
    assert real["ci95_halfwidth"] > naive["ci95_halfwidth"], (
        "treating replicates as fields must not produce a TIGHTER interval")


def test_field_key_strips_only_the_detector():
    assert S.field_key("MAR_AmbB_AS_CBS_0001") == "MAR_AmbB_AS_0001"
    assert S.field_key("260622_316_H_b2_back_CBS_01") == "260622_316_H_b2_back_01"
    assert S.detector_of("MAR_AmbB_AS_ETD_0001") == "ETD"
    # No detector token: the frame is its own field, never collapsed into a neighbour.
    assert S.field_key("Average_mosaic_260618_B2_2_1") == "Average_mosaic_260618_B2_2_1"
    assert S.detector_of("Average_mosaic_260618_B2_2_1") is None


def test_detector_sensitivity_uses_only_fields_imaged_both_ways():
    frames = [{"frame": "X_CBS_0001", "area_fraction": 0.04},
              {"frame": "X_ETD_0001", "area_fraction": 0.02},
              {"frame": "X_CBS_0002", "area_fraction": 0.90}]   # no ETD partner
    d = S.detector_sensitivity(frames)
    assert d["n_fields_both_detectors"] == 1
    assert d["cbs_over_etd_median"] == 2.0, "the unpaired CBS frame must not enter the ratio"


def test_arm_ratio_is_paired_on_the_frame():
    by_arm = {
        "sem/gated": [{"frame": "A", "specimen": "S", "area_fraction": 0.10},
                      {"frame": "B", "specimen": "S", "area_fraction": 0.20},
                      {"frame": "C", "specimen": "S", "area_fraction": 0.90}],
        "sem/machine": [{"frame": "A", "specimen": "S", "area_fraction": 0.05},
                        {"frame": "B", "specimen": "S", "area_fraction": 0.10}],
    }
    r = S.paired_arm_ratio(by_arm, "S")
    assert r["n_paired_frames"] == 2, "frame C has no machine partner"
    assert r["gated_over_machine_median"] == 2.0


def test_additive_totals_are_summed_over_fields_not_frames():
    """Area analysed and total crack length are SUMS. Summing them over frames counts a
    field imaged through two detectors twice -- it reported 2.650 mm2 analysed for a
    specimen holding 10 fields of ~0.13 mm2 each, and 67 mm of crack for 33 mm of crack.
    Collapsing handled the mean and not the totals, which is the same mistake one line
    apart."""
    frames = []
    for i in (1, 2):
        for d in ("CBS", "ETD"):
            frames.append({"frame": f"S_{d}_000{i}", "area_fraction": 0.02,
                           "n_cracks_measured": 1, "crack_density_px_per_Mpx": 1.0,
                           "scale_known": True, "area_analysed_mm2": 0.10,
                           "tcl_um": 1000.0})
    r = S.summarise("sem/gated", "S", frames)
    assert r["n_frames"] == 4 and r["n_fields"] == 2
    assert r["area_analysed_mm2"] == pytest.approx(0.20), "4 frames, but only 2 fields of material"
    assert r["tcl_um_total"] == pytest.approx(2000.0)
    assert r["n_fields_scaled"] == 2


def test_a_marked_copy_keeps_its_source_specimen_and_its_interval():
    """A re-marked field of MAR_H_AS is still a field of MAR_H_AS. Filing marked copies
    under the "uploaded" catch-all threw away the grouping that makes an E562 interval mean
    anything and put them in a bucket with unrelated images."""
    frames = [{"frame": f"MAR_H_AS_CBS_000{i}_marked", "area_fraction": v,
               "n_cracks_measured": 5, "crack_density_px_per_Mpx": 1.0,
               "scale_known": True}
              for i, v in enumerate((0.03, 0.035, 0.04, 0.045), 1)]
    r = S.summarise("uploads", "MAR_H_AS", frames)
    assert r["area_fraction_ci"] is not None, (
        "fields of one real specimen deserve an interval even in the uploads arm")
    assert r["no_ci_reason"] is None


def test_uploads_get_no_e562_interval():
    """Every uploaded frame is filed under the pseudo-specimen "uploaded", so four
    unrelated images produced a 95% CI with a method string citing between-FIELD variance.
    They are four different pieces of metal. The shipped value was +/-156%, and this is the
    only path a user who is not the author ever takes."""
    frames = [{"frame": f"img{i}", "area_fraction": v, "n_cracks_measured": 5,
               "crack_density_px_per_Mpx": 1.0, "scale_known": False}
              for i, v in enumerate((0.01, 0.05, 0.09, 0.2), 1)]
    up = S.summarise("uploads", "uploaded", frames)
    assert up["area_fraction_ci"] is None, "an interval over unrelated uploads is fabricated"
    assert up["no_ci_reason"], "it must say why, not just omit"
    # The same four values under a real specimen still get one -- the gate is the arm.
    real = S.summarise("sem/gated", "S1", frames)
    assert real["area_fraction_ci"] is not None


def test_the_stage_gradient_is_computed_over_fields_not_frames():
    """Two detectors imaging one place report the SAME stage coordinates, so passing raw
    frames doubles every point. All eight shipped records read n=20 for 10 fields, making
    every p-value up to 27x too small."""
    frames = []
    for i in range(1, 9):
        for det in ("CBS", "ETD"):
            frames.append({"frame": f"S_{det}_000{i}", "area_fraction": 0.01 * i,
                           "n_cracks_measured": 5, "crack_density_px_per_Mpx": 1.0,
                           "scale_known": False})
    kept = S._one_frame_per_field(frames)
    assert len(kept) == 8, f"16 frames are 8 fields, got {len(kept)}"
    assert len({S.field_key(f["frame"]) for f in kept}) == 8


# --- ONE MAGNIFICATION PER DETERMINATION ------------------------------------------------
def _raster(n=9, nm=51.883, af=0.02, start=1, spec="MAR_X"):
    """n fields at one scale, area fractions spread a little so s is non-zero."""
    return [{"frame": f"{spec}_CBS_{i:04d}", "area_fraction": af + 0.001 * i,
             "n_cracks_measured": 5, "crack_density_px_per_Mpx": 1.0,
             "scale_known": True, "nm_per_px": nm}
            for i in range(start, start + n)]


def test_a_coarser_field_is_not_a_replicate_of_the_fine_ones():
    """The failure: nine fields at 51.883 nm/px plus one overview at 337.2396 were averaged
    into one E562 mean. A 6.5x coarser pixel is a 6.5x coarser minimum resolvable width, so
    the two measure different populations -- and the overview's field of view is 10.6x a
    fine field's while taking 1/10 of the weight, which E562's equal-area fields forbid on
    its own."""
    frames = _raster() + [{"frame": "MAR_X_CBS_0010", "area_fraction": 0.09,
                           "n_cracks_measured": 5, "crack_density_px_per_Mpx": 1.0,
                           "scale_known": True, "nm_per_px": 337.2396}]
    r = S.summarise("sem/gated", "MAR_X", frames)
    ci = r["area_fraction_ci"]
    assert r["n_fields"] == 10, "the coarse field is still a field of this specimen"
    assert ci["n_fields"] == 9, "but it is not in the determination"
    assert ci["nm_per_px"] == pytest.approx(51.883)
    assert ci["n_fields_off_determination"] == 1
    assert ci["mean"] == pytest.approx(np.mean([f["area_fraction"] for f in frames[:9]]))
    assert "337.2396" in ci["magnification_note"]


def test_the_excluded_field_is_reported_not_silently_dropped():
    """Dropping it from the mean is right; dropping it from the record is how a reader
    stops being able to audit the interval. Both scales are on the card, with the detection
    limit each implies, and single-magnification specimens carry the list too -- an
    assertion recorded only when it fails cannot distinguish clean from unexamined."""
    frames = _raster() + [{"frame": "MAR_X_CBS_0010", "area_fraction": 0.09,
                           "n_cracks_measured": 5, "crack_density_px_per_Mpx": 1.0,
                           "scale_known": True, "nm_per_px": 337.2396}]
    g = S.summarise("sem/gated", "MAR_X", frames)["magnification_groups"]
    assert [x["nm_per_px"] for x in g] == [51.883, 337.2396], "determination first"
    assert [x["n_fields"] for x in g] == [9, 1]
    assert [x["in_determination"] for x in g] == [True, False]
    assert g[0]["min_resolvable_width_um"] == pytest.approx(0.0519, abs=1e-4)
    assert g[1]["min_resolvable_width_um"] == pytest.approx(0.3372, abs=1e-4)
    assert g[1]["area_fraction_mean"] == pytest.approx(0.09), (
        "the excluded value must still be readable, not just counted")
    # A clean specimen still says so.
    solo = S.summarise("sem/gated", "MAR_X", _raster())["magnification_groups"]
    assert len(solo) == 1 and solo[0]["in_determination"]


def test_one_magnification_and_unscaled_specimens_are_untouched():
    """Every 316 specimen has no recoverable nm/px at all. None is a real group, not a
    missing one, so those intervals must come out byte-identical to the old pooled code."""
    scaled = _raster(n=5)
    unscaled = [dict(f, nm_per_px=None, scale_known=False) for f in scaled]
    for frames in (scaled, unscaled):
        r = S.summarise("sem/gated", "S", frames)
        assert r["area_fraction_ci"]["n_fields"] == 5
        assert r["area_fraction_ci"]["n_fields_off_determination"] == 0
        assert "magnification_note" not in r["area_fraction_ci"]
        assert r["area_fraction_ci"]["ci95_halfwidth"] == pytest.approx(
            S._ci([f["area_fraction"] for f in frames])["ci95_halfwidth"])
        assert r["no_ci_reason"] is None


def test_a_scale_recorded_slightly_differently_is_still_one_determination():
    """The corpus holds both 51.883 and 52.0 nm/px -- a 1.002x difference that is a
    rounding convention, not a magnification change. Splitting on exact equality would
    refuse an interval over fields that are plainly the same determination."""
    frames = _raster(n=3) + _raster(n=3, nm=52.0, start=4)
    r = S.summarise("sem/gated", "S", frames)
    assert len(r["magnification_groups"]) == 1
    assert r["area_fraction_ci"]["n_fields"] == 6
    assert S.SAME_MAGNIFICATION < 337.2396 / 51.883, (
        "the tolerance must still split the real 6.5x pair")


def test_no_interval_when_no_magnification_group_reaches_three():
    """The refusal, and it must not read as "too few images". This specimen has five
    fields; what it lacks is three fields at ANY ONE scale, and a card saying "only 2
    fields" about a five-field specimen sends the reader to acquire the wrong thing."""
    frames = _raster(n=2) + _raster(n=3, nm=337.2396, start=3)
    r = S.summarise("sem/gated", "S", frames)
    assert r["n_fields"] == 5
    # The largest group is the 337 one at n=3, so THIS specimen does get an interval...
    assert r["area_fraction_ci"]["n_fields"] == 3
    # ...but drop it to two and nothing reaches three.
    frames = _raster(n=2) + _raster(n=2, nm=337.2396, start=3)
    r = S.summarise("sem/gated", "S", frames)
    assert r["n_fields"] == 4
    assert r["area_fraction_ci"] is None
    assert "split across magnifications" in r["no_ci_reason"]
    assert "51.883" in r["no_ci_reason"] and "337.2396" in r["no_ci_reason"]
    # Genuinely-too-few is still its own, different, silence.
    assert S.summarise("sem/gated", "S", _raster(n=2))["no_ci_reason"] is None


def test_the_gradient_is_computed_over_the_determination_too():
    """stage.py's rank correlation had the same defect: one of its ten points was measured
    at a 6.5x coarser detection limit, and that field's view spans much of the raster so it
    has no position comparable to the others'."""
    frames = _raster(n=6) + [{"frame": "MAR_X_CBS_0007", "area_fraction": 0.09,
                              "n_cracks_measured": 5, "crack_density_px_per_Mpx": 1.0,
                              "scale_known": True, "nm_per_px": 337.2396}]
    seen = {}

    import stage
    real = stage.gradient
    stage.gradient = lambda fs, **kw: seen.setdefault("n", len(fs))
    try:
        S.summarise("sem/gated", "MAR_X", frames)
    finally:
        stage.gradient = real
    assert seen["n"] == 6, f"the 337 nm/px field must not reach stage.gradient, got {seen}"


def test_the_corpus_values_this_rule_was_written_for():
    """Pinned against the real dataset, because the rule was found in it and a synthetic
    fixture cannot catch the day the ingest starts filing the overview differently.

    117.9% was not the app's worst SEM number -- MAR_Amb_AS is 138.0% and has no
    recoverable scale at all -- but it was the worst among the specimens this rule touches,
    and it was substantially one 337.2396 nm/px frame."""
    import json
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(here, "analysis", "out", "frames.json")
    if not os.path.exists(out):
        pytest.skip("no dataset built")
    fr = json.load(open(out))
    want = {"MAR_AmbB_AS": 62.0, "MAR_AmbB_HIP": 84.2, "MAR_H_AS": 49.1, "MAR_H_HIP": 93.0}
    for arm in ("sem/gated", "sem/machine"):
        for spec, ra in want.items():
            frames = [f for f in fr if f["arm"] == arm and f["specimen"] == spec]
            if not frames:
                continue
            r = S.summarise(arm, spec, frames)
            ci = r["area_fraction_ci"]
            assert ci["n_fields"] == 9, f"{arm} {spec}: 10 fields, 9 at the modal scale"
            assert ci["n_fields_off_determination"] == 1
            assert ci["nm_per_px"] == pytest.approx(51.883)
            assert ci["pct_relative_accuracy"] == pytest.approx(ra, abs=0.05), (
                f"{arm} {spec}: pooling the 337.2396 nm/px overview back in would give "
                f"53.0/117.9/42.4/81.7")
            # The overview is still on the record, with its own value.
            off = [g for g in r["magnification_groups"] if not g["in_determination"]]
            assert len(off) == 1 and off[0]["nm_per_px"] == pytest.approx(337.2396)


# --- every physical aggregate is over the determination's FIELDS --------------------
#: The six the specimen card renders, plus the three additive/count ones beside them.
PHYSICAL = ("p10_min_per_mm", "p10_mean_per_mm", "p21_skeleton_mm_per_mm2",
            "p21_buffon_mm_per_mm2", "p20_per_mm2", "mcl_um",
            "largest_network_centreline_um", "tcl_um_total", "area_analysed_mm2")


def test_n_fields_scaled_never_exceeds_the_interval_it_sits_beside():
    """The card printed "1.325218 mm² over 10 fields" two rows above "95% CI …, 9 fields at
    51.883 nm/px". Violated on exactly 8 of 34 shipped records before this."""
    import json, os
    from collections import defaultdict
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(repo, "analysis", "out", "frames.json")
    if not os.path.exists(out):
        pytest.skip("no dataset built")     # CI has no corpus; the synthetic case below covers the rule
    fr = json.load(open(out))
    rows = fr["records"] if isinstance(fr, dict) else fr
    g = defaultdict(list)
    for f in rows:
        g[(f.get("specimen"), f.get("arm"))].append(f)
    bad = []
    for (sp, arm), fs in g.items():
        r = S.summarise(arm, sp, fs)
        ci = r.get("area_fraction_ci")
        if ci and r.get("n_fields_scaled", 0) > ci["n_fields"]:
            bad.append(f"{sp}/{arm}: {r['n_fields_scaled']} scaled fields vs {ci['n_fields']} in the interval")
    assert not bad, "\n  ".join([""] + bad)


def test_the_physical_aggregates_use_determination_fields_not_frames():
    """Two errors that compound: a median over FRAMES lets a field imaged through two
    detectors vote twice (and CBS reads 2.29x ETD, so it is not a tie), and pooling every
    magnification puts a 337.2396 nm/px overview in the same median as nine fields at
    51.883. Recomputed independently here rather than trusting the record."""
    import numpy as np
    det = [
        {"frame": "MAR_X_AS_CBS_0001", "scale_known": True, "n_cracks_measured": 5, "area_fraction": 0.01,
         "crack_density_px_per_Mpx": 1.0, "nm_per_px": 50.0,
         "p20_per_mm2": 100.0, "mcl_um": 10.0, "area_analysed_mm2": 0.1, "tcl_um": 500.0,
         "p21_skeleton_mm_per_mm2": 1.0, "largest_network_centreline_um": 20.0,
         "probe": {"p10_min_per_mm": 1.0, "p10_mean_per_mm": 2.0, "p21_buffon_mm_per_mm2": 1.0}},
        # SAME physical field, other detector. Must not count twice.
        {"frame": "MAR_X_AS_ETD_0001", "scale_known": True, "n_cracks_measured": 5, "area_fraction": 0.01,
         "crack_density_px_per_Mpx": 1.0, "nm_per_px": 50.0,
         "p20_per_mm2": 200.0, "mcl_um": 20.0, "area_analysed_mm2": 0.1, "tcl_um": 700.0,
         "p21_skeleton_mm_per_mm2": 3.0, "largest_network_centreline_um": 40.0,
         "probe": {"p10_min_per_mm": 3.0, "p10_mean_per_mm": 4.0, "p21_buffon_mm_per_mm2": 3.0}},
        {"frame": "MAR_X_AS_CBS_0002", "scale_known": True, "n_cracks_measured": 5, "area_fraction": 0.01,
         "crack_density_px_per_Mpx": 1.0, "nm_per_px": 50.0,
         "p20_per_mm2": 300.0, "mcl_um": 30.0, "area_analysed_mm2": 0.1, "tcl_um": 900.0,
         "p21_skeleton_mm_per_mm2": 5.0, "largest_network_centreline_um": 60.0,
         "probe": {"p10_min_per_mm": 5.0, "p10_mean_per_mm": 6.0, "p21_buffon_mm_per_mm2": 5.0}},
        {"frame": "MAR_X_AS_CBS_0003", "scale_known": True, "n_cracks_measured": 5, "area_fraction": 0.01,
         "crack_density_px_per_Mpx": 1.0, "nm_per_px": 50.0,
         "p20_per_mm2": 400.0, "mcl_um": 40.0, "area_analysed_mm2": 0.1, "tcl_um": 1100.0,
         "p21_skeleton_mm_per_mm2": 7.0, "largest_network_centreline_um": 80.0,
         "probe": {"p10_min_per_mm": 7.0, "p10_mean_per_mm": 8.0, "p21_buffon_mm_per_mm2": 7.0}},
    ]
    # A WILDLY DIFFERENT OVERVIEW at a 10x coarser pixel. Off the determination, so it must
    # not reach any of the nine fields above.
    overview = {"frame": "MAR_X_AS_CBS_0010", "scale_known": True, "n_cracks_measured": 5, "area_fraction": 0.01,
         "crack_density_px_per_Mpx": 1.0, "nm_per_px": 500.0,
                "p20_per_mm2": 99999.0, "mcl_um": 9999.0, "area_analysed_mm2": 9.9,
                "tcl_um": 99999.0, "p21_skeleton_mm_per_mm2": 999.0,
                "largest_network_centreline_um": 9999.0,
                "probe": {"p10_min_per_mm": 999.0, "p10_mean_per_mm": 999.0,
                          "p21_buffon_mm_per_mm2": 999.0}}

    with_ov = S.summarise("sem/gated", "MAR_X_AS", det + [overview])
    without = S.summarise("sem/gated", "MAR_X_AS", det)
    for k in PHYSICAL:
        assert with_ov[k] == without[k], (
            f"{k} moved when a 10x-coarser overview was added: "
            f"{without[k]} -> {with_ov[k]}. It is pooling magnifications.")

    # And the detector replicate is averaged, not counted twice: field 0001 contributes
    # (100+200)/2 = 150, so the three field values are 150, 300, 400 -> median 300.
    assert with_ov["p20_per_mm2"] == 300.0, with_ov["p20_per_mm2"]
    assert with_ov["p10_min_per_mm"] == 5.0, with_ov["p10_min_per_mm"]   # (1+3)/2, 5, 7
    assert with_ov["n_fields_scaled"] == 3
    # Three fields of 0.1 mm2, NOT four frames and NOT the 9.9 overview.
    assert abs(with_ov["area_analysed_mm2"] - 0.3) < 1e-9, with_ov["area_analysed_mm2"]
    # The excluded material is stated, not silently dropped -- and never rendered.
    assert abs(with_ov["area_off_determination_mm2"] - 9.9) < 1e-9


def test_no_physical_aggregate_is_written_as_a_median_over_raw_frames():
    """A source guard, because the defect recurred three times in this one function and
    each time the new field simply copied the shape of the one above it."""
    import os, re
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "analysis", "specimen_stats.py")).read()
    body = src[src.index("def summarise("):]
    offenders = re.findall(r'"([a-z0-9_]+)":\s*_median\(\[[^\]]*for f in (?:scaled|frames)\]',
                           body, re.S)
    assert not offenders, (
        "computed as a median over frames rather than over determination fields: "
        + ", ".join(offenders) + " -- use collapse_to_fields(det_scaled, ...)")
