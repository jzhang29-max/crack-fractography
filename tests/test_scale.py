#!/usr/bin/env python3
"""The physical constants, pinned against the geometry that anchors them.

WHY THIS FILE EXISTS. A mutation audit set `scale.TXM_NM_PER_PX` from 29.24 to 292.4 -- a
10x error in the single physical constant of the entire TXM arm -- and all 277 tests passed.
Every micrometre quantity on that arm flows through it: area_um2, mean and max width in um,
mean crack length, total crack length, P20, P21, area_analysed_mm2, the E562 interval's
units, and the width comparison the read-out prints as a finding. None of it was pinned.

The constant appeared in tests/ five times before this file, and never as an assertion: four
were values HANDED IN to a function under test (`C.speck_threshold_px(29.24)`, a loop over
nm values, `_txm_like(nm=29.24)`) and one asserted the literal "29.24 nm/px" appears inside a
basis STRING. A test that hands in the right number cannot notice that the shipped one is
wrong, and a test that greps a sentence for a substring is checking the sentence.

So this pins the value, and then pins its DERIVATION, so that a future reader can tell the
difference between "someone changed a number" and "the instrument changed".
"""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, REPO)

import scale  # noqa: E402


def test_the_txm_scale_constant_is_the_value_the_corpus_was_measured_at():
    """29.24 nm/px. Every published TXM number in this project rests on it."""
    assert scale.TXM_NM_PER_PX == 29.24, (
        f"TXM_NM_PER_PX is {scale.TXM_NM_PER_PX}, not 29.24. Every micrometre quantity on "
        "the TXM arms -- widths, lengths, P20, P21, area_um2, area_analysed_mm2 and the "
        "E562 interval's units -- scales linearly with this, and area_um2 scales with its "
        "square. If the instrument really changed, re-measure both TXM arms and update "
        "this test with the new derivation; do not simply widen it.")


def test_the_txm_scale_matches_the_tile_geometry_that_anchors_it():
    """The constant is anchored by tile geometry, so check the geometry -- on BOTH axes.

    scale.py records the anchor as "9x5 tiles of a 30 um window at 0.35 overlap". Tiles step
    by (1 - overlap) of a field, so the mosaic spans
        short axis: 30 * (1 + 4 * 0.65) = 108.0 um
        long  axis: 30 * (1 + 8 * 0.65) = 186.0 um
    and the corpus contains a size family on each: the 3651-3752 px family (n = 13, median
    3694) is 108.01 um at 29.24 nm/px, and the 6349-6372 px family (n = 2, median 6360.5) is
    185.98 um. Two axes, two different families, both within 0.02%.

    THE TWO ARE NOT EQUALLY WEIGHTED and should not be read as two independent confirmations
    of equal strength: the short axis carries n = 13 frames, the long axis n = 2. The long
    one is robust in the sense that either member alone agrees (185.64 um, -0.19%, and
    186.32 um, +0.17%), but it is two frames. The n is printed beside each below.

    THE FIRST VERSION OF THIS TEST CHEATED, and a peer session caught it. It used 3703 px,
    described as "the modal mosaic height". 3703 occurs TWICE in 71 frames; the mode is 1706.
    The corpus has 62 distinct heights in seven families, and picking 3899/3900 -- an equally
    real mosaic size -- gives 114.0 um, +5.6% off, which would have FAILED the test's own
    +-0.5% tolerance. So the tolerance was tighter than the spread of defensible anchors, and
    the 29.0 mutation it "caught" failed because of the selection rather than the geometry.
    That is the same hazard-versus-accident error this suite calls out elsewhere: an
    assertion pinned to a convenient pick rather than to the property.

    WHAT THIS TEST CAN AND CANNOT DO, measured against the family medians. It excludes
    order-of-magnitude errors (292.4 -> +900%, 2.924 -> -90%) and errors of about 2.5% or more
    (30.0 -> +2.61%). It CANNOT adjudicate 29.0 (-0.81%) or 28.8 (-1.49%) against 29.24,
    because those sit inside the family's own -1.15%..+1.58% spread of frame heights. The
    exact pin in the test above is what catches small drift; this one establishes that the
    number means something physical. Neither alone is sufficient and the pair is not
    circular.
    """
    FIELD_UM, OVERLAP = 30.0, 0.35
    span_short = FIELD_UM * (1 + 4 * (1 - OVERLAP))
    span_long = FIELD_UM * (1 + 8 * (1 - OVERLAP))
    assert span_short == pytest.approx(108.0, abs=0.01), span_short
    assert span_long == pytest.approx(186.0, abs=0.01), span_long

    # TOLERANCE FROM THE FAMILY SPREAD, not chosen to pass. Frames inside one family differ
    # in height by up to 2.7%, so no anchor drawn from it can be held tighter than that.
    FAMILY_TOL = 0.02
    for name, median_px, span_um in (("short axis, 3651-3752 px family, n=13", 3694, span_short),
                                     ("long axis, 6349-6372 px family, n=2", 6360.5, span_long)):
        implied = median_px * scale.TXM_NM_PER_PX / 1000.0
        assert implied == pytest.approx(span_um, rel=FAMILY_TOL), (
            f"{name}: {median_px} px at {scale.TXM_NM_PER_PX} nm/px is {implied:.2f} um, but "
            f"the recorded tile geometry spans {span_um:.2f} um -- "
            f"{100 * (implied - span_um) / span_um:+.2f}%, outside the +-{100 * FAMILY_TOL:.0f}% "
            "the family's own height spread permits. The constant and its stated anchor "
            "disagree physically.")


