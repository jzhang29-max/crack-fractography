#!/usr/bin/env python3
"""Figure 6: how every constant in Table 1 was determined -- and which ones were not.

WHY. A reviewer asked for "a figure on how you determined all of the parameters to
include in the algorithm". The honest answer is that the seven rows of Table 1 do not
share one provenance. ONE was selected by a sweep on labelled data. TWO were decided by a
measurement that spends no free parameter at all, so their fitted and held-out scores are
the same number by construction. The rest were inherited from the archived pipeline with
no recorded provenance, and are swept here -- several of them for the first time. Drawing
seven selection curves would be fiction, and a reviewer who spots one fabricated optimum
stops reading. So each panel is the evidence that exists for one constant, and the panels
for the untuned constants show the SENSITIVITY instead of an optimum: where the shipped
value is not the best value on the instrument, the marker simply sits off the peak.

ONE PROBLEM TABLE 1 HIDES. Its row "morphological opening size 13 px" is two constants,
not one: unified_pipeline calls clean_mask(dark, min_area_px=13), and inside clean_mask
the 13 is remove_small_objects' area floor while the opening is a disk of radius 1. They
are drawn in two separate panels here, (e) and (f), because they do different things.

NO TWIN AXES. (a) and (c) each carry two measurands against one x, and each is drawn as
a STACKED PAIR of sub-panels sharing the x axis under a single panel letter, not as one
axes with two y scales. A dual-scale chart makes the reader guess which scale a series
belongs to, and both of the specific failures it caused here were real: in (c) a third
series on the left-hand scale had to be drawn in a third colour, which left no way to
tell; and in (a) a reference rule at an area ratio of 1 landed at 0.155 on the F1 scale,
where it reads as an F1 reference. Only the lower sub-panel of each pair carries x tick
labels and the x label; the vertical rules marking the constants run through both.

WHAT EACH PANEL IS, AND ON WHICH UNIT SET. The unit sets differ and may never be compared
across panels -- that is how this project has produced false rankings before -- so each
panel carries its own n in its axis label and the sidecar names the set.

  (a) MAD multiplier k. SELECTED. 31 public Inconel 718 whole fields, from
      docs/figures/madk_above_five.json, which is where the paper's k = 6.0 was chosen.
      Both the accuracy axis (F1) and the axis a user of the tool actually feels (the
      ratio of marked area to annotated area) are drawn, because the two do not peak in
      the same place and the paper reports an area fraction. The app's own default, 5.0,
      is marked beside it: analysis/detector_overrides.py defines SHIPPED_MAD_K = 5.0 and
      PAPER_MAD_K = 6.0, and they are not the same number.

  (b) The learned region classifier. DECIDED BY MEASUREMENT, with zero free parameters:
      deleting it raises all four pooled tile metrics, so fitted and held-out agree by
      construction. What the deletion recovers per specimen is a separate plate
      (mk_recover.py) and is not repeated here; this panel is only the decision.

  (c) The absolute intensity gate. INHERITED. Swept here in both directions it can be
      swept: pooled IoU over the 26 hand-labelled 512 px tiles, and recall on
      hand-painted crack over all 48 full frames that carry a correction mask. t = 0 is
      the gate switched off. The two tile curves are the whole corpus and the corpus
      without the one crop holding an off-specimen void, and they disagree about the sign.

  (d) The scale ladder. STRUCTURAL, NOT TUNED. Which term of the union supplies the
      hand-painted crack the darkness stage proposes, over the same 48 frames: a pixel is
      credited to a term only when that term and no other reaches it, so the bars are a
      true leave-one-out marginal. Pooled bars with the per-frame median overlaid,
      because two frames hold almost half of this corpus's painted crack and a pooled bar
      alone would be them.

  (e) The two size floors and (f) the opening radius with the connectivity. INHERITED.
      Pooled IoU over the 26 tiles as each constant moves over a wide range with
      everything else at its shipped value. All four are flat near their shipped setting
      and not one of them sits at the maximum.

EVERYTHING IS COMPUTED BY CALLING THE SHIPPED CODE. The darkness cut is
analysis/detector_overrides.install()'s own segment_dark_regions; the per-rung
decomposition is analysis/research/improve/fullframe_recall_decomposition.rung_maps, not
a second copy of the criterion -- an earlier attempt in this project to re-express that
union as a single scale disagreed with the installed detector on 11.7 M of 25.2 M pixels;
the cleaning chain is detect_cracks.clean_mask and skimage.measure.label exactly as
both_modalities.stages runs them. Four controls run before anything is drawn and every
one of them ABORTS rather than warns:

  * the rung union OR the absolute term must BE the installed detector's own output,
    pixel for pixel, on the first frame of the corpus pass (rung_maps' documented
    identity, checked by fullframe_recall_decomposition._control_union);
  * (k_max > k) OR the absolute term must reproduce that same mask, which is what makes
    the k and t sweeps readable off one pass instead of one pass per setting;
  * the tile chain used for the sweeps in (e) and (f) must reproduce
    both_modalities.stages' final mask on every one of the 26 tiles at the shipped
    settings;
  * tilebench's own three controls -- a perfect predictor scores 1.0, an empty one 0.0,
    and mark-everything scores precision == prevalence.

COST, AND THE TWO CACHES. The 48-frame pass is about 20 s per frame and is written to
docs/figures/parameters_frames.json; the tile sweeps take about 65 s and go to
docs/figures/parameters_tiles.json. With both present the plate redraws in a second;
PARAM_RECOMPUTE=1, or deleting the file, forces the pass again.

THE CACHE IS CHECKED, NOT TRUSTED, because the controls above run inside the pass and
cannot run again off a file. A cached record has to clear three things before it is
allowed to answer, and failing any of them ABORTS rather than redraws: its settings hash
has to match, the settings it states in plain text have to equal the constants this
module has just read out of detector_overrides, and every control it recorded has to say
PASS. A plate quoting an evidence file written under different constants is a failure
this project has had before, and a hash alone does not catch a file edited by hand.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_parameters.py
"""
import hashlib
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths                                       # noqa: E402

sys.path.insert(0, _paths.ANALYSIS)
sys.path.insert(0, os.path.join(_paths.ANALYSIS, "research"))
sys.path.insert(0, os.path.join(_paths.ANALYSIS, "research", "improve"))
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "code"))
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "interior_active_learning", "code"))
sys.dont_write_bytecode = True

import numpy as np                                  # noqa: E402
import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from skimage import measure as skm                  # noqa: E402

import detect_cracks as D                           # noqa: E402  -- the shipped stages
import detector_overrides as DO                     # noqa: E402  -- the shipped constants
import both_modalities as BM                        # noqa: E402  -- the one staging copy
import journal_style as J                           # noqa: E402

J.use()
OUT = _paths.FIG_DIR
NAME = "F6 - how the parameters were determined"
DOCS = os.path.join(_paths.REPO, "docs", "figures")

#: The setting the paper evaluates at. Read from both_modalities so this plate and the
#: micrograph plates cannot drift apart, and cross-checked against detector_overrides.
K = float(BM.MAD_K)
GATE = int(DO.ABSOLUTE_DARK_THRESH)
LADDER = tuple(DO.SCALE_LADDER)
CLEAN_MIN = int(BM.CLEAN_MIN_PX)
CAND_MIN = int(BM.MIN_AREA_PX)

#: The grids each constant is swept over. Chosen to bracket the shipped value by at least
#: an order of magnitude in both directions where that is meaningful, so a flat curve is
#: a statement about the constant and not about a grid drawn too narrow to move.
GATE_GRID = (0, 2, 4, 6, 8, 10, 12, 14, 16, 20, 25, 30, 40)
GATE_GRID_FRAME = (0, 10, 20)          # the full chain, which is the expensive one
GATE_GRID_DARK = tuple(range(0, 42, 2))  # the darkness stage alone, which is free
CLEANMIN_GRID = (0, 1, 3, 6, 13, 25, 50, 100, 200, 400, 800)
CANDMIN_GRID = (1, 5, 13, 40, 100, 200, 400, 800, 1600, 3200)
OPEN_GRID = (0, 1, 2, 3, 4, 5, 6)


