"""ONE instrument for scoring any crack predictor against the hand-labelled tiles.

Everything that asks "is this better?" must go through here, because two scorers make a
gain unreadable: a different exclusion list, a different pooling rule or a different
tolerance moves the answer by more than most real improvements do.

The rules this enforces, so no caller can quietly skip them:

  * Model selection is LEAVE-ONE-SPECIMEN-OUT. A parameter picked on all 26 tiles and
    then quoted against those same 26 tiles is fitted on itself. Every method reports
    BOTH, and the gap between them is printed, because that gap is the overfit.
  * Specimens are the group, not tiles. Six tiles come from MAR_H_AS alone; splitting by
    tile leaks a specimen's own texture into its test fold.
  * MAR_AmbB_AS is excluded by default: 87% of what was painted there is round (median
    elongation 1.51 vs 3.27), i.e. porosity, not cracks. Pass exclude=() to include it.
  * Controls run on demand: a perfect predictor must score 1.0, an empty one 0.0, and
    mark-everything must score precision == prevalence. A harness that cannot reproduce
    those three is not measuring what it claims.
"""
import json, os, sys
import numpy as np

SC = "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad"
CACHE = os.path.join(SC, "tilecache")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
UP = "/Users/jiamingzhang/Library/Application Support/Crack Fractography/uploads"
DEFAULT_EXCLUDE = ("MAR_AmbB_AS",)
# Owns 82% of all false positives at the shipped settings: the detector marked an
# off-specimen void. Kept IN by default -- it is a real failure, not a bad label.
FLOODED = "MAR_H_HIP_CBS_0002__crop_3122_120_512x512"


def build_cache(verbose=True):
    """Cut each tile out of its parent micrograph once and store it. The parents are up
    to 6144x4376 uint16; re-reading them per experiment is what makes a sweep take hours.
    Stores the percentile-stretched uint8 exactly as detect_cracks.load_as_uint8 makes it,
    so a cached tile is byte-identical to what the real pipeline would have seen."""
    import tifffile
    from PIL import Image
    from skimage import exposure
    Image.MAX_IMAGE_PIXELS = None
    os.makedirs(CACHE, exist_ok=True)
    tiles = json.load(open(os.path.join(SC, "tiles_meta.json")))
    orig, mach = os.path.join(SEM, "original"), os.path.join(SEM, "crack_export", "derived", "machine_masks")
    for i, t in enumerate(tiles, 1):
        out = os.path.join(CACHE, t["frame"] + ".npz")
        if os.path.exists(out):
            continue
        x, y, w, h = t["box"]
        gt = np.array(Image.open(os.path.join(UP, t["frame"] + "_gated.png")).convert("L")) < 128
        src = next(os.path.join(orig, t["parent"] + e) for e in (".tif", ".tiff", ".png")
                   if os.path.exists(os.path.join(orig, t["parent"] + e)))
        mh, mw = np.array(Image.open(os.path.join(mach, t["parent"] + "_machine.png"))).shape
        a = tifffile.imread(src)
        if a.ndim == 3:
            a = a[..., 0]
        if a.shape[1] == mw and a.shape[0] > mh:
            a = a[:mh, :]          # trim the databar, the same way _match_original_to_mask does
        raw = a[y:y + h, x:x + w]
        lo, hi = np.percentile(raw, [1.0, 99.5])
        img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                          out_range=(0, 255)).astype(np.uint8)
        np.savez_compressed(out, img8=img8, raw=raw.astype(np.uint16), gt=gt)
        if verbose:
            print(f"  cached [{i}/{len(tiles)}] {t['frame']}", flush=True)
    return CACHE


def load(exclude=DEFAULT_EXCLUDE, with_raw=False):
    """Every tile as a dict: img8, gt, raw (uint16, optional), specimen, frame."""
    tiles = json.load(open(os.path.join(SC, "tiles_meta.json")))
    out = []
    for t in tiles:
        if t["specimen"] in exclude:
            continue
        z = np.load(os.path.join(CACHE, t["frame"] + ".npz"))
        d = dict(frame=t["frame"], parent=t["parent"], specimen=t["specimen"],
                 box=t["box"], img8=z["img8"], gt=z["gt"].astype(bool))
        if with_raw:
            d["raw"] = z["raw"]
        out.append(d)
    return out


