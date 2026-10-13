"""Q3 -- IS THE THRESHOLD TIE REAL, AND WHAT COULD THIS CORPUS DETECT IF IT WEREN'T?

Two separate questions, and the second is the one that governs every other arm in this
workflow:

  (a) Paired across the 13 specimens, is CURRENT MODEL - one-line threshold distinguishable
      from zero? Exact Wilcoxon signed-rank, sign test, and a specimen bootstrap CI.
  (b) What is the SMALLEST clDice gain this corpus could detect at n = 13? Anybody who
      reports "+0.03 clDice" on 26 tiles needs this number next to it.

The unit of analysis is the SPECIMEN, not the tile: six tiles come from MAR_H_AS alone, so
13 is the real n and treating 26 tiles as 26 independent draws doubles the apparent power.

Two one-line arms are carried, because "one line" is ambiguous and the answer should not
depend on which one is meant:
  oneline_fz    fz < c, c leave-one-specimen-out selected. Literally one line, no cleaning.
  oneline_mad   the darkness cut at a leave-one-specimen-out mad_k, then the SAME
                clean_mask + 40 px region floor the shipped path uses. This is the
                like-for-like arm -- it differs from v1.49.1 ONLY in that v1.49.1 unions
                seven flattening radii where this one uses the single shipped radius.
"""
import os, sys, json, itertools
import numpy as np
from scipy import ndimage as ndi, stats
from skimage import filters
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import approach4_lib as L
import detect_cracks as D

MAD_GRID = (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)
BOOT = 20000
RNG = np.random.default_rng(20261012)


def region40(m):
    c = D.clean_mask(m, 1, 3, 13)
    lab, _ = ndi.label(c)
    sz = np.bincount(lab.ravel()); sz[0] = 0
    return sz[lab] >= L.FEATURE_MIN_AREA


def build_arms(tiles):
    rows = {}
    rows["current"] = [L.score_tile(t["arms"]["current"], t["gt"], sgt=t["skel_gt"]) for t in tiles]
    rows["trace3"] = [L.score_tile(t["arms"]["trace3"], t["gt"], sgt=t["skel_gt"]) for t in tiles]
    rows["frangi"] = None
    fam_fz, fam_mad = [], []
    for c in L.ONE_LINE_GRID:
        k = "fz_%.1f" % c
        rows[k] = [L.score_tile(t["fz"] < c, t["gt"], sgt=t["skel_gt"]) for t in tiles]
        fam_fz.append(k)
    for mk in MAD_GRID:
        k = "mad_%.1f" % mk
        masks = []
        for t in tiles:
            sm = filters.gaussian(t["flat40"], sigma=1, preserve_range=True)
            med = np.median(sm); mad = np.median(np.abs(sm - med)) * 1.4826
            masks.append(region40((sm < min(filters.threshold_otsu(sm), med - mk * mad))
                                  | (t["img8"] < L.ABSOLUTE_DARK)))
        rows[k] = [L.score_tile(m, t["gt"], sgt=t["skel_gt"]) for m, t in zip(masks, tiles)]
        fam_mad.append(k)
    fkeys = [k for k in tiles[0]["arms"] if k.startswith("frangi_")]
    for k in fkeys:
        rows[k] = [L.score_tile(t["arms"][k], t["gt"], sgt=t["skel_gt"]) for t in tiles]
    rows["random"] = [L.score_tile(t["arms"]["random"], t["gt"], sgt=t["skel_gt"]) for t in tiles]
    del rows["frangi"]
    held = {}
    for nm, fam in (("oneline_fz", fam_fz), ("oneline_mad", fam_mad), ("frangi", fkeys)):
        h, picks, fit = L.loso_pick(tiles, rows, fam)
        held[nm] = (h, picks, fit)
    return rows, held


def per_specimen(tiles, rows, metric="cldice"):
    """One number per specimen: the mean over that specimen's tiles, matching the
    per-tile-mean aggregation the headline clDice uses."""
    specs = sorted({t["specimen"] for t in tiles})
    out = []
    for sp in specs:
        idx = [i for i, t in enumerate(tiles) if t["specimen"] == sp]
        out.append(float(np.mean([rows[i][metric] for i in idx])))
    return specs, np.array(out)


