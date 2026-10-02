#!/usr/bin/env python3
"""The orientation rose needs a null, and this is the control that proves it.

A bare resultant R is uninterpretable on this corpus. Measured independently: a synthetic
mask of perfectly straight lines at UNIFORM RANDOM angles returns R = 0.267-0.285, at or
above the corpus median R of 0.257. So a lopsided-looking rose is the default appearance of
randomness here, and without a null every frame reads as "preferentially oriented".

MUTATION AUDIT, 2026-10-01. Seven guards in this file were shown to pass while the
behaviour they claim to protect was broken. The pattern was the same in six of the seven:
they asserted on PROSE (the sentence in rose_null says "1000 draws", the sentence in app.js
says "Not distinguishable from random") or on a CONCLUSION (this mask does not beat its
null) rather than on the quantity. Every repair below replaces the prose check with a
hand-computed property, and each one is recorded against the mutation that defeated its
predecessor. The prose assertions are kept -- a sentence that lies is still a bug -- they
are just no longer the only teeth.

THE INDEPENDENT INSTRUMENT the repairs use, stated once here because five of them share it.
The null is |sum_i w_i exp(i phi_i)| with w_i = L_i / sum(L) and phi_i uniform on the
circle. That is a 2-D random walk, so C = sum w_i cos phi_i and S = sum w_i sin phi_i are
each zero-mean with variance (1/2) sum w_i^2, and R^2 = C^2 + S^2 is exponential:

    P(R > r) = exp(-r^2 / sum(w^2))   =>   R_p = sqrt(sum(w^2) * ln(1/(1-p)))

(Rayleigh; Mardia & Jupp, Directional Statistics, ch. 4.) That closed form is computed here
in `math` from the per-segment lengths the function REPORTS, so it is independent of the
permutation code it is checking: it knows nothing about the seed, the draw count or the
percentile call. On the four isotropic calibration fixtures below the shipped null tracks it
to a mean 2.2% relative error. The approximation needs sum(w^2) << 1, which is why those
fixtures all carry 20+ directional branches; at one branch the walk degenerates and the
exact answer is 1.0 instead, which is the anchor the determinism guard uses.
"""
import math
import os
import re
import shutil
import subprocess
import sys
import textwrap

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPJS = os.path.join(REPO, "app", "static", "app.js")
sys.path.insert(0, os.path.join(REPO, "analysis"))
from segments import (MIN_DIRECTIONAL_PX, ROSE_NULL_DRAWS,   # noqa: E402
                      ROSE_NULL_PCT, skeleton_segments)


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


#: Twelve angles spread over the half circle, none of them on a lattice direction.
_ANG = [7, 23, 38, 52, 67, 83, 98, 113, 131, 147, 162, 176]


def _tiles(specs, tile=220, cols=4):
    """One ISOLATED straight segment per tile, so the branch count and the length
    distribution are known from the construction rather than from the skeletoniser.

    `_lines` scatters its lines over one frame, so they cross, and crossings fragment the
    skeleton -- 24 drawn lines come back as 57 branches of unpredictable length. Several
    repairs below need a fixture whose sum(w^2) is set deliberately, so this one puts each
    segment in its own cell of a grid where nothing can touch anything else.
    """
    rows = (len(specs) + cols - 1) // cols
    m = np.zeros((rows * tile, cols * tile), bool)
    for k, (length, ang) in enumerate(specs):
        r, c = divmod(k, cols)
        cy, cx = r * tile + tile // 2, c * tile + tile // 2
        dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        for t in np.linspace(-length / 2, length / 2, int(length * 4) + 1):
            x, y = int(round(cx + t * dx)), int(round(cy + t * dy))
            m[y - 1:y + 2, x - 1:x + 2] = True
    return m


#: Same branch COUNT (12), deliberately different length concentration. EQUAL puts an equal
#: share on each branch, so sum(w^2) = 1/12 = 0.0833; SKEWED gives one branch 190 px against
#: eleven of 26 px, so sum(w^2) = 0.185, 2.2x larger. A null that carries "the observed
#: segment lengths" must separate these two; a null that ignores the lengths cannot, because
#: with uniform weights the two fixtures are the same 12-vector problem.
def _equal_lengths_mask():
    return _tiles([(120, a) for a in _ANG])


