#!/usr/bin/env python3
"""Render paper/sections/*.md into paper/draft.pdf.

WHY MATPLOTLIB. There is no LaTeX, no pandoc and no reportlab on this machine; matplotlib
is the only PDF writer available, and the repository already renders its slide deck this
way. The output is a readable draft, not typeset camera-ready copy.

EVERY NUMBER IS RESOLVED, NEVER TYPED. The sections contain {placeholders}; this script
fills them from the measurement JSON and FAILS if one cannot be resolved. A draft where a
number is typed by hand is a draft where a number goes stale silently, which has happened
in this project repeatedly. `[FIGURE name]` on its own line embeds that plate.

    <sem-crack-detector>/.venv/bin/python -B paper/make_paper.py
"""
import json
import os
import re
import sys
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.image as mpimg

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SECT = os.path.join(HERE, "sections")
PLATES = os.path.join(HERE, "figures", "out")
SCRATCH = os.path.join(REPO, "docs", "figures")   # the measurement files live here

PAGE = (8.27, 11.69)          # A4 portrait, inches
ML, MR, MT, MB = 0.95, 0.95, 0.85, 0.75
BODY, H1, H2, H3, SMALL = 9.3, 15.0, 11.6, 10.0, 8.2
FLOOR = 7.0
LEAD = {"body": 0.175, "h1": 0.34, "h2": 0.27, "h3": 0.22}
#: characters per line at each size. A single WRAP for every size overflowed the title off
#: the right margin: 96 characters is right for 9.3 pt body and far too many for 15 pt.
WRAP = {"body": 96, "h1": 54, "h2": 74, "h3": 86, "small": 108}


def _markup(s):
    """Markdown emphasis is not rendered by matplotlib, so strip the syntax rather than
    print it. **bold** and `code` were appearing with their asterisks and backticks."""
    import re as _re
    s = _re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = _re.sub(r"\*(.+?)\*", r"\1", s)
    # EMPHASIS THAT SPANS A SOURCE LINE BREAK leaves its markers behind, because this
    # renderer processes one source line at a time and the regexes above need both ends on
    # the same line. "**an area fraction ... is 1.30 times too high**" shipped with its
    # asterisks for one build. Strip any survivors rather than require the author to keep
    # emphasis on one line.
    s = s.replace("**", "")
    s = s.replace("`", "")
    return s


def _f(path, what):
    if not os.path.exists(path):
        raise SystemExit(f"missing {what}: {path}")
    return json.load(open(path))


PM = _f(os.path.join(REPO, "docs/figures/public_metrics.json"), "public metrics")["datasets"]
SP = _f(os.path.join(REPO, "docs/figures/sem_public_metrics.json"), "SEM metrics")["datasets"]
SB = _f(os.path.join(REPO, "docs/figures/sem_baselines.json"), "SEM baselines")["results"]
PB = _f(os.path.join(SCRATCH, "baselines_full.json"), "pavement baselines")["results"]
SW = _f(os.path.join(REPO, "docs/figures/sem_width_ceiling.json"), "SEM width ceiling")
# The ranking measured on WHOLE FIELDS, every arm scored by pixel F1 and by a width-blind
# skeleton F1, and carrying a decoy arm -- the detector's own mask dilated -- whose only
# job is to say whether the metric can be bought instead of earned.
SK = _f(os.path.join(REPO, "docs/figures/skelf1_ranking.json"), "skeleton-F1 ranking")["sets"]
DC = _f(os.path.join(REPO, "docs/figures/dilation_costs_measurements.json"),
        "what dilation costs the measurements")["sets"]
# Where the recall goes, stage by stage, with both gates opened to their limit so the
# ceiling below is the proposal mechanism's own and not a threshold choice.
RD = _f(os.path.join(REPO, "docs/figures/recall_decomposition_inconel.json"),
        "recall decomposition")
RG = _f(os.path.join(REPO, "docs/figures/ridge_grow_controls.json"),
        "ridge-growing controls")["sets"]
