"""How wide is the label, and what does that alone do to IoU?

THE CLAIM THIS MEASURES. The same detector scores IoU 0.68 on DeepCrack and about 0.33 on
this project's own corpus. If that gap is the ANNOTATION rather than the detector, then a
by-construction-PERFECT answer -- the label's own medial axis, redrawn at a chosen width --
should show the same pattern: its IoU against the label depends almost entirely on how wide
the human drew, and peaks at the label's own width.

So for each dataset: skeletonise the ground truth, redraw it at widths 1..41 px, and score
each against the original label. Zero localisation error by construction. Whatever IoU that
curve peaks at is the most any correct answer can score there.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from PIL import Image
import scipy.io as sio
Image.MAX_IMAGE_PIXELS = None

SCR = "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad"
WIDTHS = [1, 3, 5, 7, 9, 11, 15, 21, 31, 41]
ST = ndi.generate_binary_structure(2, 2)


def iou(p, g):
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    inter = int((p & g).sum()); union = int((p | g).sum())
    return inter / max(union, 1)


def half_width(gt):
    """Median distance from a label pixel on the medial axis to the label's edge, doubled:
    the stroke width the human actually drew."""
    sk = skeletonize(gt)
    if not sk.any():
        return None
    d = ndi.distance_transform_edt(gt)
    return float(np.median(d[sk]) * 2.0)


def trace_at(gt, w):
    sk = skeletonize(gt)
    if w <= 1:
        return sk
    it = max(int(round((w - 1) / 2)), 1)
    return ndi.binary_dilation(sk, ST, iterations=it)


def run(name, pairs, limit=60):
    per_w = {w: [] for w in WIDTHS}
    hw = []
    used = 0
    for i, pr in enumerate(pairs[:limit], 1):
        img, gt = pr
        if gt is None or gt.sum() < 50 or gt.mean() > 0.6:
            continue
        used += 1
        h = half_width(gt)
        if h:
            hw.append(h)
        for w in WIDTHS:
            per_w[w].append(iou(trace_at(gt, w), gt))
        if i % 20 == 0:
            print(f"   [{i}]", flush=True)
    if not used:
        return None
    curve = {str(w): float(np.mean(v)) for w, v in per_w.items()}
    best_w = max(WIDTHS, key=lambda w: np.mean(per_w[w]))
    return {"n": used, "label_stroke_px_median": float(np.median(hw)) if hw else None,
            "iou_by_trace_width": curve,
            "ceiling_iou": curve[str(best_w)], "ceiling_at_width": best_w}


RES = {}
dc = f"{SCR}/pub_deepcrack/DeepCrack-master/dataset"
pairs = []
for f in sorted(os.listdir(dc + "/test_img")):
    g = os.path.join(dc, "test_lab", os.path.splitext(f)[0] + ".png")
    if os.path.exists(g):
        pairs.append((None, np.array(Image.open(g).convert("L")) > 127))
print(f"DeepCrack: {len(pairs)}")
RES["DeepCrack"] = run("DeepCrack", pairs)

cf = f"{SCR}/pub_cfd/CrackForest-dataset-master"
names = sorted(f[:-4] for f in os.listdir(cf + "/groundTruth") if f.endswith(".mat"))
pairs = []
for n in names:
    seg = np.array(sio.loadmat(os.path.join(cf, "groundTruth", n + ".mat"))
                   ["groundTruth"][0, 0]["Segmentation"])
    pairs.append((None, seg == 2))
print(f"CrackForest: {len(pairs)}")
RES["CrackForest"] = run("CrackForest", pairs)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "width_ceiling.json")
json.dump(RES, open(out, "w"), indent=1)
print("\nwrote", out)
for k, v in RES.items():
    print(f"\n{k}: n={v['n']}  label stroke {v['label_stroke_px_median']:.1f} px")
    print(f"   perfect-trace IoU peaks at {v['ceiling_iou']:.4f} at width {v['ceiling_at_width']} px")
    print("   ", {w: round(x, 3) for w, x in v["iou_by_trace_width"].items()})
