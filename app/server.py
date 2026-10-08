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
import io
import os
import re
import threading
import time

from fastapi import Body, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from . import mark_proxy
from . import paths as P

_HERE = os.path.dirname(os.path.abspath(__file__))
RES = P.RES
#: Warn that an uploaded mask looks inverted above this area fraction. Above the 0.414
#: maximum of the 357-frame reference corpus, and below the 0.5 at which 'crack'
#: becomes the majority phase.
POLARITY_WARN_ABOVE = 0.5

OUT = P.OUT

#: Smallest crop worth measuring. Under this the morphology features are noise:
#: extract_candidates already drops anything under 40 px of area.
MIN_CROP_PX = 64

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


#: Held across every read-modify-write of the dataset files. They are rewritten in place
#: by upload, remeasure, mask_edit and set_scale, and remeasure is a sync def -- so FastAPI
#: runs it in the threadpool and several execute at once. Six concurrent re-measures of six
#: DIFFERENT frames returned five HTTP 500s: one thread read frames.json while another was
#: streaming it out, and json.load hit the truncation mid-object. Two app windows, or the
#: desktop app plus a browser, or the Mark tab's save overlapping the Analysis tab's
#: re-measure (different buttons, each disabling only itself) all reach it. _load() already
#: had a try/except serving the last good copy for exactly this hazard -- the writers' own
#: reads had no such protection. Reentrant because remeasure calls _rebuild_specimen.
_DATASET_LOCK = threading.RLock()


def _write_json(path, obj):
    """Write a dataset file so no reader can ever see a partial one.

    tmp + os.replace, because os.replace is atomic within a filesystem: a reader gets the
    whole old file or the whole new one, never the middle. Truncate-and-rewrite gives them
    the middle. scale.py already used this for user_scale.json and server.py for the mask
    PNG; the three files that ARE the app's product were the ones still doing it unsafely.

    allow_nan=False because Python's json writes bare Infinity and NaN, which are not JSON
    (RFC 8259) and which strict readers reject -- JSON.parse, R's jsonlite. One nm/px of
    inf put 12 Infinity literals into frames.json and left three endpoints returning 500
    across restarts with no route back through the UI. Refusing at the write keeps a
    non-finite value out of the product rather than persisting it.
    """
    tmp = f"{path}.tmp"
    with open(tmp, "w") as fh:
        json.dump(obj, fh, allow_nan=False)
    os.replace(tmp, path)


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
    # WHETHER A MICROGRAPH EXISTS BEHIND THIS ARM'S MASKS, so the client does not have to
    # know. The editor draws the crack in red over the original where there is one; asking
    # for one that cannot exist -- every uploaded mask -- produced a 404 per frame and a
    # console error per 404, which is the noise a real error hides behind. The server
    # already decides this in original(); reporting it keeps one source of that truth
    # instead of a second copy of the rule in JavaScript.
    # YOUR IMAGES IS A PLACE, NOT A CONSEQUENCE.
    #
    # This list was built purely from frames.json, so an arm with no frames did not exist
    # and the client dropped it from the dropdown. For sem/* and txm that is right -- they
    # describe corpora this app did not make and cannot offer when they are absent. For
    # uploads it is backwards: it is the one arm the app owns, the destination of the Add
    # image button, and the only arm a user can put anything into. Hiding it until
    # something is in it means the entry appears when the SYSTEM creates something there
    # and disappears when the user deletes their last image -- the exact inversion the
    # user objected to. It is now always offered, at zero frames if that is the truth, so
    # going there is a choice rather than a notification.
    out.setdefault("uploads", {"arm": "uploads", "n_frames": 0, "n_scaled": 0,
                               "n_cracks": 0, "specimens": set()})
    out["uploads"]["collections"] = collections_get()["collections"]
    have_sem = bool(P.sem_repo())
    have_txm = bool(P.txm_images())
    for a in out.values():
        a["n_specimens"] = len(a.pop("specimens"))
        a["has_originals"] = (a["arm"].startswith("sem/") and have_sem) or \
                             (a["arm"].startswith("txm") and have_txm)
    return sorted(out.values(), key=lambda a: a["arm"])


@app.get("/api/frames")
def frames(arm: str = Query(...), specimen: str | None = None,
           collection: str | None = None):
    fr = [f for f in _load("frames") if f["arm"] == arm]
    if specimen:
        fr = [f for f in fr if f["specimen"] == specimen]
    if collection:
        # An empty collection answers [] rather than 404 for the same reason an empty
        # uploads arm does: you have to be able to go to the place before you fill it.
        return sorted([f for f in fr if f.get("collection") == collection],
                      key=lambda f: f["frame"])
    # EMPTY IS AN ANSWER FOR THE ARM THIS APP OWNS. /api/arms now always offers uploads so
    # that going there is the user's choice rather than a side effect of something being
    # created, and a 404 on the way in would turn that choice into "Could not load the
    # uploads arm" -- a worse dead end than the hidden option it replaced. Every other arm
    # still 404s: asking for sem/gated on a machine with no SEM checkout is a real error
    # and must not render as an empty list.
    if not fr and not (arm == "uploads" and not specimen):
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


def _mask_path(arm: str, frame: str) -> str:
    """Where this arm keeps its mask PNGs. Shared by /api/mask and /api/crop so a crop can
    be taken from any arm the viewer can display, rather than from the SEM arms alone."""
    derived = P.sem_derived()
    src = {"sem/gated": (derived and os.path.join(derived, "gated_masks"), "_gated.png"),
           "sem/machine": (derived and os.path.join(derived, "machine_masks"), "_machine.png"),
           "uploads": (P.UPLOADS, "_gated.png")}
    if arm in src:
        root, suf = src[arm]
        if not root:
            raise HTTPException(503, "no SEM repo is configured, so its masks cannot be "
                                     "shown. Set one in Setup.")
        return os.path.join(root, frame + suf)
    if arm.startswith("txm"):
        # Both TXM arms share one layout across two trees: the gated archive and the
        # model-only one. Resolved per arm rather than by a single txm_export() call, which
        # is what made "txm" the only TXM arm whose mask could be fetched.
        tx = P.txm_export_machine() if arm == "txm/machine" else P.txm_export()
        if not tx:
            raise HTTPException(503, f"no mask tree is configured for {arm}, so its masks "
                                     "cannot be shown. Set one in Setup.")
        return os.path.join(tx, frame, f"{frame}_crack_mask.png")
    raise HTTPException(400, f"unknown arm {arm!r}")


@app.get("/api/mask/{arm:path}/{frame}")
def mask(arm: str, frame: str):
    """The mask PNG itself, so the page can show what a number was measured on.

    AN EDIT STANDS IN FOR IT. Correcting a research frame stores the result in the app's
    own folder and serves it here, so re-opening that frame shows the correction rather
    than the detector's original -- including after the app has been closed. The research
    mask on disk is never written to; see _edit_path.
    """
    e = _edit_of(arm, frame)
    if e:
        return FileResponse(e, media_type="image/png")
    p = _mask_path(arm, frame)
    if not os.path.exists(p):
        raise HTTPException(404, f"no mask on disk for {frame!r} in {arm!r}")
    return FileResponse(p, media_type="image/png")


#: Display cap for an original. The TXM mosaics are 5039x3703 float32 (48 MB each) and the
#: SEM originals 6144x4376; sending either at full size to draw behind a mask is megabytes
#: of transfer for pixels no canvas will show.
ORIGINAL_MAX_W = 2400

#: Blur radius subtracted to remove tile-to-tile illumination. See original() below.
def _app_version():
    """What build this is, so "which version are you running" is answerable from the UI.

    A round of this project was spent on a screenshot whose toolbar did not match any
    version in the repository, because there was no way to tell from the window which
    build it was. The packaged app carries it in Info.plist; a checkout has no plist, so
    it reads the spec's fallback and says it is a dev run.
    """
    import re as _re
    plist = os.path.join(RES, "..", "Info.plist")
    try:
        with open(plist, encoding="utf-8") as fh:
            m = _re.search(r"<key>CFBundleShortVersionString</key>\s*<string>([^<]+)", fh.read())
        if m:
            return m.group(1)
    except OSError:
        pass
    spec = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "packaging", "fractography.spec")
    try:
        with open(spec, encoding="utf-8") as fh:
            m = _re.search(r'FALLBACK_VERSION\s*=\s*"([^"]+)"', fh.read())
        if m:
            return f"{m.group(1)} (dev)"
    except OSError:
        pass
    return "unknown"


HIGHPASS_SIGMA = 60

#: Rendered micrographs, newest last. Small because each entry is a ~2 MB PNG.
_ORIGINAL_CACHE = {}
ORIGINAL_CACHE_N = 8

#: ...and on disk, because the expensive part is reading the source at all. With the page
#: cache warm the whole render is 0.5 s; cold it is about 3 s, and almost all of that is
#: pulling a 48 MB TIFF off the disk for the first time. An in-memory cache only helps
#: within one run, so the first visit to each frame paid it again after every restart.
#: Keyed on the source's mtime and size, like the memory cache, so a replaced micrograph
#: can never be served from a stale render.
ORIGINAL_DISK_CACHE_MB = 600


def _original_cache_dir():
    d = os.path.join(OUT, "render_cache")
    os.makedirs(d, exist_ok=True)
    return d


def _disk_cache_path(key):
    import hashlib
    h = hashlib.sha1(repr(key).encode()).hexdigest()[:24]
    return os.path.join(_original_cache_dir(), f"{h}.png")


def _disk_cache_trim():
    """Oldest-first, by access time, to a byte budget."""
    try:
        d = _original_cache_dir()
        files = []
        for f in os.listdir(d):
            fp = os.path.join(d, f)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            files.append((st.st_atime, st.st_size, fp))
        total = sum(f[1] for f in files)
        files.sort()
        while total > ORIGINAL_DISK_CACHE_MB * 1024 * 1024 and files:
            _, size, fp = files.pop(0)
            try:
                os.remove(fp)
                total -= size
            except OSError:
                break
    except Exception:                                   # noqa: BLE001 - a cache miss is fine
        pass


def _match_original_to_mask(oim, mask_wh):
    """Trim the instrument databar so the micrograph covers the same field as the mask.

    SEM .tif originals here carry the databar as a band BELOW the image -- 6144x4376
    against a 6144x4096 mask, 280 rows. The mask has it removed; the original does not.
    Both are then stretched into the same canvas, so the micrograph was squashed by
    4096/4376 and every mask pixel sat up to 280 source rows away from the feature it was
    meant to be marking, worst at the bottom of the frame -- where the databar itself was
    also being painted over. Verified on 260622_316_H_b2_back_CBS_01: the row-mean profile
    steps hard at row 4095/4096 and the served render's own profile steps at row 1600 of
    1709, which is 4096 x the serving scale exactly.

    Only ever TRIMS, and only from the bottom, and only when the widths already agree. A
    mismatch of any other shape is left alone and reported by the caller, because
    rescaling to fit would put a correct mask over the wrong picture with nothing to say so.
    """
    W, H = mask_wh
    ow, oh = oim.size
    if (ow, oh) == (W, H):
        return oim, None
    if ow == W and oh > H:
        return oim.crop((0, 0, W, H)), f"trimmed {oh - H} rows of databar"
    return oim, (f"the micrograph is {ow}x{oh} but the mask is {W}x{H}, so the same box is "
                 f"not the same region of the specimen")


def _mask_size(arm: str, frame: str):
    """The mask's pixel dimensions, or None. Header-only read; it does not decode."""
    try:
        mp = _mask_path(arm, frame)
    except HTTPException:
        return None
    if not mp or not os.path.exists(mp):
        return None
    try:
        from PIL import Image as _I
        _I.MAX_IMAGE_PIXELS = None
        with _I.open(mp) as m:
            return m.size
    except Exception:                                   # noqa: BLE001
        return None


def _original_path(arm: str, frame: str, _depth: int = 0):
    """Where the micrograph behind `frame` lives, or None. Shared by the viewer and the crop.

    Factored out because the crop has to cut the SAME file the viewer draws, and a second
    copy of this lookup is how the two would drift apart.
    """
    if arm.startswith("txm"):
        d = P.txm_images()
        if not d:
            return None
        for ext in (".tif", ".tiff", ".png"):
            cand = os.path.join(d, frame + ext)
            if os.path.exists(cand):
                return cand
        return None
    if arm.startswith("sem/"):
        sem = P.sem_repo()
        if not sem:
            return None
        for ext in (".tif", ".tiff", ".png"):
            cand = os.path.join(sem, "original", frame + ext)
            if os.path.exists(cand):
                return cand
        return None
    if arm == "uploads":
        # A CROP CARRIES ITS PARENT'S MICROGRAPH, CUT TO THE SAME BOX. Without this the
        # uploads arm 404s and the crop is painted on a bare black-and-white mask -- you
        # cannot judge a boundary against the thing whose boundary it is meant to be.
        cand = os.path.join(UPLOAD_DIR, f"{frame}_original.png")
        if os.path.exists(cand):
            return cand
        # AND SO DOES A MARKED COPY, which is the ordinary case: the first stroke on a
        # research frame saves a copy here rather than touching the research mask, and
        # that copy is the same field at the same size. Without this the moment you drew
        # on a SEM frame the picture underneath vanished and you were left painting on a
        # bare mask -- which is precisely when you most need to see what is under the
        # brush. Resolved through the record's own copied_from rather than by taking the
        # name apart, and depth-limited because a copy of a copy is reachable.
        rec = next((f for f in (_load_quiet("frames") or [])
                    if f.get("arm") == "uploads" and f.get("frame") == frame), None)
        src = (rec or {}).get("copied_from")
        if isinstance(src, str) and "/" in src and _depth < 4:
            parm, pframe = src.rsplit("/", 1)
            if parm != "uploads" or pframe != frame:
                return _original_path(parm, pframe, _depth + 1)
        return None
    return None


