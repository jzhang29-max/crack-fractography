#!/usr/bin/env python3
"""Figure 5: what over-counting and under-counting look like, in both modalities.

WHY. The paper reports a precision and a recall for each collection and leaves a reader to
imagine what the two failures look like. They look like completely different things, and
which one dominates decides what a user of the measurement should do about it: an
over-count is a bright inclusion halo or a polishing artefact that a human can see and
reject at a glance, and an under-count is a crack that was never proposed and that the
user will never be shown. A number cannot tell those apart; two pictures can.

WHICH FRAMES, BY RULE, AND WHY THE WORST RATHER THAN THE TYPICAL. Each panel comes from
the frame holding the most pixels of its own error kind, and within it from the window
holding the most -- both found from numbers, never by eye. The frames are ranked from
`docs/figures/overlap_means_sem_txm.json`, where the per-frame precision and recall are
measured, so this figure cannot disagree with the table beside it; the window is found
exactly by a box sum over the summed-area table.

A first version of this figure used the median-F1 frame instead, and its over-counting
panels held 0.5% and 0.03% over-counted pixels: on a typical frame there is essentially no
over-counting to look at, which is the collection's precision stated as a picture. That is
a result, and it belongs in the text rather than in a panel captioned "over-counted" and
showing nothing. So each panel is the WORST case of its kind, the caption says so, and the
caption JSON records what share of all of that collection's error of that kind the chosen
frame holds -- which is the number that says whether the picture is one pathology or a
general tendency.

EVERY PANEL SHOWS BOTH ERRORS AND THE AGREEMENT. A panel selected for over-counting still
draws the under-counts and the agreement in it. Showing a pure example of each failure
would mean finding a window where the other does not occur, which is a claim about the
data rather than an illustration of a definition.

UNREVIEWED PIXELS ARE NOT AN ERROR AND ARE NOT COLOURED. Neither collection adjudicates
the whole frame. A marked pixel nobody looked at is left grey, and the caption gives the
share of each panel that is in that state, because colouring it either way would be the
mistake that once turned a precision of 0.99 into 0.29 in this project.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_counting.py
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths                                       # noqa: E402

sys.path.insert(0, _paths.ANALYSIS)
sys.path.insert(0, os.path.join(_paths.ANALYSIS, "research", "improve"))
sys.dont_write_bytecode = True

import numpy as np                                  # noqa: E402
import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.patches import Rectangle            # noqa: E402
from skimage import exposure                        # noqa: E402

import overlap_means_sem_txm as OV                  # noqa: E402  -- loaders and scorer
import both_modalities as BM                        # noqa: E402  -- pixel sizes
import journal_style as J                           # noqa: E402
from scalebar import scalebar                       # noqa: E402

J.use()
OUT = _paths.FIG_DIR
NAME = "F5 - over- and under-counting"
DOCFIG = os.path.join(os.path.dirname(os.path.dirname(HERE)), "docs", "figures")
# THE RESTRICTED RECORDS. The paper reports on specimen series b2 and b3, so the frame
# this plate chooses must be chosen from that pool: the previous run picked
# AS_24hr_BSE_Side_008 and an AM/HC frame, neither of which is in the paper any more.
# `scoped()` raises if a record is missing rather than falling back to the full corpus.
SCORES = _paths.scoped("overlap_means_sem_txm.json")
TRACES = _paths.scoped("paint_region_vs_trace.json")
LEGIB = _paths.scoped("frame_legibility.json")

#: An over-counting panel has to show over-counting, not one object. On the TXM frame
#: with the most over-counted pixels, 98.8% of that area is a SINGLE connected component
#: -- one large low-attenuation region the operator rejected -- so the panel was a red
#: rectangle whatever window was cut from it. A frame is eligible for the over-counting
#: column only if its largest false-positive component is at most this share of its
#: false-positive area. The shares are measured per frame by
#: `analysis/research/improve/frame_legibility.py`.
MAX_FP_CONCENTRATION = 0.35

#: A frame is eligible only if its annotation is a TRACE rather than a filled region: at
#: most this share of its painted-crack pixels further than 50 px inside the paint. It is
#: the criterion `paint_region_vs_trace.py` measures and `mk_txm_pipeline.py` already
#: selects on, and without it this figure is a picture of the brush. On the frames it
#: excludes, the paint asserts "there is crack in this region" over strokes 468 px wide at
#: the median, so a window inside one is solid "under-counted" whatever the detector does:
#: the first run of this figure produced exactly that, two panels of flat colour.
MAX_DEEP_SHARE = 0.25

#: The window each panel shows, in micrometres. Wide enough that the SEM paint, whose 90th
#: percentile stroke is 14 um, does not fill it: a window narrower than the brush shows
#: nothing but brush.
FOV_UM = 30.0

AGREE, OVER, UNDER = J.MASK, J.ROI, J.PAINT_CRACK


def worst_frames(coll):
    """Per error kind, the frame holding the most pixels of it, from the measured file.

    The scorer records precision, recall and the painted-crack count per frame, which
    determines the confusion matrix exactly:

        tp = recall x crack_px        fp = tp x (1 - precision) / precision
        fn = crack_px - tp

    so the ranking needs no detector run, and the two frames it picks are the only ones
    that have to be loaded.
    """
    rows = json.load(open(SCORES))[coll]["per_frame"]
    deep = {r["frame"]: r["deep_share"]
            for r in json.load(open(TRACES))[coll]["frames"]}
    if not os.path.exists(LEGIB):
        raise SystemExit(
            f"{LEGIB} is missing. Run analysis/research/improve/frame_legibility.py: the "
            f"over-counting panel is chosen on a measured property of each frame and must "
            f"not fall back to the unconstrained maximum.")
    conc = {r["frame"]: r["fp_largest_share"]
            for r in json.load(open(LEGIB))[coll]}
    missing = [r["frame"] for r in rows if r["frame"] not in deep]
    if missing:
        raise SystemExit(f"{coll}: no trace/region measurement for {missing[:3]}")
    kept = [r for r in rows if deep[r["frame"]] <= MAX_DEEP_SHARE]
    if not kept:
        raise SystemExit(f"{coll}: no frame has a trace annotation")
    print(f"  {coll}: {len(kept)} of {len(rows)} frames annotated as a trace "
          f"(deep share <= {MAX_DEEP_SHARE})", flush=True)
    rows = kept
    for r in rows:
        tp = r["recall"] * r["crack_px"]
        r["_fp"] = tp * (1.0 - r["precision"]) / max(r["precision"], 1e-12)
        r["_fn"] = r["crack_px"] - tp
    tot = {"over-counted": sum(r["_fp"] for r in rows),
           "under-counted": sum(r["_fn"] for r in rows)}
    out = {}
    for kind, key in (("over-counted", "_fp"), ("under-counted", "_fn")):
        pool = rows
        if kind == "over-counted":
            pool = [r for r in rows
                    if conc.get(r["frame"], 1.0) <= MAX_FP_CONCENTRATION] or rows
        best = max(pool, key=lambda r: r[key])
        out[kind] = {"frame": best["frame"], "f1": best["f1"],
                     "precision": best["precision"], "recall": best["recall"],
                     "px_of_this_kind": int(round(best[key])),
                     "collection_px_of_this_kind": int(round(tot[kind])),
                     "share_of_collection": (best[key] / tot[kind]
                                             if tot[kind] > 0 else None),
                     "eligible_frames": len(pool),
                     "fp_largest_share": conc.get(best["frame"]),
                     "max_fp_concentration": (MAX_FP_CONCENTRATION
                                              if kind == "over-counted" else None),
                     "deep_share": deep[best["frame"]],
                     "max_deep_share": MAX_DEEP_SHARE}
    return out


def fetch(coll, want):
    """Load one named frame through the collection's own loader, stopping when found."""
    it = OV.sem_frames() if coll == "SEM" else OV.txm_frames()
    for nm, img8, corr in it:
        if nm == want:
            return img8, corr
    raise SystemExit(f"{coll}: {want} not found by its own loader")


