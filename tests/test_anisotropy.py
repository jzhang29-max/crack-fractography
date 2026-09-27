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
        f"isotropic input reported anisotropy: R={s['rose_R']} null95={s['rose_R_null95']}")
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
    assert a["rose_R_null95"] == b["rose_R_null95"]


def test_the_null_is_described_with_its_draw_count():
    _, s = skeleton_segments(_lines([30] * 8))
    assert str(ROSE_NULL_DRAWS) in s["rose_null"]
    assert "observed segment lengths" in s["rose_null"]


def test_an_empty_mask_reports_no_verdict_rather_than_a_false_one():
    _, s = skeleton_segments(np.zeros((100, 100), bool))
    assert s["rose_R"] is None and s["rose_beats_null"] is None
