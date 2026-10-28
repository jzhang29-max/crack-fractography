# Which frame can carry an intergranular / transgranular measurement

`analysis/crackmode.py` needs a co-registered grain reference and a standoff that both clears
the crack wall and stays inside the flanking grain. This screens every frame that has a
machine mask on the geometric half of that requirement, before any measurement is run.

    budget = (mean linear intercept / 2) / median crack half-width

The intercept is the classical stereological pi / (2 L_A) from a ridge skeleton with the crack
blanked, at the 95th-percentile ridge threshold; the half-width is the distance transform read
along the crack's own skeleton. The budget has to be well above 1 for a standoff to exist.

## Two things this table cannot tell you

**It does not know whether the structure is grains.** The intercept counts polishing scratches
and detector striations as readily as boundaries. Several of the highest-scoring frames here
are polished sections with no grain structure at all, and their "intercept" is the scratch
spacing. The last column is what the frame shows when looked at, at native resolution; blank
means it was not inspected.

**It does not know whether the mask is crack.** On the low-magnification and edge-view frames
the mask includes off-specimen void and background, which inflates the crack statistics.

## Scale

`HFW / image_width_px`, from the SEM databar, per
`sem-crack-detector/crack_export/analysis/CORRECTION_scale_and_magnification.md`. Verified
against the panel for `260622_316_H_b2_back_CBS_01`: HFW 259 um over 6144 px = **42.15 nm/px**
(the databar also prints a 100 um bar, CBS, 20.00 kV, Apreo).

## The screen

