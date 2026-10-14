"""Figure 1 -- what each filter and model stage does, panel by panel.

Every image panel is a real array written by a stage runner that imports and calls the
pipelines' own functions. The TXM ensemble panel was verified bit-identical to the app's
cached probability map (mean |diff| = 0.0).

THE SEM ROW NOW DRAWS v1.49.2 -- WHAT THE APPLICATION RUNS. It used to draw the archived
published pipeline, and two of its eight panels had no counterpart in production at all:
the darkness cut at ONE flattening radius, and the logistic region classifier keeping
"245 of 453 regions". Production unions the cut over seven radii (5,10,20,40,80,160,320),
because a feature wider than the blur radius is erased by its own flattening, and it sets
USE_REGION_CLASSIFIER = False, so there is no kept/dropped split to draw -- deleting the
classifier beat keeping it on every metric with zero free parameters (paired median IoU
+0.1753 over 13 specimens, 11 of 13, Wilcoxon p = 0.0061).

The single-radius cut SURVIVES as panel 4, as the honest "before" that panel 5 is measured
against. The row's arrays come from sem_production.py (`semp_*`, driven through
`detector_overrides.install()` and `run_unified_pipeline` exactly as analysis/detect_one.py
drives them) and sem_rungs.py (`semr_*`, the union decomposed by rung). Its numbers come
from sem_production.json and sem_rungs.json and from nowhere else. sem_stats.json is the
ARCHIVED record and is now read by NOTHING: figure 2's SEM column was rebuilt against
production too, and its model numbers come from sem_models.json. The file is kept as the
committed record of the published pipeline, not because a plate depends on it.

PANEL 8 IS THE FULL PIPELINE, Pass 2 included -- `np.isin(labeled, df["Label"])` over the
whole of run_unified_pipeline's output, which is what detect_one.py writes to disk. It is
not the candidate stage; panel 6 is, and the two differ by 0.67 pp on this window. A panel
that claimed to show what the app emits while drawing only the candidates would be short
by every Pass-2 pixel.

TXM arm unchanged: the SEM arm still has eight panels, so the layout did not move.

Layout rule learned the hard way: caption height is MEASURED from the wrapped text, never
assumed, or the first row overwrites the second.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

HERE = _paths.FIG_CACHE
# The SEM arm reads the PRODUCTION record and the rung decomposition. It deliberately does
# NOT read sem_stats.json: that file is the archived published pipeline's record, and a
# single number lifted from it into this plate would attach the retired classifier's
# arithmetic to a panel drawn from v1.49.2.
PROD = json.load(open(f"{HERE}/sem_production.json"))
RUNG = json.load(open(f"{HERE}/sem_rungs.json"))
TXM = json.load(open(f"{HERE}/txm_stats.json"))
assert PROD["frame"] == RUNG["frame"] and PROD["crop"] == RUNG["crop"], \
    "the production record and the rung decomposition are not the same window"
assert PROD["use_region_classifier"] is False, "this plate draws the classifier-off path"
for _c, _v in RUNG["controls"].items():
    assert _v.startswith("PASS"), f"sem_rungs control {_c} did not pass: {_v}"
L = lambda n: np.load(f"{HERE}/{n}.npy")

INK, MUT = (24, 24, 26), (98, 98, 104)
RULE = (212, 212, 208)
RED, GRN, AMB, BLU, VIO = (196, 42, 42), (28, 118, 74), (186, 120, 10), (38, 102, 190), (112, 62, 172)

def font(sz, bold=False):
    for p in (("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
               else "/System/Library/Fonts/Supplemental/Arial.ttf"),
              "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try: return ImageFont.truetype(p, sz)
        except Exception: pass
    return ImageFont.load_default()

F_TITLE, F_SUB = font(46, True), font(22)
F_SEC, F_SECN = font(26, True), font(19)
F_PN, F_CAP, F_TINY, F_H3 = font(26, True), font(14), font(24), font(18, True)
LH = 17
TINY_LH = 29
MIN_PX = 24   # F_TINY, the smallest size still drawn

P, GAP, M = 312, 18, 40
NCOL = 4
W = M*2 + NCOL*P + (NCOL-1)*GAP

_probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
def wrap(text, f, width):
    out, line = [], ""
    for word in text.split():
        t = (line + " " + word).strip()
        if _probe.textlength(t, font=f) <= width: line = t
        else:
            if line: out.append(line)
            line = word
    if line: out.append(line)
    return out

def laid(cap, width=P):
    rows = []
    for ln in cap: rows += wrap(ln, F_CAP, width)
    return rows

# ---------------------------------------------------------------- array -> image
def grey(a, lo=None, hi=None):
    a = np.asarray(a, np.float32)
    lo = a.min() if lo is None else lo; hi = a.max() if hi is None else hi
    return Image.fromarray((np.clip((a-lo)/max(hi-lo, 1e-12), 0, 1)*255).astype(np.uint8)).convert("RGB")

def ramp(a, stops, lo=None, hi=None, gamma=1.0):
    a = np.asarray(a, np.float32)
    lo = a.min() if lo is None else lo; hi = a.max() if hi is None else hi
    v = np.clip((a-lo)/max(hi-lo, 1e-12), 0, 1)**gamma
    xs = np.linspace(0, 1, len(stops))
    out = np.zeros(v.shape+(3,), np.float32)
    for c in range(3): out[..., c] = np.interp(v, xs, [s[c] for s in stops])
    return Image.fromarray(out.astype(np.uint8))

PROB = [(250, 250, 247), (206, 222, 238), (106, 158, 204), (36, 76, 148), (14, 22, 62)]
HEAT = [(255, 255, 252), (252, 232, 176), (244, 160, 56), (198, 48, 26), (72, 6, 6)]
GLOW = [(16, 14, 24), (74, 26, 56), (190, 78, 36), (246, 170, 54), (255, 246, 206)]

def over(base, layers):
    b = np.dstack([np.asarray(base, np.uint8)]*3).astype(np.float32)
    for mask, col, al in layers:
        m = np.asarray(mask, bool)
        for c in range(3): b[..., c][m] = (1-al)*b[..., c][m] + al*col[c]
    return Image.fromarray(b.clip(0, 255).astype(np.uint8))

def contour(im, mask, col=(235, 60, 40), it=2):
    a = np.asarray(im).copy()
    ring = np.asarray(mask, bool) ^ ndi.binary_erosion(np.asarray(mask, bool), iterations=it)
    a[ring] = col
    return Image.fromarray(a)


def fit(im, n=P):
    return im.resize((n, n), Image.LANCZOS)

def tag(im, text, corner="tl"):
    """A small legend chip inside a panel.

    The chip is drawn on the panel at its NATIVE crop size (1200 px for SEM, 1100 for TXM)
    and fit() then downscales the panel to P = 312 px. A 24 px font therefore arrives on the
    page at 24 * 312/1200 = 6 px, which measured 1.6 pt -- illegible, and invisible to a
    check that only looks at the declared font size. The font is scaled by the SAME factor
    fit() will divide by, so MIN_PX is what actually lands.
    """
    im = im.copy(); d = ImageDraw.Draw(im)
    k = im.width / P                      # the downscale fit() is about to apply
    f = font(max(8, round(MIN_PX * k)))
    lh = round(TINY_LH * k)
    pad = round(6 * k)
    # Wrap to the panel. At the old 6 px effective size every chip fitted; at MIN_PX the
    # longest ("664 components -> 453 >= 40 px") ran off the panel and was cut by the crop.
    avail = im.width - 2*round(8*k) - 2*pad
    lines = []
    for raw in text.split("\n"):
        lines += wrap(raw, f, avail) or [""]
    wmax = max(d.textlength(l, font=f) for l in lines)
    assert wmax <= avail, f"chip text {wmax:.0f} px wide in {avail:.0f} px panel: {lines!r}"
    hh = len(lines)*lh + 2*pad
    x0, y0 = (round(8*k), round(8*k)) if corner == "tl" else (round(8*k), im.height-hh-round(8*k))
    d.rectangle([x0, y0, x0+wmax+2*pad, y0+hh], fill=(255, 255, 255))
    d.rectangle([x0, y0, x0+wmax+2*pad, y0+hh], outline=RULE, width=max(1, round(k)))
    for i, l in enumerate(lines):
        d.text((x0+pad, y0+pad+i*lh), l, font=f, fill=INK)
    return im

def locator(im, thumb_path, crop, full):
    """Paste a frame thumbnail with the crop box into the panel's corner."""
    im = im.copy()
    th = Image.open(thumb_path).convert("RGB")
    tw = round(0.26 * im.width)   # ~26% of the panel AFTER fit(), not 108 raw px
    th = th.resize((tw, max(1, round(th.height*tw/th.width))), Image.LANCZOS)
    d = ImageDraw.Draw(th)
    sx, sy = th.width/full[0], th.height/full[1]
    d.rectangle([crop[0]*sx, crop[1]*sy, (crop[0]+crop[2])*sx, (crop[1]+crop[2])*sy],
                outline=(255, 70, 70), width=max(2, round(2*im.width/P)))
    pad = round(8*im.width/P)
    bx, by = im.width-th.width-pad, im.height-th.height-pad
    r = max(2, round(2*im.width/P))
    ImageDraw.Draw(im).rectangle([bx-r, by-r, bx+th.width+r, by+th.height+r], fill=(255, 255, 255))
    im.paste(th, (bx, by))
    return im

