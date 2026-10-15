# MAR_H_AS vs MAR_H_HIP — initial conclusions

Written 2026-10-14 against the comparison shown in the app's Groups pane. Every number
below was re-derived through `app/groupstats.py`'s own code path and cross-checked against
the frame table; where this document disagrees with the on-screen table, it says so.

## The short version

**The table is arithmetically correct and the two sides are unusually well matched — and
it still does not support "HIP cracks less than AS".** Three things undercut it, in order
of severity:

1. **The crack-count difference is a detector effect, not a material one.** On the *same
   six physical fields*, recorded simultaneously at byte-identical stage coordinates, the
   CBS channel says HIP has **1.68x** AS's crack count and the ETD channel says **0.81x**.
   Both cannot be a property of the specimen, because the specimen did not change between
   the two channels.
2. **The area-deficit sign is a property of which frames are in the set.** The six frames
   compared are rows 2 and 3 of a 3x3 raster. Restore row 1 and the area-fraction ratio
   moves from **0.645 (HIP 35% lower) to 1.082 (HIP 8% higher)** on CBS, and to **1.512**
   on ETD.
3. **n = 1 specimen and 1 imaged patch per side.** Six frames is six positions on one
   patch, along a stage gradient that is itself significant (Spearman rho +0.867, p=0.0025
   on AS; +0.833, p=0.0053 on HIP). No amount of further imaging *on these patches* can
   narrow a between-specimen claim.

**What does survive:** HIP's cracks are **shorter** in every scope and on both detectors —
the only direction that never reverses. And the two sides are **indistinguishable** in how
concentrated the damage is: `largest_share_of_area` 0.0576 vs 0.0625 (1.08x, ranges
overlapping heavily), so neither is one big crack plus noise.

## What was compared

The groups were **not saved** — `groups.json` is `{}`, and the Groups pane posts an ad-hoc
frame list with a typed-in name. The membership was recovered by searching every subset of
the 20 frames per specimen for one matching the on-screen crack count *and* total crack
area exactly. It is unique:

| | frames |
|---|---|
| MAR_H_AS | `CBS_0004 0005 0006 0007 0008 0009` |
| MAR_H_HIP | `CBS_0004 0005 0006 0007 0008 0009` |

Both sums reconcile to the byte: 3,954,527 px (AS) and 2,550,770 px (HIP).

**Save both groups by name before citing any of this.** As it stands the comparison is not
reproducible from anything on disk.

The matching is the comparison's real strength, and it is unusually good: all 12 frames are
**CBS**, **6144x4096 px**, **51.883 nm/px exactly** (scale spread 1.000), same speck cutoff,
same aspect source, and the two specimens sit at disjoint stage positions. The detector
confound this project has measured elsewhere — CBS reads 2.29x ETD's area fraction on the
same field — is held constant here rather than ignored.

## The table, read

| quantity | AS | HIP | ratio | what it means here |
|---|---|---|---|---|
| Crack count | 1,172 | 1,967 | 1.68x | **reverses on ETD (0.81x)** — do not use |
| Total crack area | 3,954,527 px / 10,645 um^2 | 2,550,770 px / 6,866 um^2 | 0.645x | sign depends on frame selection |
| Crack area fraction | 2.62% | 1.69% | 0.645x | same |
| Average crack area | 3,369 px^2 | 1,369 px^2 | 0.41x | **pooled value is 0.38x** — see below |
| Median crack area | 1,084 px^2 | 490 px^2 | 0.45x | HIP's regions are smaller |
| Average length (all) | 465.4 px | 184.4 px | 0.40x | **the one robust direction** |
| Average length (uncensored) | 449.7 px | 181.2 px | 0.40x | same |
| Average aspect ratio | 5.42 | 4.80 | 0.89x | **not length/width** — see below |
| Largest crack's share of area | 0.0576 | 0.0625 | 1.08x | **no difference** |
| Orientation | 89.75 deg (R 0.681) | 89.58 deg (R 0.689) | 0.17 deg apart | **retired measurand** — see below |

### Why count x mean area does not equal total area

It reconciles, but the table mixes two aggregations: `n_cracks` and `total_area_px` are
sums, `mean_area_px` is the unweighted mean of six per-frame means. With unequal crack
counts per frame those differ. Pooled: **3,374 vs 1,297 px^2, ratio 0.384**. Quote 0.38x,
or quote 0.41x and say it is a mean over frames. (AS is off by 0.17%, HIP by 5.58%.)