#: A panel must not be a solid block of one colour. The paint here is broad-brush -- the
#: SEM stroke is 14 um wide at the 90th percentile -- so the window holding the MOST
#: pixels of an error kind is routinely a window holding nothing else: the first run of
#: this figure produced an under-counted panel that was 99.98% under-counted and an
#: over-counted panel that was 100% over-counted, which show a colour rather than a
#: failure. Capping the error kind's share forces the window onto the BOUNDARY of the
#: error, where the mask, the paint and the matrix are all visible at once.
MAX_ERROR_SHARE = 0.25


#: A window may not be mostly pixels nobody adjudicated. The under-counting panel first
#: came out two thirds BLACK: the frame's widest crack has an unreviewed interior, the
#: detector marks it, and an unreviewed pixel is correctly left uncoloured -- so the panel
#: was dominated by a region that carries no verdict either way and illustrates neither
#: error. Capping that share puts the window on the part of the crack a human actually
#: ruled on.
MAX_UNREVIEWED_SHARE = 0.25


def _boxsum(mask, sdim):
    ii = np.pad(np.cumsum(np.cumsum(mask.astype(np.int64), 0), 1), ((1, 0), (1, 0)))
    return (ii[sdim:, sdim:] - ii[:-sdim, sdim:] - ii[sdim:, :-sdim]
            + ii[:-sdim, :-sdim])


