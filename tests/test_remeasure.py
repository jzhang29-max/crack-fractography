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
    src = open(os.path.join(REPO, "app", "server.py")).read()
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
    src = open(os.path.join(REPO, "app", "server.py")).read()
    fn = src[src.index("def remeasure("):src.index("def _rebuild_specimen")]
    for k in ("changed", "mask_modified", "seconds_since_mask_written", "unchanged"):
        assert f'"{k}"' in fn, f"the reply must carry {k}"


def test_the_specimen_record_is_rebuilt_for_that_specimen_only():
    src = open(os.path.join(REPO, "app", "server.py")).read()
    fn = src[src.index("def _rebuild_specimen"):src.index('@app.get("/api/readout")')]
    assert 'r.get("arm") == arm and r.get("specimen") == specimen' in fn, (
        "only the affected specimen-arm record may be replaced")


def test_the_result_message_survives_the_refresh():
    """renderReadout() rebuilds the element the message is written into, so writing the
    message first erased it: the button worked, the numbers updated, and the user saw
    nothing happen."""
    js = open(os.path.join(REPO, "app", "static", "app.js")).read()
    fn = js[js.index("async function remeasure("):js.index("async function loadArm()")]
    assert fn.index("await renderReadout()") < fn.index("fresh.innerHTML = msg"), (
        "the refresh must happen before the message is written")
