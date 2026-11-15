"""Plate F8: how the detector scores, specimen sample by specimen sample, in both arms.

ONE PANEL: precision, recall and F1 for every specimen sample of both microscopies.

THERE USED TO BE A SECOND, the area the detector marks as a percentage of all image
pixels, and the author took it off. It was answering a question this plate does not ask.
How much of a frame gets marked is a property of the specimen as much as of the detector
-- a field with a wide crack in it has more crack in it -- so a bar twice as tall says
nothing about whether the detector is right, which is the whole subject of panel (a).
The quantity that DOES belong to the detector, reported area over annotated area, is
Figure 4's left panel. Every per-sample area number is still written to the caption file
beside this figure: marked_pct_of_image, marked_pct_inside_adjudicated,
marked_pct_where_nobody_ruled and painted_crack_pct_of_image, per sample, per arm.

WHAT THE UNITS ARE. Both arms are scored the same way and by the same record: an operator
painted a correction mask on each frame marking crack (1) and not-crack (2 or 3)
explicitly and leaving the rest of the frame unruled (0), and only the pixels that carry a
verdict are scored. A frame enters only if it carries at least 200 px of each verdict.
Every value here is a MEAN OVER FRAMES, one vote per frame; the pooled-over-pixels twin of
each one is in the caption file beside this figure, because the frames of this corpus
differ in area by a factor of two hundred and the two aggregations do not agree.

THE SEM ARM IS SCORED IN SAMPLE, AND THE PLATE SAYS SO. The region classifier is enabled,
and 45 of the 48 hand-painted SEM frames are among the 45 images its bundle records being
fitted on. Every SEM bar here is therefore the detector answering about frames it was
built from. The leave-one-frame-out refit that answers the other question is
`docs/figures/sem_classifier_lofo.json`; it is not drawn here because it is a different
unit set, and a bar from it standing beside these would be read as comparable.

THE CONVENTION THAT DECIDES PRECISION. The detector also marks pixels OUTSIDE the painted
region, which nobody ruled on. Excluding them -- what the record calls `precision`, and
what every bar here is drawn at -- is the higher of two numbers. Counting every one of
them as a false positive -- `precision_if_unrefereed_wrong` -- is the lower. NEITHER IS
QUOTED IN THIS DOCSTRING any more: they were, and they went stale the moment the
classifier was switched on, with nothing in the build able to notice. Both are in the
record and in the caption file this module writes beside the plate.

That second number is a BOUND, not a second measurement. It asserts that every marked
pixel nobody ruled on is a false positive, which is an assumption about pixels this
corpus never adjudicated and which nothing in the record tests. So the bar is drawn at
the score over the pixels that DO carry a verdict, and the bound is a thin whisker
beneath it. This plate used to do the opposite -- solid to the bound, hollow on to
the score -- which put the conspicuous part of every bar on the assumption and the faint
part on the measurement. Recall cannot move with the convention at all, since its
denominator is painted crack and an unruled pixel is not in it, so recall carries no
whisker. Both numbers are in the caption file for every sample either way.

SAMPLES. The TXM record carries its own `group` per frame (B2, B3, Wrought, AM/HC). The
SEM record carries none, so the specimen key is derived from the frame name by the rule
this project already uses, `analysis/research/improve/unetctx_base.py:specimen_of`, which
reproduces the mapping in tiles_meta.json: a frame is <specimen>_<detector>_<index> with
the detector token CBS / ETD / SE / BSE, and a trailing front/back is a fracture surface
and not a specimen. That gives six SEM keys; the two b2 keys are the same specimen series
imaged on two dates (260622 and 260708) and are merged into one `b2` sample so that the
one sample both microscopies cover is one bar group. The merge is checked, not asserted:
the merged sample must reproduce the SEM block of the b2/b3-restricted record exactly.

THERE IS NO SEM b3 BAR because there are no labelled SEM b3 frames -- every SEM lab
correction in the paper's scope is b2 -- and the script aborts if one ever appears.

Sources, all under docs/figures/ and all read, never retyped:
  overlap_means_sem_txm.json        per-frame precision/recall/F1 and both bounds, 18 SEM
                                    and 31 TXM frames (the FULL corpus, scope=False)
  overlap_means_sem_txm_b2b3.json   the restricted twin, used only as a check
  txm_background_units.json         the independently generated per-group pixel accounting
                                    that panel (b)'s reconstruction is validated against
  frame_legibility.json             the same per-frame scores from a second pass, used
                                    only as a check
"""
import os
import sys
import json
import statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.legend_handler import HandlerTuple

import journal_style as J
from _paths import scoped, DOC_FIGURES

J.use()

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
NAME = "F8 - scores by sample"
MAD_K = 6.0
TXM_ARM = "SEM detector, mad_k=6"

# ----------------------------------------------------------------------------- records
# scoped(..., scope=False) is the FULL-corpus record. The manuscript's own numbers come
# from the b2/b3 twin; this figure is asked for every sample, so it reads the wider file
# and loads the restricted one only to check the b2 rows against it.
FULL = json.load(open(scoped("overlap_means_sem_txm.json", scope=False)))
B2B3 = json.load(open(scoped("overlap_means_sem_txm.json")))
UNITS = json.load(open(scoped("txm_background_units.json", scope=False)))
LEGIB = json.load(open(scoped("frame_legibility.json", scope=False)))