def densest(mask, side, max_frac=MAX_ERROR_SHARE, veto=None,
            max_veto=MAX_UNREVIEWED_SHARE):
    """The `side` x `side` window holding the most True pixels, among the admissible ones.

    Exact, not sampled: box sums over the summed-area table, then the maximum over the
    boxes whose True fraction is at most `max_frac` and whose `veto` fraction is at most
    `max_veto`. Falls back to the unconstrained maximum when no box satisfies both and
    SAYS SO in the caption file, rather than silently returning a window chosen by a
    different rule than the caption states.
    """
    h, w = mask.shape
    sdim = min(side, h, w)
    box = _boxsum(mask, sdim)
    ok = box <= max_frac * sdim * sdim
    if veto is not None:
        ok &= _boxsum(veto, sdim) <= max_veto * sdim * sdim
    capped = bool(ok.any())
    search = np.where(ok, box, -1) if capped else box
    y, x = np.unravel_index(int(search.argmax()), search.shape)
    return int(y), int(x), sdim, int(box[y, x]), capped


def main():
    nm_per_px = {"SEM": BM.SEM_NM_PER_PX, "TXM": BM.TXM_NM_PER_PX}
    panels, meta = [], {}
    for coll in ("SEM", "TXM"):
        picks = worst_frames(coll)
        meta[coll] = picks
        cache = {}
        for kind in ("over-counted", "under-counted"):
            frame = picks[kind]["frame"]
            if frame not in cache:
                cache[frame] = fetch(coll, frame)
            img8, corr = cache[frame]
            pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
            mask = OV.clean(OV.u.segment_dark_regions(OV.D.flatten_background(img8),
                                                      img8=img8, mad_k=OV.MADK))
            agree, over, under = mask & pos, mask & neg, pos & ~mask
            sel = over if kind == "over-counted" else under
            nm = nm_per_px[coll]
            side = int(round(FOV_UM * 1000.0 / nm))
            y, x, sdim, cnt, capped = densest(sel, side,
                                              veto=mask & ~pos & ~neg)
            sl = (slice(y, y + sdim), slice(x, x + sdim))
            # 0.5/99.5, not 2/98: on the BSE side-view frames 2/98 clips enough of the
            # dark tail that the matrix prints as paper-white and the panel loses its
            # context entirely. These are also the percentiles the application's own
            # 8-bit loader uses, so the panel is stretched the way the operator saw it.
            lo, hi = np.percentile(img8[sl], [0.5, 99.5])
            grey = (exposure.rescale_intensity(img8[sl].astype(np.float32),
                                               in_range=(lo, hi), out_range=(0.0, 1.0))
                    if hi > lo else img8[sl].astype(np.float32) / 255.0)
            rgb = np.dstack([grey] * 3)
            rgb[under[sl]] = np.array(J.rgb(UNDER))
            rgb[agree[sl]] = np.array(J.rgb(AGREE))
            rgb[over[sl]] = np.array(J.rgb(OVER))
            panels.append({
                "coll": coll, "kind": kind, "rgb": np.clip(rgb, 0, 1), "nm": nm,
                "frame": frame, "side": sdim, "origin": [y, x], "selected_px": cnt,
                "fov_um": FOV_UM, "share_caps_applied": capped,
                "max_error_share": MAX_ERROR_SHARE,
                "max_unreviewed_share": MAX_UNREVIEWED_SHARE,
                "agree_pct": 100 * float(agree[sl].mean()),
                "over_pct": 100 * float(over[sl].mean()),
                "under_pct": 100 * float(under[sl].mean()),
                "marked_unreviewed_pct": 100 * float(
                    (mask[sl] & ~pos[sl] & ~neg[sl]).mean())})
            print(f"  {coll} {kind:<14} {frame[:44]:<46} window {sdim} px at ({y},{x}): "
                  f"agree {panels[-1]['agree_pct']:5.2f}%  over "
                  f"{panels[-1]['over_pct']:5.2f}%  under "
                  f"{panels[-1]['under_pct']:5.2f}%  unreviewed "
                  f"{panels[-1]['marked_unreviewed_pct']:5.2f}%", flush=True)

    W = J.PAGEW
    Mg = 0.03
    LAB = 0.26
    GAP = 0.07
    PAN = (W - 2 * Mg - LAB - GAP) / 2
    HDR = 0.24
    CAP = 0.0      # no per-panel numbers: they are in the caption, read from this file
    LEG = 0.30
    Htot = Mg + HDR + 2 * (PAN + CAP) + GAP + LEG + Mg

    fig = plt.figure(figsize=(W, Htot))

    def ax_at(xin, yin, win, hin):
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    for c, head in enumerate(("Over-counted", "Under-counted")):
        hx = ax_at(Mg + LAB + c * (PAN + GAP), Mg, PAN, HDR)
        hx.set_axis_off()
        hx.text(0.5, 0.45, head, fontsize=J.BODY, fontweight="bold", ha="center",
                va="center", color=J.INK, transform=hx.transAxes)

    letters = iter("abcd")
    for r, coll in enumerate(("SEM", "TXM")):
        yrow = Mg + HDR + r * (PAN + CAP + GAP)
        lx = ax_at(Mg, yrow, LAB, PAN)
        lx.set_axis_off()
        lx.text(0.55, 0.5, coll, fontsize=J.BODY, fontweight="bold", rotation=90,
                ha="center", va="center", color=J.INK, transform=lx.transAxes)
        for c, kind in enumerate(("over-counted", "under-counted")):
            p = next(q for q in panels if q["coll"] == coll and q["kind"] == kind)
            ax = ax_at(Mg + LAB + c * (PAN + GAP), yrow, PAN, PAN)
            ax.imshow(p["rgb"], interpolation="nearest")
            J.micrograph(ax)
            ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes, fill=False,
                                   edgecolor=J.INK, linewidth=0.7, zorder=30))
            J.panel_label(ax, next(letters), inside=True)
            scalebar(ax, p["nm"], p["side"], fontsize=J.TICK)
    lg = ax_at(Mg, Htot - Mg - LEG, W - 2 * Mg, LEG)
    lg.set_axis_off()
    items = ((AGREE, "marked, operator agrees"), (OVER, "marked, operator says not crack"),
             (UNDER, "operator's crack, not marked"))
    xx = 0.015
    for colour, text in items:
        lg.add_patch(Rectangle((xx, 0.52), 0.016, 0.26, transform=lg.transAxes,
                               facecolor=colour, edgecolor="none", clip_on=False))
        lg.text(xx + 0.024, 0.65, text, fontsize=J.TICK, va="center", ha="left",
                color=J.G_DARK, transform=lg.transAxes)
        xx += 0.024 + 0.0105 * len(text) + 0.022

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "the worst over-counted and worst under-counted window of a typical frame, "
                "in each modality",
        "frames": meta,
        "panel_framing": "each panel is the WORST case of its own kind in its collection, "
                         "not a typical one; share_of_collection says how much of that "
                         "collection's total error of that kind the chosen frame holds",
        "panels": [{k: v for k, v in p.items() if k != "rgb"} for p in panels],
        "selection_rule": "frame: the one holding the most pixels of that panel's error "
                          "kind, ranked from the per-frame precision and recall in "
                          "docs/figures/overlap_means_sem_txm.json. Window: the position "
                          "within it holding the most pixels of that kind, found exactly "
                          "by a box sum over the summed-area table, capped so the error "
                          f"kind is at most {100 * MAX_ERROR_SHARE:.0f}% of the window. Only frames whose "
                          "annotation is a trace rather than a filled region are eligible",
        "unreviewed": "marked pixels nobody adjudicated are left grey and counted "
                      "separately; they are neither an over-count nor an agreement",
        "mad_k": OV.MADK,
        "scale_provenance": {"sem": BM.SEM_SCALE_SOURCE, "txm": BM.TXM_SCALE_SOURCE},
    }, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)
    for coll, m in meta.items():
        for kind, r in m.items():
            print(f"  {coll} {kind:<14} {r['frame'][:44]:<46} holds "
                  f"{r['px_of_this_kind']:>10,} px, "
                  f"{100 * r['share_of_collection']:.1f}% of the eligible frames' "
                  f"{r['collection_px_of_this_kind']:,}")


if __name__ == "__main__":
    main()
