"""Controls the additive arm has to beat before its gain means anything.

An additive rule adds area, and adding area moves clDice on its own: Tsens can only rise
when the mask grows. So "union the current mask with the net" must be compared against
"union the current mask with something that knows nothing", at the SAME added area, on
the same tiles, through the same scorer. Four comparators:

    random blobs       smoothed noise thresholded to the net's own added area per tile.
                       An information-free comparator -- it must score near the current
                       model or the metric is rewarding area, not detection.
    Frangi             a ridge filter at the net's added area. The strongest no-learning
                       rival the project has, and the arm the brief already names.
    darkest-first      the darkest unmarked pixels of the flattened image, matched area.
                       This is the one-line threshold extended additively.
    3 px trace         the physically correct answer unioned in. Not reachable -- it uses
                       the label -- it is the CEILING an additive rule can reach, so a
                       method near the random control and far from this one has found
                       nothing.

    python -B scl_controls.py --tag main --loss thin4 --tau 0.5
"""
import os, sys, json, argparse, warnings
warnings.filterwarnings("ignore")
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True
import scl_cldice as C   # noqa: E402
import tilebench as TB   # noqa: E402
from skimage import filters  # noqa: E402

OUT = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/scl")


def topk_outside(score, cur, k, prefer_low=False):
    """The k highest-scoring pixels OUTSIDE the current mask, as a boolean mask."""
    s = score.astype(np.float32).copy()
    if prefer_low:
        s = -s
    s[cur] = -np.inf
    if k <= 0:
        return np.zeros(cur.shape, bool)
    flat = s.ravel()
    k = min(k, int(np.isfinite(flat).sum()))
    idx = np.argpartition(flat, -k)[-k:]
    m = np.zeros(flat.size, bool); m[idx] = True
    return m.reshape(cur.shape)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="main")
    ap.add_argument("--loss", default="thin4")
    ap.add_argument("--tau", type=float, default=0.5)
    ap.add_argument("--save", default="")
    a = ap.parse_args()

    tiles = TB.load()
    gs = [C.skel(t["gt"]) for t in tiles]
    z = np.load(os.path.join(OUT, "ref_masks.npz"))
    cur, flat, sm = z["cur"].astype(bool), z["flat"], z["sm"]
    P = np.load(os.path.join(OUT, f"prob_{a.tag}_{a.loss}.npy"))
    rng = np.random.default_rng(7)

    arms = {"CURRENT MODEL (v1.49.1)": [], "one-line global threshold": [],
            f"additive: U-Net {a.loss}@{a.tau}": [], "additive: random blobs (matched area)": [],
            "additive: Frangi (matched area)": [], "additive: darkest-first (matched area)": [],
            "additive: 3 px trace (CEILING, uses the label)": []}
    thr = z["thr"].astype(bool)
    added = []
    for i, t in enumerate(tiles):
        c = cur[i]
        net = (P[i] >= a.tau) & ~c
        k = int(net.sum()); added.append(k)
        n = ndi.gaussian_filter(rng.standard_normal(c.shape).astype(np.float32), 2.0)
        fr = filters.frangi(flat[i].astype(float), sigmas=range(1, 7), black_ridges=True)
        arms["CURRENT MODEL (v1.49.1)"].append(c)
        arms["one-line global threshold"].append(thr[i])
        arms[f"additive: U-Net {a.loss}@{a.tau}"].append(c | net)
        arms["additive: random blobs (matched area)"].append(c | topk_outside(n, c, k))
        arms["additive: Frangi (matched area)"].append(c | topk_outside(fr, c, k))
        arms["additive: darkest-first (matched area)"].append(c | topk_outside(sm[i], c, k, True))
        arms["additive: 3 px trace (CEILING, uses the label)"].append(c | C.trace(t["gt"], 3))

    print(f"added area per tile: median {int(np.median(added)):,} px "
          f"({100*np.median(added)/262144:.2f}% of a tile), total {sum(added):,}")
    print(f"  {'arm':<48}{'prec':>8}{'recall':>8}{'F1':>8}{'IoU':>8}{'clDice':>9}"
          f"{'(mean)':>9}{'(pooled)':>10}")
    rows, res = {}, {}
    for k, v in arms.items():
        rows[k] = [C.cl_counts(m, t["gt"], g) for m, t, g in zip(v, tiles, gs)]
        m = C.agg(rows[k]); res[k] = m
        print(f"  {k:<48}{m['precision']:8.4f}{m['recall']:8.4f}{m['f1']:8.4f}"
              f"{m['iou']:8.4f}{m['cldice']:9.4f}{m['cldice_mean']:9.4f}{m['cldice_pooled']:10.4f}")
    base = C.per_specimen(rows["CURRENT MODEL (v1.49.1)"], tiles)
    print(f"\n  {'arm':<48}{'median d vs current':>20}{'up':>4}{'dn':>4}{'wilcoxon':>10}")
    pairs = {}
    for k in arms:
        if k == "CURRENT MODEL (v1.49.1)":
            continue
        p = C.paired(C.per_specimen(rows[k], tiles), base, k, "current")
        pairs[k] = p
        print(f"  {k:<48}{p['median_delta']:+20.4f}{p['improved']:4d}{p['regressed']:4d}"
              f"{p['wilcoxon_p']:10.4f}")
    if a.save:
        json.dump(dict(agg=res, paired=pairs, added=added),
                  open(os.path.join(OUT, a.save), "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
