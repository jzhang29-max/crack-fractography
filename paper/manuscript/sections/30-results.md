## 3  Results

### 3.1  Aggregate crack area agreement

At a MAD multiplier of {mk_best}, the detector produced a reported crack area fraction of
{ag_best_mark}%, compared with a reference fraction of {ag_best_lab}%. The resulting area
ratio was {ag_best}. The net difference was +0.024 percentage points, corresponding to an
aggregate relative excess of approximately {ag_best_err_pct}%.

The selected setting also recorded a reported background specificity of {ag_best_spec}%.
This value characterises rejection of non-crack background pixels. Together, the area ratio
and specificity quantify two aspects of the output: the total marked area and the
classification of the background population. Figure 3 places the result against every
collection scored in this work, and Table 2 collects the principal numerical results.

| Endpoint | Reported or derived value |
|---|---|
| Reference crack area | {ag_best_lab}% of image area |
| Predicted crack area | {ag_best_mark}% of image area |
| Predicted-to-reference area ratio | {ag_best} |
| Net aggregate area difference | +0.024 percentage points |
| Absolute relative aggregate area discrepancy | Approximately {ag_best_err_pct}% |
| Background specificity | {ag_best_spec}% |
| Pixel accuracy | {wf6_acc}% |
| Pixel accuracy of an all-background prediction | {in_empty_acc}% |
| Fields with lower absolute area error than the default | 23 of {in_n} |

[FIGURE areabars | Performance on every collection scored in this work. (a) reported crack area divided by annotated crack area; the vertical line at 1.0 is exact agreement and the diamond marks the selected setting on the whole fields. The axis is logarithmic. (b) pixel accuracy, with the vertical bar giving the accuracy an all-background prediction would reach on the same collection. MetalDAM is included for reference and labels voids rather than cracks; the EBC coating was withdrawn from this study as a ceramic.]

### 3.2  Descriptive comparison of aggregate area estimates

The darkness detector had the reported area ratio closest to unity among the seven displayed
method summaries. Its ratio of {arm_area_det} corresponds to an absolute relative aggregate
area discrepancy of approximately 1.3%. The darkness-or-Sato union had a ratio of
{arm_union_area}. The closest classical arm on its own was {arm_area_2nd_name} at
{arm_area_2nd}. Table 3 and Figure 4 retain the complete displayed comparison.

{arm_tbl}

[FIGURE arms | Seven arms on the 31 whole fields, each given its own best parameter by the same leave-one-image-out rule and ordered by agreement in total marked area. (a) reported crack area divided by annotated crack area; the vertical line at 1.0 is exact agreement. (b) pixel accuracy expressed as the difference from an all-background prediction on the same images, in percentage points; every arm lies to the left of zero, that is, below what marking nothing would score. The accuracies themselves span 97.7 to 98.2% and are plotted as a difference because a value axis cropped to separate them would misrepresent their similarity. Otsu thresholding on the flattened image is omitted here, marking 99.5% of the frame, and appears in Appendix A. This detector is the dark bar.]

The area comparison identifies a specific strength of the selected configuration: its total
foreground area closely matches the reported reference total. The numerical ordering applies
to that endpoint and to these displayed summaries. It does not establish superiority in
foreground overlap, and Section 5.1 states what it does not establish.

### 3.3  Field-level area error comparison

A lower absolute area error was recorded at the selected setting than at the default setting
in 23 of the {in_n} whole fields, approximately 74% of the evaluated fields. The count
supplements the aggregate comparison by describing the direction of the paired image-level
difference.

### 3.4  The operating-setting sweep, in full

[FIGURE sweep | Reported crack area divided by annotated crack area against the MAD multiplier k, on the 31 whole fields and on the 26 released crops cut from them. Both axes are logarithmic and the horizontal line at 1.0 is exact agreement. The diamond marks k = 6.0, where the whole-field curve crosses unity. The earlier analysis swept only k = 1.0 to 5.0, the leftmost seven points of each series, and selected the largest value it had tested.]

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

[FIGURE ceiling | Pixel accuracy of the reference annotation reduced to its centreline and redrawn at a fixed width, against that width: a prediction exactly correct about where every crack lies and wrong only about how wide it is drawn. The horizontal axis is logarithmic. Dotted lines give the accuracy of an all-background prediction on each collection, and the diamonds mark each curve's maximum. The vertical distance between a dotted line and its diamond is the entire range in which any prediction can move on that collection: 0.708 points on the whole fields and 2.128 on the crops.]

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
