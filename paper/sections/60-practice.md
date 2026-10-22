## 6  Measurement practices this forced

Stated as rules because each one followed a specific error of ours.

1. **Report the score in the units of the answer.** Overlap scores discard every pixel
   correctly left alone — 98% of the evidence on a {in_lab_pct}%-crack image — and none of
   them can state the error a user suffers, which is an area fraction off by some factor.
   Report labelled %, marked %, and their ratio. That ratio is {in_ratio}x here at the
   shipped setting, {ag_best}x one rung up, and {ebc_ratio}x on a set this detector fails;
   no overlap score in any draft of this paper distinguished those three situations as
   plainly, which is why they are the only units this one uses.
2. **Never quote plain accuracy without the accuracy of an empty mask.** It is {in_acc}%
   here and an empty file scores {in_empty_acc}%. Marking a pixel pays for itself in
   accuracy only where more than half of what is marked is right, so at low prevalence the
   two numbers must be printed together or not at all.
3. **State the whole range the score can move in.** A mask with perfect localisation and
   the best possible width — §4's construction — reaches {wc_f_peak}% accuracy on these
   fields against an empty mask's {wc_f_empty}%. The entire competitive range is
   {wc_f_head} points. A score quoted without that range cannot be read.
4. **Report the no-information floor beside every score.** Across the sets measured for
   this project the floor moves by more than a factor of seven, and on our own corpus the
   refereed pixels are {lab_pos_pct}% crack, so a mask that marks every pixel scores
   {lab_all_f1} there. A bare score is not a result.
5. **Choose parameters by grouped hold-out, and say what the group is.** Regrouping alone
   moved an AUC by +0.0458 in our data, which is larger than most effects we chased.
6. **A difference of medians is not a paired difference.** One result moved 0.0742 as
   medians and 0.0000 paired.
7. **State the resolution of the comparison.** Differences of a few thousandths on 26 to 31
   images are not results; the mad_k change in §3.2 is reported with a paired test over
   every image and the count favouring each value, and nothing smaller is claimed anywhere.
8. **Do not stop a sweep at the value you are validating.** Ours ran to the shipped
   constant and no further, so the claim that the constant was already optimal could not
   have failed. It did fail when the grid was extended (§3.2), and the original claim was
   this paper's headline.
9. **Controls must be able to fail.** Every control we built was broken on purpose to check
   it noticed; two did not and were rewritten. A control fed the *wrong image* killed three
   separate improvements in §3.5 that had looked real.
10. **Check the mask encoding and the bit depth before scoring anything.** This set's masks
   are anti-aliased rather than two-valued and its images are 16-bit; an ordinary 8-bit
   conversion made the detector find almost nothing and looked like a detector failure
   rather than a loading bug.
11. **Score whole fields, not crops of them.** Cropping these images around their own cracks
   moves the reported area fraction from {in_ratio}x to {in_crop_ratio}x with no change to
   the method, and reverses which operating point is best.
12. **An oracle must match the arity of the thing it bounds.** The constant-width
   reconstruction in §4 is not an upper bound on an overlap score, and we described it as
   one until the data said otherwise.
