## 6  Measurement practices this forced

Stated as rules because each one followed a specific error of ours.

1. **Report the score in the units of the answer.** F1 and IoU discard every pixel
   correctly left alone — 98% of the evidence on a {in_lab_pct}%-crack image — and neither
   can state the error a user suffers, which is an area fraction off by some factor. Report
   labelled %, marked %, and their ratio; keep F1 and IoU beside them for comparability
   with the literature. The ratio is {in_ratio}x here and {ebc_ratio}x on a set this
   detector fails, and no F1 in this paper distinguishes those two situations as plainly.
2. **Never quote plain accuracy at low prevalence.** It is {in_acc}% here, and marking
   nothing at all scores {in_tn_plus}%. Balanced accuracy and MCC use the true negatives
   without being swamped by them.
3. **Report the no-information floor beside every score.** Marking every pixel scores
   F1 {in_me_f1} on this dataset. A bare score cannot be read without it, and across the
   sets measured for this project the floor moves by more than a factor of seven.
4. **Choose parameters by grouped hold-out, and say what the group is.** Regrouping alone
   moved an AUC by +0.0458 in our data, which is larger than most effects we chased.
5. **A difference of medians is not a paired difference.** One result moved 0.0742 as
   medians and 0.0000 paired.
6. **State the resolution of the comparison.** Our laboratory corpus detects about +0.14
   F1 for a new method; we reported smaller differences for weeks before measuring this.
7. **Controls must be able to fail.** Every control we built was broken on purpose to check
   it noticed; two did not and were rewritten.
8. **Check the mask encoding and the bit depth before scoring anything.** This set's masks
   are anti-aliased rather than two-valued and its images are 16-bit; an ordinary 8-bit
   conversion drove recall to 0.0012 and looked like a detector failure rather than a
   loading bug.
9. **Score whole fields, not crops of them.** Cropping these images around their own cracks
   raises F1 by {in_crop_gain} with no change to the method.
10. **An oracle must match the arity of the thing it bounds.** The constant-width
   reconstruction in §4 is not an upper bound, and we described it as one until the data
   said otherwise.
