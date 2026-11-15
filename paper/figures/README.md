# Figure and PDF generators

Section 7.9 of the paper stated that no generator for its figures was checked into any of
the three repositories. This directory closes that: the full source chain is here, and it
reproduces all six figures byte-for-byte.

Nothing here contains an absolute path. Every location the scripts need is an environment
variable with a default that assumes the three repositories sit as siblings; see
`_paths.py`. To build against a cache and an output directory of your own:

    FIG_CACHE=/path/to/npy-cache \
    FIG_DIR=/path/to/figure-output \
    PAPER_DIR=/path/to/paper \
        python mk_fig1.py && python mkpdf.py

## 2026-11-14: the region classifier is ON

`analysis/detector_overrides.py` now sets `USE_REGION_CLASSIFIER = True`, by the author's
decision. **Everything below this section that says the classifier is off describes the
previous configuration.** Those passages are kept rather than rewritten, because the
evidence that justified switching it off is still true and a setting whose
counter-evidence has been deleted cannot be reviewed. What changed is the decision, not
the measurements that argued against it.

Three things follow, and no figure is correct until all three are respected.

**1. The SEM arm is a trained detector now.** The candidate stage is still a rule with no
fitted parameters, but the mask is no longer the candidate stage: an eight-feature
logistic model scores every surviving region and the app keeps the ones it calls crack.
Any plate or caption calling the SEM arm "a threshold rule, nothing trained" is wrong.
`mk_flow.py` branches on the live flag for exactly this reason.

**2. It is a trade, not an upgrade.** On the 25 hand-labelled tiles that exclude the
off-specimen flood tile, precision rises 0.784 → 0.860 while recall falls 0.625 → 0.434,
IoU 0.533 → 0.405 and F1 0.695 → 0.577. On 4 of the 26 tiles the classifier returns an
empty mask for a tile that contains real crack. A figure that shows only the precision is
a sales pitch.

**3. Every score on this corpus is in-sample — and it was measured how much that is
worth.** The bundle records the 45 images it was fitted on, and 45 of the 48 hand-painted
SEM frames here are those images. `analysis/research/improve/sem_classifier_lofo.py`
refits the deployed recipe without each frame in turn (two controls: the CSV is within
0.07% of the bundle's corpus, and refitting on all of today's rows lands within 0.037 of
the shipped coefficients). `sem_deadzone.py` does the same per parent micrograph on the
26 tiles, as arm `shipped_lofo`.

The answer is that the leakage is small: 0.006 in precision and 0.002 in F1 over the 18
scorable frames, and 0.004 in pooled precision on the 25 tiles, with 11 of 13 specimens
tied. **This is not evidence that the model generalises well.** At frame scale the model
barely acts at all — `docs/figures/sem_force_keep_share.json` measures 0.13 to 0.23% of
the proposed regions holding 21.6 to 90.3% of the retained area, and any region of 50,000
px is retained whatever the model says. There is little for leakage to inflate. On the
512 px crops the model does most of the deciding, and there the refit still agrees.

What DOES differ by training overlap is how much the classifier helps: with the flood
tile excluded it raises pooled precision 0.806 to 0.955 on the 10 tiles whose parent it
was fitted on, and 0.770 to 0.810 on the 16 it was not. Training overlap is confounded
with specimen family there — every hydrogen-charged field is in the never-trained group —
so that split is "where does it help", not a second leakage estimate. Both groups and the
clean estimate are in `sem_deadzone.json`.

**4. The public Inconel 718 collection was NOT recomputed, and cannot be here.** Every
producer under `analysis/research/improve/` that reads `pub_ebc_download/...` — among
them `madk_above_five.py` and `pixel_accounting.py`, which supply the paper's headline
area agreement and the MAD-multiplier selection — scores that collection at the
candidate stage with the classifier bypassed. The source images were a public download
kept in a session scratchpad and are no longer on this machine, so those numbers cannot
be repeated at the present setting without re-obtaining the collection. The abstract and
Section 2 say so. The direction is known even though the value is not: the classifier
only removes candidate regions, so the retained set with it on is a subset of the set
with it off and the predicted area fraction there can only fall or stay equal.

