## 5  Negative results

These cost the most time and are the most likely to save someone else's.

**Retuning the detector for a different modality does nothing.** Applying the
SEM-calibrated detector to transmission X-ray tomography, we swept its two gating constants
singly and jointly, plus every morphology and size floor, under leave-one-specimen-out
selection. No arm beat doing nothing on held-out data; the joint optimum lost 0.021 F1 when
its selection was held out, and resolution-matching the scale ladder to the measured width
ratio moved F1 by 0.0008.

**That corpus cannot answer the question anyway.** It holds four specimens, so a paired
test has an exact two-sided floor of p = 0.125 — no result on it can reach significance at
any conventional level, a win or a null. One specimen carries 57.7% of all adjudicated
not-crack pixels, so the pooled score surface is essentially that specimen's.

**F1 is width-gameable where the labels are broad.** On the same corpus a
by-construction-correct 3 px crack scores F1 0.1260, *below* marking every pixel (0.1499),
while F1 climbs to 0.64 on marked width alone. "Beats the no-information floor on F1" is
necessary and not sufficient; precision lift separates where F1 does not.

**Six precision rules validated on crops were deleters on frames.** See §2.