def _key(**kw):
    return hashlib.sha1(json.dumps(kw, sort_keys=True).encode()).hexdigest()[:12]


def _cached(path, key, build, expect):
    """Reuse a committed evidence file only when it was written at these settings.

    THE CACHE IS CHECKED, NOT TRUSTED. The reconstruction controls run inside build() and
    cannot run again off a cached file, so a cached record has to prove three things
    before it is allowed to answer: the settings hash matches, the settings it states in
    plain text match the constants this module reads out of detector_overrides now, and
    every control it recorded says PASS. Any of those failing aborts rather than redraws
    -- a figure quoting a cache written under other constants is the failure mode this
    project has hit before.
    """
    rec = None
    if os.path.exists(path) and not os.environ.get("PARAM_RECOMPUTE"):
        rec = json.load(open(path))
        if rec.get("key") == key:
            print(f"  reusing {os.path.relpath(path, _paths.REPO)} (key {key})")
        else:
            print(f"  {os.path.relpath(path, _paths.REPO)} was written at key "
                  f"{rec.get('key')}, not {key} -- recomputing")
            rec = None
    if rec is None:
        t0 = time.time()
        rec = build()
        rec["key"] = key
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(rec, open(path, "w"), indent=1)
        print(f"  wrote {os.path.relpath(path, _paths.REPO)} in {time.time() - t0:.0f}s")
    bad = {k: (rec.get(k), v) for k, v in expect.items() if rec.get(k) != v}
    if bad:
        raise SystemExit(f"{path} states {bad} -- it was not written at the constants "
                         f"this module is drawing")
    notpass = {k: v for k, v in rec.get("controls", {}).items()
               if not str(v).startswith("PASS")}
    if not rec.get("controls") or notpass:
        raise SystemExit(f"{path} carries no passing reconstruction controls ({notpass}); "
                         f"delete it or set PARAM_RECOMPUTE=1 and run it again")
    return rec


# ======================================================================= the 26 tiles
def tile_chain(proposed, open_radius=1, close_radius=3, clean_min=CLEAN_MIN,
               cand_min=CAND_MIN, conn=2):
    """The cleaning chain exactly as both_modalities.stages runs it, with the four
    constants exposed. Checked against both_modalities.stages itself on every tile at the
    shipped settings before any sweep is read."""
    cleaned = D.clean_mask(proposed, open_radius=open_radius, close_radius=close_radius,
                           min_area_px=clean_min)
    lab = skm.label(cleaned, connectivity=conn)
    if not lab.max():
        return np.zeros(cleaned.shape, bool)
    sz = np.bincount(lab.ravel())
    keep = np.where(sz >= cand_min)[0]
    return np.isin(lab, keep[keep > 0])


def tile_evidence():
    """Sweep the gate, the two size floors, the opening and the connectivity on the tiles.

    tilebench is THE scorer in this project; its three absolute paths are repointed by
    _paths.tilebench() so the figure runs against the committed tile manifest. Pooled over
    every pixel at zero tolerance, which is the most pessimistic of the five aggregations
    this project uses and is stated in the sidecar.
    """
    TB = _paths.tilebench()
    tiles = TB.load()
    ok = TB.controls()
    if not ok:
        raise SystemExit("tilebench's own controls did not pass; nothing here is readable")
    flood = TB.FLOODED
    if not any(t["frame"] == flood for t in tiles):
        raise SystemExit(f"the off-specimen void tile {flood} is not in the corpus; the "
                         f"26-vs-25 reading in panel (b) would be meaningless")

    class _U:
        pass

    u = _U()
    DO.install(u)

    flats, props, finals = [], [], []
    for t in tiles:
        flat, proposed, _cleaned, final = BM.stages(t["img8"])
        flats.append(flat)
        props.append(proposed)
        finals.append(final)

    # RECONSTRUCTION CHECK 3. The chain this module sweeps must BE the shipped chain.
    bad = [t["frame"] for t, p, f in zip(tiles, props, finals)
           if not np.array_equal(tile_chain(p), f)]
    if bad:
        raise SystemExit(f"tile_chain does not reproduce both_modalities.stages on "
                         f"{len(bad)} tiles ({bad[:3]}); every sweep below would be a "
                         f"different pipeline from the one the paper evaluates")
    print(f"  CONTROL tile_chain == both_modalities.stages on all {len(tiles)} tiles: PASS")

    def pooled(masks, drop=()):
        tp = fp = fn = 0
        for m, t in zip(masks, tiles):
            if t["frame"] in drop:
                continue
            c = TB.counts(m, t["gt"], tol=0)
            tp += c["tp"]
            fp += c["fp"]
            fn += c["fn"]
        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        return dict(precision=p, recall=r, iou=tp / max(tp + fp + fn, 1),
                    f1=2 * p * r / max(p + r, 1e-12), tp=tp, fp=fp, fn=fn)

    rec = dict(
        what="sensitivity of the pooled tile score to each constant of Table 1",
        n_tiles=len(tiles), n_specimens=len({t["specimen"] for t in tiles}),
        excluded=list(TB.DEFAULT_EXCLUDE), flood_tile=flood,
        tolerance_px=0, aggregation="pooled over every pixel of the named tile set",
        mad_k=K, scorer="analysis/research/tilebench.py via paper/figures/_paths.tilebench()",
        shipped=pooled(finals), shipped_25=pooled(finals, drop=(flood,)),
        controls=dict(
            tilebench="PASS: oracle 1.0, empty 0.0, mark-everything precision == prevalence",
            chain="PASS: tile_chain reproduces both_modalities.stages on every tile"),
    )

    g26, g25 = {}, {}
    for t_dn in GATE_GRID:
        masks = [tile_chain(u.segment_dark_regions(f, img8=t["img8"], mad_k=K,
                                                   absolute_dark_thresh=t_dn))
                 for f, t in zip(flats, tiles)]
        g26[str(t_dn)] = pooled(masks)
        g25[str(t_dn)] = pooled(masks, drop=(flood,))
    rec["gate_26"], rec["gate_25"] = g26, g25

    rec["clean_min"] = {str(v): pooled([tile_chain(p, clean_min=v) for p in props])
                        for v in CLEANMIN_GRID}
    rec["cand_min"] = {str(v): pooled([tile_chain(p, cand_min=v) for p in props])
                       for v in CANDMIN_GRID}
    rec["opening"] = {
        str(c): {str(v): pooled([tile_chain(p, open_radius=v, conn=c) for p in props])
                 for v in OPEN_GRID}
        for c in (2, 1)}
    return rec


