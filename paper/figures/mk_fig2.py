"""Figure 2 -- what the two models are MADE of, as the application runs them (v1.49.2).

Every dimension, layer shape, parameter count, coefficient and threshold here is READ OUT
of the shipped artefacts and of a production run, through two committed JSON records:
`sem_models.json` (sem_models.py, the two SEM bundles) and `sem_production.json`
(sem_production.py, the pipeline driven exactly as analysis/detect_one.py drives it). The
TXM side reads `txm_stats.json` and models/f17_v5_20260824.joblib,
models/hybrid_v5_20260824.joblib and facebook/sam-vit-huge's own config.

THE SEM COLUMN USED TO DRAW THE ARCHIVED v1.47 CLASSIFIER AS IF IT DECIDED SOMETHING.
It is disabled: v1.49.2 sets USE_REGION_CLASSIFIER = False and detect_one.py keeps every
row of df. Two treatments were considered and BOTH were wrong as stated:

  (a) keep the panel, labelled "the archived, now-disabled model". True but incomplete --
      it implies the model has no effect, and it has one.
  (b) replace it with "production contains no learned model at all on the SEM side".
      Striking, and FALSE. The check is in sem_production.json: a joblib.load trace over a
      real production run returns BOTH `models/crack_classifier.joblib` and
      `interior_active_learning/models/unified_model.joblib`. Reading
      USE_REGION_CLASSIFIER and inferring (b) is exactly the assumption the task warned
      against, and the code says otherwise in two places:
        * score_pass1_candidates loads the 8-feature bundle on every run and writes
          IsCrack; run_unified_pipeline then builds Pass 2's seed crack_mask from THAT
          column. The switched-off model still chooses which Pass-2 candidates exist and
          what MeanDistToCrack and FracBoundaryTouchingCrack are measured against.
        * Pass 2 scores every candidate with the 11-feature unified model and drops the
          ones it rejects -- 544 generated, 431 accepted on the example frame. That model
          gates every pixel Pass 2 contributes, and Pass 2 is in what the app emits.

So this column draws the THIRD, true thing: the candidate stage has zero fitted parameters
(the honest part of (b), correctly scoped), pass 1's nine coefficients are computed and
discarded at emission while still steering pass 2 (the part (a) missed), and pass 2's
twelve are the only learned weights in the SEM arm that change a pixel of the output. The
three boxes are three different colours for that reason.

The eight pass-1 coefficients were EIGHT LITERALS in this file, under a docstring saying
they had been read out of the artefact. They had been, once, by hand. A refit would have
left the figure drawing last year's weights with nothing able to notice. They come from
sem_models.json now, in the order the bar chart draws them.

The TXM arm is unchanged.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = _paths.FIG_CACHE
TXM = json.load(open(f"{HERE}/txm_stats.json"))
# The SEM column's two sources, and NOTHING is computed from them here. sem_models.json is
# the readout of the two bundles (sem_models.py); sem_production.json is what the pipeline
# did when it was driven exactly as analysis/detect_one.py drives it (sem_production.py).
# sem_stats.json, the archived single-radius record, is deliberately NOT read: this column
# no longer draws that pipeline.
MOD = json.load(open(f"{HERE}/sem_models.json"))
M1, M2, SG = MOD["pass1"], MOD["pass2"], MOD["stages"]
PR = json.load(open(f"{HERE}/sem_production.json"))
assert PR["use_region_classifier"] is False, "this figure draws the classifier-off path"
# The claim "no learned model on the SEM side" is checkable and it is FALSE; the trace in
# sem_production.json is the check. Both bundles load on every production run, so if this
# ever stops being true the figure must change, loudly.
assert set(PR["learned_artefacts_loaded"]) == {M1["path"], M2["path"]}, \
    f"the SEM path's learned artefacts moved: {PR['learned_artefacts_loaded']}"

INK, MUT, RULE = (24, 24, 26), (98, 98, 104), (210, 210, 206)
RED, BLU, AMB, GRN, VIO, SLT = (196, 42, 42), (38, 102, 190), (186, 120, 10), (28, 118, 74), (112, 62, 172), (96, 104, 118)
# one colour per KIND of stage, used in both columns and in the key
K = {"in":   ((242, 242, 238), SLT,  "input"),
     "det":  ((238, 244, 250), BLU,  "deterministic image processing"),
     "fit":  ((252, 238, 238), RED,  "fitted to this lab's labels"),
     "froz": ((244, 238, 252), VIO,  "frozen, pre-trained, 637 M params"),
     "hum":  ((252, 246, 232), AMB,  "operator"),
     # Deliberately the DARKEST fill of the seven. Its first value was (240,240,236),
     # one grey step from "input" at (242,242,238) -- indistinguishable on a greyscale
     # print, which is where a figure about what is and is not switched on must still
     # work. Its left spine is drawn broken as well, so the state survives even a
     # black-and-white photocopy.
     "off":  ((214, 214, 210), (108, 108, 114), "fitted, loaded, verdict discarded"),
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

# 2200 was not enough once the SEM column grew a box: the crop is min(height, last+30),
# so an overflow is SILENT -- the plate just ends mid-diagram. Assert instead.
CANVAS = 3200
img = Image.new("RGB", (W, CANVAS), "white")
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
    # THE HEAD ITSELF WAS NEVER MEASURED. Only head-plus-rhs was, so a long head alone ran
    # straight out of the box and over the column beside it, and the script still exited 0:
    # five heads in the rewritten SEM column did exactly that, printing on top of the
    # coefficient panel. PIL clips nothing and reports nothing, so this has to be an assert.
    assert hw <= w - 32, (f"box head is {hw:.0f} px wide in a {w - 32:.0f} px box "
                          f"and will overprint the next column: {head!r}")
    # at MIN_PX a long head and a long rhs no longer share a line; measure rather than hope
    stacked = bool(rhs) and (hw + 24 + rw > w - 32)
    h = 14 + 36 + (30 if stacked else 0) + 10
    d.rounded_rectangle([x, y, x+w, y+h], radius=7, fill=fill, outline=edge, width=2)
    if kind == "off":
        seg = 9
        for yy0 in range(y+2, y+h-2, seg*2):
            d.rectangle([x, yy0, x+6, min(yy0+seg, y+h-2)], fill=edge)
    else:
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
for kind in ("in", "det", "fit", "off", "froz", "hum", "meas"):
    fill, edge, lab = K[kind]
    need = 46 + d.textlength(lab, font=F_SM) + 34
    if kx > M and kx + need > W - M:
        kx, ky = M, ky + 38
    d.rounded_rectangle([kx, ky, kx+30, ky+28], radius=4, fill=fill, outline=edge, width=2)
    if kind == "off":
        for yy0 in range(ky+2, ky+28, 18):
            d.rectangle([kx, yy0, kx+6, min(yy0+9, ky+26)], fill=edge)
    d.text((kx+40, ky+2), lab, font=F_SM, fill=MUT)
    kx += need
KEYBOT = ky + 48
d.line([M, KEYBOT, W-M, KEYBOT], fill=INK, width=2)

# ------------------------------------------------------------------ SEM column
# THIS COLUMN DRAWS PRODUCTION (v1.49.2), and the two learned boxes are drawn differently
# from each other because they are in different states. See the module docstring: one is
# loaded, scored and then ignored at emission; the other gates every pixel pass 2 adds.
X0 = M
LAD = " · ".join(str(s) for s in PR["scale_ladder"])
d.rectangle([X0, KEYBOT+20, X0+6, KEYBOT+52], fill=RED)
d.text((X0+18, KEYBOT+18), "SEM arm — v1.49.2, as the application runs it", font=F_H, fill=INK)
# Wrapped and measured. The unwrapped single draw this replaced ran off the right edge of
# the plate and was cropped away, silently.
_sf = ("Candidate REGIONS are scored, not pixels. Nothing is fitted up to the candidate "
       f"stage; pass 1's {M1['n_params']} coefficients are computed and then discarded at "
       f"emission; pass 2's {M2['n_params']} decide.")
_sfy = KEYBOT + 56
for _ln in wrap(_sf, F_HN, CW - 18):
    d.text((X0+18, _sfy), _ln, font=F_HN, fill=MUT); _sfy += 32
SEMTOP = _sfy + 12

bx, bw = X0, 700
cx = bx + bw//2
y = SEMTOP
y = box(bx, y, bw, "in", "Back-scattered SEM frame",
        [f"16-bit TIFF, {PR['raw_full'][0]}×{PR['raw_full'][1]} px, {PR['nm_per_px']:.1f} nm/px. 142 frames are 86 physical",
         "fields, many imaged through two detectors — the invariant tests/test_specimen_stats.py exists to hold."],
        rhs="25 MP")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "det", "load_as_uint8  →  find_field_of_view",
        ["Rescale on the frame's own 1–99.5 percentile, then crop to the usable sample area:",
         f"on this frame {PR['raw_full'][1]} rows become {PR['full'][1]}, and every count below is on that extent.",
         "A databar, if present, is detected by two independent signals (row mean+sd collapse,",
         "and a full-width step) and cropped."], rhs="no parameters fitted")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "det", "flatten_background  ·  SEVEN radii",
        [f"σ = {LAD} px. Subtract a Gaussian copy, stretch on 0.5–99.5.",
         "The archived pipeline ran this at",
         "σ = 40 alone; flattening is a high-pass filter, so ONE radius erases every feature",
         "wider than itself and a crack is only reliably dark at the scales near its own width.",
         f"Above σ = {PR['decimate_above_sigma']} the background is estimated on a decimated copy, which changes",
         "cost and not the result."], rhs="radii enumerated, not learned")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "det", f"compute_vesselness  ·  Frangi, σ = {SG['frangi_label']}",
        [f"sigmas=range({SG['frangi_sigmas'][0]}, {SG['frangi_sigmas'][-1]+1}) — FIVE scales, not six; the figure said σ = 1–6 for three",
         "revisions because the range's exclusive stop was read as inclusive.",
         "Hessian eigenvalue ratio, black_ridges=True. Separates thin curves from round blobs,",
         f"which darkness alone cannot: {PR['ves_ratio']:.1f}:1 crack-to-matrix on the window in figure 1.",
         "It is still computed, and it is still a feature of both models below."],
        rhs="a feature of both models")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "det", "segment_dark_regions  ·  UNIONED",
        [f"At every rung: min(Otsu, median − {PR['mad_k']:.0f}·MAD·1.4826). OR-ed across the seven, then OR-ed",
         f"with an absolute DN < {PR['absolute_dark_thresh']} test for voids wider than any blur radius.",
         "The union contains the σ = 40 term unchanged, so it cannot drop a pixel one radius kept;",
         "collapsing the ladder to (40,) reproduces the archived cut bit for bit, and that control",
         "runs before any number here is written.",
         f"On the example frame: {PR['frame_dark_single_pct']:.2f}% dark at one radius → {PR['frame_dark_union_pct']:.2f}% at seven."],
        rhs="NO parameter is fitted")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "det",
        f"clean_mask  →  candidates  ·  all {PR['frame_candidates']:,} kept",
        [f"Open r={SG['clean_open_radius']}, close r={SG['clean_close_radius']}, drop < {SG['clean_min_area_px_production']} px — run_unified_pipeline's own literal, not clean_mask's",
         f"default of {SG['clean_min_area_px_default']} — fill holes, then a {PR['min_area_candidate']} px floor on the component.",
         f"{PR['frame_candidates_single']:,} candidates at one radius → {PR['frame_candidates']:,} at seven, {PR['frame_cand_pct']:.2f}% of the frame.",
         "EVERY one of them survives to the output. Up to this line the SEM detector contains",
         "no learned parameter at all: a darkness cut, morphology, and an area floor."],
        rhs="zero fitted parameters to here")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "off", "PASS 1  ·  SCORED, THEN DISCARDED",
        [f"{M1['path']} is still read on every run and still writes an IsCrack column;",
         "detect_one.py then ignores it, because USE_REGION_CLASSIFIER is False.",
         f"On the example frame it would keep {PR['frame_archived_kept']:,} of {PR['frame_candidates']:,} regions and remove "
         f"{PR['frame_archived_would_drop_px']:,} px,",
         f"{100*PR['frame_archived_would_drop_frac']:.1f}% of what the app emits, {PR['frame_archived_drops_painted_px']:,} px of it hand-painted crack.",
         "IT IS NOT INERT. Pass 2's candidates are generated relative to the crack mask built",
         "from exactly this column, so the switched-off model still chooses what pass 2 may",
         "propose and what its two context features are measured against."],
        rhs=f"{M1['n_params']} coefficients, none of them consulted")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "fit", "PASS 2  ·  interior fill — THIS ONE DECIDES",
        [f"{M2['path']}. Adds MeanRawBrightness, MeanFlatBrightness, FracBoundaryTouchingCrack",
         "and MeanDistToCrack — context rather than shape — beside a geometric rule calibrated",
         f"on known positives: accept within {M2['interior_fill_rule']['dist_thr']:.1f} px of accepted crack and below "
         f"{M2['interior_fill_rule']['bri_thr']:.1f} flat",
         f"brightness, floor {M2['interior_fill_rule']['floor']:.2f}. Recall {M2['interior_fill_rule']['recall_on_known_positives']:.2f} on known positives at a "
         f"{M2['interior_fill_rule']['full_pool_accept_rate']:.2f} accept rate over the full pool.",
         f"On the example frame it generated {PR['pass2_candidates_generated']} candidates and accepted {PR['pass2_candidates_accepted']}, adding "
         f"{PR['frame_pass2_added_px']:,} px",
         f"({PR['frame_pass2_added_pct']:.2f} pp) that the candidate stage does not contain. Fill only: the candidates are",
         "a strict subset of the result."],
        rhs=f"{M2['n_params']} fitted parameters")
arrow(cx, y, y+26); y += 26
y = box(bx, y, bw, "hum", "Operator reviews whole regions",
        ["Add or remove a region before anything is measured; every change is written to a ledger:",
         f"{SG['ledger_path']} holds {SG['ledger_rows']} rows over {SG['ledger_frames']} frames. The old caption said 44 of 142 frames",
         "carried one; no record in these repositories produces that number, so it is not quoted.",
         "Not a brush — the unit of correction is the unit of decision."],
        rhs="auditable")
arrow(cx, y, y+26); y += 26
y_sem_end = box(bx, y, bw, "meas", "Measurement",
        ["Per crack: area, mean/max width, geodesic length, skeleton, junction order, orientation",
         "on doubled angles, H/W elongation. Per frame: P21, characteristic length, orientation",
         "histogram. Per specimen: ASTM E562 interval from BETWEEN-FIELD variance only."],
        rhs="what is reported")

# The coefficients, read out of the bundle by sem_models.py and NOT retyped here. They used
# to be eight literals in this file under a docstring claiming they had come from the
# artefact; a refit would have left the figure drawing last year's weights with no check
# able to see it.
CO = [(n, v) for n, v in M1["coefficients"]]
rx = X0 + bw + 40
rw = CW - bw - 40
by = barchart(rx, SEMTOP, rw, 300, [c[0] for c in CO], [c[1] for c in CO],
         f"Pass 1: the {M1['n_features']} weights, and what they now decide",
         "Standardised coefficients read out of the bundle the application still loads. Sign is "
         "toward 'crack'. Nothing downstream reads the verdict they produce, so this panel is "
         "the archived model's anatomy, not a description of a decision in the running system. "
         "Vesselness is the largest single term and it is NEGATIVE: given a region's shape, more "
         "ridge-like texture inside it argues AGAINST crack on this training set. Darkness is the "
         "smallest term of the eight — the thing a human looks at first.")
by += 10
FAM = M1["families"]
_famline = " · ".join(f"{k.split()[0]} {v['accuracy']:.3f}" for k, v in FAM.items()
                      if k != "LogisticRegression")
by = box(rx, by, rw, "det", "Why linear, while it was consulted",
    [f"On the same grouped split, trees score HIGHER raw accuracy — {_famline} against",
     f"LogisticRegression's {FAM['LogisticRegression']['accuracy']:.3f} — by calling almost everything crack. Their specificity is "
     + ", ".join(f"{v['specificity']:.3f}" for k, v in FAM.items() if k != "LogisticRegression"),
     f"against {FAM['LogisticRegression']['specificity']:.3f}, on a set that is "
     f"{100*M1['n_pos']/M1['n_train']:.0f}% positive. Ranked by pooled AUC the order reverses:",
     " · ".join(f"{k.split()[0]} {v['pooled_auc']:.3f}" for k, v in FAM.items()) + ".",
     "Accuracy on an 85%-positive set is not a model comparison. That argument chose this family;",
     "it is reproduced because the bundle is still on disk and still loaded, not because the",
     "choice still has consequences."],
    rhs=f"AUC {FAM['LogisticRegression']['pooled_auc']:.3f} vs "
        + ", ".join(f"{v['pooled_auc']:.2f}" for k, v in FAM.items() if k != "LogisticRegression"))
by += 10
by = box(rx, by, rw, "det", "What switching the verdict off is worth",
    ["Measured, not argued, and with ZERO free parameters — fitted and held-out are the same",
     "number by construction. On the 26 hand-labelled tiles, keeping every region the",
     "classifier would have rejected: precision 0.3378 → 0.4033, recall 0.3696 → 0.5326,",
     "IoU 0.2143 → 0.2979, F1 0.3530 → 0.4590. Paired across the 13 specimens the median IoU",
     "gain is +0.1753, 11 of 13 better, Wilcoxon p = 0.0061.",
     "It also ended a dead zone. Three ETD specimens scored recall 0.0000 at EVERY candidate",
     "setting ever tried, which read as the cracks being invisible to intensity. They were not:",
     "the candidate stage proposed them and the classifier rejected all of them —",
     "MAR_Amb_AS 0.0000 → 0.3792, MAR_Amb_Cast 0.0000 → 0.3537, MAR_Amb_HIP 0.0000 → 0.6827.",
     f"On the example frame, recall on the operator's own mask: {PR['frame_recall_single']:.3f} at one radius, "
     f"{PR['frame_recall_cand']:.3f} at",
     f"seven, {PR['frame_recall_archived']:.3f} if the classifier's verdict were honoured, {PR['frame_recall_emitted']:.3f} as the app emits it.",
     "A retrained 32-feature version of the same model deletes 72.67% of hand-painted crack on",
     "the 48 full frames; of six region-level precision rules tried, four are deleters and two",
     "change no score. Record: analysis/detector_overrides.py."],
    rhs="+0.1753 median IoU, 0 parameters")
by += 10
by = box(rx, by, rw, "fit", "Pass 2's weights put CONTEXT first",
    [" · ".join(f"{n} {v:+.3f}" for n, v in M2["coefficients"][:3]),
     " · ".join(f"{n} {v:+.3f}" for n, v in M2["coefficients"][3:7]),
     " · ".join(f"{n} {v:+.3f}" for n, v in M2["coefficients"][7:]),
     "The two strongest terms are both relational: how far this region sits from crack already",
     "accepted, and how bright it is after flattening. Vesselness flips sign between passes.",
     "These are the only learned weights in the SEM arm that change a pixel of the output."],
    rhs=f"{M2['n_features']} features, intercept {M2['intercept']:+.3f}")

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
assert last + 30 <= CANVAS, f"the plate overflowed the canvas: {last+30} > {CANVAS}"
img = img.crop((0, 0, W, last + 30))
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
# "the deployed bundle" was the phrase this caption used, and it is the one thing the
# figure may not say: the bundle is loaded, but its verdict is discarded.
CO_TEXT = (f"**Pass 1: the {M1['n_features']} weights, and what they now decide** \u2014 standardised "
           f"coefficients read out of `{M1['path']}`, the bundle the application still loads on "
           "every run; drawn as the bar panel beside the SEM column, sign toward crack. "
           + " \u00b7 ".join(f"{n} {v:+.3f}" for n, v in CO) +
           f", intercept {M1['intercept']:+.3f}. Vesselness is the largest single term and it is "
           "negative: given a region's shape, more ridge-like texture inside it argues against "
           "crack on this training set. Darkness is the smallest of the eight \u2014 the thing a "
           "human looks at first. **No stage reads the verdict these weights produce.** They are "
           "the archived model's anatomy, reproduced because the artefact is still on the SEM "
           "path, not because the decision still has consequences.")
_key = ("Colour says what kind of stage it is, keyed along the top: input; deterministic image "
        "processing; fitted to this laboratory's labels; **fitted, loaded, verdict discarded**; "
        "frozen and pre-trained; operator; measurement. The upper column is the SEM arm as "
        f"v{PR['version'].lstrip('v')} runs it, scoring candidate **regions**: nothing is fitted up to and "
        f"including the candidate stage, pass 1's {M1['n_params']} coefficients are computed and then "
        f"discarded at emission, and pass 2's {M2['n_params']} are the only learned weights in the arm "
        "that change a pixel of the output. The lower column is the TXM arm, scoring every "
        "**pixel**, with 46,658 fitted parameters on top of 637 M frozen ones. "
        "Stage by stage: ")
def _join(ls):
    """Join a box's drawn lines back into prose.

    An earlier version inserted "; " whenever a line did not end in punctuation, on the
    theory that each drawn line was a clause. Most are not: a wrapped sentence ends
    mid-phrase, and the rule produced "A databar, if present, is detected; by two
    independent signals". The case it was actually for is a coefficient list wrapped
    across lines -- "... MeanVesselness +1.364" / "LogArea -1.125 ..." -- which is the one
    place a separator is needed. So: separate only where a value is followed by a new
    term, and otherwise just rejoin the wrap.
    """
    out = ""
    for ln in ls:
        ln = ln.strip()
        if not out:
            out = ln
        elif out[-1].isdigit() and ln[:1].isupper():
            out += "; " + ln
        else:
            out += " " + ln
    return out
_key += " ".join(f"**{h}** \u2014 {_join(ls)}" for h, ls in BOXPROSE)
_key += " " + CO_TEXT

CAPTION = dict(
  min_px=MIN_PX,
  lead=("What the two models are made of: every layer shape, parameter count, coefficient and "
        "threshold was read out of the model files themselves and SAM's own configuration "
        "rather than from documentation, because in this project the documentation went stale "
        "twice while the files did not. The SEM column draws the pipeline the application "
        f"runs (v{PR['version'].lstrip('v')}), in which the candidate stage contains no fitted parameter "
        "at all and the eight-feature region classifier, though still loaded and still scored "
        "on every run, has its verdict discarded."),
  panel_key=_key,
  # The one number in the caption that is not drawn anywhere on the plate, and the one the
  # whole treatment turns on. Asserted against the record rather than written by hand.
  classifier_off_evidence=dict(
      artefacts_loaded=PR["learned_artefacts_loaded"],
      frame=PR["frame"],
      candidates=PR["frame_candidates"],
      classifier_would_keep=PR["frame_archived_kept"],
      classifier_would_remove_px=PR["frame_archived_would_drop_px"],
      of_emitted=round(PR["frame_archived_would_drop_frac"], 4),
      hand_painted_px_removed=PR["frame_archived_drops_painted_px"],
      pass2_generated=PR["pass2_candidates_generated"],
      pass2_accepted=PR["pass2_candidates_accepted"]),
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
