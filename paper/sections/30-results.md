## 3  On public SEM data with pixel-exact ground truth

One set: the Inconel 718 crack class of a public cross-material microstructure collection
(Zenodo 23045328, CC BY 4.0), {in_n} whole 1024 px fields of a nickel superalloy at
{in_prev}% crack prevalence. It is the only public crack segmentation data we found in this
modality and material class; Section 7 records what else was searched and rejected.

Scoring is at 0 px tolerance with `mad_k` chosen leave-one-image-out. Two properties of the
data had to be established before any score could be trusted: the masks are **anti-aliased
binary** rather than strictly two-valued, so the scorer checks bimodality and refuses a
mask that fails it; and the images are **16-bit TIFFs**, where an ordinary 8-bit conversion
made the detector find almost nothing before it was caught. Taking the high byte
reproduces the dataset
authors' own 8-bit PNGs exactly, so that is the conversion used.

We report whole fields rather than the collection's released crops. Every one of the
{in_crop_src} source images behind those crops also appears among the originals, so the two
are not independent sets, and the crops are cut around their cracks — which raises
prevalence from {in_prev}% to {in_crop_prev}% and the score with it, with no change to the
detector.

### 3.1  What it scores

[FIGURE P1 - public scores]

At the operating point of Section 3.2 the detector marks {ag_best_mark}% of the field where
the annotator marked {ag_best_lab}%: an area-fraction agreement of **{ag_best}x**, with
accuracy {ag_best_acc}% and specificity {ag_best_spec}%. An empty mask scores
{in_empty_acc}% accuracy on these fields and a full one {in_lab_pct}%, so accuracy alone
separates very little here; the agreement does, and Section 3.4 shows no classical arm
matches it.

The same detector on the dataset's released crops reaches accuracy {cb_acc}% against an
empty mask's {in_crop_empty_acc}%, a margin of {cb_margin} points, at specificity
{cb_spec}%.

### 3.2  The one free constant, and where the sweep stopped

[FIGURE P2 - operating curve]

`mad_k = {mk_ship}` was fitted on SEM steel in a different laboratory, on a different alloy,
years before this dataset existed. An earlier draft reported that it was the best of seven
values tested here and that the curve fell away on either side, and offered that as the
paper's strongest result.

**It was the largest value tested.** The seven rungs ran from 1.0 to {mk_ship}, the score
was still climbing at the top of them, and nothing above the shipped constant had been
scored. A claim that a constant lands on an independent laboratory's optimum cannot be made
from a grid whose maximum is that constant, and we made it.

Extending the sweep to {mk_top} gives the two-sided curve the claim needed, and in the
units of Section 3.3 the answer is sharper than the original claim was:

| mad_k | marked% | area reported / true | accuracy | specificity |
|---|---|---|---|---|
| 4.0 | 3.260% | {wf4_area}x | 96.74% | 97.60% |
| **{mk_ship} shipped** | {wf5_mark}% | {wf5_area}x | {wf5_acc}% | {wf5_spec}% |
| **{mk_best} optimum** | {wf6_mark}% | **{wf6_area}x** | {wf6_acc}% | {wf6_spec}% |
| 7.0 | 1.518% | {wf7_area}x | 97.97% | 99.11% |

At `mad_k = {mk_best}` the reported crack area fraction is **{wf6_area} times the
annotator's** — {ag_best_mark}% against {ag_best_lab}%, an error of {ag_best_err_pct}%.
The shipped constant overstates it by {wf5_area}x. The difference survives the test this
paper demands of everyone else: across the {mk_n} whole fields the absolute area error is
smaller at {mk_best} than at {mk_ship} in {mk_area_wins} of {mk_n} images, paired Wilcoxon
p {mk_area_p}.

The direction matters more than the magnitude. Every attempt in this paper to improve the
score by marking **more** either failed its controls or wrecked the area fraction
(Section 3.5). The one change that improves it marks **less**.

