#!/usr/bin/env python3
"""The diagnostic plate for one crackmode run: where the junctions are, how the branches
were cut, which class each got, and whether the obvious shortcut would have worked.

ONE MARKER PER NODE. `CM.junctions` returns topological junctions -- connected clusters of
>=3-neighbour pixels, with the degree read off the branches incident on the cluster -- not the
pixels themselves. The per-pixel set over-marks by about 5x (an axis-aligned crossing lights
its centre and all four arms), so a plate drawn from it stacks five markers on one node and
reads as a dense smear wherever the crack is wide.

PANEL (d) IS THE POINT OF THE PLATE. Junctions here do one job: they cut the skeleton into
branches. They are not evidence of crack mode -- a junction's degree says how many ways the
crack divides, not whether it divided at a grain corner. The natural next thought is that
degree and branch length ought to predict the mode anyway, and if they did, the EBSD map
would be unnecessary. So the plate measures that directly, as an AUC against the class the
grain map assigns, with chance drawn in. A reader who wants the shortcut can see what it is
worth on their own specimen instead of being told.
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import ndimage as ndi
from skimage import morphology

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(os.path.dirname(HERE), "paper", "figures")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import crackmode as CM                         # noqa: E402
import journal_style as J                      # noqa: E402

CLASS_COLOUR = {"intergranular": J.ACCENT, "transgranular": J.ACCENT2, "mixed": J.G_MID}
DEGREE_MARKER = {3: ("o", 26), 4: ("s", 34)}   # 3-way and 4-way-or-more, one marker per NODE


def _branch_label_map(mask, rows):
    """Paint each classified branch with its class index, for display."""
    _skel, lab, _n = CM._segment_pixels(mask)
    out = np.zeros(lab.shape, np.uint8)
    order = {"intergranular": 1, "transgranular": 2, "mixed": 3}
    for r in rows:
        out[lab == r["segment"]] = order[r["mode"]]
    return out


def _pick_window(painted, side=320):
    """A window containing both classes if one exists, else the busiest one."""
    H, W = painted.shape
    side = min(side, H, W)
    best, bxy = -1.0, (0, 0)
    step = max(16, side // 8)
    for y in range(0, H - side + 1, step):
        for x in range(0, W - side + 1, step):
            sub = painted[y:y + side, x:x + side]
            a, b = (sub == 1).sum(), (sub == 2).sum()
            score = min(a, b) * 1000 + a + b          # both classes first, then density
            if score > best:
                best, bxy = score, (y, x)
    return bxy[0], bxy[1], side


def explain(mask, grain_ids, result, out_png, *, nm_per_px=None, tau_px=None):
    mask = np.asarray(mask, bool)
    boundary = CM.boundaries_from_grain_ids(grain_ids)
    rows = result["classification"].get("segments", [])
    painted = _branch_label_map(mask, rows)
    jy, jx, jdeg = CM.junctions(mask)
    y0, x0, side = _pick_window(painted)

    # TWO gridspecs. One set of margins cannot serve both rows: micrographs want none and
    # the charts need room for tick labels, and sharing them silently pushed panel (d)'s
    # y labels off the canvas so that (e)'s appeared to belong to (d).
    fig = plt.figure(figsize=(J.W2, 4.6))
    gs = fig.add_gridspec(1, 3, wspace=0.03,
                          left=0.004, right=0.996, top=0.985, bottom=0.455)
    gs2 = fig.add_gridspec(1, 3, wspace=0.46,
                           left=0.062, right=0.988, top=0.385, bottom=0.105)

    def micro(ax, draw_boundary=True):
        ax.imshow(np.ones(mask.shape), cmap="gray", vmin=0, vmax=1, interpolation="nearest")
        if draw_boundary:
            b = np.ma.masked_where(~boundary, boundary.astype(float))
            ax.imshow(b, cmap=matplotlib.colors.ListedColormap([J.G_LIGHT]),
                      interpolation="nearest")
        J.micrograph(ax)

    # (a) the grain network, the crack, and every junction
    ax = fig.add_subplot(gs[0, 0])
    micro(ax)
    skel = morphology.skeletonize(mask)
    sk = np.ma.masked_where(~skel, skel.astype(float))
    ax.imshow(sk, cmap=matplotlib.colors.ListedColormap([J.INK]), interpolation="nearest")
    for deg in (3, 4):
        sel = (jdeg == deg) if deg == 3 else (jdeg >= 4)
        if sel.any():
            m, s = DEGREE_MARKER[deg]
            ax.scatter(jx[sel], jy[sel], s=s * 0.55, marker=m, facecolor="none",
                       edgecolor=J.PAINT_NOTCRACK, linewidths=0.7, zorder=5)
    ax.add_patch(plt.Rectangle((x0, y0), side, side, fill=False, edgecolor=J.ROI, lw=1.0))
    J.panel_label(ax, "a", inside=True)

    # (b) the same window enlarged, so the cut points are legible
    ax = fig.add_subplot(gs[0, 1])
    sub = slice(y0, y0 + side), slice(x0, x0 + side)
    ax.imshow(np.ones((side, side)), cmap="gray", vmin=0, vmax=1)
    bb = np.ma.masked_where(~boundary[sub], boundary[sub].astype(float))
    ax.imshow(bb, cmap=matplotlib.colors.ListedColormap([J.G_LIGHT]), interpolation="nearest")
    ss = np.ma.masked_where(~skel[sub], skel[sub].astype(float))
    ax.imshow(ss, cmap=matplotlib.colors.ListedColormap([J.INK]), interpolation="nearest")
    inw = (jy >= y0) & (jy < y0 + side) & (jx >= x0) & (jx < x0 + side)
    for deg in (3, 4):
        sel = inw & ((jdeg == deg) if deg == 3 else (jdeg >= 4))
        if sel.any():
            m, s = DEGREE_MARKER[deg]
            ax.scatter(jx[sel] - x0, jy[sel] - y0, s=s, marker=m, facecolor="none",
                       edgecolor=J.PAINT_NOTCRACK, linewidths=1.0, zorder=5)
    J.micrograph(ax)
    J.panel_label(ax, "b", inside=True)

    # (c) the branches, coloured by the class the GRAIN MAP assigned
    ax = fig.add_subplot(gs[0, 2])
    ax.imshow(np.ones((side, side)), cmap="gray", vmin=0, vmax=1)
    ax.imshow(bb, cmap=matplotlib.colors.ListedColormap([J.G_LIGHT]), interpolation="nearest")
    pw = painted[sub]
    for idx, name in ((1, "intergranular"), (2, "transgranular"), (3, "mixed")):
        lay = np.ma.masked_where(pw != idx, (pw == idx).astype(float))
        ax.imshow(lay, cmap=matplotlib.colors.ListedColormap([CLASS_COLOUR[name]]),
                  interpolation="nearest")
    J.micrograph(ax)
    J.panel_label(ax, "c", inside=True)

    # (d) and (e): does the shortcut work?
    defin = [r for r in rows if r["mode"] in ("intergranular", "transgranular")]
    st = result.get("shortcut_test", {})
    for col, (key, field, xlabel) in enumerate((
            ("auc_branch_length", "length_px", "branch length (px)"),
            ("auc_junction_degree", "max_adjacent_degree", "highest adjacent junction degree"))):
        ax = fig.add_subplot(gs2[0, col])
        rng = np.random.default_rng(0)
        for i, name in enumerate(("intergranular", "transgranular")):
            v = np.array([r[field] for r in defin if r["mode"] == name], float)
            if v.size == 0:
                continue
            ax.plot(v, i + (rng.random(v.size) - 0.5) * 0.34, linestyle="none", marker="o",
                    markersize=3.4, markerfacecolor=CLASS_COLOUR[name], alpha=0.75,
                    markeredgecolor=J.INK, markeredgewidth=0.25)
            ax.plot([np.median(v)] * 2, [i - 0.26, i + 0.26], color=J.INK, lw=1.4)
        ax.set_yticks([0, 1]); ax.set_yticklabels(["inter", "trans"])
        ax.set_ylim(-0.55, 1.55); ax.set_xlabel(xlabel)
        auc = st.get(key)
        ax.text(0.97, 0.97, "AUC " + ("n/a" if auc is None else f"{auc:.3f}")
                + "\n0.5 = carries nothing", transform=ax.transAxes, ha="right", va="top",
                fontsize=J.TICK, color=J.G_DARK, linespacing=1.3)
        J.panel_label(ax, "de"[col])

    # (f) the controls, so the plate is readable on its own
    ax = fig.add_subplot(gs2[0, 2])
    ctl = result["controls"]
    names = ["negative", "null", "this\ncrack", "positive"]
    vals = [ctl.get("negative_control"), ctl.get("null_mean"),
            ctl.get("real_boundary_frac"), ctl.get("positive_control")]
    cols = [J.ACCENT2, J.G_MID, J.ACCENT, J.G_DARK]
    xs = np.arange(4)
    ok = [v is not None for v in vals]
    ax.bar(xs[ok], [v for v, k in zip(vals, ok) if k], 0.62,
           color=[c for c, k in zip(cols, ok) if k], edgecolor=J.INK, linewidth=0.5)
    sat = ctl.get("saturation")
    if sat is not None and np.isfinite(sat):
        ax.axhline(sat, color=J.INK, lw=0.9, ls=(0, (4, 2)))
        ax.text(-0.42, sat + 0.03, "saturation floor", ha="left", va="bottom",
                fontsize=J.TICK, color=J.G_DARK)
    ax.set_xticks(xs); ax.set_xticklabels(names, fontsize=J.TICK)
    ax.set_ylabel("fraction on a boundary"); ax.set_ylim(0, 1.18)
    J.panel_label(ax, "f")

    J.save(fig, out_png, printed_width=J.W2)
    return out_png
