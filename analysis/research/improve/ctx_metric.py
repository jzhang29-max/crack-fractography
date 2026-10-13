"""IS clDice ACTUALLY WIDTH-INSENSITIVE AGAINST THIS BRUSH? And if not, what is?

The brief's second fact says clDice "ignores how thickly it was drawn". The dilation null
says otherwise: isotropic dilation of the shipped mask adds no information whatsoever and
moves clDice 0.6405 -> 0.7702. Two tests pin down why, and a third proposes the
instrument that does not have the fault.

 1. IS THE 0.9984 REACHABLE? The "correct 3 px trace" scores it because it IS the
    skeleton of the label -- an oracle. Slide the same correct trace sideways INSIDE the
    paint, by d px, still entirely on hand-marked crack and still 3 px wide, and read
    clDice. If it collapses, 0.9984 is not a score an honest thin method can approach;
    it is the label's own medial axis scoring against itself.

 2. WHICH HALF BREAKS? tprec reads the prediction's skeleton, so dilation barely moves
    it. tsens reads whether the LABEL's medial axis is covered, and a wider prediction
    covers more of it. So clDice is width-insensitive in tprec and width-SEEKING in
    tsens, and against a 35 px brush the second term dominates.

 3. THE REPLACEMENT. Score skeleton against skeleton at a tolerance: match skel(pred) to
    skel(gt) within tau px both ways and take the F1. Dilating the prediction does not
    move its skeleton, so the null must read FLAT -- that is the test of the instrument,
    and it is run here before the instrument is used on anything.
"""
import os, sys, json
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C, ctx_method as M
from ctx_matched import dilate_to_area, grow_to_area

ST = ndi.generate_binary_structure(2, 2)


def skelf1(pred, gt, tau=5):
    """F1 between the two SKELETONS at a tau px tolerance. Width-insensitive by
    construction: thickening the prediction leaves skel(pred) where it was."""
    pred = np.asarray(pred, bool); gt = np.asarray(gt, bool)
    if not pred.any() or not gt.any():
        return 0.0
    sp, sg = skeletonize(pred), skeletonize(gt)
    if not sp.any() or not sg.any():
        return 0.0
    dg = ndi.distance_transform_edt(~sg)
    dp = ndi.distance_transform_edt(~sp)
    p = float((dg[sp] <= tau).mean())
    r = float((dp[sg] <= tau).mean())
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def shifted_trace(gt, d, width=3):
    """The correct centreline, slid d px sideways but kept INSIDE the paint. Built by
    taking the level set of the distance-to-boundary at (max - d) rather than the ridge,
    so it is a legitimate thin curve entirely on hand-marked crack."""
    if d == 0:
        return C.correct_trace(gt, width)
    sk = skeletonize(gt)
    # move each skeleton point d px along the gradient of the distance transform's
    # perpendicular: approximate by dilating the skeleton d px and keeping the part at
    # exactly distance d, intersected with the paint
    ring = (ndi.distance_transform_edt(~sk) <= d) & (ndi.distance_transform_edt(~sk) > d - 1)
    out = ring & gt
    if not out.any():
        return C.correct_trace(gt, width)
    return ndi.binary_dilation(out, ST, iterations=max(0, (width - 1) // 2))


DILA = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
SHIFTS = (0, 2, 5, 10, 20)


def main():
    ts = C.tiles()
    gtw = []
    shift = {d: [] for d in SHIFTS}
    dil = {a: dict(cld=[], sf3=[], sf5=[], sf10=[]) for a in DILA}
    ctx = {a: dict(cld=[], sf3=[], sf5=[], sf10=[]) for a in (0.5, 1.0, 2.0)}
    trace = dict(cld=[], sf3=[], sf5=[], sf10=[])
    for i, t in enumerate(ts, 1):
        gt = t["gt"]; d = C.prep(t); seed = d["cur"]
        sg = skeletonize(gt)
        gtw.append(float(np.median(2 * ndi.distance_transform_edt(gt)[sg])))
        for s in SHIFTS:
            shift[s].append(C.cldice(shifted_trace(gt, s), gt))
        tr = C.correct_trace(gt)
        trace["cld"].append(C.cldice(tr, gt))
        for tau, k in ((3, "sf3"), (5, "sf5"), (10, "sf10")):
            trace[k].append(skelf1(tr, gt, tau))
        n = int(seed.sum())
        cost = M.cost_field(d["sm"], d["fr"])
        for a in DILA:
            m = dilate_to_area(seed, int(round(a * n)))
            dil[a]["cld"].append(C.cldice(m, gt))
            for tau, k in ((3, "sf3"), (5, "sf5"), (10, "sf10")):
                dil[a][k].append(skelf1(m, gt, tau))
        for a in ctx:
            m, _ = grow_to_area(seed, cost, int(round(a * n)))
            ctx[a]["cld"].append(C.cldice(m, gt))
            for tau, k in ((3, "sf3"), (5, "sf5"), (10, "sf10")):
                ctx[a][k].append(skelf1(m, gt, tau))
        print(f"  [{i:>2}/{len(ts)}] {t['frame'][:44]}", flush=True)

    print(f"\nmedian label WIDTH at its own centreline, over the 26 tiles: "
          f"{np.median(gtw):.1f} px  (range {min(gtw):.0f}-{max(gtw):.0f})")

    print("\n1. THE 'CORRECT 3 PX TRACE' SLID SIDEWAYS, STILL ENTIRELY INSIDE THE PAINT")
    print(f"   {'shift (px)':>11} {'clDice':>9}")
    for s in SHIFTS:
        print(f"   {s:>11} {np.median(shift[s]):9.4f}")

    print("\n2/3. THE NULL UNDER BOTH INSTRUMENTS. clDice must rise with pure width; a")
    print("     width-insensitive instrument must not.")
    print(f"   {'arm':<22} {'clDice':>9} {'skelF1@3':>10} {'skelF1@5':>10} {'skelF1@10':>10}")
    print(f"   {'correct 3 px trace':<22} {np.median(trace['cld']):9.4f} "
          f"{np.median(trace['sf3']):10.4f} {np.median(trace['sf5']):10.4f} "
          f"{np.median(trace['sf10']):10.4f}")
    for a in DILA:
        nm = "shipped v1.49.1" if a == 0 else f"  + dilation x{a}"
        print(f"   {nm:<22} {np.median(dil[a]['cld']):9.4f} {np.median(dil[a]['sf3']):10.4f} "
              f"{np.median(dil[a]['sf5']):10.4f} {np.median(dil[a]['sf10']):10.4f}")
    for a in sorted(ctx):
        print(f"   {'  + CONTEXT x' + str(a):<22} {np.median(ctx[a]['cld']):9.4f} "
              f"{np.median(ctx[a]['sf3']):10.4f} {np.median(ctx[a]['sf5']):10.4f} "
              f"{np.median(ctx[a]['sf10']):10.4f}")
    json.dump(dict(gtw=gtw, shift={str(k): v for k, v in shift.items()}, trace=trace,
                   dil={str(k): v for k, v in dil.items()},
                   ctx={str(k): v for k, v in ctx.items()}),
              open(os.path.join(C.MY, "metric.json"), "w"))


if __name__ == "__main__":
    main()
