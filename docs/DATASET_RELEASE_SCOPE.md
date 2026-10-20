# Scoping a pixel-exact SEM crack dataset release

Written 2026-10-20. Every quantity below is measured from this project's own corpus and
existing hand labels, not estimated from the literature. Where a number rests on an
assumption, the assumption is named.

## Why this is the highest-leverage work left

The paper currently rests on **31 images of one alloy** from one released collection, and
the method ranks third of seven against classical filters on it. More method work does not
fix that. A pixel-exact release of this laboratory's own micrographs would:

* give the paper a second corpus, restoring the two-corpus comparisons §4 and §6 lost;
* make it a dataset contribution, which is a claim no prior-art search has yet taken away —
  unlike the eight method framings this project has already had refuted;
* and fix, for everyone, the thing that makes crack benchmarks unreadable: no public crack
  dataset we have found states **which pixels a human actually adjudicated**.

## What exists today

| | |
|---|---|
| SEM frames | **142**, 14 specimens, 108 of them 6144x4096 (25.2 Mpx) |
| measured crack regions | 34,348 |
| median crack area fraction | 2.82% of frame |
| existing pixel-level tiles | **37** at 512 px, 29 usable, 8.4 regions each |
| existing broad-brush paint | 203 correction files; 91% of 70 M labelled px are broad-brush, median stroke 59 px |

**The existing paint cannot be reused as pixel-exact ground truth.** It is a region
assertion — a 59 px brush saying "crack is somewhere in here" — and that is a different
object from a traced boundary. This work is new tracing, not conversion.

## The effort model, measured

Annotation cost scales with the **boundary** a human has to trace, not with image area or
crack area. Measured on the 29 existing hand-labelled tiles:

| | measured |
|---|---|
| boundary px per 512 px tile | **1,499** (median 1,430) |
| boundary px per Mpx of image | 5,718 |
| boundary / skeleton ratio | **3.03** |

Applying that ratio to the skeleton lengths already measured on all 142 frames:

| | boundary px to trace |
|---|---|
| one whole 25 Mpx frame, median | **93,578** — about **62** of the 512 px tiles already done |
| one whole frame, mean | 265,213 |
| the worst frame | ~4.3 M (46x the median; it holds one very large crack) |
| 10 whole frames | 0.94 M |
| 40 whole frames | 3.74 M |

**Whole-frame pixel-exact annotation is not affordable by hand.** Ten frames is 620
tile-equivalents. If a 512 px tile takes you 10 minutes — you have done 37 of them, so you
can replace that figure with a real one — ten frames is about **103 hours** of tracing.
That is the single most important number in this document and it is the one resting on an
assumption, so calibrate it on three tiles before committing to anything below.

## Three options

### A. Whole frames, pixel-exact — not recommended
10-15 frames, ~100-155 h tracing. Gives the only dataset that can answer "what does the
detector do on a full field", which is the question this project has repeatedly found that
tiles answer wrongly. Too expensive for the return, and a single giant-crack frame can
consume a quarter of the budget.

### B. Large tiles, pixel-exact — the compromise
2048 px tiles, 16x the area of the existing ones, ~24,000 boundary px each (~16
tile-equivalents, ~2.7 h). **40 tiles ≈ 107 h.** 2048 px is the smallest size that can hold
the corpus's wide cracks: tile paint maxes at 43.7 px wide while full frames reach 178 px,
and every rule this project validated on 512 px crops turned out to be a deleter on frames.

### C. Declared windows inside whole frames, pixel-exact — recommended
Trace to pixel precision inside explicitly declared windows, and ship a **reviewed-region
mask** marking everything else as not adjudicated. Three label states per pixel: crack,
not-crack, not-reviewed.

* Cost scales with window area, so it is tunable to whatever time exists.
* It keeps whole-frame context: windows can be placed on wide cracks, thin cracks, junctions
  and clean matrix, rather than wherever a grid happens to cut.
* It is the honest form of what this project already knows: 99.41% of this detector's
  apparent false positives on SEM were never refereed, and precision is therefore a
  bracket [0.29, 0.99] rather than a number. A dataset that states its adjudicated region
  lets anyone compute that bracket instead of guessing.
* **This is the part no public crack dataset we found provides**, and it is a more
  defensible contribution than another 31 images.

Suggested first release under C: **8 frames x 4 windows of 1024 px** = 32 windows,
~8 tile-equivalents each, **~85 h** including QC below.

## Sampling design

Whatever the unit, the selection rule has to be stated in the release or the numbers are
unreadable. This corpus's own failure modes dictate it:

* **Stratify by crack width.** Tiles cannot see wide cracks; a release that samples only
  narrow ones repeats the error. Draw windows across the measured width distribution, and
  publish the distribution.
* **Stratify by detector.** CBS reads about 2.29x the area fraction of ETD on the *same
  field*, and that effect is confounded with specimen here. Include both channels of the
  same field where they exist.
* **At least 2 specimens per condition.** Frames of one specimen are not independent; the
  MAR_H comparison in this project is n=1 vs n=1 dressed as 6 vs 6.
* **Include negative windows.** Regions with no crack at all, declared as adjudicated. Every
  precision number this project has produced is a bracket because these are missing.

## Quality control — not optional

* **Double-annotate 15-20% of windows** by a second person, or by the same person after a
  gap long enough that they do not recall the frame. Publish the inter-annotator IoU.
* That number is the dataset's real ceiling, and without it "pixel-exact" is a claim with
  no evidence. For context, a constant-width redraw of a label's own centreline — zero
  localisation error — scores IoU 0.55-0.59 against that label, so two careful humans will
  not agree at 0.9 and the release should say what they do agree at.
* **Adjudicate disagreements** and record how, rather than averaging them away.

## Release mechanics

* **Per-frame metadata**: nm/px, detector (CBS/ETD/SE/BSE), specimen, condition,
  magnification, accelerating voltage if recoverable. 62 of 142 frames currently have no
  recovered pixel size; those either get one or get excluded, not a default.
* **Licence**: CC BY 4.0 matches the comparable sets. The images are this laboratory's own,
  so the decision is the PI's, not a technical one.
* **Format**: 8-bit PNG images beside 8-bit PNG masks with an explicit value convention,
  documented in the archive. Not a 16-bit TIFF beside an 8-bit mask — that combination
  drove this project's own recall to 0.0012 through nothing but a loading bug.
* **A loader and a scorer** in the archive, so a user does not have to guess the conventions.

## Risks

| risk | mitigation |
|---|---|
| The release is a second corpus from the same lab, same microscope, and does not generalise | state it; it is still the second corpus the field lacks |
| Tracing speed is slower than assumed | calibrate on 3 tiles before committing; cost is linear in boundary px |
| "Pixel-exact" is not achievable on faint AM cracks | this corpus has cracks with d=+0.09 intensity contrast against +1.10 to +2.91 elsewhere; declare them not-reviewed rather than guessing |
| Publishing specimen imagery is not the annotator's call | resolve before any tracing |

## What I need from you to turn this into a plan

1. **Your real tracing time** for one 512 px tile. Everything above scales off it.
2. **Option A, B or C**, and the hours you are willing to spend.
3. **Whether the images can be published at all**, which is a PI decision.
4. Whether a second annotator exists, or whether QC is you twice.
