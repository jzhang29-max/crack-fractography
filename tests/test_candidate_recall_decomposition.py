"""The candidate-stage recall decomposition, and the two levers that deliberately do NOT
ship from it.

Why these exist. The 70.13% of hand-painted crack the candidate stage never proposes was
decomposed at frame scale and turned out to be 96.02% the darkness cut and 4% everything
else. That pointed at two additive changes -- raising `absolute_dark_thresh` above 10, and
taking the robust cut on the unclipped float residual -- and NEITHER ships: the first
cannot be priced (the paint has no precision headroom and the tiles cannot contain the wide
cracks it is for), and the second is worth +0.14 points and in raw form deletes 444,839 px
of hand-painted crack. Both are exactly the kind of plausible-looking change that gets
re-proposed once the reasoning behind the refusal is out of the room, so the refusal and
its evidence are pinned here.

Every test below was sabotaged to confirm it fails: flipping the flag, deleting an evidence
figure, removing the additivity guard, and inverting the partition assertion.
"""
import ast
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "analysis"))
DO_SRC = os.path.join(HERE, "analysis", "detector_overrides.py")
RESEARCH = os.path.join(HERE, "analysis", "research", "improve")
DECOMP = os.path.join(RESEARCH, "fullframe_recall_decomposition.py")
RECOVERY = os.path.join(RESEARCH, "fullframe_recall_recovery.py")
TILES = os.path.join(RESEARCH, "absdark_tiles.py")


SEM_CODE = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code"


def _src(p):
    return open(p, encoding="utf-8").read()


def _detector_importable():
    """detect_cracks imports pandas, which lives in the DETECTOR's venv and not this app's
    -- the same separation test_detector_overrides.py works around, and the reason
    detect_one.py runs as a subprocess at all."""
    if not os.path.isdir(SEM_CODE):
        return False
    import importlib.util
    return importlib.util.find_spec("pandas") is not None


# --------------------------------------------------------- nothing changed in what ships
def test_this_work_changed_no_shipped_constant():
    """The whole point: a 100-line measurement record and zero behaviour change. A future
    edit that quietly ships the absolute-threshold lever has to break this."""
    import detector_overrides as DO

    assert DO.USE_REGION_CLASSIFIER is False
    assert DO.USE_MULTISCALE_UNION is True
    assert DO.SCALE_LADDER == (5, 10, 20, 40, 80, 160, 320)
    assert DO.DECIMATE_ABOVE_SIGMA == 64
    assert DO.OVERRIDES == {}, (
        "OVERRIDES is no longer empty. If absolute_dark_thresh or mad_k is being shipped, "
        "it needs the precision evidence the record in detector_overrides.py says does not "
        "exist -- certified NOT-crack at frame scale, not a tile IoU and not the paint.")
    assert "absolute_dark_thresh" not in DO.OVERRIDES


@pytest.mark.skipif(not _detector_importable(),
                    reason="the detector and its venv are not both available here")
def test_the_absolute_threshold_is_overridable_so_the_record_is_actionable():
    """Functional, not structural. The record says raising absolute_dark_thresh recovers
    10.6-13.5 points of painted-crack coverage but cannot be priced; that is only a real
    option if the override route actually carries the constant to the callee. Checked by
    driving install()'s own multiscale closure and reading back which pixels it calls dark,
    so a refactor that drops the kwarg fails here rather than silently reverting to 10."""
    import numpy as np
    import detector_overrides as DO

    class FakeUP:
        pass

    # A RAMPED background, not a flat one. On a flat background a 15-level block is a
    # 5-MAD outlier and the RELATIVE cut catches it too, so the fixture would pass whether
    # or not the kwarg arrived. Here the 15-level block sits where the local background is
    # ~20, so it is invisible to the relative cut at every radius and only the absolute
    # term can reach it.
    rng = np.random.default_rng(0)
    h = w = 128
    ramp = np.linspace(18, 240, w)[None, :].repeat(h, 0)
    img8 = (ramp + rng.normal(0, 3, (h, w))).clip(0, 255).astype(np.uint8)
    img8[50:60, 2:12] = 15        # dark, above the shipped 10, no local contrast
    img8[50:60, 60:70] = 4        # unambiguously below the shipped 10

    sys.path.insert(0, SEM_CODE)
    import detect_cracks as dc
    flat = dc.flatten_background(img8)

    up = FakeUP()
    DO.install(up)                                    # shipped: absolute 10
    shipped = up.segment_dark_regions(flat, img8=img8)
    up2 = FakeUP()
    DO.install(up2, absolute_dark_thresh=20)          # the lever, if ever taken
    raised = up2.segment_dark_regions(flat, img8=img8)

    assert shipped[55, 65], "the fixture does not exercise the absolute term at all"
    assert not shipped[55, 6], \
        "the 15-level block is already dark at the shipped setting; the fixture cannot " \
        "distinguish the kwarg arriving from the relative cut firing"
    assert raised[55, 6], "absolute_dark_thresh did not reach the callee"
    extra = raised & ~shipped
    assert extra.any()
    assert int((shipped & ~raised).sum()) == 0, "raising the threshold must only ever add"
    assert img8[extra].min() >= 10 and img8[extra].max() < 20, \
        "the added pixels are not exactly the ones the new threshold admits"


