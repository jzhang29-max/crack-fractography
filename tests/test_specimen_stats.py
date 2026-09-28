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
