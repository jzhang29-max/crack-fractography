#!/usr/bin/env python3
"""Where everything lives -- the ONE place that answers it.

A repo checkout and a double-clickable app disagree about every path, and the disagreement
is not cosmetic:

  READ-ONLY vs WRITABLE. In a checkout, code and output share a tree and everything is
  writable. Inside a .app the code lives in a signed, read-only bundle that is replaced
  wholesale on update. Writing measurements next to the code would either fail or be
  destroyed by the next version.

  THE SIBLING REPOS ARE SYMLINKS. data/sem, data/txm_export are relative links to repos
  beside this one. A downloaded app has no siblings, so those locations become configuration
  -- a path the user gives us once -- and every consumer has to ask for them by function
  call rather than by joining REPO.

Every module that used to build a path out of `os.path.dirname(__file__)` now asks here, so
there is one definition to get right instead of six that drift.

Dev behaviour is deliberately unchanged: in a checkout DATA is analysis/out and the sibling
links are used exactly as before, so nothing about the existing workflow moves.
"""
import json
import os
import sys

#: True when running from a PyInstaller bundle.
FROZEN = bool(getattr(sys, "frozen", False))

#: Read-only resources: the code, templates and static files as shipped.
RES = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The checkout root when running from source; None when frozen (there is no checkout).
REPO = None if FROZEN else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _user_data_root():
    """A per-user directory that survives replacing the app."""
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Crack Fractography")
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        return os.path.join(base, "Crack Fractography")
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "crack-fractography")


#: Everything this app writes. Overridable so a test never touches the real one.
DATA = os.environ.get("FRACTOGRAPHY_DATA") or (
    _user_data_root() if FROZEN else os.path.join(REPO, "analysis", "out"))

OUT = DATA
UPLOADS = os.path.join(DATA, "uploads")
CONFIG_PATH = os.path.join(DATA, "config.json")


def ensure_dirs():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(UPLOADS, exist_ok=True)


# ---------------------------------------------------------------------------------------
# Configuration: the paths we cannot discover.
_CFG = None


def config():
    global _CFG
    if _CFG is None:
        try:
            _CFG = json.load(open(CONFIG_PATH))
        except Exception:
            _CFG = {}
    return _CFG


def set_config(**kw):
    cfg = dict(config())
    cfg.update({k: v for k, v in kw.items() if v is not None})
    ensure_dirs()
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(cfg, fh, indent=2)
    os.replace(tmp, CONFIG_PATH)
    globals()["_CFG"] = cfg
    return cfg


def _resolved(key, dev_link):
    """Configured path first, then the dev symlink, then nothing. Never a stale answer:
    a configured path that has since been moved or deleted resolves to None, so the app
    reports it as missing instead of failing later inside a subprocess."""
    p = config().get(key)
    if p and os.path.isdir(p):
        return os.path.realpath(p)
    if REPO:
        d = os.path.join(REPO, "data", dev_link)
        if os.path.isdir(d):
            return os.path.realpath(d)
    return None


def sem_repo():
    """The sem-crack-detector checkout, or None."""
    return _resolved("sem_repo", "sem")


def txm_export():
    """The txm_crack_export tree, or None."""
    return _resolved("txm_export", "txm_export")


def txm_export_machine():
    """The TXM MODEL-ONLY mask tree, or None.

    WHY THERE ARE TWO TXM TREES. txm_export() holds the archive the pipeline's own
    api_export_all writes, and that archive is built with corrections="gate": inside a
    hand-painted crack stroke the model's threshold drops to CORRECTION_FLOOR, and an erase
    stroke is absolute in every mode. 61 of its 71 frames carry crack strokes and 70 carry
    erase strokes, so the archive is a HUMAN-GATED mask -- the TXM analogue of the SEM
    repo's gated_masks, not of its machine_masks.

    A user looking at the TXM masks saw the brush in them and asked for the model's own
    output. There was no TXM analogue of machine_masks anywhere, so the question could not
    be asked of this corpus from outside the pipeline app. This tree is that arm: the same
    deployed model, the same threshold, pruning, hole-filling and tightening, with
    corrections="none" as the single difference.

    Resolution mirrors txm_export, plus one convenience: a sibling of the gated tree whose
    name is the gated tree's name with "_machine" appended, which is where
    rebuild_export.py --corrections none writes by default.
    """
    p = _resolved("txm_export_machine", "txm_export_machine")
    if p:
        return p
    tx = txm_export()
    if tx:
        sib = tx.rstrip("/") + "_machine"
        if os.path.isdir(sib):
            return os.path.realpath(sib)
    return None


