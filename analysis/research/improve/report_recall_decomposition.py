"""Tables for fullframe_recall_decomposition.py. Reads its json, prints, writes nothing.

Every table is given per frame and per specimen as well as pooled, because
MAR_Amb_AS_CBS_0003 holds 12.8M of the 70M hand-painted crack pixels: a pooled figure on
this corpus can be one frame. The bin edges are imported from the instrument rather than
restated, so a change to them cannot silently misread an old json.
"""
import os, sys, json
from collections import defaultdict
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fullframe_recall_decomposition as RD      # bin edges, ladder, constants

MY = RD.MY
J = os.environ.get("IN", MY + "/work/recall_decomp.json")
STAGES = ("kept", "notdark", "small13", "opening", "area40")
W = 160


def hsum(recs, path):
    """Add per-frame histograms. Returns (counts, lo, hi) with the overflow buckets kept
    separate so nothing is folded into an edge bin."""
    acc = None; lo = hi = n = 0
    for r in recs:
        d = r
        for k in path:
            d = d.get(k) if isinstance(d, dict) else None
            if d is None:
                break
        if d is None:
            continue
        h = np.asarray(d["h"], np.int64)
        acc = h if acc is None else acc + h
        lo += d["lo"]; hi += d["hi"]; n += d["n"]
    return acc, lo, hi, n


def pct_at(bins, acc, lo, hi, thresholds, above=True):
    """Fraction of a histogram's mass above (or below) each threshold, exactly, with the
    overflow buckets counted on the correct side."""
    tot = acc.sum() + lo + hi
    out = {}
    for t in thresholds:
        i = int(np.searchsorted(bins, t, side="left"))
        if above:
            m = acc[i:].sum() + hi
        else:
            m = acc[:i].sum() + lo
        out[t] = (int(m), float(m) / max(tot, 1))
    return out


def qfrom(bins, acc, lo, hi, qs=(10, 25, 50, 75, 90)):
    """Quantiles read off the summed histogram -- exact over all pixels, unlike the
    per-frame sampled quantiles the instrument also stores."""
    tot = acc.sum() + lo + hi
    if tot == 0:
        return {}
    c = np.concatenate([[lo], lo + np.cumsum(acc)])
    out = {}
    for q in qs:
        want = q / 100.0 * tot
        if want <= lo:
            out[q] = float("-inf"); continue
        if want > lo + acc.sum():
            out[q] = float("inf"); continue
        i = int(np.searchsorted(c, want, side="left"))
        out[q] = float(bins[min(max(i - 1, 0), len(bins) - 1)])
    return out


def line(ch="-"):
    print(ch * W)


