#!/usr/bin/env python3
"""Which image the Mark tab shows, and the bug where it showed the wrong one.

THE DEFECT. The tab had two modes, "Edit mask" and "Full tool", and the reader had to know
which one their frame supported. Picking a TXM frame while the full tool was running left
the SEM tool on screen -- displaying 260622_316_H_b2_back_CBS_01 -- with a note underneath
saying the chosen frame was not one of its 154 images. The sidebar highlighted one image and
the canvas showed another, and a brush stroke would have landed on the image the reader was
not looking at. It was reported as "the txm images don't work", which understates it.

The rule is now one pure function, tested here without a DOM, because the thing that went
wrong was a decision rather than a rendering.
"""
import json
import os
import shutil
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPJS = os.path.join(REPO, "app", "static", "app.js")


def can_open(running, frame, images, arm="sem/gated"):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = open(APPJS, encoding="utf-8").read()
    # TOOL_ARMS is part of the rule, so it has to come along -- taking only the function
    # gave ReferenceError, which is the harness telling the truth about a real dependency.
    arms = src[src.index("const TOOL_ARMS"):]
    arms = arms[:arms.index("\n") + 1]
    fn = src[src.index("function toolCanOpen("):src.index("async function renderMark()")]
    harness = (arms + fn + "\nprocess.stdout.write(JSON.stringify(toolCanOpen("
               + json.dumps(running) + ", " + json.dumps(frame)
               + ", new Set(" + json.dumps(images) + "), " + json.dumps(arm) + ")));\n")
    out = subprocess.run([node, "-e", harness], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)



def js(body):
    """Run `body` under node; parse what it writes to stdout as JSON.

    Four guards in this file were repaired from source scans into executions of the real
    app.js functions, because a scan for a substring cannot tell `have.has(m.arm)` from
    `true` -- see each repaired docstring. This is the shared harness.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", body], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def js_block(code, marker):
    """`code` from `marker` to the close of the first brace-delimited block after it.

    Used instead of a line slice so a guard reads the WHOLE statement: an earlier version
    of the start-bar guard took 32 characters and scanned the wrong text entirely (see the
    note in the mounting guard). No brace in the regions this is applied to occurs inside
    a string or an unbalanced template hole, so counting is sufficient here.
    """
    i = code.index(marker)
    j = code.index("{", i)
    depth = 0
    for k in range(j, len(code)):
        if code[k] == "{":
            depth += 1
        elif code[k] == "}":
            depth -= 1
            if depth == 0:
                return code[i:k + 1]
    raise AssertionError(f"unbalanced braces after {marker!r}")


#: A DOM small enough to be obviously correct, faithful on the one point these guards turn
#: on: writing innerHTML DETACHES what was there and builds new nodes, so anything living
#: inside the old markup -- an iframe's unsaved strokes, its 23 MB loaded template -- is
#: gone. WRITES counts innerHTML writes; PREPENDS counts bars added.
NODE_DOM = r"""
let WRITES = 0, PREPENDS = 0;
const DOM = {};
function mkEl(id) {
  return {
    id: id, tag: "", className: "", hidden: null, children: [],
    get innerHTML() { return this._h || ""; },
    set innerHTML(v) {
      WRITES++;
      this._h = v;
      for (const m of v.matchAll(/id="([^"]+)"/g)) DOM[m[1]] = mkEl(m[1]);
    },
    prepend(n) { PREPENDS++; this.children.unshift(n); },
  };
}
const $ = (s) => DOM[s.slice(1)] || null;
const document = { createElement: (t) => { const e = mkEl(null); e.tag = t; return e; } };
"""


def mode_rules(src):
    """MODES, modeOptions(), firstMode() and plural(), lifted verbatim, ready for node.

    ARM_HAS_ORIGINALS is a module-level `let` that modeOptions assigns into; it is declared
    here rather than sliced because it is harness scaffolding, not the rule under test.
    """
    return ("let ARM_HAS_ORIGINALS = {};\n"
            + src[src.index("const MODES = ["):src.index("const esc = ")])


def code_only(text):
    """`text` with // comment lines removed.

    THREE assertions in this file have failed against CORRECT code by matching the comment
    written to explain the thing they forbid: a guard for loadArm() matched
    "NOT loadArm(): ...", and a guard for the string "all 1 frames" matched the comment
    quoting it. A source scan must look at code, so every scan here goes through this.
    """
    return "\n".join(L for L in text.split("\n") if not L.strip().startswith("//"))


SEM = "260622_316_H_b2_back_CBS_01"
TXM = "Average_mosaic_260618_B2_3_1_lbf_idx00000_mosaictileAA_img001of010.xrm.bim.bim"


def test_a_name_that_collides_with_a_sem_original_does_not_open_the_sem_tool():
    """THE ARM IS PART OF THE IDENTITY. The SEM repo's own export names masks
    `<stem>_gated.png` and this app's canonical_stem() strips `_gated`, so uploading
    MAR_H_AS_CBS_0001_gated.png files it as arm=uploads, frame=MAR_H_AS_CBS_0001 -- a name
    that IS one of the tool's 154 originals. Matching on the name alone opened the SEM
    repo's own micrograph while the sidebar said uploads: the same defect the TXM case
    established, reached through a collision instead of a gap."""
    assert can_open(True, "MAR_H_AS_CBS_0001", ["MAR_H_AS_CBS_0001"], arm="uploads") is False
    assert can_open(True, "MAR_H_AS_CBS_0001", ["MAR_H_AS_CBS_0001"], arm="txm") is False
    # And the arms it does serve still work.
    assert can_open(True, "MAR_H_AS_CBS_0001", ["MAR_H_AS_CBS_0001"], arm="sem/gated") is True
    assert can_open(True, "MAR_H_AS_CBS_0001", ["MAR_H_AS_CBS_0001"], arm="sem/machine") is True


def test_a_frame_the_tool_does_not_hold_never_shows_the_tool():
    """THE REGRESSION. The tool holds the 154 SEM originals and nothing else. Asked about a
    TXM frame it must answer no, so the caller shows the mask editor instead of leaving
    someone else's image on screen."""
    assert can_open(True, TXM, [SEM], arm="txm") is False


