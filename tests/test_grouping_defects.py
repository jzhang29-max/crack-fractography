#!/usr/bin/env python3
"""The six grouping defects found by auditing the real endpoints.

None of these lost data -- the data-loss one is in test_concurrent_saves.py. These all
produce a number or a comparison that READS WRONG, which for a measurement tool is the
same severity with a longer fuse.
"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tests"))
sys.path.insert(0, HERE)
from liveserver import Server, mask_png  # noqa: E402
from app import groupstats as GS  # noqa: E402


def _frame(spec, modality="sem", nm=None, n=3, big=100, rest=10, mp=1.0):
    """A frame record plus cracks, shaped the way frame_stats expects."""
    rec = {"arm": "uploads", "frame": f"{spec}_f{n}", "specimen": spec,
           "modality": modality, "megapixels": mp, "nm_per_px": nm,
           "scale_known": nm is not None,
           "largest_share_of_area": big / (big + rest * (n - 1)) if n else None}
    cracks = [{"Area_px": big, "SkeletonLength_px": 50, "MeanWidth_px": 2,
               "Orientation_deg": 10, "touches_border": False}]
    cracks += [{"Area_px": rest, "SkeletonLength_px": 12, "MeanWidth_px": 2,
                "Orientation_deg": 20, "touches_border": False} for _ in range(n - 1)]
    return rec, cracks


def _summary(frames_and_cracks):
    frames = [f for f, _ in frames_and_cracks]
    by = {(f["arm"], f["frame"]): c for f, c in frames_and_cracks}
    return GS.group_summary(frames, by)


# ---------------------------------------------------------------- 1. a count is not a mass
def test_the_group_reports_concentration_beside_the_count():
    """305 components once read as a fragmented network until the largest was found to
    hold 97.45% of the area. The per-frame value existed and was correct; it was simply
    not in the group summary, so the table showed a count with nothing to read it against."""
    out = _summary([_frame("S1"), _frame("S1", n=4)])
    assert "largest_share_of_area" in out, "no concentration row in the group summary"
    assert out["largest_share_of_area"]["value"] is not None
    assert out["n_cracks"]["value"] > 0


def test_every_summary_row_carries_a_plain_definition():
    out = _summary([_frame("S1")])
    for key, label, how, unit, _d in GS.SUMMARY:
        assert out[key].get("definition"), f"{key} has no definition"
        assert len(out[key]["definition"]) > 40, f"{key}'s definition is a stub"


# ------------------------------------------------------------------- 2 & 3. caveats
def test_a_single_group_gets_caveats_at_all():
    """group_summary returned none -- only the two-group compare had them -- so the first
    button a user presses pooled across specimens and modalities in silence."""
    out = _summary([_frame("S1"), _frame("S2", modality="txm")])
    assert out.get("caveats"), "a mixed-modality group produced no caveats"
    assert any("modalit" in c.lower() for c in out["caveats"])


def test_differing_scale_is_named_not_just_missing_scale():
    """The old caveat fired only when a scale was ABSENT. Two fully-scaled frames 249x
    apart were pooled with nothing said."""
    out = _summary([_frame("S1", nm=2.0), _frame("S1", nm=498.0, n=4)])
    assert any("pixel size varies" in c.lower() for c in out.get("caveats", [])), \
        f"no scale-spread caveat: {out.get('caveats')}"


def test_a_dominant_crack_is_called_out():
    out = _summary([_frame("S1", big=10000, rest=1, n=3)])
    assert any("single crack" in c.lower() for c in out.get("caveats", [])), \
        f"no dominance caveat: {out.get('caveats')}"


def test_a_clean_group_is_not_nagged():
    """Caveats that always fire are ignored. One specimen, one modality, one scale."""
    out = _summary([_frame("S1", nm=10.0, big=50, rest=40),
                    _frame("S1", nm=10.0, n=4, big=50, rest=40)])
    assert not out.get("caveats"), f"clean group still warned: {out['caveats']}"


# ------------------------------------------- 4. two masks of one micrograph are one image
@pytest.mark.parametrize("a,b,same", [
    ("sem/gated", "sem/machine", True),
    ("txm", "txm/machine", True),
    ("sem/gated", "txm", False),
    ("uploads", "sem/gated", False),
    ("uploads", "uploads", True),
])
def test_pixel_source_treats_two_masks_of_one_image_as_one(a, b, same):
    """sem/gated against sem/machine is the same micrograph under two masks and is the
    most obvious A/B this app invites; keying overlap on the arm reported zero shared
    pixels and the fatal banner never appeared. 142 frames exist in both SEM arms."""
    from app.server import _pixel_source
    assert (_pixel_source(a) == _pixel_source(b)) is same


# ------------------------------------------------------- 5 & 6. self-overlap, and rename
def test_a_group_holding_a_frame_and_its_own_crop_double_counts(monkeypatch):
    """_pixel_overlaps had exactly ONE call site -- group_compare, across the two sides --
    so a group holding a parent AND its own crop measured as two frames and summed the
    same pixels twice, with no warning and a spread that looks tighter than it is.

    Driven against _pixel_overlaps directly with synthetic records rather than through
    /api/crop, because a crop is now a VIEWPORT and does not always mint a child frame;
    the lineage this resolves (cropped_from.box_px) is what the check actually reads.
    """
    from app import server as SV

    frames = [
        {"arm": "uploads", "frame": "parent", "width_px": 400, "height_px": 300},
        {"arm": "uploads", "frame": "child",
         "cropped_from": {"arm": "uploads", "frame": "parent",
                          "box_px": [10, 10, 120, 90],
                          "parent_size_px": [400, 300]}},
        {"arm": "uploads", "frame": "elsewhere", "width_px": 400, "height_px": 300},
    ]
    monkeypatch.setattr(SV, "_load_quiet", lambda what: frames if what == "frames" else [])

    mem = [{"arm": "uploads", "frame": "parent"}, {"arm": "uploads", "frame": "child"}]
    ov = [o for o in SV._pixel_overlaps(mem, mem) if o["a"] != o["b"]]
    assert ov, "a parent and its own crop in one group reported no overlap"
    assert max(o["share_of_smaller"] or 0 for o in ov) == 1.0, \
        f"the crop is wholly inside the parent, so share_of_smaller must be 1.0: {ov}"

    # the negative control: two unrelated frames must NOT report an overlap, or the check
    # would simply be firing on everything
    mem2 = [{"arm": "uploads", "frame": "parent"}, {"arm": "uploads", "frame": "elsewhere"}]
    assert not [o for o in SV._pixel_overlaps(mem2, mem2) if o["a"] != o["b"]], \
        "two unrelated frames reported shared pixels"


def test_two_masks_of_one_micrograph_report_shared_pixels(monkeypatch):
    """sem/gated against sem/machine is ONE micrograph under two masks. Keying the check
    on the arm made the most obvious A/B this app invites report zero overlap."""
    from app import server as SV

    frames = [
        {"arm": "sem/gated", "frame": "F", "width_px": 400, "height_px": 300},
        {"arm": "sem/machine", "frame": "F", "width_px": 400, "height_px": 300},
    ]
    monkeypatch.setattr(SV, "_load_quiet", lambda what: frames if what == "frames" else [])
    ov = SV._pixel_overlaps([{"arm": "sem/gated", "frame": "F"}],
                            [{"arm": "sem/machine", "frame": "F"}])
    assert ov and (ov[0]["share_of_smaller"] or 0) == 1.0, \
        f"the same micrograph under two masks reported no shared pixels: {ov}"


def test_a_group_can_be_renamed(tmp_path):
    """There was no rename at all -- only save-under-a-new-name then delete, which leaves
    a duplicate if the user stops halfway."""
    with Server(tmp_path / "d") as s:
        st, raw = s.upload("a.png", mask_png(120, 90, 20))
        assert st == 200, raw[:200]
        mem = [{"arm": "uploads", "frame": json.loads(raw)["frame"]}]
        assert s.post("/api/groups", json.dumps({"name": "old", "frames": mem}).encode(),
                      "application/json")[0] == 200
        st, raw = s.post("/api/groups", json.dumps(
            {"name": "old", "rename": "new"}).encode(), "application/json")
        assert st == 200, raw[:200]
        st, got = s.json("/api/groups")
        names = got["groups"] if isinstance(got["groups"], dict) else \
            {x["name"]: 1 for x in got["groups"]}
        assert "new" in names and "old" not in names, names


def test_rename_refuses_to_overwrite_and_refuses_an_unknown_group(tmp_path):
    with Server(tmp_path / "d") as s:
        st, raw = s.upload("a.png", mask_png(120, 90, 20))
        mem = [{"arm": "uploads", "frame": json.loads(raw)["frame"]}]
        for n in ("one", "two"):
            s.post("/api/groups", json.dumps({"name": n, "frames": mem}).encode(),
                   "application/json")
        st, _ = s.post("/api/groups", json.dumps({"name": "one", "rename": "two"}).encode(),
                       "application/json")
        assert st == 409, f"rename clobbered an existing group (status {st})"
        st, _ = s.post("/api/groups", json.dumps(
            {"name": "nope", "rename": "x"}).encode(), "application/json")
        assert st == 404, f"rename of an unknown group returned {st}"
        st, _ = s.post("/api/groups", json.dumps(
            {"name": "one", "rename": "  "}).encode(), "application/json")
        assert st == 400, f"rename to a blank name returned {st}"


# ------------------------------------- the comparison table has to be readable on its own
def test_compare_rows_carry_their_unit_and_definition():
    """A column of bare numbers is unreadable: "Crack area fraction 2.62" is a PERCENTAGE,
    and nothing on screen said so. The unit was already in the payload and unrendered; the
    definition was not sent at all."""
    a = _summary([_frame("S1", nm=10.0)])
    b = _summary([_frame("S2", nm=10.0, n=5)])
    cmp = GS.compare(a, b, "A", "B")
    assert cmp["rows"], "no rows"
    for r in cmp["rows"]:
        assert r.get("unit"), f"{r['key']} has no unit"
        assert r.get("definition"), f"{r['key']} has no definition"
        assert len(r["definition"]) > 40, f"{r['key']}'s definition is a stub"
    frac = next(r for r in cmp["rows"] if r["key"] == "area_fraction_pct")
    assert "%" in frac["unit"], f"the area-fraction unit must say it is a percentage: {frac['unit']}"


def test_the_compare_table_prints_the_definition_rather_than_hiding_it():
    """Printed, not a title= tooltip: a tooltip is invisible on a touch screen and does not
    survive a screenshot, which is how this table actually gets shared."""
    js = open(os.path.join(HERE, "app", "static", "app.js"), encoding="utf-8").read()
    i = js.index("function gCompareTable")
    body = js[i:js.index("\nfunction ", i + 10)]
    assert "r.definition" in body, "the compare table never reads the definition"
    assert "r.unit" in body, "the compare table never reads the unit"
    assert 'title="' not in body.split("r.definition")[1][:200], \
        "the definition is being put in a tooltip instead of printed"


# ------------------------------- the table read cleaner than the data was: four silent rows
def _cen_frame(spec, by_area, n_cen=0, n=4, nm=10.0):
    """A frame whose censoring is set independently by count and by area, which is how the
    frame records actually carry it."""
    rec, cracks = _frame(spec, nm=nm, n=n)
    rec["frame"] = f"{spec}_cen{by_area}_{n_cen}_{n}"
    rec["censored_share_by_area"] = by_area
    for c in cracks[:n_cen]:
        c["length_is_censored"] = True
    return rec, cracks


def test_censoring_is_reported_and_judged_by_area_not_only_by_count():
    """The caveat tested the COUNT-weighted share, the smallest of the three the frame
    records carry. A real comparison sat at 7.42% by count and 12.16% by area and passed in
    silence while every length row was a lower bound."""
    a = _summary([_cen_frame("S1", 0.13, n_cen=0, n=20)])     # 0% by count, 13% by area
    b = _summary([_cen_frame("S2", 0.12, n_cen=0, n=20)])
    assert a["censoring"]["pct_censored"] == 0.0, "the count share should be zero here"
    assert a["censoring"]["pct_censored_by_area"] == 13.0, \
        f"area share not reported: {a['censoring']}"
    cav = GS.compare(a, b, "A", "B")["caveats"]
    assert any("area" in c.lower() and "lower bound" in c.lower() for c in cav), \
        f"high area-censoring raised no caveat: {cav}"


def test_low_censoring_on_both_weightings_raises_nothing():
    """Negative control. The test above must be able to NOT fire, or it measures nothing."""
    a = _summary([_cen_frame("S1", 0.02, n_cen=0, n=20)])
    b = _summary([_cen_frame("S2", 0.02, n_cen=0, n=20)])
    cav = GS.compare(a, b, "A", "B")["caveats"]
    assert not any("lower bound" in c.lower() for c in cav), f"nagged on clean data: {cav}"


def test_a_lopsided_censoring_split_is_named():
    """Two sides censored by very different amounts bias their lengths in OPPOSITE
    directions, so the length ratio is partly that. max() alone could never see it."""
    a = _summary([_cen_frame("S1", 0.02, n_cen=8, n=20)])     # 40% by count
    b = _summary([_cen_frame("S2", 0.02, n_cen=1, n=20)])     # 5% by count
    cav = GS.compare(a, b, "A", "B")["caveats"]
    assert any("different amounts" in c.lower() for c in cav), f"no asymmetry caveat: {cav}"


def test_two_single_specimen_sides_are_called_n_equals_one():
    """6 frames against 6 frames of one specimen each reads as n=6 and is n=1. spec_overlap
    sees only a specimen on BOTH sides; summary_caveats sees only pooling SEVERAL per side.
    This configuration fell through both."""
    a = _summary([_frame("AS", nm=10.0, n=3), _frame("AS", nm=10.0, n=4)])
    b = _summary([_frame("HIP", nm=10.0, n=5), _frame("HIP", nm=10.0, n=6)])
    cav = GS.compare(a, b, "AS", "HIP")["caveats"]
    hit = [c for c in cav if "n=1 specimen" in c.lower()]
    assert hit, f"no single-specimen caveat: {cav}"
    assert "2 frames of AS" in hit[0] and "2 frames of HIP" in hit[0], hit[0]


def test_several_specimens_a_side_does_not_get_the_n_equals_one_caveat():
    """Negative control for the test above."""
    a = _summary([_frame("AS1", nm=10.0, n=3), _frame("AS2", nm=10.0, n=4)])
    b = _summary([_frame("HIP1", nm=10.0, n=5), _frame("HIP2", nm=10.0, n=6)])
    cav = GS.compare(a, b, "AS", "HIP")["caveats"]
    assert not any("n=1 specimen" in c.lower() for c in cav), f"fired wrongly: {cav}"


def test_the_aspect_row_does_not_claim_to_be_length_over_width():
    """It is the fitted ellipse's major over minor. On a tortuous crack that is several
    times SMALLER than skeleton length over mean width, and the two can move in opposite
    directions -- so the old 'length / width' unit named a quantity it does not compute."""
    row = next(r for r in GS.SUMMARY if r[0] == "mean_aspect")
    key, label, how, unit, definition = row
    assert "ellipse" in unit.lower(), f"unit still misnames the quantity: {unit!r}"
    assert "not length" in definition.lower() or "NOT length" in definition, \
        "the definition must say it is not length over width"
    assert "3.3" not in definition, \
        "the 'about 3.3' benchmark has no stated provenance in the code that ships it"


def test_the_orientation_note_discloses_that_it_is_the_retired_measurand():
    """analysis/segments.py retires the whole-component second-moment axis BY NAME for
    branched networks, and the comparison shipped it with no disclosure and a reference axis
    ~90 degrees from the segment rose's."""
    out = _summary([_frame("S1", nm=10.0)])
    note = out["orientation"]["note"].lower()
    assert "whole-component" in note or "second-moment" in note, f"no disclosure: {note}"
    assert "90 degrees" in note, "the ~90 degree axis difference is not stated"
    assert "segments.py" in note, "the note does not point at the module that retires it"
    doc = open(os.path.join(HERE, "analysis", "segments.py"), encoding="utf-8").read()
    assert "second-moment major axis of the component" in doc, \
        "segments.py no longer retires this -- the note's claim has gone stale"


