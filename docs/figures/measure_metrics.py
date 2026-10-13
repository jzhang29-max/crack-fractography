"""Stage 1 of the metric figures: measure everything the four plates draw.

Writes `metric_figures.json` beside itself. That file is the record -- every number in a
caption is resolved from it, so a reader can check a figure without a GPU, the two
detection repositories, or a six-minute run. `mk_metric_figures.py` draws from it and
computes nothing.

WHAT IS MEASURED, AND WHY EACH ONE NEEDS ITS OWN SCORING RULE

  (1) THE AGGREGATION. One set of masks -- the v1.49.1 candidate stage with the region
      classifier off -- scored five ways. precision, recall, F1 and IoU are reported
      pooled over every pixel of the 26 tiles, as the median of the 26 per-tile values,
      and as the median over the 13 specimens of the median of that specimen's tiles,
      each at 0 px and at the 2 px tolerance the literature reports. The five readings
      are of the SAME pixels; nothing about the detector changes between them.

  (2) THE CEILING. A trace of width 1, 3, ... 41 px laid down the skeleton of the
      human's own paint is the best answer any detector could give if the paint marks
      where the crack is but not how wide the brush was. Scoring that against the paint
      bounds every overlap metric from above. Computed here, not quoted.

  (3) WIDTH GAMEABILITY. The shipped mask, dilated until it has k times its own area,
      k = 1.0 ... 3.0. A dilation adds no information: it cannot find a crack the mask
      missed. A metric that RISES under it is measuring thickness.

  (4) THE OPERATING CURVE. precision against recall as the detector's own two knobs move
      -- mad_k over the seven-scale union, and absolute_dark_thresh -- with the shipped
      point marked and the no-information floor (the crack prevalence, which is what
      marking every pixel scores) drawn in.

CONTROLS. Nothing here is believed until `controls()` passes, and each control is one a
broken implementation would fail: the union rebuilt from the per-scale cache must be
bit-identical to the shipped `segment_dark_regions`; the local `clean` must be
bit-identical to `detect_cracks.clean_mask`; a 1 px trace must score precision exactly
1.0 because the skeleton of a mask lies inside it; dilating to 1.0x must return the mask
unchanged; and tilebench's own oracle/empty/mark-everything must come out at 1.0, 0.0 and
the prevalence.

Run:  <sem-crack-detector>/.venv/bin/python -B measure_metrics.py [--quick]
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(os.path.dirname(HERE))
SEM = os.environ.get("SEM_REPO", os.path.join(os.path.dirname(APP), "sem-crack-detector"))
for _p in (os.path.join(APP, "analysis", "research"), os.path.join(APP, "analysis"),
           os.path.join(SEM, "code")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.dont_write_bytecode = True

from scipy import ndimage as ndi                      # noqa: E402
from skimage import exposure as _exp, filters, morphology  # noqa: E402
from skimage.morphology import skeletonize            # noqa: E402

import tilebench as TB                                # noqa: E402
import detect_cracks as D                             # noqa: E402
import detector_overrides as DO                       # noqa: E402

OUT = os.path.join(HERE, "metric_figures.json")
ST8 = ndi.generate_binary_structure(2, 2)             # 8-connected, as measure.label uses
TRACE_K = list(range(0, 21))                          # trace widths 1, 3, ... 41
DILATE_F = [round(1.0 + 0.1 * i, 1) for i in range(21)]   # 1.0 ... 3.0
MAD_K = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 10.0, 12.0]
ABS_DARK = [0, 5, 10, 15, 20, 25, 30, 40, 50, 60]
TAU = 2


class _U:
    """Something for DO.install to rebind its stages onto."""


_up = _U()
DO.install(_up)


# ----------------------------------------------------------------- the shipped chain
def _flatten(img8, sigma):
    """detector_overrides.install()'s own flattening, at an arbitrary ladder radius.
    Asserted bit-identical to the shipped union in controls()."""
    if sigma <= DO.DECIMATE_ABOVE_SIGMA:
        return D.flatten_background(img8, sigma=sigma)
    f = max(1, int(round(sigma / 32.0)))
    small = ndi.uniform_filter(img8.astype(np.float32), f)[::f, ::f]
    bg_s = ndi.gaussian_filter(small, sigma / f, mode="nearest")
    bg = ndi.zoom(bg_s, (img8.shape[0] / bg_s.shape[0], img8.shape[1] / bg_s.shape[1]),
                  order=1, mode="nearest")[:img8.shape[0], :img8.shape[1]]
    if bg.shape != img8.shape:
        bg = np.pad(bg, ((0, img8.shape[0] - bg.shape[0]),
                         (0, img8.shape[1] - bg.shape[1])), mode="edge")
    flat = img8.astype(np.float32) - bg
    lo, hi = np.percentile(flat, [0.5, 99.5])
    if hi <= lo:
        lo, hi = flat.min(), flat.max()
    return _exp.rescale_intensity(flat, in_range=(lo, hi), out_range=(0, 255)).astype(np.uint8)


def scale_cache(img8):
    """(smoothed flat, otsu, median, mad) per ladder radius, so any mad_k is then free."""
    out = []
    for sigma in DO.SCALE_LADDER:
        f = D.flatten_background(img8, sigma=40) if sigma == 40 else _flatten(img8, sigma)
        sm = filters.gaussian(f, sigma=1.0, preserve_range=True)
        med = float(np.median(sm))
        out.append(dict(sigma=sigma, sm=sm, otsu=float(filters.threshold_otsu(sm)), med=med,
                        mad=float(np.median(np.abs(sm - med)) * 1.4826)))
    return out


def union_at(cache, img8, mad_k=5.0, absolute_dark=10):
    out = None
    for sc in cache:
        c = sc["sm"] < min(sc["otsu"], sc["med"] - mad_k * sc["mad"])
        out = c if out is None else (out | c)
    if absolute_dark and absolute_dark > 0:
        out = out | (img8 < absolute_dark)
    return out


def clean(dark, open_radius=1, close_radius=3, min_area=13, fill=True):
    """detect_cracks.clean_mask, spelled out. Asserted equal to it in controls().
    `fill` exists only so controls() can ask whether the last step does anything on a
    given tile -- it is never turned off in a measurement."""
    m = morphology.remove_small_objects(dark, max_size=min_area)
    if open_radius:
        m = morphology.opening(m, morphology.disk(open_radius))
    if close_radius:
        m = morphology.closing(m, morphology.disk(close_radius))
    return ndi.binary_fill_holes(m) if fill else m


def area_filter(mask, min_area_px=40):
    """unified_pipeline's extract_candidates(min_area_px=40). 8-connected, as
    measure.label(connectivity=2) is; scipy's default of 4 is a different filter."""
    lab, n = ndi.label(mask, structure=ST8)
    if n == 0:
        return mask
    sizes = np.bincount(lab.ravel())
    keep = sizes >= min_area_px
    keep[0] = False
    return keep[lab]


