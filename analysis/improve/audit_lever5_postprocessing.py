"""ADVERSARIAL AUDIT of lever5_postprocessing.py's headline:
   "disk(31) closing of the final mask, shipped mad_k -- held-out IoU 0.2516".

Every number here goes through analysis/tilebench.py. Nothing writes to the archived
repos or to the uploads directory. Run from a scratch dir:

    <sem-crack-detector/.venv/bin/python> -B audit_lever5_postprocessing.py --all

WHAT REPRODUCES EXACTLY (no leakage found)
------------------------------------------
  baseline (CP.predict, parameter-free)   P 0.3378 R 0.3696 IoU 0.2143 F1 0.3530
  closing family, LOSO held-out           P 0.3626 R 0.4511 IoU 0.2516 F1 0.4020
  closing fixed r=31 (fitted)                                 IoU 0.2532   gap +0.0016
  LOSO picks: cl31 x12, cl39 x1          mad_k family held-out IoU 0.2382
  Selection is inside the fold; the single harness is used; the baseline is the right
  one; closing is extensive so it removes ZERO pixels and cannot delete TP.
  Their stated open gap is closed too: re-cutting 8 tiles (incl. both load-bearing
  specimens) straight from the parent TIFFs gives byte-identical img8 AND gt.

WHY IT STILL DOES NOT SURVIVE
-----------------------------
  1. ONE TILE of 26 owns 82.4% of the pooled delta. Close everything EXCEPT
     260708_316_H_b2_front_CBS_005__crop_2122_2980: 0.2222 (+0.0078).
  2. Drop that specimen from the corpus and closing gives +0.0088 (0.2005->0.2093)
     while the mad_k family gives +0.0252 (0.2005->0.2257). The claim "beats the
     known-best 0.2382" is that one tile; without it closing LOSES to mad_k by 3x.
  3. Look at the tile (panel()): the "crack" is a broad painted band along the TOP
     FRAME EDGE (specimen boundary/background), ~60-100 px of brush, GT stroke 16.1 px.
     The prediction is striped inside it; disk(31) fills the stripes -- 11,229 TP added
     for 198 FP. That is filling a broad-brush region assertion at a frame edge, the
     same pathology as the MAR_H_HIP void, not crack-gap bridging.
  4. At each family's own best radius, blind dilation scores 0.2492 vs closing 0.2532.
     The operator's geometry buys +0.0040; the other ~90% of the gain is "paint more
     pixels", which the claimant themselves called metric gaming when dilation does it.
  5. On the 9 hand-labelled frames in uploads that are NOT in tiles_meta and so were
     never swept, closing gives +0.0017 on the only one with nonzero GT and adds 9,017
     FP across the 8 null frames.
  6. Direction is supported, magnitude is not: 8/13 specimens up, 1 down (sign p=0.039),
     specimen bootstrap 95% CI [+0.0036, +0.1620] -- the lower end is negligible.

THE TRIVIAL ALTERNATIVE THAT WINS (audit item 7, untested by the claimant)
--------------------------------------------------------------------------
DELETE THE CLASSIFIER. Accept every candidate region clean_mask produces.
Zero free parameters, so held-out == fitted.

                                     P        R       IoU      F1
  shipped (with classifier)       0.3378   0.3696   0.2143   0.3530
  accept ALL candidates           0.4037   0.5402   0.3005   0.4621
  accept ALL candidates + cl31    0.3700   0.6591   0.3106   0.4740

  11 of 13 specimens improve, 2 regress. Corpus jackknife +0.0739..+0.1453 -- never
  concentrated, unlike closing. Sabotage collapses (shuffled gt 0.0123, 180-rot 0.0036).
  With the porosity specimen MAR_AmbB_AS put back in: 0.2013 -> 0.3226.
  The shipped classifier deletes 31.6% of candidate TP pixels and only 9.2% of
  candidate FP pixels: it is anti-informative on this corpus.
  It also zeroes four specimens outright. MAR_Amb_AS/Cast/HIP and MAR_AmbB_HIP go
  0.0000 -> 0.3732 / 0.3942 / 0.6170 / 0.2131, so "their marked crack is BRIGHTER than
  background, recall 0.000 at every setting" is wrong -- the candidate stage finds them
  and the classifier throws them away.
"""
import argparse, os, re, sys

