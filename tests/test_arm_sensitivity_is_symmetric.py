#!/usr/bin/env python3
"""arm_sensitivity is a property of a PAIR of arms, stored in both arms' records.

`specimen_stats.paired_arm_ratio` compares the gated arm against the machine arm on
identical frames, so its answer does not depend on which of the two you are looking at.
It is written into both records, and `_rebuild_specimen` -- the writer the remeasure
endpoint calls after a correction -- rewrote only the arm whose frame changed. The
counterpart's copy then went on describing the pre-edit masks.

A field with a writer that nothing re-runs reads exactly like a correct one. Measured on
the shipped corpus: of the 28 paired specimen records, exactly ONE disagreed with the live
computation -- MAR_H_AS sem/machine held n_frames_corrected = 0 where a frame-by-frame
recount of frames.json and specimen_stats itself both say 1. What that put on screen:

    sem/gated  card: "Corrections change area 1.003x on 1 frames."
    sem/machine card: "Unreviewed: detector output, no operator corrections -- the gated
                       and machine arms are identical on all 20 frames of this specimen."
    arm read-outs:    "Operator corrections change 10 of 14 specimens."   (gated)
                      "Operator corrections change  9 of 14 specimens."   (machine)

Two cards and two read-outs disagreeing about whether a human ever touched one specimen.
"Unreviewed" is a provenance claim, so the wrong one is the costly direction.

These drive `_rebuild_specimen` itself -- the function the endpoint calls -- against a
seeded data directory, rather than asserting on its source text.
"""
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

SPEC = "PAIRED"


def _frames(gated_af):
    """Three frames in each arm. The machine arm is fixed; the gated arm's first frame is
    the one a 'correction' moves."""
    out = []
    for i, af in enumerate(gated_af):
        out.append({"frame": f"{SPEC}_{i:02d}_CBS", "arm": "sem/gated", "specimen": SPEC,
                    "area_fraction": af, "scale_known": False, "nm_per_px": None,
                    "crack_area_px": int(af * 10000), "n_cracks_measured": 2,
                    "largest_share_of_area": 0.5, "speck_count": 0,
                    "crack_density_px_per_Mpx": af * 1e6, "megapixels": 1.0})
        out.append({"frame": f"{SPEC}_{i:02d}_CBS", "arm": "sem/machine", "specimen": SPEC,
                    "area_fraction": 0.010, "scale_known": False, "nm_per_px": None,
                    "crack_area_px": 100, "n_cracks_measured": 2,
                    "largest_share_of_area": 0.5, "speck_count": 0,
                    "crack_density_px_per_Mpx": 10000.0, "megapixels": 1.0})
    return out


@pytest.fixture
def out(tmp_path, monkeypatch):
    """A private data dir, and the server module pointed at it.

    setattr, NOT setenv + importlib.reload. app.paths reads FRACTOGRAPHY_DATA once at its
    first import and app.server copies that value, so reloading app.server does NOT reload
    app.paths: the second test in a file got the FIRST test's directory, _rebuild_specimen
    found no frames.json there, returned early, and the records it was supposed to fix came
    back unchanged -- a test that passed alone and failed after any sibling. Same pattern
    as tests/test_dataset_reload.py's own fixture.
    """
    d = tmp_path / "data"
    d.mkdir()
    (d / "cracks.json").write_text("[]", encoding="utf-8")
    import app.server as S
    monkeypatch.setattr(S, "OUT", str(d))
    monkeypatch.setattr(S, "_CACHE", {})
    return d, S


def _write(d, S, frames):
    (d / "frames.json").write_text(json.dumps(frames), encoding="utf-8")
    # Both records, as a full corpus build would leave them.
    import specimen_stats
    by_arm = {}
    for f in frames:
        by_arm.setdefault(f["arm"], []).append(f)
    recs = []
    for arm in ("sem/gated", "sem/machine"):
        fs = [f for f in frames if f["arm"] == arm]
        r = specimen_stats.summarise(arm, SPEC, fs)
        pair = specimen_stats.pair_for(arm)
        r["arm_sensitivity"] = specimen_stats.paired_arm_ratio(by_arm, SPEC, *pair)
        recs.append(r)
    (d / "specimens.json").write_text(json.dumps(recs), encoding="utf-8")
    S._load.cache_clear() if hasattr(S._load, "cache_clear") else None
    return recs


def _sens(d):
    recs = json.loads((d / "specimens.json").read_text(encoding="utf-8"))
    return {r["arm"]: r.get("arm_sensitivity") for r in recs}


