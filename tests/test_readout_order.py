#!/usr/bin/env python3
"""Where the app's statements live, and the rule that none of them may be lost.

THE HISTORY, because it is the reason these assertions are shaped the way they are.

1. The statements were rendered on the Results page, sorted severity-first and capped at
   five. A frame carries two or three findings and six or seven caveats, so the cap filled
   entirely with caveats and every finding was pushed into a collapsed "5 more" button --
   the page displayed five failures and hid each conclusion it had computed. A user read
   that screen and said the conclusions were all inconclusive. They were reading it
   correctly.
2. Findings then led the page and the caveats moved to a header drawer.
3. The findings followed them. Seven green-dotted sentences above the figure were, in a
   user's words, not something they could see the point of.

So the page carries the figure and the numbers; the drawer carries every statement,
findings first, each with the basis and the hedge that make it checkable. What must never
happen again is a statement that the engine produced and the interface cannot show, which
is what every test here is about.
"""
import json
import os
import shutil
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPJS = os.path.join(REPO, "app", "static", "app.js")

#: 2 findings among 9, the ratio that made the old ordering hide everything useful, and
#: deliberately caveats-first so that merely preserving input order cannot pass.
STATEMENTS = {
    "specimen": [
        {"level": "bad", "text": "+-31%: wider than E562's +-10% precision target."},
        {"level": "warn", "text": "Ranking specimens is not supported by this design."},
        {"level": "warn", "text": "Detector effect unmeasured here."},
        {"level": "good", "text": "Cracking rises toward one edge of the raster."},
        {"level": "info", "text": "One imaged site per specimen."},
    ],
    "frame": [
        {"level": "bad", "text": "Length unreliable: two estimators differ 1.9x."},
        {"level": "warn", "text": "Not resolvably oriented."},
        {"level": "good", "text": "Crack area survives a 6x coarser pixel."},
        {"level": "info", "text": "No scale; um withheld."},
    ],
}


def _eval(ro, call):
    """Run the real statement selectors from app.js against an RO object."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = open(APPJS, encoding="utf-8").read()
    sev = src[src.index("const SEV = {"):src.index("\n", src.index("const SEV = {"))]
    fns = src[src.index("function currentStatements("):src.index("function syncLimitsButton(")]
    harness = (sev + "\nlet RO = " + json.dumps(ro) + ";\n" + fns
               + f"\nprocess.stdout.write(JSON.stringify({call}));\n")
    out = subprocess.run([node, "-e", harness], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def findings(ro):
    return _eval(ro, "currentFindings()")


def limits(ro):
    return _eval(ro, "currentLimits()")


def test_no_statement_is_rendered_on_the_results_page():
    """The page is the figure and the numbers. Both statement sections are gone from the
    template, and the renderers that filled them are gone from the script -- a container
    left behind would be an empty section, and a renderer left behind would be a write to
    an element that does not exist."""
    import re
    raw = open(os.path.join(REPO, "app", "templates", "index.html"), encoding="utf-8").read()
    # STRIP THE COMMENTS. The comment explaining why these sections were removed quotes
    # their heading, so a raw scan matched the explanation and failed on a correct file --
    # the fifth time in this project a source scan has matched its own prose.
    html = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    src = open(APPJS, encoding="utf-8").read()
    for gone in ('id="armro"', 'id="readout"', "What this arm establishes"):
        assert gone not in html, f"{gone!r} survives in the page"
    code = "\n".join(L for L in src.split("\n") if not L.strip().startswith("//"))
    for gone in ("function roRender(", "function armStatements(", "$(\"#armro\")"):
        assert gone not in code, f"{gone!r} survives in the script"


def test_every_statement_the_engine_produced_is_reachable():
    """THE RULE. Moving statements off the page must not quietly become dropping them.
    Findings and limits together must equal exactly what the engine emitted -- nothing
    lost, and nothing miscategorised in either direction."""
    ro = {**STATEMENTS, "arm": [
        {"level": "bad", "text": "0 of 9 specimens reach E562's target."},
        {"level": "bad", "text": "CBS carries 1.8x to 6.0x ETD's crack centreline."},
    ]}
    got = {x["st"]["text"] for x in findings(ro)} | {x["st"]["text"] for x in limits(ro)}
    expected = {s["text"] for g in ro.values() for s in g}
    assert got == expected, f"lost: {expected - got} | invented: {got - expected}"


def test_findings_and_limits_are_split_by_level_not_by_scope():
    ro = {**STATEMENTS}
    f = {x["st"]["text"] for x in findings(ro)}
    L = {x["st"]["text"] for x in limits(ro)}
    assert not (f & L), "a statement appears in both sections"
    for g in ro.values():
        for s in g:
            if s["level"] == "good":
                assert s["text"] in f, f"a finding was filed as a limit: {s['text']}"
            else:
                assert s["text"] in L, f"a limit was filed as a finding: {s['text']}"


def test_arm_level_statements_are_included():
    """RO.arm is assigned AFTER RO.specimen and RO.frame in renderReadout. Counting one
    line too early silently excluded every arm-level statement."""
    got = limits({"arm": [{"level": "warn", "text": "62 of 142 frames have no scale."}],
                  "frame": [{"level": "bad", "text": "Length unreliable."}]})
    assert {x["scope"] for x in got} == {"arm", "frame"}


def test_the_limits_are_ordered_worst_first():
    order = [x["st"]["level"] for x in limits(STATEMENTS)]
    rank = {"bad": 0, "warn": 1, "info": 3}
    assert order == sorted(order, key=lambda L: rank[L]), order


def test_the_drawer_leads_with_findings_and_names_its_scopes():
    src = open(APPJS, encoding="utf-8").read()
    fn = src[src.index("function openLimits()"):src.index("function openDefs(")]
    assert fn.index("currentFindings()") < fn.index("currentLimits()")
    assert fn.index('section("Established"') < fn.index("limits.filter"), (
        "the limits are rendered before the findings")
    assert "state.arm" in fn and "state.spec" in fn and "state.frame" in fn, (
        "the drawer does not name which arm, specimen and frame it is describing")


def test_the_button_counts_findings_and_titles_both():
    """The count is what a reader decides to open the drawer for."""
    src = open(APPJS, encoding="utf-8").read()
    fn = src[src.index("function syncLimitsButton()"):src.index("function openLimits(")]
    assert "currentFindings()" in fn and "currentLimits()" in fn
    assert "plural(" in fn, "the tooltip would read '1 findings'"


def test_the_strip_still_leads_with_the_worst_statement():
    """A reader who never opens the drawer must not be able to miss a caveat. This is the
    one place the severity ordering is still right, because there is room for one line."""
    src = open(APPJS, encoding="utf-8").read()
    i = src.index("RO_TOP = all.length")
    ctx = src[max(0, i - 400):i]
    assert "SEV[a.level]" in ctx, "the strip no longer sorts by severity"