# ---------------------------------------------------------------- SEM panels
# Colours for the union panel, ordered DARK -> LIGHT down the ladder, so a reader who
# cannot see hue still reads "smaller flattening radius = darker swatch". Checked by
# converting the finished plate to greyscale and confirming the six stay ordered.
RUNG_COL = [("sigma 5",   (118,  16,  62)),
            ("sigma 10",  (178,  38,  36)),
            ("sigma 20",  (212, 104,  22)),
            ("sigma 80",  (226, 158,  28)),
            ("sigma 160", (238, 202,  70)),
            ("sigma 320", (250, 238, 158))]
RUNG_IDX = {f"sigma {s}": i for i, s in enumerate(RUNG["ladder"], start=1)}


def union_chip(im, lines, swatches, lo, hi):
    """Panel 5's legend: two measured lines, then a swatch bar reading smallest radius to
    largest, which is also smallest-to-largest in LIGHTNESS so the order survives a
    greyscale print.

    Same geometry discipline as tag(): the chip is drawn at the panel's NATIVE crop size,
    which fit() then divides by k, so every size is multiplied by k and MIN_PX is what
    lands on the page. The width is asserted -- at MIN_PX a chip that used to fit does not.
    """
    im = im.copy(); d = ImageDraw.Draw(im)
    k = im.width / P
    f = font(max(8, round(MIN_PX * k)))
    lh, pad, gap = round(TINY_LH * k), round(6 * k), round(7 * k)
    cw = round(26 * k)                      # one swatch cell
    bar = len(swatches) * cw
    wlo, whi = d.textlength(lo, font=f), d.textlength(hi, font=f)
    wmax = max([d.textlength(t, font=f) for t in lines] + [wlo + gap + bar + gap + whi])
    hh = (len(lines) + 1) * lh + 2 * pad
    x0, y0 = round(8 * k), im.height - hh - round(8 * k)
    assert x0 + wmax + 2 * pad <= im.width, f"chip {wmax:.0f} px wide in {im.width} px panel"
    d.rectangle([x0, y0, x0 + wmax + 2 * pad, y0 + hh], fill=(255, 255, 255))
    d.rectangle([x0, y0, x0 + wmax + 2 * pad, y0 + hh], outline=RULE, width=max(1, round(k)))
    y = y0 + pad
    for t in lines:
        d.text((x0 + pad, y), t, font=f, fill=INK); y += lh
    d.text((x0 + pad, y), lo, font=f, fill=INK)
    bx = x0 + pad + wlo + gap
    for i, col in enumerate(swatches):
        d.rectangle([bx + i * cw, y + round(4 * k), bx + (i + 1) * cw, y + round(22 * k)],
                    fill=col, outline=RULE, width=max(1, round(k)))
    d.text((bx + bar + gap, y), hi, font=f, fill=INK)
    return im


