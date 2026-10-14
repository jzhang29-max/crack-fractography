#!/usr/bin/env python3
"""A downloaded app with nothing set in Setup must say so, not crash.

Two defects found by auditing rather than by a failing test, both reachable on the FIRST
RUN of a downloaded app with no sibling repositories:

  * app/server.py defined _mask_path TWICE at module level. The earlier copy raised
    HTTPException(503, "no SEM repo is configured...") when the tree was unset; the later
    one shadowed it and returned None, so the message was dead code and /api/mask did
    os.path.exists(None) -> TypeError -> 500.
  * every figure kind except "scatter" reads one field as `y or x`. With both omitted that
    is None, and FIELDS[None] raises KeyError -> 500, while an unknown field name is a
    clean 400. Same user error, two different answers.

These assert the contract, not the implementation: one definition, and a 4xx/503 rather
than a 500 for each.
"""
import ast
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tests"))
from liveserver import Server, mask_png  # noqa: E402


def _tree(name):
    return ast.parse(open(os.path.join(HERE, "app", name), encoding="utf-8").read())


def test_no_top_level_function_is_defined_twice():
    """A shadowed definition is dead code whose docstring still reads as the contract.
    ast, not grep: the name appears in calls and comments throughout the file."""
    names = [n.name for n in _tree("server.py").body if isinstance(n, ast.FunctionDef)]
    dup = sorted({n for n in names if names.count(n) > 1})
    assert not dup, f"shadowed top-level definitions in server.py: {dup}"


def test_mask_on_an_unconfigured_arm_is_503_not_500(tmp_path):
    """No SEM repo configured is the first-run state of a downloaded app."""
    with Server(tmp_path / "d") as s:
        st, raw = s.get("/api/mask/sem/gated/anything")
        assert st != 500, f"500 on an unconfigured arm: {raw[:200]}"
        assert st in (404, 503), f"expected 503 (or 404 if a tree exists), got {st}: {raw[:200]}"


def test_a_figure_with_no_field_is_400_not_500(tmp_path):
    """Omitting both x and y is the same class of user error as naming an unknown field,
    which already answers 400."""
    with Server(tmp_path / "d") as s:
        st, raw = s.upload("img.png", mask_png(160, 120, 30))
        assert st == 200, raw[:200]
        for path in ("/api/figure.svg?arm=uploads", "/api/figure/says?arm=uploads"):
            st, raw = s.get(path)
            assert st != 500, f"500 on {path}: {raw[:300]}"
            assert st == 400, f"expected 400 on {path}, got {st}: {raw[:200]}"
            assert b"field" in raw.lower(), f"{path} 400 does not say what is missing: {raw[:200]}"


def test_a_figure_with_a_field_still_works(tmp_path):
    """The guard must not have broken the normal case.

    kind=histogram, because the default box_by_specimen legitimately refuses a single
    uploaded image ("every specimen has fewer than 3 fields") -- a different and correct
    400 that would mask whether the field guard above is the one answering."""
    with Server(tmp_path / "d") as s:
        st, raw = s.upload("img.png", mask_png(160, 120, 30))
        assert st == 200, raw[:200]
        st, raw = s.get("/api/figure.svg?arm=uploads&kind=histogram&y=area_fraction")
        assert st == 200, f"a valid figure request broke: {st} {raw[:200]}"
        st, raw = s.get("/api/figure.svg?arm=uploads&kind=histogram")
        assert st == 400 and b"field" in raw.lower(), \
            f"the field guard stopped answering for histogram: {st} {raw[:200]}"
