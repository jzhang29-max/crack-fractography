#!/usr/bin/env python3
"""Editing a mask in the app: what it may touch, and at what resolution."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fn(name, src):
    i = src.index(f"def {name}(")
    j = src.index("\n@app.", i)
    return src[i:j]


def test_no_research_mask_is_ever_written():
    """Marking works on any frame, in this window -- but the sem and txm arms read the SEM
    repo's derived masks and the TXM export, which are irreplaceable research data this app
    does not own. Editing one writes a COPY into uploads instead.

    The invariant is not "editing is refused" -- that was the earlier, blunter version, and
    it is what forced marking out into a separate program. It is that the destination path
    is ALWAYS inside the app's own uploads directory, whatever the source arm."""
    fn = _fn("mask_edit", open(os.path.join(REPO, "app", "server.py")).read())
    import re
    dests = re.findall(r"dest = os\.path\.join\((\w+)", fn)
    assert dests, "no destination assignment found"
    assert set(dests) == {"UPLOAD_DIR"}, (
        f"an edit could be written outside the uploads directory: {set(dests)}")
    assert "_mask_path(arm, frame)" in fn, "the source is read from the arm's own location"
    # And the source must only ever be READ.
    assert "open(src" not in fn and 'open(src, "w"' not in fn


def test_a_marked_research_frame_keeps_its_scale():
    """A marked copy is the same field at the same magnification. Losing the scale would
    silently drop every micrometre column from the copy."""
    fn = _fn("mask_edit", open(os.path.join(REPO, "app", "server.py")).read())
    assert "set_user_scale(new_frame, src_scale)" in fn


def test_a_half_written_mask_cannot_replace_a_whole_one():
    """An interrupted save must not leave a truncated PNG where the measurement's input
    used to be."""
    fn = _fn("mask_edit", open(os.path.join(REPO, "app", "server.py")).read())
    assert "dest + \".tmp\"" in fn and "os.replace(tmp, dest)" in fn
    assert "im.verify()" in fn, "the bytes must be a readable image before they replace one"


def test_the_editor_draws_at_natural_resolution():
    """The canvas on screen is scaled to fit -- 6144x4096 shown at 323x215. Painting on the
    scaled copy and uploading that would resample the user's mask, changing every
    measurement by more than their correction did. Verified in the browser: after a stroke
    the saved mask was still 6144x4096."""
    js = open(os.path.join(REPO, "app", "static", "app.js")).read()
    fn = js[js.index("async function openEditor("):js.index("async function loadArm()")]
    assert "img.naturalWidth" in fn and "img.naturalHeight" in fn, (
        "the offscreen canvas must be the image's own size")
    assert "ED.off.width" in fn and "cv.width" in fn, (
        "display coordinates must be mapped back to image pixels")
    # The brush must scale with the ratio too, or a stroke is a different size per window.
    assert "ED.brush * (ED.off.width / cv.width)" in fn


def test_saving_re_measures_rather_than_just_storing():
    fn = _fn("mask_edit", open(os.path.join(REPO, "app", "server.py")).read())
    assert "remeasure(" in fn, "an edit that does not re-measure leaves a stale number"
