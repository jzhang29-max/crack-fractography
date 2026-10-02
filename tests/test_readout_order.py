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

2026-10-01, MUTATION AUDIT. Five guards in this file were proven worthless: the audit
broke the behaviour each one claims to protect and every one still passed. All five were
SOURCE SCANS -- they asserted that a token appears in a slice of app.js, which survives
any mutation that keeps the token and changes what the code does with it. The five
mutations that passed, and now fail:

  * syncLimitsButton() moved one line earlier, above `RO.arm = ARM_STATEMENTS` -- the
    exact regression test_arm_level_statements_are_included was written for.
  * the strip's comparator reversed to (SEV[b] - SEV[a]), so the banner leads with the
    LEAST severe statement. "SEV[a.level]" is still in the source.
  * the button's count switched from findings to limits. Both names are still in the
    function, because it computes both.
  * the drawer's sections concatenated limits-first into the body while leaving the
    source order of `section("Established"` and `limits.filter` untouched.
  * a statement list re-added to the Results page under a new id by a new renderer, which
    no blacklist of the three OLD names can see.

The repair is the same in every case: run the shipped functions under node against a
stubbed DOM and assert on what they WROTE, with counts hand-computed from a fixture whose
answer is fixed by its construction. The source-scan assertions that are cheap and still
true are kept, but nothing now rests on them alone.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPJS = os.path.join(REPO, "app", "static", "app.js")
INDEX = os.path.join(REPO, "app", "templates", "index.html")

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


def _node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return node


def _src():
    return open(APPJS, encoding="utf-8").read()


def _span(src, first, last):
    """The real source between two anchors. Nothing in here is re-implemented."""
    i, j = src.index(first), src.index(last)
    assert i < j, f"{first!r} no longer precedes {last!r} in app.js"
    return src[i:j]


def _line(src, anchor):
    i = src.index(anchor)
    return src[src.rindex("\n", 0, i) + 1:src.index("\n", i)]


