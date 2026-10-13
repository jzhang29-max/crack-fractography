"""APPROACH 2 -- THE WHOLE RESULT. Paired over the 13 specimens, against both baselines
and against the nulls that the instrument itself requires.

Three things this file refuses to do, because each is how a tie gets reported as a win.

 1. QUOTE A MEDIAN DIFFERENCE AS A GAIN. clDice is pooled here as the median over tiles,
    which is how the brief's table is made, and a median moves when one tile crosses the
    middle rank. Every claim is therefore ALSO reported paired per specimen -- mean
    clDice within a specimen, Wilcoxon across the 13 -- which is the unit the brief
    requires. The two can disagree completely and in this project they do.

 2. SCORE A WIDER MASK AND CALL IT BETTER. A peer session established that clDice on
    these labels is partly a width contest: its tsens half asks whether the LABEL's
    8.7 px-wide medial axis was covered, so isotropic dilation -- which adds no
    information at all -- moves clDice +0.0478 on 13 specimens of 13. The primary
    readout here is therefore AREA-MATCHED: the U-Net marks exactly the number of pixels
    the shipped detector marks on that tile. A dilation null is run anyway, for the
    readouts that are not area-matched.

 3. REPORT ONE INSTRUMENT. clDice is the brief's primary and is reported first.
    skeleton-F1 at tau=2 (ctx_metric.skelf1) is reported beside it because its dilation
    null reads flat, so it can tell a real length gain from a width gain.
"""
import os, sys, json, argparse
import numpy as np
from scipy import stats

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True
import torch
import unetctx_base as B
import unetctx_train as TR
import unetctx_eval as EV
import ctx_core as CC
from ctx_metric import skelf1
from ctx_matched import dilate_to_area

TAU = 2


def measure(masks, tiles):
    out = []
    for m, t in zip(masks, tiles):
        r = CC.row(m, t["gt"])
        r["iou"] = r["tp"] / max(r["tp"] + r["fp"] + r["fn"], 1)
        r["skelf1"] = skelf1(m, t["gt"], TAU)
        r["specimen"] = t["specimen"]
        out.append(r)
    return out


def byspec(rows, key, specs):
    o = {}
    for r in rows:
        o.setdefault(r["specimen"], []).append(r[key])
    return np.array([float(np.mean(o[s])) for s in specs])


def paired(a_rows, b_rows, specs, key):
    a, b = byspec(a_rows, key, specs), byspec(b_rows, key, specs)
    d = a - b
    p = float(stats.wilcoxon(a, b).pvalue) if np.any(d != 0) else 1.0
    return dict(mean_d=float(d.mean()), median_d=float(np.median(d)),
                up=int((d > 0).sum()), down=int((d < 0).sum()), p=p)


def line(name, rows):
    cl = float(np.median([r["cld"] for r in rows]))
    sf = float(np.median([r["skelf1"] for r in rows]))
    tp = sum(r["tp"] for r in rows); fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return dict(name=name, cldice=cl, skelf1=sf, precision=pr, recall=rc,
                f1=2 * pr * rc / max(pr + rc, 1e-12), iou=tp / max(tp + fp + fn, 1),
                area=float(np.mean([r["area"] for r in rows])))


def show(m):
    print(f"  {m['name']:<40} clDice {m['cldice']:.4f}  skelF1@2 {m['skelf1']:.4f}  "
          f"P {m['precision']:.4f}  R {m['recall']:.4f}  IoU {m['iou']:.4f}  "
          f"area {m['area']:>8.0f}")


