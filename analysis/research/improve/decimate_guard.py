#!/usr/bin/env python3
"""DECIMATE_ABOVE_SIGMA, re-checked at FRAME scale -- the only scale where it can matter.

WHAT THE GUARD IS. detector_overrides.install() replaces the darkness cut with a union
over SCALE_LADDER = (5, 10, 20, 40, 80, 160, 320). scipy truncates a gaussian at 4 sigma,
so sigma=320 convolves with a ~2561 px kernel and costs ~32 s on a 25 Mpx frame. For
sigma > DECIMATE_ABOVE_SIGMA the background is instead estimated on a decimated copy and
resampled back (`_flatten`). It is a SPEED optimisation -- 67.2 s -> 14.5 s per full frame
by the comment in that file -- and it is only legitimate if it does not change the answer.

WHY THE EXISTING CHECK DOES NOT COUNT. The comment says "across the 26 tiles the two masks
differ by 347 px out of 6.8 M (0.005%)". Those are 512 px tiles. docs/figures/
ladder_endpoints.json "saturation" shows that on a 512 px tile sigma=2560 moves 307 px in
6,815,744 against the rung BELOW it: flatten_background subtracts a gaussian-blurred copy,
and once sigma approaches the tile width that copy is within a hair of a global constant,
so the high-pass has stopped being local. The tile bench cannot distinguish the large rungs
from one another, so it cannot price a change to how the large rungs are computed either.
The guard was validated on the one instrument where the radii it governs are inert.

At 25 Mpx a sigma=320 background estimate is genuinely local. That is where this measures.

NOTE THE RUNG SET. The file's own comment, and the brief for this script, both speak of
"sigma=320" as the rung the guard governs. It governs sigma=80 and sigma=160 as well --
every ladder rung above 64 -- at decimation factors f=2 and f=5. All three are measured.

AND NOTE THE sigma==40 SHORTCUT. install()'s union reads `f = flat if sigma == 40 else
_flatten(img8, sigma)`, so the sigma=40 rung is handed the caller's already-exact flat and
never reaches `_flatten` at all. DECIMATE_ABOVE_SIGMA=32 therefore produces the SAME mask
as 64 on the shipped ladder. The counterfactual (sigma=40 decimated too) is measured
separately as the arm "32_no40shortcut", because the equality is a property of that one
line and not of the constant.

WHAT IS MEASURED, per frame, at 25 Mpx:
  1. EXACT vs FAST per rung (80, 160, 320, and 640/1280/2560 for the proposed longer
     ladder), then for the full seven-rung union, then for the candidate mask after
     cleaning. Differing pixels in BOTH directions, as counts and fractions.
  2. Where the differing pixels land in the hand-painted correction mask: 1 = crack,
     2 or 3 = not-crack, 0 = unreviewed. A guard that moves few pixels but moves real
     crack is not safe.
  3. Whether the fast union is still a strict superset of the stock single-scale mask.
  4. A sweep of DECIMATE_ABOVE_SIGMA in (32, 64, 128, 256, never) -- agreement with the
     exact path against wall-clock cost. The output is a curve, not a winner.

CONTROLS THAT FAIL LOUDLY (SystemExit, not a logged warning):
  * with decimation disabled, install()'s own `_flatten` must return an array BIT-IDENTICAL
    to detect_cracks.flatten_background, at every sigma checked, on every frame;
  * the cached per-rung cuts, recombined at the shipped threshold, must equal a direct call
    to the shipped multiscale segment_dark_regions on the same frame.
Both drive the SHIPPED closure out of install() rather than a reimplementation of it --
`_flatten` is pulled out of the function's own __closure__ -- because this project has
twice been burnt by a figure that reimplemented the function it was supposed to measure.

FRAME SELECTION IS NOT ALPHABETICAL. The repo records a before/after spoiled by taking the
alphabetically-first 12 painted frames, which turned out to be two specimens. This takes
frames round-robin across specimens.

Run:
  NFRAMES=12 WORKERS=6 <sem-venv>/bin/python -B analysis/research/improve/decimate_guard.py
Writes docs/figures/decimate_guard.json and nothing else. Reads the paint read-only.
"""
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))
import _paths                                        # noqa: E402
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "code"))
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "interior_active_learning", "code"))
sys.dont_write_bytecode = True

