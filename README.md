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

## Install

**As an app.** [Download the latest release](https://github.com/jzhang29-max/crack-fractography/releases/latest),
unzip, drag `Crack Fractography.app` to Applications, double-click. It is a real application
window — the analysis runs inside it, not in a browser tab. macOS refuses unsigned apps
downloaded from the internet, so once:

```bash
xattr -dr com.apple.quarantine "/Applications/Crack Fractography.app"
```

Apple Silicon, macOS 12+. Your measurements live in
`~/Library/Application Support/Crack Fractography` and survive replacing the app.

**From source.** `./run` — it builds its own virtualenv and serves on
<http://127.0.0.1:8810>.

**To build the app yourself:** `./packaging/build.sh`.

### What works without anything else installed

Drop a black-and-white mask on the page and it is measured. That needs nothing configured.

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
cell tile a 3×3 grid over ~1.2 × 1.1 mm of one specimen. The specimen is the inferential unit;
`estimable_dispersion` marks the 11 specimen-arms holding fewer than three frames.

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
