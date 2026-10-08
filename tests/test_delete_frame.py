#!/usr/bin/env python3
"""Deleting a frame from the sidebar.

THIS IS THE ONLY ENDPOINT THAT REMOVES ANYTHING, and the app sits beside two repositories
of irreplaceable hand-labelled research data. The refusals are therefore the feature; the
happy path is the easy part.

Written after the author of the endpoint deleted two of this user's frames by accident
while clearing test artifacts. Hence: files are moved to a trash folder rather than
unlinked, and a name that is not a frame cannot reach os.replace however it is spelled.
"""
import io
import json
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server, mask_png  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _post(s, path, obj):
    st, raw = s.post(path, json.dumps(obj).encode(), "application/json")
    return st, (json.loads(raw) if raw else None)


def _seed(s, name="img", bar=40):
    st, raw = s.upload(f"{name}.png", mask_png(200, 150, bar))
    assert st == 200, raw[:200]
    up = json.loads(raw)
    return up["frames"][0]["frame"] if "frames" in up else up.get("frame")


# --- THE REFUSALS ----------------------------------------------------------------------
@pytest.mark.parametrize("arm", ["sem/gated", "sem/machine", "txm", "txm/machine",
                                 "uploadsX", "", "UPLOADS", "../uploads"])
def test_only_the_uploads_arm_can_be_deleted_from(tmp_path, arm):
    """The SEM and TXM arms are research masks this app has never written to. Exact
    equality, not startswith: "uploadsX" must not slip through."""
    with Server(tmp_path / "d") as s:
        f = _seed(s)
        st, d = _post(s, "/api/delete_frame", {"arm": arm, "frame": f})
        assert st == 400, f"{arm!r} was accepted: {d}"
        # and nothing was removed
        assert any(r["frame"] == f for r in s.dataset("frames"))


@pytest.mark.parametrize("bad", [
    "../../../etc/passwd",
    "../uploads/other",
    "..",
    "/absolute/path",
    "name/with/slash",
    "a\\x00b",
    ".hidden",
])
def test_a_frame_name_that_is_not_one_cannot_reach_the_filesystem(tmp_path, bad):
    """THE ATTACK THIS ENDPOINT WAS MOST LIKELY TO SHIP WITH. `arm == "uploads"` constrains
    the ARM, not the NAME, and no other uploads write path in the app validates its name --
    so a crafted frame would have moved a research mask into the trash."""
    with Server(tmp_path / "d") as s:
        _seed(s)
        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": bad})
        assert st in (400, 404), f"{bad!r} was accepted: {d}"


def test_the_name_check_stands_alone_even_with_a_matching_record(tmp_path):
    """THE PREVIOUS VERSION OF THIS WAS VACUOUS. Every traversal name it tried was refused
    by the frames.json lookup with a 404 long before SAFE_FRAME was consulted, so deleting
    the regex entirely left the suite green -- confirmed by doing exactly that.

    Two things guard this endpoint and they must be tested apart: the record check (a name
    that is not a frame is not a frame) and the name check (a name that IS a record must
    still be unusable as a path). Here a malicious name is planted directly in frames.json
    so the record check passes and only the regex is left."""
    d = tmp_path / "d"
    with Server(d) as s:
        _seed(s, "real")
        evil = "../../../../tmp/pwned"
        with open(os.path.join(str(d), "frames.json"), encoding="utf-8") as fh:
            fr = json.load(fh)
        fr.append({"arm": "uploads", "frame": evil, "specimen": "uploaded"})
        with open(os.path.join(str(d), "frames.json"), "w", encoding="utf-8") as fh:
            json.dump(fr, fh)
        st, got = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": evil})
        assert st == 400, f"a path-shaped frame name was accepted: {got}"
        assert "path" in json.dumps(got).lower() or "name" in json.dumps(got).lower()


def test_an_unknown_frame_is_refused_before_any_file_is_touched(tmp_path):
    with Server(tmp_path / "d") as s:
        f = _seed(s)
        before = sorted(os.listdir(os.path.join(str(tmp_path / "d"), "uploads")))
        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": "nope"})
        assert st == 404, d
        assert sorted(os.listdir(os.path.join(str(tmp_path / "d"), "uploads"))) == before


def test_deleting_a_frame_other_frames_were_cut_from_is_refused(tmp_path):
    """A crop records its parent, and the lineage walk is what refuses to compare a crop
    against the frame it came from. Orphan the parent and that guard stops finding the
    overlap -- with no error, which is the worst way for a safety check to fail."""
    with Server(tmp_path / "d") as s:
        f = _seed(s, "parent")
        st, c = _post(s, "/api/crop", {"arm": "uploads", "frame": f,
                                       "x": 0, "y": 0, "w": 100, "h": 100})
        assert st == 200, c
        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": f})
        assert st == 409, d
        assert c["frame"] in json.dumps(d), "the refusal does not name the child"
        assert any(r["frame"] == f for r in s.dataset("frames"))
        # the child can go first, and then the parent
        st, _ = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": c["frame"]})
        assert st == 200
        st, _ = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": f})
        assert st == 200


