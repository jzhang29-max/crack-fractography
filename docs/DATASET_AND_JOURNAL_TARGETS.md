# A public SEM-only benchmark, and where to send this

Searched 2026-10-22. Five parallel finders, every candidate re-checked by a second agent
that was told to refute it. 15 of 30 candidates survived. **The verifiers did real work** —
HTTP range requests into ZIP64 central directories, downloading and measuring mask
morphology, rendering tiles and looking at them — and three of them overturned their
finder's headline claim.

## 1. Is there a public SEM-only crack benchmark? No.

**The defensible statement:**

> There is no public **SEM metal/alloy crack pixel-mask** dataset other than the Inconel 718
> folders in Zenodo 23045328.

Not "no public SEM crack masks exist" — they do, for ceramic coatings. The claim needs
*metal/alloy* **and** *cracks* together, and there it holds. Nine candidates were checked
and every one failed on a specific, measured point.

### The candidate that looked best, and why it is dead

**Medghalchi et al., DP800 dual-phase steel, Zenodo 11224127** (*Materials & Design* 243
(2024) 113031). Panoramic SEM of a metal, hand-drawn pixel masks, CC BY, 3.65 GB. It fails
on content, and the verifier measured rather than inferred:

- Downloaded all 171 labelled masks and measured every damage object ≥20 px (n = 296):
  **median aspect ratio 1.74**, only 1 of 296 above aspect 5, 87.8% below aspect 3, median
  solidity 0.92 with 91.2% above 0.8, median equivalent diameter 0.42 µm.
- Rendered the seven highest-damage tiles with contours over the SEM and looked at them:
  **every labelled site is a rounded, near-convex cavity.** Not one elongated or branching
  crack in the top-damage set. Mask registration checked (mean grey 19–47 inside damage vs
  83–162 outside), so these really are the dark voids.

It is **void labelling, morphologically the inverse** of Inconel 718 fatigue cracks, where
one connected tortuous structure carries ~97% of the area. Do not use it.

### Everything else

| candidate | measured reason it fails |
|---|---|
| NASA MicroNet EBC-1/2/3 | ceramic **coating**. The only maintained SEM crack-mask benchmark there is, and it is the wrong material |
| BAM hot-cracking TIG weld (Zenodo 16919145) | the record's own description says the images are **light microscopy** |
| Ti-6Al-4V fractography, CWRU SDLE | labels are **lack-of-fusion and keyhole porosity**, not cracks |
| Ti-6Al-4V CT, Materials Data Facility | fails "pixel masks of cracks" on three independent grounds |
| Cold-spray Cr on Zr (Zenodo 10478594) | the record **contains no images at all** |
| ORNL tungsten thermal-shock (arXiv 2610.03505) | not public, and the verifier found that permanent |
| DeepFract 316L CSCC (SSRN 5012225) | artifact **not retrievable**, confirmed on re-check |
| Al-Mg-Si SCC, CWRU SDLE | X-ray CT, weak labels |
| NMC cathode cracks (figshare 32975921) | **NMC811 is an oxide ceramic**, not a metal — see §3, it matters for another reason |

## 2. A provenance problem in the benchmark this paper already uses

A verifier pulled the ZIP64 central directory of `train.zip` from Zenodo 23045328 by HTTP
range request (4,389,010,246 bytes, 30,840 entries, central directory at offset
4,384,583,366), located `class_id.txt` at local-header offset 96,049,044, range-fetched and
inflated it, and read all 15 lines verbatim:

```
0 Al-Zn_cooling      5 MetalDAM_defect      10 UHCS_cementite_network
1 EBC_background     6 MetalDAM_ma&au       11 UHCS_cementite_particles
2 EBC_crack(24)      7 MetalDAM_matrix      12 UHCS_ferrite
3 EBC_oxide(24)      8 Ni-super_secondary   13 UHCS_information
4 MetalDAM_austenite 9 Ni-super_terriary    14 UHCS_Widman
```

