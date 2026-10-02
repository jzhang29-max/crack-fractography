#!/usr/bin/env python3
"""Nothing computed may be silently discarded.

segments.py produced 24 summary fields and measure.py forwarded 9. The other 15 were
calculated on every frame of every run and thrown away -- among them the anisotropy null,
which unit-tested green against skeleton_segments() and then landed on 0 of 358 frames after
a 40-minute batch, because no test exercised the path from the producer to the stored record.

That is the shape of the failure this file exists to catch: a read with no writer, or here a
writer with no reader. Unit-testing the producer in isolation cannot see it.
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np
import pytest

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
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPJS = os.path.join(REPO, "app", "static", "app.js")

#: The claim being policed. Unchanged from the original guard -- the regex was never the
#: problem; what it did with its two hits was.
CLAIM = re.compile(r"never (?:rendered|shown|displayed)|rendered nowhere|not rendered"
                   r"|never displayed|shown nowhere", re.I)

#: ONE SPECIMEN RECORD, WRITTEN OUT BY HAND, because the card's interesting branches are
#: all conditional and a one-group single-branch record leaves most of the renderer
#: unexecuted. This is MAR_AmbB_AS's shape: nine fields at 51.883 nm/px plus one overview
#: at 337.2396, which is the only configuration in the corpus where magRow() takes its
#: off-determination branch and therefore the only one that renders
#: area_off_determination_mm2 at all. Every value is non-null on purpose: the probe below
#: works by knocking one field out at a time, and a field that is already null cannot be
#: knocked out.
_SPECIMEN = {
    "arm": "sem/gated", "specimen": "MAR_AmbB_AS",
    "n_frames": 20, "n_fields": 10, "n_cracks_total": 1526, "scale_known_frames": 20,
    "area_fraction_median": 0.0174, "area_fraction_min": 0.005613,
    "area_fraction_max": 0.060981, "density_median": 1298.5,
    "estimable_dispersion": True,
    "area_fraction_ci": {
        "mean": 0.022265, "sd_between_fields": 0.017963, "n_fields": 9,
        "ci95_halfwidth": 0.013807, "ci95_lo": 0.008458, "ci95_lo_clamped": False,
        "ci95_lo_note": None, "ci95_hi": 0.036072, "pct_relative_accuracy": 62.0,
        "t95": 2.306, "method": "ASTM E562-19e1 between-field variance",
        "nm_per_px": 51.883, "n_fields_off_determination": 1,
        "magnification_note": "over the 9 fields at 51.883 nm/px only",
    },
    "no_ci_reason": "placeholder — overwritten in the no-interval variant",
    "magnification_groups": [
        {"nm_per_px": 51.883, "n_fields": 9, "area_fraction_mean": 0.022265,
         "min_resolvable_width_um": 0.0519, "in_determination": True},
        {"nm_per_px": 337.2396, "n_fields": 1, "area_fraction_mean": 0.032351,
         "min_resolvable_width_um": 0.3372, "in_determination": False},
    ],
    "n_fields_off_determination": 1,
    "p10_min_per_mm": 9.0175, "p10_mean_per_mm": 9.3995,
    "p21_skeleton_mm_per_mm2": 25.7728, "p21_buffon_mm_per_mm2": 14.765,
    "p20_per_mm2": 1073.92, "mcl_um": 39.31, "largest_network_centreline_um": 216.67,
    "tcl_um_total": 15415.0, "area_analysed_mm2": 0.609687, "n_fields_scaled": 9,
    "area_off_determination_mm2": 0.715531, "tcl_um_off_determination": 2244.9,
    "stage_gradient": {
        "n_frames_with_position": 9, "field": "area_fraction", "axis": "stage_y",
        "spearman_rho": 0.75, "p_value": 0.019942, "n_distinct_stage_coords": 9,
        "field_max_min_ratio": 3.7, "significant": True, "note": "trend across one patch",
    },
    "n_patches": 1,
    "detectors": {"CBS": 10, "ETD": 10},
    "detector_sensitivity": {"n_fields_both_detectors": 10, "cbs_over_etd_median": 2.447,
                             "note": "same physical field, two detectors"},
    "arm_sensitivity": {"n_paired_frames": 20, "n_frames_corrected": 3,
                        "gated_over_machine_median": 1.0,
                        "gated_over_machine_where_corrected": 1.08,
                        "note": "the operator's strokes against the detector alone"},
    "stage_gradient_by_detector": {"CBS": {"spearman_rho": 0.7, "significant": True}},
}


def _card_variants():
    """The same record through each branch of the card, so "not rendered" means not
    rendered on ANY of them.

    One record exercises one side of every `?:` in specimenCard(). Measured on the
    two-magnification scaled record alone, area_fraction_median and n_fields read as
    unrendered -- they are the fallback shown when there is no interval -- so a claim that
    either is never shown would have passed. Four variants close that: with and without an
    interval, with and without a physical scale, and with one magnification group instead
    of two.
    """
    import copy
    full = copy.deepcopy(_SPECIMEN)
    full["no_ci_reason"] = None

    no_ci = copy.deepcopy(full)
    no_ci["area_fraction_ci"] = None
    no_ci["no_ci_reason"] = "under 3 fields at a single magnification — no interval"

    unscaled = copy.deepcopy(full)
    unscaled["scale_known_frames"] = 0

    one_mag = copy.deepcopy(full)
    one_mag["magnification_groups"] = [full["magnification_groups"][0]]
    one_mag["n_fields_off_determination"] = 0
    return [full, no_ci, unscaled, one_mag]


def _fields_the_card_renders():
    """The set of record fields the REAL renderer puts on screen, measured by ablation.

    Loads specimenCard() and its helpers out of app.js, renders each variant, then renders
    it again with one field set to null and compares the HTML. A field whose removal
    changes the card is a field the card shows -- whether it is printed, formatted into a
    tooltip, or used to gate a clause. No source-text matching anywhere: a name that
    appears only in an app.js comment cannot register, and a field reached dynamically
    without ever being written literally does.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = open(APPJS, encoding="utf-8").read()
    # The helper slice is taken by anchor rather than line number so the harness breaks
    # loudly if the renderer is moved, instead of silently evaluating the wrong bytes.
    for anchor in ("const plural = (n, word)", "const esc = (v)", "const fmt = (v",
                   "const pct = (v, d = 2)", "function specimenCard(",
                   "async function renderSpecimens("):
        assert src.count(anchor) == 1, f"anchor {anchor!r} is not unique in app.js"
    i = src.index("const plural = (n, word)")
    pre = src[i:src.index("\n", i) + 1]
    pre += src[src.index("const esc = (v)"):src.index("const fmt = (v")]
    pre += src[src.index("const pct = (v, d = 2)"):src.index("async function renderSpecimens(")]
    assert "function specimenCard(" in pre and "function magRow(" in pre

    harness = pre + "\nconst RECS = " + json.dumps(_card_variants()) + ";\n" + """
const shown = {};
for (const rec of RECS) {
  const base = specimenCard(rec);
  if (!base || base.length < 50) throw new Error("card rendered empty: " + base);
  for (const k of Object.keys(rec)) {
    const c = JSON.parse(JSON.stringify(rec));
    c[k] = null;
    let html;
    try { html = specimenCard(c); } catch (e) { html = "THREW " + e.message; }
    if (html !== base) shown[k] = true;
  }
}
process.stdout.write(JSON.stringify(shown));
"""
    out = subprocess.run([node, "-e", harness], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return set(json.loads(out.stdout))


def _docstring_owner_by_line(py_src):
    """{line number: name of the def/class whose docstring occupies that line}.

    Parsed with ast, not matched with a regex, because the claim this guard missed was in
    the body of `def n_patches` and named its subject only in the signature ten lines
    above the sentence.
    """
    owners = {}
    for node in ast.walk(ast.parse(py_src)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None) or []
        if not (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            continue
        doc = body[0]
        for ln in range(doc.lineno, (doc.end_lineno or doc.lineno) + 1):
            owners[ln] = node.name
    return owners


def _unrendered_claims(text, fields, owners=None):
    """[(line number, field)] for every "never rendered" sentence and each field it is about.

    A sentence is about a field if the field's name appears within a line either side, or
    -- for a Python docstring -- if the field has the same name as the function the
    docstring documents. Candidates are drawn from `fields`, the record's own key set,
    rather than from a shape regex: the old guard required three underscore-separated
    parts, which silently excluded every two-part field name in the record.
    """
    out = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not CLAIM.search(line):
            continue
        window = " ".join(lines[max(0, i - 1):i + 4])
        named = {f for f in fields if re.search(rf"\b{re.escape(f)}\b", window)}
        owner = (owners or {}).get(i + 1)
        if owner in fields:
            named.add(owner)
        out += [(i + 1, f) for f in sorted(named)]
    return out


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
    or document may say a record field is unrendered while the card renders it.

    REPAIRED 2026-10-01, after a mutation audit. WHAT THE OLD ASSERTION DID: it found the
    "never rendered" sentences, pulled identifiers of three-or-more underscore-separated
    parts out of a five-line window, and flagged any that app.js mentioned. Instrumented,
    that scan reports two claim sites in the whole repo -- README.md:55 and
    analysis/stage.py:203 -- and extracts ZERO identifiers from either, so `offenders` was
    unconditionally empty and no state of app.js could fail it.

    WHAT DEFEATED IT: adding a row to specimenCard() that prints r.n_patches, while
    analysis/stage.py's own docstring for n_patches says "it is never displayed". The UI
    then renders a field the source claims is unrendered -- exactly the defect -- and the
    guard passed, for two independent reasons. (1) `n_patches` has one underscore, so the
    three-part identifier regex could never name it. (2) The sentence is ten lines below
    the signature, so no window around it contains the word `n_patches` either.

    WHAT IS ASSERTED NOW: the rendered artifact, not app.js's source text. specimenCard()
    is executed in node against four hand-written variants of one specimen record, each
    field is ablated to null in turn, and a field whose removal changes the HTML is a field
    the card shows. The claim side is parsed with ast so a docstring sentence is attributed
    to the function it documents, and candidate names come from the record's key set
    instead of a shape regex. Two controls stand in front of the comparison so it cannot go
    vacuous again: the ablation probe must agree with two facts established by reading the
    renderer (area_off_determination_mm2 IS on the card, under the Magnification row;
    tcl_um_off_determination is stored and is NOT), and the claim parser must recover a
    planted claim whose answer is known from how it was written.
    """
    rendered = _fields_the_card_renders()

    # CONTROL 1 -- the probe is live and discriminating. Both facts are read off
    # specimen_stats.py's own comment at the "area_off_determination_mm2" assignment and
    # off magRow(), not produced by this probe. If the probe degenerated to "everything"
    # or "nothing" one of these two fails.
    assert "area_off_determination_mm2" in rendered, (
        "the probe cannot see a field that magRow() demonstrably prints; the harness, not "
        "the app, is broken")
    assert "tcl_um_off_determination" not in rendered, (
        "the probe calls a stored-but-unshown field rendered, so 'rendered' has become a "
        "superset that always contains the claim")

    # CONTROL 2 -- the claim parser recovers a subject it was given. Both planted sentences
    # are about `n_patches`: the first names it in the window, the second only in the
    # signature, which is the case the old guard could not see.
    planted = (
        'def n_patches(frames):\n'
        '    """How many separated imaged sites these frames cover.\n\n'
        '    Padding so the sentence is nowhere near the signature.\n'
        '    Padding.\n'
        '    Padding.\n'
        '    It is never displayed -- the units would be wrong on screen.\n'
        '    """\n'
        '    return None\n\n'
        '# mcl_um is never rendered on the card.\n'
    )
    got = _unrendered_claims(planted, {"n_patches", "mcl_um"},
                             _docstring_owner_by_line(planted))
    assert got == [(7, "n_patches"), (11, "mcl_um")], got

    # --- the guard itself -----------------------------------------------------------
    sources = [os.path.join(REPO, "README.md")]
    for d in ("analysis", "app"):
        for f in sorted(os.listdir(os.path.join(REPO, d))):
            if f.endswith(".py"):
                sources.append(os.path.join(REPO, d, f))

    offenders = []
    for path in sources:
        text = open(path, encoding="utf-8").read()
        owners = _docstring_owner_by_line(text) if path.endswith(".py") else {}
        for lineno, field in _unrendered_claims(text, rendered, owners):
            offenders.append(
                f"{os.path.relpath(path, REPO)}:{lineno} says {field!r} is not rendered, "
                f"but removing it changes the HTML specimenCard() produces")
    assert not offenders, "\n  ".join([""] + sorted(set(offenders)))
