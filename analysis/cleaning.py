#!/usr/bin/env python3
"""Pre-analysis cleaning -- the steps that RECORD, and an explicit record of the ones that
are deliberately not shipped.

Framing from Dow et al., Automation in Construction 151:104867 (2023), who measured this
exact tradeoff: uncleaned input recall 90%, best-recall filter 85%, best-F1 setting 77% --
the best method discarded about 14% of recoverable true crack pixels to lift precision from
22% to 91% -- and whose own constants "are likely only suitable for cracks of widths that
match the dataset". Cleaning parameters do not transfer between corpora.

This project has already shipped two artefact "fixes" that were deleters, one removing 19%
of all human labels, and a monotone correction that removed 30% of a terminal crack. So the
default here is to RECORD, never to remove, and the destructive steps are absent rather than
off-by-default -- an off toggle is an invitation, and the parameters that would make them
safe are corpus-specific and unmeasured here.

What this module does:
  1  ingest assertion -- is the mask actually a two-valued crack mask, and which polarity
  2  physical frame -- nm/px, area, and the smallest crack this frame could express
  3  speck threshold expressed in PHYSICAL units, with the pixel fallback made visible
  8  border handling, differentiated per metric (the length half lives in measure.py)

What it deliberately does not do, and why, is in NOT_SHIPPED below. It is emitted into every
frame record so a reader of the CSV can see which operations were never applied, rather than
having to assume.
"""
import numpy as np

#: Physical reference area for the speck floor, chosen to equal the historical 25 px at the
#: corpus median scale (~51.9 nm/px) so nothing moves for a typical frame and only the
#: frames that were genuinely out of step change.
SPECK_UM2 = 0.067

#: The resolution floor: below this a region has too few pixels for regionprops to mean
#: anything, whatever the magnification. Also the value used where nm/px is unknown, so
#: unscaled frames behave exactly as they always did.
SPECK_PX_FALLBACK = 25

#: 8-connectivity. Stated in every record because it is not a detail: 4- vs 8-connectivity
#: rewrites every count statistic in the file, and it was previously a silent argument.
CONNECTIVITY = 2

NOT_SHIPPED = {
    "hole_filling": "would remove enclosed background islands, which here are uncracked "
                    "ligaments and crack bridges -- a toughening mechanism other work "
                    "builds algorithms to FIND (Babout et al., Scripta Mater. 65:131, 2011)",
    "skeleton_spur_pruning": "would shorten TCL by deleting real short branches along with "
                             "thinning spurs; the threshold that separates them is "
                             "corpus-specific and is not measured here",
    "small_component_removal": "the Dow et al. tradeoff verbatim -- it costs recall, and "
                               "disproportionately on the AM subset where cracks are near "
                               "intensity-invisible (d=+0.09 against +1.10..+2.91 elsewhere)",
    "gap_bridging": "manufactures crack where none was imaged. ASTM E1382-97(2015) 6.4 "
                    "warns boundary completion may create false boundaries. If traces are "
                    "ever merged it must be in bookkeeping only, changing counts and never "
                    "area or length",
}


def speck_threshold_px(nm_per_px):
    """The speck cutoff for THIS frame, in pixels, and how it was arrived at.

    TWO FLOORS, AND THEY ANSWER DIFFERENT QUESTIONS. Collapsing them into one is a bug in
    either direction.

      PIXELS ask whether a shape is measurable at all. Width, orientation and tortuosity
      from regionprops on a three-pixel blob are noise at any magnification -- DiameterJ's
      own validation covers features of 10 px and up. This floor is about resolution and
      does not care what the pixels represent.

      PHYSICAL AREA asks whether two frames excluded the same class of object. A fixed
      25 px spans a 133x range of physical size across this corpus (29.24 to 337.24 nm/px),
      so speck_count is not comparable frame to frame without it.

    So the threshold is the LARGER of the two. Taking the physical floor alone, as the
    cleaning plan says literally, gives 1 px at the corpus's coarsest scale -- handing
    shape statistics to two-pixel regions. Taking the pixel floor alone leaves the
    comparability problem the plan correctly identifies. Whichever one binds is reported.
    """
    if not nm_per_px:
        return SPECK_PX_FALLBACK, {
            "basis": "pixels (no scale for this frame)",
            "threshold_px": SPECK_PX_FALLBACK, "threshold_um2": None,
            "binding_floor": "pixel"}
    um_per_px = nm_per_px / 1000.0
    phys = max(1, int(round(SPECK_UM2 / (um_per_px ** 2))))
    px = max(SPECK_PX_FALLBACK, phys)
    return px, {
        "basis": "max(pixel floor, physical floor)",
        "threshold_px": px,
        "pixel_floor_px": SPECK_PX_FALLBACK,
        "physical_floor_px": phys,
        "threshold_um2": round(px * um_per_px * um_per_px, 5),
        "reference_um2": SPECK_UM2,
        "binding_floor": "physical" if phys > SPECK_PX_FALLBACK else "pixel",
        "note": "pixels decide whether a shape is measurable; physical area decides "
                "whether two frames excluded the same class of object",
    }


def ingest_assertion(gray, mask):
    """Is this a two-valued crack mask, and is crack really the minority phase?

    Not a filter -- nothing is changed. Three things that are silently wrong otherwise:

    NOT TWO-VALUED. A greyscale image thresholded at 128 by load_mask looks like a mask and
    is not one; every area statistic would then be a statistic about an arbitrary threshold.

    POLARITY. crack = BLACK is the convention. A mask saved the other way round measures the
    matrix and reports it as crack, and the number is perfectly plausible -- which is why
    the fraction is checked rather than the caller trusted.

    EMPTY OR FULL. Both produce numbers; neither produces a measurement.
    """
    vals = np.unique(gray)
    frac = float(mask.mean())
    out = {
        "n_grey_levels": int(vals.size),
        "two_valued": bool(vals.size <= 2),
        "crack_fraction_as_read": round(frac, 6),
        "connectivity": CONNECTIVITY,
        "connectivity_note": "8-connected labelling; 4-connectivity changes every count",
        "warnings": [],
    }
    if vals.size > 2:
        out["warnings"].append(
            f"not a two-valued mask ({vals.size} grey levels) -- it was thresholded at 128, "
            f"so every area statistic depends on that threshold")
    if frac > 0.5:
        out["warnings"].append(
            f"{100 * frac:.1f}% of the frame reads as crack. Crack should be BLACK and the "
            f"minority phase -- this looks inverted, and an inverted mask measures the "
            f"matrix and calls it crack")
    if frac == 0:
        out["warnings"].append("no crack pixels at all")
    elif frac == 1:
        out["warnings"].append("every pixel reads as crack")
    return out


def detection_limit(nm_per_px, speck_px):
    """The smallest crack this frame could express, in physical units.

    ANSI/NACE TM0284-2016 declares its limit by magnification rather than filtering small
    features out. Same idea: state what the frame cannot see instead of pretending the
    absence of small cracks is a measurement.
    """
    if not nm_per_px:
        return {"one_pixel_um": None, "speck_cutoff_um2": None,
                "note": "no scale for this frame, so the limit cannot be stated in um"}
    um = nm_per_px / 1000.0
    return {
        "one_pixel_um": round(um, 4),
        "min_resolvable_width_um": round(um, 4),
        "speck_cutoff_um2": round(speck_px * um * um, 5),
        "note": "a crack narrower than one pixel is not absent, it is unresolved",
    }