def test_the_tool_shows_for_a_frame_it_does_hold():
    assert can_open(True, SEM, [SEM]) is True


def test_no_tool_when_it_is_not_running():
    assert can_open(False, SEM, [SEM]) is False


def test_no_tool_when_no_frame_is_chosen():
    assert can_open(True, "", [SEM]) is False
    assert can_open(True, None, [SEM]) is False


def test_an_empty_image_list_is_not_a_wildcard():
    """If /mark/api/images fails the set is empty, and an empty set must mean "it holds
    nothing", not "it holds everything". The failure mode of the opposite reading is the
    original bug, reached by a different route."""
    assert can_open(True, SEM, []) is False


def test_there_is_no_mode_toggle_left_to_get_wrong():
    """The two buttons were the mechanism: they let the app be in a state where the visible
    canvas and the selected frame disagreed, and asked the reader to resolve it."""
    src = open(APPJS, encoding="utf-8").read()
    for gone in ("MARK_MODE", "wireModes", "markmodes", "Full tool</button>"):
        assert gone not in src, f"{gone!r} survives; the mode machinery is meant to be gone"
    css = open(os.path.join(REPO, "app", "templates", "index.html"), encoding="utf-8").read()
    assert "markmodes" not in css


def test_the_tool_and_the_editor_are_both_mounted_so_switching_keeps_state():
    """Tearing the iframe down on every switch would discard unsaved strokes and refetch a
    23 MB template on the way back, so visibility is toggled instead.

    REPAIRED -- IT MEASURED NOTHING. The old guard asserted that the strings 'id="marktool"'
    and 'id="markedit"' occur in markShell's text and that "tool.hidden" and "edit.hidden"
    occur in renderMark's. Deleting the line that makes the mount idempotent --
    `if ($("#marktool")) return;` -- leaves every one of those four strings in place, so
    the guard passed while markShell re-wrote #markbody.innerHTML on EVERY renderMark,
    detaching the iframe and losing exactly the unsaved strokes and the 23 MB template the
    message names. It was pinned to the markup rather than to the behaviour.

    It now RUNS markShell twice against a DOM stub and asserts the property: the second
    call writes no innerHTML, returns the SAME #marktool and #markframe nodes, and a value
    parked on the iframe between the calls survives. The expectation (one write, identity
    preserved) comes from what "stays mounted" means, not from the code.

    The visibility half is now asserted as a property too: the two hidden-assignments must
    be COMPLEMENTARY, which a both-shown or both-hidden mutation breaks and a substring
    check does not see."""
    src = open(APPJS, encoding="utf-8").read()
    shell = js_block(src, "function markShell()")
    r = js(NODE_DOM + "DOM.markbody = mkEl('markbody');\n" + shell + r"""
markShell();
const tool1 = $("#marktool"), edit1 = $("#markedit"), frame1 = $("#markframe");
const writes_after_first = WRITES;
if (frame1) frame1.unsavedStrokes = 17;   // what a teardown would throw away
markShell();                              // the Mark -> Results -> Mark round trip
process.stdout.write(JSON.stringify({
  mounted_tool: !!tool1, mounted_edit: !!edit1, mounted_frame: !!frame1,
  writes_after_first: writes_after_first,
  writes_after_second: WRITES,
  same_tool: tool1 === $("#marktool"),
  same_frame: frame1 === $("#markframe"),
  strokes: $("#markframe") ? ($("#markframe").unsavedStrokes ?? null) : null,
}));
""")
    assert r["mounted_tool"] and r["mounted_edit"], (
        "one call to markShell does not mount both containers, so a switch cannot be a "
        "visibility toggle")
    assert r["mounted_frame"], "the iframe is not inside the mounted shell"
    assert r["writes_after_first"] == 1, r
    assert r["writes_after_second"] == 1, (
        "markShell re-wrote #markbody.innerHTML on the second visit: the mount is not "
        "idempotent, so every switch detaches the iframe")
    assert r["same_tool"] and r["same_frame"], (
        "the containers are different nodes after a second visit -- they were rebuilt")
    assert r["strokes"] == 17, (
        "state parked on the iframe did not survive a second visit; this is the unsaved "
        "stroke loss, and the 23 MB refetch, that keeping both mounted exists to prevent")

    rm = src[src.index("async function renderMark()"):src.index("async function syncMarkFrame()")]
    import re as _re
    pairs = set(_re.findall(r"tool\.hidden = (true|false); edit\.hidden = (true|false);", rm))
    assert pairs == {("false", "true"), ("true", "false")}, (
        f"the hidden-flags are not complementary across the two branches: {pairs}; "
        "exactly one of the tool and the editor is on screen at a time")
    # THE SLICE WAS 32 CHARACTERS LONG. `rm.split("markShell()")[0]` splits at the FIRST
    # occurrence, which is the call on renderMark's opening line, so the text actually
    # scanned was 'async function renderMark() {\n  ' -- re-introducing the exact
    # regression the message names would have left this passing. What matters is that
    # renderMark never writes innerHTML on the SHELL container; writing into #markedit is
    # how the editor is mounted and is correct.
    code = code_only(rm)
    bad = _re.findall(r'\$\("#markbody"\)[^\n]*innerHTML', code)
    assert not bad, (
        f"renderMark writes #markbody.innerHTML ({bad}), which destroys #marktool and "
        "#markedit and therefore the live iframe -- discarding unsaved strokes and "
        "forcing a 23 MB refetch")
    assert "markShell()" in code.split("\n")[1], (
        "the shell is not built on entry, so the containers may not exist")


