# CLAIMS — what this project can say, what it must qualify, and what is dead

Written 2026-10-13 as an end-to-end audit of the claim set: `analysis/conclusions.py`
(42 on-screen statements, 4 refusals, 4 named constants), `docs/REPORTING_GUIDE.md`,
`docs/PRACTICE_AND_PRIOR_ART.md`, `README.md`, and the provenance block in
`analysis/detector_overrides.py`.

This document decides what may go in the paper. It is deliberately conservative: a claim
that needs an assumption to survive carries that assumption **in its own row**, and a
claim whose number changes with the aggregation is not a claim until the aggregation is
named.

Every row is marked:

| mark | meaning |
|---|---|
| **STILL TRUE** | survives this week's measurements as written |
| **CAVEAT** | true, but unreadable or misleading without the qualifier in the row |
| **DEAD** | withdrawn; the row says what killed it |
| *(re-measured)* | I re-ran the measurement in this audit; the value in the row is what came out |
| *(on record)* | taken from the git record / a script docstring; not re-run here |

**The headline conclusion of this audit:** the strongest claims this project owns are the
**negative** ones (§5). Every positive claim about detector quality is either
aggregation-dependent, ceiling-limited, or below the corpus's own resolution. Section 6
lists five defects this audit found in the record itself, two of which affect numbers
already written down.

---

## 1. The five reading rules

No number below may be quoted without the rule that governs it.

**R1 — Name the aggregation before the number.** The same masks against the same labels,
scored five legitimate ways *(re-measured, `analysis/research/improve/aggregation.py`)*:

| aggregation | prec | recall | F1 | IoU |
|---|---|---|---|---|
| pooled over all pixels | 0.4182 | 0.6252 | 0.5012 | 0.3344 |
| median over the 26 TILES | 0.8056 | 0.7623 | **0.5922** | 0.4208 |
| median over 13 SPECIMENS (tiles pooled within) | 0.7950 | **0.5624** | 0.5192 | 0.3506 |
| median over 13 SPECIMENS (tile medians within) | 0.7897 | **0.7159** | 0.5418 | 0.3715 |
| median over TILES, 2 px tolerance | 0.8970 | 0.9200 | 0.6785 | 0.5134 |
| median over SPECIMENS (median in), 2 px tol | 0.8988 | 0.8025 | 0.6633 | 0.4962 |

The spread across these rows (recall 0.56 → 0.92) is larger than any model change ever
measured in this project. **"Median over specimens" is itself ambiguous** and the two
readings differ by 0.15 recall — say which.

**R2 — A median row is four separate order statistics, not a model's operating point.**
In the 26-tile row, precision, recall, F1 and IoU are each the median of 26 numbers over
*different* tiles. *(re-measured)*: the F1 implied by the quoted precision and recall is
**0.7833**, while the quoted F1 is the median per-tile F1, **0.5922** — a gap of 0.1911.
Only **5 of 26** tiles are at or above both medians; per-tile precision and recall are
rank-correlated **−0.227 (p = 0.26)**, i.e. the high-precision tiles are not the
high-recall ones. The triple (0.8056, 0.7623, 0.5922) describes **no tile that exists**.
Quote the median F1, or quote a pair and say it is a pair of medians.
`docs/REPORTING_GUIDE.md` §1 already states this for the per-specimen row (0.8479 vs
0.6633); the figures above are the same defect on the 26-tile row, with the evidence that
the two medians are not even weakly coupled.

**R3 — IoU must carry a ceiling of the same aggregation.** *(re-measured,
`approach4_q1_ceiling.py` + this audit)* A perfectly placed trace down the label's own
centreline peaks at:

| ceiling | value | at trace width |
|---|---|---|
| pooled over pixels | **0.4993** | 11 px |
| median over the 26 tiles | **0.5498** | 7 px |
| per-tile oracle width (upper bound) | 0.5920 | per tile |

So: pooled model IoU 0.3344 is **67.0%** of the pooled ceiling; median-over-tiles IoU
0.4208 is **76.5%** of the median ceiling. **The "84% of what is achievable" figure in
circulation is 0.4208 ÷ 0.4993 — a per-tile median over a pooled ceiling.** Do not use it.

