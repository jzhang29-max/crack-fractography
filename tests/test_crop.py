#!/usr/bin/env python3
"""Cropping a frame: the box, the pixels, the provenance, and the micrograph behind it.

Driven over real HTTP against a live server on a private data directory, not by reading
the source of the endpoint. This repo already has source-scan tests, and a source scan
asserts that a function MENTIONS something -- it cannot tell a working crop from one that
writes the right-shaped file full of the wrong pixels.
"""
import io
import json
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server


def _mask(w, h, boxes):
    """A white mask with black rectangles at `boxes` = [(x0,y0,x1,y1), ...]."""
    im = Image.new("L", (w, h), 255)
    for (x0, y0, x1, y1) in boxes:
        for y in range(y0, y1):
            for x in range(x0, x1):
                im.putpixel((x, y), 0)
    out = io.BytesIO(); im.save(out, "PNG"); return out.getvalue()


def _seed(s, name="parent", w=400, h=300, boxes=((20, 20, 180, 40),)):
    st, raw = s.upload(f"{name}.png", _mask(w, h, list(boxes)))
    assert st == 200, raw[:300]
    return json.loads(raw)


def _crop(s, frame, x, y, w, h, arm="uploads"):
    st, raw = s.post("/api/crop", json.dumps(
        {"arm": arm, "frame": frame, "x": x, "y": y, "w": w, "h": h}).encode(),
        "application/json")
    return st, json.loads(raw) if raw else None


def test_the_crop_holds_the_pixels_that_were_in_the_box(tmp_path):
    """The one thing a crop must get right. A crop of the right SHAPE containing the wrong
    REGION is the failure that no shape assertion can see, so this puts a mark in a known
    place and checks the crop contains it and the region beside it does not."""
    with Server(tmp_path / "d") as s:
        up = _seed(s, "p1", 400, 300, [(200, 100, 260, 160)])   # one black square, right half
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, left = _crop(s, f, 0, 0, 150, 300)
        assert st == 200, left
        st, right = _crop(s, f, 180, 80, 160, 140)
        assert st == 200, right
        # The square is entirely inside the right box and entirely outside the left one.
        assert left["n_cracks"] == 0, f"the left crop should be blank, got {left}"
        assert right["n_cracks"] == 1, f"the right crop should hold the square, got {right}"
        assert right["area_fraction"] > 0.1, right["area_fraction"]


def test_a_crop_records_the_box_it_was_cut_from(tmp_path):
    """Provenance is the whole defence against a measurement drifting loose from the region
    it describes. The parent, the box and the parent's size must all be on the frame."""
    with Server(tmp_path / "d") as s:
        up = _seed(s, "p2", 400, 300)
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, d = _crop(s, f, 10, 20, 200, 150)
        assert st == 200, d
        rec = next(r for r in s.dataset("frames") if r["frame"] == d["frame"])
        cf = rec["cropped_from"]
        assert cf["frame"] == f
        assert cf["box_px"] == [10, 20, 200, 150]
        assert cf["parent_size_px"] == [400, 300]


def test_a_box_running_off_the_edge_is_clamped_and_says_so(tmp_path):
    with Server(tmp_path / "d") as s:
        up = _seed(s, "p3", 400, 300)
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, d = _crop(s, f, 300, 200, 400, 400)
        assert st == 200, d
        assert d["clamped"] is True
        assert d["box_px"] == [300, 200, 100, 100], d["box_px"]


def test_a_crop_too_small_to_measure_is_refused(tmp_path):
    with Server(tmp_path / "d") as s:
        up = _seed(s, "p4", 400, 300)
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, d = _crop(s, f, 0, 0, 10, 10)
        assert st == 400
        assert "too small" in json.dumps(d).lower()


def test_the_crop_reports_the_censoring_it_created(tmp_path):
    """A crack comfortably inside the parent can touch the edge of the crop, which turns its
    length into a lower bound. That change is invisible in the numbers unless it is said."""
    with Server(tmp_path / "d") as s:
        # a long bar well inside the parent; the crop cuts through it
        up = _seed(s, "p5", 400, 300, [(50, 140, 350, 160)])
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, whole = _crop(s, f, 20, 100, 360, 120)     # bar fully inside -> no new censoring
        assert st == 200, whole
        st, cut = _crop(s, f, 100, 100, 150, 120)      # crop slices the bar -> censored
        assert st == 200, cut
        assert whole["n_censored"] == 0, whole
        assert cut["n_censored"] >= 1, cut
        assert "lower bound" in cut["note"]


