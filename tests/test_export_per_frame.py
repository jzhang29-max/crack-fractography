#!/usr/bin/env python3
"""Exporting one image's measurements, and one file per image.

THE BUG THIS STARTS FROM. /api/export.csv has always recorded its filters in a comment
line, because "a citable number that silently disagrees with the screen it came from is
worse than no export" -- its own docstring. But it had no frame filter, and the image
editor's CSV button called it with arm and level=cracks only, then saved the answer as
`<frame>_cracks.csv`. On the reference corpus that is a file named for one image carrying
26,075 cracks from 142 of them. The filename asserted a filter the request never applied.

So: `frame` narrows to one image, and `export_per_frame.zip` gives one CSV per image in
one download. The tests below pin the filtering, the filename, the comment line that
records the filter, and the thing that makes the zip trustworthy -- that each entry is
byte-identical to that frame's own export.csv rather than a second implementation of it.
"""
import csv
import io
import json
import os
import sys
import urllib.parse
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server, mask_png  # noqa: E402


def _seed(s, name, bar):
    """Upload one mask and return its frame stem. `bar` changes how much is marked."""
    st, raw = s.upload(f"{name}.png", mask_png(200, 150, bar))
    assert st == 200, raw[:300]
    up = json.loads(raw)
    return up["frames"][0]["frame"] if "frames" in up else up["frame"]


def _csv(s, **params):
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    st, raw = s.get(f"/api/export.csv?{q}")
    return st, raw


def _parse(raw):
    """-> (comment line, list of dict rows). The first line is the filter record."""
    text = raw.decode()
    head, rest = text.split("\n", 1)
    return head, list(csv.DictReader(io.StringIO(rest)))


@pytest.fixture
def seeded(tmp_path):
    with Server(str(tmp_path)) as s:
        frames = [_seed(s, "alpha", 40), _seed(s, "beta", 70), _seed(s, "gamma", 25)]
        yield s, frames


def test_frame_filter_returns_only_that_frame(seeded):
    """The whole point: ask for one image, get one image."""
    s, frames = seeded
    st, raw = _csv(s, arm="uploads", level="cracks")
    assert st == 200, raw[:300]
    _, allrows = _parse(raw)
    assert len({r["frame"] for r in allrows}) == len(frames), \
        "fixture is not exercising the bug: the combined export must span every frame"

    for fr in frames:
        st, raw = _csv(s, arm="uploads", level="cracks", frame=fr)
        assert st == 200, raw[:300]
        _, rows = _parse(raw)
        assert rows, f"no rows for {fr}"
        assert {r["frame"] for r in rows} == {fr}


def test_the_per_frame_rows_partition_the_combined_export(seeded):
    """No crack is lost by filtering, and none is duplicated into two frames."""
    s, frames = seeded
    _, combined = _parse(_csv(s, arm="uploads", level="cracks")[1])
    split = []
    for fr in frames:
        split += _parse(_csv(s, arm="uploads", level="cracks", frame=fr)[1])[1]
    key = lambda r: (r["frame"], r["crack_id"])      # noqa: E731
    assert sorted(map(key, split)) == sorted(map(key, combined))


def test_the_comment_line_records_the_frame_filter(seeded):
    """A filtered file that does not say it is filtered is the fault this endpoint
    exists to avoid; `frame` has to appear there like `specimen` does."""
    s, frames = seeded
    head, rows = _parse(_csv(s, arm="uploads", level="cracks", frame=frames[0])[1])
    assert f"frame={frames[0]}" in head, head
    assert f"rows={len(rows)}" in head, head

    head_all, _ = _parse(_csv(s, arm="uploads", level="cracks")[1])
    assert "frame=all" in head_all, head_all


def test_the_download_is_named_for_the_frame_it_contains(seeded):
    """The original fault was a filename asserting a filter the request never applied.
    Now the name follows the filter rather than the caller's intention."""
    s, frames = seeded
    q = urllib.parse.urlencode({"arm": "uploads", "level": "cracks", "frame": frames[0]})
    st, raw, hdrs = s.get_with_headers(f"/api/export.csv?{q}")
    assert st == 200
    assert frames[0] in hdrs.get("Content-Disposition", "")

    st, raw, hdrs = s.get_with_headers("/api/export.csv?arm=uploads&level=cracks")
    assert st == 200
    assert "uploads_cracks.csv" in hdrs.get("Content-Disposition", "")


