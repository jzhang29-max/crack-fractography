"""THE FULL-FRAME PAINT GATE. Six rules have died here; state the number before the gain.

Any predictor that can REMOVE a pixel the shipped build keeps must be priced against the
hand-painted correction masks on the 48 frames that carry one -- 70,041,625 painted crack
px, READ ONLY. The project's rule: delete less than 1% of the hand-marked crack the
shipped path keeps, and report how many individual frames lose more than 1%.

Two arms, and the difference between them is the whole design decision:

    standalone  prob >= tau                 -- a REPLACEMENT. It can delete, so it is
                gated, and a tile score means nothing until this number is on the table.
    additive    shipped_clean | prob >= tau -- a strict superset of what ships, so its
                deletion is 0. That is an argument, not a measurement: it is ASSERTED
                here per frame on the real micrographs, and the script fails loudly if
                any frame loses one painted pixel.

The net used on a frame is the LOSO fold net that never saw that frame's specimen; a
frame whose specimen contributes no tiles would have no honest fold, so those frames are
recorded with the fold that was used and counted separately.

A 512 px training tile is percentile-stretched by its own crop and a full micrograph by
the whole image, so inference is done in sliding 512 px windows z-scored window by
window -- the normalisation the net was actually trained on. A global one would feed it a
distribution it has never seen, which is the same class of mistake as the tile-trained
width feature that deleted 72.67% of the paint.

    python -B scl_gate.py --tag main --loss thin4 --tau 0.5 [--frames 6] [--no-tta]
"""
import os, sys, json, time, argparse, warnings
warnings.filterwarnings("ignore")
import numpy as np
from PIL import Image

APP = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
for p in (APP + "/analysis/research", APP + "/analysis/research/improve", APP + "/analysis",
          SEM + "/code", SEM + "/interior_active_learning/code"):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True
Image.MAX_IMAGE_PIXELS = None

import torch                      # noqa: E402
import tifffile                   # noqa: E402
from skimage import exposure      # noqa: E402
import detect_cracks as D         # noqa: E402
import scl_unet as U              # noqa: E402
import scl_cldice as C            # noqa: E402

PAINT = os.path.join(SEM, "interior_active_learning", "paint")
OUT = U.OUT


def contrast_kwargs_for(name):
    try:
        import unified_pipeline as up
        f = getattr(up, "contrast_kwargs_for", None)
        if f:
            return f(name)
    except Exception:
        pass
    return dict(low_pct=1.0, high_pct=99.5)


def load_frame(name):
    raw = tifffile.imread(os.path.join(SEM, "original", name + ".tif"))
    while raw.ndim > 2:
        raw = raw[..., 0]
    ck = contrast_kwargs_for(name)
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]
    corr = np.array(Image.open(os.path.join(PAINT, name + "_correction_mask.png")))
    while corr.ndim > 2:
        corr = corr[..., 0]
    if corr.shape != img8.shape:
        if corr.shape[0] >= y1 and corr.shape[1] >= x1:
            corr = corr[y0:y1, x0:x1]
        else:
            return None
    return img8, corr


@torch.no_grad()
def unet_frame(net, img8, win=512, stride=384, tta=True, threads=14):
    torch.set_num_threads(threads)
    H, W = img8.shape
    acc = np.zeros((H, W), np.float32); cnt = np.zeros((H, W), np.float32)

    def starts(n):
        if n <= win:
            return [0]
        s = list(range(0, n - win + 1, stride))
        if s[-1] != n - win:
            s.append(n - win)
        return s

    for y in starts(H):
        for x in starts(W):
            a = img8[y:y + win, x:x + win].astype(np.float32)
            a = (a - a.mean()) / max(a.std(), 1e-6)
            if tta:
                p = U.predict_prob(net, a[None])
            else:
                p = torch.sigmoid(net(torch.from_numpy(a[None, None])))[0, 0].numpy()
            acc[y:y + a.shape[0], x:x + a.shape[1]] += p
            cnt[y:y + a.shape[0], x:x + a.shape[1]] += 1
    return acc / np.maximum(cnt, 1)


def shipped_clean(img8):
    """The candidate stage the app ships, through scl_cldice's own definition so the
    frame and the tiles cannot disagree about what 'the current model' is."""
    flat = D.flatten_background(img8)
    return C.cand(C._up.segment_dark_regions(flat, img8=img8))


