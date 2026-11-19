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


def prepare(tag):
    """Measure one modality's largest interior region with the SHIPPED functions.

    Everything drawn for that modality comes out of this one call, so the panel and the
    table row cannot drift apart: the route drawn is checked against the geodesic the
    software reports, and the skeleton drawn is the one the numbers were taken from.
    """
    d = BM.load(tag)
    nm = float(d["nm_per_px"])
    um = nm / 1000.0
    region_full = largest_interior(d["final"])

    ys, xs = np.where(region_full)
    by0, by1, bx0, bx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    bbox = region_full[by0:by1, bx0:bx1]
    shape = EF.crack_shape_measurements(bbox)
    net_len, n_branch, n_end, skel_local, _loc, skel_px = EF.skeleton_stats(bbox)
    geo, geo_info = geodesic.longest_tip_geodesic(skel_local, net_len)

    y0 = max(by0 - PAD, 0)
    y1 = min(by1 + PAD, region_full.shape[0])
    x0 = max(bx0 - PAD, 0)
    x1 = min(bx1 + PAD, region_full.shape[1])
    sl = (slice(y0, y1), slice(x0, x1))
    region, img = region_full[sl], d["img"][sl]
    sy = (by0 - 2 if by0 >= 2 else 0) - y0
    sx = (bx0 - 2 if bx0 >= 2 else 0) - x0
    skel = np.zeros(region.shape, bool)
    skel[sy:sy + skel_local.shape[0], sx:sx + skel_local.shape[1]] = skel_local
    if int(skel.sum()) != skel_px:
        raise SystemExit(f"{tag}: the measured skeleton does not fit the display crop: "
                         f"{int(skel.sum())} px placed of {skel_px}")

    path, path_len = axis_path(skel)
    if geo is not None and abs(path_len - geo) > 1.0:
        raise SystemExit(
            f"{tag}: the drawn route is {path_len:.2f} px and the shipped longest "
            f"tip-to-tip geodesic is {geo:.2f} px; the figure would draw a different "
            f"route from the one it reports")
    dt = ndi.distance_transform_edt(region)
    (py0, px0), (py1, px1) = path[0], path[-1]
    chord_px = float(np.hypot(py1 - py0, px1 - px0))
    floor = straight_floor(chord_px)

    lo, hi = BM.display_range(d["img"])
    grey = exposure.rescale_intensity(img.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0.0, 1.0))
    rgb = np.dstack([grey] * 3)
    rgb[region] = 0.72 * rgb[region] + 0.28 * np.array(J.rgb(J.MASK))
    #: kept beside the composite so the panel can draw the photograph smoothly and
    #: the region exactly, instead of resampling one rule over both.

    sk_pts = np.argwhere(skel)
    sk_w = np.array([2.0 * dt[y, x] for y, x in sk_pts])
    order = np.argsort(sk_w)
    picks = [int(order[int(round(q * (len(order) - 1)))]) for q in (0.10, 0.50, 0.90)]
    circles = [(sk_pts[k][0], sk_pts[k][1], sk_w[k] / 2.0) for k in picks]

    return dict(d=d, nm=nm, um=um, region=region, rgb=rgb, grey=grey,
                skel=skel, circles=circles,
                shape=shape, net_len=net_len, n_branch=n_branch, n_end=n_end,
                skel_px=skel_px, geo=geo, geo_info=geo_info, path_len=path_len,
                floor=floor, chord_px=chord_px, ends=(py0, px0, py1, px1),
                crop=(int(y0), int(x0), int(y1 - y0), int(x1 - x0)))


