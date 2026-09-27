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
    "mcl_um":                   ("Longest crack (MCL)", "µm", 1.0, ""),
    "tcl_um":                   ("Total crack length (TCL)", "µm", 1.0, ""),
    "R_L_median":               ("R_L (median)", "", 1.0, ""),
    "mean_width_px_median":     ("Median mean-width", "px", 1.0, ""),
    "n_junctions":              ("Junctions", "", 1.0, ""),
    "censored_share":           ("Area touching frame edge", "", 100.0, "%"),
    "area_analysed_mm2":        ("Area analysed", "mm²", 1.0, ""),
    "crack_area_px":            ("Crack area", "px", 1.0, ""),
}
#: Fields that only exist once a physical scale is known.
NEEDS_SCALE = {"p21_skeleton_mm_per_mm2", "p20_per_mm2", "mcl_um", "tcl_um", "area_analysed_mm2"}

KINDS = ("scatter", "box_by_specimen", "bar_by_specimen", "histogram")


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

    if kind == "histogram":
        return _hist(rows, arm, y or x, dropped)
    if kind == "scatter":
        if not (x and y):
            raise ValueError("a scatter needs both x and y")
        return _scatter(rows, arm, x, y, dropped)
    return _by_specimen(rows, arm, y or x, kind, min_frames, include_thin, dropped)


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
    if dropped.get("thin_specimens"):
        bits.append(f"{dropped['thin_specimens']} specimens hidden: under 3 fields")
    # Said out loud, because a box built from two detectors that differ by 2.29x on the
    # same physical field is showing instrument spread as if it were material spread.
    if dropped.get("_mixed_detectors"):
        m = dropped["_mixed_detectors"]
        bits.append(f"{len(m)} specimens average two detectors per field "
                    f"(CBS reads ~2.3x ETD; the spread is partly instrument)")
    if extra:
        bits.append(extra)
    return "  ·  ".join(bits)


def _scatter(rows, arm, x, y, dropped):
    W, H = 640, 420
    x0, y0, x1, y1 = 64, 40, W - 20, H - 52
    lx, ux, sx, _ = FIELDS[x]
    ly, uy, sy, _ = FIELDS[y]
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
                          f"{ly}{(' ' + uy) if uy else ''}", f"{lx}{(' ' + ux) if ux else ''}"),
            "caption": _cap(arm, len(rows), dropped), "n": len(rows), "dropped": dropped}


def _hist(rows, arm, field, dropped):
    W, H = 640, 400
    x0, y0, x1, y1 = 64, 40, W - 20, H - 52
    lab, unit, sc, _ = FIELDS[field]
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
                          "frames", f"{lab}{(' ' + unit) if unit else ''}"),
            "caption": _cap(arm, len(rows), dropped), "n": len(rows), "dropped": dropped}


def _by_specimen(rows, arm, field, kind, min_frames, include_thin, dropped):
    from collections import defaultdict
    lab, unit, sc, _ = FIELDS[field]
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
    W = max(520, 90 + 74 * len(keys))
    H = 470
    x0, y0, x1, y1 = 74, 40, W - 20, H - 120
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
        short = k if len(k) <= 15 else k[:14] + "…"
        marks.append(f'<text x="{cx:.1f}" y="{y1+14}" font-size="10" text-anchor="end" '
                     f'fill="var(--text-secondary,#52514e)" '
                     f'transform="rotate(-38 {cx:.1f} {y1+14})">{_esc(short)} '
                     f'<tspan fill="var(--text-muted,#82807a)">(n={len(vs)})</tspan></text>')
    body = (_axes(x0, y0, x1, y1, lo, hi, st, horizontal=True)
            + f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="var(--rule,#dedbd6)"/>'
            + "".join(marks))
    what = "mean" if kind == "bar_by_specimen" else "median, IQR, range"
    return {"svg": _frame(W, H, f"{lab} by specimen ({what})",
                          _cap(arm, len(rows), dropped, "specimen is the inferential unit"),
                          body, f"{lab}{(' ' + unit) if unit else ''}", ""),
            "caption": _cap(arm, len(rows), dropped), "n": len(rows), "dropped": dropped}