def _skewed_lengths_mask():
    return _tiles([(190, _ANG[0])] + [(26, a) for a in _ANG[1:]])


def _directional(segs):
    """The branches the directional statistics are actually computed on."""
    return [s for s in segs if s["length_px"] >= MIN_DIRECTIONAL_PX]


def _hand_weights(segs):
    L = np.array([s["length_px"] for s in _directional(segs)], float)
    return L / L.sum()


def _hand_axial_R(segs):
    """The length-weighted axial resultant, recomputed here from the reported branches.

    Doubled angles, because a crack has an axis and not a direction. This is the definition,
    written out independently of the implementation; it uses only `angle_deg` and
    `length_px`, which the function reports per branch.
    """
    k = _directional(segs)
    w = _hand_weights(segs)
    two = np.deg2rad(2.0 * np.array([s["angle_deg"] for s in k], float))
    return float(np.hypot((w * np.cos(two)).sum(), (w * np.sin(two)).sum()))


def _hand_null_quantile(segs, pct):
    """The Rayleigh closed form for the pct-th percentile of the null. See module docstring.

    Independent instrument: `math` and the reported segment lengths, nothing from
    segments.py's permutation block.
    """
    sum_w2 = float((_hand_weights(segs) ** 2).sum())
    return math.sqrt(sum_w2 * math.log(1.0 / (1.0 - pct / 100.0)))


#: Four ISOTROPIC fixtures at four densities, 20-40 lines each. Cached because two guards
#: share them and each one costs a skeletonisation.
_CALIB = []


def _calibration():
    if not _CALIB:
        for seed, n, length in ((3, 20, 170), (4, 26, 150), (5, 34, 130), (6, 40, 110)):
            ang = np.random.default_rng(seed).uniform(0, 180, n)
            _CALIB.append(skeleton_segments(_lines(ang, L=length, size=620, seed=seed)))
    return _CALIB


def _null_error_against_closed_form(pct):
    """Mean |reported R_null / Rayleigh(pct) - 1| over the four calibration fixtures."""
    errs = [abs(s["rose_R_null"] / _hand_null_quantile(segs, pct) - 1.0)
            for segs, s in _calibration()]
    return sum(errs) / len(errs)


def test_an_isotropic_mask_does_not_beat_its_own_null():
    """THE negative control. Without this the whole statistic is decoration.

    REPAIRED after the mutation audit. The old guard asserted only the CONCLUSION -- that
    this mask reports rose_beats_null False and an R above 0.05 -- and replacing
    `w = L / L.sum()` with uniform weights left both of those true, so the whole file passed
    with a rose that was no longer length-weighted and a null that no longer carried the
    observed lengths. A verdict of "not oriented" is also what a null that NEVER fires
    returns: R_null = 0.999 passed this guard too.

    So the control keeps its conclusion and gains the two things that make it a control:
    rose_R is checked against the axial resultant recomputed by hand from the reported
    branches, and the null is checked to be non-vacuous by the paired positive case on the
    same fixture family. Neither the muting of the weights nor a null pinned near 1 survives.
    """
    segs, s = skeleton_segments(_lines(np.random.default_rng(1).uniform(0, 180, 24)))

    # The reported R is the quantity it claims to be: length-weighted, axial, on doubled
    # angles. Computed here from angle_deg and length_px alone.
    assert s["rose_R"] == pytest.approx(_hand_axial_R(segs), abs=2e-3), (
        f"rose_R is {s['rose_R']}; the length-weighted axial resultant of the "
        f"{len(_directional(segs))} directional branches is {_hand_axial_R(segs):.4f}")

    assert s["rose_beats_null"] is False, (
        f"isotropic input reported anisotropy: R={s['rose_R']} null95={s['rose_R_null']}")
    # And the point of the control: its R is NOT near zero, so R alone would over-read.
    assert s["rose_R"] > 0.05, "if R were ~0 for random input the null would be unnecessary"

    # The positive control, which is what makes the negative one evidence rather than a
    # statement that the gate is welded shut.
    osegs, o = skeleton_segments(_lines(np.random.default_rng(1).normal(35, 6, 24)))
    assert o["rose_beats_null"] is True, (
        "the null never fires, so 'does not beat its null' above is vacuous: an oriented "
        f"mask with R={o['rose_R']} also failed to beat null={o['rose_R_null']}")
    assert o["rose_R"] == pytest.approx(_hand_axial_R(osegs), abs=2e-3), o["rose_R"]
    assert o["rose_R"] > s["rose_R"], (o["rose_R"], s["rose_R"])


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