import detect_cracks as D                            # noqa: E402
import detector_overrides as DO                      # noqa: E402

Image.MAX_IMAGE_PIXELS = None
SEM = _paths.SEM_REPO
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
OUT = os.path.join(REPO, "docs", "figures", "decimate_guard.json")

SHIPPED_LADDER = tuple(DO.SCALE_LADDER)                      # (5,10,20,40,80,160,320)
EXTENDED_LADDER = SHIPPED_LADDER + (640, 1280, 2560)         # the top under consideration
MAX_SIGMA = int(os.environ.get("MAX_SIGMA", "2560"))
SIGMAS = tuple(s for s in EXTENDED_LADDER if s <= MAX_SIGMA)
GATE = int(DO.ABSOLUTE_DARK_THRESH)
MAD_K = float(DO.SHIPPED_MAD_K)
SHIPPED_T = float(DO.DECIMATE_ABOVE_SIGMA)                   # 64
#: the sweep. inf = never decimate = the exact path, which is the reference arm.
THRESHOLDS = (32.0, 64.0, 128.0, 256.0, float("inf"))

PER_SPECIMEN = int(os.environ.get("PER_SPECIMEN", "2"))
LIMIT = int(os.environ.get("NFRAMES", "12"))
WORKERS = int(os.environ.get("WORKERS", "6"))
MIN_PAINT = 20000


def specimen_of(name):
    """Coarse specimen key: everything before the trailing capture index."""
    parts = name.split("_")
    while parts and (parts[-1].isdigit() or parts[-1] in ("CBS", "ETD", "SE", "BSE")):
        parts.pop()
    return "_".join(parts) or name


def pick_frames():
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
    return chosen, len(names), len(by_spec)


def shipped_flatten():
    """The REAL `_flatten` closure out of install(), not a copy of it."""
    class _V:
        pass
    v = _V()
    DO.install(v)
    f = v.segment_dark_regions
    cells = dict(zip(f.__code__.co_freevars,
                     (c.cell_contents for c in f.__closure__)))
    if "_flatten" not in cells:
        raise SystemExit("install() no longer closes over _flatten; this script is stale")
    return cells["_flatten"]


def rung_cutter():
    """A segment_dark_regions pinned to a one-rung ladder at sigma=40.

    install()'s union uses the caller's `flat` verbatim when sigma == 40, so this applies
    the SHIPPED cut (denoise, median/MAD, min(otsu, med - k*mad)) to whatever flattened
    image it is handed, exact or decimated, with the absolute gate switched off.
    """
    class _C:
        pass
    c = _C()
    DO.install(c, scale_ladder=(40,), use_multiscale_union=True, absolute_dark_thresh=0)
    return c.segment_dark_regions


