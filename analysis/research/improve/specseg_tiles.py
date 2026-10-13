"""SECONDARY: the 26 hand-labelled tiles, scored through analysis/research/tilebench.py.

The point of ANGLE 2 is that the specimen is a FRAME-SCALE object. A 512 px crop cannot
tell you whether it is standing on material -- which is exactly why the off-specimen void
tile (MAR_H_HIP_CBS_0002__crop_3122_120_512x512, owner of 82-86% of all candidate-stage
false positives) is unfixable from inside the tile. So the specimen mask is computed on
the tile's PARENT MICROGRAPH, in the same coordinates the app uses, and then cropped to
the tile box. Nothing else about the tile pipeline changes.

Scoring goes through tilebench.evaluate and nothing else: leave-one-SPECIMEN-out variant
selection, MAR_AmbB_AS excluded, fitted and held-out both printed with the gap. A second
scorer would make the gain unreadable.

The candidate stage is the one that ships -- the multi-scale union taken from
detector_overrides.install() itself. Sanity-checked by collapsing SCALE_LADDER to (40,),
which must reproduce the stock single-scale mask exactly.
"""
import os, sys, json
import warnings; warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
R_DIR = os.path.dirname(HERE)
for p in (HERE, R_DIR, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis",
          "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/code",
          "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/interior_active_learning/code"):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
import tilebench as TB
import detect_cracks as D
import specimen_mask as SM
import specseg_cache as FC

SC = TB.SC
SEM = TB.SEM
PCACHE = os.path.join(FC.WORK, "parentcache")


