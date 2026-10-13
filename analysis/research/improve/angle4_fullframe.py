"""ANGLE 4, stage 2+3: full-frame precision over REFEREED pixels only, and where the
rest of the "error" lives.

The correction masks give a real three-way split that the tiles cannot:
    1 = hand-marked CRACK       a predicted pixel here is a true positive, refereed
    2 = hand-marked NOT-crack   a predicted pixel here is a false positive, refereed
    3 = ERASED from candidacy   also a human not-crack verdict (pooled with 2)
    0 = UNREVIEWED              no verdict exists. 91% of the corpus.

So three precision numbers, and only the middle one is a measurement:
    P_pess  = tp / (tp + fp2 + fp3 + unreviewed)    every unreviewed px counted as error
    P_ref   = tp / (tp + fp2 + fp3)                 refereed pixels only  <- THE NUMBER
    P_opt   = tp / (tp + fp2 + fp3) with unreviewed also excluded == P_ref by definition;
              the genuine optimistic end is P_pess's complement: (tp + unreviewed) / all,
              i.e. every unreviewed predicted px is crack. Reported as P_credit.

Also recorded per frame, for the FP census in angle4_census.py:
  * a coarse SPECIMEN mask (is the predicted region on the specimen body at all?), with
    its own positive control: it must agree with the human's 1/2 verdicts where those
    exist, or it is not measuring "off-specimen".
  * every predicted connected component, with area, bbox, and its 0/1/2/3 composition, so
    false positives can be sampled size-matched and blind.

Writes only to the scratchpad. The paint is opened read-only and never written.

Run:
    A4OUT=<dir> /Users/.../sem-crack-detector/.venv/bin/python -B \
        analysis/research/improve/angle4_fullframe.py
Env: NFRAMES to limit.
"""
import os, sys, json, time, warnings
warnings.filterwarnings("ignore")
OUT = os.environ.get("A4OUT", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                              "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/angle4")
os.environ.setdefault("MPLCONFIGDIR", OUT + "/mpl")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import numpy as np, tifffile                       # noqa: E402
from scipy import ndimage as ndi                   # noqa: E402
from skimage import exposure, filters              # noqa: E402
from PIL import Image                              # noqa: E402
Image.MAX_IMAGE_PIXELS = None
import angle4_shipped as S                         # noqa: E402  (puts the detector on sys.path)
import detect_cracks as D                          # noqa: E402
from common import contrast_kwargs_for             # noqa: E402

SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
ST8 = np.ones((3, 3), bool)


