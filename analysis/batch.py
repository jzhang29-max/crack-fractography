#!/usr/bin/env python3
"""Measure every mask in the corpus and write one dataset the app serves from.

Sources, and the reason each is a separate arm rather than one pooled pile:
  sem/gated    the SEM detector plus the operator's strokes, boundaries drawn by the image
  sem/machine  the SEM detector alone, no human input
  txm          the TXM export

They are kept apart because they are different instruments and, for the two SEM arms,
different definitions of the object. Pooling them would produce an average of things nobody
measured. The app lets you switch arms; it never adds them together.

SPECIMEN GROUPING comes from the SEM repo's own specimen_key(), not from a rule invented
here, so a frame is grouped the same way the published statistics group it. Frames from one
specimen are NOT independent: on the 2026-09-15 batch the nine fields per cell are a 3x3 grid
tiling ~1.2 x 1.1 mm of ONE specimen, so a per-specimen aggregate is the right unit and a
per-frame one is pseudo-replication.

Writes analysis/out/frames.json, analysis/out/cracks.json, analysis/out/specimens.json.
"""
import argparse
import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, REPO)

from app import paths as P                       # noqa: E402
for _d in P.sem_code_dirs():
    sys.path.insert(0, _d)

from measure import measure_path                 # noqa: E402
from scale import txm_specimen_key               # noqa: E402
import specimen_stats                            # noqa: E402

# The repo's own grouping, not a rule invented here. Absent without a SEM checkout, in which
# case SEM frames are not measurable anyway -- but uploads are, so the import must not be
# what stops the app from running.
try:
    from aggregate import specimen_key           # noqa: E402
except ImportError:
    def specimen_key(_stem):
        return None

OUT = P.OUT
SEM_DERIVED = P.sem_derived() or os.path.join(_HERE, "__no_sem_repo__")
ARMS = {
    "sem/gated": (os.path.join(SEM_DERIVED, "gated_masks"), "*_gated.png", "sem"),
    "sem/machine": (os.path.join(SEM_DERIVED, "machine_masks"), "*_machine.png", "sem"),
    "txm": (P.txm_export() or os.path.join(_HERE, "__no_txm_export__"),
            "*/*_crack_mask.png", "txm"),
    # Uploads are a first-class arm, not an append-only side channel. They used to be
    # written straight into frames.json by the upload endpoint, which meant a batch re-run
    # silently deleted every uploaded frame -- the masks stayed on disk and the rows
    # vanished. Measuring them here fixes that AND keeps them on the current metric set:
    # preserving the old rows instead would have left uploads carrying whatever metrics
    # existed when they were uploaded, silently mixed with everything else.
    "uploads": (P.UPLOADS, "*_gated.png", "sem"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", choices=list(ARMS) + ["all"], default=None)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    arms = list(ARMS) if (not a.arm or "all" in a.arm) else a.arm

    P.ensure_dirs()
    frames, cracks = [], []
    for arm in arms:
        root, pat, modality = ARMS[arm]
        paths = sorted(glob.glob(os.path.join(root, pat)))
        if a.limit:
            paths = paths[: a.limit]
        if not paths:
            print(f"  {arm}: no masks under {root} -- skipped", flush=True)
            continue
        print(f"  {arm}: {len(paths)} masks", flush=True)
        for i, p in enumerate(paths, 1):
            try:
                rows, summ = measure_path(p, modality)
            except Exception as e:
                print(f"    [{i}/{len(paths)}] {os.path.basename(p)[:48]} FAILED "
                      f"{type(e).__name__}: {e}", flush=True)
                continue
            summ["arm"] = arm
            summ["specimen"] = ("uploaded" if arm == "uploads" else
                            (txm_specimen_key(summ["frame"]) if modality == "txm"
                             else specimen_key(summ["frame"])) or "unparsed")
            frames.append(summ)
            for r in rows:
                r["frame"] = summ["frame"]
                r["arm"] = arm
                r["specimen"] = summ["specimen"]
            cracks.extend(rows)
            if i % 20 == 0 or i == len(paths):
                print(f"    [{i}/{len(paths)}] {summ['frame'][:44]:<44} "
                      f"{summ['n_cracks_measured']:>5} cracks", flush=True)

    # Per specimen, per arm. Frames within a specimen are not independent, so the specimen is
    # the inferential unit; frame-level spread is reported so the reader can see it.
    #
    # MERGING MAKES THIS SUBTLE. Specimen records are recomputed only for the arms in this
    # run, so an --arm run must read the carried-over frames too or it would rewrite the
    # specimen table for arms it never measured.
    prior_frames = []
    fp = os.path.join(OUT, "frames.json")
    if os.path.exists(fp):
        try:
            prior_frames = [r for r in json.load(open(fp)) if r.get("arm") not in set(arms)]
        except Exception:
            prior_frames = []
    all_frames = frames + prior_frames

    by_arm = defaultdict(list)
    for f in all_frames:
        by_arm[f["arm"]].append(f)

    spec = defaultdict(list)
    for f in frames:
        spec[(f["arm"], f["specimen"])].append(f)
    specimens = []
    for (arm, s), fs in sorted(spec.items()):
        rec = specimen_stats.summarise(arm, s, fs)
        # Segmentation sensitivity, on identical frames. Only meaningful for the SEM arms.
        rec["arm_sensitivity"] = (specimen_stats.paired_arm_ratio(by_arm, s)
                                  if arm.startswith("sem/") else None)
        specimens.append(rec)

    # MERGE, do not replace. Writing the whole file on every run made --arm a data-loss
    # footgun: `--arm uploads` overwrote 355 measured frames with 2, and only the arms in
    # THIS run survived. Records for arms that were not re-run are carried over untouched;
    # records for arms that WERE re-run are replaced wholesale, so a frame deleted upstream
    # does not linger.
    ran = set(arms)
    for name, obj in (("frames.json", frames), ("cracks.json", cracks),
                      ("specimens.json", specimens)):
        path = os.path.join(OUT, name)
        prior = []
        if os.path.exists(path):
            try:
                prior = [r for r in json.load(open(path)) if r.get("arm") not in ran]
            except Exception as e:
                print(f"  could not read existing {name} ({type(e).__name__}); "
                      f"writing only this run's records")
        merged = prior + obj
        with open(path, "w") as fh:
            json.dump(merged, fh)
        kept = len(merged) - len(obj)
        print(f"  wrote {name}: {len(merged):,} records "
              f"({len(obj):,} from this run, {kept:,} carried over) "
              f"({os.path.getsize(path)/1e6:.1f} MB)")

    print(f"\n  {len(frames)} frames, {len(cracks):,} cracks, {len(specimens)} specimen-arms")
    ns = sum(1 for f in frames if not f["scale_known"])
    print(f"  frames without a physical scale: {ns} (their um columns are null, by design)")
    thin = [s for s in specimens if not s["estimable_dispersion"]]
    print(f"  specimen-arms with <3 frames, where dispersion is not estimable: {len(thin)}")


if __name__ == "__main__":
    main()
