# Recent papers doing what this paper does

Searched 2026-10-22. Grouped by how they relate to this work, not by date. **Flagged
throughout: the bibliographic details below come from search results, not from full texts
read in the original. Confirm each before citing.**

## A. The closest relatives — same argument, different field or material

**1. Tegetmeyer-Kleine et al., arXiv:2608.27162** (also circulating as "Multi-class crack
mapping in NMC811 cathodes with frozen DINOv3 features", Nature Computational Science 2026).
Data: figshare 32975921, 482 BSE-SEM tile/mask pairs at 22.3 nm/px.
**This is the paper to read first.** Wrong material — NMC811 is an oxide cathode — but it
independently reports modest Dice (0.580) on narrow cracks, attributes the shortfall to
one-to-two-pixel boundary placement, and **pivots to area fraction, width and tortuosity as
the reported quantities**. That is your argument, arriving from battery science, in the same
year. If a reviewer asks whether the framing is novel, this is the paper they will find.

**2. ExpertSegmentation: segmentation for microscopy with domain-informed targets via custom
loss.** Acta Materialia, 2025. Argues that classical methods retain an advantage *because*
domain knowledge such as a known phase volume fraction can be imposed explicitly, and
evaluates volume-fraction alignment (KL divergence) rather than overlap. The nearest thing to
your thesis inside materials science.

**3. Olofsson, Foody, Herold, Stehman, Woodcock & Wulder (2014),** *Remote Sensing of
Environment* 148:42-57, doi:10.1016/j.rse.2014.02.015. Already cited in your draft and worth
keeping prominent: the error matrix in units of area proportion plus a bias-adjusted area
estimator. The idea is a decade old outside materials; your contribution is the transfer with
a worked measurement, and saying so protects the paper.

## B. Classical, threshold-based crack-area measurement in SEM — your methodological ancestors

**4. Analysis of SEM digital images to quantify crack network pattern area in chromium
electrodeposits.** *Surface and Coatings Technology*, 2015. The closest methodological
ancestor found: histogram-threshold binarisation of SEM crack networks, with a
Laplacian-of-Gaussian second-derivative step to choose the threshold, reporting cracked area
and arguing it is more objective than visual assessment. Deterministic, no training, SEM,
crack area. Cite it — a reviewer who knows it and finds it uncited will not be generous.

**5. Improvement of qualitative analysis of SEM images by computational tools.** *Journal of
Microscopy*, 2016. Binarisation, Otsu, Laplacian filters and reverse binarisation, reporting
crack length, angle and **total crack length per unit area**. Same family, same reasoning,
a decade earlier.

## C. Why a deterministic threshold is defensible on fracture surfaces

**6. Image-based fracture surface defect characterization methods for additively manufactured
Ti-6Al-4V tested in fatigue.** *JOM*, 2024, doi:10.1007/s11837-024-06655-7. Reports that
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

**11. Maier-Hein, Reinke, Godau et al. (2024),** *Nature Methods* 21:195-212, "Metrics
reloaded" — already cited.
**12. Reinke, Tizabi, Baumgartner et al. (2024),** *Nature Methods* 21:182-194, "Understanding
metric-related pitfalls" — already cited.

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

**13.** *Measurement Science and Technology*, March 2025, doi:10.1088/1361-6501/adbc08 — SEM
measurement methodology on fatigue cracks in **GH4169, which is Inconel 718 under its Chinese
designation**, with no learned weights. A second 2025 MST paper does in-situ SEM-DIC crack
characterisation on another nickel superalloy. Same modality, same alloy, same object, same
classical approach: this is the single closest venue precedent found.

**14.** *Materials Characterization* 2026, doi:10.1016/j.matchar.2026.116319 — Jiao,
"Curvature-driven quantification of 2D SEM fracture morphology across metallic materials".
Deterministic geometric quantification of 2D SEM fracture morphology. Same genre, same
modality, this year.

**15.** *Engineering Failure Analysis* 2026, doi:10.1016/j.engfailanal.2026.111235 —
quantitative fractography as a standalone training-free image-measurement method paper.
Evidence that EFA takes this article type.

---

## What to do with these

Four of them change the paper rather than just its reference list:

* **[1] and [2]** mean the framing is not novel and the draft should say so explicitly. It
  already concedes novelty in Section 1; name these two when it does.
* **[4] and [5]** are direct methodological ancestors in SEM crack area and are currently
  uncited. Add them to Section 1.
* **[6]** gives you an external statement of why a naive global threshold fails on fracture
  surfaces, which is the justification for your background-correction stage.
* **[13]** is the strongest single argument for the venue choice.
