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
    src = open(os.path.join(REPO, "app", "figures.py"), encoding="utf-8").read()
    assert "from specimen_stats import" in src, (
        "figures.py must reuse specimen_stats.field_key, not define its own")
    assert specimen_stats.field_key("S1_CBS_0001") == specimen_stats.field_key("S1_ETD_0001")


# --- dead-UI guards. Both of these were silent for several releases. -----------------
def _src(rel):
    import os
    return open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             *rel.split("/")), encoding="utf-8").read()


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
    EXTERNAL = {
        "pywebview",          # the native shell's js_api bridge (packaging/launcher.py)
        # BROWSER BUILT-INS. The guard is about app-defined hooks -- a name this file
        # calls and expects this file to have assigned. Platform members are assigned by
        # the platform, so requiring a `window.X =` for them makes the guard fire on
        # correct code: it did, on window.addEventListener, the first time one was added.
        # Named individually rather than pattern-matched, because the value of this guard
        # is that it has no way to shrug.
        "addEventListener", "removeEventListener", "location", "setTimeout",
        "clearTimeout", "requestAnimationFrame", "innerWidth", "innerHeight",
        "devicePixelRatio", "getComputedStyle", "matchMedia", "scrollTo",
    }
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


# --- AXIS LABELS THAT DO NOT COLLIDE ---------------------------------------------------
#: Fourteen specimens with names the length of the real corpus's. The defect scaled with
#: specimen count, so a two-specimen fixture -- which is what every test above uses --
#: could not see it.
def _many_specimens(n=14, name_len=17):
    out = []
    for i in range(n):
        spec = f"260622_316_{'ambH'[i % 4]}_b{i}".ljust(name_len, "x")
        for j in range(4):
            out.append({"arm": "sem/gated", "specimen": spec,
                        "frame": f"{spec}_CBS_000{j}", "scale_known": True,
                        "area_fraction": 0.01 + 0.004 * i + 0.001 * j,
                        "n_cracks_measured": 10})
    return out


def _labels(svg):
    """(cx, cy, angle, text) for every rotated axis label in the SVG."""
    import re
    out = []
    for m in re.finditer(
            r'<text x="([\d.]+)" y="(\d+)"[^>]*transform="rotate\((-?[\d.]+) '
            r'([\d.]+) ([\d.]+)\)"[^>]*>(.*?)</text>', svg, re.S):
        txt = re.sub(r"<[^>]+>", "", m.group(6))
        out.append((float(m.group(4)), float(m.group(5)), float(m.group(3)), txt.strip()))
    return out


def test_specimen_labels_do_not_overlap_each_other():
    """THE REGRESSION. Labels were rotated -38 degrees, where a label's horizontal
    footprint is most of its text length. With 14 specimens that is 96px of text on 68px
    centres, and getBoundingClientRect on the rendered figure found 10 of 13 consecutive
    pairs overlapping -- by up to 30px across and 80px down. Nine tests in this file
    passed throughout, because each used two specimens and asserted on n, not geometry.

    At -90 the footprint is the font size, so this holds for any name length."""
    out = F.build(_many_specimens(), "sem/gated", "box_by_specimen", y="area_fraction")
    labs = _labels(out["svg"])
    assert len(labs) == 14, f"expected one label per specimen, got {len(labs)}"
    for cx, cy, ang, txt in labs:
        assert ang == -90, (
            f"label at {cx} is rotated {ang}; at anything other than -90 the horizontal "
            "footprint grows with the name length and long names collide")
    xs = sorted(cx for cx, _, _, _ in labs)
    spacing = min(b - a for a, b in zip(xs, xs[1:]))
    #: A vertical label occupies its line box across the axis: font-size 10 with ascender
    #: and descender is under 14px. Compared against the real tick spacing.
    assert spacing > 14, (
        f"ticks are {spacing:.1f}px apart, which cannot fit a 10px vertical label")


def test_the_bottom_margin_fits_the_longest_label():
    """Vertical labels extend DOWN from the axis, so the margin has to be computed from
    the longest one rather than fixed at 120px -- otherwise the fix for overlap just
    moves the defect from collision to clipping."""
    import re
    long_names = _many_specimens(n=6, name_len=40)
    out = F.build(long_names, "sem/gated", "box_by_specimen", y="area_fraction")
    svg = out["svg"]
    H = float(re.search(r'viewBox="0 0 [\d.]+ ([\d.]+)"', svg).group(1))
    labs = _labels(svg)
    assert labs, "no labels were rendered"
    for cx, cy, _, txt in labs:
        # 5.2px per character at font-size 10, the same estimate the renderer sizes by.
        reach = cy + len(txt) * 5.2
        assert reach <= H, (
            f"label {txt!r} reaches y={reach:.0f} in a {H:.0f}px figure: it is clipped")


