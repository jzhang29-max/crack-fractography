#!/usr/bin/env python3
"""Two plates for the public benchmarks: the scores, and real examples.

Draws only. Every number comes from public_benchmarks.json, written by the measurement
runs in analysis/research/improve/ -- so the plate cannot drift from what was measured.

The example rows use PUBLIC images (CrackForest and DeepCrack), which is the point: this
pair of plates makes the whole public-data argument without showing one micrograph of the
user's own corpus.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REC = json.load(open(os.path.join(HERE, "public_benchmarks.json"), encoding="utf-8"))
SCR = os.environ.get("SCR", "")
INK, MUTED, WARN = "#15181c", "#59606a", "#8a4b00"
BLUE, GREY, ORANGE = "#1f77b4", "#9aa3ad", "#ff7f0e"
MIN_PT = 7.0


def scores():
    D = REC["datasets"]
    names = list(D)
    arms = [("frozen, as shipped (mad_k 5.0)", "5.0", GREY),
            ("mad_k 2.5, fitted on CrackForest", "2.5", BLUE)]
    fig, ax = plt.subplots(figsize=(12.5, 5.4)); fig.patch.set_facecolor("white")
    x = np.arange(len(names)); w = 0.26
    sizes = []
    for i, (lab, k, c) in enumerate(arms):
        v = [D[n]["per_k"][k] for n in names]
        b = ax.bar(x + (i - 1) * w, v, w, label=lab, color=c, edgecolor="white", linewidth=2)
        ax.bar_label(b, fmt="%.3f", fontsize=10, color=INK, padding=2); sizes.append(10)
    v = [D[n]["loo"] for n in names]
    b = ax.bar(x + w, v, w, label="refitted here (leave-one-image-out)", color=ORANGE,
               edgecolor="white", linewidth=2)
    ax.bar_label(b, fmt="%.3f", fontsize=10, color=INK, padding=2)
    for i, n in enumerate(names):
        r = D[n]["random"]
        ax.plot([i - 1.6 * w, i + 1.6 * w], [r, r], color="#c0392b", lw=1.4, ls=":",
                zorder=5)
        ax.text(i + 1.68 * w, r + 0.022, f" random {r:.3f}", fontsize=8.5,
                color="#c0392b", va="center"); sizes.append(8.5)
        p = D[n].get("published")
        if p:
            ax.plot([i - 1.6 * w, i + 1.6 * w], [p["f1"], p["f1"]], color=INK, lw=1.4,
                    ls="--", zorder=5)
            # placed to the RIGHT of its own group, not centred on it: centred, it ran
            # straight through the legend
            ax.text(i + 1.68 * w, p["f1"], f" published (trained on it) {p['f1']:.3f}",
                    fontsize=9, color=INK, ha="left", va="center"); sizes.append(9)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{n}\n{D[n]['n']} images, {100*D[n]['prevalence']:.2f}% crack"
                        for n in names], fontsize=11); sizes.append(11)
    ax.set_ylabel("mean F1 per image, 0 px tolerance", fontsize=11)
    ax.set_ylim(0, 1.0)
    ax.legend(fontsize=10, frameon=False, loc="upper left", ncol=3,
              bbox_to_anchor=(0, 1.13)); sizes.append(10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e8ebee", lw=0.8); ax.set_axisbelow(True)
    fig.tight_layout()
    p = os.path.join(HERE, "fig_public_scores.png")
    fig.savefig(p, dpi=170); plt.close(fig)
    assert min(sizes) >= MIN_PT
    return p


def examples():
    """One row per dataset: image, ground truth, frozen, and at mad_k 2.5."""
    sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
    sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code")
    import warnings
    warnings.filterwarnings("ignore")
    from PIL import Image
    from scipy import ndimage as ndi
    from skimage import measure as skm
    import scipy.io as sio
    import detect_cracks as D
    import detector_overrides as DO

    class U:
        pass

    u = U(); DO.install(u)

    def emit(img8, k):
        raw = u.segment_dark_regions(D.flatten_background(img8), img8=img8, mad_k=k)
        lab = skm.label(D.clean_mask(raw, min_area_px=13), connectivity=2)
        if not lab.max():
            return np.zeros(lab.shape, bool)
        sz = np.bincount(lab.ravel()); kk = np.where(sz >= 40)[0]
        return np.isin(lab, kk[kk > 0])

    def f1q(p, g):
        tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
        pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
        return 2 * pr * rc / max(pr + rc, 1e-12)

    def pick(cands):
        """THE IMAGE IS CHOSEN BY A RULE, NOT BY EYE. The one whose mad_k 2.5 score is
        nearest that dataset's own mean for that arm, so the panel shows typical
        behaviour. The first draft of this plate hand-picked CrackForest 005, where
        frozen scores 0.721 against 2.5's 0.478 -- the reverse of the aggregate, and a
        reader would have taken the exception for the rule."""
        scored = []
        for lab, img, gt in cands:
            scored.append((abs(f1q(emit(img, 2.5), gt) - target), lab, img, gt))
        scored.sort(key=lambda t: t[0])
        return scored[0][1:]

    rows = []
    cfd = f"{SCR}/pub_cfd/CrackForest-dataset-master"
    if os.path.isdir(cfd):
        target = REC["datasets"]["CrackForest"]["per_k"]["2.5"]
        cands = []
        for n in [f"{i:03d}" for i in range(1, 40)]:
            ip = f"{cfd}/image/{n}.jpg"; gp = f"{cfd}/groundTruth/{n}.mat"
            if not (os.path.exists(ip) and os.path.exists(gp)):
                continue
            img = np.array(Image.open(ip).convert("L"))
            gt = np.array(sio.loadmat(gp)["groundTruth"][0, 0]["Segmentation"]) == 2
            if gt.sum() > 50:
                cands.append((f"CrackForest {n}", img, gt))
        if cands:
            rows.append(pick(cands))
    dc = f"{SCR}/pub_deepcrack/DeepCrack-master/dataset"
    if os.path.isdir(dc + "/test_img"):
        target = REC["datasets"]["DeepCrack"]["per_k"]["2.5"]
        cands = []
        for f in sorted(os.listdir(dc + "/test_img"))[:40]:
            gp = f"{dc}/test_lab/{os.path.splitext(f)[0]}.png"
            if not os.path.exists(gp):
                continue
            img = np.array(Image.open(f"{dc}/test_img/{f}").convert("L"))
            gt = np.array(Image.open(gp).convert("L")) > 127
            if gt.sum() > 50:
                cands.append((f"DeepCrack {os.path.splitext(f)[0]}", img, gt))
        if cands:
            rows.append(pick(cands))
    if not rows:
        raise SystemExit("no public images available -- refusing to draw an empty plate")

    def f1(p, g):
        tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
        pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
        return 2 * pr * rc / max(pr + rc, 1e-12)

    fig, axes = plt.subplots(len(rows), 4, figsize=(13, 3.4 * len(rows)))
    fig.patch.set_facecolor("white")
    axes = np.atleast_2d(axes)
    for r, (lab, img, gt) in enumerate(rows):
        m5, m25 = emit(img, 5.0), emit(img, 2.5)
        panels = [(img, f"{lab}\n(typical: nearest this dataset's mean)", None),
                  (img, f"ground truth  ({100*gt.mean():.2f}% of pixels)", (gt, "#2ca02c")),
                  (img, f"frozen, mad_k 5.0   F1 {f1(m5, gt):.3f}", (m5, "#c0392b")),
                  (img, f"mad_k 2.5   F1 {f1(m25, gt):.3f}", (m25, BLUE))]
        for c, (base, title, ov) in enumerate(panels):
            ax = axes[r, c]
            ax.imshow(base, cmap="gray"); ax.axis("off")
            if ov is not None:
                mask, col = ov
                rgba = np.zeros(mask.shape + (4,))
                rgba[..., :3] = matplotlib.colors.to_rgb(col)
                rgba[..., 3] = mask * 0.75
                ax.imshow(rgba)
            ax.set_title(title, fontsize=9.5, color=INK, pad=4)
    fig.tight_layout()
    p = os.path.join(HERE, "fig_public_examples.png")
    fig.savefig(p, dpi=150); plt.close(fig)
    return p


if __name__ == "__main__":
    for p in (scores(), examples()):
        print(f"wrote {p}  ({os.path.getsize(p)/1024:.0f} KB)")
