"""Q6 -- IS THE VERDICT AN ARTEFACT OF MY OWN CHOICES? and HOW BIG A CORPUS WOULD IT TAKE?

Three choices were made in Q3 that a reader is entitled to distrust:
  * clDice is aggregated per tile and then averaged within a specimen. Pooling the
    skeleton COUNTS within a specimen instead weights a tile by how much crack it holds.
  * the degenerate guard (a mask covering >25% of the tile scores 0) is inherited from the
    project's existing implementation.
  * MAR_AmbB_AS is excluded, as tilebench does by default.
Each is flipped here. If the tie verdict moves, it was mine, not the data's.

Then the question that follows from the power analysis: if 13 specimens cannot resolve the
margins this workflow cares about, how many would?
"""
import os, sys, json
import numpy as np
from scipy import ndimage as ndi, stats
from skimage import filters
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import approach4_lib as L
import approach4_q3_power as Q3
import tilebench as TB
import detect_cracks as D

RNG = np.random.default_rng(99)


def arms_for(tiles):
    cur = [L.score_tile(t["arms"]["current"], t["gt"], sgt=t["skel_gt"]) for t in tiles]
    fam = {}
    for mk in Q3.MAD_GRID:
        masks = []
        for t in tiles:
            sm = filters.gaussian(t["flat40"], sigma=1, preserve_range=True)
            med = np.median(sm); mad = np.median(np.abs(sm - med)) * 1.4826
            masks.append(Q3.region40((sm < min(filters.threshold_otsu(sm), med - mk * mad))
                                     | (t["img8"] < L.ABSOLUTE_DARK)))
        fam["mad_%.1f" % mk] = [L.score_tile(m, t["gt"], sgt=t["skel_gt"])
                                for m, t in zip(masks, tiles)]
    held, _, _ = L.loso_pick(tiles, fam, list(fam))
    return cur, held


def spec_scores(tiles, rows, how):
    specs = sorted({t["specimen"] for t in tiles})
    out = []
    for sp in specs:
        idx = [i for i, t in enumerate(tiles) if t["specimen"] == sp]
        if how == "mean":
            out.append(float(np.mean([rows[i]["cldice"] for i in idx])))
        else:   # pooled skeleton counts within the specimen
            tp = sum(rows[i]["hit_skel_pred"] for i in idx) / max(
                sum(rows[i]["n_skel_pred"] for i in idx), 1)
            ts = sum(rows[i]["hit_skel_gt"] for i in idx) / max(
                sum(rows[i]["n_skel_gt"] for i in idx), 1)
            out.append(float(2 * tp * ts / max(tp + ts, 1e-12)))
    return specs, np.array(out)


def verdict(a, b, tag):
    d = a - b
    try:
        p = stats.wilcoxon(a, b, zero_method="wilcox", method="exact").pvalue
    except Exception:
        p = float("nan")
    bs = np.array([d[RNG.integers(0, len(d), len(d))].mean() for _ in range(20000)])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print(f"  {tag:<46} {d.mean():+.4f}  CI [{lo:+.4f},{hi:+.4f}]  "
          f"{int((d > 0).sum())}/{int((d < 0).sum())}  p {p:.4f}"
          f"{'   DISTINGUISHABLE' if p < 0.05 else '   tie'}")
    return dict(mean=float(d.mean()), ci=[float(lo), float(hi)], p=float(p))


