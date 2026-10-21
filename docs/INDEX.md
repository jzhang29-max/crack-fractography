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

## The paper

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_paper_plates.py   # plates
    <sem-crack-detector>/.venv/bin/python -B paper/make_paper.py                # -> draft.pdf

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

## Measurement files — the numbers everything else is drawn from

| file | what it holds | generator |
|---|---|---|
| `figures/sem_originals_metrics.json` | **the paper's primary numbers.** P/R/F1/IoU + controls, SEM whole fields | `analysis/research/improve/sem_originals_eval.py` |
| `figures/pixel_accounting.json` | the full confusion matrix as a percentage of pixels, plus accuracy, specificity, balanced accuracy and MCC | `analysis/research/improve/pixel_accounting.py` |
| `figures/sem_public_metrics.json` | the same, on the released crops | `analysis/research/improve/sem_public_eval.py` |
| `figures/sem_baselines.json` | seven classical arms on the SEM sets | `analysis/research/improve/sem_extras.py` |
| `figures/sem_width_ceiling.json` | constant-width reconstruction curves, SEM | `analysis/research/improve/sem_extras.py` |
| `figures/metaldam_specificity.json` | what the detector marks on SEM steel with no cracks labelled | `analysis/research/improve/metaldam_specificity.py` |
| `figures/metric_figures.json` | the corpus-side measurements, including the width curve on 26 tiles | `figures/measure_metrics.py` |
| `figures/public_metrics.json` | pavement sets. **Measured, then removed from the paper** as the wrong modality | `analysis/research/improve/pub_prfi.py` |
| `figures/public_benchmarks.json`, `figures/public_baselines.json`, `figures/baselines_full.json`, `figures/width_ceiling.json` | earlier pavement runs, kept as a record | see `PUBLIC_CRACK_DATA_SEARCH.md` |

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