def parent_blocks(parent):
    """8x8 block mean/std of the parent micrograph, in the app's FOV coordinates."""
    os.makedirs(PCACHE, exist_ok=True)
    f = os.path.join(PCACHE, parent + ".npz")
    if os.path.exists(f):
        z = np.load(f)
        return z["bmean"], z["bstd"], tuple(int(v) for v in z["shape"]), tuple(int(v) for v in z["fov"])
    import tifffile
    from skimage import exposure
    from common import contrast_kwargs_for
    raw = tifffile.imread(os.path.join(SEM, "original", parent + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    ck = contrast_kwargs_for(parent)
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]
    bm, bs = SM.blocks(img8)
    np.savez_compressed(f, bmean=bm, bstd=bs, shape=np.array(img8.shape),
                        fov=np.array([x0, y0, x1, y1]))
    return bm, bs, img8.shape, (x0, y0, x1, y1)


def parent_specimen(parent, v):
    bm, bs, shape, fov = parent_blocks(parent)
    return SM.upsample(SM.build(bm, bs, v), shape), shape


def crop_to_box(full, box):
    x, y, w, h = box
    out = np.ones((h, w), bool)
    sub = full[y:y + h, x:x + w]
    out[:sub.shape[0], :sub.shape[1]] = sub
    return out


def tile_specimen(tile, v):
    """The parent's specimen mask, cropped to this tile's box.

    The tile cache cuts tiles out of the parent after trimming the databar to the machine
    mask's height; find_field_of_view on these parents returns exactly that crop
    (x0=0, y0=0, x1=width), which _check_coords() asserts rather than assumes. If a
    parent ever disagreed, the tile box would not be in FOV coordinates and the crop
    would be silently wrong.
    """
    bm, bs, shape, fov = parent_blocks(tile["parent"])
    S, T, E = SM.specimen_coarse(bm, bs, **{k: v[k] for k in
                                            ("kind", "rule", "close_px", "grow_px")})
    full = SM.upsample(S, shape)
    x, y, w, h = tile["box"]
    out = np.ones((h, w), bool)
    sub = full[y:y + h, x:x + w]
    out[:sub.shape[0], :sub.shape[1]] = sub
    return out


def _check_coords(tiles):
    ok = True
    for t in {tt["parent"]: tt for tt in tiles}.values():
        _, _, shape, fov = parent_blocks(t["parent"])
        x0, y0, x1, y1 = fov
        good = (x0 == 0 and y0 == 0 and x1 == shape[1] and y1 == shape[0])
        if not good:
            print(f"  CONTROL FAIL {t['parent']}: fov {fov} vs shape {shape}")
        ok &= good
    print(f"  CONTROL every tile parent's FOV is a pure databar trim "
          f"(x0=0,y0=0,x1=w): {'PASS' if ok else 'FAIL'}")
    return ok


_SEG = {}


def shipped_candidates(img8, ladder=None):
    key = ladder or "ship"
    if key not in _SEG:
        import detector_overrides as DO

        class _Stub:
            pass

        up = _Stub()
        kw = dict(use_multiscale_union=True)
        if ladder:
            kw["scale_ladder"] = ladder
        DO.install(up, **kw)
        _SEG[key] = up.segment_dark_regions
    flat = D.flatten_background(img8, sigma=40)
    return D.clean_mask(_SEG[key](flat, img8=img8), open_radius=1, close_radius=3,
                        min_area_px=13)


VARIANTS = SM.GRID


key = SM.vkey


def main():
    tiles = TB.load(with_raw=False)
    meta = {t["frame"]: t for t in json.load(open(os.path.join(SC, "tiles_meta.json")))}
    print(f"{len(tiles)} tiles, {len({t['specimen'] for t in tiles})} specimens")
    print("\nINSTRUMENT CONTROLS")
    assert _check_coords([meta[t["frame"]] for t in tiles])
    t0 = tiles[0]
    a = shipped_candidates(t0["img8"], ladder=(40,))
    b = D.clean_mask(D.segment_dark_regions(D.flatten_background(t0["img8"], sigma=40),
                                            img8=t0["img8"]), open_radius=1,
                     close_radius=3, min_area_px=13)
    print(f"  CONTROL union at ladder=(40,) == stock single-scale cut: "
          f"{'PASS' if np.array_equal(a, b) else 'FAIL'}")
    assert np.array_equal(a, b)
    print(f"  CONTROL EDT closing == dilate+erode: "
          f"{'PASS' if SM._selfcheck_close() else 'FAIL'}")
    print()
    TB.controls()

    base = [shipped_candidates(t["img8"]) for t in tiles]
    parents = sorted({meta[t["frame"]]["parent"] for t in tiles})
    masks = {}
    for i, v in enumerate(VARIANTS, 1):
        pm = {p: parent_specimen(p, v)[0] for p in parents}
        masks[key(v)] = [b & crop_to_box(pm[meta[t["frame"]]["parent"]],
                                         meta[t["frame"]]["box"])
                         for b, t in zip(base, tiles)]
        if i % 20 == 0:
            print(f"    {i}/{len(VARIANTS)} variants", flush=True)

    cnt = {"shipped (no specimen mask)": [TB.counts(m, t["gt"]) for m, t in zip(base, tiles)]}
    for k, ms in masks.items():
        cnt[k] = [TB.counts(m, t["gt"]) for m, t in zip(ms, tiles)]

    print("\n--- single-variant (0 free parameters: fitted == held-out) ---")
    singles = {}
    for k in list(cnt):
        singles[k] = TB.evaluate(k, {k: cnt[k]}, quiet=True)
        m = singles[k]["loso"]
        print(f"  {k:<34} P {m['precision']:.4f} R {m['recall']:.4f} "
              f"IoU {m['iou']:.4f} F1 {m['f1']:.4f}")

    print("\n--- void-tile false positives removed ---")
    vi = next((i for i, t in enumerate(tiles) if t["frame"] == TB.FLOODED), None)
    if vi is not None:
        bfp = int((base[vi] & ~tiles[vi]["gt"]).sum())
        tot_fp = sum(int((b & ~t["gt"]).sum()) for b, t in zip(base, tiles))
        print(f"  void tile {TB.FLOODED}")
        print(f"  it owns {bfp:,} of {tot_fp:,} candidate false-positive px "
              f"({100*bfp/max(tot_fp,1):.1f}% of all FP on the 26 tiles)")
        for k, ms in masks.items():
            fp = int((ms[vi] & ~tiles[vi]["gt"]).sum())
            print(f"    {k:<34} void FP {fp:>8,}  removed {100*(bfp-fp)/max(bfp,1):6.2f}%")

    print("\n--- LOSO variant selection over the whole grid (this is the honest read) ---")
    TB.evaluate("specimen mask, R and threshold chosen leave-one-specimen-out",
                {k: v for k, v in cnt.items() if k != "shipped (no specimen mask)"})
    TB.evaluate("shipped + every specimen-mask variant, chosen leave-one-specimen-out", cnt)

    json.dump({k: v for k, v in cnt.items()},
              open(os.path.join(FC.WORK, "tilecounts.json"), "w"))
    print(f"\nwrote {os.path.join(FC.WORK, 'tilecounts.json')}")


if __name__ == "__main__":
    main()
