"""Plate T1: what each stage of the TXM detector adds.

The TXM collection has its OWN detector -- not the SEM one carried over -- and it is a
different kind of model: a 17-channel feature stack feeding a small MLP, the same stack
concatenated with a frozen SAM ViT-H encoding, and the mean of the two. This plate shows
all three rungs on one window beside the operator's painted crack, so the reader can see
which rung changes what is marked.

The window is chosen by measurement, not by looks: its full-resolution agreement with the
operator is 0.503 against a corpus median of 0.507 over 58 labelled frames.

Arrays are the deployed model's own cached artefacts for that frame, so the SAM embedding
shown is the one the deployed model used (15 tiles over the whole frame), not one
re-embedded on a crop.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import journal_style as J
from scalebar import scalebar

J.use()
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
NAME = "T1 - TXM stages"

ST = json.load(open(os.path.join(HERE, "txm_stats.json")))
TH = ST["threshold"]
NM = ST["nm_per_px"]
d8 = np.load(os.path.join(HERE, "txm_disp8.npy"))
lbl = np.load(os.path.join(HERE, "txm_label.npy")).astype(bool)
p17 = np.load(os.path.join(HERE, "txm_p17.npy"))
ph = np.load(os.path.join(HERE, "txm_ph.npy"))
mask = np.load(os.path.join(HERE, "txm_mask.npy")).astype(bool)


def iou(a, b):
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    return float((a & b).sum() / max((a | b).sum(), 1))


PANELS = [
    ("a", "the operator's painted crack", lbl, J.rgb(J.PAINT_CRACK)),
    ("b", "17 hand-built channels", p17 > TH, J.rgb(J.MASK)),
    ("c", "+ frozen SAM ViT-H encoding", ph > TH, J.rgb(J.MASK)),
    ("d", "mean of the two, pruned", mask, J.rgb(J.MASK)),
]

H, W = d8.shape
fig, axes = plt.subplots(1, 4, figsize=(J.W2, J.W2 / 4 + 0.10))
fig.subplots_adjust(left=0.004, right=0.996, top=0.995, bottom=0.085, wspace=0.022)

bar_nm = None
for ax, (letter, _title, m, col) in zip(axes, PANELS):
    rgb = np.dstack([d8.astype(np.float32)] * 3) / 255.0
    sel = np.asarray(m, bool)
    for c in range(3):
        rgb[..., c][sel] = 0.30 * rgb[..., c][sel] + 0.70 * col[c]
    ax.imshow(rgb, interpolation="nearest")
    J.micrograph(ax)
    J.panel_label(ax, letter, inside=True)
    bar_nm = scalebar(ax, NM, W, loc="lower right", fontsize=J.TICK)

os.makedirs(OUT, exist_ok=True)
J.save(fig, os.path.join(OUT, NAME + ".png"),
       printed_width=J.COLUMN_CLASS.get(NAME, ("double", J.W2))[1])

vals = {
    "operator_paint_pct_of_window": round(100 * lbl.mean(), 2),
    "A_17ch": dict(iou=round(iou(p17 > TH, lbl), 4), pct_of_window=round(100 * (p17 > TH).mean(), 2)),
    "B_sam_hybrid": dict(iou=round(iou(ph > TH, lbl), 4), pct_of_window=round(100 * (ph > TH).mean(), 2)),
    "C_ensemble": dict(iou=round(iou(mask, lbl), 4), pct_of_window=round(100 * mask.mean(), 2)),
    "agreement_A_vs_B": round(iou(p17 > TH, ph > TH), 4),
    "agreement_B_vs_C": round(iou(ph > TH, mask), 4),
}
CAPTION = dict(
    what=("The TXM collection's own detector, stage by stage, on one window beside the "
          "operator's painted crack."),
    why=("The jump is from (b) to (c). The 17-channel stack alone marks the crack's trace and "
         "floods the matrix with it; adding the frozen encoder cuts what is marked from "
         f"{vals['A_17ch']['pct_of_window']:.0f}% of the window to "
         f"{vals['B_sam_hybrid']['pct_of_window']:.0f}%, against the operator's "
         f"{vals['operator_paint_pct_of_window']:.0f}%. The ensemble's advantage over (c) is a "
         "corpus-level result and is not visible on any one window."),
    panels=dict(a="the operator's painted crack, the reference for this window",
                b="17 hand-built channels: intensity, smooth sigma 2-64, gradmag sigma 1-8, "
                  "laplacian sigma 1-8, texture sigma 2 and 8, scaled then MLP(64, 32); runs "
                  "with no encoder and is the fallback when SAM is unreachable",
                c="the same 17 channels concatenated with 256 frozen SAM ViT-H encoder "
                  "channels, 273 inputs, MLP(128, 64); 1024 px tiles at stride 896, "
                  "Hann-blended; the encoder is never fine-tuned and its prompt encoder and "
                  "mask decoder are never called",
                d="predict() returns the mean of (b) and (c) at threshold "
                  f"{TH:.2f}, then speck pruning -- the deployed mask"),
    values=vals,
    window=dict(frame=ST["frame"], crop=ST["crop"], side_px=int(W),
                nm_per_px=NM, side_um=round(W * NM / 1000.0, 2),
                scale_bar_nm=bar_nm,
                frame_iou=ST["frame_iou"], corpus_n=ST["corpus_n"],
                corpus_median_iou=ST["corpus_median_iou"],
                corpus_q1=ST["corpus_q1"], corpus_q3=ST["corpus_q3"]),
    caveats=[
        "The pixel size of 29.24 nm/px is DERIVED from operator-supplied mosaic geometry, not "
        "read from instrument metadata; the TXM repository marks it [TODO-AUTHOR]. Any "
        "physical length on this plate inherits that assumption.",
        "The display is contrast-stretched per crop for legibility; the model ran on the "
        "unstretched image.",
        "The IoU values here are for ONE window and are not the corpus figures. The published "
        "cross-validated scores -- 17-feature 0.726, hybrid 0.786, ensemble 0.811 -- are "
        "scored on a 250,000-row sample of hand-painted pixels that is 49% crack, not on whole "
        "frames, and drop to 0.51-0.67 when a whole specimen is held out.",
        "Zero-shot SAM figures of 0.23-0.36 reported elsewhere are NOT comparable to those "
        "cross-validated numbers: 4 frames against 71, external masks against the owner's own, "
        "the full painted crack against its dark core, whole frames at about 1% prevalence "
        "against a 49%-crack sample, and cold inference against grouped cross-validation.",
        "Plate T2 is the necessary companion: an IoU against this reference rewards covering "
        "the stroke, and the stroke is median 53.9 px wide.",
    ],
    source="paper/figures/txm_*.npy and txm_stats.json, cached from the deployed TXM model "
           "(model key " + ST["model_key"] + ", " + ST["sam_model"] + ")",
)
json.dump(CAPTION, open(os.path.join(OUT, NAME + ".caption.json"), "w"),
          indent=1, ensure_ascii=False)
print("caption written; bar =", bar_nm, "nm")
