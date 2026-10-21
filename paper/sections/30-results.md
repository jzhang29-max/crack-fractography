## 3  On public SEM data with pixel-exact ground truth

One set: the Inconel 718 crack class of a public cross-material microstructure collection
(Zenodo 23045328, CC BY 4.0), {in_n} whole 1024 px fields of a nickel superalloy at
{in_prev}% crack prevalence. It is the only public crack segmentation data we found in this
modality and material class. Section 7 records what else was searched and rejected,
including a second class from this same collection.

Scoring is at 0 px tolerance with `mad_k` chosen leave-one-image-out.

Two properties of the data had to be established before any score could be trusted. The
masks are **anti-aliased binary** rather than strictly two-valued — 94.7% of pixels exactly
0, 4.3% at 246 or above, 0.52% in between — so the scorer checks bimodality and refuses a
mask that fails it. And the images are **16-bit TIFFs**: an ordinary 8-bit conversion turns
them nearly white, mean 254.8 against the data's 15510 of 65535, which drove the detector's
recall to 0.0012 before it was caught. Taking the high byte reproduces the dataset authors'
own 8-bit PNGs exactly, so that is the conversion used.

[FIGURE P1 - public scores]

### 3.1  Whole fields, not the released crops

The collection ships a test split of 1024 px crops. We do not use it as the primary
measurement for two reasons. Every one of the {in_crop_src} source images behind those
crops also appears among the originals, so the two are not independent sets. And the crops
are cut around their cracks: prevalence rises from {in_prev}% to {in_crop_prev}% and F1
with it, from {in_f1} to {in_crop_f1}, with no change to the detector. Figure 2 shows both
curves. The difference between them is what a benchmark's framing is worth, and it is
larger than most differences between methods in this literature.

### 3.2  Scored as a pixel budget

[FIGURE P5 - pixel budget]

Precision, recall, F1 and IoU all discard the true negatives. On an image that is
{in_prev}% crack that is 98% of the evidence, and it lets two very different detectors
share a score — one marking 0.3% of a frame and one marking 5% can land on the same IoU.
The quantity this tool actually reports to a user is an **area fraction**, a pixel
percentage, so the scores belong in the same units as the answer.

| | whole fields | released crops |
|---|---|---|
| labelled crack | {in_lab_pct}% | {in_crop_lab_pct}% |
| detector marked | {in_mark_pct}% | {in_crop_mark_pct}% |
| of which correct | {in_tp_pct}% | {in_crop_tp_pct}% |
| of which wrong | {in_fp_pct}% | {in_crop_fp_pct}% |
| **area fraction reported / true** | **{in_ratio}x** | **{in_crop_ratio}x** |
| accuracy | {in_acc}% | {in_crop_acc}% |
| balanced accuracy | {in_bacc}% | {in_crop_bacc}% |
| MCC | {in_mcc} | {in_crop_mcc} |

Three things only this view shows.

**The area fraction a user reads off this tool is about {in_ratio} times too high** on
whole fields. That is the error that reaches a materials conclusion, and no F1 or IoU
states it.

**The bias reverses between the two framings of the same images** — {in_ratio}x on whole
fields, {in_crop_ratio}x on the crops cut from them. The detector did not change.

**Accuracy is {in_acc}% and is worthless.** Marking nothing at all would score
{in_tn_plus}%. It is printed here only so that it is never quoted: at this prevalence the
measures worth reading are balanced accuracy and MCC, and those are {in_bacc}% and
{in_mcc}.

### 3.3  The one free constant

[FIGURE P2 - operating curve]

`mad_k = 5.0` was fitted on SEM steel in a different laboratory, on a different alloy,
years before this dataset existed. On these whole fields it is the best of the seven values
tested and the curve falls away monotonically below it. That is the strongest positive
result here: the constant did not need refitting for a new SEM corpus.

### 3.4  Against classical detectors, the detector does not lead

[FIGURE P4 - baselines]

Every arm gets its own best parameter by the same leave-one-image-out rule, on the same
images, through the same scoring function. This detector ranks **{in_rank} of seven**:
Sauvola local thresholding reaches {in_sauvola} and Sato ridge {in_sato} against our
{in_crop_f1}.

The top three are separated by {in_spread} F1, about the width of a gap this project has
elsewhere called irresolvable at this sample size, so the honest statement is that this
detector and two classical filters are indistinguishable here. We built it for micrographs
and on micrographs it is matched by a local threshold from 2000 and a ridge filter from
1998.

This comparison was run on the released crops, the only set all seven arms have been scored
on, so every arm in it is flattered by the same cropping described in §3.1.
