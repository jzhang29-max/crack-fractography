"""ADVERSARIAL AUDIT of lever3_pixelmodel.py (the 35-feature pixel-wise HGB).

VERDICT: every number in the claim reproduces BIT-FOR-BIT.  The code is honest, the
folds are clean, sabotage collapses it to 0.0000.  But the ATTRIBUTION is wrong and
the method is not needed: a one-line, no-model, no-training threshold on the shipped
detector's OWN decision statistic scores the same held-out IoU.

WHAT REPRODUCED EXACTLY (nothing to report here -- it is all correct)
    their loso.npy vs my independent re-implementation of the fold loop: max |dp| = 0.0
    seed 0/1/2 IoU 0.4147 / 0.3985 / 0.4014   3-seed mean P 0.5666 R 0.5864 IoU 0.4049
    F1 0.5763  (they quote 0.5667/0.5864/0.4049/0.5763 -- rounding only)
    fitted-on-all-26 0.7524.  per-specimen table, 10 improved / 3 regressed, drop-one
    range 0.3567-0.4599: all identical.  Features recompute byte-identical from img8+raw
    and contain no label.  tilebench's three controls pass; the shipped 0.3378/0.3696/
    0.2143 reproduces.  No second scorer was built.  No parameter saw its own fold.

    SABOTAGE (my own, not theirs):
        shuffle training labels   IoU 0.0000
        constant feature matrix   IoU 0.0000
        pure-noise features       IoU 0.0000
        intact model, GT rotated by one tile (wrong-image control)   IoU 0.0129
        intact                    IoU 0.4147
    The method genuinely reads the image.  The score is not coming from anywhere else.

FINDING 1 -- A ONE-LINE THRESHOLD WITH NO MODEL MATCHES IT (the headline problem)
    Feature `fz_s1` in their own stack IS the shipped detector's dark test as a
    continuous number: flatten_background(img8, sigma=40) -> robust z against the tile's
    own median/MAD -> gaussian sigma=1.  Cut it at a constant, LOSO-selected over
    8 values (unanimous pick, overfit gap 0.0000):

                                          P        R      IoU       F1
        shipped mad_k=5.0 (the baseline)  0.3378  0.3696  0.2143  0.3530
        mad_k sweep, LOSO-selected        0.3383  0.4460  0.2382  0.3847
        darkest q% of each tile (no model)0.5309  0.5358  0.3636  0.5333
        fz_s1 < -2.5  (ONE LINE, no model)0.5548  0.6114  0.4101  0.5817
        LEVER3 HGB, seed 0                0.5811  0.5915  0.4147  0.5862
        LEVER3 HGB, 3-seed mean (quoted)  0.5666  0.5864  0.4049  0.5763
    The quoted 3-seed mean is BELOW the one-liner.  The best seed is +0.0046, which is
    inside the 0.0161 seed range they report.  Head to head by specimen the model is
    9 improved / 4 REGRESSED against the one-liner, and it deletes 21,708 true-positive
    pixels to add 17,678 -- a net TP LOSS.  IoU(model, one-liner) is only 0.50, so the
    two find different pixels; they just score the same.
    => "the nonlinearity is the win" is not supported.  Their logistic-regression
       negative result (0.2102) reproduces even with proper feature scaling, so that
       finding is sound -- but a model is not what is doing the work either way.

FINDING 2 -- MOST OF THE GAIN IS DELETING SHIPPED STAGES, WITH ZERO PARAMETERS
    Stage decomposition of the shipped pipeline at its OWN mad_k=5.0 (held-out):
        bare robust cut, no otsu cap/morphology/classifier   IoU 0.3598  F1 0.5292
        + the min(otsu, .) cap                               IoU 0.2836
        + clean_mask (open/close/min_area 13)                IoU 0.3005
        + the region classifier  == FULL SHIPPED             IoU 0.2143
    Deleting three stages, changing no constant and training nothing, is worth +0.1455
    of the claimed +0.1906.  The otsu cap alone costs 0.0762 (it binds on 6/26 tiles);
    the region classifier costs a further 0.0862.  At mad_k=2.5 the bare cut is 0.3971.

FINDING 3 -- ON THE ONLY DETECTOR-FREE LABELS THE MODEL LOSES TO THE BASELINE
    Their leakage note 1 is CONFIRMED independently: 21/26 tiles were opened with the
    shipped detector's mask preloaded (IoU(_ascut, machine_mask crop) = 1.0000 on all
    21, min and median), and 100,596 of 202,632 labelled crack px (49.6%) came from
    that seed.  The brief's "opened BLANK and painted from scratch" is false.
    On the 5 genuinely blank-start tiles they quote 3.0x -- but against the WRONG
    baseline.  Against the one the brief names as current best:
        shipped mad5  0.0541 | mad_k=2.5  0.2305 | fz_s1<-2.5  0.1716 | model  0.1620
    The model is LAST but one, and 0.069 BELOW the plain mad_k=2.5 region pipeline.
    n=5 tiles / 4 specimens, so this decides nothing on its own -- but it is the only
    slice where the old detector did not write the answer, and the claim does not
    survive it.

FINDING 4 -- their flag 6 resolves IN THEIR FAVOUR (reported for completeness)
    Including MAR_AmbB_AS (29 tiles / 14 specimens) RAISES every learned score:
        shipped 0.2013 | mad2.5 0.2331 | fz_s1<-2.5 0.4308 | model 0.4541
    On MAR_AmbB_AS alone: shipped 0.0000, mad2.5 0.0000, one-liner 0.6728, model 0.7095.
    The exclusion was not hiding anything.

WHAT I BELIEVE
    0.4049 held-out IoU for their method, as measured by this harness: verified.
    The gain over the SHIPPED baseline: real, +0.1906.
    The gain over the best no-model alternative: 0.0000 to +0.0046, i.e. nothing.
    Adopt the preprocessing (drop the otsu cap and the region classifier, keep the
    per-tile robust cut); do not adopt the 35-feature model to get this number.

Run: <sem-crack-detector venv>/bin/python -B audit_lever3_pixelmodel.py [--all]
"""
import os, sys, numpy as np

