#!/usr/bin/env python3
"""The ladder's TOP, on full frames, where the 512 px tiles provably cannot speak.

WHAT THE TILE SWEEP SETTLED AND WHAT IT COULD NOT. ladder_endpoints.py sweeps base, top
and step on the 26 hand-labelled tiles. Two of its results stand on their own:

  the base is wrong      dropping sigma=5 RAISES pooled tile IoU, 0.2290 -> 0.2301, and
                         the same +0.001 appears at every top in the grid
  the mid rungs earn it  trimming to 40-320 or 80-320 costs 0.014-0.016 IoU

Its third result does not stand, and the saturation table in its own record is why: on a
512 px tile, sigma=2560 changes 307 pixels out of 6,815,744 against the rung below it
(0.0045%). flatten_background subtracts a gaussian-blurred copy, so once sigma approaches
the tile width the "background" is within a hair of a global constant and the high-pass
has stopped being local. A tile cannot tell a sigma=2560 rung from a sigma=320 one, so the
tile ranking of the TOP of the ladder is a ranking of noise -- which is exactly what its
leave-one-specimen-out folds show: 11 of 13 vote for a 9-rung ladder, but 4 of those folds
score 0.0000 either way, 4 more are worse for the pick, and the entire mean gain is ONE
specimen moving 0.6067 -> 0.6788.

So the top is tested here instead, at 25 Mpx, where a sigma=320 background estimate is
genuinely local and a sigma=2560 one is still well inside the frame.

SCORED ON THE CORRECTION MASKS, read only: 1 = crack, 2 = not-crack, 3 = erased (also a
not-crack verdict), 0 = unreviewed and excluded from both. Per frame as well as pooled,
because this project has twice had a pooled recall that was five frames.

FRAME SELECTION IS NOT ALPHABETICAL. The repo records a previous before/after taken on
"the ALPHABETICALLY FIRST 12" frames, which came from two specimens. This takes up to
PER_SPECIMEN frames from each specimen in turn, so the sample spans the corpus.

Run:  NFRAMES=18 <sem-venv>/bin/python -B analysis/research/improve/ladder_endpoints_frames.py
Writes docs/figures/ladder_endpoints_frames.json.
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
OUT = os.path.join(REPO, "docs", "figures", "ladder_endpoints_frames.json")

#: The candidates. Only the questions the tiles left open: does dropping sigma=5 hold at
#: frame scale, and does the top keep paying past 320?
LADDERS = {
    "shipped_5-320": (5, 10, 20, 40, 80, 160, 320),
    "drop5_10-320": (10, 20, 40, 80, 160, 320),
    "drop5_top640": (10, 20, 40, 80, 160, 320, 640),
    "drop5_top1280": (10, 20, 40, 80, 160, 320, 640, 1280),
    "drop5_top2560": (10, 20, 40, 80, 160, 320, 640, 1280, 2560),
    "keep5_top2560": (5, 10, 20, 40, 80, 160, 320, 640, 1280, 2560),
}
SIGMAS = tuple(sorted({s for L in LADDERS.values() for s in L}))
GATE = int(DO.ABSOLUTE_DARK_THRESH)
PER_SPECIMEN = int(os.environ.get("PER_SPECIMEN", "2"))
LIMIT = int(os.environ.get("NFRAMES", "18"))
MIN_PAINT = 20000


def specimen_of(name):
    """Coarse specimen key: everything before the trailing capture index."""
    parts = name.split("_")
    while parts and (parts[-1].isdigit() or parts[-1] in ("CBS", "ETD", "SE", "BSE")):
        parts.pop()
    return "_".join(parts) or name


def candidates(mask):
    """The cleaning chain's candidate stage, as absdark_frames.py runs it."""
    lab, _ = ndi.label(D.clean_mask(mask, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel())
    keep = np.where(sz >= 40)[0]
    return np.isin(lab, keep[keep > 0])


def main():
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
    print(f"{len(chosen)} frames from {len({specimen_of(n) for n in chosen})} specimens "
          f"(up to {PER_SPECIMEN} each), out of {len(names)} painted frames\n")

    acc = {L: dict(tp=0, fp=0, area=0) for L in LADDERS}
    tot = dict(crack=0, notc=0, px=0, n=0)
    per_frame, superset_violations = [], []

    for n in chosen:
        try:
            img8 = D.load_as_uint8(os.path.join(SEM, "original", n + ".tif"))
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
                continue

            flat = D.flatten_background(img8, sigma=40)
            gate = img8 < GATE
            cuts = {}
            for s in SIGMAS:
                class _V:
                    pass
                v = _V()
                DO.install(v, scale_ladder=(s,), use_multiscale_union=True,
                           absolute_dark_thresh=0)
                cuts[s] = v.segment_dark_regions(flat, img8=img8, mad_k=5.0)

            # CONTROL: the cached decomposition must equal a direct shipped call.
            class _U:
                pass
            u = _U()
            DO.install(u)
            mine = gate.copy()
            for s in LADDERS["shipped_5-320"]:
                mine |= cuts[s]
            if not np.array_equal(mine, u.segment_dark_regions(flat, img8=img8,
                                                               mad_k=5.0)):
                raise SystemExit(f"{n}: cached rungs do not reproduce the shipped union")

            row = dict(frame=n, specimen=specimen_of(n),
                       painted_crack_px=int(crack.sum()),
                       painted_notcrack_px=int(notc.sum()), frame_px=int(img8.size))
            base_mask = None
            for L, rungs in LADDERS.items():
                prop = gate.copy()
                for s in rungs:
                    prop |= cuts[s]
                m = candidates(prop)
                if L == "shipped_5-320":
                    base_mask = m
                tp, fp = int((m & crack).sum()), int((m & notc).sum())
                acc[L]["tp"] += tp
                acc[L]["fp"] += fp
                acc[L]["area"] += int(m.sum())
                row[L] = dict(recall=round(tp / max(int(crack.sum()), 1), 4),
                              notcrack_rate=round(fp / max(int(notc.sum()), 1), 4),
                              marked_pct=round(100 * int(m.sum()) / img8.size, 4))
                # dropping sigma=5 is SUBTRACTIVE: it can lose a pixel the shipped
                # ladder kept. That is the risk the tiles cannot price, so count it.
                if base_mask is not None and L != "shipped_5-320":
                    lost = int((base_mask & ~m).sum())
                    lost_painted = int((base_mask & ~m & crack).sum())
                    row[L]["px_lost_vs_shipped"] = lost
                    row[L]["painted_crack_lost_vs_shipped"] = lost_painted
                    if lost_painted:
                        superset_violations.append((n, L, lost_painted))
            tot["crack"] += int(crack.sum())
            tot["notc"] += int(notc.sum())
            tot["px"] += img8.size
            tot["n"] += 1
            per_frame.append(row)
            cells = " ".join(f"{row[L]['recall']:7.4f}" for L in LADDERS)
            print(f"{n:<36} {int(crack.sum()):>10,} | {cells}   ({time.time()-t0:.0f}s)",
                  flush=True)
        except SystemExit:
            raise
        except Exception as e:
            print(f"{n:<36}  ERROR {type(e).__name__}: {e}", flush=True)

    summary = {L: dict(
        rungs=list(LADDERS[L]), n_rungs=len(LADDERS[L]),
        recall_on_painted_crack=round(acc[L]["tp"] / max(tot["crack"], 1), 4),
        rate_on_painted_notcrack=round(acc[L]["fp"] / max(tot["notc"], 1), 4),
        pct_of_frame_marked=round(100 * acc[L]["area"] / max(tot["px"], 1), 4),
    ) for L in LADDERS}

    # per-frame medians, because a pooled recall here has been five frames before
    for L in LADDERS:
        rs = sorted(r[L]["recall"] for r in per_frame)
        summary[L]["median_per_frame_recall"] = round(rs[len(rs) // 2], 4) if rs else None
        summary[L]["n_frames_better_than_shipped"] = sum(
            1 for r in per_frame if r[L]["recall"] > r["shipped_5-320"]["recall"])
        summary[L]["n_frames_worse_than_shipped"] = sum(
            1 for r in per_frame if r[L]["recall"] < r["shipped_5-320"]["recall"])

    rec = dict(
        what="the scale ladder's base and top, on full frames, scored against the paint",
        generated=time.strftime("%Y-%m-%d"),
        why_not_tiles=("on a 512 px tile sigma=2560 changes 307 px in 6,815,744 against "
                       "the rung below it, so the tile bench cannot rank the top of the "
                       "ladder; see docs/figures/ladder_endpoints.json saturation"),
        scoring="correction masks: 1 = crack, 2 or 3 = not-crack, 0 excluded",
        frame_selection=f"up to {PER_SPECIMEN} per specimen, NOT alphabetical",
        n_frames=tot["n"], n_specimens=len({r["specimen"] for r in per_frame}),
        painted_crack_px=tot["crack"], painted_notcrack_px=tot["notc"],
        mad_k=5.0, absolute_dark_thresh=GATE,
        use_region_classifier=DO.USE_REGION_CLASSIFIER,
        controls={"cached_rungs_reproduce_shipped_union": "PASS on every frame scored"},
        subtractive_warning=(
            "every arm that drops sigma=5 can delete a pixel the shipped ladder kept; "
            "px_lost_vs_shipped and painted_crack_lost_vs_shipped are per frame"),
        frames_losing_painted_crack=superset_violations,
        ladders=summary, per_frame=per_frame,
        seconds=round(time.time() - t0, 1),
    )
    json.dump(rec, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}  ({rec['seconds']}s)\n")
    print(f"{'ladder':<16} {'n':>3} {'recall':>8} {'median':>8} {'notcrack':>9} "
          f"{'marked%':>8} {'better':>7} {'worse':>6}")
    for L in LADDERS:
        v = summary[L]
        print(f"{L:<16} {v['n_rungs']:>3} {v['recall_on_painted_crack']:>8.4f} "
              f"{v['median_per_frame_recall']:>8.4f} "
              f"{v['rate_on_painted_notcrack']:>9.4f} {v['pct_of_frame_marked']:>8.3f} "
              f"{v['n_frames_better_than_shipped']:>7} "
              f"{v['n_frames_worse_than_shipped']:>6}")
    if superset_violations:
        print(f"\n{len(superset_violations)} (frame, ladder) pairs DELETE painted crack "
              f"relative to the shipped ladder:")
        for n, L, px in superset_violations[:10]:
            print(f"   {n}  {L}  -{px:,} px")
    return rec


if __name__ == "__main__":
    main()
