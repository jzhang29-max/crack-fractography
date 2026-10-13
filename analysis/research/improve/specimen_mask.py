"""ANGLE 2 -- segment the SPECIMEN first, then never score anything outside it.

The four precision rules that died here all asked, one region at a time, "is this blob a
crack?". They all failed on the same object: a wide-open main crack, which is large, dark,
smooth and border-touching, i.e. identical to off-specimen background under every
REGION-LOCAL property anyone measured (unified_pipeline.run_unified_pipeline lists three:
vesselness, raw darkness -- INVERTED -- and perimeter touch at 28.6% vs 28.5%). That
comment ends by naming the property nobody measured: "whether the region is ENCLOSED BY
SPECIMEN".

This module computes that property, and it computes it from the IMAGE, not from the
candidate regions -- it never looks at the detector's output, so it cannot be a fifth
region classifier wearing a hat. The construction:

  1. COARSE TEXTURE ENERGY. Material returns signal and therefore has texture; empty space
     does not. Measured on 8x8 block statistics (block mean + block std) because a
     specimen boundary is a coarse-scale object and a per-pixel texture measure is both
     60x more expensive and dominated by noise. Two energies are offered:
         "fine"   local mean of the 8x8 block STD   -- grain/noise energy
         "coarse" local std  of the 8x8 block MEAN  -- large-scale structure
         "max"    the larger of the two, each in units of its own frame median
  2. THRESHOLD. Otsu on the energy map, parameter-free. (A median-multiple rule is
     offered too, so the threshold choice can be shown not to carry the result.)
  3. BRIDGE THE CRACKS -- this is the whole idea, and the ONLY place a scale enters.
     A crack is a thin region EMBEDDED in material: close the textured set with a disk of
     radius R and the crack is bridged, because material faces material across it. Off-
     specimen background is not bridged, because there is no material on the far side --
     the far side is the edge of the frame. R is in FULL-RESOLUTION pixels and must exceed
     the half-width of the widest crack; it is swept, never picked by a score.
  4. FILL HOLES, keep the large components. What survives is the specimen. Everything
     outside it is background BY CONSTRUCTION and is never offered to the detector.

The hazard is stated head-on because it is the one that killed the others: a wide-open
crack is ALSO untextured, so step 1 alone would excise the main crack. Step 3 is what
separates them, and step 3 is topological (is there material on the far side?) rather than
region-local (is this blob smooth?). If R is too small the main crack is not bridged and
this becomes the fifth dead rule -- which is exactly what the primary gate measures.

Also provided, as a second and independent operator: enclosure_axis(), which asks directly
whether a pixel has material on BOTH sides along at least one axis. No closing radius, no
connected components. It is a weaker statement than step 3 and is here as a control.

Nothing here reads the correction masks, the ground truth, or the detector output.
"""
import numpy as np
from scipy import ndimage as ndi
from skimage import filters, morphology

B = 8      # block factor the coarse statistics are computed at


