#!/usr/bin/env python3
"""Figure 4: what is measured on a detected crack, drawn on one real crack.

WHY. The paper reports an area fraction, a length and a width, and until now defined all
three in prose only. A reader cannot check a width without being told where it is
measured from, and three of this project's own mistakes were definitional rather than
numerical: a "length" that was a pixel count, a "tortuosity" that came out below one
because of it, and a "width" that silently meant two different things in two sections.
This figure puts every measurand on one crack with the rule beside it.

THE CRACK IS THE ONE FIGURES 1 AND 3 ALREADY SHOW -- the largest marked region the SEM
frame contains -- so a reader arriving here has already seen it twice in context.

EVERY NUMBER COMES FROM THE SHIPPED MEASUREMENT CODE, not from a reimplementation in this
script. `analysis/_vendor/extended_features.crack_shape_measurements` and
`analysis/geodesic.longest_tip_geodesic` are the functions the application calls, and they
are called here on the same region that is drawn. A first version of this figure
recomputed the same five quantities from scratch and disagreed with the software by 10 to
20% on three of them -- not because either was wrong, but because they averaged over
different point sets: a width along the longest route is not a width over the whole
skeleton. A methods figure that defines a measurand differently from the code is worse
than no methods figure.

TWO LENGTHS, BECAUSE THE SOFTWARE REPORTS TWO. The network length sums every branch of the
medial axis; the longest crack is the longest tip-to-tip route through it. They are not
interchangeable and on this region they differ by 15%. Both are summed step lengths, with
a diagonal step counted as sqrt(2): a pixel count understates length by up to 41% and,
divided by an endpoint distance, once gave 819 of 1,503 exported cracks a tortuosity below
one, which is geometrically impossible.

TORTUOSITY IS BLANK HERE, AND THAT IS THE MEASUREMENT. The shipped definition applies only
to an unbranched skeleton -- two endpoints, no branch points -- and this region has nine
branch points, so the software emits no value for it. The figure says so rather than
substituting a number of its own. The caption carries the digitisation floor, measured by
rasterising a straight line of the same chord and running it through the same code, so that
where a tortuosity IS reported a reader knows it is read against about 1.08 and not 1.

    <sem-crack-detector>/.venv/bin/python -B paper/figures/mk_measurands.py
"""
import json
import os
import sys
import warnings
from heapq import heappop, heappush

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths                                       # noqa: E402

sys.path.insert(0, _paths.ANALYSIS)
sys.dont_write_bytecode = True

import numpy as np                                  # noqa: E402
import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.patches import Circle, Rectangle    # noqa: E402
from scipy import ndimage as ndi                    # noqa: E402
from skimage import draw, exposure, morphology as morph  # noqa: E402

sys.path.insert(0, os.path.join(_paths.ANALYSIS, "_vendor"))
import extended_features as EF                      # noqa: E402  -- the shipped measurands
import geodesic                                     # noqa: E402  -- the shipped longest route
import both_modalities as BM                        # noqa: E402
import journal_style as J                           # noqa: E402
from scalebar import scalebar                       # noqa: E402

J.use()
OUT = _paths.FIG_DIR
NAME = "F4 - what is measured"
PAD = 40                       # pixels of context around the region's bounding box


