## 4  What the scores measure

This is the part we would most want another group to check.

[FIGURE P3 - width sensitivity]

Take the ground truth, reduce it to its centreline, and redraw it at a fixed width. The
result is exactly right about where every crack is and wrong only about how wide. Scored
against the label it should be nearly perfect, and it is not: on CrackForest the best such
reconstruction reaches IoU {wc_cf_iou} and on DeepCrack {wc_dc_iou}. Most of the available
IoU is being spent on agreeing about width.

Two consequences.

**A score is not comparable across corpora whose annotation differs.** The curves peak at
different widths and fall away at different rates, so the same detector's IoU can differ
between datasets without its localisation differing at all.

**But width does not explain our own gap, and we initially claimed it did.** The detector
scores IoU {dc_iou} on DeepCrack and roughly 0.33–0.42 on our laboratory corpus, and the
obvious explanation was that our hand-painted labels are much broader. Measured, that
explanation fails: the constant-width curve peaks at {wc_dc_iou} on DeepCrack and
{wc_corpus_iou} on the corpus tiles — within 0.01 of each other. Whatever makes the
laboratory corpus harder for this detector, it is not the width of the brush.

Note also that the detector *exceeds* the constant-width reconstruction on DeepCrack
({dc_iou} against {wc_dc_iou}). The reconstruction is therefore not an upper bound, and we
do not present it as one: a real label varies in width along its length, and a detector
that tracks that variation can beat a constant-width redraw of the same centreline. We had
to be told this by the measurement, having first written the figure up as a ceiling.
