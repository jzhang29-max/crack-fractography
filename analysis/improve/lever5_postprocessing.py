"""LEVER 5 -- post-processing and geometry, measured against the 26 hand-labelled tiles.

Everything here scores through analysis/tilebench.py. Nothing writes to the archived
repos or to the uploads directory.

RESULT (full 26 tiles, held-out, selected leave-one-specimen-out)
-----------------------------------------------------------------
                            precision  recall     IoU       F1    overfit gap
  shipped detector            0.3378   0.3696   0.2143   0.3530     +0.0000
  mad_k 5.0 -> 2.5 (known best)0.3383  0.4460   0.2382   0.3847     +0.0086
  >> closing disk(31) only     0.3626   0.4511   0.2516   0.4020     +0.0016   <<
  mad_k x closing (2 params)   0.3393   0.4615   0.2430   0.3910     +0.0282
  mad_k x close x dil x elong  0.7073   0.4883   0.4063   0.5778     +0.0496

Replacing clean_mask's close_radius=3 with a disk(31) closing of the FINAL mask, at the
shipped mad_k, raises all four metrics and beats the known-best mad_k relaxation on all
four, with one free parameter and an overfit gap of +0.0016 (12 of 13 LOSO folds picked
r=31, the 13th picked r=39). The radius curve has an interior optimum -- it turns over
at r=31 and is clearly worse by r=63 -- so this is not a grid-edge artefact.

READ THE QUALIFICATION BEFORE QUOTING THE NUMBER
------------------------------------------------
Closing improves 8 of 13 specimens, leaves 4 unchanged and REGRESSES 1
(260622_316_amb_b3, -0.0373). But the pooled metric is area-weighted and 92% of the
pooled gain is a single specimen, 260708_316_H_b2, whose crack the pipeline splits into
4 fragments: closing takes it from IoU 0.4079 to 0.8811. jackknife() prints this --
drop any other specimen and the gain stays at +0.037 to +0.039; drop that one and it
falls to +0.0065. So the mechanism is real and is exactly the one Lever 5 names
(a fragmented crack loses its gaps as FN), but only one specimen in 13 is badly
fragmented, and that specimen sets the headline.

The 0.4063 row is worse than it looks: 93.9% of all false-positive pixels at the shipped
settings are one off-specimen void on MAR_H_HIP_CBS_0002, and the elongation filter in
that row exists to delete it. Drop MAR_H_HIP from the corpus and the shipped detector
already scores P 0.8783 / IoU 0.3414, and that row falls to +0.0412. Drop both
pathological specimens and every post-processing gain collapses to +0.003..+0.010.

WHAT IS DETECTION AND WHAT IS METRIC GAMING
-------------------------------------------
Closing is detection-ish: it is width-preserving on a straight stroke (test_closing_
preserves_width), and the pixels it adds land on crack 62.0% of the time against a base
precision of 33.8%. Dilation is NOT: the human's median stroke is 8.71 px and the shipped
prediction is ALREADY 10.20 px, i.e. 1.17x WIDER, so there is no stroke to match;
dilate(3) pushes it to 16.00 px (1.84x the human) and still gains IoU, because at
precision 0.88 / recall 0.36 on the clean subset, over-painting is nearly free. Report
dilation as a metric gain only. Neither operator discovers anything: baseline touches
33 of 216 GT components and 64.9% of GT area, dilate(4) touches 34 and 65.1%,
closing touches 33 and 64.9%.

HOW TO REPRODUCE
----------------
    cd <a scratch dir>            # the scratchpad root shadows imports
    <sem-crack-detector/.venv/bin/python> -B lever5_postprocessing.py --all

FAST PATH
---------
flatten_background / gaussian / frangi depend only on img8, not on mad_k and not on any
clean_mask constant, so they are cached once per tile. verify_fast_path() proves the
cached path is byte-identical to crackpipe.predict at the shipped settings; if that
assertion ever fails, every number below is unreadable.
"""
import os, sys, time, pickle, itertools, argparse

import numpy as np
from scipy import ndimage as ndi
from skimage import filters, morphology, measure, draw

ANALYSIS = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis"
if ANALYSIS not in sys.path:
    sys.path.insert(0, ANALYSIS)
import tilebench as TB            # noqa: E402  THE scorer -- do not write another one
import crackpipe as CP            # noqa: E402
import detect_cracks as D         # noqa: E402  (crackpipe puts sem-crack-detector/code on the path)