def test_the_family_medians_this_derivation_uses_are_still_in_the_corpus():
    """The anchors above are two hardcoded medians. Pin them to the data that produced them.

    Without this, the derivation test is two literals multiplied by a third, and a corpus
    that gained or lost frames could move the families out from under it while the test went
    on passing.

    THE CLUSTERING MARGIN, measured rather than asserted -- and the first version of this
    docstring got both numbers wrong AND cited the wrong quantity. Single-link clustering
    keys on CONSECUTIVE gaps, not on a family's total span. Measured over the 71 TXM heights:
    the largest consecutive gap inside any family is 28 px, the smallest gap between families
    is 147 px, and the full between-family gap list is [147, 569, 596, 623, 1112, 1298]. So
    any threshold in (28, 146] reproduces these seven families, and 120 sits in the middle of
    that window. At t = 147 the 3651-3752 and 3899-3900 families merge, the combined median
    moves to 3702, and 3694 stops being a family median -- that is the real failure mode, and
    it is 27 px above the chosen threshold rather than the 102 px the first version implied.
    The earlier docstring's "within-family spread 101" was one family's total span and its
    "between-family gap 222" appears nowhere in the data.
    """
    import json
    import statistics
    fp = os.path.join(REPO, "analysis", "out", "frames.json")
    if not os.path.exists(fp):
        pytest.skip("no dataset built")
    rows = json.load(open(fp, encoding="utf-8"))
    h = sorted(r["height_px"] for r in rows if (r.get("arm") or "") == "txm")
    if len(h) < 20:
        pytest.skip("too few TXM frames measured to recover the size families")
    fams, cur = [], [h[0]]
    for prev, nxt in zip(h, h[1:]):
        if nxt - prev > 120:
            fams.append(cur)
            cur = []
        cur.append(nxt)
    fams.append(cur)
    meds = {int(statistics.median(f)): (min(f), max(f), len(f)) for f in fams}
    for want in (3694, 6360):
        assert want in meds, (
            f"the geometry test anchors on a family median of {want} px, which is no longer "
            f"a family median in this corpus. Families now: "
            f"{ {m: v for m, v in sorted(meds.items())} }. Re-derive the anchors before "
            "changing the tolerance.")


def test_the_measured_txm_frames_all_report_that_constant():
    """And the dataset must actually carry it -- a constant nothing reaches is not a scale.

    Asserted over the measured output rather than by calling the resolver, because the
    failure worth catching is a frame that reached frames.json with some OTHER nm/px: a
    user_scale.json override, a stale record from before the constant existed, or a second
    TXM arm wired to a different resolver.
    """
    import json
    fp = os.path.join(REPO, "analysis", "out", "frames.json")
    if not os.path.exists(fp):
        pytest.skip("no dataset built")
    rows = json.load(open(fp, encoding="utf-8"))
    txm = [r for r in rows if (r.get("arm") or "").startswith("txm")]
    if not txm:
        pytest.skip("no TXM frames measured in this checkout")
    wrong = [(r["arm"], r["frame"], r.get("nm_per_px")) for r in txm
             if r.get("nm_per_px") != scale.TXM_NM_PER_PX]
    assert not wrong, (
        f"{len(wrong)} of {len(txm)} TXM frames report a nm/px that is not "
        f"{scale.TXM_NM_PER_PX}: {wrong[:4]}")
    # One magnification per determination is the premise the whole TXM arm rests on, and
    # the read-out prints it as a finding. Pin it here too, from the data.
    assert len({r.get("nm_per_px") for r in txm}) == 1, (
        "the TXM frames no longer sit at a single magnification, so the finding "
        "'every frame is scaled at one magnification' is false and width comparisons "
        "across those frames are no longer like-for-like")
