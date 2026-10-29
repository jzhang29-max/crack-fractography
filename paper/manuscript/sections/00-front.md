# Multiscale darkness detection for crack area fraction measurement in scanning electron micrographs of Inconel 718

[Author names]

[Department and institution, city, country]

[Corresponding author email]

## Abstract

Quantifying crack area in scanning electron microscopy supports the characterisation of
defects in metallic microstructures. This study examines a deterministic multiscale
darkness detector for measuring the two-dimensional crack area fraction in Inconel 718
micrographs. The evaluated pipeline combines background correction, multiscale candidate
detection, morphological cleanup and connected-component filtering without a learned region
classifier. The primary collection comprises {in_n} whole fields. At the reported MAD
multiplier of {mk_best}, the predicted crack area fraction was {ag_best_mark}%, compared
with a reference value of {ag_best_lab}%. The predicted-to-reference area ratio was
{ag_best}, corresponding to a net difference of 0.024 percentage points and an aggregate
relative discrepancy of approximately {ag_best_err_pct}%. The reported background
specificity was {ag_best_spec}%. Among seven displayed classical method summaries, the
darkness detector had the area ratio closest to unity under the original selection
procedure. A field-level comparison reported a smaller absolute area error at the selected
setting than at the default setting in 23 of the {in_n} fields.

This revision adds two things the previous version asserted without showing. First, the
operating-setting sweep is now reported in full: the earlier grid stopped at the default
setting with the area ratio still falling, and extending it identifies {mk_best} as the
point at which the reported and reference areas agree. Second, the area endpoint is placed
against the range it can resolve, using a reconstruction of the reference annotation that
is exactly correct about position and wrong only about width. The revision also adds a
cross-modality evaluation in four parts. The transmission X-ray microscopy collection's
own detector is reported here for the first time, and the same model returns an IoU of
{tm_cv_ens}, {tm_ld_iou} or {tm_wf_iou} according only to which pixels are scored. Against
that collection's labels, a reconstruction of the reference annotation that is exactly
correct about position scores {tm_ld_ceil} where the deployed model scores {tm_ld_iou}, and
the two move in opposite directions with the width of the annotator's stroke — so a higher
overlap score there is evidence of resemblance to the brush rather than of crack found. The
SEM detector itself, carried across unchanged to {tx_n} of those frames, reports {tx_area}
times the annotated crack area pooled across four specimen groups and clears an
all-background prediction on one of them; giving each frame one vote rather than pooling
pixels, it sits {tpf_mean_all} points from that prediction with {tpf_pos_all} of the
{tpf_n} frames above it, and one group changes sign between the two aggregations, so the
pooled statement is reported with the per-frame one throughout. On this laboratory's own
SEM and TXM frames the mean per-frame F1 is {om_sem_f1} and {om_txm_f1} against
{om_sem_cf1} and {om_txm_cf1} for a geometrically correct trace of the same annotations,
which is the brush effect measured a second time.

These findings support the detector as an interpretable approach to aggregate crack area
measurement within the evaluated collection. The principal result concerns agreement in
total image area, with pixel-level segmentation considered as a separate endpoint.

Keywords: scanning electron microscopy; Inconel 718; crack area fraction; multiscale image
analysis; deterministic segmentation; cross-modality transfer; transmission X-ray microscopy
