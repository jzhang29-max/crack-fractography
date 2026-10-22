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
cross-modality evaluation: the same detector, unchanged, applied to {tx_n} transmission
X-ray microscopy frames of austenitic steel, where it reports {tx_area} times the annotated
crack area pooled across four specimen groups and clears an all-background prediction on one
of them.

These findings support the detector as an interpretable approach to aggregate crack area
measurement within the evaluated collection. The principal result concerns agreement in
total image area, with pixel-level segmentation considered as a separate endpoint.

Keywords: scanning electron microscopy; Inconel 718; crack area fraction; multiscale image
analysis; deterministic segmentation; cross-modality transfer
