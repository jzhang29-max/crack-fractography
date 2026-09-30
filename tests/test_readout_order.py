#!/usr/bin/env python3
"""The read-out leads with findings, not with caveats.

WHY THIS TEST EXISTS. The list used to sort severity-first and cap at five. A frame
typically carries two or three findings and six or seven caveats, so severity-first filled
the whole cap with caveats and pushed every finding into a collapsed "5 more" button. The
pane therefore displayed five failures and hid the conclusions -- and a user looking at it
said the conclusions were all inconclusive. They were reading the screen correctly. It was
not a wording problem or a statistics problem; it was an ordering bug with a truncation
behind it, and nothing in the suite could see it because nothing ran the renderer.

RUN IN NODE, NOT ASSERTED ON SOURCE TEXT. This repo already learnt that a test which greps
a function for a string passes while the function misbehaves. So roRender is executed with
a realistic mix of statements and the resulting markup is inspected.
"""
import json
import os
import shutil
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPJS = os.path.join(REPO, "app", "static", "app.js")

#: 2 findings among 9 statements -- the ratio that made the old ordering hide everything
#: useful. The order here is deliberately caveats-first, so a renderer that merely
#: preserves input order cannot pass.
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


def esc(v):
    """The same escaping app.js applies. Written out because a test that normalises only
    &amp; silently fails on any statement containing an apostrophe -- "E562's" became
    "E562&#39;s" and two assertions failed against correct markup."""
    for ch, ent in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"),
                    ('"', "&quot;"), ("'", "&#39;")):
        v = v.replace(ch, ent)
    return v