On the released crops the same change moves the area fraction the wrong way, {mk_crop_ship_ratio}x
to {mk_crop_6_ratio}x (p {mk_crop_area_p}), because those crops are cut around their cracks
and the detector already under-marks on them. The two framings disagree about the right
operating point, which is a further reason not to read a single tuned constant as a
property of the method.

What survives of the original claim is weaker and still worth stating: a constant carried
unchanged from another laboratory's alloy lands one rung from the optimum, and every value
tested below it is worse. We have not changed the shipped default on the strength of 31
images of one alloy; Section 7 says what would be needed.

### 3.3  Scored as a pixel budget

[FIGURE P5 - pixel budget]

Precision, recall, F1 and IoU all discard the true negatives. On an image that is
{in_lab_pct}% crack that is 98% of the evidence, and it lets two very different detectors
share a score — one marking 0.3% of a frame and one marking 5% can land on the same IoU.
The quantity this tool reports to a user is an **area fraction**, a pixel percentage, so
every number in this paper is computed over the whole frame and none of them is an overlap
score.

| | whole fields | released crops |
|---|---|---|
| labelled crack | {in_lab_pct}% | {in_crop_lab_pct}% |
| detector marked | {in_mark_pct}% | {in_crop_mark_pct}% |
| of which correct | {in_tp_pct}% | {in_crop_tp_pct}% |
| of which wrong | {in_fp_pct}% | {in_crop_fp_pct}% |
| area fraction reported / true | {in_ratio}x | {in_crop_ratio}x |
| accuracy | {in_acc}% | {in_crop_acc}% |
| an empty mask would score | {in_empty_acc}% | {in_crop_empty_acc}% |
| specificity | {in_spec}% | {in_crop_spec}% |

**The area fraction is the result.** It is the number a materials reader takes away, and at
the operating point of Section 3.2 the detector reports {ag_best_mark}% of the field as
cracked against the annotator's {ag_best_lab}% — **{ag_best}x, an error of
{ag_best_err_pct}%**. At the shipped setting it is {ag_ship}x. No overlap score states that
quantity, which is the whole reason this section exists.

**Accuracy has to be read against an empty mask.** Leaving the background alone is free and
it is 98% of the frame, so an empty file scores {in_empty_acc}% on the whole fields.
Marking a pixel pays for itself in accuracy only where more than half of what is marked is
right. On the released crops the detector clears that line — {in_crop_acc}% against
{in_crop_empty_acc}%, and {cb_acc}% at its best setting, {cb_margin} points clear — and on
the whole fields it does not. We print both rather than the one that flatters.

**The bias reverses between the two framings of the same images** — {in_ratio}x on whole
fields, {in_crop_ratio}x on the crops cut from them. The detector did not change.

### 3.4  Against classical detectors

[FIGURE P4 - baselines]

Every arm gets its own best parameter by the same leave-one-image-out rule, on the same
whole fields, through the same scoring code, and each is shown at whichever of its two
tunings gives it the higher accuracy — so no arm is handicapped by a choice we made for it.

{arm_tbl}

**On the quantity this tool exists to report, the detector places {arm_area_rank} of the
eight arms.** It reports {arm_area_det} times the annotator's crack area fraction; the
nearest classical arm, {arm_area_2nd_name}, reports {arm_area_2nd}x. That is the one
comparison in this paper the detector wins outright, and it wins it on the measure the
laboratory actually uses.

It does not win on accuracy, and neither does anything else: **{arm_n_earned} of the eight
arms have an accuracy an empty mask does not beat** on these fields. At {in_lab_pct}% crack
an empty file scores {in_empty_acc}%, and no arm tested here marks enough of the crack
correctly to pay for what it marks wrongly. On the released crops, where prevalence is
{in_crop_lab_pct}%, three arms do clear that line and this detector is one of them.

We report the comparison because a reader can reproduce it in an afternoon, and because the
premise is worth more than the ranking: none of these arms is trained, all are tuned
identically, and the table shows what the whole classical family reaches on a benchmark
where learned methods report far higher overlap scores — in units those scores never state.

