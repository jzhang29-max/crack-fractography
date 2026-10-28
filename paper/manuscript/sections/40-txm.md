## 4  Cross-modality evaluation

The transmission X-ray microscopy collection is used here for two separate purposes, and the
distinction matters because the two give opposite-looking answers. The collection has **its
own detector**, built independently of the one evaluated in Section 3 and on different
principles, so Section 4.1 is a second instance of the same measurement problem rather than a
second dataset. Section 4.2 then uses that detector to show what an overlap score measures
when the reference is a broad brush, which is this paper's central claim in a form that can
be read off a number. Section 4.3 carries the SEM detector itself across, unchanged.

A pixel size of {tm_nm} nm/px is used for every scale bar in this section. It is **derived
from operator-supplied mosaic geometry, not read from instrument metadata**, and the source
repository marks it as unconfirmed. Every physical length below inherits that assumption; the
area fractions and overlap scores do not, being dimensionless.

### 4.1  The collection's own detector

[FIGURE txmstages | The TXM collection's own detector, stage by stage, on one window of a typical frame. (a) the operator's painted crack, the reference for this window, in green. (b)-(d) the model, in blue: (b) seventeen hand-built channels — intensity, smoothing at sigma 2 to 64, gradient magnitude and Laplacian at sigma 1 to 8, and texture at sigma 2 and 8 — scaled and passed to a two-layer network, which runs with no encoder and is the fallback when the encoder is unreachable; (c) the same seventeen channels concatenated with 256 frozen SAM ViT-H encoder channels, 273 inputs, applied in 1024 px tiles at stride 896 and Hann-blended, the encoder never fine-tuned and its prompt encoder and mask decoder never called; (d) the mean of (b) and (c) at threshold 0.60 followed by speck pruning, which is what the application emits. The window is 1100 px of a frame whose full-resolution agreement with the operator is the corpus median, so it is typical rather than flattering. The display is contrast-stretched per crop; the model ran on the unstretched image. Scale bars 5 micrometres at {tm_nm} nm/px (Section 4).]

The three rungs differ in what they mark, not by a little. On the window of Figure 8 the
operator painted {tm_ws_paint}% of the field. The seventeen-channel member alone reaches an
IoU of {tm_ws_f17} against that paint while marking {tm_ws_f17pct}% of the window — it finds
the crack's trace and floods the matrix with it. Adding the frozen encoder raises the IoU to
{tm_ws_hyb} and cuts what is marked to {tm_ws_pct}%, close to the operator's own coverage. The
deployed mean of the two scores {tm_ws_ens}. **The step that matters is the encoder, not the
averaging.** The two members agree with each other at an IoU of only {tm_ws_ab} on this
window, so the encoder changes what is marked rather than refining it; the hybrid and the
deployed mean agree at {tm_ws_bc}, so the averaging is close to a no-op here and whatever it
contributes is a corpus-level result rather than a visible one.

Grouped cross-validation over {tm_cv_n} labelled images puts the ensemble at IoU
{tm_cv_ens} with a standard deviation of {tm_cv_sd} and a lowest fold of {tm_cv_min}, against
{tm_cv_f17} for the seventeen-channel member and {tm_cv_hyb} for the hybrid, at a precision of
{tm_cv_prec} and a recall of {tm_cv_rec}.

**That figure is not an estimate of whole-frame performance, and the difference is large.**
The same deployed model, on the same collection, returns three materially different numbers
according to what is scored:

| What is scored | Aggregation | Frames | IoU |
|---|---|---|---|
| 250,000 sampled hand-painted pixels per fold, 5 folds grouped by image | mean over folds | {tm_cv_n} | {tm_cv_ens} |
| Only pixels an operator adjudicated, as crack or as not-crack | median over frames | {tm_ld_n} | {tm_ld_iou} |
| Every pixel of the frame, at full resolution | median over frames | {tm_wf_n} | {tm_wf_iou} |

The spread across those three rows, {tm_cv_ens} to {tm_wf_iou}, is larger than any difference
between the three model rungs. Two properties of the cross-validated row explain most of it
and must travel with it: the rows are drawn from painted pixels rather than from frames, so
the prevalence of crack in the scored sample is nothing like its prevalence in a frame; and
the folds are **grouped by image, not by specimen**, while the labelled frames span four
specimen groups, so no whole specimen is ever held out. The whole-frame row is the one a
reader should compare with Section 3. Its interquartile range is {tm_wf_q1} to {tm_wf_q3},
and on the frame shown in Figure 8 the recall is {tm_wf_rec} while only {tm_wf_fp}% of the
pixels the operator painted as not-crack are marked.

