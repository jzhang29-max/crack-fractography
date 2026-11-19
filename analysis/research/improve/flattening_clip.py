#!/usr/bin/env python3
"""Is flatten_background's 0.5/99.5 percentile clip measured, or is it just a kwarg?

WHY THIS EXISTS. `flatten_background(img8, sigma=40, low_pct=0.5, high_pct=99.5)` in
sem-crack-detector/code/detect_cracks.py subtracts a blurred copy and then rescales the
residual to 8-bit by a PERCENTILE stretch. Figure 6 letters the pair F and its
justification record says, in as many words: "kwarg defaults on flatten_background; the
docstring argues percentile over min/max and gives no numbers for either". The docstring's
argument is real -- "a handful of outlier pixels ... can dominate the range and compress
all of the real background texture into a narrow band, which then breaks Otsu thresholding
downstream (seen on low-contrast ETD captures)" -- but it is an argument for percentiles,
not for 0.5 and 99.5. This file supplies numbers for both halves: the grid, and a raw
min/max arm (0.0, 100.0) which IS the alternative the docstring argues against and is
therefore the one claim in it that can be tested rather than repeated.

WHAT THE CONSTANT CAN AND CANNOT DO, BEFORE ANY DATA. Downstream of the stretch,
segment_dark_regions cuts at `min(otsu(sm), median(sm) - k*MAD(sm))`. Both of those are
affine-EQUIVARIANT: in exact arithmetic on an unclipped float residual the cut would be
the identical set of pixels for EVERY (low_pct, high_pct), and this constant would have no
effect whatsoever. Its entire effect therefore runs through the two things the stretch
does that an affine map does not:

  SATURATION   rescale_intensity clips outside [lo, hi], so low_pct percent of pixels are
               pinned at 0 and (100 - high_pct) percent at 255.
  QUANTISATION the result is cast to uint8, so a wider range is a coarser grid.

Both are measured per arm below (sat_lo_pct, sat_hi_pct, and the per-rung MAD), so the
size of any effect can be read against the mechanism that has to produce it.

AND THERE IS A THIRD, WHICH IS THE INTERESTING ONE. detector_overrides' own notes record
that the stretch "pins the flattened image's MAD at 24-43 grey levels with a median near
130 -- so `med - 5*mad` lands NEGATIVE and the rung proposes nothing at all ... 56 of 336
frame-rungs (16.7%) are dead this way". That dead-rung count is a DIRECT function of this
constant: a narrow clip spreads the surviving distribution over the full 0-255, inflating
the MAD in grey levels and killing more rungs; a wide clip compresses it and revives them.
dead_rungs is counted per arm here for exactly that reason.

THE DUAL-LOCATION COUPLING, which is a finding in its own right and is measured, not
asserted. The shipped detector re-flattens at seven radii (detector_overrides.SCALE_LADDER
= 5, 10, 20, 40, 80, 160, 320). Rungs at sigma <= DECIMATE_ABOVE_SIGMA (64) are produced by
`detect_cracks.flatten_background` and so read the kwarg defaults; rungs above it are
produced by `detector_overrides.install._flatten`, which re-implements the same stretch
with 0.5 and 99.5 HARD-CODED. Editing one file alone changes 4 of 7 rungs or 3 of 7, and
the ladder's rungs then disagree with each other. Every arm is therefore scored three
ways -- `both`, `kwarg_only` (edit detect_cracks.py alone) and `override_only` (edit
detector_overrides.py alone) -- so the cost of a half-edit is a number.

RECALL IS READ AGAINST MARKED AREA OR IT IS NOT READ. The candidate stage already marks
~10-20% of a frame, and a wider clip marks more, so recall alone ranks whichever arm
paints most. Every frame row carries pct_of_frame_marked and lift_over_mark_everything
(= recall / marked fraction), which an arm that only dilates cannot move.

AND THE DOCSTRING'S CLAIM IS TESTED WHERE IT SAYS TO TEST IT. It names "low-contrast ETD
captures" as where min/max breaks Otsu, so the min/max arm is reported split by capture
detector (CBS / ETD / BSE / SE) and not only pooled; and the three captures the shipped
pipeline ALREADY hand-overrides to a (0.0, 100.0) contrast window -- the lowest-contrast
frames in the corpus, common.GENTLE_CONTRAST_IMAGES -- are appended to the frame sample
and pooled SEPARATELY, because they are a different unit set and must not be averaged in.

TILES ARE THE SCREEN, FRAMES ARE THE VERDICT. The 26 hand-labelled tiles are 512 px and
this project has repeatedly had them disagree with full frames; a tile sweep last said to
drop the ladder's smallest radius and the frame test showed that deletes 64,728 px of
hand-painted crack. So the grid is swept on tiles and the decisive arms are re-run at
25 Mpx against the correction masks, read only.

Run:  <sem-venv>/bin/python -B analysis/research/improve/flattening_clip.py
      STAGE=tiles|frames|both   NFRAMES=18   PER_SPECIMEN=2
Writes docs/figures/flattening_clip.json (the only file this script creates).
"""
import json
import os
import sys
import time
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
FIGS = os.path.join(REPO, "paper", "figures")
sys.path.insert(0, FIGS)
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.dont_write_bytecode = True

