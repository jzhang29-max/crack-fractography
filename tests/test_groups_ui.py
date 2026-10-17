#!/usr/bin/env python3
"""The Groups pane: its controls are wired, and its collections outlive the window.

WHY AN ID-REFERENCE GUARD. /api/groups has been a complete persisted store since it was
written -- read, save, delete, and pruning when a frame is deleted -- and no line of the
client ever called it. Every set of frames a reader assembled was lost on reload. Nothing
failed, nothing logged, and no test noticed, because a control that is never reached and
a control that does not exist look identical from the outside.

So this checks both directions. Markup with an id nothing reaches is a dead control; JS
reaching for an id the markup does not have is a dead handler. Either one ships silently.
"""
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server, mask_png  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(REPO, "app", "templates", "index.html"), encoding="utf-8").read()
JS = open(os.path.join(REPO, "app", "static", "app.js"), encoding="utf-8").read()


def _pane(name):
    start = HTML.index(f'id="pane-{name}"')
    depth, i = 0, HTML.rindex("<div", 0, start)
    # walk forward to the matching close; the pane is a flat-ish block so a div counter is
    # enough and a parser dependency is not worth adding for it
    for m in re.finditer(r"<(/?)div\b", HTML[i:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return HTML[i:i + m.end()]
    raise AssertionError(f"pane-{name} is not closed")


GROUPS = _pane("groups")


#: Half the group controls are reached through a template literal with the side
#: substituted -- $(`#g${side}-clear`), $(`#gcol-${side}`) -- so a check that only looks
#: for the literal string "#ga-clear" reports eleven live controls as dead. Expanding the
#: templates is the difference between a guard and a nuisance.
def _reachable_ids():
    out = set(re.findall(r'[$]\("#([a-z0-9][a-z0-9-]*)"\)', JS))
    out |= set(re.findall(r"[$]\('#([a-z0-9][a-z0-9-]*)'\)", JS))
    out |= set(re.findall(r'getElementById\("([a-z0-9][a-z0-9-]*)"\)', JS))
    for pre, post in re.findall(r'[$]\(`#([a-z0-9-]*)\$\{side\}([a-z0-9-]*)`\)', JS):
        out |= {f"{pre}a{post}", f"{pre}b{post}"}
    # the tab machinery builds every pane id from the TABS table: $("#pane-" + k)
    tabs = JS[JS.index("const TABS = ["):]
    out |= {f"pane-{t}" for t in re.findall(r'\["([a-z]+)",', tabs[:tabs.index("];")])}
    return out


def test_every_control_in_the_groups_pane_is_reached_by_the_code():
    ids = set(re.findall(r'id="([a-z0-9][a-z0-9-]*)"', GROUPS))
    assert len(ids) > 10, f"only found {ids} -- the pane was not located"
    dead = sorted(ids - _reachable_ids())
    assert not dead, f"controls in the Groups pane that no code reaches: {dead}"


def test_every_id_the_group_code_reaches_for_exists_in_the_markup():
    """The other direction. A renamed id leaves `$("#ga-clear")` returning null, the
    optional-chaining `?.` swallows it, and the button simply stops working."""
    start = JS.index("// ============================================================ GROUPS")
    end = JS.index("// ============================================================ CROP")
    block = JS[start:end]
    want = set(re.findall(r'[$]\("#([a-z0-9][a-z0-9-]*)"\)', block))
    for pre, post in re.findall(r'[$]\(`#([a-z0-9-]*)\$\{side\}([a-z0-9-]*)`\)', block):
        want |= {f"{pre}a{post}", f"{pre}b{post}"}
    assert len(want) > 8, f"only found {want} -- the block was not located"
    have = set(re.findall(r'id="([a-z0-9][a-z0-9-]*)"', HTML))
    # An id the group code WRITES ITSELF counts as existing. The distributions placeholder
    # is emitted into the results container a line before it is read, so it is never in
    # index.html -- but it is still subject to this test's real point, that the name on the
    # left of the lookup matches the name on the right of the markup, because both spellings
    # are in this same block and a rename of one without the other still fails here.
    have |= set(re.findall(r'id="([a-z0-9][a-z0-9-]*)"', block))
    missing = sorted(w for w in want if w not in have)
    assert not missing, f"the group code reaches for ids that do not exist: {missing}"


def test_a_and_b_are_side_by_side_in_one_card():
    """Two identical cards stacked vertically is the opposite of a comparison: you cannot
    see both sets at once, which is the only reason to have two."""
    assert 'class="gpair"' in GROUPS, "the two groups are not in a pair container"
    pair = GROUPS[GROUPS.index('class="gpair"'):]
    pair = pair[:pair.index('class="grow gactions"')]
    assert 'id="gcol-a"' in pair and 'id="gcol-b"' in pair, (
        "A and B are not both inside the pair container")
    assert GROUPS.count("<section") == 1, (
        f"the Groups pane is back to {GROUPS.count('<section')} stacked cards")


def test_the_fatal_caveat_wraps_and_the_status_pills_do_not():
    """.banner was written for the one-line pills in the specimen strip, where nowrap is
    right, then reused for the comparison's fatal caveat -- a full sentence naming the
    overlapping frames. Measured at a 1180 px window it rendered 2,206 px of text in a
    782 px card: 1,424 px of "THE TWO GROUPS SHARE PIXELS, this comparison is invalid"
    ran off the right edge unread."""
    assert re.search(r"\.banner\{[^}]*white-space:\s*nowrap", HTML), (
        "the strip pills should stay on one line")
    m = re.search(r"\.gfatal\{([^}]*)\}", HTML)
    assert m, "there is no .gfatal rule"
    assert "white-space:normal" in m.group(1).replace(" ", ""), m.group(1)
    assert "display:block" in m.group(1).replace(" ", ""), m.group(1)
    assert 'class="banner bad gfatal"' in JS, (
        "the fatal caveat does not use the class that lets it wrap")


# --- THE STORE THE CLIENT NOW DEPENDS ON ------------------------------------------------
def _post(s, path, obj):
    st, raw = s.post(path, json.dumps(obj).encode(), "application/json")
    return st, (json.loads(raw) if raw else None)


def _seed(s, name, bar):
    st, raw = s.upload(f"{name}.png", mask_png(200, 150, bar))
    assert st == 200, raw[:200]
    up = json.loads(raw)
    return up["frames"][0]["frame"] if "frames" in up else up["frame"]


def test_a_saved_collection_outlives_the_window(tmp_path):
    """The whole point of saving one. Two servers on the same data directory, because a
    store that only works while the process is up is the bug this replaces."""
    d = tmp_path / "d"
    with Server(d) as s:
        a, b = _seed(s, "ca", 30), _seed(s, "cb", 60)
        st, _ = _post(s, "/api/groups", {"name": "front set",
                                         "frames": [{"arm": "uploads", "frame": a},
                                                    {"arm": "uploads", "frame": b}]})
        assert st == 200
    with Server(d) as s:
        st, g = s.json("/api/groups")
        assert st == 200, g
        assert sorted(m["frame"] for m in g["groups"]["front set"]) == sorted([a, b])


def test_a_collection_can_be_deleted_without_touching_the_images(tmp_path):
    with Server(tmp_path / "d") as s:
        a = _seed(s, "da", 30)
        _post(s, "/api/groups", {"name": "temp", "frames": [{"arm": "uploads", "frame": a}]})
        st, g = _post(s, "/api/groups", {"name": "temp", "delete": True})
        assert st == 200 and "temp" not in g["groups"], g
        assert any(r["frame"] == a for r in s.dataset("frames")), "the frame went with it"
        assert os.path.exists(os.path.join(str(tmp_path / "d"), "uploads", f"{a}_gated.png"))


def test_saving_over_a_name_replaces_rather_than_appends(tmp_path):
    with Server(tmp_path / "d") as s:
        a, b = _seed(s, "ra", 30), _seed(s, "rb", 60)
        _post(s, "/api/groups", {"name": "set", "frames": [{"arm": "uploads", "frame": a}]})
        st, g = _post(s, "/api/groups", {"name": "set",
                                         "frames": [{"arm": "uploads", "frame": b}]})
        assert st == 200
        assert [m["frame"] for m in g["groups"]["set"]] == [b], g["groups"]["set"]


@pytest.mark.parametrize("bad", [{}, {"name": ""}, {"name": "x"}, {"name": "x", "frames": []}])
def test_a_collection_needs_a_name_and_a_member(tmp_path, bad):
    with Server(tmp_path / "d") as s:
        _seed(s, "n", 30)
        st, _ = _post(s, "/api/groups", bad)
        assert st == 400, (bad, st)
