"""PRIMARY GATE for ANGLE 3: every candidate-stage change, against the hand paint.

RESULT, 48 frames, 70,041,625 hand-painted crack px, denominator = the 20,903,694 of them
the shipped v1.49.1 path keeps (the same two figures fullframe_lever4_safety.py reports,
reached by a separate implementation -- the instruments agree):

    arm        kept crack   DELETED     % of kept   frames >1%   notc removed   crack:notc
    shipped    20,903,694         0         0.00%            0              0           --
    filt100    20,629,885   273,809         1.31%           13         30,949        8.8:1
    open2      18,721,773 2,181,921        10.44%           32         39,746       54.9:1
    gridbest   14,104,474 9,502,816        45.46%           26        152,528       62.3:1
    absoff     10,974,693 9,929,001        47.50%           23        112,347       88.4:1
    filt13     21,103,068         0         0.00%            0              0           --
    mk4        23,718,844         0         0.00%            0              0           --

NOTHING PRECISION-MOTIVATED PASSES. The bar is <1% deleted and no concentration. The
mildest precision knob in the whole angle, moving the production feature filter from
40 px to 100 px, deletes 1.31% and concentrates on 13 of 48 frames (worst 6.69%), so it
fails on both clauses -- and it had already failed a sabotage test on the tiles, where
removing a RANDOM HALF of the 40-99 px band it targets buys the same precision for half
the pixels. The three bigger knobs delete 10%, 45% and 48%. Dropping `img8 < 10` destroys
90.0% of MAR_Amb_Cast, 87.1% of Cast_24hr and 81.9% of 260622_316_H_b2, and takes
MAR_Amb_Cast_ETD_0004 and 260622_316_H_b2_back_CBS_01 to 100.0%.

AND THE FULL FRAME CANNOT MEASURE PRECISION AT ALL, which is the finding that closes the
angle. The hand-marked not-crack pool is 429,274 px against 70,041,625 px of crack --
0.61% of the reviewed pool. Precision over reviewed pixels:

    shipped 0.9819   filt100 0.9831   open2 0.9818   gridbest 0.9837   mk4 0.9840
    CONTROL, mark every reviewed pixel                                  0.9939

The information-free predictor beats all five. So the two instruments split the problem
and neither half can answer it: the tiles have a real negative class but structurally
cannot hold a wide-open main crack (ground-truth width tops out at 43.7 px mean against
178 px on frames), and the frames hold the wide cracks but have no negative class to
score against. Any future precision claim here needs hand-marked NOT-crack at frame
scale; until that exists, a precision gain on this corpus is not measurable, let alone
shippable.

THE ADDITIVE ARMS ARE THE ONLY ONES THAT SURVIVE, and they are not precision. filt13 and
mk4 are strict supersets -- 0 px deleted, asserted per frame rather than argued -- and on
full frames they add at purity 0.9985 and 0.9997 against the shipped 0.9819, i.e. they
would raise reviewed precision while adding recall. On the tiles, where the negative class
is real, the same two arms add at purity 0.2601 and 0.3709 against an operating point of
0.4181, i.e. they would LOWER precision. The two instruments rank the same arm in
opposite directions, exactly as they did for the retrained region classifier, and the
0.9985/0.9997 figures are the biased denominator above, not evidence. mk4 is a mad_k
change and belongs to the recall work, not here.

Four precision rules have already died by scoring well on the 512 px tiles and then
deleting hand-painted main crack on full frames, so no tile number in this angle is
evidence until this has run.

    1 = hand-marked CRACK      -> a pixel lost here is a DELETION, the disqualifying harm
    2 = hand-marked NOT-crack  -> a pixel lost here is a real precision gain
    3 = ERASE                  -> also a human not-crack verdict; pooled with 2
    0 = UNREVIEWED             -> excluded from numerator AND denominator. 91% of the
                                  corpus. Counting it as error invents a precision
                                  collapse; counting it as correct invents a win.

The masks under sem-crack-detector/interior_active_learning/paint are irreplaceable hand
labels and are opened READ ONLY. Nothing here writes outside the scratchpad.

ARMS (all share the shipped multi-scale union, taken from detector_overrides.install()):
    shipped      union mad_k=5.0 | img8<10 -> clean(1,3,13) -> feature filter >=40
    absoff       union mad_k=5.0           -> clean(1,3,13) -> feature filter >=40
    filt100      union mad_k=5.0 | img8<10 -> clean(1,3,13) -> feature filter >=100
    gridbest     union mad_k=4.0           -> clean(2,5,13) -> feature filter >=100
                 (the variant that wins the 48-cell knob grid on POOLED tile precision:
                  P 0.6728 vs the shipped 0.4182 at matched recall. Held-out it scores
                  IoU 0.3338 against the shipped 0.3344 -- see angle3 report.)

Run:
    /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python -B \
        analysis/research/improve/angle3_paint_gate.py
Env: NFRAMES to limit, OUT for the json path.
"""
import os, sys, json, time, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
os.environ.setdefault("MPLCONFIGDIR", A.MY + "/mpl")
import numpy as np, tifffile
from scipy import ndimage as ndi
from skimage import exposure, filters, morphology
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
import detect_cracks as D
from common import contrast_kwargs_for

