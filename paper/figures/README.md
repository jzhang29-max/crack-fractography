# Figure and PDF generators

Section 7.8 of the paper stated that no generator for its figures was checked into any of
the three repositories. This directory closes that: the full source chain is here, and it
reproduces all five figures byte-for-byte.

Nothing here contains an absolute path. Every location the scripts need is an environment
variable with a default that assumes the three repositories sit as siblings; see
`_paths.py`. To build against a cache and an output directory of your own:

    FIG_CACHE=/path/to/npy-cache \
    FIG_DIR=/path/to/figure-output \
    PAPER_DIR=/path/to/paper \
        python mk_fig1.py && python mkpdf.py

## The chain

    repos ──(1)──> .npy caches + *_stats.json ──(2)──> PNG + .caption.json ──(3)──> PDF

**(1) Re-run the pipelines and cache their intermediates.** These import the shipped stage
functions and call them on real frames; they are the slow step (~30 s each).

| script | writes | reads from |
|---|---|---|
| `sem_fullframe.py` | `sem_*.npy`, `sem_stats.json` | `sem-crack-detector` |
| `sem_specificity.py` | `spec_*.npy`, `sem_specificity.json` | `sem-crack-detector` |
| `txm_full.py` | `txm_*.npy`, `txm_stats.json` | `TXM_Crack_Detection_Pipeline` |
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
| `mk_txm.py` | 4 — TXM, what each stage adds |
| `mk_spec.py` | 5 — SEM, where the model differs |

**(3) Typeset.** `mkpdf.py` reads `../sections/*.md` and the caption JSONs and writes the
PDF. It refuses to build if: a caption is missing or holds an unresolved `{...}` template; a
figure's anchor matches no paragraph (so a figure can never silently revert to the back of
the document); any figure's smallest drawn type would land below 6 pt on the page; or any
character would be dropped by the font that draws it.

## What is NOT here

The ~277 MB of `.npy` intermediates from step (1), and the rendered PNGs. Both are derived
and both are gitignored. Regenerating them needs the two detection repositories and their
model bundles; steps (2) and (3) will not run until step (1) has been run once.

The `*_stats.json` and `sem_specificity.json` files **are** committed. They are small, they
are what the captions quote their numbers from, and keeping them under version control is
what lets a reader check a figure's number without re-running the pipelines.

## Two things worth knowing before editing a figure

**On-page type size is `font_px x (column_pt / image_width_px)`.** Enlarging a generator's
fonts does not make a figure more legible, because it widens the laid-out image by the same
factor. Narrow the image instead — Figure 1 went from 8 panels per row to 4, and Figure 2
from two side-by-side arms to one stacked column, which is what moved them from 2.3 pt to
7-8 pt. `mkpdf.py` enforces the floor and will name the measured size when it fails.

**Text drawn before a downscale arrives smaller than its declared size.** `mk_fig1.py` draws
its legend chips onto a 1,200 px crop that `fit()` then resizes to 312 px; a 24 px font would
land at 6 px. `tag()` scales its font by the same factor the resize divides by.
