# crack-fractography

Automatic crack-network measurement over black-and-white crack masks, with an interactive
page to read it. Reads the sibling repos; writes nothing back to them.

    ./run          # builds .venv, measures if needed, serves http://127.0.0.1:8810

## What this measures, and what it cannot

A BW mask records crack **geometry**. Everything here is derived from that: length, width,
tortuosity, orientation, branching, density, area fraction, size distribution, and
per-specimen aggregates.

Classic fractography — ductile versus brittle, dimples, cleavage facets, fatigue striations,
intergranular versus transgranular — is read from grayscale surface **texture**, which a
binary mask has thrown away. This app does not attempt it, and a panel claiming to would be
inventing its answers.

## What kind of contribution this is

Stated plainly, because the alternative is letting a reader assume something stronger.

**No metric here is new, and the search for one is closed.** Per-region area, skeleton
length, mean and maximum width, branch-point counts and an orientation index from a binary
mask are **DiameterJ** (Hotaling et al., *Biomaterials* 61:327–338, 2015), which has a NIST
validation behind it. Endpoint/slab/junction classification and branch lengths are **Fiji
AnalyzeSkeleton**, shipped since about 2008. The density taxonomy (P10/P20/P21) is
**Dershowitz & Herda (1992)**. The projected-length roughness parameter is **Underwood &
Banerji**. The sampling, counting and confidence-interval layer is **ASTM E562, E1382,
E1245, E2283** and **ISO 643**. The censoring machinery is rock-mechanics window sampling.
Twenty-three separate novelty framings were tested against the literature over this
project's life and all twenty-three were already owned; see
`docs/PRACTICE_AND_PRIOR_ART.md` for the list and the citations that killed each one.

**What this is, then:** those established metrics computed with the sampling discipline the
standards actually require, on a corpus where that discipline changes the answer. Frames
collapsed to fields, because a field imaged through two detectors is one field. One
magnification per determination, because a 6.5× coarser pixel measures a different
population. Arms never pooled. Specimens never ranked, because one imaged site per specimen
makes the between-field and between-specimen variance the same parameter. Every statistic
carrying its null or its interval, and every refusal stated on screen rather than left as a
silence. The measured results it does assert — the detector changes crack length rather than
width; crack area survives a 6× coarser pixel — each survived an adversarial attempt to kill
them, and the ones that did not survive are recorded as killed.

**The one framing that has not been refuted is procedural**, and it remains conditional: no
ASTM or ISO test method exists for quantifying cracks in micrographs by image analysis, and
the coatings literature says so directly. A documented, sampled, interference-listed,
Pij-labelled, CI-bearing procedure with quantified threshold sensitivity would be a modest
standards-shaped contribution.

**Status of the work-item check, 2026-09-29 — partially done, and it cannot be closed from
outside ASTM.** What a public search establishes:

* No live ASTM E04 or E08 work item on quantifying cracks in micrographs by image analysis
  surfaced. E04.14 is the relevant subcommittee (Quantitative Metallography).
* The existing ASTM crack standards are **mechanical, not image-analysis**: E647 (fatigue
  crack growth rates), E1820 (fracture toughness). Their live work items — WK93300, WK95201
  — are revisions of E1820, not new image-analysis methods.
* One adjacent live item exists and does **not** collide: ASTM **D04** is developing a
  proposed method for load-induced cracking in asphalt mixtures (announced August 2026).
  That is mechanical testing of asphalt, not micrograph measurement.
* **Supporting evidence for the gap:** ASTM **D661** does rate coating cracking — by
  comparison against *photographic standards*, i.e. subjective visual matching rather than
  measurement. An existing standard that ranks cracking by eye is consistent with there
  being no method that measures it.
* IIW Commission V covers NDT and quality assurance of welded products; nothing on
  metallographic crack quantification surfaced.

**What would actually close it:** a member search of ASTM's work-item database for E04 and
E08 (it is not publicly searchable — `astm.org` returns 403 to automated fetches and part of
it is members-only), or an email to the E04.14 staff manager. Until then treat the framing as
*not yet refuted* rather than *established* — absence from a public search is not absence
from the register.

