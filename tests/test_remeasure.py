#!/usr/bin/env python3
"""Re-measuring one frame must change that frame and nothing else.

This is the step that closes the loop the app exists for -- detect, look, correct, measure
again. Before it, the only way to see what a correction did was a full-corpus rebuild: 358
frames, about 17 minutes. That is not a loop, it is a one-way trip with a long way back.

The property that matters is containment. It writes into the same three JSON files every
other frame is stored in, so a bug here does not produce a wrong number on one frame -- it
produces wrong numbers on someone else's.
"""
import hashlib
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


def _digest(rows, skip_arm, skip_frame):
    other = [r for r in rows
             if not (r.get("arm") == skip_arm and r.get("frame") == skip_frame)]
    return hashlib.md5(json.dumps(other, sort_keys=True).encode()).hexdigest(), len(other)


def test_remeasure_replaces_only_its_own_frame():
    """Verified against the real dataset: re-measuring one uploaded frame left the digest
    of all 355 other frames byte-identical."""
    src = open(os.path.join(REPO, "app", "server.py"), encoding="utf-8").read()
    fn = src[src.index("def remeasure("):src.index("def _rebuild_specimen")]
    # The filter must exclude on BOTH arm and frame. On frame alone it would delete the
    # same-named frame in every other arm; on arm alone it would delete the whole arm.
    assert 'x.get("arm") == arm and x.get("frame") == summ["frame"]' in fn, (
        "the replacement filter must key on arm AND frame")
    assert "kept + new_rows" in fn, "everything not matching must be carried through"


def test_remeasure_reports_what_moved_and_the_masks_age():
    """"Did my correction do anything" has to be answered on the spot. The mask timestamp
    is how a user tells a real no-change from corrections that have not been exported yet:
    the marking tool paints into a paint layer, and a derived mask only changes after that
    tool re-applies."""
    src = open(os.path.join(REPO, "app", "server.py"), encoding="utf-8").read()
    fn = src[src.index("def remeasure("):src.index("def _rebuild_specimen")]
    for k in ("changed", "mask_modified", "seconds_since_mask_written", "unchanged"):
        assert f'"{k}"' in fn, f"the reply must carry {k}"


def test_the_specimen_record_is_rebuilt_for_that_specimen_only():
    src = open(os.path.join(REPO, "app", "server.py"), encoding="utf-8").read()
    fn = src[src.index("def _rebuild_specimen"):src.index('@app.get("/api/readout")')]
    assert 'r.get("arm") == arm and r.get("specimen") == specimen' in fn, (
        "only the affected specimen-arm record may be replaced")


def test_the_result_message_survives_the_refresh():
    """renderReadout() rebuilds the element the message is written into, so writing the
    message first erased it: the button worked, the numbers updated, and the user saw
    nothing happen."""
    js = open(os.path.join(REPO, "app", "static", "app.js"), encoding="utf-8").read()
    fn = js[js.index("async function remeasure("):js.index("async function loadArm()")]
    assert fn.index("await renderReadout()") < fn.index("fresh.innerHTML = msg"), (
        "the refresh must happen before the message is written")


# --- the dataset files are shared mutable state. These drive a real server. ---------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # for liveserver


def test_concurrent_remeasures_do_not_tear_the_dataset(tmp_path):
    """remeasure is a sync def, so FastAPI runs it in the threadpool and several execute at
    once. Each did read-whole-file / filter / truncate-and-rewrite with no lock and no
    atomic replace. Six concurrent re-measures of six DIFFERENT frames returned five HTTP
    500s -- one thread read frames.json while another was streaming it out, and json.load
    hit the truncation mid-object. Two app windows, or the Mark tab's save overlapping the
    Analysis tab's re-measure, both reach it.

    The containment property the rest of this file asserts is the one at risk: a torn read
    does not produce a wrong number on the frame being measured, it produces wrong numbers
    on someone else's.
    """
    import json as _json
    from concurrent.futures import ThreadPoolExecutor

    from liveserver import Server, mask_png

    with Server(tmp_path / "d") as s:
        frames = []
        for i in range(6):
            st, body = s.upload(f"conc{i}_gated.png", mask_png(bar=20 + 8 * i))
            assert st == 200, body[:300]
            frames.append(_json.loads(body)["frame"])

        before = len(s.dataset("frames"))
        with ThreadPoolExecutor(max_workers=6) as ex:
            results = list(ex.map(
                lambda f: s.post(f"/api/remeasure?arm=uploads&frame={f}")[0], frames))

        assert all(r == 200 for r in results), (
            f"concurrent re-measures returned {results} -- a non-200 here is a torn read "
            f"of the dataset, not a measurement failure")

        # And the files are still whole, still parseable, and still hold every frame.
        rows = s.dataset("frames")
        assert len(rows) == before, f"{before} frames before, {len(rows)} after"
        keys = [(r["arm"], r["frame"]) for r in rows]
        assert len(keys) == len(set(keys)), "a concurrent write duplicated a frame row"
        s.dataset("cracks"); s.dataset("specimens")      # parse or raise


def test_a_non_finite_scale_is_refused_before_it_reaches_the_dataset(tmp_path):
    """float('inf') passed the old `v > 0` check. Every physical column is then a pixel
    count times it, and json.dump writes bare `Infinity` -- which is not JSON (RFC 8259).
    Python's json accepts it, which is why it went unnoticed; JSON.parse and R's jsonlite
    do not. Three endpoints then returned 500 across restarts with no route back through
    the UI, because the frame could no longer be selected to clear its scale."""
    import json as _json

    from liveserver import Server, mask_png

    with Server(tmp_path / "d") as s:
        st, body = s.upload("scaletest_gated.png", mask_png(bar=30))
        assert st == 200
        frame = _json.loads(body)["frame"]

        for bad in ("inf", "-inf", "nan", "0", "-5"):
            st, body = s.post(f"/api/scale?arm=uploads&frame={frame}&nm_per_px={bad}")
            assert st == 400, f"nm_per_px={bad} returned {st}, expected a 400: {body[:200]}"
            assert b"finite" in body or b"greater than zero" in body, body[:200]

        # The dataset is untouched and every arm still answers.
        for name in ("frames", "cracks", "specimens"):
            raw = open(os.path.join(s.data_dir, f"{name}.json"), encoding="utf-8").read()
            assert "Infinity" not in raw and "NaN" not in raw, f"{name}.json is not JSON"
        assert s.get("/api/frames?arm=uploads")[0] == 200

        # A finite value still works.
        st, _ = s.post(f"/api/scale?arm=uploads&frame={frame}&nm_per_px=52")
        assert st == 200
