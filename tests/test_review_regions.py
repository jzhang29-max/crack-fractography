#!/usr/bin/env python3
"""Reviewed regions: the control that makes precision measurable on this corpus.

WHY IT EXISTS. Measured over the 48 hand-labelled SEM frames: of the 41,265,259 pixels
counted as detector false positives, 244,493 (0.59%) were marked not-crack by a human and
41,020,766 (99.41%) were never looked at. 35 of 48 frames carry no not-crack mark at all.
Pooled precision is 0.2945 counting unreviewed as wrong and 0.9860 excluding it, and
neither end measures the detector.

The missing ingredient is verified NEGATIVES. More crack strokes raise the ceiling and
never supply a denominator. A reviewed region supplies one: a box in which every pixel
carries a verdict, so a detector pixel inside it is a true or a false positive with a
human behind the judgement either way.

THE TWO WAYS THIS COULD HAVE BEEN USELESS, both tested below:
  1. Scoring against sem/gated. gated_masks.py:122 builds it as
     `(machine | (painted & darker)) & ~notc`, so it contains the human's own strokes and
     can never fire where a human said not-crack -- precision 1 by construction.
  2. Scoring a verdict against the very file it was copied from, which is what an uploads
     frame with no edit is. Also precision 1, also by construction.
"""
import io
import json
import os
import sys

import numpy as np
import pytest
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server, mask_png  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from app import paths as P  # noqa: E402

SEM = P.sem_repo()
_GATED = os.path.join(SEM or "", "crack_export", "derived", "gated_masks")
_MACHINE = os.path.join(SEM or "", "crack_export", "derived", "machine_masks")
needs_sem = pytest.mark.skipif(
    not SEM or not os.path.isdir(_MACHINE),
    reason="no sem-crack-detector checkout with machine masks on this machine")


def _sem_frame():
    if not os.path.isdir(_MACHINE) or not os.path.isdir(_GATED):
        return None
    for f in sorted(os.listdir(_MACHINE)):
        if f.endswith("_machine.png"):
            n = f[:-len("_machine.png")]
            if os.path.exists(os.path.join(_GATED, f"{n}_gated.png")):
                return n
    return None


FRAME = _sem_frame()
needs_frame = pytest.mark.skipif(FRAME is None, reason="no paired SEM mask available")


def _post(s, path, obj):
    st, raw = s.post(path, json.dumps(obj).encode(), "application/json")
    return st, (json.loads(raw) if raw else None)


def _seed(s, name="u", bar=40):
    st, raw = s.upload(f"{name}.png", mask_png(400, 300, bar))
    assert st == 200, raw[:200]
    up = json.loads(raw)
    return up["frames"][0]["frame"] if "frames" in up else up["frame"]


def test_nothing_reviewed_is_said_plainly_rather_than_scored(tmp_path):
    """Zero regions must not come back as an empty confusion matrix, which reads as a
    measurement of zero rather than as the absence of one."""
    with Server(tmp_path / "d") as s:
        st, d = s.json("/api/review_scores")
        assert st == 200
        assert d["n_regions"] == 0
        assert "not estimable" in d["note"]
        assert "pooled" not in d


def test_a_verdict_read_from_the_file_it_would_be_scored_against_is_refused(tmp_path):
    """THE UNFALSIFIABLE CASE. When the verdict is copied from the very PNG it will be
    scored against -- an uploads frame with no edit, or any frame marked reviewed without
    touching it -- every pixel agrees and the region returns precision 1.0 having
    measured nothing. Nothing in the stored data could have come out differently, so it
    cannot distinguish "checked and agreed" from "clicked without looking".

    This project has shipped that shape of error before: a control that correlated 0.9989
    with the variable it was controlling for. A score of exactly 1.0 is its symptom, so
    the case is refused rather than explained in a footnote. Genuine agreement is still
    recordable -- edit the frame, change nothing, and the verdict becomes a separate
    artifact; see the unchanged-region test below."""
    with Server(tmp_path / "d") as s:
        f = _seed(s)
        st, d = _post(s, "/api/review_region",
                      {"arm": "uploads", "frame": f, "box": [0, 0, 200, 150]})
        assert st == 200, d
        st, sc = s.json("/api/review_scores")
        assert sc["n_regions_refused_as_circular"] == 1, sc
        assert sc["n_scored"] == 0
        assert sc["pooled"]["precision"] is None, sc["pooled"]
        assert "same file" in sc["regions"][0]["error"]