# --- WHAT A DELETE ACTUALLY DOES ---------------------------------------------------------
def test_a_delete_trashes_the_files_and_clears_every_dataset(tmp_path):
    with Server(tmp_path / "d") as s:
        keep = _seed(s, "keepme", bar=30)
        doomed = _seed(s, "doomed", bar=60)
        updir = os.path.join(str(tmp_path / "d"), "uploads")
        assert os.path.exists(os.path.join(updir, f"{doomed}_gated.png"))
        n_before = len([c for c in s.dataset("cracks") if c["frame"] == doomed])
        assert n_before > 0, "the seed produced no cracks; this test proves nothing"

        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": doomed})
        assert st == 200, d
        assert d["crack_rows_removed"] == n_before

        assert not os.path.exists(os.path.join(updir, f"{doomed}_gated.png"))
        assert not any(r["frame"] == doomed for r in s.dataset("frames"))
        assert not any(c["frame"] == doomed for c in s.dataset("cracks"))
        # the other frame is untouched
        assert any(r["frame"] == keep for r in s.dataset("frames"))
        assert os.path.exists(os.path.join(updir, f"{keep}_gated.png"))

        # TRASHED, NOT UNLINKED.
        trash = os.path.join(str(tmp_path / "d"), "trash")
        assert os.path.isdir(trash), "nothing was trashed"
        got = os.listdir(trash)
        assert any(doomed in n for n in got), got
        assert d["files_trashed"], d


def test_the_trash_is_not_where_the_corpus_batch_will_find_it(tmp_path):
    """analysis/batch.py re-measures the uploads arm by globbing UPLOADS/*_gated.png and
    replacing every uploads row wholesale, so a trashed file left as a sibling there comes
    back as a frame on the next corpus measurement. And it must not go in the render cache,
    whose trim loop os.remove()s what it finds and breaks on the first OSError -- a
    directory in there silently stops the size budget being enforced at all."""
    with Server(tmp_path / "d") as s:
        f = _seed(s)
        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": f})
        assert st == 200, d
        data = str(tmp_path / "d")
        trash = os.path.realpath(d["trash_dir"])
        assert trash == os.path.realpath(os.path.join(data, "trash")), trash
        assert os.path.realpath(os.path.join(data, "uploads")) not in trash
        assert "render_cache" not in trash
        # and the glob the batch uses finds nothing
        import glob as _g
        assert _g.glob(os.path.join(data, "uploads", "*_gated.png")) == []


def test_a_crop_takes_its_sidecars_with_it(tmp_path):
    """A crop owns three files, not one. A glob of `<frame>*` would instead sweep up any
    frame whose name merely begins with this one's, so they are listed explicitly."""
    with Server(tmp_path / "d") as s:
        f = _seed(s, "sc")
        st, c = _post(s, "/api/crop", {"arm": "uploads", "frame": f,
                                       "x": 0, "y": 0, "w": 100, "h": 100})
        assert st == 200, c
        updir = os.path.join(str(tmp_path / "d"), "uploads")
        Image.new("L", (100, 100), 90).save(os.path.join(updir, f"{c['frame']}_original.png"))
        assert os.path.exists(os.path.join(updir, f"{c['frame']}_ascut.png"))

        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": c["frame"]})
        assert st == 200, d
        for suf in ("_gated.png", "_ascut.png", "_original.png"):
            assert not os.path.exists(os.path.join(updir, c["frame"] + suf)), suf
        assert len(d["files_trashed"]) == 3, d["files_trashed"]
        # the parent kept its own
        assert os.path.exists(os.path.join(updir, f"{f}_gated.png"))


def test_a_deleted_frame_is_pruned_from_saved_groups(tmp_path):
    """Groups resolve members by name at request time and nothing prunes them, so a stale
    member silently shrinks a group and reports it only in a field no screen renders."""
    with Server(tmp_path / "d") as s:
        a, b = _seed(s, "ga"), _seed(s, "gb")
        st, _ = _post(s, "/api/groups", {"name": "mine",
                                         "frames": [{"arm": "uploads", "frame": a},
                                                    {"arm": "uploads", "frame": b}]})
        assert st == 200
        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": a})
        assert st == 200, d
        assert d["groups_pruned"] == ["mine"], d
        st, g = s.json("/api/groups")
        assert [m["frame"] for m in g["groups"]["mine"]] == [b]


def test_deleting_the_last_frame_leaves_a_coherent_empty_arm(tmp_path):
    with Server(tmp_path / "d") as s:
        f = _seed(s)
        st, d = _post(s, "/api/delete_frame", {"arm": "uploads", "frame": f})
        assert st == 200, d
        assert s.dataset("frames") == []
        assert [r for r in s.dataset("specimens") if r.get("arm") == "uploads"] == []
