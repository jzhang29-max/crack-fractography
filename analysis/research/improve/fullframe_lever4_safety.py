"""Is the retrained region classifier (lever 4) a real gain, or another deleter?

VERDICT: REJECTED. It deletes 72.67% of the hand-marked crack the shipped path delivers --
worse than the texture veto and the thickness excision this repo already rejected, and
worse than the shipped classifier it was meant to replace. Numbers below.

It scores nested held-out IoU 0.5318 on the 26 hand-labelled tiles against 0.2979 for the
shipped-with-classifier-off path. But it is a rule that REJECTS regions, and two rules in
that class already died here: a texture veto (tiles IoU 0.4940) and a thickness excision
(tiles IoU 0.3853) each deleted ~40% of hand-marked crack on FULL frames. The tiles are
structurally blind to it -- a wide-open main crack does not fit in a 512 px crop.

So this asks the tiles nothing. It asks the paint: train leave-one-SPECIMEN-out on the
tiles, run on every full frame that has a correction mask, and count hand-marked crack
pixels the classifier rejects that the shipped path keeps.

    1 = hand-marked CRACK       -> a rejection here is a DELETION, the disqualifying harm
    2 = hand-marked NOT-crack   -> a rejection here is a real precision gain
    3 = ERASE from candidacy    -> also a human not-crack verdict. The earlier full-frame
                                   script counted state 3 as unreviewed; pooling 2 and 3
                                   raises the not-crack evidence from 258,352 to 429,274 px
    0 = unreviewed              -> excluded from everything; 91% of the corpus, and
                                   scoring it would invent a precision collapse

MEASURED, 48 frames (every correction mask that has a micrograph; all 48 align natively in
FOV coordinates), 70,041,625 hand-marked crack px -- against the 10-12 frames and 6.3M px
the earlier run used. At the shipped mad_k=5.0, on hand-marked CRACK pixels:

    arm                     crack px kept   deleted vs no-classifier   % of what it kept
    no classifier (v1.48)      17,225,923                          0               0.00%
    lever 4                     4,707,541                 12,518,382              72.67%
    lever 4 + force-keep       15,721,158                  1,504,765               8.74%
    shipped classifier         16,333,534                    892,389               5.18%

Ranked against the two rules already rejected, re-measured on these SAME 48 frames with
this same denominator -- because voidkiller_safety.py's 43.46% and 41.00% were four frames
against a different denominator and are not comparable to anything here
(deadrules_same_frames.py):

    lever 4 (retrained region classifier)      deletes 12,518,382   72.67% of kept
    texture veto floor=1.0                     deletes 11,634,179   67.54% of kept
    thickness excision r_big=50                deletes 10,753,927   62.43% of kept
    thickness excision r_big=100               deletes  9,409,029   54.62% of kept

Lever 4 is the worst of the four. On the "% of painted" denominator those same three dead
rules read 16.61% / 15.35% / 13.43% over 48 frames, against 43.46% / 41.00% / 40.28% over
the four frames voidkiller_safety.py used -- which is why only one unit set and one
denominator may be quoted at a time.

RE-MEASURED against the candidate stage that ships TODAY. v1.49 (commit b5de5a5) landed
the multi-scale union while this was in flight, so the numbers above are against v1.48's
single-scale sigma=40 cut. Re-run with CANDIDATES=v149, which takes the override function
from detector_overrides.install() itself rather than reimplementing it (and is checked by
collapsing its ladder to (40,), which must reproduce v1.48 exactly):

    arm                     crack px kept   deleted vs no-classifier   % of what it kept
    no classifier (v1.49)      20,903,694                          0               0.00%
    lever 4                     4,865,430                 16,038,264              76.72%
    lever 4 + force-keep       18,645,814                  2,257,880              10.80%
    shipped classifier         19,770,671                  1,133,023               5.42%

The union is a strict superset, so it hands the classifier MORE crack to reject and the
verdict gets worse, not better: 76.72% against 72.67%, and the force-keep remedy degrades
from 28 to 33 of 48 frames losing more than 1% of their kept crack. Every conclusion below
holds on both candidate stages.

Not a single-frame artefact: 38 of the 48 frames lose more than 1% of their kept crack,
7 of the 10 specimens lose more than 60%, and the figure is 77.49% at mad_k=3.0 and
77.64% at mad_k=2.5. The one number that settles it -- lever 4 removes 143,252
hand-marked NOT-crack pixels while deleting 12,518,382 hand-marked crack pixels, i.e. it
destroys 87 px of real crack per px of false positive it removes. The shipped classifier,
which this repo already switched OFF as net-negative, removes MORE not-crack (150,293 px)
for 14x less crack damage (5.9 px per px). Lever 4 is strictly worse than the thing it
was proposed to replace.

WHY -- and it is in the INPUT, not the score. MeanWidth is the model's top feature by
permutation importance (+0.0570). Over the tile TRAINING POSITIVES it spans 2.61-29.34 px,
because a crack wider than that cannot fit in a 512 px tile. The regions holding
hand-painted crack on a full frame span MeanWidth 18-236 px and MaxWidth 42-654 px:
DISJOINT support. 88.0% of all deleted crack pixels lie in regions wider than ANY training
positive (lever4_width_extrapolation.py). And only 8 of 31 such regions are rejected, so
this is not even a learned width rule -- it is unconstrained extrapolation into a corner of
feature space the training set never visited, where the verdict is arbitrary and the stakes
are the whole main crack. It is the thickness excision again, reached by a fitted
coefficient instead of a hard constant.

THE TILE SCORE WAS NEVER EVIDENCE FOR IT, either. Read at MATCHED mad_k and with the one
known-pathological tile removed (the off-specimen void on MAR_H_HIP_CBS_0002, which owns
86.5% of all candidate-stage false positives), lever 4's advantage over keeping every
candidate is:

    mad_k=5.0 (the shipped setting)   IoU26 +0.1766   IoU25 -0.0063   <- a REGRESSION
    mad_k=3.0                         IoU26 +0.2082   IoU25 +0.0247
    mad_k=2.5                         IoU26 +0.2218   IoU25 +0.0625

At the setting that ships, the entire gain is one void region. And lever 4 already deletes
real crack ON THE TILES -- true positives 107,930 -> 103,792 (-3.8%) at mad_k=5.0, -7.7% at
mad_k=2.5. The tile instrument reported that loss as a win because the precision it bought
on one void outweighed it in a pooled IoU.

THE FORCE-KEEP REMEDY ALSO FAILS. Production calls classify_with_model with
force_keep_area=50000 -- any candidate of at least 50,000 px is kept whatever the model
says, installed by the repo for exactly this hazard ("No training data means no reliable
model opinion here"). Bolting it onto lever 4 cuts the deletion from 72.67% to 8.74%, which
is still 28 of 48 frames losing more than 1% of their kept crack. And the tiles cannot
evaluate it: only 1 of 228 tile regions reaches 50,000 px and it is the void, so on tiles a
force-keep force-keeps the void and scores IoU 0.5318 -> 0.3324. The tile ranking and the
full-frame ranking of the same rule point opposite ways.

(Incidentally, the force-keep is not what protected the shipped classifier: at mad_k=5.0 the
shipped arm is bit-identical with and without it, so the old 8-feature model keeps large
regions on its own. The two full-frame scripts that omitted force_keep_area still compared
like with like, so the v1.48 conclusion stands, but "recall 0.6740" in detector_overrides.py
is not the real shipped recall.)

WHAT WOULD HAVE TO CHANGE before any tile-trained region rule is believable: training
regions that contain wide-open main cracks, which means labelling at frame scale or at a
crop size that admits them, not 512 px. Until then a tile IoU cannot rank a rule that
rejects regions, in either direction.

Nothing here writes outside the scratchpad, and nothing writes to sem-crack-detector.

Run:
    /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python -B \
        analysis/research/improve/fullframe_lever4_safety.py
    ... then report_fullframe_lever4.py for the tables above.
Env: NFRAMES to limit, MADKS to pick thresholds, OUT for the json path.
"""
import os, sys, json, time, warnings
warnings.filterwarnings("ignore")
MY = os.environ.get("MYSC", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                            "35618087-5532-4f31-9699-5f1551304d41/scratchpad")
os.environ.setdefault("MPLCONFIGDIR", MY + "/mpl")
R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R); sys.path.insert(0, R + "/improve")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code")
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/interior_active_learning/code")
sys.dont_write_bytecode = True
import numpy as np, tifffile, joblib
from scipy import ndimage as ndi
from skimage import exposure, filters
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
import detect_cracks as D
import crackpipe as CP, tilebench as TB
import lever4_region_classifier as L4
from common import contrast_kwargs_for

SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
PAINT = os.path.join(SEM, "interior_active_learning", "paint")
MADKS = tuple(float(x) for x in os.environ.get("MADKS", "5.0,3.0,2.5").split(","))
SPEC_BY_LEN = sorted({t["specimen"] for t in json.load(open(L4.SC + "/tiles_meta.json"))},
                     key=len, reverse=True)


# ---------------------------------------------------------------- feature extraction
def nf_bbox(labeled, lab, sl, flat, raw, ves, ts):
    """L4.new_features for one region, without materialising a full-frame mask.

    L4.new_features pads the bbox by 8 and then only ever reads inside that window, so
    handing it the window itself -- with a slice that covers the whole window, which pads
    to a no-op -- is the same arithmetic on the same pixels. _selfcheck() asserts that
    bit-for-bit against L4.new_features on real tile regions before any frame is scored.
    """
    pad = 8
    y0 = max(sl[0].start - pad, 0); y1 = min(sl[0].stop + pad, flat.shape[0])
    x0 = max(sl[1].start - pad, 0); x1 = min(sl[1].stop + pad, flat.shape[1])
    w = (slice(y0, y1), slice(x0, x1))
    m = labeled[w] == lab
    h, wd = m.shape
    return L4.new_features(m, (slice(0, h), slice(0, wd)), flat[w], raw[w], ves[w], ts)


