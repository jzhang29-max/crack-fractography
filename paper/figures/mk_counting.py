#!/usr/bin/env python3
"""Figure 5: what over-counting and under-counting look like, in both modalities.

WHY. The paper reports a precision and a recall for each collection and leaves a reader to
imagine what the two failures look like. They look like completely different things, and
which one dominates decides what a user of the measurement should do about it: an
over-count is a bright inclusion halo or a polishing artefact that a human can see and
reject at a glance, and an under-count is a crack that was never proposed and that the
user will never be shown. A number cannot tell those apart; two pictures can.

WHAT THE AUTHOR ASKED FOR, AND WHAT THAT CHANGED
------------------------------------------------
"For figure 6, after choosing the parameter and model, I want to visually see how it
performs with the cracks overlay and I like the color distinction but can you choose a
different image for those identifications. I think the HIP Hydrogen embrittlement ones are
good to demonstrate. Also show a better TXM where it correctly labels most of it."

Three things follow, and each is a change of WHICH FRAME and WITH WHAT, never of how a
window is placed inside one.

  1. THE SPECIMEN. Each row is now drawn from the specimen the author named -- the HIP
     fields on the electron side, the hydrogen-charged 316L fatigue mosaics on the
     transmission side -- instead of from specimen series b2/b3. Those two specimens are
     OUTSIDE the b2/b3 restriction the rest of the paper reports on, so this file reads
     the FULL-corpus measurement records rather than the `_b2b3` ones, and says so in the
     caption JSON under `specimen_scope_departure`. Every other plate still reads the
     restricted record; nothing here changes what they do.

  2. ONE FRAME PER ROW, CHOSEN FOR AGREEMENT, NOT FOR FAILURE. The previous edition took,
     per column, the frame of the whole collection holding the MOST pixels of that error
     kind -- the worst case. The author asked to see the detector working, so the rule is
     now the opposite and is stated as such: among the eligible frames of the requested
     specimen, the one whose detector output agrees BEST with the operator (highest F1
     over refereed pixels). That is a flattering rule and the caption records the whole
     eligible field -- every candidate, its score, and where the chosen one ranks -- so
     the choice cannot be read as typical. The two COLUMNS are still the worst window of
     each error kind inside that frame, found by exact box sum.

  3. THE TXM ROW IS SCORED WITH THE TXM MODEL. The previous edition carried the SEM
     darkness rule onto the transmission mosaics, where it reaches F1 0.02-0.16 on these
     frames; its panels were therefore almost entirely "missed". That is a real result
     about transfer and it is Figure T6's subject, not this one's. What the application
     actually ships for TXM is the deployed ensemble -- 17-feature MLP + SAM+17 hybrid,
     mean probability, threshold 0.60, speck pruning -- and this plate now reads that
     model's own cached probability map for the frame it draws. On the chosen frame it
     scores precision 0.85 / recall 0.70 against the SEM rule's 0.20 / 0.13. The two rows
     therefore show two different detectors and each row SAYS WHICH on the figure, because
     a plate whose rows are scored differently and does not say so is a figure with the
     numbers attached to the wrong object.

     AND THEY ARE NOT ON THE SAME FOOTING. The deployed TXM model was trained on all 71
     labelled frames with none held out -- `txm_training_note()` reads that out of the
     deployed bundle and raises if it ever stops being true -- so the field in the TXM
     row is IN ITS TRAINING SET and that row's precision and recall are in-sample. The
     SEM rule fits nothing, though its one constant was selected on this corpus. Both
     statements are printed on the plate, because the alternative is a reader concluding
     from two pictures that the transmission detector is the better one when part of the
     difference is fit to these very labels.

  4. THE SEM ROW IS THE HYDROGEN-CHARGED HIP FIELD, AND ONE OF ITS TWO COLUMNS IS A
     STATEMENT RATHER THAN A MEASUREMENT. The author asked for this specimen twice. The
     frame is `HIP_24hr_SE_Side_006`, and its correction mask carries exactly two values:
     0 and 1. 574,137 pixels are painted CRACK and NOT ONE pixel is marked not-crack, so
     by the operator's own verdict no pixel on this field can be an over-count. Three
     things follow and all three are on the plate or in its record.

     First, the over-counting column cannot be measured here. Earlier editions refused
     the frame for that reason and drew the AMBIENT HIP field instead, because an empty
     red column is indistinguishable from a detector that over-counts nothing. That is
     still true, so the panel does not pretend otherwise: where the other three panels
     print the share of themselves that is their own error kind, this one prints WHY no
     such share exists. The window is then placed by agreement rather than by an error
     that is identically zero everywhere, and `densest()` reports which rule placed it.

     Second, the precision of this row is 1.0000 BY CONSTRUCTION and is not a score. It
     is recorded as `precision_is_by_construction` and the manuscript caption quotes
     recall only. Recall is a real measurement over the frame's painted pixels; the
     value is in this plate's caption file and is NOT quoted here, because it moved
     when the region classifier was enabled and a docstring cannot be made to follow a
     record.

     Third, nothing else about the frame is a compromise. Its paint is a trace, not a
     filled region -- deep share 0.145 against the 0.25 cap -- it has a databar-measured
     scale, and 2.28% of it carries a verdict, which is the same order as the ambient
     field's 2.47%.

WHAT IS STILL OUT OF REACH. `Cast_24hr_SE_Side_006` is one-sided in the same way
(3,709,448 crack, 0 not-crack) and the hydrogen-charged MAR fields (`MAR_H_HIP_*`) carry
no correction mask at all. On the transmission side the hydrogen-charged frames ARE
adjudicated in both directions, so that row needs none of this.

EVERY PANEL SHOWS BOTH ERRORS AND THE AGREEMENT. A panel selected for over-counting still
draws the under-counts and the agreement in it. Showing a pure example of each failure
would mean finding a window where the other does not occur, which is a claim about the
data rather than an illustration of a definition.

UNREVIEWED PIXELS ARE NOT AN ERROR AND ARE NOT COLOURED. Neither collection adjudicates
the whole frame. A marked pixel nobody looked at is left grey, and the caption gives the
share of each panel that is in that state, because colouring it either way would be the
mistake that once turned a precision of 0.99 into 0.29 in this project.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_counting.py
"""
import csv
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths                                       # noqa: E402

sys.path.insert(0, _paths.ANALYSIS)
sys.path.insert(0, os.path.join(_paths.ANALYSIS, "research", "improve"))
sys.dont_write_bytecode = True

import numpy as np                                  # noqa: E402
from scipy import ndimage as ndi                    # noqa: E402
import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.patches import Rectangle            # noqa: E402
from skimage import exposure                        # noqa: E402
import tifffile                                     # noqa: E402

import overlap_means_sem_txm as OV                  # noqa: E402  -- loaders and scorer
import both_modalities as BM                        # noqa: E402  -- pixel sizes
import journal_style as J                           # noqa: E402
from scalebar import scalebar                       # noqa: E402

J.use()
OUT = _paths.FIG_DIR
NAME = "F5 - over- and under-counting"

# THE RECORDS, UNRESTRICTED. The paper's own laboratory data is reported on specimen
# series b2 and b3 and the measurement scripts write a second `_b2b3` record for that
# scope. The two specimens the author asked this plate to show -- HIP on the electron
# side, hydrogen-charged 316L on the transmission side -- are NOT in that scope, so the
# `_b2b3` records do not contain them and `scoped()` would raise. This plate therefore
# reads the full-corpus records, which are a superset, and declares the departure in its
# caption JSON. Nothing else in the paper is changed by it: every other generator still
# calls `scoped()` with its default.
SCORES = _paths.scoped("overlap_means_sem_txm.json", scope=False)
TRACES = _paths.scoped("paint_region_vs_trace.json", scope=False)
LEGIB = _paths.scoped("frame_legibility.json", scope=False)

#: WHICH SPECIMEN EACH ROW DRAWS FROM. Substring tests against the frame stem, lower-cased,
#: written here rather than buried in a condition so that changing the figure's subject is
#: one edit. `HIP` picks the MAR 247 hot-isostatic-pressed fields; `hc_316l` picks the
#: hydrogen-charged 316L fatigue mosaics, which is exactly the set `OV.txm_group()` already
#: calls "AM/HC", so this plate and the by-group tables cannot disagree about membership.
#: THE ELECTRON ARM IS THE HIP FAMILY, NOT ONE PINNED FRAME. It was pinned to
#: mar_amb_hip_cbs_0010, whose mask holds 574,137 px of crack and 0 px of not-crack, so
#: over-counting could not be measured on it and two of the plate's panels carried a
#: sentence where the other two carried a percentage. Widening the arm to the specimen
#: family lets the same selection rule -- best agreement among eligible frames -- pick a
#: field that an operator ruled in BOTH directions, so every panel reports a measured
#: share. The rule is unchanged; only the pool it chooses from is.
#: THE TWO ROWS ARE DIFFERENT MATERIALS AND THE DATA WILL NOT CURRENTLY ALLOW OTHERWISE.
#: The author asked for both rows on one material, which is right -- as it stands a
#: reader comparing the rows is comparing two materials as well as two instruments.
#: `316_h_b2` was tried, since the transmission row is hydrogen-charged 316L and a
#: hydrogen-charged 316 electron series exists. It fails on a second requirement:
#:
#:   eligible for this plate  an operator ruled BOTH directions, the annotation is a
#:                            trace not a filled region, and no single object holds
#:                            more than 35% of the over-counted area
#:   drawable                 the frame has a measured field width, so a scale bar can
#:                            be drawn
#:
#: Of 20 '316_h_b2' frames exactly two are eligible -- 260708_316_H_b2_front_CBS_002
#: (F1 0.735) and _CBS_012 (F1 0.687) -- and NEITHER has a row in
#: crack_export/analysis/scale_hfw.csv, nor FEI metadata to recover one from
#: (scale.from_tiff returns None on both). The only 260708 frame with a measured width,
#: _CBS_001, has 0 px of not-crack and so cannot show over-counting at all.
#:
#: So matching the material would cost the scale bar, and a micrograph in a methods
#: paper without one is worse than a material mismatch the caption states. To fix this
#: properly, measure the field width of _CBS_002 from its databar and add it to the
#: scale table; then switch SPECIMEN["SEM"] to "316_h_b2" and this comment goes.
SPECIMEN = {"SEM": "mar_amb_hip", "TXM": "hc_316l"}
SPECIMEN_WORDS = {"SEM": "HIP (MAR 247, ambient)",
                  "TXM": "hydrogen-charged 316L fatigue"}

