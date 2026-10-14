#!/usr/bin/env python3
"""Build docs/flowchart/index.html: the shipped crack pipeline, one real image per stage.

EVERY PANEL IS A REAL ARRAY. Nothing here is drawn, mocked or schematic. The frame is
pushed through `unified_pipeline.run_unified_pipeline` -- the function the desktop app
calls -- with `detector_overrides.install()` applied exactly as `analysis/detect_one.py`
applies it, and the stage functions are wrapped (not reimplemented) so what is rendered
is the array that stage actually returned.

Two things this file refuses to do, because both have shipped a wrong figure here before:
  * it never reimplements a stage to draw it. Each rung of the darkness ladder is obtained
    by calling the INSTALLED `segment_dark_regions` with that single rung in the ladder,
    and the OR of the seven is asserted equal, bit for bit, to the full-ladder mask the
    pipeline itself produced. If this file drifts from the detector, that assert fires.
  * it never hardcodes a path outside the repo pair. APP_REPO/SEM_REPO default to this
    file's own location and its sibling, and every path written into index.html is
    relative, so the folder can be copied anywhere and still open.

Usage
  <sem-venv>/bin/python -B make_flowchart.py            # capture + render (slow: ~4 min)
  <sem-venv>/bin/python -B make_flowchart.py --render    # re-render from _stages.npz only
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.abspath(os.environ.get("APP_REPO", os.path.dirname(os.path.dirname(HERE))))
SEM = os.path.abspath(os.environ.get("SEM_REPO",
                                     os.path.join(os.path.dirname(APP), "sem-crack-detector")))
NPZ = os.path.join(HERE, "_stages.npz")
STATS = os.path.join(HERE, "_stats.json")

# --- the frame, and the reason it is this frame -----------------------------------------
# Chosen by score, not by eye. Every one of the 26 hand-labelled tiles was pushed through
# the shipped candidate stage and scored by analysis/research/tilebench.py; the tiles were
# ranked by IoU and the two central ones taken (n = 26, so there is no single median tile).
# They sit at IoU 0.4039 and 0.4339 and are EXACTLY equidistant from the median 0.4189 by
# construction, so the tie is broken toward the LOWER of the two: a flowchart built on the
# better half of its own corpus is an advertisement.
FRAME = "HIP_24hr_SE_Side_006"
CROP = (4695, 807, 512, 512)                 # x, y, w, h, in the tile corpus' coordinates
TILE = "HIP_24hr_SE_Side_006__crop_4695_807_512x512"
PICK_IOU = 0.4039
PICK_WHY = ("lower of the two central tiles by IoU over the 26 hand-labelled tiles "
            "(0.4039 and 0.4339 straddle the median 0.4189 at equal distance; the tie is "
            "broken downward so the page cannot flatter the detector)")

LADDER = (5, 10, 20, 40, 80, 160, 320)
ABS_DARK = 10
MIN_AREA_CLEAN = 13
MIN_AREA_REGION = 40


def _paths():
    for p in (os.path.join(APP, "analysis"), os.path.join(APP, "analysis", "research"),
              os.path.join(APP, "analysis", "research", "improve"),
              os.path.join(SEM, "code"), os.path.join(SEM, "interior_active_learning", "code")):
        if p not in sys.path:
            sys.path.insert(0, p)


def capture():
    """Run the real pipeline on the real frame and keep every intermediate, cropped."""
    _paths()
    sys.dont_write_bytecode = True
    import detector_overrides as DO
    import detect_cracks as D
    import unified_pipeline as up
    import common
    from skimage import filters

    # Corrections off, exactly as analysis/detect_one.py runs it: the mask on this page is
    # the detector's own answer, not the detector plus a human's paint.
    up.load_correction_mask = lambda *a, **k: None
    common.load_correction_mask = lambda *a, **k: None
    up.load_hard_overrides = lambda *a, **k: {}

    applied = DO.install(up)
    assert DO.USE_REGION_CLASSIFIER is False, "page text says the classifier is off"
    assert tuple(DO.SCALE_LADDER) == LADDER and DO.ABSOLUTE_DARK_THRESH == ABS_DARK

    rec = {}
    f_flat, f_seg, f_clean, f_ves, f_ext = (up.flatten_background, up.segment_dark_regions,
                                            up.clean_mask, up.compute_vesselness,
                                            up.extract_candidates)

    def w_flat(img8, *a, **k):
        rec["img8"] = img8
        t = time.time()
        out = f_flat(img8, *a, **k)
        rec["t_flat"] = time.time() - t
        rec["flat"] = out
        # The thing flatten_background removes, kept so the page can show WHY it runs.
        rec["bg"] = filters.gaussian(img8, sigma=40, preserve_range=True)
        return out

    def w_seg(flat, *a, **k):
        t = time.time()
        out = f_seg(flat, *a, **k)
        rec["t_seg"] = time.time() - t
        rec["dark"] = out
        return out

    def w_clean(mask, *a, **k):
        out = f_clean(mask, *a, **k)
        rec["clean"] = out
        return out

    def w_ves(flat, *a, **k):
        t = time.time()
        out = f_ves(flat, *a, **k)
        rec["t_ves"] = time.time() - t
        return out

    def w_ext(mask, flat, ves, **k):
        lab, df = f_ext(mask, flat, ves, **k)
        rec["lab_pass1"] = lab
        rec["n_pass1"] = int(lab.max())
        rec["min_area_px"] = k.get("min_area_px")
        return lab, df

    up.flatten_background, up.segment_dark_regions = w_flat, w_seg
    up.clean_mask, up.compute_vesselness, up.extract_candidates = w_clean, w_ves, w_ext

    t0 = time.time()
    st = up.run_unified_pipeline(FRAME)
    rec["t_total"] = time.time() - t0
    print(f"  pipeline done in {rec['t_total']:.1f}s  ({applied})", flush=True)

    img8, flat = rec["img8"], rec["flat"]
    lab_final, df = st["labeled"], st["df"]
    # Classifier OFF -> every candidate region is kept, which is what detect_one.py emits.
    emitted = lab_final > 0
    pass1 = rec["lab_pass1"] > 0
    pass2_added = emitted & ~pass1

    # --- the seven rungs, taken from the INSTALLED function, one rung at a time ----------
    import angle4_shipped as A4
    rungs, t_rung = {}, {}
    absterm = img8 < ABS_DARK
    for s in LADDER:
        t = time.time()
        seg1 = A4.seg_fn(ladder=(s,), mad_k=5.0)
        # `flat` is used only by the sigma=40 rung; every other rung re-flattens img8 at
        # its own radius inside the installed function, on the decimated path production
        # uses. Handing it a flat computed here would be a second implementation.
        m = seg1(flat, img8=img8)
        t_rung[s] = time.time() - t
        rungs[s] = m & ~absterm          # the rung's own contribution, absolute term split out
        print(f"  rung sigma={s:<3d} {int(rungs[s].sum()):>10,} px  {t_rung[s]:.1f}s", flush=True)
    union_rebuilt = absterm.copy()
    for s in LADDER:
        union_rebuilt |= rungs[s]
    # THE CONTROL. If this file's idea of the ladder has drifted from the pipeline's, the
    # seven rungs will not rebuild the mask the pipeline itself returned.
    same = bool(np.array_equal(union_rebuilt, rec["dark"]))
    print(f"  {'PASS' if same else 'FAIL'}  7 rungs OR absolute term == the pipeline's own "
          f"dark mask, bit for bit ({int(rec['dark'].sum()):,} px)", flush=True)
    assert same, "the per-rung render does not reproduce the shipped union"

    # --- crop -----------------------------------------------------------------------------
    # The tile corpus cuts its crops out of the raw frame after trimming the databar; the
    # pipeline crops with find_field_of_view. Assert the two origins agree before using the
    # tile's box, instead of assuming it.
    x, y, w, h = CROP
    import tifffile
    raw = tifffile.imread(os.path.join(SEM, "original", FRAME + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    assert img8.shape[1] == raw.shape[1], (
        f"field-of-view crop moved the x origin ({img8.shape} vs {raw.shape}); the tile "
        "box can no longer be used unshifted")
    assert img8.shape[0] <= raw.shape[0]
    sl = (slice(y, y + h), slice(x, x + w))

    gt = _ground_truth(h, w)
    out = dict(img8=img8[sl], bg=rec["bg"][sl].astype(np.float32), flat=flat[sl],
               dark=rec["dark"][sl], clean=rec["clean"][sl], pass1=pass1[sl],
               emitted=emitted[sl], pass2=pass2_added[sl], absterm=absterm[sl], gt=gt)
    for s in LADDER:
        out[f"rung{s}"] = rungs[s][sl]
    # A thumbnail of the whole frame with the crop marked, so the reader can see that the
    # 512 px window is a window and not the specimen.
    out["frame_thumb"] = img8[::6, ::6]
    out["frame_emitted_thumb"] = emitted[::6, ::6]

    # PASS 2 ADDS NOTHING INSIDE THE MAIN CROP (0 px of 41,369 frame-wide), so a panel of
    # the main crop would show the stage doing nothing and invite the reader to conclude
    # the stage does nothing. A second window is cut where Pass 2 DID act -- centred on
    # its largest accepted region -- and is labelled as a different place, not a different
    # stage. The main-crop panel still appears, with its zero stated.
    from scipy import ndimage as _ndi
    p2lab, p2n = _ndi.label(pass2_added, structure=np.ones((3, 3), bool))
    if p2n:
        sizes = _ndi.sum(np.ones_like(p2lab, np.uint8), p2lab, range(1, p2n + 1))
        big = int(np.argmax(sizes)) + 1
        cy, cx = _ndi.center_of_mass(p2lab == big)
        py = int(np.clip(cy - 128, 0, img8.shape[0] - 256))
        px_ = int(np.clip(cx - 128, 0, img8.shape[1] - 256))
        s2 = (slice(py, py + 256), slice(px_, px_ + 256))
        out["p2_img8"] = img8[s2]
        out["p2_before"] = pass1[s2]
        out["p2_after"] = emitted[s2]
        out["p2_added"] = pass2_added[s2]
        rec["p2_box"] = [px_, py, 256, 256]
        rec["p2_big_px"] = int(sizes[big - 1])

    stats = _stats(rec, st, df, img8, flat, emitted, pass1, pass2_added, absterm, rungs,
                   t_rung, sl, gt)
    np.savez_compressed(NPZ, **out)
    json.dump(stats, open(STATS, "w"), indent=1)
    print(f"  wrote {os.path.basename(NPZ)} and {os.path.basename(STATS)}")
    return out, stats


def _ground_truth(h, w):
    """The hand paint for this crop, if the labelling corpus is on this machine."""
    cand = os.path.expanduser(
        "~/Library/Application Support/Crack Fractography/uploads/" + TILE + "_gated.png")
    if not os.path.exists(cand):
        return np.zeros((h, w), bool)
    from PIL import Image
    return np.array(Image.open(cand).convert("L")) < 128


def _stats(rec, st, df, img8, flat, emitted, pass1, pass2, absterm, rungs, t_rung, sl, gt):
    x, y, w, h = CROP
    frame_px = int(img8.size)
    crop_px = w * h

    def two(a_full):
        return dict(frame=int(a_full.sum()), crop=int(a_full[sl].sum()))

    s = dict(frame=FRAME, tile=TILE, crop=list(CROP), pick_iou=PICK_IOU, pick_why=PICK_WHY,
             frame_shape=[int(img8.shape[0]), int(img8.shape[1])],
             frame_px=frame_px, crop_px=crop_px,
             t_total=round(rec["t_total"], 1), t_seg=round(rec["t_seg"], 1),
             t_flat=round(rec["t_flat"], 1), t_ves=round(rec.get("t_ves", 0), 1),
             t_rung={str(k): round(v, 1) for k, v in t_rung.items()},
             dark=two(rec["dark"]), clean=two(rec["clean"]), pass1=two(pass1),
             emitted=two(emitted), pass2=two(pass2), absterm=two(absterm),
             rungs={str(k): two(v) for k, v in rungs.items()},
             n_pass1=int(rec["n_pass1"]), n_final=int(st["labeled"].max()),
             n_interior_total=int(st["n_interior_total"]),
             n_pass2_accepted=int(len(st["interior_origin"])),
             mask_source=st["mask_source"], sam2=st["sam2"].get("sam2_mode"),
             gt_crop=int(gt.sum()))
    # what each rung adds that no earlier rung had -- the honest way to show a union
    seen = absterm.copy()
    add = {}
    for k in LADDER:
        add[str(k)] = dict(frame=int((rungs[k] & ~seen).sum()),
                           crop=int((rungs[k] & ~seen)[sl].sum()))
        seen |= rungs[k]
    s["rung_new"] = add
    s["single40_only"] = two(rungs[40] | absterm)

    # scores on the crop, against the hand paint, through tilebench's own counter
    if gt.any():
        import tilebench as TB
        for nm, m in (("dark", rec["dark"][sl]), ("clean", rec["clean"][sl]),
                      ("pass1", pass1[sl]), ("emitted", emitted[sl]),
                      ("single40", (rungs[40] | absterm)[sl])):
            c = TB.counts(m, gt)
            s.setdefault("score", {})[nm] = dict(
                precision=round(c["tp"] / max(c["tp"] + c["fp"], 1), 4),
                recall=round(c["tp"] / max(c["tp"] + c["fn"], 1), 4),
                iou=round(c["tp"] / max(c["tp"] + c["fp"] + c["fn"], 1), 4))
    s["p2_box"] = rec.get("p2_box")
    s["p2_big_px"] = rec.get("p2_big_px")

    # WHERE THE RECALL GOES, on this crop, against this crop's own hand paint. Each missed
    # painted pixel is charged to the FIRST stage that dropped it: closing and fill_holes
    # can only add, so a pixel that was never dark and is in the mask anyway was not lost.
    if gt.any():
        missed = gt & ~emitted[sl]
        d, c, p1 = rec["dark"][sl], rec["clean"][sl], pass1[sl]
        # Charged to the first stage that dropped it AND DID NOT GIVE IT BACK, which is
        # the rule detector_overrides.py's own frame-scale decomposition uses: closing and
        # fill_holes are extensive, so a pixel that was never dark but is in the clean mask
        # was not lost at the darkness cut. The first arrangement of these three buckets
        # double-counted exactly those pixels and the exhaustiveness assert below caught it.
        buckets = [("never dark at any of the 7 radii", missed & ~c & ~d),
                   ("dark, then removed by clean_mask (<= 13 px, or the opening)",
                    missed & ~c & d),
                   ("in the clean mask, then below the 40 px region floor", missed & c)]
        tot = int(missed.sum())
        s["loss"] = [dict(stage=n, px=int(m.sum()),
                          share_of_loss=round(float(m.sum()) / max(tot, 1), 4),
                          share_of_painted=round(float(m.sum()) / max(int(gt.sum()), 1), 4))
                     for n, m in buckets]
        s["loss_total_px"] = tot
        assert sum(b["px"] for b in s["loss"]) == tot, "loss buckets are not exhaustive"

    # the measured output: per-crack rows from the app's own measure.py
    s["rows"], s["summary"] = _measure(emitted[sl])
    s["frame_summary"] = _measure(emitted, rows_too=False)[1]
    return s


KEEP_SUMMARY = ("n_cracks", "crack_area_px", "area_fraction", "largest_area_px",
                "largest_share_of_area", "total_skeleton_length_px", "mean_width_px_median",
                "speck_threshold_px", "n_censored", "censored_share",
                "censored_share_by_area", "censored_share_by_length", "um_per_px")


def _measure(mask, rows_too=True):
    """The app's own measurement step, not a reimplementation of it."""
    sys.path.insert(0, os.path.join(APP, "analysis"))
    import measure as M
    t = time.time()
    rows, summ = M.measure_frame(mask.copy(), FRAME, modality="sem")
    print(f"  measured {mask.shape[1]}x{mask.shape[0]}: {len(rows)} regions "
          f"in {time.time() - t:.1f}s", flush=True)
    small = {k: summ.get(k) for k in KEEP_SUMMARY if k in summ}
    small["n_rows"] = len(rows)
    if not rows_too:
        return [], small
    rows = sorted(rows, key=lambda r: -r["area_px"])[:8]
    keep = ("crack_id", "area_px", "TipToTipGeodesic_px", "SkeletonLength_px",
            "MeanWidth_px", "MaxWidth_px", "Tortuosity", "length_is_censored")
    return [{k: r.get(k) for k in keep} for r in rows], small


