#!/usr/bin/env python3
"""The E562 interval, checked against answers worked out independently of the code."""
import io
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "analysis"))
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


def _real_raster(specimen, arm="sem/gated", nm=51.883):
    """The nine fine fields of one real raster, both detectors, or None without the table.

    Real frame names, because stage.position reads a metadata table keyed on them and
    returns None for anything else -- which is how the per-detector test below came to
    assert nothing at all.
    """
    import json
    path = os.path.join(REPO, "analysis", "out", "frames.json")
    if not os.path.exists(path):
        return None
    try:
        import stage
    except Exception:
        return None
    rows = json.load(io.open(path, encoding="utf-8"))
    out = [f for f in rows
           if f.get("arm") == arm and f.get("frame", "").startswith(specimen + "_")
           and (f.get("nm_per_px") or 0) and abs(f["nm_per_px"] - nm) < 1
           and stage.position(f["frame"])]
    return out if len(out) >= 2 * stage.MIN_FIELDS else None


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


def test_the_gradient_averages_the_detectors_instead_of_picking_one():
    """The test above counted fields and passed for the wrong code for two revisions.

    `_one_frame_per_field` keeps the alphabetically first frame per field, and the detector
    token sorts CBS before ETD on every pair in this corpus -- so it is a CBS-only selector
    with a neutral-sounding name, and CBS reads 2.29x ETD on the same physical field. Eight
    shipped records carried a CBS-only rank correlation beside an interval computed from a
    real detector mean. Counting is not enough: this asserts on the VALUE.
    """
    frames = []
    for i in range(1, 10):
        frames.append({"frame": f"S_CBS_{i:04d}", "area_fraction": 0.100,
                       "n_cracks_measured": 5, "crack_density_px_per_Mpx": 1.0,
                       "scale_known": False})
        frames.append({"frame": f"S_ETD_{i:04d}", "area_fraction": 0.200,
                       "n_cracks_measured": 5, "crack_density_px_per_Mpx": 1.0,
                       "scale_known": False})
    recs = S._field_records(frames)
    assert len(recs) == 9, f"18 frames are 9 fields, got {len(recs)}"
    for r in recs:
        assert abs(r["area_fraction"] - 0.150) < 1e-9, (
            "the field value must be the MEAN of the two detectors, not either one; "
            f"got {r['area_fraction']}")
        assert r["n_detectors"] == 2, "a field's detector count travels with its mean"
    # THE HAZARD, NOT THE ACCIDENT. An earlier version asserted this set equals {"CBS"},
    # which pins the alphabetical accident rather than the thing that makes the selector
    # unsafe: that it collapses a two-detector field to ONE detector's number. Renaming a
    # detector would have failed that assertion while leaving the bug untouched.
    picked = S._one_frame_per_field(frames)
    dets = {S.detector_of(f["frame"]) for f in picked}
    assert len(dets) == 1, (
        "_one_frame_per_field is documented as unsafe for a measured value because it "
        f"represents every field by a single detector; it chose {sorted(dets)}, so either "
        "the function changed or that documentation is now wrong")
    only = next(iter(dets))
    assert all(abs(f["area_fraction"] - (0.100 if only == "CBS" else 0.200)) < 1e-9
               for f in picked), (
        "the selected frames must carry that one detector's value, which is what makes "
        "passing them to a statistic a detector choice")


def test_the_gradient_is_also_reported_per_detector():
    """A trend computed from a detector mean must not read as detector-independent.

    THE FIRST VERSION OF THIS TEST ASSERTED NOTHING, and it was written in the same commit
    that replaced a test for passing against the wrong code. It built frames named
    S_CBS_0001..S_ETD_0009 and bailed out on `if out is None: return`. Stage positions come
    from a metadata table keyed on REAL frame names, so `stage.position("S_CBS_0001")` is
    None, so `_gradient_by_detector` returned None, so the early return fired on every run
    and the three assertions below it were unreachable. Its own docstring pointed at "the
    real-corpus assertion" in a test that did not exist.

    Two changes: real frame names, so the code path actually engages; and an explicit skip
    naming the missing table, so a checkout without the SEM repo reports a SKIP rather than
    a silent pass.
    """
    frames = _real_raster("MAR_H_AS")
    if frames is None:
        pytest.skip("no stage-coordinate table in this checkout (needs the SEM repo)")
    out = S._gradient_by_detector(frames)
    assert out is not None, "positions resolved, so both channels must produce a gradient"
    assert set(out) == {"CBS", "ETD"}, f"both channels must appear, got {sorted(out)}"
    for det, g in out.items():
        assert g["n_frames_with_position"] == 9, (
            f"{det} must be 9 fields, not 18 frames; got {g['n_frames_with_position']}")
        for key in ("axis", "spearman_rho", "p_value"):
            assert key in g, f"{det} is missing {key}, so the pair cannot be read"
    # The point of publishing the pair is that the two channels can DISAGREE. Assert that
    # the mean is not simply one of them -- otherwise the per-detector report is decoration.
    mean_g = S._gradient(S._field_records(frames))
    assert mean_g is not None
    per = {d: g["spearman_rho"] for d, g in out.items()}
    assert len(set(per.values()) | {mean_g["spearman_rho"]}) >= 2, (
        "every channel and the mean agree exactly, so this fixture cannot show the "
        f"disagreement the pair exists to expose: {per} against {mean_g['spearman_rho']}")


