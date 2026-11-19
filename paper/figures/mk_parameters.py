"""Figure 6: every constant of BOTH detectors, what it is set to, and how it was fixed.

WHAT THE PLATE IS. Per arm: a row of sweep panels over a printed table. Nine panels,
because eleven of the fifty constants have evidence worth plotting; fifty
table rows, because that is how many constants the two detectors read once the
swept ones carry their curve. A constant with a panel
names its letter in its row.

WHY IT WAS REDRAWN, FOUR TIMES, AND WHERE THIS ONE CAME FROM. The first edition was six
curves in a two-by-three grid and left the TXM arm out entirely. The second was
wordless by request: nine panels over loose name/value strips, twenty-one constants of
fifty. The third carried them all in a ruled block with colour swatches. The fourth
made the constants into stage boxes joined by arrows. Every one of those was built from
a description of what a scientific figure ought to look like, and every one was
rejected.

This edition is built from two REAL PUBLISHED FIGURES of this kind, opened and
measured; what they do is written down, with their citations, in
docs/FIGURE_CONVENTIONS_FROM_PUBLISHED_WORK.md. Two things follow from them and they
are the whole of this revision:

  * A DATA PANEL IN THESE JOURNALS CARRIES A FULL AXIS TITLE WITH ITS UNIT AND SEVERAL
    NUMERIC TICK LABELS on each axis, and its letter is lowercase, bold and inside the
    axes at the top left. Earlier editions had no y tick labels at all and set the x
    ends as loose figure text beside an axes whose ticks were switched off. That is a
    sparkline, and a sparkline with no scale is a shape rather than a measurement.
  * AN INVENTORY OF SETTINGS IS A TABLE, and in these journals a table is plain: a top
    rule, a header, a header rule, the rows, a bottom rule. No boxes, no arrows, no
    colour, no legend. How each value was settled is ONE LETTER in its own narrow
    column with a single footnote under the plate, which is the ordinary way a printed
    table carries a flag. Three editions tried to make the inventory into artwork and
    each one read as a figure that had been filled with words.

WHAT IS ON THE PLATE IS UNCHANGED. The content was never what was wrong: the same nine
sweeps and the same fifty constants, including the eight settings the SEM chain applies
before the detector runs -- a contrast window with a three-frame exception, a databar
probe, a field-of-view finder -- and the twelve the TXM mask path applies after it, a
nine-constant width clip and a three-constant straight-artefact rejector that
`_narrow_to_image` runs on every exported mask. A constant applied to the data and not
declared is an undeclared degree of freedom.

HOW EACH CONSTANT WAS FIXED IS THE ref. COLUMN, AND THAT IS THE RESULT.
The SEM MAD multiplier was once the single constant with a sweep behind it, and that
sweep was run on a public collection since removed from this paper at the author's
instruction; the value in use is unchanged and the sweep behind it is now this
laboratory's own, not the removed collection's. Of the fifty: NINETEEN are swept here,
of which seven carry no panel and state their finding in WHY_THE_SWEPT_VALUE_STANDS
instead; FIVE were settled by a test that had no value to choose -- on or off, which
members; EIGHT were selected from a measurement recorded in the source repository but
are not drawn, and the caption file quotes each measurement in full; EIGHTEEN are fixed
by construction or set by hand with nothing measured about them anywhere. Nine of the
swept rows were taken from archived code with no recorded provenance, so their panels
show SENSITIVITY, not selection, and where the shipped value is not the best value on
the instrument the marker simply sits off the peak.

THE LADDER'S TWO ROWS JOINED THE SWEPT ONES AND THE VALUE DID NOT CHANGE. They read F
until docs/figures/ladder_endpoints.json and ladder_endpoints_frames.json existed, on
the honest grounds that no sweep over alternative ladders had ever been run. One has
now been run -- 58 ladders over base, top and step on the 26 tiles, and six of them on
14 full frames against the paint -- so the F claim became false and the letter moved.
What the sweep found is that the ladder's TOP is unrankable on tiles (sigma=2560 moves
307 px in 6,815,744 there, because a 512 px tile cannot hold a background estimate that
large) and that the tile preference for dropping sigma=5 is WRONG at frame scale, where
it loses 64,728 px of painted crack and is worse on 12 of 14 frames. The shipped ladder
stands; what changed is that there is now evidence behind it. Panel (e) still draws the
single-radius curve, which is the part of the question a tile can answer.

THE M LETTER EXISTS BECAUSE F WAS BEING USED FOR TWO DIFFERENT THINGS and only said one
of them. F asserts that no measurement of a constant exists in either repository. Eight
rows carrying it had one: the TXM hole fill was swept over all 71 frames at three caps,
the speck floor by leave-one-image-out IoU, the tile stride, narrowing window, narrowing
core, correction floor, clip peak sigma and straight-artefact wander cut each by a
measurement written above the constant in its own source file. What they share is not an
absence of evidence but an absence of a PANEL -- they act after the threshold rather
than on the model, so none was drawn -- and every row without a panel had been given F.
This edition's own sidecar gave the game away: it filed five of them under a key named
`txm_fixed_from_its_own_measurements` while the plate lettered them "no measurement
exists". Nothing in either pipeline changed here; the column was made true about
constants that are exactly where they were. The width clip moved to T instead, because
it is an on/off decision with a verdict and no optimum, like the multiscale union and
the region classifier beside it.

THREE OF THOSE NINE WERE SWEPT FOR THE FIRST TIME IN THIS REVISION, because the author's
standing objection was that the plate did not show how each setting was chosen and for
most of them the honest answer was that nothing had ever been measured. The closing
radius, the denoise sigma and the flattening radius can all be swept on the SAME 26
tiles and the SAME scorer as the rest, so they were, and the shipped value is not the
best on its own grid for either of the first two. Panel (f) also gives the seven-rung
ladder the evidence it never had, by scoring one radius at a time against the union.

NO IoU IS QUOTED IN THIS DOCSTRING, DELIBERATELY. An earlier revision wrote the numbers
out here, the region classifier was then switched on, every one of them moved, and the
prose went on asserting the old values with nothing to catch it. The figures, the
printed controls and the caption file all read the current record; a docstring cannot,
so it no longer pretends to. Drawing fifty selection curves would be
fiction, and a reviewer who spots one fabricated optimum stops reading. The key at the
foot says which kind each swatch is.

PANEL (f) AGAINST PANEL (i) IS THE ONE CROSS-PANEL COMPARISON THE PLATE MAKES, and it is
safe only because it was made safe: both are the same 31 TXM frames and the same
refereed pixels, asserted against the record rather than assumed. The TXM model clears
the do-nothing baseline at every threshold above 0.47; the SEM detector's one swept
constant, carried onto the same frames, never clears it at any k. They are not drawn on
one axis: on a shared accuracy axis the TXM model's 2.8 point margin and the SEM rule's
9.5 point shortfall are each under a point of ink, so both curves sit ON the baseline
and a reader cannot see which side either is on. (f) shows the two rates the threshold
was decided on and (i) shows the margin itself, hanging below zero.

AND THE TWO ARE NOT ON EQUAL TERMS. The TXM members were fitted on this very paint, so
(f) is IN-SAMPLE; the SEM rule was fitted to nothing at all. The asymmetry runs in the
trained model's favour, so the pair is evidence that the darkness rule does not transfer
-- which is why the TXM arm has a trained model -- and is NOT a measurement of how much
better the trained model is.

WHAT IS COMPUTED VERSUS READ. Everything on the SEM side is computed by calling the
SHIPPED code: the darkness cut is detector_overrides.install()'s own segment_dark_regions,
the per-rung decomposition is fullframe_recall_decomposition.rung_maps, and the cleaning
chain is detect_cracks.clean_mask exactly as both_modalities.stages runs it. The TXM
threshold sweep is computed here from the deployed model's own cached probability maps.
Every constant quoted in the table is PARSED out of the deployed source with ast --
never retyped, and never matched with a regular expression, which would hit the
constant's name inside the prose that explains it. `_sem_constants` reads the SEM
stages' defaulted arguments and `_txm_constants` the TXM modules' module-level literals;
either aborts on a name that is no longer there, rather than letting a row quote a value
the code has stopped using.

SEVEN CONTROLS RUN BEFORE ANYTHING IS DRAWN, AND EVERY ONE ABORTS RATHER THAN WARNS:

  * the rung union OR the absolute term must BE the installed detector's own output,
    pixel for pixel, on the first frame of the corpus pass;
  * (k_max > k) OR the absolute term must reproduce that same mask;
  * the tile chain used for the sweeps in (c)-(e) must reproduce both_modalities.stages'
    final mask on every one of the 26 tiles at the shipped settings;
  * tilebench's own three controls -- a perfect predictor scores 1.0, an empty one 0.0,
    and mark-everything scores precision == prevalence;
  * the TXM pass must recover txm_background_units.json's own frame count and both of
    its refereed pixel counts, group by group, or rows (g) and (j) would be two
    different pixel sets drawn as if they were one;
  * every TXM probability map read must carry the registry's CURRENT model key, and
    txm_stats.json and pipeline.py must agree with it on the threshold;
  * and after the draw, every string is measured at the renderer's own extents: no pair
    may overlap by more than 1 pt, and no string may leave the column it was placed in.

COST, AND THE THREE CACHES. The 48-frame SEM pass is about 20 s per frame and is written
to docs/figures/parameters_frames.json; the tile sweeps take about 65 s and go to
docs/figures/parameters_tiles.json; the TXM pass is a few seconds and goes to
docs/figures/parameters_txm.json. With all three present the plate redraws in a second;
PARAM_RECOMPUTE=1, or deleting a file, forces that pass again.

THE CACHES ARE CHECKED, NOT TRUSTED, because the controls above run inside the pass and
cannot run again off a file. A cached record has to clear three things before it is
allowed to answer, and failing any of them ABORTS rather than redraws: its settings hash
has to match, the settings it states in plain text have to equal the constants this
module has just read, and every control it recorded has to say PASS. A plate quoting an
evidence file written under different constants is a failure this project has had before,
and a hash alone does not catch a file edited by hand.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_parameters.py
"""
import hashlib
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths                                       # noqa: E402

sys.path.insert(0, _paths.ANALYSIS)
sys.path.insert(0, os.path.join(_paths.ANALYSIS, "research"))
sys.path.insert(0, os.path.join(_paths.ANALYSIS, "research", "improve"))
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "code"))
sys.path.insert(0, os.path.join(_paths.SEM_REPO, "interior_active_learning", "code"))
sys.dont_write_bytecode = True

import numpy as np                                  # noqa: E402
import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.patches import Rectangle            # noqa: E402
from skimage import measure as skm                  # noqa: E402

import detect_cracks as D                           # noqa: E402  -- the shipped stages
import detector_overrides as DO                     # noqa: E402  -- the shipped constants
import both_modalities as BM                        # noqa: E402  -- the one staging copy
import journal_style as J                           # noqa: E402

J.use()
#: THE ONE COMPARISON THE PLATE WAS MISSING. Everything above sweeps a constant within
#: ONE arm. The question the author calls the paper's unique point is across the arms:
#: does a constant chosen on one microscopy serve the other? This record answers it per
#: frame -- the critical k at which a frame's painted crack stops being separable from
#: its painted not-crack -- so the shipped k can be drawn against what each arm's
#: frames actually need.
CONTRAST_REC = _paths.scoped("modality_contrast.json", scope=False)

OUT = _paths.FIG_DIR
#: WHAT THE DASHED SERIES IS, per plate. Each entry names only the panels that plate
#: draws.
_DASHED_KEY = {
    "SEM": "DASHED is the panel\u2019s second series: (a) precision, "
           "(c) candidate floor,\n(d) 4-connectivity, (f) one radius at a time.",
    "TXM": "DASHED is the panel\u2019s second series: (j) false-positive rate.",
}

NAME = "F6 - how the parameters were determined"
#: ONE PLATE PER ARM. See draw()'s docstring for the measurement that forced the split:
#: on one sheet this ran 12.69 in tall and the figure pack printed its 8 pt type at
#: 5.6 pt.
PLATE_NAME = {"SEM": "F6a - SEM, how the parameters were determined",
              "TXM": "F6b - TXM, how the parameters were determined"}
DOCS = os.path.join(_paths.REPO, "docs", "figures")

#: The setting the paper evaluates at. Read from both_modalities so this plate and the
#: micrograph plates cannot drift apart, and cross-checked against detector_overrides.
K = float(BM.MAD_K)
GATE = int(DO.ABSOLUTE_DARK_THRESH)
LADDER = tuple(DO.SCALE_LADDER)
CLEAN_MIN = int(BM.CLEAN_MIN_PX)
CAND_MIN = int(BM.MIN_AREA_PX)

#: The grids each constant is swept over. Chosen to bracket the shipped value by at least
#: an order of magnitude in both directions where that is meaningful, so a flat curve is
#: a statement about the constant and not about a grid drawn too narrow to move.
GATE_GRID = (0, 2, 4, 6, 8, 10, 12, 14, 16, 20, 25, 30, 40)
GATE_GRID_FRAME = (0, 10, 20)          # the full chain, which is the expensive one
GATE_GRID_DARK = tuple(range(0, 42, 2))  # the darkness stage alone, which is free
CLEANMIN_GRID = (0, 1, 3, 6, 13, 25, 50, 100, 200, 400, 800)
CANDMIN_GRID = (1, 5, 13, 40, 100, 200, 400, 800, 1600, 3200)
OPEN_GRID = (0, 1, 2, 3, 4, 5, 6)
#: THREE CONSTANTS THAT HAD NO CURVE AND NOW HAVE ONE. The author's standing objection
#: to this plate has been that it does not show how each setting was chosen, and the
#: honest half of the answer was that most of them were never swept. These three can
#: be swept on the SAME 26 tiles and the SAME scorer as the rest, so they are, and the
#: plate gains three real graphs instead of three table rows:
#:   the closing radius, straight off the cached proposals;
#:   the denoise sigma, which the installed darkness stage already takes per call;
#:   and the flattening radius, by installing the detector with a ONE-RUNG ladder, so
#:   the curve is what a single radius scores and the shipped union can be read
#:   against the best single radius on the same axis.
CLOSE_GRID = (0, 1, 2, 3, 5, 8, 12)
DENOISE_GRID = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0)
#: THE BACKGROUND-ESTIMATE SIGMA, swept here because it was the ONE constant
#: on this plate with no sweep anywhere and the author would not have it
#: left without a curve. The grid brackets the shipped 40 px by a
#: factor of eight either way; below about 10 px the estimate starts to
#: follow the crack itself and above a few hundred it stops following the
#: illumination it exists to remove.
FLATSIG_GRID = (5, 10, 20, 40, 80, 160, 320)
SINGLE_LADDER_GRID = (5, 10, 20, 40, 80, 160, 320)


def _key(**kw):
    return hashlib.sha1(json.dumps(kw, sort_keys=True).encode()).hexdigest()[:12]


def _cached(path, key, build, expect):
    """Reuse a committed evidence file only when it was written at these settings.

    THE CACHE IS CHECKED, NOT TRUSTED. The reconstruction controls run inside build() and
    cannot run again off a cached file, so a cached record has to prove three things
    before it is allowed to answer: the settings hash matches, the settings it states in
    plain text match the constants this module reads out of detector_overrides now, and
    every control it recorded says PASS. Any of those failing aborts rather than redraws
    -- a figure quoting a cache written under other constants is the failure mode this
    project has hit before.
    """
    rec = None
    if os.path.exists(path) and not os.environ.get("PARAM_RECOMPUTE"):
        rec = json.load(open(path))
        if rec.get("key") == key:
            print(f"  reusing {os.path.relpath(path, _paths.REPO)} (key {key})")
        else:
            print(f"  {os.path.relpath(path, _paths.REPO)} was written at key "
                  f"{rec.get('key')}, not {key} -- recomputing")
            rec = None
    if rec is None:
        t0 = time.time()
        rec = build()
        rec["key"] = key
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(rec, open(path, "w"), indent=1)
        print(f"  wrote {os.path.relpath(path, _paths.REPO)} in {time.time() - t0:.0f}s")
    bad = {k: (rec.get(k), v) for k, v in expect.items() if rec.get(k) != v}
    if bad:
        raise SystemExit(f"{path} states {bad} -- it was not written at the constants "
                         f"this module is drawing")
    notpass = {k: v for k, v in rec.get("controls", {}).items()
               if not str(v).startswith("PASS")}
    if not rec.get("controls") or notpass:
        raise SystemExit(f"{path} carries no passing reconstruction controls ({notpass}); "
                         f"delete it or set PARAM_RECOMPUTE=1 and run it again")
    return rec


# ======================================================================= the 26 tiles
def tile_chain(proposed, flat=None, img8=None, ves=None, open_radius=1,
               close_radius=3, clean_min=CLEAN_MIN, cand_min=CAND_MIN, conn=2):
    """The cleaning chain exactly as both_modalities.stages runs it.

    THE EMISSION STEP IS DELEGATED, not transcribed. With the region classifier on,
    emission is no longer an area floor: it is features, the production model and a
    keep-list. Writing that out a second time here is how the project's own comment
    says two copies of six lines came to differ by one argument, so this calls
    `both_modalities.emit` and the sweeps vary only what they claim to vary.

    WHAT THE CONTROL BELOW THEREFORE STILL TESTS, honestly: that this function's
    `clean_mask` arguments and labelling connectivity reproduce the shipped chain's
    cleaned input. It no longer independently re-derives the emission, because there
    is now exactly one implementation of it.
    """
    cleaned = D.clean_mask(proposed, open_radius=open_radius, close_radius=close_radius,
                           min_area_px=clean_min)
    if not DO.USE_REGION_CLASSIFIER:
        lab = skm.label(cleaned, connectivity=conn)
        if not lab.max():
            return np.zeros(cleaned.shape, bool)
        sz = np.bincount(lab.ravel())
        keep = np.where(sz >= cand_min)[0]
        return np.isin(lab, keep[keep > 0])
    return BM.emit(cleaned, flat, img8, ves=ves)


