#!/usr/bin/env python3
"""Collections: entries in the instrument dropdown that the user made.

WHAT A COLLECTION IS, AND WHAT IT DELIBERATELY IS NOT. sem/gated, txm and uploads are
INSTRUMENTS -- different physical ways of producing a mask -- and this app refuses to
aggregate across them because the numbers are not comparable. A collection is a division
WITHIN Your images. Every frame in one is still an uploaded mask measured by the same
code, and critically `arm` stays "uploads", so every guard that reads `arm == "uploads"`
-- delete_frame, mask_edit, crop, send_to_parent -- keeps working untouched. Making
collections a new kind of arm would have put a user-typed string into the path and record
logic of all four.

The user asked for this in these words: "people can make a new dropdown themselves and
add more images in there".
"""
import json
import os
import sys
import urllib.parse

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server, mask_png  # noqa: E402


def _post(s, path, obj):
    st, raw = s.post(path, json.dumps(obj).encode(), "application/json")
    return st, (json.loads(raw) if raw else None)


def _seed(s, name="img", bar=40, collection=None):
    path = "/api/upload"
    if collection:
        path += "?collection=" + urllib.parse.quote(collection)
    st, raw = s.upload(f"{name}.png", mask_png(200, 150, bar), path=path)
    assert st == 200, raw[:250]
    up = json.loads(raw)
    return up["frames"][0]["frame"] if "frames" in up else up["frame"]


def _names(s):
    st, d = s.json("/api/collections")
    assert st == 200, d
    return [c["name"] for c in d["collections"]]


def _in(s, name):
    st, rows = s.json("/api/frames?arm=uploads&collection=" + urllib.parse.quote(name))
    assert st == 200, rows
    return sorted(r["frame"] for r in rows)


def test_a_collection_exists_before_anything_is_in_it(tmp_path):
    """The whole point. "Make one and then add images to it" is not a thing you can do if
    the place only comes into existence once something is already in it -- the same
    inversion that hid Your images itself until the system created something there."""
    with Server(tmp_path / "d") as s:
        _seed(s, "a")
        st, _ = _post(s, "/api/collections", {"name": "Batch 3"})
        assert st == 200
        assert _names(s) == ["Batch 3"]
        st, arms = s.json("/api/arms")
        up = [a for a in arms if a["arm"] == "uploads"][0]
        assert up["collections"] == [{"name": "Batch 3", "n_frames": 0}], up["collections"]
        # and it is reachable: empty, not missing
        assert _in(s, "Batch 3") == []


def test_an_upload_lands_in_the_collection_it_was_sent_to(tmp_path):
    with Server(tmp_path / "d") as s:
        _post(s, "/api/collections", {"name": "Batch 3"})
        a = _seed(s, "loose")
        b = _seed(s, "filed", 70, collection="Batch 3")
        assert _in(s, "Batch 3") == [b]
        rec = next(r for r in s.dataset("frames") if r["frame"] == b)
        assert rec["arm"] == "uploads", "a collection must not become an arm"
        assert rec["collection"] == "Batch 3"
        assert next(r for r in s.dataset("frames")
                    if r["frame"] == a).get("collection") is None


def test_uploading_into_a_name_that_does_not_exist_yet_registers_it(tmp_path):
    """Otherwise the frame is filed somewhere the dropdown cannot offer, which is a frame
    you cannot navigate to."""
    with Server(tmp_path / "d") as s:
        b = _seed(s, "x", 60, collection="Typed on the spot")
        assert "Typed on the spot" in _names(s)
        assert _in(s, "Typed on the spot") == [b]


def test_an_image_you_already_have_can_be_filed(tmp_path):
    """Without this a collection could only ever hold images uploaded after it was made,
    which makes it useless for organising what is already there."""
    with Server(tmp_path / "d") as s:
        a = _seed(s, "old")
        st, _ = _post(s, "/api/set_collection", {"frame": a, "collection": "Later"})
        assert st == 200
        assert _in(s, "Later") == [a]
        st, _ = _post(s, "/api/set_collection", {"frame": a, "collection": None})
        assert st == 200
        assert _in(s, "Later") == []
        assert any(r["frame"] == a for r in s.dataset("frames")), "the frame went with it"


