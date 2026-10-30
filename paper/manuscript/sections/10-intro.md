## 1  Introduction

Quantitative microscopy links microstructural observations to material condition and
processing history. Crack area is one useful descriptor because it summarises the fraction
of an observed field occupied by annotated cracking. Extracting this quantity from scanning
electron microscopy (SEM) images requires a consistent definition of the foreground and a
documented relationship between image processing and the final measurement. Recent work on
microstructure inference and microscopy-specific representation learning demonstrates the
growing role of automated image analysis in materials characterisation [1,2].

A deterministic detector offers a directly inspectable route from image intensity to a
binary mask. This is attractive when the study concerns a defined material and imaging
regime and when investigators wish to examine the intermediate processing stages.
Background correction can separate local contrast from slower variations in illumination,
while multiscale processing can accommodate structures with different apparent widths.
Morphological and component-based operations then convert the candidate response into the
mask used for area measurement.

The evaluation endpoint must match the scientific quantity of interest. Image-analysis
validation frameworks distinguish task-specific measurements from general pixel
classification scores [3,4]. Area estimation likewise has its own accounting requirements
[5]. In the present study, crack area fraction refers to the proportion of pixels in a
two-dimensional SEM field. It is distinct from a direct measurement of crack volume or a
stereological volume-fraction estimate [6].

**Related work.** Reporting a segmentation in the units of the downstream measurement
rather than as an overlap score is established practice outside materials science: in
land-cover accuracy assessment, Olofsson et al. set out the error matrix in units of area
proportion together with a bias-adjusted area estimator [5]. Within materials microscopy the
same instinct appears in several recent forms. Work on domain-informed segmentation targets
argues that classical methods retain an advantage because domain knowledge such as a known
phase volume fraction can be imposed explicitly, and evaluates volume-fraction alignment
rather than overlap [14]. Segment-anything-based models for material micrographs have added
boundary-sensitive scores for the same reason [15]. A 2026 analysis of architecture choice
in materials segmentation warns that segmentation errors propagate undetected into porosity
fractions and grain-size distributions [16].

Classical, threshold-based crack-area measurement in SEM has direct precedent: Vidal et al.
binarise SEM images of chromium electrodeposits with a histogram threshold chosen by a
Laplacian-of-Gaussian criterion and report the cracked area [17], and unsupervised
segmentation has recently been used for quantitative fractography of quasi-cleavage
fractures [21]. Deterministic geometric quantification of two-dimensional SEM fracture
morphology across metallic materials has also been reported [20], and classical
measurement methodology for SEM has been applied to microscale fatigue crack propagation
through moire-based distortion correction [22]. Crack quantification in a
different material system has independently reported modest overlap scores on narrow cracks,
attributed them to one-to-two-pixel boundary placement, and reported area fraction, width
and tortuosity as the primary quantities [18]; the present study reaches the same position
from a different direction. A counterpoint worth stating is that non-learned segmentation
has been reported to struggle on rough fracture surfaces precisely because a manual
intensity threshold varies across features [19], which is the difficulty the background
correction and multiscale stages of Section 2.2 exist to address.

The present study claims no novelty for the framing; its contribution is the measurement,
made in those units, for one deterministic detector on one alloy, together with the ways the
conventional scores mislead about it.

We examine the reported behaviour of a multiscale darkness detector on Inconel 718
whole-field images. The analysis centres on aggregate area agreement at a selected operating
setting, the corresponding background specificity, and a descriptive comparison with
classical image-processing methods. Two sections place the selected setting against the full
sweep and against the range the area endpoint can resolve, and a third carries the detector
to a second imaging modality. That third section reports the transfer under two aggregations
rather than one, because a figure pooled over pixels and the mean over frames disagree about
it, and it closes by giving precision, recall and F1 for both of this laboratory's own
collections beside the score a geometrically correct crack trace earns against their
annotations.

Figure {fig_workflow} is the whole study in one picture. Two microscopies that form an
image of a crack in entirely different ways enter at the top; one detection rule, with one
set of constants and no retuning, is applied to both; and the same quantity comes out of
each — except that it does not mean the same physical thing on the two sides, which is
where Section 4 begins.