@pytest.mark.parametrize("box", [[0, 0, 8, 8], [0, 0, 400, 8], [0, 0, 5000, 150],
                                 [-1, 0, 100, 100], "x", [1, 2, 3], None])
def test_a_box_that_cannot_be_reviewed_is_refused(tmp_path, box):
    with Server(tmp_path / "d") as s:
        f = _seed(s)
        st, _ = _post(s, "/api/review_region", {"arm": "uploads", "frame": f, "box": box})
        assert st in (400, 409), f"{box!r} was accepted"


def test_an_unknown_frame_cannot_reach_the_filesystem(tmp_path):
    with Server(tmp_path / "d") as s:
        _seed(s)
        for bad in ("../../../etc/passwd", "..", "a/b", ""):
            st, _ = _post(s, "/api/review_region",
                          {"arm": "uploads", "frame": bad, "box": [0, 0, 100, 100]})
            assert st in (400, 404), f"{bad!r} was accepted"


@needs_sem
@needs_frame
def test_the_whole_loop_on_a_real_frame(tmp_path):
    """Correct the detector inside a box, declare the box reviewed, and get a precision
    with a real denominator -- without writing one byte into the SEM repo."""
    before = {f: os.path.getmtime(os.path.join(_MACHINE, f))
              for f in os.listdir(_MACHINE)}
    with Server(tmp_path / "d") as s:
        st, raw = s.get(f"/api/mask/sem/machine/{FRAME}")
        assert st == 200
        base = np.array(Image.open(io.BytesIO(raw)).convert("L"))
        x, y, w, h = 1800, 1200, 1200, 800
        if y + h > base.shape[0] or x + w > base.shape[1]:
            pytest.skip(f"{FRAME} is {base.shape[1]}x{base.shape[0]}, too small")
        piece = base[y:y + h, x:x + w].copy()
        piece[100:200, 100:300] = 0        # a crack the detector missed -> 20,000 FN
        piece[400:460, 500:900] = 255      # something it got wrong -> some FP
        b = io.BytesIO(); Image.fromarray(piece, mode="L").save(b, "PNG")
        st, raw = s.upload(f"{FRAME}.png", b.getvalue(),
                           path=f"/api/mask_edit?arm=sem/machine&frame={FRAME}"
                                f"&box={x},{y},{w},{h}")
        assert st == 200, raw[:300]

        st, d = _post(s, "/api/review_region",
                      {"arm": "sem/machine", "frame": FRAME, "box": [x, y, w, h]})
        assert st == 200, d
        assert d["n_px"] == w * h
        assert d["n_crack_px"] > 0

        st, sc = s.json("/api/review_scores")
        assert st == 200, sc
        assert sc["n_scored"] == 1 and sc["n_regions_refused_as_circular"] == 0, sc
        r = sc["regions"][0]
        assert r["scored_against"] == "sem/machine"
        # the 20,000 px of crack the human added are false negatives, exactly
        assert r["fn"] == 20000, r
        assert r["fp"] > 0, "the removed region produced no false positives"
        assert r["human_changed_nothing"] is False
        # every pixel of the box is accounted for -- that is what "reviewed" means
        assert r["tp"] + r["fp"] + r["fn"] + r["tn"] == w * h, r
        assert sc["pooled"]["reviewed_px"] == w * h

    after = {f: os.path.getmtime(os.path.join(_MACHINE, f)) for f in os.listdir(_MACHINE)}
    assert before == after, "the SEM repo's machine masks were written to"


