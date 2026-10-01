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
    23 MB template on the way back, so visibility is toggled instead."""
    src = open(APPJS, encoding="utf-8").read()
    fn = src[src.index("function markShell()"):src.index("async function renderMark()")]
    assert 'id="marktool"' in fn and 'id="markedit"' in fn
    rm = src[src.index("async function renderMark()"):src.index("async function syncMarkFrame()")]
    assert "tool.hidden" in rm and "edit.hidden" in rm, "visibility is not what switches"
    # THE SLICE WAS 32 CHARACTERS LONG. `rm.split("markShell()")[0]` splits at the FIRST
    # occurrence, which is the call on renderMark's opening line, so the text actually
    # scanned was 'async function renderMark() {\n  ' -- re-introducing the exact
    # regression the message names would have left this passing. What matters is that
    # renderMark never writes innerHTML on the SHELL container; writing into #markedit is
    # how the editor is mounted and is correct.
    code = code_only(rm)
    import re as _re
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
    elements sharing id="markstart"."""
    src = open(APPJS, encoding="utf-8").read()
    rm = src[src.index("async function renderMark()"):src.index("async function syncMarkFrame()")]
    code = code_only(rm)
    assert "prepend(bar)" in code
    guard = code[:code.index("prepend(bar)")]
    assert "markstart" in guard and "!" in guard, (
        "the bar is prepended without checking whether one is already there")


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
    the dataset does not contain is a dead entry that 404s on selection."""
    src = open(APPJS, encoding="utf-8").read()
    opts = src[src.index("function modeOptions("):src.index("function firstMode(")]
    assert "have.has" in opts or "filter" in opts, (
        "modeOptions does not filter by what the dataset actually contains")


def test_the_opening_mode_falls_back_when_sem_is_absent():
    """A downloaded copy with no SEM repo must land on something that exists."""
    src = open(APPJS, encoding="utf-8").read()
    fn = src[src.index("function firstMode("):]
    fn = fn[:fn.index("\n}")]
    assert "MODES.find" in fn, "the opening mode is not chosen from the mode list"
    assert "arms &&" in fn or "arms?." in fn, "an empty arms list would throw here"


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
