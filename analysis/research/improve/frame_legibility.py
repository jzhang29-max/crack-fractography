"""Which frame should a figure be drawn from? Measure it, rather than choosing by eye.

Three figures in this paper show one frame of each collection, and which frame is chosen
changes what a reader believes. Picking by eye is how a paper ends up showing its best
case without saying so, and picking the median by score is how this one ended up with a
TXM panel that reproduced as a grey smudge: the frame that is typical by accuracy margin
is not necessarily a frame on which anything can be seen.

So the properties a figure actually needs are measured, per frame, and the selection rule
in each generator is written against these numbers:

  sharpness          the 99.5th percentile of Sobel gradient magnitude divided by the
                     frame's own intensity standard deviation. Scale-free, so a crisp
                     frame and a blurred mosaic average are comparable. These TXM mosaics
                     range over a factor of three on it.
  recall, precision  whether the shipped rule marks the operator's crack on that frame at
                     all. A stage figure whose last column is empty shows nothing.
  fp spread          the number of connected false-positive components and the share of
                     the false-positive area the largest of them holds. A frame where one
                     object is 99% of the over-counting illustrates that object, not
                     over-counting, and that is exactly what the first over-counting
                     panel showed.
  trace or region    carried over from paint_region_vs_trace.json, because a window
                     inside a broad-brush annotation is a picture of the brush.

Both paint directories are opened READ-ONLY.

    <sem-crack-detector>/.venv/bin/python -B analysis/research/improve/frame_legibility.py
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import numpy as np                                      # noqa: E402
from scipy import ndimage as ndi                        # noqa: E402
from skimage import filters                             # noqa: E402

import overlap_means_sem_txm as OV                      # noqa: E402  -- the loaders

REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

# ----------------------------------------------- specimen-series scope: b2 and b3 only
#: WHY THIS EXISTS. A reviewer restricted the paper's own laboratory specimens to series
#: b2 and b3 in BOTH microscopies; the corpus also carries SEM b4 and MAR_*/AS_*/Cast_*/
#: HIP_*, and TXM Wrought and AM/HC, which are other specimens.
#:
#: THE PREDICATE IS NOT REDEFINED HERE. This file does not enumerate frames itself -- it
#: iterates `OV.sem_frames()` and `OV.txm_frames()` -- so the scope filter lives there, in
#: one place, keyed on the same environment variable, and this file only has to agree
#: about the filenames.
#:
#: THE TRACES FILE IS AN INPUT, NOT AN OUTPUT. `deep_share` is a property of one frame's
#: paint, so the scoped and unscoped records of it are the same numbers over different
#: frame sets. The scoped file is preferred when it exists, purely so a scoped run reads a
#: scoped pipeline; the full-corpus file is a valid fallback because it is a superset and
#: every in-scope frame is in it. Either way the lookup returns the same value.
#:
#: OFF by default: unset, this file measures and writes exactly what it always did under
#: exactly the same filename. Nothing about sharpness, the 0.25 trace cut, the detector
#: call or the selection rules is touched.
#:
#:     SCOPE_B2B3=1 <sem-crack-detector>/.venv/bin/python -B <this file>
SCOPE = OV.SCOPE
SCOPE_ON = OV.SCOPE_ON
SUFFIX = OV.SUFFIX

OUT = os.path.join(REPO, "docs", "figures", f"frame_legibility{SUFFIX}.json")
TRACES = os.path.join(REPO, "docs", "figures", f"paint_region_vs_trace{SUFFIX}.json")
if not os.path.exists(TRACES):
    TRACES = os.path.join(REPO, "docs", "figures", "paint_region_vs_trace.json")


def sharpness(img8):
    """High-frequency content, in units of the frame's own intensity spread."""
    g = filters.sobel(img8.astype(np.float32))
    sd = float(img8.astype(np.float32).std()) or 1.0
    return float(np.percentile(g, 99.5) / sd)


def run(label, it, grouper=None):
    deep = {r["frame"]: r["deep_share"]
            for r in json.load(open(TRACES))[label]["frames"]}
    rows = []
    for nm, img8, corr in it:
        pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
        if pos.sum() < OV.MIN_PX or neg.sum() < OV.MIN_PX:
            continue
        m = OV.clean(OV.u.segment_dark_regions(OV.D.flatten_background(img8), img8=img8,
                                               mad_k=OV.MADK))
        tp, fp, fn = int((m & pos).sum()), int((m & neg).sum()), int((~m & pos).sum())
        lab, n = ndi.label(m & neg, np.ones((3, 3), bool))
        sz = np.bincount(lab.ravel())
        sz[0] = 0
        row = {"frame": nm, "sharpness": sharpness(img8),
               "trace": bool(deep.get(nm, 1.0) <= 0.25), "deep_share": deep.get(nm),
               "recall": tp / max(tp + fn, 1), "precision": tp / max(tp + fp, 1),
               "f1": 2 * tp / max(2 * tp + fp + fn, 1),
               "fp_px": fp, "fp_components": int(n),
               "fp_largest_share": (float(sz.max()) / fp) if (n and fp) else 0.0,
               "fn_px": fn}
        if grouper:
            row["group"] = grouper(nm)
        rows.append(row)
        print(f"  {nm[:52]:<54} sharp {row['sharpness']:5.2f}  R {row['recall']:.3f} "
              f"P {row['precision']:.3f}  fp {fp:>9,} in {n:>4} comps, largest "
              f"{100 * row['fp_largest_share']:5.1f}%", flush=True)
    return rows


def main():
    if SCOPE_ON:
        print(f"SCOPE_B2B3 is set: specimen series {SCOPE} only, in both microscopies; "
              f"output gains the '{SUFFIX}' suffix")
    print(f"deep_share read from {TRACES}\n")
    res = {
        "sharpness": "99.5th percentile of Sobel gradient magnitude divided by the "
                     "frame's own intensity standard deviation",
        "fp_largest_share": "the share of the false-positive AREA held by its largest "
                            "connected component; a frame near 1.0 has one object, not a "
                            "tendency",
        "trace": "deep share at most 0.25 in paint_region_vs_trace.json",
        "mad_k": OV.MADK,
        "SEM": run("SEM", OV.sem_frames()),
        "TXM": run("TXM", OV.txm_frames(), OV.txm_group),
    }
    if SCOPE_ON:
        res["specimen_scope"] = list(SCOPE)   # only on a filtered run
    assert SCOPE_ON == OUT.endswith("_b2b3.json"), "a scoped run must not write the full file"
    json.dump(res, open(OUT, "w"), indent=1)
    print("\nwrote", OUT)
    for tag in ("SEM", "TXM"):
        ok = [r for r in res[tag] if r["trace"] and r["recall"] >= 0.25]
        if ok:
            b = max(ok, key=lambda r: r["sharpness"])
            print(f"  {tag}: sharpest trace frame reaching a quarter of the paint is "
                  f"{b['frame'][:48]} (sharpness {b['sharpness']:.2f}, "
                  f"recall {b['recall']:.3f})")
        sc = [r for r in res[tag] if r["trace"] and r["fp_largest_share"] <= 0.35]
        if sc:
            b = max(sc, key=lambda r: r["fp_px"])
            print(f"  {tag}: most over-counting not dominated by one object is "
                  f"{b['frame'][:48]} ({b['fp_px']:,} px in {b['fp_components']} "
                  f"components, largest {100 * b['fp_largest_share']:.1f}%)")


if __name__ == "__main__":
    main()