@app.get("/api/original/{arm:path}/{frame}")
def original(arm: str, frame: str):
    """The GREYSCALE MICROGRAPH a mask was made from, as an 8-bit PNG.

    WHY THIS EXISTS. The Mark tab drew the TXM arm as its bare mask -- black specks on
    white -- while the SEM arm showed the crack in red over the actual micrograph, because
    the SEM path hands off to a tool that owns the originals and the TXM path had nothing
    to hand off to. A user pointed at the difference. A binary mask is the measurement's
    INPUT; it is not a picture of the specimen, and you cannot judge a correction against
    it because there is nothing underneath to compare the boundary to.

    I had concluded no TXM original existed, having looked in the export tree and found
    only `<frame>_crack_mask.png`. They were in the pipeline repo's own images/ directory
    all along: 71 .tif files, names matching the 71 exported frames, pixel dimensions
    matching the masks exactly.

    THE DISPLAY TRANSFORM IS A HIGH-PASS, AND IT WAS CHOSEN BY MEASURING, NOT BY EYE.
    A TXM mosaic's dominant variation is tile-to-tile illumination -- a visible 6x5 grid
    of bright squares -- which is instrument, not specimen. Four candidates were scored on
    the same frame by how far the crack pixels separate from the matrix, in units of the
    matrix's own standard deviation, using the crack mask as the reference:

        percentile 1-99             +0.15 sd     (the grid dominates; cracks invisible)
        CLAHE                       +0.23 sd     (amplifies the tile seams; worse to look at)
        divide by blur, sigma 80    +0.57 sd     (seams gone, but noise blows up off-specimen)
        subtract blur, sigma 60     +2.05 sd     <- this one

    Subtracting a heavily blurred copy removes exactly the low-frequency illumination and
    leaves the crack, which is a fine dark feature. 13.7x the separation of the obvious
    choice, and unlike the division it cannot blow up where the signal approaches zero
    outside the specimen.

    IT IS A DISPLAY TRANSFORM AND NOTHING MEASURED COMES FROM THIS ENDPOINT. Saying so
    matters here specifically: this project has previously mistaken a flat-fielded render
    for evidence about what was underneath it, calling a region featureless matrix when
    91.3% of it lay inside the human's own painted crack. This image exists to be looked
    at behind a red overlay, and the overlay -- not the greyscale -- is what states where
    the crack is.
    """
    import numpy as np
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None

    # A RENDER IS WORTH KEEPING. Nothing about it depends on anything but the file on
    # disk, and the editor re-requests it on every return to the Mark tab -- so a second
    # visit paid the full cost again. Keyed on the path's mtime and size so an edited or
    # replaced micrograph is never served from a stale entry.
    src = _original_path(arm, frame)
    ckey = None
    if src and os.path.exists(src):
        st = os.stat(src)
        ckey = (arm, frame, st.st_mtime_ns, st.st_size)
        hit = _ORIGINAL_CACHE.get(ckey)
        if hit is None:
            dp = _disk_cache_path(ckey)
            if os.path.exists(dp):
                try:
                    with open(dp, "rb") as fh:
                        hit = fh.read()
                    _ORIGINAL_CACHE[ckey] = hit
                except OSError:
                    hit = None
        if hit is not None:
            return Response(hit, media_type="image/png",
                            headers={"Cache-Control": "public, max-age=3600"})


    # BOTH TXM arms draw on the same micrographs. The masks differ; the specimen does not.
    if arm.startswith("txm") and not P.txm_images():
        raise HTTPException(503, "no TXM image directory is configured, so the "
                                 "original cannot be shown. Set one in Setup.")
    if arm.startswith("sem/") and not P.sem_repo():
        raise HTTPException(503, "no SEM repo is configured.")
    path = _original_path(arm, frame)
    if not path:
        # An uploaded mask that is not a crop has no micrograph behind it -- 404 rather
        # than 400, because the caller's question has a clean answer.
        raise HTTPException(404, f"no original on disk for {frame!r} in {arm!r}")

    from scipy import ndimage as ndi
    im = Image.open(path)
    ms = _mask_size(arm, frame)
    if ms:
        im, why = _match_original_to_mask(im, ms)
        # A REFUSAL MUST NOT BE DISCARDED. _match_original_to_mask returns the image
        # UNCHANGED when it cannot align it, and the second value is how it says so.
        # Throwing that away served the full micrograph for a mask that covers only part
        # of it -- five SEM frames here are FOV-cropped rather than databar-trimmed
        # (MAR_Amb_AS_CBS_0001 is 6144x4376 against a 2952x2952 mask), and the editor
        # stretches whatever it gets into the mask's own aspect. The crack overlay then
        # sat hundreds of pixels from the feature it marked, which invites a correction
        # that is itself wrong. A 409 makes the editor fall back to the bare mask, which
        # is honest: no picture beats the wrong picture.
        if why and im.size != ms:
            raise HTTPException(409, why)
    # REDUCE FIRST, THEN HIGH-PASS. The answer is ORIGINAL_MAX_W wide whatever happens,
    # and a sigma-60 gaussian over a 6144x4096 float32 array costs 4.2 s -- which is the
    # whole reason opening a SEM frame took 28 seconds. Downsampling first and scaling
    # sigma by the same factor is 13.6x faster and gives the same picture, because the
    # low frequencies this subtracts are exactly the ones a downsample preserves.
    #
    # CHECKED AGAINST THE MEASUREMENT THAT CHOSE THIS TRANSFORM, not by eye. The docstring
    # above picked subtract-blur over three alternatives by how far crack pixels separate
    # from the matrix in units of the matrix's own standard deviation. On
    # MAR_H_HIP_CBS_0002 that separation is +2.105 sd before and +2.105 sd after;
    # correlation between the two renders is 0.99977 and the mean absolute difference is
    # 0.24 of 255.
    k = 1.0
    if im.width > ORIGINAL_MAX_W:
        k = ORIGINAL_MAX_W / im.width
        im = im.resize((ORIGINAL_MAX_W, max(1, round(im.height * k))), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float32)
    if a.ndim == 3:
        a = a.mean(axis=2)
    a = a - ndi.gaussian_filter(a, HIGHPASS_SIGMA * k)
    lo, hi = np.percentile(a, 0.5), np.percentile(a, 99.5)
    if hi <= lo:
        lo, hi = float(a.min()), float(a.max() or 1)
    a = np.clip((a - lo) / (hi - lo), 0, 1) * 255
    out = Image.fromarray(a.astype("uint8"), mode="L")
    buf = io.BytesIO()
    # optimize=True buys ~2% here and costs a pass over every pixel; this endpoint is on
    # the path between clicking a frame and seeing it.
    out.save(buf, "PNG", compress_level=6)
    blob = buf.getvalue()
    if ckey is not None:
        _ORIGINAL_CACHE[ckey] = blob
        while len(_ORIGINAL_CACHE) > ORIGINAL_CACHE_N:
            _ORIGINAL_CACHE.pop(next(iter(_ORIGINAL_CACHE)))
        try:
            dp = _disk_cache_path(ckey)
            tmp = dp + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(blob)
            os.replace(tmp, dp)
            _disk_cache_trim()
        except OSError:
            pass
    return Response(blob, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


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
async def upload(file: UploadFile = File(...), nm_per_px: float | None = None,
                 collection: str | None = None):
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
    if collection:
        if not SAFE_COLLECTION.match(collection.strip()):
            raise HTTPException(400, f"{collection!r} is not a usable collection name")
        summ["collection"] = collection.strip()
        # REGISTER IT. Uploading into a name that is not on the list yet would file the
        # frame somewhere the dropdown cannot offer, which is a frame you cannot reach.
        with _DATASET_LOCK:
            if summ["collection"] not in _read_collections():
                _write_json(_collections_path(), _read_collections() + [summ["collection"]])
    # The filename as given, so a later upload can tell "the same file again" from "a
    # different file with a colliding name".
    summ["source_filename"] = name
    summ["was_segmented_here"] = detected
    for r in rows:
        r["frame"] = stem
        r["arm"] = "uploads"
        r["specimen"] = "uploaded"

    # Append to the served dataset and drop the cache so the page sees it immediately.
    with _DATASET_LOCK:
        for fname, new in (("frames", [summ]), ("cracks", rows)):
            p = os.path.join(OUT, f"{fname}.json")
            cur = json.load(open(p)) if os.path.exists(p) else []
            cur = [x for x in cur
                   if not (x.get("arm") == "uploads" and x.get("frame") == stem)]
            cur.extend(new)
            _write_json(p, cur)

    # And rebuild the uploads specimen record. Without this an upload adds a frame and no
    # specimen, so the specimen card -- the FIRST card on the page -- simply disappeared
    # for the uploads arm, which is the only arm a downloaded copy has. batch.py maintains
    # this table for every other arm; the upload path was writing two of the three files.
    _rebuild_uploads_specimen()
    _CACHE.clear()

    # POLARITY. This app's convention is CRACK = BLACK, because that is how a crack looks
    # in a micrograph and how every mask in the corpus is stored. A mask saved the other way
    # round is the single most likely mistake a new user makes with a black-and-white image,
    # and without this check the app answers it confidently and exactly backwards: a test
    # mask with 1.46% of its pixels marked, inverted, measured as 98.54% of the frame in ONE
    # crack of mean width 102 px, with no warning and an "ok": true. The two readings summed
    # to 1.000000, which is the signature.
    #
    # The threshold is not a guess. Over the 357 measured frames in the reference corpus the
    # area fraction runs from near zero to 0.414 with a median of 0.028, so nothing real
    # comes close to half a frame; and above 0.5 the "crack" is the majority phase and the
    # background is the minority one, which inverts the meaning of every number returned.
    # This warns and still returns the measurement -- it is not the app's place to refuse a
    # mask a user insists on -- but it refuses to stay silent.
    polarity_warning = None
    if not detected and summ["area_fraction"] > POLARITY_WARN_ABOVE:
        polarity_warning = (
            f"{summ['area_fraction'] * 100:.1f}% of this image measured as crack. This app "
            f"reads CRACK = BLACK on a white background. The highest area fraction anywhere "
            f"in the reference corpus is 41.4% over 357 frames, so a value this high almost "
            f"always means the mask is inverted. Invert it and upload again, and every "
            f"number here will change.")

    return {"ok": True, "frame": summ["frame"], "arm": "uploads",
            "renamed_from": (raw_stem if raw_stem != summ["frame"] else None),
            "segmented_here": detected,
            "scale_known": summ["scale_known"],
            "n_cracks": summ["n_cracks_measured"], "n_specks": summ["speck_count"],
            "area_fraction": summ["area_fraction"],
            "scale_note": scale_note,
            "polarity_warning": polarity_warning,
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
    _write_json(sp, others + recs)


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


def _paint_port_candidates():
    """Ports to try, override first.

    MARK_PORT exists so a development instance can be pointed at a sandbox copy of the
    paint layer. It is FIRST, not a fallback: if it is set and something is listening there,
    that is the tool this app talks to. Silently preferring the default would mean a dev run
    proxying to the researcher's real tool -- writes into hand-labelled data -- while
    reporting the sandbox port back to the UI.
    """
    return [p for p in (mark_proxy.port_override(), _PAINT.get("port"), PAINT_PORT) if p]


def _paint_alive():
    """Whether the marking tool is reachable, NOT whether this process started it.

    It was the latter, so restarting this server reported a perfectly healthy tool as
    stopped and offered to start a second one -- the subprocess handle lives in memory and
    the tool does not. Same shape as the dataset cache keyed on a name: state held here
    that should be read from the world.
    """
    for port in _paint_port_candidates():
        if _listening(port):
            _PAINT["port"] = port
            return True
    # ONLY NOW the subprocess handle, and only as a "starting up" signal. It used to be
    # checked first, which reported a tool this process had spawned as alive for the whole
    # window between fork and first accept -- and, with MARK_PORT set, reported the wrong
    # tool as the live one.
    p = _PAINT["proc"]
    return bool(p and p.poll() is None)


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
    for port in _paint_port_candidates():
        if _listening(port):
            _PAINT["port"] = port
            return {**paint_status(), "reused": True}
    port = PAINT_PORT
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
# THE MARKING TOOL, SERVED INSIDE THIS APP.
#
# Everything the tool can do -- paint, flip a region, undo a correction, reapply the model,
# retrain it, pick a model, export -- now works in this window instead of in a browser tab
# this app opened and then had no control over. See app/mark_proxy.py for why the HTML has
# to be rewritten and what is asserted about that rewrite.
#
# ASYNC, WITH THE BLOCKING CALL PUSHED TO THE THREADPOOL EXPLICITLY. urllib blocks, and a
# retrain or a reapply holds the connection for minutes; doing that on the event loop would
# freeze every other request, including the read-out the user is looking at while it runs.
@app.api_route("/mark/{path:path}", methods=["GET", "POST"])
async def mark(path: str, request: Request):
    from starlette.concurrency import run_in_threadpool
    if not _paint_alive():
        raise HTTPException(503, "the marking tool is not running -- start it from the "
                                 "Mark tab, which also reports why it cannot start")
    port = _PAINT.get("port") or mark_proxy.port_override() or PAINT_PORT
    body = await request.body() if request.method == "POST" else None
    try:
        status, headers, raw, _ = await run_in_threadpool(
            mark_proxy.forward,
            port, path, method=request.method, body=body,
            headers=dict(request.headers), query=str(request.url.query or ""))
    except ConnectionError as e:
        raise HTTPException(502, str(e))
    except ValueError as e:
        # The rewrite found nothing to rewrite. Saying so is the whole point: the page would
        # otherwise render perfectly and send every call to the wrong server.
        raise HTTPException(500, str(e))
    return Response(content=raw, status_code=status,
                    media_type=headers.get("Content-Type") or headers.get("content-type"))


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
    if arm.startswith("txm"):
        tx = P.txm_export_machine() if arm == "txm/machine" else P.txm_export()
        return os.path.join(tx, frame, f"{frame}_crack_mask.png") if tx else None
    return None


# ---------------------------------------------------------------- crop, groups, compare

@app.post("/api/crop")
def crop(payload: dict = Body(...)):
    """Cut a rectangle out of one frame and store it as a new frame you can draw on.

    WHY A NEW FRAME RATHER THAN A VIEW. The whole point of cropping here is to then paint
    on the crop and retrain, and every downstream stage -- the mark tool, the measurement,
    the retrain -- is keyed on a frame. A crop that were only a viewport would have to be
    threaded through all of them; a crop that IS a frame needs none of that and inherits
    the tools unchanged.

    WHAT IS CARRIED, AND WHAT CANNOT BE. The pixel size comes with the crop unchanged: a
    crop does not magnify, so nm/px is the parent's. The parent frame and the box are
    recorded on the new frame so the provenance is never guessed. What does NOT survive is
    censoring status -- a crack that was comfortably inside the parent can touch the edge of
    the crop, so its length becomes a lower bound that it was not before. The response says
    how many cracks that happened to, because it is the one number a user will otherwise
    read straight past.
    """
    import sys as _sys
    _sys.path.insert(0, os.path.join(RES, "analysis"))
    from measure import canonical_stem, measure_path
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None

    arm = (payload.get("arm") or "").strip()
    frame = (payload.get("frame") or "").strip()
    try:
        x, y = int(payload["x"]), int(payload["y"])
        w, h = int(payload["w"]), int(payload["h"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "crop needs integer x, y, w, h in PIXELS of the full frame")
    if w < MIN_CROP_PX or h < MIN_CROP_PX:
        raise HTTPException(400, f"a {w}x{h} crop is too small to measure; the minimum is "
                                 f"{MIN_CROP_PX} px on a side")

    src = _mask_path(arm, frame)
    if not os.path.exists(src):
        raise HTTPException(404, f"no mask on disk for {frame!r} in {arm!r}")
    im = Image.open(src)
    W, H = im.size
    # Clamp rather than refuse: a drag that ends past the edge is a normal gesture, and the
    # clamped box is reported back so the caller can see what was actually taken.
    x0, y0 = max(0, min(x, W - 1)), max(0, min(y, H - 1))
    x1, y1 = max(x0 + 1, min(x + w, W)), max(y0 + 1, min(y + h, H))
    if (x1 - x0) < MIN_CROP_PX or (y1 - y0) < MIN_CROP_PX:
        raise HTTPException(400, f"after clamping to the {W}x{H} frame the crop is "
                                 f"{x1-x0}x{y1-y0} px, under the {MIN_CROP_PX} px minimum")

    # THE PARENT'S NAME IS ALREADY CANONICAL; APPEND TO IT RATHER THAN RE-DERIVING. A TXM
    # frame name contains dots (`...img001of005.xrm.bim.bim`), and canonical_stem() used to
    # run splitext() unconditionally, so `<name>.bim.bim__crop_300_300_700x600` lost
    # ".bim__crop_300_300_700x600" as if it were a file extension: the crop came back named
    # after no box at all, and a second crop of the same frame would have overwritten it.
    # splitext is now limited to image extensions, and the composition order is fixed here
    # too, so neither change alone is load-bearing.
    custom = (payload.get("name") or "").strip()
    stem = canonical_stem(custom) if custom else f"{frame}__crop_{x0}_{y0}_{x1-x0}x{y1-y0}"
    if not stem:
        stem = f"{frame}__crop"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # `{stem}_gated.png`, NOT `{stem}.png`. The uploads arm resolves every mask through
    # _mask_path, which appends "_gated.png" -- so a crop saved under its bare stem is
    # written, measured, and listed as a frame while /api/mask, mask_edit and a second
    # crop all 404 on it. The crop would appear in the sidebar and be impossible to open,
    # which is the one thing a crop exists to let you do: paint on it.
    dst = os.path.join(UPLOAD_DIR, f"{stem}_gated.png")
    cut = im.crop((x0, y0, x1, y1))
    cut.save(dst)

    # A PRISTINE COPY, BECAUSE A DIFF NEEDS SOMETHING TO DIFF AGAINST. Painting the crop
    # overwrites <stem>_gated.png in place, so once the user has drawn there is no longer
    # any record of what the detector proposed -- and "which pixels did the human actually
    # change" is unanswerable. That question is the whole basis of sending strokes back to
    # the parent's correction mask: without it, confirming a crop would assert a verdict on
    # every pixel in the box, including the ones nobody looked at.
    #
    # `_ascut` is not in measure.MASK_SUFFIXES and nothing globs this directory (the corpus
    # batch globs only the SEM and TXM trees), so the file cannot be mistaken for a frame.
    cut.save(os.path.join(UPLOAD_DIR, f"{stem}_ascut.png"))

    # CUT THE MICROGRAPH TO THE SAME BOX. The point of a crop is to paint on it, and you
    # cannot judge a crack boundary against a bare binary mask -- there is nothing
    # underneath to compare it to. Saved UNTRANSFORMED (the display high-pass is applied
    # by the viewer, not baked in) and at the mask's own pixel grid, so the box that was
    # cut from the mask is the same box in the same coordinates.
    original_cropped, original_note = False, None
    osrc = _original_path(arm, frame)
    if not osrc:
        original_note = ("no micrograph is on file for the parent frame, so this crop is a "
                         "bare mask -- you can still paint on it, but there is nothing "
                         "underneath to judge the boundary against")
    else:
        try:
            oim = Image.open(osrc)
            oim, why = _match_original_to_mask(oim, (W, H))
            if oim.size == (W, H):
                cut = oim.crop((x0, y0, x1, y1))
                # A float TIFF cannot be written as PNG at all ("cannot write mode F"),
                # which is what every TXM original is. Scale to 16-bit rather than 8:
                # the viewer high-passes this image, and quantising to 256 levels first
                # throws away the low-contrast detail that the high-pass exists to find.
                if cut.mode in ("F", "I", "I;16", "I;16B", "I;16L"):
                    import numpy as _np
                    _a = _np.asarray(cut, dtype=_np.float64)
                    _lo, _hi = float(_a.min()), float(_a.max())
                    _a = ((_a - _lo) / (_hi - _lo) * 65535.0) if _hi > _lo else _a * 0
                    cut = Image.fromarray(_a.astype("uint16"), mode="I;16")
                cut.save(os.path.join(UPLOAD_DIR, f"{stem}_original.png"))
                original_cropped = True
            else:
                # A micrograph of a different size would make the box mean a different
                # region of the specimen than it means on the mask. Refuse rather than
                # rescale: a silently resampled original is the wrong picture behind a
                # correct mask, and nothing downstream would say so.
                original_note = f"{why}; no original was saved for this crop"
        except Exception as exc:                        # noqa: BLE001 - never fail the crop
            original_note = f"could not cut the micrograph: {exc}"

    parent = next((f for f in (_load_quiet("frames") or [])
                   if f.get("arm") == arm and f.get("frame") == frame), {}) or {}
    # THE MODALITY IS THE PARENT'S, NOT "sem". This read `measure_path(dst, "sem", ...)`
    # unconditionally, so every crop of a TXM frame was measured under SEM settings -- a
    # silent modality swap on exactly half the images the crop feature was asked for.
    modality = parent.get("modality") or ("txm" if arm.startswith("txm") else "sem")
    rows, summ = measure_path(dst, modality, stem=stem)
    summ["arm"] = "uploads"
    summ["specimen"] = parent.get("specimen") or "uploaded"
    # a crop does not change the pixel size
    if parent.get("scale_known") and parent.get("nm_per_px"):
        summ["nm_per_px"] = parent["nm_per_px"]
        summ["scale_known"] = True
    # PER-FRAME, BECAUSE "does this frame have a micrograph" is not a property of the arm.
    # /api/arms reports has_originals per ARM, and uploads is false there -- correctly, for
    # an uploaded mask, which has nothing behind it. A crop DOES, and the editor was
    # therefore refusing to load a background it could have fetched: the crop opened as a
    # bare binary mask, which is the one thing cropping exists to avoid.
    summ["has_original"] = original_cropped
    summ["cropped_from"] = {"arm": arm, "frame": frame,
                            "box_px": [x0, y0, x1 - x0, y1 - y0],
                            "parent_size_px": [W, H],
                            "modality": modality,
                            "original_cropped": original_cropped,
                            "original_note": original_note}
    for r in rows:
        r["arm"] = "uploads"; r["frame"] = stem; r["specimen"] = summ["specimen"]

    with _DATASET_LOCK:
        for fname, new in (("frames", [summ]), ("cracks", rows)):
            fp = os.path.join(OUT, f"{fname}.json")
            cur = json.load(open(fp)) if os.path.exists(fp) else []
            cur = [q for q in cur
                   if not (q.get("arm") == "uploads" and q.get("frame") == stem)]
            cur.extend(new)
            _write_json(fp, cur)
    _rebuild_uploads_specimen()
    _CACHE.clear()
    n_cen = sum(1 for r in rows if r.get("length_is_censored"))
    return {"ok": True, "frame": stem, "arm": "uploads",
            "box_px": [x0, y0, x1 - x0, y1 - y0], "parent_size_px": [W, H],
            "clamped": [x0, y0, x1 - x0, y1 - y0] != [x, y, w, h],
            "n_cracks": summ.get("n_cracks_measured"),
            "area_fraction": summ.get("area_fraction"),
            "scale_known": bool(summ.get("scale_known")),
            "n_censored": n_cen,
            "modality": modality,
            "original_cropped": original_cropped,
            "original_note": original_note,
            "note": (f"{n_cen} of {len(rows)} cracks touch the crop edge, so their lengths "
                     f"are lower bounds. Cropping creates edges that were not there in the "
                     f"parent frame.") if n_cen else
                    "no crack touches the crop edge, so no new censoring was introduced."}


def _groups_path():
    return os.path.join(OUT, "groups.json")


def _read_groups():
    p = _groups_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return {}


#: A COLLECTION IS A PLACE IN THE DROPDOWN THAT THE USER MADE.
#:
#: Not an arm. sem/gated, txm and uploads are INSTRUMENTS -- different physical ways of
#: producing a mask -- and the app refuses to aggregate across them because the numbers
#: are not comparable. A collection is a division WITHIN Your images, so every frame in
#: one is still an uploaded mask measured by the same code, and every guard that reads
#: `arm == "uploads"` (delete, mask_edit, crop, send-to-parent) keeps working untouched.
#:
#: Stored as a list of names rather than inferred from the frames that use them, for the
#: same reason /api/arms now always offers uploads: a collection you just made and have
#: not put anything in yet has to exist, or "make one and then add images to it" is not a
#: thing you can do.
SAFE_COLLECTION = re.compile(r"[^\x00-\x1f/\\]{1,60}\Z")


def _collections_path():
    return os.path.join(OUT, "collections.json")


def _read_collections():
    p = _collections_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8") as fh:
            v = json.load(fh)
        return [str(x) for x in v] if isinstance(v, list) else []
    except (ValueError, OSError):
        return []


def _collection_counts():
    n = {}
    for f in (_load_quiet("frames") or []):
        if f.get("arm") == "uploads" and f.get("collection"):
            n[f["collection"]] = n.get(f["collection"], 0) + 1
    return n


@app.get("/api/collections")
def collections_get():
    counts = _collection_counts()
    names = _read_collections()
    # A name that frames still point at but the list has lost is still a real place --
    # report it rather than stranding those frames somewhere unreachable.
    for extra in sorted(set(counts) - set(names)):
        names.append(extra)
    return {"collections": [{"name": n, "n_frames": counts.get(n, 0)} for n in names]}


@app.post("/api/collections")
def collections_set(payload: dict = Body(...)):
    """Make or remove one collection. Removing it never touches an image."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "a collection needs a name")
    if not SAFE_COLLECTION.match(name):
        raise HTTPException(400, "a collection name cannot contain a slash or a control "
                                 "character, and must be 60 characters or fewer")
    with _DATASET_LOCK:
        names = _read_collections()
        if payload.get("delete"):
            names = [n for n in names if n != name]
            # THE IMAGES STAY. Removing a collection is removing a label, and the frames
            # that carried it go back to being plain Your images -- deleting them would
            # make an organising control into a destructive one.
            fp = os.path.join(OUT, "frames.json")
            if os.path.exists(fp):
                cur = json.load(open(fp, encoding="utf-8"))
                freed = 0
                for r in cur:
                    if r.get("arm") == "uploads" and r.get("collection") == name:
                        r.pop("collection", None); freed += 1
                _write_json(fp, cur)
            _write_json(_collections_path(), names)
            _CACHE.clear()
            return {"ok": True, "deleted": name, "frames_freed": freed,
                    "collections": names,
                    "note": "the images are still in Your images; only the label is gone."}
        if name not in names:
            names.append(name)
        _write_json(_collections_path(), names)
        _CACHE.clear()
    return {"ok": True, "collections": names}


@app.post("/api/set_collection")
def set_collection(payload: dict = Body(...)):
    """Move one uploaded frame into a collection, or out of every collection."""
    frame = (payload.get("frame") or "").strip()
    name = payload.get("collection")
    name = None if name in (None, "", False) else str(name).strip()
    if not frame:
        raise HTTPException(400, "which frame?")
    if name is not None and not SAFE_COLLECTION.match(name):
        raise HTTPException(400, f"{name!r} is not a usable collection name")
    with _DATASET_LOCK:
        fp = os.path.join(OUT, "frames.json")
        cur = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else []
        hit = False
        for r in cur:
            if r.get("arm") == "uploads" and r.get("frame") == frame:
                hit = True
                if name is None:
                    r.pop("collection", None)
                else:
                    r["collection"] = name
        if not hit:
            raise HTTPException(404, f"there is no uploaded frame called {frame!r}")
        _write_json(fp, cur)
        if name is not None and name not in _read_collections():
            _write_json(_collections_path(), _read_collections() + [name])
        _CACHE.clear()
    return {"ok": True, "frame": frame, "collection": name}


@app.get("/api/groups")
def groups_get():
    return {"groups": _read_groups()}


@app.post("/api/groups")
def groups_set(payload: dict = Body(...)):
    """Save or delete one named group. A group is a list of {arm, frame}."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "a group needs a name")
    g = _read_groups()
    if payload.get("delete"):
        g.pop(name, None)
    else:
        members = payload.get("frames") or []
        if not isinstance(members, list) or not members:
            raise HTTPException(400, "a group needs at least one frame")
        g[name] = [{"arm": m.get("arm"), "frame": m.get("frame")} for m in members
                   if m.get("arm") and m.get("frame")]
    _write_json(_groups_path(), g)
    return {"ok": True, "groups": g}


def _collect(members):
    """Resolve [{arm, frame}] into the frame records and their crack rows."""
    want = {(m.get("arm"), m.get("frame")) for m in members}
    frames = [f for f in (_load_quiet("frames") or [])
              if (f.get("arm"), f.get("frame")) in want]
    by = {}
    for c in (_load_quiet("cracks") or []):
        k = (c.get("arm"), c.get("frame"))
        if k in want:
            by.setdefault(k, []).append(c)
    missing = sorted(f"{a}/{f}" for (a, f) in want
                     if not any(x.get("arm") == a and x.get("frame") == f for x in frames))
    return frames, by, missing


@app.post("/api/group_stats")
def group_stats(payload: dict = Body(...)):
    """Preliminary analysis over a chosen set of frames."""
    from app import groupstats as GS
    members = payload.get("frames") or _read_groups().get(payload.get("name") or "", [])
    if not members:
        raise HTTPException(400, "give either a list of frames or the name of a saved group")
    frames, by, missing = _collect(members)
    if not frames:
        raise HTTPException(404, f"none of those frames is measured: {', '.join(missing)}")
    out = GS.group_summary(frames, by)
    out["requested"] = len(members)
    out["missing"] = missing
    return out


def _root_box(arm, frame, by_key, _seen=None):
    """Resolve a frame to (root_arm, root_frame, x, y, w, h) in the ROOT frame's pixels.

    A crop of a crop is still the parent's pixels, so the chain is walked to the end and
    each box offset into its parent's coordinates on the way up. Returns None when the
    frame is unknown or its provenance is incomplete.
    """
    _seen = _seen or set()
    key = (arm, frame)
    if key in _seen:            # a cycle cannot be resolved; refuse rather than loop
        return None
    _seen.add(key)
    rec = by_key.get(key)
    if rec is None:
        # ONLY AN UPLOADS FRAME CAN BE A CROP, so a missing record for any other arm is a
        # root whose record simply has not been measured into this dataset -- which is the
        # normal state of a fresh install that has cropped one SEM frame without running
        # the corpus measurement. Returning None there made the lineage unresolvable and
        # the crop unsendable, for a reason that had nothing to do with the crop.
        if arm == "uploads":
            return None
        try:
            mp = _mask_path(arm, frame)
        except HTTPException:
            return None
        if not mp or not os.path.exists(mp):
            return None
        from PIL import Image as _I
        _I.MAX_IMAGE_PIXELS = None
        with _I.open(mp) as _m:
            return (arm, frame, 0, 0, _m.size[0], _m.size[1])
    cf = rec.get("cropped_from") or {}
    box = cf.get("box_px")
    if not (cf.get("frame") and isinstance(box, list) and len(box) == 4):
        w, h = rec.get("width_px"), rec.get("height_px")
        if not (w and h):
            return None
        return (arm, frame, 0, 0, int(w), int(h))
    up = _root_box(cf.get("arm"), cf["frame"], by_key, _seen)
    if up is None:
        return None
    rarm, rframe, px, py, pw, ph = up
    x, y, w, h = (int(v) for v in box)
    # THE PARENT'S EXTENT WAS BOUND TO THROWAWAY NAMES AND NEVER USED. cropped_from records
    # parent_size_px at crop time and nothing read it, so a parent re-rendered at a new
    # size since the crop was taken would silently relocate the box -- the offset would
    # still compose, and the write would land on different pixels of a different picture.
    # Check it at every link, and refuse rather than guess.
    want = cf.get("parent_size_px")
    if isinstance(want, list) and len(want) == 2 and (pw, ph) != (int(want[0]), int(want[1])):
        return None
    if not (0 <= x and 0 <= y and x + w <= pw and y + h <= ph):
        return None
    return (rarm, rframe, px + x, py + y, w, h)


def _pixel_overlaps(members_a, members_b):
    """Pairs across the two groups that are literally the same pixels, with how much.

    A CROP IS NOT AN INDEPENDENT FRAME. Put a crop on one side and its parent on the other
    and the comparison is the same pixels against themselves: it cannot fail to agree, and
    the agreement means nothing. The same error one level up is what inflates a retrained
    model's held-out score -- on this corpus, splitting each image into four pseudo-crops
    and letting them count as separate frames moved pooled grouped-CV from 0.8910 to
    0.9368 with no label added and no pixel painted, which is several times the size of
    the real differences the SEM repo's promotion gate exists to police.
    """
    by_key = {(f.get("arm"), f.get("frame")): f for f in (_load_quiet("frames") or [])}
    ra = [(m, _root_box(m.get("arm"), m.get("frame"), by_key)) for m in members_a]
    rb = [(m, _root_box(m.get("arm"), m.get("frame"), by_key)) for m in members_b]
    out = []
    for ma, a in ra:
        if not a:
            continue
        for mb, b in rb:
            if not b or a[0] != b[0] or a[1] != b[1]:
                continue
            ax0, ay0, aw, ah = a[2], a[3], a[4], a[5]
            bx0, by0, bw, bh = b[2], b[3], b[4], b[5]
            ix = max(0, min(ax0 + aw, bx0 + bw) - max(ax0, bx0))
            iy = max(0, min(ay0 + ah, by0 + bh) - max(ay0, by0))
            if ix <= 0 or iy <= 0:
                continue
            inter = ix * iy
            smaller = min(aw * ah, bw * bh)
            out.append({"a": ma.get("frame"), "b": mb.get("frame"),
                        "root": a[1],
                        "share_of_smaller": round(inter / smaller, 4) if smaller else None})
    return out


# ======================================================================== SEND TO PARENT
#
# The only route by which painting a crop can improve the detector.
#
# A crop holds its parent's pixels, so counting it as a NEW image is a leak and not a
# gain: splitting each image into four pseudo-crops and letting them count as separate
# frames moved pooled grouped-CV from 0.8910 to 0.9368 with no label added and no pixel
# painted. (The mechanism is concrete -- the SEM repo's specimen_key() cannot parse a crop
# name and returns None, so a crop of the held-out frame stays in training while its
# parent is held out.) The strokes therefore go into the PARENT's correction mask, at the
# parent's own coordinates, under the parent's own image identity. Nothing new is created,
# so there is nothing to leak, and no fold structure changes: nothing in the retrain keys
# on the NUMBER of labelled images.
#
# ONLY THE PIXELS THE HUMAN ACTUALLY CHANGED. The crop is cut from the detector's output,
# so most of it is the model's opinion. Writing the whole box would manufacture a verdict
# on every pixel in it -- about a million for a 1000x900 crop -- from a handful of
# strokes. That is not hypothetical arithmetic: the entire corpus holds 258k not-crack
# pixels, 92.4% of the negative ROWS come from one frame, and stamping one 500x500 box
# white would roughly double the corpus's negative evidence from a single gesture.

#: The SEM repo's correction-mask coding. ANY value outside 0..3 silently suppresses the
#: region it lands in -- build_training_data does np.bincount(...)[1:].argmax()+1, so a
#: stray 255 is counted as "reviewed" and then yields a verdict that is neither 1 nor 2,
#: and the region is dropped with no warning. The app's own crop masks are literally
#: 0/255, which is exactly the byte copy that must never happen.
PAINT_CRACK, PAINT_NOT_CRACK, PAINT_UNREVIEWED, PAINT_ERASED = 1, 2, 0, 3

#: Same rule as measure.load_mask, so a label agrees with what the app measured.
CRACK_BELOW = 128

#: build_training_data's floor for a verdict that lands where the segmenter proposed no
#: candidate at all: connected components smaller than this teach nothing. Cropping in
#: order to zoom is exactly what encourages strokes this fine, so it is reported.
FROM_SCRATCH_MIN_PX = 40

#: train_v3_weighted gives each image mass min(1, rows/50). Below the floor, adding rows
#: multiplies that frame's influence over the whole fit; at or above it, nothing changes.
WEIGHT_FLOOR_ROWS = 50


def _sem_code_on_path():
    import sys
    for d in P.sem_code_dirs():
        if d not in sys.path:
            sys.path.insert(0, d)


def _sem_paint_dir():
    """The SEM repo's paint directory, ASKED OF THAT REPO rather than reconstructed.

    common.PAINT_DIR honours SEMCRACK_PAINT_DIR, which is how this whole path can be
    exercised against a throwaway copy of the hand labels. Joining the default location
    here instead would split the brain: the writer (common.save_correction_mask) would
    follow the environment while the reader, the undo stack and the "does it already
    exist" check stayed on the real directory -- so a test believing itself sandboxed
    would read the real masks, and a merge would snapshot one file and overwrite another.
    """
    try:
        _sem_code_on_path()
        import common as _c
        return _c.PAINT_DIR
    except Exception:                                   # noqa: BLE001
        sem = P.sem_repo()
        return os.path.join(sem, "interior_active_learning", "paint") if sem else None


def _correction_mask_path(frame):
    d = _sem_paint_dir()
    return os.path.join(d, f"{frame}_correction_mask.png") if d else None


def _gated_mask_size(frame):
    """The correction mask's coordinate frame, taken from the gated mask rather than from
    the original .tif -- the two differ by the databar, and on all 48 currently painted
    frames the correction mask matches the GATED mask exactly. That identity is what makes
    a crop box usable as an offset without a transform."""
    derived = P.sem_derived()
    if not derived:
        return None
    g = os.path.join(derived, "gated_masks", f"{frame}_gated.png")
    if not os.path.exists(g):
        return None
    from PIL import Image as _I
    _I.MAX_IMAGE_PIXELS = None
    with _I.open(g) as im:
        return im.size


def _undo_snapshot(frame):
    """Push the current mask onto the SEM paint tool's own undo stack, so a merge can be
    taken back from the program the user already knows.

    Replicated rather than imported: app_undo imports flask, which this app does not have.
    The format is the contract -- paint/.undo/<image>/NNNN.png, depth 10, a `.none` marker
    when no mask existed, and no entry when the top of the stack is byte-identical.
    """
    import shutil
    try:
        d = _sem_paint_dir()
        if not d:
            return None
        root = os.path.join(d, ".undo", frame)
        os.makedirs(root, exist_ok=True)
        have = sorted(f for f in os.listdir(root) if f.endswith((".png", ".none")))
        src = _correction_mask_path(frame)
        if have:
            top = os.path.join(root, have[-1])
            if ((not os.path.exists(src) and have[-1].endswith(".none"))
                    or (os.path.exists(src) and have[-1].endswith(".png")
                        and os.path.getsize(top) == os.path.getsize(src)
                        and open(top, "rb").read() == open(src, "rb").read())):
                return have[-1]
        n = (max(int(f.split(".")[0]) for f in have) + 1) if have else 0
        if os.path.exists(src):
            name = f"{n:04d}.png"
            shutil.copy2(src, os.path.join(root, name))
        else:
            name = f"{n:04d}.none"
            open(os.path.join(root, name), "w").close()
        while True:
            have = sorted(f for f in os.listdir(root) if f.endswith((".png", ".none")))
            if len(have) <= 10:
                break
            os.remove(os.path.join(root, have[0]))
        return name
    except Exception:                                   # noqa: BLE001
        return None


def _held_out_frame():
    """The frame train_v3_weighted holds out, read from its source rather than assumed.

    Regex rather than import: that module pulls in scikit-learn, and the SEM repo's model
    is pickled against a different version than this app's venv carries.
    """
    for d in P.sem_code_dirs():
        f = os.path.join(d, "train_v3_weighted.py")
        if not os.path.exists(f):
            continue
        try:
            import re as _re
            m = _re.search(r'^HELD\s*=\s*["\']([^"\']+)', open(f, encoding="utf-8").read(),
                           _re.M)
            if m:
                return m.group(1)
        except Exception:                               # noqa: BLE001
            pass
    return None


def _rows_for_frame(frame):
    """How many training rows this frame currently contributes, or None if unknown."""
    sem = P.sem_repo()
    if not sem:
        return None
    csv = os.path.join(sem, "training_data", "labeled_regions.csv")
    if not os.path.exists(csv):
        return None
    try:
        import csv as _csv
        with open(csv, newline="", encoding="utf-8") as fh:
            return sum(1 for r in _csv.DictReader(fh) if r.get("SourceImage") == frame)
    except Exception:                                   # noqa: BLE001
        return None


@app.post("/api/send_to_parent")
def send_to_parent(payload: dict = Body(...)):
    """Write the strokes made on a crop into its PARENT frame's correction mask."""
    import numpy as np
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None

    frame = (payload.get("frame") or "").strip()
    dry = bool(payload.get("dry_run"))
    if not frame:
        raise HTTPException(400, "which crop?")

    # AN EDITED RESEARCH FRAME IS THE ORDINARY CASE NOW, because a correction is stored
    # against the frame it was made on rather than copied into another arm. The baseline
    # is then the research mask still sitting untouched on disk: same size, offset zero,
    # no lineage to resolve. It is a better reference than any snapshot -- it cannot
    # drift, and there is nothing to keep beside it.
    send_arm = (payload.get("arm") or "uploads").strip()
    edit_src = _edit_of(send_arm, frame) if send_arm.startswith("sem/") else None
    if edit_src:
        root_arm, root_frame = send_arm, frame
        baseline = _mask_path(send_arm, frame)
        if not baseline or not os.path.exists(baseline):
            raise HTTPException(404, f"no mask on disk for {frame!r} in {send_arm!r}")
        from PIL import Image as _I0
        _I0.MAX_IMAGE_PIXELS = None
        with _I0.open(baseline) as _b:
            bw, bh = _b.size
        ox = oy = 0
        rec = {}
    elif send_arm.startswith("sem/"):
        raise HTTPException(400, f"{frame!r} has no correction on it yet -- draw on it "
                                 f"first, and the strokes are what gets sent")
    else:
        by_key = {(f.get("arm"), f.get("frame")): f
                  for f in (_load_quiet("frames") or [])}
        rec = by_key.get(("uploads", frame))
        if rec is None:
            raise HTTPException(404, f"no uploaded frame called {frame!r}")
        edit_src = None
    # TWO WAYS A FRAME CAN BE DERIVED FROM A RESEARCH FRAME, and both must work.
    #
    #   copied_from  -- the normal one. Painting a sem/* frame writes a COPY into uploads
    #                   rather than touching the research mask, and that copy is the same
    #                   size as its source. The baseline is then the source mask ITSELF,
    #                   still untouched on disk, which is a better pristine reference than
    #                   any snapshot: it cannot drift, and there is nothing to keep.
    #   cropped_from -- a frame cut out by /api/crop, which carries an offset.
    #
    # Cropping in the UI is now a VIEW on the open image, so the ordinary path is a copy
    # at offset (0, 0) and the whole class of offset bugs does not arise. The crop branch
    # stays because /api/crop still exists and its frames are still sendable.
    copied = rec.get("copied_from")
    if edit_src:
        pass                                  # resolved above: this frame IS the target
    elif rec.get("cropped_from"):
        box = _root_box("uploads", frame, by_key)
        if box is None:
            raise HTTPException(400, "this crop's lineage could not be resolved to a root "
                                     "frame, so there is no offset to write at")
        root_arm, root_frame, ox, oy, bw, bh = box
        baseline = None                       # the as-cut copy, resolved below
    elif isinstance(copied, str) and "/" in copied:
        root_arm, root_frame = copied.rsplit("/", 1)
        if not root_arm.startswith("sem/"):
            raise HTTPException(400, f"this frame was copied from {root_arm!r}. Correction "
                                     f"masks and the retrain exist only for the SEM "
                                     f"corpus, so there is nowhere for these strokes to go.")
        baseline = _mask_path(root_arm, root_frame)
        if not baseline or not os.path.exists(baseline):
            raise HTTPException(404, f"the frame this was copied from, {root_frame!r}, has "
                                     f"no mask on disk to compare against")
        from PIL import Image as _I0
        _I0.MAX_IMAGE_PIXELS = None
        with _I0.open(baseline) as _b:
            bw, bh = _b.size
        ox = oy = 0
    else:
        raise HTTPException(400, f"{frame!r} was not derived from a research frame -- it is "
                                 f"neither a crop nor a marked copy -- so there is no "
                                 f"correction mask it belongs to")
    if not root_arm.startswith("sem/"):
        raise HTTPException(400, f"the root of this crop is {root_arm!r}. Correction masks "
                                 f"and the retrain exist only for the SEM corpus, so there "
                                 f"is nowhere for these strokes to go.")
    if not P.sem_repo():
        raise HTTPException(503, "no SEM repo is configured, so there is no correction "
                                 "mask to write into. Set one in Setup.")
    # The frame name is about to be joined into a path in someone else's repository.
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", root_frame):
        raise HTTPException(400, f"refusing to build a path from the frame name "
                                 f"{root_frame!r}")

    # TWO PROCESSES, ONE FILE, NO LOCK. The SEM paint tool serialises its own writes with a
    # threading.Lock, which is per-process and therefore no protection at all against this
    # one. Both would read-modify-write the whole mask and the last save would silently
    # discard the other's strokes. There is no file lock anywhere in that repo, so the only
    # honest answer is to refuse while the other writer is alive.
    if _paint_alive():
        raise HTTPException(409, "the SEM marking tool is running, and it writes the same "
                                 "correction masks with a lock that does not reach across "
                                 "processes -- whichever saved last would silently discard "
                                 "the other's strokes. Close it, then send again.")

    # THE RETRAIN PAIRS A MASK WITH AN ORIGINAL AND SKIPS A MASK THAT HAS NONE, keeping any
    # stale rows it already had. Labels written for a frame with no .tif are effort that
    # never reaches a model and never says so.
    tif = os.path.join(P.sem_repo(), "original", f"{root_frame}.tif")
    if not os.path.exists(tif):
        raise HTTPException(400, f"{root_frame!r} has no original .tif in the SEM repo. The "
                                 f"training build pairs every correction mask with one and "
                                 f"skips the masks that have none, so these strokes would "
                                 f"never reach the model.")

    gsize = _gated_mask_size(root_frame)
    if gsize is None:
        raise HTTPException(400, f"no gated mask on disk for {root_frame!r}, so the shape "
                                 f"of its correction mask cannot be established")
    GW, GH = gsize
    if not (0 <= ox and 0 <= oy and ox + bw <= GW and oy + bh <= GH):
        raise HTTPException(409, f"the crop maps to [{ox}, {oy}, {bw}, {bh}], which does not "
                                 f"fit inside {root_frame!r} at {GW}x{GH}. The mask was "
                                 f"probably regenerated at a different size since this crop "
                                 f"was taken; re-crop it.")

    cur_p = edit_src or os.path.join(UPLOAD_DIR, f"{frame}_gated.png")
    cut_p = baseline or os.path.join(UPLOAD_DIR, f"{frame}_ascut.png")
    if not os.path.exists(cut_p):
        raise HTTPException(409, "there is no pristine copy of what the detector proposed "
                                 "for this frame, so a stroke cannot be told apart from the "
                                 "model's own output. Re-open the research frame and paint "
                                 "again.")
    cur = np.array(Image.open(cur_p).convert("L"))
    cut = np.array(Image.open(cut_p).convert("L"))
    if cur.shape != cut.shape:
        raise HTTPException(409, f"the painted crop is {cur.shape[1]}x{cur.shape[0]} but was "
                                 f"cut at {cut.shape[1]}x{cut.shape[0]}; it has been "
                                 f"resampled, so the strokes no longer line up")
    if (cur.shape[1], cur.shape[0]) != (bw, bh):
        raise HTTPException(409, f"the crop is {cur.shape[1]}x{cur.shape[0]} but its record "
                                 f"says {bw}x{bh}; refusing to guess which is right")

    now_crack, was_crack = cur < CRACK_BELOW, cut < CRACK_BELOW
    changed = now_crack != was_crack
    n_changed = int(changed.sum())
    rows_now = _rows_for_frame(root_frame)
    if n_changed == 0:
        return {"ok": True, "wrote": 0, "parent": root_frame, "crack_px": 0,
                "not_crack_px": 0, "rows_before": rows_now,
                "note": "nothing on this crop differs from what the detector proposed, so "
                        "there is no human verdict to send. Accepting the model's output "
                        "is not a label."}

    _sem_code_on_path()
    try:
        import common as _sem_common
    except Exception as exc:                            # noqa: BLE001
        raise HTTPException(503, f"the SEM repo's correction-mask writer could not be "
                                 f"imported ({type(exc).__name__}), so nothing was written")

    cm = _sem_common.load_correction_mask(root_frame, (GH, GW))
    existed = cm is not None
    if not existed:
        if os.path.exists(_correction_mask_path(root_frame)):
            # load_correction_mask returns None for a shape mismatch too, and in that case
            # writing would rename the human's labels aside as `.stale-HxW.png`. That is
            # the repo protecting itself; do not provoke it.
            raise HTTPException(409, f"{root_frame} already has a correction mask that does "
                                     f"not fit its {GW}x{GH} render. Writing now would move "
                                     f"those hand labels aside; realign or re-mark that "
                                     f"frame first.")
        cm = np.zeros((GH, GW), dtype=np.uint8)
    cm = np.array(cm, dtype=np.uint8, copy=True)
    if cm.shape != (GH, GW):
        raise HTTPException(409, f"internal: mask is {cm.shape} not {(GH, GW)}")

    sub = cm[oy:oy + bh, ox:ox + bw]

    # ERASED (3) IS A HAND VERDICT AND IS NEVER OVERWRITTEN. It says "this should not be a
    # candidate at all", which is a different statement from "this is / is not a crack",
    # and a binary crop mask has no way to express it -- so a stroke landing there carries
    # no information about whether the human still means it. There are 170,922 such pixels
    # across 16 of the 48 painted frames, comparable to the entire not-crack label set
    # (258,352), all of it in the directory this app has no business overwriting. Skipped
    # and counted, not warned about after the fact.
    protect = sub == PAINT_ERASED
    writable = changed & ~protect
    skipped_erased = int((changed & protect).sum())
    n_changed = int(writable.sum())
    if n_changed == 0:
        return {"ok": True, "wrote": 0, "parent": root_frame, "crack_px": 0,
                "not_crack_px": 0, "skipped_erased_px": skipped_erased,
                "rows_before": rows_now, "dry_run": dry,
                "note": f"every one of the {skipped_erased:,} changed pixels lands on the "
                        f"parent's 'erased from candidacy' verdict, which this will not "
                        f"overwrite. Nothing was written."}

    contested = int((writable & (sub != PAINT_UNREVIEWED)).sum())
    now_crack_w = writable & now_crack
    now_not_w = writable & ~now_crack
    n_crack = int(now_crack_w.sum())
    n_not = int(now_not_w.sum())

    # A STROKE IS NOT CONFINED TO THE BOX. build_training_data labels a whole candidate
    # region by plurality, and a region clipped by the crop edge extends past it, so a
    # verdict inside the box can decide pixels far outside it. Reported rather than
    # implied away by a "left_unreviewed" count over the box alone.
    from scipy import ndimage as _ndi
    lab, nlab = _ndi.label(writable)
    sizes = sorted((int(v) for v in (_ndi.sum(writable, lab, range(1, nlab + 1))
                                     if nlab else [])), reverse=True)
    too_small = sum(1 for v in sizes if v < FROM_SCRATCH_MIN_PX)
    edge = set()
    if nlab:
        for band in (lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1]):
            edge.update(int(v) for v in np.unique(band) if v)
    touching_edge = len(edge)

    held = _held_out_frame()
    # THE HELD-OUT FRAME IS THE YARDSTICK, NOT TRAINING DATA. Labels added there never
    # reach the fit, so they cannot improve the model -- but they do change what the
    # held-out AUC is measuring, and in the direction of agreement with whoever painted
    # them. Every gate number then improves at once, for no reason connected to the
    # model. Refused rather than warned, with an explicit override for someone who has
    # read this and means it.
    if held and root_frame == held and not payload.get("allow_held_out"):
        raise HTTPException(409,
            f"{root_frame} is the frame the retrain HOLDS OUT to measure out-of-sample "
            f"performance. Labels here never reach training, so they cannot improve the "
            f"model -- they only move the yardstick toward whoever painted them, and the "
            f"before/after comparison stops measuring the same thing. Pass "
            f"allow_held_out if you intend that and will re-establish the baseline.")

    if dry:
        return {"ok": True, "dry_run": True, "parent": root_frame, "parent_arm": root_arm,
                "box_px": [ox, oy, bw, bh], "would_write": n_changed,
                "crack_px": n_crack, "not_crack_px": n_not,
                "skipped_erased_px": skipped_erased,
                "contested_existing_verdicts": contested, "marks": nlab,
                "marks_below_floor": too_small, "marks_touching_box_edge": touching_edge,
                "rows_before": rows_now, "mask_exists": existed,
                "is_held_out_frame": bool(held and root_frame == held),
                "note": "nothing was written. Send again without dry_run to apply."}

    # THE SNAPSHOT IS THE ONLY WAY BACK. If it could not be taken, the write must not
    # happen: this directory is irreplaceable and the app would be its only mutator with
    # no recovery path. Swallowing the failure and writing anyway is how the undo stack
    # becomes decorative.
    undo = _undo_snapshot(root_frame)
    if undo is None:
        raise HTTPException(500, "could not record an undo snapshot of "
                                 f"{root_frame}'s correction mask, so the write was not "
                                 f"attempted -- these are hand labels with no other copy.")

    sub[now_crack_w] = PAINT_CRACK
    sub[now_not_w] = PAINT_NOT_CRACK
    cm[oy:oy + bh, ox:ox + bw] = sub
    assert cm.dtype == np.uint8 and set(np.unique(cm).tolist()) <= {0, 1, 2, 3}
    assert int((np.asarray(cm)[oy:oy + bh, ox:ox + bw] == PAINT_ERASED).sum()) \
        == int(protect.sum()), "an erased verdict was overwritten"

    # ONE WRITER AT A TIME, AT LEAST WITHIN THIS PROCESS. save_correction_mask writes
    # through a FIXED `<path>.tmp`, so two merges into the same parent -- two crops of one
    # frame, or a double-clicked button -- interleave on that one temp file and can leave
    # the mask truncated or half-written. The SEM repo's own per-frame lock is the right
    # one to hold because it is the lock its other writers hold. It does not reach across
    # processes; the running-paint-tool refusal above is what covers that.
    _lock = getattr(_sem_common, "mask_lock", None)
    if _lock is not None:
        with _lock(root_frame):
            _sem_common.save_correction_mask(root_frame, cm)
    else:
        _sem_common.save_correction_mask(root_frame, cm)

    # HOW MUCH OF THIS CAN ACTUALLY BECOME A TRAINING ROW. build_training_data labels a
    # candidate REGION by plurality over the non-zero values inside it, so a correction
    # inside a large region already marked the other way is simply outvoted and produces
    # nothing. Where no candidate exists at all there is a separate path with a hard
    # 40-pixel floor. Neither is predictable here without running the detector, but the
    # component sizes are, and a stroke below the floor cannot win either way.
    warn = []
    if n_not == 0:
        warn.append("Every stroke here says CRACK. The corpus already holds 70.0M crack "
                    "pixels against 258k not-crack, and 35 of its 48 painted frames carry "
                    "no not-crack label at all -- a correction (erasing something the "
                    "detector wrongly marked) is worth far more to this model than another "
                    "confirmation.")
    if too_small:
        warn.append(f"{too_small} of {nlab} separate marks are under {FROM_SCRATCH_MIN_PX} "
                    f"px. Where the detector proposed no candidate, the training build "
                    f"discards components below that size, so those marks may teach "
                    f"nothing.")
    if skipped_erased:
        warn.append(f"{skipped_erased:,} painted pixels were SKIPPED because the parent "
                    f"marks them 'erased from candidacy'. That is a hand verdict a binary "
                    f"crop cannot contradict, so it was left exactly as it was.")
    if touching_edge:
        warn.append(f"{touching_edge} of {nlab} marks touch the edge of the crop. The "
                    f"training build labels a whole candidate region by plurality, and a "
                    f"region clipped by the crop extends beyond it -- so these verdicts "
                    f"decide pixels outside the box you could see.")
    if held and root_frame == held:
        warn.append(f"{root_frame} is the frame the retrain HOLDS OUT to measure "
                    f"out-of-sample performance. Labels added here do not leak into "
                    f"training, but they change the yardstick, so the held-out AUC before "
                    f"and after will no longer be measuring the same thing.")
    if rows_now is not None and rows_now < WEIGHT_FLOOR_ROWS:
        warn.append(f"{root_frame} currently contributes {rows_now} training rows, below "
                    f"the {WEIGHT_FLOOR_ROWS}-row floor where each image's weight is "
                    f"min(1, rows/{WEIGHT_FLOOR_ROWS}). Adding rows to it raises its "
                    f"influence over the whole fit; above the floor it would not.")

    return {
        "ok": True,
        "parent": root_frame,
        "parent_arm": root_arm,
        "box_px": [ox, oy, bw, bh],
        "created_mask": not existed,
        "undo_entry": undo,
        "wrote": n_changed,
        "crack_px": n_crack,
        "not_crack_px": n_not,
        "marks": nlab,
        "largest_mark_px": sizes[0] if sizes else 0,
        "marks_below_floor": too_small,
        "marks_touching_box_edge": touching_edge,
        "contested_existing_verdicts": contested,
        "skipped_erased_px": skipped_erased,
        "untouched_in_box": int(bw * bh - n_changed - skipped_erased),
        "rows_before": rows_now,
        "dry_run": False,
        "warnings": warn,
        "note": (f"Written into {root_frame}'s own correction mask, under its own image "
                 f"identity, so the retrain treats this as more evidence about a frame it "
                 f"already knows rather than as a new frame. Whether these pixels become "
                 f"training ROWS is decided by a plurality vote over each candidate region, "
                 f"which only the training build can answer -- re-run it and compare this "
                 f"frame's row count against the {rows_now} it has now."),
    }


@app.post("/api/group_compare")
def group_compare(payload: dict = Body(...)):
    """Two groups side by side, with what would make the comparison unreadable stated."""
    from app import groupstats as GS
    saved = _read_groups()
    def side(k, default_label):
        spec = payload.get(k) or {}
        members = spec.get("frames") or saved.get(spec.get("name") or "", [])
        if not members:
            raise HTTPException(400, f"side {k!r} has no frames")
        fr, by, miss = _collect(members)
        if not fr:
            raise HTTPException(404, f"side {k!r}: none of those frames is measured")
        s = GS.group_summary(fr, by)
        s["missing"] = miss
        return s, (spec.get("name") or default_label)
    a, la = side("a", "A")
    b, lb = side("b", "B")
    res = GS.compare(a, b, la, lb)
    ov = _pixel_overlaps(payload.get("a", {}).get("frames")
                         or saved.get((payload.get("a") or {}).get("name") or "", []),
                         payload.get("b", {}).get("frames")
                         or saved.get((payload.get("b") or {}).get("name") or "", []))
    if ov:
        worst = max(ov, key=lambda o: o["share_of_smaller"] or 0)
        res.setdefault("caveats", [])
        # FIRST, because it invalidates the comparison rather than qualifying it.
        res["caveats"].insert(0, (
            f"THE TWO GROUPS SHARE PIXELS. {len(ov)} pair"
            f"{'' if len(ov) == 1 else 's'} of frames overlap -- "
            f"{worst['a']} and {worst['b']} cover the same part of "
            f"{worst['root']} ({(worst['share_of_smaller'] or 0) * 100:.0f}% of the "
            f"smaller one). A crop is not an independent frame: comparing it against its "
            f"own parent compares the same pixels with themselves, and they agree because "
            f"they are the same, not because anything was measured."))
    res["pixel_overlaps"] = ov
    res["a"], res["b"] = a, b
    return res


# ============================================================================== DELETE
#
# The one endpoint that removes a frame, and the only arm it will touch is uploads.
#
# WHY NOT THE OTHER ARMS. sem/* and txm* read the SEM repo's derived masks and the TXM
# export -- hand-made research data this app has never written to. A delete there would
# either destroy something it does not own, or merely hide a row that the next corpus
# measurement puts straight back. Neither is a delete, so it is refused rather than
# offered and quietly broken.
#
# WHY TRASH RATHER THAN UNLINK. Because the author of this endpoint deleted two of this
# user's frames by accident on the day it was written, while clearing test artifacts, and
# they were not recoverable. A delete the user presses on purpose deserves at least the
# safety net that mistake did not have.

#: A frame name is about to be joined into filesystem paths. `arm == "uploads"` constrains
#: the ARM, not the NAME: without this, frame="../../../sem-crack-detector/crack_export/
#: derived/gated_masks/MAR_H_AS_CBS_0001" moves a research mask into the trash. No other
#: uploads write path validates its name either -- this is the first.
SAFE_FRAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\-]*\Z")

#: Everything one uploads frame can own on disk. `_ascut` and `_original` exist only for
#: crops and marked copies; a glob of `<frame>*` would instead sweep up any frame whose
#: name merely starts with this one's.
UPLOAD_SUFFIXES = ("_gated.png", "_original.png", "_ascut.png")


#: AN EDIT BELONGS TO THE FRAME IT WAS MADE ON, not to a new frame beside it.
#:
#: Painting a research frame used to file a COPY in uploads, so correcting one image left
#: you with two: the original in its own group and "<name>_marked" in Your images. The
#: reader asked for the opposite -- "it should just autosave on the same file and if I
#: leave and come back it should still be there" -- and they are right, because a
#: correction is not a different picture, it is this picture with a mistake taken out.
#:
#: WHAT IS NOT DONE IS WRITING OVER THE RESEARCH MASK. Those are the SEM and TXM
#: pipelines' own output. Overwriting one would be erased by the next pipeline run, and it
#: would destroy the comparison between what the detector said and what a human corrected
#: -- which is the measurement this whole project rests on. The edit is kept in the app's
#: own folder, keyed to (arm, frame), and served in the mask's place whenever it exists.
#: From the sidebar it is the same image; on disk the original is untouched.
def _edit_path(arm, frame):
    if not frame or not SAFE_FRAME.match(frame):
        return None
    d = os.path.join(OUT, "edits", arm.replace("/", "__"))
    return os.path.join(d, f"{frame}_gated.png")


def _edit_of(arm, frame):
    p = _edit_path(arm, frame)
    return p if (p and os.path.exists(p)) else None


def _trash_dir():
    """Beside the data, not inside uploads and not inside the render cache.

    analysis/batch.py re-measures the uploads arm by globbing UPLOADS/*_gated.png and
    replacing every uploads row wholesale, so a trashed file left as a sibling there comes
    back as a frame on the next corpus measurement. glob's `*` does not cross a separator,
    so a subdirectory would be safe -- but the render cache is not: _disk_cache_trim()
    os.remove()s what it finds and breaks out of its loop on the first OSError, so a
    directory in there silently stops the 600 MB budget being enforced at all.
    """
    d = os.path.join(OUT, "trash")
    os.makedirs(d, exist_ok=True)
    return d


def _dependents_of(frame):
    """Frames that would be orphaned by deleting this one, with how they point at it."""
    out = []
    for f in (_load_quiet("frames") or []):
        cf = f.get("cropped_from") or {}
        if cf.get("arm") == "uploads" and cf.get("frame") == frame:
            out.append({"frame": f.get("frame"), "via": "cropped from"})
        cp = f.get("copied_from")
        if isinstance(cp, str) and cp == f"uploads/{frame}":
            out.append({"frame": f.get("frame"), "via": "copied from"})
    return out


@app.post("/api/restore")
def restore(payload: dict = Body(...)):
    """Put back what a delete or a discard just moved to the trash.

    WHY THIS EXISTS RATHER THAN A CONFIRMATION. Deleting used to take two clicks: one to
    arm the control and one to mean it. A confirmation taxes every correct action in order
    to catch the rare wrong one, and it does not even work -- people learn to click
    through it. Acting at once and offering the way back costs nothing when the click was
    meant, and is the better remedy when it was not, because it is still there a minute
    later instead of half a second before.

    It is only possible because neither path destroys anything in the first place: both
    move files into trash/ rather than unlinking them.
    """
    import shutil
    kind = (payload.get("kind") or "").strip()
    arm = (payload.get("arm") or "").strip()
    frame = (payload.get("frame") or "").strip()
    if kind not in ("frame", "edit"):
        raise HTTPException(400, f"restore what? {kind!r}")
    if not frame or not SAFE_FRAME.match(frame):
        raise HTTPException(400, f"{frame!r} is not a frame name this will build a path from")
    tdir = _trash_dir()

    def _in_trash(name):
        """Resolve a trash entry, refusing anything that is not a plain name inside it.

        "" AND ".." BOTH SURVIVE A BASENAME CHECK. os.path.basename("..") is "..", and
        both join to a path whose dirname IS the trash directory, so a realpath comparison
        passes them too -- and os.path.exists() then says yes, because the thing they name
        is the directory itself. Both reached open() and returned a 500. The entry has to
        be a plain name AND a regular file.
        """
        if (not isinstance(name, str) or not name or name in (".", "..")
                or os.sep in name or (os.altsep and os.altsep in name)
                or os.path.basename(name) != name):
            raise HTTPException(400, f"not a trash entry: {name!r}")
        src = os.path.join(tdir, name)
        if os.path.realpath(os.path.dirname(src)) != os.path.realpath(tdir):
            raise HTTPException(400, f"not a trash entry: {name!r}")
        return src

    if kind == "edit":
        dst = _edit_path(arm, frame)
        if not dst:
            raise HTTPException(400, f"no edit location for {arm!r}/{frame!r}")
        names = payload.get("files") or ([payload["record"]] if payload.get("record") else [])
        if not names:
            raise HTTPException(400, "which trashed correction?")
        src = _in_trash(names[0])
        if not os.path.isfile(src):
            raise HTTPException(404, "that correction is not in the trash any more")
        # UNDO PUTS BACK WHAT WAS THERE; IT DOES NOT OVERWRITE WHAT IS THERE NOW. The
        # offer stands for 25 seconds, which is long enough to discard a correction and
        # start painting a new one before thinking better of it -- and that restore would
        # have replaced the new strokes with the old ones and said "is back".
        if _edit_of(arm, frame):
            raise HTTPException(409, f"{frame} has a correction on it again -- undoing "
                                     f"would throw that one away. The discarded one is "
                                     f"still in the app's trash folder.")
        with _DATASET_LOCK:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            fp = os.path.join(OUT, "frames.json")
            if os.path.exists(fp):
                with open(fp, encoding="utf-8") as fh:
                    cur = json.load(fh)
                for r in cur:
                    if r.get("arm") == arm and r.get("frame") == frame:
                        r["edited"] = True
                _write_json(fp, cur)
            _CACHE.clear()
        # Measured from the restored strokes. Safe here where it is not for a frame: the
        # research record was never removed, so remeasure still finds the prior it needs
        # for modality, specimen and lineage.
        out = remeasure(arm=arm, frame=frame)
        out["restored"] = [os.path.basename(dst)]
        out["note"] = f"the correction on {frame} is back."
        return out

    # A FRAME IS RESTORED FROM ITS RECORD, NOT BY MEASURING IT AGAIN -- see the comment
    # beside where delete_frame writes the record for what re-measuring would lose.
    if arm not in ("", "uploads"):
        raise HTTPException(400, "only an uploaded frame is deleted, so only one is restored")
    rp = _in_trash(payload.get("record") or "")
    if not os.path.isfile(rp):
        raise HTTPException(404, "that frame is not in the trash any more")
    with open(rp, encoding="utf-8") as fh:
        rec = json.load(fh)
    if (rec.get("frame") or {}).get("frame") != frame:
        raise HTTPException(400, "that trash record is for a different frame")

    moved = []
    with _DATASET_LOCK:
        # SAME RULE AS FOR AN EDIT: 25 seconds is long enough to delete a frame and upload
        # a new one under the same name, and the restore would have moved the old PNG over
        # the new one and replaced its record with the old measurements.
        if any(f.get("arm") == "uploads" and f.get("frame") == frame
               for f in (_load_quiet("frames") or [])):
            raise HTTPException(409, f"there is an uploaded frame called {frame} again -- "
                                     f"undoing would overwrite it. The deleted one is "
                                     f"still in the app's trash folder.")
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        up_real = os.path.realpath(UPLOAD_DIR)
        for name in rec.get("files") or []:
            src = _in_trash(name)
            if not os.path.isfile(src):
                continue
            # "<stamp>__<frame><suffix>" -- the stamp carries no "__", so one split takes
            # it off and leaves a frame name that may contain its own.
            tail = name.split("__", 1)[1] if "__" in name else name
            dst = os.path.join(UPLOAD_DIR, tail)
            if os.path.realpath(os.path.dirname(dst)) != up_real:
                raise HTTPException(400, f"refusing to restore outside uploads: {dst}")
            shutil.move(src, dst)
            moved.append(os.path.basename(dst))
        if not moved:
            raise HTTPException(404, "that frame's files are not in the trash any more")

        fp = os.path.join(OUT, "frames.json")
        cur = json.load(open(fp)) if os.path.exists(fp) else []
        cur = [f for f in cur
               if not (f.get("arm") == "uploads" and f.get("frame") == frame)]
        _write_json(fp, cur + [rec["frame"]])

        if rec.get("cracks"):
            cp = os.path.join(OUT, "cracks.json")
            cr = json.load(open(cp)) if os.path.exists(cp) else []
            cr = [c for c in cr
                  if not (c.get("arm") == "uploads" and c.get("frame") == frame)]
            _write_json(cp, cr + rec["cracks"])

        if rec.get("groups"):
            groups = _read_groups()
            for name, members in rec["groups"].items():
                if name in groups:
                    # THE MEMBER BACK, NOT THE OLD LIST BACK. Writing the saved list
                    # wholesale would silently drop anything added to that group since the
                    # delete -- an undo that undoes someone else's work as well as its own.
                    have = {(m.get("arm"), m.get("frame")) for m in groups[name]}
                    groups[name] = groups[name] + [
                        m for m in members if (m.get("arm"), m.get("frame")) not in have]
                else:
                    # The group emptied and was popped, so there is nothing to merge into
                    # and the saved list is the only record of what it held.
                    groups[name] = members
            _write_json(_groups_path(), groups)

        if rec.get("scale"):
            try:
                import sys as _sys
                _sys.path.insert(0, os.path.join(RES, "analysis"))
                import scale as _scale
                _scale.set_user_scale(frame, rec["scale"])
            except Exception:                           # noqa: BLE001 - never fail a restore
                pass

        _rebuild_uploads_specimen()
        _CACHE.clear()
    os.remove(rp)
    return {"ok": True, "arm": "uploads", "frame": frame, "restored": moved,
            "crack_rows_restored": len(rec.get("cracks") or []),
            "groups_restored": sorted(rec.get("groups") or {}),
            "scale_restored": bool(rec.get("scale")),
            "note": f"{frame} is back, with the numbers it had when it was deleted."}


@app.post("/api/hide_frame")
def hide_frame(payload: dict = Body(...)):
    """Take a frame out of the sidebar without destroying anything.

    WHY HIDING IS THE HONEST VERB FOR A RESEARCH FRAME. sem/* and txm* rows are the
    pipelines' output; the app has never written to them and deleting one would either
    destroy data it does not own or remove a row the next corpus measurement puts back.
    But a list of 142 frames is a list you want to prune, and "I cannot do anything about
    this row" is not an answer. So the row goes away and the file does not.

    Reversible by construction: nothing is moved and nothing is measured again, a flag is
    set, and the list offers to show them again.
    """
    arm = (payload.get("arm") or "").strip()
    frame = (payload.get("frame") or "").strip()
    show = bool(payload.get("show"))
    if not frame:
        raise HTTPException(400, "which frame?")
    with _DATASET_LOCK:
        fp = os.path.join(OUT, "frames.json")
        if not os.path.exists(fp):
            raise HTTPException(404, "no dataset yet")
        with open(fp, encoding="utf-8") as fh:
            cur = json.load(fh)
        hit = False
        for r in cur:
            if r.get("arm") == arm and (frame == "*" or r.get("frame") == frame):
                hit = True
                if show:
                    r.pop("hidden", None)
                else:
                    r["hidden"] = True
        if not hit:
            raise HTTPException(404, f"no frame {frame!r} in {arm!r}")
        _write_json(fp, cur)
        _CACHE.clear()
    n_hidden = sum(1 for r in cur if r.get("arm") == arm and r.get("hidden"))
    return {"ok": True, "arm": arm, "frame": frame, "shown": show,
            "hidden_in_arm": n_hidden,
            "note": ("nothing was moved or deleted -- the row is out of the list and the "
                     "file is exactly where it was.")}


@app.post("/api/discard_edit")
def discard_edit(payload: dict = Body(...)):
    """Throw away the correction on a research frame and go back to the detector's mask.

    This is what "delete" means on a sem/* or txm row. The frame is not the app's to
    remove -- it is the pipeline's output and would return on the next corpus measurement
    anyway -- but the correction drawn on top of it IS the app's, and taking it off is a
    thing a reader needs to be able to do after a stroke goes wrong.

    The edit is moved to the trash like anything else, so a discarded correction is
    recoverable by hand. The research mask was never written to, so there is nothing to
    restore: removing the edit IS the restore.
    """
    import shutil
    arm = (payload.get("arm") or "").strip()
    frame = (payload.get("frame") or "").strip()
    if arm == "uploads":
        raise HTTPException(400, "an uploaded frame has no edit to discard -- delete the "
                                 "frame instead")
    if not frame or not SAFE_FRAME.match(frame):
        raise HTTPException(400, f"{frame!r} is not a frame name this will build a path from")
    src = _edit_of(arm, frame)
    if not src:
        raise HTTPException(404, f"{frame!r} has no correction on it in {arm!r}")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(_trash_dir(), f"{stamp}__edit__{arm.replace('/', '__')}__"
                                     f"{frame}_gated.png")
    with _DATASET_LOCK:
        shutil.move(src, dst)
        fp = os.path.join(OUT, "frames.json")
        if os.path.exists(fp):
            with open(fp, encoding="utf-8") as fh:
                cur = json.load(fh)
            for r in cur:
                if r.get("arm") == arm and r.get("frame") == frame:
                    r.pop("edited", None)
            _write_json(fp, cur)
        _CACHE.clear()
    # Measured back to what the detector said, so the numbers follow the pixels.
    out = remeasure(arm=arm, frame=frame)
    out["discarded"] = True
    out["trashed_to"] = os.path.basename(dst)
    out["note"] = (f"the correction on {frame} was moved to trash/ and the frame is back "
                   f"to the detector's own mask.")
    return out


@app.post("/api/delete_frame")
def delete_frame(payload: dict = Body(...)):
    """Remove one uploaded frame: its files to the trash, its rows from every dataset."""
    import shutil

    arm = (payload.get("arm") or "").strip()
    frame = (payload.get("frame") or "").strip()
    # EXACT EQUALITY, NOT startswith -- "uploadsX" must not be accepted -- and BEFORE
    # anything looks the frame up, so an unknown arm never reaches a path.
    if arm != "uploads":
        raise HTTPException(400, f"{arm!r} is not the uploads arm. The SEM and TXM arms are "
                                 f"research masks this app does not own and never writes "
                                 f"to; a frame removed from one would come back on the next "
                                 f"corpus measurement anyway.")
    if not frame or not SAFE_FRAME.match(frame):
        raise HTTPException(400, f"{frame!r} is not a frame name this will build a path from")

    with _DATASET_LOCK:
        frames = _load_quiet("frames") or []
        rec = next((f for f in frames
                    if f.get("arm") == "uploads" and f.get("frame") == frame), None)
        # THE RECORD IS THE AUTHORITY, not the filesystem. Requiring it to exist before a
        # single file is touched means a name that is not a frame cannot reach os.replace
        # whatever it is spelled like.
        if rec is None:
            raise HTTPException(404, f"there is no uploaded frame called {frame!r}")

        kids = _dependents_of(frame)
        if kids and not payload.get("with_dependents"):
            raise HTTPException(409,
                "%s was the source of %s. Deleting it would leave %s pointing at nothing: "
                "the lineage walk that refuses to compare a crop against its own parent "
                "would stop finding the overlap, with no error. Delete %s first, or pass "
                "with_dependents." % (
                    frame, ", ".join(f"{k['frame']} ({k['via']})" for k in kids),
                    "them" if len(kids) > 1 else "it",
                    "them" if len(kids) > 1 else "it"))

        # FILES FIRST, RECORDS SECOND. In the other order an autosave landing mid-delete
        # re-measures the surviving mask and writes the record straight back, so the delete
        # undoes itself and leaves a frame with no files.
        stamp = time.strftime("%Y%m%d-%H%M%S")
        tdir = _trash_dir()
        up_real = os.path.realpath(UPLOAD_DIR)
        moved = []
        for suf in UPLOAD_SUFFIXES:
            src = os.path.join(UPLOAD_DIR, frame + suf)
            # Belt and braces behind SAFE_FRAME: whatever the name, the file being moved
            # must actually live in the directory this app owns.
            if os.path.realpath(os.path.dirname(src)) != up_real:
                raise HTTPException(400, f"refusing to touch a path outside uploads: {src}")
            if os.path.exists(src):
                dst = os.path.join(tdir, f"{stamp}__{frame}{suf}")
                shutil.move(src, dst)
                moved.append(os.path.basename(dst))

        kept = [f for f in frames
                if not (f.get("arm") == "uploads" and f.get("frame") == frame)]
        _write_json(os.path.join(OUT, "frames.json"), kept)

        cp = os.path.join(OUT, "cracks.json")
        n_rows = 0
        gone_cracks = []
        if os.path.exists(cp):
            cr = json.load(open(cp))
            # BY THE PAIR, never by the frame alone: cracks.json is keyed on (arm, frame)
            # and a stem can exist in uploads AND in a research arm at the same time.
            keep, gone_cracks = [], []
            for c in cr:
                (gone_cracks if (c.get("arm") == "uploads"
                                 and c.get("frame") == frame) else keep).append(c)
            n_rows = len(gone_cracks)
            _write_json(cp, keep)

        # THE SCALE STORE IS KEYED BY BARE STEM WITH NO ARM, so clearing it would strip the
        # nm/px from a research frame that happens to share the name -- and every micrometre
        # column computed from it. Only clear when this stem belongs to nobody else.
        scale_cleared, saved_scale = False, None
        if not any(f.get("frame") == frame for f in kept):
            try:
                import sys as _sys
                _sys.path.insert(0, os.path.join(RES, "analysis"))
                import scale as _scale
                # Through set_user_scale, not by rewriting the file: scale.py caches the
                # whole dict in a module-level _USER, and a later unrelated set would dump
                # that stale copy and put this entry back.
                if _scale.nm_per_px(frame, "sem") or _scale.user_scales().get(frame):
                    saved_scale = _scale.user_scales().get(frame)
                    _scale.set_user_scale(frame, None)
                    scale_cleared = True
            except Exception:                           # noqa: BLE001 - never fail a delete
                pass

        # Saved groups resolve members by name at request time and nothing prunes them, so
        # a stale member silently shrinks a group and reports it only in a `missing` field
        # no screen renders.
        groups, pruned, gone_groups = _read_groups(), [], {}
        for name in list(groups):
            was = groups[name]
            groups[name] = [m for m in was
                            if not (m.get("arm") == "uploads" and m.get("frame") == frame)]
            if len(groups[name]) != len(was):
                pruned.append(name)
                # The WHOLE list, not just the removed member: a group that empties is
                # popped below, so putting one member back into a group that no longer
                # exists would resurrect it with a single row and silently drop the rest.
                gone_groups[name] = was
            if not groups[name]:
                groups.pop(name)
        if pruned:
            _write_json(_groups_path(), groups)

        # EVERYTHING THE DELETE TOOK, written beside the files it moved.
        #
        # Without this, putting a frame back means measuring the restored PNG again -- and
        # re-measuring is NOT the inverse of deleting. remeasure() reads the frame's prior
        # record for its modality, specimen and lineage, and the delete just removed that
        # record: a restored TXM crop would come back measured as SEM, under specimen
        # "unparsed", with cropped_from gone -- which is the field that lets its strokes
        # reach the parent and stops a group comparing it against the frame it was cut
        # from. The crack rows, the scale and the group memberships have no path back at
        # all. So the delete carries its own undo rather than leaving one to be inferred.
        record = {"frame": rec, "cracks": gone_cracks, "groups": gone_groups,
                  "scale": saved_scale, "files": moved}
        recname = f"{stamp}__{frame}.record.json"
        _write_json(os.path.join(tdir, recname), record)

        # _rebuild_uploads_specimen, not _rebuild_specimen: the generic one returns early
        # when a specimen has no frames left and leaves its card describing data that is
        # gone.
        _rebuild_uploads_specimen()
        _CACHE.clear()

    return {"ok": True, "frame": frame, "arm": "uploads",
            "files_trashed": moved, "trash_dir": _trash_dir(),
            "crack_rows_removed": n_rows,
            "scale_cleared": scale_cleared,
            "groups_pruned": pruned,
            "record": recname,
            # ORPHANED, not removed: nothing in this function deletes a dependent. The
            # old key named an action that never happened.
            "dependents_orphaned": [k["frame"] for k in kids] if kids else [],
            "note": (f"moved to {os.path.basename(_trash_dir())}/ in the app's data folder "
                     f"rather than deleted, so it can be put back by hand.")}


def _paste_region(arm, frame, box, blob):
    """Composite a crop-sized PNG into the frame's CURRENT mask and return the whole thing.

    The base is the mask as it stands right now -- the app's own edit if there is one,
    otherwise the frame's mask -- so successive crop saves accumulate instead of each one
    reverting the last. The research file is still never opened for writing; for a sem/*
    or txm frame the result is written to the edit store by the caller.

    Every dimension is checked rather than trusted. A crop that does not fit, or a PNG
    whose size disagrees with the box it claims to be, is refused: pasting it would move
    the strokes somewhere other than where they were drawn, and nothing downstream could
    tell that had happened.
    """
    import io
    import numpy as np
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None

    parts = str(box).split(",")
    if len(parts) != 4:
        raise HTTPException(400, f"box must be x,y,w,h -- got {box!r}")
    try:
        x, y, w, h = (int(v) for v in parts)
    except ValueError:
        raise HTTPException(400, f"box must be four integers -- got {box!r}")
    if w <= 0 or h <= 0 or x < 0 or y < 0:
        raise HTTPException(400, f"box {box!r} is not a region")

    base_p = _edit_of(arm, frame) or _mask_path(arm, frame)
    if not base_p or not os.path.exists(base_p):
        raise HTTPException(404, f"no mask on disk for {frame!r} in {arm!r} to paste into")
    with Image.open(base_p) as bim:
        base = np.array(bim.convert("L"))
    H, W = base.shape
    if x + w > W or y + h > H:
        raise HTTPException(409, f"box {x},{y},{w}x{h} runs outside the {W}x{H} mask")

    with Image.open(io.BytesIO(blob)) as pim:
        piece = np.array(pim.convert("L"))
    if piece.shape != (h, w):
        raise HTTPException(409, f"the painted region is {piece.shape[1]}x{piece.shape[0]} "
                                 f"but the box says {w}x{h}; it has been resampled, so the "
                                 f"strokes no longer line up")

    base[y:y + h, x:x + w] = piece
    out = io.BytesIO()
    Image.fromarray(base, mode="L").save(out, "PNG", optimize=True)
    return out.getvalue()


@app.post("/api/mask_edit")
async def mask_edit(arm: str = Query(...), frame: str = Query(...),
                    box: str | None = Query(None), file: UploadFile = File(...)):
    """Replace an UPLOADED frame's mask with an edited one, then re-measure it.

    WITH `box` ("x,y,w,h") THE UPLOAD IS A REGION, NOT THE WHOLE MASK, and it is pasted
    into the frame's current mask at that offset. That is what cropping means now: the
    crop restricts what you are LOOKING AT, and the strokes land on the frame you were
    already working on. It used to cut a new frame into Your images instead, from the
    autosave timer, so a crop you drew on for eight seconds appeared in the sidebar as a
    thing you had not asked to create -- against the user's standing rule that nothing
    may ever be created there except by their own click.

    This is the correct-and-measure half of the loop, built in, so it works in a downloaded
    copy. The detect and retrain halves cannot be: the model is pickled against the SEM
    repo's own interpreter, so they stay behind the Mark tab's hand-off. Painting on a mask
    needs no model, and correcting a mask is the step a researcher with their own data
    actually needs.

    UPLOADS ONLY, and this is a hard restriction rather than a default. The other arms read
    from the SEM repo's derived masks and the TXM export, which are irreplaceable research
    data this app has no business overwriting -- it is a measurement tool, and the one
    directory it owns is its own uploads folder.
    """
    # ANY FRAME CAN BE MARKED; NO RESEARCH MASK IS OVERWRITTEN.
    #
    # Editing used to be refused outright outside the uploads arm, which kept the derived
    # SEM masks and the TXM export safe and left marking as a hand-off to another program
    # on another port. Both can be true at once: an edit to a research frame is saved as a
    # COPY in the uploads arm, measured there, and the original file is never opened for
    # writing. The researcher marks anything in one window; the data this app does not own
    # is still data this app does not write.
    into_uploads = arm == "uploads"
    if into_uploads:
        dest = os.path.join(UPLOAD_DIR, f"{frame}_gated.png")
        if not os.path.exists(dest):
            raise HTTPException(404, f"no uploaded mask for {frame!r}")
        new_frame = frame
    else:
        # THE EDIT IS THIS FRAME, NOT A NEW ONE. It used to be filed in uploads as
        # "<frame>_marked", so correcting one image left two in the sidebar. It now goes
        # to the app's own edit store under the frame's own name and is served in the
        # mask's place, so the frame you corrected is the frame you come back to -- across
        # restarts. The research mask itself is still never opened for writing.
        src = _mask_path(arm, frame)
        if not src or not os.path.exists(src):
            raise HTTPException(404, f"no mask on disk for {frame!r} in {arm!r}")
        new_frame = frame
        dest = _edit_path(arm, frame)
        if not dest:
            raise HTTPException(400, f"refusing to build an edit path from {frame!r}")
        os.makedirs(os.path.dirname(dest), exist_ok=True)

    blob = await file.read()
    if not blob.startswith(b"\x89PNG"):
        raise HTTPException(400, "the edited mask must be a PNG")
    if len(blob) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"{len(blob)/1e6:.0f} MB is over the limit")

    if box is not None:
        blob = _paste_region(arm, frame, box, blob)

    # Write beside it and swap, so an interrupted save cannot leave a half-written mask
    # where a whole one used to be.
    tmp = dest + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(blob)
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(tmp) as im:
            im.verify()
    except Exception as e:
        os.remove(tmp)
        raise HTTPException(400, f"not a readable PNG: {type(e).__name__}: {e}")
    os.replace(tmp, dest)

    # MEASURED IN PLACE, UNDER ITS OWN NAME. The edit is this frame, so the record that
    # gets re-measured is this frame's -- not a new row in another arm. remeasure() reads
    # through /api/mask's own resolution order, so it measures the edit.
    out = remeasure(arm=arm, frame=new_frame)
    if not into_uploads:
        out["edited_in_place"] = True
        out["edit_path"] = dest
        with _DATASET_LOCK:
            fp = os.path.join(OUT, "frames.json")
            cur = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else []
            for r in cur:
                if r.get("arm") == arm and r.get("frame") == frame:
                    r["edited"] = True
            _write_json(fp, cur)
            _CACHE.clear()
    out["edited"] = True
    out["frame"] = new_frame
    return out


