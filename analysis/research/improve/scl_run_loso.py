"""Leave-one-SPECIMEN-out U-Net runs: 13 folds x N losses, scored on clDice.

Produces one probability map per (loss, tile), every tile predicted by a net that never
saw its specimen. Thresholds are chosen NESTED -- for fold i the operating point is the
one that maximises pooled clDice over the held-out predictions of all OTHER folds -- so
no tile's threshold saw its own score. Writes probs to the scratchpad; scl_score.py reads
them. Nothing is written outside the scratchpad.

    python -B scl_run_loso.py --losses dice,cldice,thin4,thin8 --steps 400 --jobs 4
"""
import os, sys, time, argparse, warnings
warnings.filterwarnings("ignore")
import numpy as np

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True
import scl_unet as U    # noqa: E402
import scl_cldice as C  # noqa: E402
import tilebench as TB  # noqa: E402

OUT = U.OUT
THIN_R = {"thin2": 2, "thin4": 4, "thin8": 8, "thin16": 16}


def _job(args):
    (kind, sp, specs_of_tile, Xc, Y, S, T, steps, seed, threads, base, crop, nch) = args
    import torch
    torch.set_num_threads(threads)
    tr = [i for i, s in enumerate(specs_of_tile) if s != sp]
    te = [i for i, s in enumerate(specs_of_tile) if s == sp]
    t0 = time.time()
    net = U.train_fold(Xc[tr], Y[tr], S[tr], T[tr], kind.rstrip("0123456789") if kind.startswith("thin") else kind,
                       seed=seed, steps=steps, threads=threads, base=base, crop=crop)
    probs = {i: U.predict_prob(net, Xc[i]) for i in te}
    import torch as _t
    ck = os.path.join(U.OUT, f"net_{os.environ.get('CTX_TAG','main')}_{kind}_{sp}.pt")
    _t.save(dict(state=net.state_dict(), cin=Xc.shape[1], base=base), ck)
    return kind, sp, probs, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--losses", default="dice,cldice,thin4,thin8")
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--base", type=int, default=16)
    ap.add_argument("--crop", type=int, default=256)
    ap.add_argument("--specimens", default="")
    ap.add_argument("--channels", default="img")       # img | img+flat
    ap.add_argument("--shuffle-labels", action="store_true")
    ap.add_argument("--rotate-labels", action="store_true")
    ap.add_argument("--constant-input", action="store_true")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()

    os.environ["CTX_TAG"] = a.tag or "main"
    tiles = TB.load()
    gs = [C.skel(t["gt"]) for t in tiles]
    specs_of_tile = [t["specimen"] for t in tiles]
    specs = sorted(set(specs_of_tile))
    if a.specimens:
        specs = [s for s in specs if s in a.specimens.split(",")]

    # ---- sabotage arms, applied to the TRAINING signal only, never to the score ----
    rng = np.random.default_rng(1234)
    if a.shuffle_labels:
        perm = rng.permutation(len(tiles))
        tiles_tr = [dict(tiles[i], gt=tiles[perm[i]]["gt"]) for i in range(len(tiles))]
        gs_tr = [gs[perm[i]] for i in range(len(tiles))]
    elif a.rotate_labels:
        roll = list(range(1, len(tiles))) + [0]
        tiles_tr = [dict(tiles[i], gt=tiles[roll[i]]["gt"]) for i in range(len(tiles))]
        gs_tr = [gs[roll[i]] for i in range(len(tiles))]
    else:
        tiles_tr, gs_tr = tiles, gs

    kinds = a.losses.split(",")
    thin_rs = sorted({THIN_R.get(k, 4) for k in kinds})
    # one prep per thin radius, so each loss gets the target it names
    packs = {}
    for r in thin_rs:
        X, Y, S, T = U.prep(tiles_tr, gs_tr, r)
        packs[r] = (X, Y, S, T)
    X0 = packs[thin_rs[0]][0]
    if a.constant_input:
        X0 = np.zeros_like(X0)
        for r in packs:
            packs[r] = (np.zeros_like(packs[r][0]),) + packs[r][1:]
    if a.channels == "img+flat":
        import detect_cracks as D
        from skimage import filters
        extra = []
        for t in tiles:
            f = D.flatten_background(t["img8"], sigma=40).astype(np.float32)
            f = (f - f.mean()) / max(f.std(), 1e-6)
            v = filters.frangi(255 - t["img8"].astype(np.float32), black_ridges=False).astype(np.float32)
            v = (v - v.mean()) / max(v.std(), 1e-6)
            extra.append(np.stack([f, v]))
        extra = np.stack(extra)
        if a.constant_input:
            extra = np.zeros_like(extra)
        for r in packs:
            packs[r] = (np.concatenate([packs[r][0], extra], 1),) + packs[r][1:]

    jobs = []
    for kind in kinds:
        r = THIN_R.get(kind, thin_rs[0])
        X, Y, S, T = packs[r]
        for sp in specs:
            jobs.append((kind, sp, specs_of_tile, X, Y, S, T, a.steps, a.seed,
                         a.threads, a.base, a.crop, X.shape[1]))
    print(f"{len(jobs)} jobs ({len(kinds)} losses x {len(specs)} folds), "
          f"{a.steps} steps, {a.jobs} procs x {a.threads} threads", flush=True)

    store = {k: {} for k in kinds}
    t0 = time.time()
    if a.jobs <= 1:
        res = [_job(j) for j in jobs]
    else:
        import multiprocessing as mp
        ctx = mp.get_context("fork")
        with ctx.Pool(a.jobs) as pool:
            res = []
            for i, out in enumerate(pool.imap_unordered(_job, jobs), 1):
                res.append(out)
                print(f"  [{i}/{len(jobs)}] {out[0]} / {out[1]}  {out[3]:.0f}s "
                      f"(elapsed {time.time()-t0:.0f}s)", flush=True)
    for kind, sp, probs, _ in res:
        store[kind].update(probs)

    tag = a.tag or "main"
    for kind in kinds:
        arr = np.zeros((len(tiles), 512, 512), np.float32)
        for i, p in store[kind].items():
            arr[i] = p
        np.save(os.path.join(OUT, f"prob_{tag}_{kind}.npy"), arr)
    print(f"wrote {len(kinds)} prob stacks to {OUT} with tag '{tag}' in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
