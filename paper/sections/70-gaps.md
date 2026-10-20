## 7  What this draft is missing

Listed rather than hidden.

* **The SEM evidence is {in_n} images of one alloy and {ebc_n} of one coating**, from a
  single released collection whose record is one sentence long and names no pixel size, no
  microscope and no annotation protocol. Two crack classes out of eighteen targets. That is
  enough to place the detector and not enough to characterise it.
* **What was searched for and not found.** Public crack segmentation data in this modality
  is close to non-existent. Ruled out, each for a stated reason: road and pavement sets
  (CrackForest, DeepCrack, Crack500, CrackSeg9k and the aggregated collections) are the
  wrong modality; MetalDAM is SEM steel with pixel masks but its five classes are phases
  and a generic "defect", not cracks; NASA's MicroNet superalloy tasks label precipitates,
  not cracks; a released Ti-6Al-4V fractography set (SE and BSE, 16 GB) ships images with
  no masks at all; and the published nickel-superalloy fatigue-crack segmentation work we
  found is tomography with no data release. A second independent SEM crack set would change
  this paper more than any further work on the method.
* **Pavement results were measured and removed.** The detector reaches F1 0.7932 and IoU
  0.6809 on DeepCrack, ranking first of seven there. It is not reported above because a
  road-surface benchmark says nothing about micrographs, and the contrast between that
  ranking and the third-of-seven on SEM is better read as a warning about cross-modality
  benchmarking than as a result. The numbers remain in docs/figures/public_metrics.json.
* **No laboratory results are reported.** By choice: the specimen measurements are not
  being published here. Sections 2 and 5 cite effects measured on that corpus as
  methodological evidence; a reviewer cannot check those without the data, and they should
  be read as weaker than the public-dataset numbers.
* **The corpus series in Figure 3 carries no stroke width.** The instrument that would
  measure it comparably needs a tile cache not present on this machine.
* **No timing, and no comparison against a trained network on equal footing.** A fair
  speed claim needs matched hardware, and an earlier attempt found this detector 1.6x
  slower than a single-pass U-Net at p = 0.0001.
* **Novelty is not claimed.** Fifty-five framings of this work were checked against prior
  art and all were already owned. What is offered is measurement.
