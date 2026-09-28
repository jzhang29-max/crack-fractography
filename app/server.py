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
import time

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from . import paths as P

_HERE = os.path.dirname(os.path.abspath(__file__))
RES = P.RES
OUT = P.OUT

app = FastAPI(title="crack fractography")
# name -> ((mtime_ns, size), parsed). The stamp is half the entry: see _load.
_CACHE = {}


def _load_quiet(name):
    """_load, but returns None instead of raising when the dataset does not exist yet."""
    try:
        return _load(name)
    except HTTPException:
        return None


def _load(name):
    """Read one dataset file, re-reading it whenever the bytes on disk change.

    Keyed on the file's (mtime_ns, size), not on the name alone. Keyed on the name, a
    server started before an out-of-process `analysis/batch.py --arm all` run served the
    pre-run dataset for the rest of its life -- and that failure did not look like
    staleness. Observed 2026-09-27: the page served the CURRENT app.js against the OLD
    records, so one row showed newly written explanatory prose beside a stale number, and
    a newly added row was silently absent because its field did not exist in the cached
    records. A half-fresh page reads as a live one, which is worse than an obviously old
    one. The three writers inside this process already dropped the cache; nothing covered
    a rebuild run from the command line, which is how the corpus is normally measured.

    Swapping the object out is safe because no caller mutates what it gets back: every
    endpoint filters into a new list before sorting, figures.py copies each record it
    edits, conclusions.py only reads, and the upload path re-reads the file from disk
    rather than appending to the cached list.

    batch.py truncates these files in place and streams tens of MB into them, and
    /api/measure_corpus runs it on a thread inside THIS process, so a reload can land on
    a partly written file. A stale-but-valid dataset beats a 500 in the middle of a
    rebuild, so a failed reload keeps serving the last good copy and leaves the stamp
    alone, which makes the next request try again.
    """
    p = os.path.join(OUT, f"{name}.json")
    try:
        st = os.stat(p)
    except OSError:
        raise HTTPException(503, f"{name}.json not built yet -- run analysis/batch.py")
    stamp = (st.st_mtime_ns, st.st_size)
    cached = _CACHE.get(name)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    try:
        with open(p) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        if cached is not None:
            return cached[1]
        raise HTTPException(503, f"{name}.json is being written -- retry in a moment")
    _CACHE[name] = (stamp, data)
    return data


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
    derived = P.sem_derived()
    src = {"sem/gated": (derived and os.path.join(derived, "gated_masks"), "_gated.png"),
           "sem/machine": (derived and os.path.join(derived, "machine_masks"), "_machine.png"),
           "uploads": (P.UPLOADS, "_gated.png")}
    if arm in src:
        root, suf = src[arm]
        if not root:
            raise HTTPException(503, "no SEM repo is configured, so its masks cannot be "
                                     "shown. Set one in Setup.")
        p = os.path.join(root, frame + suf)
    elif arm == "txm":
        tx = P.txm_export()
        if not tx:
            raise HTTPException(503, "no TXM export is configured, so its masks cannot be "
                                     "shown. Set one in Setup.")
        p = os.path.join(tx, frame, f"{frame}_crack_mask.png")
    else:
        raise HTTPException(400, f"unknown arm {arm!r}")
    if not os.path.exists(p):
        raise HTTPException(404, f"no mask on disk for {frame!r} in {arm!r}")
    return FileResponse(p, media_type="image/png")


