"""LEVER 3 -- a per-pixel learned crack model, leave-one-SPECIMEN-out.

WHAT THIS IS
    The shipped detector is a two-stage REGION pipeline: segment_dark_regions proposes
    candidate blobs, then a logistic model over 8 region features keeps or drops each
    blob.  45.7% of hand-marked crack is never proposed at all, which caps that design
    at recall 0.5326 even with a perfect classifier.  This replaces both stages with one
    pixel-wise classifier over 35 local image features, so nothing has to survive a
    dark-threshold to be found.  It is not a refinement of the region pipeline; it
    supersedes it (see COMBINABILITY).

HEADLINE -- held-out, leave-one-SPECIMEN-out, 13 specimens / 26 tiles
                        precision   recall      IoU       F1
    shipped mad_k=5.0      0.3378   0.3696   0.2143   0.3530   <- the baseline
    shipped mad_k=2.5      0.3421   0.4697   0.2468   0.3959   <- previous best known
    THIS (seed 0)          0.5811   0.5915   0.4147   0.5862   <- +0.2004 IoU over mad5
    THIS, 3-seed mean      0.5667   0.5864   0.4049   0.5763   <- quote this one
    THIS, 2px tolerance    0.6623   0.7355   0.5349   0.6970
    seeds 0/1/2 IoU: 0.4147 / 0.3985 / 0.4014  (range 0.0161, i.e. 12x smaller than the
    gain).  The improved/regressed specimen SET is byte-identical across all three seeds.

NO FREE PARAMETER
    thr=0.5 is fixed a priori.  The sample weights in _sample restore the true class
    prior, so the output is a calibrated probability and 0.5 is the natural cut.
    Handing tilebench the whole 19-value threshold grid and letting it select
    leave-one-specimen-out scores IoU 0.3925 -- WORSE than the fixed 0.5, because
    selection costs more than the best threshold is worth (grid max 0.4148 vs 0.4147).
    So the quoted method has overfit gap 0.0000 by construction.

    What an UNGROUPED experiment would have claimed: train on all 26, score all 26 ->
    IoU 0.7524.  Honest-to-dishonest gap 0.3377.  That gap is the reason for the folds.

READ THIS BEFORE QUOTING THE HEADLINE -- the ground truth is NOT detector-free
    The brief for this work said these 26 tiles "were opened BLANK and painted from
    scratch, so the detector had no hand in them".  That is not what is on disk.
    uploads/<frame>_ascut.png is PIXEL-IDENTICAL (IoU 1.0000 on all 20 non-empty cases)
    to the shipped detector's own crack_export/derived/machine_masks/<parent>_machine.png
    cropped to that tile.  21 of the 26 scored tiles were opened with the detector's mask
    already loaded, and 49.6% of all 202,632 labelled crack pixels were already in that
    seed.  `pixelmodel.py --audit` reproves this in ten seconds.

    On the 5 genuinely blank-start tiles (4 specimens) everything falls:
        shipped mad5  IoU 0.0541  ->  this model  IoU 0.1620      (3.0x, but n=5)
        seeded 21 tiles:    0.2270  ->  0.4448                    (2.0x)
    The ranking survives every slice and the model's margin is proportionally LARGER on
    the detector-free tiles.  The ABSOLUTE 0.41 does not survive: it is partly a measure
    of agreement with a label that is half the old detector's own output.

THE GAIN IS NOT BRUSH IMITATION -- three tests, all pointing the same way
    1. tolerance: a model that learned the human's stroke gains at 0 px and gives it back
       at 2 px.  This gains MORE at 2 px (+0.2994 IoU) than at 0 px (+0.2004).
    2. placement: of 52,666 new true positives, 78.4% are more than 5 px from ANY pixel
       the baseline got right -- newly found crack, not thickened crack.  21.6% is
       thickening.
    3. width: mean mask width  gt 10.01 px,  shipped 18.65 px,  this model 6.50 px.
       It paints THINNER than the human, so it cannot be imitating her brush.
    4. components: GT crack components >=25% covered, shipped 28/189 -> this 136/189.
       Thickening cannot move that number.

PER-SPECIMEN (IoU, shipped mad5 -> this model; identical sign on all 3 seeds)
    MAR_Amb_HIP      0.0000 -> 0.6538   | 260622_316_H_b2   0.2487 -> 0.0956  REGRESSED
    MAR_Amb_Cast     0.0000 -> 0.4481   | 260622_316_amb_b3 0.1927 -> 0.1115  REGRESSED
    MAR_Amb_AS       0.0000 -> 0.3915   | AS_24hr           0.5587 -> 0.2249  REGRESSED
    MAR_AmbB_HIP     0.0000 -> 0.2844   |
    MAR_H_HIP        0.0981 -> 0.3897   | 10 improved / 0 unchanged / 3 regressed  (vs mad5)
    MAR_H_AS         0.5250 -> 0.6691   |  9 improved / 0 unchanged / 4 regressed  (vs mad2.5)
    Cast_24hr        0.2343 -> 0.5026   |
    260708_316_H_b2  0.4079 -> 0.5676   | All three regressions are PRECISION losses on
    260622_316_H_b4  0.5053 -> 0.6098   | specimens where the shipped detector is very
    HIP_24hr         0.0132 -> 0.0944   | conservative (AS_24hr P 0.915 -> 0.226 while
                                        | recall went 0.589 -> 0.969).
    The four MAR_Amb* / MAR_AmbB_HIP specimens sat at recall 0.000 at EVERY setting of
    the shipped detector because their marked crack is BRIGHTER than the background.
    The bright-polarity ridge channels (frangi_br*) are what rescue them.
    No single specimen owns the gain: dropping any one specimen leaves the pooled
    held-out IoU between 0.3567 and 0.4599, every value above the baseline's best (0.3414).

ABLATIONS (held-out IoU at thr 0.5, same folds, same subsample)
    full 35 features    0.4147      noraw      (drop the 16-bit original)   0.4228
    norank              0.4072      noridge    (drop frangi/sato/hessian)   0.3912
    plainonly (7 intensity feats)   0.3155     hgb_small (regularised)      0.4042
    LOGISTIC REGRESSION over the same 35 pixel features: 0.2102 -- BELOW the 0.2143
    baseline.  The win needs the nonlinearity; "a pixel model" alone is not enough.
    Every ablation except the linear one still beats the 0.2468 previous best.
    Note `noraw` >= `full`: the result does NOT depend on access to the 16-bit original.
    Reporting `full` as the headline rather than `noraw` is deliberate -- picking noraw
    because it scored higher on the test set is exactly the selection this harness exists
    to prevent.

COMBINABILITY -- it conflicts, it does not stack
    pixel model alone                      IoU 0.4147  F1 0.5862
    UNION with shipped mad5 / mad2.5           0.3008 / 0.3101
    INTERSECT with shipped mad5 / mad2.5       0.3133 / 0.3369  (but precision 0.85)
    Every combination with the region pipeline is worse on IoU and F1 than the pixel
    model by itself, so this supersedes levers 1 and 2 rather than adding to them.  The
    intersection is the one worth keeping if precision is what you want (P 0.8350).

CONTROLS -- `pixelmodel.py --audit` runs all of these
    shuffle training labels   IoU 0.0000 at thr 0.5; best over the whole grid 0.0297,
                              which is exactly the crack prevalence (= mark-everything).
                              If any feature leaked the label this would be above zero.
    label as a 36th feature   IoU 1.0000  (positive control: the trainer uses its inputs)
    anti-LOSO (train on the   IoU 0.8825 vs the honest 0.4147.  The fold split is doing
    specimen you then score)  real work; the "LOSO" label is not cosmetic.
    tilebench's own three controls (oracle 1.0, empty 0.0, mark-everything P == 2.9730%)
    pass, and this file reproduces the shipped 0.3378/0.3696/0.2143 to 4 decimals.

Run:  <sem-crack-detector venv>/bin/python -B pixelmodel.py            # score from cache
      <...>/bin/python -B pixelmodel.py --fit                          # refit from scratch
      <...>/bin/python -B pixelmodel.py --audit                        # provenance + controls
"""
import os, sys, time
import numpy as np
from scipy import ndimage as ndi

