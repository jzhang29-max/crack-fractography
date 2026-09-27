#!/usr/bin/env python3
"""The served dataset must follow the file on disk, for the life of the process.

app/server.py caches frames/cracks/specimens.json in a module-level dict. Keyed on the
name alone, a server started before an out-of-process `analysis/batch.py` run served the
pre-run dataset forever. Observed 2026-09-27, and the shape of the failure is why this
file exists: the page served the CURRENT app.js against the OLD records, so a row showed
new caption prose beside a stale number and a newly added row was absent because its
field did not exist in the cached records. It looked live.

The writers inside the process (upload, config, measure_corpus) all drop the cache, so
every test here writes the file the way an EXTERNAL process does -- no endpoint is asked
to invalidate anything -- and then calls the endpoint function FastAPI would call.
"""
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from fastapi import HTTPException          # noqa: E402

from app import server as S                # noqa: E402


def write(d, name, rows):
    """Write a dataset file the way batch.py does: truncate in place, no atomic rename."""
    with open(os.path.join(d, f"{name}.json"), "w") as fh:
        json.dump(rows, fh)


def frame(fr, arm="sem/gated", **kw):
    r = {"frame": fr, "arm": arm, "specimen": "S1", "scale_known": True,
         "n_cracks_measured": 1, "area_fraction": 0.01}
    r.update(kw)
    return r


@pytest.fixture
def out(tmp_path, monkeypatch):
    """Point _load at an empty temp dir and give it a cold cache."""
    monkeypatch.setattr(S, "OUT", str(tmp_path))
    monkeypatch.setattr(S, "_CACHE", {})
    return str(tmp_path)


def test_a_rewritten_frames_json_is_reflected_on_the_next_request(out):
    """The regression itself: changed number, and a row that only the new file has."""
    write(out, "frames", [frame("f1", area_fraction=0.01)])
    assert [f["area_fraction"] for f in S.frames(arm="sem/gated")] == [0.01]

    # An external rebuild: one value changed, one frame added.
    write(out, "frames", [frame("f1", area_fraction=0.02), frame("f2")])
    got = S.frames(arm="sem/gated")

    assert [f["area_fraction"] for f in got] == [0.02, 0.01], "stale number served"
    assert [f["frame"] for f in got] == ["f1", "f2"], "added frame missing"


def test_a_field_added_by_the_rebuild_becomes_visible(out):
    """The absent-row half of 2026-09-27: app.js reads a field the old records lack."""
    write(out, "frames", [frame("f1")])
    assert "new_metric" not in S.frames(arm="sem/gated")[0]

    write(out, "frames", [frame("f1", new_metric=1.5)])
    assert S.frames(arm="sem/gated")[0]["new_metric"] == 1.5


def test_an_unchanged_file_is_not_reparsed(out):
    """Still a cache: cracks.json is 40 MB, so a per-request reparse is not acceptable."""
    write(out, "cracks", [{"frame": "f1", "arm": "sem/gated", "area_px": 10}])
    first = S._load("cracks")
    assert S._load("cracks") is first, "reparsed a file that did not change"


def test_every_endpoint_follows_the_file_not_just_frames(out):
    """_load backs arms/specimens/cracks/export too; a per-endpoint fix would miss them."""
    write(out, "frames", [frame("f1")])
    write(out, "cracks", [{"frame": "f1", "arm": "sem/gated", "area_px": 10}])
    write(out, "specimens", [{"arm": "sem/gated", "specimen": "S1", "n_frames": 1}])
    assert S.arms()[0]["n_frames"] == 1
    assert S.cracks(frame="f1", arm="sem/gated")["n_total"] == 1
    assert S.specimens(arm="sem/gated")[0]["n_frames"] == 1

    write(out, "frames", [frame("f1"), frame("f2")])
    write(out, "cracks", [{"frame": "f1", "arm": "sem/gated", "area_px": 10},
                          {"frame": "f1", "arm": "sem/gated", "area_px": 20}])
    write(out, "specimens", [{"arm": "sem/gated", "specimen": "S1", "n_frames": 2}])
    assert S.arms()[0]["n_frames"] == 2
    assert S.cracks(frame="f1", arm="sem/gated")["n_total"] == 2
    assert S.specimens(arm="sem/gated")[0]["n_frames"] == 2
    assert len(list(S.export_csv(arm="sem/gated").body.splitlines())) == 4  # hdr+2+comment


