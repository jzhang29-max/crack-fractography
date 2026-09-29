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


# --- dead-UI guards. Both of these were silent for several releases. -----------------
def _src(rel):
    import os
    return open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             *rel.split("/"))).read()


def test_every_control_in_the_markup_is_wired_to_something():
    """A <select> or <button> that no JavaScript ever names is dead UI, and it does not
    look dead: it renders, it is clickable, and it does nothing.

    This is the guard for a real regression. Commit 977e28c -- about crack pins and batch
    upload, whose message never mentions figures -- spliced into the upload handler and
    took the adjacent figure-builder block with it. #figkind, #figy, #figx and #figdl kept
    rendering from index.html while nothing populated or wired them, so the Figure tab
    shipped as two empty dropdowns and a download button that did nothing, for several
    releases, with app/figures.py and /api/figure.svg fully alive behind it. Nothing in the
    suite referred to those ids, which is why it survived: tests/test_figures.py exercised
    the renderer and never asked whether anyone could reach it.
    """
    import re
    html, js = _src("app/templates/index.html"), _src("app/static/app.js")
    controls = re.findall(r'<(select|button|input|textarea)\b[^>]*\bid="([^"]+)"', html)
    assert controls, "no id'd controls found -- this guard has stopped measuring anything"
    dead = sorted(f"<{t} id={i}>" for t, i in controls if i not in js)
    assert not dead, ("declared in index.html and named by no JavaScript, so it renders "
                      "and does nothing:\n  " + "\n  ".join(dead))


def test_no_function_reference_is_called_without_ever_being_assigned():
    """`window.figRenderRef` survived the deletion as two guarded call sites against a name
    nothing assigned -- `if (typeof window.figRenderRef === "function")`, which is exactly
    the shape that makes a dead reference invisible. A read with no writer, again."""
    import re
    js = _src("app/static/app.js")
    # Injected by the host, not by this file. An allowlist rather than a looser pattern,
    # because the whole value of this guard is that it has no way to shrug.
    EXTERNAL = {"pywebview"}   # the native shell's js_api bridge (packaging/launcher.py)
    # `=(?!=)` IS THE WHOLE GUARD. The first version matched `\s*=`, which also matches the
    # `===` in `typeof window.figRenderRef === "function"` -- so it counted the dead
    # comparison as an assignment and could never fire on the exact pattern it was written
    # for. Caught by deleting the block and watching the test pass. A guard that cannot see
    # the bug in front of it is not a guard.
    for name in sorted(set(re.findall(r"window\.(\w+)", js)) - EXTERNAL):
        reads = len(re.findall(rf"window\.{name}\b(?!\s*=(?!=))", js))
        writes = len(re.findall(rf"window\.{name}\s*=(?!=)", js))
        if reads:
            assert writes, (f"window.{name} is read {reads}x and assigned nowhere -- "
                            f"either wire it or delete the call sites")


def test_the_percent_fields_carry_their_unit_onto_the_axis():
    """FIELDS is (label, unit, scale, suffix) and every render path bound the fourth slot
    to `_`. The three percent fields put their scale in slot 2 and their "%" in slot 4, so
    a histogram of area_fraction drew values multiplied by 100 under an axis reading
    "Crack area fraction" with ticks 0..50 -- wrong by 100x unless the reader guesses."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.figures import FIELDS, axis_label
    for key, (lab, unit, scale, suffix) in FIELDS.items():
        got = axis_label(key)
        if suffix:
            assert suffix in got, f"{key}: axis label {got!r} drops its {suffix!r}"
        if unit:
            assert unit in got, f"{key}: axis label {got!r} drops its unit {unit!r}"
        if scale != 1.0:
            assert unit or suffix, (
                f"{key} is scaled by {scale} and declares no unit at all, so the axis "
                f"numbers cannot be interpreted")


def test_the_censored_share_axes_name_their_weighting():
    """One field called "Area touching frame edge" plotted censored_share, which is the
    share of REGIONS -- the dataset says so in its own censored_share_weighting column.
    On sem/gated 260622_316_H_b2 that read 2.4% against an area-weighted 84.1%."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.figures import FIELDS, axis_label
    assert "AREA" in axis_label("censored_share_by_area")
    assert "LENGTH" in axis_label("censored_share_by_length")
    assert "Regions" in axis_label("censored_share")
    assert "Area touching" not in FIELDS["censored_share"][0], (
        "censored_share is a count share and must not be labelled as an area share")