# ================================================================ the 48 painted frames
def frame_evidence():
    """One pass over every full frame that carries a hand-painted correction mask.

    The loader, the field-of-view crop, the gentler contrast stretch three frames need and
    the four paint states all come from fullframe_lever4_safety; the per-rung maps and the
    cleaning chain come from fullframe_recall_decomposition. Nothing here re-expresses the
    detector's criterion -- rung_maps' own identity, dark(k) = (k_max > k) | (img8 < t),
    is what makes a sweep readable off one pass, and it is checked against the installed
    segment_dark_regions on the first frame.
    """
    import fullframe_recall_decomposition as FRD
    import fullframe_lever4_safety as FF

    FRD.MAD_K = K                       # the paper's setting, not the app's default
    FRD.MIN_AREA_CLEAN = CLEAN_MIN
    FRD.MIN_AREA_CAND = CAND_MIN
    if tuple(FRD.LADDER) != LADDER or int(FRD.ABS_DARK) != GATE:
        raise SystemExit(f"fullframe_recall_decomposition reports ladder {FRD.LADDER} / "
                         f"gate {FRD.ABS_DARK}, detector_overrides says {LADDER} / {GATE}")

    names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(FRD.PAINT)
                   if f.endswith("_correction_mask.png"))
    names = [n for n in names
             if os.path.exists(os.path.join(FRD.SEM, "original", n + ".tif"))]
    print(f"  {len(names)} full frames carry both a micrograph and a correction mask")

    out, t0, first = [], time.time(), True
    for i, n in enumerate(names, 1):
        got = FF.load_frame(n)
        if got is None:
            out.append(dict(frame=n, error="shape_mismatch"))
            continue
        img8, _raw, corr = got
        crack = corr == 1
        flat40 = D.flatten_background(img8, sigma=40)
        dark_rel, kmax, per = FRD.rung_maps(img8, flat40)

        if first:
            # RECONSTRUCTION CHECKS 1 and 2, both of which assert rather than warn.
            FRD._control_union(img8, flat40, dark_rel, n)
            FRD._control_kmax(img8, kmax, dark_rel | (img8 < GATE))
            first = False
        del kmax

        r = dict(frame=n, px=int(img8.size), crack=int(crack.sum()),
                 notc=int((corr == 2).sum()), erase=int((corr == 3).sum()),
                 dark_rel=int(dark_rel.sum()), absdark=int((img8 < GATE).sum()))

        # the darkness stage alone, which costs nothing and gives a smooth gate curve
        r["dark_crack"] = {str(t_dn): int((crack & (dark_rel | (img8 < t_dn))).sum())
                           for t_dn in GATE_GRID_DARK}
        # the WHOLE chain, which is what the detector emits, at three settings
        r["chain"] = {}
        for t_dn in GATE_GRID_FRAME:
            dark = dark_rel if t_dn == 0 else (dark_rel | (img8 < t_dn))
            st = FRD.chain(dark, flat40)
            r["chain"][str(t_dn)] = FRD.decompose(crack, dark, st)
            r["chain"][str(t_dn)]["cand_px"] = int(st["cand"].sum())
            del st, dark

        # leave-one-out marginal of each term of the union. A pixel is credited to a rung
        # only when that rung is the ONLY term that reaches it, so removing the rung would
        # really lose it; `cnt == 1` is the cheap form of "no other rung marks this".
        cnt = np.zeros(img8.shape, np.uint8)
        for s in LADDER:
            cnt += per[s]["cut"].astype(np.uint8)
        absm = img8 < GATE
        r["rung_area"] = {str(s): int(per[s]["cut"].sum()) for s in LADDER}
        r["rung_only_area"] = {}
        r["rung_only_crack"] = {}
        for s in LADDER:
            only = per[s]["cut"] & (cnt == 1) & ~absm
            r["rung_only_area"][str(s)] = int(only.sum())
            r["rung_only_crack"][str(s)] = int((only & crack).sum())
            del only
        gate_only = absm & ~(cnt > 0)
        r["gate_only_area"] = int(gate_only.sum())
        r["gate_only_crack"] = int((gate_only & crack).sum())
        r["union_area"] = int(((cnt > 0) | absm).sum())
        r["union_crack"] = int((((cnt > 0) | absm) & crack).sum())
        del cnt, absm, gate_only, per, dark_rel

        out.append(r)
        print(f"  [{i}/{len(names)}] {n:<34} painted {r['crack']:>10,}  "
              f"kept {r['chain'][str(GATE)]['kept']:>10,}  gate-only crack "
              f"{r['gate_only_crack']:>10,}  {time.time() - t0:5.0f}s", flush=True)

    return dict(what="per-frame evidence for the absolute gate, the scale ladder and the "
                     "two size floors, on every frame carrying a hand-painted correction",
                mad_k=K, gate=GATE, ladder=list(LADDER),
                clean_min=CLEAN_MIN, cand_min=CAND_MIN,
                paint_states="1 = crack, 2 = not crack, 3 = erase (also a not-crack "
                             "verdict), 0 = unreviewed and counted as neither",
                source="fullframe_lever4_safety.load_frame + "
                       "fullframe_recall_decomposition.rung_maps / chain / decompose",
                controls=dict(
                    union="PASS: rung union OR (img8 < gate) == the installed "
                          "segment_dark_regions, pixel for pixel, on the first frame",
                    kmax="PASS: (k_max > k) OR (img8 < gate) reproduces that same mask"),
                n_frames=len([r for r in out if "error" not in r]), frames=out)


# ============================================================================= drawing
#: ONE convention for the whole plate. A solid neutral rule and a filled square on the
#: curve mark THE VALUE REPORTED IN TABLE 1, in every panel that has one on an axis; in
#: (a) it lands on the maximum because that is where it came from, and nowhere else does.
#: The dotted rule appears once, in (a), and is the value the application itself runs.
SHIPPED_RULE = dict(color=J.G_MID, lw=0.8, zorder=1)
APP_RULE = dict(color=J.G_MID, lw=0.7, linestyle=(0, (1, 2)), zorder=1)


def _no_collisions(fig):
    """Every visible string, measured where it is actually drawn, must clear every other.

    A stacked pair halves the height a rotated y label has to live in, and the first
    draft of (a) put "F1, 31 whole fields" straight through "marked / annotated area" --
    at full size, in a plate whose type check passed. Looking at a 2000 px preview is how
    that survives; measuring the renderer's own extents is how it does not. The threshold
    is 1 pt of real overlap in BOTH directions, so touching bounding boxes are allowed
    and crossing glyphs are not.
    """
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    items = []
    for t in fig.findobj(plt.Text):
        if not t.get_text().strip() or not t.get_visible():
            continue
        try:
            items.append((t.get_text().strip()[:40], t.get_window_extent(renderer=r)))
        except Exception:                       # an artist with no renderable extent
            continue
    tol = fig.dpi / 72.0
    bad = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i][1], items[j][1]
            if (min(a.x1, b.x1) - max(a.x0, b.x0) > tol
                    and min(a.y1, b.y1) - max(a.y0, b.y0) > tol):
                bad.append(f"{items[i][0]!r} x {items[j][0]!r}")
    if bad:
        raise SystemExit(f"{len(bad)} overlapping label(s) in the plate: "
                         + "; ".join(bad[:6]))
    return len(items)


def _box(ax):
    ax.tick_params(labelsize=J.TICK, pad=1.6)
    for s in ax.spines.values():
        s.set_linewidth(0.6)


def _pooled(frames, num, den="crack"):
    """Pooled over pixels, and the per-frame median of the same ratio. Two frames hold
    almost half of this corpus's painted crack, so a pooled figure alone can be them.

    `den` is a key of the per-frame record, or a callable taking the record."""
    return _spread(frames, num, den)[:2]


def _spread(frames, num, den="crack"):
    """(pooled, median, p25, p75, frames with a non-zero value, frames with a denominator).

    The pooled value and the per-frame median are different statistics of a RATIO, and
    where the per-frame distribution is zero-inflated they can differ by two orders of
    magnitude without either being wrong. The quartiles and the non-zero count are what
    say which of those is happening, so they travel with the median rather than being
    left for a reader to assume.
    """
    dfn = den if callable(den) else (lambda r, k=den: r[k])
    ns = [num(r) for r in frames]
    ds = [dfn(r) for r in frames]
    per = sorted(n / d for n, d in zip(ns, ds) if d > 0)
    pooled = sum(ns) / max(sum(ds), 1)
    if not per:
        nan = float("nan")
        return pooled, nan, nan, nan, 0, 0

    def q(f):
        if len(per) == 1:
            return per[0]
        i = f * (len(per) - 1)
        lo = int(np.floor(i))
        hi = min(lo + 1, len(per) - 1)
        return per[lo] + (per[hi] - per[lo]) * (i - lo)

    return pooled, q(0.5), q(0.25), q(0.75), sum(1 for x in per if x > 0), len(per)