def shipped(img8, cache=None, mad_k=5.0, absolute_dark=10):
    """What v1.49.1 marks on a tile: 7-scale dark union -> clean_mask(13) -> 40 px
    component filter -> (no region classifier, it is switched off)."""
    cache = scale_cache(img8) if cache is None else cache
    return area_filter(clean(union_at(cache, img8, mad_k, absolute_dark)), 40)


# ----------------------------------------------------------------- metrics
def pr(tp, fp, fn):
    p = tp / max(tp + fp, 1)
    r = tp / max(tp + fn, 1)
    return dict(precision=p, recall=r, f1=2 * p * r / max(p + r, 1e-12),
                iou=tp / max(tp + fp + fn, 1))


def cldice(pred, gt, sg=None):
    pred = np.asarray(pred, bool)
    gt = np.asarray(gt, bool)
    if not pred.any() or not gt.any():
        return 0.0
    sp = skeletonize(pred)
    sg = skeletonize(gt) if sg is None else sg
    a = (sp & gt).sum() / max(sp.sum(), 1)
    b = (sg & pred).sum() / max(sg.sum(), 1)
    return 0.0 if a + b == 0 else float(2 * a * b / (a + b))


def skelf1(pred, gt, tau=TAU, sg=None, dg=None):
    pred = np.asarray(pred, bool)
    gt = np.asarray(gt, bool)
    if not pred.any() or not gt.any():
        return 0.0
    sp = skeletonize(pred)
    sg = skeletonize(gt) if sg is None else sg
    if not sp.any() or not sg.any():
        return 0.0
    dg = ndi.distance_transform_edt(~sg) if dg is None else dg
    dp = ndi.distance_transform_edt(~sp)
    p = float((dg[sp] <= tau).mean())
    r = float((dp[sg] <= tau).mean())
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def dilate_steps(m, factor):
    """Whole-step binary dilation until the mask holds `factor` times its own area --
    the spelling analysis/research/improve/honest_score.py uses. Kept so the finer
    growth below has something already in the record to be checked against. A step
    overshoots: asking for 1.5x lands near 1.66x, which is why the ACHIEVED ratio is
    what gets plotted and never the requested one."""
    out = np.asarray(m, bool).copy()
    base = int(out.sum())
    if base == 0:
        return out, 1.0
    target = base * factor
    for _ in range(80):
        if out.sum() >= target:
            break
        out = ndi.binary_dilation(out, ST8)
    return out, float(out.sum()) / base


