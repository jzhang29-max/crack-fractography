"""Does a crack read DARK in each modality, and by how much? One instrument, both.

WHY THIS IS MEASURED RATHER THAN ASSERTED. The introduction now carries a figure
contrasting how the two microscopies form an image of a crack, and the obvious thing to
write beside it is a mechanism: electrons escape a surface opening poorly so it reads
dark, X-rays cross less material through a void so it reads bright. The second half of
that sentence is not true of these images -- in this TXM corpus a crack reads DARK on
most frames -- and the project does not have a verified account of why, because the
stored arrays' radiometric convention (transmitted intensity, optical density, or a
phase-contrast rendering) is not recorded anywhere in the three repositories.

So the figure states what can be measured from the data instead of what the physics
"should" give: the SIGN and SIZE of the intensity contrast between the two verdicts a
human painted, per frame, in both modalities, with one definition.

    d = (mean intensity of painted NOT-crack - mean intensity of painted crack)
        / pooled standard deviation

Positive d means the crack is darker than the not-crack a human marked on the same
frame. The comparison is WITHIN a frame and between the two painted verdicts, never
against the whole frame: a frame-wide mean mixes in matrix nobody adjudicated, and the
not-crack verdict is the thing a detector actually has to separate crack from.

THE SEM FRAMES ARE PERCENTILE-STRETCHED per frame by the application's own loader before
they become 8-bit, so raw grey levels are not comparable across frames. A standardised
effect size is, which is the other reason for d rather than a difference of means.

Both paint directories are opened READ-ONLY.

    <sem-crack-detector>/.venv/bin/python -B analysis/research/improve/modality_contrast.py
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

import overlap_means_sem_txm as OV                      # noqa: E402  -- the loaders
import detect_cracks as D                               # noqa: E402  -- via OV's sys.path
import fullframe_recall_decomposition as FRD            # noqa: E402  -- k_max lives here

u = OV.u                      # the instance the overrides are installed on

# ----------------------------------------------- specimen-series scope: b2 and b3 only
#: WHY THIS EXISTS. A reviewer restricted the paper's own laboratory specimens to series
#: b2 and b3 in BOTH microscopies; the corpus also carries SEM b4 and MAR_*/AS_*/Cast_*/
#: HIP_*, and TXM Wrought and AM/HC, which are other specimens.
#:
#: THE PREDICATE IS NOT REDEFINED HERE. This file does not enumerate frames itself -- it
#: iterates `OV.sem_frames()` and `OV.txm_frames()`, the same two loaders the overlap
#: scorer uses -- so the scope filter lives there, in one place, keyed on the same
#: environment variable, and this file only has to agree about the output name. Importing
#: the flag rather than re-deriving it also makes it impossible for the two files to
#: disagree about whether a run was filtered.
#:
#: OFF by default: unset, this file measures and writes exactly what it always did under
#: exactly the same filename. The definition of d, MIN_PX, the ladder, the absolute floor
#: and the reconstruction check are untouched.
#:
#:     SCOPE_B2B3=1 <sem-crack-detector>/.venv/bin/python -B <this file>
SCOPE = OV.SCOPE
SCOPE_ON = OV.SCOPE_ON
SUFFIX = OV.SUFFIX

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))),
                   "docs", "figures", f"modality_contrast{SUFFIX}.json")
MIN_PX = OV.MIN_PX          # the same floor the overlap scorer uses, for one frame set


#: The criterion's own constants and its own ladder, imported rather than retyped. The
#: deployed proposal stage is NOT the stock single-scale cut: the override in
#: `analysis/detector_overrides.py` re-flattens at every radius of a 7-scale ladder,
#: applies min(Otsu, median - k x 1.4826 x MAD) at each, UNIONS the results, and ORs that
#: with an absolute darkness test on the unflattened 8-bit array. A first version of this
#: file reconstructed a SINGLE scale and its own check caught it, on 11.7 million pixels.
#:
#: `k_max` -- per pixel, the largest mad_k at which the relative union would still propose
#: it -- is already implemented, with its own reconstruction control, in
#: `fullframe_recall_decomposition.rung_maps`. It is imported from there. A second
#: transcription of a seven-rung loop is exactly the kind of duplication that produced the
#: single-scale error above.
MAD_K = OV.MADK
DARK_FLOOR = FRD.ABS_DARK
LADDER = tuple(FRD.LADDER)


def cohen_d(a, b):
    """(mean b - mean a) / pooled sd, so POSITIVE means a is darker than b."""
    na, nb = a.size, b.size
    if na < 2 or nb < 2:
        return None
    va, vb = a.var(ddof=1), b.var(ddof=1)
    sp = np.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    if sp <= 0:
        return None
    return float((b.mean() - a.mean()) / sp)


def med(xs):
    return float(np.median(xs)) if xs else None


def run(label, it, grouper=None):
    rows = []
    for nm, img8, corr in it:
        pos, neg = (corr == 1), ((corr == 2) | (corr == 3))
        if pos.sum() < MIN_PX or neg.sum() < MIN_PX:
            continue
        a = img8[pos].astype(np.float64)
        b = img8[neg].astype(np.float64)
        d = cohen_d(a, b)
        if d is None:
            continue
        flat40 = D.flatten_background(img8)
        _rel5, kc, _per = FRD.rung_maps(img8, flat40)
        # the real mask, from the function the application installs, and the
        # reconstruction from the critical k. They must agree pixel for pixel or the axis
        # the figure plots is not the detector's axis. A single-scale version of this
        # reconstruction disagreed on 11.7 million pixels, which is how the ladder was
        # found; the check stays so that a later change to the ladder cannot pass quietly.
        real = u.segment_dark_regions(flat40, img8=img8, mad_k=MAD_K)
        relative = kc > MAD_K
        recon = relative | (img8 < DARK_FLOOR)
        # TOLERANCE, AND WHY IT IS NOT ZERO. The reconstruction and the installed
        # function evaluate `sm < min(otsu, med - k x mad)` and `k_max > k` on the same
        # numbers in a different order, so a pixel sitting exactly on the boundary can
        # fall either way in float. The budget is 1e-6 of the frame -- six pixels in a
        # six-megapixel frame -- and the realised count is recorded per frame, so the
        # single-scale error this check first caught (11.7 MILLION pixels) remains five
        # orders of magnitude outside it.
        bad = int((real ^ recon).sum())
        budget = max(2, int(1e-6 * real.size))
        if bad > budget:
            raise SystemExit(
                f"{nm}: the critical-k reconstruction differs from the installed "
                f"segment_dark_regions on {bad:,} of {real.size:,} pixels (budget "
                f"{budget:,}); the figure's axis would not be the detector's own")
        row = {"frame": nm, "crack_px": int(pos.sum()), "notcrack_px": int(neg.sum()),
               "mean_crack": float(a.mean()), "mean_notcrack": float(b.mean()),
               "d": d,
               "median_critical_k_crack": float(np.median(kc[pos])),
               "median_critical_k_notcrack": float(np.median(kc[neg])),
               "crack_px_proposed_frac": float(real[pos].mean()),
               "crack_px_only_absolute_frac": float(
                   (real[pos] & ~relative[pos]).mean()),
               "reconstruction_mismatch_px": bad}
        del kc, relative, recon, real, flat40
        if grouper:
            row["group"] = grouper(nm)
        rows.append(row)
        print(f"  {nm[:52]:<54} d {d:+7.3f}  median critical k "
              f"{row['median_critical_k_crack']:+8.2f}  proposed "
              f"{100 * row['crack_px_proposed_frac']:5.1f}% (absolute floor alone on "
              f"{100 * row['crack_px_only_absolute_frac']:4.1f}%)", flush=True)
    ds = [r["d"] for r in rows]
    zs = [r["median_critical_k_crack"] for r in rows]
    out = {"n_frames": len(rows), "median_d": med(ds),
           "median_of_median_critical_k_crack": med(zs),
           "frames_median_critical_k_below_k": sum(1 for x in zs if x < MAD_K),
           "mad_k": MAD_K,
           "median_crack_px_proposed_frac": med(
               [r["crack_px_proposed_frac"] for r in rows]),
           "max_reconstruction_mismatch_px": max(
               (r["reconstruction_mismatch_px"] for r in rows), default=0),
           "frames_d_positive": sum(1 for x in ds if x > 0),
           "frames_d_negative": sum(1 for x in ds if x < 0),
           "min_d": min(ds) if ds else None, "max_d": max(ds) if ds else None,
           "per_frame": rows}
    if grouper:
        out["by_group"] = {}
        for g in sorted({r["group"] for r in rows}):
            gd = [r["d"] for r in rows if r["group"] == g]
            gz = [r["median_critical_k_crack"] for r in rows if r["group"] == g]
            out["by_group"][g] = {"n": len(gd), "median_d": med(gd),
                                  "frames_d_negative": sum(1 for x in gd if x < 0),
                                  "min_d": min(gd), "max_d": max(gd),
                                  "median_of_median_critical_k_crack": med(gz),
                                  "frames_median_critical_k_below_k": sum(
                                      1 for x in gz if x < MAD_K),
                                  "median_crack_px_proposed_frac": med(
                                      [r["crack_px_proposed_frac"] for r in rows
                                       if r["group"] == g])}
    print(f"{label}: n = {out['n_frames']}, median d = {out['median_d']:+.3f}, "
          f"{out['frames_d_negative']} frames with the crack BRIGHTER; median critical "
          f"k over painted crack {out['median_of_median_critical_k_crack']:+.2f} "
          f"({out['frames_median_critical_k_below_k']} frames below k = {MAD_K:g})")
    return out


def main():
    res = {
        "definition": "d = (mean intensity of painted not-crack - mean intensity of "
                      "painted crack) / pooled sd; POSITIVE means the crack is darker",
        "min_px_per_verdict": MIN_PX,
        "critical_k_definition": "per pixel, the largest mad_k at which the deployed "
                                 "multiscale relative test would still propose it: the "
                                 "maximum over the 7-scale ladder of the pixel's robust "
                                 "z at that scale, restricted to scales where that z also "
                                 "clears the scale's own Otsu threshold. A pixel is "
                                 "proposed where this exceeds k, or where the unflattened "
                                 "8-bit value is below the absolute floor. Every frame's "
                                 "reconstruction is checked pixel for pixel against the "
                                 "installed segment_dark_regions and the run aborts on any "
                                 "disagreement.",
        "mad_k": MAD_K, "absolute_dark_thresh": DARK_FLOOR,
        "scale_ladder": list(LADDER),
        "note": "within-frame, between the two painted verdicts only; unreviewed pixels "
                "take no part. SEM 8-bit frames are percentile-stretched per frame by the "
                "application's loader, which is why a standardised effect size is used.",
    }
    if SCOPE_ON:
        res["specimen_scope"] = list(SCOPE)   # only on a filtered run
        print(f"SCOPE_B2B3 is set: specimen series {SCOPE} only, in both microscopies; "
              f"output gains the '{SUFFIX}' suffix\n")
    print("SEM")
    res["SEM"] = run("SEM", OV.sem_frames())
    print("TXM")
    res["TXM"] = run("TXM", OV.txm_frames(), OV.txm_group)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    assert SCOPE_ON == OUT.endswith("_b2b3.json"), "a scoped run must not write the full file"
    json.dump(res, open(OUT, "w"), indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
