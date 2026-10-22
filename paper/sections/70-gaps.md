## 7  What this draft is missing

Listed rather than hidden.

* **The evidence is {in_n} images of one alloy**, from a single released collection whose
  record is one sentence long and names no pixel size, no microscope and no annotation
  protocol. One crack class out of eighteen targets. That is enough to place the detector
  and not enough to characterise it, and it is the single largest weakness of this draft.
* **A second class from the same collection was measured and removed.** The EBC
  environmental barrier coating ({ebc_n} fields, {ebc_prev}% prevalence) is a ceramic
  coating rather than a metal and is outside the application. The detector failed on it —
  it reports {ebc_ratio} times the labelled area fraction there — and that failure is not
  reported above. Removing it
  also cost Section 4 its strongest form, which compared two sets annotated four times
  apart in brush width. Both measurements remain in docs/figures/.
* **What was searched for and not found.** Public crack segmentation data in this modality
  is close to non-existent. Ruled out, each for a stated reason: road and pavement sets
  (CrackForest, DeepCrack, Crack500, CrackSeg9k and the aggregated collections) are the
  wrong modality; MetalDAM is SEM steel with pixel masks but its five classes are phases
  and a generic "defect", not cracks; NASA's MicroNet superalloy tasks label precipitates,
  not cracks; a released Ti-6Al-4V fractography set (SE and BSE, 16 GB) ships images with
  no masks at all; and the published nickel-superalloy fatigue-crack segmentation work we
  found is tomography with no data release. A second independent SEM crack set would change
  this paper more than any further work on the method.
* **The pavement result cannot be restated in this paper's units, so it is withdrawn
  rather than converted.** The detector was once scored on DeepCrack and ranked first of
  seven there. Those were overlap scores; every other result in this paper has since been
  recomputed over every pixel, and this one cannot be, because the downloaded images were
  not retained and there is nothing left to re-score. We will not convert a measurement by
  arithmetic on a stored summary. Two reasons not to re-download and re-run it: a
  road-surface benchmark says nothing about micrographs, which is why it left the argument
  in the first place, and the contrast between that ranking and the {in_rank_fields}-of-seven
  on the SEM whole fields was always better read as a warning about cross-modality
  benchmarking than as a result. The old figures survive in
  `docs/figures/public_metrics.json` and in the git history; they are not quoted here and
  should not be quoted from there.
* **No laboratory results are reported.** By choice: the specimen measurements are not
  being published here. Sections 2 and 5 cite effects measured on that corpus as
  methodological evidence; a reviewer cannot check those without the data, and they should
  be read as weaker than the public-dataset numbers.
* **The corpus series in Figure 6 carries no stroke width.** The instrument that would
  measure it comparably needs a tile cache not present on this machine.
* **The detector's best score in this project is not on cracks.** On MetalDAM's voids —
  compact, dark, high-contrast objects in SEM steel — it reaches accuracy {md_acc}% and specificity
  {md_spec}% there, {md_margin} points clear of an empty mask, against {in_acc}% on
  cracks in the superalloy where an empty mask wins; it reports an area fraction
  {md_ratio}x the truth
  against {in_ratio}x. That is what a multi-scale darkness threshold should do, and it
  bounds how much of this paper is about cracks specifically rather than about dark thin
  objects. Appendix A gives the full span.
* **No timing, and no comparison against a trained network on equal footing.** A fair
  speed claim needs matched hardware, and an earlier attempt found this detector 1.6x
  slower than a single-pass U-Net at p = 0.0001.
* **Novelty is not claimed.** Fifty-five framings of this work were checked against prior
  art and all were already owned. What is offered is measurement.

## Data and code availability

The images and masks in Section 3 are the Inconel 718 crack class of a public collection,
Zenodo record 23045328, CC BY 4.0 (doi:10.5281/zenodo.23045328). The whole fields are its
`image`/`mask` directories and the released crops its `image_cropped`/`mask_cropped`
directories; both are used unmodified except for the 16-bit to 8-bit conversion described
in Section 3, which takes the high byte.

Every measurement file this paper draws a number from is listed in `docs/INDEX.md` with the
script that produced it, and the paper itself is built by `paper/make_paper.py`, which fails
rather than renders if a number has no source. **The repository is not yet public and no
archival DOI or commit hash is quoted here; both are required before submission**, and
until they exist a reader cannot check any of the above. The hand-corrected micrographs of
our own laboratory referred to in Sections 2, 5 and 6 are not in a public release either;
`docs/DATASET_RELEASE_SCOPE.md` measures what releasing them would cost and lists the
decisions still open.
