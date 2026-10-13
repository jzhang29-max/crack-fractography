"""Q2 -- WHERE DOES THE MISSING clDice GO? Decomposed on CENTRELINES, not on area.

clDice has exactly two halves and they fail for different reasons:

    Tsens = |skel(GT) & pred| / |skel(GT)|    LENGTH FOUND  -- the recall half
    Tprec = |skel(pred) & GT| / |skel(pred)|  LENGTH SPENT  -- the precision half

So the first thing to say about "the shipped model scores 0.64, it misses a third of the
crack's length" is whether that third is unfound length or misspent length. Then every
centreline pixel the model does not cover is attributed to the FIRST stage that dropped
it, exactly as recall_loss_decomposition.py does for area -- but on the skeleton, so a
single missed centreline pixel counts once however thickly the human painted around it.

Stages, in order (the classifier does not appear: v1.49.1 has it switched off):
    never dark      not below the cut at ANY of the 7 ladder radii, nor < absolute_dark
    clean_mask      dark, but erased by the disk(1) opening or the 13 px area floor
    region < 40     survived cleaning, but its component is too small to be featured

And the question the stage names cannot answer: is the missed length even VISIBLE? Each
centreline pixel carries fz, the robust z of the flattened image -- the exact statistic
the darkness cut thresholds. fz > -1 means the pixel is less than one robust sd darker
than this tile's own background, i.e. there is no intensity signal there to threshold at
any setting. That is the part of the loss no darkness-based method can ever recover.
"""
import os, sys, json
import numpy as np
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import approach4_lib as L
import detect_cracks as D

NOSIGNAL = -1.0          # fz above this = indistinguishable from this tile's background