def tile_evidence():
    """Sweep the gate, the two size floors, the opening and the connectivity on the tiles.

    tilebench is THE scorer in this project; its three absolute paths are repointed by
    _paths.tilebench() so the figure runs against the committed tile manifest. Pooled over
    every pixel at zero tolerance, which is the most pessimistic of the five aggregations
    this project uses and is stated in the sidecar.
    """
    TB = _paths.tilebench()
    tiles = TB.load()
    ok = TB.controls()
    if not ok:
        raise SystemExit("tilebench's own controls did not pass; nothing here is readable")
    flood = TB.FLOODED
    if not any(t["frame"] == flood for t in tiles):
        raise SystemExit(f"the off-specimen void tile {flood} is not in the corpus; the "
                         f"26-vs-25 reading in panel (b) would be meaningless")

    class _U:
        pass

    u = _U()
    DO.install(u)

    flats, props, finals = [], [], []
    for t in tiles:
        flat, proposed, _cleaned, final = BM.stages(t["img8"])
        flats.append(flat)
        props.append(proposed)
        finals.append(final)
    #: VESSELNESS ONCE PER TILE. It is a function of `flat` alone and it is the
    #: expensive half of the classifier's feature step; recomputing it at every sweep
    #: point would multiply the pass by the number of grid values. The single-radius
    #: sweep is the one place `flat` changes, and it passes its own.
    vess = [D.compute_vesselness(f) for f in flats] if DO.USE_REGION_CLASSIFIER \
        else [None] * len(flats)

    def chain(i, proposed, **kw):
        return tile_chain(proposed, flat=flats[i], img8=tiles[i]["img8"],
                          ves=vess[i], **kw)

    # RECONSTRUCTION CHECK 3. The chain this module sweeps must BE the shipped chain.
    bad = [t["frame"] for i, (t, p, f) in enumerate(zip(tiles, props, finals))
           if not np.array_equal(chain(i, p), f)]
    if bad:
        raise SystemExit(f"tile_chain does not reproduce both_modalities.stages on "
                         f"{len(bad)} tiles ({bad[:3]}); every sweep below would be a "
                         f"different pipeline from the one the paper evaluates")
    print(f"  CONTROL tile_chain == both_modalities.stages on all {len(tiles)} tiles: PASS")

    def pooled(masks, drop=()):
        tp = fp = fn = 0
        for m, t in zip(masks, tiles):
            if t["frame"] in drop:
                continue
            c = TB.counts(m, t["gt"], tol=0)
            tp += c["tp"]
            fp += c["fp"]
            fn += c["fn"]
        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        return dict(precision=p, recall=r, iou=tp / max(tp + fp + fn, 1),
                    f1=2 * p * r / max(p + r, 1e-12), tp=tp, fp=fp, fn=fn)

    rec = dict(
        what="sensitivity of the pooled tile score to each constant of Table 1",
        n_tiles=len(tiles), n_specimens=len({t["specimen"] for t in tiles}),
        excluded=list(TB.DEFAULT_EXCLUDE), flood_tile=flood,
        tolerance_px=0, aggregation="pooled over every pixel of the named tile set",
        mad_k=K, use_region_classifier=bool(DO.USE_REGION_CLASSIFIER),
        scorer="analysis/research/tilebench.py via paper/figures/_paths.tilebench()",
        shipped=pooled(finals), shipped_25=pooled(finals, drop=(flood,)),
        controls=dict(
            tilebench="PASS: oracle 1.0, empty 0.0, mark-everything precision == prevalence",
            chain="PASS: tile_chain reproduces both_modalities.stages on every tile"),
    )

    g26, g25 = {}, {}
    for t_dn in GATE_GRID:
        masks = [chain(i, u.segment_dark_regions(f, img8=t["img8"], mad_k=K,
                                                 absolute_dark_thresh=t_dn))
                 for i, (f, t) in enumerate(zip(flats, tiles))]
        g26[str(t_dn)] = pooled(masks)
        g25[str(t_dn)] = pooled(masks, drop=(flood,))
    rec["gate_26"], rec["gate_25"] = g26, g25

    rec["clean_min"] = {str(v): pooled([chain(i, p, clean_min=v)
                                        for i, p in enumerate(props)])
                        for v in CLEANMIN_GRID}
    rec["cand_min"] = {str(v): pooled([chain(i, p, cand_min=v)
                                       for i, p in enumerate(props)])
                       for v in CANDMIN_GRID}
    rec["opening"] = {
        str(c): {str(v): pooled([chain(i, p, open_radius=v, conn=c)
                                 for i, p in enumerate(props)])
                 for v in OPEN_GRID}
        for c in (2, 1)}

    # ---- the three that had no curve before ----------------------------------------
    rec["close"] = {str(v): pooled([chain(i, p, close_radius=v)
                                    for i, p in enumerate(props)])
                    for v in CLOSE_GRID}
    rec["denoise"] = {}
    for dv in DENOISE_GRID:
        masks = [chain(i, u.segment_dark_regions(f, img8=t["img8"], mad_k=K,
                                                 denoise_sigma=dv))
                 for i, (f, t) in enumerate(zip(flats, tiles))]
        rec["denoise"][str(dv)] = pooled(masks)
    #: ONE RUNG AT A TIME. A second installed detector whose ladder is the single
    #: radius under test; the shipped seven-rung union is scored on the same tiles and
    #: the same scorer, so the two are comparable and the union's value is readable
    #: off the panel rather than asserted.
    rec["single_radius"] = {}
    for sv in SINGLE_LADDER_GRID:
        class _V:
            pass
        v1 = _V()
        DO.install(v1, scale_ladder=(sv,), use_multiscale_union=True)
        masks = []
        for t in tiles:
            fl = D.flatten_background(t["img8"], sigma=sv)
            # `flat` changes here, so this sweep cannot reuse the cached vesselness
            masks.append(tile_chain(v1.segment_dark_regions(fl, img8=t["img8"],
                                                            mad_k=K),
                                    flat=fl, img8=t["img8"]))
        rec["single_radius"][str(sv)] = pooled(masks)
    #: THE FLATTENING SIGMA, one value at a time. `flat` is recomputed per sigma, so
    #: like the single-radius sweep this one cannot reuse the cached vesselness.
    rec["flatten_sigma"] = {}
    for fv in FLATSIG_GRID:
        masks = []
        for t in tiles:
            fl = D.flatten_background(t["img8"], sigma=fv)
            masks.append(tile_chain(u.segment_dark_regions(fl, img8=t["img8"],
                                                           mad_k=K),
                                    flat=fl, img8=t["img8"]))
        rec["flatten_sigma"][str(fv)] = pooled(masks)
    rec["union_on_these_tiles"] = rec["shipped"]
    return rec


# ================================================================ the 48 painted frames
def frame_evidence():
    """One pass over every full frame that carries a hand-painted correction mask.

    The loader, the field-of-view crop, the gentler contrast stretch three frames need and
    the four paint states all come from fullframe_lever4_safety; the per-rung maps and the
    cleaning chain come from fullframe_recall_decomposition. Nothing here re-expresses the
    detector's criterion -- rung_maps' own identity, dark(k) = (k_max > k) | (img8 < t),
    is what makes a sweep readable off one pass, and it is checked against the installed
    segment_dark_regions on the first frame.
    """
    import fullframe_recall_decomposition as FRD
    import fullframe_lever4_safety as FF

    FRD.MAD_K = K                       # the paper's setting, not the app's default
    FRD.MIN_AREA_CLEAN = CLEAN_MIN
    FRD.MIN_AREA_CAND = CAND_MIN
    if tuple(FRD.LADDER) != LADDER or int(FRD.ABS_DARK) != GATE:
        raise SystemExit(f"fullframe_recall_decomposition reports ladder {FRD.LADDER} / "
                         f"gate {FRD.ABS_DARK}, detector_overrides says {LADDER} / {GATE}")

    names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(FRD.PAINT)
                   if f.endswith("_correction_mask.png"))
    names = [n for n in names
             if os.path.exists(os.path.join(FRD.SEM, "original", n + ".tif"))]
    print(f"  {len(names)} full frames carry both a micrograph and a correction mask")

    out, t0, first = [], time.time(), True
    for i, n in enumerate(names, 1):
        got = FF.load_frame(n)
        if got is None:
            out.append(dict(frame=n, error="shape_mismatch"))
            continue
        img8, _raw, corr = got
        crack = corr == 1
        flat40 = D.flatten_background(img8, sigma=40)
        dark_rel, kmax, per = FRD.rung_maps(img8, flat40)

        if first:
            # RECONSTRUCTION CHECKS 1 and 2, both of which assert rather than warn.
            FRD._control_union(img8, flat40, dark_rel, n)
            FRD._control_kmax(img8, kmax, dark_rel | (img8 < GATE))
            first = False
        del kmax

        r = dict(frame=n, px=int(img8.size), crack=int(crack.sum()),
                 notc=int((corr == 2).sum()), erase=int((corr == 3).sum()),
                 dark_rel=int(dark_rel.sum()), absdark=int((img8 < GATE).sum()))

        # the darkness stage alone, which costs nothing and gives a smooth gate curve
        r["dark_crack"] = {str(t_dn): int((crack & (dark_rel | (img8 < t_dn))).sum())
                           for t_dn in GATE_GRID_DARK}
        # the WHOLE chain, which is what the detector emits, at three settings
        r["chain"] = {}
        for t_dn in GATE_GRID_FRAME:
            dark = dark_rel if t_dn == 0 else (dark_rel | (img8 < t_dn))
            st = FRD.chain(dark, flat40)
            r["chain"][str(t_dn)] = FRD.decompose(crack, dark, st)
            r["chain"][str(t_dn)]["cand_px"] = int(st["cand"].sum())
            del st, dark

        # leave-one-out marginal of each term of the union. A pixel is credited to a rung
        # only when that rung is the ONLY term that reaches it, so removing the rung would
        # really lose it; `cnt == 1` is the cheap form of "no other rung marks this".
        cnt = np.zeros(img8.shape, np.uint8)
        for s in LADDER:
            cnt += per[s]["cut"].astype(np.uint8)
        absm = img8 < GATE
        r["rung_area"] = {str(s): int(per[s]["cut"].sum()) for s in LADDER}
        r["rung_only_area"] = {}
        r["rung_only_crack"] = {}
        for s in LADDER:
            only = per[s]["cut"] & (cnt == 1) & ~absm
            r["rung_only_area"][str(s)] = int(only.sum())
            r["rung_only_crack"][str(s)] = int((only & crack).sum())
            del only
        gate_only = absm & ~(cnt > 0)
        r["gate_only_area"] = int(gate_only.sum())
        r["gate_only_crack"] = int((gate_only & crack).sum())
        r["union_area"] = int(((cnt > 0) | absm).sum())
        r["union_crack"] = int((((cnt > 0) | absm) & crack).sum())
        del cnt, absm, gate_only, per, dark_rel

        out.append(r)
        print(f"  [{i}/{len(names)}] {n:<34} painted {r['crack']:>10,}  "
              f"kept {r['chain'][str(GATE)]['kept']:>10,}  gate-only crack "
              f"{r['gate_only_crack']:>10,}  {time.time() - t0:5.0f}s", flush=True)

    return dict(what="per-frame evidence for the absolute gate, the scale ladder and the "
                     "two size floors, on every frame carrying a hand-painted correction",
                mad_k=K, gate=GATE, ladder=list(LADDER),
                use_region_classifier=bool(DO.USE_REGION_CLASSIFIER),
                clean_min=CLEAN_MIN, cand_min=CAND_MIN,
                paint_states="1 = crack, 2 = not crack, 3 = erase (also a not-crack "
                             "verdict), 0 = unreviewed and counted as neither",
                source="fullframe_lever4_safety.load_frame + "
                       "fullframe_recall_decomposition.rung_maps / chain / decompose",
                controls=dict(
                    union="PASS: rung union OR (img8 < gate) == the installed "
                          "segment_dark_regions, pixel for pixel, on the first frame",
                    kmax="PASS: (k_max > k) OR (img8 < gate) reproduces that same mask"),
                n_frames=len([r for r in out if "error" not in r]), frames=out)

# ================================================================ the 31 TXM frames
#: The TXM model's one free operating constant, swept on the SAME refereed pixels that
#: docs/figures/txm_background_units.json scored the SEM detector over. Same frames, same
#: paint, same measure -- so the two TXM rows of this plate may be read against each other,
#: which is the one comparison this plate is allowed to make across its arms.
TXM_NB = 200                                   # 0.005-wide probability bins
TXM_EPS = 1e-7                                 # so a bin sum is count(prob > t), not >=
TXM_GRID = tuple(round(0.05 + 0.005 * i, 3) for i in range(int((0.95 - 0.05) / 0.005) + 1))


def _txm_group(name):
    """The four specimen groups, by the TXM project's own rule.

    Copied from analysis/research/improve/txm_background_units.py, which is the file that
    wrote the record this sweep has to reproduce. It is four string tests, and the control
    below asserts that this copy puts every frame in the same group that record did -- a
    second classifier that disagreed would be caught before a single number is drawn.
    """
    n = name.lower()
    if "_b3_" in n:
        return "B3"
    if "wrought" in n:
        return "Wrought"
    if "hc_316l" in n:
        return "AM/HC"
    if "_b2_" in n or "b2_" in n:
        return "B2"
    return "other"


def _txm_constants():
    """The TXM arm's shipped constants, PARSED out of the deployed source, never retyped.

    ast rather than import: the app's modules pull in torch and transformers, which this
    plate has no use for, and a source scan with a regular expression would match the
    constant's name inside the prose that explains it. Every name here is a module-level
    assignment of a literal in one of the two files, and a missing one aborts.
    """
    import ast
    want = {
        #: EVERY MODULE-LEVEL CONSTANT THE MASK PATH READS, not the handful the first
        #: edition listed. The width-clip family and the straight-artefact rejector are
        #: nine and three more numbers that _narrow_to_image applies to every exported
        #: mask; leaving them off the plate understated the TXM arm's parameter count by
        #: half, which is what the author noticed.
        "pipeline.py": ("DEFAULT_THRESHOLD", "MIN_BLOB_PX", "FILL_HOLES_MAX_PX",
                        "TIGHTEN_WINDOW", "TIGHTEN_MIN_CORE", "CORRECTION_FLOOR",
                        "RECIPE", "WIDTH_CLIP", "WIDTH_CLIP_RADIUS",
                        "WIDTH_CLIP_DIRS", "WIDTH_CLIP_PROBES", "WIDTH_CLIP_RECENTRE",
                        "WIDTH_CLIP_PEAK_SIGMA", "WIDTH_CLIP_BG_WINDOWS",
                        "WIDTH_CLIP_MIN_MEASURED", "WIDTH_CLIP_IDW_K",
                        "STRAIGHT_MIN_PX", "STRAIGHT_MIN_ASPECT",
                        "STRAIGHT_MAX_WANDER"),
        "model.py": ("TILE", "TILE_STRIDE", "EMB_STRIDE", "SAM_MODEL_ID"),
    }
    out = {}
    for fname, names in want.items():
        path = _paths.require(os.path.join(_paths.TXM_REPO, "app", "core", fname),
                              f"the TXM arm's {fname}", "TXM_REPO")
        tree = ast.parse(open(path).read())
        found = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id in names:
                    try:
                        found[tgt.id] = ast.literal_eval(node.value)
                    except ValueError:
                        pass
        missing = [n for n in names if n not in found]
        if missing:
            raise SystemExit(f"{path} no longer defines {missing} as module-level "
                             f"literals; the TXM rows would be quoting values that are "
                             f"not the ones the app runs")
        out.update(found)
    return out


#: The three frames the SEM chain reads at a gentler stretch, imported rather than
#: counted here, so a frame joining or leaving that set moves the plate.
from common import GENTLE_CONTRAST_IMAGES as GENTLE, contrast_kwargs_for  # noqa: E402
_g = contrast_kwargs_for(sorted(GENTLE)[0])
GENTLE_PCT = (_g["low_pct"], _g["high_pct"])


def _sem_constants():
    """The SEM chain's own stage defaults, PARSED out of the shipped detect_cracks.py.

    Same discipline as `_txm_constants`, and for the same reason. Eight of these -- the
    contrast window, the databar probe and the field-of-view finder -- never appeared on
    the plate at all, although every frame the paper reports passes through them, and a
    constant that is applied to the data and not declared is an undeclared degree of
    freedom. A name that stops being a defaulted argument of its function aborts rather
    than quietly dropping off the table.
    """
    import ast
    want = {
        "load_as_uint8": ("low_pct", "high_pct"),
        "_detect_databar_top": ("search_frac", "window", "std_ratio", "mean_ratio"),
        "find_field_of_view": ("bright_thresh", "shrink_frac", "min_keep_frac"),
        "flatten_background": ("sigma", "low_pct", "high_pct"),
        "segment_dark_regions": ("denoise_sigma", "absolute_dark_thresh"),
        "clean_mask": ("open_radius", "close_radius"),
    }
    path = _paths.require(os.path.join(_paths.SEM_REPO, "code", "detect_cracks.py"),
                          "the SEM arm's detect_cracks.py", "SEM_REPO")
    tree = ast.parse(open(path).read())
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    out, missing = {}, []
    for fname, names in want.items():
        node = fns.get(fname)
        if node is None:
            missing.append(fname)
            continue
        args = [a.arg for a in node.args.args]
        defs = node.args.defaults
        have = {}
        for i, d in enumerate(defs):
            try:
                have[args[len(args) - len(defs) + i]] = ast.literal_eval(d)
            except ValueError:
                pass
        for nm in names:
            if nm in have:
                out[f"{fname}.{nm}"] = have[nm]
            else:
                missing.append(f"{fname}({nm}=)")
    if missing:
        raise SystemExit(f"{path} no longer defines {missing} as defaulted arguments "
                         f"of literals; the SEM table would be quoting values that are "
                         f"not the ones the chain runs")
    return out


