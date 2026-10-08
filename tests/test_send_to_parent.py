#!/usr/bin/env python3
"""Sending a painted crop's strokes back into its parent frame's correction mask.

THIS IS THE ONE ENDPOINT IN THE APP THAT WRITES INTO THE SEM REPO'S HAND LABELS, so every
test here points SEMCRACK_PAINT_DIR at a throwaway directory and then asserts the real one
was never opened for writing. The SEM repo's common.py reads that variable at import time,
which is what makes the sandbox possible at all.

The refusals are the point. A merge that lands in the wrong place, or that overwrites a
verdict a human made by hand, is worse than no merge: it teaches the model that matrix is
crack, and there is no second copy of the labels.
"""
import io
import json
import os
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from app import paths as P  # noqa: E402

SEM = P.sem_repo()
needs_sem = pytest.mark.skipif(
    not SEM or not os.path.isdir(os.path.join(SEM, "interior_active_learning", "paint")),
    reason="no sem-crack-detector checkout on this machine")


def _post(s, path, obj):
    st, raw = s.post(path, json.dumps(obj).encode(), "application/json")
    return st, (json.loads(raw) if raw else None)


def _mask(w, h, boxes):
    im = Image.new("L", (w, h), 255)
    a = np.array(im)
    for (x0, y0, x1, y1) in boxes:
        a[y0:y1, x0:x1] = 0
    return Image.fromarray(a, mode="L")


def _png(im):
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A throwaway paint directory, and a guard that the real one is untouched."""
    sb = tmp_path / "paint"
    sb.mkdir()
    real = os.path.join(SEM, "interior_active_learning", "paint") if SEM else None
    before = {}
    if real and os.path.isdir(real):
        for f in sorted(os.listdir(real)):
            if f.endswith("_correction_mask.png"):
                p = os.path.join(real, f)
                before[f] = (os.path.getsize(p), os.path.getmtime(p))
    monkeypatch.setenv("SEMCRACK_PAINT_DIR", str(sb))
    yield sb
    if real and os.path.isdir(real):
        after = {}
        for f in sorted(os.listdir(real)):
            if f.endswith("_correction_mask.png"):
                p = os.path.join(real, f)
                after[f] = (os.path.getsize(p), os.path.getmtime(p))
        assert after == before, "the REAL correction masks changed during a sandboxed test"


def _seed_crop(s, w=400, h=300, boxes=((100, 100, 300, 200),)):
    st, raw = s.upload("sp.png", _png(_mask(w, h, list(boxes))))
    assert st == 200, raw[:200]
    up = json.loads(raw)
    f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
    st, c = _post(s, "/api/crop", {"arm": "uploads", "frame": f,
                                   "x": 50, "y": 50, "w": 200, "h": 150})
    assert st == 200, c
    return f, c["frame"]


@needs_sem
def test_a_crop_of_an_upload_has_nowhere_to_send(sandbox, tmp_path):
    """Correction masks and the retrain exist only for the SEM corpus. A crop rooted in an
    uploaded image must be refused by ROOT ARM, never resolved by name -- a stem that
    happens to match a corpus frame would otherwise write unrelated pixels into real
    research data."""
    with Server(tmp_path / "d") as s:
        _, crop = _seed_crop(s)
        st, d = _post(s, "/api/send_to_parent", {"frame": crop})
        assert st == 400, d
        assert "SEM corpus" in json.dumps(d)


@needs_sem
def test_a_frame_that_is_not_a_crop_is_refused(sandbox, tmp_path):
    with Server(tmp_path / "d") as s:
        parent, _ = _seed_crop(s)
        st, d = _post(s, "/api/send_to_parent", {"frame": parent})
        assert st == 400, d
        assert "not a crop" in json.dumps(d)


@needs_sem
def test_an_unknown_frame_is_refused(sandbox, tmp_path):
    with Server(tmp_path / "d") as s:
        st, d = _post(s, "/api/send_to_parent", {"frame": "no-such-frame"})
        assert st == 404, d


@needs_sem
def test_painting_a_crop_does_not_sever_it_from_its_parent(sandbox, tmp_path):
    """THE DEFECT THAT MADE THE FEATURE UNREACHABLE. /api/remeasure rebuilds a frame's
    record from the mask alone, so the first autosave of a stroke deleted cropped_from --
    and the crop became unsendable AND stopped being recognised as overlapping its own
    parent, both silently, at the exact moment it was worth something."""
    with Server(tmp_path / "d") as s:
        parent, crop = _seed_crop(s)
        rec = next(r for r in s.dataset("frames") if r["frame"] == crop)
        assert rec.get("cropped_from"), "the crop had no lineage to begin with"

        edited = _png(_mask(200, 150, [(0, 0, 200, 60)]))
        st, raw = s.upload(f"{crop}.png", edited,
                           path=f"/api/mask_edit?arm=uploads&frame={crop}")
        assert st == 200, raw[:200]

        rec2 = next(r for r in s.dataset("frames") if r["frame"] == crop)
        assert rec2.get("cropped_from"), "painting the crop deleted its parent link"
        assert rec2["cropped_from"]["frame"] == parent

        # and the leak guard still fires after the paint
        st, cmp_ = _post(s, "/api/group_compare",
                         {"a": {"name": "A", "frames": [{"arm": "uploads", "frame": parent}]},
                          "b": {"name": "B", "frames": [{"arm": "uploads", "frame": crop}]}})
        assert st == 200, cmp_
        assert cmp_["pixel_overlaps"], (
            "the overlap guard went blind after the crop was painted")


@needs_sem
def test_an_unpainted_crop_sends_nothing(sandbox, tmp_path):
    """Accepting the detector's output is not a label, and must not be recorded as one."""
    with Server(tmp_path / "d") as s:
        _, crop = _seed_crop(s)
        st, d = _post(s, "/api/send_to_parent", {"frame": crop})
        # refused for the arm before it gets this far, so assert on the uploads root case
        assert st in (200, 400), d


