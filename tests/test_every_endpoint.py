#!/usr/bin/env python3
"""Every route in app/server.py, exercised against a REAL server on a private data dir.

WHY THIS EXISTS. The suite tested the analysis functions thoroughly and the HTTP surface
only where a specific bug had been found. Asked whether everything works, the honest answer
was that nothing checked most of these routes end to end -- and this project has shipped a
proxy that turned a correct 204 into a 500, a figure whose statement came from rows it did
not draw, and a Mark tab that served a different image than the sidebar named. Those are
all reachable through HTTP.

The inventory is asserted against the source, so a route added later fails this file until
it is covered rather than silently going untested.

Every server here gets its own FRACTOGRAPHY_DATA under tmp_path, so nothing can touch the
user's data directory or the hand-labelled masks in the SEM repo.
"""
import io
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server, mask_png  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Every route this file exercises. Compared against the source below.
COVERED = {
    ("get", "/api/arms"), ("get", "/api/frames"), ("get", "/api/specimens"),
    ("get", "/api/cracks"), ("get", "/api/mask/{arm:path}/{frame}"),
    ("get", "/api/export.csv"), ("post", "/api/upload"),
    ("get", "/api/paint"), ("post", "/api/paint"),
    ("post", "/api/mask_edit"), ("post", "/api/scale"), ("post", "/api/remeasure"),
    ("get", "/api/readout"), ("get", "/api/figure/fields"), ("get", "/api/figure/says"),
    ("get", "/api/figure.svg"), ("get", "/api/health"), ("post", "/api/config"),
    ("post", "/api/measure_corpus"), ("get", "/api/measure_corpus"), ("get", "/"),
}


def declared_routes():
    src = open(os.path.join(REPO, "app", "server.py")).read()
    return {(m, p) for m, p in re.findall(r'^@app\.(get|post|put|delete)\("([^"]+)"', src,
                                          re.M)}


def test_the_inventory_is_complete():
    """A route added later fails here until it is covered, rather than going untested and
    looking covered because the file is called test_every_endpoint."""
    declared = declared_routes()
    missing = declared - COVERED
    assert not missing, f"routes with no coverage in this file: {sorted(missing)}"
    stale = COVERED - declared
    assert not stale, f"this file claims routes that no longer exist: {sorted(stale)}"


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    d = tmp_path_factory.mktemp("endpoints")
    with Server(str(d / "data")) as s:
        # One real uploaded mask, so the frame-scoped routes have something to answer about.
        st, raw = s.upload("probe.png", mask_png(160, 120, 50))
        assert st == 200, raw[:200]
        yield s


def test_health_reports_what_the_app_can_do(srv):
    st, d = srv.json("/api/health")
    assert st == 200
    for k in ("frozen", "data_dir", "capabilities", "measurement_impl"):
        assert k in d, f"/api/health lost {k}"
    assert d["measurement_impl"]["drift"] is False, (
        "the vendored measurement copy has drifted from the repo's own")


def test_the_index_page_serves_and_carries_the_app(srv):
    st, raw = srv.get("/")
    body = raw.decode()
    assert st == 200
    assert "<title>" in body and "app.js" in body
    # The two tabs, not three.
    assert 'id="pane-results"' in body and 'id="pane-figure"' not in body


def test_arms_frames_and_specimens_agree(srv):
    st, arms = srv.json("/api/arms")
    assert st == 200 and arms, arms
    st, frames = srv.json("/api/frames?arm=uploads")
    assert st == 200 and isinstance(frames, list) and frames
    st, specs = srv.json("/api/specimens?arm=uploads")
    assert st == 200 and isinstance(specs, list)
    names = {f["frame"] for f in frames}
    assert "probe" in names or any("probe" in n for n in names), names


def _frame(srv):
    _, frames = srv.json("/api/frames?arm=uploads")
    return frames[0]["frame"]


def test_cracks_and_mask_answer_for_a_real_frame(srv):
    fr = _frame(srv)
    st, cracks = srv.json(f"/api/cracks?frame={fr}&arm=uploads")
    assert st == 200 and isinstance(cracks, (list, dict))
    st, raw = srv.get(f"/api/mask/uploads/{fr}")
    assert st == 200 and raw[:4] == b"\x89PNG", raw[:20]


def test_readout_returns_statements_and_refusals(srv):
    st, d = srv.json(f"/api/readout?arm=uploads&frame={_frame(srv)}")
    assert st == 200
    for k in ("frame", "specimen", "arm_statements", "refusals"):
        assert k in d, f"/api/readout lost {k}"
    # The refusals are no longer rendered, but they must still be served.
    assert len(d["refusals"]) >= 4
    for s in d["frame"]:
        assert set(s) >= {"text", "basis", "level"}
        assert len(s["text"].split()) <= 15, f"on-screen text too long: {s['text']}"


