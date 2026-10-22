# Is the TXM work ready to go into the paper?

**No — not as a capability. Yes, as a scoped negative result plus one positive group.**
Measured 2026-10-22. Data: `docs/figures/txm_background_units.json`, generator
`analysis/research/improve/txm_background_units.py`.

## 1. The SEM detector on TXM, in pixel-percentage units

31 TXM frames carry both an image and a hand-made correction mask. Scored over **refereed
pixels only** (1 = crack, 2/3 = not-crack, 0 = unreviewed and excluded); 38.1% of all
pixels in those frames were ruled on by a human. Crack is 8.103% of the refereed area, so
**an empty mask scores 91.897% accuracy** there.

TXM is a better substrate for this than our own SEM corpus: its paint carries 96.6M
refereed not-crack pixels against 8.5M crack (11.3:1), so a false positive actually costs
something. On the SEM corpus the ratio runs the other way and precision cannot be measured.

**Pooled, the detector is below an empty mask at every setting tested:**

| mad_k | marked% of refereed | accuracy | vs empty mask | recall | area reported / painted |
|---|---|---|---|---|---|
| 5.0 (old default) | 20.890 | 81.878% | −10.02 pp | 0.671 | 2.578× |
| 6.0 (SEM optimum) | 20.041 | 82.378% | −9.52 pp | 0.649 | 2.473× |
| 10.0 | 18.904 | 82.891% | −9.01 pp | 0.611 | 2.333× |
| *control: Otsu, no model* | 83.497 | 23.140% | −68.76 pp | — | 10.30× |
| *control: mark everything* | 100.000 | 8.103% | −83.79 pp | 1.000 | 12.34× |

It beats both controls comfortably. It does not beat doing nothing.

## 2. The pooled number is four different answers

This is the finding. At `mad_k = 6`:

| group | frames | crack % of refereed | accuracy | vs empty | recall | area |
|---|---|---|---|---|---|---|
| **B3** | 6 | 22.2% | **97.2%** | **+19.4 pp** | **0.918** | **1.01×** |
| B2 | 12 | 8.9% | 84.7% | −6.3 pp | 0.187 | 1.10× |
| AM/HC | 9 | 2.6% | 84.9% | −12.5 pp | **0.009** | **5.17×** |
| Wrought | 4 | 15.4% | 65.5% | −19.1 pp | 0.856 | 3.00× |

- **B3 transfers.** Accuracy 19 points clear of an empty mask, recall 0.92, area fraction
  within 1%. The SEM constant works unchanged on this group.
- **B2 gets the amount right and the location wrong**: area 1.10× but recall 0.187.
- **AM/HC is the failure case**: it finds under 1% of the painted crack while marking 13%
  of the refereed area — blind *and* over-marking.
- **Wrought over-marks 3×** while finding most of the crack.

Averaging these into one number would be a weighted mean of four different materials.
See figure `paper/figures/out/txm_transfer.png`.

## 3. Why it is not ready

1. **The transfer result is mostly negative** and the one positive group is 6 frames of
   one specimen. Prior work in this project records that the eight TXM nulls are all the
   same specimen, with an exact p floor of 0.1111 — the groups cannot be compared.
2. **The pixel size is not confirmed.** 29.24 nm/px is DERIVED from operator-supplied
   mosaic geometry (a 30 µm window at 0.35 overlap, 9×5 tiles over 6367×3691 px), not read
   from instrument metadata. The TXM repository marks it `[TODO-AUTHOR]` and records that
   two frames close only at 0.30 overlap. Every physical length — and every scale bar —
   scales with it.
3. **45 `[TODO-AUTHOR]` markers** remain in the TXM draft, most of them one missing
   acquisition block: instrument, beam energy, voxel size, projections, reconstruction
   algorithm, stitching software, flat/dark protocol. None of it is derivable from the
   data.
4. **Specimen and loading provenance is absent**: what "1200 cycles", "3_1_lbf" and
   "338_13um" mean, whether frames were acquired under load, and how the crack-free
   specimens were confirmed crack-free.

## 4. What could go in the paper now

A short subsection, honestly scoped: *the detector was carried unchanged to a second
modality and the result was mixed* — it clears both no-information controls everywhere,
clears an empty mask on one specimen group of four, and over-reports the crack area
fraction by 2.5× pooled. That is a real cross-modality transfer result and it costs the
paper nothing to state. It is not a TXM capability claim and must not be written as one.

**What it needs to become one:** the acquisition block (§3 above), confirmation of the
voxel size, and more than one specimen per group.
