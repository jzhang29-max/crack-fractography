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


def can_open(running, frame, images):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = open(APPJS).read()
    fn = src[src.index("function toolCanOpen("):src.index("async function renderMark()")]
    harness = (fn + "\nprocess.stdout.write(JSON.stringify(toolCanOpen("
               + json.dumps(running) + ", " + json.dumps(frame)
               + ", new Set(" + json.dumps(images) + "))));\n")
    out = subprocess.run([node, "-e", harness], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


SEM = "260622_316_H_b2_back_CBS_01"
TXM = "Average_mosaic_260618_B2_3_1_lbf_idx00000_mosaictileAA_img001of010.xrm.bim.bim"


def test_a_frame_the_tool_does_not_hold_never_shows_the_tool():
    """THE REGRESSION. The tool holds the 154 SEM originals and nothing else. Asked about a
    TXM frame it must answer no, so the caller shows the mask editor instead of leaving
    someone else's image on screen."""
    assert can_open(True, TXM, [SEM]) is False


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
    src = open(APPJS).read()
    for gone in ("MARK_MODE", "wireModes", "markmodes", "Full tool</button>"):
        assert gone not in src, f"{gone!r} survives; the mode machinery is meant to be gone"
    css = open(os.path.join(REPO, "app", "templates", "index.html")).read()
    assert "markmodes" not in css


def test_the_tool_and_the_editor_are_both_mounted_so_switching_keeps_state():
    """Tearing the iframe down on every switch would discard unsaved strokes and refetch a
    23 MB template on the way back, so visibility is toggled instead."""
    src = open(APPJS).read()
    fn = src[src.index("function markShell()"):src.index("async function renderMark()")]
    assert 'id="marktool"' in fn and 'id="markedit"' in fn
    rm = src[src.index("async function renderMark()"):src.index("async function syncMarkFrame()")]
    assert "tool.hidden" in rm and "edit.hidden" in rm, "visibility is not what switches"
    assert "innerHTML" not in rm.split("markShell()")[0], (
        "renderMark rebuilds the shell, which would tear down the live tool")


# --- THE PAGE STRUCTURE THE USER ASKED FOR --------------------------------------------
def test_there_are_two_tabs_not_three():
    """Analysis and Figure both answered "what do these images show?", so the figure -- the
    thing most worth looking at -- was the one behind an extra click."""
    src = open(APPJS).read()
    tabs = src[src.index("const TABS = ["):src.index("let TAB =")]
    assert '"mark"' in tabs and '"results"' in tabs
    assert '"figure"' not in tabs and '"analysis"' not in tabs, tabs


def test_the_figure_is_on_the_results_page_above_the_frame_detail():
    html = open(os.path.join(REPO, "app", "templates", "index.html")).read()
    pane = html[html.index('id="pane-results"'):html.index('</main>')]
    assert 'id="figout"' in pane, "the figure did not move onto the results page"
    assert pane.index('id="figout"') < pane.index('id="mask"'), (
        "the frame's mask comes before the figure; the figure is the headline")
    assert 'id="pane-figure"' not in html, "the old figure pane is still in the document"


def test_the_refusal_section_is_not_in_the_ui():
    """It listed four questions the app declines, on every frame, so a page whose job is to
    report findings opened with a block about what it cannot do. The refusals still exist
    in conclusions.py and still travel in the API response -- they are not rendered."""
    html = open(os.path.join(REPO, "app", "templates", "index.html")).read()
    src = open(APPJS).read()
    assert 'id="refusals"' not in html
    assert "Asked and answered" not in src and "Asked and answered" not in html
    # Still available to anyone who asks the endpoint.
    import sys
    sys.path.insert(0, os.path.join(REPO, "analysis"))
    import conclusions
    assert len(conclusions.REFUSALS) >= 4, "the reasoning itself must not have been deleted"


def test_the_specimen_is_chosen_in_one_place():
    """A header dropdown SCOPED the statistics to a specimen while the sidebar's group rows
    only expanded and collapsed -- two controls that looked like one thing and did two
    different things. Clicking a specimen's name did not select it."""
    html = open(os.path.join(REPO, "app", "templates", "index.html")).read()
    src = open(APPJS).read()
    assert 'id="spec"' not in html, "the specimen dropdown survives"
    assert '$("#spec")' not in src, "the dropdown is gone but the code still reads it"
    grp = src[src.index('t.querySelectorAll("tbody tr.grp")'):]
    grp = grp[:grp.index("});")]
    # STRIP COMMENTS FIRST. The handler's own comment says "NOT loadArm(): ..." explaining
    # why it must not call it, and a raw substring scan matched that and failed on correct
    # code. This repo has made exactly this mistake before -- a boot guard fooled by the
    # comment written to explain the guard.
    code = "\n".join(L for L in grp.split("\n") if not L.strip().startswith("//"))
    assert "state.spec" in code, "the group row still does not scope the numbers"
    assert "loadArm()" not in code, (
        "refetching the arm on a scope change resets the selection to frames[0] and throws "
        "away the frame the reader was looking at")


def test_changing_arm_clears_the_frame_from_the_previous_arm():
    """state.frame belongs to the arm being left. loadArm() re-renders before it picks the
    new arm's first frame, so the read-out fired
    /api/readout?arm=uploads&frame=<a TXM frame name> and took a 404 on every arm switch.
    The next render corrects it, which is why it survived -- a 404 per switch in the
    console is the noise a real one hides behind."""
    src = open(APPJS).read()
    h = src[src.index('$("#arm").onchange'):]
    h = h[:h.index("};") + 2]
    code = "\n".join(L for L in h.split("\n") if not L.strip().startswith("//"))
    assert "state.frame = null" in code, (
        "the previous arm's frame is carried into the new arm's requests")
    assert "state.spec" in code


def test_a_one_field_specimen_does_not_read_one_fields():
    """Every fresh upload is a one-field specimen, so "1 fields" is among the first things
    a new user reads. Two sites printed it."""
    src = open(APPJS).read()
    import re
    # Any interpolation of a count immediately followed by a bare plural noun.
    bad = re.findall(r"\$\{[A-Za-z_.\[\]]*n_(?:fields|frames)\} (?:fields|frames)", src)
    assert not bad, f"unpluralised counts: {bad}"


def test_the_start_button_is_not_offered_on_an_arm_the_tool_cannot_serve():
    """The guard read `... && (await markImages()).size === 0`, and markImages() can only
    return names from a RUNNING tool -- so whenever the tool is not running the set is
    empty and that conjunct is always true. It excluded nothing, and the button appeared on
    TXM frames the tool cannot open: the dead control the modes used to be, reintroduced by
    the guard written to prevent it."""
    src = open(APPJS).read()
    rm = src[src.index("async function renderMark()"):src.index("async function syncMarkFrame()")]
    code = "\n".join(L for L in rm.split("\n") if not L.strip().startswith("//"))
    line = [L for L in code.split("\n") if "startable =" in L]
    assert line, "the startable guard vanished"
    assert "markImages()" not in line[0], (
        "the guard still consults an image list that is empty whenever it is consulted")
    assert "state.arm" in line[0], "the guard does not test the arm, which is knowable"


def test_the_frame_list_is_never_narrowed_to_one_specimen():
    """THE REGRESSION. Four sites refetched frames with `&specimen=` appended, so scoping a
    specimen and then pressing Re-measure replaced the only frame picker in the app with
    that specimen's rows -- 142 down to 1 -- and un-scoping did not refetch, so it stayed
    collapsed with the count beside it still reading "62/142 frames"."""
    src = open(APPJS).read()
    import re
    bad = re.findall(r"state\.frames = await api\([^)]*specimen", src, re.S)
    assert not bad, f"a frames fetch is still specimen-filtered: {bad}"
    assert src.count("state.frames = await allFrames();") >= 4, (
        "the unfiltered helper is not used at every refetch site")
    helper = src[src.index("async function allFrames()"):]
    helper = helper[:helper.index("\n}")]
    assert "specimen" not in helper, "allFrames() filters, which defeats the point"


def test_scoping_a_specimen_moves_the_selection_into_it():
    """Scoping used to leave state.frame in another specimen, so the strip, specimen card
    and limits drawer described one specimen while the mask, frame statements and
    measurements below were another's."""
    src = open(APPJS).read()
    h = src[src.index('t.querySelectorAll("tbody tr.grp")'):]
    h = h[:h.index("\n  });") + 6]
    code = "\n".join(L for L in h.split("\n") if not L.strip().startswith("//"))
    assert "selectFrame(" in code, "scoping does not move the selection"
    assert "f.specimen === state.spec" in code, (
        "the frame it selects is not required to belong to the scoped specimen")


def test_the_limits_drawer_names_which_specimen_and_frame_it_describes():
    """It labelled its groups "About this specimen" without naming which, which is how a
    reader takes the wrong confidence interval into a caption."""
    src = open(APPJS).read()
    fn = src[src.index("function openLimits()"):src.index("function openDefs(")]
    assert "state.spec" in fn and "state.frame" in fn, fn[:200]
    assert "About this specimen" in fn, "no fallback wording when nothing is scoped"
    assert "state.arm" in fn, "the arm-level group does not name the arm"