def txm_images():
    """The directory of TXM ORIGINAL .tif mosaics, or None.

    WHY THIS IS SEPARATE FROM txm_export. The export tree holds one crack mask per frame
    and nothing else -- I checked it, found only `<frame>_crack_mask.png`, and concluded
    there was no TXM original to draw an overlay on. That was wrong: the originals live in
    the TXM pipeline repo, in its own images/ directory, 71 .tif files whose names match
    the 71 exported frames exactly and whose pixel dimensions match the masks exactly
    (5039x3703 on the frame I compared). The mask tree was simply not where they are.

    The consequence of getting that wrong was visible: the Mark tab showed TXM as a
    black-and-white mask while SEM showed a red overlay on the micrograph, and a user said
    so. A binary mask is the measurement's input, not a picture of the specimen.

    Resolution order matches every other path here -- configured, then the dev symlink --
    with one addition: the pipeline repo sits beside txm_crack_export in practice, so a
    sibling named TXM_Crack_Detection_Pipeline/images is tried before giving up. That is a
    convenience, not a contract; Setup can point it anywhere.
    """
    p = _resolved("txm_images", "txm_images")
    if p:
        return p
    tx = txm_export()
    if tx:
        sib = os.path.join(os.path.dirname(tx), "TXM_Crack_Detection_Pipeline", "images")
        if os.path.isdir(sib):
            return os.path.realpath(sib)
    return None


def sem_derived():
    s = sem_repo()
    return os.path.join(s, "crack_export", "derived") if s else None


def sem_python():
    """The SEM repo's own interpreter -- the only one that can run the detector, because the
    model bundle is pickled against that venv's scikit-learn. Returns None if not built."""
    s = sem_repo()
    if not s:
        return None
    p = os.path.join(s, ".venv", "bin", "python3")
    if os.name == "nt":
        p = os.path.join(s, ".venv", "Scripts", "python.exe")
    return p if os.path.exists(p) else None


def sem_code_dirs():
    """Import paths inside the SEM repo, in the order they should be searched."""
    s = sem_repo()
    if not s:
        return []
    return [d for d in (os.path.join(s, "interior_active_learning", "code"),
                        os.path.join(s, "code")) if os.path.isdir(d)]


def check_sem_repo(path):
    """Is `path` a usable sem-crack-detector? Returns (ok, list_of_findings).

    Checked by what this app actually needs, one line per need, so a wrong folder says which
    piece is missing rather than 'invalid'.
    """
    out, ok = [], True
    if not path or not os.path.isdir(path):
        return False, [("missing", "that folder does not exist")]
    need = {
        "measurement code": os.path.join(path, "interior_active_learning", "code",
                                         "extended_features.py"),
        "detector": os.path.join(path, "interior_active_learning", "code",
                                 "unified_pipeline.py"),
        "model bundle": os.path.join(path, "models", "crack_classifier.joblib"),
    }
    for label, p in need.items():
        if os.path.exists(p):
            out.append(("ok", label))
        else:
            out.append(("missing", label))
            ok = False
    py = os.path.join(path, ".venv", "bin", "python3")
    if os.name == "nt":
        py = os.path.join(path, ".venv", "Scripts", "python.exe")
    if os.path.exists(py):
        out.append(("ok", "virtualenv (needed to segment raw micrographs)"))
    else:
        out.append(("warn", "virtualenv not built -- run ./run in that repo once before "
                            "uploading a raw micrograph"))
    return ok, out