def test_a_crop_of_a_frame_with_no_micrograph_says_so(tmp_path):
    """An uploaded mask has no original behind it. The crop still works, but painting on a
    bare binary mask has nothing underneath to judge a boundary against, so it is stated
    rather than left for the user to discover at the brush."""
    with Server(tmp_path / "d") as s:
        up = _seed(s, "p6", 400, 300)
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, d = _crop(s, f, 0, 0, 200, 200)
        assert st == 200, d
        assert d["original_cropped"] is False
        assert d["original_note"] and "micrograph" in d["original_note"]
        # and the viewer agrees there is nothing to show
        st2, _ = s.get(f"/api/original/uploads/{d['frame']}")
        assert st2 == 404


def test_a_crop_can_itself_be_cropped(tmp_path):
    """A crop is a frame, which is the whole design. If a crop could not be cropped, it
    would be a viewport wearing a frame's name."""
    with Server(tmp_path / "d") as s:
        up = _seed(s, "p7", 400, 300, [(100, 100, 300, 200)])
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, a = _crop(s, f, 50, 50, 300, 220)
        assert st == 200, a
        st, b = _crop(s, a["frame"], 10, 10, 200, 150)
        assert st == 200, b
        rec = next(r for r in s.dataset("frames") if r["frame"] == b["frame"])
        assert rec["cropped_from"]["frame"] == a["frame"]


def test_the_crop_does_not_invent_a_scale(tmp_path):
    """A crop does not magnify, so it inherits the parent's nm/px -- and when the parent has
    none, the crop must not acquire one."""
    with Server(tmp_path / "d") as s:
        up = _seed(s, "p8", 400, 300)
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, d = _crop(s, f, 0, 0, 200, 200)
        assert st == 200, d
        assert d["scale_known"] is False
        rec = next(r for r in s.dataset("frames") if r["frame"] == d["frame"])
        assert rec.get("nm_per_px") in (None, 0), rec.get("nm_per_px")


def test_the_crop_can_be_opened_and_painted(tmp_path):
    """THE WHOLE POINT OF A CROP IS TO DRAW ON IT. The crop was first written under its bare
    stem while the uploads arm resolves masks as `<frame>_gated.png`, so the crop was
    measured and listed as a frame while /api/mask and mask_edit both 404'd on it -- it
    appeared in the sidebar and could not be opened. Nothing in the crop's own response
    said so: it reported a frame, a crack count and an area fraction, all correct.
    """
    with Server(tmp_path / "d") as s:
        up = _seed(s, "p9", 400, 300, [(100, 100, 300, 200)])
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, d = _crop(s, f, 50, 50, 300, 220)
        assert st == 200, d
        child = d["frame"]

        # 1. the mask is fetchable, and it is the size of the box
        st, raw = s.get(f"/api/mask/uploads/{child}")
        assert st == 200, f"the crop's mask could not be fetched: {st}"
        im = Image.open(io.BytesIO(raw))
        assert im.size == (300, 220), im.size

        # 2. an edit to it is accepted and re-measured
        edited = _mask(300, 220, [(0, 0, 300, 110)])     # half the crop painted black
        st, raw = s.upload(f"{child}.png", edited,
                           path=f"/api/mask_edit?arm=uploads&frame={child}")
        assert st == 200, raw[:300]
        rec = next(r for r in s.dataset("frames") if r["frame"] == child)
        assert rec["area_fraction"] > 0.4, (
            f"the painted mask was not re-measured: area {rec['area_fraction']}")


# --- THE DATABAR ------------------------------------------------------------------------
def _match(ow, oh, mw, mh):
    from app.server import _match_original_to_mask
    return _match_original_to_mask(Image.new("L", (ow, oh)), (mw, mh))


def test_a_databar_band_is_trimmed_so_the_overlay_lines_up():
    """SEM originals carry the databar below the image: 6144x4376 against a 6144x4096 mask.
    Both were stretched into the same canvas, so the micrograph was squashed by 4096/4376
    and a mask pixel sat up to 280 source rows from the feature it marked -- worst at the
    bottom, where the databar was itself being painted over."""
    im, why = _match(6144, 4376, 6144, 4096)
    assert im.size == (6144, 4096), im.size
    assert why and "280" in why


