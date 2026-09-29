#!/usr/bin/env python3
"""Physical scale per frame, or None. Never a guess.

Any area, length or width in physical units needs nm/px for THAT frame. The SEM corpus spans
a 249x magnification range, so a single pooled number in micrometres is meaningless unless
every frame carried its own scale -- and 71 of the 151 originals have no instrument metadata
at all. So this returns None rather than a default, and the callers are expected to keep
pixel units alongside physical ones and to refuse to pool across unknown scales.

Sources, in the order they are trusted:
  1. the FEI/Thermo metadata block inside the TIFF (exact; the 2026-09-15 batch only)
  2. crack_export/analysis/fei_metadata_260915.csv, the extracted form of the same thing
  3. the TXM tile-geometry constant, for TXM frames
Databar OCR is deliberately NOT used here: it exists in the SEM repo for the older frames and
is a separate, noisier instrument. Mixing it in silently would make two populations look like
one.
"""
import csv
import math
import os
import sys as _sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
_sys.path.insert(0, REPO)
from app import paths as _P   # noqa: E402

#: Anchored by tile geometry, not by a databar: 9x5 tiles of a 30 um window at 0.35 overlap.
TXM_NM_PER_PX = 29.24

_FEI = {}

#: Where a user-supplied nm/px is kept. Per frame, in the app's own writable data
#: directory, so it survives a re-measure and never touches the source images.
_USER = {}
_USER_LOADED = [False]


def _user_path():
    from app import paths as _P
    return os.path.join(_P.DATA, "user_scale.json")


def user_scales():
    if not _USER_LOADED[0]:
        import json
        try:
            _USER.update(json.load(open(_user_path())))
        except Exception:
            pass
        _USER_LOADED[0] = True
    return _USER


def set_user_scale(stem, nm_per_px):
    """Record nm/px for one frame, or clear it with None."""
    import json
    from app import paths as _P
    user_scales()
    if nm_per_px is None:
        _USER.pop(stem, None)
    else:
        v = float(nm_per_px)
        # isfinite, not just > 0. float("inf") passes `v > 0`, and every physical column
        # is then computed by multiplying a pixel count by it -- so json.dump wrote bare
        # `Infinity` into frames.json, cracks.json and specimens.json (12, 5 and 4
        # occurrences). Those files stop being JSON: JSON.parse and R's jsonlite reject
        # them, Python's json is unusually permissive and accepts them, which is exactly
        # why it went unnoticed. The three arm endpoints then returned 500 across restarts
        # with no route back through the UI, because the frame could no longer be selected
        # to clear its scale. A finite-but-huge value was already handled correctly
        # (1e300 gives a clean OverflowError and leaves the files intact); only the
        # non-finite case got through. _write_json's allow_nan=False is the second line of
        # defence; this is the first, and it is the one that gives a usable message.
        if not math.isfinite(v) or v <= 0:
            raise ValueError("nm/px must be a finite number greater than zero")
        _USER[stem] = v
    _P.ensure_dirs()
    tmp = _user_path() + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(_USER, fh, indent=2)
    os.replace(tmp, _user_path())
    return _USER.get(stem)


# ---------------------------------------------------------------------------------------
#: The FEI/Thermo block is appended AFTER the pixel data, so it lives in the file's tail.
#: 400 kB is far more than any block observed (~9 kB) and avoids reading 25 MB per frame.
_FEI_TAIL = 400_000