def txm_evidence():
    """Sweep the TXM ensemble's probability threshold over the refereed TXM paint.

    WHY THIS UNIT SET AND NO OTHER. docs/figures/txm_background_units.json scored the SEM
    detector on TXM over the frames in TXM/paint/corrections that carry at least 5000
    crack AND 5000 not-crack pixels, on refereed pixels only (1 = crack, 2 or 3 = not
    crack, 0 excluded). This function enumerates by the same rule and ASSERTS that it
    recovers that record's own totals -- 31 frames, its crack and not-crack pixel counts,
    and every one of its four by-group counts -- before it sweeps anything. The two TXM
    rows of the plate are then the same pixels measured two ways.

    WHY ACCURACY AND NOT OVERLAP. The record forbids overlap scores on this set in so many
    words: the TXM paint is far wider than the feature and a prior measurement puts the
    IoU ceiling for a correct 3 px crack at 0.0498, so IoU here ranks imitation of the
    brush. Accuracy against the EMPTY-MASK baseline is what that record reports, so it is
    what this sweep reports, and the empty-mask accuracy computed here is checked against
    the one the record states.

    WHAT IS SWEPT. `prob > t` on the deployed model's own cached probability map, before
    the speck prune and the hole fill that the serving path applies afterwards. A
    histogram per frame answers every t exactly, which is the trick
    TXM/research/oppoint/build_hists.py uses and the reason the pass costs seconds; bin
    edges carry the same +EPS shift so that summing from the edge at t counts prob > t.
    """
    R = _paths.require(_paths.TXM_REPO, "the TXM_Crack_Detection_Pipeline checkout",
                       "TXM_REPO")
    cdir = _paths.require(os.path.join(R, "paint", "corrections"),
                          "the TXM correction masks", "TXM_REPO")
    idir = _paths.require(os.path.join(R, "app_data", "images"),
                          "the TXM app's image store", "TXM_REPO")
    reg = json.load(open(_paths.require(
        os.path.join(R, "app_data", "models", "registry.json"),
        "the TXM model registry", "TXM_REPO")))
    deployed = reg["current"].get("created")
    recipe = reg["current"].get("recipe")

    # the record this pass has to reproduce, read before anything is computed
    units = json.load(open(_paths.scoped("txm_background_units.json", scope=False)))

    by_stem = {}
    for iid in sorted(os.listdir(idir)):
        mp = os.path.join(idir, iid, "meta.json")
        if os.path.exists(mp):
            m = json.load(open(mp))
            by_stem[os.path.splitext(m["filename"])[0]] = (iid, m)

    edges = np.linspace(0.0, 1.0, TXM_NB + 1) + TXM_EPS
    edges[0], edges[-1] = -1.0, 2.0
    h1 = np.zeros(TXM_NB, np.int64)
    h0 = np.zeros(TXM_NB, np.int64)
    grp = {}
    used, keys = 0, set()
    for f in sorted(os.listdir(cdir)):
        if not f.endswith("_correction.npy"):
            continue
        stem = f[: -len("_correction.npy")]
        if not os.path.exists(os.path.join(R, "images", stem + ".tif")):
            continue
        corr = np.load(os.path.join(cdir, f))
        crack = corr == 1
        notc = (corr == 2) | (corr == 3)
        nc, nn = int(crack.sum()), int(notc.sum())
        if nc < 5000 or nn < 5000:              # the record's own floor
            continue
        used += 1
        g = _txm_group(stem)
        if stem not in by_stem:
            raise SystemExit(f"{stem} is in the scored set but has no entry in the TXM "
                             f"app store, so its probability map cannot be read")
        iid, meta = by_stem[stem]
        keys.add(meta.get("model_key"))
        pp = os.path.join(idir, iid, "probs", str(meta.get("model_key")) + ".npy")
        if not os.path.exists(pp):
            pp = os.path.join(idir, iid, "prob.npy")
        prob = np.load(pp)
        if prob.shape != corr.shape:
            raise SystemExit(f"{stem}: probability map {prob.shape} does not fit its "
                             f"correction mask {corr.shape}")
        a = np.histogram(prob[crack], bins=edges)[0].astype(np.int64)
        b = np.histogram(prob[notc], bins=edges)[0].astype(np.int64)
        h1 += a
        h0 += b
        gb = grp.setdefault(g, dict(frames=0, crack_px=0, notcrack_px=0))
        gb["frames"] += 1
        gb["crack_px"] += nc
        gb["notcrack_px"] += nn
        del prob, corr, crack, notc
        print(f"  [{used:>2}] {g:<8} {stem[:46]:<48} crack {nc:>9,}", flush=True)

    # ---- CONTROL 1. the same frames, the same pixels, as the record --------------------
    want = dict(n_frames=units["n_frames"],
                crack=units["refereed_crack_px"], notc=units["refereed_notcrack_px"])
    got = dict(n_frames=used, crack=int(h1.sum()), notc=int(h0.sum()))
    if got != want:
        raise SystemExit(f"this pass enumerated {got} but txm_background_units.json was "
                         f"written over {want}; the two TXM rows would be different "
                         f"pixel sets drawn as if they were one")
    for g, blk in units["by_group"].items():
        mine = grp.get(g)
        if (not mine or mine["frames"] != blk["frames"]
                or mine["crack_px"] != blk["crack_px"]
                or mine["notcrack_px"] != blk["notcrack_px"]):
            raise SystemExit(f"group {g}: this pass has {mine}, the record has "
                             f"{blk['frames']} frames / {blk['crack_px']} crack / "
                             f"{blk['notcrack_px']} not-crack")

    # ---- CONTROL 2. the deployed model, not an archived one ----------------------------
    if keys != {deployed}:
        raise SystemExit(f"the probability maps carry model keys {sorted(keys)}; the "
                         f"registry's current model is {deployed}")

    # ---- CONTROL 3. the do-nothing baseline must be the record's own -------------------
    tot1, tot0 = int(h1.sum()), int(h0.sum())
    empty = 100.0 * tot0 / (tot1 + tot0)
    stated = max(v["empty_mask_accuracy_pct"] for v in units["pooled"].values())
    if abs(empty - stated) > 1e-9:
        raise SystemExit(f"empty-mask accuracy here is {empty!r}, the record states "
                         f"{stated!r}")

    cum1 = h1[::-1].cumsum()[::-1]
    cum0 = h0[::-1].cumsum()[::-1]
    curve = {}
    for t in TXM_GRID:
        i = int(round(t * TXM_NB))
        tp, fp = int(cum1[i]), int(cum0[i])
        tn = tot0 - fp
        acc = 100.0 * (tp + tn) / (tot1 + tot0)
        curve[f"{t:.3f}"] = dict(
            accuracy_pct=acc, margin_pp=acc - empty,
            recall=tp / max(tot1, 1), specificity_pct=100.0 * tn / max(tot0, 1),
            marked_pct=100.0 * (tp + fp) / (tot1 + tot0),
            area_agreement=(tp + fp) / max(tot1, 1))
    return dict(
        what="the TXM ensemble's probability threshold swept over the refereed TXM paint, "
             "on the same frames and the same pixels as docs/figures/"
             "txm_background_units.json scored the SEM detector over",
        model_key=deployed, recipe=recipe,
        n_frames=used, crack_px=tot1, notcrack_px=tot0,
        empty_mask_accuracy_pct=empty,
        scoring="refereed pixels only: 1 = crack, 2 or 3 = not-crack, 0 excluded. "
                "prob > t on the deployed model's cached map, BEFORE the speck prune and "
                "the hole fill the serving path applies after it",
        by_group={g: dict(v) for g, v in sorted(grp.items())},
        grid=list(TXM_GRID), curve=curve,
        controls=dict(
            unit_set="PASS: 31 frames and both refereed pixel counts reproduce "
                     "docs/figures/txm_background_units.json exactly, group by group",
            model="PASS: every probability map carries the registry's current model key",
            baseline="PASS: the empty-mask accuracy computed here equals the one the "
                     "record states, to 1e-9"))

# ============================================================================= drawing
#: ONE CONVENTION, EVERY ROW. A solid neutral rule and a filled square mark THE VALUE THE
#: PAPER RUNS AT, on every sparkline that has one on an axis. The dotted rule appears
#: once, in row (a), and is the value the shipped application itself runs.
SHIPPED_RULE = dict(color=J.G_MID, lw=0.8, zorder=2)
APP_RULE = dict(color=J.G_MID, lw=0.7, linestyle=(0, (1, 2)), zorder=2)

#: TYPE SIZES. J.FLOOR is 8 pt at the printed width and nothing here is below it.
#: T_NAME is a panel head or a group head, T_BAND an arm heading, T_TICK everything
#: inside the table and on the axes.
T_NAME, T_BAND, T_TICK = 8.5, 9.0, 8.0

#: THE TALLY THIS MODULE'S DOCSTRING STATES, asserted against the tables after they are
#: built. The docstring is prose and prose does not recompute: how many constants were
#: selected by a sweep is the plate's finding, and a constant added to either
#: table in a later revision would falsify it silently. Changing a table without
#: changing these numbers now aborts.
#: THE INHERITED CONSTANTS AND THEIR PANELS WERE REMOVED at the author's instruction.
#: Nine constants carried no recorded provenance and five panels swept them after the
#: fact -- the darkness gate, the two area floors, the opening radius and connectivity,
#: the closing radius and the denoise sigma -- plus the SEM multiplier carried onto
#: transmission. They are gone from the plate and from the tables.
#:
#: WHAT LEFT WITH THEM, so nobody has to find out by missing it: panel (b) was the
#: evidence that more than half the detector\'s frame-scale recall rests on one
#: unsearched integer (recall 0.274 against 0.124 with the gate off), and the closing
#: and denoise panels were the two new sweeps showing the shipped values are not at
#: their own grid\'s optimum. Those measurements still exist in
#: docs/figures/parameters_tiles.json and parameters_frames.json; the figure no longer
#: shows them.
#: EVERY ROW LETTERED F MUST SAY, HERE, WHY F IS TRUE OF IT.
#:
#: F is the only letter on this plate that makes a claim about what does NOT exist:
#: that no measurement of this constant is on record in either repository. That is the
#: easiest claim in the figure to get wrong, and this edition got it wrong eight times
#: -- the TXM hole fill was lettered "no measurement exists" while the caption file
#: printed its three-point sweep over all 71 frames two keys further down. The cause was
#: that F had become the default for any row without a PANEL, and not-drawn is not the
#: same as not-measured.
#:
#: A text scan of the source comments was tried as the guard and rejected: of thirteen
#: F-lettered TXM constants it flagged three, and all three were the comment above a
#: NEIGHBOURING constant (the straightness census belongs to the wander cut, the model
#: scores belong above the recipe name, and WIDTH_CLIP_PROBES merely contains the word
#: "measured" in its own one-line description). A guard with a quarter of its hits
#: spurious teaches a reader to wave it through, and the exemption list would be exactly
#: where the next real one hid. So the requirement is a sentence per row instead: cheap
#: to write, impossible to satisfy without looking at the source, and readable by a
#: referee who wants to check one.
WHY_F_IS_TRUE = {
    # --- SEM: plain defaults in detect_cracks.py's function signatures ---------------
    "contrast window (%)": "a kwarg default on load_as_uint8; the docstring measures "
                           "nothing and no sweep of the percentiles exists",
    "contrast, 3 frames (%)": "0/100 is the degenerate no-clip case, applied by hand to "
                              "three named low-contrast frames in common.py",
    "databar search depth": "kwarg default on _detect_databar_top; its docstring "
                            "describes the burned-in info bar and measures nothing",
    "databar window (rows)": "kwarg default on _detect_databar_top, never measured",
    "databar sd ratio": "kwarg default on _detect_databar_top, never measured",
    "databar mean ratio": "kwarg default on _detect_databar_top, never measured",
    "field-of-view gate (DN)": "kwarg default on find_field_of_view, never measured",
    "field-of-view shrink": "kwarg default on find_field_of_view, never measured",
    "field-of-view floor": "kwarg default on find_field_of_view; a fallback trigger, "
                           "not a tuned quantity",
    # --- TXM ------------------------------------------------------------------------
    "recipe": "a NAME, not a quantity. The comment above it reports the model's scores, "
              "which are evidence about the model and not about the string",
    "feature channels": "the 17 hand-built channels, which is a COUNT of the filter "
                        "bank and not a tuned number: 1 intensity + 6 Gaussian "
                        "smoothings + 4 gradient magnitudes + 4 Laplacians + 2 local "
                        "standard deviations. No sweep over alternative banks exists "
                        "(the hybrid member's 273 dimensions are these plus SAM's 256, "
                        "and that is `hybrid_dim`, not this row)",
    "backbone": "facebook/sam-vit-huge, used frozen. No comparison against a smaller "
                "SAM checkpoint exists in this project",
    "SAM tile (px)": "1024 px is the ViT-H encoder's own input size",
    "embedding stride (px)": "16 px is the ViT patch size: 1024 / 64 embedding cells",
    "clip probes": "a budget per frame. Its own line contains the word 'measured' "
                   "describing what a probe IS, which is not evidence about 4000",
    "clip min points": "a refusal threshold -- decline rather than guess -- not tuned",
    "straight min area (px)": "this and the aspect below DEFINE the population the "
                              "wander census screened; the census measured the wander "
                              "cut, not this screen",
    "straight min aspect": "see the area floor above: part of the screen, not a "
                           "measured cut",
}

DOCSTRING_TALLY = {"total": 50, "swept": 19, "test": 5, "measured": 8,
                   "fixed": 18}


#: A SWEPT ROW WITH NO PANEL still owes the reader the finding. These seven were
#: lettered F until the sweeps of 2026-11-18 existed; F asserts that no measurement
#: of a constant exists, so the letter had to move the moment one did. They have no
#: sparkline because their grids are not one-dimensional curves over a single tile
#: score -- they are frame-scale recalls, paired width ratios and liveness checks --
#: so what the sweep concluded is written here and quoted into the caption file.
WHY_THE_SWEPT_VALUE_STANDS = {
    "flattening clip (%)": "kwarg defaults on flatten_background. SWEPT NOW, and the "
                           "docstring's argument holds: raw min/max scores the same "
                           "recall and deletes 17,153 px of hand-painted crack, "
                           "(2, 98) deletes 376,508, and (0.5, 99.5) is the only arm "
                           "that deletes none. Note the pair exists TWICE -- "
                           "detector_overrides._flatten hard-codes it for sigma > 64, "
                           "so it governs 3 of 7 ladder rungs. "
                           "docs/figures/flattening_clip.json",
    "decimate above (px)": "a speed guard, RE-VALIDATED at frame scale after its only "
                           "prior check ran on tiles where the radii it governs are "
                           "inert. The decimated path finds 7,373 painted crack px "
                           "the exact path misses and loses 1,149, is 4x faster "
                           "(17.98 s vs 72.39 s per frame), and 32 and 64 are the "
                           "same computation because install() never decimates the "
                           "sigma=40 rung. docs/figures/decimate_guard.json",
    "clip radius (px)": "swept 20 to 2000: the curve KNEES at the shipped 200 -- 100 px reaches 0.79x of the shipped width, 400 px only 1.03x and nothing above it moves. The one of the five with a defensible value. docs/figures/txm_clip_constants.json",
    "clip directions": "swept 2 to 120: a smooth monotone from 1.11x to 0.92x of the shipped width with no knee, Jaccard >= 0.99 throughout. 12 is arbitrary and the choice costs little. docs/figures/txm_clip_constants.json",
    "clip recentre (px)": "slack for a skeleton sitting off the ridge. Swept 0 to 30: a smooth monotone 1.05x to 0.87x with no knee, so 3 is arbitrary and cheap. docs/figures/txm_clip_constants.json",
    "clip background (px)": "three window sizes. SWEPT NOW -- and the module constant is a DEAD KNOB: local_background binds WIDTH_CLIP_BG_WINDOWS as a default argument at import, so assigning to it changes this table and nothing else (0 of 511,153 px moved). The VALUE is live and is the most load-bearing of the five -- measured width spans 0.36x to 1.59x across the grid -- but the NAME is not a knob. docs/figures/txm_clip_constants.json",
    "clip IDW neighbours": "swept k = 1 to 120: median width moves 0.9998x to 1.0031x, so this constant is inert to within 0.3% and 12 is as good as anything. docs/figures/txm_clip_constants.json",
}

_SCRATCH = None


def _tw(text, size, *, bold=False):
    """The width of `text`, in inches, MEASURED at the renderer.

    A characters-per-inch estimate is how a box comes out a tenth of an inch too
    narrow and its longest row prints over its own value. The scratch figure is made
    once and the text artist removed after each measurement.
    """
    global _SCRATCH
    if _SCRATCH is None:
        _SCRATCH = plt.figure(figsize=(2.0, 2.0), dpi=100)
        _SCRATCH.canvas.draw()
    t = _SCRATCH.text(0.0, 0.0, text, fontsize=size,
                      fontweight="bold" if bold else "normal")
    w = t.get_window_extent(renderer=_SCRATCH.canvas.get_renderer()).width
    t.remove()
    return w / _SCRATCH.dpi


def _lines(size, n):
    """The height, in inches, of `n` lines set at `size` points, at this plate's lead."""
    return n * size * 1.25 / 72.0


#: THE TABLE-BUILDER THAT USED TO LIVE HERE IS GONE. `Plate` laid out a six-column
#: ruled table whose widest column was a sentence of prose per row, with
#: `_no_collisions` and `_within_columns` to police it. The plate carries no prose now,
#: so all three were unreachable: a class with no caller is a second description of the
#: figure that nothing keeps true. The layout, and its own two controls, are in draw().


def _pooled(frames, num, den="crack"):
    """Pooled over pixels, and the per-frame median of the same ratio. Two frames hold
    almost half of this corpus's painted crack, so a pooled figure alone can be them.

    `den` is a key of the per-frame record, or a callable taking the record."""
    return _spread(frames, num, den)[:2]


def _spread(frames, num, den="crack"):
    """(pooled, median, p25, p75, frames with a non-zero value, frames with a denominator).

    The pooled value and the per-frame median are different statistics of a RATIO, and
    where the per-frame distribution is zero-inflated they can differ by two orders of
    magnitude without either being wrong. The quartiles and the non-zero count are what
    say which of those is happening, so they travel with the median rather than being
    left for a reader to assume.
    """
    dfn = den if callable(den) else (lambda r, k=den: r[k])
    ns = [num(r) for r in frames]
    ds = [dfn(r) for r in frames]
    per = sorted(n / d for n, d in zip(ns, ds) if d > 0)
    pooled = sum(ns) / max(sum(ds), 1)
    if not per:
        nan = float("nan")
        return pooled, nan, nan, nan, 0, 0

    def q(f):
        if len(per) == 1:
            return per[0]
        i = f * (len(per) - 1)
        lo = int(np.floor(i))
        hi = min(lo + 1, len(per) - 1)
        return per[lo] + (per[hi] - per[lo]) * (i - lo)

    return pooled, q(0.5), q(0.25), q(0.75), sum(1 for x in per if x > 0), len(per)


def _best(d):
    """The key of the maximum of a {setting: score} mapping, read off the record."""
    return max(d, key=lambda s: d[s])


def _mark(ax, x, y, color):
    ax.axvline(x, **SHIPPED_RULE)
    ax.plot([x], [y], "s", color=color, ms=3.6, mew=0, zorder=7)


