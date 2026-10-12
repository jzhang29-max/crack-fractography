"""WHY are 45.7% of marked crack pixels not dark enough?

Two possibilities with opposite fixes:
  (a) they ARE darker than background, just not by the 5-MAD margin the code demands
      -> a parameter is too tight, and loosening it is the whole fix
  (b) they sit at background level
      -> no intensity threshold can ever find them; the candidate generator needs a
         second, non-intensity channel. Vesselness is already computed, so test it.
Measured separately because they call for completely different work.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
SC = "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad"
os.environ["MPLCONFIGDIR"] = SC + "/mpl"
S = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
sys.path.insert(0, S + "/code"); sys.dont_write_bytecode = True
import numpy as np, tifffile
from PIL import Image
from skimage import exposure, filters
import detect_cracks as D
Image.MAX_IMAGE_PIXELS = None
UP = "/Users/jiamingzhang/Library/Application Support/Crack Fractography/uploads"
ORIG = os.path.join(S, "original"); MACH = os.path.join(S, "crack_export", "derived", "machine_masks")
tiles = [t for t in json.load(open(SC + "/tiles_meta.json")) if t["specimen"] != "MAR_AmbB_AS"]
def as_uint8(a):
    lo, hi = np.percentile(a, [1.0, 99.5])
    return exposure.rescale_intensity(a.astype(np.float32), in_range=(lo, hi), out_range=(0, 255)).astype(np.uint8)

MADK = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
VQ = [0.90, 0.95, 0.975, 0.99]
rows, zmiss, zkept, zbg = [], [], [], []
cap = {f"mad{k}": dict(hit=0, area=0) for k in MADK}
cap["otsu_only"] = dict(hit=0, area=0)
for k in MADK:
    for q in VQ: cap[f"mad{k}+ves{q}"] = dict(hit=0, area=0)
gt_tot = bg_tot = 0
for i, t in enumerate(tiles, 1):
    n, par = t["frame"], t["parent"]; x, y, w, h = t["box"]
    gt = np.array(Image.open(os.path.join(UP, n + "_gated.png")).convert("L")) < 128
    src = next(os.path.join(ORIG, par + e) for e in (".tif", ".tiff", ".png")
               if os.path.exists(os.path.join(ORIG, par + e)))
    mh, mw = np.array(Image.open(os.path.join(MACH, par + "_machine.png"))).shape
    a = tifffile.imread(src)
    if a.ndim == 3: a = a[..., 0]
    if a.shape[1] == mw and a.shape[0] > mh: a = a[:mh, :]
    img8 = as_uint8(a[y:y+h, x:x+w])
    flat = D.flatten_background(img8)
    smooth = filters.gaussian(flat, sigma=1.0, preserve_range=True)
    med = np.median(smooth); mad = np.median(np.abs(smooth - med)) * 1.4826
    z = (smooth - med) / max(mad, 1e-6)               # robust z; crack should be NEGATIVE
    otsu = filters.threshold_otsu(smooth)
    shipped = smooth < min(otsu, med - 5.0 * mad * 1.0) * 1.0
    shipped = (smooth < min(otsu, med - 5.0 * mad)) | (img8 < 10)
    ves = D.compute_vesselness(flat)
    missed = gt & ~shipped
    zmiss.append(z[missed]); zkept.append(z[gt & shipped]); zbg.append(z[~gt][::37])
    gt_tot += int(gt.sum()); bg_tot += int((~gt).sum())
    for k in MADK:
        m = (smooth < min(otsu, med - k * mad)) | (img8 < 10)
        cap[f"mad{k}"]["hit"] += int((gt & m).sum()); cap[f"mad{k}"]["area"] += int((~gt & m).sum())
        for q in VQ:
            vm = m | (ves >= np.quantile(ves, q))
            cap[f"mad{k}+ves{q}"]["hit"] += int((gt & vm).sum()); cap[f"mad{k}+ves{q}"]["area"] += int((~gt & vm).sum())
    om = (smooth < otsu) | (img8 < 10)
    cap["otsu_only"]["hit"] += int((gt & om).sum()); cap["otsu_only"]["area"] += int((~gt & om).sum())
    rows.append(dict(frame=n, specimen=t["specimen"], gt=int(gt.sum()),
                     otsu=float(otsu), robust=float(med - 5 * mad), used="otsu" if otsu < med-5*mad else "robust",
                     z_missed_median=float(np.median(z[missed])) if missed.any() else None,
                     z_kept_median=float(np.median(z[gt & shipped])) if (gt & shipped).any() else None))
    print(f"[{i:>2}/{len(tiles)}] {t['specimen'][:14]:<15} used {rows[-1]['used']:<7} "
          f"z(missed) {rows[-1]['z_missed_median']}", flush=True)
zm, zk, zb = np.concatenate(zmiss), np.concatenate(zkept), np.concatenate(zbg)
json.dump(dict(cap=cap, rows=rows, gt_tot=gt_tot, bg_tot=bg_tot,
               z=dict(missed=[float(np.percentile(zm, p)) for p in (10, 25, 50, 75, 90)],
                      kept=[float(np.percentile(zk, p)) for p in (10, 25, 50, 75, 90)],
                      bg=[float(np.percentile(zb, p)) for p in (10, 25, 50, 75, 90)])),
          open(SC + "/why.json", "w"), indent=1)
print("\nwrote why.json")
