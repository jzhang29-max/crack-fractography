#!/usr/bin/env python3
"""Cleaning steps: the ones that record, and proof that the rest are absent."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "analysis"))
import cleaning as C   # noqa: E402


def test_both_floors_bind_and_neither_alone():
    """Taking the physical floor alone gives 1 px at the corpus's coarsest scale, handing
    shape statistics to two-pixel regions. Taking the pixel floor alone leaves speck_count
    incomparable across a 12x scale range. The threshold is the larger of the two."""
    coarse, _ = C.speck_threshold_px(337.24)      # coarsest real frame here
    assert coarse == C.SPECK_PX_FALLBACK, "the pixel floor must hold at coarse scales"
    fine, info = C.speck_threshold_px(29.24)      # finest real frame here (TXM)
    assert fine > C.SPECK_PX_FALLBACK and info["binding_floor"] == "physical"
    mid, info = C.speck_threshold_px(51.88)       # corpus median
    assert mid == 25, "nothing moves for a typical frame, by construction"


def test_threshold_never_drops_below_the_resolution_floor():
    """At any scale. A threshold under the floor would put regionprops on blobs too small
    for width, orientation or tortuosity to mean anything."""
    for nm in (1, 10, 29.24, 51.88, 100, 337.24, 1000, 5000):
        px, _ = C.speck_threshold_px(nm)
        assert px >= C.SPECK_PX_FALLBACK, f"{nm} nm/px gave {px} px"


def test_no_scale_behaves_exactly_as_before():
    px, info = C.speck_threshold_px(None)
    assert px == 25 and info["threshold_um2"] is None


def test_ingest_flags_an_inverted_mask():
    """An inverted mask measures the matrix and reports it as crack, and the number is
    perfectly plausible -- which is why the fraction is checked rather than trusted."""
    g = np.full((10, 10), 0, np.uint8); g[0, 0] = 255       # 99% reads as crack
    w = C.ingest_assertion(g, g < 128)["warnings"]
    assert any("inverted" in x for x in w)


def test_ingest_flags_a_greyscale_image_posing_as_a_mask():
    g = (np.arange(100, dtype=np.uint8).reshape(10, 10) * 2)
    a = C.ingest_assertion(g, g < 128)
    assert a["two_valued"] is False
    assert any("two-valued" in x for x in a["warnings"])


def test_ingest_passes_a_real_mask_silently():
    g = np.full((10, 10), 255, np.uint8); g[2:4, 2:8] = 0
    a = C.ingest_assertion(g, g < 128)
    assert a["warnings"] == [] and a["two_valued"] and a["n_grey_levels"] == 2


def test_connectivity_is_reported_not_implied():
    """4- vs 8-connectivity rewrites every count statistic in the file. It used to be a
    silent argument to skmeasure.label."""
    g = np.full((4, 4), 255, np.uint8); g[1, 1] = 0
    assert C.ingest_assertion(g, g < 128)["connectivity"] == C.CONNECTIVITY == 2


def test_the_destructive_steps_are_absent_with_reasons():
    """Not 'off by default' -- absent. An off toggle is an invitation, and the parameters
    that would make these safe are corpus-specific and unmeasured here. This project has
    already shipped two artefact fixes that were deleters."""
    for step in ("hole_filling", "skeleton_spur_pruning", "small_component_removal",
                 "gap_bridging"):
        assert step in C.NOT_SHIPPED and len(C.NOT_SHIPPED[step]) > 40


def test_detection_limit_says_unresolved_not_absent():
    d = C.detection_limit(50.0, 25)
    assert d["min_resolvable_width_um"] == pytest.approx(0.05)
    assert d["speck_cutoff_um2"] == pytest.approx(25 * 0.05 * 0.05)
    assert "unresolved" in d["note"]
    assert C.detection_limit(None, 25)["one_pixel_um"] is None


def test_censored_share_is_reported_in_three_weightings():
    """A COUNT share of censored regions was the only one reported, and it sat next to MCL
    and TCL. Measured over the corpus the median frame is 4.2% of regions censored but 22.1%
    of crack AREA and 16.6% of crack LENGTH; on TXM, 25.0% of regions against 71.0% of area.
    One frame reads 6% of regions and 44% of area. A count share beside a length statistic
    invites the reader to dismiss it."""
    import numpy as np
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "analysis"))
    from measure import measure_frame
    m = np.zeros((200, 200), bool)
    m[95:105, 0:190] = True        # one big region touching the LEFT edge -> censored
    m[20:24, 60:70] = True         # one small interior region -> not censored
    _, s = measure_frame(m, "synthetic", "sem")
    assert s["censored_share"] == pytest.approx(0.5), "1 of 2 regions"
    # The big one holds almost all the area and length, so those shares must be far higher.
    assert s["censored_share_by_area"] > 0.9, s["censored_share_by_area"]
    assert s["censored_share_by_length"] > 0.9, s["censored_share_by_length"]
    assert "regions (count)" in s["censored_share_weighting"]


def test_a_user_supplied_scale_outranks_everything():
    """nm_per_px() could only return the TXM constant or look up the author's own extracted
    CSV, keyed by the author's own frame stems. Every physical column was therefore
    permanently null for every other user, and the app silently became pixel-only."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "analysis"))
    import scale
    scale._USER.clear(); scale._USER_LOADED[0] = True
    assert scale.nm_per_px("whatever", "sem") is None
    scale._USER["whatever"] = 41.5
    assert scale.nm_per_px("whatever", "sem") == 41.5
    assert scale.scale_source("whatever", "sem") == "set by you"
    # It must beat the TXM constant too: the user may know the image was cropped.
    scale._USER["txmframe"] = 12.0
    assert scale.nm_per_px("txmframe", "txm") == 12.0
    scale._USER.clear()


def test_a_zero_or_negative_scale_is_refused():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "analysis"))
    import scale
    for bad in (0, -1, -0.001):
        with pytest.raises(ValueError):
            scale.set_user_scale("x", bad)


def test_tiff_metadata_is_actually_parsed():
    """scale.py's docstring has listed the FEI block as trust-source 1 since it was
    written, and it was implemented nowhere."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "analysis"))
    import scale
    assert hasattr(scale, "from_tiff")
    # Resolve it the way the app does, not from one developer's home. Hardcoding
    # ~/Desktop/APP/... meant this skipped silently on every machine that keeps the
    # checkout anywhere else, so the TIFF-metadata parser was untested there and looked
    # covered. paths.sem_repo() honours the configured location and the data/ dev symlink.
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "app"))
    import paths as _P
    _repo = _P.sem_repo() or os.path.expanduser("~/Desktop/APP/sem-crack-detector")
    sem = os.path.join(_repo, "original")
    cand = os.path.join(sem, "MAR_H_AS_CBS_0001.tif")
    if not os.path.exists(cand):
        pytest.skip("no SEM corpus here")
    got = scale.from_tiff(cand)
    assert got and 10 < got < 1000, f"implausible nm/px from the TIFF: {got}"