SEM = A.SEM
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
MADKS = (5.0, 4.0)

ARMS = {                 # name -> (mad_k, absolute_dark, open, close, min_area, filter)
    "shipped":  (5.0, 10, 1, 3, 13, 40),
    # --- subtractive relative to shipped: must clear the <1% deletion bar ---
    "absoff":   (5.0,  0, 1, 3, 13, 40),
    "filt100":  (5.0, 10, 1, 3, 13, 100),
    "open2":    (5.0, 10, 2, 3, 13, 40),
    "gridbest": (4.0,  0, 2, 5, 13, 100),
    # --- ADDITIVE: strict supersets of shipped. These cannot delete anything, so the
    # question for them is not safety but PURITY -- a superset raises precision if and
    # only if the pixels it adds are purer than the operating point it adds them to.
    # Measured directly below as added_crack / (added_crack + added_notc) over reviewed
    # pixels only.
    "filt13":   (5.0, 10, 1, 3, 13, 13),
    "mk4":      (4.0, 10, 1, 3, 13, 40),
}
SUPERSETS = ("filt13", "mk4")


def unions(img8):
    """One pass over the ladder, both mad_k values accumulated together.

    Equivalent to calling the shipped segment_dark_regions once per mad_k -- asserted
    against it on a tile in selfcheck() before any frame is scored.
    """
    out = {mk: None for mk in MADKS}
    for sigma in A.DO.SCALE_LADDER:
        f = (D.flatten_background(img8, sigma=40) if sigma == 40
             else A._flatten_like_shipped(img8, sigma))
        sm = filters.gaussian(f, sigma=1.0, preserve_range=True)
        med = float(np.median(sm))
        mad = float(np.median(np.abs(sm - med)) * 1.4826)
        otsu = float(filters.threshold_otsu(sm))
        for mk in MADKS:
            c = sm < min(otsu, med - mk * mad)
            out[mk] = c if out[mk] is None else (out[mk] | c)
        del f, sm
    return out


def arm_mask(uni, img8, spec):
    mk, absd, op, cl, ma, af = spec
    d = uni[mk] | (img8 < absd) if absd else uni[mk]
    return A.area_filter(A.clean(d, open_radius=op, close_radius=cl, min_area=ma), af)


