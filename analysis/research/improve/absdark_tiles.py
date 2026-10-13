"""Does raising segment_dark_regions' absolute_dark_thresh cost precision? Ask the tiles.

`absolute_dark_thresh=10` carries HALF of the candidate stage's whole recall --
13,907,547 of the 20,923,398 hand-painted crack pixels proposed on 48 full frames, and
10,516,306 of them found by that term and no ladder rung (fullframe_recall_decomposition).
Raising it to 20/30 recovers 15.2%/19.3% of the never-proposed painted crack and cannot
delete anything. But the paint cannot price it: the corpus holds 258,352 hand-marked
NOT-crack pixels against 70,041,625 crack, and 85.5% of them are ALREADY proposed at the
shipped setting, so there is no headroom in which a precision cost could show up.

MEASURED, and it does NOT ship. Leave-one-specimen-out over the grid picks t=10 in 13 of
13 folds; IoU falls 0.3246 -> 0.3056 (t=20) -> 0.2622 (t=30) -> 0.1603 (t=50). Going to 20
buys +1,227 true px and costs +27,473 false px: 22.4 px of false positive per px of real
crack, identical without the known off-specimen void tile. But the budget-matched random
control below says that is not "it is noise" -- at the 2.97% tile prevalence the null is
81.6, so 22.4 is a 3.53x enrichment over chance. The added area is real signal whose
MARGINAL precision (4.3%) sits far below the stage's running 41%, which is why every
IoU-like metric falls. And the tiles are blind to what the change is FOR: t=10->20 raises
the tile region count 14.6% at 700 px per new region and the FRAME region count 0.4% at
42,476 px per new region, because these 26 crops are 6.8 Mpx of 811 Mpx, actively selected
and 3x less painted than the corpus -- they hold the pores the threshold also catches and
not the wide-open cracks it widens. Neither instrument can say whether the added dark
pixels are crack. Full record in analysis/detector_overrides.py.

The 26 hand-labelled tiles can, and for an ADDITIVE rule a tile score is admissible --
that is v1.49's own argument for shipping on tile evidence ("a STRICT SUPERSET ... which
is why a tile score is sufficient evidence for it"), and it is the opposite of the three
region-REJECTING rules the tiles ranked backwards. Scored through analysis/research/
tilebench.py so selection is leave-one-SPECIMEN-out and the three controls run.

THE CONFOUND THAT MAKES THIS TWO ARMS, NOT ONE. `img8` is a PERCENTILE-STRETCHED image,
and tilebench stretches each 512 px crop by its OWN 1.0/99.5 percentiles while the full
pipeline stretches the whole micrograph. An absolute grey level therefore does not mean
the same thing in the two places, so a threshold tuned on crop-stretched tiles would not
transfer to a frame. Both are run:

    crop   tilebench's own cached img8. Comparable to every tile number on record, and the
           t=10 arm must reproduce the 0.3344 that ships -- asserted, not hoped. (NOT
           0.2979, which is v1.48's single-scale figure; this control was written against
           that stale number first and correctly failed.)
    parent the same crop re-stretched by its PARENT micrograph's percentiles, which is what
           the pipeline actually feeds the absolute test. This is the arm whose threshold
           transfers to a full frame.

Nothing here writes outside the scratchpad, and nothing writes to sem-crack-detector.

Run:
    MYSC=<scratchpad> /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python \
        -B analysis/research/improve/absdark_tiles.py
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
MY = os.environ.get("MYSC", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                            "6a52cb79-9e35-41ca-afd2-799d7027591c/scratchpad")
os.environ.setdefault("MPLCONFIGDIR", MY + "/mpl")
R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R); sys.path.insert(0, R + "/improve")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.dont_write_bytecode = True
import numpy as np, tifffile
from PIL import Image
from skimage import exposure, filters
import detect_cracks as D
import tilebench as TB
import fullframe_recall_decomposition as RD

Image.MAX_IMAGE_PIXELS = None
SEM = RD.SEM
TS = (10, 15, 20, 25, 30, 40, 50)
MADK = 5.0


def parent_percentiles(parent, cache={}):
    """The 1.0/99.5 percentiles of the WHOLE micrograph, which is what the pipeline's
    load_as_uint8 uses. Cached: 26 tiles come from far fewer parents."""
    if parent in cache:
        return cache[parent]
    src = next(os.path.join(SEM, "original", parent + e) for e in (".tif", ".tiff", ".png")
               if os.path.exists(os.path.join(SEM, "original", parent + e)))
    a = tifffile.imread(src)
    if a.ndim == 3:
        a = a[..., 0]
    mh, mw = np.array(Image.open(os.path.join(
        SEM, "crack_export", "derived", "machine_masks", parent + "_machine.png"))).shape
    if a.shape[1] == mw and a.shape[0] > mh:
        a = a[:mh, :]
    cache[parent] = tuple(float(x) for x in np.percentile(a, [1.0, 99.5]))
    del a
    return cache[parent]


def dark_masks(img8):
    """k_max once per tile, then every threshold is a re-OR and costs nothing. Uses the
    shipped ladder and the shipped per-radius flattening, from detector_overrides itself."""
    flat40 = D.flatten_background(img8, sigma=40)
    km = None
    for sigma in RD.LADDER:
        f = flat40 if sigma == 40 else RD._FLATTEN(img8, sigma)
        sm = filters.gaussian(f, sigma=1.0, preserve_range=True)
        med = float(np.median(sm))
        mad = float(np.median(np.abs(sm - med)) * 1.4826)
        otsu = float(filters.threshold_otsu(sm))
        if mad > 0:
            k = ((med - sm) / mad).astype(np.float32)
            k[sm >= otsu] = -np.inf
        else:
            k = np.full(img8.shape, -np.inf, np.float32)
        km = k if km is None else np.maximum(km, k)
    return flat40, km


def main():
    tiles = TB.load(with_raw=True)
    print(f"{len(tiles)} tiles, {len({t['specimen'] for t in tiles})} specimens\n")
    print("CONTROLS")
    assert TB.controls(), "tilebench controls failed"

    per = {("crop", t): [] for t in TS}
    per.update({("parent", t): [] for t in TS})
    for i, tl in enumerate(tiles, 1):
        for mode in ("crop", "parent"):
            if mode == "crop":
                img8 = tl["img8"]
            else:
                lo, hi = parent_percentiles(tl["parent"])
                img8 = exposure.rescale_intensity(tl["raw"].astype(np.float32),
                                                  in_range=(lo, hi),
                                                  out_range=(0, 255)).astype(np.uint8)
            flat40, km = dark_masks(img8)
            for t in TS:
                st = RD.chain((km > MADK) | (img8 < t), flat40)
                c = TB.counts(st["cand"], tl["gt"])
                #: GROWTH vs NEW OBJECTS. On full frames raising this threshold adds
                #: 8.3 Mpx for only +196 new regions (42,476 px per new region), i.e. it
                #: widens cracks the detector already found. If on the tiles the same
                #: change instead adds many SMALL NEW regions, the two instruments are
                #: scoring the threshold's effect on two different populations of objects
                #: and the disagreement between them is explained rather than arbitrary.
                c["nreg"] = st["nreg"]
                c["area"] = int(st["cand"].sum())
                per[(mode, t)].append(c)
        print(f"  [{i}/{len(tiles)}] {tl['frame'][:46]:<48} "
              f"crop t10 IoU {TB._m(**{k: per[('crop', 10)][-1][k] for k in ('tp','fp','fn')})['iou']:.4f}  "
              f"parent t10 IoU {TB._m(**{k: per[('parent', 10)][-1][k] for k in ('tp','fp','fn')})['iou']:.4f}",
              flush=True)

    print("\n" + "=" * 110)
    print("ABSOLUTE DARKNESS THRESHOLD, 26 hand-labelled tiles, classifier OFF (what "
          "ships), mad_k=5.0")
    print("=" * 110)
    for mode, note in (("crop", "tilebench's own crop-local 1.0/99.5 stretch -- "
                                "comparable to every number on record"),
                       ("parent", "re-stretched by the PARENT micrograph -- what the "
                                  "pipeline really feeds the absolute test")):
        print(f"\n{mode}: {note}\n")
        print(f"  {'absolute_dark_thresh':>21} {'precision':>10} {'recall':>8} {'IoU':>8} "
              f"{'F1':>8}   {'2px IoU':>8} {'2px F1':>8}")
        for t in TS:
            m = TB._agg(per[(mode, t)])
            mt = TB._agg(per[(mode, t)], "t")
            print(f"  {t:>21} {m['precision']:10.4f} {m['recall']:8.4f} {m['iou']:8.4f} "
                  f"{m['f1']:8.4f}   {mt['iou']:8.4f} {mt['f1']:8.4f}")
        # the same, without the one known-pathological off-specimen void tile
        keep = [j for j, tl in enumerate(tiles) if tl["frame"] != TB.FLOODED]
        print(f"  -- without the off-specimen void tile ({TB.FLOODED[:28]}...), "
              f"{len(keep)} tiles:")
        for t in TS:
            m = TB._agg([per[(mode, t)][j] for j in keep])
            print(f"  {t:>21} {m['precision']:10.4f} {m['recall']:8.4f} {m['iou']:8.4f} "
                  f"{m['f1']:8.4f}")

    # ---------------------------------------------------------- budget-matched random null
    # A sibling session established that on these tiles almost all apparent precision GAIN
    # from a deleting rule is the SIZE of the deletion rather than where it lands, because
    # one tile owns ~80% of all false positives, and that any precision claim here needs a
    # budget-matched random control. The same applies in reverse to an ADDING rule: at a
    # 2.97% crack prevalence, area added at random lands on crack 2.97% of the time, so the
    # null fp/tp is about 66 and a measured 22 is a GAIN over chance, not a failure. The
    # per-tile prevalence is used, not the pooled one, because the tiles differ 100-fold in
    # how much of them is painted.
    print("\nBUDGET-MATCHED RANDOM CONTROL on the ADDITION. `enrichment` is the measured "
          "new true\npositives over what the same number of pixels added at random inside "
          "each tile would hit.")
    for mode in ("crop", "parent"):
        print(f"\n  {mode}:")
        print(f"    {'t':>5} {'added px':>12} {'new tp':>9} {'new fp':>10} "
              f"{'fp per tp':>10} {'random null':>12} {'exp. tp':>9} {'enrichment':>11}")
        b = per[(mode, 10)]
        for t in TS[1:]:
            a = per[(mode, t)]
            dtp = sum(y["tp"] - x["tp"] for x, y in zip(b, a))
            dfp = sum(y["fp"] - x["fp"] for x, y in zip(b, a))
            add = sum(y["area"] - x["area"] for x, y in zip(b, a))
            etp = sum((y["area"] - x["area"]) * (x["tp"] + x["fn"]) / float(tl["gt"].size)
                      for x, y, tl in zip(b, a, tiles))
            print(f"    {t:>5} {add:>12,} {dtp:>+9,} {dfp:>+10,} "
                  f"{dfp / max(dtp, 1):>10.2f} {(add - etp) / max(etp, 1e-9):>12.2f} "
                  f"{etp:>9.0f} {dtp / max(etp, 1e-9):>10.2f}x")

    base = TB._agg(per[("crop", 10)])
    # 0.3344 is the v1.49 multi-scale-union, classifier-off score recorded in
    # analysis/detector_overrides.py. (0.2979 is v1.48's single-scale number and is NOT
    # the right reference for an arm built on the shipped ladder -- this control was
    # written against the stale one first and correctly failed.)
    print(f"\nCONTROL the t=10 crop arm must reproduce the shipped v1.49 classifier-off "
          f"tile score 0.3344:\n  got IoU {base['iou']:.4f} "
          f"(P {base['precision']:.4f} R {base['recall']:.4f} F1 {base['f1']:.4f} "
          f"vs the recorded 0.4182/0.6252/0.3344/0.5012)  "
          + ("PASS" if abs(base["iou"] - 0.3344) < 0.0005
             else "FAIL -- the arms are not comparable to anything on record"))

    print("\nLEAVE-ONE-SPECIMEN-OUT over the threshold grid, through tilebench.evaluate "
          "(selection\nnever sees the held-out specimen; the gap to FITTED is the "
          "overfit):")
    for mode in ("crop", "parent"):
        TB.evaluate(f"absolute_dark_thresh, {mode} stretch",
                    {t: per[(mode, t)] for t in TS}, criterion="iou")
    json.dump({f"{m}_{t}": per[(m, t)] for m in ("crop", "parent") for t in TS},
              open(MY + "/work/absdark_tiles.json", "w"))
    print(f"\nwrote {MY}/work/absdark_tiles.json")


if __name__ == "__main__":
    main()
