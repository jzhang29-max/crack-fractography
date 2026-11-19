#!/usr/bin/env python3
"""The five width-clip constants Figure 6 letters F, measured.

WHY THIS EXISTS. paper/figures/mk_parameters.py prints eight TXM rows whose names begin
"clip". Five of them carry the letter F and a WHY_F_IS_TRUE string that says, in as many
words, that nothing in either repository measures them:

    clip IDW neighbours    "a one-line description in the source, no measurement"
    clip background (px)   "three window sizes with no comment and no measurement"
    clip directions        "a one-line description in the source, no measurement"
    clip radius (px)       "a one-line description in the source, no measurement"
    clip recentre (px)     "slack for a skeleton sitting off the ridge; no measurement"

They all belong to one step, TXM_Crack_Detection_Pipeline/app/core/pipeline.py:

    WIDTH_CLIP_RADIUS      = 200            line 596
    WIDTH_CLIP_DIRS        = 12             line 597
    WIDTH_CLIP_RECENTRE    = 3              line 599
    WIDTH_CLIP_BG_WINDOWS  = (301,901,2401) line 610
    WIDTH_CLIP_IDW_K       = 12             line 612

read by local_background (line 615), _transverse_fwhm (line 639) and
clip_to_measured_width (line 675). That step is LIVE: effective_mask -> _narrow_to_image
-> clip_to_measured_width, reached whenever tight is set, and app/server.py's _tight()
defaults to True, so every export and every overlay the application serves goes through
it. paper/figures/mk_flow.py:233 and mk_txm_ceiling.py both reproduce
effective_mask(corrections="none", tight=True), so the manuscript's TXM masks are its
output too.

WHAT IS SCORED, AND WHAT IS NOT. Not IoU against the hand-painted TXM masks. This project
measured that a correct 3 px crack scores IoU 0.0498 there because the operator painted
with a broad brush (docs/figures/txm_iou_ceiling_v2.json, median label width 23 px), so
TXM IoU ranks brush imitation and cannot rank a width estimator. Scored instead:

  half_width_med   the step's OWN output: the median, over every skeleton pixel, of the
                   transverse half-width it read off the image. This is the quantity the
                   five constants exist to produce.
  measured_frac    n_measured / n_probe -- how many probes yielded a width at all
  keep             clipped area / input area -- what the step does to the mask
  mean_width_px    area / skeleton length of the clip output: a skeleton-based width,
                   independent of the FWHM estimator, so the two cannot agree by
                   construction
  rough_p99        99th percentile of |delta half-width| between 8-adjacent skeleton
                   pixels, recovered from the output by EDT. This is the statistic the
                   IDW comment's claim is about ("nearest-probe makes the field piecewise
                   constant ... the clip boundary then follows the cell edges")
  jaccard_vs_shipped   swept clip output against shipped clip output, mask against mask.
                   Not against human paint.

A POSITIVE CONTROL SETS THE CEILING. Before any swept number is read, the shipped
estimator is run on synthetic bands of KNOWN width, at known angles, with known
background shading, by calling the shipped _transverse_fwhm and local_background on
arrays. If the instrument cannot recover a width it was handed, no number below means
anything.

CONTROLS THAT FAIL LOUDLY. Every one of these raises rather than warns:
  1  _narrow_to_image(..., True) == effective_mask(corrections="none", tight=True)
  2  the staged reconstruction used here == that same shipped mask, on every frame
  3  the patch harness at shipped settings == an unpatched shipped call, bit for bit
  4  every swept clip output is a SUBSET of its input (the step may only remove)
  5  the memoised local_background returns what the shipped one returns
  6  the positive control recovers the synthetic widths

READ ONLY. Nothing under TXM_Crack_Detection_Pipeline is written, and paint/corrections/
is never opened.

Run:  <txm-venv>/bin/python -B analysis/research/improve/txm_clip_constants.py
Writes docs/figures/txm_clip_constants.json and nothing else.
"""
import json
import os
import sys
import time
from hashlib import blake2b

import numpy as np

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "paper", "figures"))

import _paths                                           # noqa: E402

TXM = _paths.require(_paths.TXM_REPO, "the TXM_Crack_Detection_Pipeline checkout",
                     "TXM_REPO")
sys.path.insert(0, os.path.join(TXM, "code"))
sys.path.insert(0, os.path.join(TXM, "app"))

import core.pipeline as PL                              # noqa: E402  the shipped step
import core.store as S                                  # noqa: E402

from scipy.ndimage import distance_transform_edt        # noqa: E402
from skimage.morphology import skeletonize              # noqa: E402

OUT = os.path.join(REPO, "docs", "figures", "txm_clip_constants.json")
CEIL = os.path.join(REPO, "paper", "figures", "txm_iou_ceiling_v2.json")

#: 29 nm/px, the TXM scale this project anchored by tile geometry.
NM_PER_PX = 29.0

#: The specimen series the paper reports on. AM and WR frames are other specimens; the
#: 24 B2/B3 frames are the scope every other TXM record in this repository uses.
GROUPS = ("B2", "B3")
NFRAMES = int(os.environ.get("NFRAMES", "0"))           # 0 = all of them

