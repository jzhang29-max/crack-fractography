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
from scipy.stats import wilcoxon   # noqa: E402

OUT = _paths.FIG_CACHE
t0 = time.time()
tick = lambda m: print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

ARMS = ("v147", "ablation", "v1492")
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
pred = {a: [] for a in ARMS}
for i, t in enumerate(tiles):
    st = CP.stages(t["img8"])                       # computed once, shared by A and B
    pred["v147"].append(CP.probability(st) >= CP.THR)
    pred["ablation"].append(st["labeled"] > 0)      # same candidates, classifier bypassed
    pred["v1492"].append(A4.shipped_clean(t["img8"]))
    tick(f"predicted {i+1}/{len(tiles)} {t['frame']}")

cnt = {a: [TB.counts(p, t["gt"]) for p, t in zip(pred[a], tiles)] for a in ARMS}

# Single-variant evaluate(): fitted and held-out agree by construction, which is the
# statement that no arm has a knob that was chosen on these tiles.
for a in ARMS:
    r = TB.evaluate(a, {a: cnt[a]}, quiet=True)
    assert abs(r["overfit_gap"]) < 1e-12, f"{a} is not parameter-free"

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
PAIRED = {a: paired(a) for a in ("ablation", "v1492")}
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
    v1492="C: what the app runs -- darkness cut unioned over flattening radii "
          "(5,10,20,40,80,160,320) at mad_k 5.0, background for sigma>64 estimated on a "
          "decimated copy, every candidate region kept. Bound out of "
          "detector_overrides.install() by analysis/research/improve/angle4_shipped.py."),
  classifier_threshold=float(CP.THR),
  scorer=dict(module="analysis/research/tilebench.py", n_tiles=len(tiles),
              n_specimens=len(SPECS), excluded=list(TB.DEFAULT_EXCLUDE), tolerance_px=0,
              aggregation="pooled over pixels within the unit named by each key"),
  controls=dict(
    ladder_collapse="PASS: SCALE_LADDER=(40,) reproduces the stock single-radius cut "
                    "exactly; the full ladder is a strict superset",
    tilebench="PASS: oracle 1.0, empty 0.0, mark-everything precision == prevalence",
    parameter_free="PASS: all three arms single-variant, overfit gap 0.0000",
    record_attribution="PASS: the four values detector_overrides.py publishes "
                       "(+0.1753, p 0.0061, recalls 0.3792/0.3537/0.6827) reproduce as "
                       "arm B to 4 dp, NOT as arm C"),
  pooled_26=POOLED26,
  pooled_25_no_flood=dict(flood_tile=TB.FLOODED, **COST),
  paired=PAIRED,
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
