#!/usr/bin/env python3
"""Nothing computed may be silently discarded.

segments.py produced 24 summary fields and measure.py forwarded 9. The other 15 were
calculated on every frame of every run and thrown away -- among them the anisotropy null,
which unit-tested green against skeleton_segments() and then landed on 0 of 358 frames after
a 40-minute batch, because no test exercised the path from the producer to the stored record.

That is the shape of the failure this file exists to catch: a read with no writer, or here a
writer with no reader. Unit-testing the producer in isolation cannot see it.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "analysis"))
from measure import measure_frame        # noqa: E402
from probes import line_probe            # noqa: E402
from segments import skeleton_segments   # noqa: E402


def _mask():
    m = np.zeros((400, 400), bool)
    m[190:196, 40:360] = True            # a long horizontal crack
    m[100:300, 195:201] = True           # crossing it, so there are junctions
    return m


def _reachable(obj, seen=None):
    """Every key anywhere in the nested record."""
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            out |= _reachable(v)
    return out


def test_every_segment_field_reaches_the_frame_record():
    m = _mask()
    seg = skeleton_segments(m)[1]
    rec = measure_frame(m, "probe", "sem")[1]
    reachable = _reachable(rec)
    # Nothing is renamed on the way out any more -- the one entry here was R_L_n, and R_L
    # is deleted. Reintroducing a rename means reintroducing this map, on purpose.
    RENAMED = {}
    stranded = sorted(k for k in seg
                      if k not in reachable and RENAMED.get(k) not in reachable)
    assert not stranded, (
        "computed by segments.py and never stored:\n  " + "\n  ".join(stranded))


def test_every_probe_field_reaches_the_frame_record():
    """Through the TXM path, because its scale is a constant in scale.py. Measuring an
    unscaled frame and comparing it against a scaled line_probe() call compares two
    different field sets and fails for the wrong reason -- the probe legitimately omits its
    millimetre fields when there is no nm/px."""
    m = _mask()
    rec = measure_frame(m, "Average_mosaic_260618_B2_2_1", "txm")[1]
    assert rec["scale_known"], "the TXM constant should make this scaled"
    pr = line_probe(m, nm_per_px=rec["nm_per_px"])
    reachable = _reachable(rec)
    stranded = sorted(k for k in pr if k not in reachable)
    assert not stranded, (
        "computed by probes.py and never stored:\n  " + "\n  ".join(stranded))


def test_the_anisotropy_verdict_specifically_is_in_the_record():
    """Named explicitly because this is the one that got away, and the generic check above
    would not say which field mattered if it regressed."""
    rec = measure_frame(_mask(), "probe", "sem")[1]
    seg = rec.get("segments") or {}
    for k in ("rose_R", "rose_R_null", "rose_beats_null", "rose_theta_deg", "rose_null"):
        assert k in seg, f"{k} missing from the stored record"
    assert seg["rose_beats_null"] in (True, False), seg["rose_beats_null"]


def test_an_empty_frame_still_carries_the_field_set():
    """The 8 zero-crack frames must not have a different record shape."""
    rec = measure_frame(np.zeros((80, 80), bool), "empty", "sem")[1]
    seg = rec.get("segments") or {}
    assert "rose_beats_null" in seg and seg["rose_beats_null"] is None


def test_the_readout_can_actually_see_the_anisotropy_verdict():
    """conclusions.py reads rose_beats_null at the TOP level of the frame record. Nesting it
    only under `segments` would leave the read-out permanently silent about orientation --
    and silently, because the read-out is designed to say nothing when a field is absent."""
    import conclusions
    rec = measure_frame(_mask(), "probe", "sem")[1]
    assert rec.get("rose_beats_null") in (True, False), rec.get("rose_beats_null")
    said = " ".join(s["text"] for s in conclusions.for_frame(rec))
    assert "orient" in said.lower(), f"read-out said nothing about orientation: {said!r}"


# --- a claim that a field is not shown must stay true -------------------------------
def test_nothing_is_described_as_unrendered_while_the_ui_renders_it():
    """Three times in one day a description outlived the change it described:

      - the magnification tooltip ended "and still counted in the area analysed" after
        the totals had moved off those fields;
      - the README said area_off_determination_mm2 / tcl_um_off_determination "are never
        rendered" one commit after they were put on the card;
      - stage.py still called field_max_min_ratio a "row-to-row ratio" under a docstring
        explaining at length why that name was wrong.

    The second is mechanically checkable, and it is the dangerous one: a reader who trusts
    "never rendered" will not go looking for the thing that is one pane away. So no comment
    or document may say a record field is unrendered while app.js names it.
    """
    import os
    import re
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(repo, "app", "static", "app.js"), encoding="utf-8").read()

    sources = [os.path.join(repo, "README.md")]
    for d in ("analysis", "app"):
        for f in sorted(os.listdir(os.path.join(repo, d))):
            if f.endswith(".py"):
                sources.append(os.path.join(repo, d, f))

    CLAIM = re.compile(r"never (?:rendered|shown|displayed)|rendered nowhere|not rendered"
                       r"|never displayed|shown nowhere", re.I)
    offenders = []
    for path in sources:
        lines = open(path, encoding="utf-8").read().splitlines()
        for i, line in enumerate(lines):
            if not CLAIM.search(line):
                continue
            # A window either side: a comment usually sits ABOVE the field it describes,
            # a prose sentence usually names it on the same line or just before. Wide
            # enough to catch both, at the cost of occasionally naming a neighbouring
            # field -- which still points at the right line.
            window = " ".join(lines[max(0, i - 1):i + 4])
            for ident in set(re.findall(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+){2,})\b", window)):
                if re.search(rf"\b{re.escape(ident)}\b", js):
                    offenders.append(
                        f"{os.path.relpath(path, repo)}:{i + 1} says {ident!r} is not "
                        f"rendered, but app/static/app.js references it")
    assert not offenders, "\n  ".join([""] + sorted(set(offenders)))