#: Where each constant lives, so the mapping is in the record and not only in a chat log.
SOURCE = {
    "WIDTH_CLIP_RADIUS": "app/core/pipeline.py:596",
    "WIDTH_CLIP_DIRS": "app/core/pipeline.py:597",
    "WIDTH_CLIP_RECENTRE": "app/core/pipeline.py:599",
    "WIDTH_CLIP_BG_WINDOWS": "app/core/pipeline.py:610",
    "WIDTH_CLIP_IDW_K": "app/core/pipeline.py:612",
}
ROW = {
    "WIDTH_CLIP_RADIUS": "clip radius (px)",
    "WIDTH_CLIP_DIRS": "clip directions",
    "WIDTH_CLIP_RECENTRE": "clip recentre (px)",
    "WIDTH_CLIP_BG_WINDOWS": "clip background (px)",
    "WIDTH_CLIP_IDW_K": "clip IDW neighbours",
}
SHIP = {k: getattr(PL, k) for k in SOURCE}

#: Each grid brackets the shipped value by at least an order of magnitude either side
#: where that is meaningful. recentre cannot go below 0 (0.1x of 3 is 0.3, and the
#: constant indexes a slice), so 0 -- no slack at all -- is the floor.
GRIDS = {
    "WIDTH_CLIP_RADIUS": [20, 50, 100, 200, 400, 800, 2000],
    "WIDTH_CLIP_DIRS": [2, 3, 4, 6, 8, 12, 24, 48, 120],
    "WIDTH_CLIP_RECENTRE": [0, 1, 2, 3, 5, 10, 30],
    "WIDTH_CLIP_IDW_K": [1, 2, 3, 6, 12, 24, 48, 120],
    "WIDTH_CLIP_BG_WINDOWS": [
        (31,), (101,), (301,), (901,), (2401,), (4801,),
        (31, 91, 241),                 # the shipped triple / 10
        (301, 901, 2401),              # SHIPPED
        (3001, 9001, 24001),           # the shipped triple x 10 -- all beyond the frame
    ],
}

t0 = time.time()


def tick(m):
    print(f"[{time.time() - t0:7.1f}s] {m}", flush=True)


# --------------------------------------------------------------------------- the harness
#
# WIDTH_CLIP_BG_WINDOWS IS A DEFAULT ARGUMENT, NOT A RUNTIME CONSTANT:
#
#     def local_background(image, mask, wins=WIDTH_CLIP_BG_WINDOWS):
#
# Python binds that tuple once, at import. Setting PL.WIDTH_CLIP_BG_WINDOWS afterwards
# changes the printed parameter table and nothing else -- the function keeps the tuple it
# was born with. So this harness overrides the FUNCTION, not the constant, and CONTROL 5b
# below asserts the difference rather than assuming it.
_ORIG_LB = PL.local_background
_BG_WINS = [None]            # None -> let the shipped default stand
_BG_CACHE = {}
_CUR = {"key": None}


def _lb(image, mask, wins=None):
    """Memoised local_background. The VALUE still comes from the shipped function."""
    w = _BG_WINS[0]
    key = (_CUR["key"], None if w is None else tuple(w))
    hit = _BG_CACHE.get(key)
    if hit is None:
        hit = _ORIG_LB(image, mask) if w is None else _ORIG_LB(image, mask, wins=tuple(w))
        _BG_CACHE[key] = hit
    return hit


def _mhash(a):
    h = blake2b(digest_size=8)
    h.update(np.ascontiguousarray(a).view(np.uint8))
    return h.hexdigest()


def set_shipped():
    for k, v in SHIP.items():
        setattr(PL, k, v)
    _BG_WINS[0] = None


def run_clip(iid, mask_in, **over):
    """One shipped clip_to_measured_width call at one setting. Returns (mask, report)."""
    set_shipped()
    bgw = over.pop("WIDTH_CLIP_BG_WINDOWS", None)
    if bgw is not None:
        _BG_WINS[0] = tuple(bgw)
        PL.WIDTH_CLIP_BG_WINDOWS = tuple(bgw)       # for the record; inert, see above
    for k, v in over.items():
        setattr(PL, k, v)
    rep = {}
    out = PL.clip_to_measured_width(iid, mask_in, report=rep)
    set_shipped()
    return out, rep


def _skel_stats(out):
    """Skeleton length, skeleton-based mean width, and an EDT-recovered roughness.

    rough_p99 IS NOT THE INSTRUMENT FOR THE IDW QUESTION and is kept only so the record
    shows why: a Euclidean distance transform is 1-Lipschitz, so |delta| between
    8-adjacent pixels cannot exceed sqrt(2) = 1.4142 whatever the radius field did. It
    pins at the bound on every setting. The IDW claim is tested on the FIELD instead, by
    field_roughness() below, against a bit-exact reconstruction of the shipped step.
    """
    sk = skeletonize(out)
    n = int(sk.sum())
    if n == 0:
        return dict(skel_px=0, mean_width_px=None, rough_p99=None, frac_jump_gt1=None)
    dt = distance_transform_edt(out).astype(np.float32)
    ys, xs = np.nonzero(sk)
    v = dt[ys, xs]
    idx = -np.ones(out.shape, np.int32)
    idx[ys, xs] = np.arange(n)
    d = []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        yy, xx = ys + dy, xs + dx
        ok = (yy >= 0) & (yy < out.shape[0]) & (xx >= 0) & (xx < out.shape[1])
        j = idx[yy[ok], xx[ok]]
        hit = j >= 0
        if hit.any():
            d.append(np.abs(v[np.nonzero(ok)[0][hit]] - v[j[hit]]))
    d = np.concatenate(d) if d else np.zeros(0, np.float32)
    return dict(skel_px=n,
                mean_width_px=float(out.sum()) / n,
                rough_p99=None if d.size == 0 else float(np.percentile(d, 99)),
                frac_jump_gt1=None if d.size == 0 else float((d > 1.0).mean()))


