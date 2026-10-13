"""Tables for fullframe_recall_recovery.py. Reads its json, prints, writes nothing.

Two things here are not just sums of the json:

  * ENRICHMENT IS PER FRAME. An arm's newly proposed area is judged against the painted
    crack prevalence OF THAT FRAME, and the per-frame ratios are reported as a median with
    a range, never pooled. Pooled, relaxing mad_k looks 4.08x enriched; per frame it is
    1.5-1.7x on the two frames that hold 46% of the loss, because half of each of those
    frames is painted. The pooled figure is a Simpson effect.

  * A LOWER BOUND ON HOW MUCH OF THE NEVER-PROPOSED PAINT IS REAL SIGNAL, with no
    crack-like reference distribution needed. If the never-proposed painted pixels are a
    mixture pi*(crack) + (1-pi)*(local matrix), then for ANY threshold tau on img8

        P_lost(img8 < tau) = pi*P_crack(<tau) + (1-pi)*P_matrix(<tau)  and  P_crack <= 1
        =>  pi >= [P_lost(<tau) - P_matrix(<tau)] / [1 - P_matrix(<tau)]

    which is computable from two measured distributions alone. The bound is reported as
    its maximum over tau, with two controls on the estimator itself: run against the
    PROPOSED painted crack it must come out large, and run with distant matrix in place of
    the paint it must come out at ~0. An estimator that cannot reproduce those two is not
    measuring a mixture.

img8 is the instrument, not the flattened robust z, because flattening is a high-pass
filter and the detector's own docstring says a crack wider than the blur radius is removed
by it -- so a genuine wide-open crack sits at z ~ 0 exactly where matrix does, and the z
comparison cannot be read. img8 is the percentile-stretched image the absolute darkness
test reads, where an open crack is dark however wide it is.
"""
import os, sys, json
from collections import defaultdict
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fullframe_recall_decomposition as RD
import fullframe_recall_recovery as RC

J = os.environ.get("IN", RC.MY + "/work/recall_recovery.json")
ARMS = RC.ARM_ORDER
LAB = {"ship": "shipped (mad_k 5, img8<10)", "abs20": "img8<20", "abs30": "img8<30",
       "abs50": "img8<50", "madk3": "mad_k 3.0",
       "float_": "float residual (NOT a superset)",
       "float_abs30": "float residual + img8<30 (NOT)",
       "float_union": "shipped | float residual",
       "float_union_abs30": "shipped | float | img8<30"}
POPS = ("crack_kept", "crack_lost", "notc", "erase", "near_matrix", "far_matrix")
PLAB = {"crack_kept": "painted crack, proposed", "crack_lost": "painted crack, NOT proposed",
        "notc": "hand-marked NOT-crack (2)", "erase": "hand-marked ERASE (3)",
        "near_matrix": f"unreviewed matrix <= {RC.NEAR_PX} px from paint",
        "far_matrix": f"unreviewed matrix > {RC.FAR_PX} px from paint"}


def hsum(recs, key, pop):
    acc = None; lo = hi = n = 0
    for r in recs:
        d = r.get(key, {}).get(pop)
        if not d:
            continue
        h = np.asarray(d["h"], np.int64)
        acc = h if acc is None else acc + h
        lo += d["lo"]; hi += d["hi"]; n += d["n"]
    return acc, lo, hi, n


def cdf(acc, lo, hi):
    """P(value < bin edge i), with the overflow buckets on the correct side."""
    tot = acc.sum() + lo + hi
    if tot == 0:
        return None, 0
    return (lo + np.concatenate([[0], np.cumsum(acc)])) / tot, tot


def qfrom(bins, acc, lo, hi, qs=(10, 25, 50, 75, 90)):
    c, tot = cdf(acc, lo, hi)
    if c is None:
        return {}
    out = {}
    for q in qs:
        i = int(np.searchsorted(c, q / 100.0, side="left"))
        out[q] = float(bins[min(i, len(bins) - 1)])
    return out


