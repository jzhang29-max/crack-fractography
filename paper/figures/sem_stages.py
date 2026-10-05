"""Real SEM pipeline stages on a frame that LOOKS like a crack network.

Imports the shipped detector rather than reimplementing it, so every panel is the
function the app actually runs. Picks the crop by measurement: a window whose crack
is a NETWORK (many junctions, no single component dominating), because the previous
figure's crop was 91% one blob and read as a pore.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import os, sys, json
import numpy as np
S = _paths.require(_paths.SEM_REPO, "the sem-crack-detector checkout", "SEM_REPO")
sys.path.insert(0, os.path.join(S, "code"))
sys.path.insert(0, os.path.join(S, "interior_active_learning", "code"))
import detect_cracks as D
from skimage import morphology
from scipy import ndimage as ndi
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

FRAME = sys.argv[1] if len(sys.argv) > 1 else "MAR_H_AS_CBS_0004"
OUT = os.path.dirname(os.path.abspath(__file__))

img8 = D.load_as_uint8(f"{S}/original/{FRAME}.tif")
gated = np.asarray(Image.open(f"{S}/crack_export/derived/gated_masks/{FRAME}_gated.png").convert("L")) < 128
mach = np.asarray(Image.open(f"{S}/crack_export/derived/machine_masks/{FRAME}_machine.png").convert("L")) < 128
h = min(img8.shape[0], gated.shape[0], mach.shape[0])
w = min(img8.shape[1], gated.shape[1], mach.shape[1])
img8, gated, mach = img8[:h, :w], gated[:h, :w], mach[:h, :w]
print(f"{FRAME}: {w}x{h}  gated af {gated.mean():.4f}")

# --- crop selection, by measurement -----------------------------------------------
# want: enough crack to see, a skeleton with branches, and NO single component holding
# the crop. The old crop failed the last test.
SIDE = 1200
best = None
for y in range(0, h - SIDE, 200):
    for x in range(0, w - SIDE, 200):
        g = gated[y:y+SIDE, x:x+SIDE]
        af = g.mean()
        if not (0.015 < af < 0.08):
            continue
        lab, n = ndi.label(g)
        if n < 6:
            continue
        sz = np.bincount(lab.ravel())[1:]
        share = sz.max() / sz.sum()
        if share > 0.55:
            continue
        mm = mach[y:y+SIDE, x:x+SIDE]
        chg = int((mm ^ g).sum())
        if chg < 2000:          # the correction panel must have something in it
            continue
        sk = morphology.skeletonize(g)
        score = sk.sum() * (1.0 - share) * min(n, 60) / 60.0
        if best is None or score > best[0]:
            best = (score, y, x, af, n, share, int(sk.sum()), chg)
print("crop:", best)
_, y0, x0, af, n, share, skl, chg = best
sl = (slice(y0, y0+SIDE), slice(x0, x0+SIDE))
sub, g, m = img8[sl], gated[sl], mach[sl]

# --- the shipped stages, called by name ------------------------------------------
flat = D.flatten_background(sub)                      # sigma 40, 0.5-99.5 stretch
dark = D.segment_dark_regions(flat, img8=sub)         # Otsu vs median/MAD, OR absolute
clean = D.clean_mask(dark)                            # open 1, close 3, >=15 px, fill
ves = D.compute_vesselness(flat)                      # Frangi sigmas 1-6, black_ridges

for nm, a in [("img8", sub), ("flat", flat), ("dark", dark), ("clean", clean),
              ("ves", ves), ("gated", g), ("mach", m)]:
    np.save(f"{OUT}/sem_{nm}.npy", a)

stats = dict(
    frame=FRAME, crop=[int(x0), int(y0), SIDE], full=[int(w), int(h)],
    crop_af=float(af), crop_components=int(n), largest_share=float(share),
    skel_px=int(skl),
    raw_crack_dn=float(np.median(sub[g])), raw_matrix_dn=float(np.median(sub[~g])),
    matrix_std_raw=float(sub[~g].std()), matrix_std_flat=float(flat[~g].std()),
    sep_raw_sd=float((np.median(sub[~g])-np.median(sub[g]))/sub[~g].std()),
    sep_flat_sd=float((np.median(flat[~g])-np.median(flat[g]))/flat[~g].std()),
    ves_sep_sd=float((ves[g].mean()-ves[~g].mean())/ves[~g].std()),
    ves_crack=float(ves[g].mean()), ves_matrix=float(ves[~g].mean()),
    dark_frac=float(dark.mean()), clean_frac=float(clean.mean()),
    clean_components=int(ndi.label(clean)[1]),
    mach_frac=float(m.mean()), gated_frac=float(g.mean()),
    removed_px=int((m & ~g).sum()), added_px=int((g & ~m).sum()),
)
print(json.dumps(stats, indent=1))
json.dump(stats, open(f"{OUT}/sem_stats.json", "w"), indent=1)