def test_an_original_that_already_matches_is_untouched():
    im, why = _match(3914, 3899, 3914, 3899)
    assert im.size == (3914, 3899)
    assert why is None


def test_a_mismatch_of_any_other_shape_is_refused_not_rescaled():
    """Trimming is only ever from the bottom and only when the widths already agree. A
    rescale would put a correct mask over the wrong picture with nothing to say so."""
    for ow, oh in ((3000, 4376), (6144, 3000), (6000, 4376)):
        im, why = _match(ow, oh, 6144, 4096)
        assert im.size == (ow, oh), f"{ow}x{oh} was altered"
        assert why and "not the same region" in why


def test_a_databar_is_trimmed_end_to_end_and_the_crop_takes_the_right_region(tmp_path):
    """The trim, driven through the real server rather than called directly.

    A 400x340 micrograph behind a 400x300 mask is the SEM shape in miniature: 40 rows of
    databar. The crop must come from the IMAGE area, so a box at y=100 is row 100 of the
    specimen -- not row 100 of a picture that has been squashed to fit.
    """
    with Server(tmp_path / "d") as s:
        up = _seed(s, "pd", 400, 300, [(40, 40, 360, 80)])
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")

        # a micrograph 40 rows taller than the mask, with a known bright stripe at y=120
        # and a black "databar" band below the image area
        im = Image.new("L", (400, 340), 30)
        for y in range(120, 140):
            for x in range(400):
                im.putpixel((x, y), 240)
        for y in range(300, 340):
            for x in range(400):
                im.putpixel((x, y), 0)
        updir = os.path.join(str(tmp_path / "d"), "uploads")
        assert os.path.isdir(updir), sorted(os.listdir(str(tmp_path / "d")))
        im.save(os.path.join(updir, f"{f}_original.png"))

        # the viewer now serves it at the MASK's aspect ratio, databar removed
        st, raw = s.get(f"/api/original/uploads/{f}")
        assert st == 200, st
        served = Image.open(io.BytesIO(raw))
        assert abs(served.width / served.height - 400 / 300) < 0.01, (
            f"served {served.size}; the databar was not trimmed")

        # and a crop takes the box from the image area
        st, d = _crop(s, f, 0, 90, 400, 100)
        assert st == 200, d
        assert d["original_cropped"] is True, d.get("original_note")
        cut = Image.open(os.path.join(updir, f"{d['frame']}_original.png"))
        assert cut.size == (400, 100), cut.size
        a = cut.convert("L")
        # the stripe at image rows 120..140 lands at crop rows 30..50, and nowhere else
        assert a.getpixel((200, 40)) > 200, "the crop did not take the stripe"
        assert a.getpixel((200, 5)) < 60, "the crop is offset from the image area"
        assert a.getpixel((200, 90)) < 60, "the crop is offset from the image area"


# --- A CROP IS NOT AN INDEPENDENT FRAME -------------------------------------------------
def _cmp(s, fa, fb):
    body = {"a": {"name": "A", "frames": [{"arm": "uploads", "frame": fa}]},
            "b": {"name": "B", "frames": [{"arm": "uploads", "frame": fb}]}}
    st, raw = s.post("/api/group_compare", json.dumps(body).encode(), "application/json")
    return st, json.loads(raw)


def test_comparing_a_crop_against_its_parent_is_called_out(tmp_path):
    """The same pixels on both sides is not a comparison. It cannot fail to agree, and the
    agreement means nothing -- the same error one level up is what makes a crop-fed retrain
    look like an improvement."""
    with Server(tmp_path / "d") as s:
        up = _seed(s, "ov1", 400, 300, [(100, 100, 300, 200)])
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, c = _crop(s, f, 50, 50, 300, 200)
        assert st == 200, c
        st, d = _cmp(s, f, c["frame"])
        assert st == 200, d
        assert d["pixel_overlaps"], "the overlap went unreported"
        assert "SHARE PIXELS" in d["caveats"][0], d["caveats"]


def test_two_crops_that_do_not_touch_are_not_called_overlapping(tmp_path):
    """The guard must distinguish. Two disjoint boxes of one parent are different pixels,
    and flagging them would make the warning noise that gets ignored when it matters."""
    with Server(tmp_path / "d") as s:
        up = _seed(s, "ov2", 400, 300, [(0, 0, 400, 300)])
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, left = _crop(s, f, 0, 0, 150, 300)
        assert st == 200, left
        st, right = _crop(s, f, 200, 0, 150, 300)
        assert st == 200, right
        st, d = _cmp(s, left["frame"], right["frame"])
        assert st == 200, d
        assert not d["pixel_overlaps"], d["pixel_overlaps"]
        assert not any("SHARE PIXELS" in c for c in d.get("caveats", []))