def main(arm, seeds, modes, do_sabotage):
    tiles = CC.tiles()
    specs = sorted({t["specimen"] for t in tiles})
    paint_specs = {B.specimen_of(n) for n in B.frame_names()}
    res = {"arm": arm, "specimens": specs, "n_tiles": len(tiles)}

    cur_m = [CC.prep(t)["cur"] for t in tiles]
    thr_m = [CC.prep(t)["thr"] for t in tiles]
    cur, thr = measure(cur_m, tiles), measure(thr_m, tiles)
    print("BASELINES, 26 tiles")
    res["shipped"] = line("CURRENT MODEL (v1.49.1)", cur); show(res["shipped"])
    res["threshold"] = line("one-line global threshold", thr); show(res["threshold"])
    tr = measure([CC.correct_trace(t["gt"]) for t in tiles], tiles)
    res["trace"] = line("a correct 3 px trace", tr); show(res["trace"])

    print("\nU-NET, held out by specimen (a tile is never scored by a model that "
          "saw its specimen)")
    store = {}
    for mode in modes:
        for seed in seeds:
            rows_s, masks_s = [], []
            bl = mode.endswith("_bl")
            base = mode[:-3] if bl else mode
            for t in tiles:
                hold = t["specimen"] if t["specimen"] in paint_specs else None
                p = EV.tile_prob(arm, hold, t, seed, blend=bl)
                af = float(CC.prep(t)["cur"].mean()) if base == "area" else None
                masks_s.append(TR.mask_from_prob(p, area_frac=af))
            rows_s = measure(masks_s, tiles)
            k = f"{arm}__{mode}__s{seed}"
            store[k] = (rows_s, masks_s)
            res[k] = line(f"{arm} [{mode}] seed {seed}  HELD-OUT", rows_s)
            show(res[k])
            for bname, brows in (("vs shipped", cur), ("vs one-line", thr)):
                for key, lab in (("cld", "clDice"), ("skelf1", "skelF1@2")):
                    q = paired(rows_s, brows, specs, key)
                    res[f"{k}__{bname}__{key}"] = q
                    print(f"      paired {lab:<9} {bname:<11} {q['mean_d']:+.4f}  "
                          f"better {q['up']:>2}/{len(specs)}  worse {q['down']:>2}  "
                          f"p {q['p']:.4f}")

    # THE SEED ENSEMBLE. Three seeds on identical data span 0.11 clDice on the probe
    # tiles -- wider than the whole gap to the baselines -- so a single seed's score is
    # not a property of the method. Averaging the three probability maps is the standard
    # answer and costs no new parameter.
    print("\nSEED ENSEMBLE (mean of the three seeds' probability maps, area-matched)")
    ens = []
    for t in tiles:
        hold = t["specimen"] if t["specimen"] in paint_specs else None
        pm = np.mean([EV.tile_prob(arm, hold, t, sd) for sd in seeds], 0)
        ens.append(TR.mask_from_prob(pm, area_frac=float(CC.prep(t)["cur"].mean())))
    rows_e = measure(ens, tiles)
    res["ensemble"] = line(f"{arm} x{len(seeds)} seeds [area]", rows_e)
    show(res["ensemble"])
    for key, lab in (("cld", "clDice"), ("skelf1", "skelF1@2")):
        for nm, br in (("vs shipped", cur), ("vs one-line", thr)):
            q = paired(rows_e, br, specs, key)
            res[f"ensemble__{nm}__{key}"] = q
            print(f"      paired {lab:<9} {nm:<12} {q['mean_d']:+.4f}  "
                  f"better {q['up']:>2}/{len(specs)}  worse {q['down']:>2}  p {q['p']:.4f}")
    store[f"{arm}__area__ENS"] = (rows_e, ens)

    # The ADDITIVE form. A replacement cannot pass the full-frame paint gate -- the gate
    # asks that the arm keep what the shipped path keeps, so only a superset can. The
    # union is that superset, and it deletes nothing by construction. Its extra area is
    # then matched against a blind dilation, because clDice pays for area.
    print("\nADDITIVE FORM (shipped | u-net), and the blind dilation that adds the "
          "same area")
    k0 = f"{arm}__area__ENS"
    uni = [a | b for a, b in zip(store[k0][1], cur_m)]
    rows_u = measure(uni, tiles)
    res["union"] = line("shipped | u-net", rows_u); show(res["union"])
    extra = int(round(res["union"]["area"] - res["shipped"]["area"]))
    dilu = [dilate_to_area(c, extra) for c in cur_m]
    rows_dl = measure(dilu, tiles)
    res["union_null"] = line(f"shipped dilated by the same {extra} px (no information)",
                             rows_dl)
    show(res["union_null"])
    for key, lab in (("cld", "clDice"), ("skelf1", "skelF1@2")):
        for nm, br in (("vs shipped", cur), ("vs blind dilation", rows_dl)):
            q = paired(rows_u, br, specs, key)
            res[f"union__{nm}__{key}"] = q
            print(f"      paired {lab:<9} {nm:<18} {q['mean_d']:+.4f}  "
                  f"better {q['up']:>2}/{len(specs)}  worse {q['down']:>2}  p {q['p']:.4f}")

    # train-on-all, the optimistic number, for the overfit gap
    print("\nTRAIN-ON-ALL (optimistic -- every tile's specimen WAS in training)")
    for mode in modes:
        masks_a = []
        bl = mode.endswith("_bl")
        base = mode[:-3] if bl else mode
        for t in tiles:
            p = EV.tile_prob(arm, None, t, seeds[0], blend=bl)
            af = float(CC.prep(t)["cur"].mean()) if base == "area" else None
            masks_a.append(TR.mask_from_prob(p, area_frac=af))
        rows_a = measure(masks_a, tiles)
        res[f"{arm}__{mode}__TRAINALL"] = line(f"{arm} [{mode}] train-on-all", rows_a)
        show(res[f"{arm}__{mode}__TRAINALL"])
        g = res[f"{arm}__{mode}__TRAINALL"]["cldice"] - res[f"{arm}__{mode}__s{seeds[0]}"]["cldice"]
        res[f"overfit_gap__{mode}"] = float(g)
        print(f"      overfit gap on clDice: {g:+.4f}")

    # the null the instrument needs: same extra area, no information
    print("\nNULLS")
    for mode in modes:
        k = f"{arm}__{mode}__s{seeds[0]}"
        extra = res[k]["area"] - res["shipped"]["area"]
        if extra > 1:
            dil = [dilate_to_area(c, int(round(extra))) for c in cur_m]
            rows_d = measure(dil, tiles)
            res[f"null_dilate__{mode}"] = line(
                f"shipped dilated to {mode} arm's area (no information)", rows_d)
            show(res[f"null_dilate__{mode}"])
            q = paired(store[k][0], rows_d, specs, "cld")
            res[f"{k}__vs_dilate__cld"] = q
            print(f"      paired clDice  vs dilation null  {q['mean_d']:+.4f}  "
                  f"better {q['up']}/{len(specs)}  p {q['p']:.4f}")
        else:
            print(f"  [{mode}] area-matched to the shipped mask by construction "
                  f"({res[k]['area']:.0f} vs {res['shipped']['area']:.0f} px) -- "
                  f"the dilation null does not apply")

    print("\nPER-SPECIMEN clDice (mean over that specimen's tiles) -- the paired unit.")
    k0 = f"{arm}__{modes[0]}__s{seeds[0]}"
    a = byspec(store[k0][0], "cld", specs)
    b = byspec(cur, "cld", specs); c = byspec(thr, "cld", specs)
    sa = byspec(store[k0][0], "skelf1", specs); sb = byspec(cur, "skelf1", specs)
    print(f"  {'specimen':<20} {'u-net':>8} {'shipped':>8} {'one-line':>9} "
          f"{'d vs ship':>10} | {'uNet sF1':>9} {'ship sF1':>9}")
    for i, sp in enumerate(specs):
        print(f"  {sp:<20} {a[i]:8.4f} {b[i]:8.4f} {c[i]:9.4f} {a[i]-b[i]:+10.4f} | "
              f"{sa[i]:9.4f} {sb[i]:9.4f}")
    print(f"  {'spread (sd)':<20} {a.std():8.4f} {b.std():8.4f} {c.std():9.4f}")
    res["per_specimen"] = {sp: dict(unet=float(a[i]), shipped=float(b[i]),
                                    oneline=float(c[i])) for i, sp in enumerate(specs)}
    res["spread"] = dict(unet=float(a.std()), shipped=float(b.std()), oneline=float(c.std()))
    dead_b = [specs[i] for i in range(len(specs)) if b[i] < 0.05]
    dead_a = [specs[i] for i in range(len(specs)) if a[i] < 0.05]
    print(f"  specimens near zero: shipped {dead_b or 'none'};  u-net {dead_a or 'none'}")
    res["dead_shipped"] = dead_b; res["dead_unet"] = dead_a

    if do_sabotage:
        print("\nSABOTAGE (all-paint model, scored on all 26 tiles -- the most "
              "favourable setting for a broken method)")
        for sab in ("sab_shuffle", "sab_rot", "sab_const"):
            try:
                masks_x = []
                for t in tiles:
                    p = EV.tile_prob(sab, None, t, seeds[0])
                    masks_x.append(TR.mask_from_prob(
                        p, area_frac=float(CC.prep(t)["cur"].mean())))
                res[sab] = line(f"{sab} [area]", measure(masks_x, tiles))
                show(res[sab])
            except Exception as e:
                print(f"  {sab}: {e}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="thin")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--modes", default="area,p50")
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    torch.set_num_threads(int(os.environ.get("NT", "4")))
    r = main(a.arm, [int(s) for s in a.seeds.split(",")], a.modes.split(","), a.sabotage)
    if a.json:
        json.dump(r, open(a.json, "w"), indent=1, default=float)
        print("\nwrote " + a.json)
