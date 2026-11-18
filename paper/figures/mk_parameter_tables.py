"""The two parameter tables on their own, as a readable A4 PDF.

WHY THIS EXISTS SEPARATELY FROM F6. The plate sets fifty constants in three narrow
columns per arm at 8 pt, which is the right density for a journal page beside thirteen
sparklines and the wrong one for reading. This renders the same fifty rows one per line,
at body size, and then prints the EVIDENCE behind each letter -- the measurement for
every M row and the stated reason for every F row -- which the plate has no room for at
all and which is the part a referee actually has to check.

IT READS THE PLATE'S OWN CAPTION FILE AND DERIVES NOTHING. Every row, value, letter and
reason here comes out of
`out/F6 - how the parameters were determined.caption.json`, which mk_parameters.py
writes in the same run that draws the plate. A second generator that recomputed the
provenance column would be a second opinion about it, and the two would disagree the
first time one was edited -- the exact failure this document was made to report. So the
only thing this file decides is layout. If the caption file is missing or stale, run
mk_parameters.py first; this aborts rather than drawing an old table.

    <sem-crack-detector>/.venv/bin/python -B mk_parameter_tables.py
"""
import json
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
PAPER = os.path.dirname(HERE)
if PAPER not in sys.path:
    sys.path.insert(0, PAPER)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages                 # noqa: E402

from make_paper import Doc, PAGE, ML, MR, MB, BODY, H1, H2, SMALL    # noqa: E402

OUT = os.path.join(HERE, "out")
CAPTION = os.path.join(OUT, "F6 - how the parameters were determined.caption.json")
NAME = "crack parameters - the two tables.pdf"

#: the printed table's three columns, in inches from the left margin
COL_VALUE = PAGE[0] - MR - 1.05          # right edge of the value column
COL_REF = PAGE[0] - MR - 0.12            # right edge of the ref. letter
ROWLEAD = 0.168


def load():
    if not os.path.exists(CAPTION):
        raise SystemExit(
            f"{CAPTION} is not there. This document is a rendering of the plate's own "
            f"record, not a second derivation of it -- run mk_parameters.py first.")
    rec = json.load(open(CAPTION))
    for key in ("table_rows", "ref_column_key", "counts_by_letter", "why_each_F_is_true",
                "not_drawn_but_fixed"):
        if key not in rec:
            raise SystemExit(
                f"the caption file has no `{key}`, so it predates the provenance audit. "
                f"Re-run mk_parameters.py and then this.")
    return rec


def rule(doc, weight=0.9, gap=0.045):
    """A plain horizontal rule, which is how a printed table is ruled."""
    doc.space(gap * 2)
    doc.y -= gap
    doc.page.add_artist(plt.Line2D(
        [ML / PAGE[0], (PAGE[0] - MR) / PAGE[0]], [doc.y / PAGE[1]] * 2,
        transform=doc.page.transFigure, color="black", lw=weight))
    doc.y -= gap


def row(doc, name, value, letter, *, bold=False):
    doc.space(ROWLEAD)
    w = "bold" if bold else "normal"
    doc.page.text(ML / PAGE[0], doc.y / PAGE[1], name, fontsize=BODY, va="top",
                  ha="left", transform=doc.page.transFigure, fontweight=w)
    doc.page.text(COL_VALUE / PAGE[0], doc.y / PAGE[1], value, fontsize=BODY, va="top",
                  ha="right", transform=doc.page.transFigure, fontweight=w)
    doc.page.text(COL_REF / PAGE[0], doc.y / PAGE[1], letter, fontsize=BODY, va="top",
                  ha="right", transform=doc.page.transFigure, fontweight=w)
    doc.y -= ROWLEAD


def head(doc, title):
    doc.text(title, H2, weight="bold", gap=0.16, wrap="h2")
    rule(doc)
    row(doc, "parameter", "value", "ref.", bold=True)
    rule(doc, weight=0.6)


def table(doc, rec, arm, title):
    head(doc, title)
    rows = [r for r in rec["table_rows"] if r["arm"] == arm]
    for r in rows:
        #: REPEAT THE HEADER WHEN THE TABLE BREAKS. The first build ran the TXM table
        #: onto a second page and left a reader there with three unlabelled columns of
        #: bare numbers and single letters -- the one page of this document where the
        #: ref. column, which is the whole point of it, had nothing naming it.
        if doc.y - ROWLEAD < MB:
            doc._new()
            head(doc, title + "  (continued)")
        nm = r["name"] + (f"  ({r['panel']})" if r.get("panel") else "")
        row(doc, nm, str(r["value"]), r["letter"])
    rule(doc)
    return len(rows)