def union_panel(g8, single, rung):
    """The seven-radius union: the sigma = 40 cut in the same violet panel 4 draws, and
    every pixel the OTHER six radii add coloured by the smallest radius that sees it.

    The stock cut already OR-s the absolute-darkness term in, so neither sigma = 40 nor
    that term can appear among the additions -- sem_rungs.py asserts both are zero.
    """
    a = np.asarray(over(g8, [(single, VIO, 0.55)])).astype(np.float32)
    for name, col in RUNG_COL:
        m = (rung == RUNG_IDX[name]) & ~single
        for c in range(3):
            a[..., c][m] = 0.08 * a[..., c][m] + 0.92 * col[c]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def sem_panels():
    """The SEM arm, drawn against v1.49.2 -- what the application runs, not what the paper
    archived. The fourth element of each tuple is unused by row(); the prose that is
    typeset lives in CAPTION below, and duplicating numbers into a string nothing renders
    is how a figure acquires a caption no check ever reads."""
    img8, flat, ves = L("semp_img8"), L("semp_flat"), L("semp_ves")
    cand, emitted = L("semp_cand"), L("semp_emitted")
    single, rung = L("semr_single"), L("semr_rung")
    g8 = np.asarray(img8, np.uint8)
    micro = locator(grey(img8, 0, 255), f"{HERE}/semp_frame_thumb.png", PROD["crop"], PROD["full"])
    vhi = float(np.percentile(ves, 99.5))

    return [
      ("1", "Micrograph", micro, []),
      ("2", "flatten_background", grey(flat, 0, 255), []),
      ("3", "Frangi vesselness", tag(ramp(ves, GLOW, 0, vhi, gamma=0.5),
          f"crack {PROD['ves_crack']:.4f}\nmatrix {PROD['ves_matrix']:.4f}\n"
          f"ratio {PROD['ves_ratio']:.1f} : 1"), []),
      ("4", "Darkness cut \u00b7 \u03c3 40", tag(over(g8, [(single, VIO, 0.78)]),
          f"\u03c3 = 40 only\n{RUNG['crop_single_pct']:.2f} % of window"), []),
      ("5", "Seven-radius union", union_chip(union_panel(g8, single, rung),
          [f"\u03c3 40 alone {RUNG['crop_single_pct']:.2f} %",
           f"all seven {RUNG['crop_union_pct']:.2f} %",
           f"+{RUNG['crop_added_over_single_px']:,} px"],
          [c for _, c in RUNG_COL], "\u03c3 5", "320"), []),
      ("6", "Candidates \u00b7 all kept", tag(over(g8, [(cand, VIO, 0.78)]),
          f"frame: {PROD['frame_candidates']:,} regions\n"
          f"none rejected\nwindow: {PROD['crop_cand_pct']:.2f} % area"), []),
      ("7", "Pass 2 \u00b7 interior fill", tag(over(g8, [(cand, RED, 0.55),
                                                     (emitted & ~cand, AMB, 0.88)]),
          f"red   Pass 1\namber Pass 2 +{PROD['crop_pass2_added_pp']:.2f} pp",
          corner="bl"), []),
      ("8", "Emitted mask", tag(contour(grey(img8, 0, 255), emitted, it=2),
          f"what the app writes\nPass 1 + Pass 2\n{PROD['crop_emitted_pct']:.2f} % of window",
          corner="bl"), []),
    ]

