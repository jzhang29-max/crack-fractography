#!/usr/bin/env python3
"""The percentile contrast window that makes the 8-bit image every later stage reads.

WHY THIS EXISTS. `detect_cracks.load_as_uint8(path, low_pct=1.0, high_pct=99.5)` maps the
raw 16-bit micrograph onto 0..255 by clipping at those two percentiles. It runs FIRST --
before find_field_of_view, before flatten_background, before the 7-rung darkness ladder,
before the absolute gate `img8 < 10` -- so every pixel the detector has ever seen passed
through it. Figure 6 letters it F and its justification record says, in as many words,
"a kwarg default on load_as_uint8; the docstring measures nothing and no sweep of the
percentiles exists". This is that sweep: low_pct over (0, 0.1, 0.5, 1, 2, 5) crossed with
high_pct over (95, 98, 99, 99.5, 99.9, 100), 36 settings, shipped pair (1.0, 99.5).

WHY THERE IS NO TILE ARM, AND WHY THAT IS A MEASUREMENT AND NOT AN EXCUSE. The 26
hand-labelled 512 px tiles are the cheap instrument for every other constant in this
project, and the tile cache does keep the uint16 `raw` crop, so re-stretching looks
available. It is not, for a reason the cache's own code makes plain:

    tilebench.build_cache:  lo, hi = np.percentile(raw, [1.0, 99.5])      # the 512px CROP
    detect_cracks.load_as_uint8:  lo, hi = np.percentile(img, [...])      # the WHOLE frame

A percentile is a property of the population it is taken over. The shipped constant selects
a window from the whole micrograph; a tile re-stretch would select one from a 512 px crop,
which is per-tile autocontrast -- a different operation that happens to share a parameter
name. TILE_CONTROL below measures the gap instead of asserting it, and RAISES if the two
agree, because the only thing that would justify a tile arm is them agreeing. (It also
means the cached img8 is NOT, as build_cache's docstring claims, byte-identical to what
the pipeline would have seen. Nothing else here depends on that, but it is true.)
Recovering the correct window needs the parent micrograph read at full size, which is the
cost the tile cache exists to avoid -- so the frames are not a fallback here, they are the
only instrument, and the whole measurement is made on them.

WHAT THE CONSTANT CAN AND CANNOT DO, BEFORE ANY DATA -- because this bounds how big any
result here is allowed to be, and a row that exceeds its own mechanism is a bug, not a
finding. Downstream of this stretch, flatten_background re-stretches the residual by ITS
own percentiles and segment_dark_regions cuts at `min(otsu(sm), median(sm) - k*MAD(sm))`.
Every one of those is affine-EQUIVARIANT: in exact arithmetic on unclipped floats the
RELATIVE cut would select the identical pixels for every (low_pct, high_pct), and this
constant would do nothing at all. Its whole effect runs through three channels, each
measured per setting below rather than argued:

  SATURATION      rescale_intensity clips outside [lo, hi], so pixels below lo pin at 0
                  and above hi pin at 255 -- sat_lo_pct, sat_hi_pct.
  QUANTISATION    two uint8 casts; a wider window is a coarser grey grid.
  THE ABSOLUTE GATE, which is the one that is not equivariant at all and is therefore
                  expected to dominate. segment_dark_regions ORs in `img8 < 10` against
                  the un-flattened stretched image, comparing a RESCALED value to a FIXED
                  number, so moving the window moves that set directly -- and this repo
                  already records the gate as roughly half of all recall. gate_px counts
                  it per setting.

A fourth channel is NOT a channel at all for most of this grid, and it is the reason so
many rows here are byte-identical: a percentile is clamped by the data. Where a frame has
more than low_pct percent of its pixels at the raw floor (a black databar, a dead border),
every low_pct in this grid returns the SAME lo and the same image. n_distinct_img8_over_
grid and n_frames_identical_img8_to_default count that, so "no effect" is never confused
with "the knob was never turned" -- CONTROL 3 raises if a frame turns out to have one.

SCORED ON THE CORRECTION MASKS, read only: 1 = crack, 2 = not-crack, 3 = erased (also a
not-crack verdict), 0 = unreviewed and excluded from both. Per frame as well as pooled,
because this project has twice had a pooled recall that was a handful of frames.

FRAME SELECTION IS NOT ALPHABETICAL, for the reason the repo already records: a previous
before/after was taken on "the ALPHABETICALLY FIRST 12" frames and they came from two
specimens. Up to PER_SPECIMEN frames from each specimen in turn.

AND IT IS NOT ALLOWED TO MISS THE THREE FRAMES THAT ALREADY OVERRIDE THIS CONSTANT.
common.GENTLE_CONTRAST_IMAGES names three captures that the shipped pipeline runs at
(0.0, 100.0) instead of (1.0, 99.5), by hand, because they are too low-contrast for the
default -- so they are the only frames in the corpus where someone has already decided
this constant is wrong. The round-robin above picks none of them (it takes CBS_01/CBS_03
and CBS_001/CBS_002, never CBS_04, CBS_009 or CBS_010), which would have measured the
constant exclusively on the frames nobody needed to override it on. They are appended to
the sample and flagged, and their pooled block is reported SEPARATELY from the
round-robin's, because they are a different unit set and must not be averaged into it.
The set is imported from common.py, not copied, so a frame joining or leaving it moves
this measurement too.

ONE PIXEL GRID FOR EVERY ARM. find_field_of_view thresholds the 8-bit image at 12, so the
crop box is itself downstream of this constant and can move with it. Every arm is scored
inside the SHIPPED box so that "pixels this setting deletes" is defined at all; whether the
box moved is measured separately and reported per setting (fov_box_changed_on_frames). A
setting that moves the box is not fully described by its row here and the record says so.

RECALL IS READ AGAINST MARKED AREA OR IT IS NOT READ. The candidate stage already marks
~20% of a frame, and widening the window marks more, so recall alone ranks whichever
setting paints most. Every row carries pct_of_frame_marked and lift_over_mark_everything
(= recall / marked fraction), which a setting that only dilates cannot move.

Run:  NFRAMES=14 <sem-venv>/bin/python -B analysis/research/improve/contrast_window.py
Writes docs/figures/contrast_window.json.
"""
import hashlib
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np
import tifffile
from PIL import Image
from scipy import ndimage as ndi
from skimage import exposure

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))
import _paths                                        # noqa: E402
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "code"))
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "interior_active_learning", "code"))
sys.dont_write_bytecode = True

