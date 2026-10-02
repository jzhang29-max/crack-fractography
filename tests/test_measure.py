#!/usr/bin/env python3
"""Guards on the measurement, on synthetic masks where the answer is known by construction.

Run: ../.venv/bin/python3 tests/test_measure.py   (or the SEM repo's venv)

A MUTATION AUDIT ON 2026-10-01 PROVED SIX OF THESE GUARDS WORTHLESS. For each one the audit
broke the behaviour the guard names and the guard still printed PASS. Every one of the six
failed for the same family of reasons, and they are worth naming together because the next
guard added here will be tempted by all of them:

  A ONE-ELEMENT FIXTURE MAKES max, min, mean AND 1.0 THE SAME NUMBER. "largest share ~1.0"
  ran on a frame whose only non-speck region was a single bar, so max/sum was 1.0 by algebra
  and `areas.min()/areas.sum()` passed it.

  A FIXTURE THAT EXERCISES ONE BRANCH OF A DISJUNCTION CERTIFIES ALL FOUR. The censored-edge
  check only ever built a region at x0 == 0, so deleting `or y1 >= H or x1 >= W` from
  measure.py passed.

  AN EXPECTATION THE CODE SUPPLIES IS NOT AN EXPECTATION. The rose's "weighted_by" was read
  off a field measure.py re-supplies as its own `.get(..., "segment length")` default, so
  deleting the real declaration in segments.py passed.

  A NAME IS NOT A VALUE. The ISO 643 edge rule asserted that the string "n_edge/2" appears
  in the output, so changing the arithmetic to `n_int + n_edge` -- counting every edge region
  whole -- passed while the label still claimed the halving.

  A TOP-LEVEL SCAN DOES NOT SEE A FORWARDED DICT. "no path-roughness field" iterated the
  summary's own keys, and measure.py forwards segments.py's whole summary under one key, so a
  tortuosity field added in segments.py arrived in the dataset invisibly.

  PRINTING A NUMBER IN THE DETAIL STRING IS NOT ASSERTING IT. The scale check printed
  nm_per_px and asserted only that micrometre columns were non-None.

Each repaired guard below carries its own note: what the old assertion did, what defeated it,
and what the new one asserts. The notes are not decoration -- the repository's convention is
that a check explains the number it already got wrong once.

WHAT THIS FILE DOES NOT PIN: the VALUE of the TXM scale constant. tests/test_scale.py pins
29.24 nm/px and its tile-geometry derivation. Here the scale is read off the frame summary
and used only to check UNIT RELATIONS -- that a micrometre column is its pixel column times
the frame's own stated micrometres per pixel. A guard here cannot also pin the constant
without duplicating test_scale.py and going stale against it.
"""
import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(REPO, "analysis"))
from measure import measure_frame, SPECK_PX     # noqa: E402
from scale import nm_per_px, txm_specimen_key   # noqa: E402

FAILED = []

#: A TXM stem, so nm/px comes from the constant anchored by tile geometry inside scale.py
#: rather than from the SEM repo's FEI metadata CSV. An SEM stem made the scale checks pass
#: on a developer machine, where data/sem is a live symlink, and fail anywhere without that
#: checkout -- which is every clone, every CI run and every user. Caught by the first CI run
#: on 2026-09-27, and it is the coupling CI was added to find.
TXM_STEM = "Average_mosaic_260618_B2_2_1"


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))
    if not cond:
        FAILED.append(name)


def rounded_to(got, hand, dp, slack=0.0):
    """Is `got` the hand-computed `hand` rounded to `dp` decimals?

    The tolerance is the rounding bound itself (plus any slack for a rounded INPUT), so a
    value sitting exactly on a rounding tie cannot make this flake, and nothing larger than
    one unit in the last reported place can slip through.
    """
    return (isinstance(got, (int, float))
            and abs(float(got) - hand) <= 0.5 * 10 ** (-dp) + slack + 1e-12)


# ---------------------------------------------------------------------------------------
# Fixtures. Each is described by the numbers that make it, because every expectation below
# is derived from those numbers and not from a previous run of the code.
# ---------------------------------------------------------------------------------------

