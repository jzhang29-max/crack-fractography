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
subsets originate from different microscopes. **No scale bar can be drawn on any panel
taken from this collection, and none is shown.** The crack area fraction reported throughout
is a dimensionless ratio of pixel counts and does not depend on a pixel size; physical
lengths cannot be derived from these images and none are reported.

For that reason every micrograph panel in this paper — Figures {fig_workflow},
{fig_modality}, {fig_stages} and {fig_measurands} — is drawn from a field of this
laboratory's own corpus at a known pixel size and carries a scale bar, and each caption
states that the field is not part of the evaluated collection. No quantitative result in
Section 3 is taken from those fields.

### 2.2  Detector configuration

The evaluated detector processes an 8-bit grayscale image and applies background correction
before identifying dark candidate regions over seven spatial scales. The scales are 5, 10,
20, 40, 80, 160 and 320 pixels. Candidate selection combines a median absolute deviation
(MAD) criterion with an absolute intensity gate.

Mask processing consists of hole filling, morphological opening and connected-component
filtering, with an opening size of 13 pixels and a minimum retained region area of 40
pixels. Components use 8-connectivity. The learned region classifier is ENABLED in the
scored branch: every surviving component is described by eight shape and intensity
features, scored by a logistic model at its bundled threshold of {clf_thr}, and retained
only if the model calls it crack, with the single exception that a component of at least
50,000 pixels is retained regardless. Those nine fitted numbers are the only fitted
parameters anywhere in this arm. Enabling the classifier is a trade and not an
improvement. One unit set answers this, and all four numbers below come from it: the 26
hand-labelled 512-pixel crops at a MAD multiplier of 5.0, pooled over pixels, with the
one off-specimen void crop excluded because it owns most of the false positives at every
setting. Holding the candidate stage fixed and changing only the classifier, precision
rises {clf_p_off} to {clf_p_on} while recall falls {clf_r_off} to {clf_r_on}, and the
paired per-specimen change in intersection over union is {clf_d_iou} across
{clf_n_spec} specimens, worse on {clf_n_worse} of them (Wilcoxon p = {clf_p}). The same
comparison at the multiplier this paper reports, 6.0, is Figure {fig_parameters}'s own
record and agrees in direction: precision {sw_prec25}, recall {sw_rec25}. **Scores computed for this arm on the laboratory collection are
in sample.** The classifier's deployed bundle records the {clf_n_train_img} images it was
fitted on, and all {clf_n_overlap} of the {clf_n_painted} hand-corrected frames that
carry enough of both verdicts to be scored are among them. A leave-one-frame-out refit of the same recipe, reported in
the supplementary record `sem_classifier_lofo.json`, is the out-of-sample estimate, and
the difference it finds is {clf_leak_p} in precision and {clf_leak_f1} in F1 at frame
scale. The same refit on the 512-pixel crops, holding out each crop's parent micrograph,
moves the pooled precision by {clf_leak_tile_p}.

**The classifier's influence is strongly scale-dependent, and the reason is geometric.**
A crack in a whole micrograph is one very large connected component, and the retention
rule keeps any component of at least 50,000 pixels whatever the model says. Over
{fk_n} frames measured directly, {fk_pct}% of the retained area lies in such components,
which are {fk_reg_pct}% of the components proposed. The classifier therefore decides a
small minority of the retained area at frame scale and most of it on a 512-pixel crop,
where no component approaches that size. Scores from the two unit sets are reported
separately throughout and are not pooled.

**Which collections were scored with the classifier, and which were not.** Everything above describes the configuration this laboratory's own collections were scored at: the hand-corrected scanning-electron frames and the transmission frames were recomputed for it. The public Inconel 718 collection, and every quantity derived from it including the aggregate area agreement and the selection of the MAD multiplier itself, was measured with the classifier bypassed. Those measurements have not been repeated at the present setting, because the source images are a public download that is no longer held on the machine this analysis runs on; recomputing them requires re-obtaining that collection. The distinction has a known direction rather than an unknown one: the classifier only ever removes candidate regions and never adds one, so the retained set with it enabled is a subset of the retained set without it, and the predicted area fraction on that collection can only fall or stay equal. This is stated here rather than left for a reader to discover, because the two configurations differ and a methods section describing only one of them would misdescribe the other.

Table {tbl_settings} lists the reported settings, and Figure {fig_parameters} gives the evidence behind each of them.

