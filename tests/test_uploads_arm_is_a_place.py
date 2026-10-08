#!/usr/bin/env python3
"""Your images is always reachable, empty or not.

THE DEFECT. /api/arms was built purely from frames.json, so an arm with no frames did not
appear in the response and the client dropped it from the instrument dropdown. For sem/*
and txm that is right: they describe corpora this app did not make and cannot offer when
they are absent. For uploads it was backwards. It is the one arm the app owns, the
destination of the Add image button, and the only arm a user can put anything into -- so
the entry appeared when something was CREATED there and vanished when the user deleted
their last image.

That inversion is what the user objected to, in those words: they wanted Your images to be
somewhere they choose to go, "not by the system but by their choice". Hiding it until the
system puts something in it is the opposite.

Making it always visible needed a second change, and that is the half worth testing:
/api/frames 404s on an empty arm, so an always-offered-but-empty Your images would have
loaded straight into "Could not load the uploads arm" -- a worse dead end than the hidden
option it replaced.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server, mask_png  # noqa: E402


def _post(s, path, obj):
    st, raw = s.post(path, json.dumps(obj).encode(), "application/json")
    return st, (json.loads(raw) if raw else None)


def _seed(s, name="img", bar=40):
    st, raw = s.upload(f"{name}.png", mask_png(200, 150, bar))
    assert st == 200, raw[:200]
    up = json.loads(raw)
    return up["frames"][0]["frame"] if "frames" in up else up.get("frame")


def test_uploads_survives_its_last_frame_being_deleted(tmp_path):
    """The exact sequence the user hit: put one image in, take it out, and the place you
    put it into is still on the menu."""
    with Server(tmp_path / "d") as s:
        f = _seed(s, "only")
        st, arms = s.json("/api/arms")
        assert st == 200
        assert [a for a in arms if a["arm"] == "uploads"][0]["n_frames"] == 1

        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": f})
        assert st == 200, d

        st, arms = s.json("/api/arms")
        assert st == 200, arms
        up = [a for a in arms if a["arm"] == "uploads"]
        assert up, "Your images disappeared from the arm list when it emptied"
        assert up[0]["n_frames"] == 0, up[0]
        # and the counts are coherent zeros, not absent keys the client would render as
        # "undefined frames"
        for k in ("n_frames", "n_scaled", "n_cracks", "n_specimens"):
            assert up[0][k] == 0, (k, up[0])


def test_an_empty_uploads_arm_loads_as_empty_rather_than_failing(tmp_path):
    """THE HALF THAT MAKES THE OTHER HALF SAFE. Without this the always-visible option
    leads to loadArm()'s error branch, which clears the page and prints "Could not load
    the uploads arm" -- the dropdown entry would exist and be a dead end."""
    with Server(tmp_path / "d") as s:
        f = _seed(s, "gone")
        st, _ = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": f})
        assert st == 200
        st, rows = s.json("/api/frames?arm=uploads")
        assert st == 200, rows
        assert rows == [], rows


def test_every_other_arm_still_fails_loudly_when_it_has_nothing(tmp_path):
    """An empty sem/gated is a real error -- no SEM checkout, or a corpus that was never
    measured -- and must not render as a legitimately empty list. If this ever starts
    returning [], a machine with no reference corpus will silently show an empty SEM arm
    instead of saying why."""
    with Server(tmp_path / "d") as s:
        _seed(s)
        for arm in ("sem/gated", "sem/machine", "txm", "txm/machine", "nonsense"):
            st, _ = s.json(f"/api/frames?arm={arm.replace('/', '%2F')}")
            assert st == 404, f"{arm} returned {st}, not 404"


def test_a_specimen_scope_on_an_empty_uploads_arm_is_still_an_error(tmp_path):
    """The empty-list answer is for "show me Your images", not for "show me the frames of
    specimen X in Your images". The second names something that does not exist, and
    answering [] would let a stale scope look like an empty arm."""
    with Server(tmp_path / "d") as s:
        f = _seed(s, "sc")
        _post(s, "/api/delete_frame", {"arm": "uploads", "frame": f})
        st, _ = s.json("/api/frames?arm=uploads&specimen=whatever")
        assert st == 404, st


def test_uploads_is_not_invented_on_an_arm_that_has_frames(tmp_path):
    """The default must not overwrite a real record. If uploads already has frames the
    counts must be the measured ones, not zeros."""
    with Server(tmp_path / "d") as s:
        _seed(s, "a"), _seed(s, "b", 90)
        st, arms = s.json("/api/arms")
        up = [a for a in arms if a["arm"] == "uploads"][0]
        assert up["n_frames"] == 2, up
        assert up["n_cracks"] > 0, up
