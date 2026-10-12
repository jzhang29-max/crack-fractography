"""LEVER 4 -- retrain the region classifier on the precise tile labels, with new features.

STATUS: REJECTED, 2026-10-12. Do not ship this, and do not read the tile scores below as
support for shipping it. Tested against the hand-painted correction masks on 48 full
frames, it deletes 72.67% of the hand-marked crack the shipped classifier-off path
delivers -- worse than the texture veto (67.54%) and the thickness excision (62.43%) that
were already rejected on the same evidence, and worse than the shipped classifier it was
meant to replace. Its top feature, MeanWidth, spans 2.61-29.34 px over the training
positives here and 18-236 px over the regions that hold painted crack on a full frame, so
its verdict on a main crack is extrapolation, not learning. The headline below is also
weaker than it looks at the shipped setting: at MATCHED mad_k=5.0 with the one
off-specimen void tile removed its gain over keeping every candidate is -0.0063.
Full record: fullframe_lever4_safety.py. Guard: tests/test_region_rules_rejected.py.

RESULT (held-out, leave-one-SPECIMEN-out, scored by analysis/research/tilebench.py):

    shipped baseline          P 0.3378  R 0.3696  IoU 0.2143  F1 0.3530
    this, mad_k fixed at 5.0  P 0.8655  R 0.5122  IoU 0.4745  F1 0.6436   <- pure lever 4
    this, mad_k LOSO-picked   P 0.8099  R 0.6126  IoU 0.5356  F1 0.6976   <- headline
    same, trained on all 26   P 0.8734  R 0.6393  IoU 0.5851  F1 0.7382   (optimistic)
    overfit gap on IoU                                        +0.0495

    12 of 13 specimens improve, 1 regresses (260622_316_amb_b3, a single 673 px tile).
    Conservative floor: leave-one-IMAGING-FAMILY-out (3 folds) gives IoU 0.4902.

WHAT CARRIES IT -- and what does not:
  * Refitting the SAME 8 shipped features on the precise labels buys NOTHING. At
    mad_k=5.0 it scores IoU 0.2943 against 0.2979 for keeping every candidate with no
    classifier at all: slightly worse than having no classifier.
  * The gain is the NEW features. Permutation importance ranks MeanWidth (+0.0570),
    RingStdFlat (+0.0562), Eccentricity (+0.0526, shipped), RawRingZ (+0.0461),
    RawInteriorCV (+0.0460), RawFlatnessRatio (+0.0404), WanderRMS (+0.0331).
    Five of the eight shipped features have zero or negative importance: LogArea
    0.0000, Solidity +0.0005, Circularity -0.0008, Extent -0.0008, MeanDarkness -0.0021.
  * Separately, and needing no model at all: the shipped classifier is net-NEGATIVE.
    Marking every candidate region and skipping the classifier scores IoU 0.2979
    against the shipped 0.2143, with zero free parameters.

TWO CORRECTIONS TO THE BRIEF THIS RUN TURNED UP:
  1. MAR_Amb_AS / _Cast / _HIP are NOT at recall 0.000 because their marked crack is
     brighter than the background median. Their CANDIDATE stage recovers 35-85% of
     marked crack at precision 0.56-0.98, at every mad_k tested. It is the classifier
     that zeroes them, not the dark threshold. (See report() section 2.)
  2. Passing a 63-variant grid to TB.evaluate scores held-out IoU 0.2911 -- WORSE than
     a single pre-specified configuration. The across-variant selection itself overfits:
     on the MAR_H_HIP fold it picks a variant that floods the off-specimen void.

HONEST CAVEAT, up front: the off-specimen void on
MAR_H_HIP_CBS_0002__crop_3122_120_512x512 is 86.5% of all candidate-stage false
positives, so a 26-tile pooled IoU is largely a referendum on that one region. Every
arm below is therefore also reported on the 25 tiles without it. At the shipped
mad_k=5.0 the retrained classifier's entire advantage IS that region (IoU25 0.4749 vs
0.4812 for no classifier). Only once mad_k is relaxed does it add elsewhere as well
(mad_k=2.5: IoU25 0.5447 vs 0.4822).

Usage:
    /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python -B \
        analysis/research/improve/lever4_region_classifier.py
(builds an 82 MB region cache in the scratchpad on first run, ~25 s, then reports)
"""
import os, sys, time, pickle, warnings
warnings.filterwarnings("ignore")
SC = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
      "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
