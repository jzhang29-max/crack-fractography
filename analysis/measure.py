#!/usr/bin/env python3
"""Per-crack and per-frame measurement of a black-and-white crack mask.

The per-region shape code is IMPORTED from the SEM repo
(interior_active_learning/code/extended_features.crack_shape_measurements), never copied. A
second implementation of the same metrics is a silent mismatch with every number that repo
has published, and that function carries fixes that are not obvious: mean width is
area/skeleton LENGTH rather than area/pixel count (the count overstates a diagonal crack's
width by up to sqrt(2)), and max width reads the distance transform on the skeleton from the
same crop the skeleton was built on -- a shape mismatch there once made max width fall back
to sqrt(area) for every region ever measured.

WHAT THIS FILE ADDS is the frame level, and three guards that each already cost this project
a wrong number:

  A COUNT IS NOT A MASS. 305 components read as a fragmented network until the largest was
  found to hold 97.45% of the area. So every frame reports largest_share_of_area beside
  n_cracks, and a count is never reported alone.

  LENGTH IS CENSORED AT THE FRAME EDGE. A crack running out of view is longer than measured.
  Regions touching the border are counted and their length is flagged, so a length
  distribution can be read without pretending the tail is complete.

  NO PHYSICAL UNITS WITHOUT SCALE. Pixel columns are always present; micrometre columns
  appear only when nm/px is established for that frame, and are None otherwise. The older
  SEM corpus spans a 249x magnification range, so pooling um across unknown scales is
  meaningless.

Tortuosity is left NaN unless the region has exactly 2 skeleton endpoints and no branch
points, which is the only topology for which path/chord is defined. Reporting a number for a
branched network would invent one.
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from skimage import measure as skmeasure

Image.MAX_IMAGE_PIXELS = None
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(REPO, "data", "sem", "interior_active_learning", "code"))
sys.path.insert(0, _HERE)

from extended_features import crack_shape_measurements   # noqa: E402  (the shared implementation)
from scale import nm_per_px                               # noqa: E402

#: Regions at or below this pixel area are counted but excluded from shape statistics: a
#: handful of pixels has no meaningful width, orientation or tortuosity. They are reported
#: as speck_count so the exclusion is visible rather than silent.
SPECK_PX = 25


def load_mask(path):
    """A BW mask, crack = BLACK. Returns a boolean array, True where crack."""
    a = np.array(Image.open(path).convert("L"))
    return a < 128


def measure_frame(mask, stem, modality="sem"):
    """Per-crack rows plus a frame summary. mask: bool array, True = crack."""
    lab = skmeasure.label(mask, connectivity=2)
    n = int(lab.max())
    nm = nm_per_px(stem, modality)
    px_um = (nm / 1000.0) if nm else None       # um per pixel

    rows, specks = [], 0
    H, W = mask.shape
    for p in skmeasure.regionprops(lab):
        if p.area <= SPECK_PX:
            specks += 1
            continue
        y0, x0, y1, x1 = p.bbox
        sub = lab[y0:y1, x0:x1] == p.label
        d = crack_shape_measurements(sub)
        touches = bool(y0 == 0 or x0 == 0 or y1 >= H or x1 >= W)
        r = {
            "crack_id": int(p.label),
            "area_px": int(p.area),
            "centroid_x_px": round(float(p.centroid[1]), 1),
            "centroid_y_px": round(float(p.centroid[0]), 1),
            "touches_frame_edge": touches,
            "length_is_censored": touches,
        }
        for k, v in d.items():
            r[k] = (None if (isinstance(v, float) and not np.isfinite(v)) else v)
        if px_um:
            r["area_um2"] = round(p.area * px_um * px_um, 4)
            for src, dst in (("SkeletonLength_px", "length_um"),
                             ("MeanWidth_px", "mean_width_um"),
                             ("MaxWidth_px", "max_width_um")):
                v = d.get(src)
                r[dst] = (round(float(v) * px_um, 4)
                          if isinstance(v, (int, float)) and np.isfinite(v) else None)
        rows.append(r)

    total_px = int(mask.sum())
    areas = np.array([r["area_px"] for r in rows], float) if rows else np.zeros(0)
    lengths = np.array([r.get("SkeletonLength_px") or 0.0 for r in rows], float)
    widths = np.array([r["MeanWidth_px"] for r in rows if isinstance(r.get("MeanWidth_px"), (int, float))], float)
    torts = np.array([r["Tortuosity"] for r in rows if isinstance(r.get("Tortuosity"), (int, float))], float)
    oris = np.array([r["Orientation_deg"] for r in rows if isinstance(r.get("Orientation_deg"), (int, float))], float)
    branches = np.array([r.get("BranchPointCount") or 0 for r in rows], float)

    summary = {
        "frame": stem,
        "modality": modality,
        "height_px": int(H), "width_px": int(W),
        "megapixels": round(mask.size / 1e6, 3),
        "nm_per_px": nm,
        "scale_known": nm is not None,

        "n_regions_total": n,
        "n_cracks_measured": len(rows),
        "speck_count": specks,
        "speck_threshold_px": SPECK_PX,

        "crack_area_px": total_px,
        "area_fraction": round(float(mask.mean()), 6),
        # A COUNT IS NOT A MASS.
        "largest_area_px": int(areas.max()) if len(areas) else 0,
        "largest_share_of_area": round(float(areas.max() / areas.sum()), 4) if areas.sum() else None,
        "top1pct_share_of_area": _top_share(areas, 0.01),

        "total_skeleton_length_px": round(float(lengths.sum()), 1),
        # length per unit area -- the standard crack-density form
        "crack_density_px_per_Mpx": round(float(lengths.sum()) / (mask.size / 1e6), 1),

        "n_censored": int(sum(1 for r in rows if r["length_is_censored"])),
        "censored_share": round(sum(1 for r in rows if r["length_is_censored"]) / len(rows), 4) if rows else None,

        "mean_width_px_median": _med(widths),
        "tortuosity_median": _med(torts),
        "tortuosity_n_defined": int(len(torts)),
        "branch_points_total": int(branches.sum()),
        "orientation_hist_deg": _rose(oris, areas, rows),
    }
    if px_um:
        summary["crack_area_um2"] = round(total_px * px_um * px_um, 2)
        summary["total_length_um"] = round(float(lengths.sum()) * px_um, 2)
        summary["field_width_um"] = round(W * px_um, 2)
    return rows, summary


def _med(a):
    return round(float(np.median(a)), 4) if len(a) else None


def _top_share(areas, frac):
    if not len(areas):
        return None
    k = max(1, int(round(len(areas) * frac)))
    return round(float(np.sort(areas)[::-1][:k].sum() / areas.sum()), 4)


def _rose(oris, areas, rows):
    """Orientation histogram in 12 bins of 15 deg, weighted by AREA not by count.

    Count-weighting lets a thousand specks outvote the one crack that holds the area -- the
    same failure as reporting n_cracks alone. Bins are 0-180: a crack has an axis, not a
    direction, so 10 deg and 190 deg are the same orientation.
    """
    if not len(oris):
        return None
    w = np.array([r["area_px"] for r in rows
                  if isinstance(r.get("Orientation_deg"), (int, float))], float)
    o = np.mod(oris, 180.0)
    hist, edges = np.histogram(o, bins=12, range=(0, 180), weights=w)
    tot = hist.sum()
    return {"bin_deg": [int(e) for e in edges[:-1]],
            "area_share": [round(float(h / tot), 4) for h in hist] if tot else None,
            "weighted_by": "area"}


def measure_path(path, modality="sem", stem=None):
    stem = stem or os.path.splitext(os.path.basename(path))[0]
    for suf in ("_gated", "_machine", "_mask", "_crack_mask"):
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
    return measure_frame(load_mask(path), stem, modality)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: measure.py <mask.png> [sem|txm]")
    rows, summ = measure_path(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "sem")
    print(json.dumps(summ, indent=2))
    print(f"\n{len(rows)} cracks measured")
    for r in sorted(rows, key=lambda r: -r["area_px"])[:5]:
        print(f"  id {r['crack_id']:>5}  area {r['area_px']:>9,} px  "
              f"len {r.get('SkeletonLength_px')}  meanW {r.get('MeanWidth_px')}  "
              f"tort {r.get('Tortuosity')}  censored {r['length_is_censored']}")
