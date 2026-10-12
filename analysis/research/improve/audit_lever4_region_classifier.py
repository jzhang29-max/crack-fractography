"""ADVERSARIAL AUDIT of improve/lever4_region_classifier.py.

Run:
    cd <scratchpad>/audit_lever4
    /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python -B \
        /Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/improve/audit_lever4_region_classifier.py

Everything scores through analysis/tilebench.py. Nothing writes outside the scratchpad.
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
SC = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
      "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
os.environ.setdefault("MPLCONFIGDIR", SC + "/mpl")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/improve")
sys.dont_write_bytecode = True
import numpy as np
import tilebench as TB
import lever4_region_classifier as L4

MAD_KS = L4.MAD_KS
ALLF = L4.ALLF
R0 = lambda: np.random.default_rng(0)


def ctx():
    return L4._ctx()


def _agg(rows):
    return TB._agg(rows)


def voidless(rows):
    fi = L4._idx()[0]
    return [r for i, r in enumerate(rows) if i != fi]


def pr(label, rows, extra=""):
    a = _agg(rows); b = _agg(voidless(rows))
    print(f"  {label:<52} P {a['precision']:.4f} R {a['recall']:.4f} IoU {a['iou']:.4f} "
          f"F1 {a['f1']:.4f} | IoU25 {b['iou']:.4f} {extra}", flush=True)
    return a


# ---------------------------------------------------------------- 1. nested selection
def nested(feats=ALLF, kind="logit", wmode="sqrt", tau=0.18, thr=0.5,
           group="specimen", seed=0, Xmap=None):
    """Fully nested: mad_k picked by an INNER LOSO over the training specimens only,
    then refit on all 12 and applied to the held-out specimen. No choice sees the fold.

    Xmap(mk, X) -> X lets a sabotage mutate the design matrix identically everywhere.
    """
    S, tiles, order, spec, fam, gt = ctx()
    gmap = spec if group == "specimen" else fam
    M = {}
    for mk in MAD_KS:
        X, area, frac, fidx, labs = L4.matrix(mk, feats)
        if Xmap is not None:
            X = Xmap(mk, X)
        g = np.array([gmap[order[i]] for i in fidx])
        M[mk] = dict(X=X, y=(frac > tau).astype(int), w=L4.weights(area, wmode),
                     g=g, fidx=fidx, labs=labs)

    rng = np.random.default_rng(seed)
    groups = sorted(set(next(iter(M.values()))["g"]))
    # out-of-fold keep-flags per mad_k, assembled fold by fold
    keep = {mk: np.zeros(len(M[mk]["y"]), bool) for mk in MAD_KS}
    picks = {}
    for s in groups:
        inner_groups = [u for u in groups if u != s]
        score = {}
        for mk in MAD_KS:
            d = M[mk]
            p = np.zeros(len(d["y"]))
            for u in inner_groups:                       # inner LOSO, training only
                tr = (d["g"] != u) & (d["g"] != s)
                te = d["g"] == u
                p[te] = L4._pred(L4._fit(kind, d["X"][tr], d["y"][tr], d["w"][tr]), d["X"][te])
            k = p >= thr
            rows = L4.paint(mk, d["fidx"], d["labs"], k)
            tr_tiles = [i for i, fr in enumerate(order) if gmap[fr] != s]
            score[mk] = _agg([rows[i] for i in tr_tiles])["iou"]
        best = max(MAD_KS, key=lambda m: score[m])
        picks[s] = best
        d = M[best]
        tr, te = d["g"] != s, d["g"] == s
        p = L4._pred(L4._fit(kind, d["X"][tr], d["y"][tr], d["w"][tr]), d["X"][te])
        keep[best][np.where(te)[0]] = p >= thr
    # paint each tile with the mad_k its own fold selected
    rows = []
    for i, fr in enumerate(order):
        mk = picks[gmap[fr]]
        d = M[mk]
        sel = d["labs"][(d["fidx"] == i) & keep[mk]]
        pred = np.isin(L4._S[(mk, fr)]["labeled"], sel) if len(sel) else \
            np.zeros(L4._S[(mk, fr)]["labeled"].shape, bool)
        rows.append(TB.counts(pred, gt[fr]))
    return rows, picks


def main():
    S, tiles, order, spec, fam, gt = ctx()
    base = np.load(SC + "/baseline_rows.npy")
    ship = [dict(tp=int(a), fp=int(b), fn=int(c)) for a, b, c in base]
    fi, keep25 = L4._idx()

    print("=" * 112)
    print("A) REFERENCE ARMS (all through tilebench). IoU25 = the 25 tiles without the "
          "off-specimen void tile.")
    pr("SHIPPED baseline (mad_k=5.0, shipped clf)", ship)
    allcand = {}
    for mk in MAD_KS:
        X, area, frac, fidx, labs = L4.matrix(mk, L4.SHIPPED8)
        allcand[f"allcand_{mk}"] = L4.paint(mk, fidx, labs, np.ones(len(labs), bool))
        pr(f"TRIVIAL: mad_k={mk}, keep EVERY candidate, no model", allcand[f"allcand_{mk}"])
    r_tr = TB.evaluate("TRIVIAL allcand, mad_k by harness LOSO", allcand, quiet=True)
    print(f"    -> trivial-alternative HELD-OUT IoU {r_tr['loso']['iou']:.4f}  "
          f"(P {r_tr['loso']['precision']:.4f} R {r_tr['loso']['recall']:.4f})")

    print()
    print("=" * 112)
    print("B) THE CLAIM, as they report it, vs a FULLY NESTED selection of mad_k.")
    print("   Their TB.evaluate call picks mad_k on training-fold rows whose own models")
    print("   were trained on sets that INCLUDED the test specimen. Nested removes that.")
    oof = {f"mad_k={mk}": L4.run_variant(mk, ALLF, rng=R0())[0] for mk in MAD_KS}
    r_claim = TB.evaluate("their headline", oof, quiet=True)
    print(f"  their headline (harness LOSO over mad_k) : "
          f"P {r_claim['loso']['precision']:.4f} R {r_claim['loso']['recall']:.4f} "
          f"IoU {r_claim['loso']['iou']:.4f} F1 {r_claim['loso']['f1']:.4f}")
    nrows, npicks = nested()
    pr("FULLY NESTED (inner LOSO picks mad_k)", nrows)
    print(f"    nested mad_k picks: {npicks}")
    nfam, nfpicks = nested(group="family")
    pr("FULLY NESTED, leave-one-FAMILY-out", nfam)
    print(f"    nested family picks: {nfpicks}")

    print()
    print("=" * 112)
    print("C) IS IT ONE SPECIMEN? Jackknife: delete each specimen's tiles entirely and")
    print("   recompute the POOLED held-out IoU of both arms.")
    sel = [oof[r_claim["picks"][t["specimen"]]][i] for i, t in enumerate(tiles)]
    print(f"  {'deleted specimen':<22} {'n':>2}  {'baseline IoU':>12} {'method IoU':>11} {'gain':>9}")
    print(f"  {'(none)':<22} {26:>2}  {_agg(ship)['iou']:12.4f} {_agg(sel)['iou']:11.4f} "
          f"{_agg(sel)['iou']-_agg(ship)['iou']:+9.4f}")
    gains = []
    for sp in sorted({t["specimen"] for t in tiles}):
        ix = [i for i, t in enumerate(tiles) if t["specimen"] != sp]
        a, b = _agg([sel[i] for i in ix]), _agg([ship[i] for i in ix])
        gains.append((a["iou"] - b["iou"], sp))
        print(f"  {sp:<22} {26-len(ix):>2}  {b['iou']:12.4f} {a['iou']:11.4f} "
              f"{a['iou']-b['iou']:+9.4f}")
    print(f"  -> worst-case gain after deleting any single specimen: "
          f"{min(gains)[0]:+.4f} (dropping {min(gains)[1]})")

    print()
    print("  Drop the ONE void TILE only (not the whole specimen):")
    print(f"    baseline IoU25 {_agg(voidless(ship))['iou']:.4f}   "
          f"method IoU25 {_agg(voidless(sel))['iou']:.4f}   "
          f"gain {_agg(voidless(sel))['iou']-_agg(voidless(ship))['iou']:+.4f}")
    tv, fv = ship[fi], sel[fi]
    tot_fp = sum(r["fp"] for r in ship)
    print(f"    void tile alone: baseline tp {tv['tp']:,} fp {tv['fp']:,} fn {tv['fn']:,}"
          f"  ({tv['fp']/max(tot_fp,1):.1%} of ALL baseline FP)")
    print(f"    void tile alone: method   tp {fv['tp']:,} fp {fv['fp']:,} fn {fv['fn']:,}")

    print()
    print("=" * 112)
    print("D) DOES IT DELETE REAL CRACK TO BUY PRECISION? TP kept/lost vs keep-everything,")
    print("   at MATCHED mad_k (no model vs model).")
    for mk in MAD_KS:
        a = _agg(allcand[f"allcand_{mk}"]); m = _agg(L4.run_variant(mk, ALLF, rng=R0())[0])
        tpa = sum(r["tp"] for r in allcand[f"allcand_{mk}"])
        rows_m = L4.run_variant(mk, ALLF, rng=R0())[0]
        tpm = sum(r["tp"] for r in rows_m); fpa = sum(r["fp"] for r in allcand[f"allcand_{mk}"])
        fpm = sum(r["fp"] for r in rows_m)
        print(f"  mad_k={mk}: TP {tpa:,} -> {tpm:,} ({(tpm-tpa)/max(tpa,1):+.1%})   "
              f"FP {fpa:,} -> {fpm:,} ({(fpm-fpa)/max(fpa,1):+.1%})   "
              f"IoU {a['iou']:.4f} -> {m['iou']:.4f}  | IoU25 "
              f"{_agg(voidless(allcand[f'allcand_{mk}']))['iou']:.4f} -> "
              f"{_agg(voidless(rows_m))['iou']:.4f}")

    print()
    print("=" * 112)
    print("E) MY OWN SABOTAGE. mad_k=3.0, held-out. Reference: intact IoU26 "
          f"{_agg(oof['mad_k=3.0'])['iou']:.4f} / IoU25 {_agg(voidless(oof['mad_k=3.0']))['iou']:.4f}.")
    print("   A sabotage only counts if it falls BELOW the no-model trivial arm "
          f"(IoU25 {_agg(voidless(allcand['allcand_3.0']))['iou']:.4f}).")
    TOP = ["MeanWidth", "RingStdFlat", "Eccentricity", "RawInteriorCV", "RawRingZ",
           "RawFlatnessRatio", "WanderRMS"]
    jtop = [ALLF.index(f) for f in TOP]

    def mk_const(cols):
        def f(mk, X):
            X = X.copy(); X[:, cols] = 0.0; return X
        return f

    def mk_shuffle(cols, seed):
        rg = np.random.default_rng(seed)
        def f(mk, X):
            X = X.copy()
            for c in cols:
                X[:, c] = rg.permutation(X[:, c])
            return X
        return f

    runs = [("top-7 features ZEROED (constant)", mk_const(jtop)),
            ("ALL 32 features ZEROED", mk_const(list(range(len(ALLF))))),
            ("top-7 features row-SHUFFLED", mk_shuffle(jtop, 11)),
            ("ALL 32 features row-SHUFFLED", mk_shuffle(list(range(len(ALLF))), 12))]
    for nm, fn in runs:
        rows = []
        for mk in [3.0]:
            X, area, frac, fidx, labs = L4.matrix(mk, ALLF)
            X = fn(mk, X)
            y = (frac > 0.18).astype(int); w = L4.weights(area, "sqrt")
            g = np.array([spec[order[i]] for i in fidx]); p = np.zeros(len(y))
            for s in sorted(set(g)):
                tr, te = g != s, g == s
                p[te] = L4._pred(L4._fit("logit", X[tr], y[tr], w[tr]), X[te])
            rows = L4.paint(mk, fidx, labs, p >= 0.5)
        pr(nm, rows)
    print("   (10-seed means for shuffles, since one seed can reject the void by luck):")
    for nm, cols in [("top-7 row-SHUFFLED", jtop), ("ALL 32 row-SHUFFLED", list(range(len(ALLF))))]:
        v26, v25 = [], []
        for s in range(10):
            X, area, frac, fidx, labs = L4.matrix(3.0, ALLF)
            rg = np.random.default_rng(500 + s); X = X.copy()
            for c in cols:
                X[:, c] = rg.permutation(X[:, c])
            y = (frac > 0.18).astype(int); w = L4.weights(area, "sqrt")
            g = np.array([spec[order[i]] for i in fidx]); p = np.zeros(len(y))
            for u in sorted(set(g)):
                tr, te = g != u, g == u
                p[te] = L4._pred(L4._fit("logit", X[tr], y[tr], w[tr]), X[te])
            rr = L4.paint(3.0, fidx, labs, p >= 0.5)
            v26.append(_agg(rr)["iou"]); v25.append(_agg(voidless(rr))["iou"])
        print(f"   {nm:<52} IoU26 {np.mean(v26):.4f}+-{np.std(v26):.4f}   "
              f"IoU25 {np.mean(v25):.4f}+-{np.std(v25):.4f}")

    print()
    print("=" * 112)
    print("F) HOW SMALL A MODEL REPRODUCES IT? (over-parameterisation check, nested mad_k)")
    for feats, nm in [(TOP, "top-7 only"),
                      (["RawFlatnessRatio", "RawInteriorCV", "MeanWidth"], "3 features"),
                      (["RawFlatnessRatio"], "1 feature (RawFlatnessRatio)"),
                      (L4.SHIPPED8, "shipped 8 only"),
                      (ALLF, "all 32 (their config)")]:
        rows, pk = nested(feats=feats)
        pr(f"nested, {nm} ({len(feats)} feats)", rows)

    print()
    print("=" * 112)
    print("G) NO-MODEL THRESHOLD ALTERNATIVES through the same harness")
    import crackpipe as CP
    glob = {}
    for q in (1.0, 2.0, 3.0, 5.0):
        rr = []
        for t in tiles:
            thr = np.percentile(t["img8"], q)
            rr.append(TB.counts(t["img8"] <= thr, t["gt"]))
        glob[f"global p{q}"] = rr
    rg = TB.evaluate("global percentile threshold, no model", glob, quiet=True)
    print(f"  global dark percentile threshold, harness LOSO: "
          f"P {rg['loso']['precision']:.4f} R {rg['loso']['recall']:.4f} "
          f"IoU {rg['loso']['iou']:.4f}")
    print(f"  mark everything: P 0.0297 R 1.0000 IoU 0.0297 (harness control)")


if __name__ == "__main__":
    main()