ANALYSIS = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, ANALYSIS)
import tilebench as TB
import crackpipe as CP

FEATCACHE = os.path.join(TB.SC, "pixelmodel_cache")      # written by lever3_pixelmodel
FZ_S1 = 1                                                # index of fz_s1 in their 35
MACH = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/crack_export/derived/machine_masks"
BLANK = {"260622_316_H_b2_front_CBS_04__crop_423_59_512x512",
         "260622_316_amb_b3_CBS_02__crop_3853_3216_512x512",
         "HIP_24hr_SE_Side_006__crop_3853_3216_512x512",
         "HIP_24hr_SE_Side_006__crop_4695_807_512x512",
         "MAR_Amb_Cast_ETD_0003__crop_2841_1211_512x512"}


def _feat(frame):
    return np.asarray(np.load(os.path.join(FEATCACHE, frame + ".npy"), mmap_mode="r"))


def _iou(rows):
    tp, fp, fn = (sum(r[k] for r in rows) for k in ("tp", "fp", "fn"))
    return tp / max(tp + fp + fn, 1)


def finding1_one_line_threshold(tiles):
    """A no-model cut on the shipped detector's own statistic, LOSO-selected."""
    print("\nFINDING 1 -- no-model baselines through the SAME harness")
    TB.evaluate("mad_k sweep, LOSO-selected (the 'current best known' lever)",
                {f"mad{k}": [TB.counts(CP.predict(t["img8"], mad_k=k), t["gt"]) for t in tiles]
                 for k in (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)})
    TB.evaluate("NO MODEL: darkest q% of each tile (their `rank` feature alone)",
                {f"rank<{q}": [TB.counts(_feat(t["frame"])[:, :, 6] < q, t["gt"]) for t in tiles]
                 for q in (0.01, 0.02, 0.03, 0.04, 0.05, 0.07, 0.10, 0.15)})
    TB.evaluate("NO MODEL: fz_s1 < c  -- ONE LINE, no training, LOSO-selected",
                {f"fz_s1<{c}": [TB.counts(_feat(t["frame"])[:, :, FZ_S1] < c, t["gt"]) for t in tiles]
                 for c in (-0.5, -1, -1.5, -2, -2.5, -3, -4, -5)})


def finding2_stage_decomposition(tiles):
    """Which shipped stage destroys the score. No parameter changes."""
    print("\nFINDING 2 -- where the shipped pipeline loses it (mad_k at its own default)")
    for k in (5.0, 2.5):
        S = [CP.stages(t["img8"], mad_k=k) for t in tiles]
        for nm, P in (("bare robust cut (no otsu cap, no clean, no classifier)",
                       [s["smooth"] < (s["med"] - k * s["mad"]) for s in S]),
                      ("+ min(otsu,.) cap", [s["dark"] for s in S]),
                      ("+ clean_mask", [s["clean"] for s in S]),
                      ("+ region classifier == FULL SHIPPED",
                       [CP.predict(t["img8"], mad_k=k) for t in tiles])):
            TB.evaluate(f"mad_k={k}: {nm}",
                        {"x": [TB.counts(P[i], t["gt"]) for i, t in enumerate(tiles)]}, quiet=True)
            r = TB.evaluate(f"mad_k={k}: {nm}",
                            {"x": [TB.counts(P[i], t["gt"]) for i, t in enumerate(tiles)]},
                            quiet=True)["loso"]
            print(f"   mad_k={k}  {nm:<52} IoU {r['iou']:.4f}  F1 {r['f1']:.4f}")
        print(f"   otsu was the binding cut on "
              f"{sum(1 for s in S if s['otsu'] < s['med'] - k * s['mad'])}/{len(tiles)} tiles")