os.environ.setdefault("MPLCONFIGDIR", SC + "/mpl")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research")
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import tilebench as TB, crackpipe as CP

# 82 MB region cache -- scratchpad, never the repo
PKL = os.path.join(SC, "lever4_regions.pkl")
MAD_KS = (5.0, 3.0, 2.5)

SHIPPED8 = ["LogArea", "Elongation", "Solidity", "Eccentricity", "Extent",
            "Circularity", "MeanDarkness", "MeanVesselness"]
NEW = ["SkelLenOverArea", "MeanWidth", "WidthCV", "MaxWidth", "WidthRatio",
       "EndpointsPerLen", "BranchPerLen", "WanderRMS", "WanderMax", "AxisRatioSkel",
       "SkelTortuosity", "RingContrastFlat", "RingZFlat", "InteriorStdFlat",
       "FlatnessRatio", "RingStdFlat", "RawRelDark", "RawRingZ", "RawInteriorCV",
       "RawFlatnessRatio", "RawLogRatio", "VesMax", "VesStd", "VesP90"]
ALLF = SHIPPED8 + NEW


# ==============================================================================
# features.  NOTHING in this section receives the ground truth -- that is the
# leakage guard, and report() section 0 re-checks it by recomputing the whole
# block with the labels replaced by noise and asserting bit-identity.
# ==============================================================================
def new_features(mask_full, sl, flat, raw, ves, tile_stats):
    pad = 8
    y0 = max(sl[0].start - pad, 0); y1 = min(sl[0].stop + pad, flat.shape[0])
    x0 = max(sl[1].start - pad, 0); x1 = min(sl[1].stop + pad, flat.shape[1])
    m = mask_full[y0:y1, x0:x1]
    f = flat[y0:y1, x0:x1].astype(np.float64)
    r = raw[y0:y1, x0:x1].astype(np.float64)
    v = ves[y0:y1, x0:x1].astype(np.float64)
    area = float(m.sum())
    out = {}

    # --- skeleton: width consistency, branching, and centreline WANDER ---
    sk = skeletonize(m)
    ys, xs = np.nonzero(sk)
    nsk = len(ys)
    out["SkelLenOverArea"] = nsk / area
    dt = ndi.distance_transform_edt(m)
    w = 2.0 * dt[sk] if nsk else np.array([1.0])
    out["MeanWidth"] = float(w.mean())
    out["WidthCV"] = float(w.std() / max(w.mean(), 1e-6))
    out["MaxWidth"] = float(w.max())
    out["WidthRatio"] = float(w.max() / max(w.mean(), 1e-6))
    if nsk:
        nb = ndi.convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant") - sk
        nb = nb[sk]
        out["EndpointsPerLen"] = float((nb == 1).sum()) / nsk
        out["BranchPerLen"] = float((nb >= 3).sum()) / nsk
    else:
        out["EndpointsPerLen"] = out["BranchPerLen"] = 0.0
    if nsk >= 3:
        P = np.stack([xs, ys]).astype(np.float64)
        P -= P.mean(1, keepdims=True)
        u, s, _ = np.linalg.svd(P, full_matrices=False)
        proj, perp = u[:, 0] @ P, u[:, 1] @ P
        span = float(proj.max() - proj.min()) or 1.0
        out["WanderRMS"] = float(np.sqrt((perp ** 2).mean()) / span)
        out["WanderMax"] = float(np.abs(perp).max() / span)
        out["AxisRatioSkel"] = float(s[1] / max(s[0], 1e-6))
        out["SkelTortuosity"] = float(nsk / span)
    else:
        out["WanderRMS"] = out["WanderMax"] = out["AxisRatioSkel"] = 0.0
        out["SkelTortuosity"] = 1.0

    # --- surrounding ring: darker than its OWN neighbourhood, and how flat inside ---
    st = ndi.generate_binary_structure(2, 2)
    ring = ndi.binary_dilation(m, st, iterations=5) & ~ndi.binary_dilation(m, st, iterations=1)
    if ring.sum() < 8:
        ring = ndi.binary_dilation(m, st, iterations=8) & ~m
    ring_f, in_f = f[ring], f[m]
    ring_r, in_r = r[ring], r[m]
    out["RingContrastFlat"] = float(ring_f.mean() - in_f.mean())
    out["RingZFlat"] = float((ring_f.mean() - in_f.mean()) / max(ring_f.std(), 1e-6))
    out["InteriorStdFlat"] = float(in_f.std())
    out["FlatnessRatio"] = float(in_f.std() / max(ring_f.std(), 1e-6))
    out["RingStdFlat"] = float(ring_f.std())
    # --- raw uint16: the only honest absolute darkness (PIL convert("L") CLIPS I;16) ---
    med, madv, sd = tile_stats["raw_med"], tile_stats["raw_mad"], tile_stats["raw_std"]
    out["RawRelDark"] = float((med - in_r.mean()) / max(madv, 1e-6))
    out["RawRingZ"] = float((ring_r.mean() - in_r.mean()) / max(ring_r.std(), 1e-6))
    out["RawInteriorCV"] = float(in_r.std() / max(abs(in_r.mean()), 1e-6))
    out["RawFlatnessRatio"] = float(in_r.std() / max(sd, 1e-6))
    out["RawLogRatio"] = float(np.log10(max(in_r.mean(), 1.0) / max(med, 1.0)))
    out["VesMax"] = float(v[m].max())
    out["VesStd"] = float(v[m].std())
    out["VesP90"] = float(np.percentile(v[m], 90))
    return out