def load_frame(name):
    """Exactly fullframe_lever4_safety.load_frame: the same stretch, the same FOV crop,
    the same correction-mask alignment. Using a second loader here would make these
    numbers incomparable with the ones the dead rules were measured against."""
    raw = tifffile.imread(os.path.join(SEM, "original", name + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    ck = contrast_kwargs_for(name)
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8, raw = img8[y0:y1, x0:x1], raw[y0:y1, x0:x1]
    corr = np.array(Image.open(os.path.join(PAINT, name + "_correction_mask.png")))
    while corr.ndim > 2:
        corr = corr[..., 0]
    if corr.shape != img8.shape:
        if corr.shape[0] >= y1 and corr.shape[1] >= x1:
            corr = corr[y0:y1, x0:x1]
        else:
            return None
    return img8, raw, corr


def specimen_mask(img8, sigma=25):
    """Coarse "is this on the specimen body" mask.

    Off-specimen background in these micrographs is a large, smooth, dark area that runs
    off the edge of the frame. At a blur radius far larger than any crack's width it
    survives; a crack, however wide, is narrow relative to sigma*4 and gets filled in by
    the blur. Otsu on the blurred image then splits body from background, and the body is
    taken as the union of large bright components with holes filled -- hole filling is
    what makes an enclosed wide crack part of the body rather than a separate object.

    This is deliberately NOT a region-local property: whether a dark area is inside the
    filled body depends on what surrounds it, which is the one discriminator
    unified_pipeline's own comment says nobody has measured.
    """
    b = ndi.gaussian_filter(img8.astype(np.float32), sigma)
    thr = filters.threshold_otsu(b)
    body = b >= thr
    body = ndi.binary_fill_holes(body)
    lab, n = ndi.label(body, structure=ST8)
    if n > 1:                       # keep components that are a real fraction of the frame
        sz = np.bincount(lab.ravel())
        sz[0] = 0
        keep = np.where(sz >= 0.02 * img8.size)[0]
        body = np.isin(lab, keep) if len(keep) else body
    return ndi.binary_fill_holes(body)


def compose(mask, corr):
    return dict(area=int(mask.sum()),
                c1=int((mask & (corr == 1)).sum()), c2=int((mask & (corr == 2)).sum()),
                c3=int((mask & (corr == 3)).sum()), c0=int((mask & (corr == 0)).sum()))


def score(name):
    got = load_frame(name)
    if got is None:
        return dict(frame=name, error="shape_mismatch")
    img8, raw, corr = got
    pred = S.shipped_clean(img8, min_area=15)
    body = specimen_mask(img8)
    rec = dict(frame=name, shape=list(img8.shape),
               corr_counts={str(v): int((corr == v).sum()) for v in (0, 1, 2, 3)},
               pred=compose(pred, corr),
               pred_on_body=compose(pred & body, corr),
               pred_off_body=compose(pred & ~body, corr),
               body_frac=float(body.mean()),
               # positive control for the specimen mask: what share of hand-marked CRACK
               # does it place off-specimen? A good body mask puts nearly none there.
               crack_off_body=int(((corr == 1) & ~body).sum()),
               notc_off_body=int(((corr == 2) & ~body).sum()),
               crack_total=int((corr == 1).sum()), notc_total=int((corr == 2).sum()))
    lab, n = ndi.label(pred, structure=ST8)
    objs = ndi.find_objects(lab)
    comps = []
    if n:
        for i in range(1, n + 1):
            sl = objs[i - 1]
            m = lab[sl] == i
            sub = corr[sl]
            a = int(m.sum())
            comps.append(dict(id=i, area=a,
                              bbox=[int(sl[0].start), int(sl[1].start),
                                    int(sl[0].stop), int(sl[1].stop)],
                              c1=int((m & (sub == 1)).sum()), c2=int((m & (sub == 2)).sum()),
                              c3=int((m & (sub == 3)).sum()), c0=int((m & (sub == 0)).sum()),
                              on_body=int((m & body[sl]).sum())))
    rec["ncomp"] = n
    comps.sort(key=lambda c: -c["area"])
    rec["comps"] = comps[:4000]
    rec["comps_truncated"] = max(0, len(comps) - 4000)
    return rec


def main():
    names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
                   if f.endswith("_correction_mask.png"))
    names = [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
    names = names[:int(os.environ.get("NFRAMES", "0")) or len(names)]
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "fullframe.json")
    print("INSTRUMENT CONTROL (ladder collapse on a real frame)", flush=True)
    img8 = load_frame(names[0])[0]
    S.selfcheck([img8[:1024, :1024]])
    out, t0 = [], time.time()
    for i, n in enumerate(names, 1):
        try:
            r = score(n)
        except Exception as e:
            r = dict(frame=n, error=f"{type(e).__name__}: {e}")
        out.append(r)
        json.dump(out, open(path, "w"))
        if "error" in r:
            print(f"[{i}/{len(names)}] {n:<34} ERROR {r['error']}", flush=True)
            continue
        p = r["pred"]
        ref = p["c1"] + p["c2"] + p["c3"]
        print(f"[{i}/{len(names)}] {n:<34} pred {p['area']:>9,}  "
              f"on-crack {p['c1']:>9,}  on-notc {p['c2'] + p['c3']:>8,}  "
              f"unrev {p['c0']:>9,} ({100 * p['c0'] / max(p['area'], 1):4.1f}%)  "
              f"P_ref {p['c1'] / max(ref, 1):.4f}  {time.time() - t0:5.0f}s", flush=True)
    print(f"\nwrote {path} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