# --- THE PAGE STRUCTURE THE USER ASKED FOR --------------------------------------------
def test_there_are_two_tabs_not_three():
    """Analysis and Figure both answered "what do these images show?", so the figure -- the
    thing most worth looking at -- was the one behind an extra click."""
    src = open(APPJS, encoding="utf-8").read()
    tabs = src[src.index("const TABS = ["):src.index("let TAB =")]
    assert '"mark"' in tabs and '"results"' in tabs
    assert '"figure"' not in tabs and '"analysis"' not in tabs, tabs


def test_the_figure_is_on_the_results_page_above_the_frame_detail():
    html = open(os.path.join(REPO, "app", "templates", "index.html"), encoding="utf-8").read()
    pane = html[html.index('id="pane-results"'):html.index('</main>')]
    assert 'id="figout"' in pane, "the figure did not move onto the results page"
    assert pane.index('id="figout"') < pane.index('id="mask"'), (
        "the frame's mask comes before the figure; the figure is the headline")
    assert 'id="pane-figure"' not in html, "the old figure pane is still in the document"


def test_the_refusal_section_is_not_in_the_ui():
    """It listed four questions the app declines, on every frame, so a page whose job is to
    report findings opened with a block about what it cannot do. The refusals still exist
    in conclusions.py and still travel in the API response -- they are not rendered."""
    html = open(os.path.join(REPO, "app", "templates", "index.html"), encoding="utf-8").read()
    src = open(APPJS, encoding="utf-8").read()
    assert 'id="refusals"' not in html
    assert "Asked and answered" not in src and "Asked and answered" not in html
    # Still available to anyone who asks the endpoint.
    import sys
    sys.path.insert(0, os.path.join(REPO, "analysis"))
    import conclusions
    assert len(conclusions.REFUSALS) >= 4, "the reasoning itself must not have been deleted"


