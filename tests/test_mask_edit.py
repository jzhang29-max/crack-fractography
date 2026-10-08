#!/usr/bin/env python3
"""Editing a mask in the app: what it may touch, and at what resolution."""
import os
import os as _os
REPO_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPJS = os.path.join(REPO, "app", "static", "app.js")


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
    fn = _fn("mask_edit", open(os.path.join(REPO, "app", "server.py"), encoding="utf-8").read())
    import re
    dests = re.findall(r"dest = os\.path\.join\((\w+)", fn)
    assert dests, "no destination assignment found"
    assert set(dests) == {"UPLOAD_DIR"}, (
        f"an edit could be written outside the uploads directory: {set(dests)}")
    assert "_mask_path(arm, frame)" in fn, "the source is read from the arm's own location"
    # And the source must only ever be READ.
    assert "open(src" not in fn and 'open(src, "w"' not in fn


def test_editing_a_research_frame_keeps_its_identity_and_its_scale():
    """An edit is the SAME frame, so there is nothing to inherit a scale from -- it never
    leaves the record that has one. This used to file the result as "<frame>_marked" in
    uploads and copy the scale across, and losing that copy silently dropped every
    micrometre column from the corrected version."""
    src = open(os.path.join(REPO, "app", "server.py"), encoding="utf-8").read()
    fn = _fn("mask_edit", src)
    assert "new_frame = frame" in fn, "an edit is filed under a different name again"
    # THE CODE FORM, NOT THE WORD. A comment above it narrates why the old
    # "<frame>_marked" copy is gone, which is accurate and worth keeping -- this repo has
    # already rejected one guard that banned mentioning a removed thing at all.
    assert 'f"{frame}_marked"' not in fn, "an edit creates a second frame again"
    assert "_edit_path(arm, frame)" in fn, "the edit is not stored against its own frame"


def test_a_half_written_mask_cannot_replace_a_whole_one():
    """An interrupted save must not leave a truncated PNG where the measurement's input
    used to be."""
    fn = _fn("mask_edit", open(os.path.join(REPO, "app", "server.py"), encoding="utf-8").read())
    assert "dest + \".tmp\"" in fn and "os.replace(tmp, dest)" in fn
    assert "im.verify()" in fn, "the bytes must be a readable image before they replace one"


def test_the_editor_draws_at_natural_resolution():
    """The canvas on screen is scaled to fit -- 6144x4096 shown at 323x215. Painting on the
    scaled copy and uploading that would resample the user's mask, changing every
    measurement by more than their correction did. Verified in the browser: after a stroke
    the saved mask was still 6144x4096."""
    js = open(os.path.join(REPO, "app", "static", "app.js"), encoding="utf-8").read()
    fn = js[js.index("async function openEditor("):js.index("async function loadArm()")]
    assert "img.naturalWidth" in fn and "img.naturalHeight" in fn, (
        "the offscreen canvas must be the image's own size")
    assert "ED.off.width" in fn and "cv.width" in fn, (
        "display coordinates must be mapped back to image pixels")
    # THE BRUSH SCALES BY IMAGE-PIXELS-SHOWN OVER CANVAS-PIXELS, or a stroke is a
    # different size per window. That ratio used to be ED.off.width / cv.width because the
    # canvas always showed the whole mask; with a crop view it is the VIEW's width, which
    # equals the mask's width when nothing is cropped. Asserted as the ratio rather than
    # as one spelling of it.
    assert "ED.brush * ((ED.view ? ED.view.w : ED.off.width) / cv.width)" in fn, (
        "the brush no longer scales with the visible region")
    assert "ED.off.width = img.naturalWidth" in fn or "ED.off.width" in fn


def test_saving_re_measures_rather_than_just_storing():
    fn = _fn("mask_edit", open(os.path.join(REPO, "app", "server.py"), encoding="utf-8").read())
    assert "remeasure(" in fn, "an edit that does not re-measure leaves a stale number"


# --- the first edit of a research frame must report what it changed -----------------
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))   # for liveserver


def test_an_edit_diffs_against_what_the_frame_measured_before():
    """remeasure() keeps the prior record and reports what moved, which for an in-place
    edit is exactly the right before-and-after: the same frame, before and after the
    stroke. The copy-based version needed a special case because the row it would have
    diffed against had just been written from the same mask."""
    src = open(os.path.join(REPO, "app", "server.py"), encoding="utf-8").read()
    fn = _fn("remeasure", src)
    assert "prior = next(" in fn
    assert "changed" in fn


def test_a_marked_copy_keeps_its_parents_micrograph():
    """THE FIRST STROKE ON A RESEARCH FRAME USED TO TAKE THE PICTURE AWAY.

    Saving writes a copy into uploads rather than touching the research mask, and the
    uploads arm reports has_originals false -- correctly, for an uploaded mask. So the
    copy rendered as a bare black-and-white mask, which is exactly when you most need to
    see what is under the brush. A copy is the same field at the same size, so it
    resolves its parent's micrograph through its own copied_from."""
    src = open(os.path.join(REPO, "app", "server.py"), encoding="utf-8").read()
    fn = src[src.index("def _original_path("):src.index('@app.get("/api/original/')]
    assert "copied_from" in fn, (
        "a marked copy cannot find its parent's micrograph, so painting a research frame "
        "drops you onto a bare mask")
    assert "_depth" in fn, "a copy of a copy would recurse without a depth limit"
    # and the record must ADVERTISE it, or the editor never asks for it
    mi = src[src.index("def _measure_into_uploads("):src.index("@app.post(\"/api/scale\")")]
    assert 'summ["has_original"] = True' in mi


