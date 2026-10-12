"""WHY lever 4 deletes main cracks: the feature that carries it has no training support.

MeanWidth is the model's top feature by permutation importance (+0.0570). Over the tile
TRAINING POSITIVES it spans 2.61-29.34 px, because a crack wider than that cannot fit in a
512 px tile alongside enough context to be labelled. This attributes every deleted
hand-marked crack pixel on a full frame to the MeanWidth of the region it was deleted
with, split at the training-positive maximum. If the deletion is concentrated above that
line, the model is extrapolating off the end of its own training data -- which is the
thickness excision again, reached by a learned coefficient instead of a hard constant.
"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
MY = os.environ.get("MYSC", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                            "35618087-5532-4f31-9699-5f1551304d41/scratchpad")
os.environ.setdefault("MPLCONFIGDIR", MY + "/mpl")
R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R); sys.path.insert(0, R + "/improve")
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
import lever4_region_classifier as L4
import fullframe_lever4_safety as FF

MK = float(os.environ.get("MK", "5.0"))
FRAMES = os.environ.get("FRAMES", ",".join([
    "260622_316_H_b2_back_CBS_01", "Cast_24hr_SE_Side_006", "MAR_Amb_AS_CBS_0003",
    "260708_316_H_b2_front_CBS_016", "AS_24hr_BSE_Side_008", "MAR_Amb_AS_CBS_0004",
])).split(",")

X, area, frac, fidx, labs = L4.matrix(MK, L4.ALLF)
y = (frac > 0.18).astype(int)
JW = L4.ALLF.index("MeanWidth")
WMAX = float(X[y == 1, JW].max())
print(f"mad_k={MK}.  MeanWidth over tile training POSITIVES: "
      f"{X[y==1,JW].min():.2f} .. {WMAX:.2f} px  (n={int(y.sum())} positive regions)\n")
models = FF.loso_models(MK)

print(f"{'frame':<32} {'deleted px':>12} {'in width<=max':>14} {'in width>max':>13} {'>max share':>11}")
print("-" * 86)
agg = dict(d=0, lo=0, hi=0, kept_hi=0, kept_lo=0)
rows = []
for name in FRAMES:
    got = FF.load_frame(name)
    if got is None:
        print(f"{name:<32}  (paint does not fit)"); continue
    img8, raw, corr = got
    spec = next((s for s in FF.SPEC_BY_LEN if name.startswith(s)), None)
    crack = corr == 1
    base = FF.frame_base(img8); ts = FF.raw_stats(raw)
    st = FF.stages_at(base, MK)
    labeled, df = st["labeled"], st["df"]
    ids = df["Label"].values.astype(int)
    if not len(ids):
        continue
    objs = ndi.find_objects(labeled)
    feats = [FF.nf_bbox(labeled, l, objs[l - 1], base["flat"], raw, base["ves"], ts)
             for l in ids]
    sh = df[L4.SHIPPED8].values.astype(np.float64)
    Xf = np.stack([sh[:, L4.SHIPPED8.index(f)] if f in L4.SHIPPED8
                   else np.array([r[f] for r in feats]) for f in L4.ALLF], 1)
    key = spec if spec in models else "ALL"
    keep = L4._pred(models[key], Xf) >= 0.5
    w = Xf[:, JW]
    # hand-marked crack px inside each region
    cnt = ndi.sum(crack, labeled, index=ids).astype(np.int64)
    rej = ~keep
    d_lo = int(cnt[rej & (w <= WMAX)].sum()); d_hi = int(cnt[rej & (w > WMAX)].sum())
    k_lo = int(cnt[keep & (w <= WMAX)].sum()); k_hi = int(cnt[keep & (w > WMAX)].sum())
    tot = d_lo + d_hi
    agg["d"] += tot; agg["lo"] += d_lo; agg["hi"] += d_hi
    agg["kept_lo"] += k_lo; agg["kept_hi"] += k_hi
    rows.append(dict(frame=name, deleted=tot, d_lo=d_lo, d_hi=d_hi, k_lo=k_lo, k_hi=k_hi,
                     n_reg=len(ids), n_wide=int((w > WMAX).sum()),
                     wide_rejected=int((rej & (w > WMAX)).sum()),
                     wide_total=int((w > WMAX).sum())))
    print(f"{name:<32} {tot:>12,} {d_lo:>14,} {d_hi:>13,} "
          f"{100*d_hi/max(tot,1):10.1f}%")
print("-" * 86)
print(f"{'POOLED':<32} {agg['d']:>12,} {agg['lo']:>14,} {agg['hi']:>13,} "
      f"{100*agg['hi']/max(agg['d'],1):10.1f}%")
print(f"\nHand-marked crack px the model KEEPS: {agg['kept_lo']:,} in regions at or below "
      f"the training width max, {agg['kept_hi']:,} above it.")
print(f"Rejection rate of regions WIDER than any training positive: "
      f"{sum(r['wide_rejected'] for r in rows)}/{sum(r['wide_total'] for r in rows)}")
json.dump(dict(mad_k=MK, wmax=WMAX, frames=rows, pooled=agg),
          open(MY + "/work/width_extrapolation.json", "w"), indent=1)
