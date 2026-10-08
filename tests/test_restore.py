#!/usr/bin/env python3
"""Undoing a delete.

WHY THIS ENDPOINT EXISTS. The sidebar's cross used to arm itself and wait for a second
click. A confirmation taxes every correct delete to catch the rare wrong one, and people
learn to click through it; the user's report was that it "ask for two steps which is
really unhelpful". So the cross acts at once and the status line offers Undo for 25
seconds -- which is only honest if the way back is real.

WHAT THESE TESTS ARE ACTUALLY GUARDING. Putting the PNG back is the easy half and it is
not the half that goes wrong. The obvious implementation -- move the files back, call
/api/remeasure -- passes a "the frame is in the list again" test while silently returning
a DIFFERENT frame: remeasure reads the deleted record for the modality, the specimen and
the lineage, and the delete just removed it. A restored TXM crop would come back measured
as SEM, under specimen "unparsed", with cropped_from gone -- which is the field that lets
its strokes reach the parent and that stops a group comparing it against the frame it was
cut from. The crack rows, the user's scale and the group memberships have no path back at
all. Hence a record written into the trash beside the files, and hence the tests below
assert on the fields a re-measure would lose rather than on the row merely existing.

Checked by sabotage: replacing the whole record-based restore with "move the files back
and call remeasure" fails exactly four of these -- comes_back_with_the_record_it_had,
still_knows_its_parent, keeps_its_scale and goes_back_into_its_groups -- and leaves the
other twelve green, so those four are the ones carrying the claim.
"""
import io
import json
import os
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server, mask_png  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from app import paths as P  # noqa: E402

SEM = P.sem_repo()
needs_sem = pytest.mark.skipif(
    not SEM or not os.path.isdir(os.path.join(SEM, "interior_active_learning", "paint")),
    reason="no sem-crack-detector checkout on this machine")


def _post(s, path, obj):
    st, raw = s.post(path, json.dumps(obj).encode(), "application/json")
    return st, (json.loads(raw) if raw else None)


def _seed(s, name="img", bar=40):
    st, raw = s.upload(f"{name}.png", mask_png(200, 150, bar))
    assert st == 200, raw[:200]
    up = json.loads(raw)
    return up["frames"][0]["frame"] if "frames" in up else up.get("frame")


def _row(s, frame, arm="uploads"):
    return next((r for r in s.dataset("frames")
                 if r.get("arm") == arm and r.get("frame") == frame), None)


# --- THE WHOLE FRAME COMES BACK --------------------------------------------------------
def test_a_deleted_frame_comes_back_with_the_record_it_had(tmp_path):
    """Not a frame with the same name -- the same frame. The record is compared field for
    field, because the failure this is written against produces a row that is present,
    plausible and different."""
    with Server(tmp_path / "d") as s:
        f = _seed(s, "whole")
        before = _row(s, f)
        n_cracks = len([c for c in s.dataset("cracks") if c["frame"] == f])
        assert before and n_cracks > 0, "the seed produced nothing to lose"

        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": f})
        assert st == 200, d
        assert _row(s, f) is None

        st, r = _post(s, "/api/restore",
                      {"kind": "frame", "arm": "uploads", "frame": f, "record": d["record"]})
        assert st == 200, r
        assert _row(s, f) == before, "the frame came back as a different frame"
        assert len([c for c in s.dataset("cracks") if c["frame"] == f]) == n_cracks
        up = os.path.join(str(tmp_path / "d"), "uploads")
        assert os.path.exists(os.path.join(up, f"{f}_gated.png"))
        # and the specimen card is rebuilt rather than left describing an absent frame
        assert [x for x in s.dataset("specimens") if x.get("arm") == "uploads"]