import numpy as np
from scipy import ndimage as ndi
from skimage import exposure, morphology, filters

ANALYSIS = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis"
if ANALYSIS not in sys.path:
    sys.path.insert(0, ANALYSIS)
import tilebench as TB            # noqa: E402  THE scorer
import crackpipe as CP            # noqa: E402

SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
UP = "/Users/jiamingzhang/Library/Application Support/Crack Fractography/uploads"
CLS = [0, 3, 7, 11, 15, 19, 25, 31, 39, 49, 63]
BENEFICIARY = "260708_316_H_b2"


def predictions(tiles):
    """Shipped prediction, the raw candidate mask, and disk(31) closing, per tile."""
    base, cand = [], []
    for t in tiles:
        st = CP.stages(t["img8"])
        cand.append(st["clean"])
        base.append(CP.probability(st) >= CP.THR)
    cl31 = [morphology.closing(p, morphology.disk(31)) for p in base]
    return base, cand, cl31


# ------------------------------------------------------------------ 1. reproduce
def reproduce(tiles, base):
    grid = {f"cl{r}": [TB.counts(morphology.closing(p, morphology.disk(r)) if r else p, t["gt"])
                       for p, t in zip(base, tiles)] for r in CLS}
    TB.evaluate("baseline (parameter-free)", {"b": grid["cl0"]})
    TB.evaluate("closing family, disk(r)", grid)
    TB.evaluate("closing fixed r=31", {"cl31": grid["cl31"]})
    mad = {f"mad{k}": [TB.counts(CP.predict(t["img8"], mad_k=k), t["gt"]) for t in tiles]
           for k in (2.0, 2.5, 3.0, 3.5, 4.0, 5.0)}
    TB.evaluate("mad_k family (the known-best lever)", mad)
    return grid, mad


# --------------------------------------------- 2. is the cache what it claims to be?
def recut_check(specimens=("260708_316_H_b2", "MAR_H_HIP", "260622_316_amb_b3", "Cast_24hr")):
    """The claimant reused the cache without re-deriving it. Re-cut straight from the
    parent TIFFs and compare bytes."""
    import json, tifffile
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    meta = json.load(open(os.path.join(TB.SC, "tiles_meta.json")))
    ok = True
    for m in [m for m in meta if m["specimen"] in specimens]:
        z = np.load(os.path.join(TB.CACHE, m["frame"] + ".npz"))
        im = _cut(m["parent"], m["box"])
        gt = np.array(Image.open(os.path.join(UP, m["frame"] + "_gated.png")).convert("L")) < 128
        same = np.array_equal(im, z["img8"]) and np.array_equal(gt, z["gt"].astype(bool))
        ok &= same
        print(f"  {'PASS' if same else 'FAIL'}  re-cut {m['frame'][:52]}")
    return ok


def _cut(parent, box):
    import tifffile
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    x, y, w, h = box
    src = next(os.path.join(SEM, "original", parent + e) for e in (".tif", ".tiff", ".png")
               if os.path.exists(os.path.join(SEM, "original", parent + e)))
    mh, mw = np.array(Image.open(os.path.join(
        SEM, "crack_export", "derived", "machine_masks", parent + "_machine.png"))).shape
    a = tifffile.imread(src)
    if a.ndim == 3:
        a = a[..., 0]
    if a.shape[1] == mw and a.shape[0] > mh:
        a = a[:mh, :]
    raw = a[y:y + h, x:x + w]
    lo, hi = np.percentile(raw, [1.0, 99.5])
    return exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)


