# Can the detector be improved?

**Yes, and the improvement is the opposite of what was asked for.** Raising recall cannot be
done honestly on this data. Lowering it can: the shipped `mad_k = 5.0` sits one rung below
the optimum, and moving to 6.0 improves F1 *and* halves the error in the crack area fraction
while marking **less**.

Measurement files: `docs/figures/{madk_above_five,madk_paired_test,arms_pixel_budget,
unproposed_crack_anatomy,missed_shell_contrast_raw,texture_channel_test,texture_prototype,
watershed_to_the_lip,ridge_grow_controls,ridge_vs_dilation_loo}.json`. All on the public
Inconel 718 set (31 whole fields / 26 released crops), every arm tuned leave-one-image-out.

## 1. The free improvement: the sweep stopped at the shipped value

The published `mad_k` sweep ran 1.0 → 5.0. 5.0 is the shipped constant, F1 was still rising
at the top of the grid, and nothing above it had ever been scored. Extending to 40:

| mad_k | marked% | area ratio | precision | recall | F1 |
|---|---|---|---|---|---|
| 4.0 | 3.260 | 2.36× | 0.258 | 0.474 | 0.3228 |
| **5.0 shipped** | 2.340 | 1.65× | 0.312 | 0.412 | 0.3444 |
| **6.0 optimum** | 1.827 | **1.27×** | 0.363 | 0.371 | **0.3564** |
| 7.0 | 1.518 | **1.06×** | 0.393 | 0.335 | 0.3521 |

Paired across the 31 fields, 6.0 beats 5.0 on F1 in **27 of 31 images (Wilcoxon p < 0.0001)**
and on absolute area-fraction error in **23 of 31 (p = 0.0124)**. Labelled crack is 1.803%.

On the released crops the same change is a wash on F1 (p = 0.3533) and *worse* on area
(0.93× → 0.72×, p < 0.0001) — those crops are cut around their cracks, so the detector
already under-marks there. **The two framings disagree about the right operating point.**

Not shipped yet: this is 31 images of one alloy, and the lab-corpus check is the decider.

## 2. Why recall cannot be raised: the missing crack is bright, not invisible

42.1% of labelled crack is never proposed even with both gates fully open. It is not faint —
it is the **wrong polarity**:

| | raw grey level | Cohen's d vs background |
|---|---|---|
| background matrix | 82 | — |
| crack the detector finds | 59 | +1.72 (darker) |
| **crack it never finds** | **127** | **−3.39 (brighter)** |

Flattening contributed only −0.16 d, so this is in the micrograph, not the pipeline. Panels
(`paper/figures/out/missed_shell_panels.png`) show what it is: **these cracks are open wide
enough to see into, and the lit, rough fracture surface inside the opening is brighter than
the matrix.** The detector marks the shadowed void; the annotator's band covers the whole
opening. 98.5% of the missed area lies within 10 px of crack that was found.

So the missing recall is real crack, and reaching it means marking bright pixels — which is
why every widening arm below both works and ruins the area fraction.

## 3. Four channels tried to reach it. All four failed their decoys.

Every arm got matched parameter count, the same LOO rule, and controls. The control that
mattered most was feeding the arm **a different image**.

| arm (whole fields) | F1 | vs wrong-image control | vs equal-area dilation | area ratio |
|---|---|---|---|---|
| shipped | 0.3444 | — | — | 1.65× |
| ridge-grown | 0.4730 | **+0.0022** | +0.0123 | 2.86× |
| texture-attached | 0.4850 | **+0.0227** | +0.0245 | 3.44× |
| watershed to the lip | 0.4500 | **−0.0077** | **−0.0111** | 2.86× |
| *equal-area dilation (reads nothing)* | 0.4608 | — | — | 3.19× |

An information-free dilation matches or beats three of them. The watershed — whose stopping
rule is the actual crack edge, the one construction with a principled boundary — scored
*below* both its own controls. **Every route that marks more buys F1 with area.**

