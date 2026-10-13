"""Score the LOSO probability stacks on clDice, against the reference arms.

Threshold selection is NESTED: for the tiles of specimen s the operating point is the one
that maximises the clDice of the held-out predictions of every OTHER specimen. No tile's
threshold ever saw its own score. `train-on-all` picks one threshold on everything and is
reported only so the overfit gap can be read.

Two deliverables are scored for every loss:
    standalone   (prob >= tau)                   -- a replacement; can delete, so gated
    additive     current_mask | (prob >= tau)    -- a strict superset of what ships, so
                 it cannot delete a hand-marked pixel and the paint gate is 0 by
                 construction (asserted on the real frames in scl_gate.py)

    python -B scl_score.py --tag main --losses dice,cldice,thin4,thin8 --save score.json
"""
import os, sys, json, argparse, warnings
warnings.filterwarnings("ignore")
import numpy as np

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True
import scl_cldice as C   # noqa: E402
import tilebench as TB   # noqa: E402

OUT = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/scl")
TAUS = [round(x, 2) for x in np.arange(0.05, 0.96, 0.05)]


def refs(tiles, gs):
    z = np.load(os.path.join(OUT, "ref_masks.npz"))
    cur, thr = z["cur"].astype(bool), z["thr"].astype(bool)
    rows = {"CURRENT MODEL (v1.49.1)": [C.cl_counts(m, t["gt"], g) for m, t, g in zip(cur, tiles, gs)],
            "one-line global threshold": [C.cl_counts(m, t["gt"], g) for m, t, g in zip(thr, tiles, gs)]}
    return cur, thr, rows


def counts_grid(P, tiles, gs, base=None, post=None):
    g = {}
    for tau in TAUS:
        rows = []
        for i, (t, s) in enumerate(zip(tiles, gs)):
            m = P[i] >= tau
            if post is not None:
                m = post(m)
            if base is not None:
                m = m | base[i]
            rows.append(C.cl_counts(m, t["gt"], s))
        g[tau] = rows
    return g


def nested(grid, tiles, specs, crit="cldice"):
    idx = {s: [i for i, t in enumerate(tiles) if t["specimen"] == s] for s in specs}
    held = [None] * len(tiles)
    picks = {}
    for s in specs:
        other = [i for sp in specs if sp != s for i in idx[sp]]
        tau = max(grid, key=lambda tt: C.agg([grid[tt][i] for i in other])[crit])
        picks[s] = tau
        for i in idx[s]:
            held[i] = grid[tau][i]
    allidx = [i for s in specs for i in idx[s]]
    tau_all = max(grid, key=lambda tt: C.agg([grid[tt][i] for i in allidx])[crit])
    held = [h for h in held if h is not None]
    return C.agg(held), C.agg([grid[tau_all][i] for i in allidx]), picks, tau_all, held


def line(lab, m, extra=""):
    print(f"  {lab:<36}{m['precision']:8.4f}{m['recall']:8.4f}{m['f1']:8.4f}"
          f"{m['iou']:8.4f}{m['cldice']:9.4f}{m['cldice_mean']:9.4f}{m['cldice_pooled']:10.4f}  {extra}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="main")
    ap.add_argument("--losses", default="dice,cldice,thin4,thin8")
    ap.add_argument("--specimens", default="")
    ap.add_argument("--save", default="")
    ap.add_argument("--quiet-paired", action="store_true")
    a = ap.parse_args()

    tiles_all = TB.load()
    gs_all = [C.skel(t["gt"]) for t in tiles_all]
    cur, thr, ref_rows_all = refs(tiles_all, gs_all)
    specs = sorted({t["specimen"] for t in tiles_all})
    if a.specimens:
        specs = [s for s in specs if s in a.specimens.split(",")]
    keep = [i for i, t in enumerate(tiles_all) if t["specimen"] in specs]
    tiles = [tiles_all[i] for i in keep]; gs = [gs_all[i] for i in keep]
    curK = cur[keep]
    ref_rows = {k: [v[i] for i in keep] for k, v in ref_rows_all.items()}

    print(f"\ntag '{a.tag}' on {len(tiles)} tiles / {len(specs)} specimens")
    print(f"  {'arm':<36}{'prec':>8}{'recall':>8}{'F1':>8}{'IoU':>8}{'clDice':>9}"
          f"{'(mean)':>9}{'(pooled)':>10}")
    for k, v in ref_rows.items():
        line(k, C.agg(v))
    out = {"reference": {k: C.agg(v) for k, v in ref_rows.items()},
           "per_spec_ref": {k: C.per_specimen(v, tiles) for k, v in ref_rows.items()}}

    for kind in a.losses.split(","):
        f = os.path.join(OUT, f"prob_{a.tag}_{kind}.npy")
        if not os.path.exists(f):
            print(f"  (missing {os.path.basename(f)})")
            continue
        P = np.load(f)[keep]
        for mode, base in [("standalone", None), ("additive", curK)]:
            grid = counts_grid(P, tiles, gs, base)
            ho, tr, picks, tau_all, held = nested(grid, tiles, specs)
            line(f"{kind} {mode}", ho, f"taus {sorted(set(picks.values()))}")
            line(f"   {kind} {mode} train-on-all", tr,
                 f"tau {tau_all}  gap {tr['cldice']-ho['cldice']:+.4f}")
            ps = C.per_specimen(held, tiles)
            key = f"{kind}|{mode}"
            out[key] = dict(heldout=ho, train_on_all=tr, gap=tr["cldice"] - ho["cldice"],
                            taus={k: float(v) for k, v in picks.items()}, per_spec=ps,
                            per_tile_cld=[h["cld"] for h in held])
            for rn, rv in ref_rows.items():
                pr = C.paired(ps, C.per_specimen(rv, tiles), key, rn)
                out[key][f"paired_vs::{rn}"] = pr
                if not a.quiet_paired:
                    print(f"      vs {rn:<30} median {pr['median_delta']:+.4f}  "
                          f"{pr['improved']} up / {pr['regressed']} down  "
                          f"wilcoxon p={pr['wilcoxon_p']:.4f}  sign p={pr['sign_p']:.4f}")
    if a.save:
        json.dump(out, open(os.path.join(OUT, a.save), "w"), indent=1, default=float)
        print(f"  saved {a.save}")


if __name__ == "__main__":
    main()
