#!/usr/bin/env python3
"""A frame the app will CREATE, it must also be able to delete.

/api/upload names a frame from the uploaded filename, but delete, rename, review and
mask_edit all gate on SAFE_FRAME = [A-Za-z0-9][A-Za-z0-9._-]*, which upload itself never
checked. So a file called "_scan01.tif", "my scan.tif" or a macOS "._foo" segmented fine,
got measured, wrote crack rows -- and then could never be removed or edited, with the 400
coming from a different endpoint than the one that made it.

Found by uploading a real micrograph through the running app as "__cf_e2e_test": it
segmented, wrote 42 crack rows, and delete_frame answered "'__cf_e2e_test' is not a frame
name this will build a path from". The frame had to be removed by editing frames.json.

The fix is in canonical_stem, the one exported definition, so every caller gets it.
"""
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "analysis"))
from liveserver import Server, mask_png  # noqa: E402

SAFE_FRAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\-]*\Z")
HOSTILE = ["_scan01.png", "__double.png", ".hidden.png", "my scan.png", "a+b.png", "___.png"]


@pytest.mark.parametrize("filename", HOSTILE)
def test_a_name_the_app_accepts_is_a_name_it_can_delete(filename, tmp_path):
    with Server(tmp_path / "d") as s:
        st, raw = s.upload(filename, mask_png(160, 120, 30))
        assert st == 200, raw[:300]
        frame = json.loads(raw)["frame"]
        assert SAFE_FRAME.match(frame), f"upload created {frame!r}, which SAFE_FRAME rejects"
        st, raw = s.post("/api/delete_frame",
                         json.dumps({"arm": "uploads", "frame": frame}).encode(),
                         "application/json")
        assert st == 200, f"created {frame!r} from {filename!r} but could not delete it: {raw[:300]}"


def test_canonical_stem_is_idempotent_on_hostile_names():
    """The sanitiser runs BEFORE the mask-suffix loop and that order is load-bearing.
    Sanitising afterwards turns "foo mask.png" into "foo_mask", which a second call then
    strips to "foo" -- canonical_stem is applied twice (endpoint, then measure_path), so
    a non-idempotent version silently splits the frame record from its mask and rows."""
    from measure import canonical_stem

    for name in HOSTILE + ["foo mask.png", "demo_gated.png", "_smoke_mask_gated.png",
                           "260622_316_H_b2_back_CBS_01.png"]:
        once = canonical_stem(name)
        assert canonical_stem(once) == once, f"{name!r}: {once!r} -> {canonical_stem(once)!r}"
        assert SAFE_FRAME.match(once), f"{name!r} canonicalised to {once!r}, still unsafe"


def test_the_fix_cannot_rename_an_existing_frame():
    """Every real frame name in this corpus is already safe, so the sanitiser must be a
    no-op on all of them. If it renames one, stored masks and crack rows stop resolving."""
    from measure import canonical_stem

    for name in ("260622_316_H_b2_back_CBS_01", "MAR_H_AS_CBS_0001", "AS_24hr_SE_Side_006",
                 "260708_316_H_b2_front_CBS_004", "MAR_Amb_Cast_ETD_0003",
                 "MAR_H_HIP_CBS_0002__crop_3122_120_512x512"):
        assert canonical_stem(name) == name, f"{name!r} would be renamed"
