## 3  Results

### 3.1  Precision, recall and F1 on this laboratory's two collections

Precision, recall and F1 are computed over the crack class alone and discard the
pixels that are background in both the prediction and the annotation. This section
reports them for the two collections this laboratory produced itself, at the same constant k = {om_k}, averaged over frames rather
than pooled over pixels: pooling lets one frame carry a collection, and in the TXM set one
frame holds {tpf_b3_share}% of its group's reviewed crack.

On the {om_sem_n} SEM frames that carry both a painted crack and a reviewed not-crack
verdict, the mean precision is {om_sem_prec}, the mean recall {om_sem_rec} and the mean F1
{om_sem_f1}, with standard deviations over frames of {om_sem_precsd}, {om_sem_recsd} and
{om_sem_f1sd}. On the {om_txm_n} TXM frames the same three are {om_txm_prec},
{om_txm_rec} and {om_txm_f1}, with standard deviations {om_txm_precsd}, {om_txm_recsd} and
{om_txm_f1sd}. The spread is as large as the difference between the collections, and on
TXM it is structured by specimen group rather than scattered.

**Two things have to be read with those six numbers, and both of them are larger than the
numbers.**

The first is the brush. Neither annotation is a crack trace; both are strokes far wider
than the feature, {om_sem_width} px wide on the SEM frames and {om_txm_width} px on the TXM
frames at the 90th percentile. Reducing each frame's own annotation to its centreline and
redrawing it three pixels wide gives a prediction that is exactly right about where every
crack runs, and against the stroke it came from it scores an F1 of {om_sem_cf1} on the SEM
frames and {om_txm_cf1} on the TXM frames. The detector scores {om_sem_f1} and
{om_txm_f1}. It is above that reference on {om_sem_above} of {om_sem_n} SEM frames and
{om_txm_above} of {om_txm_n} TXM frames. **An F1 measured on these collections therefore
ranks how closely a mask reproduces the annotator's stroke, and the detector outscores a
geometrically correct trace because it marks wide, not because it is better located.**
This is the same statement Section 4.2 makes for the collection's own detector, measured
on a second detector and a second modality.

The SEM annotation is the wider of the two by this measure, not the narrower. On the
{pr_sem_n} SEM frames the share of annotated pixels lying more than {pr_px} px inside the
annotation has a median of {pr_sem_med}% and reaches {pr_sem_max}%, and {pr_sem_above} of
the {pr_sem_n} exceed 25%; the corresponding TXM figures are a median of {pr_txm_med}% and
{pr_txm_above} of {pr_txm_n}. On more than half of this laboratory's own SEM frames the
reference is therefore closer to a blocked-out area than to a traced line, which is the
direct reason the SEM precision in this section is high while its ceiling is low: there is
a great deal of annotated area to land inside.

The second is the denominator. Neither collection adjudicates the whole frame, so a
precision computed on it is a bracket rather than a value. The figures above exclude
unreviewed pixels at both ends, which assumes every marked pixel nobody looked at is
correct; at the other end, counting every one of them as wrong, the mean precision is
{om_sem_lo} on the SEM frames and {om_txm_lo} on the TXM frames, and the mean F1 is
{om_sem_f1lo} and {om_txm_f1lo}. The true value lies between the two, and which end a
reader should stand nearer to is not something this annotation can settle.

### 3.2  What the two errors look like

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
rather than a number. Each failure is also concentrated in a few frames, and in the TXM over-counting it is concentrated in a single OBJECT: 98.8% of the over-counted area of the worst TXM frame is one connected low-attenuation region the operator rejected. A panel cut from that frame would be a picture of that object, so the over-counting column excludes frames whose error is that concentrated and the caption says what was excluded and why. The pictures therefore say what the two failures look like where they are a tendency, and the measurements in Sections 3.1 and 4.3 say how much of each there is and how unevenly it is spread; neither reading substitutes for the other.

