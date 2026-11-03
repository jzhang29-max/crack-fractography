#!/usr/bin/env python3
"""Assemble the publishable dataset folder: this laboratory's b2/b3 SEM and TXM frames
with their hand annotations, plus the public Inconel 718 collection, in one tree.

    <sem-crack-detector>/.venv/bin/python -B tools/build_release.py
    <sem-crack-detector>/.venv/bin/python -B tools/build_release.py --out /tmp/ds --skip-zenodo

WHAT IS AND IS NOT COMMITTED. This file is. The tree it writes is not: `release/` is in
.gitignore, because the output is several gigabytes of image data and, in the Inconel
subtree, other people's redistributed collections. The BUILDER is the reproducible
artifact. Re-running it against the same three sources and the same Zenodo record
reproduces the tree byte for byte, and it is idempotent: every output has a fixed path,
nothing is appended to, and a second run overwrites rather than duplicates.

THE SOURCES ARE READ-ONLY. `sem-crack-detector` and `TXM_Crack_Detection_Pipeline` are
archived and public. Nothing here opens a file in either of them for writing. The
hand-painted correction masks in particular are irreplaceable: they are copied out, never
touched.

-------------------------------------------------------------------------------------
THE FOUR PAINT STATES. The single thing most easily got wrong about this data.

    0  unreviewed  -- nobody looked. EXCLUDED FROM EVERY DENOMINATOR.
    1  crack       -- a human painted crack here.
    2  not-crack   -- a human painted an explicit not-crack verdict here.
    3  not-crack by erasure -- a human erased a machine mark here. An erase is a
                     not-crack VERDICT, not the absence of one, and it counts as a
                     refereed negative exactly like state 2.

Collapsing 0 into not-crack is the error that once turned a precision of 0.99 into 0.29
in this project. All four values are preserved exactly in the published masks, and
`loader.py` hands out `crack`, `not_crack` and `reviewed` so that a user of this dataset
never has to decide what 0 means.

-------------------------------------------------------------------------------------
SHAPE AGREEMENT. A published annotation that does not line up with its image is worse
than no annotation. Of the 48 SEM correction masks in the source repository, 12 match
their original exactly, 24 are exactly 280 rows shorter (the instrument databar, which
the uncropped originals still carry and the painting tool cropped off), 6 are 140 rows
shorter (the same databar on a half-resolution frame), and 6 line up with neither.

This builder does not guess an offset and it does not silently crop. It resolves the
crop with `detect_cracks.find_field_of_view` -- THIS PROJECT'S OWN field-of-view finder,
the same call `analysis/research/improve/overlap_means_sem_txm.py` makes -- and then
requires the resolved crop to match the mask EXACTLY. The resolved box is written into
`frames.json` and `metadata.csv` as four explicit numbers, so the published alignment is
a recorded fact and the shipped `loader.py` needs no field-of-view finder of its own.
Any frame the box does not resolve is reported, marked `shape_status=unresolved`, and
refused by the loader. A frame whose relation changes from the one recorded in
EXPECTED_ALIGNMENT below fails the build.

-------------------------------------------------------------------------------------
SCALE. The user asked for "a scale bar on everything". It cannot honestly be given for
everything, and this builder does not invent one.

  SEM, 2026-06-22 session: recovered from the instrument databar that survives in the
    uncropped originals, by `analysis/research/improve/sem_databar_scale.py`, which is
    already written and committed. Its output, docs/figures/sem_databar_scale.json, is
    read here. It covers 7 of the 23 b2/b3 frames.

  SEM, 2026-07-08 session: fifteen of the sixteen frames were re-saved by tifffile and
    carry no scale of any kind -- every TIFF tag was dumped to check (see SCALE NOTES in
    the generated README). They get nm_per_px = null and scale_source = "none". No value
    is carried over from the other session: the two were acquired at different
    magnifications, 42.2 and 28.1 and 13.5 nm/px against 844.6.

    The SIXTEENTH, 260708_316_H_b2_front_CBS_001, DOES carry a databar, and this builder
    recovers it. The file is 2188 rows where the field of view is 2048: the 140 rows
    underneath are the instrument panel at half resolution. `sem_databar_scale.py`
    misses it because its FOV_ROWS constant is hard-coded to 4096, so the frame fails its
    `h <= FOV_ROWS` test and is written off as "saved already cropped". The recovery here
    is that module's own two-route method, at the same 1% tolerance: the drawn bar's
    annotation over the measured tick span, controlled against the printed horizontal
    field width. Both fields were read off the panel and are transcribed in SEM_DATABAR_140.

  TXM: 29.24 nm/px on every frame. This is NOT an instrument header value. It is derived
    from operator-supplied mosaic geometry and is recorded with that provenance string,
    never as metadata.

-------------------------------------------------------------------------------------
THE PUBLIC COLLECTION. Zenodo record 23045328 is downloaded from the Zenodo API, its
bytes checked against the md5 the API declares, and only its Inconel 718 folders are
extracted. The record's identity is verified before anything is written: the DOI, the
licence, and the presence of an Inconel 718 class with both images and masks. If any of
those fails the build stops and reports. Nothing is substituted.

The record is CC BY 4.0, but its own directory names show it re-publishes at least three
upstream collections, and one of those is NC-ND. `LICENSING.md` in the output states the
facts; the decision to publish that subtree is the author's, and this builder makes it
possible rather than making it for them.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sys
import textwrap
import time
import urllib.error
import urllib.request
import warnings
import zipfile
from datetime import datetime, timezone

warnings.filterwarnings("ignore")
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))

import numpy as np                                                       # noqa: E402
import tifffile                                                          # noqa: E402
from PIL import Image, ImageDraw, ImageFont                              # noqa: E402

import _paths                                                            # noqa: E402

Image.MAX_IMAGE_PIXELS = None

SEM_REPO = _paths.SEM_REPO
TXM_REPO = _paths.TXM_REPO
SEM_ORIG = os.path.join(SEM_REPO, "original")
SEM_PAINT = os.path.join(SEM_REPO, "interior_active_learning", "paint")
TXM_IMAGES = os.path.join(TXM_REPO, "images")
TXM_CORR = os.path.join(TXM_REPO, "paint", "corrections")
DATABAR_SCALE_JSON = os.path.join(REPO, "docs", "figures", "sem_databar_scale.json")
OVERLAP_MODULE = os.path.join(REPO, "analysis", "research", "improve",
                              "overlap_means_sem_txm.py")

DATASET_NAME = "crack-fractography-dataset-v1"
DEFAULT_OUT = os.path.join(REPO, "release", DATASET_NAME)

#: The specimen series this release covers, in both microscopies.
SCOPE = ("b2", "b3")

#: TXM pixel size, and the provenance it must always be reported with. Weaker than an
#: instrument databar, and said so every time it is written down.
TXM_NM_PER_PX = 29.24
TXM_SCALE_SOURCE = "derived_mosaic_geometry"
TXM_SCALE_NOTE = (
    "derived from operator-supplied mosaic geometry, not an instrument header: 9 x 5 "
    "tiles of a 30 um viewing window at 0.35 overlap, giving 186.0 x 108.0 um over a "
    "6367 x 3691 px mosaic, isotropic to 0.2%. The window and the overlap are operator "
    "statements and have not been confirmed against an acquisition record; every length "
    "in nanometres scales with them, every ratio does not."
)

#: The 140-row databar on the one 2026-07-08 frame that kept it. Transcribed from the
#: panel, which this builder also writes to evidence/ so the transcription is auditable
#: against the pixels rather than taken on trust. The tick SPAN is measured, never read.
SEM_DATABAR_140 = {
    "260708_316_H_b2_front_CBS_001": {
        "fov_rows": 2048, "databar_rows": 140, "tick_rows": (1, 45), "tick_fill": 0.80,
        "bar_um": 1000.0, "hfw_um": 2590.0,
        "panel": "7/8/2026 4:47:49 PM | HV 20.00 kV | curr 13 nA | WD 8.0 mm | "
                 "HFW 2.59 mm | use case Standard | det CBS | 1 mm bar | Apreo",
    },
}
#: How far the drawn bar and the printed field width may disagree before this refuses to
#: emit a number. Same value as sem_databar_scale.py, deliberately.
SEM_SCALE_TOLERANCE = 0.01

#: Instrument and detector, per acquisition session, with where each came from. The
#: 2026-07-08 session has exactly one frame that kept its panel; the instrument for the
#: other fifteen is read off THAT panel and the source string says so rather than
#: pretending each file carried it.
SESSIONS = {
    "260622": {
        "date": "2026-06-22",
        "instrument": "Thermo Fisher Apreo",
        "detector": "CBS",
        "beam": "20.00 kV, 13 nA, WD 8.0 mm",
        "source": "read from the instrument databar burned into each of these frames",
    },
    "260708": {
        "date": "2026-07-08",
        "instrument": "Thermo Fisher Apreo",
        "detector": "CBS",
        "beam": "20.00 kV, 13 nA, WD 8.0 mm",
        "source": "read from the databar of 260708_316_H_b2_front_CBS_001, the only "
                  "frame of this session that was not saved already cropped; the other "
                  "fifteen files carry no instrument metadata at all",
    },
}

#: Every SEM frame/mask relation this build has seen and checked, as
#: frame -> (image rows, image cols, mask rows, mask cols). A frame whose shapes differ
#: from these fails the build rather than being quietly re-resolved: the point of the
#: check is to notice when the source data changes under it, and a rule that re-derives
#: the answer every time can never notice anything.
EXPECTED_ALIGNMENT = {
    "260622_316_H_b2_back_CBS_01":   (4376, 6144, 4096, 6144),
    "260622_316_H_b2_front_CBS_01":  (4376, 6144, 4096, 6144),
    "260622_316_H_b2_front_CBS_03":  (4376, 6144, 4096, 6144),
    "260622_316_H_b2_front_CBS_04":  (4376, 6144, 4096, 6144),
    "260708_316_H_b2_front_CBS_001": (2188, 3072, 1490, 1490),
    "260708_316_H_b2_front_CBS_002": (2044, 3067, 2044, 3067),
    "260708_316_H_b2_front_CBS_003": (2044, 3068, 2044, 3068),
    "260708_316_H_b2_front_CBS_004": (2045, 3072, 2045, 3072),
    "260708_316_H_b2_front_CBS_005": (4093, 6139, 4091, 6139),
    "260708_316_H_b2_front_CBS_006": (2044, 3071, 2044, 3071),
    "260708_316_H_b2_front_CBS_007": (2047, 3071, 2047, 3071),
    "260708_316_H_b2_front_CBS_008": (2045, 3072, 2045, 3072),
    "260708_316_H_b2_front_CBS_009": (2038, 3072, 2038, 3072),
    "260708_316_H_b2_front_CBS_010": (2037, 3072, 2037, 3072),
    "260708_316_H_b2_front_CBS_011": (2041, 3072, 2041, 3072),
    "260708_316_H_b2_front_CBS_012": (2038, 3072, 1903, 3072),
    "260708_316_H_b2_front_CBS_013": (2046, 3072, 2005, 3072),
    "260708_316_H_b2_front_CBS_014": (2045, 3072, 2045, 3072),
    "260708_316_H_b2_front_CBS_015": (4092, 6144, 4092, 6144),
    "260708_316_H_b2_front_CBS_016": (4090, 6144, 4090, 6144),
}

#: A frame needs this many pixels of a verdict before a score against that verdict means
#: anything, and an F1 needs both. The same threshold the published tables use
#: (analysis/research/improve/overlap_means_sem_txm.py, MIN_PX), repeated in the shipped
#: score.py so the dataset and the paper agree about which frames are scoreable.
MIN_VERDICT_PX = 200

ZENODO_RECORD = "23045328"
ZENODO_API = f"https://zenodo.org/api/records/{ZENODO_RECORD}"
ZENODO_EXPECT_DOI = f"10.5281/zenodo.{ZENODO_RECORD}"
ZENODO_EXPECT_LICENCE = "cc-by-4.0"
#: What makes this record "the Inconel 718 collection". If no member path matches, the
#: record is not what the ID is being used for here and the build stops.
INCONEL_RE = re.compile(r"(^|/)inconel ?718", re.IGNORECASE)
#: Only image data is taken out of the archives. The deposit also carries the depositor's
#: own working scripts (`delete.py`, `match.py`) next to the image folders; those are
#: somebody else's code, they are not data, and unpacking executable files out of a
#: downloaded archive into a folder that is about to be published is not something to do
#: by accident. They are counted and named in checks.json, and left in the zip.
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")

PREVIEW_MAX_SIDE = 1600
CRACK_RGB = (0, 220, 60)
NOTCRACK_RGB = (235, 40, 40)

LOG: list[str] = []


def say(msg=""):
    print(msg, flush=True)
    LOG.append(msg)


def die(msg):
    say("")
    say("=" * 90)
    say("BUILD STOPPED")
    say("=" * 90)
    for line in textwrap.wrap(msg, 88):
        say(line)
    sys.exit(2)


# ======================================================================= small utilities
def sha256_file(path, _buf=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(_buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def md5_file(path, _buf=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(_buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def tree_bytes(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            p = os.path.join(root, f)
            if os.path.isfile(p) and not os.path.islink(p):
                total += os.path.getsize(p)
    return total


def human(n):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:,.1f} {unit}" if unit != "B" else f"{n:,} B"
        n /= 1024.0


def copy_verbatim(src, dst):
    """Byte-for-byte copy, skipped when the destination is already that file.

    The skip is what makes a re-run cheap; it is a size-and-digest comparison, not an
    mtime one, because an mtime comparison would silently keep a destination that had
    been edited in place.
    """
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
        if sha256_file(dst) == sha256_file(src):
            return False
    shutil.copyfile(src, dst)
    return True


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


# ================================================================= the group classifier
def load_txm_group():
    """`txm_group()` out of overlap_means_sem_txm.py, by reading that file -- not a copy.

    THERE IS DELIBERATELY NO SECOND RULE HERE. The groups this release is scoped to are
    the groups the paper already reports, so the scope cannot disagree with the tables
    beside it. The function is lifted out with `ast` rather than by importing the module,
    because importing it installs detector overrides and pulls three modules out of the
    archived SEM repository, none of which this builder needs. The exact source text that
    was executed is recorded in checks.json, so a reader can see the rule rather than
    trust this sentence.
    """
    src = open(OVERLAP_MODULE, encoding="utf-8").read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "txm_group":
            text = ast.get_source_segment(src, node)
            ns: dict = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]),
                         OVERLAP_MODULE, "exec"), ns)
            return ns["txm_group"], text
    die(f"txm_group() was not found in {os.path.relpath(OVERLAP_MODULE, REPO)}. The "
        f"release scope is defined by that function and this builder will not invent a "
        f"second rule for it.")


# ============================================================ field of view, SEM masking
def sem_fov_box(stem):
    """(row0, col0, row1, col1) of the field of view, from this project's own finder.

    The call is exactly the one `overlap_means_sem_txm.sem_frames()` makes: percentile
    stretch with the frame's own contrast settings, then `find_field_of_view`. It is made
    HERE, at build time, so the published tree carries four numbers instead of a
    dependency on the archived repository.
    """
    from skimage import exposure
    raw = tifffile.imread(os.path.join(SEM_ORIG, stem + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    ck = _sem_contrast_kwargs(stem)
    lo, hi = np.percentile(raw, [ck["low_pct"], ck["high_pct"]])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = _sem_detect().find_field_of_view(img8)
    return (int(y0), int(x0), int(y1), int(x1)), raw, ck, img8[y0:y1, x0:x1]


_SEM_MODULES: dict = {}


def _sem_detect():
    if "detect" not in _SEM_MODULES:
        for d in (os.path.join(SEM_REPO, "code"),
                  os.path.join(SEM_REPO, "interior_active_learning", "code")):
            if d not in sys.path:
                sys.path.insert(0, d)
        import detect_cracks as D
        _SEM_MODULES["detect"] = D
    return _SEM_MODULES["detect"]


def _sem_contrast_kwargs(stem):
    if "contrast" not in _SEM_MODULES:
        _sem_detect()
        from common import contrast_kwargs_for
        _SEM_MODULES["contrast"] = contrast_kwargs_for
    return _SEM_MODULES["contrast"](stem)


# ================================================================== SEM databar recovery
def ticks_in_bar(bar, rows, fill):
    """Columns of the scale bar's two end ticks. Measured, never read.

    Lifted from `sem_databar_scale.ticks()` and parameterised by the tick band, which is
    the only thing that differs between a 280-row panel and the 140-row half-resolution
    one. A tick is a column bright over essentially the whole band; the databar's own
    left-hand cell divider also passes that test, so the runs are grouped and the
    outermost two of the right-hand group are taken.
    """
    v = bar > bar.max() * 0.75
    band = v[rows[0]:min(rows[1], bar.shape[0]), :]
    cols = np.where(band.sum(0) >= fill * band.shape[0])[0]
    if len(cols) < 2:
        return None
    runs = np.split(cols, np.where(np.diff(cols) > 3)[0] + 1)
    cent = [float(r.mean()) for r in runs]
    right = [c for c in cent if c > 0.25 * bar.shape[1]]
    if len(right) < 2:
        return None
    return right[0], right[-1]


def recover_140_row_databar(stem, raw, evidence_dir):
    """nm/px for the one 2026-07-08 frame that kept its panel, or stop the build.

    Two routes, as in sem_databar_scale.py, and they have to agree to within
    SEM_SCALE_TOLERANCE: the drawn bar's annotation over its MEASURED tick span, against
    the printed horizontal field width over the frame width. The panel crop is written to
    evidence/ so the two transcribed numbers can be checked against the pixels.
    """
    spec = SEM_DATABAR_140[stem]
    h, w = raw.shape
    if h != spec["fov_rows"] + spec["databar_rows"]:
        die(f"{stem} is {h} rows; the 140-row databar recovery expects "
            f"{spec['fov_rows']} + {spec['databar_rows']}. The file has changed. Do not "
            f"publish a pixel size recovered from a geometry that no longer holds.")
    bar = raw[spec["fov_rows"]:, :]
    tk = ticks_in_bar(bar, spec["tick_rows"], spec["tick_fill"])
    if tk is None:
        die(f"{stem}: no scale-bar ticks were found in its databar. The recovery this "
            f"build relies on has stopped working; it will not fall back to a default.")
    span = tk[1] - tk[0]
    from_bar = spec["bar_um"] * 1000.0 / span
    from_hfw = spec["hfw_um"] * 1000.0 / w
    disagree = abs(from_bar - from_hfw) / from_hfw
    os.makedirs(evidence_dir, exist_ok=True)
    panel8 = (bar.astype(np.float32) / max(float(bar.max()), 1.0) * 255)
    Image.fromarray(panel8.clip(0, 255).astype(np.uint8)).save(
        os.path.join(evidence_dir, f"{stem}__databar.png"))
    if disagree > SEM_SCALE_TOLERANCE:
        die(f"{stem}: the drawn scale bar gives {from_bar:.4f} nm/px and the printed "
            f"horizontal field width gives {from_hfw:.4f}, {100 * disagree:.2f}% apart "
            f"against a tolerance of {100 * SEM_SCALE_TOLERANCE:g}%. Either the tick "
            f"finder has latched onto something that is not the bar, or one of the two "
            f"transcriptions in SEM_DATABAR_140 is wrong. Look at the panel crop in "
            f"evidence/ before changing anything.")
    return {
        "nm_per_px": round(from_bar, 4),
        "scale_source": "sem_databar_140row",
        "scale_note": (
            f"recovered here from the 140-row instrument databar this frame kept: a "
            f"{spec['bar_um']:g} um drawn bar over a measured {span:.1f} px tick span, "
            f"controlled against the printed horizontal field width "
            f"({spec['hfw_um']:g} um over {w} px = {from_hfw:.4f} nm/px, "
            f"{100 * disagree:.2f}% apart). analysis/research/improve/"
            f"sem_databar_scale.py misses this frame because its FOV_ROWS constant is "
            f"4096 and this file is a half-resolution 2048 + 140. Panel: "
            f"{spec['panel']}"),
        "tick_span_px": round(span, 1),
        "bar_annotation_um": spec["bar_um"],
        "printed_hfw_um": spec["hfw_um"],
        "nm_per_px_from_printed_hfw": round(from_hfw, 4),
        "disagreement_pct": round(100 * disagree, 3),
    }


def load_databar_scale_json():
    if not os.path.exists(DATABAR_SCALE_JSON):
        die(f"{os.path.relpath(DATABAR_SCALE_JSON, REPO)} does not exist. It is the "
            f"recovered pixel size of the 2026-06-22 SEM session and this release will "
            f"not ship those frames unscaled when the measurement exists. Regenerate "
            f"it:  <sem-crack-detector>/.venv/bin/python -B "
            f"analysis/research/improve/sem_databar_scale.py")
    d = json.load(open(DATABAR_SCALE_JSON, encoding="utf-8"))
    return {r["frame"]: r for r in d["frames"]}, d


# ==================================================================== the Zenodo subtree
def zenodo_record():
    say(f"  GET {ZENODO_API}")
    try:
        with urllib.request.urlopen(ZENODO_API, timeout=60) as r:
            rec = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        die(f"the Zenodo API for record {ZENODO_RECORD} could not be read ({e}). The "
            f"public collection cannot be assembled without it. Nothing is substituted. "
            f"Re-run when the network is available, or pass --skip-zenodo to build the "
            f"laboratory arms alone and say so in the report.")
    md = rec.get("metadata", {})
    doi = rec.get("doi")
    lic = (md.get("license") or {}).get("id")
    title = md.get("title")
    say(f"  record {ZENODO_RECORD}: {title!r}")
    say(f"  doi {doi}   licence {lic}   {len(rec.get('files', []))} files")
    if doi != ZENODO_EXPECT_DOI:
        die(f"Zenodo record {ZENODO_RECORD} reports DOI {doi!r}, not "
            f"{ZENODO_EXPECT_DOI!r}. That is not the record this builder was pointed at.")
    if lic != ZENODO_EXPECT_LICENCE:
        die(f"Zenodo record {ZENODO_RECORD} is licensed {lic!r}, not "
            f"{ZENODO_EXPECT_LICENCE!r}. The licence of the subtree is the whole reason "
            f"LICENSING.md exists; a changed licence is not something to build through.")
    return rec


#: A multi-gigabyte transfer from Zenodo stalls. Observed while building this: a
#: connection that stayed open and delivered nothing for 95 minutes. A socket timeout
#: catches that, and a RANGE RESUME means catching it costs the retry rather than the
#: gigabytes already on disk.
DL_TIMEOUT = 90
DL_ATTEMPTS = 40


def download_resumable(url, part, want_bytes, label):
    """Fetch `url` into `part`, resuming from whatever is already there.

    Without the resume, one stalled socket near the end of a 4.4 GB file throws away the
    whole transfer, and the retry is as likely to stall as the attempt was.
    """
    last = None
    for attempt in range(1, DL_ATTEMPTS + 1):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        if have >= want_bytes:
            return
        req = urllib.request.Request(url)
        if have:
            req.add_header("Range", f"bytes={have}-")
        try:
            with urllib.request.urlopen(req, timeout=DL_TIMEOUT) as r:
                resuming = r.status == 206
                if have and not resuming:
                    # The server ignored the Range header; start over rather than
                    # appending the whole file onto a partial one.
                    have, resuming = 0, False
                    open(part, "wb").close()
                mode = "ab" if (have and resuming) else "wb"
                with open(part, mode) as out:
                    while True:
                        chunk = r.read(1 << 22)
                        if not chunk:
                            break
                        out.write(chunk)
                        have += len(chunk)
        except (urllib.error.URLError, OSError, ValueError) as e:
            last = e
            got = os.path.getsize(part) if os.path.exists(part) else 0
            say(f"    attempt {attempt}/{DL_ATTEMPTS} stopped at {human(got)} of "
                f"{human(want_bytes)} ({type(e).__name__}: {e}); resuming")
            time.sleep(min(30, 2 * attempt))
            continue
        if os.path.getsize(part) >= want_bytes:
            return
        say(f"    attempt {attempt}/{DL_ATTEMPTS} ended early at "
            f"{human(os.path.getsize(part))} of {human(want_bytes)}; resuming")
        time.sleep(min(30, 2 * attempt))
    die(f"downloading {label} from Zenodo did not complete after {DL_ATTEMPTS} "
        f"attempts (last error: {last}). Nothing is substituted.")


def zenodo_fetch(rec, cache):
    os.makedirs(cache, exist_ok=True)
    got = []
    for f in rec.get("files", []):
        key = f["key"]
        if not key.lower().endswith(".zip"):
            say(f"  skipping {key}: not a zip")
            continue
        want_md5 = (f.get("checksum") or "").split(":")[-1]
        dst = os.path.join(cache, os.path.basename(key))
        part = dst + ".part"
        if os.path.exists(part):
            say(f"  {key}: a partial download of {human(os.path.getsize(part))} is "
                f"already here and will be resumed, not restarted")
        if os.path.exists(dst) and os.path.getsize(dst) == f["size"]:
            say(f"  {key}: already cached, {human(f['size'])}; verifying md5")
            if md5_file(dst) == want_md5:
                say(f"  {key}: md5 ok, not re-downloaded")
                got.append((key, dst, f["size"], want_md5))
                continue
            say(f"  {key}: cached copy does not match the declared md5; re-downloading")
        url = (f.get("links") or {}).get("self") or f"{ZENODO_API}/files/{key}/content"
        say(f"  downloading {key} ({human(f['size'])}) from {url}")
        t0 = time.time()
        download_resumable(url, dst + ".part", f["size"], key)
        os.replace(dst + ".part", dst)
        dt = time.time() - t0
        say(f"  {key}: {human(os.path.getsize(dst))} in {dt / 60:.1f} min")
        if os.path.getsize(dst) != f["size"]:
            die(f"{key} downloaded {os.path.getsize(dst)} bytes, the record declares "
                f"{f['size']}.")
        if md5_file(dst) != want_md5:
            die(f"{key} does not match the md5 the Zenodo record declares "
                f"({want_md5}). The download is not the file.")
        say(f"  {key}: md5 {want_md5} ok")
        got.append((key, dst, f["size"], want_md5))
    if not got:
        die(f"Zenodo record {ZENODO_RECORD} exposes no zip files. That is not the "
            f"record this builder was pointed at.")
    return got


def zenodo_extract(zips, dest):
    """Extract only the Inconel 718 members, and report every top-level folder seen.

    The census is the answer to "what did the download actually contain", and it is also
    the evidence for LICENSING.md: the directory names are how a reader learns that this
    record re-publishes other people's collections.
    """
    census: dict = {}
    extracted, extracted_bytes, skipped_unsafe, not_image = 0, 0, [], []
    for key, path, _size, _md5 in zips:
        split = os.path.splitext(os.path.basename(key))[0]
        with zipfile.ZipFile(path) as zf:
            members = zf.infolist()
            say(f"  {key}: {len(members):,} entries")
            for m in members:
                parts = [p for p in m.filename.replace("\\", "/").split("/") if p]
                if not parts:
                    continue
                # Two levels is enough to separate the class folders from the split
                # folder above them whichever way round the archive is arranged.
                top = "/".join(parts[:2]) if len(parts) > 1 else parts[0]
                if top.split("/")[0] == split and len(parts) > 2:
                    top = "/".join(parts[1:3])
                c = census.setdefault(f"{split}.zip:{top}", {"files": 0, "bytes": 0})
                if not m.is_dir():
                    c["files"] += 1
                    c["bytes"] += m.file_size
            # These archives wrap everything in a single folder ("testsem/", ...). Keep
            # the split name, drop the wrapper, so the tree reads inconel718/test/<class>
            # rather than inconel718/test/testsem/<class>.
            roots = {m.filename.replace("\\", "/").lstrip("/").split("/")[0]
                     for m in members if m.filename.strip("/")}
            wrapper = roots.pop() if len(roots) == 1 else None
            for m in members:
                if m.is_dir() or not INCONEL_RE.search(m.filename):
                    continue
                if not m.filename.lower().endswith(IMAGE_EXT):
                    not_image.append(m.filename)
                    continue
                rel = m.filename.replace("\\", "/").lstrip("/")
                if ".." in rel.split("/") or rel.startswith("/"):
                    skipped_unsafe.append(m.filename)
                    continue
                parts = rel.split("/")
                if wrapper and parts[0] == wrapper and len(parts) > 1:
                    parts = parts[1:]
                out = os.path.join(dest, split, *parts)
                if os.path.exists(out) and os.path.getsize(out) == m.file_size:
                    extracted += 1
                    extracted_bytes += m.file_size
                    continue
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with zf.open(m) as fh, open(out, "wb") as o:
                    shutil.copyfileobj(fh, o, 1 << 20)
                extracted += 1
                extracted_bytes += m.file_size
    if skipped_unsafe:
        say(f"  !! {len(skipped_unsafe)} archive members had unsafe paths and were not "
            f"extracted: {skipped_unsafe[:5]}")
    if not extracted:
        die(f"Zenodo record {ZENODO_RECORD} contains no path matching Inconel 718. The "
            f"record is not what this builder is using the ID for. Nothing is "
            f"substituted. What it does contain: "
            f"{', '.join(sorted(census)[:25])}")
    say(f"  extracted {extracted:,} Inconel 718 image files, {human(extracted_bytes)}")
    if not_image:
        say(f"  left in the archives: {len(not_image)} non-image member(s) under the "
            f"Inconel 718 folders, the depositor's own scripts -- "
            f"{', '.join(sorted({os.path.basename(x) for x in not_image}))}")
    return census, extracted, extracted_bytes, sorted(not_image)


def zenodo_class_list(zips):
    """The record's own declared class list, read out of the archive.

    `LICENSING.md` and `README.md` both say that the Inconel 718 folders are present in
    the archive but absent from the collection's own class list. That is a claim about a
    file, so it is read from the file rather than recited: `class_id.txt` is located in
    whichever archive holds it, inflated, and its lines parsed. If it is not there, the
    claim is not made.
    """
    for _key, path, _size, _md5 in zips:
        with zipfile.ZipFile(path) as zf:
            for m in zf.infolist():
                if os.path.basename(m.filename).lower() != "class_id.txt":
                    continue
                raw = zf.read(m).decode("utf-8", "replace")
                names = re.findall(r"\b\d+\s+([^\s]+)", raw)
                return {"found_in": os.path.basename(path), "path": m.filename,
                        "declared_classes": names,
                        "n_declared": len(names),
                        "declares_inconel": [n for n in names
                                             if "inconel" in n.lower()]}
    return None


def inconel_sanity(dest):
    """Images and masks both present, and the masks look like masks.

    `--skip-zenodo` aside, a tree with images and no masks is not the collection the
    paper benchmarks on, and finding that out at build time is cheaper than finding it
    out in a reviewer's hands.
    """
    img, msk = [], []
    for root, _d, files in os.walk(dest):
        low = root.lower()
        for f in files:
            if not f.lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")):
                continue
            (msk if "mask" in low else img).append(os.path.join(root, f))
    say(f"  Inconel subtree: {len(img):,} image files, {len(msk):,} mask files")
    if not img or not msk:
        die(f"the extracted Inconel 718 subtree has {len(img)} images and {len(msk)} "
            f"masks. A crack benchmark with no masks is not what the record ID is being "
            f"used for here.")
    folders = {}
    for root, _d, files in os.walk(dest):
        n = sum(1 for f in files if f.lower().endswith(IMAGE_EXT))
        if n:
            folders[os.path.relpath(root, dest)] = n
    pairs = {}
    for rel, n in folders.items():
        parent, leaf = os.path.split(rel)
        kind = ("mask" if leaf.startswith("mask") else
                "image" if leaf.startswith(("image", "img")) else "other")
        variant = (leaf.replace("mask", "", 1).replace("image", "", 1)
                      .replace("img", "", 1).strip("_") or "base")
        pairs.setdefault((parent, variant), {})[kind] = n
    unbalanced = {f"{par}/{var}": v for (par, var), v in sorted(pairs.items())
                  if v.get("image") != v.get("mask")}
    augmented = {k: v for k, v in sorted(folders.items()) if "_aug" in k}
    sample = sorted(msk)[: min(8, len(msk))]
    polarity = []
    for p in sample:
        a = np.array(Image.open(p).convert("L"))
        polarity.append({"file": os.path.basename(p), "shape": list(a.shape),
                         "frac_zero": round(float((a == 0).mean()), 5),
                         "frac_ge_246": round(float((a >= 246).mean()), 5),
                         "frac_between": round(float(((a > 0) & (a < 246)).mean()), 5)})
    return {"n_images": len(img), "n_masks": len(msk),
            "files_per_folder": dict(sorted(folders.items())),
            "image_mask_counts_that_do_not_match": unbalanced,
            "augmented_folders": augmented,
            "mask_polarity_sample": polarity}


# ========================================================================= preview making
def _font(size):
    for p in ("/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _nice_bar(nm_per_px_preview, preview_w):
    """A round physical length close to a fifth of the preview width."""
    target_nm = 0.2 * preview_w * nm_per_px_preview
    best = None
    for unit, mult in (("nm", 1.0), ("um", 1000.0), ("mm", 1e6)):
        for v in (1, 2, 5, 10, 20, 50, 100, 200, 500):
            nm = v * mult
            px = nm / nm_per_px_preview
            if px < 40 or px > 0.6 * preview_w:
                continue
            score = abs(nm - target_nm) / target_nm
            if best is None or score < best[0]:
                best = (score, nm, px, f"{v:g} {unit}")
    return best


def stretch8(a):
    """A percentile stretch, the same 1.0 / 99.5 the project's own loader uses."""
    a = np.asarray(a, np.float32)
    finite = np.isfinite(a)
    if not finite.all():
        a = np.where(finite, a, np.nanmedian(a[finite]) if finite.any() else 0.0)
    lo, hi = np.percentile(a, [1.0, 99.5])
    if hi <= lo:
        lo, hi = float(a.min()), float(max(a.max(), a.min() + 1))
    return np.clip((a - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)


def make_preview(img8, paint, nm_per_px, out_path):
    """Greyscale frame, crack green, both not-crack verdicts red, unreviewed untouched.

    State 3 is drawn the SAME red as state 2 on purpose: an erase is a not-crack verdict,
    and colouring it differently would suggest it is a third kind of thing.

    A scale bar is burned in only where nm/px is known. Where it is not, there is no bar
    and no number: an unscaled preview is honest, an invented bar is not.
    """
    h, w = img8.shape
    k = max(1, int(np.ceil(max(h, w) / PREVIEW_MAX_SIDE)))
    if k > 1:
        img8 = np.array(Image.fromarray(img8).resize((w // k, h // k), Image.BILINEAR))
        # Nearest for the labels: a bilinear resize of a category map invents categories.
        paint = np.array(Image.fromarray(paint).resize((w // k, h // k), Image.NEAREST))
    rgb = np.repeat(img8[:, :, None], 3, axis=2).astype(np.float32)
    for states, colour in (((1,), CRACK_RGB), ((2, 3), NOTCRACK_RGB)):
        sel = np.isin(paint, states)
        if sel.any():
            rgb[sel] = 0.45 * rgb[sel] + 0.55 * np.array(colour, np.float32)
    im = Image.fromarray(rgb.clip(0, 255).astype(np.uint8))
    if nm_per_px:
        got = _nice_bar(nm_per_px * k, im.width)
        if got:
            _score, _nm, px, label = got
            d = ImageDraw.Draw(im)
            fs = max(12, im.width // 48)
            f = _font(fs)
            pad, th = max(8, im.width // 90), max(3, im.height // 220)
            x1, y1 = im.width - pad, im.height - pad
            x0 = x1 - px
            d.rectangle([x0 - 2, y1 - th - 2, x1 + 2, y1 + 2], fill=(0, 0, 0))
            d.rectangle([x0, y1 - th, x1, y1], fill=(255, 255, 255))
            tb = d.textbbox((0, 0), label, font=f)
            tx = x0 + (px - (tb[2] - tb[0])) / 2
            ty = y1 - th - 6 - (tb[3] - tb[1])
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    d.text((tx + dx, ty + dy), label, font=f, fill=(0, 0, 0))
            d.text((tx, ty), label, font=f, fill=(255, 255, 255))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    im.save(out_path, optimize=True)


# ============================================================================ the arms
def audit_all_sem_masks():
    """Every correction mask in the source repository against its original, by shape.

    The README states how many of the 48 match exactly, how many are short by the
    databar and how many by neither. Those are counted HERE rather than written into
    the prose, so the sentence cannot go stale when the source repository changes.
    """
    counts, examples = {}, {}
    for f in sorted(os.listdir(SEM_PAINT)):
        if not f.endswith("_correction_mask.png"):
            continue
        stem = f[: -len("_correction_mask.png")]
        tif = os.path.join(SEM_ORIG, stem + ".tif")
        if not os.path.exists(tif):
            counts["no original"] = counts.get("no original", 0) + 1
            continue
        with tifffile.TiffFile(tif) as tf:
            ih, iw = tf.pages[0].shape[:2]
        with Image.open(os.path.join(SEM_PAINT, f)) as im:
            mw, mh = im.size
        dr, dc = ih - mh, iw - mw
        key = ("exact" if (dr, dc) == (0, 0) else
               "short by 280 rows (databar)" if (dr, dc) == (280, 0) else
               "short by 140 rows (databar, half resolution)" if (dr, dc) == (140, 0)
               else "neither")
        counts[key] = counts.get(key, 0) + 1
        examples.setdefault(key, []).append(stem)
    return {"total": sum(counts.values()), "by_relation": counts,
            "neither": sorted(examples.get("neither", []))}


def audit_all_txm_state3():
    """Is paint state 3 used anywhere in the TXM source, not just in the released 30?

    The README says state 3 is absent from every TXM frame. That is a claim about the
    collection, so it is tested against the collection.
    """
    n, with3 = 0, []
    for f in sorted(os.listdir(TXM_CORR)):
        if not f.endswith("_correction.npy"):
            continue
        n += 1
        a = np.load(os.path.join(TXM_CORR, f), mmap_mode="r")
        if bool((np.asarray(a) == 3).any()):
            with3.append(f[: -len("_correction.npy")])
    return {"corrections_examined": n, "with_state_3": with3}


def build_sem(out, scale_rows):
    say("")
    say("SEM -- this laboratory's hand-corrected b2/b3 frames")
    stems = sorted(f[: -len("_correction_mask.png")] for f in os.listdir(SEM_PAINT)
                   if f.endswith("_correction_mask.png")
                   and any(f"_{s}_" in f.lower() for s in SCOPE))
    say(f"  {len(stems)} b2/b3 frames carry a correction mask "
        f"(of {sum(1 for f in os.listdir(SEM_PAINT) if f.endswith('_correction_mask.png'))}"
        f" masks in the source repository)")
    series = sorted({s for stem in stems for s in SCOPE if f"_{s}_" in stem.lower()})
    say(f"  specimen series present: {', '.join(series)}")
    # WHY THERE IS NO b3 SEM ARM. Counted, not assumed: b3 SEM frames exist in the
    # source repository, they simply have no correction mask, so there is nothing to
    # publish an annotation for. The README says this rather than leaving a reader to
    # wonder why one microscopy has both series and the other has only one.
    originals = {f[:-4] for f in os.listdir(SEM_ORIG) if f.endswith(".tif")}
    by_series = {s: sorted(o for o in originals if f"_{s}_" in o.lower())
                 for s in SCOPE}
    missing = {s: [o for o in by_series[s] if o not in stems] for s in SCOPE}
    for s in SCOPE:
        if missing[s]:
            say(f"  series {s}: {len(by_series[s])} original(s) in the source "
                f"repository, {len(by_series[s]) - len(missing[s])} with a correction "
                f"mask; without one: {', '.join(missing[s])}")

    rows, problems, darkness = [], [], {}
    evidence = os.path.join(out, "evidence", "sem_databar")
    for stem in stems:
        src_tif = os.path.join(SEM_ORIG, stem + ".tif")
        src_png = os.path.join(SEM_PAINT, stem + "_correction_mask.png")
        box, raw, ck, crop8 = sem_fov_box(stem)
        r0, c0, r1, c1 = box
        paint = np.array(Image.open(src_png))
        while paint.ndim > 2:
            paint = paint[..., 0]
        exp = EXPECTED_ALIGNMENT.get(stem)
        seen = (raw.shape[0], raw.shape[1], paint.shape[0], paint.shape[1])
        if exp is None:
            problems.append(f"{stem}: not in EXPECTED_ALIGNMENT; shapes {seen}")
        elif tuple(exp) != seen:
            problems.append(f"{stem}: shapes {seen}, recorded {tuple(exp)}")
        crop_h, crop_w = r1 - r0, c1 - c0
        if (crop_h, crop_w) == paint.shape:
            status = "ok"
            if (raw.shape[0] - crop_h, raw.shape[1] - crop_w) in ((280, 0), (140, 0)):
                status = f"ok_databar_{raw.shape[0] - crop_h}rows"
            elif (r0, c0, r1, c1) != (0, 0, raw.shape[0], raw.shape[1]):
                status = "ok_field_of_view_crop"
        else:
            status = "unresolved"
            problems.append(
                f"{stem}: the field-of-view crop is {crop_h}x{crop_w} and the mask is "
                f"{paint.shape[0]}x{paint.shape[1]}; no offset is published for it")

        # POSITIVE CONTROL ON THE ALIGNMENT. Matching shapes do not prove a matching
        # OFFSET: a mask cropped from the wrong corner has the right shape too. A crack
        # is dark, so if the offset is right the painted pixels are darker than the
        # unpainted ones. Measured, and a frame where it comes out the wrong way is a
        # problem, not a footnote.
        if status.startswith("ok") and (paint == 1).sum() > 50:
            inside = float(crop8[paint == 1].mean())
            outside = float(crop8[paint == 0].mean()) if (paint == 0).any() else inside
            darkness[stem] = round(inside - outside, 2)
            if inside >= outside:
                problems.append(
                    f"{stem}: painted crack is NOT darker than unreviewed area "
                    f"({inside:.1f} vs {outside:.1f} of 255). The mask may be aligned "
                    f"to the wrong offset even though its shape fits.")

        session = SESSIONS[stem[:6]]
        sc = scale_rows.get(stem, {})
        nm, src, note = sc.get("nm_per_px"), None, None
        if nm is not None:
            src = "sem_databar_280row"
            note = (f"recovered by analysis/research/improve/sem_databar_scale.py from "
                    f"the 280-row instrument databar this uncropped original kept: a "
                    f"{sc['bar_annotation_um']:g} um drawn bar over a measured "
                    f"{sc['tick_span_px']:.1f} px tick span, controlled against the "
                    f"printed horizontal field width "
                    f"({sc['printed_hfw_um']:g} um / {raw.shape[1]} px = "
                    f"{sc['nm_per_px_from_printed_hfw']:.4f} nm/px, "
                    f"{sc['disagreement_pct']:.2f}% apart)")
        elif stem in SEM_DATABAR_140:
            got = recover_140_row_databar(stem, raw, evidence)
            nm, src, note = got["nm_per_px"], got["scale_source"], got["scale_note"]
            sc = {**sc, **got}
        else:
            src = "none"
            note = ("the file carries no scale of any kind: it was re-saved by tifffile, "
                    "so Software is 'tifffile.py', ImageDescription is only the array "
                    "shape, XResolution/YResolution are 1/1 with ResolutionUnit NONE, "
                    "there is no FEI/Thermo private tag and no block in the file tail, "
                    "and no sidecar exists beside the originals. No value is carried "
                    "over from the 2026-06-22 session: the two were acquired at "
                    "different magnifications")

        dst_tif = os.path.join(out, "sem", "images", stem + ".tif")
        dst_png = os.path.join(out, "sem", "masks", stem + "_paint.png")
        copy_verbatim(src_tif, dst_tif)
        copy_verbatim(src_png, dst_png)

        hist = {int(k): int(v) for k, v in zip(*np.unique(paint, return_counts=True))}
        unexpected = sorted(k for k in hist if k not in (0, 1, 2, 3))
        if unexpected:
            problems.append(f"{stem}: paint holds values outside 0-3: {unexpected}")
        rows.append(frame_row(
            frame_id=stem, modality="SEM",
            series=next(s for s in SCOPE if f"_{s}_" in stem.lower()),
            session=session, raw_shape=raw.shape, box=box, mask_shape=paint.shape,
            status=status, nm=nm, scale_source=src, scale_note=note, hist=hist,
            image_file=os.path.relpath(dst_tif, out),
            mask_file=os.path.relpath(dst_png, out),
            source_repo="sem-crack-detector",
            source_image=os.path.basename(src_tif),
            source_mask=os.path.basename(src_png),
            source_image_sha=sha256_file(src_tif), source_mask_sha=sha256_file(src_png),
            extra={"contrast_percentiles": [ck["low_pct"], ck["high_pct"]],
                   "databar_rows": int(raw.shape[0] - crop_h) if status.startswith(
                       "ok_databar") else 0,
                   **{k: v for k, v in sc.items()
                      if k in ("tick_span_px", "bar_annotation_um", "printed_hfw_um",
                               "nm_per_px_from_printed_hfw", "disagreement_pct")}}))
        say(f"  {stem:<32} {status:<22} "
            f"{'%9.4f nm/px' % nm if nm else '     no pixel size'}  "
            f"crack {hist.get(1, 0):>9,}  notcrack {hist.get(2, 0) + hist.get(3, 0):>8,}"
            f"  unreviewed {hist.get(0, 0):>11,}")
    if darkness:
        say(f"  alignment positive control: on all {len(darkness)} frames carrying "
            f"painted crack, the paint is darker than the unreviewed area by "
            f"{-max(darkness.values()):.0f} to {-min(darkness.values()):.0f} grey "
            f"levels of 255")
    return rows, problems, darkness, {"originals_by_series":
                                      {k: len(v) for k, v in by_series.items()},
                                      "no_correction_mask": missing}


def build_txm(out, txm_group):
    say("")
    say("TXM -- the transmission X-ray collection")
    stems = sorted(f[: -len("_correction.npy")] for f in os.listdir(TXM_CORR)
                   if f.endswith("_correction.npy"))
    groups: dict = {}
    for s in stems:
        groups.setdefault(txm_group(s), []).append(s)
    say("  txm_group() over the whole correction set: "
        + ", ".join(f"{g} {len(v)}" for g, v in sorted(groups.items())))
    inscope = sorted(s for s in stems if txm_group(s).lower() in SCOPE)
    say(f"  in scope {SCOPE}: {len(inscope)} "
        f"(B2 {len(groups.get('B2', []))}, B3 {len(groups.get('B3', []))})")

    rows, problems = [], []
    for stem in inscope:
        src_tif = os.path.join(TXM_IMAGES, stem + ".tif")
        src_npy = os.path.join(TXM_CORR, stem + "_correction.npy")
        if not os.path.exists(src_tif):
            problems.append(f"{stem}: a correction exists but the image does not")
            continue
        paint = np.load(src_npy)
        raw = tifffile.imread(src_tif)
        if raw.ndim == 3:
            raw = raw[..., 0]
        status = "ok" if raw.shape == paint.shape else "unresolved"
        if status == "unresolved":
            problems.append(f"{stem}: image {raw.shape} vs correction {paint.shape}")

        fid = txm_frame_id(stem)
        dst_tif = os.path.join(out, "txm", "images", fid + ".tif")
        dst_npy = os.path.join(out, "txm", "masks", fid + "_paint.npy")
        dst_png = os.path.join(out, "txm", "masks", fid + "_paint.png")
        copy_verbatim(src_tif, dst_tif)
        copy_verbatim(src_npy, dst_npy)
        # A PNG beside the .npy so both arms have one loadable mask format. It is
        # written from the .npy and then READ BACK and compared: a convenience copy
        # that silently differed from the research data would be worse than none.
        if paint.dtype != np.uint8:
            problems.append(f"{stem}: correction dtype is {paint.dtype}, expected uint8")
        os.makedirs(os.path.dirname(dst_png), exist_ok=True)
        Image.fromarray(paint.astype(np.uint8), mode="L").save(dst_png, optimize=True)
        back = np.array(Image.open(dst_png))
        if back.shape != paint.shape or not np.array_equal(back, paint.astype(np.uint8)):
            die(f"{fid}: the PNG written beside the .npy does not read back equal to it. "
                f"A published mask that is not the research data is not publishable.")

        hist = {int(k): int(v) for k, v in zip(*np.unique(paint, return_counts=True))}
        unexpected = sorted(k for k in hist if k not in (0, 1, 2, 3))
        if unexpected:
            problems.append(f"{stem}: paint holds values outside 0-3: {unexpected}")
        rows.append(frame_row(
            frame_id=fid, modality="TXM", series=txm_group(stem).lower(),
            session={"date": txm_session_date(stem), "instrument": None,
                     "detector": None, "beam": None,
                     "source": "the source repository records no instrument, beam "
                               "energy, detector, objective, exposure or projection "
                               "count for this collection"},
            raw_shape=raw.shape, box=(0, 0, raw.shape[0], raw.shape[1]),
            mask_shape=paint.shape, status=status,
            nm=TXM_NM_PER_PX, scale_source=TXM_SCALE_SOURCE, scale_note=TXM_SCALE_NOTE,
            hist=hist,
            image_file=os.path.relpath(dst_tif, out),
            mask_file=os.path.relpath(dst_png, out),
            source_repo="TXM_Crack_Detection_Pipeline",
            source_image=os.path.basename(src_tif),
            source_mask=os.path.basename(src_npy),
            source_image_sha=sha256_file(src_tif), source_mask_sha=sha256_file(src_npy),
            extra={"mask_npy_file": os.path.relpath(dst_npy, out),
                   "txm_group": txm_group(stem)}))
        say(f"  {fid:<34} {txm_group(stem):<4} {status:<12} {TXM_NM_PER_PX:7.2f} nm/px  "
            f"crack {hist.get(1, 0):>9,}  notcrack {hist.get(2, 0) + hist.get(3, 0):>10,}"
            f"  unreviewed {hist.get(0, 0):>11,}")
    return rows, problems


def txm_frame_id(stem):
    s = re.sub(r"^Average_mosaic_", "", stem)
    return re.sub(r"_idx\d+_mosaictileAA_img\d+of\d+(\.xrm)?(\.bim)*$", "", s)


def txm_session_date(stem):
    m = re.search(r"_(2\d{5})_", "_" + stem)
    if not m:
        return None
    y, mo, d = m.group(1)[:2], m.group(1)[2:4], m.group(1)[4:6]
    return f"20{y}-{mo}-{d}"


def frame_row(*, frame_id, modality, series, session, raw_shape, box, mask_shape, status,
              nm, scale_source, scale_note, hist, image_file, mask_file, source_repo,
              source_image, source_mask, source_image_sha, source_mask_sha, extra):
    r0, c0, r1, c1 = box
    h0 = int(hist.get(0, 0)); h1 = int(hist.get(1, 0))
    h2 = int(hist.get(2, 0)); h3 = int(hist.get(3, 0))
    return {
        "frame_id": frame_id,
        "modality": modality,
        "specimen_series": series,
        "session_date": session["date"],
        "instrument": session["instrument"],
        "detector": session["detector"],
        "beam": session.get("beam"),
        "instrument_source": session["source"],
        "image_file": image_file,
        "mask_file": mask_file,
        "image_px_h": int(raw_shape[0]), "image_px_w": int(raw_shape[1]),
        "crop_row0": r0, "crop_col0": c0, "crop_row1": r1, "crop_col1": c1,
        "frame_px_h": int(r1 - r0), "frame_px_w": int(c1 - c0),
        "mask_px_h": int(mask_shape[0]), "mask_px_w": int(mask_shape[1]),
        "shape_status": status,
        "nm_per_px": nm,
        "scale_source": scale_source,
        "scale_note": scale_note,
        "px_state_0_unreviewed": h0,
        "px_state_1_crack": h1,
        "px_state_2_not_crack": h2,
        "px_state_3_not_crack_erased": h3,
        "px_total": h0 + h1 + h2 + h3,
        "px_reviewed": h1 + h2 + h3,
        "px_crack": h1,
        "px_not_crack": h2 + h3,
        "source_repo": source_repo,
        "source_image_file": source_image,
        "source_mask_file": source_mask,
        "source_image_sha256": source_image_sha,
        "source_mask_sha256": source_mask_sha,
        **extra,
    }


# ============================================================================== the checks
#: What must not appear anywhere in the published tree. The building user's own home
#: directory name is one of them, which is why this list is NOT written into checks.json:
#: a check that records what it is looking for would publish the very string it exists to
#: keep out.
def _needles():
    ns = [b"/Users/", b"/home/", b"C:\\Users", b"/private/var/folders",
          os.path.basename(os.path.expanduser("~")).encode(),
          REPO.encode(), SEM_REPO.encode(), TXM_REPO.encode()]
    return [n for n in ns if n and len(n) > 2]


def scan_for_paths(paths, out):
    """Absolute paths and personal directory names, in whole files, byte by byte.

    Every file is scanned, not just the text ones: a TIFF can carry a capture path in a
    tag, and the point of the check is to find that rather than to assume it away. The
    64-byte carry-over means a needle split across two reads is still found.
    """
    needles = _needles()
    hits, scanned, nbytes = [], 0, 0
    for p in paths:
        if os.path.islink(p) or not os.path.isfile(p):
            continue
        scanned += 1
        nbytes += os.path.getsize(p)
        rel = os.path.relpath(p, out)
        found = None
        tail = b""
        with open(p, "rb") as fh:
            while found is None:
                chunk = fh.read(1 << 22)
                if not chunk:
                    break
                buf = tail + chunk
                for n in needles:
                    if n in buf:
                        found = n.decode("utf-8", "replace")
                        break
                tail = buf[-64:]
        if found:
            hits.append({"file": rel, "found": found})
    return {"files_scanned": scanned, "bytes_scanned": nbytes,
            "looked_for": "the absolute-path prefixes of the macOS, Linux and Windows "
                          "user directories and of the macOS temporary area; the "
                          "building user's home directory name; and the absolute path "
                          "of each of the three source repositories. The strings "
                          "themselves are deliberately not spelled out here -- writing "
                          "one of them into the tree is exactly what this check exists "
                          "to prevent, and an earlier version of this field failed its "
                          "own check by quoting them.",
            "hits": hits}


def all_files(out, exclude=()):
    ex = {os.path.join(out, e) for e in exclude}
    for root, dirs, files in os.walk(out):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            if p not in ex:
                yield p


def write_manifest(out):
    entries = []
    for root, dirs, files in os.walk(out):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, out)
            if rel in ("MANIFEST.sha256",) or os.path.islink(p):
                continue
            entries.append((sha256_file(p), os.path.getsize(p), rel))
    entries.sort(key=lambda e: e[2])
    body = "".join(f"{h}  {sz:>14}  {rel}\n" for h, sz, rel in entries)
    write_text(os.path.join(out, "MANIFEST.sha256"),
               "# sha256  size_bytes  path   (paths relative to this file)\n" + body)
    return len(entries)


# ============================================================================ the writing
def write_tables(out, rows):
    cols = ["frame_id", "modality", "specimen_series", "session_date", "instrument",
            "detector", "beam", "instrument_source", "image_file", "mask_file",
            "image_px_h", "image_px_w", "crop_row0", "crop_col0", "crop_row1",
            "crop_col1", "frame_px_h", "frame_px_w", "mask_px_h", "mask_px_w",
            "shape_status", "nm_per_px", "scale_source", "scale_note",
            "px_state_0_unreviewed", "px_state_1_crack", "px_state_2_not_crack",
            "px_state_3_not_crack_erased", "px_total", "px_reviewed", "px_crack",
            "px_not_crack", "source_repo", "source_image_file", "source_mask_file",
            "source_image_sha256", "source_mask_sha256"]
    with open(os.path.join(out, "metadata.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_text(os.path.join(out, "frames.json"),
               json.dumps({"dataset": DATASET_NAME,
                           "paint_states": {"0": "unreviewed, excluded from every "
                                                 "denominator",
                                            "1": "crack",
                                            "2": "not-crack",
                                            "3": "not-crack by erasure"},
                           "columns_are_the_same_as": "metadata.csv, plus the per-arm "
                                                      "extras each frame carries",
                           "n_frames": len(rows),
                           "frames": rows}, indent=1) + "\n")


LOADER_PY = '''\
"""Open a frame of this dataset and its annotation. Refuses rather than guesses.

    from loader import load, frames
    fr = load("260622_316_H_b2_front_CBS_03")
    fr.image        # the frame, cropped to its recorded field of view
    fr.crack        # bool: a human painted crack here            (paint state 1)
    fr.not_crack    # bool: a human painted a not-crack verdict   (paint states 2 and 3)
    fr.reviewed     # bool: crack | not_crack -- the only valid denominator
    fr.nm_per_px    # float, or None. None means nobody knows, not "use a default".

THE FOUR PAINT STATES. 0 is UNREVIEWED and is not a negative. It is the absence of a
verdict, and every rate computed over it is wrong. 3 is not-crack by ERASURE, which is a
not-crack verdict and not the absence of one, so it is a negative exactly like 2. This
module hands out `crack`, `not_crack` and `reviewed` so that nobody has to decide.

WHY `image` IS CROPPED. Some frames were saved with the instrument databar still in the
file and the annotation was painted on the field of view alone. The crop that reconciles
them is not re-derived here: it was resolved once, at build time, by the project's own
field-of-view finder, and is recorded in frames.json as four numbers per frame. This
module applies those numbers and then CHECKS that image and mask agree, raising if they
do not. A frame whose shape_status is not "ok..." is refused outright.
"""
import json
import os

import numpy as np
import tifffile
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.abspath(__file__))
_META = None


class FrameShapeError(RuntimeError):
    """Image and annotation do not line up. Never silently cropped or resized."""


class Frame:
    __slots__ = ("meta", "image", "paint", "crack", "not_crack", "reviewed")

    def __init__(self, meta, image, paint):
        self.meta = meta
        self.image = image
        self.paint = paint
        self.crack = paint == 1
        self.not_crack = (paint == 2) | (paint == 3)
        self.reviewed = self.crack | self.not_crack

    def __repr__(self):
        s = self.meta.get("nm_per_px")
        return (f"<Frame {self.meta['frame_id']} {self.meta['modality']} "
                f"{self.image.shape[0]}x{self.image.shape[1]} "
                f"{'%.4g nm/px' % s if s else 'no pixel size'}>")

    @property
    def nm_per_px(self):
        return self.meta.get("nm_per_px")

    @property
    def scale_source(self):
        return self.meta.get("scale_source")


def _meta():
    global _META
    if _META is None:
        with open(os.path.join(ROOT, "frames.json"), encoding="utf-8") as fh:
            _META = {r["frame_id"]: r for r in json.load(fh)["frames"]}
    return _META


def frames(modality=None, series=None):
    """Frame ids, optionally filtered by modality ("SEM"/"TXM") or series ("b2"/"b3")."""
    out = []
    for fid, r in sorted(_meta().items()):
        if modality and r["modality"].lower() != modality.lower():
            continue
        if series and r["specimen_series"].lower() != series.lower():
            continue
        out.append(fid)
    return out


def meta(frame_id):
    try:
        return dict(_meta()[frame_id])
    except KeyError:
        raise KeyError(f"{frame_id!r} is not in this dataset; "
                       f"loader.frames() lists {len(_meta())} ids") from None


def load(frame_id):
    m = meta(frame_id)
    if not m["shape_status"].startswith("ok"):
        raise FrameShapeError(
            f"{frame_id}: shape_status is {m['shape_status']!r}. Its annotation could "
            f"not be aligned with its image at build time and this loader will not "
            f"guess an offset. See README.md, 'Frames whose annotation does not fit'.")
    img = tifffile.imread(os.path.join(ROOT, m["image_file"]))
    if img.ndim == 3:
        img = img[..., 0]
    if (img.shape[0], img.shape[1]) != (m["image_px_h"], m["image_px_w"]):
        raise FrameShapeError(
            f"{frame_id}: the image on disk is {img.shape} and frames.json records "
            f"{(m['image_px_h'], m['image_px_w'])}. The file is not the one this "
            f"dataset was built from; check MANIFEST.sha256.")
    img = img[m["crop_row0"]:m["crop_row1"], m["crop_col0"]:m["crop_col1"]]
    paint = np.array(Image.open(os.path.join(ROOT, m["mask_file"])))
    while paint.ndim > 2:
        paint = paint[..., 0]
    if img.shape != paint.shape:
        raise FrameShapeError(
            f"{frame_id}: image {img.shape} and annotation {paint.shape} disagree after "
            f"the recorded crop. Nothing is resized here.")
    bad = sorted(set(np.unique(paint).tolist()) - {0, 1, 2, 3})
    if bad:
        raise ValueError(f"{frame_id}: the annotation holds values outside 0-3: {bad}")
    return Frame(m, img, paint)


if __name__ == "__main__":
    import sys
    ids = sys.argv[1:] or (frames("SEM")[:1] + frames("TXM")[:1])
    for fid in ids:
        fr = load(fid)
        n = fr.paint.size
        print(fr)
        print(f"   crack      {fr.crack.sum():>12,}  {100 * fr.crack.mean():6.3f}% of frame")
        print(f"   not-crack  {fr.not_crack.sum():>12,}  {100 * fr.not_crack.mean():6.3f}%"
              f"   (state 2 {int((fr.paint == 2).sum()):,} + erased state 3 "
              f"{int((fr.paint == 3).sum()):,})")
        print(f"   reviewed   {fr.reviewed.sum():>12,}  {100 * fr.reviewed.mean():6.3f}%"
              f"   -- the denominator; the other {100 * (1 - fr.reviewed.mean()):.3f}% "
              f"({n - int(fr.reviewed.sum()):,} px) is state 0 and is excluded")
        print(f"   scale      {fr.nm_per_px}  ({fr.scale_source})")
'''

SCORE_PY = '''\
"""Score a prediction against a frame of this dataset, over REVIEWED PIXELS ONLY.

    from loader import load
    from score import score
    print(score(load("260622_316_H_b2_front_CBS_03"), my_mask))

    python score.py <frame_id> <prediction.png>

Reported: precision, recall, F1, IoU and the area ratio. Balanced accuracy and MCC are
deliberately absent and must not be added: both are dominated by the true-negative count,
which on this data is whatever fraction of the frame a human happened to paint a
not-crack verdict over, so both measure annotation coverage more than they measure a
detector.

WHY "REVIEWED ONLY" IS NOT A DETAIL. Neither arm adjudicates the whole frame. Counting
unreviewed pixels as negatives charges a detector for marking area nobody ever looked at;
in this project that once turned a precision of 0.99 into 0.29. `reviewed_fraction` is
returned beside every score so the reader can see how much of the frame the number rests
on, and `precision_if_unrefereed_wrong` is returned as the other end of the bracket a
partly-refereed annotation can support. A single precision is not the answer; the two
ends are.

AND WHY A FRAME CAN STILL NOT SUPPORT ONE. Restricting to reviewed pixels means the
denominator of precision is `crack + not-crack`. __N_NO_NEG__ of the __N_FRAMES__ frames
in this dataset carry painted crack and **no not-crack verdict at all**, and
__N_NO_POS__ carry a not-crack verdict and no crack. On a frame with no refereed
negative, every reviewed pixel is positive, so a detector that marks the whole frame
scores precision 1.0 -- not because it is precise but because there is nothing on that
frame it can be wrong about. The same holds for recall where there is no painted crack.

So `precision_supported` and `recall_supported` are returned beside the numbers, using
this project's own convention of at least MIN_PX of the relevant verdict, and a mean
taken over frames must drop the unsupported ones rather than average a 1.0 that was
free. `precision_if_unrefereed_wrong` is the informative end on exactly those frames.
"""
import numpy as np

#: A frame needs this many pixels of a verdict before a score against that verdict means
#: anything. The same threshold the published tables use
#: (analysis/research/improve/overlap_means_sem_txm.py, MIN_PX).
MIN_PX = 200


def score(frame, prediction, *, restrict_to_reviewed=True):
    """`frame` from loader.load(); `prediction` a bool array of the same shape."""
    pred = np.asarray(prediction)
    if pred.shape != frame.paint.shape:
        raise ValueError(
            f"prediction is {pred.shape}, the frame is {frame.paint.shape}. Nothing is "
            f"resized here: a resized prediction is a different prediction.")
    pred = pred.astype(bool)
    pos, neg, rev = frame.crack, frame.not_crack, frame.reviewed
    m = (pred & rev) if restrict_to_reviewed else pred

    tp = int((m & pos).sum())
    fp = int((m & neg).sum())
    fn = int((~pred & pos).sum())
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    f1 = (2 * precision * recall / (precision + recall)
          if tp + fp and tp + fn and (precision + recall) else 0.0)
    iou = tp / (tp + fp + fn) if tp + fp + fn else float("nan")

    marked_unreviewed = int((pred & ~rev).sum())
    fp_all = fp + marked_unreviewed
    p_lo = tp / (tp + fp_all) if tp + fp_all else float("nan")

    n_pos, n_neg = int(pos.sum()), int(neg.sum())
    return {
        "frame_id": frame.meta["frame_id"],
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "iou": iou,
        # Does this frame carry enough of each verdict for the score above it to mean
        # anything? With no refereed negative, precision is 1.0 for free.
        "precision_supported": n_neg >= MIN_PX,
        "recall_supported": n_pos >= MIN_PX,
        "f1_supported": n_pos >= MIN_PX and n_neg >= MIN_PX,
        "crack_px": n_pos,
        "not_crack_px": n_neg,
        # predicted crack area over painted crack area, on reviewed pixels. >1 is
        # over-marking, <1 is under-marking; it is a different question from precision
        # and it is the one an area-fraction result turns on.
        "area_ratio": (int(m.sum()) / int(pos.sum())) if pos.sum() else float("nan"),
        "tp": tp, "fp": fp, "fn": fn,
        "reviewed_px": int(rev.sum()),
        "reviewed_fraction": float(rev.mean()),
        "predicted_px": int(pred.sum()),
        "predicted_px_on_reviewed": int(m.sum()),
        "marked_px_nobody_reviewed": marked_unreviewed,
        "precision_if_unrefereed_wrong": p_lo,
    }


def _fmt(d):
    order = ["precision", "recall", "f1", "iou", "area_ratio",
             "precision_if_unrefereed_wrong", "reviewed_fraction"]
    flag = {"precision": "precision_supported", "recall": "recall_supported",
            "f1": "f1_supported", "iou": "f1_supported"}
    lines = [d["frame_id"]]
    for k in order:
        note = ""
        if flag.get(k) and not d[flag[k]]:
            why = ("no refereed not-crack on this frame" if k != "recall"
                   else "no painted crack on this frame")
            note = f"   <-- NOT SUPPORTED: {why}"
        lines.append(f"  {k:<30} {d[k]:.4f}{note}")
    for k in ("tp", "fp", "fn", "crack_px", "not_crack_px", "predicted_px",
              "reviewed_px", "marked_px_nobody_reviewed"):
        lines.append(f"  {k:<30} {d[k]:,}")
    return "\\n".join(lines)


if __name__ == "__main__":
    import sys
    from PIL import Image
    from loader import load

    if len(sys.argv) != 3:
        raise SystemExit("usage: python score.py <frame_id> <prediction.png>")
    fr = load(sys.argv[1])
    pr = np.array(Image.open(sys.argv[2]))
    while pr.ndim > 2:
        pr = pr[..., 0]
    print(_fmt(score(fr, pr > 0)))
'''


def _inconel_contents(zen):
    """What the extracted subtree holds, and the two things not to assume about it."""
    s = (zen or {}).get("sanity")
    if not s:
        return ""
    rows = "\n".join(f"| `{k}` | {v:,} |"
                      for k, v in sorted(s["files_per_folder"].items()) if v)
    aug = s.get("augmented_folders") or {}
    unb = s.get("image_mask_counts_that_do_not_match") or {}
    out = [
        "### What the subtree holds",
        "",
        "Only image data was taken out of the archives. The deposit also carries the "
        "depositor's own working scripts beside the image folders (" +
        (", ".join("`" + os.path.basename(x) + "`"
                   for x in sorted({os.path.basename(y)
                                    for y in s.get('not_extracted_non_image_members', [])}))
         or "none found") + "); those are somebody else's code, not data, and they were "
        "left in the zip.",
        "",
        "| folder | image files |",
        "|---|---|",
        rows,
        "",
    ]
    if aug:
        out += [
            "**The `*_aug` folders are augmented copies, not new fields.** They hold " +
            f"{sum(aug.values()):,} files across {len(aug)} folders and are derived from "
            "the originals beside them. Counting them as independent samples inflates "
            "n by several-fold; score on the base `image`/`mask` or "
            "`image_cropped`/`mask_cropped` folders unless you mean to train on "
            "augmentations.",
            "",
        ]
    if unb:
        out += [
            "**Image and mask counts do not match in every folder pair**, which is the "
            "depositor's structure rather than a fault in this build -- several classes "
            "share one pool of source images and carry only the masks that class needs:",
            "",
        ] + [f"- `{k}`: {v.get('image', 0):,} images, {v.get('mask', 0):,} masks"
             for k, v in unb.items()] + [""]
    out += [
        "This release makes no claim about the annotation protocol behind these masks; "
        "see the caveat above and `LICENSING.md`.",
    ]
    return "\n".join(out)


def _undeclared_note(zen):
    """The 'present but undeclared' paragraph, written only if the archive says so."""
    c = (zen or {}).get("classes")
    if not c:
        return ("The record's own class list was not read on this build, so no claim is "
                "made here about whether the Inconel 718 folders are declared in it.")
    if c["declares_inconel"]:
        return ("**The record declares its Inconel 718 classes.** `" + c["path"] +
                "` lists " + str(c["n_declared"]) + " classes, among them " +
                ", ".join("`" + n + "`" for n in c["declares_inconel"]) + ".")
    return (
        "**There is a provenance caveat on this collection that a reviewer will find.** "
        "The record's own `" + c["path"] + "` declares " + str(c["n_declared"]) +
        " target classes and **not one of them names Inconel** -- read from the archive "
        "on this build, not quoted from memory. The declared classes are " +
        ", ".join("`" + n + "`" for n in c["declared_classes"]) + ". The Inconel 718 "
        "folders are present in the archive but undeclared, with no class definition and "
        "no stated annotation protocol. The data is real and has masks; the protocol "
        "behind them is undocumented. Say so rather than letting a reader discover it.")


def _undeclared_bullet(zen):
    c = (zen or {}).get("classes")
    if not c:
        return ("- The record's own class list was not read on this build, so nothing is "
                "claimed here about whether the Inconel 718 folders are declared in it.")
    if c["declares_inconel"]:
        return ("- The Inconel 718 material **is** declared in the record's own class "
                "list (`" + c["path"] + "`, " + str(c["n_declared"]) + " classes).")
    return ("- The Inconel 718 folders are **not in the record's own declared class "
            "list**: `" + c["path"] + "` declares " + str(c["n_declared"]) + " classes "
            "and none of them names Inconel (read from the archive on this build). The "
            "material is present in the archive but undeclared, so its provenance and "
            "annotation protocol are not documented by the record either.")


def build_readme(out, rows, zen, darkness, mask_audit, s3_audit, sem_series):
    nocrack = [r for r in rows if r["px_crack"] == 0]
    nonotcrack = [r for r in rows if r["px_not_crack"] == 0]
    both = [r for r in rows if r["px_crack"] >= MIN_VERDICT_PX
            and r["px_not_crack"] >= MIN_VERDICT_PX]
    sem = [r for r in rows if r["modality"] == "SEM"]
    txm = [r for r in rows if r["modality"] == "TXM"]
    scaled = [r for r in sem if r["nm_per_px"]]
    unscaled = [r for r in sem if not r["nm_per_px"]]
    unresolved = [r for r in rows if not r["shape_status"].startswith("ok")]
    s3 = {"SEM": sum(r["px_state_3_not_crack_erased"] for r in sem),
          "TXM": sum(r["px_state_3_not_crack_erased"] for r in txm)}
    txm_b2 = [r for r in txm if r["specimen_series"] == "b2"]
    txm_b3 = [r for r in txm if r["specimen_series"] == "b3"]

    def tab(rs, cols, fmt):
        head = "| " + " | ".join(cols) + " |"
        rule = "|" + "|".join("---" for _ in cols) + "|"
        return "\n".join([head, rule] + [fmt(r) for r in rs])

    scale_tbl = tab(
        sorted(sem, key=lambda r: r["frame_id"]),
        ["frame", "session", "nm/px", "source"],
        lambda r: (f"| `{r['frame_id']}` | {r['session_date']} | "
                   f"{('%.4f' % r['nm_per_px']) if r['nm_per_px'] else '--'} | "
                   f"{r['scale_source']} |"))

    zen_block = "The Zenodo stage was skipped (`--skip-zenodo`); `inconel718/` is absent."
    if zen:
        lines = [
            f"Downloaded from the Zenodo API on {zen['when']}, each archive's bytes "
            f"checked against the md5 its record entry declares before anything was "
            f"extracted from it:",
            "",
        ]
        lines += [f"- `{k}` -- {human(s)}, md5 `{m}`" for k, _p, s, m in zen["files"]]
        lines += [
            "",
            f"Record title: *{zen['title']}* DOI `{zen['doi']}`, licence "
            f"`{zen['licence']}`, published {zen['publication_date']}, deposited by "
            f"{zen['creators']}.",
            "",
            f"**Only the Inconel 718 members were extracted: {zen['extracted']:,} files, "
            f"{human(zen['extracted_bytes'])}.** Everything else the archives hold was "
            f"left in them. What the download actually contained, by archive and folder:",
            "",
            "| archive : folder | files | size |",
            "|---|---|---|",
        ]
        lines += [f"| `{k}` | {v['files']:,} | {human(v['bytes'])} |"
                  for k, v in sorted(zen["census"].items()) if v["files"]]
        lines += [
            "",
            f"What was extracted: {zen['sanity']['n_images']:,} image files and "
            f"{zen['sanity']['n_masks']:,} mask files.",
        ]
        zen_block = "\n".join(lines)

    body = f"""\
# {DATASET_NAME}

SEM and transmission X-ray microscopy (TXM) of fatigue cracks in 316L stainless steel,
specimen series b2 and b3, with the hand annotations made on them -- assembled beside the
public Inconel 718 crack collection so that a method can be tried on both without
stitching three sources together first.

Built by `tools/build_release.py` in the `crack-fractography` repository. Re-running that
script against the same sources reproduces this tree; nothing in it was edited by hand.

Built {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.

---

## What is here

| | frames | annotation | pixel size |
|---|---|---|---|
| `sem/` | {len(sem)} | 4-state hand correction masks | {len(scaled)} of {len(sem)} recovered, {len(unscaled)} null |
| `txm/` | {len(txm)} (B2 {len(txm_b2)}, B3 {len(txm_b3)}) | 4-state hand correction masks | all {TXM_NM_PER_PX} nm/px, **derived, not instrument metadata** |
| `inconel718/` | public collection, Zenodo {ZENODO_RECORD} | binary masks | **none published anywhere in that record** |

```
{DATASET_NAME}/
  README.md  LICENSING.md  CITATION.cff  DATA_AVAILABILITY.md
  loader.py  score.py
  metadata.csv  frames.json  checks.json  MANIFEST.sha256
  sem/images/*.tif          sem/masks/*_paint.png
  txm/images/*.tif          txm/masks/*_paint.npy  *_paint.png
  inconel718/{{train,test}}/...
  previews/sem/*.png        previews/txm/*.png
  evidence/sem_databar/*.png
```

**Read `LICENSING.md` before redistributing `inconel718/`.** The two laboratory arms and
that subtree are not under the same terms, and the difference is not cosmetic.

---

## The four paint states

Every value in every `*_paint.png` and `*_paint.npy` in `sem/` and `txm/` is one of four
numbers, and they are preserved here exactly as the annotator left them:

| value | meaning |
|---|---|
| `0` | **unreviewed.** Nobody looked at this pixel. **Excluded from every denominator.** |
| `1` | **crack.** A human painted crack here. |
| `2` | **not-crack.** A human painted an explicit not-crack verdict here. |
| `3` | **not-crack by erasure.** A human erased a machine mark here. |

Two of these are easy to get wrong and both have cost this project real numbers.

**`0` is not a negative.** It is the absence of a verdict. Scoring unreviewed area as
background charges a detector for marking pixels nobody ever adjudicated; doing exactly
that once turned a precision of 0.99 into 0.29 here. Use `frame.reviewed` as the
denominator, which is what `score.py` does, and read the returned `reviewed_fraction`
beside every number: on these frames it ranges from under a per cent to most of the
frame.

**`3` is a verdict, not an absence.** An erase is a human saying *not crack here*. It
counts as a refereed negative exactly like `2`. Collapsing it into `0` throws away
{s3['SEM']:,} adjudicated pixels.

State `3` is used on SEM ({s3['SEM']:,} px across {sum(1 for r in sem if r['px_state_3_not_crack_erased'])} of the {len(sem)} frames) and is **absent from every
TXM frame** ({s3['TXM']} px) -- checked on all {len(txm)} published TXM corrections and,
separately, on all {s3_audit['corrections_examined']} corrections in the source
repository, {'none of which uses it' if not s3_audit['with_state_3'] else 'of which ' + str(len(s3_audit['with_state_3'])) + ' DO use it -- this sentence is wrong, see checks.json'}. Not assumed.

`loader.py` returns `crack`, `not_crack` and `reviewed` as three boolean arrays so that a
user of this dataset never has to make this decision.

```python
from loader import load, frames
fr = load(frames("SEM")[0])
fr.crack, fr.not_crack, fr.reviewed      # bool arrays, aligned with fr.image
fr.nm_per_px                             # float, or None -- never a default
```

---

## How the data was acquired and annotated

**SEM.** Thermo Fisher Apreo, CBS detector, 20.00 kV, 13 nA, 8.0 mm working distance,
over two sessions: 2026-06-22 ({sum(1 for r in sem if r['session_date'] == '2026-06-22')} frames here) and 2026-07-08
({sum(1 for r in sem if r['session_date'] == '2026-07-08')} frames). The instrument and
beam conditions are read off the databar burned into the 2026-06-22 frames; for the
2026-07-08 session they come from the one frame of that session that kept its panel
(`260708_316_H_b2_front_CBS_001`), and the other fifteen files carry no instrument
metadata at all. `metadata.csv` says this per frame in `instrument_source`.

**TXM.** Mosaic transmission X-ray microscopy of 316L specimens under load, 2026-06-18
and 2026-06-20, stored as deflate-compressed float32 and bit-exact to the instrument
output. **The microscope, beam energy, detector, zone plate, exposure, projection count
and reconstruction method are not recorded in the source repository and are therefore
not recorded here.** `instrument` is null for every TXM frame, with that reason attached.

**Every SEM frame here is specimen series b2. There is no b3 SEM arm, and that is not an
omission.** The source repository holds {sem_series['originals_by_series']['b3']} b3 SEM
original(s) -- {', '.join('`' + x + '`' for x in sem_series['no_correction_mask']['b3'])} --
and **not one of them has a correction mask**, so there is no annotation to publish
against them. The b3 evidence in this release is entirely in the TXM arm, which carries
{sum(1 for r in rows if r['modality'] == 'TXM' and r['specimen_series'] == 'b3')} b3
frames. Of the {sem_series['originals_by_series']['b2']} b2 SEM originals,
{sem_series['originals_by_series']['b2'] - len(sem_series['no_correction_mask']['b2'])}
have a correction mask and are here{'; without one: ' + ', '.join('`' + x + '`' for x in sem_series['no_correction_mask']['b2']) if sem_series['no_correction_mask']['b2'] else ''}.

**Annotation, both arms.** A detector proposed a mask, a human corrected it in a painting
tool, and the correction was saved as the four-state array above. The human reviewed the
areas they chose to review: coverage is partial by design and varies by two orders of
magnitude across frames, which is why the unreviewed state exists and why it must be
excluded rather than counted.

---

## Scale, per arm, and where it is missing

A scale bar was asked for on everything. It cannot honestly be given for everything, and
nothing here is defaulted or carried over between sessions.

**SEM 2026-06-22 -- recovered from the instrument databar.** These frames were saved
uncropped: 4376 rows where the field of view is 4096, and the 280 rows underneath are the
instrument panel with the acquisition parameters and a drawn scale bar still in them.
`analysis/research/improve/sem_databar_scale.py` recovers the pixel size from the drawn
bar's annotation over its measured tick span, controlled against the printed horizontal
field width; the two routes agree to better than 0.1% on every frame.

**SEM 2026-07-08 -- one frame recovered, fifteen null.**
`260708_316_H_b2_front_CBS_001` is 2188 rows where the field of view is 2048: it is a
half-resolution frame and the 140 rows underneath are the same instrument panel. Its
pixel size is recovered here by the same two-route method
(**{next((r['nm_per_px'] for r in sem if r['frame_id'] == '260708_316_H_b2_front_CBS_001'), None)} nm/px**
from a 1 mm bar over a measured tick span, against 843.09 nm/px from the printed
2.59 mm field width, 0.18% apart). The panel crop it was read from is in
`evidence/sem_databar/` so the transcription can be checked against the pixels.

The other fifteen carry nothing, and that was established rather than assumed. Every TIFF
tag of all sixteen was dumped: `Software` is `tifffile.py` on every one of them, so the
files were re-saved and the instrument block was dropped; `ImageDescription` holds only
`{{"shape": [h, w]}}`; `XResolution` and `YResolution` are `1/1` with `ResolutionUnit`
`NONE`, which is "no resolution information", not a resolution; there is no FEI/Thermo
private tag, nothing matching `PixelWidth`, `HFW`, `Magnification` or `[Scan]` anywhere in
the file tail, and no sidecar file exists beside the originals. They are recorded with
`nm_per_px: null` and `scale_source: "none"`.

**No value is transferred between the two sessions.** They were acquired at different
magnifications and these very numbers show it: {min(r['nm_per_px'] for r in sem if r['session_date'] == '2026-06-22'):.1f} to {max(r['nm_per_px'] for r in sem if r['session_date'] == '2026-06-22'):.1f} nm/px on 2026-06-22 against
{next(r['nm_per_px'] for r in sem if r['session_date'] == '2026-07-08' and r['nm_per_px']):.1f} nm/px
on the one 2026-07-08 frame that can be measured, a factor of
{next(r['nm_per_px'] for r in sem if r['session_date'] == '2026-07-08' and r['nm_per_px']) / max(r['nm_per_px'] for r in sem if r['session_date'] == '2026-06-22'):.0f} to {next(r['nm_per_px'] for r in sem if r['session_date'] == '2026-07-08' and r['nm_per_px']) / min(r['nm_per_px'] for r in sem if r['session_date'] == '2026-06-22'):.0f}.

**And that one frame is a survey image, not a crack field.** A 2.59 mm field width across
3072 px is the whole specimen at low magnification; its fifteen siblings are working
fields and are a different kind of picture. Use it to locate, not to measure, and do not
pool its area fraction with the others as though they were the same acquisition. It is
also the reason its pixel size cannot stand in for theirs: it is the one frame of that
session that is NOT at the session's working magnification.

**TXM -- {TXM_NM_PER_PX} nm/px, derived, on every frame.** {TXM_SCALE_NOTE[0].upper() + TXM_SCALE_NOTE[1:]}
It is recorded with `scale_source: "{TXM_SCALE_SOURCE}"` and never as instrument metadata.

**Inconel 718 -- no pixel size at all.** The Zenodo record publishes none: no TIFF
resolution tag, no databar, nothing in the record metadata, and its subsets come from
different microscopes. Area fractions and IoU on that subtree are dimensionless and
comparable; lengths and widths in physical units are not available from it.

{scale_tbl}

Every TXM frame: {TXM_NM_PER_PX} nm/px, `{TXM_SCALE_SOURCE}`.

---

## Previews

`previews/` holds an 8-bit PNG per frame: the greyscale micrograph with crack painted
green and both not-crack verdicts (states 2 and 3) painted red. Unreviewed area is left as
the greyscale, because it is not a verdict and colouring it would make it look like one.
States 2 and 3 are drawn the same red on purpose: they are the same verdict.

**A scale bar is burned in only where the pixel size is known.** On the frames with
`scale_source: "none"` there is no bar and no number. An unscaled preview is honest; an
invented bar is not.

Previews are downscaled to a longest side of {PREVIEW_MAX_SIDE} px. The image is resampled
bilinearly and the annotation **nearest-neighbour**, because a bilinear resize of a
category map invents categories that were never painted.

---

## Frames whose annotation does not fit, and how the crop was resolved

Counted over all {mask_audit['total']} SEM correction masks in the source repository,
against the original each one names:

{chr(10).join('- %s: **%d**' % (k, v) for k, v in sorted(mask_audit['by_relation'].items()))}

The 280-row and 140-row cases are the instrument databar, which the uncropped originals
still carry and the painting tool removed; that is legitimate. The rest line up with
neither{': ' + ', '.join('`' + x + '`' for x in mask_audit['neither']) if mask_audit['neither'] else ''}.

This release does not guess an offset and does not silently crop. For each frame the crop
was resolved once at build time by `detect_cracks.find_field_of_view`, **this project's
own field-of-view finder** -- the same call `analysis/research/improve/overlap_means_sem_txm.py`
makes -- and the resolved box is written into `frames.json` and `metadata.csv` as four
explicit numbers (`crop_row0`, `crop_col0`, `crop_row1`, `crop_col1`). `loader.py` applies
those numbers and then checks that image and annotation agree; it has no field-of-view
finder of its own and needs none.

All {len(sem)} published SEM frames resolve exactly this way, including the
{sum(1 for r in sem if r['shape_status'] == 'ok_field_of_view_crop')} whose raw shapes
match neither the exact nor the databar case:

| frame | image | mask | resolved crop | relation |
|---|---|---|---|---|
{chr(10).join(f"| `{r['frame_id']}` | {r['image_px_h']}x{r['image_px_w']} | {r['mask_px_h']}x{r['mask_px_w']} | ({r['crop_row0']},{r['crop_col0']})-({r['crop_row1']},{r['crop_col1']}) | {r['shape_status']} |" for r in sem if r['shape_status'] not in ('ok',))}

The alignment was not accepted on shape agreement alone: a mask cropped from the wrong
corner has the right shape too. A crack is dark, so the builder measures it. On all
{len(darkness)} frames carrying painted crack, the mean grey level inside the paint is
darker than the unreviewed area by **{-max(darkness.values()):.0f} to {-min(darkness.values()):.0f} grey levels of 255**
(per frame in `checks.json`). A correct shape with a wrong offset would not do that, and
a frame where the sign came out the other way would fail this build.

All {len(txm)} TXM corrections match their image exactly; none needed a crop.

{"**Unresolved: " + str(len(unresolved)) + " frame(s).** " + ", ".join('`' + r['frame_id'] + '`' for r in unresolved) + " -- `loader.py` refuses these." if unresolved else "**No frame in this release is unresolved.**"}

---

## Frames that carry only one of the two verdicts

Annotation coverage here is partial by design, and on some frames it is one-sided. Those
frames are not errors and they are not empty -- a frame with only a not-crack verdict is
exactly what a false-positive measurement needs -- but **a score computed on them can be
meaningless while looking fine**, so they are listed rather than left to be discovered.

**{len(nocrack)} of the {len(rows)} frames carry zero crack pixels.** Recall on them is
0/0, and a mean over frames that silently includes them is wrong.

{chr(10).join(f"- `{r['frame_id']}` ({r['modality']}, {r['specimen_series']}): {r['px_not_crack']:,} not-crack px, {r['px_state_0_unreviewed']:,} unreviewed" for r in nocrack)}

**{len(nonotcrack)} of the {len(rows)} frames carry zero not-crack pixels.** This is the
one that bites. Scoring over reviewed pixels means the denominator of precision is
crack + not-crack; with no refereed negative, every reviewed pixel is positive, so a
detector that marks the entire frame scores **precision 1.0** on it -- not because it is
precise but because there is nothing on that frame it can be wrong about. Read
`precision_if_unrefereed_wrong` instead on these, which is the other end of the bracket.

{chr(10).join(f"- `{r['frame_id']}` ({r['modality']}, {r['specimen_series']}): {r['px_crack']:,} crack px, {r['px_state_0_unreviewed']:,} unreviewed" for r in nonotcrack)}

**{len(both)} of the {len(rows)} frames carry at least {MIN_VERDICT_PX} px of both
verdicts.** Those are the frames an F1 is defined on, and they are the set the published
tables score. `score.py` returns `precision_supported`, `recall_supported` and
`f1_supported` on every frame so this never has to be remembered.

---

## The public Inconel 718 subtree

{zen_block}

{_undeclared_note(zen)}

{_inconel_contents(zen)}

---

## Reproducing the paper's numbers

The release carries the frames and the annotation, not the detector. To reproduce a
published score:

1. **Scope.** The manuscript reports specimen series b2 and b3 in both microscopies. That
   is exactly this release: {len(sem)} SEM and {len(txm)} TXM frames. The full laboratory
   corpus is wider (SEM also has b4 and the MAR_*/AS_*/Cast_*/HIP_* fields; TXM also has
   Wrought and AM/HC) and those are different specimens, not different frames.
2. **Denominator.** Refereed pixels only: `1` positive, `2` or `3` negative, `0` excluded
   at both ends. `score.py` does this.
3. **Aggregation.** Per frame, then averaged -- one vote per frame, pixels never pooled.
   One B3 TXM frame holds 1,472,046 of the {sum(r['px_crack'] for r in txm):,} crack
   pixels the TXM arm has; pooling lets it carry the result.
4. **A frame needs both verdicts.** The published tables require at least
   {MIN_VERDICT_PX} px of each of crack and not-crack before a frame is scored, because
   a precision from one set of frames and a recall from another do not combine into an
   F1. On this release that is {len(both)} of the {len(rows)} frames.
5. **Read the TXM scores against the label-width row beside them, never alone.** The TXM
   brush is far wider than the feature it marks, so a pixel-overlap score there is
   agreement with a brush of that width.

The generator for the published tables is
`analysis/research/improve/overlap_means_sem_txm.py` in the `crack-fractography`
repository, run with `SCOPE_B2B3=1`. The frame set it enumerates is the frame set here.

---

## What is and is not validated in this release

**Checked by the builder, and it fails rather than warns:**

- Every frame's annotation lines up with its image at the recorded crop ({len(rows)}/{len(rows)}).
- Every annotation value is one of `0 1 2 3` -- no other value anywhere.
- The TXM `*_paint.png` reads back bit-equal to the `*_paint.npy` beside it.
- Each Zenodo archive matches the md5 its record entry declares, before anything is
  extracted from it.
- No absolute path and no personal directory name anywhere in the tree -- every file is
  scanned byte by byte, not just the text ones, and the totals and any hits are in
  `checks.json` under `no_absolute_paths`.
- `MANIFEST.sha256` carries a sha256 and a byte size for every file.

**Not validated, and not claimed:**

- **Annotation coverage is partial and uneven.** `px_reviewed / px_total` per frame is in
  `metadata.csv`; it is not uniform and must not be treated as if it were.
- **The TXM pixel size rests on two operator statements** (a 30 um window and a 0.35
  overlap) that have not been checked against an acquisition record. Lengths in nanometres
  scale with them; ratios do not.
- **The TXM acquisition parameters are unrecorded.** Not missing from this release --
  missing from the source.
- **The Inconel 718 annotation protocol is undocumented** (above), and that record
  publishes no pixel size.
- **Nothing here establishes that a score on one arm predicts a score on the other.** The
  two arms are different instruments at pixel sizes that differ by one to two orders of
  magnitude, on overlapping but not identical specimens.
- **The 1490x1490 annotation on `260708_316_H_b2_front_CBS_001` covers a 1490x1490 window
  of a 3072x2188 frame.** It is aligned, but it is a small part of that frame.

---

## Files

- `metadata.csv` / `frames.json` -- the same content in two formats: one row per frame
  with modality, specimen series, session date, instrument and detector where recoverable,
  pixel dimensions of image and mask, the resolved crop box, `nm_per_px`, `scale_source`,
  a one-line `scale_note`, and the full four-state pixel histogram.
- `checks.json` -- what every check actually found, including the `txm_group()` source
  text the scope was decided with.
- `MANIFEST.sha256` -- sha256 and byte size for every file.
- `loader.py` -- `load(frame_id)` returns image plus `crack` / `not_crack` / `reviewed`.
  Raises `FrameShapeError` rather than guessing when anything disagrees.
- `score.py` -- precision, recall, F1, IoU and area ratio over reviewed pixels, with the
  precision bracket beside them. No balanced accuracy and no MCC, by the author's
  instruction and because both are dominated by the not-crack coverage rather than by the
  detector.
- `evidence/sem_databar/` -- the panel crops the hand-transcribed scale-bar annotation and
  printed field width were read from.

Run either file directly for a demonstration:

```
python loader.py                       # first SEM and first TXM frame
python loader.py <frame_id>
python score.py <frame_id> <prediction.png>
```
"""
    write_text(os.path.join(out, "README.md"), body)


def build_licensing(out, zen):
    zen_files, upstream = "", []
    if zen:
        zen_files = "\n".join(f"- `{k}`, {human(s)}, md5 `{m}`"
                              for k, _p, s, m in zen["files"])
        seen = set()
        for key in zen["census"]:
            for part in key.replace(":", "/").split("/"):
                if re.match(r"(MetalDAM|UHCS|EBC|Al-Zn|Ni-super|Inconel|inconel)", part):
                    seen.add(part)
        upstream = sorted(seen)
    body = f"""\
# Licensing

**This file states the licence of each subtree separately, because they are not the same
and the difference matters for redistribution.** It exists so that the decision to publish
the `inconel718/` subtree is made with the facts in front of whoever makes it.

---

## 1. The laboratory data -- `sem/`, `txm/`, `previews/`, `evidence/`, and the tables

**Creative Commons Attribution 4.0 International (CC BY 4.0).**
Copyright (c) 2026 Jiaming Zhang.

This is the licence the two source repositories place on their experimental data:

- `sem-crack-detector/LICENSE-DATA` -- CC BY 4.0, covering the original micrographs and
  the human correction labels.
- `TXM_Crack_Detection_Pipeline/LICENSE-DATA` -- CC BY 4.0, covering `images/`,
  `dataset_cache/` and `paint/corrections/`.

You may share and adapt it for any purpose, including commercially, with attribution, a
link to the licence, and an indication of changes. Full text:
https://creativecommons.org/licenses/by/4.0/

`loader.py`, `score.py` and the builder that produced this tree are software, and follow
the MIT licence of the repositories they came from.

---

## 2. The Inconel 718 subtree -- `inconel718/`

**As received: Zenodo record {ZENODO_RECORD}, marked CC BY 4.0, DOI
`10.5281/zenodo.{ZENODO_RECORD}`.**

Tian, Jiayi (Zhejiang University). *Cross-Material Few-Shot Segmentation for Generalizable
Microstructure Analysis.* Zenodo, 2026-09-29. The record's own `metadata.license.id` is
`cc-by-4.0` and its access right is `open`. The files received:

{zen_files or "(the Zenodo stage was skipped on this build)"}

### What the record's own directory names show

The archives are organised by target class, and the class names are not one collection.
The folder names observed in this download:

{chr(10).join('- `' + d + '`' for d in upstream) or "- `MetalDAM_*`, `UHCS_*`, `EBC_*` (the Zenodo stage was skipped on this build; these are the names recorded on earlier reads of the record)"}

The `MetalDAM_`, `UHCS_` and `EBC_` prefixes identify **at least three upstream datasets
that this record re-publishes**:

- **MetalDAM** -- a metallographic damage-segmentation dataset, published separately by
  its own authors.
- **UHCS** -- the ultrahigh-carbon-steel micrograph collection, published separately by
  its own authors.
- **EBC** -- environmental barrier coating SEM, whose upstream is NASA MicroNet EBC-1
  (identical filenames).

### The specific conflict

**MetalDAM's own licence is Creative Commons Attribution-NonCommercial-NoDerivatives 4.0
(CC BY-NC-ND 4.0).** NoDerivatives forbids distributing a modified or adapted form of the
work, and NonCommercial restricts the purposes for which it may be shared at all. A
CC BY-NC-ND work cannot be relicensed as CC BY by a third party who re-publishes it, and
it cannot be redistributed as part of a derivative collection.

**Zenodo record {ZENODO_RECORD} is nonetheless marked CC BY 4.0 in its entirety.**

### What follows from that

The depositor has applied a permissive licence to an archive that contains at least one
upstream work whose own licence does not permit that. Whether or not that was intended,
the consequence for anyone downstream is concrete:

> **Redistributing the `inconel718/` subtree publicly carries a risk that the depositor
> has passed on.** A recipient who relies on the record's CC BY 4.0 marking inherits the
> depositor's licensing assumption rather than a clean grant from each upstream author.

Two further facts, stated because they bear on the same decision:

- This build extracts **only the Inconel 718 members** of the archives. The MetalDAM, UHCS
  and EBC members were not extracted and are not in this tree. The conflict above is about
  the record's licence marking, which covers the whole deposit; it is not a claim that
  MetalDAM files are present here.
{_undeclared_bullet(zen)}

### What this file does not do

It does not tell you whether to publish. The author has decided to assemble this folder;
this file records the facts so that the separate decision to publish the `inconel718/`
subtree is made by the author, with those facts visible. If that subtree is removed before
publication, nothing else in this release depends on it: `sem/`, `txm/`, `loader.py`,
`score.py` and every number in `metadata.csv` stand alone.

---

## 3. Attribution

If you use the laboratory arms:

> Jiaming Zhang, *Crack fractography: SEM and TXM of fatigue cracks in 316L stainless
> steel, specimen series b2 and b3, with hand annotations.* 2026. CC BY 4.0.

If you use the Inconel 718 subtree, cite the Zenodo record as well:

> Tian, Jiayi. *Cross-Material Few-Shot Segmentation for Generalizable Microstructure
> Analysis.* Zenodo, 2026. doi:10.5281/zenodo.{ZENODO_RECORD}.

See `CITATION.cff` for the machine-readable form.
"""
    write_text(os.path.join(out, "LICENSING.md"), body)


def _series_phrase(rows):
    """"b2 (SEM and TXM) and b3 (TXM only)" -- whichever is actually true here.

    The SEM arm is b2 only, because no b3 SEM frame has a correction mask. Writing
    "series b2 and b3" without that qualifier would overstate the SEM arm in the two
    places a reader is most likely to quote from.
    """
    where = {}
    for r in rows:
        where.setdefault(r["specimen_series"], set()).add(r["modality"])
    parts = []
    for ser in sorted(where):
        mods = sorted(where[ser])
        parts.append(f"{ser} ({' and '.join(mods)}{' only' if len(mods) == 1 else ''})")
    return " and ".join(parts)


def build_citation(out, rows):
    sem = sum(1 for r in rows if r["modality"] == "SEM")
    txm = sum(1 for r in rows if r["modality"] == "TXM")
    series = _series_phrase(rows)
    write_text(os.path.join(out, "CITATION.cff"), f"""\
cff-version: 1.2.0
message: "If you use this dataset, please cite it as below."
title: "{DATASET_NAME}: SEM and TXM of fatigue cracks in 316L stainless steel, specimen series {series}, with four-state hand annotations"
abstract: >-
  {sem} scanning electron and {txm} transmission X-ray microscopy frames of fatigue cracks
  in 316L stainless steel, specimen series {series}, each with a four-state hand
  annotation (unreviewed / crack / not-crack / not-crack-by-erasure) in which the
  unreviewed state is preserved and excluded from every denominator. Pixel size is
  recovered from the instrument databar where it survives and recorded as null where it
  does not; it is never defaulted. Distributed beside the public Inconel 718 crack
  collection of Zenodo record {ZENODO_RECORD}, which is covered by its own licence -- see
  LICENSING.md.
type: dataset
authors:
  - family-names: Zhang
    given-names: Jiaming
version: "1"
date-released: "{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
license: CC-BY-4.0
keywords:
  - fatigue crack
  - 316L stainless steel
  - scanning electron microscopy
  - transmission X-ray microscopy
  - semantic segmentation
  - partial annotation
references:
  - type: dataset
    title: "Cross-Material Few-Shot Segmentation for Generalizable Microstructure Analysis"
    authors:
      - family-names: Tian
        given-names: Jiayi
        affiliation: "Zhejiang University"
    doi: "10.5281/zenodo.{ZENODO_RECORD}"
    year: 2026
    notes: >-
      Source of the inconel718/ subtree. Marked CC BY 4.0; see LICENSING.md for the
      upstream licence conflict that marking carries.
""")


def build_data_availability(out, rows, zen):
    sem = [r for r in rows if r["modality"] == "SEM"]
    txm = [r for r in rows if r["modality"] == "TXM"]
    scaled = [r for r in sem if r["nm_per_px"]]
    series = _series_phrase(rows)
    write_text(os.path.join(out, "DATA_AVAILABILITY.md"), f"""\
# Data availability

A paragraph the manuscript can use as written.

---

The laboratory data supporting this study are available as
*{DATASET_NAME}* under CC BY 4.0: {len(sem)} scanning electron micrographs and
{len(txm)} transmission X-ray mosaics of fatigue cracks in 316L stainless steel, specimen
series {series}, each with the four-state hand annotation used in the analysis
(0 unreviewed, 1 crack, 2 not-crack, 3 not-crack by erasure), together with per-frame
metadata, a loader and the scoring script. The unreviewed state is preserved and is
excluded from every denominator reported here. Pixel size is given per frame where it
could be recovered from the instrument databar ({len(scaled)} of the {len(sem)} SEM
frames) and is recorded as null, with the reason, where it could not; the TXM pixel size
of {TXM_NM_PER_PX} nm/px is derived from mosaic geometry rather than read from an
instrument header and is labelled as such. The public Inconel 718 collection used for
external evaluation is third-party data, obtained from Zenodo record {ZENODO_RECORD}
(doi:10.5281/zenodo.{ZENODO_RECORD}) and redistributed subject to the terms recorded in
that record{'' if zen else ' (not included in this build)'}; that record publishes no
pixel size. Code to rebuild the dataset folder from its sources is in the
`crack-fractography` repository at `tools/build_release.py`.
""")


# ===================================================================================== main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help=f"output directory (default: {os.path.relpath(DEFAULT_OUT, REPO)})")
    ap.add_argument("--cache", default=None,
                    help="where the Zenodo zips are kept between runs "
                         "(default: _zenodo_cache beside --out)")
    ap.add_argument("--skip-zenodo", action="store_true",
                    help="build the two laboratory arms only; the report must say so")
    ap.add_argument("--no-previews", action="store_true")
    args = ap.parse_args()

    out = os.path.abspath(os.path.expanduser(args.out))
    cache = os.path.abspath(os.path.expanduser(
        args.cache or os.path.join(os.path.dirname(out), "_zenodo_cache")))
    for p, what in ((SEM_ORIG, "the SEM originals"), (SEM_PAINT, "the SEM paint"),
                    (TXM_IMAGES, "the TXM images"), (TXM_CORR, "the TXM corrections")):
        if not os.path.isdir(p):
            die(f"{what} directory does not exist at {p}. Set SEM_REPO / TXM_REPO, or "
                f"place the repositories as siblings of this one.")
    os.makedirs(out, exist_ok=True)

    t0 = time.time()
    size_before = tree_bytes(out)
    say("=" * 90)
    say(f"building {DATASET_NAME}")
    say("=" * 90)
    say(f"  out       {out}")
    say(f"  cache     {cache}")
    say(f"  sources   {SEM_REPO}")
    say(f"            {TXM_REPO}   (both read-only; nothing here writes to them)")
    say(f"  tree size before this run: {human(size_before)}")

    txm_group, txm_group_src = load_txm_group()
    scale_rows, scale_doc = load_databar_scale_json()
    say(f"  scale     {os.path.relpath(DATABAR_SCALE_JSON, REPO)}: "
        f"{scale_doc['n_recovered']} of {scale_doc['n_frames_examined']} b2/b3 frames "
        f"recovered from the 280-row databar")

    sem_rows, sem_problems, darkness, sem_series = build_sem(out, scale_rows)
    txm_rows, txm_problems = build_txm(out, txm_group)
    rows = sem_rows + txm_rows
    problems = sem_problems + txm_problems

    say("")
    say("source-wide audits (what the README's counts are counted from)")
    mask_audit = audit_all_sem_masks()
    say(f"  all {mask_audit['total']} SEM correction masks vs their originals: "
        + "; ".join(f"{k} {v}" for k, v in sorted(mask_audit["by_relation"].items())))
    s3_audit = audit_all_txm_state3()
    say(f"  paint state 3 across all {s3_audit['corrections_examined']} TXM corrections "
        f"in the source repository: "
        + (f"present on {len(s3_audit['with_state_3'])}" if s3_audit["with_state_3"]
           else "absent from every one"))
    if s3_audit["with_state_3"]:
        problems.append("the README says paint state 3 is absent from TXM; it is "
                        f"present on {len(s3_audit['with_state_3'])} source corrections")

    # ------------------------------------------------------------------ the Zenodo arm
    zen = None
    if args.skip_zenodo:
        say("")
        say("Inconel 718 -- SKIPPED (--skip-zenodo). This tree is incomplete.")
    else:
        say("")
        say(f"Inconel 718 -- public collection, Zenodo record {ZENODO_RECORD}")
        rec = zenodo_record()
        files = zenodo_fetch(rec, cache)
        dest = os.path.join(out, "inconel718")
        classes = zenodo_class_list(files)
        if classes:
            say(f"  the record's own class_id.txt ({classes['path']}) declares "
                f"{classes['n_declared']} classes; "
                + (f"{len(classes['declares_inconel'])} of them name Inconel"
                   if classes["declares_inconel"]
                   else "none of them names Inconel"))
        else:
            say("  the record carries no class_id.txt; the undeclared-class note is "
                "not made")
        census, n_ex, b_ex, not_image = zenodo_extract(files, dest)
        sanity = inconel_sanity(dest)
        sanity["not_extracted_non_image_members"] = not_image
        md = rec.get("metadata", {})
        zen = {"when": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
               "record": ZENODO_RECORD, "doi": rec.get("doi"),
               "title": md.get("title"), "licence": (md.get("license") or {}).get("id"),
               "publication_date": md.get("publication_date"),
               "creators": ", ".join(c.get("name", "?") for c in md.get("creators", [])),
               "files": files, "census": census, "extracted": n_ex,
               "extracted_bytes": b_ex, "sanity": sanity, "classes": classes}

    # ------------------------------------------------------------------------ previews
    if not args.no_previews:
        say("")
        say("previews")
        for r in rows:
            if not r["shape_status"].startswith("ok"):
                say(f"  {r['frame_id']}: no preview, shape unresolved")
                continue
            img = tifffile.imread(os.path.join(out, r["image_file"]))
            if img.ndim == 3:
                img = img[..., 0]
            img = img[r["crop_row0"]:r["crop_row1"], r["crop_col0"]:r["crop_col1"]]
            paint = np.array(Image.open(os.path.join(out, r["mask_file"])))
            while paint.ndim > 2:
                paint = paint[..., 0]
            p = os.path.join(out, "previews", r["modality"].lower(),
                             r["frame_id"] + ".png")
            make_preview(stretch8(img), paint, r["nm_per_px"], p)
            r["preview_file"] = os.path.relpath(p, out)
        say(f"  wrote {sum(1 for r in rows if r.get('preview_file'))} previews "
            f"({sum(1 for r in rows if r['nm_per_px'])} with a scale bar, "
            f"{sum(1 for r in rows if not r['nm_per_px'])} without, by design)")

    # -------------------------------------------------------------------------- checks
    say("")
    say("checks")
    nocrack = [r["frame_id"] for r in rows if r["px_crack"] == 0]
    nonotcrack = [r["frame_id"] for r in rows if r["px_not_crack"] == 0]
    both = [r["frame_id"] for r in rows
            if r["px_crack"] >= MIN_VERDICT_PX and r["px_not_crack"] >= MIN_VERDICT_PX]
    say(f"  paint states: every value in every published annotation is one of 0 1 2 3")
    say(f"  frames with ZERO crack pixels: {len(nocrack)}  -- recall is 0/0 on these")
    for f in nocrack:
        r = next(x for x in rows if x["frame_id"] == f)
        say(f"    {f:<34} {r['modality']:<4} not-crack {r['px_not_crack']:>11,}  "
            f"unreviewed {r['px_state_0_unreviewed']:>12,}")
    say(f"  frames with ZERO not-crack pixels: {len(nonotcrack)}  -- precision over "
        f"reviewed pixels is 1.0 by construction on these, for free")
    for f in nonotcrack:
        r = next(x for x in rows if x["frame_id"] == f)
        say(f"    {f:<34} {r['modality']:<4} crack     {r['px_crack']:>11,}  "
            f"unreviewed {r['px_state_0_unreviewed']:>12,}")
    say(f"  frames carrying at least {MIN_VERDICT_PX} px of BOTH verdicts, the only "
        f"ones an F1 is defined on: {len(both)} of {len(rows)}")
    s3_txm = sum(r["px_state_3_not_crack_erased"] for r in rows if r["modality"] == "TXM")
    s3_sem = sum(r["px_state_3_not_crack_erased"] for r in rows if r["modality"] == "SEM")
    say(f"  state 3 (erase = not-crack): SEM {s3_sem:,} px, TXM {s3_txm:,} px "
        f"-- {'absent from every TXM frame, as documented' if s3_txm == 0 else 'PRESENT ON TXM, which contradicts the README'}")

    write_text(os.path.join(out, "loader.py"), LOADER_PY)
    write_text(os.path.join(out, "score.py"),
               SCORE_PY.replace("__N_NO_NEG__", str(len(nonotcrack)))
                       .replace("__N_NO_POS__", str(len(nocrack)))
                       .replace("__N_FRAMES__", str(len(rows)))
                       .replace("MIN_PX = 200", f"MIN_PX = {MIN_VERDICT_PX}"))
    write_tables(out, rows)
    build_readme(out, rows, zen, darkness, mask_audit, s3_audit,
                 sem_series)
    build_licensing(out, zen)
    build_citation(out, rows)
    build_data_availability(out, rows, zen)

    # Everything except the two files that do not exist yet. They are scanned
    # separately below, after they are written, so nothing in the tree goes unscanned.
    paths = scan_for_paths(all_files(out, exclude=("checks.json", "MANIFEST.sha256")),
                           out)
    say(f"  absolute paths / personal directory names: scanned "
        f"{paths['files_scanned']:,} files ({human(paths['bytes_scanned'])}); "
        f"{len(paths['hits'])} hit(s)")
    for h in paths["hits"][:20]:
        say(f"    !! {h['file']}  contains {h['found']!r}")
    if paths["hits"]:
        problems.append(f"{len(paths['hits'])} file(s) in the tree contain an absolute "
                        f"path or a personal directory name")

    checks = {
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": list(SCOPE),
        "txm_group_rule": {
            "taken_from": os.path.relpath(OVERLAP_MODULE, REPO),
            "source": txm_group_src,
            "note": "lifted from that file with ast at build time; there is no second "
                    "copy of this rule anywhere in this builder",
        },
        "shape_check": {
            "frames": len(rows),
            "resolved": sum(1 for r in rows if r["shape_status"].startswith("ok")),
            "unresolved": [r["frame_id"] for r in rows
                           if not r["shape_status"].startswith("ok")],
            "by_status": {s: sum(1 for r in rows if r["shape_status"] == s)
                          for s in sorted({r["shape_status"] for r in rows})},
            "method": "detect_cracks.find_field_of_view at build time; the resolved box "
                      "is published per frame, so the loader applies four numbers and "
                      "never re-derives anything",
        },
        "paint_states": {
            "legend": {"0": "unreviewed, excluded from every denominator", "1": "crack",
                       "2": "not-crack", "3": "not-crack by erasure"},
            "pooled": {
                arm: {f"state_{i}": sum(r[k] for r in rows if r["modality"] == arm)
                      for i, k in enumerate(["px_state_0_unreviewed", "px_state_1_crack",
                                             "px_state_2_not_crack",
                                             "px_state_3_not_crack_erased"])}
                for arm in ("SEM", "TXM")},
            "state_3_absent_from_txm": s3_txm == 0,
            "frames_with_zero_crack_px": nocrack,
            "frames_with_zero_not_crack_px": nonotcrack,
            "min_px_each_verdict": MIN_VERDICT_PX,
            "frames_scoreable_on_both_verdicts": both,
            "note": "a frame with no refereed negative returns precision 1.0 over "
                    "reviewed pixels for free, and a frame with no painted crack "
                    "returns recall 0/0. score.py flags both rather than hiding them, "
                    "and a mean over frames must drop the unsupported ones.",
        },
        "scale": {
            "sem_recovered": {r["frame_id"]: r["nm_per_px"] for r in rows
                              if r["modality"] == "SEM" and r["nm_per_px"]},
            "sem_null": [r["frame_id"] for r in rows
                         if r["modality"] == "SEM" and not r["nm_per_px"]],
            "txm_nm_per_px": TXM_NM_PER_PX,
            "txm_scale_source": TXM_SCALE_SOURCE,
            "txm_provenance": TXM_SCALE_NOTE,
        },
        "sem_alignment_positive_control": {
            "what": "mean grey level of painted crack minus mean grey level of "
                    "unreviewed area, on the percentile-stretched field-of-view crop. "
                    "Negative is correct: a crack is dark. Shapes matching does not "
                    "prove the OFFSET matches; this does.",
            "per_frame_delta_grey": darkness,
        },
        "sem_series_coverage": sem_series,
        "all_sem_masks_vs_originals": mask_audit,
        "txm_state_3_across_source": s3_audit,
        "no_absolute_paths": paths,
        "zenodo": None if zen is None else {
            k: v for k, v in zen.items() if k != "files"},
        "zenodo_files": None if zen is None else [
            {"key": k, "bytes": s, "md5": m} for k, _p, s, m in zen["files"]],
        "problems": problems,
    }
    write_text(os.path.join(out, "checks.json"), json.dumps(checks, indent=1) + "\n")
    n_manifest = write_manifest(out)
    # The last two files the build writes, scanned in their turn. A hit here would be a
    # bug in this builder rather than in the data, and it is still a failure.
    late = scan_for_paths([os.path.join(out, "checks.json"),
                           os.path.join(out, "MANIFEST.sha256")], out)
    if late["hits"]:
        say("  the two generated index files, scanned after they were written:")
        for h in late["hits"]:
            say(f"    !! {h['file']}  contains {h['found']!r}")
        problems.append(f"{len(late['hits'])} generated index file(s) contain an "
                        f"absolute path or a personal directory name")

    size_after = tree_bytes(out)
    say("")
    say("=" * 90)
    say(f"tree size before: {human(size_before)}")
    say(f"tree size after:  {human(size_after)}   ({n_manifest:,} files in MANIFEST.sha256)")
    for sub in ("sem", "txm", "inconel718", "previews", "evidence"):
        p = os.path.join(out, sub)
        if os.path.isdir(p):
            say(f"    {sub + '/':<14} {human(tree_bytes(p)):>12}")
    if cache.startswith(out):
        say(f"  (the Zenodo cache is inside the tree)")
    else:
        say(f"  zenodo cache (outside the tree): {human(tree_bytes(cache))} at {cache}")
    say(f"SEM {len(sem_rows)} frames, TXM {len(txm_rows)} frames, "
        f"{'Inconel 718 ' + format(zen['extracted'], ',') + ' files' if zen else 'no Inconel subtree'}")
    say(f"built in {(time.time() - t0) / 60:.1f} min")

    # The console log, beside the tree and NOT in it: it names the absolute path of
    # every source, which is exactly what the tree is checked for not containing.
    logp = os.path.join(os.path.dirname(out), "build_release.log")
    try:
        write_text(logp, "\n".join(LOG) + "\n")
        say(f"build log: {logp}")
    except OSError:
        pass

    if problems:
        say("")
        say("!" * 90)
        say(f"{len(problems)} PROBLEM(S) -- the tree was written, and these are in "
            f"checks.json:")
        for p in problems:
            say(f"  - {p}")
        say("!" * 90)
        return 1
    say("")
    say("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
