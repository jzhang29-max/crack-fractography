# Crack metrics: what to add, what to cut, and the honest novelty answer

Grounded on the current code (`/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/measure.py`, `batch.py`, `app/static/app.js`) and the 357 frames / 60,893 regions already in `analysis/out/`.

Four numbers from the existing dataset set the agenda:

| measured now | sem/gated | txm |
|---|---|---|
| regions with a defined tortuosity | 43.7% | **0 of 285** |
| **crack AREA** those regions hold | **2.6%** | **0.0%** |
| crack area in border-touching regions | 72.3% | 74.0% |
| regions with mean width < 10 px (DiameterJ's validated floor) | 84.9% | 44.2% |

Tortuosity is a headline column describing 2.6% of the object. Border regions hold three quarters of it. Those two facts drive most of what follows.

---

## 1. ADD THESE METRICS

One new primitive unlocks items 2, 4, 5, 6 and 9: **a scanline sampler**. Lay parallel test lines at angle θ (18 angles, 10° steps; spacing ~5 px), walk each line over the mask, record 0→1 transitions (intercept count) and in-crack run lengths. ~60 lines of numpy in a new `analysis/probes.py`. Everything below is a different reduction of the same transition table.

Units policy stays as it is: pixel form always, physical form only where `nm_per_px` is known (80/142 SEM, 71/71 TXM).

**1. Sampling header: fields, total physical area analysed, specimens** — *ubiquitous; every standard specifies how much before what.*
Per specimen: n_frames, Σ physical area (mm²), n frames with scale, magnification range. ISO 643:2003 §7.2.1 requires ≥50 intercepts/field, ≥5 fields, ≥250 total; ASTM E2283 fixes a control area A₀ = 150 mm². *Naive failure:* reporting megapixels. Mpx is not area, and this corpus spans a 249× magnification range, so pooling frames of unequal physical area is the error the standards exist to prevent. Cheapest item on the list and it gates every other physical number.

**2. P10 — line-intercept crack count, cracks/mm, directional** — *ubiquitous; the single highest-value addition, and the app does not compute it at all.*
P10(θ) = intercepts per unit test-line length. Report the full θ-curve plus **min, max, mean**. This is the form in ASTM B456-17 ("more than 30 cracks/mm … in any direction" for microcracked chromium — read from an unofficial hosted copy, not an ASTM-issued PDF), in TBC segmentation crack density (2.38–4.76 cracks/mm), and in heat-checking density (mm⁻¹; Le Roux et al., *Micron* 2013, PMID 23036369). *Naive failure:* reporting one isotropic mean. "In any direction" is a **minimum over directions** — an average and a single-axis count both pass specimens B456 fails. P10 cannot be recovered from P21 without the orientation distribution.

**3. TCL and MCL — total and maximum crack length, µm** — *ubiquitous in weldability/hot-cracking (Varestraint: TCL, MCL, TNC).*
TCL you already have in px; convert. **MCL is the longest tip-to-tip geodesic on one region's skeleton** — over all pairs of skeleton tips, the shortest path between them, maximised (`analysis/geodesic.py`). *Naive failure, and this app shipped it:* **MCL is not `max(SkeletonLength_px)`.** That length is summed over the skeleton's adjacency *edges*, not along one ordered path — the vendored `skeleton_path_length` docstring says so — so for a branched region it is the **total centreline of the whole network**, every arm and spur added together. Taking its max and labelling it "Longest crack (MCL)" invites comparison with a Varestraint MCL, which is one crack. Measured over the 143 scaled frames before the fix: the region that set it had a median **594 branch points** (96% had ≥10), its skeleton length was a median **5.2×** its own ellipse major axis, and the value exceeded the short side of the field on **89 of 143** frames — **4893.9 µm** of "longest crack" inside a **107.9 µm** field at worst. Both quantities now ship, each under its own name: `mcl_um` (one crack) and `largest_network_centreline_um` (the network). The tip-to-tip measure equals the region's whole centreline *exactly* when the skeleton is unbranched, so the two columns separate only where topology is the reason they should. Spur pruning (§3.5) is still not applied: spurs inflate the network total, and they inflate MCL only when the longest tip-to-tip route ends on one.
**The measure is owned, and is not claimed here.** "Largest shortest path" per skeleton is a shipped feature of Fiji **AnalyzeSkeleton** (contributed by Huub Hovens; published as Polder, Hovens & Zweers, *Measuring shoot length of submerged aquatic plants using graph analysis*, ImageJ User and Developer Conference 2010) — the same plugin already named in §"Refuted as a measurement contribution" for endpoint/slab/junction classification. On the morphology side it is the **geodesic diameter** (Lantuéjoul & Beucher, *On the use of the geodesic metric in image analysis*, J. Microscopy 121:39–49, 1981). What is fixed here is a wrong label on this app's own column, not a new metric.

**4. P21 (mm/mm²) and P20 (count/mm²), labelled with their Pij subscripts** — *common; and the labelling is not optional.*
Dershowitz & Herda (1992), verified in Niven & Deutsch, CCG Annual Report 12, Paper 103 (2010): P10, P20, P21, P30, P32, P33 are six incompatible quantities, and conversion needs a stochastic-geometry model, not a unit change. Definitions in use: L/A mm/mm² and n/A pieces/mm² (Liu et al., *Materials* 18(13):3102, 2025). Two fixes: **(a)** replace `crack_density_px_per_Mpx` with mm/mm², and cross-check it against the Buffon estimator L_A = (π/2)·P̄_L from item 2 — the two disagreeing *is* your skeletonisation-error readout, free. **(b)** P20 needs the ISO 643 planimetric edge rule n = n_interior + n_edge/2; the app currently applies no edge correction to its count, only a flag. *Naive failure:* quoting a bare "crack density."

**5. Area fraction with a 95% CI from between-field variance** — *ubiquitous as practice (ASTM E562-19e1: the CI computed from field-to-field variance is the product).*
You already have ≥3 frames for most specimen-arms and `estimable_dispersion` in `batch.py`. Compute the CI there. *Naive failure:* `area_fraction` to six decimals with no uncertainty. Also: one chromium study reported 9.25%, 46.07% and 50.89% cracked area on the *same images* from three segmenters — so pair the CI with the **gated-vs-machine paired ratio you already have on identical frames**. That is your threshold-sensitivity band, at zero cost.

**6. Mean crack spacing and D = 1/spacing** — *common (composites; hard-coating toughness from crack spacing).*
Falls straight out of item 2: mean spacing along θ = 1/P10(θ). Report at the θ minimising spacing. *Naive failure:* computing it as nearest-neighbour centroid distance — that is a nearest-branch distance, a different quantity.

**7. Length-weighted, per-SEGMENT orientation rose** — *common; replaces the current rose outright.*
Split the skeleton at junctions; one angle per segment (endpoint-to-endpoint chord), weight by segment length. Convention from Le Roux et al. (*Micron* 2013): features are measured on crack **branches**. *Naive failure:* all three are in the code today — the angle is the second-moment major axis of a whole connected component (noise for a branched network, arbitrary for a 4-way junction), the weight is **area** (so it is a width-weighted rose: one short wide crack outvotes a long thin one), and there is no Terzaghi 1/|cos θ| weighting, which you will need the moment item 2's directional sampling lands.

**8. R_L = true length / projected length on a DECLARED axis** — *common in the literature; **NOT SHIPPED**, see the note at the end of this item.*
Quantitative fractography's roughness parameter (Underwood & Banerji, *Metall. Mater. Trans. A*, doi:10.1007/BF02698249 / BF02656538); fatigue usage projects the main crack on the specimen's transverse direction (Ma et al., *Materials* 8:11, 2015, doi:10.3390/ma8115388). Defined for **any** profile — no 2-endpoint gate. Per segment, and per region on its longest skeleton path. The axis must be a stated input (default: image x; the user must be able to set it per arm). *Naive failure:* the current path÷chord-between-2-endpoints definition projects on the crack's own chord, not a fixed specimen axis, and its gate throws away exactly the branched cracks that hold 97.4% of the area here. R_L ≥ 1 by construction — keep a hard assert; this project has already shipped impossible sub-1 tortuosities.

**Not shipped, on purpose (2026-09-28).** This was built, shipped, and then removed. The axis input was never wired to a control, so `R_L_axis_deg` was `0.0` on all 356 frames. Against a fixed image axis the projection is `chord·cos θ`, so the column reduces to `(length/chord)·sec θ` — an identity, not a measurement — and its corpus median *and* upper quartile were both exactly 1.4142, where sec(45°) is at once a pixel-lattice diagonal, a straight 45° crack and the isotropic expectation. It also ran −0.78/−0.83/−0.45 against `rose_R`, which answers the same question *with* a per-frame permutation null. The app now states the refusal (`conclusions.REFUSALS`) instead of printing the number. A declared axis would go on the rose, not here.

**9. Junction density per mm², split triple / quadruple, plus characteristic length** — *common; replaces the raw count.*
CFL = total centreline length / junctions (DiameterJ); triple vs quadruple classification is AnalyzeSkeleton's, 2008. *Naive failure:* `branch_points_total` as a raw per-frame count is a function of field size. And skeletonisation manufactures junctions: a true 4-way crossing is usually two adjacent 3-way nodes.

**10. (Advanced / opt-in) S_V = 2·P_L, crack surface per unit volume** — *common as the stereologically correct target for "how much crack."*
Same transition table. **State the assumption on screen:** 2·P_L estimates S_V only for isotropic-uniform-random line probes; from one fixed section plane with in-plane isotropic lines it holds only if the crack-surface orientation distribution is isotropic w.r.t. that plane. Worth having because area fraction is V_V, and a crack is a *surface* — its volume fraction measures the opening plus the segmentation's dilation, not the amount of cracking.

### OUT OF SCOPE — say so in the UI, do not approximate

| Not computable | Why |
|---|---|
| **Crack depth** (mean/max vs cycles) | Needs a cross-section geometry and a defined free surface. The app has no notion of either. This is the first number a thermal-fatigue reader looks for; better absent than faked from trace length. |
| **Aspect ratio a/c** (BS 7910 / API 579) | a/c is depth ÷ half surface length. A 2D inertia-ellipse ratio is an unrelated number a materials reader will misread. If you ever ship a 2D ratio, do not call it aspect ratio. |
| **Elastic crack density ρ = (N/V)⟨a³⟩** (Budiansky–O'Connell) | 3D and dimensionless. Recovering it from traces is a live named literature (Kachanov & Sevostianov; Pronina & Kachanov, *Mech. Mater.*, in press) — do not re-derive. |
| **Crack size `a` / da/dN** (ASTM E647) | Time series + specimen datum + W-referenced resolution. Note: I could not access E647's text (403s) and could not verify any crack-path-deviation angle limit — do not quote one. |
| **Saltykov unfolding to a 3D size distribution** | Assumes spheres; fails completely for planar flaws. Consequence for today: **label the existing size histogram a section distribution.** |
| **Dimple size, striation spacing, fracture-mode area fractions** | Grayscale fractographs of a fracture *surface* — no trace to segment. If the corpus mixes fractographs, polished sections and plan views, those are three disjoint metric sets; pooling them is the same error class as pooling across 249× magnification. |
| **Fractal dimension** | Computable, deliberately not added: over <2 decades of box size it returns 1–2 for any non-empty mask, so it cannot fail and proves nothing. If ever added, ship the fitted scale range in µm and the R². |
| **Extreme-value max feature (ASTM E2283)** | Needs a fixed reference area A₀. Revisit only once item 1 exists and frames can be grouped at constant physical area. `largest_share_of_area` is a within-frame concentration measure and is not this. |

---

## 2. DROP OR DEMOTE

| Now | Action | Why |
|---|---|---|
| `tortuosity_median`, `tortuosity_n_defined` | **Dropped** from the frame summary. R_L replaced them and was itself removed (#8); nothing replaces either. | Described 2.6% of gated crack area and 0.0% of TXM. Also the wrong definition. |
| `Tortuosity` (per-crack column) | **Kept.** Still ships on all 60,893 crack rows and in every crack-level CSV. | Per crack it is what the column says it is. Separate known defect: 31,838 of those values are the empty string rather than a number. |
| Area-weighted per-component rose (`_rose`) | **Replace** with #7 | Wrong weight, wrong unit of analysis. |
| `crack_density_px_per_Mpx` | **Demote to CSV**, headline becomes P21 mm/mm² | Magnification-dependent; comparable to nothing published. |
| `branch_points_total` | **Replace** with junction density /mm² + triple/quad | Field-size dependent. |
| `MaxWidth_px` / `max_width_um` | **Demote to detail + CSV** | Noisiest number on a 1–3 px crack. |
| `MeanWidth_px` / `mean_width_um` | **Keep, gate it** | This is DiameterJ's D_SP = Area/Length, validated only for features ≥10 px across — 84.9% of gated regions fail that. Show a "below validated width envelope" flag on the frame, not a bare median. |
| `top1pct_share_of_area` | **Drop from screen**, keep in CSV | `largest_share_of_area` earned its place (305 components, largest held 97.45%); the top-1% variant is a second telling of the same story. |
| Per-crack `Orientation_deg` column | **Drop** | Component second moment; noise once #7 exists. |
| `n_regions_total` / `n_cracks_measured` / `speck_count` as three columns | **Collapse** to one cell: `135 measured (+36,087 specks ≤25 px)` | Same information, one column. |
| Size-distribution chart | **Demote to detail**, relabel "section size distribution" | Correct but not what a referee asks for first. |
| Frames table, 11 columns | **Cut to 6** (see §5) | It is 1109 px wide against a 512 px card. |

---

## 3. CLEANING, IN ORDER

Framing source: Dow et al., *Automation in Construction* 151:104867 (2023) measured this exact tradeoff — uncleaned input recall 90%, best-recall filter 85%, best-F1 setting 77%, i.e. the best method discarded ~14% of recoverable true crack pixels to lift precision 22%→91%; and their constants (T_area 6 px, T_length 55 px, T_radius 8 px) "are likely only suitable for cracks of widths that match the dataset." **Cleaning parameters do not transfer between corpora.** This project has already had two artefact "fixes" that were deleters, one removing 19% of all human labels. Default is: record, don't remove.

| # | Step | Removes | Risks destroying | Default? |
|---|---|---|---|---|
| 1 | **Ingest assertion** — mask is 2-valued; crack fraction ≤50% (polarity check); log 8- vs 4-connectivity into every record | nothing | nothing | **Default.** Connectivity is currently a silent `connectivity=2` that rewrites every count statistic and is never reported. |
| 2 | **Record the physical frame** — nm/px, mm² analysed, detection limit in µm (the smallest expressible crack at this frame's scale) | nothing | nothing | **Default.** ANSI/NACE TM0284-2016 declares its limit by magnification instead of filtering; copy that. |
| 3 | **Speck exclusion (existing, keep)** — excluded from shape stats, retained in area and count, `speck_count` reported | nothing from area | nothing | **Default, but make the threshold physical.** A fixed 25 px is a physical threshold varying ~6×10⁴ across a 249× magnification range. Set it in µm² with the px equivalent logged; fall back to 25 px where scale is unknown. |
| 4 | **Hole filling** | enclosed background islands | **uncracked ligaments / crack bridges** — Babout, Janaszewski, Marrow & Withers, *Scripta Mater.* 65:131-134 (2011) built an algorithm to *find* exactly these as a toughening mechanism | **Opt-in, never default.** If on, report filled area as its own number. |
| 5 | **Skeleton spur pruning** | thinning spurs from width variation and blobs | short real branches; junction classes | **Opt-in.** Even when on, apply only to segment-level stats (#7, #8) — never to TCL. Report pruned length as a fraction of total. |
| 6 | **Small-component removal by area/length/elongation** | debris | real short cracks, and disproportionately on the AM subset where cracks are near-intensity-invisible | **Opt-in, off.** This is the Dow et al. tradeoff verbatim; if shipped, show the recall cost estimate beside the toggle. |
| 7 | **Gap bridging** | segmentation gaps splitting one crack into two | manufactures crack where none was imaged; ASTM E1382-97(2015) §6.4 warns boundary-completion "may create false boundaries" | **Never as a pixel operation.** If merging is wanted, do it in bookkeeping only — TM0284 §9.4 merges traces <0.5 mm apart for the purpose of *summing lengths*, adding no pixels. Changes counts, never area or length. |
| 8 | **Border handling — per metric, never global** | — | 72–74% of crack area is in border-touching regions here; a global delete is catastrophic | **Default, differentiated:** area fraction = no correction (Delesse, it's a ratio); counts = ISO 643 n_interior + n_edge/2; length statistics = keep, flag, and report MCL/percentiles *both* with and without censored regions (keeping biases down, dropping biases up — long cracks touch frames more). Note `edge_censored_share` itself is owned: rock-mechanics window sampling (Pahl 1981; Laslett 1982; Kulatilake & Wu 1984) estimates *through* censoring and names four biases. |
| 9 | **Operator edit** | whatever the operator sees is wrong | operator bias — so it must be logged | **Opt-in, but build the hook.** E1382 §6.3 requires each field be examinable and "manually edited, if necessary," and §6 is a 12-item interference list. An automatic segment-then-skeletonise pipeline with no interference list and no edit step is the thing E1382 spends a page warning about. |

---

## 4. NOVELTY VERDICT

**Refuted as a measurement contribution — plainly, and every item.** Per-region area, skeleton length, area÷length mean width, distance-transform max width, branch-point count and an orientation index from a binary mask are DiameterJ (Hotaling, Bharti, Kriel & Simon, *Biomaterials* 61:327-338, 2015), a 2015 ImageJ plugin with an NIST validation behind it; its intersection density per 10⁴ px is literally the same construct as your px/Mpx, and it *also* already published the segmentation-sensitivity result you would want to claim (diameter CV ~1% across four segmenters, other network metrics 8–27%). Endpoint/slab/junction classification, triple and quadruple points and mean/max branch length are Fiji AnalyzeSkeleton, shipped since ~2008–2010 — the 2-endpoint/0-branch tortuosity gate is a narrower re-implementation of its voxel classification. The density taxonomy is Dershowitz & Herda (1992). R_L is Underwood & Banerji. The counting, sampling and confidence-interval layer is ISO 643, ASTM E562, E1382, E1245, E2283. The censoring machinery is rock-mechanics window sampling. The cleaning tradeoff is measured in Dow et al. (2023). The 2D-traces→3D-crack-density problem is an active named literature (Kachanov & Sevostianov). Even the "Kulpa-corrected" length is a misattribution: 0.948 is Kulpa's *closed-boundary perimeter* estimator; the matched estimator for an open digital curve is Vossepoel–Smeulders with corner counts, and either way the factor corrects metrication error only — for a 1–3 px crack, skeletonisation error dominates and no scalar fixes it. The **one** space that survived the search is procedural, not metric: no ASTM or ISO test method exists for quantifying cracks in micrographs by image analysis, and the coatings literature says so directly. A documented, sampled, interference-listed, Pij-labelled, CI-bearing procedure with quantified threshold sensitivity would be a real (modest, standards-shaped) contribution — **but treat even that as unclaimed only after someone checks the ASTM E04/E08 and IIW work-item lists, which the research explicitly did not do; a live work item kills it.** Ship this as *fitness for purpose*, not novelty: an app that reports what materials papers report, in units they can compare, with the uncertainty attached. That is worth building regardless of who owns the ideas.

---

## 5. UI

Rule: the primary screen answers "how much cracking, measured over how much material, how sure are you." Everything else is a detail view. Target: **6 table columns, 3 cards, no paragraph longer than one line.**

**Primary screen**

1. **Header (one line):** `sem/gated · 14 specimens · 142 fields · 38.6 mm² analysed · 80/142 scaled` — arm selector, specimen selector, CSV, upload. Physical area analysed replaces the frame/crack totals.
2. **Specimen card (new, and it goes first — the specimen is the inferential unit, frames within one are not independent):**
   - Crack area fraction **2.83% (95% CI 2.1–3.6, 9 fields)**
   - P10 **min 12 /mm** (at 80°) · mean 19 /mm
   - P21 **0.42 mm/mm²** · P20 **86 /mm²**
   - MCL **410 µm** (longest single crack, tip to tip) · TCL **9.1 mm**
   - Gated vs machine on the same frames: **×1.09** (segmentation sensitivity)
   Six rows, no prose. Grey out and label any row whose specimen has no scale.
3. **Frames table — 6 columns:** Frame · Cracks (+specks) · Area frac · Largest share · P21 mm/mm² · P10 min /mm. Sortable, click-to-select, `no scale` chip on the frame cell. Everything dropped here stays in the CSV.
4. **Mask + rose, side by side.** Rose is now length-weighted per segment; caption is four words: `Length-weighted, 15° bins.`

**Behind "Details" (one disclosure on the frame card, closed by default)**

- Per-crack table (ID, area, length, mean width, censored) — no R_L: it was never a per-crack column, and it is no longer a frame one either
- Section size distribution, relabelled
- Junction density, triple/quad split, characteristic length
- S_V with its isotropy assumption printed next to it
- Mean/max width with the `<10 px, below validated envelope` flag
- Censoring: `72.3% of crack area touches a frame edge` and the with/without length statistics
- Cleaning toggles (§3 items 4–6, 9), each with its cost line, all off

**Words to delete now:** the `?` hint tooltips on Arm, Orientation, Size distribution, Mask and Cracks currently carry 60–90 words of rationale each. Move them to a single `README`-linked "How these numbers are defined" page and leave one sentence per card. Tooltip text also is not read text — measure the page with `innerText`, not `textContent`, when checking this.

**One-file map of the work:** `analysis/probes.py` (new, scanlines → items 2/4/6/10) · `analysis/segments.py` (new, skeleton→segments → items 7/8/9) · `measure.py` (frame summary rewrite, drops) · `batch.py` (specimen CI, physical area roll-up) · `app.js` `FCOLS`/`CCOLS` (column cuts) · `index.html` (specimen card + details disclosure).
---

## Round 6: identification **and** analysis in one tool — asked directly, 2026-09-30

The question put to the search was the owner's own: *is this unique, and are there papers
or tools that do both identification and analysis?* Five literature neighbourhoods, one
searcher each, and every claimed gap handed to a separate agent whose job was to find what
already fills it.

**57 works do both. 20 of 20 gap claims came back owned. None survived.** That takes this
project's running tally to **43 of 43 novelty framings refuted**.

### The strongest overlap, and it was missing from this file

**MIPAR** — Sosa, Huber, Welk & Fraser, *Integrating Materials and Manufacturing
Innovation* 3:10 (2014); product at mipar.us. A commercial cross-platform standalone
desktop application, no programming required, sold to materials scientists. It ships
recipe-based *and* deep-learning segmentation followed by a measurement library (area, size
distribution, roundness, fibre thickness, porosity, orientation, aspect ratio, grain size),
batch processing over many images, integrated statistics and reports, and claims ASTM
conformance with E112 named.

Its own product page advertises **"quantify additive manufacturing crack density, size
distribution, localized density"**.

That is this app's pitch, in this app's material system, already shipping commercially. It
is the single most damaging prior art found in six rounds and it was absent from this
record until now.

### Others doing identification + measurement in one end-user tool

| Work | Form | What it already covers |
|---|---|---|
| **CIAS / PCAS** — Liu, Tang, Shi & Suo, *Computers & Geosciences* 57:77–80 (2013); PCAS from Liu et al. (2011) | Free Windows desktop GUI, no runtime | Segmentation → crack identification → measurement: node count, crack count, per-segment length, width, direction, crack area, area ratio, fractal dimension. Widely used **on SEM micrographs**. Ships crack-gap fusion as a default — the pixel operation this app deliberately refuses |
| **Arena, Delle Piane & Sarout**, *Computers & Geosciences* 66:106–120 (2014) | MATLAB research code | Closest published method analogue: automatic separation of individual cracks from a connected mask, then per-crack width, length, area, **aspect ratio** and orientation, from SEM micrographs |
| **Patzelt & Erfurt**, *Journal of Microscopy* 286:154–159 (2022) | Fiji + Python scripts | Skeleton length, area, and mean/max/min width from the distance transform **taken on the skeleton** — the same implementation detail this app uses — plus a width *distribution*. Already publishes the honest-limits result: automatic crack length **differs** from manual |
| **FracPaQ** — Healy, Rizzo, Cornwell et al. | MATLAB toolbox with GUI, open source | Pij densities and orientation statistics from traces |
| **DiameterJ** — Hotaling, Bharti, Kriel & Simon, *Biomaterials* 61:327–338 (2015) | Fiji plugin, GUI, batch | **This file mis-described it.** It was recorded as owning the measurement set only. It also ships 16 segmentation algorithms (`Segment SRM` / `Segment Mixed`), so it does identification **and** measurement in one GUI — it is not a measurement-only plugin |
| **ilastik**, **CellProfiler**, **QuPath**, **MorphoLibJ**, **AngioTool**, **Ridge Detection** (Steger 1998) | Free desktop apps / Fiji plugins | Pixel classification or ridge detection followed by object measurement, skeleton length, junctions, orientation |
| **ZEN core + Intellesis**, **Clemex Vision**, **Leica LAS X Phase/Steel Expert**, **Buehler OmniMet**, **Olympus/Evident Stream**, **Dragonfly**, **Avizo/Amira** | Commercial desktop, microscope-bundled | ML segmentation feeding standards modules. **Stream, Clemex, Buehler, Claravision and Leica each ship an ASTM E562 routine** — so the E562 statistic is also not a gap |
| **CrackDect** — Drvoderic et al., *SoftwareX* 16:100832 (2021) · **CrackPy** (DLR) · **CrackIT** — Oliveira & Correia, ICIP 2014 | Python / MATLAB | Crack detection plus density; CrackIT adds crack-type classification **and** a built-in detector-evaluation module |

### On "a tool that refuses questions and states its own limits"

Not a gap either, and the clearest refutation of the framing I had most hope for. It is an
existing category with at least six independent names in six fields — **HistoQC**
(Janowczyk et al. 2019) for slide QC, **CellProfiler's FlagImage**, **statcheck** (Nuijten
& Epskamp) for reported statistics, **MIL-HDBK-1823A** for NDE probability-of-detection,
and the reporting standards STARD / MIQE / REFLECT. At least three of those are packaged
end-user tools that combine identification, measurement and refusal in one application.

### What actually survives

Nothing as a capability. Every metric, every statistic, and the refusal layer are each
owned by named shipping software. What survives is the **integration** claim the README
already makes conditionally: the search did not find one tool applying the *metallographic
sampling discipline* (E562 between-field interval, % relative accuracy, specimen as the
inferential unit, one magnification per determination, arms never pooled) to a *crack
network* measured from a micrograph, with each refusal stated on screen. That is a claim
about an arrangement, not about a method, and it is worth much less than a capability
claim. It should be stated that way or not at all.

---

## Round 7: five sharpened claims, attacked on priority AND on method — 2026-10-01

Round 6 killed the capability framing ("a tool that does both identification and analysis").
Round 7 asked the next question: take the assets that are actually unusual about this corpus
and this code, state the sharpest claim each could support, and try to kill *that*. Five
assets, one proposer each, then two independent attackers per claim — one searching for prior
art, one attacking the method and the numbers.

**5 of 5 died. Running tally: 48 of 48 novelty framings refuted.**

What makes this round different from the six before it: three of the five were killed by
**measurements taken on this project's own files**, not by a citation. Those are defects, and
they are listed as such below.

### The prior art Round 7 added

| Work | What it owns |
|---|---|
| **Schmies, Hemmleb & Bettge**, *Engineering Failure Analysis* **156**:107814 (2024; online Nov 2023) | SE + BSE + shape-from-shading topography on the **same annotated fatigue-fracture fields**, with an input-channel ablation concluding that the detection channel determines crack-feature segmentation. Same-field, different-channel, on cracks — so "resolution is excluded by construction" is not a new exclusion. This is the citation that killed framing 8 in an earlier round; the detector claim is that framing with a metric-family wrapper |
| **ISO 5725-1 / -2** (2019) · **ASTM E2782** (Measurement Systems Analysis) · **AIAG MSA** 4th ed. | A change of EQUIPMENT is by definition a *reproducibility* factor, and reporting s_r against s_R with intervals is the standard's own output. "A between-field interval cannot absorb an instrument change" IS the repeatability/reproducibility distinction. The acceptance criterion exists too: %GRR bands and ndc, where "measurement-system variation exceeds part-to-part variation" is the textbook unacceptable-gauge case |
| **Lu et al.**, "Quantifying segmentation sensitivity in OCTA: device-specific profiles across three commercial platforms", *PLOS One*, doi:10.1371/journal.pone.0343605 | 32 eyes, three commercial devices, one open analysis pipeline, and **per-device sensitivity coefficients for vessel area density, total vessel length, vessel length density, branching measures and FAZ area** — i.e. a device-indexed sensitivity profile for exactly the network-extent metric family this project reports. The broader OCTA inter-device literature already concludes these metrics are "not interchangeable" across devices |
| **Salvato et al.**, "Impact of SEM acquisition parameters on the porosity analysis of irradiated U-Mo fuel", *Nuclear Materials and Energy* (2023), doi:10.1016/j.nme.2023.101494 | The closest materials prior art: varying SEM voltage, beam current and magnification one at a time on BSE micrographs moves **total porosity by up to 30%**, average diameter 10% and pore density 20% over 5–30 kV, with Monte Carlo probing-depth simulations for the mechanism. A segmentation-derived extent metric moving with acquisition settings is a known, published result in this exact measurement class |
| **Paumgartner, Losa & Weibel**, *Journal of Microscopy* (1981) | The classical ordering this project thought it was contradicting: volume fraction robust to resolution, surface density fragile. Also **Scrivener (2004)** on back-scattered imaging of cementitious microstructures, and the Monte Carlo work on the BSE signal across pore/solid boundaries, for why segmented extent is detector-dependent |
| **Dahari et al.**, "Prediction of Microstructural Representativity From A Single Image", *Advanced Science* (2025), doi:10.1002/advs.202414149, arXiv:2410.19568, code at `tldr-group/ImageRep`, app at imagerep.io | Estimates a confidence interval on a **phase fraction from one micrograph**, analytically from the two-point correlation function. This project asserted that an interval on a one-patch raster has no remedy short of imaging more patches. Scope matters in both directions: ImageRep bounds the *within-image* representativity of a phase fraction and does **not** estimate between-patch variance over a specimen surface — so it does not answer this corpus's question, but it does falsify "no remedy exists without more patches" as stated, and it is a tool this app could call |

### The three internal kills — these are defects, not citations

**1. "The detector changes crack LENGTH rather than WIDTH" is an algebraic identity, not a
finding.** The global calibre estimator *is* `crack_area_px / total_skeleton_length_px`, so
`area_ratio == width_ratio × length_ratio` holds to ~1e-16 over the 36 paired fields.
Comparing |log length| against |log width| is therefore variance apportionment of an exact
product. The two other "independent" calibre estimators are the same construct at different
aggregations (per-region A/L — which is DiameterJ's D_SP — and lineal fraction over mean P10).
The one calibre instrument that is *not* amount-over-extent, a distance transform read on the
skeleton, reportedly moves 1.285× with CBS > ETD on 31 of 36 fields, which if it holds makes
the "not width" half **false** rather than unproven. Two further problems with the same claim:
the specimen-level sign test is 4/4 at **p = 0.125**, which is the p floor at n = 4 — the
design cannot produce a smaller p, and the project's own rule is that the specimen is the
inferential unit; and the ratio is a monotone function of how much crack is present
(6.00× / 4.88× / 3.38× / 1.83× by ETD area-fraction stratum), which is the signature of a
detection floor rather than a constant. **Corrected 2026-10-01 — see Round 8 below for what
the statement says now, including the mechanism, which is largely one uncalibrated constant.**

**2. The shipped stage gradient was CBS-only. Fixed, and the finding survived.**
`specimen_stats._one_frame_per_field` kept the alphabetically first frame per physical field,
and the detector token sorts CBS before ETD on every pair here — so eight shipped records
carried a CBS-only rank correlation on the same card as an E562 interval computed from a real
detector mean, under a comment that claimed the values were "collapsed to fields first, like
every other aggregate in this function". Corrected to field means:

| specimen | shipped (CBS) | field mean | CBS only | ETD only | max/min |
|---|---|---|---|---|---|
| MAR_AmbB_AS  | +0.750 p 0.0199 | **+0.867** p 0.0025 | +0.750 p 0.0199 | +0.683 p 0.0424 | 4.9× |
| MAR_AmbB_HIP | +0.867 p 0.0025 | **+0.883** p 0.0016 | +0.867 p 0.0025 | +0.650 p 0.0581 | 18.8× |
| MAR_H_AS     | +0.867 p 0.0025 | **+0.867** p 0.0025 | +0.867 p 0.0025 | +0.883 p 0.0016 | 5.3× |
| MAR_H_HIP    | +0.833 p 0.0053 | **+0.833** p 0.0053 | +0.833 p 0.0053 | +0.883 p 0.0016 | 12.4× |

The gradient is **not** a property of the CBS channel: two channels of one simultaneous scan
over the same physical fields agree in sign on all four specimens. The shipped range was
+0.750..+0.867 and the corrected range is +0.833..+0.883. `stage_gradient_by_detector` now
ships beside it so the detector-sensitivity of the conclusion is on the record rather than in
a comment. What does **not** survive: attribution. Stage position is rank-collinear with
acquisition order (Spearman(StageY, timestamp) −0.650 to −0.950), so surface gradient, session
drift and the operator's choice of raster origin are not separable here, and the card should
not read as a spatial finding.

**3. "More patches would narrow the interval" had no supporting measurement and has been
removed.** `n_patches` is 1 on the eight positioned specimen-arms and None on the other 26,
and never reaches 2 — so between-patch variance has never been observed in this corpus. The
sentence appeared in `analysis/stage.py`, `analysis/conclusions.py` and
`app/static/app.js`; all three now say the remedy is untested here and name the experiment it
asks for. This was an assertion of exactly the class the refusal engine exists to block, in
the file that argues for refusing such assertions.

### Two prose/artifact mismatches, both now corrected in the README

- **The grain-boundary positive control has no artifact.** The z = +0.62 ceiling, the
  z = +2.0..+3.4 real-label range, the 72.8% and the +1.99 dose-response exist only as English
  prose inside a string literal in `analysis/conclusions.py`, and the test that covers it
  greps that prose for the substring. A search of the whole working tree finds no script that
  computes a grain-boundary skeleton, an exclusion-radius sweep, or any z. The result may well
  be right — it is recorded in a session note — but **the repository cannot reproduce it**, so
  it is carried as a recorded prior finding and not as a measured one. Re-deriving it with a
  retained artifact is the open item.
- **"Every refusal stated on screen" was false.** Five value-level suppressions are
  data-evaluated and rendered; the four question-level refusals travel in `/api/readout` and
  are rendered nowhere, because the block that listed them was removed at a user's request.
  The README now describes the two layers separately.

### What Round 7 says about the project

The attack was run to find something *more* unique. It found the opposite, and that is the
useful result: the defensible residue of the detector work is a **magnitude**, not a framing —
"on 36 physical fields of these specimens, through both detectors at 51.883 nm/px with one
segmenter fixed, segmented crack amount and extent both scale ~2.3–2.8× CBS over ETD, so their
quotient is within 8% of unity" — which is a technical note quantifying a qualitative result
Schmies et al. already own. Stated at that size it is honest and still worth recording. Stated
any larger it is refutable in one search.

---

## Round 8: the detector effect has a named cause inside our own pipeline — 2026-10-01

Round 7 killed the *framing* of the detector result ("LENGTH, not width", one multiplier).
Round 8 asks the next question — **where does the 2.8× come from?** — and the answer moves the
result further from a detector finding and closer to a pipeline finding. The statement in
`analysis/conclusions.py` has been re-worded accordingly and demoted from `good` to `bad`.

### What the statement says now

`CBS carries 1.8× to 6.0× ETD's crack centreline, depending how much ETD found.` The range is
the extreme ETD area-fraction strata, not the extreme fields; the direction (CBS longer on
**35 of 36** fields) is what is established; the overall median 2.79× is carried only as the
midpoint of a trend. The between-field "CONTROL" sentence is **gone**, and no width claim is
made in either direction.

### Why the control sentence had to go — its own numbers refuted it

It claimed that between two *different* fields with the *same* detector, an area difference
routes through width instead, citing "only 69 of 144 and 96 of 144". Those two counts sum to
**165 of 288 — a majority**, i.e. length moves more than width between fields too. At the
median, between-field |log length| is 0.427 against |log width| 0.369; the ETD half alone is
96/144 with 0.713 against 0.352. The detector swap is a more extreme version of the same
pattern, not a different routing. A minority was read off a majority.

### No instrument here can referee width — including the two that looked like they could

`area/length` width is `log(area) − log(length)` by construction (verified: maximum deviation
3.33e-16, i.e. float64 zero), so it is pinned near 1 whenever area and length move together —
here 2.72× and 2.79×. `mean_width_px_median` cannot referee it either: it is the **median over
regions** of per-region `Area_px/SkeletonLength_px`, so still amount-over-extent, just at
region level. It is **not** the global `crack_area_px/total_skeleton_length_px` — the two agree
within 0.01 px on only **17 of 348** frames, worst case 138.6 px against 6.7 px. An earlier
draft of this section said they were the same number; that was a verification of the per-region
field attached in prose to the frame-level one.

That leaves the two per-region instruments in `cracks.json` that are not amount-over-extent.
**They were briefly offered here as evidence that width moves the OTHER way, and that is now
withdrawn too.** Both are size proxies:

| | `MaxWidth_px` (distance transform) | `EllipseMinorAxis_px` (fitted ellipse) |
|---|---|---|
| naive: per-field area-weighted, median over pairs | **1.26×** (26/36) | **1.67×** (29/36) |
| log–log slope on region area | **0.426** (r 0.952) — it is a maximum | **0.561** (r 0.950) — a second moment |
| size-matched: 20 equal-count area bins | **0.97×** — unity | **1.02×** — unity |
| unweighted median over regions | 1.02× | 1.08× |
| pooled across pairs | 0.84× — *inverts* | 0.96× — *inverts* |
| size-only null (area + ETD's size distribution, nothing about width) | **1.53× predicted vs 1.26× observed — overshoots** | 1.54× vs 1.67× |

Both instruments are strongly monotone in region area, so area-weighting them on a detector
that marks **more and bigger** regions manufactures a ratio out of size. Size-matched strata
put both at unity. A null that knows only each region's area and ETD's own size–calibre
relation *overshoots* the distance-transform result. The unweighted median over regions is
already at unity, so the area weighting was doing all the work — and an instrument whose answer
moves 0.84× → 1.67× with the weighting choice is not measuring width. What the 1.26×/1.67×
actually reports is the 2.72× area and 2.79× length already on the record.

So **no instrument in this dataset supports a width change in either direction**, and the card
asserts none. `conclusions.DETECTOR_CALIBRE_RATIOS` now stores the naive **and** the
size-matched pair, and `tests/test_conclusions.py` asserts the *confound*: naive away from
unity, size-matched at unity, and each instrument still size-monotone. The previous version of
that test asserted the naive ratios **exceed 1**, which would have pinned the withdrawn claim
in place — a guard on a conclusion rather than on the thing that makes it doubtful.

**Discrepancies on the record.** The figures that prompted this round were 1.285× with CBS>ETD
on 31 of 36 and 1.620×; recomputed as a per-field area-weighted mean they are 1.26×/26-of-36
(Wilcoxon p = 1.6e-3) and 1.67×/29-of-36 (p = 1.9e-4). The exact original recipe was not
recoverable, and every weighting gives the same direction while the decimals move — which was
itself the clue. Also **not** reproduced: the claim that the distance-transform calibre moves
nearly as much under the detector swap as between fields (reported 0.348 vs 0.414, ratio 1.19).
That ratio is **unstable against choices nobody stated** — 0.40, 0.53, 1.02 or 1.43 depending
on median-vs-mean and whether censored regions are included — so it is quoted nowhere, and the
argument above rests on the construction identity and the size confound, neither of which
depends on that choice.

### The acquisition is clean — this is a detection-mode contrast, not a settings bundle

An earlier draft of this section implied the two channels were confounded by acquisition
settings. **They are not.** Across all 40 pairs carrying FEI metadata (the block beginning
`[User]` in the TIFFs under `sem-crack-detector/original/`; all 72 frames of the 36 analysed
pairs carry it, though only 80 of the 114 `MAR_*` files do), these are **bit-identical within
every pair**: `EScan.Dwell`, `EBeam.HV`, `EBeam.BeamCurrent`, `EBeam.WD`, stigmator and source
tilt, `EScan.HorFieldsize`, `Scan.PixelWidth`, every stage axis (`StageX/Y/Z/R/T`) **and the
acquisition timestamp** (`User.Date`, `User.Time`). The only keys that ever differ are the
detector name and mode, each detector's own contrast/brightness/gain block, the display
zoom-pan, and `EBeam.EmissionCurrent` on 1 of 40 pairs.

Identical timestamps confirm these are two channels of **one simultaneous scan**, which is as
clean as a paired contrast gets. And a detector's own gain is part of what using that detector
means, so the gain difference is not a confound to apologise for:

| | CBS | ETD |
|---|---|---|
| `ContrastDB` | **45.28 on all 36** — one setting, never touched | median **32.32**, range 27.12–37.50 |
| `Setting` | `A+B+C+D` — four summed quadrants | `250` — one element |
| 16-bit frame median | 44.9k, pinned (44.5k–45.5k) | 25.8k, scattered (19.3k–38.2k) |

CBS `ContrastDB` exceeds ETD's on **36 of 36** pairs. One asymmetry does survive as a caveat:
the CBS channel ran at a single fixed gain throughout while the ETD channel was re-adjusted
field to field, so the **ETD arm carries operator-dependent variation the CBS arm does not** —
a second reason the ratio is not a constant, and a within-arm nuisance rather than a
between-arm confound.

### The mechanism: a large share is our own segmenter, but not one constant

`sem-crack-detector/code/detect_cracks.py::segment_dark_regions` thresholds with

```python
thresh = min(otsu_thresh, median - mad_k * mad * 1.4826)   # mad_k = 5.0
relative_mask = smooth < thresh
return relative_mask | (img8 < absolute_dark_thresh)       # absolute_dark_thresh = 10
```

and its **own docstring names "this dataset's ETD captures"** as the low-contrast/unimodal case
the MAD term exists to cap. So the ETD channel is the channel the fallback was written for, and
`mad_k = 5.0` is a hand-set constant never calibrated against the CBS channel it is implicitly
compared with. That much is readable in the source and is not in dispute.

**The size of its contribution is contested, and the figure quoted here has been revised
down.** Re-running the real pipeline (`load_as_uint8` → `find_field_of_view` →
`flatten_background` → `segment_dark_regions`) on 8 full pairs gives a dark-fraction share of
**44–150% of the log area-fraction gap, median ~70%** — not the "66–96%" or the three-pair
`1.85× / 4.97× / 2.49×` an earlier draft carried, neither of which this repository reproduced
independently. Two further corrections to that draft:

- **It is not attributable to `mad_k` alone.** The absolute `img8 < 10` term supplies **13–100%
  of each frame's dark area** and is the sole contributor on at least one pair, so the
  relative/MAD threshold is not the single lever the earlier text implied.
- **Re-tuning `mad_k` on ETD is a calibration to a target, not a fix.** It equalises the area
  number, but **lowers mask agreement with the registered CBS mask on 2 of 3 pairs** —
  equalising a summary statistic moved the masks further apart.

### What this does to the result

The paired design is sound and the direction is real: 36 physical fields, one simultaneous scan
with every beam and stage parameter identical, two detectors, CBS longer on 35 of 36. What is
*not* supported is a single multiplier, any width claim, or a reading of the effect as pure
detector physics — a median ~70% of the gap is reproduced by this repository's own segmentation
before detector response is invoked, which is why the card is a limit rather than a finding.

It is also **not a correction factor.** `mad_k` was re-tuned per pair on three pairs only, it
lowers mask agreement where it was checked, and equalising dark fraction is not evidence that
the equalised answer is right, since nothing here referees which pixels are crack. The open
item is a calibration of both threshold terms against labelled data on both channels, which
would decide whether CBS over-segments, ETD under-segments, or both.