def grow_to(m, factor, edt=None):
    """The no-information control, at a CONTINUOUS radius. A whole dilation step is a
    coarse instrument -- one step can add 30% of the area, so a step sweep cannot say
    what a metric does at 1.1x. Thresholding the Euclidean distance from the mask at a
    real-valued radius can, and bisection lands the achieved ratio on the requested one.

    Adds no information by construction: every pixel it adds is chosen by distance from
    what the detector already marked, and the labels are never consulted."""
    m = np.asarray(m, bool)
    base = int(m.sum())
    if base == 0 or factor <= 1.0:
        return m.copy(), 1.0
    edt = ndi.distance_transform_edt(~m) if edt is None else edt
    target = base * factor
    lo, hi = 0.0, 1.0
    while (edt <= hi).sum() < target and hi < 512:
        hi *= 2
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if (edt <= mid).sum() < target:
            lo = mid
        else:
            hi = mid
    out = edt <= hi
    return out, float(out.sum()) / base


# ----------------------------------------------------------------- controls
def controls(tiles, caches, verbose=True):
    """Each of these fails loudly if the corresponding piece is wrong. Verified by
    deliberately breaking each one once; see the module header of mk_metric_figures.py."""
    ok = True
    print("CONTROLS")
    ok &= TB.controls()

    bad = 0
    for t, c in zip(tiles, caches):
        a = union_at(c, t["img8"], 5.0, DO.ABSOLUTE_DARK_THRESH)
        b = _up.segment_dark_regions(D.flatten_background(t["img8"]), img8=t["img8"])
        bad += 0 if np.array_equal(a, b) else 1
    ok &= bad == 0
    print(f"  {'PASS' if not bad else 'FAIL'}  cached union == shipped segment_dark_regions "
          f"on {len(tiles)} / {len(tiles)} tiles" + (f"  ({bad} differ)" if bad else ""))

    # On every tile, not the first one: a hole-filling bug is invisible on a mask with
    # no holes, and `teeth` counts the tiles where the last step of clean() actually
    # changes something, so a comparison that could only ever pass is reported as such.
    bad = teeth = 0
    for t, c in zip(tiles, caches):
        d = union_at(c, t["img8"], 5.0, DO.ABSOLUTE_DARK_THRESH)
        mine = clean(d)
        bad += 0 if np.array_equal(
            mine, D.clean_mask(d, open_radius=1, close_radius=3, min_area_px=13)) else 1
        teeth += 0 if np.array_equal(mine, clean(d, fill=False)) else 1
    ok &= bad == 0 and teeth > 0
    print(f"  {'PASS' if not bad and teeth else 'FAIL'}  clean() == detect_cracks.clean_mask "
          f"on {len(tiles) - bad} / {len(tiles)} tiles "
          f"(its last step, the hole fill, changes {teeth} of them, so the test has teeth)")

    gt = tiles[0]["gt"]
    sk = skeletonize(gt)
    inside = (sk & gt).sum() / max(sk.sum(), 1)
    # ... and it must be ONE pixel wide. Inside-the-label alone is not a test: the paint
    # is tens of pixels across, so a skeleton dilated twice is still inside it. A 2x2
    # block that is entirely set cannot occur in a thin skeleton and does occur in any
    # dilation of one.
    blocks = int((sk[:-1, :-1] & sk[1:, :-1] & sk[:-1, 1:] & sk[1:, 1:]).sum())
    good = abs(inside - 1.0) < 1e-12 and blocks == 0
    ok &= good
    print(f"  {'PASS' if good else 'FAIL'}  a 1 px trace lies inside the label "
          f"(precision {inside:.6f}) and is one pixel wide ({blocks} filled 2x2 blocks)")

    m = shipped(tiles[0]["img8"], caches[0])
    m0, ratio = grow_to(m, 1.0)
    same = np.array_equal(m, m0) and ratio == 1.0
    ok &= same
    print(f"  {'PASS' if same else 'FAIL'}  growing to 1.0x returns the mask unchanged")

    # The EDT is itself quantised -- a 512x512 grid admits only so many distances -- so
    # the achieved ratio cannot be exact. It must be close (a whole dilation STEP
    # overshoots 1.5x by about 16%, which is why that spelling is not the one plotted)
    # and it must be a superset, because a growth that drops a pixel is not a growth.
    m2, ratio = grow_to(m, 1.5)
    hit = abs(ratio - 1.5) < 0.05 and bool((m2 | m).sum() == m2.sum())
    ok &= hit
    print(f"  {'PASS' if hit else 'FAIL'}  growing to 1.5x lands within 5% of 1.5x "
          f"({ratio:.4f}) and is a superset")
    return ok