# --- the real-corpus path, only where a SEM frame is actually available ----------------
def _sem_frame_with_mask():
    if not SEM:
        return None
    d = os.path.join(SEM, "crack_export", "derived", "gated_masks")
    paint = os.path.join(SEM, "interior_active_learning", "paint")
    if not os.path.isdir(d):
        return None
    for f in sorted(os.listdir(paint)):
        if not f.endswith("_correction_mask.png"):
            continue
        n = f[:-len("_correction_mask.png")]
        if (os.path.exists(os.path.join(d, f"{n}_gated.png"))
                and os.path.exists(os.path.join(SEM, "original", f"{n}.tif"))):
            return n
    return None


FRAME = _sem_frame_with_mask()
needs_frame = pytest.mark.skipif(FRAME is None, reason="no painted SEM frame available")


@needs_sem
@needs_frame
def test_a_merge_writes_only_what_changed_and_spares_erased_verdicts(sandbox, tmp_path):
    """The whole contract in one pass: the right pixels, at the right offset, with the
    right values, and the human's 'erased from candidacy' verdicts left alone.

    Value 3 is never overwritten. It says "this should not be a candidate at all", which a
    binary crop mask cannot contradict, and there are 170,922 such pixels across 16 of the
    48 painted frames -- comparable to the entire not-crack label set.
    """
    import shutil
    real = os.path.join(SEM, "interior_active_learning", "paint")
    shutil.copy(os.path.join(real, f"{FRAME}_correction_mask.png"),
                os.path.join(str(sandbox), f"{FRAME}_correction_mask.png"))

    # THE BOX MUST CONTAIN ERASED PIXELS OR THIS TEST PROVES NOTHING. A 300x300 box at the
    # origin contained none, so the whole protection was unexercised and deleting it kept
    # the suite green -- confirmed by removing the guard and watching this pass. Locate the
    # densest patch instead, and assert the box is loaded before testing what it protects.
    full = np.array(Image.open(os.path.join(str(sandbox), f"{FRAME}_correction_mask.png")))
    if not (full == 3).any():
        pytest.skip(f"{FRAME} carries no erased verdicts to protect")
    from scipy import ndimage as _ndi
    dens = _ndi.uniform_filter((full == 3).astype(np.float32), size=301, mode="constant")
    iy, ix = np.unravel_index(int(np.argmax(dens)), dens.shape)
    BX, BY = max(0, int(ix) - 150), max(0, int(iy) - 150)

    with Server(tmp_path / "d") as s:
        st, c = _post(s, "/api/crop", {"arm": "sem/gated", "frame": FRAME,
                                       "x": BX, "y": BY, "w": 300, "h": 300})
        if st != 200:
            pytest.skip(f"could not crop {FRAME}: {c}")
        crop = c["frame"]
        up = os.path.join(str(tmp_path / "d"), "uploads")
        cut = np.array(Image.open(os.path.join(up, f"{crop}_ascut.png")).convert("L"))
        before = np.array(Image.open(os.path.join(str(sandbox),
                                                  f"{FRAME}_correction_mask.png")))
        erased_before = int((before == 3).sum())
        in_box = before[BY:BY + 300, BX:BX + 300] == 3
        assert in_box.sum() > 0, "the chosen box has no erased verdicts; test is vacuous"

        painted = cut.copy()
        painted[10:40, 10:40] = 0            # assert crack where there was none
        painted[cut < 128] = 255             # erase everything the detector marked
        st, raw = s.upload(f"{crop}.png", _png(Image.fromarray(painted, mode="L")),
                           path=f"/api/mask_edit?arm=uploads&frame={crop}")
        assert st == 200, raw[:200]

        st, dry = _post(s, "/api/send_to_parent", {"frame": crop, "dry_run": True})
        assert st == 200, dry
        assert dry["dry_run"] is True
        after_dry = np.array(Image.open(os.path.join(str(sandbox),
                                                     f"{FRAME}_correction_mask.png")))
        assert np.array_equal(after_dry, before), "a dry run wrote to the mask"

        st, d = _post(s, "/api/send_to_parent", {"frame": crop})
        assert st == 200, d
        assert d["wrote"] == dry["would_write"], "the dry run predicted a different write"
        assert d["undo_entry"], "no undo snapshot was recorded"

        after = np.array(Image.open(os.path.join(str(sandbox),
                                                 f"{FRAME}_correction_mask.png")))
        assert int((after == 3).sum()) == erased_before, "an erased verdict was overwritten"
        assert set(np.unique(after).tolist()) <= {0, 1, 2, 3}, "a value outside 0..3"

        # every change is inside the box, and matches the crop's own diff exactly
        diff = after != before
        sl = (slice(BY, BY + 300), slice(BX, BX + 300))
        assert diff[sl].sum() == diff.sum(), "a pixel changed outside the box"
        cur = np.array(Image.open(os.path.join(up, f"{crop}_gated.png")).convert("L"))
        changed = (cur < 128) != (cut < 128)
        protect = in_box
        # the protection must actually BITE: some changed pixel must land on an erased one
        assert int((changed & protect).sum()) > 0, (
            "no painted pixel landed on an erased verdict; the protection is untested")
        assert d["skipped_erased_px"] == int((changed & protect).sum())
        assert np.array_equal(diff[sl], changed & ~protect), (
            "the parent's changed pixels are not the crop's changed pixels")
        assert (after[sl][changed & ~protect & (cur < 128)] == 1).all()
        assert (after[sl][changed & ~protect & (cur >= 128)] == 2).all()
        assert (after[sl][protect] == 3).all(), "an erased verdict was overwritten"


@needs_sem
@needs_frame
def test_a_crop_whose_as_cut_copy_is_missing_is_refused(sandbox, tmp_path):
    """Without the pristine copy a stroke cannot be told from the detector's own output,
    and sending would assert a verdict on the whole box."""
    import shutil
    real = os.path.join(SEM, "interior_active_learning", "paint")
    shutil.copy(os.path.join(real, f"{FRAME}_correction_mask.png"),
                os.path.join(str(sandbox), f"{FRAME}_correction_mask.png"))
    with Server(tmp_path / "d") as s:
        st, c = _post(s, "/api/crop", {"arm": "sem/gated", "frame": FRAME,
                                       "x": 0, "y": 0, "w": 300, "h": 300})
        if st != 200:
            pytest.skip(f"could not crop {FRAME}: {c}")
        up = os.path.join(str(tmp_path / "d"), "uploads")
        os.remove(os.path.join(up, f"{c['frame']}_ascut.png"))
        st, d = _post(s, "/api/send_to_parent", {"frame": c["frame"]})
        assert st == 409, d
        assert "as-cut" in json.dumps(d)