def render(groups):
    """Execute the real roRender() from app.js in node and return its markup."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = open(APPJS).read()
    # Take the file's own esc(), MARK, SEV and roRender rather than restating them here: a
    # copy of the renderer in the test would let the shipped one drift away from it.
    start = src.index("const MARK = {")
    end = src.index("let RO = {};")
    harness = (
        "const esc = (v) => String(v ?? '').replace(/[&<>\"']/g, (ch) =>"
        "({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[ch]));\n"
        + src[start:end]
        + "\nprocess.stdout.write(roRender(" + json.dumps(groups) + "));\n")
    out = subprocess.run([node, "-e", harness], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout


def visible_region(html):
    """The markup a reader sees without opening anything.

    NOT `html.partition("<details")[0]`. That was the first version and it was vacuous
    against the exact renderer it was written to catch: the old one emitted no <details> at
    all, so partition returned the WHOLE document as the "visible" part and every finding
    was trivially found in it -- including the ones the old renderer had shipped with a
    [hidden] attribute behind a "4 more" button. The test passed on the broken code.

    So visibility is computed from what actually hides a line: everything from the first
    <details onwards, and any element carrying [hidden].
    """
    visible = html.partition("<details")[0]
    # Drop hidden lines individually -- a [hidden] div before any <details> is still hidden.
    out, i = [], 0
    while True:
        j = visible.find('<div class="ro-line', i)
        if j < 0:
            out.append(visible[i:])
            break
        k = visible.find("</div>", j)
        k = len(visible) if k < 0 else k + len("</div>")
        chunk = visible[j:k]
        out.append(visible[i:j])
        if " hidden" not in chunk.split(">")[0]:
            out.append(chunk)
        i = k
    return "".join(out)


def test_every_finding_is_shown_open():
    html = render(STATEMENTS)
    shown = visible_region(html)
    goods = [s for g in STATEMENTS.values() for s in g if s["level"] == "good"]
    assert goods, "the fixture must contain findings or this test proves nothing"
    for st in goods:
        frag = esc(st["text"])
        assert frag in html, f"finding vanished from the markup: {st['text']}"
        assert frag in shown, (
            f"finding is not visible without opening something: {st['text']}. This is the "
            "regression: findings must not be behind a disclosure or a [hidden] attribute.")


def test_a_frame_with_no_findings_says_so_in_one_line():
    """The honest case. Leaving the reader to infer 'nothing established' from a list of
    caveats is how the pane read before, and inference is not a conclusion."""
    html = render({"frame": [s for s in STATEMENTS["frame"] if s["level"] != "good"]})
    assert "Nothing is established for this frame yet." in html
    head, _, _ = html.partition("<details")
    assert "Nothing is established" in head, "the statement itself must not be collapsed"


def test_statement_text_is_escaped():
    """Statement text interpolates frame names, and frame names come from uploaded
    filenames. armStatements() escaped and this renderer did not."""
    html = render({"frame": [{"level": "good", "text": "<img onerror=x> & co"}]})
    assert "<img" not in html and "&lt;img" in html and "&amp; co" in html


# --- THE CAVEATS MOVED OFF THE SURFACE, AND MUST NOT HAVE BEEN LOST ---------------------
def render_limits(groups):
    """Execute the real currentLimits() from app.js against an RO object."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = open(APPJS).read()
    sev = src[src.index("const SEV = {"):src.index("\n", src.index("const SEV = {"))]
    fn = src[src.index("function currentLimits()"):src.index("function syncLimitsButton()")]
    harness = (sev + "\nlet RO = " + json.dumps(groups) + ";\n" + fn
               + "\nprocess.stdout.write(JSON.stringify(currentLimits()));\n")
    out = subprocess.run([node, "-e", harness], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_no_caveat_is_rendered_on_the_reading_surface():
    """Fourteen caveats stacked under four findings, and the user asked twice for them
    gone. The surface is findings only now."""
    html = render(STATEMENTS)
    for st in (s for g in STATEMENTS.values() for s in g if s["level"] != "good"):
        assert esc(st["text"]) not in html, (
            f"caveat is still on the reading surface: {st['text']}")
    assert "<details" not in html, "no disclosure either -- the surface is findings only"


def test_every_caveat_is_still_reachable_and_none_was_dropped():
    """THE TEST THAT MATTERS. Moving the caveats off the surface must not quietly become
    deleting them. Three were audited against "what wrong number could a reader publish if
    this appeared nowhere" and all three came back load-bearing -- including the two that
    looked most like noise: "Corrections change area 1.003x" is the same template that
    prints 2.446x for MAR_Amb_AS on 6 of its 11 frames.

    So the set the drawer offers must be exactly the set the engine produced: nothing lost
    in the move, and nothing gained either, since a finding must not be filed as a caveat."""
    ro = {**STATEMENTS, "arm": [
        {"level": "bad", "text": "0 of 9 specimens reach E562's target."},
        {"level": "good", "text": "The detector changes crack LENGTH, not width."},
    ]}
    got = render_limits(ro)
    expected = {s["text"] for g in ro.values() for s in g if s["level"] != "good"}
    assert {x["st"]["text"] for x in got} == expected, "the drawer's set != the engine's set"
    findings = {s["text"] for g in ro.values() for s in g if s["level"] == "good"}
    assert not ({x["st"]["text"] for x in got} & findings), "a finding was filed as a caveat"


def test_the_drawer_includes_arm_level_caveats():
    """RO.arm is assigned AFTER RO.specimen and RO.frame in renderReadout. Counting one line
    too early would silently exclude every arm-level caveat, and the button would show a
    smaller number than the drawer lists -- a discrepancy nothing else would catch."""
    got = render_limits({"arm": [{"level": "warn", "text": "62 of 142 frames have no scale."}],
                         "frame": [{"level": "bad", "text": "Length unreliable."}]})
    assert {x["scope"] for x in got} == {"arm", "frame"}


def test_the_caveats_are_ordered_worst_first_in_the_drawer():
    got = render_limits(STATEMENTS)
    order = [x["st"]["level"] for x in got]
    rank = {"bad": 0, "warn": 1, "info": 3}
    assert order == sorted(order, key=lambda L: rank[L]), order


def test_the_drawer_heading_names_its_mode():
    """One drawer, two modes. It read "Definitions" above a list of fourteen caveats."""
    src = open(APPJS).read()
    lim = src[src.index("function openLimits()"):src.index("function openDefs(")]
    dfs = src[src.index("function openDefs("):src.index("const DEFS = [")]
    assert "defstitle" in lim, "limits mode does not set the heading"
    assert "defstitle" in dfs, "definitions mode does not restore the heading"
    assert "do not cover" in lim
