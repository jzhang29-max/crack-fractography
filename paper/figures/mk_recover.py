"""Figure 6 -- what deleting the SEM region classifier recovers, and what it costs.

Replaces `mk_spec.py`, which drew what the region classifier REJECTS. v1.49.2 sets
USE_REGION_CLASSIFIER = False, so nothing is rejected and that figure had no subject.

THIS SCRIPT DRAWS; IT DOES NOT COMPUTE. Every number on the plate and in the caption is
read out of `sem_deadzone.json`, which `sem_deadzone.py` wrote and which is committed.
The only arithmetic here is percent-of-a-bar for the cost inset, and the bar's own label
is the value from the record.

Three rows, one per dead-zone specimen, four columns:
    the hand label | arm A, v1.47 | arm B, the classifier ablation | arm C, v1.49.2
Arm C is the CANDIDATE STAGE of the shipped pipeline, not the mask the application
emits -- the app adds Pass 2 on top of it and keeps a superset. The column header and the
caption both say so; nothing here may read as "what the app emits".

Greyscale check matters here: the three overlay colours are chosen for separated
LUMINANCE (true positive 85, false positive 155, label outline 40 on a mid-grey
micrograph), not just separated hue, so the plate survives a greyscale print.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

H, OUT = _paths.FIG_CACHE, _paths.FIG_DIR
R = json.load(open(os.path.join(H, "sem_deadzone.json")))
L = lambda n: np.load(os.path.join(H, n + ".npy"))

INK, MUT, RULE = (24, 24, 26), (98, 98, 104), (206, 206, 202)
TP = (196, 42, 42)        # kept, and the operator painted it   -- luminance ~85
FP = (214, 150, 20)       # kept, not painted                   -- luminance ~155
LAB = (26, 30, 38)        # the hand label's outline            -- luminance ~30
GRN = (28, 118, 74)
PALE = (247, 247, 244)


def font(sz, b=False):
    for p in (("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if b
               else "/System/Library/Fonts/Supplemental/Arial.ttf"),
              "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()


# Every surviving font must clear MIN_PX, which mkpdf scales by (column_pt / plate_width)
# and refuses below 6 pt. At W = 1382 px in a 487 pt column the factor is 0.353, so
# MIN_PX = 26 lands at 9.2 pt.
F_COL, F_SUB, F_ROW, F_NUM, F_LEG, F_FOOT = (font(30, True), font(26), font(28, True),
                                             font(34, True), font(26), font(26))
MIN_PX = 26

P, GAP, MG = 312, 18, 40
NCOL = 4
W = MG * 2 + NCOL * P + (NCOL - 1) * GAP          # 1382

_probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))


def wrap(t, f, width):
    out, line = [], ""
    for w_ in t.split():
        s = (line + " " + w_).strip()
        if _probe.textlength(s, font=f) <= width:
            line = s
        else:
            if line:
                out.append(line)
            line = w_
    if line:
        out.append(line)
    return out


def panel(img8, pred=None, gt=None):
    """One 512 px tile as RGB. `pred` filled by agreement, `gt` always outlined.

    The outline is drawn OUTSIDE the label (dilate ^ label), not inside it. Eroding
    inward made the ring cover the whole of any label narrower than 4 px, which is most
    of them: column A then read as a solid dark detection instead of an empty one, and
    in columns B and C the ring painted over the red fill it was supposed to bracket.
    """
    a = np.dstack([np.asarray(img8, np.uint8)] * 3).astype(np.float32)
    if pred is not None:
        for m, col in ((pred & gt, TP), (pred & ~gt, FP)):
            for c in range(3):
                a[..., c][m] = 0.28 * a[..., c][m] + 0.72 * col[c]
    else:
        for c in range(3):
            a[..., c][gt] = 0.40 * a[..., c][gt] + 0.60 * GRN[c]
    if gt is not None:
        a[ndi.binary_dilation(gt, iterations=2) & ~gt] = LAB
    return Image.fromarray(a.clip(0, 255).astype(np.uint8)).resize((P, P), Image.LANCZOS)


# ---------------------------------------------------------------- geometry
COLS = [("The hand label", "what the operator painted", None),
        ("A  v1.47", "one radius, classifier ON", "v147"),
        ("B  classifier OFF", "same cut, all regions kept", "ablation"),
        ("C  v1.49.2 candidates", "seven radii, classifier OFF", "v1492")]
ROWS = R["dead_zone"]

# Heights are MEASURED from the wrapped text, never assumed. The first draft fixed the
# header at 86 px; "same cut, all regions kept" wraps to two lines at 312 px and the
# second line landed on top of the first row's specimen name.
SUBL = max(len(wrap(h2, F_SUB, P)) for _, h2, _ in COLS)
HDR = 38 + SUBL * 30 + 14
RLAB = 40                     # specimen name above each row
RNUM = 52                     # recall under each row
ROWH = RLAB + P + RNUM + 16

img = Image.new("RGB", (W, 24 + HDR + len(ROWS) * ROWH + 900), "white")
d = ImageDraw.Draw(img)

y = 24
for i, (h1, h2, _) in enumerate(COLS):
    x = MG + i * (P + GAP)
    d.text((x, y), h1, font=F_COL, fill=INK)
    for j, ln in enumerate(wrap(h2, F_SUB, P)):
        d.text((x, y + 38 + j * 30), ln, font=F_SUB, fill=MUT)
y += HDR

for row in ROWS:
    s = row["specimen"]
    g = L(f"dz_{s}_gt")
    im8 = L(f"dz_{s}_img8")
    d.text((MG, y), f"{s}   ({row['frame'].split('__')[0]}, 512 px tile)",
           font=F_ROW, fill=INK)
    for i, (_, _, arm) in enumerate(COLS):
        x = MG + i * (P + GAP)
        pr = L(f"dz_{s}_{arm}") if arm else None
        img.paste(panel(im8, pr, g), (x, y + RLAB))
        d.rectangle([x - 1, y + RLAB - 1, x + P, y + RLAB + P], outline=RULE, width=1)
        ty = y + RLAB + P + 10
        if arm is None:
            d.text((x, ty), f"{row['gt_px']:,} px painted", font=F_LEG, fill=MUT)
        else:
            r = row[arm]["recall"]
            d.text((x, ty), f"recall {r:.4f}", font=F_NUM,
                   fill=GRN if r > 0.05 else TP)
    y += ROWH

# ---------------------------------------------------------------- legend
d.text((MG, y), "In the three model columns:", font=F_LEG, fill=MUT)
lx = MG + int(d.textlength("In the three model columns:", font=F_LEG)) + 24
for col, lab in ((TP, "kept, and painted"), (FP, "kept, not painted"),
                 (LAB, "outline = the hand label")):
    d.rectangle([lx, y + 4, lx + 24, y + 26], fill=col)
    d.text((lx + 32, y), lab, font=F_LEG, fill=MUT)
    lx += 32 + int(d.textlength(lab, font=F_LEG)) + 42
y += 46

# ---------------------------------------------------------------- the anchor, and the cost
# Laid out as two STACKED blocks, not two side-by-side columns. Side by side, the paired
# table's third field ran under the cost block's heading: a 631 px half-column cannot hold
# "median dIoU +0.2296   11 of 13 better   Wilcoxon p = 0.0024" at 26 px. Every x below is
# measured off the widest string in its own column, and the canvas is cropped to the last
# baseline actually drawn.
d.line([MG, y, W - MG, y], fill=RULE, width=2)
y += 20

pa, pc = R["paired"]["ablation"], R["paired"]["v1492"]
d.text((MG, y), "All 13 specimens, paired against v1.47  (per-specimen IoU, "
                "two-sided Wilcoxon signed-rank)", font=F_COL, fill=INK)
y += 42
PCOL = [0, max(d.textlength(t, font=F_LEG) for t in
               ("B  classifier OFF", "C  v1.49.2 candidates")) + 50]
# The width probes measure the strings ACTUALLY DRAWN below, not copies of them. A copied
# literal goes stale the moment the measurement changes and silently mis-sizes the column.
_PS = [(f"median ΔIoU {q['median_delta_iou']:+.4f}",
        f"{q['n_better']} of {q['n_specimens']} better") for q in (pa, pc)]
PCOL += [PCOL[1] + max(d.textlength(t[0], font=F_LEG) for t in _PS) + 50]
PCOL += [PCOL[2] + max(d.textlength(t[1], font=F_LEG) for t in _PS) + 50]
for tag, p in (("B  classifier OFF", pa), ("C  v1.49.2 candidates", pc)):
    for k, s in enumerate((tag,
                           f"median ΔIoU {p['median_delta_iou']:+.4f}",
                           f"{p['n_better']} of {p['n_specimens']} better",
                           f"p = {p['wilcoxon_p']:.4f}")):
        d.text((MG + PCOL[k], y), s, font=F_LEG, fill=INK if k == 0 else MUT)
    y += 36
y += 24

# The cost. Precision falls, and a plate that showed only the recovery would be a sales
# pitch. Bar lengths are the recorded value; the number beside each bar is that value.
C25 = R["pooled_25_no_flood"]
d.text((MG, y), "What it costs — the same 13 specimens, pooled over the 25 tiles "
                "with the flooded tile dropped", font=F_COL, fill=INK)
y += 42
ARMLAB = {"v147": "A  v1.47", "ablation": "B  classifier OFF",
          "v1492": "C  v1.49.2 candidates"}
LABW = max(d.textlength(s, font=F_LEG) for s in ARMLAB.values()) + 40
BW = int((W - 2 * MG - LABW - 3 * 150) / 3)
MET = (("precision", "precision", TP, "falls"), ("recall", "recall", GRN, "rises"),
       ("iou", "IoU", GRN, "rises"))
for j, (_k, metric, col, verb) in enumerate(MET):
    x = MG + LABW + j * (BW + 150)
    d.text((x, y), f"{metric} — {verb}", font=F_LEG, fill=MUT)
for i, arm in enumerate(("v147", "ablation", "v1492")):
    yy = y + 38 + i * 34
    d.text((MG, yy - 3), ARMLAB[arm], font=F_LEG, fill=INK)
    for j, (_k, metric, col, _) in enumerate(MET):
        v = C25[arm][_k]
        x = MG + LABW + j * (BW + 150)
        d.rectangle([x, yy, x + max(2, int(BW * v)), yy + 22], fill=col)
        d.text((x + BW + 14, yy - 4), f"{v:.4f}", font=F_LEG, fill=INK)
y += 38 + 3 * 34

img = img.crop((0, 0, W, y + 30))
os.makedirs(OUT, exist_ok=True)
p = os.path.join(OUT, "6 - SEM, what deleting the region classifier recovers.png")
img.save(p)
print("wrote", p, img.size, "min_px", MIN_PX)

# ---------------------------------------------------------------- caption
# Built by looping over the same `ROWS` and `COLS` the panels were drawn from, so a row's
# numbers cannot be attached to another row's panel. mk_spec.py once hand-indexed its rows
# and gave panels 2 and 3 each other's values.
dz = {r["specimen"]: r for r in ROWS}
P26 = R["pooled_26"]

key = ("Rows are the three specimens; the dark outline in every panel is the operator's "
       "hand label, so what each model column shows is how much of that outline it fills. "
       "**Red** = kept and painted, **amber** = kept and not painted. Columns: "
       "**(A) v1.47** — the published pipeline, darkness cut at one flattening radius "
       "(σ = 40) and the bundled logistic region classifier at its threshold "
       f"{R['classifier_threshold']:.4f}. **(B) classifier OFF** — arm A's own candidate "
       "stage with the "
       "classifier bypassed and every region kept; exactly one variable differs from A, "
       "so A→B is the classifier's effect and nothing else's. **(C) v1.49.2** — "
       "what the application runs: the darkness cut unioned over seven flattening radii "
       "(5, 10, 20, 40, 80, 160, 320) at mad_k 5.0, every candidate region kept. "
       + " ".join(
    f"**{s}** ({dz[s]['frame'].split('__')[0]}, {dz[s]['gt_px']:,} px painted): recall "
    f"{dz[s]['v147']['recall']:.4f} → {dz[s]['ablation']['recall']:.4f} → "
    f"{dz[s]['v1492']['recall']:.4f}." for s in [r["specimen"] for r in ROWS]))

CAPTION = dict(
  min_px=MIN_PX,
  lead=("The three specimens that scored recall 0.0000 at every candidate setting ever "
        "tried were not invisible to the detector: the candidate stage had proposed their "
        "cracks all along and the region classifier was rejecting all of them. Switching "
        "it off — which is what the application now does — recovers them, at a "
        "cost in precision shown at lower right."),
  panel_key=key,
  extended=[
   ("What arm C is, and what it is not.",
    "Column C is the v1.49.2 CANDIDATE STAGE, not the mask the application emits. "
    "`detect_one.py` runs `unified_pipeline.run_unified_pipeline`, which also runs Pass 2 "
    "(concavity, bridge-corridor, interior-fill) and, with the classifier off, keeps every "
    "Pass-2 row of its dataframe as well. Pass 2 resolves its input frame from "
    "ORIGINAL_DIR and operates on a whole micrograph, so it is not defined on a 512 px "
    "crop cut out of one and is absent from every panel here. Pass 2 is additive by "
    "construction: it claims only pixels no Pass-1 candidate owns "
    "(`claimable = mask_bool & (labeled == 0) & ~protected` in `unified_pipeline.py`) and "
    "appends its rows, so with the classifier off the emitted mask is a strict superset "
    "of column C and these panels understate production rather than flattering it. The "
    "size of that gap is recorded, not re-measured here: `docs/CLAIMS.md` D2 puts it at "
    "+17,972 px, losing none — but over 20 tiles, not 26, because the pipeline's own "
    "`find_field_of_view` crops the other six, and per-tile IoU moves between −0.191 "
    "and +0.073, so Pass 2 is not uniformly favourable to the score."),
   ("How the three crops were chosen: they were not.",
    f"{R['crop_choice']} The generator asserts both facts and raises if either stops "
    f"holding: that each dead-zone specimen contributes exactly one tile, and that its "
    f"arm-A recall is exactly 0.0000."),
   ("The paired result over all 13 specimens.",
    f"Scored through `analysis/research/tilebench.py`, the one scorer in this project: "
    f"{R['scorer']['n_tiles']} hand-labelled 512 px tiles over "
    f"{R['scorer']['n_specimens']} specimens, {R['scorer']['excluded'][0]} excluded "
    f"(87 % of its paint is round, i.e. porosity), zero-pixel tolerance, pooled within "
    f"each specimen. Against v1.47, arm B moves the median per-specimen IoU by "
    f"{pa['median_delta_iou']:+.4f} ({pa['n_better']} of {pa['n_specimens']} better, "
    f"{pa['n_worse']} worse, two-sided Wilcoxon p = {pa['wilcoxon_p']:.4f}) and arm C by "
    f"{pc['median_delta_iou']:+.4f} ({pc['n_better']} of {pc['n_specimens']}, "
    f"p = {pc['wilcoxon_p']:.4f}). Neither arm has a parameter that was chosen on these "
    f"tiles, so leave-one-specimen-out and fitted selection return the same number and "
    f"the overfit gap is exactly zero — there is nothing here to have tuned."),
   ("The cost, which is real.",
    f"Deleting the classifier loses precision on ordinary fields. Pooled over the 25 tiles "
    f"with the flooded tile dropped — `{C25['flood_tile'].split('__')[0]}`, an "
    f"off-specimen void that owns most of the false positives at every setting and would "
    f"otherwise make this number describe that one object — precision falls "
    f"{C25['v147']['precision']:.4f} → {C25['ablation']['precision']:.4f} → "
    f"{C25['v1492']['precision']:.4f} while recall rises "
    f"{C25['v147']['recall']:.4f} → {C25['ablation']['recall']:.4f} → "
    f"{C25['v1492']['recall']:.4f}. IoU rises throughout, "
    f"{C25['v147']['iou']:.4f} → {C25['ablation']['iou']:.4f} → "
    f"{C25['v1492']['iou']:.4f}, which is why the trade is taken; but the precision "
    f"column is the honest reason not to read this figure as free."),
   ("Which arm the project's published numbers belong to.",
    f"`analysis/detector_overrides.py` publishes “+0.1753 median IoU, 11 of 13, "
    f"Wilcoxon p = 0.0061” and the recoveries “0.3792 / 0.3537 / 0.6827” in "
    f"the paragraph that introduces the shipped change, which reads as though they "
    f"describe production. They do not. All four reproduce to four decimals as arm B, the "
    f"single-radius ablation, and the generator asserts them against arm B so the "
    f"attribution cannot rot. Production is arm C and is larger: "
    f"{pc['median_delta_iou']:+.4f} and {dz['MAR_Amb_AS']['v1492']['recall']:.4f} / "
    f"{dz['MAR_Amb_Cast']['v1492']['recall']:.4f} / "
    f"{dz['MAR_Amb_HIP']['v1492']['recall']:.4f}. Pooled over all 26 tiles arm C scores "
    f"precision {P26['v1492']['precision']:.4f}, recall {P26['v1492']['recall']:.4f}, "
    f"IoU {P26['v1492']['iou']:.4f}; the committed v1.49.1 row in `tilebench.py` records "
    f"{R['v1491_committed_pooled']['value']['precision']:.4f} / "
    f"{R['v1491_committed_pooled']['value']['recall']:.4f} / "
    f"{R['v1491_committed_pooled']['value']['iou']:.4f} for the same settings, which this "
    f"re-measurement matches on IoU but not on precision and recall. Every number in this "
    f"figure is the re-measurement, not the committed row."),
  ])
json.dump(CAPTION, open(p.replace(".png", ".caption.json"), "w"), indent=1,
          ensure_ascii=False)
print("wrote caption json")
