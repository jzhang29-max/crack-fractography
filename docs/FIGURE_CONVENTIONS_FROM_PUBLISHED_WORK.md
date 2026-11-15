# What published figures of this kind actually look like

Three editions of Figure 2 and three of Figure 3 were rejected in a row. Each was built
from a description of what a scientific figure ought to look like rather than from one.
This file records what two real published figures DO, measured by opening them, so the
plates can be built against a source instead of against taste.

The reference figures are cited here and nothing is reproduced from them. What is
copied is convention -- element vocabulary, label placement, line weight, how much of
an instrument gets drawn -- which is not anyone's expression.

## Reference A — imaging geometry schematic
Journal of Synchrotron Radiation 32 (2025) 1503, figure 1(a). Open access, CC-BY.
`https://pmc.ncbi.nlm.nih.gov/articles/PMC12591069/`

## Reference B — correlative imaging overview, two instrument insets
Science Advances 8 (2022) eabj6738, figure 1. Open access, CC-BY.
`https://pmc.ncbi.nlm.nih.gov/articles/PMC8986107/`

## The finding, and it is the opposite of what was built

**Neither figure draws the microscope.** Both draw only the measurement geometry, and
both do it with four or five elements:

| element | Reference A | Reference B (X-ray) | Reference B (electron) |
|---|---|---|---|
| source | off-figure, beam enters from the left | a small filled bar, labelled "X-ray source" | a filled wedge, labelled "E-beam" |
| beam | a flat translucent BAND across the sheet | a pale filled CONE | a filled cone |
| specimen | a plain filled rectangle, labelled "sample" | the dogbone silhouette, labelled "Sample" | a plain grey block |
| signal | a small fan of arrows in one colour | — | one ray labelled "e-" |
| detector | plain filled boxes, labelled | a plain grey bar | a plain grey bar |

There is **no optical column anywhere**: no gun, no condenser, no objective, no
crossover, no scan coils, no zone plates, no optic axis. Reference B draws a whole
laboratory X-ray microtomograph in four elements occupying about a fortieth of its
sheet.

Everything else these figures do:

* **Flat colour, no gradient and no shadow.** Fills are flat and often translucent.
* **No engineering drawing conventions.** No section hatching, no fixed-support symbol,
  no dimension lines with extension lines and arrow terminators, no dash-dot centreline.
  None of these appears in either figure.
* **Labels sit beside the element in plain sans-serif**, horizontal, with a short
  straight leader only where the label cannot touch the thing it names.
* **A feature of interest is marked with a dashed ellipse or a single arrow plus a
  word**, never with a dimension.
* **Panel letters are lowercase, bold, no parentheses**, at the top left.
* **Micrographs carry a scale bar** as a plain filled bar with its length beside it,
  bottom right.
* **A coordinate triad** anchors the geometry where orientation matters (Reference A).

## Data panels
Reference A figure 2, and the J-vs-crack-extension plot inside Reference B figure 1:

* a plain grid of ordinary axes, nothing custom;
* **every axis carries a full title with its unit in parentheses** -- "scattering angle
  2θ (°)", "crack extension (mm)", "J (kJ/m²)";
* **several numeric tick labels per axis**, not two end values;
* panel letters lowercase bold at the top left, inside the axes;
* a framed legend inside the one panel that needs it.

Gridlines appear in both, but the project's own survey of 129 figures from the TARGET
journals (see `paper/figures/journal_style.py`) found full box, no grid, so the house
rule wins on that point. What is taken from these two is the structure, not the frame.

## What this changes

Figure 2 loses both optical trains and becomes source, beam cone, specimen, detector,
per column -- which is what a reader of these journals is used to and what the previous
edition buried under an instrument diagram nobody asked for.

Figure 3's nine sweeps become ordinary labelled axes with real axis titles and real
tick labels, which is what the data panels above are.
