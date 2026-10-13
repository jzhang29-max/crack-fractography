"""Are the pixels absolute_dark 10->20 adds CRACKS or PORES? Decide it without labels.

The two label sets disagree 9x on this band's purity (tiles 9.9%, frames 91.6%) and both
may be right about the same pixels: the tiles say the labeller did not paint them, the
frames say they fall inside paint whose own median width is 192 px and which therefore
sweeps up whatever sits beside a crack. Neither answers whether the pixels are crack.

Shape does, and needs no label. This project already separates the two that way:
MAR_AmbB_AS was excluded from scoring because 87% of its painted area is ROUND -- median
elongation 1.51 against 3.27 elsewhere -- i.e. porosity. So measure the elongation of the
regions this change adds, against the regions already kept on the same frames.
"""
import os, sys
import numpy as np
from scipy import ndimage as ndi
from skimage import measure as skm

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code")
sys.dont_write_bytecode = True
import detect_cracks as D
import detector_overrides as DO
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
PAINT = os.path.join(SEM, "interior_active_learning", "paint")


def arm(t):
    class U:
        pass
    u = U(); DO.install(u, absolute_dark_thresh=t); return u


u10, u20 = arm(10), arm(20)


def regions(m, minpx=40):
    lab, n = ndi.label(m, structure=np.ones((3, 3), bool))
    out = []
    for p in skm.regionprops(lab):
        if p.area < minpx:
            continue
        mn = p.axis_minor_length
        out.append((p.area, p.axis_major_length / mn if mn > 1e-6 else np.inf))
    return out


names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
               if f.endswith("_correction_mask.png"))
names = [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
LIMIT = int(os.environ.get("NFRAMES", "14"))
kept_e, added_e = [], []
kept_a, added_a = [], []
done = 0
for n in names:
    if done >= LIMIT:
        break
    try:
        img8 = D.load_as_uint8(os.path.join(SEM, "original", n + ".tif"))
        x0, y0, x1, y1 = D.find_field_of_view(img8); img8 = img8[y0:y1, x0:x1]
        flat = D.flatten_background(img8)
        a = D.clean_mask(u10.segment_dark_regions(flat, img8=img8), min_area_px=13)
        b = D.clean_mask(u20.segment_dark_regions(flat, img8=img8), min_area_px=13)
        add = b & ~a
        if int(add.sum()) < 20000:
            continue
        ke, ae = regions(a), regions(add)
        if not ae:
            continue
        kept_e += [e for _, e in ke]; added_e += [e for _, e in ae]
        kept_a += [x for x, _ in ke]; added_a += [x for x, _ in ae]
        done += 1
        print(f"  {n[:44]:<46} kept {len(ke):>5} regions (med elong {np.median([e for _,e in ke]):5.2f})"
              f"   ADDED {len(ae):>5} (med elong {np.median([e for _,e in ae]):5.2f})", flush=True)
    except Exception as e:
        print(f"  {n[:40]} ERROR {type(e).__name__}: {e}", flush=True)

ke, ae = np.array(kept_e), np.array(added_e)
ka, aa = np.array(kept_a), np.array(added_a)
print(f"\nPOOLED over {done} frames")
print(f"  {'':<22} {'n regions':>10} {'median elong':>13} {'p25':>7} {'p75':>7} {'median area':>12}")
print(f"  {'already kept (t=10)':<22} {len(ke):>10,} {np.median(ke):13.2f} "
      f"{np.percentile(ke,25):7.2f} {np.percentile(ke,75):7.2f} {np.median(ka):12.0f}")
print(f"  {'ADDED by t=20':<22} {len(ae):>10,} {np.median(ae):13.2f} "
      f"{np.percentile(ae,25):7.2f} {np.percentile(ae,75):7.2f} {np.median(aa):12.0f}")
print(f"\n  reference from this project: painted CRACK median elongation 3.27,")
print(f"                               painted POROSITY (MAR_AmbB_AS) median 1.51")
print(f"  share of ADDED regions below elongation 2.0 (pore-like): {100*(ae<2).mean():.1f}%")
print(f"  share of KEPT  regions below elongation 2.0:             {100*(ke<2).mean():.1f}%")
w_add = float(np.sum(aa[ae < 2]) / max(np.sum(aa), 1))
print(f"  share of ADDED AREA in pore-like (elong<2) regions:      {100*w_add:.1f}%")
