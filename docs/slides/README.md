# The slide deck

    python3 docs/slides/make_slides.py      ->  all_figures.pdf

## To change the slides, edit `slides.json`

That file **is** the deck. Nothing about the wording lives in the Python any more.

```json
{
  "figure": "docs:fig_ceiling.png",
  "title":  "A correct answer caps at IoU 0.50",
  "bullets": ["A perfectly placed trace peaks at 0.4993.",
              "So IoU 0.42 is ~75% of possible, not 42%."],
  "caveat": "Always quote IoU with this ceiling."
}
```

| field | what it does |
|---|---|
| `figure` | `docs:x.png` looks in `docs/figures/`, `paper:x.png` in `paper/figures/out/` |
| `title` | the heading beside the figure. Under ~30 characters or it wraps |
| `bullets` | 2–4 **short** lines, printed as a list. The figure is the slide; these support it |
| `caveat` | one line in amber under the bullets. `""` for none |

Reorder, delete or add entries freely, then re-run. Changes appear immediately —
verified by round-trip: editing a title and a bullet puts exactly that text on the plate.

## What the generator refuses to do

* **A figure that does not exist stops the build.** It does not emit a slide with a hole
  in it. A path bug once produced a 42 KB "deck" containing no figures at all and nothing
  complained, which is why this is an error and not a warning.
* **Type below 9 pt stops the build.** A figure in this project once shipped at 2.3 pt.
  Multi-panel slides wrap their captions narrower rather than shrinking past the floor.

## What is NOT in slides.json, and why

Three sections are generated, because hand-copying them is how they go stale:

* the plain-English metric card and the Venn picture — `metrics_plain.py`
* the measurement definitions — imported live from `app/groupstats.py`, so the deck
  always says what the application says
* the pipeline walk-through — drawn from `../flowchart/flow_content.json`, the same
  record the standalone flow PDF uses

To change any of those, change them at the source and every output follows.
