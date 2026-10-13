"""ANGLE 4, stage 1: what is a tile precision number worth, given how the tiles were made?

The quoted held-out precision 0.4153 treats every unmarked pixel in a 512 px tile as
verified not-crack. It is not. The labeller painted crack onto a BLANK mask, so an
unmarked pixel carries one bit of weak evidence (a human looked at this tile and did not
paint here) and zero bits of explicit verdict. Nothing was ever marked "not crack".

So 0.4153 is the PESSIMISTIC end of a bracket. This script measures the other end under
two defensible optimistic readings, and -- because any rule that excludes pixels near the
paint raises precision mechanically -- against decoys that must NOT show the same lift.

  PESSIMISTIC   unmarked = not-crack.                      P = tp / (tp + fp)
  OPT-ADJ(d)    an unmarked predicted pixel within d px of painted crack is UNKNOWN and
                leaves the denominator. Rationale: brush strokes have an edge, and the
                edge is where the painter's hand stopped, not where the crack stopped.
  OPT-CONT      an unmarked predicted pixel in a connected component that OVERLAPS painted
                crack is UNKNOWN. Rationale: the detector followed the same dark channel
                past the end of the stroke. Components with zero paint overlap stay FP.
  OPT-BOTH      union of the two.

DECOYS, run on identical machinery, because a bracket built from a dilation is only
evidence if a sham paint of the same size and shape does not produce it:
  SHAM-SHIFT    the tile's own gt translated by +128,+128 (wrapped). Same area, same
                stroke geometry, wrong place. OPT-ADJ/CONT computed against it.
  SHAM-ROT90    the tile's own gt rotated 90 degrees. Same area, same stroke geometry.
  The decoy answers "how much of the lift is the band's area alone?" Whatever the decoy
  reaches is the floor; only the excess over it is evidence about real crack.

Run:
    /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python -B \
        analysis/research/improve/angle4_tile_bracket.py
Writes nothing outside the scratchpad. Reads the paint read-only.
"""
import os, sys, json
import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import tilebench as TB                 # noqa: E402
import angle4_shipped as S             # noqa: E402

OUT = os.environ.get("A4OUT", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                              "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/angle4")
ST8 = np.ones((3, 3), bool)
DS = (1, 2, 4, 8, 16)


def brackets(pred, gt):
    """tp, and the fp that survives each reading. tp never changes -- only the denominator
    loses pixels, so every optimistic reading is an upper bound on the same tp."""
    tp = int((pred & gt).sum())
    fp = pred & ~gt
    out = {"tp": tp, "fp_pess": int(fp.sum())}
    for d in DS:
        band = ndi.binary_dilation(gt, ST8, iterations=d)
        out[f"fp_adj{d}"] = int((fp & ~band).sum())
    lab, n = ndi.label(pred, structure=ST8)
    if n:
        touch = np.zeros(n + 1, bool)
        hit = np.unique(lab[gt])
        touch[hit[hit > 0]] = True
        cont = touch[lab] & pred
    else:
        cont = np.zeros_like(pred)
    out["fp_cont"] = int((fp & ~cont).sum())
    for d in DS:
        band = ndi.binary_dilation(gt, ST8, iterations=d)
        out[f"fp_both{d}"] = int((fp & ~band & ~cont).sum())
    out["fp_ncomp"] = n
    out["fp_ncomp_touch"] = int(touch.sum()) if n else 0
    return out


def P(tp, fp):
    return tp / max(tp + fp, 1)


def main():
    tiles = TB.load()
    print("INSTRUMENT CONTROL")
    S.selfcheck([t["img8"] for t in tiles[:4]])
    print("  tilebench controls:")
    assert TB.controls()

    rows = []
    for t in tiles:
        pred = S.shipped_clean(t["img8"], min_area=15)
        gt = t["gt"]
        r = dict(frame=t["frame"], specimen=t["specimen"], gtpx=int(gt.sum()),
                 predpx=int(pred.sum()), real=brackets(pred, gt))
        # decoys: same stroke geometry, wrong location
        r["sham_shift"] = brackets(pred, np.roll(gt, (128, 128), (0, 1)))
        r["sham_rot90"] = brackets(pred, np.rot90(gt))
        rows.append(r)
        print(f"  {t['frame'][:52]:<52} gt {int(gt.sum()):>7,} pred {int(pred.sum()):>7,} "
              f"tp {r['real']['tp']:>7,} fp {r['real']['fp_pess']:>7,}", flush=True)

    os.makedirs(OUT, exist_ok=True)
    json.dump(rows, open(os.path.join(OUT, "tile_bracket.json"), "w"), indent=1)

    def agg(arm, key):
        tp = sum(r[arm]["tp"] for r in rows)
        return P(tp, sum(r[arm][key] for r in rows))

    print("\n" + "=" * 78)
    print("TILE PRECISION BRACKET  (26 tiles, 13 specimens, shipped v1.49.1 mask)")
    print("=" * 78)
    print(f"  {'reading':<34} {'REAL paint':>12} {'sham-shift':>12} {'sham-rot90':>12}")
    keys = [("PESSIMISTIC (quoted today)", "fp_pess")]
    keys += [(f"OPT-ADJ  d={d} px", f"fp_adj{d}") for d in DS]
    keys += [("OPT-CONT (component touches)", "fp_cont")]
    keys += [(f"OPT-BOTH d={d} px", f"fp_both{d}") for d in DS]
    for lab, k in keys:
        print(f"  {lab:<34} {agg('real', k):12.4f} {agg('sham_shift', k):12.4f} "
              f"{agg('sham_rot90', k):12.4f}")

    tp = sum(r["real"]["tp"] for r in rows)
    fp = sum(r["real"]["fp_pess"] for r in rows)
    print(f"\n  pooled tp {tp:,}   fp {fp:,}")
    print(f"  fp mass removed by OPT-CONT: {fp - sum(r['real']['fp_cont'] for r in rows):,}"
          f"  ({100*(fp-sum(r['real']['fp_cont'] for r in rows))/max(fp,1):.1f}%)")
    print(f"  fp mass removed by OPT-ADJ d=2: "
          f"{fp - sum(r['real']['fp_adj2'] for r in rows):,}"
          f"  ({100*(fp-sum(r['real']['fp_adj2'] for r in rows))/max(fp,1):.1f}%)")

    # where the fp lives: one tile owns most of it, and that matters for the bracket
    print("\n  FP concentration (pessimistic fp per tile, top 5):")
    for r in sorted(rows, key=lambda r: -r["real"]["fp_pess"])[:5]:
        print(f"    {r['frame'][:56]:<56} {r['real']['fp_pess']:>9,} "
              f"({100*r['real']['fp_pess']/max(fp,1):5.1f}% of all FP)")

    # the same bracket with the known off-specimen void tile removed
    sub = [r for r in rows if r["frame"] != TB.FLOODED]
    print(f"\n  WITHOUT the off-specimen void tile ({len(sub)} tiles):")
    for lab, k in keys[:1] + [(f"OPT-ADJ  d=2 px", "fp_adj2"), ("OPT-CONT", "fp_cont"),
                              ("OPT-BOTH d=2 px", "fp_both2")]:
        tps = sum(r["real"]["tp"] for r in sub)
        print(f"    {lab:<32} {P(tps, sum(r['real'][k] for r in sub)):.4f}")


if __name__ == "__main__":
    main()
