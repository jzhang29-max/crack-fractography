"""Every TXM panel, from the DEPLOYED artefacts plus the shipped model's own code.

The frame and the window are both chosen by measurement, and nothing here is hand-set.

FRAME.  The paper reports on specimen series b2 and b3 only, so the frame is drawn from the
24 B2/B3 rows of txm_iou_ceiling_v2.json and not from all 61 labelled frames.  The rule is
the one the first edition of this plate used -- take the frame whose agreement with the
operator is closest to the corpus median, so the window is typical rather than flattering --
applied to the restricted corpus.  It selects

    Average_mosaic_260618_b2_340_00_idx00000_mosaictileAA_img001of010  (B2, 2362x1683)

and it is close to the median on BOTH scoring conventions this project uses:

    adjudicated domain   0.800 against a restricted median of 0.806 over 24 frames
    whole frame          0.584 against a restricted median of 0.635 over the same 24

Those two conventions are NOT interchangeable and the first edition's docstring conflated
them.  `iou_shipped` in txm_iou_ceiling_v2.json is restricted to pixels the operator
adjudicated (painted crack OR painted not-crack); the median over all 61 of its rows is
0.675, not 0.507.  The 0.503 / 0.507 / n = 58 this file used to hard-code are the WHOLE
FRAME convention, and no per-frame table for them survives in either repository, so they
could not be re-derived -- they are recomputed here from the frames themselves instead, by
the same expression that scores `frame_iou`, which reproduces the old frame's 0.5032 exactly.

The selection is an exact tie at the top: n = 24 is even, so the median falls midway between
b2_340_00 (0.8002) and b2_336_25 (0.8125) and both are 0.00617 away by construction.  The tie
is broken on the whole-frame convention -- the one the rule's own wording names -- where
b2_340_00 is 0.050 from the restricted median and b2_336_25 is 0.583 from it.

WINDOW.  SIDE px square, placed at the position holding the most painted-crack pixels, found
exactly by a box sum over the summed-area table of the `correction == 1` mask.  No position
is hand-chosen and the window cannot fall outside the frame.

img.npy / display.npy / prob.npy / correction.npy / emb.npz are the app's own cached
artefacts for that frame, so the SAM embedding shown is the one the deployed model used
rather than one re-embedded on a crop.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import os, sys, json, time
import numpy as np
R = _paths.require(_paths.TXM_REPO, "the TXM_Crack_Detection_Pipeline checkout", "TXM_REPO")
sys.path.insert(0, f"{R}/code"); sys.path.insert(0, f"{R}/app")
from PIL import Image
import txm_features as T
import core.model as M
import core.pipeline as PL
Image.MAX_IMAGE_PIXELS = None
OUT = os.path.dirname(os.path.abspath(__file__))

#: The specimen series the paper reports on.  AM and WR frames are excluded from the
#: selection and from every corpus figure written below.
GROUPS = ("B2", "B3")
#: Side of the square window, in pixels.  Unchanged from the first edition of this plate so
#: the two are comparable; every B2/B3 frame is at least 1629 px on its short side, so it
#: never has to be reduced.  If a frame smaller than this is ever selected it is clamped to
#: the short side and the reduction is recorded in txm_stats.json as crop_side_requested.
SIDE_REQUESTED = 1100

t0 = time.time()
def tick(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

B = f"{R}/app_data/images"


def wholeframe_iou(d):
    """The whole-frame convention: deployed mask vs painted crack, every pixel, no mask."""
    prob = np.load(f"{B}/{d}/prob.npy", mmap_mode="r")
    corr = np.asarray(np.load(f"{B}/{d}/correction.npy", mmap_mode="r"))
    crack, notc = corr == 1, corr == 2
    mask = PL.prune_specks(np.asarray(prob) > PL.DEFAULT_THRESHOLD)
    inter, union = int((mask & crack).sum()), int((mask | crack).sum())
    return dict(iou=inter / max(union, 1),
                recall=inter / max(int(crack.sum()), 1),
                fp_on_not=float((mask & notc).sum()) / max(int(notc.sum()), 1),
                crack_px=int(crack.sum()))


# --- the restricted corpus, on both conventions ----------------------------------------
CEIL = json.load(open(f"{OUT}/txm_iou_ceiling_v2.json"))
ROWS = [r for r in CEIL["per_frame"] if r["group"] in GROUPS]
tick(f"restricted corpus: {len(ROWS)} of {len(CEIL['per_frame'])} rows are {'/'.join(GROUPS)}")

ld = np.array([r["iou_shipped"] for r in ROWS], float)
ld_med, ld_q1, ld_q3 = (float(np.median(ld)), float(np.percentile(ld, 25)),
                        float(np.percentile(ld, 75)))
wid = np.array([r["label_width_px"] for r in ROWS], float)

WF = {r["id"]: wholeframe_iou(r["id"]) for r in ROWS}
wf = np.array([WF[r["id"]]["iou"] for r in ROWS], float)
wf_med, wf_q1, wf_q3 = (float(np.median(wf)), float(np.percentile(wf, 25)),
                        float(np.percentile(wf, 75)))
tick(f"adjudicated-domain median {ld_med:.4f} (q1 {ld_q1:.4f} q3 {ld_q3:.4f}); "
     f"whole-frame median {wf_med:.4f} (q1 {wf_q1:.4f} q3 {wf_q3:.4f}); n {len(ROWS)}")

# closest to the restricted median on the named convention; ties broken on the other one,
# then on id so the choice can never depend on dict ordering.
ranked = sorted(ROWS, key=lambda r: (round(abs(r["iou_shipped"] - ld_med), 12),
                                     abs(WF[r["id"]]["iou"] - wf_med), r["id"]))

# a frame is only usable if the operator actually painted crack on it and the deployed SAM
# embedding is cached, so nothing has to be re-embedded for the figure.
rejected = []
for cand in ranked:
    d = cand["id"]
    ok_corr = os.path.exists(f"{B}/{d}/correction.npy") and WF[d]["crack_px"] > 0
    ok_emb = os.path.exists(f"{B}/{d}/emb.npz")
    if ok_corr and ok_emb:
        D = d
        break
    rejected.append(dict(id=d, correction=ok_corr, emb=ok_emb))
else:
    raise SystemExit("no B2/B3 frame has both a correction mask and a cached emb.npz")
if rejected:
    print("  skipped, failing the correction/emb cross-check:",
          json.dumps(rejected, indent=1))

SELECTION = [dict(rank=i + 1, id=r["id"], group=r["group"],
                  iou_adjudicated=round(r["iou_shipped"], 4),
                  d_from_median=round(abs(r["iou_shipped"] - ld_med), 4),
                  iou_wholeframe=round(WF[r["id"]]["iou"], 4),
                  d_from_wholeframe_median=round(abs(WF[r["id"]]["iou"] - wf_med), 4),
                  label_width_px=round(r["label_width_px"], 1))
             for i, r in enumerate(ranked[:5])]
CHOSEN = next(r for r in ROWS if r["id"] == D)
tick(f"chosen {D[:58]}  adjudicated {CHOSEN['iou_shipped']:.4f}  "
     f"whole-frame {WF[D]['iou']:.4f}")

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

# --- the window: the SIDE px box holding the most painted crack ------------------------
SIDE = int(min(SIDE_REQUESTED, H, W))
if SIDE < SIDE_REQUESTED:
    print(f"  window reduced from {SIDE_REQUESTED} to {SIDE} px: the frame is only {W}x{H}")
sat = np.zeros((H + 1, W + 1), np.int64)
np.cumsum(np.cumsum(crack_all, axis=0, dtype=np.int64), axis=1, out=sat[1:, 1:])
box = (sat[SIDE:, SIDE:] - sat[:-SIDE, SIDE:] - sat[SIDE:, :-SIDE] + sat[:-SIDE, :-SIDE])
Y0, X0 = (int(v) for v in np.unravel_index(int(np.argmax(box)), box.shape))
crop_crack_px = int(box[Y0, X0])
del sat, box
tick(f"window {SIDE}px at x={X0} y={Y0}: {crop_crack_px} painted-crack px "
     f"({100.0*crop_crack_px/max(int(crack_all.sum()), 1):.1f}% of the frame's paint, "
     f"{100.0*crop_crack_px/SIDE**2:.1f}% of the window)")

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

st = dict(frame=meta["filename"], frame_id=D, frame_group=CHOSEN["group"],
  crop=[X0, Y0, SIDE], crop_side_requested=SIDE_REQUESTED, full=[int(W), int(H)],
  crop_rule="the SIDE px square holding the most correction==1 pixels, by a box sum over "
            "the summed-area table of that mask; argmax takes the topmost-leftmost box on "
            "a tie, and the box can never fall outside the frame",
  crop_crack_px=crop_crack_px,
  crop_crack_share_of_frame=float(crop_crack_px) / max(int(crack_all.sum()), 1),
  megapixels=meta["megapixels"], nm_per_px=29.24, display=meta["display"],
  model=meta["model"], model_key=meta["model_key"],
  sam_model=M.SAM_MODEL_ID, sam_tiles=int(len(coords)), sam_tile=M.TILE,
  sam_stride=M.TILE_STRIDE, emb_shape=[int(v) for v in embs.shape],
  emb_stride=M.EMB_STRIDE, emb_pca3_var=var3, emb_pc1_sep_sd=emb_sep,
  n_features=17, hybrid_dim=int(cm.n_hybrid), threshold=TH,
  feature_sep=[(nm, round(s, 2)) for s, nm, _ in sep],
  frame_iou=iou_all, frame_recall=rec_all, frame_fp_on_not=fp_all,
  frame_label_pct=100*float(crack_all.mean()), frame_notlabel_pct=100*float(not_all.mean()),

  # --- the corpus, restricted to the series the paper reports on ----------------------
  # corpus_* is the WHOLE FRAME convention, the same expression that produced frame_iou
  # above, so the two may be quoted in one sentence.  It is recomputed here over the
  # restricted frame set rather than carried over: the old 0.507 / 0.360 / 0.712 / 58 were
  # hard-coded and no per-frame table reproducing them exists in either repository.
  corpus_scope="specimen series b2 and b3 only; AM and WR frames excluded",
  corpus_convention="full-resolution IoU against the operator's painted crack, whole frame",
  corpus_median_iou=wf_med, corpus_q1=wf_q1, corpus_q3=wf_q3, corpus_n=len(ROWS),
  # the convention txm_iou_ceiling_v2.json uses, and the one the frame was selected on.
  # NOT interchangeable with corpus_* above: it admits only adjudicated pixels.
  selection=dict(
    rule="closest to the restricted corpus median; ties broken on the whole-frame "
         "convention, then on id",
    source="paper/figures/txm_iou_ceiling_v2.json",
    convention=CEIL["iou_convention"],
    groups=list(GROUPS), n=len(ROWS),
    median_iou=ld_med, q1=ld_q1, q3=ld_q3,
    frame_iou_adjudicated=CHOSEN["iou_shipped"],
    label_width_median_px=float(np.median(wid)),
    label_width_median_px_frame=CHOSEN["label_width_px"],
    ranked=SELECTION, rejected=rejected),

  crop_label_pct=100*float(lbl.mean()), crop_mask_pct=100*float(msk.mean()),
  crop_iou=iou(msk, lbl),
  p17_iou=iou(p17 > TH, lbl), ph_iou=iou(ph > TH, lbl), ens_iou=iou(ens > TH, lbl),
  p17_pct=100*float((p17 > TH).mean()), ph_pct=100*float((ph > TH).mean()),
  agreement_p17_vs_ph=iou(p17 > TH, ph > TH), agreement_ph_vs_mask=iou(ph > TH, msk),
  recompute_mean_abs_diff=agree,
  raw_sep_sd=float(abs(np.median(raw[~lbl])-np.median(raw[lbl]))/raw[~lbl].std()),
  disp_sep_sd=float(abs(float(np.median(disp8[~lbl]))-float(np.median(disp8[lbl])))/disp8[~lbl].std()),
  seconds=round(time.time()-t0, 1))
print(json.dumps(st, indent=1, default=float))
json.dump(st, open(f"{OUT}/txm_stats.json", "w"), indent=1, default=float)
