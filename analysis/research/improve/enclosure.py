"""ENCLOSURE: is a dark region ENCLOSED BY SPECIMEN, or is it off-specimen background?

VERDICT: SAFE, AND NO GAIN. The measure is real, it is the first rule here that does not
destroy hand-painted crack, and it does the one thing the repo said was impossible -- but
at every operating point safe enough to ship it fires on TWO blobs in 48 frames, removes
ZERO hand-marked not-crack, and leaves the tile score bit-identical to what ships today.
At every operating point that moves the tile score it becomes the fifth dead rule.
Nothing here should be shipped. The numbers are below; the reason is at the bottom.

WHY THIS ANGLE. unified_pipeline.py ends its long "do not reintroduce a region-level
rule" comment with the one discriminator it says nobody measured:

    "Physically this is expected: a wide-open crack void and empty background are the
     same thing to the detector, no returned signal. What separates them is whether the
     region is ENCLOSED BY SPECIMEN, which none of these measure."

Four precision rules have died here (retrained region classifier 72.67%, texture veto
67.54%, thickness excision at 50 px 62.43% and at 100 px 54.62%, all as a share of the
hand-marked crack the shipped path keeps). Every one is REGION-LOCAL -- it asks a
property of the region's own pixels -- and a wide-open main crack and off-specimen
background are region-locally identical. Enclosure is not region-local: it is a property
of the frame's layout AROUND the region.

It also must not be region-LEVEL in the implementation, and that is the whole point. The
repo names its own counterexample: on MAR_Amb_Cast_CBS_0005 the off-specimen background
and a crack holding 976,295 hand-marked pixels are ONE CONNECTED COMPONENT, so "no
region-level exclusion can drop it without destroying human labels". True -- so the rule
here is PER-PIXEL. A pixel-level enclosure score can carve the background half off that
component and leave the crack half standing.

WHAT IS MEASURED. All of it in one pass over the same frames with the same denominator,
so nothing that lost is quietly dropped.

  A  ray enclosure      per candidate pixel, cast 8 (or 16) rays to the frame border; a
                        ray is BLOCKED if it crosses >= m specimen (non-candidate) px.
                        E = blocked/N. Delete the pixel if E < need.
  B  open background    the shipped arm. Component the LOW-enclosure pixels on their own
                        and delete only those blobs that reach the frame edge and exceed
                        an area floor. This is what can carve a merged component.
  C  specimen hull      convex hull of the largest connected specimen component.
  D  border-reachable   NEGATIVE CONTROL, region level: drop any candidate component that
                        touches the frame border. The naive reading of "enclosed".
  E  local spec frac    NEGATIVE CONTROL, neighbourhood level: the same question asked
                        LOCALLY (fraction of a disc of radius R that is specimen).
  Decoys, because a rule that deletes area deletes crack: the real field FLIPPED before
  it is applied; the real field INVERTED; and RANDAREA, a random pixel subset handed the
  real arm's own per-frame (per-tile) deletion budget.

PRIMARY GATE -- 48 full frames against the hand paint, run before any tile score.
  masks  sem-crack-detector/interior_active_learning/paint/*_correction_mask.png
         1 = crack, 2 = not-crack, 3 = erased, 0 = UNREVIEWED (excluded from BOTH ends)
  hand-marked crack painted on these frames        70,041,625 px
  of which the SHIPPED v1.49 path keeps            21,162,207 px   <- the denominator
  hand-marked NOT-crack it also keeps                 386,214 px
  total candidate area                             69,708,963 px
  (fullframe_lever4_safety.py's comparable denominator is 20,903,694: it counts the
  regions that survive region_features_from_labeled, this counts the clean mask itself,
  +1.24%. Every arm below shares THIS denominator, so the rows are comparable to each
  other; against the four dead rules read the ratio, not the last digit.)

THE ONE ARM THAT PASSES -- openbg, need >= 4 of 8 rays, area floor 1,000,000 px:

  arm                      crack deleted  % of kept  frames>1%  notc removed  area removed
  openbg8_n4_A1000k                2,435     0.012%          0             0     3,601,661
  openbg16_n7_A1000k               1,487     0.007%          0             0     1,690,109
  openbg8_n4_A500k                16,530     0.078%          1             0     5,649,229
  openbg8_n4_A50k                142,621     0.674%          3           439     5,989,753
  openbg8_n4 (no floor)          203,329     0.961%          7           892     6,238,836
  openbg16_n9                  1,060,658     5.012%         13        42,907    11,640,925
  openbg16_n10                 2,467,618    11.661%         22        51,870    15,957,256
  rayE_m20_t0.875              5,159,830    24.382%         35        69,060    28,911,861
  rayE_m50_t1.000              9,067,511    42.848%         39        94,635    39,191,293
  --- the controls, which die exactly as predicted ---
  hull                         3,210,019    15.168%         17        45,823    25,013,559
  localfrac_R150_t0.25         5,756,032    27.201%         25        37,270    32,393,943
  borderdrop (region level)   13,408,058    63.354%         38       125,276    46,432,882
  localfrac_R50_t0.50         14,806,095    69.965%         40        90,760    49,185,583
  rayE_m20_t0.875_INVERT      16,002,377    75.618%         45       317,154    40,797,102

AND WHY THE PASS IS WORTH NOTHING. The passing arm fires on exactly TWO blobs in the
whole 48-frame corpus (census in the `blob_census` run; floors 200k and 500k reach five
blobs, 2,000,000 reaches none):
    1,884,208 px on 260708_316_H_b2_front_CBS_005   0 hand crack, 0 hand not-crack
    1,717,453 px on MAR_Amb_Cast_CBS_0005           2,435 hand crack, 0 hand not-crack
Two deletions is not a rule. It removes 5.2% of all candidate area and not one pixel of
it has a human verdict, so neither instrument can say whether it was a false positive.

THE COUNTEREXAMPLE, which is the one durable positive result. On MAR_Amb_Cast_CBS_0005
the candidate mask really does hold one border-touching component of 7,798,644 px
carrying 1,366,030 hand-marked crack px (the comment's 976,295 is on the older candidate
stage). Measured:
    arm              component crack kept   deleted      %   component px kept   pieces
    keepall                     1,366,030         0   0.00%          7,798,644        1
    openbg_n4                   1,354,410    11,620   0.85%          4,588,746       12
    rayE_m20_t0.500             1,352,626    13,404   0.98%          4,552,125     1843
    hull                          388,780   977,250  71.54%          1,419,125       12
    borderdrop (region level)           0 1,366,030 100.00%                  0        0
So the repo's claim is exactly right about region-level rules and exactly wrong as a
limit on what is possible: a pixel-level enclosure score carves 3,209,898 px of
off-specimen background out of that single component while keeping 99.15% of the hand
paint inside it. That is the thing unified_pipeline.py says cannot be done, done.

The same on the three frames where the four previous rules did their damage, reading the
single component that holds the most hand paint on each:
  frame                           component px   hand crack   openbg_n4 deletes   hull   borderdrop
  260708_316_H_b2_front_CBS_003      1,268,411      214,237     0.00% (0 px)    75.88%   100.00%
  260708_316_H_b2_front_CBS_004      2,649,793      192,535     0.00% (0 px)    37.54%   100.00%
  260708_316_H_b2_front_CBS_005     10,586,132      186,750     0.00% (0 px)    54.48%   100.00%
On _005 openbg_n4 removes 1,884,208 px from that 10,586,132 px component -- 17.8% of it --
without deleting a single hand-marked crack pixel and without even disconnecting it
(it is still one piece afterwards). texture veto and exclude_border_background removed
167,607 hand-marked px on _003 and 69,497 on _004; this removes none on either.

WHY IT STILL CANNOT BE A PRECISION RULE -- the structural reason, and it is new.
A CRACK THAT RUNS OUT OF THE FIELD OF VIEW IS, BY DEFINITION, NOT ENCLOSED. On
MAR_Amb_AS_ETD_0002 a single 123,653 px blob in the top-left corner is 99.6% hand-marked
crack (123,214 px) and has median enclosure 6/16, against 16/16 for the crack that is
kept. That one blob is 86% of all the damage the best floored arm does across 48 frames.
The repo's own perimeter-touch figure is 28.6% of crack regions, so enclosure is not
noisy for those regions -- it is UNDEFINED, because the specimen that would enclose them
is outside the frame. Enclosure therefore joins vesselness, raw darkness and perimeter
touch as a fourth overlapping discriminator, and now the overlap has a cause rather than
a coincidence: all four stop at the frame edge, which is where the evidence stops.
The area floor only works because it quietly encodes "a crack mouth is smaller than a
background flood", and at n=2 firings that is a guess, not a measurement.

SECONDARY -- the 26 tiles, through analysis/research/tilebench.py and nothing else.
A contextual rule cannot be scored from inside a 512 px crop (the crop edge is not the
specimen edge), so the enclosure field is computed on the WHOLE parent micrograph and
cropped to the tile box. Both readings are reported by `tiles()`; the parent one is the
quantity the rule uses.
  POSITIVE CONTROL, shipped v1.49 candidate mask, classifier off:
      P 0.4147  R 0.6321  IoU 0.3341  F1 0.5008   (documented: .4182/.6252/.3344/.5012)
  At every gate-safe rung -- openbg_n4, openbg_n4_A50k, ray16_n7, rayE_m20_t0.500 --
  the parent-context score is BIT-IDENTICAL to that. Zero change, four decimal places.
  Selecting the rung leave-one-SPECIMEN-out over the whole parent-context family:
      held-out  P 0.7482  R 0.6319  IoU 0.5211  F1 0.6852   overfit gap +0.0091
  which looks like +0.187 IoU -- and the rung it selects is rayE_m50_t1.000, which the
  gate above says deletes 42.85% of the hand-marked crack. The tile instrument ranks a
  rule that destroys 43% of the real crack as the best thing on offer. That is the fifth
  independent confirmation of the repo's structural point, not a result.
  AND THE TILE GAIN IS NOT ENCLOSURE-SPECIFIC. RANDAREA -- random pixels, handed the real
  arm's own per-tile deletion budget -- scores held-out IoU 0.4717 over its 4 variants,
  and arm for arm:
      openbg16_n10   real IoU 0.4745   area-matched random decoy 0.4722   (+0.0023)
      openbg_n6      real IoU 0.5131   area-matched random decoy 0.5098   (+0.0033)
      rayE_m20_t.875 real IoU 0.5244   area-matched random decoy 0.5190   (+0.0054)
  Almost all of the tile movement is the deletion BUDGET, not where it is spent. One
  tile -- the off-specimen void on MAR_H_HIP_CBS_0002 -- owns ~85% of all false positives,
  so any rule that deletes most of that tile wins the pooled score whatever it deletes.

SABOTAGE of the passing arm, field replaced by a misaligned copy of itself:
    real                 3,601,661 px removed   2,435 crack deleted (0.012%)
    flipped vertically   1,882,647 px removed       0 crack deleted
    rotated 180 degrees          0 px removed       0 crack deleted
The field is not interchangeable with a misaligned copy -- the 180-degree version finds
nothing at all -- so the measure is reading the frame and not an artefact of area. It is
reading it correctly about two blobs.

INSTRUMENT CONTROLS (`controls()`), all passing before any score was taken:
  * the shipped union with SCALE_LADDER collapsed to (40,) reproduces the single-scale
    cut exactly, and the full ladder is a strict superset of it
  * a dark disc inside specimen scores 8/8 and 16/16; a band on the bottom edge scores
    at most 3/8 and 7/16
  * the merged case -- disc and band as ONE component -- keeps the disc at 8/8 while the
    band stays at 3/8, and openbg16_n10 deletes 100% of the band and 0% of the disc.
    A region-level rule cannot produce that row, which is the whole argument in one test.
  * the decimated enclosure field (dec=4) against the exact one (dec=1) on a real frame:
    0.071-0.132% of candidates disagree, 13x faster. Everything above is dec=1, exact.

The candidate stage is the SHIPPED v1.49 multi-scale union, taken from
detector_overrides.install() itself rather than reimplemented. Nothing here writes to
sem-crack-detector; the paint masks are opened read-only. The size-floor sweep lives in
encl_sizefloor.py and shares this file's frame cache, arms and denominator.

Run:
    .../sem-crack-detector/.venv/bin/python -B enclosure.py cache    # candidate masks
    .../sem-crack-detector/.venv/bin/python -B enclosure.py gate     # the primary gate
    .../sem-crack-detector/.venv/bin/python -B enclosure.py counter  # the counterexample
    .../sem-crack-detector/.venv/bin/python -B enclosure.py tiles    # secondary
"""
import os, sys, json, time, warnings
warnings.filterwarnings("ignore")