def draw(tiles, frames, madk, dead):
    wf = madk["sets"]["whole_fields"]
    grid = [float(g) for g in madk["grid"]]
    fr = [r for r in frames["frames"] if "error" not in r]

    # ---- geometry ------------------------------------------------------------------
    # NO TWIN AXES ANYWHERE. Two measurands against one x belong in two sub-panels that
    # share the x axis, not on two y scales: a dual-scale chart makes the reader guess
    # which scale a series is read against, and in the first draft of (c) a third series
    # drawn in a third colour made that guess impossible. A reference rule at a ratio of
    # 1 also lands somewhere arbitrary on the other measurand's scale and reads as a
    # reference for IT. (a) and (c) are therefore stacked pairs under one panel letter;
    # only the lower sub-panel carries x tick labels and the x label, and the vertical
    # rules marking the constants run through both.
    W = J.PAGEW
    ML, GX, MR = 0.56, 0.66, 0.12
    MT, GY, MB = 0.20, 0.52, 0.42
    CW = (W - ML - GX - MR) / 2.0
    SUBGAP = 0.11
    H_SPLIT, H_LAST = 2.18, 1.46
    SUBH = (H_SPLIT - SUBGAP) / 2.0
    ROWS = (H_SPLIT, H_SPLIT, H_LAST)
    Htot = MT + sum(ROWS) + GY * (len(ROWS) - 1) + MB
    fig = plt.figure(figsize=(W, Htot))

    def cell(col, row, h=None, dy=0.0):
        x = ML + col * (CW + GX)
        y = MT + sum(ROWS[:row]) + GY * row + dy
        hh = ROWS[row] if h is None else h
        return fig.add_axes([x / W, 1.0 - (y + hh) / Htot, CW / W, hh / Htot])

    def stacked(col, row):
        """Upper and lower sub-panels of one lettered panel, sharing the x axis."""
        return cell(col, row, h=SUBH), cell(col, row, h=SUBH, dy=SUBH + SUBGAP)

    # ---- (a) the MAD multiplier: the one constant selected by a sweep ---------------
    axu, axl = stacked(0, 0)
    for ax in (axu, axl):
        ax.set_xscale("log")
        ax.set_xticks([1, 2, 5, 10, 20, 40])
        ax.set_xlim(0.9, 44)
        ax.axvline(K, **SHIPPED_RULE)
        ax.axvline(float(DO.SHIPPED_MAD_K), **APP_RULE)
        _box(ax)
    axu.plot(grid, [wf["per_k"][str(g)]["f1"] for g in grid], "-o", color=J.ACCENT,
             ms=2.8, lw=1.1, mew=0, zorder=5)
    axu.plot([K], [wf["per_k"][str(K)]["f1"]], "s", color=J.ACCENT, ms=4.4, mew=0,
             zorder=6)
    axu.set_ylim(0, 0.42)
    axu.set_yticks([0, 0.1, 0.2, 0.3, 0.4])
    axu.set_ylabel("F1", fontsize=J.LABEL, labelpad=2.0)
    axu.tick_params(labelbottom=False)
    J.panel_label(axu, "a")

    axl.plot(grid, [wf["per_k"][str(g)]["area_ratio"] for g in grid], "-o",
             color=J.ACCENT2, ms=2.8, lw=1.1, mew=0, zorder=5)
    axl.plot([K], [wf["per_k"][str(K)]["area_ratio"]], "s", color=J.ACCENT2, ms=4.4,
             mew=0, zorder=6)
    axl.axhline(1.0, color=J.G_DARK, lw=0.6, dashes=(2.5, 2.0), zorder=2)
    axl.set_yscale("log")
    axl.set_ylim(0.08, 70)
    axl.set_yticks([0.1, 1, 10])
    axl.set_yticklabels(["0.1", "1", "10"])
    axl.set_xticklabels(["1", "2", "5", "10", "20", "40"])
    axl.set_xlabel("MAD multiplier $k$, 31 whole fields", fontsize=J.LABEL,
                   labelpad=1.5)
    axl.set_ylabel("marked / annotated area", fontsize=J.LABEL, labelpad=2.0)

    # ---- (b) the region classifier: the other constant decided by measurement -------
    ax = cell(1, 0)
    mets = ["precision", "recall", "iou", "f1"]
    xs = np.arange(len(mets))
    ax.bar(xs - 0.19, [dead["pooled_26"]["v147"][m] for m in mets], 0.36,
           color=J.G_LIGHT, edgecolor=J.INK, linewidth=0.5, label="classifier on",
           zorder=3)
    ax.bar(xs + 0.19, [dead["pooled_26"]["ablation"][m] for m in mets], 0.36,
           color=J.ACCENT, edgecolor=J.INK, linewidth=0.5, label="classifier off",
           zorder=3)
    ax.set_xticks(xs)
    ax.set_xticklabels(["P", "R", "IoU", "F1"])
    ax.set_xlim(-0.6, len(mets) - 0.4)
    ax.set_ylim(0, 0.62)
    ax.set_yticks([0, 0.2, 0.4, 0.6])
    ax.set_xlabel("learned region classifier, 26 tiles", fontsize=J.LABEL, labelpad=1.5)
    ax.set_ylabel("score", fontsize=J.LABEL, labelpad=2.0)
    ax.tick_params(axis="x", length=0)
    ax.minorticks_off()
    _box(ax)
    ax.legend(loc="upper left", fontsize=J.TICK, handlelength=1.1, handletextpad=0.45,
              borderpad=0.0, labelspacing=0.22, borderaxespad=0.3)
    J.panel_label(ax, "b")

    # ---- (c) the absolute intensity gate: inherited, swept only afterwards ----------
    axu, axl = stacked(0, 1)
    gg = [int(g) for g in GATE_GRID]
    for ax in (axu, axl):
        ax.set_xlim(-1.5, 41.5)
        ax.set_xticks([0, 10, 20, 30, 40])
        ax.axvline(GATE, **SHIPPED_RULE)
        _box(ax)
    # BOTH tile sets, in ONE hue, because they are the same measurand on two unit sets.
    # They disagree about the sign: one 512 px crop holds an off-specimen void that is
    # pitch black, so the gate claims it at any t >= 2 and it owns most of the corpus's
    # false positives; dropping that one tile reverses the verdict.
    axu.plot(gg, [tiles["gate_26"][str(g)]["iou"] for g in gg], "-o", color=J.ACCENT,
             ms=2.8, lw=1.1, mew=0, zorder=5, label="26 tiles")
    axu.plot(gg, [tiles["gate_25"][str(g)]["iou"] for g in gg], "--o", color=J.ACCENT,
             ms=3.6, lw=1.0, mfc="white", mec=J.ACCENT, mew=0.8, dashes=(3.2, 1.8),
             zorder=4, label="25 tiles")
    axu.plot([GATE], [tiles["gate_26"][str(GATE)]["iou"]], "s", color=J.ACCENT, ms=4.4,
             mew=0, zorder=6)
    axu.set_ylim(0, 0.62)
    axu.set_yticks([0, 0.2, 0.4, 0.6])
    axu.set_ylabel("IoU, tiles", fontsize=J.LABEL, labelpad=2.0)
    axu.tick_params(labelbottom=False)
    axu.legend(loc="lower left", fontsize=J.TICK, handlelength=1.8, handletextpad=0.45,
               borderpad=0.0, labelspacing=0.22, borderaxespad=0.3)
    J.panel_label(axu, "c")

    dk = [int(g) for g in GATE_GRID_DARK]
    rec_by_t = {g: _pooled(fr, lambda r, g=g: r["dark_crack"][str(g)])[0] for g in dk}
    axl.plot(dk, [rec_by_t[g] for g in dk], "-", color=J.ACCENT2, lw=1.2, zorder=5)
    axl.plot([GATE], [rec_by_t[GATE]], "s", color=J.ACCENT2, ms=4.4, mew=0, zorder=6)
    axl.set_ylim(0, 0.46)
    axl.set_yticks([0, 0.1, 0.2, 0.3, 0.4])
    axl.set_xlabel("absolute intensity gate, DN of 255", fontsize=J.LABEL, labelpad=1.5)
    axl.set_ylabel("painted-crack recall,\n48 frames", fontsize=J.LABEL, labelpad=2.0)

    # ---- (d) the scale ladder: what each radius adds that no other radius does ------
    # DENOMINATOR: the painted crack the SEVEN-RUNG UNION reaches on its own, which is
    # dark_crack at threshold 0, i.e. with the absolute gate switched off. The gate is
    # panel (c)'s subject and including it here would put a 57% bar beside seven bars of
    # 1% and make the ladder -- this panel's actual subject -- unreadable.
    #
    # THE WHISKER IS NOT DECORATION. The pooled bar and the per-frame median differ by
    # two orders of magnitude at the coarse radii, and without the quartiles that reads
    # as a contradiction. It is not one: the per-frame distribution is zero-inflated --
    # only 22 of the 40 frames whose paint the ladder reaches have ANY pixel that
    # sigma = 320 alone reaches -- so the median sits near zero while the frames that do
    # have such pixels carry a lot of them. The p25-p75 bar is what shows that.
    ax = cell(1, 1)
    den = lambda r: r["dark_crack"]["0"]                               # noqa: E731
    spread = [_spread(fr, lambda r, s_=s_: r["rung_only_crack"][str(s_)], den=den)
              for s_ in LADDER]
    pooled_v = [100 * x[0] for x in spread]
    med_v = [100 * x[1] for x in spread]
    lo_v = [100 * x[2] for x in spread]
    hi_v = [100 * x[3] for x in spread]
    xs = np.arange(len(LADDER))
    ax.bar(xs, pooled_v, 0.66, color=J.ACCENT, edgecolor=J.INK, linewidth=0.5, zorder=3,
           label="pooled")
    ax.errorbar(xs, med_v,
                yerr=[np.subtract(med_v, lo_v), np.subtract(hi_v, med_v)],
                fmt="D", color=J.ACCENT2, ms=3.2, mew=0, elinewidth=0.9, capsize=1.8,
                capthick=0.9, linestyle="none", zorder=6,
                label="per frame: median, p25–p75")
    ax.set_xticks(xs)
    ax.set_xticklabels([str(s_) for s_ in LADDER])
    ax.set_xlim(-0.7, len(LADDER) - 0.3)
    ax.set_ylim(0, 8.0)
    ax.set_yticks([0, 2, 4, 6, 8])
    ax.set_xlabel("flattening radius $\\sigma$, px", fontsize=J.LABEL, labelpad=1.5)
    ax.set_ylabel("% of ladder-proposed painted\ncrack this radius alone reaches",
                  fontsize=J.LABEL, labelpad=2.0)
    ax.tick_params(axis="x", length=0)
    ax.minorticks_off()
    _box(ax)
    ax.legend(loc="upper center", fontsize=J.TICK, handlelength=1.1, handletextpad=0.45,
              borderpad=0.0, labelspacing=0.25, borderaxespad=0.3)
    J.panel_label(ax, "d")
    ladder_bars = dict(
        terms=[str(s_) for s_ in LADDER], pooled=pooled_v, median=med_v,
        p25=lo_v, p75=hi_v,
        frames_with_a_nonzero_share=[x[4] for x in spread],
        frames_with_a_denominator=[x[5] for x in spread],
        shared_pct=100.0 - sum(pooled_v))

    # ---- (e) the two size floors ---------------------------------------------------
    ax = cell(0, 2)
    for key, gridv, ship, col, dash, lab in (
            ("clean_min", CLEANMIN_GRID, CLEAN_MIN, J.ACCENT, None, "small-object floor"),
            ("cand_min", CANDMIN_GRID, CAND_MIN, J.ACCENT2, (3.5, 2.0),
             "candidate-region floor")):
        xs = [max(float(v), 0.5) for v in gridv]
        ys = [tiles[key][str(v)]["iou"] for v in gridv]
        kw = dict(dashes=dash) if dash else {}
        ax.plot(xs, ys, "-o" if dash is None else "--o", color=col, ms=2.4, lw=1.0,
                mew=0, label=lab, zorder=5, **kw)
        ax.plot([ship], [tiles[key][str(ship)]["iou"]], "s", color=col, ms=4.2, mew=0,
                zorder=6)
        ax.axvline(ship, **SHIPPED_RULE)
    ax.set_xscale("log")
    ax.set_xticks([1, 10, 100, 1000])
    ax.set_xticklabels(["1", "10", "100", "1000"])
    ax.set_xlim(0.4, 4500)
    ax.set_ylim(0, 0.42)
    ax.set_yticks([0, 0.1, 0.2, 0.3, 0.4])
    ax.set_xlabel("minimum region area, px", fontsize=J.LABEL, labelpad=1.5)
    ax.set_ylabel("IoU, 26 tiles", fontsize=J.LABEL, labelpad=2.0)
    _box(ax)
    ax.legend(loc="lower left", fontsize=J.TICK, handlelength=1.5, handletextpad=0.45,
              borderpad=0.0, labelspacing=0.22, borderaxespad=0.3)
    J.panel_label(ax, "e")

    # ---- (f) the opening radius, and the connectivity ------------------------------
    ax = cell(1, 2)
    # The two curves coincide to within 0.0002 IoU, which IS the result for this row of
    # Table 1. The shipped 8-connected labelling is the line; the 4-connected alternative
    # is drawn as open markers on top of it, so a reader sees two series landing on the
    # same points rather than one line with a redundant legend.
    ax.plot(list(OPEN_GRID), [tiles["opening"]["2"][str(v)]["iou"] for v in OPEN_GRID],
            "-o", color=J.ACCENT, ms=2.6, lw=1.1, mew=0, label="8-connected", zorder=5)
    ax.plot(list(OPEN_GRID), [tiles["opening"]["1"][str(v)]["iou"] for v in OPEN_GRID],
            "o", color=J.ACCENT2, mfc="none", mew=0.9, ms=5.0, linestyle="none",
            label="4-connected", zorder=6)
    ax.plot([1], [tiles["opening"]["2"]["1"]["iou"]], "s", color=J.ACCENT, ms=4.2,
            mew=0, zorder=7)
    ax.axvline(1, **SHIPPED_RULE)
    ax.set_xlim(-0.4, max(OPEN_GRID) + 0.4)
    ax.set_xticks(list(OPEN_GRID))
    ax.set_ylim(0, 0.42)
    ax.set_yticks([0, 0.1, 0.2, 0.3, 0.4])
    ax.set_xlabel("opening radius, px", fontsize=J.LABEL, labelpad=1.5)
    ax.set_ylabel("IoU, 26 tiles", fontsize=J.LABEL, labelpad=2.0)
    _box(ax)
    ax.legend(loc="lower left", fontsize=J.TICK, handlelength=1.5, handletextpad=0.45,
              borderpad=0.0, labelspacing=0.22, borderaxespad=0.3)
    J.panel_label(ax, "f")

    n_text = _no_collisions(fig)
    print(f"  CONTROL {n_text} drawn strings, no overlapping pair above 1 pt: PASS")
    J.save(fig, os.path.join(OUT, NAME + ".png"))
    ladder_bars["figure_height_in"] = Htot
    ladder_bars["n_text"] = n_text
    return ladder_bars