def test_saving_moves_nothing_and_creates_nothing():
    """Three earlier versions of this were wrong in the same direction: the first followed
    a copy into Your images and rebuilt the editor on it; the second kept the canvas but
    still switched the arm and the selected row; the third stopped moving but still made a
    second frame. None of them is what "save it on the same image" means."""
    js = open(APPJS, encoding="utf-8").read()
    a = js.index("if (d.edited_in_place) {")
    blk = js[a:js.index("return;", a)]
    for moved in ('state.arm =', "state.frame =", 'sel.value', "await loadArm()",
                  "selectFrame("):
        assert moved not in blk, f"the save still moves the reader: {moved}"
    assert "SEND.frame = saveFrame" in blk, "the edit is not sendable to a correction mask"


def test_an_edit_measures_the_mask_once():
    """Measuring one of these frames costs 12.8 s, and the copy-based save measured the
    same 25 megapixels twice -- once to create the copy's record and once to report. An
    in-place edit has one record to update, so there is one measurement."""
    src = open(os.path.join(REPO, "app", "server.py"), encoding="utf-8").read()
    fn = _fn("mask_edit", src)
    # One CALL. The word also appears in the comment explaining why there is only one.
    import re as _re
    calls = _re.findall(r"=\s*remeasure\(", fn)
    assert len(calls) == 1, f"the mask is measured {len(calls)} times per save"
    assert "_measure_into_uploads(dest" not in fn, "a second measuring path is back"


def test_a_save_in_progress_says_so_where_it_can_be_seen():
    """The only sign a save was running was the label on #edsave, which is hidden."""
    js = open(APPJS, encoding="utf-8").read()
    # #edsave is built by editorHTML(), and it is hidden there.
    assert 'id="edsave" hidden' in js, "the save button is no longer hidden; re-read this"
    fn = js[js.index("const saveNow = async"):js.index("ED.scheduleSave = ")]
    assert 'out = $("#edout")' in fn, "the readout element is not in scope"
    i = fn.index('btn.textContent = "Saving')
    j = fn.index("try {", i)
    # Between arming the (hidden) button and starting the request, something must be
    # written to the visible readout.
    assert "out.innerHTML" in fn[i:j], (
        "nothing visible changes while a save runs, so a slow one reads as a broken one")


def test_the_editor_does_not_wait_for_the_micrograph():
    """Opening a frame used to `await` the background before building anything, so the
    first view of a frame nobody had rendered before was several seconds of an empty pane
    -- no canvas, no toolbar, nothing saying why. It read as "the image doesn't come up".

    Nothing downstream needs the background to exist: ED.paint() already draws the bare
    mask when ED.bg is null, because that is the uploads case. So it is fetched without
    blocking and painted in on arrival, GUARDED ON THE FRAME -- a reader can click another
    row inside those seconds, and a late arrival must not paint one frame's micrograph
    under another frame's mask."""
    js = open(APPJS, encoding="utf-8").read()
    fn = js[js.index("async function openEditor("):js.index("async function loadArm()")]
    i = fn.index("ARM_HAS_ORIGINALS[state.arm] || _rec?.has_original")
    blk = fn[i:i + 1400]
    assert "bg.onload" in blk, "the background is no longer loaded at all"
    assert "await new Promise" not in blk, (
        "the editor still blocks on the micrograph, so a cold frame is a blank pane")
    assert "if (ED.frame !== frame) return;" in blk, (
        "a late micrograph could land under a different frame's mask")
    # and the readout has ONE definition, used before and after the photo arrives
    assert "ED.edoutHTML" in fn, "the readout line is spelled twice and will disagree"


def test_the_autosave_waits_long_enough_to_think():
    """A save re-measures 25 megapixels and three hundred cracks -- about thirteen
    seconds -- so a 1.8 s idle delay meant any pause to look at what you had just drawn
    triggered one. You were interrupted for thinking.

    The risk a longer delay carries is unsaved work, and that exposure is a hard crash
    and nothing else: flushSave runs on leaving the frame, leaving the Mark tab, closing
    the window, and before strokes go to a correction mask. Those four are asserted here
    because the delay is only defensible while they all hold."""
    js = open(APPJS, encoding="utf-8").read()
    import re
    m = re.search(r"const AUTOSAVE_MS = (\d+);", js)
    assert m, "the autosave delay is gone"
    ms = int(m.group(1))
    assert ms >= 5000, f"the delay is {ms} ms, short enough to fire on a thinking pause"
    assert ms <= 60000, f"the delay is {ms} ms, long enough to hold real work at risk"
    # the four things that must still flush
    assert js.count("ED.flushSave") >= 5, "a flush site has gone missing"
    assert 'if (id !== "mark" && ED.dirty && ED.flushSave)' in js, "leaving the tab"
    assert 'window.addEventListener("beforeunload"' in js, "closing the window"


def test_every_path_that_dirties_the_mask_offers_a_manual_save():
    """With an eight-second delay the Save now button is the only way to not wait, so a
    path that dirties the mask without revealing it leaves the reader stuck. Two paths
    dirty it -- the brush and the whole-region fill -- and only the brush used to unhide
    the button."""
    js = open(APPJS, encoding="utf-8").read()
    fn = js[js.index("async function openEditor("):js.index("async function loadArm()")]
    assert "ED.markDirty = () =>" in fn, "there is no single place that marks it dirty"
    # nothing sets the flag directly except that helper
    body = fn.replace("ED.markDirty = () => {\n    ED.dirty = true;", "")
    assert "ED.dirty = true" not in body, (
        "a path sets ED.dirty without going through markDirty, so it will not reveal the "
        "manual save")
    assert fn.count("ED.markDirty()") >= 2, "the fill path no longer marks dirty"