SC = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
      "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
MY = os.path.join(SC, "encl")
os.environ.setdefault("MPLCONFIGDIR", MY + "/mpl")
APP = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
for p in (APP + "/analysis/research", APP + "/analysis", SEM + "/code",
          SEM + "/interior_active_learning/code"):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True

import numpy as np
from scipy import ndimage as ndi
from skimage import exposure, filters, morphology
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
import tifffile
import detect_cracks as D
from common import contrast_kwargs_for

PAINT = os.path.join(SEM, "interior_active_learning", "paint")
CACHE = os.path.join(MY, "cache")

# ------------------------------------------------------------------ shipped candidates
_SEG = {}


def shipped_seg(ladder=None):
    """The multi-scale union exactly as detector_overrides.install() builds it."""
    key = ladder
    if key not in _SEG:
        import detector_overrides as DO

        class _FakeUP:
            pass
        up = _FakeUP()
        kw = dict(use_multiscale_union=True)
        if ladder is not None:
            kw["scale_ladder"] = ladder
        DO.install(up, **kw)
        _SEG[key] = up.segment_dark_regions
    return _SEG[key]


def candidate_mask(img8, ladder=None, min_area=13):
    """The shipped candidate stage: multi-scale dark union -> clean_mask."""
    flat = D.flatten_background(img8, sigma=40)
    dark = shipped_seg(ladder)(flat, img8=img8, mad_k=5.0)
    return D.clean_mask(dark, open_radius=1, close_radius=3, min_area_px=min_area)


