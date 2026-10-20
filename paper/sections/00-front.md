# A one-parameter crack detector, measured on SEM micrographs of a nickel superalloy

DRAFT — not submitted. Every number is generated from measurement files by
`paper/make_paper.py`; nothing in this document is typed by hand twice.

## Abstract

We describe a crack segmentation detector with a single free parameter and no learned
weights, and measure it on the only public crack data we could find in its own modality
and material class: scanning-electron micrographs of a nickel superalloy with pixel-exact
masks. On {in_n} whole fields of Inconel 718 it reaches mean per-image F1 {in_f1} and IoU
{in_iou} — {in_lift_f1} times the F1 and {in_lift_iou} times the IoU of marking every
pixel. Its one constant, fitted years earlier on SEM steel in another laboratory, is the
best of seven values tested here without being refitted.

Two results cut against the method and we report them with the first. Against seven
classical detectors tuned identically on the same images it ranks **{in_rank} of seven** —
a local threshold and a ridge filter score as well or better. And cropping the same images
around their cracks, as the dataset's own released test split does, raises F1 from {in_f1}
to {in_crop_f1} without changing the detector at all.

**Status of this draft.** This is one alloy and {in_n} images. Section 7 says what that is
and is not enough for.
