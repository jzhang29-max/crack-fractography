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
