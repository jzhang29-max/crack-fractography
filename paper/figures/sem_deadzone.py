"""Stage 1 for Figure 6: what switching the region classifier OFF recovers, and what it costs.

This replaces `sem_specificity.py`, whose figure asked what the region classifier REJECTS.
v1.49.2 sets `USE_REGION_CLASSIFIER = False`, so nothing is rejected and that question has
no subject. The question that superseded it is the one measured here.

THREE ARMS, BECAUSE TWO WOULD CONFOUND THE ANSWER
  A  v1.47       `crackpipe.predict` -- darkness cut at ONE flattening radius (sigma = 40),
                 then the bundled logistic region classifier at its own threshold 0.5538.
  B  ablation    the SAME candidate stage with the classifier bypassed and every region
                 kept. Exactly one variable differs from A, so A -> B is the classifier's
                 own effect and nothing else's.
  C  v1.49.2     what the application runs: the darkness cut unioned over SEVEN flattening
                 radii (5,10,20,40,80,160,320) at mad_k 5.0, every candidate region kept.
                 The function is bound out of `detector_overrides.install()` on a stand-in
                 module by `angle4_shipped`, so it is the app's own function.

B IS NOT C, AND THE RECORD'S HEADLINE NUMBERS ARE B's. `analysis/detector_overrides.py`
quotes "+0.1753 median IoU, 11 of 13, Wilcoxon p = 0.0061" and the dead-zone recalls
"MAR_Amb_AS 0.3792, MAR_Amb_Cast 0.3537, MAR_Amb_HIP 0.6827" in the paragraph that
introduces the shipped change, which reads as though they describe production. They do
not: they reproduce here to four decimals as arm B, the single-radius ablation. Production
is arm C, and it is a different and larger number (+0.2296, p = 0.0024, recalls 0.4252 /
0.4009 / 0.8086). Both are true; they are not interchangeable, and the plate labels every
panel with the arm it came from. This runner ASSERTS the four arm-B values so that the
attribution cannot rot silently.

ONE SCORER. All three arms go through `analysis/research/tilebench.py`: same 26 tiles,
same 13 specimens, same exclusion list (MAR_AmbB_AS, 87 % of whose paint is round), same
zero-pixel tolerance. Two scorers would make the comparison unreadable -- a different
exclusion or pooling rule moves these numbers by more than the treatment does.

WHAT IS DRAWN IS THE CANDIDATE STAGE, NOT THE APP'S EMITTED MASK. `detect_one.py` calls
`unified_pipeline.run_unified_pipeline`, which also runs PASS 2 (concavity,
bridge-corridor, interior-fill) and, with the classifier off, keeps every row of `df`
including the Pass-2 rows. Pass 2 resolves its input frame from ORIGINAL_DIR by name and
operates on the whole micrograph; it is not defined on a 512 px crop cut out of one. So
every arm-C mask in this record is the CANDIDATE STAGE of v1.49.2, the caption says so in
those words, and nothing here may be labelled "what the app emits". Pass 2 is ADDITIVE BY
CONSTRUCTION -- it claims only pixels no Pass-1 candidate owns (`claimable = mask_bool &
(labeled == 0) & ~protected`) and appends its rows -- so with the classifier off the
emitted mask is a strict superset of arm C and arm C understates production. The SIZE of
that gap is a committed record, not re-measured here: docs/CLAIMS.md D2 gives +17,972 px
losing none, but over 20 tiles not 26 (the pipeline's own find_field_of_view crops the
other six) and with per-tile IoU moving between -0.191 and +0.073, so Pass 2 is not
uniformly favourable to the score. Quote it with those two caveats or not at all.

CONTROLS THAT RUN BEFORE ANY NUMBER IS WRITTEN
  * `angle4_shipped.selfcheck` -- collapsing SCALE_LADDER to (40,) must reproduce the stock
    single-radius cut bit for bit, and the full ladder must be a strict superset of it.
  * `tilebench.controls` -- a perfect predictor must score 1.0, an empty one 0.0, and
    mark-everything must score precision == prevalence.
  * both treatment arms are single-variant, so leave-one-specimen-out equals fitted and
    the overfit gap must be exactly 0; there is no parameter here to have chosen.
Any of these failing raises, because a number from a broken harness is unreadable.

Writes `sem_deadzone.json` (committed; the plate maker draws from it and computes nothing)
and `dz_*.npy` (the three dead-zone tiles' pixels, derived, gitignored).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import json, time
import numpy as np

TB = _paths.tilebench()
import angle4_shipped as A4        # noqa: E402  (on sys.path via _paths.tilebench)
import crackpipe as CP             # noqa: E402
import both_modalities as BM       # noqa: E402  (the one staging copy of the emission)
import detect_cracks as D          # noqa: E402
import detector_overrides as DO    # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "analysis", "research", "improve"))
import pandas as pd                # noqa: E402
from skimage import measure as skm  # noqa: E402
import sem_classifier_lofo as LF   # noqa: E402  (the one copy of the training recipe)
from scipy.stats import wilcoxon   # noqa: E402

OUT = _paths.FIG_CACHE
t0 = time.time()
tick = lambda m: print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

ARMS = ("v147", "ablation", "v1492", "v1492_floor", "shipped", "shipped_lofo")
# The three ETD specimens that scored recall 0.0000 at every candidate setting ever tried.
# Named here because the figure is about them; every recall is MEASURED below and the
# script raises if any of the three is not in fact at zero under v1.47.
DEAD = ("MAR_Amb_AS", "MAR_Amb_Cast", "MAR_Amb_HIP")

if not os.path.isdir(_paths.TILE_CACHE) or not os.listdir(_paths.TILE_CACHE):
    TB.build_cache()
tiles = TB.load()
SPECS = sorted({t["specimen"] for t in tiles})
tick(f"{len(tiles)} tiles, {len(SPECS)} specimens")

A4.selfcheck([t["img8"] for t in tiles[:3]])
assert TB.controls(), "tilebench controls failed; every number below would be unreadable"
tick("controls pass")

# ---------------------------------------------------------------- the three arms
# ------------------------------------------------- who has already seen these tiles
#: THE CLASSIFIER WAS FITTED ON SOME OF THESE SPECIMENS' OWN REGIONS. 9 of the 22 parent
#: micrographs this tile set is cropped from are in the bundle's training image list;
#: 13, among them every hydrogen-charged MAR_H_* field, are not. So the tile corpus
#: carries a natural held-out group, and arm E can be split by it without refitting
#: anything. Arm F refits as well, for the 9 that need it, so that every tile in the
#: pooled row is out of sample.
_CSV = pd.read_csv(LF.CSV)
_CSV = _CSV[_CSV["SourceImage"].isin(LF.TRAIN_IMAGES)].reset_index(drop=True)
_X, _Y = _CSV[LF.FEATURES].values, _CSV["IsCrack"].astype(bool).values
_SRC = _CSV["SourceImage"].values
IN_TRAIN = {t["frame"]: (t["parent"] in set(LF.TRAIN_IMAGES)) for t in tiles}
tick(f"{sum(IN_TRAIN.values())} of {len(tiles)} tiles are cropped from a micrograph the "
     f"classifier was fitted on")

_FOLD = {}


def _fold_bundle(parent):
    """A bundle refitted without `parent`'s rows, cached per parent across its tiles."""
    if parent not in _FOLD:
        keep = _SRC != parent
        assert keep.sum() < len(_CSV), f"{parent} contributes no rows to drop"
        sc, clf = LF.fit(_X[keep], _Y[keep], LF.weights(_SRC[keep]))
        _FOLD[parent] = LF.dump(sc, clf, LF.THR,
                                os.path.join(OUT, f"dz_fold_{abs(hash(parent))%10**8}.joblib"))
    return _FOLD[parent]