# ----------------------------------------------------------------- provenance
def app_mask_check(tiles, masks):
    """The figures score `shipped()` above. The APP runs unified_pipeline through
    analysis/detect_one.py. Those are not obviously the same mask, and a headline
    measured on something the application does not emit is not a headline.

    Runs the real `run_unified_pipeline` exactly as detect_one.py does -- same
    DO.install, same correction suppression, same classifier-off keep rule -- with
    load_as_uint8 and find_field_of_view patched to hand it the cached tile instead of
    reading a file, so nothing is written into the archived read-only repository.
    """
    iac = os.path.join(SEM, "interior_active_learning", "code")
    if not os.path.isdir(iac):
        return dict(ran=False, why=f"no {iac}")
    if iac not in sys.path:
        sys.path.insert(0, iac)
    import unified_pipeline as up
    import common
    up.load_correction_mask = lambda *a, **k: None
    common.load_correction_mask = lambda *a, **k: None
    up.load_hard_overrides = lambda *a, **k: {}
    DO.install(up)
    rows = []
    for i, (t, m) in enumerate(zip(tiles, masks), 1):
        img8 = t["img8"]
        up.load_as_uint8 = lambda *a, **k: img8
        up.find_field_of_view = lambda a: (0, 0, a.shape[1], a.shape[0])
        st = up.run_unified_pipeline("TILE")
        lab, df = st["labeled"], st["df"]
        keep = (df.loc[df["IsCrack"] == True, "Label"] if DO.USE_REGION_CLASSIFIER  # noqa: E712
                else df["Label"]).tolist()
        app = np.isin(lab, keep) if keep else np.zeros(lab.shape, bool)
        io = st.get("interior_origin") or {}
        inter = np.isin(lab, list(io)) if io else np.zeros_like(app)
        extra = app & ~m
        rows.append(dict(frame=t["frame"], app_px=int(app.sum()), scored_px=int(m.sum()),
                         app_only=int(extra.sum()), scored_only=int((m & ~app).sum()),
                         app_only_from_pass2=int((extra & inter).sum()),
                         bridge_px=int(np.asarray(st["bridge_mask"]).sum())
                         if st.get("bridge_mask") is not None else 0,
                         **{"app_" + k: v for k, v in TB.counts(app, t["gt"], tol=2).items()}))
        print(f"  [{i:>2}/{len(tiles)}] app {rows[-1]['app_px']:>7,}  "
              f"scored {rows[-1]['scored_px']:>7,}  app-only {rows[-1]['app_only']:>6,}",
              flush=True)
    tot = sum(r["app_only"] for r in rows)
    print(f"  the app emits {tot:,} px the figures do not score "
          f"({100 * tot / max(sum(r['scored_px'] for r in rows), 1):.2f}% of scored area); "
          f"the figures score {sum(r['scored_only'] for r in rows):,} px the app does not")
    return dict(ran=True, rows=rows)


