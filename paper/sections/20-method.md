## 2  The detector

[FIGURE P6 - pipeline in pictures]

Two gates do the detection: a robust median-absolute-deviation cut at `mad_k` standard
deviations, and an absolute floor on intensity. Everything else is preparation and
cleanup. There is no training step and no model file, and every panel in Figure 1 is the
array that stage actually produces — captured by running the shipped code, not drawn.

Two decisions are worth stating because both were made by measurement and both went
against the intuition that produced the code in the first place.

**The region classifier is switched off.** An eight-feature logistic classifier scored each
candidate region. Switching it off changes exactly one thing, so the difference is the
classifier's own, and we have measured it twice: first by IoU, which is how an earlier draft
reported it, and again over every pixel once this paper settled on the units of Section 3.3.
The two tell different stories and the second is the one we stand behind.

Across {dz_n_spec} specimens and {dz_n_tiles} hand-labelled tiles at {dz_lab}% crack:

| | classifier ON | classifier OFF |
|---|---|---|
| marked | 3.253% | 3.926% |
| accuracy | {dz_a_acc}% | {dz_b_acc}% |
| an empty mask would score | {dz_empty}% | {dz_empty}% |
| specificity | {dz_a_spec}% | {dz_b_spec}% |
| area reported / marked, pooled | {dz_a_area}x | {dz_b_area}x |

Paired per specimen, switching it off **gains {dz_acc_gain} points of accuracy in
{dz_acc_wins} of {dz_n_spec} specimens (p {dz_acc_p})** and brings the reported area
fraction closer to the annotator's in **{dz_area_wins} of {dz_n_spec} (p {dz_area_p})**.

**It also costs specificity in {dz_spec_worse} of {dz_n_spec} specimens (p {dz_spec_p}),
and an earlier draft's claim that it "improved every metric" is withdrawn.** It marks more,
so more background is marked; that is not a surprise, it is a cost, and the overlap score
we first used could not show it.

**Pooled and per-specimen disagree about the area fraction, and we report both.** Per
specimen the change helps in {dz_area_wins} of {dz_n_spec}; pooled it moves the ratio from
{dz_a_area}x to {dz_b_area}x, further from exact. One specimen is responsible:
{dz_hog} carries {dz_hog_share}% of all labelled crack in this benchmark and over-marks in
both arms ({dz_hog_a}x to {dz_hog_b}x), so it dominates a pooled ratio while counting once
in a per-specimen test. Neither aggregation is wrong; they answer different questions.

**Neither arm earns its accuracy on these tiles.** An empty mask scores {dz_empty}% and the
best arm reaches {dz_b_acc}%. The classifier decision is a choice between two operating
points inside a band where accuracy cannot distinguish either from doing nothing, which is
the same situation Section 4 measures on the public fields.

Three specimens on which the pipeline had found no crack at all, at every candidate setting
ever tried, were never invisible to the proposal stage; the classifier was rejecting them.
That is the finding this change rests on, and it does not depend on the units. The shipped
path also widened the flattening ladder from one radius to seven; that second change takes
the pooled area ratio to {dz_c_area}x and is not attributed to the classifier anywhere in
this paper. One caveat the ablation did not cover: with the classifier off the application
still keeps Pass-2 rows the model itself scored not-crack, so "switched off" is a broader
change in the app than in the experiment.

**Tiles cannot stand in for frames.** Six region-level precision rules validated on 512 px
crops were rejected on whole frames: four delete 54–75% of hand-marked crack and two change
no score. The widest crack in the training crops was
43.7 px; on full frames crack widths reach 178 px, so a region rule fitted on crops is
extrapolating on the object it most needs to keep.