import _paths                                        # noqa: E402

#: The same path order mk_parameters.py sets up; without it the shipped stages are not
#: importable and nothing below is calling the real detector.
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "code"))
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "interior_active_learning", "code"))

from PIL import Image                                # noqa: E402
from scipy import ndimage as ndi                     # noqa: E402
from skimage import exposure as _exp, filters        # noqa: E402

import detect_cracks as D                            # noqa: E402  (shipped stages)
import detector_overrides as DO                      # noqa: E402  (shipped constants)
import both_modalities as BM                         # noqa: E402
from mk_parameters import tile_chain                 # noqa: E402  the shipped chain
from common import GENTLE_CONTRAST_IMAGES, contrast_kwargs_for   # noqa: E402

Image.MAX_IMAGE_PIXELS = None
SEM = _paths.SEM_REPO
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
OUT = os.path.join(REPO, "docs", "figures", "flattening_clip.json")

LADDER = tuple(DO.SCALE_LADDER)
DEC = int(DO.DECIMATE_ABOVE_SIGMA)
GATE = int(DO.ABSOLUTE_DARK_THRESH)
SHIPPED = (0.5, 99.5)

#: The grid the question asks for. (0.0, 100.0) IS the raw min/max arm -- it is in the
#: grid rather than bolted on beside it, so it is scored by the same instrument as
#: everything else and cannot get a different exclusion list or tolerance by accident.
LOWS = (0.0, 0.1, 0.5, 1.0, 2.0, 5.0)
HIGHS = (95.0, 98.0, 99.0, 99.5, 99.9, 100.0)
ARMS = tuple((lo, hi) for lo in LOWS for hi in HIGHS if lo < hi)

#: Tiles are scored at the paper's own detection setting (both_modalities.MAD_K), which is
#: what makes CONTROL 3 below -- tile_chain == both_modalities.stages -- a real check.
#: Frames are scored at mad_k 5.0, the shipped kwarg default and the setting
#: ladder_endpoints_frames.py and the dead-rung record in detector_overrides both use.
#: The clip acts THROUGH the MAD, so the two are not interchangeable and the tile grid is
#: run at both to keep the tile->frame comparison from riding on that difference.
TILE_MAD_K = float(BM.MAD_K)
FRAME_MAD_K = 5.0

STAGE = os.environ.get("STAGE", "both")
PER_SPECIMEN = int(os.environ.get("PER_SPECIMEN", "2"))
LIMIT = int(os.environ.get("NFRAMES", "18"))
MIN_PAINT = 20000


def label_of(arm):
    return f"p{arm[0]:g}_{arm[1]:g}"


def detector_of(name):
    """CBS / ETD / SE / BSE, the capture detector, from the frame name.

    The docstring's claim names low-contrast ETD captures specifically, so the min/max
    comparison is split this way rather than only pooled.
    """
    for tag in ("CBS", "ETD", "BSE", "SE"):
        if f"_{tag}_" in name or name.endswith("_" + tag):
            return tag
    return "?"


def specimen_of(name):
    """Coarse specimen key: everything before the trailing capture index."""
    parts = name.split("_")
    while parts and (parts[-1].isdigit() or parts[-1] in ("CBS", "ETD", "SE", "BSE")):
        parts.pop()
    return "_".join(parts) or name


# ----------------------------------------------------------------- the shipped stretch
def background(img8, sigma):
    """The background estimate the shipped code makes at `sigma`, clip-independent.

    This is the ONE place the two implementations are transcribed, and it is transcribed
    because the clip has to be lifted out of them to be swept. It is not trusted: CONTROL
    2 asserts that feeding (0.5, 99.5) back through it reproduces the shipped
    `segment_dark_regions` output bit for bit, on every tile and every frame scored.
    """
    if sigma <= DEC:
        return filters.gaussian(img8, sigma=sigma, preserve_range=True)
    f = max(1, int(round(sigma / 32.0)))
    small = ndi.uniform_filter(img8.astype(np.float32), f)[::f, ::f]
    bg_s = ndi.gaussian_filter(small, sigma / f, mode="nearest")
    bg = ndi.zoom(bg_s, (img8.shape[0] / bg_s.shape[0], img8.shape[1] / bg_s.shape[1]),
                  order=1, mode="nearest")[:img8.shape[0], :img8.shape[1]]
    if bg.shape != img8.shape:                 # zoom can land a pixel short
        bg = np.pad(bg, ((0, img8.shape[0] - bg.shape[0]),
                         (0, img8.shape[1] - bg.shape[1])), mode="edge")
    return bg


def stretch(resid, low, high):
    """The percentile stretch, with its `hi <= lo` fallback to raw min/max kept."""
    lo, hi = np.percentile(resid, [low, high])
    if hi <= lo:
        lo, hi = resid.min(), resid.max()
    return _exp.rescale_intensity(resid, in_range=(lo, hi),
                                  out_range=(0, 255)).astype(np.uint8)