# ---------------------------------------------------------------- TXM panels
def txm_panels():
    raw8, disp8, emb = L("txm_raw8"), L("txm_disp8"), L("txm_embrgb")
    p17, ph, ens = L("txm_p17"), L("txm_ph"), L("txm_ens")
    mask, lbl = L("txm_mask"), L("txm_label")
    ftex, fgrad, flap, fsm = L("txm_ftex"), L("txm_fgrad"), L("txm_flap"), L("txm_fsm")
    TH = TXM["threshold"]; d8 = np.asarray(disp8, np.uint8)
    rawp = locator(grey(raw8, 0, 255), f"{HERE}/txm_frame_thumb.png", TXM["crop"], TXM["full"])

    q = P//2
    mont = Image.new("RGB", (P, P), (255, 255, 255))
    for k, (a, nm) in enumerate([(fsm, "smooth σ 16"), (fgrad, "gradmag σ 4"),
                                 (flap, "laplacian σ 4"), (ftex, "texture σ 8")]):
        lo, hi = np.percentile(a, [1, 99])
        mont.paste(fit(grey(a, lo, hi), q-2), ((k % 2)*q+1, (k//2)*q+1))
    dd = ImageDraw.Draw(mont)
    for k, nm in enumerate(["smooth σ 16", "gradmag σ 4", "laplacian σ 4", "texture σ 8"]):
        x, y = (k % 2)*q+5, (k//2)*q+5
        bb = dd.textbbox((0, 0), nm, font=F_TINY)
        dd.rectangle([x, y, x+bb[2]+8, y+bb[3]+6], fill=(255, 255, 255))
        dd.text((x+4, y+2), nm, font=F_TINY, fill=INK)
    seps = dict(TXM["feature_sep"])

    enspanel = tag(ramp(ens, PROB, 0, 1), f"mask = mean p > {TH:.2f}\nthen prune_specks\n{TXM['crop_mask_pct']:.2f}% of window")
    ea = np.asarray(enspanel).copy()
    ring = mask ^ ndi.binary_erosion(mask, iterations=2)
    ea[ring] = [235, 60, 40]
    enspanel = Image.fromarray(ea)

    return [
      ("1", "Raw mosaic", rawp, [
        f"{TXM['full'][0]}×{TXM['full'][1]} px, {TXM['megapixels']} MP at {TXM['nm_per_px']} nm/px — ONE magnification for the whole",
        "determination, which is what E562 asks for and what makes the field count the binding term.",
        "A TXM mosaic's dominant variation is tile-to-tile illumination: a visible grid of brighter",
        f"squares that is instrument, not specimen. Against that the crack separates by {TXM['raw_sep_sd']:.2f} sd here.",
        "Untreated, it is effectively invisible, which is why the next panel is not cosmetic."]),
      ("2", "Destitch + flat-field — the HUMAN view", tag(grey(disp8, 0, 255), f"{TXM['disp_sep_sd']:.2f} sd separation\n({TXM['disp_sep_sd']/max(TXM['raw_sep_sd'],1e-9):.1f}× the raw mosaic)"), [
        "THIS IS NOT WHAT THE MODEL READS, and an earlier version of this caption said it was. The",
        "pipeline stores two arrays: img.npy, the raw path normalised, is the MODEL input; display.npy,",
        "destitched and flat-fielded, is the HUMAN view. pipeline.py gives the reason in its own",
        "comment — the model is fed raw because that is what it was trained on, while thin faint",
        "cracks are often visible only under local contrast — so the two are deliberately different",
        "images that share a geometry, and a mask from one registers on the other.",
        "The flat-field DIVIDES by an anisotropic Gaussian (σy 16, σx 22). The σ-60 SUBTRACT whose",
        "+2.05 sd this caption used to quote belongs to a third transform, in the fractography app's",
        f"own TXM original view. This panel measures {TXM['disp_sep_sd']:.2f} sd."]),
      ("3", "17 hand-built channels", mont, [
        "intensity; smooth σ 2, 4, 8, 16, 32, 64; gradmag σ 1, 2, 4, 8; laplacian σ 1, 2, 4, 8;",
        "texture (local sd) σ 2, 8. Four of the seventeen are shown. Separation of crack from matrix",
        f"on this window, in matrix sd: texture σ8 {seps.get('texture_s8',0):.2f}, texture σ2 {seps.get('texture_s2',0):.2f}, gradmag σ4 {seps.get('gradmag_s4',0):.2f},",
        f"laplacian σ4 {seps.get('laplacian_s4',0):.2f} — and raw intensity only {seps.get('intensity',0):.2f}. Local VARIANCE carries the crack in",
        "TXM and brightness does not, which is the reverse of the SEM arm's darkness feature."]),
      ("4", "SAM ViT-H embedding", tag(Image.fromarray(np.asarray(emb, np.uint8)),
          f"3 of 256 components\n{100*TXM['emb_pca3_var']:.0f}% of variance\nPC1 separates {TXM['emb_pc1_sep_sd']:.2f} sd"), [
        f"{TXM['sam_model']} is used as a FROZEN ENCODER: the prompt encoder and the mask decoder",
        f"are never called. {TXM['sam_tile']} px tiles at stride {TXM['sam_stride']} so neighbours overlap ({TXM['sam_tiles']} tiles for this frame),",
        f"256 channels at stride {TXM['emb_stride']}, bilinearly sampled and Hann-blended across every tile covering a",
        "pixel — abutting tiles put a visible 33× step at the seam, and reaching past a tile edge",
        "invents data. Shown: the 3 leading principal components of those 256 channels, as RGB."]),
      ("5", "Member A · 17→64→32→1", tag(ramp(p17, PROB, 0, 1), f"p > {TH:.2f} on {100*float((p17>TH).mean()):.0f}% of window"), [
        "StandardScaler → MLPClassifier(hidden_layer_sizes=(64, 32)), 17 inputs, ONE logistic output. Cheap, runs",
        "with no encoder at all, and it is the automatic fallback whenever SAM cannot be reached — a",
        "promise that was false until the loader learned to raise its own exception type.",
        f"Grouped-by-image 5-fold over all 71 labelled frames: mean IoU 0.726. On this window {TXM['p17_iou']:.3f}:",
        f"it puts p > {TH:.2f} across {100*float((p17>TH).mean()):.0f}% of the area. It finds the trace; it does not find the edge."]),
      ("6", "Member B · 273→128→64→1", tag(ramp(ph, PROB, 0, 1), f"p > {TH:.2f} on {100*float((ph>TH).mean()):.0f}% of window"), [
        f"The same 17 channels CONCATENATED with the 256 embedding channels → StandardScaler →",
        f"MLPClassifier(hidden_layer_sizes=(128, 64)), {TXM['hybrid_dim']} inputs. Grouped 5-fold mean IoU 0.786;",
        f"on this window {TXM['ph_iou']:.3f}. Its output is close to bimodal — it commits — which is why the mean of",
        "the two is decided here and only tempered by member A. Both members were fitted on the",
        "owner's own corrections across all 71 frames and on nothing else: no external label, anywhere."]),
      ("7", "Mean probability → mask", enspanel, [
        f"predict() returns (A + B) / 2, thresholded at {TH:.2f} — chosen jointly with speck pruning rather",
        "than on threshold alone — then prune_specks; the red outline is the resulting mask.",
        "Averaging beat BOTH members in every single fold (0.811 against 0.786 and 0.726), which is",
        "the property worth having, because a mean can be carried by one fold."]),
      ("8", "Against the operator", tag(over(d8, [(mask & lbl, RED, 0.70), (lbl & ~mask, BLU, 0.70),
                                                 (mask & ~lbl, AMB, 0.70)]),
          "red   both\nblue  painted, missed\namber model only", corner="bl"), [
        f"This frame's full-resolution IoU is {TXM['frame_iou']:.3f}. The median over {TXM['corpus_n']} labelled frames is {TXM['corpus_median_iou']:.3f}",
        f"(quartiles {TXM['corpus_q1']:.2f}–{TXM['corpus_q3']:.2f}, range 0.05–0.94) — so this frame was chosen BECAUSE it is typical,",
        f"not because it is good. Recall on painted crack {TXM['frame_recall']:.2f}; false positives on painted",
        f"not-crack {100*TXM['frame_fp_on_not']:.2f}%. Nearly all the disagreement is boundary rather than existence,",
        "and the boundary is exactly what a width measurement is computed from."]),
    ]

SEMP, TXMP = sem_panels(), txm_panels()

# ---------------------------------------------------------------- measure, then lay out
# The title, standfirst, row notes, per-panel paragraphs and three footer columns are no
# longer drawn. Baked into a 2,782 px plate they rendered at 2.3 pt on the page, which is
# the whole reason this figure was unreadable. They are emitted as a caption JSON and
# typeset by mkpdf.py at 8.2 pt. What stays in the image is a row label, a panel number and
# a panel name, plus the legend chips that have to sit on top of the pixels they describe.
def titleh(panels):
    return max(len(wrap(nm, F_PN, P - 30)) for _, nm, _, _ in panels)

def rowh(panels):
    """Height of one arm: ceil(n/NCOL) sub-rows of panel + wrapped title."""
    import math
    subs = math.ceil(len(panels)/NCOL)
    return subs*(P + 12 + titleh(panels)*32 + 18)

H = 40 + (46 + rowh(SEMP)) + (46 + rowh(TXMP)) + 30
img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)

def row(y, head, panels, accent):
    d.rectangle([M, y+4, M+8, y+34], fill=accent)
    d.text((M+20, y), head, font=F_SEC, fill=INK)
    ty = y + 46
    th = titleh(panels)
    for i, (num, name, im, _cap) in enumerate(panels):
        cx_, ry = i % NCOL, i // NCOL
        x = M + cx_*(P+GAP)
        py = ty + ry*(P + 12 + th*32 + 18)
        img.paste(fit(im), (x, py))
        d.rectangle([x-1, py-1, x+P, py+P], outline=RULE, width=1)
        d.text((x, py+P+10), num, font=F_PN, fill=accent)
        cy = py+P+10
        for ln in wrap(name, F_PN, P - 30):
            d.text((x+26, cy), ln, font=F_PN, fill=INK); cy += 32
    return ty + rowh(panels)

y = 24
y = row(y, "SEM arm", SEMP, RED) + 30
y = row(y, "TXM arm", TXMP, BLU) + 14
img = img.crop((0, 0, W, min(img.height, y)))

out = os.path.join(_paths.FIG_DIR, "1 - what each stage does.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
img.save(out)
print("wrote", out, img.size, "min_px", MIN_PX)

# ---------------------------------------------------------------- caption
# Tightened from the inventory: one clause per panel. The three footer columns that used to
# sit under this figure are NOT reproduced here -- they argued the paper's thesis (the E562
# intervals, the label-width ceiling, the refusals), and sections 5, 6 and 7 make those
# arguments at length. A caption that restates the paper's conclusions is not a caption.
# One of them also still carried the withdrawn "0 of 22" pooled count; section 5.1 reports
# the four arms separately and declines to pool them, and that is the only place it belongs.
CAPTION = dict(
  min_px=MIN_PX,
  lead=("What every filter and model stage actually does: the SEM arm (top) and the TXM arm "
        "(bottom), each panel real output from the shipped code — the stage function imported "
        "from the pipeline and called on one window of one frame — rather than a schematic. "
        f"The SEM arm is version {PROD['version']}, the build the application runs: the darkness "
        f"cut unioned over seven flattening radii and every candidate region kept."),
  panel_key=(
    f"**SEM arm, {PROD['version']} — what the application runs**, on one {PROD['crop'][2]} px window "
    f"({RUNG['crop_frac_pct']:.2f} % of the frame, located by the red box in the inset) of "
    f"`{PROD['frame']}`. The "
    f"stages come from `run_unified_pipeline` driven exactly as `analysis/detect_one.py` "
    f"drives it, with `detector_overrides.install()` binding the production darkness cut. "
    f"**(1) Micrograph**, 16-bit back-scattered TIFF, {PROD['full'][0]}×{PROD['full'][1]} px "
    f"at {PROD['nm_per_px']:.1f} nm/px, rescaled to 8-bit on its own 1–99.5 percentile; crack "
    f"sits at DN {PROD['crack_dn']:.0f} against a DN {PROD['matrix_dn']:.0f} matrix whose own "
    f"spread is ±{PROD['matrix_sd']:.1f} DN, a {PROD['sep_raw_sd']:.1f} sd gap. Crack and matrix "
    f"are separated here by the frame's *gated* mask, and on this frame the operator made no "
    f"edits at all — it is bit-identical to the archived detector's own output — so it marks "
    f"where that detector found crack and is not an independent label. **(2) "
    f"`flatten_background`**, subtract a σ = 40 px Gaussian and stretch on the 0.5–99.5 "
    f"percentile; contrast *falls*, {PROD['sep_raw_sd']:.1f} → {PROD['sep_flat_sd']:.1f} sd, so "
    f"this is not a contrast step — it exists so that one threshold can work across a frame "
    f"with illumination drift, and its cost is the next two panels' whole subject. "
    f"**(3) Frangi vesselness**, `sigmas=range(1, 6)`, so σ = 1–5 and not the 1–6 this "
    f"caption used to say, `black_ridges=True`: crack {PROD['ves_crack']:.4f} "
    f"against matrix {PROD['ves_matrix']:.4f}, a {PROD['ves_ratio']:.1f} : 1 ratio. It is still "
    f"computed on every frame and is still one of the features Pass 2 scores on; with the "
    f"region classifier off it no longer decides anything at Pass 1. It is shown beside the "
    f"image it is computed from; in the code it runs after the next two panels. **(4) Darkness cut at ONE "
    f"radius**, `segment_dark_regions` at min(Otsu, median − {PROD['mad_k']:.0f}·MAD·1.4826) "
    f"OR-ed with an absolute DN < {PROD['absolute_dark_thresh']} test — the σ = 40 cut the "
    f"detector shipped with, covering {RUNG['crop_single_pct']:.2f} % of this window and "
    f"{PROD['frame_dark_single_pct']:.2f} % of the frame. **(5) The seven-radius union**, which "
    f"is the change: the SAME cut taken at σ = {', '.join(str(x) for x in PROD['scale_ladder'])} "
    f"and OR-ed, with the background estimated on a decimated copy above σ = "
    f"{PROD['decimate_above_sigma']}. Flattening is a high-pass filter, so a feature wider than "
    f"its own blur radius is removed along with the illumination drift and one radius sees one "
    f"band of widths. The union reaches {RUNG['crop_union_pct']:.2f} % of this window against "
    f"{RUNG['crop_single_pct']:.2f} %, adding {RUNG['crop_added_over_single_px']:,} px "
    f"(+{RUNG['crop_added_over_single_pp']:.2f} pp); each added pixel is coloured by the "
    f"smallest radius that sees it — "
    + ", ".join(f"σ {k.split()[1]} {v:,} px" for k, v in RUNG['crop_added_by_radius_px'].items() if v)
    + f". Frame-wide the cut goes {PROD['frame_dark_single_pct']:.2f} % → "
    f"{PROD['frame_dark_union_pct']:.2f} % for +{RUNG['frame_added_over_single_px']:,} px, and "
    f"σ = 40 and the absolute term add nothing by construction because the stock cut already "
    f"contains both. No new fitted parameter is introduced: the ladder is every scale and "
    f"`mad_k` is unchanged, and because the union keeps the σ = 40 term unchanged it cannot "
    f"drop a pixel the single radius kept — asserted on this frame by sem_rungs.py and 0 px "
    f"lost across the 26 hand-labelled tiles. It is a superset that deletes nothing rather "
    f"than a demonstrated gain: this corpus cannot resolve it (docs/CLAIMS.md D6). **(6) Candidate regions, all of them kept**, `clean_mask` at open "
    f"r = 1, close r = 3, drop under {PROD['min_area_clean']} px, fill holes, then components of "
    f"{PROD['min_area_candidate']} px or more: {PROD['frame_candidates']:,} regions frame-wide "
    f"against {PROD['frame_candidates_single']:,} at one radius, "
    f"{PROD['crop_cand_pct']:.2f} % of this window. `USE_REGION_CLASSIFIER` is False, so NONE is "
    f"rejected — the bundled logistic model would have kept {PROD['frame_archived_kept']:,} of "
    f"the {PROD['frame_candidates']:,} and taken "
    f"{100*PROD['frame_archived_would_drop_frac']:.1f} % "
    f"({PROD['frame_archived_would_drop_px']:,} px) out of the emitted mask. **(7) Pass 2, "
    f"interior fill**, concavity, bridge-corridor and interior-fill candidates, each scored by "
    f"a separately fitted 11-feature model that adds MeanRawBrightness, MeanFlatBrightness, "
    f"FracBoundaryTouchingCrack and MeanDistToCrack — context, not shape. "
    f"{PROD['frame_pass2_rows']:,} are accepted frame-wide and they add "
    f"{PROD['frame_pass2_added_px']:,} px ({PROD['crop_pass2_added_pp']:.2f} pp on this window). "
    f"The disabled classifier has not left the path entirely: Pass 2's seed crack mask is still "
    f"built from the `IsCrack` column it writes, so it still decides which Pass-2 candidates "
    f"exist. **(8) The emitted mask**, `np.isin(labeled, df['Label'])` over the whole of "
    f"`run_unified_pipeline` — Pass 1 candidates AND Pass 2, which is what `detect_one.py` "
    f"writes to disk — outlined in red on the micrograph at {PROD['crop_emitted_pct']:.2f} % of "
    f"this window against {PROD['frame_emitted_pct']:.2f} % of the frame. This panel is the full "
    f"pipeline and panel 6 is the candidate stage; they differ by every Pass-2 pixel. "
    f"**TXM arm**, one 1100 px window of `HC_316L_fatigue_1200_cycles`. **(1) Raw mosaic**, "
    f"{TXM['full'][0]}×{TXM['full'][1]} px, {TXM['megapixels']:.2f} MP at {TXM['nm_per_px']:.2f} "
    f"nm/px — one magnification for the whole determination, against which the crack "
    f"separates by only {TXM['raw_sep_sd']:.2f} sd. **(2) Destitch + flat-field**, the "
    f"**human** view and not the model input (see below); it divides by an anisotropic "
    f"Gaussian (σy 16, σx 22) and measures {TXM['disp_sep_sd']:.2f} sd separation. "
    f"**(3) 17 hand-built channels** — intensity, smooth σ 2–64, gradmag σ 1–8, laplacian "
    f"σ 1–8, texture σ 2 and 8; four are shown as a 2×2 montage. Ranked by separation in "
    f"matrix sd: texture σ 8 at 1.83, texture σ 2 at 1.52, gradmag σ 4 at 1.42, against raw "
    f"intensity at 0.26 — local variance carries the crack in TXM and brightness does not, "
    f"the reverse of the SEM arm. **(4) SAM ViT-H embedding**, `facebook/sam-vit-huge` as a "
    f"**frozen encoder**; the prompt encoder and mask decoder are never called. 1024 px tiles "
    f"at stride 896, 256 channels at stride 16, bilinearly sampled and Hann-blended; shown "
    f"as RGB are the 3 leading principal components of those 256 channels. **(5) Member A**, "
    f"17→64→32→1, which runs with no encoder and is the fallback when SAM is unreachable: "
    f"grouped 5-fold IoU 0.726, and on this window it puts p > 0.60 across 59 % of the frame "
    f"— it finds the trace, not the edge. **(6) Member B**, 273→128→64→1, the same 17 "
    f"channels concatenated with the 256 embedding channels: grouped 5-fold IoU 0.786, 8 % of "
    f"this window. **(7) Mean probability → mask**, `predict()` returns (A + B) / 2 at "
    f"threshold 0.60, then `prune_specks`. **(8) Against the operator** — red both, blue "
    f"painted and missed, amber model only: this frame's full-resolution IoU is "
    f"{TXM['frame_iou']:.3f} against a median of {TXM['corpus_median_iou']:.3f} over "
    f"{TXM['corpus_n']} labelled frames, so it was chosen because it is typical. Nearly all "
    f"the disagreement is boundary rather than existence, and the boundary is what a width "
    f"measurement is computed from."),
  extended=[
   ("How the panels were made, and what the scores are.",
    f"Each stage function was imported from the shipped pipeline and called on a real array; "
    f"the TXM ensemble panel was checked bit-identical to the application's own cached "
    f"probability map. The SEM arm is 142 frames over 86 fields and 14 specimen groups; the "
    f"TXM arm is 71 frames. **TXM panel 2 is a human view and not a model input**: the "
    f"pipeline stores two arrays, `img.npy` (the raw path, normalised) which is what the "
    f"model reads, and `display.npy` (destitched, flat-fielded) which is what the operator "
    f"sees. `pipeline.py` gives the reason in its own comment — the model is fed raw because "
    f"that is what it was trained on, while thin faint cracks are often visible only under "
    f"local contrast — so the two are deliberately different images sharing one geometry, and "
    f"a mask from either registers on the other. **The SEM arm no longer scores its candidate "
    f"regions.** The logistic model over eight shape and darkness features that used to is "
    f"still on disk and is figure 2's subject, but `USE_REGION_CLASSIFIER` is False and its "
    f"verdict is not consulted. Deleting it beat keeping it on precision, recall, IoU and F1 "
    f"at once with zero free parameters — paired median IoU +0.1753 over 13 specimens, 11 of "
    f"13 better, Wilcoxon p = 0.0061, recorded with its measurement in "
    f"`analysis/detector_overrides.py`. On this frame it would have kept "
    f"{PROD['frame_archived_kept']:,} of {PROD['frame_candidates']:,} regions. What stays "
    f"fitted on this arm is Pass 2's 11-feature model, which gates every pixel panel 7 adds. "
    f"On the TXM arm, grouped "
    f"5-fold IoU is 0.811 ± 0.023 for the mean of the two members against 0.786 and 0.726 "
    f"for the members themselves, and averaging beat both in every fold. Both members were "
    f"fitted on the operator's own corrections across all 71 frames and on no external "
    f"label. **These are detection scores. They are not measurement accuracy**, and the "
    f"application is built so that they cannot be read as if they were."),
  ])
import json as _json
_json.dump(CAPTION, open(out.replace(".png", ".caption.json"), "w"), indent=1, ensure_ascii=False)
print("wrote caption json")
