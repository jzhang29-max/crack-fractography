## 3  Results

### 3.1  Aggregate crack area agreement

At a MAD multiplier of {mk_best}, the detector produced a reported crack area fraction of
{ag_best_mark}%, compared with a reference fraction of {ag_best_lab}%. The resulting area
ratio was {ag_best}. The net difference was +0.024 percentage points, corresponding to an
aggregate relative excess of approximately {ag_best_err_pct}%.

The selected setting also recorded a reported background specificity of {ag_best_spec}%.
This value characterises rejection of non-crack background pixels. Together, the area ratio
and specificity quantify two aspects of the output: the total marked area and the
classification of the background population. Figure {fig_areabars}(a) places the pixel accuracy of every collection scored in this work beside the accuracy an all-background prediction reaches on the same pixels. The two are indistinguishable at this prevalence, which is the point, and it is why panel (b) plots the difference between them instead. Averaged over images, the detector sits {wf_margin_img} points BELOW an all-background prediction on the whole fields and {crop_margin_img} points above it on the released crops. Pooled over pixels at the selected setting, which is what Table {tbl_endpoints} reports, the whole-field deficit is {wf_margin_pool} points; the all-background value is the same under both aggregations, so the difference between those two figures is the aggregation and nothing else. Table {tbl_endpoints} collects the principal numerical results.

[TABLE endpoints | The principal numerical results at the selected setting, on the 31 whole fields. Every row is pooled over pixels. The area ratio is also recorded as a mean over images in the caption file beside Figure {fig_parameters}, where it reads about a quarter higher at every value of k; it is not plotted on that figure, whose panel (a) carries F1, and the two aggregations of that one quantity are named wherever either is used. The two pixel accuracies are the same quantity under two aggregations and are both given because the figures quote different ones: the pooled row is over pixels at the fixed selected multiplier, the per-image row is the mean over images at the leave-one-image-out setting, and the all-background value is identical under both.]
| Endpoint | Reported or derived value |
|---|---|
| Reference crack area | {ag_best_lab}% of image area |
| Predicted crack area | {ag_best_mark}% of image area |
| Predicted-to-reference area ratio, pooled over pixels | {ag_best} |
| Net aggregate area difference | +0.024 percentage points |
| Absolute relative aggregate area discrepancy | Approximately {ag_best_err_pct}% |
| Background specificity | {ag_best_spec}% |
| Pixel accuracy, pooled over pixels at the selected setting | {wf6_acc}% |
| Pixel accuracy of an all-background prediction | {in_empty_acc}% |
| Pixel accuracy, mean over images at the leave-one-image-out setting | {in_acc}% |
| Fields with lower absolute area error than the default | 23 of {in_n} |