def specimen_of(name):
    """The specimen key this project already uses, derived the same way.

    Copied in behaviour from analysis/research/improve/unetctx_base.py:specimen_of, which
    documents the rule: a frame is <specimen>_<detector>_<index>, the detector token being
    CBS / ETD / SE / BSE, and tiles_meta.json calls 260622_316_H_b2_front_CBS_03 the
    specimen "260622_316_H_b2" because the fracture-surface side is not a specimen.
    """
    parts = name.split("_")
    for i, p in enumerate(parts):
        if p in ("CBS", "ETD", "SE", "BSE"):
            parts = parts[:i]
            break
    else:
        parts = parts[:-1]
    if parts and parts[-1] in ("front", "back"):
        parts = parts[:-1]
    return "_".join(parts)


#: The two SEM specimen keys below are specimen series b2 imaged on two dates. Merging
#: them is the only regrouping this script does, and guard 3 checks it against the
#: restricted record rather than trusting it.
SEM_SERIES = {"260622_316_H_b2": "b2", "260708_316_H_b2": "b2"}


def sample_of(arm, frame):
    if arm == "TXM":
        return frame["group"]
    key = specimen_of(frame["frame"])
    return SEM_SERIES.get(key, key)


def tp_fp(f):
    """True- and false-positive pixel counts, recovered from the scores and the counts.

    recall = tp / crack_px and precision = tp / (tp + fp) over refereed pixels, so both
    counts follow. Guard 2 checks this reconstruction against a record generated by a
    different script, on all four TXM groups, before any of it is drawn.
    """
    tp = f["recall"] * f["crack_px"]
    fp = (tp / f["precision"] - tp) if f["precision"] > 0 else 0.0
    return tp, fp


def areas(f):
    """Every area this figure needs for one frame, as a percentage of ALL its pixels.

    refereed_frac is the adjudicated share of the frame, so the frame's own pixel count
    follows from it; on this corpus that returns exact raster sizes (6144 x 4096 and so
    on), which is the cheapest available check that the denominator is the whole image.
    """
    ref = f["crack_px"] + f["notcrack_px"]
    total = ref / f["refereed_frac"]
    tp, fp = tp_fp(f)
    unruled = f["marked_px_nobody_refereed"]
    return dict(total_px=total,
                marked_adjudicated_pct=100.0 * (tp + fp) / total,
                marked_unruled_pct=100.0 * unruled / total,
                marked_pct=100.0 * (tp + fp + unruled) / total,
                painted_crack_pct=100.0 * f["crack_px"] / total)


# ----------------------------------------------------------------------- build the rows
BY_SAMPLE = {}
for arm in ("SEM", "TXM"):
    for f in FULL[arm]["per_frame"]:
        BY_SAMPLE.setdefault((arm, sample_of(arm, f)), []).append(f)


def summarise(frames):
    a = [areas(f) for f in frames]
    tot = sum(x["total_px"] for x in a)
    tp = sum(tp_fp(f)[0] for f in frames)
    fp = sum(tp_fp(f)[1] for f in frames)
    cr = sum(f["crack_px"] for f in frames)
    un = sum(f["marked_px_nobody_refereed"] for f in frames)
    ref = cr + sum(f["notcrack_px"] for f in frames)
    return dict(
        n=len(frames),
        frames=[f["frame"] for f in frames],
        # drawn in (a): mean over frames, one vote per frame
        precision=st.mean(f["precision"] for f in frames),
        precision_if_unruled_wrong=st.mean(f["precision_if_unrefereed_wrong"]
                                           for f in frames),
        recall=st.mean(f["recall"] for f in frames),
        f1=st.mean(f["f1"] for f in frames),
        f1_if_unruled_wrong=st.mean(f["f1_if_unrefereed_wrong"] for f in frames),
        # drawn in (b): mean over frames of each frame's own area fraction
        marked_pct=st.mean(x["marked_pct"] for x in a),
        marked_adjudicated_pct=st.mean(x["marked_adjudicated_pct"] for x in a),
        marked_unruled_pct=st.mean(x["marked_unruled_pct"] for x in a),
        painted_crack_pct=st.mean(x["painted_crack_pct"] for x in a),
        adjudicated_coverage_pct=st.mean(100.0 * f["refereed_frac"] for f in frames),
        # NOT drawn, recorded: the same quantities pooled over pixels. The frames of this
        # corpus span 0.12 M to 25 M px, so pooling weights a sample by its largest frame.
        pooled=dict(
            precision=tp / (tp + fp) if tp + fp else 0.0,
            precision_if_unruled_wrong=tp / (tp + fp + un) if tp + fp + un else 0.0,
            recall=tp / cr if cr else 0.0,
            marked_pct=100.0 * (tp + fp + un) / tot,
            marked_pct_of_adjudicated=100.0 * (tp + fp) / ref,
            painted_crack_pct=100.0 * cr / tot,
            tp_pct_of_adjudicated=100.0 * tp / ref,
            fp_pct_of_adjudicated=100.0 * fp / ref,
        ),
    )


