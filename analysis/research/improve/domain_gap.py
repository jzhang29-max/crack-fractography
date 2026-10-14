"""WHY does the SEM detector only half-work on TXM, and what would have to change?

Already established, not re-derived: on 31 TXM frames with correction masks every SEM model
version ties (F1 0.3635-0.3755), precision 0.2602 against a no-information floor of 0.0810 --
a 3.2x lift, so the darkness cut DOES transfer, weakly. Plain Otsu reaches 1.09x.

This measures the mechanism in units that imply a fix. Every constant in this detector is in
PIXELS: flatten radii 5..320, min_area 13, the 40 px region floor, mad_k=5.0 against the
background's own MAD. If a TXM crack is a different number of pixels wide than an SEM one,
the detector is simply mis-scaled and the remedy is a resolution-matched ladder -- which is
testable, not a hypothesis to assert.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
TXM = "/Users/jiamingzhang/Desktop/APP/TXM_Crack_Detection_Pipeline"
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from skimage import filters
from skimage.morphology import skeletonize
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None
PAINT_S = os.path.join(SEM, "interior_active_learning", "paint")
PAINT_T = os.path.join(TXM, "paint", "corrections")


def arm(**kw):
    class U:
        pass
    u = U(); DO.install(u, **kw); return u


def widths(paint, cap=40):
    """2 x the EDT on the skeleton = local thickness, per component, area-weighted."""
    lab, n = ndi.label(paint, structure=np.ones((3, 3), bool))
    dt = ndi.distance_transform_edt(paint)
    ws, ar = [], []
    objs = ndi.find_objects(lab)
    for i in range(1, min(n, 4000) + 1):
        sl = objs[i - 1]
        m = lab[sl] == i
        if m.sum() < 60:
            continue
        sk = skeletonize(m)
        if sk.any():
            ws.append(2 * float(dt[sl][sk].mean())); ar.append(int(m.sum()))
    return np.array(ws), np.array(ar)


def contrast(img8, paint):
    """Cohen's d of crack vs matrix on the 8-bit image, and the sign."""
    c = img8[paint].astype(float)
    bg = img8[~ndi.binary_dilation(paint, iterations=12)].astype(float)
    if len(c) < 100 or len(bg) < 100:
        return None
    bg = bg[::max(1, len(bg) // 400000)]
    sp = np.sqrt((c.var() + bg.var()) / 2)
    return dict(crack=float(c.mean()), matrix=float(bg.mean()),
                d=float((bg.mean() - c.mean()) / max(sp, 1e-9)))


def madstats(img8):
    flat = D.flatten_background(img8)
    sm = filters.gaussian(flat, sigma=1.0, preserve_range=True)
    med = float(np.median(sm)); mad = float(np.median(np.abs(sm - med)) * 1.4826)
    return dict(med=med, mad=mad, bar=med - 5.0 * mad,
                otsu=float(filters.threshold_otsu(sm)))


def survey(name, files, loader, nmax):
    W, A, Ds, Ms, px = [], [], [], [], []
    for k, (stem, imgp, pp) in enumerate(files[:nmax], 1):
        try:
            img8, paint = loader(imgp, pp)
            if paint is None or int(paint.sum()) < 20000:
                continue
            w, a = widths(paint)
            if len(w):
                W.append(w); A.append(a)
            c = contrast(img8, paint)
            if c:
                Ds.append(c)
            Ms.append(madstats(img8)); px.append(img8.size)
            print(f"   {name} [{k}] {stem[:44]:<46} med width {np.median(w) if len(w) else float('nan'):6.1f} px", flush=True)
        except Exception as e:
            print(f"   {name} [{k}] {stem[:40]} ERR {type(e).__name__}", flush=True)
    W = np.concatenate(W) if W else np.array([]); A = np.concatenate(A) if A else np.array([])
    return dict(w_med=float(np.median(W)) if len(W) else None,
                w_p25=float(np.percentile(W, 25)) if len(W) else None,
                w_p75=float(np.percentile(W, 75)) if len(W) else None,
                w_awt=float(np.average(W, weights=A)) if len(W) else None,
                n_regions=int(len(W)),
                d_med=float(np.median([x["d"] for x in Ds])) if Ds else None,
                crack_dn=float(np.median([x["crack"] for x in Ds])) if Ds else None,
                matrix_dn=float(np.median([x["matrix"] for x in Ds])) if Ds else None,
                mad_med=float(np.median([x["mad"] for x in Ms])) if Ms else None,
                med_med=float(np.median([x["med"] for x in Ms])) if Ms else None)


def sem_loader(imgp, pp):
    img8 = D.load_as_uint8(imgp)
    x0, y0, x1, y1 = D.find_field_of_view(img8); img8 = img8[y0:y1, x0:x1]
    a = np.array(Image.open(pp)); a = a[..., 0] if a.ndim == 3 else a
    if a.shape != img8.shape:
        if a.shape[0] >= y1 and a.shape[1] >= x1:
            a = a[y0:y1, x0:x1]
        else:
            return img8, None
    return img8, a == 1


def txm_loader(imgp, pp):
    img8 = D.load_as_uint8(imgp)
    a = np.load(pp)
    return (img8, a == 1) if a.shape == img8.shape else (img8, None)


semf = [(f[:-len("_correction_mask.png")],
         os.path.join(SEM, "original", f[:-len("_correction_mask.png")] + ".tif"),
         os.path.join(PAINT_S, f))
        for f in sorted(os.listdir(PAINT_S)) if f.endswith("_correction_mask.png")]
semf = [x for x in semf if os.path.exists(x[1])]
txmf = [(f[:-len("_correction.npy")],
         os.path.join(TXM, "images", f[:-len("_correction.npy")] + ".tif"),
         os.path.join(PAINT_T, f))
        for f in sorted(os.listdir(PAINT_T)) if f.endswith("_correction.npy")]
txmf = [x for x in txmf if os.path.exists(x[1])]
print(f"SEM frames with paint: {len(semf)}   TXM frames with paint: {len(txmf)}\n")
S = survey("SEM", semf, sem_loader, 14)
print()
T = survey("TXM", txmf, txm_loader, 14)

print("\n" + "=" * 86)
print("THE DOMAIN GAP, MEASURED")
print(f"  {'':<34} {'SEM':>14} {'TXM':>14}   ratio")
def row(lab, a, b, fmt="{:14.2f}"):
    r = (b / a) if (a and b) else float("nan")
    print(f"  {lab:<34} " + fmt.format(a if a else float('nan')) + fmt.format(b if b else float('nan')) + f"   {r:6.2f}x")
row("painted crack width, median px", S["w_med"], T["w_med"])
row("  area-weighted mean px", S["w_awt"], T["w_awt"])
row("  p25 px", S["w_p25"], T["w_p25"])
row("  p75 px", S["w_p75"], T["w_p75"])
row("crack DN (8-bit)", S["crack_dn"], T["crack_dn"])
row("matrix DN (8-bit)", S["matrix_dn"], T["matrix_dn"])
row("contrast, Cohen's d (matrix-crack)", S["d_med"], T["d_med"])
row("background MAD after flattening", S["mad_med"], T["mad_med"])
row("flattened median", S["med_med"], T["med_med"])
print(f"\n  regions measured: SEM {S['n_regions']:,}  TXM {T['n_regions']:,}")
json.dump(dict(sem=S, txm=T), open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "gap.json"), "w"), indent=1)
print("\n  -> if the width ratio is far from 1.0, every pixel-denominated constant is mis-scaled")
