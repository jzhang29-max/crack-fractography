## 2  Materials and methods

### 2.1  Image collection and evaluation units

The primary evaluation comprises {in_n} whole-field SEM images of Inconel 718 from the
collection identified in the source study [7]. The images are 1024 x 1024 pixels. Reference
masks define the annotated crack pixels, and the mean reference crack area fraction for the
whole fields is {ag_best_lab}%. Each field serves as an image-level evaluation unit.

The collection also includes {in_crop_n} released crops originating from {in_crop_src}
parent images represented among the whole fields. The present primary endpoint uses the
whole-field collection. The crop set provides related views of the material and its image
framing, and is reported separately wherever it is used.

**A provenance limitation of this collection, disclosed here because it affects how the
reference should be read.** The archive's own class list declares fifteen target classes,
of which the only crack class is a ceramic environmental barrier coating. The Inconel 718
folders used here, including the crack class on which this entire evaluation rests, are
present in the archive but absent from that class list; the undeclared folders and the
Inconel 718 folders are the same set. The masks exist, are pixel-level, and are released
under CC BY, but no annotation protocol, annotator count or class definition accompanies
them. The collection also publishes no pixel size: there is no resolution tag in the image
files, no databar in the fields, and no magnification in the record, and the collection's
subsets originate from different microscopes. **No scale bar can therefore be drawn on any
panel from this collection, and none is shown.** The crack area fraction reported throughout
is a dimensionless ratio of pixel counts and does not depend on a pixel size; physical
lengths cannot be derived from these images and none are reported.

### 2.2  Detector configuration

The evaluated detector processes an 8-bit grayscale image and applies background correction
before identifying dark candidate regions over seven spatial scales. The scales are 5, 10,
20, 40, 80, 160 and 320 pixels. Candidate selection combines a median absolute deviation
(MAD) criterion with an absolute intensity gate.

Mask processing consists of hole filling, morphological opening and connected-component
filtering, with an opening size of 13 pixels and a minimum retained region area of 40
pixels. Components use 8-connectivity. The learned region classifier is disabled in the
scored branch, so the configuration produces its candidate mask without fitting a learned
region-classification model. Table 1 lists the reported settings.

| Component | Reported setting |
|---|---|
| Input representation | 8-bit grayscale SEM image |
| Multiscale processing | 5, 10, 20, 40, 80, 160 and 320 px |
| Selected MAD multiplier | {mk_best} |
| Absolute intensity gate | 10.0 |
| Morphological opening size | 13 px |
| Minimum connected-region area | 40 pixels |
| Connectivity | 8-connected components |
| Learned region classifier | Disabled in the evaluated branch |

**On the number of free parameters.** One constant, the MAD multiplier, is exposed and
swept, and it is the only one given a grid in any comparison reported here. It is not the
only constant. The absolute intensity gate is a second threshold, held fixed rather than
fitted in this study. Behind those sit the seven-rung scale ladder and the two size floors,
also fixed. A reader comparing this against a single-parameter classical filter should know
that the filter carries one constant and this configuration carries a frozen preprocessing
budget.

Figure 1 shows the microscopy example and the intermediate image outputs. Figure 2
summarises the scored branch from grayscale input to area measurement.

[FIGURE pipeline | The detector applied to one Inconel 718 field, 360 x 360 px detail. (a) the field as acquired, 8-bit. (b) after background flattening, a multi-scale estimate at sigma 5 to 320 px subtracted. (c) dark candidates, pixels dark at any of the seven scales after the MAD criterion and the absolute intensity gate. (d) after hole filling, removal of components under 13 px and 8-connected labelling. (e) after removal of regions under 40 px; this is the scored mask. In (c-e) the stage output is shown in blue over the field it was computed from. (f) the scored mask in blue with the reference annotation outlined in black. No scale bar is shown: the source collection publishes no pixel size (Section 2.1).]

[FIGURE workflow | The scored detector workflow. Candidate detection and mask processing produce the predicted crack area fraction. The learned region classifier is disabled. Subsequent region growth and manual correction are outside the evaluated branch.]

### 2.3  Measurement endpoints

Let N denote the number of evaluated image pixels, Nref the reference foreground count and
Npred the predicted foreground count. Reference and predicted crack area fractions,
expressed as percentages of image area, are Ax = 100 Nx / N for x in {ref, pred}.

The predicted-to-reference area ratio is R = Apred / Aref and the net area difference is
dA = Apred - Aref. R = 1 denotes equality of the reported foreground area totals. dA is
expressed in percentage points. The absolute relative aggregate area discrepancy used for
the comparator summary is Earea = 100 |R - 1|, expressed as a percentage of the reference
area. It is computed from the displayed aggregate ratio and is distinct from the mean of
individual relative image errors.

Background specificity describes the fraction of reference background pixels classified as
background. With TN and FP denoting true-negative and false-positive pixels, specificity is
TN / (TN + FP). Aggregate area agreement and background specificity have separate
interpretations from foreground overlap [3,4].

**An all-background reference point accompanies every accuracy figure in this manuscript.**
On an image that is {ag_best_lab}% crack, a prediction that marks nothing scores
{in_empty_acc}% pixel accuracy, so marking a pixel improves accuracy only where more than
half of what is marked is correct. Accuracy quoted without that reference point is not
interpretable at this prevalence, and both numbers are given together throughout.

### 2.4  Comparator and field-level analyses

The displayed comparison includes the multiscale darkness detector, a darkness-or-Sato
union, Sato filtering, Frangi filtering, Meijering filtering, Sauvola thresholding and
percentile thresholding [8-12]. Seven method summaries appear in the source table. Each arm
receives its own parameter by the same leave-one-image-out rule, on the same images, through
the same scoring code.

The selected operating setting is a MAD multiplier of {mk_best}. A paired field-level
comparison contrasts its absolute area error with that of the default setting. The
comparator summaries and field counts are descriptive.

### 2.5  Cross-modality evaluation

To test whether the configuration is specific to this imaging modality, the identical
detector, with the identical constant, was applied to {tx_n} transmission X-ray microscopy
(TXM) frames of austenitic stainless steel spanning four specimen groups. Those frames carry
hand-made correction masks that mark crack and not-crack explicitly and leave the remainder
unreviewed, so only reviewed pixels are scored: {tx_cov}% of all pixels in those frames were
ruled on. The reviewed area holds {tx_crack_px} crack pixels against {tx_notc_px} not-crack
({tx_ratio_pn}:1), so a false positive is priced by the annotation rather than assumed.
Percentages in Section 4 are therefore percentages of the reviewed area, not of the frame.

TXM frames carry a pixel size of 29.24 nm/px, which is **derived from mosaic geometry — a
30 micrometre viewing window at 0.35 tile overlap over a 9 x 5 mosaic — and not read from
instrument metadata.** Scale bars on TXM panels use that value and scale with it if the
acquisition geometry is corrected.
