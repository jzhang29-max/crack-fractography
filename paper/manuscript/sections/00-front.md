# Multiscale darkness detection for crack area fraction measurement in scanning electron and transmission X-ray micrographs

[Author names]

[Department and institution, city, country]

[Corresponding author email]

## Abstract

Quantifying crack area in micrographs supports the characterisation of defects in
metallic microstructures. This study examines the two detectors a laboratory actually
ships for its own scanning electron (SEM) and transmission X-ray (TXM) micrographs: a
multiscale darkness rule on the electron arm and a trained per-pixel ensemble on the
transmission arm. The electron pipeline combines background correction, multiscale
candidate detection, morphological cleanup and connected-component filtering, followed by
an eight-feature logistic region classifier that decides which candidates are retained and
carries the only fitted parameters in the chain, nine of them. Enabling that classifier is
a trade and not an improvement: it raises precision and lowers recall, intersection over
union and F1. Both collections reported here were scored with it enabled.

The principal result is what an overlap score on these collections measures. On the
{om_sem_n} SEM and {om_txm_n} TXM frames that carry an explicit painted verdict for both
crack and not-crack, the mean per-frame F1 is {om_sem_f1} and {om_txm_f1}. Reducing each
frame's own annotation to its centreline and redrawing it three pixels wide gives a
prediction that is exactly right about where every crack runs and wrong only about width,
and against the stroke it came from that prediction scores {om_sem_cf1} and {om_txm_cf1}.
**The detector outscores a geometrically correct trace of the reference because it marks
wide, not because it is better located**, so an F1 on these collections ranks how closely
a mask reproduces the annotator's brush. Neither collection adjudicates the whole frame
either, so each precision is a bracket rather than a value, and both ends are reported.

The paper also reports a cross-modality evaluation in four parts. The transmission X-ray microscopy collection's
own detector is reported here for the first time, and the same model returns an IoU of
{tm_cv_ens}, {tm_ld_iou} or {tm_wf_iou} according only to which pixels are scored. Against
that collection's labels, a reconstruction of the reference annotation that is exactly
correct about position scores {tm_ld_ceil} where the deployed model scores {tm_ld_iou}, and
the two move in opposite directions with the width of the annotator's stroke — so a higher
overlap score there is evidence of resemblance to the brush rather than of crack found. The
SEM detector itself, its candidate stage carried across unchanged to the {tx_n} frames of the two specimen
series reported here, returns {tx_area} times the annotated crack area pooled and stands
{tx_margin} points above an all-background prediction — but that pooled figure is the
area-weighted average of {tx_b3_margin} points on one series and {tx_b2_margin} on the
other, and describes neither. Giving each frame one vote rather than pooling pixels puts
it at {tpf_mean_all} points with {tpf_pos_all} of the {tpf_n} frames above the prediction,
so the pooled statement is reported with the per-frame one throughout. The series that
clears the line is also the one whose annotation does not survive an audit of what it was
painted on: {fb_b3_crack}% of its painted crack lies below {fb_thresh} optical density,
where {fb_b3_frame}% of the frame does and {fb_b3_notcrack}% of the same frames' painted
NOT-crack does, and {fb_b3_gate}% of it falls under the detector's absolute darkness
floor, which marks it whatever the relative criterion decides. On this laboratory's own
SEM and TXM frames the mean per-frame F1 is {om_sem_f1} and {om_txm_f1} against
{om_sem_cf1} and {om_txm_cf1} for a geometrically correct trace of the same annotations,
which is the brush effect measured a second time.

Where the transfer fails is also located, in the detector's own units rather than through
a score. The proposal stage keeps a pixel that is darker than its frame's median by more
than k scaled median absolute deviations at any radius of its scale ladder; measuring the
operator's annotated crack on that same axis, the median annotated pixel sits at
{mc_sem_k} on the {mc_sem_n} SEM frames and {mc_txm_k} on the {mc_txm_n} TXM frames
against an operating point of {om_k}, below it on {mc_sem_below} and {mc_txm_below} of
them, with a median of {mc_sem_prop}% and {mc_txm_prop}% of the annotated crack proposed
at all. The reconstruction of the real proposal mask from that axis is checked pixel for
pixel against the deployed detector on every frame and agrees to within {mc_recon} pixel.
The loss is therefore at candidate generation and not at the filters that follow it, and
it is a margin that is thinner in transmission X-ray microscopy rather than a failure
peculiar to it.

These findings support the detector as an interpretable approach to crack measurement
on the collections evaluated here, and they locate what its scores can and cannot
settle: the overlap numbers are governed by the width of the annotator's stroke, and
the transfer loss is at candidate generation rather than at the filters that follow it.

Keywords: scanning electron microscopy; transmission X-ray microscopy; austenitic stainless
steel; crack area fraction; multiscale image analysis; deterministic
segmentation; cross-modality transfer; annotation quality
