import sys
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
import tilebench as TB
import numpy as np
from scipy import ndimage as ndi
from skimage import measure
import detect_cracks as D

tiles = TB.load(with_raw=True)
caches = [A.scale_cache(t["img8"]) for t in tiles]
S8 = ndi.generate_binary_structure(2, 2)


def af8(mask, n=40):
    lab, k = ndi.label(mask, structure=S8)
    if not k:
        return mask
    sz = np.bincount(lab.ravel()); keep = sz >= n; keep[0] = False
    return keep[lab]


tot4 = tot8 = diff = 0
for t, c in zip(tiles, caches):
    cl = A.clean(A.union_at(c, t["img8"], 5.0, 10), 1, 3, 13)
    a, b = A.area_filter(cl, 40), af8(cl, 40)
    # what production really produces: labelled regions with >=40 px, 8-connected
    lab, df = D.extract_candidates(cl, np.zeros_like(cl, np.uint8),
                                   np.zeros(cl.shape, np.float64), min_area_px=40)
    prod = lab > 0
    tot4 += int(a.sum()); tot8 += int(b.sum()); diff += int((a ^ b).sum())
    assert np.array_equal(b, prod), t["frame"]
print(f"4-connected filter: {tot4:,} px   8-connected: {tot8:,} px   differ by {diff:,} px")
print("CONTROL 8-connected area_filter == detect_cracks.extract_candidates: PASS (all 26 tiles)")
for nm, f in (("4-conn (what the gate ran)", A.area_filter), ("8-conn (production)", af8)):
    cs = [TB.counts(f(A.clean(A.union_at(c, t["img8"], 5.0, 10), 1, 3, 13), 40), t["gt"])
          for t, c in zip(tiles, caches)]
    m = TB.evaluate("x", {"x": cs}, quiet=True)["loso"]
    print(f"  {nm:<28} P {m['precision']:.4f} R {m['recall']:.4f} IoU {m['iou']:.4f} F1 {m['f1']:.4f}")