# ------------------------------------------------------------------ coarse statistics
def blocks(img8, b=B):
    h, w = img8.shape
    hh, ww = h // b * b, w // b * b
    a = img8[:hh, :ww].astype(np.float32).reshape(hh // b, b, ww // b, b)
    return (a.mean(axis=(1, 3)).astype(np.float32),
            np.sqrt(np.maximum(a.var(axis=(1, 3)), 0)).astype(np.float32))


def energy(bmean, bstd, kind="max", win=4):
    """Texture energy on the coarse grid, in units of its own frame median.

    `win` is a radius in COARSE pixels (so win=4 is a 72x72 full-resolution window).
    Dividing by the median makes the map comparable across captures with different gain,
    which matters because these frames span CBS and ETD detectors.
    """
    k = 2 * int(win) + 1
    fine = ndi.uniform_filter(bstd, k)
    m = ndi.uniform_filter(bmean, k)
    m2 = ndi.uniform_filter(bmean * bmean, k)
    coarse = np.sqrt(np.maximum(m2 - m * m, 0))
    fine = fine / max(float(np.median(fine)), 1e-6)
    coarse = coarse / max(float(np.median(coarse)), 1e-6)
    return {"fine": fine, "coarse": coarse, "max": np.maximum(fine, coarse)}[kind]


def _close(T, r):
    """Binary closing by a disk of radius r, via two distance transforms.

    morphology.binary_closing(disk(r)) is O(N r^2) and r here is ~50-100 coarse pixels,
    which takes minutes on a 768x512 grid. Exact same result in O(N): dilation by a disk
    is "within r of a True pixel", erosion of that is "not within r of a False pixel".
    _selfcheck_close() asserts the two agree for small r before anything is measured.
    """
    dil = ndi.distance_transform_edt(~T) <= r
    if dil.all():
        return dil                      # nothing to erode against; edt of an all-True
    return ndi.distance_transform_edt(dil) > r      # array has no zero to measure to


def _selfcheck_close(seed=0):
    rng = np.random.default_rng(seed)
    ok = True
    for r in (1, 2, 3, 5, 8):
        for dens in (0.02, 0.1, 0.3):
            T = rng.random((90, 110)) < dens
            a = _close(T, r)
            b = ndi.binary_erosion(ndi.binary_dilation(T, morphology.disk(r)),
                                   morphology.disk(r), border_value=1)
            ok &= bool(np.array_equal(a, b))
    return ok


def _threshold(E, rule):
    if rule == "otsu":
        return float(filters.threshold_otsu(E))
    if isinstance(rule, (int, float)):
        return float(rule)             # already in median units
    raise ValueError(rule)


# ------------------------------------------------------------------ the specimen mask
def specimen_coarse(bmean, bstd, close_px=400, kind="max", win=4, rule="otsu",
                    min_comp_frac=0.02, grow_px=0, b=B):
    """The specimen mask on the coarse grid. close_px/grow_px are FULL-RES pixels."""
    E = energy(bmean, bstd, kind, win)
    T = E >= _threshold(E, rule)
    r = max(1, int(round(close_px / float(b))))
    S = _close(T, r)
    lab, n = ndi.label(S, structure=np.ones((3, 3), bool))
    if n:
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        keep = np.flatnonzero(sizes >= max(1.0, min_comp_frac * S.size))
        S = np.isin(lab, keep) if len(keep) else (lab == int(sizes.argmax()))
    S = ndi.binary_fill_holes(S)
    if grow_px:
        g = max(1, int(round(grow_px / float(b))))
        S = ndi.distance_transform_edt(~S) <= g
    return S, T, E


def upsample(S, shape, b=B):
    """Coarse mask -> full resolution. Edge rows/cols the block grid could not cover are
    set True (inside the specimen): this mask may only ever REMOVE area, so an unknown
    strip must default to 'keep', never to 'background'."""
    full = np.ones(shape, bool)
    up = np.kron(S, np.ones((b, b), bool))
    h = min(shape[0], up.shape[0]); w = min(shape[1], up.shape[1])
    full[:h, :w] = up[:h, :w]
    return full


def specimen_mask(img8=None, bmean=None, bstd=None, shape=None, **kw):
    if bmean is None:
        bmean, bstd = blocks(img8)
        shape = img8.shape
    S, T, E = specimen_coarse(bmean, bstd, **kw)
    return upsample(S, shape), S, T, E


# ------------------------------------------------------------------ control operator
def enclosure_axis(T):
    """Material on BOTH sides along at least one axis, on the coarse grid.

    A crack has material facing material across its width, so at least one axis is
    bounded. Off-specimen background runs to the frame edge, so the axis perpendicular to
    that edge is bounded on one side only. No closing radius and no components -- a
    strictly weaker, purely local-to-the-ray statement than specimen_coarse(), kept as a
    control so the closing step can be shown to be doing the work.
    """
    def anyside(a, axis, rev):
        x = a[::-1] if (rev and axis == 0) else (a[:, ::-1] if (rev and axis == 1) else a)
        c = np.maximum.accumulate(x, axis=axis)
        c = np.roll(c, 1, axis=axis)
        if axis == 0:
            c[0, :] = False
        else:
            c[:, 0] = False
        return c[::-1] if (rev and axis == 0) else (c[:, ::-1] if (rev and axis == 1) else c)

    up, dn = anyside(T, 0, False), anyside(T, 0, True)
    lf, rt = anyside(T, 1, False), anyside(T, 1, True)
    return (up & dn) | (lf & rt) | T


# ------------------------------------------------------------------ the one variant grid
# ONE grid, shared by the full-frame gate and the tile bench, so the two instruments are
# answering about the same objects. A variant that exists on one side and not the other
# cannot be cross-read, and cross-reading them is the entire point.
GRID = [dict(kind=k, rule=t, close_px=R, grow_px=g)
        for k in ("fine", "coarse")
        for t in (0.1, 0.2, 0.3, 0.5)
        for R in (200, 300, 400, 600, 800, 1200, 1600, 2400)
        for g in (0, 200, 400)]
# CONTROL ARM: the closing/largest-component step replaced by the weaker ray test
# (material on both sides along some axis), so the closing can be shown to do the work.
GRID += [dict(kind="fine", rule=t, close_px=R, grow_px=0, enclosure=True)
         for t in (0.2, 0.3) for R in (300, 400, 800)]


def vkey(v):
    return (f"{v['kind']}/thr{v['rule']}/R{v['close_px']}/g{v['grow_px']}"
            + ("/encl" if v.get("enclosure") else ""))


def build(bmean, bstd, v):
    """One grid entry -> a coarse specimen mask."""
    S, T, E = specimen_coarse(bmean, bstd, **{k: v[k] for k in
                                              ("kind", "rule", "close_px", "grow_px")})
    return (S | enclosure_axis(T)) if v.get("enclosure") else S
