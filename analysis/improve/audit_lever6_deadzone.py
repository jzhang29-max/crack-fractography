"""ADVERSARIAL AUDIT of improve/lever6_deadzone.py (claim: held-out IoU 0.2143 -> 0.5409).

VERDICT: the IoU claim SURVIVES. Every headline number reproduces to 4 decimals through
analysis/tilebench.py, selection is inside the fold, and the gain is not one specimen or
one tile. Two statements attached to it are WRONG and one is overstated.

REPRODUCED EXACTLY (26 tiles, 13 specimens, tilebench.py, controls pass):
    shipped baseline                 P 0.3378  R 0.3696  IoU 0.2143
    candidates only (no classifier)  P 0.4037  R 0.5402  IoU 0.3005   parameter-free
    + flatness veto (fixed 1.0)      P 0.8546  R 0.5394  IoU 0.4940
    mad_k x veto grid, LOSO          P 0.7976  R 0.6269  IoU 0.5409   fitted 0.5478, gap +0.0070
                                     picks mad3.0_r8_floor1.0 in 12/13 folds
    mad5-only sub-grid, LOSO         P 0.8408  R 0.5014  IoU 0.4579   (their own asterisk)
    mad_k-only WITH classifier       P 0.3383  R 0.4460  IoU 0.2382   (brief's best-known)

WHAT IS WRONG IN THE CLAIM

1. "13 improved, 0 regressed" is FALSE under every arm. Per-specimen held-out IoU against
   the shipped baseline:
       grid LOSO arm (the 0.5409 headline)   12 improved, 0 unchanged, 1 REGRESSED
       candidates-only and fixed veto        11 improved, 0 unchanged, 2 REGRESSED
   The grid arm's regression is total: 260622_316_amb_b3 goes 0.1927 -> 0.0000. That is the
   one fold where the selector picks floor=1.25, and that tile's entire crack is a single
   region whose relstd ratio is 1.137. Any floor above ~1.14 deletes 100% of its true
   positives (see ambb3 table below). lever6_deadzone.py never computes this count; it was
   asserted, not measured.

2. The PRECISION headline (0.3378 -> 0.7976) is the flooded tile, not the method. Off that
   one tile the shipped detector is already precise and the treatment is WORSE on precision:
       25 tiles, no flood:  baseline P 0.8925  ->  grid LOSO P 0.8012
   The real gain is recall and IoU, not precision. Quote precision only with the flood tile
   named, or quote the 25-tile pair.

3. "Parameter-free 0.4940" is a half-claim, as the author admits. The honest
   data-picked-the-floor number is 0.4579. The honest fully-parameter-free number is
   candidates-only, 0.3005.

WHAT SURVIVES (the reason the verdict is not a rejection)

  * NOT one tile. Held-out IoU with the flooded tile dropped from the aggregate: 0.5422
    (vs 0.5409 with it). The 25-tile ladder is baseline 0.3550 -> candidates-only 0.4837
    -> veto 0.4946 -> grid LOSO 0.5422. The veto is worth only +0.011 off the flood, but
    deleting the classifier (+0.129) and loosening mad_k (+0.048) are not flood effects.
  * NOT one specimen. Leave-one-specimen-out jackknife of the whole comparison: the gain
    over baseline stays between +0.193 and +0.350 IoU for every specimen dropped. Worst
    case is dropping MAR_H_HIP (which owns the flood tile): 0.3414 -> 0.5343.
  * NO LEAKAGE FOUND. predict() reads only img8; the relstd floor is normalised by the
    tile's OWN median local std, not by anything label-derived; TB.evaluate does the
    LOSO selection and the whole 40-variant grid is handed to it. One instrument
    throughout -- no second scorer, no changed exclusion list, no changed tolerance.
  * SABOTAGE COLLAPSES IT (all through tilebench):
        constant input image           IoU 0.0000, 0 predicted px
        shuffled ground truth          IoU 0.0069
        relstd recomputed from noise   IoU 0.1611 (26) / 0.2654 (25) -- below candidates-only
        shuffle relstd across regions, 200 draws:
            mad5 r16  26 tiles  null 0.3041 +/- 0.0409  real 0.4940
                      25 tiles  null 0.4772 +/- 0.0052  real 0.4946  (+3.3 sd, effect +0.017)
            mad3 r8   25 tiles  null 0.4909 +/- 0.0192  real 0.5492  (+3.0 sd)
        area-matched random region keep, 200 draws:
            mad5 r16  25 tiles  null 0.4835 +/- 0.0037  real 0.4946  (+3.0 sd, effect +0.011)
            mad3 r8   25 tiles  null 0.5167 +/- 0.0063  real 0.5492  (+5.1 sd, effect +0.033)
    i.e. off the flood tile the veto beats "delete the same amount of area at random" by
    +0.011 to +0.033 IoU, not by the +0.19 the pooled table suggests.
  * IT DOES NOT BUY PRECISION BY DELETING CRACK. The veto removes 143,082 FP px and only
    168 TP px; 137,774 of the FP (96.3%) are the single off-specimen void. At floor 1.0 no
    tile loses its main crack region (min best-TP-region ratio 1.137, median 3.67); the
    worst TP loss on any tile is 7.95% of TP area (HIP_24hr).
  * BETTER THAN THE TRIVIAL ALTERNATIVES. mark-everything IoU 0.0297. A plain global
    percentile threshold, no flat-field and no model, LOSO over 7 percentiles: held-out
    IoU 0.2844 (0.4106 off the flood) -- which already beats the shipped detector, but is
    far below 0.5409. mad_k-only with the classifier: 0.2382.

NUMBER TO QUOTE: held-out IoU 0.5409 (P 0.7976, R 0.6269, F1 0.7020), two LOSO-selected
parameters, overfit gap +0.0070; 0.5422 with the flooded tile excluded; 12 of 13 specimens
improved and 260622_316_amb_b3 regressed to zero.

Run:  /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python -B audit_lever6_deadzone.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from scipy import ndimage as ndi
import tilebench as TB
import crackpipe as CP
import detect_cracks as D
import lever6_deadzone as L6

FLOOD = L6.FLOOD
MADS, RADII, FLOORS = (5.0, 4.0, 3.0, 2.5), (8, 16), (0.0, 0.75, 1.0, 1.25, 1.5)


def agg(rows):
    tp = sum(r["tp"] for r in rows); fp = sum(r["fp"] for r in rows); fn = sum(r["fn"] for r in rows)
    p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
    return dict(p=p, r=r, iou=tp / max(tp + fp + fn, 1), tp=tp, fp=fp, fn=fn)


def precompute(tiles):
    """Per (tile, mad_k): the candidate labelling and each region's relstd ratio.

    Hoisting this out of the grid is the only reason a 40-variant sweep is cheap; the
    masks it produces are identical to L6.predict's (asserted in main)."""
    store = {}
    for ti, t in enumerate(tiles):
        for mk in MADS:
            st = CP.stages(t["img8"], mad_k=mk)
            lab, n = ndi.label(st["clean"])
            d = dict(lab=lab, n=n, ratios={}, size=np.bincount(lab.ravel(), minlength=n + 1)[1:])
            for r in RADII:
                s = L6.local_std(st["flat"], r)
                base = max(float(np.median(s)), 1e-6)
                med = (ndi.labeled_comprehension(s, lab, np.arange(1, n + 1), np.median, float, 0.0)
                       if n else np.zeros(0))
                d["ratios"][r] = med / base
            store[(ti, mk)] = d
        print(f"  precompute {ti + 1}/{len(tiles)}", flush=True)
    return store


