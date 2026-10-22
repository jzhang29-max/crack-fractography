# A one-parameter crack detector on SEM micrographs, and the pixel budget it spends

DRAFT — not submitted. No author, affiliation or venue is set, and there is no reference
list yet; both are required before this goes anywhere. Most numbers are generated from
measurement files by `paper/make_paper.py`, which fails the build on an unresolved name, but
a residue in Sections 2, 4, 5 and 6 is still typed by hand and is being migrated.

## Abstract

We describe a crack segmentation detector with a single free parameter and no learned
weights, and measure it on the only public crack data we could find in its own modality
and material class: {in_n} whole scanning-electron fields of Inconel 718 with pixel-exact
masks.

**We previously reported that its one constant did not need refitting. That was an artefact
of where the sweep stopped.** The published sweep tested seven values of `mad_k`, the largest
of which was the shipped {mk_ship}, and F1 was still rising when the grid ran out. Extending
it to {mk_top} puts the optimum at **{mk_best}**, and the gap is not noise: on the whole
fields {mk_best} beats {mk_ship} in {mk_f1_wins} of {mk_n} images (paired Wilcoxon
p {mk_f1_p}) and improves the area fraction from {mk_ship_ratio}x the labelled value to
{mk_6_ratio}x in {mk_area_wins} of {mk_n} (p {mk_area_p}). The constant is one rung off,
in the direction of marking less. We report this because the claim it replaces was this
paper's headline.

We report the accuracy primarily as a **pixel budget** rather than as F1 or IoU. On an image that is
{in_lab_pct}% crack, F1 and IoU discard the 98% of pixels that are correctly left alone,
and they cannot state the quantity this tool actually outputs — an area fraction. The
detector marks {in_mark_pct}% of the image where the human marked {in_lab_pct}%: of that,
{in_tp_pct}% is right and {in_fp_pct}% is wrong, so **an area fraction read off this tool
is {in_ratio} times too high**. Accuracy is {in_acc}%, which is worse than marking nothing;
balanced accuracy is {in_bacc}% and MCC {in_mcc}. In the conventional units it is F1
{in_f1} and IoU {in_iou}, {in_lift_f1} times the F1 of marking every pixel.

Three results cut against the method and we report them rather than omit them. Against six
classical detectors tuned identically it ranks **{in_rank_fields} of seven on these whole
fields** ({in_f1_fields_cmp} against the leader's {in_best_fields}), and {in_rank} of seven
on the dataset's released crops, within {in_spread} F1 of the leader there. Cropping these
same images around their cracks — as the dataset's own test split does — moves the reported
area fraction from {in_ratio}x to {in_crop_ratio}x and F1 from {in_f1} to {in_crop_f1}, with
no change to the detector at all. And the ranking itself is buyable: dilating this detector's
own output, which reads nothing new from the image, takes it to first place on the crops at
the cost of a {dec_area_fields}x area-fraction error (Section 3.5).

**Status of this draft.** This is one alloy and {in_n} images. Section 7 says what that is
and is not enough for.