# ------------------------------------------------------------------ enclosure primitives
def _shift(a, dy, dx):
    """out[y,x] = a[y+dy, x+dx], zero outside."""
    out = np.zeros_like(a)
    H, W = a.shape
    if abs(dy) >= H or abs(dx) >= W:
        return out
    y0d, y1d = max(0, -dy), H - max(0, dy)
    x0d, x1d = max(0, -dx), W - max(0, dx)
    out[y0d:y1d, x0d:x1d] = a[y0d + dy:y1d + dy, x0d + dx:x1d + dx]
    return out


def ahead_count(spec, dy, dx, cap=255):
    """Number of `spec` pixels strictly ahead of each pixel along (dy,dx), to the border.

    Suffix sum by log-doubling: S_0(p) = spec[p+v], S_{k+1}(p) = S_k(p) + S_k(p + 2^k v).
    Saturated at `cap` so it fits uint8 -- every threshold used here is well under 255.
    """
    H, W = spec.shape
    acc = _shift(spec.astype(np.uint8), dy, dx)
    step = 1
    while step < max(H, W):
        acc = np.minimum(acc.astype(np.uint16) + _shift(acc, dy * step, dx * step),
                         cap).astype(np.uint8)
        step *= 2
    return acc


DIRS8 = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
#: 8 rays put the only rungs of the enclosure ladder at 4/8, 5/8, 6/8 -- and the gate
#: finds 5/8 safe (0.01% of crack) and 6/8 fatal (5.1%). Sixteen directions halve the
#: rung spacing so the ladder can be read where it actually turns. The eight extra are
#: knight steps, the shortest integer directions off the 45-degree lattice; a ray along
#: (1,2) advances sqrt(5) px per sample, so its specimen count is scaled by that step
#: length rather than compared to the same m as an axis ray.
DIRS16 = DIRS8 + [(1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)]


def enclosure_counts16(cand, ms, dec=1):
    """As enclosure_counts but over DIRS16, with each direction's threshold scaled by its
    step length so a diagonal or knight ray is not asked for more specimen than an axis
    ray. Returns counts out of 16."""
    H, W = cand.shape
    if dec > 1:
        h, w = H // dec, W // dec
        cnd = cand[:h * dec, :w * dec].reshape(h, dec, w, dec).mean(axis=(1, 3)) >= 0.5
    else:
        h, w, cnd = H, W, cand
    spec = ~cnd
    out = {m: np.zeros((h, w), np.uint8) for m in ms}
    for dy, dx in DIRS16:
        step = (dy * dy + dx * dx) ** 0.5
        a = ahead_count(spec, dy, dx)
        for m in ms:
            out[m] += (a >= max(1, int(round(m / dec / step)))).astype(np.uint8)
    if dec > 1:
        for m in ms:
            out[m] = np.repeat(np.repeat(out[m], dec, 0), dec, 1)
            if out[m].shape != (H, W):
                out[m] = np.pad(out[m], ((0, H - out[m].shape[0]),
                                         (0, W - out[m].shape[1])), mode="edge")
    return out


def enclosure_counts(cand, ms, dec=4):
    """{m: uint8 array, how many of 8 rays are blocked by >= m specimen px}.

    Computed on a `dec`-decimated copy and resampled back. Enclosure is a frame-scale
    layout property -- it has no structure finer than the regions it is about -- and the
    full-resolution suffix sums are 16x the work. dec=1 reproduces the exact version;
    `control_decimation()` measures the difference on a real frame instead of assuming it.
    """
    H, W = cand.shape
    if dec > 1:
        h, w = H // dec, W // dec
        sm = cand[:h * dec, :w * dec].reshape(h, dec, w, dec).mean(axis=(1, 3))
        cnd = sm >= 0.5
    else:
        h, w, cnd = H, W, cand
    spec = ~cnd
    out = {m: np.zeros((h, w), np.uint8) for m in ms}
    for dy, dx in DIRS8:
        a = ahead_count(spec, dy, dx)
        for m in ms:
            out[m] += (a >= max(1, int(round(m / dec)))).astype(np.uint8)
    if dec > 1:
        for m in ms:
            out[m] = np.repeat(np.repeat(out[m], dec, 0), dec, 1)
            if out[m].shape != (H, W):
                out[m] = np.pad(out[m], ((0, H - out[m].shape[0]), (0, W - out[m].shape[1])),
                                mode="edge")
    return out


