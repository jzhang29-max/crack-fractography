#!/usr/bin/env python3
"""A frame, its crack rows and its mask file must all answer to the same name.

They did not, twice. First the upload endpoint used the raw filename while measure_path
used the stripped one, so /api/cracks returned 0 of 305 rows it had just measured and
/api/mask 404'd while the read-out worked -- the frame looked measured. Then the fix for
that applied the stripping TWICE for a double-suffixed name, reproducing the same split.
"""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "analysis"))
from measure import MASK_SUFFIXES, canonical_stem   # noqa: E402


def test_canonicalising_twice_gives_the_same_answer():
    """The endpoint canonicalises to name the file; measure_path canonicalises to name the
    frame. If the two disagree the frame's rows and mask are unreachable, so f(f(x)) must
    equal f(x) for every name."""
    for n in ("_smoke_mask_gated", "weld_mask", "x_crack_mask", "a_gated", "plain",
              "a_gated_gated", "b_mask_mask", "c_machine_gated", "d_crack_mask_gated"):
        once = canonical_stem(n)
        assert canonical_stem(once) == once, f"{n!r}: {n} -> {once} -> {canonical_stem(once)}"


def test_a_name_made_only_of_suffixes_never_canonicalises_to_nothing():
    """_gated.png produced a frame named "" — which sorted first and became the app's
    default selection, so opening the app showed a frame with no name.

    The guarantee is non-emptiness, not that the name is untouched: "_crack_mask" losing
    its "_mask" to become "_crack" is odd but harmless, whereas an empty frame name breaks
    every lookup keyed on it."""
    for n in list(MASK_SUFFIXES) + ["_gated.png", "_mask_gated", "_gated_gated"]:
        got = canonical_stem(n)
        assert got, f"{n!r} canonicalised away to an empty name"
    assert canonical_stem("_gated.png") == "_gated"


def test_the_longest_suffix_wins():
    """_crack_mask also ends with _mask; stripping the shorter one first leaves _crack."""
    assert canonical_stem("frame7_crack_mask") == "frame7"


def test_the_project_s_own_export_shape_round_trips():
    """<frame>_gated.png is what this project exports, so it is the likeliest upload."""
    assert canonical_stem("260622_316_H_b4_CBS_01_gated.png") == "260622_316_H_b4_CBS_01"


def test_a_plain_name_is_untouched():
    assert canonical_stem("my_crack_photo.png") == "my_crack_photo"


def test_the_upload_endpoint_refuses_a_colliding_name():
    """weld.png and weld_mask.png are both frame "weld". The second used to replace the
    first, and the only sign was a crack count changing on a row nobody was looking at."""
    src = open(os.path.join(REPO, "app", "server.py")).read()
    up = src[src.index("async def upload("):src.index("def _rebuild_uploads_specimen")]
    assert "409" in up, "a colliding upload must be refused, not silently overwritten"
    assert "source_filename" in up, (
        "the stored filename is what distinguishes a re-upload from a collision")


def test_the_smoke_check_actually_measures():
    """It printed "OK: starts, serves, and measures" while its only measurement assertion
    read health['capabilities']['measure_uploaded_mask'] — a literal True in server.py. It
    is the release gate, and it could not fail."""
    src = open(os.path.join(REPO, "packaging", "smoke_check.py")).read()
    assert "/api/upload" in src, "the gate must upload something"
    assert "/api/cracks" in src and "/api/mask" in src, (
        "the gate must confirm the three views of a frame agree — that is the bug it missed")
    # The old assertion, not a mention of it: the comment explaining why it was removed
    # legitimately quotes the expression.
    assert 'if not health["capabilities"]["measure_uploaded_mask"]:' not in src, (
        "asserting on a literal True is not a measurement check")