def from_tiff(path):
    """nm/px from the FEI/Thermo metadata block inside a TIFF, or None.

    This module's docstring has listed this as trust-source 1 since it was written and it
    was implemented nowhere: nm_per_px() could only return the TXM constant or look up the
    author's own extracted CSV, keyed by the author's own frame stems. So every physical
    quantity -- P10, P20, P21, S_V, MCL, TCL, spacing, area analysed -- was permanently
    null for every user who was not the author, and the app silently degraded to pixels.

    Parsed from the raw tail with the standard library, the same way the SEM repo's
    crack_export/tools/fei_metadata.py does it, so an uploaded .tif carries its own scale
    without that repo being installed.
    """
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, size - _FEI_TAIL))
            txt = fh.read().decode("latin-1")
    except OSError:
        return None
    start = txt.find("[User]")
    if start < 0:
        start = txt.find("[System]")
    if start < 0:
        return None
    for line in txt[start:].splitlines():
        line = line.strip()
        if line.startswith("PixelWidth="):
            try:
                metres = float(line.split("=", 1)[1].strip())
            except ValueError:
                return None
            # PixelWidth is metres per pixel; 1e9 nm in a metre.
            return round(metres * 1e9, 4) if metres > 0 else None
    return None


def _load_fei():
    if _FEI:
        return _FEI
    # The scale table lives in the SEM repo. Without one configured there is no table, so
    # every SEM frame reports scale_known=false -- which is the honest answer, not an
    # excuse to fall back to a default nm/px.
    sem = _P.sem_repo()
    if not sem:
        return _FEI
    p = os.path.join(sem, "crack_export", "analysis", "fei_metadata_260915.csv")
    if not os.path.exists(p):
        return _FEI
    for r in csv.DictReader(open(p)):
        try:
            v = float(r.get("nm_per_px") or "")
        except ValueError:
            continue
        _FEI[os.path.splitext(r["frame"])[0]] = v
    return _FEI


def scale_source(stem, modality="sem"):
    """Which source supplied this frame's scale, so the number is never anonymous."""
    if stem in user_scales():
        return "set by you"
    if modality == "txm":
        return "TXM tile geometry (constant)"
    if _load_fei().get(stem) is not None:
        return "FEI metadata extracted from the TIFF"
    return None


def nm_per_px(stem, modality="sem"):
    """nm per pixel for this frame, or None when it is not established.

    A VALUE THE USER SET WINS, including over the TXM constant. They may know the image was
    cropped, rescaled, or came off a different instrument than its name suggests, and the
    app cannot. scale_source() reports which source answered so the number is never
    anonymous.
    """
    u = user_scales().get(stem)
    if u:
        return u
    if modality == "txm":
        return TXM_NM_PER_PX
    return _load_fei().get(stem)


def coverage():
    """How many frames have a scale. Reported so a reader knows what fraction is physical."""
    return len(_load_fei())


# ---------------------------------------------------------------------------------------
# TXM specimen grouping.
#
# The SEM repo's specimen_key() returns None for any name outside its own grammar, and TXM
# stems are outside it. That sentinel is deliberate there -- it prevents each unparsed frame
# becoming its own "specimen" and inflating the apparent sample size -- but used for TXM it
# does the opposite harm: all 71 frames collapse into ONE specimen, and any per-specimen
# statistic then averages four different materials together.
#
# TXM stems look like Average_mosaic_<date>_<specimen>_<condition/position>_idx...:
#     Average_mosaic_260618_B2_333_75_um_zoom_...        -> 260618_B2
#     Average_mosaic_260619_HC_316L_fatigue_200_cycles_  -> 260619_HC_316L
#     Average_mosaic_260620_wrought_316L_fatigue_0_...   -> 260620_wrought_316L
# Case is not meaningful in the specimen field (b2 and B2 are the same block), so it is
# normalised; the date IS meaningful and is kept, because the same block imaged on two days is
# two sessions.
import re as _re

_TXM = _re.compile(
    r"^Average_mosaic_(?P<date>\d{6})_"
    r"(?P<spec>HC_316L|wrought_316L|[A-Za-z]\d+)",
    _re.IGNORECASE)


def txm_specimen_key(stem):
    """Specimen for a TXM frame, or None when the name does not parse."""
    m = _TXM.match(stem)
    if not m:
        return None
    return f"{m.group('date')}_{m.group('spec').lower()}"
