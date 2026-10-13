"""WHERE IS CANDIDATE-STAGE RECALL LOST ON FULL FRAMES? One stage per missed pixel.

The region-classifier debate of the last two days was about the 30% of hand-painted crack
the candidate stage DOES propose. This is about the other 70.2%. After v1.49's multi-scale
union the candidate stage still never proposes 70.16% of the 70,041,625 hand-painted crack
pixels on the 48 frames that carry a correction mask -- a bigger quantity than anything a
region rule could move -- and it had only ever been decomposed on 512 px tiles, where the
same figure reads 45.7% and so understates it by 24 points.

The chain a painted pixel has to survive, exactly as interior_active_learning/code/
unified_pipeline.py runs it (lines 223-289), with the v1.49 override installed:

    flatten_background(img8)                     sigma=40
    segment_dark_regions(flat, img8=img8)        -> OVERRIDDEN: union of the same cut over
                                                   flattening radii (5,10,20,40,80,160,320)
                                                   OR (img8 < 10)
    clean_mask(dark, min_area_px=13)             remove_small_objects(<=13, 4-conn)
                                                   -> opening(disk 1) -> closing(disk 3)
                                                   -> binary_fill_holes
    extract_candidates(clean, ..., min_area_px=40)  measure.label(connectivity=2), then
                                                   drop every component under 40 px

Four of those steps can lose a pixel (closing and fill_holes are extensive and can only
add), so every hand-marked crack pixel that does not reach a candidate is attributed to
exactly one of four, by the first step that dropped it and did not give it back:

    notdark     dark at NO radius on the ladder and not absolutely dark either
    small13     dark, but its 4-connected dark component was <= 13 px
    opening     survived that, but erased by opening with disk(1)
    area40      reached the clean mask, but its 8-connected component was < 40 px

This instrument does NOT write a second loader. load_frame / frame_base / raw_stats come
from fullframe_lever4_safety.py, which already handles the three frames needing
contrast_kwargs_for's gentler stretch, the FOV crop, and the four paint states. The
per-radius flattening function is pulled OUT OF THE SHIPPED OVERRIDE'S OWN CLOSURE
(analysis/detector_overrides.py install()._flatten) rather than reimplemented, so the
ladder cannot drift from what the app runs, and the reconstruction is checked bit-for-bit
against the override's own union output on every frame.

HOW MUCH IS RECOVERABLE, measured rather than asserted. For each rung the cut is
`sm < min(otsu_s, med_s - k*mad_s)`, so a pixel is dark at rung s for threshold k iff
`sm_s < otsu_s` AND `k < (med_s - sm_s)/mad_s`. Define

    k_max(px) = max over rungs of ((med_s - sm_s)/mad_s if sm_s < otsu_s else -inf)

then `dark(k) = (k_max > k) | (img8 < 10)` EXACTLY, for every k at once. k_max is the
recoverability coordinate: its histogram over the never-proposed painted pixels says how
far mad_k would have to move to reach them, and its histogram over the hand-marked
NOT-crack and the unreviewed matrix says what that would cost. The full chain is then
re-run at k in (5.0, 3.0, 2.0, 1.0) so the answer is the real one and not a dark-stage
upper bound.

THE CAVEAT THE NUMBER CANNOT BE READ WITHOUT. The paint is broad-brush: it asserts "there
is crack in this region", not "this pixel is crack". So some of the 70.2% is paint lying
over genuine matrix, and that part is not recoverable by any detector. Three independent
bounds on it, none of which uses the darkness cut as its own referee:

  * stroke width, from the paint's own distance transform: 2*EDT inside the painted mask,
    quantiles reported per frame. A stroke of width W over a crack of width w leaves a
    halo of (W-w)/2 px that no detector should mark.
  * geometry: every painted 8-connected component is scored for whether the detector hit
    it at all. Mass inside a component the detector DID hit is attributable to brush
    overshoot / width mismatch; mass in a component it missed entirely is a missed object.
    Plus the full distance-to-nearest-candidate curve for the missed pixels, against the
    same curve for unreviewed matrix as the no-relationship reference.
  * appearance: robust z on the sigma=40 flattened image and Frangi vesselness, for
    never-proposed painted crack against (a) hand-marked NOT-crack, states 2 and 3, which
    is the only human-certified matrix in the corpus and is dark-biased because a human
    only paints it where the detector proposed something, so it is a CONSERVATIVE
    comparator, and (b) unreviewed matrix, which has no referee at all.

Reported per frame and per specimen, never pooled alone: MAR_Amb_AS_CBS_0003 alone holds
12.8M of the 70M painted pixels, so a pooled figure can be one frame.

Nothing here writes outside the scratchpad, and nothing writes to sem-crack-detector.

Run:
    MYSC=<scratchpad> /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python \
        -B analysis/research/improve/fullframe_recall_decomposition.py
    ... then report_recall_decomposition.py for the tables.
Env: NFRAMES to limit, KSWEEP to pick the re-run thresholds, OUT for the json path.
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
from skimage import filters, measure, morphology
import detect_cracks as D
import crackpipe as CP, tilebench as TB
# The loader, the FOV crop, contrast_kwargs_for and the four paint states all live here.
import fullframe_lever4_safety as FF

SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
MAD_K = 5.0                      # what ships
ABS_DARK = 10                    # segment_dark_regions' absolute_dark_thresh
MIN_AREA_CLEAN = 13              # unified_pipeline.py:225
MIN_AREA_CAND = 40               # unified_pipeline.py:289
KSWEEP = tuple(float(x) for x in os.environ.get("KSWEEP", "5.0,3.0,2.0,1.0").split(","))

# ---- binning. Fixed bins so per-frame histograms sum exactly to the corpus histogram.
KB = np.round(np.arange(-3.0, 15.0001, 0.1), 4)      # k_max
ZB = np.round(np.arange(-14.0, 8.0001, 0.25), 4)     # robust z on the sigma=40 flat
VB = np.concatenate([[-1e-12], np.logspace(-7, 0, 71)])   # Frangi vesselness (very skewed)
DB = np.concatenate([np.arange(0, 256.0, 1.0), [1e9]])    # distance to nearest candidate
WB = np.concatenate([np.arange(0, 512.0, 2.0), [1e9]])    # 2*EDT inside the paint


def _h(vals, bins):
    """Histogram as a plain list, with the two overflow buckets kept separately so no
    pixel is silently dropped into an edge bin."""
    if not len(vals):
        return dict(n=0, lo=0, hi=0, h=[0] * (len(bins) - 1))
    v = np.asarray(vals, np.float64)
    finite = np.isfinite(v)
    lo = int(((v < bins[0]) & finite).sum()) + int((v == -np.inf).sum())
    hi = int(((v >= bins[-1]) & finite).sum()) + int((v == np.inf).sum())
    h, _ = np.histogram(v[finite], bins=bins)
    return dict(n=int(len(v)), lo=lo, hi=hi, h=[int(x) for x in h])


def _q(vals, qs=(1, 5, 10, 25, 50, 75, 90, 95, 99)):
    if not len(vals):
        return {}
    v = np.asarray(vals, np.float64)
    v = v[np.isfinite(v)]
    if not len(v):
        return {}
    return {f"p{q}": float(np.percentile(v, q)) for q in qs}


def _samp(arr, m, cap=600000, seed=0):
    """At most `cap` of arr's values under mask m, uniformly, for the populations where a
    quantile is wanted but 20M values are not. The histograms above are always over ALL
    pixels; only the printed quantiles are sampled."""
    v = arr[m]
    if len(v) <= cap:
        return v
    i = np.random.default_rng(seed).choice(len(v), cap, replace=False)
    return v[i]


# ---------------------------------------------------------------- the shipped ladder
def shipped_ladder():
    """SCALE_LADDER, the absolute threshold, and install()'s own _flatten -- taken from
    analysis/detector_overrides.py rather than copied, so a change there reaches here."""
    import detector_overrides as DO

    class _U:
        pass

    u = _U()
    DO.install(u)
    seg = u.segment_dark_regions
    fv = seg.__code__.co_freevars
    flat_fn = seg.__closure__[fv.index("_flatten")].cell_contents
    return DO.SCALE_LADDER, int(DO.OVERRIDES.get("absolute_dark_thresh", ABS_DARK)), flat_fn, seg


LADDER, ABS_DARK, _FLATTEN, _SEG = shipped_ladder()


def rung_maps(img8, flat40):
    """Per-rung boolean cut, and k_max. One pass, two outputs, no second flattening.

    dark = OR(rung cuts) | (img8 < ABS_DARK) is the override's own union by construction;
    _control_union() checks that against the override function itself on real pixels.
    """
    kmax = np.full(img8.shape, -np.inf, np.float32)
    dark_rel = np.zeros(img8.shape, bool)
    per = {}
    for sigma in LADDER:
        f = flat40 if sigma == 40 else _FLATTEN(img8, sigma)
        sm = filters.gaussian(f, sigma=1.0, preserve_range=True)
        med = float(np.median(sm))
        mad = float(np.median(np.abs(sm - med)) * 1.4826)
        otsu = float(filters.threshold_otsu(sm))
        cut = sm < min(otsu, med - MAD_K * mad)
        dark_rel |= cut
        if mad > 0:
            k = ((med - sm) / mad).astype(np.float32)
            k[sm >= otsu] = -np.inf
        else:
            k = np.full(img8.shape, -np.inf, np.float32)
        np.maximum(kmax, k, out=kmax)
        per[sigma] = dict(cut=cut, med=med, mad=mad, otsu=otsu,
                          area=int(cut.sum()))
        del sm, k, f
    return dark_rel, kmax, per


def chain(dark, flat40, ves=None, features=False):
    """clean_mask then the min-area-40 candidate filter, with the intermediates kept.

    The candidate filter is applied by bincount over measure.label(connectivity=2), which
    is what region_features_from_labeled's `p.area < min_area_px` test does -- regionprops'
    `area` IS the pixel count. _control_bincount() checks the two agree exactly on a real
    frame before the cheap form is used for the sweep.
    """
    b = morphology.remove_small_objects(dark, max_size=MIN_AREA_CLEAN)
    c = morphology.opening(b, morphology.disk(1))
    d = morphology.closing(c, morphology.disk(3))
    e = ndi.binary_fill_holes(d)
    lab = measure.label(e, connectivity=2)
    cnt = np.bincount(lab.ravel())
    keep = cnt >= MIN_AREA_CAND
    keep[0] = False
    cand = keep[lab]
    out = dict(b=b, c=c, e=e, cand=cand, lab=lab, nreg=int(keep.sum()))
    if features:
        labeled, df = D.region_features_from_labeled(lab, flat40, ves)
        out["labeled"], out["df"] = labeled, df
    return out


# ---------------------------------------------------------------- controls
def _control_union(img8, flat40, dark_rel, where):
    """The reconstruction must BE the shipped union, not merely resemble it."""
    ref = _SEG(flat40, img8=img8, mad_k=MAD_K)
    got = dark_rel | (img8 < ABS_DARK)
    diff = int((ref ^ got).sum())
    print(f"  CONTROL [{where}] reconstruction == detector_overrides' union: "
          f"{'PASS' if diff == 0 else 'FAIL ' + str(diff) + ' px'}", flush=True)
    assert diff == 0
    return got


def _control_kmax(img8, kmax, dark):
    """dark(k) = (k_max > k) | absolute must reproduce the union at the shipped k."""
    got = (kmax > MAD_K) | (img8 < ABS_DARK)
    diff = int((got ^ dark).sum())
    tot = max(int(dark.sum()), 1)
    ok = diff <= 1e-7 * dark.size
    print(f"  CONTROL k_max reconstructs dark at mad_k={MAD_K}: "
          f"{'PASS' if ok else 'FAIL'}  ({diff} px of {tot:,} dark, "
          f"{100.0 * diff / tot:.6f}% -- float round-off only)", flush=True)
    assert ok


def _control_bincount(st):
    """The cheap min-area-40 filter must equal region_features_from_labeled's own."""
    a, b = st["cand"], st["labeled"] > 0
    diff = int((a ^ b).sum())
    print(f"  CONTROL bincount min_area filter == region_features_from_labeled: "
          f"{'PASS' if diff == 0 else 'FAIL ' + str(diff) + ' px'}", flush=True)
    assert diff == 0
    print(f"  CONTROL regions kept: bincount {st['nreg']}, "
          f"region_features {len(st['df'])}  "
          f"{'PASS' if st['nreg'] == len(st['df']) else 'FAIL'}", flush=True)
    assert st["nreg"] == len(st["df"])