### Two rows of this table count different pixels

`total_area_px` is summed from the crack table, which **excludes specks** (regions under the
25 px cutoff never reach it). `area_fraction_pct` is read off the frame record, which
**includes** them. So `total_area_px / (n x W x H)` does not equal `area_fraction_pct`. The
gap is 0.0077% on AS and 0.0085% on HIP — far too small to affect any conclusion, but it is
a real non-identity, and it is why a subset search over the frame record's `crack_area_px`
finds nothing: the AS set is 303 px heavier there than in the crack table.

### The mechanism, where the scope holds

Within these six fields the area deficit is **entirely a length deficit, not a narrowing**.
Pooled over all cracks: mean skeleton length 464.8 vs 169.7 px (**0.365x**), implied mean
width 7.26 vs 7.64 px (**1.052x**). And 0.365 x 1.052 = **0.384** = the pooled area ratio,
to three figures. HIP's cracks are ~2.7x shorter and ~5% *wider*.

HIP's 795 extra regions are predominantly small: regions under 1,000 px^2 are 73% of HIP's
count but only 18.9% of its area, against 47.6% and 5.9% on AS.

## Where it breaks

| scope | n/side | count | area fraction | mean area | mean length |
|---|---|---|---|---|---|
| CBS row 1 (fields 1-3, excluded) | 3 | 1.13 | **1.421** | 1.246 | 0.825 |
| CBS row 2 (4-6) | 3 | 1.52 | 0.580 | 0.394 | 0.398 |
| CBS row 3 (7-9) | 3 | 1.86 | 0.730 | 0.420 | 0.394 |
| **CBS rows 2+3 — the compared set** | **6** | **1.68** | **0.645** | **0.406** | **0.396** |
| CBS all 9 fine fields | 9 | 1.40 | **1.082** | 0.740 | 0.497 |
| ETD, the same 6 fields | 6 | **0.81** | 0.446 | 0.566 | 0.766 |
| ETD all 9 fine fields | 9 | **0.88** | **1.512** | 1.353 | 0.944 |
| everything, 20/side | 20 | 1.17 | 1.189 | 0.886 | 0.622 |

Two independent reversals, both verified from the frame table:

* **Frame selection.** HIP's top raster row carries area fractions 10.78 / 13.41 / 4.54%
  against AS's 5.36 / 5.89 / 8.97%. It was excluded. The same reversal appears with no
  frames removed at all: over all 9 CBS fields the *mean* area fraction says HIP is higher
  (1.082) while the *median field* says HIP is lower (0.581). Two HIP fields decide it.
* **Detector.** CBS 1.13-1.86 across every scope; ETD 0.81-0.94 across every scope.
  Consistent within each channel, opposite between them, on simultaneous acquisitions of
  the same object.

The six chosen fields are also the *homogeneous* part of each raster: the stage gradient on
them alone is not significant (AS rho +0.543, p=0.27; HIP +0.429, p=0.40) where it is
significant on all nine. That is defensible as "the uniform interior fields", but it is a
selection made on a measured quantity and has to be stated with its criterion.

## Two rows that do not mean what they are labelled

Both were defects in the app, not in the data, and both changed how the table reads. Both
are now fixed; the descriptions below are what the table said when the screenshot was taken.

* **`Average aspect ratio` is not length over width.** It is the fitted ellipse's major
  over minor axis, while the row ships with unit `length / width` and the definition
  "length divided by width". On these cracks those differ by an order of magnitude:
  skeleton-length-over-mean-width is **75.8 (AS) and 26.4 (HIP)**, ratio 0.348 — consistent
  with the length finding — against the ellipse's **5.42 and 4.80**, ratio 0.886. The
  ellipse major axis (163 vs 91 px) is 2-3x shorter than the skeleton it appears to
  measure, because these cracks are tortuous and branched. So 0.89x and 0.40x are not in
  conflict; they are different measurands. The definition's "painted crack runs about 3.3"
  benchmark has no stated provenance in the code that ships it.