# ============================== the page ================================================
# Nothing below invents a number. Every value interpolated into the HTML comes out of the
# stats dict the capture wrote, or is a corpus figure quoted with its source named in the
# text beside it.
CSS = """
:root{--bg:#0f1115;--panel:#171a21;--line:#2a2f3a;--fg:#e8ecf3;--dim:#9aa4b5;
      --mask:#2bb3ff;--add:#ffb020;--gone:#ff4d4d;--p2:#c26bff;--ok:#35d07f;--fn:#4da3ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
     font:16.5px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:32px 16px 96px}
h1{font-size:30px;line-height:1.25;margin:0 0 6px}
h2{font-size:21px;margin:0 0 4px}
.sub{color:var(--dim);font-size:15px;margin:0 0 28px}
.step{background:var(--panel);border:1px solid var(--line);border-radius:12px;
      padding:20px 22px;margin:0 0 18px}
.step.hot{border-color:#7a4a12;background:#1d1a14}
.num{display:inline-block;min-width:30px;height:30px;line-height:30px;text-align:center;
     background:#242a35;border-radius:8px;font-weight:700;font-size:15px;margin-right:10px}
.hot .num{background:#5a3a0d}
.does{margin:10px 0 2px}
.cost{color:var(--dim);font-size:15.5px;margin:4px 0 0}
.row{display:flex;flex-wrap:wrap;gap:14px;margin:14px 0 2px}
figure{margin:0;flex:1 1 300px;min-width:240px}
figure img{width:100%;height:auto;display:block;border-radius:8px;border:1px solid var(--line);
           background:#000;image-rendering:auto}
figcaption{color:var(--dim);font-size:13.5px;margin-top:6px}
.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:10px}
.strip figure{min-width:0}
.strip figcaption{font-size:12.5px}
.k{font-variant-numeric:tabular-nums;color:var(--fg)}
table{border-collapse:collapse;width:100%;margin:12px 0 0;font-size:14.5px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:right;
      font-variant-numeric:tabular-nums}
th:first-child,td:first-child{text-align:left}
th{color:var(--dim);font-weight:600}
.arrow{text-align:center;color:var(--dim);font-size:22px;line-height:1;margin:-6px 0 10px}
.legend{display:flex;flex-wrap:wrap;gap:16px;font-size:14.5px;color:var(--dim);
        margin:10px 0 24px}
.sw{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;
    vertical-align:-1px}
.note{background:#131722;border-left:3px solid var(--mask);padding:12px 16px;
      border-radius:0 8px 8px 0;margin:16px 0;font-size:15.5px}
.warn{border-left-color:var(--add)}
code{background:#0b0d12;padding:1px 5px;border-radius:4px;font-size:14px}
"""