def two_bar_frame():
    """TWO bars of known area -- 4x100 = 400 px and 4x40 = 160 px -- plus 30 single pixels.

    The 30 specks are what the mass-versus-count guard is about: a COUNT says 32 regions and
    reads as a fragmented network, while the MASS is 560 px in two bars.

    THE SECOND BAR IS THE REPAIR. The original fixture had one bar, and after speck
    filtering `areas` was a one-element array, where max/sum, min/sum, mean/sum and the
    constant 1.0 are all the same number.
    """
    m = np.zeros((200, 200), bool)
    m[100:104, 40:140] = True           # 400 px
    m[150:154, 40:80] = True            # 160 px
    rng = np.random.default_rng(0)
    for y, x in zip(rng.integers(5, 60, 30), rng.integers(5, 190, 30)):
        m[y, x] = True                  # 30 specks, all in rows 5..59, clear of both bars
    return m


def three_interior_two_edge_frame():
    """200x200 with FIVE measurable regions: 3 wholly interior, 2 touching the frame edge.

    Counts known by construction, which is what the ISO 643 planimetric rule needs: the
    expected P20 numerator is 3 + 2/2 = 4, and the two wrong answers a reader might get
    instead -- 5 if edge regions are counted whole, 3 if they are dropped -- are far enough
    from it to be told apart at two decimal places.
    """
    m = np.zeros((200, 200), bool)
    m[100:104, 40:140] = True           # interior, 400 px
    m[20:24, 60:100] = True             # interior, 160 px
    m[150:154, 60:100] = True           # interior, 160 px
    m[60:64, 0:50] = True               # touches the LEFT edge
    m[0:4, 120:170] = True              # touches the TOP edge
    return m


