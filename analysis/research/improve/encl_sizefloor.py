"""Does a size floor separate off-specimen background from a crack that exits the frame?

enclosure.py's gate found one failure mode and it is structural: a crack that runs OUT
of the field of view is, by definition, not enclosed by specimen. On MAR_Amb_AS_ETD_0002
a single 123,653 px blob in the top-left corner -- 99.6% of it hand-marked crack, median
enclosure 6/16 against 16/16 for the crack that is kept -- is 86% of all the damage the
best arm does across 48 frames.

The obvious repair is a size floor: an off-specimen background flood is millions of
pixels, a crack mouth is hundreds of thousands. This sweeps that floor honestly, on the
same 48 frames and the same denominator as the gate, and reports what it costs as well
as what it buys. It is a NEW TUNED CONSTANT, so the overfit question is live and the
per-frame concentration is reported for every rung, not just the pooled number.
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import enclosure as E

FLOORS = (0, 50_000, 200_000, 500_000, 1_000_000, 2_000_000, 5_000_000)
ARMS = [("openbg8", 4), ("openbg8", 5), ("openbg16", 7), ("openbg16", 8),
        ("openbg16", 9), ("openbg16", 10)]


def main():
    names = [n for n in E.frame_names()
             if os.path.exists(os.path.join(E.CACHE, n + ".npz"))]
    out_path = os.path.join(E.MY, "work", "sizefloor.json")
    rows, t0 = [], time.time()
    for i, n in enumerate(names, 1):
        cand, corr = E.read_cache(n)
        crack, notc = corr == 1, (corr == 2) | (corr == 3)
        e8 = E.enclosure_counts(cand, (20,), dec=1)[20]
        e16 = E.enclosure_counts16(cand, (20,), dec=1)[20]
        r = dict(frame=n, arms={})
        r["arms"]["keepall"] = dict(area=int(cand.sum()), crack=int((cand & crack).sum()),
                                    notc=int((cand & notc).sum()))
        for fam, need in ARMS:
            e = e8 if fam == "openbg8" else e16
            for a in FLOORS:
                bg = E.open_background(cand, e, need, min_area=a)
                m = cand & ~bg
                r["arms"][f"{fam}_n{need}_A{a // 1000}k"] = dict(
                    area=int(m.sum()), crack=int((m & crack).sum()),
                    notc=int((m & notc).sum()))
        rows.append(r)
        json.dump(rows, open(out_path, "w"))
        print(f"[{i}/{len(names)}] {n:<36} {time.time() - t0:5.0f}s", flush=True)
    json.dump(rows, open(out_path, "w"))
    E.report(out_path)
    return out_path


if __name__ == "__main__":
    main()
