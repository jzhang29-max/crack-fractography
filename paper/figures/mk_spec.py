"""Figure 5: on the only frame with negatives, the deployed model is visibly better.

Chosen crop: the window with the most candidate regions that the OPERATOR rejected, because
that is where a specificity difference can be seen at all. Measured, not eyeballed.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
H = _paths.FIG_CACHE
OUT = _paths.FIG_DIR
st = json.load(open(f"{H}/sem_specificity.json"))
img8 = np.load(f"{H}/spec_img8.npy"); gated = np.load(f"{H}/spec_gated.npy")
M4 = {r["model"]: np.load(f"{H}/spec_mask_{r['model'].split()[0]}.npy") for r in st["rows"]}
LR = M4["LogisticRegression"]; SV = M4["SVC (RBF)"]
# the crop that shows the most DISAGREEMENT about non-crack: kept by SVC, rejected by LR,
# and not crack according to the operator.
diff = SV & ~LR & ~gated
SIDE = 1100
best, h, w = None, *img8.shape
for yy in range(0, h - SIDE, 220):
    for xx in range(0, w - SIDE, 220):
        d = diff[yy:yy+SIDE, xx:xx+SIDE]
        n = ndi.label(d)[1]
        if best is None or n > best[0]: best = (n, yy, xx)
_, y0, x0 = best
sl = (slice(y0, y0+SIDE), slice(x0, x0+SIDE))
print(f"crop ({x0},{y0}) holds {best[0]} regions SVC keeps, LR rejects and the operator calls not-crack")

INK, MUT, RULE = (24, 24, 26), (98, 98, 104), (214, 214, 210)
RED, AMB, BLU, GRN = (196, 42, 42), (214, 150, 20), (38, 102, 190), (28, 118, 74)
def font(sz, b=False):
    for p in (("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if b
               else "/System/Library/Fonts/Supplemental/Arial.ttf"),):
        try: return ImageFont.truetype(p, sz)
        except Exception: pass
    return ImageFont.load_default()

# The figure no longer carries its own prose. Title, standfirst, per-panel paragraphs and
# the three footer columns are emitted as a caption JSON and typeset by mkpdf.py at 8.2 pt,
# because baked into a 1,840 px plate they rendered at 4.0 pt on the page. What stays in the
# image is a panel name and the one number the panel exists to show.
# Every surviving font must clear MIN_PX so that min_px * (page_width / W) >= 6 pt.
F_H, F_B = font(30, True), font(26)
MIN_PX = 26

order = sorted(st["rows"], key=lambda r: -r["spec"])
T, GAP, MG = 400, 20, 40
W = MG*2 + len(order)*T + (len(order)-1)*GAP
LEG = 46
img = Image.new("RGB", (W, T + 230), "white"); d = ImageDraw.Draw(img)

y0p = 16
sub = np.asarray(img8[sl], np.uint8); g = gated[sl]
for i, r in enumerate(order):
    nm = r["model"]; m = M4[nm][sl]
    x = MG + i*(T + GAP)
    a = np.dstack([sub]*3).astype(np.float32)
    for mask, col, al in ((m & g, RED, 0.70), (m & ~g, AMB, 0.70)):
        for c in range(3): a[..., c][mask] = (1-al)*a[..., c][mask] + al*col[c]
    img.paste(Image.fromarray(a.clip(0, 255).astype(np.uint8)).resize((T, T), Image.LANCZOS), (x, y0p))
    d.rectangle([x-1, y0p-1, x+T, y0p+T], outline=RULE, width=1)
    d.text((x, y0p+T+14), f"({i+1})  {nm}", font=F_H, fill=INK)
    d.text((x, y0p+T+52), f"specificity {r['spec']:.3f}", font=F_B,
           fill=GRN if r["spec"] > 0.3 else RED)
ly = y0p + T + 100
for lab, col in (("kept, operator agrees", RED), ("kept, operator marked not-crack", AMB)):
    d.rectangle([MG, ly+6, MG+22, ly+24], fill=col)
    d.text((MG+32, ly+2), lab, font=F_B, fill=(66, 66, 72))
    MG += 32 + int(d.textlength(lab, font=F_B)) + 60
img = img.crop((0, 0, W, ly + 40))
os.makedirs(OUT, exist_ok=True)
p = os.path.join(OUT, "5 - SEM, where the model differs.png")
img.save(p); print("wrote", p, img.size, "min_px", MIN_PX)

# ---------------------------------------------------------------- caption
# Built by LOOPING OVER `order`, the same sequence the panels are drawn in. An earlier
# draft of this caption hand-wrote st['rows'][1] as GradientBoosting and st['rows'][2] as
# RandomForest; the JSON holds them in the order LR, RF, GB, SVC, so panels 2 and 3 had
# each other's numbers. Deriving the key from the drawing order removes that possibility.
HELD = st["held_rows"]

# Computed from the masks this figure draws, not typed. Two hand-written versions of these
# ranges disagreed at the third decimal -- this caption said 0.966/0.9999 and 0.856/0.890
# while section 6.3 said 0.965/0.9999 and 0.860/0.894 -- and no artifact in the tree settled
# it. Deriving them here makes the caption and the section checkable against one number.
import itertools as _it
_pairs = [(a, b, float((M4[a] & M4[b]).sum() / max((M4[a] | M4[b]).sum(), 1)))
          for a, b in _it.combinations(M4, 2)]
_lin = lambda n: n.startswith("Logistic")
_NON = [v for a, b, v in _pairs if not _lin(a) and not _lin(b)]
_LIN = [v for a, b, v in _pairs if _lin(a) or _lin(b)]
NON_LO, NON_HI, LIN_LO, LIN_HI = min(_NON), max(_NON), min(_LIN), max(_LIN)
print(f"  mask agreement: non-linear {NON_LO:.4f}-{NON_HI:.4f}, "
      f"linear vs them {LIN_LO:.4f}-{LIN_HI:.4f}")
key = ("In every panel, red = kept and the operator agrees; amber = kept but the operator "
       "marked not-crack. ")
key += " ".join(
    f"**({i+1}) {r['model']}**{' (deployed)' if r['model'].startswith('Logistic') else ''}, "
    f"specificity {r['spec']:.3f}, AUC {r['auc']:.3f}; keeps {r['kept']:,} of "
    f"{r['candidates']:,} candidate regions, {r['fp']:,} false positives of "
    f"{r['tn']+r['fp']:,} not-crack regions; recall {r['recall']:.3f}, predicted area "
    f"{r['area_pct']:.3f} % of frame."
    for i, r in enumerate(order))

CAPTION = dict(
  min_px=MIN_PX,
  lead=("Where the deployed SEM model differs from the other three classifier families: it "
        "rejects non-crack, shown on the one frame of this corpus where that question is "
        "answerable."),
  panel_key=key,
  extended=[
   ("Why this is the one answerable frame, and which AUCs these are.",
    f"On a crack-rich frame the four classifier families are indistinguishable. This is the "
    f"one frame where the question is answerable: `{st['frame']}` carries {st['held_neg']:,} "
    f"of the corpus's 1,100 not-crack labels (92.4 %). Each family was fitted *without* it "
    f"and applied to it, so all four are out of sample. The AUCs above are refits of each "
    f"family on that holdout, computed here; the shipped bundle records its own "
    f"leave-one-image-out values (0.884, 0.555, 0.475, 0.921) from a different fit, and the "
    f"two must not be quoted interchangeably. Two region counts appear and they are not the "
    f"same set: specificity, AUC and the false-positive counts are computed over the "
    f"{HELD:,} adjudicated label rows this frame contributes, while \"regions kept\" is "
    f"over the {st['n_candidates']:,} candidates found by re-running the segmenter on the "
    f"frame. The gap is visible only on the one selective family — when a model accepts "
    f"essentially everything, any two region sets return nearly the same count."),
   ("Ranking and usability disagree.",
    f"The highest AUC is the unusable model, and this is not a superiority claim. SVC (RBF) "
    f"has the best ranking of the four (AUC {order[-1]['auc']:.3f}) and keeps every single "
    f"one of the {st['n_candidates']:,} candidate regions: specificity 0.000, "
    f"{order[-1]['fp']:,} false positives of {order[-1]['tn']+order[-1]['fp']:,}. Random "
    f"forest and gradient boosting behave the same way, at 0.001 and 0.003. Their masks "
    f"agree with each other at IoU {NON_LO:.4f} to {NON_HI:.4f}; the deployed logistic "
    f"regression differs from all three at {LIN_LO:.4f} to {LIN_HI:.4f}, and that difference "
    f"is entirely in what it rejects."),
   ("Why the shipped model is the linear one.",
    "AUC measures ranking. A pipeline applies a *threshold*, and a threshold is only "
    "meaningful if the probability scale is stable between retrains. Logistic regression is "
    "the only family here whose ranking is strong and whose scale is comparable across "
    "training sets, so a fixed operating point means the same thing from one retrain to the "
    "next. It is not the best-ranking model and this figure does not claim it is."),
   ("The limitation this figure exposes.",
    f"Fitting without this frame leaves only {st['train_neg_left']} negatives in the whole "
    f"training set. A classifier cannot learn to reject what it was never shown, so this is "
    f"a property of the labelling campaign, not of the model families. It is also why the "
    f"four cannot be ranked on this corpus: with 92.4 % of the negatives in one image, "
    f"specificity is estimable on exactly one frame and four incompatible orderings of the "
    f"same four models are derivable from the same data."),
  ])
json.dump(CAPTION, open(p.replace(".png", ".caption.json"), "w"), indent=1, ensure_ascii=False)
print("wrote caption json")