def main():
    m = two_bar_frame()
    rows, s = measure_frame(m, "synthetic_bar", "sem")
    big = max(rows, key=lambda r: r["area_px"])
    small = min(rows, key=lambda r: r["area_px"])

    check("specks are excluded from shape stats but counted",
          s["speck_count"] == 30 and s["n_cracks_measured"] == 2,
          f"specks {s['speck_count']}, measured {s['n_cracks_measured']}")

    # REPAIRED 2026-10-01. The old assertion was `largest_share_of_area > 0.99` on a fixture
    # with ONE non-speck region, so max/sum was 1.0 by algebra: the audit replaced
    # areas.max() with areas.min() in measure.py and the guard still passed, as would
    # areas.mean(), areas.sum()/areas.sum(), or the literal 1.0.
    #
    # The fixture now has two bars of 400 px and 160 px, areas fixed by construction, so the
    # share is 400/560 = 0.714285... = 0.7143 at four places and nothing but a max over the
    # region areas produces it. min/sum would be 0.2857 and mean/sum 0.5. The two bars are
    # also asserted to be the regions they are, so a speck threshold change that swallowed
    # the 160 px bar would fail here rather than silently restore the degenerate fixture.
    check("the two bars are the measured regions, 400 px and 160 px",
          big["area_px"] == 400 and small["area_px"] == 160,
          f"largest {big['area_px']}, smallest {small['area_px']}")
    check("a count is not a mass: largest share is max(area)/sum(area), by hand 400/560",
          s["largest_share_of_area"] == round(400 / 560, 4)
          and s["largest_area_px"] == 400,
          f"largest_share_of_area={s['largest_share_of_area']} "
          f"(hand {round(400 / 560, 4)}; min/sum would be {round(160 / 560, 4)}, "
          f"mean/sum {round(280 / 560, 4)})")

    check("region total counts every region, specks included",
          s["n_regions_total"] == 32, f"n_regions_total={s['n_regions_total']}")
    check("a 4x100 bar measures ~4 px mean width",
          abs(big["MeanWidth_px"] - 4.0) < 1.0, f"{big['MeanWidth_px']}")
    check("a straight bar is ~straight: tortuosity near 1",
          big["Tortuosity"] is not None and abs(big["Tortuosity"] - 1.0) < 0.05,
          f"{big['Tortuosity']}")
    check("an interior region is not flagged as censored",
          big["length_is_censored"] is False and s["n_censored"] == 0)

    # REPAIRED 2026-10-01. A bar running off the edge must be flagged: its length is a lower
    # bound. The old check built ONE region, at x0 == 0, and asserted it was censored --
    # which exercised exactly one of the four disjuncts in
    #     touches = bool(y0 == 0 or x0 == 0 or y1 >= H or x1 >= W)
    # so the audit deleted `or y1 >= H or x1 >= W` -- half the rule, the two far edges --
    # and the guard passed. A region leaving the bottom or the right of the frame was
    # reported as a complete crack.
    #
    # Now parametrised over all four edges, one region per frame so n_censored pins the
    # count too, with the shape held constant (a 4x100 bar) so the only thing varying is
    # which border it reaches. Deleting any single disjunct now fails one of the four.
    H = W = 200
    for edge, (ys, xs) in {
            "top    (y0 == 0)": (slice(0, 4), slice(60, 160)),
            "bottom (y1 >= H)": (slice(H - 4, H), slice(60, 160)),
            "left   (x0 == 0)": (slice(60, 160), slice(0, 4)),
            "right  (x1 >= W)": (slice(60, 160), slice(W - 4, W))}.items():
        e = np.zeros((H, W), bool)
        e[ys, xs] = True
        erows, es = measure_frame(e, "synthetic_edge", "sem")
        check(f"a region touching the {edge} edge is flagged censored",
              len(erows) == 1 and erows[0]["touches_frame_edge"] is True
              and erows[0]["length_is_censored"] is True and es["n_censored"] == 1,
              f"touches={erows[0]['touches_frame_edge'] if erows else None} "
              f"censored={erows[0]['length_is_censored'] if erows else None} "
              f"n_censored={es['n_censored']}")

    # No scale -> no physical columns, rather than a default.
    check("a frame with no known scale gets no um columns",
          s["scale_known"] is False and "area_um2" not in big
          and "crack_area_um2" not in s)

    # ---------------------------------------------------------------------------------
    # REPAIRED 2026-10-01: the micrometre columns.
    #
    # The old pair of checks asserted that scale_known was True and area_um2 was not None,
    # printed nm_per_px in the detail string, and checked the area relation alone. Printing
    # a number is not asserting it, and the area column is one of nine. The audit dropped
    # the pixel->micrometre multiply from measure.py's (src, dst) conversion loop
    #     r[dst] = (round(float(v) * px_um, 4) ...   ->   round(float(v), 4)
    # so mean_width_um, max_width_um, network_length_um and longest_crack_um all shipped
    # PIXEL values under micrometre names -- a 34x error on this corpus -- and the guard
    # passed, because they were non-None and area_um2 was computed on a different line.
    #
    # Every micrometre column is now checked against its own pixel column times the frame's
    # own stated micrometres per pixel, hand-computed here, lengths linearly and areas with
    # the square. The tolerance is the reported rounding bound, not a fudge factor.
    #
    # THE VALUE OF nm_per_px IS DELIBERATELY NOT PINNED HERE -- tests/test_scale.py pins
    # 29.24 and its tile geometry. This guard asserts the unit RELATION, which is the part
    # measure.py owns; a second copy of the constant here would go stale against that file.
    # ---------------------------------------------------------------------------------
    edge_rows, edge_s = measure_frame(three_interior_two_edge_frame(), TXM_STEM, "txm")
    nm = edge_s["nm_per_px"]
    check("a frame with a known scale gets um columns",
          edge_s["scale_known"] is True and isinstance(nm, (int, float)) and nm > 0
          and edge_rows[0].get("area_um2") is not None,
          f"nm_per_px={nm}")
    um_px = (nm / 1000.0) if nm else None       # micrometres per pixel
    for r in edge_rows:
        rel = [
            # column,               hand-computed from,                       dp, slack
            ("area_um2", r["area_px"] * um_px ** 2, 4, 0.0),
            ("mean_width_um", r["MeanWidth_px"] * um_px, 4, 0.005 * um_px),
            ("max_width_um", r["MaxWidth_px"] * um_px, 4, 0.005 * um_px),
            ("network_length_um", r["SkeletonLength_px"] * um_px, 4, 0.005 * um_px),
            ("longest_crack_um", r["TipToTipGeodesic_px"] * um_px, 4, 0.005 * um_px),
        ]
        bad = [(k, r.get(k), hand) for k, hand, dp, sl in rel
               if not rounded_to(r.get(k), hand, dp, sl)]
        check(f"crack {r['crack_id']}: every um column is its px column x {nm} nm/px",
              not bad, f"{bad}" if bad else
              f"area {r['area_um2']} um2, mean width {r['mean_width_um']} um")

    frame_rel = [
        ("crack_area_um2", edge_s["crack_area_px"] * um_px ** 2, 2, 0.0),
        ("total_length_um", edge_s["total_skeleton_length_px"] * um_px, 2, 0.05 * um_px),
        ("tcl_um", edge_s["total_skeleton_length_px"] * um_px, 2, 0.05 * um_px),
        ("field_width_um", edge_s["width_px"] * um_px, 2, 0.0),
        ("area_analysed_mm2",
         edge_s["height_px"] * edge_s["width_px"] * (um_px / 1000.0) ** 2, 6, 0.0),
    ]
    bad = [(k, edge_s.get(k), hand) for k, hand, dp, sl in frame_rel
           if not rounded_to(edge_s.get(k), hand, dp, sl)]
    check("every frame-level um/mm column is its px column x the frame's own scale",
          not bad, f"{bad}" if bad else
          f"{edge_s['crack_area_um2']} um2 crack in {edge_s['area_analysed_mm2']} mm2")
    # A relation that holds whatever the scale is: the same factor converts a length across
    # the frame and a length along the skeleton, so their RATIO is scale-free. This one
    # survives any change to the constant and fails if either conversion is dropped or
    # squared. The bound is the rounding of the three reported inputs propagated through the
    # division -- 2 dp on the two micrometre columns and 1 dp on the pixel length -- and not
    # a tolerance chosen to fit: here the residual is 5.8e-4 against a bound of 2.2e-3,
    # while dropping the length conversion moves the ratio from 1.31 to 44.8.
    got = edge_s["total_length_um"] / edge_s["field_width_um"]
    hand = edge_s["total_skeleton_length_px"] / edge_s["width_px"]
    bound = ((0.005 + 0.005 * hand) / edge_s["field_width_um"]
             + 0.05 / edge_s["width_px"] + 1e-12)
    check("the um/px factor is the same for the field and for the skeleton (scale-free)",
          abs(got - hand) <= bound,
          f"{edge_s['total_length_um']}/{edge_s['field_width_um']} = {got:.5f} vs "
          f"{edge_s['total_skeleton_length_px']}/{edge_s['width_px']} = {hand:.5f}, "
          f"bound {bound:.5f}")

    # An empty mask must not crash and must not claim a share of nothing.
    _, z = measure_frame(np.zeros((50, 50), bool), "empty", "sem")
    check("an empty mask yields no cracks and no largest share",
          z["n_cracks_measured"] == 0 and z["largest_share_of_area"] is None
          and z["area_fraction"] == 0.0)

    rose_guards()
    iso643_guard(edge_s)
    no_path_roughness_guard(edge_s)

    check("Pij densities are labelled with their subscripts",
          "p21_skeleton_mm_per_mm2" in edge_s and "p20_per_mm2" in edge_s
          and "p20_edge_rule" in edge_s)

    check("scale is None for a frame with no metadata, not a default",
          nm_per_px("260622_316_H_b2_front_CBS_01") is None)
    check("TXM specimens parse and normalise case",
          txm_specimen_key("Average_mosaic_260618_B2_x") == "260618_b2"
          and txm_specimen_key("Average_mosaic_260618_b2_y") == "260618_b2")
    check("TXM keeps distinct materials distinct",
          txm_specimen_key("Average_mosaic_260619_HC_316L_a") !=
          txm_specimen_key("Average_mosaic_260620_wrought_316L_a"))
    check("an unparseable stem returns None, not a per-frame sentinel",
          txm_specimen_key("nonsense") is None)

    print(f"\n{'=' * 60}\n{len(FAILED)} failed")
    for f in FAILED:
        print(f"  - {f}")
    return 1 if FAILED else 0


