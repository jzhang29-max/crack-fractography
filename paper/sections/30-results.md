## 3  On public data with pixel-exact ground truth

Both datasets are scored at 0 px tolerance, with `mad_k` chosen leave-one-image-out.
Image-level grouping is the right unit here — these are independent road scenes, not
repeated views of one specimen.

[FIGURE P1 - public scores]

Against the no-information floors the margin is large: on DeepCrack the detector is
{dc_lift_f1} times the F1 of marking every pixel and {dc_lift_iou} times its IoU; on
CrackForest, {cf_lift_f1} and {cf_lift_iou} times. A mask of the same area with its pixels
scattered at random scores {dc_rnd_f1} and {cf_rnd_f1}.

### 3.1  One constant, two datasets

[FIGURE P2 - transfer]

The shipped constant was fitted on SEM steel. Carried unchanged to road images it is poor
on CrackForest ({cf_frozen}) and adequate on DeepCrack ({dc_frozen}). Refitted, each
dataset peaks within one grid step of the other's optimum. That is the difference between
"this needs retuning per corpus" and "this needs retuning per imaging modality", and only
the second is a tolerable property for a tool.

### 3.2  Against classical detectors

[FIGURE P4 - baselines]

Every arm gets its own best parameter by the same leave-one-image-out rule, on the same
images, through the same scoring function. The detector ranks first of seven on DeepCrack
and third on CrackForest, where two ridge filters beat it.

It is worth naming what this comparison is not. These are classical baselines, not the
trained networks that hold the published state of the art on both datasets — about 0.86 F1
on DeepCrack and 0.7535 on CrackForest, both trained on the dataset in question. A
one-parameter detector landing at {dc_f1} and {cf_f1} without training is a statement about
how much of the benchmark is reachable without learning, not a claim to have beaten anyone.