def _concentration(fr, ladder):
    """Is a radius's pooled bar just the frames that dominate the denominator?

    Answered rather than assumed: the two frames holding most of the denominator are
    named, and for each radius the share of its own unique pixels that its own two
    largest contributors hold. If those were the same two frames the pooled bar would be
    reporting them; they are not.
    """
    den = sorted(fr, key=lambda r: r["dark_crack"]["0"], reverse=True)
    tot = sum(r["dark_crack"]["0"] for r in fr)
    out = {"two_frames_holding_most_of_the_denominator":
           [{"frame": r["frame"], "pct_of_denominator": 100.0 * r["dark_crack"]["0"]
             / max(tot, 1)} for r in den[:2]],
           "per_radius": {}}
    for s_ in ladder:
        key = str(s_)
        tops = sorted(fr, key=lambda r, k=key: r["rung_only_crack"][k], reverse=True)[:2]
        tot_s = sum(r["rung_only_crack"][key] for r in fr)
        out["per_radius"][key] = {
            "its_own_two_largest_contributors": [r["frame"] for r in tops],
            "share_of_its_unique_px_they_hold_pct":
                100.0 * sum(r["rung_only_crack"][key] for r in tops) / max(tot_s, 1),
            "same_frames_as_the_denominator":
                sorted(r["frame"] for r in tops) == sorted(r["frame"] for r in den[:2])}
    return out