#: Child process for the determinism guard. Perturbs the global numpy RNG and runs under a
#: different PYTHONHASHSEED before measuring, so a null seeded from ambient state cannot
#: look reproducible.
_DETERMINISM_CHILD = textwrap.dedent("""
    import sys
    import numpy as np
    sys.path.insert(0, sys.argv[1])
    np.random.seed(int(sys.argv[3]))
    np.random.random(int(sys.argv[3]) % 97 + 1)
    from segments import skeleton_segments
    sys.stdout.write(repr(skeleton_segments(np.load(sys.argv[2]))[1]["rose_R_null"]))
""")


def test_the_null_is_deterministic(tmp_path):
    """A frame's verdict must not change between runs.

    REPAIRED after the mutation audit. The old guard called skeleton_segments twice on one
    mask in ONE process and compared rose_R_null to itself. Replacing the whole percentile
    with the constant `R_null = 0.2` passed it -- a constant is perfectly reproducible, and
    the guard could not tell a deterministic null from no null at all. It also could not see
    the determinism failure that actually threatens this code, which is a null seeded from
    ambient process state: same process, same answer, different run, different verdict.

    Three assertions now. (1) A fixture with exactly ONE directional branch must report
    R_null == 1.0 EXACTLY, because with w = [1.0] every draw gives |exp(i phi)| = 1 and
    every percentile of a vector of ones is one -- an arithmetic identity, so any constant
    other than 1.0 dies here. (2) Two fixtures with different length concentration must
    report different nulls, which no constant can do. (3) Reproducibility is measured ACROSS
    PROCESSES, under two different PYTHONHASHSEEDs and two different global numpy seeds, so
    `default_rng(hash(...))` or a null drawn from `np.random` is caught where the old
    in-process repeat was blind to it.
    """
    # (1) The degenerate case, where the null's value is arithmetic rather than empirical.
    one = _tiles([(150, 33)])
    segs, s = skeleton_segments(one)
    assert len(_directional(segs)) == 1, _directional(segs)
    assert s["rose_R_null"] == 1.0, (
        "a null over a single branch carries all the weight on one unit vector, so every "
        f"draw has modulus 1 and every percentile of it is 1.0; got {s['rose_R_null']}")
    assert s["rose_beats_null"] is False, "R == R_null == 1 is not 'beats'"

    # (2) A constant is deterministic and worthless; the null must respond to its input.
    _, eq = skeleton_segments(_equal_lengths_mask())
    _, sk = skeleton_segments(_skewed_lengths_mask())
    assert sk["rose_R_null"] > eq["rose_R_null"], (
        "the null did not move when the length distribution did, so it is not being "
        f"computed from the input: equal={eq['rose_R_null']} skewed={sk['rose_R_null']}")

    # (3) The determinism that matters: between RUNS, not between calls.
    npy = str(tmp_path / "mask.npy")
    np.save(npy, _lines([20, 40, 60, 80, 100, 120]))
    seen = []
    for hashseed, globalseed in (("1", "17"), ("524287", "900001")):
        env = dict(os.environ, PYTHONHASHSEED=hashseed)
        out = subprocess.run(
            [sys.executable, "-c", _DETERMINISM_CHILD,
             os.path.join(REPO, "analysis"), npy, globalseed],
            capture_output=True, text=True, env=env)
        assert out.returncode == 0, out.stderr
        seen.append(out.stdout.strip())
    assert seen[0] == seen[1], (
        "rose_R_null changed between two processes that differ only in PYTHONHASHSEED and "
        f"in the global numpy seed, so the null is drawing from ambient state: {seen}")
    assert seen[0] not in ("None", ""), seen


