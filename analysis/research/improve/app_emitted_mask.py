"""SCORE THE MASK THE APP ACTUALLY EMITS -- not the candidate stage every number so far.

Every figure this project has quoted (tilebench.SHIPPED_V1491, detector_overrides.py's
provenance block, docs/REPORTING_GUIDE.md) is of the CANDIDATE STAGE: the multi-scale
darkness union, clean_mask(13), a 40 px region floor. The app does not emit that.
analysis/detect_one.py calls unified_pipeline.run_unified_pipeline, which also runs a
FIELD-OF-VIEW CROP before anything else and a PASS 2 (concavity / bridge_corridor /
interior_fill candidates scored by the unified model) after. This file drives that real
function, with load_as_uint8 rebound to hand back the cached tile so ORIGINAL_DIR is
never read and nothing is written into either archived repo.

INSTRUMENT CHECK FIRST: the candidate arm reproduces tilebench.SHIPPED_V1491 pooled to
1e-4 (P 0.4183 vs 0.4182, R 0.6252, F1 0.5013 vs 0.5012, IoU 0.3344).

RESULT -- 26 hand-labelled tiles. Read every row with its aggregation; the aggregation
moves these more than any method change in this project ever has, and the IoU ceiling for
a PERFECTLY PLACED trace is 0.4993 pooled / 0.5498 median-over-tiles.

  aggregation                    candidate stage        WHAT SHIPS       ships + FOV guard
  pooled                 P .4183 R .6252 IoU .3344   .4084 .6454 .3336   .4094 .6487 .3351
  median over tiles      P .8056 R .7623 IoU .4220   .7855 .7933 .4334   .7855 .7933 .4314
  median over specimens  P .7950 R .5624 IoU .3502   .7840 .5810 .3381   .7840 .5810 .3519
  median specimens, 2px  P .8964 R .7303 IoU .4802   .8893 .7303 .4256   .8893 .7303 .4854
  skeleton-F1@2, med/tile              .5485               .4950               .4986

THE APP IS NOT A SUPERSET OF THE CANDIDATE STAGE, and the difference is a defect, not
Pass 2. Over the 26 tiles the app keeps 18,646 px the candidate stage does not and LOSES
1,270 -- 1,156 of them to a field-of-view crop that fires on texture (see
fov_databar_guard.py: six tiles lose 34-127 rows each, including 40.3% of the painted
crack on MAR_Amb_Cast_ETD_0003). On the 20 tiles the crop leaves alone it is a strict
superset: +17,983 px, 0 lost, which is the figure an earlier session reported. That
session then quoted pooled recall 0.6255 -> 0.6487 and IoU 0.3344 -> 0.3351 beside it;
those are the UNTRUNCATED numbers (they reproduce exactly as candidate -> ships+FOV guard
here), so they are two different unit sets in one sentence. The truncated emission -- what
actually ships today -- is recall 0.6454 and IoU 0.3336, i.e. BELOW the candidate stage
on IoU, not above.

IS PASS 2 BETTER OR WORSE? A TIE, and that is the answer. Paired over the 13 specimens,
Pass 1 only -> Pass 1 + Pass 2 (what ships):

    IoU         median 0.3381 -> 0.3381   mean delta -0.0003   3+/5-/5=   p = 0.8438
    F1          median 0.5053 -> 0.5053   mean delta -0.0015   3+/5-/5=   p = 0.7422
    skelF1@2    median 0.4518 -> 0.4518   mean delta -0.0015   4+/4-/5=   p = 0.8438
    recall      median 0.5627 -> 0.5810   mean delta +0.0147   5+/0-/8=   p = 0.0625
    precision   median 0.7993 -> 0.7840   mean delta -0.0176   1+/7-/5=   p = 0.0156

So Pass 2 buys recall and pays for it in precision, almost exactly evenly. The net is
0.7% of the +0.05 the corpus resolves for a variant and 0.2% of the +0.14 it resolves for
a new method -- unmeasurable here, and it would stay unmeasurable at ten times this
corpus. Keeping it is the right default anyway: it is strictly ADDITIVE (0 px of the
Pass-1 mask removed, asserted per tile), so unlike every rejected precision rule it cannot
delete a pixel a human marked, and dropping it is the arm that would need the paint gate.

THE THIRD ARM IN THE BRIEF DOES NOT EXIST. "Pass 1 + only those Pass-2 regions the model
scored crack" IS the shipped arm, bit for bit: run_unified_pipeline does
`accepted, proba = _score(...); if not accepted: continue` BEFORE building the row, so a
rejected Pass-2 candidate never becomes a row of df and USE_REGION_CLASSIFIER=False cannot
resurrect it. Over the 26 tiles 92 Pass-2 candidates are proposed, 60 accepted, 32
rejected and dropped inside the pipeline. What the keep-everything rule actually
resurrects is PASS-1 rejections: 291 Pass-1 regions, of which the production 8-feature
classifier calls only 63 crack. Scored as its own arm, keeping only those 63 is a disaster
and reconfirms the shipped choice -- IoU 0.3381 -> 0.1927 paired (p = 0.0093), recall
0.5627 -> 0.3382 (p = 0.0010), skelF1 0.4518 -> 0.2489 (p = 0.0024).

ONE LEAD, NOT A RESULT. Of Pass 2's three candidate types, bridge_corridor never fires on
these tiles (0 accepted), concavity is neutral, and interior_fill -- 14 regions, 10,542 px
-- is where the precision goes. Dropping it is +0.0041 IoU and +0.0115 skelF1 paired over
13 specimens (p = 1.000; it fires on 5 tiles in 3 specimens, so ten specimens are ties),
but ON THOSE FIVE TILES it is +0.0461 IoU and +0.1387 skelF1, and on
MAR_H_AS_CBS_0001__crop_5351_2331 alone IoU 0.5133 -> 0.7095 and skelF1 0.3144 -> 0.7018.
That is the size of effect this corpus could resolve if it held more of it. It REMOVES
pixels, so it is exactly the shape of the six region-level precision rules that scored
well on 512 px crops and then deleted 54-75% of hand-painted crack on full frames. It
does not ship, and it does not get quoted, until analysis/research/improve/ runs it
against the 48 painted frames.

Run:
    /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python -B \
        analysis/research/improve/app_emitted_mask.py
"""
import os
import sys
import json
import warnings