_RD_OPEN = RD["arms"]["no gates (mad_k=0.5, no floor)"]
_RD_MAD = RD["arms"]["MAD cut only (no darkness floor)"]
_RD_SHIP = RD["arms"]["shipped proposal (both gates)"]
_DECOY = "DECOY: detector DILATED"
_DET = "DETECTOR (shipped, 1 param)"


def _rank_real(set_key, metric):
    """Where the detector sits among the seven real arms, the decoy excluded: the decoy is
    not a competing method, it is a control on the metric."""
    r = sorted(((k, v[metric]) for k, v in SK[set_key].items() if k != _DECOY),
               key=lambda kv: -kv[1])
    return [k for k, _ in r].index(_DET) + 1


def _decoy_rank(set_key, metric):
    r = sorted(SK[set_key].items(), key=lambda kv: -kv[1][metric])
    return [k for k, _ in r].index(_DECOY) + 1
PA = _f(os.path.join(REPO, "docs/figures/pixel_accounting.json"), "pixel accounting")["sets"]
PA_W = PA["Inconel 718, whole fields"]["detector"]
PA_C = PA["Inconel 718, released crops"]["detector"]
PA_E = PA["EBC coating, whole fields"]["detector"]
PA_EC = PA["EBC coating, released crops"]["detector"]
PA_M = PA["MetalDAM voids (not cracks)"]["detector"]


def _pct(d, k):
    return _n(d[k], 2)


def _ratio(d):
    return _n(d["marked_pct"] / d["labelled_pct"], 2)
WC = _f(os.path.join(SCRATCH, "width_ceiling.json"), "width ceiling")
MF = _f(os.path.join(REPO, "docs/figures/metric_figures.json"), "corpus ceiling")

_ce = MF["ceiling"]
_corpus = [sum(_ce[str(w)]["iou"]) / len(_ce[str(w)]["iou"]) for w in MF["ceiling_widths"]]


def _n(x, d=4):
    return f"{x:.{d}f}"


# CrackForest's values are deliberately absent: it is road imagery and was removed from
# the draft. If a section reintroduces a {cf_...} placeholder the renderer fails on an
# unresolved name rather than quietly printing a dataset the paper no longer argues from.
SO = _f(os.path.join(REPO, "docs/figures/sem_originals_metrics.json"),
        "SEM originals")["datasets"]
# WHOLE FIELDS are the paper's primary numbers. The released crops are quoted only where
# the text says so, and the baseline comparison is crops-only because that is the one set
# all seven arms share.
IN, EBC = SO["Inconel718_crack"], SO["EBC_crack"]
IN_CROP = SP["Inconel718_crack"]
_rank_i = len(SB["Inconel718_crack"]) - sorted(
    SB["Inconel718_crack"].items(), key=lambda kv: kv[1]).index(
        ("YOUR DETECTOR", SB["Inconel718_crack"]["YOUR DETECTOR"]))
_dc_rank = sorted(PB["DeepCrack"].items(), key=lambda kv: -kv[1])
_in_rank = sorted(SB["Inconel718_crack"].items(), key=lambda kv: -kv[1])
_ORD = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
        6: "sixth", 7: "seventh", 8: "eighth"}

