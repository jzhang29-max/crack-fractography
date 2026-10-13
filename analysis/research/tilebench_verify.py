"""Does the cached harness reproduce the v1.47 detector's independently measured score?

If it does not, every comparison built on it is between two different instruments and the
differences mean nothing. This runs before any improvement is believed.

WHAT THIS DOES *NOT* CHECK, and the name used to say otherwise. `crackpipe.predict` is the
v1.47 pipeline -- region classifier ON at threshold 0.5538, one flattening radius -- and
that is NOT what ships. v1.49.1 switches the classifier off and unions the darkness cut
across seven radii. So this file is a HARNESS check (the cached tiles and the counting
agree with a figure measured elsewhere), not a check on the shipped detector. The shipped
detector's own score is TB.SHIPPED_V1491, reproduced by
analysis/research/improve/aggregation.py and verified against what the app emits by
analysis/research/improve/app_truth.py.
"""
import sys, numpy as np
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research")
sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP

tiles = TB.load()
print(f"running the v1.47 pipeline (classifier ON) on {len(tiles)} cached tiles ...")
rows = []
for i, t in enumerate(tiles, 1):
    rows.append(TB.counts(CP.predict(t["img8"]), t["gt"]))
    print(f"  [{i:>2}/{len(tiles)}] {t['specimen'][:16]:<17} "
          f"tp {rows[-1]['tp']:>6,} fp {rows[-1]['fp']:>7,} fn {rows[-1]['fn']:>6,}", flush=True)
r = TB.evaluate("v1.47 detector, classifier ON (mad_k=5.0, thr=0.5538)", {"v147": rows})
got, want = r["loso"], TB.V147_CLASSIFIER_ON
bad = [k for k, v in want.items() if abs(got[k] - v) > 5e-4]
print(f"\n  reproduces the previously measured score: {'YES' if not bad else 'NO -- ' + str(bad)}")
for k, v in want.items():
    print(f"    {k:<10} harness {got[k]:.4f}   previously measured {v:.4f}   d {got[k]-v:+.5f}")
np.save("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
        "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/baseline_rows.npy",
        np.array([[x["tp"], x["fp"], x["fn"]] for x in rows]))
sys.exit(0 if not bad else 1)