S = {k: summarise(v) for k, v in BY_SAMPLE.items()}

ALL_SAMPLES = [
    ("b2", {"SEM": "b2", "TXM": "B2"}),
    ("b3", {"TXM": "B3"}),
    ("Wrought", {"TXM": "Wrought"}),
    ("AM/HC", {"TXM": "AM/HC"}),
    ("AS_24hr", {"SEM": "AS_24hr"}),
    ("MAR_Amb\nAS", {"SEM": "MAR_Amb_AS"}),
    ("MAR_Amb\nCast", {"SEM": "MAR_Amb_Cast"}),
    ("MAR_Amb\nHIP", {"SEM": "MAR_Amb_HIP"}),
]
#: EVERY BAR ON THIS PLATE IS A METAL SPECIMEN IMAGED IN A MICROSCOPE. Samples from
#: other subjects have no place on it whatever they score: this is a measurement of
#: crack detection in metal, and a bar from a different material and a different
#: instrument cannot be read against these.

#: WHICH BAR GROUPS THE PLATE DRAWS, AND THE LINE THAT DECIDES IT.
#:
#: The author asked for the samples that do not work to come off this figure and be
#: listed instead, as work to be done rather than results to be shown. That is a
#: reasonable thing to want from a progress figure and it is a dangerous thing to do
#: silently, because a panel of survivors selected ON THEIR SCORES is not an estimate of
#: anything: drop the worst third of any corpus and the rest always looks good.
#:
#: So the cut is made in the open, and three things keep it honest. The threshold is a
#: stated round number fixed in one place rather than a judgement made bar by bar. It is
#: applied to every arm of both microscopies alike, so it cannot be a device for
#: keeping a flattering sample and dropping an awkward one. And every group it
#: removes is named on the plate with its own score,
#: so the figure still reports them; it stops drawing them.
#:
#: A reader who wants the unselected figure has it: `mk_scores.py SHOW_ALL=1` draws
#: every group, and the caption file beside the plate always carries all ten.
KEEP_F1 = 0.50
SHOW_ALL = os.environ.get("SHOW_ALL", "") not in ("", "0")


def _keep(arm, key):
    return SHOW_ALL or S[(arm, key)]["f1"] >= KEEP_F1


DROPPED = [(lab, arm, key, S[(arm, key)]["f1"])
           for lab, keys in ALL_SAMPLES for arm, key in keys.items()
           if not _keep(arm, key)]
SAMPLES = [(lab, {a: k for a, k in keys.items() if _keep(a, k)})
           for lab, keys in ALL_SAMPLES]
SAMPLES = [(lab, keys) for lab, keys in SAMPLES if keys]
if not SAMPLES:
    raise SystemExit(f"every bar group scores below F1 {KEEP_F1:g}; there is no figure")

# ------------------------------------------------------------------------------- guards
# Each of these compares this script's numbers against a record it did not produce, and
# each aborts. None of them is algebra that cannot fail: guard 1 is a second scoring pass,
# guard 2 is a different generator's pixel accounting, guards 3 and 4 are the restricted
# record the manuscript itself reads.
_fail = []

# 1. the per-frame scores agree with the second record that carries them
for arm in ("SEM", "TXM"):
    other = {r["frame"]: r for r in LEGIB[arm]}
    for f in FULL[arm]["per_frame"]:
        o = other.get(f["frame"])
        if o is None:
            _fail.append(f"{arm} {f['frame']} is absent from frame_legibility.json")
            continue
        for k in ("precision", "recall", "f1"):
            if abs(o[k] - f[k]) > 1e-9:
                _fail.append(f"{arm} {f['frame']} {k}: {f[k]} vs {o[k]} in "
                             f"frame_legibility.json")

# 2. the tp/fp reconstruction reproduces an independently generated pixel accounting
for g, rec in UNITS["by_group"].items():
    rows = BY_SAMPLE[("TXM", g)]
    if len(rows) != rec["frames"]:
        _fail.append(f"TXM {g}: {len(rows)} frames here, {rec['frames']} in "
                     f"txm_background_units.json")
        continue
    tp = sum(tp_fp(f)[0] for f in rows)
    fp = sum(tp_fp(f)[1] for f in rows)
    ref = sum(f["crack_px"] + f["notcrack_px"] for f in rows)
    arm = rec["arms"][TXM_ARM]
    for name, got, want in (("tp_pct", 100.0 * tp / ref, arm["tp_pct"]),
                            ("fp_pct", 100.0 * fp / ref, arm["fp_pct"]),
                            ("marked_pct", 100.0 * (tp + fp) / ref, arm["marked_pct"]),
                            ("crack_px", sum(f["crack_px"] for f in rows),
                             rec["crack_px"])):
        if abs(got - want) > 1e-6 * max(1.0, abs(want)):
            _fail.append(f"TXM {g} {name}: reconstructed {got!r}, recorded {want!r}")

# 3. the merged SEM b2 sample IS the restricted record's SEM block
_b2 = S[("SEM", "b2")]
_ref = B2B3["SEM"]
if _b2["n"] != _ref["n_frames"]:
    _fail.append(f"SEM b2 holds {_b2['n']} frames, the b2/b3 record {_ref['n_frames']}")
