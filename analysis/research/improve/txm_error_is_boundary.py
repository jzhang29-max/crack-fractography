#!/usr/bin/env python3
"""Is the TXM model's error a BOUNDARY error or a DETECTION error?

WHY THIS WAS ASKED. A reviewer looked at the over/under-counting plate and wrote, of
the transmission row, "i'm assuming this is our model -- if so how do we improve the
error?" Figure F5 already rules out one answer: both error classes sit at the crack's
OWN grey level (over-counted 0.33 against crack 0.22, under-counted 0.57 against crack
0.53, matrix 0.50 and 0.74), so neither is the model reacting to the wrong brightness.
That leaves two very different possibilities, and they have opposite remedies:

  BOUNDARY   the model finds the crack and disagrees about where its edge is. The
             error then hugs the agreed crack, and the fix is width calibration --
             nothing to do with finding anything new.
  DETECTION  the model misses whole cracks and invents whole objects somewhere else.
             The error is then scattered, and the fix is more or better features.

WHAT IS MEASURED. Per frame, the Euclidean distance from every over-counted and every
under-counted pixel to the nearest pixel both parties accept as crack, and the share of
each class within d px of it.

THE CONTROL, WITHOUT WHICH THE NUMBER MEANS NOTHING. "Most of the error is within 5 px
of the crack" is unimpressive if most of the FRAME is within 5 px of the crack -- on a
field dense with crack, every pixel is. So the same statistic is computed for a null
drawn from the refereed pixels that are NOT agreed crack, matched in count, frame by
frame. The error is a boundary effect only if it beats that null. Matching the count
per frame also stops a single large frame deciding a pooled answer.
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))
sys.dont_write_bytecode = True

import mk_counting as MC                                        # noqa: E402
import _paths                                                   # noqa: E402

BANDS = (1, 2, 3, 5, 10, 20, 50)


def shares(sel, dist, bands=BANDS):
    n = int(sel.sum())
    if not n:
        return None, 0
    d = dist[sel]
    return {f"within_{b}px": round(float((d <= b).mean()), 4) for b in bands}, n


def main():
    rng = np.random.default_rng(0)
    loaded, pre = MC.load_txm(MC.SPECIMEN["TXM"])
    ranked, rejected, best, masks = MC.score_candidates("TXM", loaded, pre)

    rows = []
    for frame, (img8, corr) in sorted(loaded.items()):
        mask = masks.get(frame)
        if mask is None:
            continue
        pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
        if pos.sum() < 200 or neg.sum() < 200:
            continue
        agree = mask & pos
        over, under = mask & neg, pos & ~mask
        if not agree.any():
            continue
        #: distance to the nearest AGREED crack pixel. EDT measures distance to the
        #: nearest ZERO, so the agreed mask is inverted going in.
        dist = ndi.distance_transform_edt(~agree)

        #: THE NULL. Refereed pixels that are not agreed crack, sampled to the same
        #: count as the class it stands in for, on this same frame.
        pool = np.flatnonzero((pos | neg).ravel() & ~agree.ravel())
        row = {"frame": frame, "agree_px": int(agree.sum())}
        for name, sel in (("over", over), ("under", under)):
            sh, n = shares(sel, dist)
            row[f"{name}_px"] = n
            row[name] = sh
            if n and pool.size:
                take = rng.choice(pool, size=min(n, pool.size), replace=False)
                nullsel = np.zeros(agree.size, bool)
                nullsel[take] = True
                row[f"{name}_null"] = shares(nullsel.reshape(agree.shape), dist)[0]
            else:
                row[f"{name}_null"] = None
        rows.append(row)

    if not rows:
        raise SystemExit("no TXM frame carried 200 px of each verdict")

    print(f"\n{len(rows)} TXM frames\n")
    hdr = "  ".join(f"{'<=' + str(b) + 'px':>8}" for b in BANDS)
    for name in ("over", "under"):
        got = [r for r in rows if r[name]]
        if not got:
            continue
        print(f"{name.upper()}-COUNTED  ({sum(r[name + '_px'] for r in got):,} px over "
              f"{len(got)} frames)")
        for tag, key in (("error", name), ("null ", name + "_null")):
            m = {b: float(np.mean([r[key][f"within_{b}px"] for r in got
                                   if r[key]])) for b in BANDS}
            print(f"  {tag}  " + "  ".join(f"{100 * m[b]:7.1f}%" for b in BANDS))
        e5 = float(np.mean([r[name]["within_5px"] for r in got]))
        n5 = float(np.mean([r[name + "_null"]["within_5px"] for r in got
                            if r[name + "_null"]]))
        print(f"  => within 5 px: error {100 * e5:.1f}% vs null {100 * n5:.1f}%"
              f"  ({e5 / n5:.2f}x)\n" if n5 else "\n")

    out = os.path.join(_paths.DOC_FIGURES, "txm_error_is_boundary.json")
    json.dump({"question": __doc__.strip().splitlines()[0],
               "bands_px": list(BANDS), "n_frames": len(rows),
               "null": "refereed pixels that are not agreed crack, count-matched per "
                       "frame, same distance transform",
               "frames": rows}, open(out, "w"), indent=1)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