ANALYSIS = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, ANALYSIS)
import tilebench as TB
import crackpipe as CP
from skimage import filters
from skimage.feature import hessian_matrix, hessian_matrix_eigvals
import detect_cracks as D

# ~1 GB of cached per-pixel features lives here -- deliberately NOT inside the repo.
WORK = os.environ.get("PIXELMODEL_CACHE", os.path.join(TB.SC, "pixelmodel_cache"))
BG_PER_TILE = 40000          # background pixels sampled per training tile
THR = 0.5                    # fixed a priori; see the docstring
SEED = 0


# ---------------------------------------------------------------- features
def _rz(x):
    """Robust z-score of a map against its OWN median/MAD.

    Every feature is normalised per tile.  The specimens differ in absolute grey level by
    two orders of magnitude, and three of them (MAR_Amb_*, ETD) have crack BRIGHTER than
    their background -- an un-normalised feature would let the model memorise a specimen
    instead of learning a crack.  These are test-time statistics of the image only; no
    label enters them.
    """
    m = np.median(x)
    return (x - m) / max(np.median(np.abs(x - m)) * 1.4826, 1e-6)


def features(img8, raw=None):
    f, names = [], []
    flat = D.flatten_background(img8, sigma=40).astype(np.float32)
    fz = _rz(flat)

    # multi-scale flattened intensity.  fz at sigma=1 IS the shipped `dark` test, as a
    # continuous number instead of a mad_k cut -- the model gets to choose its own cut,
    # per pixel, in the company of 34 other facts.
    for s in (0, 1, 2, 4, 8):
        f.append((fz if s == 0 else filters.gaussian(fz, sigma=s, preserve_range=True)).astype(np.float32))
        names.append(f"fz_s{s}")

    # the 16-bit original: the only honest source of absolute darkness (the uint8 the
    # pipeline sees is a CLIPPED percentile stretch).
    f.append(_rz(raw.astype(np.float32)).astype(np.float32) if raw is not None
             else np.zeros_like(flat)); names.append("rawz")

    # within-tile percentile rank -- fully specimen-invariant ordering.
    # CAVEAT: this also encodes "roughly 3% of a tile is crack", which is true of these
    # 26 tiles because they were chosen for containing crack.  Ablating it costs little
    # (see the ablation table in the write-up), so it is not load-bearing.
    r = np.empty(flat.size, np.float32)
    r[np.argsort(flat, axis=None, kind="stable")] = np.arange(flat.size, dtype=np.float32)
    f.append((r / flat.size).reshape(flat.shape)); names.append("rank")

    for w in (5, 15, 31, 63):                       # local texture and local contrast
        mu = ndi.uniform_filter(fz, w)
        f.append(np.sqrt(np.maximum(ndi.uniform_filter(fz * fz, w) - mu * mu, 0)).astype(np.float32))
        names.append(f"std{w}")
        f.append((fz - mu).astype(np.float32)); names.append(f"ctr{w}")

    for s in (1, 2, 4):                             # gradient magnitude
        f.append(np.hypot(ndi.gaussian_filter(fz, s, order=(0, 1)),
                          ndi.gaussian_filter(fz, s, order=(1, 0))).astype(np.float32))
        names.append(f"grad{s}")

    # ridge filters at three scale bands, BOTH polarities.  The bright-ridge channel is
    # what rescues MAR_Amb_AS / Cast / HIP, which sit at recall 0.000 at every setting of
    # the shipped detector because their marked crack is brighter than the background.
    fn = (flat - flat.min()) / max(float(flat.max() - flat.min()), 1e-6)
    for lo, hi in ((1, 3), (2, 5), (4, 8)):
        for pol, tag in ((True, "dk"), (False, "br")):
            v = filters.frangi(fn.astype(np.float64), sigmas=range(lo, hi), black_ridges=pol)
            f.append((v / max(v.max(), 1e-12)).astype(np.float32)); names.append(f"frangi_{tag}{lo}")
        v = filters.sato(fn.astype(np.float64), sigmas=range(lo, hi), black_ridges=True)
        f.append((v / max(v.max(), 1e-12)).astype(np.float32)); names.append(f"sato{lo}")

    for w in (9, 25):                               # depth below / height above local extreme
        f.append((fz - ndi.minimum_filter(fz, w)).astype(np.float32)); names.append(f"amin{w}")
        f.append((ndi.maximum_filter(fz, w) - fz).astype(np.float32)); names.append(f"bmax{w}")

    for s in (2, 4):                                # signed Hessian eigenvalues
        e = hessian_matrix_eigvals(hessian_matrix(fz.astype(np.float64), sigma=s,
                                                  use_gaussian_derivatives=True))
        f.append(e[0].astype(np.float32)); names.append(f"h1_{s}")
        f.append(e[1].astype(np.float32)); names.append(f"h2_{s}")

    return np.stack(f, -1), names


