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
import functools
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
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D
from matplotlib.textpath import TextToPath

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

# --- TABLE TYPOGRAPHY -----------------------------------------------------------------
# Booktabs rule weights, in points: a heavier rule above the header and below the last
# row, a lighter one under the header, and NO vertical rules and no row shading. The
# previous renderer drew its only rule as a run of hyphen characters.
RULE_HEAVY, RULE_LIGHT = 1.0, 0.5
TBL_MAX_LINES = 3             # a text cell may wrap onto at most this many lines
TBL_GUT = 1.55                # inter-column gutter, in multiples of the type size
TBL_LEAD = 1.30               # line pitch inside a cell, in multiples of the type size
TBL_ROWGAP = 0.34             # extra air between rows, in multiples of the type size
TBL_TEXT_PT = (PAGE[0] - ML - MR) * 72.0      # the measure, in points

_T2P = TextToPath()


@functools.lru_cache(maxsize=1 << 16)
def _tw(s, size, bold=False):
    """The width of `s` in POINTS, set in the body face at `size` pt.

    Measured through matplotlib's text-path machinery, which is the same unhinted run of
    glyph advances the PDF backend lays the string out with. The old table renderer
    multiplied a CHARACTER COUNT by 0.6*size instead, which is only true of a monospaced
    face -- and so the tables had to be set in one. Everything below (column widths,
    wrapping, decimal alignment, the fit test) is built on this function.
    """
    if not s:
        return 0.0
    fp = FontProperties(size=size, weight="bold" if bold else "normal")
    return _T2P.get_text_width_height_descent(s, fp, s.count("$") >= 2)[0]


#: A cell counts as a number -- and so right-aligns -- when it is digits with an optional
#: leading sign, an optional decimal part, an optional +/- tolerance and an optional short
#: trailing unit. "97.2%", "+0.024", "1.013x", "13 px" and "6" all qualify; "40 pixels",
#: "8-connected components" and "23 of 15" do not.
_NUM_CELL = re.compile(
    r"^[+\-−±]?\s*\d[\d,]*(?:\.\d+)?"
    r"(?:\s*[±+\-−]\s*\d[\d,]*(?:\.\d+)?)?"
    r"\s*(?:%|×|[A-Za-zµμ]{1,3})?$")
#: where the decimal point sits, for aligning a numeric column on it
_DEC_PT = re.compile(r"\.\d")


def _is_number(s):
    return bool(_NUM_CELL.match(s.strip()))


def _dec_split(s):
    """Split a cell into the part left of its decimal point and the part from the point
    on, so a column can be aligned on the point rather than merely flushed right."""
    m = _DEC_PT.search(s)
    return (s[:m.start()], s[m.start():]) if m else (s, "")


def _wrap_pt(s, width_pt, size, bold=False, first_pt=None):
    """Greedy word wrap to a width in POINTS, measured not counted.

    `first_pt` gives the first line a different measure, which is how the caption runs on
    after its bold "Table N." label.
    """
    words = []
    for wd in s.split():
        # A LONE SLASH OR DASH IS NOT A WORD. "Area reported / annotated" was breaking
        # as "Area reported" / "/ annotated", which no copy-editor would pass; keep the
        # connector at the end of the line it belongs to.
        if wd in ("/", "-", "–", "—", "|") and words:
            words[-1] += " " + wd
        else:
            words.append(wd)
    if not words:
        return [""]
    limit = first_pt if first_pt is not None else width_pt
    lines, cur = [], ""
    for wd in words:
        trial = f"{cur} {wd}" if cur else wd
        if cur and _tw(trial, size, bold) > limit + 0.01:
            lines.append(cur)
            cur, limit = wd, width_pt
        else:
            cur = trial
    lines.append(cur)
    return lines


