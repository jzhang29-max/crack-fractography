"""F9 - how the model class was chosen, and what choosing it was worth.

WHAT F7 LEAVES OPEN. F7 asks which DETECTOR ARM to carry -- Otsu, Sauvola, a ridge
filter, this detector -- and it is careful to put the same candidate list on both
microscopies. It says in its own docstring that the learned models could not go on those
axes, because the transmission models have no scanning-electron counterpart. So nothing
in the figure set yet answers the question one rung down: inside the detector, which
MODEL CLASS, and why is it a logistic regression on one instrument and a neural network
on the other?

This plate answers that, from the bake-offs this project actually ran. Every number is
read from a record written by the run that produced it; none is typed in here, and the
checks at the bottom fail the build rather than let a stale one through.

THE ANSWER IS NOT "LOGISTIC REGRESSION WON", AND THE PLATE SHOULD NOT SAY THAT.

  (a) On the scanning-electron region classifier the four candidates were scored two
      ways, and THE TWO WAYS DISAGREE ABOUT THE WINNER. Pooled cross-validation grouped
      by image puts the logistic regression alone above chance and the other three at or
      below it. Leave-one-image-out on a single held-out frame puts the RBF support
      vector machine first -- the same model that scores 0.281 pooled, which is below
      chance by more than the logistic regression is above it. One frame is one frame.
      The earlier bundle, fitted on 32 images instead of 47, selected the SVC outright.
      So the choice moved when the corpus grew, and the protocol decides it.

  (b) On the second-pass unified model, eleven features and eight candidate classes, the
      logistic regression does NOT win either: it is 0.892 against the SVC's 0.894, a
      gap of 0.002 against run-to-run spreads of 0.016 and 0.018. It is a tie. What the
      panel does show is the two arms that fail -- a two-layer neural network collapses
      to 0.542, near chance, on 329 examples in 25 groups.

  (c) WHAT THE CHOSEN MODEL IS WORTH, which is the panel that matters. Scored on the 18
      frames carrying enough referee to score, the region classifier is beaten on F1 by
      the area floor with no model in it at all: 0.6470 against 0.6376. It buys about a
      point of precision and gives back two of recall. Leaving the frame out of the fit
      changes almost nothing (0.6387 in-sample against 0.6363 leave-one-frame-out), so
      this is not overfitting -- the model is close to inert at frame scale, and the
      ranking in (a) and (b) is a ranking among options that mostly do not matter.

  (d) The transmission instrument gives the opposite answer, and that is the point of
      drawing both. Under one leave-one-image-out protocol over four labelled mosaics,
      the multilayer perceptron clears the tree ensembles by 0.042-0.055 IoU and the
      logistic regression by 0.187. There the model class is doing real work.

  TAKEN TOGETHER: a learned classifier earns its place on the transmission frames and
  does not earn it on the scanning-electron frames, and the honest reason the scanning
  arm carries a logistic regression is that it is the only candidate that never
  collapses -- not that it won.

THE ONE COMPARISON ON THIS PLATE THAT IS NOT LIKE FOR LIKE, stated here because it is
visible in panel (d) and a reader will otherwise take it for a model-class result. In
the transmission bake-off the tree ensembles and the perceptron were given all 17
channels; the logistic regression and the depth-3 tree were run as the INTERPRETABLE
tier on the four channels a random forest ranked highest. Part of the 0.187 gap is
therefore the feature set, not the model class, and the panel annotates every bar with
its channel count so the confound is on the plate rather than in a footnote. The run
that would separate them -- the same logistic regression on all 17 channels -- cannot be
added, because generate_benchmark_report.py, which held the sampling, the fold split and
the seed, is not in the archived repository any more; only its outputs are. Re-running a
reconstructed protocol would be a second instrument, and a before/after needs one.

SOURCES, all of them records written by the run they describe:
  sem-crack-detector/models/crack_classifier_v3_metrics.json          panel (a)
  sem-crack-detector/archive/superseded_models/
      crack_classifier_v2_metrics.json                                panel (a) history
  sem-crack-detector/interior_active_learning/code/experiments/
      benchmark_results_unified.json                                  panel (b)
  crack-fractography/docs/figures/sem_classifier_lofo.json            panel (c)
  TXM_Crack_Detection_Pipeline/research/benchmark_figures/
      benchmark_summary.json, extended_summary.json                   panel (d)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths                                       # noqa: E402

import numpy as np                                  # noqa: E402
import matplotlib                                   # noqa: E402
matplotlib.use("Agg")                               # noqa: E402
import matplotlib.pyplot as plt                     # noqa: E402

import journal_style as J                           # noqa: E402

J.use()
OUT = _paths.FIG_DIR
os.makedirs(OUT, exist_ok=True)
NAME = "F9 - how the model class was chosen"

SEM = _paths.SEM_REPO
TXM = _paths.TXM_REPO

P_V3 = os.path.join(SEM, "models", "crack_classifier_v3_metrics.json")
P_V2 = os.path.join(SEM, "archive", "superseded_models", "crack_classifier_v2_metrics.json")
P_UNI = os.path.join(SEM, "interior_active_learning", "code", "experiments",
                     "benchmark_results_unified.json")
P_LOFO = os.path.join(_paths.REPO, "docs", "figures", "sem_classifier_lofo.json")
P_TXM_BASE = os.path.join(TXM, "research", "benchmark_figures", "benchmark_summary.json")
P_TXM_EXT = os.path.join(TXM, "research", "benchmark_figures", "extended_summary.json")

for p, what, env in ((P_V3, "the shipped region classifier's metrics", "SEM_REPO"),
                     (P_V2, "the superseded v2 metrics", "SEM_REPO"),
                     (P_UNI, "the unified-model bake-off", "SEM_REPO"),
                     (P_TXM_BASE, "the transmission bake-off", "TXM_REPO"),
                     (P_TXM_EXT, "the transmission extended arms", "TXM_REPO")):
    _paths.require(p, what, env)

V3 = json.load(open(P_V3))
V2 = json.load(open(P_V2))
UNI = json.load(open(P_UNI))
LOFO = json.load(open(P_LOFO))
TB = json.load(open(P_TXM_BASE))
TE = json.load(open(P_TXM_EXT))

#: Short labels. The records spell the classes differently in different files; this is the
#: one place the spellings are reconciled, so a rename in one record cannot silently drop
#: a bar (the checks below assert every record key is consumed).
SHORT = {
    "LogisticRegression": "logistic regression",
    "RandomForest": "random forest",
    "GradientBoosting": "gradient boosting",
    "HistGradientBoosting": "hist. gradient boosting",
    "ExtraTrees": "extra trees",
    "SVC (RBF)": "SVM (RBF)",
    "GaussianNB": "Gaussian naive Bayes",
    "KNeighbors (k=5)": "k-nearest neighbours",
    "NeuralNet (8,)": "neural net (8)",
    "NeuralNet (32,16)": "neural net (32, 16)",
}
CHOSEN_SEM = "LogisticRegression"

# =======================================================================================
# the numbers, pulled out of the records
# =======================================================================================
# --- (a) pass-1 region classifier, two protocols --------------------------------------
A_MODELS = list(V3["cv_results"])
A_POOLED = [V3["cv_results"][m]["pooled_auc"] for m in A_MODELS]
A_POOLED_SD = [V3["cv_results"][m]["pooled_auc_std"] for m in A_MODELS]
A_LOIO = [V3["cv_results"][m]["loio_auc_exhaustive_image"] for m in A_MODELS]
A_V2 = {m: V2["cv_results"][m]["auc"] for m in V2["cv_results"]}

# --- (b) pass-2 unified model ----------------------------------------------------------
B_MODELS = sorted(UNI["results"], key=lambda m: UNI["results"][m]["auc_mean"])
B_AUC = [UNI["results"][m]["auc_mean"] for m in B_MODELS]
B_SD = [UNI["results"][m]["auc_std"] for m in B_MODELS]
B_RUNS = {m: UNI["results"][m]["per_run_auc"] for m in B_MODELS}

# --- (c) what the chosen model is worth, at frame scale --------------------------------
C_ARMS = [("floor", "no model (area floor)"),
          ("refit_all", "+ logistic reg., in-sample"),
          ("lofo_matched", "+ logistic reg., frame held out")]
C_METRICS = [("mean_precision", "sd_precision", "precision"),
             ("mean_recall", "sd_recall", "recall"),
             ("mean_f1", "sd_f1", "F1")]

# --- (d) transmission bake-off ---------------------------------------------------------
TIERS = TE["interpretability_tiers"]
N_ALL = TB["protocol"]["n_features"]
N_TOP = len(TIERS["top4_features"])
D_ROWS = [
    ("Otsu threshold", TIERS["otsu"]["mean"]["iou"], None, 1, False),
    ("logistic regression", TIERS["logistic_regression"]["mean"]["iou"], None, N_TOP, False),
    ("decision tree (d=3)", TIERS["decision_tree"]["mean"]["iou"], None, N_TOP, False),
    ("extra trees", TB["models"]["ExtraTrees"]["mean"]["iou"],
     TB["models"]["ExtraTrees"]["std"]["iou"], N_ALL, False),
    ("random forest", TB["models"]["RandomForest"]["mean"]["iou"],
     TB["models"]["RandomForest"]["std"]["iou"], N_ALL, False),
    ("hist. grad. boosting", TB["models"]["HistGradientBoosting"]["mean"]["iou"],
     TB["models"]["HistGradientBoosting"]["std"]["iou"], N_ALL, False),
    ("neural net (64, 32)", TE["neural_network"]["mean"]["iou"],
     TE["neural_network"]["std"]["iou"], N_ALL, True),
]

# =======================================================================================
# the plate
# =======================================================================================
fig = plt.figure(figsize=(J.PAGEW, 6.35))
gs = fig.add_gridspec(2, 2, hspace=0.64, wspace=0.70,
                      left=0.215, right=0.955, top=0.915, bottom=0.115)
axa = fig.add_subplot(gs[0, 0])
axb = fig.add_subplot(gs[0, 1])
axc = fig.add_subplot(gs[1, 0])
axd = fig.add_subplot(gs[1, 1])

from matplotlib.lines import Line2D                 # noqa: E402

CHOSEN_C, OTHER_C, SECOND_C = J.ACCENT, J.G_MID, J.ACCENT2
FS = J.FLOOR          # journal_style reserves SCRIPT_FLOOR for sub/superscripts only


def _chance(ax):
    """The 0.5 line. It is NAMED IN THE AXIS LABEL, not beside the line: a text anchored
    to the line collided with the panel title above it in the first render."""
    ax.axvline(0.5, color=J.INK, lw=0.7, ls=(0, (3, 2)), zorder=1)


def _hbars(ax, labels, vals, sds, colours):
    """Best at the top, in every panel of this plate, so one reading order serves all."""
    y = np.arange(len(labels))
    ax.barh(y, vals, height=0.62, color=colours, zorder=3)
    if any(s for s in sds):
        ax.errorbar(vals, y, xerr=[(s or 0) for s in sds], fmt="none",
                    ecolor=J.INK, elinewidth=0.7, capsize=1.8, zorder=4)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=FS)
    ax.set_ylim(len(labels) - 0.5, -0.5)            # index 0 at the top
    ax.set_xlim(0, 1.0)
    ax.tick_params(axis="y", pad=2)
    return y


# --- (a) ------------------------------------------------------------------------------
oa = sorted(range(len(A_MODELS)), key=lambda i: -A_POOLED[i])
ya = _hbars(axa, [SHORT[A_MODELS[i]] for i in oa], [A_POOLED[i] for i in oa],
            [A_POOLED_SD[i] for i in oa],
            [CHOSEN_C if A_MODELS[i] == CHOSEN_SEM else OTHER_C for i in oa])
axa.scatter([A_LOIO[i] for i in oa], ya, s=15, marker="D", facecolors="none",
            edgecolors=J.INK, linewidths=0.8, zorder=5)
axa.set_xlabel("ROC AUC, dashed line chance\nbars pooled CV by image,\ndiamonds one held-out image", fontsize=FS)
axa.set_title(f"(a)  first-pass region classifier\n"
              f"{V3['n_images']} images, {V3['n_train']:,} regions, 8 features",
              fontsize=FS, loc="left")
_chance(axa)

# --- (b) ------------------------------------------------------------------------------
ob = sorted(B_MODELS, key=lambda m: -UNI["results"][m]["auc_mean"])
yb = _hbars(axb, [SHORT[m] for m in ob], [UNI["results"][m]["auc_mean"] for m in ob],
            [UNI["results"][m]["auc_std"] for m in ob],
            [CHOSEN_C if m == CHOSEN_SEM else OTHER_C for m in ob])
for i, m in enumerate(ob):
    axb.scatter(B_RUNS[m], [i] * len(B_RUNS[m]), s=2.5, color=J.INK, zorder=5,
                alpha=0.9, linewidths=0)
axb.set_xlabel("ROC AUC, dashed line chance\nbars mean of five runs,\ndots the runs", fontsize=FS)
axb.set_title(f"(b)  second-pass unified model\n"
              f"{UNI['n_examples']} regions in {UNI['n_groups']} groups, 11 features",
              fontsize=FS, loc="left")
_chance(axb)

# --- (c) ------------------------------------------------------------------------------
w = 0.26
xs = np.arange(len(C_METRICS))
for k, (key, lab) in enumerate(C_ARMS):
    rec = LOFO["all_frames"][key]
    axc.bar(xs + (k - 1) * w, [rec[m] for m, _s, _n in C_METRICS], width=w * 0.9,
            color=[J.G_DARK, SECOND_C, CHOSEN_C][k], zorder=3, label=lab)
    axc.errorbar(xs + (k - 1) * w, [rec[m] for m, _s, _n in C_METRICS],
                 yerr=[rec[s] for _m, s, _n in C_METRICS], fmt="none",
                 ecolor=J.INK, elinewidth=0.7, capsize=1.6, zorder=4)
axc.set_xticks(xs)
axc.set_xticklabels([n for _m, _s, n in C_METRICS], fontsize=FS)
axc.set_ylim(0, 1.42)
axc.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
axc.set_ylabel("mean over frames", fontsize=FS)
axc.set_title(f"(c)  what that model is worth on a frame\n"
              f"{LOFO['frames_scored']} refereed frames, mask level",
              fontsize=FS, loc="left")
#: The legend goes BELOW the panel, where there are no bars for it to sit on top of.
axc.legend(fontsize=FS, frameon=False, loc="upper left", ncol=1,
           handlelength=0.9, handletextpad=0.5, borderaxespad=0.1, labelspacing=0.25)

_f_floor = LOFO["all_frames"]["floor"]["mean_f1"]
_f_lofo = LOFO["all_frames"]["lofo_matched"]["mean_f1"]
#: Inside the axes. Placed above the panel it overlapped (d)'s first tick label.
#: Bottom right, below every bar and whisker in the F1 group. Placed level with the
#: legend it overlapped the legend's third entry, which the collision guard caught.
axc.text(2.45, 0.05, f"the model lowers\nF1 by {_f_floor - _f_lofo:.4f}",
         ha="right", va="bottom", fontsize=FS, color=J.INK, linespacing=1.3)

# --- (d) ------------------------------------------------------------------------------
od = sorted(D_ROWS, key=lambda r: -r[1])
yd = _hbars(axd, [r[0] for r in od], [r[1] for r in od], [r[2] for r in od],
            [CHOSEN_C if r[4] else OTHER_C for r in od])
#: The channel count sits INSIDE the bar. Printed after the bar end it collided with the
#: error-bar caps, which is how the first render of this plate shipped.
for i, r in enumerate(od):
    axd.text(0.022, i, f"{r[3]} ch", va="center", ha="left", fontsize=FS,
             color="white", zorder=6)
axd.set_xlabel("IoU\nch = channels the arm was given", fontsize=FS)
axd.set_title(f"(d)  transmission, per pixel\n"
              f"leave-one-image-out over {TB['protocol']['n_images']} mosaics",
              fontsize=FS, loc="left")

for ax in (axa, axb, axc, axd):
    ax.tick_params(labelsize=FS)
    for _sp in ("top", "right"):
        ax.spines[_sp].set_visible(False)

#: TEXT COLLISIONS, measured rather than looked at. Three separate renders of this plate
#: shipped overlapping labels, a legend clipped off the bottom of the sheet and an axis
#: label running past the right edge, and each was caught by eye on the next look. The
#: same check mk_parameters.py applies is applied here: every visible string -- titles,
#: axis labels, tick labels, legend entries, free text -- measured at the renderer's own
#: extents, and any pair overlapping by more than 1 pt, or anything leaving the sheet,
#: fails the build.
fig.canvas.draw()
_rend = fig.canvas.get_renderer()
_pw, _ph = (fig.get_size_inches() * fig.dpi)
_measured = []
for _ax in (axa, axb, axc, axd):
    #: ALL THREE title artists. `ax.title` is only the CENTRED title; a title set with
    #: loc="left" -- which every panel here uses -- lives in `ax._left_title`, so a guard
    #: that measures `ax.title` alone measures nothing and reports PASS. That is how the
    #: first version of this check passed a plate whose row-two titles ran into row one's
    #: axis labels.
    _measured += [getattr(_ax, "title", None), getattr(_ax, "_left_title", None),
                  getattr(_ax, "_right_title", None),
                  _ax.xaxis.label, _ax.yaxis.label]
    _measured += list(_ax.get_xticklabels()) + list(_ax.get_yticklabels())
    _measured += list(_ax.texts)
    _lg = _ax.get_legend()
    if _lg is not None:
        _measured += list(_lg.get_texts())
_boxes = []
for _t in _measured:
    if _t is None or not _t.get_text().strip() or not _t.get_visible():
        continue
    try:
        _boxes.append((_t.get_text().strip().replace("\n", " ")[:40],
                       _t.get_window_extent(renderer=_rend)))
    except Exception:
        continue
_TOL = 1.0
_bad = [f"{_boxes[i][0]!r} x {_boxes[k][0]!r}"
        for i in range(len(_boxes)) for k in range(i + 1, len(_boxes))
        if (min(_boxes[i][1].x1, _boxes[k][1].x1)
            - max(_boxes[i][1].x0, _boxes[k][1].x0) > _TOL
            and min(_boxes[i][1].y1, _boxes[k][1].y1)
            - max(_boxes[i][1].y0, _boxes[k][1].y0) > _TOL)]
_off = [n for n, e in _boxes
        if e.x0 < -_TOL or e.x1 > _pw + _TOL or e.y0 < -_TOL or e.y1 > _ph + _TOL]
if _bad or _off:
    raise SystemExit(
        f"mk_model_class.py: {len(_bad)} overlapping label(s): {'; '.join(_bad[:8])}"
        + (f"   |   {len(_off)} off the sheet: {'; '.join(repr(x) for x in _off[:8])}"
           if _off else ""))
N_STRINGS = len(_boxes)

# =======================================================================================
# checks -- these fail the build rather than ship a plate that disagrees with its record
# =======================================================================================
fail = []

if set(A_MODELS) != set(V2["cv_results"]):
    fail.append("v2 and v3 scored different model sets; the history sentence in the "
                "caption assumes the same four")
if V3["best"] != CHOSEN_SEM:
    fail.append(f"v3 records best={V3['best']!r}, not {CHOSEN_SEM!r}")
if V2["best"] == CHOSEN_SEM:
    fail.append("v2 now records the logistic regression as best; the caption says the "
                "selection MOVED when the corpus grew")
_best_loio = max(A_MODELS, key=lambda m: V3["cv_results"][m]["loio_auc_exhaustive_image"])
if _best_loio == CHOSEN_SEM:
    fail.append("the one-image protocol now also picks the logistic regression; panel "
                "(a)'s whole point is that the two protocols disagree")
_best_pooled = max(A_MODELS, key=lambda m: V3["cv_results"][m]["pooled_auc"])
if _best_pooled != CHOSEN_SEM:
    fail.append(f"pooled CV now picks {_best_pooled!r}")

_b_best = max(B_MODELS, key=lambda m: UNI["results"][m]["auc_mean"])
if _b_best == CHOSEN_SEM:
    fail.append("the unified bake-off now has the logistic regression outright first; "
                "the caption calls it a tie for second")
_gap = UNI["results"][_b_best]["auc_mean"] - UNI["results"][CHOSEN_SEM]["auc_mean"]
if _gap > min(UNI["results"][_b_best]["auc_std"], UNI["results"][CHOSEN_SEM]["auc_std"]):
    fail.append(f"the gap to {_b_best} is {_gap:.4f}, larger than either run-to-run "
                f"spread, so calling it a tie is no longer supported")

if _f_floor <= _f_lofo:
    fail.append("the model no longer lowers F1 against the no-model floor; panel (c)'s "
                "annotation is wrong")
_insample = LOFO["all_frames"]["refit_all"]["mean_f1"]
if abs(_insample - _f_lofo) > 0.01:
    fail.append(f"in-sample and leave-one-frame-out F1 now differ by "
                f"{abs(_insample - _f_lofo):.4f}; the caption says leakage is negligible")

_d_top = max(D_ROWS, key=lambda r: r[1])
if not _d_top[4]:
    fail.append(f"the transmission bake-off's best arm is now {_d_top[0]!r}, not the "
                f"perceptron the application carries")
_lr_txm = [r for r in D_ROWS if r[0] == "logistic regression"][0]
if _lr_txm[3] == N_ALL:
    fail.append("the transmission logistic regression now has all channels, so the "
                "like-for-like caveat in the docstring is stale")

# every model in every record reached an axis, so a renamed key cannot drop a bar
_unlabelled = sorted((set(A_MODELS) | set(B_MODELS) | set(V2["cv_results"]))
                     - set(SHORT))
if _unlabelled:
    fail.append(f"no short label for: {_unlabelled}")

if fail:
    raise SystemExit("mk_model_class.py: the records no longer support the plate:\n  "
                     + "\n  ".join(fail))

J.save(fig, os.path.join(OUT, NAME + ".png"))
plt.close(fig)


# =======================================================================================
# caption sidecar
# =======================================================================================
CAPTION = dict(
    figure=NAME + ".png",
    column_class="single plate at the paper's own text width, 6.37 in",
    what="which model class each microscopy's detector carries, why, and -- panel (c) -- "
         "what the choice was worth once it was measured on frames rather than on "
         "held-out rows.",
    panels={
        "a": {
            "record": "sem-crack-detector/models/crack_classifier_v3_metrics.json",
            "n_images": V3["n_images"], "n_regions": V3["n_train"],
            "n_pos": V3["n_pos"], "n_neg": V3["n_neg"],
            "selected": V3["best"], "threshold": V3["threshold"],
            "pooled_cv_grouped_by_image": {m: round(V3["cv_results"][m]["pooled_auc"], 4)
                                           for m in A_MODELS},
            "pooled_cv_sd": {m: round(V3["cv_results"][m]["pooled_auc_std"], 4)
                             for m in A_MODELS},
            "one_held_out_image": {
                m: round(V3["cv_results"][m]["loio_auc_exhaustive_image"], 4)
                for m in A_MODELS},
            "held_out_image": V3["held_out_image"],
            "the_two_protocols_disagree":
                f"pooled CV ranks {_best_pooled} first and it is the only arm above "
                f"chance; the single held-out image ranks {_best_loio} first at "
                f"{V3['cv_results'][_best_loio]['loio_auc_exhaustive_image']:.4f} while "
                f"that same arm scores "
                f"{V3['cv_results'][_best_loio]['pooled_auc']:.4f} pooled. One frame is "
                f"one frame, and it is the pooled column the selection used.",
            "history": {
                "record": "sem-crack-detector/archive/superseded_models/"
                          "crack_classifier_v2_metrics.json",
                "n_images": V2["n_images"], "n_regions": V2["n_train"],
                "selected_then": V2["best"],
                "auc_then": {m: round(V2["cv_results"][m]["auc"], 4) for m in A_V2},
                "sd_then": {m: round(V2["cv_results"][m]["auc_std"], 4)
                            for m in V2["cv_results"]},
                "note": "at 32 images every arm sits inside every other arm's standard "
                        "deviation, so that bake-off did not separate them and the "
                        "selection it made was not supported. Not drawn; recorded here.",
            },
        },
        "b": {
            "record": "sem-crack-detector/interior_active_learning/code/experiments/"
                      "benchmark_results_unified.json",
            "n_examples": UNI["n_examples"], "n_groups": UNI["n_groups"],
            "n_pos": UNI["n_pos"], "n_neg": UNI["n_neg"], "n_features": 11,
            "auc_mean": {m: round(UNI["results"][m]["auc_mean"], 4) for m in B_MODELS},
            "auc_sd": {m: round(UNI["results"][m]["auc_std"], 4) for m in B_MODELS},
            "per_run_auc": {m: [round(x, 4) for x in B_RUNS[m]] for m in B_MODELS},
            "it_is_a_tie": f"{_b_best} leads the logistic regression by {_gap:.4f}, "
                           f"against run-to-run spreads of "
                           f"{UNI['results'][_b_best]['auc_std']:.4f} and "
                           f"{UNI['results'][CHOSEN_SEM]['auc_std']:.4f}.",
            "what_fails": "the two-layer neural network at "
                          f"{UNI['results']['NeuralNet (32,16)']['auc_mean']:.4f} is at "
                          f"chance on this many examples; the one-layer net and Gaussian "
                          f"naive Bayes trail the leaders by 0.046 and 0.067.",
        },
        "c": {
            "record": "docs/figures/sem_classifier_lofo.json",
            "question": LOFO["question"],
            "aggregation": LOFO["aggregation"], "scoring": LOFO["scoring"],
            "frames_scored": LOFO["frames_scored"],
            "mad_k": LOFO["mad_k"],
            "deployed_threshold": LOFO["deployed_threshold"],
            "arms": {k: LOFO["arms"][k] for k, _lab in C_ARMS},
            "means": {k: {m.replace("mean_", ""): round(LOFO["all_frames"][k][m], 4)
                          for m, _s, _n in C_METRICS} for k, _lab in C_ARMS},
            "sd": {k: {s.replace("sd_", ""): round(LOFO["all_frames"][k][s], 4)
                       for _m, s, _n in C_METRICS} for k, _lab in C_ARMS},
            "the_finding": f"the area floor with no model in it scores F1 "
                           f"{_f_floor:.4f}; adding the logistic regression gives "
                           f"{_f_lofo:.4f} with the frame left out of the fit and "
                           f"{_insample:.4f} in-sample. It buys "
                           f"{LOFO['all_frames']['lofo_matched']['mean_precision'] - LOFO['all_frames']['floor']['mean_precision']:+.4f} "
                           f"precision for "
                           f"{LOFO['all_frames']['lofo_matched']['mean_recall'] - LOFO['all_frames']['floor']['mean_recall']:+.4f} "
                           f"recall.",
            "leakage": f"in-sample minus leave-one-frame-out is {_insample - _f_lofo:+.4f} "
                       f"in F1, so the ranking is not a leakage artefact; the model is "
                       f"close to inert at this scale.",
            "why_it_is_on_anyway": "detector_overrides.USE_REGION_CLASSIFIER is True by "
                                   "the author's decision and is recorded there as a "
                                   "trade, not an upgrade: on the 25 hand-labelled tiles "
                                   "excluding the off-specimen flood tile it raises "
                                   "precision and lowers recall, IoU and F1. Everything "
                                   "downstream is measured at that setting.",
            "spread_is_large": "the standard deviations here are 0.24-0.29 on recall and "
                               "F1 across 18 frames. Read the arms as indistinguishable, "
                               "which is the claim; the ordering within that is not one.",
        },
        "d": {
            "records": ["TXM_Crack_Detection_Pipeline/research/benchmark_figures/"
                        "benchmark_summary.json",
                        "TXM_Crack_Detection_Pipeline/research/benchmark_figures/"
                        "extended_summary.json"],
            "protocol": TB["protocol"],
            "images": TB["protocol"]["images"],
            "iou_mean": {r[0]: round(r[1], 4) for r in D_ROWS},
            "iou_sd": {r[0]: (round(r[2], 4) if r[2] is not None else None)
                       for r in D_ROWS},
            "channels_given": {r[0]: r[3] for r in D_ROWS},
            "top4_features": TIERS["top4_features"],
            "logistic_regression_equation": TIERS["logistic_regression"]["equation"],
            "perceptron": TE["neural_network"]["params"],
            "not_like_for_like": "the tree ensembles and the perceptron were given all "
                                 f"{N_ALL} channels; the logistic regression and the "
                                 f"depth-3 tree were the interpretable tier on the "
                                 f"{N_TOP} channels a random forest ranked highest. Part "
                                 f"of the gap is the feature set, not the model class. "
                                 f"The arm that would separate them cannot be added: "
                                 f"generate_benchmark_report.py, which held the "
                                 f"sampling, the folds and the seed, is no longer in the "
                                 f"archived repository -- only its outputs are.",
            "what_is_not_on_this_axis": "the pair of models the application actually "
                                        "loads is the mean of a 17-channel perceptron "
                                        "and a 273-dimension one that appends a frozen "
                                        "SAM ViT-H embedding. Only the 17-channel arm "
                                        "was run under this protocol, so only it is "
                                        "drawn.",
        },
    },
    the_plate_in_one_line=(
        "a learned classifier earns its place on the transmission frames and does not "
        "earn it on the scanning-electron frames; the scanning arm carries a logistic "
        "regression because it is the only candidate that never collapses, not because "
        "it won."),
    checks=[
        "every bar is read from the record named beside its panel; no value is typed "
        "into this script",
        f"the v3 record still selects {CHOSEN_SEM} and pooled CV still ranks it first",
        f"the single-image protocol still ranks a different arm first ({_best_loio}), "
        f"which is what panel (a) exists to show",
        f"the v2 record still selects something else ({V2['best']}), so the sentence "
        f"about the selection moving is still true",
        f"the unified bake-off still has {_b_best} nominally ahead by {_gap:.4f}, which "
        f"is still inside both run-to-run spreads, so 'a tie' still holds",
        f"the no-model floor still beats the model on F1 ({_f_floor:.4f} vs "
        f"{_f_lofo:.4f}), so panel (c)'s annotation is still true",
        f"in-sample and leave-one-frame-out F1 still agree to "
        f"{abs(_insample - _f_lofo):.4f}, so 'not a leakage artefact' still holds",
        "the transmission bake-off's best arm is still the perceptron the application "
        "carries",
        "the transmission logistic regression still ran on fewer channels than the "
        "ensembles, so the like-for-like caveat is still needed and is still drawn on "
        "the panel as a per-bar channel count",
        "every model class named in any of the three scanning-electron records has a "
        "short label, so a renamed key cannot silently drop a bar",
        f"{N_STRINGS} drawn strings measured at the renderer's own extents: no pair "
        f"overlapping by more than 1 pt in both directions, and none leaving the sheet",
    ],
    generated_from={
        "sem-crack-detector/models/crack_classifier_v3_metrics.json":
            "panel (a) bars, diamonds and title counts",
        "sem-crack-detector/archive/superseded_models/crack_classifier_v2_metrics.json":
            "caption only, nothing drawn",
        "sem-crack-detector/interior_active_learning/code/experiments/"
        "benchmark_results_unified.json": "panel (b) bars, dots and title counts",
        "docs/figures/sem_classifier_lofo.json": "panel (c) bars and whiskers",
        "TXM_Crack_Detection_Pipeline/research/benchmark_figures/benchmark_summary.json":
            "panel (d) tree-ensemble bars, protocol and title counts",
        "TXM_Crack_Detection_Pipeline/research/benchmark_figures/extended_summary.json":
            "panel (d) Otsu, logistic-regression, tree and perceptron bars",
    },
)
json.dump(CAPTION, open(os.path.join(OUT, NAME + ".caption.json"), "w"),
          indent=1, ensure_ascii=False)
print(f"wrote {os.path.join(OUT, NAME + '.png')}")
print(f"      {os.path.join(OUT, NAME + '.caption.json')}")
print(f"all {len(CAPTION['checks'])} checks passed")