def _measure_into_uploads(mask_path, frame, source=None, specimen=None):
    """Create an uploads-arm record for a mask that is already on disk."""
    import sys as _sys
    _sys.path.insert(0, os.path.join(RES, "analysis"))
    from measure import measure_path

    # WHAT A RE-MEASURE MUST NOT FORGET. This replaces the frame's whole record with a
    # freshly measured one, so every field that is a property of the frame's ORIGIN rather
    # than of its pixels was being dropped the first time anyone painted on it:
    #
    #   cropped_from  -- the lineage. Losing it detaches a crop from its parent, which
    #                    breaks sending strokes back AND silently disables the guard that
    #                    refuses to compare a crop against the frame it was cut from. The
    #                    guard would simply stop finding the overlap, with no error.
    #   has_original  -- whether a micrograph sits behind it, so the editor stops loading
    #                    the background the moment you paint on the crop.
    #   modality      -- and it was hardcoded "sem" below, so painting a crop of a TXM
    #                    frame re-measured it under SEM settings.
    prior = next((f for f in (_load_quiet("frames") or [])
                  if f.get("arm") == "uploads" and f.get("frame") == frame), {}) or {}
    modality = prior.get("modality") or "sem"
    rows, summ = measure_path(mask_path, modality, stem=frame)
    summ["arm"] = "uploads"
    summ["specimen"] = specimen or prior.get("specimen") or "uploaded"
    summ["source_filename"] = f"{frame}_gated.png"
    for carried in ("cropped_from", "has_original"):
        if carried in prior:
            summ[carried] = prior[carried]
    # ARM_HAS_ORIGINALS says the uploads arm has none, which is right for an uploaded mask
    # and wrong for a copy of a research frame. The editor consults the frame's own flag
    # when the arm's is false, so without this the copy renders black-and-white with its
    # micrograph sitting fetchable on disk.
    if source and "/" in source:
        _parm, _pframe = source.rsplit("/", 1)
        if _original_path(_parm, _pframe):
            summ["has_original"] = True
    if prior.get("scale_known") and prior.get("nm_per_px") and not summ.get("nm_per_px"):
        summ["nm_per_px"] = prior["nm_per_px"]
        summ["scale_known"] = True
    if source:
        summ["copied_from"] = source
    for r in rows:
        r["frame"] = summ["frame"]; r["arm"] = "uploads"
        r["specimen"] = summ["specimen"]
    with _DATASET_LOCK:
        for fname, new_rows in (("frames", [summ]), ("cracks", rows)):
            fp = os.path.join(OUT, f"{fname}.json")
            cur = json.load(open(fp)) if os.path.exists(fp) else []
            kept = [x for x in cur
                    if not (x.get("arm") == "uploads" and x.get("frame") == summ["frame"])]
            _write_json(fp, kept + new_rows)
        _CACHE.clear()
        _rebuild_uploads_specimen()
    _CACHE.clear()


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

    # AN EDIT IS WHAT THIS FRAME NOW IS, so it is what gets measured. Same resolution
    # order as /api/mask: without it the numbers would describe the detector's original
    # while the canvas showed the correction, which is the two-sources-of-truth failure
    # this app has been bitten by before.
    path = _edit_of(arm, frame) or _mask_path(arm, frame)
    if not path:
        raise HTTPException(400, f"no mask location known for arm {arm!r}")
    if not os.path.exists(path):
        raise HTTPException(404, f"no mask on disk at {path}")

    prior = next((f for f in (_load_quiet("frames") or [])
                  if f.get("arm") == arm and f.get("frame") == frame), None)
    # THE ARM DOES NOT DETERMINE THE MODALITY FOR AN UPLOAD. Every uploads frame was
    # measured as "sem" by this rule, including a crop of a TXM frame, which carries its
    # parent's modality on its own record. Ask the record first and fall back to the arm.
    modality = (prior or {}).get("modality") or ("txm" if arm == "txm" else "sem")
    from measure import measure_path
    try:
        rows, summ = measure_path(path, modality, stem=frame)
    except Exception as e:
        raise HTTPException(500, f"measurement failed: {type(e).__name__}: {e}")

    summ["arm"] = arm
    summ["specimen"] = (prior or {}).get("specimen") or "unparsed"
    # CARRY THE IDENTITY FIELDS THROUGH. measure_path rebuilds the summary from the mask
    # alone, so anything the record knew about WHERE IT CAME FROM was dropped on every
    # re-measure -- and source_filename has exactly one consumer, the upload collision
    # guard, so nothing else flagged the loss. That guard reads
    # `existing.get("source_filename") not in (None, name)`, so a missing value reads as
    # "no prior filename" and a genuinely different file that canonicalises to the same
    # frame is then allowed to overwrite it. Measured: upload weld.png, upload a different
    # weld_mask.png -> correctly refused 409. Re-measure once, upload weld_mask.png again
    # -> 200, and the frame is replaced (area_fraction 0.117215 -> 0.040319, 185 cracks ->
    # 75, the PNG on disk overwritten). mask_edit and set_scale both call remeasure, so
    # the guard was off after every correction -- the exact moment the mask is worth most.
    #
    # cropped_from and has_original join that list for the same reason and with a sharper
    # consequence. A crop's lineage is what lets its strokes be sent back to the parent's
    # correction mask, and what lets a group comparison REFUSE to put a crop against the
    # frame it was cut from. Dropping it on re-measure meant the lineage survived exactly
    # until the moment the user painted on the crop -- so the guard stopped finding the
    # overlap with no error, and the strokes became unsendable, both silently, at the one
    # moment the crop was worth anything.
    #
    # "edited" joins them for a third reason, found by a restore test. mask_edit sets the
    # flag AFTER this function runs, so it survived there by luck of ordering -- but every
    # OTHER caller re-measures an already-edited frame and dropped it: setting a scale on
    # a corrected research frame silently cleared the flag, and the flag is what makes the
    # sidebar offer "discard your correction" instead of "hide this row", and what marks
    # the row as corrected at all. discard_edit pops the key before it re-measures rather
    # than setting it False, so a genuine discard is still not carried back.
    for k in ("source_filename", "was_segmented_here", "copied_from",
              "cropped_from", "has_original", "edited", "collection"):
        if prior and prior.get(k) is not None and summ.get(k) is None:
            summ[k] = prior[k]
    for r in rows:
        r["frame"] = summ["frame"]
        r["arm"] = arm
        r["specimen"] = summ["specimen"]

    # Replace exactly this frame's records. Everything else is left byte-for-byte alone:
    # a re-measure of one frame must never be able to disturb another.
    with _DATASET_LOCK:
        for fname, new_rows in (("frames", [summ]), ("cracks", rows)):
            fp = os.path.join(OUT, f"{fname}.json")
            cur = json.load(open(fp)) if os.path.exists(fp) else []
            kept = [x for x in cur
                    if not (x.get("arm") == arm and x.get("frame") == summ["frame"])]
            _write_json(fp, kept + new_rows)
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
    pair = specimen_stats.pair_for(arm)
    rec["arm_sensitivity"] = (specimen_stats.paired_arm_ratio(by_arm, specimen, *pair)
                              if pair else None)
    others = []
    if os.path.exists(sp):
        try:
            others = [r for r in json.load(open(sp))
                      if not (r.get("arm") == arm and r.get("specimen") == specimen)]
        except Exception:
            others = []
    _write_json(sp, others + [rec])


