# The intergranular / transgranular algorithm, step by step

`analysis/crackmode.py`. Written out here because the module docstring explains *why* each
step exists and this explains *what* it does. Every constant named below has its measured
justification on the constant itself in the source.

## Inputs

1. A binary **crack mask** of one field — crack = true. (The app emits crack = black; the
   loader inverts.)
2. A co-registered **grain reference** of the same field, same pixel grid, same size:
   either a grain-ID label image (an EBSD export — preferred, because it has no threshold in
   it) or an RGB IPF/boundary image, whose distinct colours are collapsed to integer IDs.
   Label 0 — or anything passed in `ignore` — is treated as unindexed: a hole in the index is
   missing information, not a grain edge.
3. `nm_per_px`, optional, for reporting in µm.

There is **no mask-only mode**. Both routes from the micrograph alone were built and measured
in this project and both failed; `measure()` raises rather than guess.

## Step 1 — regularise the crack wall

`regularise(mask, r = REGULARISE_PX = 2)`

Morphological closing of the mask with a disc of radius `r`, unioned with the input.

A closing is extensive, so the result **contains** the input and no crack pixel can be lost.
What it can do is bridge two mask fragments within about `r` px of each other; the area added
and the number of components bridged are both returned and recorded in every output. Nothing
downstream re-regularises — `_skeleton_graph` and `flank_geometry` both return the mask they
used, and the flank route reads branch labels and centreline coordinates from the same one.

## Step 2 — skeleton, junction candidates, clusters

`morphology.skeletonize` → a 1-px centreline.

A pixel is a **junction candidate** when at least three of its eight neighbours are also
skeleton. The convolution kernel for that count has a **zero centre**; with a one-centre kernel
every pixel on a plain line reads as a candidate.

Candidates are grouped into 8-connected **clusters**. One cluster is one node: an axis-aligned
crossing lights its centre and all four arms, so the per-pixel set over-counts by about 5x.

## Step 3 — branches, degree, and demotion to a fixed point

Cutting the skeleton at the kept clusters leaves the **branches**. A cluster's **degree** is the
number of distinct branch components incident on it, found by dilating the cluster by one pixel
and reading the branch labels it touches. (A branch that leaves a node and returns to it is one
label, so a self-loop is counted once.)

A cluster is demoted from node to ordinary skeleton when either holds:

