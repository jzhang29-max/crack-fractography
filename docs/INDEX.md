# Index

Everything produced for the paper and the analysis, what it says, and how to rebuild it.
Nothing here is hand-maintained data: every figure and every number has a generator, and
the generator is named.

## Read these first

| document | what it is |
|---|---|
| [`../paper/draft.pdf`](../paper/draft.pdf) | **the paper draft.** Built from `paper/sections/*.md` by `paper/make_paper.py` |
| [`PUBLIC_CRACK_DATA_SEARCH.md`](PUBLIC_CRACK_DATA_SEARCH.md) | every public crack dataset checked, used or rejected with a reason, plus the MetalDAM specificity result |
| [`DATASET_RELEASE_SCOPE.md`](DATASET_RELEASE_SCOPE.md) | what a pixel-exact release of this lab's own micrographs would cost, measured from the tiles already traced |
| [`CLAIMS.md`](CLAIMS.md) | every claim this project has made, its status, and what withdrew it |
| [`REPORTING_GUIDE.md`](REPORTING_GUIDE.md) | how a number must be reported here, and the error each rule came from |
| [`PRACTICE_AND_PRIOR_ART.md`](PRACTICE_AND_PRIOR_ART.md) | prior-art checks; every novelty framing tested so far and its outcome |
| [`MAR_H_AS_vs_MAR_H_HIP.md`](MAR_H_AS_vs_MAR_H_HIP.md) | initial conclusions on that specimen comparison, with the confounds that limit it |
| [`CAN_THE_MODEL_BE_IMPROVED.md`](CAN_THE_MODEL_BE_IMPROVED.md) | **yes, by marking less.** The shipped mad_k sits one rung below the optimum; four channels that tried to mark more all failed their decoys; and the missing 42% of labelled crack is the lit fracture surface inside open cracks, brighter than matrix |
| [`RANKING_IS_BUYABLE.md`](RANKING_IS_BUYABLE.md) | the attempt to raise the detector's rank on the public set. It succeeded, by dilation, which detects nothing and costs a 2.54x area-fraction error; also records that the detector ranks fifth of seven on whole fields, not third |

## The paper

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_paper_plates.py     # P1-P5
    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_pipeline_visual.py  # P6
    <sem-crack-detector>/.venv/bin/python -B paper/make_paper.py                  # -> draft.pdf

Prose lives in `paper/sections/*.md`. Numbers are `{placeholders}` resolved from the JSON
below at render time — **the build fails if one cannot be resolved**, so a number cannot go
stale. `[FIGURE name]` on its own line embeds a plate, and a missing plate is an error.

| plate | shows |
|---|---|
| `P1 - public scores` | P/R/F1/IoU against the no-information floors |
| `P2 - operating curve` | the one free constant, whole fields against the crops of them |
| `P3 - width sensitivity` | what IoU costs for getting width wrong with location right |
| `P4 - baselines` | seven classical detectors, tuned identically |
| `P5 - pixel budget` | the confusion matrix as a share of the image, and how wrong the area fraction is |
| `P6 - pipeline in pictures` | **every step as a real image panel**, captured by running the shipped detector on one public field — `paper/figures/mk_pipeline_visual.py` |

The paper now has an **Appendix A** giving the pixel budget for all five SEM sets measured, including the two that are not crack benchmarks, and an **Appendix B** with the pipeline plate.

## Measurement files — the numbers everything else is drawn from

