"""Is a painted crack a TRACE or a REGION? One statistic, computed on the paint alone.

A reference that follows a crack is a stroke: of any width, almost none of it is far from
its own edge. A reference that fills the open mouth of a crack, or blocks out an area the
annotator judged to be crack without tracing it, has a large deep interior. The statistic
is the share of painted-crack pixels lying more than DEEP_PX from the edge of the paint.

WHY IT IS NEEDED. The cross-modality plate used to choose the frame it showed by
`max(crack pixels)` per specimen group, which selects the largest painted object. On TXM
that picked a B3 frame in which three-quarters of the annotation is deep interior, and the
panel came out as solid paint with no micrograph visible in it. The same frame carries
most of its group's pooled score, so the statistic is not only a figure-selection rule --
it says which numbers in Section 4.3 are statements about a traced crack and which are
statements about a blocked-out area.

No image is read and no detector is run: only the correction masks, so this is cheap and
depends on nothing that can drift. Both collections are measured with the same convention.
Opens all paint READ-ONLY.
"""
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

Image.MAX_IMAGE_PIXELS = None
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
TXM = "/Users/jiamingzhang/Desktop/APP/TXM_Crack_Detection_Pipeline"
REPO = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
SEM_PAINT = os.path.join(SEM, "interior_active_learning", "paint")
TXM_CORR = os.path.join(TXM, "paint", "corrections")

DEEP_PX = 50        #: the distance at which "inside the paint" starts
#: A frame needs this much of each verdict to be scorable at all. 200, the same floor
#: `overlap_means_sem_txm.py` uses, so the two files describe the SAME frames and a count
#: quoted from one can be read beside a score quoted from the other. On TXM the set is
#: identical at 200 and at 5000; on SEM it is 18 frames at 200 and 10 at 5000.
MIN_PX = 200

# ----------------------------------------------- specimen-series scope: b2 and b3 only
#: WHY THIS EXISTS. A reviewer restricted the paper's own laboratory specimens to series
#: b2 and b3 in BOTH microscopies. The SEM paint also carries series b4 and the MAR_* /
#: AS_* / Cast_* / HIP_* fields; the TXM corrections also carry Wrought and AM/HC. Those
#: are other specimens, so the restriction changes the frame SET and nothing else.
#:
#: OFF by default: unset, this file measures and writes exactly what it always did under
#: exactly the same filename. Set, the enumeration skips out-of-scope frames and the
#: output gains a `_b2b3` suffix, so a filtered run can never overwrite the full-corpus
#: record. DEEP_PX, MIN_PX and the statistic itself are untouched: every per-frame row
#: must be bit-identical with the switch on and off.
#:
#:     SCOPE_B2B3=1 <sem-crack-detector>/.venv/bin/python -B <this file>
SCOPE = ("b2", "b3")
SCOPE_ON = os.environ.get("SCOPE_B2B3", "") not in ("", "0")
SUFFIX = "_b2b3" if SCOPE_ON else ""


def group_of(n):
    n = n.lower()
    if "_b3_" in n:
        return "B3"
    if "wrought" in n:
        return "Wrought"
    if "hc_316l" in n:
        return "AM/HC"
    return "B2"


def in_scope_sem(stem):
    """SEM carries the series in the frame stem: `..._b2_...`, `..._b3_...`, `..._b4_...`.

    Checked against the 48 correction masks on disk: 20 admitted (all b2), 28 rejected,
    `260622_316_H_b4_CBS_02` among them. The underscores are load-bearing.
    """
    return not SCOPE_ON or any(f"_{s}_" in stem.lower() for s in SCOPE)


def in_scope_txm(stem):
    """TXM is scoped through `group_of()` above -- this file's existing classifier, so the
    scope cannot disagree with the by-group table it writes beside it."""
    return not SCOPE_ON or group_of(stem).lower() in SCOPE


def measure(crack):
    dt = ndi.distance_transform_edt(crack)
    v = dt[crack]
    return {"crack_px": int(crack.sum()),
            "deep_share": float((v > DEEP_PX).mean()),
            "width_p90_px": float(2 * np.percentile(v, 90)),
            "width_median_px": float(2 * np.median(v))}


