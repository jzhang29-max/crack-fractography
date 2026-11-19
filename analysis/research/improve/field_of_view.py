#!/usr/bin/env python3
"""The seven constants that choose WHICH PIXELS EXIST, measured for the first time.

WHY THIS FAMILY IS DIFFERENT FROM EVERY OTHER PARAMETER SWEEP IN THIS PROJECT. The seven
constants below are Figure 6's `_detect_databar_top` and `find_field_of_view` rows, all
lettered F -- "kwarg default, never measured". They do not decide whether a pixel is
called crack. They decide whether a pixel is LOOKED AT. `find_field_of_view` runs as
run_unified_pipeline's second statement, before flattening, before the darkness ladder,
before everything, and every area fraction, every per-mm^2 density and every "percent of
frame marked" this project reports is a numerator divided by the area these seven
constants chose. A crop that is wrong on one capture type makes every physical number
computed from that capture type wrong, and nothing downstream says a word: the mask is
written at the cropped size and the cropped size becomes the denominator.

WHAT IS MEASURED HERE, IN ORDER.

  1. INVENTORY, over every .tif in <SEM>/original. Per frame: the shipped box, the input
     shape, the rows and columns trimmed, and -- the part that makes this an audit rather
     than a sweep -- what the trimmed band actually CONTAINS. A databar background is a
     near-solid fill with burned-in text; specimen is not. The separator used is the modal
     grey fraction (what share of the band sits at its single most common DN) measured
     against an equal-height reference band of specimen taken immediately above the cut.
     Both numbers are reported per frame so the rule can be checked rather than believed.

  2. GROUND TRUTH, on the 80 frames that carry an FEI/Thermo metadata block in the TIFF
     tail. `ResolutionY` there is the SCAN height -- the image excluding the burned-in
     panel -- so `ResolutionY` IS the correct bar_top, read from the instrument and not
     from any detector. (The block's own `DatabarHeight` field reads 0 on all 80 and is
     useless; file_height - ResolutionY is the bar.) That turns the sweep into an accuracy
     measurement on 80 frames: for every setting of every constant, how many of the 80
     land on the instrument's own answer.

  3. SWEEP, one constant at a time off the shipped point, over the whole corpus. Reported
     per constant: how many frames change box at any value in the bracket (0 = INERT), the
     largest area change, and the accuracy curve against the 80 ground-truth frames.

CONTROLS, AND THEY FAIL LOUDLY.
  A. REPRODUCTION. The parameterised copies below are line-for-line the shipped ones. On
     EVERY frame, `_fov(img8, **SHIPPED)` must equal `D.find_field_of_view(img8)` and
     `_databar_top(img8, **SHIPPED)` must equal `D._detect_databar_top(img8)`, exactly.
     One mismatch aborts the run before any swept number is written.
  B. THE INSTRUMENT MUST BE ABLE TO MOVE. A sweep that reports "nothing changed" is
     indistinguishable from a harness that is not wired up. `bright_thresh=250` gates out
     essentially every pixel of an 8-bit frame and MUST change the box on most frames; if
     it does not, the comparison is broken and the run aborts. This is the positive
     control, and it is deliberately not one of the swept values.
  C. CONTRAST. The pipeline reads three frames at a 0/100 stretch rather than 1/99.5
     (common.GENTLE_CONTRAST_IMAGES). `find_field_of_view` thresholds the STRETCHED image
     at 12 DN, so the stretch is upstream of the crop. Each frame is loaded with its own
     shipped contrast, as tools/build_release.sem_fov_box does.

WHAT THIS CANNOT ESTABLISH. 74 of the 154 originals carry no FEI block, so for those the
only check available is the band-content audit, not an instrument truth. The six
261113_MAR247_HIP_H_Int_Test_* frames verified by hand are not in this checkout.

Run:
    /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python -B \
        analysis/research/improve/field_of_view.py
Writes docs/figures/field_of_view.json. Writes nothing else, and reads <SEM> read-only.
"""
import json
import math
import os
import re
import sys
import time
import warnings

warnings.filterwarnings("ignore")
import numpy as np                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))
import _paths                                        # noqa: E402
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "code"))
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "interior_active_learning", "code"))
sys.dont_write_bytecode = True

import tifffile                                      # noqa: E402
from skimage import exposure                         # noqa: E402
import detect_cracks as D                            # noqa: E402
from common import contrast_kwargs_for               # noqa: E402