@app.get("/api/export.csv")
def export_csv(arm: str = Query(...), level: str = "frames",
               specimen: str | None = None, min_area_px: int = 0):
    """Flat CSV of whatever is on screen, because the table IS the product for most users.

    "Whatever is on screen" is now true. It was not: the min-area slider and the specimen
    selector were client-side only, so a filtered view exported unfiltered rows and the
    exported file carried no record of the filter. A citable number that silently disagrees
    with the screen it came from is worse than no export.
    """
    import csv
    import io
    if level not in ("frames", "specimens", "cracks"):
        raise HTTPException(400, "level must be frames, specimens or cracks")
    rows = [r for r in _load(level) if r.get("arm") == arm]
    if specimen:
        rows = [r for r in rows if r.get("specimen") == specimen]
    n_before = len(rows)
    if min_area_px and level == "cracks":
        rows = [r for r in rows if (r.get("area_px") or 0) >= min_area_px]
    if not rows:
        raise HTTPException(404, f"nothing for arm={arm!r} at level={level!r}")
    keys, seen = [], set()
    for r in rows:
        for k in r:
            if k not in seen and not isinstance(r[k], (dict, list)):
                seen.add(k); keys.append(k)
    buf = io.StringIO()
    # The filters travel WITH the data. A CSV that does not record what was excluded cannot
    # be reconciled with the figure it sits beside six months later.
    buf.write(f"# crack-fractography export  arm={arm}  level={level}"
              f"  specimen={specimen or 'all'}"
              f"  min_area_px={min_area_px}"
              f"  rows={len(rows)} of {n_before} before filtering\n")
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
UPLOAD_DIR = P.UPLOADS
MASK_EXT = {".png", ".bmp", ".gif"}
IMAGE_EXT = {".tif", ".tiff"}
MAX_UPLOAD_MB = 200


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), nm_per_px: float | None = None):
    import shutil
    import subprocess
    import sys as _sys
    import tempfile

    import sys as _sys
    _sys.path.insert(0, os.path.join(RES, "analysis"))
    from measure import canonical_stem

    name = os.path.basename(file.filename or "")
    raw_stem, ext = os.path.splitext(name)
    ext = ext.lower()
    # ONE stem for the saved file, the crack rows, the frame record and the response.
    # These were three different strings: the frame was stored stripped of its _gated
    # suffix while its rows and its mask file kept it, so /api/cracks and /api/mask both
    # missed a frame the read-out had just described.
    stem = canonical_stem(raw_stem) or raw_stem
    if ext not in MASK_EXT | IMAGE_EXT:
        raise HTTPException(400, f"{ext or 'no extension'} is not supported. Upload a mask "
                                 f"(.png/.bmp) or a micrograph (.tif/.tiff).")
    if not stem:
        raise HTTPException(400, "the file needs a name")

    # A DIFFERENT FILE THAT CANONICALISES TO THE SAME FRAME IS REFUSED, NOT OVERWRITTEN.
    # canonical_stem strips the mask suffix, so weld.png and weld_mask.png are both frame
    # "weld": uploading the second replaced the first, and the only sign was the crack count
    # changing on a row the user was not looking at. Re-uploading the SAME filename still
    # replaces, because that is how you re-measure after correcting a mask in the Mark tab
    # -- which is the whole point of that tab, so it must not be the case that gets blocked.
    existing = next((f for f in (_load_quiet("frames") or [])
                     if f.get("arm") == "uploads" and f.get("frame") == stem), None)
    if existing is not None and existing.get("source_filename") not in (None, name):
        raise HTTPException(409,
            f"{name!r} and {existing['source_filename']!r} are both frame {stem!r} once the "
            f"mask suffix is stripped, and accepting this would replace the measurement "
            f"already stored for it. Rename one of them.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    blob = await file.read()
    if len(blob) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"{len(blob)/1e6:.0f} MB is over the {MAX_UPLOAD_MB} MB limit")

    detected = False
    _tif_scale = [None]

    def _from_tiff_quiet(path):
        import sys as _s3
        _s3.path.insert(0, os.path.join(RES, "analysis"))
        try:
            import scale as _sc
            return _sc.from_tiff(path)
        except Exception:
            return None

    if ext in MASK_EXT:
        mask_path = os.path.join(UPLOAD_DIR, f"{stem}_gated.png")
        with open(mask_path, "wb") as fh:
            fh.write(blob)
    else:
        # Stage into the SEM repo's originals under a temp name -- run_unified_pipeline
        # resolves its input by stem from there -- then remove it. The repo's own corpus is
        # never modified: the staged file is deleted in the finally block whatever happens.
        sem = P.sem_repo()
        py = P.sem_python()
        if not sem:
            raise HTTPException(503, "no SEM repo is configured, so a raw micrograph cannot "
                                     "be segmented. Upload a black-and-white mask instead, "
                                     "or point the app at a sem-crack-detector checkout in "
                                     "Setup.")
        if not py:
            raise HTTPException(503, "the SEM repo's virtualenv is not built, so a raw "
                                     "micrograph cannot be segmented. Upload a mask instead, "
                                     "or run ./run in that repo once first.")
        tmp_stem = f"__upload_{os.getpid()}_{abs(hash(stem)) % 10**6}"
        staged = os.path.join(sem, "original", tmp_stem + ".tif")
        mask_path = os.path.join(UPLOAD_DIR, f"{stem}_gated.png")
        try:
            with open(staged, "wb") as fh:
                fh.write(blob)
            r = subprocess.run(
                [py, os.path.join(RES, "analysis", "detect_one.py"), staged, mask_path, sem],
                capture_output=True, text=True, timeout=1800)
            if r.returncode != 0:
                why = (r.stderr or r.stdout or "").strip()[-500:]
                raise HTTPException(500, f"segmentation failed: {why}")
            detected = True
        finally:
            # Read the scale out of the ORIGINAL tif before the staged copy is removed:
            # the derived mask is a PNG and carries no instrument metadata.
            if os.path.exists(staged):
                try:
                    _tif_scale[0] = _from_tiff_quiet(staged)
                finally:
                    os.remove(staged)

    # SCALE, BEFORE MEASURING, because every physical column depends on it.
    #
    # Until now nm_per_px() could only return the TXM constant or look up the author's own
    # extracted CSV keyed by the author's own frame stems, so P10, P20, P21, S_V, MCL, TCL,
    # spacing and every micrometre column were permanently null for everybody else and the
    # app quietly became a pixel-only tool the moment someone else used it.
    import sys as _s2
    _s2.path.insert(0, os.path.join(RES, "analysis"))
    import scale as _scale
    scale_note = None
    if nm_per_px is not None:
        try:
            _scale.set_user_scale(stem, nm_per_px)
            scale_note = f"scale set to {nm_per_px} nm/px"
        except ValueError as e:
            raise HTTPException(400, str(e))
    elif ext in IMAGE_EXT:
        found = _tif_scale[0]
        if found:
            _scale.set_user_scale(stem, found)
            scale_note = f"{found} nm/px read from the TIFF's FEI metadata"

    # Measure with the SAME code every other arm uses, so an uploaded frame is comparable.
    _sys.path.insert(0, os.path.join(RES, "analysis"))
    from measure import measure_path
    try:
        rows, summ = measure_path(mask_path, "sem", stem=stem)
    except Exception as e:
        raise HTTPException(500, f"measurement failed: {type(e).__name__}: {e}")
    summ["arm"] = "uploads"
    summ["specimen"] = "uploaded"
    # The filename as given, so a later upload can tell "the same file again" from "a
    # different file with a colliding name".
    summ["source_filename"] = name
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

    # And rebuild the uploads specimen record. Without this an upload adds a frame and no
    # specimen, so the specimen card -- the FIRST card on the page -- simply disappeared
    # for the uploads arm, which is the only arm a downloaded copy has. batch.py maintains
    # this table for every other arm; the upload path was writing two of the three files.
    _rebuild_uploads_specimen()
    _CACHE.clear()

    return {"ok": True, "frame": summ["frame"], "arm": "uploads",
            "renamed_from": (raw_stem if raw_stem != summ["frame"] else None),
            "segmented_here": detected,
            "scale_known": summ["scale_known"],
            "n_cracks": summ["n_cracks_measured"], "n_specks": summ["speck_count"],
            "area_fraction": summ["area_fraction"],
            "scale_note": scale_note,
            "note": ("segmented here with the SEM detector, then measured"
                     if detected else "measured as a mask, as uploaded")}