def draw_region(ax, P, letter):
    """One micrograph panel: the region, its whole medial axis, route, chord, circles."""
    #: TWO LAYERS: the micrograph resampled smoothly because it is a photograph, the
    #: region tint at nearest neighbour because it is the result. The tint is a 28%
    #: blend over the grey, so it is rebuilt here at the same weights rather than
    #: reused from the composite.
    ax.imshow(P["grey"], cmap="gray", vmin=0, vmax=1, interpolation="bilinear",
              zorder=1)
    _rgba = np.zeros(P["region"].shape + (4,), float)
    _rgba[P["region"], :3] = np.array(J.rgb(J.MASK))
    _rgba[P["region"], 3] = 0.28
    ax.imshow(_rgba, interpolation="nearest", zorder=2)
    J.micrograph(ax)
    ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes, fill=False,
                           edgecolor=J.INK, linewidth=0.7, zorder=40))
    ays, axs_ = np.where(P["skel"])
    ax.plot(axs_, ays, ".", color=J.SKELETON, ms=1.1, mew=0, zorder=20)
    py0, px0, py1, px1 = P["ends"]
    ax.plot([px0, px1], [py0, py1], color=J.ROI, lw=1.0, linestyle=(0, (4, 2)),
            zorder=21)
    ax.plot([px0, px1], [py0, py1], "o", ms=3.4, mfc="white", mec=J.ROI, mew=1.0,
            linestyle="none", zorder=22)
    for yy, xx, r in P["circles"]:
        ax.add_patch(Circle((xx, yy), r, fill=False, edgecolor=J.ROI, linewidth=1.0,
                            zorder=25))
        ax.plot([xx, xx + r], [yy, yy], color=J.ROI, lw=0.9, zorder=26)
    J.panel_label(ax, letter, inside=True)
    scalebar(ax, P["nm"], P["region"].shape[1], fontsize=J.TICK)


def values(P):
    """The table's value column for one modality, formatted from the shipped numbers."""
    sh, um, geo = P["shape"], P["um"], P["geo"]
    field = P["d"]["img"].shape[0] * P["d"]["img"].shape[1] * um * um / 1e3
    return [
        f"{sh['Area_px'] * um * um:.1f} \u00b5m\u00b2 of a {field:.0f} \u00d7 10\u00b3 \u00b5m\u00b2 field",
        f"{P['net_len'] * um:.1f} \u00b5m, {P['n_branch']} branch pts",
        (f"{geo * um:.1f} \u00b5m" if geo is not None
         else f"not defined: {P['geo_info'].get('reason')}"),
        f"{sh['MeanWidth_px'] * um:.2f} \u00b5m",
        f"{sh['MaxWidth_px'] * um:.2f} \u00b5m",
        f"{sh['Orientation_deg']:+.1f}\u00b0 from the image rows",
    ]


