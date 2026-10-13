"""THE FULL-FRAME PAINT GATE. State this number before stating any gain.

A U-Net that replaces the shipped candidate stage can remove pixels, so it is subject to
the gate six previous rules have died on: across all 48 hand-painted frames it must delete
LESS THAN 1% of the hand-marked crack the shipped path keeps. The tiles cannot see this.
A 512 px tile cannot even contain a wide crack -- tile paint tops out at 43.7 px mean
width while real crack regions reach 178 px -- which is exactly how the last attempt
scored well on tiles and then deleted 72.67% of the hand paint on full frames.

Denominator: hand-marked crack (correction mask == 1) that the SHIPPED path keeps.
Numerator: that same set, minus the candidate arm under test.
Reported in total and per frame, with a count of frames individually over 1%.

The paint is READ ONLY.
"""
import os, sys, json, argparse
import numpy as np

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True
import torch
import unetctx_base as B
import unetctx_train as TR
import ctx_core as CC
import detect_cracks as D

CACHE = os.path.join(B.MY, "gate")
os.makedirs(CACHE, exist_ok=True)


def shipped_frame(name):
    """The shipped v1.49.1 candidate mask on a full frame, plus its flattened input."""
    f = os.path.join(CACHE, "ship_" + name + ".npz")
    if os.path.exists(f):
        try:
            z = np.load(f)
            return z["flat"], z["cur"].astype(bool), z["corr"]
        except Exception:
            os.remove(f)
    img8, corr = B.load_frame(name)
    flat = D.flatten_background(img8)
    cur = CC.cand(CC.SEG(flat, img8=img8))
    np.savez_compressed(f, flat=flat.astype(np.uint8), cur=cur, corr=corr)
    return flat.astype(np.uint8), cur, corr


def unet_frame(name, arm, holdout, seed=0, stride=128):
    f = os.path.join(CACHE, f"p_{arm}__{holdout or 'ALL'}__s{seed}__{name}.npy")
    if os.path.exists(f):
        try:
            return np.load(f)
        except Exception:
            os.remove(f)
    flat, _, _ = shipped_frame(name)
    net = TR.load_net(TR.train_fold(arm, holdout, seed))
    p = TR.predict_prob(net, flat, stride=stride)
    np.save(f, (p * 255).astype(np.uint8))
    return (p * 255).astype(np.uint8)


def run(arm, names, seed=0, union=False, stride=128):
    """Returns per-frame deletion of hand-marked crack the shipped path keeps."""
    paint_specs = {B.specimen_of(n) for n in B.frame_names()}
    out = []
    for name in names:
        flat, cur, corr = shipped_frame(name)
        marked_kept = (corr == 1) & cur
        hold = B.specimen_of(name) if B.specimen_of(name) in paint_specs else None
        p = unet_frame(name, arm, hold, seed, stride).astype(np.float32) / 255.0
        mine = TR.mask_from_prob(p, area_frac=float(cur.mean()))
        if union:
            mine = mine | cur
        out.append(dict(frame=name, kept=int(marked_kept.sum()),
                        deleted=int((marked_kept & ~mine).sum()),
                        added=int((mine & ~cur).sum()),
                        cur_area=float(cur.mean()), my_area=float(mine.mean())))
        print(f"  {name:<34} kept {out[-1]['kept']:>10,}  deleted {out[-1]['deleted']:>10,} "
              f"({100*out[-1]['deleted']/max(out[-1]['kept'],1):6.2f}%)", flush=True)
    return out


def verdict(rows, label):
    k = sum(r["kept"] for r in rows); d = sum(r["deleted"] for r in rows)
    pct = 100 * d / max(k, 1)
    over = [r["frame"] for r in rows
            if r["kept"] > 0 and 100 * r["deleted"] / r["kept"] > 1.0]
    print(f"\n  {label}")
    print(f"    hand-marked crack the shipped path keeps : {k:,} px over {len(rows)} frames")
    print(f"    deleted by this arm                      : {d:,} px = {pct:.2f}%")
    print(f"    frames individually losing more than 1%  : {len(over)} / {len(rows)}")
    if over:
        print("      " + ", ".join(over[:12]) + (" ..." if len(over) > 12 else ""))
    print(f"    {'PASS' if pct < 1.0 and not over else 'FAIL'} the <1% gate"
          f"{'' if pct < 1.0 else '  -- DISQUALIFIED'}")
    return dict(pct=pct, kept=k, deleted=d, n_over=len(over), frames_over=over,
                passes=bool(pct < 1.0))


def headroom(names, arm="thin", seed=0, mults=(1, 2, 3, 4, 6, 8)):
    """How far must the arm OVER-MARK before it stops deleting hand paint?

    A failing gate number on its own does not say whether the model is looking in the
    wrong place or merely spending a smaller budget differently. This answers that: at
    each multiple of the shipped detector's own marked area, how much of the hand-marked
    crack the shipped path keeps is still missing.
    """
    tot = {m: 0 for m in mults}
    kept = 0
    print(f"{'frame':<34} {'ship area':>10} " + "".join(f"{'x'+str(m):>8}" for m in mults))
    for n in names:
        flat, cur, corr = shipped_frame(n)
        mk = (corr == 1) & cur
        if not mk.any():
            continue
        p = unet_frame(n, arm, B.specimen_of(n), seed).astype(np.float32) / 255.0
        kept += int(mk.sum())
        cells = []
        for m in mults:
            msk = TR.mask_from_prob(p, area_frac=min(float(cur.mean()) * m, 0.98))
            d = int((mk & ~msk).sum()); tot[m] += d
            cells.append(100 * d / int(mk.sum()))
        print(f"{n:<34} {100*cur.mean():9.1f}% " +
              "".join(f"{c:7.1f}%" for c in cells), flush=True)
    print(f"{'TOTAL % of kept hand crack deleted':<34} {'':>10} " +
          "".join(f"{100*tot[m]/max(kept,1):7.2f}%" for m in mults))
    return {str(m): 100 * tot[m] / max(kept, 1) for m in mults}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--union", action="store_true")
    ap.add_argument("--frames", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--headroom", action="store_true")
    a = ap.parse_args()
    torch.set_num_threads(int(os.environ.get("NT", "10")))
    names = a.frames.split(",") if a.frames else B.frame_names()
    if a.headroom:
        h = headroom(names, a.arm, a.seed)
        if a.json:
            json.dump(h, open(a.json, "w"), indent=1)
        sys.exit(0)
    rows = run(a.arm, names, a.seed, a.union)
    v = verdict(rows, f"{a.arm}{' UNION shipped' if a.union else ' (replacement)'}")
    if a.json:
        json.dump(dict(rows=rows, verdict=v), open(a.json, "w"), indent=1, default=float)
