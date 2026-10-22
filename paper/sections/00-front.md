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
of which was the shipped {mk_ship}, and the score was still rising when the grid ran out.
Extending
it to {mk_top} puts the optimum at **{mk_best}**, and the gap is not noise: on the whole
fields {mk_best} beats {mk_ship} in {mk_f1_wins} of {mk_n} images (paired Wilcoxon
p {mk_f1_p}) and improves the area fraction from {mk_ship_ratio}x the labelled value to
{mk_6_ratio}x in {mk_area_wins} of {mk_n} (p {mk_area_p}). The constant is one rung off,
in the direction of marking less. We report this because the claim it replaces was this
paper's headline.

**Everything here is measured over every pixel in the frame.** We do not report F1 or IoU:
on an image that is {in_lab_pct}% crack they discard the 98% of pixels correctly left alone,
which is most of what the detector is being asked to get right, and neither can state the
quantity this tool actually outputs — a crack area fraction. The measures used throughout
are the four-way pixel budget, accuracy, specificity, and the agreement between the area
fraction reported and the area fraction marked.

**On that last and most important measure the detector is nearly exact.** At `mad_k =
{ag_best_k}` it reports {ag_best_mark}% of the field as cracked where the annotator marked
{ag_best_lab}% — an agreement of **{ag_best}x, an error of {ag_best_err_pct}%** — and it
places **{arm_area_rank} of eight** on that measure against six classical detectors tuned
identically. The next closest is a two-parameter union of this detector with a ridge filter
at {arm_union_area}x; the closest classical arm on its own is {arm_area_2nd_name} at
{arm_area_2nd}x. Specificity
there is {ag_best_spec}%. On the dataset's released crops accuracy reaches **{cb_acc}%**,
{cb_margin} points clear of the {in_crop_empty_acc}% an empty mask scores, with specificity
{cb_spec}%. The highest figures anywhere in this work are on a second public SEM set of the
same alloy family, MetalDAM — accuracy **{md_acc}%** and specificity **{md_spec}%**, against
an empty mask's {md_empty_acc}% — but the objects labelled there are **voids, not cracks**,
so that set measures the detector's dark-object segmentation rather than its subject.

Three results cut against the method and we report them rather than omit them. **Accuracy
on the whole fields is {in_acc}%, and an empty mask scores {in_empty_acc}%** — on a field
this sparse, leaving the background alone is most of the score, and marking a pixel pays
for itself only where more than half of what is marked is right; the released-crop and MetalDAM figures
above do clear that line and the whole-field figure does not. Cropping these same images
around their cracks — as the dataset's own test split does — moves the reported area
fraction from {ag_ship}x to {in_crop_ratio}x with no change to the detector at all. And
widening the mask can buy almost any overlap score one wants: dilating the detector's own
output, which reads nothing new from the image, would take it to the top of a conventional
ranking while pushing the area fraction to {dec_area_fields}x (Section 3.5). That is the
clearest argument we have for reporting in these units and not those.

**Status of this draft.** This is one alloy and {in_n} images. Section 7 says what that is
and is not enough for.