def _emit_with(cleaned, img8, model_path):
    """`both_modalities.emit`, but classifying with a named bundle instead of the
    deployed one. The emission itself is still not transcribed: only the model file
    changes, so arm F differs from arm E in the fold and in nothing else."""
    flat = D.flatten_background(img8)
    lab = skm.label(cleaned, connectivity=2)
    if not lab.max():
        return np.zeros_like(cleaned, bool)
    ves = D.compute_vesselness(flat)
    labeled, df = D.region_features_from_labeled(lab, flat, ves,
                                                 min_area_px=BM.MIN_AREA_PX)
    if not len(df):
        return np.zeros_like(cleaned, bool)
    sc = D.classify_with_model(df, model_path, proba_threshold=None)
    keep = sc.loc[sc["IsCrack"] == True, "Label"].tolist()          # noqa: E712
    return np.isin(labeled, keep) if keep else np.zeros_like(cleaned, bool)


def _emit(cleaned, img8, on):
    """`both_modalities.emit` at a chosen setting of the flag, restored afterwards.

    The emission is not transcribed here. Arms D and E differ from each other in the flag
    and in nothing else, which is the whole point of having both.
    """
    was = DO.USE_REGION_CLASSIFIER
    DO.USE_REGION_CLASSIFIER = on
    try:
        return BM.emit(cleaned, D.flatten_background(img8), img8)
    finally:
        DO.USE_REGION_CLASSIFIER = was


