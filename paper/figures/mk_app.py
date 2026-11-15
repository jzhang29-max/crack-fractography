#!/usr/bin/env python3
"""What the application does with a detection once it has one.

The detector is the middle of the tool, not the end of it. This plate is the three
things a user actually does in the application, captured from the running app rather
than mocked up: correct a mask by hand, read the measurement off a specimen, and
compare two collections of frames against each other.

THE SCREENSHOTS ARE REAL AND WERE TAKEN FROM THE RUNNING APPLICATION. The comparison in
panel (c) is a live run over 6 hydrogen-charged HIP frames against 6 ambient HIP frames
of the same specimen family, not a worked example: every number in it was computed by
the application at capture time. Recapture them with `tools/capture_app_panels.md`
rather than editing the image.

    <sem-crack-detector>/.venv/bin/python -B mk_app.py
"""
import json
import os
import textwrap
import sys
import warnings

warnings.filterwarnings("ignore")
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matplotlib                                    # noqa: E402
matplotlib.use("Agg")                                # noqa: E402
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.patches import Rectangle             # noqa: E402
from PIL import Image                                # noqa: E402

import journal_style as J                            # noqa: E402
import _paths                                        # noqa: E402

OUT = _paths.FIG_DIR
NAME = "F9 - the application"
SHOTS = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
         "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/appshots")

#: Each panel: the screenshot, the heading a reader needs, and the one line that says
#: what the user DID. Written so the plate carries itself with no caption.
#: (file, heading, note, crop box in the screenshot's own pixels). The crops drop the
#: frame list and chrome so each panel is the thing it is about; the full screenshots
#: are kept on disk unedited.
PANELS = [
    ("01_mark.jpg", "Correct the mask by hand",
     "The mask is drawn over the micrograph; brush and eraser edit it and the "
     "correction saves beside the frame. The original image is never written.",
     (196, 96, 800, 506)),
    ("02_results.jpg", "Measure a specimen",
     "Crack area with a confidence interval over that specimen's own fields, and the "
     "spread across every specimen. Exports as CSV or SVG.",
     (196, 26, 800, 506)),
    ("03_groups.jpg", "Compare two collections",
     "Two sets of frames compared quantity by quantity: the difference, the ratio, and "
     "the change in standard deviations of the per-frame spread.",
     (196, 252, 800, 506)),
]


def main():
    missing = [f for f, _h, _n, _b in PANELS
               if not os.path.exists(os.path.join(SHOTS, f))]
    if missing:
        raise SystemExit(
            "the application screenshots are not on disk: " + ", ".join(missing)
            + "\n  They are captured from the running app, not generated. See the "
              "module docstring.")

    W = J.PAGEW
    M = 0.04
    HEAD = 0.16          # the panel heading
    LINE = 0.145         # one wrapped line of the note
    GAP = 0.22
    COLGAP = 0.16

    def crop(i):
        f, _h, _n, box = PANELS[i]
        return Image.open(os.path.join(SHOTS, f)).crop(box)

    top = [crop(0), crop(1)]
    bot = crop(2)
    cw = (W - 2 * M - COLGAP) / 2.0
    th = max(cw * im.height / im.width for im in top)
    bw = W - 2 * M
    bh = bw * bot.height / bot.width
    SUB = SUB_B = 0.06
    Htot = M + HEAD + SUB + th + GAP + HEAD + SUB_B + bh + M

    fig = plt.figure(figsize=(W, Htot))

    def ax_at(xin, yin, win, hin):
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    def wrapped(note, w):
        # matplotlib's own wrap=True wraps to the FIGURE width, not the column, so the
        # two top notes ran straight through each other. Wrap by hand to the column.
        return textwrap.wrap(note, max(20, int(w * 15.5)))

    def block(x, y, w, im, letter, head, note, outside=False):
        fig.text(x / W, 1.0 - y / Htot, f"({letter})  {head}", fontsize=J.LABEL,
                 fontweight="bold", va="top", ha="left", color=J.INK)
        del note  # printed in the caption, not on the plate
        h = w * im.height / im.width
        ax = ax_at(x, y + HEAD + SUB, w, h)
        ax.imshow(im)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor(J.G_MID); sp.set_linewidth(0.6)
        return h

    for i, (im, letter) in enumerate(zip(top, "ab")):
        block(M + i * (cw + COLGAP), M, cw, im, letter, PANELS[i][1], PANELS[i][2])
    _sb = SUB
    SUB = SUB_B
    block(M, M + _sb + HEAD + th + GAP, bw, bot, "c", PANELS[2][1], PANELS[2][2],
          outside=True)

    J.save(fig, os.path.join(OUT, NAME + ".png"))
    json.dump({
        "figure": NAME + ".png",
        "what": "the three things the application does with a detection, captured from "
                "the running app",
        "panels": [{"file": f, "heading": h, "note": n, "crop": list(b)}
                   for f, h, n, b in PANELS],
        "capture": "real screenshots of the running application at localhost:8810, not "
                   "mock-ups; the comparison in (c) is a live run",
        "comparison_shown": {
            "A": "MAR_H_HIP, 6 frames (hydrogen charged, hot isostatically pressed)",
            "B": "MAR_AmbB_HIP, 6 frames (ambient, hot isostatically pressed)",
            "note": "the quantities, differences, ratios and change-in-SD columns are "
                    "the application's own output at capture time; this plate reports "
                    "no number of its own"},
    }, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)
    print(f"  wrote {NAME}.png  ({len(PANELS)} panels, {Htot:.2f} in tall)")


if __name__ == "__main__":
    main()