def test_a_same_size_rewrite_is_still_caught(out):
    """mtime alone would be enough here, but only because the clock is fine-grained.

    A value edit that does not change the file's length is the case a size-only key
    misses, and it is the common one: a remeasurement writes 0.02 where 0.01 was.
    """
    write(out, "frames", [frame("f1", area_fraction=0.01)])
    n = os.path.getsize(os.path.join(out, "frames.json"))
    assert S.frames(arm="sem/gated")[0]["area_fraction"] == 0.01

    write(out, "frames", [frame("f1", area_fraction=0.09)])
    assert os.path.getsize(os.path.join(out, "frames.json")) == n, "not a same-size rewrite"
    assert S.frames(arm="sem/gated")[0]["area_fraction"] == 0.09


def test_a_half_written_file_serves_the_last_good_copy_not_a_500(out):
    """batch.py truncates in place and streams ~40 MB, and measure_corpus runs it on a
    thread in THIS process. Reloading on every mtime change puts requests on top of a
    partly written file, so the reload must fail soft -- and must retry afterwards
    rather than pinning the stale copy."""
    write(out, "frames", [frame("f1")])
    assert S.frames(arm="sem/gated")[0]["frame"] == "f1"

    p = os.path.join(out, "frames.json")
    with open(p, "w") as fh:
        fh.write('[{"frame": "f2", "arm": "sem/g')        # truncated mid-write
    assert S.frames(arm="sem/gated")[0]["frame"] == "f1", "served a torn read"

    write(out, "frames", [frame("f2")])                   # writer finishes
    assert S.frames(arm="sem/gated")[0]["frame"] == "f2", "stale copy got pinned"


def test_a_torn_file_with_nothing_cached_says_so(out):
    """No last-good copy to fall back on: 503, not a JSONDecodeError traceback."""
    with open(os.path.join(out, "frames.json"), "w") as fh:
        fh.write('[{"frame":')
    with pytest.raises(HTTPException) as e:
        S.frames(arm="sem/gated")
    assert e.value.status_code == 503


def test_a_deleted_dataset_still_asks_for_a_rebuild(out):
    with pytest.raises(HTTPException) as e:
        S.frames(arm="sem/gated")
    assert e.value.status_code == 503
    assert "batch.py" in e.value.detail


def test_no_caller_mutates_the_cached_records(out):
    """The cache hands out shared objects. Swapping the list is only safe while that
    stays true, so this pins it: drive every read endpoint and compare the bytes."""
    write(out, "frames", [frame("f1"), frame("f2", specimen="S2")])
    write(out, "cracks", [{"frame": "f1", "arm": "sem/gated", "area_px": 10,
                           "SkeletonLength_px": 5, "MeanWidth_px": 2}])
    write(out, "specimens", [{"arm": "sem/gated", "specimen": "S1", "n_frames": 1}])
    before = json.dumps(S._load("frames"), sort_keys=True)
    ids = [id(r) for r in S._load("frames")]

    S.arms()
    S.frames(arm="sem/gated")
    S.cracks(frame="f1", arm="sem/gated", sort="MeanWidth_px")
    S.specimens(arm="sem/gated")
    S.export_csv(arm="sem/gated", level="frames")
    try:
        S.figure_svg(arm="sem/gated", kind="box_by_specimen", y="area_fraction",
                     min_frames=1)
    except HTTPException:
        pass                                  # too few frames to plot; it still read them

    assert json.dumps(S._load("frames"), sort_keys=True) == before, "an endpoint wrote back"
    assert [id(r) for r in S._load("frames")] == ids, "records were reordered in place"
