#!/usr/bin/env python3
"""Editing a mask in the app: what it may touch, and at what resolution."""
import os
import sys

import pytest

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

    seed = os.path.join(
        "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP",
        "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/auditseed")
    if not os.path.isdir(seed):
        pytest.skip("no seeded reference corpus on this machine")

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