def test_long_names_are_truncated_not_allowed_to_grow_the_figure_forever():
    out = F.build(_many_specimens(n=4, name_len=60), "sem/gated", "box_by_specimen",
                  y="area_fraction")
    for _, _, _, txt in _labels(out["svg"]):
        assert "…" in txt, "a 60-character name must be elided"
        assert len(txt) < 32, f"label is {len(txt)} chars: {txt!r}"


def test_the_mixed_detector_count_carries_its_denominator():
    """"7 specimens average two detectors per field" sat directly under a figure drawing
    fourteen boxes. The clause was true -- seven of the fourteen are imaged twice -- but
    the leading number in a caption is read as the figure's specimen count, so the caption
    contradicted the picture above it. A number needs the object it belongs to."""
    frames = []
    for i in range(4):
        spec = f"S{i}"
        for j in range(3):
            dets = ("CBS", "ETD") if i < 2 else ("CBS",)
            for det in dets:
                frames.append({"arm": "sem/gated", "specimen": spec,
                               "frame": f"{spec}_{det}_000{j}", "scale_known": True,
                               "area_fraction": 0.02 + 0.01 * i, "n_cracks_measured": 10})
    cap = F.build(frames, "sem/gated", "box_by_specimen", y="area_fraction")["caption"]
    assert "2 of 4 specimens average two detectors" in cap, cap


# --- THE STAGE RASTER FIGURES ----------------------------------------------------------
def _frames_from_disk(arm):
    """The measured corpus, read from the dataset the app itself writes.

    NOT an HTTP call to a dev server on a fixed port. These tests were written against
    127.0.0.1:8822 and skipped when it was absent -- so they passed on the machine where I
    happened to have a server up and SILENTLY DID NOT RUN anywhere else, including CI. A
    test that only executes on the author's desktop is the coverage equivalent of a comment,
    and the raster defect these cover (a 7x9 grid holding nine cells on a diagonal) is
    exactly the kind that reaches a release through that gap.

    Falls back to the app's own data directory, then the repo's analysis/out.
    """
    import json
    for base in (os.environ.get("FRACTOGRAPHY_DATA"),
                 os.path.expanduser("~/Library/Application Support/Crack Fractography"),
                 os.path.join(REPO, "analysis", "out")):
        if not base:
            continue
        f = os.path.join(base, "frames.json")
        if os.path.exists(f):
            rows = json.load(open(f, encoding="utf-8"))
            rows = rows if isinstance(rows, list) else rows.get("frames", [])
            hit = [r for r in rows if r.get("arm") == arm]
            if hit:
                return hit
    pytest.skip(f"no measured {arm} corpus on this machine "
                "(frames.json absent -- expected on a fresh checkout and on CI)")


def _positioned():
    """Real frames from the arm that recorded stage coordinates -- or a NAMED skip.

    THE FRAMES AND THE POSITIONS COME FROM DIFFERENT PLACES, and only the first was
    guarded. frames.json is found in the per-user data directory, which exists on a
    developer machine; the stage coordinates are read by analysis/stage.py from a metadata
    table inside the SEM checkout, reached through the data/sem symlink. data/ is gitignored
    -- deliberately, because committing those links would bake one machine's sibling layout
    into the repo -- so a fresh clone or a detached worktree has the frames and NOT the
    positions.

    Five tests in this file then failed with "no specimen produced raster cells" instead of
    skipping, which reads as a regression in the figure code and is not one. It cost a peer
    session a wrong conclusion about a commit. A skip that names the missing input says so
    immediately.
    """
    rows = _frames_from_disk("sem/gated")
    try:
        import stage
    except Exception as e:                                        # noqa: BLE001
        pytest.skip(f"analysis/stage.py is not importable here ({type(e).__name__}), so no "
                    "frame can resolve a stage position")
    if not any(stage.position(r.get("frame", "")) for r in rows):
        pytest.skip(f"none of the {len(rows)} sem/gated frames resolves a stage position: the "
                    "coordinate table lives in the SEM checkout, reached through the "
                    "gitignored data/sem symlink, so this needs a configured SEM repo")
    return rows


def test_a_three_by_three_raster_is_drawn_as_three_by_three():
    """Grid indices came from RANKING the distinct stage coordinates, and stage.py says in
    its own docstring that the nine fields of a 3x3 raster differ in the sixth decimal
    place, so every field landed in its own group. The result was a 7x9 grid holding nine
    cells strung along a diagonal. It rendered, it looked deliberate, and it was not a
    raster -- no test could see it because no test drew a positioned corpus."""
    cells, modal = F._stage_cells([f for f in _positioned() if f.get("arm") == "sem/gated"])
    assert cells, "no specimen produced raster cells"
    for spec, cs in cells.items():
        ncols = max(c for c, _, _, _ in cs) + 1
        nrows = max(r for _, r, _, _ in cs) + 1
        assert ncols * nrows == len(cs), (
            f"{spec}: {len(cs)} cells in a {ncols}x{nrows} grid -- the grid has holes, "
            "which means the axis clustering split one raster step into several")
        assert ncols <= 4 and nrows <= 4, f"{spec}: {ncols}x{nrows} is not a raster"