def rose_guards():
    """The orientation rose is weighted by SEGMENT LENGTH, and says so truthfully.

    Orientation was area-weighted per component until 2026-09-26, which made it a
    width-weighted rose over a per-component second-moment axis: one short wide crack
    outvoted a long thin one, and for a branched network the component axis is noise. That
    change was deliberate; the old behaviour is not a regression to restore.

    WHAT THE OLD GUARD DID: it read orientation_hist_deg["weighted_by"] == "segment length"
    and asserted max(area_share) > 0.5.

    WHAT DEFEATED IT, twice over.
      (1) THE DECLARATION WAS THE TEST'S OWN DEFAULT. measure.py builds that field as
          segsum.get("rose_weighted_by", "segment length"), so the audit deleted the real
          declaration from segments.py's summary and measure.py handed the literal straight
          back. The guard was reading a hardcoded string, not a statement about the rose.
      (2) THE INEQUALITY WAS FORCED BY THE FIXTURE. The frame held one horizontal bar, so
          every segment landed in the 0-15 deg bin and the top share was 1.0 whatever the
          weights were. The audit changed np.histogram(..., weights=L) to an UNWEIGHTED
          count histogram -- the rose no longer weighted by length at all -- and
          max(share) > 0.5 still held.

    WHAT THIS ASSERTS NOW. Two fixtures, both with segments in two different bins, and the
    declaration read from segments.py's own dict (which measure.py forwards wholesale under
    "segments") rather than from the defaulted copy:

      THIN: a 1-px horizontal line 300 px long and a 1-px vertical line 100 px long. The
      polylines through those pixel centres are 299 and 99 px, so the length shares are
      299/398 = 0.7513 and 99/398 = 0.2487 -- hand-computed from the construction, exact at
      four places, and nothing else produces them. An unweighted count histogram would give
      0.5/0.5 on this frame, which is how the audit's mutation is now caught.

      THICK: the same 300 px horizontal line, and the vertical line thickened to 9 px so its
      AREA is 900 against the horizontal's 300 while its centreline is unchanged. Length
      weighting keeps the horizontal bin above 0.6; the area weighting this rose replaced
      would put it at 300/1200 = 0.25. The two fixtures together separate length weighting
      from count weighting and from area weighting, which no single fixture here does.
    """
    thin = np.zeros((400, 400), bool)
    thin[50, 40:340] = True             # horizontal, 300 px -> 299 px of polyline
    thin[150:250, 200] = True           # vertical,   100 px ->  99 px of polyline
    _, ts = measure_frame(thin, "rose_thin", "sem")
    r = ts["orientation_hist_deg"]

    # The declaration, read from the producer rather than from measure.py's fallback.
    check("the rose declares its weighting in segments.py, not via measure.py's default",
          "rose_weighted_by" in ts["segments"]
          and ts["segments"]["rose_weighted_by"] == "segment length"
          and r is not None and r["weighted_by"] == "segment length",
          f"segments={ts['segments'].get('rose_weighted_by')!r} "
          f"forwarded={r and r['weighted_by']!r}")
    check("the rose bins are the twelve 15 deg bins from 0",
          r is not None and r["bin_deg"] == list(range(0, 180, 15)),
          f"{r and r['bin_deg']}")

    hand = [0.0] * 12
    hand[0] = round(299 / 398, 4)       # the horizontal line, bin [0, 15)
    hand[6] = round(99 / 398, 4)        # the vertical line,   bin [90, 105)
    check("the rose IS the length-weighted histogram: shares equal 299/398 and 99/398",
          r is not None and r["area_share"] == hand,
          f"got {r and r['area_share']}; hand {hand}; a count histogram would give "
          f"0.5/0.5")

    thick = np.zeros((400, 400), bool)
    thick[50, 40:340] = True            # horizontal, area 300
    thick[150:250, 196:205] = True      # vertical, 9 px wide: area 900, same centreline
    _, ks = measure_frame(thick, "rose_thick", "sem")
    k = ks["orientation_hist_deg"]
    check("tripling the vertical crack's AREA does not move the rose: it is not area-weighted",
          k is not None and k["area_share"][0] > 0.6,
          f"horizontal share {k and k['area_share'][0]} (length weighting keeps this "
          f"~0.76; area weighting would give 300/1200 = 0.25)")