[FIGURE areabars | (a) pixel accuracy on every collection scored in this work, with the vertical bar giving the accuracy an all-background prediction reaches on the same collection. (b) the difference between the two, in points, from its own zero. Panel (a) keeps a full 0 to 100 range, because a cropped value axis under bars misrepresents; panel (b) is a different quantity, and it is the only axis on which these collections are distinguishable at all. The withdrawn EBC coating appears in (a) and not in (b): it is 20 points below an all-background prediction and on a shared difference axis it reduces the three reported collections to slivers, which is the same failure that withdrew an area-ratio panel from this plate in an earlier version -- that panel's logarithmic axis had to reach 100 to hold the same collection. MetalDAM is included for reference and labels voids rather than cracks. The area ratio is the subject of Figure {fig_sensitivity}(a), where it is drawn against the constant that moves it.]

### 3.2  Descriptive comparison of aggregate area estimates

The darkness detector had the reported area ratio closest to unity among the seven displayed
method summaries. Its ratio of {arm_area_det} corresponds to an absolute relative aggregate
area discrepancy of approximately 1.3%. The darkness-or-Sato union had a ratio of
{arm_union_area}. The closest classical arm on its own was {arm_area_2nd_name} at
{arm_area_2nd}. Table {tbl_arms} and Figure {fig_arms} retain the complete displayed comparison.

[TABLE arms | Seven arms on the 31 whole fields, each given its own best parameter by the same leave-one-image-out rule and ordered by agreement in total marked area. The ordering applies to the area endpoint and to these displayed summaries; it does not establish superiority in foreground overlap.]
{arm_tbl}

[FIGURE arms | Seven arms on both framings of the same images, each given its own best parameter by the same leave-one-image-out rule and ordered by agreement in total marked area on the whole fields. The filled circle is the 31 whole fields and the open square the 26 released crops cut from them, joined by a rule. (a) reported crack area divided by annotated crack area; the vertical line at 1.0 is exact agreement. The marks are drawn on a rule against unity rather than as bars from zero, because one and not zero is this quantity's reference. (b) pixel accuracy expressed as the difference from an all-background prediction on the same pixels, in percentage points, where zero IS the reference and the origin is therefore zero. The accuracies themselves span 97.7 to 98.2% on the whole fields and are plotted as a difference because a value axis cropped to separate them would misrepresent their similarity. Neither axis is cropped. Otsu thresholding on the flattened image is omitted, marking 55 times the annotated area on the whole fields, and appears in Appendix A. The shaded row is this detector.]

**The ordering is a property of the framing and not of the methods.** Drawing both
collections on one plate shows that every one of the seven arms sits below an all-background
prediction on the whole fields, and that four of them sit above it on the crops cut from
those same fields. This detector is one of the four, moving from {arm_rev_wf} points below
to {arm_rev_cr} points above. The images are the same; only the cut is different. No ranking
in this section should be read as a property of a method without the collection it was
measured on attached to it.

The area comparison identifies a specific strength of the selected configuration: its total
foreground area closely matches the reported reference total. The numerical ordering applies
to that endpoint and to these displayed summaries. It does not establish superiority in
foreground overlap; Section 3.6 reports the overlap measures for the crack class, and
Section 5.1 states what the area ordering does not establish.

### 3.3  Field-level area error comparison

A lower absolute area error was recorded at the selected setting than at the default setting
in 23 of the {in_n} whole fields, approximately 74% of the evaluated fields. The count
supplements the aggregate comparison by describing the direction of the paired image-level
difference.

### 3.4  The operating-setting sweep, in full

[FIGURE sensitivity | The two sensitivities the result rests on, on one plate. (a) reported crack area divided by annotated crack area against the MAD multiplier k. Both axes are logarithmic and the horizontal line at 1.0 is exact agreement; the diamond marks k = 6.0, and the leftmost seven points of each SEM series are the range swept in the earlier analysis. All three series are the same ratio, but the two SEM series are over every pixel of the frame and the transmission series is over the pixels an operator adjudicated, so the ratios are commensurable while their denominators cover different things. (b) pixel accuracy of the reference annotation reduced to its centreline and redrawn at a fixed width, against that width: a prediction exactly correct about where every crack lies and wrong only about how wide it is drawn. The horizontal axis is logarithmic, the dotted lines give the accuracy of an all-background prediction on each collection, and the diamonds mark each curve's maximum. The vertical axis of (b) is not cropped to separate the series: it still reaches both all-background lines, which is what the curves are read against.]

The earlier analysis selected its operating setting from a grid of seven values running from
1.0 to the default of 5.0. **The default was the largest value tested, and the area ratio was
still falling when the grid ran out.** A selection made from a grid whose maximum is the
value being selected cannot fail, and this one did not.

Extending the sweep gives the two-sided curve. The reported area ratio falls monotonically
with the multiplier, crossing unity between 5.0 and 7.0, and the crossing is at {mk_best},
where the reported fraction is {ag_best_mark}% against the annotated {ag_best_lab}%. At the
earlier default the detector over-reports by {wf5_area} times; one rung higher it agrees to
{ag_best_err_pct}%; one rung beyond that it under-reports at {wf7_area} times. Across the
{mk_n} whole fields the absolute area error is smaller at {mk_best} than at the default in
{mk_area_wins} of {mk_n} images, paired Wilcoxon p {mk_area_p}.

Two consequences should be read with the result. The direction of the useful change is
towards marking **less**, not more. And on the released crops the same change moves the area
ratio the wrong way, from {mk_crop_ship_ratio} to {mk_crop_6_ratio} (p {mk_crop_area_p}),
because those crops are cut around their own cracks and the detector already under-reports on
them. The two framings of the same images disagree about the correct operating setting, which
is a reason not to read a single tuned constant as a property of the method.

Panel (a) also carries the transmission collection, which the sweep had never been drawn
against. Over the {sw_grid} range both were run at, the whole-field ratio moves by a factor
of {sw_sem_span}, from {sw_sem_hi} to {sw_sem_lo}, and crosses unity on the way. The
transmission ratio moves by a factor of {sw_txm_span}, from {sw_txm_hi} to {sw_txm_lo},
crossing unity between k = 6 and k = 7 near the top of its range. **The one free constant
has leverage on one microscopy and almost none on the other.** Where it does bring the
transmission area into agreement it does not bring the accuracy with it -- Section 4.3
reports that combination, the right quantity of foreground in the wrong places -- so the
disagreement reported there is not a tuning failure. The two series are the same
ratio; their denominators are not the same population, and the caption says which.

### 3.5  What the area endpoint can resolve

Figure {fig_sensitivity}(b) carries this section. A comparison is only readable against the range in which it can move. Taking the reference
annotation itself, reducing it to its centreline and redrawing it at a fixed width gives a
prediction with perfect localisation whose only error is width. Whatever that construction
scores is an upper reference point for this collection.

**On the whole fields the entire range is {wc_f_head} percentage points.** The
reconstruction peaks at {wc_f_peak}% pixel accuracy at a drawn width of {wc_f_at} px, against
{wc_f_empty}% for an all-background prediction. A prediction with perfect localisation and
the best available width is worth less than one point of accuracy over marking nothing. That
is not a statement about any detector; it is a statement about what pixel accuracy can
express at this prevalence, and it is why the area endpoint rather than accuracy carries the
result.

On the released crops, where the annotated fraction is {in_crop_lab_pct}%, the range is
{wc_c_head} points — a reconstruction ceiling of {wc_c_peak}% against {wc_c_empty}% — and
there the comparison becomes informative. The detector reaches {cb_acc}%, which is
{wc_c_captured}% of the available range.

The same construction locates the width. The reconstruction reproduces the annotated crack
area fraction at {wc_f_areaw} px on the whole fields and {wc_c_areaw} px on the crops, so a
mask drawn near the annotation's own stroke width already carries approximately the correct
amount of foreground, and the residual disagreement concerns placement rather than quantity.

### 3.6  Foreground overlap for the crack class

Every endpoint reported so far is computed over all the pixels of the frame. Precision,
recall and F1 are computed over the crack class alone and discard the pixels that are
background in both the prediction and the annotation, which at an annotated crack fraction
of {in_prev}% is most of the image. This section reports those three measures for the same
two collections, from the same predictions.

On the {in_n} whole fields the recorded values were a precision of {ov_prec}, a recall of
{in_recall_perimage} and an F1 of {in_f1}. On the {ov_crop_n} released crops cut from
those same fields they were {ov_crop_prec}, {ov_crop_recall} and {in_crop_f1}. The MAD
multiplier was selected leave-one-image-out in both cases, and on both collections the
rule returned the same value for every held-out image, so these are also the values at a
fixed multiplier of {mk_ship}. A prediction that marks every pixel records a recall of
{ov_me_recall} on either collection, a precision equal to the annotated crack fraction,
and an F1 of {in_me_f1} on the whole fields. The same three measures on this laboratory's
own two collections are given in Section 4.4, averaged over frames and each read against
the score a geometrically correct trace of its own annotation would reach.

[FIGURE overlap | Precision, recall and F1 for the crack class on the Inconel 718 collection, scored against an annotation that covers every pixel, at zero pixels of tolerance, on the detector's own mask with no annotation unioned into it. (a) the three measures on the whole fields and on the released crops cut from them; the short horizontal rule drawn on each bar is the value a prediction that marks every pixel records, which is 1.000 for recall and the annotated crack fraction for precision. (b) the same two collections as precision against recall across the seven values of the MAD multiplier, with the diamond marking the selected setting and the horizontal rule at recall 1.000 marking the mark-everything prediction. The multiplier increases from right to left along each curve. The legend in panel (b) identifies the collections in both panels.]

Precision differs between the two framings by a factor of {ov_prec_ratio} and recall by a
factor of {ov_recall_ratio}. The annotated crack fraction also differs between them, by a
factor of {ov_prev_ratio}, {in_prev}% against {in_crop_prev}%, and the precision a
no-information prediction records moves with it, from {ov_prec_floor} on the whole fields
to {ov_crop_prec_floor} on the crops. Read as a multiple of that reference, precision is
{ov_lift} times it on the whole fields and {ov_crop_lift} times it on the crops. The two readings — the crops
record the higher precision, the whole fields the higher multiple of their own reference —
are two descriptions of the same measurements, and the collection a method is scored on is
reported with them for that reason.

Panel (b) places the reported pair on the sweep it is one point of. Across the grid, which
runs from {ov_k_lo} to {ov_k_hi}, precision rises and recall falls monotonically; at the
low end of the grid the whole fields record a precision of {ov_prec_lo} at a recall of
{ov_recall_lo}, which is a prediction close to the mark-everything one. The selected value
is the largest in the grid, the same grid-edge condition described in Section 3.4, so the
curve is not shown to turn.

These are reported as values rather than as intervals because every pixel of this
collection's annotation carries a verdict, so a predicted pixel outside the annotated crack
is counted against a decision that was actually made. Where an annotation adjudicates only
part of each frame, as this laboratory's own hand-marked frames do, a precision computed
against it is a bracket whose ends are the assumption that every unadjudicated predicted
pixel is wrong and the assumption that every one is right. No value in this section is a
measurement of such a collection; Section 4.4 measures those two collections and gives
both ends of that bracket for each.

Figure {fig_budgets} puts the three overlap measures back into the pixel accounting they
discard. The annotated crack is {in_prev}% of the whole-field collection, so {in_tn_pct}%
of every image is background in both the prediction and the annotation and takes no part in
precision, recall or F1 at all; panel (a) shows the marked area split into the part that
agrees with the annotation and the part that does not, against the annotated area, in the
units the measurement is actually reported in. Panel (b) is the same accounting for the
transmission X-ray collection, in that collection's own denominator, and Section 4.3
reads it; panel (c) is the one quantity the two arms can be compared on.

[FIGURE budgets | The pixel budget in both arms, in the units the measurement is reported in rather than as an overlap score. (a) the detector's marked area on the two public collections, divided into the part that agrees with the annotation and the part that does not, with the annotated area drawn as an outline, all as a percentage of ALL image pixels. (b) the same accounting on the two specimen series of the transmission collection, as a percentage of the REVIEWED area, which is the area an operator ruled on and is about a fifth of the frame. The two panels are percentages of different things and are kept apart for that reason; no bar in (a) may be compared with a bar in (b). (c) marked area divided by annotated area for all four, which is dimensionless, has unity for its reference in both arms, and is the one quantity they share; it is drawn in a single neutral colour because blue and orange already carry a meaning in (a) and (b). Precision, recall, F1 and IoU discard the pixels that are background in both, which at these annotated crack fractions is most of the image, and the over-marking ratio in (c) is the error a user of an area fraction feels. The withdrawn EBC coating is omitted: at 20.29% marked against 0.27% annotated it would set the axis of (a) by itself.]

### 3.7  What the two errors look like

The two failures that precision and recall measure do not look alike, and which one
dominates decides what a user of the measurement can do about it. An over-count is a
marked object the operator rejected, and it is visible to a person as soon as the mask is
drawn; an under-count is annotated crack the detector never proposed, and the user is never
shown it. Figure {fig_counting} gives the worst window of each kind in each of this
laboratory's two collections, drawn on the frames whose annotation is a trace rather than a
filled region.

**They are the worst cases and not typical ones, deliberately, and the figure says so.** A
first version of this figure drew the median-F1 frame of each collection, and its
over-counting panels held 0.5% and 0.03% over-counted pixels: on a typical frame there is
essentially nothing to look at, which is this collection's precision restated as a picture
rather than a number. Each failure is also concentrated in a few frames, and in the TXM over-counting it is concentrated in a single OBJECT: 98.8% of the over-counted area of the worst TXM frame is one connected low-attenuation region the operator rejected. A panel cut from that frame would be a picture of that object, so the over-counting column excludes frames whose error is that concentrated and the caption says what was excluded and why. The pictures therefore say what the two failures look like where they are a tendency, and the measurements in Sections 3.6 and 4.4 say how much of each there is and how unevenly it is spread; neither reading substitutes for the other.

[FIGURE counting | The two errors, on one field of each modality, each marked by the detector that modality actually ships. Columns: the window holding the most over-counted pixels, and the window holding the most under-counted. Top row, a {cnt_sem_spec} field at {cnt_sem_nm} nm/px marked by the shipped SEM detector -- the darkness rule followed by the region classifier. That field is one of the 45 images the classifier was fitted on, so this row is IN SAMPLE in the same way the transmission row below it is: recall {cnt_sem_rec} over the {cnt_sem_crack_px} pixels the operator painted crack. **That operator left no not-crack verdict anywhere on this field** -- {cnt_sem_notcrack_px} pixels -- so no pixel on it can be an over-count, the left-hand panel of that row says so in place of a percentage, and the precision of {cnt_sem_prec} the record carries for it is 1 by construction rather than a score. Quote the recall. Bottom row, a {cnt_txm_spec} field at {cnt_txm_nm} nm/px marked by the trained transmission model -- seventeen image channels and a frozen SAM embedding, the mean of two fitted members cut at 0.60: precision {cnt_txm_prec}, recall {cnt_txm_rec}. **That transmission field is inside the model's training set.** No labelled frame was held out when the deployed members were fitted, so those two numbers are in-sample; the out-of-sample estimate for the same model is the grouped cross-validation reported in Section 4.3, and the two must not be read as one number. Blue is marked area the operator agrees with, red is marked area the operator ruled not crack, green is the operator's crack that was not marked, and grey is pixels nobody adjudicated, which are neither an error nor an agreement -- counting them either way is what moves a precision of 0.99 to 0.29. Each window is a multiple of its own frame's 90th-percentile paint stroke rather than a fixed field of view: the two frames differ by more than fourfold in pixel size, and a fixed micrometre window came out wider than the SEM frame is tall, which silently disabled every placement constraint. The multiple is six on both rows. Frame and multiple were chosen together by search: every eligible SEM field was crossed with five window sizes and the pairs ranked on the WORSE of their two panels, by the share of the panel carrying a verdict of any kind. An operator adjudicated {cnt_txm_ref}% of the transmission frame and {cnt_sem_ref}% of the SEM one. Within the frame the window is placed by an exact box sum at the position holding the most pixels of that panel's error kind -- or, where that error kind does not occur on the frame at all, at the position holding the most confirmed detection, which the figure's record states per panel -- subject to that error kind being at most a quarter of the window, at most a quarter marked but unreviewed, at most 5% off-specimen black, a floor on operator-confirmed mask so the error is seen beside a correct detection, and a bound on the straight edge of the annotated region; the constraints relax one at a time, weakest first, and none was relaxed on any panel here. Each frame is the best-agreeing eligible field of its specimen, which flatters both rows, and every candidate and every rejection is in the figure's record. The ambient field MAR_Amb_HIP_CBS_0006 is the only HIP field that can be scored in both directions, and it is what this figure drew in its previous edition; eleven of the thirteen HIP frames carrying a mask are one-sided in the way the hydrogen-charged field is, Cast_24hr_SE_Side_006 among them (3,709,448 crack, 0 not-crack), and the hydrogen-charged MAR fields carry no correction mask at all. The over-counting behaviour of the electron detector is therefore read off the ambient fields and off Figure {fig_arms}, not off this plate.]
