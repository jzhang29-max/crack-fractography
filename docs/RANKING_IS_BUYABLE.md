# The public-benchmark ranking can be bought, and what buying it costs

**Question asked:** raise the detector's recall so it ranks higher on the public Inconel 718
set. **Answer:** it ranks first after a two-line change that detects nothing, and shipping
that change would put a 2.54x error into the one number the tool exists to report.

All numbers: Zenodo 23045328 Inconel 718 crack class, CC BY 4.0. Every arm picks its own
parameters leave-one-image-out, same scorer, same images. Measurement files are
`docs/figures/{recall_decomposition_inconel,recall_fix_attempts,ridge_grow_controls,
ridge_vs_dilation_loo,skelf1_ranking,dilation_costs_measurements}.json`.

## 1. The recall that is missing cannot be tuned back

Nested arms on the 31 whole fields, pooled over pixels, each row adding one gate:

| arm | recall | precision | marked% |
|---|---|---|---|
| no gates (mad_k=0.5, no darkness floor) | 0.5792 | 0.0196 | 53.354% |
| MAD cut only | 0.4258 | 0.3212 | 2.390% |
| shipped proposal, both gates | 0.4264 | 0.3214 | 2.392% |
| + clean, blobs under 13 px | 0.4402 | 0.3276 | 2.423% |
| + 40 px region floor (SHIPPED) | 0.4347 | 0.3350 | 2.340% |

With both gates open to their limit, marking over half the image, recall stops at 0.5792.
**42.1% of the labelled crack is not dark at any scale**, so no gate setting proposes it.

Two corollaries. The absolute darkness floor costs **0.0006** recall here, against roughly
96% of proposal-stage recall loss on our own corpus — the known fix does not transfer. And
the MAD cut's 0.153 of recall is not free: taking it drops precision from 0.3214 to 0.0196.

## 2. Growing through a ridge filter looked like the fix; decoys killed it

Seeding on the darkness proposal and growing through the Sato ridge response reached
F1 0.6169 under two-parameter LOO selection, against the shipped 0.4958 — first place.
Three controls, each keeping something and destroying something:

| whole fields, fixed mad_k=5.0, ridge top 2% | F1 | recall | marked% |
|---|---|---|---|
| A shipped darkness only | 0.3444 | 0.4123 | 2.340% |
| B grown through REAL ridge | 0.4065 | 0.5795 | 2.906% |
| C grown through FLIPPED ridge | 0.3118 | 0.4784 | 3.333% |
| **D grown through ANOTHER FIELD's ridge** | **0.4043** | 0.5784 | 2.975% |
| E seed DILATED to B's area | 0.4176 | 0.6255 | 3.206% |

**D is the killer: feeding the step a different image entirely costs 0.0022 F1.** A step
whose output barely moves when the input is wrong is not reading the input. And E — a
dilation, no information at all — beats B on both sets.

Under matched arity (2 parameters, 8 grid points, identical LOO rule):

| | crops | whole fields |
|---|---|---|
| grown through RIDGE | 0.6169 | 0.4730 |
| just DILATED | **0.6307** | 0.4608 |

The two sets disagree in sign and the gap is ~0.013 either way. The ridge filter is
decoration.

## 3. So the ranking is buyable — under a width-blind metric too

Carrying the dilation decoy through every ranking as a control on the metric:

| arm | crops pixel F1 | fields pixel F1 | fields skelF1@5 |
|---|---|---|---|
| **DECOY: detector DILATED** | **0.6307 (1st)** | 0.4608 | **0.4684 (1st)** |
| Sauvola local | 0.5145 | 0.4040 | 0.4335 |
| Sato ridge | 0.4985 | 0.4659 | 0.4589 |
| Meijering ridge | 0.4924 | 0.4697 | 0.4450 |
| DETECTOR (shipped) | 0.4958 | 0.3444 | 0.3727 |

Skeleton F1 was adopted in this project precisely because it is width-blind, and the decoy
still takes first place under it: dilation closes gaps in a fragmented mask, and
gap-closing moves a centreline score. Width-blindness is not sufficient.

**Also recorded here because it is a correction, not a decoy:** the detector ranks *third
of seven* on the released crops but *fifth of seven* on the whole fields the rest of the
paper reports. The ridge filters lose 0.02-0.03 F1 between the two framings; this detector
loses 0.1514.

## 4. What first place costs

Each arm given its best single setting in-sample, which favours it:

| whole fields | area fraction reported / true | mean width reported / true |
|---|---|---|
| shipped detector | 1.30x | 0.75x |
| dilated, ranks first | **2.54x** | **2.18x** |

Buying 0.1163 F1 on whole fields takes the reported crack area fraction from 1.30x the
labelled value to 2.54x. The benchmark and the measurement move in opposite directions.

**Not shipped.** The detector is unchanged. What changed is the paper, which now reports
the whole-field ranking alongside the crops one and states that the ranking on this dataset
is substantially a ranking of how wide each method draws (§3.4-3.6 of `paper/draft.pdf`).
