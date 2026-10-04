"""Figure 1 -- what each filter and model stage does, panel by panel.

Every image panel is a real array written by sem_fullframe.py / txm_full.py, which import
and call the shipped pipelines' own functions. The TXM ensemble panel was verified
bit-identical to the app's cached probability map (mean |diff| = 0.0).

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
SEM = json.load(open(f"{HERE}/sem_stats.json"))
TXM = json.load(open(f"{HERE}/txm_stats.json"))
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
_SKEL = (0, 0)


def measured_panel(g8, gated):
    """Mask, plus the geometry the measurements are actually taken from."""
    global _SKEL
    from skimage import morphology
    sk = morphology.skeletonize(np.asarray(gated, bool))
    nb = ndi.convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant") - sk
    junc = sk & (nb >= 3)
    lab, nj = ndi.label(junc, structure=np.ones((3, 3)))
    _SKEL = (int(sk.sum()), int(nj))
    jd = ndi.binary_dilation(junc, iterations=3)
    skd = ndi.binary_dilation(sk, iterations=1)
    return over(g8, [(np.asarray(gated, bool), (242, 170, 170), 0.80),
                     (skd, (150, 16, 16), 1.0),
                     (jd, (20, 70, 180), 1.0)])


def sem_panels():
    img8, flat, ves = L("sem_img8"), L("sem_flat"), L("sem_ves")
    clean, prob, pass1 = L("sem_clean"), L("sem_prob"), L("sem_pass1")
    mach, gated = L("sem_mach"), L("sem_gated")
    thr = SEM["threshold"]; g8 = np.asarray(img8, np.uint8)
    micro = locator(grey(img8, 0, 255), f"{HERE}/sem_frame_thumb.png", SEM["crop"], SEM["full"])

    vhi = float(np.percentile(ves, 99.5))
    vimg = ramp(ves, GLOW, 0, vhi, gamma=0.5)

    # probability: colour by side of the decision point, lightness by distance from it
    conf = np.clip(np.abs(prob-thr)/0.22, 0, 1)
    al = 0.30 + 0.60*conf
    base = np.dstack([g8]*3).astype(np.float32)*0.30 + 178
    out = base.copy()
    for side, col in ((prob >= thr, BLU), ((prob < thr) & clean, AMB)):
        mm = side & clean
        for c in range(3):
            out[..., c][mm] = (1-al[mm])*base[..., c][mm] + al[mm]*col[c]
    probpanel = tag(Image.fromarray(out.clip(0, 255).astype(np.uint8)),
                    f"blue  p ≥ {thr:.3f}  keep\namber p < {thr:.3f}  drop")

    return [
      ("1", "Micrograph", micro, [
        f"16-bit back-scattered TIFF, {SEM['full'][0]}×{SEM['full'][1]} px at {SEM['nm_per_px']:.1f} nm/px, rescaled to 8-bit on its own",
        "1–99.5 percentile by load_as_uint8. The window shown is 1200 px, 2.5% of the frame (inset).",
        f"Crack sits at DN {SEM['crack_dn']:.0f} against a DN {SEM['matrix_dn']:.0f} matrix whose own spread is ±{SEM['matrix_sd']:.1f} DN — a",
        f"{SEM['sep_raw_sd']:.1f} sd gap ON THIS WINDOW — 6.6 sd over the whole frame. SEM is the easy",
        "modality, and the white specks are a second phase rather than noise."]),
      ("2", "flatten_background", grey(flat, 0, 255), [
        "Subtract a σ = 40 px Gaussian copy, then stretch on the 0.5–99.5 percentile.",
        f"This is NOT a contrast step — contrast falls, {SEM['sep_raw_sd']:.1f} sd → {SEM['sep_flat_sd']:.1f} sd on this",
        "window and 6.6 → 4.7 sd over the whole frame. It exists so that ONE",
        "threshold can work across a frame with illumination drift. Its known cost: a void wider",
        "than the blur radius is itself a low-frequency feature and is removed with the drift,",
        "which is why an absolute-darkness test is OR-ed back in at the next stage."]),
      ("3", "Frangi vesselness", tag(vimg, f"crack {SEM['ves_crack']:.4f}\nmatrix {SEM['ves_matrix']:.4f}\nratio {SEM['ves_ratio']:.1f} : 1"), [
        "skimage.filters.frangi, σ = 1–6, black_ridges=True. The ratio of Hessian eigenvalues is",
        "high on thin curvilinear structure and low on round blobs, so a pore and a crack of equal",
        f"darkness separate here where darkness alone cannot tell them apart: {SEM['ves_ratio']:.1f}:1 on this window.",
        "This map becomes one of the eight features, and it is the one the fitted classifier",
        "weights most heavily of all — see figure 2 for the coefficients."]),
      ("4", "Candidate regions", tag(over(g8, [(clean, VIO, 0.78)]),
          f"{SEM['frame_components']} components → {SEM['frame_candidates']} ≥ 40 px"), [
        "segment_dark_regions takes min(Otsu, median − 5·MAD·1.4826), so a unimodal low-contrast frame",
        "cannot be forced into a 50/50 split, OR-ed with an absolute test at DN < 10 for wide voids.",
        f"clean_mask then opens at r = 1, closes at r = 3, drops anything under {SEM['min_area_clean']} px — the",
        "production value max(5, 40 // 3), not clean_mask's own default of 15 — and fills holes.",
        f"Over the {SEM['full'][1]}×{SEM['full'][0]} extent the frame shares with its masks: {SEM['frame_dark_pct']:.2f}% dark → "
        f"{SEM['frame_components']} components → {SEM['frame_candidates']} candidates of {SEM['min_area_candidate']} px or more. The TIFF is 4376 rows,",
        "the masks 4096; the threshold is global, so the extent changes these counts.",
        "No model has run yet. Everything to the left of here is deterministic image processing."]),
      ("5", "Pass 1 · 8 features", probpanel, [
        "Per candidate region: LogArea, Elongation, Solidity, Eccentricity, Extent, Circularity,",
        "MeanDarkness, MeanVesselness → StandardScaler → LogisticRegression(class_weight='balanced').",
        f"The decision point {thr:.3f} is READ FROM the model bundle rather than defaulted to 0.5, and it",
        f"was transferred by quantile from a held-out image. Median p is {SEM['prob_median_kept']:.2f} for what it keeps",
        f"and {SEM['prob_median_dropped']:.2f} for what it drops, so the two populations are genuinely separated."]),
      ("6", "Pass 1 accepted", tag(over(g8, [(pass1, RED, 0.70)]),
          f"{SEM['frame_kept']} of {SEM['frame_candidates']} regions\n{SEM['frame_pass1_pct']:.2f}% of frame"), [
        f"Trained on {SEM['n_train']:,} hand-adjudicated regions from {SEM['n_images']} images. Pooled grouped-CV AUC",
        f"{SEM['pooled_auc']:.3f} ± {SEM['pooled_auc_sd']:.3f}, train and test never sharing an image; leave-one-image-out on a single",
        "frame reads 0.884, and the app quotes the pooled figure because the optimistic one is a",
        "property of that split. Trees score HIGHER raw accuracy here (0.83, 0.85 vs 0.65) by calling",
        "almost everything crack — specificity 0.008 — on a set that is 85% positive. Hence linear."]),
      ("7", "Pass 2 · interior fill", tag(over(g8, [(pass1, RED, 0.55), (mach & ~pass1, AMB, 0.82)]),
          f"red  Pass 1\namber Pass 2 adds {SEM['crop_pass2_added_pp']:.2f} pp", corner="bl"), [
        "A second, separately fitted 11-feature model adds MeanRawBrightness, MeanFlatBrightness,",
        "FracBoundaryTouchingCrack and MeanDistToCrack — context, not shape — alongside a geometric",
        "rule calibrated on known positives: within 12.9 px of accepted crack and below 135.8 flat",
        "brightness. Recall 0.82 on known positives at a 0.54 accept rate over the full pool.",
        f"Pass 1's output is a strict subset of the result ({SEM['crop_pass1_not_mach_pp']:.2f} pp outside it), as a fill must be."]),
      ("8", "Measured", tag(measured_panel(g8, gated), f"{SEM['crop_gated_pct']:.2f}% area \u00b7 {SEM['crop_components']} regions\n{_SKEL[0]:,} px skeleton\n{_SKEL[1]} junction clusters"), [
        "The operator may add or remove whole regions before anything is measured; on this frame they",
        "changed nothing, and the ledger records every frame where they did. Then, per crack: area,",
        "mean and max width, geodesic length, skeleton length (dark red), junction order (blue),",
        "orientation on doubled angles, and H/W elongation. Per frame: P21 line density and an",
        "ASTM E562 interval built from BETWEEN-FIELD variance — never from pixels inside one field."]),
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
SK = (f"{SEM['crop_gated_pct']:.2f} % area over {SEM['crop_components']} regions on this "
      f"window, {_SKEL[0]:,} px skeleton, {_SKEL[1]} junction clusters")
CAPTION = dict(
  min_px=MIN_PX,
  lead=("What every filter and model stage actually does: the SEM arm (top) and the TXM arm "
        "(bottom), each panel real output from the shipped code — the stage function imported "
        "from the pipeline and called on one window of one frame — rather than a schematic."),
  panel_key=(
    f"**SEM arm**, one 1200 px window (2.5 % of the frame, located by the red box in the "
    f"inset) of `{SEM['frame']}`. **(1) Micrograph**, 16-bit back-scattered TIFF, "
    f"{SEM['full'][0]}×{SEM['full'][1]} px at {SEM['nm_per_px']:.1f} nm/px, rescaled to 8-bit on "
    f"its own 1–99.5 percentile; crack sits at DN {SEM['crack_dn']:.0f} against a DN "
    f"{SEM['matrix_dn']:.0f} matrix whose own spread is ±{SEM['matrix_sd']:.1f} DN, a "
    f"{SEM['sep_raw_sd']:.1f} sd gap on this window against 6.6 sd over the whole frame. "
    f"**(2) `flatten_background`**, subtract a σ = 40 px Gaussian and stretch on the "
    f"0.5–99.5 percentile; contrast *falls*, {SEM['sep_raw_sd']:.1f} → "
    f"{SEM['sep_flat_sd']:.1f} sd here, so this is not a contrast step — it exists so that one "
    f"threshold can work across a frame with illumination drift. **(3) Frangi vesselness**, "
    f"σ = 1–6, `black_ridges=True`: crack {SEM['ves_crack']:.4f} against matrix "
    f"{SEM['ves_matrix']:.4f}, a {SEM['ves_ratio']:.1f} : 1 ratio, which is what separates a "
    f"thin curve from a round void of the same darkness. **(4) Candidate regions**, "
    f"`segment_dark_regions` at min(Otsu, median − 5·MAD·1.4826) OR-ed with an absolute "
    f"DN < 10 test, then `clean_mask`: {SEM['frame_dark_pct']:.2f} % dark → {SEM['frame_components']:,} "
    f"components → {SEM['frame_candidates']:,} candidates of 40 px or more. No model has run yet; "
    f"everything to the left of here is deterministic. **(5) Pass 1, 8 features** — LogArea, "
    f"Elongation, Solidity, Eccentricity, Extent, Circularity, MeanDarkness, MeanVesselness "
    f"→ `StandardScaler` → `LogisticRegression(class_weight='balanced')`; the decision point "
    f"{SEM['threshold']:.3f} is read from the model bundle rather than defaulted to 0.5. "
    f"**(6) Pass 1 accepted**, frame-wide {SEM['frame_kept']:,} of {SEM['frame_candidates']:,} regions, "
    f"{SEM['frame_pass1_pct']:.2f} % of frame. **(7) Pass 2, interior fill**, a separately "
    f"fitted 11-feature model adding MeanRawBrightness, MeanFlatBrightness, "
    f"FracBoundaryTouchingCrack and MeanDistToCrack — context, not shape — beside a geometric "
    f"rule; Pass 1 (red) is a strict subset of the result, as a fill must be, and Pass 2 "
    f"(amber) adds {SEM['crop_pass2_added_pp']:.2f} pp on this window. **(8) Measured**, {SK}: the operator may add "
    f"or remove whole regions before anything is measured, and only then are area, width, "
    f"geodesic and skeleton length, junction order and orientation computed. "
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
    f"a mask from either registers on the other. SEM Pass 1 was trained on 7,505 "
    f"hand-adjudicated regions from 45 images, pooled grouped-CV AUC "
    f"{SEM['pooled_auc']:.3f} ± {SEM['pooled_auc_sd']:.3f}, grouped by image and not by "
    f"specimen; leave-one-image-out on a single frame reads 0.884, and the pooled figure is "
    f"quoted because the optimistic one is a property of that split. On the TXM arm, grouped "
    f"5-fold IoU is 0.811 ± 0.023 for the mean of the two members against 0.786 and 0.726 "
    f"for the members themselves, and averaging beat both in every fold. Both members were "
    f"fitted on the operator's own corrections across all 71 frames and on no external "
    f"label. **These are detection scores. They are not measurement accuracy**, and the "
    f"application is built so that they cannot be read as if they were."),
  ])
import json as _json
_json.dump(CAPTION, open(out.replace(".png", ".caption.json"), "w"), indent=1, ensure_ascii=False)
print("wrote caption json")
