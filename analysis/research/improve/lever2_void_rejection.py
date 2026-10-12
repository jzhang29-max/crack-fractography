"""LEVER 2 -- precision: reject the off-specimen void without eating real crack.

ONE tile (MAR_H_HIP_CBS_0002__crop_3122_120) owns 93.9% of all false positives at the
shipped settings: 137,774 px of pure vacuum outside the specimen edge, marked as crack.
It contributes ZERO true positives, so every pixel of it is pure loss.

WHAT THIS FILE ESTABLISHES

1. The "off-specimen" framing is WRONG as an instrument. Every raw-uint16 signal that
   says "this region is not material" -- absolute darkness, texture-freeness (local std),
   interior-vs-ring contrast, degenerate histogram, entropy -- FAILS to separate the void
   from real crack on these tiles, because one real crack
   (260622_316_H_b4_CBS_02__crop_4695_807, gt overlap 1.00, 6914 px) is just as dark,
   just as flat and has an even more extreme ring contrast. See `signal_margins()`.

2. The only thing that separates them is SIZE, and specifically WIDTH. A crack has a
   bounded half-width; the void does not. Median Euclidean-distance-transform half-width:
   void 102.6 px, every other predicted region on the corpus <= 8.9 px.

3. The rejection rule is therefore a width rule, calibrated INSIDE each leave-one-
   specimen-out fold from the training specimens' own widest component, so no threshold
   is read off the tile it is tested on.

Run:  <sem-crack-detector/.venv/bin/python> -B lever2_void_rejection.py
"""
import sys, os
import numpy as np
from scipy import ndimage as ndi

ANALYSIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ANALYSIS not in sys.path:
    sys.path.insert(0, ANALYSIS)
import tilebench as TB
import crackpipe as CP

STRUCT8 = np.ones((3, 3), bool)


# ---------------------------------------------------------------- the rule ----
def component_halfwidths(pred):
    """(labels, n, median EDT half-width per label). Index 0 is unused.

    The EDT of a binary mask is distance-to-background, so inside one component it is
    that component's own local half-width; components are disjoint, so a single global
    transform is exact and there is no cross-talk between them."""
    lab, n = ndi.label(pred, structure=STRUCT8)
    if n == 0:
        return lab, 0, np.zeros(1)
    dt = ndi.distance_transform_edt(pred)
    w = np.zeros(n + 1)
    for i in range(1, n + 1):
        w[i] = np.median(dt[lab == i])
    return lab, n, w


def reject_wide(pred, max_halfwidth):
    """Drop every connected component whose MEDIAN half-width is >= max_halfwidth.

    Median, not max: a real crack that locally opens into a pore has a large max EDT but
    a small median. This rule can only remove pixels, so recall can never rise -- any
    improvement it shows is precision, and any recall it costs is visible immediately."""
    if max_halfwidth is None or not pred.any():
        return pred
    lab, n, w = component_halfwidths(pred)
    if n == 0:
        return pred
    keep = w < max_halfwidth
    keep[0] = False
    return keep[lab]


def fold_threshold(train_preds, mult):
    """Calibrate the width cap from the TRAINING specimens only: `mult` times the widest
    median half-width any predicted component reaches there. Void-blind by construction
    when the void's specimen is the held-out one."""
    worst = 0.0
    for p in train_preds:
        _, n, w = component_halfwidths(p)
        if n:
            worst = max(worst, float(w[1:].max()))
    return mult * worst if worst > 0 else None