MADS = [2.5, 3.0, 3.5, 4.0, 5.0]
# closing radii run past the optimum on purpose: r=31 is the peak and r=63 is clearly
# worse, which is the only way to show the pick is interior and not a grid edge.
CLS, DLS, ELS = [0, 3, 7, 11, 15, 19, 25, 31, 39, 49, 63], [0, 1, 2, 3, 4, 5], [1.0, 2.0]
SHIPPED_KEY = "mad5.0_cl0_dl0_el1.0"
RECOMMENDED = dict(mad_k=5.0, close_r=31, elong_min=1.0, dilate_r=0)

# ~116 MB of cached intermediates -- kept OUT of the repo directory on purpose.
CACHE = os.path.join(os.environ.get("TMPDIR", "/tmp"), "lever5_stagecache.pkl")


# ----------------------------------------------------------------------------- fast path
def stagecache(tiles, path=CACHE):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    out = {}
    for i, t in enumerate(tiles, 1):
        flat = D.flatten_background(t["img8"], sigma=40)
        smooth = filters.gaussian(flat, sigma=1.0, preserve_range=True)
        med = float(np.median(smooth))
        out[t["frame"]] = dict(
            flat=flat, smooth=smooth, ves=D.compute_vesselness(flat),
            otsu=float(filters.threshold_otsu(smooth)), med=med,
            mad=float(np.median(np.abs(smooth - med)) * 1.4826))
        print(f"  staged [{i}/{len(tiles)}] {t['frame']}", flush=True)
    with open(path, "wb") as f:
        pickle.dump(out, f, protocol=4)
    return out


def darkmask(t, S, mad_k=5.0, absolute_dark=10):
    s = S[t["frame"]]
    return (s["smooth"] < min(s["otsu"], s["med"] - mad_k * s["mad"])) | (t["img8"] < absolute_dark)


def clean(mask, min_area=13, open_radius=1, close_radius=3, fill_holes=True):
    """detect_cracks.clean_mask with every constant exposed and fill_holes optional.
    Defaults are the shipped ones. radius 0 skips the step (disk(0) is a no-op anyway)."""
    if min_area:
        mask = morphology.remove_small_objects(mask, max_size=min_area)
    if open_radius:
        mask = morphology.opening(mask, morphology.disk(open_radius))
    if close_radius:
        mask = morphology.closing(mask, morphology.disk(close_radius))
    if fill_holes:
        mask = ndi.binary_fill_holes(mask)
    return mask


def prob_from_clean(t, S, cleanmask, feat_min_area=40):
    s = S[t["frame"]]
    lab, _ = ndi.label(cleanmask)
    labeled, df = D.region_features_from_labeled(lab, s["flat"], s["ves"], min_area_px=feat_min_area)
    if not len(df):
        return np.zeros(labeled.shape, np.float32)
    p = CP.CLF.predict_proba(CP.SCALER.transform(df[CP.FEATS].values))[:, 1]
    pm = np.zeros(int(labeled.max()) + 1, np.float32)
    for l, v in zip(df["Label"].values, p):
        pm[int(l)] = v
    return pm[labeled] * (labeled > 0)


def predict(t, S, mad_k=5.0, thr=None, **cleankw):
    return prob_from_clean(t, S, clean(darkmask(t, S, mad_k=mad_k), **cleankw)) >= (thr or CP.THR)


def verify_fast_path():
    """The cached path must be byte-identical to the real pipeline, or nothing below counts."""
    tiles = TB.load(); S = stagecache(tiles)
    bad = [t["frame"] for t in tiles if not np.array_equal(predict(t, S), CP.predict(t["img8"]))]
    print(f"fast-path verify: {len(tiles)-len(bad)}/{len(tiles)} tiles byte-identical to CP.predict")
    assert not bad, bad
    return True


# -------------------------------------------------------------- post-classifier operators
def close(m, r):      return morphology.closing(m, morphology.disk(r)) if r else m
def dilate(m, d):     return morphology.dilation(m, morphology.disk(d)) if d else m
def erode(m, d):      return morphology.erosion(m, morphology.disk(d)) if d else m
def rso(m, a):        return morphology.remove_small_objects(m, max_size=a) if a else m
def fill(m, on=True): return ndi.binary_fill_holes(m) if on else m


