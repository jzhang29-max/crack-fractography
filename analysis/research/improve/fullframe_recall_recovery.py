"""HOW MUCH OF THE 70.2% IS RECOVERABLE, and is any of it worth taking?

fullframe_recall_decomposition.py established WHERE the loss is: of the 49,118,227
hand-painted crack pixels the candidate stage never proposes on the 48 frames with a
correction mask, 96.02% are not dark at ANY radius on v1.49's ladder. clean_mask's
small-object filter is 2.30%, its opening 1.19%, the min_area_px=40 candidate filter
0.49%. So morphology and the area filters are 4% of the problem and the darkness cut is
all of it. This measures the three ways the darkness cut could be opened up, on the same
48 frames, through the same instrument, with the cost measured and not assumed.

  abs<t     The absolute test `img8 < 10` already carries HALF of all recall: 13,907,547
            of the 20,923,398 painted crack pixels proposed, 10,516,306 of them found by
            that term and no ladder rung. It is a hard constant with no provenance in this
            repo and nobody has swept it. t in (20, 30, 50).
  mad_k     The relative bar, swept on the same instrument for comparison.
  float     The relative bar is UNREACHABLE on 56 of the 336 frame-rungs: flatten_background
            rescales the residual onto 0..255 by its 0.5/99.5 percentiles, which fixes the
            flattened image's MAD at 24-43 grey levels, so `med - 5*mad` lands at a
            NEGATIVE value that a uint8 image cannot take and the rung proposes nothing at
            all. 17 of 48 frames have at least one such rung and they hold 45.5% of the
            whole loss -- MAR_Amb_Cast_ETD_0004 has all seven dead and reaches 6.1% of its
            paint. The cut is affine-invariant in exact arithmetic, so this is purely the
            CLIPPING at 0: taking the same cut, same mad_k, same ladder, on the unclipped
            float residual costs no new constant and makes the bar representable again.

Every arm is additive-only (each is `(k > bar) | (img8 < t)` with a bar at or below the
shipped one), so no arm can delete a pixel the shipped build keeps; asserted per frame
rather than argued.

AND THE COST, measured three ways, because the obvious one is a trap:
  * hand-marked NOT-crack (state 2) and ERASE (state 3) are the only human-certified
    false positives, but they are 258,352 + 170,922 px against 70,041,625 px of crack and
    are ALREADY 85.5% / 96.7% proposed at the shipped setting, so they have almost no
    headroom and cannot carry a precision verdict on their own.
  * unreviewed frame area proposed -- the honest cost axis, but it must be read PER FRAME.
    Pooled, relaxing mad_k to 3.0 adds area that is 35.2% painted crack against an 8.6%
    corpus prevalence, an apparent 4.08x enrichment. Per frame it is 1.52x and 1.72x on
    the two frames that hold 46% of the loss, because half of each of those frames is
    painted. The pooled figure is a Simpson effect of relaxation adding area mainly on the
    heavily painted frames, and it must not be quoted.
  * appearance of what is being left out, which is the broad-brush question below.

THE BROAD-BRUSH BOUND, with the confounded instrument replaced. The paint asserts "there
is crack in this region", not "this pixel is crack": over all 70M painted crack pixels the
paint's own distance transform gives 2*EDT p50 = 192 px, p75 = 380 px. On the sigma=40
robust z the never-proposed paint is indistinguishable from unreviewed matrix (p50 +0.00
vs +0.00, p25 -0.75 vs -0.75) -- but that comparison cannot be read, because flattening is
a high-pass filter and the detector's own docstring says a crack wider than the blur
radius is removed by it, so a genuine wide-open crack ALSO sits at z ~ 0. This re-runs the
appearance test on `img8` itself, the percentile-stretched image the absolute test reads,
where an open crack is dark however wide it is -- and against a LOCAL matrix null, the
unreviewed pixels within 128 px of the paint, instead of all matrix in the frame, which on
these frames includes the off-specimen background.

Nothing here writes outside the scratchpad, and nothing writes to sem-crack-detector.

Run:
    MYSC=<scratchpad> /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python \
        -B analysis/research/improve/fullframe_recall_recovery.py
    ... then report_recall_recovery.py.
Env: NFRAMES to limit, OUT for the json path.
"""
import os, sys, json, time, warnings
warnings.filterwarnings("ignore")
MY = os.environ.get("MYSC", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                            "6a52cb79-9e35-41ca-afd2-799d7027591c/scratchpad")
os.environ.setdefault("MPLCONFIGDIR", MY + "/mpl")
R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R); sys.path.insert(0, R + "/improve")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from skimage import filters, exposure
import detect_cracks as D
import fullframe_lever4_safety as FF          # the loader, FOV crop and paint states
import fullframe_recall_decomposition as RD   # the chain, the ladder, the bins

