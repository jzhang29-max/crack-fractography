## 1  Why another crack detector

There are many. Most are learned, most report F1 or IoU against a benchmark, and most are
compared against each other at their own authors' operating points. Our interest is narrow
and practical: a materials laboratory needs crack measurements out of scanning-electron and
transmission X-ray micrographs, on a machine with no GPU, from a tool a researcher can
audit line by line and correct by hand. That rules out most of the field, and it makes the
natural baseline not a network but a threshold.

The detector here is close to that baseline. It flattens the background at seven scales,
takes pixels that are dark at any of them, applies a robust outlier cut and an absolute
darkness floor, and cleans the result. There is no training step and no model file.

**On "one parameter".** One constant, `mad_k`, is exposed and swept; that is the sense in
which the title means it, and it is the only one given a grid in any comparison here. It is
not the only constant. `absolute_dark_thresh = 10` is a second gate, held fixed rather than
fitted in this paper but chosen by leave-one-specimen-out on our own corpus, where it
supplies roughly half the proposal-stage recall — on the alloy measured here it supplies
almost none (Section 3.6), and three instruments in our own records disagree about its
value. Behind those sit a seven-rung scale ladder and two size floors, frozen. A reader
comparing this against a single-parameter classical filter should know that the filter
carries one constant and this detector carries a frozen preprocessing budget.

**Related work.** Reporting a segmentation as an area budget rather than as an overlap
score is not new: it is standard practice in land-cover accuracy assessment, where Olofsson
et al. [6] set out the error matrix in units of area proportion together with a
bias-adjusted area estimator and its confidence interval. Materials microscopy has the same
instinct — Durmaz et al. [7] report the downstream morphological quantity beside the
segmentation score — and a materials laboratory's own standard, ASTM E562 [8], is written
in area fraction and in nothing else. This paper claims no novelty for that framing. What
it offers is the measurement: the full budget for one detector on one alloy, in the units
the laboratory reports, together with the ways the usual scores mislead about it. The
classical arms it is compared against are the standard ones [1–5].

Reporting such a thing honestly turns out to be harder than building it, and most of this
paper is about the reporting. The detector is a threshold; what is less obvious is that the
scores conventionally used to grade one — F1 and IoU — cannot express the error a
materials laboratory actually suffers, which is a crack area fraction that comes out too
high or too low by some factor. Section 3.3 reports that factor, and Appendix A gives it
for every set we measured. It ranges from {md_ratio}x to {ebc_ratio}x for the same
unchanged detector.
