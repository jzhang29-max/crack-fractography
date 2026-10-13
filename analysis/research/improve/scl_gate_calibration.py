"""What does the CORRECT ANSWER score on the full-frame paint gate?

The gate asks: of the hand-marked crack pixels the shipped path keeps, how many does the
candidate rule drop? That is a PIXEL-COVERAGE test, and the brief's own correct answer --
a 3 px trace down the centre of the human's paint -- covers almost none of a 192 px-wide
brush stroke. So before reading any centreline method's gate number as a failure, measure
what the gate says about an answer that is right by construction.

This is the gate's calibration, not a method. Two rows per frame:

    3 px trace of the paint   the brief's physically correct answer, drawn 3 px wide
    9 px trace of the paint   the width the thin4 target is trained to produce

If these delete ~the same fraction as the net does, the gate is not telling us the net
failed to find the crack; it is telling us the net drew it thinner than the brush, which
is what it was asked to do. Either way the conclusion for production is the same -- only
an ADDITIVE form is admissible -- but the reason matters for what to build next.

    python -B scl_gate_calibration.py --frames 8
"""
import os, sys, json, time, argparse, warnings
warnings.filterwarnings("ignore")
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True
import scl_gate as G    # noqa: E402
import scl_cldice as C  # noqa: E402

OUT = G.OUT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--save", default="gate_calibration.json")
    a = ap.parse_args()
    names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(G.PAINT)
                   if f.endswith("_correction_mask.png"))
    names = [n for n in names if os.path.exists(
        os.path.join(G.SEM if hasattr(G, "SEM") else
                     "/Users/jiamingzhang/Desktop/APP/sem-crack-detector", "original", n + ".tif"))]
    names = names[:a.frames]
    st = ndi.generate_binary_structure(2, 2)
    rows, t0 = [], time.time()
    print(f"{len(names)} frames | gate calibration: what a CORRECT thin answer deletes")
    for i, n in enumerate(names, 1):
        got = G.load_frame(n)
        if got is None:
            continue
        img8, corr = got
        crack = corr == 1
        shipped = G.shipped_clean(img8)
        kept = int((shipped & crack).sum())
        sk = C.skel(crack)
        r = dict(frame=n, kept=kept, painted=int(crack.sum()),
                 median_2edt=float(2 * np.median(ndi.distance_transform_edt(crack)[crack]))
                 if crack.any() else 0.0)
        for w, it in (("trace3", 1), ("trace9", 4), ("trace33", 16)):
            m = ndi.binary_dilation(sk, st, iterations=it)
            r["del_" + w] = int((shipped & crack & ~m).sum())
        rows.append(r)
        print(f"[{i}/{len(names)}] {n:<38} kept {kept:>10,}  paint width p50 "
              f"{r['median_2edt']:6.1f} px  3px deletes {100*r['del_trace3']/max(kept,1):5.1f}%"
              f"  9px {100*r['del_trace9']/max(kept,1):5.1f}%"
              f"  33px {100*r['del_trace33']/max(kept,1):5.1f}%  {time.time()-t0:4.0f}s",
              flush=True)
        json.dump(rows, open(os.path.join(OUT, a.save), "w"))
    K = sum(r["kept"] for r in rows)
    for w in ("trace3", "trace9", "trace33"):
        D = sum(r["del_" + w] for r in rows)
        print(f"  {w:<9} deletes {100*D/max(K,1):.2f}% of kept hand-marked crack over "
              f"{len(rows)} frames")


if __name__ == "__main__":
    main()