LADDER, ABS_DARK, _FLATTEN, _SEG = RD.LADDER, RD.ABS_DARK, RD._FLATTEN, RD._SEG
MAD_K = RD.MAD_K
PAINT = RD.PAINT
SEM = RD.SEM
NEAR_PX, FAR_PX = 128, 512
IB = np.arange(0, 257.0, 1.0)                 # img8 levels, exact


def kmax_both(img8, flat40, control=False):
    """k_max over the ladder for BOTH representations, one rung at a time so nothing bigger
    than two frames of float32 is ever resident.

    Per rung there is ONE background estimate, from which the shipped uint8 flattened image
    and the unclipped float residual are both derived -- so the two arms differ only by the
    rescale-and-clip the float arm is testing, and not by a different background. The
    background uses detect_cracks.flatten_background's own gaussian below
    DECIMATE_ABOVE_SIGMA and the override's decimated estimate above it; `control` checks
    that re-deriving the uint8 image from it reproduces the shipped _flatten bit-for-bit,
    which is what makes it the same background.

    k_max: a pixel is dark at threshold k iff k_max > k, exactly -- see
    fullframe_recall_decomposition's docstring for the derivation.
    """
    import detector_overrides as DO
    kmu = kmf = None
    bad = 0
    for sigma in LADDER:
        if sigma <= DO.DECIMATE_ABOVE_SIGMA:
            bg = filters.gaussian(img8, sigma=sigma, preserve_range=True)
        else:
            f = max(1, int(round(sigma / 32.0)))
            small = ndi.uniform_filter(img8.astype(np.float32), f)[::f, ::f]
            bg_s = ndi.gaussian_filter(small, sigma / f, mode="nearest")
            bg = ndi.zoom(bg_s, (img8.shape[0] / bg_s.shape[0],
                                 img8.shape[1] / bg_s.shape[1]),
                          order=1, mode="nearest")[:img8.shape[0], :img8.shape[1]]
            if bg.shape != img8.shape:
                bg = np.pad(bg, ((0, img8.shape[0] - bg.shape[0]),
                                 (0, img8.shape[1] - bg.shape[1])), mode="edge")
        res = img8.astype(np.float32) - bg
        del bg
        lo, hi = np.percentile(res, [0.5, 99.5])
        if hi <= lo:
            lo, hi = res.min(), res.max()
        u8 = exposure.rescale_intensity(res, in_range=(float(lo), float(hi)),
                                        out_range=(0, 255)).astype(np.uint8)
        if control:
            ref = flat40 if sigma == 40 else _FLATTEN(img8, sigma)
            bad += int((u8 != ref).sum())
        for a, which in ((u8, "u8"), (res, "float")):
            sm = filters.gaussian(a, sigma=1.0, preserve_range=True)
            med = float(np.median(sm))
            mad = float(np.median(np.abs(sm - med)) * 1.4826)
            otsu = float(filters.threshold_otsu(sm))
            if mad > 0:
                k = ((med - sm) / mad).astype(np.float32)
                k[sm >= otsu] = -np.inf
            else:
                k = np.full(a.shape, -np.inf, np.float32)
            del sm
            if which == "u8":
                kmu = k if kmu is None else np.maximum(kmu, k)
            else:
                kmf = k if kmf is None else np.maximum(kmf, k)
            del k
        del u8, res
    if control:
        print(f"  CONTROL re-derived uint8 flattening == the shipped _flatten on all "
              f"{len(LADDER)} rungs: {'PASS' if bad == 0 else 'FAIL ' + str(bad) + ' px'}",
              flush=True)
        assert bad == 0
    return kmu, kmf