Records that follow the flag and were recomputed for it:
`parameters_tiles.json`, `parameters_frames.json`, `overlap_means_sem_txm.json` (and its
`_b2b3` scope), `frame_legibility.json` (and its `_b2b3` scope), `sem_deadzone.json`.
`txm_background_units.json` is unchanged on purpose: the SEM region classifier is not
part of the TXM pipeline, which runs a model of its own.

## Which SEM figures draw the app, and which draw the archive

Read this before quoting any SEM panel as "what the detector does", because the two are
no longer the same thing and the plates no longer agree with each other on purpose.

`sem-crack-detector` as published and archived takes the darkness cut at a single
flattening radius (sigma = 40) and then scores every candidate region with a logistic
model at its bundled threshold. **The application runs neither of those any more.**
v1.49.2 unions the darkness cut over seven radii and sets `USE_REGION_CLASSIFIER = False`,
so it keeps every candidate region — deleting the classifier beat keeping it on every
metric with zero free parameters (paired median IoU +0.1753 over 13 specimens, 11 of 13
better, Wilcoxon p = 0.0061), and a retrained version of the same model deletes 72.67% of
hand-painted crack on the 48 full frames.

| plate | which pipeline | why |
|---|---|---|
| **1** — what each stage does | **v1.49.2, the app** | its subject is what the app does to a micrograph, so it has to be the app |
| **2** — what the models are made of | archived, deliberately | its subject IS the region classifier's eight weights; the caption says the verdict is not consulted |
| **6** — what deleting the classifier recovers | v1.49.2, the app | rebuilt, not patched; see below |