@app.get("/api/readout")
def readout(arm: str = Query(...), specimen: str | None = None, frame: str | None = None):
    """The sentences, not the numbers. Computed server-side from the SAME dataset the tables
    read, so a statement can never disagree with the figure beside it."""
    import sys as _sys
    _sys.path.insert(0, os.path.join(RES, "analysis"))
    import conclusions

    frames = [f for f in _load("frames") if f.get("arm") == arm]
    out = {"arm": arm, "frame": [], "specimen": [], "refusals": conclusions.REFUSALS}

    # WHAT THE WHOLE ARM SUPPORTS. The comparison view showed fourteen specimens by seven
    # columns and left the reading to the reader; these are the statements that are true
    # of the set rather than of any row in it.
    try:
        out["arm_statements"] = conclusions.for_arm(
            [r for r in _load("specimens") if r.get("arm") == arm], frames)
    except HTTPException:
        out["arm_statements"] = []

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
    # `v[1] or v[3]`: the percent fields carry their scale in slot 2 and their "%" in slot
    # 4, so reporting only v[1] told the picker those fields were unitless while the figure
    # drew them multiplied by 100. The picker and the figure now name the same unit.
    return {"fields": [{"key": k, "label": v[0], "unit": v[1] or v[3],
                        "needs_scale": k in F.NEEDS_SCALE}
                       for k, v in F.FIELDS.items()],
            "kinds": list(F.KINDS)}


