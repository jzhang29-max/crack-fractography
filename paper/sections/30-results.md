## 3  On public data with pixel-exact ground truth

Three public sets, all scored by one instrument at 0 px tolerance with `mad_k` chosen
leave-one-image-out. Image-level grouping is the right unit: these are independent fields,
not repeated views of one specimen.

| set | modality | material | n | crack prevalence |
|---|---|---|---|---|
| Inconel 718 | SEM | nickel superalloy | {in_n} | {in_prev}% |
| EBC | SEM | environmental barrier coating | {ebc_n} | {ebc_prev}% |
| DeepCrack | optical | concrete and asphalt | {dc_n} | {dc_prev}% |

The two SEM sets are the crack classes of a public cross-material microstructure
collection (Zenodo 23045328, CC BY 4.0). Their masks were checked rather than assumed: the
coating masks are strictly binary, the alloy masks are anti-aliased binary — 94.7% of
pixels exactly 0, 4.3% at 246 or above, 0.52% in between — so a mid-grey threshold is safe,
and the scorer refuses to run on a mask that is not bimodal.

[FIGURE P1 - public scores]

### 3.1  The detector is much worse on micrographs, and that is the result

On SEM alloy the detector reaches IoU {in_iou}; on pavement, {dc_iou}. Both are far above
their own no-information floors — {in_lift_iou} and {dc_lift_iou} times the IoU of marking
every pixel — so neither is a failure to detect anything. They are a factor of two apart on
the same metric with the same code.

This matters beyond the benchmark. The same detector scores IoU roughly 0.33–0.42 on our
own laboratory SEM corpus, which is within the range it reaches on Inconel 718 here. An
independent laboratory's alloy micrographs, annotated by other people to pixel precision,
put the detector in the same place our own data does. Whatever makes micrographs harder is
a property of the imagery, not of our annotation.

### 3.2  One constant, and the limit of its transfer

[FIGURE P2 - operating curve]

The shipped constant `mad_k = 5.0` was fitted on SEM steel. On the SEM alloy set it is the
best of the seven values tested, and the curve falls away monotonically below it. On
pavement the same detector wants a smaller value and loses {dc_frozen_loss} F1 if the SEM
constant is used unchanged.

So the constant transfers *within* a modality and not *across* one. That is a weaker claim
than "one refit covers everything" and a more useful one for a tool: a laboratory that
calibrates once on its own microscope does not recalibrate per specimen.

### 3.3  The failure case

On the EBC coating the detector reaches precision {ebc_p} at a crack prevalence of
{ebc_prev}%. Recall is high ({ebc_r}) — the cracks are found — but the detector marks far
too much besides, and at this prevalence a small absolute false-positive area destroys
precision. We report it because a method paper that shows only the sets where a method
works is not reporting a method.

### 3.4  Against classical detectors, the detector does not lead on SEM

[FIGURE P4 - baselines]

Every arm gets its own best parameter by the same leave-one-image-out rule, on the same
images, through the same scoring function. The result is the opposite of convenient.

On pavement this detector ranks **first of seven** ({dc_f1} against {dc_next} for the next
arm). On the SEM alloy it ranks **third of seven**: Sauvola local thresholding reaches
{in_sauvola} and Sato ridge {in_sato} against our {in_f1}. On the SEM coating it ranks
**fifth of seven**.

We built this detector for micrographs and it is beaten on micrographs by a local
threshold from 2000 and a ridge filter from 1998. The three leading arms on Inconel 718 are
separated by {in_spread} F1 — about the width of the gap we have previously called
irresolvable on a corpus this size — so the honest statement is that on SEM alloy this
detector and two classical filters are indistinguishable, and that the margin it enjoys on
pavement does not survive the change of modality.

What survives is the comparison's premise rather than its winner: none of these arms is
trained, all are tuned identically, and a reader can see what the whole classical family
reaches on each set.
