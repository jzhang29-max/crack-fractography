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


def test_a_marked_research_frame_keeps_its_scale():
    """A marked copy is the same field at the same magnification. Losing the scale would
    silently drop every micrometre column from the copy."""
    fn = _fn("mask_edit", open(os.path.join(REPO, "app", "server.py"), encoding="utf-8").read())
    assert "set_user_scale(new_frame, src_scale)" in fn


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


def test_the_first_edit_of_a_frame_diffs_against_the_frame_it_copied(tmp_path):
    """On the copy path, mask_edit called _measure_into_uploads -- which writes the new
    frame's record FROM THE SAME MASK -- and then remeasure, whose `prior` is that row. The
    diff was empty by construction, so the first edit of any research frame reported "No
    measurement changed" however large the correction. Only the first: a second edit of the
    copy diffed correctly, which is what made it look like a quirk.

    Measured on the real corpus: painting a 40 px band across the full 6144 px width of
    MAR_H_AS_CBS_0001 moved area_fraction 0.053548 -> 0.062242 and skeleton length
    111932.5 -> 117208.7 px, and the reply was {"changed": {}}.

    Needs a research arm, because the copy path is what happens for a frame this app does
    not own -- an uploads frame is edited in place and always diffed correctly. Skipped
    where there is no reference corpus. Writes only into the server's own uploads dir; the
    SEM repo is read and never written, which is mask_edit's documented restriction.
    """
    import io, json, os, shutil
    from PIL import Image
    from liveserver import Server

    # The seed is the repository's own built dataset. This used to be an absolute path
    # into one session's scratch directory, complete with that session's UUID: it could
    # never run on another machine, and when the scratch directory was emptied the test
    # went on reporting success by skipping. analysis/out/ holds exactly the three files
    # Server(seed=...) copies, and FRACTOGRAPHY_ANALYSIS_OUT overrides it.
    seed = os.environ.get("FRACTOGRAPHY_ANALYSIS_OUT",
                          os.path.join(REPO_ROOT, "analysis", "out"))
    missing = [n for n in ("frames.json", "cracks.json", "specimens.json")
               if not os.path.exists(os.path.join(seed, n))]
    if missing:
        pytest.skip(f"no built dataset at {seed} (missing {', '.join(missing)}); "
                    f"run the analysis or set FRACTOGRAPHY_ANALYSIS_OUT")

    with Server(tmp_path / "d", seed=seed) as s:
        st, frames = s.json("/api/frames?arm=sem%2Fgated")
        if st != 200 or not frames:
            pytest.skip("no sem/gated frames available")
        src = frames[0]["frame"]
        st, raw = s.get(f"/api/mask/sem/gated/{src}")
        if st != 200:
            pytest.skip("the source mask is not on disk (no SEM repo configured)")

        before = [f for f in s.dataset("frames")
                  if f["arm"] == "sem/gated" and f["frame"] == src][0]

        # Paint a band right across the mask: a correction nobody could call no-change.
        im = Image.open(io.BytesIO(raw)).convert("L")
        w, h = im.size
        for y in range(h // 2, min(h, h // 2 + 40)):
            for x in range(w):
                im.putpixel((x, y), 0)
        buf = io.BytesIO(); im.save(buf, "PNG")

        st, body = s.upload(f"{src}.png", buf.getvalue(),
                            path=f"/api/mask_edit?arm=sem/gated&frame={src}")
        assert st == 200, body[:400]
        d = json.loads(body)

        assert d.get("changed"), (
            f"the first edit of a research frame reported no change. source "
            f"area_fraction={before.get('area_fraction')}, reply keys="
            f"{ {k: d[k] for k in ('changed', 'unchanged', 'frame') if k in d} }")
        assert d["unchanged"] is False
        assert "area_fraction" in d["changed"], d["changed"]
        assert d["changed"]["area_fraction"]["before"] == before["area_fraction"]
        assert d["changed"]["area_fraction"]["after"] != before["area_fraction"]
        # And it says WHAT the before column is.
        assert d.get("changed_against") == f"sem/gated/{src}", d.get("changed_against")


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


def test_saving_does_not_tear_down_the_editor():
    """The first save switched the arm to uploads, reloaded the list and reselected, which
    rebuilt the editor on the copy -- taking the crop view, the place in the list, and the
    picture with it, and dropping the reader into a tab they had not asked for.

    The selection still follows the copy, so nobody reads the original's numbers beside
    their own edit. What must not happen is the remount."""
    js = open(APPJS, encoding="utf-8").read()
    # THE WHOLE BRANCH, to its `return`. A window that stopped at the first
    # `state.frames = await allFrames();` ended before the teardown would sit, so putting
    # loadArm() back left this test green -- confirmed by doing exactly that.
    a = js.index("if (d.copied_from) {")
    blk = js[a:js.index("return;", a)]
    assert "await loadArm()" not in blk, "the save still reloads the arm and remounts"
    assert "selectFrame(" not in blk, "the save still reselects and remounts"
    assert "saveArm" in blk and "saveFrame" in blk, (
        "the next save must be retargeted at the copy, or it posts the research frame "
        "name under arm=uploads and 404s")
    # AND NOTHING ABOUT WHERE THE READER IS MAY CHANGE. The jump is something seen in the
    # sidebar, not something the DOM does: keeping the canvas mounted while still moving
    # the arm and the selected row is still a jump, and was still reported as one.
    for moved in ('state.arm = "uploads"', "state.frame = d.frame",
                  'state.spec = ""', 'sel.value = "uploads"',
                  "renderFrames()", "renderSpecimens()"):
        assert moved not in blk, f"the save still moves the reader: {moved}"
    assert "SEND.frame = d.frame" in blk, (
        "the copy must still be reachable by Send strokes to corrections")


def test_the_first_save_measures_the_mask_once():
    """Measuring one of these frames costs 12.8 s. The first save called
    _measure_into_uploads and then remeasure() on the same 25 megapixels, so it took 27.5 s
    against 13.9 for every save after it -- with nothing on screen saying why."""
    src = open(os.path.join(REPO, "app", "server.py"), encoding="utf-8").read()
    fn = src[src.index('@app.post("/api/mask_edit")'):src.index("def _measure_into_uploads(")]
    assert "_measure_into_uploads(dest, new_frame" in fn
    assert 'remeasure(arm="uploads", frame=new_frame)' not in fn, (
        "the copy is measured twice again")


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
