#!/usr/bin/env python3
"""User-chosen figures, rendered as SVG the browser shows and the user downloads.

WHY SVG AND NOT A PNG FROM MATPLOTLIB. A figure that goes in a paper has to be editable and
resolution-independent, and matplotlib would add ~40 MB to a bundled app for something the
browser already draws. SVG also means the download and the on-screen figure are literally the
same bytes, so what you publish is what you checked.

WHAT IT REFUSES TO PLOT, and each refusal is the point:

  * Any physical quantity for a frame with no nm/px. Those frames are dropped from the figure
    and the count is printed on it, rather than plotted as if a missing scale were a zero.
  * A specimen mean over fewer than 3 frames, unless asked, because a mean of two is not a
    mean and this corpus has 12 specimen-arms that thin.
  * Two arms on one axis. sem/gated, sem/machine and txm are different instruments or
    different definitions of the object; overlaying them makes a picture of nothing.

Every figure carries its n, its units and its arm in the caption, because a figure that
leaves the app loses the page around it.
"""
import os
import math

#: Validated categorical slots (light / dark), checked with the colour-vision validator
#: rather than picked by eye. Only two are used at a time; a third series is a facet.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

#: Numeric fields a user may put on an axis, with the label and unit shown on the figure.
FIELDS = {
    "area_fraction":            ("Crack area fraction", "", 100.0, "%"),
    "n_cracks_measured":        ("Cracks measured", "", 1.0, ""),
    "speck_count":              ("Specks", "", 1.0, ""),
    "largest_share_of_area":    ("Largest region's share of area", "", 100.0, "%"),
    "p21_skeleton_mm_per_mm2":  ("P21 (skeleton)", "mm/mm²", 1.0, ""),
    "p20_per_mm2":              ("P20", "/mm²", 1.0, ""),
    # MCL is the longest tip-to-tip crack. The network total is a SEPARATE axis, because
    # putting a network size on an axis labelled "longest crack" is how it got read as one.
    "mcl_um":                   ("Longest crack (MCL)", "µm", 1.0, ""),
    "largest_network_centreline_um": ("Largest network centreline", "µm", 1.0, ""),
    "tcl_um":                   ("Total crack length (TCL)", "µm", 1.0, ""),
    "mean_width_px_median":     ("Median mean-width", "px", 1.0, ""),
    "n_junctions":              ("Junctions", "", 1.0, ""),
    # NAMED FOR THE WEIGHTING, all three of them. This was one field called "Area touching
    # frame edge" plotting censored_share, which is the share of REGIONS -- the dataset
    # says so in its own censored_share_weighting column, and the frame table on screen
    # already shows the three separately. On sem/gated 260622_316_H_b2 the figure read
    # 2.4% while the area-weighted share is 84.1%: a 35x understatement, on the app's own
    # headline caveat about MCL, exported as a standalone figure that contradicted the
    # screen it came from. Offering all three is the honest option because all three are
    # already computed on every frame.
    "censored_share":           ("Regions touching frame edge", "", 100.0, "%"),
    "censored_share_by_area":   ("Crack AREA touching frame edge", "", 100.0, "%"),
    "censored_share_by_length": ("Crack LENGTH touching frame edge", "", 100.0, "%"),
    "area_analysed_mm2":        ("Area analysed", "mm²", 1.0, ""),
    "crack_area_px":            ("Crack area", "px", 1.0, ""),
}
#: Fields that only exist once a physical scale is known.
NEEDS_SCALE = {"p21_skeleton_mm_per_mm2", "p20_per_mm2", "mcl_um",
               "largest_network_centreline_um", "tcl_um", "area_analysed_mm2"}

KINDS = ("scatter", "box_by_specimen", "bar_by_specimen", "histogram",
         "stage_map", "stage_surface")

#: A SEQUENTIAL RAMP: ONE HUE, LIGHT TO DARK. Not a rainbow, and no hue change -- the
#: quantity it encodes (crack area on a patch) is a magnitude, and a rainbow makes a
#: magnitude read as categories. Five steps, because a reader matching a cell to a legend
#: cannot resolve more than about five.
RAMP = ["#dbe9fb", "#a8cbf4", "#6ba6e8", "#3579cf", "#1b4f8f"]


def _ramp(t):
    """Colour for a value already normalised to 0..1."""
    if t != t:
        return "var(--surface-3,#eee)"
    i = min(len(RAMP) - 1, max(0, int(t * len(RAMP))))
    return RAMP[i]


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _nice(lo, hi):
    """A rounded axis range and a step, so ticks land on readable numbers."""
    if hi <= lo:
        hi = lo + 1.0
    span = hi - lo
    mag = 10 ** math.floor(math.log10(span))
    for m in (1, 2, 2.5, 5, 10):
        step = mag * m
        if span / step <= 6:
            break
    return math.floor(lo / step) * step, math.ceil(hi / step) * step, step


