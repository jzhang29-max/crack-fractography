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