@needs_sem
@needs_frame
def test_a_sem_gated_region_is_never_scored_against_gated(tmp_path):
    """THE CIRCULARITY THAT WOULD HAVE MADE THIS WORTHLESS. gated_masks.py:122 is
    `gated = (machine | (painted & darker)) & ~notc`: it unions the human's crack strokes
    into the "prediction" and subtracts not-crack, so it can never fire on a pixel a
    human called not-crack. Scoring a human verdict against it returns precision 1 by
    construction, which is how this project once built a whole chart on contaminated
    masks."""
    with Server(tmp_path / "d") as s:
        st, raw = s.get(f"/api/mask/sem/gated/{FRAME}")
        assert st == 200
        g = np.array(Image.open(io.BytesIO(raw)).convert("L"))
        x, y, w, h = 1800, 1200, 1200, 800
        if y + h > g.shape[0] or x + w > g.shape[1]:
            pytest.skip("frame too small")
        st, d = _post(s, "/api/review_region",
                      {"arm": "sem/gated", "frame": FRAME, "box": [x, y, w, h]})
        assert st == 200, d
        st, sc = s.json("/api/review_scores")
        r = sc["regions"][0]
        assert r.get("scored_against") == "sem/machine", (
            f"a sem/gated region was scored against {r.get('scored_against')!r}; gated "
            f"contains the labels and can only come out perfect")
        assert r.get("precision") != 1.0 or r.get("fp") == 0


@needs_sem
@needs_frame
def test_agreeing_with_the_detector_is_a_verdict_but_is_counted_apart(tmp_path):
    """"I checked this and the detector is right here" is the assertion that gave
    AS_24hr_BSE_Side_008 its 1,016 negatives -- 92.4% of every negative in the corpus --
    so refusing it would recreate the rule that starved this corpus. But it cannot
    discriminate, and a wall of agreements reads as a perfect detector, so it is counted
    separately and the gap between the two pooled numbers is on the record."""
    with Server(tmp_path / "d") as s:
        x, y, w, h = 1800, 1200, 600, 400
        st, raw = s.get(f"/api/mask/sem/machine/{FRAME}")
        base = np.array(Image.open(io.BytesIO(raw)).convert("L"))
        if y + h > base.shape[0] or x + w > base.shape[1]:
            pytest.skip("frame too small")
        # A REVIEW THAT AGREES, BUT THROUGH AN ARTIFACT OF ITS OWN. The human opened the
        # box, went over it, and changed nothing -- so there IS a separate stored edit
        # and the verdict is not a byte-copy of the file it will be scored against. That
        # is the difference between "agreed" and "unfalsifiable": marking a region
        # reviewed with no edit at all leaves nothing in the data that could have come
        # out differently, and is refused by the test above.
        piece = base[y:y + h, x:x + w].copy()
        b = io.BytesIO(); Image.fromarray(piece, mode="L").save(b, "PNG")
        st, raw = s.upload(f"{FRAME}.png", b.getvalue(),
                           path=f"/api/mask_edit?arm=sem/machine&frame={FRAME}"
                                f"&box={x},{y},{w},{h}")
        assert st == 200, raw[:300]
        st, d = _post(s, "/api/review_region",
                      {"arm": "sem/machine", "frame": FRAME, "box": [x, y, w, h]})
        assert st == 200, d
        st, sc = s.json("/api/review_scores")
        assert sc["n_regions_refused_as_circular"] == 0, (
            "a region recorded from the user's own edit is not circular -- the edit is a "
            "separate artifact from the detector output it is scored against")
        assert sc["n_regions_human_changed_nothing"] == 1, sc
        assert sc["pooled"]["precision"] == 1.0, sc["pooled"]
        assert sc["pooled_excluding_unchanged"]["precision"] is None, (
            "an agreement-only corpus must not report a precision once the agreements "
            "are set aside")
        assert sc["pooled_excluding_unchanged"]["n_regions"] == 0


def test_a_region_can_be_removed(tmp_path):
    with Server(tmp_path / "d") as s:
        f = _seed(s)
        st, d = _post(s, "/api/review_region",
                      {"arm": "uploads", "frame": f, "box": [0, 0, 200, 150]})
        rid = d["id"]
        assert os.path.exists(os.path.join(str(tmp_path / "d"), "reviewed", rid + ".png"))
        st, _ = _post(s, "/api/review_region", {"frame": f, "delete": True, "id": rid})
        assert st == 200
        assert s.json("/api/reviewed")[1]["n"] == 0
        assert not os.path.exists(
            os.path.join(str(tmp_path / "d"), "reviewed", rid + ".png"))
        # and the image itself is untouched
        assert any(r["frame"] == f for r in s.dataset("frames"))