### 4.2  What the overlap score is measuring

[FIGURE txmceiling | What a TXM overlap score rewards. (a) for each of {tm_ld_n} frames, the IoU the deployed model reaches against the operator's stroke (circles) and the IoU a physically correct crack trace could reach against that same stroke (triangles), plotted against the median width of the stroke on that frame. The correct trace is a construction, not a model: the annotation's own centreline redrawn three pixels wide, so it is exactly right about where every crack runs and wrong only about how wide it is drawn. Spearman correlations with stroke width are given beside each series. (b) the same two quantities as specimen-group medians, with each group's median stroke width beneath its label. Both series use one IoU convention, restricted to pixels an operator adjudicated, and the model's mask is taken with the operator's corrections excluded so that the comparison is not circular.]

The reference in this collection is a wide brush. The operator's stroke has a median width of
{tm_ld_width} px and ranges from {tm_ld_wmin} to {tm_ld_wmax} px, over a crack whose dark core
is a few pixels across. An IoU scored against that stroke therefore pays for covering the
stroke, and the two series in Figure 9 show what that is worth: the annotation's own
centreline redrawn at three pixels scores {tm_ld_ceil}, while the deployed model scores
{tm_ld_iou} — a ratio of medians of {tm_ld_ratio}. A trace that is exactly right about the
location of every crack outscores the model on **{tm_ld_wins} of the {tm_ld_n} frames**.

**The two move in opposite directions with stroke width.** The model's IoU rises with how
widely the operator painted, at a Spearman correlation of {tm_rho_sh}; the correct trace's
ceiling falls, at {tm_rho_c3}. Across specimen groups the ordering is the same: the group with
the widest strokes records the highest model IoU and the lowest ceiling, and the group with
the narrowest strokes records the lowest model IoU and the highest ceiling. Neither slope is
interesting on its own — the frames are plotted against a property of their own labels — but
the **opposite sign** is not an artefact of that, and it is the whole of the argument. On this
collection, a higher overlap score is evidence that a mask resembles the annotator's brush and
is not, by itself, evidence that it has found more crack.

This is why Section 3 reports an area fraction with its measurement error as the endpoint and
treats the overlap measures as secondary, and it is why the ceiling in Figure 6 is reported
beside them rather than after them.

### 4.3  The SEM detector carried across

[FIGURE txm | The same detector as Section 3, with the same constant, applied to transmission X-ray microscopy of austenitic steel. (a)-(c) a B3 frame and (d)-(f) an AM/HC frame, the two specimen groups whose behaviour differs most: (a, d) the frame, contrast-stretched per crop for display only, the detector having run on the unstretched image; (b, e) the annotated crack in blue, with area that was not reviewed by an annotator dimmed and excluded from every number; (c, f) the prediction, green where it agrees with the annotation, orange where it marks reviewed not-crack, blue where annotated crack was missed. (g) pixel accuracy over reviewed pixels, expressed as the difference from an all-background prediction in percentage points. (h) reported crack area divided by annotated crack area, the vertical line at 1.0 being exact agreement. Scale bars 5 micrometres at {tm_nm} nm/px (Section 4).]

The SEM detector was carried unchanged to {tx_n} TXM frames. Over the reviewed area, crack is
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
measured. What the section establishes is narrow and still worth stating: a constant fitted on
SEM steel in one laboratory, carried without modification to a different imaging physics,
clears both no-information comparators on all four groups and clears an all-background
prediction on one.

**Section 4.1 and Section 4.3 are not in conflict.** The collection's own detector reaches a
whole-frame median IoU of {tm_wf_iou} where the carried-over SEM detector falls below an
all-background prediction, which is the expected ordering: one was fitted on this modality and
the other was not. What Section 4.2 adds is that neither number should be read as a distance
from the crack. The frame counts also differ between the three subsections — {tm_cv_n},
{tm_ld_n}, {tm_wf_n} and {tx_n} frames respectively, according to which frames carry the
labels each measurement needs — and they are not pooled anywhere.