pred = {a: [] for a in ARMS}
for i, t in enumerate(tiles):
    st = CP.stages(t["img8"])                       # computed once, shared by A and B
    pred["v147"].append(CP.probability(st) >= CP.THR)
    pred["ablation"].append(st["labeled"] > 0)      # same candidates, classifier bypassed
    cleaned = A4.shipped_clean(t["img8"])
    pred["v1492"].append(cleaned)
    #: arm C is the CLEANED cut and stops there. The application does two more things to
    #: it: a 40 px component floor, and -- now that the flag is set -- the region
    #: classifier. Collapsing both into one arm would make the classifier's own effect
    #: unreadable, so they are separated: C -> D is the floor, D -> E is the classifier.
    pred["v1492_floor"].append(_emit(cleaned, t["img8"], False))
    pred["shipped"].append(_emit(cleaned, t["img8"], True))
    #: arm F: out of sample for every tile. Where the parent is not in the bundle's
    #: image list the deployed model has never seen it and arm E already is out of
    #: sample, so the two agree there by construction and only the other 9 refit.
    pred["shipped_lofo"].append(
        _emit_with(cleaned, t["img8"], _fold_bundle(t["parent"]))
        if IN_TRAIN[t["frame"]] else pred["shipped"][-1])
    tick(f"predicted {i+1}/{len(tiles)} {t['frame']}")

cnt = {a: [TB.counts(p, t["gt"]) for p, t in zip(pred[a], tiles)] for a in ARMS}

# Single-variant evaluate(): fitted and held-out agree by construction, which is the
# statement that no arm has a knob SELECTED ON THESE TILES by this script.
#
# IT IS NOT A STATEMENT THAT ANY ARM IS OUT OF SAMPLE. Arms A, D and E all run a logistic
# region classifier that was fitted on hand-labelled regions from these same specimens,
# so their scores here are in-sample and a zero overfit gap says nothing about that. The
# out-of-sample question is asked, and answered, in
# analysis/research/improve/sem_classifier_lofo.py, which refits the deployed recipe
# without each frame in turn. Quote this record for what the classifier DOES to the
# shipped mask; quote that one for what it is worth on a frame it has not seen.
for a in ARMS:
    r = TB.evaluate(a, {a: cnt[a]}, quiet=True)
    assert abs(r["overfit_gap"]) < 1e-12, f"{a} has a knob selected on these tiles"

per_spec = {a: {s: TB._agg([c for c, t in zip(cnt[a], tiles) if t["specimen"] == s])
                for s in SPECS} for a in ARMS}
POOLED26 = {a: TB._agg(cnt[a]) for a in ARMS}

# ---------------------------------------------------------------- paired, vs v1.47
def paired(a):
    d = np.array([per_spec[a][s]["iou"] - per_spec["v147"][s]["iou"] for s in SPECS])
    W, p = wilcoxon(d)
    return dict(arm=a, baseline="v147", n_specimens=len(SPECS),
                median_delta_iou=float(np.median(d)), n_better=int((d > 0).sum()),
                n_worse=int((d < 0).sum()), n_tied=int((d == 0).sum()),
                wilcoxon_stat=float(W), wilcoxon_p=float(p),
                test="two-sided Wilcoxon signed-rank on the per-specimen IoU difference, "
                     "one pair per specimen, 13 pairs")
PAIRED = {a: paired(a) for a in ("ablation", "v1492", "v1492_floor", "shipped",
                                 "shipped_lofo")}