def _plan_table(rows, size):
    """Lay the table out at `size` pt, or say which column made that impossible.

    Returns ``(plan, None)`` or ``(None, offending_column_index)``. The column model is:
    every cell measured at its rendered width; numeric columns held at their natural
    width because a number must never break; text columns capped at a common ceiling
    found by bisection, so the WIDEST columns are the ones that give ground, and then
    wrapped onto at most TBL_MAX_LINES lines. Only when that fails does the caller try a
    smaller size -- shrinking the type is the last resort, not the first.
    """
    cols = len(rows[0])
    gut = TBL_GUT * size
    budget = TBL_TEXT_PT - gut * (cols - 1)
    if budget <= 0:
        return None, 0

    align, head, tail, nat, minw = [], [], [], [], []
    for c in range(cols):
        body = [r[c].strip() for r in rows[1:] if r[c].strip()]
        numeric = bool(body) and all(_is_number(v) for v in body)
        align.append("r" if numeric else "l")
        hw = _tw(rows[0][c], size, True)
        if numeric:
            parts = [_dec_split(r[c].strip()) for r in rows[1:]]
            h = max([_tw(p[0], size) for p in parts] or [0.0])
            t = max([_tw(p[1], size) for p in parts] or [0.0])
            head.append(h)
            tail.append(t)
            nat.append(max(h + t, hw))
            # A NUMBER IS NEVER BROKEN, BUT ITS HEADING IS. Holding the whole column at
            # the width of "Crack % of reviewed area" drove the seven-column TXM table
            # to the 7 pt floor while its data cells were five characters wide.
            minw.append(max(h + t, max([_tw(wd, size, True)
                                        for wd in rows[0][c].split()] or [0.0])))
        else:
            head.append(0.0)
            tail.append(0.0)
            nat.append(max([_tw(r[c], size, i == 0) for i, r in enumerate(rows)] or [0.0]))
            longest = max([_tw(wd, size, i == 0)
                           for i, r in enumerate(rows) for wd in r[c].split()] or [0.0])
            minw.append(min(longest, nat[c]))

    if sum(nat) <= budget:
        w = nat[:]
    elif sum(minw) <= budget:
        lo, hi = 0.0, max(nat)
        for _ in range(60):                # bisect the common ceiling on column width
            mid = (lo + hi) / 2.0
            if sum(min(n, max(m, mid)) for n, m in zip(nat, minw)) <= budget:
                lo = mid
            else:
                hi = mid
        w = [min(n, max(m, lo)) for n, m in zip(nat, minw)]
    else:
        # even with every text column broken at its longest word the row is too wide
        return None, max(range(cols), key=lambda c: minw[c])

    wrapped = []
    for i, r in enumerate(rows):
        cells = []
        for c in range(cols):
            if align[c] == "r" and i:
                cells.append([r[c].strip()])
            else:
                cells.append(_wrap_pt(r[c], w[c], size, i == 0))
        n = max(len(x) for x in cells)
        if n > TBL_MAX_LINES:
            return None, max(range(cols), key=lambda c: len(cells[c]))
        wrapped.append(cells)

    # Spend what is left over on the gutters, so the table fills the measure and the
    # rules span the text block rather than stopping somewhere inside it.
    spare = budget - sum(w)
    gut_eff = gut + (spare / (cols - 1) if cols > 1 else 0.0)
    x0, xs = ML * 72.0, []
    for c in range(cols):
        xs.append(x0)
        x0 += w[c] + gut_eff
    if cols == 1:
        w = [TBL_TEXT_PT]
    return {"size": size, "cols": cols, "align": align, "w": w, "x": xs,
            "head": head, "tail": tail, "rows": wrapped}, None


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


SB = _f(os.path.join(REPO, "docs/figures/sem_baselines.json"), "SEM baselines")["results"]
PB = _f(os.path.join(SCRATCH, "baselines_full.json"), "pavement baselines")["results"]
SW = _f(os.path.join(REPO, "docs/figures/sem_width_ceiling.json"), "SEM width ceiling")
# The ranking measured on WHOLE FIELDS, every arm scored by pixel F1 and by a width-blind
# skeleton F1, and carrying a decoy arm -- the detector's own mask dilated -- whose only
# job is to say whether the metric can be bought instead of earned.
SK = _f(os.path.join(REPO, "docs/figures/skelf1_ranking.json"), "skeleton-F1 ranking")["sets"]
# Where the recall goes, stage by stage, with both gates opened to their limit so the
# ceiling below is the proposal mechanism's own and not a threshold choice.
# The mad_k sweep EXTENDED ABOVE the shipped value. The published sweep stopped at 5.0
# with F1 still rising, so the claimed optimum was the edge of the grid; this carries the
# two-sided curve and the paired test against the neighbouring rungs.
# Everything the paper reports is now computed over EVERY pixel in the frame. BC carries
# the sweep in those units with the empty-mask baseline beside each row; AB carries the
# classical-arm comparison re-ranked the same way.
BC = _f(os.path.join(REPO, "docs/figures/background_counting_table.json"),
        "background-counting table")
AB = _f(os.path.join(REPO, "docs/figures/arms_background_units.json"),
        "arms in background units")["sets"]
