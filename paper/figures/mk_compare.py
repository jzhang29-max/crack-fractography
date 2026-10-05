"""Paper figure: every method on one measurement axis, with its interval and its tiles.

The axis is the one thing that makes this publishable. All eleven arms are scored on the SAME
15 leak-gated 1024x1024 tiles from the SAME 9 SEM frames, under the SAME leave-one-FRAME-out
budget, with frame-clustered bootstrap 95% intervals. Nothing here is pooled across different
corpora, and no OIS/ODS oracle number appears beside a LOFO number.

Two metrics side by side on purpose: the ranking REVERSES between them, which is the result.
The dashed line is what a physically correct 3 px crack trace scores against these labels.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

B = os.path.join(_paths.require(_paths.SEM_REPO, "the sem-crack-detector checkout",
                                "SEM_REPO"), "crack_export", "analysis", "sam3")
OUT = _paths.FIG_DIR
mb = json.load(open(f"{B}/methods_bench.json"))
om = json.load(open(f"{B}/omnicrack_eval.json"))
se = json.load(open(f"{B}/serd_eval.json"))
tr = json.load(open(f"{B}/trained_lofo.json"))
ce = json.load(open(f"{B}/iou_ceiling.json"))
pw = json.load(open(f"{B}/power_analysis.json"))
TILES = mb["_tiles"]; FRAMES = len(set(mb["_frames"].values()))

def tiles_of(d):
    if "per_tile_LOFO" in d: return list(d["per_tile_LOFO"])
    if "per_tile" in d and isinstance(d["per_tile"], list): return list(d["per_tile"])
    return []

ARMS = []   # (label, kind, {metric: (value, lo, hi, [per-tile])})
def add(label, kind, iou, cld):
    ARMS.append((label, kind, {"IoU": iou, "clDice": cld}))
def frm(d):
    return (d["LOFO"], d.get("LOFO_ci", [None, None])[0], d.get("LOFO_ci", [None, None])[1], tiles_of(d))

add("OmniCrack30k nnU-Net", "published", frm(om["IoU"]), frm(om["clDice"]))
add("SAM 3 (zero-shot)", "published", frm(mb["SAM 3 union|IoU"]), frm(mb["SAM 3 union|clDice"]))
add("SERD", "published", frm(se["SERD raw|IoU"]), frm(se["SERD raw|clDice"]))
add("SERD + Sobel", "published", frm(se["SERD +Sobel|IoU"]), frm(se["SERD +Sobel|clDice"]))
for nm in ("global threshold", "Sauvola local", "Frangi ridge", "Sato ridge", "Meijering ridge"):
    add(nm, "classical", frm(mb[f"{nm}|IoU"]), frm(mb[f"{nm}|clDice"]))
for key, lab in (("logreg", "logistic regression"), ("hist-gbdt", "hist. gradient boosting")):
    d = tr[key]
    pt = d["per_tile"]
    add(lab, "trained",
        (d["median_IoU"], None, None, [v["IoU"] for v in pt.values()]),
        (d["median_clDice"], None, None, [v["clDice"] for v in pt.values()]))
ARMS.sort(key=lambda a: a[0].lower())   # ALPHABETICAL. The order is not a ranking.

INK, MUT, RULE = (24, 24, 26), (98, 98, 104), (214, 214, 210)
COL = {"published": (38, 102, 190), "classical": (122, 128, 140), "trained": (196, 42, 42)}
def font(sz, b=False):
    for p in (("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if b
               else "/System/Library/Fonts/Supplemental/Arial.ttf"),):
        try: return ImageFont.truetype(p, sz)
        except Exception: pass
    return ImageFont.load_default()
F_T, F_S, F_H, F_B, F_C = font(40, True), font(19), font(23, True), font(16), font(15)
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

# Title, standfirst and the three "What this figure says" columns are no longer drawn:
# baked into a 2,200 px plate they rendered at 3.3 pt on the page. They are emitted as a
# caption JSON and typeset by mkpdf.py at 8.2 pt. Everything that remains is the chart.
# Fonts are sized so that min_px * (487 pt / W) >= 6 pt.
F_H, F_B, F_C = font(36, True), font(30), font(28)
MIN_PX = 28

W, M = 2200, 40
LBL = 430                      # row-label gutter; "hist. gradient boosting" at 28 px
VALW = 96
PANW = (W - 2*M - LBL - 80 - 2*VALW)//2
ROWH, TOP = 58, 96
H = TOP + len(ARMS)*ROWH + 300
img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)
CEIL = ce["ceiling_IoU"]

for pi, metric in enumerate(("IoU", "clDice")):
    x0 = M + LBL + pi*(PANW + VALW + 80)
    hi = max(max(mm[metric][0] for _, _, mm in ARMS),
             max([p for _, _, mm in ARMS for p in mm[metric][3]] or [0]))
    xmax = 0.1*np.ceil(hi/0.1 + 0.3)
    d.text((x0, TOP - 62), metric, font=F_H, fill=INK)
    d.text((x0 + d.textlength(metric, font=F_H) + 16, TOP - 54),
           "median over 15 tiles", font=F_C, fill=MUT)
    sx = lambda v: x0 + (v/xmax)*PANW
    g = 0.0
    while g <= xmax + 1e-9:
        d.line([sx(g), TOP - 18, sx(g), TOP + len(ARMS)*ROWH], fill=(238, 238, 234), width=1)
        # every 0.2, not every 0.1: at 28 px a "0.0" label is 42 px wide against a 0.1 gap
        # of 72 px, and adjacent labels touched.
        if abs(round(g*10) % 2) == 0:
            d.text((sx(g) - 21, TOP + len(ARMS)*ROWH + 10), f"{g:.1f}", font=F_C, fill=MUT)
        g += 0.1
    d.line([x0, TOP + len(ARMS)*ROWH, x0 + PANW, TOP + len(ARMS)*ROWH], fill=RULE, width=1)
    if metric == "IoU":
        cx = sx(CEIL)
        for yy in range(TOP - 18, TOP + len(ARMS)*ROWH, 11):
            d.line([cx, yy, cx, yy + 6], fill=(186, 120, 10), width=3)
        d.text((cx - 8, TOP - 92), f"{CEIL:.3f}  a correct 3 px trace", font=F_C, fill=(186, 120, 10))
    for i, (lab, kind, mm) in enumerate(ARMS):
        v, lo, hiv, pts = mm[metric]
        y = TOP + i*ROWH
        if pi == 0:
            d.text((M + 26, y + 14), lab, font=F_B, fill=INK)
            d.rectangle([M, y + 18, M + 14, y + 36], fill=COL[kind])
        d.rectangle([x0, y + 14, sx(v), y + 40], fill=COL[kind])
        if lo is not None:
            d.line([sx(lo), y + 27, sx(hiv), y + 27], fill=(60, 60, 66), width=3)
            for e in (lo, hiv):
                d.line([sx(e), y + 18, sx(e), y + 36], fill=(60, 60, 66), width=3)
        for pp in pts:
            d.ellipse([sx(pp) - 3.5, y + 23, sx(pp) + 3.5, y + 31], fill=(255, 255, 255),
                      outline=(70, 70, 76), width=2)
        d.text((x0 + PANW + 16, y + 14), f"{v:.3f}", font=F_C, fill=INK)

y = TOP + len(ARMS)*ROWH + 64
kx = M
for kind, lab in (("published", "published method"), ("classical", "classical filter"),
                  ("trained", "trained on this corpus")):
    d.rectangle([kx, y + 4, kx + 26, y + 26], fill=COL[kind])
    d.text((kx + 36, y), lab, font=F_B, fill=MUT)
    kx += 36 + d.textlength(lab, font=F_B) + 70
img = img.crop((0, 0, W, y + 60))
os.makedirs(OUT, exist_ok=True)
p = os.path.join(OUT, "3 - method comparison, identical data.png")
img.save(p); print("wrote", p, img.size, "min_px", MIN_PX)

# ---------------------------------------------------------------- caption
_P1 = pw["OmniCrack30k vs global threshold"]
_P2 = pw["Meijering ridge vs SAM 3"]
CAPTION = dict(
  min_px=MIN_PX,
  lead=("Eleven crack-detection methods on identical data, scored on two metrics under one "
        "leave-one-frame-out budget; the bar order is alphabetical and is not a ranking."),
  panel_key=(
    f"**IoU** (left) and **clDice** (right), both pixel agreement, median over 15 tiles. The "
    f"dashed vertical rule in the IoU panel at {CEIL:.3f} is where a geometrically correct "
    f"3 px trace falls; the same trace scores clDice 0.9997, so no ceiling rule is drawn "
    f"there. The eleven method labels sit in a shared gutter and serve both panels; the "
    f"order is **alphabetical and is not a ranking**. Bars are the median per-tile score "
    f"with each arm's own value printed at the right edge of its panel, whiskers the "
    f"frame-clustered bootstrap 95 % interval, and dots the 15 tiles. Colour keys the method "
    f"family, as shown beneath the panels; the two arms trained on this corpus carry no "
    f"interval, so the overlap statement below is over the other nine."),
  extended=[
   ("What this figure says.",
    "All eleven arms \u2014 four published, five classical, two trained on this corpus \u2014 are "
    "scored on the same 15 leak-gated 1024 \u00d7 1024 tiles from the same 9 SEM frames, under one "
    "leave-one-**frame**-out budget so that train and test never share an image. Nothing is "
    "pooled across corpora, and no ODS/OIS oracle number appears beside a "
    "leave-one-frame-out one."),
   ("No pair of methods differs.",
    f"Every interval overlaps every other, and a paired Wilcoxon over the 15 tiles with Holm "
    f"and Benjamini\u2013Hochberg correction separates 0 of the 55 pairs on IoU and 0 of 55 on "
    f"clDice. Paired power at this n is the reason: OmniCrack30k against the one-line global "
    f"threshold has a median delta of {_P1['median_delta']:.3f} and "
    f"{100*_P1['power']['9']:.0f} % power at nine **frames** \u2014 the power curve resamples the 9 "
    f"source frames, not the tiles \u2014 and Meijering against SAM 3, "
    f"{100*_P2['power']['9']:.0f} %. Eighty percent power would need roughly 40 to 150 frames, "
    f"not 9. Nine of the 165 IoU cells and 15 of 165 clDice cells read exactly 0.0000, 7 and "
    f"13 of them on the two tiles of one frame; six of the eleven arms have no IoU zero at all."),
   ("The metric decides the winner.",
    "By IoU the best arm is a one-line grey-level cut (0.258); by clDice it is the Meijering "
    "ridge filter (0.338), and that same one-line cut falls to **ninth of eleven** (0.183). "
    "\"Fifth\" is its rank in a seven-arm subset this figure does not draw. A published "
    "30,000-image nnU-Net (OmniCrack30k; Benz & Rodehorst, CVPRW 2024, "
    "doi:10.1109/CVPRW63382.2024.00392) is **second of eleven on both metrics** \u2014 behind the "
    "one-line threshold on IoU and behind Meijering on clDice. A single-metric bar chart of "
    "this corpus is a chart of the metric choice."),
   ("IoU is above its own ceiling.",
    f"A geometrically **correct** 3 px trace down the label's own centreline scores IoU "
    f"{CEIL:.4f} against these hand-painted masks. The median annotator stroke over the 15 "
    f"tiles is 16.0 px as the median of the per-tile medians and 14.6 px pooled over all "
    f"label-skeleton pixels; an earlier caption read 15.6 px, which is the whole-frame figure \u2014 the median of the nine per-frame medians \u2014 and not a per-tile measurement. The "
    f"IoU leader sits {0.2579/CEIL:.2f}\u00d7 above that ceiling, so on this corpus a higher pixel "
    f"IoU measures imitation of the brush rather than accuracy of the boundary. The same "
    f"trace scores clDice 0.9997, which is why both metrics are shown."),
  ])
json.dump(CAPTION, open(p.replace(".png", ".caption.json"), "w"), indent=1, ensure_ascii=False)
print("wrote caption json")