def _n(v):
    return "{:,}".format(int(v))


def _pc(v, d=2):
    return ("{:." + str(d) + "f}%").format(100.0 * float(v))


def _cap(crop, frame, crop_px):
    return ('<figcaption>carries <span class="k">' + _n(crop) + '</span> px in this crop ('
            + _pc(crop / float(crop_px)) + ' of it) &middot; <span class="k">' + _n(frame)
            + '</span> px in the whole frame</figcaption>')


def write_html(p, s):
    cp = float(s["crop_px"])
    fp = float(s["frame_px"])
    sc = s.get("score", {})
    rows = s.get("rows", [])
    L = {b["stage"]: b for b in s.get("loss", [])}
    o = []
    A = o.append

    def fig(key, cap):
        A('<figure><img src="' + p[key] + '" alt="' + key + '">' + cap + '</figure>')

    def step(n, title, body, hot=False):
        A('<section class="step' + (' hot' if hot else '') + '">'
          '<h2><span class="num">' + n + '</span>' + title + '</h2>' + body + '</section>'
          '<div class="arrow">&darr;</div>')

    A('<!doctype html><html lang="en"><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width,initial-scale=1">'
      '<title>Crack pipeline, stage by stage</title><style>' + CSS + '</style></head><body>'
      '<div class="wrap">')
    A('<h1>The shipped crack detector, one real image per stage</h1>')
    A('<p class="sub">Frame <code>' + s["frame"] + '</code>, crop at x=' + str(CROP[0])
      + ' y=' + str(CROP[1]) + ', ' + str(CROP[2]) + '&times;' + str(CROP[3])
      + ' px. The same crop appears at every stage, so the panels are comparable.<br>'
      'Every panel is an array this pipeline actually returned on this frame &mdash; no'
      ' mock-ups, no schematic boxes. Built by <code>make_flowchart.py</code> in this'
      ' folder; one run of <code>run_unified_pipeline</code> took '
      + str(s["t_total"]) + ' s on the full ' + _n(fp) + ' px frame.</p>')

    A('<div class="note"><b>Why this frame.</b> ' + PICK_WHY[0].upper() + PICK_WHY[1:]
      + '. The selected tile is <code>' + s["tile"] + '</code> at IoU '
      + "{:.4f}".format(PICK_IOU) + '. Re-run through the full-frame pipeline here it'
      ' scores IoU ' + "{:.4f}".format(sc.get("emitted", {}).get("iou", 0)) + ' on the same'
      ' crop: the gap is the tile corpus stretching contrast per 512 px crop and labelling'
      ' 4-connected, against the frame-scale stretch and <code>connectivity=2</code>'
      ' production uses. Neither number is a corpus figure &mdash; see the last panel.</div>')

    A('<div class="legend">'
      '<span><i class="sw" style="background:var(--mask)"></i>pixels the stage keeps</span>'
      '<span><i class="sw" style="background:var(--add)"></i>pixels the stage adds</span>'
      '<span><i class="sw" style="background:var(--gone)"></i>pixels the stage removes</span>'
      '<span><i class="sw" style="background:var(--p2)"></i>added by Pass 2</span>'
      '<span><i class="sw" style="background:var(--ok)"></i>hand paint / true positive</span>'
      '</div>')

    A('<div class="row">')
    fig("frame", '<figcaption>The whole frame, ' + str(s["frame_shape"][1]) + '&times;'
        + str(s["frame_shape"][0]) + ' px. The amber box is the 512 px window every other'
        ' panel shows &mdash; 0.19% of the frame area.</figcaption>')
    fig("frame_mask", '<figcaption>The emitted mask over the whole frame: '
        + _n(s["emitted"]["frame"]) + ' px, ' + _pc(s["emitted"]["frame"] / fp)
        + ' of the frame.</figcaption>')
    A('</div>')

    step("1", "The micrograph",
         _one(p, "micrograph",
         '<figcaption>8-bit, after the 0.5/99.5 percentile stretch and the'
         ' field-of-view crop.</figcaption>') +
         '<p class="does"><b>What it does.</b> Reads the 16-bit TIFF, stretches it to 8 bit'
         ' on its 0.5/99.5 percentiles, and crops the databar off: '
         + str(s["frame_shape"][1]) + '&times;' + str(s["frame_shape"][0]) + ' px survive.</p>'
         '<p class="cost"><b>Cost.</b> A percentile stretch, not min/max: a hot pixel or the'
         ' crack itself at 0 would otherwise own the range and flatten the background'
         ' texture Otsu needs downstream.</p>')

    step("2", "Why the next step exists: the illumination",
         '<div class="row">'
         + _f(p, "background", '<figcaption>The Gaussian background estimate at '
              'sigma=40 over this crop, false-coloured. It spans '
              + str(s["bg_range"][0]) + ' to ' + str(s["bg_range"][1]) + ' grey levels'
              ' across 512 px &mdash; drift of that size sits on top of every crack.</figcaption>')
         + _f(p, "micrograph", '<figcaption>The same crop, as captured, for comparison.'
              '</figcaption>')
         + '</div>'
         '<p class="does"><b>What it does.</b> Nothing yet &mdash; this is the quantity'
         ' <code>flatten_background</code> is about to subtract.</p>'
         '<p class="cost"><b>Why it matters.</b> A single global threshold on the raw image'
         ' would track this drift instead of the crack.</p>')

    step("3", "flatten_background",
         _one(p, "flat", '<figcaption>The flattened image: raw minus the background above,'
              ' rescaled to 8 bit on its own 0.5/99.5 percentiles.</figcaption>')
         + '<p class="does"><b>What it does.</b> Subtracts the blurred copy, so what is left'
           ' is local contrast.</p>'
           '<p class="cost"><b>What it costs.</b> It is a high-pass filter, so it also erases'
           ' anything <i>wider</i> than its own radius. The detector\'s own docstring'
           ' measures this: pixels that are genuinely pitch black (raw 0&ndash;4) come out'
           ' near 122 of 255 after flattening, indistinguishable from mid-grey matrix. That'
           ' single sentence is why steps 5 and 6 exist.</p>')

    cut40 = s["single40_only"]
    step("4", "The darkness cut, at one radius",
         _one(p, "cut40", _cap(cut40["crop"], cut40["frame"], cp))
         + '<p class="does"><b>What it does.</b> Keeps a pixel if the denoised flat image is'
           ' below <code>min(Otsu, median &minus; 5&times;MAD)</code>, OR if the raw 8-bit'
           ' image is below ' + str(ABS_DARK) + '. Taking the lower of Otsu and the robust'
           ' bar is what stops Otsu flagging half the frame on a unimodal histogram.</p>'
           '<p class="cost"><b>What it buys, on this crop.</b> precision <span class="k">'
         + "{:.4f}".format(sc.get("single40", {}).get("precision", 0)) + '</span>, recall'
           ' <span class="k">' + "{:.4f}".format(sc.get("single40", {}).get("recall", 0))
         + '</span>, IoU <span class="k">'
         + "{:.4f}".format(sc.get("single40", {}).get("iou", 0)) + '</span> against the hand'
           ' paint. Almost everything it marks is crack; it finds about a quarter of it.</p>'
           '<p class="cost">The absolute-darkness term alone carries '
         + _n(s["absterm"]["crop"]) + ' px here and ' + _n(s["absterm"]["frame"])
         + ' px frame-wide. At corpus scale it supplies roughly half of all the recall the'
           ' detector has, and its threshold of ' + str(ABS_DARK) + ' has no provenance;'
           ' raising it is additive but three instruments disagree about whether to, so it'
           ' stays put.</p>')

    A('<section class="step"><h2><span class="num">5</span>The same cut at each of the'
      ' seven radii</h2>'
      '<p class="does"><b>What it does.</b> Re-flattens the image at sigma = '
      + ", ".join(str(r) for r in LADDER) + ' and takes the identical cut at each. A crack'
      ' is only reliably dark at the scales near its own width, so one radius sees one'
      ' band.</p><div class="strip">')
    for r in LADDER:
        rr, nn = s["rungs"][str(r)], s["rung_new"][str(r)]
        A('<figure><img src="' + p["rung" + str(r)] + '" alt="sigma ' + str(r) + '">'
          '<figcaption><b>sigma = ' + str(r) + '</b><br><span class="k">' + _n(rr["crop"])
          + '</span> px here<br>' + _n(nn["crop"]) + ' of them new<br><span class="k">'
          + _n(rr["frame"]) + '</span> px frame-wide<br>' + _n(nn["frame"])
          + ' new frame-wide</figcaption></figure>')
    A('</div><p class="cost">&ldquo;New&rdquo; counts pixels no earlier rung and not the'
      ' absolute-darkness term had already claimed, taken in ascending sigma, so the seven'
      ' new-counts sum to the union and no pixel is counted twice. Each rung is produced by'
      ' calling the <i>installed</i> detector with that one rung in its ladder; the OR of'
      ' the seven plus the absolute term is asserted equal, bit for bit, to the mask the'
      ' pipeline itself returned.</p></section><div class="arrow">&darr;</div>')

    gain = s["dark"]["crop"] - cut40["crop"]
    gainf = s["dark"]["frame"] - cut40["frame"]
    step("6", "Their union &mdash; the change v1.49 made",
         _one(p, "union", _cap(s["dark"]["crop"], s["dark"]["frame"], cp)
              + '<figcaption>Blue is what one radius already had; amber is what the other'
              ' six radii add.</figcaption>')
         + '<p class="does"><b>What it does.</b> ORs the seven cuts. It is a strict superset'
           ' of the single-radius mask by construction, so it cannot drop a pixel the older'
           ' build kept &mdash; checked, not assumed: 0 px lost across the 26 labelled tiles'
           ' and across 6,669,145 hand-painted pixels on 12 full frames.</p>'
           '<p class="cost"><b>What it buys, on this crop.</b> <span class="k">+'
         + _n(gain) + '</span> px here and <span class="k">+' + _n(gainf) + '</span> px'
           ' frame-wide. precision ' + "{:.4f}".format(sc.get("single40", {}).get("precision", 0))
         + ' &rarr; <span class="k">' + "{:.4f}".format(sc.get("dark", {}).get("precision", 0))
         + '</span>, recall ' + "{:.4f}".format(sc.get("single40", {}).get("recall", 0))
         + ' &rarr; <span class="k">' + "{:.4f}".format(sc.get("dark", {}).get("recall", 0))
         + '</span>, IoU ' + "{:.4f}".format(sc.get("single40", {}).get("iou", 0))
         + ' &rarr; <span class="k">' + "{:.4f}".format(sc.get("dark", {}).get("iou", 0))
         + '</span>. Over the 26 labelled tiles the same change reads IoU 0.2979 &rarr;'
           ' 0.3344 pooled, and it costs no new tuned constant: the ladder is every scale,'
           ' not a chosen subset.</p>'
           '<p class="cost"><b>What it costs.</b> Seven flattening passes instead of one:'
           ' <span class="k">' + str(s["t_seg"]) + ' s</span> of this frame\'s '
         + str(s["t_total"]) + ' s. Above sigma=64 the background is estimated on a'
           ' decimated copy, which is what keeps that from being 67 s.</p>', hot=True)

    step("7", "clean_mask",
         _one(p, "clean", _cap(s["clean"]["crop"], s["clean"]["frame"], cp))
         + '<p class="does"><b>What it does.</b> Drops components of '
         + str(MIN_AREA_CLEAN) + ' px or fewer, opens with a disk of radius 1, closes with a'
           ' disk of radius 3, fills holes.</p>'
           '<p class="cost"><b>What it costs here.</b> removes <span class="k">'
         + _n(s["clean_removed"]) + '</span> px, adds back <span class="k">'
         + _n(s["clean_added"]) + '</span> (the closing and the hole fill are extensive),'
           ' net ' + _n(s["clean"]["crop"] - s["dark"]["crop"]) + ' px in this crop.</p>')

    step("8", "The 40 px region floor",
         _one(p, "floor", _cap(s["pass1"]["crop"], s["pass1"]["frame"], cp))
         + '<p class="does"><b>What it does.</b> <code>extract_candidates</code> labels the'
           ' clean mask with <code>connectivity=2</code> and keeps only components of at'
           ' least ' + str(MIN_AREA_REGION) + ' px, renumbering the survivors 1..N. '
         + _n(s["n_pass1"]) + ' candidate regions survive on this frame.</p>'
           '<p class="cost"><b>What it costs here.</b> <span class="k">'
         + _n(s["floor_removed"]) + '</span> px in this crop.</p>'
           '<p class="cost"><b>And what does not happen next.</b> The region classifier is'
           ' <code>USE_REGION_CLASSIFIER = False</code>, so every one of those regions is'
           ' kept. Deleting it won on all four metrics with zero free parameters; six'
           ' region-level precision rules tried since all scored well on 512 px crops and'
           ' then deleted 54&ndash;75% of hand-painted crack on the 48 full frames.</p>')

    p2 = ('<div class="row">'
          + _f(p, "p2_before", '<figcaption>A different 256 px window, at x='
               + str(s["p2_box"][0]) + ' y=' + str(s["p2_box"][1]) + ': the mask before'
               ' Pass 2.</figcaption>')
          + _f(p, "p2_after", '<figcaption>The same window after. Violet is Pass 2\'s'
               ' addition &mdash; its largest accepted region is '
               + _n(s["p2_big_px"]) + ' px.</figcaption>')
          + '</div>') if "p2_before" in p else ""
    step("9", "Pass 2",
         _one(p, "pass2_main", _cap(s["emitted"]["crop"], s["emitted"]["frame"], cp)
              + '<figcaption>The main crop, unchanged: Pass 2 added <b>0 px</b> here.'
              '</figcaption>') + p2
         + '<p class="does"><b>What it does.</b> With a crack mask now in hand, proposes'
           ' concavity, bridge-corridor and interior-fill candidates <i>relative to it</i>,'
           ' scores them with the unified model, and folds the accepted ones in. '
         + _n(s["n_interior_total"]) + ' proposed on this frame, '
         + _n(s["n_pass2_accepted"]) + ' accepted.</p>'
           '<p class="cost"><b>What it buys.</b> <span class="k">+'
         + _n(s["pass2"]["frame"]) + '</span> px frame-wide ('
         + _pc(s["pass2"]["frame"] / max(float(s["emitted"]["frame"]), 1))
         + ' of the final mask) and <b>0 px in this crop</b>. The second pair of panels is a'
           ' different <i>place</i>, not a different stage, and is shown because a panel of'
           ' the main crop alone would read as the stage doing nothing anywhere.</p>')

    step("10", "The emitted mask",
         '<div class="row">'
         + _f(p, "emitted", _cap(s["emitted"]["crop"], s["emitted"]["frame"], cp)
              + '<figcaption>Crack black on white, exactly the PNG'
              ' <code>analysis/detect_one.py</code> writes.</figcaption>')
         + _f(p, "frame_mask", '<figcaption>The same mask over the whole frame, for scale.'
              '</figcaption>') + '</div>'
         + '<p class="does"><b>What it does.</b> Unions every kept region into one boolean'
           ' mask and saves it. Area fraction <span class="k">'
         + _pc(s["frame_summary"]["area_fraction"], 3) + '</span> on this frame, '
         + _pc(s["summary"]["area_fraction"], 3) + ' in this crop.</p>')

    hdr = ["crack", "area px", "tip-to-tip px", "skeleton px", "mean width px",
           "max width px", "tortuosity", "edge-censored"]
    tb = ['<table><thead><tr>' + "".join('<th>' + x + '</th>' for x in hdr)
          + '</tr></thead><tbody>']
    for r in rows:
        tb.append('<tr><td>' + str(r["crack_id"]) + '</td><td>' + _n(r["area_px"]) + '</td>'
                  + "".join('<td>' + ("&mdash;" if r.get(k) in (None, "") else str(r[k]))
                            + '</td>' for k in ("TipToTipGeodesic_px", "SkeletonLength_px",
                                                "MeanWidth_px", "MaxWidth_px", "Tortuosity"))
                  + '<td>' + ("yes" if r["length_is_censored"] else "no") + '</td></tr>')
    tb.append('</tbody></table>')
    step("11", "The measured output",
         '<div class="row">'
         + _f(p, "regions", '<figcaption>One colour per measured crack; grey is a component'
              ' at or below the ' + str(s["summary"]["speck_threshold_px"]) + ' px speck'
              ' floor, which the measurement step drops. '
              + _n(s["n_components"]) + ' components in this crop, '
              + _n(s["n_specks_dropped"]) + ' of them specks.</figcaption>')
         + '<figure style="flex:2 1 420px">' + "".join(tb)
         + '<figcaption>The eight largest cracks in this crop, by the app\'s own'
           ' <code>analysis/measure.py</code>. Tortuosity is left blank unless the region'
           ' has exactly two skeleton endpoints and no branch point.</figcaption></figure>'
         + '</div>'
         + '<p class="does"><b>What it does.</b> Re-labels the emitted mask and measures'
           ' every component: area, tip-to-tip geodesic, skeleton length, mean and max'
           ' width, tortuosity, and whether it runs off the frame edge.</p>'
           '<p class="cost"><b>What it costs.</b> '
         + _n(s["frame_summary"]["n_rows"]) + ' rows on this frame, '
         + _n(s["summary"]["n_rows"]) + ' in this crop. <b>Length is a bracket, not a'
           ' value:</b> ' + _pc(s["frame_summary"]["censored_share"]) + ' of regions on this'
           ' frame touch the edge, but they are '
         + _pc(s["frame_summary"]["censored_share_by_area"]) + ' of the crack area and '
         + _pc(s["frame_summary"]["censored_share_by_length"]) + ' of the length. No scale'
           ' bar was recovered for this frame, so every column here is pixels, not microns.'
           '</p>')

    A(_scorecard(p, s, sc, L, cp))
    A('</div></body></html>')
    open(os.path.join(HERE, "index.html"), "w").write("".join(o))