def cached_features(t):
    os.makedirs(WORK, exist_ok=True)
    p = os.path.join(WORK, t["frame"] + ".npy")
    if os.path.exists(p):
        return np.load(p, mmap_mode="r")
    X, _ = features(t["img8"], t.get("raw"))
    np.save(p, X)
    return X


# ---------------------------------------------------------------- model
def _sample(tiles, idxs, rng):
    """All positives + a background subsample, with weights restoring the TRUE prior.

    Subsampling background without re-weighting would inflate the apparent crack prior
    ~45x and decalibrate the probability, which is what makes a fixed 0.5 threshold
    legitimate here.  The weights put the prior back.
    """
    Xs, ys, ws = [], [], []
    for i in idxs:
        X = np.asarray(cached_features(tiles[i])).reshape(-1, 35)
        y = tiles[i]["gt"].ravel()
        pos, neg = np.flatnonzero(y), np.flatnonzero(~y)
        sel = rng.choice(neg, min(BG_PER_TILE, neg.size), replace=False)
        Xs += [X[pos], X[sel]]
        ys += [np.ones(pos.size, np.int8), np.zeros(sel.size, np.int8)]
        ws += [np.ones(pos.size, np.float32), np.full(sel.size, neg.size / sel.size, np.float32)]
    return np.concatenate(Xs), np.concatenate(ys), np.concatenate(ws)


