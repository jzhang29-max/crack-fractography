## 6  Limitations and future improvements

### 6.1  Spatial interpretation and measurement scope

Agreement in aggregate area can arise when false-positive and false-negative areas
cancel. It does not establish accurate crack localisation or foreground overlap, and
neither does pixel accuracy: over every refereed frame of each arm the detectors
score {sa_sem_acc}% and {sa_txm_acc}% where a
prediction that marks no crack at all scores {sa_sem_bg}% and {sa_txm_bg}%. Complete
per-image precision, recall, Dice, intersection over union and boundary measures are
required to assess localisation [3,4]. Section 3.1 reports the first three, averaged over
frames, on both of this laboratory's collections, together with the two reasons they must
be read with care — on both collections the annotation is a stroke far wider than the
feature, so an overlap score there pays for covering the stroke, and neither collection
adjudicates the whole frame, so a precision computed on it is a bracket rather than a
value.

**A conventional overlap ranking can be climbed without detecting anything**, because
widening a mask raises the score whether or not the mask is better placed. That is not an
inference here but the measurement of Section 3.1: a reconstruction of each frame's own
annotation that is exactly right about where every crack runs scores {om_sem_cf1} and
{om_txm_cf1}, while the detector scores {om_sem_f1} and {om_txm_f1} against the same
references. Every overlap score in this manuscript is therefore reported beside what that
correct trace earns, and a reader should apply the same scepticism to any ranking by
area: it ranks total marked area and nothing more.

Diagnostic observations further limit the interpretation of the darkness criterion.
Reported in Figure {fig_modality}(b), the median frame has {mc_sem_prop}% of its annotated
crack proposed in SEM and {mc_txm_prop}% in TXM, with the median annotated pixel sitting
below the operating threshold on {mc_sem_below} of {mc_sem_n} and {mc_txm_below} of
{mc_txm_n} frames. The unreached annotated regions are not dark: the record behind Figure
{fig_counting} puts the crack the SEM detector missed at a median displayed grey of
{cnt_sem_under_grey} where the crack it found sits at {cnt_sem_agree_grey}, which is
consistent with a contrast-polarity limitation rather than with a threshold set too high.
Panels of the
most heavily cracked fields indicate that these regions are the illuminated interior surface
of an open crack. Expansion experiments increased marked area and did not establish a
validated correction. A future detector could combine dark-core evidence with independently
validated contextual or polarity-aware features; such changes require new experiments and
joint assessment of area bias and spatial overlap.

**The annotation geometry of this laboratory's own collections is itself a limitation, and
it is now measured rather than asserted.** On the {pr_sem_n} SEM frames and {pr_txm_n} TXM
frames that carry both verdicts, the share of annotated pixels lying more than {pr_px} px
inside the annotation has a median of {pr_sem_med}% and {pr_txm_med}% and a maximum of
{pr_sem_max}% and {pr_txm_max}%; {pr_sem_above} of {pr_sem_n} SEM frames and
{pr_txm_above} of {pr_txm_n} TXM frames exceed 25%. A stroke that follows a crack scores
near zero on this statistic, and no TXM frame of the restricted collection reaches
exactly zero; the eight that did are in groups the paper no longer reports. The frames above 25% carry a
reference that is closer to a blocked-out area than to a traced line, so on those frames
neither an overlap score nor a crack width can be read from the annotation, and the
quantity a detector is being asked to reproduce is not the crack but the annotator's
judgement about where the crack region lies. This is a property of the references and
cannot be corrected by any change to the detector; correcting it requires re-annotation
against a stated stroke rule, which Section 6.3 lists among what a new benchmark needs.

### 6.2  Scale and units

Pixel size is known for both collections evaluated here, so every micrograph panel in
this paper carries a scale bar and the method figures are drawn from the same frames the
results are computed on. On the electron side 7 of the 23 b2 and b3 frames carry a
recoverable databar, at {wf_sem_nm} nm/px on the one illustrated.

The TXM panels in Section 4 do carry scale bars, from a pixel size of 29.24 nm/px that is
derived from mosaic geometry rather than read from instrument metadata. Those bars, and any
physical length derived from those frames, scale with the acquisition geometry if it is
corrected.

### 6.3  Validation and reproducibility

Neither collection evaluated here has a second annotator, so no inter-annotator
agreement can be computed and neither reference can be distinguished from one annotator's
judgement. A new benchmark should fix the tuning objective within training folds, preserve
complete per-image results, report uncertainty for the primary endpoint, and document the
annotation rules — including a stated stroke width, since Section 6.1 shows that the
annotations available here vary between a traced line and a filled region and that the
difference changes every overlap score computed against them.

The implementation requires a reproducible specification of the MAD normalisation, the
logical combination of the intensity gates, image and mask resizing, the morphological
footprint and the software version. The reported 13-pixel opening does not establish whether
that value denotes a radius, diameter or another footprint convention.

The current conclusion is limited to the two collections evaluated here, with the
cross-modality result of Section 4 scoped as stated there. Generic defect
labels from another material collection, including MetalDAM [13], are not interchangeable
with crack annotations. Independent material-specific validation is needed before
interpreting image area as a physical three-dimensional defect quantity.

## Data and code availability

The source study identifies the dataset record in Ref. [7]. The TXM frames of Section 4 are
not part of a public release, and the acquisition parameters required to interpret them
physically are not recorded with the data. No archival DOI or commit hash is quoted for the
analysis code in this revision; both are required before submission, and until they exist a
reader cannot independently reproduce the numbers reported here.