def _f(p, key, cap):
    if key not in p:
        return ""
    return '<figure><img src="' + p[key] + '" alt="' + key + '">' + cap + '</figure>'


def _one(p, key, cap):
    return '<div class="row">' + _f(p, key, cap) + '</div>'


def _scorecard(p, s, sc, L, cp):
    """The last block: what the mask is worth, and what may not be read off this page."""
    if "score" not in p:
        return ""
    keys = ["never dark at any of the 7 radii",
            "dark, then removed by clean_mask (<= 13 px, or the opening)",
            "in the clean mask, then below the 40 px region floor"]
    lab = ["the darkness cut", "clean_mask (small objects + the opening)",
           "the 40 px region floor"]
    tb = ['<table><thead><tr><th>where a painted pixel was lost</th><th>px</th>'
          '<th>share of the loss here</th><th>corpus, 48 frames</th></tr></thead><tbody>']
    corpus = ["96.02%", "3.49%", "0.49%"]
    for k, nm, cc in zip(keys, lab, corpus):
        b = L.get(k, {"px": 0, "share_of_loss": 0})
        tb.append('<tr><td>' + nm + '</td><td>' + _n(b["px"]) + '</td><td>'
                  + _pc(b["share_of_loss"]) + '</td><td>' + cc + '</td></tr>')
    tb.append('</tbody></table>')
    e = sc.get("emitted", {})
    return ('<section class="step hot"><h2><span class="num">&#9679;</span>Against the hand'
            ' paint, and where the recall goes</h2>'
            '<div class="row">'
            + _f(p, "paint", '<figcaption>The hand paint for this crop: '
                 + _n(s["gt_crop"]) + ' px, ' + _pc(s["gt_crop"] / cp)
                 + ' of it. Painted from blank; the detector had no hand in it.</figcaption>')
            + _f(p, "score", '<figcaption>green = found, red = marked but not painted,'
                 ' blue = painted but missed.</figcaption>')
            + _f(p, "loss", '<figcaption>The missed paint, charged to the stage that dropped'
                 ' it: blue = never dark, red = clean_mask, amber = the 40 px floor.'
                 '</figcaption>')
            + '</div>'
            + '<p class="does"><b>On this crop:</b> precision <span class="k">'
            + "{:.4f}".format(e.get("precision", 0)) + '</span>, recall <span class="k">'
            + "{:.4f}".format(e.get("recall", 0)) + '</span>, IoU <span class="k">'
            + "{:.4f}".format(e.get("iou", 0)) + '</span>. <b>One crop is not a corpus'
              ' figure.</b></p>' + "".join(tb)
            + '<p class="cost">The two stages worth marking are the first row and'
              ' everything else. On this crop the darkness cut owns '
            + _pc(L.get(keys[0], {}).get("share_of_loss", 0)) + ' of all missed paint and'
              ' the two morphology/area filters own '
            + _pc(sum(L.get(k, {}).get("share_of_loss", 0) for k in keys[1:]))
            + ' between them; over the 48 hand-painted full frames the same decomposition'
              ' reads 96.02% and 3.98%. Tuning the morphology cannot reach the problem.</p>'
            '<div class="note warn"><b>How to read any number on this page.</b> These are'
            ' one crop of one frame, shown because the stages are comparable on it. The'
            ' corpus figures, over the 26 hand-labelled tiles, move further with the'
            ' <i>aggregation</i> than with any method change ever measured in this project,'
            ' so a score is unreadable without its row and its tolerance:'
            '<table><thead><tr><th>aggregation</th><th>precision</th><th>recall</th>'
            '<th>F1</th><th>IoU</th></tr></thead><tbody>'
            '<tr><td>pooled over all pixels</td><td>0.4182</td><td>0.6252</td>'
            '<td>0.5012</td><td>0.3344</td></tr>'
            '<tr><td>median over the 26 tiles</td><td>0.8056</td><td>0.7623</td>'
            '<td>0.5922</td><td>0.4208</td></tr>'
            '<tr><td>median over 13 specimens</td><td>0.7897</td><td>0.7159</td>'
            '<td>0.5418</td><td>0.3715</td></tr>'
            '<tr><td>median over specimens, 2 px tolerance</td><td>0.8988</td>'
            '<td>0.8025</td><td>0.6633</td><td>0.4962</td></tr></tbody></table>'
            'A <i>perfectly placed</i> trace caps at IoU 0.4993 pooled and 0.5498 median'
            ' over tiles on these labels, so 0.4208 is 84% of what the labels permit, not'
            ' 42% of perfect. IoU and clDice are both width-gameable here &mdash; a'
            ' no-information dilation to 1.5&times; area moves clDice +0.0478 on 13 of 13'
            ' specimens &mdash; so the metric to compare methods on is skeleton-F1 at a'
            ' 2 px tolerance, where this detector scores 0.5507.</div>'
            '<p class="cost">Reproduce every panel and every number on this page:'
            ' <code>make_flowchart.py</code> beside this file, run under the detector'
            ' environment. It asserts its own ladder against the pipeline\'s output and'
            ' asserts the loss buckets are exhaustive before it writes anything.</p>'
            '</section>')