Figure 1's SEM arm was rebuilt on 2026-10-13. Its old panels 5 and 6 (`245 of 453 regions
kept`) described a split that does not exist in production and are gone; the single-radius
cut survives as panel 4, as the "before" the seven-radius union in panel 5 is measured
against, and panel 8 is the mask `analysis/detect_one.py` writes — Pass 2 included, which
the candidate stage in panel 6 is not. The predictor it calls is
`analysis/research/improve/angle4_shipped.py`, which binds the real function out of
`detector_overrides.install()` so it cannot drift.

**`sem_stats.json` renamed its stage keys.** `frame_dark_pct`, `frame_components`,
`frame_candidates` and `frame_kept` read as facts about the frame and were quoted as
facts about the detector; they are facts about one retired pipeline. They are now
`published_dark_pct`, `published_components`, `published_candidates` and
`published_kept`, so a generator still asking for an old name fails with a KeyError
rather than drawing the wrong pipeline's number. The production record is
`sem_production.json`. **`sem_stats.json` now has no reader at all.** It was left as
`mk_fig2.py`'s source while that figure still drew the archived classifier as a live
stage; Figure 2's SEM column was then rebuilt against production and its model numbers
moved to `sem_models.json`, so nothing in the chain reads `sem_stats.json` any more. It
is kept as the committed record of the published pipeline, which is what §7.9 and the
`sem_fullframe.py` runner are about, and not because a plate depends on it.

## Figure 6 was rebuilt, not patched

The old Figure 6 (`mk_spec.py`, over `sem_specificity.py`) drew what the SEM region
classifier REJECTS, on the one frame of this corpus where specificity is estimable.
v1.49.2 sets `USE_REGION_CLASSIFIER = False`, so nothing is rejected: that figure had no
subject left and could not be corrected by rewording. `mk_spec.py` is deleted. The
measurement that superseded it is drawn instead, by `mk_recover.py` over
`sem_deadzone.py` — what switching the classifier off RECOVERS, and what it costs.

`sem_specificity.py` and its committed `sem_specificity.json` are kept. The four-family
comparison is a true statement about the archived published pipeline; it is simply no
longer a figure, so the runner moves to the "earlier previews" row above.

**Three arms, because two would confound the answer.** The record's headline numbers are
arm B's, not production's, and this is the thing to get right:

| arm | what it is | median ΔIoU vs A | dead-zone recalls |
|---|---|---|---|
| A | v1.47: one flattening radius, classifier ON | — | 0.0000 / 0.0000 / 0.0000 |
| B | arm A's own candidates, classifier bypassed | +0.1753, p = 0.0061 | 0.3792 / 0.3537 / 0.6827 |
| C | v1.49.2: seven radii, classifier OFF | +0.2296, p = 0.0024 | 0.4252 / 0.4009 / 0.8086 |

`analysis/detector_overrides.py` publishes arm B's four values in the paragraph that
introduces the shipped change, which reads as though they describe production. They do
not — they are the single-radius ablation, which is the right instrument for *the
classifier's own effect* (one variable differs from A) but is not what the app runs.
`sem_deadzone.py` ASSERTS all four against arm B, so the attribution cannot rot silently.

**What the plate draws is the CANDIDATE STAGE, and it says so.** `analysis/detect_one.py`
runs `unified_pipeline.run_unified_pipeline`, which adds Pass 2 (concavity,
bridge-corridor, interior-fill) and, with the classifier off, keeps every Pass-2 row too.
Pass 2 resolves its frame from `ORIGINAL_DIR` and works on a whole micrograph, so it is
not defined on the 512 px crops this figure uses. Pass 2 is additive by construction — it
claims only pixels no Pass-1 candidate owns (`labeled == 0`) and appends its rows — so the
app keeps a strict superset of column C and the panels understate production. The size of
that gap is a committed record, not re-measured here: `docs/CLAIMS.md` D2 gives +17,972 px
losing none, but over 20 tiles not 26 (`find_field_of_view` crops the other six) and with
per-tile IoU moving between −0.191 and +0.073.

**One scorer.** Every arm goes through `analysis/research/tilebench.py` — same 26 tiles,
13 specimens, same exclusion list, zero tolerance. That module's three locations are
hard-coded to one machine, so `_paths.tilebench()` rebinds `SC`, `CACHE` and `UP` to
`TILE_CACHE` / `TILE_LABELS` and leaves its scoring functions untouched. `TILE_LABELS` is
the only path here with no sibling-repo default: the tiles' `*_gated.png` hand labels live
in the desktop app's upload store, outside all three repositories. An already-built
`tilecache/` needs no labels, which is the usual case. The committed `sem_tiles.json` says
WHICH tiles; the pixels are derived and gitignored.

## The chain

    repos ──(1)──> .npy caches + *_stats.json ──(2)──> PNG + .caption.json ──(3)──> PDF

**(1) Re-run the pipelines and cache their intermediates.** The first four import this
project's own shipped stage functions and call them on real frames, at roughly 30 s each.
The two `transfer_*` runners are different in kind: they load third-party checkpoints and
score them on the 15 benchmark tiles, they need `torch` plus `segmentation_models_pytorch`
or `micro_sam`, and they take about 8 minutes (imranlabs) and 10 to 15 minutes (micro-sam,
which is run once per checkpoint). `transfer_imranlabs.py` additionally needs a 293 MB
published checkpoint that is **not** vendored here; run it with no checkpoint present and
it prints the one-line `curl` that fetches it.

| script | writes | reads from |
|---|---|---|
| `sem_production.py` | `semp_*.npy`, `sem_production.json` — **the v1.49.2 production stages**, `run_unified_pipeline` driven as `analysis/detect_one.py` drives it | `sem-crack-detector`, this repo's `analysis/` |
| `sem_rungs.py` | `semr_*.npy`, `sem_rungs.json` — the seven-radius union decomposed by the rung that supplies each pixel, for Figure 1 panel 5 | the same |
| `sem_models.py` | `sem_models.json` — the two SEM bundles read out: coefficients, intercepts, thresholds, the pass-2 rule constants and the four-family CV table. Figure 2's only model source | `sem-crack-detector`'s two `.joblib` bundles |
| `sem_fullframe.py` | `sem_*.npy`, `sem_stats.json` — the ARCHIVED published pipeline, `published_*` keys. Drawn by no current figure; kept as the committed record | `sem-crack-detector` |
| `sem_deadzone.py` | `dz_*.npy`, `sem_deadzone.json` | `sem-crack-detector`, this repo's `analysis/` (see below) |
| `txm_full.py` | `txm_*.npy`, `txm_stats.json` | `TXM_Crack_Detection_Pipeline` |
| `transfer_imranlabs.py` | `imranlabs_eval.json` | the 15 benchmark tiles in `sem-crack-detector`, plus a downloaded checkpoint |
| `transfer_microsam.py <ckpt>` | `microsam_eval.json` (`vit_b`), `microsam_em_organelles_eval.json` (`vit_b_em_organelles`) | the same 15 tiles |
| `transfer_bench.py` | `transfer_bench.json` | the three JSONs above |
| `sem_ladder.py` | `lad_*.npy` — four classifier FAMILIES on one frame. The wrong axis for v1.49.2 and deliberately not rebuilt: see its docstring, and `sem_rungs.py` for the ladder production still has | `sem-crack-detector` |
| `sem_full.py`, `sem_stages.py`, `sem_specificity.py` | earlier previews, not drawn by any current figure | |

**(2) Draw each figure.** Each writes a PNG *and* a `<figure>.caption.json` beside it, with
every number resolved in the scope that computed it. The caption is data, not pixels, so it
can be grepped and checked against the body text.

| script | figure |
|---|---|
| `mk_fig1.py` | 1 — what each filter and model stage does (SEM arm = v1.49.2) |
| `mk_fig2.py` | 2 — what the two models are made of |
| `mk_compare.py` | 3 — eleven methods on identical data |
| `mk_transfer.py` | 4 — transfer, the class list does not say |
| `mk_txm.py` | 5 — TXM, what each stage adds |
| `mk_recover.py` | 6 — SEM, what deleting the region classifier recovers |

Figures are numbered in order of first citation, which is why adding the transfer plate at
§4.8 took slot 4 and pushed the two §6 plates to 5 and 6 rather than being appended. Nothing derives a figure number from
file order or directory listing, but the number is not in one place either. Renumbering means:
the `FIGCAP` and `FIGFILE` keys and the inline-anchor table in `mkpdf.py`; the output path
hardcoded in each generator; any generator docstring that names a figure; the prose
references in `sections/*.md`, **including the plural `Figures N and M` form**, which a pass
matching only `Figure N` will miss; and deleting the plates left behind under their old
names. `mkpdf.py` refuses to build if the emission order and the numbering disagree.

**(3) Typeset.** `mkpdf.py` reads `../sections/*.md` and the caption JSONs and writes the
PDF. It refuses to build if: a caption is missing or holds an unresolved `{...}` template; a
figure's anchor matches no paragraph (so a figure can never silently revert to the back of
the document); any figure's smallest drawn type would land below 6 pt on the page; or any
character would be dropped by the font that draws it.

## What is NOT here

The `.npy` intermediates from step (1) and the rendered PNGs. Both are derived and both are
gitignored, as is the downloaded `imranlabs/` checkpoint. Regenerating them needs the two detection repositories and their
model bundles; steps (2) and (3) will not run until step (1) has been run once.

The small JSON artifacts **are** committed — `sem_stats.json`, `txm_stats.json`,
`sem_deadzone.json`, `sem_specificity.json`, the two TXM audit files, and the four §4.8 transfer files. They are
what the captions quote their numbers from, and keeping them under version control is what
lets a reader check a figure's number without re-running the pipelines. `txm_stats.json`
carries one non-deterministic field, `seconds`, which is wall-clock and is drawn by no
figure; every other value in it reproduces exactly.

A generator that reads a committed JSON resolves it beside itself, not through `FIG_CACHE`.
`FIG_CACHE` is the `.npy` cache and a reader is told above to repoint it; routing the
committed artifacts through it would make them unfindable in a checkout that did.

## Two things worth knowing before editing a figure

**On-page type size is `font_px x (column_pt / image_width_px)`.** Enlarging a generator's
fonts does not make a figure more legible, because it widens the laid-out image by the same
factor. Narrow the image instead — Figure 1 went from 8 panels per row to 4, and Figure 2
from two side-by-side arms to one stacked column, which is what moved them from 2.3 pt to
7-8 pt. `mkpdf.py` enforces the floor and will name the measured size when it fails.

**Text drawn before a downscale arrives smaller than its declared size.** `mk_fig1.py` draws
its legend chips onto a 1,200 px crop that `fit()` then resizes to 312 px; a 24 px font would
land at 6 px. `tag()` scales its font by the same factor the resize divides by.