#: AN ARM MAY DRAW A FRAME THE OPERATOR RULED IN ONLY ONE DIRECTION, AND THE PLATE THEN
#: SAYS SO IN THE CELL. Normally a frame needs at least OV.MIN_PX of BOTH verdicts, so
#: that both columns measure something. The hydrogen-charged HIP field the author asked
#: for has 574,137 px of crack and 0 px of not-crack -- the mask holds no other value --
#: so it fails that gate, and before this constant existed the plate silently fell back
#: to the ambient HIP field. Naming the arm here is the opt-in: it says which row is
#: allowed to carry a column that cannot be measured, and everything downstream then
#: prints the reason instead of a number. It never suppresses the OTHER direction: a
#: frame with no UNDER-count is still rejected, because the under-counting column is
#: where the detector's real failure on this corpus lives.
#: BOTH VERDICTS REQUIRED, ON BOTH ARMS. The electron arm used to be allowed through
#: with crack paint alone, and the frame that won on agreement had NO not-crack verdict
#: anywhere on it. Over-counting is defined against that verdict, so its two panels
#: could carry no percentage -- they printed "no over-count is possible" where the
#: other two printed a number, and the author asked why half the plate had no
#: statistics. The honest answer was that the frame could not supply them. The fix is
#: to require a frame that can: a collection's panels are drawn from a frame carrying
#: at least MIN_PX of BOTH verdicts, so every panel on the plate reports a measured
#: share of its own window.
ONE_SIDED_OK = set()

#: An over-counting panel has to show over-counting, not one object. On the TXM frame
#: with the most over-counted pixels, 98.8% of that area is a SINGLE connected component
#: -- one large low-attenuation region the operator rejected -- so the panel was a red
#: rectangle whatever window was cut from it. A frame is eligible only if its largest
#: false-positive component is at most this share of its false-positive area. It is
#: measured HERE, from this plate's own detector output, because the two rows now run two
#: different detectors and the stored `frame_legibility.json` column describes only the
#: SEM rule. Where that file does have a row for a frame this plate measured with the same
#: detector, the two are cross-checked and a disagreement is fatal.
MAX_FP_CONCENTRATION = 0.35

#: A frame is eligible only if its annotation is a TRACE rather than a filled region: at
#: most this share of its painted-crack pixels further than 50 px inside the paint. It is
#: the criterion `paint_region_vs_trace.py` measures and `mk_txm_pipeline.py` already
#: selects on, and without it this figure is a picture of the brush. On the frames it
#: excludes, the paint asserts "there is crack in this region" over strokes 468 px wide at
#: the median, so a window inside one is solid "under-counted" whatever the detector does:
#: the first run of this figure produced exactly that, two panels of flat colour.
MAX_DEEP_SHARE = 0.25

#: THE WINDOW IS MEASURED IN BRUSH WIDTHS, NOT IN MICROMETRES. It used to be a fixed 30 um,
#: with the reasoning that a window narrower than the operator's brush shows nothing but
#: brush. The reasoning is right and the unit was wrong: 30 um was fixed while the pixel
#: size was not, and on the HIP field, which is a 41.4 um view at 6.74 nm/px, a 30 um
#: window is 4,452 px -- wider than the frame is tall. Clipped to the frame it leaves the
#: placement rule nothing to choose between, which silently disables every constraint
#: below. The window is therefore this many of the frame's OWN 90th-percentile paint
#: strokes across, which is the quantity the original reasoning was about, and the two
#: rows become comparable in the unit that matters instead of in micrometres.
#:
#: THE MULTIPLE IS A JUDGEMENT AND IT IS NOT TUNED TO THE ANSWER. It is set by how much
#: of the panel carries a VERDICT at all, which is a legibility property, and never by
#: what the verdicts say.
#:
#: IT IS STILL PER ARM, AND BOTH ARMS NOW SIT AT 6. The frame and the multiple were
#: chosen together, by search rather than by eye: every SEM frame the figure may legally
#: draw was crossed with 3, 4, 5, 6 and 8 strokes, each pair of windows was cut, and the
#: pairs were ranked on the WORSE of their two panels -- the share of the panel carrying
#: a verdict of any kind, which is what "the colouring can be read on this crop" means.
#: MAR_Amb_HIP_CBS_0010 at 6 strokes wins at 22.0% against 16.9% for the runner-up, and
#: the crop it gives is 11.6 um across on an 862 px window, so it prints sharp. The
#: dict stays because the two arms are free to differ and the search may move one of
#: them again; it is not an assertion that they must agree.
#:
#: THE OVER-COUNTED SHARE IS NOT MONOTONE IN IT AND WAS NOT WHAT SET IT: on the SEM field
#: the over-counted window holds 0.11% at 4 strokes, 0.24% at 5, 0.14% at 6 and 0.16% at
#: 8, because 7,882 of that frame's 15,901 over-counted pixels -- 49.6% of them -- fall
#: inside one 416 px box that holds no confirmed detection at all, and
#: MIN_AGREE_FRACTION below excludes that box on purpose, at every window size tried.
#: Going BELOW 4 costs the panel its subject: at 3 strokes the over-counted window holds
#: no over-counted pixel at all, and a column headed "Over-counted" that contains none
#: is worse than one that contains little. Whatever the window ends up holding, the
#: figure prints the measured share under the panel, so the choice cannot flatter it.
WINDOW_STROKES = {"SEM": 6.0, "TXM": 6.0}

#: A WINDOW THE AUTHOR CHOSE, NAMED AS SUCH. Everywhere else a window is PLACED, by
#: an exact box sum at the position holding the most of its panel's error kind, and
#: the figure says so. The author asked for a different part of the electron frame
#: than that rule returns, which is an editorial choice about a picture and a
#: perfectly reasonable one -- but it is not the rule, and a plate that quietly
#: swapped the region while still claiming "placed by most of its own error kind"
#: would be describing a search it did not run.
#:
#: So the override is explicit, it is keyed to the frame it was chosen on so it
#: cannot silently follow a change of frame, and `placed_by` reports it. The
#: percentages under each panel are measured on whatever window is drawn, so they
#: stay true either way; what changes is only which crack a reader is shown.
#:
#: Chosen from the eight well-separated windows that carry both a crack the detector
#: found and one it missed: (2176, 2688) and (256, 1920), the latter holding more
#: marked-but-rejected area than any other window on this frame.
WINDOW_OVERRIDE = {
    ("MAR_Amb_HIP_CBS_0006", "under-counted"): (2176, 2688),
    ("MAR_Amb_HIP_CBS_0006", "over-counted"): (256, 1920),
}
#: and it may never exceed this share of the frame's short side, for the reason above.
MAX_WINDOW_FRAC = 0.5
MIN_WINDOW_PX = 256

AGREE, OVER, UNDER = J.MASK, J.ROI, J.PAINT_CRACK


# ---------------------------------------------------------------- the two detectors
def sem_detector(img8, frame):
    """The SEM mask the APPLICATION emits, at the k Section 3.4 selects.

    THIS CALLED `OV.clean` UNTIL 2026-11-14 AND THAT WAS WRONG ONCE THE CLASSIFIER WENT
    ON. `OV.clean` is the area floor alone -- `clean_mask(13)` plus a 40 px component
    floor -- which is what the SEM arm emitted while `USE_REGION_CLASSIFIER` was False.
    With the flag True the app keeps only the regions the model calls crack, so this
    plate was drawing, at run time, a mask no user could obtain, under a caption that
    described the shipped detector.
    
    It went unnoticed because the in-plate cross-check against the score record only
    fires for frames the record holds, and this plate's SEM frame carries painted crack
    with no painted not-crack, so it is in none of them. `OV.sem` is the shipped
    emission and delegates to `both_modalities.emit`, the one staging copy.
    """
    return OV.sem(img8)


_PL = None
_APPDATA = None


