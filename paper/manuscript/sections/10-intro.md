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

[FIGURE workflow | Two microscopies in, one detection rule, one measurement out. The rows are the two microscopies and the columns are the four stages, applied to both with the same constants and nothing between the arms retuned; Table {tbl_settings} lists the constants and Figure {fig_parameters} reports how each was arrived at. (a) a scanning electron field of this laboratory's own corpus, {wf_sem_w} x {wf_sem_h} px at {wf_sem_nm} nm/px, which is {wf_sem_umw} x {wf_sem_umh} micrometres, and (e) a transmission X-ray frame, {wf_txm_w} x {wf_txm_h} px at {wf_txm_nm} nm/px, which is {wf_txm_umw} x {wf_txm_umh} micrometres. Each is ONE frame divided down the middle, the left half as acquired and the right half with the finished mask drawn on it in blue, so the before and the after are read side by side rather than from opposite corners of the plate; the red box marks the detail, and on (e) it crosses the divider. (b) and (c) the SEM detail before and after detection, over a {wf_sem_detail} micrometre window; (f) and (g) the TXM detail likewise, over {wf_txm_detail} micrometres. Each detail window is the position holding the most mask-BOUNDARY pixels, found exactly by a box sum rather than chosen by eye. A window chosen for the most MARKED pixels is solid mask wherever the crack is wider than the window, and a panel of flat colour says nothing about where the detector put its edge; the boundary of a region more than 15% of whose own outline lies on the frame border is discounted, because such a region is the limit of the field rather than a decision. Section 2.3 gives both measurements. One display range is taken from each frame and applied to the field and to the detail cut from it, so the detail is the field magnified and not a differently rendered picture; Section 2.2 states the convention, which is the median of the frame plus and minus three robust standard deviations rather than a percentile pair: where a frame's dark tail reaches the low percentile, a percentile stretch washes the matrix out. (d) and (h) are what the application actually emits: every marked region of the WHOLE frame measured by the shipped measurement functions, its network length against its mean width, both axes logarithmic and shared by the two rows, with the marker area proportional to the square root of the region's own area and a red ring on the region the detail panels are centred on. The weighting matters: this SEM frame holds {wf_sem_regions} marked regions of which the largest holds {wf_sem_largest}% of the marked area, against {wf_txm_regions} and {wf_txm_largest}% on the TXM frame, so a plot giving every region the same dot would describe the two as the same kind of object. The rule marks {wf_sem_marked}% of the SEM frame and {wf_txm_marked}% of the TXM frame, and those two numbers do not mean the same thing: on a polished section the marked area is a trace where the crack meets the surface, and in transmission it is the area of a shadow cast through the whole specimen thickness, which is the subject of Figure {fig_modality}. **This SEM field is the median of its collection, not its best.** Of the eleven b2 frames carrying a hand correction, only two were saved uncropped and so have a recoverable pixel size; a figure needs a scale bar, so the illustrated field comes from those two, and of them this is the one whose F1 is closest to the collection's median -- 0.683 against a median of 0.683, rank 6 of 11. The other scores 0.986 and is the best frame in the collection, which is what an earlier version of this figure showed. The two pixel sizes are NOT equally well founded: the SEM value is measured from the scale bar in the instrument databar that survives in the uncropped original and cross-checked against the printed field width, the TXM value derived from operator-supplied mosaic geometry (Section 2.5). Section 4.3 gives what the carried-over rule scores on the TXM collection.]

Figure {fig_modality} is the reason the difference matters. Scanning electron microscopy
records a signal that leaves a shallow volume beneath a polished surface, so a pixel reports
the specimen in one plane; transmission X-ray microscopy records a beam that has crossed the
whole specimen, so a pixel reports everything along one line of sight. An area fraction
measured in the first is the area of a trace on a section; the same number measured in the
second is the area of a shadow cast through the thickness. The panel beside those two
schematics gives the consequence that governs every result in this paper: on the axis the
detector actually thresholds, the crack a human painted sits below the operating point on
{fig_modality_below} of the {fig_modality_n} annotated frames of the two collections.

[FIGURE modality | How each microscopy forms an image of a crack, and how much of the crack the detector's criterion can reach. (a) is a SCHEMATIC, drawn by hand and not to scale: one block of material, one crack, and both instruments. The electron beam arrives at the polished top face and the signal has to escape back out of it, so what that instrument records is the line where the crack cuts that face, drawn in blue; the X-ray beam crosses the whole thickness to a detector behind, so what it records is the crack's silhouette along the beam, drawn in orange on the detector. The two measurands are different properties of the same crack. In practice the two are also different specimen preparations -- a polished section and a transmission specimen -- and they are drawn on one block here only so that the two measurands can be compared at a glance. **The two images mounted on the schematic are not schematic.** They are the real fields of Figure {fig_workflow}, each placed at the instrument that produces it, both at a matched {fig_modality_fov} micrometre field of view so the two appearances can be compared without converting pixel sizes, and each carrying its own scale bar. (b) per frame, the median over the operator's painted crack pixels of the largest MAD multiplier at which the deployed multiscale darkness union would still propose that pixel; one point per frame, the bar at the group median, the axis logarithmic because one SEM frame sits above 50, and the red line at the operating point k = {om_k}. A frame below that line is one whose median annotated crack pixel the relative test cannot propose at any radius. (c) the same per-frame quantity against the share of that frame's painted crack the deployed rule actually proposes, both collections on one pair of axes, which turns (b) from a diagnostic into a consequence. The reconstruction of the real proposal mask from this axis is checked pixel for pixel against the installed detector on every frame and agrees to within {mc_recon} pixel. No mechanism is offered for the SIGN of the TXM contrast: a crack reads darker than the painted not-crack on most TXM frames too, and the radiometric convention of the stored arrays is not recorded in any of the three repositories.]
