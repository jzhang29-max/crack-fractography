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


def test_the_caveats_are_collapsed_behind_one_counted_line():
    html = render(STATEMENTS)
    assert "<details" in html, "seven caveats expanded is what made the pane unreadable"
    assert "7 limits on this frame" in html, (
        "the disclosure must carry its own count, so a reader sees there are seven "
        "without reading seven")
    _, _, tail = html.partition("<details")
    for st in (s for g in STATEMENTS.values() for s in g if s["level"] != "good"):
        assert esc(st["text"]) in tail


def test_nothing_is_truncated_away():
    """The old cap dropped four of nine statements into a button. Every statement the
    engine produced must be present in the markup -- collapsed is fine, absent is not."""
    html = render(STATEMENTS)
    for st in (s for g in STATEMENTS.values() for s in g):
        assert esc(st["text"]) in html, f"dropped: {st['text']}"
    assert "ro-more" not in html, "the truncating button is gone; nothing should emit it"
    assert "hidden" not in html, "no statement should be rendered with [hidden]"


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
