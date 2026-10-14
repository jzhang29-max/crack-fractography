"""The field-of-view crop fires on texture, not on a databar, and silently eats the
bottom of a small frame.  Measured, with a positive control, and a one-line guard.

WHAT IT DOES TODAY.  run_unified_pipeline's second statement is
find_field_of_view(img8), whose first statement is _detect_databar_top(img8).  That has
two signals and takes the EARLIER of the two.  Signal 2 is geometric: inside the bottom
25% of the frame it finds the row where the largest fraction of columns change by more
than 10 grey levels from the row above, and if that fraction reaches 0.60 and at least 20
rows sit below it, every row from there down is discarded as an info panel.

On a 4376-row micrograph that is correct -- the panel edge changes ~99% of the columns at
one row.  On a 512 px crop of a NOISY detector image it is a coin flip, because ordinary
row-to-row noise already changes 53-81% of the columns at EVERY row in the band.  Six of
the 26 hand-labelled tiles lose 34-127 rows this way, and the cut is invisible: the app
writes the mask at the cropped size and nothing downstream says a band was dropped.

    tile                                            bar_top  rows cut  gt px in band
    Cast_24hr_SE_Side_006__crop_3260_2586               429        83     808  (5.0%)
    HIP_24hr_SE_Side_006__crop_3853_3216                478        34       0
    HIP_24hr_SE_Side_006__crop_4695_807                 463        49       0
    MAR_Amb_Cast_ETD_0003__crop_2841_1211               424        88   1,393 (40.3%)
    MAR_H_AS_ETD_0006__crop_3658_3272                   443        69       0
    MAR_H_AS_ETD_0007__crop_3779_9                      385       127     399  (7.5%)

THE DISCRIMINATOR IS NOT THE PEAK, IT IS THE PEAK'S MARGIN.  best_frac alone does not
separate: the real panel edges run 0.648-1.000 and these six run 0.619-0.863.  What
separates completely is how far the peak stands above the rest of its own band.  A real
panel edge is the only row in the band that changes anything; noise makes every row look
alike.  Over the 121 originals in the archived repo where this signal fires, and the six
tiles:

    margin = best_frac - p95(frac over the band)
    real panel edge   min 0.279   p25 0.583   median 0.744   max 0.966   (n=121)
    the six tiles     min 0.021   p25 0.027   median 0.033   max 0.073   (n=6)

A 4x gap, so MARGIN_MIN = 0.15 is not a fitted constant in any meaningful sense -- any
value in [0.08, 0.27] gives the identical partition.  It is still a new constant and is
reported as one.

POSITIVE CONTROL, and it is the point of this file: the guard must not un-detect a single
real bar.  Over all 154 .tif in sem-crack-detector/original it returns a bar row
IDENTICAL to today's on every image that has one, including the five the module's own
docstring names as the reason signal 2 exists (MAR_Amb_Cast_CBS_0002/0005,
MAR_Amb_Cast_ETD_0002/0005, MAR_Amb_HIP_CBS_0003), which are detected by signal 2 ALONE
and whose margins are 0.84-0.97.

A SECOND, UNRELATED FALSE POSITIVE IT ALSO FIXES: the twelve apptest_*.tif fixtures are
400x600 uniform synthetic noise with no bar at all (row means 144-150 straight through the
"edge"), and today they lose 34-72 rows each.

THIS IS NOT WIRED INTO detector_overrides.py.  It is interceptable the same way the four
stage functions are -- find_field_of_view is a bare-name call inside run_unified_pipeline
-- but shipping it is a separate decision and peer sessions share this checkout.

Run:
    /Users/jiamingzhang/Desktop/APP/sem-crack-detector/.venv/bin/python -B \
        analysis/research/improve/fov_databar_guard.py
"""
import os
import sys
import glob
import warnings

warnings.filterwarnings("ignore")
import numpy as np

APP = os.path.abspath(os.environ.get(
    "APP_REPO", os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))))
SEM = os.path.abspath(os.environ.get(
    "SEM_REPO", os.path.join(os.path.dirname(APP), "sem-crack-detector")))