def main():
    out = {}
    print("ROBUSTNESS OF THE TIE VERDICT (CURRENT MODEL minus the LOSO threshold, clDice)")
    tiles = L.tiles_with_arms()
    cur, thr = arms_for(tiles)
    _, a = spec_scores(tiles, cur, "mean"); _, b = spec_scores(tiles, thr, "mean")
    out["baseline, per-tile mean"] = verdict(a, b, "as reported (per-tile mean within specimen)")
    _, a2 = spec_scores(tiles, cur, "pooled"); _, b2 = spec_scores(tiles, thr, "pooled")
    out["pooled within specimen"] = verdict(a2, b2, "pooled skeleton counts within specimen")

    # no degenerate guard
    def nog(rows):
        v = []
        for r in rows:
            tp, ts = r["tprec"], r["tsens"]
            v.append(2 * tp * ts / max(tp + ts, 1e-12))
        return v
    cg = [dict(r, cldice=c) for r, c in zip(cur, nog(cur))]
    tg = [dict(r, cldice=c) for r, c in zip(thr, nog(thr))]
    _, a3 = spec_scores(tiles, cg, "mean"); _, b3 = spec_scores(tiles, tg, "mean")
    out["no 25% guard"] = verdict(a3, b3, "clDice without the >25%-of-tile guard")

    # MAR_AmbB_AS back in
    tiles2 = L.tiles_with_arms()
    try:
        all_tiles = TB.load(exclude=(), with_raw=True)
        extra = [t for t in all_tiles if t["specimen"] == "MAR_AmbB_AS"]
        print(f"  (MAR_AmbB_AS contributes {len(extra)} further tiles; re-running with them in)")
        import approach4_lib as LL
        # rebuild the per-tile cache entries for the excluded specimen if absent
        miss = [t for t in extra
                if not os.path.exists(os.path.join(L.WORK, "t_" + t["frame"] + ".npz"))]
        for t in miss:
            st = L.current_stages(t["img8"])
            np.savez_compressed(os.path.join(L.WORK, "t_" + t["frame"] + ".npz"),
                                gt=t["gt"], pred_current=st["pred"], dark=st["dark"],
                                clean=st["clean"], labeled=st["labeled"].astype(np.int32),
                                fz=L.fz_s1(t["img8"]), flat40=st["flat40"], img8=t["img8"],
                                **{"rung_%s" % k: v for k, v in st["rungs"].items()})
        tilesA = []
        for t in all_tiles:
            z = np.load(os.path.join(L.WORK, "t_" + t["frame"] + ".npz"))
            gt = z["gt"].astype(bool)
            d = dict(t); d.update(gt=gt, skel_gt=L.skel(gt), fz=z["fz"],
                                  flat40=z["flat40"],
                                  arms={"current": z["pred_current"].astype(bool)})
            tilesA.append(d)
        curA, thrA = arms_for(tilesA)
        _, a4 = spec_scores(tilesA, curA, "mean"); _, b4 = spec_scores(tilesA, thrA, "mean")
        out["MAR_AmbB_AS included"] = verdict(a4, b4, "with MAR_AmbB_AS back in (n=14)")
    except Exception as e:
        print("  (could not re-include MAR_AmbB_AS:", e, ")")

    # ---------------------------------------------------------------- sample size
    print("\nHOW MANY SPECIMENS WOULD IT TAKE? paired t, alpha 0.05, power 0.80")
    sd_spec = float(np.std(a, ddof=1))
    print(f"  between-specimen sd of clDice = {sd_spec:.4f}")
    print(f"  {'wanted gain':>12}" + "".join(f"{('r=%.2f' % r):>10}" for r in (0.99, 0.95, 0.90, 0.80)))
    for delta in (0.01, 0.02, 0.03, 0.05, 0.10):
        line = f"  {delta:>12.2f}"
        for r in (0.99, 0.95, 0.90, 0.80):
            sdd = sd_spec * np.sqrt(2 * (1 - r))
            n = 4
            while n < 100000:
                if Q3.mde(sdd, n=n) <= delta:
                    break
                n += 1
            line += f"{n:>10}"
        print(line)
    print("  (r is the correlation between the new method's per-specimen scores and the")
    print("   baseline's. A re-tuned constant sits near 0.97; a structurally different")
    print("   method measured today sits at 0.60-0.67.)")

    json.dump(out, open(os.path.join(L.WORK, "q6_robustness.json"), "w"), indent=1)
    print("\nwrote", os.path.join(L.WORK, "q6_robustness.json"))


if __name__ == "__main__":
    main()
