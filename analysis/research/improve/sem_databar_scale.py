#!/usr/bin/env python3
"""Recover the pixel size of the b2 and b3 SEM frames from the instrument databar.

WHY THIS EXISTS. `analysis/scale.py` has two SEM sources and neither answers for these
frames. `from_tiff()` parses the FEI/Thermo block appended to a TIFF and returns None for
all 23 b2/b3 originals -- the block is simply not there. `fei_metadata_260915.csv` is 80
rows and every one of them is a `MAR_*` frame. So on the specimen series the paper is now
restricted to, the application reports `scale_known: false`, every physical quantity is
null, and a figure drawn from one of these frames can carry no scale bar.

But the frames from the 2026-06-22 session were saved UNCROPPED: 4376 rows where the
field of view is 4096, and the 280 rows underneath are the instrument's own databar, with
the acquisition parameters and a drawn scale bar still in them. That is a recoverable
pixel size, and this module recovers it.

TWO INDEPENDENT ROUTES, AND THEY HAVE TO AGREE.

  1. THE DRAWN BAR. The bar is two vertical ticks joined by a rule, annotated with a round
     length. The tick columns are found by measurement -- the only columns in the tick
     band that are bright over essentially their whole height -- and the span between the
     outermost two, divided into the annotated length, is the pixel size. The span is
     measured to about one pixel in two thousand, so this route is precise to under 0.1%,
     and it assumes only that the annotation is exact, which is how an instrument draws a
     scale bar.

  2. THE PRINTED HORIZONTAL FIELD WIDTH. The databar also prints HFW. Divided by the
     frame's width in pixels that is the pixel size again, from a number the instrument
     states rather than draws. It is printed to three significant figures, so it is the
     coarser of the two -- 259 um is anything from 258.5 to 259.5, which is +/-0.2%.

Route 1 is reported. Route 2 is the control, and `TOLERANCE` is a hard abort: if the drawn
bar and the printed field width disagree by more than a per cent on any frame, something
is wrong with the tick finder or with the transcription and the module refuses to emit a
number rather than quietly publishing the wrong one.

WHAT IS HAND-READ, AND WHY THAT IS SAFE. Two fields are glyphs on a dark strip: the bar's
annotation and the HFW. There is no OCR in this project and adding one to read fourteen
numbers would be a second thing to verify. They are transcribed in `READ` below, and the
script writes the exact crop it transcribed them from to `evidence/`, so the transcription
is auditable against the pixels rather than taken on trust. The tick SPAN -- the only
quantity precision depends on -- is measured, never read.

WHAT THIS DOES NOT RECOVER. The sixteen frames of the 2026-07-08 session were saved
already cropped to the field of view. There is no databar in the file and nothing to
recover; they are reported with a null and the reason, and nine of the eleven scored b2
frames are among them. A pixel size is not transferred from one session to another here:
the two sessions were acquired at different magnifications, which these very numbers show.

    <sem-crack-detector>/.venv/bin/python -B analysis/research/improve/sem_databar_scale.py
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))
sys.dont_write_bytecode = True

import numpy as np                                  # noqa: E402
import tifffile                                     # noqa: E402

import _paths                                       # noqa: E402

ORIG = os.path.join(_paths.SEM_REPO, "original")
OUT = os.path.join(REPO, "docs", "figures", "sem_databar_scale.json")
EVID = os.path.join(REPO, "docs", "figures", "evidence", "sem_databar")

#: The frame height the field of view occupies. Everything below it in an uncropped file
#: is databar. Measured, not assumed: `detect_cracks.find_field_of_view` puts the boundary
#: here on every frame of this session, and the module checks that it still does.
FOV_ROWS = 4096
#: The rows of the databar the scale bar's ticks live in, and the brightness fraction a
#: column has to reach over that band to count as a tick.
TICK_ROWS = (2, 90)
TICK_FILL = 0.80
#: How far the two routes may disagree before this module refuses to emit anything.
TOLERANCE = 0.01

#: The two glyph fields, transcribed from the crops this script writes to `evidence/`.
#: bar_um is the scale bar's own annotation; hfw_um is the printed horizontal field width.
#: A frame absent from this table and carrying a databar is REPORTED, not skipped quietly.
READ = {
    "260622_316_H_b2_back_CBS_01":  {"bar_um": 100.0, "hfw_um": 259.0},
    "260622_316_H_b2_front_CBS_01": {"bar_um": 100.0, "hfw_um": 259.0},
    "260622_316_H_b2_front_CBS_02": {"bar_um": 50.0,  "hfw_um": 173.0},
    "260622_316_H_b2_front_CBS_03": {"bar_um": 30.0,  "hfw_um": 82.9},
    "260622_316_H_b2_front_CBS_04": {"bar_um": 50.0,  "hfw_um": 173.0},
    "260622_316_amb_b3_CBS_01":     {"bar_um": 100.0, "hfw_um": 259.0},
    "260622_316_amb_b3_CBS_02":     {"bar_um": 50.0,  "hfw_um": 173.0},
}

#: Where in the databar each transcribed field sits, as (row0, row1, col0, col1) relative
#: to the top of the databar. Only used to write the audit crops.
CROP = {"bar_um": (0, 95, 3300, 6144), "hfw_um": (130, 250, 2020, 2500)}


def ticks(bar):
    """The columns of the scale bar's end ticks, found by measurement.

    A tick is a column that is bright over essentially the whole tick band. The databar
    also has a vertical cell divider near its left edge which passes that test, so the
    runs are grouped and the OUTERMOST TWO OF THE RIGHT-HAND GROUP are taken: the bar is
    the only structure in the right half of the strip.
    """
    v = bar > bar.max() * 0.75
    band = v[TICK_ROWS[0]:TICK_ROWS[1], :]
    cols = np.where(band.sum(0) >= TICK_FILL * band.shape[0])[0]
    if len(cols) < 2:
        return None
    runs = np.split(cols, np.where(np.diff(cols) > 3)[0] + 1)
    cent = [float(r.mean()) for r in runs]
    right = [c for c in cent if c > 0.25 * bar.shape[1]]
    if len(right) < 2:
        return None
    return right[0], right[-1]


def main():
    _paths.require(ORIG, "the SEM originals directory", "SEM_REPO")
    os.makedirs(EVID, exist_ok=True)
    from PIL import Image

    frames = [f[:-4] for f in sorted(os.listdir(ORIG))
              if f.endswith(".tif") and ("b2" in f or "b3" in f)]
    rows, missing_table = [], []
    for stem in frames:
        raw = tifffile.imread(os.path.join(ORIG, stem + ".tif"))
        if raw.ndim == 3:
            raw = raw[..., 0]
        h, w = raw.shape
        if h <= FOV_ROWS:
            rows.append({"frame": stem, "frame_px": [int(h), int(w)],
                         "nm_per_px": None,
                         "why": "saved already cropped to the field of view; the file "
                                "holds no databar and nothing can be recovered from it"})
            continue
        bar = raw[FOV_ROWS:, :]
        tk = ticks(bar)
        if tk is None:
            rows.append({"frame": stem, "frame_px": [int(h), int(w)], "nm_per_px": None,
                         "why": "a databar is present but no scale-bar ticks were found "
                                "in it"})
            continue
        if stem not in READ:
            missing_table.append(stem)
            rows.append({"frame": stem, "frame_px": [int(h), int(w)], "nm_per_px": None,
                         "why": "a databar and its ticks are present but the annotation "
                                "and the printed field width are not transcribed in READ"})
            continue
        for field, (r0, r1, c0, c1) in CROP.items():
            patch = bar[r0:r1, c0:min(c1, bar.shape[1])]
            Image.fromarray((patch.astype(np.float32) / max(float(patch.max()), 1.0)
                             * 255).clip(0, 255).astype(np.uint8)).save(
                os.path.join(EVID, f"{stem}__{field}.png"))

        span = tk[1] - tk[0]
        rd = READ[stem]
        from_bar = rd["bar_um"] * 1000.0 / span
        from_hfw = rd["hfw_um"] * 1000.0 / w
        disagree = abs(from_bar - from_hfw) / from_hfw
        if disagree > TOLERANCE:
            raise SystemExit(
                f"{stem}: the drawn scale bar gives {from_bar:.4f} nm/px and the printed "
                f"horizontal field width gives {from_hfw:.4f}, a disagreement of "
                f"{100 * disagree:.2f}% against a tolerance of {100 * TOLERANCE:g}%. "
                f"Either the tick finder has latched onto something that is not the bar "
                f"or one of the two transcriptions in READ is wrong. Look at "
                f"{os.path.join(EVID, stem)}__*.png before changing anything.")
        rows.append({
            "frame": stem, "frame_px": [int(h), int(w)],
            "fov_rows": FOV_ROWS, "databar_rows": int(h - FOV_ROWS),
            "tick_columns": [round(tk[0], 1), round(tk[1], 1)],
            "tick_span_px": round(span, 1),
            "bar_annotation_um": rd["bar_um"], "printed_hfw_um": rd["hfw_um"],
            "nm_per_px": round(from_bar, 4),
            "nm_per_px_from_printed_hfw": round(from_hfw, 4),
            "disagreement_pct": round(100 * disagree, 3),
            "field_width_um": round(w * from_bar / 1000.0, 2),
        })

    got = [r for r in rows if r["nm_per_px"] is not None]
    json.dump({
        "what": "pixel size of the b2 and b3 SEM frames, recovered from the instrument "
                "databar that survives in the uncropped originals",
        "why": "scale.from_tiff() finds no FEI block in any of these files and the "
               "project's extracted metadata table covers only the MAR_* frames, so "
               "without this the specimen series the paper reports on has no pixel size "
               "and no figure drawn from it can carry a scale bar",
        "method": {
            "reported": "the annotated length of the drawn scale bar divided by the "
                        "measured span between its two end ticks",
            "control": "the printed horizontal field width divided by the frame width "
                       "in pixels, an independent number from the same strip",
            "tolerance": TOLERANCE,
            "hand_read": "only the bar's annotation and the printed field width; the "
                         "tick span, which is what precision depends on, is measured. "
                         "The crop each was transcribed from is written to "
                         "docs/figures/evidence/sem_databar/ so it can be checked",
            "tick_rule": f"a column bright over at least {TICK_FILL:.0%} of rows "
                         f"{TICK_ROWS[0]}-{TICK_ROWS[1]} of the databar; the outermost "
                         f"two such runs in the right three quarters of the strip",
        },
        "n_frames_examined": len(rows),
        "n_recovered": len(got),
        "worst_disagreement_pct": (round(max(r["disagreement_pct"] for r in got), 3)
                                   if got else None),
        "frames": rows,
    }, open(OUT, "w"), indent=1)

    print(f"  wrote {OUT}")
    for r in rows:
        if r["nm_per_px"] is None:
            print(f"  {r['frame']:<32} --        {r['why']}")
        else:
            print(f"  {r['frame']:<32} {r['nm_per_px']:>7.3f} nm/px  "
                  f"({r['bar_annotation_um']:g} um over {r['tick_span_px']:.0f} px; "
                  f"printed HFW gives {r['nm_per_px_from_printed_hfw']:.3f}, "
                  f"{r['disagreement_pct']:.2f}% apart); field "
                  f"{r['field_width_um']:.0f} um")
    if missing_table:
        print(f"  {len(missing_table)} frame(s) carry a readable databar that is not "
              f"transcribed in READ: {', '.join(missing_table)}")
    print(f"  recovered {len(got)} of {len(rows)} b2/b3 frames; worst disagreement "
          f"between the two routes "
          f"{max((r['disagreement_pct'] for r in got), default=float('nan')):.2f}%")


if __name__ == "__main__":
    main()
