"""STEP 0 -- reproduce the brief's table before interpreting anything in it.

A workflow that quotes "clDice 0.6405 vs 0.6205" and then argues about a 0.02 difference is
unreadable unless both numbers come out of this process. So: rebuild all six arms, print
precision / recall / F1 / IoU / clDice, and show the pooled-vs-mean clDice side by side so
the aggregation that produced the headline is on the record.

Also runs the harness controls (perfect / empty / mark-everything) and the sabotage arms
(shuffled labels, rotated labels, constant input), because a scoring instrument that cannot
fail is not measuring anything.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import approach4_lib as L
from scipy import ndimage as ndi


def main():
    tiles = L.tiles_with_arms()
    specs = sorted({t["specimen"] for t in tiles})
    print(f"{len(tiles)} tiles, {len(specs)} specimens\n")

    # ---- the one-line arm and Frangi are families; LOSO-select inside each, on clDice
    rows = {}
    for key in tiles[0]["arms"]:
        rows[key] = [L.score_tile(t["arms"][key], t["gt"], sgt=t["skel_gt"]) for t in tiles]

    onel = [k for k in rows if k.startswith("oneline_")]
    fran = [k for k in rows if k.startswith("frangi_")]
    held_ol, picks_ol, fit_ol = L.loso_pick(tiles, rows, onel)
    held_fr, picks_fr, fit_fr = L.loso_pick(tiles, rows, fran)

    arms = [("CURRENT MODEL (v1.49.1)", rows["current"]),
            ("one-line threshold (LOSO)", held_ol),
            ("a correct 3 px trace", rows["trace3"]),
            ("ridge filter (Frangi, LOSO)", held_fr),
            ("random, area-matched", rows["random"]),
            ("mark everything", rows["markall"]),
            ("empty", rows["empty"])]

    hdr = f"{'arm':<30}{'prec':>8}{'recall':>8}{'F1':>8}{'IoU':>8}{'clDice':>9}{'clD-pool':>10}{'Tprec':>8}{'Tsens':>8}"
    print(hdr); print("-" * len(hdr))
    out = {}
    for name, r in arms:
        m = L.pool(r)
        out[name] = m
        print(f"{name:<30}{m['precision']:8.4f}{m['recall']:8.4f}{m['f1']:8.4f}"
              f"{m['iou']:8.4f}{m['cldice_mean']:9.4f}{m['cldice_pooled']:10.4f}"
              f"{m['tprec_mean']:8.4f}{m['tsens_mean']:8.4f}")
    print(f"\n  one-line LOSO picks: {sorted(set(picks_ol.values()))}  (fitted-on-all: {fit_ol})")
    print(f"  Frangi   LOSO picks: {sorted(set(picks_fr.values()))}  (fitted-on-all: {fit_fr})")

    # ---- controls
    print("\nCONTROLS (must come out right or no number above is readable)")
    perfect = [L.score_tile(t["gt"], t["gt"], sgt=t["skel_gt"]) for t in tiles]
    mp = L.pool(perfect)
    print(f"  perfect (gt itself)   IoU {mp['iou']:.4f}  clDice {mp['cldice_mean']:.4f}"
          f"   -- expect 1.0000 / 1.0000")
    me = L.pool(rows["empty"])
    print(f"  empty                 IoU {me['iou']:.4f}  clDice {me['cldice_mean']:.4f}"
          f"   -- expect 0.0000 / 0.0000")
    ma = L.pool(rows["markall"])
    prev = sum(int(t["gt"].sum()) for t in tiles) / sum(t["gt"].size for t in tiles)
    print(f"  mark everything       prec {ma['precision']:.4f}  -- expect prevalence {prev:.4f}")

    # ---- sabotage
    print("\nSABOTAGE (a broken version must NOT score well)")
    rng = np.random.default_rng(7)
    sab = {}
    perm = rng.permutation(len(tiles))
    sab["labels shuffled between tiles"] = [
        L.score_tile(tiles[i]["arms"]["current"], tiles[perm[i]]["gt"]) for i in range(len(tiles))]
    sab["labels rotated 90 deg"] = [
        L.score_tile(t["arms"]["current"], np.rot90(t["gt"])) for t in tiles]
    sab["labels mirrored"] = [
        L.score_tile(t["arms"]["current"], t["gt"][:, ::-1]) for t in tiles]
    const = []
    for t in tiles:
        flat = np.full_like(t["img8"], int(np.median(t["img8"])))
        try:
            p = L.current_stages(flat)["pred"]
        except Exception:
            p = np.zeros_like(t["gt"])
        const.append(L.score_tile(p, t["gt"], sgt=t["skel_gt"]))
    sab["constant input image"] = const
    for nm, r in sab.items():
        m = L.pool(r)
        print(f"  {nm:<32} IoU {m['iou']:.4f}  clDice {m['cldice_mean']:.4f}"
              f"  (real: IoU {out['CURRENT MODEL (v1.49.1)']['iou']:.4f} "
              f"clDice {out['CURRENT MODEL (v1.49.1)']['cldice_mean']:.4f})")

    json.dump({k: v for k, v in out.items()},
              open(os.path.join(L.WORK, "reproduce.json"), "w"), indent=1)
    print("\nwrote", os.path.join(L.WORK, "reproduce.json"))


if __name__ == "__main__":
    main()
