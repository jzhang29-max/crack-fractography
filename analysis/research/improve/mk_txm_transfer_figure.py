"""The SEM detector carried to TXM: where it works, where it does not, and by how much.

Two rows of panels and two bars. The panels are the two specimen series the paper reports
on and the two that behave most differently -- B3, where the detector clears an empty mask
by a wide margin, and B2, where it does not. The bars are both series and the pooled value,
scored the way the rest of this work scores: accuracy against the accuracy of an EMPTY
MASK, and the crack area fraction reported against the one painted. The rows and the bars
are driven by what the restricted measurement record holds, so a change of scope moves them
without an edit here.

Only refereed pixels are scored (1 = crack, 2 or 3 = not-crack, 0 = unreviewed, excluded),
so every percentage is of the refereed area and the panels shade the unrefereed part so a
reader can see how much of each frame nobody ruled on.

WHICH FRAME EACH ROW SHOWS, AND WHY THE RULE CHANGED. The first version of this plate
picked `max(crack pixels)` within each group. That is the rule that selects the largest
painted BLOB, and it did: the B3 frame it chose, b3_380_00um, carries 1,472,046 of that
group's 2,431,104 refereed crack pixels, and 73.2% of those pixels lie more than 50 px
INSIDE the paint. A stroke that follows a crack has almost no deep interior -- every
AM/HC frame but one is at 0.0% on the same statistic -- so that annotation is a filled
region and not a crack trace. The panel showed it at the centroid of the region, which is
why the crop was solid paint with no micrograph visible in it.

Ranking by skeleton length instead does NOT fix it: that frame has the longest skeleton in
its group as well. The rule here therefore has two parts, both printed when this runs:

  ELIGIBILITY -- at least 5,000 refereed pixels of each verdict, AND at most
  MAX_DEEP_SHARE of the painted crack lying more than DEEP_PX inside the paint. The second
  condition is what excludes a region.
  CHOICE -- among the eligible frames, the LONGEST painted crack by skeleton length.

The frames this selects are named in the caption sidecar this script writes. Excluding a
frame from the PANEL does not exclude it from any number: the bars in (g) and (h) are
computed over every frame of both series, the ineligible ones included, and Section 4.3
reports what dropping the largest B3 frame does to that group's margin.

WHAT THE B3 ROW IS AGREEING WITH. That series' painted crack sits at essentially zero
optical density -- see `txm_paint_free_beam.py` -- so most of what the detector proposes
there it proposes through the absolute darkness floor, which fires on anything near zero.
The row is drawn because the paper reports the series; the caption carries the audit.

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
from skimage import measure as skm, morphology as morph
from scipy import ndimage as ndi
import detect_cracks as D
import detector_overrides as DO
from scalebar import scalebar
import journal_style as J

J.use()

NM_PER_PX = 29.24          # derived from mosaic geometry; see the docstring
#: A painted crack is eligible to be SHOWN only if its paint is a trace rather than a
#: filled region. Measured as the share of painted pixels further than DEEP_PX from the
#: edge of the paint. Across the 31 scorable frames this runs 0.0% (nine AM/HC frames) to
#: 73.2% (the B3 frame the old rule chose); the four frames above 36% are the two B3 and
#: two Wrought region annotations. 25% sits in the empty part of that range.
DEEP_PX, MAX_DEEP_SHARE = 50, 0.25
#: A frame is also ineligible to be SHOWN if the detector marks more operator-REJECTED
#: area on it than there is painted crack. Such a panel is not a picture of crack
#: detection: it is a picture of one enormous false positive, and the B2 frame the
#: length rule used to choose, b2_343_75_LARGE, is exactly that -- 1,169,632 rejected
#: pixels against 258,927 painted ones, rendering as a sheet of flat red across the
#: lower half of the panel, and 85.3% of its marked area lies at an optical density
#: below 0.10, which is the gap where the beam missed the specimen rather than material.
#: The bound separates cleanly: that frame sits at 4.52 and the next highest of the
#: eighteen at 0.35, so nothing else in either group is touched. It is a choice of
#: PANEL only and changes no number; the bars in (g) and (h) are over all frames.
MAX_FP_RATIO = 1.0
#: The eligibility floor, named rather than repeated as a literal in the loop below.
MIN_PX = 5000
# The width this plate is printed at on the page (PAGE[0] - ML - MR in make_paper.py).
# Drawn at 12.4 in it reached the page at 0.51x and its 8 pt labels printed at 4.1 pt.
# Five columns do not fit in 6.37 in, so the panels and the bars are stacked instead.
PAGEW = 6.37
FLOOR = 7.0
MADK = 6.0                 # the operating point Section 3.2 argues for on SEM
OUT = os.path.join(REPO, "paper/figures/out/txm_transfer.png")
# THE RESTRICTED RECORD. The paper reports on specimen series b2 and b3, and the measuring
# scripts write that scope to a separate file rather than overwriting the full-corpus one.
# `scoped()` raises if it is missing instead of falling back, because a plate that quietly
# drew the wider corpus would carry a caption naming the narrower one.
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))
import _paths as PATHS                               # noqa: E402
BG = json.load(open(PATHS.scoped("txm_background_units.json")))
#: The two rows of panels and the bars, driven by what the restricted record holds.
PANEL_GROUPS = tuple(g for g in ("B3", "B2") if g in BG["by_group"])




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
    crack = corr == 1
    c = int(crack.sum())
    if c >= MIN_PX and int(((corr == 2) | (corr == 3)).sum()) >= MIN_PX:
        # LENGTH, not area, and only if the paint is a trace. See the docstring.
        dt = ndi.distance_transform_edt(crack)
        skel = int(morph.skeletonize(crack).sum())
        wid = float(2 * np.percentile(dt[crack], 90))
        deep = float((dt[crack] > DEEP_PX).mean())
        # How much operator-REJECTED area the detector marks here, relative to the
        # painted crack. See MAX_FP_RATIO: this is what keeps the panel from being one
        # enormous false positive over the gap where the beam missed the specimen.
        img8 = D.load_as_uint8(tif)
        if img8.shape != corr.shape:
            continue
        final = cand(u.segment_dark_regions(D.flatten_background(img8), img8=img8,
                                            mad_k=MADK))
        fp_ratio = float((final & ((corr == 2) | (corr == 3))).sum() / max(c, 1))
        cands.append((group_of(stem), skel, stem, tif, os.path.join(cdir, f), c, wid,
                      deep, fp_ratio))

# the LONGEST TRACE-PAINTED crack in each of the two groups that disagree most
pick = {}
for g in PANEL_GROUPS:
    rows = [c for c in cands if c[0] == g]
    ok = [r for r in rows if r[7] <= MAX_DEEP_SHARE and r[8] <= MAX_FP_RATIO]
    if not ok:
        raise SystemExit(
            f"mk_txm_transfer_figure: no {g} frame is both trace-painted at "
            f"MAX_DEEP_SHARE={MAX_DEEP_SHARE} and below MAX_FP_RATIO={MAX_FP_RATIO}. "
            f"Do not fall back to the widest region or to a frame that is one huge "
            f"false positive -- that is the behaviour these rules exist to stop. Raise "
            f"a bound deliberately, or drop the row.")
    pick[g] = max(ok, key=lambda r: r[1])
    for r in sorted(rows, key=lambda r: -r[1]):
        tag = ("<- shown" if r is pick[g]
               else "excl:paint" if r[7] > MAX_DEEP_SHARE
               else "excl:fp" if r[8] > MAX_FP_RATIO else "        ")
        print(f"  {g:<7} skeleton {r[1]:>7,} px  area {r[5]:>9,} px  paint p90 "
              f"{r[6]:6.1f} px  deep {100 * r[7]:5.1f}%  fp/crack {r[8]:5.2f}  "
              f"{tag}  {r[2][:52]}")

fig = plt.figure(figsize=(J.PAGEW, 6.9))
# Panels on top (2 rows x 3), bars underneath (1 row x 2). Side by side they needed
# 12.4 in and the page gives 6.37.
#
# NESTED, because one hspace cannot do two jobs. The comment here used to claim that
# "the micrograph rows abut, the bar row keeps a normal gap" from a single 3-row
# gridspec with hspace=0.055, which gives all three rows the SAME gap: the bar panels'
# (g) and (h) labels sat against the bottom edge of the micrographs above them. An
# outer two-row grid separates the two blocks, and each block sets its own spacing.
outer = fig.add_gridspec(2, 1, height_ratios=[2.0, 1.25], hspace=0.17)
gs = outer[0].subgridspec(2, 3, hspace=0.02, wspace=0.015)
gsb = outer[1].subgridspec(1, 3, wspace=0.055)

for r, g in enumerate(PANEL_GROUPS):
    if g not in pick:
        continue
    _, _, stem, tif, cpath = pick[g][:5]
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
    # Unrefereed area dimmed: nobody ruled on it, and it is excluded from every number.
    # 0.45 was too strong once the B3 row moved to a frame where most of the crop is
    # unrefereed -- the reviewed islands then read as bright particles in the
    # microstructure rather than as the part of the image a human looked at.
    ov[~R] *= 0.62
    ov[C] = list(J.rgb(J.MASK))
    ax2.imshow(ov)
    scalebar(ax2, NM_PER_PX, H)
    J.micrograph(ax2)
    J.panel_label(ax2, "be"[r], inside=True)

    ax3 = fig.add_subplot(gs[r, 2])
    ov = np.dstack([I] * 3).astype(float) / 255.0
    ov[~R] *= 0.62
    # HOUSE TOKENS, NOT LITERALS. These were four hardcoded RGB floats, and two pairs
    # of them were invisible to a colour-blind reader: found vs marked-not-crack
    # measured 4.19 under worst-case CVD and annotated vs found 5.38, against the 5.9
    # that journal_style.py's own comment calls a FAIL. The tokens clear it at 17.05.
    ov[M & C] = list(J.rgb(J.PAINT_CRACK))          # found
    ov[M & ~C & R] = list(J.rgb(J.PAINT_NOTCRACK))  # marked, refereed not-crack
    ov[~M & C] = list(J.rgb(J.MASK))                # missed
    ax3.imshow(ov)
    scalebar(ax3, NM_PER_PX, H)
    J.micrograph(ax3)
    J.panel_label(ax3, "cf"[r], inside=True)

# ---- the bars: every group, in the units the paper reports ---------------------------
groups = [g for g in ("B3", "B2", "Wrought", "AM/HC") if g in BG["by_group"]]
key = f"SEM detector, mad_k={MADK:g}"
acc = [BG["by_group"][g]["arms"][key]["accuracy_pct"] for g in groups]
emp = [BG["by_group"][g]["arms"][key]["empty_mask_accuracy_pct"] for g in groups]
area = [BG["by_group"][g]["arms"][key]["area_agreement"] for g in groups]
pool = BG["pooled"][key]

axA = fig.add_subplot(gsb[0, 0:2])
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

axB = fig.add_subplot(gsb[0, 2])
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

# THE SIDECAR. Every other plate in the programme writes one and this was the only figure
# that did not, which made it the only figure whose caption could not be checked against
# what was actually drawn.
json.dump({
    "figure": os.path.basename(OUT),
    "what": "the SEM detector carried unchanged to the transmission collection: two rows "
            "of panels, one per specimen series, and two bar panels over both series and "
            "the pooled value",
    "panel_rows": {g: {"frame": pick[g][2], "skeleton_px": int(pick[g][1]),
                       "painted_crack_px": int(pick[g][5]),
                       "paint_p90_width_px": round(float(pick[g][6]), 1),
                       "deep_share": round(float(pick[g][7]), 4)}
                   for g in PANEL_GROUPS if g in pick},
    "selection_rule": {
        "eligibility": f"at least {MIN_PX:,} refereed pixels of each verdict, and at most "
                       f"{MAX_DEEP_SHARE:.0%} of the painted crack lying more than "
                       f"{DEEP_PX} px inside the paint",
        "choice": "among the eligible frames, the longest painted crack by skeleton length",
        "note": "excluding a frame from a panel does not exclude it from any bar",
    },
    "bars": {"groups": groups, "mad_k": MADK,
             "accuracy_margin_pp": {g: round(float(d), 3) for g, d in zip(groups, dif)},
             "pooled_accuracy_margin_pp": round(float(pool["margin_pp"]), 3),
             "area_agreement": {g: round(float(a), 4) for g, a in zip(groups, area)},
             "pooled_area_agreement": round(float(pool["area_agreement"]), 4)},
    "scoring": "refereed pixels only: 1 = crack, 2 or 3 = not-crack, 0 = unreviewed and "
               "excluded from every denominator",
    "scale_provenance": "29.24 nm/px DERIVED from operator-supplied mosaic geometry, not "
                        "read from instrument metadata",
    "source": os.path.basename(PATHS.scoped("txm_background_units.json")),
    "read_with": "docs/figures/txm_paint_free_beam.json -- the B3 row's painted crack "
                 "sits at essentially zero optical density, and most of what the detector "
                 "proposes there comes from the absolute darkness floor",
}, open(os.path.splitext(OUT)[0] + ".caption.json", "w"), indent=1)
print("caption written")