def test_overlap_is_found_through_a_crop_of_a_crop(tmp_path):
    """A crop of a crop is still the parent's pixels. Walking only one step up would miss
    it, and one step is the version anyone writes first."""
    with Server(tmp_path / "d") as s:
        up = _seed(s, "ov3", 400, 300, [(0, 0, 400, 300)])
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, a = _crop(s, f, 0, 0, 300, 300)
        assert st == 200, a
        st, aa = _crop(s, a["frame"], 0, 0, 100, 100)     # grandchild of f
        assert st == 200, aa
        st, d = _cmp(s, f, aa["frame"])
        assert st == 200, d
        assert d["pixel_overlaps"], "a grandchild crop was not traced to its root"
        assert d["pixel_overlaps"][0]["share_of_smaller"] == 1.0, d["pixel_overlaps"]


def test_a_crop_advertises_its_micrograph_per_frame(tmp_path):
    """ARM_HAS_ORIGINALS is per-ARM and says uploads has none, which is right for an
    uploaded mask and wrong for a crop. The editor consulted only the arm flag, so a crop
    opened as a bare binary mask with the micrograph sitting fetchable on disk."""
    with Server(tmp_path / "d") as s:
        up = _seed(s, "hv", 400, 300, [(40, 40, 360, 80)])
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        updir = os.path.join(str(tmp_path / "d"), "uploads")
        Image.new("L", (400, 300), 90).save(os.path.join(updir, f"{f}_original.png"))
        st, d = _crop(s, f, 0, 0, 200, 200)
        assert st == 200, d
        rec = next(r for r in s.dataset("frames") if r["frame"] == d["frame"])
        assert rec.get("has_original") is True, (
            "the crop does not advertise its micrograph, so the editor will not load it")
        # an uploaded mask with no micrograph must NOT claim one
        st, d2 = _crop(s, f, 200, 0, 200, 200)
        assert st == 200, d2
        os.remove(os.path.join(updir, f"{f}_original.png"))
        st, d3 = _crop(s, f, 0, 100, 200, 200)
        rec3 = next(r for r in s.dataset("frames") if r["frame"] == d3["frame"])
        assert rec3.get("has_original") is False, rec3.get("has_original")


def test_the_crop_keeps_a_pristine_copy_of_what_it_cut(tmp_path):
    """Painting overwrites the crop's mask in place. Without a copy of what the detector
    proposed, "which pixels did the human actually change" has no answer -- and that
    question is the whole basis of sending strokes back to a parent's correction mask.
    Without it, confirming a crop asserts a verdict on every pixel in the box."""
    with Server(tmp_path / "d") as s:
        up = _seed(s, "ac", 400, 300, [(100, 100, 300, 200)])
        f = up["frames"][0]["frame"] if "frames" in up else up.get("frame")
        st, d = _crop(s, f, 50, 50, 200, 200)
        assert st == 200, d
        updir = os.path.join(str(tmp_path / "d"), "uploads")
        gated = os.path.join(updir, f"{d['frame']}_gated.png")
        ascut = os.path.join(updir, f"{d['frame']}_ascut.png")
        assert os.path.exists(ascut), "no pristine copy was kept"
        a, b = Image.open(ascut).convert("L"), Image.open(gated).convert("L")
        assert a.size == b.size == (200, 200)
        pristine = a.tobytes()
        assert pristine == b.tobytes(), "the copy differs from what was cut"

        # now paint the crop, and the pristine copy must NOT follow
        edited = _mask(200, 200, [(0, 0, 200, 100)])
        st, raw = s.upload(f"{d['frame']}.png", edited,
                           path=f"/api/mask_edit?arm=uploads&frame={d['frame']}")
        assert st == 200, raw[:200]
        after_gated = Image.open(gated).convert("L").tobytes()
        after_ascut = Image.open(ascut).convert("L").tobytes()
        assert after_gated != after_ascut, (
            "the pristine copy was overwritten by the edit, so the diff is now empty "
            "and every painted pixel would be invisible")
        assert after_ascut == pristine, "the pristine copy changed"