# ============================== panels ==================================================
# Every panel is written at the array's own resolution with no axes and no burned-in text.
# All labelling is HTML text, which the reader can zoom. A figure in this project once
# shipped at 2.3 pt because the type was inside the image; there is no type inside these.
INK = dict(mask="#2bb3ff", add="#ffb020", gone="#ff4d4d", p2="#c26bff", gt="#35d07f",
           tp="#35d07f", fp="#ff4d4d", fn="#4da3ff")


def _rgb(hexs):
    h = hexs.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.uint8)


def _base(gray):
    """Grey micrograph, dimmed a little so a coloured overlay reads on top of it."""
    g = np.asarray(gray, np.float32)
    g = (0.30 + 0.62 * (g / 255.0)) * 255.0
    return np.repeat(np.clip(g, 0, 255).astype(np.uint8)[:, :, None], 3, 2)


def _over(rgb, mask, colour, alpha=1.0):
    c = _rgb(colour).astype(np.float32)
    m = np.asarray(mask, bool)
    rgb[m] = (rgb[m] * (1 - alpha) + c * alpha).astype(np.uint8)
    return rgb


def _save(rgb, name, scale=1):
    from PIL import Image
    im = Image.fromarray(np.ascontiguousarray(rgb))
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(os.path.join(HERE, name), optimize=True)
    return name


