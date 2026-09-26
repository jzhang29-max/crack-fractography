#!/usr/bin/env python3
"""JSON API + the single page that consumes it.

The server does no measurement. analysis/batch.py produces frames.json / cracks.json /
specimens.json and this reads them, so the page can never show a number that was computed
differently from the one in the dataset. If the dataset is missing, every endpoint says so
rather than returning an empty list that would render as "no cracks".

Arms are never mixed. sem/gated, sem/machine and txm are different instruments or different
definitions of the object, so the API requires an arm and refuses to aggregate across them.
"""
import json
import os

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
OUT = os.path.join(REPO, "analysis", "out")
SEM_DERIVED = os.path.join(REPO, "data", "sem", "crack_export", "derived")

app = FastAPI(title="crack fractography")
_CACHE = {}


def _load(name):
    if name in _CACHE:
        return _CACHE[name]
    p = os.path.join(OUT, f"{name}.json")
    if not os.path.exists(p):
        raise HTTPException(503, f"{name}.json not built yet -- run analysis/batch.py")
    _CACHE[name] = json.load(open(p))
    return _CACHE[name]


@app.get("/api/arms")
def arms():
    """Which arms exist, with their frame counts and scale coverage."""
    fr = _load("frames")
    out = {}
    for f in fr:
        a = out.setdefault(f["arm"], {"arm": f["arm"], "n_frames": 0, "n_scaled": 0,
                                      "n_cracks": 0, "specimens": set()})
        a["n_frames"] += 1
        a["n_scaled"] += 1 if f["scale_known"] else 0
        a["n_cracks"] += f["n_cracks_measured"]
        a["specimens"].add(f["specimen"])
    for a in out.values():
        a["n_specimens"] = len(a.pop("specimens"))
    return sorted(out.values(), key=lambda a: a["arm"])


@app.get("/api/frames")
def frames(arm: str = Query(...), specimen: str | None = None):
    fr = [f for f in _load("frames") if f["arm"] == arm]
    if specimen:
        fr = [f for f in fr if f["specimen"] == specimen]
    if not fr:
        raise HTTPException(404, f"no frames for arm={arm!r} specimen={specimen!r}")
    return sorted(fr, key=lambda f: f["frame"])


@app.get("/api/specimens")
def specimens(arm: str = Query(...)):
    sp = [s for s in _load("specimens") if s["arm"] == arm]
    if not sp:
        raise HTTPException(404, f"no specimens for arm={arm!r}")
    return sp


@app.get("/api/cracks")
def cracks(frame: str = Query(...), arm: str = Query(...),
           limit: int = 2000, sort: str = "area_px"):
    """Per-crack rows for one frame. Capped, and the cap is REPORTED: a silent top-N would
    make a 5000-crack frame look like a 2000-crack frame."""
    cr = [c for c in _load("cracks") if c["frame"] == frame and c["arm"] == arm]
    total = len(cr)
    key = sort if sort in ("area_px", "SkeletonLength_px", "MeanWidth_px") else "area_px"
    cr.sort(key=lambda c: (c.get(key) is None, -(c.get(key) or 0)))
    return {"frame": frame, "arm": arm, "n_total": total, "n_returned": min(total, limit),
            "truncated": total > limit, "sorted_by": key, "cracks": cr[:limit]}


@app.get("/api/mask/{arm:path}/{frame}")
def mask(arm: str, frame: str):
    """The mask PNG itself, so the page can show what a number was measured on."""
    src = {"sem/gated": (os.path.join(SEM_DERIVED, "gated_masks"), "_gated.png"),
           "sem/machine": (os.path.join(SEM_DERIVED, "machine_masks"), "_machine.png"),
           "uploads": (os.path.join(REPO, "analysis", "out", "uploads"), "_gated.png")}
    if arm in src:
        root, suf = src[arm]
        p = os.path.join(root, frame + suf)
    elif arm == "txm":
        p = os.path.join(REPO, "data", "txm_export", frame, f"{frame}_crack_mask.png")
    else:
        raise HTTPException(400, f"unknown arm {arm!r}")
    if not os.path.exists(p):
        raise HTTPException(404, f"no mask on disk for {frame!r} in {arm!r}")
    return FileResponse(p, media_type="image/png")


@app.get("/api/export.csv")
def export_csv(arm: str = Query(...), level: str = "frames"):
    """Flat CSV of whatever is on screen, because the table IS the product for most users."""
    import csv
    import io
    if level not in ("frames", "specimens", "cracks"):
        raise HTTPException(400, "level must be frames, specimens or cracks")
    rows = [r for r in _load(level) if r.get("arm") == arm]
    if not rows:
        raise HTTPException(404, f"nothing for arm={arm!r} at level={level!r}")
    keys, seen = [], set()
    for r in rows:
        for k in r:
            if k not in seen and not isinstance(r[k], (dict, list)):
                seen.add(k); keys.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition":
                             f'attachment; filename="{arm.replace("/", "_")}_{level}.csv"'})