def draw(tiles, frames, madk, dead, txm, units, scores, stats, const, sem, arm):
    """One arm's plate. `arm` is "SEM" or "TXM".

    THE TWO ARMS ARE TWO FIGURES, and the reason is measurable rather than editorial.
    On one plate this ran 12.69 in tall against a 6.37 in text block. The figure pack
    fits each plate to a 8.5 x 11 in page with 0.75 in margins, which leaves 8.95 in of
    height, so the plate was scaled by 0.705 and its 8.0 pt type printed at 5.6 pt --
    under the 8 pt floor journal_style enforces at draw time and under the 6 pt floor
    reserved for sub- and superscripts. The plate passed its own checks because they
    measure the plate, not the page it is pasted on.

    Everything below is unchanged except that each block is drawn only for its own arm.
    The cross-arm comparison rides with TXM, because that is the arm the shared constant
    serves worse and the panel exists to say so.
    """
    """The plate: every constant of both detectors, and the evidence where there is any.

    WHY IT WAS REDRAWN AGAIN. The wordless edition before this one was nine line panels
    over two strips of loose name/value pairs, and it drew twenty-one constants. The
    author's reading of it was that it looked simple and that it was not the whole set.
    Both were right. The SEM chain reads eight more numbers before the detector ever
    runs -- a contrast window, a databar probe, a field-of-view finder -- and the TXM
    mask path applies twelve more after it: a nine-constant width clip and a
    three-constant straight-artefact rejector. Forty-seven constants, not twenty-one.

    SO THE PLATE IS A FIGURE AND A TABLE, which is what a methods section with this many
    settings looks like in print. The panels carry the nine constants that have evidence
    worth plotting; the ruled table underneath carries EVERY constant, grouped by the
    stage that reads it, with its value and how it was fixed. A constant with a panel
    names its letter. Nothing on the plate is a sentence.

    WHAT CHANGED IN THE PANELS. They had no numbers on them: no y tick labels at all and
    the x ends set as loose figure text beside an axes with its ticks switched off. That
    is a sparkline, and a sparkline with no scale is a shape, not a measurement. Each
    panel is now a small axes with real ticks -- two on each axis, labelled, at the
    plate's own type size -- so a reader can see what the curve moved BY and not only
    which way it went.
    """
    wf = madk["sets"]["whole_fields"]
    grid = [float(g) for g in madk["grid"]]
    fr = [r for r in frames["frames"] if "error" not in r]
    cv = scores["cross_validated"]

    # ---- every number a panel or a row quotes, read off a record rather than typed ---
    f1 = {g: wf["per_k"][str(g)]["f1"] for g in grid}
    gate26 = {k: v["iou"] for k, v in tiles["gate_26"].items()}
    cmin = {k: v["iou"] for k, v in tiles["clean_min"].items()}
    amin = {k: v["iou"] for k, v in tiles["cand_min"].items()}
    op8 = {k: v["iou"] for k, v in tiles["opening"]["2"].items()}
    clo = {k: v["iou"] for k, v in tiles["close"].items()}
    dns = {k: v["iou"] for k, v in tiles["denoise"].items()}
    sing = {k: v["iou"] for k, v in tiles["single_radius"].items()}
    fsig = {k: v["iou"] for k, v in tiles["flatten_sigma"].items()}
    #: THE MULTIPLIER, SWEPT ON THIS LABORATORY'S OWN FRAMES. The sweep that used to
    #: stand behind this constant was run on a public collection the author has
    #: removed from the paper, which left the one constant the plate called swept with
    #: no evidence here at all. This record is the same question asked of the frames
    #: the paper reports: 45 carrying painted crack for recall, 18 carrying both
    #: verdicts for precision. The two are NEVER pooled into an F1 -- the record says
    #: so in its own scoring note, because they are different frame sets -- so the
    #: panel draws them as two series and makes no composite of them.
    _LK = json.load(open(os.path.join(_paths.DOC_FIGURES, "lab_madk_sweep.json")))
    kgrid_lab = [float(g) for g in _LK["grid"]]
    k_rec = {g: _LK["means"][str(g)]["recall"] for g in kgrid_lab}
    k_pre = {g: _LK["means"][str(g)]["precision"] for g in kgrid_lab}
    union_iou = float(tiles["union_on_these_tiles"]["iou"])
    best_single = max(sing, key=lambda k: sing[k])
    best_close = max(clo, key=lambda k: clo[k])
    best_den = max(dns, key=lambda k: dns[k])
    op4 = {k: v["iou"] for k, v in tiles["opening"]["1"].items()}
    den = lambda r: r["dark_crack"]["0"]                               # noqa: E731
    ladder = [_spread(fr, lambda r, s_=s_: r["rung_only_crack"][str(s_)], den=den)
              for s_ in LADDER]
    lad_pct = [100 * x[0] for x in ladder]
    tgrid = [float(t) for t in txm["grid"]]
    THR = float(const["DEFAULT_THRESHOLD"])
    at_ship = txm["curve"][f"{THR:.3f}"]
    best_t = max(tgrid, key=lambda t: txm["curve"][f"{t:.3f}"]["accuracy_pct"])
    trec = [txm["curve"][f"{t:.3f}"]["recall"] for t in tgrid]
    tfp = [1.0 - txm["curve"][f"{t:.3f}"]["specificity_pct"] / 100.0 for t in tgrid]
    kgrid = [float(k) for k in units["grid"]]
    karm = {k: units["pooled"][f"SEM detector, mad_k={k:g}"] for k in kgrid}
    kmar = [karm[k]["margin_pp"] for k in kgrid]
    best_k = max(kgrid, key=lambda k: karm[k]["margin_pp"])
    best_cmin, best_amin = _best(cmin), _best(amin)

    if const["SAM_MODEL_ID"] != "facebook/sam-vit-huge":
        raise SystemExit(f"the TXM backbone is now {const['SAM_MODEL_ID']}; the table "
                         f"row below says 'SAM ViT-H' and would be wrong")

    # ---------------------------------------------------------------- the four kinds
    SWEEP, TEST, MEASURED, FIXED = J.ACCENT, J.G_DARK, J.ACCENT2, J.G_MID
    #: ADOPTED: a value this paper uses and offers no evidence for. It is
    #: not FIXED -- nothing about its construction determines it -- and it
    #: is not SWEPT, because no sweep of it exists on any data reported
    #: here. Saying so is the whole point of this column.
    #: its own colour, because these categories are keyed BY COLOUR: giving
    #: ADOPT the same value as SWEEP silently merged the two and the tally
    #: went on reporting one swept constant after the sweep was removed.
    ADOPT = J.INK
    #: FOUR WORDS ON THE PLATE, and what each one means in the caption file below.
    #: The key used to be four phrases -- twenty words of lettering explaining a
    #: four-colour legend -- and a legend that needs a sentence per entry is a caption
    #: that has wandered into the artwork.
    PROV_GLOSS = {
        SWEEP: "swept on this laboratory's own tiles or frames, in this edition. The "
               "filled square is the value the software uses, and on several of these "
               "it is NOT the best point on the grid -- which is the finding, not an "
               "oversight, and is why the curve is drawn rather than summarised",
        MEASURED: "selected from a measurement recorded in the source repository, "
                  "not from a sweep run here. The measurement is quoted in the caption "
                  "file beside this plate; it is not drawn, because several are two "
                  "values on one frame rather than a grid and a sparkline would dress "
                  "them as something they are not",
        TEST: "settled by a test that had no value to choose -- on or off, which "
              "members -- so there is a verdict but no optimum",
        FIXED: "fixed by construction or set by hand, with no measurement of it on "
               "record in either repository"}
    PROV = [(SWEEP, "swept"), (TEST, "tested"), (MEASURED, "measured"),
            (FIXED, "fixed")]

    MAXDOTS = 14

    def L(ax, xs, ys, *, logx=False, dashed=False, colour=J.ACCENT):
        kw = dict(color=colour, lw=0.9, zorder=4)
        if len(xs) <= MAXDOTS:
            kw |= dict(marker="o", ms=1.9, mfc="white", mec=colour, mew=0.6)
        if dashed:
            kw["dashes"] = (2.8, 1.6)
        ax.plot(xs, ys, "--" if dashed else "-", **kw)
        if logx:
            ax.set_xscale("log")

    def S(ax, x, y, colour=J.ACCENT):
        ax.plot([x], [y], "s", color=colour, ms=3.8, zorder=6,
                markeredgecolor="white", markeredgewidth=0.5)

    #: THE PLOTTERS DRAW AND SET LIMITS; the axis titles and the tick values live in
    #: PANELS below, because in both reference figures every axis carries a full title
    #: with its unit and several numeric tick labels, and those belong where a reader
    #: of this module can see them against each other rather than buried in nine
    #: separate closures.
    def p_madk(ax):
        """The MAD multiplier on this laboratory's frames: recall and precision."""
        L(ax, kgrid_lab, [k_rec[g] for g in kgrid_lab])
        L(ax, kgrid_lab, [k_pre[g] for g in kgrid_lab], dashed=True)
        S(ax, K, k_rec[K])
        S(ax, K, k_pre[K])
        ax.set_xlim(min(kgrid_lab) - 0.4, max(kgrid_lab) + 0.4)
        ax.set_ylim(0.0, 1.05)

    def p_fsig(ax):
        """The background-estimate sigma, the last constant to get a curve."""
        xs = [int(v) for v in FLATSIG_GRID]
        L(ax, xs, [fsig[str(v)] for v in xs], logx=True)
        S(ax, int(sem["flatten_background.sigma"]),
          fsig[str(int(sem["flatten_background.sigma"]))])
        ax.set_xlim(xs[0] * 0.7, xs[-1] * 1.4)
        _v = list(fsig.values())
        _pad = max((max(_v) - min(_v)) * 0.12, 0.003)
        ax.set_ylim(min(_v) - _pad, max(_v) + _pad)

    def p_b(ax):
        gg = [int(g) for g in GATE_GRID]
        L(ax, gg, [gate26[str(g)] for g in gg])
        S(ax, GATE, gate26[str(GATE)])
        ax.set_xlim(-1.5, 41.5); ax.set_ylim(0.15, 0.56)

    def p_c(ax):
        L(ax, [max(float(v), 0.5) for v in CLEANMIN_GRID],
          [cmin[str(v)] for v in CLEANMIN_GRID], logx=True)
        L(ax, [float(v) for v in CANDMIN_GRID], [amin[str(v)] for v in CANDMIN_GRID],
          dashed=True)
        S(ax, CLEAN_MIN, cmin[str(CLEAN_MIN)])
        S(ax, CAND_MIN, amin[str(CAND_MIN)])
        ax.set_xlim(0.4, 4500); ax.set_ylim(0.15, 0.36)

    def p_d(ax):
        L(ax, list(OPEN_GRID), [op8[str(v)] for v in OPEN_GRID])
        L(ax, list(OPEN_GRID), [op4[str(v)] for v in OPEN_GRID], dashed=True)
        S(ax, 1, op8["1"])
        ax.set_xlim(-0.4, max(OPEN_GRID) + 0.4); ax.set_ylim(0.15, 0.36)

    def p_e(ax):
        L(ax, list(LADDER), lad_pct, logx=True)
        #: EVERY RUNG IS MARKED because every rung is in use. The shipped setting here
        #: is not one value on this axis, it is the whole ladder, and a panel with no
        #: filled marker reads as a sweep whose choice was left off.
        for _x, _y in zip(LADDER, lad_pct):
            S(ax, _x, _y)
        ax.set_xlim(LADDER[0] * 0.7, LADDER[-1] * 1.4)
        ax.set_ylim(0.0, max(lad_pct) * 1.25)

    def p_f(ax):
        """One flattening radius at a time, against the seven-rung union.

        The union had no sweep anywhere until this one: it was asserted to be worth
        having. On the same 26 tiles and the same scorer it scores %.4f, against
        %.4f for the best single radius on the grid, so the panel now SHOWS what the
        ladder buys instead of claiming it.
        """
        #: BLUE IS THE SHIPPED THING ON THIS PANEL, which inverts the colours it
        #: used to carry. Everywhere else the blue series holds the value in use and
        #: a blue filled square marks it; here the value in use is the UNION, which
        #: was the orange dashed line, so the one panel where a reader most needs to
        #: find "the setting" was the one where it was not blue. The union is now
        #: Both series are the ELECTRON arm, so both are blue: colour means the arm
        #: now, not "first or second series". The single-radius curve is the dashed
        #: one, matching the key, and the union in use is a solid horizontal
        #: reference, which is what it is.
        xs = [int(v) for v in SINGLE_LADDER_GRID]
        L(ax, xs, [sing[str(v)] for v in xs], logx=True, dashed=True)
        ax.axhline(union_iou, color=J.ACCENT, lw=1.0, zorder=5)
        #: the value in use on this axis is the UNION, not any single radius, so the
        #: dashed line is what the filled square means on the other panels and is
        #: named here rather than left to the footnote.
        #: AND A FILLED SQUARE ON IT, because on this plate a filled square is what
        #: "the value the software uses" looks like and a reader should not have to
        #: learn a second convention for one panel. It sits ON the union line rather
        #: than over any rung: the shipped setting is all seven radii at once, so
        #: there is no single radius to put it on and pinning it to one would say
        #: the opposite of what the panel is for.
        #: ON THE MIDDLE OF THE LINE, not its left end. Put at the first grid value
        #: the square landed in the top-left corner, hard against the panel letter,
        #: and read as a stray mark rather than as a marker sitting on the line --
        #: which is exactly what the author saw. The union has no x of its own, so
        #: the only honest place for it is the middle: the geometric centre of a log
        #: axis, clear of the letter on the left and the "in use" label on the right.
        S(ax, (SINGLE_LADDER_GRID[0] * SINGLE_LADDER_GRID[-1]) ** 0.5, union_iou)
        ax.text(SINGLE_LADDER_GRID[-1], union_iou, "in use ", fontsize=T_TICK,
                ha="right", va="bottom", color=J.ACCENT, zorder=7)
        ax.set_xlim(xs[0] * 0.7, xs[-1] * 1.4)
        #: LIMITS FROM THE DATA, NOT A TYPED FLOOR. This read set_ylim(0.23, ...),
        #: which was inside the range while the region classifier was off. With it on
        #: every single-radius point falls to 0.128-0.216 and the union to 0.229, so
        #: the floor sat above the entire series and the panel rendered EMPTY -- an
        #: axis frame with nothing in it, and no check caught it because an empty axis
        #: draws no text and overlaps nothing.
        _vals = list(sing.values()) + [union_iou]
        _lo, _hi = min(_vals), max(_vals)
        _pad = max((_hi - _lo) * 0.12, 0.004)
        ax.set_ylim(_lo - _pad, _hi + _pad)

    def p_g(ax):
        xs = [int(v) for v in CLOSE_GRID]
        L(ax, xs, [clo[str(v)] for v in xs])
        S(ax, int(sem["clean_mask.close_radius"]),
          clo[str(int(sem["clean_mask.close_radius"]))])
        ax.set_xlim(-0.5, max(xs) + 0.5)
        ax.set_ylim(min(clo.values()) * 0.995, max(clo.values()) * 1.005)

    def p_h(ax):
        xs = [float(v) for v in DENOISE_GRID]
        L(ax, xs, [dns[str(v)] for v in xs])
        sig = float(sem["segment_dark_regions.denoise_sigma"])
        S(ax, sig, dns[str(sig)])
        ax.set_xlim(-0.2, max(xs) + 0.2)
        ax.set_ylim(min(dns.values()) * 0.99, max(dns.values()) * 1.01)

    def p_i(ax):
        L(ax, tgrid, trec, colour=J.ACCENT2)
        L(ax, tgrid, tfp, dashed=True, colour=J.ACCENT2)
        S(ax, THR, at_ship["recall"], colour=J.ACCENT2)
        ax.set_xlim(0.03, 0.97); ax.set_ylim(0.0, 1.0)

    def p_j(ax):
        ys = [cv["f17_mean_iou"], cv["hybrid_mean_iou"], cv["ens_mean_iou"]]
        L(ax, [0, 1, 2], ys, colour=J.ACCENT2); S(ax, 2, ys[2], colour=J.ACCENT2)
        ax.set_xlim(-0.35, 2.35); ax.set_ylim(0.0, 1.0)

    def p_k(ax):
        """What a SAM tile is: 1024 px squares at stride 896, overlapping by 128."""
        TILE, STR = int(const["TILE"]), int(const["TILE_STRIDE"])
        OV = TILE - STR
        span = 2 * STR + TILE
        ax.set_xlim(-0.02 * span, 1.02 * span)
        # HEADROOM FOR THE PANEL LETTER. At a ylim of 1.0 the bold 'h' printed on top
        # of the stride callout, which the control below now also measures.
        ax.set_ylim(0.0, 1.34)
        for i, c in enumerate((J.ACCENT2, J.ACCENT2, J.ACCENT2)):
            ax.add_patch(Rectangle((i * STR, 0.30), TILE, 0.40, facecolor=c,
                                   alpha=0.22, edgecolor=c, lw=0.6, zorder=2 + i))
        for k_ in (0, 1):
            ax.add_patch(Rectangle((STR + k_ * STR, 0.30), OV, 0.40, facecolor=J.INK,
                                   alpha=0.20, edgecolor="none", zorder=6))
        ax.annotate("", xy=(0, 0.17), xytext=(TILE, 0.17),
                    arrowprops=dict(arrowstyle="<|-|>", lw=0.6, color=J.INK,
                                    mutation_scale=4.5), zorder=7)
        ax.text(TILE / 2.0, 0.08, "%d" % TILE, fontsize=T_TICK, ha="center",
                va="center", color=J.INK)
        ax.annotate("", xy=(0, 0.83), xytext=(STR, 0.83),
                    arrowprops=dict(arrowstyle="<|-|>", lw=0.6, color=J.INK,
                                    mutation_scale=4.5), zorder=7)
        ax.text(STR / 2.0, 0.92, "%d" % STR, fontsize=T_TICK, ha="center",
                va="center", color=J.INK)
        ax.text(STR + OV / 2.0, 0.50, "%d" % OV, fontsize=T_TICK, ha="center",
                va="center", color=J.INK, zorder=8)

    def p_l(ax):
        #: ORANGE, because it is a transmission panel. It used to be blue on the old
        #: rule that the second colour meant "a second series"; colour now means the
        #: arm, and this panel asks what the ELECTRON arm's k does on TRANSMISSION
        #: frames, which is a transmission measurement and sits under that heading.
        L(ax, kgrid, kmar, colour=J.ACCENT2)
        ax.axhline(0.0, color=J.INK, lw=0.7, zorder=5)
        S(ax, K, karm[K]["margin_pp"], colour=J.ACCENT2)
        ax.set_xlim(min(kgrid) - 0.4, max(kgrid) + 0.4)
        ax.set_ylim(min(kmar) * 1.15, abs(min(kmar)) * 0.18)

    _f0, _f1 = min(fsig.values()), max(fsig.values())
    _lo_l = round(min(kmar) * 1.15)
    _hi_e = round(max(lad_pct), 1)

    #: (arm, letter, x title, y title, plotter, x ticks, x labels, y ticks, y labels)
    #: TWELVE PANELS, NOT NINE. The author's standing objection was that the plate did
    #: not show how each setting was CHOSEN, and for three of them the honest answer
    #: used to be that nothing had ever been measured. Three were sweepable on the
    #: same 26 tiles and the same scorer as the rest, so they were swept, and two of
    #: the three came back saying the shipped value is not the best one on its own
    #: grid -- which is the kind of thing this plate exists to report.
    _c0, _c1 = min(clo.values()), max(clo.values())
    _d0, _d1 = min(dns.values()), max(dns.values())
    _s1 = max(max(sing.values()), union_iou)
    #: THIRTEEN PANELS, and every constant on this plate that is not fixed by
    #: construction now has one. Two were added when the author refused the word
    #: "adopted" and asked for the sweeps to be run instead of the provenance
    #: merely described. Both were run; both show the shipped value off the grid
    #: best, which is the finding and the reason each gets a curve.
    #: described: the MAD multiplier, swept on this laboratory's own frames rather
    #: than on the removed public collection, and the background-estimate sigma,
    #: which had no sweep anywhere until this edition.
    PANELS = [
        ("SEM", "a", "MAD multiplier $k$", "rate", p_madk,
         [3, 6, 10], ["3", "6", "10"], [0, 0.5, 1], ["0", "0.5", "1"]),
        ("SEM", "b", "darkness gate (DN)", "IoU", p_b,
         [0, 20, 40], ["0", "20", "40"], [0.2, 0.35, 0.5], ["0.2", "0.35", "0.5"]),
        ("SEM", "c", "area floor (px)", "IoU", p_c,
         [1, 100, 3200], ["1", "10$^2$", "3200"], [0.2, 0.3], ["0.2", "0.3"]),
        ("SEM", "d", "opening radius (px)", "IoU", p_d,
         [0, 3, 6], ["0", "3", "6"], [0.2, 0.3], ["0.2", "0.3"]),
        ("SEM", "e", "ladder rung (px)", "unique (%)", p_e,
         [5, 40, 320], ["5", "40", "320"], [0, _hi_e], ["0", "%g" % _hi_e]),
        ("SEM", "f", "one radius only (px)", "IoU", p_f,
         [5, 40, 320], ["5", "40", "320"], [0.25, round(_s1, 2)],
         ["0.25", "%.2f" % round(_s1, 2)]),
        ("SEM", "g", "closing radius (px)", "IoU", p_g,
         [0, 6, 12], ["0", "6", "12"], [round(_c0, 3), round(_c1, 3)],
         ["%.3f" % _c0, "%.3f" % _c1]),
        ("SEM", "h", "denoise sigma", "IoU", p_h,
         [0, 2, 4], ["0", "2", "4"], [round(_d0, 2), round(_d1, 2)],
         ["%.2f" % _d0, "%.2f" % _d1]),
        ("SEM", "i", "flattening sigma (px)", "IoU", p_fsig,
         [5, 40, 320], ["5", "40", "320"], [round(_f0, 3), round(_f1, 3)],
         ["%.3f" % _f0, "%.3f" % _f1]),
        ("TXM", "j", "threshold", "rate", p_i,
         [0.05, 0.5, 0.95], ["0.05", "0.5", "0.95"], [0, 0.5, 1],
         ["0", "0.5", "1"]),
        ("TXM", "k", "members", "IoU", p_j,
         [0, 2], ["17-ch", "mean"], [0, 0.5, 1], ["0", "0.5", "1"]),
        ("TXM", "l", "SAM tile and stride (px)", "", p_k, [], [], [], []),
        ("TXM", "m", "$k$ on TXM", "margin (pp)", p_l,
         [3, 10], ["3", "10"], [_lo_l, 0], ["%d" % _lo_l, "0"]),
    ]

    # ------------------------------------------- EVERY constant, as a printed table
    #: A PRINTED TABLE, WHICH IS WHAT THIS IS. Three editions tried to make the
    #: parameter inventory into artwork -- loose value strips, a ruled block with
    #: colour swatches, then stage boxes joined by arrows -- and each one read as a
    #: figure that had been filled with words. Neither reference figure contains
    #: anything of the sort, because an inventory of settings is a TABLE, and a table
    #: in these journals is plain: a top rule, a header, a header rule, the rows, a
    #: bottom rule. No boxes, no arrows, no colour, no key. How each value was settled
    #: is one letter in its own narrow column, defined in a single footnote, which is
    #: the normal way a printed table carries that kind of flag.
    CODE = {SWEEP: "S", TEST: "T", MEASURED: "M", FIXED: "F"}

    def R(name, value, prov, letter=None):
        return (name, value, prov, letter)

    pct = lambda a, b: "%g/%g" % (a, b)                                # noqa: E731
    SEM_ROWS = [
        R("contrast window (%)", pct(sem["load_as_uint8.low_pct"],
                                     sem["load_as_uint8.high_pct"]), FIXED),
        R("contrast, %d frames (%%)" % len(GENTLE), pct(*GENTLE_PCT), FIXED),
        R("databar search depth", "%.2f" % sem["_detect_databar_top.search_frac"],
          FIXED),
        R("databar window (rows)", "%d" % sem["_detect_databar_top.window"], FIXED),
        R("databar sd ratio", "%.2f" % sem["_detect_databar_top.std_ratio"], FIXED),
        R("databar mean ratio", "%.2f" % sem["_detect_databar_top.mean_ratio"], FIXED),
        R("field-of-view gate (DN)", "%d" % sem["find_field_of_view.bright_thresh"],
          FIXED),
        R("field-of-view shrink", "%.2f" % sem["find_field_of_view.shrink_frac"],
          FIXED),
        R("field-of-view floor", "%.2f" % sem["find_field_of_view.min_keep_frac"],
          FIXED),
        R("flattening clip (%)", pct(sem["flatten_background.low_pct"],
                                     sem["flatten_background.high_pct"]), SWEEP),
        R("scale ladder (px)", "%d–%d" % (LADDER[0], LADDER[-1]), SWEEP, "e"),
        R("ladder rungs", "%d" % len(LADDER), SWEEP, "e"),
        R("decimate above (px)", "%d" % int(DO.DECIMATE_ABOVE_SIGMA), SWEEP),
        R("multiscale union", "on" if DO.USE_MULTISCALE_UNION else "off",
          TEST, "f"),
        #: ADOPTED, EACH WITH A PANEL. These nine carry no recorded provenance in
        #: either repository -- no sweep chose them -- and each is swept HERE, on this
        #: laboratory's own tiles and frames. A panel therefore shows what moving the
        #: value does, never why the value is what it is, and the ref. column marks
        #: the constant swept HERE so selection and sensitivity are not confused.
        R("denoise sigma", "%.1f" % sem["segment_dark_regions.denoise_sigma"],
          SWEEP, "h"),
        R("MAD multiplier k", "%.1f" % K, SWEEP, "a"),
        R("darkness gate (DN)", "%d" % GATE, SWEEP, "b"),
        R("opening radius (px)", "1", SWEEP, "d"),
        R("closing radius (px)", "%d" % sem["clean_mask.close_radius"], SWEEP, "g"),
        R("connectivity", "8", SWEEP, "d"),
        R("clean area floor (px)", "%d" % CLEAN_MIN, SWEEP, "c"),
        R("candidate floor (px)", "%d" % CAND_MIN, SWEEP, "c"),
        R("flattening sigma (px)", "%g" % sem["flatten_background.sigma"],
          SWEEP, "i"),
        R("region classifier", "on" if DO.USE_REGION_CLASSIFIER else "off", TEST),
    ]
    TXM_ROWS = [
        R("recipe", str(const["RECIPE"]), FIXED),
        R("members averaged", "2", TEST, "k"),
        R("feature channels", "%d" % stats["n_features"], FIXED),
        R("backbone", "SAM ViT-H", FIXED),
        R("SAM tile (px)", "%d" % const["TILE"], FIXED, "l"),
        R("tile stride (px)", "%d" % const["TILE_STRIDE"], MEASURED, "l"),
        R("embedding stride (px)", "%d" % const["EMB_STRIDE"], FIXED),
        R("probability threshold", "%.2f" % THR, TEST, "j"),
        #: NOT A SETTING ANYONE CHOSE: the electron arm's multiplier carried onto
        #: transmission data, where panel (k) shows every value on the grid scoring
        #: below an empty mask. The row exists so the plate cannot be read as though
        #: the two arms share a constant.
        R("SEM k on TXM", "none", SWEEP, "m"),
        R("correction floor", "%.2f" % const["CORRECTION_FLOOR"], MEASURED),
        R("speck floor (px)", "%d" % const["MIN_BLOB_PX"], MEASURED),
        R("hole fill (px)", "%d" % const["FILL_HOLES_MAX_PX"], MEASURED),
        R("narrowing window (px)", "%d" % const["TIGHTEN_WINDOW"], MEASURED),
        R("narrowing core", "%.2f" % const["TIGHTEN_MIN_CORE"], MEASURED),
        R("width clip", "on" if const["WIDTH_CLIP"] else "off", TEST),
        R("clip radius (px)", "%d" % const["WIDTH_CLIP_RADIUS"], SWEEP),
        R("clip directions", "%d" % const["WIDTH_CLIP_DIRS"], SWEEP),
        R("clip probes", "%d" % const["WIDTH_CLIP_PROBES"], FIXED),
        R("clip recentre (px)", "%d" % const["WIDTH_CLIP_RECENTRE"], SWEEP),
        R("clip peak sigma", "%.1f" % const["WIDTH_CLIP_PEAK_SIGMA"], MEASURED),
        R("clip background (px)", "/".join(str(w) for w in
                                           const["WIDTH_CLIP_BG_WINDOWS"]), SWEEP),
        R("clip min points", "%d" % const["WIDTH_CLIP_MIN_MEASURED"], FIXED),
        R("clip IDW neighbours", "%d" % const["WIDTH_CLIP_IDW_K"], SWEEP),
        R("straight min area (px)", "%d" % const["STRAIGHT_MIN_PX"], FIXED),
        R("straight min aspect", "%.1f" % const["STRAIGHT_MIN_ASPECT"], FIXED),
        R("straight max wander (px)", "%.1f" % const["STRAIGHT_MAX_WANDER"],
          MEASURED),
    ]

    # ---- geometry, in inches ---------------------------------------------------
    W = J.PAGEW
    MX, NCOL, COLGAP = 0.05, 3, 0.185
    PW = (W - 2 * MX - (NCOL - 1) * COLGAP) / NCOL
    YLABW = 0.42                       # y title + y tick labels
    PLOTH, XTICKH, XLABH, ROWGAP = 0.72, 0.17, 0.20, 0.16
    PANELROW = PLOTH + XTICKH + XLABH + ROWGAP
    ARMH, LEAD, TOPM, FOOTH = 0.20, 0.132, 0.07, 0.62
    TCOL, TGAP = 3, 0.16               # the table's column groups

    def _tcolw(rows):
        nm = max(_tw(r[0] + ("" if r[3] is None else "  (%s)" % r[3]), T_TICK)
                 for r in rows)
        vl = max(_tw(r[1], T_TICK) for r in rows)
        return nm, vl

    def table_block(y0, rows, title):
        """One printed table: top rule, header, header rule, rows, bottom rule."""
        per = -(-len(rows) // TCOL)
        cw = (W - 2 * MX - (TCOL - 1) * TGAP) / TCOL
        nmw, vlw = _tcolw(rows)
        codew = _tw("ref.", T_TICK, bold=False) + 0.04
        T(MX, y0, title, T_NAME, weight="bold")
        y0 += LEAD + 0.02
        for c in range(TCOL):
            x = MX + c * (cw + TGAP)
            chunk = rows[c * per:(c + 1) * per]
            if not chunk:
                continue
            rule(x, x + cw, y0, lw=0.8)
            T(x, y0 + 0.030, "parameter", T_TICK, color=J.G_DARK)
            T(x + cw - codew, y0 + 0.030, "value", T_TICK, color=J.G_DARK,
              ha="right")
            T(x + cw, y0 + 0.030, "ref.", T_TICK, color=J.G_DARK, ha="right")
            rule(x, x + cw, y0 + LEAD + 0.012, lw=0.5)
            yy = y0 + LEAD + 0.040
            for name, value, prov, letter in chunk:
                T(x, yy, name if letter is None else "%s  (%s)" % (name, letter),
                  T_TICK)
                T(x + cw - codew, yy, value, T_TICK, ha="right")
                T(x + cw, yy, CODE[prov], T_TICK, ha="right", color=J.G_DARK)
                yy += LEAD
            rule(x, x + cw, yy + 0.010, lw=0.8)
        return y0 + LEAD + 0.040 + per * LEAD + 0.030

    sem_p = [q for q in PANELS if q[0] == "SEM" and arm == "SEM"]
    txm_p = [q for q in PANELS if q[0] == "TXM" and arm == "TXM"]
    ARM_PANELS = [q for q in PANELS if q[0] == arm]
    sem_rows = -(-len(sem_p) // NCOL)
    txm_rows = -(-len(txm_p) // NCOL)
    _srows = SEM_ROWS if arm == "SEM" else []
    _trows = TXM_ROWS if arm == "TXM" else []
    sem_t_h = ((LEAD + 0.02 + LEAD + 0.040 + (-(-len(_srows) // TCOL)) * LEAD + 0.030)
               if _srows else 0.0)
    txm_t_h = ((LEAD + 0.02 + LEAD + 0.040 + (-(-len(_trows) // TCOL)) * LEAD + 0.030)
               if _trows else 0.0)
    #: the cross-arm comparison block: its gap, its heading, its axes and the gap under
    CMPH = (0.30 + ARMH + 0.86 + 0.36 + 0.30 + 0.16) if arm == "TXM" else 0.0
    _armh_sem = ARMH if arm == "SEM" else 0.0
    _armh_txm = ARMH if arm == "TXM" else 0.0
    H = (TOPM + _armh_sem + sem_rows * PANELROW + sem_t_h + (0.22 if arm == "SEM" else 0)
         + _armh_txm + txm_rows * PANELROW + txm_t_h + CMPH + FOOTH)
    fig = plt.figure(figsize=(W, H))
    texts = []

    def T(x, y, t, size, *, weight="normal", color=J.INK, ha="left", va="top"):
        a = fig.text(x / W, 1.0 - y / H, t, fontsize=size, ha=ha, va=va, color=color,
                     fontweight=weight, linespacing=1.15)
        texts.append(a)
        return a

    def rule(x0, x1, y, lw=0.5, colour=J.INK):
        fig.add_artist(plt.Line2D([x0 / W, x1 / W], [1.0 - y / H] * 2,
                                  transform=fig.transFigure, color=colour, lw=lw,
                                  zorder=3, solid_capstyle="butt"))

    panel_axes = []

    def panels(y0, items):
        """Lay the panels out `NCOL` across, wrapping. The SEM arm has eight of them
        now and one row of eight would be 0.75 in per panel, where an axis title does
        not fit."""
        #: A SHORT ROW IS CENTRED, NOT LEFT-ALIGNED AGAINST A HOLE. The grid is NCOL
        #: wide and neither arm fills it: the electron arm has two panels since its
        #: one swept constant lost its panel with the collection that swept it, and
        #: the transmission arm has three. Laid out from the left, each row ended in
        #: empty columns and the author read the plate as truncated -- as though a
        #: panel had failed to draw. Centring says the row is the whole row.
        _n_last = len(items) % NCOL or NCOL
        for i, (_arm, letter, xlab, ylab, fn, xt, xl, yt, yl) in enumerate(items):
            r, c = divmod(i, NCOL)
            _in_row = NCOL if (r + 1) * NCOL <= len(items) else _n_last
            x = MX + c * (PW + COLGAP) + (NCOL - _in_row) * (PW + COLGAP) / 2.0
            ax = fig.add_axes([(x + YLABW) / W,
                               1.0 - (y0 + r * PANELROW + PLOTH) / H,
                               (PW - YLABW) / W, PLOTH / H])
            panel_axes.append(ax)
            fn(ax)
            ax.minorticks_off()
            ax.set_xticks(xt)
            ax.set_xticklabels(xl)
            ax.set_yticks(yt)
            ax.set_yticklabels(yl)
            ax.tick_params(which="both", length=2.0, width=0.5, pad=1.6,
                           labelsize=T_TICK, top=False, right=False, direction="out")
            for sp in ax.spines.values():
                sp.set_linewidth(0.5)
            if ylab:
                ax.set_ylabel(ylab, fontsize=T_TICK, labelpad=1.6)
            if xlab:
                ax.set_xlabel(xlab, fontsize=T_TICK, labelpad=1.6)
            #: PARENTHESISED, at the author's instruction for every plate in the pack.
            #: This read "no parentheses ... both reference figures letter their panels
            #: exactly so", which was true of the reference figures and is not what this
            #: paper does.
            ax.text(0.035, 0.965, f"({letter})", transform=ax.transAxes, fontsize=T_NAME,
                    fontweight="bold", ha="left", va="top", color=J.INK, zorder=9)

    cmp_axes = []
    y = TOPM
    if arm == "SEM":
        T(MX, y, "SEM arm", T_NAME, weight="bold", color=J.ACCENT)
        y += ARMH
        panels(y, sem_p)
        y += sem_rows * PANELROW
        y = table_block(y, SEM_ROWS, "SEM arm: every constant") + 0.22
    else:
        T(MX, y, "TXM arm", T_NAME, weight="bold", color=J.ACCENT2)
        y += ARMH
        panels(y, txm_p)
        y += txm_rows * PANELROW
        y = table_block(y, TXM_ROWS, "TXM arm: every constant")

    if arm == "TXM":
        # ---- the cross-arm comparison -------------------------------------------------
        #: WHAT ONE CONSTANT COSTS THE OTHER ARM. Every panel above varies a constant inside
        #: one arm. This one asks the question across them, on the constant both arms share:
        #: the MAD multiplier. For each frame, the critical k is the multiplier at which that
        #: frame's painted crack stops separating from its painted not-crack -- below the
        #: shipped k the frame is losing crack the detector could have had.
        #:
        #: The two arms do not sit the same way against the single shipped value, and that
        #: is the finding: the electron frames straddle it and the transmission frames are
        #: almost all under it.
        _CON = json.load(open(CONTRAST_REC))
        y += 0.30
        T(MX, y, "Both arms, one constant", T_NAME, weight="bold", color=J.INK)
        y += ARMH
        cax = fig.add_axes([(MX + 0.52) / W, 1.0 - (y + 0.86) / H,
                            (W - 2 * MX - 0.70) / W, 0.86 / H])
        #: DELIBERATELY NOT IN `panel_axes`. That list is checked one-to-one against the
        #: lettered rows of the two tables, because every panel above sweeps a constant that
        #: the tables name. This one does not sweep a constant -- it compares the two arms
        #: against the one they share -- so it has no row to cite and counting it there would
        #: make the control fail for the right reason about the wrong panel. It IS measured
        #: for text collisions, which is a separate list.
        cmp_axes.append(cax)
        _rng = np.random.default_rng(0)
        _say = []
        for _i, (_arm, _col) in enumerate((("SEM", J.ACCENT), ("TXM", J.ACCENT2))):
            _ks = [f["median_critical_k_crack"] for f in _CON[_arm]["per_frame"]]
            _yy = _i + _rng.uniform(-0.17, 0.17, len(_ks))
            cax.scatter(_ks, _yy, s=9, facecolors="none", edgecolors=_col, linewidths=0.7,
                        zorder=4)
            _med = _CON[_arm]["median_of_median_critical_k_crack"]
            cax.plot([_med, _med], [_i - 0.30, _i + 0.30], color=_col, lw=1.8, zorder=5)
            cax.text(_med, _i + 0.34, f"median {_med:.2f}", color=_col, fontsize=T_TICK,
                     ha="center", va="bottom")
            _n = _CON[_arm]["n_frames"]
            _below = _CON[_arm]["frames_median_critical_k_below_k"]
            _prop = 100 * _CON[_arm]["median_crack_px_proposed_frac"]
            _say.append(f"{_arm}: {_below} of {_n} frames below the shipped k; "
                        f"{_prop:.0f}% of painted crack proposed on the median frame")
        cax.axvline(K, color=J.INK, lw=1.0, dashes=(3.0, 1.8), zorder=6)
        cax.text(K, 1.62, f"shipped k = {K:g}", fontsize=T_TICK, ha="center", va="bottom",
                 color=J.INK)
        cax.set_xlim(0, 10.4)
        cax.set_ylim(-0.6, 1.6)
        cax.set_yticks([0, 1])
        cax.set_yticklabels(["SEM", "TXM"], fontsize=T_TICK)
        cax.set_xticks([0, 2, 4, 6, 8, 10])
        cax.set_xticklabels(["0", "2", "4", "6", "8", "10"], fontsize=T_TICK)
        cax.set_xlabel("critical MAD multiplier $k$ this frame needs", fontsize=T_TICK,
                       labelpad=1.6)
        cax.tick_params(which="both", length=2.0, width=0.5, pad=1.6, top=False,
                        right=False, direction="out")
        for _sp in cax.spines.values():
            _sp.set_linewidth(0.5)
        cax.text(0.012, 0.95, "(n)", transform=cax.transAxes, fontsize=T_NAME,
                 fontweight="bold", ha="left", va="top", color=J.INK)
        y += 0.86 + 0.36
        T(MX, y, "\n".join(_say), T_TICK, color=J.G_DARK)
        y += 0.30

    # one footnote, which is how a printed table carries a flag column
    # TWO LINES. One ran 7 in on a 6.27 in sheet and the plate's own check caught it.
    #
    # BUILT FROM THE SAME MAP THE COLUMN PRINTS, not retyped beside it. This line was a
    # literal string, and when an M letter joined the table the key went on offering a
    # reader three letters to decode four -- the column said M on three rows and nothing
    # on the plate said what M was. A key that is typed cannot be kept in step with a
    # column that is computed, so it is no longer typed.
    KEY_PHRASE = {SWEEP: "swept here", TEST: "settled by a test",
                  MEASURED: "measured in the source, not drawn",
                  FIXED: "fixed by construction, nothing measured"}
    #: SEM_ROWS + TXM_ROWS rather than ROWS: ROWS is assembled further down,
    #: after the tables are drawn, and the footnote is drawn before it.
    _used = {r[2] for r in SEM_ROWS + TXM_ROWS}
    _unkeyed = sorted(CODE[c] for c in _used if c not in KEY_PHRASE)
    if _unkeyed:
        raise SystemExit(f"the table prints {_unkeyed} and the footnote key does not "
                         f"define them; a reader cannot decode the ref. column")
    _key = ";   ".join(f"{CODE[c]} {KEY_PHRASE[c]}" for c, _w in PROV if c in _used)
    #: WHAT THE DASHED LINE IS, PANEL BY PANEL. "Dashed: a second series" was the whole
    #: of the old key, and that is not an explanation -- the second series is a
    #: different quantity in every panel that has one. Colour now means the ARM and
    #: nothing else (blue SEM, orange TXM, throughout the paper), so within a panel the
    #: series are told apart by line style, and the style has to be named.
    T(MX, y + 0.03,
      f"ref.   {_key}.\n"
      "FILLED SQUARE: the value the software uses.   Bracketed letter: the panel "
      "above.\n"
      #: NOT "throughout this paper", which is what this said and which is false.\n      #: Figure 1 colours the pipeline STAGE -- blue is crack found so far and\n      #: orange is pixels the step removes, in both arms -- and Figure 4 colours\n      #: the operator VERDICT. Those are not arm colours and should not be. The\n      #: rule is about panels that distinguish the arms, and it has to say so.\n      "WHERE COLOUR DISTINGUISHES THE ARMS it is blue SEM, orange TXM.\\n"
      #: ONLY THIS PLATE'S PANELS. Listing all five on both sheets sent a reader of the
      #: transmission plate looking for panels (a), (c), (d) and (f), which are on the
      #: electron one -- a reference the split created and nothing would have caught.
      + _DASHED_KEY[arm],
      T_TICK, color=J.G_DARK)

    # ---- the controls ----------------------------------------------------------
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    pw, ph = fig.canvas.get_width_height()
    tol = fig.dpi / 72.0
    #: AXIS TITLES AND TICK LABELS ARE TEXT ON THE SHEET, and until now the check did
    #: not look at them: it measured only the strings this module placed itself. The
    #: last panel's axis title ran off the right edge of the plate and the check
    #: reported PASS, because the title belongs to the axes and not to `texts`. Every
    #: visible string is measured now, wherever it came from.
    measured = list(texts)
    for a_ in panel_axes:
        measured.append(a_.xaxis.label)
        measured.append(a_.yaxis.label)
        measured.extend(a_.get_xticklabels())
        measured.extend(a_.get_yticklabels())
        measured.extend([t_ for t_ in a_.texts])
    boxes = []
    for t in measured:
        if not t.get_text().strip() or not t.get_visible():
            continue
        try:
            boxes.append((t.get_text().strip().replace("\n", " ")[:38],
                          t.get_window_extent(renderer=rend)))
        except Exception:
            continue
    bad = [f"{boxes[i][0]!r} x {boxes[k][0]!r}"
           for i in range(len(boxes)) for k in range(i + 1, len(boxes))
           if (min(boxes[i][1].x1, boxes[k][1].x1)
               - max(boxes[i][1].x0, boxes[k][1].x0) > tol
               and min(boxes[i][1].y1, boxes[k][1].y1)
               - max(boxes[i][1].y0, boxes[k][1].y0) > tol)]
    off = [f"{n!r}" for n, e in boxes
           if e.x0 < -tol or e.x1 > pw + tol or e.y0 < -tol or e.y1 > ph + tol]
    if bad or off:
        raise SystemExit(("%d overlapping label(s): " % len(bad) + "; ".join(bad[:6])
                          if bad else "")
                         + ("  %d off the sheet: " % len(off) + "; ".join(off[:6])
                            if off else ""))
    print(f"  CONTROL {len(boxes)} drawn strings, none overlapping, none off the "
          f"sheet: PASS")

    ROWS = [("SEM", r) for r in SEM_ROWS] + [("TXM", r) for r in TXM_ROWS]
    drawn = {q[1] for q in ARM_PANELS}
    cited = {r[3] for _a, r in ROWS if r[3] and _a == arm}
    if drawn != cited:
        raise SystemExit(f"panels drawn {sorted(drawn)} but the tables cite "
                         f"{sorted(cited)}")
    if len(panel_axes) != len(ARM_PANELS):
        raise SystemExit(f"{len(panel_axes)} axes drawn for {len(ARM_PANELS)} "
                         f"{arm} panels")
    #: the comparison axis rides with TXM and is accounted for rather than ignored
    _want_cmp = 1 if arm == "TXM" else 0
    if len(cmp_axes) != _want_cmp:
        raise SystemExit(f"{len(cmp_axes)} cross-arm comparison axes on the {arm} "
                         f"plate, expected {_want_cmp}")
    print(f"  CONTROL {len(drawn)} panels, every one of them a row of its table, and "
          f"every lettered row a panel: PASS")

    #: AND EVERY PANEL MUST HAVE SOMETHING VISIBLE INSIDE ITS OWN AXES. Panel (f)
    #: shipped EMPTY: its y-limits were a typed floor of 0.23 chosen while the region
    #: classifier was off, and with it on the entire series fell below that floor and
    #: was clipped away. Nothing caught it -- an empty axis draws no text, so the
    #: label and overlap checks see a clean sheet, and the caption still described a
    #: curve that was not there. A panel with a frame and no data is the one failure
    #: this plate had no way to notice.
    import numpy as _np
    _bare = []
    for _lt, _ax in panel_axes.items() if isinstance(panel_axes, dict) \
            else enumerate(panel_axes):
        _x0, _x1 = sorted(_ax.get_xlim())
        _y0, _y1 = sorted(_ax.get_ylim())
        _seen = 0
        for _ln in _ax.get_lines():
            _xd, _yd = _np.asarray(_ln.get_xdata(), float), \
                _np.asarray(_ln.get_ydata(), float)
            if _xd.size == 0:
                continue
            _in = ((_xd >= _x0) & (_xd <= _x1) & (_yd >= _y0) & (_yd <= _y1))
            _seen += int(_in.sum())
        _seen += sum(1 for _c in _ax.collections)
        _seen += sum(1 for _pt in _ax.patches)
        if _seen == 0:
            _bare.append(str(_lt))
    if _bare:
        raise SystemExit(f"{len(_bare)} panel(s) have an axis frame and nothing "
                         f"visible inside it: " + ", ".join(_bare))
    print(f"  CONTROL every panel has data inside its own limits: PASS")
    n_rows = len(ROWS)
    tally = {"total": n_rows,
             "swept": len([1 for _a, r in ROWS if r[2] == SWEEP]),
             "test": len([1 for _a, r in ROWS if r[2] == TEST]),
             "measured": len([1 for _a, r in ROWS if r[2] == MEASURED]),
             "fixed": len([1 for _a, r in ROWS if r[2] == FIXED]),
             }
    if tally != DOCSTRING_TALLY:
        raise SystemExit(f"this module's docstring states {DOCSTRING_TALLY} and the "
                         f"tables now hold {tally}; fix whichever is wrong rather "
                         f"than shipping a figure whose own description is false")
    print(f"  CONTROL the tally this module's docstring states is the tally the two "
          f"tables hold ({tally}): PASS")
    #: F is the one letter that asserts an ABSENCE -- no measurement of this constant
    #: anywhere -- so every row carrying it has to say why that is true. Eight rows
    #: carried F with a measurement sitting in their own source file, and nothing in
    #: this build could notice, because the only check was on the COUNTS.
    #: THE SWEPT ROWS WITHOUT A PANEL owe the same debt F rows do, for the same reason:
    #: a reader cannot see the evidence, so the module has to carry it. Without this the
    #: new dict would rot exactly as the F reasons did -- a row moves letter and its
    #: paragraph is left behind describing a state that no longer holds.
    _s_nopanel = sorted(r[0] for _a, r in ROWS if r[2] == SWEEP and not r[3])
    _s_missing = [n for n in _s_nopanel if n not in WHY_THE_SWEPT_VALUE_STANDS]
    _s_stale = sorted(set(WHY_THE_SWEPT_VALUE_STANDS) - set(_s_nopanel))
    if _s_missing or _s_stale:
        raise SystemExit(
            "WHY_THE_SWEPT_VALUE_STANDS must hold one line for each swept row that has "
            "no panel, and nothing else.\n  swept, undrawn, unexplained: "
            + (", ".join(_s_missing) or "-")
            + "\n  explained but no longer a swept undrawn row: "
            + (", ".join(_s_stale) or "-"))
    print(f"  CONTROL each of the {len(_s_nopanel)} swept rows with no panel states what "
          f"its sweep found: PASS")

    _f_rows = sorted(r[0] for _a, r in ROWS if r[2] == FIXED)
    _missing = [n for n in _f_rows if n not in WHY_F_IS_TRUE]
    _stale = sorted(set(WHY_F_IS_TRUE) - set(_f_rows))
    if _missing or _stale:
        raise SystemExit(
            "WHY_F_IS_TRUE must hold one line for each row lettered F, and nothing "
            "else.\n  lettered F with no reason given: " + (", ".join(_missing) or "-")
            + "\n  a reason for a row no longer lettered F: "
            + (", ".join(_stale) or "-")
            + "\nF claims no measurement of the constant exists in either repository. "
              "If one does, the row is M, not F.")
    print(f"  CONTROL each of the {len(_f_rows)} rows lettered F states why no "
          f"measurement of it exists: PASS")
    print(f"  CONTROL {n_rows} constants on the plate ({len(SEM_ROWS)} SEM, "
          f"{len(TXM_ROWS)} TXM), every value parsed from the shipped source or read "
          f"off a record: PASS")
    J.save(fig, os.path.join(OUT, PLATE_NAME[arm] + ".png"))
    return dict(
        figure_height_in=H, n_text=len(boxes), n_placed=len(boxes),
        n_constants_on_the_plate=n_rows, panel_letters=sorted(drawn), tally=tally,
        key_on_the_plate={CODE[c]: PROV_GLOSS[c] for c, _w in PROV},
        #: `letter` as well as the gloss, so the two printed tables can be rebuilt
        #: from this record without re-deriving which letter a row carries.
        constants=[{"arm": arm, "name": r[0], "value": r[1], "panel": r[3],
                    "letter": CODE[r[2]], "how_fixed": PROV_GLOSS[r[2]]}
                   for arm, r in ROWS],
        key_phrases={CODE[c]: KEY_PHRASE[c] for c, _w in PROV},
        terms=[str(s) for s in LADDER], pooled=lad_pct,
        median=[100 * x[1] for x in ladder], p25=[100 * x[2] for x in ladder],
        p75=[100 * x[3] for x in ladder],
        frames_with_a_nonzero_share=[x[4] for x in ladder],
        frames_with_a_denominator=[x[5] for x in ladder],
        shared_pct=100.0 - sum(lad_pct),
        best_clean_min=best_cmin, best_cand_min=best_amin,
        best_txm_threshold=best_t, txm_at_shipped=at_ship,
        best_k_on_txm=best_k, best_margin_on_txm_pp=karm[best_k]["margin_pp"])


def _concentration(fr, ladder):
    """Is a radius's pooled bar just the frames that dominate the denominator?

    Answered rather than assumed: the two frames holding most of the denominator are
    named, and for each radius the share of its own unique pixels that its own two
    largest contributors hold. If those were the same two frames the pooled bar would be
    reporting them; they are not.
    """
    den = sorted(fr, key=lambda r: r["dark_crack"]["0"], reverse=True)
    tot = sum(r["dark_crack"]["0"] for r in fr)
    out = {"two_frames_holding_most_of_the_denominator":
           [{"frame": r["frame"], "pct_of_denominator": 100.0 * r["dark_crack"]["0"]
             / max(tot, 1)} for r in den[:2]],
           "per_radius": {}}
    for s_ in ladder:
        key = str(s_)
        tops = sorted(fr, key=lambda r, k=key: r["rung_only_crack"][k], reverse=True)[:2]
        tot_s = sum(r["rung_only_crack"][key] for r in fr)
        out["per_radius"][key] = {
            "its_own_two_largest_contributors": [r["frame"] for r in tops],
            "share_of_its_unique_px_they_hold_pct":
                100.0 * sum(r["rung_only_crack"][key] for r in tops) / max(tot_s, 1),
            "same_frames_as_the_denominator":
                sorted(r["frame"] for r in tops) == sorted(r["frame"] for r in den[:2])}
    return out


def _crossing(wf, grid):
    """Where the marked/annotated area ratio passes 1, read off the grid rather than
    typed into a sentence that a later sweep could falsify."""
    gs = sorted(float(g) for g in grid)
    for a, b in zip(gs, gs[1:]):
        ra, rb = wf["per_k"][str(a)]["area_ratio"], wf["per_k"][str(b)]["area_ratio"]
        if ra >= 1.0 > rb:
            return f"between k = {a:g} ({ra:.3f}) and k = {b:g} ({rb:.3f})"
    return "nowhere on this grid"


def sidecar(tiles, frames, madk, madp, dead, txm, units, scores, stats, const, bars):
    """Every number the plate prints, with the file or the function that produced it.

    ONE BLOCK PER LETTERED ROW, and every block names its arm, its value, its verdict,
    its unit set and the record the row was drawn from. A reader who wants to check a
    row should not have to guess which of three unit sets it sits on.
    """
    wf = madk["sets"]["whole_fields"]
    fr = [r for r in frames["frames"] if "error" not in r]
    cv = scores["cross_validated"]
    cmp_path = os.path.join(_paths.REPO, "docs", "slides", "comparison.json")
    comp = {r["arm"]: r for r in json.load(open(cmp_path))["rows"]}
    THR = float(const["DEFAULT_THRESHOLD"])

    def chain_pooled(t_dn, field):
        return _pooled(fr, lambda r, t=t_dn, f=field: r["chain"][str(t)][f])

    painted = sum(r["crack"] for r in fr)
    kept = sum(r["chain"][str(GATE)]["kept"] for r in fr)
    karm = {k: units["pooled"][f"SEM detector, mad_k={float(k):g}"] for k in units["grid"]}
    k_margin = karm[K]["margin_pp"] if K in karm else float("nan")

    rec = {
        "figure": NAME + ".png",
        #: WHICH PANELS ARE NOT AT THE SHIPPED SETTING, named because they cannot be
        #: brought to it. An audit of this plate found two.
        "panels_measured_without_the_region_classifier": {
            "l": ("the SEM multiplier carried onto transmission data. Its record, "
                  "docs/figures/txm_background_units.json, is the same area floor. "
                  "That is deliberate -- the SEM region classifier is not part of the "
                  "TXM pipeline -- but the panel is labelled as the SEM detector and "
                  "the curve would move if it were applied."),
            "everything_else": ("panels b to h sweep through both_modalities.emit and "
                                "are at the shipped setting; their two records carry "
                                "use_region_classifier true and a hash that includes "
                                "the flag, so a stale one aborts the build")},
        "column_class": "double, Elsevier 190 mm, but drawn at the paper's own text "
                        "block (journal_style.PAGEW) because it is a full-height table. "
                        "journal_style.COLUMN_CLASS carries no row for this plate and is "
                        "not edited from here.",
        "layout": "per arm, a row of sweep panels over a printed table of every "
                  "constant that arm reads. The panels carry a full axis title with "
                  "its unit and numeric tick labels on both axes, and a lowercase bold "
                  "letter inside the axes at the top left. The table is plain -- top "
                  "rule, header, header rule, rows, bottom rule -- with how each value "
                  "was settled as one letter in a ref. column, defined in one footnote "
                  "under the plate. Both conventions are copied from the two published "
                  "figures cited in docs/FIGURE_CONVENTIONS_FROM_PUBLISHED_WORK.md; "
                  "`key_on_the_plate` below expands the ref. codes.",
        "what": "one row per constant of BOTH detectors, grouped by how the constant was "
                "fixed. Each row names the parameter in words, prints the value the "
                "paper runs at, shows the evidence that exists for it as a sparkline "
                "with that value marked, and states in words how it was decided and on "
                "which unit set.",
        "why_a_table": "the previous edition was six unlabelled curves. A reader could "
                       "not tell which parameter a panel was about, which of the two "
                       "models it belonged to, or what value had been chosen, and the "
                       "TXM arm was absent entirely.",
        "reading_rule": "THE SPARKLINE COLUMN IS A STRIP, NOT AN AXES: no tick marks and "
                        "no y tick labels. The swept range is printed under each strip "
                        "and the measurand with its full span opens the note beside it, "
                        "so no information a tick label would have carried is lost. A "
                        "solid grey rule and a filled square mark the value the paper "
                        "runs at, in every row that has one on an axis; the one dotted "
                        "rule, in (a), is the value the application itself runs.",
        "the_point_of_the_grouping": "of the eleven panels and the constants they sweep, NONE "
                                     "was selected by a sweep on data this paper "
                                     "reports. Two were settled by a test with no "
                                     "value to choose. "
                                     "The rest were taken with no recorded "
                                     "provenance and swept only after the fact, or never "
                                     "swept at all. The band headings are that fact.",

        "arm_1_sem": {
            "model": "the darkness detector: no training. flatten the background at "
                     "seven radii, cut every pixel more than k MAD below its local "
                     "median, clean, keep regions",
            "settings_drawn": {
                "mad_k": K, "absolute_dark_thresh": GATE, "scale_ladder": list(LADDER),
                "clean_mask_min_area_px": CLEAN_MIN, "clean_mask_open_radius": 1,
                "clean_mask_close_radius": 3, "candidate_min_area_px": CAND_MIN,
                "connectivity": 8, "region_classifier": bool(DO.USE_REGION_CLASSIFIER),
                "source": "analysis/detector_overrides.py and paper/figures/"
                          "both_modalities.py, read at run time, never retyped"},
            "two_values_of_mad_k": {
                "shipped_in_the_app": float(DO.SHIPPED_MAD_K),
                "evaluated_in_the_paper": float(DO.PAPER_MAD_K),
                "note": "detector_overrides.py defines both and they are not the same "
                        "number; every row other than (a) and (b) is drawn at the "
                        "paper's 6.0, and (a) marks both"}},

        "arm_2_txm": {
            "model": "a trained per-pixel ensemble: the mean probability of a "
                     "%d-channel intensity and texture model and a %d-dimensional "
                     "hybrid that adds a frozen %s embedding"
                     % (stats["n_features"], stats["hybrid_dim"], const["SAM_MODEL_ID"]),
            "settings_drawn": {k: const[k] for k in sorted(const)},
            "source": "PARSED with ast out of the deployed "
                      "TXM_Crack_Detection_Pipeline/app/core/pipeline.py and model.py, "
                      "never retyped; a name that stops being a module-level literal "
                      "aborts the plate",
            "deployed_model": {"registry_key": txm["model_key"], "recipe": txm["recipe"],
                               "members": stats["model"]}},

        "rows": {
            "a": {
                "arm": "SEM", "parameter": "MAD multiplier k", "value": K,
                "verdict": "SWEPT ON THIS LABORATORY'S OWN FRAMES, and the shipped "
                           "value is not the best point on the grid. Recall falls "
                           "monotonically as k rises while precision barely moves, so "
                           "the lowest value tested wins on both, and the grid's best "
                           "is its own EDGE -- the same flaw this paper reports in the "
                           "published sweep it replaced. Paired against the "
                           "application's k = 5, k = 3 gains 0.064 median recall on 40 "
                           "of 45 frames with none worse, and 0.0013 median precision "
                           "on 16 of 18, costing 2.1 more points of marked area. The "
                           "shipped value is kept and the curve drawn, so the choice "
                           "is visible rather than asserted.",
                "unit_set": "45 frames carrying painted crack for recall, 18 carrying "
                            "both verdicts for precision. NEVER pooled into an F1: "
                            "they are different frame sets and the record says so.",
                "record": "docs/figures/lab_madk_sweep.json"},
            "b": {
                "arm": "SEM", "parameter": "absolute darkness gate",
                "value": "%d of 255 DN" % GATE,
                "verdict": "INHERITED. The value carries no recorded provenance anywhere "
                           "in the archived pipeline or in this project -- "
                           "analysis/detector_overrides.py calls it \"an integer with no "
                           "provenance here\" -- and it supplies more of the detector's "
                           "frame-scale recall than the whole seven-rung ladder does",
                "unit_set": "26 tiles, pooled, 0 px tolerance, mad_k 6.0",
                "record": "docs/figures/parameters_tiles.json, gate_26 and gate_25",
                "iou_by_threshold_26": {k: v["iou"] for k, v in tiles["gate_26"].items()},
                "iou_by_threshold_25": {k: v["iou"] for k, v in tiles["gate_25"].items()},
                "best_26": _best({k: v["iou"] for k, v in tiles["gate_26"].items()}),
                "best_25": _best({k: v["iou"] for k, v in tiles["gate_25"].items()}),
                "flood_tile": tiles["flood_tile"],
                "read_this": (
                    "on all 26 tiles the best setting on this grid is t = %s, where "
                    "t = 0 is the gate switched off; drop the one crop with an "
                    "off-specimen void and the ordering reverses -- the gate is then "
                    "clearly worth having and the shipped %d sits %.4f IoU below that "
                    "grid's own best at t = %s"
                    % (_best({k: v["iou"] for k, v in tiles["gate_26"].items()}), GATE,
                       max(v["iou"] for v in tiles["gate_25"].values())
                       - tiles["gate_25"][str(GATE)]["iou"],
                       _best({k: v["iou"] for k, v in tiles["gate_25"].items()}))),
                "frame_scale_cross_check": {
                    "unit_set": "48 full frames carrying a hand-painted correction mask, "
                                "%d painted crack px, mad_k 6.0" % painted,
                    "record": "docs/figures/parameters_frames.json",
                    "pooled_dark_stage_recall_by_threshold":
                        {str(g): _pooled(fr, lambda r, t=g: r["dark_crack"][str(t)])[0]
                         for g in GATE_GRID_DARK},
                    "full_chain_recall_pooled":
                        {str(t): chain_pooled(t, "kept")[0] for t in GATE_GRID_FRAME}},
                "prior_record": "analysis/detector_overrides.py records the same quantity "
                                "at the app's mad_k 5.0: the gate proposes 13,907,547 of "
                                "the 20,923,398 painted px that reach a candidate, "
                                "10,516,306 of them reached by no ladder rung, and "
                                "dropping it deletes 47.50% of kept hand-marked crack"},
            "c": {
                "arm": "SEM", "parameter": "minimum region area, two separate floors",
                "value": {"clean_mask small-object floor px": CLEAN_MIN,
                          "candidate region floor px": CAND_MIN},
                "verdict": "INHERITED, AND NEITHER IS AT AN OPTIMUM",
                "unit_set": "26 tiles, pooled, 0 px tolerance, mad_k 6.0",
                "record": "docs/figures/parameters_tiles.json, clean_min and cand_min",
                "clean_mask_small_object_floor_iou":
                    {k: v["iou"] for k, v in tiles["clean_min"].items()},
                "candidate_region_floor_iou":
                    {k: v["iou"] for k, v in tiles["cand_min"].items()},
                "best_on_each_grid": {"small_object_floor_px": bars["best_clean_min"],
                                      "candidate_floor_px": bars["best_cand_min"]},
                "shipped_iou": tiles["shipped"]["iou"],
                "read_this": (
                    "the small-object floor moves pooled IoU by %.4f over 0-50 px and "
                    "its best value on this grid is %s, not %d; the candidate floor is "
                    "worth %+.4f IoU against the smallest floor on its grid, so %d px "
                    "is a cost rather than a choice"
                    % (max(tiles["clean_min"][str(v)]["iou"] for v in CLEANMIN_GRID if v <= 50)
                       - min(tiles["clean_min"][str(v)]["iou"] for v in CLEANMIN_GRID if v <= 50),
                       bars["best_clean_min"], CLEAN_MIN,
                       tiles["cand_min"][str(CAND_MIN)]["iou"]
                       - tiles["cand_min"][str(CANDMIN_GRID[0])]["iou"], CAND_MIN)),
                "table_1_row_that_is_two_constants": {
                    "row": "Morphological opening size 13 px",
                    "what_the_code_does": "unified_pipeline.py calls clean_mask(dark, "
                                          "min_area_px=13); inside clean_mask the 13 is "
                                          "remove_small_objects' AREA floor and the "
                                          "opening is morphology.opening(mask, "
                                          "disk(open_radius=1)). They are separate "
                                          "constants and are rows (d) and (e)",
                    "source": "sem-crack-detector/code/detect_cracks.py clean_mask and "
                              "interior_active_learning/code/unified_pipeline.py"},
                "frame_scale_cross_check": {
                    "unit": "share of all hand-painted crack on the 48 frames lost to "
                            "each cleaning step, at the shipped settings",
                    "small_object_floor": chain_pooled(GATE, "small13")[0],
                    "opening": chain_pooled(GATE, "opening")[0],
                    "candidate_floor": chain_pooled(GATE, "area40")[0],
                    "never_dark": chain_pooled(GATE, "notdark")[0],
                    "kept": kept / max(painted, 1),
                    "note": "the buckets are disjoint and exhaustive and are asserted to "
                            "sum to the painted crack on every frame by "
                            "fullframe_recall_decomposition.decompose"}},
            "d": {
                "arm": "SEM", "parameter": "morphological opening radius, and the "
                                           "labelling connectivity",
                "value": {"opening": "disk, radius 1 px", "connectivity": 8},
                "verdict": "INHERITED, AND NOT AT AN OPTIMUM. Connectivity is below the "
                           "resolution of every instrument this project has",
                "unit_set": "26 tiles, pooled, 0 px tolerance, mad_k 6.0",
                "record": "docs/figures/parameters_tiles.json, opening['2'] and ['1']",
                "iou_by_radius_8_connected":
                    {k: v["iou"] for k, v in tiles["opening"]["2"].items()},
                "iou_by_radius_4_connected":
                    {k: v["iou"] for k, v in tiles["opening"]["1"].items()},
                "read_this": (
                    "no opening at all scores higher than the shipped disk(1) by %.4f "
                    "IoU, and the whole 4-versus-8 connectivity question is worth %.4f"
                    % (tiles["opening"]["2"]["0"]["iou"] - tiles["opening"]["2"]["1"]["iou"],
                       max(abs(tiles["opening"]["2"][str(v)]["iou"]
                               - tiles["opening"]["1"][str(v)]["iou"])
                           for v in OPEN_GRID)))},
            "e": {
                "arm": "SEM", "parameter": "background-flattening ladder",
                "value": list(LADDER),
                "verdict": "NEVER SEARCHED. Unioning the darkness cut over a ladder of "
                           "flattening radii was decided by measurement and costs no "
                           "free parameter, but the seven VALUES are a doubling ladder, "
                           "not a searched set, and no sweep over alternative ladders "
                           "(a different base, a different count, a different top) "
                           "exists in this project",
                "unit_set": "48 painted frames. A painted pixel is credited to a radius "
                            "only when that radius and no other of the seven reaches it, "
                            "so each bar is a true leave-one-out marginal",
                "record": "docs/figures/parameters_frames.json, rung_only_crack",
                "denominator": "the painted crack the SEVEN-RUNG UNION reaches on its "
                               "own, with the absolute gate switched off: %d px of the "
                               "%d painted"
                               % (sum(r["dark_crack"]["0"] for r in fr), painted),
                "radii": bars["terms"], "pooled_pct": bars["pooled"],
                "per_frame_median_pct": bars["median"],
                "per_frame_p25_pct": bars["p25"], "per_frame_p75_pct": bars["p75"],
                "frames_with_a_nonzero_share": bars["frames_with_a_nonzero_share"],
                "frames_with_any_ladder_reached_paint":
                    bars["frames_with_a_denominator"],
                "reached_by_two_or_more_radii_pct": bars["shared_pct"],
                "the_bar_is_pooled_and_the_distribution_is_zero_inflated": {
                    "question": "at the coarse radii the pooled bar and the per-frame "
                                "median differ by two orders of magnitude. Is the bar an "
                                "artefact of the two frames holding most of the paint?",
                    "answer": "NO. Only %d of the %d frames whose paint the ladder "
                              "reaches have any pixel that the top radius alone reaches, "
                              "so the per-frame median sits at zero while p75 is %.2f%%. "
                              "A coarse radius contributes nothing on most frames and a "
                              "great deal on the frames carrying a crack wide enough for "
                              "it. The previous edition drew the quartiles on the bars; "
                              "a sparkline strip cannot carry them, so they are here."
                              % (bars["frames_with_a_nonzero_share"][-1],
                                 bars["frames_with_a_denominator"][-1], bars["p75"][-1]),
                    "checked_separately": _concentration(fr, LADDER)},
                "read_this": (
                    "%.1f%% of what the ladder reaches is reached by two or more radii, "
                    "and the two largest unique contributions are sigma = %s and "
                    "sigma = %s -- the ENDS of the ladder, which is the mechanism the "
                    "override's docstring names: a crack is only reliably dark at the "
                    "scales near its own width"
                    % (bars["shared_pct"],
                       *[bars["terms"][i] for i in sorted(
                           sorted(range(len(bars["pooled"])),
                                  key=lambda j: -bars["pooled"][j])[:2])])),
                "the_gate_is_not_in_this_row": {
                    "why": "against the same denominator the absolute gate's unique "
                           "share is an order of magnitude larger than any radius and "
                           "would make the seven bars unreadable; it is row (c)",
                    "gate_unique_pct_of_the_whole_union_pooled": 100.0 * _pooled(
                        fr, lambda r: r["gate_only_crack"], den="union_crack")[0]},
                "single_radius_comparison": "detector_overrides.py records the union's "
                                            "gain over the single sigma = 40 cut the "
                                            "archived pipeline used, on the 26 tiles at "
                                            "mad_k 5.0: P 0.4033 -> 0.4182, R 0.5326 -> "
                                            "0.6252, IoU 0.2979 -> 0.3344, F1 0.4590 -> "
                                            "0.5012, and the union is a strict superset "
                                            "so it can delete nothing"},
            "f": {
                "arm": "SEM", "parameter": "one flattening radius against the union",
                "value": "7 rungs, 5-320 px",
                "verdict": "the union had NO sweep anywhere until this revision; it "
                           "was asserted to be worth having and is now measured",
                "unit_set": "26 hand-labelled 512 px tiles, pooled over every pixel "
                            "at 0 px tolerance, at the shipped constants",
                "record": "docs/figures/parameters_tiles.json, single_radius and "
                          "union_on_these_tiles",
                "note": "the dashed rule on the panel is the shipped seven-rung "
                        "union; the curve is what ONE radius scores on its own"},
            "g": {
                "arm": "SEM", "parameter": "clean_mask closing radius",
                "value": "3 px",
                "verdict": "INHERITED with no recorded provenance and swept HERE for "
                           "the first time; the shipped value is not the best on its "
                           "own grid",
                "unit_set": "26 hand-labelled 512 px tiles, pooled, 0 px tolerance",
                "record": "docs/figures/parameters_tiles.json, close"},
            "h": {
                "arm": "SEM", "parameter": "denoise sigma",
                "value": "1.0",
                "verdict": "INHERITED with no recorded provenance and swept HERE for "
                           "the first time; the shipped value is not the best on its "
                           "own grid",
                "unit_set": "26 hand-labelled 512 px tiles, pooled, 0 px tolerance",
                "record": "docs/figures/parameters_tiles.json, denoise"},
            "i": {
                "arm": "SEM", "parameter": "flatten_background sigma", "value": 40,
                "verdict": "SWEPT HERE FOR THE FIRST TIME. This was the last constant "
                           "on the plate with no sweep anywhere. Over a grid "
                           "bracketing the shipped value by a factor of eight either "
                           "way the curve is a plateau: 40 px scores IoU 0.2290 "
                           "against 0.2339 for the grid's best at 10 px, a difference "
                           "of 0.005 across a 64x range in the parameter. The value is "
                           "not optimal and barely matters, which is worth knowing and "
                           "is what the panel shows.",
                "unit_set": "the same 26 hand-labelled tiles as the other tile sweeps",
                "record": "docs/figures/parameters_tiles.json, flatten_sigma"},
            "j": {
                "arm": "TXM", "parameter": "probability threshold", "value": THR,
                "verdict": "SETTLED BY A TEST ON DATA THE MEMBERS WERE NOT FITTED TO: "
                           "matched on the FALSE-ALARM RATE of the previous model over "
                           "the three largest confirmed crack-free specimens, not "
                           "maximised on any score. The curve drawn beside it is a "
                           "sweep made HERE, after the fact",
                "unit_set": "%d TXM frames, refereed pixels only (1 = crack, 2 or 3 = "
                            "not-crack, 0 excluded): %d crack and %d not-crack px"
                            % (txm["n_frames"], txm["crack_px"], txm["notcrack_px"]),
                "record": "docs/figures/parameters_txm.json, written by this module; "
                          "its frame set reproduces docs/figures/txm_background_units."
                          "json exactly, group by group, which is control 1",
                "measure": "pixel accuracy over refereed pixels, against the EMPTY-MASK "
                           "baseline of %.3f%%. Overlap is NOT reported on this set: "
                           "%s" % (txm["empty_mask_accuracy_pct"],
                                   units["why_no_overlap_scores"]),
                "what_is_swept": txm["scoring"],
                "at_the_shipped_threshold": bars["txm_at_shipped"],
                "best_on_the_grid": bars["best_txm_threshold"],
                "accuracy_by_threshold": {t: v["accuracy_pct"]
                                          for t, v in txm["curve"].items()},
                "recall_by_threshold": {t: v["recall"] for t, v in txm["curve"].items()},
                "read_this": (
                    "the shipped %.2f scores %.3f%% accuracy, %+.3f pp over marking "
                    "nothing, with recall %.4f on painted crack. The grid's own best is "
                    "%.2f at %+.3f pp, so the curve is flat across the whole upper half "
                    "and the threshold is not what the model's performance rests on"
                    % (THR, bars["txm_at_shipped"]["accuracy_pct"],
                       bars["txm_at_shipped"]["margin_pp"],
                       bars["txm_at_shipped"]["recall"], bars["best_txm_threshold"],
                       txm["curve"][f"{bars['best_txm_threshold']:.3f}"]["margin_pp"])),
                "the_provenance_itself": "TXM_Crack_Detection_Pipeline/app/core/"
                                         "pipeline.py, the comment block above "
                                         "DEFAULT_THRESHOLD, which tabulates crack-free "
                                         "false positives, indications per frame, width "
                                         "and recall for v4 at 0.60 and v5 at 0.70 and "
                                         "0.60. That table is prose in the source and "
                                         "has no machine-readable record, which is why "
                                         "this row's sparkline is the sweep made here "
                                         "and not that table"},
            "k": {
                "arm": "TXM", "parameter": "which members are averaged",
                "value": stats["model"],
                "verdict": "SETTLED BY CROSS-VALIDATION",
                "unit_set": cv["convention"],
                "record": "docs/figures/txm_model_scores.json, cross_validated",
                "f17_mean_iou": cv["f17_mean_iou"],
                "hybrid_mean_iou": cv["hybrid_mean_iou"],
                "ensemble_mean_iou": cv["ens_mean_iou"],
                "ensemble_std_iou": cv["ens_std_iou"],
                "ensemble_min_iou": cv["ens_min_iou"],
                "mean_precision": cv["mean_precision"], "mean_recall": cv["mean_recall"],
                "labelled_images_used": cv["labelled_images_used"],
                "model_version_of_the_cv_artefact": cv["model_version"],
                "caveat_grouping": cv["not_specimen_independent"],
                "caveat_scope": cv["not_restricted"],
                "read_this": "the mean of the two members beats either alone (%.4f "
                             "against %.4f and %.4f), but the folds are grouped BY "
                             "IMAGE over all %d labelled frames of four specimen "
                             "groups, so no specimen is ever held out and this is not a "
                             "specimen-independent score. It is also a v4 artefact; the "
                             "deployed members are v5 and no v5 grouped-CV artefact "
                             "exists in either repository."
                             % (cv["ens_mean_iou"], cv["f17_mean_iou"],
                                cv["hybrid_mean_iou"], cv["labelled_images_used"])},
            "l": {
                "arm": "TXM", "parameter": "SAM tile size and tile stride",
                "value": {"tile_px": const["TILE"], "stride_px": const["TILE_STRIDE"],
                          "embedding_stride_px": const["EMB_STRIDE"],
                          "backbone": const["SAM_MODEL_ID"]},
                "verdict": "TWO ROWS, TWO DIFFERENT ANSWERS, which is why they now "
                           "carry different letters. The TILE is F: 1024 px is the "
                           "ViT-H encoder's own input size and the 16 px embedding "
                           "stride is its patch size, so neither was ever a choice. "
                           "The tile STRIDE is M: 896 was settled by the measurement "
                           "quoted below, on one frame. The previous edition lettered "
                           "both F and so asserted, of the stride, that no measurement "
                           "of it exists -- while printing that measurement two keys "
                           "further down.",
                "unit_set": "no sparkline: the stride's evidence is one frame, not a "
                            "grid, and drawing two points as a curve would overstate it",
                "record": "TXM_Crack_Detection_Pipeline/app/core/model.py, TILE and "
                          "TILE_STRIDE, parsed with ast",
                "what_the_source_states": "the comment above TILE_STRIDE records a "
                                          "single measurement on one 3044x2354 frame: "
                                          "with abutting tiles the worst row carried "
                                          "32.8x the median row-to-row probability "
                                          "change, all of it at the tile boundary, and "
                                          "at stride 896 the worst row is 7.8x and sits "
                                          "on crack. Those numbers are prose in the "
                                          "source, on one frame, with no machine-"
                                          "readable record, so they are quoted here and "
                                          "NOT drawn as if they were a sweep."},
            "m": {
                "arm": "the SEM constant, run on TXM", "parameter": "MAD multiplier k",
                "value": "none -- the SEM detector is not the TXM arm's detector",
                "verdict": "CANNOT BE CHOSEN AT ALL ON THIS MODALITY",
                "unit_set": "the same %d TXM frames and the same refereed pixels as row "
                            "(g), so the two rows may be read against each other"
                            % txm["n_frames"],
                "record": "docs/figures/txm_background_units.json (FULL corpus, via "
                          "_paths.scoped(scope=False)), pooled",
                "groups": {g: {"frames": v["frames"], "crack_px": v["crack_px"],
                               "notcrack_px": v["notcrack_px"]}
                           for g, v in units["by_group"].items()},
                "accuracy_by_k": {k: karm[k]["accuracy_pct"] for k in units["grid"]},
                "margin_by_k": {k: karm[k]["margin_pp"] for k in units["grid"]},
                "empty_mask_accuracy_pct": txm["empty_mask_accuracy_pct"],
                "controls_in_the_record": {
                    "mark_everything": units["pooled"]["control: mark everything"],
                    "otsu_no_model": units["pooled"]["control: Otsu, no model"]},
                "read_this": "every k on the grid scores BELOW an empty mask; the best "
                             "is k = %g at %+.3f pp and the paper's k = %g at %+.3f pp. "
                             "A constant cannot be selected on an instrument where no "
                             "value of it beats marking nothing, which is the reason "
                             "the TXM arm has a trained model and not this rule."
                             % (bars["best_k_on_txm"], bars["best_margin_on_txm_pp"], K,
                                k_margin)}},

        "not_drawn_but_fixed": {
            "sem_swept_only_in_this_edition": {
                "clean_mask_close_radius_px": 3,
                "denoise_sigma": 1.0,
                "flatten_background_sigma_px": 40,
                "note": "the closing radius was searched once by "
                        "analysis/research/improve/lever5_postprocessing.py and its own "
                        "adversarial audit withdrew the result: 82.4% of the gain was "
                        "one tile. The flattening sigma is the base the ladder in (f) "
                        "is built around rather than a constant swept on its own."},
            "these_rows_used_to_be_lettered_F_and_were_wrong": {
                "what_went_wrong": "F asserts no measurement of the constant exists in "
                                   "either repository. For the eight rows now lettered "
                                   "M that assertion was false, and this sidecar said "
                                   "so in the same breath: the previous edition filed "
                                   "them under a key literally named "
                                   "`txm_fixed_from_its_own_measurements`. The letter "
                                   "was a SCOPE decision -- these act after the "
                                   "threshold rather than on the model, so no panel was "
                                   "drawn for them -- and every row without a panel was "
                                   "given F. Not drawn is not the same as not measured, "
                                   "and only M says the second thing.",
                "nothing_about_the_pipeline_changed": "no constant moved; this is the "
                                                      "provenance column being made "
                                                      "true about constants that are "
                                                      "exactly where they were."},
            "measured_not_drawn": {
                "why_not_drawn": "several of these are two values on one frame rather "
                                 "than a grid, and a sparkline drawn through two points "
                                 "would dress a comparison as a sweep. The measurement "
                                 "is quoted in full here instead, and the source line "
                                 "is named so a reader can check it.",
                "rows": {
                    "hole fill (px)": {
                        "value": const["FILL_HOLES_MAX_PX"],
                        "measurement": "a three-point sweep over ALL 71 frames at "
                                       "64 / 256 / 1024 px, taken after narrowing. "
                                       "1024 is best on every axis at once: enclosed "
                                       "voids 342,963 -> 2,471 / 1,145 / 894, recall on "
                                       "painted crack 74.74% -> 76.02% / 76.32% / "
                                       "76.58%, and on-specimen false positives on the "
                                       "6 crack-free frames flat at 0.0040% for every "
                                       "cap including no fill at all. An earlier census "
                                       "over the first 14 images set the cap's SHAPE: "
                                       "1,302 of 1,313 interior holes are under 1,024 "
                                       "px and hold only 19.4% of the hole area, while "
                                       "two holes of 59,194 and 65,505 px are islands "
                                       "of intact material that filling would misreport",
                        "source": "app/core/pipeline.py, above FILL_HOLES_MAX_PX"},
                    "speck floor (px)": {
                        "value": const["MIN_BLOB_PX"],
                        "measurement": "leave-one-image-out IoU on full-resolution "
                                       "probability maps, improving monotonically up to "
                                       "2000 and winning on all four folds. 2000 rather "
                                       "than the better-scoring 5000 because at 5000 "
                                       "the worst single image loses 12.4% of the crack "
                                       "its owner confirmed, against 2.7% at 2000 -- "
                                       "scored on the owner's own 30.2 M hand-drawn "
                                       "crack pixels",
                        "source": "app/core/pipeline.py, above MIN_BLOB_PX"},
                    "narrowing window (px)": {
                        "value": const["TIGHTEN_WINDOW"],
                        "measurement": "TWO VALUES ON ONE FRAME, which is why this is "
                                       "not drawn. On wrought_316L_fatigue_1200_cycles, "
                                       "w = 151 keeps 76.6% of the painted crack at a "
                                       "1.0 px half-width and w = 301 keeps 83.7% at "
                                       "1.4 px; 301 is chosen for the recall",
                        "source": "app/core/pipeline.py, above TIGHTEN_WINDOW"},
                    "narrowing core": {
                        "value": const["TIGHTEN_MIN_CORE"],
                        "measurement": "a per-frame census over 66 frames against the "
                                       "darkest fifth of the corridor: the rule keeps a "
                                       "median 97.0%, but 8 frames fall below 70% and 4 "
                                       "below 50%, worst 34.4%. 0.60 sits between the "
                                       "65.1% frame and the 49.8% one, so narrowing is "
                                       "DECLINED on the four pathological frames and "
                                       "applied everywhere else",
                        "source": "app/core/pipeline.py, above TIGHTEN_MIN_CORE"},
                    "correction floor": {
                        "value": const["CORRECTION_FLOOR"],
                        "measurement": "two values: 0.20 keeps 89.6% of what the hand "
                                       "strokes were adding while dropping the "
                                       "brush-shaped remainder, 0.35 keeps only 65.3%",
                        "source": "app/core/pipeline.py, above CORRECTION_FLOOR"},
                    "tile stride (px)": {
                        "value": const["TILE_STRIDE"],
                        "measurement": "ONE FRAME, 3044x2354. With abutting tiles "
                                       "(stride == tile) the worst row carries 32.8x "
                                       "the median row-to-row probability change, all "
                                       "of it at the y = 1023 tile boundary; at stride "
                                       "896 the worst row is 7.8x and sits on crack "
                                       "rather than on a seam. Two lookup-time "
                                       "alternatives were tried and both failed -- "
                                       "reaching past a tile edge invents data and "
                                       "raised false positives on crack-free specimens "
                                       "6.2x, and a window that stops at the edge "
                                       "reduces to last-tile-wins. Costs 13% more tiles",
                        "source": "app/core/model.py, above TILE_STRIDE"},
                    "clip peak sigma": {
                        "value": const["WIDTH_CLIP_PEAK_SIGMA"],
                        "measurement": "gating on whether the WIDTH MEASUREMENT "
                                       "succeeded rather than on the pixel's own "
                                       "contrast. The v1 contrast gate was a selection "
                                       "effect, because width rises with contrast "
                                       "(rho = +0.673): on the worst over-marker it "
                                       "admitted 1.6% of the skeleton and reported a "
                                       "median half-width of 17.6 px where an ungated "
                                       "sample of the same frame reports 3.5 px. The "
                                       "change took the measurable fraction from 43% to "
                                       "65% and that frame from 2.57x to 1.15x",
                        "source": "app/core/pipeline.py, above WIDTH_CLIP_PEAK_SIGMA"},
                    "straight max wander (px)": {
                        "value": const["STRAIGHT_MAX_WANDER"],
                        "measurement": "a population census over all 71 frames. "
                                       "Standalone components of >= 200 px with bbox "
                                       "aspect >= 6 split into 5 artefacts wandering "
                                       "0.13-0.71 px, one component at 1.73 px that is "
                                       "55.9% painted CRACK, and 6 genuine long cracks "
                                       "at 2.9-12.9 px. The cut is placed in the gap at "
                                       "1.0. The first version used 2.0 and removed "
                                       "1,360 px of crack the annotator had painted",
                        "source": "app/core/pipeline.py, above STRAIGHT_MAX_WANDER"}}}},

        "why_each_F_is_true": dict(WHY_F_IS_TRUE,
            **{"_what_this_is": "F asserts that no measurement of the constant exists "
                                "in either repository, which is a claim about an "
                                "absence and the easiest thing on this plate to get "
                                "wrong. One line per F row, checked against the table "
                                "at build time so a row cannot carry F silently."}),

        "panel_letters_have_moved": {
            "why": "the plate is a row of sweep panels over a printed table of every "
                   "constant, and only the constants with evidence worth plotting "
                   "get a letter. TWO have lost their panel. The learned region "
                   "classifier is a yes-or-no setting with no grid to sweep, so "
                   "there was never a curve to draw. The MAD multiplier had the "
                   "one genuine sweep on this plate, and that sweep was run on a "
                   "public collection the author has removed from the paper; its "
                   "panel went with it, and the constant is swept here on this laboratory's own frames instead. "
                   "Between them they shift every remaining letter up by two.",
            "two_editions_ago_six_panels": {
                "a": "MAD multiplier k", "b": "learned region classifier",
                "c": "absolute intensity gate", "d": "the scale ladder",
                "e": "the two size floors", "f": "opening radius and connectivity"},
            "previous_edition_ten_rows": {
                "a": "MAD multiplier k", "b": "learned region classifier",
                "c": "absolute darkness gate", "d": "the two size floors",
                "e": "opening radius and connectivity", "f": "the scale ladder",
                "g": "probability threshold", "h": "which members are averaged",
                "i": "SAM tile and stride", "j": "the SEM multiplier, run on TXM"},
            "this_edition": "filled in below, from the panels actually drawn",
            "downstream_kept_in_step": "paper/manuscript/sections/20-methods.md and "
                "paper/figures/mk_paper_pdf.py were rewritten against THIS lettering "
                "when the plate was. The keys of `rows` above are the plate's own panel "
                "letters, and a control below fails the build if they stop matching the "
                "panels the figure draws, so a future relettering cannot leave this "
                "record describing a panel that is not there.",
            "not_edited_from_here": "this module owns only itself; it reports a stale "
                                    "pointer rather than reaching into the manuscript"},
        "reconstruction_checks": {
            "sem_union": frames["controls"]["union"],
            "sem_kmax": frames["controls"]["kmax"],
            "sem_tile_chain": tiles["controls"]["chain"],
            "sem_tilebench": tiles["controls"]["tilebench"],
            "txm_unit_set": txm["controls"]["unit_set"],
            "txm_model": txm["controls"]["model"],
            "txm_baseline": txm["controls"]["baseline"],
            "plate_text_collisions": "PASS: %d drawn strings measured at the renderer's "
                                     "own extents, no pair overlapping by more than 1 pt "
                                     "in both directions" % bars["n_text"],
            "plate_column_containment": "PASS: %d placed strings, every one measured "
                                        "inside the column it was laid out in"
                                        % bars["n_placed"],
            "rule": "all of them abort the script on disagreement; none of them warns"},

        "plate": {"figure_width_in": J.PAGEW, "figure_height_in": bars["figure_height_in"],
                  "dpi": 600, "smallest_printed_type_pt": J.FLOOR,
                  "layout": "a table: parameter, value, sparkline, note, grouped under "
                            "two arm headings and seven provenance bands"},

        "the_preprocessing_budget": {
            "why_it_matters": "the SEM arm's constants are not free: together they are a "
                              "tuning budget spent before any model runs. On the 15-tile "
                              "benchmark this project scored the published models on, a "
                              "one-line global darkness threshold fitted "
                              "leave-one-frame-out outscores a network trained on 30,017 "
                              "images, which is what a reviewer should weigh a "
                              "seven-constant preprocessing chain against",
            "15_tile_benchmark_iou": {
                "a one-line global threshold, leave-one-frame-out":
                    comp["global threshold"]["iou"],
                "OmniCrack30k nnU-Net, trained on 30,017 images":
                    comp["OmniCrack30k nnU-Net"]["iou"],
                "SAM 3, zero-shot union": comp["SAM 3 (zero-shot union)"]["iou"],
                "shipped v1.49.2, all 15 tiles":
                    comp[">>> shipped v1.49.2, all 15 tiles"]["iou"]},
            "source": "docs/slides/comparison.json",
            "caveat": "at n = 15 nothing on that benchmark separates statistically, and "
                      "3 of its 9 frames also appear in the 26-tile set that informed "
                      "the shipped configuration"},

        #: THE COUNTS, so no downstream document has to retype them. Four places --
        #: the manuscript caption, the figure pack's caption, and two passages of the
        #: explainer -- each carried a hand-typed "four tested, thirty-six fixed", and
        #: all four were wrong the moment eight rows moved off F. They read this now.
        "counts_by_letter": dict(DOCSTRING_TALLY),
        "tally": {
            "swept in this edition on this laboratory's own data": [
                "SEM: MAD multiplier k"],
            "settled by a test, no value to choose":
                ["SEM: learned region classifier (%s)"
                 % ("enabled" if DO.USE_REGION_CLASSIFIER else "disabled"),
                 "SEM: multiscale union versus a single flattening radius",
                 "TXM: probability threshold 0.60, matched on false alarms",
                 "TXM: which members are averaged",
                 "TXM: the width clip, on or off (no panel: it acts on the exported "
                 "mask, after everything this plate's panels sweep)"],
            "fixed by construction, no sweep on record":
                ["TXM: SAM tile 1024 px -- the ViT-H encoder's own input size, and the "
                 "16 px embedding stride is its patch size"],
            "selected from a measurement in the source, not drawn":
                ["TXM: tile stride 896 px (one frame; see `measured_not_drawn`)",
                 "TXM: hole fill 1024 px, speck floor 2000 px, narrowing window 301 px, "
                 "narrowing core 0.60, correction floor 0.20, clip peak sigma 2.0, "
                 "straight-artefact wander cut 1.0 px"],
            "swept here after the fact, no recorded provenance for the value":
                ["SEM: absolute darkness gate 10", "SEM: opening disk(1)",
                 "SEM: clean_mask small-object floor 13 px",
                 "SEM: candidate region floor 40 px", "SEM: 8-connectivity"],
            "swept here for the first time":
                ["SEM: the seven ladder values 5-320 px",
                 "SEM: clean_mask close radius 3 px", "SEM: denoise sigma 1.0",
                 "SEM: flatten_background sigma 40"],
            "cannot be chosen on the other modality at all":
                ["the SEM MAD multiplier k, run on TXM"]},

        "the_asymmetry_between_g_and_j": {
            "what_is_equal": "the same 31 TXM frames, the same refereed pixels, the "
                             "same pixel-accuracy quantity behind both rows and the "
                             "same empty-mask baseline. Control 1 of the TXM pass "
                             "asserts the first two against docs/figures/"
                             "txm_background_units.json, group by group.",
            "what_is_drawn": "a DIFFERENT view of that one quantity in each row, "
                             "because no single view can be read in both: on a 0-100% "
                             "accuracy axis a 2.8 point margin and a 9.5 point "
                             "shortfall are each under a point of ink. (g) draws the "
                             "two axes the threshold was decided on, recall on painted "
                             "crack and false alarms on painted not-crack; (j) draws "
                             "the margin itself as bars below zero. The accuracy "
                             "numbers for both are in their own blocks above.",
            "what_is_not": "the TXM ensemble was FITTED on this paint, so row (g) is an "
                           "in-sample curve and the row says so on the plate. The SEM "
                           "darkness rule was fitted to nothing, so row (j) is "
                           "out-of-sample for it.",
            "which_way_it_runs": "the asymmetry favours the trained model. The pair is "
                                 "therefore evidence that the SEM constant does NOT "
                                 "transfer to TXM -- a rule fitted to nothing still has "
                                 "to beat an empty mask, and it does not at any k -- and "
                                 "it is NOT a measurement of how much better the trained "
                                 "model is. That number is row (h), with its own "
                                 "grouping caveat.",
            "the_honest_pair": "an out-of-sample TXM number would need a grouped-CV "
                               "artefact for the DEPLOYED v5 members, and none exists in "
                               "either repository (txm_model_scores.json says so in "
                               "cross_validated.model_version)."},
        "aggregation_warning": "the rows use four different unit sets -- "
                               "26 hand-labelled tiles, 48 painted SEM frames, "
                               "31 refereed TXM frames and 71 labelled TXM frames -- and "
                               "a value from one may not be compared with a value from "
                               "another. Each row names its own. The ONE comparison the "
                               "plate makes across rows is (g) against (j), which is the "
                               "same 31 frames, the same refereed pixels and the same "
                               "measure by construction and by control.",

        #: THE TWO PRINTED TABLES, row for row, as the plate sets them. The caption
        #: carried the VALUES already but not which letter each row ends in, so the
        #: one column this figure exists to publish was the one thing a reader could
        #: not get out of the record without re-running the generator.
        "table_rows": bars["constants"],
        "ref_column_key": bars["key_phrases"],

        "generated_from": {
            "docs/figures/parameters_tiles.json": tiles["key"],
            "docs/figures/parameters_frames.json": frames["key"],
            "docs/figures/parameters_txm.json": txm["key"],
            "docs/figures/madk_above_five.json": "committed",
            "docs/figures/madk_paired_test.json": "committed",
            "docs/figures/txm_background_units.json": "committed, FULL corpus",
            "docs/figures/txm_model_scores.json": "committed",
            "paper/figures/sem_deadzone.json": dead.get("generated", "committed"),
            "paper/figures/txm_stats.json": stats.get("model_key", "committed"),
            "TXM app/core/pipeline.py + model.py": "parsed with ast at run time",
            "docs/slides/comparison.json": "committed"},
    }
    #: Read off the rows that were actually built, so the migration table cannot drift
    #: from the plate the way the manuscript caption it warns about already has.
    rec["panel_letters_have_moved"]["this_edition"] = {
        L: "%s  [%s]" % (r["parameter"], r["arm"])
        for L, r in rec["rows"].items()
        #: only the lettered panel rows; this dict also carries narrative blocks that
        #: have no parameter of their own, and reading them here was a KeyError
        if isinstance(r, dict) and "parameter" in r and "arm" in r}
    # THE RECORD'S LETTERS MUST BE THE PLATE'S LETTERS. This file was describing a
    # panel (b) called "learned region classifier" after that panel had been taken off
    # the plate, and every letter after it pointed one row out. A letter in this record
    # that is not a panel, or a panel with no entry here, now fails the build.
    lettered = {L for L in rec["rows"] if len(L) == 1}
    drawn = set(bars["panel_letters"])
    if lettered != drawn:
        raise SystemExit(f"this caption file keys rows {sorted(lettered)} and the plate "
                         f"draws panels {sorted(drawn)}; re-key the rows rather than "
                         f"shipping a record that points at a panel nobody drew")
    if bars["tally"] != DOCSTRING_TALLY:
        raise SystemExit("the plate's tally and this module's docstring disagree")
    print(f"  CONTROL the caption file's panel letters are the panels the plate draws "
          f"({''.join(sorted(drawn))}): PASS")
    #: ONE RECORD, BOTH PLATES. The sidecar describes all fifty constants and all
    #: thirteen panels, which now live on two sheets; it is written under each plate's
    #: name so neither ships without the record that documents it, and it says so.
    rec["covers_plates"] = [PLATE_NAME["SEM"] + ".png", PLATE_NAME["TXM"] + ".png"]
    for _nm in PLATE_NAME.values():
        json.dump(rec, open(os.path.join(OUT, _nm + ".caption.json"), "w"), indent=1)
    return rec


def main():
    t_start = time.time()
    tiles = _cached(os.path.join(DOCS, "parameters_tiles.json"),
                    #: THE CLASSIFIER FLAG IS PART OF THE KEY. It changes the mask
                    #: every sweep point is scored on, and without it in the key a
                    #: cache written with the classifier off answers a run with it on
                    #: -- silently, because the settings the file states would all
                    #: still match. This is the exact failure `_cached` exists to
                    #: prevent, and it was one flag away from happening.
                    _key(k=K, gate=list(GATE_GRID), cmin=list(CLEANMIN_GRID),
                         amin=list(CANDMIN_GRID), op=list(OPEN_GRID),
                         close=list(CLOSE_GRID), den=list(DENOISE_GRID),
                         single=list(SINGLE_LADDER_GRID),
                         ladder=list(LADDER), clean=CLEAN_MIN, cand=CAND_MIN,
                         clf=bool(DO.USE_REGION_CLASSIFIER)),
                    tile_evidence,
                    dict(mad_k=K, use_region_classifier=bool(DO.USE_REGION_CLASSIFIER)))
    frames = _cached(os.path.join(DOCS, "parameters_frames.json"),
                     _key(k=K, gate=GATE, ladder=list(LADDER), clean=CLEAN_MIN,
                          cand=CAND_MIN, dark=list(GATE_GRID_DARK),
                          chain=list(GATE_GRID_FRAME),
                          clf=bool(DO.USE_REGION_CLASSIFIER)),
                     frame_evidence,
                     dict(mad_k=K, gate=GATE, ladder=list(LADDER),
                          clean_min=CLEAN_MIN, cand_min=CAND_MIN,
                          use_region_classifier=bool(
                              DO.USE_REGION_CLASSIFIER)))
    const = _txm_constants()
    txm = _cached(os.path.join(DOCS, "parameters_txm.json"),
                  _key(nb=TXM_NB, grid=list(TXM_GRID), thr=const["DEFAULT_THRESHOLD"]),
                  txm_evidence, {})
    units = json.load(open(_paths.scoped("txm_background_units.json", scope=False)))
    scores = json.load(open(os.path.join(DOCS, "txm_model_scores.json")))
    stats = json.load(open(os.path.join(HERE, "txm_stats.json")))
    madk = json.load(open(os.path.join(DOCS, "madk_above_five.json")))
    madp = json.load(open(os.path.join(DOCS, "madk_paired_test.json")))
    dead = json.load(open(os.path.join(HERE, "sem_deadzone.json")))

    # The TXM arm's three records have to describe ONE model, or the rows would print a
    # threshold from one configuration beside an architecture from another.
    if str(stats.get("model_key")) != str(txm["model_key"]):
        raise SystemExit(f"paper/figures/txm_stats.json was written for model "
                         f"{stats.get('model_key')}, the deployed registry says "
                         f"{txm['model_key']}")
    if abs(float(stats.get("threshold", -1)) - float(const["DEFAULT_THRESHOLD"])) > 1e-9:
        raise SystemExit(f"txm_stats.json states threshold {stats.get('threshold')}, "
                         f"app/core/pipeline.py says {const['DEFAULT_THRESHOLD']}")
    print(f"  CONTROL txm_stats.json, the registry and pipeline.py agree on model "
          f"{txm['model_key']} at threshold {const['DEFAULT_THRESHOLD']}: PASS")

    sem = _sem_constants()
    #: ONE CALL PER ARM. Each writes its own plate and its own caption sidecar; the
    #: bars the SEM pass returns are the ones the record quotes, and the TXM pass
    #: returns the same object because `bars` is built from both arms' data.
    _letters = []
    for _arm in ("SEM", "TXM"):
        bars = draw(tiles, frames, madk, dead, txm, units, scores, stats, const,
                    sem, _arm)
        _letters.extend(bars["panel_letters"])
    #: THE RECORD DESCRIBES BOTH PLATES, so the letters it is checked against are both
    #: plates' letters. Taking them from the last call alone would have let the control
    #: pass while the sidecar described panels the TXM plate does not draw.
    bars["panel_letters"] = _letters
    rec = sidecar(tiles, frames, madk, madp, dead, txm, units, scores, stats, const, bars)
    for k_, v in rec["tally"].items():
        print(f"  {k_}: {', '.join(v)}")
    print(f"total {time.time() - t_start:.0f}s")


if __name__ == "__main__":
    main()