def test_a_group_row_only_opens_and_shuts():
    """It used to do two things: toggle the group AND scope every statistic to that
    specimen. Two behaviours on one click, one of them invisible, and the scoping was
    never asked for -- a disclosure triangle opens and shuts."""
    src = open(APPJS, encoding="utf-8").read()
    h = src[src.index('t.querySelectorAll("tbody tr.grp")'):]
    h = h[:h.index("\n  });") + 6]
    code = code_only(h)
    assert "GROUPS_OPEN" in code and "GROUPS_CLOSED" in code
    assert "state.spec" not in code, "the row still scopes as a side effect of expanding"
    assert "selectFrame(" not in code, "the row still changes the selection"
    assert "loadArm()" not in code


def test_a_group_can_be_shut_even_when_it_holds_the_selected_frame():
    """THE REPORTED BUG: "you can click and expand but you can't unexpand it." The open
    condition includes "contains the selected frame", which is right on load -- and became
    inescapable once clicking a group also selected a frame inside it, so the group you
    just opened permanently contained the selection. An explicit close has to win."""
    src = open(APPJS, encoding="utf-8").read()
    i = src.index("const open = GROUPS_CLOSED")
    stmt = src[i:src.index(";", i)]
    assert "GROUPS_CLOSED.has(spec) ? false" in stmt, (
        "a deliberate close does not override the auto-open")
    assert "f.frame === state.frame" in stmt, (
        "the group holding the selection no longer opens itself on load")
    # And the two sets must be kept disjoint by the handler, or a group ends up in both.
    h = src[src.index('t.querySelectorAll("tbody tr.grp")'):]
    h = code_only(h[:h.index("\n  });") + 6])
    assert "GROUPS_CLOSED.delete" in h and "GROUPS_OPEN.delete" in h, (
        "opening does not clear the closed flag, or closing does not clear the open one")


def test_changing_arm_clears_the_frame_from_the_previous_arm():
    """state.frame belongs to the arm being left. loadArm() re-renders before it picks the
    new arm's first frame, so the read-out fired
    /api/readout?arm=uploads&frame=<a TXM frame name> and took a 404 on every arm switch.
    The next render corrects it, which is why it survived -- a 404 per switch in the
    console is the noise a real one hides behind."""
    src = open(APPJS, encoding="utf-8").read()
    h = src[src.index('$("#arm").onchange'):]
    h = h[:h.index("};") + 2]
    code = code_only(h)
    assert "state.frame = null" in code, (
        "the previous arm's frame is carried into the new arm's requests")
    assert "state.spec" in code