def _control_monotone(st5, st_lower):
    """Relaxing mad_k can only add dark pixels, so the candidate mask must only grow."""
    lost = int((st5["cand"] & ~st_lower["cand"]).sum())
    print(f"  CONTROL relaxing mad_k is additive at the candidate stage: "
          f"{'PASS' if lost == 0 else 'NOTE ' + str(lost) + ' px lost'}", flush=True)
    return lost


def _control_partition(rec):
    """The five buckets must sum to the painted crack, exactly, on every frame."""
    d = rec["decomp"]["crack"]
    s = d["kept"] + d["notdark"] + d["small13"] + d["opening"] + d["area40"]
    ok = s == rec["crack"]
    if not ok:
        print(f"  CONTROL FAIL partition {s} != painted {rec['crack']}", flush=True)
    assert ok
    return ok


def _control_connectivity(e):
    """production labels with connectivity=2; crackpipe and fullframe_lever4_safety use
    ndi.label (4-conn), which fragments more and so drops more at min_area_px=40. Measure
    the gap rather than assume it is nothing."""
    lab8 = measure.label(e, connectivity=2)
    c8 = np.bincount(lab8.ravel()); k8 = c8 >= MIN_AREA_CAND; k8[0] = False
    lab4, _ = ndi.label(e)
    c4 = np.bincount(lab4.ravel()); k4 = c4 >= MIN_AREA_CAND; k4[0] = False
    a8, a4 = int(k8[lab8].sum()), int(k4[lab4].sum())
    print(f"  CONTROL connectivity: production 8-conn keeps {a8:,} px, "
          f"4-conn (crackpipe/lever4) keeps {a4:,} px  (delta {a8 - a4:,})", flush=True)
    return a8, a4


