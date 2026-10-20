## 4  What the scores measure

This is the part we would most want another group to check.

[FIGURE P3 - width sensitivity]

Take the ground truth, reduce it to its centreline, and redraw it at a fixed width. The
result is exactly right about where every crack is and wrong only about how wide. Scored
against the label it should be nearly perfect, and it is not: the best such reconstruction
reaches IoU {wc_in_iou}. Most of the available IoU is being spent on agreeing about width,
and the two curves in Figure 3 peak at different widths — {wc_in_at} px for this dataset's
labels against {wc_corpus_at} px for our own corpus tiles — so the same detector's IoU can
differ between corpora without its localisation differing at all.

**This is not an upper bound, and we presented it as one.** A real label varies in width
along its length, so a detector that tracks that variation can score above a constant-width
redraw of the same centreline. We had to be told that by the measurement.

**And width does not explain the detector's difficulty, which we initially claimed it did.**
This dataset's labels are drawn at a median {in_stroke} px and its best constant-width
reconstruction reaches {wc_in_iou}; our own corpus tiles, scored by the same construction,
peak at {wc_corpus_iou}. Two corpora whose brush widths differ substantially reach
comparable ceilings, so whatever makes these images hard for this detector, it is not how
wide the labels are drawn.

That argument was stronger one draft ago. It rested on two SEM sets annotated four times
apart in stroke width — 25.8 px and 6.4 px — reaching the same ceiling to within 0.007. The
second of those was the EBC coating, withdrawn from this paper as a ceramic rather than a
metal, and the argument is weaker without it. The measurement remains in
`docs/figures/sem_width_ceiling.json`.