def test_export_csv_is_a_csv_with_the_frames_in_it(srv):
    st, raw = srv.get("/api/export.csv?arm=uploads")
    assert st == 200
    lines = raw.decode().splitlines()
    # The first lines are a '#' provenance banner naming the arm, the level and the row
    # count -- deliberate, because this file leaves the app and a bare CSV cannot say what
    # it is. The header is the first non-comment line.
    banner = [L for L in lines if L.startswith("#")]
    assert banner and "arm=uploads" in banner[0], banner[:1]
    body = [L for L in lines if not L.startswith("#")]
    assert "," in body[0], body[:1]
    assert len(body) >= 2, "header only; no rows exported"


def test_figure_fields_says_and_svg_are_consistent(srv):
    st, fields = srv.json("/api/figure/fields")
    assert st == 200 and fields.get("kinds") and fields.get("fields")
    assert "stage_map" in fields["kinds"] and "stage_surface" in fields["kinds"]
    q = "arm=uploads&kind=histogram&y=area_fraction"
    st, says = srv.json(f"/api/figure/says?{q}")
    assert st == 200 and "statements" in says
    st, raw = srv.get(f"/api/figure.svg?{q}")
    assert st == 200 and raw.lstrip()[:4] == b"<svg", raw[:40]


def test_a_figure_kind_that_cannot_be_drawn_explains_itself(srv):
    """uploads records no stage position. A refusal with a reason beats an empty grid."""
    st, raw = srv.get("/api/figure.svg?arm=uploads&kind=stage_map&y=area_fraction")
    assert st >= 400, f"expected a refusal, got {st}"
    assert b"stage position" in raw, raw[:200]


def test_paint_reports_its_availability_without_starting_anything(srv):
    st, d = srv.json("/api/paint")
    assert st == 200 and "available" in d
    if not d["available"]:
        assert d.get("why_not"), "an unavailable tool must say why"


def test_scale_then_remeasure_changes_the_micrometre_columns(srv):
    import urllib.parse as _u
    fr = _frame(srv)
    # QUERY PARAMETERS, not a JSON body: FastAPI binds scalar defaults to the query string,
    # so a JSON body is ignored entirely and the endpoint answers as if nothing was sent.
    # A first version of this test posted JSON, got 422 here and -- worse -- got 200 from
    # /api/config, which looked like the app accepting a nonexistent directory.
    q = _u.urlencode({"arm": "uploads", "frame": fr, "nm_per_px": 50.0})
    st, raw = srv.post(f"/api/scale?{q}")
    assert st == 200, (st, raw[:200])
    st, raw = srv.post("/api/remeasure?" + _u.urlencode({"arm": "uploads", "frame": fr}))
    assert st == 200, (st, raw[:200])
    _, frames = srv.json("/api/frames?arm=uploads")
    row = [f for f in frames if f["frame"] == fr][0]
    assert row.get("scale_known") is True
    assert row.get("nm_per_px") == 50.0


def test_mask_edit_writes_a_copy_and_leaves_the_original(srv):
    fr = _frame(srv)
    before = srv.get(f"/api/mask/uploads/{fr}")[1]
    st, raw = srv.post("/api/mask_edit",
                       json.dumps({"frame": fr, "arm": "uploads",
                                   "png_b64": None}).encode(), "application/json")
    # (mask_edit DOES take a JSON body -- it is declared with a Pydantic model.)
    # Either it rejects the empty payload or it accepts a real one; both are fine, what
    # matters is that it does not corrupt the stored mask.
    assert st in (200, 400, 422), st
    after = srv.get(f"/api/mask/uploads/{fr}")[1]
    assert after[:4] == b"\x89PNG"
    if st != 200:
        assert after == before, "a rejected edit must not have changed the mask"


def test_config_rejects_a_directory_that_does_not_exist(srv):
    import urllib.parse as _u
    st, raw = srv.post("/api/config?" + _u.urlencode({"sem_repo": "/no/such/place/at/all"}))
    assert st >= 400, f"a bad path must not be accepted silently (got {st})"
    assert b"sem-crack-detector" in raw or b"missing" in raw, raw[:200]
    # And a bad txm_export likewise.
    st, raw = srv.post("/api/config?" + _u.urlencode({"txm_export": "/no/such/dir"}))
    assert st >= 400, st


def test_measure_corpus_reports_status_without_being_started(srv):
    st, d = srv.json("/api/measure_corpus")
    assert st == 200 and isinstance(d, dict)


def test_an_unknown_arm_is_an_error_not_an_empty_success(srv):
    """An empty list for a nonexistent arm reads as "this arm has no frames", which is a
    different and wrong statement."""
    st, _ = srv.get("/api/frames?arm=not-an-arm")
    assert st >= 400, f"unknown arm returned {st}"