def test_a_one_field_specimen_does_not_read_one_fields():
    """Every fresh upload is a one-field specimen, so "1 fields" is among the first things
    a new user reads. Two sites printed it."""
    src = open(APPJS, encoding="utf-8").read()
    import re
    # Any interpolation of a count immediately followed by a bare plural noun.
    bad = re.findall(r"\$\{[A-Za-z_.\[\]]*n_(?:fields|frames)\} (?:fields|frames)", src)
    assert not bad, f"unpluralised counts: {bad}"


def test_the_start_bar_is_added_once_not_once_per_visit():
    """openEditor early-returns when the frame has not changed, which is exactly what a
    Mark -> Results -> Mark round trip looks like -- so an unconditional prepend added
    another "Start the full tool" bar on every visit: three visits, three bars, three
    elements sharing id="markstart".

    REPAIRED -- IT MEASURED NOTHING, by a superset that always contains it. The old guard
    took every character of renderMark before `prepend(bar)` and asked that it contain
    "markstart" and "!". Both are in that text unconditionally: "markstart" appears in the
    bar's own `<button id="markstart">` markup and in `$("#markstart")` itself, and "!"
    appears in `!fr.src`, `!state.frame` and `!paint.running` further up. Changing the
    guard from `if (startable && !existing)` to `if (startable)` -- precisely the
    unconditional prepend the docstring describes -- left this passing.

    It now RUNS the real statement: the `const existing = ...` line and the whole if-block
    are lifted out of renderMark and executed three times against a DOM stub, which is what
    three Mark -> Results -> Mark round trips do (openEditor early-returns, so #markstart
    from visit one is still in the document on visit two). The expectation is counted by
    hand from the behaviour in the title: three visits, ONE bar. Two further visits with
    startable false check the other direction, that a copy with no SEM repo behind it is
    not offered the button at all."""
    src = open(APPJS, encoding="utf-8").read()
    rm = src[src.index("async function renderMark()"):src.index("async function syncMarkFrame()")]
    code = code_only(rm)
    assert "prepend(bar)" in code, "the start bar is no longer prepended"
    block = js_block(code, 'const existing = $("#markstart");')
    assert "prepend(bar)" in block, (
        f"the prepend is not inside the extracted statement: {block!r}")
    r = js(NODE_DOM + r"""
DOM.markedit = mkEl("markedit");
const edit = DOM.markedit;
function visit(startable) {
""" + block + r"""
}
visit(true); visit(true); visit(true);
const after_three = { bars: PREPENDS, present: !!$("#markstart") };
PREPENDS = 0; delete DOM.markstart;          // a fresh page, no SEM repo behind it
visit(false); visit(false);
process.stdout.write(JSON.stringify({
  bars_after_three_visits: after_three.bars,
  bar_present: after_three.present,
  bars_when_not_startable: PREPENDS,
}));
""")
    assert r["bar_present"] is True, "the bar was never added at all"
    assert r["bars_after_three_visits"] == 1, (
        f"three visits to Mark added {r['bars_after_three_visits']} start bars; each one "
        'carries id="markstart", so the page ends up with duplicate ids')
    assert r["bars_when_not_startable"] == 0, (
        "a bar is offered even when the arm cannot be served -- the dead control the "
        "modes used to be")


def test_the_start_button_is_not_offered_on_an_arm_the_tool_cannot_serve():
    """The guard read `... && (await markImages()).size === 0`, and markImages() can only
    return names from a RUNNING tool -- so whenever the tool is not running the set is
    empty and that conjunct is always true. It excluded nothing, and the button appeared on
    TXM frames the tool cannot open: the dead control the modes used to be, reintroduced by
    the guard written to prevent it."""
    src = open(APPJS, encoding="utf-8").read()
    rm = src[src.index("async function renderMark()"):src.index("async function syncMarkFrame()")]
    code = code_only(rm)
    # The WHOLE statement, not its first line: the guard now wraps, and a one-line check
    # read only `const startable = paint.available && !paint.running` and reported the arm
    # term missing from correct code.
    assert "startable =" in code, "the startable guard vanished"
    stmt = code[code.index("startable ="):]
    stmt = stmt[:stmt.index(";") + 1]
    assert "markImages()" not in stmt, (
        "the guard still consults an image list that is empty whenever it is consulted")
    assert "state.arm" in stmt, "the guard does not test the arm, which is knowable"
    assert "TOOL_ARMS" in stmt, "the served arms are hardcoded rather than named once"