# ---------------------------------------------------------------------------------------
# Upload. Two kinds of file, because the owner has both and the split is not the user's job
# to remember:
#   a MASK (.png/.bmp)  -> measured directly
#   a MICROGRAPH (.tif) -> segmented first, then measured
#
# The detector lives in the sibling SEM repo and needs pandas, cv2 and a model bundle that
# this app deliberately does not carry. It is invoked as a subprocess with THAT repo's
# interpreter rather than imported, which is the only thing that can work across two venvs.
UPLOAD_DIR = os.path.join(REPO, "analysis", "out", "uploads")
MASK_EXT = {".png", ".bmp", ".gif"}
IMAGE_EXT = {".tif", ".tiff"}
MAX_UPLOAD_MB = 200


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    import shutil
    import subprocess
    import sys as _sys
    import tempfile

    name = os.path.basename(file.filename or "")
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext not in MASK_EXT | IMAGE_EXT:
        raise HTTPException(400, f"{ext or 'no extension'} is not supported. Upload a mask "
                                 f"(.png/.bmp) or a micrograph (.tif/.tiff).")
    if not stem:
        raise HTTPException(400, "the file needs a name")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    blob = await file.read()
    if len(blob) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"{len(blob)/1e6:.0f} MB is over the {MAX_UPLOAD_MB} MB limit")

    detected = False
    if ext in MASK_EXT:
        mask_path = os.path.join(UPLOAD_DIR, f"{stem}_gated.png")
        with open(mask_path, "wb") as fh:
            fh.write(blob)
    else:
        # Stage into the SEM repo's originals under a temp name -- run_unified_pipeline
        # resolves its input by stem from there -- then remove it. The repo's own corpus is
        # never modified: the staged file is deleted in the finally block whatever happens.
        sem = os.path.join(REPO, "data", "sem")
        py = os.path.join(sem, ".venv", "bin", "python3")
        if not os.path.exists(py):
            raise HTTPException(503, "the SEM repo's virtualenv is not built, so a raw "
                                     "micrograph cannot be segmented. Upload a mask instead, "
                                     "or run ./run in the sem-crack-detector repo first.")
        tmp_stem = f"__upload_{os.getpid()}_{abs(hash(stem)) % 10**6}"
        staged = os.path.join(sem, "original", tmp_stem + ".tif")
        mask_path = os.path.join(UPLOAD_DIR, f"{stem}_gated.png")
        try:
            with open(staged, "wb") as fh:
                fh.write(blob)
            r = subprocess.run(
                [py, os.path.join(REPO, "analysis", "detect_one.py"), staged, mask_path, sem],
                capture_output=True, text=True, timeout=1800)
            if r.returncode != 0:
                why = (r.stderr or r.stdout or "").strip()[-500:]
                raise HTTPException(500, f"segmentation failed: {why}")
            detected = True
        finally:
            for p in (staged,):
                if os.path.exists(p):
                    os.remove(p)

    # Measure with the SAME code every other arm uses, so an uploaded frame is comparable.
    _sys.path.insert(0, os.path.join(REPO, "analysis"))
    from measure import measure_path
    try:
        rows, summ = measure_path(mask_path, "sem", stem=stem)
    except Exception as e:
        raise HTTPException(500, f"measurement failed: {type(e).__name__}: {e}")
    summ["arm"] = "uploads"
    summ["specimen"] = "uploaded"
    summ["was_segmented_here"] = detected
    for r in rows:
        r["frame"] = stem
        r["arm"] = "uploads"
        r["specimen"] = "uploaded"

    # Append to the served dataset and drop the cache so the page sees it immediately.
    for fname, new in (("frames", [summ]), ("cracks", rows)):
        p = os.path.join(OUT, f"{fname}.json")
        cur = json.load(open(p)) if os.path.exists(p) else []
        cur = [x for x in cur if not (x.get("arm") == "uploads" and x.get("frame") == stem)]
        cur.extend(new)
        with open(p, "w") as fh:
            json.dump(cur, fh)
    _CACHE.clear()

    return {"ok": True, "frame": stem, "arm": "uploads", "segmented_here": detected,
            "scale_known": summ["scale_known"],
            "n_cracks": summ["n_cracks_measured"], "n_specks": summ["speck_count"],
            "area_fraction": summ["area_fraction"],
            "note": ("segmented here with the SEM detector, then measured"
                     if detected else "measured as a mask, as uploaded")}


@app.get("/")
def index():
    p = os.path.join(_HERE, "templates", "index.html")
    if not os.path.exists(p):
        return HTMLResponse("<h1>index.html missing</h1>", status_code=500)
    return HTMLResponse(open(p).read())


# Mounted last so it cannot shadow /api/*.
app.mount("/static", StaticFiles(directory=os.path.join(_HERE, "static")), name="static")