# The constant-width construction, re-scored over every pixel: Section 4 used to argue it
# in IoU, which discards the background the rest of the paper counts.
WBG = _f(os.path.join(REPO, "docs/figures/width_ceiling_background_units.json"),
         "width ceiling, background units")["sets"]
LSC = _f(os.path.join(REPO, "docs/figures/lab_scoring_positive_control.json"),
         "lab-corpus scoring control")
UCA = _f(os.path.join(REPO, "docs/figures/unproposed_crack_anatomy.json"),
         "unproposed crack anatomy")
# The region-classifier ablation re-scored over every pixel. Its own guard asserts the
# three arms still reproduce the overlap numbers Section 2 used to quote, so these are
# the same arms measured differently and not a different experiment.
DZ = _f(os.path.join(REPO, "docs/figures/sem_deadzone_background_units.json"),
        "classifier ablation, background units")
_CR = BC["sweeps"]["crops"]
# the operating point whose reported area fraction is closest to the annotator's, and the
# one the app currently ships, so the two can be quoted against each other
_CROP_BEST = max(_CR, key=lambda r: r["accuracy_pct"])
_ARM_W = AB["whole_fields"]["arms"]
_ARM_AREA = sorted(_ARM_W.items(), key=lambda kv: abs(kv[1]["area_agreement"] - 1.0))
_ARM_AREA_RANK = {1: "first", 2: "second", 3: "third", 4: "fourth",
                  5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth"}[
    [k for k, _ in _ARM_AREA].index("DETECTOR (shipped)") + 1]
# The nearest CLASSICAL arm, which is what the sentence claims. The union of darkness and
# Sato is our own two-parameter combination, not a classical detector, so naming it here
# would be comparing the method against a variant of itself.
_ARM_AREA_2ND = next(kv for kv in _ARM_AREA
                     if kv[0] not in ("DETECTOR (shipped)", "UNION darkness OR Sato"))
_ARM_UNION = _ARM_W["UNION darkness OR Sato"]
# the specimen that owns the pooled area ratio, named because the pooled and
# per-specimen aggregations disagree about the ablation and a reader needs to know
# which one specimen is responsible
_DZ_HOG = max(DZ["labelled_share_by_specimen"].items(), key=lambda kv: kv[1])




def _ARM_TABLE():
    """The classical comparison as a markdown table, in background-counting units only.

    Kept to five columns: the renderer shrinks a table to fit the page and raises rather
    than let one run off the edge, and the full eight-column form does not fit at the 7 pt
    floor. The dropped columns (free parameters, and the marked area split into right and
    wrong) are in Appendix A for every arm.
    """
    short = {"DETECTOR (shipped)": "**this detector**",
             "UNION darkness OR Sato": "darkness OR Sato",
             "global threshold (Otsu on flat)": "Otsu on flattened"}
    out = ["| arm | marked% | area rep./true | accuracy | specificity |",
           "|---|---|---|---|---|"]
    for nm, v in _ARM_AREA:
        if nm.startswith("global threshold"):
            continue          # marks 99.5% of the frame; it is in Appendix A, not here
        out.append(f"| {short.get(nm, nm)} | {v['marked_pct']:.2f}% | "
                   f"**{v['area_agreement']:.3f}x** | {v['accuracy_pct']:.2f}% | "
                   f"{v['specificity_pct']:.2f}% |")
    return "\n".join(out)


_ARM_TABLE = _ARM_TABLE()
RVD = _f(os.path.join(REPO, "docs/figures/ridge_vs_dilation_loo.json"),
         "ridge vs dilation")["sets"]
RFA = _f(os.path.join(REPO, "docs/figures/recall_fix_attempts.json"),
         "recall fix attempts")
TXP = _f(os.path.join(REPO, "docs/figures/texture_prototype.json"),
         "texture prototype")["sets"]
RG = _f(os.path.join(REPO, "docs/figures/ridge_grow_controls.json"),
        "ridge-growing controls")["sets"]
_DECOY = "DECOY: detector DILATED"
_DET = "DETECTOR (shipped, 1 param)"




def _decoy_rank(set_key, metric):
    r = sorted(SK[set_key].items(), key=lambda kv: -kv[1][metric])
    return [k for k, _ in r].index(_DECOY) + 1
PA = _f(os.path.join(REPO, "docs/figures/pixel_accounting.json"), "pixel accounting")["sets"]
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


