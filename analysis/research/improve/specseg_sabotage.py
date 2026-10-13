"""Break the specimen mask and confirm the score collapses.

A rule that removes area will raise precision whether or not it knows anything, so the
tile gain is unreadable without a control that removes area while knowing NOTHING about
where the specimen is. Four arms, all scored through tilebench and nothing else:

  REAL        the parent frame's own specimen mask, cropped to the tile box
  WRONG-FRAME the specimen mask of a DIFFERENT parent, cropped at the same box. Same
              construction, same amount of structure, wrong object. If the gain survives
              this, the gain is not about this frame's specimen.
  SHIFTED     the real mask rolled by half the parent frame in both axes.
  AREA-MATCHED NOISE  a random coarse-block mask removing exactly the same number of
              candidate pixels, per tile. This is the information-free comparator: it
              buys the precision that merely deleting that much area buys.

Also reported exactly (not to 4 dp): the true-positive pixels each arm destroys on the
tiles, because "recall unchanged" has to mean unchanged.
"""
import os, sys, json
import warnings; warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
import tilebench as TB
import specimen_mask as SM
import specseg_tiles as ST

BEST = dict(kind="fine", rule=0.5, close_px=200, grow_px=0)   # the TOP TILE SCORER
SAFE = dict(kind="coarse", rule=0.1, close_px=600, grow_px=200)  # the best gate-PASSING arm


def parent_specimen(parent, v=BEST):
    bm, bs, shape, fov = ST.parent_blocks(parent)
    S, T, E = SM.specimen_coarse(bm, bs, **v)
    return SM.upsample(S, shape), shape


def crop(full, shape, box):
    x, y, w, h = box
    out = np.ones((h, w), bool)
    sub = full[y:y + h, x:x + w]
    out[:sub.shape[0], :sub.shape[1]] = sub
    return out


def main():
    tiles = TB.load()
    meta = {t["frame"]: t for t in json.load(open(TB.SC + "/tiles_meta.json"))}
    parents = sorted({meta[t["frame"]]["parent"] for t in tiles})
    full = {p: parent_specimen(p) for p in parents}
    base = [ST.shipped_candidates(t["img8"]) for t in tiles]
    rng = np.random.default_rng(0)

    safefull = {p: parent_specimen(p, SAFE) for p in parents}
    arms = {"shipped (no mask)": base,
            "SAFE arm (passes gate)": [b & crop(*safefull[meta[t["frame"]]["parent"]],
                                                meta[t["frame"]]["box"])
                                       for b, t in zip(base, tiles)]}
    real, wrong, shift, noise = [], [], [], []
    for b, t in zip(base, tiles):
        m = meta[t["frame"]]; box = m["box"]; p = m["parent"]
        f, sh = full[p]
        r = crop(f, sh, box)
        real.append(b & r)
        # wrong frame: the next parent in sorted order that is not this tile's own
        alt = next(q for q in parents[parents.index(p) + 1:] + parents[:parents.index(p)]
                   if q != p)
        fa, sa = full[alt]
        wrong.append(b & crop(fa, sa, box))
        shift.append(b & crop(np.roll(f, (sh[0] // 2, sh[1] // 2), (0, 1)), sh, box))
        # area-matched noise: drop random coarse blocks until the same number of
        # CANDIDATE pixels is gone as the real mask dropped on this very tile
        want = int((b & ~r).sum())
        nb = (t["gt"].shape[0] // SM.B, t["gt"].shape[1] // SM.B)
        cand_blk = b[:nb[0] * SM.B, :nb[1] * SM.B].reshape(nb[0], SM.B, nb[1], SM.B).sum((1, 3))
        order = rng.permutation(nb[0] * nb[1])
        drop = np.zeros(nb[0] * nb[1], bool)
        acc = 0
        for i in order:
            if acc >= want:
                break
            if cand_blk.ravel()[i]:
                drop[i] = True; acc += int(cand_blk.ravel()[i])
        nm = ~SM.upsample(drop.reshape(nb), t["gt"].shape)
        noise.append(b & nm)
    # GLOBAL area-matched noise: the per-tile arm above is handed the real mask's own
    # per-tile budget, i.e. it is TOLD which tile to cut and by how much -- most of the
    # answer. This one is told only the total: remove the same FRACTION of candidate area
    # from every tile at random. It is the information-free comparator.
    tot_rm = sum(int((b & ~r).sum()) for b, r in zip(base, real))
    frac = tot_rm / max(sum(int(b.sum()) for b in base), 1)
    gnoise = []
    for b, t in zip(base, tiles):
        nb = (t["gt"].shape[0] // SM.B, t["gt"].shape[1] // SM.B)
        cand_blk = b[:nb[0] * SM.B, :nb[1] * SM.B].reshape(nb[0], SM.B, nb[1], SM.B).sum((1, 3))
        want = frac * int(b.sum())
        order = rng.permutation(nb[0] * nb[1]); drop = np.zeros(nb[0] * nb[1], bool); acc = 0
        for i in order:
            if acc >= want:
                break
            if cand_blk.ravel()[i]:
                drop[i] = True; acc += int(cand_blk.ravel()[i])
        gnoise.append(b & ~SM.upsample(drop.reshape(nb), t["gt"].shape))
    arms.update({"REAL (top tile scorer)": real, "WRONG-FRAME mask": wrong,
                 "SHIFTED mask": shift, "AREA-MATCHED NOISE (per tile)": noise,
                 "AREA-MATCHED NOISE (global)": gnoise})

    vi = next(i for i, t in enumerate(tiles) if t["frame"] == TB.FLOODED)
    print(f"{'arm':<24} {'P':>8} {'R':>8} {'IoU':>8} {'F1':>8} {'tp lost':>9} "
          f"{'cand px rm':>11} {'void FP':>9} {'void FP rm':>11}")
    print("-" * 104)
    btp = sum(int((b & t["gt"]).sum()) for b, t in zip(base, tiles))
    bfp = int((base[vi] & ~tiles[vi]["gt"]).sum())
    bca = sum(int(b.sum()) for b in base)
    for k, ms in arms.items():
        r = TB.evaluate(k, {k: [TB.counts(m, t["gt"]) for m, t in zip(ms, tiles)]},
                        quiet=True)["loso"]
        tp = sum(int((m & t["gt"]).sum()) for m, t in zip(ms, tiles))
        ca = sum(int(m.sum()) for m in ms)
        fp = int((ms[vi] & ~tiles[vi]["gt"]).sum())
        print(f"{k:<24} {r['precision']:8.4f} {r['recall']:8.4f} {r['iou']:8.4f} "
              f"{r['f1']:8.4f} {btp - tp:>9,} {bca - ca:>11,} {fp:>9,} "
              f"{100 * (bfp - fp) / max(bfp, 1):>10.2f}%")

    print("\nper-tile effect of the REAL mask (only tiles it touches)")
    for i, t in enumerate(tiles):
        rm = int((base[i] & ~real[i]).sum())
        if rm:
            print(f"  {t['frame']:<52} cand px removed {rm:>8,}  "
                  f"of which GT crack {int((base[i] & ~real[i] & t['gt']).sum()):>7,}")


if __name__ == "__main__":
    main()