# --------------------------------------------------------------------- the evidence is on record
@pytest.mark.parametrize("ev", [
    "96.02%",        # share of the loss that is the darkness cut
    "47,165,748",    # px never dark at any ladder radius
    "10,516,306",    # painted crack reached by img8 < 10 and no ladder rung
    "22.4 px of false positive",   # the tile cost of raising it
    "3.53x",         # the budget-matched random control on that cost
    "13 of 13 folds",              # leave-one-specimen-out picks the shipped value
    "444,839",       # painted crack the raw float-residual arm deletes
    "56 of 336",     # frame-rungs whose robust bar is unreachable
    "19.72%",        # lower bound on the never-proposed paint that is darker than matrix
    "192 px",        # median painted stroke width, the broad-brush caveat
])
def test_every_refusal_carries_its_measurement(ev):
    """A constant left unchanged with no recorded measurement is indistinguishable from
    never having been examined, which is how a dead lever gets re-proposed."""
    assert ev in _src(DO_SRC), f"{ev!r} (evidence for a refusal) is not recorded"


def test_the_pooled_figure_is_not_quoted_without_its_unit_set():
    """Two frames hold 45.97% of the loss. The record must say so next to the pooled
    number, or the pooled number is one frame."""
    s = _src(DO_SRC)
    assert "45.97% of the loss" in s
    assert "pooled alone" in s or "quoted pooled" in s


def test_the_broadbrush_bound_records_that_its_first_form_was_wrong():
    """The mixture bound first read 88.16% because it was maximised over the threshold; its
    own control read 96.22% where it must read ~0. A record that keeps only the corrected
    number teaches nobody why the control is mandatory."""
    s = _src(DO_SRC)
    assert "88.16%" in s and "96.22%" in s, \
        "the corrected bound is recorded without the error it corrects"


# ------------------------------------------------------- the instruments keep their guards
def test_the_decomposition_asserts_its_partition_closes():
    """Five buckets that do not sum to the painted crack are five numbers about nothing.
    Parsed with ast, not grepped: the words appear in the docstring too."""
    tree = ast.parse(_src(DECOMP))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_control_partition"), None)
    assert fn is not None, "the partition control is gone"
    assert any(isinstance(n, ast.Assert) for n in ast.walk(fn)), \
        "_control_partition no longer asserts anything"
    called = {ast.unparse(n.func) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_control_partition" in called, "the partition control is never called"


def test_the_recovery_instrument_still_guards_additivity():
    """This guard is what caught the float-residual arm deleting 444,839 px of hand-painted
    crack on the first MAR frame. Without it that arm reads as a free superset."""
    src = _src(RECOVERY)
    tree = ast.parse(src)
    assert "SUPERSETS" in {t.id for n in ast.walk(tree)
                           if isinstance(n, ast.Assign) for t in n.targets
                           if isinstance(t, ast.Name)}, "SUPERSETS is gone"
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "score")
    # the guard is two statements: `bad = [arm for arm in SUPERSETS if ...deletes_vs_ship]`
    # and `assert not bad`. Both must survive -- an assert alone over an empty list passes
    # vacuously, which is how `a-read-with-no-writer` happens.
    built = [ast.unparse(n) for n in ast.walk(fn) if isinstance(n, ast.Assign)]
    bad_src = [b for b in built if "deletes_vs_ship" in b and "SUPERSETS" in b]
    assert bad_src, "score() no longer computes which superset arms deleted something"
    asserts = [ast.unparse(n) for n in ast.walk(fn) if isinstance(n, ast.Assert)]
    assert any("bad" in a for a in asserts), \
        "the deletion list is computed but never asserted on"


def test_the_tile_instrument_reproduces_the_shipped_score_before_quoting_a_delta():
    """An arm whose baseline does not reproduce 0.3344 is not comparable to anything on
    record -- and this control did fail first, against the stale v1.48 figure 0.2979."""
    s = _src(TILES)
    assert "0.3344" in s, "the tile instrument does not pin the shipped v1.49 score"
    assert "0.2979" in s, "the stale reference this control first failed against is not noted"
    tree = ast.parse(s)
    assert any("0.3344" in ast.unparse(n) for n in ast.walk(tree)
               if isinstance(n, ast.Compare)), \
        "0.3344 appears only in prose; the control no longer compares against it"


def test_the_research_scripts_stay_out_of_the_shipped_bundle():
    """analysis/*.py is bundled file-by-file into the app. These three read the paint corpus
    by absolute path, which the build's own guard rejects in a shipped file, so they must
    live under analysis/research/."""
    for p in (DECOMP, RECOVERY, TILES):
        assert os.path.join("analysis", "research") in p
        assert os.path.exists(p)
    top = os.path.join(HERE, "analysis")
    for f in os.listdir(top):
        if f.endswith(".py"):
            assert "recall_decomposition" not in f and "recall_recovery" not in f \
                and "absdark" not in f, f"{f} is in the bundled layer"