def _compwidth(m):
    lab, n = ndi.label(m)
    if n == 0:
        return lab, np.zeros(1)
    dt = ndi.distance_transform_edt(m); sk = morphology.skeletonize(m)
    w = np.zeros(n + 1)
    for i in range(1, n + 1):
        s = sk & (lab == i)
        w[i] = 2 * np.median(dt[s if s.any() else (lab == i)])
    return lab, w


def drop_fat(m, wmax):
    """Drop components whose median stroke width exceeds wmax. A crack is thin; the
    off-specimen void on MAR_H_HIP_CBS_0002 has a median stroke width of 159 px."""
    if not np.isfinite(wmax) or not m.any():
        return m
    lab, w = _compwidth(m)
    keep = np.where(w <= wmax)[0]
    return np.isin(lab, keep[keep > 0])


def drop_blobby(m, emin):
    """Drop components whose elongation (major/minor second-moment axis) is below emin.
    NOTE this is not new information: Elongation is already a feature of the shipped
    logistic classifier. This is a hard post-hoc floor on a feature the model soft-weights."""
    if emin <= 1 or not m.any():
        return m
    lab, _ = ndi.label(m)
    keep = [p.label for p in measure.regionprops(lab)
            if p.axis_major_length / (p.axis_minor_length or 0.5) >= emin]
    return np.isin(lab, keep)


def regrow(m, w):
    """Skeletonise, then re-grow to a uniform stroke width w px."""
    if not m.any():
        return m
    sk = morphology.skeletonize(m)
    r = max(int(round((w - 1) / 2.0)), 0)
    return dilate(sk, r) if r else sk


def _endpoints(sk):
    nb = ndi.convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant")
    return np.argwhere(sk & (nb == 2))


def _tangent(sk, pt, span=9):
    y, x = pt; H, W = sk.shape
    pts = np.argwhere(sk[max(0, y-span):min(H, y+span+1), max(0, x-span):min(W, x+span+1)]) \
        + [max(0, y-span), max(0, x-span)]
    if len(pts) < 3:
        return None
    v = np.array([y, x], float) - pts.mean(0)
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else None


def bridge(m, maxgap=25, max_angle_deg=50):
    """Join two fragments only where their skeleton endpoints are close AND the gap is
    roughly collinear with both local tangents. Unlike a disk closing this cannot fatten
    a crack, so a gain here would be DETECTION, not stroke matching. (It gains +0.0008.)"""
    if not m.any():
        return m
    sk = morphology.skeletonize(m)
    eps = _endpoints(sk)
    if len(eps) < 2:
        return m
    lab, _ = ndi.label(m); dt = ndi.distance_transform_edt(m)
    tans = [_tangent(sk, p) for p in eps]
    ca = np.cos(np.deg2rad(max_angle_deg)); out = m.copy()
    for i in range(len(eps)):
        if tans[i] is None:
            continue
        for j in range(i + 1, len(eps)):
            if tans[j] is None:
                continue
            a, b = eps[i], eps[j]
            if lab[a[0], a[1]] == lab[b[0], b[1]]:
                continue
            d = b - a; L = float(np.linalg.norm(d))
            if L < 1 or L > maxgap:
                continue
            u = d / L
            if np.dot(tans[i], u) < ca or np.dot(tans[j], -u) < ca:
                continue
            ln = np.zeros_like(m)
            rr, cc = draw.line(int(a[0]), int(a[1]), int(b[0]), int(b[1])); ln[rr, cc] = True
            r = max(int(round((max(1.0, dt[a[0], a[1]] + dt[b[0], b[1]]) - 1) / 2)), 0)
            out |= dilate(ln, r) if r else ln
    return out


def postprocess(p, close_r=0, elong_min=1.0, dilate_r=0):
    """The composed post-processor, in the order the grid applied it."""
    return dilate(drop_blobby(close(p, close_r), elong_min), dilate_r)


# ------------------------------------------------------------------------------ scoring
def with_corpus(exclude_extra=()):
    """Context-managed restriction of TB.load. tilebench.load() already takes `exclude`,
    but TB.evaluate calls it with the default bound at def time, so the module attribute
    has to be swapped for the restricted corpus to reach the evaluator."""
    import contextlib

    @contextlib.contextmanager
    def cm():
        orig = TB.load
        exc = TB.DEFAULT_EXCLUDE + tuple(exclude_extra)

        def restricted(exclude=exc, with_raw=False):
            return orig(exclude=exc, with_raw=with_raw)
        TB.load = restricted
        try:
            yield [i for i, t in enumerate(orig()) if t["specimen"] not in exc]
        finally:
            TB.load = orig
    return cm()