def candidates(mask):
    """The cleaning chain's candidate stage, as the other frame scripts run it."""
    lab, _ = ndi.label(D.clean_mask(mask, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel())
    keep = np.where(sz >= 40)[0]
    return np.isin(lab, keep[keep > 0])


def breakdown(m, crack, notc, unrev):
    return dict(px=int(m.sum()), crack=int((m & crack).sum()),
                notcrack=int((m & notc).sum()), unreviewed=int((m & unrev).sum()))


def compare(a, b, crack, notc, unrev, npx):
    """b is the arm under test, a is the reference (exact). Both directions, in paint."""
    extra, missing = b & ~a, a & ~b
    return dict(
        ref_px=int(a.sum()), arm_px=int(b.sum()),
        differing_px=int(extra.sum() + missing.sum()),
        differing_frac=round(float(extra.sum() + missing.sum()) / npx, 10),
        fast_extra=breakdown(extra, crack, notc, unrev),
        fast_missing=breakdown(missing, crack, notc, unrev),
        is_superset_of_ref=bool(not missing.any()),
    )


def work(name):
    """One frame. Returns a dict, or {'frame':..., 'error':...}. Controls raise."""
    t_frame = time.time()
    img8 = D.load_as_uint8(os.path.join(SEM, "original", name + ".tif"))
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]
    corr = np.array(Image.open(os.path.join(PAINT, name + "_correction_mask.png")))
    corr = corr[..., 0] if corr.ndim == 3 else corr
    if corr.shape != img8.shape:
        if corr.shape[0] >= y1 and corr.shape[1] >= x1:
            corr = corr[y0:y1, x0:x1]
        else:
            return dict(frame=name, error=f"mask {corr.shape} vs frame {img8.shape}")
    vals = sorted(int(v) for v in np.unique(corr))
    crack = corr == 1
    notc = (corr == 2) | (corr == 3)
    unrev = corr == 0
    if int(crack.sum()) < MIN_PAINT:
        return dict(frame=name, error=f"only {int(crack.sum())} painted crack px")
    npx = int(img8.size)

    _flatten = shipped_flatten()
    cut_of = rung_cutter()
    gate = img8 < GATE

    # ---- CONTROL 1: decimation disabled must reproduce the stock flatten, bit for bit.
    # The branch is one line (`return dc.flatten_background(img8, sigma=sigma)`) and is
    # sigma-independent, so three sigmas spanning the guard are enough; checking it at
    # sigma=2560 would double the single most expensive array in the run.
    DO.DECIMATE_ABOVE_SIGMA = float("inf")
    ctrl1 = []
    for s in (5, 40, max(s for s in SIGMAS if s <= 320)):
        a = _flatten(img8, s)
        b = D.flatten_background(img8, sigma=s)
        if not np.array_equal(a, b):
            raise SystemExit(f"{name}: _flatten(sigma={s}) with decimation disabled is NOT "
                             f"detect_cracks.flatten_background ({int((a != b).sum())} px)")
        ctrl1.append(s)

    # ---- per-rung cuts, both ways. The exact array at sigma=max dominates the cost.
    cut_exact, cut_fast, t_exact, t_fast = {}, {}, {}, {}
    for s in SIGMAS:
        DO.DECIMATE_ABOVE_SIGMA = float("inf")
        t = time.time()
        fl = _flatten(img8, s)
        cut_exact[s] = cut_of(fl, img8=img8, mad_k=MAD_K)
        t_exact[s] = round(time.time() - t, 3)
        del fl
        DO.DECIMATE_ABOVE_SIGMA = 0.0
        t = time.time()
        fl = _flatten(img8, s)
        cut_fast[s] = cut_of(fl, img8=img8, mad_k=MAD_K)
        t_fast[s] = round(time.time() - t, 3)
        del fl
    DO.DECIMATE_ABOVE_SIGMA = SHIPPED_T

    def union(ladder, thresh, force_exact_at_40=True):
        out = gate.copy()
        for s in ladder:
            if s not in cut_exact:           # only when MAX_SIGMA truncates, i.e. smoke runs
                continue
            exact = (s <= thresh) or (force_exact_at_40 and s == 40)
            out |= cut_exact[s] if exact else cut_fast[s]
        return out

    # ---- CONTROL 2: recombined cuts at the shipped threshold == a direct shipped call.
    class _U:
        pass
    u = _U()
    DO.install(u)
    flat40 = D.flatten_background(img8, sigma=40)
    t = time.time()
    shipped_direct = u.segment_dark_regions(flat40, img8=img8, mad_k=MAD_K)
    t_shipped_endtoend = round(time.time() - t, 2)
    mine = union(SHIPPED_LADDER, SHIPPED_T)
    if not np.array_equal(mine, shipped_direct):
        raise SystemExit(f"{name}: cached rungs do not reproduce the shipped union "
                         f"({int((mine ^ shipped_direct).sum())} px)")

    row = dict(frame=name, specimen=specimen_of(name), frame_px=npx,
               frame_shape=[int(img8.shape[0]), int(img8.shape[1])],
               mask_values=vals,
               painted_crack_px=int(crack.sum()), painted_notcrack_px=int(notc.sum()),
               painted_crack_frac=round(float(crack.sum()) / npx, 6),
               controls=dict(exact_branch_bit_identical_at=ctrl1,
                             cached_rungs_reproduce_shipped_union=True),
               seconds_shipped_union_end_to_end=t_shipped_endtoend)

    # ---- 1/2. per rung, exact vs fast, and where the difference lands in the paint
    row["per_rung"] = {}
    for s in SIGMAS:
        c = compare(cut_exact[s], cut_fast[s], crack, notc, unrev, npx)
        c["decimation_factor"] = max(1, int(round(s / 32.0)))
        c["seconds_exact"] = t_exact[s]
        c["seconds_fast"] = t_fast[s]
        c["governed_by_guard"] = bool(s > SHIPPED_T)
        row["per_rung"][str(s)] = c

    # ---- unions and candidate masks over the sweep
    arms = {
        "32": (SHIPPED_LADDER, 32.0, True),
        "32_no40shortcut": (SHIPPED_LADDER, 32.0, False),
        "64_shipped": (SHIPPED_LADDER, 64.0, True),
        "128": (SHIPPED_LADDER, 128.0, True),
        "256": (SHIPPED_LADDER, 256.0, True),
        "never": (SHIPPED_LADDER, float("inf"), True),
    }
    if max(SIGMAS) >= 2560:
        arms["ext_64_shipped"] = (EXTENDED_LADDER, 64.0, True)
        arms["ext_never"] = (EXTENDED_LADDER, float("inf"), True)

    masks, t_cand = {}, {}
    for a, (lad, th, sc) in arms.items():
        masks[a] = union(lad, th, sc)
    ref = masks["never"]
    ext_ref = masks.get("ext_never")

    cand, row["union"], row["candidates"] = {}, {}, {}
    for a in arms:
        t = time.time()
        cand[a] = candidates(masks[a])
        t_cand[a] = round(time.time() - t, 2)
    for a, (lad, th, sc) in arms.items():
        r = ext_ref if a.startswith("ext_") else ref
        rc = cand["ext_never"] if a.startswith("ext_") else cand["never"]
        row["union"][a] = compare(r, masks[a], crack, notc, unrev, npx)
        row["candidates"][a] = compare(rc, cand[a], crack, notc, unrev, npx)
        row["candidates"][a]["seconds_clean_and_label"] = t_cand[a]

    # recall/precision-side context: what each arm actually delivers on the paint
    row["arm_scores"] = {
        a: dict(recall_on_painted_crack=round(float((cand[a] & crack).sum())
                                              / max(int(crack.sum()), 1), 6),
                rate_on_painted_notcrack=round(float((cand[a] & notc).sum())
                                               / max(int(notc.sum()), 1), 6),
                pct_of_frame_marked=round(100.0 * float(cand[a].sum()) / npx, 4))
        for a in arms}

    # ---- 3. superset of the STOCK single-scale mask?
    stock = D.segment_dark_regions(flat40, img8=img8, mad_k=MAD_K,
                                   absolute_dark_thresh=GATE)
    row["stock_single_scale"] = dict(
        px=int(stock.sum()),
        painted_crack_px=int((stock & crack).sum()),
    )
    stock_cand = candidates(stock)
    for a in ("64_shipped", "never", "32_no40shortcut"):
        lost = stock & ~masks[a]
        lost_c = stock_cand & ~cand[a]
        row["stock_single_scale"][a] = dict(
            union_is_superset_of_stock=bool(not lost.any()),
            union_px_of_stock_lost=int(lost.sum()),
            union_painted_crack_lost=int((lost & crack).sum()),
            candidates_is_superset_of_stock_candidates=bool(not lost_c.any()),
            candidates_px_lost=int(lost_c.sum()),
            candidates_painted_crack_lost=int((lost_c & crack).sum()),
        )

    # ---- 4. cost. Per-rung cost is flatten+cut; the sigma=40 shortcut is free either way.
    row["cost_seconds"] = {}
    for a, (lad, th, sc) in arms.items():
        tot = 0.0
        for s in lad:
            if s not in t_exact:
                continue
            exact = (s <= th) or (sc and s == 40)
            tot += t_exact[s] if exact else t_fast[s]
        row["cost_seconds"][a] = dict(
            ladder_seconds=round(tot, 2),
            clean_seconds=t_cand[a],
            total_seconds=round(tot + t_cand[a], 2))
    row["seconds_frame_total"] = round(time.time() - t_frame, 1)
    return row