VALUES = {
    # --- SEM alloy, the paper's primary set ---
    "in_n": str(IN["n"]),
    "in_prev": _n(100 * IN["prevalence"], 2),
    "in_f1": _n(IN["loo"]["f1"]),
    "in_recall_perimage": _n(IN["loo"]["recall"]),
    "in_iou": _n(IN["loo"]["iou"]),
    "in_me_f1": _n(IN["controls"]["mark_everything"]["f1"]),
    "in_lift_f1": _n(IN["loo"]["f1"] / IN["controls"]["mark_everything"]["f1"], 1),
    "in_lift_iou": _n(IN["loo"]["iou"] / IN["controls"]["mark_everything"]["iou"], 1),
    "in_rnd_f1": _n(IN["controls"]["equal_area_random"]["f1"]),
    "in_sauvola": _n(SB["Inconel718_crack"]["Sauvola local"]),
    "in_sato": _n(SB["Inconel718_crack"]["Sato ridge"]),
    # the spread across the three leading arms, which is the "indistinguishable" claim
    "in_spread": _n(_in_rank[0][1] - _in_rank[2][1]),
    "in_stroke": _n(SW["Inconel718_crack"]["label_stroke_px_median"], 1),
    "wc_in_iou": _n(SW["Inconel718_crack"]["ceiling_iou"]),
    "in_crop_f1": _n(IN_CROP["loo"]["f1"]),
    "in_crop_prev": _n(100 * IN_CROP["prevalence"], 2),
    "in_crop_src": "18",
    "in_crop_gain": _n(IN_CROP["loo"]["f1"] - IN["loo"]["f1"]),
    "in_rank": _ORD[_rank_i],
    # the same comparison on the whole fields the rest of the paper reports
    "in_rank_fields": _ORD[_rank_real("whole_fields", "pixel_f1")],
    "in_rank_skel": _ORD[_rank_real("whole_fields", "skel_f1_tau5")],
    "in_best_fields": _n(max(v["pixel_f1"] for k, v in SK["whole_fields"].items()
                             if k != _DECOY)),
    "in_f1_fields_cmp": _n(SK["whole_fields"][_DET]["pixel_f1"]),
    # the decoy: the detector's own mask, dilated, nothing else
    "dec_rank_crop": _ORD[_decoy_rank("crops", "pixel_f1")],
    # NOTE: the 3.5 paragraph argues from the crops throughout, so its skeleton rank
    # must come from the crops too -- a whole-field rank quoted beside crop values
    # would be two different sets in one sentence.
    "dec_rank_skel": _ORD[_decoy_rank("crops", "skel_f1_tau5")],
    "dec_f1_crop": _n(SK["crops"][_DECOY]["pixel_f1"]),
    "dec_f1_fields": _n(SK["whole_fields"][_DECOY]["pixel_f1"]),
    "dec_skel_crop": _n(SK["crops"][_DECOY]["skel_f1_tau5"]),
    "det_skel_crop": _n(SK["crops"][_DET]["skel_f1_tau5"]),
    "dec_gain_crop": _n(SK["crops"][_DECOY]["pixel_f1"]
                        - SK["crops"][_DET]["pixel_f1"]),
    "dec_area_crop": _n(DC["crops"]["detector DILATED (ranks 1st)"]
                        ["area_fraction_ratio"], 2),
    "dec_area_fields": _n(DC["whole_fields"]["detector DILATED (ranks 1st)"]
                          ["area_fraction_ratio"], 2),
    "dec_width_fields": _n(DC["whole_fields"]["detector DILATED (ranks 1st)"]
                           ["width_ratio"], 2),
    "ship_width_fields": _n(DC["whole_fields"]["shipped detector"]["width_ratio"], 2),
    # --- where the recall goes ---
    "rd_open_recall": _n(_RD_OPEN["recall"], 3),
    "rd_open_marked": _n(_RD_OPEN["marked_pct"], 1),
    "rd_open_prec": _n(_RD_OPEN["precision"], 4),
    "rd_never": _n(100 * (1 - _RD_OPEN["recall"]), 1),
    "rd_ship_prec": _n(_RD_SHIP["precision"], 4),
    "rd_floor_cost": _n(_RD_SHIP["recall"] - _RD_MAD["recall"], 4),
    "rd_ship_recall": _n(RD["shipped_recall"], 4),
    # the ridge-growing arm against the same arm fed another field entirely
    "rg_real": _n(RG["whole_fields"]["B grown through REAL ridge"]["f1"]),
    "rg_other": _n(RG["whole_fields"]["D grown through ANOTHER FIELD ridge"]["f1"]),
    "wc_in_at": str(SW["Inconel718_crack"]["ceiling_at_width"]),
    "wc_corpus_at": str(MF["ceiling_widths"][_corpus.index(max(_corpus))]),
    # --- the pixel budget: the same result in the units the tool actually reports ---
    "in_lab_pct": _n(PA_W["labelled_pct"], 2),
    "in_mark_pct": _n(PA_W["marked_pct"], 2),
    "in_tp_pct": _n(PA_W["tp_pct"], 2),
    "in_fp_pct": _n(PA_W["fp_pct"], 2),
    "in_tn_plus": _n(100 * (1 - PA_W["labelled_pct"] / 100), 2),
    "in_ratio": _n(PA_W["marked_pct"] / PA_W["labelled_pct"], 2),
    "in_acc": _n(100 * PA_W["accuracy"], 2),
    "in_bacc": _n(100 * PA_W["balanced_accuracy"], 2),
    "in_mcc": _n(PA_W["mcc"]),
    "in_crop_lab_pct": _n(PA_C["labelled_pct"], 2),
    "in_crop_mark_pct": _n(PA_C["marked_pct"], 2),
    "in_crop_tp_pct": _n(PA_C["tp_pct"], 2),
    "in_crop_fp_pct": _n(PA_C["fp_pct"], 2),
    "in_crop_ratio": _n(PA_C["marked_pct"] / PA_C["labelled_pct"], 2),
    "in_crop_acc": _n(100 * PA_C["accuracy"], 2),
    "in_crop_bacc": _n(100 * PA_C["balanced_accuracy"], 2),
    "in_crop_mcc": _n(PA_C["mcc"]),
    # --- appendix A: every set measured ---
    "ebc_lab_pct": _pct(PA_E, "labelled_pct"), "ebc_mark_pct": _pct(PA_E, "marked_pct"),
    "ebc_tp_pct": _pct(PA_E, "tp_pct"), "ebc_fp_pct": _pct(PA_E, "fp_pct"),
    "ebc_ratio": _ratio(PA_E), "ebc_bacc": _n(100 * PA_E["balanced_accuracy"], 2),
    "ebc_mcc": _n(PA_E["mcc"]),
    "ebcc_lab_pct": _pct(PA_EC, "labelled_pct"), "ebcc_mark_pct": _pct(PA_EC, "marked_pct"),
    "ebcc_tp_pct": _pct(PA_EC, "tp_pct"), "ebcc_fp_pct": _pct(PA_EC, "fp_pct"),
    "ebcc_ratio": _ratio(PA_EC), "ebcc_bacc": _n(100 * PA_EC["balanced_accuracy"], 2),
    "ebcc_mcc": _n(PA_EC["mcc"]),
    "md_n": str(PA["MetalDAM voids (not cracks)"]["n"]),
    "md_lab_pct": _pct(PA_M, "labelled_pct"), "md_mark_pct": _pct(PA_M, "marked_pct"),
    "md_tp_pct": _pct(PA_M, "tp_pct"), "md_fp_pct": _pct(PA_M, "fp_pct"),
    "md_ratio": _ratio(PA_M), "md_bacc": _n(100 * PA_M["balanced_accuracy"], 2),
    "md_mcc": _n(PA_M["mcc"]),
    # --- SEM coating, the failure case ---
    "ebc_stroke": _n(SW["EBC_crack"]["label_stroke_px_median"], 1),
    "wc_ebc_iou": _n(SW["EBC_crack"]["ceiling_iou"]),
    "ebc_n": str(EBC["n"]),
    "ebc_prev": _n(100 * EBC["prevalence"], 2),
    "ebc_p": _n(EBC["loo"]["precision"]),
    "ebc_r": _n(EBC["loo"]["recall"]),
    # --- pavement, the cross-modality check ---
    "wc_corpus_iou": _n(max(_corpus)),
}


