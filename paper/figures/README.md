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
| `sem_fullframe.py` | `sem_*.npy`, `sem_stats.json` | `sem-crack-detector` |
| `sem_specificity.py` | `spec_*.npy`, `sem_specificity.json` | `sem-crack-detector` |
| `txm_full.py` | `txm_*.npy`, `txm_stats.json` | `TXM_Crack_Detection_Pipeline` |
| `transfer_imranlabs.py` | `imranlabs_eval.json` | the 15 benchmark tiles in `sem-crack-detector`, plus a downloaded checkpoint |
| `transfer_microsam.py <ckpt>` | `microsam_eval.json` (`vit_b`), `microsam_em_organelles_eval.json` (`vit_b_em_organelles`) | the same 15 tiles |
| `transfer_bench.py` | `transfer_bench.json` | the three JSONs above |
| `sem_ladder.py` | `lad_*.npy` | `sem-crack-detector` |
| `sem_full.py`, `sem_stages.py` | earlier previews, not used by the shipped figures | |

**(2) Draw each figure.** Each writes a PNG *and* a `<figure>.caption.json` beside it, with
every number resolved in the scope that computed it. The caption is data, not pixels, so it
can be grepped and checked against the body text.

| script | figure |
|---|---|
| `mk_fig1.py` | 1 — what each filter and model stage does |
| `mk_fig2.py` | 2 — what the two models are made of |
| `mk_compare.py` | 3 — eleven methods on identical data |
| `mk_transfer.py` | 4 — transfer, the class list does not say |
| `mk_txm.py` | 5 — TXM, what each stage adds |
| `mk_spec.py` | 6 — SEM, where the model differs |

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
`sem_specificity.json`, the two TXM audit files, and the four §4.8 transfer files. They are
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