def test_the_frame_list_is_never_narrowed_to_one_specimen():
    """THE REGRESSION. Four sites refetched frames with `&specimen=` appended, so scoping a
    specimen and then pressing Re-measure replaced the only frame picker in the app with
    that specimen's rows -- 142 down to 1 -- and un-scoping did not refetch, so it stayed
    collapsed with the count beside it still reading "62/142 frames"."""
    src = open(APPJS, encoding="utf-8").read()
    import re
    bad = re.findall(r"state\.frames = await api\([^)]*specimen", src, re.S)
    assert not bad, f"a frames fetch is still specimen-filtered: {bad}"
    assert src.count("state.frames = await allFrames();") >= 4, (
        "the unfiltered helper is not used at every refetch site")
    helper = src[src.index("async function allFrames()"):]
    helper = helper[:helper.index("\n}")]
    assert "specimen" not in helper, "allFrames() filters, which defeats the point"


def test_the_limits_drawer_names_which_specimen_and_frame_it_describes():
    """It labelled its groups "About this specimen" without naming which, which is how a
    reader takes the wrong confidence interval into a caption."""
    src = open(APPJS, encoding="utf-8").read()
    fn = src[src.index("function openLimits()"):src.index("function openDefs(")]
    assert "state.spec" in fn and "state.frame" in fn, fn[:200]
    assert "About this specimen" in fn, "no fallback wording when nothing is scoped"
    assert "state.arm" in fn, "the arm-level group does not name the arm"


def test_no_css_survives_for_the_removed_refusal_section():
    """The .markmodes half of this cleanup was done and is asserted above; the .refuse half
    was missed. Nine rules matching nothing is not a failure, but it is the residue that
    makes the next reader think the section still exists."""
    css = open(os.path.join(REPO, "app", "templates", "index.html"), encoding="utf-8").read()
    src = open(APPJS, encoding="utf-8").read()
    for cls in (".refuse", ".refuse-all", ".refuse-all-open", ".ans"):
        assert cls not in css, f"{cls} still styled, but nothing emits it"
    for cls in ('class="refuse', 'class="ans'):
        assert cls not in src


def test_the_unreachable_top_conclusion_banner_is_gone():
    """It was emitted only when TAB !== "results" while the strip itself is painted only
    when ANALYSIS_TABS.has(TAB), and ANALYSIS_TABS is now {"results"} -- two mutually
    exclusive conditions, so it could never appear."""
    src = open(APPJS, encoding="utf-8").read()
    assert "striptop" not in src
    html = open(os.path.join(REPO, "app", "templates", "index.html"), encoding="utf-8").read()
    assert "striptop" not in html


def test_loadarm_does_not_fetch_a_list_nothing_reads():
    """The specimen fetch fed the deleted dropdown. Its two consumers went with the
    dropdown, leaving every arm change blocking on a round trip that was discarded -- and
    duplicating the request renderSpecimens() makes moments later."""
    src = open(APPJS, encoding="utf-8").read()
    fn = src[src.index("async function loadArm()"):]
    fn = fn[:fn.index("\n}\n")]
    code = "\n".join(L for L in fn.split("\n") if not L.strip().startswith("//"))
    assert "/api/specimens" not in code, "loadArm still fetches the specimen list"
    assert "let specs" not in code


def test_the_frame_list_header_pluralises_too():
    """The pluralise pass missed it: the guard matched `${...n_frames}` and this site
    interpolates state.frames.length, so the arm dropdown read "uploads . 1 frame" while
    the header directly beneath it read "all 1 frames scaled"."""
    src = code_only(open(APPJS, encoding="utf-8").read())
    assert "all 1 frames" not in src
    # There are four writes to #listcount; the one that carries the count is the noScale
    # ternary. Taking the first match found `= ""` and reported correct code as wrong.
    i = src.index("$(\"#listcount\").textContent = noScale")
    stmt = src[i:src.index(";", i)]
    assert "plural(" in stmt or '=== 1 ?' in stmt, stmt
    assert "frames scaled`" not in stmt, "the plural is still hardcoded in the scaled branch"


