"""APPROACH 3 -- CONTEXT WITHOUT DEEP LEARNING. Shared machinery.

One definition of every baseline arm, one definition of clDice, one cache. Experiments
import from here so two scripts cannot disagree about what "the shipped model" is.

The arms reproduce scratchpad/run_good/is_it_good.py exactly (that is the table the task
quotes), and selfcheck() asserts the reproduction before anything new is scored:

    arm                            prec  recall      F1     IoU   clDice
    CURRENT MODEL (v1.49.1)      0.4182  0.6252  0.5012  0.3344   0.6405
    one-line global threshold    0.4271  0.6027  0.4999  0.3332   0.6205
    a correct 3 px trace         0.9754  0.2505  0.3987  0.2490   0.9984

clDice is reported as the MEDIAN over tiles, which is how the baseline table was made.
P/R/F1/IoU are pooled over pixels. Both travel together everywhere.
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np

R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
for p in (R, R + "/improve", "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis",
          "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code"):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True

MY = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
      "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/ctx")
os.makedirs(MY, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", MY + "/mpl")

from scipy import ndimage as ndi
from skimage import filters
from skimage.morphology import skeletonize
import tilebench as TB
import detect_cracks as D
import detector_overrides as DO

STRUCT8 = ndi.generate_binary_structure(2, 2)


class _U:
    pass


_UP = _U()
DO.install(_UP)
SEG = _UP.segment_dark_regions          # the shipped v1.49.1 multi-scale union


# --------------------------------------------------------------------- scoring
def cldice(pred, gt):
    """Harmonic mean of (prediction's centreline inside the label) and (label's
    centreline inside the prediction). Width-insensitive on purpose. Identical to the
    definition used to produce the baseline table."""
    pred = np.asarray(pred, bool); gt = np.asarray(gt, bool)
    if not pred.any() or not gt.any():
        return 0.0
    sp, sg = skeletonize(pred), skeletonize(gt)
    tprec = (sp & gt).sum() / max(sp.sum(), 1)
    tsens = (sg & pred).sum() / max(sg.sum(), 1)
    return 0.0 if (tprec + tsens) == 0 else 2 * tprec * tsens / (tprec + tsens)


def cldice_parts(pred, gt):
    pred = np.asarray(pred, bool); gt = np.asarray(gt, bool)
    if not pred.any() or not gt.any():
        return 0.0, 0.0
    sp, sg = skeletonize(pred), skeletonize(gt)
    return float((sp & gt).sum() / max(sp.sum(), 1)), float((sg & pred).sum() / max(sg.sum(), 1))


def row(pred, gt):
    """Everything one tile contributes: pixel counts for the pooled metrics, clDice for
    the median."""
    pred = np.asarray(pred, bool); gt = np.asarray(gt, bool)
    tp, ts = cldice_parts(pred, gt)
    return dict(tp=int((pred & gt).sum()), fp=int((pred & ~gt).sum()),
                fn=int((~pred & gt).sum()), cld=cldice(pred, gt),
                tprec=tp, tsens=ts, area=int(pred.sum()))


def pooled(rows):
    tp = sum(r["tp"] for r in rows); fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    p = tp / max(tp + fp, 1); r_ = tp / max(tp + fn, 1)
    return dict(precision=p, recall=r_, f1=2 * p * r_ / max(p + r_, 1e-12),
                iou=tp / max(tp + fp + fn, 1),
                cldice=float(np.median([r["cld"] for r in rows])),
                cldice_mean=float(np.mean([r["cld"] for r in rows])))


# --------------------------------------------------------------------- the arms
def cand(m):
    """clean_mask(min_area=13) then the production area filter at 40 px. Every arm in the
    baseline table passes through this, so a new arm must too or it is not comparable."""
    lab, _ = ndi.label(D.clean_mask(m, min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel()); k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def correct_trace(gt, width=3):
    sk = skeletonize(gt)
    return ndi.binary_dilation(sk, STRUCT8, iterations=max(0, (width - 1) // 2))


# --------------------------------------------------------------------- cache
_CACHE = {}


def prep(t):
    """Per-tile intermediates every experiment needs: flattened image, denoised copy,
    Frangi ridge response, the shipped mask and the area-matched one-line threshold."""
    k = t["frame"]
    if k in _CACHE:
        return _CACHE[k]
    f = os.path.join(MY, "prep_" + k + ".npz")
    if os.path.exists(f):
        z = np.load(f)
        d = {n: z[n] for n in z.files}
        d["cur"] = d["cur"].astype(bool); d["thr"] = d["thr"].astype(bool)
    else:
        img8 = t["img8"]
        flat = D.flatten_background(img8)
        sm = filters.gaussian(flat, sigma=1.0, preserve_range=True)
        fr = filters.frangi(flat.astype(float), sigmas=range(1, 7), black_ridges=True)
        cur = cand(SEG(flat, img8=img8))
        thr = cand(sm < np.percentile(sm, 100 * float(cur.mean())))
        d = dict(flat=flat.astype(np.float32), sm=sm.astype(np.float32),
                 fr=fr.astype(np.float32), cur=cur, thr=thr)
        np.savez_compressed(f, **d)
    _CACHE[k] = d
    return d


def tiles():
    return TB.load(with_raw=False)


def selfcheck(verbose=True):
    """The baseline table must come back out of this module before anything new is
    believed. Four numbers, to four decimals, from the task statement."""
    ts = tiles()
    want = {"CURRENT MODEL (v1.49.1)": (0.4182, 0.6252, 0.3344, 0.6405),
            "one-line global threshold": (0.4271, 0.6027, 0.3332, 0.6205),
            "a correct 3 px trace": (0.9754, 0.2505, 0.2490, 0.9984)}
    got = {k: [] for k in want}
    for t in ts:
        d = prep(t); gt = t["gt"]
        got["CURRENT MODEL (v1.49.1)"].append(row(d["cur"], gt))
        got["one-line global threshold"].append(row(d["thr"], gt))
        got["a correct 3 px trace"].append(row(correct_trace(gt), gt))
    ok = True
    for k, (p, r, i, c) in want.items():
        m = pooled(got[k])
        bad = (abs(m["precision"] - p) > 5e-4 or abs(m["recall"] - r) > 5e-4
               or abs(m["iou"] - i) > 5e-4 or abs(m["cldice"] - c) > 5e-4)
        ok &= not bad
        if verbose:
            print(f"  {'PASS' if not bad else 'FAIL'}  {k:<28} "
                  f"P {m['precision']:.4f} R {m['recall']:.4f} IoU {m['iou']:.4f} "
                  f"clDice {m['cldice']:.4f}"
                  + ("" if not bad else f"   expected {p} {r} {i} {c}"))
    return ok, got


if __name__ == "__main__":
    print("BASELINE REPRODUCTION (must match the task's table to 4 dp)")
    ok, _ = selfcheck()
    print("\nreproduced" if ok else "\nFAILED -- do not trust anything built on this")
