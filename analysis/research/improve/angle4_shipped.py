"""The v1.49.1 shipped candidate stage, importable, taken from detector_overrides.install().

Nothing here reimplements the union. install() is called on a stand-in module and the
function it binds is the one used, so this cannot drift from what the app runs. The
ladder-collapse control (SCALE_LADDER -> (40,) must reproduce the stock single-scale cut
bit for bit) lives in selfcheck() and every script that imports this runs it first.

Shipped path after v1.49.1: multi-scale darkness union at mad_k=5.0, region classifier OFF.
"""
import os, sys
import numpy as np
from scipy import ndimage as ndi

SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
APP = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
for p in (APP + "/analysis/research", APP + "/analysis", SEM + "/code",
          SEM + "/interior_active_learning/code"):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True
import detect_cracks as D            # noqa: E402
import detector_overrides as DO      # noqa: E402

MIN_AREA = 13


class _FakeUP:
    pass


def seg_fn(ladder=None, mad_k=5.0):
    up = _FakeUP()
    kw = dict(use_multiscale_union=True, mad_k=mad_k)
    if ladder is not None:
        kw["scale_ladder"] = ladder
    DO.install(up, **kw)
    return up.segment_dark_regions


_SEG = {}


def shipped_clean(img8, mad_k=5.0, ladder=None, min_area=MIN_AREA):
    """The candidate mask the app ships: union darkness cut, cleaned. Classifier OFF, so
    this IS the prediction -- no region is rejected downstream."""
    key = (ladder, mad_k)
    if key not in _SEG:
        _SEG[key] = seg_fn(ladder, mad_k)
    flat = D.flatten_background(img8, sigma=40)
    dark = _SEG[key](flat, img8=img8, mad_k=mad_k)
    return D.clean_mask(dark, open_radius=1, close_radius=3, min_area_px=min_area)


def single_scale_clean(img8, mad_k=5.0, min_area=MIN_AREA):
    """v1.48: detect_cracks' own stock cut at sigma=40, unmodified."""
    flat = D.flatten_background(img8, sigma=40)
    # img8 must be passed: the stock cut ORs in the absolute-darkness term, and the
    # multiscale override ORs in the same term. Omitting it here made the collapse
    # control fail on a tile containing a void -- the control caught it, which is what
    # it is for.
    dark = D.segment_dark_regions(flat, mad_k=mad_k, img8=img8)
    return D.clean_mask(dark, open_radius=1, close_radius=3, min_area_px=min_area)


def selfcheck(img8s):
    """Two controls that must hold before any number from this module is read."""
    ok = True
    for i, img8 in enumerate(img8s):
        a = single_scale_clean(img8)
        b = shipped_clean(img8, ladder=(40,))
        same = np.array_equal(a, b)
        sup = bool((shipped_clean(img8) | a == shipped_clean(img8)).all())
        ok &= same and sup
        if not (same and sup):
            print(f"  FAIL image {i}: ladder-collapse={same} superset={sup}")
    print(f"  {'PASS' if ok else 'FAIL'}  ladder=(40,) reproduces the stock single-scale "
          f"cut exactly, and the full ladder is a strict superset  "
          f"({len(img8s)} image(s))")
    assert ok
    return ok


def labels_of(mask):
    lab, n = ndi.label(mask, structure=np.ones((3, 3), bool))
    return lab, n
