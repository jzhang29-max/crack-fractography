#!/usr/bin/env python3
"""Saving a collection must not destroy the collections already saved.

WHY THIS FILE EXISTS. /api/groups was the one writer of groups.json that did not hold
_DATASET_LOCK, and _write_json streamed every dataset through a FIXED `<path>.tmp`. Six
concurrent saves of six DIFFERENT collections, driven over real HTTP against a real
server, produced all three failures at once:

  * three of six answered HTTP 500 -- `FileNotFoundError: groups.json.tmp`, because the
    first os.replace consumed the temp file the others were still writing;
  * two that answered 200 and told the user "Saved" were not on disk afterwards, having
    been overwritten by a writer that had read the file before them;
  * on one round in six, groups.json itself stopped being JSON. _read_groups() catches
    that ValueError and returns {}, so the Groups pane shows "no saved collections yet"
    with no error anywhere, and the next save writes a one-entry file over the wreckage.

Six concurrent requests is not a stress test here. The pane's Save button does not
disable itself while the request is in flight, so a double-click is two posts; the app's
own note beside _DATASET_LOCK already lists "two app windows, or the desktop app plus a
browser" as cases it had to cover; and the uploads path calls _rebuild_uploads_specimen()
outside the lock, so an upload racing a save reaches the same temp file from a different
endpoint.

These assert on BEHAVIOUR, not on source text: the only way to pass is for the file on
disk to hold every collection that was told it had been saved.
"""
import json
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server, mask_png  # noqa: E402


def _post(s, path, obj):
    st, raw = s.post(path, json.dumps(obj).encode(), "application/json")
    return st, (json.loads(raw) if raw else None)


def _seed(s, name, bar=30, w=200, h=150):
    st, raw = s.upload(f"{name}.png", mask_png(w, h, bar))
    assert st == 200, raw[:300]
    up = json.loads(raw)
    return up["frames"][0]["frame"] if "frames" in up else up["frame"]


def _concurrent(fns):
    ts = [threading.Thread(target=f) for f in fns]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=60)
    assert not any(t.is_alive() for t in ts), "a request never came back"


def test_six_concurrent_saves_all_persist(tmp_path):
    """The whole defect in one assertion: what the server said it saved is on disk."""
    d = tmp_path / "d"
    with Server(d) as s:
        f = _seed(s, "cc")
        # A BULKY MEMBER LIST, so the write is not over before the next writer opens the
        # same temp file. 60 members is a plausible collection on a 393-frame corpus and
        # it widens the window the interleaving needs.
        members = [{"arm": "uploads", "frame": f}] * 60
        res = {}

        def save(i):
            def go():
                try:
                    st, _ = s.post("/api/groups",
                                   json.dumps({"name": f"c{i:02d}",
                                               "frames": members}).encode(),
                                   "application/json")
                    res[i] = st
                except Exception as e:                       # noqa: BLE001
                    res[i] = f"raised {e!r}"
            return go

        _concurrent([save(i) for i in range(6)])

        bad = {i: v for i, v in res.items() if v != 200}
        assert not bad, f"concurrent saves did not all succeed: {bad}"

        raw = open(os.path.join(str(d), "groups.json"), "rb").read()
        try:
            on_disk = json.loads(raw)
        except ValueError as e:
            raise AssertionError(
                f"groups.json is no longer JSON after six concurrent saves "
                f"({len(raw)} bytes): {e}. _read_groups() swallows this and reports no "
                f"saved collections at all.") from None
        gone = sorted(f"c{i:02d}" for i in range(6) if f"c{i:02d}" not in on_disk)
        assert not gone, f"saves that answered 200 and are not on disk: {gone}"

        # And the server agrees with the file -- a cached {} would read as "none saved".
        st, g = s.json("/api/groups")
        assert st == 200
        assert sorted(g["groups"]) == [f"c{i:02d}" for i in range(6)], sorted(g["groups"])
        assert all(len(v) == 1 for v in g["groups"].values()), (
            "a group is a set of frames; 60 copies of one frame should store once")


