# What to put in the paper, and how to read each number

Written 2026-10-12 from measurements in this repository. Every figure here was produced by
a script under `analysis/research/`; none is quoted from memory or from a summary.

---

## 1. The headline table

The detector, scored against 26 tiles the labeller painted **from a blank mask**, so it had
no hand in them. Selection is leave-one-**specimen**-out over 13 specimens.

**State the aggregation and the tolerance or the number means nothing.** The same masks and
the same labels, under five legitimate choices — the spread is larger than the difference
between any two methods ever tested on this corpus:

| aggregation | precision | recall | F1 | IoU |
|---|---|---|---|---|
| pooled over all pixels | 0.4182 | 0.6252 | 0.5012 | 0.3344 |
| median over the 26 tiles | 0.8056 | 0.7623 | 0.5922 | 0.4208 |
| median over 13 specimens | 0.7897 | 0.7159 | 0.5418 | 0.3715 |
| **median over tiles, 2 px tolerance** | **0.8970** | **0.9200** | 0.6785 | 0.5134 |
| **median over specimens, 2 px tolerance** | **0.8988** | **0.8025** | 0.6633 | 0.4962 |

Both qualifiers are standard: per-image medians and a stated tolerance are what the crack
literature reports (CrackForest is published at F1 75.35 at 0 px and 97.10 at 2 px — same
paper, same model). The recommended row for a write-up is **median over specimens at 2 px**,
because the specimen is the unit that repeats and the tolerance is declared.

**Do not compute F1 from the median precision and the median recall.** That gives 0.8479 and
describes a specimen that does not exist — the high-precision specimens are not the
high-recall ones. The median of the per-specimen F1s is **0.6633**. Quote that.

**IoU must be quoted with its ceiling — like for like.** A *perfectly placed* trace, down the
label's own centreline with zero localisation error at its best width, caps at **IoU 0.4993**
pooled (an 11 px trace) and **0.5498** as a median over tiles (a 7 px trace). The ceiling is
aggregation-dependent too, so it must be read in the same units as the score:

| | achieved | ceiling | fraction |
|---|---|---|---|
| pooled | 0.3344 | 0.4993 | **67.0%** |
| median over tiles | 0.4208 | 0.5498 | **76.5%** |

An earlier draft of this file said "84%". That divided a per-tile MEDIAN by a POOLED ceiling
and is withdrawn. Either row above is defensible; mixing them is not.

**One tile of 26 holds 80.3% of all false positives** — an off-specimen void, 141,480 FP
against 554 TP. Excluding it, pooled precision is 0.7840. Give both or neither.

**The scored masks are NOT what the app emits, and an earlier draft of this file said they
were.** That claim compared two reimplementations of the CANDIDATE STAGE, which differ only
by the 4- vs 8-connected spelling of the 40 px filter (242 px over 26 tiles). The app calls
`unified_pipeline.run_unified_pipeline`, which also runs a **Pass 2** — concavity,
bridge-corridor and interior-fill proposals — and with the region classifier switched OFF
`detect_one.py` keeps every row of `df`, Pass-2 rows included, which the model itself scored
not-crack. Driving the real function:

    the app keeps 17,972 px MORE than was scored, over the 20 of 26 tiles whose raster
    survives the pipeline's own find_field_of_view crop, and loses none.
    pooled      precision 0.4181 -> 0.4094   recall 0.6255 -> 0.6487   IoU 0.3344 -> 0.3351
    per specimen                              recall 0.7159 -> 0.7858

So "the classifier is off" is a broader change than the tile experiment tested. The direction
is favourable — more recall, slightly less precision, IoU essentially unmoved — but the
scored numbers describe the candidate stage, not the shipped output, and should be labelled
that way until the app's own masks are scored directly.

**"Median over specimens" is ambiguous and the two readings differ by 0.15.** Median of the
per-tile medians gives recall 0.7159; pooling each specimen's pixels first gives 0.5624. This
file means the former. Say which you mean.

**The 26-tile median row has the F1 defect too.** Median precision 0.8056 and median recall
0.7623 would imply F1 0.7833; the quoted 0.5922 is the median per-tile F1. Only 5 of 26 tiles
reach both medians, and per-tile precision and recall rank-correlate **-0.227**. The triple
describes no tile that exists — quote the median F1, never the F1 of the medians.

## 2. Full frames: pooled and per-frame disagree, and both belong

Scored against the hand-painted correction masks on 41 frames (70,041,625 painted px),
counting only refereed pixels — crack and not-crack — and excluding the 91% of the corpus
nobody has reviewed.

| | recall on hand-painted crack |
|---|---|
| pooled, area-weighted | 0.2983 |
| per-frame median | 0.6464 (p25 0.358, p75 0.808) |

Five frames hold **57.9%** of all painted crack and every one sits at recall 0.10-0.36, so
the pooled figure is essentially those five frames. A subset of 12 frames from two
specimens pools to 0.7911 — if a number like that appears anywhere, check which frames
produced it.

## 3. The measurements, which matter more than IoU

Per-tile ratio of the detector's measurement to the same measurement on the hand labels.
1.000 is perfect.

