## 6  Measurement practices this forced

Stated as rules because each one followed a specific error of ours.

1. **Report the no-information floor beside every score.** Marking every pixel scores
   F1 {in_me_f1} on the SEM alloy and {ebc_me_f1} on the coating. A bare score cannot be
   read without it, and the floor moves by a factor of seven between those two sets
   alone.
2. **Choose parameters by grouped hold-out, and say what the group is.** Regrouping alone
   moved an AUC by +0.0458 in our data, which is larger than most effects we chased.
3. **A difference of medians is not a paired difference.** One result moved 0.0742 as
   medians and 0.0000 paired.
4. **State the resolution of the comparison.** Our laboratory corpus detects about +0.14
   F1 for a new method; we reported smaller differences for weeks before measuring this.
5. **Controls must be able to fail.** Every control we built was broken on purpose to check
   it noticed; two did not and were rewritten.
6. **Check the mask encoding and the bit depth before scoring anything.** The two SEM
   crack sets use different mask conventions, and the images are 16-bit: an ordinary 8-bit
   conversion drove recall to 0.0012 and looked like a detector failure rather than a
   loading bug.
7. **Score whole fields, not crops of them.** Cropping these images around their own cracks
   raises F1 by {in_crop_gain} with no change to the method.
8. **An oracle must match the arity of the thing it bounds.** The constant-width
   reconstruction in §4 is not an upper bound, and we described it as one until the data
   said otherwise.