def sweep(tiles, S, mads, cls, dls, els, log_every=40):
    """Score the whole cartesian product. Returns {key: [per-tile counts]} for TB.evaluate."""
    preds = {mk: [predict(t, S, mad_k=mk) for t in tiles] for mk in mads}
    grid = {}; t0 = time.time()
    for n, (mk, cl, dl, el) in enumerate(itertools.product(mads, cls, dls, els), 1):
        grid[f"mad{mk}_cl{cl}_dl{dl}_el{el}"] = [
            TB.counts(postprocess(p, cl, el, dl), t["gt"]) for p, t in zip(preds[mk], tiles)]
        if n % log_every == 0:
            print(f"  {n} configs, {time.time()-t0:.0f}s", flush=True)
    return grid, preds


def per_specimen_delta(grid, key, ref="mad5.0_cl0_dl0_el1.0", idx=None):
    """improved / unchanged / REGRESSED against the shipped reference, per specimen.
    A gain that lives in one specimen is not a gain, and only this table shows that."""
    tiles = TB.load()
    if idx is None:
        idx = list(range(len(tiles)))
    specs = sorted({tiles[i]["specimen"] for i in idx})
    rows, up, same, down = [], 0, 0, 0
    for sp in specs:
        ii = [i for i in idx if tiles[i]["specimen"] == sp]
        a = TB._agg([grid[ref][i] for i in ii])["iou"]
        b = TB._agg([grid[key][i] for i in ii])["iou"]
        rows.append((sp, a, b))
        up += b > a + 1e-6; down += b < a - 1e-6; same += abs(b - a) <= 1e-6
    return rows, dict(improved=up, unchanged=same, regressed=down)


def jackknife(grid, family_keys, ref=SHIPPED_KEY):
    """Pooled held-out IoU of a family, dropping ONE specimen from the CORPUS at a time.

    Leave-one-specimen-out protects the parameter choice; it does NOT tell you whether
    the gain is concentrated, because 12 of the 13 folds still contain the beneficiary.
    Only removing a specimen from the corpus shows that. A gain that holds at roughly
    the same size under every drop is distributed; one that collapses under exactly one
    drop belongs to that specimen.
    """
    tiles = TB.load()
    specs = sorted({t["specimen"] for t in tiles})
    print(f"  {'dropped specimen':<22} {'baseline IoU':>13} {'family IoU':>11} {'delta':>9} {'pick':>8}")
    rows = []
    for drop in [None] + specs:
        with with_corpus((drop,) if drop else ()) as idx:
            g = {k: [grid[k][i] for i in idx] for k in family_keys}
            b = TB._agg([grid[ref][i] for i in idx])["iou"]
            r = TB.evaluate("jk", g, quiet=True)
        rows.append((drop, b, r["loso"]["iou"], r["fitted_key"]))
        print(f"  {(drop or '(none)'):<22} {b:13.4f} {r['loso']['iou']:11.4f} "
              f"{r['loso']['iou']-b:+9.4f} {r['fitted_key']:>8}")
    return rows


def stroke_widths(tiles, S):
    """Median stroke width (2 x median distance-transform on the skeleton) of the human
    label and of each operator's output. This is the test for stroke matching: an
    operator that pushes the prediction FURTHER from the human width and still gains
    IoU is gaming the metric, not matching a stroke."""
    def sw(m):
        if not m.any():
            return np.nan
        sk = morphology.skeletonize(m)
        return 2 * np.median(ndi.distance_transform_edt(m)[sk]) if sk.any() else np.nan
    base = [predict(t, S) for t in tiles]
    human = float(np.nanmedian([sw(t["gt"]) for t in tiles]))
    print(f"  {'HUMAN ground truth':<20} {human:6.2f} px")
    for nm, f in [("shipped prediction", lambda p: p), ("+ closing disk(31)", lambda p: close(p, 31)),
                  ("+ dilation disk(3)", lambda p: dilate(p, 3))]:
        w = float(np.nanmedian([sw(f(p)) for p in base]))
        print(f"  {nm:<20} {w:6.2f} px   ({w/human:.2f}x the human)")
    return human