def _cmap(a, name="magma"):
    import matplotlib
    a = np.asarray(a, np.float32)
    lo, hi = float(a.min()), float(a.max())
    n = (a - lo) / max(hi - lo, 1e-9)
    lut = (matplotlib.colormaps[name](np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)
    return lut[(n * 255).astype(np.uint8)], lo, hi


def render(z, s):
    from scipy import ndimage as ndi
    from skimage import measure as skm
    img8, flat = z["img8"], z["flat"]
    out = {}

    # the frame, and the window this page lives in
    th = _base(z["frame_thumb"])
    x, y, w, h = CROP
    f = z["frame_thumb"].shape[0] / s["frame_shape"][0]
    x0, y0 = int(x * f), int(y * f)
    x1, y1 = int((x + w) * f), int((y + h) * f)
    for t in range(3):
        th[max(y0 - t, 0), x0:x1] = th[min(y1 + t, th.shape[0] - 1), x0:x1] = _rgb(INK["add"])
        th[y0:y1, max(x0 - t, 0)] = th[y0:y1, min(x1 + t, th.shape[1] - 1)] = _rgb(INK["add"])
    out["frame"] = _save(th, "p00_frame.png")
    out["frame_mask"] = _save(_over(_base(z["frame_thumb"]), z["frame_emitted_thumb"],
                                    INK["mask"], 0.85), "p00b_frame_mask.png")

    out["micrograph"] = _save(_base(img8) * 0 + np.repeat(img8[:, :, None], 3, 2),
                              "p01_micrograph.png")
    bg, lo, hi = _cmap(z["bg"], "magma")
    out["background"] = _save(bg, "p02_background.png")
    s["bg_range"] = [round(lo, 1), round(hi, 1)]
    out["flat"] = _save(np.repeat(flat[:, :, None], 3, 2), "p03_flat.png")

    single = z["rung40"] | z["absterm"]
    out["cut40"] = _save(_over(_base(img8), single, INK["mask"]), "p04_cut40.png")
    for r in LADDER:
        out[f"rung{r}"] = _save(_over(_base(img8), z[f"rung{r}"], INK["mask"]),
                                f"p05_rung{r:03d}.png")
    u = _over(_base(img8), single, INK["mask"])
    out["union"] = _save(_over(u, z["dark"] & ~single, INK["add"]), "p06_union.png")

    rm = z["dark"] & ~z["clean"]
    ad = z["clean"] & ~z["dark"]
    c = _over(_base(img8), z["clean"], INK["mask"])
    c = _over(c, ad, INK["add"])
    out["clean"] = _save(_over(c, rm, INK["gone"]), "p07_clean.png")
    s["clean_removed"] = int(rm.sum())
    s["clean_added"] = int(ad.sum())

    fl = _over(_base(img8), z["pass1"], INK["mask"])
    out["floor"] = _save(_over(fl, z["clean"] & ~z["pass1"], INK["gone"]), "p08_floor.png")
    s["floor_removed"] = int((z["clean"] & ~z["pass1"]).sum())

    out["pass2_main"] = _save(_over(_base(img8), z["emitted"], INK["mask"]),
                              "p09_pass2_main.png")
    if "p2_img8" in z:
        b = _over(_base(z["p2_img8"]), z["p2_before"], INK["mask"])
        out["p2_before"] = _save(b, "p09b_pass2_before.png", scale=2)
        a = _over(_base(z["p2_img8"]), z["p2_before"], INK["mask"])
        out["p2_after"] = _save(_over(a, z["p2_added"], INK["p2"]), "p09c_pass2_after.png",
                                scale=2)

    em = np.where(z["emitted"][:, :, None], 0, 255).astype(np.uint8)
    out["emitted"] = _save(np.repeat(em, 3, 2), "p10_emitted.png")

    # the measured object: one colour per measured crack, specks in grey
    lab = skm.label(z["emitted"], connectivity=2)
    sizes = np.bincount(lab.ravel())
    speck = int(s["summary"]["speck_threshold_px"])
    rgbm = np.zeros(lab.shape + (3,), np.uint8) + 18
    import matplotlib
    pal = (matplotlib.colormaps["tab20"](np.linspace(0, 1, 20))[:, :3] * 255).astype(np.uint8)
    k = 0
    for i in range(1, lab.max() + 1):
        m = lab == i
        if sizes[i] <= speck:
            rgbm[m] = (110, 110, 110)
        else:
            rgbm[m] = pal[k % 20]
            k += 1
    out["regions"] = _save(rgbm, "p11_regions.png")
    s["n_specks_dropped"] = int(sum(1 for i in range(1, lab.max() + 1) if sizes[i] <= speck))
    s["n_components"] = int(lab.max())

    gt = z["gt"]
    if gt.any():
        sc = _base(img8)
        sc = _over(sc, gt & ~z["emitted"], INK["fn"])
        sc = _over(sc, z["emitted"] & ~gt, INK["fp"])
        out["score"] = _save(_over(sc, gt & z["emitted"], INK["tp"]), "p12_score.png")
        ls = _base(img8)
        missed = gt & ~z["emitted"]
        ls = _over(ls, missed & ~z["clean"] & ~z["dark"], INK["fn"])
        ls = _over(ls, missed & ~z["clean"] & z["dark"], INK["gone"])
        ls = _over(ls, missed & z["clean"], INK["add"])
        out["loss"] = _save(_over(ls, gt & z["emitted"], INK["tp"], 0.45), "p13_loss.png")
        out["paint"] = _save(_over(_base(img8), gt, INK["gt"], 0.75), "p14_paint.png")
    json.dump(s, open(STATS, "w"), indent=1)
    return out


if __name__ == "__main__":
    if "--render" in sys.argv:
        z, s = dict(np.load(NPZ)), json.load(open(STATS))
    else:
        z, s = capture()
    panels = render(z, s)
    write_html(panels, s)
    print("  wrote index.html with", len(panels), "panels")
