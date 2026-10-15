# The metric figures

Four plates about **how this project's numbers are read**, rather than about what the
detector sees. They exist because a week of measurement found that the reporting rule
moves the headline further than any model change ever has.

    <sem-crack-detector>/.venv/bin/python -B measure_metrics.py   # ~70 s -> metric_figures.json
    python -B mk_metric_figures.py                                # -> four PNGs + captions

| file | plate |
|---|---|
| `fig_aggregation.png` | One set of masks, six ways of reporting it |
| `fig_ceiling.png` | What a PERFECT answer scores, and why IoU cannot reach 0.8 here |
| `fig_gameability.png` | Which metrics can be bought by simply drawing fatter |
| `fig_operating_curve.png` | Where the shipped operating point sits on the detector's own two knobs |

`measure_metrics.py` measures; `mk_metric_figures.py` draws and computes nothing. Every
number in a caption is resolved from `metric_figures.json`, so a caption cannot drift
from its plate, and `<name>.caption.json` beside each PNG is greppable data rather than
pixels. The plates are byte-identical on a re-run and are **pure greyscale** — max RGB
channel spread 0 across all four — so no series is identified by colour alone; each is
separated by lightness, dash pattern and marker together.

**The type-size guard runs before `savefig`, not after.** A plate in this project once
shipped with 2.3 pt type. `check()` refuses anything under 7 pt and writes nothing when
it fires; verified by setting the small-type size to 2.3 and confirming the PNG on disk
was unchanged.

## What is measured, and what the plates say

* **The aggregation.** The shipped v1.49.1 candidate stage (region classifier off,
  7-scale union, mad_k 5.0, absolute_dark 10) on the 26 hand-labelled 512 px tiles from
  13 specimens, scored six ways. IoU reads 0.3344 to 0.5329 and recall 0.6255 to 0.9200
  across the six; the IoU span of 0.1985 is **larger than the +0.1753 paired median IoU**
  that switching the region classifier off bought, which is the largest gain any model
  change has made here.
* **The ceiling.** A trace of width 1, 3, ... 41 px laid down the skeleton of the human's
  own paint. Pooled IoU peaks at **0.4993 at 11 px**; as the median over tiles the
  ceiling is **0.5498 at 7 px**. The two must never be crossed: the detector is 67% of
  the pooled ceiling and 76% of the tile-median one, and the "84% of what is achievable"
  figure in circulation divides a tile median by a pooled ceiling.
* **Width gameability.** Growth at a continuous radius (bisected onto the requested area
  ratio, not whole dilation steps, which overshoot 1.5x by ~16%). At 1.5x area, paired
  over the 13 specimens: clDice **+0.0189, 12 up / 1 down, p = 0.0005**; skeleton-F1 at
  2 px **−0.0018, 5 up / 8 down, p = 0.2439**; IoU **−0.0226, 5 up / 8 down, p = 0.7354**
  — while the *tile median* IoU rises 0.4189 -> 0.5044. IoU is gameable in one reading and
  not in the other, which is the first plate's point again.
* **The operating curve.** The whole detector re-run at 15 values of mad_k and 10 of
  absolute_dark_thresh. The no-information floor drawn in is what a mask of the same
  per-tile area scores with its pixels scattered at random (0.0242 at the shipped area;
  0.0297, the crack prevalence, for a mask covering everything). One tile — an
  off-specimen void — moves pooled precision about 0.37, further than either knob does.

## Controls

`measure_metrics.py` refuses to write anything until six controls pass, and each was
**verified by breaking it on purpose** (see the scratch harness described in the git
message, not shipped here):

| control | broken by | caught |
|---|---|---|
| tilebench oracle / empty / mark-everything | dropping 1% of true positives in `TB.counts` | yes |
| the cached 7-scale union equals the shipped `segment_dark_regions` on all 26 tiles | removing the sigma=5 rung | yes |
| local `clean()` equals `detect_cracks.clean_mask` on all 26 tiles | removing the hole fill | yes |
| a 1 px trace lies inside the label *and* is one pixel wide | returning a 5 px trace from `skeletonize` | yes |
| growing to 1.0x returns the mask unchanged | always adding one dilation step | yes |
| growing to 1.5x lands within 5% and is a superset | eroding instead of growing | yes |

Two of these did not catch their break on the first attempt and were rewritten. The
`clean()` control compared one tile, and hole-filling changes only 5 of the 26, so it was
passing vacuously; it now runs on every tile and prints how many it actually exercises.
The trace control asserted only that the skeleton lies inside the label, which a skeleton
dilated twice also does, because the paint is tens of pixels across; it now also counts
filled 2x2 blocks, which a thin skeleton cannot have.

## Provenance: is this what the application emits?

Not exactly, and `measure_metrics.py` measures the gap rather than assuming it away. The
plates score the **candidate stage**. The application runs `unified_pipeline` through
`analysis/detect_one.py`, which also runs a pass-2 interior-candidate step and keeps those
regions too once the classifier is off. Over the 26 tiles the application emits a strict
superset: **17,948 px more** than is scored here, 5.9% of the 303,159 px scored, 15 of 26
tiles affected, **100% of it pass-2 interior candidates**, and 0 px that the plates score and the
application does not. Scored through the same instrument that moves the headline by less
than the aggregation does: pooled precision 0.4181 -> 0.4094, recall 0.6255 -> 0.6487,
IoU 0.3344 -> 0.3351. The record's claim that the scored masks match the application
"to within 242 px over 26 tiles" is not this measurement — 242 px is the 4- versus
8-connected spelling of the 40 px component filter, a separate and much smaller
discrepancy.

## Inventory of every other figure in this repository