def _node_json(js):
    out = subprocess.run([_node(), "-e", js], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _eval(ro, call):
    """Run the real statement selectors from app.js against an RO object."""
    src = _src()
    sev = _line(src, "const SEV = {")
    fns = _span(src, "function currentStatements(", "function syncLimitsButton(")
    harness = (sev + "\nlet RO = " + json.dumps(ro) + ";\n" + fns
               + f"\nprocess.stdout.write(JSON.stringify({call}));\n")
    return _node_json(harness)


def findings(ro):
    return _eval(ro, "currentFindings()")


def limits(ro):
    return _eval(ro, "currentLimits()")


# ---------------------------------------------------------------------------------------
# THE WHOLE READ-OUT PATH, DRIVEN. Five guards here used to scan app.js for a token; a
# token survives every mutation that keeps the name and changes the behaviour. This runs
# the shipped renderReadout -- which is where RO.arm is assigned and where
# syncLimitsButton is called from -- against a DOM stub that RECORDS EVERY WRITE, so the
# assertions can be about what a reader would see.
#
# Only the browser is stubbed. The statement machinery (renderReadout, currentStatements,
# currentFindings, currentLimits, syncLimitsButton, openLimits) and the formatting
# helpers that the assertions depend on (SEV, MARK, plural, esc) are the file's own text.
_STUBS = r"""
const DOM = {};
function mk(sel) {
  const o = { sel, writes: [], hidden: true, scrollTop: 0, dataset: {}, title: "",
              value: "", onclick: null, onkeydown: null,
              querySelectorAll: () => [] };
  let h = "", t = "";
  Object.defineProperty(o, "innerHTML",
    { get: () => h, set: (v) => { h = String(v); o.writes.push(String(v)); } });
  Object.defineProperty(o, "textContent",
    { get: () => t, set: (v) => { t = String(v); o.writes.push(String(v)); } });
  return o;
}
// Every selector resolves, and nothing is silently dropped: an element the code writes to
// is created on first touch and keeps its write log, so a statement rendered into ANY
// element -- including one this test has never heard of -- is visible afterwards.
const $ = (s) => DOM[s] || (DOM[s] = mk(s));
const document = { getElementById: (id) => DOM["#" + id] || null };
let ARM_STATEMENTS = [], RO = {}, RO_TOP = {};
// The real shortFrame truncates for the frames table; identity keeps the fixture's own
// frame name checkable by hand in the drawer's group headings.
const shortFrame = (name) => name;
const defsAll = () => "<!--definitions-->";
async function api(_path) { return PAYLOAD; }
"""

_DRIVER = r"""
(async () => {
  await renderReadout();
  // Snapshot BEFORE the drawer is opened, so #page is only ever what the Results page
  // itself received.
  const page = {};
  for (const k of Object.keys(DOM)) {
    page[k] = { html: DOM[k].innerHTML, text: DOM[k].textContent,
                writes: DOM[k].writes, title: DOM[k].title, none: DOM[k].dataset.none };
  }
  const res = { page, top: RO_TOP, ro: RO, drawer: null, drawerTitle: null };
  if (OPEN_DRAWER) {
    openLimits();
    res.drawer = DOM["#defsbody"].innerHTML;
    res.drawerTitle = DOM["#defstitle"].textContent;
  }
  process.stdout.write(JSON.stringify(res));
})();
"""


def render(payload, arm="sem/gated", spec="260622_316_H_b2",
           frame="260622_316_H_b2_front_CBS_01", open_drawer=False):
    """Run the shipped renderReadout over `payload` (an /api/readout body) and return
    {page: {selector: {html, text, writes, title, none}}, top: RO_TOP, ro: RO,
    drawer, drawerTitle}."""
    src = _src()
    st = {"arm": arm, "spec": spec, "frame": frame,
          "frames": [{"frame": frame, "scale_known": True}]}
    js = "\n".join([
        _line(src, "const SEV = {"),
        _line(src, "const MARK = {"),
        _line(src, "const plural = "),
        _span(src, "const esc = (v) =>", "const fmt = "),
        _STUBS,
        "const PAYLOAD = " + json.dumps(payload) + ";",
        "const OPEN_DRAWER = " + json.dumps(bool(open_drawer)) + ";",
        "let state = " + json.dumps(st) + ";",
        # renderReadout .. openLimits, verbatim.
        _span(src, "async function renderReadout()", "function openDefs("),
        _DRIVER,
    ])
    return _node_json(js)


#: Two findings and two limits, split across all three scopes so that dropping ANY scope
#: changes both counts. The counts below are hand-computed from this literal: the two
#: "good" statements are the findings, the "warn" and the "bad" are the limits.
ARM_FIXTURE = {
    "arm_statements": [
        {"level": "good", "text": "ARM FINDING: cracking rises toward one edge of the raster."},
        {"level": "warn", "text": "ARM LIMIT: 62 of 142 frames have no scale."},
    ],
    "specimen": [
        {"level": "good", "text": "SPECIMEN FINDING: crack area survives a 6x coarser pixel."},
    ],
    "frame": [
        {"level": "bad", "text": "FRAME LIMIT: length unreliable, two estimators differ 1.9x."},
    ],
}
ARM_FINDINGS = 2
ARM_LIMITS = 2


def test_no_statement_is_rendered_on_the_results_page():
    """The page is the figure and the numbers. Both statement sections are gone from the
    template, and the renderers that filled them are gone from the script.

    AUDIT. The old guard was a blacklist of three strings -- 'id="armro"', 'id="readout"',
    'function roRender('. A superset always contains it: re-adding the statement list to
    the Results page under a NEW id, written by a NEW function, passed untouched. The
    audit's mutation put every statement back into #frameacts as `.ro-line` paragraphs
    inside `<section id="pageconclusions">` and all eight tests stayed green.

    NOW. renderReadout is run with statements in all three scopes and every DOM write it
    makes is recorded; no element may receive any statement's text, under any id, from any
    function. Two positive controls keep that from being vacuously true: the pane must
    have received the re-measure control (the renderer ran), and all four statements must
    be in RO -- the object the page renderer reads -- when it ran, so there was something
    available to leak. The template and source scans are kept -- they are cheap and they
    are history -- but nothing rests on them now."""
    got = render(ARM_FIXTURE)

    # POSITIVE CONTROLS: the renderer ran, and it ran with the statements in front of it.
    assert "Re-measure this frame" in got["page"]["#frameacts"]["html"], (
        "renderReadout did not render the Results pane at all; the absence of statements "
        "below would prove nothing")
    for scope, key in (("arm", "arm_statements"), ("specimen", "specimen"), ("frame", "frame")):
        assert [s["text"] for s in got["ro"].get(scope, [])] == \
               [s["text"] for s in ARM_FIXTURE[key]], (
            f"RO.{scope} was not populated, so this fixture cannot show a leak")

    texts = [s["text"] for g in ARM_FIXTURE.values() for s in g]
    for sel, node in got["page"].items():
        blob = "\n".join(node["writes"])
        for t in texts:
            assert t not in blob, f"the statement {t!r} was rendered into {sel}"
        assert "ro-line" not in blob, f"a statement line was rendered into {sel}"

    raw = open(INDEX, encoding="utf-8").read()
    # STRIP THE COMMENTS. The comment explaining why these sections were removed quotes
    # their heading, so a raw scan matched the explanation and failed on a correct file --
    # the fifth time in this project a source scan has matched its own prose.
    html = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    src = _src()
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
    line too early silently excluded every arm-level statement.

    AUDIT. The old guard called currentLimits() against an RO object it had BUILT ITSELF,
    with .arm already in it, and asserted the scopes came back as {"arm", "frame"}. It
    never ran renderReadout, so the one regression it names -- syncLimitsButton() called
    before RO.arm exists -- could not reach it. The audit moved that call one line earlier
    and the guard passed.

    NOW. renderReadout is driven for real against a fixture with one finding and one limit
    at arm level, one finding at specimen level and one limit at frame level. The button
    must have been written 2 findings and 2 limits -- hand-counted from the literal above
    -- and the drawer must carry all four statements by name. With the call moved early
    the button reads 1 and 1; with "arm" dropped from the scope list it reads 1 and 2."""
    got = render(ARM_FIXTURE, open_drawer=True)
    assert got["page"]["#limitsn"]["text"] == str(ARM_FINDINGS)
    assert got["page"]["#limitsbtn"]["title"] == "2 findings, 2 limits", (
        "the count was written before RO.arm existed, or a scope is missing from it")
    for g in ARM_FIXTURE.values():
        for s in g:
            assert s["text"] in got["drawer"], f"unreachable in the drawer: {s['text']}"

    # The categorisation itself, unchanged from the original guard.
    scoped = limits({"arm": [{"level": "warn", "text": "62 of 142 frames have no scale."}],
                     "frame": [{"level": "bad", "text": "Length unreliable."}]})
    assert {x["scope"] for x in scoped} == {"arm", "frame"}


def test_the_limits_are_ordered_worst_first():
    order = [x["st"]["level"] for x in limits(STATEMENTS)]
    rank = {"bad": 0, "warn": 1, "info": 3}
    assert order == sorted(order, key=lambda L: rank[L]), order


def test_the_drawer_leads_with_findings_and_names_its_scopes():
    """FINDINGS FIRST, then what they do not cover, grouped by what it is about.

    AUDIT. The old guard compared source offsets inside openLimits: that
    `section("Established"` appears before `limits.filter`, and that the strings
    "state.arm", "state.spec", "state.frame" appear somewhere in the function. Source
    order is not render order. The audit built the limit sections into a second variable
    and wrote `body.innerHTML = lim + html` -- every token the guard looked for still in
    place, in the same order -- and the drawer led with the caveats again.

    NOW. openLimits is run and its OUTPUT is parsed: the group headings, in the order the
    reader meets them, must be Established first and then the three limit groups in arm,
    specimen, frame order, each one naming the fixture's actual arm, specimen and frame.
    The counts in the headings (3 findings, 1 limit per scope) are hand-computed from the
    fixture below, and every finding's text must physically precede every limit's text."""
    fixture = {
        "arm_statements": [
            {"level": "good", "text": "ARM FINDING: cracking rises toward one edge."},
            {"level": "bad", "text": "ARM LIMIT: 0 of 9 specimens reach the E562 target."},
        ],
        "specimen": [
            {"level": "good", "text": "SPECIMEN FINDING: area survives a 6x coarser pixel."},
            {"level": "warn", "text": "SPECIMEN LIMIT: one imaged site per specimen."},
        ],
        "frame": [
            {"level": "good", "text": "FRAME FINDING: two estimators agree within 4 percent."},
            {"level": "info", "text": "FRAME LIMIT: no scale, um withheld."},
        ],
    }
    arm, spec, frame = "sem/gated", "260622_316_H_b2", "260622_316_H_b2_front_CBS_01"
    got = render(fixture, arm=arm, spec=spec, frame=frame, open_drawer=True)

    groups = re.findall(r'<p class="limgrp">(.*?)</p>', got["drawer"])
    assert groups == [
        "Established &middot; 3",
        f"About the {arm} arm — limits &middot; 1",
        f"About {spec} — limits &middot; 1",
        f"About {frame} — limits &middot; 1",
    ], groups
    assert got["drawerTitle"] == "Conclusions · 3", got["drawerTitle"]

    finds = [s["text"] for g in fixture.values() for s in g if s["level"] == "good"]
    lims = [s["text"] for g in fixture.values() for s in g if s["level"] != "good"]
    for f in finds:
        for L in lims:
            assert got["drawer"].index(f) < got["drawer"].index(L), (
                f"the limit {L!r} is rendered above the finding {f!r}")


def test_the_button_counts_findings_and_titles_both():
    """The count is what a reader decides to open the drawer for.

    AUDIT. The old guard asserted that "currentFindings()", "currentLimits()" and
    "plural(" all appear in syncLimitsButton. The function computes both counts, so both
    names are there whichever one it displays: the audit changed the badge to
    `String(n)` -- the LIMITS -- and the guard passed. A reader would have seen 3 on a
    frame with one finding.

    NOW. syncLimitsButton is reached through renderReadout with a fixture built so the two
    counts CANNOT be confused: 1 finding and 3 limits. The badge must read "1", the
    tooltip exactly "1 finding, 3 limits" -- singular, which is the whole point of
    plural() -- and the empty case must read "0" with the button marked as having nothing
    to show."""
    fixture = {
        "arm_statements": [{"level": "bad", "text": "ARM LIMIT: nothing reaches the target."},
                           {"level": "warn", "text": "ARM LIMIT: 62 frames have no scale."}],
        "specimen": [{"level": "good", "text": "THE ONLY FINDING: cracking rises to one edge."}],
        "frame": [{"level": "info", "text": "FRAME LIMIT: no scale, um withheld."}],
    }
    got = render(fixture)
    assert got["page"]["#limitsn"]["text"] == "1", "the badge is not the finding count"
    assert got["page"]["#limitsbtn"]["title"] == "1 finding, 3 limits", (
        got["page"]["#limitsbtn"]["title"])
    assert got["page"]["#limitsbtn"]["none"] == "0"

    empty = render({"arm_statements": [], "specimen": [], "frame": []})
    assert empty["page"]["#limitsn"]["text"] == "0"
    assert empty["page"]["#limitsbtn"]["title"] == "0 findings, 0 limits"
    assert empty["page"]["#limitsbtn"]["none"] == "1"


def test_the_strip_still_leads_with_the_worst_statement():
    """A reader who never opens the drawer must not be able to miss a caveat. This is the
    one place the severity ordering is still right, because there is room for one line.

    AUDIT. The old guard searched the 400 characters before `RO_TOP = all.length` for the
    substring "SEV[a.level]". The audit reversed the comparator to
    `(SEV[b.level] ?? 9) - (SEV[a.level] ?? 9)` -- both substrings still present -- and
    the strip began leading with the LEAST severe statement while the guard passed.

    NOW. renderReadout is run on four statements whose severity order is the reverse of
    their input order, with the single "bad" one LAST so that neither input order nor a
    reversed sort can produce it. RO_TOP must be that statement, with its level, its basis
    and more = 3 (four statements, one shown). The empty case must leave RO_TOP empty
    rather than inventing a line."""
    fixture = {
        "arm_statements": [],
        "specimen": [
            {"level": "info", "text": "INFO: one imaged site per specimen."},
            {"level": "good", "text": "GOOD: cracking rises toward one edge of the raster."},
        ],
        "frame": [
            {"level": "warn", "text": "WARN: not resolvably oriented."},
            {"level": "bad", "text": "BAD: length unreliable, two estimators differ 1.9x.",
             "basis": "two length estimators, 1.9x apart"},
        ],
    }
    top = render(fixture)["top"]
    assert top["level"] == "bad", f"the strip leads with a {top['level']} statement"
    assert top["text"] == "BAD: length unreliable, two estimators differ 1.9x.", top["text"]
    assert top["basis"] == "two length estimators, 1.9x apart", (
        "the strip dropped the basis of the statement it leads with")
    assert top["more"] == 3, top["more"]

    assert render({"arm_statements": [], "specimen": [], "frame": []})["top"] == {}

    # The sort is still in the source too, which is where it has to be: the strip is
    # rendered from RO_TOP by renderStrip, not from RO.
    src = _src()
    i = src.index("RO_TOP = all.length")
    assert "SEV[a.level]" in src[max(0, i - 400):i], "the strip no longer sorts by severity"
