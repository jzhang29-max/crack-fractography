## 5  Discussion and conclusions

### 5.1  Interpretation of the principal measurement

The principal finding is close aggregate area agreement for a deterministic detector applied
to the evaluated Inconel 718 collection. A reference fraction of {ag_best_lab}% and a
predicted fraction of {ag_best_mark}% differ by 0.024 percentage points. Expressing the
result in both image-area units and relative reference-area units makes the measurement scale
explicit. The ratio of {ag_best} supplies an interpretable summary for readers comparing
marked area with the reference total.

The complete displayed comparator set places this result in context. Among the seven
summaries, the darkness detector has the smallest absolute deviation of the area ratio from
unity. The field-level count provides a complementary observation: the selected setting has
lower reported absolute area error than the default in most of the evaluated whole fields.
Section 3.4 adds the information that the earlier selection could not have identified any
other setting, because its grid stopped at the default; the extended sweep locates the
crossing and the selected setting survives it.

### 5.2  Interpretation of the processing workflow

The evaluated branch uses image intensity, multiple spatial scales and explicit mask
operations. Each stage has a visible intermediate representation in Figure 1, and Figure 2
separates the operations that lead to the final area estimate. Disabling the learned region
classifier gives the reported configuration an inspectable processing path without a learned
region-classification step.

The reported specificity of {ag_best_spec}% indicates high background rejection in the
reference background population. This observation is consistent with the intended use of a
darkness criterion to identify a relatively small foreground population. It complements the
area measurement while retaining its own definition and denominator.

### 5.3  Conclusions

A multiscale darkness detector achieved close reported agreement with the aggregate reference
crack area in {in_n} Inconel 718 SEM whole fields. At a MAD multiplier of {mk_best}, the
predicted area was {ag_best_mark}% against a reference of {ag_best_lab}%, giving a ratio of
{ag_best} and an approximately {ag_best_err_pct}% relative aggregate discrepancy. The
detector also recorded {ag_best_spec}% background specificity and the closest area ratio to
unity among the seven displayed comparator summaries.

Two results reported here qualify that conclusion rather than supporting it. The pixel
accuracy at the selected setting, {wf6_acc}%, is below the {in_empty_acc}% of an
all-background prediction, and Section 3.5 shows that the entire range available to pixel
accuracy on this collection is {wc_f_head} percentage points, so no configuration could have
been distinguished on that endpoint. And the same detector carried to a second imaging
modality clears an all-background prediction on one specimen group of four.

Together these establish an aggregate area result and an interpretable workflow within the
evaluated collection, and they bound how far either should be read.