def mask_for(store, ti, mk, r, fl):
    d = store[(ti, mk)]
    if fl <= 0:
        return d["lab"] > 0
    return np.concatenate([[False], d["ratios"][r] >= fl])[d["lab"]]


def loso(tiles, grid, idx=None, baseline=None):
    """Leave-one-SPECIMEN-out selection, optionally aggregating over a tile subset."""
    specs = sorted({t["specimen"] for t in tiles}); keys = list(grid)
    held, hb = [], []
    for sp in specs:
        tr = [i for i, t in enumerate(tiles) if t["specimen"] != sp]
        te = [i for i, t in enumerate(tiles) if t["specimen"] == sp]
        best = max(keys, key=lambda k: agg([grid[k][i] for i in tr])["iou"])
        held += [grid[best][i] for i in te if idx is None or i in idx]
        if baseline is not None:
            hb += [baseline[i] for i in te if idx is None or i in idx]
    return (agg(held), agg(hb)) if baseline is not None else agg(held)


def main():
    print("CONTROLS"); assert TB.controls(), "harness controls failed"
    tiles = TB.load()
    fi = next(i for i, t in enumerate(tiles) if t["frame"] == FLOOD)
    keep25 = [i for i in range(len(tiles)) if i != fi]

    base = [CP.predict(t["img8"]) for t in tiles]
    bc = [TB.counts(m, t["gt"]) for m, t in zip(base, tiles)]
    store = precompute(tiles)

    # the precompute shortcut must give byte-identical masks to the claimed implementation
    for ti in (0, fi, len(tiles) - 1):
        assert np.array_equal(mask_for(store, ti, 5.0, 16, 1.0),
                              L6.predict(tiles[ti]["img8"], 5.0, 16, 1.0)), "precompute diverged"
    print("  precompute matches L6.predict on 3 spot-checked tiles")

    grid = {f"mad{mk}_r{r}_floor{fl}": [TB.counts(mask_for(store, ti, mk, r, fl), t["gt"])
                                        for ti, t in enumerate(tiles)]
            for mk in MADS for r in RADII for fl in FLOORS}
    cand = {k: v for k, v in grid.items() if k == "mad5.0_r8_floor0.0"}
    veto = {k: v for k, v in grid.items() if k == "mad5.0_r16_floor1.0"}

    print("\n== REPRODUCTION ==")
    TB.evaluate("shipped baseline", {"x": bc})
    TB.evaluate("candidates only [parameter-free]", cand)
    TB.evaluate("+ flatness veto floor 1.0 [floor chosen after looking]", veto)
    TB.evaluate("mad5-only sub-grid [floor LOSO-selected]",
                {k: v for k, v in grid.items() if k.startswith("mad5.0")})
    TB.evaluate("mad_k x veto grid [2 params, LOSO]", grid)

    print("\n== IS IT ONE TILE?  (pooled 26 vs pooled 25 without the flooded tile) ==")
    for nm, rows in [("baseline", bc), ("candidates only", cand["mad5.0_r8_floor0.0"]),
                     ("+ veto", veto["mad5.0_r16_floor1.0"])]:
        a, b = agg(rows), agg([rows[i] for i in keep25])
        print(f"  {nm:18s} 26: IoU {a['iou']:.4f} P {a['p']:.4f} R {a['r']:.4f}"
              f" | 25: IoU {b['iou']:.4f} P {b['p']:.4f} R {b['r']:.4f}")
    g26, g25 = loso(tiles, grid), loso(tiles, grid, keep25)
    print(f"  {'grid LOSO':18s} 26: IoU {g26['iou']:.4f} P {g26['p']:.4f} R {g26['r']:.4f}"
          f" | 25: IoU {g25['iou']:.4f} P {g25['p']:.4f} R {g25['r']:.4f}")
    print("  -> IoU survives the flood tile; PRECISION does not (0.8925 -> 0.8012 off it).")

    print("\n== IS IT ONE SPECIMEN?  (held-out gain with each specimen dropped) ==")
    worst = 1.0
    for sp in [None] + sorted({t["specimen"] for t in tiles}):
        idx = [i for i, t in enumerate(tiles) if t["specimen"] != sp]
        g, b = loso(tiles, grid, idx, bc)
        worst = min(worst, g["iou"] - b["iou"])
        print(f"  drop {str(sp):24s} baseline {b['iou']:.4f} -> {g['iou']:.4f} ({g['iou'] - b['iou']:+.4f})")
    print(f"  smallest gain over any single-specimen jackknife: {worst:+.4f}")

    print("\n== PER-SPECIMEN HELD-OUT, and the improved/regressed count the claim got wrong ==")
    specs = sorted({t["specimen"] for t in tiles}); keys = list(grid)
    cnt = [0, 0, 0]
    for sp in specs:
        tr = [i for i, t in enumerate(tiles) if t["specimen"] != sp]
        te = [i for i, t in enumerate(tiles) if t["specimen"] == sp]
        best = max(keys, key=lambda k: agg([grid[k][i] for i in tr])["iou"])
        g = agg([grid[best][i] for i in te])["iou"]; b = agg([bc[i] for i in te])["iou"]
        cnt[0 if g - b > 1e-6 else (2 if g - b < -1e-6 else 1)] += 1
        print(f"  {sp:22s} n={len(te)}  {b:.4f} -> {g:.4f} ({g - b:+.4f})  pick {best}")
    print(f"  improved/unchanged/REGRESSED = {tuple(cnt)}   (claim said 13/0/0)")

    print("\n== THE CLIFF: 260622_316_amb_b3 is all-or-nothing in the floor ==")
    ti = next(i for i, t in enumerate(tiles) if t["specimen"] == "260622_316_amb_b3")
    for fl in FLOORS:
        r = grid[f"mad3.0_r8_floor{fl}"][ti]
        print(f"  mad3.0 r8 floor {fl:<5} tp {r['tp']:5d} fp {r['fp']:6d} "
              f"IoU {r['tp'] / max(r['tp'] + r['fp'] + r['fn'], 1):.4f}")

    print("\n== DOES IT DELETE CRACK TO BUY PRECISION? ==")
    tpr = fpr = 0
    for ti in range(len(tiles)):
        rm = mask_for(store, ti, 5.0, 16, 0.0) & ~mask_for(store, ti, 5.0, 16, 1.0)
        tpr += int((rm & tiles[ti]["gt"]).sum()); fpr += int((rm & ~tiles[ti]["gt"]).sum())
    rmf = mask_for(store, fi, 5.0, 16, 0.0) & ~mask_for(store, fi, 5.0, 16, 1.0)
    print(f"  veto removes {fpr} FP and {tpr} TP; the flooded tile alone is "
          f"{int((rmf & ~tiles[fi]['gt']).sum())} FP ({int((rmf & ~tiles[fi]['gt']).sum()) / fpr:.1%})")

    print("\n== SABOTAGE ==")
    rng = np.random.default_rng(0)
    def score(mk, sel, idx=None):
        rows = [TB.counts(np.concatenate([[False], sel(store[(ti, mk)], ti)])[store[(ti, mk)]["lab"]],
                          t["gt"]) for ti, t in enumerate(tiles)]
        return agg(rows if idx is None else [rows[i] for i in idx])["iou"]

    for mk, r in ((5.0, 16), (3.0, 8)):
        real26, real25 = score(mk, lambda d, ti: d["ratios"][r] >= 1.0), \
                         score(mk, lambda d, ti: d["ratios"][r] >= 1.0, keep25)
        v26, v25 = [], []
        for _ in range(200):
            perm = {ti: rng.permutation(store[(ti, mk)]["ratios"][r]) for ti in range(len(tiles))}
            f = lambda d, ti: perm[ti] >= 1.0
            v26.append(score(mk, f)); v25.append(score(mk, f, keep25))
        print(f"  shuffle-relstd mad{mk} r{r}: real 26 {real26:.4f} vs null {np.mean(v26):.4f}"
              f"+/-{np.std(v26):.4f} | real 25 {real25:.4f} vs null {np.mean(v25):.4f}+/-{np.std(v25):.4f}"
              f"  ({(real25 - np.mean(v25)) / max(np.std(v25), 1e-9):+.1f} sd off the flood)", flush=True)

        a26, a25 = [], []
        for _ in range(200):
            sel = {}
            for ti in range(len(tiles)):
                d = store[(ti, mk)]
                if d["n"] == 0:
                    sel[ti] = np.zeros(0, bool); continue
                target = d["size"][d["ratios"][r] >= 1.0].sum()
                k = np.zeros(d["n"], bool); tot = 0
                for j in rng.permutation(d["n"]):
                    if tot >= target: break
                    k[j] = True; tot += d["size"][j]
                sel[ti] = k
            f = lambda d, ti: sel[ti]
            a26.append(score(mk, f)); a25.append(score(mk, f, keep25))
        print(f"  area-matched-random mad{mk} r{r}: real 25 {real25:.4f} vs null {np.mean(a25):.4f}"
              f"+/-{np.std(a25):.4f}  ({(real25 - np.mean(a25)) / max(np.std(a25), 1e-9):+.1f} sd)", flush=True)

    rows = []
    for ti, t in enumerate(tiles):
        d = store[(ti, 5.0)]
        s = L6.local_std(rng.normal(0, 1, t["img8"].shape).astype(np.float32), 16)
        bb = max(float(np.median(s)), 1e-6)
        med = (ndi.labeled_comprehension(s, d["lab"], np.arange(1, d["n"] + 1), np.median, float, 0.0)
               if d["n"] else np.zeros(0))
        rows.append(TB.counts(np.concatenate([[False], med / bb >= 1.0])[d["lab"]], t["gt"]))
    print(f"  relstd recomputed from NOISE: 26 {agg(rows)['iou']:.4f}  25 "
          f"{agg([rows[i] for i in keep25])['iou']:.4f}   (candidates-only is 0.3005 / 0.4837)")

    rows = [TB.counts(L6.predict(np.full_like(t["img8"], 128), 5.0, 16, 1.0), t["gt"]) for t in tiles]
    print(f"  constant input image: IoU {agg(rows)['iou']:.4f}, predicted px "
          f"{sum(r['tp'] + r['fp'] for r in rows)}")
    perm = rng.permutation(len(tiles))
    rows = [TB.counts(L6.predict(t["img8"], 5.0, 16, 1.0), tiles[perm[i]]["gt"]) for i, t in enumerate(tiles)]
    print(f"  shuffled ground truth: IoU {agg(rows)['iou']:.4f}")

    print("\n== TRIVIAL ALTERNATIVES ==")
    mg = {f"clf_mad{mk}": [TB.counts(CP.predict(t["img8"], mad_k=mk), t["gt"]) for t in tiles]
          for mk in (5.0, 4.0, 3.5, 3.0, 2.5, 2.0)}
    m = loso(tiles, mg)
    print(f"  mad_k-only WITH the shipped classifier: P {m['p']:.4f} R {m['r']:.4f} IoU {m['iou']:.4f}")
    tg = {}
    for q in (1, 2, 3, 4, 5, 7, 10):
        tg[f"pct{q}"] = [TB.counts(D.clean_mask(t["img8"] <= np.percentile(t["img8"], q),
                                                open_radius=1, close_radius=3, min_area_px=13),
                                   t["gt"]) for t in tiles]
    a, b = loso(tiles, tg), loso(tiles, tg, keep25)
    print(f"  global percentile threshold, no flat-field, no model: IoU {a['iou']:.4f} "
          f"(26) / {b['iou']:.4f} (25)")
    print("  mark-everything: IoU 0.0297 (== prevalence, from TB.controls)")


if __name__ == "__main__":
    main()