def test_a_save_racing_a_frame_delete_keeps_both_effects(tmp_path):
    """delete_frame prunes groups.json from inside the lock; a save that ignored the lock
    met it on the same temp file from another endpoint entirely.

    HONEST LABEL: this one is a boundary check, not a regression test. Run against the
    pre-fix code it passed 5 rounds out of 5 -- delete_frame moves files, rewrites
    frames.json and cracks.json and clears the scale before it touches groups.json, so the
    two writes rarely overlap. The regression is caught by the six-way save above; this
    asserts the invariant the pair must keep and would catch a future delete that writes
    groups.json earlier.
    """
    with Server(tmp_path / "d") as s:
        keep, doomed = _seed(s, "ka", 20), _seed(s, "kb", 50)
        _post(s, "/api/groups", {"name": "holds the doomed frame",
                                 "frames": [{"arm": "uploads", "frame": doomed},
                                            {"arm": "uploads", "frame": keep}]})
        res = {}

        def do_delete():
            res["delete"] = s.post("/api/delete_frame",
                                   json.dumps({"arm": "uploads",
                                               "frame": doomed}).encode(),
                                   "application/json")[0]

        def do_save():
            res["save"] = s.post("/api/groups",
                                 json.dumps({"name": "saved during the delete",
                                             "frames": [{"arm": "uploads",
                                                         "frame": keep}] * 40}).encode(),
                                 "application/json")[0]

        _concurrent([do_delete, do_save])
        assert res == {"delete": 200, "save": 200}, res

        st, g = s.json("/api/groups")
        assert st == 200
        assert "saved during the delete" in g["groups"], (
            f"the save was lost to the delete's own write: {sorted(g['groups'])}")
        assert g["groups"]["holds the doomed frame"] == [
            {"arm": "uploads", "frame": keep}], (
            f"the prune was lost to the save: {g['groups'].get('holds the doomed frame')}")


@pytest.mark.parametrize("members", [
    [{"nope": 1}],                                  # no arm, no frame
    [{"arm": "uploads"}],                           # arm only
    [{"frame": "x"}],                               # frame only
    ["just-the-frame-name"],                        # not an object at all -> used to 500
    [None],
])
def test_a_collection_is_never_stored_empty(tmp_path, members):
    """`{"name": []}` is a collection the pane offers as "0 frames", that group_stats then
    rejects as though it did not exist, and that delete_frame's pruner goes out of its way
    never to leave behind. The members check ran before the filter, so the filter could
    still empty it."""
    with Server(tmp_path / "d") as s:
        _seed(s, "ea")
        st, body = _post(s, "/api/groups", {"name": "hollow", "frames": members})
        assert st == 400, f"{members!r} was accepted: {body}"
        st, g = s.json("/api/groups")
        assert g["groups"] == {}, f"an empty collection was stored anyway: {g['groups']}"
        p = os.path.join(str(tmp_path / "d"), "groups.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                assert json.load(fh) == {}, "it reached the file even so"


def test_a_frame_listed_twice_is_measured_once_and_says_so(tmp_path):
    """_collect() resolves members through a set, so a duplicate is pooled once -- which is
    right, double-counting it would be worse. The reporting was what lied: three requested,
    two frames, nothing missing."""
    with Server(tmp_path / "d") as s:
        a, b = _seed(s, "da", 20), _seed(s, "db", 60)
        dup = [{"arm": "uploads", "frame": a}, {"arm": "uploads", "frame": a},
               {"arm": "uploads", "frame": b}]
        st, g = _post(s, "/api/groups", {"name": "dup", "frames": dup})
        assert st == 200
        assert [m["frame"] for m in g["groups"]["dup"]] == [a, b], g["groups"]["dup"]

        # Through an ad-hoc list, which the pane sends and which the store never sees.
        st, d = _post(s, "/api/group_stats", {"frames": dup})
        assert st == 200, d
        assert d["n_frames"] == 2 and d["missing"] == [], d
        assert d["duplicates_ignored"] == 1, (
            "requested, measured and missing must add up: "
            f"requested={d['requested']} n_frames={d['n_frames']} "
            f"missing={len(d['missing'])} duplicates={d.get('duplicates_ignored')}")
        assert d["requested"] == d["n_frames"] + len(d["missing"]) + d["duplicates_ignored"]
