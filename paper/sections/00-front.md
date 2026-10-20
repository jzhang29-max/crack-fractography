# A one-parameter crack detector, measured on SEM micrographs

DRAFT — not submitted. Every number is generated from measurement files by
`paper/make_paper.py`; nothing in this document is typed by hand twice.

## Abstract

We describe a crack segmentation detector with a single free parameter and no learned
weights, and measure it on the only public crack data we could find in its own modality:
scanning-electron micrographs of metals and coatings with pixel-exact masks. On whole
fields of Inconel 718 it reaches mean per-image F1 {in_f1} and IoU {in_iou}, which is
{in_lift_f1} times the F1 and {in_lift_iou} times the IoU of marking every pixel. Its one
constant, fitted years earlier on SEM steel, is the best of seven values tested here
without being refitted.

Three results cut against the method and we report them with the first. Against seven
classical detectors tuned identically on the same images it ranks **{in_rank} of seven** —
a local threshold and a ridge filter score as well or better. On an SEM coating at
{ebc_prev}% crack prevalence it fails at {ebc_p} precision. And cropping the same images
around their cracks, as the dataset's own released test split does, raises F1 from {in_f1}
to {in_crop_f1} without changing the detector at all.

**Status of this draft.** Section 7 lists what is missing before submission.