SEM = _paths.SEM_REPO
ORIG = os.path.join(SEM, "original")
OUT = os.path.join(REPO, "docs", "figures", "field_of_view.json")

#: The seven, with where they live and what they ship as. Read off the source by ast in
#: mk_parameters.py; repeated here as literals so a drift between the two is visible, and
#: asserted against the live signature below.
SHIPPED_BAR = dict(search_frac=0.25, window=10, std_ratio=0.4, mean_ratio=0.85)
SHIPPED_FOV = dict(bright_thresh=12, shrink_frac=0.16, min_keep_frac=0.2)

#: One-at-a-time brackets. Each spans well past any plausible tuned value in both
#: directions, so "inert" means inert, not "inert within +-10%".
BRACKETS = {
    "bright_thresh": [0, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 32, 48, 64, 96],
    "shrink_frac": [0.0, 0.04, 0.08, 0.12, 0.16, 0.20, 0.24, 0.30, 0.40, 0.50],
    "min_keep_frac": [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60,
                      0.70, 0.80, 0.90],
    "search_frac": [0.02, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50],
    "window": [1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 80, 120],
    "std_ratio": [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95],
    "mean_ratio": [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98, 1.0],
}
BAR_NAMES = ("search_frac", "window", "std_ratio", "mean_ratio")
FOV_NAMES = ("bright_thresh", "shrink_frac", "min_keep_frac")

#: Figure 6's row label for each, so the finding can be pasted back onto the plate.
FIG6_ROW = {
    "search_frac": "databar search depth",
    "window": "databar window (rows)",
    "std_ratio": "databar sd ratio",
    "mean_ratio": "databar mean ratio",
    "bright_thresh": "field-of-view gate (DN)",
    "shrink_frac": "field-of-view shrink",
    "min_keep_frac": "field-of-view floor",
}


# ---------------------------------------------------------------- parameterised copies
def _databar_top(img8, search_frac=0.25, window=10, std_ratio=0.4, mean_ratio=0.85):
    """Line-for-line `detect_cracks._detect_databar_top`, with its kwargs reachable."""
    h, w = img8.shape
    search_start = int(h * (1 - search_frac))
    rows = img8[search_start:].astype(np.float32)
    if rows.shape[0] < window + 5:
        return h

    bar_top_stat = h
    row_means = rows.mean(axis=1)
    row_stds = rows.std(axis=1)
    for i in range(window, len(row_means)):
        baseline_std = row_stds[i - window:i].max()
        baseline_mean = row_means[i - window:i].max()
        if (baseline_std > 3 and row_stds[i] < baseline_std * std_ratio
                and row_means[i] < baseline_mean * mean_ratio):
            bar_top_stat = search_start + i
            break

    bar_top_edge = h
    best_frac, best_row = 0.0, None
    for i in range(1, rows.shape[0]):
        frac = float((np.abs(rows[i] - rows[i - 1]) > 10).mean())
        if frac > best_frac:
            best_frac, best_row = frac, search_start + i
    if best_frac >= 0.60 and best_row is not None and h - best_row >= 20:
        bar_top_edge = best_row

    return min(bar_top_stat, bar_top_edge)


def _fov(img8, bright_thresh=12, shrink_frac=0.16, min_keep_frac=0.2, bar_kw=None):
    """Line-for-line `detect_cracks.find_field_of_view`, with its kwargs reachable.

    `bar_kw` is the only addition: the shipped function calls `_detect_databar_top(img8)`
    with no arguments, so the four databar constants are unreachable from outside without
    this hook. With bar_kw=None it is byte-identical in behaviour to the shipped call.
    """
    h, w = img8.shape
    bar_top = _databar_top(img8, **(bar_kw or SHIPPED_BAR))
    workspace = img8[:bar_top].astype(np.float32)
    row_ok = np.where(workspace.mean(axis=1) > bright_thresh)[0]
    col_ok = np.where(workspace.mean(axis=0) > bright_thresh)[0]
    if len(row_ok) == 0 or len(col_ok) == 0:
        return 0, 0, w, bar_top

    y0, y1 = int(row_ok.min()), int(row_ok.max())
    x0, x1 = int(col_ok.min()), int(col_ok.max())
    fills_workspace = (x1 - x0) > 0.97 * w and (y1 - y0) > 0.97 * bar_top

    corner_size = max(20, int(0.03 * min(w, bar_top)))
    corners = [
        workspace[:corner_size, :corner_size].mean(),
        workspace[:corner_size, -corner_size:].mean(),
        workspace[-corner_size:, :corner_size].mean(),
        workspace[-corner_size:, -corner_size:].mean(),
    ]
    looks_like_round_vignette = all(c < bright_thresh for c in corners)

    if fills_workspace or not looks_like_round_vignette:
        x0, y0, x1, y1 = 0, 0, w, bar_top
    else:
        cy, cx = (y0 + y1) / 2, (x0 + x1) / 2
        radius = max(y1 - y0, x1 - x0) / 2
        half_side = radius / math.sqrt(2) * (1 - shrink_frac)
        y0, y1 = int(cy - half_side), int(cy + half_side)
        x0, x1 = int(cx - half_side), int(cx + half_side)
        y0, x0 = max(y0, 0), max(x0, 0)
        y1, x1 = min(y1, bar_top), min(x1, w)

    if (x1 - x0) * (y1 - y0) < min_keep_frac * w * h:
        return 0, 0, w, bar_top
    return x0, y0, x1, y1