def test_closing_preserves_width():
    """Closing must not fatten a straight stroke -- that is what separates it from
    dilation. Away from the image border it is exactly area-preserving up to r=11."""
    ok = True
    for w in (2, 4):
        m = np.zeros((160, 160), bool); m[80:80+w, 30:130] = True
        for r in (3, 7, 11):
            same = close(m, r).sum() == m.sum()
            ok &= same
            print(f"  {'PASS' if same else 'FAIL'}  straight bar w={w}, closing r={r}: area preserved")
    m = np.zeros((160, 160), bool); m[80:84, 30:70] = True; m[80:84, 80:130] = True
    grew = close(m, 11).sum() > m.sum()
    ok &= grew
    print(f"  {'PASS' if grew else 'FAIL'}  bar with a 10 px gap, closing r=11: gap bridged")
    return ok


def sabotage():
    """Deliberately broken predictors. If these do not collapse, the scoring measured
    nothing and no number in this file is readable."""
    tiles = TB.load(); S = stagecache(tiles)
    base = [predict(t, S) for t in tiles]
    rng = np.random.default_rng(0)
    checks = {
        "pred scored against the WRONG tile's gt":
            [TB.counts(p, tiles[(i + 1) % len(tiles)]["gt"]) for i, p in enumerate(base)],
        "elongation filter on a RANDOM mask of equal area":
            [TB.counts(drop_blobby(rng.random(t["gt"].shape) < max(p.mean(), 1e-9), 2.0), t["gt"])
             for p, t in zip(base, tiles)],
        "dilation applied to the EMPTY mask":
            [TB.counts(dilate(np.zeros_like(t["gt"]), 4), t["gt"]) for t in tiles],
        "the prediction inverted":
            [TB.counts(~p, t["gt"]) for p, t in zip(base, tiles)],
    }
    ok = True
    for nm, v in checks.items():
        m = TB._agg(v)
        bad = m["iou"] > 0.10
        ok &= not bad
        print(f"  {'PASS' if not bad else 'FAIL'}  {nm:<48} IoU {m['iou']:.4f}")
    print(f"  (shipped baseline for comparison: IoU {TB._agg([TB.counts(p, t['gt']) for p, t in zip(base, tiles)])['iou']:.4f})")
    return ok


# --------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    print("CONTROLS"); assert TB.controls(), "tilebench controls failed"
    assert verify_fast_path()
    print("\nCLOSING IS WIDTH-PRESERVING"); assert test_closing_preserves_width()
    print("\nSABOTAGE"); assert sabotage()
    if args.verify and not args.all:
        return

    tiles = TB.load(); S = stagecache(tiles)
    grid, _ = sweep(tiles, S, MADS, CLS, DLS, ELS)

    for label, extra in [("FULL 26 TILES (13 specimens)", ()),
                         ("CLEAN 12 SPECIMENS -- flooded MAR_H_HIP dropped", ("MAR_H_HIP",))]:
        print(f"\n{'#'*78}\n### {label}\n{'#'*78}")
        with with_corpus(extra) as idx:
            g = {k: [v[i] for i in idx] for k, v in grid.items()}
            TB.evaluate("shipped (parameter-free)", {"shipped": g[SHIPPED_KEY]})
            TB.evaluate("A. closing only, shipped mad_k  (1 free param)",
                        {k: v for k, v in g.items() if k.startswith("mad5.0_") and k.endswith("_dl0_el1.0")})
            TB.evaluate("B. all post-ops, shipped mad_k  (3 free params)",
                        {k: v for k, v in g.items() if k.startswith("mad5.0_")})
            TB.evaluate("C. mad_k only  (the known-best lever)",
                        {k: v for k, v in g.items() if "_cl0_dl0_el1.0" in k})
            TB.evaluate("D. mad_k + all post-ops  (4 free params)", g)

    print(f"\n{'#'*78}\n### IS THE CLOSING GAIN DISTRIBUTED, OR ONE SPECIMEN?\n{'#'*78}")
    jackknife(grid, [f"mad5.0_cl{r}_dl0_el1.0" for r in CLS])
    print(f"\n{'#'*78}\n### STROKE WIDTH vs THE HUMAN\n{'#'*78}")
    stroke_widths(tiles, S)
    print(f"\n{'#'*78}\n### PER-SPECIMEN, the recommended closing disk(31)\n{'#'*78}")
    rows, tally = per_specimen_delta(grid, "mad5.0_cl31_dl0_el1.0")
    for sp, a, b in rows:
        print(f"  {sp[:22]:<22} {a:8.4f} -> {b:8.4f}   {b-a:+8.4f}")
    print(f"  {tally}")


if __name__ == "__main__":
    main()