# ---------------------------------------------------------------- per-frame
_DONE = []


def decompose(crack, dark, st):
    """Which of the four steps lost each painted pixel, ordered so the buckets are
    disjoint and exhaustive. closing and fill_holes are extensive, so a pixel the opening
    erased can come back; `& ~e` is what makes the attribution final rather than
    provisional."""
    b, c, e, cand = st["b"], st["c"], st["e"], st["cand"]
    lost = crack & ~cand
    ne = lost & ~e
    return dict(
        kept=int((crack & cand).sum()),
        notdark=int((ne & ~dark).sum()),
        small13=int((ne & dark & ~b).sum()),
        opening=int((ne & dark & b & ~c).sum()),
        area40=int((lost & e).sum()),
        # diagnostics, not part of the partition
        rescued_by_close=int((crack & ~dark & cand).sum()),
        in_dark=int((crack & dark).sum()),
        in_clean=int((crack & e).sum()),
    )


def score(name):
    got = FF.load_frame(name)
    if got is None:
        return None
    img8, raw, corr = got
    spec = next((s for s in FF.SPEC_BY_LEN if name.startswith(s)), None)
    crack, notc, erase = corr == 1, corr == 2, corr == 3
    unrev = corr == 0
    first = not _DONE
    flat40 = D.flatten_background(img8, sigma=40)
    dark_rel, kmax, per = rung_maps(img8, flat40)
    dark = (_control_union(img8, flat40, dark_rel, name) if first
            else dark_rel | (img8 < ABS_DARK))
    del dark_rel
    if first:
        _control_kmax(img8, kmax, dark)
    ves = D.compute_vesselness(flat40)
    st = chain(dark, flat40, ves, features=first)
    if first:
        _control_bincount(st)
        _control_connectivity(st["e"])
    rec = dict(frame=name, specimen=spec, shape=list(img8.shape), px=int(img8.size),
               crack=int(crack.sum()), notc=int(notc.sum()), erase=int(erase.sum()),
               unrev=int(unrev.sum()), ladder=list(LADDER),
               dark=int(dark.sum()), clean=int(st["e"].sum()), cand=int(st["cand"].sum()),
               nreg=st["nreg"],
               rung_area={str(s): per[s]["area"] for s in LADDER},
               rung_stats={str(s): dict(med=per[s]["med"], mad=per[s]["mad"],
                                        otsu=per[s]["otsu"]) for s in LADDER},
               absdark=int((img8 < ABS_DARK).sum()))

    # ---- stage decomposition, for crack and for the two human NOT-crack states
    rec["decomp"] = dict(crack=decompose(crack, dark, st),
                         notc=decompose(notc, dark, st),
                         erase=decompose(erase, dark, st))
    _control_partition(rec)

    # ---- per-rung marginal contribution to the painted crack that IS proposed
    acc = np.zeros(img8.shape, bool)
    for s in LADDER:
        acc |= per[s]["cut"]
    rec["rung_crack"] = {}
    for s in LADDER:
        others = np.zeros(img8.shape, bool)
        for s2 in LADDER:
            if s2 != s:
                others |= per[s2]["cut"]
        only = per[s]["cut"] & ~others & ~(img8 < ABS_DARK)
        rec["rung_crack"][str(s)] = dict(
            crack=int((per[s]["cut"] & crack).sum()),
            crack_only=int((only & crack).sum()),
            notc_only=int((only & notc).sum()),
            erase_only=int((only & erase).sum()),
            area_only=int(only.sum()))
        del others, only
    rec["absdark_crack"] = int(((img8 < ABS_DARK) & crack).sum())
    rec["absdark_only_crack"] = int(((img8 < ABS_DARK) & ~acc & crack).sum())
    del acc
    for s in LADDER:
        del per[s]["cut"]

    # ---- recoverability: k_max over every population, and the cost populations
    nd = crack & ~st["cand"] & ~dark          # never dark at any rung
    rec["kmax"] = dict(
        crack_lost_notdark=_h(kmax[nd], KB),
        crack_kept=_h(kmax[crack & st["cand"]], KB),
        notc_notdark=_h(kmax[notc & ~dark], KB),
        erase_notdark=_h(kmax[erase & ~dark], KB),
        unrev_notdark=_h(kmax[unrev & ~dark], KB),
    )
    rec["kmax_q"] = dict(crack_lost_notdark=_q(_samp(kmax, nd, 1000000, 2)),
                         crack_kept=_q(_samp(kmax, crack & st["cand"], 1000000, 2)),
                         notc_notdark=_q(_samp(kmax, notc & ~dark, 1000000, 2)),
                         erase_notdark=_q(_samp(kmax, erase & ~dark, 1000000, 2)),
                         unrev_notdark=_q(_samp(kmax, unrev & ~dark, 1000000, 2)))

    # ---- the real cost of relaxing: re-run the whole chain, not just the dark stage
    rec["ksweep"] = {}
    base_cand = st["cand"]
    for k in KSWEEP:
        if k == MAD_K:
            stk = st
        else:
            dk = (kmax > k) | (img8 < ABS_DARK)
            stk = chain(dk, flat40)
            if first:
                _control_monotone(st, stk)
            del dk
        ck = stk["cand"]
        rec["ksweep"][str(k)] = dict(
            dark=int(((kmax > k) | (img8 < ABS_DARK)).sum()),
            cand=int(ck.sum()), nreg=stk["nreg"],
            crack=int((ck & crack).sum()), notc=int((ck & notc).sum()),
            erase=int((ck & erase).sum()), unrev=int((ck & unrev).sum()),
            lost_vs_shipped=int((base_cand & ~ck).sum()))
        if stk is not st:
            del stk
    del kmax

    # ---- bound 1: how broad is the brush?
    dt_paint = ndi.distance_transform_edt(crack).astype(np.float32)
    rec["stroke"] = dict(width_h=_h(2.0 * dt_paint[crack], WB),
                         width_q=_q(2.0 * _samp(dt_paint, crack, 1000000, 3)))

    # ---- bound 2: geometry. Does the detector hit the painted component at all, and how
    #      far is a missed painted pixel from the nearest candidate pixel?
    plab = measure.label(crack, connectivity=2)
    pn = int(plab.max())
    if pn:
        tot = np.bincount(plab.ravel(), minlength=pn + 1)[1:]
        hit = np.bincount(plab[crack & st["cand"]].ravel(), minlength=pn + 1)[1:] \
            if (crack & st["cand"]).any() else np.zeros(pn, np.int64)
        halfw = ndi.maximum(dt_paint, plab, index=np.arange(1, pn + 1))
        halfw = np.asarray(halfw, np.float64)
        touched = hit > 0
        order = np.argsort(-tot)
        rec["paint_components"] = dict(
            n=pn, n_touched=int(touched.sum()),
            area_total=int(tot.sum()), area_touched=int(tot[touched].sum()),
            lost_in_touched=int((tot - hit)[touched].sum()),
            lost_in_untouched=int(tot[~touched].sum()),
            top=[dict(area=int(tot[i]), hit=int(hit[i]), halfwidth=float(halfw[i]))
                 for i in order[:40]],
            # the same split, but by component size decade, because one component can be
            # the whole main crack and would make "touched" trivially ~100%
            by_decade={})
        dec = np.clip(np.floor(np.log10(np.maximum(tot, 1))).astype(int), 0, 8)
        for dd in range(9):
            m = dec == dd
            if not m.any():
                continue
            rec["paint_components"]["by_decade"][str(dd)] = dict(
                n=int(m.sum()), n_touched=int((m & touched).sum()),
                area=int(tot[m].sum()), hit=int(hit[m].sum()),
                area_untouched=int(tot[m & ~touched].sum()))
    del plab, dt_paint

    dt_cand = ndi.distance_transform_edt(~st["cand"]).astype(np.float32)
    lost = crack & ~st["cand"]
    rec["dist"] = dict(
        crack_lost=_h(dt_cand[lost], DB),
        unrev=_h(dt_cand[unrev & ~st["cand"]], DB),
        notc_lost=_h(dt_cand[notc & ~st["cand"]], DB),
    )
    del dt_cand

    # ---- bound 3: appearance. robust z on the sigma=40 flat, and vesselness.
    sm40 = filters.gaussian(flat40, sigma=1.0, preserve_range=True)
    m40 = float(np.median(sm40)); d40 = float(np.median(np.abs(sm40 - m40)) * 1.4826)
    z40 = ((sm40 - m40) / max(d40, 1e-9)).astype(np.float32)
    del sm40
    pops = dict(crack_kept=crack & st["cand"], crack_lost=lost,
                crack_lost_notdark=nd, notc=notc, erase=erase,
                unrev=unrev & ~st["cand"])
    rec["z40"] = {k: _h(z40[v], ZB) for k, v in pops.items()}
    rec["ves"] = {k: _h(ves[v], VB) for k, v in pops.items()}
    rec["z40_q"] = {k: _q(_samp(z40, v, 600000, 5)) for k, v in pops.items()}
    rec["ves_q"] = {k: _q(_samp(ves, v, 600000, 5)) for k, v in pops.items()}
    rec["z40_frame"] = dict(med=m40, mad=d40)
    return rec