def iso643_guard(s):
    """P20 applies the ISO 643 planimetric edge rule: an edge region counts as half a region.

    WHAT THE OLD GUARD DID: asserted that the substring "n_edge/2" appears in
    s["p20_edge_rule"], a string literal measure.py sets on the next line.

    WHAT DEFEATED IT: the audit changed the arithmetic from
        (n_int + n_edge / 2.0) / area_mm2   ->   (n_int + n_edge) / area_mm2
    so every border-touching region was counted whole. The label still said "n_edge/2", so
    the guard passed while P20 was overstated -- by 25% on this fixture, and by much more on
    the real corpus, where 25% of TXM regions touch an edge. A name is not a value.

    WHAT THIS ASSERTS NOW: the value, on a fixture whose composition is fixed by
    construction -- three wholly interior regions and two touching the frame edge. The
    expected numerator is 3 + 2/2 = 4.0, and both wrong rules are named in the failure
    detail: 5.0 if edge regions are counted whole, 3.0 if they are dropped. The area is
    hand-computed from the frame's own stated scale (see the module docstring on why the
    constant itself is pinned in tests/test_scale.py, not here). The label check is KEPT --
    a correct number under a missing or wrong definition is still a defect -- it is just no
    longer the only thing asserted.
    """
    check("the fixture is 5 regions, 3 interior and 2 edge-touching, as built",
          s["n_cracks_measured"] == 5 and s["n_censored"] == 2,
          f"measured {s['n_cracks_measured']}, censored {s['n_censored']}")
    um_px = s["nm_per_px"] / 1000.0
    area_mm2 = s["height_px"] * s["width_px"] * (um_px / 1000.0) ** 2
    hand = round((3 + 2 / 2.0) / area_mm2, 2)
    whole = round((3 + 2) / area_mm2, 2)
    dropped = round(3 / area_mm2, 2)
    check("P20 halves the edge regions: its numerator is 3 + 2/2, not 3 + 2 and not 3",
          s["p20_per_mm2"] == hand,
          f"p20_per_mm2={s['p20_per_mm2']}, hand {hand} "
          f"(counting edges whole would be {whole}, dropping them {dropped})")
    check("the ISO 643 edge rule is named in the output, not just applied",
          "n_edge/2" in str(s.get("p20_edge_rule", "")))