def build_regions(path=PKL, mad_ks=MAD_KS):
    tiles = TB.load(with_raw=True)
    store = {}
    for mk in mad_ks:
        t0 = time.time()
        for i, t in enumerate(tiles):
            st = CP.stages(t["img8"], mad_k=mk)
            labeled, df, raw = st["labeled"], st["df"], t["raw"]
            ts = dict(raw_med=float(np.median(raw)),
                      raw_mad=float(np.median(np.abs(raw - np.median(raw))) * 1.4826),
                      raw_std=float(raw.std()))
            objs = ndi.find_objects(labeled)
            rows, ov, areas = [], [], []
            for lab in df["Label"].values.astype(int):
                mfull = labeled == lab
                rows.append(new_features(mfull, objs[lab - 1], st["flat"], raw, st["ves"], ts))
                areas.append(int(mfull.sum()))
                ov.append(int((mfull & t["gt"]).sum()))      # the ONLY ground-truth touch
            store[(mk, t["frame"])] = dict(
                labels=df["Label"].values.astype(int),
                shipped=df[SHIPPED8].values.astype(np.float64), new=rows,
                area=np.array(areas), gtov=np.array(ov), labeled=labeled.astype(np.int32))
        print(f"  mad_k={mk}: {sum(len(store[(mk,t['frame'])]['area']) for t in tiles)} "
              f"regions over {len(tiles)} tiles in {time.time()-t0:.0f}s", flush=True)
    pickle.dump(store, open(path, "wb"), protocol=4)
    return store


