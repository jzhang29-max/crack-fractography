"""Figure 2 -- what the two models are MADE of.

Every dimension, layer shape, parameter count, coefficient and threshold here was read
out of the shipped artefacts (models/crack_classifier.joblib,
interior_active_learning/models/unified_model.joblib, models/f17_v5_20260824.joblib,
models/hybrid_v5_20260824.joblib and facebook/sam-vit-huge's own config), not copied
from documentation.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = _paths.FIG_CACHE
SEM = json.load(open(f"{HERE}/sem_stats.json"))
TXM = json.load(open(f"{HERE}/txm_stats.json"))

INK, MUT, RULE = (24, 24, 26), (98, 98, 104), (210, 210, 206)
RED, BLU, AMB, GRN, VIO, SLT = (196, 42, 42), (38, 102, 190), (186, 120, 10), (28, 118, 74), (112, 62, 172), (96, 104, 118)
# one colour per KIND of stage, used in both columns and in the key
K = {"in":   ((242, 242, 238), SLT,  "input"),
     "det":  ((238, 244, 250), BLU,  "deterministic image processing"),
     "fit":  ((252, 238, 238), RED,  "fitted to this lab's labels"),
     "froz": ((244, 238, 252), VIO,  "frozen, pre-trained, 637 M params"),
     "hum":  ((252, 246, 232), AMB,  "operator"),
     "meas": ((236, 248, 240), GRN,  "measurement")}

def font(sz, bold=False):
    for p in (("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
               else "/System/Library/Fonts/Supplemental/Arial.ttf"),
              "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try: return ImageFont.truetype(p, sz)
        except Exception: pass
    return ImageFont.load_default()

F_T, F_S = font(46, True), font(22)   # no longer drawn; title/standfirst go to the caption
F_H, F_HN = font(32, True), font(26)
F_BH, F_B, F_SM, F_XS = font(26, True), font(15), font(24), font(24)
MIN_PX = 24   # F_SM / F_XS, the smallest sizes still drawn
LH = 17
BOXPROSE = []   # (head, [lines]) collected out of the boxes and typeset in the caption

W, M = 1448, 80
GUT = 46
CW = W - 2*M
_pb = ImageDraw.Draw(Image.new("RGB", (8, 8)))

def wrap(t, f, w):
    out, line = [], ""
    for word in t.split():
        s = (line+" "+word).strip()
        if _pb.textlength(s, font=f) <= w: line = s
        else:
            if line: out.append(line)
            line = word
    if line: out.append(line)
    return out

img = Image.new("RGB", (W, 2200), "white")
d = ImageDraw.Draw(img)

def box(x, y, w, kind, head, lines, rhs=None):
    """A stage box: head, and the one-phrase annotation on its right. Returns its bottom y.

    The body prose that used to sit inside every box is COLLECTED, not drawn. At 15 px in a
    2,782 px plate it rendered at 2.3 pt on the page; mkpdf.py sets it at 8.2 pt from the
    caption JSON instead. What stays is the diagram: stage name, kind-colour and parameter
    count, which is what a composition figure is for.
    """
    fill, edge, _ = K[kind]
    if lines:
        BOXPROSE.append((head, [l for l in lines if l.strip()]))
    hw = d.textlength(head, font=F_BH)
    rw = d.textlength(rhs, font=F_SM) if rhs else 0
    # at MIN_PX a long head and a long rhs no longer share a line; measure rather than hope
    stacked = bool(rhs) and (hw + 24 + rw > w - 32)
    h = 14 + 36 + (30 if stacked else 0) + 10
    d.rounded_rectangle([x, y, x+w, y+h], radius=7, fill=fill, outline=edge, width=2)
    d.rectangle([x, y+2, x+6, y+h-2], fill=edge)
    d.text((x+16, y+12), head, font=F_BH, fill=INK)
    if rhs:
        if stacked:
            d.text((x+16, y+50), rhs, font=F_SM, fill=edge)
        else:
            d.text((x+w-16-rw, y+16), rhs, font=F_SM, fill=edge)
    return y+h

def arrow(cx, y0, y1, col=SLT, label=None):
    d.line([cx, y0, cx, y1-9], fill=col, width=3)
    d.polygon([(cx-7, y1-10), (cx+7, y1-10), (cx, y1)], fill=col)
    if label:
        d.text((cx+14, (y0+y1)//2-9), label, font=F_SM, fill=col)

def barchart(x, y, w, h, labels, vals, title, sub, pos_col=RED, neg_col=BLU, fmt="{:+.3f}", zero=True):
    d.text((x, y), title, font=F_BH, fill=INK)
    yy = y + 34
    for ln in wrap(sub, F_SM, w):
        d.text((x, yy), ln, font=F_SM, fill=MUT); yy += 28
    yy += 8
    lw = max(d.textlength(l, font=F_SM) for l in labels) + 14
    vw = 108
    bw = w - lw - vw
    mx = max(abs(v) for v in vals) or 1
    # h is the CALLER's hint. At the old 14 px font 300 px held 8 rows; at 24 px it does not,
    # and (h - header)//8 went negative, which PIL reports as "y1 must be >= y0" from inside
    # the bar rectangle rather than as a layout error. Row height is driven by the font now
    # and the chart returns its real bottom, so the column below it moves down with it.
    rh = max(round(F_SM.size * 1.5), (h - (yy-y))//len(labels))
    bh = min(rh-8, 26)
    for l, v in zip(labels, vals):
        d.text((x, yy+(rh-bh)//2-1), l, font=F_SM, fill=INK)
        bx = x+lw
        if zero:
            mid = bx + bw/2
            d.line([mid, yy, mid, yy+rh], fill=RULE, width=1)
            L = abs(v)/mx*(bw/2 - 4)
            if v >= 0: d.rectangle([mid, yy+(rh-bh)//2, mid+L, yy+(rh-bh)//2+bh], fill=pos_col)
            else:      d.rectangle([mid-L, yy+(rh-bh)//2, mid, yy+(rh-bh)//2+bh], fill=neg_col)
        else:
            L = abs(v)/mx*(bw-4)
            d.rectangle([bx, yy+(rh-bh)//2, bx+L, yy+(rh-bh)//2+bh], fill=pos_col)
        d.text((x+lw+bw+8, yy+(rh-bh)//2-1), fmt.format(v), font=F_SM, fill=MUT)
        yy += rh
    return yy

# ------------------------------------------------------------------ header
# Six swatches no longer fit one row at this width: at 2,782 px they did, and after the
# columns were stacked "operator" and "measurement" ran off the right edge and were cropped.
kx, ky = M, 24
for kind in ("in", "det", "fit", "froz", "hum", "meas"):
    fill, edge, lab = K[kind]
    need = 46 + d.textlength(lab, font=F_SM) + 34
    if kx > M and kx + need > W - M:
        kx, ky = M, ky + 38
    d.rounded_rectangle([kx, ky, kx+30, ky+28], radius=4, fill=fill, outline=edge, width=2)
    d.text((kx+40, ky+2), lab, font=F_SM, fill=MUT)
    kx += need
KEYBOT = ky + 48
d.line([M, KEYBOT, W-M, KEYBOT], fill=INK, width=2)

# ------------------------------------------------------------------ SEM column
X0 = M
d.rectangle([X0, KEYBOT+20, X0+6, KEYBOT+52], fill=RED)
d.text((X0+18, KEYBOT+18), "SEM arm — region classifier, two passes", font=F_H, fill=INK)
d.text((X0+18, KEYBOT+56), "Candidate REGIONS are scored, not pixels. 9 fitted coefficients in pass 1, 12 in pass 2.", font=F_HN, fill=MUT)

bx, bw = X0, 700
cx = bx + bw//2
y = KEYBOT + 98
y = box(bx, y, bw, "in", "Back-scattered SEM frame",
        [f"16-bit TIFF, {SEM['full'][0]}×{SEM['full'][1]} px, {SEM['nm_per_px']:.1f} nm/px. 142 frames = 86 physical fields, many imaged through two detectors, over 14 specimens."],
        rhs="25 MP")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "det", "load_as_uint8",
        ["Rescale on the frame's own 1–99.5 percentile. A databar, if present, is detected",
         "by two independent signals (row mean+sd collapse, and a full-width step) and cropped."], rhs="no parameters fitted")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "det", "flatten_background  ·  σ = 40 px",
        ["Subtract a Gaussian copy, stretch on 0.5–99.5. Makes one global threshold viable;",
         "costs contrast and removes voids wider than the blur radius."], rhs="σ chosen, not learned")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "det", "compute_vesselness  ·  Frangi, σ = 1–6",
        ["Hessian eigenvalue ratio, black_ridges=True. Separates thin curves from round blobs,",
         f"which darkness alone cannot: {SEM['ves_ratio']:.1f}:1 crack-to-matrix on the window in figure 1."], rhs="becomes feature 8")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "det", "segment_dark_regions  +  clean_mask",
        ["min(Otsu, median − 5·MAD·1.4826)  OR  absolute DN < 10 for wide voids.",
         "Then open r=1, close r=3, drop < 13 px — max(5, 40 // 3), the production value, not",
         "clean_mask's own default of 15. Fill holes.",
         f"On the example frame, over the {SEM['full'][1]}×{SEM['full'][0]} extent it shares with its masks: "
         f"{SEM['frame_dark_pct']:.2f}% dark → {SEM['frame_components']} components → {SEM['frame_candidates']} candidates ≥ 40 px.",
         "The threshold is global, so the extent chosen changes these counts."],
        rhs="candidate proposal")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "fit", "PASS 1  ·  StandardScaler → LogisticRegression",
        ["8 region features → 8 weights + 1 intercept. class_weight='balanced', max_iter=2000.",
         f"Fitted on {SEM['n_train']:,} adjudicated regions from {SEM['n_images']} images ({SEM['n_train']:,} = 6,408 crack / 1,097 not).",
         f"Operating point {SEM['threshold']:.4f}, read from the bundle — transferred by quantile from a",
         f"held-out image, NOT the 0.5 library default. Pooled grouped-CV AUC {SEM['pooled_auc']:.3f} ± {SEM['pooled_auc_sd']:.3f}."],
        rhs="9 fitted parameters")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "fit", "PASS 2  ·  interior fill, 11 features",
        ["Adds MeanRawBrightness, MeanFlatBrightness, FracBoundaryTouchingCrack, MeanDistToCrack",
         "— context rather than shape — and a geometric rule calibrated on known positives:",
         "accept within 12.9 px of accepted crack and below 135.8 flat brightness, floor 0.65.",
         "Recall 0.82 on known positives at a 0.54 accept rate over the full pool. Fill only:",
         "pass 1's output is a strict subset of the result."],
        rhs="12 fitted parameters")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "hum", "Operator reviews whole regions",
        ["Add or remove a region before anything is measured; every change is written to a ledger",
         "(44 of the 142 SEM frame-records carry one). Not a brush — the unit of correction is the unit of decision."],
        rhs="auditable")
arrow(cx, y, y+26); y += 26
y_sem_end = box(bx, y, bw, "meas", "Measurement",
        ["Per crack: area, mean/max width, geodesic length, skeleton, junction order, orientation",
         "on doubled angles, H/W elongation. Per frame: P21, characteristic length, orientation",
         "histogram. Per specimen: ASTM E562 interval from BETWEEN-FIELD variance only."],
        rhs="what is reported")

# the coefficients, read off the fitted model
CO = [("MeanVesselness", -0.574), ("Elongation", +0.324), ("Extent", -0.316),
      ("Eccentricity", +0.195), ("LogArea", +0.131), ("Solidity", +0.090),
      ("Circularity", +0.048), ("MeanDarkness", -0.037)]
rx = X0 + bw + 40
rw = CW - bw - 40
by = barchart(rx, KEYBOT + 98, rw, 300, [c[0] for c in CO], [c[1] for c in CO],
         "Pass 1: the 8 weights, as fitted",
         "Standardised coefficients from the deployed bundle. Sign is toward 'crack'. "
         "Vesselness is the largest single term and it is NEGATIVE: given a region's shape, more "
         "ridge-like texture inside it argues AGAINST crack on this training set. Darkness is the "
         "smallest term of the eight — the thing a human looks at first.")
by += 10
by = box(rx, by, rw, "det", "Why linear, measured not assumed",
    ["On the same grouped split, trees score HIGHER raw accuracy — RandomForest 0.834,",
     "GradientBoosting 0.849, SVC 0.837 against LogisticRegression's 0.655 — by calling almost",
     "everything crack. Their specificity is 0.008, 0.009 and 0.005 on a set that is 85% positive.",
     "Ranked by pooled AUC instead, the order reverses: 0.714 against 0.508, 0.533 and 0.276.",
     "Accuracy on an 85%-positive set is not a model comparison; that is why the linear one ships."],
    rhs="AUC 0.714 vs 0.51, 0.53, 0.28")
by += 10
by = box(rx, by, rw, "fit", "Pass 2's weights put CONTEXT first",
    ["MeanDistToCrack −1.956 · MeanFlatBrightness +1.890 · MeanVesselness +1.364",
     "LogArea −1.125 · MeanRawBrightness −0.852 · Extent −0.532 · Solidity −0.439",
     "Circularity −0.283 · FracBoundaryTouchingCrack −0.185 · Eccentricity −0.080 · Elongation +0.062",
     "The two strongest terms are both relational: how far this region sits from crack already",
     "accepted, and how bright it is after flattening. Vesselness flips sign between passes."],
    rhs="11 features, intercept −0.225")

# ------------------------------------------------------------------ TXM arm, below the SEM arm
X1 = M
TXMTOP = max(y_sem_end, by) + 64
d.line([M, TXMTOP - 28, W-M, TXMTOP - 28], fill=RULE, width=2)
d.rectangle([X1, TXMTOP, X1+6, TXMTOP+32], fill=BLU)
d.text((X1+18, TXMTOP-2), "TXM arm — per-pixel ensemble of two MLPs", font=F_H, fill=INK)
d.text((X1+18, TXMTOP+36), "Every PIXEL is scored. 46,658 fitted parameters sit on top of 637 M frozen ones.", font=F_HN, fill=MUT)

tw_ = CW
y = TXMTOP + 78
tcx = X1 + tw_//2
y = box(X1, y, tw_, "in", "X-ray tomographic microscopy mosaic",
        [f"16-bit, {TXM['full'][0]}×{TXM['full'][1]} px, {TXM['megapixels']} MP, {TXM['nm_per_px']} nm/px — ONE magnification per determination.",
         "71 labelled frames. Dominant variation is tile-to-tile illumination, not specimen."], rhs="10.3 MP")
arrow(tcx, y, y+24); y += 24
y = box(X1, y, tw_, "det", "destitch  →  flat-field  →  robust_normalize (1–99 pct → [0,1])",
        ["TWO ARRAYS, NOT ONE, and this box asserted the opposite. img.npy — the raw path,",
         "normalised — is the MODEL input. display.npy — destitched, then DIVIDED by an",
         "anisotropic Gaussian (σy 16, σx 22) — is the HUMAN view. The pipeline's own comment",
         "gives the reason: the model is fed raw because that is what it was trained on, while",
         "thin faint cracks are often visible only under local contrast. Both preserve geometry,",
         "so a raw-derived mask still registers on the display."], rhs="no parameters fitted")
arrow(tcx, y, y+24); y += 24
y = box(X1, y, tw_, "det", "compute_feature_stack  →  17 channels",
        ["intensity  ·  smooth σ 2, 4, 8, 16, 32, 64  ·  gradmag σ 1, 2, 4, 8  ·  laplacian σ 1, 2, 4, 8  ·  texture (local sd) σ 2, 8"],
        rhs="hand-built, scale-aware")
split_y = y + 22
# two branches
BW = (tw_ - 40)//2
ax, bx2 = X1, X1 + BW + 40
d.line([tcx, y, tcx, split_y], fill=SLT, width=3)
d.line([ax+BW//2, split_y, bx2+BW//2, split_y], fill=SLT, width=3)
arrow(ax+BW//2, split_y, split_y+26); arrow(bx2+BW//2, split_y, split_y+26)
ay = split_y + 26
by2 = split_y + 26
ay = box(ax, ay, BW, "fit", "MEMBER A",
    ["StandardScaler → MLPClassifier",
     "17 → 64 → 32 → 1, ReLU, logistic out.",
     "3,265 fitted parameters, 204 iterations,",
     "final loss 0.2419.",
     "Needs no encoder, so it is the automatic",
     "fallback when SAM cannot be reached.",
     "Grouped 5-fold mean IoU 0.726."], rhs="3,265 params")
by2 = box(bx2, by2, BW, "froz", "SAM ViT-H image encoder  ·  FROZEN",
    ["facebook/sam-vit-huge. 641.1 M parameters,",
     "of which the image encoder is 637.0 M — 99.4%.",
     "ViT-H: 32 blocks, d = 1280, 16 heads, patch 16,",
     "windowed attention 14 with global attention at",
     "blocks 7, 15, 23, 31; 1024² input → 256 ch at",
     "stride 16. The prompt encoder (256-d) and the",
     "2-layer mask decoder are NEVER CALLED — this",
     "arm uses SAM as a texture descriptor, not as",
     "a segmenter."], rhs="0 params fitted")
arrow(bx2+BW//2, by2, by2+24); by2 += 24
by2 = box(bx2, by2, BW, "det", "Tile, then blend",
    [f"{TXM['sam_tile']} px tiles at stride {TXM['sam_stride']} so neighbours OVERLAP",
     f"({TXM['sam_tiles']} tiles for this frame). Each pixel's 256-vector",
     "is bilinear within a tile and Hann-weighted",
     "across every tile covering it. Abutting tiles",
     "instead put a 32.8× probability step at the",
     "seam; reaching past a tile edge invents data",
     "and raised crack-free false positives 6.2×."], rhs="+13% tiles")
arrow(bx2+BW//2, by2, by2+24); by2 += 24
by2 = box(bx2, by2, BW, "fit", "MEMBER B  ·  concat 17 + 256 = 273",
    ["StandardScaler → MLPClassifier",
     "273 → 128 → 64 → 1, ReLU, logistic out.",
     "43,393 fitted parameters, 64 iterations,",
     "final loss 0.0280. Fitted on 3,530,484 sampled",
     "pixels from all 71 frames, 49.2% crack,",
     "recipe thincore_v5, stamp 20260824_225236.",
     "Grouped 5-fold mean IoU 0.786 — but it loses",
     "badly on the single 23.5 MP mosaic."], rhs="43,393 params")
mergey = max(ay, by2) + 24
d.line([ax+BW//2, max(ay, by2)+2, ax+BW//2, mergey], fill=SLT, width=3)
d.line([bx2+BW//2, max(ay, by2)+2, bx2+BW//2, mergey], fill=SLT, width=3)
d.line([ax+BW//2, mergey, bx2+BW//2, mergey], fill=SLT, width=3)
arrow(tcx, mergey, mergey+26)
y = box(X1, mergey+26, tw_, "fit", f"predict() = (A + B) / 2   →   p > {TXM['threshold']:.2f}   →   prune_specks",
    ["Averaging beat BOTH members in EVERY fold — 0.811 against 0.786 and 0.726 — which is the",
     "property worth having, since a mean can be carried by one fold. Deployed gate record: IoU",
     "0.8113, sd 0.0229, worst fold 0.7777, precision 0.9355, recall 0.8597, grouped by image over",
     "71 frames. A third SAM-only member adds +0.009 IoU, below the 0.0070 retrain-noise floor,",
     "so it is excluded. Threshold 0.60 was chosen jointly with pruning, not on threshold alone."],
    rhs="+25% inference time over B alone")
arrow(tcx, y, y+24); y += 24
y = box(X1, y, tw_, "hum", "Operator paints, and the model is refitted on what they painted",
    ["Both members were fitted on the owner's own corrections across all 71 frames and on nothing",
     "else: no external label is used in training or in the gate. Retrain is a button, and each",
     "retrain is gated against an absolute floor rather than against its predecessor."], rhs="auditable")
arrow(tcx, y, y+24); y += 24
y_txm_end = box(X1, y, tw_, "meas", "Measurement — the same code as the SEM arm",
    ["Identical measurement, editor, export and refusal logic; the arms differ only in how the mask",
     "is produced. Width = area / centreline length, 0.34–1.21 µm between specimens, and it varies",
     "50× within the corpus while tracking depth at ρ = +0.67."], rhs="one implementation")

# ------------------------------------------------------------------ bottom strip
last = max(y_sem_end, y_txm_end, by)
img = img.crop((0, 0, W, min(img.height, last + 30)))
out = os.path.join(_paths.FIG_DIR, "2 - what the models are made of.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
img.save(out)
print("wrote", out, img.size, "min_px", MIN_PX)

# ---------------------------------------------------------------- caption
# The "Does a newer SAM help?" block that used to run across the foot of this figure is a
# RESULT, not a legend, and it is reproduced here in full because section 1's claim 5 is the
# only other place it appears. The per-box prose is taken from BOXPROSE, which box() filled
# as it drew, so the caption cannot drift from the diagram: every box that carries prose
# appears here under its own drawn heading, in drawing order.
CO_TEXT = ("**Pass 1: the 8 weights, as fitted** \u2014 standardised coefficients from the deployed "
           "bundle, drawn as the bar panel beside the SEM column; sign is toward crack. "
           + " \u00b7 ".join(f"{n} {v:+.3f}" for n, v in CO) +
           ". Vesselness is the largest single term and it is negative: given a region's shape, "
           "more ridge-like texture inside it argues against crack on this training set. "
           "Darkness is the smallest of the eight \u2014 the thing a human looks at first.")
_key = ("Colour says what kind of stage it is, keyed along the top: input; deterministic image "
        "processing; fitted to this laboratory's labels; frozen and pre-trained; operator; "
        "measurement. The left column is the SEM arm, scoring candidate **regions** with 9 "
        "fitted coefficients in pass 1 and 12 in pass 2; the right column is the TXM arm, "
        "scoring every **pixel**, with 46,658 fitted parameters on top of 637 M frozen ones. "
        "Stage by stage: ")
def _join(ls):
    out = ""
    for ln in ls:
        ln = ln.strip()
        if not out:
            out = ln
        elif out[-1] in ".;:,\u2014":
            out += " " + ln
        else:
            out += "; " + ln
    return out
_key += " ".join(f"**{h}** \u2014 {_join(ls)}" for h, ls in BOXPROSE)
_key += " " + CO_TEXT

CAPTION = dict(
  min_px=MIN_PX,
  lead=("What the two models are made of: every layer shape, parameter count, coefficient and "
        "threshold was read out of the shipped model files and SAM's own configuration rather "
        "than from documentation, because in this project the documentation went stale twice "
        "while the files did not."),
  panel_key=_key,
  extended=[
   ("Does a newer SAM help? Asked by measurement, on paired pixels, and the answer was no.",
    "SAM is used here as a frozen **dense feature** source, so the only question that matters "
    "is whether a newer encoder's features are more discriminative. Prompted the way SAM is "
    "designed to be prompted \u2014 zero-shot, from a box or a point \u2014 it measures 0.23\u20130.36 IoU "
    "on the four external reference frames, against 0.819 for the two-member ensemble on the "
    "same four. SAM 3's headline capability, "
    "open-vocabulary segmentation from a text prompt, is therefore the part of it this project "
    "can use least: there is no noun phrase for a hairline fatigue crack in a grayscale X-ray "
    "of 316L that a web-trained model holds a prior on. All three generations emit 256 "
    "channels, and SAM 2's nearest pyramid level is also stride 16, so the 273-d vector is "
    "unchanged and nothing downstream moves."),
   ("SAM 1 ViT-H against SAM 2.1 Hiera-L, paired on identical pixels.",
    "Leave-one-frame-out over 4 dense reference frames, 120,000 px each, two seeds, with the "
    "same sampled indices in both arms so that the 17 hand-built columns are byte-identical "
    "and only the 256 embedding channels differ. The ensemble, which is the thing that ships: "
    "IoU +0.0011 (t = 0.16, p = 0.87), AUC +0.0013 (p = 0.20). The hybrid member alone: IoU "
    "+0.0213 (t = 2.23, p = 0.061), AUC +0.0052 (p = 0.029). False positives on 6 crack-free "
    "specimens: +0.146 pp (t = 1.66, p = 0.16), worse on four of six. SAM 2's features **are** "
    "better in isolation; the ensemble conceals it, because it averages in a 17-feature member "
    "that is identical across arms and so halves whatever the encoder adds."),
   ("The decision, and what it predicts about SAM 3.",
    "Do not switch: +0.001 IoU on the shipped model, against a second 856 MB encoder download "
    "in every install and a nominal false-positive cost pointing the wrong way. Capturing the "
    "isolated gain would mean dropping the 17-only member and forfeiting the ensemble's "
    "advantage elsewhere. `facebook/sam3` is gated and answers 403, and the GitHub repository "
    "ships code rather than checkpoints, so a SAM 3 arm stays wired in and reports itself "
    "skipped rather than guessing. A full architecture generation \u2014 plain ViT to Hiera \u2014 "
    "bought +0.005 AUC on the isolated member and nothing on the ensemble, so SAM 3 is "
    "unlikely to be transformative here. The binding limitation is label coverage on the AM "
    "and HC specimens, not the encoder."),
  ])
import json as _json
_json.dump(CAPTION, open(out.replace(".png", ".caption.json"), "w"), indent=1, ensure_ascii=False)
print("wrote caption json;", len(BOXPROSE), "boxes carried prose")
