#!/usr/bin/env python3
"""The orientation rose needs a null, and this is the control that proves it.

A bare resultant R is uninterpretable on this corpus. Measured independently: a synthetic
mask of perfectly straight lines at UNIFORM RANDOM angles returns R = 0.267-0.285, at or
above the corpus median R of 0.257. So a lopsided-looking rose is the default appearance of
randomness here, and without a null every frame reads as "preferentially oriented".
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "analysis"))
from segments import ROSE_NULL_DRAWS, skeleton_segments   # noqa: E402


def _lines(angles, L=160, size=600, seed=0):
    rng = np.random.default_rng(seed)
    m = np.zeros((size, size), bool)
    for a in angles:
        cx, cy = rng.uniform(0.25, 0.75, 2) * size
        dx, dy = np.cos(np.deg2rad(a)), np.sin(np.deg2rad(a))
        for t in np.linspace(-L / 2, L / 2, int(L * 3)):
            x, y = int(cx + t * dx), int(cy + t * dy)
            if 1 <= x < size - 1 and 1 <= y < size - 1:
                m[y - 1:y + 2, x - 1:x + 2] = True
    return m


def test_an_isotropic_mask_does_not_beat_its_own_null():
    """THE negative control. Without this the whole statistic is decoration."""
    rng = np.random.default_rng(1)
    _, s = skeleton_segments(_lines(rng.uniform(0, 180, 24)))
    assert s["rose_beats_null"] is False, (
        f"isotropic input reported anisotropy: R={s['rose_R']} null95={s['rose_R_null']}")
    # And the point of the control: its R is NOT near zero, so R alone would over-read.
    assert s["rose_R"] > 0.05, "if R were ~0 for random input the null would be unnecessary"


def test_a_genuinely_oriented_mask_beats_the_null_and_recovers_the_angle():
    rng = np.random.default_rng(1)
    _, s = skeleton_segments(_lines(rng.normal(35, 6, 24)))
    assert s["rose_beats_null"] is True, s
    assert abs(s["rose_theta_deg"] - 35) < 12, s["rose_theta_deg"]


def test_angles_are_axial_so_10_and_170_do_not_cancel():
    """A crack has an axis, not a direction. On raw angles these two nearly cancel; on
    doubled angles they reinforce, which is the correct treatment."""
    _, s = skeleton_segments(_lines([8] * 12 + [172] * 12))
    assert s["rose_beats_null"] is True, (
        f"near-parallel cracks read as random: R={s['rose_R']}")
    assert s["rose_theta_deg"] < 25 or s["rose_theta_deg"] > 155, s["rose_theta_deg"]


def test_the_null_is_deterministic():
    """A frame's verdict must not change between runs."""
    m = _lines([20, 40, 60, 80, 100, 120])
    a = skeleton_segments(m)[1]
    b = skeleton_segments(m)[1]
    assert a["rose_R_null"] == b["rose_R_null"]


def test_the_null_is_described_with_its_draw_count():
    _, s = skeleton_segments(_lines([30] * 8))
    assert str(ROSE_NULL_DRAWS) in s["rose_null"]
    assert "observed segment lengths" in s["rose_null"]


def test_an_empty_mask_reports_no_verdict_rather_than_a_false_one():
    _, s = skeleton_segments(np.zeros((100, 100), bool))
    assert s["rose_R"] is None and s["rose_beats_null"] is None


# --- the rose CHART must carry the null, not just the read-out -----------------------
def _appjs():
    import os
    return open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "app", "static", "app.js")).read()


def test_the_rose_chart_draws_its_own_null():
    """rose_R_null was computed on every frame and no pixel of the chart used it, so a
    reader saw a lopsided rose and concluded "preferentially oriented" every time -- which
    is the exact failure the null exists to prevent. A synthetic mask of straight lines at
    uniform random angles returns R = 0.267-0.285, at or above this corpus's median R."""
    js = _appjs()
    i = js.index("function rose(")
    body = js[i:js.index("/* -----", i)]
    for needed in ("rose_beats_null", "rose_R_null", "rose_R"):
        assert needed in body, f"the rose chart never reads {needed}"
    assert "Not distinguishable from random" in body, "no on-chart verdict when it fails"
    # Identity is never colour alone: the muting must be accompanied by the words.
    assert "stroke-dasharray" in body, "no reference ring for the wedge lengths"