def _p(x):
    """A p-value. Rounding an exact test's result to 0.0000 states a certainty no
    finite sample can deliver, so anything below the printable floor is given as an
    inequality instead."""
    return "< 0.0001" if x < 0.0001 else f"= {x:.4f}"


# CrackForest's values are deliberately absent: it is road imagery and was removed from
# the draft. If a section reintroduces a {cf_...} placeholder the renderer fails on an
# unresolved name rather than quietly printing a dataset the paper no longer argues from.

# THE PUBLIC WHOLE-FIELD COLLECTION IS ABSENT FOR THE SAME REASON, at the author's
# instruction: the paper reports this laboratory's own material and nothing else. What
# went with it was not a mention but a result -- it had been the primary evaluation set,
# and the abstract's headline, the principal-measurement section, the seven-arm
# comparator and the conclusions were all computed on it. The {in_...}, {ag_...},
# {mk_...}, {wf<n>_...}, {ov_...} and {arm_tbl} families are therefore deleted rather
# than left defined and unused, so a section that reintroduces one fails on an
# unresolved name instead of quietly reprinting a collection the paper no longer argues
# from. The records themselves are still on disk and nothing about them is retracted.
#
# ONE CONSEQUENCE IS RECORDED HERE BECAUSE IT IS NOT VISIBLE ANYWHERE ELSE. The MAD
# multiplier was the single constant of the forty-one that had been chosen by a sweep on
# labelled data, and that sweep was run on the removed collection; no record of this
# laboratory's own reproduces it. The value in use is unchanged and is now read from the
# record the reported results were computed at, but it is a constant this paper offers
# no evidence for, and Figure 3's tally says so rather than counting it as swept.
SO = _f(os.path.join(REPO, "docs/figures/sem_originals_metrics.json"),
        "SEM originals")["datasets"]
EBC = SO["EBC_crack"]
_ORD = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
        6: "sixth", 7: "seventh", 8: "eighth"}

