## 5  Discussion and conclusions

### 5.1  Interpretation of the principal measurement

The principal finding is what an overlap score on these collections measures. Both
annotations are painted strokes rather than traced lines — on the SEM frames a median of
{pr_sem_med}% of annotated pixels lie more than {pr_px} px inside the annotation, reaching
{pr_sem_max}% — and against such a reference the detector records a mean per-frame F1 of
{om_sem_f1} on SEM and {om_txm_f1} on TXM, where a geometrically correct three-pixel trace
of the same annotation records {om_sem_cf1} and {om_txm_cf1}. The detector is above that
trace on {om_sem_above} of {om_sem_n} SEM frames and {om_txm_above} of {om_txm_n} TXM
frames. **An overlap score on these collections therefore ranks resemblance to the
annotator's stroke rather than agreement about where the crack is**, which is the
conclusion Section 4.2 reaches for the transmission collection's own detector, arrived at
here independently on a second detector and a second modality.

A second reading of the same measurements concerns the denominator. Neither collection
adjudicates the whole frame, so every precision computed on it is a bracket, and the
distance between its ends is wider than most of the differences a reader would want to
draw from it. Section 3.1 gives both ends for that reason rather than choosing one.

### 5.2  Interpretation of the processing workflow

The evaluated branch uses image intensity, multiple spatial scales and explicit mask
operations. Each stage has a visible intermediate representation in Figure {fig_flow}, and
Figure {fig_flow} separates the operations that lead to the final area estimate. The
lower row of Figure {fig_flow} is the same three stages on a frame of the second
modality, which is where the inspectability earns something: the transfer there fails at the
candidate stage rather than at the filters, and Figure {fig_modality}(b) measures by how
much in the criterion's own units. The reported configuration retains the learned region classifier, so the
processing path is not free of fitted parameters; what it offers instead is a small and
inspectable one. Nine fitted numbers act on eight named geometric and intensity features
of each candidate region, every feature is readable off the mask, and the stage before it
is a rule that could be reproduced by hand. The cost is stated rather than set aside:
enabling the classifier lowers recall, intersection over union and F1 on every unit set
measured here, and its training images overlap the laboratory collection, so the
corresponding scores are in sample.

### 5.3  Conclusions

On this laboratory's own two collections, scored only on the pixels an operator ruled on,
the two detectors record a mean per-frame F1 of {om_sem_f1} over {om_sem_n} SEM frames and
{om_txm_f1} over {om_txm_n} TXM frames. Those numbers are not a ranking of how well the
cracks were found. A reconstruction of each frame's own annotation that is exactly right
about where every crack runs and wrong only about width scores {om_sem_cf1} and
{om_txm_cf1} against the annotation it came from, so the detector outscores a
geometrically correct trace by marking wide rather than by being better placed.

Pixel accuracy settles nothing either. Over every refereed frame of each arm, the
detectors score {sa_sem_acc}% and {sa_txm_acc}%
where a prediction that marks no crack at all scores {sa_sem_bg}% and {sa_txm_bg}%: a
hundredth of a point above that baseline on one arm, and below it on the other.

The same detector carried to the second modality clears an all-background prediction on
one of its two specimen series when the comparison is pooled over pixels; giving each
frame one vote instead, it is {tpf_mean_all} points from that prediction on average over
the {tpf_n} frames, with {tpf_pos_all} of them individually above it, and one specimen
group changes sign between the two aggregations. Section 4.3 reports both.

Where the transfer is lost is located rather than inferred. On the axis the detector
itself thresholds, the median annotated pixel sits below the operating point on
{mc_sem_below} of {mc_sem_n} SEM frames and {mc_txm_below} of {mc_txm_n} TXM frames, with
a median of {mc_sem_prop}% and {mc_txm_prop}% of the annotated crack proposed at all, so
the loss is at candidate generation and not at the filters that follow it.

Together these establish an interpretable workflow on the collections evaluated here, and
bound what its scores can be asked to settle.
