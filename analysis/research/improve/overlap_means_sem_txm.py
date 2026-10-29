"""One average precision, recall and F1 for SEM, and one for TXM -- per frame, not pooled.

WHY THIS FILE EXISTS. The manuscript carried a four-row table of precision/recall/F1 for
the public Inconel 718 collection and nothing at all for this laboratory's own two
collections. Two separate problems:

  `lab_madk_sweep.json` measures recall on 45 frames and precision on 18, and says in its
  own `scoring` field that the two "are never pooled into an F1". That is correct: a
  precision from one set of frames and a recall from another do not combine. The fix is
  not to pool them, it is to score all three on the INTERSECTION -- the frames that carry
  both a painted crack and a refereed not-crack verdict -- where F1 is defined.

  `txm_background_units.json` reports no overlap scores at all, because the TXM paint is
  far wider than the feature. That caveat is real and is reported here as a NUMBER rather
  than as a reason to withhold the measurement: the same three scores are computed for a
  geometrically correct 3 px trace of each frame's own paint, which is what a perfect
  detector of the real feature would earn against this brush. Read the TXM row against
  that row, never on its own.

PER FRAME, THEN AVERAGED. Pooling pixels lets one frame carry the number: in the TXM set
a single B3 frame holds 1,472,046 of the 2,431,104 crack pixels its whole group has -- 61%
of the group from 1 of 6 frames -- and its paint is 483 px wide at the 90th percentile,
14 um, which is a region and not a crack. A mean over frames gives that frame one vote.

Both collections score REFEREED PIXELS ONLY: 1 = crack, 2 or 3 = not-crack (3 is erase and
is still a not-crack verdict), 0 = unreviewed and excluded from the confusion matrix at
both ends. Scoring unrefereed area as negative is what once turned a precision of 0.99
into 0.29.

Opens all paint READ-ONLY.
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
TXM = "/Users/jiamingzhang/Desktop/APP/TXM_Crack_Detection_Pipeline"
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, os.path.join(SEM, "code"))
sys.path.insert(0, os.path.join(SEM, "interior_active_learning", "code"))
sys.dont_write_bytecode = True
import numpy as np
import tifffile
from scipy import ndimage as ndi
from skimage import exposure, measure as skm, morphology as morph
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
from common import contrast_kwargs_for
Image.MAX_IMAGE_PIXELS = None

PAINT = os.path.join(SEM, "interior_active_learning", "paint")
CORR = os.path.join(TXM, "paint", "corrections")
MADK = 6.0          # the setting Section 3.4 selects; the sweep is in lab_madk_sweep.json
MIN_PX = 200        # a frame needs this many of BOTH verdicts to score all three measures


class U:
    pass


u = U()
DO.install(u)


def clean(m):
    lab = skm.label(D.clean_mask(m, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel())
    k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def prf(m, pos, neg):
    tp = int((m & pos).sum())
    fp = int((m & neg).sum())
    fn = int((~m & pos).sum())
    p = tp / max(tp + fp, 1)
    r = tp / max(tp + fn, 1)
    return p, r, (2 * p * r / (p + r) if p + r else 0.0), tp, fp, fn


def precision_bracket(m, pos, neg):
    """Both ends of the precision a partly-refereed annotation can support.

    Neither collection adjudicates the whole frame. A precision computed over refereed
    pixels alone assumes every marked pixel nobody looked at is correct; the other end
    assumes every one is wrong. Reporting one end as the value is the error that once
    turned 0.99 into 0.29 in this project, so both are carried and the gap between them
    is the measurement's own uncertainty, not noise.
    """
    tp = int((m & pos).sum())
    fp_ref = int((m & neg).sum())
    fp_all = int((m & ~pos).sum())           # every marked pixel outside painted crack
    return (tp / max(tp + fp_ref, 1), tp / max(tp + fp_all, 1),
            int((m & ~pos & ~neg).sum()))


def trace_3px(pos):
    """The frame's own paint reduced to its centreline and redrawn 3 px wide.

    This is what a detector that is exactly right about WHERE the crack runs and marks it
    at the real feature width would score against this brush. It is a property of the
    labels; no detector is involved.
    """
    sk = morph.skeletonize(pos)
    return morph.binary_dilation(sk, morph.disk(1))


def width_p90(pos):
    if not pos.any():
        return 0.0
    dt = ndi.distance_transform_edt(pos)
    return float(2 * np.percentile(dt[pos], 90))


# ---------------------------------------------------------------- SEM, this lab's frames
def sem_frames():
    for nm in sorted(f[: -len("_correction_mask.png")] for f in os.listdir(PAINT)
                     if f.endswith("_correction_mask.png")):
        try:
            raw = tifffile.imread(os.path.join(SEM, "original", nm + ".tif"))
        except Exception as e:
            print(f"  skip {nm}: {e}", flush=True)
            continue
        if raw.ndim == 3:
            raw = raw[..., 0]
        ck = contrast_kwargs_for(nm)
        lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
        img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                          out_range=(0, 255)).astype(np.uint8)
        x0, y0, x1, y1 = D.find_field_of_view(img8)
        img8 = img8[y0:y1, x0:x1]
        corr = np.array(Image.open(os.path.join(PAINT, nm + "_correction_mask.png")))
        while corr.ndim > 2:
            corr = corr[..., 0]
        if corr.shape != img8.shape:
            if corr.shape[0] >= y1 and corr.shape[1] >= x1:
                corr = corr[y0:y1, x0:x1]
            else:
                print(f"  skip {nm}: mask does not fit the frame", flush=True)
                continue
        yield nm, img8, corr


def txm_group(n):
    n = n.lower()
    if "_b3_" in n:
        return "B3"
    if "wrought" in n:
        return "Wrought"
    if "hc_316l" in n:
        return "AM/HC"
    return "B2"


def txm_frames():
    for f in sorted(os.listdir(CORR)):
        if not f.endswith("_correction.npy"):
            continue
        stem = f[: -len("_correction.npy")]
        tif = os.path.join(TXM, "images", stem + ".tif")
        if not os.path.exists(tif):
            continue
        corr = np.load(os.path.join(CORR, f))
        img8 = D.load_as_uint8(tif)
        if img8.shape != corr.shape:
            print(f"  skip {stem[:46]}: shape {img8.shape} vs {corr.shape}", flush=True)
            continue
        yield stem, img8, corr


def run(label, it, grouper=None):
    rows = []
    for nm, img8, corr in it:
        pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
        if pos.sum() < MIN_PX or neg.sum() < MIN_PX:
            print(f"  -- {nm[:52]:<54} crack {int(pos.sum()):>9,}  "
                  f"notcrack {int(neg.sum()):>10,}  excluded, needs {MIN_PX} of both",
                  flush=True)
            continue
        m = clean(u.segment_dark_regions(D.flatten_background(img8), img8=img8,
                                         mad_k=MADK))
        p, r, f1, tp, fp, fn = prf(m, pos, neg)
        cp, cr, cf1, *_ = prf(trace_3px(pos), pos, neg)
        p_hi, p_lo, unref_marked = precision_bracket(m, pos, neg)
        f1_lo = (2 * p_lo * r / (p_lo + r)) if p_lo + r else 0.0
        row = {"frame": nm, "crack_px": int(pos.sum()), "notcrack_px": int(neg.sum()),
               "refereed_frac": float((pos.sum() + neg.sum()) / corr.size),
               "paint_width_p90_px": width_p90(pos),
               "precision": p, "recall": r, "f1": f1,
               "precision_if_unrefereed_wrong": p_lo,
               "f1_if_unrefereed_wrong": f1_lo,
               "marked_px_nobody_refereed": unref_marked,
               "ceiling_precision": cp, "ceiling_recall": cr, "ceiling_f1": cf1}
        if grouper:
            row["group"] = grouper(nm)
        rows.append(row)
        print(f"  {nm[:52]:<54} P {p:.4f}  R {r:.4f}  F1 {f1:.4f}   "
              f"(3px trace F1 {cf1:.4f}, paint {row['paint_width_p90_px']:.0f} px)",
              flush=True)
    return rows


def summarise(label, rows):
    if not rows:
        print(f"\n{label}: no frames scored")
        return {}
    g = lambda k: float(np.mean([x[k] for x in rows]))
    s = lambda k: float(np.std([x[k] for x in rows], ddof=1)) if len(rows) > 1 else 0.0
    out = {"n_frames": len(rows),
           "mean_precision": g("precision"), "mean_recall": g("recall"),
           "mean_f1": g("f1"),
           "sd_precision": s("precision"), "sd_recall": s("recall"), "sd_f1": s("f1"),
           "median_f1": float(np.median([x["f1"] for x in rows])),
           "mean_precision_if_unrefereed_wrong": g("precision_if_unrefereed_wrong"),
           "mean_f1_if_unrefereed_wrong": g("f1_if_unrefereed_wrong"),
           "ceiling_mean_precision": g("ceiling_precision"),
           "ceiling_mean_recall": g("ceiling_recall"),
           "ceiling_mean_f1": g("ceiling_f1"),
           "mean_paint_width_p90_px": g("paint_width_p90_px"),
           "per_frame": rows}
    print(f"\n{'=' * 96}\n{label}  --  mean over {len(rows)} frames, each frame one vote")
    print(f"  precision {out['mean_precision']:.4f} (sd {out['sd_precision']:.4f})")
    print(f"  recall    {out['mean_recall']:.4f} (sd {out['sd_recall']:.4f})")
    print(f"  F1        {out['mean_f1']:.4f} (sd {out['sd_f1']:.4f})  "
          f"median {out['median_f1']:.4f}")
    print(f"  precision bracket: {out['mean_precision_if_unrefereed_wrong']:.4f} if every "
          f"marked pixel nobody refereed is wrong, {out['mean_precision']:.4f} if every "
          f"one is right; F1 at the low end {out['mean_f1_if_unrefereed_wrong']:.4f}")
    print(f"  a geometrically correct 3 px trace of the same paint scores "
          f"F1 {out['ceiling_mean_f1']:.4f} "
          f"(P {out['ceiling_mean_precision']:.4f}, R {out['ceiling_mean_recall']:.4f})")
    print(f"  mean 90th-percentile paint width {out['mean_paint_width_p90_px']:.1f} px")
    return out


print(f"mad_k = {MADK:g}; refereed pixels only; a frame needs {MIN_PX} of each verdict\n")
print("SEM -- this laboratory's hand-corrected frames")
SEMR = summarise("SEM", run("SEM", sem_frames()))
print("\nTXM -- the transmission X-ray collection")
TXMR = summarise("TXM", run("TXM", txm_frames(), txm_group))

if TXMR:
    print("\nTXM by specimen group, mean over frames:")
    for gname in ("B3", "B2", "Wrought", "AM/HC"):
        sub = [x for x in TXMR["per_frame"] if x.get("group") == gname]
        if sub:
            print(f"  {gname:<8} n={len(sub):<3} P {np.mean([x['precision'] for x in sub]):.4f}"
                  f"  R {np.mean([x['recall'] for x in sub]):.4f}"
                  f"  F1 {np.mean([x['f1'] for x in sub]):.4f}"
                  f"   3px-trace F1 {np.mean([x['ceiling_f1'] for x in sub]):.4f}")

p = os.path.join(REPO, "docs/figures/overlap_means_sem_txm.json")
json.dump({"mad_k": MADK, "min_px_each_verdict": MIN_PX,
           "aggregation": "mean over frames, one vote per frame; pixels are NOT pooled",
           "scoring": "refereed pixels only: 1 = crack, 2 or 3 = not-crack, 0 excluded",
           "ceiling": "the frame's own paint skeletonised and redrawn 3 px wide, scored "
                      "against that same paint: what a detector exactly right about where "
                      "the crack runs earns against this brush",
           "SEM": SEMR, "TXM": TXMR}, open(p, "w"), indent=1)
print("\nwrote", p)
