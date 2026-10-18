## 6  Measurement practices this forced

Stated as rules because each one followed a specific error of ours.

1. **Report the no-information floor beside every score.** Marking every pixel scores
   F1 {dc_me_f1} on DeepCrack and {cf_me_f1} on CrackForest. A bare score cannot be read
   without them.
2. **Choose parameters by grouped hold-out, and say what the group is.** Regrouping alone
   moved an AUC by +0.0458 in our data, which is larger than most effects we chased.
3. **A difference of medians is not a paired difference.** One result moved 0.0742 as
   medians and 0.0000 paired.
4. **State the resolution of the comparison.** Our laboratory corpus detects about +0.14
   F1 for a new method; we reported smaller differences for weeks before measuring this.
5. **Controls must be able to fail.** Every control we built was broken on purpose to check
   it noticed; two did not and were rewritten.
6. **An oracle must match the arity of the thing it bounds.** The constant-width
   reconstruction in §4 is not an upper bound, and we described it as one until the data
   said otherwise.
