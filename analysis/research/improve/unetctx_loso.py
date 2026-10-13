"""Driver: train every (arm, held-out specimen) fold, and the sabotage controls.

Folds. Nine of the 13 tile specimens have painted frames and get their own model trained
without them. The other four have no painted frame at all, so the all-paint model is
already held out for their 13 tiles. Ten models per arm.

Sabotage. Three broken versions of the same pipeline, trained and scored identically:
shuffled labels (each patch keeps its image and gets another patch's paint), rotated
labels (the paint is turned 90 degrees against its own image), and constant input (the
image is replaced by zeros). If a broken version still scores near the real one, the score
is coming from the harness or from the shape of the paint, not from the method.

Runs folds as separate processes: convolution on this CPU barely scales past two threads
(0.6 Mpx/s at 2 threads, 0.8 at 12), so six processes of two beat one of twelve by ~4x.
"""
import os, sys, subprocess, argparse, time
import numpy as np

HERE = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve"
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import unetctx_base as B
import unetctx_train as TR
import ctx_core as CC

PY = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python"


def folds():
    paint_specs = {B.specimen_of(n) for n in B.frame_names()}
    tile_specs = {t["specimen"] for t in CC.tiles()}
    own = sorted(paint_specs & tile_specs)
    return [None] + own


def run_parallel(jobs, nproc=6, nt=2):
    """jobs: list of (arm, holdout, seed)."""
    todo = [j for j in jobs
            if not os.path.exists(os.path.join(
                TR.MODELS, f"{j[0]}__{j[1] or 'ALL'}__s{j[2]}.pt"))]
    print(f"{len(jobs)} folds, {len(todo)} to train, {nproc} at a time")
    env = dict(os.environ, NT=str(nt), OMP_NUM_THREADS=str(nt), MKL_NUM_THREADS=str(nt))
    running, i, t0 = [], 0, time.time()
    while i < len(todo) or running:
        while len(running) < nproc and i < len(todo):
            arm, hold, seed = todo[i]
            log = open(os.path.join(B.MY, f"log_{arm}_{hold or 'ALL'}_{seed}.txt"), "w")
            running.append((subprocess.Popen(
                [PY, "-B", os.path.join(HERE, "unetctx_train.py"), arm,
                 hold or "ALL", str(seed)], env=env, stdout=log, stderr=subprocess.STDOUT),
                f"{arm}/{hold or 'ALL'}/s{seed}", log))
            i += 1
        time.sleep(5)
        for r in list(running):
            if r[0].poll() is not None:
                running.remove(r); r[2].close()
                print(f"  [{time.time()-t0:6.0f}s] done {r[1]} rc={r[0].returncode}", flush=True)
    print(f"all folds done in {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default=",".join(TR.ARMS))
    ap.add_argument("--nproc", type=int, default=6)
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--all-only", action="store_true")
    a = ap.parse_args()
    fs = [None] if a.all_only else folds()
    jobs = [(arm, h, int(s)) for arm in a.arms.split(",")
            for h in fs for s in a.seeds.split(",")]
    print("folds:", [f or "ALL" for f in fs])
    run_parallel(jobs, a.nproc)