def test_the_segment_rose_reaches_the_comparison_table():
    """rose_R is stored on every frame with a permutation null and the comparison did not
    read it. On one real pair the retired row read 'identical' (R 0.681 vs 0.689) while
    rose_R separated the two sides completely."""
    fa, ca = _frame("S1", nm=10.0)
    fb, cb = _frame("S2", nm=10.0, n=5)
    fa["rose_R"], fa["rose_R_null"], fa["rose_beats_null"] = 0.29, 0.14, True
    fb["rose_R"], fb["rose_R_null"], fb["rose_beats_null"] = 0.51, 0.14, True
    a = GS.group_summary([fa], {(fa["arm"], fa["frame"]): ca})
    b = GS.group_summary([fb], {(fb["arm"], fb["frame"]): cb})
    row = next((r for r in GS.compare(a, b, "A", "B")["rows"] if r["key"] == "rose_R"), None)
    assert row is not None, "rose_R never reaches the comparison"
    assert row["a"] == 0.29 and row["b"] == 0.51, row
    assert "null" in row["definition"].lower(), "the definition must mention the null"
    assert a["orientation"]["rose_frames_beating_null"] == "1 of 1", \
        a["orientation"].get("rose_frames_beating_null")


# ------------------------------- the group pane computed four things and rendered none of them
def _gstats_body():
    js = open(os.path.join(HERE, "app", "static", "app.js"), encoding="utf-8").read()
    i = js.index("function gStatsTable")
    return js[i:js.index("\nfunction ", i + 10)]