def mixture_bound_at(tgt, refs, tau):
    """[P_tgt(<tau) - P_ref(<tau)] / [1 - P_ref(<tau)] at ONE tau, against whichever
    reference is hardest (largest P_ref(<tau)) -- a lower bound on the fraction of tgt
    that cannot be explained as a draw from that reference.

    Evaluated at a FIXED, decision-relevant tau and not maximised over tau. Maximising is
    what the first version of this did and it is wrong: as tau rises the denominator goes
    to zero and the ratio explodes on any tail difference, so it reported 88% for the
    never-proposed paint AND 96% for distant matrix measured against near matrix -- a
    control that must read ~0. The two matrix populations really do differ in their
    saturated-bright tail (near-paint matrix has img8 p90 = 250 against 235 far away), so
    at high tau neither is a usable reference for the other and the estimator is reading
    that, not crack. At the dark thresholds the absolute test actually uses, the
    denominator is ~1, the controls come out at 0.0-7.1%, and the number is readable."""
    ct, _ = cdf(*tgt[:3])
    if ct is None:
        return 0.0
    i = min(int(tau), len(ct) - 1)
    vals = []
    for rf in refs:
        cr, _ = cdf(*rf[:3])
        if cr is None:
            continue
        pr = cr[i]
        vals.append((ct[i] - pr) / max(1.0 - pr, 1e-9))
    return float(max(min(vals), 0.0)) if vals else 0.0