@app.get("/api/figure/says")
def figure_says(arm: str = Query(...), kind: str = Query("box_by_specimen"),
                x: str | None = None, y: str | None = None,
                min_frames: int = 3, include_thin: bool = False):
    """What the figure on screen shows, computed from the points it drew.

    A separate call from figure.svg because that one returns image bytes. Same parameters,
    same build, so the statements and the picture cannot disagree.
    """
    import sys as _sys
    _sys.path.insert(0, os.path.join(RES, "analysis"))
    import conclusions
    from . import figures as F
    try:
        out = F.build(_load("frames"), arm, kind, x, y, min_frames, include_thin)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"statements": conclusions.for_figure(
        kind, x, y, out.get("rows") or [], label_of=lambda k: F.FIELDS[k][0])}


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
    # HEALTH REPORTS THE RESOLUTION; IT DOES NOT TRIGGER IT.
    #
    # provenance() works out which measurement implementation is in use, and doing so
    # IMPORTS the SEM repo's extended_features.py. That repo lives under ~/Desktop, which
    # macOS gates behind a per-app permission -- so inside the packaged app, launched the
    # way a user launches it, that read blocks. Measured: health answered in 5.9 ms when
    # the same binary was started from a terminal (which inherits the terminal's own
    # grant) and never answered at all under `open -a`, past eleven minutes, while every
    # other endpoint replied in milliseconds. The page fetches health on load, so the
    # capabilities list, the configured paths and the version badge all waited on it.
    #
    # Resolution happens where it belongs: on the first measurement, which needs the
    # implementation anyway and is already a long request. Health reads the cached answer
    # if there is one and says so if there is not.
    #
    # NOT ON A BACKGROUND THREAD. That was tried: importing skimage off-thread while a
    # request imports it on another gives "partially initialized module
    # 'skimage.morphology' has no attribute 'skeletonize'", and 49 tests failed with
    # measurements returning 500.
    impl = {"source": None, "pending": True,
            "note": "not yet determined -- it is resolved by the first measurement"}
    try:
        import sys as _sys
        if os.path.join(RES, "analysis") not in _sys.path:
            _sys.path.insert(0, os.path.join(RES, "analysis"))
        mod = _sys.modules.get("shared_impl")
        if mod is not None and getattr(mod, "_STATE", None):
            impl = mod.provenance()
    except Exception as e:                              # noqa: BLE001
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
        "version": _app_version(),
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
def set_config(sem_repo: str | None = None, txm_export: str | None = None,
               txm_export_machine: str | None = None, txm_images: str | None = None):
    """Point the app at the repos. Validated before it is saved, so a wrong folder is
    rejected here with the reason instead of accepted and failing later.

    txm_export_machine and txm_images are here because paths.py READS both out of the
    config -- _resolved("txm_export_machine", ...) and _resolved("txm_images", ...) -- and
    until now nothing could write either. They resolved through the data/ dev symlinks on
    this machine and were unreachable anywhere else, so an installed copy could not reach
    the txm/machine arm at all and could not show a TXM original. A key with a reader and
    no writer is dead on every machine except the one it was developed on."""
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
    for name, val in (("txm_export_machine", txm_export_machine), ("txm_images", txm_images)):
        if val is not None and not os.path.isdir(os.path.expanduser(val.strip())):
            raise HTTPException(400, f"{name}: that folder does not exist")
    P.set_config(sem_repo=sem_repo, txm_export=txm_export,
                 txm_export_machine=(os.path.expanduser(txm_export_machine.strip())
                                     if txm_export_machine is not None else None),
                 txm_images=(os.path.expanduser(txm_images.strip())
                             if txm_images is not None else None))
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
    # NO-STORE, BECAUSE THIS APP REPLACES ITSELF IN PLACE.
    #
    # The script tag carries a cache-busting token and the static mount sends an ETag, so
    # the JS is safe. The HTML was not: it went out with no Cache-Control and no validator
    # at all, which leaves WKWebView free to heuristically cache it -- and a cached
    # index.html pins BOTH the old markup AND the old `?v=` token, so an install that
    # replaced the whole bundle could still render the previous version's interface
    # against the new server. The user would be looking at 1.36.0 while /api/health said
    # 1.37.0, and every UI change would read as "you did not fix it".
    #
    # One document per launch is nothing to re-fetch; the cost of getting this wrong is
    # debugging a release the user never actually ran.
    return HTMLResponse(html, headers={"Cache-Control": "no-store, must-revalidate",
                                       "Pragma": "no-cache"})


# Mounted last so it cannot shadow /api/*.
app.mount("/static", StaticFiles(directory=os.path.join(RES, "app", "static")), name="static")