def test_the_group_card_shows_the_area_censoring_share_not_only_the_count_share():
    """The sentence quoted pct_censored alone -- the smallest of the three weightings the
    server sends. On one real group it printed 5.5% while the area share was 24.8%."""
    body = _gstats_body()
    assert "pct_censored_by_area" in body, "the group card never reads the area share"
    assert "pct_censored" in body, "the count share went missing"


def test_the_group_card_shows_every_summary_row():
    """The key list is hardcoded, so a row added to SUMMARY is invisible here until it is
    added here too -- which is how rose_R reached the comparison table and not this pane."""
    body = _gstats_body()
    missing = [k for (k, *_rest) in GS.SUMMARY if f'"{k}"' not in body]
    assert not missing, f"SUMMARY rows the group card never renders: {missing}"


def test_the_group_card_renders_its_own_caveats():
    """group_summary has returned caveats since the pane was built and nothing rendered them:
    only the two-group compare had a block. "Measure group A" pooled across modalities and
    across a 6.5x pixel size in silence."""
    body = _gstats_body()
    assert "caveats" in body, "the group card never reads s.caveats"
    assert "s.caveats.map" in body or "caveats || []" in body, \
        "s.caveats is mentioned but never iterated"
    for cap in (".slice(0,", ".slice(0, 3", "[0]"):
        assert f"s.caveats{cap}" not in body, \
            f"the group card caps its caveats with {cap} -- a cap plus a sort has deleted " \
            "findings in this app before"