| file | what it holds | generator |
|---|---|---|
| `figures/sem_originals_metrics.json` | **the paper's primary numbers.** P/R/F1/IoU + controls, SEM whole fields | `analysis/research/improve/sem_originals_eval.py` |
| `figures/pixel_accounting.json` | **the primary measurement.** The full confusion matrix as a percentage of pixels for all five SEM sets, plus accuracy, specificity, balanced accuracy and MCC | `analysis/research/improve/pixel_accounting.py` |
| `figures/sem_public_metrics.json` | the same, on the released crops | `analysis/research/improve/sem_public_eval.py` |
| `figures/sem_baselines.json` | seven classical arms on the SEM sets | `analysis/research/improve/sem_extras.py` |
| `figures/sem_width_ceiling.json` | constant-width reconstruction curves, SEM | `analysis/research/improve/sem_extras.py` |
| `figures/metaldam_specificity.json` | what the detector marks on SEM steel with no cracks labelled | `analysis/research/improve/metaldam_specificity.py` |
| `figures/recall_decomposition_inconel.json` | which stage loses which recall, both gates opened to their limits | `analysis/research/improve/recall_decomposition_inconel.py` |
| `figures/recall_fix_attempts.json` | five ways of raising recall, priced in free parameters as well as F1 | `analysis/research/improve/recall_fix_attempts.py` |
| `figures/ridge_grow_controls.json` | the decoys that killed ridge-growing: flipped ridge, another field's ridge, equal-area dilation | `analysis/research/improve/ridge_grow_controls.py` |
| `figures/ridge_vs_dilation_loo.json` | ridge-growing against a plain dilation at matched parameter count | `analysis/research/improve/ridge_vs_dilation_loo.py` |
| `figures/skelf1_ranking.json` | every arm on both sets by pixel F1 and width-blind skeleton F1, carrying the dilation decoy as a control on the metric | `analysis/research/improve/skelf1_ranking.py` |
| `figures/dilation_costs_measurements.json` | what ranking first costs the area fraction and the width | `analysis/research/improve/dilation_costs_measurements.py` |
| `figures/background_counting_table.json` | **the paper's primary table.** Every operating point scored only in measures that count the background: pixel budget, accuracy with the empty-mask baseline, specificity, area agreement | `analysis/research/improve/background_counting_table.py` |
| `figures/arms_background_units.json` | the eight classical arms re-ranked in those units; the detector places first on area agreement | `analysis/research/improve/arms_background_units.py` |
| `figures/width_ceiling_background_units.json` | the constant-width construction re-scored over every pixel: the whole competitive range is 0.71 pp on whole fields | `analysis/research/improve/width_ceiling_background_units.py` |
| `figures/sem_deadzone_background_units.json` | the region-classifier ablation re-run in those units. Its guard asserts the three arms still reproduce the stored IoU record before reporting anything | `paper/figures/sem_deadzone_background_units.py` |
| `figures/lab_scoring_positive_control.json` | whether our own corpus can referee a detector at all: 99.1% of refereed pixels are crack | `analysis/research/improve/lab_scoring_positive_control.py` |
| `figures/lab_madk_sweep.json` | the mad_k sweep on our own 45 frames, recall and precision on separate frame sets | `analysis/research/improve/lab_madk_sweep.py` |
| `figures/madk_above_five.json` | **the mad_k sweep extended above the shipped value.** Every older file stops at 5.0 | `analysis/research/improve/madk_above_five.py` |
| `figures/madk_paired_test.json` | whether mad_k 6.0 beats 5.0 per-image, paired Wilcoxon, on F1 and on area error | `analysis/research/improve/madk_paired_test.py` |
| `figures/arms_pixel_budget.json` | all eight arms as a pixel budget AND as precision/recall/F1/IoU, tuned two ways | `analysis/research/improve/arms_pixel_budget.py` |
| `figures/unproposed_crack_anatomy.json` | what the 42.1% the detector never proposes actually is | `analysis/research/improve/unproposed_crack_anatomy.py` |
| `figures/missed_shell_contrast_raw.json` | the same contrast on raw grey levels, to rule out a flattening artefact | `analysis/research/improve/missed_shell_contrast_raw.py` |
| `figures/texture_channel_test.json`, `figures/texture_prototype.json` | a local-roughness channel for the lit crack interior, and its decoys | `analysis/research/improve/texture_channel_test.py`, `texture_prototype.py` |
| `figures/watershed_to_the_lip.json` | growing the dark core to the crack lip by watershed, and its decoys | `analysis/research/improve/watershed_to_the_lip.py` |
| `figures/lab_madk_sweep.json`, `figures/lab_corpus_channels.json` | the same two questions on this lab's own 48 hand-corrected frames | `analysis/research/improve/lab_madk_sweep.py`, `lab_corpus_channels.py` |
| `figures/metric_figures.json` | the corpus-side measurements, including the width curve on 26 tiles | `figures/measure_metrics.py` |
| `figures/public_metrics.json` | pavement sets. **Measured, then removed from the paper** as the wrong modality | **generator not retained** — written in scratch and pruned. The numbers reproduce `public_benchmarks.json`'s F1 to four decimals, which is the only check on them now |
| `figures/public_benchmarks.json`, `figures/public_baselines.json`, `figures/baselines_full.json`, `figures/width_ceiling.json` | earlier pavement runs, kept as a record | see `PUBLIC_CRACK_DATA_SEARCH.md` |

**One file has no live generator**, which this project's own figures README treats as a
defect: `figures/public_metrics.json` was produced by a script kept in scratch that has
since been pruned. It is pavement data, removed from the paper, and is kept only as a
record; do not build anything new on it.

**One stale number is on disk on purpose.** `figures/public_baselines.json` reports the
detector at 0.8209 on DeepCrack; that run scored the first 120 of 237 images and dropped
k=1.0 from the grid. The full split gives 0.7932. The file is kept because it has been
quoted; it must not be quoted again.

## Other figures and decks

| | |
|---|---|
| `figures/fig_pipeline.png` | the detector end to end; every constant read from `analysis/detector_overrides.py` at draw time — `figures/mk_pipeline.py` |
| `figures/fig_aggregation / ceiling / gameability / operating_curve` | how this project's own numbers are read — `figures/mk_metric_figures.py` |
| `slides/all_figures.pdf` | the slide deck. Content is editable in `slides/slides.json`, then `slides/make_slides.py` |
| `flowchart/pipeline_flow.pdf` | the 13-page pipeline flow — `flowchart/make_flowchart_pdf.py` |
| `paper/figures/out/1,2,3,6 - *.png` | the older paper plates — `paper/figures/mk_fig1.py`, `mk_fig2.py`, `mk_compare.py`, `mk_recover.py` |

## Which interpreter

Anything that imports `detect_cracks` — every measuring script above — needs the SEM
repo's environment, because this app's venv has no pandas or cv2:

    /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python -I <script>

The app's own test suite uses this repo's `.venv`.