- fewer than `MIN_JUNCTION_DEGREE = 3` branches leave it — a staircase artefact, not a node;
- the `MIN_JUNCTION_DEGREE`-th longest incident branch is shorter than
  `MIN_BRANCH_WIDTHS = 0.5` × the local crack **width** (twice the distance transform at the
  cluster's representative pixel). Two paths are not distinguishable over a run shorter than the
  channel is wide.

Demotion **deletes nothing**: the cluster's pixels return to the skeleton and the branches
either side rejoin. Because rejoining lengthens branches and can rescue a neighbour, this
iterates to a fixed point, capped at `MAX_RESOLVE_PASSES = 12`; the pass count and whether it
converged are reported. Three to five passes on real frames.

Degree is reported from the *candidate* cut — every cluster removed — because that is the local
topology of the node; incidence is reported from the *final* cut, because that is the branch set
the caller holds.

## Step 4a — the flank route (the one to use)

`flank_geometry` → `flank_ids` → `flank_mode`

For each centreline pixel:

1. The nearest non-crack pixel gives the step to **wall A**; its length is the local half-width.
2. Normalise that step, and step out from the centreline by (half-width + `standoff_px`) in
   both directions. Reflecting the offset through the centreline point lands on **wall B**. No
   tangent estimate is needed, so nothing depends on how noisy the skeleton is.
3. A pixel is **decidable** when both sample points are outside the crack and in indexed
   material. The share is computed over decidable pixels only, and the decidable fraction is
   always reported beside it.
4. Flanks in **different** grains → intergranular at that pixel. Same grain → transgranular.

Per-branch rows carry each branch's own fraction, binned by `THETA_HI = 0.70` /
`THETA_LO = 0.30` into intergranular / mixed / transgranular — two thresholds, so the mixed
population stays visible instead of being forced to a side.

**The standoff is a geometric budget, not a knob.** It must clear the local crack wall and stay
inside the flanking grain. Where the crack is a large fraction of a grain no value does both,
and the share then tracks the standoff instead of the crack — so it is swept on every run.

## Step 4b — the coincidence route (kept for comparison)

`classify(mask, boundary, tau_px=…)` asks instead whether each centreline pixel lies within
`tau_px` of a grain boundary. This is the conventional test and it is the wrong one for a crack
wide enough to measure, because the crack has destroyed whatever boundary it ran along. It
ships because its **saturation** — the share of the whole field already within `tau` of a
boundary — is the floor every other number is read against, and it is the statistic that killed
this project's image-only attempt.

## Step 5 — controls, all geometry-matched

`flank_controls` (for the flank route) and `controls` (for the coincidence route). The two are
not interchangeable: a path on a boundary scores ~1 on a distance test while flank comparison is
saturated, so each route needs its own.

| control | construction | expected |
|---|---|---|
| positive | the grain map's own boundary skeleton, walked breadth-first to the crack's own length, then dilated to the crack's median half-width | ~100 % |
| negative | the real crack path placed where its mean distance to a boundary is greatest, dilated the same way | the floor |
| null | the grain map shifted and flipped at random under the fixed crack, `NULL_DRAWS = 200` draws | the real score is reported as a z against this |

Width is matched across all three, so they differ only in where the path runs — an unmatched
control would be measuring width, which is the confound that killed the earlier attempt
(Spearman +0.891 there). The positive and negative paths go through the **same** wall closing as
the real crack. The null moves the *map*, not the crack, so a draw costs two array lookups
instead of re-skeletonizing a 4096 × 6144 frame.

The **boundary budget** is reported whether or not the positive control can be built: the total
boundary skeleton length, its largest connected component, and the ratio to the crack
centreline. Under 1.0 the answer is refused outright — a crack cannot have followed boundaries
for a length the partition does not contain.

## Step 6 — the gates

`read_flank_controls` and `read_flank_sweep` are separated from the measurement so they can be
tested on recorded numbers. They refuse when:

| gate | value | meaning |
|---|---|---|
| `FLANK_MIN_POSITIVE` | 80 % | a path on the partition's own boundaries must read near 100 |
| `FLANK_MIN_RESOLUTION_PP` | 50 pp | positive − negative; everything between is scale the instrument cannot distinguish |
| `FLANK_SPAN_CEILING_PP` | 10 pp | movement across the standoff sweep |
| `FLANK_MIN_DECIDABLE` | 0.50 | share of centreline with indexed material on both flanks |
| `SATURATION_CEILING` | 0.50 | coincidence route: share of the field already within `tau` of a boundary |
| `MIN_SEGMENTS` | 8 | below this the per-segment percentages are not a distribution |
| `MIN_PER_CLASS_FOR_AUC` | 12 | below this the shortcut AUC would describe the class imbalance |

Also refused: a real value **below** the negative control, and a boundary network shorter than
the crack. Warned, not refused: a pooled fraction at the saturation floor (that reads as
transgranular), and a boundary fraction correlating with branch length or width at |ρ| > 0.3.

Two verdicts, not one — `pooled_quotable` and `split_quotable` — because the pooled fraction can
be sound on a three-branch crack while the inter/trans split cannot, and a unimodal per-segment
distribution makes the split a property of the thresholds while leaving the pooled figure
untouched.

## Step 7 — the shortcut test

`degree_separates` asks the obvious question: do branch **length** and adjacent junction
**degree** predict the class the grain map assigns? Reported as an AUC with 0.5 drawn in. If
they did, the grain map would be unnecessary. This is a measurement of the shortcut, not an
endorsement: a high AUC on one specimen is a property of that specimen's microstructure.

## What the junctions are, and are not, for

Junctions do exactly one job here: they cut the skeleton into branches. A junction's degree says
how many ways the crack divides, not whether it divided at a grain corner. The module measures
whether degree carries any mode signal rather than assuming it either way.
