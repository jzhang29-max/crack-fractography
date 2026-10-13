"""APPROACH 4 -- shared instrument. Centreline (clDice) scoring, the arms, and the cache.

Nothing here builds a model. It exists so the three questions -- what ceiling the labels
impose, where the centreline recall goes, and whether the threshold tie is real -- are all
answered with ONE definition of clDice and ONE definition of each arm.

clDice (Shit et al. 2021) is
    Tprec = |skel(P) & G| / |skel(P)|      how much of the PREDICTED centreline is on crack
    Tsens = |skel(G) & P| / |skel(G)|      how much of the LABEL centreline was found
    clDice = 2 Tprec Tsens / (Tprec + Tsens)
and the degenerate guard from the project's own implementation
(sem-crack-detector/crack_export/analysis/sam3/methods_bench.py) is kept so numbers here
are comparable with the ones already quoted: a prediction covering more than 25% of the
tile scores 0, which is why "mark everything" reads 0.0000 rather than ~0.05.

AGGREGATION. Tiles differ in crack content by 100x, so there are two honest ways to pool
and they are NOT the same number. Both are computed everywhere:
    cldice_mean   mean of the per-tile clDice            (each tile one vote)
    cldice_pooled 2TpTs/(Tp+Ts) on summed skeleton counts (each pixel one vote)
The headline numbers this workflow quotes (0.6405 shipped, 0.6205 threshold, 0.9984 for a
3 px trace) are the per-tile MEAN; that is what `cldice_mean` reproduces.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")

ANALYSIS = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
if ANALYSIS not in sys.path:
    sys.path.insert(0, ANALYSIS)
import numpy as np
from scipy import ndimage as ndi
from skimage import filters
from skimage.morphology import skeletonize, disk

import tilebench as TB
import crackpipe as CP          # also puts the archived detector on sys.path
import detect_cracks as D

WORK = os.path.join(TB.SC, "a4")
os.makedirs(WORK, exist_ok=True)

SCALE_LADDER = (5, 10, 20, 40, 80, 160, 320)
DECIMATE_ABOVE_SIGMA = 64
ABSOLUTE_DARK = 10
MAD_K = 5.0
MIN_AREA = 13
FEATURE_MIN_AREA = 40       # detect_cracks.region_features_from_labeled drops below this


# --------------------------------------------------------------------------- clDice
def skel(m):
    return skeletonize(np.asarray(m, bool))


def cldice_parts(pred, gt, spred=None, sgt=None):
    """Returns (Tprec, Tsens, n_skel_pred, n_skel_gt, hits_pred, hits_gt)."""
    pred = np.asarray(pred, bool); gt = np.asarray(gt, bool)
    sp = skel(pred) if spred is None else spred
    sg = skel(gt) if sgt is None else sgt
    np_, ng = int(sp.sum()), int(sg.sum())
    hp = int((sp & gt).sum()); hg = int((sg & pred).sum())
    tp = hp / np_ if np_ else 0.0
    ts = hg / ng if ng else 0.0
    return tp, ts, np_, ng, hp, hg


def cldice(pred, gt, guard=True, **kw):
    pred = np.asarray(pred, bool)
    if pred.sum() == 0 or np.asarray(gt, bool).sum() == 0:
        return 0.0
    if guard and pred.mean() > 0.25:
        return 0.0
    tp, ts, *_ = cldice_parts(pred, gt, **kw)
    return float(2 * tp * ts / (tp + ts)) if (tp + ts) > 0 else 0.0


def score_tile(pred, gt, sgt=None):
    """Every metric for one tile, plus the raw counts needed to pool later."""
    pred = np.asarray(pred, bool); gt = np.asarray(gt, bool)
    tp = int((pred & gt).sum()); fp = int((pred & ~gt).sum()); fn = int((~pred & gt).sum())
    tpr, tsn, nsp, nsg, hp, hg = cldice_parts(pred, gt, sgt=sgt)
    degenerate = pred.mean() > 0.25 or pred.sum() == 0
    cd = 0.0 if degenerate else (2 * tpr * tsn / (tpr + tsn) if (tpr + tsn) > 0 else 0.0)
    return dict(tp=tp, fp=fp, fn=fn, n_skel_pred=nsp, n_skel_gt=nsg,
                hit_skel_pred=hp, hit_skel_gt=hg, cldice=float(cd),
                tprec=float(tpr), tsens=float(tsn), degenerate=bool(degenerate))


def pool(rows):
    tp = sum(r["tp"] for r in rows); fp = sum(r["fp"] for r in rows); fn = sum(r["fn"] for r in rows)
    p = tp / max(tp + fp, 1); r_ = tp / max(tp + fn, 1)
    tpr = sum(r["hit_skel_pred"] for r in rows) / max(sum(r["n_skel_pred"] for r in rows), 1)
    tsn = sum(r["hit_skel_gt"] for r in rows) / max(sum(r["n_skel_gt"] for r in rows), 1)
    return dict(precision=p, recall=r_, f1=2 * p * r_ / max(p + r_, 1e-12),
                iou=tp / max(tp + fp + fn, 1),
                cldice_mean=float(np.mean([r["cldice"] for r in rows])),
                cldice_pooled=float(2 * tpr * tsn / max(tpr + tsn, 1e-12)),
                tprec_mean=float(np.mean([r["tprec"] for r in rows])),
                tsens_mean=float(np.mean([r["tsens"] for r in rows])))


# --------------------------------------------------------------------------- stages
def flatten(img8, sigma):
    if sigma <= DECIMATE_ABOVE_SIGMA:
        return D.flatten_background(img8, sigma=sigma)
    from skimage import exposure as _exp
    f = max(1, int(round(sigma / 32.0)))
    small = ndi.uniform_filter(img8.astype(np.float32), f)[::f, ::f]
    bg_s = ndi.gaussian_filter(small, sigma / f, mode="nearest")
    bg = ndi.zoom(bg_s, (img8.shape[0] / bg_s.shape[0], img8.shape[1] / bg_s.shape[1]),
                  order=1, mode="nearest")[:img8.shape[0], :img8.shape[1]]
    if bg.shape != img8.shape:
        bg = np.pad(bg, ((0, img8.shape[0] - bg.shape[0]),
                         (0, img8.shape[1] - bg.shape[1])), mode="edge")
    flat = img8.astype(np.float32) - bg
    lo, hi = np.percentile(flat, [0.5, 99.5])
    if hi <= lo:
        lo, hi = flat.min(), flat.max()
    return _exp.rescale_intensity(flat, in_range=(lo, hi), out_range=(0, 255)).astype(np.uint8)


def dark_per_rung(img8, mad_k=MAD_K):
    """The ladder's per-radius cuts, kept separately so a missed pixel can be attributed."""
    out = {}
    for sigma in SCALE_LADDER:
        f = flatten(img8, sigma)
        sm = filters.gaussian(f, sigma=1.0, preserve_range=True)
        med = float(np.median(sm))
        mad = float(np.median(np.abs(sm - med)) * 1.4826)
        out[sigma] = sm < min(filters.threshold_otsu(sm), med - mad_k * mad)
    out["absolute"] = img8 < ABSOLUTE_DARK
    return out


