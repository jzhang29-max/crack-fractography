## 4  What the scores measure

This is the part we would most want another group to check.

[FIGURE P3 - width sensitivity]

Take the annotator's own ground truth, reduce it to its centreline, and redraw it at a
fixed width. The result is exactly right about **where** every crack is and wrong only
about **how wide**. It is the best any detector could do on localisation, so whatever it
scores is a ceiling, and the gap between that ceiling and an empty mask is the entire range
in which a detector can compete.

**On the whole fields that range is 0.7 percentage points.** The redraw peaks at accuracy
{wc_f_peak}% at a drawn width of {wc_f_at} px; an empty mask scores {wc_f_empty}%. A mask
with perfect localisation and the best possible width is worth {wc_f_head} points of
accuracy over marking nothing at all, and every classical arm in Section 3.4 — and this
detector — sits inside or below that band. That is not a statement about any detector. It
is a statement about what accuracy can express on an image that is {in_lab_pct}% crack.

**On the released crops the range is {wc_c_head} points** — ceiling {wc_c_peak}% at
{wc_c_at} px against an empty mask's {wc_c_empty}% — and there the comparison becomes
informative. This detector reaches {cb_acc}%, which is **{wc_c_captured}% of the whole
available headroom**. That is the most favourable honest statement in this paper, and it is
available only where prevalence is high enough for accuracy to have room to move.

The same construction says where the width goes. The redraw reproduces the annotator's own
crack area fraction at {wc_f_areaw} px on the whole fields and {wc_c_areaw} px on the crops
— so a mask drawn at the annotator's median stroke of {in_stroke} px is already close to
the right **amount** of paint, and the remaining disagreement is about placement, not
quantity.

**Two claims from an earlier draft are withdrawn here.** We reported this construction as an
upper bound on IoU; it is not, because a real label varies in width along its length and a
detector that tracks that variation can score above a constant-width redraw of the same
centreline. And we reported that label width does not explain the detector's difficulty, on
the strength of two corpora whose brush widths we said differed substantially. We cannot say
that: the corpus stroke width is not measured here, Section 7 records it as unmeasured, and
the second of those corpora was the EBC coating, withdrawn from this paper as a ceramic. The
inference had nothing holding it up.
