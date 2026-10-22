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
proportion together with a bias-adjusted area estimator [5]. Within materials microscopy
the same instinct appears in several recent forms. Work on domain-informed segmentation
targets argues that classical methods retain an advantage because domain knowledge such as
a known phase volume fraction can be imposed explicitly, and evaluates volume-fraction
alignment rather than overlap [14]. Segment-anything-based models for material micrographs
have added boundary-sensitive scores for the same reason [15]. A 2026 analysis of
architecture choice in materials segmentation warns that segmentation errors propagate
undetected into porosity fractions and grain-size distributions [16]. Classical,
threshold-based crack-area measurement in SEM has direct precedent: histogram-threshold
binarisation of crack networks in chromium electrodeposits [17] and a filter-and-threshold
pipeline reporting crack length per unit area [18]. Crack quantification in a different
material system has independently reported modest overlap scores on narrow cracks,
attributed them to one-to-two-pixel boundary placement, and reported area fraction and width
as the primary quantities [19]. The present study claims no novelty for the framing; its
contribution is the measurement, made in those units, for one deterministic detector on one
alloy, together with the ways the conventional scores mislead about it.

We examine the reported behaviour of a multiscale darkness detector on Inconel 718
whole-field images. The analysis centres on aggregate area agreement at a selected operating
setting, the corresponding background specificity, and a descriptive comparison with
classical image-processing methods. Representative microscopy panels and a processing
diagram connect the numerical results to the evaluated workflow. Two sections added in this
revision place the selected setting against the full sweep and against the range the area
endpoint can resolve, and a third carries the detector to a second imaging modality.