def _crossing(wf, grid):
    """Where the marked/annotated area ratio passes 1, read off the grid rather than
    typed into a sentence that a later sweep could falsify."""
    gs = sorted(float(g) for g in grid)
    for a, b in zip(gs, gs[1:]):
        ra, rb = wf["per_k"][str(a)]["area_ratio"], wf["per_k"][str(b)]["area_ratio"]
        if ra >= 1.0 > rb:
            return f"between k = {a:g} ({ra:.3f}) and k = {b:g} ({rb:.3f})"
    return "nowhere on this grid"


def sidecar(tiles, frames, madk, madp, dead, ladder_bars):
    """Every number the plate prints, with the file or the function that produced it."""
    wf = madk["sets"]["whole_fields"]
    fr = [r for r in frames["frames"] if "error" not in r]
    cmp_path = os.path.join(_paths.REPO, "docs", "slides", "comparison.json")
    comp = {r["arm"]: r for r in json.load(open(cmp_path))["rows"]}

    def chain_pooled(t_dn, field):
        return _pooled(fr, lambda r, t=t_dn, f=field: r["chain"][str(t)][f])

    painted = sum(r["crack"] for r in fr)
    kept = sum(r["chain"][str(GATE)]["kept"] for r in fr)
    rec = {
        "figure": NAME + ".png",
        "column_class": "double, Elsevier 190 mm. journal_style.COLUMN_CLASS carries no "
                        "row for this plate and is not edited from here, so the class is "
                        "recorded in this sidecar instead.",
        "what": "the evidence behind each constant of Table 1, one panel per constant, "
                "with the panels for the constants that were never searched showing the "
                "sensitivity rather than an optimum",
        "settings_drawn": {
            "mad_k": K, "absolute_dark_thresh": GATE, "scale_ladder": list(LADDER),
            "clean_mask_min_area_px": CLEAN_MIN, "clean_mask_open_radius": 1,
            "clean_mask_close_radius": 3, "candidate_min_area_px": CAND_MIN,
            "connectivity": 8, "region_classifier": bool(DO.USE_REGION_CLASSIFIER),
            "source": "analysis/detector_overrides.py and paper/figures/"
                      "both_modalities.py, read at run time, never retyped"},
        "two_values_of_mad_k": {
            "shipped_in_the_app": float(DO.SHIPPED_MAD_K),
            "evaluated_in_the_paper": float(DO.PAPER_MAD_K),
            "note": "detector_overrides.py defines both and they are not the same "
                    "number; every panel other than (a) and (b) is drawn at the paper's "
                    "6.0, and (a) marks both"},
        "plate": {
            "figure_width_in": J.PAGEW, "figure_height_in": ladder_bars["figure_height_in"],
            "dpi": 600, "smallest_printed_type_pt": J.FLOOR,
            "layout": "two columns by three rows; (a) and (c) are stacked pairs of "
                      "sub-panels sharing one x axis under one panel letter, and no "
                      "panel in the plate carries a second y scale",
            "text_collision_control": "PASS: %d drawn strings measured at the renderer's "
                                      "own extents, no pair overlapping by more than "
                                      "1 pt in both directions"
                                      % ladder_bars.get("n_text", 0)},
        "reconstruction_checks": {
            "union": frames["controls"]["union"],
            "kmax": frames["controls"]["kmax"],
            "tile_chain": tiles["controls"]["chain"],
            "tilebench": tiles["controls"]["tilebench"],
            "rule": "all four abort the script on disagreement; none of them warns"},
        "panel_a_mad_multiplier": {
            "verdict": "SELECTED BY MEASUREMENT",
            "unit_set": "31 public Inconel 718 whole fields, mean per image",
            "source": "docs/figures/madk_above_five.json, sets.whole_fields.per_k",
            "f1_by_k": {str(g): wf["per_k"][str(g)]["f1"] for g in madk["grid"]},
            "area_ratio_by_k": {str(g): wf["per_k"][str(g)]["area_ratio"]
                                for g in madk["grid"]},
            "best_in_sample": wf["best_in_sample"],
            "leave_one_image_out_f1": wf["loo_full_grid_f1"],
            "f1_at_the_app_default_5": wf["shipped_f1"],
            "why_the_grid_runs_to_40": madk["why"],
            "paired_test_6_vs_5": {
                "whole_fields": madp["tests"]["whole_fields"]["F1"]["6.0"],
                "crops": madp["tests"]["crops"]["F1"]["6.0"],
                "source": "docs/figures/madk_paired_test.json",
                "read_this": (
                    "resolved on the 31 whole fields (paired median gain %+.4f, %d of %d "
                    "images favouring, p = %.1e) and NOT resolved on the 26 crops "
                    "(%+.4f, p = %.2f)"
                    % (madp["tests"]["whole_fields"]["F1"]["6.0"]["paired_median_gain"],
                       madp["tests"]["whole_fields"]["F1"]["6.0"]["images_favouring"],
                       madp["tests"]["whole_fields"]["n"],
                       madp["tests"]["whole_fields"]["F1"]["6.0"]["wilcoxon_p"],
                       madp["tests"]["crops"]["F1"]["6.0"]["paired_median_gain"],
                       madp["tests"]["crops"]["F1"]["6.0"]["wilcoxon_p"]))},
            "area_ratio_crosses_one": _crossing(wf, madk["grid"]),
            "area_ratio_at_the_reported_k": wf["per_k"][str(K)]["area_ratio"],
            "area_ratio_at_the_app_default": wf["per_k"][str(float(DO.SHIPPED_MAD_K))][
                "area_ratio"]},
        "panel_b_region_classifier": {
            "verdict": "DECIDED BY MEASUREMENT, with zero free parameters, so fitted and "
                       "held-out are the same number by construction",
            "unit_set": "26 hand-labelled 512 px tiles, 13 specimens, pooled over every "
                        "pixel at 0 px tolerance, mad_k 5.0",
            "source": "paper/figures/sem_deadzone.json, pooled_26.v147 (classifier on) "
                      "and pooled_26.ablation (same candidate stage, classifier off)",
            "classifier_on": dead["pooled_26"]["v147"],
            "classifier_off": dead["pooled_26"]["ablation"],
            "paired": dead["paired"]["ablation"],
            "without_the_off_specimen_void_tile": dead["pooled_25_no_flood"],
            "not_duplicated": "what the deletion recovers per specimen is "
                              "paper/figures/out/6 - SEM, what deleting the region "
                              "classifier recovers.png (mk_recover.py); this panel is "
                              "only the decision"},
        "panel_c_absolute_gate": {
            "verdict": "INHERITED. The value 10 carries no recorded provenance "
                       "anywhere in the archived pipeline or in this project -- "
                       "analysis/detector_overrides.py calls it \"an integer with no "
                       "provenance here\" -- and it supplies more of the detector's "
                       "frame-scale recall than the whole seven-rung ladder does. It is "
                       "swept here, and the instruments disagree about its sign",
            "tiles": {"unit_set": "26 tiles, pooled, 0 px tolerance, mad_k 6.0",
                      "iou_by_threshold_26": {k: v["iou"] for k, v in tiles["gate_26"].items()},
                      "iou_by_threshold_25": {k: v["iou"] for k, v in tiles["gate_25"].items()},
                      "best_26": max(tiles["gate_26"], key=lambda k: tiles["gate_26"][k]["iou"]),
                      "best_25": max(tiles["gate_25"], key=lambda k: tiles["gate_25"][k]["iou"]),
                      "flood_tile": tiles["flood_tile"],
                      "read_this": (
                          "on all 26 tiles the best setting on this grid is t = %s, "
                          "where t = 0 is the gate switched off; drop the one crop with an "
                          "off-specimen void and the ordering reverses -- the gate is "
                          "then clearly worth having and the shipped 10 sits %.4f IoU "
                          "below that grid's own best at t = %s"
                          % (max(tiles["gate_26"], key=lambda k_: tiles["gate_26"][k_]["iou"]),
                             max(v["iou"] for v in tiles["gate_25"].values())
                             - tiles["gate_25"][str(GATE)]["iou"],
                             max(tiles["gate_25"], key=lambda k_: tiles["gate_25"][k_]["iou"])))},
            "frames": {"unit_set": "48 full frames carrying a hand-painted correction "
                                   "mask, %d painted crack px, mad_k 6.0" % painted,
                       "pooled_dark_stage_recall_by_threshold":
                           {str(g): _pooled(fr, lambda r, t=g: r["dark_crack"][str(t)])[0]
                            for g in GATE_GRID_DARK},
                       "full_chain_recall_pooled":
                           {str(t): chain_pooled(t, "kept")[0] for t in GATE_GRID_FRAME},
                       "full_chain_recall_per_frame_median":
                           {str(t): chain_pooled(t, "kept")[1] for t in GATE_GRID_FRAME},
                       "read_this": "the curve in the LOWER sub-panel is the "
                                    "darkness stage alone, which is 96% of the loss and "
                                    "agrees with the whole chain to 0.001 at the shipped "
                                    "setting; the three full-chain values are listed "
                                    "here"},
            "prior_record": "analysis/detector_overrides.py records the same quantity at "
                            "the app's mad_k 5.0: the gate proposes 13,907,547 of the "
                            "20,923,398 painted px that reach a candidate, 10,516,306 of "
                            "them reached by no ladder rung, and dropping it deletes "
                            "47.50% of kept hand-marked crack"},
        "panel_d_scale_ladder": {
            "verdict": "STRUCTURAL, NOT TUNED. Unioning the darkness cut over a ladder of "
                       "flattening radii was decided by measurement and costs no free "
                       "parameter, but the seven VALUES are a doubling ladder, not a "
                       "searched set, and no sweep over alternative ladders exists in "
                       "this project",
            "unit_set": "the same 48 painted frames. A painted pixel is credited to a "
                        "radius only when that radius and no other of the seven reaches "
                        "it, so each bar is a true leave-one-out marginal",
            "denominator": "the painted crack the SEVEN-RUNG UNION reaches on its own, "
                           "with the absolute gate switched off: %d px of the %d painted"
                           % (sum(r["dark_crack"]["0"] for r in fr), painted),
            "radii": ladder_bars["terms"],
            "pooled_pct": ladder_bars["pooled"],
            "per_frame_median_pct": ladder_bars["median"],
            "per_frame_p25_pct": ladder_bars["p25"],
            "per_frame_p75_pct": ladder_bars["p75"],
            "frames_with_a_nonzero_share": ladder_bars["frames_with_a_nonzero_share"],
            "frames_with_any_ladder_reached_paint":
                ladder_bars["frames_with_a_denominator"],
            "reached_by_two_or_more_radii_pct": ladder_bars["shared_pct"],
            "why_the_pooled_bar_and_the_median_diamond_differ": {
                "question": "at sigma = 320 the pooled bar is 3.80% and the per-frame "
                            "median 0.03%, two orders of magnitude apart. Is the bar an "
                            "artefact of the two frames that hold most of the paint?",
                "answer": "NO, and the quartile bars in the panel are what says so. Both "
                          "statistics are the same leave-one-out quantity; they differ "
                          "because the per-frame distribution is ZERO-INFLATED and "
                          "right-skewed, not because a few frames distort the pooled "
                          "sum. Only %d of the %d frames whose paint the ladder reaches "
                          "have any pixel that sigma = 320 alone reaches, so the median "
                          "sits at zero while p75 is %.2f%%; the same pattern holds at "
                          "sigma = 160 (%d of %d) and sigma = 80 (%d of %d). A coarse "
                          "radius contributes nothing on most frames and a great deal on "
                          "the frames that carry a crack wide enough for it, which is "
                          "the mechanism, not a defect of the aggregation."
                          % (ladder_bars["frames_with_a_nonzero_share"][-1],
                             ladder_bars["frames_with_a_denominator"][-1],
                             ladder_bars["p75"][-1],
                             ladder_bars["frames_with_a_nonzero_share"][-2],
                             ladder_bars["frames_with_a_denominator"][-2],
                             ladder_bars["frames_with_a_nonzero_share"][-3],
                             ladder_bars["frames_with_a_denominator"][-3]),
                "checked_separately": _concentration(fr, LADDER)},
            "read_this": (
                "%.1f%% of what the ladder reaches is reached by two or more radii, and "
                "the two largest unique contributions are sigma = %s and sigma = %s -- "
                "the ENDS of the ladder, which is the mechanism the override's docstring "
                "names: a crack is only reliably dark at the scales near its own width, "
                "so one radius sees one band"
                % (ladder_bars["shared_pct"],
                   *[ladder_bars["terms"][i] for i in sorted(
                       sorted(range(len(ladder_bars["pooled"])),
                              key=lambda j: -ladder_bars["pooled"][j])[:2])])),
            "the_gate_is_not_in_this_panel": {
                "why": "against the same denominator the absolute gate's unique share is "
                       "an order of magnitude larger than any radius and would make the "
                       "seven bars unreadable; it is panel (c)'s subject",
                "gate_unique_pct_of_the_whole_union_pooled": 100.0 * _pooled(
                    fr, lambda r: r["gate_only_crack"], den="union_crack")[0],
                "gate_unique_pct_of_the_whole_union_per_frame_median": 100.0 * _pooled(
                    fr, lambda r: r["gate_only_crack"], den="union_crack")[1]},
            "single_radius_comparison": "detector_overrides.py records the union's gain "
                                        "over the single sigma = 40 cut the archived "
                                        "pipeline used, on the 26 tiles at mad_k 5.0: "
                                        "P 0.4033 -> 0.4182, R 0.5326 -> 0.6252, "
                                        "IoU 0.2979 -> 0.3344, F1 0.4590 -> 0.5012, and "
                                        "the union is a strict superset so it can delete "
                                        "nothing"},
        "panel_e_size_floors": {
            "verdict": "INHERITED, AND NEITHER IS AT AN OPTIMUM",
            "unit_set": "26 tiles, pooled, 0 px tolerance, mad_k 6.0",
            "clean_mask_small_object_floor_iou": {k: v["iou"] for k, v in tiles["clean_min"].items()},
            "candidate_region_floor_iou": {k: v["iou"] for k, v in tiles["cand_min"].items()},
            "shipped_iou": tiles["shipped"]["iou"],
            "read_this": (
                "the small-object floor moves pooled IoU by %.4f over 0-50 px and its "
                "best value on this grid is %s, not %d; the candidate floor is worth "
                "%+.4f IoU against the smallest floor on its grid, so 40 px is a cost "
                "rather than a choice"
                % (max(tiles["clean_min"][str(v)]["iou"] for v in CLEANMIN_GRID if v <= 50)
                   - min(tiles["clean_min"][str(v)]["iou"] for v in CLEANMIN_GRID if v <= 50),
                   max((str(v) for v in CLEANMIN_GRID),
                       key=lambda v: tiles["clean_min"][v]["iou"]), CLEAN_MIN,
                   tiles["cand_min"][str(CAND_MIN)]["iou"]
                   - tiles["cand_min"][str(CANDMIN_GRID[0])]["iou"])),
            "frame_scale_cross_check": {
                "unit": "share of all hand-painted crack on the 48 frames lost to each "
                        "cleaning step, at the shipped settings",
                "small_object_floor": chain_pooled(GATE, "small13")[0],
                "opening": chain_pooled(GATE, "opening")[0],
                "candidate_floor": chain_pooled(GATE, "area40")[0],
                "never_dark": chain_pooled(GATE, "notdark")[0],
                "kept": kept / max(painted, 1),
                "note": "the buckets are disjoint and exhaustive and are asserted to sum "
                        "to the painted crack on every frame by "
                        "fullframe_recall_decomposition.decompose"}},
        "panel_f_opening_and_connectivity": {
            "verdict": "INHERITED, AND NOT AT AN OPTIMUM. Connectivity is below the "
                       "resolution of every instrument this project has",
            "unit_set": "26 tiles, pooled, 0 px tolerance, mad_k 6.0",
            "iou_by_radius_8_connected": {k: v["iou"] for k, v in tiles["opening"]["2"].items()},
            "iou_by_radius_4_connected": {k: v["iou"] for k, v in tiles["opening"]["1"].items()},
            "largest_8_vs_4_difference": max(
                abs(tiles["opening"]["2"][str(v)]["iou"] - tiles["opening"]["1"][str(v)]["iou"])
                for v in OPEN_GRID),
            "read_this": (
                "no opening at all scores higher than the shipped disk(1) by %.4f IoU, "
                "and the whole 4-versus-8 connectivity question is worth %.4f"
                % (tiles["opening"]["2"]["0"]["iou"] - tiles["opening"]["2"]["1"]["iou"],
                   max(abs(tiles["opening"]["2"][str(v)]["iou"]
                           - tiles["opening"]["1"][str(v)]["iou"]) for v in OPEN_GRID)))},
        "table_1_row_that_is_two_constants": {
            "row": "Morphological opening size 13 px",
            "what_the_code_does": "unified_pipeline.py calls clean_mask(dark, "
                                  "min_area_px=13); inside clean_mask the 13 is "
                                  "remove_small_objects' AREA floor and the opening is "
                                  "morphology.opening(mask, disk(open_radius=1)). The "
                                  "two are separate constants and are drawn in panels "
                                  "(e) and (f) respectively",
            "source": "sem-crack-detector/code/detect_cracks.py clean_mask and "
                      "interior_active_learning/code/unified_pipeline.py"},
        "constants_with_no_evidence_and_so_not_drawn": {
            "scale_ladder_values": "no sweep over alternative ladders (a different base, "
                                   "a different number of rungs, a different top radius) "
                                   "exists; panel (d) shows what the chosen ladder does, "
                                   "not that it is the best ladder",
            "clean_mask_close_radius_3": "not a row of Table 1 and never swept here. "
                                         "analysis/research/improve/"
                                         "lever5_postprocessing.py searched it and its "
                                         "own adversarial audit "
                                         "(audit_lever5_postprocessing.py) withdrew the "
                                         "result: 82.4% of the gain was one tile",
            "denoise_sigma_1.0": "segment_dark_regions' gaussian pre-smooth, inherited "
                                 "and never swept",
            "flatten_background_sigma_40": "fixed; the ladder in (d) is the response to "
                                           "it rather than a sweep of it"},
        "the_preprocessing_budget": {
            "why_it_matters": "the constants above are not free: together they are a "
                              "tuning budget spent before any model runs. On the 15-tile "
                              "benchmark this project scored the published models on, a "
                              "one-line global darkness threshold fitted "
                              "leave-one-frame-out outscores a network trained on 30,017 "
                              "images, which is what a reviewer should weigh a "
                              "seven-constant preprocessing chain against",
            "15_tile_benchmark_iou": {
                "a one-line global threshold, leave-one-frame-out":
                    comp["global threshold"]["iou"],
                "OmniCrack30k nnU-Net, trained on 30,017 images":
                    comp["OmniCrack30k nnU-Net"]["iou"],
                "SAM 3, zero-shot union": comp["SAM 3 (zero-shot union)"]["iou"],
                "shipped v1.49.2, all 15 tiles": comp[">>> shipped v1.49.2, all 15 tiles"]["iou"]},
            "source": "docs/slides/comparison.json",
            "caveat": "at n = 15 nothing on that benchmark separates statistically, and "
                      "3 of its 9 frames also appear in the 26-tile set that informed the "
                      "shipped configuration"},
        "tally": {
            "selected by a sweep on labelled data": ["MAD multiplier k"],
            "decided by measurement, zero free parameters":
                ["learned region classifier (disabled)",
                 "multiscale union versus a single flattening radius"],
            "inherited, no recorded provenance, swept only after the fact":
                ["absolute intensity gate 10", "morphological opening disk(1)",
                 "clean_mask small-object floor 13 px",
                 "candidate region floor 40 px", "8-connectivity"],
            "inherited and never swept at all":
                ["the seven ladder values 5-320 px", "clean_mask close radius 3 px",
                 "denoise sigma 1.0", "flatten_background sigma 40"]},
        "aggregation_warning": "the panels use three different unit sets -- 31 public "
                               "whole fields, 26 hand-labelled tiles and 48 painted full "
                               "frames -- and a value from one may not be compared with a "
                               "value from another. Each panel names its own n.",
        "generated_from": {
            "docs/figures/parameters_tiles.json": tiles["key"],
            "docs/figures/parameters_frames.json": frames["key"],
            "docs/figures/madk_above_five.json": "committed",
            "docs/figures/madk_paired_test.json": "committed",
            "paper/figures/sem_deadzone.json": dead.get("generated", "committed"),
            "docs/slides/comparison.json": "committed"},
    }
    json.dump(rec, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)
    return rec


