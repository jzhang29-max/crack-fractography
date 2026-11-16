## 2  Materials and methods

### 2.1  Image collection and evaluation units

The evaluation uses the two collections this laboratory produced itself. A frame enters
if it carries an explicit painted verdict for both crack and not-crack, which is the
condition every score in this paper is computed under; {om_sem_n_all} scanning electron
(SEM) and {om_txm_n_all} transmission X-ray (TXM) frames meet it. **Every number quoted
in this paper is further restricted to specimen series b2 and b3**, which is {om_sem_n}
of those SEM frames and {om_txm_n} of the TXM frames, and that restriction is the scope
of the work rather than a selection made after seeing results. Figure {fig_scores} is the
one exception and says so: its bars are drawn over every refereed frame of each arm, so
they do not equal the restricted numbers in the text, and its caption file carries both
unit sets. Each frame is one evaluation unit, and every quantity is a mean over frames,
one vote per frame, unless it is named as pooled.

**The annotation is a painted correction mask rather than a trace, and that governs what
can be read off it.** An operator marked crack and not-crack explicitly and left the rest
of each frame unruled, so every pixel carries one of three states: crack, not-crack, or no
verdict. Only pixels carrying a verdict are scored. Two consequences follow, and both are
carried through every result rather than noted once.

First, a painted stroke is far wider than the feature it marks — {om_sem_width} px on the
SEM frames and {om_txm_width} px on the TXM frames at the 90th percentile — so an overlap
score computed against it rewards a mask for reproducing the stroke. Every such score in
Section 3 is therefore reported beside what a geometrically correct three-pixel trace of
the same annotation scores against that annotation, which is the only way to tell a mask
that is well placed from one that is merely wide.

Second, the unruled remainder carries no verdict, so a precision computed on these frames
is a bracket and not a value. Its ends are the assumption that every marked pixel nobody
ruled on is correct and the assumption that every one is wrong. Both ends are reported
wherever a precision is.

Pixel sizes are known for both collections and every micrograph panel in this paper
carries a scale bar; the transmission value and its provenance are given in Section 2.4.
Unlike the summary measures, the panels are drawn from the same frames the results are
computed on, so a reader can check a number against the field it came from.

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

Table {tbl_settings} lists the reported settings, and Figure {fig_parameters} gives the evidence behind each of them.