#: The arms, built one at a time so seven full-frame masks are never resident at once.
#: SUPERSETS are `(kmu > bar) | (img8 < t)` with the bar at or below the shipped one: the
#: whole chain after the darkness cut is monotone (remove_small_objects, opening, closing,
#: fill_holes and the min-area filter all preserve inclusion), so these cannot drop a pixel
#: the shipped build keeps, and that is ASSERTED per frame rather than argued.
#:
#: The raw float arms are NOT supersets and the instrument's first run caught it. Moving
#: the cut onto the unclipped residual changes that rung's own median, MAD and Otsu, so a
#: pixel can fall on the other side of its own threshold: the cut is affine-invariant in
#: exact arithmetic only when the statistics are computed on the same values, and clipping
#: at 0 changes them. They are measured anyway, with their deletion of hand-painted CRACK
#: recorded and not asserted away, because that is the only form in which the finding about
#: dead rungs can be read. The form in which such a change could ever SHIP is the union
#: with the shipped mask, which is additive by construction -- exactly the route v1.49 took.
SUPERSETS = ("ship", "abs20", "abs30", "abs50", "madk3", "madk3_abs30", "madk2_abs30",
             "float_union", "float_union_abs30")
RAW = ("float_", "float_abs30")
ALL_ARMS = ("ship", "abs20", "abs30", "abs50", "madk3", "madk3_abs30", "madk2_abs30",
            "float_", "float_abs30", "float_union", "float_union_abs30")
#: ARMS=a,b,c runs a subset; the default is all of them. `ship` is always included, since
#: every other arm is reported against it.
ARM_ORDER = tuple(dict.fromkeys(["ship"] + [a for a in os.environ.get("ARMS", "").split(",")
                                            if a in ALL_ARMS])) \
    if os.environ.get("ARMS") else ALL_ARMS
#: The appearance histograms are the slow part of the record and do not depend on the arms,
#: so a subset run skips them rather than recomputing a subset of them.
FULL = ARM_ORDER == ALL_ARMS


def arm_dark(nm, img8, kmu, kmf):
    if nm == "ship":
        return (kmu > 5.0) | (img8 < 10)
    if nm == "abs20":
        return (kmu > 5.0) | (img8 < 20)
    if nm == "abs30":
        return (kmu > 5.0) | (img8 < 30)
    if nm == "abs50":
        return (kmu > 5.0) | (img8 < 50)
    if nm == "madk3":
        return (kmu > 3.0) | (img8 < 10)
    if nm == "madk3_abs30":
        return (kmu > 3.0) | (img8 < 30)
    if nm == "madk2_abs30":
        return (kmu > 2.0) | (img8 < 30)
    if nm == "float_":
        return (kmf > 5.0) | (img8 < 10)
    if nm == "float_abs30":
        return (kmf > 5.0) | (img8 < 30)
    if nm == "float_union":
        return (kmu > 5.0) | (kmf > 5.0) | (img8 < 10)
    if nm == "float_union_abs30":
        return (kmu > 5.0) | (kmf > 5.0) | (img8 < 30)
    raise KeyError(nm)