for here, there in (("precision", "mean_precision"), ("recall", "mean_recall"),
                    ("f1", "mean_f1"),
                    ("precision_if_unruled_wrong", "mean_precision_if_unrefereed_wrong"),
                    ("f1_if_unruled_wrong", "mean_f1_if_unrefereed_wrong")):
    if abs(_b2[here] - _ref[there]) > 1e-9:
        _fail.append(f"SEM b2 {here}: {_b2[here]} here, {_ref[there]} in the b2/b3 record")

# 4. TXM B2 and B3 together ARE the restricted record's TXM block
_rows = BY_SAMPLE[("TXM", "B2")] + BY_SAMPLE[("TXM", "B3")]
_ref = B2B3["TXM"]
if len(_rows) != _ref["n_frames"]:
    _fail.append(f"TXM B2+B3 holds {len(_rows)} frames, the b2/b3 record "
                 f"{_ref['n_frames']}")
for here, there in (("precision", "mean_precision"), ("recall", "mean_recall"),
                    ("f1", "mean_f1")):
    if abs(st.mean(f[here] for f in _rows) - _ref[there]) > 1e-9:
        _fail.append(f"TXM B2+B3 {here} disagrees with the b2/b3 record")

# 5. no SEM b3 frame exists, so no SEM b3 bar can be drawn by accident
for (arm, s) in S:
    if arm == "SEM" and s.lower().startswith("b3"):
        _fail.append(f"a SEM sample resolved to {s!r}: there are no labelled SEM b3 "
                     f"frames, so either the corpus changed or specimen_of is wrong")

# 6. the two records were made at the same detector setting
if FULL["mad_k"] != MAD_K or UNITS.get("n_frames") != FULL["TXM"]["n_frames"]:
    _fail.append(f"mad_k {FULL['mad_k']} / TXM n {UNITS.get('n_frames')} vs "
                 f"{FULL['TXM']['n_frames']}")

# 7. the plate draws the kept groups, the record carries ALL of them, and the
#    difference between the two sets is EXACTLY the list the plate prints as dropped.
#    This used to require the two sets to be equal. That was right while nothing was
#    ever withheld; now something is, and the check that matters is not "nothing is
#    missing" but "everything missing is declared". A group that fell out by a bug in
#    the filter, or one silently removed from ALL_SAMPLES, fails here just as loudly --
#    and a dropped group that the plate forgot to name fails too.
_drawn = {(a, k) for _, keys in SAMPLES for a, k in keys.items()}
_declared = {(a, k) for _, a, k, _f1 in DROPPED}
_all = {(a, k) for _, keys in ALL_SAMPLES for a, k in keys.items()}
if _all != set(S):
    _fail.append(f"ALL_SAMPLES {sorted(_all)} != summarised {sorted(S)}")
if _drawn | _declared != _all or (_drawn & _declared):
    _fail.append(f"drawn {sorted(_drawn)} and declared-dropped {sorted(_declared)} do "
                 f"not partition {sorted(_all)}")
for _a, _k in _declared:
    if S[(_a, _k)]["f1"] >= KEEP_F1:
        _fail.append(f"{_a} {_k} is listed as dropped but scores F1 "
                     f"{S[(_a, _k)]['f1']:.4f}, at or above the {KEEP_F1:g} line")
for _a, _k in _drawn:
    if not SHOW_ALL and S[(_a, _k)]["f1"] < KEEP_F1:
        _fail.append(f"{_a} {_k} is drawn but scores F1 {S[(_a, _k)]['f1']:.4f}, "
                     f"below the {KEEP_F1:g} line")

if _fail:
    raise SystemExit("mk_scores.py aborted, {} check(s) failed:\n  ".format(len(_fail))
                     + "\n  ".join(_fail))

# ------------------------------------------------------------------------------ drawing
ARM_COLOUR = {"SEM": J.ACCENT, "TXM": J.ACCENT2}
#: One hue per arm, three lightnesses for the three metrics, lightest first so the ramp
#: runs the same way the bars are ordered and the headline metric is the most saturated.
METRICS = [("precision", 0.38), ("recall", 0.66), ("F1", 1.00)]


def tint(hexstr, f):
    r, g, b = J.rgb(hexstr)
    return (r + (1 - r) * (1 - f), g + (1 - g) * (1 - f), b + (1 - b) * (1 - f))


#: The gap BETWEEN samples has to be several times the gap between the two arms of one
#: sample, or b2's two bar groups read as two samples and the one place where a blue bar
#: may be compared with an orange one stops looking like one place.
BARW, ARMGAP, SAMPGAP = 0.86, 0.55, 2.5
#: Whisker cap, in the same x units as BARW: half the bar, so the cap reads as a
#: bound on that bar and not as a second bar behind it.
CAPW = 0.43
blocks, ticks = [], []
x = 0.0
for label, keys in SAMPLES:
    start = x
    for i, (arm, key) in enumerate(keys.items()):
        blocks.append(dict(arm=arm, key=key, centre=x + 1.5,
                           bars=[x + 0.5, x + 1.5, x + 2.5]))
        x += 3.0
        if i < len(keys) - 1:
            x += ARMGAP
    ticks.append(dict(label=label, centre=0.5 * (start + x)))
    x += SAMPGAP
