"""Two more measurements on the SEM crack classes: classical baselines, and the
constant-width reconstruction curve. Same instruments as the pavement runs."""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from skimage import measure as skm, filters
from skimage.morphology import skeletonize
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None

ROOT = sys.argv[1]
class U: pass
u = U(); DO.install(u)
ST = ndi.generate_binary_structure(2, 2)
WIDTHS = [1, 3, 5, 7, 9, 11, 15, 21, 31, 41]


def clean(m):
    lab = skm.label(D.clean_mask(m, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def f1(p, g):
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return 2 * pr * rc / max(pr + rc, 1e-12)


def ridge(im, sig, q, kind):
    f = {"frangi": filters.frangi, "sato": filters.sato, "meijering": filters.meijering}[kind]
    r = f(im.astype(float), sigmas=sig, black_ridges=True)
    return clean(r >= np.percentile(r, 100 - q))


ARMS = [
    ("YOUR DETECTOR", [5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0],
     lambda im, k: clean(u.segment_dark_regions(D.flatten_background(im), img8=im, mad_k=k))),
    ("global threshold (Otsu on flat)", [0.0],
     lambda im, _: clean(filters.gaussian(D.flatten_background(im), 1, preserve_range=True)
                         < filters.threshold_otsu(filters.gaussian(
                             D.flatten_background(im), 1, preserve_range=True)))),
    ("percentile threshold", [0.5, 1, 2, 4, 8], lambda im, q: clean(im <= np.percentile(im, q))),
    ("Sauvola local", [15, 25, 51, 101],
     lambda im, w: clean(im < filters.threshold_sauvola(im, window_size=w))),
    ("Frangi ridge", [0.5, 1, 2, 4, 8], lambda im, q: ridge(im, range(1, 5), q, "frangi")),
    ("Sato ridge", [0.5, 1, 2, 4, 8], lambda im, q: ridge(im, range(1, 5), q, "sato")),
    ("Meijering ridge", [0.5, 1, 2, 4, 8], lambda im, q: ridge(im, range(1, 5), q, "meijering")),
]


def loo(by, n):
    ks = list(by)
    return float(np.mean([by[max(ks, key=lambda k: np.mean([by[k][j] for j in range(n) if j != i]))][i]
                          for i in range(n)]))


def pairs(cls):
    idir = os.path.join(ROOT, cls, "image_cropped"); mdir = os.path.join(ROOT, cls, "mask_cropped")
    out = []
    for f in sorted(os.listdir(idir)):
        im = np.array(Image.open(os.path.join(idir, f)).convert("L"))
        gt = np.array(Image.open(os.path.join(mdir, f)).convert("L")) > 127
        if gt.sum() >= 50:
            out.append((im, gt))
    return out


BASE, WID = {}, {}
for cls in ("Inconel718_crack", "EBC_crack"):
    data = pairs(cls)
    print(f"\n{cls}: {len(data)} images", flush=True)
    BASE[cls] = {}
    for name, ps, fn in ARMS:
        by = {p: [] for p in ps}
        for im, gt in data:
            for p in ps:
                try:
                    by[p].append(f1(fn(im, p), gt))
                except Exception:
                    by[p].append(0.0)
        v = loo(by, len(data)) if len(ps) > 1 else float(np.mean(by[ps[0]]))
        BASE[cls][name] = v
        print(f"   {name:<34}{v:.4f}", flush=True)
    per_w = {w: [] for w in WIDTHS}; hw = []
    for im, gt in data:
        sk = skeletonize(gt)
        if not sk.any():
            continue
        hw.append(float(np.median(ndi.distance_transform_edt(gt)[sk]) * 2.0))
        for w in WIDTHS:
            t = sk if w <= 1 else ndi.binary_dilation(sk, ST, iterations=max(int(round((w-1)/2)), 1))
            inter = int((t & gt).sum()); union = int((t | gt).sum())
            per_w[w].append(inter / max(union, 1))
    curve = {str(w): float(np.mean(v)) for w, v in per_w.items()}
    bw = max(WIDTHS, key=lambda w: np.mean(per_w[w]))
    WID[cls] = {"n": len(hw), "label_stroke_px_median": float(np.median(hw)),
                "iou_by_trace_width": curve, "ceiling_iou": curve[str(bw)],
                "ceiling_at_width": bw}
    print(f"   label stroke {np.median(hw):.1f} px, best constant-width redraw "
          f"IoU {curve[str(bw)]:.4f} at {bw} px", flush=True)

d = os.path.dirname(os.path.abspath(__file__))
json.dump({"note": "full SEM crack classes, same arms and rule as the pavement run",
           "results": BASE}, open(os.path.join(d, "sem_baselines.json"), "w"), indent=1)
json.dump(WID, open(os.path.join(d, "sem_width_ceiling.json"), "w"), indent=1)
print("\nwrote sem_baselines.json and sem_width_ceiling.json")
