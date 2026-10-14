"""Stage 1b: WHICH flattening radius sees which pixel, for the v1.49.2 darkness cut.

`sem_production.py` writes the production stages end to end but keeps the seven-radius
union as one array. Figure 1's union panel has to answer a narrower question -- why is one
radius not enough -- so it needs the union decomposed by the rung that supplies each pixel.
That decomposition is computed here and nowhere else, because the plate maker draws and
does not compute.

NOTHING HERE REIMPLEMENTS THE UNION. Every rung is obtained by asking
`detector_overrides.install()` for a ladder of exactly one radius, through
`angle4_shipped.seg_fn(ladder=(sigma,))`, so each rung is the production function with its
ladder shortened and cannot drift from the app. Two controls run before anything is
written and both are hard assertions:

  * ladder collapse -- `seg_fn(ladder=(40,))` must reproduce `detect_cracks`'
    stock single-radius cut bit for bit (this is `angle4_shipped.selfcheck`);
  * partition -- the OR over the seven one-rung ladders must equal the seven-rung ladder
    run in one call, pixel for pixel. If it does not, the attribution below is fiction.

THE ATTRIBUTION, and its one honest wrinkle. Every rung's return value is
`cut_at_sigma OR (img8 < absolute_dark_thresh)`: the absolute-darkness term is OR-ed in by
`segment_dark_regions` itself at every radius, so a pixel dark enough for that term is
returned by all seven rungs and belongs to none of them. Those pixels are therefore given
their own class and the remaining pixels are labelled by the SMALLEST radius that marks
them. The classes are disjoint and exhaust the union, which is asserted.

    semr_rung.npy   uint8 on the drawn window: 0 = not dark, 1..7 = first ladder rung
                    (ascending sigma) that marks the pixel, 8 = supplied by the absolute
                    DN < absolute_dark_thresh term, which every rung carries
    semr_single.npy bool, the stock single-radius (sigma = 40) cut, uncleaned
    semr_union.npy  bool, the seven-rung union, uncleaned
    sem_rungs.json  the counts, frame-wide and on the window

No absolute paths; see `_paths.py`.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths

S = _paths.require(_paths.SEM_REPO, "the sem-crack-detector checkout", "SEM_REPO")
A = _paths.require(os.path.join(_paths.REPO, "analysis"), "this repo's analysis/ directory",
                   "(it is part of crack-fractography)")
os.environ.setdefault("SEMCRACK_ORIGINAL_DIR", os.path.join(S, "original"))
os.environ.setdefault("SEM_REPO", S)
os.environ.setdefault("APP_REPO", _paths.REPO)
for p in (os.path.join(A, "research", "improve"), A,
          os.path.join(S, "interior_active_learning", "code"), os.path.join(S, "code")):
    sys.path.insert(0, p)

import json, time
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

import detect_cracks as D
import angle4_shipped as A4
import detector_overrides as DO
import common

OUT = _paths.FIG_CACHE
FRAME, X0, Y0, SIDE = "MAR_H_AS_CBS_0004", 400, 1600, 1200
MAD_K = 5.0
t0 = time.time()


def tick(m):
    print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)


# ---------------------------------------------------------------- production load
img8_full = D.load_as_uint8(os.path.join(common.ORIGINAL_DIR, f"{FRAME}.tif"),
                            **common.contrast_kwargs_for(FRAME))
fx0, fy0, fx1, fy1 = D.find_field_of_view(img8_full)
img8 = img8_full[fy0:fy1, fx0:fx1]
tick(f"loaded {img8_full.shape} -> field of view {img8.shape}")

A4.selfcheck([img8[Y0:Y0+SIDE, X0:X0+SIDE]])
tick("control 1: ladder collapse")

flat = D.flatten_background(img8, sigma=40)
tick("flatten_background sigma=40")

LADDER = tuple(DO.SCALE_LADDER)
rungs = {}
for sigma in LADDER:
    rungs[sigma] = A4.seg_fn(ladder=(sigma,))(flat, img8=img8, mad_k=MAD_K)
    tick(f"rung sigma={sigma:>3}: {100*rungs[sigma].mean():6.3f}% dark")

union_one_call = A4.seg_fn()(flat, img8=img8, mad_k=MAD_K)
union_or = np.zeros_like(union_one_call)
for sigma in LADDER:
    union_or |= rungs[sigma]
assert np.array_equal(union_or, union_one_call), (
    "the OR over one-rung ladders is not the seven-rung ladder; the attribution is fiction")
tick("control 2: partition == the seven-rung union, pixel for pixel")

single = D.segment_dark_regions(flat, mad_k=MAD_K, img8=img8)
assert np.array_equal(single, rungs[40]), "sigma=40 rung is not the stock cut"
assert bool((union_one_call | single == union_one_call).all()), (
    "the union is not a superset of the single-radius cut")
tick(f"single radius {100*single.mean():.3f}%  union {100*union_one_call.mean():.3f}%")

# ---------------------------------------------------------------- attribution
absolute = img8 < DO.ABSOLUTE_DARK_THRESH          # the term every rung OR-s in
rung = np.zeros(img8.shape, np.uint8)
assigned = absolute.copy()
rung[absolute] = 8
for k, sigma in enumerate(LADDER, start=1):
    new = rungs[sigma] & ~assigned
    rung[new] = k
    assigned |= new
assert np.array_equal(assigned, union_one_call), "the classes do not exhaust the union"
assert not (rung.astype(bool) ^ union_one_call).any(), "class 0 is not exactly the non-union"
tick("attribution: classes disjoint and exhaustive")

sl = (slice(Y0, Y0+SIDE), slice(X0, X0+SIDE))
np.save(os.path.join(OUT, "semr_rung.npy"), rung[sl])
np.save(os.path.join(OUT, "semr_single.npy"), single[sl])
np.save(os.path.join(OUT, "semr_union.npy"), union_one_call[sl])

NAMES = [f"sigma {s}" for s in LADDER] + [f"absolute DN < {DO.ABSOLUTE_DARK_THRESH}"]
frame_px = int(img8.size)
crop_px = SIDE * SIDE
rec = dict(
    version="v1.49.2", frame=FRAME, crop=[X0, Y0, SIDE],
    full=[int(img8.shape[1]), int(img8.shape[0])],
    ladder=list(LADDER), mad_k=MAD_K,
    absolute_dark_thresh=int(DO.ABSOLUTE_DARK_THRESH),
    decimate_above_sigma=int(DO.DECIMATE_ABOVE_SIGMA),
    class_names=NAMES,
    controls=dict(
        ladder_collapse="PASS: seg_fn(ladder=(40,)) == detect_cracks.segment_dark_regions",
        partition="PASS: OR over the seven one-rung ladders == the seven-rung union"),
    frame_px=frame_px, crop_px=crop_px,
    # The drawn window as a share of the frame. The captions quoted 2.5 % for several
    # revisions; 1200^2 of 6144x4096 is 5.72 %, and the plate may not compute it itself.
    crop_frac_pct=100 * crop_px / frame_px,
    frame_single_pct=100 * float(single.mean()),
    frame_union_pct=100 * float(union_one_call.mean()),
    crop_single_pct=100 * float(single[sl].mean()),
    crop_union_pct=100 * float(union_one_call[sl].mean()),
    # DISJOINT: each pixel counted once, under the first rung that marks it.
    frame_first_seen_px={n: int((rung == i).sum())
                         for i, n in enumerate(NAMES, start=1)},
    crop_first_seen_px={n: int((rung[sl] == i).sum())
                        for i, n in enumerate(NAMES, start=1)},
    # NOT disjoint: how much each rung marks in total, absolute term included, which is
    # what that rung would propose on its own.
    frame_rung_total_px={f"sigma {s}": int(rungs[s].sum()) for s in LADDER},
    frame_absolute_px=int(absolute.sum()),
    # WHAT THE SIX OTHER RADII BUY OVER THE SINGLE RADIUS THAT SHIPPED BEFORE, which is the
    # quantity the union panel draws. The stock cut already OR-s the absolute-darkness term
    # in, so every added pixel is supplied by a rung other than sigma = 40 and the two
    # dictionaries below can contain neither "sigma 40" nor the absolute class -- asserted.
    frame_added_by_radius_px={n: int(((rung == i) & ~single).sum())
                              for i, n in enumerate(NAMES, start=1)},
    crop_added_by_radius_px={n: int(((rung[sl] == i) & ~single[sl]).sum())
                             for i, n in enumerate(NAMES, start=1)},
    frame_added_over_single_px=int((union_one_call & ~single).sum()),
    frame_added_over_single_pp=100 * float((union_one_call & ~single).mean()),
    crop_added_over_single_px=int((union_one_call[sl] & ~single[sl]).sum()),
    crop_added_over_single_pp=100 * float((union_one_call[sl] & ~single[sl]).mean()),
    seconds=round(time.time() - t0, 1))
for _k in (f"sigma {40}", f"absolute DN < {DO.ABSOLUTE_DARK_THRESH}"):
    assert rec["frame_added_by_radius_px"][_k] == 0, (
        f"{_k} cannot ADD anything over the stock cut, which already contains it")
    assert rec["crop_added_by_radius_px"][_k] == 0, _k
assert sum(rec["frame_added_by_radius_px"].values()) == rec["frame_added_over_single_px"]
assert sum(rec["crop_added_by_radius_px"].values()) == rec["crop_added_over_single_px"]
assert sum(rec["frame_first_seen_px"].values()) == int(union_one_call.sum())
tick("control 3: the added-pixel breakdown sums to the union's own excess")
print(json.dumps(rec, indent=1))
json.dump(rec, open(os.path.join(OUT, "sem_rungs.json"), "w"), indent=1)
tick("done")