### 3.5  Why we do not report overlap scores

Section 3.3 says this paper reports the pixel budget and not F1 or IoU. This is the
experiment behind that decision, and it is the strongest argument in the paper for the
choice.

We tried to raise this detector's standing on a conventional overlap score. The attempt
succeeded, and that is the finding.

Take the detector's own output and dilate it. Give the dilation one tuned parameter, chosen
leave-one-image-out exactly as every other arm chooses its own. Nothing is added: a
morphological dilation cannot find a crack the detector did not already mark, and it reads
no new evidence from the image. That mask takes first place on the released crops on the
conventional score, clear of every classical filter, and it holds first place under a
width-blind variant that reduces both masks to centrelines — because dilation closes gaps,
and gap-closing moves a centreline score too.

Two further arms were built before it and did no better. Growing the proposal through a
Sato ridge response, which at least reads the image, lost to the plain dilation on the
crops and beat it by a similar margin on the whole fields — the two framings disagree in
sign, which is itself the answer. And on whole fields, growing the proposal through **a
different field's** ridge response scored {rg_other} against the real field's {rg_real}.
A step whose output barely changes when you feed it the wrong image is not reading the
image. Two more followed: a local-roughness channel, motivated by what the missed crack
turns out to be (Section 3.6), and a watershed grown from the dark core out to the gradient
ridge along the crack lip — the one construction whose stopping rule is the crack edge
rather than a threshold. The watershed scored *below* both of its own controls.

**Here is what all four cost, in the units of Section 3.3.** Each marks more, and each
pushes the reported crack area fraction further from the truth:

| arm, whole fields | area reported / true |
|---|---|
| shipped detector at `mad_k = {mk_best}` | **{wf6_area}x** |
| shipped detector at `mad_k = {mk_ship}` | {ag_ship}x |
| grown through a Sato ridge | 2.86x |
| local-roughness channel | {tx_ratio}x |
| watershed to the crack lip | 2.86x |
| dilated, which reads nothing at all | {dec_area_fields}x |

An overlap score rewards every row in that table. The area fraction rejects all of them.
A reader given the dilated mask would be told that {dec_area_fields} times as much of the
field had cracked as the annotator marked, and the mean crack width would read
{dec_width_fields}x. We did not ship any of it.

The ranking on this dataset is substantially a ranking of how wide each method draws. That
is the same conclusion Section 4 reaches from the other direction, and it is why a table of
overlap scores on broad-brush labels should not be read as a table of detection ability —
or printed in this paper.

### 3.6  The labelled crack the detector cannot reach

Of the {in_lab_pct}% of the frame the annotator marked as crack, the proposal stage reaches
{rd_reach_pct_img}% and **never reaches {rd_never_pct_img}%** — and that second figure does
not move with any setting of either gate. Opening both to their limits, so that
{rd_open_marked}% of the image is marked, leaves it unchanged. It is a ceiling on the
proposal mechanism for this material, not an operating point.

**It is not faint. It is the wrong polarity.** The labelled area the detector never reaches
has a mean grey level of 127 against a background of 82 and a detected crack core of 59 —
it is substantially *brighter* than the matrix. Flattening the image contributes only
−0.16 of a standard deviation to that difference, so it is in the micrograph and not in the
pipeline. Panels of the three most heavily cracked fields show what it is: these cracks are
open wide enough to see into, and the lit, rough fracture surface inside the opening is what
the annotator's band covers and a darkness threshold cannot. {rd_never_within10}% of it lies
within 10 px of crack the detector did find.

That is why every widening arm in Section 3.5 reaches this area and every one of them
wrecks the reported area fraction doing it: reaching material that is brighter than matrix
means marking bright pixels, and a detector built on darkness has no principled way to stop.

It also refutes a fix carried over from our own corpus, where the absolute darkness floor
accounted for nearly all of the proposal stage's losses. On this alloy that gate costs
{rd_floor_cost} of the labelled area and the MAD cut costs the rest.