def _rebuild_uploads_specimen():
    """Recompute the uploads arm's specimen record from whatever frames are on disk.

    Only the uploads arm: every other arm's record is batch.py's, and recomputing those
    here would let a web request silently rewrite the measured dataset.
    """
    import sys as _sys
    _sys.path.insert(0, os.path.join(RES, "analysis"))
    try:
        import specimen_stats
    except ImportError:
        return
    fp = os.path.join(OUT, "frames.json")
    sp = os.path.join(OUT, "specimens.json")
    if not os.path.exists(fp):
        return
    frames = [f for f in json.load(open(fp)) if f.get("arm") == "uploads"]
    others = []
    if os.path.exists(sp):
        try:
            others = [r for r in json.load(open(sp)) if r.get("arm") != "uploads"]
        except Exception:
            others = []
    recs = []
    for spec in sorted({f.get("specimen") or "uploaded" for f in frames}):
        fs = [f for f in frames if (f.get("specimen") or "uploaded") == spec]
        r = specimen_stats.summarise("uploads", spec, fs)
        r["arm_sensitivity"] = None
        recs.append(r)
    with open(sp, "w") as fh:
        json.dump(others + recs, fh)


# ---------------------------------------------------------------------------------------
# MARKING. The tool that draws the masks this app measures already exists -- it is
# interior_active_learning/code/paint_server.py in the SEM repo, a Flask app with Add
# crack / Not crack / Erase / Brush / Whole region and a Retrain button. It was reachable
# only by knowing it was there and starting it by hand on another port, which is exactly
# the "two separate apps" confusion: this app would refuse a bad mask and say nothing about
# where to fix it.
#
# Started as a subprocess with the SEM REPO'S interpreter, the same way detection is,
# because it needs Flask and a model bundle this app deliberately does not carry.
_PAINT = {"proc": None, "port": None}
PAINT_PORT = 8767