def paired_vs(a, b):
    """The same test between any two arms, so C -> D -> E can be read with a p-value."""
    d = np.array([per_spec[a][s]["iou"] - per_spec[b][s]["iou"] for s in SPECS])
    if not d.any():
        return dict(arm=a, baseline=b, n_specimens=len(SPECS), median_delta_iou=0.0,
                    n_better=0, n_worse=0, n_tied=len(SPECS), wilcoxon_stat=None,
                    wilcoxon_p=None, test="identical on every specimen; no test run")
    W, p = wilcoxon(d)
    return dict(arm=a, baseline=b, n_specimens=len(SPECS),
                median_delta_iou=float(np.median(d)), n_better=int((d > 0).sum()),
                n_worse=int((d < 0).sum()), n_tied=int((d == 0).sum()),
                wilcoxon_stat=float(W), wilcoxon_p=float(p),
                test="two-sided Wilcoxon signed-rank on the per-specimen IoU difference, "
                     "one pair per specimen, 13 pairs")
for a in PAIRED:
    tick(f"paired {a}: median dIoU {PAIRED[a]['median_delta_iou']:+.4f}, "
         f"{PAIRED[a]['n_better']}/{len(SPECS)} better, p = {PAIRED[a]['wilcoxon_p']:.4f}")

# ---------------------------------------------------------------- the cost
# Precision falls, and a figure that showed only the recovery would be a sales pitch.
# Quote it OFF the flooded tile: MAR_H_HIP_CBS_0002__crop_3122_120 is an off-specimen void
# that owns most of the false positives at every setting, so a pooled precision including
# it describes that one object rather than the change.
keep25 = [i for i, t in enumerate(tiles) if t["frame"] != TB.FLOODED]
assert len(keep25) == len(tiles) - 1, "the flooded tile is not in this tile set"
COST = {a: TB._agg([cnt[a][i] for i in keep25]) for a in ARMS}
tick("precision off the flood tile: " +
     " -> ".join(f"{a} {COST[a]['precision']:.4f}" for a in ARMS))

# ---------------------------------------------------------------- attribution guard
# These four are the values analysis/detector_overrides.py publishes. They are arm B, and
# the point of asserting them is that if a future edit re-points this figure's anchor at
# arm C the mismatch surfaces here rather than in a caption.
for s, want in zip(DEAD, (0.3792, 0.3537, 0.6827)):
    got = per_spec["ablation"][s]["recall"]
    assert abs(got - want) < 5e-5, f"record says {s} ablation recall {want}, measured {got:.4f}"
assert abs(PAIRED["ablation"]["median_delta_iou"] - 0.1753) < 5e-5, \
    f"record says +0.1753, measured {PAIRED['ablation']['median_delta_iou']:+.4f}"
assert abs(PAIRED["ablation"]["wilcoxon_p"] - 0.0061) < 5e-5
tick("record check: the four published values are arm B and reproduce to 4 dp")

# The committed v1.49.1 pooled row, for comparison with arm C measured here.
V1491_RECORD = dict(TB.SHIPPED_V1491["pooled"])

# ---------------------------------------------------------------- the panels
# HOW THE CROPS WERE CHOSEN: they were not chosen. Each of the three dead-zone specimens
# contributes EXACTLY ONE hand-labelled tile to this corpus, so the panel is that tile and
# there is no selection to make or to bias. Asserted, not assumed.
panels = []
for s in DEAD:
    idx = [i for i, t in enumerate(tiles) if t["specimen"] == s]
    assert len(idx) == 1, f"{s} contributes {len(idx)} tiles; the crop is no longer forced"
    i, t = idx[0], tiles[idx[0]]
    assert per_spec["v147"][s]["recall"] == 0.0, \
        f"{s} is not in the dead zone: v1.47 recall {per_spec['v147'][s]['recall']}"
    np.save(os.path.join(OUT, f"dz_{s}_img8.npy"), t["img8"])
    np.save(os.path.join(OUT, f"dz_{s}_gt.npy"), t["gt"])
    for a in ARMS:
        np.save(os.path.join(OUT, f"dz_{s}_{a}.npy"), pred[a][i])
    panels.append(dict(specimen=s, frame=t["frame"], parent=t["parent"], box=t["box"],
                       gt_px=int(t["gt"].sum()),
                       px={a: int(pred[a][i].sum()) for a in ARMS},
                       **{a: per_spec[a][s] for a in ARMS}))