| frame | nm/px | crack % | half-width um | intercept um | budget | what the frame shows |
|---|---|---|---|---|---|---|
| `MAR_Amb_AS_CBS_0005` | 6.7 | 1.0 | 0.028 | 2.24 | 39.93 |  |
| `MAR_Amb_HIP_CBS_0007` | 3.4 | 1.9 | 0.020 | 1.23 | 30.73 |  |
| `MAR_Amb_HIP_CBS_0004` | 169.3 | 0.1 | 0.379 | 21.58 | 28.47 |  |
| `MAR_Amb_HIP_ETD_0008` | 4.5 | 1.8 | 0.026 | 1.46 | 28.00 |  |
| `MAR_Amb_AS_CBS_0006` | 169.3 | 0.5 | 0.535 | 27.73 | 25.91 |  |
| `MAR_Amb_HIP_ETD_0007` | 3.4 | 1.0 | 0.024 | 1.22 | 25.44 |  |
| `MAR_Amb_HIP_CBS_0006` | 6.7 | 3.2 | 0.043 | 2.17 | 25.23 |  |
| `MAR_Amb_HIP_ETD_0006` | 6.7 | 1.4 | 0.056 | 2.53 | 22.58 |  |
| `HIP_24hr_SE_Side_006` | 6.7 | 1.9 | 0.054 | 2.40 | 22.25 |  |
| `MAR_Amb_AS_CBS_0004` | 42.1 | 2.8 | 0.179 | 7.50 | 20.96 | polished section, NO grain structure (polishing scratches only) |
| `MAR_Amb_Cast_ETD_0004` | 51.9 | 3.2 | 0.220 | 8.83 | 20.06 |  |
| `MAR_Amb_AS_ETD_0006` | 169.3 | 2.9 | 0.479 | 19.10 | 19.93 | low magnification, NO grain structure; mask floods the background |
| `MAR_Amb_HIP_CBS_0008` | 4.5 | 3.0 | 0.040 | 1.59 | 19.84 |  |
| `Cast_24hr_SE_Side_006` | 51.9 | 10.1 | 0.280 | 10.83 | 19.33 | edge / fracture view; mask includes off-specimen void |
| `MAR_Amb_Cast_CBS_0003` | 169.3 | 0.5 | 0.610 | 23.09 | 18.92 |  |
| `MAR_Amb_HIP_ETD_0010` | 19.3 | 5.1 | 0.117 | 4.32 | 18.45 |  |
| `260622_316_H_b4_CBS_02` | 28.2 | 8.2 | 0.227 | 7.96 | 17.53 |  |
| `260622_316_H_b4_CBS_01` | 42.1 | 12.9 | 0.298 | 10.18 | 17.09 | 316 plan view, grains clear; mask includes the specimen edge |
| `MAR_Amb_HIP_CBS_0010` | 19.3 | 6.4 | 0.117 | 3.73 | 15.96 |  |
| `MAR_Amb_Cast_ETD_0003` | 169.3 | 0.2 | 0.535 | 16.43 | 15.35 |  |
| `AS_24hr_BSE_Side_008` | 67.4 | 3.6 | 0.426 | 12.88 | 15.11 |  |
| `MAR_Amb_HIP_CBS_0005` | 67.4 | 2.7 | 0.344 | 10.25 | 14.90 |  |
| `260622_316_H_b2_front_CBS_04` | 28.2 | 4.4 | 0.315 | 9.32 | 14.80 | 316 plan view; grain relief + slip traces |
| `MAR_Amb_AS_ETD_0004` | 42.1 | 1.2 | 0.227 | 6.43 | 14.17 |  |
| `MAR_Amb_AS_CBS_0003` | 51.9 | 4.6 | 0.328 | 9.29 | 14.16 |  |
| `260622_316_H_b2_back_CBS_01` | 42.1 | 11.3 | 0.348 | 9.54 | 13.70 | 316 plan view; grain relief + slip traces |
| `MAR_Amb_HIP_CBS_0003` | 51.9 | 7.3 | 0.348 | 8.31 | 11.94 |  |
| `260622_316_H_b2_front_CBS_01` | 42.1 | 10.0 | 0.422 | 9.38 | 11.12 | 316 plan view; grain relief + slip traces |
| `MAR_Amb_HIP_ETD_0005` | 67.4 | 1.4 | 0.491 | 10.00 | 10.18 |  |
| `260622_316_H_b2_front_CBS_02` | 28.2 | 9.7 | 0.366 | 7.30 | 9.98 | 316 plan view; grain relief + slip traces |
| `MAR_Amb_Cast_ETD_0005` | 51.9 | 22.2 | 0.511 | 8.58 | 8.39 |  |
| `MAR_Amb_AS_ETD_0002` | 169.3 | 5.1 | 1.396 | 21.73 | 7.78 |  |
| `MAR_Amb_HIP_ETD_0003` | 51.9 | 5.1 | 0.542 | 8.18 | 7.55 |  |
| `MAR_Amb_Cast_CBS_0004` | 51.9 | 25.5 | 0.571 | 7.13 | 6.25 |  |
| `260622_316_H_b2_front_CBS_03` | 13.5 | 11.6 | 0.382 | 4.34 | 5.68 | 316 plan view; grain relief + slip traces |
| `MAR_Amb_Cast_CBS_0005` | 51.9 | 35.4 | 0.605 | 6.75 | 5.58 |  |
| `260622_316_amb_b3_CBS_02` | 28.2 | 7.3 | 0.732 | 7.82 | 5.34 |  |
| `MAR_Amb_AS_CBS_0002` | 169.3 | 21.6 | 2.376 | 20.53 | 4.32 |  |
| `260622_316_amb_b3_CBS_01` | 42.1 | 13.9 | 1.407 | 10.15 | 3.61 |  |
| `MAR_Amb_AS_ETD_0003` | 51.9 | 4.7 | 1.177 | 8.30 | 3.52 |  |
| `MAR_Amb_Cast_ETD_0002` | 169.3 | 19.5 | 3.427 | 21.79 | 3.18 |  |
| `MAR_Amb_Cast_CBS_0002` | 169.3 | 27.3 | 5.387 | 19.21 | 1.78 |  |

## What the screen was used for

The four `260622_316_H_b2_*` frames and `260622_316_H_b4_*` are the only plan views of a
cracked specimen in this corpus with grain-to-grain contrast. Those are the frames the flank
measurement was then run on, across a partition sweep; see the partition-sweep result in the
session record. The budget is satisfied there (10-17) and the measurement still fails, for a
reason this table cannot see: the grain partition derived from the micrograph.

