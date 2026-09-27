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

    print(f"\n{len(F)} failed")
    for x in F: print(f"  - {x}")
    return 1 if F else 0

if __name__ == "__main__":
    sys.exit(main())