def finding3_provenance(tiles, model_pred):
    """Is the ground truth the old detector's own output, and what happens without it."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    print("\nFINDING 3 -- label provenance, re-derived from disk")
    seen, ious, kept, gtot, seeded = {}, [], 0, 0, 0
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
    print(f"   {seeded}/{len(tiles)} tiles opened with the detector's mask preloaded; "
          f"IoU(_ascut, machine crop) min {min(ious):.4f} median {float(np.median(ious)):.4f}")
    print(f"   {kept:,} of {gtot:,} labelled crack px ({kept/gtot:.1%}) came from that seed")

    P = {"shipped mad5": [CP.predict(t["img8"]) for t in tiles],
         "mad2.5": [CP.predict(t["img8"], mad_k=2.5) for t in tiles],
         "fz_s1<-2.5": [_feat(t["frame"])[:, :, FZ_S1] < -2.5 for t in tiles],
         "LEVER3 model": list(model_pred)}
    R = {k: [TB.counts(v[i], t["gt"]) for i, t in enumerate(tiles)] for k, v in P.items()}
    for nm, sel in (("all 26", lambda t: True),
                    ("seeded 21", lambda t: t["frame"] not in BLANK),
                    ("BLANK-START 5", lambda t: t["frame"] in BLANK)):
        idx = [i for i, t in enumerate(tiles) if sel(t)]
        print(f"   {nm:<15}" + "".join(f"  {k} {_iou([R[k][i] for i in idx]):.4f}" for k in P))
    print("   -> on the only detector-free labels the model is BELOW plain mad_k=2.5")


def sabotage(tiles, model_pred):
    """Break it on purpose. A check that passes on broken code measured nothing."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    print("\nSABOTAGE -- the score must collapse")
    specs = sorted({t["specimen"] for t in tiles})
    for mode in ("shuffleY", "constX", "noiseX"):
        rng = np.random.default_rng(0)
        out = np.zeros((len(tiles), 512, 512), np.float32)
        for sp in specs:
            Xs, ys, ws = [], [], []
            for i in [i for i, t in enumerate(tiles) if t["specimen"] != sp]:
                X = _feat(tiles[i]["frame"]).reshape(-1, 35).copy()
                if mode == "constX":
                    X[:] = 1.0
                if mode == "noiseX":
                    X = rng.standard_normal(X.shape).astype(np.float32)
                y = tiles[i]["gt"].ravel()
                pos, neg = np.flatnonzero(y), np.flatnonzero(~y)
                sel = rng.choice(neg, min(40000, neg.size), replace=False)
                Xs += [X[pos], X[sel]]
                ys += [np.ones(pos.size, np.int8), np.zeros(sel.size, np.int8)]
                ws += [np.ones(pos.size, np.float32),
                       np.full(sel.size, neg.size / sel.size, np.float32)]
            X, y, w = np.concatenate(Xs), np.concatenate(ys), np.concatenate(ws)
            if mode == "shuffleY":
                y = rng.permutation(y)
            m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.1,
                                               max_leaf_nodes=31, min_samples_leaf=200,
                                               l2_regularization=1.0, random_state=0
                                               ).fit(X, y, sample_weight=w)
            for i in [i for i, t in enumerate(tiles) if t["specimen"] == sp]:
                Xi = _feat(tiles[i]["frame"]).reshape(-1, 35).copy()
                if mode == "constX":
                    Xi[:] = 1.0
                if mode == "noiseX":
                    Xi = rng.standard_normal(Xi.shape).astype(np.float32)
                out[i] = m.predict_proba(Xi)[:, 1].reshape(512, 512)
        print(f"   {mode:<10} IoU {_iou([TB.counts(out[i] >= 0.5, t['gt']) for i, t in enumerate(tiles)]):.4f}"
              "   (must be ~0)")
    rot = _iou([TB.counts(model_pred[i], tiles[(i + 1) % len(tiles)]["gt"])
                for i in range(len(tiles))])
    print(f"   intact model scored against the WRONG tile's GT: IoU {rot:.4f}   (must be ~0)")
    print(f"   intact: IoU {_iou([TB.counts(model_pred[i], t['gt']) for i, t in enumerate(tiles)]):.4f}")


def main():
    print("CONTROLS"); TB.controls()
    tiles = TB.load()
    model_pred = np.load(os.path.join(FEATCACHE, "loso.npy")) >= 0.5
    TB.evaluate("LEVER3 as claimed (their cached LOSO probabilities, thr 0.5)",
                {"x": [TB.counts(model_pred[i], t["gt"]) for i, t in enumerate(tiles)]})
    finding1_one_line_threshold(tiles)
    finding2_stage_decomposition(tiles)
    finding3_provenance(tiles, model_pred)
    if "--all" in sys.argv:
        sabotage(tiles, model_pred)
    else:
        print("\n(pass --all to re-run the sabotage controls, ~10 min)")


if __name__ == "__main__":
    main()