def test_no_comment_claims_a_tab_count_or_a_tab_that_does_not_exist():
    """Comments described three tabs, told the reader the strip banner "earns its place on
    Mark, Compare and Figure", and named Analysis as somewhere it was suppressed -- while
    the code has two tabs, the banner is deleted, and Figure is part of Results. Acting on
    that comment would have restored a duplicate sentence 200 px from its original. Stale
    prose under a change is a recurring defect here, so it is asserted."""
    src = open(APPJS, encoding="utf-8").read()
    comments = "\n".join(L for L in src.split("\n") if L.strip().startswith("//"))
    # PRESCRIPTIVE CLAIMS ONLY. A first version banned any mention of "the Figure tab" and
    # failed on two comments that narrate, in the past tense, a bug from when that tab
    # existed -- which is accurate and worth keeping. What must not survive is a comment
    # that tells the reader something is true NOW, or directs behaviour at a tab that is
    # gone: acting on "it earns its place on Mark, Compare and Figure" would have restored
    # a duplicate sentence 200 px from its original.
    for phrase in ("THREE TABS", "on Mark, Compare and Figure", "NOT ON ANALYSIS"):
        assert phrase not in comments, f"a comment still asserts {phrase!r}"
    # And the tab list itself is the authority on how many there are.
    tabs = src[src.index("const TABS = ["):src.index("let TAB =")]
    assert tabs.count('["') == 2, f"the tab list has {tabs.count('[\"')} entries"


# --- MODES, NOT STORAGE LAYOUT ---------------------------------------------------------
def test_the_selector_offers_instruments_not_arms():
    """It listed "sem/gated", "sem/machine", "txm", "uploads" -- the storage layout, not a
    choice anyone wants to make. Asked for SEM or TXM."""
    src = open(APPJS, encoding="utf-8").read()
    modes = src[src.index("const MODES = ["):src.index("function modeOptions(")]
    assert '"SEM"' in modes and '"TXM"' in modes
    assert '"sem/gated"' in modes and '"txm"' in modes
    assert "sem/machine" not in modes, (
        "the uncorrected arm is offered again; its only consumer is the corrections "
        "comparison, which reads it server-side")
    # The label is what the reader sees, so the raw arm string must not be rendered.
    opts = src[src.index("function modeOptions("):src.index("function firstMode(")]
    assert "m.label" in opts and "${a.arm}" not in opts


def test_a_mode_with_no_frames_is_not_offered():
    """A fresh install has only uploads; a configured one has all three. Offering an arm
    the dataset does not contain is a dead entry that 404s on selection.

    REPAIRED -- IT MEASURED NOTHING. The old guard asked whether the text of modeOptions
    contains "have.has" OR "filter". Rewriting the filter as `MODES.filter((m) => true)`
    keeps the word "filter", so the guard passed while a fresh install -- uploads only --
    was offered SEM, TXM and TXM-model-only, every one of them a dead entry that 404s on
    selection. (It is worse than a dead entry: with no matching arm, `have.get(m.arm)` is
    undefined and reading `a.n_frames` throws, so the whole selector fails to render.)

    It now CALLS modeOptions on three fixtures and compares against option strings written
    out by hand from MODES' labels and the plural rule -- a fresh install, a configured one
    whose arms arrive in a different order from MODES, and one holding only sem/machine,
    which is deliberately not a mode at all. The exact-string comparison also pins the
    ORDER to MODES rather than to whatever order the server listed the arms in."""
    src = open(APPJS, encoding="utf-8").read()
    r = js(mode_rules(src) + r"""
process.stdout.write(JSON.stringify({
  fresh:        modeOptions([{arm: "uploads", n_frames: 1, has_originals: false}]),
  configured:   modeOptions([{arm: "uploads", n_frames: 3, has_originals: false},
                             {arm: "txm", n_frames: 71, has_originals: true},
                             {arm: "sem/gated", n_frames: 154, has_originals: true}]),
  sem_machine_only: modeOptions([{arm: "sem/machine", n_frames: 154, has_originals: true}]),
  no_arms:      modeOptions([]),
  null_arms:    modeOptions(null),
}));
""")
    DOT = "·"
    # By hand from MODES: uploads is labelled "Your images", and plural(1, "frame") is
    # "1 frame" -- one option, and not one of the other three.
    assert r["fresh"] == f'<option value="uploads">Your images {DOT} 1 frame</option>', r["fresh"]
    # By hand again, in MODES order and NOT the order the arms were handed over in.
    assert r["configured"] == (
        f'<option value="sem/gated">SEM {DOT} 154 frames</option>'
        f'<option value="txm">TXM {DOT} 71 frames</option>'
        f'<option value="uploads">Your images {DOT} 3 frames</option>'), r["configured"]
    assert r["sem_machine_only"] == "", (
        "sem/machine is offered; it is not in MODES, and its only consumer is the "
        "corrections comparison, which reads it server-side")
    assert r["no_arms"] == "" and r["null_arms"] == "", (
        "a dataset with no arms still produces options")