def metrics(mask_in, out, rep, shipped_out=None):
    a_in, a_out = int(mask_in.sum()), int(out.sum())
    m = dict(area_in=a_in, area_out=a_out,
             keep=round(a_out / max(a_in, 1), 6),
             measured=("half_width_med" in rep),
             n_skel=rep.get("n_skel"), n_probe=rep.get("n_probe"),
             n_measured=rep.get("n_measured"),
             measured_frac=(None if not rep.get("n_probe") else
                            round(rep["n_measured"] / rep["n_probe"], 4)),
             sigma=None if rep.get("sigma") is None else round(rep["sigma"], 6),
             half_width_med=(None if "half_width_med" not in rep else
                             round(rep["half_width_med"], 4)))
    m.update({k: (round(v, 4) if isinstance(v, float) else v)
              for k, v in _skel_stats(out).items()})
    if shipped_out is not None:
        inter = int((out & shipped_out).sum())
        union = int((out | shipped_out).sum())
        m["jaccard_vs_shipped"] = round(inter / max(union, 1), 6)
        m["delta_px_vs_shipped"] = int(np.logical_xor(out, shipped_out).sum())
    return m


# ------------------------------------------------- the radius field, reconstructed
#
# The IDW step has no function of its own -- it is eleven lines inside
# clip_to_measured_width -- and the only justification written down for
# WIDTH_CLIP_IDW_K = 12 is about the FIELD it builds ("nearest-probe assignment makes the
# radius field piecewise constant over the probes' Voronoi cells, and the clip boundary
# then follows the cell edges"). That statement cannot be tested from the output mask,
# because the mask's own distance transform is 1-Lipschitz and smooths the jumps away.
#
# So the field is rebuilt here, from the SHIPPED pieces -- the shipped local_background,
# the shipped _transverse_fwhm, the shipped probe subsample -- and assemble() is asserted
# bit-identical to clip_to_measured_width at two different k before any of it is read.
def probe_pack(iid, mask):
    """Everything up to the probe half-widths, exactly as clip_to_measured_width does."""
    img = np.asarray(S.load_npy(iid, "img.npy"), np.float32)
    bg = PL.local_background(img, mask)
    contrast = (bg - img).astype(np.float32)
    del bg, img
    outside = contrast[~mask]
    sigma = float(np.percentile(outside, 84.1) - np.percentile(outside, 50))
    del outside
    skel = skeletonize(mask)
    ys, xs = np.nonzero(skel)
    rng = np.random.default_rng(0)
    sub = (np.arange(ys.size) if ys.size <= PL.WIDTH_CLIP_PROBES
           else np.sort(rng.choice(ys.size, PL.WIDTH_CLIP_PROBES, replace=False)))
    rad = PL.WIDTH_CLIP_RADIUS
    offs = np.arange(-rad, rad + 1)
    dirs = _dirs_of(PL.WIDTH_CLIP_DIRS)
    half = np.array([PL._transverse_fwhm(contrast, int(ys[k]), int(xs[k]), sigma, dirs,
                                         offs, rad) / 2.0 for k in sub], np.float32)
    return dict(mask=mask, skel=skel, ys=ys, xs=xs, sub=sub, half=half,
                ok=np.isfinite(half), sigma=sigma)


def smooth_field(pack, k):
    """The inverse-distance-weighted half-width at every skeleton pixel, for one k."""
    from scipy.spatial import cKDTree
    ys, xs, sub, half, ok = (pack["ys"], pack["xs"], pack["sub"], pack["half"], pack["ok"])
    pts = np.stack([ys[sub][ok], xs[sub][ok]], 1).astype(np.float32)
    vals = half[ok].astype(np.float32)
    kk = int(min(k, pts.shape[0]))
    dist_k, idx_k = cKDTree(pts).query(np.stack([ys, xs], 1).astype(np.float32), k=kk)
    if kk == 1:
        dist_k = dist_k[:, None]
        idx_k = idx_k[:, None]
    w = 1.0 / np.maximum(dist_k, 1.0) ** 2
    return (vals[idx_k] * w).sum(1) / w.sum(1)


def assemble(pack, k, slack=1.0):
    """The IDW + EDT tail of clip_to_measured_width, for an arbitrary k. Returns
    (output mask, the smoothed half-width field sampled at every skeleton pixel)."""
    ys, xs = pack["ys"], pack["xs"]
    mask, skel = pack["mask"], pack["skel"]
    smooth = smooth_field(pack, k)
    allowed = np.zeros(mask.shape, np.float32)
    allowed[ys, xs] = smooth
    dist, idx = distance_transform_edt(~skel, return_distances=True, return_indices=True)
    out = mask & (dist <= np.maximum(allowed[idx[0], idx[1]], slack))
    return (mask if not out.any() else out), smooth


def field_roughness(pack, smooth):
    """|delta| in the radius field between 8-adjacent skeleton pixels. This is the
    quantity the IDW comment's claim is about, and it is NOT bounded by sqrt(2)."""
    ys, xs = pack["ys"], pack["xs"]
    n = ys.size
    idx = -np.ones(pack["mask"].shape, np.int32)
    idx[ys, xs] = np.arange(n)
    d = []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        yy, xx = ys + dy, xs + dx
        okb = ((yy >= 0) & (yy < idx.shape[0]) & (xx >= 0) & (xx < idx.shape[1]))
        j = idx[yy[okb], xx[okb]]
        hit = j >= 0
        if hit.any():
            d.append(np.abs(smooth[np.nonzero(okb)[0][hit]] - smooth[j[hit]]))
    d = np.concatenate(d) if d else np.zeros(0, np.float32)
    if d.size == 0:
        return {}
    return dict(field_mean_abs_delta=round(float(d.mean()), 5),
                field_p99_abs_delta=round(float(np.percentile(d, 99)), 4),
                field_max_abs_delta=round(float(d.max()), 4),
                field_frac_delta_gt_1px=round(float((d > 1.0).mean()), 5),
                field_frac_delta_eq_0=round(float((d == 0).mean()), 5),
                field_median_radius=round(float(np.median(smooth)), 4))


