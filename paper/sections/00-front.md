# A one-parameter crack detector, and what its scores do and do not mean

DRAFT — not submitted. Every number is generated from measurement files by
`paper/make_paper.py`; nothing in this document is typed by hand twice.

## Abstract

We describe a crack segmentation detector with a single free parameter and no learned
weights, and measure it on two public crack datasets with pixel-exact ground truth. On the
DeepCrack test split it reaches mean per-image F1 {dc_f1} and IoU {dc_iou}, ranking first
of seven among classical detectors tuned identically on the same images; on CrackForest it
reaches F1 {cf_f1} and IoU {cf_iou}, ranking third. One constant refitted on one dataset
carries to the other. We then show that the scores themselves are the fragile part: a
reconstruction of the label that is *exactly right about where the crack is* and wrong only
about how wide it is loses most of its IoU, and the shape of that loss differs between
corpora. We report the measurement practices this forced on us, and several negative
results, including one that refutes the explanation we ourselves offered first.

**Status of this draft.** Section 7 lists what is missing before submission.
