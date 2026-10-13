"""Score the U-Net arms on the 26 precise tiles, through ctx_core's instrument only.

The headline is clDice (median over tiles, exactly as the task's baseline table is made).
IoU is reported and never selected on: a physically correct 3 px trace scores IoU 0.2490
here, BELOW the shipped model, because the labels are a brush and IoU rewards width.

Each tile is predicted by the model whose training fold EXCLUDED that tile's specimen.
Thirteen of the 26 tiles come from four specimens with no painted frame at all, so for
those the all-paint model is already held out; the other nine specimens each get their
own fold. Both numbers are printed -- the held-out one and the train-on-all one -- and so
is the gap between them, because that gap is the overfit.

Readouts are parameter-free. `area` marks the same fraction of the tile the shipped
detector marks on that tile, so every arm is compared at equal area and no threshold is
fitted. `p50` is a fixed 0.5 cut. Both go through ctx_core.cand, the clean_mask + 40 px
filter every arm in the baseline table passes through.
"""
import os, sys, json, argparse
import numpy as np

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True
import torch
import unetctx_base as B
import unetctx_train as TR
import ctx_core as CC

OUT = os.path.join(B.MY, "probs")
os.makedirs(OUT, exist_ok=True)


def tile_prob(arm, holdout, tile, seed=0, stride=80, blend=False):
    """Cached probability map for one tile under one trained model."""
    tag = f"{arm}__{holdout or 'ALL'}__s{seed}{'__bl' if blend else ''}__{tile['frame']}.npy"
    f = os.path.join(OUT, tag)
    if os.path.exists(f):
        try:
            return np.load(f)
        except Exception:
            os.remove(f)
    d = CC.prep(tile)
    net = TR.load_net(TR.train_fold(arm, holdout, seed))
    p = (TR.predict_prob_blended(net, d["flat"].astype(np.uint8)) if blend
         else TR.predict_prob(net, d["flat"].astype(np.uint8), stride=stride))
    np.save(f, p.astype(np.float32))
    return p


def arm_rows(arm, tiles, mode, seed=0, heldout=True):
    """mode: 'area' (equal-area with the shipped detector) or 'p50'."""
    rows, masks = [], []
    paint_specs = {B.specimen_of(n) for n in B.frame_names()}
    for t in tiles:
        hold = t["specimen"] if (heldout and t["specimen"] in paint_specs) else None
        p = tile_prob(arm, hold, t, seed)
        d = CC.prep(t)
        af = float(d["cur"].mean()) if mode == "area" else None
        m = TR.mask_from_prob(p, area_frac=af)
        masks.append(m)
        rows.append(CC.row(m, t["gt"]))
    return rows, masks


def show(name, rows):
    m = CC.pooled(rows)
    print(f"  {name:<40} P {m['precision']:.4f}  R {m['recall']:.4f}  F1 {m['f1']:.4f}  "
          f"IoU {m['iou']:.4f}  clDice {m['cldice']:.4f}")
    return m


def baseline_rows(tiles):
    cur = [CC.row(CC.prep(t)["cur"], t["gt"]) for t in tiles]
    thr = [CC.row(CC.prep(t)["thr"], t["gt"]) for t in tiles]
    return cur, thr


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default=",".join(TR.ARMS))
    ap.add_argument("--probe", action="store_true",
                    help="all-paint model only, scored on the 13 tiles whose specimen "
                         "has no painted frame -- already held out, no fold needed")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    torch.set_num_threads(int(os.environ.get("NT", "10")))

    tiles = CC.tiles()
    paint_specs = {B.specimen_of(n) for n in B.frame_names()}
    if a.probe:
        tiles = [t for t in tiles if t["specimen"] not in paint_specs]
        print(f"PROBE: all-paint model on the {len(tiles)} tiles from "
              f"{len({t['specimen'] for t in tiles})} specimens with NO painted frame\n")
    cur, thr = baseline_rows(tiles)
    print("BASELINES on this tile set")
    res = {"baseline_current": show("CURRENT MODEL (v1.49.1)", cur),
           "baseline_threshold": show("one-line global threshold", thr),
           "baseline_trace": show("a correct 3 px trace",
                                  [CC.row(CC.correct_trace(t["gt"]), t["gt"]) for t in tiles])}
    print("\nU-NET ARMS (held-out by specimen)" if not a.probe else "\nU-NET ARMS")
    for arm in a.arms.split(","):
        for mode in ("area", "p50"):
            rows, masks = arm_rows(arm, tiles, mode, a.seed, heldout=not a.probe)
            res[f"{arm}__{mode}"] = show(f"{arm}  [{mode}]", rows)
            res[f"{arm}__{mode}"]["per_tile_cld"] = [r["cld"] for r in rows]
            res[f"{arm}__{mode}"]["area"] = float(np.mean([r["area"] for r in rows]))
    res["_tiles"] = [t["frame"] for t in tiles]
    res["_spec"] = [t["specimen"] for t in tiles]
    res["baseline_current"]["per_tile_cld"] = [r["cld"] for r in cur]
    res["baseline_threshold"]["per_tile_cld"] = [r["cld"] for r in thr]
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1, default=float)
        print(f"\nwrote {a.json}")
