"""Does the cached harness reproduce the shipped detector's independently measured score?

If it does not, every comparison built on it is between two different instruments and the
differences mean nothing. This runs before any improvement is believed.
"""
import sys, numpy as np
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research")
sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP

tiles = TB.load()
print(f"running the shipped pipeline on {len(tiles)} cached tiles ...")
rows = []
for i, t in enumerate(tiles, 1):
    rows.append(TB.counts(CP.predict(t["img8"]), t["gt"]))
    print(f"  [{i:>2}/{len(tiles)}] {t['specimen'][:16]:<17} "
          f"tp {rows[-1]['tp']:>6,} fp {rows[-1]['fp']:>7,} fn {rows[-1]['fn']:>6,}", flush=True)
r = TB.evaluate("SHIPPED detector (mad_k=5.0, thr=0.5538)", {"shipped": rows})
got, want = r["loso"], TB.SHIPPED
bad = [k for k, v in want.items() if abs(got[k] - v) > 5e-4]
print(f"\n  reproduces the previously measured score: {'YES' if not bad else 'NO -- ' + str(bad)}")
for k, v in want.items():
    print(f"    {k:<10} harness {got[k]:.4f}   previously measured {v:.4f}   d {got[k]-v:+.5f}")
np.save("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
        "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/baseline_rows.npy",
        np.array([[x["tp"], x["fp"], x["fn"]] for x in rows]))
sys.exit(0 if not bad else 1)
