"""The SEM detector carried to TXM: where it works, where it does not, and by how much.

Two rows of panels and two bars. The panels are the two specimen groups that behave most
differently -- B3, where the detector transfers, and AM/HC, where it is effectively blind
while still marking a tenth of the refereed area. The bars are every group, scored the way
the rest of this work scores: accuracy against the accuracy of an EMPTY MASK, and the crack
area fraction reported against the one painted.

Only refereed pixels are scored (1 = crack, 2 or 3 = not-crack, 0 = unreviewed, excluded),
so every percentage is of the refereed area and the panels shade the unrefereed part so a
reader can see how much of each frame nobody ruled on.

SCALE BARS. Every TXM frame has a pixel size, but it is DERIVED: 29.24 nm/px from
operator-supplied mosaic geometry (a 30 um window at 0.35 overlap, 9x5 tiles over
6367x3691 px), not read from instrument metadata, and the TXM repository marks it
[TODO-AUTHOR] and notes that two frames close only at 0.30 overlap. The bars are drawn and
the caption says where the number came from; if the operator corrects the window or the
overlap, every bar here scales with it.
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
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from skimage import measure as skm
import detect_cracks as D
import detector_overrides as DO
from scalebar import scalebar
import journal_style as J

J.use()

NM_PER_PX = 29.24          # derived from mosaic geometry; see the docstring
# The width this plate is printed at on the page (PAGE[0] - ML - MR in make_paper.py).
# Drawn at 12.4 in it reached the page at 0.51x and its 8 pt labels printed at 4.1 pt.
# Five columns do not fit in 6.37 in, so the panels and the bars are stacked instead.
PAGEW = 6.37
FLOOR = 7.0
MADK = 6.0                 # the operating point Section 3.2 argues for on SEM
OUT = os.path.join(REPO, "paper/figures/out/txm_transfer.png")
BG = json.load(open(os.path.join(REPO, "docs/figures/txm_background_units.json")))




class U:
    pass


u = U()
DO.install(u)


def cand(m):
    lab = skm.label(D.clean_mask(m, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel())
    k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def group_of(n):
    n = n.lower()
    if "_b3_" in n:
        return "B3"
    if "wrought" in n:
        return "Wrought"
    if "hc_316l" in n:
        return "AM/HC"
    return "B2"


cdir = os.path.join(TXM, "paint", "corrections")
cands = []
for f in sorted(os.listdir(cdir)):
    if not f.endswith("_correction.npy"):
        continue
    stem = f[: -len("_correction.npy")]
    tif = os.path.join(TXM, "images", stem + ".tif")
    if not os.path.exists(tif):
        continue
    corr = np.load(os.path.join(cdir, f))
    c = int((corr == 1).sum())
    if c >= 5000 and int(((corr == 2) | (corr == 3)).sum()) >= 5000:
        cands.append((group_of(stem), c, stem, tif, os.path.join(cdir, f)))

# the most heavily painted frame of each of the two groups that disagree most
pick = {}
for g in ("B3", "AM/HC"):
    rows = [c for c in cands if c[0] == g]
    if rows:
        pick[g] = max(rows, key=lambda r: r[1])
print({g: v[2][:48] for g, v in pick.items()})

fig = plt.figure(figsize=(J.PAGEW, 6.9))
# panels on top (2 rows x 3), bars underneath (1 row x 2). Side by side they needed
# 12.4 in and the page gives 6.37.
# nested spacing: the micrograph rows abut, the bar row keeps a normal gap
gs = fig.add_gridspec(3, 3, height_ratios=[1, 1, 1.25], hspace=0.055,
                      wspace=0.015)

for r, g in enumerate(("B3", "AM/HC")):
    if g not in pick:
        continue
    _, _, stem, tif, cpath = pick[g]
    corr = np.load(cpath)
    img8 = D.load_as_uint8(tif)
    flat = D.flatten_background(img8)
    m = cand(u.segment_dark_regions(flat, img8=img8, mad_k=MADK))
    crack = corr == 1
    notc = (corr == 2) | (corr == 3)
    ref = crack | notc
    # crop to the painted crack so the panels show the feature, not a field of matrix
    ys, xs = np.where(crack)
    cy, cx = int(ys.mean()), int(xs.mean())
    H = min(900, img8.shape[0], img8.shape[1])
    y0 = int(np.clip(cy - H // 2, 0, img8.shape[0] - H))
    x0 = int(np.clip(cx - H // 2, 0, img8.shape[1] - H))
    sl = (slice(y0, y0 + H), slice(x0, x0 + H))
    I, C, M, R = img8[sl], crack[sl], m[sl], ref[sl]
    # DISPLAY ONLY, and the caption says so. load_as_uint8 stretches the whole
    # frame, so a crop of a dark corner renders near-black and shows nothing. The
    # detector ran on the unstretched crop; this rescaling touches the panel only.
    lo, hi = np.percentile(I, [1, 99])
    I = np.clip((I.astype(float) - lo) / max(hi - lo, 1e-6), 0, 1)
    I = (255 * I).astype(np.uint8)

    ax = fig.add_subplot(gs[r, 0])
    ax.imshow(I, cmap="gray")
    scalebar(ax, NM_PER_PX, H)
    J.micrograph(ax)
    J.panel_label(ax, "ad"[r], inside=True)

    ax2 = fig.add_subplot(gs[r, 1])
    ov = np.dstack([I] * 3).astype(float) / 255.0
    ov[~R] *= 0.45                       # unrefereed area dimmed: nobody ruled on it
    ov[C] = [0.10, 0.55, 0.95]
    ax2.imshow(ov)
    scalebar(ax2, NM_PER_PX, H)
    J.micrograph(ax2)
    J.panel_label(ax2, "be"[r], inside=True)

    ax3 = fig.add_subplot(gs[r, 2])
    ov = np.dstack([I] * 3).astype(float) / 255.0
    ov[~R] *= 0.45
    ov[M & C] = [0.10, 0.70, 0.25]       # found
    ov[M & ~C & R] = [0.95, 0.35, 0.05]  # marked, refereed not-crack
    ov[~M & C] = [0.20, 0.35, 0.95]      # missed
    ax3.imshow(ov)
    scalebar(ax3, NM_PER_PX, H)
    J.micrograph(ax3)
    J.panel_label(ax3, "cf"[r], inside=True)

# ---- the bars: every group, in the units the paper reports ---------------------------
groups = ["B3", "B2", "Wrought", "AM/HC"]
key = f"SEM detector, mad_k={MADK:g}"
acc = [BG["by_group"][g]["arms"][key]["accuracy_pct"] for g in groups]
emp = [BG["by_group"][g]["arms"][key]["empty_mask_accuracy_pct"] for g in groups]
area = [BG["by_group"][g]["arms"][key]["area_agreement"] for g in groups]
pool = BG["pooled"][key]

axA = fig.add_subplot(gs[2, 0:2])
y = np.arange(len(groups))[::-1]
cols = [J.ACCENT if g == "B3" else J.G_LIGHT for g in groups]
# the SIGNED difference from an all-background mask, zero-based: the accuracies
# themselves are 65-97% and a cropped axis to separate them would be the
# misrepresentation the convention exists to prevent
dif = [a - e for a, e in zip(acc, emp)]
axA.barh(y, dif, 0.6, color=cols, edgecolor=J.INK, linewidth=0.5, zorder=2)
axA.barh([-1], [pool["margin_pp"]], 0.6, color=J.G_MID, edgecolor=J.INK,
         linewidth=0.5, zorder=2)
axA.axvline(0.0, color=J.INK, lw=0.9, zorder=3)
axA.set_yticks(list(y) + [-1], groups + ["pooled"])
axA.set_xlabel("Pixel accuracy relative to an\nall-background mask (points)")
J.panel_label(axA, "g")

axB = fig.add_subplot(gs[2, 2])
axB.barh(y, area, 0.6, color=cols, edgecolor=J.INK, linewidth=0.5, zorder=2)
axB.barh([-1], [pool["area_agreement"]], 0.6, color=J.G_MID, edgecolor=J.INK,
         linewidth=0.5, zorder=2)
axB.axvline(1.0, color=J.INK, lw=0.9, zorder=3)
axB.set_yticks(list(y) + [-1], ["" for _ in groups] + [""])
axB.set_xlabel("Reported / annotated\ncrack area")
J.panel_label(axB, "h")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.subplots_adjust(left=0.085, right=0.995, top=0.995, bottom=0.085)
J.save(fig, OUT)
