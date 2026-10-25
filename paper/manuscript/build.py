"""Build the revised manuscript with the two added parts.

This renders `Revised_Manuscript` as supplied, plus the material it was missing:

  the restored comparison figures -- the operating-setting sweep and the width-sensitivity
  ceiling, both of which the supplied manuscript asserts in prose and does not show; and

  a new cross-modality section carrying the SEM detector to transmission X-ray microscopy,
  scored in the same area units.

It reuses `paper/make_paper.py` for page layout, text wrapping, tables and placeholder
resolution, so every number here comes from the same measurement files as the longer draft
and an unresolved name fails the build rather than rendering as a brace. Figures are
referenced as `[FIGURE key | caption]` so each one carries a real caption instead of a file
name -- a manuscript needs the caption to say which collection the panel is from, and the
longer draft's auto-generated captions cannot.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.dirname(HERE)
REPO = os.path.dirname(PAPER)
sys.path.insert(0, PAPER)
sys.dont_write_bytecode = True

import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_pdf import PdfPages

import make_paper as MP          # noqa: E402  -- Doc, resolve, VALUES, metrics, layout

OUT = os.path.join(HERE, "Revised_Manuscript_v2.pdf")
SECT = os.path.join(HERE, "sections")
FIGS = {
    "pipeline": os.path.join(PAPER, "figures/out/P6 - pipeline in pictures.png"),
    # the stage diagram: the supplied manuscript had it as Figure 2 and the text
    # still refers to it, so it has to be embedded or the reference dangles
    # The journal variant, not the documentation diagram. The latter carries a title,
    # paragraphs of prose, p-values and source identifiers; all four are things a
    # journal figure does not do, and the detail belongs to Methods. Same generator,
    # same constants: docs/figures/mk_pipeline.py writes both.
    "workflow": os.path.join(REPO, "docs/figures/fig_pipeline_journal.png"),
    "areabars": os.path.join(PAPER, "figures/out/P1 - public scores.png"),
    "sweep": os.path.join(PAPER, "figures/out/P2 - operating curve.png"),
    "ceiling": os.path.join(PAPER, "figures/out/P3 - width sensitivity.png"),
    "arms": os.path.join(PAPER, "figures/out/P4 - baselines.png"),
    "budget": os.path.join(PAPER, "figures/out/P5 - pixel budget.png"),
    "txm": os.path.join(PAPER, "figures/out/txm_transfer.png"),
}

# --- values this manuscript needs that the longer draft does not define ----------------
import json                                                            # noqa: E402
TX = MP._f(os.path.join(REPO, "docs/figures/txm_background_units.json"), "TXM")
_k6 = "SEM detector, mad_k=6"
_pool = TX["pooled"][_k6]


def _rec(d):
    return d["tp_pct"] / max(d["tp_pct"] + d["fn_pct"], 1e-12)


MP.VALUES.update({
    # the false-negative share of the frame, which the longer draft does not
    # expose because its own limitations section quotes it differently
    "in_fn_pct": MP._n(MP.PA_W["fn_pct"], 2),
    "tx_n": str(TX["n_frames"]),
    "tx_cov": MP._n(100 * TX["refereed_coverage_frac"], 1),
    "tx_crack_px": f"{TX['refereed_crack_px']:,}",
    "tx_notc_px": f"{TX['refereed_notcrack_px']:,}",
    "tx_ratio_pn": MP._n(TX["refereed_notcrack_px"] / TX["refereed_crack_px"], 1),
    "tx_prev": MP._n(_pool["tp_pct"] + _pool["fn_pct"], 3),
    "tx_empty": MP._n(_pool["empty_mask_accuracy_pct"], 3),
    "tx_acc": MP._n(_pool["accuracy_pct"], 3),
    "tx_margin": MP._n(_pool["margin_pp"], 2),
    "tx_area": MP._n(_pool["area_agreement"], 3),
    "tx_recall": MP._n(_rec(_pool), 3),
    "tx_otsu_acc": MP._n(TX["pooled"]["control: Otsu, no model"]["accuracy_pct"], 1),
    "tx_all_acc": MP._n(TX["pooled"]["control: mark everything"]["accuracy_pct"], 1),
})
for g in ("B3", "B2", "Wrought", "AM/HC"):
    d = TX["by_group"][g]["arms"][_k6]
    tag = g.replace("/", "").lower()
    MP.VALUES.update({
        f"tx_{tag}_n": str(TX["by_group"][g]["frames"]),
        f"tx_{tag}_acc": MP._n(d["accuracy_pct"], 1),
        f"tx_{tag}_empty": MP._n(d["empty_mask_accuracy_pct"], 1),
        f"tx_{tag}_margin": MP._n(d["margin_pp"], 1),
        f"tx_{tag}_recall": MP._n(_rec(d), 3),
        f"tx_{tag}_area": MP._n(d["area_agreement"], 2),
    })

FIG_RE = re.compile(r"^\[FIGURE ([a-z]+)\s*\|\s*(.+)\]$")


def main():
    files = sorted(f for f in os.listdir(SECT) if f.endswith(".md"))
    if not files:
        raise SystemExit(f"{SECT} is empty")
    with PdfPages(OUT) as pdf:
        doc = MP.Doc(pdf)
        fign = 0
        pending = []
        for src in files:
            whole = MP.resolve(open(os.path.join(SECT, src), encoding="utf-8").read())
            for raw in whole.split("\n"):
                line = raw.rstrip()
                m = FIG_RE.match(line.strip())
                if m:
                    fign += 1
                    key, cap = m.group(1), m.group(2)
                    if key not in FIGS:
                        raise SystemExit(f"unknown figure key {key!r}")
                    if not os.path.exists(FIGS[key]):
                        raise SystemExit(f"missing plate for {key!r}: {FIGS[key]}")
                    doc.figure(FIGS[key], f"Figure {fign}.  {cap}")
                    continue
                if line.lstrip().startswith("|"):
                    pending.append([c.strip() for c in line.strip().strip("|").split("|")])
                    continue
                if pending:
                    doc.table([r for r in pending
                               if not all(set(c) <= set("-: ") for c in r)], MP.SMALL)
                    pending = []
                    doc.y -= 0.06
                if not line.strip():
                    doc.y -= 0.07
                elif line.startswith("### "):
                    doc.text(line[4:], MP.H3, "bold", MP.LEAD["h3"], gap=0.14, wrap="h3")
                elif line.startswith("## "):
                    doc.text(line[3:], MP.H2, "bold", MP.LEAD["h2"], gap=0.20, wrap="h2")
                elif line.startswith("# "):
                    doc.text(line[2:], MP.H1, "bold", MP.LEAD["h1"], gap=0.0, wrap="h1")
                elif line.lstrip().startswith("* "):
                    doc.bullet(line.lstrip()[2:], MP.BODY)
                else:
                    doc.text(line, MP.BODY, lead=MP.LEAD["body"])
        if pending:
            doc.table([r for r in pending
                       if not all(set(c) <= set("-: ") for c in r)], MP.SMALL)
        doc.close()
    print("wrote", OUT)
    print(f"resolved {len(MP.VALUES)} values; sections: {len(files)}; figures: {fign}")


if __name__ == "__main__":
    main()