| | previous | current |
|---|---|---|
| area fraction | 0.419 | **0.951** |
| crack length | 0.469 | 1.095 |
| crack width | 0.928 | 0.925 |
| crack count (components >= 250 px) | 0.211 | 0.95 |

Pooled and area-weighted over the 25 non-void tiles the area fraction is 0.42x -> 0.80x, so
corpus totals still under-report by about a fifth. Raw crack counts read 1.5x because they
include sub-100 px specks; **always report counts with a minimum component size.**

## 4. What is defensible, and what is not

**Defensible, and measured here:**

- An independent ground truth: tiles sampled uniformly and painted from blank, against a
  corpus whose own labels are broad-brush (median stroke 59 px; full-frame paint has a
  median width of 192 px).
- Held-out numbers with their brackets, and the pooled/per-frame split stated.
- The negative results, which are the most transferable part: six region-level rules that
  score well on 512 px crops and then delete 54-75% of hand-painted crack on full frames.
  The structural cause is that **a 512 px crop cannot contain a wide crack** — tile ground
  truth tops out at 43.7 px mean width while real painted cracks reach 178 px, and 19.6% of
  real crack regions are wider than anything in the tiles.
- The metric critique: on this SEM corpus a physically correct 3 px trace scores IoU 0.1662;
  on TXM it scores 0.0498. Any IoU above that is bought by being thicker than a crack.
- Model size: 4 KB, against 293 MB - 3.2 GB for the deep baselines.

**Not defensible — do not write these:**

- Any claim of beating published methods. Frozen at its settings this detector scores
  **F1 0.0000** on CrackForest; given the one parameter every published arm is allowed to
  fit, 0.4886 against a published ~0.7177. On ceramic cracks, 0.0630.
- Any speed claim. It loses to a plain single-pass UNet by 1.6x at p=0.0001.
- Any novelty framing. 55 of 55 tested framings were found to be prior art. The magnitudes
  measured on this material are what is unowned, not the ideas.
- Pooled numbers without the void caveat, or IoU on TXM as a ranking.

---

## 5. What each metric means, and how to read it

| metric | in one sentence | no-information floor | ceiling on this data | read it as |
|---|---|---|---|---|
| **recall** | of the crack that is really there, the fraction you found | **1.000** — marking every pixel scores a perfect recall | 1.0 | never alone; only at a stated precision |
| **precision** | of what you marked, the fraction that is really crack | the prevalence of crack: **0.0297** on SEM tiles, **0.0810** on TXM refereed px | 1.0 | as a multiple of the floor ("lift"); below ~2x it is close to noise |
| **lift** | precision divided by the floor | 1.00 | — | >3 is a real signal; 1.09 is what Otsu scores, i.e. nothing |
| **F1** | the balance of precision and recall, so it cannot be gamed by marking everything | 0.0577 SEM tiles / 0.1499 TXM | 1.0 | the single best summary number here |
| **IoU** | overlap divided by union — the strictest pixel measure | 0.0297 / 0.0810 | **0.1662** (SEM) and **0.0498** (TXM) for a *correct* 3 px crack | comparable only at a stated tolerance; never rank TXM on it |
| **clDice** | overlap of the centre-lines, so it scores where the crack *runs*, not how fat it is drawn | ~0 | ~1.0 | the right metric for thin structures; use it alongside IoU |
| **tolerance** | how many px of slack is allowed before a pixel counts as wrong | — | — | worth ~22 F1 points at 2 px in the literature; state it or the number is unreadable |

## 6. What each parameter does, and its sensible range

| parameter | in one sentence | shipped | sensible range | outside that range |
|---|---|---|---|---|
| **mad_k** | how many robust standard deviations below the frame's median a pixel must sit to be called dark | **5.0** | **4 - 6** | F1 on TXM peaks at 5.0 (0.3750) and falls away either side; by 1.0 lift is 1.69 and by **0.5 it is 1.09 — identical to marking everything** |
| **absolute_dark_thresh** | the grey level below which a pixel counts as crack whatever its surroundings | **10** | 10 - 20 | supplies half of all recall; 20 gains frame recall but costs tile precision and TXM F1, so it is exposed and left at 10 |
| **SCALE_LADDER** | the background-blur radii the darkness cut is taken at, unioned — a feature wider than the radius is erased by its own flattening | 5,10,20,40,80,160,320 | use all of them | a single radius sees only one band of crack widths |
| **min_area_px** (clean_mask) | the smallest blob that survives cleaning | 13 | 10 - 20 | accounts for only 1.6% of missed crack, so not worth tuning |
| **feature filter** | the smallest region passed on for measurement | 40 | 40 - 100 | raising it to 100 deletes 1.31% of real crack for no measurable gain |
| **region classifier** | a model that accepted or rejected each candidate region | **off** | off | switching it on costs recall on every specimen tested and zeroes three of them |

### The one trap worth repeating

A higher recall is not a better detector. On TXM the loosest setting reaches recall 0.9819
and scores F1 0.1620; the shipped setting reaches recall 0.6707 and scores F1 0.3750. The
loose arm's precision, 0.0883, is the same number a plain Otsu threshold gets and is 1.09x
a coin flip. **Read recall and precision together, and read precision against its floor.**
