## 3  Results

### 3.1  Aggregate crack area agreement

At a MAD multiplier of {mk_best}, the detector produced a reported crack area fraction of
{ag_best_mark}%, compared with a reference fraction of {ag_best_lab}%. The resulting area
ratio was {ag_best}. The net difference was +0.024 percentage points, corresponding to an
aggregate relative excess of approximately {ag_best_err_pct}%.

The selected setting also recorded a reported background specificity of {ag_best_spec}%.
This value characterises rejection of non-crack background pixels. Together, the area ratio
and specificity quantify two aspects of the output: the total marked area and the
classification of the background population. Figure {fig_areabars}(a) places the pixel accuracy of every collection scored in this work beside the accuracy an all-background prediction reaches on the same pixels. The two are indistinguishable at this prevalence, which is the point, and it is why panel (b) plots the difference between them instead. Averaged over images, the detector sits {wf_margin_img} points BELOW an all-background prediction on the whole fields and {crop_margin_img} points above it on the released crops. Pooled over pixels at the selected setting, which is what Table 2 reports, the whole-field deficit is {wf_margin_pool} points; the all-background value is the same under both aggregations, so the difference between those two figures is the aggregation and nothing else. Table 2 collects the principal numerical results.

| Endpoint | Reported or derived value |
|---|---|
| Reference crack area | {ag_best_lab}% of image area |
| Predicted crack area | {ag_best_mark}% of image area |
| Predicted-to-reference area ratio | {ag_best} |
| Net aggregate area difference | +0.024 percentage points |
| Absolute relative aggregate area discrepancy | Approximately {ag_best_err_pct}% |
| Background specificity | {ag_best_spec}% |
| Pixel accuracy, pooled over pixels at the selected setting | {wf6_acc}% |
| Pixel accuracy of an all-background prediction | {in_empty_acc}% |
| Pixel accuracy, mean over images at the leave-one-image-out setting | {in_acc}% |
| Fields with lower absolute area error than the default | 23 of {in_n} |