def test_an_unknown_frame_is_404_not_the_whole_arm(seeded):
    """Silently widening to every frame is how the original bug read to a user."""
    s, _ = seeded
    st, raw = _csv(s, arm="uploads", level="cracks", frame="no_such_frame")
    assert st == 404, (st, raw[:200])


def test_specimens_level_rejects_a_frame_filter(seeded):
    s, frames = seeded
    st, _ = _csv(s, arm="uploads", level="specimens", frame=frames[0])
    assert st == 400


# ----------------------------------------------------------------- the zip
def _zip(s, **params):
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    st, raw = s.get(f"/api/export_per_frame.zip?{q}")
    return st, raw


def test_zip_has_one_csv_per_frame_plus_a_manifest(seeded):
    s, frames = seeded
    st, raw = _zip(s, arm="uploads", level="cracks")
    assert st == 200, raw[:300]
    z = zipfile.ZipFile(io.BytesIO(raw))
    assert z.testzip() is None
    names = sorted(z.namelist())
    assert "MANIFEST.txt" in names
    assert len([n for n in names if n.endswith(".csv")]) == len(frames)
    for fr in frames:
        assert any(fr in n for n in names), f"{fr} missing from {names}"


def test_each_zip_entry_is_byte_identical_to_that_frames_own_export(seeded):
    """THE CHECK THAT MATTERS. If the zip built its CSVs separately they would drift from
    export.csv the first time a column changed, and a reader comparing the two files would
    be comparing two instruments. It must call the same code."""
    s, frames = seeded
    _, raw = _zip(s, arm="uploads", level="cracks")
    z = zipfile.ZipFile(io.BytesIO(raw))
    for fr in frames:
        entry = next(n for n in z.namelist() if n.endswith(".csv") and fr in n)
        _, one = _csv(s, arm="uploads", level="cracks", frame=fr)
        assert z.read(entry) == one, f"{fr}: zip entry differs from export.csv"


def test_zip_rows_add_up_to_the_combined_export(seeded):
    s, frames = seeded
    _, combined = _parse(_csv(s, arm="uploads", level="cracks")[1])
    _, raw = _zip(s, arm="uploads", level="cracks")
    z = zipfile.ZipFile(io.BytesIO(raw))
    total = sum(len(_parse(z.read(n))[1]) for n in z.namelist() if n.endswith(".csv"))
    assert total == len(combined)


def test_zip_works_at_frames_level_too(seeded):
    """One row per image, split per image -- the summary table, not the crack list."""
    s, frames = seeded
    st, raw = _zip(s, arm="uploads", level="frames")
    assert st == 200, raw[:300]
    z = zipfile.ZipFile(io.BytesIO(raw))
    csvs = [n for n in z.namelist() if n.endswith(".csv")]
    assert len(csvs) == len(frames)
    for n in csvs:
        assert len(_parse(z.read(n))[1]) == 1


def test_min_area_filter_reaches_the_zip_and_an_emptied_frame_is_in_the_manifest(seeded):
    """A frame filtered down to nothing is a fact about that frame. It must not fail the
    download, and it must not vanish without a word either."""
    s, frames = seeded
    st, raw = _zip(s, arm="uploads", level="cracks", min_area_px=10 ** 9)
    assert st == 200, raw[:300]
    z = zipfile.ZipFile(io.BytesIO(raw))
    assert [n for n in z.namelist() if n.endswith(".csv")] == []
    man = z.read("MANIFEST.txt").decode()
    for fr in frames:
        assert fr in man, man
    assert "no rows after filtering" in man


def test_zip_rejects_the_specimens_level(seeded):
    s, _ = seeded
    st, _ = _zip(s, arm="uploads", level="specimens")
    assert st == 400


def test_a_frame_name_cannot_escape_the_zip():
    """Frame stems come from uploaded filenames, so they are user input reaching a path."""
    from app.server import _safe_stem
    assert "/" not in _safe_stem("../../etc/passwd")
    assert "\\" not in _safe_stem(r"..\..\windows")
    assert _safe_stem("") == "frame"
    assert _safe_stem("MAR_H_HIP_CBS_0004") == "MAR_H_HIP_CBS_0004"
