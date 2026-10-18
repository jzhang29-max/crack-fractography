## 2  The detector

Figure 1 is the whole path. Two gates do the detection: a robust median-absolute-deviation
cut at `mad_k` standard deviations, and an absolute floor on intensity. Everything else is
preparation and cleanup.

Two decisions are worth stating because both were made by measurement and both went against
the intuition that produced the code in the first place.

**The region classifier is switched off.** An eight-feature classifier scored each candidate
region, and deleting it improved every metric with no free parameters: paired median IoU
+0.2296 over thirteen specimens, p = 0.0024. Three specimens that had scored recall 0.0000
at every candidate setting ever tried were never invisible to the proposal stage; the
classifier was rejecting them.

**Tiles cannot stand in for frames.** Rules validated on 512 px crops deleted 40–43% of
hand-marked crack when run on whole frames. The widest crack in the training crops was
43.7 px; on full frames crack widths reach 178 px, so a region rule fitted on crops is
extrapolating on the object it most needs to keep.