def main():
    raw = json.load(open(J))
    recs = [r for r in raw if "error" not in r]
    spec = defaultdict(list)
    for r in recs:
        spec[r["specimen"]].append(r)
    TC = sum(r["crack"] for r in recs)
    TN = sum(r["notc"] for r in recs)
    TE = sum(r["erase"] for r in recs)
    TA = sum(r["px"] for r in recs)

    print("=" * 150)
    print(f"RECOVERY ARMS AT THE DARKNESS CUT -- {len(recs)} frames, "
          f"{TC:,} hand-painted crack px")
    print(f"ladder {RC.LADDER}   the superset arms {RC.SUPERSETS} are additive by "
          f"construction and asserted so per frame;\n{'':<17}the two raw float arms are "
          f"NOT, and their deletion of hand-painted crack is in the last column")
    print("=" * 150)

    print("\n1. WHAT EACH ARM DELIVERS, AND WHAT IT COSTS\n")
    print(f"   {'arm':<34} {'crack px':>13} {'% painted':>10} {'notc%':>7} {'erase%':>8} "
          f"{'cand area':>14} {'% of frame':>11} {'deletes painted':>16}")
    for a in ARMS:
        cr = sum(r["arms"][a]["crack"] for r in recs)
        nc = sum(r["arms"][a]["notc"] for r in recs)
        er = sum(r["arms"][a]["erase"] for r in recs)
        ca = sum(r["arms"][a]["cand"] for r in recs)
        dl = sum(r["arms"][a]["deletes_crack_vs_ship"] for r in recs)
        print(f"   {LAB[a]:<34} {cr:>13,} {100 * cr / max(TC, 1):9.2f}% "
              f"{100 * nc / max(TN, 1):6.2f}% {100 * er / max(TE, 1):7.2f}% "
              f"{ca:>14,} {100 * ca / max(TA, 1):10.2f}% {dl:>16,}")

    print("\n2. IS THE NEWLY PROPOSED AREA CRACK-ENRICHED?  PER FRAME, against that "
          "frame's own\n   painted prevalence. The pooled ratio is a Simpson effect and is "
          "shown only to be\n   dismissed.\n")
    print(f"   {'arm':<34} {'new area':>13} {'new crack':>12} {'pooled x':>9}   "
          f"per-frame enrichment over that frame's prevalence (n frames that moved)")
    for a in ARMS:
        if a == "ship":
            continue
        da = dc = 0
        rat = []
        for r in recs:
            if r["crack"] == 0:
                continue
            b, x = r["arms"]["ship"], r["arms"][a]
            d1, d2 = x["cand"] - b["cand"], x["crack"] - b["crack"]
            da += d1; dc += d2
            if d1 > 20000:            # ignore frames the arm barely touched
                rat.append((d2 / d1) / max(r["crack"] / r["px"], 1e-12))
        rat = np.array(sorted(rat))
        pooled = (dc / max(da, 1)) / max(TC / TA, 1e-12)
        q = (f"median x{np.median(rat):.2f}  p25 x{np.percentile(rat, 25):.2f}  "
             f"p75 x{np.percentile(rat, 75):.2f}  min x{rat.min():.2f}  "
             f"max x{rat.max():.2f}  (n={len(rat)})") if len(rat) else "no frame moved"
        print(f"   {LAB[a]:<34} {da:>13,} {dc:>12,} {pooled:8.2f}x   {q}")

    print("\n3. PER SPECIMEN -- painted crack proposed, % of that specimen's paint\n")
    print(f"   {'specimen':<24} {'n':>3} {'painted':>12} "
          + "".join(f"{a.rstrip('_'):>12}" for a in ARMS))
    for sp in sorted(spec, key=lambda s: -sum(r["crack"] for r in spec[s])):
        rs = spec[sp]
        c = max(sum(r["crack"] for r in rs), 1)
        print(f"   {sp:<24} {len(rs):>3} {c:>12,} "
              + "".join(f"{100 * sum(r['arms'][a]['crack'] for r in rs) / c:11.2f}%"
                        for a in ARMS))

    print("\n4. PER FRAME -- painted crack proposed, % of that frame's paint\n")
    print(f"   {'frame':<34} {'painted':>11} "
          + "".join(f"{a.rstrip('_'):>12}" for a in ARMS))
    for r in sorted(recs, key=lambda r: -r["crack"]):
        if r["crack"] == 0:
            continue
        c = r["crack"]
        print(f"   {r['frame']:<34} {c:>11,} "
              + "".join(f"{100 * r['arms'][a]['crack'] / c:11.2f}%" for a in ARMS))

    print("\n5. WHAT THE NEVER-PROPOSED PAINT LOOKS LIKE, on img8 -- the image the absolute")
    print("   darkness test reads, which (unlike the flattened robust z) is not blinded by")
    print("   flattening's high-pass and so can see a wide-open crack.\n")
    print(f"   {'population':<44} {'n px':>14}   img8 quantiles (p10/p25/p50/p75/p90), "
          f"0=black")
    H = {p: hsum(recs, "img8", p) for p in POPS}
    for p in POPS:
        acc, lo, hi, n = H[p]
        if acc is None:
            continue
        q = qfrom(RC.IB, acc, lo, hi)
        print(f"   {PLAB[p]:<44} {n:>14,}   "
              + "  ".join(f"{v:6.0f}" for v in q.values()))

    print("\n   fraction of each population at or below an img8 level "
          "(the absolute test's own axis):\n")
    lv = [10, 20, 30, 40, 50, 60, 80, 100]
    print(f"   {'population':<44} {'n px':>14} " + "".join(f"{'<' + str(t):>9}" for t in lv))
    for p in POPS:
        acc, lo, hi, n = H[p]
        if acc is None:
            continue
        c, tot = cdf(acc, lo, hi)
        print(f"   {PLAB[p]:<44} {n:>14,} "
              + "".join(f"{100 * c[t]:8.2f}%" for t in lv))

    print("\n6. THE BOUND. Lower bound on the fraction of a population that cannot be "
          "explained as a\n   draw from unreviewed matrix, from the img8 distributions "
          "alone, at each darkness\n   threshold -- against whichever of the two matrix "
          "references is HARDER at that tau.\n")
    MR = [H["near_matrix"], H["far_matrix"]]
    taus = [10, 20, 30, 40, 50, 60, 80, 100]
    rows = [("painted crack, NOT proposed  <-- the answer", H["crack_lost"]),
            ("  CONTROL painted crack, proposed (must be high)", H["crack_kept"]),
            ("  CONTROL hand-marked NOT-crack 2 (high: it is dark)", H["notc"]),
            ("  CONTROL distant matrix (must be ~0)", H["far_matrix"]),
            ("  CONTROL near matrix (must be exactly 0)", H["near_matrix"])]
    print(f"   {'population':<52} " + "".join(f"{'<' + str(t):>9}" for t in taus))
    for nm, t in rows:
        print(f"   {nm:<52} "
              + "".join(f"{100 * mixture_bound_at(t, MR, t2):8.2f}%" for t2 in taus))
    print("\n   Read it as: at least this much of the never-proposed paint is darker than "
          "matrix can\n   account for, so at MOST the complement is paint lying over "
          "genuine matrix. One-sided:\n   it needs no crack-like reference, so no "
          "crack-like reference can inflate it, which is\n   why no upper bound is "
          "quoted. Trust it only where the two matrix controls are near 0.")

    print("\n7. k_max on the two representations, for the same populations -- what the "
          "float arm\n   buys is entirely in the lower tail that clipping had removed.\n")
    for key, nm in (("kmax_u8", "shipped uint8 flattening"),
                    ("kmax_float", "unclipped float residual")):
        print(f"   {nm}:")
        print(f"   {'population':<44} {'n px':>14} "
              + "".join(f"{'k>' + str(k):>9}" for k in (5.0, 3.0, 2.0, 1.0)))
        for p in POPS:
            acc, lo, hi, n = hsum(recs, key, p)
            if acc is None:
                continue
            c, tot = cdf(acc, lo, hi)
            out = []
            for k in (5.0, 3.0, 2.0, 1.0):
                i = int(np.searchsorted(RD.KB, k, side="right"))
                out.append(100 * (1.0 - c[min(i, len(c) - 1)]))
            print(f"   {PLAB[p]:<44} {n:>14,} " + "".join(f"{v:8.2f}%" for v in out))
        print()
    print("=" * 150)


if __name__ == "__main__":
    main()