* **`Orientation` is a measurand this project retired by name.** It is the whole
  component's second-moment major axis, area-weighted. `analysis/segments.py`'s own
  docstring retires exactly that: *"For a branched network that is noise, and for a
  symmetric 4-way junction it is arbitrary"*, and the area weighting *"makes it a
  width-weighted rose"*. The replacement — segment-level `rose_theta_deg` / `rose_R` with a
  per-frame permutation null — **is already stored on all 12 frames and the comparison does
  not read it.** The two disagree by ~90 deg (rose theta is 0.2-8.4 deg; the table says
  89.75 deg) because of an unstated reference axis, so a reader will get the crack direction
  90 deg wrong.

  The retired row also hides a difference the kept one shows. `rose_R` is **0.243-0.411 on
  AS and 0.468-0.548 on HIP — non-overlapping, 6/6, every frame beating its own null**
  (nulls 0.119-0.180). The table's orientation line reads "identical". Treat the rose_R gap
  as a lead, not a result: HIP's cracks are 2.7x shorter, and short segments quantise onto
  the pixel lattice, which `segments.py` documents as a competing explanation.

## Why the table carried no warnings

`compare()["caveats"]` is empty, and the UI suppresses the warning block when it is. Every
trigger misses this configuration:

| trigger | threshold | actual | fires? |
|---|---|---|---|
| scale spread | >= 1.5x | 1.000x | no (correctly) |
| censoring | count-weighted >= 10% | 7.42% / 3.81% | no |
| specimen overlap | a specimen on both sides | disjoint | no |
| pooling | > 1 specimen per side | exactly 1 per side | no |
| small n | n < 3 | n = 6 | no |

**Silence here was coverage, not clearance.** Two gaps mattered, and both are now fixed —
re-running this comparison emits **three** caveats where it emitted none:

1. *"group A is 6 frames of MAR_H_AS; group B is 6 frames of MAR_H_HIP ... that side is n=1
   SPECIMEN however many frames it holds."*
2. *"Censoring is high (7.42% against 3.81% by count, 12.16% against 8.11% of the crack
   AREA) ... Every length here is a lower bound."*
3. *"The two groups are censored by different amounts ... the length ratio below is partly
   that difference, not the material."*

The two gaps were:

* The censoring test **was count-weighted**. By area the same frames are **12.16% (AS) and
  8.11% (HIP)**, and `MAR_H_AS_CBS_0005` alone is 19.94% — over the code's own threshold on
  the weighting the frame records already store and label as the larger one. Every length
  row is a lower bound, and the bound is ~1.5x tighter on HIP than on AS. The caveat now
  tests both weightings and reports both.
* **"6 frames, 1 specimen" fell through both specimen tests** in silence, though the module
  docstring opens by saying frames of one specimen are not independent: one test looks for a
  specimen on *both* sides, the other for *several* pooled on one side, and this design is
  neither. The comparison now names it.

## What can be said today

> On six matched CBS fields of one AS and one HIP specimen, imaged at identical
> magnification, the HIP specimen's crack network is finer: individual cracks are about 2.7x
> shorter and marginally wider, and small regions make up a much larger share of the count.
> Total crack area over these fields is lower in HIP, but that contrast reverses when the
> remaining fields of the same raster are included, and the crack-count contrast reverses
> between the CBS and ETD channels of the same acquisition — so neither is reported as a
> specimen-level difference. Damage concentration is indistinguishable between the two.

Everything stronger needs: more than one specimen per condition, agreement between CBS and
ETD on whichever quantity is being claimed, and a frame set chosen by a stated rule rather
than by position in the raster.

## What changed in the app as a result

Four things this comparison exposed, all shipped with tests that fail against the previous
code:

1. `Average aspect ratio` now carries the unit **`ellipse major / minor`** and a definition
   that says it is not length over width. The unprovenanced "about 3.3" benchmark is gone.
2. A new row, **`Direction strength (segment rose)`**, reads the `rose_R` already stored on
   every frame — the orientation measurand this project endorses, with its permutation null.
   On this pair it reads **0.295 (AS) vs 0.515 (HIP)**, 6 of 6 frames beating their own null
   on each side.
3. The `Orientation` row now discloses in its own note that it is the whole-component
   second-moment axis that `analysis/segments.py` retires, and that its reference axis sits
   ~90 deg from the rose's.
4. Censoring is reported **by area as well as by count**, the caveat fires on either, and a
   lopsided split between the two sides is named.