def test_no_file_asserts_that_more_patches_would_narrow_the_interval():
    """n_patches is 1 on the eight positioned arms and None on the other 26, never 2.

    So "more patches would narrow it" has no supporting measurement anywhere in this corpus.
    It was asserted in three places -- stage.py's note, conclusions.py's hedge and app.js's
    tooltip -- by the same code that exists to refuse unsupported assertions.

    PARSED, NOT GREPPED, and the first version of this test did grep. A raw file scan has to
    exempt the paragraphs that RECORD the removal, because they quote the sentence they are
    removing -- and an exemption keyed on nearby words ("used to", "removed", "untested") is
    an escape hatch a future edit walks straight through. This project has already recorded
    four source scans that matched their own explanatory prose. So: for Python, walk the AST
    and test only string literals that are NOT docstrings, which is where a user-facing claim
    can live and where a comment or a docstring cannot reach. For app.js, which carries no
    explanatory prose on this subject, test the file text with no exemption at all.
    """
    import ast
    PHRASE = "more patches would"
    bad = []
    for rel in ("analysis/stage.py", "analysis/conclusions.py", "analysis/specimen_stats.py"):
        path = os.path.join(REPO, rel)
        tree = ast.parse(io.open(path, encoding="utf-8").read(), filename=rel)
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                body = getattr(node, "body", None)
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    docstrings.add(id(body[0].value))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docstrings
                    and PHRASE in node.value.lower()):
                bad.append(f"{rel}:{node.lineno} (string literal)")
    for rel in ("app/static/app.js", "app/templates/index.html"):
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            continue
        text = io.open(path, encoding="utf-8").read().lower()
        if PHRASE in text:
            bad.append(f"{rel} (file text)")
    assert not bad, (
        "these assert a remedy this corpus has never measured -- n_patches never reaches 2: "
        + ", ".join(bad))


def test_the_patch_count_that_makes_that_remedy_untestable():
    """The measurement behind the test above, so it cannot rot into a style rule.

    If a future corpus ever carries two patches on one specimen, this fails and the sentence
    becomes assertable -- which is the point. A prose ban with no measurement attached is the
    same kind of unsupported rule it was written to remove.
    """
    import json
    path = os.path.join(REPO, "analysis", "out", "specimens.json")
    if not os.path.exists(path):
        pytest.skip("no measured output in this checkout")
    rows = json.load(io.open(path, encoding="utf-8"))
    vals = [r.get("n_patches") for r in rows]
    assert vals, "specimens.json carried no records"
    seen = sorted({v for v in vals if v is not None})
    assert seen and max(seen) < 2, (
        "a specimen now has two or more imaged patches, so between-patch variance is "
        f"measurable and the remedy may be stated: n_patches values {seen}")


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
    calls = []

    import stage
    real = stage.gradient

    def _spy(fs, **kw):
        calls.append(len(fs))
        # A stub has to return the real shape. This one returned an int, so the day a
        # second caller appeared it raised inside the module instead of failing an
        # assertion here -- and a stub that cannot be called twice is a stub that pins the
        # number of callers, which is not what this test is about.
        return {"n_frames_with_position": len(fs), "axis": "stage_y",
                "spearman_rho": 0.0, "p_value": 1.0, "field_max_min_ratio": 1.0,
                "significant": False}

    stage.gradient = _spy
    try:
        S.summarise("sem/gated", "MAR_X", frames)
    finally:
        stage.gradient = real
    assert calls, "stage.gradient was never called"
    assert calls[0] == 6, f"the 337 nm/px field must not reach stage.gradient, got {calls}"
    assert all(n <= 6 for n in calls), (
        f"no call may see the excluded overview field, got {calls}")


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
    fr = json.load(open(out, encoding="utf-8"))
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
    fr = json.load(open(out, encoding="utf-8"))
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
                            "analysis", "specimen_stats.py"), encoding="utf-8").read()
    body = src[src.index("def summarise("):]
    offenders = re.findall(r'"([a-z0-9_]+)":\s*_median\(\[[^\]]*for f in (?:scaled|frames)\]',
                           body, re.S)
    assert not offenders, (
        "computed as a median over frames rather than over determination fields: "
        + ", ".join(offenders) + " -- use collapse_to_fields(det_scaled, ...)")

