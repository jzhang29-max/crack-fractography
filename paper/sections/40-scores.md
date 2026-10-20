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

**This does not set a ceiling, and we presented it as one.** A real label varies in
width along its length, so a detector that tracks that variation can score above a
constant-width redraw of the same centreline. We had to be told this by the measurement.

**And width does not explain the detector's difficulty here, which we initially claimed it
did.** The two SEM sets are annotated at a median {in_stroke} px and {ebc_stroke} px — four
times apart — and their best constant-width reconstructions reach {wc_in_iou} and
{wc_ebc_iou}, the same ceiling to within 0.007. Our own laboratory corpus, scored by the
same construction, peaks at {wc_corpus_iou}. Whatever makes these images hard for this
detector, it is not how wide the labels are drawn.