def _txm_app():
    """The deployed TXM pipeline module and the app's frame index, imported once.

    Imported lazily and from the TXM checkout, exactly as `txm_full.py` does it, so the
    threshold and the speck floor are the shipped constants rather than copies.
    """
    global _PL, _APPDATA
    if _PL is None:
        R = _paths.require(_paths.TXM_REPO, "the TXM_Crack_Detection_Pipeline checkout",
                           "TXM_REPO")
        for p in (os.path.join(R, "code"), os.path.join(R, "app")):
            if p not in sys.path:
                sys.path.insert(0, p)
        import core.pipeline as PL                   # noqa: E402
        _PL = PL
        base = os.path.join(R, "app_data", "images")
        _APPDATA = {}
        for d in sorted(os.listdir(base)):
            mp = os.path.join(base, d, "meta.json")
            if os.path.exists(mp):
                _APPDATA[json.load(open(mp))["filename"]] = os.path.join(base, d)
    return _PL, _APPDATA


def txm_training_note():
    """Was the frame this plate draws in the deployed TXM model's training set?

    Read, not assumed. The deployed hybrid bundle records how many images it was trained
    on and which reference frames were held out; the app's own index says how many
    carry an operator correction. If nothing was held out and the two counts agree, every
    labelled frame trained the model and the one drawn here is in sample. If a future
    bundle DOES hold frames out, this raises rather than quietly keeping a sentence that
    has stopped being true.
    """
    import joblib
    path = os.path.join(_paths.TXM_REPO, "models", "hybrid_v5_20260824.joblib")
    _paths.require(path, "the deployed TXM hybrid model", "TXM_REPO")
    b = joblib.load(path)
    n_train = int(b.get("trained_on_images", -1))
    held = list(b.get("reference_held_out") or [])
    _, index = _txm_app()
    labelled = 0
    for d in index.values():
        cc = json.load(open(os.path.join(d, "meta.json"))).get("corr_counts") or {}
        labelled += int((cc.get("crack", 0) + cc.get("not", 0)) > 0)
    if held or n_train != labelled:
        raise SystemExit(
            f"the deployed TXM model reports trained_on_images={n_train} and "
            f"reference_held_out={held!r} against {labelled} labelled frames in the "
            f"app. This plate's 'in its training set' line assumes nothing was held "
            f"out; check whether the frame it draws is in sample before trusting it.")
    return {"trained_on_images": n_train, "labelled_frames": labelled,
            "reference_held_out": held, "bundle": os.path.basename(path),
            "means": "no labelled frame was held out, so the field this plate draws is "
                     "IN SAMPLE and the precision and recall printed for the TXM row "
                     "are in-sample. The out-of-sample estimate for this model is the "
                     "grouped-by-image cross-validation in txm_model_scores.json."}


def txm_detector(shape, frame):
    """The deployed TXM ensemble's own mask for one frame, from the app's cached output.

    prob.npy is what the application wrote when it ingested the frame with the deployed
    model -- the mean of the 17-feature MLP and the SAM+17 hybrid -- so this is the model
    the tool ships, not a re-implementation. Thresholding and speck pruning are the
    shipped `pipeline` functions and the shipped constants.
    """
    PL, index = _txm_app()
    d = index.get(frame + ".tif")
    if d is None:
        raise SystemExit(f"TXM: {frame} has no app_data entry, so the deployed model's "
                         f"output for it does not exist. Ingest it in the application "
                         f"first, or choose another frame.")
    path = os.path.join(d, "prob.npy")
    if not os.path.exists(path):
        raise SystemExit(f"TXM: {path} is missing")
    prob = np.asarray(np.load(path, mmap_mode="r"))
    if prob.shape != shape:
        raise SystemExit(f"TXM: {frame} probability map is {prob.shape} and its "
                         f"correction mask is {shape}; they are not the same frame")
    return PL.prune_specks(prob > PL.DEFAULT_THRESHOLD), PL.DEFAULT_THRESHOLD


DETECTOR_WORDS = {
    "SEM": "multi-scale darkness detector",
    "TXM": "trained TXM model (17 features + SAM)",
}

#: THE TWO ROWS ARE NOT ON THE SAME FOOTING AND THE FIGURE SAYS SO. The SEM rule fits
#: nothing -- it has no model file -- though its one constant, mad_k = 6, was selected on
#: this corpus leave-one-image-out, so it is not free of the data either. The deployed
#: TXM model was trained on every labelled frame with none held out, which
#: `txm_training_note()` verifies against the deployed bundle rather than asserting, so
#: the frame this plate draws is IN ITS TRAINING SET and the precision and recall printed
#: for the TXM row are in-sample. Its out-of-sample estimate is the grouped-by-image
#: cross-validation in docs/figures/txm_model_scores.json (IoU 0.792, and grouped by
#: image rather than by specimen). Without this line a reader reads the transmission row
#: as the better detector when part of the difference is fit to these very labels.
DETECTOR_CAVEAT = {"SEM": "no fitted model", "TXM": "in its training set"}


# ---------------------------------------------------------------- pixel size, per frame
_HFW = None


def sem_nm_per_px(frame):
    """nm/px for ONE SEM field, from the instrument databar, not from a constant.

    The SEM corpus spans a 249x magnification range -- HFW 10.4 um to 2.59 mm -- so a
    single pixel size is a property of one field and not of the collection. The previous
    edition drew every SEM panel at 42.1941 nm/px, which is right for the 260622 b2 fields
    it was written for and wrong by a factor of 6.3 for the HIP field this one shows. The
    authoritative table is HFW / image width, tabulated per frame from the databar in
    `crack_export/analysis/scale_hfw.csv` and explained in the CORRECTION note beside it.
    The width is the ORIGINAL tif's, before `find_field_of_view` trims the databar rows:
    cropping does not change the size of a pixel.
    """
    global _HFW
    path = os.path.join(_paths.SEM_REPO, "crack_export", "analysis", "scale_hfw.csv")
    if _HFW is None:
        _paths.require(path, "the per-frame SEM scale table", "SEM_REPO")
        with open(path) as fh:
            _HFW = {r["SourceImage"]: float(r["HFW_um"]) for r in csv.DictReader(fh)}
    if frame not in _HFW:
        raise SystemExit(
            f"{frame} has no databar-measured field width in {path}, so no scale bar can "
            f"be drawn for it. Choose a frame that has one, or measure this one.")
    tif = os.path.join(_paths.SEM_REPO, "original", frame + ".tif")
    with tifffile.TiffFile(tif) as tf:
        w = int(tf.pages[0].shape[1])
    nm = _HFW[frame] * 1000.0 / w
    src = (f"databar: printed horizontal field width {_HFW[frame]:g} um over {w} px "
           f"({os.path.relpath(path, _paths.SEM_REPO)})")
    return nm, src


# ---------------------------------------------------------------- frame selection
def _fp_largest_share(mask, neg, fp):
    """Share of the false-positive area held by its largest connected component.

    8-connected, matching `frame_legibility.py`, so the two numbers are comparable.
    """
    lab, n = ndi.label(mask & neg, np.ones((3, 3), bool))
    if not (n and fp):
        return 0.0
    sz = np.bincount(lab.ravel())
    sz[0] = 0
    return float(sz.max()) / fp


def _trace_table(coll):
    return {r["frame"]: r["deep_share"]
            for r in json.load(open(TRACES))[coll]["frames"]}


def _legibility_table(coll):
    return {r["frame"]: r for r in json.load(open(LEGIB))[coll]}


def _scores_table(coll):
    return {r["frame"]: r for r in json.load(open(SCORES))[coll]["per_frame"]}