Taken 2026-10-13.

**Committed images with no live generator (4).** `disagreement_tiles.png`,
`ground_truth_tiles_sheet.png` and `tile_size_comparison.png` sit at the repository root
and **no file in the repository so much as names them** — not a script, not a README, not
a test. They were committed on 2026-10-09 and 2026-10-11 and cannot be regenerated or
checked. `packaging/appicon.svg` is an asset, not a figure.

**The paper plates (6).** `paper/figures/mk_fig1.py`, `mk_fig2.py`, `mk_compare.py`,
`mk_transfer.py`, `mk_txm.py`, `mk_recover.py`.

CORRECTED 2026-10-14: this list said `mk_spec.py`, which no longer exists. Figure 6 drew
what the region classifier REJECTS, and v1.49.2 rejects nothing, so the plate had no
subject; `mk_recover.py` replaced it with what deleting the classifier RECOVERS. A reader
following this list would have run a script that is not there.

STALENESS RE-CHECKED 2026-10-14 by regenerating rather than by reading timestamps: all
four plates in `paper/figures/out/` and all four metric figures in `docs/figures/` come
back **byte-identical**, so they are current. The check is worth describing because the
first pass gave a FALSE PASS: `mk_spec.py` failed to run (it is deleted), nothing rewrote
Figure 6, and comparing the file with itself reported "SAME". A regeneration check must
confirm the generator actually ran.

* Their `.npy` caches date from 2026-10-02 and 2026-10-06. Every detector change this
  project shipped — the 7-scale union, the region classifier switched off — landed on
  2026-10-12. So the caches, and therefore plates 1, 2, 5 and 6, show a detector the
  application no longer runs.
* On plate 1's own frame, `MAR_H_AS_CBS_0004`, the caption says *"2.44% dark → 664
  components → 453 candidates"* and *"Pass 1 accepted, frame-wide 245 of 453 regions,
  2.32% of frame"*. Re-measured here under v1.49.1: **3.54% dark, 3,110 components, 1,347
  candidates, and all 1,347 accepted at 3.54% of frame**, because there is no classifier
  left to reject any of them. Candidates 3.0x, accepted regions 5.5x, accepted area 1.5x.
  (The 664-versus-646 component count is only 4- versus 8-connected labelling.)
* **Five of the six captions never say which detector they drew.** The *source* docstrings
  of `sem_fullframe.py`, `sem_ladder.py` and `mk_spec.py` do disclose it and point at
  `analysis/detector_overrides.py` — but a source scan is not what the reader sees, and
  only `6 - SEM, where the model differs.caption.json` carries the words "v1.49" into the
  caption itself.
* `mkpdf.py` reads `../sections/*.md`. **`paper/sections/` does not exist**, so stage 3 of
  the documented chain cannot run at all in this checkout, and the one check that would
  catch a figure with sub-6 pt type or an unresolved caption template never executes.
* `mk_compare.py` scores on **15 leak-gated 1024 px tiles from 9 frames** under
  leave-one-frame-out. That is a second instrument beside `analysis/research/tilebench.py`
  and its numbers (a 3 px trace at IoU 0.166) are not comparable to this directory's
  (the same trace, pooled over the 26 tiles, is 0.2490). Neither is wrong; they must never
  appear in one sentence.

### Addendum 2026-10-13, later the same day: plate 6 rebuilt

Scoped to plate 6 only; every other statement in the snapshot above stands as taken.

`mk_spec.py` is **deleted**, so the two references to it above now name a file that no
longer exists. Its figure asked what the SEM region classifier REJECTS, and with
`USE_REGION_CLASSIFIER = False` nothing is rejected — the subject was gone, not the
wording. `paper/figures/mk_recover.py`, over the new stage runner `sem_deadzone.py`, draws
the result that superseded it: the three ETD specimens that scored recall 0.0000 at every
candidate setting ever tried were never invisible, the candidate stage had proposed their
cracks all along and the classifier was rejecting them. The plate is
`6 - SEM, what deleting the region classifier recovers.png`, and `mkpdf.py`'s `FIGFILE[6]`
points at it.

Two things the rebuild established that bear on the snapshot's other bullets:

* **The project's published recovery numbers are not production's.** `+0.1753 median IoU,
  11 of 13, p = 0.0061` and the recalls `0.3792 / 0.3537 / 0.6827` in
  `analysis/detector_overrides.py` reproduce to four decimals as the SINGLE-RADIUS
  ablation — arm A's own candidates with the classifier bypassed — not as v1.49.2. They
  sit in the paragraph that introduces the shipped change and read as though they describe
  it. Production is larger: `+0.2296, p = 0.0024`, recalls `0.4252 / 0.4009 / 0.8086`.
  `sem_deadzone.py` asserts all four against the ablation arm so the attribution cannot
  rot. Both arms are honest; they are different objects and must not be swapped.
* **`tilebench.SHIPPED_V1491['pooled']` does not re-measure exactly.** Re-running the same
  settings through the same harness gives precision 0.4147 / recall 0.6321 / IoU 0.3341
  against the committed 0.4182 / 0.6252 / 0.3344. IoU agrees to 0.0003; precision and
  recall do not. Unexplained, recorded in `sem_deadzone.json`, and no figure quotes the
  committed row — plate 6's numbers are all the re-measurement.

Stage 3 is still unrunnable here, now for two independent reasons: `paper/sections/` does
not exist, and `reportlab` is not installed under either interpreter on this machine. So
plate 6's type size and caption templates were checked by computing `mkpdf.py`'s own two
gates by hand (8.79 pt against a 6.0 pt floor; no unresolved `{...}`), not by a build.
