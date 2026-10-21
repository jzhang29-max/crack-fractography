"""A specificity test, not a crack benchmark.

MetalDAM is SEM of additively-manufactured steel with five-class pixel masks. NONE of its
classes is cracks -- class 4 is "defects, voids and artifacts". So this cannot score crack
detection. What it CAN answer is the question §4 of the paper leaves open: is this
detector a crack detector, or a dark-thing detector?

The measurement is therefore a DECOMPOSITION, not a score. Run the detector at the shipped
setting and ask which labelled class each marked pixel lands on. A crack detector on an
image with no cracks should mark very little; a dark-thing detector should mark the voids
and whatever else is dark.

Caveats carried in the output: the released images are JPEG, so they carry compression
artefacts a darkness threshold can see, and the detector is being run on a material and
magnification (5,000-15,000x) outside anything it was tuned on.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
from skimage import measure as skm
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None

ROOT = sys.argv[1]
class U: pass
u = U(); DO.install(u)
NAMES = {0: "matrix", 1: "austenite", 2: "martensite/austenite", 3: "precipitate",
         4: "defect/void"}


def emit(img8, k=5.0):
    raw = u.segment_dark_regions(D.flatten_background(img8), img8=img8, mad_k=k)
    lab = skm.label(D.clean_mask(raw, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); kk = np.where(sz >= 40)[0]
    return np.isin(lab, kk[kk > 0])


idir, ldir = os.path.join(ROOT, "images"), os.path.join(ROOT, "labels")
marked_by_class = np.zeros(5, np.int64)
total_by_class = np.zeros(5, np.int64)
per_image = []
for f in sorted(os.listdir(idir)):
    stem = os.path.splitext(f)[0]
    lp = os.path.join(ldir, stem + ".png")
    if not os.path.exists(lp):
        continue
    im = np.array(Image.open(os.path.join(idir, f)).convert("L"))
    lb = np.array(Image.open(lp))
    if lb.ndim == 3:
        lb = lb[..., 0]
    # THE RELEASED IMAGES STILL CARRY THE INFORMATION BAND; the labels were cropped of it.
    # 768 rows against 703, and 960 against 895 -- a 65-row databar in both cases, which is
    # what the dataset README means by "after cropping the bottom information band". Trim
    # the image to the label, top-aligned, the same way this project's own loader trims a
    # databar. Without this every image is skipped and the run silently scores nothing.
    if lb.shape != im.shape:
        if im.shape[1] == lb.shape[1] and im.shape[0] > lb.shape[0]:
            im = im[:lb.shape[0], :]
        else:
            print(f"  skip {stem}: image {im.shape} vs label {lb.shape}")
            continue
    m = emit(im)
    for c in range(5):
        cm = lb == c
        total_by_class[c] += int(cm.sum())
        marked_by_class[c] += int((m & cm).sum())
    d = lb == 4
    per_image.append({"frame": stem, "marked_frac": float(m.mean()),
                      "defect_frac": float(d.mean()),
                      "recall_on_defect": float((m & d).sum() / max(d.sum(), 1)),
                      "share_of_marks_on_defect": float((m & d).sum() / max(m.sum(), 1))})

if not per_image:
    raise SystemExit("no image could be paired with its label -- refusing to write a result")
tot_marked = marked_by_class.sum()
print(f"images scored: {len(per_image)}")
print(f"\nthe detector marked {100*tot_marked/total_by_class.sum():.2f}% of all pixels\n")
print(f"{'class':24s} {'% of image':>11s} {'% of marks':>11s} {'recall':>8s} {'enrichment':>11s}")
for c in range(5):
    share_img = total_by_class[c] / total_by_class.sum()
    share_mark = marked_by_class[c] / max(tot_marked, 1)
    rec = marked_by_class[c] / max(total_by_class[c], 1)
    print(f"{NAMES[c]:24s} {100*share_img:10.3f}% {100*share_mark:10.3f}% "
          f"{rec:8.4f} {share_mark/max(share_img,1e-12):10.2f}x")
print("\nenrichment = share of the detector's marks / share of the image. 1.0 is no "
      "preference.")
d = np.array([p["recall_on_defect"] for p in per_image])
s = np.array([p["share_of_marks_on_defect"] for p in per_image])
print(f"\nper image: recall on voids   mean {d.mean():.4f}  median {np.median(d):.4f}")
print(f"           marks on voids    mean {s.mean():.4f}  median {np.median(s):.4f}")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metaldam_specificity.json")
json.dump({"what": "class decomposition of the detector's output on MetalDAM; NOT a crack "
                   "benchmark -- MetalDAM labels no cracks",
           "source": "github.com/ari-dasci/OD-MetalDAM release 1.0, MetalDAM_labeled.zip",
           "caveats": ["released images are JPEG, so a darkness threshold sees compression "
                       "artefacts", "5,000-15,000x, a magnification range the detector was "
                       "never tuned on"],
           "n": len(per_image),
           "class_share_of_image": {NAMES[c]: float(total_by_class[c]/total_by_class.sum())
                                    for c in range(5)},
           "class_share_of_marks": {NAMES[c]: float(marked_by_class[c]/max(tot_marked,1))
                                    for c in range(5)},
           "recall_by_class": {NAMES[c]: float(marked_by_class[c]/max(total_by_class[c],1))
                               for c in range(5)},
           "per_image": per_image}, open(out, "w"), indent=1)
print("\nwrote", out)
