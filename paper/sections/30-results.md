## 3  On public data with pixel-exact ground truth

The DeepCrack test split is scored at 0 px tolerance, with `mad_k` chosen
leave-one-image-out. Image-level grouping is the right unit here — these are independent
scenes, not repeated views of one specimen.

[FIGURE P1 - public scores]

Against the no-information floors the margin is large: the detector is {dc_lift_f1} times
the F1 of marking every pixel and {dc_lift_iou} times its IoU. A mask of the same area
with its pixels scattered at random scores {dc_rnd_f1}.

### 3.1  The one free constant

[FIGURE P2 - operating curve]

The shipped constant was fitted on SEM steel. Carried unchanged to this dataset it reaches
{dc_frozen}; refitted it reaches {dc_f1}. The curve is single-peaked and broad, so the
detector is not balanced on a knife edge — but with one dataset in this draft, nothing here
shows that a refitted constant *transfers*, and no such claim is made. See Section 7.

### 3.2  Against classical detectors

[FIGURE P4 - baselines]

Every arm gets its own best parameter by the same leave-one-image-out rule, on the same
images, through the same scoring function. The detector ranks first of seven.

It is worth naming what this comparison is not. These are classical baselines, not the
trained networks that hold the published state of the art on this dataset — about 0.86 F1,
trained on it. A one-parameter detector landing at {dc_f1} without training is a statement
about how much of the benchmark is reachable without learning, not a claim to have beaten
anyone.