# ==============================================================================
# model.  Everything is pre-specified: logistic regression C=1.0, sample weight
# sqrt(area), decision threshold 0.5, positive label = region with more than tau
# of its pixels inside the ground truth, tau = IoU/(1+IoU) = 0.18.
#
# Why tau = IoU/(1+IoU): adding a region with `a` true and `b` false pixels moves
# pixel IoU from TP/D to (TP+a)/(D+b), an improvement iff a/b > TP/D = IoU. With
# f = a/(a+b) that is f > IoU/(1+IoU); at the shipped IoU 0.2143 that is 0.1765.
# report() section 5 shows the answer moves 0.003 over tau in [0.02, 0.70].
# ==============================================================================
_S, _TILES = None, None


def _load():
    global _S, _TILES
    if _S is None:
        _S = pickle.load(open(PKL, "rb")) if os.path.exists(PKL) else build_regions()
        _TILES = TB.load()
    return _S, _TILES


def _ctx():
    S, tiles = _load()
    order = [t["frame"] for t in tiles]
    spec = {t["frame"]: t["specimen"] for t in tiles}
    # 13 "specimens" are really 3 imaging families; leave-one-family-out is the
    # conservative grouping, because MAR_Amb_AS/_Cast/_HIP are one session.
    fam = {f: ("F_316" if s[:4] in ("2606", "2607") else
               "F_24hr" if s.endswith("_24hr") else "F_MAR") for f, s in spec.items()}
    gt = {t["frame"]: t["gt"] for t in tiles}
    return S, tiles, order, spec, fam, gt


def matrix(mk, feats):
    S, tiles, order, spec, fam, gt = _ctx()
    X, area, frac, fidx, labs = [], [], [], [], []
    for i, fr in enumerate(order):
        d = S[(mk, fr)]
        if not len(d["area"]):
            continue
        cols = [d["shipped"][:, SHIPPED8.index(f)] if f in SHIPPED8
                else np.array([r[f] for r in d["new"]]) for f in feats]
        X.append(np.stack(cols, 1))
        area.append(d["area"]); frac.append(d["gtov"] / np.maximum(d["area"], 1))
        fidx.append(np.full(len(d["area"]), i)); labs.append(d["labels"])
    return (np.concatenate(X), np.concatenate(area), np.concatenate(frac),
            np.concatenate(fidx), np.concatenate(labs))


def paint(mk, fidx, labs, keep):
    S, tiles, order, spec, fam, gt = _ctx()
    rows = []
    for i, fr in enumerate(order):
        d = S[(mk, fr)]
        sel = labs[(fidx == i) & keep]
        pred = np.isin(d["labeled"], sel) if len(sel) else np.zeros(d["labeled"].shape, bool)
        rows.append(TB.counts(pred, gt[fr]))
    return rows


def _fit(kind, Xtr, ytr, wtr):
    if len(np.unique(ytr)) < 2:
        return ("const", float(ytr[0]))
    sc = StandardScaler().fit(Xtr)
    m = {"logit": lambda: LogisticRegression(max_iter=4000, C=1.0),
         "logitC01": lambda: LogisticRegression(max_iter=4000, C=0.1),
         "logitC001": lambda: LogisticRegression(max_iter=4000, C=0.01),
         "rf": lambda: RandomForestClassifier(n_estimators=300, max_depth=3,
                                              min_samples_leaf=8, random_state=0)}[kind]()
    m.fit(sc.transform(Xtr), ytr, sample_weight=wtr)
    return (sc, m)


def _pred(model, X):
    if model[0] == "const":
        return np.full(len(X), model[1])
    return model[1].predict_proba(model[0].transform(X))[:, 1]


def weights(area, mode):
    w = {"none": lambda: np.ones(len(area)), "sqrt": lambda: np.sqrt(area),
         "area": lambda: area.astype(float), "log": lambda: np.log10(area + 1)}[mode]()
    return w / w.mean()