def score_candidates(coll, loaded, pre_rejected):
    """Score every frame of the requested specimen with THAT ROW'S detector.

    `loaded` is {frame: (img8, corr)} for the frames that could be read. Returns the rows
    kept, the rows rejected with the reason, the chosen frame, and every candidate's mask
    so the chosen frame's detector is not run twice.
    """
    deep = _trace_table(coll)
    legib = _legibility_table(coll)
    rows, rejected, masks = [], list(pre_rejected), {}
    for frame in sorted(loaded):
        img8, corr = loaded[frame]
        pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
        c, n = int(pos.sum()), int(neg.sum())
        one_sided = c >= OV.MIN_PX and n < OV.MIN_PX and coll in ONE_SIDED_OK
        if c < OV.MIN_PX or (n < OV.MIN_PX and not one_sided):
            rejected.append({"frame": frame, "why": "needs at least "
                             f"{OV.MIN_PX} px of BOTH operator verdicts and has "
                             f"{c:,} crack / {n:,} not-crack", "crack_px": c,
                             "notcrack_px": n})
            continue
        if frame in deep:
            d = deep[frame]
            measured_here = False
        elif one_sided:
            # THE STORED TABLE CANNOT HAVE THIS FRAME. paint_region_vs_trace.py applies
            # the same both-verdicts gate before it measures, so a one-sided frame is
            # absent from it by construction, not by staleness. The statistic is its
            # own definition -- the share of painted-crack pixels further than 50 px
            # from the edge of the paint -- so it is computed here on the same mask and
            # the caption records that this row's deep share was measured in-plate.
            dt = ndi.distance_transform_edt(pos)
            d = float((dt[pos] > 50).mean())
            measured_here = True
        else:
            raise SystemExit(f"{coll}: no trace/region measurement for {frame}")
        if d > MAX_DEEP_SHARE:
            rejected.append({"frame": frame, "why": "the annotation is a filled region, "
                             f"not a trace: deep share {d:.3f} > "
                             f"{MAX_DEEP_SHARE}", "deep_share": d})
            continue
        if coll == "SEM":
            mask = sem_detector(img8, frame)
        else:
            mask, _thr = txm_detector(corr.shape, frame)
        masks[frame] = mask
        tp = int((mask & pos).sum())
        fp = int((mask & neg).sum())
        fn = int((pos & ~mask).sum())
        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        conc = _fp_largest_share(mask, neg, fp)
        row = {"frame": frame, "crack_px": c, "notcrack_px": n,
               "one_sided": one_sided, "deep_share_measured_in_plate": measured_here,
               "refereed_frac": float((pos | neg).mean()),
               "deep_share": d, "precision": p, "recall": r, "f1": f1,
               "tp_px": tp, "fp_px": fp, "fn_px": fn, "fp_largest_share": conc}
        # CROSS-CHECK against the stored measurement, where it describes the same
        # detector on the same frame. A figure that re-measures silently is a figure that
        # can drift away from the table beside it.
        if coll == "SEM" and frame in legib:
            for key, got in (("precision", p), ("recall", r),
                             ("fp_largest_share", conc)):
                want = legib[frame][key]
                if abs(want - got) > 1e-6:
                    raise SystemExit(
                        f"{coll} {frame}: this plate measures {key} = {got:.6f} and "
                        f"{os.path.basename(LEGIB)} records {want:.6f}. One of them is "
                        f"stale; regenerate frame_legibility.py or fix the loader.")
            row["agrees_with_frame_legibility"] = True
        # An absent UNDER-count still disqualifies a frame: that column is where this
        # corpus's real failure lives. An absent OVER-count disqualifies it too UNLESS
        # the operator left no not-crack verdict at all, in which case the absence is a
        # property of the annotation, it is known, and the panel prints it.
        if fn == 0 or (fp == 0 and not one_sided):
            rejected.append({"frame": frame, "why": "one of the two error kinds does not "
                             f"occur on it ({fp:,} over-counted, {fn:,} under-counted), "
                             "so one column would be empty by construction",
                             "fp_px": fp, "fn_px": fn})
            continue
        if one_sided:
            print(f"  {coll} ONE-SIDED  {frame[:52]:<54} the operator ruled {c:,} px "
                  f"crack and {n:,} px not-crack, so the over-counting column is a "
                  f"statement, not a measurement; precision {p:.4f} is by construction",
                  flush=True)
        if conc > MAX_FP_CONCENTRATION:
            rejected.append({"frame": frame, "why": "one object holds "
                             f"{100 * conc:.1f}% of the over-counted area (cap "
                             f"{100 * MAX_FP_CONCENTRATION:.0f}%), so the over-counted "
                             "panel would illustrate that object", **row})
            continue
        rows.append(row)
        print(f"  {coll} candidate {frame[:52]:<54} P {p:.4f} R {r:.4f} F1 {f1:.4f}  "
              f"over {fp:>9,}  under {fn:>9,}  largest-fp {100 * conc:4.1f}%", flush=True)
    for q in rejected:
        print(f"  {coll} rejected  {q['frame'][:52]:<54} {q['why']}", flush=True)
    if not rows:
        raise SystemExit(
            f"{coll}: no frame of the '{SPECIMEN[coll]}' specimen can carry this figure. "
            f"Every candidate is listed above with the reason. Change SPECIMEN[{coll!r}] "
            f"or relax a named constraint -- do not fall back silently.")
    ranked = sorted(rows, key=lambda r: (-r["f1"], r["frame"]))
    best = ranked[0]
    print(f"  {coll}: {len(rows)} eligible of {len(loaded)} '{SPECIMEN[coll]}' frames; "
          f"best agreement is {best['frame'][:52]} at F1 {best['f1']:.4f} "
          f"(eligible F1 range {min(r['f1'] for r in rows):.4f}-"
          f"{max(r['f1'] for r in rows):.4f})", flush=True)
    return ranked, rejected, best, masks


# ---------------------------------------------------------------- loaders
def load_sem(token):
    """One pass over the SEM corpus, keeping only the requested specimen's frames.

    `OV.sem_frames()` is the loader the scorer uses -- same contrast kwargs, same
    field-of-view trim, same correction mask -- so a frame this plate draws is the frame
    the table scored. It reads the tif before it yields, so the filter cannot save the
    read; one pass is still cheaper than the two the previous edition made.
    """
    out = {}
    for nm, img8, corr in OV.sem_frames():
        if token in nm.lower():
            out[nm] = (img8, corr)
            print(f"  SEM loaded   {nm[:52]:<54} {img8.shape}", flush=True)
    if not out:
        raise SystemExit(f"SEM: no frame with a correction mask matches '{token}'")
    return out, []


def load_txm(token):
    """The requested specimen's TXM frames, read one by one rather than by a full sweep.

    `OV.txm_frames()` enumerates `paint/corrections/` and loads every tif in it; this
    needs nine of seventy-one, so it enumerates the same directory and makes the same
    `D.load_as_uint8` call on the ones it wants, with the same shape check. Opened
    READ-ONLY, like every other reader of that directory.
    """
    corr_dir = os.path.join(_paths.TXM_REPO, "paint", "corrections")
    _paths.require(corr_dir, "the TXM correction masks", "TXM_REPO")
    out, pre = {}, []
    for f in sorted(os.listdir(corr_dir)):
        if not f.endswith("_correction.npy"):
            continue
        stem = f[: -len("_correction.npy")]
        if token not in stem.lower():
            continue
        tif = os.path.join(_paths.TXM_REPO, "images", stem + ".tif")
        if not os.path.exists(tif):
            pre.append({"frame": stem, "why": "no micrograph on disk for this mask"})
            continue
        corr = np.asarray(np.load(os.path.join(corr_dir, f)))
        c = int((corr == 1).sum())
        if c < OV.MIN_PX:
            # Not loaded at all: with no painted crack there is nothing for the figure
            # to be right or wrong about, and reading the mosaic would cost a minute per
            # frame for a candidate that cannot be chosen. Recorded, not silent.
            pre.append({"frame": stem, "why": "the operator painted no crack on it "
                        f"({c:,} px, needs {OV.MIN_PX})", "crack_px": c,
                        "notcrack_px": int(((corr == 2) | (corr == 3)).sum())})
            continue
        img8 = OV.D.load_as_uint8(tif)
        if img8.shape != corr.shape:
            pre.append({"frame": stem, "why": f"micrograph is {img8.shape} and its "
                        f"correction mask is {corr.shape}"})
            continue
        out[stem] = (img8, corr)
        print(f"  TXM loaded   {stem[14:66]:<54} {img8.shape}", flush=True)
    if not out:
        raise SystemExit(f"TXM: no frame with a correction mask matches '{token}'")
    return out, pre


#: A panel must not be a solid block of one colour. The paint here is broad-brush -- the
#: SEM stroke is 14 um wide at the 90th percentile -- so the window holding the MOST
#: pixels of an error kind is routinely a window holding nothing else: the first run of
#: this figure produced an under-counted panel that was 99.98% under-counted and an
#: over-counted panel that was 100% over-counted, which show a colour rather than a
#: failure. Capping the error kind's share forces the window onto the BOUNDARY of the
#: error, where the mask, the paint and the matrix are all visible at once.
MAX_ERROR_SHARE = 0.25


#: A window may not be mostly pixels nobody adjudicated. The under-counting panel first
#: came out two thirds BLACK: the frame's widest crack has an unreviewed interior, the
#: detector marks it, and an unreviewed pixel is correctly left uncoloured -- so the panel
#: was dominated by a region that carries no verdict either way and illustrates neither
#: error. Capping that share puts the window on the part of the crack a human actually
#: ruled on.
MAX_UNREVIEWED_SHARE = 0.25


#: A window must also SHOW something. Over-counting on the transmission frames is sparse
#: and diffuse, so the window holding the most of it was 97.9% plain micrograph -- 1.59%
#: over-counted, 0.39% under-counted, no agreement at all -- which reads as a blank grey
#: square rather than as an error. The window is therefore chosen among those carrying at
#: least this fraction of the MOST CONFIRMED mask any window of that frame can hold. An
#: error panel is only legible beside the thing it is an error about: the over-counted
#: panel first landed on an off-specimen void with no crack anywhere in it, which shows
#: the detector marking a pit rather than mis-marking a crack. Requiring agreement in
#: the window puts the error next to correct detection, so the reader sees all three
#: verdicts at once. The bound is RELATIVE, not absolute, because an absolute floor
#: admitted no window at all on the sparser transmission frames and fell straight back
#: to the unconstrained maximum -- the blank panel it was meant to prevent. Relative,
#: the best-agreeing window always qualifies and the rule is never silently off.
MIN_AGREE_FRACTION = 0.35

#: A panel may not be mostly nothing. These fields are cut from fracture surfaces and a
#: large part of some frames is off the specimen entirely, at an 8-bit value of ~0: the
#: under-counted panel came out with its top third solid black, which is not an image of
#: a detection error. Windows carrying more than this share of no-signal pixels are
#: inadmissible. 10 of 255 is the detector's own absolute darkness floor, reused here.
NO_SIGNAL_DN, MAX_NO_SIGNAL_SHARE = 10, 0.05