def test_the_null_is_described_with_its_draw_count():
    """The sentence in rose_null says "uniform random directions with the observed segment
    lengths, 1000 draws". Both halves of that are now measured.

    REPAIRED after the mutation audit. The old guard was `str(ROSE_NULL_DRAWS) in
    s["rose_null"]` and `"observed segment lengths" in s["rose_null"]` -- two substring
    tests on a sentence that is itself an f-string over ROSE_NULL_DRAWS, so the sentence
    cannot disagree with the constant no matter what the code does with it. Cutting the draw
    count to `size=(7, len(w))` passed. Replacing `w = L / L.sum()` with uniform weights,
    which deletes the observed lengths from both the rose and the null, passed too, and so
    did the entire rest of this file.

    What is asserted now. The DRAW COUNT shows up as estimator accuracy: the 99th percentile
    of 1000 draws sits within a couple of percent of the Rayleigh closed form (measured mean
    2.2% over the four calibration fixtures), while the 99th percentile of 7 draws is barely
    the maximum of 7 and lands 41% low. The OBSERVED LENGTHS show up as sensitivity to
    sum(w^2): two fixtures with the same 12 branches but 2.2x different length concentration
    must give different nulls, and under uniform weights they give byte-identical ones.
    """
    _, s = skeleton_segments(_lines([30] * 8))
    assert str(ROSE_NULL_DRAWS) in s["rose_null"]
    assert "observed segment lengths" in s["rose_null"]

    # The draw count, as resolution. Clean: 0.022. 7 draws: 0.410. 50 draws: 0.090.
    # A constant or a different percentile also fails here, which is correct -- the
    # sentence claims all three things at once.
    mare = _null_error_against_closed_form(ROSE_NULL_PCT)
    assert mare <= 0.07, (
        f"the reported null misses its own closed form by {100 * mare:.1f}% on average "
        f"over {len(_calibration())} isotropic fixtures. {ROSE_NULL_DRAWS} draws resolve "
        f"the {ROSE_NULL_PCT}th percentile to about 2%; this is the accuracy of far fewer "
        f"draws, or of a percentile other than the one claimed.")

    # The observed lengths. Same branch count, sum(w^2) = 0.083 against 0.185.
    eq_segs, eq = skeleton_segments(_equal_lengths_mask())
    sk_segs, sk = skeleton_segments(_skewed_lengths_mask())
    assert len(_directional(eq_segs)) == len(_directional(sk_segs)) == 12, (
        len(_directional(eq_segs)), len(_directional(sk_segs)))
    w2_eq = float((_hand_weights(eq_segs) ** 2).sum())
    w2_sk = float((_hand_weights(sk_segs) ** 2).sum())
    assert w2_sk > 2.0 * w2_eq, f"fixture lost its contrast: {w2_eq:.4f} vs {w2_sk:.4f}"
    assert sk["rose_R_null"] > 1.08 * eq["rose_R_null"], (
        "two fixtures with the same number of branches and 2.2x different length "
        "concentration got the same null, so the null is NOT carrying the observed "
        f"segment lengths its own description claims: equal={eq['rose_R_null']} "
        f"skewed={sk['rose_R_null']}")