def run_variant(mk, feats=ALLF, kind="logit", wmode="sqrt", tau=0.18, thr=0.5,
                group="specimen", permute=None, rng=None, shuffle_y=False,
                noise_X=False, invert=False):
    """Returns (held-out rows, train-on-all rows). The held-out model for group g is
    fitted on the regions of every OTHER group only."""
    rng = rng or np.random.default_rng(0)
    S, tiles, order, spec, fam, gt = _ctx()
    X, area, frac, fidx, labs = matrix(mk, feats)
    if permute is not None:
        X = X.copy(); X[:, permute] = rng.permutation(X[:, permute])
    if noise_X:
        X = rng.standard_normal(X.shape)
    y = (frac > tau).astype(int)
    w = weights(area, wmode)
    gmap = spec if group == "specimen" else fam
    g = np.array([gmap[order[i]] for i in fidx])
    p_oof = np.zeros(len(y))
    for s in sorted(set(g)):
        tr, te = g != s, g == s
        p_oof[te] = _pred(_fit(kind, X[tr], rng.permutation(y[tr]) if shuffle_y else y[tr],
                               w[tr]), X[te])
    p_all = _pred(_fit(kind, X, rng.permutation(y) if shuffle_y else y, w), X)
    k1, k2 = p_oof >= thr, p_all >= thr
    if invert:
        k1, k2 = ~k1, ~k2
    return paint(mk, fidx, labs, k1), paint(mk, fidx, labs, k2)


# ==============================================================================
# report
# ==============================================================================
def _idx():
    S, tiles, order, spec, fam, gt = _ctx()
    fi = [i for i, t in enumerate(tiles) if t["frame"] == TB.FLOODED][0]
    return fi, [i for i in range(len(tiles)) if i != fi]


def _io25(rows):
    return TB._agg([rows[i] for i in _idx()[1]])["iou"]


def _row(nm, rows):
    a = TB._agg(rows); b = TB._agg([rows[i] for i in _idx()[1]])
    print(f"  {nm:<46} {a['precision']:8.4f} {a['recall']:7.4f} {a['iou']:7.4f} "
          f"{a['f1']:7.4f} | {b['iou']:7.4f}", flush=True)
    return a


