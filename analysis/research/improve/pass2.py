"""Score what the app ACTUALLY emits, and ask whether Pass 2 should be kept.

Every number this project has quoted scores the CANDIDATE STAGE. detect_one.py calls
run_unified_pipeline, which also runs PASS 2 -- concavity, bridge_corridor and interior_fill
proposals, scored by the same model -- and with USE_REGION_CLASSIFIER=False it keeps EVERY
row of df, Pass-2 rows included, which the model itself scored not-crack. So the shipped
configuration has never been evaluated.

Three arms, all through tilebench, paired across the 13 specimens:
    pass1        keep only Pass-1 candidate regions
    pass1+pass2  what ships today
    pass1+p2ok   Pass 1, plus only the Pass-2 rows the model scored crack

Nothing is written into the archived repo: load_as_uint8 and find_field_of_view are
rebound so the pipeline is handed the tile array directly instead of resolving a path out
of ORIGINAL_DIR.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R)
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis")
sys.path.insert(0, os.path.join(SEM, "interior_active_learning", "code"))
sys.path.insert(0, os.path.join(SEM, "code"))
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
from scipy import stats
from skimage.morphology import skeletonize
import tilebench as TB, crackpipe as CP
import detector_overrides as DO
import unified_pipeline as up
import common
ST = ndi.generate_binary_structure(2, 2)

# suppress human corrections exactly as detect_one.py does
up.load_correction_mask = lambda *a, **k: None
common.load_correction_mask = lambda *a, **k: None
up.load_hard_overrides = lambda *a, **k: {}
print("install():", DO.install(up))

_CUR = {}
up.load_as_uint8 = lambda *a, **k: _CUR["img8"]
up.find_field_of_view = lambda img8: (0, 0, img8.shape[1], img8.shape[0])
up.contrast_kwargs_for = lambda name: {}


def skelf1(pred, gt, tau=2):
    p, g = np.asarray(pred, bool), np.asarray(gt, bool)
    if not p.any() or not g.any():
        return 0.0
    sp, sg = skeletonize(p), skeletonize(g)
    if not sp.any() or not sg.any():
        return 0.0
    dg = ndi.distance_transform_edt(~sg); dp = ndi.distance_transform_edt(~sp)
    a = float((dg[sp] <= tau).mean()); b = float((dp[sg] <= tau).mean())
    return 0.0 if a + b == 0 else 2 * a * b / (a + b)


def met(pred, gt):
    tp = int((pred & gt).sum()); fp = int((pred & ~gt).sum()); fn = int((~pred & gt).sum())
    p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
    return dict(precision=p, recall=r, f1=2 * p * r / max(p + r, 1e-12),
                iou=tp / max(tp + fp + fn, 1), skelf1=skelf1(pred, gt))


tiles = TB.load()
print("CONTROLS"); assert TB.controls(); print()
ARMS = ["candidate stage only (what was scored)", "pass1 regions", "pass1+pass2 (SHIPS)",
        "pass1 + model-approved pass2"]
rows = {a: [] for a in ARMS}
ok_tiles = []
for i, t in enumerate(tiles, 1):
    _CUR["img8"] = t["img8"]
    try:
        st = up.run_unified_pipeline(t["frame"])
    except Exception as e:
        print(f"  [{i:>2}/26] {t['frame'][:40]:<42} PIPELINE FAILED {type(e).__name__}: {e}", flush=True)
        continue
    lab, df = st["labeled"], st["df"]
    if lab.shape != t["gt"].shape:
        print(f"  [{i:>2}/26] {t['frame'][:40]:<42} shape {lab.shape} != gt {t['gt'].shape} -- skipped", flush=True)
        continue
    cols = set(df.columns)
    srccol = "CandidateType" if "CandidateType" in cols else None
    allm = np.isin(lab, df["Label"].tolist()) if len(df) else np.zeros(lab.shape, bool)
    if srccol:
        # Pass 1 rows have CandidateType NaN; Pass 2 rows carry concavity /
        # bridge_corridor / interior_fill. isna() is the split, not a name list.
        p1 = df[df[srccol].isna()]
        p2 = df[df[srccol].notna()]
    else:
        p1, p2 = df, df.iloc[0:0]
    m_p1 = np.isin(lab, p1["Label"].tolist()) if len(p1) else np.zeros(lab.shape, bool)
    p2ok = p2[p2["IsCrack"] == True] if len(p2) and "IsCrack" in cols else p2.iloc[0:0]  # noqa: E712
    m_mix = m_p1 | (np.isin(lab, p2ok["Label"].tolist()) if len(p2ok) else False)
    cand = CP.stages(t["img8"])["labeled"] > 0
    for a, m in zip(ARMS, [cand, m_p1, allm, m_mix]):
        rows[a].append(met(np.asarray(m, bool), t["gt"]))
    ok_tiles.append(i - 1)
    print(f"  [{i:>2}/26] {t['frame'][:40]:<42} df {len(df):>4} rows"
          + (f" (pass1 {len(p1)}, pass2 {len(p2)}, p2 approved {len(p2ok)})" if srccol else " (no source column)")
          + f"  emitted {int(allm.sum()):>6} px vs cand {int(cand.sum()):>6}", flush=True)

print(f"\n{len(ok_tiles)} of {len(tiles)} tiles went through the real pipeline")
specs = [tiles[i]["specimen"] for i in ok_tiles]
us = sorted(set(specs))
print(f"\n  {'arm':<40} {'prec':>7} {'recall':>7} {'F1':>7} {'IoU':>7} {'skelF1':>8}")
for a in ARMS:
    if not rows[a]:
        continue
    pm = []
    for s in us:
        jj = [j for j, sp in enumerate(specs) if sp == s]
        pm.append({k: np.median([rows[a][j][k] for j in jj]) for k in rows[a][0]})
    print(f"  {a:<40} " + " ".join(f"{np.median([x[k] for x in pm]):7.4f}"
                                   for k in ("precision", "recall", "f1", "iou"))
          + f" {np.median([x['skelf1'] for x in pm]):8.4f}")
print("\n  (median over specimens of the median over that specimen's tiles)")
print("\nPAIRED across specimens, vs 'pass1+pass2 (SHIPS)'")
def perspec(a, k):
    return np.array([np.median([rows[a][j][k] for j, sp in enumerate(specs) if sp == s]) for s in us])
for a in ARMS:
    if a == "pass1+pass2 (SHIPS)" or not rows[a]:
        continue
    for k in ("f1", "iou", "skelf1"):
        x, y = perspec("pass1+pass2 (SHIPS)", k), perspec(a, k)
        if np.allclose(x, y):
            print(f"  {a:<40} {k:<7} identical"); continue
        print(f"  {a:<40} {k:<7} {np.median(y-x):+.4f}  {int((y>x).sum())} up / {int((y<x).sum())} down  "
              f"p={stats.wilcoxon(x,y).pvalue:.4f}")
json.dump({a: rows[a] for a in ARMS} | {"tiles": [tiles[i]["frame"] for i in ok_tiles]},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pass2.json"), "w"), indent=1)