# ------------------------------------------------- 3. how much of the gain is one tile
def concentration(tiles, base, cl31):
    r0 = [TB.counts(p, t["gt"]) for p, t in zip(base, tiles)]
    r31 = [TB.counts(p, t["gt"]) for p, t in zip(cl31, tiles)]
    i0, i1 = TB._agg(r0)["iou"], TB._agg(r31)["iou"]
    j = next(i for i, t in enumerate(tiles) if t["specimen"] == BENEFICIARY)
    only = TB._agg([r31[i] if i == j else r0[i] for i in range(len(tiles))])["iou"]
    exc = TB._agg([r0[i] if i == j else r31[i] for i in range(len(tiles))])["iou"]
    print(f"  pooled   base {i0:.4f}  cl31 {i1:.4f}  delta {i1-i0:+.4f}")
    print(f"  closing ONLY on the one {BENEFICIARY} tile: {only:.4f} ({only-i0:+.4f})")
    print(f"  closing EVERYWHERE ELSE:                    {exc:.4f} ({exc-i0:+.4f})")
    print(f"  -> {100*(only-i0)/(i1-i0):.1f}% of the pooled gain is 1 tile of 26")
    # closing removes nothing, so it cannot buy precision by deleting crack
    print(f"  pixels REMOVED by closing: {sum(int((p & ~c).sum()) for p, c in zip(base, cl31))}"
          f"   added: {sum(int((c & ~p).sum()) for p, c in zip(base, cl31))}")
    return r0, r31


def bootstrap(tiles, r0, r31, n=20000):
    from scipy import stats
    specs = sorted({t["specimen"] for t in tiles})
    by = {s: [i for i, t in enumerate(tiles) if t["specimen"] == s] for s in specs}
    rng = np.random.default_rng(0)
    d = np.array([TB._agg([r31[i] for i in ix])["iou"] - TB._agg([r0[i] for i in ix])["iou"]
                  for ix in ([i for k in rng.choice(len(specs), len(specs), True)
                              for i in by[specs[k]]] for _ in range(n))])
    print(f"  specimen bootstrap dIoU: median {np.median(d):+.4f} "
          f"95% CI [{np.percentile(d,2.5):+.4f}, {np.percentile(d,97.5):+.4f}] "
          f"P(<=0) {np.mean(d<=0):.4f}")
    up = sum(TB._agg([r31[i] for i in by[s]])["iou"] > TB._agg([r0[i] for i in by[s]])["iou"] + 1e-9
             for s in specs)
    dn = sum(TB._agg([r31[i] for i in by[s]])["iou"] < TB._agg([r0[i] for i in by[s]])["iou"] - 1e-9
             for s in specs)
    print(f"  specimen sign test: {up} up, {dn} down, {len(specs)-up-dn} tied "
          f"-> p={stats.binomtest(up, up+dn, 0.5).pvalue:.4f}")


# ------------------------------------- 4. is it the geometry, or just more paint?
def equal_area_control(tiles, base, cl31):
    addC = sum(int((c & ~p).sum()) for p, c in zip(base, cl31))
    hitC = sum(int(((c & ~p) & t["gt"]).sum()) for p, c, t in zip(base, cl31, tiles))
    print(f"  closing r=31 : adds {addC:6d} ({100*hitC/addC:4.1f}% GT)  "
          f"IoU {TB._agg([TB.counts(c, t['gt']) for c, t in zip(cl31, tiles)])['iou']:.4f}")
    for d in range(1, 8):
        dl = [morphology.dilation(p, morphology.disk(d)) for p in base]
        a = sum(int((x & ~p).sum()) for p, x in zip(base, dl))
        h = sum(int(((x & ~p) & t["gt"]).sum()) for p, x, t in zip(base, dl, tiles))
        m = TB._agg([TB.counts(x, t["gt"]) for x, t in zip(dl, tiles)])
        print(f"  dilate  r={d} : adds {a:6d} ({100*h/max(a,1):4.1f}% GT)  IoU {m['iou']:.4f}")