def _selfcheck():
    """Two positive controls on the instrument, before it is pointed at the paint."""
    t = TB.load(with_raw=True)[0]
    st = CP.stages(t["img8"], mad_k=3.0)
    lab, raw, objs = st["labeled"], t["raw"], ndi.find_objects(st["labeled"])
    ts = raw_stats(raw)
    ids = st["df"]["Label"].values.astype(int)
    ref = [L4.new_features(lab == l, objs[l - 1], st["flat"], raw, st["ves"], ts) for l in ids]
    got = [nf_bbox(lab, l, objs[l - 1], st["flat"], raw, st["ves"], ts) for l in ids]
    bad = [(k, a[k], b[k]) for a, b in zip(ref, got) for k in a if a[k] != b[k]]
    print(f"  CONTROL bbox features identical to L4.new_features over {len(ids)} regions: "
          f"{'PASS' if not bad else 'FAIL ' + str(bad[:3])}")
    assert not bad
    # cached-stage reuse must reproduce crackpipe.stages exactly
    base = frame_base(t["img8"])
    for mk in (5.0, 2.5):
        a, b = CP.stages(t["img8"], mad_k=mk), stages_at(base, mk)
        same = (np.array_equal(a["clean"], b["clean"])
                and np.array_equal(a["labeled"], b["labeled"])
                and len(a["df"]) == len(b["df"]))
        print(f"  CONTROL cached stages == crackpipe.stages at mad_k={mk}: "
              f"{'PASS' if same else 'FAIL'}")
        assert same
    # the shipped multi-scale override, with its ladder collapsed to the single shipped
    # radius, must reproduce the v1.48 cut exactly -- otherwise a v149 number is not
    # comparable to a v148 one and the whole before/after is unreadable.
    a = stages_at(base, 5.0)
    b = stages_v149(base, 5.0, ladder=(40,))
    same = np.array_equal(a["labeled"], b["labeled"])
    print(f"  CONTROL shipped union at ladder=(40,) == v1.48 single scale: "
          f"{'PASS' if same else 'FAIL'}")
    assert same
    if CANDIDATES == "v149":
        c = stages_v149(base, 5.0)
        grew = int(c["clean"].sum()) >= int(a["clean"].sum())
        print(f"  CONTROL full ladder is a superset on this tile: {'PASS' if grew else 'FAIL'}"
              f"  ({int(a['clean'].sum()):,} -> {int(c['clean'].sum()):,} px)")
        assert grew


def raw_stats(raw):
    med = float(np.median(raw))
    return dict(raw_med=med, raw_mad=float(np.median(np.abs(raw - med)) * 1.4826),
                raw_std=float(raw.std()))


# ---------------------------------------------------------------- the pipeline, mad_k-shared
def frame_base(img8):
    """Everything in crackpipe.stages that does NOT depend on mad_k. Frangi vesselness is
    the expensive stage and is mad_k-independent, so it is computed once per frame."""
    flat = D.flatten_background(img8, sigma=40)
    smooth = filters.gaussian(flat, sigma=1.0, preserve_range=True)
    otsu = float(filters.threshold_otsu(smooth))
    med = float(np.median(smooth))
    mad = float(np.median(np.abs(smooth - med)) * 1.4826)
    return dict(img8=img8, flat=flat, smooth=smooth, otsu=otsu, med=med, mad=mad,
                ves=D.compute_vesselness(flat))