# --- THE TXM ARM PAIR -------------------------------------------------------------------
def test_pair_for_knows_every_arm_and_refuses_the_ones_with_no_counterpart():
    """The gated/machine pair is DECLARED, not inferred from the arm name.

    It has to be: the TXM gated arm is called "txm", not "txm/gated", because renaming it
    would invalidate every stored record and every saved mode in a user's config. A prefix
    rule would therefore pair "txm" with nothing and silently drop the comparison -- which
    is the state this corpus was in until the model-only export existed.
    """
    assert S.pair_for("sem/gated") == ("sem/gated", "sem/machine")
    assert S.pair_for("sem/machine") == ("sem/gated", "sem/machine")
    assert S.pair_for("txm") == ("txm", "txm/machine")
    assert S.pair_for("txm/machine") == ("txm", "txm/machine")
    # An arm with no counterpart must return None rather than a half-pair: paired_arm_ratio
    # is called with *pair, so a one-element answer would raise inside the endpoint.
    assert S.pair_for("uploads") is None
    assert S.pair_for("nonsense") is None
    for arm, pair in ((a, S.pair_for(a)) for a in ("sem/gated", "txm", "uploads")):
        assert pair is None or len(pair) == 2, f"{arm} -> {pair}"


def test_the_two_txm_trees_are_not_the_same_directory():
    """THE MISTAKE THIS GUARDS is pointing both TXM arms at one tree.

    Both arms read `<stem>/<stem>_crack_mask.png`, so the layouts are identical and a
    resolver that returned the gated tree for both would produce a complete, plausible
    second arm whose every number equalled the first. Nothing downstream would complain:
    the frames would measure, the comparison would read exactly 1.000x on every specimen,
    and "the operator changed nothing" is a sentence the card is willing to print.
    """
    from app import paths as P
    gated, machine = P.txm_export(), P.txm_export_machine()
    if not (gated and machine):
        pytest.skip("no TXM export configured in this checkout")
    assert os.path.realpath(gated) != os.path.realpath(machine), (
        "both TXM arms resolve to the same directory, so the model-only arm is a copy of "
        f"the gated one: {gated}")


def test_the_machine_arm_carries_no_operator_input():
    """The model-only masks must DIFFER from the gated ones, and differ in the right places.

    Measured on the real export rather than a fixture, because the property at issue is a
    property of the two trees. The operator touched 65 of 71 frames; on those the two masks
    must disagree, and on the untouched remainder they must agree exactly -- any other
    pattern means the corrections were applied to the wrong arm, or to both, or to neither.
    """
    import json
    fp = os.path.join(REPO, "analysis", "out", "frames.json")
    if not os.path.exists(fp):
        pytest.skip("no dataset built")
    rows = json.load(io.open(fp, encoding="utf-8"))
    g = {f["frame"]: f for f in rows if f["arm"] == "txm"}
    m = {f["frame"]: f for f in rows if f["arm"] == "txm/machine"}
    if not (g and m):
        pytest.skip("the TXM arms are not both measured in this checkout")
    both = sorted(set(g) & set(m))
    assert len(both) == len(g) == len(m), (
        f"the two TXM arms cover different frames: {len(g)} gated, {len(m)} machine, "
        f"{len(both)} shared")
    same = [k for k in both if g[k]["crack_area_px"] == m[k]["crack_area_px"]]
    assert len(same) < len(both), (
        "every frame has identical crack area on both TXM arms, so either the model-only "
        "export was built with corrections applied or both arms read one tree")
    # And it must not be the degenerate opposite either -- a machine arm that disagrees
    # everywhere, including on frames with no strokes at all, would mean the two trees were
    # built from different models or different thresholds rather than differing only in
    # whether the human was applied.
    assert same, (
        "no frame agrees between the two TXM arms. They should differ ONLY where the "
        "operator drew, so total disagreement means the two exports differ in something "
        "else -- model, threshold, pruning or tightening.")
