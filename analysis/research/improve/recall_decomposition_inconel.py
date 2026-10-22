"""Where does recall go on Inconel 718? Stage by stage, before touching anything.

The detector reaches recall 0.4123 on whole fields. This asks which stage loses the other
0.59, because a fix aimed at the wrong stage cannot work: if the pixels were never
proposed, no amount of post-filtering brings them back.

Six nested arms, each removing one gate, so the gap between consecutive rows is what that
gate costs in recall:

    everything dark anywhere   no gates at all -- the ceiling the proposal stage can reach
    MAD cut only              drop the absolute darkness floor
    shipped proposal          both gates, as shipped
    + clean                   holes filled, blobs under 13 px dropped
    + 40 px region floor      the shipped answer

Run with the SEM repo's interpreter.
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
from skimage import measure as skm
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None

SCR = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
SRC = os.path.join(SCR, "pub_ebc_download/train_subset/Inconel718_crack")


class U:
    pass


u = U()
DO.install(u)


def load():
    mdir = os.path.join(SRC, "mask")
    mstem = {os.path.splitext(f)[0]: f for f in os.listdir(mdir)}
    out = []
    for f in sorted(os.listdir(os.path.join(SRC, "image"))):
        stem = os.path.splitext(f)[0]
        if stem not in mstem:
            continue
        a = np.array(Image.open(os.path.join(SRC, "image", f)))
        img = (a >> 8).astype(np.uint8) if a.dtype == np.uint16 else \
            np.array(Image.open(os.path.join(SRC, "image", f)).convert("L"))
        gt = np.array(Image.open(os.path.join(mdir, mstem[stem])).convert("L")) > 127
        if img.shape == gt.shape and gt.sum() >= 50:
            out.append((stem, img, gt))
    return out


def arms(img8):
    """Every nested arm, from no gates to the shipped answer."""
    flat = D.flatten_background(img8)
    out = {}
    # no gates at all: dark at any scale with the MAD cut wide open
    out["no gates (mad_k=0.5, no floor)"] = u.segment_dark_regions(
        flat, img8=img8, mad_k=0.5, absolute_dark_thresh=0)
    out["MAD cut only (no darkness floor)"] = u.segment_dark_regions(
        flat, img8=img8, mad_k=5.0, absolute_dark_thresh=0)
    raw = u.segment_dark_regions(flat, img8=img8, mad_k=5.0)
    out["shipped proposal (both gates)"] = raw
    cleaned = D.clean_mask(raw, min_area_px=13)
    out["+ clean, blobs under 13 px"] = cleaned
    lab = skm.label(cleaned, connectivity=2)
    if lab.max():
        sz = np.bincount(lab.ravel())
        keep = np.where(sz >= 40)[0]
        out["+ 40 px region floor (SHIPPED)"] = np.isin(lab, keep[keep > 0])
    else:
        out["+ 40 px region floor (SHIPPED)"] = np.zeros_like(cleaned, bool)
    return out


data = load()
print(f"{len(data)} Inconel 718 whole fields\n")
names = list(arms(data[0][1]))
acc = {n: {"tp": 0, "fp": 0, "fn": 0, "marked": 0} for n in names}
total_gt = 0
npx = 0
for i, (stem, img, gt) in enumerate(data, 1):
    total_gt += int(gt.sum())
    npx += gt.size
    for n, m in arms(img).items():
        acc[n]["tp"] += int((m & gt).sum())
        acc[n]["fp"] += int((m & ~gt).sum())
        acc[n]["marked"] += int(m.sum())
    if i % 8 == 0:
        print(f"  [{i}/{len(data)}]", flush=True)

print(f"\n{'arm':36s} {'recall':>8s} {'precision':>10s} {'F1':>7s} {'marked%':>9s} "
      f"{'d recall':>9s}")
prev = None
rows = {}
for n in names:
    a = acc[n]
    rc = a["tp"] / max(total_gt, 1)
    pr = a["tp"] / max(a["tp"] + a["fp"], 1)
    f1 = 2 * pr * rc / max(pr + rc, 1e-12)
    mk = 100 * a["marked"] / npx
    d = "" if prev is None else f"{rc - prev:+9.4f}"
    print(f"{n:36s} {rc:8.4f} {pr:10.4f} {f1:7.4f} {mk:8.3f}% {d:>9s}")
    rows[n] = {"recall": rc, "precision": pr, "f1": f1, "marked_pct": mk}
    prev = rc

ceiling = rows[names[0]]["recall"]
shipped = rows[names[-1]]["recall"]
print(f"\nthe proposal stage can reach recall {ceiling:.4f} with both gates open.")
print(f"the shipped answer reaches {shipped:.4f}.")
print(f"  lost to the DARKNESS FLOOR : {rows[names[1]]['recall'] - rows[names[2]]['recall']:+.4f}")
print(f"  lost to the MAD CUT        : {rows[names[0]]['recall'] - rows[names[1]]['recall']:+.4f}")
print(f"  lost to CLEAN + SIZE FLOORS: {rows[names[2]]['recall'] - rows[names[4]]['recall']:+.4f}")
print(f"  NEVER PROPOSED even with both gates open: {100*(1-ceiling):.1f}% of labelled crack")

out = os.path.join(REPO, "docs/figures/recall_decomposition_inconel.json")
json.dump({"n": len(data), "pooled_over_pixels": True, "arms": rows,
           "proposal_ceiling_recall": ceiling, "shipped_recall": shipped,
           "note": "nested arms; the gap between consecutive rows is what that gate costs"},
          open(out, "w"), indent=1)
print("\nwrote", out)