def test_a_restored_crop_still_knows_its_parent(tmp_path):
    """THE FIELD A RE-MEASURE LOSES AND NOTHING ELSE NOTICES. cropped_from is what lets a
    crop's strokes be sent back into the parent's correction mask, and what makes a group
    refuse to compare a crop against the frame it was cut from. If a restore drops it,
    both stop working with no error at all."""
    with Server(tmp_path / "d") as s:
        parent = _seed(s, "par")
        st, c = _post(s, "/api/crop", {"arm": "uploads", "frame": parent,
                                       "x": 10, "y": 10, "w": 100, "h": 80})
        assert st == 200, c
        child = c["frame"]
        lineage = _row(s, child).get("cropped_from")
        assert lineage, "the crop was not recorded as a crop; this test proves nothing"

        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": child})
        assert st == 200, d
        st, r = _post(s, "/api/restore",
                      {"kind": "frame", "frame": child, "record": d["record"]})
        assert st == 200, r
        assert _row(s, child).get("cropped_from") == lineage


def test_a_restored_frame_keeps_its_scale(tmp_path):
    """The delete clears the user's nm/px -- the scale store is keyed by bare stem, so it
    has to. Restoring the pixels without it leaves every micrometre column wrong."""
    with Server(tmp_path / "d") as s:
        f = _seed(s, "scaled")
        st, raw = s.post(f"/api/scale?arm=uploads&frame={f}&nm_per_px=77.0")
        assert st == 200, raw[:200]
        assert _row(s, f).get("scale_known"), "the scale did not take; test proves nothing"

        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": f})
        assert st == 200, d
        assert d["scale_cleared"] is True, d
        st, r = _post(s, "/api/restore",
                      {"kind": "frame", "frame": f, "record": d["record"]})
        assert st == 200, r
        assert r["scale_restored"] is True, r
        assert _row(s, f).get("scale_known"), "the frame came back without its scale"


def test_a_restored_frame_goes_back_into_its_groups(tmp_path):
    """A group that lost its last member is popped, so putting one member back into a
    group that no longer exists has to recreate the whole list, not just the one row."""
    with Server(tmp_path / "d") as s:
        a, b = _seed(s, "ga"), _seed(s, "gb")
        st, _ = _post(s, "/api/groups", {"name": "mine",
                                         "frames": [{"arm": "uploads", "frame": a},
                                                    {"arm": "uploads", "frame": b}]})
        assert st == 200
        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": a})
        assert st == 200 and d["groups_pruned"] == ["mine"], d

        st, r = _post(s, "/api/restore",
                      {"kind": "frame", "frame": a, "record": d["record"]})
        assert st == 200, r
        st, g = s.json("/api/groups")
        assert sorted(m["frame"] for m in g["groups"]["mine"]) == sorted([a, b])


def test_a_restored_crop_brings_its_sidecars(tmp_path):
    """A crop owns three files. Two of them back is a frame that renders without its
    original, which is the state the overlay editor cannot open."""
    with Server(tmp_path / "d") as s:
        f = _seed(s, "sc")
        st, c = _post(s, "/api/crop", {"arm": "uploads", "frame": f,
                                       "x": 0, "y": 0, "w": 100, "h": 100})
        assert st == 200, c
        up = os.path.join(str(tmp_path / "d"), "uploads")
        Image.new("L", (100, 100), 90).save(os.path.join(up, f"{c['frame']}_original.png"))

        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": c["frame"]})
        assert st == 200 and len(d["files_trashed"]) == 3, d
        st, r = _post(s, "/api/restore",
                      {"kind": "frame", "frame": c["frame"], "record": d["record"]})
        assert st == 200, r
        for suf in ("_gated.png", "_ascut.png", "_original.png"):
            assert os.path.exists(os.path.join(up, c["frame"] + suf)), suf


# --- THE REFUSALS ----------------------------------------------------------------------
@pytest.mark.parametrize("rec", [
    "../../../etc/passwd", "../uploads/x", "..", "/abs/path", "a/b", "",
])
def test_a_record_name_that_is_not_one_cannot_reach_the_filesystem(tmp_path, rec):
    """The record name arrives from the client and is joined onto the trash path."""
    with Server(tmp_path / "d") as s:
        f = _seed(s)
        st, d = _post(s, "/api/restore",
                      {"kind": "frame", "frame": f, "record": rec})
        assert st in (400, 404), f"{rec!r} was accepted: {d}"