def main():
    raw = json.load(open(J))
    recs = [r for r in raw if "error" not in r]
    bad = [r for r in raw if "error" in r]
    spec = defaultdict(list)
    for r in recs:
        spec[r["specimen"]].append(r)

    TC = sum(r["crack"] for r in recs)
    TN = sum(r["notc"] for r in recs)
    TE = sum(r["erase"] for r in recs)
    tot = {s: sum(r["decomp"]["crack"][s] for r in recs) for s in STAGES}

    line("=")
    print(f"CANDIDATE-STAGE RECALL DECOMPOSITION -- {len(recs)} frames"
          + (f" ({len(bad)} skipped: {[b['frame'] for b in bad]})" if bad else ""))
    print(f"ladder {RD.LADDER}   mad_k {RD.MAD_K}   absolute_dark {RD.ABS_DARK}   "
          f"clean min_area {RD.MIN_AREA_CLEAN}   candidate min_area {RD.MIN_AREA_CAND}")
    print(f"hand-painted: CRACK {TC:,} px   NOT-crack {TN:,} px   ERASE {TE:,} px")
    line("=")

    # ------------------------------------------------------------------ 1. the headline
    print("\n1. WHICH STAGE LOSES THE PAINTED CRACK  (pooled -- read section 2 before "
          "quoting it)\n")
    print(f"   {'stage':<44} {'px':>14} {'% of painted':>13}")
    for s in STAGES:
        lab = dict(kept="REACHES A CANDIDATE",
                   notdark="not dark at ANY ladder radius",
                   small13="dark, but component <= 13 px (clean_mask)",
                   opening="erased by clean_mask's opening, disk(1)",
                   area40="in the clean mask, component < 40 px")[s]
        print(f"   {lab:<44} {tot[s]:>14,} {100 * tot[s] / max(TC, 1):12.2f}%")
    print(f"   {'':<44} {'':>14} {'':>13}")
    print(f"   {'TOTAL (must equal painted crack)':<44} {sum(tot.values()):>14,} "
          f"{100 * sum(tot.values()) / max(TC, 1):12.2f}%")
    assert sum(tot.values()) == TC, "the partition does not close"
    miss = TC - tot["kept"]
    print(f"\n   never proposed: {miss:,} px = {100 * miss / max(TC, 1):.2f}% of painted "
          f"crack.  Of that loss, by stage:")
    for s in STAGES[1:]:
        print(f"     {s:<12} {100 * tot[s] / max(miss, 1):6.2f}%")

    # ------------------------------------------------- 2. concentration: is it one frame?
    print("\n2. CONCENTRATION -- how much of the corpus, and of the loss, is one frame\n")
    byf = sorted(recs, key=lambda r: -r["crack"])
    print(f"   {'frame':<36} {'painted':>12} {'% corpus':>9} {'missed':>12} "
          f"{'% of loss':>10} {'cum %':>8}")
    cum = 0.0
    top = byf[:min(8, len(byf))]
    for r in top:
        m = r["crack"] - r["decomp"]["crack"]["kept"]
        cum += 100 * m / max(miss, 1)
        print(f"   {r['frame']:<36} {r['crack']:>12,} {100 * r['crack'] / TC:8.2f}% "
              f"{m:>12,} {100 * m / max(miss, 1):9.2f}% {cum:7.2f}%")
    if len(byf) > len(top):
        print(f"   ... {len(byf) - len(top)} further frames hold the remaining "
              f"{100 - cum:.2f}% of the loss")

    # --------------------------------------------------------------- 3. per specimen
    print("\n3. PER SPECIMEN  (the unit that generalises -- tiles leak texture within one)\n")
    print(f"   {'specimen':<24} {'n':>3} {'painted':>12} {'kept':>12} {'kept%':>7} "
          + "".join(f"{s:>9}" for s in STAGES[1:]) + "   (% of painted)")
    for sp in sorted(spec, key=lambda s: -sum(r["crack"] for r in spec[s])):
        rs = spec[sp]
        c = sum(r["crack"] for r in rs)
        d = {s: sum(r["decomp"]["crack"][s] for r in rs) for s in STAGES}
        print(f"   {sp:<24} {len(rs):>3} {c:>12,} {d['kept']:>12,} "
              f"{100 * d['kept'] / max(c, 1):6.2f}%"
              + "".join(f"{100 * d[s] / max(c, 1):8.2f}%" for s in STAGES[1:]))

    # --------------------------------------------------------------- 4. per frame
    print("\n4. PER FRAME  (every frame, sorted by how much painted crack it holds)\n")
    print(f"   {'frame':<36} {'painted':>11} {'kept%':>7} {'notdark%':>9} "
          f"{'small13%':>9} {'open%':>7} {'area40%':>8} {'strokeW p50':>11}")
    for r in byf:
        c = max(r["crack"], 1)
        d = r["decomp"]["crack"]
        w = r.get("stroke", {}).get("width_q", {}).get("p50", float("nan"))
        print(f"   {r['frame']:<36} {r['crack']:>11,} {100 * d['kept'] / c:6.2f}% "
              f"{100 * d['notdark'] / c:8.2f}% {100 * d['small13'] / c:8.2f}% "
              f"{100 * d['opening'] / c:6.2f}% {100 * d['area40'] / c:7.2f}% {w:10.1f}")

    # --------------------------------------------------------- 5. the precision side
    print("\n5. THE SAME CHAIN ON THE HUMAN'S *NOT-CRACK* VERDICTS\n")
    print("   State 2 = 'not crack'; state 3 = 'erase from candidacy'. A pixel the "
          "candidate stage\n   PROPOSES here is a false positive the human has certified. "
          "A relaxation's cost is\n   measured against these, not against unreviewed "
          "matrix.\n")
    for nm, tt in (("notc", TN), ("erase", TE)):
        d = {s: sum(r["decomp"][nm][s] for r in recs) for s in STAGES}
        print(f"   {nm:<8} total {tt:>10,}   proposed {d['kept']:>10,} "
              f"({100 * d['kept'] / max(tt, 1):5.2f}%)   "
              + "  ".join(f"{s} {100 * d[s] / max(tt, 1):.2f}%" for s in STAGES[1:]))

    # --------------------------------------------------------- 6. per-rung contribution
    print("\n6. WHAT EACH LADDER RUNG CONTRIBUTES  (v1.49's union; 'only' = this rung and "
          "no other)\n")
    print(f"   {'sigma':>7} {'dark area':>14} {'painted crack':>14} "
          f"{'crack only here':>16} {'notc only':>10} {'erase only':>11} {'area only':>13}")
    for s in RD.LADDER:
        k = str(s)
        a = sum(r["rung_area"][k] for r in recs)
        cc = sum(r["rung_crack"][k]["crack"] for r in recs)
        co = sum(r["rung_crack"][k]["crack_only"] for r in recs)
        no = sum(r["rung_crack"][k]["notc_only"] for r in recs)
        eo = sum(r["rung_crack"][k]["erase_only"] for r in recs)
        ao = sum(r["rung_crack"][k]["area_only"] for r in recs)
        print(f"   {s:>7} {a:>14,} {cc:>14,} {co:>16,} {no:>10,} {eo:>11,} {ao:>13,}")
    ad = sum(r["absdark"] for r in recs)
    adc = sum(r["absdark_crack"] for r in recs)
    ado = sum(r["absdark_only_crack"] for r in recs)
    print(f"   {'abs<10':>7} {ad:>14,} {adc:>14,} {ado:>16,}")

    # --------------------------------------------- 7. recoverability: how far is the bar
    print("\n7. HOW MUCH IS RECOVERABLE AT THE DARKNESS CUT\n")
    print("   k_max(px) = max over rungs of (med-sm)/mad where sm < otsu. A pixel is dark "
          "at\n   threshold k iff k_max > k, exactly. The shipped bar is k = 5.0.\n")
    pops = [("crack_lost_notdark", "painted crack, never dark"),
            ("crack_kept", "painted crack that IS proposed"),
            ("notc_notdark", "hand-marked NOT-crack, not dark"),
            ("erase_notdark", "hand-marked ERASE, not dark"),
            ("unrev_notdark", "unreviewed matrix, not dark")]
    ks = [5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0, 0.0]
    print(f"   {'population':<34} {'n px':>13} " + "".join(f"{'k>' + str(k):>9}" for k in ks))
    for key, lab in pops:
        acc, lo, hi, n = hsum(recs, ("kmax", key))
        if acc is None:
            continue
        p = pct_at(RD.KB, acc, lo, hi, ks)
        print(f"   {lab:<34} {n:>13,} "
              + "".join(f"{100 * p[k][1]:8.2f}%" for k in ks))
    acc, lo, hi, n = hsum(recs, ("kmax", "crack_lost_notdark"))
    if acc is not None:
        print(f"\n   quantiles of k_max over the never-dark painted crack "
              f"(exact, all {n:,} px): "
              + "  ".join(f"p{q}={v:+.2f}" for q, v in qfrom(RD.KB, acc, lo, hi).items()))

    print("\n   AND WHAT RELAXING ACTUALLY DELIVERS -- the whole chain re-run, not the "
          "dark stage alone:\n")
    kk = sorted({k for r in recs for k in r["ksweep"]}, key=float, reverse=True)
    print(f"   {'mad_k':>7} {'cand area':>14} {'painted crack':>14} {'% painted':>10} "
          f"{'notc prop.':>11} {'% notc':>8} {'erase prop.':>12} {'% erase':>8} "
          f"{'unrev prop.':>12} {'% frame':>8}")
    TU = sum(r["unrev"] for r in recs)
    TA = sum(r["px"] for r in recs)
    for k in kk:
        ca = sum(r["ksweep"][k]["cand"] for r in recs)
        cr = sum(r["ksweep"][k]["crack"] for r in recs)
        nc = sum(r["ksweep"][k]["notc"] for r in recs)
        er = sum(r["ksweep"][k]["erase"] for r in recs)
        ur = sum(r["ksweep"][k]["unrev"] for r in recs)
        print(f"   {k:>7} {ca:>14,} {cr:>14,} {100 * cr / max(TC, 1):9.2f}% "
              f"{nc:>11,} {100 * nc / max(TN, 1):7.2f}% {er:>12,} "
              f"{100 * er / max(TE, 1):7.2f}% {ur:>12,} {100 * ur / max(TA, 1):7.2f}%")
    lost = {k: sum(r["ksweep"][k]["lost_vs_shipped"] for r in recs) for k in kk}
    print(f"\n   additive check -- candidate pixels the shipped k=5.0 keeps that a "
          f"relaxed k drops: "
          + ", ".join(f"k={k}: {lost[k]:,}" for k in kk))

    print("\n   per specimen, painted crack proposed (% of that specimen's paint):\n")
    print(f"   {'specimen':<24} {'painted':>12} " + "".join(f"{'k=' + k:>10}" for k in kk))
    for sp in sorted(spec, key=lambda s: -sum(r["crack"] for r in spec[s])):
        rs = spec[sp]
        c = max(sum(r["crack"] for r in rs), 1)
        print(f"   {sp:<24} {c:>12,} "
              + "".join(f"{100 * sum(r['ksweep'][k]['crack'] for r in rs) / c:9.2f}%"
                        for k in kk))

    # ------------------------------------------------------ 8. the broad-brush bound
    print("\n8. HOW MUCH OF THE LOSS IS BROAD-BRUSH PAINT RATHER THAN DETECTOR FAILURE\n")
    acc, lo, hi, n = hsum(recs, ("stroke", "width_h"))
    if acc is not None:
        q = qfrom(RD.WB, acc, lo, hi, (5, 25, 50, 75, 90, 95, 99))
        print("   8a. STROKE WIDTH, from the paint's own distance transform "
              "(2*EDT inside the paint):")
        print(f"       over all {n:,} painted crack px: "
              + "  ".join(f"p{k}={v:.0f}px" for k, v in q.items()))

    print("\n   8b. GEOMETRY -- did the detector hit the painted component at all?")
    pc = [r for r in recs if "paint_components" in r]
    nT = sum(r["paint_components"]["n"] for r in pc)
    nTT = sum(r["paint_components"]["n_touched"] for r in pc)
    aT = sum(r["paint_components"]["area_total"] for r in pc)
    aTT = sum(r["paint_components"]["area_touched"] for r in pc)
    lit = sum(r["paint_components"]["lost_in_touched"] for r in pc)
    liu = sum(r["paint_components"]["lost_in_untouched"] for r in pc)
    print(f"       {nT:,} painted components; {nTT:,} ({100 * nTT / max(nT, 1):.1f}%) "
          f"contain at least one candidate pixel")
    print(f"       area in a component the detector HIT:    {aTT:>14,} "
          f"({100 * aTT / max(aT, 1):5.2f}% of painted crack)")
    print(f"       of that, the part not itself proposed:    {lit:>14,} "
          f"({100 * lit / max(miss, 1):5.2f}% of the LOSS)   <- bounded by brush overshoot")
    print(f"       area in a component the detector MISSED:  {liu:>14,} "
          f"({100 * liu / max(miss, 1):5.2f}% of the LOSS)   <- genuinely unproposed objects")
    print("\n       by component size decade, because one component can be the whole "
          "main crack:")
    print(f"       {'area decade':>14} {'n':>8} {'n hit':>8} {'% n hit':>9} "
          f"{'painted px':>14} {'px proposed':>14} {'% px':>7} {'px in missed comp':>18}")
    dd = defaultdict(lambda: dict(n=0, nt=0, a=0, h=0, au=0))
    for r in pc:
        for k, v in r["paint_components"]["by_decade"].items():
            t = dd[int(k)]
            t["n"] += v["n"]; t["nt"] += v["n_touched"]; t["a"] += v["area"]
            t["h"] += v["hit"]; t["au"] += v["area_untouched"]
    for k in sorted(dd):
        t = dd[k]
        print(f"       {'10^' + str(k) + '..':>14} {t['n']:>8,} {t['nt']:>8,} "
              f"{100 * t['nt'] / max(t['n'], 1):8.1f}% {t['a']:>14,} {t['h']:>14,} "
              f"{100 * t['h'] / max(t['a'], 1):6.1f}% {t['au']:>18,}")

    print("\n   8c. DISTANCE from a missed painted pixel to the nearest candidate pixel.")
    print("       If the paint is a fat stroke over a crack the detector found, the missed")
    print("       pixels sit within half a stroke width of a candidate. Unreviewed matrix "
          "is the\n       no-relationship reference: it has the same access to the frame "
          "and no paint.\n")
    ds = [0.5, 2, 5, 10, 20, 30, 50, 100]
    print(f"       {'population':<34} {'n px':>14} "
          + "".join(f"{'<=' + str(d):>9}" for d in ds))
    for key, lab in (("crack_lost", "painted crack, not proposed"),
                     ("notc_lost", "hand-marked NOT-crack, not proposed"),
                     ("unrev", "unreviewed matrix, not proposed")):
        acc, lo, hi, n = hsum(recs, ("dist", key))
        if acc is None:
            continue
        p = pct_at(RD.DB, acc, lo, hi, [d + 1e-9 for d in ds], above=False)
        print(f"       {lab:<34} {n:>14,} "
              + "".join(f"{100 * p[d + 1e-9][1]:8.2f}%" for d in ds))

    print("\n   8d. APPEARANCE. Robust z on the sigma=40 flattened image (the quantity the")
    print("       shipped cut thresholds at -5.0) and Frangi vesselness. The only "
          "human-certified\n       matrix in the corpus is states 2 and 3, and a human "
          "only paints those where the\n       detector proposed something, so they are "
          "DARK-BIASED and therefore a conservative\n       comparator: painted crack "
          "lighter than them is very unlikely to be crack.\n")
    pops2 = [("crack_kept", "painted crack, proposed"),
             ("crack_lost", "painted crack, not proposed"),
             ("crack_lost_notdark", "painted crack, never dark at all"),
             ("notc", "hand-marked NOT-crack (state 2)"),
             ("erase", "hand-marked ERASE (state 3)"),
             ("unrev", "unreviewed matrix, not proposed")]
    print(f"       {'population':<36} {'n px':>14}   " + "robust z quantiles "
          "(p10/p25/p50/p75/p90)")
    for key, lab in pops2:
        acc, lo, hi, n = hsum(recs, ("z40", key))
        if acc is None:
            continue
        q = qfrom(RD.ZB, acc, lo, hi)
        print(f"       {lab:<36} {n:>14,}   "
              + "  ".join(f"{v:+7.2f}" for v in q.values()))
    print()
    print(f"       {'population':<36} {'n px':>14}   vesselness quantiles "
          "(p10/p25/p50/p75/p90)")
    for key, lab in pops2:
        acc, lo, hi, n = hsum(recs, ("ves", key))
        if acc is None:
            continue
        q = qfrom(RD.VB, acc, lo, hi)
        print(f"       {lab:<36} {n:>14,}   "
              + "  ".join(f"{v:9.2e}" for v in q.values()))
    line("=")


if __name__ == "__main__":
    main()
