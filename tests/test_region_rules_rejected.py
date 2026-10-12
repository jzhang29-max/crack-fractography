"""A third region-rejecting rule was tested against the paint and rejected. Keep it that way.

analysis/detector_overrides.py already warns that no region-level precision rule may be
reintroduced without re-running the full-frame safety test against the hand-painted
correction masks. Two rules died that way (texture veto, thickness excision). A third --
a region classifier retrained on the 26 hand-labelled tiles with 24 extra features,
scoring nested held-out tile IoU 0.5318 against the shipped 0.2979 -- died the same way,
and worse: it deletes 72.67% of the hand-marked crack the shipped path delivers, against
67.54% for the texture veto, on the same 48 frames through the same denominator.

These tests exist because that record is the only thing standing between the next tile
score and a change that would delete two thirds of the user's measured crack. A tile IoU
cannot rank a rule that rejects regions: the labelling crop is 512 px and a wide-open main
crack does not fit in one, so the training set contains no example of the object that
holds most of the crack area.
"""
import ast
import os

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH = os.path.join(HERE, "analysis", "research", "improve")
RECORD = os.path.join(RESEARCH, "fullframe_lever4_safety.py")


def _record_text():
    tree = ast.parse(open(RECORD, encoding="utf-8").read())
    return ast.get_docstring(tree) or ""


def test_the_rejection_is_recorded_with_the_numbers_that_decided_it():
    """A verdict with no numbers is a preference. Each of these is a measurement that
    would have to be re-done to overturn the decision, so each must survive in the file."""
    doc = _record_text()
    for ev in (
        "REJECTED",
        "72.67%",          # lever 4's deletion of kept hand-marked crack, mad_k=5.0
        "12,518,382",      # the crack pixels it deletes
        "70,041,625",      # the paint corpus it was measured against
        "67.54%",          # the texture veto, same frames, same denominator
        "62.43%",          # the thickness excision, likewise
        "143,252",         # the not-crack pixels it removes, i.e. what the damage bought
        "2.61-29.34",      # MeanWidth over the tile training positives
        "88.0%",           # share of deleted crack in regions wider than any of them
        "-0.0063",         # its tile gain at the SHIPPED mad_k, void tile removed
        "8.74%",           # the force-keep remedy, which also fails
    ):
        assert ev in doc, f"the rejection is recorded but {ev!r} (its evidence) is not"


def test_the_record_names_the_structural_reason_not_just_the_outcome():
    """Without the mechanism the next person re-runs the same experiment. The reason is
    that the tiles cannot contain the object, so no amount of tile score fixes it."""
    doc = _record_text()
    assert "512 px" in doc, "the record does not say what the tiles structurally cannot hold"
    assert "DISJOINT" in doc or "disjoint" in doc, "the training-support gap is not stated"


def test_the_full_frame_gate_is_runnable_and_reads_nothing_it_should_not_write():
    """The gate detector_overrides.py points at must exist, parse, and never open a file
    for writing under sem-crack-detector -- the correction masks are irreplaceable."""
    for f in ("fullframe_lever4_safety.py", "report_fullframe_lever4.py",
              "deadrules_same_frames.py", "lever4_width_extrapolation.py"):
        path = os.path.join(RESEARCH, f)
        assert os.path.exists(path), f"{f} is referenced as the gate but is missing"
        tree = ast.parse(open(path, encoding="utf-8").read())
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open":
                mode = ""
                if len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                    mode = str(n.args[1].value)
                mode += "".join(str(k.value.value) for k in n.keywords
                                if k.arg == "mode" and isinstance(k.value, ast.Constant))
                if "w" in mode or "a" in mode:
                    tgt = ast.unparse(n.args[0]) if n.args else ""
                    assert "sem-crack-detector" not in tgt and "PAINT" not in tgt, (
                        f"{f} opens {tgt} for writing; the paint is read-only")


def test_the_research_scripts_stay_out_of_the_shipped_bundle():
    """They carry absolute /Users paths, which the build's own guard forbids in a shipped
    file. The spec lists analysis/*.py file by file and does not recurse, so these are
    safe only as long as that stays true -- assert it rather than trust it."""
    spec = open(os.path.join(HERE, "packaging", "fractography.spec"), encoding="utf-8").read()
    tree = ast.parse(spec)
    listdirs = {ast.unparse(n) for n in ast.walk(tree)
                if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("listdir")}
    assert listdirs, "the spec no longer enumerates analysis/ at all; re-check this guard"
    assert not any("research" in d for d in listdirs), (
        "the spec now walks analysis/research, which would ship absolute paths")
    assert "walk" not in spec.split("analysis_files")[1].split("]")[0], (
        "analysis_files now recurses; research scripts would be bundled")


def test_a_rejecting_rule_cannot_be_called_safe_by_the_arm_that_keeps_everything():
    """The instrument's own control, as logic rather than as a printed line.

    The deletion counter compares a rule's mask against the mask that keeps every
    candidate. If it is wired up correctly then keeping everything must score exactly 0
    deletions and rejecting everything must score exactly the hand-marked crack inside the
    candidates -- otherwise a rule that deletes the main crack can report itself clean.
    """
    labeled = np.array([[1, 1, 1, 0], [1, 1, 1, 0], [0, 0, 0, 2], [0, 0, 0, 2]])
    corr = np.zeros_like(labeled)
    corr[:2, :3] = 1        # the human painted region 1 as CRACK
    corr[2:, 3] = 2         # and region 2 as NOT-crack
    ids = np.array([1, 2])
    crack, notc = corr == 1, corr == 2

    def kept_crack(sel):
        m = np.isin(labeled, ids[sel]) if sel.any() else np.zeros_like(labeled, bool)
        return int((m & crack).sum()), int((m & notc).sum())

    keepall_c, keepall_n = kept_crack(np.array([True, True]))
    assert (keepall_c, keepall_n) == (6, 2), "the fixture does not exercise both states"
    assert keepall_c - kept_crack(np.array([True, True]))[0] == 0, \
        "keep-everything reports a deletion against itself"
    assert keepall_c - kept_crack(np.array([False, False]))[0] == keepall_c, \
        "reject-everything does not report the full deletion; the counter is blind"
    # the shape of lever 4's failure: reject the big region, keep the small one
    rej_big_c, rej_big_n = kept_crack(np.array([False, True]))
    assert keepall_c - rej_big_c == 6 and keepall_n - rej_big_n == 0, (
        "rejecting the crack region must be counted as deleting crack and as buying "
        "no precision -- that asymmetry is exactly what disqualified lever 4")