def main():
    t_start = time.time()
    tiles = _cached(os.path.join(DOCS, "parameters_tiles.json"),
                    _key(k=K, gate=list(GATE_GRID), cmin=list(CLEANMIN_GRID),
                         amin=list(CANDMIN_GRID), op=list(OPEN_GRID),
                         ladder=list(LADDER), clean=CLEAN_MIN, cand=CAND_MIN),
                    tile_evidence, dict(mad_k=K))
    frames = _cached(os.path.join(DOCS, "parameters_frames.json"),
                     _key(k=K, gate=GATE, ladder=list(LADDER), clean=CLEAN_MIN,
                          cand=CAND_MIN, dark=list(GATE_GRID_DARK),
                          chain=list(GATE_GRID_FRAME)),
                     frame_evidence,
                     dict(mad_k=K, gate=GATE, ladder=list(LADDER),
                          clean_min=CLEAN_MIN, cand_min=CAND_MIN))
    madk = json.load(open(os.path.join(DOCS, "madk_above_five.json")))
    madp = json.load(open(os.path.join(DOCS, "madk_paired_test.json")))
    dead = json.load(open(os.path.join(HERE, "sem_deadzone.json")))
    bars = draw(tiles, frames, madk, dead)
    rec = sidecar(tiles, frames, madk, madp, dead, bars)
    for k_, v in rec["tally"].items():
        print(f"  {k_}: {', '.join(v)}")
    print(f"total {time.time() - t_start:.0f}s")


if __name__ == "__main__":
    main()