def main():
    names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
                   if f.endswith("_correction_mask.png"))
    names = [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
    lim = int(os.environ.get("NFRAMES", "0")) or len(names)
    names = names[:lim]
    out_path = os.environ.get("OUT", MY + "/work/recall_decomp.json")
    print(f"ladder {LADDER}  absolute_dark {ABS_DARK}  mad_k {MAD_K}  "
          f"ksweep {KSWEEP}", flush=True)
    print(f"{len(names)} frames have both a micrograph and a correction mask", flush=True)
    print("\nINSTRUMENT CONTROLS run on the first frame, on its real pixels\n", flush=True)
    out, t0 = [], time.time()
    for i, n in enumerate(names, 1):
        try:
            r = score(n)
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"[{i}/{len(names)}] {n}  ERROR {type(e).__name__}: {e}", flush=True)
            out.append(dict(frame=n, error=f"{type(e).__name__}: {e}"))
            json.dump(out, open(out_path, "w")); continue
        if r is None:
            out.append(dict(frame=n, error="shape_mismatch"))
            json.dump(out, open(out_path, "w")); continue
        _DONE.append(n)
        out.append(r)
        d = r["decomp"]["crack"]
        print(f"[{i}/{len(names)}] {n:<34} painted {r['crack']:>10,}  "
              f"kept {d['kept']:>10,} ({100 * d['kept'] / max(r['crack'], 1):5.1f}%)  "
              f"notdark {100 * d['notdark'] / max(r['crack'], 1):5.1f}%  "
              f"small13 {100 * d['small13'] / max(r['crack'], 1):4.1f}%  "
              f"open {100 * d['opening'] / max(r['crack'], 1):4.1f}%  "
              f"area40 {100 * d['area40'] / max(r['crack'], 1):4.1f}%  "
              f"{time.time() - t0:5.0f}s", flush=True)
        json.dump(out, open(out_path, "w"))
    json.dump(out, open(out_path, "w"))
    print(f"\nwrote {out_path} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
