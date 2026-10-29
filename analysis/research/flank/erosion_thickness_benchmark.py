"""Matched comparison: one free constant per arm, the same grid, the same eight cells.

THE FIRST RUN WAS RIGGED, by me, in ET's favour. I set ET's threshold to 2 x the true
half-width of each synthetic cell -- an oracle the generator knows and no real frame does
-- while the width-floor rule read its width from the distance transform. ET came out 8x
better and the number meant nothing.

Here each arm gets ONE constant, held FIXED across all eight cells, swept over its own
grid, and the arm is scored at its best single value. That is the discipline the rest of
this project uses for the classical comparators. Reported with it: the per-cell error at
that value, so a reader can see whether the winner needs the cells to agree.

  width-floor   min_branch_widths: the third-longest branch at a node must exceed this
                multiple of the LOCAL diameter, read from the distance transform
  ET            tau in PIXELS: prune a peripheral branch whose
                R(end) + geodesic(end, node) - R(node) falls below tau

Truth is 4 by construction in every cell.
"""
import os
import sys
import warnings
warnings.filterwarnings("ignore")
import numpy as np
from scipy import ndimage as ndi
from skimage import morphology, draw

REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.dont_write_bytecode = True
import crackmode as CM

_EIGHT = np.ones((3, 3), np.uint8)
CELLS = [(hw, r) for hw in (2, 5, 15, 40) for r in (0.0, 1.0)]


def synthetic(half_width=5, roughness=0.0, side=600, seed=0):
    rng = np.random.default_rng(seed)
    m = np.zeros((side, side), bool)
    for (y0, x0), (y1, x1) in [((80, 300), (520, 300)), ((200, 300), (120, 120)),
                               ((300, 300), (380, 120)), ((400, 300), (330, 480)),
                               ((120, 120), (300, 120))]:
        rr, cc = draw.line(y0, x0, y1, x1)
        m[rr, cc] = True
    m = ndi.binary_dilation(m, morphology.disk(half_width))
    if roughness > 0:
        shell = ndi.binary_dilation(m, morphology.disk(2)) & ~ndi.binary_erosion(
            m, morphology.disk(2))
        m = m ^ ((rng.random(m.shape) < roughness * 0.5) & shell)
        m = ndi.binary_fill_holes(m)
    return m


def _clusters(skel):
    cand, _ = CM._junction_candidates(skel)
    jlab, nj = ndi.label(cand, structure=_EIGHT)
    return cand, jlab, int(nj)


def _nodes(skel, min_degree=3):
    cand, jlab, nj = _clusters(skel)
    if nj == 0:
        return 0
    blab, nb = ndi.label(skel & ~cand, structure=_EIGHT)
    if nb == 0:
        return 0
    inc = CM._incident_branches(jlab, blab, range(1, nj + 1))
    return sum(1 for i in range(1, nj + 1) if len(inc[i]) >= min_degree)


def et_prune(mask, tau, min_degree=3, max_passes=400):
    """Shaked-Bruckstein pruning with the Liu et al. 2011 ET value. No re-skeletonisation."""
    skel = morphology.skeletonize(mask).copy()
    R = ndi.distance_transform_edt(mask)
    for _ in range(max_passes):
        cand, jlab, nj = _clusters(skel)
        if nj == 0:
            break
        blab, nb = ndi.label(skel & ~cand, structure=_EIGHT)
        if nb == 0:
            break
        inc = CM._incident_branches(jlab, blab, range(1, nj + 1))
        touch = {}
        for cid, bs in inc.items():
            for b in bs:
                touch.setdefault(b, set()).add(cid)
        cen = ndi.center_of_mass(jlab > 0, jlab, list(range(1, nj + 1)))
        doomed = []
        for b, cids in touch.items():
            if len(cids) != 1:
                continue
            cid = next(iter(cids))
            jy, jx = cen[cid - 1]
            px = np.argwhere(blab == b)
            if not len(px):
                continue
            far = px[int(np.argmax(np.hypot(px[:, 0] - jy, px[:, 1] - jx)))]
            et = (R[far[0], far[1]] + len(px)
                  - R[int(round(jy)), int(round(jx))])
            if et < tau:
                doomed.append(b)
        if not doomed:
            break
        for b in doomed:
            skel[blab == b] = False
    return _nodes(skel, min_degree)


MASKS = {c: synthetic(*c) for c in CELLS}
print(f"built {len(MASKS)} cells\n")

ET_GRID = [1, 2, 3, 5, 8, 12, 20, 30, 50, 80, 120, 200]
WF_GRID = [0.0, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]

print("ET, one fixed tau in px for every cell")
print(f"  {'tau':>5} {'per-cell counts':<34} {'sum|err|':>8}")
et_best = None
for tau in ET_GRID:
    counts = [et_prune(MASKS[c], tau) for c in CELLS]
    err = sum(abs(v - 4) for v in counts)
    print(f"  {tau:>5} {str(counts):<34} {err:>8}")
    if et_best is None or err < et_best[1]:
        et_best = (tau, err, counts)

print("\nwidth-floor, one fixed multiple of the LOCAL diameter for every cell")
print(f"  {'mbw':>5} {'per-cell counts':<34} {'sum|err|':>8}")
wf_best = None
for mbw in WF_GRID:
    counts = []
    for c in CELLS:
        g = CM._skeleton_graph(MASKS[c], regularise_px=0, min_branch_widths=mbw)
        counts.append(len(g["nodes"][0]))
    err = sum(abs(v - 4) for v in counts)
    print(f"  {mbw:>5} {str(counts):<34} {err:>8}")
    if wf_best is None or err < wf_best[1]:
        wf_best = (mbw, err, counts)

print(f"\n{'=' * 78}")
print(f"  ET          best tau {et_best[0]:<6} sum|err| {et_best[1]:<6} {et_best[2]}")
print(f"  width-floor best mbw {wf_best[0]:<6} sum|err| {wf_best[1]:<6} {wf_best[2]}")
print(f"  truth in every cell: 4")
