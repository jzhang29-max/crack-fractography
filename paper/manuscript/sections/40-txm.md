## 4  Cross-modality evaluation

[FIGURE txm | The same detector, with the same constant, applied to transmission X-ray microscopy of austenitic steel. (a-c) a B3 frame and (d-f) an AM/HC frame, the two specimen groups whose behaviour differs most: (a, d) the frame, contrast-stretched per crop for display only, the detector having run on the unstretched image; (b, e) the annotated crack in blue, with area that was not reviewed by an annotator dimmed and excluded from every number; (c, f) the prediction, green where it agrees with the annotation, orange where it marks reviewed not-crack, blue where annotated crack was missed. (g) pixel accuracy over reviewed pixels, expressed as the difference from an all-background prediction in percentage points. (h) reported crack area divided by annotated crack area, the vertical line at 1.0 being exact agreement. Scale bars 5 micrometres, from a pixel size of 29.24 nm/px derived from mosaic geometry rather than read from instrument metadata (Section 2.5).]

The detector was carried unchanged to {tx_n} TXM frames. Over the reviewed area, crack is
{tx_prev}% and an all-background prediction scores {tx_empty}% accuracy.

**Pooled, the configuration does not transfer.** It records {tx_acc}% accuracy, {tx_margin}
percentage points below an all-background prediction, and reports {tx_area} times the
annotated crack area at a recall of {tx_recall}. It clears both no-information comparators
comfortably — an Otsu darkness cut with no model records {tx_otsu_acc}% and marking every
pixel {tx_all_acc}% — so the configuration is doing something. It is not doing enough to
improve on marking nothing.

**The pooled figure is four different results.** The specimen groups do not behave alike:

| Specimen group | Frames | Crack % of reviewed area | Accuracy | All-background | Recall | Area reported / annotated |
|---|---|---|---|---|---|---|
| B3 | {tx_b3_n} | 22.2% | {tx_b3_acc}% | {tx_b3_empty}% | {tx_b3_recall} | {tx_b3_area} |
| B2 | {tx_b2_n} | 8.9% | {tx_b2_acc}% | {tx_b2_empty}% | {tx_b2_recall} | {tx_b2_area} |
| Wrought | {tx_wrought_n} | 15.4% | {tx_wrought_acc}% | {tx_wrought_empty}% | {tx_wrought_recall} | {tx_wrought_area} |
| AM/HC | {tx_amhc_n} | 2.6% | {tx_amhc_acc}% | {tx_amhc_empty}% | {tx_amhc_recall} | {tx_amhc_area} |

One group transfers. On B3 the detector records {tx_b3_acc}% accuracy against
{tx_b3_empty}% for an all-background prediction, a margin of {tx_b3_margin} points, at a
recall of {tx_b3_recall} and an area ratio of {tx_b3_area}. On B2 the reported area is close
to correct at {tx_b2_area} while the recall is {tx_b2_recall}, so the right quantity of
foreground is placed substantially in the wrong locations. On AM/HC the detector reaches a
recall of {tx_amhc_recall} while marking 13% of the reviewed area, and reports
{tx_amhc_area} times the annotated crack area. On Wrought it finds most of the annotated
crack and over-reports the area by {tx_wrought_area} times.

**This is reported as a transfer result and not as a capability.** Four specimen groups give
four answers, each group is a small number of frames, and the groups are different materials
and loading conditions, so the pooled figure is a weighted mean over four distinct
measurements rather than an estimate of one. The acquisition parameters for this collection —
instrument, beam energy, voxel size at the specimen, reconstruction algorithm — are not
recorded with the data, and the pixel size used for the scale bars is derived rather than
measured. Any physical length derived from these frames inherits that assumption. What the
section establishes is narrow and still worth stating: a constant fitted on SEM steel in one
laboratory, carried without modification to a different imaging physics, clears both
no-information comparators on all four groups and clears an all-background prediction on one.
