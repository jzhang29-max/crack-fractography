## 7  What this draft is missing

Listed rather than hidden.

* **The only public dataset here is pavement, and the application is micrographs.**
  DeepCrack is concrete and asphalt surfaces. A second public set, CrackForest, was
  measured and removed from this draft for the same reason, and every other public crack
  dataset we could obtain is also road imagery. So the benchmark section establishes that
  the detector is competitive on *a* pixel-exact crack benchmark, and establishes nothing
  about micrographs. Closing this needs a public materials-microscopy crack dataset with
  pixel ground truth, and we have not found one.
* **No transfer claim.** An earlier draft argued that one refitted constant carries
  between datasets. That argument needed two datasets and this draft has one; the
  measurement still exists in docs/figures/public_metrics.json.
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