# ----------------------------------------- 5. never-swept hand-labelled frames
def out_of_corpus():
    import json
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    meta = {m["frame"] for m in json.load(open(os.path.join(TB.SC, "tiles_meta.json")))}
    frames = sorted(f[:-10] for f in os.listdir(UP)
                    if f.endswith("_gated.png") and f[:-10] not in meta)
    r0, r31 = [], []
    for f in frames:
        g = re.match(r"(.+)__crop_(\d+)_(\d+)_(\d+)x(\d+)$", f)
        gt = np.array(Image.open(os.path.join(UP, f + "_gated.png")).convert("L")) < 128
        im = _cut(g.group(1), [int(g.group(i)) for i in (2, 3, 4, 5)])
        p = CP.predict(im); c = morphology.closing(p, morphology.disk(31))
        a, b = TB.counts(p, gt), TB.counts(c, gt)
        r0.append(a); r31.append(b)
        print(f"  {f[:56]:<56} gt {gt.mean():.4f} IoU "
              f"{TB._m(a['tp'],a['fp'],a['fn'])['iou']:.4f} -> {TB._m(b['tp'],b['fp'],b['fn'])['iou']:.4f}"
              f"  fp {a['fp']}->{b['fp']}")
    print(f"  pooled base  {TB._agg(r0)}")
    print(f"  pooled cl31  {TB._agg(r31)}")


# ------------------------------------------ 6. the trivial alternative that wins
def no_classifier(tiles, base, cand, cl31):
    rows = {
        "shipped (with classifier)": [TB.counts(p, t["gt"]) for p, t in zip(base, tiles)],
        "closing31 on shipped": [TB.counts(p, t["gt"]) for p, t in zip(cl31, tiles)],
        "accept ALL candidates (no clf)": [TB.counts(p, t["gt"]) for p, t in zip(cand, tiles)],
        "accept ALL candidates + cl31": [
            TB.counts(morphology.closing(p, morphology.disk(31)), t["gt"])
            for p, t in zip(cand, tiles)],
    }
    for k, v in rows.items():
        m = TB._agg(v)
        print(f"  {k:<34} P {m['precision']:.4f} R {m['recall']:.4f} "
              f"IoU {m['iou']:.4f} F1 {m['f1']:.4f}")
    tp = sum(int((c & t["gt"]).sum()) for c, t in zip(cand, tiles))
    fp = sum(int((c & ~t["gt"]).sum()) for c, t in zip(cand, tiles))
    dtp = sum(int((c & ~b & t["gt"]).sum()) for c, b, t in zip(cand, base, tiles))
    dfp = sum(int((c & ~b & ~t["gt"]).sum()) for c, b, t in zip(cand, base, tiles))
    print(f"  the classifier deletes {100*dtp/tp:.1f}% of candidate TP px and only "
          f"{100*dfp/fp:.1f}% of candidate FP px -> anti-informative here")
    specs = sorted({t["specimen"] for t in tiles})
    r0, rc = rows["shipped (with classifier)"], rows["accept ALL candidates (no clf)"]
    up = dn = 0
    for s in specs:
        ii = [i for i, t in enumerate(tiles) if t["specimen"] == s]
        a, b = TB._agg([r0[i] for i in ii])["iou"], TB._agg([rc[i] for i in ii])["iou"]
        up += b > a + 1e-9; dn += b < a - 1e-9
        print(f"    {s:<20} {a:7.4f} -> {b:7.4f}  {b-a:+7.4f}")
    print(f"    improved {up}, regressed {dn}, tied {len(specs)-up-dn}")
    print("  corpus jackknife of the no-classifier gain:")
    for drop in [None] + specs:
        ix = [i for i, t in enumerate(tiles) if t["specimen"] != drop]
        print(f"    drop {(drop or '(none)'):<20} "
              f"{TB._agg([rc[i] for i in ix])['iou']-TB._agg([r0[i] for i in ix])['iou']:+.4f}")
    rng = np.random.default_rng(3); perm = rng.permutation(len(tiles))
    print(f"  SABOTAGE shuffled gt {TB._agg([TB.counts(c, tiles[j]['gt']) for c, j in zip(cand, perm)])['iou']:.4f}"
          f"   180-rot {TB._agg([TB.counts(np.rot90(c,2), t['gt']) for c, t in zip(cand, tiles)])['iou']:.4f}")


