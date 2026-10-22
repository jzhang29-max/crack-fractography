## 6  Limitations and future improvements

### 6.1  Spatial interpretation and measurement scope

Agreement in aggregate area can arise when false-positive and false-negative areas cancel. It
does not establish accurate crack localisation or foreground overlap. At the selected
setting the reported pixel accuracy is {wf6_acc}%, against approximately {in_empty_acc}% for
an all-background prediction. A decomposition of the aggregate summaries gives approximately
{in_fp_pct}% false-positive and {in_fn_pct}% false-negative image area. Their near
cancellation explains the small net area discrepancy. The {ag_best_spec}% specificity must
not be interpreted as foreground segmentation accuracy. Complete per-image precision, recall,
Dice, intersection over union and boundary measures are required to assess localisation
[3,4], and are deliberately not reported here because they cannot express the measurement
this study is about.

**The ranking reported in Section 3.2 is specific to the area endpoint and can be obtained
without detection.** Dilating this detector's own output, which reads no new evidence from
the image, moves it to the top of a conventional overlap ranking while increasing the
reported crack area fraction to {dec_area_fields} times the reference. That observation is
the reason this manuscript reports area agreement and background rejection rather than
overlap scores, and a reader should apply the same scepticism to the area ranking: it is a
ranking of total marked area and nothing more.

Diagnostic observations further limit the interpretation of the darkness criterion.
Approximately 42% of annotated crack area lies outside the reported proposal support. The
unreached labelled regions have higher reported mean intensity than the detected dark cores —
a mean grey level of 127 against a background of 82 and detected cores of 59 — which is
consistent with a contrast-polarity limitation rather than a threshold setting. Panels of the
most heavily cracked fields indicate that these regions are the illuminated interior surface
of an open crack. Expansion experiments increased marked area and did not establish a
validated correction. A future detector could combine dark-core evidence with independently
validated contextual or polarity-aware features; such changes require new experiments and
joint assessment of area bias and spatial overlap.

### 6.2  Scale, units and the absence of a scale bar

No panel drawn from the Inconel 718 collection carries a scale bar, because the collection
publishes no pixel size in any form: no resolution tag in the image files, no databar in the
fields, no magnification in the record, and subsets originating from different microscopes.
This is stated rather than left as an omission. The reported quantity is a dimensionless
ratio of pixel counts and does not depend on a pixel size, so the principal result survives
the absence; no physical length is reported for this collection and none can be.

The TXM panels in Section 4 do carry scale bars, from a pixel size of 29.24 nm/px that is
derived from mosaic geometry rather than read from instrument metadata. Those bars, and any
physical length derived from those frames, scale with the acquisition geometry if it is
corrected.

### 6.3  Validation and reproducibility

The reference annotation for this collection has undocumented provenance. As recorded in
Section 2.1, the Inconel 718 crack class is present in the archive but absent from the
collection's own class list, and no annotation protocol, annotator count or class definition
accompanies it. No inter-annotator agreement can be computed, and no second annotator exists,
so the reference cannot be distinguished from one annotator's judgement. A new benchmark
should fix the tuning objective within training folds, preserve complete per-image results,
report uncertainty for the primary endpoint, and document the annotation rules.

The released crops share parent images with the whole fields, so they do not form an
independent test population. Image framing also changes the reported area ratio: cropping
these images around their own cracks moves it from {in_ratio} to {in_crop_ratio} with no
change to the method, and reverses which operating setting is preferable.

The implementation requires a reproducible specification of the MAD normalisation, the
logical combination of the intensity gates, image and mask resizing, the morphological
footprint and the software version. The reported 13-pixel opening does not establish whether
that value denotes a radius, diameter or another footprint convention.

The current conclusion is limited to Inconel 718 whole fields and a two-dimensional area
endpoint, with the cross-modality result of Section 4 scoped as stated there. Generic defect
labels from another material collection, including MetalDAM [13], are not interchangeable
with crack annotations. Independent material-specific validation is needed before
interpreting image area as a physical three-dimensional defect quantity.

## Data and code availability

The source study identifies the dataset record in Ref. [7]. The TXM frames of Section 4 are
not part of a public release, and the acquisition parameters required to interpret them
physically are not recorded with the data. No archival DOI or commit hash is quoted for the
analysis code in this revision; both are required before submission, and until they exist a
reader cannot independently reproduce the numbers reported here.