def main():
    tiles = L.tiles_with_arms()
    onel = [k for k in tiles[0]["arms"] if k.startswith("oneline_")]
    sc = {k: [L.score_tile(t["arms"][k], t["gt"], sgt=t["skel_gt"]) for t in tiles] for k in onel}
    held_ol, picks_ol, _ = L.loso_pick(tiles, sc, onel)

    # ---------------------------------------------------------------- halves of clDice
    print("THE TWO HALVES OF clDice (per-tile mean, 26 tiles)")
    print(f"  {'arm':<28}{'Tsens (length found)':>22}{'Tprec (length spent)':>22}{'clDice':>9}")
    for nm, rows in [("CURRENT MODEL (v1.49.1)",
                      [L.score_tile(t["arms"]["current"], t["gt"], sgt=t["skel_gt"]) for t in tiles]),
                     ("one-line threshold (LOSO)", held_ol),
                     ("a correct 3 px trace",
                      [L.score_tile(t["arms"]["trace3"], t["gt"], sgt=t["skel_gt"]) for t in tiles])]:
        m = L.pool(rows)
        print(f"  {nm:<28}{m['tsens_mean']:22.4f}{m['tprec_mean']:22.4f}{m['cldice_mean']:9.4f}")

    # ---------------------------------------------------------------- stage attribution
    agg = dict(total=0, found=0, never_dark=0, lost_clean=0, lost_small=0)
    sig = {k: dict(n=0, nosignal=0) for k in ("found", "never_dark", "lost_clean", "lost_small")}
    fzvals = {k: [] for k in sig}
    per_spec = {}
    print("\nEVERY CENTRELINE PIXEL OF THE LABEL, BY THE STAGE THAT LOST IT (v1.49.1)")
    for t in tiles:
        sg = t["skel_gt"]
        dark = t["dark"]; clean = t["clean"]
        lab, _ = ndi.label(clean)
        sz = np.bincount(lab.ravel()); sz[0] = 0
        cand = sz[lab] >= L.FEATURE_MIN_AREA
        pred = t["arms"]["current"]
        fz = t["fz"]

        # Mutually exclusive and exhaustive. clean_mask CLOSES as well as opens, so it can
        # hand back a pixel the darkness cut never had; attributing on the raw stage masks
        # double-counts those. Attribute only what is actually missing at the end, to the
        # first stage that did not have it.
        found = sg & pred
        missed = sg & ~pred
        never = missed & ~dark & ~clean
        lclean = missed & dark & ~clean
        lsmall = missed & clean & ~cand
        buckets = dict(found=found, never_dark=never, lost_clean=lclean, lost_small=lsmall)
        n = int(sg.sum())
        agg["total"] += n
        for k, m in buckets.items():
            agg[k] += int(m.sum())
            v = fz[m]
            sig[k]["n"] += int(m.sum())
            sig[k]["nosignal"] += int((v > NOSIGNAL).sum())
            fzvals[k].append(v)
        s = per_spec.setdefault(t["specimen"], dict(total=0, **{k: 0 for k in buckets}))
        s["total"] += n
        for k, m in buckets.items():
            s[k] += int(m.sum())

    tot = agg["total"]
    print(f"  {'stage':<34}{'centreline px':>15}{'% of label length':>19}{'% of the loss':>15}")
    loss = tot - agg["found"]
    for k, lab_ in [("found", "reached the prediction"),
                    ("never_dark", "not dark at ANY ladder radius"),
                    ("lost_clean", "dark, erased by clean_mask"),
                    ("lost_small", "in clean mask, component < 40 px")]:
        pct_loss = "" if k == "found" else f"{100 * agg[k] / max(loss, 1):14.2f}%"
        print(f"  {lab_:<34}{agg[k]:>15,}{100 * agg[k] / tot:18.2f}%{pct_loss:>15}")
    print(f"  {'(sum check)':<34}{sum(agg[k] for k in ('found','never_dark','lost_clean','lost_small')):>15,}"
          f"{'':>19}   total {tot:,}")

    # ---------------------------------------------------------------- visibility
    print(f"\nIS THE MISSED LENGTH EVEN VISIBLE? fz > {NOSIGNAL} = no intensity signal at all")
    print(f"  {'stage':<34}{'median fz':>11}{'% with fz > -1':>17}{'% of label length':>19}")
    for k, lab_ in [("found", "reached the prediction"),
                    ("never_dark", "not dark at ANY ladder radius"),
                    ("lost_clean", "dark, erased by clean_mask"),
                    ("lost_small", "in clean mask, component < 40 px")]:
        v = np.concatenate(fzvals[k]) if fzvals[k] else np.array([0.0])
        v = v[np.isfinite(v)]
        print(f"  {lab_:<34}{np.median(v):11.2f}{100 * sig[k]['nosignal'] / max(sig[k]['n'], 1):16.1f}%"
              f"{100 * sig[k]['n'] / tot:18.2f}%")
    bg = np.concatenate([t["fz"][~t["gt"]][::97] for t in tiles])
    print(f"  {'background (unpainted pixels)':<34}{np.median(bg):11.2f}"
          f"{100 * (bg > NOSIGNAL).mean():16.1f}%")
    inv = sig["never_dark"]["nosignal"]
    print(f"\n  OF THE WHOLE LABEL CENTRELINE, {100 * inv / tot:.2f}% is both unproposed AND has")
    print(f"  no intensity signal ({inv:,} px). That is the floor on Tsens for any method that")
    print(f"  decides from intensity alone: Tsens <= {1 - inv / tot:.4f}, clDice <= "
          f"{2 * 1.0 * (1 - inv / tot) / (1 + (1 - inv / tot)):.4f} even with perfect precision.")

    # ---------------------------------------------------------------- can a cut reach it?
    print("\nCOULD A LOWER CUT REACH THE UNPROPOSED LENGTH? Tsens and Tprec vs the cut")
    print(f"  {'fz cut':>8}{'Tsens':>9}{'Tprec':>9}{'clDice':>9}{'% of tile marked':>19}")
    for c in (-0.5, -1.0, -1.5, -2.0, -2.5, -3.0, -4.0):
        rows = [L.score_tile(t["fz"] < c, t["gt"], sgt=t["skel_gt"]) for t in tiles]
        m = L.pool(rows)
        frac = np.mean([float((t["fz"] < c).mean()) for t in tiles])
        print(f"  {c:>8.1f}{m['tsens_mean']:9.4f}{m['tprec_mean']:9.4f}"
              f"{m['cldice_mean']:9.4f}{100 * frac:18.1f}%")

    # ---------------------------------------------------------------- per specimen
    print("\nPER SPECIMEN -- where the length is lost is NOT uniform")
    print(f"  {'specimen':<20}{'label len':>11}{'found':>9}{'never dark':>12}{'clean':>8}{'<40px':>8}")
    for sp in sorted(per_spec):
        s = per_spec[sp]
        print(f"  {sp:<20}{s['total']:>11,}{100 * s['found'] / s['total']:8.1f}%"
              f"{100 * s['never_dark'] / s['total']:11.1f}%"
              f"{100 * s['lost_clean'] / s['total']:7.1f}%{100 * s['lost_small'] / s['total']:7.1f}%")

    json.dump(dict(agg=agg, per_spec=per_spec,
                   nosignal={k: v for k, v in sig.items()}),
              open(os.path.join(L.WORK, "q2_centreline.json"), "w"), indent=1)
    print("\nwrote", os.path.join(L.WORK, "q2_centreline.json"))


if __name__ == "__main__":
    main()
