"""clDice scoring for the 26 hand-labelled tiles -- the SAME instrument the brief's table
used, reproduced here so a gain measured against it is readable.

WHY A SECOND SCORING FILE AT ALL. tilebench.evaluate selects and reports on IoU. On this
corpus IoU is the wrong objective and the brief says so with a number: a physically
correct 3 px trace down the centre of the human's own paint scores IoU 0.2490, BELOW the
shipped detector's 0.3344, because the labels are a paintbrush and IoU rewards being as
fat as the brush. clDice (Shit et al., CVPR 2021) scores whether the crack was found
along its LENGTH and is blind to how thickly it was drawn:

    Tprec = |skel(pred) & gt| / |skel(pred)|      Tsens = |skel(gt) & pred| / |skel(gt)|
    clDice = 2 Tprec Tsens / (Tprec + Tsens)

TWO POOLING RULES, AND THEY ARE NOT THE SAME NUMBER. The brief's table pools clDice as
the MEDIAN of the 26 per-tile values; precision/recall/F1/IoU are pooled by summing
tp/fp/fn, the way tilebench does. Both are reproduced bit-for-bit from the harness's own
run_good/is_it_good.py -- `cldice_median` is the headline, `cldice_pooled` (one ratio over
summed skeleton counts) travels beside it because a median over 26 values moves in steps
of about 1/26 and a method can win one and lose the other. Every table here prints both.

The reference arms are lifted from that same script, including `cand()` -- clean_mask at
min_area 13 followed by production's 40 px component filter, which crackpipe.stages omits
and which is worth +0.0035 precision on the current-model row.
"""
import os, sys
import numpy as np
from scipy import ndimage as ndi

APP = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
for p in (APP + "/analysis/research", APP + "/analysis/research/improve",
          APP + "/analysis", SEM + "/code"):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True

import tilebench as TB         # noqa: E402
import detect_cracks as D      # noqa: E402
import detector_overrides as DO  # noqa: E402
from skimage import filters    # noqa: E402
from skimage.morphology import skeletonize  # noqa: E402


class _U:
    pass


_up = _U()
DO.install(_up)


def skel(m):
    m = np.asarray(m, bool)
    return np.zeros_like(m) if not m.any() else skeletonize(m)


def cand(m):
    """clean_mask(min_area 13) + extract_candidates' 40 px component filter. This IS the
    shipped candidate stage once the region classifier is off."""
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def cl_counts(pred, gt, gt_skel=None):
    """Per-tile clDice plus the four skeleton counts and tp/fp/fn, so one call feeds the
    median pooling, the pooled-ratio pooling and the IoU family."""
    pred = np.asarray(pred, bool); gt = np.asarray(gt, bool)
    sp = skel(pred)
    sg = gt_skel if gt_skel is not None else skel(gt)
    sp_in, sp_n = int((sp & gt).sum()), int(sp.sum())
    sg_in, sg_n = int((sg & pred).sum()), int(sg.sum())
    if not pred.any() or not gt.any():
        cld = 0.0
    else:
        tp_, ts_ = sp_in / max(sp_n, 1), sg_in / max(sg_n, 1)
        cld = 0.0 if tp_ + ts_ == 0 else 2 * tp_ * ts_ / (tp_ + ts_)
    return dict(tp=int((pred & gt).sum()), fp=int((pred & ~gt).sum()),
                fn=int((~pred & gt).sum()), sp_in=sp_in, sp_n=sp_n,
                sg_in=sg_in, sg_n=sg_n, cld=float(cld))


def agg(rows):
    tp = sum(r["tp"] for r in rows); fp = sum(r["fp"] for r in rows); fn = sum(r["fn"] for r in rows)
    p = tp / max(tp + fp, 1); r_ = tp / max(tp + fn, 1)
    tprec = sum(r["sp_in"] for r in rows) / max(sum(r["sp_n"] for r in rows), 1)
    tsens = sum(r["sg_in"] for r in rows) / max(sum(r["sg_n"] for r in rows), 1)
    return dict(precision=p, recall=r_, f1=2 * p * r_ / max(p + r_, 1e-12),
                iou=tp / max(tp + fp + fn, 1),
                cldice=float(np.median([r["cld"] for r in rows])),
                cldice_mean=float(np.mean([r["cld"] for r in rows])),
                cldice_pooled=2 * tprec * tsens / max(tprec + tsens, 1e-12),
                tprec=tprec, tsens=tsens, n=len(rows))