def test_an_empty_mask_reports_no_verdict_rather_than_a_false_one():
    """REPAIRED after the mutation audit. The old guard read two fields out of the empty
    summary -- rose_R and rose_beats_null -- and asserted both None. Deleting "rose_R_null"
    and "rose_null_pct" from _empty_summary's key tuple passed it, which is exactly the
    KeyError regression that function's own docstring says it exists to prevent: a consumer
    reading a real field off a zero-crack frame raises instead of reading "no verdict". Two
    of sixteen fields is a subset check dressed as a shape check.

    Now: the empty summary must carry the SAME KEY SET as a summary from a mask with cracks,
    and every rose_* field in it must be None. The second half also exercises the OTHER
    no-verdict path, which the old guard never reached -- a mask that has a skeleton but no
    branch long enough to have a direction returns through the main body with R, theta and
    R_null left None, not through the early return.
    """
    _, s = skeleton_segments(np.zeros((100, 100), bool))
    assert s["rose_R"] is None and s["rose_beats_null"] is None

    _, real = skeleton_segments(_lines([30] * 8))
    # SUPERSET, not equality. The hazard is a MISSING key: a consumer reading a real field
    # off a zero-crack frame raises KeyError. An extra key is not that hazard, and
    # `_empty_summary` deliberately adds one -- `note`, carrying the reason there is no
    # verdict ("no skeleton"), which is the whole point of distinguishing "no crack" from
    # "crack with no direction". Asserting equality made the repaired guard fail on correct
    # code, which is the opposite error from the one it was repairing.
    missing = set(real) - set(s)
    assert not missing, (
        "the empty summary is missing fields a real one has, so a consumer reading a real "
        f"field off a zero-crack frame raises KeyError: {sorted(missing)}")
    assert set(s) - set(real) <= {"note"}, (
        "the empty summary gained a field beyond `note`; if that is deliberate, say here "
        f"why a zero-crack frame reports something a real frame does not: {sorted(set(s) - set(real))}")
    assert s["note"], "a no-verdict summary must say WHY there is no verdict"
    assert real["rose_R"] is not None, "fixture no longer produces a verdict to compare to"
    for k in [k for k in real if k.startswith("rose_") and k != "rose_weighted_by"]:
        assert s[k] is None, f"empty mask reported {k}={s[k]!r} instead of no verdict"

    # The second no-verdict path: branches exist but none is directional.
    stubs = _tiles([(MIN_DIRECTIONAL_PX - 9, a) for a in _ANG], tile=60)
    ssegs, st = skeleton_segments(stubs)
    assert ssegs and not _directional(ssegs), (
        f"fixture must have branches and no directional ones: "
        f"{sorted(round(x['length_px'], 1) for x in ssegs)}")
    assert st["rose_R"] is None and st["rose_R_null"] is None, st
    assert st["rose_beats_null"] is None, (
        "a mask with no branch long enough to have a direction reported a verdict: "
        f"{st['rose_beats_null']}")


# --- the rose CHART must carry the null, not just the read-out -----------------------
def _appjs():
    return open(APPJS, encoding="utf-8").read()


def _rose_body(js):
    i = js.index("function rose(")
    return js[i:js.index("/* -----", i)]