def paired(a, b, labels, name_a, name_b, boot=BOOT):
    d = a - b
    n = len(d)
    res = dict(mean_diff=float(d.mean()), median_diff=float(np.median(d)),
               n_better=int((d > 0).sum()), n_worse=int((d < 0).sum()),
               n_tied=int((d == 0).sum()))
    try:
        w = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided",
                           method="exact" if n <= 25 else "auto")
        res["wilcoxon_p"] = float(w.pvalue)
    except Exception as e:
        res["wilcoxon_p"] = float("nan")
    res["ttest_p"] = float(stats.ttest_rel(a, b).pvalue)
    k = int((d > 0).sum()); m = int((d != 0).sum())
    res["sign_p"] = float(stats.binomtest(k, m, 0.5).pvalue) if m else 1.0
    bs = np.array([d[RNG.integers(0, n, n)].mean() for _ in range(boot)])
    res["ci95"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    res["sd_diff"] = float(d.std(ddof=1))
    res["corr"] = float(np.corrcoef(a, b)[0, 1])
    print(f"\n  {name_a}  minus  {name_b}")
    print(f"    mean difference   {res['mean_diff']:+.4f}   median {res['median_diff']:+.4f}")
    print(f"    specimens better/worse/tied   {res['n_better']} / {res['n_worse']} / {res['n_tied']}  of {n}")
    print(f"    bootstrap 95% CI on the mean difference  [{res['ci95'][0]:+.4f}, {res['ci95'][1]:+.4f}]")
    print(f"    Wilcoxon exact p {res['wilcoxon_p']:.4f}    sign test p {res['sign_p']:.4f}"
           f"    paired t p {res['ttest_p']:.4f}")
    print(f"    sd of the paired difference {res['sd_diff']:.4f}   correlation between arms "
          f"{res['corr']:+.3f}")
    worst = np.argsort(d)
    print("    per specimen: " + ", ".join(f"{labels[i]} {d[i]:+.3f}" for i in worst))
    return res


def mde(sd_diff, n=13, alpha=0.05, power=0.80):
    """Smallest true mean difference a paired t-test at this n would reject 80% of the time."""
    from scipy.stats import t as tdist, nct
    tc = tdist.ppf(1 - alpha / 2, n - 1)
    lo, hi = 0.0, 10 * max(sd_diff, 1e-9)
    for _ in range(200):
        mid = (lo + hi) / 2
        ncp = mid / (sd_diff / np.sqrt(n))
        pw = 1 - nct.cdf(tc, n - 1, ncp) + nct.cdf(-tc, n - 1, ncp)
        if pw < power:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main():
    tiles = L.tiles_with_arms()
    rows, held = build_arms(tiles)
    specs = sorted({t["specimen"] for t in tiles})

    named = {"CURRENT MODEL (v1.49.1)": rows["current"],
             "oneline_fz  (LOSO)": held["oneline_fz"][0],
             "oneline_mad (LOSO)": held["oneline_mad"][0],
             "ridge filter (LOSO)": held["frangi"][0],
             "a correct 3 px trace": rows["trace3"],
             "random, area-matched": rows["random"]}
    print("ARMS, per-tile-mean clDice (26 tiles, LOSO where a parameter exists)")
    for nm, r in named.items():
        m = L.pool(r)
        print(f"  {nm:<26} clDice {m['cldice_mean']:.4f}   IoU {m['iou']:.4f}   "
              f"Tsens {m['tsens_mean']:.4f} Tprec {m['tprec_mean']:.4f}")
    print(f"  oneline_fz  LOSO picks {sorted(set(held['oneline_fz'][1].values()))}")
    print(f"  oneline_mad LOSO picks {sorted(set(held['oneline_mad'][1].values()))}")

    # --------------------------------------------------------------- per-specimen scores
    sv = {nm: per_specimen(tiles, r)[1] for nm, r in named.items()}
    print(f"\nPER-SPECIMEN clDice ({len(specs)} specimens -- THIS is the n)")
    print(f"  {'specimen':<20}" + "".join(f"{nm.split('(')[0].strip()[:12]:>14}" for nm in named))
    for i, sp in enumerate(specs):
        print(f"  {sp:<20}" + "".join(f"{sv[nm][i]:14.4f}" for nm in named))
    print(f"  {'mean':<20}" + "".join(f"{sv[nm].mean():14.4f}" for nm in named))
    print(f"  {'sd across specimens':<20}" + "".join(f"{sv[nm].std(ddof=1):14.4f}" for nm in named))

    # --------------------------------------------------------------- (a) is the tie real
    print("\n" + "=" * 86)
    print("(a) IS THE TIE REAL?  paired across the 13 specimens")
    print("=" * 86)
    out = {}
    cur = sv["CURRENT MODEL (v1.49.1)"]
    for nm in ("oneline_mad (LOSO)", "oneline_fz  (LOSO)"):
        out[nm] = paired(cur, sv[nm], specs, "CURRENT MODEL", nm)
    # a method that is genuinely different, as a positive control for the test itself
    out["ridge"] = paired(cur, sv["ridge filter (LOSO)"], specs, "CURRENT MODEL", "ridge filter")
    out["random"] = paired(cur, sv["random, area-matched"], specs, "CURRENT MODEL", "random")

    # --------------------------------------------------------------- (b) what is detectable
    print("\n" + "=" * 86)
    print("(b) WHAT IS THE SMALLEST clDice GAIN THIS CORPUS COULD DETECT AT n = 13?")
    print("=" * 86)
    sd_spec = float(np.mean([sv[nm].std(ddof=1) for nm in
                             ("CURRENT MODEL (v1.49.1)", "oneline_mad (LOSO)")]))
    print(f"\n  Between-specimen sd of clDice, averaged over the two arms: {sd_spec:.4f}")
    print("  A paired test only sees the sd of the DIFFERENCE, which depends on how")
    print("  correlated the new method is with the baseline. sd_diff = sd * sqrt(2(1-r)).")
    print(f"\n  {'correlation r with the baseline':<36}{'sd of difference':>18}"
          f"{'detectable gain (80% power)':>30}")
    for r in (0.99, 0.95, 0.90, 0.80, 0.60, 0.30, 0.00):
        sdd = sd_spec * np.sqrt(2 * (1 - r))
        print(f"  {('r = %.2f' % r):<36}{sdd:18.4f}{mde(sdd):30.4f}")
    print("\n  And from the sd actually OBSERVED between each pair of arms:")
    for nm in ("oneline_mad (LOSO)", "oneline_fz  (LOSO)"):
        sdd = out[nm]["sd_diff"]
        print(f"    vs {nm:<24} observed sd_diff {sdd:.4f} (r {out[nm]['corr']:+.3f})"
              f"  -> detects {mde(sdd):+.4f} or larger")
    sdd_r = out["ridge"]["sd_diff"]
    print(f"    vs {'a structurally different method (the ridge filter)':<24}"
          f" observed sd_diff {sdd_r:.4f} (r {out['ridge']['corr']:+.3f})"
          f"  -> detects {mde(sdd_r):+.4f} or larger")

    # nonparametric floors, which is what a Wilcoxon on 13 specimens can actually do
    print(f"\n  NONPARAMETRIC FLOORS AT n = 13, which is what a rank test can do here:")
    print(f"    smallest two-sided Wilcoxon p attainable (all 13 same sign, max ranks): "
          f"{stats.wilcoxon(np.arange(1, 14).astype(float), np.zeros(13), method='exact').pvalue:.5f}")
    for k in (13, 12, 11, 10, 9):
        print(f"    sign test, {k:>2} of 13 specimens improve: p = "
              f"{stats.binomtest(k, 13, 0.5).pvalue:.4f}"
              f"{'   <- clears 0.05' if stats.binomtest(k, 13, 0.5).pvalue < 0.05 else ''}")

    # empirical power: shift the observed difference vector and resample specimens
    print("\n  EMPIRICAL POWER -- take the observed CURRENT-minus-oneline_mad difference")
    print("  vector, add a constant gain, resample the 13 specimens, count rejections.")
    print("  Each test is centred on the location IT tests, or its own null is false and")
    print("  the curve measures the miscentring instead of the power: the Wilcoxon on the")
    print("  Hodges-Lehmann pseudo-median, the sign test on the median. The delta = 0 row")
    print("  is the calibration check and must come out near 0.05.")
    draw = cur - sv["oneline_mad (LOSO)"]
    hl = float(np.median([(draw[i] + draw[j]) / 2 for i in range(13) for j in range(i, 13)]))
    d_w = draw - hl
    d_s = draw - np.median(draw)
    print(f"  {'true gain':>10}{'Wilcoxon power':>17}{'sign-test power':>18}")
    N = 4000
    for delta in (0.00, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20):
        rej_w = rej_s = 0
        for _ in range(N):
            idx = RNG.integers(0, 13, 13)
            xw = d_w[idx] + delta
            xs = d_s[idx] + delta
            if np.ptp(xw) == 0:
                xw = xw + RNG.normal(0, 1e-9, 13)
            try:
                if stats.wilcoxon(xw, np.zeros(13), method="exact").pvalue < 0.05:
                    rej_w += 1
            except Exception:
                pass
            if stats.binomtest(int((xs > 0).sum()), 13, 0.5).pvalue < 0.05:
                rej_s += 1
        tag = "   <- calibration, want ~0.05" if delta == 0 else ""
        print(f"  {delta:>10.2f}{rej_w / N:17.2f}{rej_s / N:18.2f}{tag}")

    # --------------------------------------------------------------- how wide is one score?
    print("\n  HOW PRECISE IS A SINGLE ARM'S HEADLINE NUMBER? specimen bootstrap, 95% CI")
    for nm in named:
        v = sv[nm]
        bs = np.array([v[RNG.integers(0, 13, 13)].mean() for _ in range(BOOT)])
        print(f"    {nm:<26} {v.mean():.4f}  [{np.percentile(bs, 2.5):.4f}, "
              f"{np.percentile(bs, 97.5):.4f}]  width {np.percentile(bs, 97.5) - np.percentile(bs, 2.5):.4f}")

    # --------------------------------------------------------------- influence
    dd = cur - sv["oneline_mad (LOSO)"]
    print("\n  LEAVE-ONE-SPECIMEN-OUT INFLUENCE on CURRENT minus oneline_mad "
          f"(full-corpus value {dd.mean():+.4f})")
    for i, sp in enumerate(specs):
        keep = np.delete(dd, i)
        print(f"    drop {sp:<20} -> {keep.mean():+.4f}")

    json.dump(dict(per_specimen={k: v.tolist() for k, v in sv.items()},
                   specimens=specs, tests=out, sd_spec=sd_spec),
              open(os.path.join(L.WORK, "q3_power.json"), "w"), indent=1)
    print("\nwrote", os.path.join(L.WORK, "q3_power.json"))


if __name__ == "__main__":
    main()
