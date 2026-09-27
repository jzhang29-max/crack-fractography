#!/usr/bin/env python3
"""Guards on the measurement, on synthetic masks where the answer is known by construction.

Run: ../.venv/bin/python3 tests/test_measure.py   (or the SEM repo's venv)
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(REPO, "analysis"))
from measure import measure_frame, SPECK_PX     # noqa: E402
from scale import nm_per_px, txm_specimen_key   # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))
    if not cond:
        FAILED.append(name)


def main():
    # One 4x100 bar plus 30 single-pixel specks. A COUNT would say 31 regions and read as a
    # fragmented network; the MASS is essentially all in the bar.
    m = np.zeros((200, 200), bool)
    m[100:104, 40:140] = True
    rng = np.random.default_rng(0)
    for y, x in zip(rng.integers(5, 60, 30), rng.integers(5, 190, 30)):
        m[y, x] = True
    rows, s = measure_frame(m, "synthetic_bar", "sem")

    check("specks are excluded from shape stats but counted",
          s["speck_count"] == 30 and s["n_cracks_measured"] == 1,
          f"specks {s['speck_count']}, measured {s['n_cracks_measured']}")
    check("a count is not a mass: largest share is reported and is ~1.0",
          s["largest_share_of_area"] is not None and s["largest_share_of_area"] > 0.99,
          f"largest_share_of_area={s['largest_share_of_area']}")
    check("region total counts every region, specks included",
          s["n_regions_total"] == 31, f"n_regions_total={s['n_regions_total']}")
    check("a 4x100 bar measures ~4 px mean width",
          abs(rows[0]["MeanWidth_px"] - 4.0) < 1.0, f"{rows[0]['MeanWidth_px']}")
    check("a straight bar is ~straight: tortuosity near 1",
          rows[0]["Tortuosity"] is not None and abs(rows[0]["Tortuosity"] - 1.0) < 0.05,
          f"{rows[0]['Tortuosity']}")
    check("an interior region is not flagged as censored",
          rows[0]["length_is_censored"] is False)

    # A bar running off the edge must be flagged: its length is a lower bound.
    e = np.zeros((200, 200), bool)
    e[100:104, 0:120] = True
    erows, es = measure_frame(e, "synthetic_edge", "sem")
    check("a region touching the frame edge is flagged censored",
          erows[0]["length_is_censored"] is True and es["n_censored"] == 1)

    # No scale -> no physical columns, rather than a default.
    check("a frame with no known scale gets no um columns",
          s["scale_known"] is False and "area_um2" not in rows[0]
          and "crack_area_um2" not in s)
    # With scale, they appear and are consistent.
    rows2, s2 = measure_frame(m, "MAR_H_AS_CBS_0001", "sem")
    check("a frame with a known scale gets um columns",
          s2["scale_known"] is True and rows2[0].get("area_um2") is not None,
          f"nm_per_px={s2['nm_per_px']}")
    px_um = s2["nm_per_px"] / 1000.0
    check("area_um2 equals area_px x (um/px)^2",
          abs(rows2[0]["area_um2"] - rows2[0]["area_px"] * px_um ** 2) < 1e-3)

    # An empty mask must not crash and must not claim a share of nothing.
    _, z = measure_frame(np.zeros((50, 50), bool), "empty", "sem")
    check("an empty mask yields no cracks and no largest share",
          z["n_cracks_measured"] == 0 and z["largest_share_of_area"] is None
          and z["area_fraction"] == 0.0)

    # Orientation is weighted by SEGMENT LENGTH, not component area. It was area-weighted
    # until 2026-09-26, which made it a width-weighted rose over a per-component second-moment
    # axis: one short wide crack outvoted a long thin one, and for a branched network the
    # component axis is noise. This assertion changed deliberately; the old one is not a
    # regression to restore.
    r = s["orientation_hist_deg"]
    check("the rose is weighted by segment length and declares it",
          r is not None and r["weighted_by"] == "segment length"
          and max(r["area_share"]) > 0.5,
          f"weighted_by={r and r['weighted_by']}")
    check("tortuosity is gone from the frame summary, replaced by R_L on a declared axis",
          "tortuosity_median" not in s and "R_L_median" in s and "R_L_axis_deg" in s)
    check("Pij densities are labelled with their subscripts",
          "p21_skeleton_mm_per_mm2" in s2 and "p20_per_mm2" in s2 and "p20_edge_rule" in s2)
    check("the ISO 643 edge rule is named in the output, not just applied",
          "n_edge/2" in str(s2.get("p20_edge_rule", "")))

    check("scale is None for a frame with no metadata, not a default",
          nm_per_px("260622_316_H_b2_front_CBS_01") is None)
    check("TXM specimens parse and normalise case",
          txm_specimen_key("Average_mosaic_260618_B2_x") == "260618_b2"
          and txm_specimen_key("Average_mosaic_260618_b2_y") == "260618_b2")
    check("TXM keeps distinct materials distinct",
          txm_specimen_key("Average_mosaic_260619_HC_316L_a") !=
          txm_specimen_key("Average_mosaic_260620_wrought_316L_a"))
    check("an unparseable stem returns None, not a per-frame sentinel",
          txm_specimen_key("nonsense") is None)

    print(f"\n{'=' * 60}\n{len(FAILED)} failed")
    for f in FAILED:
        print(f"  - {f}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