[FIGURE scores | (a) precision, recall, F1 and whole-frame pixel accuracy for each arm over every frame it scores, as a mean over frames with one vote per frame; pooling over pixels instead would hand the answer to the largest frame, and these differ in area by a factor of two hundred. The whisker under precision and F1 is where each would fall if every marked pixel nobody adjudicated were counted a false positive: a bound on unadjudicated pixels, not a measurement of them. The hatched bar is pixel accuracy and the rule across it is what predicting no crack at all would score -- crack is a few per cent of a frame, so accuracy is high on both arms and sits at or below that rule, which is why it is not the headline. The electron scores are IN SAMPLE: 45 of the 48 hand-corrected frames are images the region classifier was fitted on. (b) held-out intersection over union for the transmission model across its retraining rounds, with the corrected pixel count printed under each; the count is flat across these rounds, so the gain is the recipe and not the volume of correction.]

[FIGURE counting | The two errors, on one field of each modality, each marked by the detector that modality actually ships. Columns: the window holding the most over-counted pixels, and the window holding the most under-counted. **Each window is drawn twice: the micrograph alone, then the same pixels with the comparison on top**, so what the detector reacted to can be read beside what was concluded from it. The figure's record carries, for each panel, the median displayed grey of that error class beside the crack both parties accept and the uncontested matrix, which says which failures intensity could have separated and which it could not. Top row, a {cnt_sem_spec} field at {cnt_sem_nm} nm/px marked by the shipped SEM detector -- the darkness rule followed by the region classifier. That field is one of the 45 images the classifier was fitted on, so this row is IN SAMPLE in the same way the transmission row below it is: recall {cnt_sem_rec} over the {cnt_sem_crack_px} pixels the operator painted crack. That operator ruled {cnt_sem_notcrack_px} pixels of it not crack, so both error kinds are measurable on it and all four of its panels report a measured share: precision {cnt_sem_prec}, recall {cnt_sem_rec}. An earlier edition drew the field with the best agreement of its specimen without requiring that, and the field it chose carried no not-crack verdict at all, so its over-counting panels could print no percentage. The selection rule is unchanged; it now draws from frames an operator ruled in both directions. Bottom row, a {cnt_txm_spec} field at {cnt_txm_nm} nm/px marked by the trained transmission model -- seventeen image channels and a frozen SAM embedding, the mean of two fitted members cut at 0.60: precision {cnt_txm_prec}, recall {cnt_txm_rec}. **That transmission field is inside the model's training set.** No labelled frame was held out when the deployed members were fitted, so those two numbers are in-sample; the out-of-sample estimate for the same model is the grouped cross-validation reported in Section 4.3, and the two must not be read as one number. Blue is marked area the operator agrees with, red is marked area the operator ruled not crack, green is the operator's crack that was not marked, and grey is pixels nobody adjudicated, which are neither an error nor an agreement -- counting them either way is what moves a precision of 0.99 to 0.29. Each window is a multiple of its own frame's 90th-percentile paint stroke rather than a fixed field of view: the two frames differ by more than fourfold in pixel size, and a fixed micrometre window came out wider than the SEM frame is tall, which silently disabled every placement constraint. The multiple is six on both rows. Frame and multiple were chosen together by search: every eligible SEM field was crossed with five window sizes and the pairs ranked on the WORSE of their two panels, by the share of the panel carrying a verdict of any kind. An operator adjudicated {cnt_txm_ref}% of the transmission frame and {cnt_sem_ref}% of the SEM one. Within the frame the window is placed by an exact box sum at the position holding the most pixels of that panel's error kind -- or, where that error kind does not occur on the frame at all, at the position holding the most confirmed detection, which the figure's record states per panel -- subject to that error kind being at most a quarter of the window, at most a quarter marked but unreviewed, at most 5% off-specimen black, a floor on operator-confirmed mask so the error is seen beside a correct detection, and a bound on the straight edge of the annotated region; the constraints relax one at a time, weakest first, and none was relaxed on any panel here. Each frame is the best-agreeing eligible field of its specimen, which flatters both rows, and every candidate and every rejection is in the figure's record. The ambient field MAR_Amb_HIP_CBS_0006 is the only HIP field that can be scored in both directions, and it is what this figure drew in its previous edition; eleven of the thirteen HIP frames carrying a mask are one-sided in the way the hydrogen-charged field is, Cast_24hr_SE_Side_006 among them (3,709,448 crack, 0 not-crack), and the hydrogen-charged MAR fields carry no correction mask at all.]