VALUES = {
    # --- SEM alloy, the paper's primary set ---
    # the spread across the three leading arms, which is the "indistinguishable" claim
    # --- accuracy and specificity, with the empty-mask baseline that makes them legible ---
    "md_acc": _n(100 * PA_M["accuracy"], 2),
    "md_spec": _n(100 * PA_M["specificity"], 2),
    "md_empty_acc": _n(100 - PA_M["labelled_pct"], 2),
    "md_margin": _n(100 * PA_M["accuracy"] - (100 - PA_M["labelled_pct"]), 2),
    # --- the headline: the crack area fraction the tool reports against the human's ---
    # --- the crops at their best accuracy ---
    "cb_acc": _n(_CROP_BEST["accuracy_pct"], 2),
    "cb_k": f"{_CROP_BEST['mad_k']:g}",
    "cb_margin": _n(_CROP_BEST["accuracy_pct"] - _CROP_BEST["empty_mask_accuracy_pct"], 2),
    "cb_spec": _n(_CROP_BEST["specificity_pct"], 2),
    # --- where the detector places among the classical arms, in these units ---
    "arm_area_rank": _ARM_AREA_RANK,
    "arm_area_det": _n(_ARM_W["DETECTOR (shipped)"]["area_agreement"], 3),
    "arm_area_2nd": _n(_ARM_AREA_2ND[1]["area_agreement"], 3),
    "arm_area_2nd_name": _ARM_AREA_2ND[0],
    "arm_n_earned": str(sum(1 for v in _ARM_W.values() if v["beats_empty_mask"])),
    "arm_union_area": _n(_ARM_UNION["area_agreement"], 3),
    # --- Section 2: the classifier ablation in background-counting units ---
    "dz_n_tiles": str(DZ["n_tiles"]), "dz_n_spec": str(DZ["n_specimens"]),
    "dz_lab": _n(DZ["pooled"]["v147"]["labelled_pct"], 3),
    "dz_empty": _n(DZ["pooled"]["v147"]["empty_mask_accuracy_pct"], 3),
    "dz_a_acc": _n(DZ["pooled"]["v147"]["accuracy_pct"], 3),
    "dz_b_acc": _n(DZ["pooled"]["ablation"]["accuracy_pct"], 3),
    "dz_a_area": _n(DZ["pooled"]["v147"]["area_agreement"], 3),
    "dz_b_area": _n(DZ["pooled"]["ablation"]["area_agreement"], 3),
    "dz_c_area": _n(DZ["pooled"]["v1492"]["area_agreement"], 3),
    "dz_a_spec": _n(DZ["pooled"]["v147"]["specificity_pct"], 3),
    "dz_b_spec": _n(DZ["pooled"]["ablation"]["specificity_pct"], 3),
    "dz_acc_gain": _n(DZ["paired_vs_v147"]["ablation"]["accuracy (pp)"]["median_gain"], 4),
    "dz_acc_wins": str(DZ["paired_vs_v147"]["ablation"]["accuracy (pp)"]
                       ["specimens_better"]),
    "dz_acc_p": _p(DZ["paired_vs_v147"]["ablation"]["accuracy (pp)"]["wilcoxon_p"]),
    "dz_area_wins": str(DZ["paired_vs_v147"]["ablation"]["|area agreement - 1|"]
                        ["specimens_better"]),
    "dz_area_p": _p(DZ["paired_vs_v147"]["ablation"]["|area agreement - 1|"]
                    ["wilcoxon_p"]),
    "dz_spec_worse": str(DZ["paired_vs_v147"]["ablation"]["specificity (pp)"]
                         ["specimens_worse"]),
    "dz_spec_p": _p(DZ["paired_vs_v147"]["ablation"]["specificity (pp)"]["wilcoxon_p"]),
    "dz_hog": _DZ_HOG[0], "dz_hog_share": _n(100 * _DZ_HOG[1], 1),
    "dz_hog_a": _n(DZ["per_specimen"]["v147"][_DZ_HOG[0]]["area_agreement"], 3),
    "dz_hog_b": _n(DZ["per_specimen"]["ablation"][_DZ_HOG[0]]["area_agreement"], 3),
    # the sweep in background-counting units, at the three rungs the text names
    # the classical arms, ranked by how close their reported area fraction is
    # our own corpus: the refereed pixels are overwhelmingly crack, so a full mask nearly
    # wins there. Rule 4 needs both numbers to make that concrete.
    # Section 3.6 in percentage-of-image units: the labelled crack the proposal stage
    # never reaches, expressed as a share of the frame rather than as a recall
    "lab_pos_pct": _n(100 * LSC["refereed_crack_px"]
                      / (LSC["refereed_crack_px"] + LSC["refereed_notcrack_px"]), 1),
    "lab_all_f1": _n(2 * (LSC["refereed_crack_px"]
                          / (LSC["refereed_crack_px"] + LSC["refereed_notcrack_px"]))
                     / (1 + LSC["refereed_crack_px"]
                        / (LSC["refereed_crack_px"] + LSC["refereed_notcrack_px"])), 3),
    # --- Section 4: the ceiling a perfectly-localised mask reaches, in these units ---
    "wc_f_peak": _n(WBG["whole_fields"]["best_accuracy_pct"], 3),
    "wc_f_at": str(WBG["whole_fields"]["best_accuracy_width"]),
    "wc_f_empty": _n(WBG["whole_fields"]["empty_mask_accuracy_pct"], 3),
    "wc_f_head": _n(WBG["whole_fields"]["best_accuracy_pct"]
                    - WBG["whole_fields"]["empty_mask_accuracy_pct"], 3),
    "wc_c_peak": _n(WBG["crops"]["best_accuracy_pct"], 3),
    "wc_c_at": str(WBG["crops"]["best_accuracy_width"]),
    "wc_c_empty": _n(WBG["crops"]["empty_mask_accuracy_pct"], 3),
    "wc_c_head": _n(WBG["crops"]["best_accuracy_pct"]
                    - WBG["crops"]["empty_mask_accuracy_pct"], 3),
    "wc_c_captured": _n(100 * (_CROP_BEST["accuracy_pct"] - WBG["crops"]
                               ["empty_mask_accuracy_pct"])
                        / (WBG["crops"]["best_accuracy_pct"]
                           - WBG["crops"]["empty_mask_accuracy_pct"]), 1),
    "wc_f_areaw": str(WBG["whole_fields"]["area_match_width"]),
    "wc_c_areaw": str(WBG["crops"]["area_match_width"]),
    # Appendix A, in background-counting units for all five sets
    "ebc_acc": _n(100 * PA_E["accuracy"], 2), "ebc_spec": _n(100 * PA_E["specificity"], 2),
    "ebc_empty_acc": _n(100 - PA_E["labelled_pct"], 2),
    "ebcc_acc": _n(100 * PA_EC["accuracy"], 2),
    "ebcc_spec": _n(100 * PA_EC["specificity"], 2),
    "ebcc_empty_acc": _n(100 - PA_EC["labelled_pct"], 2),
    # the same comparison on the whole fields the rest of the paper reports
    # the decoy: the detector's own mask, dilated, nothing else
    # NOTE: the 3.5 paragraph argues from the crops throughout, so its skeleton rank
    # must come from the crops too -- a whole-field rank quoted beside crop values
    # would be two different sets in one sentence.
    "det_skel_crop": _n(SK["crops"][_DET]["skel_f1_tau5"]),
    # --- where the recall goes ---
    # the ridge-growing arm against the same arm fed another field entirely
    "rg_real": _n(RG["whole_fields"]["B grown through REAL ridge"]["f1"]),
    "rg_other": _n(RG["whole_fields"]["D grown through ANOTHER FIELD ridge"]["f1"]),
    # --- the two-sided mad_k curve, and whether its peak is resolvable ---
    # the whole-field form of the decoy gain, which the cost sentence needs
    "rgd_fields_ridge": _n(RVD["whole_fields"]["grown through RIDGE (2 params)"]["f1"]),
    "rgd_fields_dil": _n(RVD["whole_fields"]["just DILATED (2 params)"]["f1"]),
    "rgd_crop_ridge": _n(RVD["crops"]["grown through RIDGE (2 params)"]["f1"]),
    "rgd_crop_dil": _n(RVD["crops"]["just DILATED (2 params)"]["f1"]),
    "tx_margin": _n(TXP["whole_fields"]["+ TEXTURE attached to seed"]["sel_by_f1"]["f1"]
                    - TXP["whole_fields"]["decoy: WRONG-IMAGE texture"]["sel_by_f1"]["f1"]),
    "tx_ratio": _n(TXP["whole_fields"]["+ TEXTURE attached to seed"]["sel_by_f1"]
                   ["area_ratio"], 2),
    "wc_corpus_at": str(MF["ceiling_widths"][_corpus.index(max(_corpus))]),
    # --- the pixel budget: the same result in the units the tool actually reports ---
    # --- appendix A: every set measured ---
    "ebc_lab_pct": _pct(PA_E, "labelled_pct"), "ebc_mark_pct": _pct(PA_E, "marked_pct"),
    "ebc_tp_pct": _pct(PA_E, "tp_pct"), "ebc_fp_pct": _pct(PA_E, "fp_pct"),
    "ebc_ratio": _ratio(PA_E),
    "ebcc_lab_pct": _pct(PA_EC, "labelled_pct"), "ebcc_mark_pct": _pct(PA_EC, "marked_pct"),
    "ebcc_tp_pct": _pct(PA_EC, "tp_pct"), "ebcc_fp_pct": _pct(PA_EC, "fp_pct"),
    "ebcc_ratio": _ratio(PA_EC),
    "md_n": str(PA["MetalDAM voids (not cracks)"]["n"]),
    "md_lab_pct": _pct(PA_M, "labelled_pct"), "md_mark_pct": _pct(PA_M, "marked_pct"),
    "md_tp_pct": _pct(PA_M, "tp_pct"), "md_fp_pct": _pct(PA_M, "fp_pct"),
    "md_ratio": _ratio(PA_M),
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

    def _rule(self, lw):
        """A booktabs rule across the measure, drawn as a line and not as hyphens."""
        y = self.y / PAGE[1]
        ln = Line2D([ML / PAGE[0], (PAGE[0] - MR) / PAGE[0]], [y, y],
                    transform=self.page.transFigure, color="black", linewidth=lw,
                    solid_capstyle="butt", clip_on=False)
        self.page.add_artist(ln)

    def _cell(self, x_pt, y, s, size, bold=False, ha="left"):
        if not s:
            return
        self.page.text(x_pt / 72.0 / PAGE[0], y / PAGE[1], s, fontsize=size,
                       fontweight="bold" if bold else "normal", va="top", ha=ha,
                       transform=self.page.transFigure)

    def table(self, rows, size, caption=None, number=None, name=None):
        """A journal table: proportional type, booktabs rules, a real column model.

        What this replaces was a terminal dump -- fixed-width monospace, space-padded to
        equal columns, a row of hyphens for the header rule, and the whole table's type
        shrunk until the widest CHARACTER COUNT fitted. Here every cell is measured at
        its rendered width (`_tw`), columns are allocated from that, a long text column
        WRAPS rather than making the whole table smaller, numeric columns right-align on
        their decimal point, and the rules are lines.

        `number` and `caption` come from a `[TABLE key | caption]` directive and set the
        "Table N." head above the rules; a table with no directive renders with neither,
        which is what the sections still contain.
        """
        # TABLE CELLS NEED THE SAME MARKUP STRIP AS BODY TEXT. They did not get it, so
        # "**1.30x**" printed with its asterisks inside the table while the same emphasis
        # was stripped correctly in the paragraph above it.
        rows = [[_markup(c) for c in r] for r in rows]
        if not rows:
            return
        cols = max(len(r) for r in rows)
        rows = [r + [""] * (cols - len(r)) for r in rows]
        label = f"Table {number}." if number else None
        tag = (f"Table {number} ({caption[:48]})" if number
               else (name or "the table headed " + " | ".join(rows[0])))

        # LARGEST TYPE THAT FITS, NOT SMALLEST THAT WORKS. Step down from the requested
        # size; the first size whose plan lays out inside the measure wins. Wrapping is
        # tried at every step before the size moves, so a long text column costs two or
        # three lines rather than costing the whole table a point of type.
        plan, blame = None, 0
        s = size
        while s >= FLOOR - 1e-9:
            plan, blame = _plan_table(rows, round(s, 2))
            if plan:
                break
            s -= 0.1
        if plan is None:
            # KEEP THE EXISTING FAILURE MODE LOUD. The old renderer raised rather than
            # let a table run off the page; so does this one, and it names the column.
            raise SystemExit(
                f"{tag}: column {blame + 1} ({rows[0][blame]!r}) will not fit inside the "
                f"{TBL_TEXT_PT / 72:.2f} in text block even wrapped onto {TBL_MAX_LINES} "
                f"lines at the {FLOOR} pt floor -- shorten or drop that column rather "
                f"than letting the table run past the margin")
        size = plan["size"]
        lead = TBL_LEAD * size / 72.0
        rowgap = TBL_ROWGAP * size / 72.0
        caplead = TBL_LEAD * SMALL / 72.0
        body = plan["rows"][1:]
        hdr_h = max(len(c) for c in plan["rows"][0]) * lead

        cap_lines = []
        if caption:
            cap_lines = _wrap_pt(caption, TBL_TEXT_PT, SMALL,
                                 first_pt=TBL_TEXT_PT - _tw(label + "  ", SMALL, True))
        head_h = (0.10 + len(cap_lines) * caplead + 0.055 + 0.055 + hdr_h + 0.045 + 0.055)
        body_h = sum(max(len(c) for c in r) * lead + rowgap for r in body)
        total = head_h + body_h + 0.050 + 0.10
        page_h = PAGE[1] - MT - MB

        # DO NOT ORPHAN THE HEADER. If the whole block does not fit in what is left of
        # this page, start it on the next one; a table genuinely taller than one page
        # cannot do that, so it only insists on carrying its first row past the header
        # and repeats the header after the break.
        first_h = (max(len(c) for c in body[0]) * lead + rowgap) if body else 0.0
        need = total if total <= page_h else head_h + first_h + 0.050 + 0.10
        if self.y - need < MB:
            self._new()

        def start_block(first):
            self.y -= 0.10
            if first and cap_lines:
                x = ML * 72.0 + _tw(label + "  ", SMALL, True)
                self._cell(ML * 72.0, self.y, label, SMALL, bold=True)
                self._cell(x, self.y, cap_lines[0], SMALL)
                self.y -= caplead
                for ln in cap_lines[1:]:
                    self._cell(ML * 72.0, self.y, ln, SMALL)
                    self.y -= caplead
            elif first and label:
                self._cell(ML * 72.0, self.y, label, SMALL, bold=True)
                self.y -= caplead
            self.y -= 0.055
            self._rule(RULE_HEAVY)
            self.y -= 0.055
            self._row(plan, plan["rows"][0], size, lead, bold=True)
            self.y -= 0.045
            self._rule(RULE_LIGHT)
            self.y -= 0.055

        start_block(True)
        for r in body:
            h = max(len(c) for c in r) * lead
            if self.y - h - 0.050 < MB:
                self.y -= 0.050
                self._rule(RULE_HEAVY)
                self._new()
                start_block(False)
            self._row(plan, r, size, lead)
            self.y -= rowgap
        self.y -= 0.050
        self._rule(RULE_HEAVY)
        self.y -= 0.10
        return {"size": size, "widths_pt": plan["w"], "align": plan["align"]}

    def _row(self, plan, cells, size, lead, bold=False):
        """One table row. Numeric columns are set on their decimal point, every other
        column flush left, and a wrapped cell keeps the row's rules aligned because the
        row advances by its tallest cell."""
        for c in range(plan["cols"]):
            y = self.y
            for ln in cells[c]:
                if plan["align"][c] == "r":
                    right = plan["x"][c] + plan["w"][c]
                    if bold:
                        self._cell(right, y, ln, size, bold=True, ha="right")
                    else:
                        h, _t = _dec_split(ln)
                        anchor = right - plan["tail"][c]
                        self._cell(anchor - _tw(h, size), y, ln, size)
                else:
                    self._cell(plan["x"][c], y, ln, size, bold=bold)
                y -= lead
        self.y -= max(len(c) for c in cells) * lead

    #: HEAD_SIZE and HEAD_TITLE are the figure-pack's own heading sizes, repeated here
    #: so the two documents present a plate the same way. The pack draws "Figure N" at
    #: 15 pt bold over a 11.5 pt title in #333333; a reader who has both in front of
    #: them should not have to work out that they are looking at the same six plates.
    HEAD_SIZE, HEAD_TITLE = 15.0, 11.6

    def figure(self, path, caption, number=None, title=None):
        """Place a plate, optionally under the figure pack's own heading.

        WITHOUT `number` and `title` this is what it always was: the plate, then a
        small grey caption under it, which is what the explainer wants because its
        plates sit inside a running explanation and are introduced by the prose
        above them.

        WITH them it matches the pack: a bold "Figure N" and a short title ABOVE the
        artwork, then the plate, then the detailed caption. The author asked for the
        manuscript to present its figures the way the pack does, and the difference
        was not the artwork -- the same six files are in both -- but that the pack
        gives each plate a heading and a one-line title while the manuscript buried
        the title as the opening clause of a dense caption below the image. The
        heading carries the number, so the caption no longer repeats it.
        """
        img = mpimg.imread(path)
        w_in = PAGE[0] - ML - MR
        h_in = w_in * img.shape[0] / img.shape[1]
        head_in = 0.52 if number is not None else 0.0
        if h_in > PAGE[1] - MT - MB - 1.0 - head_in:
            h_in = PAGE[1] - MT - MB - 1.0 - head_in
            w_in = h_in * img.shape[1] / img.shape[0]
        #: the heading must not be orphaned from its plate, so the break test counts it
        if self.y - h_in - head_in - 0.5 < MB:
            self._new()
        self.y -= 0.12
        if number is not None:
            #: EACH HEADING LINE LEADS ITSELF. `text` advances by the BODY lead unless
            #: told otherwise, and the body lead is 0.175 in against a 15 pt line that
            #: stands 0.21 in tall, so the title printed through the number it was
            #: supposed to sit under. A line's leading has to come from its own size.
            self.text("Figure %d" % number, self.HEAD_SIZE, weight="bold",
                      lead=self.HEAD_SIZE / 72.0 * 1.30)
            if title:
                self.text(title, self.HEAD_TITLE, color="#333333",
                          lead=self.HEAD_TITLE / 72.0 * 1.30)
            self.y -= 0.04
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
            # RESOLVE THE WHOLE FILE, THEN SPLIT. Resolving line by line meant a value
            # holding several lines -- the classical-arm table is generated as one --
            # expanded into a single 422-character line, which the table renderer then
            # refused as too wide to fit. Substituting first lets a placeholder carry
            # structure.
            whole = resolve(open(os.path.join(SECT, src), encoding="utf-8").read())
            for raw in whole.split("\n"):
                line = raw.rstrip()
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
        # The caption used to say every constant was read from the source file. Five are;
        # mad_k falls back to a literal in the generator when the name is absent, and the
        # stage text carries typed values. Claiming provenance the plate does not have is
        # the defect this paper spends Section 6 on.
        doc.figure(os.path.join(REPO, "docs/figures/fig_pipeline.png"),
                   f"Figure {fign + 1}.  The shipped pipeline. Five constants are read from "
                   f"analysis/detector_overrides.py when the plate is drawn; mad_k and the "
                   f"two size floors are typed into the generator and are not yet under "
                   f"that check. Pass 2 and the hand-correction layer are stages of the "
                   f"application and are not in the scored path.")
        doc.close()
    print("wrote", out)
    print("resolved", len(VALUES), "values; sections:", len(files))


if __name__ == "__main__":
    main()