def test_a_record_cannot_restore_a_frame_it_is_not_for(tmp_path):
    """Two deletes leave two records in the trash. Pairing the wrong one with a frame name
    would write one frame's measurements under the other's name."""
    with Server(tmp_path / "d") as s:
        a, b = _seed(s, "ra", 40), _seed(s, "rb", 90)
        st, da = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": a})
        assert st == 200
        st, db = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": b})
        assert st == 200
        st, r = _post(s, "/api/restore",
                      {"kind": "frame", "frame": a, "record": db["record"]})
        assert st == 400, r
        assert _row(s, a) is None and _row(s, b) is None


def test_restoring_twice_is_refused_rather_than_duplicating(tmp_path):
    with Server(tmp_path / "d") as s:
        f = _seed(s, "twice")
        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": f})
        assert st == 200
        st, _ = _post(s, "/api/restore",
                      {"kind": "frame", "frame": f, "record": d["record"]})
        assert st == 200
        st, r = _post(s, "/api/restore",
                      {"kind": "frame", "frame": f, "record": d["record"]})
        assert st == 404, r
        assert len([x for x in s.dataset("frames") if x["frame"] == f]) == 1


def test_a_research_arm_is_not_restorable_as_a_frame(tmp_path):
    """Symmetry with the delete: only uploads frames are ever deleted, so only uploads
    frames are ever put back. A sem/* restore would write a research row from a file the
    client named."""
    with Server(tmp_path / "d") as s:
        f = _seed(s)
        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": f})
        assert st == 200
        st, r = _post(s, "/api/restore",
                      {"kind": "frame", "arm": "sem/gated", "frame": f,
                       "record": d["record"]})
        assert st == 400, r


def test_restore_needs_a_kind_it_knows(tmp_path):
    with Server(tmp_path / "d") as s:
        f = _seed(s)
        for kind in ("", "everything", "mask", None):
            st, r = _post(s, "/api/restore", {"kind": kind, "frame": f, "record": "x"})
            assert st == 400, (kind, r)


# --- A DISCARDED CORRECTION ------------------------------------------------------------
def _sem_frame_with_mask():
    """A real gated mask to paint on. The dataset is empty in a fresh test server, so the
    frame is found on disk in the SEM checkout rather than asked of /api/frames."""
    if not SEM:
        return None
    d = os.path.join(SEM, "crack_export", "derived", "gated_masks")
    if not os.path.isdir(d):
        return None
    for f in sorted(os.listdir(d)):
        if f.endswith("_gated.png"):
            return f[:-len("_gated.png")]
    return None


SEM_FRAME = _sem_frame_with_mask()


@needs_sem
@pytest.mark.skipif(SEM_FRAME is None, reason="no gated SEM mask available")
def test_a_discarded_correction_comes_back(tmp_path):
    """The other half of the cross. Here re-measuring IS right: the research record was
    never removed, so remeasure still finds the prior it needs."""
    with Server(tmp_path / "d") as s:
        name = SEM_FRAME
        st, raw = s.get(f"/api/mask/sem/gated/{name}")
        assert st == 200
        orig = np.array(Image.open(io.BytesIO(raw)).convert("L"))
        painted = orig.copy()
        ys, xs = np.where(orig < 128)
        if len(ys) < 500:
            pytest.skip(f"{name} has too little marked area to erase")
        painted[ys[:500], xs[:500]] = 255
        b = io.BytesIO(); Image.fromarray(painted, mode="L").save(b, "PNG")
        st, raw = s.upload(f"{name}.png", b.getvalue(),
                           path=f"/api/mask_edit?arm=sem/gated&frame={name}")
        assert st == 200, raw[:300]
        assert _row(s, name, "sem/gated").get("edited") is True

        st, d = _post(s, "/api/discard_edit", {"arm": "sem/gated", "frame": name})
        assert st == 200, d
        assert not _row(s, name, "sem/gated").get("edited")

        st, r = _post(s, "/api/restore", {"kind": "edit", "arm": "sem/gated",
                                          "frame": name, "files": [d["trashed_to"]]})
        assert st == 200, r
        assert _row(s, name, "sem/gated").get("edited") is True
        st, raw = s.get(f"/api/mask/sem/gated/{name}")
        back = np.array(Image.open(io.BytesIO(raw)).convert("L"))
        assert np.array_equal(back, painted), "the strokes that came back are not the ones"


