#!/usr/bin/env python3
"""A statement must not ship prose that the code behind it has withdrawn.

/api/readout renders `stage_gradient.note` for a specimen whose fields trend across the
patch. That note is a CONSTANT -- it carries no rho, no ratio, no field count -- yet a copy
of it is frozen into every specimen record when the measurement runs, and `for_specimen`
printed the frozen copy.

`analysis/stage.py` later replaced the note's ending. It used to assert a remedy ("-- more
patches would" narrow the interval); n_patches is 1 on every positioned arm in this corpus,
so between-patch variance has never been observed and the remedy is untested. The module's
own comment says exactly that. The records already on disk kept the old sentence: measured
on the shipped corpus, 6 of the 8 stage_gradient records still end "more patches would",
while app.js's own +/-% badge tooltip on the SAME screen says it is untested. Nothing on
screen distinguished the six stale records from the two re-measured ones.

These drive the live endpoint with a record carrying the OLD note, because that is the only
input that can see the defect: a test seeded with the current note passes either way.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server, REPO                                  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "analysis"))

#: The exact retracted ending, as six records in the shipped corpus still carry it.
RETRACTED = ("ASTM E562 presumes fields placed over a surface. A gradient means the "
             "between-field variance is partly a trend across one patch, so more tiles "
             "in the same patch will not narrow the interval -- more patches would.")

ARM = "sem/gated"
SPEC = "STALE_NOTE"


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    d = tmp_path_factory.mktemp("stale")
    frames = [{"frame": f"{SPEC}_{i:02d}_CBS", "arm": ARM, "specimen": SPEC,
               "area_fraction": 0.01 * (i + 1), "scale_known": True,
               "nm_per_px": 51.883, "largest_share_of_area": 0.4,
               "n_cracks_measured": 2, "speck_count": 0, "crack_area_px": 50,
               "n_junctions": 0, "mean_width_px_median": 2.0,
               "censored_share": 0.0, "censored_share_by_area": 0.0,
               "censored_share_by_length": 0.0} for i in range(9)]
    spec = [{"arm": ARM, "specimen": SPEC, "n_frames": 9, "n_fields": 9,
             "area_fraction_median": 0.05, "scale_known_frames": 9,
             "area_fraction_ci": {"mean": 0.05, "sd_between_fields": 0.0274,
                                  "n_fields": 9, "ci95_halfwidth": 0.0211,
                                  "ci95_lo": 0.0289, "ci95_hi": 0.0711,
                                  "ci95_lo_clamped": False,
                                  "pct_relative_accuracy": 42.1, "t95": 2.306,
                                  "n_fields_off_determination": 0, "nm_per_px": 51.883},
             #: THE STALE RECORD. Everything else here exists to make this render.
             "stage_gradient": {"axis": "stage_y", "spearman_rho": 0.867,
                                "p_value": 0.002495, "n_frames_with_position": 9,
                                "field_max_min_ratio": 8.5, "significant": True,
                                "note": RETRACTED},
             "n_patches": 1}]
    #: A SECOND REAL SPECIMEN, so the arm-level ranking refusal fires at all -- it needs
    #: len(real) > 1, and without it the last test in this file asserts over an empty list.
    frames += [{**frames[0], "frame": "OTHER_00_CBS", "specimen": "OTHER",
                "area_fraction": 0.02}]
    spec += [{"arm": ARM, "specimen": "OTHER", "n_frames": 1, "n_fields": 1,
              "area_fraction_median": 0.02, "scale_known_frames": 1,
              "area_fraction_ci": None, "n_patches": 1}]
    with open(os.path.join(d, "frames.json"), "w", encoding="utf-8") as fh:
        json.dump(frames, fh)
    with open(os.path.join(d, "specimens.json"), "w", encoding="utf-8") as fh:
        json.dump(spec, fh)
    with open(os.path.join(d, "cracks.json"), "w", encoding="utf-8") as fh:
        json.dump([], fh)
    with Server(d) as s:
        yield s


def _gradient_statement(srv):
    st, j = srv.json(f"/api/readout?arm={ARM}&specimen={SPEC}")
    assert st == 200, j
    hits = [x for x in j["specimen"] if "patch" in x["text"]]
    assert hits, ("the seeded gradient produced no statement, so this file is measuring "
                  f"nothing: {[x['text'] for x in j['specimen']]}")
    return hits[0]


def test_the_retracted_remedy_never_reaches_the_reader(srv):
    """The record asserts "more patches would". The screen must not."""
    s = _gradient_statement(srv)
    blob = f"{s['text']} {s['basis']} {s.get('hedge') or ''}"
    assert "more patches would" not in blob, (
        "the readout printed the withdrawn remedy straight out of the record:\n" + blob)


def test_the_live_caveat_is_the_one_that_is_printed(srv):
    """Not just "the old text is gone" -- the current text has to be there instead, or a
    silent empty note would pass the test above."""
    import stage
    s = _gradient_statement(srv)
    assert stage.GRADIENT_NOTE in s["basis"], (
        "the gradient caveat is missing or is not the module's:\n" + s["basis"])
    assert "UNTESTED here" in s["basis"], s["basis"]


def test_the_measured_parts_still_come_from_the_record(srv):
    """Sourcing the NOTE from the module must not also overwrite the numbers. rho, p and
    the ratio are per-specimen measurements and have to stay the record's."""
    s = _gradient_statement(srv)
    assert "+0.867" in s["basis"] and "0.00249" in s["basis"], s["basis"]
    assert "9 fields" in s["basis"], s["basis"]
    assert s["text"].startswith("Cracking varies 8"), s["text"]


def test_the_refusal_to_rank_names_no_screen_furniture(srv):
    """The arm-level ranking refusal used to end "The table below is in name order for that
    reason." That table was removed from app.js, and /api/specimens returns neither name
    order nor any order on two of the four arms. A basis that describes a deleted widget
    is a claim about the UI that the UI does not keep."""
    st, j = srv.json(f"/api/readout?arm={ARM}")
    assert st == 200, j
    # THE REFUSAL MUST ACTUALLY FIRE, or the loop below is vacuous. It needs more than one
    # real specimen in the arm, which is why the fixture seeds two: with one, `len(real) > 1`
    # is False, no statement is emitted, and a `not in` over an empty list passes anything.
    rank = [x for x in (j.get("arm_statements") or [])
            if "cannot be ordered" in x["text"]]
    assert rank, ("the ranking refusal did not fire, so this test measures nothing: "
                  f"{[x['text'] for x in j.get('arm_statements') or []]}")
    for x in rank:
        assert "table below" not in x["basis"], (
            "the ranking refusal still points at the removed specimens table: "
            + x["basis"])