def largest_interior(final):
    lab, _ = ndi.label(final, np.ones((3, 3), bool))
    sz = np.bincount(lab.ravel())
    sz[0] = 0
    for b in set(np.unique(np.concatenate(
            [lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}:
        sz[b] = 0
    return lab == int(sz.argmax())


def axis_path(skel):
    """The longest tip-to-tip route along the medial axis, for DRAWING it.

    Dijkstra over the 8-connected axis with step weights 1 and sqrt(2), from one extremity
    to the far one and back to recover the route. The LENGTH is not taken from here -- the
    shipped `geodesic.longest_tip_geodesic` owns that -- but this path's own length is
    checked against it, so the route drawn is the route measured.
    """
    pts = np.argwhere(skel)
    if len(pts) < 2:
        raise SystemExit("the medial axis has fewer than two pixels")
    index = {tuple(q): i for i, q in enumerate(pts)}
    nbrs = [[] for _ in pts]
    for (y, x), i in index.items():
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == dx == 0:
                    continue
                j = index.get((y + dy, x + dx))
                if j is not None:
                    nbrs[i].append((j, float(np.hypot(dy, dx))))

    def dijkstra(src):
        dist = np.full(len(pts), np.inf)
        prev = np.full(len(pts), -1)
        dist[src] = 0.0
        q = [(0.0, src)]
        while q:
            dd, uu = heappop(q)
            if dd > dist[uu]:
                continue
            for v, w in nbrs[uu]:
                nd = dd + w
                if nd < dist[v]:
                    dist[v], prev[v] = nd, uu
                    heappush(q, (nd, v))
        return dist, prev

    d0, _ = dijkstra(0)
    aa = int(np.nanargmax(np.where(np.isfinite(d0), d0, -1)))
    da, prev = dijkstra(aa)
    bb = int(np.nanargmax(np.where(np.isfinite(da), da, -1)))
    path, k = [], bb
    while k != -1:
        path.append(tuple(pts[k]))
        k = int(prev[k])
    return path[::-1], float(da[bb])


def straight_floor(chord_px, n_angles=46):
    """What a perfectly straight crack of this chord can report, through the same code.

    THE FLOOR IS A RANGE, NOT A NUMBER, and it depends on the crack's ANGLE. A line at
    0, 45 or 90 degrees rasterises to steps that are all axial or all diagonal, and its
    path length equals the distance between its own ends exactly: the floor there is
    1.000. At every intermediate angle the raster is a staircase of mixed steps and the
    summed path is longer than the chord, with no crack waviness involved at all. So the
    control sweeps the angle and reports both ends; quoting one angle's value as "the
    floor" would understate it everywhere else.

    Measured with the shipped `skeleton_stats`, so a reported tortuosity and this floor
    come from the same code.
    """
    L = max(float(chord_px), 8.0)
    out = {}
    for deg in np.linspace(0.0, 90.0, n_angles):
        th = np.radians(deg)
        dy, dx = int(round(L * np.sin(th))), int(round(L * np.cos(th)))
        h, w = abs(dy) + 5, abs(dx) + 5
        line = np.zeros((h, w), bool)
        rr, cc = draw.line(2, 2, 2 + abs(dy), 2 + abs(dx))
        line[rr, cc] = True
        length, _bp, _ep, sk, _loc, npx = EF.skeleton_stats(line)
        if npx < 2:
            continue
        ys, xs = np.where(sk)
        ends = np.hypot(ys.max() - ys.min(), xs.max() - xs.min())
        out[round(float(deg), 1)] = length / max(ends, 1e-9)
    vals = list(out.values())
    return {"min": min(vals), "max": max(vals), "at_angles": out,
            "chord_px": L, "n_angles": len(vals)}


def main():
    d = BM.load("sem")
    nm = float(d["nm_per_px"])
    um = nm / 1000.0
    region_full = largest_interior(d["final"])

    # The shipped measurement, on the region exactly as the application hands it over:
    # cropped to its own bounding box, which is what `_local_crop` inside
    # `skeleton_stats` then re-crops with a 2 px margin.
    ys, xs = np.where(region_full)
    by0, by1, bx0, bx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    bbox = region_full[by0:by1, bx0:bx1]
    shape = EF.crack_shape_measurements(bbox)
    net_len, n_branch, n_end, skel_local, _loc, skel_px = EF.skeleton_stats(bbox)
    geo, geo_info = geodesic.longest_tip_geodesic(skel_local, net_len)

    # the display crop, with context around the region, and the MEASURED skeleton placed
    # back into it: drawing a freshly skeletonised copy would risk showing an axis that is
    # not the one the numbers came from
    y0 = max(by0 - PAD, 0)
    y1 = min(by1 + PAD, region_full.shape[0])
    x0 = max(bx0 - PAD, 0)
    x1 = min(bx1 + PAD, region_full.shape[1])
    sl = (slice(y0, y1), slice(x0, x1))
    region, img = region_full[sl], d["img"][sl]
    sy = (by0 - 2 if by0 >= 2 else 0) - y0          # _local_crop's own margin
    sx = (bx0 - 2 if bx0 >= 2 else 0) - x0
    skel = np.zeros(region.shape, bool)
    skel[sy:sy + skel_local.shape[0], sx:sx + skel_local.shape[1]] = skel_local
    if int(skel.sum()) != skel_px:
        raise SystemExit(f"the measured skeleton does not fit the display crop: "
                         f"{int(skel.sum())} px placed of {skel_px}")

    path, path_len = axis_path(skel)
    if geo is not None and abs(path_len - geo) > 1.0:
        raise SystemExit(
            f"the drawn route is {path_len:.2f} px and the shipped longest tip-to-tip "
            f"geodesic is {geo:.2f} px; the figure would draw a different route from the "
            f"one it reports")
    dt = ndi.distance_transform_edt(region)
    width_px = np.array([2.0 * dt[y, x] for y, x in path])
    (py0, px0), (py1, px1) = path[0], path[-1]
    chord_px = float(np.hypot(py1 - py0, px1 - px0))
    floor = straight_floor(chord_px)

    lo, hi = np.percentile(img, [2, 98])
    grey = exposure.rescale_intensity(img.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0.0, 1.0))
    rgb = np.dstack([grey] * 3)
    rgb[region] = 0.72 * rgb[region] + 0.28 * np.array(J.rgb(J.MASK))

    # the three circles, at the 10th, 50th and 90th percentile of the width along the
    # whole SKELETON -- the population MeanWidth_px averages over -- so the panel shows
    # the spread of the quantity the table reports rather than of a different one
    sk_pts = np.argwhere(skel)
    sk_w = np.array([2.0 * dt[y, x] for y, x in sk_pts])
    order = np.argsort(sk_w)
    picks = [int(order[int(round(q * (len(order) - 1)))]) for q in (0.10, 0.50, 0.90)]
    circles = [(sk_pts[k][0], sk_pts[k][1], sk_w[k] / 2.0) for k in picks]

    W = J.PAGEW
    Mg = 0.03
    GAP = 0.18
    LW = 3.22                                  # the micrograph column
    RW = W - 2 * Mg - LW - GAP
    IMH = LW * region.shape[0] / region.shape[1]
    ROWH = 0.215                               # one definition row
    NROWS = 7
    # +0.12 of slack below the last row: the closing rule is drawn from the row pitch,
    # and without it the rule for a seven-row table lands BELOW the axes and overprints
    # the footnote. The table grew from five rows to seven when the measurands were taken
    # from the shipped code instead of recomputed.
    TABH = 0.26 + NROWS * ROWH + 0.12
    FOOT = 0.06        # no footnote: the colour key and the caveats are in the caption
    Htot = Mg + max(IMH, 1.80) + 0.26 + TABH + FOOT + Mg

    fig = plt.figure(figsize=(W, Htot))

    def ax_at(xin, yin, win, hin):
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    ax = ax_at(Mg, Mg, LW, IMH)
    ax.imshow(rgb, interpolation="nearest")
    J.micrograph(ax)
    ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes, fill=False,
                           edgecolor=J.INK, linewidth=0.7, zorder=40))

    # the WHOLE medial axis, which is what the network length sums over
    ays, axs_ = np.where(skel)
    ax.plot(axs_, ays, ".", color=J.SKELETON, ms=1.1, mew=0, zorder=20)
    # the two tips of the longest route, and the straight chord between them
    ax.plot([px0, px1], [py0, py1], color=J.ROI, lw=1.0, linestyle=(0, (4, 2)),
            zorder=21)
    ax.plot([px0, px1], [py0, py1], "o", ms=3.4, mfc="white", mec=J.ROI, mew=1.0,
            linestyle="none", zorder=22)
    for yy, xx, r in circles:
        ax.add_patch(Circle((xx, yy), r, fill=False, edgecolor=J.ROI, linewidth=1.0,
                            zorder=25))
        ax.plot([xx, xx + r], [yy, yy], color=J.ROI, lw=0.9, zorder=26)
    J.panel_label(ax, "a", inside=True)
    scalebar(ax, nm, region.shape[1], fontsize=J.TICK)

    # --- (b) the width profile -----------------------------------------------------
    PROFH = min(IMH, 1.80)   # fill the row beside the micrograph rather than leaving it empty
    pax = ax_at(Mg + LW + GAP + 0.30, Mg + 0.22, RW - 0.36, PROFH - 0.58)
    s_um = np.concatenate([[0.0], np.cumsum(
        [np.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
         for i in range(len(path) - 1)])]) * um
    pax.plot(s_um, width_px * um, color=J.ACCENT, lw=1.0)
    pax.axhline(shape["MeanWidth_px"] * um, color=J.G_MID, lw=0.8,
                linestyle=(0, (4, 2)), zorder=4)
    pax.set_xlabel("along the longest tip-to-tip route, \u00b5m", fontsize=J.TICK,
                   labelpad=1.5)
    pax.set_ylabel("width, \u00b5m", fontsize=J.TICK, labelpad=1.5)
    pax.tick_params(labelsize=J.TICK)
    pax.set_xlim(0, s_um[-1])
    pax.set_ylim(0, None)
    J.panel_label(pax, "b")

    # --- (c) the definitions, as a three-column table ------------------------------
    tort = shape["Tortuosity"]
    rows = [
        ("Area  A", "marked pixels as a fraction of the field",
         f"{shape['Area_px'] * um * um:.1f} \u00b5m\u00b2 of a "
         f"{d['img'].shape[0] * d['img'].shape[1] * um * um / 1e3:.0f}"
         f" \u00d7 10\u00b3 \u00b5m\u00b2 field"),
        ("Network length", "every branch of the medial axis, summed",
         f"{net_len * um:.1f} \u00b5m over {n_branch} branch points"),
        ("Longest crack", "the longest tip-to-tip route through it",
         f"{geo * um:.1f} \u00b5m" if geo is not None
         else f"not defined: {geo_info.get('reason')}"),
        ("Mean width", "twice the medial-axis radius, over the skeleton",
         f"{shape['MeanWidth_px'] * um:.2f} \u00b5m"),
        ("Max width", "the largest circle that fits inside",
         f"{shape['MaxWidth_px'] * um:.2f} \u00b5m"),
        ("Orientation  \u03b8", "the region's second-moment major axis",
         f"{shape['Orientation_deg']:+.1f}\u00b0 from the image rows"),
        ("Tortuosity  L/C", "length over the chord, for an UNBRANCHED axis",
         f"{tort:.3f}" if isinstance(tort, (int, float))
         else f"no value: the axis has {n_branch} branch points"),
    ]
    ytab = Mg + max(IMH, 1.80) + 0.26
    dax = ax_at(Mg, ytab, W - 2 * Mg, TABH)
    dax.set_axis_off()
    C1, C2 = 0.175, 0.585
    dax.plot([0, 1], [1.0, 1.0], transform=dax.transAxes, color=J.INK, lw=0.8,
             clip_on=False)
    for xx, head in ((0.0, "measurand"), (C1, "how it is measured"),
                     (C2, "on the crack in (a)")):
        dax.text(xx, 0.955, head, fontsize=J.TICK, fontweight="bold", va="top",
                 ha="left", color=J.G_DARK, transform=dax.transAxes)
    hline = 0.955 - 0.26 / TABH + 0.02
    dax.plot([0, 1], [hline, hline], transform=dax.transAxes, color=J.G_MID, lw=0.6,
             clip_on=False)
    for i, (name, rule, val) in enumerate(rows):
        top = hline - 0.035 - i * (ROWH / TABH)
        dax.text(0.0, top, name, fontsize=J.BODY, fontweight="bold", va="top",
                 ha="left", color=J.INK, transform=dax.transAxes)
        dax.text(C1, top, rule, fontsize=J.TICK, va="top", ha="left", color=J.G_DARK,
                 transform=dax.transAxes)
        dax.text(C2, top, val, fontsize=J.TICK, va="top", ha="left", color=J.ACCENT,
                 transform=dax.transAxes)
    if len(rows) != NROWS:
        raise SystemExit(f"the table has {len(rows)} rows and was laid out for {NROWS}")
    dax.plot([0, 1], [hline - 0.035 - len(rows) * (ROWH / TABH) + 0.03] * 2,
             transform=dax.transAxes, color=J.INK, lw=0.8, clip_on=False)
    dax.text(0.0, 1.0 + 0.055 / TABH, "(c)", fontsize=J.PANEL, fontweight="bold",
             va="bottom", ha="left", color=J.INK, transform=dax.transAxes)


    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "every measurand the paper reports, drawn on the largest marked region "
                "the SEM frame contains -- the same region Figures 1 and 3 show",
        "field": str(d["field"]), "nm_per_px": nm,
        "crop": [int(y0), int(x0)], "crop_px": [int(y1 - y0), int(x1 - x0)],
        "shipped_measurements": {k: (v if v != "" else None)
                                 for k, v in shape.items()},
        "network_length_px": net_len, "branch_points": n_branch,
        "endpoints": n_end, "skeleton_px": skel_px,
        "longest_tip_geodesic_px": geo, "geodesic_info": geo_info,
        "drawn_route_px": path_len,
        "source": "analysis/_vendor/extended_features.crack_shape_measurements and "
                  "analysis/geodesic.longest_tip_geodesic -- the functions the "
                  "application calls; this script recomputes nothing but the route it "
                  "draws, whose length is checked against the shipped geodesic",
        "width_circle_positions_pct": [10, 50, 90],
        "width_circle_population": "the whole skeleton, which is the population "
                                   "MeanWidth_px averages over",
        "tortuosity_digitisation_floor": floor,
        "tortuosity_floor_note": "a straight rasterised line of the same chord swept over "
                                 "angle, measured by the same code. It is 1.000 at 0, 45 "
                                 "and 90 degrees and rises in between with no waviness "
                                 "involved, so where a tortuosity IS reported it has to "
                                 "be read against this range and not against 1",
        "tortuosity_here": "not emitted: the shipped definition requires an unbranched "
                           "medial axis and this region has %d branch points" % n_branch,
        "length_note": "summed step lengths along the medial axis, diagonal steps counted "
                       "as sqrt(2); a pixel count understates length by up to 41% and can "
                       "put the tortuosity below 1",
        "scale_provenance": BM.SEM_SCALE_SOURCE,
    }, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)
    print(f"  region {shape['Area_px']:,} px; network {net_len * um:.2f} um over "
          f"{n_branch} branch points and {n_end} tips; longest route "
          f"{(geo or float('nan')) * um:.2f} um (drawn {path_len * um:.2f})")
    print(f"  width mean {shape['MeanWidth_px'] * um:.2f}, max "
          f"{shape['MaxWidth_px'] * um:.2f} um; orientation "
          f"{shape['Orientation_deg']:+.1f} deg; tortuosity "
          f"{shape['Tortuosity'] if shape['Tortuosity'] != '' else 'not emitted'} "
          f"(straight-line floor {floor['min']:.3f}-{floor['max']:.3f} over "
          f"{floor['n_angles']} angles)")


if __name__ == "__main__":
    main()