# ----------------------------------------------------------------- main
def main():
    t0 = time.time()
    tiles = TB.load()
    print(f"{len(tiles)} tiles, "
          f"{len({t['specimen'] for t in tiles})} specimens\nbuilding scale caches ...", flush=True)
    caches = []
    for i, t in enumerate(tiles, 1):
        caches.append(scale_cache(t["img8"]))
        print(f"  [{i:>2}/{len(tiles)}] {t['frame'][:46]}", flush=True)

    if not controls(tiles, caches):
        sys.exit("CONTROLS FAILED -- nothing measured here can be read")

    rec = dict(n_tiles=len(tiles), n_specimens=len({t["specimen"] for t in tiles}),
               tau=TAU, tolerance_px=2,
               frames=[t["frame"] for t in tiles],
               specimens=[t["specimen"] for t in tiles],
               ladder=list(DO.SCALE_LADDER), shipped_mad_k=5.0,
               shipped_absolute_dark=DO.ABSOLUTE_DARK_THRESH,
               use_region_classifier=DO.USE_REGION_CLASSIFIER)
    rec["tile_px"] = [int(t["gt"].size) for t in tiles]
    rec["gt_px"] = [int(t["gt"].sum()) for t in tiles]
    rec["prevalence"] = sum(rec["gt_px"]) / sum(rec["tile_px"])
    # The off-specimen void. REPORTING_GUIDE.md: the 26-tile headline must never appear
    # without the 25-tile row, because this one tile owns 80.3% of all false positives.
    rec["flooded_index"] = [i for i, t in enumerate(tiles) if t["frame"] == TB.FLOODED]

    # (1) the aggregation ------------------------------------------------------------
    print("\n(1) scoring the shipped mask ...", flush=True)
    counts, areas = [], []
    masks = []
    for i, (t, c) in enumerate(zip(tiles, caches), 1):
        m = shipped(t["img8"], c)
        masks.append(m)
        areas.append(int(m.sum()))
        counts.append(TB.counts(m, t["gt"], tol=2))
        print(f"  [{i:>2}/{len(tiles)}] marked {m.sum():>7,}", flush=True)
    rec["shipped_counts"] = counts
    rec["shipped_area_px"] = areas

    # (2) the ceiling ----------------------------------------------------------------
    print("\n(2) the ceiling: a perfect trace at widths 1 .. 41 ...", flush=True)
    ceil = {k: dict(iou=[], f1=[], cldice=[], skelf1=[], tp=[], fp=[], fn=[]) for k in TRACE_K}
    for i, t in enumerate(tiles, 1):
        gt = t["gt"]
        sg = skeletonize(gt)
        dg = ndi.distance_transform_edt(~sg)
        for k in TRACE_K:
            tr = sg if k == 0 else ndi.binary_dilation(sg, ST8, iterations=k)
            tp = int((tr & gt).sum()); fp = int((tr & ~gt).sum()); fn = int((~tr & gt).sum())
            d = ceil[k]
            mm = pr(tp, fp, fn)
            d["iou"].append(mm["iou"]); d["f1"].append(mm["f1"])
            d["cldice"].append(cldice(tr, gt, sg)); d["skelf1"].append(skelf1(tr, gt, TAU, sg, dg))
            d["tp"].append(tp); d["fp"].append(fp); d["fn"].append(fn)
        print(f"  [{i:>2}/{len(tiles)}] {t['frame'][:46]}", flush=True)
    rec["ceiling_widths"] = [2 * k + 1 for k in TRACE_K]
    rec["ceiling"] = {str(2 * k + 1): ceil[k] for k in TRACE_K}

    # (3) width gameability ----------------------------------------------------------
    print("\n(3) width gameability: the shipped mask dilated to 1.0 .. 3.0x area ...", flush=True)
    game = {f: dict(iou=[], cldice=[], skelf1=[], ratio=[], precision=[], recall=[])
            for f in DILATE_F}
    step = {f: dict(iou=[], cldice=[], skelf1=[], ratio=[]) for f in DILATE_F}
    for i, (t, m) in enumerate(zip(tiles, masks), 1):
        gt = t["gt"]
        sg = skeletonize(gt)
        dg = ndi.distance_transform_edt(~sg)
        edt = ndi.distance_transform_edt(~m)
        for f in DILATE_F:
            dm, ratio = grow_to(m, f, edt)
            tp = int((dm & gt).sum()); fp = int((dm & ~gt).sum()); fn = int((~dm & gt).sum())
            mm = pr(tp, fp, fn)
            d = game[f]
            d["iou"].append(mm["iou"]); d["precision"].append(mm["precision"])
            d["recall"].append(mm["recall"]); d["ratio"].append(ratio)
            d["cldice"].append(cldice(dm, gt, sg)); d["skelf1"].append(skelf1(dm, gt, TAU, sg, dg))
            sm_, sr = dilate_steps(m, f)
            e = step[f]
            tp = int((sm_ & gt).sum()); fp = int((sm_ & ~gt).sum()); fn = int((~sm_ & gt).sum())
            e["iou"].append(pr(tp, fp, fn)["iou"]); e["ratio"].append(sr)
            e["cldice"].append(cldice(sm_, gt, sg)); e["skelf1"].append(skelf1(sm_, gt, TAU, sg, dg))
        print(f"  [{i:>2}/{len(tiles)}] {t['frame'][:46]}", flush=True)
    rec["dilate_factors"] = DILATE_F
    rec["gameability"] = {str(f): game[f] for f in DILATE_F}
    rec["gameability_wholestep"] = {str(f): step[f] for f in DILATE_F}

    # (4) the operating curve --------------------------------------------------------
    print("\n(4) the operating curve ...", flush=True)
    sweeps = {}
    for name, knob, values, fixed in [
            ("mad_k", "mad_k", MAD_K, dict(absolute_dark=DO.ABSOLUTE_DARK_THRESH)),
            ("absolute_dark", "absolute_dark", ABS_DARK, dict(mad_k=5.0))]:
        rows = []
        for v in values:
            kw = dict(fixed); kw[knob] = v
            cs = [TB.counts(shipped(t["img8"], c, **kw), t["gt"], tol=2)
                  for t, c in zip(tiles, caches)]
            rows.append(dict(value=v, counts=cs))
            agg = pr(sum(x["tp"] for x in cs), sum(x["fp"] for x in cs), sum(x["fn"] for x in cs))
            print(f"  {name}={v:<6} pooled P {agg['precision']:.4f} R {agg['recall']:.4f} "
                  f"IoU {agg['iou']:.4f}", flush=True)
        sweeps[name] = rows
    rec["sweeps"] = sweeps

    # a budget-matched random control at the shipped area: a no-information mask whose
    # precision must land at the prevalence, which is what fixes the floor in plate 4.
    rng = np.random.default_rng(0)
    rnd = []
    for t, a in zip(tiles, areas):
        r = np.zeros(t["gt"].size, bool)
        r[rng.choice(t["gt"].size, a, replace=False)] = True
        rnd.append(TB.counts(r.reshape(t["gt"].shape), t["gt"], tol=2))
    rec["random_area_matched"] = rnd
    agg = pr(sum(x["tp"] for x in rnd), sum(x["fp"] for x in rnd), sum(x["fn"] for x in rnd))
    print(f"  random, area-matched: pooled P {agg['precision']:.4f} "
          f"(prevalence {rec['prevalence']:.4f})")

    # (5) is the scored mask the one the APP emits? -------------------------------
    print("\n(5) provenance: running the app's own pipeline on each tile ...", flush=True)
    rec["app_mask_check"] = app_mask_check(tiles, masks)

    rec["seconds"] = round(time.time() - t0, 1)
    with open(OUT, "w") as fh:
        json.dump(rec, fh, separators=(",", ":"), sort_keys=True)
    print(f"\nwrote {OUT}  ({os.path.getsize(OUT) / 1024:.0f} KB, {rec['seconds']:.0f} s)")


if __name__ == "__main__":
    main()