#: The window must not straddle the EDGE of the region an operator ruled on. The paint
#: stops dead at that edge, so a window crossing it shows a bar of flat colour running
#: the full height of the panel -- the boundary of the annotation, not of a crack, and
#: the most eye-catching thing in the panel. Measured as the count of adjudicated pixels
#: that touch an unadjudicated one: a straight edge crossing the window contributes about
#: one window-side of them, a crack's own paint outline far fewer. A bounding box will
#: NOT do this job: scattered paint puts the box at nearly the whole frame, so the
#: restriction is vacuous where it is needed and empties the candidate set where it is
#: not, and neither will the TOTAL length of that edge: a crack's own paint outline is
#: long and irregular, so bounding the total merely prefers windows with little
#: annotation in them -- it moved the over-counted panel from 1.63% over-counted to
#: 0.58%, losing the error the panel exists to show. What distinguishes the artefact is
#: that it is STRAIGHT: a review boundary crossing the window puts most of its pixels in
#: a single column or row, where a crack outline spreads over many. The bound is
#: therefore on the fullest single column or row of annotation edge, as a fraction of
#: the window side, and it is applied last so it can never empty the candidate set.
#: Measured on the transmission frame this was drawn for: the statistic runs 45 to
#: 357 over its windows against a 1026 px side, so 0.40 passed every one of them
#: and bound nothing. 0.20 is inside that range and actually selects.
MAX_STRAIGHT_EDGE_FRAC = 0.20


def _boxsum(mask, sdim):
    ii = np.pad(np.cumsum(np.cumsum(mask.astype(np.int64), 0), 1), ((1, 0), (1, 0)))
    return (ii[sdim:, sdim:] - ii[:-sdim, sdim:] - ii[sdim:, :-sdim]
            + ii[:-sdim, :-sdim])


def densest(mask, side, max_frac=MAX_ERROR_SHARE, veto=None,
            max_veto=MAX_UNREVIEWED_SHARE, agree=None,
            min_agree=MIN_AGREE_FRACTION, nosignal=None,
            max_nosignal=MAX_NO_SIGNAL_SHARE, inside=None, avoid=None):
    """The `side` x `side` window holding the most True pixels, among the admissible ones.

    Exact, not sampled: box sums over the summed-area table, then the maximum over the
    boxes whose True fraction is at most `max_frac` and whose `veto` fraction is at most
    `max_veto`. Falls back to the unconstrained maximum when no box satisfies both and
    SAYS SO in the caption file, rather than silently returning a window chosen by a
    different rule than the caption states.
    """
    h, w = mask.shape
    sdim = min(side, h, w)
    box = _boxsum(mask, sdim)

    # WHEN THE ERROR KIND DOES NOT OCCUR ANYWHERE ON THE FRAME, every window holds the
    # same zero of it and `box.argmax()` returns the top-left corner -- a window chosen
    # by array order, which is not a rule and would read as one. The panel is then
    # ranked by AGREEMENT instead, so it still shows the detector working on the field,
    # and the caller is told which rule placed it so the figure can say so.
    rank, placed_by = box, "most of its own error kind"
    cons = []
    # TWO PANELS OF ONE FRAME MUST NOT BE THE SAME PICTURE. Where a row's two windows
    # are ranked by two different quantities that happen to peak in the same place --
    # which is what happens on a one-sided frame, whose over-counting panel falls back
    # to agreement and whose under-counting panel sits on the same crack -- the second
    # window is required not to overlap the first. It is the WEAKEST constraint, so it
    # is dropped before any other if nothing satisfies the set, and the caller is told.
    if avoid is not None:
        ay, ax, asd = avoid
        yy = np.arange(box.shape[0])[:, None]
        xx = np.arange(box.shape[1])[None, :]
        cons.append(("no overlap with the other panel",
                     ~((yy < ay + asd) & (yy + sdim > ay)
                       & (xx < ax + asd) & (xx + sdim > ax))))
    abox = _boxsum(agree, sdim) if agree is not None else None
    if not mask.any():
        if abox is None:
            raise SystemExit("densest: the error kind does not occur on this frame and "
                             "no agreement mask was given to place the window by")
        rank, placed_by = abox, "most confirmed detection (its error kind does not " \
                                "occur on this frame)"
    if agree is not None:
        if abox.max() > 0:
            cons.append(("agreement", abox >= min_agree * float(abox.max())))
    if nosignal is not None:
        cons.append(("no signal",
                     _boxsum(nosignal, sdim) <= max_nosignal * sdim * sdim))
    if veto is not None:
        cons.append(("unreviewed",
                     _boxsum(veto, sdim) <= max_veto * sdim * sdim))
    cons.append(("error share", box <= max_frac * sdim * sdim))

    dropped = []
    while True:
        ok = np.ones_like(box, dtype=bool)
        for _n, c in cons:
            ok &= c
        if ok.any() or not cons:
            break
        dropped.append(cons.pop(0)[0])

    # The straight-annotation-edge bound, applied last over the surviving windows only,
    # so it can never empty the candidate set.
    if inside is not None and ok.any():
        edge = (inside & ~ndi.binary_erosion(inside, np.ones((3, 3), bool))
                ).astype(np.int32)
        ny, nx = box.shape
        off = (sdim - 1) // 2
        # fullest single COLUMN of edge inside each window
        colsum = np.cumsum(edge, axis=0)
        colsum = np.vstack([colsum[sdim - 1:sdim], colsum[sdim:] - colsum[:-sdim]])
        cmax = ndi.maximum_filter1d(colsum, size=sdim, axis=1, mode="constant",
                                    cval=0)[:, off:off + nx]
        # fullest single ROW
        rowsum = np.cumsum(edge, axis=1)
        rowsum = np.hstack([rowsum[:, sdim - 1:sdim], rowsum[:, sdim:] - rowsum[:, :-sdim]])
        rmax = ndi.maximum_filter1d(rowsum, size=sdim, axis=0, mode="constant",
                                    cval=0)[off:off + ny, :]
        straight = np.maximum(cmax[:ny, :nx], rmax[:ny, :nx])
        quiet = ok & (straight <= MAX_STRAIGHT_EDGE_FRAC * sdim)
        if quiet.any():
            ok = quiet
        else:
            dropped.append("straight review edge")
    capped = bool(ok.any())
    search = np.where(ok, rank, -1) if capped else rank
    y, x = np.unravel_index(int(search.argmax()), search.shape)
    return int(y), int(x), sdim, int(box[y, x]), (capped, dropped, placed_by)


def paint_width_p90(pos):
    """The 90th-percentile paint stroke, in pixels: `OV.width_p90` on this frame's crack."""
    return OV.width_p90(pos)


def window_side(pos, shape, strokes):
    """`strokes` of the frame's own brush, clamped so a window can still be placed."""
    p90 = paint_width_p90(pos)
    want = int(round(strokes * p90))
    ceil = int(MAX_WINDOW_FRAC * min(shape))
    side = max(MIN_WINDOW_PX, min(want, ceil))
    return side, p90, want, ceil


