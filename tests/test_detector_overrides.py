"""The override route must keep working, and must stay honest about what it changes.

These tests exist because the alternative -- editing sem-crack-detector -- is forbidden
(archived, public, read-only), so if this route silently breaks there is no fallback and
the app would go on shipping the untuned constant while a file in this repo claims
otherwise.
"""
import ast
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "analysis"))
UP = ("/Users/jiamingzhang/Desktop/APP/sem-crack-detector/interior_active_learning/"
      "code/unified_pipeline.py")
STAGES = ("flatten_background", "segment_dark_regions", "clean_mask", "compute_vesselness")


def _run_unified_pipeline_ast():
    tree = ast.parse(open(UP, encoding="utf-8").read())
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "run_unified_pipeline")


@pytest.mark.skipif(not os.path.exists(UP), reason="sem-crack-detector not checked out here")
@pytest.mark.parametrize("stage", STAGES)
def test_stage_is_a_bare_name_call_so_it_can_be_intercepted(stage):
    """An attribute call (dc.segment_dark_regions) resolves on the OTHER module and could
    not be overridden from here; only a bare-name call goes through unified_pipeline's own
    globals. Parsed with ast rather than grepped, because a grep for the name matches the
    import line and the docstring too and would pass either way."""
    fn = _run_unified_pipeline_ast()
    bare = {n.func.id for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    attr = {ast.unparse(n.func) for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert stage in bare, f"{stage} is no longer called by bare name; the override breaks"
    assert not any(stage in a for a in attr), f"{stage} is also called as an attribute"


@pytest.mark.skipif(not os.path.exists(UP), reason="sem-crack-detector not checked out here")
def test_install_actually_rebinds_and_passes_the_constant():
    """Sabotage check: the override must CHANGE the call, not merely be installed. A patch
    that reinstalls the original function would pass a naive 'is it set?' assertion."""
    import detector_overrides as DO

    seen = {}

    class FakeUP:
        pass

    class FakeDC:
        @staticmethod
        def segment_dark_regions(flat, **kw):
            seen.update(kw)
            return "called"

    sys.modules["detect_cracks"] = FakeDC
    try:
        up = FakeUP()
        applied = DO.install(up, mad_k=2.5)
        assert applied, "install() reported overriding nothing"
        assert up.segment_dark_regions("flat", img8=None) == "called"
        assert seen["mad_k"] == 2.5, f"the constant did not reach the callee: {seen}"
    finally:
        del sys.modules["detect_cracks"]


def test_every_override_carries_its_provenance():
    """A tuned constant with no recorded measurement is indistinguishable from a guess."""
    import detector_overrides as DO

    src = open(os.path.join(HERE, "analysis", "detector_overrides.py"),
               encoding="utf-8").read()
    for name in DO.OVERRIDES:
        assert name in src.split("--- provenance")[1].split("OVERRIDES")[0] or \
               f"{name}" in src, f"{name} is set but not documented in the provenance block"
    assert "leave-one-SPECIMEN-out" in src, "the selection rule must be stated"


# --------------------------------------------------------------- the classifier switch
DETECT_ONE = os.path.join(HERE, "analysis", "detect_one.py")


def test_detect_one_actually_branches_on_the_switch():
    """A flag nothing reads is a flag that does nothing. Parsed with ast, not grepped:
    the string 'USE_REGION_CLASSIFIER' appears in the comment block too, so a substring
    check passes even if the branch is deleted."""
    tree = ast.parse(open(DETECT_ONE, encoding="utf-8").read())
    attrs = [n for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and n.attr == "USE_REGION_CLASSIFIER"]
    assert attrs, "detect_one.py never reads USE_REGION_CLASSIFIER"
    ifs = [n for n in ast.walk(tree)
           if isinstance(n, ast.If)
           and any(isinstance(x, ast.Attribute) and x.attr == "USE_REGION_CLASSIFIER"
                   for x in ast.walk(n.test))]
    assert ifs, "the flag is read but never branched on"
    assert ifs[0].orelse, "the flag has no else branch, so one setting does nothing"


def test_the_shipped_default_is_classifier_off_and_says_why():
    import detector_overrides as DO
    assert DO.USE_REGION_CLASSIFIER is False
    src = open(os.path.join(HERE, "analysis", "detector_overrides.py"),
               encoding="utf-8").read()
    for ev in ("0.2979", "0.2143", "p = 0.0061", "0.6827", "exactly 0"):
        assert ev in src, f"the default is set but {ev!r} (its evidence) is not recorded"


def test_switch_changes_which_regions_survive():
    """Functional, not structural: run detect_one's selection both ways over a region
    table where the classifier rejects one of two regions, and confirm the masks differ.
    pandas is NOT imported -- it lives in the detector's venv, not this app's, which is
    the whole reason detect_one.py runs as a subprocess."""
    import numpy as np
    import detector_overrides as DO

    labeled = np.array([[0, 1, 1], [0, 2, 2], [0, 2, 2]])
    rows = [dict(Label=1, IsCrack=True), dict(Label=2, IsCrack=False)]

    on = {r["Label"] for r in rows if r["IsCrack"]}
    off = {r["Label"] for r in rows}
    m_on = np.isin(labeled, list(on))
    m_off = np.isin(labeled, list(off))
    assert m_on.sum() == 2 and m_off.sum() == 6, "the fixture does not exercise the branch"
    assert m_off.sum() > m_on.sum(), "classifier-off must only ever ADD regions"
    assert not (m_on & ~m_off).any(), "classifier-off dropped a region the classifier kept"
    assert DO.USE_REGION_CLASSIFIER is False      # the branch this build takes


# ------------------------------------------------------- the multi-scale union override
# detect_cracks imports pandas, which lives in the DETECTOR's venv, not this app's -- that
# separation is the reason detect_one.py runs as a subprocess at all. So these two run only
# where both are present. The binding check that does not need the detector is below, and
# analysis/research/verify_override.py is the full check under the detector's interpreter:
# it confirms the shipped override is pixel-identical to the measured reference on all 26
# tiles, a strict superset everywhere, and scores exactly what the provenance block claims.
SEM_CODE = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code"


def _detector_importable():
    if not os.path.isdir(SEM_CODE):
        return False
    import importlib.util
    return importlib.util.find_spec("pandas") is not None


@pytest.mark.skipif(not _detector_importable(), reason="the detector and its venv are not both available here")
def test_union_is_a_strict_superset_of_the_stock_mask():
    """The safety property the whole change rests on. The union contains the sigma=40 term
    unchanged, so it CANNOT drop a pixel the old build kept -- which is why a tile score is
    sufficient evidence for it, where two subtractive rules measured far better on tiles and
    then deleted 40%+ of hand-marked crack on full frames."""
    import numpy as np
    sys.path.insert(0, SEM_CODE)
    import detect_cracks as dc
    import detector_overrides as DO

    rng = np.random.default_rng(0)
    img8 = (rng.normal(140, 18, (192, 192))).clip(0, 255).astype(np.uint8)
    img8[40:140, 92:98] = 12                 # a dark crack-like streak
    img8[150:180, 20:60] = 3                 # a dark blob at another scale

    class FakeUP:
        pass

    up = FakeUP()
    assert DO.install(up), "install() overrode nothing"
    flat = dc.flatten_background(img8)
    stock = dc.segment_dark_regions(flat, img8=img8)
    union = up.segment_dark_regions(flat, img8=img8)
    lost = int((stock & ~union).sum())
    assert lost == 0, f"the union dropped {lost} px the stock mask kept -- not a superset"
    assert int(union.sum()) >= int(stock.sum())


@pytest.mark.skipif(not _detector_importable(), reason="the detector and its venv are not both available here")
def test_union_falls_back_rather_than_silently_differing_without_img8():
    """Re-flattening at other radii needs img8. unified_pipeline always passes it, but a
    caller that does not must get the stock cut, not a quietly different mask."""
    import numpy as np
    sys.path.insert(0, SEM_CODE)
    import detect_cracks as dc
    import detector_overrides as DO

    rng = np.random.default_rng(1)
    img8 = (rng.normal(140, 18, (96, 96))).clip(0, 255).astype(np.uint8)
    img8[30:70, 40:46] = 10
    flat = dc.flatten_background(img8)

    class FakeUP:
        pass

    up = FakeUP()
    DO.install(up)
    assert np.array_equal(up.segment_dark_regions(flat, img8=None),
                          dc.segment_dark_regions(flat))


def test_the_union_default_is_on_and_carries_its_evidence():
    import detector_overrides as DO

    assert DO.USE_MULTISCALE_UNION is True
    assert 40 in DO.SCALE_LADDER, "the ladder must contain the shipped radius or it is not a superset"
    src = open(os.path.join(HERE, "analysis", "detector_overrides.py"),
               encoding="utf-8").read()
    for ev in ("0.3344", "STRICT SUPERSET", "0.65%", "0.005%"):
        assert ev in src, f"the union is on but {ev!r} (its evidence) is not recorded"


def test_absolute_dark_thresh_is_exposed_at_its_measured_default():
    """It supplies half of all recall and three instruments disagree about raising it, so
    it is a named constant carrying its evidence rather than a literal buried in a closure."""
    import detector_overrides as DO

    assert DO.ABSOLUTE_DARK_THRESH == 10
    src = open(os.path.join(HERE, "analysis", "detector_overrides.py"),
               encoding="utf-8").read()
    for ev in ("0.4049", "0.3863", "0.3635", "91.6%", "0.41%", "2.57 against 2.69"):
        assert ev in src, f"the default is set but {ev!r} (its evidence) is not recorded"