def report(label, rows):
    rows = sorted(rows, key=lambda r: -r["deep_share"])
    print(f"\n{'=' * 96}\n{label}: {len(rows)} frames, share of painted crack more than "
          f"{DEEP_PX} px inside the paint\n{'=' * 96}")
    print(f"  {'deep%':>7} {'crack px':>10} {'p90 w':>8} {'med w':>8}  frame")
    for r in rows:
        print(f"  {100 * r['deep_share']:7.1f} {r['crack_px']:10,d} "
              f"{r['width_p90_px']:8.1f} {r['width_median_px']:8.1f}  {r['frame'][:56]}")
    v = np.array([r["deep_share"] for r in rows])
    out = {"n_frames": len(rows), "median_deep_share": float(np.median(v)),
           "max_deep_share": float(v.max()), "min_deep_share": float(v.min()),
           "frames_at_zero": int((v == 0).sum()),
           "frames_above_25pct": int((v > 0.25).sum()),
           "frames": rows}
    print(f"  median {100 * out['median_deep_share']:.1f}%, range "
          f"{100 * out['min_deep_share']:.1f}-{100 * out['max_deep_share']:.1f}%, "
          f"{out['frames_at_zero']} frames at exactly 0.0%, "
          f"{out['frames_above_25pct']} above 25%")
    return out


txm = []
for f in sorted(os.listdir(TXM_CORR)):
    if not f.endswith("_correction.npy"):
        continue
    stem = f[: -len("_correction.npy")]
    if not in_scope_txm(stem):
        print(f"  out of scope {SCOPE}: {group_of(stem):<8} {stem[:62]}")
        continue
    if not os.path.exists(os.path.join(TXM, "images", stem + ".tif")):
        continue
    corr = np.load(os.path.join(TXM_CORR, f))
    crack, notc = corr == 1, ((corr == 2) | (corr == 3))
    if crack.sum() < MIN_PX or notc.sum() < MIN_PX:
        continue
    r = measure(crack)
    r.update(frame=stem, group=group_of(stem))
    txm.append(r)

sem = []
for f in sorted(os.listdir(SEM_PAINT)):
    if not f.endswith("_correction_mask.png"):
        continue
    stem = f[: -len("_correction_mask.png")]
    if not in_scope_sem(stem):
        print(f"  out of scope {SCOPE}: {stem}")
        continue
    corr = np.array(Image.open(os.path.join(SEM_PAINT, f)))
    while corr.ndim > 2:
        corr = corr[..., 0]
    crack, notc = corr == 1, ((corr == 2) | (corr == 3))
    if crack.sum() < MIN_PX or notc.sum() < MIN_PX:
        continue
    r = measure(crack)
    r.update(frame=stem)
    sem.append(r)

TX = report("TXM", txm)
SE = report("SEM", sem)

print("\nTXM by specimen group:")
GRP = {}
for g in ("B3", "B2", "Wrought", "AM/HC"):
    sub = [r for r in txm if r["group"] == g]
    if not sub:
        continue
    v = np.array([r["deep_share"] for r in sub])
    GRP[g] = {"n": len(sub), "median_deep_share": float(np.median(v)),
              "max_deep_share": float(v.max()), "min_deep_share": float(v.min()),
              "frames_at_zero": int((v == 0).sum()),
              "frames_above_25pct": int((v > 0.25).sum()),
              "worst_frame": max(sub, key=lambda r: r["deep_share"])["frame"]}
    print(f"  {g:<8} n={len(sub):<3} median {100 * np.median(v):5.1f}%  range "
          f"{100 * v.min():5.1f}-{100 * v.max():5.1f}%  "
          f"{GRP[g]['frames_above_25pct']} above 25%")

p = os.path.join(REPO, f"docs/figures/paint_region_vs_trace{SUFFIX}.json")
assert SCOPE_ON == p.endswith("_b2b3.json"), "a scoped run must not write the full file"
_payload = {"deep_px": DEEP_PX, "min_px_each_verdict": MIN_PX,
            "statistic": "share of painted-crack pixels further than deep_px from the "
                         "edge of the painted crack; a stroke of any width has almost "
                         "none, a filled region has a lot",
            "TXM": TX, "SEM": SE, "TXM_by_group": GRP}
if SCOPE_ON:          # recorded only on a filtered run, so the unfiltered file is unchanged
    _payload["specimen_scope"] = list(SCOPE)
json.dump(_payload, open(p, "w"), indent=1)
print("\nwrote", p)