# ------------------------------------------------------- signal comparison ----
def signal_margins(tiles, preds):
    """Every rejection signal the brief suggested, scored by how far the void sits from
    the nearest OTHER predicted region. margin > 1 means the signal separates."""
    K5 = np.ones((5, 5), np.float32) / 25.0
    rows = []
    for t, pred in zip(tiles, preds):
        if not pred.any():
            continue
        raw = t["raw"].astype(np.float32)
        m1 = ndi.convolve(raw, K5, mode="reflect")
        m2 = ndi.convolve(raw * raw, K5, mode="reflect")
        lstd = np.sqrt(np.maximum(m2 - m1 * m1, 0))
        lab, n = ndi.label(pred, structure=STRUCT8)
        dt = ndi.distance_transform_edt(pred)
        for i in range(1, n + 1):
            R = lab == i
            a = int(R.sum())
            ring = (ndi.binary_dilation(R, STRUCT8, iterations=12)
                    & ~ndi.binary_dilation(R, STRUCT8, iterations=3))
            if not ring.any():
                ring = ~R
            h = np.bincount(t["raw"][R].astype(np.int64) // 256, minlength=256).astype(float)
            h /= h.sum()
            rows.append(dict(
                frame=t["frame"], area=a, gt=float((R & t["gt"]).sum() / a),
                med_halfwidth=float(np.median(dt[R])), max_halfwidth=float(dt[R].max()),
                area_frac=a / R.size,
                local_std=float(np.median(lstd[R])),
                std_ratio=float(np.median(lstd[R]) / max(np.median(lstd[ring]), 1e-9)),
                floor_frac=float((t["raw"][R] == 0).mean()),
                entropy=float(-(h[h > 0] * np.log2(h[h > 0])).sum()),
                uniq_rate=len(np.unique(t["raw"][R])) / a,
                ring_contrast=float(raw[R].mean() / max(np.median(raw[ring]), 1e-9))))
    return rows


# ------------------------------------------------------------------ report ----
def per_tile_delta(tiles, base, new):
    """FP removed and TP removed, per tile. The number that decides whether a pooled
    gain was bought by deleting real crack somewhere else."""
    out = []
    for t, b, nw in zip(tiles, base, new):
        gone = b & ~nw
        out.append(dict(frame=t["frame"], specimen=t["specimen"],
                        fp_removed=int((gone & ~t["gt"]).sum()),
                        tp_removed=int((gone & t["gt"]).sum())))
    return out


def reject_blob_core(pred, r_big=50, r_small=10):
    """V2 -- excise the void BODY, not the whole connected component.

    reject_wide() deletes an entire component, so a real crack that merely TOUCHES the
    void is deleted with it. The synthetic-void positive control (25 tiles x 4 corners)
    showed that costs 38,896 true positives: there the pasted vacuum edge cuts across
    crack-rich material, which the one real void tile could not reveal because its
    detector output had zero true positives to lose.

    Instead: find pixels too thick to be crack (EDT >= r_big, above the 27.5 px maximum
    any real crack reaches on this corpus), grow them only through pixels that are still
    implausibly thick (EDT >= r_small) so growth cannot run down a thin crack, then
    dilate by r_small to recover the blob's own thin rind. Everything else survives.
    """
    if not pred.any():
        return pred
    dt = ndi.distance_transform_edt(pred)
    thick = dt >= r_big
    if not thick.any():
        return pred
    body = ndi.binary_propagation(thick, mask=(dt >= r_small), structure=STRUCT8)
    kill = ndi.binary_dilation(body, STRUCT8, iterations=int(r_small)) & pred
    return pred & ~kill


def synthetic_void_control(tiles, rule, n_corners=4, seed=0):
    """POSITIVE CONTROL. The corpus holds exactly ONE off-specimen void, so specificity
    can be measured on 25 tiles but sensitivity cannot be measured at all. This pastes
    the REAL vacuum pixel population (sampled from the void tile's own flooded region)
    into a corner of each of the other 25 tiles, re-runs the whole pipeline including
    the percentile stretch, and scores ONLY outside the injected corner.

    Returns the two numbers that matter: how often the rule fires, and how much real
    crack it eats OUTSIDE the corner -- i.e. crack that merely touches the void.
    """
    from skimage import exposure
    void = next(t for t in tiles if t["frame"].startswith("MAR_H_HIP_CBS_0002"))
    base = CP.predict(void["img8"])
    lab, n = ndi.label(base, structure=STRUCT8)
    biggest = lab == (1 + int(np.argmax([(lab == i).sum() for i in range(1, n + 1)])))
    vac = void["raw"][biggest]

    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:512, 0:512]
    corners = dict(TL=(yy + xx) < 440, BR=(yy + xx) > 584,
                   TR=(yy + (511 - xx)) < 440, BL=((511 - yy) + xx) < 440)
    rows, flood, removed, tp_eaten, fired, n_inj = [], 0, 0, 0, 0, 0
    for t in tiles:
        if t is void:
            continue
        for cn in list(corners)[:n_corners]:
            C = corners[cn]
            raw = t["raw"].copy()
            raw[C] = rng.choice(vac, size=int(C.sum()), replace=True)
            lo, hi = np.percentile(raw, [1.0, 99.5])
            img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                              out_range=(0, 255)).astype(np.uint8)
            pi = CP.predict(img8)
            pr = rule(pi)
            O = ~C
            rows.append(TB.counts(pr & O, t["gt"] & O))
            gone = pi & ~pr
            flood += int((pi & C).sum())
            removed += int((gone & C).sum())
            tp_eaten += int((gone & O & t["gt"]).sum())
            fired += int(gone.any())
            n_inj += 1
    return dict(rows=rows, n=n_inj, flood=flood, removed=removed,
                tp_eaten_outside=tp_eaten, fired=fired)


