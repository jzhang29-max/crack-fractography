#!/usr/bin/env python3
"""The figure is the artifact that LEAVES the app, so its n has to be right.

It was not. A box plot printed "n=20" for a specimen whose own card said 10 fields, with
"specimen is the inferential unit" in the caption directly beneath, because it grouped raw
frames and 56 of the 86 gated fields were imaged twice -- once through CBS, once through
ETD, two instruments that differ by 2.29x on the same physical field. That number was
heading for a paper caption.
"""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "analysis"))

from app import figures as F          # noqa: E402


def _frames():
    """Two specimens. S1 has 3 fields each imaged by CBS and ETD (6 frames); S2 has 3
    fields imaged once. So the honest n is 3 and 3, never 6 and 3."""
    out = []
    for i in (1, 2, 3):
        for det, val in (("CBS", 0.06), ("ETD", 0.02)):
            out.append({"arm": "sem/gated", "specimen": "S1",
                        "frame": f"S1_{det}_000{i}", "scale_known": True,
                        "area_fraction": val, "n_cracks_measured": 10})
        out.append({"arm": "sem/gated", "specimen": "S2",
                    "frame": f"S2_CBS_000{i}", "scale_known": True,
                    "area_fraction": 0.03, "n_cracks_measured": 10})
    return out


def test_n_counts_fields_not_frames():
    out = F.build(_frames(), "sem/gated", "box_by_specimen", y="area_fraction")
    assert "n = 6 fields" in out["caption"], out["caption"]
    assert "frames" not in out["caption"].replace("frames collapsed", ""), out["caption"]
    # S1's box must be built from 3 field values, not 6 frame values.
    assert "n=3" in out["svg"] and "n=6" not in out["svg"], "S1 must show 3 fields"


def test_the_collapse_is_declared_not_silent():
    out = F.build(_frames(), "sem/gated", "box_by_specimen", y="area_fraction")
    assert "9 frames collapsed to 6 fields" in out["caption"], out["caption"]


def test_mixing_two_detectors_in_one_box_is_stated():
    """Averaging CBS and ETD per field keeps the figure consistent with the specimen card,
    but the resulting spread is partly instrument. If it is going to do that it has to say
    so on the figure, because the figure travels without the page around it."""
    out = F.build(_frames(), "sem/gated", "box_by_specimen", y="area_fraction")
    assert "detector" in out["caption"].lower(), out["caption"]


def test_the_collapsed_value_is_the_field_mean():
    """S1's fields are CBS 0.06 and ETD 0.02, so every field is 0.04 and the median is 4%.
    Grouping frames would give a median of 4% too but over six points with a false spread;
    the guard is that the box is built on three."""
    out = F.build(_frames(), "sem/gated", "box_by_specimen", y="area_fraction")
    assert "median 4" in out["svg"], "expected the per-field mean, 4%"


def test_figure_and_specimen_card_cannot_disagree_about_a_field():
    """Both must route through specimen_stats.field_key. A second rule is how they drifted."""
    import specimen_stats
    src = open(os.path.join(REPO, "app", "figures.py")).read()
    assert "from specimen_stats import" in src, (
        "figures.py must reuse specimen_stats.field_key, not define its own")
    assert specimen_stats.field_key("S1_CBS_0001") == specimen_stats.field_key("S1_ETD_0001")