def test_a_lopsided_split_names_both_weightings_not_just_the_first():
    """The loop broke after the count case, so a pair lopsided on BOTH reported only the
    count split and the reader never learned the area split was worse."""
    a = _summary([_cen_frame("S1", 0.30, n_cen=8, n=20)])   # 40% count, 30% area
    b = _summary([_cen_frame("S2", 0.05, n_cen=1, n=20)])   # 5% count, 5% area
    hit = [c for c in GS.compare(a, b, "A", "B")["caveats"] if "different amounts" in c]
    assert hit, "no asymmetry caveat at all"
    assert "by count" in hit[0] and "by area" in hit[0], \
        f"only one weighting named, the other was dropped by the break: {hit[0]}"


def test_a_side_censored_at_zero_against_a_censored_side_still_warns():
    """min(a, b) > 0 skipped the MAXIMAL asymmetry: 0% against 40% is as lopsided as it gets
    and no ratio exists to compare."""
    a = _summary([_cen_frame("S1", 0.02, n_cen=8, n=20)])   # 40% by count
    b = _summary([_cen_frame("S2", 0.02, n_cen=0, n=20)])   # 0% by count
    cav = GS.compare(a, b, "A", "B")["caveats"]
    assert any("different amounts" in c for c in cav), f"zero-vs-40% raised nothing: {cav}"


def test_a_symmetric_pair_is_still_not_nagged_about_censoring():
    """Negative control for the two tests above."""
    a = _summary([_cen_frame("S1", 0.02, n_cen=1, n=20)])
    b = _summary([_cen_frame("S2", 0.02, n_cen=1, n=20)])
    cav = GS.compare(a, b, "A", "B")["caveats"]
    assert not any("different amounts" in c for c in cav), f"nagged on a matched pair: {cav}"
