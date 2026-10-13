"""Q1 -- THE LABEL-IMPOSED CEILING. What does a PERFECTLY LOCALISED answer score?

A trace down the centre of the human's own paint is, by construction, in exactly the right
place: it cannot be improved on localisation. The only thing left to vary is how thick it
is drawn. So sweep the thickness from 1 px to 41 px and read off every metric. The curve
separates the two things a score conflates:

    everything that changes along this curve is WIDTH
    everything that does not change is LOCALISATION

Because the trace is on the label's own centreline, clDice is pinned near 1.0 at every
width -- that is the point: clDice is blind to the axis IoU is dominated by. The IoU of
the same, perfectly placed answer swings by a factor of several across the sweep, and its
maximum is the highest IoU any correctly-placed predictor can reach against these labels
WITHOUT painting wider than the crack.

Thickening is done with a 3x3 square, i iterations -> width 2i+1, which reproduces the
brief's "3 px trace" row exactly (prec 0.9754, recall 0.2505, F1 0.3987, IoU 0.2490).
"""
import os, sys, json
import numpy as np
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import approach4_lib as L

SQ = np.ones((3, 3), bool)
WIDTHS = list(range(1, 42, 2))


def main():
    tiles = L.tiles_with_arms()

    # ---- how wide is the paint, per tile? area / centreline length is the mean width of
    # a region whatever its shape, which is the only width definition that needs no model.
    wid = []
    for t in tiles:
        a = int(t["gt"].sum()); s = int(t["skel_gt"].sum())
        wid.append(dict(frame=t["frame"], specimen=t["specimen"], area=a, skel=s,
                        mean_width=a / max(s, 1)))
    w = np.array([x["mean_width"] for x in wid])
    print("LABEL PAINT WIDTH (area / centreline length), 26 tiles")
    print(f"  median {np.median(w):.1f} px   mean {w.mean():.1f} px   "
          f"range {w.min():.1f} - {w.max():.1f} px")
    print("  pooled (total paint area / total centreline length): "
          f"{sum(x['area'] for x in wid) / sum(x['skel'] for x in wid):.1f} px\n")

    # ---- the sweep
    rows = {}
    for width in WIDTHS:
        it = (width - 1) // 2
        masks = [t["skel_gt"] if it == 0 else ndi.binary_dilation(t["skel_gt"], SQ, iterations=it)
                 for t in tiles]
        rows[width] = [L.score_tile(m, t["gt"], sgt=t["skel_gt"]) for m, t in zip(masks, tiles)]

    print("A PERFECTLY PLACED TRACE, AS A FUNCTION OF HOW THICKLY IT IS DRAWN")
    hdr = (f"{'trace width':>12}{'prec':>9}{'recall':>9}{'F1':>9}{'IoU':>9}"
           f"{'clDice':>9}{'clD-pool':>10}{'% of paint':>12}")
    print(hdr); print("  " + "-" * (len(hdr) - 2))
    curve = []
    for width in WIDTHS:
        m = L.pool(rows[width])
        area = sum(r["tp"] + r["fp"] for r in rows[width])
        gta = sum(r["tp"] + r["fn"] for r in rows[width])
        curve.append(dict(width=width, **{k: float(v) for k, v in m.items()},
                          area_fraction=area / gta))
        print(f"{width:>12}{m['precision']:9.4f}{m['recall']:9.4f}{m['f1']:9.4f}"
              f"{m['iou']:9.4f}{m['cldice_mean']:9.4f}{m['cldice_pooled']:10.4f}"
              f"{100 * area / gta:11.1f}%")

    best_iou = max(curve, key=lambda c: c["iou"])
    best_f1 = max(curve, key=lambda c: c["f1"])
    cld = [c["cldice_mean"] for c in curve]
    print(f"\n  IoU is maximised at width {best_iou['width']} px: IoU {best_iou['iou']:.4f}"
          f"  (at 3 px it is {curve[1]['iou']:.4f} -- a {best_iou['iou'] / curve[1]['iou']:.1f}x"
          f" swing from thickness alone, with localisation held perfect)")
    print(f"  F1  is maximised at width {best_f1['width']} px: F1 {best_f1['f1']:.4f}")
    print(f"  clDice over the whole sweep: {min(cld):.4f} - {max(cld):.4f}"
          f"  (spread {max(cld) - min(cld):.4f})")

    # ---- how much of a real score is width and how much is localisation?
    ref = {c["width"]: c for c in curve}
    print("\nWHAT THIS MEANS FOR THE ARMS -- each arm against the perfectly-placed trace of")
    print("the SAME area. The gap is pure localisation error; everything else was width.")
    arms = {"CURRENT MODEL (v1.49.1)": "current", "a correct 3 px trace": "trace3"}
    onel = [k for k in tiles[0]["arms"] if k.startswith("oneline_")]
    sc = {k: [L.score_tile(t["arms"][k], t["gt"], sgt=t["skel_gt"]) for t in tiles]
          for k in onel}
    held_ol, _, _ = L.loso_pick(tiles, sc, onel)
    named = [(n, [L.score_tile(t["arms"][k], t["gt"], sgt=t["skel_gt"]) for t in tiles])
             for n, k in arms.items()] + [("one-line threshold (LOSO)", held_ol)]
    print(f"  {'arm':<28}{'its IoU':>9}{'same-area trace IoU':>22}{'localisation cost':>19}")
    for n, r in named:
        m = L.pool(r)
        af = sum(x["tp"] + x["fp"] for x in r) / sum(x["tp"] + x["fn"] for x in r)
        # the trace width whose area fraction is closest to this arm's
        match = min(curve, key=lambda c: abs(c["area_fraction"] - af))
        print(f"  {n:<28}{m['iou']:9.4f}{match['iou']:22.4f}"
              f"{m['iou'] - match['iou']:19.4f}   (matched at width {match['width']} px)")

    json.dump(dict(curve=curve, widths=wid), open(os.path.join(L.WORK, "q1_ceiling.json"), "w"),
              indent=1)
    print("\nwrote", os.path.join(L.WORK, "q1_ceiling.json"))


if __name__ == "__main__":
    main()