def report():
    S, tiles, order, spec, fam, gt = _ctx()
    fi, keep = _idx()
    R0 = lambda: np.random.default_rng(0)

    print("=" * 100)
    print("0) LEAKAGE GUARD -- recompute every feature with the ground truth replaced by")
    print("   noise. The feature functions never receive it, so this must be identical.")
    t = TB.load(with_raw=True)[0]
    st = CP.stages(t["img8"], mad_k=3.0)
    lab, objs, raw = st["labeled"], ndi.find_objects(st["labeled"]), t["raw"]
    ts = dict(raw_med=float(np.median(raw)),
              raw_mad=float(np.median(np.abs(raw - np.median(raw))) * 1.4826),
              raw_std=float(raw.std()))
    ids = st["df"]["Label"].values.astype(int)
    f1 = [new_features(lab == l, objs[l - 1], st["flat"], raw, st["ves"], ts) for l in ids]
    t["gt"] = np.random.default_rng(7).random(t["gt"].shape) > 0.5
    f2 = [new_features(lab == l, objs[l - 1], st["flat"], raw, st["ves"], ts) for l in ids]
    same = all(a == b for x, y in zip(f1, f2) for a, b in zip(x.values(), y.values()))
    print(f"   -> {'IDENTICAL, no leakage path' if same else 'CHANGED -- LEAKAGE'}")
    assert same

    print("\n" + "=" * 100)
    print("1) EVERY ARM.  IoU25 drops the one tile holding the off-specimen void, which is")
    print("   86.5% of all candidate-stage false positives.")
    print(f"  {'arm':<46} {'P':>8} {'R':>7} {'IoU':>7} {'F1':>7} | {'IoU25':>7}")
    base = np.load(SC + "/baseline_rows.npy")
    ship = [dict(tp=int(a), fp=int(b), fn=int(c)) for a, b, c in base]
    _row("SHIPPED detector (baseline)", ship)
    oof, fit = {}, {}
    for mk in MAD_KS:
        X, area, frac, fidx, labs = matrix(mk, SHIPPED8)
        _row(f"mad_k={mk} ALLCAND, no classifier (0 params)",
             paint(mk, fidx, labs, np.ones(len(labs), bool)))
        _row(f"mad_k={mk} ORACLE region classifier", paint(mk, fidx, labs, frac > 0.18))
        a_o, _ = run_variant(mk, SHIPPED8, rng=R0())
        _row(f"mad_k={mk} (a) REFIT-8 held-out", a_o)
        oof[f"mad_k={mk}"], fit[f"mad_k={mk}"] = run_variant(mk, ALLF, rng=R0())
        _row(f"mad_k={mk} (b) REFIT-8+NEW held-out", oof[f"mad_k={mk}"])
        _row(f"mad_k={mk} (b) REFIT-8+NEW TRAIN-ON-ALL", fit[f"mad_k={mk}"])
        fo, _ = run_variant(mk, ALLF, group="family", rng=R0())
        _row(f"mad_k={mk} (b) held-out, leave-one-FAMILY-out", fo)

    print("\n" + "=" * 100)
    print("2) IS THE BRIEF RIGHT that MAR_Amb_AS/_Cast/_HIP are at recall 0.000 at EVERY")
    print("   setting because their crack is brighter than background? Candidate stage only:")
    for mk in MAD_KS:
        for s in ("MAR_Amb_AS", "MAR_Amb_Cast", "MAR_Amb_HIP"):
            ix = [i for i, t in enumerate(tiles) if t["specimen"] == s]
            a = TB._agg([TB.counts(S[(mk, order[i])]["labeled"] > 0, gt[order[i]]) for i in ix])
            print(f"   mad_k={mk} {s:<14} ALLCAND recall {a['recall']:.4f} "
                  f"precision {a['precision']:.4f}")
    print("   -> NO. The candidate stage finds them; the CLASSIFIER is what zeroes them.")

    print("\n" + "=" * 100)
    print("3) HEADLINE through the harness. mad_k is chosen by TB.evaluate's own")
    print("   leave-one-specimen-out selection, so it is never picked on the test fold.")
    r_oof = TB.evaluate("LEVER 4: refit + new features   [HELD-OUT]", oof)
    r_fit = TB.evaluate("LEVER 4: same, trained on all 26 [FITTED]", fit)
    print(f"\n   OVERFIT GAP = {r_fit['fitted']['iou'] - r_oof['loso']['iou']:+.4f}")
    sel = [oof[r_oof["picks"][t["specimen"]]][i] for i, t in enumerate(tiles)]
    print("\n   per-specimen, held-out, vs the shipped baseline:")
    up = dn = sm = 0
    for s in sorted({t["specimen"] for t in tiles}):
        ix = [i for i, t in enumerate(tiles) if t["specimen"] == s]
        a, b = TB._agg([sel[i] for i in ix]), TB._agg([ship[i] for i in ix])
        d = a["iou"] - b["iou"]
        up += d > 0.005; dn += d < -0.005; sm += abs(d) <= 0.005
        print(f"     {s:<20} n={len(ix)}  IoU {b['iou']:7.4f} -> {a['iou']:7.4f} {d:+8.4f}  "
              f"{'IMPROVED' if d > 0.005 else 'REGRESSED' if d < -0.005 else 'unchanged'}")
    print(f"     => IMPROVED {up}   unchanged {sm}   REGRESSED {dn}   of 13 specimens")

    print("\n" + "=" * 100)
    print("4) SABOTAGE on mad_k=3.0. Anything that does not collapse measured nothing.")
    intact, i25 = TB._agg(oof["mad_k=3.0"])["iou"], _io25(oof["mad_k=3.0"])
    print(f"   {'intact':<42} IoU26 {intact:.4f}        IoU25 {i25:.4f}")
    for nm, kw in [("training labels SHUFFLED", dict(shuffle_y=True)),
                   ("features = GAUSSIAN NOISE", dict(noise_X=True))]:
        a = [_io25(run_variant(3.0, ALLF, rng=np.random.default_rng(200 + s), **kw)[0])
             for s in range(10)]
        print(f"   {nm+' (10 seeds)':<42} IoU25 {np.mean(a):.4f}+-{np.std(a):.4f}"
              f"   -> {'COLLAPSED' if np.mean(a) < i25 - 0.10 else 'DID NOT COLLAPSE'}")
    o, _ = run_variant(3.0, ALLF, invert=True, rng=R0())
    print(f"   {'decision INVERTED':<42} IoU25 {_io25(o):.4f}"
          f"          -> {'COLLAPSED' if _io25(o) < i25 - 0.10 else 'DID NOT COLLAPSE'}")
    # NOTE: a mis-wire that only permutes LABEL IDS across tiles does NOT collapse
    # (it still paints real regions of the right tile, IoU25 0.4482). Rotate PIXELS.
    X, area, frac, fidx, labs = matrix(3.0, ALLF)
    y = (frac > 0.18).astype(int); w = weights(area, "sqrt")
    g = np.array([spec[order[i]] for i in fidx]); p = np.zeros(len(y))
    for s in sorted(set(g)):
        tr, te = g != s, g == s
        p[te] = _pred(_fit("logit", X[tr], y[tr], w[tr]), X[te])
    masks = [np.isin(S[(3.0, fr)]["labeled"], labs[(fidx == i) & (p >= 0.5)])
             for i, fr in enumerate(order)]
    rot = [TB.counts(masks[(i + 1) % len(tiles)], tiles[i]["gt"]) for i in range(len(tiles))]
    print(f"   {'predicted mask rotated to the WRONG tile':<42} IoU25 {_io25(rot):.4f}"
          f"          -> {'COLLAPSED' if _io25(rot) < i25 - 0.30 else 'DID NOT COLLAPSE'}")

    print("\n" + "=" * 100)
    print("5) SENSITIVITY (mad_k=3.0)")
    for tau in (0.02, 0.10, 0.18, 0.30, 0.50, 0.70):
        o, f = run_variant(3.0, ALLF, tau=tau, rng=R0())
        print(f"   tau={tau:<5} held-out IoU {TB._agg(o)['iou']:.4f}  fitted {TB._agg(f)['iou']:.4f}")
    for thr in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
        o, _ = run_variant(3.0, ALLF, thr=thr, rng=R0())
        a = TB._agg(o)
        print(f"   thr={thr:<4} held-out P {a['precision']:.4f} R {a['recall']:.4f} "
              f"IoU {a['iou']:.4f}")
    for kind in ("logit", "logitC01", "logitC001", "rf"):
        for wm in ("none", "sqrt", "area"):
            o, _ = run_variant(3.0, ALLF, kind=kind, wmode=wm, rng=R0())
            print(f"   {kind:<10} w={wm:<5} held-out IoU {TB._agg(o)['iou']:.4f}")

    print("\n" + "=" * 100)
    print("6) PERMUTATION IMPORTANCE, mad_k=3.0, drop in HELD-OUT IoU, mean of 5 seeds")
    imp = []
    for j, f in enumerate(ALLF):
        d = [i25 - _io25(run_variant(3.0, ALLF, permute=j,
                                     rng=np.random.default_rng(300 + s))[0]) for s in range(5)]
        imp.append((np.mean(d), f))
    for v, f in sorted(imp, reverse=True):
        print(f"   {f:<22} dIoU25 {v:+.4f}{'   <- shipped feature' if f in SHIPPED8 else ''}")


if __name__ == "__main__":
    if not os.path.exists(PKL):
        print("building region table ...", flush=True)
        build_regions()
    report()
