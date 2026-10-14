#!/usr/bin/env python3
"""The pipeline flow diagram as a PDF -- one real image per stage.

A PDF, not a web page: this is a figure to print, attach to a chapter and hand to someone,
and a folder of HTML plus two dozen loose PNGs is none of those. The panels are the same
arrays make_flowchart.py already measured and wrote, so there is ONE measurement and two
renderers rather than two measurements that can disagree.

Text is vector text (selectable and searchable); only the micrograph panels are raster,
which they are by nature. Nothing here recomputes a number -- the prose is taken from the
page make_flowchart.py wrote and the header figures from _stats.json, so the PDF cannot
drift from the measurement that produced the panels.

reportlab is not installed in either venv (which also means paper/figures/mkpdf.py cannot
currently run), so this uses matplotlib's PdfPages.
"""
import html as _html
import json
import os
import re
import sys
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.image import imread

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "pipeline_flow.pdf")
ST = json.load(open(os.path.join(HERE, "_stats.json"), encoding="utf-8"))

A4 = (8.27, 11.69)
INK, MUTED = "#1a1a1a", "#5a5a5a"
MIN_PT = 6.0          # nothing on the plate may be smaller; asserted before saving


def strip(s, br=" "):
    s = re.sub(r"<br\s*/?>", br, s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def stages():
    """The stages, their prose and their panels, from flow_content.json.

    That file is the content record. It was extracted once from the HTML page this
    directory used to ship and the page was then removed: the deliverable is the PDF, and
    keeping a web page alive purely as a parsing source for it is a second artifact to
    drift. Panels still come from make_flowchart.py's measured arrays.
    """
    cj = os.path.join(HERE, "flow_content.json")
    if os.path.exists(cj):
        return [dict(title=s["title"], does=s["does"], cost=s["cost"], note=s["note"],
                     figs=[tuple(f) for f in s["figs"]])
                for s in json.load(open(cj, encoding="utf-8"))]
    h = open(os.path.join(HERE, "index.html"), encoding="utf-8").read()
    out = []
    for blk in re.split(r'(?=<section class="step)', h)[1:]:
        head = re.search(r"<h2[^>]*>(.*?)</h2>", blk, re.S)
        if not head:
            continue
        title = re.sub(r"^[●\d]+", "", strip(head.group(1))).strip()
        out.append(dict(
            title=title,
            does=[strip(x) for x in re.findall(r'<p class="does">(.*?)</p>', blk, re.S)],
            cost=[strip(x) for x in re.findall(r'<p class="cost">(.*?)</p>', blk, re.S)],
            note=[strip(x) for x in re.findall(r'<div class="note[^"]*">(.*?)</div>', blk, re.S)],
            figs=[(m.group(1), strip(m.group(2), br="  \u00b7  ")) for m in re.finditer(
                r'<img src="([^"]+)"[^>]*>\s*<figcaption>(.*?)</figcaption>', blk, re.S)],
        ))
    return out


def wrap(ax, y, text, size, color=INK, weight="normal", width=108, style="normal"):
    """Draw wrapped text from the top down and return the new y, in axes fraction."""
    for line in textwrap.wrap(text, width=width) or [""]:
        ax.text(0, y, line, fontsize=size, color=color, fontweight=weight,
                fontstyle=style, va="top", ha="left", transform=ax.transAxes)
        y -= (size + 3.1) / 720.0
    return y - 0.004


def build():
    sts = stages()
    if not sts:
        sys.exit("no stages parsed from index.html -- refusing to write an empty PDF")
    sizes = []
    with PdfPages(OUT) as pdf:
        # --- cover / provenance -------------------------------------------------------
        fig = plt.figure(figsize=A4); fig.patch.set_facecolor("white")
        ax = fig.add_axes([0.08, 0.06, 0.84, 0.88]); ax.axis("off")
        y = 1.0
        ax.text(0, y, "The shipped crack detector", fontsize=19, fontweight="bold",
                color=INK, va="top", transform=ax.transAxes); sizes.append(19)
        y -= 0.034
        ax.text(0, y, "one real image per stage", fontsize=13, color=MUTED, va="top",
                transform=ax.transAxes); sizes.append(13)
        y -= 0.040
        ax.plot([0, 1], [y, y], lw=0.8, color="#c8c8c8", transform=ax.transAxes,
                clip_on=False)
        y -= 0.024
        hdr = (f"Frame {ST['frame']}. Window {ST['crop_px']:,} px of the frame's "
               f"{ST['frame_px']:,}. Every panel is a real array from the real pipeline: "
               f"no mock-ups, no schematic boxes standing in for an image.")
        y = wrap(ax, y, hdr, 9.4); sizes.append(9.4)
        y -= 0.010
        y = wrap(ax, y, "Why this frame. " + strip(ST["pick_why"]), 9.0, color=MUTED)
        sizes.append(9.0)
        y -= 0.016
        cfg = (f"Configuration: mad_k 5.0, absolute_dark_thresh 10, ladder "
               f"(5,10,20,40,80,160,320), decimate above sigma 64, clean_mask min_area 13, "
               f"region floor 40 px, USE_REGION_CLASSIFIER False.")
        y = wrap(ax, y, cfg, 8.6, color=MUTED); sizes.append(8.6)
        y -= 0.018
        p = os.path.join(HERE, "p00_frame.png")
        if os.path.exists(p):
            im = imread(p)
            top = 0.06 + 0.88 * y - 0.004
            axi = fig.add_axes([0.08, 0.075, 0.84, top - 0.075])
            axi.imshow(im); axi.axis("off")
            axi.set_title("The whole frame; the window every other panel shows is marked",
                          fontsize=8.2, color=MUTED, pad=4); sizes.append(8.2)
        pdf.savefig(fig); plt.close(fig)

        # --- one page per stage -------------------------------------------------------
        for i, st in enumerate(sts, 1):
            fig = plt.figure(figsize=A4); fig.patch.set_facecolor("white")
            ax = fig.add_axes([0.08, 0.06, 0.84, 0.88]); ax.axis("off")
            y = 1.0
            ax.text(0, y, f"{i}.  {st['title']}", fontsize=12.5, fontweight="bold",
                    color=INK, va="top", transform=ax.transAxes); sizes.append(12.5)
            y -= 0.030
            for d in st["does"]:
                y = wrap(ax, y, d, 9.2); sizes.append(9.2)
            for c in st["cost"]:
                y = wrap(ax, y, c, 8.8, color=MUTED, style="italic"); sizes.append(8.8)
            for n in st["note"]:
                y = wrap(ax, y, "Note. " + n, 8.8, color=INK); sizes.append(8.8)
            figs = st["figs"][:8]
            if figs:
                ncol = 1 if len(figs) == 1 else (2 if len(figs) <= 4 else 4)
                nrow = (len(figs) + ncol - 1) // ncol
                top = 0.06 + 0.88 * y - 0.004
                avail = top - 0.072
                ph = avail / nrow
                pw = 0.84 / ncol
                for k, (fn, cap) in enumerate(figs):
                    pth = os.path.join(HERE, fn)
                    if not os.path.exists(pth):
                        continue
                    r, c = divmod(k, ncol)
                    cs = 7.6 if ncol <= 2 else 6.6
                    lines = textwrap.wrap(cap, 52 if ncol <= 2 else 30)[:5]
                    caph = len(lines) * (cs + 2.4) / 720.0
                    arr = imread(pth)
                    aw = pw * 0.94
                    # height this width implies, in figure fraction, from the real aspect
                    ah = aw * (arr.shape[0] / arr.shape[1]) * (A4[0] / A4[1])
                    ah = min(ah, ph - caph - 0.016)
                    aw = ah / ((arr.shape[0] / arr.shape[1]) * (A4[0] / A4[1]))
                    cell_top = top - r * ph
                    axi = fig.add_axes([0.08 + c * pw, cell_top - ah - 0.004, aw, ah])
                    axi.imshow(arr); axi.axis("off")
                    fig.text(0.08 + c * pw, cell_top - ah - 0.010,
                             "\n".join(lines), fontsize=cs, color=MUTED,
                             va="top", ha="left")
                    sizes.append(cs)
            pdf.savefig(fig); plt.close(fig)

        d = pdf.infodict()
        d["Title"] = "Crack detector pipeline, stage by stage"
        d["Author"] = "Jiaming Zhang"
        d["Subject"] = f"v1.49.2 on {ST['frame']}"

    smallest = min(sizes)
    assert smallest >= MIN_PT, f"type as small as {smallest} pt -- below the {MIN_PT} pt floor"
    print(f"wrote {OUT}")
    print(f"  {len(sts) + 1} pages, {os.path.getsize(OUT)/1024:.0f} KB, "
          f"smallest type {smallest} pt (floor {MIN_PT})")
    return OUT


if __name__ == "__main__":
    build()