def rung(resid, low, high, mad_k):
    """One rung's dark cut, plus the diagnostics that explain why it is that cut."""
    f = stretch(resid, low, high)
    sm = filters.gaussian(f, sigma=1.0, preserve_range=True)
    med = float(np.median(sm))
    mad = float(np.median(np.abs(sm - med))) * 1.4826
    rob = med - mad_k * mad
    ots = float(filters.threshold_otsu(sm))
    cut = sm < min(ots, rob)
    return cut, dict(sat_lo=float((f == 0).mean()), sat_hi=float((f == 255).mean()),
                     med=med, mad=mad, robust=rob, otsu=ots, dead=not bool(cut.any()))


def unions(cuts, gate):
    """`both`, `kwarg_only` and `override_only` from one arm's cached per-rung cuts.

    cuts: {(low, high): {sigma: bool array}} and must contain SHIPPED.
    """
    out = {}
    for arm, per in cuts.items():
        ship = cuts[SHIPPED]
        both = gate.copy()
        kwarg = gate.copy()
        ovr = gate.copy()
        for s in LADDER:
            both |= per[s]
            kwarg |= per[s] if s <= DEC else ship[s]
            ovr |= ship[s] if s <= DEC else per[s]
        out[arm] = dict(both=both, kwarg_only=kwarg, override_only=ovr)
    return out