def pooled(rows, section, keys):
    """Sum the integer leaves of `section` across frames, per arm."""
    out = {}
    for a in rows[0][section]:
        d = {}
        for k in keys:
            if isinstance(rows[0][section][a].get(k), dict):
                d[k] = {kk: int(sum(r[section][a][k][kk] for r in rows))
                        for kk in rows[0][section][a][k]}
            else:
                d[k] = int(sum(r[section][a][k] for r in rows))
        d["n_frames_differing"] = sum(1 for r in rows if r[section][a]["differing_px"])
        d["n_frames_fast_drops_painted_crack"] = sum(
            1 for r in rows if r[section][a]["fast_missing"]["crack"])
        d["worst_frame_differing_px"] = max(
            (r[section][a]["differing_px"], r["frame"]) for r in rows)[::-1]
        d["worst_frame_painted_crack_dropped"] = max(
            (r[section][a]["fast_missing"]["crack"], r["frame"]) for r in rows)[::-1]
        out[a] = d
    return out


def main():
    t0 = time.time()
    chosen, n_painted, n_spec_all = pick_frames()
    print(f"{len(chosen)} frames from {len({specimen_of(n) for n in chosen})} specimens "
          f"(round-robin, up to {PER_SPECIMEN} each), out of {n_painted} painted frames "
          f"over {n_spec_all} specimens")
    print(f"sigmas {SIGMAS}   shipped DECIMATE_ABOVE_SIGMA={SHIPPED_T}   "
          f"mad_k={MAD_K}   gate={GATE}   workers={WORKERS}\n", flush=True)

    rows = []
    if WORKERS > 1:
        import multiprocessing as mp
        ctx = mp.get_context("spawn")
        with ctx.Pool(WORKERS) as pool:
            for r in pool.imap_unordered(work, chosen):
                rows.append(r)
                tag = r.get("error") or (
                    f"union diff {r['union']['64_shipped']['differing_px']:>8,} px, "
                    f"painted crack dropped "
                    f"{r['union']['64_shipped']['fast_missing']['crack']:>7,}")
                print(f"{r['frame']:<40} {tag}   ({time.time()-t0:.0f}s)", flush=True)
    else:
        for n in chosen:
            r = work(n)
            rows.append(r)
            print(f"{r['frame']:<40} {r.get('error', 'ok')}   "
                  f"({time.time()-t0:.0f}s)", flush=True)

    bad = [r for r in rows if r.get("error")]
    rows = sorted((r for r in rows if not r.get("error")), key=lambda r: r["frame"])
    if not rows:
        raise SystemExit("no frames scored")

    npx = sum(r["frame_px"] for r in rows)
    tot_crack = sum(r["painted_crack_px"] for r in rows)
    tot_notc = sum(r["painted_notcrack_px"] for r in rows)

    cmp_keys = ["differing_px", "fast_extra", "fast_missing"]
    rung = {}
    for s in map(str, SIGMAS):
        d = {k: ({kk: int(sum(r["per_rung"][s][k][kk] for r in rows))
                  for kk in rows[0]["per_rung"][s][k]}
                 if isinstance(rows[0]["per_rung"][s][k], dict)
                 else int(sum(r["per_rung"][s][k] for r in rows)))
             for k in cmp_keys}
        d["differing_frac_pooled"] = round(d["differing_px"] / npx, 10)
        d["decimation_factor"] = rows[0]["per_rung"][s]["decimation_factor"]
        d["governed_by_guard"] = rows[0]["per_rung"][s]["governed_by_guard"]
        d["mean_seconds_exact"] = round(
            sum(r["per_rung"][s]["seconds_exact"] for r in rows) / len(rows), 2)
        d["mean_seconds_fast"] = round(
            sum(r["per_rung"][s]["seconds_fast"] for r in rows) / len(rows), 2)
        d["n_frames_fast_drops_painted_crack"] = sum(
            1 for r in rows if r["per_rung"][s]["fast_missing"]["crack"])
        d["pct_of_painted_crack_dropped"] = round(
            100.0 * d["fast_missing"]["crack"] / max(tot_crack, 1), 6)
        rung[s] = d

    arms = list(rows[0]["union"])
    cost = {a: dict(
        mean_ladder_seconds=round(sum(r["cost_seconds"][a]["ladder_seconds"]
                                      for r in rows) / len(rows), 2),
        mean_clean_seconds=round(sum(r["cost_seconds"][a]["clean_seconds"]
                                     for r in rows) / len(rows), 2),
        mean_total_seconds=round(sum(r["cost_seconds"][a]["total_seconds"]
                                     for r in rows) / len(rows), 2),
    ) for a in arms}
    scores = {a: dict(
        recall_on_painted_crack=round(
            sum(r["arm_scores"][a]["recall_on_painted_crack"] * r["painted_crack_px"]
                for r in rows) / max(tot_crack, 1), 6),
        rate_on_painted_notcrack=round(
            sum(r["arm_scores"][a]["rate_on_painted_notcrack"] * r["painted_notcrack_px"]
                for r in rows) / max(tot_notc, 1), 6),
        pct_of_frame_marked=round(
            sum(r["arm_scores"][a]["pct_of_frame_marked"] * r["frame_px"]
                for r in rows) / npx, 4),
        median_per_frame_recall=round(sorted(
            r["arm_scores"][a]["recall_on_painted_crack"] for r in rows)[len(rows) // 2], 6),
    ) for a in arms}

    stock_keys = ("64_shipped", "never", "32_no40shortcut")
    stock = {a: dict(
        frames_where_union_is_superset=sum(
            1 for r in rows if r["stock_single_scale"][a]["union_is_superset_of_stock"]),
        frames_total=len(rows),
        union_px_of_stock_lost=int(sum(
            r["stock_single_scale"][a]["union_px_of_stock_lost"] for r in rows)),
        union_painted_crack_lost=int(sum(
            r["stock_single_scale"][a]["union_painted_crack_lost"] for r in rows)),
        frames_where_candidates_is_superset=sum(
            1 for r in rows
            if r["stock_single_scale"][a]["candidates_is_superset_of_stock_candidates"]),
        candidates_px_lost=int(sum(
            r["stock_single_scale"][a]["candidates_px_lost"] for r in rows)),
        candidates_painted_crack_lost=int(sum(
            r["stock_single_scale"][a]["candidates_painted_crack_lost"] for r in rows)),
    ) for a in stock_keys}

    rec = dict(
        what=("DECIMATE_ABOVE_SIGMA re-validated at frame scale: exact vs decimated "
              "background estimation, per rung, per union, per candidate mask, scored "
              "against the hand-painted correction masks"),
        generated=time.strftime("%Y-%m-%d"),
        why=("the guard's only prior check is on 512 px tiles, where the rungs it governs "
             "are inert -- docs/figures/ladder_endpoints.json 'saturation' shows "
             "sigma=2560 moving 307 px in 6,815,744 against the rung below it"),
        instrument=os.path.relpath(os.path.abspath(__file__), REPO),
        constants=dict(shipped_DECIMATE_ABOVE_SIGMA=SHIPPED_T,
                       SCALE_LADDER=list(SHIPPED_LADDER),
                       extended_ladder=list(EXTENDED_LADDER),
                       mad_k=MAD_K, absolute_dark_thresh=GATE,
                       decimation_factor_rule="f = max(1, round(sigma / 32))"),
        sigma40_shortcut=("install()'s union uses the caller's exact flat when sigma == 40 "
                          "(`f = flat if sigma == 40 else _flatten(img8, sigma)`), so the "
                          "sigma=40 rung is never decimated at any threshold. Arms '32' "
                          "and '64_shipped' are therefore the same computation on the "
                          "shipped ladder; '32_no40shortcut' is the counterfactual."),
        scoring="correction masks: 1 = crack, 2 or 3 = not-crack, 0 = unreviewed",
        frame_selection=(f"round-robin across specimens, up to {PER_SPECIMEN} per "
                         f"specimen, NOT alphabetical"),
        n_frames=len(rows), n_specimens=len({r["specimen"] for r in rows}),
        n_painted_frames_available=n_painted, n_specimens_available=n_spec_all,
        total_frame_px=npx, painted_crack_px=tot_crack, painted_notcrack_px=tot_notc,
        skipped=[dict(frame=r["frame"], reason=r["error"]) for r in bad],
        controls={
            "decimation_disabled_reproduces_stock_flatten_bit_for_bit":
                f"PASS on {len(rows)}/{len(rows)} frames at sigma "
                f"{rows[0]['controls']['exact_branch_bit_identical_at']}",
            "cached_rungs_reproduce_shipped_union":
                f"PASS on {len(rows)}/{len(rows)} frames",
            "both_controls_raise_SystemExit_on_failure": True,
            "shipped_closure_not_a_reimplementation":
                "_flatten and the darkness cut are pulled out of detector_overrides."
                "install()'s own closure and called directly",
        },
        direction_key=dict(
            fast_extra="pixels the decimated path marks that the exact path does not",
            fast_missing="pixels the EXACT path marks that the decimated path does not "
                         "-- the dangerous direction"),
        per_rung_pooled=rung,
        union_pooled=pooled(rows, "union", cmp_keys),
        candidates_pooled=pooled(rows, "candidates", cmp_keys),
        arm_scores_pooled=scores,
        cost_seconds_mean_per_frame=cost,
        cost_note=(f"measured with WORKERS={WORKERS} concurrent frame processes on this "
                   f"machine; relative cost between arms is the usable quantity, absolute "
                   f"seconds are inflated by contention when WORKERS > 1"),
        superset_of_stock_single_scale=stock,
        per_frame=rows,
        seconds=round(time.time() - t0, 1),
    )
    json.dump(rec, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}  ({rec['seconds']}s)")

    print(f"\nPER RUNG (pooled over {len(rows)} frames, {npx/1e6:.0f} Mpx)")
    print(f"{'sigma':>6} {'f':>3} {'guard':>6} {'diff px':>12} {'diff frac':>11} "
          f"{'fast drops crack':>17} {'exact s':>8} {'fast s':>8}")
    for s in map(str, SIGMAS):
        d = rung[s]
        print(f"{s:>6} {d['decimation_factor']:>3} "
              f"{'yes' if d['governed_by_guard'] else 'no':>6} "
              f"{d['differing_px']:>12,} {d['differing_frac_pooled']:>11.3e} "
              f"{d['fast_missing']['crack']:>17,} "
              f"{d['mean_seconds_exact']:>8.1f} {d['mean_seconds_fast']:>8.1f}")

    for sect, title in (("union_pooled", "FULL UNION vs exact"),
                        ("candidates_pooled", "CANDIDATE MASK vs exact")):
        print(f"\n{title} (pooled)")
        print(f"{'arm':<18} {'diff px':>12} {'crack dropped':>14} {'crack added':>12} "
              f"{'notcrack added':>15} {'superset':>9} {'mean s':>8}")
        for a in arms:
            d = rec[sect][a]
            print(f"{a:<18} {d['differing_px']:>12,} "
                  f"{d['fast_missing']['crack']:>14,} {d['fast_extra']['crack']:>12,} "
                  f"{d['fast_extra']['notcrack']:>15,} "
                  f"{str(all(r[sect.split('_')[0]][a]['is_superset_of_ref'] for r in rows)):>9} "
                  f"{cost[a]['mean_total_seconds']:>8.1f}")

    print("\nCOST / FIDELITY")
    print(f"{'arm':<18} {'ladder s':>9} {'total s':>9} {'union diff px':>14} "
          f"{'% of painted crack moved':>25} {'recall':>8}")
    for a in arms:
        d = rec["union_pooled"][a]
        moved = 100.0 * (d["fast_extra"]["crack"] + d["fast_missing"]["crack"]) / max(tot_crack, 1)
        print(f"{a:<18} {cost[a]['mean_ladder_seconds']:>9.1f} "
              f"{cost[a]['mean_total_seconds']:>9.1f} {d['differing_px']:>14,} "
              f"{moved:>25.6f} {scores[a]['recall_on_painted_crack']:>8.4f}")

    print("\nSUPERSET OF THE STOCK SINGLE-SCALE MASK")
    for a in stock_keys:
        d = stock[a]
        print(f"  {a:<18} union {d['frames_where_union_is_superset']}/{d['frames_total']} "
              f"frames (lost {d['union_px_of_stock_lost']:,} px, "
              f"{d['union_painted_crack_lost']:,} painted) | candidates "
              f"{d['frames_where_candidates_is_superset']}/{d['frames_total']} "
              f"(lost {d['candidates_px_lost']:,} px, "
              f"{d['candidates_painted_crack_lost']:,} painted)")
    return rec


if __name__ == "__main__":
    main()