XLIM = (-0.7, x - SAMPGAP + 0.7)

#: SHORTER, BECAUSE THE WORDS CAME OFF. The plate carried a two-line y-axis title, a
#: one-line x-axis title and a full sentence of footnote -- about thirty words of
#: lettering around eight bar groups whose own labels already said which arm, how many
#: frames and which sample. The axis title and the x-axis title are gone and the
#: footnote is a clause, so the left margin and the bottom margin both come in and the
#: same bars are drawn larger on the page. What the scores are measured against, and
#: what the whisker assumes, are the caption's job.
fig = plt.figure(figsize=(J.PAGEW, 3.00))
gs = fig.add_gridspec(1, 1, left=0.052, right=0.995, top=0.952, bottom=0.350)
ax_a = fig.add_subplot(gs[0, 0])


def score_bar(ax, centre, lo, hi, colour):
    """Solid to the measured score, with a thin whisker down to the worst case.

    THIS USED TO BE A TWO-TONE BAR -- solid to the pessimistic bound, hollow on to the
    measured one -- and the hollow section was the most conspicuous thing on the plate.
    It also put the SOLID fill at the number with the least support: the pessimistic
    bound counts every marked pixel nobody ruled on as a false positive, which is an
    assumption about unadjudicated pixels rather than a measurement of them. The bar is
    therefore drawn at the score over the pixels an operator actually ruled on -- the
    only part of the frame that carries ground truth -- and the bound is kept as a
    whisker, because on SEM b2 the two differ by a factor of two and a lone bar would
    hide that. `lo == hi` (recall, and any sample with no unruled marked pixels)
    draws no whisker at all.
    """
    ax.bar(centre, hi, BARW, color=colour, edgecolor=J.INK, linewidth=0.5, zorder=3)
    if hi - lo > 1e-12:
        ax.plot([centre, centre], [lo, hi], color=J.INK, lw=0.7, zorder=4,
                solid_capstyle="butt")
        ax.plot([centre - 0.5 * CAPW, centre + 0.5 * CAPW], [lo, lo], color=J.INK,
                lw=0.7, zorder=4, solid_capstyle="butt")


for blk in blocks:
    r = S[(blk["arm"], blk["key"])]
    hue = ARM_COLOUR[blk["arm"]]
    pairs = [(r["precision_if_unruled_wrong"], r["precision"]),
             (r["recall"], r["recall"]),
             (r["f1_if_unruled_wrong"], r["f1"])]
    for cx, (lo, hi), (_, f) in zip(blk["bars"], pairs, METRICS):
        score_bar(ax_a, cx, lo, hi, tint(hue, f))

for ax in (ax_a, ):
    ax.set_xlim(*XLIM)
    ax.set_xticks([])
    ax.tick_params(axis="x", which="both", length=0)
    ax.tick_params(axis="y", labelsize=J.TICK, pad=1.6)
    for s in ax.spines.values():
        s.set_linewidth(0.6)

ax_a.set_ylim(0, 1.0)
ax_a.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax_a.set_ylabel("score", fontsize=J.LABEL, labelpad=2.0)

# arm and frame count under each bar group, in that arm's colour; sample name below
for blk in blocks:
    ax_a.text(blk["centre"], -0.045, f"{blk['arm']} {S[(blk['arm'], blk['key'])]['n']}",
              transform=ax_a.get_xaxis_transform(), ha="center", va="top",
              fontsize=J.TICK, color=ARM_COLOUR[blk["arm"]])
for t in ticks:
    ax_a.text(t["centre"], -0.125, t["label"], transform=ax_a.get_xaxis_transform(),
              ha="center", va="top", fontsize=J.TICK, color=J.INK, linespacing=1.15)

# ------------------------------------------------------------------------------- keys
#: Every key swatch is two-tone, half in each arm's hue, so the key says once that the
#: same shading means the same thing in blue and in orange. Which hue is which arm is
#: read off the coloured arm label under each bar group, not out of a second legend.
def _pair(f):
    #: one swatch per hue that is actually on the plate, so the key cannot show a
    #: colour the figure does not draw, or omit one it does.
    _hues = [a for a in ("SEM", "TXM")
             if any(a == arm for _, keys in SAMPLES for arm in keys)]
    return tuple(Patch(facecolor=tint(ARM_COLOUR[a], f), edgecolor=J.INK, linewidth=0.5)
                 for a in _hues)


_TUPLE = {tuple: HandlerTuple(ndivide=None, pad=0.0)}
ax_a.legend([_pair(f) for _, f in METRICS],
            [m for m, _ in METRICS], handler_map=_TUPLE,
            loc="lower right", bbox_to_anchor=(1.003, 1.005), ncol=3, frameon=False,
            handlelength=1.3, handletextpad=0.35, columnspacing=0.9,
            borderpad=0.0, borderaxespad=0.0, fontsize=J.TICK)
# Panel (b) draws ONE quantity, so it carries no legend: a key with a single entry
# repeats the y-axis label, and which hue is which arm is read off the coloured arm
# label under each bar group, exactly as in panel (a).

