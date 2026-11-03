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

The three rungs differ in what they mark, not by a little. On the window of Figure {fig_txmstages} the
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

[TABLE txmiou | One deployed model on one collection, scored three ways. The three rows differ only in which pixels are admitted and how frames are combined; the spread between them is larger than any difference this paper reports between methods.]
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
and on the frame shown in Figure {fig_txmstages} the recall is {tm_wf_rec} while only {tm_wf_fp}% of the
pixels the operator painted as not-crack are marked.

### 4.2  What the overlap score is measuring

[FIGURE txmceiling | What a TXM overlap score rewards. (a) for each of {tm_ld_n} frames, the IoU the deployed model reaches against the operator's stroke (circles) and the IoU a physically correct crack trace could reach against that same stroke (triangles), plotted against the median width of the stroke on that frame. The correct trace is a construction, not a model: the annotation's own centreline redrawn three pixels wide, so it is exactly right about where every crack runs and wrong only about how wide it is drawn. Spearman correlations with stroke width are given beside each series. (b) the same two quantities as specimen-group medians, with each group's median stroke width beneath its label. Both series use one IoU convention, restricted to pixels an operator adjudicated, and the model's mask is taken with the operator's corrections excluded so that the comparison is not circular.]

The reference in this collection is a wide brush. The operator's stroke has a median width of
{tm_ld_width} px and ranges from {tm_ld_wmin} to {tm_ld_wmax} px, over a crack whose dark core
is a few pixels across. An IoU scored against that stroke therefore pays for covering the
stroke, and the two series in Figure {fig_txmceiling} show what that is worth: the annotation's own
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
treats the overlap measures as secondary, and it is why the ceiling in Figure {fig_sensitivity}(b) is reported
beside them rather than after them.

### 4.3  The SEM detector carried across

[FIGURE txm | The same detector as Section 3, with the same constant, applied to transmission X-ray microscopy of austenitic steel. (a)-(c) a B3 frame and (d)-(f) a B2 frame, the two specimen series the paper reports on and the two whose behaviour differs most: (a, d) the frame, contrast-stretched per crop for display only, the detector having run on the unstretched image; (b, e) the annotated crack in blue; the reviewed area is at full brightness and everything an annotator did not rule on is dimmed and excluded from every number, so the bright islands are reviewed image and not features of the microstructure; (c, f) the prediction, green where it agrees with the annotation, orange where it marks reviewed not-crack, blue where annotated crack was missed. The frame shown for each group is the one with the longest annotated crack among the frames whose annotation is a trace rather than a filled region, the second condition being that at most a quarter of the annotated pixels lie more than {pr_px} px inside the annotation; {pr_txm_above} frames of the {pr_txm_n} fail it, and excluding a frame from a panel does not exclude it from any number here. (g) pixel accuracy over reviewed pixels, expressed as the difference from an all-background prediction in percentage points. (h) reported crack area divided by annotated crack area, the vertical line at 1.0 being exact agreement. Panels (g) and (h) are computed over every frame of both groups, and the B3 bars should be read with Section 4.3's measurement of what that group's painted crack is: its median painted pixel has essentially zero optical density. Scale bars 5 micrometres at {tm_nm} nm/px (Section 4).]

The SEM detector was carried unchanged to {tx_n} TXM frames. Over the reviewed area, crack is
{tx_prev}% and an all-background prediction scores {tx_empty}% accuracy.

**Pooled, the configuration clears the line, and the pooled figure is the wrong one to
read.** It records {tx_acc}% accuracy, {tx_margin} percentage points ABOVE an
all-background prediction, and reports {tx_area} times the annotated crack area at a
recall of {tx_recall}. It also clears both no-information comparators comfortably — an
Otsu darkness cut with no model records {tx_otsu_acc}% and marking every pixel
{tx_all_acc}%.

That pooled margin is one of the two groups. **Against an all-background prediction B3
stands at {tx_b3_margin} points and B2 at {tx_b2_margin}**, both signed, and the pooled
number is the area-weighted average of the two. It describes neither.

[TABLE txmgroups | The pooled transmission result broken out by specimen group, over reviewed pixels only. The groups do not behave alike, and the pooled figure is not a description of any of them.]
| Specimen group | Frames | Crack % of reviewed area | Accuracy | All-background | Recall | Area reported / annotated |
|---|---|---|---|---|---|---|
| B3 | {tx_b3_n} | {tx_b3_prev}% | {tx_b3_acc}% | {tx_b3_empty}% | {tx_b3_recall} | {tx_b3_area} |
| B2 | {tx_b2_n} | {tx_b2_prev}% | {tx_b2_acc}% | {tx_b2_empty}% | {tx_b2_recall} | {tx_b2_area} |

One group transfers in these pooled units, and the rest of this section is about how much
that sentence depends on the pooling and on the annotation underneath it. On B3 the
detector records {tx_b3_acc}% accuracy against {tx_b3_empty}% for an all-background
prediction, a margin of {tx_b3_margin} points, at a recall of {tx_b3_recall} and an area
ratio of {tx_b3_area}. On B2 the reported area is close to correct at {tx_b2_area} while
the recall is {tx_b2_recall}, so the right quantity of foreground is placed substantially
in the wrong locations.

**What B3's agreement is with.** On the B3 frames the median painted-crack pixel has an
optical density of essentially zero — {fb_b3_crack}% of the painted crack lies below
{fb_thresh} on the median frame, where {fb_b3_frame}% of the frame does, against
{fb_b2_crack}% and {fb_b2_frame}% on B2. The same statistic on those frames' painted
NOT-crack is {fb_b3_notcrack}%, so this is specific to the class scored and is not an
annotator working carelessly past the specimen edge, which would show on both labels.
Zero optical density is the signal of a beam path crossing no material, whether because
it misses the specimen or because the crack there has opened through the full thickness.
Either way it is not a test of the detection rule: the median painted-crack pixel on a B3
frame reaches the detector as {fb_b3_img8} of 255 and {fb_b3_gate}% of the painted crack
is below the absolute darkness floor of {fb_gate}, which marks it unconditionally whatever
the relative criterion decides. Section 4.5 gives the split: {mc_b3_prop}% of B3's painted
crack is proposed and most of that comes from the floor alone. **B3's margin should be
read as a measurement of the annotation, not of the detector.**

[FIGURE txmcurve | The detector's one free constant, the MAD multiplier k, swept on the TXM collection over the same seven values as Section 3.4. (a) reported crack area divided by annotated crack area; the axis is logarithmic and the horizontal line at 1.0 is exact agreement. (b) pixel accuracy minus the accuracy an all-background prediction reaches on the same pixels; the horizontal line at zero is that prediction, so a curve below it describes a configuration that would do better by marking nothing. Each specimen group is drawn separately and the dashed line is the pooled value. Both panels are over reviewed pixels only.]

**No setting of the constant changes which group clears the line.** Across the whole
grid, B3 stays above an all-background prediction at every value, from {tx_k3_b3} to
{tx_k10_b3} points, and B2 stays below it at every value. The pooled curve, being the
average of the two, crosses zero between k = 3 and k = 4 and reaches its best at
{tx_pool_best} points at k = {tx_pool_bestk} — a crossing that belongs to the weighting
and not to either group. Both curves are flat above k = 7, so the sweep has nothing
further to offer: this is not a configuration that was set wrongly. B2 is the group where
the constant does buy something, and only in the area units — the reported area reaches
{tx_b2_bestarea} times the annotated at k = {tx_b2_bestareak}, essentially exact, while
the accuracy stays {tx_b2_bestareamargin} points below marking nothing. The right quantity
of foreground in the wrong places is what that combination means.

[FIGURE txmbudget | (a) where the detector's marked area goes on each specimen group, at k = 6: the part that falls on annotated crack and the part that falls on reviewed not-crack, both as a percentage of the reviewed area, with the annotated crack area drawn as a dashed outline for comparison. (b) the same detector pooled over all {tx_n} frames beside the two no-information arms it has to beat, as pixel accuracy minus the accuracy an all-background prediction reaches. Reviewed pixels only, so the denominator is the area a human ruled on and not the frame.]

Panel (a) separates two different failures that the pooled accuracy adds together. On B3
the detector finds most of the annotated crack, at a recall of {tx_b3_recall}, and marks
{tx_b3_fpratio} pixels of reviewed not-crack for every pixel of crack it finds. On B2 the
blue part of the bar is small — a recall of {tx_b2_recall} — so the annotated crack is
largely not marked at all and the marked area is somewhere else, at {tx_b2_fpratio} pixels
of reviewed not-crack per pixel of crack found. Those are two different failures and a
single accuracy cannot tell them apart. Panel (b) is the comparison the arms are entitled to — the detector is
{tx_vs_otsu} points better than an Otsu darkness cut with no model and {tx_vs_all} points
better than marking every pixel, and still below an empty mask.

**The transfer fails at the first stage, not the last, and Figure {fig_modality}(e) says so
in the criterion's own units.** The proposal stage keeps a pixel when it is darker than its
frame's median by more than k scaled median absolute deviations, at any radius of the scale
ladder. Measuring the operator's painted crack on that axis — which is the quantity
Figure {fig_modality}(e) plots, with the reconstruction of the real proposal mask from it
checked against the installed detector to within {mc_recon} pixel on every frame — the
median painted-crack pixel sits at {mc_txm_k} on the TXM frames against an operating point
of {om_k}, and below it on {mc_txm_below} of the {mc_txm_n} frames. The median frame has
{mc_txm_prop}% of its painted crack proposed at all. The same measurement on the SEM side
gives {mc_sem_k} and {mc_sem_prop}%, below the operating point on {mc_sem_below} of
{mc_sem_n} frames, so this is not a TXM-specific pathology but a margin that is thinner in
TXM.

That is a different failure from the one the pooled accuracy suggests: the configuration is
not marking the wrong things so much as not proposing the right ones, and the third column
of Figure {fig_stages} shows that the opening and the area floor then remove almost nothing
of what little was proposed. It also separates cleanly by specimen group, which the pooled
figure cannot: the median painted-crack pixel sits at {mc_b3_k} on B3, where {mc_b3_prop}%
of the painted crack is proposed, and at {mc_b2_k} on B2, where {mc_b2_prop}% is. B3's
share is not evidence that the criterion fires on a crack there, for the reason given in
Section 4.3: most of what it proposes on those frames is proposed by the absolute floor,
on pixels at essentially zero optical density.
The flattening radii and the darkness multiplier were both set where a crack is a dark line
a few pixels across; a TXM mosaic of a thick specimen records it as a broad low-density
band, and a criterion written for the first does not fire on the second at any setting of
its one constant, which is what Figure {fig_txmcurve}(b) shows from the other direction.

**Every number above weights a frame by its area, and that is doing most of the work.**
A pooled accuracy counts each refereed pixel once, so a frame with a large painted region
counts for many frames with small ones, and the painted areas here differ by a factor of
{tpf_area_spread}. Giving each of the {tpf_n} frames one vote instead gives a different answer: the
mean of the per-frame margins is {tpf_mean_all} points rather than {tx_margin}, the median
is {tpf_med_all}, and {tpf_pos_all} of the {tpf_n} frames are individually above an
all-background prediction. The two aggregations agree in sign here, which they did not on
the wider corpus, but they differ by enough that reporting either alone would be a choice
the reader cannot see.

The same split runs through the groups. The table gives, for each group, the pooled margin
in percentage points, the mean of that group's per-frame margins, the pooled margin
recomputed with the group's single largest frame removed, and that frame's share of the
group's reviewed crack pixels.

[TABLE txmpool | Pooled against per-frame aggregation, by specimen group, in percentage points of accuracy margin. The last two columns recompute the pooled margin with each group's single largest frame removed and give that frame's share of the group's reviewed crack pixels, which is what the two aggregations disagree about.]
| Group | Frames | Pooled | Frame mean | Largest dropped | Largest share |
|---|---|---|---|---|---|
| B3 | {tpf_b3_n} | {tpf_b3_pool} | {tpf_b3_mean} | {tpf_b3_cut} | {tpf_b3_share}% |
| B2 | {tpf_b2_n} | {tpf_b2_pool} | {tpf_b2_mean} | {tpf_b2_cut} | {tpf_b2_share}% |

B3 stays positive under both, at {tpf_b3_pool} points pooled and {tpf_b3_mean} as a mean
over its {tpf_b3_n} frames. B2 moves from {tpf_b2_pool} to {tpf_b2_mean}. Neither
aggregation is wrong — a pooled figure answers what happens to a pixel and a per-frame
mean answers what happens to a frame — and both are reported because they are different
questions, not because one corrects the other.

**And the group that transfers under both aggregations does not carry a crack trace.**
The B3 group is {tpf_b3_n} frames, and a single one of them holds {tpf_b3_share}% of the
group's reviewed crack pixels.

What that frame's annotation is matters as much as how large it is. The share of
annotated pixels lying more than {pr_px} px inside the annotation separates a stroke that
follows a crack from a filled region: a stroke of any width has almost none, and
{pr_txm_zero} of the {pr_txm_n} frames record exactly 0.0%. That B3 frame records
{pr_txm_max}%, the highest in the collection. Across the collection the median is
{pr_txm_med}% and {pr_txm_above} of the {pr_txm_n} frames exceed 25%; by group, B3 has
{pr_b3_above} of {tpf_b3_n} and B2 {pr_b2_above} of {tpf_b2_n}, with group medians of
{pr_b3_med}% and {pr_b2_med}%. On those frames the annotator has marked the open
crack mouth as an area rather than tracing a line, so what the detector is scored against
there is a large dark region, which a darkness rule finds easily. **The group where the
carried-over detector clears an all-background prediction is also the group holding the
most region-like annotation in the collection**, and the two facts should not be
separated. Figure {fig_txm} shows a B3 frame whose annotation is a trace, for that reason.

**This is reported as a transfer result and not as a capability.** Two specimen groups
give two answers of opposite sign, each group is a small number of frames, and the pooled
figure is an area-weighted mean over two distinct measurements rather than an estimate of
one. One of the two, as Section 4.3 sets out, is scored against an annotation whose
painted crack lies at essentially zero optical density. The acquisition parameters for this collection —
instrument, beam energy, voxel size at the specimen, reconstruction algorithm — are not
recorded with the data, and the pixel size used for the scale bars is derived rather than
measured. What the section establishes is narrow and still worth stating: a constant fitted on
SEM steel in one laboratory, carried without modification to a different imaging physics,
clears both no-information comparators on all four groups, and clears an all-background
prediction on one of them when the comparison is pooled over pixels and on
{tpf_pos_all} of the {tpf_n} individual frames.

**Section 4.1 and Section 4.3 are not in conflict.** The collection's own detector reaches a
whole-frame median IoU of {tm_wf_iou} where the carried-over SEM detector falls below an
all-background prediction, which is the expected ordering: one was fitted on this modality and
the other was not. What Section 4.2 adds is that neither number should be read as a distance
from the crack. The frame counts also differ from measurement to measurement — {tm_cv_n}
for the grouped cross-validation, {tm_ld_n} for the labelled-domain median, {tm_wf_n} for
the whole-frame median, {tx_n} for the carried-over detector in Section 4.3 and
{om_txm_n} for the overlap measures in Section 4.4, according to which frames carry the
labels each measurement needs — and they are not pooled anywhere.

### 4.4  Precision, recall and F1 on this laboratory's own two collections

[FIGURE txmoverlap | Overlap measures for the crack class on this laboratory's own two collections, scored over reviewed pixels only and averaged over frames so that no single frame carries a collection. (a) mean precision, recall and F1; the error bar is one standard deviation over frames and the horizontal rule drawn on each bar is what that collection's own annotation scores against itself after being reduced to its centreline and redrawn three pixels wide — a prediction exactly right about where every crack runs and right about its width. (b) every frame as one point, precision against recall, with curves of constant F1. SEM is the detector of Section 3 on {om_sem_n} hand-corrected SEM frames; TXM is the same detector, same constant, on {om_txm_n} TXM frames.]

Section 3.6 reports these three measures for the public collection, where every pixel of
the annotation carries a verdict. This section reports them for the two collections the
laboratory produced itself, at the same constant k = {om_k}, averaged over frames rather
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
reader should stand nearer to is not something this annotation can settle. Section 3.6
reports the public collection as values rather than as brackets for exactly this reason:
there, every pixel carries a verdict.
