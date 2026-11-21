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

We examine the behaviour of the two detectors this laboratory ships, each on the
microscopy it was built for: a multiscale darkness rule on the electron frames and a
trained per-pixel ensemble on the transmission frames. The analysis centres on precision,
recall and F1 over the crack class, each reported beside the score a geometrically correct
three-pixel trace of the same annotation earns against that annotation, and each reported
as a bracket rather than a value, because neither collection adjudicates the whole frame.
A further section carries the electron detector to the second modality unchanged and
reports the transfer under two aggregations rather than one, because a figure pooled over
pixels and the mean over frames disagree about it. A last section locates where the
transfer is lost, on the axis the detector itself thresholds rather than through a score.

[FIGURE flow | Both detectors end to end, one row per stage with the two arms side by side, so the stage is named once and the two can be compared where they differ. The operation each arm applies is written over the panel it produced; every pixel a cleaning step removes is drawn in orange on the panel it comes off, and a {flow_mag}x window over the right-hand end of that panel shows one of them close up, so what the step removed can be seen rather than asserted; no pixel in any panel is dilated. The electron arm is a darkness rule followed by a trained region classifier -- a multiscale background estimate subtracted at seven radii, a robust darkness cut, morphological cleaning, and then an eight-feature logistic model that decides which surviving regions are kept. The transmission arm is a trained per-pixel ensemble: 17 hand-built image channels and a frozen SAM ViT-H embedding, the mean of two fitted members cut at 0.60, then pruned and narrowed to the measured width. The two arms do not share a detector and the plate does not pretend they do. Table {tbl_settings} lists the constants and Figure {fig_parameters} reports how each was arrived at.]

Figure {fig_modality} is the reason the difference matters. Scanning electron microscopy
records a signal that leaves a shallow volume beneath a polished surface, so a pixel reports
the specimen in one plane; transmission X-ray microscopy records a beam that has crossed the
whole specimen, so a pixel reports everything along one line of sight. An area fraction
measured in the first is the area of a trace on a section; the same number measured in the
second is the area of a shadow cast through the thickness. The panel beside those two
schematics gives the consequence that governs every result in this paper: on the axis the
detector actually thresholds, the crack a human painted sits below the operating point on
{fig_modality_below} of the {fig_modality_n} annotated frames of the two collections.

[FIGURE modality | Where the two pictures come from, and how each instrument produces one. One 316L dogbone pulled to failure in the micro-tensile stage, one {fig_modality_fov} micrometre region taken from the middle of its gauge section, and beneath that region the geometry of each arm: a source, the beam, the foil and a detector, four elements apiece. **The two geometries differ in one respect and that is the whole of the difference between the measurands.** On the electron arm the beam lands on the polished face and an off-axis detector collects the signal that escapes back out of it, so what is recorded is the crack where it cuts the surface. On the transmission arm the beam crosses all {fig_modality_t} micrometres of the foil to a detector behind it, so what is recorded is the crack through the whole depth. Neither is wrong; they are two different quantities, the two arms' numbers are not expected to agree, and nothing in this work pools them. **The two panels are not schematic.** They are the real fields of Figure {fig_flow}, both at a matched {fig_modality_fov} micrometre field of view so the two appearances can be compared without converting pixel sizes, and each carries its own scale bar; the specimen and the two geometries above them are schematic and not to scale, and the foil thickness is the only real dimension on either. **A measurement that was plotted here has been withdrawn from the plate and is reported in the figure's caption file instead**: per frame, the median over the operator's painted crack pixels of the largest MAD multiplier at which the deployed multiscale darkness union would still propose that pixel. On {fig_modality_n} frames of the two collections that median sits below the operating point k = {om_k} on {fig_modality_below}, which is to say the relative test cannot propose their median annotated crack pixel at any radius. It is not drawn because the two collections' NOT-crack verdicts were painted to different conventions -- adversarially in one, as broad context strokes in the other -- so a panel inviting the reader to compare the two axes would have been making the figure's main claim out of an artefact of annotation practice. The reconstruction of the real proposal mask from that axis is checked pixel for pixel against the installed detector on every frame and agrees to within {mc_recon} pixel. No mechanism is offered for the SIGN of the TXM contrast: a crack reads darker than the painted not-crack on most TXM frames too, and the radiometric convention of the stored arrays is not recorded in any of the three repositories.]