# The convention and the caveats are the caption's job; the plate keeps only the one
# line a reader needs to decode the whiskers it can see.
#: TWO LINES, ONE TEXT OBJECT. As two objects anchored at opposite ends of the same
#: baseline they collided, which the label check caught.
FOOT = "Whisker: every unadjudicated marked pixel counted a false positive."
fig.text(0.0075, 0.008, FOOT, ha="left", va="bottom", fontsize=J.TICK, color=J.INK,
         linespacing=1.25)


def check_text(fig):
    """Every visible string must clear every other string AND stay on the page.

    Both halves are here because the first draft passed the type check, which only reads
    font sizes, while the footnote's first line and the last legend entry ran off the
    right edge of the sheet -- the saved PNG simply did not contain the end of either
    sentence. A string that is not on the page cannot be read at any type size, so the
    extents are measured where the renderer puts them rather than estimated. The overlap
    threshold is 1 pt of real overlap in BOTH directions, so touching boxes pass and
    crossing glyphs do not.
    """
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    w, h = fig.canvas.get_width_height()
    tol = fig.dpi / 72.0
    items, off = [], []
    for t in fig.findobj(plt.Text):
        if not t.get_text().strip() or not t.get_visible():
            continue
        try:
            e = t.get_window_extent(renderer=r)
        except Exception:
            continue
        label = t.get_text().strip().replace("\n", " ")[:40]
        items.append((label, e))
        if e.x0 < -tol or e.x1 > w + tol or e.y0 < -tol or e.y1 > h + tol:
            off.append(f"{label!r} at x {e.x0:.0f}..{e.x1:.0f} y {e.y0:.0f}..{e.y1:.0f} "
                       f"on a {w}x{h} px sheet")
    bad = []
    for i in range(len(items)):
        for k in range(i + 1, len(items)):
            a, b = items[i][1], items[k][1]
            if (min(a.x1, b.x1) - max(a.x0, b.x0) > tol
                    and min(a.y1, b.y1) - max(a.y0, b.y0) > tol):
                bad.append(f"{items[i][0]!r} x {items[k][0]!r}")
    if off:
        raise SystemExit(f"{len(off)} label(s) run off the sheet: " + "; ".join(off[:4]))
    if bad:
        raise SystemExit(f"{len(bad)} overlapping label(s): " + "; ".join(bad[:6]))
    return len(items)


_strings = check_text(fig)
os.makedirs(OUT, exist_ok=True)
J.save(fig, os.path.join(OUT, NAME + ".png"), printed_width=J.PAGEW)

# ------------------------------------------------------------------------------ caption
def _r(v, n=4):
    return round(v, n)


