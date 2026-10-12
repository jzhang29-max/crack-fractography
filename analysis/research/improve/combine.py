"""Do the levers STACK? Each agent saw only its own, and three of them overlap.

The three strongest results all say, independently, that the shipped region classifier is
the problem: lever 3 found a one-line threshold matching its 35-feature model, lever 4
attributed +0.126 of its +0.178 gain to simply DELETING the classifier, and lever 6 got
from 0.2143 to 0.4940 parameter-free by deleting it and adding a texture veto. So the
untested combination is the obvious one: lever 1's multi-scale candidates (which raise
candidate recall from 53% to 71%) feeding lever 6's no-classifier path (which stops the
classifier throwing them away again).

Every arm below runs through tilebench, so selection is leave-one-SPECIMEN-out and the
fitted/held-out gap is printed. Parameter counts are stated because each free parameter is
a chance to fit 26 tiles, and the mad_k+threshold trap already cost 0.02 IoU that way.
"""
import os, sys
import numpy as np
from scipy import ndimage as ndi
from skimage import filters

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research")
sys.dont_write_bytecode = True
import tilebench as TB, crackpipe as CP
import detect_cracks as D

SIGMAS = (5, 10, 20, 40, 80, 160, 320)


def local_std(a, r=16):
    a = np.asarray(a, np.float32)
    m = ndi.uniform_filter(a, 2 * r + 1)
    m2 = ndi.uniform_filter(a * a, 2 * r + 1)
    return np.sqrt(np.maximum(m2 - m * m, 0)).astype(np.float32)


def precompute(tiles):
    """flatten_background is a high-pass, so each sigma sees a different band of the
    image. Computed once per tile per sigma and reused by every arm, so all arms are
    scored on identical pixels -- a second flattening pass would be a second instrument."""
    pre = []
    for i, t in enumerate(tiles, 1):
        P = dict(t)
        P["smooth"], P["stat"] = {}, {}
        for s in SIGMAS:
            f = D.flatten_background(t["img8"], sigma=s)
            sm = filters.gaussian(f, sigma=1.0, preserve_range=True)
            med = float(np.median(sm)); mad = float(np.median(np.abs(sm - med)) * 1.4826)
            P["smooth"][s] = sm
            P["stat"][s] = dict(otsu=float(filters.threshold_otsu(sm)), med=med, mad=mad)
        P["flat40"] = D.flatten_background(t["img8"], sigma=40)
        P["lstd40"] = local_std(P["flat40"])
        pre.append(P)
        print(f"  precompute [{i:>2}/{len(tiles)}] {t['frame'][:44]}", flush=True)
    return pre


def cut(P, s, k):
    st = P["stat"][s]
    return P["smooth"][s] < min(st["otsu"], st["med"] - k * st["mad"])


def vote_mask(P, k, nvote):
    v = np.zeros(P["img8"].shape, np.uint8)
    for s in SIGMAS:
        v += cut(P, s, k).astype(np.uint8)
    return (v >= nvote) | (P["img8"] < 10)


def veto(mask, P, floor):
    """A crack must be at least as textured as the matrix it runs through. floor=1.0 is
    the natural boundary of that sentence, not a fitted number: the off-specimen void is
    17x FLATTER than the material around it, while a real crack sits in textured metal."""
    if floor <= 0:
        return mask
    base = max(float(np.median(P["lstd40"])), 1e-6)
    lab, n = ndi.label(mask)
    if n == 0:
        return mask
    keep = np.zeros(n + 1, bool)
    for i in range(1, n + 1):
        keep[i] = (float(np.median(P["lstd40"][lab == i])) / base) >= floor
    return keep[lab]


def clean(m):
    return D.clean_mask(m, min_area_px=13)


def main():
    tiles = TB.load()
    print("CONTROLS"); assert TB.controls(), "controls failed"
    pre = precompute(tiles)
    C = lambda masks: [TB.counts(m, t["gt"]) for m, t in zip(masks, tiles)]
    R = {}

    R["A shipped (0 params)"] = TB.evaluate(
        "A shipped detector [0 params]", {"x": C([CP.predict(t["img8"]) for t in tiles])})

    R["B mad_k only, classifier kept (1)"] = TB.evaluate(
        "B mad_k swept, shipped classifier kept [1 param]",
        {f"k{k}": C([CP.predict(t["img8"], mad_k=k) for t in tiles])
         for k in (5.0, 4.0, 3.0, 2.5, 2.0)})

    R["C no classifier (0)"] = TB.evaluate(
        "C shipped candidates, classifier DELETED [0 params]",
        {"x": C([clean(cut(P, 40, 5.0) | (P["img8"] < 10)) for P in pre])})

    R["D no classifier + texture veto (0)"] = TB.evaluate(
        "D classifier deleted + texture veto floor=1.0 [0 params]",
        {"x": C([veto(clean(cut(P, 40, 5.0) | (P["img8"] < 10)), P, 1.0) for P in pre])})

    grid = {}
    for k in (5.0, 4.0, 3.0, 2.5, 2.0):
        base = [clean(cut(P, 40, k) | (P["img8"] < 10)) for P in pre]
        for fl in (0.75, 1.0, 1.25):
            grid[f"k{k}_f{fl}"] = C([veto(m, P, fl) for m, P in zip(base, pre)])
        print(f"  single-scale grid k={k}", flush=True)
    R["E lever6: + mad_k x floor (2)"] = TB.evaluate(
        "E classifier deleted + veto, mad_k x floor LOSO [2 params]", grid)

    # --- the untested combination -------------------------------------------------------
    msv = {}
    for k in (5.0, 4.0, 3.0, 2.5, 2.0):
        for nv in (2, 3, 4):
            base = [clean(vote_mask(P, k, nv)) for P in pre]
            for fl in (0.75, 1.0, 1.25):
                msv[f"k{k}_n{nv}_f{fl}"] = C([veto(m, P, fl) for m, P in zip(base, pre)])
        print(f"  multiscale grid k={k}", flush=True)
    R["F MULTISCALE + no classifier + veto (3)"] = TB.evaluate(
        "F multi-scale vote + classifier deleted + veto, k x nvote x floor LOSO [3 params]", msv)

    R["G same, nvote=3 and floor=1.0 pinned (1)"] = TB.evaluate(
        "G multi-scale vote, nvote=3 & floor=1.0 PINNED a priori, only k swept [1 param]",
        {kk: v for kk, v in msv.items() if "_n3_f1.0" in kk})

    R["H fully pinned: k=2.5,n=3,f=1.0 (0)"] = TB.evaluate(
        "H multi-scale fully pinned [0 params]", {"x": msv["k2.5_n3_f1.0"]})

    print("\n" + "=" * 96)
    print("SUMMARY -- held-out (leave-one-specimen-out), the only numbers to quote")
    print(f"  {'arm':<44} {'prec':>7} {'recall':>7} {'IoU':>7} {'F1':>7} {'gap':>8}")
    for name, r in R.items():
        m = r["loso"]
        print(f"  {name:<44} {m['precision']:7.4f} {m['recall']:7.4f} {m['iou']:7.4f} "
              f"{m['f1']:7.4f} {r['overfit_gap']:+8.4f}")
    import json
    json.dump({k: dict(loso=v["loso"], loso_tol2=v["loso_tol2"], fitted=v["fitted"],
                       gap=v["overfit_gap"], picks=v["picks"], per_specimen=v["per_specimen"])
               for k, v in R.items()},
              open(os.path.join(TB.SC, "combine.json"), "w"), indent=1)
    print(f"\nwrote {TB.SC}/combine.json")


if __name__ == "__main__":
    main()