def specimen_hull(cand):
    """B: convex hull of the largest connected non-candidate (specimen) component."""
    from skimage.morphology import convex_hull_image
    spec = ~cand
    lab, n = ndi.label(spec)
    if n == 0:
        return np.ones_like(cand)
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    big = lab == int(sizes.argmax())
    # hull on a decimated copy: a convex hull has no fine structure, and the full-res
    # call is O(H*W) with a large constant.
    d = 8
    h, w = big.shape[0] // d, big.shape[1] // d
    sm = big[:h * d, :w * d].reshape(h, d, w, d).mean(axis=(1, 3)) >= 0.5
    hull = convex_hull_image(sm) if sm.any() else np.ones_like(sm)
    up = np.repeat(np.repeat(hull, d, 0), d, 1)
    if up.shape != big.shape:
        up = np.pad(up, ((0, big.shape[0] - up.shape[0]), (0, big.shape[1] - up.shape[1])),
                    mode="edge")
    return up


def open_background(cand, e, need, min_area=0):
    """E: off-specimen background = the UNENCLOSED dark area that reaches the frame edge.

    This is the pixel-level form of `border_reachable`. That one deletes a whole candidate
    component if any of it touches the border, which is the naive reading of "enclosed"
    and is what the repo says destroys MAR_Amb_Cast_CBS_0005. Here the low-enclosure
    pixels are componented ON THEIR OWN, and only those blobs that reach the frame edge
    are deleted -- so a component that is background at one end and crack at the other
    loses the background end and keeps the crack end, which no region-level rule can do.
    """
    low = cand & (e < need)
    if not low.any():
        return np.zeros_like(cand)
    lab, n = ndi.label(low)
    edge = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    touch = set(np.unique(edge[edge > 0]).tolist())
    if min_area:
        sizes = np.bincount(lab.ravel(), minlength=n + 1)
        touch = {l for l in touch if sizes[l] >= min_area}
    if not touch:
        return np.zeros_like(cand)
    return np.isin(lab, sorted(touch))


def border_reachable(cand):
    """C (negative control): candidate components that touch the frame border."""
    lab, n = ndi.label(cand)
    if n == 0:
        return np.zeros_like(cand)
    edge = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    touch = np.unique(edge[edge > 0])
    return np.isin(lab, touch) if len(touch) else np.zeros_like(cand)


def local_spec_frac(cand, R):
    """D (negative control): fraction of a 2R+1 box around each pixel that is specimen."""
    return ndi.uniform_filter((~cand).astype(np.float32), size=2 * R + 1, mode="nearest")


# ------------------------------------------------------------------ the variant family
MS = (5, 20, 50)
TAUS = (0.500, 0.625, 0.750, 0.875, 1.000)
LOCAL_R = (50, 150)
LOCAL_TAUS = (0.25, 0.50)


REF = "rayE_m20_t0.875"     # the ray arm the decoys are matched to
REF2 = "openbg_n6"          # the open-background arm the decoys are matched to


def enclosure_variants(cand, E, seed=0):
    """Every arm that is a function of the candidate mask and an enclosure field.

    Split out from all_variants so the TILE run can hand in an enclosure field computed
    on the whole parent micrograph. A contextual rule scored from inside a 512 px crop is
    not the same rule, and this is the only way the two runs score the same arms.
    """
    out = {"keepall": cand}
    for m in MS:
        e = E[m]
        for tau in TAUS:
            need = int(np.ceil(tau * 8 - 1e-9))
            out[f"rayE_m{m}_t{tau:.3f}"] = cand & (e >= need)

    # E: unenclosed AND reaching the frame edge, componented at pixel level.
    for need in (4, 5, 6, 7, 8):
        for a in (0, 50000):
            bg = open_background(cand, E[20], need, min_area=a)
            out[f"openbg_n{need}" + (f"_A{a // 1000}k" if a else "")] = cand & ~bg

    # DECOYS. A rule that deletes area deletes crack; the question is whether enclosure
    # deletes crack LESS than an uninformative cut of the same size would.
    #   FLIP    the real enclosure field, flipped top-to-bottom before it is applied.
    #           Same values, same spatial coherence, wrong alignment.
    #   RANDAREA a random pixel subset keeping exactly the area the real arm keeps.
    need = int(np.ceil(0.875 * 8 - 1e-9))
    out[REF + "_FLIPDECOY"] = cand & (np.flipud(E[20]) >= need)
    out[REF + "_INVERT"] = cand & (E[20] < need)          # sabotage: keep the other half
    rng = np.random.default_rng(seed)
    ncand = int(cand.sum())
    for ref in (REF, REF2):
        nkeep = int(out[ref].sum())
        pick = np.zeros(ncand, bool)
        pick[:nkeep] = True
        rng.shuffle(pick)
        rm = np.zeros_like(cand)
        rm[cand] = pick
        out[ref + "_RANDAREA"] = rm
    # the openbg decoy: same construction on a vertically flipped enclosure field
    out[REF2 + "_FLIPDECOY"] = cand & ~open_background(cand, np.flipud(E[20]), 6)
    return out


def enclosure16_variants(cand, E16, seed=0):
    """The same two families read on the 16-direction ladder, m=20 only.

    m made no difference worth a column on the 8-ray ladder (5/20/50 moved the pooled
    deletion by less than a tenth of a point at every rung), so the finer ladder spends
    its variants on tau instead.
    """
    out = {}
    e = E16[20]
    for need in range(7, 17):
        out[f"ray16_n{need}"] = cand & (e >= need)
        out[f"openbg16_n{need}"] = cand & ~open_background(cand, e, need)
    rng = np.random.default_rng(seed + 1)
    ncand = int(cand.sum())
    for ref in ("ray16_n10", "openbg16_n10"):
        nkeep = int(out[ref].sum())
        pick = np.zeros(ncand, bool); pick[:nkeep] = True
        rng.shuffle(pick)
        rm = np.zeros_like(cand); rm[cand] = pick
        out[ref + "_RANDAREA"] = rm
    out["ray16_n10_FLIPDECOY"] = cand & (np.flipud(e) >= 10)
    out["openbg16_n10_FLIPDECOY"] = cand & ~open_background(cand, np.flipud(e), 10)
    return out


