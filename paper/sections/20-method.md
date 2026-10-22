## 2  The detector

[FIGURE P6 - pipeline in pictures]

Two gates do the detection: a robust median-absolute-deviation cut at `mad_k` standard
deviations, and an absolute floor on intensity. Everything else is preparation and
cleanup. There is no training step and no model file, and every panel in Figure 1 is the
array that stage actually produces — captured by running the shipped code, not drawn.

Two decisions are worth stating because both were made by measurement and both went
against the intuition that produced the code in the first place.

**The region classifier is switched off.** An eight-feature classifier scored each
candidate region, and deleting it improved every metric at no cost in free parameters.
Against the same candidate stage with the classifier bypassed and nothing else changed —
one variable, so the difference is the classifier's own — paired median IoU **+0.1753**
over thirteen specimens, 11 of 13, Wilcoxon p = 0.0061. The shipped path also widened the
flattening ladder from one radius to seven; the two changes together are +0.2296,
p = 0.0024, and that larger figure is not the classifier's effect and must not be quoted as
it. Three specimens that had scored recall 0.0000 at every candidate setting ever tried were
never invisible to the proposal stage; the classifier was rejecting them. One caveat the
ablation did not cover: with the classifier off the application still keeps Pass-2 rows the
model itself scored not-crack, so "switched off" is a broader change in the app than in the
experiment.

**Tiles cannot stand in for frames.** Six region-level precision rules validated on 512 px
crops were rejected on whole frames: four delete 54–75% of hand-marked crack and two change
no score. The widest crack in the training crops was
43.7 px; on full frames crack widths reach 178 px, so a region rule fitted on crops is
extrapolating on the object it most needs to keep.