# ------------------------------------------------------------------------ ground truth
_FEI_TAIL = 400_000


def fei_scan_height(path):
    """(ResolutionX, ResolutionY) from the FEI/Thermo block in the TIFF tail, or None.

    ResolutionY is the SCAN height: the burned-in panel is appended below it, so the
    instrument's own answer for bar_top is exactly ResolutionY. Read the same way
    analysis/scale.from_tiff reads PixelWidth, from the raw tail with the stdlib.
    """
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, size - _FEI_TAIL))
            txt = fh.read().decode("latin-1")
    except OSError:
        return None
    i = txt.find("[User]")
    if i < 0:
        i = txt.find("[System]")
    if i < 0:
        return None
    blk = txt[i:]
    out = {}
    for key in ("ResolutionX", "ResolutionY"):
        m = re.search("^" + key + r"=(\d+)\s*$", blk, re.M)
        if not m:
            return None
        out[key] = int(m.group(1))
    return out["ResolutionX"], out["ResolutionY"]


# ------------------------------------------------------------------- band content audit
def band_profile(img8, r0, r1):
    """What a horizontal band CONTAINS, in the terms that separate panel from specimen."""
    b = img8[max(r0, 0):max(r1, 0)]
    if b.size == 0:
        return None
    cnt = np.bincount(b.ravel(), minlength=256)
    rs = b.std(axis=1)
    return dict(
        rows=int(b.shape[0]),
        mean=round(float(b.mean()), 2),
        std=round(float(b.std()), 2),
        #: a solid panel fill puts most of the band on ONE grey level; specimen does not
        modal_dn=int(cnt.argmax()),
        modal_frac=round(float(cnt.max()) / b.size, 4),
        #: burned-in text is near-white on that fill
        bright_frac=round(float((b > 200).mean()), 4),
        dark_frac=round(float((b < 12).mean()), 4),
        #: rows of pure fill have no horizontal variation at all
        flat_row_frac=round(float((rs < 3).mean()), 4),
    )


#: A band is called panel when it is mostly one grey level AND far more so than the
#: specimen band of equal height directly above it. Both halves matter: some specimens are
#: genuinely flat, and a ratio alone would call them panels.
PANEL_MODAL_MIN = 0.25
PANEL_MODAL_RATIO = 4.0


def is_panel(trim, ref):
    if trim is None:
        return None
    if ref is None:
        return bool(trim["modal_frac"] >= PANEL_MODAL_MIN)
    return bool(trim["modal_frac"] >= PANEL_MODAL_MIN
                and trim["modal_frac"] >= PANEL_MODAL_RATIO * ref["modal_frac"])