def selfcheck():
    import tilebench as TB
    ok = True
    t = TB.load(with_raw=True)[0]
    u = unions(t["img8"])
    for mk in MADKS:
        ref = A.dark_shipped(t["img8"], mad_k=mk, absolute_dark=0)
        same = np.array_equal(u[mk], ref)
        ok &= same
        print(f"  CONTROL fused union at mad_k={mk} == shipped segment_dark_regions: "
              f"{'PASS' if same else 'FAIL'}")
    ref = A.dark_shipped(t["img8"], mad_k=5.0, absolute_dark=10)
    same = np.array_equal(u[5.0] | (t["img8"] < 10), ref)
    ok &= same
    print(f"  CONTROL absolute term reattaches exactly: {'PASS' if same else 'FAIL'}")
    # a 1-element ladder must reproduce the v1.48 single-scale cut (the repo's own control)
    same = np.array_equal(A.dark_shipped(t["img8"], ladder=(40,)), A.dark_single(t["img8"]))
    ok &= same
    print(f"  CONTROL ladder=(40,) == v1.48 single scale: {'PASS' if same else 'FAIL'}")
    assert ok
    return ok


def load_frame(name):
    raw = tifffile.imread(os.path.join(SEM, "original", name + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    ck = contrast_kwargs_for(name)
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]
    del raw
    corr = np.array(Image.open(os.path.join(PAINT, name + "_correction_mask.png")))
    while corr.ndim > 2:
        corr = corr[..., 0]
    if corr.shape != img8.shape:
        if corr.shape[0] >= y1 and corr.shape[1] >= x1:
            corr = corr[y0:y1, x0:x1]
        else:
            return None
    return img8, corr


def main():
    names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
                   if f.endswith("_correction_mask.png"))
    names = [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
    names = names[:int(os.environ.get("NFRAMES", "0")) or len(names)]
    out_path = os.environ.get("OUT", A.WORK + "/angle3_paint.json")
    print("INSTRUMENT CONTROLS", flush=True)
    selfcheck()
    print(f"\n{len(names)} frames have both a micrograph and a correction mask\n", flush=True)
    out, t0 = [], time.time()
    for i, n in enumerate(names, 1):
        try:
            got = load_frame(n)
        except Exception as e:
            print(f"[{i}/{len(names)}] {n}  ERROR {type(e).__name__}: {e}", flush=True)
            out.append(dict(frame=n, error=f"{type(e).__name__}: {e}"))
            json.dump(out, open(out_path, "w")); continue
        if got is None:
            print(f"[{i}/{len(names)}] {n}  SKIPPED (paint does not fit the image)", flush=True)
            out.append(dict(frame=n, error="shape_mismatch"))
            json.dump(out, open(out_path, "w")); continue
        img8, corr = got
        crack, notc = corr == 1, (corr == 2) | (corr == 3)
        del corr
        uni = unions(img8)
        rec = dict(frame=n, shape=list(img8.shape), painted_crack=int(crack.sum()),
                   painted_notc=int(notc.sum()), arms={})
        ship = None
        for nm, spec in ARMS.items():
            m = arm_mask(uni, img8, spec)
            if nm == "shipped":
                ship = m
            rec["arms"][nm] = dict(area=int(m.sum()), crack=int((m & crack).sum()),
                                   notc=int((m & notc).sum()),
                                   deleted=int((ship & ~m & crack).sum()) if ship is not None else 0,
                                   notc_removed=int((ship & ~m & notc).sum()) if ship is not None else 0,
                                   added_crack=int((m & ~ship & crack).sum()) if ship is not None else 0,
                                   added_notc=int((m & ~ship & notc).sum()) if ship is not None else 0,
                                   added_area=int((m & ~ship).sum()) if ship is not None else 0)
            del m
        out.append(rec)
        k = rec["arms"]["shipped"]["crack"]
        msg = "  ".join(f"{nm} -{100*rec['arms'][nm]['deleted']/max(k,1):5.1f}%"
                        for nm in ARMS if nm != "shipped")
        print(f"[{i}/{len(names)}] {n:<34} painted {rec['painted_crack']:>10,} "
              f"kept {k:>10,} | {msg}  {time.time()-t0:5.0f}s", flush=True)
        json.dump(out, open(out_path, "w"))
        del uni, ship, img8, crack, notc
    json.dump(out, open(out_path, "w"))
    print(f"\nwrote {out_path} in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