REC = dict(
  generated=time.strftime("%Y-%m-%d"),
  app_version="1.49.2",
  what_is_drawn=("arm C is the v1.49.2 CANDIDATE STAGE, not the mask the application "
                 "emits. detect_one.py runs unified_pipeline.run_unified_pipeline, which "
                 "adds PASS 2 (concavity, bridge-corridor, interior-fill) and with the "
                 "classifier off keeps every Pass-2 row too, so the app's mask is a "
                 "superset of every arm-C mask here. Pass 2 is defined on a whole "
                 "micrograph resolved from ORIGINAL_DIR, not on a 512 px crop."),
  arms=dict(
    v147="A: single flattening radius sigma=40, logistic region classifier at threshold "
         f"{float(CP.THR):.4f} (analysis/research/crackpipe.py)",
    ablation="B: arm A's candidate stage with the classifier bypassed, every region kept. "
             "One variable differs from A. This is the arm whose numbers "
             "analysis/detector_overrides.py publishes.",
    v1492="C: the v1.49.2 CANDIDATE STAGE -- darkness cut unioned over flattening radii "
          "(5,10,20,40,80,160,320) at mad_k 5.0, background for sigma>64 estimated on a "
          "decimated copy, cleaned, and stopping there. Bound out of "
          "detector_overrides.install() by analysis/research/improve/angle4_shipped.py. "
          "This was the whole emission while USE_REGION_CLASSIFIER was False except for "
          "the area floor, which arm D adds.",
    v1492_floor="D: arm C with the 40 px component floor the application applies, "
                "classifier still bypassed. C -> D is the floor's own effect.",
    shipped_lofo="F: arm E with every tile scored out of sample. For the 9 tiles whose "
                 "parent micrograph is in the bundle's training image list the "
                 "classifier is refitted without that micrograph's rows, by the same "
                 "recipe (sem_classifier_lofo.fit); the other 17 are already out of "
                 "sample and are unchanged. E -> F is the leakage, and nothing else.",
    shipped="E: arm D with the region classifier ON, which is what the application emits "
            "today. D -> E is the classifier's own effect, one variable, and it is the "
            "comparison every classifier claim in the paper rests on. Both arms call "
            "both_modalities.emit, so neither is a transcription."),
  classifier_threshold=float(CP.THR),
  scorer=dict(module="analysis/research/tilebench.py", n_tiles=len(tiles),
              n_specimens=len(SPECS), excluded=list(TB.DEFAULT_EXCLUDE), tolerance_px=0,
              aggregation="pooled over pixels within the unit named by each key"),
  controls=dict(
    ladder_collapse="PASS: SCALE_LADDER=(40,) reproduces the stock single-radius cut "
                    "exactly; the full ladder is a strict superset",
    tilebench="PASS: oracle 1.0, empty 0.0, mark-everything precision == prevalence",
    parameter_free=("PASS: every arm is single-variant here, overfit gap 0.0000 -- no "
                    "knob in THIS script was chosen on these tiles. This is NOT a claim "
                    "that any arm is out of sample: arms A, D and E run a classifier "
                    "fitted on these specimens' own regions, and their scores here are "
                    "in-sample. See docs/figures/sem_classifier_lofo.json."),
    leakage=("arms v147, v1492_floor(no) and shipped(yes) use fitted weights; the "
             "classifier's training images overlap this corpus, so read "
             "sem_classifier_lofo.json before quoting arm E as an accuracy"),
    record_attribution="PASS: the four values detector_overrides.py publishes "
                       "(+0.1753, p 0.0061, recalls 0.3792/0.3537/0.6827) reproduce as "
                       "arm B to 4 dp, NOT as arm C"),
  pooled_26=POOLED26,
  pooled_25_no_flood=dict(flood_tile=TB.FLOODED, **COST),
  #: TWO DIFFERENT QUESTIONS, AND THEY MUST NOT BE READ AS ONE. `shipped` against
  #: `shipped_lofo` is the leakage: the same tiles, the same specimens, the model
  #: refitted without the parent micrograph. The split below is NOT that. The 16 tiles
  #: the classifier was never fitted on are also a different specimen population --
  #: every hydrogen-charged MAR_H_* field is in that group and none is in the other --
  #: so training overlap is confounded with specimen family here and this corpus cannot
  #: separate them. Read the split as "where does the classifier help", not as a second
  #: estimate of leakage.
  pooled_by_training_overlap={
    grp: {a: TB._agg([c for c, t in zip(cnt[a], tiles)
                      if IN_TRAIN[t["frame"]] is want]) for a in ARMS}
    for grp, want in (("parent_in_training_set", True),
                      ("parent_never_trained_on", False))},
  #: the flood tile is in the never-trained group and owns most of that group's false
  #: positives, so the split above understates its precision. Both are carried.
  pooled_by_training_overlap_no_flood={
    grp: {a: TB._agg([c for c, t in zip(cnt[a], tiles)
                      if IN_TRAIN[t["frame"]] is want and t["frame"] != TB.FLOODED])
          for a in ARMS}
    for grp, want in (("parent_in_training_set", True),
                      ("parent_never_trained_on", False))},
  the_split_is_confounded=("the 16 never-trained tiles are also the hydrogen-charged "
                           "specimen families; training overlap and specimen family "
                           "cannot be separated on this corpus. The clean leakage "
                           "estimate is shipped vs shipped_lofo, which is "
                           "paired_steps.leakage_in_sample_over_held_out"),
  n_tiles_by_training_overlap=dict(
    parent_in_training_set=sum(1 for t in tiles if IN_TRAIN[t["frame"]]),
    parent_never_trained_on=sum(1 for t in tiles if not IN_TRAIN[t["frame"]]),
    parents_in_training=sorted({t["parent"] for t in tiles if IN_TRAIN[t["frame"]]}),
    parents_never_trained=sorted({t["parent"] for t in tiles
                                  if not IN_TRAIN[t["frame"]]})),
  paired=PAIRED,
  paired_steps=dict(
    floor_over_candidates=paired_vs("v1492_floor", "v1492"),
    classifier_over_floor=paired_vs("shipped", "v1492_floor"),
    leakage_in_sample_over_held_out=paired_vs("shipped", "shipped_lofo")),
  classifier_is_on=bool(DO.USE_REGION_CLASSIFIER),
  what_the_classifier_costs_and_buys=(
    "read arm D against arm E. Every other difference in this record is a candidate-stage "
    "difference. The 26-tile pooled row is dominated by one off-specimen flooded tile; "
    "pooled_25_no_flood is the row to quote for precision."),
  v1491_committed_pooled=dict(
    value=V1491_RECORD,
    note="tilebench.SHIPPED_V1491['pooled'], the committed v1.49.1 row. Arm C measured "
         "here is the same settings and does not reproduce it exactly: IoU agrees to "
         f"{abs(V1491_RECORD['iou'] - POOLED26['v1492']['iou']):.4f} but precision differs "
         f"by {abs(V1491_RECORD['precision'] - POOLED26['v1492']['precision']):.4f} and "
         f"recall by {abs(V1491_RECORD['recall'] - POOLED26['v1492']['recall']):.4f}. No "
         "figure quotes the committed row; every arm-C number in the plate is the one "
         "measured here."),
  per_specimen={s: dict(**{a: per_spec[a][s] for a in ARMS},
                        delta_iou_ablation=float(per_spec["ablation"][s]["iou"]
                                                 - per_spec["v147"][s]["iou"]),
                        delta_iou_v1492=float(per_spec["v1492"][s]["iou"]
                                              - per_spec["v147"][s]["iou"]))
                for s in SPECS},
  dead_zone=panels,
  crop_choice=("Each dead-zone specimen contributes exactly one hand-labelled 512 px tile, "
               "so the panel is that tile and there was no crop to select. Asserted in the "
               "runner, which raises if a specimen ever gains a second tile."),
  seconds=round(time.time() - t0, 1))

json.dump(REC, open(os.path.join(OUT, "sem_deadzone.json"), "w"), indent=1)
print(json.dumps({k: REC[k] for k in
                  ("pooled_26", "pooled_25_no_flood", "paired")}, indent=1))
tick("done")