# ------------------------------------------------------- POSITIVE CONTROL (synthetic)
def _dirs_of(n):
    return [(np.cos(t), np.sin(t)) for t in np.linspace(0, np.pi, n, endpoint=False)]


def synth_contrast(h, w, phi, fwhm, amp, noise, rng, offset=0.0):
    """A straight dark band of KNOWN full width at half maximum, as a contrast array.

    `contrast` is what clip_to_measured_width builds (bg - img), so a crack is a positive
    ridge. The band's normal is (cos phi, sin phi) in (y, x), matching the direction
    convention in _transverse_fwhm. `offset` displaces the band off the probe point, which
    is what WIDTH_CLIP_RECENTRE exists to absorb.
    """
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = (yy - h / 2.0) * np.cos(phi) + (xx - w / 2.0) * np.sin(phi) - offset
    s = fwhm / 2.354820045
    c = amp * np.exp(-(d ** 2) / (2.0 * s * s))
    if noise:
        c = c + rng.normal(0.0, noise, (h, w))
    return c.astype(np.float32)


def fwhm_at(contrast, rad, dirs, sigma, y=None, x=None):
    """The shipped _transverse_fwhm, called on an array."""
    h, w = contrast.shape
    y = h // 2 if y is None else y
    x = w // 2 if x is None else x
    return PL._transverse_fwhm(contrast, int(y), int(x), sigma,
                               _dirs_of(dirs), np.arange(-rad, rad + 1), rad)


def positive_control():
    """Can the shipped estimator recover a width it was handed? Raises if not."""
    rng = np.random.default_rng(0)
    H = W = 1701                       # the size of a real B2/B3 frame
    rows = []
    for fwhm in (9, 21, 45, 91, 181):
        for phi in (0.0, np.pi / 24, np.pi / 7, 1.0):
            c = synth_contrast(H, W, phi, fwhm, 1.0, 0.02, rng)
            got = fwhm_at(c, SHIP["WIDTH_CLIP_RADIUS"], SHIP["WIDTH_CLIP_DIRS"], 0.02)
            rows.append(dict(true_fwhm=fwhm, phi=round(phi, 4),
                             measured=None if not np.isfinite(got) else float(got),
                             ratio=None if not np.isfinite(got) else round(got / fwhm, 4)))
    #: Tolerance is 2 px OR 6%, whichever is larger, because the profile is sampled on
    #: integer offsets: a 9 px band reads 8 px (0.889) purely from where the half level
    #: falls between samples, and that is a property of the estimator, not an error here.
    bad = [r for r in rows if r["measured"] is None
           or abs(r["measured"] - r["true_fwhm"]) > max(2.0, 0.06 * r["true_fwhm"])]
    if bad:
        raise SystemExit(
            "POSITIVE CONTROL FAILED: the shipped estimator did not recover a width it "
            f"was handed on {len(bad)} of {len(rows)} synthetic bands ({bad[:3]}). "
            "Nothing swept below would be readable.")
    return rows


def synth_dirs(rep=96):
    """Angular quantisation: the min over `dirs` sampled directions of an apparent width
    that goes as 1/cos(angle to the band normal). Worst case is pi/(2*dirs)."""
    rng = np.random.default_rng(1)
    H = W = 701
    phis = rng.uniform(0, np.pi, rep)
    out = {}
    for n in GRIDS["WIDTH_CLIP_DIRS"]:
        for noise in (0.0, 0.05):
            rs = []
            for phi in phis:
                c = synth_contrast(H, W, float(phi), 45.0, 1.0, noise, rng)
                g = fwhm_at(c, 200, n, max(noise, 1e-6))
                rs.append(np.nan if not np.isfinite(g) else g / 45.0)
            rs = np.array(rs, float)
            fin = rs[np.isfinite(rs)]
            out[f"dirs={n},noise={noise}"] = dict(
                n=int(fin.size), declined=int(rep - fin.size),
                median_ratio=None if not fin.size else round(float(np.median(fin)), 4),
                p95_ratio=None if not fin.size else round(float(np.percentile(fin, 95)), 4),
                max_ratio=None if not fin.size else round(float(fin.max()), 4),
                predicted_worst_case=round(1.0 / np.cos(np.pi / (2 * n)), 4))
    return out


def synth_radius():
    """A profile that does not return below half maximum inside the radius is discarded.
    So the radius is a CEILING on measurable width -- and on a real-sized frame a large
    radius also runs the probe into the border, where np.clip pins it."""
    rng = np.random.default_rng(2)
    H = W = 1701
    out = {}
    for rad in GRIDS["WIDTH_CLIP_RADIUS"]:
        for fwhm in (21, 45, 91, 181, 361, 721):
            c = synth_contrast(H, W, 0.3, float(fwhm), 1.0, 0.02, rng)
            g = fwhm_at(c, rad, 12, 0.02)
            out[f"rad={rad},fwhm={fwhm}"] = dict(
                measured=None if not np.isfinite(g) else float(g),
                ratio=None if not np.isfinite(g) else round(g / fwhm, 4),
                declined=bool(not np.isfinite(g)))
    return out