[FIGURE workflow | Two microscopies in, one detection rule, two readings out. (a) a scanning electron field of this laboratory's own corpus, {wf_sem_w} x {wf_sem_h} px at {wf_sem_nm} nm/px, which is {wf_sem_umw} x {wf_sem_umh} micrometres. (b) a transmission X-ray frame, {wf_txm_w} x {wf_txm_h} px at {wf_txm_nm} nm/px, which is {wf_txm_umw} x {wf_txm_umh} micrometres. Each of (a) and (b) is ONE frame divided down the middle: the left half as acquired and the right half with the finished mask drawn on it in blue, so the before and the after are read side by side rather than from opposite corners of the plate. The red box marks the detail shown below, and on (b) it crosses the divider. The three operations in the centre are applied to both frames with the same constants and nothing between the two arms is retuned: flatten, a multiscale background estimate at seven scales from sigma 5 to 320 px, subtracted; propose, keep every pixel darker than its frame's median by more than {mk_best} scaled median absolute deviations at any of those scales, or darker than an absolute floor of 10 of 255; and clean, fill holes, remove isolated pixels and keep connected regions of at least 40 px. Table 1 lists them. (c) and (d) the SEM detail before and after detection; (e) and (f) the TXM detail likewise. Each detail window is centred, by the same rule for both arms, on the largest marked region its frame contains. The rule marks {wf_sem_marked}% of the SEM frame and {wf_txm_marked}% of the TXM frame, and those two numbers do not mean the same thing: on a polished section the marked area is a trace where the crack meets the surface, and in transmission it is the area of a shadow cast through the whole specimen thickness, which is the subject of Figure {fig_modality}. Section 2.2 states how every micrograph panel in this paper is displayed. The two pixel sizes are NOT equally well founded: the SEM value is read from the instrument databar, the TXM value from operator-supplied mosaic geometry (Section 2.5). Section 4.3 gives what the carried-over rule scores on the TXM collection, which is substantially worse than what it scores on SEM.]

Figure {fig_modality} is the reason the difference matters. Scanning electron microscopy
records a signal that leaves a shallow volume beneath a polished surface, so a pixel reports
the specimen in one plane; transmission X-ray microscopy records a beam that has crossed the
whole specimen, so a pixel reports everything along one line of sight. An area fraction
measured in the first is the area of a trace on a section; the same number measured in the
second is the area of a shadow cast through the thickness. The panel beside those two
schematics gives the consequence that governs every result in this paper: on the axis the
detector actually thresholds, the crack a human painted sits below the operating point on
{fig_modality_below} of the {fig_modality_n} annotated frames of the two collections.

[FIGURE modality | How each microscopy forms an image of a crack, and how much of the crack the detector's criterion can reach. (a) is a SCHEMATIC, drawn by hand and not to scale: one block of material, one crack, and both instruments. The electron beam arrives at the polished top face and the signal has to escape back out of it, so what that instrument records is the line where the crack cuts that face, drawn in blue. The X-ray beam crosses the whole thickness to a detector behind, so what it records is the crack's silhouette along the beam, drawn in orange on the detector. The two measurands are different properties of the same crack. In practice the two are also different specimen preparations -- a polished section and a transmission specimen -- and they are drawn on one block here only so that the two measurands can be compared at a glance. (b) and (c) are real micrographs of the two fields in Figure {fig_workflow}, both at a matched {fig_modality_fov} micrometre field of view, so the two appearances can be compared without converting pixel sizes. (d) per frame, the median over the operator's painted crack pixels of the largest MAD multiplier at which the deployed multiscale darkness union would still propose that pixel; one point per frame, the bar at the median, the axis logarithmic because one SEM frame sits at 52, and the red line at the operating point k = {om_k}. A frame below that line is one whose median annotated crack pixel the relative test cannot propose at any radius. The reconstruction of the real proposal mask from this axis is checked pixel for pixel against the installed detector on every frame and agrees to within {mc_recon} pixel. No mechanism is offered for the SIGN of the TXM contrast: a crack reads darker than the painted not-crack on most TXM frames too, and the radiometric convention of the stored arrays is not recorded in any of the three repositories.]