[TABLE settings | The detector's reported configuration. One constant, the MAD multiplier, is exposed and swept; the rest are fixed. This table is the configuration the results are reported at; Figure {fig_parameters} carries every constant BOTH detectors read -- fifty of them, including the settings applied before the detector runs and after it -- with the value in use and how each was arrived at.]
| Component | Reported setting |
|---|---|
| Input representation | 8-bit grayscale SEM image |
| Multiscale processing | 5, 10, 20, 40, 80, 160 and 320 px |
| Selected MAD multiplier | {mk_best} |
| Absolute intensity gate | 10.0 |
| Morphological opening size | 13 px |
| Minimum connected-region area | 40 pixels |
| Connectivity | 8-connected components |
| Learned region classifier | Enabled; 8 features, logistic, threshold {clf_thr} |

**On the number of free parameters.** One constant, the MAD multiplier, is exposed and
swept, and it is the only one given a grid in any comparison reported here. It is not the
only constant. The absolute intensity gate is a second threshold, held fixed rather than
fitted in this study. Behind those sit the seven-rung scale ladder and the two size floors,
also fixed. A reader comparing this against a single-parameter classical filter should know
that the filter carries one constant and this configuration carries a frozen preprocessing
budget.

**How every micrograph panel in this paper is displayed.** Each panel is a real intermediate array produced by the shipped code on the field named in its caption, and is contrast-stretched for display between its own 2nd and 98th percentiles; the detector ran on the unstretched frame in every case. No pixel in any panel is added, dilated or removed for visibility. Where a stage's effect is too small to see at panel size it is magnified in an inset, never thickened.

Figure {fig_stages} shows what each of those operations does to a real array, in both
modalities. Three of the stages — the MAD criterion, the morphological opening and the
connected-region floor — produce outputs that are indistinguishable from one another at
print size, differing by a few hundred pixels in a half-million-pixel window, so they are
drawn as one column with the pixels they removed in a second colour and magnified; giving
each its own panel invites a reader to compare panels that cannot be told apart.

**Two stages of the application sit outside the branch evaluated here, and neither
runs in any figure or any number in this paper.** They are the second-pass region growth
over concavity, bridge and interior-fill candidates, and the operator's painted
correction, which overrides every automatic stage. The learned region classifier was a
third until the configuration reported here enabled it; it is now inside the evaluated
branch, and every mask shown and scored has passed through it.

[FIGURE stages | The three operations that change the array, in both modalities, on this laboratory's own fields. Columns: the frame as the detector receives it; the same window after the multiscale background estimate is subtracted, which is the array the darkness criterion is applied to; and the finished mask. Rows: scanning electron microscopy at {wf_sem_nm} nm/px over a {st_sem_fov} micrometre field (top) and transmission X-ray microscopy at {wf_txm_nm} nm/px over a {st_txm_fov} micrometre field (bottom). The two fields of view differ deliberately: the main crack on this SEM field reaches 35.0 micrometres at its widest and the widest marked object on this TXM field reaches 6.1, so one field of view cannot show both. Figure {fig_modality} is where the two appearances ARE compared, and it uses a matched field of view for that reason. Blue is the mask that is scored. Red, in the third column, is what the morphological opening and the connected-region floor removed, drawn at {st_zoom}x magnification in the boxed inset because at panel size it is a few pixels wide; the inset position is the window holding the most removed pixels, found exactly rather than chosen. The removed pixels are magnified, never dilated -- no pixel in any panel of this paper is added for visibility. Each window is the position holding the most mask-boundary pixels, found exactly by a box sum over the summed-area table, which is the same rule as Figure {fig_workflow}: a window chosen for the most MARKED pixels is solid mask wherever the crack is wider than the window, and a panel of flat colour says nothing about where the detector put its edge. The TXM frame is chosen by a rule with two parts, because sharpness alone chose a frame on which the only thing to show was the edge of the mosaic. On every b2 and b3 frame a large share of the marked area sits in regions the field of view cuts off -- 36.5% at best, and 98.9 to 99.8% on all six B3 frames -- and those are the largest objects the detector marks, so any window rule that maximises mask or mask boundary lands on one. A region whose outline is substantially the border of the image is the limit of the field and not a decision the detector made. The frame is therefore the trace-annotated one, of those at or above the corpus median in sharpness, with the largest marked region the field does NOT cut off; sharpness is the 99.5th percentile of gradient magnitude in units of the frame's own intensity spread and is measured for every frame of both collections. The window rule is Figure {fig_workflow}'s and is stated there: where the frame carries an operator's painted crack the window sits on the mask that paint confirms, and otherwise on mask boundary with any region more than 15% of whose own outline lies on the frame border discounted. Both frames here carry paint, so both panels are placed on confirmed detections; the geometric discount is what the fallback would apply, and on this SEM field the main crack runs out of both sides and still sits at 2.3% of its own perimeter. No pixel is removed from any mask by this and no number in the paper depends on it; it decides where to look. Two earlier choices are on the record in the figure's own module: the frame typical by accuracy margin reproduces as a grey smudge, these mosaic averages differing by a factor of three in high-frequency content, and the frame with the strongest painted-crack contrast is readable but has almost nothing marked on it. The rule is a legibility choice and the frame is not a typical one; the distribution these frames sit in is Figure {fig_modality}(b). Neither field belongs to the collection evaluated in Section 3.]

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

**The other quantities the application reports, and what each one is measured from.** Area
fraction is the paper's endpoint, but the software also emits a length, two widths and an
orientation per detected region, and those are what a reader of a crack-measurement study
will want defined. Figure {fig_measurands} puts all of them on one real crack, computed by
the functions the application itself calls rather than by a reimplementation. Two points in
it are worth carrying forward. There are TWO lengths, not one: the network length sums every
branch of the medial axis and the longest crack is the longest tip-to-tip route through it,
and on the region shown they differ by 15 per cent. And both are sums of step lengths, with a
diagonal step counted as the square root of two — a count of skeleton pixels understates a
path length by up to 41 per cent, and dividing such a count by an endpoint distance once gave
819 of 1,503 exported cracks a tortuosity below one, which is geometrically impossible.

[FIGURE parameters | Every constant BOTH detectors read, the value in use, and how each was settled. **Twelve choice graphs over a printed table of all fifty constants**; a constant with a graph names its letter in its row. The ref. column is how the value was settled, and that is the finding: of the fifty, exactly ONE was chosen by a sweep on labelled data, four were settled by a test that had no value to choose, nine were inherited from the earlier pipeline with no recorded provenance and are swept here after the fact, and thirty-six are fixed by construction with no sweep on record anywhere. **Three of the twelve graphs are new, and two of them are adverse.** The closing radius, the denoise sigma and the flattening radius had never been swept in either repository; all three sweep on the same 26 tiles and the same scorer as the rest, so they are swept here. The closing radius scores {sw_close_ship} pooled IoU at the shipped 3 px against {sw_close_best_iou} at {sw_close_best} px, and the denoise sigma {sw_den_ship} at the shipped 1.0 against {sw_den_best_iou} at {sw_den_best}: neither shipped value is the best on its own grid, and both are reported rather than quietly corrected, because the paper evaluates the configuration that was actually run. Panel (f) gives the seven-rung ladder the evidence it never had -- the dashed line is the shipped union and the curve is what ONE radius scores alone, {sw_union} against {sw_single_best_iou} for the best single radius -- so what the ladder buys is now measured instead of asserted. **Model 1, the SEM arm: a darkness rule that proposes, and nine fitted numbers that decide.** (a) the MAD multiplier is the only constant chosen by a sweep: over the 31 public whole fields mean F1 rises to an interior maximum of 0.356 at k = 6 and falls either side, leave-one-image-out selection over the full grid returns the same value, and the paired difference against the application's own k = 5 -- the dotted rule in that panel -- is +0.012 in F1 on 27 of the 31 fields (exact Wilcoxon p = 0.000004); the same comparison on the 26 hand-labelled crops is not resolved (+0.0003, p = 0.35). (b) to (d) were inherited with no recorded provenance and not one sits at its own grid's best value. (b) the absolute darkness gate is not a cleanup term: over the 48 frames carrying a hand correction, switching it off takes recall on painted crack from {fr_gate_on} to {fr_gate_off}, so more than half of what the detector finds at frame scale rests on one unsearched integer, while on the tiles nothing between 2 and 16 of 255 differs from the shipped 10 by more than 0.004 IoU. The two tile curves disagree in sign because one 512 px crop holds an off-specimen void that is pitch black and owns most of the corpus's false positives; with that crop dropped the gate is clearly worth having. (c) the two size floors and (d) the opening radius and labelling connectivity move the pooled tile IoU by less than the plotting symbol over an order of magnitude: the small-object floor is flat to 0.0004 over 0 to 50 px, the 40 px candidate floor costs 0.0015 against the smallest floor tested, the opening costs 0.0041 against no opening at all, and 4- against 8-connected labelling is worth 0.0001. (e) the seven-rung flattening ladder was never searched -- no sweep over any alternative exists in either repository -- and it acts as a union: {sw_ladder_overlap}% of the paint it reaches is reached at two or more radii, and the two largest unique contributions are its extremes, 5 px and 320 px, which is what a scale-matched darkness criterion predicts, since a crack is only reliably dark at radii near its own width. The learned region classifier is ENABLED in the reported configuration, and the choice is a trade rather than an improvement. Pooled over the 25 tiles that exclude the off-specimen flood crop it raises precision to {sw_prec25} while recall falls to {sw_rec25}; on the full 26 tiles, which that one crop's false positives dominate, every metric is lower than with it bypassed. It has no panel because it has no grid to sweep -- a classifier is on or off, and both settings are measured and reported above -- not because it is free of fitted parameters: it spends nine of them plus a threshold, and they are the only fitted parameters in this arm. **Model 2, the TXM arm, a trained per-pixel ensemble**: the mean probability of a 17-channel model and a 273-dimensional hybrid that adds a frozen SAM ViT-H embedding, both fitted on the operator's labelling of 71 frames. (f) the probability threshold 0.60, swept over the same 31 refereed frames as the rest of the transmission accounting and matched on the false-alarm curve; the sweep is IN SAMPLE, since the members were fitted on this paint, and it is therefore evidence about the threshold and not about the model. (g) which members are averaged, by a 5-fold cross-validation over the 71 labelled frames grouped BY IMAGE and not by specimen, so no whole specimen is ever held out. (h) what a SAM tile is, drawn rather than named: 1024 px squares at a stride of 896, overlapping by 128, set that way by construction so neighbouring embeddings stay continuous across their seams; there is no sweep over either number in any repository. (i) the SEM arm's MAD multiplier carried onto transmission data, where **no value of it works**: over those same 31 frames every value on the grid scores below an empty mask, and the paper's 6.0 does so by 9.5 points. That row is why the two arms do not share a detector. **Twenty of the fifty constants appeared in no earlier edition of this figure**: the contrast window with its three-frame exception, the databar probe and the field-of-view finder the SEM chain applies before the detector runs, and the nine-constant width clip and three-constant straight-artefact rejector the transmission mask path applies after it. A constant applied to the data and not declared is an undeclared degree of freedom. Row names are short because the stage box names the stage; every value is parsed out of the deployed source rather than retyped, and the figure's caption file carries the full name, the stage and the provenance of each. **The evidence here is wider than the paper's reported scope, deliberately.** The frame-scale SEM panels are the 48 frames that carried a hand correction when the constants were set -- 20 of specimen series b2 and 28 of specimens the results sections do not report -- and the tile panels are 26 tiles from 13 specimens. That is the corpus these constants were in fact fixed on, and narrowing it after the fact would describe a selection that did not happen. The panels rest on several different unit sets and values may not be compared across them; every number and its source is in the figure's caption file.]

[FIGURE measurands | Every quantity the application measures on a detected region, drawn on the largest marked region the SEM field of Figure {fig_workflow} contains. (a) the region in blue with the whole medial axis in orange; in red, the two tips of the longest tip-to-tip route, the straight chord between them, and the largest circle that fits inside the crack at the 10th, 50th and 90th percentile of width along the axis. (b) the width along that route, with the mean width over the whole axis as the dashed line. (c) each measurand, the rule it is measured by, and its value here. Every number in (c) comes from the shipped measurement functions, called on the region that is drawn; the route drawn in (a) is checked against the length reported in (c) to within one pixel. The tortuosity row is deliberately empty: the shipped definition applies only to an unbranched medial axis and this region has nine branch points, so the software emits no value. Where it does emit one, the figure's own control shows that digitisation alone puts a straight rasterised line between 1.00 and 1.08 according to its angle, so a tortuosity near 1.08 is a staircase and not a wandering crack.]

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
(TXM) frames of austenitic stainless steel spanning the two specimen series the paper
reports on. Those frames carry
hand-made correction masks that mark crack and not-crack explicitly and leave the remainder
unreviewed, so only reviewed pixels are scored: {tx_cov}% of all pixels in those frames were
ruled on. The reviewed area holds {tx_crack_px} crack pixels against {tx_notc_px} not-crack
({tx_ratio_pn}:1), so a false positive is priced by the annotation rather than assumed.
Percentages in Section 4 are therefore percentages of the reviewed area, not of the frame.

TXM frames carry a pixel size of 29.24 nm/px, which is **derived from mosaic geometry — a
30 micrometre viewing window at 0.35 tile overlap over a 9 x 5 mosaic — and not read from
instrument metadata.** Scale bars on TXM panels use that value and scale with it if the
acquisition geometry is corrected.

**Two aggregations, both reported.** The reviewed areas of these frames differ by a factor
of {tpf_area_spread}, so a figure pooled over reviewed pixels weights a frame by how much
of it was painted and one frame can carry a specimen group. Every pooled quantity in
Section 4.3 is therefore reported beside the mean of the per-frame values, which gives each
frame one vote. The two answer different questions — what happens to a pixel, and what
happens to a frame — and on this collection they disagree, so neither is given alone.

**Whether an annotation is a trace or a region, as a measured quantity.** Both of this
laboratory's collections are painted rather than traced, and the two are not painted alike.
The share of annotated pixels lying more than 50 px from the edge of the annotation
separates the two cases: a stroke of any width has almost none, a filled region has a great
deal. It is reported per collection in Sections 4.3 and 4.4, it decides which frames the
micrograph panels may show, and it is the reason the overlap measures in Section 4.4 are
each reported beside what a geometrically correct three-pixel trace of the same annotation
scores against that annotation.