[TABLE settings | The detector's reported configuration. One constant, the MAD multiplier, is exposed as a setting; the rest are fixed. This table is the configuration the results are reported at; Figure {fig_parameters} carries the constants BOTH detectors read -- forty-one of them, including the settings applied before the detector runs and after it -- with the value in use and how each was arrived at.]
| Component | Reported setting |
|---|---|
| Input representation | 8-bit grayscale SEM image |
| Multiscale processing | 5, 10, 20, 40, 80, 160 and 320 px |
| MAD multiplier | {om_k} |
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

**Two stages of the application sit outside the branch evaluated here, and neither
runs in any figure or any number in this paper.** They are the second-pass region growth
over concavity, bridge and interior-fill candidates, and the operator's painted
correction, which overrides every automatic stage. The learned region classifier was a
third until the configuration reported here enabled it; it is now inside the evaluated
branch, and every mask shown and scored has passed through it.


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

[FIGURE parameters | Every constant BOTH detectors read, the value in use, and how each was settled. **Five choice graphs over a printed table of all forty-one constants**; a constant with a graph names its letter in its row. The ref. column is how the value was settled, and that is the finding: of the forty-one, NOT ONE was chosen by a sweep on data this paper reports, four were settled by a test that had no value to choose, and thirty-six are fixed by construction with no sweep on record anywhere. The MAD multiplier is the one constant that is neither: its value is adopted, and the ref. column says so rather than claiming evidence the paper does not present. Nine further constants carried no recorded provenance at all; they and the five panels that swept them after the fact have been removed from this figure, and their sweeps remain in the supplementary records. **Panel (b) gives the seven-rung ladder the evidence it never had -- the dashed line is the shipped union and the curve is what ONE radius scores alone, {sw_union} against {sw_single_best_iou} for the best single radius -- so what the ladder buys is now measured instead of asserted. **Model 1, the SEM arm: a darkness rule that proposes, and nine fitted numbers that decide.** (a) and (b) are the seven-rung flattening ladder, which was never searched -- no sweep over any alternative exists in either repository. (a) shows it acts as a union: {sw_ladder_overlap}% of the paint it reaches is reached at two or more radii, and the two largest unique contributions are its extremes, 5 px and 320 px, which is what a scale-matched darkness criterion predicts, since a crack is only reliably dark at radii near its own width. (b) gives the ladder the evidence it never had -- the dashed line is the shipped union and the curve is what ONE radius scores alone, {sw_union} against {sw_single_best_iou} for the best single radius -- so what the ladder buys is measured instead of asserted. The learned region classifier is ENABLED in the reported configuration, and the choice is a trade rather than an improvement. Pooled over the 25 tiles that exclude the off-specimen flood crop it raises precision to {sw_prec25} while recall falls to {sw_rec25}; on the full 26 tiles, which that one crop's false positives dominate, every metric is lower than with it bypassed. It has no panel because it has no grid to sweep -- a classifier is on or off, and both settings are measured and reported above -- not because it is free of fitted parameters: it spends nine of them plus a threshold, and they are the only fitted parameters in this arm. **Model 2, the TXM arm, a trained per-pixel ensemble**: the mean probability of a 17-channel model and a 273-dimensional hybrid that adds a frozen SAM ViT-H embedding, both fitted on the operator's labelling of 71 frames. (c) the probability threshold 0.60, swept over the same 31 refereed frames as the rest of the transmission accounting and matched on the false-alarm curve; the sweep is IN SAMPLE, since the members were fitted on this paint, and it is therefore evidence about the threshold and not about the model. (d) which members are averaged, by a 5-fold cross-validation over the 71 labelled frames grouped BY IMAGE and not by specimen, so no whole specimen is ever held out. (e) what a SAM tile is, drawn rather than named: 1024 px squares at a stride of 896, overlapping by 128, set that way by construction so neighbouring embeddings stay continuous across their seams; there is no sweep over either number in any repository. the SEM arm's MAD multiplier carried onto transmission data is no longer drawn here, where **no value of it works**: over those same 31 frames every value on the grid scores below an empty mask, and the paper's 6.0 does so by 9.5 points. That row is why the two arms do not share a detector. **Twenty of the constants appeared in no earlier edition of this figure**: the contrast window with its three-frame exception, the databar probe and the field-of-view finder the SEM chain applies before the detector runs, and the nine-constant width clip and three-constant straight-artefact rejector the transmission mask path applies after it. A constant applied to the data and not declared is an undeclared degree of freedom. Row names are short because the stage box names the stage; every value is parsed out of the deployed source rather than retyped, and the figure's caption file carries the full name, the stage and the provenance of each. **The evidence here is wider than the paper's reported scope, deliberately.** The frame-scale SEM panels are the 48 frames that carried a hand correction when the constants were set -- 20 of specimen series b2 and 28 of specimens the results sections do not report -- and the tile panels are 26 tiles from 13 specimens. That is the corpus these constants were in fact fixed on, and narrowing it after the fact would describe a selection that did not happen. The panels rest on several different unit sets and values may not be compared across them; every number and its source is in the figure's caption file.]

[FIGURE measurands | Every quantity the application measures on a detected region, drawn on the largest marked region the SEM field of Figure {fig_flow} contains. (a) the region in blue with the whole medial axis in orange; in red, the two tips of the longest tip-to-tip route, the straight chord between them, and the largest circle that fits inside the crack at the 10th, 50th and 90th percentile of width along the axis. (b) the width along that route, with the mean width over the whole axis as the dashed line. (c) each measurand, the rule it is measured by, and its value here. Every number in (c) comes from the shipped measurement functions, called on the region that is drawn; the route drawn in (a) is checked against the length reported in (c) to within one pixel. The tortuosity row is deliberately empty: the shipped definition applies only to an unbranched medial axis and this region has nine branch points, so the software emits no value. Where it does emit one, the figure's own control shows that digitisation alone puts a straight rasterised line between 1.00 and 1.08 according to its angle, so a tortuosity near 1.08 is a staircase and not a wandering crack.]

**An all-background reference point accompanies every accuracy figure in this manuscript.**
Crack occupies a few per cent of a micrograph, so predicting no crack anywhere already
scores {sa_sem_bg}% pixel accuracy on the SEM collection and {sa_txm_bg}% on the TXM
collection. **Every pixel accuracy in this paper, and its baseline, is computed over
every refereed frame of its arm — the unit set Figure {fig_scores} draws, not the
b2/b3 restriction the other measures use** — because the all-background baseline is a
property of the corpus and is read off that plate. The detectors score {sa_sem_acc}% and {sa_txm_acc}%. One of those sits a
hundredth of a point above its baseline and the other sits below it, which is what the
measure is worth at this prevalence and why no accuracy appears in this paper without
the all-background figure beside it.

### 2.4  Cross-modality evaluation

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
deal. It is reported per collection in Sections 3.1 and 4.3, it decides which frames the
micrograph panels may show, and it is the reason the overlap measures in Section 3.1 are
each reported beside what a geometrically correct three-pixel trace of the same annotation
scores against that annotation.
