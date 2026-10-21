## Appendix A  Every set measured, as a pixel budget

All five SEM sets this project has scored, in the units the tool reports. Two of them are
not crack benchmarks and say so. Percentages are of all image pixels, averaged per image,
`mad_k` chosen leave-one-image-out.

| set | n | status | lab% | mark% | ok% | bad% | rep/true | bal.acc | MCC |
|---|---|---|---|---|---|---|---|---|---|
| Inconel 718, fields | {in_n} | the paper's benchmark | {in_lab_pct}% | {in_mark_pct}% | {in_tp_pct}% | {in_fp_pct}% | **{in_ratio}x** | {in_bacc}% | {in_mcc} |
| Inconel 718, crops | 26 | same images, cut on cracks | {in_crop_lab_pct}% | {in_crop_mark_pct}% | {in_crop_tp_pct}% | {in_crop_fp_pct}% | **{in_crop_ratio}x** | {in_crop_bacc}% | {in_crop_mcc} |
| EBC coating, fields | {ebc_n} | withdrawn: ceramic | {ebc_lab_pct}% | {ebc_mark_pct}% | {ebc_tp_pct}% | {ebc_fp_pct}% | **{ebc_ratio}x** | {ebc_bacc}% | {ebc_mcc} |
| EBC coating, crops | 8 | withdrawn | {ebcc_lab_pct}% | {ebcc_mark_pct}% | {ebcc_tp_pct}% | {ebcc_fp_pct}% | **{ebcc_ratio}x** | {ebcc_bacc}% | {ebcc_mcc} |
| MetalDAM voids | {md_n} | NOT cracks: voids | {md_lab_pct}% | {md_mark_pct}% | {md_tp_pct}% | {md_fp_pct}% | **{md_ratio}x** | {md_bacc}% | {md_mcc} |

The span is the point. The same detector, unchanged, reports an area fraction that is
**{md_ratio} times** the truth on compact voids in steel and **{ebc_ratio} times** the
truth on a coating at {ebc_prev}% prevalence. On the alloy it is {in_ratio}x. Anyone
quoting a single accuracy figure for this detector is quoting one point on that range.

MetalDAM is the most revealing row and it is not a crack result. Its targets are voids:
compact, dark, high-contrast. The detector reaches MCC {md_mcc} there against {in_mcc} on
cracks in the superalloy — its best score in this project is on the objects that are
easiest to be dark. That is consistent with what it is: a multi-scale darkness threshold.
Cracks are hard for it because they are thin and low in contrast, not because they are
cracks.

The two pavement sets are absent. They were measured on P/R/F1/IoU before being removed
from this paper as the wrong modality, and their downloads were not retained, so no budget
was computed for them.