def main():
    panels, meta = [], {}
    loaders = {"SEM": load_sem, "TXM": load_txm}
    for coll in ("SEM", "TXM"):
        print(f"\n{coll}: frames of the '{SPECIMEN[coll]}' specimen", flush=True)
        loaded, pre = loaders[coll](SPECIMEN[coll])
        ranked, rejected, best, masks = score_candidates(coll, loaded, pre)
        frame = best["frame"]
        img8, corr = loaded[frame]
        mask = masks[frame]
        pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
        if coll == "SEM":
            thr = None
            nm, scale_src = sem_nm_per_px(frame)
        else:
            thr = _txm_app()[0].DEFAULT_THRESHOLD
            # ONE CONSTANT FOR EVERY MOSAIC, AND IT WAS DERIVED FROM ANOTHER ONE. 29.24
            # nm/px comes from 9x5 tiles of a 30 um window at 0.35 overlap over a
            # 6367x3691 px mosaic -- a b2/b3 acquisition. The hydrogen-charged mosaics
            # are a different size and were not part of that derivation; the same tile
            # geometry is assumed for them, which is what every other TXM plate in this
            # paper also assumes. Said here so the bar is read with its provenance.
            nm = BM.TXM_NM_PER_PX
            scale_src = (BM.TXM_SCALE_SOURCE + "; the derivation is from a 6367x3691 px "
                         f"b2/b3 mosaic and this frame is {corr.shape[1]}x{corr.shape[0]}"
                         " px, so the same per-tile geometry is assumed for it")
        agree, over, under = mask & pos, mask & neg, pos & ~mask
        side, p90, want, ceil = window_side(pos, corr.shape, WINDOW_STROKES[coll])
        # The window size is load-bearing and it comes from a measured label property, so
        # it is checked against the stored measurement of the same property.
        stored = _scores_table(coll).get(frame, {}).get("paint_width_p90_px")
        if stored is not None and abs(stored - p90) > 1e-6:
            raise SystemExit(
                f"{coll} {frame}: this plate measures a 90th-percentile paint stroke of "
                f"{p90:.4f} px and {os.path.basename(SCORES)} records {stored:.4f}. The "
                f"window size is derived from it, so one of the two is stale.")
        meta[coll] = {
            "specimen_token": SPECIMEN[coll], "specimen": SPECIMEN_WORDS[coll],
            "detector": DETECTOR_WORDS[coll], "detector_threshold": thr,
            "scoring_footing": (
                {"in_sample": True,
                 "note": "the SEM arm DOES fit something: the region classifier is "
                         "enabled and its nine weights decide which candidate regions "
                         "survive, on frames that are among the images it was fitted "
                         "on. Its candidate constant mad_k = 6 was additionally "
                         "selected on this corpus "
                         "leave-one-image-out (docs/figures/lab_madk_sweep.json), so it "
                         "is not independent of these frames either"}
                if coll == "SEM" else
                dict({"in_sample": True}, **txm_training_note())),
            "frame": frame, "precision": best["precision"], "recall": best["recall"],
            "f1": best["f1"], "tp_px": best["tp_px"], "fp_px": best["fp_px"],
            "fn_px": best["fn_px"], "crack_px": best["crack_px"],
            "notcrack_px": best["notcrack_px"],
            "refereed_share_of_frame": best["refereed_frac"],
            "one_sided": best["one_sided"],
            "precision_is_by_construction": (
                "the operator left no not-crack verdict on this field, so no marked "
                "pixel on it can be counted wrong and the precision of %.4f below is 1 "
                "by construction, not a score. Recall, %.4f over the %s painted pixels, "
                "IS a measurement. Quote recall."
                % (best["precision"], best["recall"], f"{best['crack_px']:,}")
                if best["one_sided"] else False),
            "deep_share_measured_in_plate": best["deep_share_measured_in_plate"],
            "fp_largest_share": best["fp_largest_share"],
            "max_fp_concentration": MAX_FP_CONCENTRATION,
            "deep_share": best["deep_share"], "max_deep_share": MAX_DEEP_SHARE,
            "n_frames_of_specimen": len(loaded), "n_eligible": len(ranked),
            "eligible_ranked": [{k: r[k] for k in
                                 ("frame", "precision", "recall", "f1", "fp_px", "fn_px",
                                  "fp_largest_share")} for r in ranked],
            "rejected": rejected,
            "window_strokes": WINDOW_STROKES[coll],
            "paint_width_p90_px": p90, "window_side_px": side,
            "window_side_requested_px": want, "window_side_cap_px": ceil,
            "nm_per_px": nm, "scale_provenance": scale_src,
        }
        # ORDER MATTERS ON A ONE-SIDED FRAME. The over-counting panel there is placed
        # by agreement, and agreement peaks on the same crack the under-counting panel
        # sits on, so the two came out as the same 447 px box twice. The MEASURABLE
        # column is therefore placed first and the other is kept off it.
        placed, order = {}, (("under-counted", "over-counted") if not neg.any()
                             else ("over-counted", "under-counted"))
        for kind in order:
            sel = over if kind == "over-counted" else under
            y, x, sdim, cnt, (capped, dropped, placed_by) = densest(
                sel, side, veto=mask & ~pos & ~neg, agree=agree,
                nosignal=img8 < NO_SIGNAL_DN, inside=pos | neg,
                avoid=(placed.get(order[0])
                       if kind == order[1] and not neg.any() else None))
            _ov = WINDOW_OVERRIDE.get((frame, kind))
            if _ov is not None:
                _oy, _ox = _ov
                if not (0 <= _oy <= corr.shape[0] - sdim
                        and 0 <= _ox <= corr.shape[1] - sdim):
                    raise SystemExit(
                        f"the window chosen for {frame} {kind} at {_ov} does not fit "
                        f"a {sdim} px box in a {corr.shape} frame")
                y, x = _oy, _ox
                cnt = int(sel[y:y + sdim, x:x + sdim].sum())
                placed_by = ("chosen by the author from the windows carrying both a "
                             "found and a missed crack, not placed by the search")
            placed[kind] = (y, x, sdim)
            # The one line this panel prints in place of its own percentage, when that
            # percentage is zero for a reason the reader has to be told.
            impossible = ("no over-count is possible: 0 px ruled not-crack"
                          if kind == "over-counted" and not neg.any() else None)
            sl = (slice(y, y + sdim), slice(x, x + sdim))
            # 0.5/99.5, not 2/98: on the BSE side-view frames 2/98 clips enough of the
            # dark tail that the matrix prints as paper-white and the panel loses its
            # context entirely. These are also the percentiles the application's own
            # 8-bit loader uses, so the panel is stretched the way the operator saw it.
            lo, hi = np.percentile(img8[sl], [0.5, 99.5])
            grey = (exposure.rescale_intensity(img8[sl].astype(np.float32),
                                               in_range=(lo, hi), out_range=(0.0, 1.0))
                    if hi > lo else img8[sl].astype(np.float32) / 255.0)
            rgb = np.dstack([grey] * 3)
            rgb[under[sl]] = np.array(J.rgb(UNDER))
            rgb[agree[sl]] = np.array(J.rgb(AGREE))
            rgb[over[sl]] = np.array(J.rgb(OVER))
            #: WHAT THE ERROR LOOKS LIKE, MEASURED. A reviewer asked this plate to
            #: "show raw image or explain where it is over / undercounting in terms
            #: of image". The raw window is now drawn beside every overlay, and the
            #: question behind the request -- what IS the detector reacting to --
            #: is answered with a number rather than with an adjective.
            #:
            #: The statistic is the MEDIAN of the displayed grey, on the same 0.5/99.5
            #: stretch the panel beside it is drawn at, so a reader can check any of
            #: these against the picture. Median, not mean: these classes are small
            #: and often touch a bright inclusion or the frame's dark edge, and one
            #: such tail drags a mean somewhere no pixel in the class actually is.
            #:
            #: The reference classes are the operator's own: `agree` is crack both
            #: parties accept, and `matrix` is what the operator ruled NOT crack and
            #: the detector also left alone -- the uncontested background. An error
            #: class sitting at the crack level says intensity cannot separate it;
            #: sitting at the matrix level says no darkness rule would ever reach it.
            _matrix = neg[sl] & ~mask[sl]
            def _med(m):
                return round(float(np.median(grey[m])), 4) if m.any() else None
            _greys = {"over": _med(over[sl]), "under": _med(under[sl]),
                      "agree": _med(agree[sl]), "matrix": _med(_matrix)}
            _counts = {"over": int(over[sl].sum()), "under": int(under[sl].sum()),
                       "agree": int(agree[sl].sum()), "matrix": int(_matrix.sum())}
            panels.append({
                "coll": coll, "kind": kind, "rgb": np.clip(rgb, 0, 1), "nm": nm,
                "grey": grey,
                #: the three verdict masks, kept so the overlay panel can draw the
                #: photograph smoothly and each verdict exactly. Burnt into one RGB
                #: array they share a single resampling rule, and the only rule that
                #: is honest for a mask -- nearest neighbour -- is the one that makes
                #: a 2.9 Mpx transmission frame look blocky.
                "m_under": under[sl].copy(), "m_agree": agree[sl].copy(),
                "m_over": over[sl].copy(),
                "median_grey_on_displayed_stretch": _greys,
                "median_grey_px": _counts,
                "median_grey_note": (
                    "median of the panel's own 0.5/99.5-stretched grey, 0 = black, "
                    "1 = white. agree = crack both parties accept; matrix = pixels "
                    "the operator ruled not-crack and the detector did not mark."),
                "frame": frame, "side": sdim, "origin": [y, x], "selected_px": cnt,
                "fov_um": sdim * nm / 1000.0, "share_caps_applied": capped,
                "constraints_dropped": dropped, "placed_by": placed_by,
                "kind_impossible": impossible,
                "max_error_share": MAX_ERROR_SHARE,
                "max_unreviewed_share": MAX_UNREVIEWED_SHARE,
                "agree_pct": 100 * float(agree[sl].mean()),
                "over_pct": 100 * float(over[sl].mean()),
                "under_pct": 100 * float(under[sl].mean()),
                "marked_unreviewed_pct": 100 * float(
                    (mask[sl] & ~pos[sl] & ~neg[sl]).mean())})
            print(f"  {coll} {kind:<14} {frame[:44]:<46} window {sdim} px "
                  f"({sdim * nm / 1000:.2f} um) at ({y},{x}) placed by {placed_by}: "
                  f"agree {panels[-1]['agree_pct']:5.2f}%  over "
                  f"{panels[-1]['over_pct']:5.2f}%  under "
                  f"{panels[-1]['under_pct']:5.2f}%  unreviewed "
                  f"{panels[-1]['marked_unreviewed_pct']:5.2f}%  dropped {dropped}",
                  flush=True)

    # ------------------------------------------------------------------ the plate
    W = J.PAGEW
    Mg = 0.03
    LAB = 0.26
    GAP = 0.16          # between the two error kinds
    PAIR = 0.035        # between a raw panel and the overlay it belongs to
    #: FOUR PANELS PER ROW, NOT TWO, at a reviewer's request: "can help to show raw
    #: image or explain where it is over / undercounting in terms of image". An
    #: overlay on its own asks the reader to take on trust that the coloured pixels
    #: correspond to something in the micrograph; the raw window beside it, at the
    #: same place and the same stretch, lets them check. The two are a PAIR and are
    #: spaced as one -- PAIR between them, the wider GAP between the error kinds --
    #: so the grouping is read off the layout and does not need saying.
    PAN = (W - 2 * Mg - LAB - 2 * PAIR - GAP) / 4
    HDR = 0.40
    # Under each row: one line per panel saying how much of IT is the error it was chosen
    # for, then two lines for the row. The per-panel line exists because a panel can be
    # honestly almost empty -- the SEM field's precision is 0.97, so its over-counted
    # window is 0.14% red -- and an almost-empty panel under a header that says
    # "over-counted" reads as a mistake unless the figure says the number.
    CAP = 0.36
    LEG = 0.26
    #: TWO gaps, not one: there is a seam between the rows AND a seam above the key.
    #: With a single GAP in this sum the key began at the exact inch the lower row's
    #: caption ended, and the row's bold identity line printed into the swatches.
    #: THE BAR PANEL IS THE PLATE'S CONCLUSION, so it is drawn at the size of one.
    #: At 1.05 in tall and 3.10 wide it sat in the bottom-left corner of a sheet
    #: that had three blank inches under it, and read as an afterthought beside
    #: the eight micrographs rather than the count they are examples of.
    BARH = 1.95           # the counted-pixel bar panel below the rows
    Htot = Mg + HDR + 2 * (PAN + CAP) + 2 * GAP + BARH + 0.10 + LEG + Mg

    fig = plt.figure(figsize=(W, Htot))
    overflow = []

    def col_x(c, half):
        """Left edge of one panel: error kind `c`, 0 = raw and 1 = overlay."""
        return Mg + LAB + c * (2 * PAN + PAIR + GAP) + half * (PAN + PAIR)

    def ax_at(xin, yin, win, hin):
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    def say(ax, x, y, text, *, size=J.TICK, weight="normal", colour=J.INK, ha="left"):
        """Draw a line of text and REMEMBER IT, so its printed width can be checked.

        A line that runs past its own axes is invisible in the code and obvious in the
        plate -- the first draft of this layout clipped the transmission row's sentence
        at 'the operator judge'. The check runs after the draw, against the renderer, in
        the figure's own inches.
        """
        t = ax.text(x, y, text, fontsize=size, fontweight=weight, ha=ha, va="center",
                    color=colour, transform=ax.transAxes)
        overflow.append((ax, t, text))
        return t

    # Column headers. A second line says what the window IS, so the plate can be read
    # without its caption; both lines sit outside the artwork, which is where the house
    # style puts anything that is not the image.
    #: THE SUB-HEAD NAMES THE COLUMN'S SUBJECT, NOT HOW ITS WINDOW WAS PLACED. It
    #: used to say "window holding the most ...", which was true while every window
    #: came from the search and became false for the electron row the moment one was
    #: chosen by hand. A column heading that describes a placement rule has to be
    #: rewritten every time a window moves; one that describes what the colours mean
    #: does not, and the placement is in the caption and in this figure's record,
    #: per panel, under placed_by.
    heads = (("Over-counted", ""), ("Under-counted", ""))
    for c, (head, sub) in enumerate(heads):
        hx = ax_at(col_x(c, 0), Mg, 2 * PAN + PAIR, HDR)
        hx.set_axis_off()
        say(hx, 0.5, 0.84, head, size=J.BODY, weight="bold", ha="center")
        if sub:
            say(hx, 0.5, 0.52, sub, colour=J.G_DARK, ha="center")
        #: which half is which, said once per pair rather than inside eight panels.
        for half, what in enumerate(("the micrograph", "detector vs operator")):
            hw = ax_at(col_x(c, half), Mg, PAN, HDR)
            hw.set_axis_off()
            say(hw, 0.5, 0.14, what, colour=J.G_MID, ha="center")

    letters = iter("abcdefgh")
    for r, coll in enumerate(("SEM", "TXM")):
        m = meta[coll]
        yrow = Mg + HDR + r * (PAN + CAP + GAP)
        lx = ax_at(Mg, yrow, LAB, PAN)
        lx.set_axis_off()
        lx.text(0.55, 0.5, coll, fontsize=J.BODY, fontweight="bold", rotation=90,
                ha="center", va="center", color=J.INK, transform=lx.transAxes)
        for c, kind in enumerate(("over-counted", "under-counted")):
            p = next(q for q in panels if q["coll"] == coll and q["kind"] == kind)
            for half in (0, 1):
                ax = ax_at(col_x(c, half), yrow, PAN, PAN)
                if half == 0:
                    #: THE RAW HALF IS THE SAME PIXELS AND THE SAME STRETCH as the
                    #: overlay beside it, with nothing drawn on it. Anything else
                    #: would make the pair a comparison of two renderings instead of
                    #: a comparison of a micrograph with what was concluded from it.
                    ax.imshow(p["grey"], cmap="gray", vmin=0, vmax=1,
                              interpolation="bilinear")
                else:
                    ax.imshow(p["grey"], cmap="gray", vmin=0, vmax=1,
                               interpolation="bilinear", zorder=1)
                    for _z, (_m, _c) in enumerate(((p["m_under"], UNDER),
                                                   (p["m_agree"], AGREE),
                                                   (p["m_over"], OVER))):
                        if not _m.any():
                            continue
                        _rgba = np.zeros(_m.shape + (4,), float)
                        _rgba[_m, :3] = np.array(J.rgb(_c))
                        _rgba[_m, 3] = 1.0
                        ax.imshow(_rgba, interpolation="nearest", zorder=2 + _z)
                J.micrograph(ax)
                ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                                       fill=False, edgecolor=J.INK, linewidth=0.7,
                                       zorder=30))
                J.panel_label(ax, next(letters), inside=True)
                if half == 0:
                    scalebar(ax, p["nm"], p["side"], fontsize=J.TICK)
        # WHAT EACH PANEL HOLDS, AND THEN WHAT THE ROW IS. The two rows are scored with
        # two different detectors, so the figure has to say which, beside the specimen it
        # is drawn from and the score that detector earned on this field. Without it a
        # reader attributes the transmission row's agreement to the electron row's rule.
        _span = 4 * PAN + 2 * PAIR + GAP
        cx = ax_at(Mg + LAB, yrow + PAN, _span, CAP)
        cx.set_axis_off()
        step = (2 * PAN + PAIR + GAP) / _span
        for c, kind in enumerate(("over-counted", "under-counted")):
            p = next(q for q in panels if q["coll"] == coll and q["kind"] == kind)
            pct = p["over_pct"] if kind == "over-counted" else p["under_pct"]
            say(cx, c * step, 0.56,
                p["kind_impossible"] or f"{pct:.2f}% of this window is {kind}",
                colour=J.G_DARK)
        #: THE ROW'S SPECIMEN AND DETECTOR COME OFF THE PLATE at the author's
        #: instruction. The rotated SEM / TXM label at the left already says which
        #: microscopy a row is, and which specimen it is drawn from and which
        #: detector marked it are caption facts, not artwork. Both are still in this
        #: figure's record, under rows.<arm>.specimen and rows.<arm>.detector, and
        #: the manuscript caption states them.

    #: WHAT THE WHOLE FRAME COUNTS, not just the two windows above it. The author asked
    #: for the raw image, the coloured overlay and then a bar graph of the three
    #: outcomes, and the three outcomes are already on each arm's record: tp_px is
    #: correctly counted, fp_px over-counted, fn_px under-counted, measured over the
    #: refereed pixels of the whole frame rather than the chosen window. The windows
    #: above are chosen to SHOW each error; this says how much of each there is.
    _bw = 4.30
    bax = ax_at(Mg + LAB + (W - 2 * Mg - LAB - _bw) / 2.0,
                Htot - Mg - LEG - 0.10 - BARH, _bw, BARH)
    _w, _gap = 0.26, 0.10
    _xt, _xl = [], []
    for _i, coll in enumerate(("SEM", "TXM")):
        m = meta[coll]
        tot = max(m["tp_px"] + m["fp_px"] + m["fn_px"], 1)
        vals = [100.0 * m["tp_px"] / tot, 100.0 * m["fp_px"] / tot,
                100.0 * m["fn_px"] / tot]
        base = _i * (3 * _w + _gap + 0.22)
        for _j, (v, col) in enumerate(zip(vals, (AGREE, OVER, UNDER))):
            x = base + _j * _w
            bax.bar(x, v, _w * 0.88, color=col, edgecolor=J.INK, linewidth=0.5,
                    zorder=3)
            bax.text(x, v + 1.2, f"{v:.1f}", ha="center", va="bottom",
                     fontsize=J.TICK, color=J.INK)
        _xt.append(base + _w)
        _xl.append(coll)
    #: THE AXIS ENDS WHERE THE BARS DO. Matplotlib's own margins put half an
    #: inch of empty axis outside the first and last bar on a panel this wide.
    bax.set_xlim(-0.5 * _w - 0.04, _xt[-1] + 1.5 * _w + 0.04)
    bax.minorticks_off()
    bax.set_xticks(_xt)
    bax.set_xticklabels(_xl, fontsize=J.TICK)
    bax.tick_params(axis="x", pad=2.6)
    bax.set_ylim(0, 100)
    bax.set_yticks([0, 25, 50, 75, 100])
    bax.set_yticklabels(["0", "25", "50", "75", "100"], fontsize=J.TICK)
    bax.set_ylabel("% of refereed px", fontsize=J.TICK, labelpad=3.0)
    #: HIDING A SPINE DOES NOT HIDE ITS TICKS. The top and right spines were off
    #: and their tick marks went on printing, as a row of dashes floating above
    #: the bars and another down the right-hand edge of the panel.
    bax.tick_params(axis="both", which="both", length=2.0, width=0.5, pad=1.6,
                    top=False, right=False)
    for _sp in ("top", "right"):
        bax.spines[_sp].set_visible(False)
    for _sp in bax.spines.values():
        _sp.set_linewidth(0.6)
    bax.text(0.0, 1.02, "(i)  the whole frame, counted", transform=bax.transAxes,
             ha="left", va="bottom", fontsize=J.BODY, fontweight="bold", color=J.INK)

    lg = ax_at(Mg, Htot - Mg - LEG, W - 2 * Mg, LEG)
    lg.set_axis_off()
    items = ((AGREE, "marked, operator agrees"), (OVER, "marked, operator says not crack"),
             (UNDER, "operator's crack, not marked"))
    xx = 0.015
    for colour, text in items:
        lg.add_patch(Rectangle((xx, 0.60), 0.016, 0.24, transform=lg.transAxes,
                               facecolor=colour, edgecolor="none", clip_on=False))
        say(lg, xx + 0.024, 0.72, text, colour=J.G_DARK)
        xx += 0.024 + 0.0105 * len(text) + 0.022

    # THE TYPE HAS TO FIT, AND THAT IS MEASURED. Every line drawn through say() is
    # checked against the axes it was placed in, at the renderer's own geometry. A line
    # that overruns is a hard failure: the alternative is a plate that ships with its
    # sentence cut off at the page edge, which this layout did on its first run.
    fig.canvas.draw()
    _boxes = []
    for ax, t, text in overflow:
        bb = t.get_window_extent(fig.canvas.get_renderer())
        ab = ax.get_window_extent()
        _boxes.append((text, bb))
        if bb.x0 < ab.x0 - 1 or bb.x1 > ab.x1 + 1:
            raise SystemExit(
                f"the line {text!r} is {bb.width / fig.dpi:.2f} in wide and its box is "
                f"{ab.width / fig.dpi:.2f} in: it would print past the plate. Shorten it "
                f"or widen the box.")

    # AND IT HAS TO CLEAR THE LINE NEXT TO IT. Staying inside your own axes is not
    # enough when two lines share one: the two per-panel lines are drawn in the same
    # full-width caption strip, one per column, and the first long one printed straight
    # through the second -- "no over-count is possible here: the operator ruled 0 px
    # not-crack on this fiel" overlapping "11.60% of this window is under-counted", on a
    # plate whose only text check reported PASS. The threshold is 1 pt of real overlap
    # in BOTH directions, so lines that merely touch are allowed.
    _tol = fig.dpi / 72.0
    _clash = []
    for i in range(len(_boxes)):
        for k in range(i + 1, len(_boxes)):
            a, b = _boxes[i][1], _boxes[k][1]
            if (min(a.x1, b.x1) - max(a.x0, b.x0) > _tol
                    and min(a.y1, b.y1) - max(a.y0, b.y0) > _tol):
                _clash.append(f"{_boxes[i][0]!r} x {_boxes[k][0]!r}")
    if _clash:
        raise SystemExit(f"{len(_clash)} overlapping line(s) on the plate: "
                         + "; ".join(_clash[:4]))
    print(f"  CONTROL {len(_boxes)} drawn lines, each inside its box and clear of every "
          f"other: PASS")

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "one field of the specimen the author asked for, in each modality, at the "
                "window holding the most over-counted and the most under-counted area",
        "requested_by_author": "choose a different image for those identifications; the "
                               "HIP hydrogen-embrittlement ones are good to demonstrate; "
                               "also show a better TXM where it correctly labels most of "
                               "it",
        "rows": meta,
        "panel_framing": "the FRAME is the best-agreeing eligible frame of the requested "
                         "specimen, which is a flattering rule and is stated as one: "
                         "rows[*].eligible_ranked lists every candidate and its score so "
                         "the choice can be read against the field it was made from. The "
                         "two COLUMNS are the worst window of each error kind inside that "
                         "one frame.",
        "two_detectors": "the rows are scored with DIFFERENT detectors and each row says "
                         "so on the figure. SEM: the multi-scale darkness rule the paper "
                         "evaluates. TXM: the deployed TXM ensemble (17-feature MLP + "
                         "SAM+17 hybrid, mean probability, threshold "
                         f"{meta['TXM']['detector_threshold']}, speck pruning), read from "
                         "the application's own cached prob.npy. Carrying the SEM rule "
                         "onto these transmission frames scores F1 0.02-0.16 on them, "
                         "which is Figure T6's subject and not this plate's. THE TWO "
                         "ROWS ARE NOT ON THE SAME FOOTING: the TXM model was trained on "
                         "every labelled frame with none held out, so the field drawn "
                         "here is in its training set and the TXM row's precision and "
                         "recall are IN-SAMPLE, while the SEM rule fits nothing. See "
                         "rows.*.scoring_footing; the figure says it too.",
        "specimen_scope_departure": "the manuscript reports on specimen series b2 and b3 "
                                    "and the other plates read the _b2b3 records. Neither "
                                    "specimen shown here is in that scope, so this plate "
                                    "reads the full-corpus records. The figure-pack note "
                                    "that 'b2 and b3 are the series whose images are "
                                    "published' no longer describes this plate.",
        "hip_hydrogen_caveat": "THE SEM ROW IS THE HYDROGEN-CHARGED HIP FIELD AND ONE "
                               "OF ITS COLUMNS IS A STATEMENT. HIP_24hr_SE_Side_006 -- "
                               "identified as the hydrogen-charged field by its '24hr' "
                               "token, the same reading the manuscript uses -- carries "
                               "574,137 painted crack pixels and ZERO pixels marked "
                               "not-crack; its mask holds no value but 0 and 1. No "
                               "marked pixel on it can therefore be an over-count. The "
                               "over-counting panel is drawn anyway, placed by "
                               "agreement rather than by an error that is zero "
                               "everywhere, and where the other panels print the share "
                               "of themselves that is their own error kind, that one "
                               "prints why no such share exists. Its precision of 1.0 "
                               "is by construction: see rows.SEM.precision_is_by_"
                               "construction. Earlier editions drew the AMBIENT field "
                               "MAR_Amb_HIP_CBS_0006 instead, which could be scored in "
                               "both directions; the author asked for this specimen. "
                               "Cast_24hr_SE_Side_006 is one-sided in the same way "
                               "(3,709,448 / 0) and MAR_H_HIP_* carry no correction "
                               "mask at all.",
        "window_rule": "the window is "
                       + " / ".join(f"{v:g} on {k}" for k, v in WINDOW_STROKES.items())
                       + " of the frame's own 90th-percentile paint "
                       "strokes across -- per arm, because an operator ruled on 95.1% "
                       "of the transmission frame and 2.47% of the SEM one, so the same "
                       "multiple fills one panel and leaves the other mostly plain "
                       "micrograph -- capped at "
                       f"{MAX_WINDOW_FRAC:g} of the frame's short side, then placed at the "
                       "position holding the most pixels of that panel's error kind, "
                       "found exactly by a box sum over the summed-area table and capped "
                       f"so the error kind is at most {100 * MAX_ERROR_SHARE:.0f}% of the "
                       "window. A fixed field of view in micrometres was the previous "
                       "rule and it does not survive a 6.3x change of pixel size.",
        "unreviewed": "marked pixels nobody adjudicated are left grey and counted "
                      "separately; they are neither an over-count nor an agreement",
        "consumers_that_must_be_updated": {
            "why": "the previous edition chose, per column, the frame of the whole "
                   "collection holding the most pixels of that error kind, and recorded "
                   "`frames.<coll>.<kind>.share_of_collection`. This edition chooses one "
                   "frame per row, of a named specimen, for best agreement, so that "
                   "quantity no longer exists and writing a number under its old name "
                   "would make the sentence that quotes it false. The per-row record is "
                   "under `rows`.",
            "paper/manuscript/build.py": "reads "
                "CNT['frames']['TXM']['over-counted']['share_of_collection'] into "
                "{cnt_txm_over_share} and will now raise KeyError('frames'). "
                "CNT['panels'][*]['over_pct'] -> {cnt_med_over} still resolves.",
            "paper/manuscript/sections/30-results.md": "the figure's caption there "
                "describes the previous edition in detail -- 'each panel comes from the "
                "frame holding the most pixels of its own error kind', 'a 30 micrometre "
                "field', 'the frame shown instead holds {cnt_txm_over_share}% of the "
                "collection's over-counted pixels in 13 separate components' -- and none "
                "of that describes this plate.",
            "paper/figures/mk_paper_pdf.py": "its bullet for this plate says the columns "
                "are 'each found by exact box sum', which is still true, but not that "
                "the two rows run different detectors.",
        },
        "panels": [{k: v for k, v in p.items() if k not in ("rgb", "grey", "m_under", "m_agree", "m_over")}
                   for p in panels],
        "mad_k": OV.MADK,
        "sources": {"scores": os.path.basename(SCORES),
                    "traces": os.path.basename(TRACES),
                    "legibility": os.path.basename(LEGIB)},
    }, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)
    for coll, m in meta.items():
        print(f"  {coll:<4} {m['frame'][:50]:<52} {m['detector'][:34]:<36} "
              f"P {m['precision']:.4f}  R {m['recall']:.4f}  "
              f"over {m['fp_px']:>9,} px  under {m['fn_px']:>9,} px")


if __name__ == "__main__":
    main()