def all_variants(cand, dec=4, seed=0):
    """The full-frame arm set: the enclosure family plus the three negative controls."""
    E = enclosure_counts(cand, MS, dec=dec)
    out = enclosure_variants(cand, E, seed=seed)
    del E
    E16 = enclosure_counts16(cand, (20,), dec=dec)
    out.update(enclosure16_variants(cand, E16, seed=seed))
    del E16
    out["hull"] = cand & specimen_hull(cand)
    out["borderdrop"] = cand & ~border_reachable(cand)
    for R in LOCAL_R:
        f = local_spec_frac(cand, R)
        for tau in LOCAL_TAUS:
            out[f"localfrac_R{R}_t{tau:.2f}"] = cand & (f >= tau)
        del f
    return out


# ------------------------------------------------------------------ frames + paint
def frame_names():
    ns = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
                if f.endswith("_correction_mask.png"))
    return [n for n in ns if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]


def load_frame(name):
    raw = tifffile.imread(os.path.join(SEM, "original", name + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    ck = contrast_kwargs_for(name)
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]
    corr = np.array(Image.open(os.path.join(PAINT, name + "_correction_mask.png")))
    while corr.ndim > 2:
        corr = corr[..., 0]
    if corr.shape != img8.shape:
        if corr.shape[0] >= y1 and corr.shape[1] >= x1:
            corr = corr[y0:y1, x0:x1]
        else:
            return None
    return img8, corr


def build_cache():
    names = frame_names()
    print(f"{len(names)} frames carry both a micrograph and a correction mask", flush=True)
    t0 = time.time()
    for i, n in enumerate(names, 1):
        out = os.path.join(CACHE, n + ".npz")
        if os.path.exists(out):
            print(f"[{i}/{len(names)}] {n}  cached", flush=True)
            continue
        got = load_frame(n)
        if got is None:
            print(f"[{i}/{len(names)}] {n}  SKIP (paint does not fit the image)", flush=True)
            continue
        img8, corr = got
        cand = candidate_mask(img8)
        np.savez_compressed(out, cand=np.packbits(cand), corr=corr.astype(np.uint8),
                            shape=np.array(cand.shape))
        print(f"[{i}/{len(names)}] {n:<36} {cand.shape}  cand {cand.sum():>10,} px  "
              f"{time.time() - t0:5.0f}s", flush=True)
    print(f"cache built in {time.time() - t0:.0f}s")


def read_cache(n):
    z = np.load(os.path.join(CACHE, n + ".npz"))
    sh = tuple(z["shape"])
    cand = np.unpackbits(z["cand"])[:sh[0] * sh[1]].reshape(sh).astype(bool)
    return cand, z["corr"]


# ------------------------------------------------------------------ controls
def control_ladder40():
    """The shipped union with its ladder collapsed to (40,) must be the single-scale cut."""
    t = _one_tile()
    flat = D.flatten_background(t, sigma=40)
    a = shipped_seg((40,))(flat, img8=t, mad_k=5.0)
    smooth = filters.gaussian(flat, sigma=1.0, preserve_range=True)
    med = np.median(smooth); mad = np.median(np.abs(smooth - med)) * 1.4826
    b = (smooth < min(filters.threshold_otsu(smooth), med - 5.0 * mad)) | (t < 10)
    ok = np.array_equal(a, b)
    print(f"  {'PASS' if ok else 'FAIL'}  ladder=(40,) reproduces the single-scale cut")
    full = shipped_seg(None)(flat, img8=t, mad_k=5.0)
    sup = bool((full | b == full).all())
    print(f"  {'PASS' if sup else 'FAIL'}  full ladder is a strict superset "
          f"({int(b.sum()):,} -> {int(full.sum()):,} px)")
    return ok and sup


def control_enclosure():
    """Two synthetic frames whose enclosure answer is known before the code runs."""
    ok = True
    # (1) a dark disc in the middle of specimen: fully enclosed, E must be 8 everywhere.
    a = np.zeros((600, 600), bool)
    yy, xx = np.ogrid[:600, :600]
    a[(yy - 300) ** 2 + (xx - 300) ** 2 < 60 ** 2] = True
    e = enclosure_counts(a, (5,), dec=2)[5]
    g = e[a].min()
    print(f"  {'PASS' if g == 8 else 'FAIL'}  interior disc: min E over its pixels = {g}/8")
    ok &= g == 8
    # (2) a dark band filling the bottom third: off-specimen background, E must be < 8.
    b = np.zeros((600, 600), bool)
    b[400:, :] = True
    e = enclosure_counts(b, (5,), dec=2)[5]
    g = e[b].max()
    print(f"  {'PASS' if g <= 4 else 'FAIL'}  bottom-edge band: max E over its pixels = {g}/8")
    ok &= g <= 4
    # (3) the merged case: disc + band touching, ONE component. The disc must keep E=8
    #     and the band must stay low -- a region-level rule cannot do this.
    c = a | b
    e = enclosure_counts(c, (5,), dec=2)[5]
    gd, gb = e[a].min(), e[b].max()
    print(f"  {'PASS' if gd == 8 and gb <= 4 else 'FAIL'}  merged disc+band (one component): "
          f"disc min E = {gd}/8, band max E = {gb}/8")
    ok &= gd == 8 and gb <= 4
    # the same three on the 16-direction ladder
    e = enclosure_counts16(c, (20,), dec=1)[20]
    gd, gb = e[a].min(), e[b].max()
    print(f"  {'PASS' if gd == 16 and gb <= 8 else 'FAIL'}  merged, 16 directions: "
          f"disc min E = {gd}/16, band max E = {gb}/16")
    ok &= gd == 16 and gb <= 8
    # and the deletion the merged case is really about: a pixel-level rule must carve the
    # band out of the single component while leaving the disc whole.
    keep = c & ~open_background(c, e, 10)
    print(f"  {'PASS' if keep[a].all() and not keep[b].any() else 'FAIL'}  openbg16_n10 on "
          f"the merged component: disc kept {100 * keep[a].mean():.1f}%, "
          f"band kept {100 * keep[b].mean():.1f}%")
    ok &= bool(keep[a].all()) and not bool(keep[b].any())
    return ok


def control_decimation(name=None):
    """dec=4 against dec=1 on a real frame -- the shortcut, measured rather than assumed."""
    names = frame_names()
    n = name or names[0]
    cand, _ = read_cache(n)
    t0 = time.time()
    e1 = enclosure_counts(cand, (20,), dec=1)[20]
    t1 = time.time()
    e4 = enclosure_counts(cand, (20,), dec=4)[20]
    t4 = time.time()
    for tau in TAUS:
        need = int(np.ceil(tau * 8 - 1e-9))
        k1, k4 = cand & (e1 >= need), cand & (e4 >= need)
        dis = int((k1 ^ k4).sum()); tot = int(cand.sum())
        print(f"  tau={tau:.3f}  kept dec1 {int(k1.sum()):>10,}  dec4 {int(k4.sum()):>10,}"
              f"  disagree {dis:>9,} ({100 * dis / max(tot, 1):.3f}% of candidates)")
    print(f"  dec=1 {t1 - t0:.1f}s   dec=4 {t4 - t1:.1f}s   frame {cand.shape}  ({n})")


def _one_tile():
    import tilebench as TB
    return TB.load(with_raw=False)[0]["img8"]


def controls():
    print("INSTRUMENT CONTROLS", flush=True)
    ok = control_ladder40()
    ok &= control_enclosure()
    print("all controls passed" if ok else "CONTROLS FAILED -- do not trust any score")
    return ok


# ------------------------------------------------------------------ the primary gate
def gate(dec=4, limit=0, out=None):
    assert controls(), "controls failed"
    names = [n for n in frame_names() if os.path.exists(os.path.join(CACHE, n + ".npz"))]
    if limit:
        names = names[:limit]
    out = out or os.path.join(MY, "work", f"gate_dec{dec}.json")
    rows, t0 = [], time.time()
    for i, n in enumerate(names, 1):
        cand, corr = read_cache(n)
        crack, notc = corr == 1, (corr == 2) | (corr == 3)
        V = all_variants(cand, dec=dec)
        r = dict(frame=n, shape=list(cand.shape), painted_crack=int(crack.sum()),
                 painted_notc=int(notc.sum()), arms={})
        for k, m in V.items():
            r["arms"][k] = dict(area=int(m.sum()), crack=int((m & crack).sum()),
                                notc=int((m & notc).sum()))
        rows.append(r)
        a = r["arms"]
        kept = a["keepall"]["crack"]
        d = kept - a["rayE_m20_t0.875"]["crack"]
        print(f"[{i}/{len(names)}] {n:<36} painted {r['painted_crack']:>10,}  kept "
              f"{kept:>10,}  rayE(m20,t.875) deletes {d:>9,} "
              f"({100 * d / max(kept, 1):5.2f}%)  {time.time() - t0:5.0f}s", flush=True)
        json.dump(rows, open(out, "w"))
    json.dump(rows, open(out, "w"))
    print(f"\nwrote {out} in {time.time() - t0:.0f}s")
    return out


def report(path=None, dec=4):
    path = path or os.path.join(MY, "work", f"gate_dec{dec}.json")
    rows = json.load(open(path))
    keys = list(rows[0]["arms"])
    base = "keepall"
    print(f"\n=== PRIMARY GATE: {len(rows)} full frames, hand-painted correction masks ===")
    tot_crack = sum(r["arms"][base]["crack"] for r in rows)
    tot_notc = sum(r["arms"][base]["notc"] for r in rows)
    tot_area = sum(r["arms"][base]["area"] for r in rows)
    tot_painted = sum(r.get("painted_crack", 0) for r in rows)
    print(f"  hand-marked crack px on these frames : {tot_painted:,}")
    print(f"  of which the SHIPPED path keeps      : {tot_crack:,}   <- the denominator")
    print(f"  hand-marked not-crack px it also keeps: {tot_notc:,}")
    print(f"  total candidate area                  : {tot_area:,}\n")
    print(f"  {'arm':<24} {'crack deleted':>14} {'% of kept':>10} {'frames>1%':>10} "
          f"{'notc removed':>13} {'crack/notc':>11} {'area kept':>14}")
    res = []
    for k in keys:
        if k == base:
            continue
        dc = tot_crack - sum(r["arms"][k]["crack"] for r in rows)
        dn = tot_notc - sum(r["arms"][k]["notc"] for r in rows)
        ar = sum(r["arms"][k]["area"] for r in rows)
        nbad = sum(1 for r in rows
                   if r["arms"][base]["crack"] > 0
                   and (r["arms"][base]["crack"] - r["arms"][k]["crack"])
                   / r["arms"][base]["crack"] > 0.01)
        pct = 100 * dc / max(tot_crack, 1)
        res.append((k, dc, pct, nbad, dn, ar))
    for k, dc, pct, nbad, dn, ar in sorted(res, key=lambda z: z[2]):
        ratio = dc / dn if dn > 0 else float("inf")
        flag = "  PASS" if pct < 1.0 and nbad == 0 else ("  pass*" if pct < 1.0 else "")
        print(f"  {k:<24} {dc:>14,} {pct:>9.2f}% {nbad:>10} {dn:>13,} "
              f"{ratio:>11.2f} {ar:>14,}{flag}")
    print("\n  PASS = deletes <1% of kept hand-marked crack AND no single frame loses >1%.")
    print("  'crack/notc' is hand-marked crack px destroyed per hand-marked not-crack px")
    print("  removed; the four dead rules sat at 87, and the shipped classifier at 5.9.")
    return rows


def worst_frames(path=None, arm="rayE_m20_t0.875", dec=4, n=12):
    path = path or os.path.join(MY, "work", f"gate_dec{dec}.json")
    rows = json.load(open(path))
    out = []
    for r in rows:
        k = r["arms"]["keepall"]["crack"]
        d = k - r["arms"][arm]["crack"]
        out.append((100 * d / max(k, 1), d, k, r["arms"]["keepall"]["notc"]
                    - r["arms"][arm]["notc"], r["frame"]))
    print(f"\n=== per-frame, arm {arm} ===")
    print(f"  {'% kept crack deleted':>20} {'deleted':>12} {'kept':>12} "
          f"{'notc removed':>13}  frame")
    for p, d, k, dn, f in sorted(out, reverse=True)[:n]:
        print(f"  {p:>19.2f}% {d:>12,} {k:>12,} {dn:>13,}  {f}")
    return out


# ------------------------------------------------------------------ secondary: tiles
#
# A contextual rule cannot be scored from inside a 512 px crop: the crop edge is not the
# specimen edge, so enclosure measured within a tile is a different quantity from the one
# the rule actually uses. Both are reported.
#   TILE-LOCAL   enclosure from the tile's own 512 px candidate mask -- what a tile-only
#                harness would compute, and it is wrong by construction.
#   PARENT       enclosure computed on the whole parent micrograph, then cropped to the
#                tile box. This is the quantity the rule uses in deployment.
PARENTC = os.path.join(MY, "parent")


def parent_cand(parent):
    """The shipped candidate mask over a WHOLE parent micrograph, cached.

    The parent is loaded the way tilebench.build_cache loads it -- databar trimmed to the
    machine mask's height -- so a tile's `box` indexes it directly. Only the mask is
    cached; the enclosure fields are seconds to recompute and keeping them on disk would
    pin the ladder to whatever was cached first.
    """
    os.makedirs(PARENTC, exist_ok=True)
    out = os.path.join(PARENTC, parent + "_cand.npz")
    if os.path.exists(out):
        z = np.load(out)
        sh = tuple(z["shape"])
        return np.unpackbits(z["cand"])[:sh[0] * sh[1]].reshape(sh).astype(bool)
    orig = os.path.join(SEM, "original")
    mach = os.path.join(SEM, "crack_export", "derived", "machine_masks")
    src = next(os.path.join(orig, parent + e) for e in (".tif", ".tiff", ".png")
               if os.path.exists(os.path.join(orig, parent + e)))
    mh, mw = np.array(Image.open(os.path.join(mach, parent + "_machine.png"))).shape
    a = tifffile.imread(src)
    if a.ndim == 3:
        a = a[..., 0]
    if a.shape[1] == mw and a.shape[0] > mh:
        a = a[:mh, :]
    ck = contrast_kwargs_for(parent)
    lo, hi = np.percentile(a, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(a.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    cand = candidate_mask(img8)
    np.savez_compressed(out, cand=np.packbits(cand), shape=np.array(cand.shape))
    return cand


def _crop_like(e, shape, box):
    x, y, w, h = box
    c = e[y:y + h, x:x + w]
    if c.shape != shape:
        c = np.pad(c, ((0, shape[0] - c.shape[0]), (0, shape[1] - c.shape[1])),
                   mode="edge")
    return c


def tiles():
    """SECONDARY: the 26 hand-labelled tiles, through tilebench and nothing else."""
    import tilebench as TB
    ts = TB.load(with_raw=False)
    print(f"{len(ts)} tiles, {len({t['specimen'] for t in ts})} specimens, "
          f"{len({t['parent'] for t in ts})} parent micrographs", flush=True)

    # POSITIVE CONTROL: with the region classifier off the shipped prediction IS the
    # candidate mask, so this must reproduce the shipped P 0.4182 R 0.6252 IoU 0.3344.
    cands = [candidate_mask(t["img8"]) for t in ts]
    TB.evaluate("CONTROL shipped v1.49 candidate mask (classifier off) -- must be "
                "P 0.4182 R 0.6252 IoU 0.3344 F1 0.5012",
                {"shipped": [TB.counts(c, t["gt"]) for c, t in zip(cands, ts)]})

    def build(fields8, fields16):
        per = {}
        for i, (t, c) in enumerate(zip(ts, cands)):
            V = enclosure_variants(c, fields8[i], seed=i)
            V.update(enclosure16_variants(c, fields16[i], seed=i))
            for k, m in V.items():
                per.setdefault(k, []).append(TB.counts(m, t["gt"]))
        return per

    # A: enclosure measured inside the 512 px crop. WRONG by construction -- the crop
    #    edge is not the specimen edge -- and reported so the difference is visible.
    a = build([enclosure_counts(c, MS, dec=1) for c in cands],
              [enclosure_counts16(c, (20,), dec=1) for c in cands])

    # B: enclosure measured on the WHOLE parent micrograph, then cropped to the tile box.
    #    This is the quantity the rule uses when it runs.
    f8, f16, pc = [], [], {}
    for t, c in zip(ts, cands):
        p = t["parent"]
        if p not in pc:
            pcand = parent_cand(p)
            pc[p] = (enclosure_counts(pcand, MS, dec=1),
                     enclosure_counts16(pcand, (20,), dec=1))
            print(f"  parent context: {p} {pcand.shape}", flush=True)
        E8, E16 = pc[p]
        f8.append({m: _crop_like(E8[m], c.shape, t["box"]) for m in MS})
        f16.append({20: _crop_like(E16[20], c.shape, t["box"])})
    b = build(f8, f16)
    return a, b


def tile_summary(a, b):
    """One table, held-out only, so the two context definitions sit side by side.

    Every arm here is a single variant, so tilebench's fitted and held-out numbers agree
    by construction and the overfit gap is 0.0000 -- there is no parameter being selected
    INSIDE a fold. The real selection is across the rows of this table, and that is done
    on the full-frame gate, not here.
    """
    import tilebench as TB
    print("\n=== SECONDARY: 26 tiles, leave-one-SPECIMEN-out (held-out) ===")
    print(f"  {'arm':<26} {'P':>7} {'R':>7} {'IoU':>7} {'F1':>7} |"
          f" {'P':>7} {'R':>7} {'IoU':>7} {'F1':>7}")
    print(f"  {'':<26} {'------ tile-local ------':^31} |"
          f" {'---- parent context ----':^31}")
    order = [k for k in ("keepall",) if k in a] + sorted(k for k in set(a) | set(b)
                                                         if k != "keepall")
    for k in order:
        row = f"  {k:<26}"
        for i, d in enumerate((a, b)):
            if k in d:
                m = TB.evaluate(k, {k: d[k]}, quiet=True)["loso"]
                row += (f" {m['precision']:7.4f} {m['recall']:7.4f} {m['iou']:7.4f} "
                        f"{m['f1']:7.4f}")
            else:
                row += " " * 32
            if i == 0:
                row += " |"
        print(row)


# ------------------------------------------------------------------ the counterexample
#
# unified_pipeline.py names the frame that kills every region-level rule:
#   "on MAR_Amb_Cast_CBS_0005 the background region and the crack are ONE connected
#    component containing 976,295 hand-marked crack pixels, so no region-level exclusion
#    can drop it without destroying human labels."
# A pixel-level rule is allowed to carve that component; it is not allowed to take the
# crack with it. This checks the claim on the real data rather than quoting the comment.
NAMED = ("MAR_Amb_Cast_CBS_0005",
         "260708_316_H_b2_front_CBS_003",
         "260708_316_H_b2_front_CBS_004",
         "260708_316_H_b2_front_CBS_005")


def counterexample(names=NAMED, arms=("openbg_n4", "openbg_n5", "rayE_m20_t0.500",
                                      "rayE_m20_t0.625", "borderdrop", "hull"), dec=1):
    for n in names:
        f = os.path.join(CACHE, n + ".npz")
        if not os.path.exists(f):
            print(f"\n{n}: NO CACHE"); continue
        cand, corr = read_cache(n)
        crack, notc = corr == 1, (corr == 2) | (corr == 3)
        lab, nc = ndi.label(cand)
        # the component holding the most hand-marked crack
        sz = np.bincount(lab[crack].ravel(), minlength=nc + 1); sz[0] = 0
        top = int(sz.argmax())
        comp = lab == top
        edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0],
                                             lab[:, -1]])).tolist())
        print(f"\n=== {n}  {cand.shape} ===")
        print(f"  candidate components {nc:,}; the one holding the most hand paint holds "
              f"{sz[top]:,} marked crack px over {int(comp.sum()):,} px, "
              f"{'TOUCHES' if top in edge else 'does not touch'} the frame border")
        print(f"  {'arm':<20} {'comp crack kept':>16} {'deleted':>10} {'%':>7} "
              f"{'comp px kept':>13} {'pieces':>7} {'frame notc removed':>19}")
        V = all_variants(cand, dec=dec)
        base = int((V["keepall"] & comp & crack).sum())
        bnot = int((V["keepall"] & notc).sum())
        for k in ("keepall",) + arms:
            m = V[k]
            kept = int((m & comp & crack).sum())
            pieces = int(ndi.label(m & comp)[1])
            print(f"  {k:<20} {kept:>16,} {base - kept:>10,} "
                  f"{100 * (base - kept) / max(base, 1):>6.2f}% "
                  f"{int((m & comp).sum()):>13,} {pieces:>7} "
                  f"{bnot - int((m & notc).sum()):>19,}")


