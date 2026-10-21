# A one-parameter crack detector on SEM micrographs, and the pixel budget it spends

DRAFT — not submitted. Every number is generated from measurement files by
`paper/make_paper.py`; nothing in this document is typed by hand twice.

## Abstract

We describe a crack segmentation detector with a single free parameter and no learned
weights, and measure it on the only public crack data we could find in its own modality
and material class: {in_n} whole scanning-electron fields of Inconel 718 with pixel-exact
masks.

We report it primarily as a **pixel budget** rather than as F1 or IoU. On an image that is
{in_lab_pct}% crack, F1 and IoU discard the 98% of pixels that are correctly left alone,
and they cannot state the quantity this tool actually outputs — an area fraction. The
detector marks {in_mark_pct}% of the image where the human marked {in_lab_pct}%: of that,
{in_tp_pct}% is right and {in_fp_pct}% is wrong, so **an area fraction read off this tool
is {in_ratio} times too high**. Accuracy is {in_acc}%, which is worse than marking nothing;
balanced accuracy is {in_bacc}% and MCC {in_mcc}. In the conventional units it is F1
{in_f1} and IoU {in_iou}, {in_lift_f1} times the F1 of marking every pixel.

The detector's one constant, fitted years earlier on SEM steel in another laboratory, is
the best of seven values tested here without refitting. Two results cut against it, and we
report them with the first: against seven classical detectors tuned identically it ranks
**{in_rank} of seven**, and cropping these same images around their cracks — as the
dataset's own test split does — moves the reported area fraction from {in_ratio}x to
{in_crop_ratio}x and F1 from {in_f1} to {in_crop_f1}, with no change to the detector.

**Status of this draft.** This is one alloy and {in_n} images. Section 7 says what that is
and is not enough for.
