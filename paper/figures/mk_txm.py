"""Paper figure: the TXM ladder, which unlike the SEM model ladder actually separates.

Three rungs of the deployed ensemble on one frame, chosen because its full-resolution IoU
(0.503) is the corpus median (0.507) -- so it is a typical frame, not a flattering one.
Beside them, the corpus-level cross-validated scores the rungs were selected on, with the
caveat the audit insisted on: those are a 49%-crack sample of painted pixels, not whole-frame
IoU, and they drop to 0.51-0.67 when a whole specimen is held out.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
FIG = _paths.FIG_CACHE
OUT = _paths.FIG_DIR
TH = 0.60
st = json.load(open(f"{FIG}/txm_stats.json"))
d8 = np.load(f"{FIG}/txm_disp8.npy"); lbl = np.load(f"{FIG}/txm_label.npy")
p17 = np.load(f"{FIG}/txm_p17.npy"); ph = np.load(f"{FIG}/txm_ph.npy"); ens = np.load(f"{FIG}/txm_ens.npy")
mask = np.load(f"{FIG}/txm_mask.npy")
def iou(a, b): return float((a & b).sum()/max((a | b).sum(), 1))

INK, MUT, RULE = (24, 24, 26), (98, 98, 104), (214, 214, 210)
RED, BLU, AMB, GRN = (196, 42, 42), (38, 102, 190), (186, 120, 10), (28, 118, 74)
def font(sz, b=False):
    for p in (("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if b
               else "/System/Library/Fonts/Supplemental/Arial.ttf"),):
        try: return ImageFont.truetype(p, sz)
        except Exception: pass
    return ImageFont.load_default()
F_T, F_S, F_H, F_B, F_C = font(40, True), font(19), font(22, True), font(16), font(15)
_pb = ImageDraw.Draw(Image.new("RGB", (8, 8)))
def wrap(t, f, w):
    o, l = [], ""
    for wd in t.split():
        s = (l + " " + wd).strip()
        if _pb.textlength(s, font=f) <= w: l = s
        else:
            if l: o.append(l)
            l = wd
    if l: o.append(l)
    return o

PANELS = [
    ("Operator's painted crack", lbl, BLU),
    ("A  17 hand-built channels", p17 > TH, RED),
    ("B  + SAM ViT-H embedding", ph > TH, RED),
    ("C  mean of A and B, pruned", mask, RED),
]

# Title, standfirst, per-panel paragraphs and the three footer columns are no longer drawn:
# baked into a 1,966 px plate they rendered at 3.7 pt on the page. They are emitted as a
# caption JSON and typeset by mkpdf.py at 8.2 pt. What stays is a panel name and the one
# number the panel exists to show.
F_H, F_B = font(30, True), font(26)
MIN_PX = 26

T, GAP, M = 430, 22, 40
W = M*2 + len(PANELS)*T + (len(PANELS)-1)*GAP
img = Image.new("RGB", (W, T + 200), "white"); d = ImageDraw.Draw(img)
y0 = 16
for i, (title, m, col) in enumerate(PANELS):
    x = M + i*(T + GAP)
    a = np.dstack([np.asarray(d8, np.uint8)]*3).astype(np.float32)
    mm = np.asarray(m, bool)
    for c in range(3): a[..., c][mm] = 0.32*a[..., c][mm] + 0.68*col[c]
    img.paste(Image.fromarray(a.clip(0, 255).astype(np.uint8)).resize((T, T), Image.LANCZOS), (x, y0))
    d.rectangle([x-1, y0-1, x+T, y0+T], outline=RULE, width=1)
    d.text((x, y0+T+14), f"({i+1})  {title}", font=F_H, fill=INK)
    stat = (f"IoU {iou(mm, lbl):.3f}   covers {100*mm.mean():.2f} % of window" if i
            else f"{100*mm.mean():.2f} % of window")
    d.text((x, y0+T+52), stat, font=F_B, fill=col)
ly = y0 + T + 96
d.rectangle([M, ly+6, M+22, ly+24], fill=RED)
d.text((M+32, ly+2), "model", font=F_B, fill=(66, 66, 72))
xx = M + 32 + int(d.textlength("model", font=F_B)) + 60
d.rectangle([xx, ly+6, xx+22, ly+24], fill=BLU)
d.text((xx+32, ly+2), "operator", font=F_B, fill=(66, 66, 72))
img = img.crop((0, 0, W, ly + 40))
os.makedirs(OUT, exist_ok=True)
p = os.path.join(OUT, "4 - TXM, what each stage adds.png")
img.save(p); print("wrote", p, img.size, "min_px", MIN_PX)

# ---------------------------------------------------------------- caption
CAPTION = dict(
  min_px=MIN_PX,
  lead=("What each stage of the TXM detector adds: the operator's painted crack beside the "
        "three rungs of the deployed ensemble, on one window of a typical frame rather than a "
        "flattering one."),
  panel_key=(
    f"Red is the model, blue the operator. **(1) Operator's painted crack**, "
    f"{100*lbl.mean():.2f} % of the window \u2014 the reference for this window; 61 of the 71 TXM "
    f"frames carry crack strokes and 70 carry erase strokes, so the shipped TXM masks are "
    f"human-gated throughout. **(2) A, 17 hand-built channels** \u2014 IoU {iou(p17>TH, lbl):.3f}, "
    f"covering {100*(p17>TH).mean():.2f} % of the window; `StandardScaler` \u2192 MLP(64, 32); "
    f"channels: intensity, smooth \u03c3 2\u201364, gradmag \u03c3 1\u20138, laplacian \u03c3 1\u20138, texture \u03c3 2 and 8. "
    f"Runs with no encoder and is the fallback when SAM is unreachable; it finds the crack's "
    f"trace and floods the matrix with it. **(3) B, + SAM ViT-H embedding** \u2014 IoU "
    f"{iou(ph>TH, lbl):.3f}, covering {100*(ph>TH).mean():.2f} % of the window; the same 17 channels "
    f"concatenated with 256 frozen SAM encoder channels \u2192 MLP(128, 64), 273 inputs; 1024 px "
    f"tiles at stride 896, Hann-blended. The encoder is never fine-tuned and its prompt "
    f"encoder and mask decoder are never called. **(4) C, mean of A and B, pruned** \u2014 IoU "
    f"{iou(mask, lbl):.3f}, covering {100*mask.mean():.2f} % of the window; `predict()` returns "
    f"(A + B) / 2 at threshold {TH:.2f}, then speck pruning."),
  extended=[
   ("The window.",
    f"One 1100 px window of `{st['frame'][15:52]}`, chosen because its full-resolution "
    f"agreement with the operator ({st['frame_iou']:.3f}) sits just below the median of the "
    f"{st['corpus_n']} labelled frames scored here ({st['corpus_median_iou']:.3f}, quartiles "
    f"{st['corpus_q1']:.2f}\u2013{st['corpus_q3']:.2f}) \u2014 a typical frame, not a flattering one."),
   ("What separates, measured.",
    f"The jump is A \u2192 B, and the ensemble is a corpus-level result rather than a visible one. "
    f"Between the rungs on this window, A and B agree at IoU {iou(p17>TH, ph>TH):.3f} and B and C "
    f"at {iou(ph>TH, mask):.3f}. So A \u2192 B is a real change in what is marked, while B \u2192 C is not "
    f"visible on any single frame \u2014 the ensemble's advantage is 0.811 against 0.786 across 71 "
    f"frames, which no one window can show. A covers "
    f"{100*(p17>TH).mean():.0f} % of this window and B covers {100*(ph>TH).mean():.0f} %, against the "
    f"operator's {100*lbl.mean():.0f} %. Averaging beat both members in every cross-validation "
    f"fold, which is the property worth having, because a mean can be carried by one fold."),
   ("What the cross-validated numbers are.",
    "17-feature 0.726, SAM+17 hybrid 0.786, mean ensemble 0.811 \u2014 five-fold grouped by image "
    "over 71 frames, threshold 0.60, owner thin-core labels. Those are scored on a "
    "250,000-row sample of **hand-painted** pixels that is 49 % crack, not on whole frames, so "
    "they will not reproduce if a full frame is scored. The 71 frames are 4 specimens; "
    "holding out a whole specimen drops the same measurement to 0.51\u20130.67."),
   ("What must not be put on this axis.",
    "Zero-shot SAM scoring 0.23\u20130.36 is **not** comparable to the 0.811 above, on five counts: "
    "4 frames against 71; external masks from another tool against the owner's own; the full "
    "painted crack, median 65 px wide, against its 3.2 px dark core; every pixel of a frame "
    "at about 1 % crack prevalence against a 49 %-crack sample; and cold inference against "
    "grouped cross-validation. The prevalence difference alone moves IoU substantially, in "
    "the direction that flatters 0.811."),
  ])
json.dump(CAPTION, open(p.replace(".png", ".caption.json"), "w"), indent=1, ensure_ascii=False)
print("wrote caption json")
