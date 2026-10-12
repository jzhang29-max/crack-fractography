"""LEVER 6 -- the dead zone (MAR_Amb_AS / MAR_Amb_Cast / MAR_Amb_HIP, recall 0.000).

WHAT THIS FILE FOUND, in one line: the dead zone is not an intensity-visibility problem,
it is a CLASSIFIER problem, and the shipped region classifier is net-harmful on every
specimen but two.

The brief said no darkness threshold will ever reach those three tiles. That is false.
At the SHIPPED mad_k=5.0 the candidate stage (segment_dark_regions -> clean_mask, before
the classifier) already captures

    MAR_Amb_AS    40.7% of marked crack for 0.1% of background
    MAR_Amb_Cast  40.1%                    for 0.0%
    MAR_Amb_HIP   68.3%                    for 0.3%

and the largest candidate region on each of those tiles sits 95-100% inside the human
paint. Every one of them is then thrown away by the logistic model, whose maximum
per-region probability on the three tiles is 0.414 / 0.353 / 0.519 against a threshold of
0.5538. The apparent "brighter than background" paradox is resolved by the pipeline's own
flat_sigma=40 background subtraction: the marked crack on these tiles is globally bright
and locally dark.

RESULTS (26 tiles, 13 specimens, everything scored through analysis/tilebench.py):

    method                                     P       R      IoU      F1    gap
    shipped detector (baseline)           0.3378  0.3696  0.2143  0.3530   0.0000
    candidates only, no classifier        0.4037  0.5402  0.3005  0.4621   0.0000   <- parameter-free
    + flatness veto relstd16 >= 1.0       0.8546  0.5394  0.4940  0.6613   0.0000   <- parameter-free
    + mad_k and floor LOSO-selected       0.7976  0.6269  0.5409  0.7020  +0.0070   <- best held-out

READ THE FLATNESS VETO WITH ITS CAVEAT. 96.2% of the pixels it removes are ONE region on
ONE tile (the off-specimen void on MAR_H_HIP_CBS_0002, 137,774 px). With that tile dropped
the veto is worth +0.011 IoU over candidates-only, which is still above a 200-draw
randomisation null (0.4946 vs 0.4766 +/- 0.0048) but is a small effect, not the headline.
The broad, many-specimen result is CANDIDATES-ONLY.

NEGATIVE RESULTS, kept here on purpose:
  * Texture IS a real signal on the dead tiles -- local_std(r=16) and phase congruency
    reach AUC 0.96-0.99 against a 12-shift null whose max is ~0.60 -- but it fires
    everywhere (AUC 0.87 mean on the other 23 tiles) and is useless as a detector:
    texture alone held-out IoU 0.2069; dark UNION texture 0.2959 (the LOSO selector picks
    "dark alone" in 12 of 13 folds); dark INTERSECT texture fitted 0.4584 / held-out
    0.2874, a +0.1710 overfit gap.
  * BRIGHT RIDGES ARE REFUTED. sato/frangi/meijering with black_ridges=False score AUC
    0.32-0.69 on the dead tiles, below 0.5 on MAR_Amb_HIP and below the dark polarity
    everywhere. The cracks are not bright ridges.
  * A retrained region classifier (random forest, fitted inside each LOSO fold) reaches
    held-out IoU 0.4759, but on the 25 tiles that are not the flooded one it scores 0.4774
    against candidates-only's 0.4837 -- i.e. it buys nothing except the flood veto, at the
    cost of needing training labels.

Run:  /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python -B lever6_deadzone.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from scipy import ndimage as ndi
import tilebench as TB
import crackpipe as CP
import detect_cracks as D

DEAD = ("MAR_Amb_AS", "MAR_Amb_Cast", "MAR_Amb_HIP")
FLOOD = "MAR_H_HIP_CBS_0002__crop_3122_120_512x512"


def local_std(a, r):
    a = np.asarray(a, np.float32)
    m = ndi.uniform_filter(a, 2 * r + 1)
    m2 = ndi.uniform_filter(a * a, 2 * r + 1)
    return np.sqrt(np.maximum(m2 - m * m, 0)).astype(np.float32)


def predict(img8, mad_k=5.0, veto_radius=16, relstd_floor=1.0):
    """Shipped candidate stage, NO classifier, plus the flatness veto.

    relstd_floor is a ratio, not a tuned intensity: a candidate region is kept only if its
    median local standard deviation is at least `relstd_floor` times the tile's own median
    local standard deviation, i.e. a crack must be at least as textured as the matrix it
    runs through. 1.0 is the natural boundary of that statement, not a fitted value.
    Pass relstd_floor=0.0 to get plain candidates-only.
    """
    st = CP.stages(img8, mad_k=mad_k)
    clean = st["clean"]
    if relstd_floor <= 0:
        return clean
    s = local_std(st["flat"], veto_radius)
    base = max(float(np.median(s)), 1e-6)
    lab, n = ndi.label(clean)
    keep = np.zeros(n + 1, bool)
    for i in range(1, n + 1):
        m = lab == i
        keep[i] = (np.median(s[m]) / base) >= relstd_floor
    return keep[lab]


def main():
    print("CONTROLS"); assert TB.controls(), "harness controls failed"
    tiles = TB.load()
    variants = {
        "0 shipped baseline":            [CP.predict(t["img8"]) for t in tiles],
        "1 candidates only":             [predict(t["img8"], 5.0, relstd_floor=0.0) for t in tiles],
        "2 + flatness veto (fixed)":     [predict(t["img8"], 5.0, 16, 1.0) for t in tiles],
    }
    for name, masks in variants.items():
        TB.evaluate(name + "  [parameter-free]", {name: [TB.counts(m, t["gt"]) for m, t in zip(masks, tiles)]})

    # the tuned arm: the WHOLE grid goes to TB.evaluate, which does the LOSO selection
    grid = {}
    for mk in (5.0, 4.0, 3.0, 2.5):
        for r in (8, 16):
            for fl in (0.0, 0.75, 1.0, 1.25, 1.5):
                masks = [predict(t["img8"], mk, r, fl) for t in tiles]
                grid[f"mad{mk}_r{r}_floor{fl}"] = [TB.counts(m, t["gt"]) for m, t in zip(masks, tiles)]
                print(f"  grid mad{mk} r{r} floor{fl}", flush=True)
    TB.evaluate("3 mad_k x veto grid  [2 free parameters, LOSO-selected]", grid)

    # the honesty block: per specimen, and with the flooded tile removed
    def agg(rows):
        tp = sum(r["tp"] for r in rows); fp = sum(r["fp"] for r in rows); fn = sum(r["fn"] for r in rows)
        p = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
        return p, rc, tp / max(tp + fp + fn, 1), 2 * p * rc / max(p + rc, 1e-12)

    print("\nPER-SPECIMEN IoU, and the same with the flooded tile dropped")
    cols = list(variants)
    cnt = {k: [TB.counts(m, t["gt"]) for m, t in zip(v, tiles)] for k, v in variants.items()}
    spec = {}
    for i, t in enumerate(tiles):
        spec.setdefault(t["specimen"], []).append(i)
    print(f'{"specimen":18s} ' + "".join(f"{c[:16]:>20s}" for c in cols))
    for sp, ii in sorted(spec.items()):
        tag = " (DEAD ZONE)" if sp in DEAD else ""
        print(f"{sp:18s} " + "".join(f"{agg([cnt[c][i] for i in ii])[2]:20.4f}" for c in cols) + tag)
    jf = [i for i, t in enumerate(tiles) if t["frame"] != FLOOD]
    print(f'{"POOLED 26":18s} ' + "".join(f"{agg(cnt[c])[2]:20.4f}" for c in cols))
    print(f'{"POOLED 25 no flood":18s} ' + "".join(f"{agg([cnt[c][i] for i in jf])[2]:20.4f}" for c in cols))


if __name__ == "__main__":
    main()
