"""Plate T2: what the TXM overlap score is actually measuring.

The TXM labels are a wide brush -- median 53.9 px against a crack whose dark core is a few
pixels. So an IoU scored against them rewards covering the STROKE, not finding the crack.
This plate shows that directly: as the operator paints wider, the deployed model's IoU goes
UP while the IoU a physically correct 3 px trace could reach goes DOWN. Both are measured in
one pass, with one IoU convention, over the labelled domain only.

Source: paper/figures/txm_iou_ceiling_v2.json, emitted by the TXM repository's own
code/audit/measure_iou_ceiling.py. The shipped column is `effective_mask(corrections="none",
tight=True)` -- the model's own output with the human's paint excluded, so the comparison is
not circular.
"""
import os, sys, json, math, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import journal_style as J

J.use()
HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "txm_iou_ceiling_v2.json")))
R = D["per_frame"]
OUT = os.path.join(HERE, "out")
NAME = "T2 - TXM ceiling"


def spearman(x, y):
    rx = {v: i for i, v in enumerate(sorted(range(len(x)), key=lambda k: x[k]))}
    ry = {v: i for i, v in enumerate(sorted(range(len(y)), key=lambda k: y[k]))}
    ax = [rx[i] for i in range(len(x))]; ay = [ry[i] for i in range(len(y))]
    mx, my = st.mean(ax), st.mean(ay)
    num = sum((a - mx) * (b - my) for a, b in zip(ax, ay))
    den = math.sqrt(sum((a - mx) ** 2 for a in ax) * sum((b - my) ** 2 for b in ay))
    return num / den


w = [r["label_width_px"] for r in R]
sh = [r["iou_shipped"] for r in R]
c3 = [r["iou_w3"] for r in R]
rho_sh, rho_c3 = spearman(sh, w), spearman(c3, w)

GROUPS = ["AM", "B2", "WR", "B3"]            # ordered by median label width
fig = plt.figure(figsize=(J.W2, 2.45))
gs = fig.add_gridspec(1, 2, width_ratios=[1.45, 1.0], wspace=0.30,
                      left=0.062, right=0.995, top=0.90, bottom=0.21)

# (a) per frame, against how wide the operator painted
ax = fig.add_subplot(gs[0, 0])
ax.plot(w, sh, linestyle="none", marker="o", markersize=4.6, markerfacecolor=J.ACCENT,
        markeredgecolor=J.INK, markeredgewidth=0.4)
ax.plot(w, c3, linestyle="none", marker="^", markersize=4.6, markerfacecolor=J.ACCENT2,
        markeredgecolor=J.INK, markeredgewidth=0.4)
ax.set_xscale("log")
ax.set_xlabel("median width of the operator's stroke (px)")
ax.set_ylabel("IoU against that stroke")
ax.set_ylim(0, 1.0); ax.set_xlim(8, 420)
# direct labels rather than a legend box: the two clouds are unambiguous
ax.text(0.035, 0.955, f"deployed TXM model   $\\rho$ = {rho_sh:+.2f}", transform=ax.transAxes,
        ha="left", va="top", fontsize=J.TICK, color=J.ACCENT)
ax.text(0.40, 0.215, f"a correct 3 px crack trace   $\\rho$ = {rho_c3:+.2f}",
        transform=ax.transAxes, ha="left", va="bottom", fontsize=J.TICK, color=J.ACCENT2)
J.panel_label(ax, "a")

# (b) the same two quantities as specimen-group medians
ax = fig.add_subplot(gs[0, 1])
x = np.arange(len(GROUPS)); bw = 0.38
m_sh = [D["per_group"][g]["shipped"] for g in GROUPS]
m_c3 = [D["per_group"][g]["ceiling_3px"] for g in GROUPS]
ax.bar(x - bw / 2, m_sh, bw, color=J.ACCENT, edgecolor=J.INK, linewidth=0.5)
ax.bar(x + bw / 2, m_c3, bw, color=J.ACCENT2, edgecolor=J.INK, linewidth=0.5)
ax.set_xticks(x)
ax.set_xticklabels([f"{g}\n{D['per_group'][g]['label_width_px']:.0f} px" for g in GROUPS])
ax.set_ylabel("median IoU"); ax.set_ylim(0, 1.0)
J.panel_label(ax, "b")

os.makedirs(OUT, exist_ok=True)
J.save(fig, os.path.join(OUT, NAME + ".png"), printed_width=J.COLUMN_CLASS.get(NAME, ("double", J.W2))[1])

CAPTION = dict(
    what=("The TXM overlap score rises with how wide the operator painted, while the score a "
          "physically correct crack trace could reach falls."),
    why=("The TXM reference is a broad stroke, median 53.9 px, over a crack whose dark core is "
         "a few pixels. An IoU scored against it therefore rewards covering the stroke. These "
         "two series, measured in one pass with one convention, move in opposite directions "
         "with stroke width, which is what that statement means quantitatively."),
    n_frames=D["n_frames"],
    iou_convention=D["iou_convention"],
    shipped_mask='effective_mask(corrections="none", tight=True) -- the human paint is '
                 'excluded, so the comparison is not circular',
    values=dict(
        median_label_width_px=round(st.median(w), 2),
        label_width_range_px=[round(min(w), 1), round(max(w), 1)],
        median_shipped_iou=round(st.median(sh), 4),
        median_3px_ceiling=round(st.median(c3), 4),
        ratio_of_medians=round(st.median(sh) / st.median(c3), 2),
        spearman_shipped_vs_width=round(rho_sh, 3),
        spearman_ceiling_vs_width=round(rho_c3, 3),
        frames_where_correct_trace_wins=sum(1 for r in R if r["iou_w3"] > r["iou_shipped"]),
        per_group={g: dict(n=D["per_group"][g]["n"],
                           label_width_px=round(D["per_group"][g]["label_width_px"], 1),
                           shipped=round(D["per_group"][g]["shipped"], 4),
                           ceiling_3px=round(D["per_group"][g]["ceiling_3px"], 4))
                   for g in GROUPS},
    ),
    caveats=[
        "Both headline figures are MEDIANS over frames, and the 13.56x is a ratio of two "
        "medians, not a paired per-frame ratio.",
        "Panel (a)'s x axis is the median stroke width of each frame's own labels, so frames "
        "are not independent of the quantity they are plotted against by construction -- the "
        "point is the OPPOSITE SIGN of the two trends, not either slope on its own.",
        "The 3 px trace is a construction, not a measurement: skeletonize(label) dilated by "
        "disk(1). It is a lower bound on what a correct trace scores, not a model.",
        "n = 61 here. The stage plate's corpus median is over 58 labelled frames. The two "
        "frame sets are not identical and the numbers must not be pooled.",
    ],
    source="paper/figures/txm_iou_ceiling_v2.json (generator: TXM repo "
           "code/audit/measure_iou_ceiling.py, run 2026-09-21)",
)
json.dump(CAPTION, open(os.path.join(OUT, NAME + ".caption.json"), "w"),
          indent=1, ensure_ascii=False)
print("caption written")