def stages_at(base, mad_k, absolute_dark=10, min_area=13):
    dark = ((base["smooth"] < min(base["otsu"], base["med"] - mad_k * base["mad"]))
            | (base["img8"] < absolute_dark))
    return _finish(base, dark, min_area)


def _finish(base, dark, min_area=13):
    clean = D.clean_mask(dark, open_radius=1, close_radius=3, min_area_px=min_area)
    lab, _ = ndi.label(clean)
    labeled, df = D.region_features_from_labeled(lab, base["flat"], base["ves"])
    return dict(clean=clean, labeled=labeled, df=df)


# CANDIDATES=v149 scores against the candidate stage that actually ships after v1.49,
# which unions the darkness cut over a ladder of flattening radii. The override function
# is taken from analysis/detector_overrides.py by calling its own install(), not
# reimplemented here, so this cannot drift from what the app runs.
CANDIDATES = os.environ.get("CANDIDATES", "v148")
_SEG = None


def _seg_v149(ladder=None):
    global _SEG
    if _SEG is None or ladder is not None:
        sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
        import detector_overrides as DO

        class _FakeUP:
            pass

        up = _FakeUP()
        kw = dict(use_multiscale_union=True)
        if ladder is not None:
            kw["scale_ladder"] = ladder
        DO.install(up, **kw)
        if ladder is not None:
            return up.segment_dark_regions
        _SEG = up.segment_dark_regions
    return _SEG


def stages_v149(base, mad_k, min_area=13, ladder=None):
    seg = _seg_v149(ladder)
    return _finish(base, seg(base["flat"], img8=base["img8"], mad_k=mad_k), min_area)


def candidates(base, mad_k):
    return stages_v149(base, mad_k) if CANDIDATES == "v149" else stages_at(base, mad_k)


# ---------------------------------------------------------------- models
def loso_models(mad_k, feats=L4.ALLF, tau=0.18, wmode="sqrt", kind="logit"):
    """{specimen_held_out: model} plus 'ALL'. The model for specimen S never saw S.
    A frame whose specimen contributes no tiles gets 'ALL', which is held-out for it."""
    S, tiles, order, spec, fam, gt = L4._ctx()
    X, area, frac, fidx, labs = L4.matrix(mad_k, feats)
    y = (frac > tau).astype(int)
    w = L4.weights(area, wmode)
    g = np.array([spec[order[i]] for i in fidx])
    out = {"ALL": L4._fit(kind, X, y, w)}
    for s in sorted(set(g)):
        tr = g != s
        out[s] = L4._fit(kind, X[tr], y[tr], w[tr])
    return out


SHIP = joblib.load(os.path.join(SEM, "models", "crack_classifier.joblib"))
#: detect_cracks.classify_with_model's own default, and the value the production call in
#: unified_pipeline.score_pass1_candidates uses: any candidate region of at least this
#: many pixels is force-kept as crack whatever the model says. The repo installed it for
#: exactly the hazard measured here -- "No training data means no reliable model opinion"
#: about a region that large. Both this script's predecessor and the tile harness omit it,
#: so a "shipped classifier" arm without it understates the real shipped recall.
FORCE_KEEP_AREA = 50000


def shipped_keep(df):
    """The region classifier as it exists on disk today, at the bundle's own threshold."""
    if not len(df):
        return np.zeros(0, bool)
    p = SHIP["clf"].predict_proba(SHIP["scaler"].transform(df[SHIP["feature_names"]].values))[:, 1]
    return p >= SHIP["threshold"]