def test_every_rose_call_passes_a_frame_record_that_is_in_scope():
    """rose(hist) with no second argument loses the verdict and the null with no error --
    the chart still draws, and it draws the thing the null exists to prevent. This is the
    same failure raBadge had, so it gets the same guard: the argument must be resolvable in
    the enclosing function, not merely present."""
    import re
    js = _appjs()
    fn, params, bad = None, [], []
    for ln in js.splitlines():
        m = re.match(r"(?:async )?function (\w+)\(([^)]*)\)", ln)
        if m:
            fn, params = m.group(1), [x.strip().split(" =")[0]
                                      for x in m.group(2).split(",") if x.strip()]
        if re.search(r"(?<![\w.])rose\(", ln) and "function rose(" not in ln:
            call = re.search(r"rose\(\s*[\w.]+\s*,\s*(\w+)\s*\)", ln)
            if not call:
                bad.append(f"{fn}: rose() called with no frame record")
                continue
            name = call.group(1)
            if name not in params and f"const {name}" not in js and f"let {name}" not in js:
                bad.append(f"{fn}: passes {name!r}, which is not in scope there")
    assert not bad, "rose called without a usable frame record: " + "; ".join(bad)


def test_the_orientation_gate_delivers_the_error_rate_it_claims():
    """A verdict whose realised false-positive rate is double its nominal one is a verdict
    that overstates itself, and this one was: the shipped 95th-percentile threshold called
    10 of 108 isotropic-by-construction masks "oriented" -- 9.3% against a nominal 5%.

    The cause is not lattice bias (the measured angles pass a uniformity chi-square on the
    same input). It is that the null draws an independent direction per skeleton branch
    while branches are NOT independent: one crack fragments into several that all inherit
    its direction, so the observed resultant is built from fewer effective directions than
    the null assumes.

    Calibrated rather than assumed, which is why this test builds the isotropic input and
    counts. Kept small enough to run in the suite; the full 108-mask calibration is in the
    ROSE_NULL_PCT docstring.
    """
    import math
    import numpy as np
    import segments as S

    rng = np.random.default_rng(99)
    fired = total = 0
    for nlines, width in ((30, 1), (50, 2), (70, 3)):
        for _ in range(6):
            im = np.zeros((520, 520), bool)
            for _ in range(nlines):
                th = rng.uniform(0, math.pi)
                L = rng.integers(40, 170)
                cx, cy = rng.integers(60, 460), rng.integers(60, 460)
                for t in range(-L // 2, L // 2):
                    x = int(cx + t * math.cos(th)); y = int(cy + t * math.sin(th))
                    if width <= x < 520 - width and width <= y < 520 - width:
                        im[y - width:y + width + 1, x - width:x + width + 1] = True
            _, s = S.skeleton_segments(im)
            if s.get("rose_beats_null") is None:
                continue
            total += 1
            fired += bool(s["rose_beats_null"])

    assert total >= 12, f"only {total} usable masks; the calibration is not measuring"
    rate = fired / total
    # Conservative side only. The point is that the stated level and the delivered level
    # agree in the safe direction, not that they agree exactly at this sample size.
    assert rate <= 0.12, (
        f"the orientation gate fired on {fired} of {total} isotropic masks "
        f"({100 * rate:.0f}%). It must be conservative against its nominal level; the "
        f"95th percentile measured 9.3% and was replaced by ROSE_NULL_PCT = "
        f"{S.ROSE_NULL_PCT}.")


def test_the_null_says_which_percentile_it_used():
    """It said "95th percentile" while the code moved to 99. A verdict's stated basis has
    to track the threshold it actually applied."""
    import numpy as np
    import segments as S
    bar = np.zeros((200, 400), bool); bar[100:103, 40:360] = True
    _, s = S.skeleton_segments(bar)
    assert s["rose_null_pct"] == S.ROSE_NULL_PCT
    assert f"{S.ROSE_NULL_PCT}th percentile" in s["rose_null"]
