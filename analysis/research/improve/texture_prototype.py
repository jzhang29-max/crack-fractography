"""A texture channel for the crack interior, scored honestly and against decoys.

What the missing 42.1% is: the lit, rough fracture surface inside a wide-open crack. It is
brighter than matrix (127 vs 82), so no darkness threshold reaches it, and it is a wide
region rather than a thin line, which is why adding a ridge filter bought so little.

Local roughness separates it from matrix at AUC 0.991 -- but that AUC sampled matrix twelve
pixels clear of the label, which throws away every hard negative in the image. Grain
boundaries, scratches, precipitates and polishing debris are all rough, and a texture channel
that marks them is useless however well it scores against clean matrix. So the claim is
tested here as a detector, on whole images, with the whole image as the negative set.

The mechanism is the constraint. The lit fracture surface ADJOINS the shadowed void -- that
is why it is visible at all -- so rough material counts only where it is connected to a dark
seed the existing detector already found. Rough material elsewhere is rejected. That makes it
a reading of the image rather than a widening of the answer, which is the distinction every
previous attempt here has failed.

DECOYS, all at matched parameter count and the same selection rule:
  wrong-image texture  the roughness map of a different field. Same statistics, wrong place.
  texture unconnected  the same roughness cut with the connectivity constraint removed, to
                       show the constraint is doing the work rather than the filter.
  equal-area dilation  the seed grown to the same area, carrying no information at all. This
                       is the decoy that beat the ridge filter and it has to be beaten here.

Reported as a pixel budget first -- labelled%, marked%, right%, wrong% -- with precision,
recall, F1 and IoU beside it, because an arm that wins on F1 while doubling the reported
crack area fraction is not an improvement to this tool.
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
sys.path.insert(0, os.path.join(REPO, "analysis"))
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from skimage import measure as skm, morphology as morph
from PIL import Image
import detect_cracks as D
import detector_overrides as DO
Image.MAX_IMAGE_PIXELS = None

SCR = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad")
FIELDS = os.path.join(SCR, "pub_ebc_download/train_subset/Inconel718_crack")
CROPS = os.path.join(SCR, "pub_ebc_download/extracted/testsem/Inconel718_crack")
SDW = 15          # roughness window, fixed by the AUC sweep, not tuned per image
MADK = 5.0        # the shipped constant, unchanged


class U:
    pass


u = U()
DO.install(u)


def clean(m):
    lab = skm.label(D.clean_mask(m, min_area_px=13), connectivity=2)
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel())
    k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def local_sd(im, w=SDW):
    f = im.astype(np.float32)
    m = ndi.uniform_filter(f, w)
    m2 = ndi.uniform_filter(f * f, w)
    return np.sqrt(np.maximum(m2 - m * m, 0))


def budget(p, g):
    p, g = np.asarray(p, bool), np.asarray(g, bool)
    n = p.size
    tp = int((p & g).sum()); fp = int((p & ~g).sum()); fn = int((~p & g).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    lab_pct, mark_pct = 100.0 * g.sum() / n, 100.0 * p.sum() / n
    return {"labelled_pct": lab_pct, "marked_pct": mark_pct,
            "tp_pct": 100.0 * tp / n, "fp_pct": 100.0 * fp / n,
            "area_ratio": mark_pct / lab_pct if lab_pct else float("nan"),
            "area_err_pp": abs(mark_pct - lab_pct),
            "precision": pr, "recall": rc,
            "f1": 2 * pr * rc / max(pr + rc, 1e-12),
            "iou": tp / max(tp + fp + fn, 1)}


def mean_width(m):
    m = np.asarray(m, bool)
    L = int(morph.skeletonize(m).sum())
    return (m.sum() / L) if L else float("nan")


def load_fields():
    mdir = os.path.join(FIELDS, "mask")
    mstem = {os.path.splitext(f)[0]: f for f in os.listdir(mdir)}
    out = []
    for f in sorted(os.listdir(os.path.join(FIELDS, "image"))):
        stem = os.path.splitext(f)[0]
        if stem not in mstem:
            continue
        a = np.array(Image.open(os.path.join(FIELDS, "image", f)))
        im = (a >> 8).astype(np.uint8) if a.dtype == np.uint16 else \
            np.array(Image.open(os.path.join(FIELDS, "image", f)).convert("L"))
        gt = np.array(Image.open(os.path.join(mdir, mstem[stem])).convert("L")) > 127
        if im.shape == gt.shape and gt.sum() >= 50:
            out.append((im, gt))
    return out


def load_crops():
    idir, mdir = os.path.join(CROPS, "image_cropped"), os.path.join(CROPS, "mask_cropped")
    out = []
    for f in sorted(os.listdir(idir)):
        im = np.array(Image.open(os.path.join(idir, f)).convert("L"))
        gt = np.array(Image.open(os.path.join(mdir, f)).convert("L")) > 127
        if im.shape == gt.shape and gt.sum() >= 50:
            out.append((im, gt))
    return out


def run(name, loader):
    data = loader()
    n = len(data)
    print(f"\n{'=' * 100}\n{name}: {n} images\n{'=' * 100}", flush=True)
    seeds, sds = [], []
    for im, _ in data:
        seeds.append(clean(u.segment_dark_regions(D.flatten_background(im), img8=im,
                                                  mad_k=MADK)))
        sds.append(local_sd(im))

    QS = (2, 4, 8, 16, 32)          # the roughness cut, as a top-q% of the SD map
    DIL = (1, 2, 3, 4, 5)           # matched-size grid for the dilation decoy

    def rough(i, q):
        return sds[i] >= np.percentile(sds[i], 100 - q)

    def attached(i, q, src=None):
        """Rough material only where it touches a dark seed."""
        r = rough(src if src is not None else i, q)
        return clean(ndi.binary_propagation(seeds[i], mask=seeds[i] | r))

    ARMS = {
        "shipped detector": ([None], lambda i, p: seeds[i], 1),
        "+ TEXTURE attached to seed": (QS, lambda i, p: attached(i, p), 2),
        "decoy: WRONG-IMAGE texture": (QS, lambda i, p: attached(i, p, (i + 1) % n), 2),
        "decoy: texture UNCONNECTED": (QS, lambda i, p: clean(seeds[i] | rough(i, p)), 2),
        "decoy: equal-area DILATION": (DIL, lambda i, p: clean(
            ndi.binary_dilation(seeds[i], iterations=p)), 2),
    }

    out = {}
    for nm, (grid, fn, npar) in ARMS.items():
        by, wid = {}, {}
        for p in grid:
            rows, ws = [], []
            for i in range(n):
                m = fn(i, p)
                rows.append(budget(m, data[i][1]))
                ws.append(mean_width(m))
            by[p], wid[p] = rows, ws
        if len(grid) == 1:
            picks = [(grid[0], i) for i in range(n)]
            picks_a = picks
        else:
            picks = [(max(grid, key=lambda p: np.mean(
                [by[p][j]["f1"] for j in range(n) if j != i])), i) for i in range(n)]
            picks_a = [(min(grid, key=lambda p: np.mean(
                [by[p][j]["area_err_pp"] for j in range(n) if j != i])), i)
                for i in range(n)]
        gw = [mean_width(g) for _, g in data]

        def agg(pk):
            a = {k: float(np.mean([by[p][i][k] for p, i in pk])) for k in by[grid[0]][0]}
            w = [wid[p][i] for p, i in pk]
            ok = [j for j in range(n) if not (np.isnan(w[j]) or np.isnan(gw[j]))]
            a["width_ratio"] = float(np.mean([w[j] for j in ok])
                                     / np.mean([gw[j] for j in ok])) if ok else float("nan")
            return a
        out[nm] = {"free_params": npar, "sel_by_f1": agg(picks),
                   "sel_by_area": agg(picks_a)}

    lab = out["shipped detector"]["sel_by_f1"]["labelled_pct"]
    for sel, title in (("sel_by_f1", "parameter chosen by F1"),
                       ("sel_by_area", "parameter chosen by area-fraction error")):
        print(f"\n  PIXEL BUDGET, % of image. Labelled crack {lab:.3f}%. {title}.\n")
        print(f"  {'arm':30s} {'pp':>3s} {'marked%':>8s} {'right%':>8s} {'wrong%':>8s} "
              f"{'ratio':>6s} {'width':>6s} {'prec':>6s} {'recall':>6s} {'F1':>6s} {'IoU':>6s}")
        for nm in ARMS:
            a = out[nm][sel]
            print(f"  {nm:30s} {out[nm]['free_params']:3d} {a['marked_pct']:8.3f} "
                  f"{a['tp_pct']:8.3f} {a['fp_pct']:8.3f} {a['area_ratio']:6.2f} "
                  f"{a['width_ratio']:6.2f} {a['precision']:6.3f} {a['recall']:6.3f} "
                  f"{a['f1']:6.3f} {a['iou']:6.3f}")

    t = out["+ TEXTURE attached to seed"]["sel_by_f1"]
    s = out["shipped detector"]["sel_by_f1"]
    print(f"\n  TEXTURE vs shipped        F1 {t['f1'] - s['f1']:+.4f}   "
          f"area ratio {s['area_ratio']:.2f}x -> {t['area_ratio']:.2f}x")
    for d in ("decoy: WRONG-IMAGE texture", "decoy: texture UNCONNECTED",
              "decoy: equal-area DILATION"):
        print(f"  TEXTURE vs {d[7:]:28s} F1 "
              f"{t['f1'] - out[d]['sel_by_f1']['f1']:+.4f}")
    return out


RES = {"whole_fields": run("WHOLE FIELDS (the primary set)", load_fields),
       "crops": run("RELEASED CROPS", load_crops)}
p = os.path.join(REPO, "docs/figures/texture_prototype.json")
json.dump({"sd_window_px": SDW, "mad_k": MADK, "sets": RES,
           "mechanism": "rough material counts as crack only where connected to a dark "
                        "seed, because the lit fracture surface adjoins the shadowed void",
           "decoys": "wrong-image texture, texture without the connectivity constraint, "
                     "and an equal-area dilation that carries no information"},
          open(p, "w"), indent=1)
print("\nwrote", p)