warnings.filterwarnings("ignore")
import numpy as np
from scipy import stats, ndimage as ndi

APP = os.path.abspath(os.environ.get(
    "APP_REPO", os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))))
SEM = os.path.abspath(os.environ.get(
    "SEM_REPO", os.path.join(os.path.dirname(APP), "sem-crack-detector")))
for _p in (APP + "/analysis/research/improve", APP + "/analysis/research", APP + "/analysis",
           SEM + "/code", SEM + "/interior_active_learning/code"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.dont_write_bytecode = True

import tilebench as TB            # noqa: E402
import detector_overrides as DO   # noqa: E402
import unified_pipeline as up     # noqa: E402
import common                     # noqa: E402
import detect_cracks as D         # noqa: E402
import angle4_shipped as SH       # noqa: E402
import fov_databar_guard as FOV   # noqa: E402
from ctx_metric import skelf1     # noqa: E402

# EXACTLY detect_one.py's suppression: an uploaded image has no human corrections, so the
# mask under test is the detector's own answer.
up.load_correction_mask = lambda *a, **k: None
common.load_correction_mask = lambda *a, **k: None
up.load_hard_overrides = lambda *a, **k: {}
APPLIED = DO.install(up)

_CUR = {}
up.load_as_uint8 = lambda path, **kw: _CUR["img8"]
_STOCK_FOV = up.find_field_of_view


def emit(img8, stem, guarded_fov=False):
    """One tile through the app's own pipeline. Returns the FULL-SIZE masks."""
    _CUR["img8"] = img8
    fov = FOV.find_field_of_view if guarded_fov else _STOCK_FOV
    up.find_field_of_view = fov
    st = up.run_unified_pipeline(stem)
    lab, df = st["labeled"], st["df"]
    x0, y0, x1, y1 = fov(img8)
    p2 = {int(k): v[0] for k, v in st["interior_origin"].items()}
    alll = [int(v) for v in df["Label"].tolist()]

    def place(labels):
        m = np.isin(lab, labels) if len(labels) else np.zeros(lab.shape, bool)
        full = np.zeros(img8.shape, bool)
        full[y0:y1, x0:x1] = m[:y1 - y0, :x1 - x0]
        return full

    return dict(
        ship=place(alll),
        pass1=place([l for l in alll if l not in p2]),
        pass1_crack=place([int(v) for v in df.loc[df["IsCrack"] == True, "Label"].tolist()  # noqa: E712
                           if int(v) not in p2]),
        no_interior_fill=place([l for l in alll if p2.get(l) != "interior_fill"]),
        fov=(x0, y0, x1, y1), n_p1=len([l for l in alll if l not in p2]),
        n_p2=len(p2), n_p2_proposed=int(st["n_interior_total"]),
        n_p1_crack=int((df.loc[~df["Label"].isin(list(p2)), "IsCrack"] == True).sum()))  # noqa: E712


def candidate_stage(img8):
    """What every score this project has quoted actually measured."""
    lab, _ = ndi.label(D.clean_mask(SH.shipped_clean(img8), min_area_px=13))
    if not lab.max():
        return np.zeros(lab.shape, bool)
    sz = np.bincount(lab.ravel())
    k = np.where(sz >= 40)[0]
    return np.isin(lab, k[k > 0])


def prf(tp, fp, fn):
    p = tp / max(tp + fp, 1)
    r = tp / max(tp + fn, 1)
    return dict(precision=p, recall=r, f1=2 * p * r / max(p + r, 1e-12),
                iou=tp / max(tp + fp + fn, 1))


ARMS = ("candidate", "pass1", "pass1_crack", "ship", "shipfix", "no_interior_fill")


def main():
    tiles = TB.load()
    SH.selfcheck([t["img8"] for t in tiles[:3]])
    print("overrides:", APPLIED)

    masks, rows = {}, {a: [] for a in ARMS}
    for i, t in enumerate(tiles, 1):
        f, gt = t["frame"], t["gt"]
        r = emit(t["img8"], f, guarded_fov=False)
        rf = emit(t["img8"], f, guarded_fov=True)
        masks[(f, "candidate")] = candidate_stage(t["img8"])
        for k in ("ship", "pass1", "pass1_crack"):
            masks[(f, k)] = r[k]
        masks[(f, "shipfix")] = rf["ship"]
        masks[(f, "no_interior_fill")] = rf["no_interior_fill"]
        for a in ARMS:
            m = masks[(f, a)]
            c = TB.counts(m, gt, tol=2)
            c.update(frame=f, specimen=t["specimen"], px=int(m.sum()),
                     skelf1=skelf1(m, gt, 2))
            rows[a].append(c)
        print(f"  [{i:2d}/{len(tiles)}] {f[:48]:<48} fov={r['fov']} "
              f"p1={r['n_p1']:3d} (classifier keeps {r['n_p1_crack']:2d}) "
              f"p2={r['n_p2']:2d}/{r['n_p2_proposed']:3d}", flush=True)

    specs = sorted({t["specimen"] for t in tiles})

    def agg(rr, key, tol=False):
        pre = "t" if tol else ""
        if key == "pooled":
            return prf(sum(r[pre + "tp"] for r in rr), sum(r[pre + "fp"] for r in rr),
                       sum(r[pre + "fn"] for r in rr))
        if key == "tiles":
            L = [prf(r[pre + "tp"], r[pre + "fp"], r[pre + "fn"]) for r in rr]
        else:
            L = [prf(sum(r[pre + "tp"] for r in rr if r["specimen"] == s),
                     sum(r[pre + "fp"] for r in rr if r["specimen"] == s),
                     sum(r[pre + "fn"] for r in rr if r["specimen"] == s)) for s in specs]
        return {m: float(np.median([x[m] for x in L])) for m in L[0]}

    print("\n" + "=" * 112)
    print("(a) THE REAL EMITTED MASK, 26 hand-labelled tiles.  IoU ceiling for a perfect "
          "trace: 0.4993 pooled / 0.5498 median-tiles")
    print("=" * 112)
    for metric in ("precision", "recall", "f1", "iou"):
        print(f"\n  --- {metric.upper()}")
        print("  " + " " * 26 + "".join(f"{a:>18}" for a in ARMS))
        for lab_, key, tol in (("pooled", "pooled", False), ("median over tiles", "tiles", False),
                               ("median over specimens", "specs", False),
                               ("median tiles, 2px", "tiles", True),
                               ("median specimens, 2px", "specs", True)):
            print(f"  {lab_:<26}" + "".join(
                f"{agg(rows[a], key, tol)[metric]:>18.4f}" for a in ARMS))
    print("\n  --- SKELETON-F1 @ tau=2  (not width-gameable: a no-information dilation "
          "moves it +0.0015, p=0.68)")
    print("  " + " " * 26 + "".join(f"{a:>18}" for a in ARMS))
    print(f"  {'median over tiles':<26}" + "".join(
        f"{np.median([r['skelf1'] for r in rows[a]]):>18.4f}" for a in ARMS))
    print(f"  {'median over specimens':<26}" + "".join(
        f"{np.median([np.median([r['skelf1'] for r in rows[a] if r['specimen'] == s]) for s in specs]):>18.4f}"
        for a in ARMS))
    print(f"\n  {'px marked':<26}" + "".join(
        f"{sum(r['px'] for r in rows[a]):>18,}" for a in ARMS))

    def sv(rr, metric):
        v = []
        for s in specs:
            g = [r for r in rr if r["specimen"] == s]
            v.append(float(np.median([r["skelf1"] for r in g])) if metric == "skelf1"
                     else prf(sum(r["tp"] for r in g), sum(r["fp"] for r in g),
                              sum(r["fn"] for r in g))[metric])
        return np.array(v)

    print("\n" + "=" * 112)
    print("(b) PAIRED OVER THE 13 SPECIMENS -- Wilcoxon signed-rank, two-sided")
    print("=" * 112)
    for a, b in (("pass1", "ship"), ("pass1", "pass1_crack"), ("candidate", "ship"),
                 ("ship", "shipfix"), ("ship", "no_interior_fill")):
        print(f"\n  {a}  ->  {b}")
        for metric in ("iou", "f1", "recall", "precision", "skelf1"):
            x, y = sv(rows[a], metric), sv(rows[b], metric)
            d = y - x
            nz = int((np.abs(d) > 1e-12).sum())
            p = stats.wilcoxon(x, y).pvalue if nz else 1.0
            print(f"    {metric:<10} {np.median(x):7.4f} -> {np.median(y):7.4f}  "
                  f"median d {np.median(d):+8.4f}  mean d {d.mean():+8.4f}  "
                  f"{int((d > 1e-12).sum()):2d}+/{int((d < -1e-12).sum()):2d}-/{13 - nz:2d}=  "
                  f"p={p:.4f}")

    print("\n" + "=" * 112)
    print("CONTAINMENT -- an arm that DELETES pixels needs the full-frame paint gate")
    print("=" * 112)
    for a, b in (("pass1", "ship"), ("candidate", "ship"), ("candidate", "shipfix"),
                 ("ship", "shipfix"), ("ship", "no_interior_fill")):
        lo = sum(int((masks[(t["frame"], a)] & ~masks[(t["frame"], b)]).sum()) for t in tiles)
        ad = sum(int((masks[(t["frame"], b)] & ~masks[(t["frame"], a)]).sum()) for t in tiles)
        flag = "  <-- REMOVES" if lo else ""
        print(f"  {a:<18} -> {b:<18} only in {a}: {lo:>8,}   only in {b}: {ad:>8,}{flag}")

    print("\n" + "=" * 112)
    print("(c) AGAINST THE CORPUS RESOLUTION: +0.05 for a variant, +0.14 for a new method, "
          "at n=13 specimens")
    print("=" * 112)
    for a, b in (("pass1", "ship"), ("ship", "shipfix"), ("ship", "no_interior_fill"),
                 ("candidate", "ship")):
        for metric in ("iou", "skelf1"):
            d = (sv(rows[b], metric) - sv(rows[a], metric)).mean()
            print(f"  {a:>10} -> {b:<18} {metric:<7} mean paired delta {d:+8.4f}"
                  f"   = {abs(d) / 0.05 * 100:5.1f}% of the variant bar, "
                  f"{abs(d) / 0.14 * 100:5.1f}% of the new-method bar")

    out = os.path.join(os.environ.get("OUT_DIR", "/tmp"), "app_emitted_mask.json")
    json.dump({a: rows[a] for a in ARMS}, open(out, "w"), indent=1, default=float)
    print(f"\nrows -> {out}")


if __name__ == "__main__":
    main()
