# A one-parameter crack detector, measured on SEM micrographs and on pavement

DRAFT — not submitted. Every number is generated from measurement files by
`paper/make_paper.py`; nothing in this document is typed by hand twice.

## Abstract

We describe a crack segmentation detector with a single free parameter and no learned
weights, and measure it on public crack data with pixel-exact ground truth in two
modalities. On SEM micrographs of Inconel 718 it reaches mean per-image F1 {in_f1} and IoU
{in_iou}, {in_lift_f1} times the F1 of marking every pixel. On a pavement benchmark,
DeepCrack, the same detector reaches F1 {dc_f1} and IoU {dc_iou}. The difference between
those two numbers is the paper: the detector is not worse on micrographs by accident, and
the gap is not explained by annotation width, which we show by measuring it.

The detector's one constant, fitted originally on SEM steel, is **optimal unchanged** on
the SEM alloy data and wants a different value on pavement — so it transfers within a
modality and not across one. Two results cut against the method: on an SEM coating with
{ebc_prev}% crack prevalence it fails outright at {ebc_p} precision, and against classical
detectors tuned identically it ranks first of seven on pavement but only third of seven on
the SEM alloy, where Sauvola thresholding and a Sato ridge filter score as well or better.
We report both rather than omit them.

**Status of this draft.** Section 7 lists what is missing before submission.