for _p in (APP + "/analysis/research", SEM + "/code"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.dont_write_bytecode = True

import detect_cracks as D  # noqa: E402

MARGIN_MIN = 0.15


def detect_databar_top(img8, search_frac=0.25, window=10, std_ratio=0.4,
                       mean_ratio=0.85, margin_min=MARGIN_MIN):
    """detect_cracks._detect_databar_top with signal 2 required to stand out of its band."""
    h, w = img8.shape
    search_start = int(h * (1 - search_frac))
    rows = img8[search_start:].astype(np.float32)
    if rows.shape[0] < window + 5:
        return h

    bar_top_stat = h
    row_means, row_stds = rows.mean(axis=1), rows.std(axis=1)
    for i in range(window, len(row_means)):
        if (row_stds[i - window:i].max() > 3
                and row_stds[i] < row_stds[i - window:i].max() * std_ratio
                and row_means[i] < row_means[i - window:i].max() * mean_ratio):
            bar_top_stat = search_start + i
            break

    bar_top_edge = h
    frac = np.array([float((np.abs(rows[i] - rows[i - 1]) > 10).mean())
                     for i in range(1, rows.shape[0])])
    if len(frac):
        b = int(frac.argmax())
        best_frac, best_row = float(frac[b]), search_start + b + 1
        # THE ONLY CHANGE: the peak must also stand clear of the rest of the band.
        margin = best_frac - float(np.percentile(frac, 95))
        if best_frac >= 0.60 and h - best_row >= 20 and margin >= margin_min:
            bar_top_edge = best_row
    return min(bar_top_stat, bar_top_edge)


def find_field_of_view(img8, **kw):
    """find_field_of_view with the guarded databar detector, by temporary rebinding.

    detect_cracks is archived and read-only, so the private name is swapped for the
    duration of the call and restored, rather than the file being edited.
    """
    old = D._detect_databar_top
    D._detect_databar_top = lambda a, **k: detect_databar_top(a, **k)
    try:
        return D.find_field_of_view(img8, **kw)
    finally:
        D._detect_databar_top = old


def main():
    import tifffile
    from PIL import Image
    from skimage import exposure
    import tilebench as TB
    Image.MAX_IMAGE_PIXELS = None

    print("=" * 96)
    print("POSITIVE CONTROL -- every original in the archived repo keeps the bar row it has today")
    print("=" * 96)
    files = sorted(glob.glob(os.path.join(SEM, "original", "*.tif")))
    changed, same_bar, same_none, apptest = [], 0, 0, 0
    for f in files:
        a = tifffile.imread(f)
        if a.ndim == 3:
            a = a[..., 0]
        lo, hi = np.percentile(a, [1.0, 99.5])
        img8 = exposure.rescale_intensity(a.astype(np.float32), in_range=(lo, hi),
                                          out_range=(0, 255)).astype(np.uint8)
        old = D._detect_databar_top(img8)
        new = detect_databar_top(img8)
        if old == new:
            same_bar += (old < img8.shape[0])
            same_none += (old == img8.shape[0])
        else:
            changed.append((os.path.basename(f), img8.shape[0], old, new))
            apptest += "apptest" in f
    print(f"  {len(files)} originals")
    print(f"  bar row UNCHANGED and a bar is found : {same_bar}")
    print(f"  no bar before, no bar after          : {same_none}")
    print(f"  CHANGED                              : {len(changed)}  "
          f"({apptest} of them apptest_* fixtures)")
    for n, h, o, nw in changed:
        print(f"      {n:<28} h={h}  {o} -> {nw}")
    assert not [c for c in changed if "apptest" not in c[0]], \
        "the guard moved a real micrograph's bar row"

    print()
    print("=" * 96)
    print("THE 26 TILES -- how many rows the crop eats, before and after")
    print("=" * 96)
    tiles = TB.load()
    before = after = 0
    for t in tiles:
        h = t["img8"].shape[0]
        o = D.find_field_of_view(t["img8"])[3]
        n = find_field_of_view(t["img8"])[3]
        if o < h or n < h:
            lost_o = int(t["gt"][o:].sum())
            print(f"  {t['frame'][:50]:<50} y1 {o:>4} -> {n:>4}   "
                  f"gt px returned {lost_o - int(t['gt'][n:].sum()):>6,}")
        before += h - o
        after += h - n
    print(f"  rows discarded over the 26 tiles: {before} -> {after}")


if __name__ == "__main__":
    main()
