"""Typeset the paper as a PDF: real text, real tables, figures at first reference.

Single column by deliberate choice. The paper carries eight tables, several of them wide,
and a two-column measure would either break them or shrink them below legibility; a
submission draft is single-column anyway. Everything is vector/selectable except the
figures, which are raster by nature.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import io, os, re, glob, json, datetime
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Image, Table, TableStyle, KeepTogether, HRFlowable,
                                PageBreak, NextPageTemplate)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

SEC = os.path.join(_paths.PAPER_DIR, "sections")
FIGD = _paths.FIG_DIR
OUT = os.path.join(_paths.PAPER_DIR, "Crack Fractography - paper draft.pdf")

# --- fonts: a serif for the body, because this is a paper ---
FB, FI, FBD, FM = "Times-Roman", "Times-Italic", "Times-Bold", "Courier"
for name, path in (("Body", "/System/Library/Fonts/Supplemental/Times New Roman.ttf"),
                   ("Body-It", "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf"),
                   ("Body-Bd", "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf")):
    try:
        pdfmetrics.registerFont(TTFont(name, path))
    except Exception:
        pass
if "Body" in pdfmetrics.getRegisteredFontNames():
    FB, FI, FBD = "Body", "Body-It", "Body-Bd"
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily("Body", normal="Body", bold="Body-Bd", italic="Body-It",
                       boldItalic="Body-Bd")

# Times New Roman has NO GLYPH for U+26A0 (the references' incompleteness flag) and
# none for U+207B or U+2070-2079 (superscript minus and digits). A missing glyph is
# dropped silently, which turned "3.3 x 10^-16" into "3.3 x 10 1" in an earlier
# build -- a sign-inverted number, not a cosmetic defect. Two fixes below: route the
# warning sign through a font that has it, and rebuild every exponent out of <super>.
FSYM = None
for _p in ("/System/Library/Fonts/Supplemental/Apple Symbols.ttf",
           "/System/Library/Fonts/Apple Symbols.ttf"):
    try:
        pdfmetrics.registerFont(TTFont("Sym", _p))
        FSYM = "Sym"
        break
    except Exception:
        pass

# Courier New as a TTF rather than the built-in Type1 "Courier": not for looks, but
# so that the coverage check below can read its cmap. A Type1 font has no face to
# introspect, and a guard that cannot see a font is a guard with a blind spot.
try:
    pdfmetrics.registerFont(TTFont("Mono", "/System/Library/Fonts/Supplemental/Courier New.ttf"))
    FM = "Mono"
except Exception:
    pass

SUP = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
       "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
       "⁺": "+", "⁻": "−", "⁼": "=", "⁽": "(",
       "⁾": ")", "ⁿ": "n"}
SUP_RE = re.compile("[" + "".join(SUP) + "]+")

INK = colors.HexColor("#1a1a1c")
MUT = colors.HexColor("#5a5a62")
RULE = colors.HexColor("#c8c8c4")
ACC = colors.HexColor("#8c2a2a")

S = dict(
    title=ParagraphStyle("title", fontName=FBD, fontSize=19, leading=24, spaceAfter=10,
                         textColor=INK, alignment=TA_LEFT),
    author=ParagraphStyle("author", fontName=FB, fontSize=11, leading=15, spaceAfter=3,
                          textColor=MUT),
    h1=ParagraphStyle("h1", fontName=FBD, fontSize=13.5, leading=17, spaceBefore=16,
                      spaceAfter=7, textColor=INK, keepWithNext=1),
    h2=ParagraphStyle("h2", fontName=FBD, fontSize=11.5, leading=15, spaceBefore=12,
                      spaceAfter=5, textColor=INK, keepWithNext=1),
    h3=ParagraphStyle("h3", fontName=FI, fontSize=10.5, leading=14, spaceBefore=9,
                      spaceAfter=4, textColor=INK, keepWithNext=1),
    body=ParagraphStyle("body", fontName=FB, fontSize=10, leading=14.2, spaceAfter=7,
                        textColor=INK, alignment=TA_JUSTIFY),
    abstract=ParagraphStyle("abstract", fontName=FB, fontSize=9.5, leading=13.4,
                            spaceAfter=7, textColor=INK, alignment=TA_JUSTIFY,
                            leftIndent=8*mm, rightIndent=8*mm),
    li=ParagraphStyle("li", fontName=FB, fontSize=10, leading=14.2, spaceAfter=4,
                      textColor=INK, alignment=TA_JUSTIFY, leftIndent=7*mm,
                      bulletIndent=2*mm),
    cap=ParagraphStyle("cap", fontName=FB, fontSize=8.6, leading=11.6, spaceBefore=4,
                       spaceAfter=12, textColor=MUT, alignment=TA_LEFT),
    figcap=ParagraphStyle("figcap", fontName=FB, fontSize=9, leading=12.2,
                          textColor=INK, alignment=TA_JUSTIFY),
    note=ParagraphStyle("note", fontName=FB, fontSize=8.6, leading=11.8, spaceAfter=5,
                        textColor=MUT, alignment=TA_LEFT, leftIndent=4*mm, rightIndent=4*mm),
    cell=ParagraphStyle("cell", fontName=FB, fontSize=8.2, leading=10.6, textColor=INK),
    cellh=ParagraphStyle("cellh", fontName=FBD, fontSize=8.2, leading=10.6, textColor=INK),
    figkey=ParagraphStyle("figkey", fontName=FB, fontSize=8.2, leading=11.0, spaceBefore=3,
                          textColor=INK, alignment=TA_JUSTIFY),
    figext=ParagraphStyle("figext", fontName=FB, fontSize=8.2, leading=11.0, spaceBefore=4,
                          textColor=MUT, alignment=TA_JUSTIFY),
)

# Smallest type a figure may carry at final print size. The plates previously ran to
# 2.45 pt because they were sized by aspect ratio alone; the check at the bottom of
# fig_block() refuses to emit a figure below this.
MIN_FIG_PT = 6.0

FIGCAP = {
    # DEAD VALUES, KEYS ONLY. Each is overwritten from the `lead` of the caption JSON that
    # the figure's own generator writes beside its PNG, so a caption cannot drift from the
    # figure. A real caption here would be shadowed silently; a placeholder cannot be.
    n: "placeholder -- overwritten from the caption json beside the png"
    for n in (1, 2, 3, 4, 5, 6)
}
FIGFILE = {
 1: "1 - what each stage does.png",
 2: "2 - what the models are made of.png",
 3: "3 - method comparison, identical data.png",
 4: "4 - transfer, the class list does not say.png",
 5: "5 - TXM, what each stage adds.png",
 6: "6 - SEM, where the model differs.png",
}

# Each figure is placed inline, immediately after the paragraph that first cites it.
# `anchor` is the verbatim tail of that paragraph, matched on normalised whitespace.
# `min_px` is the smallest type the generator draws, in source pixels; fig_block scales
# it to the final width and refuses the figure if it lands below MIN_FIG_PT.
# `orient` is "body" for a figure that fits the text column and "land" for one that
# needs its own landscape page.
FIGURES = {
 n: dict(file=FIGFILE[n], lead=FIGCAP[n], panel_key="", extended=[],
         section="", anchor="", orient="body", min_px=13 if n <= 2 else 15)
 for n in FIGFILE
}

# All six figures now set in the text column. Two were reflowed to get there rather than
# being shrunk into it: Figure 1 from 8 panels per row to 4 (2,782 -> 1,382 px, and LARGER
# panels than a landscape page would have given it), and Figure 2 from two side-by-side
# arms to one stacked column (2,782 -> 1,448 px). The required source type size scales with
# the image WIDTH, so narrowing the image is what buys legibility -- enlarging the fonts
# alone cannot, since it widens the image by the same factor.
# The landscape template is kept for any future plate that genuinely needs it.

# Each generator writes its caption beside its PNG, with every number resolved in the scope
# that computed it. That is the point: a caption built here would have to re-derive values
# the generator already holds, and the f-string templates an earlier draft carried
# ("{st['rows'][1]['spec']:.3f}") were both unresolvable and, in one case, indexed to the
# wrong model. Reading them back means the caption cannot disagree with the figure.
for _n, _f in FIGURES.items():
    _cp = os.path.join(FIGD, _f["file"]).replace(".png", ".caption.json")
    if not os.path.exists(_cp):
        raise SystemExit(f"Figure {_n}: no caption beside the image at {_cp}\n"
                         f"  run its generator; it writes the PNG and the caption together.")
    _c = json.load(io.open(_cp, encoding="utf-8"))
    _f.update(lead=_c["lead"], panel_key=_c.get("panel_key", ""),
              extended=[tuple(x) for x in _c.get("extended", [])],
              min_px=_c["min_px"])
    # A caption is written by an f-string in the generator. If one failed to interpolate,
    # the brace survives into the JSON and would be typeset verbatim.
    for _s in [_f["lead"], _f["panel_key"]] + [t for p in _f["extended"] for t in p]:
        _m = re.search(r"\{[^{}]*\}", _s)
        if _m:
            raise SystemExit(f"Figure {_n}: unresolved template {_m.group(0)!r} in its caption")

# Placement: not the first passing mention but the first SUBSTANTIVE discussion. All of
# Figures 1-4 are name-checked in the intro's claim summary, and honouring that would
# drop four plates into section 1.
for _n, _sec, _anchor in [
 # Figure 1 is anchored at the FIRST paragraph that discusses it, which is also the one
 # that forward-references Figure 2. Its previous anchor sat at paragraph 28 of that file
 # while Figure 2's sits at paragraph 23, so the two plates came out of order: Figure 2
 # landed on page 9 and Figure 1 on page 12. Numbering was never wrong -- first citation is
 # Figure 1 then Figure 2, here and in the intro -- but the PLATES were reversed, and
 # nothing in the build checks that placement order matches numbering.
 (1, "2-materials.md",
     'read from the shipped model files rather than from documentation — in Figure 2.'),
 (2, "2-materials.md",
     'oundary, while reaching past a tile edge invents data and raised false positives on crack-free specimens 6.2×.'),
 (3, "4-benchmark.md",
     "The order is alphabetical and is not a ranking."),
 (4, "4-benchmark.md",
     "A published micrograph segmenter cannot be transferred by reading its class list."),
 (5, "6-labels.md",
     "(Figure 1 quotes 0.507 over the 58 frames in `txm_stats.json`: the denominator "
     "differs, not the frame's standing.)"),
 (6, "6-labels.md",
     "(Those agreements are region-set overlaps weighted by region area, computed over the "
     "frame's 1,295 labelled regions; they are model-against-model, not scores against the "
     "labels.)"),
]:
    FIGURES[_n]["section"] = _sec
    FIGURES[_n]["anchor"] = _anchor

def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def glyphsafe(t):
    """Replace characters the body font cannot draw. Runs on escaped text, before
    any markup is inserted -- none of the substitutions can appear inside a tag."""
    t = SUP_RE.sub(lambda m: "<super>%s</super>" % "".join(SUP[c] for c in m.group()), t)
    if FSYM:
        t = t.replace("⚠", '<font name="%s">⚠</font>' % FSYM)
    else:
        t = t.replace("⚠", "<b>[!]</b>")
    return t

def inline(t):
    t = esc(t)
    t = glyphsafe(t)
    t = re.sub(r"`([^`]+)`", r'<font name="%s" size="8.8">\1</font>' % FM, t)
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    return t

def table_flow(rows, width):
    head, body = rows[0], rows[1:]
    ncol = len(head)
    # width by content mass, floored so a narrow column stays readable
    mass = [max(1, sum(len(r[i]) for r in rows)) for i in range(ncol)]
    tot = sum(mass)
    cw = [max(width * 0.07, width * m / tot) for m in mass]
    k = width / sum(cw)
    cw = [c * k for c in cw]
    data = [[Paragraph(inline(c), S["cellh"]) for c in head]]
    data += [[Paragraph(inline(c), S["cell"]) for c in r] for r in body]
    t = Table(data, colWidths=cw, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.9, INK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, INK),
        ("LINEBELOW", (0, -1), (-1, -1), 0.9, INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f5")]),
    ]))
    return t

FIG_SCALE = {}          # n -> (final_width_pt, source_px, effective_pt_of_min_type)

def fig_block(n, avail_w, avail_h, split=False):
    """One figure with its caption, sized for the column it is placed in.

    Returns (group, tail). `group` is the image with whatever caption must stay on its page;
    `tail` is caption text allowed to flow. The image gets at most IMG_MAX of the page so
    that a long caption cannot squeeze it: Figure 2's 21-box panel key did exactly that and
    drove its own image down to 246 pt wide, which the type-size floor then rejected.
    """
    f = FIGURES[n]
    p = os.path.join(FIGD, f["file"])
    if not os.path.exists(p):
        raise SystemExit(f"Figure {n} missing: {p}")
    from PIL import Image as PILImage
    PILImage.MAX_IMAGE_PIXELS = None
    iw, ih = PILImage.open(p).size

    lead = Paragraph(f"<b>Figure {n}.</b> {inline(f['lead'])}", S["figcap"])
    keyp = Paragraph(inline(f["panel_key"]), S["figkey"]) if f["panel_key"] else None
    ext = [Paragraph(f"<b>{esc(h)}</b>  {inline(t)}", S["figext"]) for h, t in f["extended"]]

    # Only the lead sentence is tied to the image. The panel key is reference text the
    # reader consults while looking at the figure, and it immediately follows it in the
    # flow, so nothing is separated in reading order -- but holding it on the figure's page
    # made the caption, not the figure, decide the image size. Figure 1's 5,000-character
    # key drove its own image to 270 pt wide (4.7 pt type) before this split.
    head = [lead]
    tail = ([keyp] if keyp else []) + ext

    headh = sum(c.wrap(avail_w, avail_h)[1] for c in head) + 10
    IMG_MAX = 0.88
    room = min(avail_h * IMG_MAX, avail_h - headh - 6)
    w, h = avail_w, avail_w * ih / iw
    if h > room:
        h = room
        w = h * iw / ih

    eff = f["min_px"] * (w / iw)
    FIG_SCALE[n] = (w, (iw, ih), eff)
    if eff < MIN_FIG_PT:
        raise SystemExit(
            f"Figure {n}: smallest drawn type is {f['min_px']} px in a {iw} px image, "
            f"so at {w:.0f} pt wide it renders at {eff:.2f} pt -- below the {MIN_FIG_PT} pt "
            f"floor. Either the generator must draw larger type (>= "
            f"{MIN_FIG_PT * iw / w:.0f} px), use fewer panels per row so the image is "
            f"narrower, or this figure needs orient='land'.")

    im = Image(p, width=w, height=h)
    im.hAlign = "CENTER"      # a figure narrower than the column reads as an indent otherwise
    return KeepTogether([im, Spacer(1, 6)] + head), tail

def _norm(s):
    # emphasis markers are stripped too: an anchor that happened to end in "**Figure 2**"
    # broke the moment bold was removed from the sections, which is a silly way to lose a
    # figure. Match on the words.
    return re.sub(r"\s+", " ", (s or "").replace("**", "").replace("*", "")).strip()

PLACED = set()
#: Emission order, which PLACED (a set) cannot record. Figures are NUMBERED in order of
#: first citation but PLACED wherever their anchor paragraph sits, and nothing compared the
#: two. That shipped twice: Figure 2's plate came out on page 9 and Figure 1's on page 12,
#: and a sixth figure anchored in section 4 landed ahead of the two anchored in section 6.
#: Both builds were clean and both printed a reassuring placement line.
EMIT_ORDER = []

def parse(md, width, section="", page_h=None):
    """Markdown -> flowables, with each figure inserted after the paragraph that cites it.

    A figure is emitted when a paragraph's normalised tail matches its `anchor`. Nothing
    falls back to the end of the document: `assert_all_placed()` fails the build if an
    anchor never matched, because a figure quietly reverting to the back of the paper is
    exactly the defect this replaces.
    """
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    out = []
    lines = md.split("\n")
    i, buf, mode = 0, [], None
    anchors = [(n, _norm(f["anchor"])) for n, f in sorted(FIGURES.items())
               if f["section"] == section and f["anchor"]]

    def emit_figs(txt):
        for n, a in anchors:
            if n in PLACED or not a:
                continue
            if _norm(txt).endswith(a):
                PLACED.add(n)
                EMIT_ORDER.append(n)
                if FIGURES[n]["orient"] == "land":
                    g, tail = fig_block(n, LTW, LTH, split=True)
                    out.extend([NextPageTemplate("land"), PageBreak(), g,
                                NextPageTemplate("p"), PageBreak()])
                    out.extend(tail)
                else:
                    g, tail = fig_block(n, width, page_h or TH)
                    out.extend([Spacer(1, 7), g] + tail + [Spacer(1, 7)])

    def flushpara():
        nonlocal buf
        if not buf:
            return
        txt = " ".join(x.strip() for x in buf).strip()
        buf = []
        if not txt:
            return
        st = S["abstract"] if mode == "abstract" else S["body"]
        out.append(Paragraph(inline(txt), st))
        emit_figs(txt)

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            flushpara(); i += 1; continue
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|?$", lines[i+1].strip()):
            flushpara()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                r = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[\s:|-]+$", "".join(r)):
                    rows.append(r)
                i += 1
            if rows:
                out.append(Spacer(1, 3)); out.append(table_flow(rows, width)); out.append(Spacer(1, 9))
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            flushpara()
            lvl, txt = len(m.group(1)), m.group(2)
            mode = "abstract" if re.match(r"^abstract\b", txt, re.I) else None
            out.append(Paragraph(inline(txt), S["h1" if lvl <= 2 else ("h2" if lvl == 3 else "h3")]))
            i += 1; continue
        if re.match(r"^(\*{3,}|-{3,}|_{3,})$", s):
            flushpara(); out.append(HRFlowable(width="100%", thickness=0.6, color=RULE,
                                               spaceBefore=6, spaceAfter=8)); i += 1; continue
        m = re.match(r"^(?:[-*+]|(\d+)\.)\s+(.*)$", s)
        if m:
            flushpara()
            bullet = f"{m.group(1)}." if m.group(1) else "•"
            txt = [m.group(2)]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(
                    r"^(#{1,4}\s|\||[-*+]\s|\d+\.\s|(\*{3,}|-{3,}|_{3,})$)", lines[i].strip()):
                txt.append(lines[i].strip()); i += 1
            joined = " ".join(txt)
            out.append(Paragraph(inline(joined), S["li"], bulletText=bullet))
            emit_figs(joined)
            continue
        if s.startswith(">"):
            flushpara()
            txt = [s.lstrip("> ").strip()]
            i += 1
            while i < len(lines) and lines[i].strip().startswith(">"):
                txt.append(lines[i].strip().lstrip("> ").strip()); i += 1
            out.append(Paragraph(inline(" ".join(txt)), S["note"]))
            continue
        buf.append(ln); i += 1
    flushpara()
    return out

PW, PH = LETTER
LM = RM = 22 * mm
TM, BM = 20 * mm, 18 * mm
TW = PW - LM - RM
TH = PH - TM - BM

def deco(canv, doc):
    canv.saveState()
    canv.setFont(FB, 7.6); canv.setFillColor(MUT)
    canv.drawString(LM, PH - TM + 7*mm, "Crack quantification from micrographs of additively manufactured 316L")
    canv.drawRightString(PW - RM, PH - TM + 7*mm, "")
    canv.setStrokeColor(RULE); canv.setLineWidth(0.4)
    canv.line(LM, PH - TM + 5.6*mm, PW - RM, PH - TM + 5.6*mm)
    canv.drawCentredString(PW/2, BM - 9*mm, str(canv.getPageNumber()))
    canv.restoreState()

doc = BaseDocTemplate(OUT, pagesize=LETTER, leftMargin=LM, rightMargin=RM,
                      topMargin=TM, bottomMargin=BM,
                      title="Crack quantification from micrographs of additively manufactured 316L",
                      author="Jiaming Zhang")
LW, LH = landscape(LETTER)
LMG = 14 * mm
LTW, LTH = LW - 2*LMG, LH - 2*LMG - 6*mm

def deco_land(canv, doc):
    canv.saveState()
    canv.setFont(FB, 7.6); canv.setFillColor(MUT)
    canv.drawCentredString(LW/2, LMG - 9*mm, str(canv.getPageNumber()))
    canv.restoreState()

doc.addPageTemplates([
    PageTemplate(id="p", pagesize=LETTER,
                 frames=[Frame(LM, BM, TW, PH - TM - BM, id="f", leftPadding=0,
                               rightPadding=0, topPadding=0, bottomPadding=0)],
                 onPage=deco),
    PageTemplate(id="land", pagesize=landscape(LETTER),
                 frames=[Frame(LMG, LMG, LTW, LTH, id="fl", leftPadding=0, rightPadding=0,
                               topPadding=0, bottomPadding=0)],
                 onPage=deco_land),
])

story = []
story.append(Paragraph("Crack quantification from micrographs of additively manufactured 316L: "
                       "the segmenter is not the limiting term at this sampling", S["title"]))
story.append(Paragraph("Jiaming Zhang", S["author"]))
story.append(Paragraph("Stanford University &mdash; jzhang29@stanford.edu", S["author"]))
story.append(HRFlowable(width="100%", thickness=0.8, color=INK, spaceBefore=8, spaceAfter=8))

for f in sorted(glob.glob(os.path.join(SEC, "*.md"))):
    md = io.open(f, encoding="utf-8").read()
    if os.path.basename(f).startswith("1-"):
        # The intro file repeats the title, the bybline and an alternative-titles note that
        # belong to the drafting process, not to the paper. The document sets its own.
        md = re.sub(r"\A\s*#\s+.*?(?=\n##\s)", "", md, flags=re.S)
        md = re.sub(r"^Alternative titles[^\n]*\n", "", md, flags=re.M)
    story.extend(parse(md, TW, section=os.path.basename(f), page_h=TH))

# --- every figure must have landed at its anchor ---
_unplaced = [n for n in sorted(FIGURES) if n not in PLACED]
if _unplaced:
    print("FIGURE PLACEMENT FAILED -- these anchors never matched a paragraph:")
    for n in _unplaced:
        f = FIGURES[n]
        print(f"  Figure {n}: section={f['section']!r}")
        print(f"             anchor={_norm(f['anchor'])[:110]!r}")
        src = os.path.join(SEC, f["section"])
        if f["section"] and os.path.exists(src):
            body = _norm(io.open(src, encoding="utf-8").read())
            a = _norm(f["anchor"])
            print(f"             anchor substring present in file: {a in body}")
        else:
            print(f"             section file not found: {src}")
    raise SystemExit("refusing to build: a figure would silently revert to the back")
if EMIT_ORDER != sorted(EMIT_ORDER):
    print("figure emission order is", EMIT_ORDER, "but numbering is", sorted(EMIT_ORDER))
    for _a, _b in zip(EMIT_ORDER, EMIT_ORDER[1:]):
        if _b < _a:
            print(f"  Figure {_b} is placed after Figure {_a}: its anchor is in "
                  f"{FIGURES[_b]['section']}, reached later than {FIGURES[_a]['section']}")
    raise SystemExit("refusing to build: the plates are out of numerical order")
print("figure placement:", ", ".join(
    f"Fig {n} after {FIGURES[n]['section']} ({FIGURES[n]['orient']}, "
    f"{FIG_SCALE[n][2]:.1f} pt min type)" for n in sorted(PLACED)))

def _coverage(story):
    """Every character that reaches a Paragraph, against the font that will DRAW it.

    Walks the finished story rather than the two code paths I edited: figure captions
    and the abstract build their markup without going through inline(), so a check
    wired into inline() would have reported clean while the captions shipped tofu.
    A font with no glyph for a character omits it SILENTLY -- the failure mode is a
    changed number, not a visible box, so this raises instead of warning.
    """
    faces, opaque = {}, set()
    for nm in ("Body", "Body-It", "Body-Bd", "Sym", "Mono", FB, FI, FBD, FM):
        try:
            faces[nm] = pdfmetrics.getFont(nm).face.charToGlyph
        except Exception:
            opaque.add(nm)          # built-in Type1: no cmap to read
    if "Body" not in faces:
        return [("<no TTF body font registered; built-in Times-Roman is WinAnsi "
                 "and silently drops every character above U+00FF>", "", "")]
    if opaque:
        print("  note: cannot inspect", sorted(opaque),
              "- characters drawn in those fonts are NOT checked")

    def covered(ch, f):
        """None = unknown (font not inspectable), True/False = has glyph."""
        fam = ["Body", "Body-It", "Body-Bd"] if f in ("Body", "Body-It", "Body-Bd") else [f]
        known = [k for k in fam if k in faces]
        if not known:
            return None
        return any(faces[k].get(ord(ch), 0) for k in known)

    def texts(fl):
        for f in fl:
            if isinstance(f, Paragraph):
                yield f.text
            elif isinstance(f, Table):
                for row in f._cellvalues:
                    yield from texts([c for c in row if c is not None])
            elif isinstance(f, KeepTogether):
                yield from texts(f._content)

    # map each span to its font: <font name="X"> switches, </font> restores
    span = re.compile(r'<font[^>]*name="([^"]+)"[^>]*>|</font>|<[^>]+>|&[a-z]+;|&#\d+;')
    bad = []
    for t in texts(story):
        stack, i = ["Body"], 0
        for m in span.finditer(t):
            for ch in t[i:m.start()]:
                if ord(ch) < 32:
                    continue
                if covered(ch, stack[-1]) is False:
                    bad.append((ch, stack[-1], t[max(0, m.start() - 60):m.start() + 20]))
            if m.group(0).startswith("<font"):
                stack.append(m.group(1))
            elif m.group(0) == "</font>":
                if len(stack) > 1:
                    stack.pop()
            i = m.end()
        for ch in t[i:]:
            if ord(ch) < 32:
                continue
            if covered(ch, stack[-1]) is False:
                bad.append((ch, stack[-1], t[max(0, len(t) - 80):]))
    return bad

miss = _coverage(story)
if miss:
    seen = {}
    for ch, f, ctx in miss:
        seen.setdefault((ch, f), []).append(ctx)
    print("GLYPH COVERAGE FAILED -- these characters would be dropped silently:")
    for (ch, f), ctxs in seen.items():
        print(f"  {ch!r} U+{ord(ch):04X} in font {f}  x{len(ctxs)}")
        print(f"      ...{ctxs[0]}...")
    raise SystemExit("refusing to write a PDF that drops characters")
print(f"glyph coverage: OK ({len(pdfmetrics.getRegisteredFontNames())} fonts registered,"
      f" symbol font {'Sym' if FSYM else 'NONE -- using [!] fallback'})")

doc.build(story)
print("wrote", OUT, f"{os.path.getsize(OUT)/1e6:.1f} MB")
