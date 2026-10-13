"""THE THIRD CONTEXT FORMULATION: orientation coherence (tensor-voting-lite).

The first two both scored a route by how DARK it was. This one scores a pixel by whether
it CONTINUES ITS NEIGHBOUR'S DIRECTION, which is the one property in the task's list that
darkness cannot express, and the one a region-local rule provably cannot compute.

    orientation field  theta(x,y) from the Hessian of the flattened image, smoothed over
                       sigma_o so it is the direction of the local ridge, not of noise.
    growth             a pixel is added at step k only if one of its 8 neighbours is
                       already marked AND the offset to that neighbour lies within
                       +/-22.5 deg of theta at the pixel being added. A crack grows along
                       itself; a round void cannot grow at all, because its boundary
                       orientation disagrees with every outward offset.

Priced the same way as the other two: against an ISOTROPIC dilation given exactly the
same number of added pixels on exactly the same tile. Orientation either beats width per
pixel spent or it does not.

Also reported: the same growth with the orientation field ROTATED 90 degrees. If growing
ACROSS the ridge scores like growing ALONG it, the orientation field is not carrying
direction and the arm is dilation with extra steps.
"""
import os, sys, json
import numpy as np
from scipy import ndimage as ndi
from skimage.feature import hessian_matrix, hessian_matrix_eigvals

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import ctx_core as C, ctx_method as M
from ctx_matched import dilate_to_area

OFF = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
OFFANG = np.array([np.arctan2(o[0], o[1]) for o in OFF])


def orientation(flat, sigma=2.0):
    """Direction of the ridge: the eigenvector of the Hessian with the SMALLER absolute
    eigenvalue, i.e. the direction along which intensity changes least."""
    Hrr, Hrc, Hcc = hessian_matrix(flat.astype(np.float64), sigma=sigma, order="rc",
                                   use_gaussian_derivatives=False)
    # eigenvector of the 2x2 [[Hrr,Hrc],[Hrc,Hcc]] for the smaller |eigenvalue|
    tr = Hrr + Hcc
    det = Hrr * Hcc - Hrc * Hrc
    disc = np.sqrt(np.maximum(tr * tr / 4 - det, 0))
    l1, l2 = tr / 2 + disc, tr / 2 - disc
    small = np.where(np.abs(l1) <= np.abs(l2), l1, l2)
    vr, vc = Hrc, small - Hrr                      # (Hrr-l)x + Hrc y = 0  ->  v=(Hrc, l-Hrr)
    n = np.hypot(vr, vc); n[n == 0] = 1
    return np.arctan2(vr / n, vc / n)              # in (-pi, pi], axis direction mod pi


def oriented_steps(seed, theta, nsteps=40, tol=np.pi / 8):
    """Step index at which each pixel is first reached by orientation-coherent growth.
    Unreached pixels get inf, so the result can be area-matched by thresholding."""
    ok = np.zeros((8,) + seed.shape, bool)
    for i, a in enumerate(OFFANG):
        d = np.abs(np.angle(np.exp(1j * 2 * (theta - a)))) / 2      # axis difference mod pi
        ok[i] = d <= tol
    cur = seed.copy()
    step = np.where(seed, 0.0, np.inf)
    for k in range(1, nsteps + 1):
        nxt = np.zeros_like(cur)
        for i, (dr, dc) in enumerate(OFF):
            nxt |= np.roll(np.roll(cur, dr, 0), dc, 1) & ok[i]
        new = nxt & ~cur
        if not new.any():
            break
        step[new] = k
        cur |= new
    return step


def to_area(step, seed, extra):
    if extra <= 0:
        return seed.copy()
    v = step[~seed]; v = v[np.isfinite(v)]
    if v.size == 0:
        return seed.copy()
    k = min(int(extra), v.size)
    thr = float(np.partition(v, k - 1)[k - 1])
    return seed | (np.isfinite(step) & (step <= thr) & ~seed)


ALPHAS = (0.25, 0.5, 1.0, 2.0)


def main():
    ts = C.tiles()
    arms = ["ORIENT along ridge", "ORIENT rotated 90 (sabotage)", "DILATE isotropic"]
    res = {a: {al: [] for al in ALPHAS} for a in arms}
    base = []
    for i, t in enumerate(ts, 1):
        d = C.prep(t); gt = t["gt"]; seed = d["cur"]
        base.append(C.row(seed, gt))
        th = orientation(d["flat"])
        s_al = oriented_steps(seed, th)
        s_rot = oriented_steps(seed, th + np.pi / 2)
        n = int(seed.sum())
        for al in ALPHAS:
            e = int(round(al * n))
            res["ORIENT along ridge"][al].append(C.row(to_area(s_al, seed, e), gt))
            res["ORIENT rotated 90 (sabotage)"][al].append(C.row(to_area(s_rot, seed, e), gt))
            res["DILATE isotropic"][al].append(C.row(dilate_to_area(seed, e), gt))
        print(f"  [{i:>2}/{len(ts)}] {t['frame'][:44]}", flush=True)

    b = C.pooled(base)
    print(f"\nshipped v1.49.1   clDice {b['cldice']:.4f}  IoU {b['iou']:.4f}\n")
    print(f"{'arm':<30} {'alpha':>6} {'area x':>7} {'clDice':>8} {'IoU':>7} {'tprec':>7} {'tsens':>7}")
    print("-" * 76)
    ba = sum(r["area"] for r in base)
    for a in arms:
        for al in ALPHAS:
            r = res[a][al]; m = C.pooled(r)
            print(f"{a:<30} {al:6.2f} {sum(x['area'] for x in r)/ba:7.3f} {m['cldice']:8.4f} "
                  f"{m['iou']:7.4f} {np.median([x['tprec'] for x in r]):7.4f} "
                  f"{np.median([x['tsens'] for x in r]):7.4f}")
        print()
    json.dump({a: {str(k): v for k, v in d_.items()} for a, d_ in res.items()},
              open(os.path.join(C.MY, "orient.json"), "w"))


if __name__ == "__main__":
    main()