def counts(pred, gt, tol=2):
    """tp/fp/fn exactly, plus the same at a `tol` px tolerance. The literature reports
    tolerant scores (Kompanets 2024: CrackForest F1 75.35 at 0 px, 97.10 at 2 px), so an
    exact-only number is not comparable to a published one. Both travel together."""
    from scipy import ndimage as ndi
    pred = np.asarray(pred, bool); gt = np.asarray(gt, bool)
    c = dict(tp=int((pred & gt).sum()), fp=int((pred & ~gt).sum()), fn=int((~pred & gt).sum()))
    if tol:
        st = ndi.generate_binary_structure(2, 2)
        gd = ndi.binary_dilation(gt, st, iterations=tol)
        pd = ndi.binary_dilation(pred, st, iterations=tol)
        c.update(ttp=int((pred & gd).sum()), tfp=int((pred & ~gd).sum()), tfn=int((~pd & gt).sum()))
    return c


def _m(tp, fp, fn):
    p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
    return dict(precision=p, recall=r, iou=tp / max(tp + fp + fn, 1),
                f1=2 * p * r / max(p + r, 1e-12))


def _agg(rows, pre=""):
    return _m(sum(r[pre + "tp"] for r in rows), sum(r[pre + "fp"] for r in rows),
              sum(r[pre + "fn"] for r in rows))


def evaluate(name, per_tile_counts, criterion="iou", quiet=False):
    """per_tile_counts: {variant_key: [count-dict per tile, in load() order]}.

    Returns the fitted-best variant (optimistic, for shape only) and the leave-one-
    specimen-out score, which is the one to quote. With a single variant the two agree
    by construction and the method is parameter-free.
    """
    tiles = load()
    specs = sorted({t["specimen"] for t in tiles})
    keys = list(per_tile_counts)
    for k, v in per_tile_counts.items():
        assert len(v) == len(tiles), f"{name}/{k}: {len(v)} rows for {len(tiles)} tiles"

    fitted_key = max(keys, key=lambda k: _agg(per_tile_counts[k])[criterion])
    fitted = _agg(per_tile_counts[fitted_key]); fitted_tol = _agg(per_tile_counts[fitted_key], "t")

    held, picks, per_spec = [], {}, {}
    for sp in specs:
        tr = [i for i, t in enumerate(tiles) if t["specimen"] != sp]
        te = [i for i, t in enumerate(tiles) if t["specimen"] == sp]
        best = max(keys, key=lambda k: _agg([per_tile_counts[k][i] for i in tr])[criterion])
        picks[sp] = best
        rows = [per_tile_counts[best][i] for i in te]
        per_spec[sp] = _agg(rows); held.extend(rows)
    loso, loso_tol = _agg(held), _agg(held, "t")

    res = dict(name=name, n_tiles=len(tiles), n_specimens=len(specs), n_variants=len(keys),
               criterion=criterion, fitted_key=str(fitted_key), fitted=fitted,
               fitted_tol2=fitted_tol, loso=loso, loso_tol2=loso_tol,
               overfit_gap=fitted[criterion] - loso[criterion],
               picks={k: str(v) for k, v in picks.items()}, per_specimen=per_spec)
    if not quiet:
        report(res)
    return res


def report(r):
    print(f"\n=== {r['name']}   ({r['n_variants']} variant(s), {r['n_tiles']} tiles, "
          f"{r['n_specimens']} specimens, selected by {r['criterion']}) ===")
    print(f"  {'':<22} {'precision':>10} {'recall':>8} {'IoU':>8} {'F1':>8}")
    for lab, k in [("FITTED (optimistic)", "fitted"), ("HELD-OUT (quote this)", "loso"),
                   ("held-out, 2px tol", "loso_tol2")]:
        m = r[k]
        print(f"  {lab:<22} {m['precision']:10.4f} {m['recall']:8.4f} {m['iou']:8.4f} {m['f1']:8.4f}")
    print(f"  overfit gap on {r['criterion']}: {r['overfit_gap']:+.4f}"
          f"   fitted pick: {r['fitted_key']}")
    if r["n_variants"] > 1:
        from collections import Counter
        print("  held-out picks: " + ", ".join(f"{k} x{v}" for k, v in
                                               Counter(r["picks"].values()).most_common()))