def _clf(seed=SEED):
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.1, max_leaf_nodes=31,
                                          min_samples_leaf=200, l2_regularization=1.0,
                                          random_state=seed)


def fit_predict(seed=SEED):
    """Returns (loso, full): probability maps from the honest folds, and from a model
    that saw everything.  The second exists only so the overfit gap can be printed."""
    tiles = TB.load(with_raw=True)
    rng = np.random.default_rng(seed)
    loso = np.zeros((len(tiles), 512, 512), np.float32)
    for sp in sorted({t["specimen"] for t in tiles}):
        tr = [i for i, t in enumerate(tiles) if t["specimen"] != sp]
        te = [i for i, t in enumerate(tiles) if t["specimen"] == sp]
        s = time.time()
        X, y, w = _sample(tiles, tr, rng)
        m = _clf(seed).fit(X, y, sample_weight=w)
        for i in te:
            loso[i] = m.predict_proba(np.asarray(cached_features(tiles[i])).reshape(-1, 35)
                                      )[:, 1].reshape(512, 512)
        print(f"  fold {sp:<22} {X.shape[0]:>8} train px  {len(te)} tile(s)  {time.time()-s:.0f}s",
              flush=True)
    X, y, w = _sample(tiles, range(len(tiles)), rng)
    m = _clf(seed).fit(X, y, sample_weight=w)
    full = np.stack([m.predict_proba(np.asarray(cached_features(t)).reshape(-1, 35))[:, 1]
                     .reshape(512, 512) for t in tiles])
    np.save(os.path.join(WORK, "loso.npy"), loso)
    np.save(os.path.join(WORK, "full.npy"), full)
    return loso, full


# ---------------------------------------------------------------- report
def main(refit=False):
    tiles = TB.load()
    lp, fp = os.path.join(WORK, "loso.npy"), os.path.join(WORK, "full.npy")
    if refit or not os.path.exists(lp):
        loso, full = fit_predict()
    else:
        loso, full = np.load(lp), np.load(fp)

    base = np.stack([CP.predict(t["img8"]) for t in tiles])          # shipped, mad_k=5
    pred = loso >= THR

    TB.evaluate("shipped detector (mad_k=5.0)", {"x": [TB.counts(base[i], t["gt"])
                                                       for i, t in enumerate(tiles)]})
    TB.evaluate(f"LEVER3 pixel model, LOSO, thr={THR} fixed",
                {"x": [TB.counts(pred[i], t["gt"]) for i, t in enumerate(tiles)]})
    TB.evaluate("the same model FITTED ON ALL 26 -- do NOT quote this",
                {"x": [TB.counts(full[i] >= THR, t["gt"]) for i, t in enumerate(tiles)]})

    # Is the gain real crack, or the human's brush?  A brush-imitating model gains at
    # 0 px and gives it back at 2 px, and thickens what was already right.  This does
    # the opposite on all three tests.
    near = far = 0
    st = ndi.generate_binary_structure(2, 2)
    for i, t in enumerate(tiles):
        new = pred[i] & t["gt"] & ~base[i]
        halo = ndi.binary_dilation(base[i] & t["gt"], st, iterations=5)
        near += int((new & halo).sum()); far += int((new & ~halo).sum())
    print(f"\n  new true positives: {near+far:,}   thickening (<=5px from a baseline TP) "
          f"{near/(near+far):.1%}   newly found crack {far/(near+far):.1%}")
    for nm, P in (("ground truth", [t["gt"] for t in tiles]), ("shipped", list(base)),
                  ("this model", list(pred))):
        print(f"  mean mask width, {nm:<14} "
              f"{np.mean([2*ndi.distance_transform_edt(p)[p].mean() for p in P if p.sum()]):.2f} px")


