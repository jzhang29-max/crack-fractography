## Appendix A  Every set measured, as a pixel budget

All five SEM sets this project has scored, in the units the tool reports. Two of them are
not crack benchmarks and say so. Percentages are of all image pixels, averaged per image,
`mad_k` chosen leave-one-image-out.

| set | lab% | mark% | ok% | bad% | rep/true | acc% | empty% | spec% |
|---|---|---|---|---|---|---|---|---|
| Inconel 718, fields | {in_lab_pct}% | {in_mark_pct}% | {in_tp_pct}% | {in_fp_pct}% | **{in_ratio}x** | {in_acc} | {in_empty_acc} | {in_spec} |
| Inconel 718, crops | {in_crop_lab_pct}% | {in_crop_mark_pct}% | {in_crop_tp_pct}% | {in_crop_fp_pct}% | **{in_crop_ratio}x** | {in_crop_acc} | {in_crop_empty_acc} | {in_crop_spec} |
| EBC coating, fields | {ebc_lab_pct}% | {ebc_mark_pct}% | {ebc_tp_pct}% | {ebc_fp_pct}% | **{ebc_ratio}x** | {ebc_acc} | {ebc_empty_acc} | {ebc_spec} |
| EBC coating, crops | {ebcc_lab_pct}% | {ebcc_mark_pct}% | {ebcc_tp_pct}% | {ebcc_fp_pct}% | **{ebcc_ratio}x** | {ebcc_acc} | {ebcc_empty_acc} | {ebcc_spec} |
| MetalDAM voids | {md_lab_pct}% | {md_mark_pct}% | {md_tp_pct}% | {md_fp_pct}% | **{md_ratio}x** | {md_acc} | {md_empty_acc} | {md_spec} |

`empty%` is the accuracy an empty mask scores on that set, which is (100 − lab%). Two rows
beat it: MetalDAM by {md_margin} points and the Inconel crops by {in_crop_margin}. Set
sizes: Inconel {in_n} fields and 26 crops, EBC {ebc_n} fields and 8 crops, MetalDAM
{md_n}.

The span is the point. The same detector, unchanged, reports an area fraction that is
**{md_ratio} times** the truth on compact voids in steel and **{ebc_ratio} times** the
truth on a coating at {ebc_prev}% prevalence. On the alloy it is {in_ratio}x. Anyone
quoting a single accuracy figure for this detector is quoting one point on that range.

MetalDAM is the most revealing row and it is not a crack result. Its targets are voids:
compact, dark, high-contrast. The detector reaches accuracy {md_acc}% and specificity
{md_spec}% there — the highest figures anywhere in this project, and {md_margin} points
clear of an empty mask, the widest such margin we have — against {in_acc}% on cracks in the
superalloy, where an empty mask wins. Its best performance is on the objects that are
easiest to be dark, which is consistent with what it is: a multi-scale darkness threshold.
Cracks are hard for it because they are thin and low in contrast, not because they are
cracks.

The two pavement sets are absent. They were measured on overlap scores before being removed
from this paper as the wrong modality, and their downloads were not retained, so no pixel
budget was ever computed for them.