#: THIS IS NOT WHAT SHIPS, and it used to be called SHIPPED, which made the one gate that
#: certifies this harness certify a pipeline retired two versions ago. It is the v1.47
#: reference point -- region classifier ON, single flattening radius sigma=40, mad_k=5.0,
#: classifier threshold 0.5538 -- and it is kept only because `crackpipe.predict` still
#: reproduces exactly that, which is what tilebench_verify.py checks.
V147_CLASSIFIER_ON = dict(precision=0.3378, recall=0.3696, iou=0.2143)

#: WHAT ACTUALLY SHIPS (v1.49.1: classifier OFF, 7-scale darkness union, mad_k 5.0,
#: absolute_dark 10), measured through this harness over the same 26 tiles.
#:
#: EVERY ROW IS THE SAME MASKS AND THE SAME LABELS. The aggregation moves the number more
#: than any model change tested in this project ever has, so a figure from here is
#: unreadable without naming its row. Reproduce with
#: analysis/research/improve/aggregation.py; the recommended row for a write-up is
#: median over specimens at 2 px tolerance, and the pooled row must never appear alone.
#:
#:   aggregation                          prec  recall      F1     IoU
#:   pooled over all pixels             0.4182  0.6252  0.5012  0.3344
#:   median over the 26 TILES           0.8056  0.7623  0.5922  0.4208
#:   median over 13 SPECIMENS           0.7897  0.7159  0.5418  0.3715
#:   median over TILES, 2 px tol        0.8970  0.9200  0.6785  0.5134
#:   median over SPECIMENS, 2 px tol    0.8988  0.8025  0.6633  0.4962
#:
#: F1 in those rows is the MEDIAN OF THE PER-UNIT F1s, not 2PR/(P+R) of the two medians --
#: that would read 0.8479 and describe a specimen that does not exist, because the
#: high-precision specimens are not the high-recall ones.
#:
#: IoU CARRIES ITS CEILING OR IT IS MISREAD. A perfectly placed trace -- down the label's
#: own centreline, zero localisation error, best width -- caps at IoU 0.4993 on these
#: tiles, so 0.4208 is 84% of what these labels permit, not 42% of perfect.
SHIPPED_V1491 = dict(
    pooled=dict(precision=0.4182, recall=0.6252, f1=0.5012, iou=0.3344),
    median_tiles=dict(precision=0.8056, recall=0.7623, f1=0.5922, iou=0.4208),
    median_specimens=dict(precision=0.7897, recall=0.7159, f1=0.5418, iou=0.3715),
    median_tiles_tol2=dict(precision=0.8970, recall=0.9200, f1=0.6785, iou=0.5134),
    median_specimens_tol2=dict(precision=0.8988, recall=0.8025, f1=0.6633, iou=0.4962),
    iou_ceiling_perfect_trace=0.4993,
)


def controls():
    """Three predictors whose scores are known before the harness runs. If these do not
    come out right the harness is broken, and every number it produced is unreadable."""
    tiles = load()
    oracle = {"x": [counts(t["gt"], t["gt"]) for t in tiles]}
    empty = {"x": [counts(np.zeros_like(t["gt"]), t["gt"]) for t in tiles]}
    allpx = {"x": [counts(np.ones_like(t["gt"]), t["gt"]) for t in tiles]}
    prev = sum(int(t["gt"].sum()) for t in tiles) / sum(t["gt"].size for t in tiles)
    ok = True
    for nm, d, want in [("oracle (gt itself)", oracle, dict(precision=1.0, recall=1.0, iou=1.0)),
                        ("empty", empty, dict(precision=0.0, recall=0.0, iou=0.0)),
                        ("mark everything", allpx, dict(precision=prev, recall=1.0, iou=prev))]:
        got = _agg(d["x"])
        bad = [k for k, v in want.items() if abs(got[k] - v) > 1e-6]
        print(f"  {'PASS' if not bad else 'FAIL'}  {nm:<20} "
              f"P {got['precision']:.4f} R {got['recall']:.4f} IoU {got['iou']:.4f}"
              + (f"   expected {want}" if bad else ""))
        ok &= not bad
    print(f"  crack prevalence over the {len(tiles)} tiles: {prev:.4%}")
    return ok


if __name__ == "__main__":
    if "--build" in sys.argv:
        build_cache()
    print("CONTROLS")
    print("all controls passed" if controls() else "CONTROLS FAILED -- do not trust any score")