def resolve(text):
    missing = []

    def sub(m):
        k = m.group(1)
        if k not in VALUES:
            missing.append(k)
            return m.group(0)
        return VALUES[k]
    out = re.sub(r"\{([a-z0-9_]+)\}", sub, text)
    if missing:
        raise SystemExit(f"unresolved placeholders, refusing to render: {sorted(set(missing))}")
    return out


class Doc:
    def __init__(self, pdf):
        self.pdf = pdf
        self.page = None
        self.y = 0.0
        self.pageno = 0
        self._new()

    def _new(self):
        if self.page is not None:
            self._foot()
            self.pdf.savefig(self.page)
            plt.close(self.page)
        self.pageno += 1
        self.page = plt.figure(figsize=PAGE)
        self.y = PAGE[1] - MT

    def _foot(self):
        self.page.text(PAGE[0] / 2, MB / 2, str(self.pageno), ha="center",
                       fontsize=SMALL, color="0.45")

    def space(self, h):
        if self.y - h < MB:
            self._new()

    def text(self, s, size, weight="normal", lead=None, gap=0.0, color="black",
             wrap="body"):
        lead = lead or LEAD["body"]
        self.y -= gap
        for line in textwrap.wrap(_markup(s), WRAP[wrap]) or [""]:
            self.space(lead)
            self.page.text(ML / PAGE[0], self.y / PAGE[1], line, fontsize=size,
                           fontweight=weight, va="top", ha="left",
                           transform=self.page.transFigure, color=color)
            self.y -= lead

    def bullet(self, s, size):
        wrapped = textwrap.wrap(_markup(s), WRAP["body"] - 4) or [""]
        for i, line in enumerate(wrapped):
            self.space(LEAD["body"])
            self.page.text((ML + (0.0 if i == 0 else 0.17)) / PAGE[0], self.y / PAGE[1],
                           ("•  " if i == 0 else "") + line, fontsize=size,
                           va="top", ha="left", transform=self.page.transFigure)
            self.y -= LEAD["body"]

    def table(self, rows, size):
        """Pipe tables were printing as raw markdown. Rendered as aligned columns in a
        monospaced face, which is honest for a draft and needs no column model."""
        # TABLE CELLS NEED THE SAME MARKUP STRIP AS BODY TEXT. They did not get it, so
        # "**1.30x**" printed with its asterisks inside the table while the same emphasis
        # was stripped correctly in the paragraph above it.
        rows = [[_markup(c) for c in r] for r in rows]
        cols = max(len(r) for r in rows)
        rows = [r + [""] * (cols - len(r)) for r in rows]
        w = [max(len(r[c]) for r in rows) for c in range(cols)]
        lines = ["  ".join(r[c].ljust(w[c]) for c in range(cols)).rstrip() for r in rows]
        # SHRINK TO FIT, OR THE TABLE IS SILENTLY CUT OFF. A monospace line is about
        # 0.6*size wide per character; Appendix A's widest row ran past the right margin
        # and its last two columns simply vanished off the page with nothing to say so.
        avail_pt = (PAGE[0] - ML - MR) * 72.0
        widest = max(len(x) for x in lines)
        fit = avail_pt / (0.6 * max(widest, 1))
        if fit < size:
            size = max(fit, FLOOR)
        if widest * 0.6 * size > avail_pt + 0.5:
            raise SystemExit(
                f"table needs {widest} characters and will not fit at the {FLOOR} pt floor "
                f"-- drop or shorten a column rather than letting it run off the page")
        for i, (r, line) in enumerate(zip(rows, lines)):
            self.space(LEAD["body"])
            self.page.text(ML / PAGE[0], self.y / PAGE[1], line, fontsize=size,
                           fontweight="bold" if i == 0 else "normal", va="top", ha="left",
                           family="monospace", transform=self.page.transFigure)
            self.y -= LEAD["body"]
            if i == 0:
                self.space(0.05)
                self.page.text(ML / PAGE[0], self.y / PAGE[1],
                               "-" * len(line), fontsize=size, va="top", ha="left",
                               family="monospace", color="0.55",
                               transform=self.page.transFigure)
                self.y -= 0.09

    def figure(self, path, caption):
        img = mpimg.imread(path)
        w_in = PAGE[0] - ML - MR
        h_in = w_in * img.shape[0] / img.shape[1]
        if h_in > PAGE[1] - MT - MB - 1.0:
            h_in = PAGE[1] - MT - MB - 1.0
            w_in = h_in * img.shape[1] / img.shape[0]
        if self.y - h_in - 0.5 < MB:
            self._new()
        self.y -= 0.12
        ax = self.page.add_axes([ML / PAGE[0], (self.y - h_in) / PAGE[1],
                                 w_in / PAGE[0], h_in / PAGE[1]])
        ax.imshow(img); ax.axis("off")
        self.y -= h_in + 0.06
        self.text(caption, SMALL, color="0.25", wrap="small")
        self.y -= 0.08

    def close(self):
        self._foot()
        self.pdf.savefig(self.page)
        plt.close(self.page)


