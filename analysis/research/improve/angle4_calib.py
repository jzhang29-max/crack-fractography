"""ANGLE 4, round 2: calibrate the adjudicator, because round 1 could not.

Round 1's control arms were n=8 each and separated REFPOS from REFNEG at Fisher p=0.315.
An uncalibrated adjudicator cannot carry the UNREV estimate, so this round is CONTROLS
ONLY -- components the human refereed and called crack (state 1) against components the
human refereed and called not-crack (state 2/3) -- at a size that can actually answer it.

Pre-registered before any patch is rendered:
  * 40 patches, size-matched between the two arms by nearest log-area.
  * The split between the arms is drawn at random in [14, 26] from a seed, so the
    adjudicator cannot infer an expected rate from the pool composition. The split is
    written to the key, which is not read until calls2.json exists.
  * The statistic is Fisher's exact test on the call "b" (plausibly real crack) between
    the two arms. Calibration is established if it separates them; if it does not, the
    round 1 census is reported as uncalibrated, which is the honest outcome.
  * Nothing from round 1 is reused, and round 1's own numbers are not revised by this.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
OUT = os.environ.get("A4OUT", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                              "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/angle4")
os.environ.setdefault("MPLCONFIGDIR", OUT + "/mpl")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import numpy as np                                  # noqa: E402
from scipy import ndimage as ndi                    # noqa: E402
import angle4_shipped as S                          # noqa: E402
import angle4_fullframe as F                        # noqa: E402
from angle4_census import render, ST8               # noqa: E402

SEED = 777013
N = 40
PD = os.path.join(OUT, "patches2")


def build():
    rows = [r for r in json.load(open(os.path.join(OUT, "fullframe.json")))
            if "error" not in r]
    pool = [(r["frame"], c) for r in rows for c in r["comps"] if c["area"] >= 800]
    def ref(c):
        return c["c1"] + c["c2"] + c["c3"]
    rp = [p for p in pool if ref(p[1]) >= 200 and p[1]["c1"] >= 0.5 * ref(p[1])]
    rn = [p for p in pool if ref(p[1]) >= 200
          and (p[1]["c2"] + p[1]["c3"]) >= 0.5 * ref(p[1])]
    rng = np.random.default_rng(SEED)
    n_neg = int(rng.integers(14, 27))
    n_pos = N - n_neg
    neg = [rn[i] for i in rng.choice(len(rn), n_neg, replace=False)]
    # size-match the positives to the negatives by nearest log-area
    la = np.log(np.array([c[1]["area"] for c in rp], float))
    used, pos = set(), []
    for t in [c[1]["area"] for c in neg] * 3:
        if len(pos) >= n_pos:
            break
        for j in np.argsort(np.abs(la - np.log(t))):
            if j not in used:
                used.add(int(j)); pos.append(rp[int(j)]); break
    chosen = [("REFNEG", *p) for p in neg] + [("REFPOS", *p) for p in pos]
    os.makedirs(PD, exist_ok=True)
    ids = [f"q{i:03d}" for i in rng.permutation(len(chosen))]
    key, byframe = [], {}
    for (arm, frame, comp), rid in zip(chosen, ids):
        if frame not in byframe:
            img8 = F.load_frame(frame)[0]
            lab, _ = ndi.label(S.shipped_clean(img8, min_area=15), structure=ST8)
            byframe[frame] = (img8, lab)
            print(f"  loaded {frame}", flush=True)
        img8, lab = byframe[frame]
        render(img8, lab, comp, os.path.join(PD, rid + ".png"))
        key.append(dict(rid=rid, arm=arm, frame=frame, area=comp["area"],
                        c1=comp["c1"], c2=comp["c2"], c3=comp["c3"], c0=comp["c0"]))
    key.sort(key=lambda k: k["rid"])
    json.dump(key, open(os.path.join(OUT, "key2.json"), "w"), indent=1)
    print(f"\nwrote {len(key)} patches to {PD}.  Split withheld. "
          f"Do not read key2.json until calls2.json exists.")


def unblind():
    from scipy.stats import fisher_exact
    key = {k["rid"]: k for k in json.load(open(os.path.join(OUT, "key2.json")))}
    calls = json.load(open(os.path.join(OUT, "calls2.json")))
    from collections import Counter, defaultdict
    by = defaultdict(Counter)
    for rid, cl in calls.items():
        by[key[rid]["arm"]][cl] += 1
    print(f"{'arm':<8} {'n':>3}  " + "  ".join(f"{c:>8}" for c in "abcu"))
    for arm in ("REFPOS", "REFNEG"):
        c = by[arm]; n = sum(c.values())
        print(f"{arm:<8} {n:>3}  " + "  ".join(f"{c[x]:>2} {100*c[x]/max(n,1):4.0f}%"
                                               for x in "abcu"))
    t = [[by["REFPOS"]["b"], sum(by["REFPOS"].values()) - by["REFPOS"]["b"]],
         [by["REFNEG"]["b"], sum(by["REFNEG"].values()) - by["REFNEG"]["b"]]]
    p = fisher_exact(t, alternative="greater")[1]
    sens = by["REFPOS"]["b"] / max(sum(by["REFPOS"].values()), 1)
    fpr = by["REFNEG"]["b"] / max(sum(by["REFNEG"].values()), 1)
    print(f"\n  sensitivity (REFPOS called b) {sens:.3f}   "
          f"false-call rate (REFNEG called b) {fpr:.3f}")
    print(f"  Fisher one-sided p = {p:.4f}   "
          f"{'CALIBRATED' if p < 0.05 else 'NOT CALIBRATED -- the census is uncalibrated'}")
    json.dump(dict(table=t, sens=sens, fpr=fpr, p=p,
                   by={a: dict(by[a]) for a in by}),
              open(os.path.join(OUT, "calib.json"), "w"), indent=1)
    if p < 0.05 and sens > fpr:
        u = json.load(open(os.path.join(OUT, "census.json")))["UNREV"]
        n = sum(u.values()); obs = u.get("b", 0) / n
        corr = (obs - fpr) / max(sens - fpr, 1e-9)
        print(f"\n  round-1 UNREV observed b-rate {obs:.3f} -> calibration-corrected "
              f"true crack share {min(max(corr, 0.0), 1.0):.3f}"
              f"{'  (saturated at 1.0)' if corr > 1 else ''}")


if __name__ == "__main__":
    {"build": build, "unblind": unblind}[sys.argv[1]]()
