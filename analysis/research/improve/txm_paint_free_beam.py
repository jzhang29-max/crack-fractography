#!/usr/bin/env python3
"""Does the TXM crack annotation sit on the specimen, or on the beam beside it?

WHY THIS WAS RUN. The paper is being restricted to specimen series b2 and b3, and before
releasing those annotations or reporting a score from them it is worth asking the dullest
possible question about them: are the pixels an operator painted as CRACK pixels where
there is any material at all?

A transmission frame of a specimen has two populations. Where the beam crosses metal it
is attenuated, and the stored float32 array -- which is optical density, not transmitted
intensity -- reads around 1. Where the beam misses the specimen entirely it is not
attenuated and the array reads near 0. Free beam is therefore the one region in the frame
that is guaranteed to contain no crack, because it contains nothing.

WHAT IT FOUND, and it is not a small effect. On the six B3 frames carrying crack paint,
between 44% and 98% of the painted CRACK pixels have an optical density below 0.10, in
frames where only 0.8% to 6.4% of the whole frame does. On the twelve B2 frames the same
share is 0% to 7%, with one frame at 26%. Looking at the overlay settles what the number
means: on the B3 frames the green is a block flush with the right-hand edge of the image,
with a straight vertical boundary. A crack does not have a straight edge aligned with the
frame border. The operator painted past the specimen.

WHY IT MATTERS BEYOND THE RELEASE. The deployed detector proposes any pixel darker than
an absolute floor of 10 of 255, unconditionally, whatever the relative criterion says.
Free beam is near zero in optical density and is converted to near zero in the 8-bit
array the detector sees: the median painted-crack pixel on two B3 frames reads 0 and 1 of
255. So the absolute floor marks the painted region by construction, and B3 is the TXM
group that scores best. `modality_contrast.json` already records the split: on the median
B3 frame 94.5% of the painted crack is proposed and 59.0 points of that come from the
absolute floor ALONE, against 21.3% and 20.2 points on B2. The group's standout
performance is substantially the detector agreeing with an annotation that is not on the
specimen, through a gate that fires on anything near zero.

THREE THINGS THIS MODULE DOES RATHER THAN ASSERT.

  1. A THRESHOLD SWEEP. The conclusion must not hang on the number 0.10, so the share is
     reported at several densities and the separation between the groups is reported at
     each. If it only appears at one threshold it is a threshold artefact.

  2. A CONTROL ON THE OTHER LABEL. The same statistic is computed on the painted
     NOT-crack. If an operator were simply painting carelessly past the specimen edge,
     both labels would show it. If only the crack label does, the defect is specific to
     the class the paper scores.

  3. THE PICTURE. Every frame is written out as an overlay, because this is the kind of
     claim that a number can get backwards -- an earlier pass at this computed optical
     density as minus the logarithm of the stored value, which inverts the quantity, and
     got the opposite answer with a straight face.

    <sem-crack-detector>/.venv/bin/python -B analysis/research/improve/txm_paint_free_beam.py
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))
sys.dont_write_bytecode = True

import numpy as np                                  # noqa: E402
import tifffile                                     # noqa: E402

import _paths                                       # noqa: E402

sys.path.insert(0, os.path.join(_paths.SEM_REPO, "code"))
sys.path.insert(0, _paths.ANALYSIS)
import detect_cracks as D                           # noqa: E402

IMAGES = os.path.join(_paths.TXM_REPO, "images")
CORR = os.path.join(_paths.TXM_REPO, "paint", "corrections")
OUT = os.path.join(REPO, "docs", "figures", "txm_paint_free_beam.json")
EVID = os.path.join(REPO, "docs", "figures", "evidence", "txm_paint")

#: The optical densities the share is reported at. The claim is the SEPARATION between
#: the groups across all of them, not the value at any one.
OD_GRID = (0.05, 0.10, 0.20, 0.40)
#: The detector's absolute darkness floor, in the 8-bit array it is applied to. Imported
#: rather than retyped would be better, but detector_overrides pulls in the whole
#: installation; it is asserted against that module below instead.
ABS_GATE = 10


def group(stem):
    n = stem.lower()
    if "_b3_" in n:
        return "B3"
    if "wrought" in n:
        return "Wrought"
    if "hc_316l" in n:
        return "AM/HC"
    return "B2"


def main():
    import detector_overrides as DO
    if DO.ABSOLUTE_DARK_THRESH != ABS_GATE:
        raise SystemExit(
            f"this module reports the share of painted crack below {ABS_GATE} of 255 and "
            f"the installed detector's floor is {DO.ABSOLUTE_DARK_THRESH}. Update "
            f"ABS_GATE rather than publishing a share of the wrong constant.")
    os.makedirs(EVID, exist_ok=True)
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None

    rows = []
    for f in sorted(os.listdir(CORR)):
        if not f.endswith("_correction.npy"):
            continue
        stem = f[: -len("_correction.npy")]
        tif = os.path.join(IMAGES, stem + ".tif")
        if not os.path.exists(tif):
            continue
        corr = np.load(os.path.join(CORR, f))
        od = tifffile.imread(tif)
        if od.ndim > 2:
            od = od[..., 0]
        if od.shape != corr.shape:
            continue
        crack = corr == 1
        notc = (corr == 2) | (corr == 3)
        if not crack.any():
            continue
        img8 = D.load_as_uint8(tif)

        rec = {
            "frame": stem, "group": group(stem),
            "crack_px": int(crack.sum()), "notcrack_px": int(notc.sum()),
            "median_od_crack": round(float(np.median(od[crack])), 4),
            "median_od_notcrack": (round(float(np.median(od[notc])), 4)
                                   if notc.any() else None),
            "median_od_frame": round(float(np.median(od)), 4),
            "median_img8_crack": int(np.median(img8[crack])),
            "median_img8_frame": int(np.median(img8)),
            "crack_below_absolute_gate": round(float(np.mean(img8[crack] < ABS_GATE)), 4),
            "by_od_threshold": {},
        }
        for t in OD_GRID:
            rec["by_od_threshold"][f"{t:g}"] = {
                "crack": round(float(np.mean(od[crack] < t)), 4),
                "notcrack": (round(float(np.mean(od[notc] < t)), 4)
                             if notc.any() else None),
                "frame": round(float(np.mean(od < t)), 4),
            }
        rows.append(rec)

        # the picture, because this is a claim a number can get backwards
        lo, hi = np.percentile(od, [1, 99])
        g = np.clip((od.astype(np.float32) - lo) / max(float(hi - lo), 1e-9), 0, 1)
        rgb = np.dstack([g] * 3)
        rgb[crack] = [0.0, 0.835, 0.17]
        rgb[notc] = [0.843, 0.188, 0.122]
        s = max(1, max(od.shape) // 900)
        Image.fromarray((rgb[::s, ::s] * 255).astype(np.uint8)).save(
            os.path.join(EVID, f"{group(stem).replace('/', '-')}__{stem[:60]}.png"))

    by_group = {}
    for g in ("B3", "B2", "Wrought", "AM/HC"):
        sub = [r for r in rows if r["group"] == g]
        if not sub:
            continue
        by_group[g] = {
            "n": len(sub),
            "median_share_crack_below_od": {
                t: round(float(np.median([r["by_od_threshold"][t]["crack"]
                                          for r in sub])), 4) for t in
                (f"{t:g}" for t in OD_GRID)},
            "median_share_notcrack_below_od": {
                t: round(float(np.median([r["by_od_threshold"][t]["notcrack"]
                                          for r in sub
                                          if r["by_od_threshold"][t]["notcrack"]
                                          is not None])), 4) for t in
                (f"{t:g}" for t in OD_GRID)},
            "median_share_frame_below_od": {
                t: round(float(np.median([r["by_od_threshold"][t]["frame"]
                                          for r in sub])), 4) for t in
                (f"{t:g}" for t in OD_GRID)},
            "median_crack_below_absolute_gate": round(float(np.median(
                [r["crack_below_absolute_gate"] for r in sub])), 4),
            "median_img8_of_painted_crack": int(np.median(
                [r["median_img8_crack"] for r in sub])),
        }

    json.dump({
        "question": "are the pixels an operator painted as crack in the transmission "
                    "collection pixels where the beam crossed any material at all?",
        "convention": "the stored float32 array is OPTICAL DENSITY, not transmitted "
                      "intensity: free beam reads near 0 and the attenuating bulk reads "
                      "near 1. Computing minus the logarithm of the stored value inverts "
                      "the quantity and reverses every conclusion below; an earlier pass "
                      "did exactly that.",
        "od_grid": list(OD_GRID),
        "absolute_gate": ABS_GATE,
        "controls": {
            "other_label": "the same share is computed on the painted NOT-crack. A "
                           "operator painting carelessly past the specimen edge would "
                           "show it on both labels; a defect specific to the crack class "
                           "shows on one.",
            "threshold_sweep": "the share is reported at four densities so the "
                               "separation between groups cannot rest on one constant",
            "overlays": "every frame is written to docs/figures/evidence/txm_paint/",
        },
        "by_group": by_group,
        "frames": rows,
    }, open(OUT, "w"), indent=1)

    print(f"  wrote {OUT}\n")
    print(f"  {'group':<8} {'n':>2}  share of painted CRACK below OD "
          f"{', '.join(f'{t:g}' for t in OD_GRID)}")
    for g, v in by_group.items():
        s = v["median_share_crack_below_od"]
        n = v["median_share_notcrack_below_od"]
        fr = v["median_share_frame_below_od"]
        print(f"  {g:<8} {v['n']:>2}  crack    " +
              "  ".join(f"{100 * s[f'{t:g}']:5.1f}%" for t in OD_GRID))
        print(f"  {'':<8} {'':>2}  notcrack " +
              "  ".join(f"{100 * n[f'{t:g}']:5.1f}%" for t in OD_GRID))
        print(f"  {'':<8} {'':>2}  frame    " +
              "  ".join(f"{100 * fr[f'{t:g}']:5.1f}%" for t in OD_GRID))
        print(f"  {'':<8} {'':>2}  median painted-crack value {v['median_img8_of_painted_crack']}"
              f" of 255; {100 * v['median_crack_below_absolute_gate']:.1f}% of it below "
              f"the detector's absolute floor of {ABS_GATE}\n")


if __name__ == "__main__":
    main()