def _listening(port):
    """Is something answering on this port? Asked of the socket, not of a handle we kept."""
    import socket
    with socket.socket() as t:
        t.settimeout(0.3)
        return t.connect_ex(("127.0.0.1", port)) == 0


def _paint_alive():
    """Whether the marking tool is reachable, NOT whether this process started it.

    It was the latter, so restarting this server reported a perfectly healthy tool as
    stopped and offered to start a second one -- the subprocess handle lives in memory and
    the tool does not. Same shape as the dataset cache keyed on a name: state held here
    that should be read from the world.
    """
    p = _PAINT["proc"]
    if p and p.poll() is None:
        return True
    for port in (_PAINT.get("port"), PAINT_PORT):
        if port and _listening(port):
            _PAINT["port"] = port
            return True
    return False


@app.get("/api/paint")
def paint_status():
    sem = P.sem_repo()
    py = P.sem_python()
    alive = _paint_alive()
    return {
        "available": bool(sem and py),
        "why_not": (None if (sem and py) else
                    ("no SEM repo is configured" if not sem else
                     "the SEM repo's virtualenv is not built -- run ./run in it once")),
        "running": alive,
        "url": (f"http://127.0.0.1:{_PAINT['port']}" if alive else None),
        "note": "the marking tool writes corrections into the SEM repo, and this app reads "
                "them back on the next measure",
    }