def _collapse_to_fields(rows, fields_needed):
    """One observation per PHYSICAL FIELD, not per frame.

    A figure that leaves this app goes into a paper, and this one was double-counting. 142
    gated frames are 86 distinct fields: 56 were imaged twice, once through CBS and once
    through ETD. The box plot printed "n=20" for a specimen whose own card said 10 fields,
    and its caption said "specimen is the inferential unit" directly underneath -- and the
    two detectors differ by 2.29x on the same physical field, so the box was also mixing two
    instruments into one spread.

    Uses specimen_stats.field_key rather than a second rule, so the figure and the specimen
    card can never disagree about what a field is.
    """
    import sys as _sys
    import os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__))), "analysis"))
    try:
        from specimen_stats import detector_of, field_key
    except ImportError:
        return rows, {}

    groups = {}
    for r in rows:
        groups.setdefault((r.get("specimen", "unparsed"),
                           field_key(r.get("frame", ""))), []).append(r)
    out, mixed = [], {}
    for (spec, _fk), fs in sorted(groups.items()):
        rep = dict(fs[0])
        for v in fields_needed:
            vals = [f[v] for f in fs if f.get(v) is not None]
            if vals:
                rep[v] = sum(vals) / len(vals)
        rep["_n_frames_in_field"] = len(fs)
        out.append(rep)
        if len(fs) > 1:
            dets = {detector_of(f.get("frame", "")) for f in fs} - {None}
            if len(dets) > 1:
                mixed[spec] = sorted(dets)
    return out, mixed


