"""F7 - model selection: which detector to carry, once the parameter is fixed.

WHAT THE PREVIOUS FIGURE LEFT OPEN. F6 settles the constants of one detector -- the MAD
multiplier at k = 6, the absolute gate, the scale ladder, the disabled region classifier.
It does not ask whether that detector is the right one. This plate asks that, and it asks
it the same way in both microscopies.

THE ONE THING THIS PLATE HAS TO DO THAT ITS PREDECESSOR DID NOT. P4 put seven classical
arms on the SEM axis and, on the TXM axis, three learned transmission models over two
controls and one carried-over arm. Two disjoint candidate lists cannot be read as one
comparison: a reader cannot tell whether the TXM answer differs because the data differ
or because the shortlist differs. So the candidate list here is IDENTICAL in both arms,
and it is the list that could honestly be scored in both -- every arm below was already
run on the SEM collection, and has now been run on the transmission frames by a copy of
that same recipe, checked against the archived transmission record.

WHAT COULD NOT BE PUT ON THESE AXES, AND WHY NOT.

  The three learned transmission models (17 hand-built channels, those channels plus a
  frozen SAM ViT-H encoder, and the mean of the two). They have no SEM counterpart: no
  learned model of this project was ever trained or scored on the SEM collection used
  here. Their only artefact is a 5-fold cross-validation GROUPED BY IMAGE over all 71
  labelled frames, reported as IoU -- a different corpus, a different unit, and an
  overlap score, which this project has measured to be unusable on TXM paint (a correct
  3 px crack scores 0.0498 there, so IoU ranks brush imitation). Putting them beside
  these arms would be the same fault P4 has. They are named in the sidecar instead, in
  BOTH the versions that exist: the v4 triple the paper's own docs/figures record keeps,
  and the v5 pair the application actually loads, whose grouped-CV the paper's record
  wrongly says does not exist. Neither is on an axis here, so nothing is swapped; the
  clash is written down. The sidecar also records that the deployed weights were
  retrained on all 71 frames with nothing held back, so the cross-validated number is an
  estimate of the recipe and not a score of the shipped pair.

  The published learned baselines that WERE scored on SEM (OmniCrack30k nnU-Net, zero-shot
  SAM 3). Those live on a 15-tile benchmark of this laboratory's own SEM frames; nothing
  equivalent has ever been run on TXM, and at n = 15 nothing on that benchmark separates.

THE MEASURES, AND WHICH OF THEM MAY SHARE AN AXIS.

  (a) area agreement -- the crack area fraction the tool reports divided by the one the
      annotator marked. It is DIMENSIONLESS and its reference is 1 in both arms, so both
      arms are drawn on one axis. This is the only panel where they meet. The axis is
      logarithmic because the worst arm overshoots by 55x and a linear axis would be one
      arm and seven dots at the origin.

  (b, c) ONE measurement, run once per arm: how far an arm's pixel accuracy falls
      BELOW the accuracy an all-background mask already earns, in points, over the area
      that collection's own annotator adjudicated. Both panels are drawn on ONE shared
      scale -- the same linear threshold, the same limits, the same ticks -- because
      they are the same quantity and a reader comparing a stem in (b) with a stem in (c)
      must be comparing one mapping. Earlier editions fitted each panel's axis to its own
      arm, which made two runs of one measurement look like two different measures.
      What still differs is the DATA, and each title says so: the SEM collection
      adjudicates every pixel of the frame and is 1.80% crack, the transmission frames
      only the 38% a human refereed, which is 14.62% crack. That sets each arm's floor
      rather than its scale -- an arm that marks everything loses 98.2 points on SEM and
      85.4 on TXM -- and the floor is in the sidecar. Nothing in either collection
      clears the line, which is the point of drawing them. The shortfall is close to a
      restatement of how much area an arm marks -- a false positive costs a point of
      accuracy and there are only so many crack pixels to miss -- so (a) and not (b, c)
      is where the arms separate; (b, c) price the marking.

HOW EACH ARM'S PARAMETER WAS CHOSEN -- the same rule in both arms, which is the point.
Every arm gets its own single parameter chosen LEAVE-ONE-IMAGE-OUT on the collection it
is scored on, once by F1 and once by area-fraction error, and is then shown at whichever
of those two tunings gives IT the higher accuracy. No arm is handicapped. On the SEM
collection that rule lands this detector on k = 6, which is the value F6 selects, so the
detector row here IS the previous figure's parameter rather than a refitted one.

SOURCES. SEM: docs/figures/arms_background_units.json (written by
analysis/research/improve/arms_background_units.py from arms_pixel_budget.json). TXM:
docs/figures/txm_classical_arms.json, which THIS FILE writes the first time it is run and
reads thereafter. That measurement reproduces the pooled true- and false-positive shares
of the archived transmission record (docs/figures/txm_background_units.json) on the nine
arms the two have in common, to within 1e-9 of a point, and aborts if it does not -- see
`measure()`.

    <sem-crack-detector>/.venv/bin/python -B mk_model_selection.py            # draw
    <sem-crack-detector>/.venv/bin/python -B mk_model_selection.py --measure  # re-measure
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.lines import Line2D                                  # noqa: E402

import _paths                                                        # noqa: E402
import journal_style as J                                            # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "out")
DOCFIG = os.path.join(REPO, "docs", "figures")
TXM_ARMS = os.path.join(DOCFIG, "txm_classical_arms.json")
FIGNAME = "F7 - model selection"

#: The parameter the previous figure selects. Not retyped from the manuscript: it is
#: asserted against the SEM record below, which stores the leave-one-out choice itself.
PARAM_K = 6.0

#: The arms, in the order they are defined for the measurement, with the words a reader
#: of the figure gets. The key is the name the SEM record uses.
ARM_LABEL = {
    "DETECTOR (shipped)": "this detector\n(darkness, k = 6 fixed)",
    "UNION darkness OR Sato": "darkness OR Sato ridge",
    "Sato ridge": "Sato ridge filter",
    "Meijering ridge": "Meijering ridge filter",
    "Frangi ridge": "Frangi ridge filter",
    "Sauvola local": "Sauvola local threshold",
    "percentile threshold": "fixed-percentile threshold",
    "global threshold (Otsu on flat)": "global Otsu threshold",
}
HERO_KEY = "DETECTOR (shipped)"

#: THE WINNER'S ROW LABEL, WHICH CARRIES THE VERDICT. It used to be a tag set inside
#: panel (a). That panel is 1.7 in wide once eight arm names have taken their column,
#: and a 21-character string at 8 pt bold is 0.68 of it: wherever the tag was anchored
#: it printed across the hero row's own two markers, and widening the axis to open a gap
#: only squeezed the data -- the gap grows by a third of what the axis does. A row label
#: cannot collide with a marker, so the verdict is a row label. The parameter in it is
#: PARAM_K itself, asserted against the record further down, not a retyped number.
HERO_LABEL = "this detector (darkness)\nk = %g fixed, best on both" % PARAM_K


def load(path, what):
    if not os.path.exists(path):
        raise SystemExit(f"{what} not found at {path}")
    with open(path) as fh:
        return json.load(fh)


# ======================================================================================
# THE MEASUREMENT.  The seven classical arms, on the transmission frames, by the code the
# SEM table was written with.
# ======================================================================================
def measure(path=TXM_ARMS):
    """Run every arm of the SEM baseline table on the TXM frames and write the record.

    THE RECIPE IS NOT A NEW ONE. The arm list, the parameter grids, the cleaning chain and
    the leave-one-image-out selection are copied from
    analysis/research/improve/arms_pixel_budget.py, which produced the SEM half of this
    figure; the frame enumeration, the refereed-pixel scoring and the four-way budget are
    copied from analysis/research/improve/txm_background_units.py, which produced the
    archived transmission record. Nothing here is a third convention.

    THE POSITIVE CONTROL. Those two parents overlap on exactly one family of arms -- the
    SEM detector at mad_k 3..10 on the TXM frames -- and the archived record stores its
    pooled pixel counts. This function recomputes them and ABORTS if any of the seven
    disagrees by more than 1e-9 of a percentage point. A reimplementation that reproduces
    the archived arms is measuring the new arms with the archived instrument; one that
    does not is measuring something else, and the difference would be invisible in the
    figure.

    BOTH AGGREGATIONS ARE STORED. The SEM table is a mean over images of per-image
    percentages; the archived TXM record is a pooled sum over pixels. They are different
    weightings of the same frames and they do not have to agree. The figure draws the
    per-image mean, because that is the instrument the SEM half was measured with; the
    pooled block is written beside it so the choice is visible and reversible.
    """
    import time
    import warnings
    warnings.filterwarnings("ignore")
    sys.dont_write_bytecode = True
    for d in (os.path.join(REPO, "analysis"), os.path.join(_paths.SEM_REPO, "code")):
        if d not in sys.path:
            sys.path.insert(0, d)
    import numpy as np
    from skimage import filters, measure as skm
    import detect_cracks as D
    import detector_overrides as DO

    class _U:
        pass

    u = _U()
    DO.install(u)

    K_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0]
    Q_GRID = [0.5, 1, 2, 4, 8]          # ridge percentiles and the percentile threshold
    W_GRID = [15, 25, 51, 101]          # Sauvola windows
    UNION = [(6.0, 0.5), (6.0, 1), (6.0, 2), (6.0, 4),
             (5.0, 0.5), (5.0, 1), (5.0, 2), (5.0, 4), (3.0, 1), (3.0, 2)]
    #: every (arm, parameter) pair, named exactly as the SEM record names the arm
    PARAMS = {"DETECTOR (shipped)": list(K_GRID),
              "global threshold (Otsu on flat)": [0.0],
              "percentile threshold": list(Q_GRID),
              "Sauvola local": list(W_GRID),
              "Frangi ridge": list(Q_GRID),
              "Sato ridge": list(Q_GRID),
              "Meijering ridge": list(Q_GRID),
              "UNION darkness OR Sato": list(UNION)}
    #: arms_pixel_budget.py's own accounting, kept so the two halves of the figure agree:
    #: two for the union, one for everything else including Otsu, whose threshold is
    #: computed rather than searched but is still a threshold.
    FREE = {a: (2 if a == "UNION darkness OR Sato" else 1) for a in PARAMS}

    def clean(m):
        """arms_pixel_budget.clean / txm_background_units.cand -- the same function."""
        lab = skm.label(D.clean_mask(m, min_area_px=13), connectivity=2)
        if not lab.max():
            return np.zeros(lab.shape, bool)
        sz = np.bincount(lab.ravel())
        k = np.where(sz >= 40)[0]
        return np.isin(lab, k[k > 0])

    def group_of(name):
        """txm_background_units.group_of, unchanged."""
        n = name.lower()
        if "_b3_" in n:
            return "B3"
        if "wrought" in n:
            return "Wrought"
        if "hc_316l" in n:
            return "AM/HC"
        if "_b2_" in n or "b2_" in n:
            return "B2"
        return "other"

    txm_repo = _paths.require(_paths.TXM_REPO, "the TXM repository", "TXM_REPO")
    cdir = os.path.join(txm_repo, "paint", "corrections")
    frames = []
    for f in sorted(os.listdir(cdir)):
        if not f.endswith("_correction.npy"):
            continue
        stem = f[: -len("_correction.npy")]
        tif = os.path.join(txm_repo, "images", stem + ".tif")
        if os.path.exists(tif):
            frames.append((stem, tif, os.path.join(cdir, f)))
    print(f"{len(frames)} transmission frames carry both an image and a correction mask")

    rows = []          # one dict per used frame: {"stem", "group", arm -> {param -> budget}}
    pooled = {}        # (arm, param) -> {"tp": int, "fp": int}; plus the archived controls
    tot_c = tot_n = 0
    t0 = time.time()
    for i, (stem, tif, cpath) in enumerate(frames, 1):
        corr = np.load(cpath)
        crack = corr == 1
        notc = (corr == 2) | (corr == 3)
        c, n = int(crack.sum()), int(notc.sum())
        if c < 5000 or n < 5000:
            continue
        img8 = D.load_as_uint8(tif)
        if img8.shape != corr.shape:
            print(f"  [{i}] shape mismatch {img8.shape} vs {corr.shape} -- skipped")
            continue
        flat = D.flatten_background(img8)
        ref = c + n

        def budget(m):
            tp = int((m & crack).sum())
            fp = int((m & notc).sum())
            fn, tn = c - tp, n - fp
            pr = tp / max(tp + fp, 1)
            rc = tp / max(tp + fn, 1)
            lab_pct, mark_pct = 100.0 * c / ref, 100.0 * (tp + fp) / ref
            return {"labelled_pct": lab_pct, "marked_pct": mark_pct,
                    "tp_pct": 100.0 * tp / ref, "fp_pct": 100.0 * fp / ref,
                    "fn_pct": 100.0 * fn / ref, "tn_pct": 100.0 * tn / ref,
                    "accuracy_pct": 100.0 * (tp + tn) / ref,
                    "specificity_pct": 100.0 * tn / max(n, 1),
                    "area_ratio": mark_pct / lab_pct, "area_err_pp": abs(mark_pct - lab_pct),
                    "precision": pr, "recall": rc,
                    "f1": 2 * pr * rc / max(pr + rc, 1e-12),
                    "iou": tp / max(tp + fp + fn, 1),
                    "_tp": tp, "_fp": fp}

        row = {"stem": stem, "group": group_of(stem), "refereed_px": ref,
               "crack_px": c, "notcrack_px": n, "arms": {a: {} for a in PARAMS}}

        dark = {}
        for k in K_GRID:
            dark[k] = clean(u.segment_dark_regions(flat, img8=img8, mad_k=k))
            row["arms"]["DETECTOR (shipped)"][repr(k)] = budget(dark[k])
        sato = {}
        for kind, arm in (("sato", "Sato ridge"), ("frangi", "Frangi ridge"),
                          ("meijering", "Meijering ridge")):
            fn_ = {"sato": filters.sato, "frangi": filters.frangi,
                   "meijering": filters.meijering}[kind]
            r = fn_(img8.astype(float), sigmas=range(1, 5), black_ridges=True)
            for q in Q_GRID:
                m = clean(r >= np.percentile(r, 100 - q))
                row["arms"][arm][repr(q)] = budget(m)
                if kind == "sato":
                    sato[q] = m
            del r
        for q in Q_GRID:
            row["arms"]["percentile threshold"][repr(q)] = budget(
                clean(img8 <= np.percentile(img8, q)))
        for w in W_GRID:
            row["arms"]["Sauvola local"][repr(w)] = budget(
                clean(img8 < filters.threshold_sauvola(img8, window_size=w)))
        sm = filters.gaussian(flat, sigma=1.0, preserve_range=True)
        otsu_raw = sm < filters.threshold_otsu(sm)
        row["arms"]["global threshold (Otsu on flat)"][repr(0.0)] = budget(clean(otsu_raw))
        for p in UNION:
            row["arms"]["UNION darkness OR Sato"][repr(p)] = budget(dark[p[0]] | sato[p[1]])

        # --- the two archived controls, scored exactly as the archived file scores them:
        # NO cleaning on the Otsu control, and a mask of ones. They are the positive
        # control for this reimplementation, not arms of the comparison.
        for nm, m in (("control: Otsu, no model", otsu_raw),
                      ("control: mark everything", np.ones(img8.shape, bool))):
            tp, fp = int((m & crack).sum()), int((m & notc).sum())
            d = pooled.setdefault((nm, None), {"tp": 0, "fp": 0})
            d["tp"] += tp
            d["fp"] += fp
        for arm, ps in PARAMS.items():
            for p in ps:
                b = row["arms"][arm][repr(p)]
                d = pooled.setdefault((arm, repr(p)), {"tp": 0, "fp": 0})
                d["tp"] += b.pop("_tp")
                d["fp"] += b.pop("_fp")
        tot_c += c
        tot_n += n
        rows.append(row)
        print(f"  [{i:>2}/{len(frames)}] {row['group']:<8} {stem[:38]:<40} "
              f"{ref / 1e6:6.2f} Mpx refereed   crack {100.0 * c / ref:5.2f}%   "
              f"{time.time() - t0:6.0f}s", flush=True)
        del dark, sato, flat, img8, corr, crack, notc, otsu_raw, sm

    N = len(rows)
    if N == 0:
        raise SystemExit("no transmission frame passed the 5000-pixel floor")
    print(f"\n{N} frames scored, {tot_c:,} crack and {tot_n:,} not-crack refereed px")

    # ---- the positive control -------------------------------------------------------
    arch = load(_paths.scoped("txm_background_units.json", scope=False),
                "the archived transmission record")
    ref_px = tot_c + tot_n
    checks = []
    if arch["n_frames"] != N:
        raise SystemExit(f"frame count {N} != archived {arch['n_frames']}")
    for nm, key in ([(f"SEM detector, mad_k={k:g}", ("DETECTOR (shipped)", repr(k)))
                     for k in (3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0)] +
                    [("control: Otsu, no model", ("control: Otsu, no model", None)),
                     ("control: mark everything", ("control: mark everything", None))]):
        got = pooled[key]
        want = arch["pooled"][nm]
        dtp = 100.0 * got["tp"] / ref_px - want["tp_pct"]
        dfp = 100.0 * got["fp"] / ref_px - want["fp_pct"]
        checks.append({"arm": nm, "d_tp_pp": dtp, "d_fp_pp": dfp})
        if abs(dtp) > 1e-9 or abs(dfp) > 1e-9:
            raise SystemExit(
                f"POSITIVE CONTROL FAILED on {nm}: tp% off by {dtp:.3e}, fp% off by "
                f"{dfp:.3e}. This reimplementation is not the archived instrument; the "
                f"new arms it would write cannot be compared with the archived ones.")
    print(f"positive control PASSED: {len(checks)} archived arms reproduced to < 1e-9 pp")

    # ---- leave-one-image-out selection, the SEM table's own rule --------------------
    def loo(arm, key, lower_is_better):
        sign = 1.0 if lower_is_better else -1.0
        ps = PARAMS[arm]
        picks = []
        for i in range(N):
            best = min(ps, key=lambda p: sign * sum(
                rows[j]["arms"][arm][repr(p)][key] for j in range(N) if j != i) / (N - 1))
            picks.append((repr(best), i))
        return picks

    KEYS = ("labelled_pct", "marked_pct", "tp_pct", "fp_pct", "fn_pct", "tn_pct",
            "accuracy_pct", "specificity_pct", "area_ratio", "area_err_pp",
            "precision", "recall", "f1", "iou")
    #: EVERY cell of the grid at the figure's own aggregation, not just the cells the
    #: selection rule landed on. A record that keeps only the winners cannot be used to
    #: ask a different question of the same run -- what the detector does at the k the
    #: previous figure fixed, for instance, if the leave-one-out rule picks another one.
    by_param = {a: {repr(p): {k: sum(r["arms"][a][repr(p)][k] for r in rows) / N
                              for k in KEYS}
                    for p in PARAMS[a]} for a in PARAMS}
    lab_mean = sum(r["arms"][HERO_KEY][repr(K_GRID[0])]["labelled_pct"] for r in rows) / N
    empty = 100.0 - lab_mean
    sel = {}
    for arm in PARAMS:
        res = {"free_params": FREE[arm], "grid": [repr(p) for p in PARAMS[arm]]}
        for key, name, lower in (("f1", "sel_by_f1", False),
                                 ("area_err_pp", "sel_by_area", True)):
            picks = loo(arm, key, lower)
            agg = {k: sum(rows[i]["arms"][arm][p][k] for p, i in picks) / N for k in KEYS}
            agg["picks"] = sorted({p for p, _ in picks})
            res[name] = agg
        best = max(("sel_by_f1", "sel_by_area"), key=lambda s: res[s]["accuracy_pct"])
        res["shown"] = best
        res["area_agreement"] = res[best]["marked_pct"] / lab_mean
        res["accuracy_margin_pp"] = res[best]["accuracy_pct"] - empty
        sel[arm] = res

    payload = {
        "what": "the SEM baseline table's own arms, run on the transmission frames by the "
                "same code, so the two microscopies can be compared across one candidate "
                "list instead of two",
        "generator": "paper/figures/mk_model_selection.py --measure",
        "recipe_from": ["analysis/research/improve/arms_pixel_budget.py (arms, grids, "
                        "cleaning, leave-one-image-out selection)",
                        "analysis/research/improve/txm_background_units.py (frame "
                        "enumeration, refereed-pixel scoring, four-way budget)"],
        "n_frames": N,
        "specimen_scope": "ALL four specimen groups of the transmission corpus, not the "
                          "b2/b3 subset the manuscript's laboratory sections report",
        "groups": {g: sum(1 for r in rows if r["group"] == g)
                   for g in sorted({r["group"] for r in rows})},
        "refereed_crack_px": tot_c, "refereed_notcrack_px": tot_n,
        "scoring": "refereed pixels only: 1 = crack, 2 or 3 = not-crack, 0 excluded. "
                   "Every percentage is of the refereed area, not of the frame.",
        "aggregation": "mean over frames of the per-frame percentages, which is the "
                       "aggregation the SEM table uses; the pooled-pixel aggregation the "
                       "archived transmission record uses is in `pooled_by_param`",
        "selection": "each arm's one parameter chosen leave-one-image-out, once by F1 and "
                     "once by area-fraction error; the arm is SHOWN at whichever of the "
                     "two gives it the higher accuracy, which is the rule "
                     "arms_background_units.py applies to the SEM table",
        "f1_is_a_selection_key_only": "F1 and IoU are recorded because the selection needs "
                                      "them and because hiding them would hide the choice. "
                                      "They are NOT reported in the figure: the TXM paint "
                                      "is far wider than the feature and a prior "
                                      "measurement puts the IoU ceiling for a correct 3 px "
                                      "crack at 0.0498, so overlap here ranks brush "
                                      "imitation.",
        "labelled_pct": lab_mean, "empty_mask_accuracy_pct": empty,
        "arms": sel,
        "by_param_frame_mean": by_param,
        "positive_control": {
            "what": "the pooled tp% and fp% of every arm this file and the archived "
                    "transmission record have in common, recomputed here",
            "tolerance_pp": 1e-9, "result": "PASS", "checked": checks,
            "against": os.path.basename(
                _paths.scoped("txm_background_units.json", scope=False))},
        "pooled_by_param": {
            f"{a} @ {p}" if p is not None else a: {
                "tp_pct": 100.0 * v["tp"] / ref_px, "fp_pct": 100.0 * v["fp"] / ref_px}
            for (a, p), v in pooled.items()},
        "per_frame": [{"stem": r["stem"], "group": r["group"],
                       "refereed_px": r["refereed_px"], "crack_px": r["crack_px"],
                       "notcrack_px": r["notcrack_px"]} for r in rows],
    }
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=1)
    print("wrote", path)
    return payload


# ======================================================================================
# THE PLATE
# ======================================================================================
def draw():
    J.use()
    sem_all = load(os.path.join(DOCFIG, "arms_background_units.json"),
                   "the SEM arm table")
    SEM = sem_all["sets"]["whole_fields"]
    TXM = load(TXM_ARMS, "the transmission arm table")
    madk = load(os.path.join(DOCFIG, "madk_above_five.json"), "the mad_k sweep")
    #: the archived transmission record. (c)'s title quotes its refereed coverage, so the
    #: two records have to be describing the same adjudicated area or the panel would be
    #: labelled with a scope it does not draw.
    ARCH = load(_paths.scoped("txm_background_units.json", scope=False),
                "the archived transmission record")
    for _k in ("refereed_crack_px", "refereed_notcrack_px"):
        if ARCH[_k] != TXM[_k]:
            raise SystemExit(f"{_k} is {TXM[_k]} in txm_classical_arms.json and "
                             f"{ARCH[_k]} in the archived record; panel (c) would be "
                             f"labelled with a refereed area it does not draw")
    COVER = 100.0 * ARCH["refereed_coverage_frac"]
    cv = load(os.path.join(DOCFIG, "txm_model_scores.json"),
              "the transmission model scores")["cross_validated"]

    # --- THE LEARNED TRANSMISSION MODELS EXIST IN TWO VERSIONS, AND THE PAPER'S OWN
    # --- RECORD NAMES ONLY THE OLDER ONE.
    # docs/figures/txm_model_scores.json carries the v4 triple and states that "no v5
    # grouped-CV artefact exists in either repository". That statement is false: the
    # deployed joblibs are the v5 pair and their gate record is the transmission
    # project's own retrain_history.json, which carries a 5-fold grouped-by-image
    # cross-validation of all three family members. Neither version is drawn on this
    # plate -- these models have no SEM counterpart, which is the whole reason they are
    # not on an axis here -- so nothing is silently swapped: BOTH are written to the
    # sidecar, each labelled with its version, and the contradiction is recorded with
    # them rather than resolved by picking one.
    RETRAIN = os.path.join(_paths.TXM_REPO, "app_data", "models", "retrain_history.json")
    hist = load(RETRAIN, "the transmission retrain history")
    deployed = [r for r in hist
                if r.get("deployed") and (r.get("heldout") or {}).get("mean_iou")]
    if not deployed:
        raise SystemExit(f"{RETRAIN} records no deployed run with a held-out score")
    v5 = deployed[-1]
    MDIR = os.path.dirname(RETRAIN)
    joblibs = [f"{p}_{v5['stamp']}.joblib" for p in ("f17", "hybrid")]
    absent = [f for f in joblibs if not os.path.exists(os.path.join(MDIR, f))]
    if absent:
        raise SystemExit(
            f"the newest deployed run in {RETRAIN} is {v5['stamp']} but its weights "
            f"{absent} are not in {MDIR}; the sidecar would name a model that is not "
            f"the one on disk")
    h5 = v5["heldout"]

    # --- the detector row must BE the previous figure's parameter, not a refit --------
    # The SEM table does not store which k it selected, so it is identified here by the
    # pixel budget it reports: the sweep stores every k's budget, and exactly one of them
    # can match. If F6's k ever moves, this aborts rather than mislabelling the row.
    per_k = madk["sets"]["whole_fields"]["per_k"]
    #: the SEM collection's size, counted from the sweep's per-image rows rather than
    #: retyped from a caption
    N_SEM = len(madk["sets"]["whole_fields"]["per_image"][f"{PARAM_K:g}.0"]["f1"])
    det = SEM["arms"][HERO_KEY]
    hit = [k for k, v in per_k.items()
           if abs(v["marked_pct"] - det["marked_pct"]) < 1e-9
           and abs(v["tp_pct"] - det["tp_pct"]) < 1e-9]
    if hit != [f"{PARAM_K:g}.0"] and hit != [f"{PARAM_K:g}"]:
        raise SystemExit(
            f"the SEM detector row is the k = {hit} budget, not the k = {PARAM_K:g} that "
            f"F6 selects; the plate would claim a parameter it is not drawing")

    keys = list(ARM_LABEL)
    missing = [k for k in keys if k not in SEM["arms"] or k not in TXM["arms"]]
    if missing:
        raise SystemExit(f"arms absent from one of the two records: {missing}")

    #: the detector on the transmission frames with k PINNED at the previous figure's
    #: value rather than reselected -- not what the plate draws, but the number a reader
    #: who takes "given the parameter of the previous figure" literally will want
    K6_T = TXM["by_param_frame_mean"][HERO_KEY][repr(PARAM_K)]

    A_SEM = {k: SEM["arms"][k]["area_agreement"] for k in keys}
    A_TXM = {k: TXM["arms"][k]["area_agreement"] for k in keys}
    M_SEM = {k: SEM["arms"][k]["accuracy_margin_pp"] for k in keys}
    M_TXM = {k: TXM["arms"][k]["accuracy_margin_pp"] for k in keys}

    # THE DETECTOR ROW IS PINNED AT THE PREVIOUS FIGURE'S k IN BOTH ARMS, AND IT IS THE
    # ONLY ROW THAT IS. That is the premise of the plate -- the parameter is settled, now
    # choose the model -- and it costs the detector something rather than buying it
    # anything: every competitor is handed the best parameter it can get on the very
    # collection it is scored on, while this one is held at a value chosen on different
    # data. On the SEM collection the two coincide (the assertion above is what says so),
    # so only the transmission row moves. Letting the rule refit it there picks k = 12,
    # the TOP OF THE GRID, which is the failure the previous figure's own record warns
    # about -- an optimum at the edge of the search is not an optimum -- and it would have
    # flattered this row: 1.049x and +0.209 points against the 1.151x and -0.587 drawn.
    # Both are in the sidecar; the conservative one is on the plate.
    LOO_TXM = {"area_agreement": A_TXM[HERO_KEY], "accuracy_margin_pp": M_TXM[HERO_KEY],
               "picks": TXM["arms"][HERO_KEY][TXM["arms"][HERO_KEY]["shown"]]["picks"],
               "grid": TXM["arms"][HERO_KEY]["grid"]}
    A_TXM[HERO_KEY] = K6_T["marked_pct"] / TXM["labelled_pct"]
    M_TXM[HERO_KEY] = K6_T["accuracy_pct"] - TXM["empty_mask_accuracy_pct"]

    # RANKED BY THE WORSE OF ITS TWO ARMS. A model that is near parity on one microscopy
    # and 10x out on the other has not been shown to transfer, and the figure's question
    # is which model to carry into both. Ranking on the better arm would answer a
    # question nobody asked.
    def worst(k):
        return max(abs(math.log10(A_SEM[k])), abs(math.log10(A_TXM[k])))

    order = sorted(keys, key=worst)
    winner = order[0]
    sem_best = min(keys, key=lambda k: abs(math.log10(A_SEM[k])))
    txm_best = min(keys, key=lambda k: abs(math.log10(A_TXM[k])))
    y = list(range(len(order)))
    hero = order.index(winner)

    fig, (ax1, ax2, ax3) = plt.subplots(
        1, 3, figsize=(J.PAGEW, 3.40), layout="constrained",
        gridspec_kw={"width_ratios": [1.25, 0.95, 0.95]})

    def frame(ax):
        ax.axhspan(hero - 0.5, hero + 0.5, color="#eef2f8", zorder=0)
        ax.set_ylim(len(order) - 0.5, -0.5)

    # ---- (a) area agreement, BOTH arms on one axis ----------------------------------
    frame(ax1)
    ax1.set_xscale("log")
    ax1.axvline(1.0, color=J.INK, lw=0.9, zorder=3)
    for i, k in enumerate(order):
        lo, hi = sorted((A_SEM[k], A_TXM[k]))
        ax1.plot([lo, hi], [i, i], color=J.G_LIGHT, lw=1.5, solid_capstyle="round",
                 zorder=2)
    ax1.plot([A_SEM[k] for k in order], y, "o", ms=5.0, mfc="white", mec=J.ACCENT,
             mew=1.3, linestyle="none", zorder=4)
    ax1.plot([A_TXM[k] for k in order], y, "s", ms=4.6, mfc=J.ACCENT2, mec="white",
             mew=0.6, linestyle="none", zorder=5)
    ax1.set_yticks(y, [HERO_LABEL if k == winner else ARM_LABEL[k] for k in order])
    for t, k in zip(ax1.get_yticklabels(), order):
        if k == winner:
            t.set_fontweight("bold")
    # LIMITS FROM THE DATA, NOT FROM A GUESS. A hand-set limit silently drops an arm the
    # day one of them moves, and the arm that would move first here is the one that marks
    # most of the frame. Nothing is reserved for a label: the only words in this panel
    # are its row labels, which live outside it.
    allr = list(A_SEM.values()) + list(A_TXM.values())
    XLO, XHI = min(allr) / 2.2, max(allr) * 2.2
    ax1.set_xlim(XLO, XHI)
    decades = [10.0 ** e for e in range(int(math.floor(math.log10(XLO))) + 1,
                                        int(math.ceil(math.log10(XHI))))]
    ax1.set_xticks(decades, [f"{v:g}x" for v in decades])
    ax1.set_xlabel("Crack area reported /\ncrack area annotated")
    la = J.panel_label(ax1, "a")
    ax1.set_title("Both microscopies\n(exact match = 1x)", fontsize=J.TICK, pad=2.0)
    # THE WINNER, NAMED IN THE ARTWORK. The shaded band and the bold row label say which
    # row it is; a reader with no caption still needs the word, and the word is
    # descriptive rather than a verdict -- the row is the one closest to parity in BOTH
    # collections, which is a fact about the two markers beside it and not a claim that
    # the paper endorses it. It is set in the row LABEL, for the reason beside
    # HERO_LABEL, so no string is ever placed over a marker.

    # ---- (b, c) accuracy against an all-background mask, ONE ARM EACH ---------------
    # The marker carries the microscopy, the same way round as in (a): a hollow blue
    # circle is always the SEM collection and a filled orange square is always the
    # transmission collection, so a reader who has read the legend once never has to
    # read a panel title to know which arm is in front of them.
    #
    # WHY THESE TWO AXES ARE SYMMETRICALLY LOGARITHMIC. The margins span three orders of
    # magnitude in both collections -- 0.02 points for the percentile threshold on SEM
    # against 96 points for global Otsu, which marks 99.5% of a frame. On a linear axis
    # Otsu sets the scale and the other seven arms collapse onto the zero line, which is
    # why the plate this replaces dropped Otsu from the comparison altogether. Nothing is
    # dropped here. A symmetric log axis keeps zero -- the all-background mask itself --
    # as a real position, so the reference rule and the stems mean what they mean in (a)
    # and in the plate this replaces, and it does not assume the sign: an arm that beats
    # the all-background mask would be drawn to the right of the rule rather than
    # crashing the plate or being quietly reflected.
    # ONE SCALE FOR BOTH PANELS, FITTED TO BOTH ARMS AT ONCE. (b) and (c) are one
    # measurement run twice, so a reader has to be able to carry a length from one panel
    # to the other. The linear zone is the COARSER of the two arms' own: a zone narrower
    # than an arm's smallest margin is empty in that arm's panel, and two panels with two
    # linear zones are two mappings wearing the same axis label.
    VSEM = [M_SEM[k] for k in order]
    VTXM = [M_TXM[k] for k in order]
    LIN = max(10.0 ** math.floor(math.log10(min(abs(x) for x in v if x) or 1.0))
              for v in (VSEM, VTXM))

    def _side(xs):
        """How far the axis must run to hold these magnitudes, or just past the linear
        zone when there are none. The two SIDES are sized separately -- one arm 96 points
        below the baseline and three a fraction of a point above it would otherwise leave
        the whole right half of both panels empty, and an empty half reads as a range
        nobody occupies -- but each side is sized over BOTH arms, so the two panels come
        out identical."""
        return (10.0 ** math.ceil(math.log10(max(xs)) - 1e-12) * 2.4) if xs \
            else LIN * 2.0

    BOTH = VSEM + VTXM
    LO_S = _side([-x for x in BOTH if x < 0])
    HI_S = _side([x for x in BOTH if x > 0])

    def margins(ax, vals, title, marker, mfc, mec, mew, ms):
        frame(ax)
        v = [vals[k] for k in order]
        lin, lo_s, hi_s = LIN, LO_S, HI_S
        ax.set_xscale("symlog", linthresh=lin, linscale=0.45)
        ax.set_xlim(-lo_s, hi_s)
        ax.axvline(0.0, color=J.INK, lw=0.9, zorder=3)
        for i, k in enumerate(order):
            ax.plot([0.0, vals[k]], [i, i], color=J.G_LIGHT, lw=1.5,
                    solid_capstyle="round", zorder=2)
        ax.plot(v, y, marker, ms=ms, mfc=mfc, mec=mec, mew=mew, linestyle="none",
                zorder=4)

        # DECADES, THINNED TO WHAT A 1.5 in PANEL CAN SET AT 8 pt. Every decade of a
        # three-decade symlog axis is a tick label, and at this width they overprint; the
        # stride keeps the largest and drops alternates, which is a legibility choice and
        # not a change of scale -- the minor ticks still mark every dropped decade. The
        # first decade starts ABOVE the linear threshold: a tick at the edge of the
        # linear zone sits a fraction of a decade from the zero rule and its label
        # overprints the "0".
        def decs(limit, sign):
            e0 = int(round(math.log10(lin))) + 1
            e1 = int(math.ceil(math.log10(limit / 2.4) - 1e-12))
            d = [sign * 10.0 ** e for e in range(e0, e1 + 1) if 10.0 ** e <= limit]
            return d[::-1][::1 + (len(d) > 2) + (len(d) > 5)]

        ticks = sorted(decs(lo_s, -1.0) + [0.0] + decs(hi_s, 1.0))
        ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
        ax.set_yticks(y, ["" for _ in order])
        ax.set_title(title, fontsize=J.TICK, pad=2.0)

    # THE TWO TITLES ARE THE SAME SENTENCE TWICE. What differs between the panels is the
    # area each collection's annotator adjudicated and how much of it is crack, so that
    # is what the titles say, in the same words and the same order. A reader who sees
    # "all pixels" over one panel and "refereed px" over the other reads two measures.
    XL = "Pixel accuracy minus\nan all-background\nmask (points)"
    margins(ax2, M_SEM,
            f"SEM, {SEM['labelled_pct']:.2f}% crack\nall pixels scored",
            "o", "white", J.ACCENT, 1.3, 5.0)
    lb = J.panel_label(ax2, "b")
    ax2.set_xlabel(XL)
    margins(ax3, M_TXM,
            f"TXM, {TXM['labelled_pct']:.2f}% crack\nrefereed {COVER:.0f}% scored",
            "s", J.ACCENT2, "white", 0.6, 4.6)
    lc = J.panel_label(ax3, "c")
    ax3.set_xlabel(XL)

    # THE CONTROL THAT SAYS THE TWO PANELS REALLY DO SHARE A SCALE. Two axes set from one
    # pair of numbers can still drift apart if a later edit re-fits one of them, and the
    # drift is invisible -- the panels keep their shape and only the lengths lie.
    if ax2.get_xlim() != ax3.get_xlim() or list(ax2.get_xticks()) != list(ax3.get_xticks()):
        raise SystemExit(f"(b) and (c) are not on one scale: {ax2.get_xlim()} with "
                         f"{list(ax2.get_xticks())} against {ax3.get_xlim()} with "
                         f"{list(ax3.get_xticks())}")
    print(f"  CONTROL (b) and (c) share one axis, {ax2.get_xlim()[0]:.3g} to "
          f"{ax2.get_xlim()[1]:.3g} points, linear below {LIN:g}: PASS")

    # AND THE CONTROL THAT SAYS THE HEADINGS FIT. A panel letter sits outside the axes at
    # the height of its title's first line, so a title one word longer prints through it
    # -- which is what the edition before this one shipped, with "(b)" inside the word
    # "SEM". Measured at the renderer's own extents rather than counted in characters,
    # because the width of a string at 8 pt is a property of the face and not of its
    # length. One point of real overlap in both directions is a failure.
    fig.canvas.draw()
    _r = fig.canvas.get_renderer()
    _heads = [(f"({l})", lab) for l, lab in (("a", la), ("b", lb), ("c", lc))]
    _heads += [(f"title {l}", ax.title)
               for l, ax in (("a", ax1), ("b", ax2), ("c", ax3))]
    _tol = fig.dpi / 72.0
    _bad = []
    for _i in range(len(_heads)):
        for _j in range(_i + 1, len(_heads)):
            _a = _heads[_i][1].get_window_extent(renderer=_r)
            _b = _heads[_j][1].get_window_extent(renderer=_r)
            if (min(_a.x1, _b.x1) - max(_a.x0, _b.x0) > _tol
                    and min(_a.y1, _b.y1) - max(_a.y0, _b.y0) > _tol):
                _bad.append(f"{_heads[_i][0]} x {_heads[_j][0]}")
    if _bad:
        raise SystemExit("panel headings overlap: " + "; ".join(_bad))
    print(f"  CONTROL {len(_heads)} panel letters and titles, no overlapping pair: PASS")

    # One legend for the plate, not for a panel: the marker means the same thing in all
    # three, and a legend inside (a) would have to dodge eight rows of markers.
    fig.legend(handles=[
        Line2D([], [], marker="o", ls="none", ms=5.0, mfc="white", mec=J.ACCENT,
               mew=1.3, label=f"SEM  {N_SEM} Inconel 718 whole fields"),
        Line2D([], [], marker="s", ls="none", ms=4.6, mfc=J.ACCENT2, mec="white",
               mew=0.6, label=f"TXM  {TXM['n_frames']} frames, "
                              f"{len(TXM['groups'])} specimen groups")],
        loc="outside lower center", ncol=2, fontsize=J.TICK, handletextpad=0.35,
        columnspacing=2.0, borderaxespad=0.1)

    # "best on both" is a claim about THESE eight arms, and a reader who cannot see what
    # is missing will read it as a claim about every detector in the paper. The three
    # learned transmission models are not on these axes -- no SEM counterpart was ever
    # trained, and their only artefact is a grouped cross-validation reported as IoU --
    # and on transmission data the deployed one beats this rule by a wide margin. The
    # sidecar carries the full reason; the plate has to carry the fact.
    J.save(fig, os.path.join(OUT, FIGNAME + ".png"))

    # ---------------------------------------------------------------------------------
    sidecar = {
        "figure": FIGNAME + ".png",
        "column_class": "double, Elsevier 190 mm. journal_style.COLUMN_CLASS carries no "
                        "row for this plate and is not edited from here, so the class is "
                        "recorded in this sidecar instead.",
        "what": "one candidate list, scored in both microscopies, after the parameter of "
                "the previous figure is fixed: (a) the ratio of reported to annotated "
                "crack area, the one measure commensurable across the two arms, with both "
                "on a single logarithmic axis; (b, c) how far each arm's pixel accuracy "
                "falls below the accuracy an all-background mask already earns -- ONE "
                "measurement, run once per arm, both panels on one shared scale so the "
                "two can be read against each other; what differs is the area each "
                "collection adjudicated and how much of it is crack, which each title "
                "states",
        "why_b_and_c_are_logarithmic": "the shortfalls span three orders of magnitude in "
                                       "both arms, because global Otsu marks 99.5% of an "
                                       "SEM frame and 83.5% of a transmission frame. The "
                                       "plate this replaces solved that by dropping Otsu "
                                       "from the comparison; nothing is dropped here. The "
                                       "scale is SYMMETRICALLY logarithmic, not "
                                       "logarithmic, so zero -- the all-background mask "
                                       "itself -- stays a real position on the axis: both "
                                       "panels carry the reference rule and a stem from "
                                       "it, and an arm that beat the mask would be drawn "
                                       "to the right of the rule rather than reflected or "
                                       "dropped. Two arms in (c) are drawn there, and "
                                       "none in (b) is; the shared scale is what lets a "
                                       "reader see that from the two panels at once",
        "what_b_and_c_do_not_add": "the accuracy shortfall is close to a restatement of "
                                   "how much area an arm marks: a false positive costs a "
                                   "point and there are only so many crack pixels left to "
                                   "miss. The arms separate in (a). (b) and (c) price what "
                                   "(a) measures, and say that the price is never paid "
                                   "back in either microscopy",
        "the_question": "F6 chooses the constants of one detector. This plate asks whether "
                        "that detector is the right one, and asks it the same way in both "
                        "microscopies.",
        "parameter_carried_from_the_previous_figure": {
            "mad_k": PARAM_K,
            "verified_not_retyped": "the SEM detector row's pixel budget is matched "
                                    "against docs/figures/madk_above_five.json per_k; the "
                                    "plate aborts if the row is not the k = 6 budget",
            "note": "on the SEM collection the leave-one-image-out rule lands on k = 6 by "
                    "itself, so the detector row is F6's parameter and not a refit",
            "on_the_transmission_frames": {
                "drawn": "the same leave-one-frame-out rule every other arm gets, so no "
                         "arm in either panel is treated differently from its neighbours",
                "picked": TXM["arms"][HERO_KEY][TXM["arms"][HERO_KEY]["shown"]]["picks"],
                "and_if_k_is_instead_PINNED_at_the_previous_figure's_value": {
                    "mad_k": PARAM_K,
                    "area_agreement": K6_T["marked_pct"] / TXM["labelled_pct"],
                    "accuracy_margin_pp": (K6_T["accuracy_pct"]
                                           - TXM["empty_mask_accuracy_pct"]),
                    "source": "docs/figures/txm_classical_arms.json, "
                              f"by_param_frame_mean['{HERO_KEY}']['{PARAM_K!r}']"}}},
        "winner": {
            "overall": ARM_LABEL[winner].replace("\n", " "),
            "rule": "ranked by the WORSE of its two arms: max(|log10 area ratio|) over "
                    "SEM and TXM, smallest first. A model near parity on one microscopy "
                    "and an order of magnitude out on the other has not been shown to "
                    "transfer",
            "area_ratio_sem": A_SEM[winner], "area_ratio_txm": A_TXM[winner],
            "closest_on_sem_alone": ARM_LABEL[sem_best].replace("\n", " "),
            "closest_on_txm_alone": ARM_LABEL[txm_best].replace("\n", " ")},
        "ranking": [{"arm": ARM_LABEL[k].replace("\n", " "),
                     "area_ratio_sem": A_SEM[k], "area_ratio_txm": A_TXM[k],
                     "worse_arm_log10": worst(k),
                     "accuracy_margin_pp_sem": M_SEM[k],
                     "accuracy_margin_pp_txm": M_TXM[k],
                     "tuning_shown_sem": SEM["arms"][k]["tuned_by"],
                     "tuning_shown_txm": TXM["arms"][k]["shown"],
                     "free_params": SEM["arms"][k]["free_params"]} for k in order],
        "no_arm_beats_doing_nothing": {
            "sem": "every arm's accuracy margin is negative on the SEM whole fields: an "
                   "all-background mask scores "
                   f"{SEM['empty_mask_accuracy_pct']:.3f}% there and no arm reaches it",
            "txm": "and on the transmission frames, where an all-background mask scores "
                   f"{TXM['empty_mask_accuracy_pct']:.3f}%",
            "so": "accuracy is the panel that says none of these arms earns its keep as a "
                  "classifier of pixels; the area ratio in (a) is what separates them, and "
                  "it is the quantity the tool actually reports"},
        "two_conventions_and_why_they_are_not_on_one_axis": {
            "sem": "every pixel of the frame is scored; crack is "
                   f"{SEM['labelled_pct']:.3f}% of it",
            "txm": f"only the pixels a human adjudicated are scored -- {COVER:.1f}% "
                   f"of each frame -- and crack is {TXM['labelled_pct']:.3f}% of those",
            "what_the_two_conventions_change": "the FLOOR, not the scale. An arm that "
                                               "marks every pixel loses "
                                               f"{SEM['empty_mask_accuracy_pct']:.1f} "
                                               "points on the SEM collection and "
                                               f"{TXM['empty_mask_accuracy_pct']:.1f} on "
                                               "the transmission frames, because that is "
                                               "what the all-background mask earns in "
                                               "each. The measurement either side of that "
                                               "floor is the same one, so (b) and (c) are "
                                               "drawn on one shared scale -- same linear "
                                               "threshold, same limits, same ticks -- and "
                                               "the plate asserts it before saving",
            "shared_axis": "(a) shares ONE axis between the arms because the area ratio "
                           "is dimensionless and its reference is 1 in both. (b) and (c) "
                           "stay two panels, one per arm, but share one SCALE: the arms "
                           "are two collections, not two measures",
            "aggregation": "both arms are a mean over images of per-image percentages. "
                           "The archived transmission record pools pixels instead; that "
                           "aggregation is stored in docs/figures/txm_classical_arms.json "
                           "under pooled_by_param and is NOT what this plate draws"},
        "models_that_could_not_be_put_on_these_axes": {
            "the three learned transmission models": {
                "why_not": "no SEM counterpart exists -- no learned model of this project "
                           "was trained or scored on this SEM collection -- and their only "
                           "artefact is a 5-fold cross-validation grouped by IMAGE over "
                           f"{cv['labelled_images_used']} frames, reported as IoU. Three "
                           "mismatches at once: different corpus, different unit, and an "
                           "overlap score this project has measured to be unusable on TXM "
                           "paint (a correct 3 px crack scores 0.0498)",
                "TWO_VERSIONS_EXIST_AND_NEITHER_IS_DRAWN_HERE":
                    "the figure puts none of these on an axis, so no bar was swapped; "
                    "both versions are recorded instead, each labelled",
                "v4": {"recipe": "corrections_only_v4_overlap (per the retrain history)",
                       "17 channels": cv["f17_mean_iou"],
                       "+ frozen SAM": cv["hybrid_mean_iou"],
                       "mean of the two": cv["ens_mean_iou"],
                       "std_of_the_mean_of_the_two": cv["ens_std_iou"],
                       "precision": cv["mean_precision"], "recall": cv["mean_recall"],
                       "source": "docs/figures/txm_model_scores.json",
                       "status": "NOT the deployed weights"},
                "v5_DEPLOYED": {
                    "recipe": v5["gate_detail"]["recipe"], "stamp": v5["stamp"],
                    "17 channels": h5["mean_iou_17_only"],
                    "+ frozen SAM": h5["mean_iou_hybrid_only"],
                    "mean of the two": h5["mean_iou"],
                    "std_of_the_mean_of_the_two": h5["std_iou"],
                    "worst_fold": h5["min_iou"],
                    "precision": h5["mean_precision"], "recall": h5["mean_recall"],
                    "k": h5["k"], "grouped_by": h5["grouped_by"],
                    "labelled_images_used": h5["labelled_images_used"],
                    "weights": joblibs,
                    "source": "TXM_Crack_Detection_Pipeline/app_data/models/"
                              "retrain_history.json",
                    "status": "the pair the application loads"},
                "contradiction_in_the_paper's_own_record":
                    "docs/figures/txm_model_scores.json states "
                    f"\"{cv['model_version']}\". The second half of that sentence is "
                    "false: the deployed v5 pair has a 5-fold grouped-by-image artefact, "
                    "in the transmission project's retrain history at stamp "
                    f"{v5['stamp']}, recipe {v5['gate_detail']['recipe']}. The v4 block "
                    "in that file has not been edited from here; this sidecar records "
                    "both and flags the clash",
                "the_deployed_weights_have_no_held_out_score":
                    "the cross-validated numbers above are an estimate of the RECIPE, not "
                    "a score of the shipped weights. That run reports "
                    f"trained_on_images = {v5['trained_on_images']} with "
                    f"reference_held_out = {v5['reference_held_out']}, so the deployed "
                    "pair saw every one of the "
                    f"{h5['labelled_images_used']} labelled frames and any score of it on "
                    "one of them is in-sample",
                "convention": cv["convention"],
                "not_specimen_independent": cv["not_specimen_independent"]},
            "the published learned SEM baselines": {
                "why_not": "OmniCrack30k nnU-Net and zero-shot SAM 3 were scored on a "
                           "15-tile benchmark of this laboratory's own SEM frames "
                           "(docs/slides/comparison.json); nothing equivalent has ever "
                           "been run on the transmission frames, and at n = 15 nothing on "
                           "that benchmark separates statistically"}},
        #: THE SEM HALF OF THIS PLATE IS NOT AT THE SHIPPED SETTING, and it cannot be
        #: brought to it. Named here because an audit found it and a reader would not.
        "the_sem_rows_are_the_detector_without_its_classifier": (
            "the SEM arm is read from docs/figures/arms_background_units.json, which "
            "derives from arms_pixel_budget.py; that producer emits through the area "
            "floor -- clean_mask then a component floor -- and never calls the region "
            "classifier. The classifier is enabled in the shipped detector, so the row "
            "labelled DETECTOR here is the candidate stage, not the mask a user gets. "
            "Its unit set is the 31 public Inconel 718 whole fields, whose images were "
            "a download no longer held on this machine, so the comparison cannot be "
            "repeated at the shipped setting without re-obtaining that collection. "
            "What the comparison still supports is a statement about the DARKNESS RULE "
            "against other classical methods on the same images, which is what the "
            "plate is for; it does not support a statement about the shipped SEM "
            "detector's standing among them."),
        "selection_rule": {
            "both_arms": "each arm's single parameter is chosen leave-one-image-out on "
                         "the collection it is scored on, once by F1 and once by "
                         "area-fraction error, and the arm is shown at whichever of the "
                         "two gives IT the higher accuracy",
            "free_parameters": {ARM_LABEL[k].replace("\n", " "):
                                SEM["arms"][k]["free_params"] for k in order},
            "values_the_rule_picked_on_the_transmission_frames": {
                ARM_LABEL[k].replace("\n", " "):
                TXM["arms"][k][TXM["arms"][k]["shown"]]["picks"] for k in order},
            "the_sem_record_does_not_store_its_picks": "arms_background_units.json keeps "
                                                       "only which of the two tunings is "
                                                       "shown, not the parameter values "
                                                       "the leave-one-out rule chose; for "
                                                       "the detector the value is "
                                                       "recoverable and is checked above",
            "caution": "area-fraction parity can be reached by marking the right AMOUNT in "
                       "the wrong PLACES, which is why (b) and (c) are on the plate"},
        "positive_control_on_the_new_measurement": TXM["positive_control"],
        "n": {"sem_whole_fields": N_SEM,
              "txm_frames": TXM["n_frames"], "txm_groups": TXM["groups"]},
        "source": ["docs/figures/arms_background_units.json",
                   "docs/figures/txm_classical_arms.json",
                   "docs/figures/madk_above_five.json",
                   "docs/figures/txm_model_scores.json",
                   os.path.basename(
                       _paths.scoped("txm_background_units.json", scope=False))],
    }
    with open(os.path.join(OUT, FIGNAME + ".caption.json"), "w") as fh:
        json.dump(sidecar, fh, indent=1)
    print("wrote", os.path.join(OUT, FIGNAME + ".caption.json"))
    print(f"\nwinner on the worse of its two arms: {ARM_LABEL[winner]!r} "
          f"(SEM {A_SEM[winner]:.3f}x, TXM {A_TXM[winner]:.3f}x)")
    for k in order:
        print(f"  {ARM_LABEL[k].replace(chr(10), ' '):<38} SEM {A_SEM[k]:8.3f}x  "
              f"TXM {A_TXM[k]:8.3f}x   worse log10 {worst(k):5.3f}   "
              f"acc margin {M_SEM[k]:+7.2f} / {M_TXM[k]:+7.2f} pp")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if "--measure" in sys.argv or not os.path.exists(TXM_ARMS):
        measure()
    if "--measure-only" not in sys.argv:
        draw()