def per_specimen(rows, tiles):
    """{specimen: median clDice over its tiles} -- the unit of the paired test."""
    out = {}
    for sp in sorted({t["specimen"] for t in tiles}):
        idx = [i for i, t in enumerate(tiles) if t["specimen"] == sp]
        out[sp] = float(np.median([rows[i]["cld"] for i in idx]))
    return out


def paired(a, b, label_a="A", label_b="B"):
    """Wilcoxon signed-rank + sign test over the 13 specimens. a, b: {specimen: value}."""
    from scipy import stats
    ks = sorted(set(a) & set(b))
    da = np.array([a[k] for k in ks]); db = np.array([b[k] for k in ks]); d = da - db
    w = float(stats.wilcoxon(da, db).pvalue) if np.any(d != 0) else 1.0
    up_, dn = int((d > 0).sum()), int((d < 0).sum())
    sg = float(stats.binomtest(up_, up_ + dn, 0.5).pvalue) if up_ + dn else 1.0
    return dict(n=len(ks), median_delta=float(np.median(d)), mean_delta=float(d.mean()),
                improved=up_, regressed=dn, wilcoxon_p=w, sign_p=sg,
                label_a=label_a, label_b=label_b,
                per_spec={k: float(x) for k, x in zip(ks, d)})


# ------------------------------------------------------------------ reference arms
#   Lifted from the harness's own run_good/is_it_good.py so the table reproduces.
def arms(t, rng=None):
    img8, gt = t["img8"], t["gt"]
    flat = D.flatten_background(img8)
    sm = filters.gaussian(flat, sigma=1.0, preserve_range=True)
    cur = cand(_up.segment_dark_regions(flat, img8=img8))
    a = float(cur.mean())
    thr = cand(sm < np.percentile(sm, 100 * a))
    fr = filters.frangi(flat.astype(float), sigmas=range(1, 7), black_ridges=True)
    rid = cand(fr >= np.percentile(fr, 100 * (1 - a)))
    out = {"CURRENT MODEL (v1.49.1)": cur, "one-line global threshold": thr,
           "a correct 3 px trace": trace(gt, 3), "ridge filter (Frangi)": rid,
           "mark everything": np.ones_like(gt)}
    if rng is not None:
        rnd = np.zeros(gt.size, bool)
        rnd[rng.choice(gt.size, int(cur.sum()), replace=False)] = True
        out["random, area-matched"] = rnd.reshape(gt.shape)
    out["_flat"] = flat; out["_sm"] = sm
    return out


def trace(gt, width=3):
    return ndi.binary_dilation(skel(gt), ndi.generate_binary_structure(2, 2),
                               iterations=max(0, (width - 1) // 2))


def controls(tiles, gs):
    o = agg([cl_counts(t["gt"], t["gt"], g) for t, g in zip(tiles, gs)])
    e = agg([cl_counts(np.zeros_like(t["gt"]), t["gt"], g) for t, g in zip(tiles, gs)])
    a = agg([cl_counts(np.ones_like(t["gt"]), t["gt"], g) for t, g in zip(tiles, gs)])
    prev = sum(int(t["gt"].sum()) for t in tiles) / sum(t["gt"].size for t in tiles)
    ok = True
    for nm, got, want in [("oracle (gt itself)", o, dict(cldice=1.0, iou=1.0)),
                          ("empty", e, dict(cldice=0.0, iou=0.0)),
                          ("mark everything", a, dict(recall=1.0, iou=prev, cldice=0.0))]:
        bad = [k for k, v in want.items() if abs(got[k] - v) > 1e-6]
        print(f"  {'PASS' if not bad else 'FAIL'}  {nm:<20} P {got['precision']:.4f} "
              f"R {got['recall']:.4f} IoU {got['iou']:.4f} clDice {got['cldice']:.4f}"
              + (f"   expected {want}, got {got}" if bad else ""))
        ok &= not bad
    print(f"  prevalence {prev:.4%}")
    return ok


if __name__ == "__main__":
    tiles = TB.load()
    gs = [skel(t["gt"]) for t in tiles]
    print(f"{len(tiles)} tiles, {len({t['specimen'] for t in tiles})} specimens")
    assert controls(tiles, gs), "controls failed -- no score from this file is readable"