**R4 — The pooled row needs the void tile named; the median row does not.**
*(re-measured)* `MAR_H_HIP_CBS_0002__crop_3122_120_512x512` contains an off-specimen void
and holds **141,480 of 176,225 pooled false positives (80.3%)** against 554 true
positives. Removing it moves the pooled row 0.4182/0.6252/0.5012/0.3344 →
0.7840/0.6247/0.6953/0.5330, and moves the median-over-tiles row only 0.4208 → 0.4335 IoU.
The void caveat is a property of pooling, not of the detector; both rows are honest and
the pooled one is unreadable alone.

**R5 — State the tolerance.** 2 px of slack is worth +0.09 IoU and +0.09 F1 here
(and ~22 F1 points in the literature, Kompanets 2024). A number without its tolerance is
not comparable to a published one.

---

## 2. Detector-accuracy claims

| # | Claim | Status | Measurement / what qualifies it |
|---|---|---|---|
| D1 | "Precision and recall come from one model, one configuration, one prediction set — nothing is fitted per metric." | **STILL TRUE** *(re-measured)* | One mask per tile from the shipped stage (`detector_overrides.install`, classifier off, 7-scale union, mad_k 5.0, absolute_dark 10); precision and recall are two readings of the same tp/fp/fn. No metric-specific tuning exists anywhere in `tilebench.py`. **But see R2**: in the *median* rows the two numbers come from different tiles, and **see D2**: the mask scored is not byte-identical to the app's. |
| D2 | "The scored masks equal what the app emits to within 242 px over all 26 tiles" (`docs/REPORTING_GUIDE.md` §1). | **CAVEAT — materially weaker than stated** *(re-measured, this audit)* | True of a *reimplementation* of the candidate stage (`app_truth.py`: `clean_mask` → 8-connected label → ≥40 px; 242 px over 26 tiles). The app's only detect path is `detect_one.py` → `unified_pipeline.run_unified_pipeline`, which also runs **Pass 2** (concavity / bridge-corridor / interior-fill candidates). Running that real function on the tiles: the app keeps **17,972 px the scored mask does not, and loses none**, over the 20 of 26 tiles whose raster survives the pipeline's own `find_field_of_view` crop. Per-tile IoU moves **−0.191 to +0.073**. The other 6 tiles cannot be run through the app's path at all — the FOV detector crops a 512 px tile to e.g. 385×512. Assumption if quoted: the benchmark measures the *candidate stage*, which is the stage the shipped changes act on; it does not measure the app's emitted mask. |
| D3 | "The region classifier is OFF, and switching it off is an improvement." | **STILL TRUE** *(on record; paired median IoU +0.1753, 11/13, Wilcoxon p = 0.0061, zero free parameters)* | Caveat the paper must carry: with the classifier off, `detect_one.py` keeps **every** row of `df`, which now includes Pass-2 proposals the model itself scored not-crack — *(re-measured)* 15,670 px over 6 sampled tiles. "The classifier is off" is a broader change than the tile experiment tested. |
| D4 | "IoU 0.42 is 84% of what is achievable against these labels." | **DEAD** *(re-measured)* | Mixes aggregations (R3). Like-for-like it is 67.0% (pooled) or 76.5% (median). Replace with R3's table. |
| D5 | "The detector scores 0.5507 on skeleton-F1 at τ = 2, an instrument that is not width-gameable." | **STILL TRUE** *(re-measured; `honest_score.py` reproduces to 4 dp)* | Quote with its floor and ceiling: a no-information dilation to 1.5× area moves it +0.0015 (p = 0.68), where it moves clDice +0.0478 on 13/13 (p = 0.0002). This is the most defensible single accuracy number the project has. |
| D6 | "The last shipped change (v1.48 single scale → v1.49 seven-scale union) is an improvement." | **CAVEAT — below the corpus's own resolution** *(re-measured)* | Paired over the 13 specimens: clDice **+0.0408, median +0.0085, 7 better / 3 worse / 3 tied, Wilcoxon p = 0.19**; skeleton-F1 τ=2 **+0.0452, p = 0.037**, while the per-tile median skeleton-F1 *falls* 0.5518 → 0.5507. The corpus resolves about **+0.047** for an arm this correlated with the baseline. Defensible statement: the change is a **strict superset** (0 px deleted, verified) that does not make anything worse; it is not a demonstrated gain. |
| D7 | "The corpus resolves about +0.14 clDice for a structurally new method and +0.05 for a close variant at n = 13." | **STILL TRUE** *(on record, `a4/q3_power.json`; observed sd of the paired difference 0.1694 at r = 0.601 → +0.1434; 0.0558 at r = 0.965 → +0.0473)* | This is a claim about the corpus, not the method, and it is one of the strongest things here. The nonparametric floor matters too: at n = 13, 10-of-13 improving gives sign-test p = 0.092 — a method can win on 10 specimens and still not clear 0.05. |
| D8 | "`absolute_dark_thresh` stays at 10." | **STILL TRUE, as a judgement with its evidence** *(on record)* | Three instruments disagree: 41 SEM frames say raise it (recall 0.2983 → 0.4049 at t=20), the 26 tiles say no (LOSO picks t=10 in 12–13 of 13 folds), TXM says no mildly (F1 0.3750 → 0.3635). Report as an exposed, unresolved parameter, never as a tuned optimum. |
| D9 | "Recall is lost at candidate generation, not at the classifier." | **STILL TRUE with its unit named** *(on record)* | 70.13% of painted crack is never proposed at **frame** scale; the same quantity reads 45.7% on the 512 px **tiles**, so the tiles understate it by 24 points. The darkness cut is 96.02% of the loss; morphology is 4%. Two frames hold 45.97% of the loss — never quote it pooled alone. |
| D10 | "Model size: 4 KB against 293 MB – 3.2 GB for the deep baselines." | **STILL TRUE** *(on record)* | The only comparative claim against deep baselines that survives. It is a size claim and nothing else — see N4 for speed. |
| D11 | Full-frame recall "0.7911". | **DEAD** *(on record, corrected in `REPORTING_GUIDE.md`)* | That was the alphabetically-first 12 frames from two specimens. Over all 41 painted frames: **0.2983 pooled, 0.6464 per-frame median**, and five frames holding 57.9% of all painted crack all sit at 0.10–0.36, so the pooled figure *is* those five frames. The string 0.7911 still appears in `analysis/detector_overrides.py` as the record of a superseded measurement — it is labelled there, but anyone grepping for a recall number will find it. |