#: Path-roughness vocabulary. Tortuosity and R_L are the two this project actually shipped
#: and withdrew; sinuosity and waviness are the names the same quantity travels under in the
#: fracture literature, so a reintroduction under one of those would be the same defect. The
#: R_L pattern matches it as a whole underscore-delimited token in any case -- "R_L",
#: "median_RL", "r_l_px" -- because the old guard's str.startswith("R_L") missed every one
#: of those that was not at the front of the name.
_ROUGHNESS = re.compile(r"tortuosity|sinuosity|waviness|path_?roughness"
                        r"|(?:^|_)r_?l(?:_|$)")


def _nested_keys(obj, prefix=""):
    """Every dict key anywhere in the summary, as a dotted path. Descends lists too."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield (f"{prefix}.{k}" if prefix else str(k)), str(k)
            yield from _nested_keys(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _nested_keys(v, f"{prefix}[{i}]")


def no_path_roughness_guard(s):
    """No path-roughness field reaches the frame summary: not tortuosity, not R_L.

    Tortuosity's 2-endpoint/0-branch gate described 2.6% of the crack area here and 0 of 285
    TXM regions; R_L replaced it and then left too, because it needs a declared axis and
    this app has nowhere to declare one -- an unconfigured axis made R_L the identity
    (length/chord)*sec(0) on all 356 frames. See analysis/segments.py and
    conclusions.REFUSALS. Nothing is emitted in their place: an em-dash in a metric row
    reads as "measured, empty".

    WHAT THE OLD GUARD DID: `[k for k in s if "tortuosity" in k.lower() or
    k.startswith("R_L")]` -- a single pass over the summary's OWN top-level keys.

    WHAT DEFEATED IT: measure.py forwards segments.py's entire summary dict under one key,
    s["segments"], precisely so that a new field there reaches the dataset without a second
    edit. The audit added "tortuosity_median" to segments.py's summary; it arrived in every
    frame record and in every CSV built from one, and the guard never looked inside. A
    second mutation added "median_R_L" at the top level, which the anchored
    startswith("R_L") also missed.

    WHAT THIS ASSERTS NOW: the same prohibition over EVERY key at every depth of the record,
    including the forwarded "segments" and "probe" dicts, matched against the vocabulary the
    quantity travels under and with R_L matched as a token anywhere in a name. Scope is
    still the frame summary only: per-crack rows carry Tortuosity deliberately, gated and
    NaN where undefined, and that is the field this prohibition is the frame-level
    counterpart of.
    """
    hits = sorted({path for path, key in _nested_keys(s) if _ROUGHNESS.search(key.lower())})
    check("no path-roughness field anywhere in the frame summary: not tortuosity, not R_L",
          not hits, f"{hits}" if hits else
          f"scanned {len(list(_nested_keys(s)))} keys at every depth, "
          f"including segments.* and probe.*")


if __name__ == "__main__":
    sys.exit(main())