def per_specimen(path=None, arms=("openbg16_n9", "openbg16_n10", "openbg_n4"), dec=1):
    """Damage concentration by specimen: a pooled 1% can hide one destroyed specimen."""
    path = path or os.path.join(MY, "work", f"gate_dec{dec}.json")
    rows = json.load(open(path))
    import re
    def spec(f):
        return re.sub(r"_(CBS|ETD|BSE|SE)?_?\d+$", "", f)
    g = {}
    for r in rows:
        s = spec(r["frame"])
        d = g.setdefault(s, {"n": 0, "kept": 0, **{a: 0 for a in arms}})
        d["n"] += 1
        d["kept"] += r["arms"]["keepall"]["crack"]
        for a in arms:
            d[a] += r["arms"][a]["crack"]
    print(f"\n=== damage by specimen group ===")
    print(f"  {'specimen':<34} {'n':>3} {'kept crack':>13} " +
          " ".join(f"{a:>16}" for a in arms))
    for s in sorted(g):
        d = g[s]
        row = f"  {s:<34} {d['n']:>3} {d['kept']:>13,} "
        for a in arms:
            pct = 100 * (d["kept"] - d[a]) / max(d["kept"], 1)
            row += f"{pct:>15.2f}% "
        print(row)


def blob_census(need=4, floor=200_000, dec=1):
    """Exactly what the `openbg` arm deletes, blob by blob, over all 48 frames.

    A pooled "5.2% of candidate area removed" reads like a rule. This prints the blobs
    it is made of, with the hand verdict on each, so a rule that fires twice is visible
    as a rule that fires twice.
    """
    rows = []
    for n in frame_names():
        if not os.path.exists(os.path.join(CACHE, n + ".npz")):
            continue
        cand, corr = read_cache(n)
        crack, notc = corr == 1, (corr == 2) | (corr == 3)
        e = enclosure_counts(cand, (20,), dec=dec)[20]
        low = cand & (e < need)
        if not low.any():
            continue
        lab, nl = ndi.label(low)
        edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0],
                                             lab[:, -1]])).tolist()) - {0}
        sz = np.bincount(lab.ravel(), minlength=nl + 1)
        for l in sorted(edge):
            if sz[l] >= floor:
                m = lab == l
                rows.append((int(sz[l]), int((m & crack).sum()), int((m & notc).sum()), n))
    rows.sort(reverse=True)
    print(f"\n=== blobs openbg_n{need} would delete, >= {floor:,} px ===")
    print(f"  {'blob px':>12} {'hand crack in it':>17} {'hand not-crack':>15}  frame")
    for s_, c, nc, n in rows:
        print(f"  {s_:>12,} {c:>17,} {nc:>15,}  {n}")
    print(f"  {len(rows)} border-reaching unenclosed blobs across the corpus")
    for thr in (floor, 500_000, 1_000_000, 2_000_000):
        sel = [r for r in rows if r[0] >= thr]
        print(f"    floor {thr:>9,}: {len(sel):>2} blobs, {sum(r[0] for r in sel):>11,} px, "
              f"{sum(r[1] for r in sel):>9,} hand crack, {sum(r[2] for r in sel):>7,} "
              f"hand not-crack")
    return rows


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "controls"
    dec = int(os.environ.get("DEC", "1"))
    if cmd == "cache":
        build_cache()
    elif cmd == "controls":
        controls()
    elif cmd == "decim":
        control_decimation(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "gate":
        gate(dec=dec, limit=int(os.environ.get("NFRAMES", "0")))
        report(dec=dec)
    elif cmd == "report":
        report(dec=dec)
        worst_frames(dec=dec)
    elif cmd == "tiles":
        a, b = tiles()
        import pickle
        pickle.dump((a, b), open(MY + "/work/tiles.pkl", "wb"))
        tile_summary(a, b)
    elif cmd == "tilesummary":
        import pickle
        tile_summary(*pickle.load(open(MY + "/work/tiles.pkl", "rb")))
    elif cmd == "census":
        blob_census()
    elif cmd == "counter":
        counterexample(dec=dec)
    else:
        raise SystemExit(f"unknown command {cmd}")
