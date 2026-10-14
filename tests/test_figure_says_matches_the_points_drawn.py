#!/usr/bin/env python3
"""A statement under a chart must be computed from EXACTLY the points above it.

That is the one rule app/figures.py and analysis/conclusions.for_figure exist to keep, and
the `_drawn_rows` channel in figures.build is the mechanism: a panel builder that draws a
SUBSET hands the subset back so the conclusions engine sees what the reader sees.
`_stage_panels` does that. `_by_specimen` does not -- it drops thin specimens out of its
own `g` dict and returns the full pre-filter `rows`, so the sentence under a box plot is
computed over specimens whose boxes are not on the figure.

Measured on the real corpus before this test existed, driving the live endpoints:

  * txm / box_by_specimen / area_fraction at the DEFAULT min_frames=3 drew 4 boxes and the
    statement under it read "5 specimens, median Crack area fraction from 0 (260618_b3) to
    0.1751 (260618_b2)". 260618_b3 holds one field, is hidden by the default filter, and is
    the low extreme the span was computed from -- a named endpoint the reader cannot see.
  * sem/gated at min_frames=11 drew ONE box and still carried "Specimen differences exceed
    the variation inside one specimen. 14 specimens. Between the extreme medians: 0.1815"
    naming MAR_AmbB_HIP and MAR_Amb_Cast, neither of them drawn. A between-specimen verdict
    under a one-box chart.
  * The statements were byte-identical across min_frames 3, 6, 9, 10, 11 and across
    include_thin true/false. The filter moved the picture and never moved the words.

These tests drive /api/figure.svg and /api/figure/says over real HTTP and compare the two
answers to each other, because a unit call that hands `rows` in and asserts they come back
cannot see this: the defect IS which rows travel.
"""
import json
import os
import re
import sys
import urllib.parse

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server                                        # noqa: E402

ARM = "sem/gated"


def _frames():
    """One arm, four specimens. THREE ARE FAT AND ONE IS THIN, and the thin one holds the
    minimum, so dropping it must move both the span and the specimen count. A thin specimen
    in the MIDDLE of the range would let a broken implementation pass on the span.

    Two frames per field (CBS and ETD on a `_NN_DET` stem) so the field collapse runs too:
    the bug and the collapse share the same return path.
    """
    rows = []
    plan = {"FAT_LOW": (4, 0.040), "FAT_MID": (4, 0.080), "FAT_HIGH": (4, 0.120),
            "THIN_MIN": (2, 0.001)}
    for spec, (n_fields, base) in plan.items():
        for i in range(n_fields):
            for det in ("CBS", "ETD"):
                rows.append({
                    "frame": f"{spec}_{i:02d}_{det}", "arm": ARM, "specimen": spec,
                    "area_fraction": base + 0.002 * i,
                    "scale_known": False, "nm_per_px": None,
                    "largest_share_of_area": 0.5, "n_cracks_measured": 3,
                    "speck_count": 0, "crack_area_px": 100, "n_junctions": 1,
                    "mean_width_px_median": 2.0, "censored_share": 0.0,
                    "censored_share_by_area": 0.0, "censored_share_by_length": 0.0,
                })
    return rows


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    d = tmp_path_factory.mktemp("says")
    with open(os.path.join(d, "frames.json"), "w", encoding="utf-8") as fh:
        json.dump(_frames(), fh)
    for name in ("cracks", "specimens"):
        with open(os.path.join(d, f"{name}.json"), "w", encoding="utf-8") as fh:
            json.dump([], fh)
    with Server(d) as s:
        yield s


def _q(**kw):
    return urllib.parse.urlencode(kw)


def _drawn(srv, **kw):
    """The specimen names the SVG actually drew a mark for, read off the figure itself.

    From the <title> on each box/bar -- the renderer writes one per mark and nowhere else,
    so this counts marks rather than trusting a count the builder reports about itself.
    """
    st, raw = srv.get("/api/figure.svg?" + _q(**kw))
    assert st == 200, (st, raw[:300])
    return sorted(re.findall(r"<title>([^<:]+): (?:median|mean) ", raw.decode()))


def _says(srv, **kw):
    st, j = srv.json("/api/figure/says?" + _q(**kw))
    assert st == 200, (st, j)
    return j["statements"]