def main():
    t0 = time.time()
    # the literals above must still be the live defaults, or the sweep is off-centre
    import inspect
    for fn, want in ((D._detect_databar_top, SHIPPED_BAR),
                     (D.find_field_of_view, SHIPPED_FOV)):
        sig = inspect.signature(fn)
        for k, v in want.items():
            got = sig.parameters[k].default
            if got != v:
                raise SystemExit(f"{fn.__name__}.{k} ships as {got!r}, not {v!r} -- this "
                                 f"script's bracket is centred on the wrong value")

    files = sorted(f for f in os.listdir(ORIG) if f.lower().endswith(".tif"))
    print(f"{len(files)} originals in {ORIG}\n")

    per_frame = []
    # settings[const][value] -> list of boxes, index-aligned with per_frame
    settings = {c: {v: [] for v in BRACKETS[c]} for c in BRACKETS}
    poscontrol_moved = 0
    gt_n = 0

    for fi, fn in enumerate(files):
        stem = fn[:-4]
        path = os.path.join(ORIG, fn)
        raw = tifffile.imread(path)
        if raw.ndim == 3:
            raw = raw[..., 0]
        ck = contrast_kwargs_for(stem)
        lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
        img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                          out_range=(0, 255)).astype(np.uint8)
        del raw
        h, w = img8.shape

        # ---- CONTROL A: the copies must reproduce the shipped functions exactly
        ship_bar = int(D._detect_databar_top(img8))
        mine_bar = int(_databar_top(img8, **SHIPPED_BAR))
        if mine_bar != ship_bar:
            raise SystemExit(f"{stem}: _databar_top copy gave {mine_bar}, shipped gave "
                             f"{ship_bar} -- harness does not reproduce the pipeline")
        ship_box = tuple(int(v) for v in D.find_field_of_view(img8))
        mine_box = tuple(int(v) for v in _fov(img8, **SHIPPED_FOV))
        if mine_box != ship_box:
            raise SystemExit(f"{stem}: _fov copy gave {mine_box}, shipped gave {ship_box}"
                             f" -- harness does not reproduce the pipeline")

        x0, y0, x1, y1 = ship_box
        trim_bottom, trim_top = h - y1, y0
        trim_left, trim_right = x0, w - x1

        # ---- what the trimmed band contains, against specimen of the same height
        nb = trim_bottom if trim_bottom > 0 else 0
        trim_prof = band_profile(img8, y1, h) if nb else None
        ref_prof = band_profile(img8, max(y1 - nb, 0), y1) if nb else None
        # ---- and, for frames with no trim, whether a panel was LEFT IN
        probe_h = max(20, int(round(h * 0.064)))      # 280/4376, the FEI panel fraction
        kept_tail = band_profile(img8, max(y1 - probe_h, 0), y1)
        kept_ref = band_profile(img8, max(y1 - 2 * probe_h, 0), max(y1 - probe_h, 0))

        fei = fei_scan_height(path)
        gt_bar_top = None
        if fei and fei[0] == w and 0 <= h - fei[1] < h:
            gt_bar_top = int(fei[1])
            gt_n += 1

        row = dict(
            frame=stem, h=int(h), w=int(w),
            contrast=[ck["low_pct"], ck["high_pct"]],
            box=[x0, y0, x1, y1], bar_top=ship_bar,
            trim_bottom=int(trim_bottom), trim_top=int(trim_top),
            trim_left=int(trim_left), trim_right=int(trim_right),
            kept_px=int((x1 - x0) * (y1 - y0)),
            kept_pct_of_frame=round(100.0 * (x1 - x0) * (y1 - y0) / (w * h), 3),
            vignette_branch=bool(x0 or y0 or x1 != w or y1 != ship_bar),
            fei_scan=list(fei) if fei else None,
            gt_bar_top=gt_bar_top,
            gt_error_rows=(None if gt_bar_top is None else int(ship_bar - gt_bar_top)),
            trimmed_band=trim_prof, specimen_ref_band=ref_prof,
            trimmed_band_is_panel=is_panel(trim_prof, ref_prof),
            kept_tail=kept_tail, kept_tail_ref=kept_ref,
            kept_tail_is_panel=is_panel(kept_tail, kept_ref),
        )

        # ---- CONTROL B: the comparison must be able to see a change at all
        pc = tuple(int(v) for v in _fov(img8, bright_thresh=250,
                                        shrink_frac=SHIPPED_FOV["shrink_frac"],
                                        min_keep_frac=SHIPPED_FOV["min_keep_frac"]))
        if pc != ship_box:
            poscontrol_moved += 1

        # ---- the sweep, one constant at a time off the shipped point
        for const, values in BRACKETS.items():
            for v in values:
                if const in BAR_NAMES:
                    bk = dict(SHIPPED_BAR, **{const: v})
                    box = _fov(img8, bar_kw=bk, **SHIPPED_FOV)
                else:
                    fk = dict(SHIPPED_FOV, **{const: v})
                    box = _fov(img8, **fk)
                settings[const][v].append(tuple(int(q) for q in box))

        per_frame.append(row)
        flag = ""
        if nb and row["trimmed_band_is_panel"] is False:
            flag = "  <== TRIM IS NOT A PANEL"
        if row["gt_error_rows"] not in (None, 0):
            flag += f"  <== GT OFF BY {row['gt_error_rows']:+d} ROWS"
        if not nb and row["kept_tail_is_panel"]:
            flag += "  <== PANEL LEFT IN FRAME"
        if row["vignette_branch"]:
            flag += "  <== VIGNETTE BRANCH"
        print(f"[{fi+1:>3}/{len(files)}] {stem:<34} {h}x{w} -> {ship_box} "
              f"cut b{trim_bottom} t{trim_top} l{trim_left} r{trim_right}{flag}",
              flush=True)

    if poscontrol_moved < 0.5 * len(per_frame):
        raise SystemExit(
            f"POSITIVE CONTROL FAILED: bright_thresh=250 gates out an 8-bit frame and "
            f"moved the box on only {poscontrol_moved}/{len(per_frame)} frames. The "
            f"sweep cannot distinguish 'inert' from 'not wired up'; nothing written.")

    ship_boxes = [tuple(r["box"]) for r in per_frame]
    frame_px = [r["h"] * r["w"] for r in per_frame]

    # ------------------------------------------------------------------ summarise sweep
    const_out = {}
    for const, values in BRACKETS.items():
        ship_v = (SHIPPED_BAR if const in BAR_NAMES else SHIPPED_FOV)[const]
        assert settings[const][ship_v] == ship_boxes, f"{const}: shipped value disagrees"
        rows, moved_any = [], set()
        for v in values:
            boxes = settings[const][v]
            diff = [i for i, (a, b) in enumerate(zip(boxes, ship_boxes)) if a != b]
            moved_any.update(diff)
            dpx = [abs((boxes[i][2] - boxes[i][0]) * (boxes[i][3] - boxes[i][1])
                       - (ship_boxes[i][2] - ship_boxes[i][0])
                       * (ship_boxes[i][3] - ship_boxes[i][1])) for i in diff]
            dpct = [100.0 * d / frame_px[i] for d, i in zip(dpx, diff)]
            correct = sum(1 for r, b in zip(per_frame, boxes)
                          if r["gt_bar_top"] is not None and b[3] == r["gt_bar_top"]
                          and b[1] == 0 and b[0] == 0 and b[2] == r["w"])
            rows.append(dict(
                value=v, is_shipped=(v == ship_v),
                n_frames_box_differs=len(diff),
                max_area_change_pct=round(max(dpct), 3) if dpct else 0.0,
                median_area_change_pct=(round(float(np.median(dpct)), 3) if dpct else 0.0),
                total_px_change=int(sum(dpx)),
                n_gt_frames_exact=correct,
                frames_changed=[per_frame[i]["frame"] for i in diff][:25],
            ))
        best = max(r["n_gt_frames_exact"] for r in rows)
        const_out[const] = dict(
            figure6_row=FIG6_ROW[const],
            function=("_detect_databar_top" if const in BAR_NAMES
                      else "find_field_of_view"),
            shipped=ship_v,
            bracket=values,
            n_frames_depending=len(moved_any),
            frames_depending=sorted(per_frame[i]["frame"] for i in moved_any),
            inert=(len(moved_any) == 0),
            gt_exact_at_shipped=[r for r in rows if r["is_shipped"]][0]["n_gt_frames_exact"],
            gt_exact_best_in_bracket=best,
            gt_best_values=[r["value"] for r in rows if r["n_gt_frames_exact"] == best],
            sweep=rows,
        )

    # ----------------------------------------------------------------------- the audit
    gt_rows = [r for r in per_frame if r["gt_bar_top"] is not None]
    gt_wrong = [r for r in gt_rows if r["gt_error_rows"] != 0]
    trim_not_panel = [r for r in per_frame
                      if r["trim_bottom"] > 0 and r["trimmed_band_is_panel"] is False]
    panel_left_in = [r for r in per_frame
                     if r["trim_bottom"] == 0 and r["kept_tail_is_panel"]]
    vignette = [r for r in per_frame if r["vignette_branch"]]

    rec = dict(
        what=("the seven constants that choose the analysed region: "
              "_detect_databar_top(search_frac, window, std_ratio, mean_ratio) and "
              "find_field_of_view(bright_thresh, shrink_frac, min_keep_frac)"),
        generated=time.strftime("%Y-%m-%d"),
        corpus=ORIG,
        n_frames=len(per_frame),
        source=dict(
            file=os.path.join(_paths.SEM_REPO, "code", "detect_cracks.py"),
            _detect_databar_top_line=106, find_field_of_view_line=164),
        controls={
            "copies_reproduce_shipped": f"PASS on all {len(per_frame)} frames "
                                        f"(box and bar_top, exact)",
            "positive_control_bright_thresh_250":
                f"moved the box on {poscontrol_moved}/{len(per_frame)} frames "
                f"(required > 50%), so a zero in the sweep means inert, not unwired",
            "shipped_value_in_every_bracket": "PASS (asserted box-for-box)",
            "live_defaults_match_literals": "PASS (inspect.signature)",
        },
        ground_truth=dict(
            source="FEI/Thermo block in the TIFF tail; ResolutionY is the scan height, "
                   "so the burned-in panel starts exactly there",
            caveat="the block's own DatabarHeight field reads 0 on every frame that has "
                   "one and was not used",
            n_frames_with_truth=len(gt_rows),
            n_frames_without_truth=len(per_frame) - len(gt_rows),
            n_exact=len(gt_rows) - len(gt_wrong),
            n_wrong=len(gt_wrong),
            wrong=[dict(frame=r["frame"], detected=r["bar_top"], truth=r["gt_bar_top"],
                        error_rows=r["gt_error_rows"]) for r in gt_wrong],
        ),
        band_audit=dict(
            rule=f"a trimmed band is a panel when modal_frac >= {PANEL_MODAL_MIN} and "
                 f">= {PANEL_MODAL_RATIO}x the equal-height specimen band above it",
            n_frames_trimmed=sum(1 for r in per_frame if r["trim_bottom"] > 0),
            n_trimmed_band_is_panel=sum(1 for r in per_frame
                                        if r["trimmed_band_is_panel"]),
            n_trimmed_band_is_specimen=len(trim_not_panel),
            trim_is_specimen=[dict(frame=r["frame"], rows=r["trim_bottom"],
                                   trim_modal=r["trimmed_band"]["modal_frac"],
                                   ref_modal=r["specimen_ref_band"]["modal_frac"])
                              for r in trim_not_panel],
            n_panel_left_in_frame=len(panel_left_in),
            panel_left_in=[r["frame"] for r in panel_left_in],
            n_vignette_branch=len(vignette),
            vignette_frames=[r["frame"] for r in vignette],
        ),
        constants=const_out,
        per_frame=per_frame,
        seconds=round(time.time() - t0, 1),
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rec, open(OUT, "w"), indent=1)

    # ------------------------------------------------------------------------- console
    print(f"\nwrote {OUT}  ({rec['seconds']}s)\n")
    print(f"GROUND TRUTH (FEI ResolutionY): {rec['ground_truth']['n_exact']}/"
          f"{len(gt_rows)} exact, {len(gt_wrong)} wrong; "
          f"{rec['ground_truth']['n_frames_without_truth']} frames have no truth")
    for r in gt_wrong[:20]:
        print(f"   WRONG  {r['frame']:<34} detected {r['bar_top']} truth "
              f"{r['gt_bar_top']} ({r['gt_error_rows']:+d} rows)")
    print(f"\nBAND AUDIT: {rec['band_audit']['n_frames_trimmed']} frames trimmed; "
          f"{rec['band_audit']['n_trimmed_band_is_specimen']} of those cut SPECIMEN, "
          f"{rec['band_audit']['n_panel_left_in_frame']} left a panel in frame, "
          f"{rec['band_audit']['n_vignette_branch']} took the vignette branch")
    for r in trim_not_panel[:20]:
        print(f"   SPECIMEN CUT  {r['frame']:<34} {r['trim_bottom']:>4} rows  "
              f"modal {r['trimmed_band']['modal_frac']:.3f} vs ref "
              f"{r['specimen_ref_band']['modal_frac']:.3f}")
    for n in rec["band_audit"]["panel_left_in"][:20]:
        print(f"   PANEL LEFT IN {n}")

    print(f"\n{'constant':<16} {'fn':<21} {'ship':>6} {'frames':>7} {'verdict':<12} "
          f"{'gt@ship':>8} {'gt@best':>8}  best values")
    for c, v in const_out.items():
        print(f"{c:<16} {v['function']:<21} {str(v['shipped']):>6} "
              f"{v['n_frames_depending']:>7} "
              f"{'INERT' if v['inert'] else 'load-bearing':<12} "
              f"{v['gt_exact_at_shipped']:>8} {v['gt_exact_best_in_bracket']:>8}  "
              f"{v['gt_best_values']}")
    return rec


if __name__ == "__main__":
    main()