---

## 3. Corpus and measurement claims (the app's own read-out)

`analysis/conclusions.py` emits 42 statements. Most are per-frame descriptions that
restate a measured quantity and need no audit. These are the ones that carry weight
outside the app.

| # | Claim | Status | Measurement / what qualifies it |
|---|---|---|---|
| C1 | "0 of 9 / 0 of 9 / 0 of 4 / 0 of 4 specimen-arms reach ASTM E562's ±10% relative-accuracy target." | **STILL TRUE — and the four zeros are the claim** *(re-measured from `analysis/out/specimens.json`)* | sem/gated 0 of 9 (RA 32.2–138.0%), sem/machine 0 of 9 (38.5–125.8%), txm 0 of 4 (30.8–52.0%), txm/machine 0 of 4 (29.2–50.7%). The best relative accuracy anywhere in the corpus is ±29.2%, ~3× the target. **Assumption in the row:** the denominator is specimen-arms that *have* an interval — 5 of 14 SEM specimen-arms per arm have fewer than 3 fields and carry none, so "0 of 14" would be a different and unsupported statement. Never pool the arms into "0 of 22" or "0 of 26": they are different instruments. |
| C2 | "Specimens cannot be ranked by this sampling design." | **STILL TRUE** | One imaged site per specimen, so between-field and between-specimen variance are the same component (spatial pseudoreplication, Hurlbert). Fires on 33 of 34 real specimen-arms and is unconditional on interval width. Note the one piece of prior art that bounds its scope: Dahari et al. (2025, ImageRep) estimates a within-image representativity interval for a phase fraction, so "no remedy exists without more patches" is false as stated — but ImageRep does not estimate between-patch variance, which is what this corpus lacks. |
| C3 | "Detector alone moves the measured area fraction 2.29×" / "CBS carries 1.8× to 6.0× ETD's centreline depending how much ETD found." | **STILL TRUE, and must never be shown as a constant** | 36 paired fields at one magnification; CBS longer on 35 of 36 so the **direction** is established, the **size** is not: stratified by ETD's own area fraction it runs 6.0× / 4.9× / 3.4× / 1.8× (Spearman −0.61, p = 8e-5) and spans 0.11×–31.1× inside one specimen. Confounded with specimen (four specimens are CBS-only), and a large share is reproduced by this repository's own segmenter before any detector physics. Not a correction factor. |
| C4 | "No instrument in this dataset can referee a crack-width change under the detector swap." | **STILL TRUE** | area/length width is log(area) − log(length) by construction; the two independent calibres are strongly monotone in region area (log-log slope 0.426 and 0.561), a size-only null overshoots one (1.53× vs 1.26× observed) and size-matched strata put both at unity (0.97×, 1.02×). The app asserts no width result in either direction — keep it that way. |
| C5 | "Crack width separates the TXM specimens by more than each one varies." | **CAVEAT** | Separation, never ordering: one imaged site per specimen, so the named extremes are not a result. Only valid because all those frames sit at one magnification. |
| C6 | "Cracking rises toward one edge of the raster in all positioned specimens." | **CAVEAT** | p = 0.0119 is the **floor** of the exact permutation test at nine points (1 of 84 arrangements), not a small p-value. The high-stage-Y row is also the first-acquired row in every specimen, so position and acquisition order cannot be separated; stage Y maps to no declared build or loading axis; step vs ramp is undecidable at nine points. |
| C7 | "Crack area is not a resolution artefact: it survives a 6× coarser pixel." | **STILL TRUE, scoped** | A calibration at 51.883 nm/px (36 fields, median area ratio 1.000, CI 0.998–1.001), with a null that can fail (1–2 px synthetic cracks retain 0.04 of their area at 3× and 0.00 at 6×). True of an **area-preserving** binarisation only — a dilating rule inflates the same fields to 1.47× at 6×. Says nothing about crack *count*. Correctly silent on TXM, where it was never measured. |
| C8 | "One crack holds ≥90% of the crack area" (the dominance regime call). | **CAVEAT** | The 0.90 cut is the app's own, not a standard's; the call flips between detectors on 4 of 56 double-imaged fields (7.1%); it is per-field, not per-specimen, and confounded with field size (Spearman +0.49 with nm/px). The earlier framing — that dominance is the one detector-invariant metric — is **DEAD**: at the modal magnification the share does move (0.790, CBS lower on 29 of 36, p = 3.1e-4), and the pooled 0.870/p = 0.084 that suggested invariance was three scale strata mixed together. |
| C9 | "MCL is a bound, not a value, when ≥25% of length touches an edge." | **STILL TRUE** | Report the bracket (with and without censored regions). The count share understates the length share several times over, which is why the weighting is named. |
| C10 | "Length is unreliable where two estimators disagree >1.5×" (TXM: skeleton over Buffon, median ratio 0.466 ≈ 2.1× overestimate). | **STILL TRUE** | The 1.5× threshold is the app's own and is labelled as such; the TXM figure is self-disqualifying at either threshold. |
| C11 | The four refusals (transgranular/intergranular; R_L & tortuosity; ductile/brittle; depth & a/c). | **STILL TRUE, and the first is the strongest of the four** | The crack-mode refusal is backed by a *measured geometric budget* (facet call needs ≥13 µm facets; the corpus's largest resolvable microstructural intercept is 3.02 µm) and by a positive control that caps a by-construction-true path at z = +0.62 where the real labels read z = +2.0 to +3.4 — impossible as a path signal, so the apparent signal is contamination. R_L is an identity against an undeclared axis: (length/chord)·sec θ, corpus median exactly 1.4142. |
| C12 | "Linearity / tortuosity / branching as a crack-mode index." | **DEAD** | Per-branch length/chord medians 1.011–1.055 across seven specimens sit *inside* a mathematically straight line's own range (1.001–1.082, median 1.0605, set by angle to the pixel grid) and below its median. It measures staircasing. |

---

## 4. Claims the product makes, or fails to make

| # | Claim | Status | Note |
|---|---|---|---|
| P1 | "The app shows the user how accurate the detector is." | **DEAD — never was true** *(re-measured: no match for precision/recall/IoU/tile-benchmark in `app/templates` or `app/static/app.js` outside the E562 relative-accuracy wording)* | Every detector-accuracy number in this project lives in `docs/` and in a provenance comment. The app that emits the masks displays none of it. If the paper says the tool reports its own uncertainty, that is true of the **stereological** interval (E562, censoring, scale) and false of the **segmentation**. |
| P2 | "Corrections always override the model." | **STILL TRUE** *(on record)* | Repaired: Pass 2 used to re-propose pixels the human had erased or marked not-crack. |
| P3 | "Each uploaded image is measured on its own; uploads are not a specimen." | **STILL TRUE** | The pseudo-specimen carries no interval and is excluded from ranking refusals and arm statistics. |

---

## 5. The negative results — and why they are the strongest thing here

On the evidence this audit reviewed, **the transferable contribution of this project is
its negative results.** Each one below is (a) measured on a larger unit set than the
positive claims, (b) reproducible, and (c) carries a structural cause rather than a
tuning story. None of them depends on the detector being good.

| # | Negative result | Status | Evidence |
|---|---|---|---|
| N1 | **Six region-level precision rules were rejected; a tile score cannot rank a rule that rejects regions.** | **STILL TRUE — with the count qualified** *(on record)* | Four delete 54–75% of the hand-marked crack the shipped path keeps, on the same 48 frames (70,041,625 painted px) through the same denominator: retrained region classifier 72.67% (76.72% against the v1.49 candidate stage), texture veto 67.54%, thickness excision r=50 62.43%, r=100 54.62%. **The fifth and sixth died differently and the row must say so:** specimen segmentation — every variant that passes the full-frame gate scores the shipped tile IoU to four decimals, and the best-on-tiles variant deletes 27.3%; enclosure — safe, deletes nothing, fires on two blobs in 48 frames and changes no score. So: six rules, four deleters, two worthless. "Six rules delete 54–75%" is **not** accurate. |
| N2 | **A 512 px crop cannot contain a wide crack, so tile-validated rules extrapolate into unseen feature space.** | **STILL TRUE — the structural cause behind N1** | Tile paint tops out at 43.7 px mean width (training positives span MeanWidth 2.61–29.34 px); regions holding painted crack on full frames span MeanWidth 18–236 px and MaxWidth 42–654 px — disjoint support. 19.6% of real crack regions are wider than anything in the tiles, and 88.0% of every deleted crack pixel lies in a region wider than any training positive. |
| N3 | **IoU and clDice are both width-gameable against these labels; skeleton-F1 at τ=2 is not.** | **STILL TRUE** *(partly re-measured)* | A no-information dilation to 1.5× area moves clDice +0.0478 on 13 of 13 specimens (p = 0.0002) and moves skeleton-F1 +0.0015 (p = 0.68). Mechanism localised: clDice's `tsens` half asks whether the label's own medial axis is covered, and against an 8.7 px brush a prediction reaches it by getting fatter. A perfectly placed trace's IoU swings 0.2490 → 0.4993 on thickness alone with localisation held perfect *(re-measured)*. |
| N4 | **Four model families all tie or lose to a one-line threshold.** | **STILL TRUE** *(on record)* | U-Net on the 26 tiles; U-Net on 70M px of full frames (best arm clDice 0.5719 vs the one-line threshold's 0.6205 and the shipped 0.6405; worse than the threshold on 9 of 13, p = 0.2163; and disqualified anyway — as a replacement it deletes 51.17% of kept hand-marked crack on 44 of 48 frames); three context formulations, every one of which lost to an isotropic dilation given the same pixel budget, with leave-one-specimen-out picking λ = 1 (no context at all) in 13 of 13 folds; and a retuned operating point. Add the corollary *(re-measured)*: on pooled IoU the LOSO-picked one-line threshold scores **0.4021 against the shipped model's 0.3344**. |
| N5 | **The corpus cannot resolve the improvements being made on it.** | **STILL TRUE** *(on record + re-measured)* | +0.14 clDice needed for a new method, +0.047 for a close variant, at n = 13 specimens. The last shipped change scores +0.0408 (p = 0.19) — see D6. A single arm's headline clDice has a specimen-bootstrap 95% CI of width 0.217. |
| N6 | **The aggregation moves the number more than any model ever has.** | **STILL TRUE** *(re-measured)* | R1's table: recall 0.5624 → 0.9200 across legitimate aggregations of one unchanged set of masks. The largest model effect measured in this project is ~+0.17 clDice (shipped vs the weakest one-line arm). |
| N7 | **Nothing in this corpus meets ASTM E562's accuracy target — four per-arm zeros.** | **STILL TRUE** *(re-measured)* | See C1. |
| N8 | **No novelty framing survives.** | **STILL TRUE** *(on record)* | 55 of 55 tested framings were found to be prior art (DiameterJ 2015 for the metric family and the segmentation-sensitivity result; Fiji AnalyzeSkeleton; Dershowitz & Herda 1992; Underwood & Banerji; ISO 643 / ASTM E562, E1382, E1245, E2283; Schmies et al. 2024 for same-field multi-channel on cracks; Lu et al. for device-indexed sensitivity profiles; Salvato et al. 2023 for acquisition-driven extent changes; ISO 5725 / ASTM E2782 for the repeatability/reproducibility framing). **The magnitudes measured on this material are what is unowned, not the ideas.** |

**How to write this up.** The honest shape of a paper from this corpus is: *here is a
measurement problem where the label geometry caps every pixel metric* (N3, R3), *where
the validation unit everyone uses cannot contain the object* (N2), *where six plausible
precision rules and four model families all fail against full-frame paint* (N1, N4),
*where the achievable effect size is below what n = 13 specimens can resolve* (N5), and
*where no arm reaches the standard's accuracy target* (N7). The detector is the vehicle,
not the contribution.

---

## 6. Defects this audit found in the record

Five, in order of how much they change a written number.

1. **The "84% of the achievable IoU" figure is a mixed-aggregation ratio** (R3 / D4). Like
   for like it is 67.0% or 76.5%. It is live in three places as of commit `e61a4d9`:
   `docs/REPORTING_GUIDE.md` §1 ("IoU 0.4208 is 84% of what is achievable against these
   labels"), the `SHIPPED_V1491` docstring in `analysis/research/tilebench.py`, and the
   provenance block in `analysis/detector_overrides.py`. All three need the same one-line
   correction: either quote 0.3344 against 0.4993 (pooled, 67.0%) or 0.4208 against 0.5498
   (median over tiles, 76.5%).
2. **"The scored masks equal what the app emits"** — `docs/REPORTING_GUIDE.md` §1,
   "to within 242 px over all 26 tiles ... always in the app's favour" — is true of a
   reimplementation of the candidate stage, not of `run_unified_pipeline`, which is what
   the app calls (D2). The app keeps 17,972 px more over 20 tiles, all of it Pass 2, and
   6 of the 26 tiles cannot be pushed through the app's path at all. The direction
   ("always in the app's favour") is right; the magnitude is 74× larger than stated and
   the per-tile IoU effect reaches −0.191.
3. **Switching the classifier off also accepts Pass-2 proposals the model scored
   not-crack** (D3) — 15,670 px over 6 sampled tiles. The provenance block does not
   mention this, and the tile experiment that justified the change did not test it.
4. **"Six precision rules delete 54–75% of hand-painted crack"** conflates four deleters
   with two rules that died for other reasons (N1).
5. **"Median over 13 specimens" names two different statistics** that differ by 0.15
   recall (R1), and the median row's F1 is not the F1 of its own precision and recall
   (R2).

---

## 7. What would change a verdict

| To revive | You would need |
|---|---|
| Any comparison to published methods | Not available. Frozen, the detector scores F1 0.0000 on CrackForest; with the one parameter every published arm is allowed to fit, 0.4886 against a published ~0.7177; 0.0630 on ceramics. |
| Any speed claim | Not available. It loses to a plain single-pass U-Net by 1.6× at p = 0.0001. |
| A demonstrated (not merely safe) detector improvement | A gain above +0.047 clDice paired over the 13 specimens, or more specimens. The gain has to clear the corpus, not the tile set. |
| Specimen ranking | A second imaged site per specimen. Nothing else. |
| Transgranular vs intergranular | EBSD on one or two of the same fields, or an etched co-registered image. The facet route is closed by a measured geometric budget, not by tuning. |
| A width result under the detector swap | An instrument that is not monotone in region area. None exists in this dataset. |
| A claim that the benchmark measures the app | Score the mask `detect_one.py` actually writes, on frames rather than 512 px tiles — the FOV crop means the tiles cannot be pushed through that path unmodified. |

---

## 8. Reproducing this audit

All runs used `/Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python -B`,
scoring through `analysis/research/tilebench.py` only. `tilebench.controls()` was asserted
at the top of every run (oracle 1.0, empty 0.0, mark-everything = prevalence 2.9730%).

| What | Script |
|---|---|
| the five aggregations (R1, R2) | `analysis/research/improve/aggregation.py` |
| the ceiling under each aggregation (R3) | `analysis/research/improve/approach4_q1_ceiling.py`, plus the median-ceiling sweep in this audit |
| the void tile's share of error (R4) | this audit |
| the app's real mask vs the scored mask (D2, D3) | this audit, driving `unified_pipeline.run_unified_pipeline` with `ORIGINAL_DIR` rebound to a scratch directory so nothing is written into the archived read-only repo |
| the last shipped change per specimen (D6) | this audit, clDice via `approach4_lib` and skeleton-F1 at τ=2 |
| E562 four zeros (C1, N7) | this audit, from `analysis/out/specimens.json` |
| resolution limit at n = 13 (D7, N5) | `analysis/research/improve/approach4_q3_power.py` |

**How each new check was shown to be capable of failing**, because a check that cannot
fail is not evidence:

* *The mixed-aggregation finding (R3).* The same script computes the pooled and the
  median ceiling side by side. The pooled arm reproduced the published 0.4993 at an
  11 px trace to four decimals; the median arm returned 0.5498 at 7 px. Had the script
  been silently pooling in both places, the two would have been identical — they are not,
  so the instrument distinguishes the two aggregations it is used to separate.
* *The app-mask finding (D2).* Three of the twenty comparable tiles returned a difference
  of exactly 0 px, so the comparison can report agreement. The difference is one-sided
  (0 px lost on every tile), which the script does not enforce and which the superset
  argument predicts. On the void tile the 3,257 app-only px decompose into 3,247 px of
  Pass 2 plus 10 px — and 10 px is exactly what the independently written `app_truth.py`
  measured for that tile from 8-connectivity alone.
* *The v1.48 → v1.49 comparison (D6).* The run asserts that v1.48 keeps no pixel v1.49
  drops; it came out 0, as a strict superset requires. A non-zero would have meant the
  single-scale arm was reimplemented wrongly and the comparison was between two different
  pipelines rather than two settings of one.
* *The E562 four zeros (C1, N7).* Moving the target off the standard's ±10% makes the
  counter non-zero — ±35% gives 1 of 9 / 0 of 9 / 2 of 4 / 2 of 4 and ±60% gives
  3 / 2 / 4 / 4 — so the zeros are a property of the data at the standard's own target,
  not a counter that is stuck.
* *Every scoring run* asserted `tilebench.controls()` first, which fails loudly if the
  oracle does not score 1.0, the empty predictor 0.0, or mark-everything a precision
  equal to the 2.9730% prevalence.
