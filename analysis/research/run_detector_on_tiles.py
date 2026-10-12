"""Run the detector ON EACH TILE, and score it against the hand labels.

WHY THIS IS A DIFFERENT EXPERIMENT FROM THE _ascut COMPARISON. `_ascut.png` is the
detector's output computed over the WHOLE 6144x4096 frame and then cropped. Every
constant in that pipeline is global: load_as_uint8 rescales on the 1st/99.5th percentile
of the whole frame, flatten_background subtracts a background estimated over the whole
frame, segment_dark_regions thresholds against whole-frame statistics, and
clean_mask(min_area_px=13) is a fixed pixel area. Run on a 512x512 tile, every one of
those is re-derived from 262,144 pixels instead of 25 million.

So this answers a question the first comparison could not: how does the detector behave
when the tile IS the image -- which is what happens when someone uploads a crop.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
SC = "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad"
os.environ["MPLCONFIGDIR"] = SC + "/mpl"; os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)
S = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
sys.path.insert(0, S + "/code"); sys.dont_write_bytecode = True
import numpy as np, tifffile
from PIL import Image
from skimage import exposure
from scipy import ndimage as ndi
import detect_cracks as D
Image.MAX_IMAGE_PIXELS = None

UP = "/Users/jiamingzhang/Library/Application Support/Crack Fractography/uploads"
ORIG = os.path.join(S, "original"); MACH = os.path.join(S, "crack_export", "derived", "machine_masks")
MODEL = os.path.join(S, "models", "crack_classifier.joblib")
tiles = json.load(open(SC + "/tiles_meta.json"))

def as_uint8(a, low=1.0, high=99.5):
    lo, hi = np.percentile(a, [low, high])
    return exposure.rescale_intensity(a.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)

out = []
for i, t in enumerate(tiles, 1):
    n = t["frame"]; par = t["parent"]; x, y, w, h = t["box"]
    src = next((os.path.join(ORIG, par + e) for e in (".tif", ".tiff", ".png")
                if os.path.exists(os.path.join(ORIG, par + e))), None)
    gt = np.array(Image.open(os.path.join(UP, n + "_gated.png")).convert("L")) < 128
    ascut = np.array(Image.open(os.path.join(UP, n + "_ascut.png")).convert("L")) < 128
    rec = dict(frame=n, specimen=t["specimen"], sample=t["sample"],
               gt=int(gt.sum()), fullframe=int(ascut.sum()))
    try:
        mh, mw = np.array(Image.open(os.path.join(MACH, par + "_machine.png"))).shape
        a = tifffile.imread(src)
        if a.ndim == 3: a = a[..., 0]
        if a.shape[1] == mw and a.shape[0] > mh: a = a[:mh, :]      # databar
        reg = a[y:y+h, x:x+w]
        img8 = as_uint8(reg)
        flat = D.flatten_background(img8)
        dark = D.segment_dark_regions(flat, img8=img8)
        clean = D.clean_mask(dark, min_area_px=13)
        ves = D.compute_vesselness(flat)
        lab, _ = ndi.label(clean)
        labeled, df = D.region_features_from_labeled(lab, flat, ves)
        if len(df):
            sc = D.classify_with_model(df, MODEL)
            keep = np.zeros(labeled.max() + 1, bool)
            for l, k in zip(sc["Label"].values, sc["IsCrack"].values): keep[int(l)] = bool(k)
            pred = keep[labeled]
            rec["n_candidates"] = int(len(df)); rec["n_kept"] = int(sc["IsCrack"].sum())
        else:
            pred = np.zeros_like(gt); rec["n_candidates"] = 0; rec["n_kept"] = 0
        rec["pertile"] = int(pred.sum())
        for tag, p in (("ff", ascut), ("pt", pred)):
            rec[tag+"_tp"] = int((p & gt).sum()); rec[tag+"_fp"] = int((p & ~gt).sum())
            rec[tag+"_fn"] = int((~p & gt).sum()); rec[tag+"_tn"] = int((~p & ~gt).sum())
        np.save(SC + f"/pt_{n[-30:]}.npy", pred)
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    out.append(rec)
    print(f"[{i:>2}/{len(tiles)}] {t['specimen'][:16]:<17} gt {rec['gt']:>7,}  "
          f"full-frame {rec['fullframe']:>7,}  per-tile {rec.get('pertile','ERR'):>7}", flush=True)
json.dump(out, open(SC + "/tilerun.json", "w"), indent=1)
print("\nwrote tilerun.json")
