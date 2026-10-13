"""CAN skelF1@tau BE GAMED? The adversarial controls, before the instrument is proposed.

A tolerance-based skeleton match has two obvious exploits and both are tested here on
the real tiles:

  SPRAY     a regular lattice of single pixels spaced <= tau apart puts a skeleton
            fragment within tau of EVERY gt-skeleton pixel, so recall is 1 by
            construction. It must be killed by precision, which asks what fraction of
            the prediction's own skeleton is near the label's. This is the same trap a
            nearest-colour census falls into without decoys.
  SLIVER    one tiny mark sitting exactly on the label's centreline: precision 1, recall
            ~0.
  DASHES    the correct trace chopped into pieces -- fragmentation must not be rewarded.

Reported beside clDice and IoU, which have their own answers to the same three.
"""
import os, sys, json
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C
from ctx_metric import skelf1


def spray(shape, step):
    m = np.zeros(shape, bool)
    m[::step, ::step] = True
    return m


def dashes(gt, on=6, off=6):
    tr = C.correct_trace(gt)
    lab, n = ndi.label(tr, structure=C.STRUCT8)
    out = np.zeros_like(tr)
    idx = np.indices(tr.shape).sum(0)
    out = tr & ((idx // on) % 2 == 0) if off else tr
    return out


def main():
    ts = C.tiles()
    arms = {k: [] for k in ("spray lattice step 4", "spray lattice step 7",
                            "sliver on the centreline", "correct trace, dashed",
                            "correct 3 px trace", "shipped v1.49.1")}
    for i, t in enumerate(ts, 1):
        gt = t["gt"]; d = C.prep(t)
        sg = skeletonize(gt)
        sl = np.zeros_like(gt)
        ys, xs = np.nonzero(sg)
        if len(ys):
            k = len(ys) // 2
            sl[max(0, ys[k]-1):ys[k]+2, max(0, xs[k]-1):xs[k]+2] = True
        for k, m in (("spray lattice step 4", spray(gt.shape, 4)),
                     ("spray lattice step 7", spray(gt.shape, 7)),
                     ("sliver on the centreline", sl),
                     ("correct trace, dashed", dashes(gt)),
                     ("correct 3 px trace", C.correct_trace(gt)),
                     ("shipped v1.49.1", d["cur"])):
            r = C.row(m, gt)
            arms[k].append((skelf1(m, gt, 5), r["cld"],
                            r["tp"] / max(r["tp"] + r["fp"] + r["fn"], 1),
                            r["area"] / gt.size))
        print(f"  [{i:>2}/{len(ts)}] {t['frame'][:44]}", flush=True)
    print(f"\n{'arm':<28} {'area %':>8} {'skelF1@5':>10} {'clDice':>9} {'IoU':>8}")
    print("-" * 66)
    for k, v in arms.items():
        a = np.array(v)
        print(f"{k:<28} {100*np.median(a[:,3]):8.2f} {np.median(a[:,0]):10.4f} "
              f"{np.median(a[:,1]):9.4f} {np.median(a[:,2]):8.4f}")
    json.dump({k: np.array(v).tolist() for k, v in arms.items()},
              open(os.path.join(C.MY, "gamecheck.json"), "w"))


if __name__ == "__main__":
    main()


def tau_sweep():
    """THE LIMITATION, measured. A tolerance forgives gaps up to about 2*tau, so a
    DASHED correct trace scores like an unbroken one once tau is large. Pick tau from
    this table, not from taste: it must separate the dashed trace from the solid one
    while still scoring the solid one ~1 and the spray lattice ~0.
    """
    ts = C.tiles()
    taus = (1, 2, 3, 5, 8)
    rows = {k: {t: [] for t in taus} for k in
            ("correct 3 px trace", "correct trace, dashed", "spray lattice step 4",
             "shipped v1.49.1", "shipped + dilation x1.0")}
    from ctx_matched import dilate_to_area
    for i, t in enumerate(ts, 1):
        gt = t["gt"]; d = C.prep(t)
        ms = {"correct 3 px trace": C.correct_trace(gt),
              "correct trace, dashed": dashes(gt),
              "spray lattice step 4": spray(gt.shape, 4),
              "shipped v1.49.1": d["cur"],
              "shipped + dilation x1.0": dilate_to_area(d["cur"], int(d["cur"].sum()))}
        for k, m in ms.items():
            for ta in taus:
                rows[k][ta].append(skelf1(m, gt, ta))
        print(f"  [{i:>2}/{len(ts)}] {t['frame'][:44]}", flush=True)
    print(f"\n{'arm':<26}" + "".join(f"{'tau=' + str(t):>9}" for t in taus))
    print("-" * (26 + 9 * len(taus)))
    for k in rows:
        print(f"{k:<26}" + "".join(f"{np.median(rows[k][t]):9.4f}" for t in taus))
    print("\nREAD: the tolerance must be small enough that a DASHED trace is not scored as")
    print("a solid one, and the width null (last row vs the one above it) must stay flat.")


if __name__ != "__main__":
    pass