# ---------------------------------------------------------------- per-frame scoring
def load_frame(name):
    raw = tifffile.imread(os.path.join(SEM, "original", name + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    ck = contrast_kwargs_for(name)        # 3 of these frames need the gentler stretch
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8, raw = img8[y0:y1, x0:x1], raw[y0:y1, x0:x1]
    corr = np.array(Image.open(os.path.join(PAINT, name + "_correction_mask.png")))
    while corr.ndim > 2:
        corr = corr[..., 0]
    if corr.shape != img8.shape:          # older masks were saved in full-image coords
        if corr.shape[0] >= y1 and corr.shape[1] >= x1:
            corr = corr[y0:y1, x0:x1]
        else:
            return None
    return img8, raw, corr


def score(name, models):
    """One frame, every mad_k, every arm. `models[mad_k][specimen]` is the model that
    never saw that specimen's tiles."""
    got = load_frame(name)
    if got is None:
        return None
    img8, raw, corr = got
    spec = next((s for s in SPEC_BY_LEN if name.startswith(s)), None)
    crack, notc, erase = corr == 1, corr == 2, corr == 3
    base = frame_base(img8)
    ts = raw_stats(raw)
    rec = dict(frame=name, specimen=spec, shape=list(img8.shape), crack=int(crack.sum()),
               notc=int(notc.sum()), erase=int(erase.sum()), arms={})
    for mk in MADKS:
        mdl = models[mk]
        key = spec if spec in mdl else "ALL"
        rec["model"] = key
        st = candidates(base, mk)
        labeled, df = st["labeled"], st["df"]
        ids = df["Label"].values.astype(int)
        objs = ndi.find_objects(labeled)
        if len(ids):
            rows = [nf_bbox(labeled, l, objs[l - 1], base["flat"], raw, base["ves"], ts)
                    for l in ids]
            sh = df[L4.SHIPPED8].values.astype(np.float64)
            X = np.stack([sh[:, L4.SHIPPED8.index(f)] if f in L4.SHIPPED8
                          else np.array([r[f] for r in rows]) for f in L4.ALLF], 1)
            keep_new = L4._pred(mdl[key], X) >= 0.5
            keep_old = shipped_keep(df)
            big = df["Area"].values >= FORCE_KEEP_AREA     # production's force-keep
        else:
            keep_new = keep_old = big = np.zeros(0, bool)

        def painted(sel):
            s = ids[sel]
            return np.isin(labeled, s) if len(s) else np.zeros(labeled.shape, bool)

        arm = {}
        for nm, sel in (("keepall", np.ones(len(ids), bool)), ("lever4", keep_new),
                        ("lever4_fk", keep_new | big), ("shipped_clf", keep_old),
                        ("shipped_clf_fk", keep_old | big), ("bigonly", big),
                        ("rejectall", np.zeros(len(ids), bool))):
            m = painted(sel)
            arm[nm] = dict(nreg=int(sel.sum()), area=int(m.sum()),
                           crack=int((m & crack).sum()), notc=int((m & notc).sum()),
                           erase=int((m & erase).sum()))
        rec["arms"][str(mk)] = dict(nreg_total=len(ids), **arm)
    return rec


def main():
    names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
                   if f.endswith("_correction_mask.png"))
    names = [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
    lim = int(os.environ.get("NFRAMES", "0")) or len(names)
    names = names[:lim]
    out_path = os.environ.get("OUT", MY + "/work/fullframe_lever4.json")
    print("INSTRUMENT CONTROLS", flush=True)
    _selfcheck()
    print(f"\nmodels: leave-one-specimen-out over the 26 tiles, mad_k in {MADKS}", flush=True)
    models = {mk: loso_models(mk) for mk in MADKS}
    print(f"{len(names)} frames have both a micrograph and a correction mask\n", flush=True)
    out, t0 = [], time.time()
    mk0 = str(MADKS[0])
    for i, n in enumerate(names, 1):
        try:
            r = score(n, models)
        except Exception as e:
            print(f"[{i}/{len(names)}] {n}  ERROR {type(e).__name__}: {e}", flush=True)
            out.append(dict(frame=n, error=f"{type(e).__name__}: {e}"))
            json.dump(out, open(out_path, "w")); continue
        if r is None:
            print(f"[{i}/{len(names)}] {n}  SKIPPED (paint does not fit the image)", flush=True)
            out.append(dict(frame=n, error="shape_mismatch"))
            json.dump(out, open(out_path, "w")); continue
        out.append(r)
        a = r["arms"][mk0]
        kept, d = a["keepall"]["crack"], a["keepall"]["crack"] - a["lever4"]["crack"]
        print(f"[{i}/{len(names)}] {n:<34} painted {r['crack']:>10,}  mad_k={mk0} "
              f"kept {kept:>10,} -> {a['lever4']['crack']:>10,}  DELETED {d:>10,} "
              f"({100 * d / max(kept, 1):5.1f}% of kept)  {time.time() - t0:5.0f}s", flush=True)
        json.dump(out, open(out_path, "w"))
    json.dump(out, open(out_path, "w"))
    print(f"\nwrote {out_path} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
