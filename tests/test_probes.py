#!/usr/bin/env python3
"""Line-intercept probe, checked against geometry whose answer is known in advance."""
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

    # An isotropic-ish field: P10 should vary far less with angle than the striped case.
    rng = np.random.default_rng(0)
    iso = np.zeros((600, 600), bool)
    for _ in range(120):
        y, x = rng.integers(20, 580, 2); a = rng.uniform(0, np.pi)
        for t in range(-25, 25):
            yy, xx = int(y + t * np.sin(a)), int(x + t * np.cos(a))
            if 0 <= yy < 600 and 0 <= xx < 600: iso[yy, xx] = True
    q = line_probe(iso, nm_per_px=1000.0)
    aniso_striped = p["p10_max_per_mm"] / max(p["p10_min_per_mm"], 1e-9)
    aniso_iso = q["p10_max_per_mm"] / max(q["p10_min_per_mm"], 1e-9)
    check("a striped field reads far more anisotropic than a random one",
          aniso_striped > 5 * aniso_iso, f"striped {aniso_striped:.0f}x vs random {aniso_iso:.1f}x")

    # No scale -> no per-mm anything, rather than a default.
    n = line_probe(m, nm_per_px=None)
    check("without a scale every per-mm form is withheld",
          n["p10_per_mm"] is None and "p10_min_per_mm" not in n and n["scale_known"] is False)

    check("an empty mask does not raise and says so",
          line_probe(np.zeros((50, 50), bool)).get("note") is not None)

    # --- segments: the digitisation diagnostic, and the metric that is NOT here --------
    sys.path.insert(0, os.path.join(os.path.dirname(_H), "analysis"))
    from segments import skeleton_segments, MIN_DIRECTIONAL_PX

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

    check("the rose is weighted by segment length, not component area",
          sb["rose_weighted_by"] == "segment length")

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
    check("the gate threshold and retained length share are both reported",
          ss["min_directional_px"] == MIN_DIRECTIONAL_PX
          and ss["directional_length_share"] is not None)
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
