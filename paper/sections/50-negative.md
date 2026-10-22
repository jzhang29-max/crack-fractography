## 5  Negative results

These cost the most time and are the most likely to save someone else's.

**Retuning the detector for a different modality does nothing.** Applying the
SEM-calibrated detector to transmission X-ray tomography, we swept its two gating constants
singly and jointly, plus every morphology and size floor, under leave-one-specimen-out
selection. No arm beat doing nothing on held-out data, and resolution-matching the scale
ladder to the measured width ratio changed nothing measurable. Those sweeps were scored in
overlap units, before this paper settled on the units of §3.3, and have not been re-run;
the conclusion is a null either way, which is the one case where the choice of units cannot
reverse the answer.

**That corpus cannot answer the question anyway.** It holds four specimens, so a paired
test has an exact two-sided floor of p = 0.125 — no result on it can reach significance at
any conventional level, a win or a null. One specimen carries 57.7% of all adjudicated
not-crack pixels, so the pooled score surface is essentially that specimen's.

**Scores computed on the marked area alone can be bought by widening the mask.** This is
the finding that set the units of this paper, and §3.5 gives it in full: dilating the
detector's own output — which reads nothing new from the image — reaches the top of a
conventional ranking while pushing the reported crack area fraction to
{dec_area_fields}x the annotator's. A score that a morphological operation can win is not
measuring detection.

**A control fed the wrong image killed three improvements that looked real.** Growing the
proposal through a ridge filter, through a local-roughness channel, and by watershed to the
crack lip each raised a conventional score substantially. Re-run with the filter computed
from a *different field*, two of the three scored within 0.03 of their real-image version
and the third scored below it. All three are in §3.5 with what they cost the area fraction.

**Six region-level precision rules validated on 512 px crops were rejected on whole
frames.** Four of them delete 54–75% of hand-marked crack; the other two change no score.
See §2.

**Our own corpus cannot referee a detector's false positives.** Of the pixels a human
actually ruled on across 18 hand-corrected frames, {lab_pos_pct}% are crack — the masks are
region assertions over part of each frame, not complete segmentations. A mask that marks
every pixel therefore scores {lab_all_f1} there on any overlap measure, and no ranking
computed on that corpus can be trusted until refereed not-crack area exists. That is the
single largest gap in this work and `docs/DATASET_RELEASE_SCOPE.md` costs out closing it.