**`Inconel718_crack` is not in it.** `train.zip` holds 21 target folders: these 15 plus
exactly six Inconel 718 folders (`Inconel718_crack`, `Inconel718_twin_grain`,
`inconel718_carbides`, `_inter_delta`, `_intra_delta`, `_matrix`). The undeclared folders
and the Inconel 718 folders are the same set. The only crack class the record declares is
`EBC_crack` — the ceramic coating this paper withdrew.

The data is real, has masks, and is CC BY. But it is **undeclared extra content**: no class
definition, no stated provenance, and (checked separately) no pixel size anywhere — no TIFF
resolution tag, no databar, nothing in the record, and the collection's subsets come from
different microscopes.

**This belongs in the paper's limitations.** The honest sentence is that the evaluation
class is present in the archive but absent from the collection's own class list, so its
annotation protocol is undocumented. It does not invalidate the measurement — the masks
exist and the area fraction is dimensionless — but a reviewer who checks will find it, and
it is better found in your own limitations section.

## 3. Prior art that must be read before any novelty claim

**Tegetmeyer-Kleine et al.**, arXiv:2608.27162 — *"Data-efficient crack quantification in
lithium-ion cathodes using foundation model transfer"* (also circulating as *"Multi-class
crack mapping in NMC811 cathodes with frozen DINOv3 features"*, Nature Computational
Science 2026). Data at figshare 32975921, 482 BSE-SEM tile/mask pairs at 22.3 nm/px.

Wrong material, so not a benchmark. But it **independently reports modest Dice (0.580) on
narrow cracks, blames one-to-two-pixel boundary placement, and pivots to area fraction,
width and tortuosity as the reported quantities.** That is this manuscript's own argument
arriving from another field, in the same year. Read it before claiming the framing.

Separately, four searches for a materials-domain paper applying Maier-Hein-style metric
critique returned **zero**. But the idea is owned — Olofsson et al. 2014 in remote sensing,
already cited here. State the contribution as **transfer with a worked measurement**, not
invention.

## 4. Target journals — verified metrics

2025 JCR, released June 2026.

| journal | 2025 JIF | JCR rank | speed | why |
|---|---|---|---|---|
| **Engineering Failure Analysis** | **7.0** | **1/37** Mat. Sci. Characterization & Testing; 13/184 Eng. Mechanical | ~5.6 mo review; rated "easy" | highest metrics of the set, in exactly the right category. Verified to publish standalone **training-free** image-measurement method papers |
| **Materials Characterization** | **6.2** | **3/37** same category; 13/97 Metallurgy | **8 days to first decision**, 96 days to acceptance | the topical home. APC USD 3,300, or free by the subscription route |
| **Measurement Science and Technology** | 3.7 | Q1 Eng. Multidisciplinary 40/179; Q2 Instruments | ~4 mo | **the closest precedent exists here** (below) |
| **Measurement** (IMEKO) | — | Q1, SJR 1.145 | — | all of metrology; broader readership |

**The single strongest precedent is at MST:** a March 2025 paper doing SEM measurement
methodology on fatigue cracks in **GH4169 — Inconel 718 under its Chinese designation** —
doi:10.1088/1361-6501/adbc08, with no learned weights. A second 2025 MST paper does in-situ
SEM-DIC crack characterisation on another nickel superalloy. Same modality, same alloy, same
object, same classical approach.

**Recommendation.** Submit to **Engineering Failure Analysis** or **Materials
Characterization** — EFA for the metrics and category rank, MatChar for the eight-day first
decision and the topical readership. Hold **MST** as the second venue: if a reviewer objects
that this is a measurement argument rather than a materials result, at MST that is the point
rather than the objection, and the GH4169 precedent is already there.

Journal of Microscopy is the best topical fit for the metric argument and is **Q3** by SJR,
so it fails the stated requirement. Scientific Data takes only Data Descriptors and Articles
— relevant only if the lab corpus is released.
