#!/usr/bin/env python3
"""Per-crack and per-frame measurement of a black-and-white crack mask.

The per-region shape code is IMPORTED from the SEM repo
(interior_active_learning/code/extended_features.crack_shape_measurements), never copied. A
second implementation of the same metrics is a silent mismatch with every number that repo
has published, and that function carries fixes that are not obvious: mean width is
area/skeleton LENGTH rather than area/pixel count (the count overstates a diagonal crack's
width by up to sqrt(2)), and max width reads the distance transform on the skeleton from the
same crop the skeleton was built on -- a shape mismatch there once made max width fall back
to sqrt(area) for every region ever measured.

WHAT THIS FILE ADDS is the frame level, and three guards that each already cost this project
a wrong number:

  A COUNT IS NOT A MASS. 305 components read as a fragmented network until the largest was
  found to hold 97.45% of the area. So every frame reports largest_share_of_area beside
  n_cracks, and a count is never reported alone.

  LENGTH IS CENSORED AT THE FRAME EDGE. A crack running out of view is longer than measured.
  Regions touching the border are counted and their length is flagged, so a length
  distribution can be read without pretending the tail is complete.

  NO PHYSICAL UNITS WITHOUT SCALE. Pixel columns are always present; micrometre columns
  appear only when nm/px is established for that frame, and are None otherwise. The older
  SEM corpus spans a 249x magnification range, so pooling um across unknown scales is
  meaningless.

Tortuosity is left NaN unless the region has exactly 2 skeleton endpoints and no branch
points, which is the only topology for which path/chord is defined. Reporting a number for a
branched network would invent one.
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from skimage import measure as skmeasure

Image.MAX_IMAGE_PIXELS = None
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)

# The shared implementation, resolved live-repo-first. It is NOT imported from a fixed path
# any more: a downloadable app has no sibling checkout to import from, and hardcoding one
# would make the app fail to measure a mask the user dropped on it. shared_impl keeps the
# "one implementation" rule by preferring the repo whenever there is one and reporting which
# copy answered.
from shared_impl import crack_shape_measurements, skeleton_stats   # noqa: E402
import cleaning                                          # noqa: E402
import geodesic                                          # noqa: E402
from probes import line_probe                            # noqa: E402
from segments import skeleton_segments                   # noqa: E402
from scale import nm_per_px                               # noqa: E402

#: The resolution floor, re-exported from cleaning so there is one definition. The
#: threshold actually applied is per frame -- max(this, the physical floor) -- and is
#: reported on every record as speck_threshold_px with the floor that bound.
SPECK_PX = cleaning.SPECK_PX_FALLBACK


def load_mask(path, with_grey=False):
    """A BW mask, crack = BLACK. Returns a boolean array, True where crack.

    with_grey also returns the 8-bit image, which the ingest assertion needs: once it is a
    boolean there is no way to tell a two-valued mask from a greyscale image that was
    thresholded at 128, and those are not the same input.
    """
    a = np.array(Image.open(path).convert("L"))
    m = a < 128
    return (m, a) if with_grey else m


def measure_frame(mask, stem, modality="sem", grey=None):
    """Per-crack rows plus a frame summary. mask: bool array, True = crack."""
    lab = skmeasure.label(mask, connectivity=cleaning.CONNECTIVITY)
    n = int(lab.max())
    nm = nm_per_px(stem, modality)
    px_um = (nm / 1000.0) if nm else None       # um per pixel
    speck_px, speck_info = cleaning.speck_threshold_px(nm)

    rows, specks = [], 0
    H, W = mask.shape
    for p in skmeasure.regionprops(lab):
        if p.area <= speck_px:
            specks += 1
            continue
        y0, x0, y1, x1 = p.bbox
        sub = lab[y0:y1, x0:x1] == p.label
        d = crack_shape_measurements(sub)
        # THE LONGEST SINGLE CRACK, which SkeletonLength_px is not for a branched region:
        # that one is summed over the skeleton's adjacency edges, so it is the whole
        # network's centreline. Both columns are emitted; see analysis/geodesic.py. The
        # UNROUNDED skel_len is what the graph is checked against -- d["SkeletonLength_px"]
        # is rounded to 2 dp, and comparing against it would make the tie a no-op.
        # This does not skeletonize twice: shared_impl memoizes the call that
        # crack_shape_measurements just made on the same region.
        skel_len, _bp, _ep, skel, _loc, _spx = skeleton_stats(sub)
        geo, geo_info = geodesic.longest_tip_geodesic(skel, skel_len)
        touches = bool(y0 == 0 or x0 == 0 or y1 >= H or x1 >= W)
        r = {
            "crack_id": int(p.label),
            "area_px": int(p.area),
            "centroid_x_px": round(float(p.centroid[1]), 1),
            "centroid_y_px": round(float(p.centroid[0]), 1),
            "touches_frame_edge": touches,
            "length_is_censored": touches,
        }
        for k, v in d.items():
            r[k] = (None if (isinstance(v, float) and not np.isfinite(v)) else v)
        r["TipToTipGeodesic_px"] = (round(float(geo), 2) if geo is not None else None)
        # None is not an absence here, it is a stated topology: a closed loop has no tip
        # for a tip-to-tip path to start at. Carried so a reader can see which regions the
        # max could not consider rather than inferring it from a blank.
        r["geodesic_undefined_reason"] = geo_info.get("reason")
        # TWO DIFFERENT CAVEATS, kept apart because one number cannot carry both.
        # has_cycles: the region's skeleton loops, so the tip-to-tip route is the shorter
        # way round and sits below the longest simple path through it. A property of the
        # definition; on a tree it is False and the value is exact -- checked on 1078 of
        # 1078 tree regions against the brute-force all-pixel diameter.
        r["geodesic_has_cycles"] = (None if geo is None
                                    else bool(geo_info.get("n_cycles")))
        # method: HOW it was computed. Only "sampled_sources_lower_bound" can sit below
        # the true tip-to-tip maximum, and it exists because the largest region here has a
        # 1.25M px skeleton that an all-pairs sweep cannot finish.
        r["geodesic_method"] = geo_info.get("method")
        if px_um:
            r["area_um2"] = round(p.area * px_um * px_um, 4)
            for src, dst in (("SkeletonLength_px", "network_length_um"),
                             ("TipToTipGeodesic_px", "longest_crack_um"),
                             ("MeanWidth_px", "mean_width_um"),
                             ("MaxWidth_px", "max_width_um")):
                v = r.get(src)
                r[dst] = (round(float(v) * px_um, 4)
                          if isinstance(v, (int, float)) and np.isfinite(v) else None)
        rows.append(r)

    total_px = int(mask.sum())
    areas = np.array([r["area_px"] for r in rows], float) if rows else np.zeros(0)
    lengths = np.array([r.get("SkeletonLength_px") or 0.0 for r in rows], float)
    widths = np.array([r["MeanWidth_px"] for r in rows if isinstance(r.get("MeanWidth_px"), (int, float))], float)
    torts = np.array([r["Tortuosity"] for r in rows if isinstance(r.get("Tortuosity"), (int, float))], float)
    oris = np.array([r["Orientation_deg"] for r in rows if isinstance(r.get("Orientation_deg"), (int, float))], float)
    branches = np.array([r.get("BranchPointCount") or 0 for r in rows], float)
    # NaN where the region has no tip-to-tip path at all, so a max() skips it rather than
    # treating "no crack here" as a crack of length zero.
    geos = np.array([(r.get("TipToTipGeodesic_px") if r.get("TipToTipGeodesic_px")
                      is not None else np.nan) for r in rows], float)

    # Directional line-intercept sampling and branch-level geometry. Both are computed on
    # the WHOLE frame mask rather than per region: P10 is a property of a test line crossing
    # the field, and a segment rose weighted per-component would re-introduce the
    # component-level weighting these replace.
    probe = line_probe(mask, nm)
    segs, segsum = skeleton_segments(mask)

    _cen = sum(1 for r in rows if r["length_is_censored"])
    summary = {
        "frame": stem,
        "modality": modality,
        "height_px": int(H), "width_px": int(W),
        "megapixels": round(mask.size / 1e6, 3),
        "nm_per_px": nm,
        "scale_known": nm is not None,

        "n_regions_total": n,
        "n_cracks_measured": len(rows),
        "speck_count": specks,
        # The value that was actually applied to THIS frame, not the constant. Reporting the
        # constant beside a per-frame threshold is a number attached to the wrong object.
        "speck_threshold_px": speck_px,

        "crack_area_px": total_px,
        "area_fraction": round(float(mask.mean()), 6),
        # A COUNT IS NOT A MASS.
        "largest_area_px": int(areas.max()) if len(areas) else 0,
        "largest_share_of_area": round(float(areas.max() / areas.sum()), 4) if areas.sum() else None,
        "top1pct_share_of_area": _top_share(areas, 0.01),

        # HOW THE GEODESICS ON THIS FRAME WERE ARRIVED AT. Unconditional, next to the
        # other region counts, and NOT inside the micrometre block below -- these describe
        # regions, not units. Both of them lived in that block for one run, and the effect
        # was that the counter for "regions measured approximately" was absent from all 127
        # unscaled frames, which are the only frames the approximation has ever fired on.
        # A diagnostic that is missing exactly where it would trigger reads as a clean zero.
        #
        # undefined: a closed loop has no tip, so it has no tip-to-tip path. Reported
        # rather than left as a silent omission from a max().
        "n_regions_geodesic_undefined": int(np.isnan(geos).sum()),
        # sampled: too large for an exact sweep, so a lower bound. Zero on almost every
        # frame; not zero is a thing the reader should see.
        "n_regions_geodesic_sampled": sum(
            1 for r in rows if r.get("geodesic_method") == "sampled_sources_lower_bound"),

        "total_skeleton_length_px": round(float(lengths.sum()), 1),
        # length per unit area -- the standard crack-density form
        "crack_density_px_per_Mpx": round(float(lengths.sum()) / (mask.size / 1e6), 1),
        # The skeleton's own P21 in pixel units, so it can be compared against the Buffon
        # estimator on EVERY frame rather than only on the scaled ones. Same quantity as
        # p21_skeleton_mm_per_mm2 below, before the unit conversion.
        "p21_skeleton_per_px": round(float(lengths.sum()) / mask.size, 10),

        "n_censored": int(sum(1 for r in rows if r["length_is_censored"])),
        # THREE WEIGHTINGS, because the count one is the least relevant and was the only one
        # reported. A count share sits next to MCL and TCL and understates what it is
        # warning about: measured over the whole corpus, the median frame is 4.2% of
        # REGIONS censored but 22.1% of crack AREA and 16.6% of crack LENGTH; on TXM it is
        # 25.0% of regions against 71.0% of area. Printing "4% censored" beside a length
        # statistic invites the reader to ignore it.
        #
        # censored_share is kept as the count share so nothing that already reads it
        # changes meaning, but the length-weighted one is what belongs next to MCL/TCL and
        # the area-weighted one next to area fraction.
        "censored_share": round(_cen / len(rows), 4) if rows else None,
        "censored_share_weighting": "regions (count). See the area- and length-weighted "
                                    "shares, which are several times larger.",
        "censored_share_by_area": (round(sum(r["area_px"] for r in rows
                                             if r["length_is_censored"]) /
                                         max(1, sum(r["area_px"] for r in rows)), 4)
                                   if rows else None),
        "censored_share_by_length": (round(sum((r.get("SkeletonLength_px") or 0.0) for r in rows
                                               if r["length_is_censored"]) /
                                           max(1e-9, sum((r.get("SkeletonLength_px") or 0.0)
                                                         for r in rows)), 4)
                                     if rows else None),

        # Cleaning step 1: is this actually a two-valued crack mask, and is crack the
        # minority phase? Recorded, never acted on -- an inverted mask still measures, it
        # just says so, because the number it produces is otherwise perfectly plausible.
        "ingest": (cleaning.ingest_assertion(grey, mask) if grey is not None else None),
        # Step 3: which floor bound, and what it means physically on THIS frame.
        "speck_threshold": speck_info,
        # Step 2: what this frame could not have seen.
        "detection_limit": cleaning.detection_limit(nm, speck_px),
        # The operations deliberately not applied, so a CSV reader does not have to assume.
        "cleaning_not_applied": sorted(cleaning.NOT_SHIPPED),

        "mean_width_px_median": _med(widths),
        # DiameterJ's D_SP = Area/Length is validated only for features >= 10 px across.
        # 84.9% of the regions here are thinner than that, so the median ships with the
        # share of regions outside the envelope rather than as a bare number.
        "width_below_validated_envelope_share":
            (round(float((widths < 10).mean()), 4) if len(widths) else None),

        # NO PATH-ROUGHNESS FIELD. Tortuosity left because its 2-endpoint/0-branch gate
        # described 2.6% of the crack area here and 0 of 285 TXM regions; R_L replaced it
        # and then left too, because it needs a declared axis and this app has nowhere to
        # declare one -- see analysis/segments.py and conclusions.REFUSALS. Nothing is
        # emitted in their place: an em-dash in a metric row reads as "measured, empty".

        "n_segments": segsum.get("n_segments"),
        "n_junctions": segsum.get("n_junctions"),
        "n_triple": segsum.get("n_triple"),
        "n_quadruple_plus": segsum.get("n_quadruple_plus"),
        # The unit travels with the numbers. Without it a reader has no way to know these
        # are clusters rather than skeleton pixels -- which is exactly how the previous
        # version printed 3,074 junctions beside 15,515 "triple and quad" and looked wrong.
        "junction_order_counted_per": segsum.get("junction_order_counted_per"),
        "characteristic_length_px": segsum.get("characteristic_length_px"),

        # Length-weighted, per segment. The old rose was area-weighted per component, which
        # is a width-weighted rose over a meaningless per-component axis.
        "orientation_hist_deg": {
            "bin_deg": segsum.get("rose_bin_deg"),
            "area_share": segsum.get("rose_length_share"),
            "weighted_by": segsum.get("rose_weighted_by", "segment length"),
        } if segsum.get("rose_length_share") else None,

        # Pij-labelled densities. "Crack density" unqualified is six incompatible
        # quantities (Dershowitz & Herda 1992); each here carries its subscript and unit.
        "probe": probe,

        # THE WHOLE SEGMENT SUMMARY, stored wholesale like `probe` above.
        #
        # The named keys above forward nine of the twenty-four fields segments.py computes,
        # and the other fifteen were being calculated on every frame of every run and
        # thrown away -- including the anisotropy null added minutes before this, which
        # unit-tested green against skeleton_segments and then landed on 0 of 358 frames
        # because nothing carried it across. The same gap had already silently dropped two
        # diagnostics whose own comments in segments.py describe them as reported: the
        # share of skeleton length the directional gate kept, and the lattice-locked share.
        #
        # Forwarding the dict rather than adding four more named keys is the point: a new
        # field in segments.py now reaches the dataset without a second edit here, so there
        # is no second place to forget.
        "segments": segsum,

        # The anisotropy verdict ALSO at the top level, because that is where the read-out
        # and the figure field list look for it, and a nested-only field is one more place
        # to forget. rose_beats_null is the only one of the three safe to read alone: R
        # without its null means nothing on this corpus, where uniform random angles return
        # R = 0.16-0.29 against a corpus median of 0.257.
        "rose_R": segsum.get("rose_R"),
        "rose_R_null95": segsum.get("rose_R_null95"),
        "rose_theta_deg": segsum.get("rose_theta_deg"),
        "rose_beats_null": segsum.get("rose_beats_null"),
        "rose_null": segsum.get("rose_null"),
    }
    if nm:
        um_px = nm / 1000.0
        area_mm2 = mask.size * (um_px / 1000.0) ** 2
        summary["area_analysed_mm2"] = round(area_mm2, 6)
        # P21: crack length per unit area, mm/mm^2, from the skeleton.
        summary["p21_skeleton_mm_per_mm2"] = round(
            float(lengths.sum()) * (um_px / 1000.0) / area_mm2, 4) if area_mm2 else None
        # P20: regions per unit area, with the ISO 643 planimetric edge rule -- an edge
        # region is half a region, because half of it is outside the field.
        n_edge = sum(1 for r in rows if r["length_is_censored"])
        n_int = len(rows) - n_edge
        summary["p20_per_mm2"] = round((n_int + n_edge / 2.0) / area_mm2, 2) if area_mm2 else None
        summary["p20_edge_rule"] = "ISO 643 planimetric: n_interior + n_edge/2"
        # MCL: the longest single crack, tip to tip. Design-relevant in a way the mean is
        # not, and NOT max(SkeletonLength_px), which is what this used to be.
        #
        # SkeletonLength_px is summed over the skeleton's adjacency edges, so for a
        # branched region it is the whole network's centreline -- every arm and spur added
        # together. Taking its max and labelling it "longest crack" put a network size
        # under a name the reader compares with Varestraint/hot-cracking MCL, which is one
        # crack. Measured before the change: the region setting it had a median 594 branch
        # points, and the result exceeded the short side of the field on 89 of 143 scaled
        # frames -- 4893.9 um inside a 107.9 um field at worst. Both quantities are
        # reported now, each under its own name.
        #
        # Step 8, the length half: reported BOTH with and without edge-censored regions,
        # because the two bracket the truth from opposite sides and neither is it. Keeping
        # them biases MCL down -- a crack leaving the frame is longer than the part seen.
        # Dropping them biases it up by removing exactly the long cracks, since a longer
        # crack is likelier to reach an edge. Here 72-74% of crack area is in
        # border-touching regions, so the gap is not a rounding detail.
        summary.update(_bracket("mcl", geos, rows, um_px))
        summary["mcl_definition"] = (
            "longest tip-to-tip geodesic on one region's skeleton: over all pairs of "
            "skeleton tips, the shortest path between them, maximised. Equals the region's "
            "whole centreline exactly when the skeleton is unbranched; on a tree it is the "
            "longest simple path. NOT max(SkeletonLength_px) -- see "
            "largest_network_centreline_um for that.")
        summary["mcl_bracket_note"] = (
            "keeping censored regions biases MCL down (a crack leaving the frame is longer "
            "than measured); dropping them biases it up (long cracks reach edges more "
            "often). The pair brackets; neither is the value.")
        _arg = (int(np.nanargmax(geos)) if np.isfinite(geos).any() else None)
        # Whether the MCL-setting region has cycles, and how its value was computed.
        summary["mcl_has_cycles"] = (bool(rows[_arg].get("geodesic_has_cycles"))
                                     if _arg is not None else None)
        summary["mcl_method"] = (rows[_arg].get("geodesic_method")
                                 if _arg is not None else None)
        # What fraction of its own region's network the longest crack actually is. This is
        # the gap between the two columns, on the one region where it matters most; near
        # 1.0 means the region is essentially one unbranched crack.
        _net = (rows[_arg].get("SkeletonLength_px") or 0.0) if _arg is not None else 0.0
        summary["mcl_share_of_its_network"] = (round(float(geos[_arg]) / _net, 4)
                                               if _arg is not None and _net else None)

        # The network quantity, under its own name. Same censored/uncensored bracket, for
        # the same reason -- a network leaving the frame is bigger than the part seen.
        summary.update(_bracket("largest_network_centreline",
                                np.array([r.get("SkeletonLength_px") or 0.0
                                          for r in rows], float), rows, um_px))
        summary["largest_network_centreline_definition"] = (
            "max over regions of SkeletonLength_px: the TOTAL centreline length of one "
            "connected crack network, summed over every branch. A network size, not a "
            "crack length; do not compare it with a Varestraint MCL.")
        summary["tcl_um"] = round(float(lengths.sum()) * um_px, 2)
    if px_um:
        summary["crack_area_um2"] = round(total_px * px_um * px_um, 2)
        summary["total_length_um"] = round(float(lengths.sum()) * px_um, 2)
        summary["field_width_um"] = round(W * px_um, 2)
    return rows, summary


def _bracket(key, vals, rows, um_px):
    """{key}_um, {key}_um_uncensored_only, {key}_censored -- one bracket, one definition.

    Written once because MCL and the network length need exactly the same three fields
    computed exactly the same way, and two copies of an argmax-then-read-the-flag are two
    chances for the flag to end up read off a different region from the value.
    """
    out = {f"{key}_um": None, f"{key}_um_uncensored_only": None, f"{key}_censored": None}
    if not len(vals) or not np.isfinite(vals).any():
        return out
    i = int(np.nanargmax(vals))
    out[f"{key}_um"] = round(float(vals[i]) * um_px, 2)
    out[f"{key}_censored"] = bool(rows[i]["length_is_censored"])
    unc = np.where(np.array([r["length_is_censored"] for r in rows], bool), np.nan, vals)
    if np.isfinite(unc).any():
        out[f"{key}_um_uncensored_only"] = round(float(np.nanmax(unc)) * um_px, 2)
    return out


def _med(a):
    return round(float(np.median(a)), 4) if len(a) else None


def _top_share(areas, frac):
    if not len(areas):
        return None
    k = max(1, int(round(len(areas) * frac)))
    return round(float(np.sort(areas)[::-1][:k].sum() / areas.sum()), 4)


def _rose(oris, areas, rows):
    """Orientation histogram in 12 bins of 15 deg, weighted by AREA not by count.

    Count-weighting lets a thousand specks outvote the one crack that holds the area -- the
    same failure as reporting n_cracks alone. Bins are 0-180: a crack has an axis, not a
    direction, so 10 deg and 190 deg are the same orientation.
    """
    if not len(oris):
        return None
    w = np.array([r["area_px"] for r in rows
                  if isinstance(r.get("Orientation_deg"), (int, float))], float)
    o = np.mod(oris, 180.0)
    hist, edges = np.histogram(o, bins=12, range=(0, 180), weights=w)
    tot = hist.sum()
    return {"bin_deg": [int(e) for e in edges[:-1]],
            "area_share": [round(float(h / tot), 4) for h in hist] if tot else None,
            "weighted_by": "area"}


#: Suffixes stripped to get a frame's identity. A mask exported by this project is named
#: <frame>_gated.png, so the suffix is packaging, not identity.
MASK_SUFFIXES = ("_crack_mask", "_gated", "_machine", "_mask")


def canonical_stem(name):
    """The frame name for a mask file. ONE definition, exported, because there were two.

    The upload endpoint derived a stem from the filename and used it for the saved file and
    the crack rows, while measure_path stripped the suffix and used the shorter name for the
    frame record. Uploading demo_gated.png -- the shape this project's own export produces,
    so the likeliest file a user has -- stored a frame called "demo" whose crack rows were
    keyed "demo_gated" and whose mask was written to demo_gated_gated.png. The Cracks tab
    returned 0 of its own rows and the Mask tab 404'd, while the read-out worked, so the
    frame looked measured.

    Longest suffix first: "_crack_mask" also ends with "_mask", and stripping the shorter
    one leaves "_crack" behind.

        IT MUST BE IDEMPOTENT, because it is applied twice: the upload endpoint canonicalises
    the filename to name the saved file, then measure_path canonicalises again to name the
    frame. Stripping only one suffix per call made those two disagree for a double-suffixed
    name -- "_smoke_mask_gated" became "_smoke_mask" at the endpoint and "_smoke" in the
    record, so the crack rows and the mask file were unreachable exactly as before. Caught
    by the release smoke check on its first run after it was taught to measure.
    """
    stem = os.path.splitext(os.path.basename(name))[0]
    while True:
        for suf in MASK_SUFFIXES:
            if stem.endswith(suf) and len(stem) > len(suf):
                stem = stem[: -len(suf)]
                break
        else:
            return stem


def measure_path(path, modality="sem", stem=None):
    stem = canonical_stem(stem or path)
    mask, grey = load_mask(path, with_grey=True)
    return measure_frame(mask, stem, modality, grey=grey)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: measure.py <mask.png> [sem|txm]")
    rows, summ = measure_path(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "sem")
    print(json.dumps(summ, indent=2))
    print(f"\n{len(rows)} cracks measured")
    for r in sorted(rows, key=lambda r: -r["area_px"])[:5]:
        print(f"  id {r['crack_id']:>5}  area {r['area_px']:>9,} px  "
              f"longest {r.get('TipToTipGeodesic_px')}  network {r.get('SkeletonLength_px')}  "
              f"meanW {r.get('MeanWidth_px')}  "
              f"tort {r.get('Tortuosity')}  censored {r['length_is_censored']}")