[FIGURE areabars | (a) pixel accuracy on every collection scored in this work, with the vertical bar giving the accuracy an all-background prediction reaches on the same collection. (b) the difference between the two, in points, from its own zero. Panel (a) keeps a full 0 to 100 range, because a cropped value axis under bars misrepresents; panel (b) is a different quantity, and it is the only axis on which these collections are distinguishable at all. The withdrawn EBC coating appears in (a) and not in (b): it is 20 points below an all-background prediction and on a shared difference axis it reduces the three reported collections to slivers, which is the same failure that withdrew an area-ratio panel from this plate in an earlier version -- that panel's logarithmic axis had to reach 100 to hold the same collection. MetalDAM is included for reference and labels voids rather than cracks. The area ratio is the subject of Figure {fig_sweep}, where it is drawn against the constant that moves it.]

### 3.2  Descriptive comparison of aggregate area estimates

The darkness detector had the reported area ratio closest to unity among the seven displayed
method summaries. Its ratio of {arm_area_det} corresponds to an absolute relative aggregate
area discrepancy of approximately 1.3%. The darkness-or-Sato union had a ratio of
{arm_union_area}. The closest classical arm on its own was {arm_area_2nd_name} at
{arm_area_2nd}. Table 3 and Figure {fig_arms} retain the complete displayed comparison.

{arm_tbl}

[FIGURE arms | Seven arms on the 31 whole fields, each given its own best parameter by the same leave-one-image-out rule and ordered by agreement in total marked area. (a) reported crack area divided by annotated crack area; the vertical line at 1.0 is exact agreement. (b) pixel accuracy expressed as the difference from an all-background prediction on the same images, in percentage points. The accuracies themselves span 97.7 to 98.2% and are plotted as a difference because a value axis cropped to separate them would misrepresent their similarity. Otsu thresholding on the flattened image is omitted here, marking 99.5% of the frame, and appears in Appendix A. This detector is the dark bar.]

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

[FIGURE sweep | Reported crack area divided by annotated crack area against the MAD multiplier k, on the 31 whole fields and on the 26 released crops cut from them. Both axes are logarithmic and the horizontal line at 1.0 is exact agreement. The diamond marks k = 6.0. The leftmost seven points of each series are the range swept in the earlier analysis.]

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

### 3.5  What the area endpoint can resolve

[FIGURE ceiling | Pixel accuracy of the reference annotation reduced to its centreline and redrawn at a fixed width, against that width: a prediction exactly correct about where every crack lies and wrong only about how wide it is drawn. The horizontal axis is logarithmic. Dotted lines give the accuracy of an all-background prediction on each collection, and the diamonds mark each curve's maximum.]

A comparison is only readable against the range in which it can move. Taking the reference
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

Figure {fig_budget} puts the three overlap measures back into the pixel accounting they
discard. The annotated crack is {in_prev}% of the whole-field collection, so {in_tn_pct}%
of every image is background in both the prediction and the annotation and takes no part in
precision, recall or F1 at all; the panel shows the marked area split into the part that
agrees with the annotation and the part that does not, against the annotated area, in the
units the measurement is actually reported in. Its counterpart for the transmission X-ray
collection is Figure {fig_txmbudget}.

[FIGURE budget | The pixel budget on the Inconel 718 collection, in the units the measurement is reported in rather than as an overlap score. (a) the detector's marked area divided into the part that agrees with the annotation and the part that does not, with the annotated area drawn as an outline, both as a percentage of all image pixels. (b) marked area divided by annotated area, with unity marked. Precision, recall, F1 and IoU discard the pixels that are background in both, which at this collection's annotated crack fraction is most of the image; the over-marking ratio in (b) is the error a user of an area fraction feels. Figure {fig_txmbudget} is the same accounting for the transmission X-ray collection.]

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
rather than a number. Each failure is also concentrated in a few frames, and in the TXM over-counting it is concentrated in a single OBJECT: 99.6% of the over-counted area of the worst TXM frame is one connected low-attenuation region the operator rejected. A panel cut from that frame would be a picture of that object, so the over-counting column excludes frames whose error is that concentrated and the caption says what was excluded and why. The pictures therefore say what the two failures look like where they are a tendency, and the measurements in Sections 3.6 and 4.4 say how much of each there is and how unevenly it is spread; neither reading substitutes for the other.

[FIGURE counting | The two errors, in both of this laboratory's collections. Columns: the window holding the most over-counted pixels, and the window holding the most under-counted ones. Rows: the SEM collection at {wf_sem_nm} nm/px and the TXM collection at {wf_txm_nm} nm/px, each over a 30 micrometre field. Blue is marked area the operator agrees with, red is marked area the operator ruled not crack, and green is the operator's crack that was not marked. Marked pixels nobody adjudicated are left in the grey of the micrograph and are not coloured at all -- colouring them either way is the error that turns a precision of 0.99 into 0.29 -- and they are most of panel (b), whose black region is the unreviewed interior of a wide open crack. Each panel comes from the frame holding the most pixels of its own error kind, ranked from the per-frame precision and recall of Section 4.4, and from the window within it holding the most, found exactly by a box sum rather than chosen by eye and capped at 25% of the window so that the panel shows the boundary of the error and not a block of flat colour. Only frames whose annotation is a trace rather than a filled region are eligible: on the rest the annotation asserts that there is crack somewhere in a region, over strokes hundreds of pixels wide, and any window inside one is solid under-count whatever the detector does. The over-counting column asks for one more thing: that no single connected false-positive component hold more than 35% of its frame's over-counted area. The TXM frame with the most over-counting fails that at 99.6%, because its over-counting is one large low-attenuation region the operator rejected, and any window cut from it shows that object rather than the error; the frame shown instead holds {cnt_txm_over_share}% of the collection's over-counted pixels in 13 separate components. A window may also be at most a quarter marked-but-unreviewed, for the same reason: without that, the under-counting panel was two thirds black.]