def _render_rose(hist, f):
    """Run the REAL rose() from app.js in node and return (full_svg, visible_text).

    visible_text is the text NODES only: every tag is replaced by a separator, so
    aria-label and data-tip -- which live inside tag attributes and are not paint -- cannot
    satisfy an assertion about what the chart says on its face.
    """
    import json
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    js = _appjs()
    esc = js[js.index("const esc = (v) =>"):js.index("const fmt = (v, d = 2)")]
    harness = (
        "globalThis.__out = {};\n" + esc
        + "\nfunction wire() {}\n"
          "function $(sel) { if (sel !== '#rose') return null;\n"
          "  return { set innerHTML(v) { globalThis.__out.svg = v; },\n"
          "           get innerHTML() { return globalThis.__out.svg; } }; }\n"
          "globalThis.document = { querySelector: () => null };\n"
        + _rose_body(js)
        + f"\nrose({json.dumps(hist)}, {json.dumps(f)});\n"
          "process.stdout.write(globalThis.__out.svg || '');\n")
    out = subprocess.run([node, "-e", harness], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    svg = out.stdout
    visible = " ".join(x.strip() for x in re.sub(r"<[^>]*>", "\n", svg).split("\n")
                       if x.strip())
    return svg, visible


#: A lopsided but not-significant rose: 30% of the length in one 15 deg bin, and a resultant
#: that does not reach its null. This is the appearance the null exists to caption.
_HIST = {"area_share": [0.05, 0.05, 0.10, 0.30, 0.20, 0.08,
                        0.05, 0.04, 0.04, 0.03, 0.03, 0.03],
         "bin_deg": [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165],
         "weighted_by": "segment length"}


def test_the_rose_chart_draws_its_own_null():
    """rose_R_null was computed on every frame and no pixel of the chart used it, so a
    reader saw a lopsided rose and concluded "preferentially oriented" every time -- which
    is the exact failure the null exists to prevent. A synthetic mask of straight lines at
    uniform random angles returns R = 0.267-0.285, at or above this corpus's median R.

    REPAIRED after the mutation audit. The old guard read app.js as TEXT and asserted that
    the substrings "rose_beats_null", "rose_R_null", "Not distinguishable from random" and
    "stroke-dasharray" appeared somewhere in the function body. Deleting `${verdict}` from
    the template that is actually assigned to innerHTML passed it: the verdict was still
    computed into a local, every substring was still present, and the chart shipped without
    a word of its null on it. The substrings also survive in the aria-label, which the old
    guard could not distinguish from paint.

    Now the real rose() is executed in node and the EMITTED SVG is inspected, with tags
    stripped so only text nodes count. A frame that does not beat its null must say so on
    its face and print both numbers; a frame that does must name its angle and draw the
    resultant axis; and the axis must be absent when the verdict is negative, because an
    orientation line on a rose that is indistinguishable from random is the over-read.
    """
    js = _appjs()
    body = _rose_body(js)
    for needed in ("rose_beats_null", "rose_R_null", "rose_R"):
        assert needed in body, f"the rose chart never reads {needed}"

    quiet = {"rose_R": 0.1561, "rose_R_null": 0.3218, "rose_beats_null": False,
             "rose_theta_deg": 41.0, "rose_null": "uniform random directions, 1000 draws"}
    svg, visible = _render_rose(_HIST, quiet)

    assert "Not distinguishable from random" in visible, (
        "the chart does not say on its face that this rose is not evidence; rendered text "
        f"was: {visible!r}")
    for num in ("0.1561", "0.3218"):
        assert num in visible, (
            f"{num} never reaches the page: the reader cannot see the resultant beside the "
            f"level chance reaches. rendered text: {visible!r}")
    assert "Oriented near" not in visible, visible
    # Identity is never colour alone: the muting must be accompanied by the words, and the
    # resultant axis must not be drawn when the verdict is negative.
    assert 'stroke="var(--s2)"' not in svg, (
        "the resultant axis is drawn on a rose that does not beat its null")
    assert "stroke-dasharray" in svg, "no reference ring for the wedge lengths"

    loud = dict(quiet, rose_R=0.8810, rose_beats_null=True, rose_theta_deg=35.0)
    lsvg, lvisible = _render_rose(_HIST, loud)
    assert "Oriented near 35" in lvisible, lvisible
    assert "Not distinguishable from random" not in lvisible, lvisible
    assert "0.8810" in lvisible or "0.881" in lvisible, lvisible
    assert 'stroke="var(--s2)"' in lsvg, (
        "a rose that beats its null does not draw the resultant orientation")

    # And the no-verdict frame gets no verdict rather than a fabricated one.
    _, blank = _render_rose(_HIST, {"rose_R": None, "rose_R_null": None,
                                   "rose_beats_null": None, "rose_theta_deg": None})
    assert "Not distinguishable from random" not in blank, blank
    assert "Oriented near" not in blank, blank


def _top_level_functions(js):
    """(name, params, body) for every column-0 function in app.js.

    Brace matching is not safe in this file -- it is full of template literals carrying
    `${...}` and `{` inside strings -- but every top-level function here opens at column 0
    and is closed by a line that is exactly `}`, which is checked rather than assumed.
    """
    lines = js.splitlines()
    out = []
    for i, line in enumerate(lines):
        m = re.match(r"(?:async )?function (\w+)\(([^)]*)\)\s*\{\s*$", line)
        if not m:
            continue
        end = next((k for k in range(i + 1, len(lines)) if lines[k] == "}"), None)
        assert end is not None, f"{m.group(1)} has no column-0 closing brace"
        params = [x.strip().split(" =")[0] for x in m.group(2).split(",") if x.strip()]
        out.append((m.group(1), params, "\n".join(lines[i + 1:end])))
    return out


def test_every_rose_call_passes_a_frame_record_that_is_in_scope():
    """rose(hist) with no second argument loses the verdict and the null with no error --
    the chart still draws, and it draws the thing the null exists to prevent. This is the
    same failure raBadge had, so it gets the same guard: the argument must be resolvable in
    the enclosing function, not merely present.

    REPAIRED after the mutation audit. The old guard resolved the argument name by asking
    whether `f"const {name}"` appeared ANYWHERE in app.js -- a whole-file substring search
    standing in for a scope lookup. Changing the Results-tab call to `rose(rf.orientation_
    hist_deg, el)` passed it, because `const el` is declared inside rose() itself; at
    runtime that call is a ReferenceError and the rose never draws on the Results tab at
    all. "Not merely present" was the stated intent and the check did not implement it.

    Now the name must be a parameter of the enclosing function, or declared inside THAT
    function's own body, or a module-level binding at column 0. A declaration inside some
    other function no longer counts.
    """
    js = _appjs()
    functions = _top_level_functions(js)
    assert any(n == "rose" for n, _, _ in functions), "rose() is not a top-level function"
    module_level = set(re.findall(r"^(?:const|let|var) (\w+)", js, re.M))

    spans, pos = [], 0
    for name, params, body in functions:
        start = js.index(body, pos) if body else js.index(f"function {name}(", pos)
        spans.append((start, start + len(body), name, params, body))
        pos = start

    def enclosing(offset):
        for a, b, name, params, body in spans:
            if a <= offset <= b:
                return name, params, body
        return None, [], ""

    bad, seen = [], 0
    for m in re.finditer(r"(?<![\w.])rose\(", js):
        fn, params, body = enclosing(m.start())
        if fn == "rose" or fn is None:
            continue            # the definition itself, not a call site
        seen += 1
        tail = js[m.start():js.index("\n", m.start())]
        call = re.match(r"rose\(\s*[\w.]+\s*,\s*(\w+)\s*\)", tail)
        if not call:
            bad.append(f"{fn}: {tail.strip()} -- rose() called with no frame record")
            continue
        arg = call.group(1)
        declared = re.search(r"(?:const|let|var)\s+%s\b" % re.escape(arg), body)
        if arg not in params and not declared and arg not in module_level:
            bad.append(f"{fn}: passes {arg!r}, which is not a parameter of {fn}, not "
                       f"declared in its body, and not a module-level binding")
    assert seen >= 2, f"only {seen} rose() call sites found; the scan is not reaching them"
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
    to track the threshold it actually applied.

    REPAIRED after the mutation audit. The old guard was two tautologies. `s["rose_null_pct"]
    == S.ROSE_NULL_PCT` compares the constant to itself -- the field is literally assigned
    ROSE_NULL_PCT -- and the second assertion looked for "99th percentile" inside a sentence
    that is an f-string over the same constant. Changing the threshold itself to
    `np.percentile(Rn, 50)` left the field, the sentence and this guard untouched, so the
    verdict would have shipped at a nominal 50% while announcing 99%.

    Now the percentile is MEASURED. The Rayleigh closed form gives a different predicted
    null for each candidate percentile -- the 95th is 0.81x the 99th, the 99.9th is 1.22x --
    so the one the code actually applied is identified by asking which candidate the
    reported R_null is closest to across the four isotropic fixtures. That answer must be
    the percentile the field and the sentence claim.
    """
    import segments as S

    bar = np.zeros((200, 400), bool); bar[100:103, 40:360] = True
    _, s = S.skeleton_segments(bar)
    assert s["rose_null_pct"] == S.ROSE_NULL_PCT
    assert f"{S.ROSE_NULL_PCT}th percentile" in s["rose_null"]

    candidates = sorted({50.0, 90.0, 95.0, 99.9, float(S.ROSE_NULL_PCT)})
    err = {p: _null_error_against_closed_form(p) for p in candidates}
    best = min(err, key=lambda p: err[p])
    assert best == float(S.ROSE_NULL_PCT), (
        f"the null announces the {S.ROSE_NULL_PCT}th percentile but the R_null it reports "
        f"matches the {best:g}th: mean relative error against the Rayleigh closed form was "
        + ", ".join(f"{p:g}th={err[p]:.3f}" for p in candidates))
    assert err[best] <= 0.07, (
        f"R_null is closest to the {S.ROSE_NULL_PCT}th percentile but still misses it by "
        f"{100 * err[best]:.1f}%, so the stated basis is not the applied one")