def build(frames, arm, kind, x=None, y=None, min_frames=3, include_thin=False):
    """Return {'svg': str, 'caption': str, 'n': int, 'dropped': {...}} or raise ValueError."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    rows = [f for f in frames if f.get("arm") == arm]
    if not rows:
        raise ValueError(f"no frames for arm {arm!r}")

    dropped = {}
    need = [v for v in (x, y) if v]
    for v in need:
        if v not in FIELDS:
            raise ValueError(f"unknown field {v!r}")
    if any(v in NEEDS_SCALE for v in need):
        before = len(rows)
        rows = [r for r in rows if r.get("scale_known")]
        if before - len(rows):
            dropped["no_scale"] = before - len(rows)
    before = len(rows)
    rows = [r for r in rows if all(r.get(v) is not None for v in need)]
    if before - len(rows):
        dropped["missing_value"] = before - len(rows)
    if not rows:
        raise ValueError("every frame was dropped: no scale, or the field is empty here")

    n_frames = len(rows)
    rows, mixed_detectors = _collapse_to_fields(rows, need)
    if n_frames != len(rows):
        dropped["_collapsed"] = (n_frames, len(rows))
    if mixed_detectors:
        dropped["_mixed_detectors"] = mixed_detectors
    #: The DENOMINATOR for that count. Without it the caption read "7 specimens average
    #: two detectors per field" directly beneath a figure drawing FOURTEEN boxes, and the
    #: leading number in a caption is read as the figure's specimen count. The clause was
    #: true and attached to the wrong object -- the same class of error as a count of
    #: components read as a mass. Stating it as "7 of 14" removes the reading entirely.
    dropped["_n_specimens"] = len({r.get("specimen", "unparsed") for r in rows})

    # The collapsed rows travel with the result so the conclusions under the chart are
    # computed from exactly the points the chart drew -- the same rule the frame and
    # specimen read-outs follow, and the reason a statement can never disagree with the
    # figure beside it.
    def _with_rows(d):
        # THE ROWS THAT TRAVEL ARE THE ROWS THAT WERE DRAWN, and for the stage kinds those
        # are not the same set. A panel builder may legitimately use a subset -- the raster
        # figures place only the 36 positioned fields at the modal magnification, out of 86
        # -- and handing the full 86 to the conclusions engine broke the one rule this
        # module exists to keep: a statement under a chart must be computed from exactly
        # the points above it.
        #
        # It was not a cosmetic difference. The extra rows include the 337.2396 nm/px
        # overview field, whose field of view is 10.6x a fine field's and spans much of the
        # raster, so it has no position comparable to theirs. Including it computed the
        # gradient over TEN fields and reported rho +0.745..+0.842 where the nine-field
        # determination is +0.750..+0.867 -- a weaker trend, from a point that should not
        # have been on the axis at all.
        d["rows"] = d.pop("_drawn_rows", rows)
        return d

    if kind == "histogram":
        return _with_rows(_hist(rows, arm, y or x, dropped))
    if kind == "scatter":
        if not (x and y):
            raise ValueError("a scatter needs both x and y")
        return _with_rows(_scatter(rows, arm, x, y, dropped))
    if kind in ("stage_map", "stage_surface"):
        return _with_rows(_stage_panels(rows, arm, y or x, dropped, kind))
    return _with_rows(_by_specimen(rows, arm, y or x, kind, min_frames, include_thin, dropped))


def _frame(W, H, title, caption, body, ylab="", xlab=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%"
  font-family="ui-sans-serif,-apple-system,Segoe UI,system-ui,sans-serif" role="img"
  aria-label="{_esc(title)}">
<rect width="{W}" height="{H}" fill="var(--surface-2,#fff)"/>
<text x="16" y="24" font-size="14" font-weight="650" fill="var(--text-primary,#0b0b0b)">{_esc(title)}</text>
{body}
<text x="16" y="{H-10}" font-size="11" fill="var(--text-muted,#82807a)">{_esc(caption)}</text>
<text x="14" y="{H/2}" font-size="11" fill="var(--text-secondary,#52514e)"
  transform="rotate(-90 14 {H/2})" text-anchor="middle">{_esc(ylab)}</text>
<text x="{W/2}" y="{H-28}" font-size="11" fill="var(--text-secondary,#52514e)"
  text-anchor="middle">{_esc(xlab)}</text>
</svg>'''


def _axes(x0, y0, x1, y1, lo, hi, step, horizontal=False):
    """Recessive grid + ticks. Grid behind the marks, never over them."""
    out = []
    n = int(round((hi - lo) / step))
    for i in range(n + 1):
        v = lo + i * step
        t = (v - lo) / (hi - lo) if hi > lo else 0
        if horizontal:
            yy = y1 - t * (y1 - y0)
            out.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" '
                       f'stroke="var(--rule,#dedbd6)" stroke-width="1"/>')
            out.append(f'<text x="{x0-6}" y="{yy+4:.1f}" font-size="10" text-anchor="end" '
                       f'fill="var(--text-muted,#82807a)">{v:g}</text>')
        else:
            xx = x0 + t * (x1 - x0)
            out.append(f'<text x="{xx:.1f}" y="{y1+14}" font-size="10" text-anchor="middle" '
                       f'fill="var(--text-muted,#82807a)">{v:g}</text>')
    return "".join(out)


def _cap(arm, n, dropped, extra=""):
    # "fields", not "frames". The caption used to say frames while claiming in the same
    # breath that the specimen is the inferential unit, on a figure whose n double-counted
    # every field imaged through two detectors.
    bits = [f"{arm}", f"n = {n} fields"]
    if dropped.get("_collapsed"):
        was, now = dropped["_collapsed"]
        if was != now:
            bits.append(f"{was} frames collapsed to {now} fields")
    if dropped.get("no_scale"):
        bits.append(f"{dropped['no_scale']} dropped: no physical scale")
    if dropped.get("missing_value"):
        bits.append(f"{dropped['missing_value']} dropped: value not defined")
    # Written by _stage_panels. Without this clause the key was set and never read, so a
    # raster figure silently said nothing about the 50 fields it could not place.
    if dropped.get("no_stage_position"):
        bits.append(f"{dropped['no_stage_position']} excluded: no stage position recorded")
    if dropped.get("thin_specimens"):
        bits.append(f"{dropped['thin_specimens']} specimens hidden: under 3 fields")
    # Said out loud, because a box built from two detectors that differ by 2.29x on the
    # same physical field is showing instrument spread as if it were material spread.
    if dropped.get("_mixed_detectors"):
        m = dropped["_mixed_detectors"]
        tot = dropped.get("_n_specimens")
        of = f" of {tot}" if tot else ""
        bits.append(f"{len(m)}{of} specimens average two detectors per field "
                    f"(CBS reads ~2.3x ETD; the spread is partly instrument)")
    if extra:
        bits.append(extra)
    return "  ·  ".join(bits)


def axis_label(key):
    """The label a reader can check the numbers against: name plus the unit they are in.

    THE FOURTH SLOT WAS BOUND TO `_` AT EVERY RENDER PATH. FIELDS carries (label, unit,
    scale, suffix), and the three percent fields put their scale in slot 2 and their "%" in
    slot 4 -- so a histogram of area_fraction was drawn with its values multiplied by 100
    and an axis reading "Crack area fraction" with ticks 0..50. That axis is wrong by a
    factor of 100 unless the reader guesses percent, on a figure whose whole purpose is to
    stand alone. Fields with a real unit (mcl_um -> "Longest crack (MCL) µm") were fine,
    which is why it survived: the defect is invisible unless you look at a percent field.
    """
    lab, unit, _scale, suffix = FIELDS[key]
    tail = unit or suffix
    return f"{lab} ({tail})" if tail == "%" else (f"{lab} {tail}" if tail else lab)


def _scatter(rows, arm, x, y, dropped):
    W, H = 640, 420
    x0, y0, x1, y1 = 64, 40, W - 20, H - 52
    lx, _ux, sx, _px = FIELDS[x]
    ly, _uy, sy, _py = FIELDS[y]
    xs = [r[x] * sx for r in rows]
    ys = [r[y] * sy for r in rows]
    xlo, xhi, xst = _nice(min(xs), max(xs))
    ylo, yhi, yst = _nice(min(ys), max(ys))
    pts = []
    for r, vx, vy in zip(rows, xs, ys):
        px = x0 + (vx - xlo) / (xhi - xlo) * (x1 - x0)
        py = y1 - (vy - ylo) / (yhi - ylo) * (y1 - y0)
        pts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{SERIES[0]}" '
                   f'fill-opacity="0.72" stroke="var(--surface-2,#fff)" stroke-width="1.5">'
                   f'<title>{_esc(r["frame"])}: {vx:.4g}, {vy:.4g}</title></circle>')
    body = (_axes(x0, y0, x1, y1, ylo, yhi, yst, horizontal=True)
            + _axes(x0, y0, x1, y1, xlo, xhi, xst)
            + f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="var(--rule,#dedbd6)"/>'
            + "".join(pts))
    return {"svg": _frame(W, H, f"{ly} vs {lx}", _cap(arm, len(rows), dropped), body,
                          axis_label(y), axis_label(x)),
            "caption": _cap(arm, len(rows), dropped), "n": len(rows), "dropped": dropped}


def _hist(rows, arm, field, dropped):
    W, H = 640, 400
    x0, y0, x1, y1 = 64, 40, W - 20, H - 52
    lab, unit, sc, _pct = FIELDS[field]
    vals = sorted(r[field] * sc for r in rows)
    lo, hi, st = _nice(vals[0], vals[-1])
    nb = 14
    edges = [lo + i * (hi - lo) / nb for i in range(nb + 1)]
    counts = [0] * nb
    for v in vals:
        i = min(nb - 1, int((v - lo) / (hi - lo) * nb)) if hi > lo else 0
        counts[i] += 1
    mx = max(counts) or 1
    bw = (x1 - x0) / nb
    bars = []
    for i, c in enumerate(counts):
        if not c:
            continue
        h = (y1 - y0) * c / mx
        bx, by = x0 + i * bw + 1, y1 - h
        bars.append(f'<path d="M{bx:.1f},{y1} L{bx:.1f},{by+4:.1f} Q{bx:.1f},{by:.1f} {bx+4:.1f},{by:.1f} '
                    f'L{bx+bw-5:.1f},{by:.1f} Q{bx+bw-1:.1f},{by:.1f} {bx+bw-1:.1f},{by+4:.1f} '
                    f'L{bx+bw-1:.1f},{y1} Z" fill="{SERIES[2]}">'
                    f'<title>{edges[i]:.4g}–{edges[i+1]:.4g}: {c} frames</title></path>')
    body = (_axes(x0, y0, x1, y1, lo, hi, st)
            + f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="var(--rule,#dedbd6)"/>'
            + "".join(bars))
    return {"svg": _frame(W, H, f"Distribution of {lab}", _cap(arm, len(rows), dropped), body,
                          "frames", axis_label(field)),
            "caption": _cap(arm, len(rows), dropped), "n": len(rows), "dropped": dropped}


def _by_specimen(rows, arm, field, kind, min_frames, include_thin, dropped):
    from collections import defaultdict
    lab, unit, sc, _pct = FIELDS[field]
    g = defaultdict(list)
    for r in rows:
        g[r.get("specimen", "unparsed")].append(r[field] * sc)
    if not include_thin:
        thin = [k for k, v in g.items() if len(v) < min_frames]
        for k in thin:
            g.pop(k)
        if thin:
            dropped["thin_specimens"] = len(thin)
    if not g:
        raise ValueError(f"every specimen has fewer than {min_frames} fields; "
                         f"tick 'include thin specimens' to plot them anyway")
    keys = sorted(g)
    # LABELS ARE VERTICAL AND THE BOTTOM MARGIN IS COMPUTED FROM THEM.
    #
    # They were rotated -38 degrees into a fixed 120px margin, which reads fine with four
    # specimens and is broken with fourteen: a 38-degree label's horizontal footprint is
    # most of its text length, so at 96px of text on 68px centres they collide. Measured on
    # the real corpus, 10 of 13 consecutive pairs overlapped, by up to 30px across and 80px
    # down -- names sitting on top of each other. It is not obvious in a screenshot, which
    # is why it survived: every label is present and roughly where it belongs, just
    # unreadable where they cross. getBoundingClientRect on the rendered <text> found it.
    #
    # At -90 the footprint is the FONT SIZE rather than the text length, so overlap stops
    # depending on how long the specimen names happen to be -- the one rotation that is
    # correct by construction instead of correct for the corpus in front of me. The cost is
    # vertical space, so the margin is sized from the longest label actually being drawn.
    SHORT = 18
    shorts = {k: (k if len(k) <= SHORT else k[:SHORT - 1] + "…") for k in keys}
    #: ~5.2px per character at font-size 10 for this face, plus the " (n=NN)" tail that is
    #: part of the same text element, plus room for the axis label underneath.
    label_px = max(len(v) + 7 for v in shorts.values()) * 5.2
    bottom = int(min(220, max(96, label_px + 30)))
    W = max(520, 90 + 74 * len(keys))
    H = 350 + bottom
    x0, y0, x1, y1 = 74, 40, W - 20, H - bottom
    allv = [v for vs in g.values() for v in vs]
    lo, hi, st = _nice(min(allv), max(allv))
    bw = (x1 - x0) / len(keys)
    marks = []
    for i, k in enumerate(keys):
        vs = sorted(g[k])
        cx = x0 + bw * (i + 0.5)
        def Y(v):
            return y1 - (v - lo) / (hi - lo) * (y1 - y0)
        if kind == "bar_by_specimen":
            m = sum(vs) / len(vs)
            h = y1 - Y(m)
            marks.append(f'<rect x="{cx-bw*0.3:.1f}" y="{Y(m):.1f}" width="{bw*0.6:.1f}" '
                         f'height="{h:.1f}" rx="4" fill="{SERIES[0]}">'
                         f'<title>{_esc(k)}: mean {m:.4g}, n={len(vs)}</title></rect>')
        else:
            q1 = vs[len(vs) // 4]; q3 = vs[(3 * len(vs)) // 4]; med = vs[len(vs) // 2]
            marks.append(f'<line x1="{cx:.1f}" y1="{Y(vs[0]):.1f}" x2="{cx:.1f}" '
                         f'y2="{Y(vs[-1]):.1f}" stroke="var(--text-muted,#82807a)"/>')
            marks.append(f'<rect x="{cx-bw*0.26:.1f}" y="{Y(q3):.1f}" width="{bw*0.52:.1f}" '
                         f'height="{max(2, Y(q1)-Y(q3)):.1f}" rx="3" fill="{SERIES[0]}" '
                         f'fill-opacity="0.75" stroke="var(--surface-2,#fff)" stroke-width="2">'
                         f'<title>{_esc(k)}: median {med:.4g}, n={len(vs)}</title></rect>')
            marks.append(f'<line x1="{cx-bw*0.26:.1f}" y1="{Y(med):.1f}" x2="{cx+bw*0.26:.1f}" '
                         f'y2="{Y(med):.1f}" stroke="var(--text-primary,#0b0b0b)" stroke-width="2"/>')
        # n goes INSIDE the rotated label. As two separate texts they collided: the rotated
        # name swept through the horizontal n= line at every tick.
        # dominant-baseline centres the label on its tick: after a -90 rotation the
        # baseline runs vertically, so the perpendicular shift is the horizontal one.
        short = shorts[k]
        marks.append(f'<text x="{cx:.1f}" y="{y1+10}" font-size="10" text-anchor="end" '
                     f'dominant-baseline="middle" fill="var(--text-secondary,#52514e)" '
                     f'transform="rotate(-90 {cx:.1f} {y1+10})">{_esc(short)} '
                     f'<tspan fill="var(--text-muted,#82807a)">(n={len(vs)})</tspan></text>')
    body = (_axes(x0, y0, x1, y1, lo, hi, st, horizontal=True)
            + f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="var(--rule,#dedbd6)"/>'
            + "".join(marks))
    what = "mean" if kind == "bar_by_specimen" else "median, IQR, range"
    return {"svg": _frame(W, H, f"{lab} by specimen ({what})",
                          _cap(arm, len(rows), dropped, "specimen is the inferential unit"),
                          body, axis_label(field), ""),
            "caption": _cap(arm, len(rows), dropped), "n": len(rows), "dropped": dropped}


# =======================================================================================
# THE STAGE RASTER, WHICH IS THE ONE PLACE THIS CORPUS HAS REAL SPATIAL STRUCTURE.
#
# WHY THESE TWO FIGURES EXIST. The figure tab offered a scatter, a histogram, and two
# per-specimen summaries -- all of which reduce a specimen to ONE number and then plot
# fourteen of them side by side. A user called them simple bar plots that were not helpful,
# and that is a fair reading: none of them can show the arm's strongest finding, which is
# SPATIAL. "Cracking rises toward one edge of the raster in all 4 positioned specimens"
# (rho +0.750 to +0.867, every one monotonic and significant) cannot be drawn on an axis
# whose categories are specimen names. It needs the stage.
#
# The data is genuinely three-dimensional -- stage X, stage Y, and a measured value -- so
# stage_surface is a 3D render of 3D data rather than a 3D skin on a bar chart. That
# distinction is the whole reason it is defensible here: a perspective bar chart of
# per-specimen means would add a dimension the data does not have, hide the small values
# behind the large ones, and make the reader estimate heights from foreshortened columns.
# Both kinds are offered because they answer different questions: the map is for reading a
# value off a cell, the surface is for seeing the shape of the gradient.
#
# FIELDS, NOT FRAMES, AND ONE MAGNIFICATION. Nine fields per specimen at 51.883 nm/px, each
# imaged through both CBS and ETD at BYTE-IDENTICAL stage coordinates. Plotting frames would
# draw every cell twice, once per detector, with the two detectors differing 2.29x on the
# same physical field -- which is how a previous version of this corpus doubled every point
# and made every p-value up to 27x too small. The 337.2396 nm/px overview field is excluded
# for a different reason: its field of view is 10.6x a fine field's and spans much of the
# raster, so it has no position comparable to theirs.

def _stage_mod():
    """The analysis/stage module, or None. One import site, used by the cell builder and by
    the drawn-row filter -- two copies of this path juggling is how they would drift."""
    import sys
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analysis")
    if d not in sys.path:
        sys.path.insert(0, d)
    try:
        import stage as _s
        return _s
    except Exception:
        return None


def _stage_pos(stem):
    m = _stage_mod()
    return m.position(stem) if m else None


#: Below this many positioned fields a raster panel is not a raster.
STAGE_MIN_FIELDS = 4


def _stage_cells(rows):
    """{specimen: [(col, row, value, n_fields)]} on the modal magnification, plus the
    magnification used. Returns ({}, None) when no frame carries a stage position.

    Grid indices come from CLUSTERING the stage coordinates along each axis, not from
    ranking the distinct values and not from dividing the extent. stage.position()
    deliberately refuses to assert that the stage unit is the metre, so no physical spacing
    may be assumed -- but ranking distinct values is wrong for a different reason, and
    stage.py says so in its own docstring: "the nine fields of a 3x3 raster differ in the
    sixth place, so every field lands in its own group". Ranking therefore produced a 7x9
    grid holding nine cells strung along a diagonal, with every cell in a row of its own.
    It rendered, it looked deliberate, and it was not a raster.

    The real structure is three tight clusters per axis: on MAR_AmbB_AS the X values sit in
    groups separated by 4.3e-4 with 5e-6 of jitter inside a group, and Y likewise. So the
    between-group gap is one to two orders of magnitude larger than the within-group
    scatter, and a gap-based split is both robust and free of any assumed grid size --
    which matters because nothing guarantees the next batch is 3x3.
    """
    _stage = _stage_mod()
    if _stage is None:
        return {}, None

    from collections import Counter
    placed = []
    for r in rows:
        pos = _stage.position(r.get("frame", ""))
        if pos and r.get("nm_per_px"):
            placed.append((r, pos, round(float(r["nm_per_px"]), 4)))
    if not placed:
        return {}, None
    modal = Counter(m for _, _, m in placed).most_common(1)[0][0]
    placed = [(r, pos) for r, pos, m in placed if m == modal]

    by_spec = {}
    for r, pos in placed:
        by_spec.setdefault(r.get("specimen", "unparsed"), {}).setdefault(
            (round(pos[0], 6), round(pos[1], 6)), []).append(r)

    out = {}
    for spec, cells in by_spec.items():
        if len(cells) < STAGE_MIN_FIELDS:
            continue
        xi = _axis_clusters([k[0] for k in cells])
        yi = _axis_clusters([k[1] for k in cells])
        if xi is None or yi is None:
            continue
        out[spec] = [(xi[k[0]], yi[k[1]], v, _cell_frames(v)) for k, v in cells.items()]
    return out, modal


#: A raster axis with more than this many positions is not being drawn as cells.
STAGE_MAX_STEPS = 8


def _axis_clusters(vals):
    """{value: index} grouping one axis into its raster steps, or None if it has no steps.

    Splits where the gap between neighbouring coordinates exceeds half the largest gap.
    That rule is scale-free -- it needs no tolerance in instrument units, which is the
    point, since those units are not asserted to be anything -- and it recovers 3 steps
    from coordinates whose within-step jitter is 5e-6 against a 4.3e-4 step.
    """
    uniq = sorted(set(vals))
    if len(uniq) == 1:
        return {uniq[0]: 0}
    gaps = [b - a for a, b in zip(uniq, uniq[1:])]
    cut = max(gaps) / 2.0
    if cut <= 0:
        return {v: 0 for v in uniq}
    idx, k = {uniq[0]: 0}, 0
    for a, b in zip(uniq, uniq[1:]):
        if (b - a) > cut:
            k += 1
        idx[b] = k
    # A degenerate split -- every value its own step -- means this is not a raster, and
    # drawing one cell per value would invent a grid. Say nothing rather than draw it.
    if k + 1 > STAGE_MAX_STEPS or k == 0:
        return None if k + 1 > STAGE_MAX_STEPS else idx
    return idx


def _stage_value(frs, field, sc):
    """One value per stage cell.

    THE DETECTOR AVERAGE ALREADY HAPPENED, upstream in _collapse_to_fields, which means an
    earlier version of this comment was wrong about its own data flow: it claimed the mean
    over CBS and ETD was taken here, and by the time these rows arrive each physical field
    is already a single row carrying the mean and a _n_frames_in_field count. The visible
    symptom was the caption's detector clause disappearing entirely -- every cell reported
    one contributing row, so the figure stopped saying that 2 of its inputs were two
    instruments averaged. Read _n_frames_in_field for that, not the row count.

    The mean here is therefore only for the case of two DIFFERENT fields landing on one
    stage coordinate, which is not a detector pair and should stay visible as a count.
    """
    vals = [f[field] * sc for f in frs if f.get(field) is not None]
    return (sum(vals) / len(vals)) if vals else float("nan")


def _cell_frames(frs):
    """How many original FRAMES stand behind a cell, across the rows that landed on it."""
    return sum(int(f.get("_n_frames_in_field") or 1) for f in frs)


def _stage_panels(rows, arm, field, dropped, kind):
    lab, unit, sc, _pct = FIELDS[field]
    cells, modal = _stage_cells(rows)
    if not cells:
        raise ValueError(
            "no frame in this arm carries a stage position, so there is nothing to place "
            "on a raster. Only the 2026-09-15 MAR batch recorded stage coordinates.")

    specs = sorted(cells)
    flat = [(s, c, r, _stage_value(v, field, sc), n) for s in specs
            for (c, r, v, n) in cells[s]]
    flat = [t for t in flat if t[3] == t[3]]
    if not flat:
        raise ValueError(f"every positioned field is missing {lab}")
    lo = min(t[3] for t in flat)
    hi = max(t[3] for t in flat)
    span = (hi - lo) or 1.0
    ncols = max(t[1] for t in flat) + 1
    nrows = max(t[2] for t in flat) + 1
    #: Reported so the caption can say a cell is an average of two instruments.
    doubled = sum(1 for t in flat if t[4] > 1)

    if kind == "stage_map":
        body, W, H = _stage_map_body(specs, flat, ncols, nrows, lo, span, unit)
        title = f"{lab} across the stage raster"
        xlab = "stage X (instrument units, rank order)"
    else:
        body, W, H = _stage_surface_body(specs, flat, ncols, nrows, lo, span)
        title = f"{lab} across the stage raster (height = value)"
        xlab = "stage X →   stage Y ↗   (instrument units, rank order)"

    extra = (f"one cell = one field at {modal} nm/px"
             + (f"; {doubled} of {len(flat)} cells average two detectors"
                if doubled else "")
             + "; stage units are the instrument's and are not asserted to be millimetres")
    # n IS WHAT THE FIGURE DRAWS, not what the arm holds. _cap(arm, len(rows), ...) would
    # print "n = 86 fields" under a panel set built from the 36 that carry a stage
    # position -- a number attached to the wrong object, which is the defect the "7
    # specimens" clause had in this same function one release earlier.
    drew = dict(dropped)
    unplaced = len(rows) - len(flat)
    if unplaced > 0:
        drew["no_stage_position"] = unplaced
    # EVERY COUNT IN THE CAPTION IS ABOUT THE DRAWN SUBSET, not the arm. Inheriting these
    # keys unchanged printed "7 of 14 specimens average two detectors" under a panel set
    # showing FOUR -- the same wrong-denominator error in the same caption as the clause
    # that was just fixed to say "7 of 14" in the first place. Fixing one instance of a
    # defect does not fix the mechanism that produced it.
    drew["_n_specimens"] = len(specs)
    # Rescoped, not dropped: the reader needs to know a cell is a FIELD rather than a
    # frame, but with this figure's own numbers rather than the arm's.
    n_src = sum(t[4] for t in flat)
    drew["_collapsed"] = (n_src, len(flat)) if n_src != len(flat) else None
    if drew["_collapsed"] is None:
        drew.pop("_collapsed")
    dbl = {s for (s, c, r, v, n) in flat if n > 1}
    if dbl:
        drew["_mixed_detectors"] = sorted(dbl)
    else:
        drew.pop("_mixed_detectors", None)
    cap = _cap(arm, len(flat), drew, extra)
    #: Exactly the rows behind the cells: positioned, at the modal magnification, and in a
    #: specimen whose raster was large enough to draw. Read by _with_rows.
    drawn = [r for r in rows
             if r.get("specimen") in cells and r.get("nm_per_px")
             and round(float(r["nm_per_px"]), 4) == modal
             and _stage_pos(r.get("frame", ""))]
    return {"svg": _frame(W, H, title, cap, body, f"{lab}{(' ' + unit) if unit else ''}", xlab),
            "caption": _cap(arm, len(flat), drew), "n": len(flat), "dropped": drew,
            "_drawn_rows": drawn}


def _legend(x, y, lo, span, unit, w=104):
    """Five swatches with the ends labelled. Always present: the cells carry no numbers of
    their own in the surface view, so colour is the only channel there."""
    out = [f'<text x="{x}" y="{y - 6}" font-size="10" '
           f'fill="var(--text-secondary,#52514e)">{_esc(unit or "value")}</text>']
    sw = w / len(RAMP)
    for i, c in enumerate(RAMP):
        out.append(f'<rect x="{x + i * sw:.1f}" y="{y}" width="{sw - 2:.1f}" height="9" '
                   f'rx="2" fill="{c}"/>')
    out.append(f'<text x="{x}" y="{y + 21}" font-size="9" '
               f'fill="var(--text-muted,#82807a)">{lo:.4g}</text>')
    out.append(f'<text x="{x + w}" y="{y + 21}" font-size="9" text-anchor="end" '
               f'fill="var(--text-muted,#82807a)">{lo + span:.4g}</text>')
    return "".join(out)


def _stage_map_body(specs, flat, ncols, nrows, lo, span, unit):
    """Small multiples: one panel per specimen, one cell per field, value printed in it.

    Direct labels on every cell, which is normally the wrong default -- but there are only
    nine per panel, and the entire point is to let a reader see the value RISE down the
    column rather than infer it from a colour.
    """
    CELL, GAP, PAD = 46, 3, 20
    pw = ncols * (CELL + GAP)
    ph = nrows * (CELL + GAP)
    cols = min(len(specs), 4)
    rows_of = (len(specs) + cols - 1) // cols
    W = max(560, PAD * 2 + cols * (pw + 34))
    H = 58 + rows_of * (ph + 46) + 58
    out = []
    for i, spec in enumerate(specs):
        px = PAD + (i % cols) * (pw + 34)
        py = 46 + (i // cols) * (ph + 46)
        out.append(f'<text x="{px}" y="{py - 8}" font-size="11" font-weight="620" '
                   f'fill="var(--text-primary,#0b0b0b)">{_esc(spec)}</text>')
        for (s, c, r, v, n) in flat:
            if s != spec:
                continue
            # Row 0 is the LOWEST stage Y, drawn at the BOTTOM, so "rises toward one edge"
            # is a visible direction on the page rather than an inverted one.
            cx = px + c * (CELL + GAP)
            cy = py + (nrows - 1 - r) * (CELL + GAP)
            t = (v - lo) / span
            dark = t > 0.55
            out.append(
                f'<rect x="{cx}" y="{cy}" width="{CELL}" height="{CELL}" rx="4" '
                f'fill="{_ramp(t)}" stroke="var(--surface-2,#fff)" stroke-width="2">'
                f'<title>{_esc(spec)} col {c + 1} row {r + 1}: {v:.4g}'
                f'{" (2 detectors)" if n > 1 else ""}</title></rect>')
            out.append(
                f'<text x="{cx + CELL / 2:.1f}" y="{cy + CELL / 2 + 3.5:.1f}" font-size="9.5" '
                f'text-anchor="middle" font-weight="600" '
                f'fill="{"#fff" if dark else "#0b0b0b"}">{v:.3g}</text>')
    out.append(_legend(W - 150, H - 46, lo, span, unit))
    return "".join(out), W, H


def _stage_surface_body(specs, flat, ncols, nrows, lo, span):
    """An axonometric column per field: footprint on the stage, height = value.

    HEIGHT IS NORMALISED WITHIN EACH PANEL, NOT ACROSS THEM, and that is a correctness
    choice rather than a cosmetic one. On one shared scale this figure showed exactly the
    wrong thing: the four specimens' maxima run 1.79 to 12.0, so three panels collapsed to
    nearly flat tiles and the only structure left visible was the difference BETWEEN
    specimens -- which is the one comparison this app refuses to support, because each
    specimen is a single imaged site and material difference cannot be separated from site
    difference. Meanwhile the within-patch gradient, which IS established (every raster
    monotonic, rho +0.833 to +0.883), was the part being flattened away.
    So each panel is scaled to its own range and prints it, which makes the supported
    finding legible and declines to invite the unsupported one.

    A TRUE AXONOMETRIC PROJECTION, NOT PERSPECTIVE. Parallel projection keeps equal values
    equal in height anywhere in the panel, so two columns can be compared by eye; under
    perspective the far ones would be smaller and the figure would misreport its own data.

    DRAWN BACK TO FRONT. Painter's order is not cosmetic here -- a near column drawn first
    would be overpainted by the one behind it, and the taller a column is the more of its
    neighbour it hides. Sorting by (row + col) descending puts the far cells down first.
    """
    CELL, HMAX, PAD = 30, 76, 24
    DX, DY = 0.86, -0.5            # unit step along stage X
    EX, EY = 0.86, 0.5             # unit step along stage Y (into the page)
    pw = (ncols + nrows) * CELL * DX + 40
    ph = (ncols + nrows) * CELL * 0.5 + HMAX + 46
    cols = min(len(specs), 2)
    rows_of = (len(specs) + cols - 1) // cols
    W = max(620, PAD * 2 + cols * (pw + 26))
    H = 58 + rows_of * (ph + 30) + 58

    def shade(hexc, f):
        r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
        return "#%02x%02x%02x" % tuple(min(255, max(0, int(c * f))) for c in (r, g, b))

    out = []
    for i, spec in enumerate(specs):
        ox = PAD + (i % cols) * (pw + 26) + nrows * CELL * EX * 0.5
        oy = 58 + (i // cols) * (ph + 30) + HMAX + nrows * CELL * 0.5
        out.append(f'<text x="{ox - nrows * CELL * EX * 0.5:.1f}" y="{oy - HMAX - nrows * CELL * 0.5 - 8:.1f}" '
                   f'font-size="11" font-weight="620" '
                   f'fill="var(--text-primary,#0b0b0b)">{_esc(spec)}</text>')
        mine = [t for t in flat if t[0] == spec]
        p_lo = min(t[3] for t in mine)
        p_hi = max(t[3] for t in mine)
        p_span = (p_hi - p_lo) or 1.0
        # The panel's own range, printed, because per-panel scaling means the heights are
        # no longer readable against a shared legend.
        out.append(f'<text x="{ox - nrows * CELL * EX * 0.5:.1f}" '
                   f'y="{oy - HMAX - nrows * CELL * 0.5 + 5:.1f}" font-size="9" '
                   f'fill="var(--text-muted,#82807a)">{p_lo:.3g} \u2013 {p_hi:.3g}</text>')
        for (s, c, r, v, n) in sorted(mine, key=lambda t: -(t[1] + t[2])):
            t = (v - p_lo) / p_span
            h = 4 + t * HMAX
            bx = ox + c * CELL * DX + r * CELL * EX
            by = oy + c * CELL * DY + r * CELL * EY
            top = shade(_ramp(t), 1.0)
            left = shade(_ramp(t), 0.74)
            right = shade(_ramp(t), 0.56)
            # Top face, then the two visible side faces.
            p_top = (f"{bx:.1f},{by - h:.1f} "
                     f"{bx + CELL * DX:.1f},{by + CELL * DY - h:.1f} "
                     f"{bx + CELL * DX + CELL * EX:.1f},{by + CELL * DY + CELL * EY - h:.1f} "
                     f"{bx + CELL * EX:.1f},{by + CELL * EY - h:.1f}")
            p_l = (f"{bx:.1f},{by - h:.1f} {bx + CELL * EX:.1f},{by + CELL * EY - h:.1f} "
                   f"{bx + CELL * EX:.1f},{by + CELL * EY:.1f} {bx:.1f},{by:.1f}")
            p_r = (f"{bx + CELL * EX:.1f},{by + CELL * EY - h:.1f} "
                   f"{bx + CELL * DX + CELL * EX:.1f},{by + CELL * DY + CELL * EY - h:.1f} "
                   f"{bx + CELL * DX + CELL * EX:.1f},{by + CELL * DY + CELL * EY:.1f} "
                   f"{bx + CELL * EX:.1f},{by + CELL * EY:.1f}")
            tip = (f'<title>{_esc(spec)} col {c + 1} row {r + 1}: {v:.4g}'
                   f'{" (2 detectors)" if n > 1 else ""}</title>')
            for pts, fill in ((p_l, left), (p_r, right), (p_top, top)):
                out.append(f'<polygon points="{pts}" fill="{fill}" '
                           f'stroke="var(--surface-2,#fff)" stroke-width="0.8">{tip}</polygon>')
    # NO SHARED LEGEND HERE. Heights and colours are per panel, so one ramp spanning the
    # global range would be a legend for a scale no column is drawn on.
    out.append(f'<text x="{PAD}" y="{H - 44}" font-size="10" '
               f'fill="var(--text-muted,#82807a)">each panel is scaled to its own range, '
               f'shown under its name \u2014 heights compare WITHIN a specimen, not between '
               f'them</text>')
    return "".join(out), W, H