import detect_cracks as D                            # noqa: E402  (shipped stages)
import detector_overrides as DO                      # noqa: E402  (shipped constants)
from common import GENTLE_CONTRAST_IMAGES, contrast_kwargs_for   # noqa: E402

Image.MAX_IMAGE_PIXELS = None
SEM = _paths.SEM_REPO
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
OUT = os.path.join(REPO, "docs", "figures", "contrast_window.json")

LOWS = (0.0, 0.1, 0.5, 1.0, 2.0, 5.0)
HIGHS = (95.0, 98.0, 99.0, 99.5, 99.9, 100.0)
SHIPPED = (1.0, 99.5)
GATE = int(DO.ABSOLUTE_DARK_THRESH)
MAD_K = 5.0
PER_SPECIMEN = int(os.environ.get("PER_SPECIMEN", "2"))
LIMIT = int(os.environ.get("NFRAMES", "14"))
MIN_PAINT = 20000
N_TILE_CONTROL = int(os.environ.get("NTILES", "26"))


def key(lo, hi):
    return f"lo{lo}_hi{hi}"


GRID = [(lo, hi) for lo in LOWS for hi in HIGHS if lo < hi]
SHIPPED_KEY = key(*SHIPPED)
assert SHIPPED in GRID, "the shipped pair must be in the grid or nothing is a baseline"


def stretch(raw, low_pct, high_pct):
    """load_as_uint8's body, applied to an array already in memory.

    Byte-equality with the shipped function is not assumed -- CONTROL 1 checks it.
    """
    lo, hi = np.percentile(raw, [low_pct, high_pct])
    return exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8), float(lo), float(hi)