def test_the_axis_clustering_survives_jitter_and_rejects_a_non_raster():
    # Three steps of 4.3e-4 with 5e-6 of jitter inside each -- the real geometry.
    vals = [0.0256486, 0.0256532, 0.0260859, 0.0260883, 0.0260886, 0.0265221, 0.0265247]
    idx = F._axis_clusters(vals)
    assert idx is not None
    assert len(set(idx.values())) == 3, f"expected 3 steps, got {len(set(idx.values()))}"
    # Evenly spread coordinates are not a raster axis, and inventing one cell per value
    # would fabricate a grid.
    assert F._axis_clusters([i / 50 for i in range(30)]) is None


def test_the_caption_counts_what_the_figure_drew_not_what_the_arm_holds():
    """_cap(arm, len(rows), ...) printed "n = 86 fields" under panels built from the 36 that
    carry a stage position. The same wrong-denominator defect as the "7 specimens" clause,
    in the same function, one release later -- so every count is now rescoped."""
    out = F.build(_positioned(), "sem/gated", "stage_map", y="area_fraction")
    cap = out["caption"]
    assert f"n = {out['n']} fields" in cap, cap
    assert "no stage position recorded" in cap, "the excluded fields must be declared"
    assert "of 14 specimens" not in cap, (
        "the detector clause still carries the arm's specimen count, not the figure's")


def test_the_statement_is_computed_from_the_rows_the_figure_drew():
    """A statement under a chart must come from the points above it. The full 86 rows were
    travelling to the conclusions engine, which put the 337.2396 nm/px overview field on
    the gradient axis -- its field of view is 10.6x a fine field's and spans much of the
    raster. That weakened the reported trend from +0.750..+0.867 to +0.745..+0.842."""
    out = F.build(_positioned(), "sem/gated", "stage_map", y="area_fraction")
    assert len(out["rows"]) == out["n"], (
        f"{len(out['rows'])} rows travelled for a figure that drew {out['n']}")
    mags = {round(float(r["nm_per_px"]), 4) for r in out["rows"] if r.get("nm_per_px")}
    assert len(mags) == 1, f"the drawn rows span {mags}; a raster is one magnification"


def test_the_other_kinds_still_receive_every_row():
    """_with_rows now reads an optional override. A bug there would silently narrow the
    rows behind every other figure's statement."""
    fr = _positioned()
    for kind in ("box_by_specimen", "histogram"):
        out = F.build(fr, "sem/gated", kind, y="area_fraction")
        assert len(out["rows"]) > out["n"] or len(out["rows"]) == out["n"]
        assert len(out["rows"]) == 86, f"{kind} received {len(out['rows'])} rows, expected 86"


def test_a_stage_figure_on_an_arm_with_no_coordinates_says_so():
    """txm records no stage position. Refusing with a message beats drawing an empty grid."""
    fr = _frames_from_disk("txm")
    with pytest.raises(ValueError) as e:
        F.build(fr, "txm", "stage_map", y="area_fraction")
    assert "stage position" in str(e.value)


def test_the_surface_normalises_within_each_panel_not_across_them():
    """On one shared height scale the four specimens' maxima (1.79 to 12.0) collapsed three
    panels to flat tiles, leaving only the BETWEEN-specimen difference visible -- the one
    comparison this app refuses to support -- while flattening away the within-patch
    gradient that is actually established. So each panel carries its own range, printed."""
    out = F.build(_positioned(), "sem/gated", "stage_surface", y="area_fraction")
    svg = out["svg"]
    assert "scaled to its own range" in svg, "the per-panel scaling is not disclosed"
    # Every panel must contain a full-height column: that is what per-panel scaling means.
    import re
    ys = [float(m) for m in re.findall(r'points="[\d.]+,([\d.]+)', svg)]
    assert ys, "no columns drawn"
    # And the shared legend must be gone -- it would describe a scale nothing is drawn on.
    assert svg.count('rx="2"') == 0, "a shared colour legend survives on a per-panel figure"


def test_the_map_keeps_a_shared_legend_and_prints_every_value():
    """The opposite choice, for the opposite reason: the map prints each cell's number, so
    a shared ramp loses no information and small multiples should share one."""
    out = F.build(_positioned(), "sem/gated", "stage_map", y="area_fraction")
    svg = out["svg"]
    assert svg.count('rx="2"') == len(F.RAMP), "the map lost its shared legend"
    assert svg.count("<title>") == out["n"], "not every cell carries its value"