def test_removing_a_collection_removes_a_label_and_nothing_else(tmp_path):
    """An organising control that deletes data is not an organising control. The images
    go back to being plain Your images."""
    with Server(tmp_path / "d") as s:
        a = _seed(s, "p", 40, collection="Set")
        b = _seed(s, "q", 70, collection="Set")
        st, d = _post(s, "/api/collections", {"name": "Set", "delete": True})
        assert st == 200, d
        assert d["frames_freed"] == 2, d
        assert _names(s) == []
        on_disk = sorted(r["frame"] for r in s.dataset("frames"))
        assert on_disk == sorted([a, b]), on_disk
        up = os.path.join(str(tmp_path / "d"), "uploads")
        for f in (a, b):
            assert os.path.exists(os.path.join(up, f"{f}_gated.png")), f
        assert all(r.get("collection") is None for r in s.dataset("frames"))


def test_a_collection_survives_a_re_measure(tmp_path):
    """remeasure() rebuilds the record from the mask and carries a short list of identity
    fields across. A field not on that list is silently dropped by every path that
    re-measures -- setting a scale, saving a correction -- which is how `edited` was lost
    for months."""
    with Server(tmp_path / "d") as s:
        a = _seed(s, "rm", 40, collection="Keeps")
        st, raw = s.post(f"/api/scale?arm=uploads&frame={a}&nm_per_px=42.0")
        assert st == 200, raw[:200]
        assert _in(s, "Keeps") == [a], "setting a scale emptied the collection"
        st, raw = s.post(f"/api/remeasure?arm=uploads&frame={a}")
        assert st == 200, raw[:200]
        assert _in(s, "Keeps") == [a], "re-measuring emptied the collection"


def test_a_collection_still_named_by_a_frame_is_not_lost(tmp_path):
    """Defence against the two stores drifting. If the list loses a name that frames
    still point at, those frames would become unreachable -- no dropdown entry can offer
    a place that is not on the list."""
    with Server(tmp_path / "d") as s:
        a = _seed(s, "orph", 40, collection="Ghost")
        # drop it from the list only, the way a hand-edited file or a half-finished
        # delete would
        p = os.path.join(str(tmp_path / "d"), "collections.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump([], fh)
        st, d = s.json("/api/collections")
        assert st == 200
        assert [c["name"] for c in d["collections"]] == ["Ghost"], d
        assert _in(s, "Ghost") == [a]


@pytest.mark.parametrize("bad", ["", "   ", "a/b", "a\\b", "x" * 61, "a\nb", "a\x00b"])
def test_a_name_that_cannot_be_one_is_refused(tmp_path, bad):
    """A collection name is user text that ends up in a query string and in a record.
    Slashes especially: the arm vocabulary already uses them (sem/gated), and a
    collection containing one would be ambiguous with an arm."""
    with Server(tmp_path / "d") as s:
        _seed(s, "n")
        st, _ = _post(s, "/api/collections", {"name": bad})
        assert st == 400, f"{bad!r} was accepted"


@pytest.mark.parametrize("bad", ["a/b", "x" * 61, "a\nb"])
def test_a_bad_name_cannot_arrive_by_the_back_doors_either(tmp_path, bad):
    """Two other endpoints take a collection name. Validating only the one that creates
    them would leave the other two as the way in."""
    with Server(tmp_path / "d") as s:
        a = _seed(s, "bd")
        st, _ = _post(s, "/api/set_collection", {"frame": a, "collection": bad})
        assert st == 400, f"set_collection accepted {bad!r}"
        st, raw = s.upload("bd2.png", mask_png(200, 150, 50),
                           path="/api/upload?collection=" + urllib.parse.quote(bad))
        assert st == 400, f"upload accepted {bad!r}"


def test_moving_an_unknown_frame_is_refused(tmp_path):
    with Server(tmp_path / "d") as s:
        _seed(s, "real")
        st, _ = _post(s, "/api/set_collection", {"frame": "nope", "collection": "X"})
        assert st == 404
        st, _ = _post(s, "/api/set_collection", {"frame": "", "collection": "X"})
        assert st == 400


def test_a_collection_does_not_leak_into_another_arm(tmp_path):
    """The filter is on the uploads arm. Asking for a collection of sem/gated must not
    quietly return the uploads frames that carry that label."""
    with Server(tmp_path / "d") as s:
        _seed(s, "u", 40, collection="Mine")
        st, rows = s.json("/api/frames?arm=sem%2Fgated&collection=Mine")
        assert st in (200, 404), st
        if st == 200:
            assert rows == [], rows
