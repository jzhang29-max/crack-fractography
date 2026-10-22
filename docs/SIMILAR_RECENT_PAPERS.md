# Recent papers doing what this paper does

Searched 2026-10-22, **every identifier verified against the Crossref or DataCite registry
on the same day** and confirmed to resolve to the work named. Grouped by how they relate to
this work, not by date.

Three DOIs in the first version of this document were wrong, and the correction is recorded
here rather than quietly applied: two of them were plausible-looking strings constructed
from a journal name and year that resolved to real but unrelated papers (a magnesium-alloy
thermal-conductivity paper and a plasma-electrolytic-oxidation paper), and one did not
resolve at all. A fabricated DOI that lands on a real paper is worse than one that 404s,
because nothing alerts the reader. Claims about *content* below still rest on abstracts and
search results rather than full texts read in the original; identifiers and authorship are
now verified.

## A. The closest relatives — same argument, different field or material

**1. Tegetmeyer-Kleine et al., arXiv:2608.27162** (also circulating as "Multi-class crack
mapping in NMC811 cathodes with frozen DINOv3 features", Nature Computational Science 2026).
Data: figshare 32975921, 482 BSE-SEM tile/mask pairs at 22.3 nm/px.
**This is the paper to read first.** Wrong material — NMC811 is an oxide cathode — but it
independently reports modest Dice (0.580) on narrow cracks, attributes the shortfall to
one-to-two-pixel boundary placement, and **pivots to area fraction, width and tortuosity as
the reported quantities**. That is your argument, arriving from battery science, in the same
year. If a reviewer asks whether the framing is novel, this is the paper they will find.

**2. Prakash et al., "ExpertSegmentation: Segmentation for microscopy with domain-informed
targets via custom loss."** *Acta Materialia*, 2025, **doi:10.1016/j.actamat.2025.120993**
(also SSRN 10.2139/ssrn.5098869). Argues that classical methods retain an advantage *because*
domain knowledge such as a known phase volume fraction can be imposed explicitly, and
evaluates volume-fraction alignment (KL divergence) rather than overlap. The nearest thing to
your thesis inside materials science.

**3. Olofsson, Foody, Herold, Stehman, Woodcock & Wulder (2014),** *Remote Sensing of
Environment* 148:42-57, doi:10.1016/j.rse.2014.02.015. Already cited in your draft and worth
keeping prominent: the error matrix in units of area proportion plus a bias-adjusted area
estimator. The idea is a decade old outside materials; your contribution is the transfer with
a worked measurement, and saying so protects the paper.

## B. Classical, threshold-based crack-area measurement in SEM — your methodological ancestors

**4. Vidal et al., "Analysis of SEM digital images to quantify crack network pattern area
in chromium electrodeposits."** *Surface and Coatings Technology*, **2016**,
**doi:10.1016/j.surfcoat.2015.11.049**. The closest methodological ancestor found: histogram-threshold binarisation of SEM crack networks, with a
Laplacian-of-Gaussian second-derivative step to choose the threshold, reporting cracked area
and arguing it is more objective than visual assessment. Deterministic, no training, SEM,
crack area. Cite it — a reviewer who knows it and finds it uncited will not be generous.

**5. WITHDRAWN.** A *Journal of Microscopy* 2016 paper on binarisation, Otsu and Laplacian
filtering reporting crack length per unit area appeared in the search results, but no
Crossref record matching it could be found and no identifier could be established. It is
removed rather than cited from a search snippet.

## C. Why a deterministic threshold is defensible on fracture surfaces

**6. Ngo et al., "Image-Based Fracture Surface Defect Characterization Methods for
Additively Manufactured Ti-6Al-4V Tested in Fatigue."** *JOM*, 2024,
doi:10.1007/s11837-024-06655-7 — **verified**. Reports that
non-learned segmentation struggles on rough fracture surfaces because manual intensity
thresholds vary across features. That is exactly the difficulty your background-correction
and multiscale stages exist to address, and it is a citable statement of the problem from
someone who is not you.

**7. Standardization and quantification of backscattered electron imaging in SEM.** Wang,
Chiu, Wu, Chen, Chang & Chang, *Ultramicroscopy* 262 (Aug 2024) 113982,
doi:10.1016/j.ultramic.2024.113982. Measurement standardisation in SEM rather than crack
segmentation, but it is the template for "make the instrument's output quantitative and say
how", published in a venue you are considering.

## D. The learned baseline your paper is implicitly compared against

**8. Durmaz et al. (2021),** *Nature Communications* 12:6272 — already cited. Multi-phase
steel segmentation, and it reports the downstream morphological quantity beside the
segmentation score, and notes that phase-boundary localisation limits per-object morphology.

**9. Stuckner, Harder & Smith (2022),** *npj Computational Materials* 8:200 — already cited.
The MicroNet pretrained encoders; also the source of the only maintained SEM crack-mask
benchmark (the EBC coating subsets).

**10. Medghalchi et al. (2024),** *Materials & Design* 243:113031, data at Zenodo 11224127.
Panoramic SEM of DP800 with ferrite/martensite/damage masks. Cite as a near neighbour, and
know that its "damage" class is **voids, not cracks** — measured: median aspect ratio 1.74,
median solidity 0.92, every labelled site a rounded cavity.

## E. Metric critique — the line your paper joins

**11. Maier-Hein, Reinke, Godau et al. (2024),** doi:10.1038/s41592-023-02151-z —
verified. *Nature Methods* 21:195-212, "Metrics
reloaded" — already cited.
**12. Reinke, Tizabi, Baumgartner et al. (2024),** *Nature Methods* 21:182-194,
doi:10.1038/s41592-023-02150-0 — verified. "Understanding metric-related pitfalls" —
already cited.

**The gap, confirmed by four independent searches: no materials-domain paper applies this
critique to a materials measurement.** The general literature supports the mechanism — Dice
and IoU are monotonically related so they never disagree about a ranking, and a uniform
boundary offset leaves Dice near 0.95 while systematically mis-measuring the object — but the
argument has not been made for a micrograph area fraction. Two 2026 materials papers come
close without making it: a SAM-based micrograph model adds Boundary F1 "to more accurately
reflect the fitting capability for details such as grain boundaries", and an architecture
analysis (arXiv:2602.04154) warns that segmentation errors "propagate undetected into flawed
porosity fractions, grain size distributions, or corrosion rates". Neither reports the
measurement error itself.

## F. Precedent in your two target venues

**13. CORRECTED.** The MST paper at doi:10.1088/1361-6501/adbc08 is real but was
mischaracterised in the first version of this document. It is **Chen, Zhang, Xue, Li, Xie &
Zhang, "Distortion correction method for SEM images based on sampling moire patterns and its
application to characterization of the microscale fatigue crack propagation"**, *Measurement
Science and Technology*, 20 March 2025. It *is* classical SEM measurement methodology with
no learned weights, applied to microscale fatigue crack propagation, and it *is* in one of
your target venues — so the venue argument holds. But it is a distortion-correction method,
not a crack-area measurement, and **nothing in its title or record identifies GH4169**. Do
not repeat the "same alloy" claim; it was the search agent's, not the paper's.

**14. Jiao et al., "Curvature-driven quantification of 2D SEM fracture morphology across
metallic materials."** *Materials Characterization*, 2026, doi:10.1016/j.matchar.2026.116319
— **verified**. Deterministic geometric quantification of 2D SEM fracture morphology. Same
genre, same modality, this year, in your first-choice venue.

**15. Zheng et al., "Quantitative fractography of quasi-cleavage fractures via unsupervised
image segmentation."** *Engineering Failure Analysis*, 2026,
doi:10.1016/j.engfailanal.2026.111235 — **verified**, and a better fit than first described:
*unsupervised* segmentation for quantitative fractography is a standalone training-free
image-measurement method paper in a Q1 venue. Strong evidence that EFA takes this article
type, and worth citing in the manuscript itself.

---

## What to do with these

Four of them change the paper rather than just its reference list:

* **[1] and [2]** mean the framing is not novel and the draft should say so explicitly. It
  already concedes novelty in Section 1; name these two when it does.
* **[4]** is a direct methodological ancestor in SEM crack area and was uncited. It is now
  reference [17] in the manuscript. [5] was withdrawn: no record for it could be found.
* **[14] and [15]** — the Jiao and Zheng papers — are both in target venues, both 2026, and
  both now cited in the manuscript as [20] and [21].
* **[6]** gives you an external statement of why a naive global threshold fails on fracture
  surfaces, which is the justification for your background-correction stage.
* **[13]** still supports the venue choice, in its corrected form: MST publishes classical
  SEM measurement methodology applied to fatigue cracks. It does not support a "same alloy"
  claim.