def current_stages(img8, mad_k=MAD_K):
    """v1.49.1: multi-scale dark union -> clean_mask -> >=40 px regions, classifier OFF."""
    rungs = dark_per_rung(img8, mad_k)
    dark = np.zeros(img8.shape, bool)
    for v in rungs.values():
        dark |= v
    clean = D.clean_mask(dark, open_radius=1, close_radius=3, min_area_px=MIN_AREA)
    lab, _ = ndi.label(clean)
    flat40 = D.flatten_background(img8, sigma=40)
    ves = D.compute_vesselness(flat40)
    labeled, df = D.region_features_from_labeled(lab, flat40, ves)
    return dict(rungs=rungs, dark=dark, clean=clean, labeled=labeled, df=df,
                pred=labeled > 0, flat40=flat40)


def rz(x):
    m = np.median(x)
    return (x - m) / max(np.median(np.abs(x - m)) * 1.4826, 1e-6)


def fz_s1(img8):
    """The one-line arm's statistic: robust-z of the sigma=40 flattened image, blurred 1 px.
    fz_s1 < c IS the shipped darkness test written as a continuous number."""
    return filters.gaussian(rz(D.flatten_background(img8, sigma=40).astype(np.float32)),
                            sigma=1, preserve_range=True).astype(np.float32)