## 4. The other real option: a different channel entirely

Not a decoy, because these are independent detectors rather than post-processing. Whole
fields, each arm tuned for area-fraction accuracy, one free parameter each:

| arm | marked% | right% | wrong% | ratio | prec | recall | F1 |
|---|---|---|---|---|---|---|---|
| Sauvola local | 1.625 | 0.724 | 0.901 | **1.08×** | 0.411 | 0.392 | 0.394 |
| Sato ridge | 1.596 | 0.687 | 0.909 | 1.23× | 0.418 | **0.453** | **0.410** |
| Meijering ridge | 1.537 | 0.668 | 0.869 | 1.19× | 0.424 | 0.443 | 0.407 |
| DETECTOR shipped | 2.340 | 0.784 | 1.556 | 1.65× | 0.312 | 0.412 | 0.344 |

**Correction to an earlier version of this table.** It capped the detector's `mad_k` at 5.0
while giving every classical arm its full range — the same truncation that produced the
paper's wrong headline (§1 above). The detector's row here is therefore its *worst* legal
operating point on area fidelity. With the full grid it reaches **1.06× at k = 7.0**, better
than Sato's 1.23×, at F1 0.3521 and precision 0.393. So the honest statement is narrower:
the ridge filters beat this detector on **F1, precision and recall** at matched parameter
count, and the area-fidelity advantage disappears once the detector is given the same range.
`arms_pixel_budget.py` now grids all arms equally; whether any of it holds on this lab's own
frames is the open question, which `lab_madk_sweep.py` and `lab_corpus_channels.py` test.

## 5. What was asked for, and what the answer is

The request was to raise recall so the detector ranks higher. Recall *can* be raised — to
0.97 — and the rank *can* be taken to first place, by dilation
(`docs/RANKING_IS_BUYABLE.md`). Both cost a 2.5× error in the reported crack area fraction.

The change that actually improves the tool moves the other way: **mark less, at mad_k 6–7**,
where the area fraction a reader gets goes from 65% too high to within 6% of the label.


## 6. The two legacy measurements, re-run (2026-10-21)

Both overlap-unit results left in the paper were re-run over every pixel.

**The region-classifier ablation.** Its guard asserts the three arms still reproduce the
stored record (+0.1753 median IoU, 11/13, p = 0.0061) before reporting anything, so these
are the same arms measured differently. Over 26 tiles and 13 specimens at 2.973% crack:

| | classifier ON | classifier OFF |
|---|---|---|
| accuracy | 95.972% | 96.268% |
| an empty mask scores | 97.027% | 97.027% |
| specificity | 97.780% | 97.585% |
| area reported / marked, pooled | 1.094x | 1.321x |

Paired per specimen: **+0.3635 pp accuracy in 11 of 13 (p = 0.0479)** and the area fraction
closer to the annotator's in **11 of 13 (p = 0.0398)** — but **specificity worse in 12 of 13
(p = 0.0005)**. The earlier claim that switching it off "improved every metric" is
**withdrawn**: it marks more, so more background is marked, and the overlap score could not
show that. Neither arm's accuracy beats an empty mask on these tiles.

Pooled and per-specimen disagree about the area fraction and the paper reports both.
MAR_H_HIP carries 21.5% of all labelled crack here and over-marks in both arms
(3.596x → 3.690x), so it owns a pooled ratio while counting once in a per-specimen test.

**The DeepCrack result could not be re-run.** The downloaded images were not retained — the
pavement directories are 0 bytes — so there is nothing left to re-score, and a number
cannot be converted into these units by arithmetic on a stored summary. It is **withdrawn
from the paper** rather than converted. Re-downloading was rejected on two grounds: pavement
was removed from this paper as the wrong modality at the author's direction, and the result
was always a warning about cross-modality benchmarking rather than a finding.
