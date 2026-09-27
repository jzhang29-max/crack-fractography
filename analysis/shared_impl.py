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

import numpy as np

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

    _install_memo(mod)
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
    """
    return _resolve()["module"].skeleton_stats(mask_bool)


def _install_memo(mod):
    """Give the shared module's skeleton_stats a one-entry cache, in this process only.

    WHY, with the number that forced it: measuring a region now calls skeletonize twice --
    once inside crack_shape_measurements for the shape numbers, once here for the skeleton
    the geodesic needs. On a small frame that was +24%. On the corpus's big frames
    skeletonize IS the measurement, and the doubled cost took a 35-minute batch past 34
    minutes without finishing 20 of 142 masks. Both calls pass the same region mask, so
    the second one is recomputing a pure function of an argument it has already seen.

    THE CACHE IS HERE AND NOT IN THE SEM REPO. Nothing in that repo changes; this rebinds
    one attribute on the module object inside this process. The rule it must not break is
    that the app measures exactly what that repo measures, so:
      - the key is the mask's bytes, not its id() -- an id is reused after a free, and the
        collision would hand one region another region's skeleton,
      - the cached arrays are marked read-only, so a future caller that writes to a
        skeleton it did not allocate fails loudly instead of quietly poisoning the next
        region that hashes the same,
      - tests/test_geodesic.py checks the memo returns exactly what the raw function does.
    """
    raw = getattr(mod, "skeleton_stats", None)
    if raw is None or getattr(raw, "_memo", False):
        return
    cell = {}

    def memoized(mask_bool):
        a = np.ascontiguousarray(mask_bool)
        key = (a.shape, a.dtype.str, hashlib.blake2b(a.tobytes(), digest_size=16).digest())
        if cell.get("key") != key:
            out = raw(a)
            for v in out:
                if isinstance(v, np.ndarray):
                    v.setflags(write=False)
            cell["key"], cell["val"] = key, out
        return cell["val"]

    memoized._memo = True
    memoized._raw = raw
    mod.skeleton_stats = memoized


def provenance():
    """Which implementation is in use, and whether it matches what was bundled."""
    s = _resolve()
    return {"source": s["source"], "md5": s["md5"], "vendored_md5": s["vendored_md5"],
            "drift": s["drift"],
            "note": ("the SEM repo's copy differs from the one bundled in this app -- "
                     "re-run packaging/vendor.py so a packaged build measures the same way"
                     if s["drift"] else None)}