# ---------------------------------------------------------------- audit
def audit():
    """The checks that would have caught me if I had been wrong.

    Every claim above is paired here with a deliberate defect that must destroy it; a
    check that passes on broken code measured nothing.
    """
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    tiles = TB.load(with_raw=True)

    print("\nA. LABEL PROVENANCE -- is _ascut the shipped detector's own machine mask?")
    MACH = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/crack_export/derived/machine_masks"
    seen, ious, seeded, kept, gtot = {}, [], 0, 0, 0
    for t in tiles:
        if t["parent"] not in seen:
            seen[t["parent"]] = np.array(Image.open(
                os.path.join(MACH, t["parent"] + "_machine.png")).convert("L")) < 128
        x, y, w, h = t["box"]
        crop = seen[t["parent"]][y:y + h, x:x + w]
        asc = np.array(Image.open(os.path.join(
            TB.UP, t["frame"] + "_ascut.png")).convert("L")) < 128
        if asc.sum():
            seeded += 1
            ious.append((asc & crop).sum() / max((asc | crop).sum(), 1))
        kept += int((asc & t["gt"]).sum()); gtot += int(t["gt"].sum())
    print(f"   {seeded}/{len(tiles)} tiles opened with a NON-EMPTY detector mask already loaded")
    print(f"   IoU(_ascut, machine_mask crop) over those: min {min(ious):.4f} "
          f"median {float(np.median(ious)):.4f}  -> they are the same bytes")
    print(f"   {kept:,} of {gtot:,} labelled crack px ({kept/gtot:.1%}) came from that seed")

    print("\nB. SEEDED vs BLANK-START tiles")
    lo = np.load(os.path.join(WORK, "loso.npy"))
    base = np.stack([CP.predict(t["img8"]) for t in tiles])
    blank = [i for i, t in enumerate(tiles) if (np.array(Image.open(os.path.join(
        TB.UP, t["frame"] + "_ascut.png")).convert("L")) < 128).sum() == 0]
    full = range(len(tiles))
    for nm, idx in (("all", full), ("seeded", [i for i in full if i not in blank]),
                    ("BLANK-START", blank)):
        def agg(P):
            c = [TB.counts(P[i], tiles[i]["gt"]) for i in idx]
            tp, fp, fn = (sum(r[k] for r in c) for k in ("tp", "fp", "fn"))
            return tp / max(tp + fp + fn, 1)
        print(f"   {nm:<12} n={len(list(idx)):>2}  shipped IoU {agg(base):.4f}"
              f"   this model IoU {agg(lo >= THR):.4f}")

    print("\nC. SABOTAGE -- break it on purpose, the score must collapse")
    rng = np.random.default_rng(SEED)
    for mode in ("shuffle_y", "gt_feature", "self_fold"):
        P = np.zeros((len(tiles), 512, 512), np.float32)
        for sp in sorted({t["specimen"] for t in tiles}):
            own = [i for i, t in enumerate(tiles) if t["specimen"] == sp]
            tr = own if mode == "self_fold" else [i for i in full if i not in own]
            X, y, w = _sample(tiles, tr, rng)
            if mode == "shuffle_y":
                y = rng.permutation(y)
            if mode == "gt_feature":
                X = np.column_stack([X, y.astype(np.float32)])
            m = _clf().fit(X, y, sample_weight=w)
            for i in own:
                Xi = np.asarray(cached_features(tiles[i])).reshape(-1, 35)
                if mode == "gt_feature":
                    Xi = np.column_stack([Xi, tiles[i]["gt"].ravel().astype(np.float32)])
                P[i] = m.predict_proba(Xi)[:, 1].reshape(512, 512)
        c = [TB.counts(P[i] >= THR, tiles[i]["gt"]) for i in full]
        tp, fp, fn = (sum(r[k] for r in c) for k in ("tp", "fp", "fn"))
        want = {"shuffle_y": "must be ~0.00 (prevalence 0.0297 at best)",
                "gt_feature": "must be 1.0000 (positive control)",
                "self_fold": "must be >> the honest 0.4147"}[mode]
        print(f"   {mode:<12} IoU {tp/max(tp+fp+fn,1):.4f}    {want}")


if __name__ == "__main__":
    if "--audit" in sys.argv:
        audit()
    else:
        main(refit="--fit" in sys.argv)
