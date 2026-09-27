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
import os
import sys as _sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
_sys.path.insert(0, REPO)
from app import paths as _P   # noqa: E402

#: Anchored by tile geometry, not by a databar: 9x5 tiles of a 30 um window at 0.35 overlap.
TXM_NM_PER_PX = 29.24

_FEI = {}


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


def nm_per_px(stem, modality="sem"):
    """nm per pixel for this frame, or None when it is not established."""
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