FIGNUM = {}


def plate_for(tag):
    for f in sorted(os.listdir(PLATES)):
        if f.endswith(".png") and f.lower().startswith(tag.split(" - ")[0].lower()):
            return os.path.join(PLATES, f)
    extra = os.path.join(REPO, "docs/figures/fig_pipeline.png")
    if "pipeline" in tag.lower() and os.path.exists(extra):
        return extra
    raise SystemExit(f"no plate on disk for [FIGURE {tag}] -- generate it first")


def main():
    files = sorted(f for f in os.listdir(SECT) if f.endswith(".md"))
    if not files:
        raise SystemExit("paper/sections is empty")
    out = os.path.join(HERE, "draft.pdf")
    with PdfPages(out) as pdf:
        doc = Doc(pdf)
        fign = 0
        # the pipeline plate leads, before any section
        pending_table = []
        for src in files:
            for raw in open(os.path.join(SECT, src), encoding="utf-8").read().split("\n"):
                line = resolve(raw.rstrip())
                m = re.match(r"^\[FIGURE (.+)\]$", line.strip())
                if m:
                    fign += 1
                    p = plate_for(m.group(1))
                    doc.figure(p, f"Figure {fign}.  {os.path.splitext(os.path.basename(p))[0]}")
                    continue
                if line.lstrip().startswith("|"):
                    pending_table.append([c.strip() for c in
                                          line.strip().strip("|").split("|")])
                    continue
                if pending_table:
                    doc.table([r for r in pending_table
                               if not all(set(c) <= set("-: ") for c in r)], SMALL)
                    pending_table = []
                    doc.y -= 0.06
                if not line.strip():
                    doc.y -= 0.07
                elif line.startswith("### "):
                    doc.text(line[4:], H3, "bold", LEAD["h3"], gap=0.14, wrap="h3")
                elif line.startswith("## "):
                    doc.text(line[3:], H2, "bold", LEAD["h2"], gap=0.20, wrap="h2")
                elif line.startswith("# "):
                    doc.text(line[2:], H1, "bold", LEAD["h1"], gap=0.10, wrap="h1")
                elif line.startswith("* "):
                    doc.bullet(line[2:], BODY)
                elif re.match(r"^\d+\. ", line):
                    doc.bullet(line.split(". ", 1)[1], BODY)
                else:
                    doc.text(line, BODY)
            if pending_table:
                doc.table([r for r in pending_table
                           if not all(set(c) <= set("-: ") for c in r)], SMALL)
                pending_table = []
            doc.y -= 0.10
        # the pipeline figure at the end of the method section is easier as an appendix
        doc.text("Appendix B.  The detector, end to end", H2, "bold", LEAD["h2"], gap=0.25, wrap="h2")
        doc.figure(os.path.join(REPO, "docs/figures/fig_pipeline.png"),
                   f"Figure {fign + 1}.  Every constant read from "
                   f"analysis/detector_overrides.py when the plate was drawn.")
        doc.close()
    print("wrote", out)
    print("resolved", len(VALUES), "values; sections:", len(files))


if __name__ == "__main__":
    main()