def main():
    import pickle
    from tilebench import _agg
    tiles = TB.load(with_raw=True)
    mad_grid = [5.0, 4.0, 3.5, 3.0, 2.5, 2.0]
    P = {k: [CP.predict(t["img8"], mad_k=k) for t in tiles] for k in mad_grid}
    rule = lambda p: reject_blob_core(p, 50, 10)

    print("\n#### 1. which signals separate the void from real crack? ####")
    rows = signal_margins(tiles, P[5.0])
    void = next(r for r in rows if r["frame"].startswith("MAR_H_HIP_CBS_0002"))
    other = [r for r in rows if r is not void]
    print(f"  {len(rows)} predicted regions; the void's gt overlap is {void['gt']:.4f}")
    print(f"  {'signal':<16}{'VOID':>13}{'best other':>13}  margin  verdict")
    for s, hi in [("med_halfwidth", 1), ("max_halfwidth", 1), ("area_frac", 1),
                  ("local_std", 0), ("std_ratio", 0), ("floor_frac", 1),
                  ("entropy", 0), ("uniq_rate", 0), ("ring_contrast", 0)]:
        ov = [r[s] for r in other]
        nearest = max(ov) if hi else min(ov)
        marg = (void[s] / max(nearest, 1e-9)) if hi else (nearest / max(void[s], 1e-9))
        print(f"  {s:<16}{void[s]:>13.4f}{nearest:>13.4f}  {marg:6.2f}x  "
              f"{'SEPARATES' if marg > 2 else 'FAILS'}")

    print("\n#### 2. scores ####")
    TB.evaluate("A  shipped, no rule", {"x": [TB.counts(p, t["gt"]) for p, t in zip(P[5.0], tiles)]})
    TB.evaluate("B  shipped + void excision (ZERO free parameters)",
                {"x": [TB.counts(rule(p), t["gt"]) for p, t in zip(P[5.0], tiles)]})
    TB.evaluate("C  mad_k grid, no rule (the known best)",
                {f"mk{k}": [TB.counts(p, t["gt"]) for p, t in zip(P[k], tiles)] for k in P})
    TB.evaluate("D  mad_k grid + void excision  <-- headline",
                {f"mk{k}": [TB.counts(rule(p), t["gt"]) for p, t in zip(P[k], tiles)] for k in P})

    print("\n#### 3. what the rule removed, per specimen, at FIXED mad_k ####")
    for mk in mad_grid:
        d = per_tile_delta(tiles, P[mk], [rule(p) for p in P[mk]])
        touched = [x for x in d if x["fp_removed"] or x["tp_removed"]]
        print(f"  mad_k {mk:<4} tiles touched {len(touched):>2}  "
              f"FP removed {sum(x['fp_removed'] for x in d):>7}  "
              f"TP removed {sum(x['tp_removed'] for x in d)}")

    print("\n#### 4. positive control: 100 synthetic voids ####")
    for nm, fn in [("V1 whole-component", lambda p: reject_wide(p, 25)),
                   ("V2 blob-core      ", rule)]:
        c = synthetic_void_control(tiles, fn)
        m = _agg(c["rows"])
        print(f"  {nm}  fired {c['fired']}/{c['n']}  flood removed "
              f"{100*c['removed']/max(c['flood'],1):.1f}%  TP eaten outside the corner "
              f"{c['tp_eaten_outside']:>6}   IoU outside {m['iou']:.4f}")

    print("\n#### 5. sabotage ####")
    sc = lambda fn: _agg([TB.counts(fn(p), t["gt"]) for p, t in zip(P[3.0], tiles)])["iou"]
    print(f"  intact                                   {sc(rule):.4f}")
    print(f"  no-op rule          (must be 0.2455)     {sc(lambda p: p):.4f}")
    print(f"  keep ONLY the excised part (must be ~0)  {sc(lambda p: p & ~rule(p)):.4f}")
    print(f"  r_big=0.5, excise everything (must be 0) {sc(lambda p: reject_blob_core(p, .5, .5)):.4f}")
    ix = [i for i, t in enumerate(tiles) if not t["frame"].startswith("MAR_H_HIP_CBS_0002")]
    a = _agg([TB.counts(P[3.0][i], tiles[i]["gt"]) for i in ix])
    b = _agg([TB.counts(rule(P[3.0][i]), tiles[i]["gt"]) for i in ix])
    print(f"  void tile EXCLUDED: {a['iou']:.4f} -> {b['iou']:.4f}  "
          f"(the rule must be a strict no-op here: {b['iou']-a['iou']:+.4f})")


if __name__ == "__main__":
    main()