# ------------------------------------------------------------------------------- tiles
def sweep_tiles():
    t0 = time.time()
    TB = _paths.tilebench()
    tiles = TB.load()
    if not TB.controls():
        raise SystemExit("tilebench's own controls did not pass; nothing here is readable")
    print(f"  CONTROL 1 tilebench self-check: PASS  ({len(tiles)} tiles, "
          f"{len({t['specimen'] for t in tiles})} specimens)")

    class _U:
        pass
    u = _U()
    DO.install(u)

    # CONTROL 4 (cheap, run once): a degenerate clip must hit the `hi <= lo` fallback and
    # come out identical to raw min/max. If it does not, `stretch` is not the shipped one.
    probe = tiles[0]["img8"].astype(np.float32) - background(tiles[0]["img8"], 40)
    if not np.array_equal(stretch(probe, 50.0, 50.0), stretch(probe, 0.0, 100.0)):
        raise SystemExit("the hi<=lo fallback does not reproduce raw min/max; `stretch` "
                         "is not flatten_background's stretch and no arm below is valid")
    print("  CONTROL 4 degenerate clip falls back to raw min/max: PASS")

    per_tile = {label_of(a): [] for a in ARMS}
    cand_rows = {k: {label_of(a): [] for a in ARMS} for k in ("madk6", "madk5")}
    coupling = {label_of(a): defaultdict(int) for a in ARMS}
    diag = {label_of(a): dict(dead=0, rungs=0, sat_lo=[], sat_hi=[], mad=[], neg_robust=0)
            for a in ARMS}
    ship_lab = label_of(SHIPPED)

    for i, t in enumerate(tiles):
        img8 = t["img8"]
        gt = t["gt"]
        gate = img8 < GATE
        resid = {s: img8.astype(np.float32) - background(img8, s) for s in LADDER}

        for mk, key in ((TILE_MAD_K, "madk6"), (FRAME_MAD_K, "madk5")):
            cuts = {}
            for a in ARMS:
                per = {}
                for s in LADDER:
                    c, d = rung(resid[s], a[0], a[1], mk)
                    per[s] = c
                    if key == "madk6":
                        g = diag[label_of(a)]
                        g["rungs"] += 1
                        g["dead"] += int(d["dead"])
                        g["neg_robust"] += int(d["robust"] < 0)
                        if s == 40:
                            g["sat_lo"].append(d["sat_lo"])
                            g["sat_hi"].append(d["sat_hi"])
                        g["mad"].append(d["mad"])
                cuts[a] = per
            uni = unions(cuts, gate)

            if key == "madk6":
                # CONTROL 2: the lifted-out stretch, fed the shipped constants, must
                # reproduce the shipped segment_dark_regions bit for bit.
                flat = D.flatten_background(img8, sigma=40)
                theirs = u.segment_dark_regions(flat, img8=img8, mad_k=TILE_MAD_K)
                if not np.array_equal(uni[SHIPPED]["both"], theirs):
                    raise SystemExit(
                        f"{t['frame']}: the reconstruction at (0.5, 99.5) does NOT equal "
                        f"the shipped segment_dark_regions ({int(uni[SHIPPED]['both'].sum())} "
                        f"vs {int(theirs.sum())} px). Every row below would be a different "
                        f"detector.")
                # CONTROL 3: and the chain on top must be the shipped chain.
                _f, _p, _c, final = BM.stages(img8)
                ves0 = D.compute_vesselness(flat)
                if not np.array_equal(tile_chain(_p, flat=flat, img8=img8, ves=ves0), final):
                    raise SystemExit(f"{t['frame']}: tile_chain != both_modalities.stages")

            base = uni[SHIPPED]["both"]
            for a in ARMS:
                lab = label_of(a)
                m = uni[a]["both"]
                c = TB.counts(m, gt, tol=2)
                cand_rows[key][lab].append(dict(
                    frame=t["frame"], specimen=t["specimen"], det=detector_of(t["frame"]),
                    tp=int(c["tp"]), fp=int(c["fp"]), fn=int(c["fn"]),
                    px=int(m.sum()),
                    px_lost_vs_shipped=int((base & ~m).sum()),
                    gt_lost_vs_shipped=int((base & ~m & gt).sum())))
                if key == "madk6":
                    for nm in ("kwarg_only", "override_only"):
                        coupling[lab][nm + "_px_diff_vs_both"] += int(
                            (uni[a][nm] != m).sum())
                        coupling[lab][nm + "_px"] += int(uni[a][nm].sum())
                    coupling[lab]["both_px"] += int(m.sum())

            # the shipped chain, classifier included, on the `both` union only
            if key == "madk6":
                for a in ARMS:
                    lab = label_of(a)
                    flat_a = stretch(resid[40], a[0], a[1])
                    ves = D.compute_vesselness(flat_a) if DO.USE_REGION_CLASSIFIER else None
                    m = tile_chain(uni[a]["both"], flat=flat_a, img8=img8, ves=ves)
                    c = TB.counts(m, gt, tol=2)
                    per_tile[lab].append(dict(
                        frame=t["frame"], specimen=t["specimen"],
                        det=detector_of(t["frame"]),
                        tp=int(c["tp"]), fp=int(c["fp"]), fn=int(c["fn"]),
                        ttp=int(c["ttp"]), tfp=int(c["tfp"]), tfn=int(c["tfn"]),
                        px=int(m.sum())))
        print(f"    tile {i + 1}/{len(tiles)} {t['frame'][:46]:<46} "
              f"({time.time() - t0:.0f}s)", flush=True)

    # final-stage subtractive accounting needs the shipped final mask, so do it here
    for lab in per_tile:
        for j, r in enumerate(per_tile[lab]):
            r["tp_lost_vs_shipped"] = max(0, per_tile[ship_lab][j]["tp"] - r["tp"])

    def agg(rows, pre="", drop=()):
        tp = sum(r[pre + "tp"] for r in rows if r["frame"] not in drop)
        fp = sum(r[pre + "fp"] for r in rows if r["frame"] not in drop)
        fn = sum(r[pre + "fn"] for r in rows if r["frame"] not in drop)
        p = tp / max(tp + fp, 1)
        rc = tp / max(tp + fn, 1)
        return dict(precision=round(p, 4), recall=round(rc, 4),
                    iou=round(tp / max(tp + fp + fn, 1), 4),
                    f1=round(2 * p * rc / max(p + rc, 1e-12), 4), tp=tp, fp=fp, fn=fn)

    def med_iou(rows):
        v = sorted(r["tp"] / max(r["tp"] + r["fp"] + r["fn"], 1) for r in rows)
        return round(v[len(v) // 2], 4) if v else None

    flood = TB.FLOODED
    summary = {}
    for a in ARMS:
        lab = label_of(a)
        g = diag[lab]
        rows6 = cand_rows["madk6"][lab]
        rows5 = cand_rows["madk5"][lab]
        summary[lab] = dict(
            low_pct=a[0], high_pct=a[1],
            final_pooled_26=agg(per_tile[lab]),
            final_pooled_25=agg(per_tile[lab], drop=(flood,)),
            final_pooled_tol2=agg(per_tile[lab], pre="t"),
            final_median_tile_iou=med_iou(per_tile[lab]),
            candidate_pooled_madk6=agg(rows6),
            candidate_pooled_madk5=agg(rows5),
            candidate_px_lost_vs_shipped=sum(r["px_lost_vs_shipped"] for r in rows6),
            candidate_gt_lost_vs_shipped=sum(r["gt_lost_vs_shipped"] for r in rows6),
            final_tp_lost_vs_shipped=sum(r["tp_lost_vs_shipped"] for r in per_tile[lab]),
            dead_rungs=g["dead"], n_rungs=g["rungs"],
            dead_rung_pct=round(100 * g["dead"] / max(g["rungs"], 1), 2),
            negative_robust_thresh_rungs=g["neg_robust"],
            sat_lo_pct=round(100 * float(np.mean(g["sat_lo"])), 4),
            sat_hi_pct=round(100 * float(np.mean(g["sat_hi"])), 4),
            mean_mad_grey_levels=round(float(np.mean(g["mad"])), 2),
            coupling={k: int(v) for k, v in coupling[lab].items()},
        )

    # ---- leave-one-SPECIMEN-out, the selector this project uses. argmax over 26 tiles
    #      picks whatever fits 26 tiles; a fold that disagrees is the overfit showing.
    specs = sorted({t["specimen"] for t in tiles})
    folds = []
    for s in specs:
        def inner(lab):
            return agg([r for r in per_tile[lab] if r["specimen"] != s])["iou"]
        pick = max(summary, key=inner)
        held = agg([r for r in per_tile[pick] if r["specimen"] == s])
        held_ship = agg([r for r in per_tile[ship_lab] if r["specimen"] == s])
        folds.append(dict(held_out=s, picked=pick,
                          iou_of_pick_on_held_out=held["iou"],
                          iou_of_shipped_on_held_out=held_ship["iou"]))
    votes = Counter(f["picked"] for f in folds)

    # ---- the docstring's own claim, split the way the docstring states it
    mm = label_of((0.0, 100.0))
    by_det = {}
    for det in sorted({r["det"] for r in per_tile[ship_lab]}):
        sel = [r["frame"] for r in per_tile[ship_lab] if r["det"] == det]
        keep = [r for r in per_tile[ship_lab] if r["frame"] in sel]
        keep_mm = [r for r in per_tile[mm] if r["frame"] in sel]
        by_det[det] = dict(n_tiles=len(sel), shipped=agg(keep), minmax=agg(keep_mm),
                           candidate_shipped=agg([r for r in cand_rows["madk6"][ship_lab]
                                                  if r["frame"] in sel]),
                           candidate_minmax=agg([r for r in cand_rows["madk6"][mm]
                                                 if r["frame"] in sel]))

    rec = dict(
        n_tiles=len(tiles), n_specimens=len(specs), flood_tile=flood,
        tile_mad_k=TILE_MAD_K, frame_mad_k=FRAME_MAD_K,
        use_region_classifier=DO.USE_REGION_CLASSIFIER,
        scorer="analysis/research/tilebench.py via paper/figures/_paths.tilebench()",
        controls={
            "tilebench_self_check": "PASS",
            "degenerate_clip_falls_back_to_minmax": "PASS",
            "reconstruction_at_0.5_99.5_equals_shipped_segment_dark_regions":
                f"PASS, bit-identical on all {len(tiles)} tiles",
            "tile_chain_is_both_modalities_stages": f"PASS on all {len(tiles)} tiles",
        },
        arms=summary,
        loso=dict(folds=folds, votes=dict(votes),
                  mean_held_out_iou_of_selector=round(float(np.mean(
                      [f["iou_of_pick_on_held_out"] for f in folds])), 4),
                  mean_held_out_iou_of_shipped=round(float(np.mean(
                      [f["iou_of_shipped_on_held_out"] for f in folds])), 4)),
        minmax_by_detector=by_det,
        per_tile_final=per_tile,
        seconds=round(time.time() - t0, 1),
    )
    return rec


# ------------------------------------------------------------------------------ frames
def candidates(mask):
    """The cleaning chain's candidate stage, as ladder_endpoints_frames.py runs it."""
    lab, _ = ndi.label(D.clean_mask(mask, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel())
    keep = np.where(sz >= 40)[0]
    return np.isin(lab, keep[keep > 0])


def sweep_frames(frame_arms):
    t0 = time.time()
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
    #: The three captures the shipped pipeline already hand-overrides to a (0.0, 100.0)
    #: contrast window are the lowest-contrast frames in the corpus, and "low-contrast
    #: captures" is exactly the condition flatten_background's docstring names when it
    #: argues against min/max. The round-robin picks none of them, so they are appended
    #: and flagged -- and pooled SEPARATELY, because they are a different unit set.
    gentle = [n for n in sorted(GENTLE_CONTRAST_IMAGES) if n in names and n not in chosen]
    chosen = chosen + gentle
    print(f"\n{len(chosen) - len(gentle)} round-robin frames from "
          f"{len({specimen_of(n) for n in chosen if n not in gentle})} specimens "
          f"(up to {PER_SPECIMEN} each) out of {len(names)} painted frames, plus "
          f"{len(gentle)} appended low-contrast (GENTLE_CONTRAST_IMAGES) frames")
    print(f"arms: {[label_of(a) for a in frame_arms]}\n")

    class _U:
        pass
    u = _U()
    DO.install(u)

    per_frame, deletions = [], []

    for n in chosen:
        try:
            #: contrast_kwargs_for, not the bare default: three captures ship at a
            #: (0.0, 100.0) window by hand, and scoring them at (1.0, 99.5) would be
            #: measuring this constant on an input the pipeline never produces.
            #: find_field_of_view reads img8, which is UPSTREAM of the clip swept here,
            #: so unlike contrast_window.py no arm can move the crop box.
            img8 = D.load_as_uint8(os.path.join(SEM, "original", n + ".tif"),
                                   **contrast_kwargs_for(n))
            x0, y0, x1, y1 = D.find_field_of_view(img8)
            img8 = img8[y0:y1, x0:x1]
            corr = np.array(Image.open(os.path.join(PAINT, n + "_correction_mask.png")))
            corr = corr[..., 0] if corr.ndim == 3 else corr
            if corr.shape != img8.shape:
                if corr.shape[0] >= y1 and corr.shape[1] >= x1:
                    corr = corr[y0:y1, x0:x1]
                else:
                    print(f"{n:<36} SKIP: correction mask {corr.shape} vs {img8.shape}")
                    continue
            # 3 = erased is ALSO a not-crack verdict, not an absence of one.
            crack, notc = corr == 1, (corr == 2) | (corr == 3)
            if crack.sum() < MIN_PAINT:
                print(f"{n:<36} SKIP: only {int(crack.sum()):,} painted crack px "
                      f"(< {MIN_PAINT:,})", flush=True)
                continue

            gate = img8 < GATE
            # sigma OUTER, arms inner: one 25 Mpx residual in memory at a time.
            cuts = {a: {} for a in frame_arms}
            dead = {label_of(a): 0 for a in frame_arms}
            for s in LADDER:
                resid = img8.astype(np.float32) - background(img8, s)
                for a in frame_arms:
                    c, d = rung(resid, a[0], a[1], FRAME_MAD_K)
                    cuts[a][s] = c
                    dead[label_of(a)] += int(d["dead"])
                del resid
            uni = unions(cuts, gate)

            # CONTROL 2, again, at frame scale.
            flat = D.flatten_background(img8, sigma=40)
            theirs = u.segment_dark_regions(flat, img8=img8, mad_k=FRAME_MAD_K)
            if not np.array_equal(uni[SHIPPED]["both"], theirs):
                raise SystemExit(f"{n}: the reconstruction at (0.5, 99.5) does NOT equal "
                                 f"the shipped segment_dark_regions")
            del flat, theirs

            row = dict(frame=n, specimen=specimen_of(n), det=detector_of(n),
                       gentle=n in gentle,
                       painted_crack_px=int(crack.sum()),
                       painted_notcrack_px=int(notc.sum()), frame_px=int(img8.size),
                       dead_rungs=dead)
            base_mask = None
            for a in frame_arms:
                lab = label_of(a)
                m = candidates(uni[a]["both"])
                if a == SHIPPED:
                    base_mask = m
                tp, fp = int((m & crack).sum()), int((m & notc).sum())
                row[lab] = dict(tp=tp, fp=fp, area=int(m.sum()),
                                recall=round(tp / max(int(crack.sum()), 1), 4),
                                notcrack_rate=round(fp / max(int(notc.sum()), 1), 4),
                                marked_pct=round(100 * int(m.sum()) / img8.size, 4))
                # the clip is NOT additive: moving it can delete a pixel the shipped
                # setting kept. Count the hand-painted crack among them, per frame.
                if base_mask is not None and a != SHIPPED:
                    lost = int((base_mask & ~m).sum())
                    lost_painted = int((base_mask & ~m & crack).sum())
                    row[lab]["px_lost_vs_shipped"] = lost
                    row[lab]["painted_crack_lost_vs_shipped"] = lost_painted
                    row[lab]["px_gained_vs_shipped"] = int((m & ~base_mask).sum())
                    if lost_painted:
                        deletions.append((n, lab, lost_painted))
            per_frame.append(row)
            cells = " ".join(f"{row[label_of(a)]['recall']:7.4f}" for a in frame_arms)
            print(f"{n:<36} {int(crack.sum()):>10,} | {cells}   "
                  f"({time.time() - t0:.0f}s)", flush=True)
        except SystemExit:
            raise
        except Exception as e:
            print(f"{n:<36}  ERROR {type(e).__name__}: {e}", flush=True)

    ship_lab = label_of(SHIPPED)

    def block(rows):
        """Pooled scores over one unit set, plus the control that makes recall readable.

        RECALL ALONE RANKS WHICHEVER ARM PAINTS MOST. The candidate stage already marks
        ~10-20% of a frame and a wider clip marks more, so every row carries the marked
        fraction and lift_over_mark_everything = recall / marked fraction, which an arm
        that only dilates cannot move.
        """
        if not rows:
            return None
        crack = sum(r["painted_crack_px"] for r in rows)
        notc = sum(r["painted_notcrack_px"] for r in rows)
        px = sum(r["frame_px"] for r in rows)
        out = dict(n_frames=len(rows), painted_crack_px=crack, painted_notcrack_px=notc,
                   frame_px=px, frames=[r["frame"] for r in rows], arms={})
        for a in frame_arms:
            lab = label_of(a)
            tp = sum(r[lab]["tp"] for r in rows)
            fp = sum(r[lab]["fp"] for r in rows)
            area = sum(r[lab]["area"] for r in rows)
            rec = tp / max(crack, 1)
            marked = area / max(px, 1)
            rs = sorted(r[lab]["recall"] for r in rows)
            out["arms"][lab] = dict(
                low_pct=a[0], high_pct=a[1],
                recall_on_painted_crack=round(rec, 4),
                rate_on_painted_notcrack=round(fp / max(notc, 1), 4),
                pct_of_frame_marked=round(100 * marked, 4),
                lift_over_mark_everything=round(rec / max(marked, 1e-12), 4),
                median_per_frame_recall=round(rs[len(rs) // 2], 4),
                n_frames_better_than_shipped=sum(
                    1 for r in rows if r[lab]["recall"] > r[ship_lab]["recall"]),
                n_frames_worse_than_shipped=sum(
                    1 for r in rows if r[lab]["recall"] < r[ship_lab]["recall"]),
                painted_crack_deleted_vs_shipped=sum(
                    r[lab].get("painted_crack_lost_vs_shipped", 0) for r in rows),
                px_deleted_vs_shipped=sum(r[lab].get("px_lost_vs_shipped", 0)
                                          for r in rows),
                px_gained_vs_shipped=sum(r[lab].get("px_gained_vs_shipped", 0)
                                         for r in rows),
                dead_rungs=sum(r["dead_rungs"][lab] for r in rows),
                n_rungs=len(rows) * len(LADDER))
        return out

    rr = [r for r in per_frame if not r["gentle"]]
    gt_rows = [r for r in per_frame if r["gentle"]]
    return dict(
        n_frames=len(per_frame), n_round_robin=len(rr), n_gentle=len(gt_rows),
        n_specimens=len({r["specimen"] for r in rr}), mad_k=FRAME_MAD_K,
        frame_selection=f"up to {PER_SPECIMEN} per specimen, NOT alphabetical",
        input=("D.load_as_uint8 with common.contrast_kwargs_for(name), i.e. the shipped "
               "contrast window including its three hand overrides"),
        scoring="correction masks: 1 = crack, 2 or 3 = not-crack, 0 excluded",
        stage="candidate stage (clean_mask min 13 px, then components >= 40 px); the "
              "region classifier is NOT applied here, matching ladder_endpoints_frames.py",
        controls={"reconstruction_at_0.5_99.5_equals_shipped_segment_dark_regions":
                  f"PASS, bit-identical on all {len(per_frame)} frames scored"},
        round_robin=block(rr),
        low_contrast_gentle=block(gt_rows),
        by_detector={d: block([r for r in rr if r["det"] == d])
                     for d in sorted({r["det"] for r in rr})},
        all_frames=block(per_frame),
        per_frame=per_frame,
        frames_deleting_painted_crack=deletions,
        seconds=round(time.time() - t0, 1),
    )


# -------------------------------------------------------------------------------- main
def main():
    t0 = time.time()
    rec = dict(
        what=("flatten_background's low_pct/high_pct percentile clip (shipped 0.5/99.5), "
              "swept on the 26 hand-labelled tiles and confirmed on full frames"),
        generated=time.strftime("%Y-%m-%d"),
        generator="analysis/research/improve/flattening_clip.py",
        interpreter=sys.executable,
        repo_under_test=SEM,
        constant="detect_cracks.flatten_background(low_pct=0.5, high_pct=99.5)",
        figure6_justification_record=(
            "kwarg defaults on flatten_background; the docstring argues percentile over "
            "min/max and gives no numbers for either"),
        not_swept_here="sigma, which is swept in ladder_endpoints.py and is not this file",
        grid=dict(low_pct=list(LOWS), high_pct=list(HIGHS), n_arms=len(ARMS),
                  shipped=list(SHIPPED), minmax_arm=list((0.0, 100.0))),
        affine_note=(
            "both downstream thresholds, Otsu and median - k*MAD, are affine-equivariant, "
            "so on an unclipped float residual this constant would have NO effect at all. "
            "Everything measured here comes from the two things the stretch does that an "
            "affine map does not: saturation at 0 and 255, and 8-bit quantisation."),
        dual_location_coupling=dict(
            site_1="sem-crack-detector/code/detect_cracks.py :: flatten_background kwargs",
            site_2=("crack-fractography/analysis/detector_overrides.py :: install._flatten, "
                    "which hard-codes np.percentile(flat, [0.5, 99.5])"),
            split=(f"detector_overrides._flatten delegates to flatten_background for "
                   f"sigma <= DECIMATE_ABOVE_SIGMA ({DEC}) and uses its own hard-coded "
                   f"copy above it, so on SCALE_LADDER {list(LADDER)} the kwarg governs "
                   f"{sum(1 for s in LADDER if s <= DEC)} of {len(LADDER)} rungs and the "
                   f"hard-coded copy governs {sum(1 for s in LADDER if s > DEC)}"),
            measured="arms[*].coupling, in pixels, on the tiles"),
        classifier_note=(
            "the tile arms run the SHIPPED chain, region classifier included, and the "
            "classifier's MeanDarkness and MeanVesselness features are read off `flat` "
            "-- which this constant rescales. So a non-shipped arm does not merely move "
            "a threshold, it also feeds models/crack_classifier.joblib an input scaled "
            "differently from the one it was fitted on. That is a real cost of changing "
            "the constant and it is deliberately left IN the final_* rows; the "
            "candidate_pooled_* rows are the same arms with the classifier removed, and "
            "are the classifier-free comparison. The frame half is candidate-stage only, "
            "so it carries none of this."),
        scale_ladder=list(LADDER), decimate_above_sigma=DEC, absolute_dark_thresh=GATE,
        decimate_note=("DECIMATE_ABOVE_SIGMA, the boundary that splits the clip across "
                       "two files, is itself unmeasured -- Figure 6 records it as 'a "
                       "speed guard in detector_overrides.py carrying no comment and no "
                       "measurement'"),
    )

    tile_rec = None
    if STAGE in ("tiles", "both"):
        tile_rec = sweep_tiles()
        rec["tiles"] = tile_rec
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump(rec, open(OUT, "w"), indent=1)
        print(f"\n  (tile half written to {OUT})")

    if STAGE in ("frames", "both"):
        # The frame arms are not hand-picked after the fact: the shipped setting, the
        # min/max arm the docstring argues against, a fixed bracket either side of
        # shipped, and -- if the tiles ran -- whatever the tiles' pooled argmax and
        # leave-one-specimen-out vote actually chose.
        arms = [SHIPPED, (0.0, 100.0), (0.0, 99.5), (2.0, 98.0)]
        if tile_rec:
            best = max(tile_rec["arms"],
                       key=lambda L: tile_rec["arms"][L]["final_pooled_26"]["iou"])
            modal = Counter(f["picked"] for f in tile_rec["loso"]["folds"]).most_common(1)
            for lab in (best, modal[0][0]):
                a = tuple(float(x[1:]) if x.startswith("p") else float(x)
                          for x in lab.split("_"))
                if a not in arms:
                    arms.append(a)
        rec["frames"] = sweep_frames(arms)
        rec["frames"]["arm_selection"] = (
            "shipped, raw min/max, a fixed bracket, plus the tiles' pooled argmax and "
            "LOSO modal pick -- chosen by the tile half, not after seeing frame scores")

    rec["seconds"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rec, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}  ({rec['seconds']}s)")
    return rec


if __name__ == "__main__":
    r = main()
    if "tiles" in r:
        s = r["tiles"]["arms"]
        ship = label_of(SHIPPED)
        print(f"\n{'arm':>12} {'IoU26':>7} {'IoU25':>7} {'F1':>7} {'medIoU':>7} "
              f"{'candIoU':>8} {'dead%':>6} {'satLo%':>7} {'MAD':>6} {'gtLost':>7}")
        for lab in sorted(s, key=lambda L: -s[L]["final_pooled_26"]["iou"]):
            v = s[lab]
            star = " *" if lab == ship else ""
            print(f"{lab:>12} {v['final_pooled_26']['iou']:7.4f} "
                  f"{v['final_pooled_25']['iou']:7.4f} {v['final_pooled_26']['f1']:7.4f} "
                  f"{v['final_median_tile_iou']:7.4f} "
                  f"{v['candidate_pooled_madk6']['iou']:8.4f} "
                  f"{v['dead_rung_pct']:6.1f} {v['sat_lo_pct']:7.3f} "
                  f"{v['mean_mad_grey_levels']:6.1f} "
                  f"{v['candidate_gt_lost_vs_shipped']:7d}{star}")
        print(f"\nLOSO votes: {r['tiles']['loso']['votes']}")
        print(f"selector held-out IoU {r['tiles']['loso']['mean_held_out_iou_of_selector']}"
              f"  vs shipped {r['tiles']['loso']['mean_held_out_iou_of_shipped']}")
    if "frames" in r:
        for blk in ("round_robin", "low_contrast_gentle"):
            b = r["frames"].get(blk)
            if not b:
                continue
            print(f"\n--- {blk}: {b['n_frames']} frames, "
                  f"{b['painted_crack_px']:,} painted crack px")
            print(f"{'arm':>12} {'recall':>8} {'median':>8} {'notcrk':>8} {'marked%':>8} "
                  f"{'lift':>7} {'better':>7} {'worse':>6} {'paintDel':>9} {'dead':>7}")
            for lab, v in b["arms"].items():
                print(f"{lab:>12} {v['recall_on_painted_crack']:8.4f} "
                      f"{v['median_per_frame_recall']:8.4f} "
                      f"{v['rate_on_painted_notcrack']:8.4f} "
                      f"{v['pct_of_frame_marked']:8.3f} "
                      f"{v['lift_over_mark_everything']:7.3f} "
                      f"{v['n_frames_better_than_shipped']:7d} "
                      f"{v['n_frames_worse_than_shipped']:6d} "
                      f"{v['painted_crack_deleted_vs_shipped']:9,d} "
                      f"{v['dead_rungs']:3d}/{v['n_rungs']:<3d}")
        if r["frames"]["frames_deleting_painted_crack"]:
            print("\nframes where an arm DELETES hand-painted crack vs shipped:")
            for n, lab, px in r["frames"]["frames_deleting_painted_crack"][:15]:
                print(f"   {n}  {lab}  -{px:,} px")
        else:
            print("\nno arm deleted any hand-painted crack on any frame scored")