CAPTION = dict(
    figure=NAME + ".png",
    column_class="single plate at the paper's own text width, 6.37 in. "
                 "journal_style.COLUMN_CLASS carries no row for this plate and is not "
                 "edited from here, so the class is recorded in this sidecar instead.",
    what="precision, recall and F1 for every specimen sample of both microscopies. "
         "ONE panel. The second, the area the detector marks as a percentage of all "
         "image pixels, was removed at the author's request: how much of a frame gets "
         "marked is a property of the specimen as much as of the detector, so it "
         "answers a different question from the one this plate asks. Every per-sample "
         "area number is still in `samples[*].arms[*]` below.",
    arms=dict(SEM=f"{FULL['SEM']['n_frames']} scanning-electron frames, "
                  f"{len([k for k in S if k[0] == 'SEM'])} specimen samples",
              TXM=f"{FULL['TXM']['n_frames']} transmission X-ray frames, "
                  f"{len([k for k in S if k[0] == 'TXM'])} specimen groups",
              colour="SEM is journal_style.ACCENT (blue) and TXM is ACCENT2 (orange), "
                     "the same assignment the other plates use"),
    scope="THE FULL CORPUS, not the b2/b3 subset the manuscript reports. The restricted "
          "record is read only as a check: the merged SEM b2 sample reproduces its SEM "
          "block and TXM B2+B3 reproduces its TXM block, both exactly.",
    aggregation=FULL["aggregation"],
    scoring=FULL["scoring"],
    use_region_classifier=FULL.get("use_region_classifier"),
    sem_emission=FULL.get("sem_emission"),
    txm_emission=FULL.get("txm_emission"),
    the_sem_bars_are_in_sample=(
        "the region classifier is enabled, and the images its bundle records being "
        "fitted on are the hand-painted frames scored here: 45 of 48 overlap. Every SEM "
        "bar is the detector answering about frames it was built from, and none of them "
        "is an estimate of how it will behave on a new specimen. The leave-one-frame-out "
        "refit that estimates that is docs/figures/sem_classifier_lofo.json. It is not "
        "drawn on this plate because it is a different unit set and a bar from it "
        "standing beside these would be read as comparable."
        if FULL.get("use_region_classifier") else
        "the region classifier is disabled, so no fitted weight reaches an SEM bar"),
    mad_k=FULL["mad_k"],
    min_px_each_verdict=FULL["min_px_each_verdict"],
    the_convention_that_decides_precision=dict(
        why="the detector marks pixels outside the painted region that nobody ruled on. "
            "Excluding them is `precision`, which is where every BAR is drawn; counting "
            "every one of them as a false positive is "
            "`precision_if_unrefereed_wrong`, which is where the WHISKER ends. The bar "
            "carries the score over the pixels that actually hold a verdict; the "
            "whisker carries a bound, which asserts that every marked pixel nobody "
            "ruled on is a false positive and is not itself measured on this corpus. "
            "Both numbers are below, per sample, either way.",
        SEM_all_18_frames=dict(
            precision_unruled_excluded=_r(FULL["SEM"]["mean_precision"]),
            precision_unruled_counted_wrong=_r(
                FULL["SEM"]["mean_precision_if_unrefereed_wrong"]),
            f1_unruled_excluded=_r(FULL["SEM"]["mean_f1"]),
            f1_unruled_counted_wrong=_r(FULL["SEM"]["mean_f1_if_unrefereed_wrong"])),
        SEM_the_11_b2_frames_the_manuscript_reports=dict(
            precision_unruled_excluded=_r(B2B3["SEM"]["mean_precision"]),
            precision_unruled_counted_wrong=_r(
                B2B3["SEM"]["mean_precision_if_unrefereed_wrong"])),
        TXM_all_31_frames=dict(
            precision_unruled_excluded=_r(FULL["TXM"]["mean_precision"]),
            precision_unruled_counted_wrong=_r(
                FULL["TXM"]["mean_precision_if_unrefereed_wrong"])),
        recall="unchanged by the convention in both arms: its denominator is painted "
               "crack and an unruled pixel is not in it, so recall carries no whisker."),
    removed_panel_b="the area-marked panel is gone from the plate. The numbers it "
                    "drew -- marked_pct_of_image, and its split into "
                    "marked_pct_inside_adjudicated and marked_pct_where_nobody_ruled "
                    "-- are unchanged and still recorded per sample below.",
    samples=[
        dict(sample=label.replace("\n", " "), record_key=dict(keys),
             arms={a: dict(
                 n=S[(a, k)]["n"],
                 precision=_r(S[(a, k)]["precision"]),
                 precision_if_unruled_wrong=_r(S[(a, k)]["precision_if_unruled_wrong"]),
                 recall=_r(S[(a, k)]["recall"]),
                 f1=_r(S[(a, k)]["f1"]),
                 f1_if_unruled_wrong=_r(S[(a, k)]["f1_if_unruled_wrong"]),
                 marked_pct_of_image=_r(S[(a, k)]["marked_pct"], 3),
                 marked_pct_inside_adjudicated=_r(
                     S[(a, k)]["marked_adjudicated_pct"], 3),
                 marked_pct_where_nobody_ruled=_r(S[(a, k)]["marked_unruled_pct"], 3),
                 painted_crack_pct_of_image=_r(S[(a, k)]["painted_crack_pct"], 3),
                 adjudicated_coverage_pct=_r(S[(a, k)]["adjudicated_coverage_pct"], 2),
                 pooled_over_pixels={kk: _r(vv, 4) for kk, vv in
                                     S[(a, k)]["pooled"].items()},
                 drawn=bool(_keep(a, k)),
                 frames=S[(a, k)]["frames"]) for a, k in keys.items()})
        #: ALL of them, drawn or not. The plate withholds the groups below the line;
        #: the record must not, or the figure's scope becomes unrecoverable.
        for label, keys in ALL_SAMPLES],
    selection=dict(
        rule=f"a bar group is drawn when its F1 is at least {KEEP_F1:g}",
        why=("the author asked for the groups that do not yet work to come off the "
             "plate and be listed as work to do. Selecting survivors BY their scores "
             "makes the remaining panel an estimate of nothing, so the threshold is "
             "stated, fixed in one place, applied to both microscopies alike, "
             "and every group it "
             "removes is named on the plate with its own score"),
        threshold_f1=KEEP_F1,
        drawn=[f"{a} {k}" for _, keys in SAMPLES for a, k in keys.items()],
        not_drawn=[dict(sample=lab.replace("\n", " "), arm=a, key=k, f1=_r(f1))
                   for lab, a, k, f1 in DROPPED],
        unselected_figure="rebuild with SHOW_ALL=1 to draw every group"),
    how_the_samples_were_derived=dict(
        TXM="the record's own `group` field, one of B2, B3, Wrought, AM/HC",
        SEM="no group field exists, so the specimen key is derived from the frame name by "
            "the rule analysis/research/improve/unetctx_base.py:specimen_of already uses "
            "- <specimen>_<detector>_<index> with the detector token CBS / ETD / SE / "
            "BSE, and a trailing front/back is a fracture surface, not a specimen",
        the_only_regrouping="260622_316_H_b2 (2 frames) and 260708_316_H_b2 (9 frames) "
                            "are specimen series b2 on two dates and are drawn as one b2 "
                            "sample. Their separate values are below.",
        b2_by_imaging_date={
            k: dict(n=len(v), precision=_r(st.mean(f["precision"] for f in v)),
                    precision_if_unruled_wrong=_r(
                        st.mean(f["precision_if_unrefereed_wrong"] for f in v)),
                    recall=_r(st.mean(f["recall"] for f in v)),
                    f1=_r(st.mean(f["f1"] for f in v)),
                    marked_pct_of_image=_r(
                        st.mean(areas(f)["marked_pct"] for f in v), 3))
            for k, v in sorted(
                {kk: [f for f in FULL["SEM"]["per_frame"]
                      if specimen_of(f["frame"]) == kk] for kk in SEM_SERIES}.items())}),
    breakdowns_that_could_not_be_sourced=[
        "There is no SEM b3 sample. No labelled SEM b3 frame exists in this corpus - "
        "every SEM lab correction in the paper's scope is b2 - so b3 carries a TXM bar "
        "and no SEM bar. The script aborts if one ever appears.",
        "The SEM and TXM sample sets overlap in ONE sample, b2. TXM's Wrought and AM/HC "
        "groups have no SEM counterpart in this record, and SEM's AS_24hr and the three "
        "MAR_Amb specimens have no TXM counterpart. Only the b2 pair is an "
        "arm-to-arm comparison; the rest of the axis is two different specimen sets "
        "drawn on one axis, and no bar of one arm may be read against a bar of the other "
        "outside b2.",
        "No per-sample breakdown of the public Inconel 718 collection is drawn. "
        "arms_background_units.json is one external collection, not this laboratory's "
        "specimen series, and it carries no specimen grouping at all.",
        "Every SEM sample other than b2 rests on 1 to 3 frames, and MAR_Amb_Cast and "
        "AS_24hr on one frame each. Those bars are single measurements and carry no "
        "spread; no error bar is drawn on them because there is none to draw.",
    ],
    caveats=[
        "The adjudicated area is NOT a sample of the frame. On the SEM frames the "
        "operator painted mostly crack - the adjudicated pixels of every SEM sample are "
        "between 87% and 99.7% crack - while on the TXM frames they are 2.6% to 22% "
        "crack. Precision and recall are therefore computed against very differently "
        "composed references in the two arms, and that is why panel (b) is a percentage "
        "of ALL image pixels rather than of the adjudicated area: the adjudicated areas "
        "are not comparable denominators between the arms.",
        "The operator's marking is a region assertion, not an outline. It is deliberately "
        "broader than the feature in both arms, so precision is scored against a brush "
        "and not against a crack boundary.",
        "Panel (b) is drawn as a mean over frames so that it matches panel (a). Pooled "
        "over pixels every value changes, by up to 2.7 percentage points (TXM Wrought, "
        "17.2 to 19.9), because the frames of this corpus span 0.12 M to 25 M pixels and "
        "one frame can carry a group. Both aggregations are recorded per sample above.",
        "Panel (b) is the area the detector marks, not an error: a sample where it marks "
        "little can be a sample where it finds little. Read it with the recall bar "
        "directly above it - TXM AM/HC marks 10.4% of the frame at recall 0.13, and SEM "
        "MAR_Amb_AS marks 5.1% at recall 0.14, and those are opposite failures.",
        "The b3 bars read high (TXM F1 0.90) and Section 4.3's measurement of what that "
        "group's painted crack is should be read with them: its median painted pixel has "
        "essentially zero optical density.",
    ],
    checks_that_abort_this_script=[
        "every per-frame precision, recall and F1 equals frame_legibility.json's, which "
        f"is a second scoring pass ({FULL['SEM']['n_frames'] + FULL['TXM']['n_frames']} "
        "frames checked)",
        "the tp/fp pixel counts reconstructed here from precision, recall and crack_px "
        "reproduce txm_background_units.json's independently generated by_group "
        f"accounting at {TXM_ARM} - tp_pct, fp_pct, marked_pct and crack_px on all four "
        "groups, to 1 part in 1e6. That record was written by a different script, so it "
        "is the positive control for the same reconstruction applied to the SEM arm, "
        "where no such accounting exists",
        "the merged SEM b2 sample reproduces overlap_means_sem_txm_b2b3.json's SEM block "
        "(n and all five means) exactly, so the merge is checked and not asserted",
        "TXM B2 and B3 together reproduce that record's TXM block",
        "no SEM frame resolves to a b3 specimen",
        "every sample in the records is drawn and every sample drawn is in the records",
        f"{_strings} drawn strings measured at the renderer's own extents: no pair "
        f"overlapping by more than 1 pt in both directions, and none running off the "
        f"sheet",
    ],
    generated_from={
        "docs/figures/overlap_means_sem_txm.json":
            "per-frame precision, recall, F1, both unruled-pixel bounds, crack_px, "
            "notcrack_px, refereed_frac, marked_px_nobody_refereed - every drawn value "
            "is this file or arithmetic on it",
        "docs/figures/overlap_means_sem_txm_b2b3.json": "check only, nothing drawn",
        "docs/figures/txm_background_units.json": "check only, nothing drawn",
        "docs/figures/frame_legibility.json": "check only, nothing drawn",
        "analysis/research/improve/unetctx_base.py": "the specimen_of rule, reproduced",
    },
)
json.dump(CAPTION, open(os.path.join(OUT, NAME + ".caption.json"), "w"),
          indent=1, ensure_ascii=False)
print(f"caption written ({_strings} strings checked)")
