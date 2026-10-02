"""Every TXM panel, from the DEPLOYED artefacts plus the shipped model's own code.

The frame is chosen by measurement, not by looks: its full-resolution IoU against the
operator's painted crack is 0.503, and the corpus median over 58 labelled frames is
0.507 -- so this is a typical frame, not a flattering one.

img.npy / display.npy / prob.npy / correction.npy / emb.npz are the app's own cached
artefacts for that frame, so the SAM embedding shown is the one the deployed model used
(15 tiles over the whole frame) rather than one re-embedded on a crop.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import os, sys, json, time
import numpy as np
R = _paths.TXM_REPO
sys.path.insert(0, f"{R}/code"); sys.path.insert(0, f"{R}/app")
from PIL import Image
import txm_features as T
import core.model as M
import core.pipeline as PL
Image.MAX_IMAGE_PIXELS = None
OUT = os.path.dirname(os.path.abspath(__file__))
KEY = "HC_316L_fatigue_1200_cycles_idx"
X0, Y0, SIDE = 960, 360, 1100
t0 = time.time()
def tick(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

B = f"{R}/app_data/images"
D = [d for d in os.listdir(B) if KEY in json.load(open(f"{B}/{d}/meta.json"))["filename"]][0]
meta = json.load(open(f"{B}/{D}/meta.json"))
img   = np.load(f"{B}/{D}/img.npy",        mmap_mode="r")     # model input, 0-1
disp  = np.load(f"{B}/{D}/display.npy",    mmap_mode="r")     # destitched + flat-fielded
prob  = np.load(f"{B}/{D}/prob.npy",       mmap_mode="r")     # deployed ensemble probability
corr  = np.load(f"{B}/{D}/correction.npy", mmap_mode="r")     # 1 = crack, 2 = not crack
z = np.load(f"{B}/{D}/emb.npz"); coords, embs = z["coords"], z["emb"]
H, W = img.shape
tick(f"{meta['filename'][:52]}  {W}x{H}  {len(coords)} SAM tiles")

# whole-frame scores first, so the figure can say where this frame sits
crack_all = np.asarray(corr) == 1
not_all   = np.asarray(corr) == 2
mask_all  = PL.prune_specks(np.asarray(prob) > PL.DEFAULT_THRESHOLD)
iou_all   = float((mask_all & crack_all).sum() / max((mask_all | crack_all).sum(), 1))
rec_all   = float((mask_all & crack_all).sum() / max(crack_all.sum(), 1))
fp_all    = float((mask_all & not_all).sum() / max(not_all.sum(), 1))
tick(f"frame IoU {iou_all:.3f}  recall {rec_all:.3f}  fp-on-NOT {fp_all:.4f}")

sl = (slice(Y0, Y0+SIDE), slice(X0, X0+SIDE))
im  = np.asarray(img[sl], np.float32)
dp  = np.asarray(disp[sl], np.float32)
pb  = np.asarray(prob[sl], np.float32)
lbl = crack_all[sl]; nlb = not_all[sl]
msk = mask_all[sl]

# the raw mosaic, before destitching/flat-fielding, straight off the .tif
rawfull = np.asarray(Image.open(f"{R}/images/{meta['filename'][:-4]}.tif"), dtype=np.float32)
raw = rawfull[sl] if rawfull.shape[:2] == (H, W) else None
if raw is None:
    print("  raw tif shape", rawfull.shape, "!= cached", (H, W), "-- using a scaled crop")
    raw = rawfull[:min(rawfull.shape[0], H), :min(rawfull.shape[1], W)][sl]
lo, hi = np.percentile(raw, [1, 99])
raw8 = (np.clip((raw-lo)/max(hi-lo, 1e-9), 0, 1)*255).astype(np.uint8)
dlo, dhi = meta["display_limits"]
disp8 = (np.clip((dp-dlo)/max(dhi-dlo, 1e-9), 0, 1)*255).astype(np.uint8)

# the 17-channel stack -- normalised over the WHOLE frame, as predict() does
stack = T.compute_feature_stack(np.asarray(img, np.float32))[sl]
names = list(T.FEATURE_NAMES)
sep = []
for i, nm in enumerate(names):
    f = stack[..., i]; sd = f[~lbl].std()
    if sd > 0: sep.append((float(abs(f[lbl].mean()-f[~lbl].mean())/sd), nm, i))
sep.sort(reverse=True)
tick("feature stack " + ", ".join(f"{nm} {s:.2f}sd" for s, nm, _ in sep[:4]))

# the deployed SAM embedding, 256 channels -> 3 principal components -> RGB
step = 4
rr, cc = np.meshgrid(np.arange(Y0, Y0+SIDE, step), np.arange(X0, X0+SIDE, step), indexing="ij")
rows = M.emb_rows(coords, embs, rr.ravel(), cc.ravel())
Xc = rows - rows.mean(0)
U, S, Vt = np.linalg.svd(Xc[::7], full_matrices=False)
pc = (Xc @ Vt[:3].T).reshape(SIDE//step, SIDE//step, 3)
p1, p99 = np.percentile(pc, 1, axis=(0, 1)), np.percentile(pc, 99, axis=(0, 1))
embrgb = np.clip((pc-p1)/np.maximum(p99-p1, 1e-9), 0, 1)
embrgb = np.asarray(Image.fromarray((embrgb*255).astype(np.uint8)).resize((SIDE, SIDE), Image.BILINEAR))
var3 = float((S[:3]**2).sum()/(S**2).sum())
# is the embedding alone informative about crack? separation of PC1 in matrix sd
pc1 = np.asarray(Image.fromarray(pc[..., 0]).resize((SIDE, SIDE), Image.BILINEAR))
emb_sep = float(abs(pc1[lbl].mean()-pc1[~lbl].mean())/max(pc1[~lbl].std(), 1e-12))
tick(f"embedding PCA: 3 of 256 components hold {100*var3:.1f}% of variance, PC1 separates {emb_sep:.2f} sd")

# the two members, separately
cm = M.CrackModel()
p17 = np.zeros((SIDE, SIDE), np.float32)
for r0 in range(0, SIDE, 256):
    r1 = min(r0+256, SIDE)
    p17[r0:r1] = cm.m17.predict_proba(np.asarray(stack[r0:r1], np.float32).reshape(-1, 17))[:, 1] \
                   .reshape(r1-r0, SIDE)
tick("17-feature MLP(64,32)")
ph = np.zeros((SIDE, SIDE), np.float32)
for b0 in range(0, SIDE, 128):
    b1 = min(b0+128, SIDE)
    for c0 in range(0, SIDE, M.TILE):
        c1 = min(c0+M.TILE, SIDE)
        r_ = np.repeat(np.arange(b0, b1), c1-c0); c_ = np.tile(np.arange(c0, c1), b1-b0)
        Xh = np.concatenate([np.asarray(stack[r_, c_, :], np.float32),
                             M.emb_rows(coords, embs, r_+Y0, c_+X0)], axis=1)
        ph[b0:b1, c0:c1] = cm.hybrid.predict_proba(Xh)[:, 1].astype(np.float32).reshape(b1-b0, c1-c0)
tick("SAM+17 hybrid MLP(128,64) 273-d")
ens = (p17+ph)/2.0
agree = float(np.abs(ens-pb).mean())
tick(f"recomputed ensemble vs cached prob: mean |diff| {agree:.5f}")

def iou(a, b): return float((a & b).sum()/max((a | b).sum(), 1))
TH = PL.DEFAULT_THRESHOLD
for nm, a in [("raw8", raw8), ("disp8", disp8), ("img", im), ("embrgb", embrgb),
              ("p17", p17), ("ph", ph), ("ens", ens), ("prob", pb),
              ("mask", msk), ("label", lbl), ("notlabel", nlb),
              ("ftex", stack[..., names.index("texture_s8")]),
              ("fgrad", stack[..., names.index("gradmag_s4")]),
              ("flap", stack[..., names.index("laplacian_s4")]),
              ("fsm", stack[..., names.index("smooth_s16")]),
              ("fint", stack[..., names.index("intensity")])]:
    np.save(f"{OUT}/txm_{nm}.npy", a)
th = Image.fromarray(np.clip((np.asarray(disp)-dlo)/max(dhi-dlo, 1e-9), 0, 1).__mul__(255).astype(np.uint8))
th.resize((W//5, H//5), Image.LANCZOS).save(f"{OUT}/txm_frame_thumb.png")

st = dict(frame=meta["filename"], crop=[X0, Y0, SIDE], full=[int(W), int(H)],
  megapixels=meta["megapixels"], nm_per_px=29.24, display=meta["display"],
  model=meta["model"], model_key=meta["model_key"],
  sam_model=M.SAM_MODEL_ID, sam_tiles=int(len(coords)), sam_tile=M.TILE,
  sam_stride=M.TILE_STRIDE, emb_shape=[int(v) for v in embs.shape],
  emb_stride=M.EMB_STRIDE, emb_pca3_var=var3, emb_pc1_sep_sd=emb_sep,
  n_features=17, hybrid_dim=int(cm.n_hybrid), threshold=TH,
  feature_sep=[(nm, round(s, 2)) for s, nm, _ in sep],
  frame_iou=iou_all, frame_recall=rec_all, frame_fp_on_not=fp_all,
  corpus_median_iou=0.507, corpus_q1=0.360, corpus_q3=0.712, corpus_n=58,
  crop_label_pct=100*float(lbl.mean()), crop_mask_pct=100*float(msk.mean()),
  crop_iou=iou(msk, lbl),
  p17_iou=iou(p17 > TH, lbl), ph_iou=iou(ph > TH, lbl), ens_iou=iou(ens > TH, lbl),
  recompute_mean_abs_diff=agree,
  raw_sep_sd=float(abs(np.median(raw[~lbl])-np.median(raw[lbl]))/raw[~lbl].std()),
  disp_sep_sd=float(abs(float(np.median(disp8[~lbl]))-float(np.median(disp8[lbl])))/disp8[~lbl].std()),
  seconds=round(time.time()-t0, 1))
print(json.dumps(st, indent=1, default=float))
json.dump(st, open(f"{OUT}/txm_stats.json", "w"), indent=1, default=float)