@app.post("/api/paint")
def paint_start():
    import socket
    import subprocess
    if _paint_alive():
        return paint_status()
    sem, py = P.sem_repo(), P.sem_python()
    if not (sem and py):
        raise HTTPException(503, paint_status()["why_not"])
    code = os.path.join(sem, "interior_active_learning", "code")
    script = os.path.join(code, "paint_server.py")
    if not os.path.exists(script):
        raise HTTPException(503, f"no marking tool at {script}")

    # Its own default port first, so a tool the user already had open on 8767 is reused
    # rather than duplicated; otherwise whatever the OS gives us.
    port = PAINT_PORT
    if _listening(port):
        _PAINT["port"] = port
        return {**paint_status(), "reused": True}
    with socket.socket() as t:
        try:
            t.bind(("127.0.0.1", port))
        except OSError:
            t.bind(("127.0.0.1", 0))
            port = t.getsockname()[1]

    _PAINT["proc"] = subprocess.Popen(
        [py, script], cwd=code,
        env={**os.environ, "PORT": str(port)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _PAINT["port"] = port

    # Wait for it to answer rather than returning a URL that 404s for two seconds.
    import time as _t
    for _ in range(80):
        if not _paint_alive():
            raise HTTPException(500, "the marking tool exited during startup")
        with socket.socket() as t:
            if t.connect_ex(("127.0.0.1", port)) == 0:
                return paint_status()
        _t.sleep(0.25)
    raise HTTPException(504, "the marking tool did not start within 20s")


# ---------------------------------------------------------------------------------------
# RE-MEASURE ONE FRAME. The loop the app is for is: detect, look, correct, measure again.
# Until now the last step was a full-corpus rebuild -- 358 frames, about 17 minutes -- so
# after correcting a single mask there was no way to see what changed short of rebuilding
# everything. That is not a loop, it is a one-way trip with a long way back.
#
# It reads whatever mask is on disk NOW and reports that file's timestamp, because
# corrections are painted into the SEM repo's paint layer and only reach a derived mask
# after that tool re-applies and exports. The timestamp is how a user tells "my corrections
# are in this number" from "I am re-measuring the same bytes as last time".
def _mask_path(arm, frame):
    derived = P.sem_derived()
    src = {"sem/gated": (derived and os.path.join(derived, "gated_masks"), "_gated.png"),
           "sem/machine": (derived and os.path.join(derived, "machine_masks"), "_machine.png"),
           "uploads": (P.UPLOADS, "_gated.png")}
    if arm in src:
        root, suf = src[arm]
        return os.path.join(root, frame + suf) if root else None
    if arm == "txm":
        tx = P.txm_export()
        return os.path.join(tx, frame, f"{frame}_crack_mask.png") if tx else None
    return None


@app.post("/api/scale")
def set_scale(arm: str = Query(...), frame: str = Query(...),
              nm_per_px: float | None = None):
    """Set (or clear) a frame's nm/px, then re-measure it so the physical columns appear.

    A mask arrives as a PNG and carries no instrument metadata, so for most uploads this is
    the ONLY way a physical unit can ever exist. Without it the app is correct and useless
    to anyone but its author: it withholds micrometres, which is the right behaviour, but
    it gave nobody a way to supply what it was withholding them for.
    """
    import sys as _sys
    _sys.path.insert(0, os.path.join(RES, "analysis"))
    import scale as _scale
    try:
        _scale.set_user_scale(frame, nm_per_px)
    except ValueError as e:
        raise HTTPException(400, str(e))
    out = remeasure(arm=arm, frame=frame)
    out["nm_per_px"] = nm_per_px
    out["scale_source"] = _scale.scale_source(frame, "txm" if arm == "txm" else "sem")
    return out


@app.post("/api/remeasure")
def remeasure(arm: str = Query(...), frame: str = Query(...)):
    """Re-measure a single frame from its current mask, and update only that frame."""
    import sys as _sys
    import time as _t
    _sys.path.insert(0, os.path.join(RES, "analysis"))

    path = _mask_path(arm, frame)
    if not path:
        raise HTTPException(400, f"no mask location known for arm {arm!r}")
    if not os.path.exists(path):
        raise HTTPException(404, f"no mask on disk at {path}")

    modality = "txm" if arm == "txm" else "sem"
    from measure import measure_path
    try:
        rows, summ = measure_path(path, modality, stem=frame)
    except Exception as e:
        raise HTTPException(500, f"measurement failed: {type(e).__name__}: {e}")

    prior = next((f for f in (_load_quiet("frames") or [])
                  if f.get("arm") == arm and f.get("frame") == frame), None)
    summ["arm"] = arm
    summ["specimen"] = (prior or {}).get("specimen") or "unparsed"
    for r in rows:
        r["frame"] = summ["frame"]
        r["arm"] = arm
        r["specimen"] = summ["specimen"]

    # Replace exactly this frame's records. Everything else is left byte-for-byte alone:
    # a re-measure of one frame must never be able to disturb another.
    for fname, new_rows in (("frames", [summ]), ("cracks", rows)):
        fp = os.path.join(OUT, f"{fname}.json")
        cur = json.load(open(fp)) if os.path.exists(fp) else []
        kept = [x for x in cur
                if not (x.get("arm") == arm and x.get("frame") == summ["frame"])]
        with open(fp, "w") as fh:
            json.dump(kept + new_rows, fh)
    _CACHE.clear()
    _rebuild_specimen(arm, summ["specimen"])
    _CACHE.clear()

    # What actually moved, so the answer to "did my correction do anything" is on screen
    # rather than something to go and look for.
    changed = {}
    for k in ("area_fraction", "n_cracks_measured", "largest_share_of_area",
              "mcl_um", "total_skeleton_length_px"):
        before, after = (prior or {}).get(k), summ.get(k)
        if before != after:
            changed[k] = {"before": before, "after": after}
    return {"ok": True, "arm": arm, "frame": summ["frame"],
            "mask_path": path,
            "mask_modified": _t.strftime("%Y-%m-%d %H:%M:%S",
                                         _t.localtime(os.path.getmtime(path))),
            "seconds_since_mask_written": round(_t.time() - os.path.getmtime(path)),
            "changed": changed,
            "unchanged": not changed}


def _rebuild_specimen(arm, specimen):
    """Recompute one specimen-arm record after one of its frames changed."""
    import sys as _sys
    _sys.path.insert(0, os.path.join(RES, "analysis"))
    try:
        import specimen_stats
    except ImportError:
        return
    fp, sp = os.path.join(OUT, "frames.json"), os.path.join(OUT, "specimens.json")
    if not os.path.exists(fp):
        return
    frames = json.load(open(fp))
    fs = [f for f in frames if f.get("arm") == arm and f.get("specimen") == specimen]
    if not fs:
        return
    rec = specimen_stats.summarise(arm, specimen, fs)
    by_arm = {}
    for f in frames:
        by_arm.setdefault(f["arm"], []).append(f)
    rec["arm_sensitivity"] = (specimen_stats.paired_arm_ratio(by_arm, specimen)
                              if arm.startswith("sem/") else None)
    others = []
    if os.path.exists(sp):
        try:
            others = [r for r in json.load(open(sp))
                      if not (r.get("arm") == arm and r.get("specimen") == specimen)]
        except Exception:
            others = []
    with open(sp, "w") as fh:
        json.dump(others + [rec], fh)


@app.get("/api/readout")
def readout(arm: str = Query(...), specimen: str | None = None, frame: str | None = None):
    """The sentences, not the numbers. Computed server-side from the SAME dataset the tables
    read, so a statement can never disagree with the figure beside it."""
    import sys as _sys
    _sys.path.insert(0, os.path.join(RES, "analysis"))
    import conclusions

    frames = [f for f in _load("frames") if f.get("arm") == arm]
    out = {"arm": arm, "frame": [], "specimen": [], "refusals": conclusions.REFUSALS}

    if frame:
        f = next((x for x in frames if x["frame"] == frame), None)
        if f is None:
            raise HTTPException(404, f"no frame {frame!r} in arm {arm!r}")
        out["frame"] = conclusions.for_frame(f)
        specimen = specimen or f.get("specimen")

    if specimen:
        rec = next((r for r in _load("specimens")
                    if r.get("arm") == arm and r.get("specimen") == specimen), None)
        if rec is not None:
            out["specimen"] = conclusions.for_specimen(
                rec, [x for x in frames if x.get("specimen") == specimen])
            out["specimen_name"] = specimen
    return out


@app.get("/api/figure/fields")
def figure_fields():
    """What can go on an axis, and which choices need a physical scale."""
    from . import figures as F
    return {"fields": [{"key": k, "label": v[0], "unit": v[1], "needs_scale": k in F.NEEDS_SCALE}
                       for k, v in F.FIELDS.items()],
            "kinds": list(F.KINDS)}


@app.get("/api/figure.svg")
def figure_svg(arm: str = Query(...), kind: str = Query("box_by_specimen"),
               x: str | None = None, y: str | None = None,
               min_frames: int = 3, include_thin: bool = False,
               download: bool = False):
    """Render a figure the user chose. SVG, so what is shown and what downloads are the
    same bytes -- and so a figure in a paper stays editable and resolution-independent."""
    from . import figures as F
    try:
        out = F.build(_load("frames"), arm, kind, x, y, min_frames, include_thin)
    except ValueError as e:
        raise HTTPException(400, str(e))
    headers = {}
    if download:
        name = f"{arm.replace('/', '_')}_{kind}_{y or x or 'figure'}.svg"
        headers["Content-Disposition"] = f'attachment; filename="{name}"'
    return Response(out["svg"], media_type="image/svg+xml", headers=headers)


# ---------------------------------------------------------------------------------------
# Setup. A checkout finds the sibling repos through relative symlinks; a downloaded app has
# no siblings, so the one thing it cannot discover is where the SEM repo is. That is the
# whole of the configuration, and the app states plainly what it can and cannot do without
# it rather than failing at the moment of use.
@app.get("/api/health")
def health():
    """What this install can do right now, and what is missing to do the rest."""
    import sys as _sys
    _sys.path.insert(0, os.path.join(RES, "analysis"))
    try:
        from shared_impl import provenance
        impl = provenance()
    except Exception as e:
        impl = {"source": None, "error": f"{type(e).__name__}: {e}"}

    sem = P.sem_repo()
    ok, findings = P.check_sem_repo(sem) if sem else (False, [])
    # WHICH arms are measured, not merely whether any file exists. One uploaded mask
    # creates frames.json, and treating that as "the dataset is built" hid the button for
    # measuring the reference corpus from anyone who added a file before configuring the
    # repo -- so the corpus could never be measured from the UI at all.
    arms_measured = []
    try:
        arms_measured = sorted({r.get("arm") for r in _load("frames")} - {None})
    except HTTPException:
        pass
    has_data = bool(arms_measured)
    return {
        "frozen": P.FROZEN,
        "data_dir": P.DATA,
        "dataset_built": has_data,
        "arms_measured": arms_measured,
        "corpus_measured": any(a.startswith("sem/") or a == "txm" for a in arms_measured),
        "sem_repo": sem,
        "sem_repo_ok": ok,
        "sem_findings": [{"level": a, "what": b} for a, b in findings],
        "can_segment": bool(P.sem_python()),
        "txm_export": P.txm_export(),
        "measurement_impl": impl,
        # The two capabilities a user actually cares about, stated as capabilities.
        "capabilities": {
            "measure_uploaded_mask": True,
            "segment_raw_micrograph": bool(P.sem_python()),
            "reference_corpus": bool(P.sem_derived() and
                                     os.path.isdir(os.path.join(P.sem_derived(),
                                                                "gated_masks"))),
        },
    }


@app.post("/api/config")
def set_config(sem_repo: str | None = None, txm_export: str | None = None):
    """Point the app at the repos. Validated before it is saved, so a wrong folder is
    rejected here with the reason instead of accepted and failing later."""
    if sem_repo is not None:
        sem_repo = os.path.expanduser(sem_repo.strip())
        ok, findings = P.check_sem_repo(sem_repo)
        if not ok:
            miss = ", ".join(w for lv, w in findings if lv == "missing")
            raise HTTPException(400, f"that folder is not a sem-crack-detector checkout "
                                     f"-- missing: {miss}")
    if txm_export is not None:
        txm_export = os.path.expanduser(txm_export.strip())
        if not os.path.isdir(txm_export):
            raise HTTPException(400, "that folder does not exist")
    P.set_config(sem_repo=sem_repo, txm_export=txm_export)
    _CACHE.clear()
    # Which measurement implementation answers depends on this setting, and it is resolved
    # once and cached. Without this, configuring a repo leaves the process measuring with
    # the bundled copy until it is restarted.
    import sys as _sys
    _sys.path.insert(0, os.path.join(RES, "analysis"))
    try:
        import shared_impl
        shared_impl.reset()
    except Exception:
        pass
    return health()


# ---------------------------------------------------------------------------------------
# Measuring the reference corpus. This is the long job, so it runs on a thread and the page
# polls; a request that blocks for twenty minutes is a request that times out.
_JOB = {"state": "idle", "log": [], "started": None}


@app.post("/api/measure_corpus")
def measure_corpus(arm: str = "all"):
    import threading
    if _JOB["state"] == "running":
        raise HTTPException(409, "a measurement is already running")
    if not P.sem_derived():
        raise HTTPException(503, "no SEM repo is configured, so there is no corpus to "
                                 "measure. Set one in Setup, or just upload masks.")

    def run():
        import io
        import contextlib
        _JOB.update(state="running", log=[], started=time.time())
        buf = io.StringIO()
        try:
            import sys as _sys
            _sys.path.insert(0, os.path.join(RES, "analysis"))
            import importlib
            batch = importlib.import_module("batch")
            importlib.reload(batch)
            argv = _sys.argv
            _sys.argv = ["batch.py", "--arm", arm]
            try:
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    batch.main()
            finally:
                _sys.argv = argv
            _JOB["state"] = "done"
        except Exception as e:
            buf.write(f"\nFAILED {type(e).__name__}: {e}\n")
            _JOB["state"] = "failed"
        finally:
            _JOB["log"] = buf.getvalue().splitlines()[-200:]
            _CACHE.clear()

    threading.Thread(target=run, daemon=True).start()
    return {"state": "running"}


@app.get("/api/measure_corpus")
def measure_corpus_status():
    el = (time.time() - _JOB["started"]) if _JOB["started"] else 0
    return {"state": _JOB["state"], "elapsed_s": round(el, 1), "log": _JOB["log"][-40:]}


@app.get("/")
def index():
    """Serve the page with a cache-busting token on its script.

    Without this the browser keeps a cached app.js across edits: the page reloads, the HTML
    is fresh, and the JavaScript is whatever it fetched the first time. Caught on 2026-09-26
    when the orientation caption updated to "Length-weighted" while the chart's aria-label
    still said "Area-weighted" -- two strings set by the same file, disagreeing, because one
    lived in the HTML and the other in a stale script. Hard-reloading the page did not fix
    it; only the query token does. The token is the file's mtime, so it changes exactly when
    the file does and never otherwise.
    """
    p = os.path.join(RES, "app", "templates", "index.html")
    if not os.path.exists(p):
        return HTMLResponse("<h1>index.html missing</h1>", status_code=500)
    html = open(p).read()
    js = os.path.join(RES, "app", "static", "app.js")
    if os.path.exists(js):
        html = html.replace('src="/static/app.js"',
                            f'src="/static/app.js?v={int(os.path.getmtime(js))}"')
    return HTMLResponse(html)


# Mounted last so it cannot shadow /api/*.
app.mount("/static", StaticFiles(directory=os.path.join(RES, "app", "static")), name="static")
