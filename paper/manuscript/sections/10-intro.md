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

[FIGURE workflow | Two microscopies in, one detection rule, two readings out. (a) a scanning electron field of this laboratory's own corpus, 6144 x 4096 px at 51.883 nm/px. (b) a transmission X-ray frame, 2351 x 1699 px at 29.24 nm/px. The red box on each marks the detail below it. The three numbered operations in the centre are applied to both frames with the same constants; nothing between the two arms is retuned. (c) and (d) the SEM detail before and after detection; (e) and (f) the TXM detail likewise, with the mask in blue. Each detail window is centred, by the same rule for both arms, on the largest marked region its frame contains. Every panel is a real intermediate array from the shipped code and is contrast-stretched for display between its own 2nd and 98th percentiles, identically in both arms; the detector ran on the unstretched frames. The two pixel sizes are NOT equally well founded: the SEM value is read from the instrument databar and the TXM value is derived from operator-supplied mosaic geometry (Section 2.5). Section 4.3 gives what the carried-over rule scores on the TXM collection, which is substantially worse than what it scores on SEM.]

Figure {fig_modality} is the reason the difference matters. Scanning electron microscopy
records a signal that leaves a shallow volume beneath a polished surface, so a pixel reports
the specimen in one plane; transmission X-ray microscopy records a beam that has crossed the
whole specimen, so a pixel reports everything along one line of sight. An area fraction
measured in the first is the area of a trace on a section; the same number measured in the
second is the area of a shadow cast through the thickness. The panel beside those two
schematics gives the consequence that governs every result in this paper: on the axis the
detector actually thresholds, the crack a human painted sits below the operating point on
{fig_modality_below} of the {fig_modality_n} annotated frames of the two collections.

[FIGURE modality | How each microscopy forms an image of a crack, and how much of the crack the detector's criterion can reach. (a) and (b) are SCHEMATICS, drawn by hand and not to scale. In (a) the signal escapes from a shallow interaction volume just under the polished surface and has to leave the specimen to be counted, so a pixel reports one plane and a crack is seen where it cuts that plane. In (b) the beam crosses the whole specimen and is recorded behind it, so a pixel reports everything along one line of sight. (c) and (d) are real micrographs of the two fields in Figure {fig_workflow} at a matched 15 micrometre field of view, so the two appearances can be compared without converting pixel sizes. (e) per frame, the median over the operator's painted crack pixels of the largest MAD multiplier at which the deployed multiscale darkness union would still propose that pixel; one point per frame, bar at the median, and the line at the operating point k = {om_k}. The reconstruction of the real proposal mask from this axis is checked pixel for pixel against the installed detector on every frame and agrees to within one pixel. No mechanism is offered for the SIGN of the TXM contrast: a crack reads darker than the painted not-crack on most TXM frames too, and the radiometric convention of the stored arrays is not recorded in any of the three repositories.]