def wrapped(doc, label, body, *, size=SMALL, indent=0.20):
    """A bold label and a wrapped paragraph hanging under it."""
    doc.space(ROWLEAD)
    doc.page.text(ML / PAGE[0], doc.y / PAGE[1], label, fontsize=size, va="top",
                  ha="left", transform=doc.page.transFigure, fontweight="bold")
    doc.y -= 0.155
    for line in textwrap.wrap(body, 104) or [""]:
        doc.space(0.145)
        doc.page.text((ML + indent) / PAGE[0], doc.y / PAGE[1], line, fontsize=size,
                      va="top", ha="left", transform=doc.page.transFigure)
        doc.y -= 0.145
    doc.y -= 0.04


def main():
    rec = load()
    counts = rec["counts_by_letter"]
    key = rec["ref_column_key"]
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, NAME)

    with PdfPages(path) as pdf:
        doc = Doc(pdf)
        doc.text("Every constant both detectors read", H1, weight="bold", wrap="h1")
        doc.text(
            "The fifty settings the two detectors apply, the value each one is at, and "
            "how each was settled. The ref. column is the finding: of the fifty, "
            f"{counts['swept']} are swept on this laboratory's own tiles or frames, "
            f"{counts['test']} were settled by a test with no value to choose, "
            f"{counts['measured']} were selected from a measurement recorded in the "
            f"software's own source but never drawn as a curve, and {counts['fixed']} "
            "are fixed by construction or set by hand with nothing measured about them "
            "anywhere. A constant applied to the data and not declared is an "
            "undeclared degree of freedom.", BODY, gap=0.10)
        doc.text(
            "Every row, value and letter below is read out of the figure's own caption "
            "file rather than derived again here, so this table cannot disagree with "
            "the plate. A bracketed letter after a parameter names the panel that "
            "sweeps it.", SMALL, gap=0.10, color="0.35")

        n_sem = table(doc, rec, "SEM", "SEM arm — the darkness detector")
        n_txm = table(doc, rec, "TXM", "TXM arm — the trained per-pixel ensemble")

        doc.text("  ".join(f"{k} {v}." for k, v in key.items()), SMALL, gap=0.12,
                 color="0.35", wrap="small")

        # ---- the evidence behind the two letters that assert something ---------------
        doc.text("M — measured in the source, not drawn", H2, weight="bold",
                 gap=0.30, wrap="h2")
        doc.text(
            "These carry a measurement written above the constant in its own source "
            "file. They have no panel on the plate because they act on the exported "
            "mask, after everything the panels sweep, and several are two values on "
            "one frame rather than a grid — a sparkline drawn through two points "
            "would dress a comparison as a sweep. The measurement is quoted in full "
            "instead.", BODY, gap=0.08)
        mnd = rec["not_drawn_but_fixed"]["measured_not_drawn"]["rows"]
        for name, d in mnd.items():
            wrapped(doc, f"{name} = {d['value']}",
                    f"{d['measurement']}.  [{d['source']}]")

        doc.text("F — fixed by construction, nothing measured", H2, weight="bold",
                 gap=0.26, wrap="h2")
        doc.text(
            "F is the only letter here that makes a claim about what does NOT exist: "
            "that no measurement of the constant is on record in either repository. "
            "That is the easiest claim in the figure to get wrong, so every row "
            "carrying it has to say why it is true, and the figure refuses to build if "
            "one does not.", BODY, gap=0.08)
        why = {k: v for k, v in rec["why_each_F_is_true"].items()
               if not k.startswith("_")}
        for name, reason in why.items():
            wrapped(doc, name, reason + ".")

        doc._foot()
        pdf.savefig(doc.page)
        plt.close(doc.page)

    #: the document must hold every row the plate holds, or it is a different table
    if n_sem + n_txm != counts["total"]:
        raise SystemExit(f"drew {n_sem + n_txm} rows against the plate's "
                         f"{counts['total']}")
    n_f = len([1 for r in rec["table_rows"] if r["letter"] == "F"])
    if len(why) != n_f:
        raise SystemExit(f"{n_f} rows are lettered F and {len(why)} reasons were "
                         f"printed; every F must state why")
    print(f"  CONTROL all {n_sem + n_txm} rows drawn ({n_sem} SEM, {n_txm} TXM), "
          f"and every one of the {n_f} F rows states its reason: PASS")
    print(f"wrote {path}  ({os.path.getsize(path) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