# --- UNDO PUTS BACK WHAT WAS THERE; IT DOES NOT OVERWRITE WHAT IS THERE NOW -------------
def test_undo_is_refused_when_the_name_has_been_used_again(tmp_path):
    """The offer stands for 25 seconds. That is long enough to delete a frame and upload
    a new one under the same name, and a restore that just moved the old file back would
    overwrite the new one and report success."""
    with Server(tmp_path / "d") as s:
        f = _seed(s, "reused", 40)
        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": f})
        assert st == 200, d
        # the same name, a different mask -> a different measurement
        st, raw = s.upload("reused.png", mask_png(200, 150, 95))
        assert st == 200, raw[:200]
        fresh = _row(s, f)
        assert fresh, "the re-upload did not land; this test proves nothing"

        st, r = _post(s, "/api/restore",
                      {"kind": "frame", "frame": f, "record": d["record"]})
        assert st == 409, r
        assert _row(s, f) == fresh, "the re-uploaded frame was overwritten"
        up = os.path.join(str(tmp_path / "d"), "uploads")
        assert os.path.exists(os.path.join(up, f"{f}_gated.png"))


def test_undoing_a_delete_does_not_undo_a_later_change_to_the_group(tmp_path):
    """Restoring a member must merge into the group as it is now. Writing the saved list
    wholesale would drop anything added to that group since the delete."""
    with Server(tmp_path / "d") as s:
        a, b, c = _seed(s, "ma"), _seed(s, "mb"), _seed(s, "mc")
        st, _ = _post(s, "/api/groups", {"name": "mine",
                                         "frames": [{"arm": "uploads", "frame": a},
                                                    {"arm": "uploads", "frame": b}]})
        assert st == 200
        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": a})
        assert st == 200, d
        # someone adds a third frame while the undo offer is still up
        st, _ = _post(s, "/api/groups", {"name": "mine",
                                         "frames": [{"arm": "uploads", "frame": b},
                                                    {"arm": "uploads", "frame": c}]})
        assert st == 200
        st, r = _post(s, "/api/restore",
                      {"kind": "frame", "frame": a, "record": d["record"]})
        assert st == 200, r
        st, g = s.json("/api/groups")
        assert sorted(m["frame"] for m in g["groups"]["mine"]) == sorted([a, b, c])


@needs_sem
@pytest.mark.skipif(SEM_FRAME is None, reason="no gated SEM mask available")
def test_undoing_a_discard_is_refused_when_a_new_correction_exists(tmp_path):
    with Server(tmp_path / "d") as s:
        name = SEM_FRAME
        st, raw = s.get(f"/api/mask/sem/gated/{name}")
        assert st == 200
        orig = np.array(Image.open(io.BytesIO(raw)).convert("L"))
        ys, xs = np.where(orig < 128)
        if len(ys) < 900:
            pytest.skip(f"{name} has too little marked area")

        def paint(n):
            a = orig.copy(); a[ys[:n], xs[:n]] = 255
            b = io.BytesIO(); Image.fromarray(a, mode="L").save(b, "PNG")
            st, raw = s.upload(f"{name}.png", b.getvalue(),
                               path=f"/api/mask_edit?arm=sem/gated&frame={name}")
            assert st == 200, raw[:300]
            return a

        paint(500)
        st, d = _post(s, "/api/discard_edit", {"arm": "sem/gated", "frame": name})
        assert st == 200, d
        second = paint(900)                     # a different correction, drawn after

        st, r = _post(s, "/api/restore", {"kind": "edit", "arm": "sem/gated",
                                          "frame": name, "files": [d["trashed_to"]]})
        assert st == 409, r
        st, raw = s.get(f"/api/mask/sem/gated/{name}")
        assert np.array_equal(np.array(Image.open(io.BytesIO(raw)).convert("L")), second)
