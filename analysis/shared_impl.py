#!/usr/bin/env python3
"""Resolve the shared per-region measurement implementation: live repo first, vendor second.

The rule this file enforces is that there is only ever ONE implementation in play and the
app can always say which. See packaging/vendor.py for why a copy exists.

Order:
  1. the configured SEM checkout's interior_active_learning/code/extended_features.py
  2. analysis/_vendor/extended_features.py, the byte copy shipped inside the app

When (1) is used and its bytes differ from what was vendored, that is not an error -- the
live file is the source of truth and it won. But it means the bundle would measure
differently, so the difference is surfaced through provenance() and shown in the app rather
than discovered later as an unexplained gap between two runs.
"""
import hashlib
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(_HERE, "_vendor")
_STATE = {}


def _md5(p):
    try:
        return hashlib.md5(open(p, "rb").read()).hexdigest()
    except OSError:
        return None


def _load_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _resolve():
    if _STATE:
        return _STATE
    sys.path.insert(0, os.path.dirname(_HERE))
    try:
        from app import paths as P
        sem = P.sem_repo()
    except Exception:
        sem = None

    rel = "interior_active_learning/code/extended_features.py"
    vendored = os.path.join(VENDOR, "extended_features.py")
    try:
        recorded = json.load(open(os.path.join(VENDOR, "MANIFEST.json")))["files"][rel]
    except Exception:
        recorded = None

    live = os.path.join(sem, *rel.split("/")) if sem else None
    if live and os.path.exists(live):
        mod, src, path = _load_from(live, "extended_features"), "sem repo", live
    elif os.path.exists(vendored):
        mod, src, path = _load_from(vendored, "extended_features"), "bundled copy", vendored
    else:
        raise ImportError(
            "no measurement implementation available: neither a configured SEM repo nor "
            f"the bundled copy at {vendored}")

    digest = _md5(path)
    _STATE.update(module=mod, source=src, path=path, md5=digest,
                  vendored_md5=recorded,
                  drift=(src == "sem repo" and recorded is not None and digest != recorded))
    return _STATE


def reset():
    """Forget which implementation answered, so the next call resolves again.

    The resolution is cached for the life of the process, which is right for a batch run and
    WRONG the moment the SEM repo can be configured while the server is up: the first
    uploaded mask resolves to the bundled copy, and every measurement after that keeps using
    it even once a repo is set. Caught 2026-09-26 -- health reported "bundled copy" with a
    valid repo configured. Identical files make this invisible; a repo whose copy has moved
    on makes it a silent mismatch with that repo's own published numbers, which is the exact
    failure vendoring was allowed to risk only because the live copy wins.
    """
    _STATE.clear()
    sys.modules.pop("extended_features", None)


def crack_shape_measurements(mask_bool):
    return _resolve()["module"].crack_shape_measurements(mask_bool)


def skeleton_stats(mask_bool):
    """The same module's skeletonization, so the geodesic runs on the SAME skeleton.

    analysis/geodesic.py needs the skeleton ARRAY, which crack_shape_measurements does not
    return -- it returns numbers. Going through here rather than importing skeletonize
    directly keeps the one-implementation rule: whichever copy won the resolution above is
    the copy that produces both the skeleton and the length summed over it, and the
    geodesic asserts its own graph sums to that length before emitting anything.

    This does mean each region is skeletonized twice (~20% on the batch, measured). The
    alternative is a cache keyed on the mask bytes inside the SHARED module, which would
    make a number in this app depend on an optimisation in a repo this app does not own.
    """
    return _resolve()["module"].skeleton_stats(mask_bool)


def provenance():
    """Which implementation is in use, and whether it matches what was bundled."""
    s = _resolve()
    return {"source": s["source"], "md5": s["md5"], "vendored_md5": s["vendored_md5"],
            "drift": s["drift"],
            "note": ("the SEM repo's copy differs from the one bundled in this app -- "
                     "re-run packaging/vendor.py so a packaged build measures the same way"
                     if s["drift"] else None)}
