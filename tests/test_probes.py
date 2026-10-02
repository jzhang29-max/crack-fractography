#!/usr/bin/env python3
"""Line-intercept probe, checked against geometry whose answer is known in advance.

REPAIRED 2026-10-01 after a mutation audit proved four checks here worthless -- the audit
broke the behaviour each one claims to protect and each one still printed PASS. The four,
and what defeated them, are written out above the checks themselves:

  * "a striped field reads far more anisotropic than a random one" -- a ratio whose
    denominator is ~0 by construction, so it is satisfied by almost any pair of values.
  * "an empty mask does not raise and says so" -- asked for `note`, which the no-scale
    branch also sets, so deleting the empty-mask path left the check reading the wrong note.
  * "the gate threshold and retained length share are both reported" -- compared the
    reported threshold against the same module constant that produced it, and asked only
    that the share be `is not None`, which 0.0 satisfies.
  * "the rose is weighted by segment length, not component area" -- read a declaration
    string, not the weighting.

The repairs follow this file's existing rule: every expected value is computed by hand from
the fixture's construction, never by calling the function under test.
"""
import os, sys
import numpy as np
_H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_H), "analysis"))
from probes import line_probe            # noqa: E402

F = []
def check(n, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {n}" + (f"  -- {d}" if d else ""))
    if not c: F.append(n)

def main():
    # 10 horizontal bars 100 px apart in a 1000x1000 frame at 1 um/px == 1 mm across.
    m = np.zeros((1000, 1000), bool)
    for y in range(50, 1000, 100):
        m[y:y + 3, :] = True
    p = line_probe(m, nm_per_px=1000.0)

    check("P10 max equals the bar count per mm", abs(p["p10_max_per_mm"] - 10.0) < 0.3,
          f"{p['p10_max_per_mm']}")
    check("P10 min is ~0 along the bars", p["p10_min_per_mm"] < 1.0,
          f"{p['p10_min_per_mm']} at {p['p10_min_at_deg']}deg")
    check("min and mean differ, so reporting only a mean would hide the standard's criterion",
          p["p10_mean_per_mm"] > 2 * p["p10_min_per_mm"],
          f"min {p['p10_min_per_mm']} vs mean {p['p10_mean_per_mm']}")
    check("spacing at the densest direction is the bar pitch",
          abs(p["spacing_min_mm"] - 0.1) < 0.01, f"{p['spacing_min_mm']} mm")
    check("S_V ships its isotropy assumption as data, not as a docstring",
          isinstance(p.get("sv_assumption"), str) and "isotropic" in p["sv_assumption"])

    # --- the directional curve, against a law known before this code runs --------------
    # THE CURVE ITSELF, which nothing here used to check. The bars are horizontal with a
    # pitch of 100 px = 0.1 mm. A test line at theta advances l*|sin theta| across the
    # bars over a travel of l, so it meets one bar every 100/|sin theta| px:
    #
    #     P10(theta) = 10 * |sin theta|   cracks/mm
    #
    # That is arithmetic on the fixture's construction, not an output of line_probe. The
    # old file asserted only max, min, mean and spacing -- four scalars, all of which are
    # still right when the angle AXIS is wrong, which is how the mutation below survived.
    law = [10.0 * abs(np.sin(np.deg2rad(a))) for a in p["angles_deg"]]
    worst = max(abs(v - e) for v, e in zip(p["p10_per_mm"], law))
    worst_at = p["angles_deg"][int(np.argmax([abs(v - e) for v, e in
                                              zip(p["p10_per_mm"], law)]))]
    check("P10(theta) equals the 10*|sin theta| the bar pitch implies, at every angle",
          worst < 0.1, f"worst error {worst:.3f} cracks/mm at {worst_at}deg")

    # An isotropic-ish field: P10 should vary far less with angle than the striped case.
    rng = np.random.default_rng(0)
    iso = np.zeros((600, 600), bool)
    for _ in range(120):
        y, x = rng.integers(20, 580, 2); a = rng.uniform(0, np.pi)
        for t in range(-25, 25):
            yy, xx = int(y + t * np.sin(a)), int(x + t * np.cos(a))
            if 0 <= yy < 600 and 0 <= xx < 600: iso[yy, xx] = True
    q = line_probe(iso, nm_per_px=1000.0)
    # REPAIRED GUARD 1. The old assertion was `aniso_striped > 5 * aniso_iso`. Defeated
    # because the striped field's minimum is ~0 BY CONSTRUCTION (a line laid along the
    # bars meets none of them), so aniso_striped is ~250 regardless of what the probe
    # computes, and the test is satisfied by almost any pair of values. Proved by mutating
    # probes._transitions_along, `t = np.deg2rad(theta_deg)` ->
    # `t = np.deg2rad(2.0 * theta_deg)`: the angle axis is doubled, so every P10 is filed
    # under the wrong direction, and this check -- and every other check in the old file --
    # still passed.
    # NOW: both sides are anchored, and the striped side is anchored to the hand-computed
    # curve rather than to its own extremes -- an anisotropy claim is a claim about the
    # SHAPE of P10(theta), so `worst` is part of this assertion and not merely reported
    # next to it. Added to that: a floor on the span and the angle at which the minimum
    # must fall (along the bars, 0 deg). The random side is isotropic BY CONSTRUCTION --
    # straight lines at uniform random angles -- so its P10 curve must be FLAT to within
    # sampling scatter; 1.5x is the bound, against an observed 1.14x on this fixed seed.
    # The intent is unchanged: striped reads anisotropic, random does not.
    aniso_striped = p["p10_max_per_mm"] / max(p["p10_min_per_mm"], 1e-9)
    aniso_iso = q["p10_max_per_mm"] / max(q["p10_min_per_mm"], 1e-9)
    check("a striped field reads far more anisotropic than a random one",
          worst < 0.1 and aniso_striped > 100.0 and aniso_iso < 1.5
          and p["p10_min_at_deg"] == 0.0,
          f"striped {aniso_striped:.0f}x (curve error {worst:.3f}), min at "
          f"{p['p10_min_at_deg']}deg (bars lie at 0deg) vs random {aniso_iso:.2f}x")

    # No scale -> no per-mm anything, rather than a default.
    n = line_probe(m, nm_per_px=None)
    check("without a scale every per-mm form is withheld",
          n["p10_per_mm"] is None and "p10_min_per_mm" not in n and n["scale_known"] is False)

    # REPAIRED GUARD 2. The old assertion was
    #     line_probe(np.zeros((50, 50), bool)).get("note") is not None
    # with NO scale -- and the no-scale branch at the BOTTOM of line_probe sets "note" too
    # ("no nm/px for this frame..."). So the assertion was satisfied by a superset that
    # always contains it. Proved by mutating probes.line_probe, `if mask.sum() == 0:` ->
    # `if False:`: the empty-mask path is gone, the function walks 18 angles over an empty
    # frame and falls out of the no-scale branch, and the old check passed on the wrong
    # note.
    # NOW: ask WITH a scale, so the no-scale note cannot stand in, require the note to be
    # about crack absence and to differ from the no-scale note, and require the physical
    # fields to be WITHHELD rather than invented as zeros -- an empty mask reporting
    # "0.0 cracks/mm" and "S_V = 0.0" would be a measurement no one made.
    try:
        e = line_probe(np.zeros((50, 50), bool), nm_per_px=1000.0)
        raised = None
    except Exception as exc:                                       # noqa: BLE001
        e, raised = {}, repr(exc)
    check("an empty mask does not raise and says so",
          raised is None
          and isinstance(e.get("note"), str) and "no crack" in e["note"]
          and e["note"] != n["note"]
          and e["p10_per_mm"] is None
          and "p10_max_per_mm" not in e and "sv_mm2_per_mm3" not in e,
          f"raised={raised} note={e.get('note')!r} p10_per_mm={e.get('p10_per_mm')!r}")

    # --- segments: the digitisation diagnostic, and the metric that is NOT here --------
    sys.path.insert(0, os.path.join(os.path.dirname(_H), "analysis"))
    # MIN_DIRECTIONAL_PX is deliberately NOT imported any more: the old gate check compared
    # the reported threshold against this very constant, so the two sides moved together
    # and the comparison could not fail. See REPAIRED GUARD 3 below.
    from segments import skeleton_segments

    bar = np.zeros((200, 400), bool); bar[100:103, 40:360] = True
    _, sb = skeleton_segments(bar)

    dia = np.zeros((300, 300), bool)
    for i in range(30, 270): dia[i - 1:i + 2, i - 1:i + 2] = True
    _, sd = skeleton_segments(dia)

    # R_L is gone, not renamed. It needed a declared axis, this app has none, and against
    # the image raster it was the identity (length/chord) x sec(angle) -- median AND upper
    # quartile both exactly sec(45 deg) over the corpus. The keys must not come back.
    GONE = ("R_L_median", "R_L_n", "R_L_axis_deg", "R_L_below_one",
            "lattice_locked_share_all_segments")
    check("no R_L field survives anywhere in a segment summary",
          not [k for k in GONE if k in sb or k in sd],
          f"{[k for k in GONE if k in sb or k in sd]}")

    # The replacement is axis-invariant: an exact integer test on the chord endpoints.
    # Both lattice controls read 1.0 -- and the DECOY is what makes that mean anything,
    # since a function returning 1.0 unconditionally would pass the first two.
    check("a horizontal bar's chords are all on the lattice",
          sb["lattice_chord_share_all_segments"] == 1.0,
          f"{sb['lattice_chord_share_all_segments']}")
    check("a 45-degree bar's chords are all on the lattice",
          sd["lattice_chord_share_all_segments"] == 1.0,
          f"{sd['lattice_chord_share_all_segments']}")
    off = np.zeros((320, 320), bool)
    for x in range(20, 300):                      # slope 1/3: neither axis nor diagonal
        y = 20 + (x - 20) // 3
        off[y - 1:y + 2, x - 1:x + 2] = True
    _, so = skeleton_segments(off)
    check("an off-lattice line does NOT count as lattice-locked",
          so["lattice_chord_share_all_segments"] < 0.5,
          f"{so['lattice_chord_share_all_segments']}")

    # REPAIRED GUARD 4. The old assertion was
    #     sb["rose_weighted_by"] == "segment length"
    # which reads a DECLARATION the summary carries unconditionally, not the weighting.
    # Proved by mutating segments.skeleton_segments, `weights=L` -> `weights=None` in the
    # np.histogram call: the rose becomes one vote per branch, the declaration still says
    # "segment length", and the old check passed.
    # NOW: a fixture on which the three candidate weightings give three different roses.
    # One 91-px horizontal row -- a 1-px row is its own skeleton, and a run of k pixels has
    # k-1 unit steps, so length 90 px, angle 0 deg, rose bin 0 -- against THREE 31-px
    # vertical columns, length 30 px each, angle 90 deg, rose bin 6 (90-105 deg). By hand:
    #     by LENGTH   90 vs 3*30 = 90   -> 0.5000 / 0.5000   exactly
    #     by COUNT     1 vs 3           -> 0.2500 / 0.7500
    #     by PIXEL AREA 91 vs 3*31 = 93 -> 0.4946 / 0.5054
    # so an exact half in both bins is reachable only by length weighting. Every branch is
    # over the 20 px directional gate, so none of them is silently dropped first.
    rose = np.zeros((300, 300), bool)
    rose[20, 20:111] = True
    for xc in (40, 90, 140):
        rose[100:131, xc] = True
    _, sr = skeleton_segments(rose)
    rshare = sr["rose_length_share"]
    check("the rose is weighted by segment length, not component area",
          sr["rose_weighted_by"] == "segment length"
          and sr["n_segments"] == 4 and sr["n_segments_directional"] == 4
          and rshare is not None
          and rshare[0] == 0.5 and rshare[6] == 0.5 and sum(rshare) == 1.0,
          f"bin0 {rshare[0] if rshare else None} bin6 {rshare[6] if rshare else None}; "
          f"count weighting would read 0.25/0.75, pixel-area weighting 0.4946/0.5054")

    # The gate must actually gate: a field of 5px stubs has no measurable direction.
    stubs = np.zeros((400, 400), bool)
    rng2 = np.random.default_rng(1)
    for _ in range(300):
        y, x = rng2.integers(10, 390, 2)
        stubs[y:y + 1, x:x + 5] = True
    _, ss = skeleton_segments(stubs)
    check("short stubs are excluded from direction-dependent statistics",
          ss["n_segments_directional"] == 0 or ss["directional_length_share"] < 0.2,
          f"{ss['n_segments_directional']} of {ss['n_segments']} kept")
    # REPAIRED GUARD 3. The old assertion was
    #     ss["min_directional_px"] == MIN_DIRECTIONAL_PX
    #     and ss["directional_length_share"] is not None
    # Two dead halves. The first compared the reported threshold against the same module
    # constant that produced it, so both sides move together and no mutation of the
    # constant can fail it. The second is satisfied by 0.0, which is exactly what the stub
    # fixture returns -- a one-value fixture where the gate keeps NOTHING cannot tell a
    # length share from a count share from a constant. Proved by mutating
    # segments.skeleton_segments, `keep = [s for s in segs if s["length_px"] >=
    # MIN_DIRECTIONAL_PX]` -> `>= MIN_DIRECTIONAL_PX / 2.0`: the reported threshold is no
    # longer the one applied, and the old check passed. A second mutation,
    # `kept_share = float(L.sum() / L_all.sum())` -> `float(len(keep) / len(segs))`, turns
    # the length share into a count share and also passed.
    # NOW: a fixture that STRADDLES the gate, with lengths known from its construction --
    # three 1-px rows of 11, 31 and 51 px, which are their own skeletons, so the branch
    # lengths are exactly 10, 30 and 50 px and the total is exactly 90 px. The check is
    # threshold-agnostic: whatever threshold T the summary reports, the kept COUNT and the
    # kept LENGTH SHARE must both be the ones T implies on these three known lengths. At
    # the shipped T = 20 that is 2 of 3 branches and 80/90 = 0.8889, and the count share
    # (2/3 = 0.6667) and the unfiltered share (1.0) are both excluded.
    gate = np.zeros((200, 200), bool)
    gate[20, 20:31] = True                        # 11 px run -> length 10, below the gate
    gate[60, 20:51] = True                        # 31 px run -> length 30
    gate[100, 20:71] = True                       # 51 px run -> length 50
    _, sg = skeleton_segments(gate)
    T = sg["min_directional_px"]
    kept = [L for L in (10.0, 30.0, 50.0) if L >= T]
    check("the gate threshold and retained length share are both reported",
          sg["n_segments"] == 3 and sg["total_segment_length_px"] == 90.0
          and sg["n_segments_directional"] == len(kept)
          and sg["directional_length_share"] == round(sum(kept) / 90.0, 4)
          and ss["min_directional_px"] == T,
          f"T={T}: kept {sg['n_segments_directional']} of {sg['n_segments']}, share "
          f"{sg['directional_length_share']} vs hand {round(sum(kept) / 90.0, 4)}")
    check("the digitisation share is reported as a diagnostic, with no threshold on it",
          "lattice_chord_share_all_segments" in ss)
    # A field of 5 px stubs is the extreme case and must read as fully lattice-set: at
    # that length every direction is within 22.5 deg of a lattice one.
    check("a field of 5px stubs is entirely lattice-set",
          ss["lattice_chord_share_all_segments"] == 1.0,
          f"{ss['lattice_chord_share_all_segments']}")

    print(f"\n{len(F)} failed")
    for x in F: print(f"  - {x}")
    return 1 if F else 0

if __name__ == "__main__":
    sys.exit(main())