@pytest.mark.parametrize("kind", ["box_by_specimen", "bar_by_specimen"])
def test_the_statement_counts_the_specimens_that_were_drawn(srv, kind):
    """"N specimens" in the basis must be the number of boxes above it, not the number of
    specimens in the arm."""
    kw = dict(arm=ARM, kind=kind, y="area_fraction", min_frames=3)
    drawn = _drawn(srv, **kw)
    assert drawn == ["FAT_HIGH", "FAT_LOW", "FAT_MID"], drawn        # THIN_MIN is hidden
    for st in _says(srv, **kw):
        for n in re.findall(r"(\d+) specimens", st["basis"]):
            assert int(n) == len(drawn), (
                f"{kind}: basis says {n} specimens, the figure drew {len(drawn)} "
                f"({drawn}). Statement: {st['text']!r} / {st['basis']!r}")


def test_a_hidden_specimen_is_never_named_as_an_extreme(srv):
    """The thin specimen holds the minimum. If it is not on the chart it cannot be the
    endpoint of a span stated under the chart."""
    kw = dict(arm=ARM, kind="box_by_specimen", y="area_fraction", min_frames=3)
    drawn = _drawn(srv, **kw)
    assert "THIN_MIN" not in drawn
    for st in _says(srv, **kw):
        assert "THIN_MIN" not in st["basis"], (
            "a statement names a specimen the figure does not draw: " + st["basis"])
        assert "THIN_MIN" not in st["text"], st["text"]


def test_dropping_a_point_from_the_chart_changes_the_statement(srv):
    """The test the module's own docstring implies: move the filter, the words must move.

    include_thin=true adds THIN_MIN, which is the new minimum, so the span and the count
    both have to change. Identical statements mean the words were computed off a row set
    the filter never touched.
    """
    base = dict(arm=ARM, kind="box_by_specimen", y="area_fraction", min_frames=3)
    off = _says(srv, **base, include_thin="false")
    on = _says(srv, **base, include_thin="true")
    assert _drawn(srv, **base, include_thin="false") != \
        _drawn(srv, **base, include_thin="true"), "the fixture no longer hides anything"
    assert [s["basis"] for s in off] != [s["basis"] for s in on], (
        "include_thin changed the figure and not one statement under it:\n"
        + "\n".join(s["basis"] for s in off))


def test_raising_min_frames_changes_the_statement(srv):
    """Same rule through the other filter. At min_frames=5 nothing qualifies, so the
    figure refuses; at 4 only the three fat specimens do; at 3 the same three. The
    interesting step is 3 -> 4 -> refusal, and the words must track it."""
    base = dict(arm=ARM, kind="box_by_specimen", y="area_fraction", include_thin="false")
    st, raw = srv.get("/api/figure.svg?" + _q(**base, min_frames=5))
    assert st == 400 and b"include thin" in raw, (st, raw[:200])
    # Now a filter that really does change the drawn set: the thin one in, then out.
    inc = dict(base, include_thin="true")
    assert len(_drawn(srv, **inc, min_frames=2)) == 4
    assert len(_drawn(srv, **dict(base, min_frames=3))) == 3
    a = _says(srv, **inc, min_frames=2)
    b = _says(srv, **dict(base, min_frames=3))
    assert [s["basis"] for s in a] != [s["basis"] for s in b], (
        "four boxes and three boxes produced identical prose")


def test_a_scatter_of_a_field_against_itself_is_refused_or_flagged(srv):
    """x == y is an identity, not a relationship. Measured on the real corpus it drew and
    asserted "Crack area fraction rises with Crack area fraction", rho = +1.000,
    p = 0.0000, at level 'warn' -- the module flags crack_area_px vs area_fraction as
    algebraic but not the identity pair, which is the strongest algebraic pair there is."""
    kw = dict(arm=ARM, kind="scatter", x="area_fraction", y="area_fraction")
    st, raw = srv.get("/api/figure.svg?" + _q(**kw))
    if st >= 400:
        return                                      # refusing it outright is also correct
    sts = _says(srv, **kw)
    assert any(s["level"] == "bad" and "definition" in s["basis"] for s in sts), (
        "a field plotted against itself drew with no algebraic warning: "
        + json.dumps([s["text"] for s in sts]))
