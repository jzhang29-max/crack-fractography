## 1  Why another crack detector

There are many. Most are learned, most report F1 or IoU against a benchmark, and most are
compared against each other at their own authors' operating points. Our interest is narrow
and practical: a materials laboratory needs crack measurements out of scanning-electron and
transmission X-ray micrographs, on a machine with no GPU, from a tool a researcher can
audit line by line and correct by hand. That rules out most of the field, and it makes the
natural baseline not a network but a threshold.

The detector here is close to that baseline. It flattens the background at seven scales,
takes pixels that are dark at any of them, applies a robust outlier cut and an absolute
darkness floor, and cleans the result. It has one free constant, `mad_k`. There is no
training step and no model file.

Reporting such a thing honestly turns out to be harder than building it, and most of this
paper is about the reporting. The detector is a threshold; what is less obvious is that the
scores conventionally used to grade one — F1 and IoU — cannot express the error a
materials laboratory actually suffers, which is a crack area fraction that comes out too
high or too low by some factor. Section 3.2 reports that factor, and Appendix A gives it
for every set we measured. It ranges from {md_ratio}x to {ebc_ratio}x for the same
unchanged detector.
