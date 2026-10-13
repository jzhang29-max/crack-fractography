"""Reproduce the brief's six-arm reference table before anything is built on the scorer.

If this does not land on the brief's numbers -- current clDice 0.6405, one-line threshold
0.6205, a correct 3 px trace 0.9984 -- then my scorer is not their scorer and no gain
measured against it is readable. Caches the reference masks for every later script.
"""
import os, sys, json, time, warnings
warnings.filterwarnings("ignore")
import numpy as np

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True
import scl_cldice as C  # noqa: E402
import tilebench as TB  # noqa: E402

OUT = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/scl")
os.makedirs(OUT, exist_ok=True)
BRIEF = {"CURRENT MODEL (v1.49.1)": (0.4182, 0.6252, 0.5012, 0.3344, 0.6405),
         "one-line global threshold": (0.4271, 0.6027, 0.4999, 0.3332, 0.6205),
         "a correct 3 px trace": (0.9754, 0.2505, 0.3987, 0.2490, 0.9984),
         "ridge filter (Frangi)": (0.2310, 0.2718, 0.2498, 0.1427, 0.3476),
         "random, area-matched": (0.0242, 0.0362, 0.0290, 0.0147, 0.0190),
         "mark everything": (0.0297, 1.0000, 0.0577, 0.0297, 0.0000)}


def main():
    tiles = TB.load()
    gs = [C.skel(t["gt"]) for t in tiles]
    print(f"{len(tiles)} tiles / {len({t['specimen'] for t in tiles})} specimens")
    assert C.controls(tiles, gs)
    rng = np.random.default_rng(0)
    masks, t0 = {}, time.time()
    for i, t in enumerate(tiles, 1):
        for k, v in C.arms(t, rng).items():
            masks.setdefault(k, []).append(v)
        print(f"  [{i:>2}/{len(tiles)}] {t['frame'][:44]}", flush=True)
    flats = np.stack(masks.pop("_flat")); sms = np.stack(masks.pop("_sm"))
    rows = {k: [C.cl_counts(m, t["gt"], g) for m, t, g in zip(v, tiles, gs)]
            for k, v in masks.items()}
    print(f"\n  {'arm':<28}{'prec':>8}{'recall':>8}{'F1':>8}{'IoU':>8}{'clDice':>9}"
          f"{'(mean)':>9}{'(pooled)':>10}   vs brief")
    for k in BRIEF:
        m = C.agg(rows[k]); b = BRIEF[k]
        got = (m["precision"], m["recall"], m["f1"], m["iou"], m["cldice"])
        d = max(abs(x - y) for x, y in zip(got, b))
        print(f"  {k:<28}" + "".join(f"{x:8.4f}" for x in got)
              + f"{m['cldice_mean']:9.4f}{m['cldice_pooled']:10.4f}   max|d| {d:.4f}"
              + ("  OK" if d < 0.005 else "  <-- MISMATCH"))
    np.savez_compressed(os.path.join(OUT, "ref_masks.npz"),
                        cur=np.stack(masks["CURRENT MODEL (v1.49.1)"]),
                        thr=np.stack(masks["one-line global threshold"]),
                        flat=flats.astype(np.float32), sm=sms.astype(np.float32))
    json.dump({k: v for k, v in rows.items()}, open(os.path.join(OUT, "baseline_rows.json"), "w"))
    a = C.per_specimen(rows["CURRENT MODEL (v1.49.1)"], tiles)
    b = C.per_specimen(rows["one-line global threshold"], tiles)
    print("\n  per-specimen clDice (median over the specimen's tiles)")
    for k in sorted(a):
        print(f"    {k:<22}{a[k]:8.4f}{b[k]:8.4f}{a[k]-b[k]:+9.4f}")
    pr = C.paired(a, b, "current", "threshold")
    print(f"  current vs threshold: median {pr['median_delta']:+.4f}  "
          f"{pr['improved']} up / {pr['regressed']} down  wilcoxon p={pr['wilcoxon_p']:.4f}")
    print(f"  {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
