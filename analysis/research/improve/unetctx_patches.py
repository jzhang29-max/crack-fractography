"""Build the training patch bank from the 48 hand-painted FULL frames.

The tiles are 26 crops totalling 6.8 Mpx. These frames hold 70,041,625 px of hand-marked
crack -- four orders of magnitude more supervision -- and nothing in this project has ever
trained on them.

Two decisions here decide whether the model is comparable to the tiles at all:

1. INPUT REPRESENTATION. detect_cracks.flatten_background is a 40 px high-pass followed by
   a PERCENTILE stretch, and that stretch is computed over whatever image you hand it. A
   frame's 0.5/99.5 percentiles are not a tile's, so the same crack would arrive at the
   network with different contrast depending on whether it came from a frame or a tile.
   Every window -- training patch and test window alike -- is therefore standardised by its
   OWN median and MAD after flattening. A per-window robust z-score is exactly invariant to
   the linear part of that stretch, which is the part that differs.

2. WINDOW SIZE. The standardisation depends on the window, so training patches and test
   windows must be the same size. Patches are 192 px; at test time the 512 px tile is
   covered by overlapping 192 px windows, never fed whole.

Sampling is deliberately crack-heavy (the corpus is 91.3% unreviewed) but keeps a uniform
stream so the model sees ordinary matrix too. Every patch records its frame and specimen,
because training folds are leave-one-SPECIMEN-out and a patch that cannot name its
specimen cannot be held out.

READ ONLY with respect to the paint.
"""
import os, sys
import numpy as np

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True
import unetctx_base as B
import detect_cracks as D

P = 192                       # patch side; must equal the test-time window side
PER_FRAME = 220
FRAC = dict(crack=0.60, notcrack=0.15, uniform=0.25)
BANK = os.path.join(B.MY, "bank")
os.makedirs(BANK, exist_ok=True)


def standardise(flat_u8):
    """Robust z-score of a flattened window, as int8 at 1/16 of a sigma.

    int8 at this scale covers +-8 sigma; crack cores sit near -2 to -4 sigma, so the
    quantisation is far below the signal and the bank is 1 byte per pixel instead of 4.
    """
    a = flat_u8.astype(np.float32)
    med = np.median(a)
    mad = np.median(np.abs(a - med)) * 1.4826
    z = (a - med) / max(mad, 1e-3)
    return np.clip(np.round(z * 16.0), -127, 127).astype(np.int8)


def build(verbose=True):
    out_x = os.path.join(BANK, "x.npy")
    if os.path.exists(os.path.join(BANK, "thin.npy")) and os.path.exists(out_x):
        return load()
    from skimage.morphology import skeletonize
    from scipy import ndimage as ndi
    names = B.frame_names()
    rng = np.random.default_rng(20261012)
    xs, ys, ths, fr, sp = [], [], [], [], []
    for fi, name in enumerate(names):
        r = B.load_frame(name)
        if r is None:
            continue
        img8, corr = r
        # The thinned target must be the medial axis of the WHOLE painted region, taken on
        # the frame. Skeletonising a 192 px crop of a 192 px-wide brush stroke gives the
        # crop's own medial axis, which is an artefact of where the patch boundary fell.
        thin = ndi.binary_dilation(skeletonize(corr == 1), np.ones((5, 5), bool))
        flat = D.flatten_background(img8)
        H, W = corr.shape
        if H < P or W < P:
            continue
        h = P // 2
        pools = {}
        for key, m in (("crack", corr == 1), ("notcrack", corr == 2)):
            idx = np.flatnonzero(m[h:H - h, h:W - h])
            pools[key] = idx
        n_done = 0
        for key, frac in FRAC.items():
            want = int(round(PER_FRAME * frac))
            if key == "uniform":
                cy = rng.integers(h, H - h, want); cx = rng.integers(h, W - h, want)
            else:
                idx = pools[key]
                if len(idx) == 0:
                    continue
                pick = rng.choice(idx, size=min(want, max(len(idx), 1)), replace=len(idx) < want)
                cy, cx = np.unravel_index(pick, (H - 2 * h, W - 2 * h))
                cy = cy + h; cx = cx + h
            for y, x in zip(np.atleast_1d(cy), np.atleast_1d(cx)):
                y0, x0 = int(y) - h, int(x) - h
                xs.append(standardise(flat[y0:y0 + P, x0:x0 + P]))
                ys.append(corr[y0:y0 + P, x0:x0 + P].copy())
                ths.append(thin[y0:y0 + P, x0:x0 + P].copy())
                fr.append(fi); sp.append(B.specimen_of(name))
                n_done += 1
        if verbose:
            print(f"  [{fi+1}/{len(names)}] {name:<34} {H}x{W}  +{n_done} patches", flush=True)
    X = np.stack(xs); Y = np.stack(ys); T = np.stack(ths)
    np.save(out_x, X); np.save(os.path.join(BANK, "y.npy"), Y)
    np.save(os.path.join(BANK, "thin.npy"), T)
    np.savez(os.path.join(BANK, "meta.npz"), frame=np.array(fr),
             specimen=np.array(sp), names=np.array(names))
    return load()


def load():
    X = np.load(os.path.join(BANK, "x.npy"), mmap_mode="r")
    Y = np.load(os.path.join(BANK, "y.npy"), mmap_mode="r")
    T = np.load(os.path.join(BANK, "thin.npy"), mmap_mode="r")
    m = np.load(os.path.join(BANK, "meta.npz"), allow_pickle=False)
    return X, Y, T, m["specimen"], m["names"]


if __name__ == "__main__":
    X, Y, T, spec, names = build()
    print(f"\nbank: {X.shape} int8 x, {Y.shape} uint8 y")
    from collections import Counter
    print("patches per specimen:", dict(Counter(spec.tolist())))
    Ys = np.asarray(Y)
    tot = Ys.size
    print(f"  crack      {100*(Ys==1).mean():.2f}% of banked px")
    print(f"  not-crack  {100*(Ys==2).mean():.2f}%")
    print(f"  unreviewed {100*(Ys==0).mean():.2f}%")
    print(f"  patches with ANY crack paint: {(Ys==1).any(axis=(1,2)).mean():.3f}")
    Ts = np.asarray(T)
    print(f"  thinned target: {100*Ts.mean():.3f}% of banked px "
          f"({Ts.sum()/max((Ys==1).sum(),1):.4f} x the paint)")
    Xs = np.asarray(X[:200]).astype(np.float32) / 16.0
    print(f"  input z: mean {Xs.mean():+.3f} sd {Xs.std():.3f} "
          f"p1 {np.percentile(Xs,1):+.2f} p99 {np.percentile(Xs,99):+.2f}")
