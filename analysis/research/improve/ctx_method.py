"""APPROACH 3 -- the context-aware classical method itself.

Every rule tried on this corpus so far scores a blob by its OWN statistics. This scores a
pixel by what lies along the cheapest route reaching it, which is a property of its
neighbours and cannot be computed from the blob alone.

Two context operators, both built on one cost field:

  COST FIELD   rank-normalised darkness and rank-normalised Frangi ridge response, fused
               and raised to a power. Rank-normalised per tile so a threshold means the
               same thing on a bright ETD frame and a dark CBS one. Matrix costs ~1,
               crack costs ~0.

  A. GEODESIC GROWTH ("hysteresis grown along low-cost paths, not by intensity")
     Minimum cumulative cost from the shipped mask to every pixel, then keep everything
     under a budget T. A pixel 30 px away is kept if the route there was dark the whole
     way and rejected if it had to cross matrix, which no intensity threshold at that
     pixel can distinguish.

  B. PATH COMPLETION ("a crack is the cheapest connected route between two points")
     One minimum-cost route between every pair of shipped components closer than L, kept
     only if its mean cost clears tau. A minimum spanning forest over the fragments.

Both are STRICTLY ADDITIVE to the shipped mask: they can only union pixels in. That is
deliberate -- six subtractive rules have died on the full-frame paint gate, and an
additive operator's deletion count is 0 by construction and asserted per frame.

THE CONTROL THAT MATTERS: a geodesic ball on a CONSTANT cost field is exactly a
dilation. So `ctx_sabotage.py` runs this method with the context removed -- constant
cost, shuffled cost, rotated cost -- and if those score the same, the gain is width, not
context.
"""
import numpy as np
from scipy import ndimage as ndi
from skimage.graph import MCP_Geometric
from skimage.morphology import skeletonize

STRUCT8 = ndi.generate_binary_structure(2, 2)


def rank01(a):
    """Map an array onto [0,1] by rank. Scale-free, so one threshold travels between
    tiles whose absolute grey levels differ by a factor of two."""
    a = np.asarray(a, np.float64).ravel()
    o = np.empty(a.size, np.float64)
    o[np.argsort(a, kind="stable")] = np.linspace(0.0, 1.0, a.size)
    return o


def cost_field(sm, fr, w_dark=0.5, q=0.10, gamma=2.0, floor=0.01):
    """Cheap where the image is dark AND ridge-like, expensive everywhere else.

    The transition is pinned to a RANK quantile `q`, not a grey level: measured over the
    26 tiles the missed crack centreline sits at the 6th percentile of darkness and the
    9th of ridge response, while matrix sits at the 50th by construction. So the map must
    saturate by about q=0.10 or matrix travel is affordable and the search floods -- the
    first cost field tried here used a soft power over the whole range, which made matrix
    only 7x dearer than crack, and a budget of 3.0 then marked 95% of every tile.
    """
    rd = rank01(sm).reshape(sm.shape)                 # 0 = darkest
    rr = 1.0 - rank01(fr).reshape(fr.shape)           # 0 = strongest ridge
    c = w_dark * np.minimum(rd / q, 1.0) ** gamma + (1.0 - w_dark) * np.minimum(rr / q, 1.0) ** gamma
    return (floor + c).astype(np.float64)


# ------------------------------------------------------------------ A. geodesic growth
def geodesic_grow(seed, cost, budget):
    """Everything reachable from `seed` for less than `budget` of accumulated cost."""
    if not seed.any():
        return np.zeros_like(seed)
    mcp = MCP_Geometric(cost, fully_connected=True)
    cc, _ = mcp.find_costs(list(zip(*np.nonzero(seed))))
    return np.isfinite(cc) & (cc <= budget)


# ------------------------------------------------------------------ B. path completion
def complete_paths(seed, cost, max_gap=60, tau=0.25, radius=1, max_pairs=400):
    """One cheapest route between each pair of shipped components within `max_gap` px,
    accepted only if the route's mean cost clears `tau`.

    The pairing is done on the Euclidean nearest-neighbour graph so the number of routes
    stays linear in the number of fragments; the ROUTE itself is the cost-field geodesic,
    which is what makes this context rather than a straight bridge.
    """
    lab, n = ndi.label(seed, structure=STRUCT8)
    out = np.zeros_like(seed)
    if n < 2:
        return out, []
    objs = ndi.find_objects(lab)
    cx = np.array([((o[0].start + o[0].stop) / 2, (o[1].start + o[1].stop) / 2) for o in objs])
    pairs = []
    for i in range(n):
        d = np.hypot(cx[:, 0] - cx[i, 0], cx[:, 1] - cx[i, 1]); d[i] = np.inf
        for j in np.argsort(d)[:3]:
            if d[j] <= max_gap * 3 and i < j:
                pairs.append((i + 1, j + 1))
            elif d[j] <= max_gap * 3 and j < i:
                pairs.append((j + 1, i + 1))
    pairs = sorted(set(pairs))[:max_pairs]
    mcp = MCP_Geometric(cost, fully_connected=True)
    kept = []
    bylab = {}
    for a, b in pairs:
        if a not in bylab:
            bylab[a] = list(zip(*np.nonzero(lab == a)))
        if b not in bylab:
            bylab[b] = list(zip(*np.nonzero(lab == b)))
        cc, _ = mcp.find_costs(bylab[a], bylab[b], find_all_ends=False)
        tgt = np.array(bylab[b])
        v = cc[tgt[:, 0], tgt[:, 1]]
        if not np.isfinite(v).any():
            continue
        end = tuple(tgt[int(np.nanargmin(np.where(np.isfinite(v), v, np.inf)))])
        try:
            route = np.array(mcp.traceback(end))
        except Exception:
            continue
        gap = [p for p in map(tuple, route) if not seed[p]]
        if not gap or len(gap) > max_gap:
            continue
        g = np.array(gap)
        mc = float(cost[g[:, 0], g[:, 1]].mean())
        if mc > tau:
            continue
        out[g[:, 0], g[:, 1]] = True
        kept.append((len(gap), mc))
    if radius and out.any():
        out = ndi.binary_dilation(out, STRUCT8, iterations=radius)
    return out, kept


# ------------------------------------------------------------------ the composed arm
def context_mask(seed, sm, fr, mode="A", w_dark=0.5, q=0.10, gamma=2.0,
                 budget=2.0, max_gap=60, tau=0.25, radius=1, cost=None):
    """seed | whatever the context operator adds. Strictly additive, always."""
    c = cost_field(sm, fr, w_dark, q, gamma) if cost is None else cost
    add = np.zeros_like(seed)
    if "A" in mode:
        add |= geodesic_grow(seed, c, budget) & ~seed
    if "B" in mode:
        p, _ = complete_paths(seed, c, max_gap, tau, radius)
        add |= p & ~seed
    return seed | add