def load_net(tag, loss, spec, fallback):
    f = os.path.join(OUT, f"net_{tag}_{loss}_{spec}.pt")
    used, honest = spec, True
    if not os.path.exists(f):
        f = os.path.join(OUT, f"net_{tag}_{loss}_{fallback}.pt")
        used, honest = fallback, False
    z = torch.load(f, map_location="cpu", weights_only=False)
    net = U.UNet(cin=z["cin"], base=z["base"])
    net.load_state_dict(z["state"]); net.eval()
    return net, used, honest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="main")
    ap.add_argument("--loss", default="thin4")
    ap.add_argument("--tau", type=float, default=0.5)
    ap.add_argument("--frames", type=int, default=0)
    ap.add_argument("--no-tta", action="store_true")
    ap.add_argument("--threads", type=int, default=14)
    ap.add_argument("--save", default="")
    a = ap.parse_args()
    save = a.save or f"gate_{a.tag}_{a.loss}_{a.tau}.json"

    import tilebench as TB
    specs = sorted({t["specimen"] for t in TB.load()})
    fallback = "MAR_H_AS"

    names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(PAINT)
                   if f.endswith("_correction_mask.png"))
    names = [n for n in names if os.path.exists(os.path.join(SEM, "original", n + ".tif"))]
    if a.frames:
        names = names[:a.frames]
    print(f"{len(names)} painted frames | loss={a.loss} tau={a.tau} tta={not a.no_tta}", flush=True)

    rows, nets, t0 = [], {}, time.time()
    for i, n in enumerate(names, 1):
        got = load_frame(n)
        if got is None:
            print(f"[{i}/{len(names)}] {n}  SKIPPED (paint does not fit the image)", flush=True)
            rows.append(dict(frame=n, error="shape_mismatch")); continue
        img8, corr = got
        crack, notc = corr == 1, corr == 2
        shipped = shipped_clean(img8)
        kept = int((shipped & crack).sum())
        spec = next((s for s in sorted(specs, key=len, reverse=True) if n.startswith(s)), None)
        key = spec if spec in specs else fallback
        if key not in nets:
            nets[key] = load_net(a.tag, a.loss, key, fallback)
        net, used, honest = nets[key]
        prob = unet_frame(net, img8, tta=not a.no_tta, threads=a.threads)
        mine = prob >= a.tau
        add = shipped | mine
        d_std = int((shipped & crack & ~mine).sum())
        d_add = int((shipped & crack & ~add).sum())
        assert d_add == 0, f"{n}: the additive arm deleted {d_add} px -- union is not a union"
        r = dict(frame=n, specimen=spec, net=used, honest_fold=bool(honest),
                 painted=int(crack.sum()), kept=kept, del_standalone=d_std, del_additive=0,
                 npx=int(img8.size), area_shipped=int(shipped.sum()),
                 area_mine=int(mine.sum()), area_add=int(add.sum()),
                 std_crack=int((mine & crack).sum()), add_crack=int((add & crack).sum()),
                 notc=int(notc.sum()), shipped_notc=int((shipped & notc).sum()),
                 std_notc=int((mine & notc).sum()), add_notc=int((add & notc).sum()))
        rows.append(r)
        print(f"[{i}/{len(names)}] {n:<38} kept {kept:>10,}  standalone deletes "
              f"{d_std:>10,} ({100*d_std/max(kept,1):5.1f}%)  additive 0   "
              f"{'' if honest else '[NO OWN FOLD] '}{time.time()-t0:5.0f}s", flush=True)
        json.dump(rows, open(os.path.join(OUT, save), "w"))

    summarise(rows)


def summarise(rows):
    ok = [r for r in rows if "error" not in r]
    K = sum(r["kept"] for r in ok)
    print()
    for arm in ("standalone", "additive"):
        Dl = sum(r["del_" + arm] for r in ok)
        bad = [r["frame"] for r in ok if r["del_" + arm] > 0.01 * max(r["kept"], 1)]
        verdict = "PASSES" if 100 * Dl / max(K, 1) < 1.0 and not bad else "FAILS"
        print(f"  {arm:<11} deletes {Dl:,} of {K:,} kept hand-marked crack = "
              f"{100*Dl/max(K,1):.4f}%   frames losing >1%: {len(bad)} of {len(ok)}   {verdict}")
        if bad:
            print("      " + ", ".join(bad[:10]) + (" ..." if len(bad) > 10 else ""))
    for arm, fld in (("standalone", "std_crack"), ("additive", "add_crack")):
        c = sum(r[fld] for r in ok)
        print(f"  hand-marked crack kept: shipped {K:,} -> {arm} {c:,} "
              f"({100*(c-K)/max(K,1):+.2f}%)")
    N = sum(r["notc"] for r in ok)
    print(f"  hand-marked NOT-crack marked, of {N:,}: shipped "
          f"{sum(r['shipped_notc'] for r in ok):,} | standalone "
          f"{sum(r['std_notc'] for r in ok):,} | additive {sum(r['add_notc'] for r in ok):,}")
    A = sum(r["npx"] for r in ok)
    print(f"  area marked, of {A:,} px: shipped {sum(r['area_shipped'] for r in ok):,} "
          f"({100*sum(r['area_shipped'] for r in ok)/A:.2f}%) | standalone "
          f"{sum(r['area_mine'] for r in ok):,} ({100*sum(r['area_mine'] for r in ok)/A:.2f}%) "
          f"| additive {sum(r['area_add'] for r in ok):,} "
          f"({100*sum(r['area_add'] for r in ok)/A:.2f}%)")
    nh = [r["frame"] for r in ok if not r["honest_fold"]]
    print(f"  frames with no fold of their own (specimen contributes no tile): {len(nh)}")


if __name__ == "__main__":
    main()
