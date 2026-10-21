# Public crack data in this modality: what exists, what was rejected

Search record, 2026-10-19/20. Kept so the search is not paid for twice, and so the
paper's claim that this data barely exists is backed by a list rather than an assertion.

**Criterion:** scanning-electron (or comparable microscopy) imagery of metal or alloy,
with pixel-level crack annotation, publicly downloadable.

## Found and used

| source | what | verdict |
|---|---|---|
| **Zenodo 23045328** `Inconel718_crack` — CC BY 4.0 | SEM, nickel superalloy, 31 whole 1024 px fields + 26 released crops, anti-aliased binary masks | **the paper's benchmark.** md5 verified. The only public SEM crack set in a metal found anywhere in this search |
| **MetalDAM** (ari-dasci/OD-MetalDAM release 1.0) | SEM, additively-manufactured steel, 42 images, 5-class pixel masks | **used as a specificity test, not a crack benchmark** — it labels no cracks; class 4 is "defects, voids and artifacts" |

## Found and rejected, each for a stated reason

| source | why not |
|---|---|
| Zenodo 23045328 `EBC_crack` | SEM with crack masks, but a ceramic environmental barrier coating, not a metal. Measured, then withdrawn from the paper. Its upstream is NASA MicroNet EBC1 — identical filenames |
| NASA MicroNet (`nasa/pretrained-microscopy-models`) | the only crack class is the same EBC coating (EBC1-3, 58 images). Its `Super1-4` superalloy tasks label precipitates, not cracks |
| **Ti-6Al-4V fractography**, Zenodo 18666995 | SE + BSE electron microscopy of fatigue fracture surfaces — exactly the right imagery, 16 GB of it, and **no masks at all**. The record says the scans "can be cropped for future ML usage" |
| Hot-cracking weld set, Zenodo 16919145 | steel welds with manual binary crack masks, 609 pairs — but **light microscopy**, not SEM, and a single 11.4 GB archive |
| DeepCrack, CrackForest, Crack500, CrackSeg9k, Khanh11k, Ultralytics Crack-Seg, Kaggle crack sets | road, pavement, concrete or masonry |
| `Awesome-Crack-Detection` index (20+ datasets) | surveyed; every entry is road, pavement, concrete, masonry, stone or ceramic tile. None is microscopy |
| Hugging Face | searched for SEM / metal / alloy / intergranular crack segmentation; the hits are concrete and pavement re-packagings |
| Severstal steel defect (Kaggle) | optical surface defects on steel strip, not microscopy and not cracks |
| Rock microstructure SEM benchmark (Sci Data 2026) | SEM with pixel masks, but pores in sandstone and shale |
| STEM steel defect segmentation (Sci Rep 2019) | dislocations, precipitates and voids; no crack class, no stated release |
| Ni-superalloy fatigue-crack segmentation (OSTI 1837191) | synchrotron micro-CT, not SEM, and no data release found |
| VoroCrack3d (Zenodo 10518576) | 3D CT with crack labels, but **synthetic** cracks in concrete |

## The conclusion this supports

One public SEM crack dataset in a metal exists, and it is 31 images of one alloy. That is
why §7 of the paper calls a release of this laboratory's own annotated micrographs the
single highest-value piece of work available — see `DATASET_RELEASE_SCOPE.md`.

## The MetalDAM specificity result

MetalDAM labels no cracks, so it cannot score crack detection. It can answer a different
question the paper leaves open: **is this a crack detector or a dark-thing detector?**

Run at the shipped setting on all 42 images, the detector marked **0.26%** of all pixels:

| class | % of image | % of the detector's marks | enrichment |
|---|---|---|---|
| matrix | 34.6% | 0.96% | 0.03x |
| austenite | 55.5% | 2.05% | 0.04x |
| martensite/austenite | 8.96% | 0.03% | 0.00x |
| precipitate | 0.24% | 0.00% | 0.00x |
| **defect / void** | **0.69%** | **96.96%** | **141x** |

Per image, and this is the part that matters:

* **26 images contain no labelled void. The detector marked nothing at all on 24 of them**,
  and on the other two marked 0.006% and 0.13% of the frame.
* Of the 16 void-bearing images it marked nothing on 4 — including one where voids cover
  1.30% of the frame, which is a real miss.
* Recall on void-bearing images is **0.187 mean, 0.173 median**: it finds about a fifth of
  each void's area.

So: **high specificity, low recall**, on an independent laboratory's material at a
magnification (5,000-15,000x) the detector was never tuned for. That is the same profile
this project measures on its own corpus, where recall is lost at candidate generation and
about 70% of painted crack is never proposed, and it is the first time that profile has
been reproduced on data from outside this laboratory.

Caveats: the released images are JPEG, so a darkness threshold can see compression
artefacts; and the released images still carry a 65-row information band that the labels
were cropped of, which silently skipped every image until it was handled.
