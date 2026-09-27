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

**8. R_L = true length / projected length on a DECLARED axis** — *common; replaces tortuosity.*
Quantitative fractography's roughness parameter (Underwood & Banerji, *Metall. Mater. Trans. A*, doi:10.1007/BF02698249 / BF02656538); fatigue usage projects the main crack on the specimen's transverse direction (Ma et al., *Materials* 8:11, 2015, doi:10.3390/ma8115388). Defined for **any** profile — no 2-endpoint gate. Per segment, and per region on its longest skeleton path. The axis must be a stated input (default: image x; the user must be able to set it per arm). *Naive failure:* the current path÷chord-between-2-endpoints definition projects on the crack's own chord, not a fixed specimen axis, and its gate throws away exactly the branched cracks that hold 97.4% of the area here. R_L ≥ 1 by construction — keep a hard assert; this project has already shipped impossible sub-1 tortuosities.

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
| `Tortuosity`, `tortuosity_median`, `tortuosity_n_defined` | **Drop.** Replaced by R_L (#8) | Describes 2.6% of gated crack area and 0.0% of TXM. Also the wrong definition. |
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

- Per-crack table (ID, area, length, mean width, R_L, censored) — 6 columns, was 11
- Section size distribution, relabelled
- Junction density, triple/quad split, characteristic length
- S_V with its isotropy assumption printed next to it
- Mean/max width with the `<10 px, below validated envelope` flag
- Censoring: `72.3% of crack area touches a frame edge` and the with/without length statistics
- Cleaning toggles (§3 items 4–6, 9), each with its cost line, all off

**Words to delete now:** the `?` hint tooltips on Arm, Orientation, Size distribution, Mask and Cracks currently carry 60–90 words of rationale each. Move them to a single `README`-linked "How these numbers are defined" page and leave one sentence per card. Tooltip text also is not read text — measure the page with `innerText`, not `textContent`, when checking this.

**One-file map of the work:** `analysis/probes.py` (new, scanlines → items 2/4/6/10) · `analysis/segments.py` (new, skeleton→segments → items 7/8/9) · `measure.py` (frame summary rewrite, drops) · `batch.py` (specimen CI, physical area roll-up) · `app.js` `FCOLS`/`CCOLS` (column cuts) · `index.html` (specimen card + details disclosure).