def test_correcting_one_arm_updates_the_counterpart_record(out):
    """The defect, driven: write both records with NO correction, then move a gated frame
    and rebuild only the gated arm. The machine record must stop saying "no corrections"."""
    d, S = out
    sys.path.insert(0, os.path.join(REPO, "analysis"))
    _write(d, S, _frames([0.010, 0.010, 0.010]))
    before = _sens(d)
    assert before["sem/gated"]["n_frames_corrected"] == 0, before
    assert before["sem/machine"]["n_frames_corrected"] == 0, before

    # A correction lands on one gated frame, exactly as remeasure would leave it.
    _write(d, S, _frames([0.013, 0.010, 0.010]))
    # ...except that remeasure rebuilds ONE arm, so undo the counterpart's refresh and let
    # the writer under test be the only thing that touches it.
    recs = json.loads((d / "specimens.json").read_text(encoding="utf-8"))
    for r in recs:
        if r["arm"] == "sem/machine":
            r["arm_sensitivity"]["n_frames_corrected"] = 0
            r["arm_sensitivity"]["gated_over_machine_where_corrected"] = None
    (d / "specimens.json").write_text(json.dumps(recs), encoding="utf-8")

    S._rebuild_specimen("sem/gated", SPEC)

    after = _sens(d)
    assert after["sem/gated"]["n_frames_corrected"] == 1, after["sem/gated"]
    assert after["sem/machine"]["n_frames_corrected"] == 1, (
        "the counterpart record still says the arms are identical after a gated frame "
        f"was corrected: {after['sem/machine']}")


def test_the_two_records_cannot_disagree(out):
    """The invariant, stated without reference to which arm was edited: the comparison is
    symmetric, so the two stored copies must be equal field for field."""
    d, S = out
    sys.path.insert(0, os.path.join(REPO, "analysis"))
    for arm in ("sem/gated", "sem/machine"):
        # RECORDS FOR THE OLD FRAMES, THEN NEW FRAMES AND ONE REBUILD. Writing both records
        # from the new frames first would leave nothing for the writer to fix and this test
        # would pass with the fix removed -- which it did, until the frames were staged
        # before the records instead of after.
        _write(d, S, _frames([0.010, 0.010, 0.010]))
        (d / "frames.json").write_text(json.dumps(_frames([0.013, 0.010, 0.022])),
                                       encoding="utf-8")
        assert _sens(d)["sem/machine"]["n_frames_corrected"] == 0, "fixture not stale"

        S._rebuild_specimen(arm, SPEC)

        s = _sens(d)
        assert s["sem/gated"] == s["sem/machine"], (
            f"after rebuilding {arm} the two copies differ:\n"
            f"  gated  : {s['sem/gated']}\n  machine: {s['sem/machine']}")
        # And it is not equal-because-both-stale.
        assert s["sem/gated"]["n_frames_corrected"] == 2, s["sem/gated"]


def test_rebuilding_an_unpaired_arm_touches_nothing_else(out):
    """uploads has no counterpart. pair_for returns None and the counterpart loop must not
    run -- an arm with no pair writing into some other arm's record is the failure this
    fix could have introduced."""
    d, S = out
    sys.path.insert(0, os.path.join(REPO, "analysis"))
    frames = _frames([0.013, 0.010, 0.010]) + [
        {"frame": "U_00", "arm": "uploads", "specimen": SPEC, "area_fraction": 0.05,
         "scale_known": False, "nm_per_px": None, "crack_area_px": 500,
         "n_cracks_measured": 1, "largest_share_of_area": 0.9, "speck_count": 0,
         "crack_density_px_per_Mpx": 50000.0, "megapixels": 1.0}]
    _write(d, S, frames)
    recs = json.loads((d / "specimens.json").read_text(encoding="utf-8"))
    import specimen_stats
    recs.append(specimen_stats.summarise("uploads", SPEC,
                                         [f for f in frames if f["arm"] == "uploads"]))
    recs[-1]["arm_sensitivity"] = None
    (d / "specimens.json").write_text(json.dumps(recs), encoding="utf-8")
    before = _sens(d)

    S._rebuild_specimen("uploads", SPEC)

    after = _sens(d)
    assert after["sem/gated"] == before["sem/gated"], (before, after)
    assert after["sem/machine"] == before["sem/machine"], (before, after)
    assert after["uploads"] is None, after["uploads"]
