"""Did the U-Net learn anything the one-line threshold does not already know?

A tie on the headline can mean two very different things, and this separates them.

 1. IS IT THE SAME FUNCTION? Rank-correlate the U-Net's probability map against the
    darkness score the one-line threshold ranks by, over each tile. If the correlation is
    near 1 the network spent 70 million labelled pixels rediscovering `img < t` and the
    tie is an identity, not a coincidence. If it is low, two genuinely different functions
    are scoring the same, which is a statement about the LABELS rather than the methods.

 2. WHERE SHOULD IT WIN, AND DOES IT? Cracks on the additively-manufactured specimens are
    close to intensity-invisible (crack-vs-background separation d = +0.09 there against
    +1.10..+2.91 elsewhere), so a darkness threshold has nothing to work with and a
    learned context model should. That is a mechanism, stated before the test, so it is
    tested as a CORRELATION over all 26 tiles between a tile's own crack contrast and the
    U-Net's advantage on it -- not by picking the tiles where it happened to win.
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


def contrast(t):
    """Crack-vs-background separation on this tile, in robust sigmas of the flattened
    image. This is a property of the IMAGE and the LABEL only -- no method sees it -- so
    splitting on it cannot launder a score."""
    f = CC.prep(t)["flat"].astype(np.float32)
    g = t["gt"]
    bg = f[~g]
    s = np.median(np.abs(bg - np.median(bg))) * 1.4826
    return float((np.median(bg) - np.median(f[g])) / max(s, 1e-6))


def main(arm, seed, mode):
    tiles = CC.tiles()
    paint_specs = {B.specimen_of(n) for n in B.frame_names()}
    rows = []
    print(f"{'tile':<40} {'contrast':>9} {'rho(p,dark)':>12} {'uNet':>8} {'one-line':>9} "
          f"{'shipped':>8} {'d vs 1-line':>12}")
    print("-" * 104)
    for t in tiles:
        hold = t["specimen"] if t["specimen"] in paint_specs else None
        p = EV.tile_prob(arm, hold, t, seed)
        d = CC.prep(t)
        dark = -d["sm"].astype(np.float32)        # what the one-line threshold ranks by
        rho = float(stats.spearmanr(p.ravel()[::7], dark.ravel()[::7]).statistic)
        af = float(d["cur"].mean()) if mode == "area" else None
        mine = TR.mask_from_prob(p, area_frac=af)
        c_u = CC.cldice(mine, t["gt"]); c_t = CC.cldice(d["thr"], t["gt"])
        c_s = CC.cldice(d["cur"], t["gt"])
        rows.append(dict(frame=t["frame"], specimen=t["specimen"], contrast=contrast(t),
                         rho=rho, unet=c_u, oneline=c_t, shipped=c_s,
                         sf_u=skelf1(mine, t["gt"], 2), sf_t=skelf1(d["thr"], t["gt"], 2)))
        print(f"{t['frame'][:38]:<40} {rows[-1]['contrast']:9.2f} {rho:12.3f} "
              f"{c_u:8.4f} {c_t:9.4f} {c_s:8.4f} {c_u-c_t:+12.4f}")
    cs = np.array([r["contrast"] for r in rows])
    adv = np.array([r["unet"] - r["oneline"] for r in rows])
    rh = np.array([r["rho"] for r in rows])
    print("-" * 104)
    print(f"\n  rank correlation between the U-Net's map and plain darkness:")
    print(f"    median over tiles {np.median(rh):.3f}   range {rh.min():.3f} .. {rh.max():.3f}")
    sp = stats.spearmanr(cs, adv)
    print(f"\n  does the U-Net's advantage grow where darkness fails?")
    print(f"    Spearman(crack contrast, clDice advantage over the one-line threshold) "
          f"= {sp.statistic:+.3f}, p = {sp.pvalue:.4f}")
    print(f"    (the mechanism predicts a NEGATIVE correlation: more advantage at low "
          f"contrast)")
    lo = cs <= np.median(cs)
    print(f"    low-contrast half  (n={int(lo.sum())}): advantage {adv[lo].mean():+.4f}")
    print(f"    high-contrast half (n={int((~lo).sum())}): advantage {adv[~lo].mean():+.4f}")
    return dict(rows=rows, rho_median=float(np.median(rh)),
                spearman=float(sp.statistic), spearman_p=float(sp.pvalue),
                adv_low=float(adv[lo].mean()), adv_high=float(adv[~lo].mean()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="thin")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--mode", default="area")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    torch.set_num_threads(int(os.environ.get("NT", "4")))
    r = main(a.arm, a.seed, a.mode)
    if a.json:
        json.dump(r, open(a.json, "w"), indent=1, default=float)