def synth_recentre():
    """The probe sits `offset` px off the ridge. The peak is sought in +-recentre px of
    the probe; miss it and the half level is read off a shoulder, which WIDENS the
    measurement, or falls under the sigma gate and the point is dropped."""
    rng = np.random.default_rng(3)
    H = W = 701
    out = {}
    for rc in GRIDS["WIDTH_CLIP_RECENTRE"]:
        PL.WIDTH_CLIP_RECENTRE = rc
        for off in (0, 1, 2, 3, 5, 8, 12, 20, 40):
            c = synth_contrast(H, W, 0.0, 45.0, 1.0, 0.02, rng, offset=float(off))
            g = fwhm_at(c, 200, 12, 0.02)
            out[f"recentre={rc},offset={off}"] = dict(
                measured=None if not np.isfinite(g) else float(g),
                ratio=None if not np.isfinite(g) else round(g / 45.0, 4),
                declined=bool(not np.isfinite(g)))
    set_shipped()
    return out


def synth_background():
    """Ground truth for local_background: a known shading field with a known crack cut
    into it. The estimator never sees the mask pixels, so the question is whether the
    window is small enough to track the shading and large enough to find material."""
    H = W = 1201
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    truth = (0.55 + 0.25 * np.sin(2 * np.pi * xx / 900.0)
             + 0.10 * np.cos(2 * np.pi * yy / 1300.0)).astype(np.float32)
    out_rows = {}
    for band in (45, 400):             # a hairline, and a wide accepted region
        d = np.abs(xx - W / 2.0)
        dip = 0.35 * np.exp(-(d ** 2) / (2 * (band / 2.3548) ** 2))
        img = (truth - dip).astype(np.float32)
        mask = d <= band / 2.0
        for wins in GRIDS["WIDTH_CLIP_BG_WINDOWS"]:
            bg = _ORIG_LB(img, mask, wins=tuple(wins))
            err = bg - truth
            out_rows[f"band={band},wins={'/'.join(str(w) for w in wins)}"] = dict(
                mae_everywhere=round(float(np.abs(err).mean()), 5),
                mae_on_mask=round(float(np.abs(err[mask]).mean()), 5),
                bias_on_mask=round(float(err[mask].mean()), 5),
                max_abs=round(float(np.abs(err).max()), 5),
                # what it does to the thing that is actually used: contrast at the ridge
                peak_contrast=round(float((bg - img)[:, W // 2].mean()), 5),
                true_peak_contrast=round(float(dip[:, W // 2].mean()), 5))
    return out_rows


# ----------------------------------------------------------------------------- the data
def frames():
    rows = [r for r in json.load(open(CEIL))["per_frame"] if r["group"] in GROUPS]
    have = {m["id"] for m in S.list_images()}
    rows = [r for r in rows if r["id"] in have]
    rows.sort(key=lambda r: r["id"])
    return rows if not NFRAMES else rows[:NFRAMES]


def main():
    tick("positive control: can the shipped estimator read a known width?")
    pc = positive_control()
    tick(f"  PASS on {len(pc)} synthetic bands, 9-181 px wide "
         f"(measured/true {min(r['ratio'] for r in pc):.3f}-"
         f"{max(r['ratio'] for r in pc):.3f})")

    rows = frames()
    tick(f"{len(rows)} {'/'.join(GROUPS)} frames in the store")

    PL.local_background = _lb
    controls = {"positive_control_known_width": "PASS"}
    per_frame = {}
    sweeps = {k: {} for k in GRIDS}
    frame_meta = []

    for fi, fr in enumerate(rows, 1):
        iid = fr["id"]
        _BG_CACHE.clear()
        base = PL.effective_mask(iid, corrections="none", tight=False)
        if base is None or not base.any():
            tick(f"  [{fi}/{len(rows)}] {iid[:44]} has no accepted area; skipped")
            continue
        _CUR["key"] = (iid, _mhash(base))

        # ---- CONTROL 1 and 2: the shipped chain, and the staging used here.
        set_shipped()
        PL.local_background = _ORIG_LB
        shipped_final = PL._narrow_to_image(iid, base.copy(), True)
        served = PL.effective_mask(iid, corrections="none", tight=True)
        if served is None or not np.array_equal(shipped_final, served):
            raise SystemExit(f"CONTROL 1 FAILED on {iid}: _narrow_to_image does not "
                             f"reproduce effective_mask(corrections='none', tight=True)")
        tin = PL.tighten_to_image(iid, base, prune=True)
        ship_clip_raw = PL.clip_to_measured_width(iid, tin)
        tail = PL.prune_specks_keeping(ship_clip_raw, None)
        tail = tail if tail.any() else tin
        tail = PL.drop_straight_lines(tail, None)
        if not np.array_equal(tail, shipped_final):
            raise SystemExit(f"CONTROL 2 FAILED on {iid}: the staged reconstruction used "
                             f"by this sweep is not the shipped mask")
        PL.local_background = _lb

        # ---- CONTROL 5a: the memoised local_background returns the shipped value.
        if fi == 1:
            _CUR["key"] = (iid, _mhash(tin))
            img = np.asarray(S.load_npy(iid, "img.npy"), np.float32)
            if not np.array_equal(_lb(img, tin), _ORIG_LB(img, tin)):
                raise SystemExit("CONTROL 5a FAILED: the memoised local_background does "
                                 "not return what the shipped one returns")
            del img
            controls["memoised_local_background_matches_shipped"] = "PASS"
        _CUR["key"] = (iid, _mhash(tin))

        # ---- CONTROL 3: the patch harness at shipped settings is bit-identical.
        rep0 = {}
        ship_clip = PL.clip_to_measured_width(iid, tin, report=rep0)
        if not np.array_equal(ship_clip, ship_clip_raw):
            raise SystemExit(f"CONTROL 3 FAILED on {iid}: the harness changes the shipped "
                             f"result before anything has been swept")

        base_m = metrics(tin, ship_clip, rep0, ship_clip)
        per_frame[iid] = dict(group=fr["group"], shape=list(base.shape),
                              area_model=int(base.sum()), area_tightened=int(tin.sum()),
                              area_shipped_clip=int(ship_clip.sum()),
                              area_shipped_final=int(shipped_final.sum()),
                              shipped=base_m)
        frame_meta.append(iid)

        # ---- CONTROL 6: the rebuilt radius field reproduces the shipped step, bit for
        #      bit, at two different k. Only then is the field itself readable.
        pack = probe_pack(iid, tin)
        rebuilt, _sm = assemble(pack, SHIP["WIDTH_CLIP_IDW_K"])
        if not np.array_equal(rebuilt, ship_clip):
            raise SystemExit(f"CONTROL 6 FAILED on {iid}: the rebuilt IDW+EDT tail does "
                             f"not reproduce clip_to_measured_width at the shipped k")
        reb1, _ = assemble(pack, 1)
        out1, _ = run_clip(iid, tin, WIDTH_CLIP_IDW_K=1)
        if not np.array_equal(reb1, out1):
            raise SystemExit(f"CONTROL 6b FAILED on {iid}: the rebuilt tail and the "
                             f"shipped step disagree at k=1")
        hk = pack["half"][pack["ok"]]
        per_frame[iid]["probe_half_width_px"] = dict(
            n_probe=int(pack["sub"].size), n_measured=int(pack["ok"].sum()),
            median=None if not hk.size else round(float(np.median(hk)), 3),
            p10=None if not hk.size else round(float(np.percentile(hk, 10)), 3),
            p90=None if not hk.size else round(float(np.percentile(hk, 90)), 3),
            max=None if not hk.size else round(float(hk.max()), 3))
        per_frame[iid]["idw_field"] = {
            str(k): field_roughness(pack, smooth_field(pack, k))
            for k in GRIDS["WIDTH_CLIP_IDW_K"]}

        # ---- which background windows actually fire? Each is compared against the
        #      prefix before it, using the shipped local_background both times.
        img = np.asarray(S.load_npy(iid, "img.npy"), np.float32)
        wins = tuple(SHIP["WIDTH_CLIP_BG_WINDOWS"])
        prev, fire = None, {}
        for i in range(1, len(wins) + 1):
            cur = _ORIG_LB(img, tin, wins=wins[:i])
            if prev is not None:
                d = np.abs(cur - prev)
                fire[str(wins[i - 1])] = dict(
                    px_changed_vs_shorter_prefix=int((d > 0).sum()),
                    frac_of_frame=round(float((d > 0).mean()), 8),
                    max_abs_change=round(float(d.max()), 6))
            prev = cur
        del img, prev, cur
        per_frame[iid]["bg_window_firing"] = fire

        # ---- CONTROL 5b: setting the MODULE CONSTANT alone must change nothing.
        if fi == 1:
            PL.local_background = _ORIG_LB
            keep = PL.WIDTH_CLIP_BG_WINDOWS
            PL.WIDTH_CLIP_BG_WINDOWS = (31,)
            inert = PL.clip_to_measured_width(iid, tin)
            PL.WIDTH_CLIP_BG_WINDOWS = keep
            PL.local_background = _lb
            same = bool(np.array_equal(inert, ship_clip_raw))
            if not same:
                raise SystemExit(
                    "CONTROL 5b FAILED: setting PL.WIDTH_CLIP_BG_WINDOWS changed the "
                    "output, so the default-argument reading in this file's docstring "
                    "is wrong and the whole background sweep is mis-specified")
            controls["module_constant_WIDTH_CLIP_BG_WINDOWS_is_inert"] = (
                "PASS -- setting it to (31,) changed 0 of "
                f"{int(ship_clip_raw.sum())} px; the value is frozen into "
                "local_background's default argument at import")

        # ---- the sweeps
        for const, grid in GRIDS.items():
            for val in grid:
                key = "/".join(str(v) for v in val) if isinstance(val, tuple) else str(val)
                if (isinstance(val, tuple) and tuple(val) == tuple(SHIP[const])) or \
                   (not isinstance(val, tuple) and val == SHIP[const]):
                    m = dict(base_m)
                    m["is_shipped"] = True
                else:
                    out, rep = run_clip(iid, tin, **{const: val})
                    if bool((out & ~tin).any()):
                        raise SystemExit(
                            f"CONTROL 4 FAILED: {const}={key} on {iid} ADDED area. "
                            f"clip_to_measured_width is documented and selftested as "
                            f"removal-only; a setting that widens invalidates the step.")
                    m = metrics(tin, out, rep, ship_clip)
                    m["is_shipped"] = False
                sweeps[const].setdefault(key, {})[iid] = m
            tick(f"  [{fi}/{len(rows)}] {iid[:40]} {const} done")

    PL.local_background = _ORIG_LB
    set_shipped()
    controls["narrow_to_image_is_the_served_mask"] = f"PASS on all {len(frame_meta)} frames"
    controls["staged_reconstruction_is_the_shipped_mask"] = (
        f"PASS on all {len(frame_meta)} frames")
    controls["harness_at_shipped_settings_is_bit_identical"] = (
        f"PASS on all {len(frame_meta)} frames")
    controls["every_swept_output_is_a_subset_of_its_input"] = (
        f"PASS on all {len(frame_meta)} frames x "
        f"{sum(len(g) for g in GRIDS.values())} settings")
    controls["rebuilt_idw_field_reproduces_the_shipped_step"] = (
        f"PASS on all {len(frame_meta)} frames, bit for bit, at k=12 and at k=1")

    # ---- pooled, paired against shipped, frame by frame
    def pool(const, key):
        rowsv = sweeps[const][key]
        hw = [v["half_width_med"] for v in rowsv.values() if v["half_width_med"] is not None]
        sh = [per_frame[i]["shipped"]["half_width_med"] for i in rowsv
              if per_frame[i]["shipped"]["half_width_med"] is not None
              and rowsv[i]["half_width_med"] is not None]
        hw2 = [rowsv[i]["half_width_med"] for i in rowsv
               if per_frame[i]["shipped"]["half_width_med"] is not None
               and rowsv[i]["half_width_med"] is not None]
        ratio = [a / b for a, b in zip(hw2, sh) if b]
        keepv = [v["keep"] for v in rowsv.values()]
        mw = [v["mean_width_px"] for v in rowsv.values() if v["mean_width_px"] is not None]
        jac = [v["jaccard_vs_shipped"] for v in rowsv.values()
               if v.get("jaccard_vs_shipped") is not None]
        mf = [v["measured_frac"] for v in rowsv.values() if v["measured_frac"] is not None]
        rp = [v["rough_p99"] for v in rowsv.values() if v["rough_p99"] is not None]
        fj = [v["frac_jump_gt1"] for v in rowsv.values() if v["frac_jump_gt1"] is not None]
        return dict(
            n_frames=len(rowsv),
            n_declined=sum(1 for v in rowsv.values() if not v["measured"]),
            median_half_width_px=None if not hw else round(float(np.median(hw)), 3),
            median_half_width_um=None if not hw else round(
                float(np.median(hw)) * NM_PER_PX / 1000.0, 4),
            median_paired_ratio_vs_shipped=None if not ratio else round(
                float(np.median(ratio)), 4),
            min_paired_ratio=None if not ratio else round(float(np.min(ratio)), 4),
            max_paired_ratio=None if not ratio else round(float(np.max(ratio)), 4),
            median_keep=round(float(np.median(keepv)), 5),
            min_keep=round(float(np.min(keepv)), 5),
            median_mean_width_px=None if not mw else round(float(np.median(mw)), 3),
            median_measured_frac=None if not mf else round(float(np.median(mf)), 4),
            median_jaccard_vs_shipped=None if not jac else round(float(np.median(jac)), 5),
            min_jaccard_vs_shipped=None if not jac else round(float(np.min(jac)), 5),
            median_rough_p99=None if not rp else round(float(np.median(rp)), 4),
            median_frac_jump_gt1=None if not fj else round(float(np.median(fj)), 5),
        )

    summary = {c: {k: pool(c, k) for k in sweeps[c]} for c in sweeps}

    # the radius field, pooled over frames: the only measurement of the IDW claim
    fkeys = ("field_mean_abs_delta", "field_p99_abs_delta", "field_max_abs_delta",
             "field_frac_delta_gt_1px", "field_frac_delta_eq_0", "field_median_radius")
    idw_field = {}
    for k in GRIDS["WIDTH_CLIP_IDW_K"]:
        rowsf = [per_frame[i]["idw_field"][str(k)] for i in per_frame
                 if per_frame[i].get("idw_field", {}).get(str(k))]
        idw_field[str(k)] = {q: (None if not rowsf else
                                 round(float(np.median([r[q] for r in rowsf])), 5))
                             for q in fkeys}
        idw_field[str(k)]["n_frames"] = len(rowsf)
    # which background windows ever fire
    bgfire = {}
    for w in SHIP["WIDTH_CLIP_BG_WINDOWS"][1:]:
        rowsb = [per_frame[i]["bg_window_firing"][str(w)] for i in per_frame
                 if str(w) in per_frame[i].get("bg_window_firing", {})]
        bgfire[str(w)] = dict(
            n_frames=len(rowsb),
            n_frames_where_it_changes_nothing=sum(
                1 for r in rowsb if r["px_changed_vs_shorter_prefix"] == 0),
            median_px_changed=None if not rowsb else int(np.median(
                [r["px_changed_vs_shorter_prefix"] for r in rowsb])),
            max_px_changed=None if not rowsb else int(max(
                r["px_changed_vs_shorter_prefix"] for r in rowsb)),
            max_frac_of_frame=None if not rowsb else round(float(max(
                r["frac_of_frame"] for r in rowsb)), 8))

    rec = dict(
        what="the five width-clip constants Figure 6 letters F, measured on the TXM "
             "corpus and against synthetic bands of known width",
        generated=time.strftime("%Y-%m-%d"),
        generator="analysis/research/improve/txm_clip_constants.py",
        interpreter=sys.executable,
        repo_under_test=TXM,
        scope=dict(groups=list(GROUPS), n_frames=len(frame_meta), frames=frame_meta,
                   frame_source="paper/figures/txm_iou_ceiling_v2.json per_frame rows"),
        nm_per_px=NM_PER_PX,
        scoring=dict(
            not_iou_against_paint=(
                "IoU against the hand-painted TXM masks is not used. A correct 3 px "
                "crack scores IoU 0.0498 there (txm_iou_ceiling_v2.json), because the "
                "operator painted with a broad brush, so TXM IoU ranks brush imitation "
                "and cannot rank a width estimator."),
            measurands=[
                "half_width_med: the step's own output, median transverse half-width "
                "over every skeleton pixel, in px",
                "measured_frac: n_measured / n_probe",
                "keep: clipped area / input area",
                "mean_width_px: area / skeleton length of the clip output -- a "
                "skeleton-based width, independent of the FWHM estimator",
                "rough_p99 and frac_jump_gt1: |delta half-width| between 8-adjacent "
                "skeleton pixels, recovered from the output by EDT",
                "jaccard_vs_shipped: swept clip output against SHIPPED clip output, "
                "mask against mask, never against paint"],
            paint_never_read="TXM_Crack_Detection_Pipeline/paint/ is not opened by this "
                             "script; correction.npy is not read either"),
        constants={k: dict(row_in_figure_6=ROW[k], source=SOURCE[k],
                           shipped=list(SHIP[k]) if isinstance(SHIP[k], tuple)
                           else SHIP[k],
                           grid=[list(v) if isinstance(v, tuple) else v
                                 for v in GRIDS[k]]) for k in SOURCE},
        liveness=dict(
            path="effective_mask -> _narrow_to_image -> clip_to_measured_width "
                 "(app/core/pipeline.py:951 and :1017 -> :862 -> :675)",
            gate="WIDTH_CLIP = True (pipeline.py:595) and the caller's tight flag",
            default="app/server.py _tight(default=True) -- on for every overlay and "
                    "every export the application serves",
            also_in_this_repo="paper/figures/mk_flow.py:233 and mk_txm_ceiling.py "
                              "reproduce effective_mask(corrections='none', tight=True), "
                              "so the manuscript's TXM masks are this step's output",
            verdict="LIVE for all five, with one qualification: the MODULE CONSTANT "
                    "WIDTH_CLIP_BG_WINDOWS is dead as a constant. local_background binds "
                    "it as a default argument at import, so assigning to it at runtime "
                    "changes the printed parameter table and nothing else. The VALUE is "
                    "live; the name is not a knob."),
        controls=controls,
        positive_control=dict(
            what="the shipped _transverse_fwhm run on synthetic Gaussian bands of known "
                 "FWHM at known angles, 1701x1701 (a real frame's size)",
            rows=pc),
        synthetic=dict(
            directions=synth_dirs(),
            radius=synth_radius(),
            recentre=synth_recentre(),
            background=synth_background()),
        sweeps=summary,
        idw_radius_field=dict(
            what="|delta half-width| between 8-adjacent skeleton pixels in the IDW "
                 "radius field itself, from a reconstruction asserted bit-identical to "
                 "clip_to_measured_width at k=12 and k=1. This, not the output mask, is "
                 "where the source comment's Voronoi claim lives: the mask's own "
                 "distance transform is 1-Lipschitz and cannot show a jump.",
            median_over_frames=idw_field),
        bg_windows_that_fire=dict(
            what="each shipped background window compared against the prefix before it, "
                 "using the shipped local_background both times: how many pixels of the "
                 "frame does adding this window actually change?",
            per_window=bgfire),
        per_frame=per_frame,
        per_frame_sweeps=sweeps,
        seconds=round(time.time() - t0, 1),
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rec, open(OUT, "w"), indent=1)
    tick(f"wrote {OUT}")
    return rec


if __name__ == "__main__":
    r = main()
    for c in GRIDS:
        print(f"\n=== {c}  (shipped {SHIP[c]})")
        print(f"{'value':>14s} {'halfW px':>9s} {'ratio':>7s} {'keep':>7s} "
              f"{'meanW':>7s} {'measfr':>7s} {'J vs ship':>9s} {'rough99':>8s}")
        for k, v in r["sweeps"][c].items():
            def f(x, w=7, p=4):
                return ("%*.*f" % (w, p, x)) if isinstance(x, float) else "%*s" % (w, x)
            print(f"{k:>14s} {f(v['median_half_width_px'], 9, 3)} "
                  f"{f(v['median_paired_ratio_vs_shipped'])} {f(v['median_keep'])} "
                  f"{f(v['median_mean_width_px'])} {f(v['median_measured_frac'])} "
                  f"{f(v['median_jaccard_vs_shipped'], 9)} {f(v['median_rough_p99'], 8)}")
    print(f"\n=== the IDW radius field itself (shipped k={SHIP['WIDTH_CLIP_IDW_K']})")
    print(f"{'k':>4s} {'mean|d|':>9s} {'p99|d|':>9s} {'max|d|':>9s} {'frac>1px':>9s} "
          f"{'frac==0':>9s}")
    for k, v in r["idw_radius_field"]["median_over_frames"].items():
        print(f"{k:>4s} {v['field_mean_abs_delta']:9.5f} {v['field_p99_abs_delta']:9.4f} "
              f"{v['field_max_abs_delta']:9.4f} {v['field_frac_delta_gt_1px']:9.5f} "
              f"{v['field_frac_delta_eq_0']:9.5f}")
    print("\n=== background windows that fire")
    for k, v in r["bg_windows_that_fire"]["per_window"].items():
        print(f"  window {k:>6s}: changes nothing on "
              f"{v['n_frames_where_it_changes_nothing']}/{v['n_frames']} frames, "
              f"median {v['median_px_changed']} px, max {v['max_px_changed']} px")
