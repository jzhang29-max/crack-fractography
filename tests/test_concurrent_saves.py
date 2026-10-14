#!/usr/bin/env python3
"""Saving a collection must not destroy the collections already saved.

/api/groups was the only one of the four writers of groups.json that did not hold
_DATASET_LOCK, so two concurrent saves read the same dict, each added its own entry, and
the second os.replace discarded the first. The user sees "Saved" and the collection is
simply gone -- and because _read_groups() catches a parse failure and returns {}, a
corrupted file shows up as "no saved collections yet" with no error anywhere.

Six concurrent requests is not a stress test here: the Save button in the Groups pane does
not disable itself while the request is in flight, so a double-click is two posts, and the
comment on _DATASET_LOCK already lists "two app windows, or the desktop app plus a browser"
among the cases it exists for.

MEASURED, by removing the lock again: 4 of 8 saves vanish. The per-writer temp name added
alongside is NOT demonstrated by this test -- with the lock held the writes are serialised
and the shared temp is never contended. It guards the case the in-process lock cannot, a
second server on the same data directory, and is kept on that basis.
"""
import json
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server, mask_png  # noqa: E402

N = 8


def test_concurrent_collection_saves_all_survive(tmp_path):
    with Server(tmp_path / "d") as s:
        st, raw = s.upload("a.png", mask_png(120, 90, 20))
        assert st == 200, raw[:200]
        member = [{"arm": "uploads", "frame": json.loads(raw)["frame"]}]
        status = [None] * N

        def save(i):
            st, _ = s.post("/api/groups",
                           json.dumps({"name": f"collection {i}", "frames": member}).encode(),
                           "application/json")
            status[i] = st

        ts = [threading.Thread(target=save, args=(i,)) for i in range(N)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()

        assert all(x == 200 for x in status), f"a save failed outright: {status}"
        st, got = s.json("/api/groups")
        assert st == 200, got
        g = got.get("groups")
        names = set(g) if isinstance(g, dict) else {x["name"] for x in g}
        lost = {f"collection {i}" for i in range(N)} - names
        assert not lost, (f"{len(lost)} of {N} saves reported success and are not on disk: "
                          f"{sorted(lost)}")


def test_no_temp_file_is_left_beside_the_users_data(tmp_path):
    """A failed or racing write must not leave debris in the data directory, which is where
    the user's own frames.json, cracks.json and uploads live."""
    with Server(tmp_path / "d") as s:
        st, raw = s.upload("a.png", mask_png(120, 90, 20))
        assert st == 200, raw[:200]
        member = [{"arm": "uploads", "frame": json.loads(raw)["frame"]}]
        for i in range(4):
            s.post("/api/groups",
                   json.dumps({"name": f"c{i}", "frames": member}).encode(),
                   "application/json")
        stray = [f for f in os.listdir(tmp_path / "d") if ".tmp" in f]
        assert not stray, f"temp files left in the data directory: {stray}"


def test_groups_json_stays_parseable(tmp_path):
    """_read_groups() swallows a ValueError and returns {}, so a corrupted file is not an
    error the user ever sees -- it is every collection disappearing silently."""
    with Server(tmp_path / "d") as s:
        st, raw = s.upload("a.png", mask_png(120, 90, 20))
        assert st == 200, raw[:200]
        member = [{"arm": "uploads", "frame": json.loads(raw)["frame"]}]
        ts = [threading.Thread(target=lambda i=i: s.post(
            "/api/groups", json.dumps({"name": f"g{i}", "frames": member}).encode(),
            "application/json")) for i in range(N)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        p = tmp_path / "d" / "groups.json"
        if p.exists():
            json.load(open(p, encoding="utf-8"))   # raises if the writers spliced it