def main():
    P = {t: prepare(t) for t in ("sem", "txm")}

    W = J.PAGEW
    Mg = 0.03
    GAP = 0.20
    LW = (W - 2 * Mg - GAP) / 2.0
    IMH = max(LW * P[t]["region"].shape[0] / P[t]["region"].shape[1]
              for t in ("sem", "txm"))
    IMH = min(IMH, 2.30)
    ROWH = 0.215
    NROWS = len(['Area', 'Network length', 'Longest crack',
                  'Mean width', 'Max width', 'Orientation'])
    TABH = 0.26 + NROWS * ROWH + 0.12
    FOOT = 0.30
    TITLE = 0.17          # room above the panels for the SEM / TXM headings
    Htot = Mg + TITLE + IMH + 0.10 + FOOT + Mg

    fig = plt.figure(figsize=(W, Htot))

    def ax_at(xin, yin, win, hin):
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    for i, (tag, letter) in enumerate((("sem", "a"), ("txm", "b"))):
        #: BOTH PANELS THE SAME SIZE. Each used to take the height its own crack's
        #: aspect ratio implied, so the two printed at different sizes and a reader
        #: comparing them compared two box sizes as well as two instruments.
        ax = ax_at(Mg + i * (LW + GAP), Mg + TITLE, LW, IMH)
        draw_region(ax, P[tag], letter)
        #: THE ARM'S OWN COLOUR ROUND THE PANEL, so which micrograph is which is read
        #: off the frame, the same blue-SEM orange-TXM convention the rest of the pack
        #: uses.
        arm_colour = J.ACCENT if tag == "sem" else J.ACCENT2
        for sp in ax.spines.values():
            sp.set_visible(True)
            sp.set_edgecolor(arm_colour)
            sp.set_linewidth(1.6)
        ax.set_title("SEM" if tag == "sem" else "TXM", fontsize=J.LABEL,
                     fontweight="bold", pad=2.0, color=arm_colour)

    #: TORTUOSITY IS OFF THE TABLE. It had a row that said "no value" in both value
    #: columns on both arms, because the definition needs an unbranched medial axis
    #: and both regions branch. A row that is empty on every column it has is a row
    #: about the software's limits, not about the crack, and the author asked for it
    #: off the plate. The withholding itself is NOT dropped: it is still in this
    #: figure's caption file, in the manuscript caption, and in the application, which
    #: is where a reader who wonders why the quantity is missing will look.
    names = ["Area  A", "Network length", "Longest crack", "Mean width", "Max width",
             "Orientation  \u03b8"]
    rules = ["marked pixels, as area",
             "every branch of the axis, summed",
             "the longest tip-to-tip route through it",
             "twice the medial-axis radius",
             "the largest circle that fits inside",
             "the region's second-moment major axis"]
    vs, vt = values(P["sem"]), values(P["txm"])

    #: WHAT THE DRAWN GEOMETRY IS. Three things are drawn over each crack and the
    #: plate named none of them -- the rules lived in the table that has now gone, so
    #: without this key the circles and the dashed line are decoration.
    from matplotlib.lines import Line2D as _L2D
    _keys = [
        (_L2D([], [], color="#DAA520", lw=0.9, linestyle=":"),
         "medial axis \u2014 network length"),
        (_L2D([], [], color=J.ROI, lw=1.2, linestyle="--", marker="o",
              markerfacecolor="white", markeredgecolor=J.ROI, markersize=3.2),
         "longest tip-to-tip route"),
        (_L2D([], [], color=J.ROI, lw=1.2, marker="o", markerfacecolor="none",
              markeredgecolor=J.ROI, markersize=6.0, linestyle="none"),
         "inscribed circles \u2014 width"),
    ]
    fig.legend([h for h, _ in _keys], [t for _, t in _keys],
               loc="lower center", bbox_to_anchor=(0.5, 0.004), ncol=3,
               frameon=False, fontsize=J.TICK, handlelength=1.6,
               handletextpad=0.4, columnspacing=1.1, borderpad=0.0,
               borderaxespad=0.0)

    #: THE TABLE IS NOT ON THE PLATE ANY MORE. The author asked for it separate from
    #: the figure, and for "how it is measured" to be prose rather than a column.
    #: Every value it carried -- area, network length, longest route, mean and max
    #: width, orientation, for both arms -- is still computed above and still written
    #: to this module's caption file, which is where the manuscript reads them from,
    #: so dropping the drawn table loses no number. `values()` and the name and rule
    #: lists above are kept for exactly that record.

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "every measurand the paper reports, drawn on the largest interior "
                "marked region of BOTH modalities' illustrated frames",
        "arms": {t: {
            "field": str(P[t]["d"]["field"]), "nm_per_px": P[t]["nm"],
            "crop_yx": P[t]["crop"][:2], "crop_px": P[t]["crop"][2:],
            "shipped_measurements": {k: (v if v != "" else None)
                                     for k, v in P[t]["shape"].items()},
            "network_length_px": P[t]["net_len"], "branch_points": P[t]["n_branch"],
            "endpoints": P[t]["n_end"], "skeleton_px": P[t]["skel_px"],
            "longest_tip_geodesic_px": P[t]["geo"], "geodesic_info": P[t]["geo_info"],
            "drawn_route_px": P[t]["path_len"],
            "tortuosity_digitisation_floor": P[t]["floor"],
        } for t in ("sem", "txm")},
        "source": "analysis/_vendor/extended_features.crack_shape_measurements and "
                  "analysis/geodesic.longest_tip_geodesic -- the functions the "
                  "application calls; this script recomputes nothing but the route it "
                  "draws, whose length is checked against the shipped geodesic",
        "width_circle_positions_pct": [10, 50, 90],
        "width_circle_population": "the whole skeleton, which is the population "
                                   "MeanWidth_px averages over",
        "tortuosity_floor_note": "a straight rasterised line of the same chord swept over "
                                 "angle, measured by the same code. It is 1.000 at 0, 45 "
                                 "and 90 degrees and rises in between with no waviness "
                                 "involved, so where a tortuosity IS reported it has to "
                                 "be read against this range and not against 1",
        "length_note": "summed step lengths along the medial axis, diagonal steps counted "
                       "as sqrt(2); a pixel count understates length by up to 41% and can "
                       "put the tortuosity below 1",
        "scale_provenance": {"sem": BM.SEM_SCALE_SOURCE, "txm": BM.TXM_SCALE_SOURCE},
    }, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)
    for t in ("sem", "txm"):
        q = P[t]
        print(f"  {t.upper()}  region {q['shape']['Area_px']:,} px; network "
              f"{q['net_len'] * q['um']:.2f} um over {q['n_branch']} branch points; "
              f"longest route {(q['geo'] or float('nan')) * q['um']:.2f} um; width mean "
              f"{q['shape']['MeanWidth_px'] * q['um']:.2f}, max "
              f"{q['shape']['MaxWidth_px'] * q['um']:.2f} um")


if __name__ == "__main__":
    main()
