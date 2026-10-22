"""Look at the 42.1% instead of only measuring it.

Every number so far says the labelled crack the detector never proposes is a bright shell
hugging the dark core: grey level 127 against a background of 82 and a core of 59, with
98.5% of it within 10 px of crack that was found. That is the signature of SEM edge
brightening -- the lips of an open crack catch more secondary electrons than the flat
matrix -- but it is equally the signature of a misregistered mask, or of an annotator
banding in a second phase, and no statistic distinguishes those. Panels do.

Each row is one field: the raw micrograph, the annotator's band, and the band split into the
dark core the detector reaches and the bright remainder it cannot. The last column is a grey
level profile across the crack so the core, the lips and the matrix can be read off directly
rather than inferred from a Cohen's d.
"""
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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import ndimage as ndi
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None

FIELDS = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
          "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/"
          "pub_ebc_download/train_subset/Inconel718_crack")
OUT = os.path.join(REPO, "paper/figures/out/missed_shell_panels.png")

plt.rcParams.update({"font.size": 7, "axes.linewidth": 0.6, "font.family": "DejaVu Sans"})


class U:
    pass


u = U()
DO.install(u)


def load():
    mdir = os.path.join(FIELDS, "mask")
    mstem = {os.path.splitext(f)[0]: f for f in os.listdir(mdir)}
    out = []
    for f in sorted(os.listdir(os.path.join(FIELDS, "image"))):
        stem = os.path.splitext(f)[0]
        if stem not in mstem:
            continue
        a = np.array(Image.open(os.path.join(FIELDS, "image", f)))
        im = (a >> 8).astype(np.uint8) if a.dtype == np.uint16 else \
            np.array(Image.open(os.path.join(FIELDS, "image", f)).convert("L"))
        gt = np.array(Image.open(os.path.join(mdir, mstem[stem])).convert("L")) > 127
        if im.shape == gt.shape and gt.sum() >= 50:
            out.append((stem, im, gt))
    return out


data = load()
# the three fields with the most labelled crack, so the panels are not cherry-picked small
# cases; the window is centred on the label's centre of mass, not chosen by eye
data = sorted(data, key=lambda t: -t[2].sum())[:3]
W = 260

fig, axes = plt.subplots(3, 4, figsize=(9.2, 7.0))
for r, (stem, im, gt) in enumerate(data):
    flatv = D.flatten_background(im)
    opened = u.segment_dark_regions(flatv, img8=im, mad_k=0.5, absolute_dark_thresh=0)
    found, missed = gt & opened, gt & ~opened
    cy, cx = ndi.center_of_mass(gt)
    y0 = int(np.clip(cy - W // 2, 0, im.shape[0] - W))
    x0 = int(np.clip(cx - W // 2, 0, im.shape[1] - W))
    sl = (slice(y0, y0 + W), slice(x0, x0 + W))
    I, G, F, M = im[sl], gt[sl], found[sl], missed[sl]

    axes[r, 0].imshow(I, cmap="gray", vmin=0, vmax=255)
    axes[r, 0].set_ylabel(stem, fontsize=6)
    if r == 0:
        axes[r, 0].set_title("raw micrograph", fontsize=7.5)

    axes[r, 1].imshow(I, cmap="gray", vmin=0, vmax=255)
    axes[r, 1].contour(G, levels=[0.5], colors="#1f6feb", linewidths=0.8)
    if r == 0:
        axes[r, 1].set_title("annotator's band", fontsize=7.5)

    ov = np.dstack([I] * 3).astype(float) / 255.0
    ov[F] = [0.10, 0.65, 0.25]     # dark core the detector reaches
    ov[M] = [0.95, 0.35, 0.05]     # the rest of the band
    axes[r, 2].imshow(ov)
    if r == 0:
        axes[r, 2].set_title("green = dark core reached\norange = never reached",
                             fontsize=7.5)

    # a profile across the crack, at the row through the band's centre of mass
    ry = int(np.clip(ndi.center_of_mass(G)[0], 0, W - 1)) if G.any() else W // 2
    prof, inb, inf_, inm = I[ry].astype(float), G[ry], F[ry], M[ry]
    ax = axes[r, 3]
    ax.plot(prof, lw=0.8, color="#333333")
    ax.fill_between(np.arange(W), 0, 255, where=inb, color="#1f6feb", alpha=0.10,
                    label="band" if r == 0 else None)
    ax.fill_between(np.arange(W), 0, 255, where=inf_, color="#1aa64a", alpha=0.35,
                    label="core" if r == 0 else None)
    ax.fill_between(np.arange(W), 0, 255, where=inm, color="#f25c0d", alpha=0.30,
                    label="missed" if r == 0 else None)
    ax.set_ylim(0, 255)
    ax.set_xlim(0, W - 1)
    ax.tick_params(labelsize=5.5)
    if r == 0:
        ax.set_title("grey level across the band", fontsize=7.5)
        ax.legend(fontsize=5.5, loc="upper right", framealpha=0.9)
    ax.set_xlabel("px", fontsize=6)

for a in axes[:, :3].ravel():
    a.set_xticks([]); a.set_yticks([])
fig.suptitle("What the detector never proposes: the bright remainder of the annotator's band",
             fontsize=9)
fig.tight_layout(rect=(0, 0, 1, 0.97))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT, dpi=190)
print("wrote", OUT)