def score(name, first):
    got = FF.load_frame(name)
    if got is None:
        return None
    img8, raw, corr = got
    spec = next((s for s in FF.SPEC_BY_LEN if name.startswith(s)), None)
    crack, notc, erase, unrev = corr == 1, corr == 2, corr == 3, corr == 0
    flat40 = D.flatten_background(img8, sigma=40)
    kmu, kmf = kmax_both(img8, flat40, control=first)
    if first:
        ref = _SEG(flat40, img8=img8, mad_k=MAD_K)
        d = int((ref ^ arm_dark("ship", img8, kmu, kmf)).sum())
        print(f"  CONTROL the `ship` arm == detector_overrides' union: "
              f"{'PASS' if d == 0 else 'FAIL ' + str(d) + ' px'}", flush=True)
        assert d == 0

    rec = dict(frame=name, specimen=spec, px=int(img8.size),
               crack=int(crack.sum()), notc=int(notc.sum()), erase=int(erase.sum()),
               unrev=int(unrev.sum()), arms={})
    ship_cand = None
    for nm in ARM_ORDER:
        dark = arm_dark(nm, img8, kmu, kmf)
        st = RD.chain(dark, flat40)
        c = st["cand"]
        if nm == "ship":
            ship_cand = c
        rec["arms"][nm] = dict(
            dark=int(dark.sum()), cand=int(c.sum()), nreg=st["nreg"],
            crack=int((c & crack).sum()), notc=int((c & notc).sum()),
            erase=int((c & erase).sum()), unrev=int((c & unrev).sum()),
            deletes_vs_ship=int((ship_cand & ~c).sum()),
            deletes_crack_vs_ship=int((ship_cand & crack & ~c).sum()))
        del dark
        if nm != "ship":
            del st, c
    bad = [nm for nm in SUPERSETS
           if nm in rec["arms"] and rec["arms"][nm]["deletes_vs_ship"]]
    assert not bad, f"{name}: {bad} deleted a pixel the shipped build keeps"

    # ---- appearance, on img8 (the quantity the absolute test reads, and the only one that
    #      is not blinded by flattening's high-pass), against a LOCAL matrix null.
    dtp = (ndi.distance_transform_edt(~crack) if (FULL and crack.any()) else None)
    near = (unrev & ~ship_cand & (dtp <= NEAR_PX)) if dtp is not None else np.zeros_like(unrev)
    far = (unrev & ~ship_cand & (dtp > FAR_PX)) if dtp is not None else np.zeros_like(unrev)
    del dtp
    if not FULL:
        return rec
    pops = dict(crack_kept=crack & ship_cand, crack_lost=crack & ~ship_cand,
                notc=notc, erase=erase, near_matrix=near, far_matrix=far)
    rec["img8"] = {k: RD._h(img8[v], IB) for k, v in pops.items()}
    rec["kmax_u8"] = {k: RD._h(kmu[v], RD.KB) for k, v in pops.items()}
    rec["kmax_float"] = {k: RD._h(kmf[v], RD.KB) for k, v in pops.items()}
    rec["img8_q"] = {k: RD._q(RD._samp(img8, v, 600000, 7)) for k, v in pops.items()}
    rec["raw_q"] = {k: RD._q(RD._samp(raw.astype(np.float64), v, 600000, 7))
                    for k, v in pops.items()}
    return rec


def main():
    names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
                   if f.endswith("_correction_mask.png"))
    names = [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
    lim = int(os.environ.get("NFRAMES", "0")) or len(names)
    names = names[:lim]
    out_path = os.environ.get("OUT", MY + "/work/recall_recovery.json")
    print(f"ladder {LADDER}   arms: {', '.join(ARM_ORDER)}")
    print(f"{len(names)} frames\n\nINSTRUMENT CONTROLS on the first frame's real pixels\n",
          flush=True)
    out, t0, did = [], time.time(), False
    for i, n in enumerate(names, 1):
        try:
            r = score(n, not did)
        except Exception as e:
            import traceback; traceback.print_exc()
            out.append(dict(frame=n, error=f"{type(e).__name__}: {e}"))
            json.dump(out, open(out_path, "w")); continue
        if r is None:
            out.append(dict(frame=n, error="shape_mismatch"))
            json.dump(out, open(out_path, "w")); continue
        did = True
        out.append(r)
        c = max(r["crack"], 1)
        a = r["arms"]
        print(f"[{i}/{len(names)}] {n:<34} painted {r['crack']:>10,}  "
              + "  ".join(f"{k.rstrip('_')} {100 * a[k]['crack'] / c:5.1f}%"
                          for k in ARM_ORDER)
              + (f"  [float_ deletes {a['float_']['deletes_crack_vs_ship']:,} painted]"
                 if "float_" in a else "")
              + f"  {time.time() - t0:5.0f}s", flush=True)
        json.dump(out, open(out_path, "w"))
    json.dump(out, open(out_path, "w"))
    print(f"\nwrote {out_path} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