# --------------------------------------------------------------------------- arms
ONE_LINE_GRID = (-0.5, -1.0, -1.5, -2.0, -2.5, -3.0, -4.0, -5.0)


def build_cache(verbose=True):
    """Everything every script below needs, computed once per tile."""
    path = os.path.join(WORK, "arms.npz")
    tiles = TB.load(with_raw=True)
    need = [t for t in tiles if not os.path.exists(os.path.join(WORK, "t_" + t["frame"] + ".npz"))]
    for i, t in enumerate(need, 1):
        st = current_stages(t["img8"])
        z = fz_s1(t["img8"])
        payload = dict(gt=t["gt"], pred_current=st["pred"], dark=st["dark"],
                       clean=st["clean"], labeled=st["labeled"].astype(np.int32),
                       fz=z, flat40=st["flat40"], img8=t["img8"])
        for k, v in st["rungs"].items():
            payload["rung_%s" % k] = v
        np.savez_compressed(os.path.join(WORK, "t_" + t["frame"] + ".npz"), **payload)
        if verbose:
            print(f"  cached [{i}/{len(need)}] {t['frame']}", flush=True)
    return path


def tiles_with_arms(seed=0):
    """Every tile plus every arm's mask. The arms are exactly the six in the brief."""
    rng = np.random.default_rng(seed)
    tiles = TB.load(with_raw=True)
    out = []
    for t in tiles:
        z = np.load(os.path.join(WORK, "t_" + t["frame"] + ".npz"))
        gt = z["gt"].astype(bool)
        sg = skel(gt)
        d = dict(t)
        d.update(gt=gt, skel_gt=sg, fz=z["fz"], dark=z["dark"].astype(bool),
                 clean=z["clean"].astype(bool), labeled=z["labeled"],
                 flat40=z["flat40"], rungs={k.split("_", 1)[1]: z[k].astype(bool)
                                            for k in z.files if k.startswith("rung_")})
        arms = {"current": z["pred_current"].astype(bool)}
        for c in ONE_LINE_GRID:
            arms["oneline_%.1f" % c] = z["fz"] < c
        # 3x3 square, not disk(1): this is the dilation that reproduces the brief's
        # "correct 3 px trace" row exactly (prec 0.9754 recall 0.2505 IoU 0.2490).
        arms["trace3"] = ndi.binary_dilation(sg, np.ones((3, 3), bool))
        arms["markall"] = np.ones_like(gt)
        arms["empty"] = np.zeros_like(gt)
        # Frangi, matched to the published arm: ridge response, top-q of the tile
        v = filters.frangi(z["flat40"].astype(np.float32), sigmas=range(1, 5), black_ridges=True)
        for q in (0.01, 0.02, 0.03, 0.05, 0.08):
            arms["frangi_%.2f" % q] = v >= np.quantile(v, 1 - q)
        # area-matched random: same pixel count as the current arm, placed at random
        n = int(z["pred_current"].sum())
        flat = np.zeros(gt.size, bool)
        flat[rng.choice(gt.size, size=min(n, gt.size), replace=False)] = True
        arms["random"] = flat.reshape(gt.shape)
        d["arms"] = arms
        out.append(d)
    return out


def loso_pick(tiles, scores, keys, metric="cldice"):
    """Leave-one-SPECIMEN-out selection. scores[key][i] is a per-tile row dict.
    Returns (held_out_rows_in_tile_order, picks, fitted_key)."""
    specs = sorted({t["specimen"] for t in tiles})

    def agg(key, idx):
        return pool([scores[key][i] for i in idx])[
            "cldice_mean" if metric == "cldice" else metric]

    allidx = list(range(len(tiles)))
    fitted = max(keys, key=lambda k: agg(k, allidx))
    held = [None] * len(tiles)
    picks = {}
    for sp in specs:
        tr = [i for i, t in enumerate(tiles) if t["specimen"] != sp]
        te = [i for i, t in enumerate(tiles) if t["specimen"] == sp]
        best = max(keys, key=lambda k: agg(k, tr))
        picks[sp] = best
        for i in te:
            held[i] = scores[best][i]
    return held, picks, fitted


if __name__ == "__main__":
    build_cache()
    print("cache built in", WORK)
