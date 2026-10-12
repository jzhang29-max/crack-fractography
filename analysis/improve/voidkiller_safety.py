"""Which void-killer, if any, is safe on FULL frames?

The texture veto is already disqualified: it deletes 43.46% of all hand-marked crack on the
frames the repo names, including exactly the 167,607 px its own comment cites for the rule
it removed. The surviving candidate is lever 2's geometric rule -- excise the BODY of a blob
too thick to be a crack (median EDT >= r_big), grown only through pixels still >= r_small
thick so growth cannot run down a thin crack. That is a thickness rule, not a texture rule,
so the repo's "darkness is inverted" counterexample does not automatically apply to it. Its
own auditor still flagged a deletion risk and asked for r_big 50 -> 62.

Test both against the same thing that killed the veto: hand-painted crack on full frames.
Any rule that deletes hand-marked crack is disqualified no matter how it scores on tiles.
"""
import os, sys
import numpy as np
from scipy import ndimage as ndi
from PIL import Image

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code")
sys.dont_write_bytecode = True
import detect_cracks as D
Image.MAX_IMAGE_PIXELS = None
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
STRUCT8 = np.ones((3, 3), bool)
FRAMES = ["260708_316_H_b2_front_CBS_004", "260708_316_H_b2_front_CBS_003",
          "260708_316_H_b2_front_CBS_005", "MAR_Amb_Cast_CBS_0005"]


def local_std(a, r=16):
    a = np.asarray(a, np.float32)
    m = ndi.uniform_filter(a, 2 * r + 1); m2 = ndi.uniform_filter(a * a, 2 * r + 1)
    return np.sqrt(np.maximum(m2 - m * m, 0)).astype(np.float32)


def kill_texture(clean, flat, floor=1.0):
    s = local_std(flat); base = max(float(np.median(s)), 1e-6)
    lab, n = ndi.label(clean)
    if not n:
        return np.zeros_like(clean)
    keep = np.zeros(n + 1, bool); objs = ndi.find_objects(lab)
    for i in range(1, n + 1):
        sl = objs[i - 1]; m = lab[sl] == i
        keep[i] = (float(np.median(s[sl][m])) / base) >= floor
    return (~keep)[lab] & clean


def kill_thick(clean, _flat, r_big=50, r_small=10):
    dt = ndi.distance_transform_edt(clean)
    thick = dt >= r_big
    if not thick.any():
        return np.zeros_like(clean)
    body = ndi.binary_propagation(thick, mask=(dt >= r_small), structure=STRUCT8)
    return ndi.binary_dilation(body, STRUCT8, iterations=r_small) & clean


RULES = [("texture veto floor=1.0", lambda c, f: kill_texture(c, f, 1.0)),
         ("thickness excision r_big=50", lambda c, f: kill_thick(c, f, 50)),
         ("thickness excision r_big=62", lambda c, f: kill_thick(c, f, 62)),
         ("thickness excision r_big=100", lambda c, f: kill_thick(c, f, 100))]

tot = {n: 0 for n, _ in RULES}
marks_tot = 0
print(f"{'frame':<34} {'hand-marked':>12} " + "".join(f"{n.split()[0][:4]+n.split()[-1][:7]:>16}" for n, _ in RULES))
print("-" * 100)
for name in FRAMES:
    cm = os.path.join(PAINT, name + "_correction_mask.png")
    tif = os.path.join(SEM, "original", name + ".tif")
    if not (os.path.exists(cm) and os.path.exists(tif)):
        continue
    img8 = D.load_as_uint8(tif)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]
    corr = np.array(Image.open(cm))
    if corr.ndim == 3:
        corr = corr[..., 0]
    if corr.shape != img8.shape:
        if corr.shape[0] >= y1 and corr.shape[1] >= x1:
            corr = corr[y0:y1, x0:x1]
        else:
            continue
    marked = corr == 1
    flat = D.flatten_background(img8)
    clean = D.clean_mask(D.segment_dark_regions(flat, img8=img8), min_area_px=13)
    marks_tot += int(marked.sum())
    cells = []
    for n, fn in RULES:
        d = int((fn(clean, flat) & marked).sum())
        tot[n] += d
        cells.append(f"{d:>10,} {100*d/max(int(marked.sum()),1):4.1f}%")
    print(f"{name:<34} {int(marked.sum()):>12,} " + "".join(f"{c:>16}" for c in cells))
print("-" * 100)
print(f"{'TOTAL hand-marked crack DELETED':<34} {marks_tot:>12,} "
      + "".join(f"{tot[n]:>10,} {100*tot[n]/max(marks_tot,1):4.1f}%" for n, _ in RULES))
print()
for n, _ in RULES:
    pct = 100 * tot[n] / max(marks_tot, 1)
    print(f"  {'SAFE  ' if pct < 0.5 else 'UNSAFE'}  {n:<30} deletes {pct:.2f}% of hand-marked crack")