def specimen_of(name):
    """Coarse specimen key: everything before the trailing capture index."""
    parts = name.split("_")
    while parts and (parts[-1].isdigit() or parts[-1] in ("CBS", "ETD", "SE", "BSE")):
        parts.pop()
    return "_".join(parts) or name


def candidates(mask):
    """The cleaning chain's candidate stage, as absdark_frames.py and
    ladder_endpoints_frames.py run it."""
    lab, _ = ndi.label(D.clean_mask(mask, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel())
    keep = np.where(sz >= 40)[0]
    return np.isin(lab, keep[keep > 0])


def tile_control():
    """Can the 26 tiles test this constant? Measure, do not assert.

    For every tile: the window the SHIPPED code would pick (percentiles over the whole
    parent micrograph) against the window a tile re-stretch would pick (percentiles over
    the 512 px crop). RAISES if they agree, because agreement is the only thing that would
    make a tile arm legitimate, and this script's entire justification for not having one
    is that they do not.
    """
    TB = _paths.tilebench()
    tiles = TB.load(with_raw=True)
    rows, parents = [], {}
    for t in tiles[:N_TILE_CONTROL]:
        p = t["parent"]
        if p not in parents:
            a = tifffile.imread(os.path.join(SEM, "original", p + ".tif"))
            parents[p] = a[..., 0] if a.ndim == 3 else a
        flo, fhi = (float(v) for v in np.percentile(parents[p], list(SHIPPED)))
        clo, chi = (float(v) for v in np.percentile(t["raw"], list(SHIPPED)))
        # How far apart are the two maps? A raw value's 8-bit output under each.
        span_f, span_c = max(fhi - flo, 1e-9), max(chi - clo, 1e-9)
        probe = np.linspace(float(t["raw"].min()), float(t["raw"].max()), 256)
        out_f = np.clip((probe - flo) / span_f, 0, 1) * 255
        out_c = np.clip((probe - clo) / span_c, 0, 1) * 255
        rows.append(dict(tile=t["frame"], parent=p,
                         full_frame_window=[round(flo, 1), round(fhi, 1)],
                         crop_window=[round(clo, 1), round(chi, 1)],
                         mean_abs_8bit_difference=round(float(np.abs(out_f - out_c).mean()), 2)))
    n_same = sum(1 for r in rows if r["full_frame_window"] == r["crop_window"])
    if n_same == len(rows):
        raise SystemExit(
            "TILE_CONTROL: the crop window equals the full-frame window on every tile, so "
            "the tiles COULD test this constant and this script is wrong to skip them.")
    print(f"  TILE_CONTROL: the 512 px crop's own window differs from the frame window on "
          f"{len(rows) - n_same}/{len(rows)} tiles; median 8-bit map difference "
          f"{np.median([r['mean_abs_8bit_difference'] for r in rows]):.1f}/255. "
          f"NO TILE ARM.")
    return rows


def main():
    t0 = time.time()
    tiles_say = tile_control()

    names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
                   if f.endswith("_correction_mask.png"))
    names = [n for n in names
             if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
    by_spec = defaultdict(list)
    for n in names:
        by_spec[specimen_of(n)].append(n)
    chosen, round_ = [], 0
    while len(chosen) < LIMIT and round_ < PER_SPECIMEN:
        for s in sorted(by_spec):
            if round_ < len(by_spec[s]) and len(chosen) < LIMIT:
                chosen.append(by_spec[s][round_])
        round_ += 1
    roundrobin = list(chosen)

    # The three frames the shipped pipeline ALREADY overrides this constant on. Without
    # them the sweep measures the constant only where nobody found it wanting.
    gentle = sorted(g for g in GENTLE_CONTRAST_IMAGES if g in names)
    if not gentle:
        raise SystemExit("common.GENTLE_CONTRAST_IMAGES matched no painted frame with an "
                         "original; the known-sensitive arm would be silently empty")
    for g in gentle:
        if g not in chosen:
            chosen.append(g)
    # ---- CONTROL 0: the override those frames receive must be a point of this grid, or
    #      the sweep cannot say anything about the decision the repo already made.
    for g in gentle:
        kw = contrast_kwargs_for(g)
        if (kw["low_pct"], kw["high_pct"]) not in GRID:
            raise SystemExit(f"{g}'s shipped override {kw} is not a point of this grid")
    print(f"\n{len(roundrobin)} round-robin frames from "
          f"{len({specimen_of(n) for n in roundrobin})} specimens (up to {PER_SPECIMEN} "
          f"each) + {len([g for g in gentle if g not in roundrobin])} GENTLE_CONTRAST "
          f"frames the pipeline already overrides = {len(chosen)}, out of {len(names)} "
          f"painted frames with an original")
    print(f"  gentle-contrast frames: {', '.join(gentle)}  "
          f"(shipped override {contrast_kwargs_for(gentle[0])})\n")

    class _U:
        pass
    u = _U()
    DO.install(u)                       # the shipped 7-rung ladder + absolute gate

    per_frame, fov_moved = [], []

    for n in chosen:
        try:
            path = os.path.join(SEM, "original", n + ".tif")
            raw = tifffile.imread(path)
            if raw.ndim == 3:
                raw = raw[..., 0]

            # ---- CONTROL 1: this script's reconstruction of the shipped setting must be
            #      byte-identical to the shipped function. Everything below is a delta
            #      against it, so if this is off by a level nothing here means anything.
            ship8, slo, shi = stretch(raw, *SHIPPED)
            if not np.array_equal(ship8, D.load_as_uint8(path)):
                raise SystemExit(f"{n}: stretch(raw, 1.0, 99.5) != D.load_as_uint8(path); "
                                 f"the baseline is not the shipped baseline")
            if not np.array_equal(ship8, D.load_as_uint8(path, low_pct=SHIPPED[0],
                                                         high_pct=SHIPPED[1])):
                raise SystemExit(f"{n}: the shipped kwarg defaults are not {SHIPPED}")

            x0, y0, x1, y1 = D.find_field_of_view(ship8)       # THE one pixel grid
            corr = np.array(Image.open(os.path.join(PAINT, n + "_correction_mask.png")))
            corr = corr[..., 0] if corr.ndim == 3 else corr
            shape = (y1 - y0, x1 - x0)
            if corr.shape != shape:
                if corr.shape[0] >= y1 and corr.shape[1] >= x1:
                    corr = corr[y0:y1, x0:x1]
                else:
                    print(f"{n:<36} SKIP: correction mask {corr.shape} vs {shape}")
                    continue
            crack, notc = corr == 1, (corr == 2) | (corr == 3)
            n_crack, n_notc = int(crack.sum()), int(notc.sum())
            if n_crack < MIN_PAINT:
                continue

            row = dict(frame=n, specimen=specimen_of(n), raw_shape=list(raw.shape),
                       in_roundrobin=n in roundrobin,
                       gentle_contrast_frame=n in GENTLE_CONTRAST_IMAGES,
                       shipped_window_for_this_frame=contrast_kwargs_for(n),
                       fov_box=[x0, y0, x1, y1], frame_px=int(shape[0] * shape[1]),
                       painted_crack_px=n_crack, painted_notcrack_px=n_notc,
                       default_window_raw_values=[round(slo, 1), round(shi, 1)],
                       raw_min=int(raw.min()), raw_max=int(raw.max()), settings={})

            # Shipped first: every other arm is a delta against this exact mask.
            base_mask, seen = None, {}
            for lo, hi in [SHIPPED] + [g for g in GRID if g != SHIPPED]:
                k = key(lo, hi)
                img8f, vlo, vhi = stretch(raw, lo, hi)
                fov = list(D.find_field_of_view(img8f))
                img8 = img8f[y0:y1, x0:x1]
                h = hashlib.md5(img8.tobytes()).hexdigest()

                if h in seen:                       # packed to keep 36 frame-sized
                    m = np.unpackbits(seen[h],      # masks off the heap at 25 Mpx
                                      count=img8.size).astype(bool).reshape(img8.shape)
                else:
                    flat = D.flatten_background(img8, sigma=40)
                    prop = u.segment_dark_regions(flat, img8=img8, mad_k=MAD_K)
                    m = candidates(prop)
                    seen[h] = np.packbits(m)

                if k == SHIPPED_KEY:
                    base_mask = m
                    ship_hash = h
                    # ---- CONTROL 2: the baseline mask must come from a direct shipped
                    #      call through the shipped loader, not from anything reassembled
                    #      here out of `raw`.
                    d8 = D.load_as_uint8(path)[y0:y1, x0:x1]
                    direct = candidates(u.segment_dark_regions(
                        D.flatten_background(d8, sigma=40), img8=d8, mad_k=MAD_K))
                    if not np.array_equal(direct, base_mask):
                        raise SystemExit(f"{n}: the shipped-setting mask built here is not "
                                         f"what the shipped stages produce")
                    del d8, direct

                tp, fp, area = int((m & crack).sum()), int((m & notc).sum()), int(m.sum())
                # SUBTRACTIVE by construction: this constant moves the 8-bit values the
                # absolute gate and every Otsu/MAD cut read, in both directions. Count
                # what each setting DELETES, not only what it adds.
                deleted = int((base_mask & ~m).sum())
                deleted_painted = int((base_mask & ~m & crack).sum())
                added = int((m & ~base_mask).sum())
                # The three channels through which an affine-equivariant chain can feel
                # this constant at all. gate_px is the non-equivariant one.
                row["settings"][k] = dict(
                    window_raw_values=[round(vlo, 1), round(vhi, 1)],
                    tp=tp, fp=fp, marked_px=area,
                    sat_lo_pct=round(100 * float((img8 == 0).mean()), 4),
                    sat_hi_pct=round(100 * float((img8 == 255).mean()), 4),
                    gate_px=int((img8 < GATE).sum()),
                    recall=round(tp / max(n_crack, 1), 4),
                    notcrack_rate=round(fp / max(n_notc, 1), 4),
                    marked_pct=round(100 * area / max(shape[0] * shape[1], 1), 4),
                    painted_crack_deleted_vs_shipped=deleted_painted,
                    px_deleted_vs_shipped=deleted,
                    px_added_vs_shipped=added,
                    img8_identical_to_shipped=bool(h == ship_hash),
                    fov_box=fov)
                if fov != [x0, y0, x1, y1]:
                    fov_moved.append((n, k, fov, [x0, y0, x1, y1]))

            # ---- CONTROL 3: a sweep in which nothing moves is an unconfigured input,
            #      not a null result. The grid must produce more than one distinct image.
            if len(seen) == 1:
                raise SystemExit(f"{n}: all {len(GRID)} windows produced the SAME img8; "
                                 f"the sweep is not reaching the constant")

            row["n_distinct_img8_over_grid"] = len(seen)
            per_frame.append(row)
            sr = row["settings"][SHIPPED_KEY]["recall"]
            best = max(GRID, key=lambda g: row["settings"][key(*g)]["recall"])
            print(f"{n:<36} {n_crack:>10,} px  shipped r={sr:.4f}  best r="
                  f"{row['settings'][key(*best)]['recall']:.4f} at {best}  "
                  f"({len(seen)} distinct img8)  ({time.time()-t0:.0f}s)", flush=True)
        except SystemExit:
            raise
        except Exception as e:
            print(f"{n:<36}  ERROR {type(e).__name__}: {e}", flush=True)

    if not per_frame:
        raise SystemExit("no frame scored; nothing to report")

    def pool(rows):
        """Pooled table over ONE unit set. The round-robin sample and the three
        already-overridden frames are different unit sets and are never mixed."""
        if not rows:
            return None
        n_crack = sum(r["painted_crack_px"] for r in rows)
        n_notc = sum(r["painted_notcrack_px"] for r in rows)
        n_px = sum(r["frame_px"] for r in rows)
        out = {}
        for lo, hi in GRID:
            k = key(lo, hi)
            s = [r["settings"][k] for r in rows]
            tp = sum(x["tp"] for x in s)
            area = sum(x["marked_px"] for x in s)
            dp = sum(x["painted_crack_deleted_vs_shipped"] for x in s)
            rec_ = tp / max(n_crack, 1)
            frac = area / max(n_px, 1)
            rs = sorted(x["recall"] for x in s)
            out[k] = dict(
                low_pct=lo, high_pct=hi, is_default=(lo, hi) == SHIPPED,
                recall_on_painted_crack=round(rec_, 4),
                rate_on_painted_notcrack=round(sum(x["fp"] for x in s) / max(n_notc, 1), 4),
                pct_of_frame_marked=round(100 * frac, 4),
                # recall / marked fraction: mark-everything scores exactly 1.0, so a
                # setting that only dilates cannot move this.
                lift_over_mark_everything=round(rec_ / max(frac, 1e-12), 4),
                median_per_frame_recall=round(rs[len(rs) // 2], 4),
                min_per_frame_recall=round(rs[0], 4),
                # the mechanism, so a row's size can be read against what could produce it
                sat_lo_pct=round(float(np.mean([x["sat_lo_pct"] for x in s])), 4),
                sat_hi_pct=round(float(np.mean([x["sat_hi_pct"] for x in s])), 4),
                gate_px=sum(x["gate_px"] for x in s),
                pct_of_frame_in_absolute_gate=round(
                    100 * sum(x["gate_px"] for x in s) / max(n_px, 1), 4),
                n_frames_better_than_default=sum(
                    1 for r in rows
                    if r["settings"][k]["recall"] > r["settings"][SHIPPED_KEY]["recall"]),
                n_frames_worse_than_default=sum(
                    1 for r in rows
                    if r["settings"][k]["recall"] < r["settings"][SHIPPED_KEY]["recall"]),
                n_frames_identical_img8_to_default=sum(
                    1 for x in s if x["img8_identical_to_shipped"]),
                painted_crack_deleted_vs_default=dp,
                pct_of_painted_crack_deleted_vs_default=round(
                    100 * dp / max(n_crack, 1), 4),
                n_frames_deleting_painted_crack=sum(
                    1 for x in s if x["painted_crack_deleted_vs_shipped"] > 0),
                px_deleted_vs_default=sum(x["px_deleted_vs_shipped"] for x in s),
                px_added_vs_default=sum(x["px_added_vs_shipped"] for x in s),
                fov_box_changed_on_frames=sorted(
                    {f for f, kk, _a, _b in fov_moved
                     if kk == k and f in {r["frame"] for r in rows}}),
            )
        return dict(n_frames=len(rows),
                    n_specimens=len({r["specimen"] for r in rows}),
                    frames=[r["frame"] for r in rows],
                    painted_crack_px=n_crack, painted_notcrack_px=n_notc,
                    total_frame_px=n_px, settings=out)

    rr_rows = [r for r in per_frame if r["in_roundrobin"]]
    g_rows = [r for r in per_frame if r["gentle_contrast_frame"]]
    pooled_rr, pooled_gentle, pooled_all = pool(rr_rows), pool(g_rows), pool(per_frame)
    summary = pooled_rr["settings"]
    tot = dict(crack=pooled_all["painted_crack_px"], notc=pooled_all["painted_notcrack_px"],
               px=pooled_all["total_frame_px"], n=len(per_frame))
    ship = summary[SHIPPED_KEY]
    rec = dict(
        what=("the percentile contrast window in detect_cracks.load_as_uint8 -- Figure 6's "
              "constant F -- swept on full frames against the hand-painted correction "
              "masks"),
        generated=time.strftime("%Y-%m-%d"),
        shipped=dict(low_pct=SHIPPED[0], high_pct=SHIPPED[1], key=SHIPPED_KEY),
        grid=dict(low_pct=list(LOWS), high_pct=list(HIGHS), n_settings=len(GRID),
                  rule="every pair with low < high"),
        why_no_tile_arm=(
            "tilebench.build_cache takes its percentiles over the 512 px CROP while "
            "detect_cracks.load_as_uint8 takes them over the WHOLE micrograph, so a tile "
            "re-stretch is per-tile autocontrast, not this constant. Measured per tile in "
            "tile_control below; the script RAISES if the two windows agree. A corollary: "
            "the cached img8 is not byte-identical to what the pipeline sees, contrary to "
            "build_cache's docstring."),
        tile_control=tiles_say,
        scoring="correction masks: 1 = crack, 2 or 3 = not-crack, 0 excluded",
        stage_scored=("candidate stage: load -> find_field_of_view -> flatten_background"
                      "(sigma=40) -> shipped 7-rung segment_dark_regions | (img8 < 10) -> "
                      "clean_mask(min_area_px=13) -> components >= 40 px. The region "
                      "classifier is NOT applied, matching ladder_endpoints_frames.py."),
        pixel_grid=("every setting is scored inside the SHIPPED field-of-view box so that "
                    "'pixels deleted' is defined; find_field_of_view is itself downstream "
                    "of this constant and its box per setting is reported in "
                    "fov_box_changed_on_frames and per_frame[].settings[].fov_box"),
        frame_selection=(
            f"up to {PER_SPECIMEN} per specimen, NOT alphabetical, PLUS every painted "
            f"frame in common.GENTLE_CONTRAST_IMAGES -- the three the shipped pipeline "
            f"already runs at (0.0, 100.0) by hand. The two unit sets are pooled "
            f"separately: pooled_roundrobin and pooled_gentle_contrast_frames. "
            f"'settings' at the top level is the round-robin sample."),
        gentle_contrast_frames=sorted(GENTLE_CONTRAST_IMAGES),
        n_frames=tot["n"], n_specimens=len({r["specimen"] for r in per_frame}),
        painted_crack_px=tot["crack"], painted_notcrack_px=tot["notc"],
        total_frame_px=tot["px"],
        mad_k=MAD_K, absolute_dark_thresh=GATE, scale_ladder=list(DO.SCALE_LADDER),
        use_region_classifier=DO.USE_REGION_CLASSIFIER,
        mechanism=dict(
            note=("flatten_background's own percentile re-stretch and "
                  "segment_dark_regions' otsu / median-MAD cut are all affine-"
                  "EQUIVARIANT, so on unclipped floats this constant would select the "
                  "identical relative mask at every setting. Its whole effect runs "
                  "through saturation (sat_lo_pct, sat_hi_pct), uint8 quantisation, and "
                  "the ABSOLUTE gate img8 < "
                  f"{GATE}, which compares a rescaled value to a fixed number and is the "
                  "only non-equivariant stage. gate_px is that stage's own size per "
                  "setting, so no row may claim an effect larger than its mechanism."),
            clamping=("a percentile is clamped by the data: on a frame with more than "
                      "low_pct percent of its pixels at the raw floor every low_pct in "
                      "this grid returns the same lo, and the rows are byte-identical. "
                      "See n_frames_identical_img8_to_default and per_frame[]."
                      "n_distinct_img8_over_grid.")),
        direction=dict(
            verdict="SUBTRACTIVE",
            why=("this constant sets the 8-bit values that the absolute gate (img8 < 10) "
                 "and every Otsu/MAD cut in the ladder compare against, so moving it "
                 "moves pixels in BOTH directions. It is not a union-widening change like "
                 "adding a ladder rung, and it CAN delete a pixel a human painted as "
                 "crack. painted_crack_deleted_vs_shipped is that count, per setting "
                 "pooled and per frame."),
            measured=("non-zero painted_crack_deleted_vs_default on " + str(sum(
                1 for k in summary if k != SHIPPED_KEY
                and summary[k]["painted_crack_deleted_vs_default"] > 0)) +
                f" of {len(GRID) - 1} non-default settings, round-robin sample")),
        controls={
            "tile_arm_is_impossible": "MEASURED, raises if the tile windows agree",
            "the_hand_override_is_a_grid_point": "PASS, (0.0, 100.0) is swept",
            "reconstruction_equals_load_as_uint8": "PASS byte-identical on every frame",
            "shipped_kwarg_defaults_are_1.0_99.5": "PASS on every frame",
            "baseline_mask_equals_a_direct_shipped_call": "PASS on every frame",
            "grid_actually_moves_the_image": "PASS, >1 distinct img8 per frame",
        },
        caveats=[
            "recall here is the CANDIDATE stage's recall and the candidate stage marks "
            f"{ship['pct_of_frame_marked']:.1f}% of the frame at the shipped setting; read "
            "every recall against pct_of_frame_marked and lift_over_mark_everything or a "
            "setting that merely paints more will look like an improvement",
            "n frames is small and the not-crack paint is far scarcer than the crack "
            "paint, so rate_on_painted_notcrack is weak evidence about precision",
            "no leave-one-specimen-out selector is run: with 36 settings on "
            f"{tot['n']} frames the fitted argmax is not a held-out result and is not "
            "quoted as one",
            "the three GENTLE_CONTRAST frames are scored against the (1.0, 99.5) default "
            "as their baseline, NOT against their own (0.0, 100.0) override, so that "
            "'deleted vs default' means the same thing in every row",
        ],
        settings=summary,
        pooled_roundrobin=pooled_rr,
        pooled_gentle_contrast_frames=pooled_gentle,
        pooled_all_frames=pooled_all,
        per_frame=per_frame,
        fov_box_moves=[dict(frame=f, setting=k, box=a, shipped_box=b)
                       for f, k, a, b in fov_moved],
        seconds=round(time.time() - t0, 1),
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rec, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}  ({rec['seconds']}s)\n")

    def table(title, block):
        if block is None:
            return
        s = block["settings"]
        print(f"\n--- {title}: {block['n_frames']} frames, "
              f"{block['n_specimens']} specimens, "
              f"{block['painted_crack_px']:,} painted crack px ---")
        print(f"{'setting':<16} {'recall':>8} {'median':>8} {'min':>8} {'notcrk':>8} "
              f"{'marked%':>8} {'lift':>7} {'gate%':>7} {'sat_lo%':>8} "
              f"{'del_paint':>11} {'>def':>5} {'<def':>5} {'same':>5}")
        for k in sorted(s, key=lambda k: -s[k]["recall_on_painted_crack"]):
            v = s[k]
            tag = "  *DEFAULT*" if v["is_default"] else (
                "  *HAND OVERRIDE*" if (v["low_pct"], v["high_pct"]) == (0.0, 100.0)
                else "")
            print(f"{k:<16} {v['recall_on_painted_crack']:>8.4f} "
                  f"{v['median_per_frame_recall']:>8.4f} "
                  f"{v['min_per_frame_recall']:>8.4f} "
                  f"{v['rate_on_painted_notcrack']:>8.4f} "
                  f"{v['pct_of_frame_marked']:>8.3f} "
                  f"{v['lift_over_mark_everything']:>7.3f} "
                  f"{v['pct_of_frame_in_absolute_gate']:>7.3f} "
                  f"{v['sat_lo_pct']:>8.4f} "
                  f"{v['painted_crack_deleted_vs_default']:>11,} "
                  f"{v['n_frames_better_than_default']:>5} "
                  f"{v['n_frames_worse_than_default']:>5} "
                  f"{v['n_frames_identical_img8_to_default']:>5}{tag}")

    table("ROUND-ROBIN SAMPLE", pooled_rr)
    table("GENTLE-CONTRAST FRAMES (the pipeline already overrides these)", pooled_gentle)

    print(f"\nDEFAULT {SHIPPED_KEY} on the round-robin: "
          f"recall {ship['recall_on_painted_crack']:.4f}, "
          f"marked {ship['pct_of_frame_marked']:.3f}%, "
          f"lift {ship['lift_over_mark_everything']:.3f}")
    worst = max(summary, key=lambda k: summary[k]["painted_crack_deleted_vs_default"])
    print(f"MOST DESTRUCTIVE setting {worst}: deletes "
          f"{summary[worst]['painted_crack_deleted_vs_default']:,} painted crack px "
          f"({summary[worst]['pct_of_painted_crack_deleted_vs_default']:.2f}%) on "
          f"{summary[worst]['n_frames_deleting_painted_crack']} frames")
    dead = [k for k in summary if k != SHIPPED_KEY
            and summary[k]["n_frames_identical_img8_to_default"] == pooled_rr["n_frames"]]
    print(f"{len(dead)}/{len(GRID)} settings produce a BYTE-IDENTICAL img8 to the default "
          f"on every round-robin frame: {', '.join(sorted(dead))}")
    if fov_moved:
        print(f"\nfind_field_of_view's box MOVED on {len(fov_moved)} (frame, setting) "
              f"pairs; those rows are scored on the default box")
    return rec


if __name__ == "__main__":
    main()
