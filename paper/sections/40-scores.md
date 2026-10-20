## 4  What the scores measure

This is the part we would most want another group to check.

[FIGURE P3 - width sensitivity]

Take the ground truth, reduce it to its centreline, and redraw it at a fixed width. The
result is exactly right about where every crack is and wrong only about how wide. Scored
against the label it should be nearly perfect, and it is not. Most of the available IoU is
being spent on agreeing about width, and the curves peak at different widths in different
corpora — so the same detector's IoU can differ between datasets without its localisation
differing at all.

The SEM sets make the point sharply on their own. Inconel 718's labels are drawn at a
median {in_stroke} px and the coating's at {ebc_stroke} px — a factor of four apart — and
the best constant-width reconstruction reaches {wc_in_iou} and {wc_ebc_iou} respectively.
Four times the brush width, the same ceiling to within 0.007.

**This does not explain our own gap, and we initially claimed it did.** The obvious reading
of a detector scoring IoU {dc_iou} on pavement and {in_iou} on SEM alloy is that the
annotations differ in breadth. Measured, that reading fails: the constant-width curve peaks
at {wc_dc_iou} on DeepCrack and {wc_corpus_iou} on our own corpus tiles — within 0.01 of
each other despite a large difference in brush width. Whatever makes micrographs harder for
this detector, it is not how wide the labels are drawn.

**The reconstruction is not an upper bound, and we presented it as one.** The detector
*exceeds* it on DeepCrack ({dc_iou} against {wc_dc_iou}), because a real label varies in
width along its length and a detector that tracks that variation beats a constant-width
redraw of the same centreline. We had to be told this by the measurement.
