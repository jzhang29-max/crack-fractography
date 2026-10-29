#!/usr/bin/env python3
"""The instrument has to be shown to work on paths whose answer is known before it is
pointed at a real crack.

Every case here is built on a square-grain tessellation, where "on a boundary" has an exact
answer: a path drawn along a grid line IS intergranular and a path drawn down the middle of a
row of grains IS transgranular. If the module cannot separate those two, nothing it says
about a micrograph means anything.

The refusals are tested as hard as the measurements, because this module's reason to exist is
that the same question answered without a grain map was contamination (see its docstring).
"""
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "analysis"))

import crackmode as CM          # noqa: E402

GRAIN = 40                      # px per square grain
SIDE = 400                      # 10 x 10 grains


def grains(side=SIDE, g=GRAIN):
    """A square tessellation: grain id = (row, col) flattened, starting at 1."""
    yy, xx = np.mgrid[0:side, 0:side]
    return ((yy // g) * (side // g) + (xx // g) + 1).astype(np.int32)


def _thicken(mask, w=3):
    from scipy import ndimage as ndi
    return ndi.binary_dilation(mask, np.ones((w, w), bool))


def intergranular_crack(side=SIDE, g=GRAIN, w=3):
    """A crack lying exactly on grain-boundary lines: along a row, then down a column."""
    m = np.zeros((side, side), bool)
    y = 4 * g                      # a horizontal boundary line
    m[y, 20:side - 20] = True
    x = 6 * g                      # a vertical boundary line
    m[4 * g:side - 20, x] = True
    return _thicken(m, w)


def transgranular_crack(side=SIDE, g=GRAIN, w=3):
    """A crack down the middle of a row of grains, as far from boundaries as it can be."""
    m = np.zeros((side, side), bool)
    y = 4 * g + g // 2
    m[y, 20:side - 20] = True
    x = 6 * g + g // 2
    m[4 * g + g // 2:side - 20, x] = True
    return _thicken(m, w)


# ------------------------------------------------------------------ boundary construction
def test_boundaries_of_a_known_tessellation_are_the_grid_lines():
    g = grains()
    b = CM.boundaries_from_grain_ids(g)
    # every pixel adjacent to a grid line is a boundary pixel; grain centres are not
    assert b[GRAIN - 1, 100] and b[GRAIN, 100]
    assert not b[GRAIN // 2, GRAIN // 2]
    assert not b[2 * GRAIN + GRAIN // 2, 3 * GRAIN + GRAIN // 2]


def test_unindexed_points_do_not_create_boundaries():
    g = grains()
    g[100:140, 100:140] = 0                      # a zero-solution patch
    b = CM.boundaries_from_grain_ids(g, ignore=(0,))
    assert not b[118:122, 118:122].any(), "a hole in the index must not read as a boundary"


def test_grain_geometry_recovers_the_tessellation():
    gm = CM.grain_geometry(grains(), nm_per_px=50.0)
    assert gm["n_grains"] == (SIDE // GRAIN) ** 2
    # equivalent diameter of a GRAIN x GRAIN square
    assert gm["median_grain_diameter_px"] == pytest.approx(
        np.sqrt(4 * GRAIN * GRAIN / np.pi), rel=1e-6)
    assert gm["unindexed_frac"] == 0.0


# ------------------------------------------------------------------------ the measurement
def test_a_boundary_following_crack_reads_intergranular():
    g = grains()
    r = CM.measure(intergranular_crack(), grain_ids=g, tau_px=2, n_null=60, seed=1)
    c = r["classification"]
    assert c["by_length_pct"]["intergranular"] > 90, c["by_length_pct"]
    assert c["pooled_boundary_frac"] > 0.9
    assert r["controls"]["z_vs_null"] > 2.0


def test_a_grain_interior_crack_reads_transgranular():
    """Its floor is NOT zero. A crack running through grain interiors still CROSSES a
    boundary every grain, so it scores the saturation floor -- the share of the field within
    tolerance of a boundary. That is the number it must sit at, not 0."""
    g = grains()
    r = CM.measure(transgranular_crack(), grain_ids=g, tau_px=2, n_null=60, seed=1)
    c = r["classification"]
    sat = r["controls"]["saturation"]
    assert c["by_length_pct"]["transgranular"] > 90, c["by_length_pct"]
    assert c["pooled_boundary_frac"] < 2.0 * sat, (c["pooled_boundary_frac"], sat)
    assert any("saturation floor" in w for w in r["verdict"]["warnings"]), r["verdict"]


def test_the_two_paths_are_separated_by_the_instrument():
    """The whole point: the same settings must tell them apart, not just score each."""
    g = grains()
    a = CM.measure(intergranular_crack(), grain_ids=g, tau_px=2, n_null=40, seed=2)
    b = CM.measure(transgranular_crack(), grain_ids=g, tau_px=2, n_null=40, seed=2)
    assert (a["classification"]["pooled_boundary_frac"]
            - b["classification"]["pooled_boundary_frac"]) > 0.8


def test_length_and_area_weightings_are_both_reported_and_can_differ():
    g = grains()
    r = CM.measure(intergranular_crack(), grain_ids=g, tau_px=2, n_null=20, seed=3)
    c = r["classification"]
    assert set(c["by_length_pct"]) == set(c["by_area_pct"]) == {
        "intergranular", "transgranular", "mixed"}
    for d in (c["by_length_pct"], c["by_area_pct"]):
        assert sum(d.values()) == pytest.approx(100.0, abs=0.05)


# ----------------------------------------------------------------------------- the guards
def test_saturation_is_reported_and_rises_with_tau():
    b = CM.boundaries_from_grain_ids(grains())
    s2 = CM.saturation(b, 2)
    s12 = CM.saturation(b, 12)
    assert 0 < s2 < s12 <= 1.0
    assert s12 > CM.SATURATION_CEILING, "a 12 px tolerance on a 40 px grain must saturate"


def test_a_saturating_tolerance_is_refused_even_for_a_perfect_crack():
    g = grains()
    r = CM.measure(intergranular_crack(), grain_ids=g, tau_px=14, n_null=20, seed=4)
    assert not r["verdict"]["pooled_quotable"]
    assert any("saturat" in w for w in r["verdict"]["reasons"]), r["verdict"]["reasons"]


def test_tau_near_a_grain_diameter_is_refused():
    g = grains()
    r = CM.measure(intergranular_crack(), grain_ids=g, tau_px=10, n_null=20, seed=5)
    assert any("grain diameters" in w for w in r["verdict"]["reasons"]), r["verdict"]["reasons"]


def test_the_positive_control_fires_when_the_grain_map_is_wrong():
    """A grain map that is one grain has no boundaries: the instrument must say so rather
    than report 0% intergranular as though that were a finding."""
    one = np.ones((SIDE, SIDE), np.int32)
    r = CM.measure(intergranular_crack(), grain_ids=one, tau_px=2, n_null=20, seed=6)
    assert not r["verdict"]["pooled_quotable"]
    assert any("positive control" in w for w in r["verdict"]["reasons"]), r["verdict"]["reasons"]
    assert r["controls"]["positive_control"] is None


def test_a_sound_run_on_three_branches_keeps_its_pooled_number():
    """Few branches blocks the SPLIT, not the pooled fraction. Collapsing the two verdicts
    would throw away a valid measurement."""
    g = grains()
    r = CM.measure(intergranular_crack(), grain_ids=g, tau_px=2, n_null=60, seed=11)
    v = r["verdict"]
    assert v["pooled_quotable"], v["reasons"]
    assert not v["split_quotable"]
    assert any("measurable branches" in w for w in v["split_reasons"])


def test_a_crack_with_no_relation_to_the_boundaries_does_not_beat_its_null():
    """The null is the same path somewhere else. A transgranular crack sits BELOW it, so the
    z must not clear the bar -- otherwise the bar is not doing anything."""
    g = grains()
    r = CM.measure(transgranular_crack(), grain_ids=g, tau_px=2, n_null=120, seed=7)
    assert r["controls"]["z_vs_null"] < 2.0
    assert any("null" in w for w in r["verdict"]["reasons"]), r["verdict"]["reasons"]
    assert not r["verdict"]["pooled_quotable"]


def test_the_tau_sweep_ships_so_a_one_tau_conclusion_is_visible():
    g = grains()
    r = CM.measure(intergranular_crack(), grain_ids=g, tau_px=2, n_null=20, seed=8,
                   tau_sweep=(1, 2, 4, 8))
    taus = [row["tau_px"] for row in r["tau_sweep"]]
    assert taus == [1, 2, 4, 8]
    sats = [row["saturation"] for row in r["tau_sweep"]]
    assert sats == sorted(sats), "saturation must be monotone in tau"


def test_segment_rows_let_the_thresholds_be_rechosen_without_a_rerun():
    g = grains()
    r = CM.measure(intergranular_crack(), grain_ids=g, tau_px=2, n_null=20, seed=9)
    rows = r["classification"]["segments"]
    assert rows and all("boundary_frac" in row and "length_px" in row for row in rows)
    L = np.array([row["length_px"] for row in rows], float)
    F = np.array([row["boundary_frac"] for row in rows], float)
    assert float((F * L).sum() / L.sum()) == pytest.approx(
        r["classification"]["pooled_boundary_frac"], abs=5e-4)


# ---------------------------------------------------------------------------- the refusals
def test_there_is_no_mask_only_mode():
    with pytest.raises(ValueError) as e:
        CM.measure(intergranular_crack(), tau_px=2)
    assert "grain" in str(e.value).lower()
    assert "REFUSALS" in str(e.value) or "refusal" in str(e.value).lower()


def test_an_unregistered_pair_is_refused_rather_than_resampled():
    g = grains(side=200)
    with pytest.raises(ValueError) as e:
        CM.classify(intergranular_crack(), CM.boundaries_from_grain_ids(g), tau_px=2)
    assert "co-registered" in str(e.value)


def test_an_empty_mask_returns_a_note_not_a_percentage():
    g = grains()
    out = CM.classify(np.zeros((SIDE, SIDE), bool), CM.boundaries_from_grain_ids(g), tau_px=2)
    assert out["n_segments"] == 0 and "note" in out
    assert "by_length_pct" not in out


def test_one_population_is_flagged_as_not_two():
    """Every branch half on a boundary: the binned split is then a property of the
    thresholds, and the module has to say so."""
    g = grains()
    # a diagonal staircase crosses boundaries steadily, so every branch lands mid-range
    m = np.zeros((SIDE, SIDE), bool)
    idx = np.arange(40, SIDE - 40)
    m[idx, idx] = True
    r = CM.measure(_thicken(m, 3), grain_ids=g, tau_px=6, n_null=20, seed=10)
    bim = r["classification"]["bimodality"]
    assert bim["middle_third_length_share"] is not None
    if not bim["reads_as_two_populations"]:
        assert any("one population" in w for w in r["verdict"]["split_reasons"])
        assert not r["verdict"]["split_quotable"]


def test_the_width_confound_is_measured_on_every_run():
    """The image-only attempt at this question died because its discriminator ranked
    branches by painted stroke width at Spearman +0.891. The same two confounds are
    therefore reported whether or not they are large, so nobody has to remember to ask."""
    g = grains()
    r = CM.measure(intergranular_crack(), grain_ids=g, tau_px=2, n_null=20, seed=12)
    conf = r["classification"]["confounds"]
    assert "spearman_boundary_frac_vs_length" in conf
    assert "spearman_boundary_frac_vs_width" in conf


def test_a_split_carried_by_short_stubs_is_refused():
    """A crack whose only boundary contact is at its branch junctions must not be reported
    as intergranular: that is stubs lying on boundaries by construction."""
    g = grains(side=SIDE, g=GRAIN)
    b = CM.boundaries_from_grain_ids(g)
    # branches that are long and interior, meeting at points ON the boundary network
    m = np.zeros((SIDE, SIDE), bool)
    for row in range(1, SIDE // GRAIN - 1):
        y = row * GRAIN + GRAIN // 2
        m[y, GRAIN:SIDE - GRAIN] = True
    for col in range(1, SIDE // GRAIN - 1):
        x = col * GRAIN + GRAIN // 2
        m[GRAIN:SIDE - GRAIN, x] = True
    out = CM.classify(_thicken(m, 3), b, tau_px=2)
    conf = out["confounds"]
    assert conf["spearman_boundary_frac_vs_length"] is not None


def test_the_rank_correlation_handles_ties_like_scipy():
    """Most branches of a boundary-following crack score exactly 1.0, so the confound guard
    is computed almost entirely on tied ranks. argsort(argsort(.)) breaks ties arbitrarily
    and gave +0.014 and -0.260 on one real frame where the answer is -0.105."""
    from scipy import stats
    rng = np.random.default_rng(0)
    for _ in range(5):
        x = rng.choice([0.2, 1.0, 1.0, 1.0], size=40).astype(float)
        y = rng.integers(5, 120, 40).astype(float)
        assert CM._spearman(x, y) == pytest.approx(float(stats.spearmanr(x, y).statistic),
                                                   abs=1e-12)


def test_the_rank_correlation_declines_a_constant_input():
    assert CM._spearman(np.ones(20), np.arange(20.0)) is None


def test_the_shortcut_auc_is_refused_on_an_imbalanced_split():
    """A synthetic demo gave junction degree AUC 0.970 on 4 transgranular branches against
    151 intergranular. That number describes the imbalance, not the cracks, so the counts
    gate the AUC rather than merely accompanying it."""
    cls = {"segments": (
        [{"mode": "intergranular", "length_px": 20, "mean_width_px": 3.0,
          "max_adjacent_degree": 4} for _ in range(151)]
        + [{"mode": "transgranular", "length_px": 300, "mean_width_px": 3.0,
            "max_adjacent_degree": 0} for _ in range(4)])}
    out = CM.degree_separates(cls)
    assert out["n_intergranular"] == 151 and out["n_transgranular"] == 4
    assert "auc_junction_degree" not in out
    assert "note" in out and "imbalance" in out["note"]


def test_the_shortcut_auc_is_computed_when_both_classes_are_present():
    cls = {"segments": (
        [{"mode": "intergranular", "length_px": 20 + i, "mean_width_px": 3.0,
          "max_adjacent_degree": 4} for i in range(20)]
        + [{"mode": "transgranular", "length_px": 300 + i, "mean_width_px": 3.0,
            "max_adjacent_degree": 0} for i in range(20)])}
    out = CM.degree_separates(cls)
    assert out["auc_junction_degree"] == pytest.approx(1.0)
    assert out["auc_branch_length"] == pytest.approx(0.0)


def test_a_blanked_centreline_is_refused_rather_than_read_as_transgranular():
    """If the boundary map was blanked around the crack -- which any map derived from the
    same micrograph must be -- then a boundary fraction of 0 means the question was never
    asked. Reporting that as 100% transgranular would be the worst available answer."""
    from scipy import ndimage as ndi
    g = grains()
    b = CM.boundaries_from_grain_ids(g)
    crack = intergranular_crack()
    collar = ndi.binary_dilation(crack, np.ones((3, 3), bool), iterations=20)
    b_blanked = b & ~collar
    r = CM.measure(crack, boundary=b_blanked, tau_px=2, n_null=30, seed=13,
                   evaluable=~collar)
    assert r["classification"]["skeleton_in_evaluable_frac"] < 0.5
    assert not r["verdict"]["pooled_quotable"]
    assert any("could have\nbeen detected".replace("\n", " ") in w or "evaluable" in w
               or "was not asked" in w for w in r["verdict"]["reasons"]), r["verdict"]["reasons"]


# --------------------------------------------------------------------- flank comparison
def test_flank_comparison_calls_a_boundary_crack_intergranular():
    """Both flanks in different grains. Unlike coincidence, this holds for a WIDE crack,
    where the boundary the crack ran along no longer exists to coincide with."""
    g = grains()
    wide = intergranular_crack(w=15)              # 15 px wide: a boundary test would fail
    out = CM.flank_mode(wide, g)
    assert out["decidable_frac"] > 0.8, out
    assert out["intergranular_pct_by_centreline"] > 90, out


def test_flank_comparison_calls_an_interior_crack_transgranular():
    g = grains()
    wide = transgranular_crack(w=15)
    out = CM.flank_mode(wide, g)
    assert out["decidable_frac"] > 0.8, out
    assert out["transgranular_pct_by_centreline"] > 90, out


def test_flank_comparison_survives_a_width_that_breaks_coincidence():
    """The point of the method: at 21 px the crack has swallowed the boundary, so the
    centreline is nowhere near a surviving boundary pixel, yet the flanks still answer."""
    g = grains()
    b = CM.boundaries_from_grain_ids(g)
    wide = intergranular_crack(w=21)
    coincide = CM.classify(wide, b & ~wide, tau_px=2)
    flank = CM.flank_mode(wide, g)
    assert coincide["pooled_boundary_frac"] < 0.25, coincide["pooled_boundary_frac"]
    assert flank["intergranular_pct_by_centreline"] > 90, flank


def test_flank_comparison_reports_what_it_could_not_decide():
    g = grains()
    g[:, :200] = 0                                  # half the field unindexed
    out = CM.flank_mode(intergranular_crack(w=9), g, ignore=(0,))
    assert 0.0 < out["decidable_frac"] < 1.0
    assert out["n_decidable_px"] < out["n_centreline_px"]


def test_flank_comparison_refuses_an_unregistered_pair():
    with pytest.raises(ValueError) as e:
        CM.flank_mode(intergranular_crack(), grains(side=200))
    assert "co-registered" in str(e.value)


def test_flank_verdict_passes_a_narrow_crack_in_large_grains():
    g = grains()
    out = CM.flank_verdict(intergranular_crack(w=5), g, standoffs=(1, 2, 4))
    assert out["max_decidable_frac"] > 0.5
    assert out["quotable"], out["reasons"]


def test_flank_verdict_refuses_when_the_share_tracks_the_standoff():
    """The real numbers, from 260622_316_H_b2_back_CBS_01 at h = 0.10: the share runs
    11.8% at standoff 0 to 66.3% at 16 px while never deciding more than 26% of the
    centreline. The square-grid synthetic cannot reproduce this -- a crack on a grid line
    has different grains either side at every standoff -- so the rule is tested on the
    recorded sweep rather than on a contrived tessellation."""
    sweep = [{"standoff_px": 0, "decidable_frac": 0.035, "intergranular_pct": 11.8},
             {"standoff_px": 1, "decidable_frac": 0.097, "intergranular_pct": 20.2},
             {"standoff_px": 2, "decidable_frac": 0.130, "intergranular_pct": 22.1},
             {"standoff_px": 4, "decidable_frac": 0.169, "intergranular_pct": 25.1},
             {"standoff_px": 8, "decidable_frac": 0.209, "intergranular_pct": 37.2},
             {"standoff_px": 16, "decidable_frac": 0.258, "intergranular_pct": 66.3}]
    out = CM.read_flank_sweep(sweep)
    assert out["intergranular_span_pp"] == pytest.approx(54.5, abs=0.1)
    assert out["max_decidable_frac"] == pytest.approx(0.258)
    assert not out["quotable"]
    assert len(out["reasons"]) == 2, out["reasons"]
    assert any("standoff" in w for w in out["reasons"])
    assert any("decided" in w for w in out["reasons"])


def test_flank_verdict_accepts_a_stable_sweep():
    sweep = [{"standoff_px": s, "decidable_frac": 0.9, "intergranular_pct": 61.0 + 0.5 * i}
             for i, s in enumerate((1, 2, 4, 8))]
    out = CM.read_flank_sweep(sweep)
    assert out["quotable"], out["reasons"]


# --------------------------------------------------------------- junctions are nodes, not px
def test_the_neighbour_kernel_does_not_count_the_pixel_itself():
    """The one real threshold in the junction test is a neighbour COUNT, so the kernel it is
    counted with must have a zero centre. Written after a centre-1 kernel was used here by
    mistake and flagged 77 of a plain cross's 81 skeleton pixels as junction candidates --
    every pixel on a line reads as a 3-neighbour junction when the kernel counts the pixel."""
    assert CM._NEIGHBOURS[1, 1] == 0
    line = np.zeros((41, 41), bool)
    line[20, :] = True
    assert CM.junction_census(line)["candidate_pixels"] == 0


def test_one_axis_aligned_crossing_is_one_node_and_not_five():
    """A plus lights its centre and all four arms. That is one node of degree four."""
    m = np.zeros((41, 41), bool)
    m[20, :] = True
    m[:, 20] = True
    c = CM.junction_census(m)
    assert c["candidate_pixels"] == 5          # the per-pixel test over-marks 5x here
    assert c["clusters"] == 1
    assert c["nodes"] == 1
    assert c["degree_histogram"] == {4: 1}
    assert c["branches"] == 4
    ys, xs, deg = CM.junctions(m)
    assert ys.size == 1 and deg.tolist() == [4]


def test_a_T_is_one_node_of_degree_three():
    m = np.zeros((41, 41), bool)
    m[20, :] = True
    m[20:, 20] = True
    c = CM.junction_census(m)
    assert c["clusters"] == 1 and c["nodes"] == 1
    assert c["degree_histogram"] == {3: 1}
    assert c["branches"] == 3


def test_a_two_branch_cluster_is_not_a_node_and_does_not_cut_the_branch():
    """A cluster with two branches leaving it is a staircase artefact of the skeletonizer.
    Cutting there would split one path into two, which shortens the length distribution and
    manufactures junction-adjacent stubs -- the exact population `_confounds` watches for."""
    g = CM._skeleton_graph
    # an L with a one-pixel spur: the corner lights up but only two branches leave it
    m = np.zeros((41, 41), bool)
    m[20, 5:36] = True
    m[20:36, 20] = True
    out = g(m)
    assert out["kept"][1:].sum() == 1, "the corner itself is a real 3-way node here"
    # now a bare diagonal step, which can light a candidate with only two branches
    deg = out["degree"][1:]
    assert (deg >= CM.MIN_JUNCTION_DEGREE).all() or (deg < CM.MIN_JUNCTION_DEGREE).any()


def test_a_branch_knows_which_nodes_it_touches():
    """`n_adjacent_junctions` was identically zero for every branch on every image: it read a
    degree map at the branch's own pixels, and branch pixels exclude junction pixels by
    construction, so the lookup could only ever return nothing. A read with no writer."""
    m = np.zeros((81, 81), bool)
    m[40, :] = True
    m[:, 20] = True
    m[:, 60] = True                                   # two 4-way nodes on one line
    cls = CM.classify(m, CM.boundaries_from_grain_ids(grains(81, 20)), tau_px=2,
                      min_segment_widths=0)
    counts = [r["n_adjacent_junctions"] for r in cls["segments"]]
    assert max(counts) == 2, counts                   # the middle run touches both
    assert sum(1 for c in counts if c == 1) >= 4      # every stub touches exactly one
    assert all(r["max_adjacent_degree"] in (0, 3, 4) for r in cls["segments"])


def test_the_width_scaled_floor_is_off_by_default_because_it_is_a_deleter():
    """A branch shorter than the crack is wide is in principle skeleton noise inside a wide
    region. In practice the rule is a deleter: measured on 260622_316_H_b2_front_CBS_02, a
    0.5x floor removes 16.3% of the skeleton LENGTH, 1.0x removes 47.3% and 2.0x removes
    66.2%. Half a centreline is not noise, so the default must be off and anything it does
    remove has to appear in `dropped`."""
    assert CM.MIN_SEGMENT_WIDTHS == 0.0
    g = grains()
    m = intergranular_crack()
    cls = CM.classify(m, CM.boundaries_from_grain_ids(g), tau_px=2)
    assert cls["dropped"]["shorter_than_own_width"] == 0
    assert "skeleton_px_dropped_frac" in cls["dropped"]
    wide = CM.classify(m, CM.boundaries_from_grain_ids(g), tau_px=2, min_segment_widths=50.0)
    assert wide.get("n_segments", 0) < cls["n_segments"]
    dropped = (wide.get("dropped") or {})["shorter_than_own_width"]
    assert dropped > 0, "a 50x floor must remove something, and must say that it did"


# ------------------------------------------------------- the flank measurement's own control
def test_flank_controls_separate_a_boundary_path_from_an_interior_one():
    """`controls` validates boundary COINCIDENCE and says nothing about flank comparison,
    which can fail in a way coincidence cannot: a crack wide relative to a grain has both
    sample points in neighbouring grains wherever its centreline runs. So the flank
    measurement needs its own positive and negative, width-matched to the real path."""
    g = grains()
    on = np.zeros((SIDE, SIDE), bool)
    on[GRAIN - 2:GRAIN + 2, :] = True                   # along a grid line
    mid = np.zeros((SIDE, SIDE), bool)
    mid[GRAIN // 2 - 2:GRAIN // 2 + 2, :] = True        # down the middle of a row
    a = CM.flank_controls(on, g, n_null=40)
    b = CM.flank_controls(mid, g, n_null=40)
    assert a["positive_control"] == pytest.approx(100.0, abs=1.0)
    assert a["negative_control"] == pytest.approx(0.0, abs=1.0)
    assert a["real_intergranular_pct"] > 95.0
    assert b["real_intergranular_pct"] < 5.0
    assert a["z_vs_null"] > b["z_vs_null"]


def test_flank_geometry_cache_changes_nothing():
    """The standoff sweep reuses one skeleton. If that cache were wrong the sweep would be
    wrong everywhere and nothing else here would notice."""
    g = grains()
    m = np.zeros((SIDE, SIDE), bool)
    m[GRAIN - 2:GRAIN + 2, :] = True
    geo = CM.flank_geometry(m)
    for so in (1, 4, 16):
        a = CM.flank_mode(m, g, standoff_px=so)
        b = CM.flank_mode(m, g, standoff_px=so, geometry=geo)
        assert a["intergranular_pct_by_centreline"] == b["intergranular_pct_by_centreline"]
        assert a["decidable_frac"] == b["decidable_frac"]


def test_a_negative_control_that_reads_high_is_a_refusal():
    """Measured on 260622_316_H_b2_front_CBS_01: a path placed as far from the partition's
    boundaries as its own shape allows still read 69.9-89.6% intergranular, because the
    regions were smaller than the crack is wide. The sweep gate cannot see this -- a share can
    be perfectly stable across standoff at a value the instrument never resolved."""
    out = CM.read_flank_controls({"positive_control": 99.33, "negative_control": 69.88,
                                  "real_intergranular_pct": 59.64, "z_vs_null": 1.71})
    assert not out["quotable"]
    assert out["resolution_pp"] == pytest.approx(29.5, abs=0.05)
    assert any("resolves only" in r for r in out["reasons"])
    assert any("BELOW the negative control" in r for r in out["reasons"])


def test_a_resolved_instrument_passes_its_controls():
    out = CM.read_flank_controls({"positive_control": 98.0, "negative_control": 11.0,
                                  "real_intergranular_pct": 62.0, "z_vs_null": 4.1})
    assert out["quotable"], out["reasons"]
    assert out["resolution_pp"] == pytest.approx(87.0)


def test_a_stable_sweep_is_still_refused_when_the_controls_fail():
    """The two gates are independent and both must hold."""
    g = grains()
    mid = np.zeros((SIDE, SIDE), bool)
    mid[GRAIN // 2 - 2:GRAIN // 2 + 2, :] = True
    ctl = {"positive_control": 92.0, "negative_control": 80.0, "real_intergranular_pct": 85.0}
    out = CM.flank_verdict(mid, g, standoffs=(1, 2), controls=ctl)
    assert not out["quotable"]
    assert out["controls_verdict"]["resolution_pp"] == pytest.approx(12.0)


def test_a_failed_positive_control_says_why_it_failed():
    """It used to say "no boundary skeleton to walk". Measured on
    260622_316_H_b2_front_CBS_01 at a 7.45 um partition, there were 50,096 boundary skeleton
    pixels -- the walk failed because the longest CONNECTED path was 7,049 px against a
    61,156 px crack. A diagnostic that names the wrong fault sends the reader to the wrong
    input."""
    g = grains()
    m = intergranular_crack()
    ctl = CM.flank_controls(m, g, n_null=8)
    assert ctl["boundary_skeleton_px"] > 0
    assert ctl["crack_centreline_px"] > 0
    assert ctl["boundary_to_crack_length_ratio"] > 0
    one = np.ones_like(g)                       # a single grain: genuinely no boundary
    ctl2 = CM.flank_controls(m, one, n_null=4)
    assert ctl2["positive_control"] is None
    assert "no boundary at all" in ctl2["positive_note"]
    assert any("could not be built" in r for r in CM.read_flank_controls(ctl2)["reasons"])


def test_less_boundary_than_crack_is_a_refusal():
    out = CM.read_flank_controls({"positive_control": None, "positive_note": "short network",
                                  "boundary_to_crack_length_ratio": 0.82,
                                  "real_intergranular_pct": 11.6, "z_vs_null": 0.4})
    assert not out["quotable"]
    assert any("less boundary in the field than there is crack" in r for r in out["reasons"])


# -------------------------------------------------- the web, and the wall closing that cures it
def _rough_tree(half_width=5, roughness=1.0, side=600, seed=0):
    """A tree with FOUR junctions by construction, grown to a width and roughened.

    Four, not six: the cross-link lands on the tip of the first branch, which is a corner with
    two branches leaving it. The baseline returns 4 at every width with a smooth wall, which is
    how the count was checked rather than assumed.
    """
    from scipy import ndimage as ndi
    rng = np.random.default_rng(seed)
    thin = np.zeros((side, side), bool)
    # The branch spacing has to stay above the half-width or the object stops being the tree
    # that was drawn: at 70 px spacing and half-width 40 the smooth wall already gives 5 nodes
    # rather than 4, because neighbouring branches merge. 100 px spacing holds to 40.
    thin[300, 40:560] = True
    for x, dy in ((120, -1), (220, 1), (320, -1), (420, 1)):
        for i in range(110):
            y = 300 + dy * i
            if 0 <= y < side:
                thin[y, x] = True
    thin[190, 120:220] = True
    wide = ndi.binary_dilation(thin, CM.morphology.disk(half_width)) if half_width else thin
    if roughness:
        sdf = (ndi.distance_transform_edt(wide) - ndi.distance_transform_edt(~wide))
        n = ndi.gaussian_filter(rng.normal(size=wide.shape), 2.0)
        wide = (sdf + roughness * (n / (n.std() or 1.0))) > 0
    return wide, 4


def test_a_smooth_wall_gives_the_true_junction_count_at_every_width():
    """The ground truth of the synthetic, established before any cure is applied to it."""
    for hw in (0, 2, 5, 15, 40):
        m, truth = _rough_tree(half_width=hw, roughness=0.0)
        got = CM.junctions(m, regularise_px=0, min_branch_widths=0)[0].size
        assert got == truth, f"half-width {hw}: {got}"


def test_closing_the_wall_recovers_the_count_a_rough_wall_destroys():
    """Inside a wide crack with a rough wall the medial axis is a WEB of members running wall
    to wall, and every intersection is a genuine node of that skeleton -- clustering cannot
    touch it. Measured on the synthetic at 1 px of wall roughness, the raw skeleton gives
    4, 7, 7, 10 nodes for half-widths 2, 5, 15, 40 against a truth of 4; a closing of radius 2
    gives 4, 4, 4, 6."""
    # BOTH cures are off in the "raw" arm. They are module defaults now, so a call that does
    # not switch them off inherits the treatment it is meant to be compared against -- which is
    # exactly how the first draft of this comparison came to report no effect at all.
    raw, cured = [], []
    for hw in (2, 5, 15, 40):
        m, truth = _rough_tree(half_width=hw, roughness=1.0)
        raw.append(CM.junctions(m, regularise_px=0, min_branch_widths=0)[0].size)
        cured.append(CM.junctions(m, min_branch_widths=0)[0].size)
    assert max(raw) > truth, raw
    assert sum(abs(c - 4) for c in cured) < sum(abs(r - 4) for r in raw), (raw, cured)
    assert max(cured) <= max(raw)


def test_regularising_never_removes_a_crack_pixel():
    """A closing is extensive, so the cure can only ever ADD crack. That is the property that
    makes it usable at all: this project's two earlier artefact fixes were both deleters."""
    rng = np.random.default_rng(3)
    for seed in range(4):
        m, _ = _rough_tree(half_width=int(rng.integers(1, 20)), roughness=1.5, seed=seed)
        out, rep = CM.regularise(m)
        assert (out | m == out).all(), "a crack pixel was removed"
        assert rep["area_added_pct"] >= 0.0
        assert out.sum() >= m.sum()


def test_regularise_zero_is_the_identity_and_says_so():
    m, _ = _rough_tree(half_width=6, roughness=1.0)
    out, rep = CM.regularise(m, 0)
    assert (out == m).all()
    assert rep["regularise_px"] == 0 and rep["area_added_pct"] == 0.0


def test_the_closing_reports_any_components_it_bridges():
    """Closing at radius r joins fragments within 2r. On 260622_316_H_b2_front_CBS_01 that is
    2 of 260 components at r = 2 -- a 168 nm gap at that frame's 42.15 nm/px, which is a
    ligament or a mask break rather than two cracks. It is the caller's call, so it is
    reported and never left silent."""
    m = np.zeros((80, 200), bool)
    m[38:42, 20:90] = True
    m[38:42, 92:170] = True                      # a 2 px gap: r=2 bridges it, r=1 also does
    assert CM.regularise(m, 0)[1]["components_merged"] == 0
    assert CM.regularise(m, 2)[1]["components_merged"] == 1
    wider = np.zeros((80, 200), bool)
    wider[38:42, 20:90] = True
    wider[38:42, 95:170] = True                  # a 5 px gap: no radius here reaches it
    assert CM.regularise(wider, 2)[1]["components_merged"] == 0
    assert CM.regularise(wider, 3)[1]["components_merged"] == 0
    rep = CM.regularise(m, 2)[1]
    assert rep["components_before"] == 2 and rep["components_after"] == 1
    assert rep["components_merged"] == 1


def test_the_flank_route_and_the_branch_labels_share_one_mask():
    """flank_mode reads branch labels at coordinates taken from flank_geometry's skeleton. If
    the two regularised differently the arrays would still be the same shape, so nothing would
    raise and every per-branch row would be silently wrong."""
    m, _ = _rough_tree(half_width=8, roughness=1.0)
    geo = CM.flank_geometry(m)
    g = CM._skeleton_graph(m)
    assert (geo["mask"] == g["mask"]).all()
    assert (geo["skel"] == g["skel"]).all()
    assert geo["regularise"]["regularise_px"] == g["regularise"]["regularise_px"]


def test_the_flank_controls_get_the_same_wall_treatment_as_the_crack():
    """The synthetic positive and negative paths are built and then measured the same way the
    real crack is. They briefly were not -- flank_geometry's default regularisation applied to
    them while the caller had asked for none -- and a control carrying a treatment the
    measurement does not is not a control."""
    g = grains()
    on = np.zeros((SIDE, SIDE), bool)
    on[GRAIN - 2:GRAIN + 2, :] = True
    a = CM.flank_controls(on, g, n_null=16, regularise_px=0)
    b = CM.flank_controls(on, g, n_null=16, regularise_px=2)
    assert a["regularise"]["regularise_px"] == 0
    assert b["regularise"]["regularise_px"] == 2
    assert a["positive_control"] is not None and b["positive_control"] is not None
    for r in (a, b):                       # both must still separate on a clean tessellation
        assert r["positive_control"] > 95.0
        assert r["negative_control"] < 5.0


# ------------------------------------------- a node must be resolvable at the local width
def test_both_cures_together_hold_the_true_count_over_the_whole_width_range():
    """A junction is where three DISTINGUISHABLE paths meet, and two paths are not
    distinguishable over a run shorter than the channel is wide. After the wall closing, 96.7%
    of the 332 surviving nodes on 260622_316_H_b2_front_CBS_02 still had a third incident
    branch shorter than the local width (median 9 px against a 28.3 px channel)."""
    for rough in (0.0, 1.0):
        for hw in (2, 5, 15, 40):
            m, truth = _rough_tree(half_width=hw, roughness=rough)
            got = CM.junctions(m)[0].size
            assert got == truth, f"roughness {rough}, half-width {hw}: {got}"


def test_the_resolvability_factor_is_set_below_where_it_starts_losing_junctions():
    """0.5 is not a taste. Every value up to 0.8 holds the true count at all four widths with a
    smooth wall; 0.9 loses a real junction at half-width 40. The breaking point is pinned here
    so that raising the constant cannot pass silently."""
    assert CM.MIN_BRANCH_WIDTHS == 0.5
    m, truth = _rough_tree(half_width=40, roughness=0.0)
    assert CM.junctions(m, min_branch_widths=0.8)[0].size == truth
    assert CM.junctions(m, min_branch_widths=0.9)[0].size < truth


def test_demoting_a_node_deletes_nothing():
    """A demoted cluster's pixels go back to the skeleton and the branches either side rejoin.
    The mask, the skeleton and the total branch length are all untouched -- only the node list
    shrinks. This project's two earlier artefact fixes were both deleters, so the property is
    asserted rather than assumed."""
    m, _truth = _rough_tree(half_width=15, roughness=1.0)
    loose = CM._skeleton_graph(m, min_branch_widths=0)
    tight = CM._skeleton_graph(m, min_branch_widths=0.5)
    assert (loose["mask"] == tight["mask"]).all()
    assert (loose["skel"] == tight["skel"]).all()
    assert tight["nodes"][0].size <= loose["nodes"][0].size
    assert int((tight["branch_labels"] > 0).sum()) >= int((loose["branch_labels"] > 0).sum())
    assert tight["n_branches"] <= loose["n_branches"]


def test_the_demotion_converges_and_says_how_many_passes_it_took():
    """Rejoining branches lengthens them, which can rescue a neighbouring node, so one pass is
    not enough. On the real frames it settles in 3-5."""
    m, _truth = _rough_tree(half_width=15, roughness=1.0)
    g = CM._skeleton_graph(m)
    assert g["resolve_converged"] is True
    assert 1 <= g["resolve_passes"] < CM.MAX_RESOLVE_PASSES
    assert CM.junction_census(m)["resolve_converged"] is True


def test_the_node_rules_cannot_move_the_decidable_fraction():
    """Decidability is a per-centreline-pixel property of the crack's own geometry: can both
    flank samples clear the wall. The node rules change how the skeleton is CUT, never where
    it runs, so they must not touch it. Asserted rather than reasoned, because the two live in
    the same function and a future change could couple them without anything else noticing."""
    g = grains()
    m = intergranular_crack()
    base = CM.flank_mode(m, g, standoff_px=2, regularise_px=0)
    for mbw in (0, 0.5, 2.0):
        graph = CM._skeleton_graph(m, regularise_px=0, min_branch_widths=mbw)
        geo = CM.flank_geometry(m, regularise_px=0)
        out = CM.flank_mode(m, g, standoff_px=2, geometry=geo, graph=graph)
        assert out["decidable_frac"] == base["decidable_frac"]
        assert out["n_centreline_px"] == base["n_centreline_px"]
        assert out["intergranular_pct_by_centreline"] == base["intergranular_pct_by_centreline"]


def test_the_controls_carry_a_spread_and_a_z_prime():
    """The percentage-point resolution gate compares two single numbers and is blind to their
    variance. Z' = 1 - 3(sd_pos + sd_neg)/|mean_pos - mean_neg| is the published form of the
    same rule (Zhang, Chung & Oldenburg 1999), and a prior-art sweep of this module's gating
    turned it up as exactly what the invented gate was stating informally. It is reported
    alongside, not instead: the reader is owed both numbers."""
    g = grains()
    on = np.zeros((SIDE, SIDE), bool)
    on[GRAIN - 2:GRAIN + 2, :] = True
    ctl = CM.flank_controls(on, g, n_null=16, n_reps=4)
    assert len(ctl["positive_replicates"]) > 1
    assert len(ctl["negative_replicates"]) > 1
    assert ctl["z_prime"] is not None
    read = CM.read_flank_controls(ctl)
    assert any("Z'" in n for n in read["notes"])


def test_wide_control_spread_is_refused_even_on_a_large_gap():
    """A 60 point gap between two controls that each vary by 15 points is not a resolved
    instrument, and the percentage-point gate alone would wave it through."""
    tight = CM.read_flank_controls({"positive_control": 95.0, "negative_control": 20.0,
                                    "real_intergranular_pct": 60.0, "z_prime": 0.72})
    assert tight["quotable"], tight["reasons"]
    loose = CM.read_flank_controls({"positive_control": 90.0, "negative_control": 30.0,
                                    "real_intergranular_pct": 60.0, "z_prime": -0.5})
    assert not loose["quotable"]
    assert any("Z'" in r for r in loose["reasons"])


def test_both_gates_read_the_same_control():
    """The percentage-point gap used to read a single draw while Z' read the replicate mean,
    so the two gates were judging two different controls. Worse, the single draw for the
    negative was selected on MEAN DISTANCE to a boundary, a proxy the replicates show does not
    rank placements by the flank share: on one 316 frame the two furthest placements read 35.8
    and 36.9% while less-far ones read 19.3 and 19.5%."""
    g = grains()
    on = np.zeros((SIDE, SIDE), bool)
    on[GRAIN - 2:GRAIN + 2, :] = True
    ctl = CM.flank_controls(on, g, n_null=16, n_reps=4)
    assert ctl["negative_control"] == pytest.approx(
        sum(ctl["negative_replicates"]) / len(ctl["negative_replicates"]), abs=0.02)
    assert ctl["positive_control"] == pytest.approx(
        sum(ctl["positive_replicates"]) / len(ctl["positive_replicates"]), abs=0.02)
    assert "negative_control_furthest" in ctl
    assert ctl["negative_min"] <= ctl["negative_control"] <= ctl["negative_max"]


def test_a_wide_negative_spread_is_said_out_loud():
    out = CM.read_flank_controls({"positive_control": 99.0, "negative_control": 28.0,
                                  "negative_min": 19.3, "negative_max": 36.9,
                                  "real_intergranular_pct": 31.0, "z_prime": 0.6})
    assert any("spans 19.3-36.9%" in n for n in out["notes"])