def trivial_baselines(tiles, cand):
    for nm, pr in [("mark everything", [np.ones_like(t["gt"]) for t in tiles]),
                   ("global Otsu on img8", [t["img8"] < filters.threshold_otsu(t["img8"]) for t in tiles]),
                   ("accept ALL candidates", list(cand))]:
        m = TB._agg([TB.counts(p, t["gt"]) for p, t in zip(pr, tiles)])
        print(f"  {nm:<24} P {m['precision']:.4f} R {m['recall']:.4f} IoU {m['iou']:.4f}")


def sabotage(tiles, base, cl31):
    rng = np.random.default_rng(7); perm = rng.permutation(len(tiles))
    def ag(pr): return TB._agg([TB.counts(p, t["gt"]) for p, t in zip(pr, tiles)])["iou"]
    checks = [
        ("cl31 vs SHUFFLED gt", TB._agg([TB.counts(c, tiles[j]["gt"]) for c, j in zip(cl31, perm)])["iou"]),
        ("cl31 of 180-rotated prediction", ag([morphology.closing(np.rot90(p, 2), morphology.disk(31)) for p in base])),
        ("cl31 of a random equal-area mask", ag([morphology.closing(rng.random(t["gt"].shape) < max(p.mean(), 1e-9),
                                                                    morphology.disk(31)) for p, t in zip(base, tiles)])),
        ("closing of a constant-true mask", ag([np.ones_like(t["gt"]) for t in tiles])),
    ]
    ok = True
    for nm, v in checks:
        ok &= v <= 0.10
        print(f"  {'PASS' if v <= 0.10 else 'FAIL'}  {nm:<36} IoU {v:.4f}")
    ident = ag(list(base))
    print(f"  {'PASS' if abs(ident-0.2143) < 1e-3 else 'FAIL'}  closing r=0 falls back to baseline "
          f"IoU {ident:.4f}")
    return ok


def panel(tiles, base, cl31, out="beneficiary_260708.png"):
    """Look at the artifact. Left image, middle baseline, right closing.
    green = missed GT, red = FP, yellow = TP."""
    from PIL import Image
    j = next(i for i, t in enumerate(tiles) if t["specimen"] == BENEFICIARY)
    t = tiles[j]
    def rgb(pr):
        o = np.dstack([t["img8"]] * 3).astype(np.uint8)
        o[t["gt"] & ~pr] = [0, 160, 0]; o[pr & ~t["gt"]] = [220, 0, 0]
        o[t["gt"] & pr] = [255, 220, 0]
        return o
    Image.fromarray(np.concatenate(
        [np.dstack([t["img8"]] * 3), rgb(base[j]), rgb(cl31[j])], axis=1).astype(np.uint8)).save(out)
    print(f"  wrote {out}")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--all", action="store_true")
    ap.parse_args()
    print("CONTROLS"); assert TB.controls()
    tiles = TB.load()
    base, cand, cl31 = predictions(tiles)
    for title, fn in [
            ("1. REPRODUCE THE CLAIM", lambda: reproduce(tiles, base)),
            ("2. CACHE INTEGRITY (their stated open gap)", recut_check),
            ("3. SABOTAGE", lambda: sabotage(tiles, base, cl31)),
            ("4. IS THE GAIN ONE TILE?", lambda: bootstrap(tiles, *concentration(tiles, base, cl31))),
            ("5. GEOMETRY, OR JUST MORE PAINT?", lambda: equal_area_control(tiles, base, cl31)),
            ("6. NEVER-SWEPT HAND-LABELLED FRAMES", out_of_corpus),
            ("7. TRIVIAL BASELINES", lambda: trivial_baselines(tiles, cand)),
            ("8. THE TRIVIAL ALTERNATIVE THAT WINS: NO CLASSIFIER",
             lambda: no_classifier(tiles, base, cand, cl31)),
            ("9. LOOK AT THE ARTIFACT", lambda: panel(tiles, base, cl31))]:
        print(f"\n{'#'*78}\n### {title}\n{'#'*78}")
        fn()


if __name__ == "__main__":
    main()