Use this as *fitness for purpose*: an app that reports what materials papers report, in
units they can compare, with the uncertainty attached and the limits named.

## Install

**As an app.** [Download the latest release](https://github.com/jzhang29-max/crack-fractography/releases/latest),
unzip, drag `Crack Fractography.app` to Applications, double-click. It is a real application
window — the analysis runs inside it, not in a browser tab. The app is unsigned, so macOS
refuses it and reports that it **"is damaged and can't be opened"**. That message is wrong:
it means only that there is no developer signature. Once, in Terminal:

```bash
xattr -dr com.apple.quarantine "/Applications/Crack Fractography.app"
```

Apple Silicon, macOS 12+. Your measurements live in
`~/Library/Application Support/Crack Fractography` and survive replacing the app.

**From source.** `./run` — it builds its own virtualenv and serves on
<http://127.0.0.1:8810>.

**To build the app yourself:** `./packaging/build.sh`.

**Windows and Linux.** Both build and pass CI's smoke check, but only macOS is used by hand
here — treat them as untested in practice. On Linux the native window needs GTK or Qt
bindings that cannot be bundled reliably, so the app falls back to opening your browser and
says so in its log; everything else is identical.

### What works without anything else installed

Use **+ Add image** to give it a black-and-white mask and it is measured. That needs nothing
configured. (There is no drag-and-drop onto the page — use the button.)

To draw or correct a mask, the **Mark** tab starts the marking tool from the SEM repo, so the
detect / correct / measure loop is reachable without leaving the app.

Two things need a [sem-crack-detector](https://github.com/jzhang29-max/sem-crack-detector)
checkout, which you point at once in **Setup**:

| | needs the SEM repo |
|---|---|
| measure a mask you add | no |
| segment a raw micrograph (`.tif`) | yes — the detector's model is pickled against that repo's own interpreter, so it is run there as a subprocess rather than imported |
| the reference corpus | yes — it is that repo's masks |

The app says which of the three are available on first launch rather than failing when you
try one.

## The measurement is imported, not reimplemented

Per-region shape comes from the SEM repo's
`interior_active_learning/code/extended_features.crack_shape_measurements`. A second
implementation of the same metrics would be a silent mismatch with every number that repo
has published, and that function carries fixes worth inheriting:

* mean width is area ÷ skeleton **length**, not area ÷ pixel count — the count overstates a
  diagonal crack's width by up to √2;
* max width reads the distance transform on the skeleton **from the same crop the skeleton was
  built on** — a shape mismatch there once made max width fall back to `sqrt(area)` for every
  region ever measured.

The packaged app carries a **byte copy** of that one file in `analysis/_vendor`, because it
has to measure a mask with no second repo installed. The copy is never edited and never
preferred: when a SEM repo is configured its own file wins, and the copy's hash is checked
at runtime and in the test suite, so a repo whose copy has moved on is reported rather than
quietly diverged from. Re-vendor with `python3 packaging/vendor.py`; `build.sh` does it
every build.

## Three guards, each because it already produced a wrong number here

**A count is not a mass.** 305 components once read as a fragmented network until the largest
was found to hold 97.45% of the area. So `largest_share_of_area` and `top1pct_share_of_area`
are reported beside `n_cracks`, always, and the orientation rose is weighted by **area** —
count-weighting lets a thousand specks outvote the one crack that holds the frame.

**Length is censored at the frame edge.** A crack running out of view is longer than measured.
Regions touching the border are flagged `length_is_censored` and their share reported.

**No physical units without scale.** µm columns are `null` unless nm/px is established for
that frame: exact from instrument metadata for 80 frames, 29.24 for TXM from tile geometry,
and **absent** for 62 older SEM frames whose corpus spans a 249× magnification range. Of 355
frame-arms measured, 124 have no scale and say so in the row.

Tortuosity is left undefined unless a region has exactly two skeleton endpoints and no branch
points, the only topology for which path ÷ chord means anything. On a typical frame that is
188 of 457 cracks.

## The orientation rose carries its own null

`rose_R_null95` was computed on every frame and no pixel of the chart used it, so a reader
saw a lopsided rose and concluded "preferentially oriented" every time — the exact failure
the null exists to prevent. A synthetic mask of straight lines at **uniform random** angles
returns R = 0.267–0.285, at or above this corpus's median R of 0.257, so the observed R
alone cannot tell "oriented" from "random".

The chart now says which it is. On this corpus 104 of 142 gated frames beat their null and
38 do not; the 38 are drawn muted **and** labelled `Not distinguishable from random`,
because identity is never colour alone. The resultant orientation line is drawn only when
the frame beats its null.

Two references, deliberately different objects:

* The dashed **even-split ring** is 1/12 of the length in every bin — the uniform
  expectation for the quantity the wedges actually encode. Labelled "even", *not* as a
  significance threshold: with finitely many segments the bins scatter around it, so one bin
  crossing it means nothing on its own.
* The **verdict** is the axial resultant against its 1000-draw permutation null.

Drawing the resultant's threshold as a ring on the per-bin axis would be a number attached
to the wrong object, so the resultant appears as an *orientation only* — a line through the
centre at `rose_theta_deg`, no length claim — because an angle is the one thing an angular
axis can carry honestly.

The rose is also **mirrored** now. A crack has an axis, not a direction: 10° and 170° are
nearly the same orientation, the resultant is already computed on doubled angles, and the
convention in this literature (FracPaQ, fractopo) is a full bidirectional rose. Half a disc
was the arithmetic showing through the chart.

Mirroring it made the box near-square, which surfaced a layout bug that a narrow window had
been hiding: both chart SVGs are `width:100%`, harmless at 300×150 but 933×908 at a 930 px
panel — taller than the viewport, pushing the size distribution off the bottom. Both are
capped at 340 px now.

## Marking happens in this window

The Mark tab offers two tools, because they cover different images:

* **Edit mask** — this app's own canvas. Opens any frame the app knows about, including
  uploads, needs no SEM repo, and writes a marked **copy** into `uploads` so the derived
  research masks stay unwritten.
* **Full tool** — the SEM repo's `paint_server.py`, with whole-region flip, undo, re-apply
  model, retrain, model choice and export. It only knows that repo's own images.

The full tool used to be a link that opened the system browser, which undid the point of
packaging a desktop app at the one step that matters most. It is now reverse-proxied
same-origin at `/mark/` (`app/mark_proxy.py`) and shown in the window itself. An embed was
tried and abandoned once before: a cross-origin iframe rendered blank with no way to see
inside it. Same origin removes the blankness *and* the blindness — the UI check reads the
tool's own DOM through the frame and reports if it is empty.

The proxy exists because the tool's UI is a single 82 KB page whose every call is a
root-relative `fetch('/api/…')` or `img.src = '/api/…'` — 27 sites, no absolute origins
except the SVG namespace, no `XMLHttpRequest` at all. Root-relative means a `<base href>`
cannot help, so the HTML is rewritten on the way through and the rewrite **asserts a
non-zero count**: the failure mode of a string rewrite is silence, where the page renders
perfectly and every button talks to the wrong server.

That assertion has to be scoped to the UI page, and getting it wrong is not hypothetical —
it shipped for one test cycle. `/api/paintlayer` answers `204 No Content` with an empty body
and `Content-Type: text/html`, because Flask stamps its default type on a bodyless response.
Keying on the content type alone turned that correct 204 into a 500 blaming the tool for
having changed shape. Upstream HTML *error* pages have the same problem in reverse: they
carry no API calls either, so the assertion would have replaced the tool's own message
("no template for this image", "a reapply job is already running") with a proxy complaint.
Upstream statuses are forwarded verbatim for exactly that reason.

**`MARK_PORT` keeps development off the real labels.** The paint layer is hand-labelled
research data. The proxy was built and exercised against a *copy*, using the tool's own
`SEMCRACK_PAINT_DIR` / `SEMCRACK_ORIGINAL_DIR` overrides, with `MARK_PORT` pointing this app
at the sandbox instance. The override is tried **first**, not as a fallback: if the default
won, a development run would proxy to the researcher's real tool — writing into that data —
while reporting the sandbox port back to the UI. A whole-region flip was driven through the
proxy end to end and the real `paint/` directory came out byte-identical.

## Arms are never mixed

| arm | what it is |
|---|---|
| `sem/gated` | the SEM detector plus the operator's strokes, boundaries drawn by the image |
| `sem/machine` | the SEM detector alone |
| `txm` | the TXM export |

Different instruments, and for the two SEM arms a different definition of the object. The API
requires an arm and refuses to aggregate across them. Gated yields 34,348 crack regions
against machine's 26,075, so the operator's contribution is visible rather than blended away.

## Specimens, not frames

Grouping uses the SEM repo's own `specimen_key()` so a frame groups the way its published
statistics group it. TXM stems fall outside that grammar, where it returns `None` — used
unchanged that would have collapsed all 71 TXM frames into one "specimen" and averaged four
materials together, so `scale.txm_specimen_key()` parses them instead.

Frames within a specimen are **not independent**: on the 2026-09-15 batch the nine fields per
cell sit on a 3×3 stage raster on one small patch of one specimen — centre-to-centre about
1.5 field widths across, so they do not touch. No extent in millimetres is stated here or
on screen: `analysis/stage.py` does not assert that the instrument's stage unit is the
metre. The specimen is the inferential unit;
`estimable_dispersion` marks the 12 specimen-arms whose modal magnification holds fewer than
three fields.

**One magnification per E562 determination.** Four specimen-arms — `MAR_AmbB_AS`,
`MAR_AmbB_HIP`, `MAR_H_AS`, `MAR_H_HIP`, identically in both SEM arms — hold a tenth field
that is a single overview at 337.2396 nm/px beside the raster's nine at 51.883. A 6.5×
coarser pixel is a 6.5× coarser minimum resolvable width, and the overview's field of view is
10.6× a fine field's while taking 1/10 of the weight in a ten-field mean, so it is not a
replicate of the nine. **Every** physical aggregate on the record — the interval, the stage
gradient, the P10/P21/P20/MCL medians and the additive totals alike — is computed over the
modal magnification group's *fields*, and refuses when no group reaches three fields. Every
scale is listed in `magnification_groups`; the excluded field is still measured on its own,
and the material it covered is stated on the card — on `MAR_AmbB_HIP`, *"0.716 mm² of
material sits in that field and is not added to the 0.610 mm² above"*. That excluded figure
is **larger than the determination it was excluded from**, which is the 10.6× field-of-view
difference made concrete and the clearest single reason the overview was never a replicate
of the nine. It is worded so it cannot read as additive, because two areas side by side
otherwise invite exactly the sum this rule exists to forbid.

This moved the reported relative accuracy 53.0→62.0, 117.9→84.2, 42.4→49.1 and 81.7→93.0
percent — three of four **worse**, which is why it was not a cleanup.

It took two passes. The first moved the interval and the gradient but left the additive
totals and six physical medians summing or pooling every scale, so the card printed
`1.325218 mm² over 10 fields` two rows above `95% CI …, 9 fields at 51.883 nm/px`. The
exemption was written down as a defence — a coarse field really did cover that material, so
summing it "double-counts nothing" — and it is false. The reason that stands on its own is
that a total over fields whose **detection limits differ 6.5×** is not a total of anything:
the overview resolves a 6.5× wider minimum crack, so its area and the fine nine's are not
the same quantity. It is *also* a double-count — the overview's field of view is 10.6× a
fine field's and covers roughly 45% and 50% of the fine nine on the AmbB pair — but that
figure requires reading the FEI stage coordinates as **metres**, which `analysis/stage.py`
deliberately declines to assert, so it corroborates the decision rather than carrying it.
(A second session recomputed the same geometry independently: 4.07/9 and 4.52/9.)
Area-weighting instead of excluding is worse either way, since it weights *up* the field
whose contribution is least comparable.
Corrected, `MAR_AmbB_HIP` reads 0.609687 mm² over 9 fields, P20 1815.7 /mm² (was 2627.6),
MCL 26.5 µm (was 15.2 — the pool had included two overview frames whose MCL are 1181 µm and
930 µm). `n_fields_scaled ≤ area_fraction_ci.n_fields` is now asserted on every record.

The app's worst SEM relative accuracy is `MAR_Amb_AS` at 138.0%, which has no recoverable
scale at all and is untouched by this.

**Specimens are not ranked, and the app says so.** One site per specimen makes the
between-field and the between-specimen variance the same component, so no ordering of these
specimens is estimable at all — spatial pseudoreplication in Hurlbert's sense (1984). Three
consequences, shipped together:

* The comparison table is sorted by **name**. It used to sort by area fraction, under a
  comment saying so, which made one render path emit a ranking and the refusal to rank in
  the same paint; the 11 records with no interval were ordered on a bare median. Name order
  is unconditional — a sortable table would need to be an explicit control with a visible
  active column, never the order the page opens in.
* A standing statement, `Ranking specimens is not supported by this sampling design.`, on
  33 of 34 specimen-arms. Not gated on relative accuracy and not on the interval existing:
  a specimen at ±6% from one site is exactly as unrankable as one at ±138%. It switches off
  when `n_patches ≥ 2`, which nothing reaches today and no code edit is needed to reach.
* Relative accuracy no longer says "too coarse to rank this specimen" — it says
  `wider than E562's ±10% precision target`, which is what it measures. The old wording
  taught the reader that driving RA under 10% would earn a comparison.

**No path-roughness read-out.** `R_L` shipped for several releases and is now deleted, not
fixed. It is true length over length projected on a **declared** specimen axis, and this app
has nowhere to declare one: `R_L_axis_deg` was `0.0` on all 356 frames. Against a fixed image
axis the projection is `chord·cos θ`, so the column reduced to `(length/chord)·sec θ` — an
identity rather than a measurement — and its corpus median *and* upper quartile were both
exactly 1.4142, where `sec(45°)` is simultaneously a pixel-lattice diagonal, a straight 45°
crack and the isotropic expectation. It also ran −0.78 / −0.83 / −0.45 against `rose_R`,
which answers the same question and carries a per-frame permutation null. The frame row, the
figure axis and the CSV columns are gone; `conclusions.REFUSALS` states the removal rather
than printing an em-dash. Its predecessor, tortuosity, left the frame summary earlier for a
different reason (a 2-endpoint gate describing 2.6% of gated crack area and none of TXM) —
but `Tortuosity` **remains** a per-crack column on all 60,893 rows.

The axis-dependent lattice diagnostic went with it, replaced by
`lattice_chord_share_all_segments`: the share of skeleton branches whose end-to-end chord is
indistinguishable from a lattice axis or diagonal, within the angle two pixels of endpoint
wobble subtend over that chord. 0.37–0.67 on real frames, 1.0 on a field of 5 px stubs. No
threshold is attached to it and nothing consumes it; it is there to be read.

## Layout

    analysis/scale.py     nm/px per frame, or None. Never a guess.
    analysis/measure.py   per-crack rows + frame summary
    analysis/batch.py     all arms -> analysis/out/{frames,cracks,specimens}.json
    app/server.py         JSON API; does no measurement, only serves the dataset
    app/templates, static the single page
    data/{sem,txm,txm_export}  relative symlinks, gitignored

Charts are inline SVG with no CDN: this is meant to run on an offline lab machine, and a chart
that silently fails to render is worse than a table. Both palettes were run through a
colour-vision validator rather than eyeballed; the light mode's contrast warning on two slots
is why every chart also has a table beside it.