def test_the_opening_mode_falls_back_when_sem_is_absent():
    """A downloaded copy with no SEM repo must land on something that exists.

    REPAIRED -- IT MEASURED NOTHING. The old guard asked that firstMode's text contain
    "MODES.find" and "arms &&". Rewriting the predicate as `MODES.find((x) => true)` keeps
    both strings -- MODES.find is still there and the "arms &&" is in the fallback return
    below it -- so the guard passed while firstMode returned "sem/gated" on a copy with no
    SEM repo at all: the opening arm 404s, which is the whole thing this guards.

    It now CALLS firstMode. The expectations are read off MODES by hand: with only uploads
    present the answer is "uploads"; with SEM present it is "sem/gated" even when the
    server listed uploads first, because MODES order is the preference; with nothing in
    MODES present it falls through to the first arm that does exist; and the three empty
    shapes -- [], null, undefined -- must return "uploads" rather than throwing, which is
    what the "arms &&" string used to stand in for."""
    src = open(APPJS, encoding="utf-8").read()
    r = js(mode_rules(src) + r"""
process.stdout.write(JSON.stringify({
  uploads_only:     firstMode([{arm: "uploads", n_frames: 1}]),
  sem_present:      firstMode([{arm: "uploads"}, {arm: "txm"}, {arm: "sem/gated"}]),
  no_sem:           firstMode([{arm: "txm"}, {arm: "uploads"}]),
  sem_machine_only: firstMode([{arm: "sem/machine"}]),
  empty:            firstMode([]),
  null_arms:        firstMode(null),
  undef_arms:       firstMode(undefined),
}));
""")
    assert r["uploads_only"] == "uploads", (
        f"a copy with no SEM repo opens on {r['uploads_only']!r}, which it does not have")
    assert r["sem_present"] == "sem/gated", (
        "SEM is present but is not the opening mode; MODES order is the preference, not "
        "the order the server happened to list the arms in")
    assert r["no_sem"] == "txm", r
    assert r["sem_machine_only"] == "sem/machine", (
        "no mode matches, so it must fall back to an arm that exists rather than to a "
        "mode that does not")
    assert r["empty"] == "uploads" and r["null_arms"] == "uploads" and \
        r["undef_arms"] == "uploads", r


def test_the_image_list_is_not_fetched_when_no_tool_is_running():
    """markImages() fetches /mark/api/images, which the proxy answers 503 with nothing
    behind it -- so every visit to Mark in a copy with no SEM repo (every downloaded copy,
    and all three CI runners) logged a console error for a question already answered by
    paint.running one line above. It never appeared locally because the tool runs here."""
    src = open(APPJS, encoding="utf-8").read()
    rm = src[src.index("async function renderMark()"):src.index("async function syncMarkFrame()")]
    code = code_only(rm)
    i = code.index("canUseTool")
    stmt = code[i:code.index(";", i)]
    assert "paint.running" in stmt and "&&" in stmt, (
        "markImages() is awaited before the running check short-circuits it")
    assert stmt.index("paint.running") < stmt.index("markImages()"), (
        "the running check must come first, or the fetch happens anyway")
