#!/usr/bin/env python3
"""Build the paper's figure PDFs from ONE explicit, ordered list.

This exists because the figure set and the paper's figure set had drifted apart: the
build carried sixteen plates while the paper wants the eight below, in the order the
argument runs. The list here IS the paper's figure programme -- adding a plate to
`out/` does not put it in the paper, and a plate named here that is missing from `out/`
is an error rather than a silently shorter PDF.

Two PDFs, same figures, same order:
    crack figures.pdf            one plate per page, nothing else
    crack figures explained.pdf  each plate with bullets on what it establishes

    <sem-crack-detector>/.venv/bin/python -B mk_paper_pdf.py
"""
import os
import sys
import textwrap

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matplotlib                                    # noqa: E402
matplotlib.use("Agg")                                # noqa: E402
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from PIL import Image                                # noqa: E402

import _paths                                        # noqa: E402

OUT = _paths.FIG_DIR
PLAIN = os.path.join(OUT, "crack figures.pdf")
EXPLAINED = os.path.join(OUT, "crack figures explained.pdf")

#: THE PAPER'S FIGURE PROGRAMME: (plate file in out/, heading, bullets).
#: The order is the order of the argument -- what the method is, how the two
#: microscopies differ, how the constants were fixed, how the detectors compare, what
#: the errors look like, what the scores are, what comes out, and the application.
def _sweep_facts():
    """The three new sweeps' numbers, READ from the record rather than typed.

    They were typed once. The region classifier was then switched on, every one of
    them moved, and four documents went on asserting the old values with nothing to
    catch it. A bullet that quotes a measurement should read the measurement.
    """
    import json as _json
    rec = os.path.join(os.path.dirname(os.path.dirname(OUT)), "docs", "figures",
                       "parameters_tiles.json")
    if not os.path.exists(rec):
        rec = "/Users/jiamingzhang/Desktop/APP/crack-fractography/docs/figures/parameters_tiles.json"
    d = _json.load(open(rec))
    best = lambda k: max(d[k], key=lambda v: d[k][v]["iou"])        # noqa: E731
    return dict(
        close_ship=d["close"]["3"]["iou"], close_best=best("close"),
        close_best_iou=d["close"][best("close")]["iou"],
        den_ship=d["denoise"]["1.0"]["iou"], den_best=best("denoise"),
        den_best_iou=d["denoise"][best("denoise")]["iou"],
        union=d["union_on_these_tiles"]["iou"], single_best=best("single_radius"),
        single_best_iou=d["single_radius"][best("single_radius")]["iou"],
        clf=bool(d.get("use_region_classifier")))


def _deadzone_facts():
    """The classifier's own effect at the shipped candidate stage, read from the record.

    The F1 bullet used to carry arm A against arm B as literals. Those describe the
    single-radius candidate stage the application retired, and they were being read as
    though they described the shipped detector. The one-variable comparison at the stage
    the app actually runs is v1492_floor (classifier off) against shipped (on), and it
    is read here so the bullet cannot outlive it.
    """
    import json as _json
    d = _json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "sem_deadzone.json")))
    off = d["pooled_25_no_flood"]["v1492_floor"]
    on = d["pooled_25_no_flood"]["shipped"]
    st = d["paired_steps"]["classifier_over_floor"]
    return dict(off=off, on=on, st=st, on26=d["pooled_26"]["shipped"],
                off26=d["pooled_26"]["v1492_floor"], is_on=bool(d["classifier_is_on"]))


def _score_facts():
    """The F8 bullets' numbers, read from the plate's own caption file.

    They were literals: SEM b2 precision 0.947 with its whisker at 0.430, and an F1
    range of 0.04 to 0.84. All five moved when the region classifier was switched on,
    and the bullets went on asserting them. The caption file is written by mk_scores.py
    at the moment the plate is drawn, so reading it here is reading the bars.
    """
    import json as _json
    d = _json.load(open(os.path.join(OUT, "F8 - scores by sample.caption.json")))
    by = {(x["sample"], a): v for x in d["samples"] for a, v in x["arms"].items()
          if v is not None}
    #: THE RANGE IS OVER THE BARS THE PLATE DRAWS. The caption carries every group,
    #: drawn or not, so reading the minimum off all of them would quote a bar that is
    #: not on the sheet -- which is what this bullet did the moment the plate started
    #: withholding its worst groups.
    f1 = {k: v["f1"] for k, v in by.items() if v.get("f1") is not None}
    lo, hi = min(f1, key=f1.get), max(f1, key=f1.get)
    return dict(
        b2=by[("b2", "SEM")], f1_lo=f1[lo], f1_hi=f1[hi],
        f1_lo_name=f"{lo[1]} {lo[0]}", f1_hi_name=f"{hi[1]} {hi[0]}",
        txm_b2=by.get(("b2", "TXM")),
        in_sample=d.get("the_sem_bars_are_in_sample", ""))


SW = _sweep_facts()
DZ = _deadzone_facts()
SC = _score_facts()

FIGURES = [
 ("F1 - flow chart.png",
  "Two detectors, end to end",
  ["Two separate chains, because the two arms do not share a detector. SEM is a "
   "darkness rule that proposes regions and a trained 8-feature logistic model that "
   "decides which of them survive — nine fitted numbers, and they do reach the mask. "
   "The model is enabled by decision, not by measurement, and it is a trade: on the 25 "
   "hand-labelled tiles that exclude the off-specimen flood tile it raises precision "
   f"{DZ['off']['precision']:.3f} to {DZ['on']['precision']:.3f} while recall falls "
   f"{DZ['off']['recall']:.3f} to {DZ['on']['recall']:.3f}, IoU "
   f"{DZ['off']['iou']:.3f} to {DZ['on']['iou']:.3f} and F1 {DZ['off']['f1']:.3f} to "
   f"{DZ['on']['f1']:.3f}; the paired median IoU change over "
   f"{DZ['st']['n_specimens']} specimens is {DZ['st']['median_delta_iou']:+.3f}, worse "
   f"on {DZ['st']['n_worse']} and better on {DZ['st']['n_better']}. Every tile score "
   "here is in-sample — the model was fitted on these specimens' own regions — and "
   "docs/figures/sem_classifier_lofo.json holds the leave-one-frame-out answer. "
   "TXM is a trained per-pixel model — 17 image "
   "channels plus a frozen SAM embedding, the mean of two fitted members cut at 0.60.",
   "The operation is written on every arrow, and each cleaning step carries a "
   "before/after inset magnified 4x to 19x, so the reader can see what 'cleaned' "
   "actually did. No pixel is dilated. The inset sits on the largest piece that step "
   "removes which is FREE-STANDING and which the operator did not paint as crack — "
   "dropping a free-standing speck is what the step is for. Taking bites out of a "
   "region it otherwise keeps is its side effect, and the figure's record carries "
   "that split per step, in pixels.",
   "The TXM arm has NO background-subtraction step: the model reads the frame itself "
   "and its smoothed channels carry the local background.",
   "Held out, the TXM model reaches IoU 0.811 +/- 0.023 over 71 labelled frames. On the "
   "field drawn it scores 0.796, against 0.227 for the SEM darkness rule on the same "
   "pixels."]),
 ("F2 - how each modality sees a crack.png",
  "Why the two microscopies measure different quantities",
  ["One dogbone pulled to failure in the micro-tensile stage, one 35 um region taken "
   "from the middle of its gauge, and how each microscope works on that region.",
   "The electron beam lands on the polished face and the signal escapes back out of "
   "it, so what is recorded is the crack where it cuts the surface. The X-ray beam "
   "crosses all 22 um to a detector behind the foil, so what is recorded is the crack "
   "through the whole depth. Four elements per arm \u2014 source, beam, foil, detector "
   "\u2014 which is what published figures of this kind draw; see "
   "docs/FIGURE_CONVENTIONS_FROM_PUBLISHED_WORK.md.",
   "Neither arm is wrong: they measure two different quantities, so their numbers are "
   "not supposed to agree, and nothing in this work pools them.",
   "Both panels are real fields at a matched 35 um field of view with their own scale "
   "bars. The specimen and the two geometries are schematic and not to scale; the "
   "foil thickness is the only real dimension on either."]),
 ("F6 - how the parameters were determined.png",
  "Every constant, and how each one was fixed",
  ["TWELVE choice graphs, one per constant that has evidence, over a printed table "
   "carrying all FIFTY constants both detectors read. A constant with a graph names "
   "its letter in its table row.",
   "THREE OF THE TWELVE ARE NEW IN THIS REVISION. The closing radius, the denoise "
   "sigma and the flattening radius had never been swept anywhere; all three can be "
   "swept on the same 26 tiles and the same scorer as the rest, so they now are. "
   f"Neither of the first two shipped values is the best on its own grid: the closing "
   f"radius scores {SW['close_ship']:.4f} IoU at the shipped 3 px against "
   f"{SW['close_best_iou']:.4f} at {SW['close_best']} px, and the denoise sigma "
   f"{SW['den_ship']:.4f} at the shipped 1.0 against {SW['den_best_iou']:.4f} at "
   f"{SW['den_best']}.",
   "Panel f also gives the seven-rung flattening ladder the evidence it never had. "
   "The dashed line is the shipped union; the curve is what ONE radius scores on its "
   f"own. The union reaches {SW['union']:.4f} against {SW['single_best_iou']:.4f} for "
   f"the best single radius ({SW['single_best']} px), so what the ladder buys is "
   f"measured here rather than asserted.",
"The ref. column is how each value was settled, and that is the finding. TEN "
   "of the fifty are SWEPT -- every one of them on this laboratory's own tiles "
   "or frames, in this edition. Two of those sweeps were run for it: the MAD "
   "multiplier, whose earlier sweep was on a public collection the author has "
   "removed, and the background-estimate sigma, which had no sweep anywhere. "
   "FIVE were settled by a test with no value to choose. EIGHT were selected "
   "from a measurement recorded in the source repository but are not drawn -- "
   "several are two values on one frame rather than a grid, and the caption "
   "file quotes each in full. The remaining TWENTY-SEVEN are fixed by "
   "construction or set by hand, with nothing measured about them anywhere; "
   "the build fails unless each of those states why. Where a swept value is NOT the best "
   "point on its grid the panel shows it: the multiplier's own curve is still "
   "rising at the edge of the grid, and lowering it gains recall AND precision "
   "on these frames.",
   "The eight settings the SEM chain applies before the detector runs and the twelve "
   "the TXM mask path applies after it are all in the table. A constant applied to "
   "the data and not declared is an undeclared degree of freedom.",
   "Every value is parsed out of the shipped source with ast, never retyped; a name "
   "that stops being defined there aborts the build."]),
 ("F5 - over- and under-counting.png",
  "What the errors look like, on each arm's own detector",
  ["Blue is marked area the operator confirms, red is marked area the operator ruled "
   "not crack, green is painted crack that was missed, and grey is pixels nobody "
   "adjudicated — neither an error nor an agreement.",
   "SEM, an ambient HIP field: recall 0.66 over the 308,761 pixels the operator "
   "painted crack. That operator ruled NO pixel on this field not crack, so nothing on "
   "it can be an over-count — panel (a) says so where the other three print a "
   "percentage, and the precision of 1.00 the record carries for this row is 1 by "
   "construction rather than a score. Quote the recall.",
   "TXM, a hydrogen-charged 316L fatigue field marked by the trained model: precision "
   "0.85, recall 0.70. That field is in the model's training set — nothing was held "
   "out when the deployed members were fitted.",
   "The field and the window were chosen together, by search. Every SEM field the "
   "figure may legally draw was crossed with five window sizes, each pair of windows "
   "was cut, and the pairs were ranked on the WORSE of their two panels — the share "
   "carrying a verdict of any kind, which is what a crop the colouring can be read on "
   "means. This pair wins at 22.0% against 16.9% for the runner-up. The window is six "
   "of the frame's own 90th-percentile brush widths, 11.6 um here and 18.7 um on the "
   "transmission row.",
   "Eleven of the thirteen HIP frames carrying a mask are one-sided in this way, and "
   "the hydrogen-charged MAR fields carry no correction mask at all. Over-counting on "
   "the electron arm is therefore read off the two-sided fields and off Figure 4, not "
   "off this plate."]),
 ("F8 - scores by sample.png",
  "How well it does, and what retraining bought",
  ["(a) precision, recall and F1 for each arm over every frame it scores, as a mean "
   "over frames with one vote per frame — the aggregation the manuscript quotes. "
   "Pooling over pixels instead would hand the answer to the largest frame; these "
   "differ in area by a factor of two hundred.",
   "The hatched bar is whole-frame pixel accuracy and the red rule across it is what "
   "predicting no crack at all would score. Accuracy is high on both arms — and on "
   "both it sits at or below that rule, because crack is a few per cent of a "
   "micrograph. That is why this paper does not lead with it.",
   "The whisker under precision and F1 is where each would fall if every marked pixel "
   "nobody ruled on were counted a false positive. It is an assumption about "
   "unadjudicated pixels, not a second measurement of them. Recall carries none: an "
   "unruled pixel is not in its denominator.",
   "The SEM bars are IN SAMPLE. The region classifier is enabled and 45 of the 48 "
   "hand-painted frames are the images its bundle was fitted on. Refitting it without "
   "each frame in turn moves precision by 0.006, because at frame scale the model "
   "decides little: 72% of the retained area sits in components kept regardless of "
   "what it says.",
   "(b) is the transmission model, and it does NOT show that each round of human "
   "correction improved it. Across these three rounds the corrected pixel count moves "
   "0.16%, from 31,268,420 to 31,317,667, while held-out IoU rises 0.776 to 0.811 — "
   "so the gain is the recipe, not more labelling. The round where correction volume "
   "did jump, by 20%, is also the round the scoring reference changed, so it cannot "
   "be read and is not drawn. The counts are printed under each point rather than "
   "left for a rising line to imply otherwise.",
   "Per-specimen scores are not on this plate; every sample, including the four that "
   "score below F1 0.5, is in the caption file beside it."]),
 ("F4 - what is measured.png",
  "The measurement the application returns",
  ["Every quantity the shipped measurement functions return, drawn on the largest "
   "interior region of each arm: medial axis, longest tip-to-tip route and its chord, "
   "and inscribed circles at the 10th, 50th and 90th width percentile.",
   "SEM: 27.8 um network length, 1.52 um mean width, 3.97 um maximum. TXM: 13.6, 0.54 "
   "and 1.40 um.",
   "Tortuosity is not on the plate. The definition requires an unbranched medial axis "
   "and these regions carry 12 and 22 branch points, so the software emits nothing for "
   "them; a table row that reads 'no value' in every column it has is about the "
   "software's limits rather than about the crack. The withholding itself still stands "
   "and is recorded in the figure's caption file and in the application."]),
]

W, H = 8.5, 11.0
M = 0.75


def pages():
    missing = [f for f, _, _ in FIGURES if not os.path.exists(os.path.join(OUT, f))]
    if missing:
        raise SystemExit(
            "the paper's figure list names plates that are not in out/:\n  "
            + "\n  ".join(missing)
            + "\nBuild them, or take them off the list -- do not ship a short PDF.")
    return FIGURES


def build(path, with_text):
    pdf = PdfPages(path)
    for n, (fname, title, bullets) in enumerate(pages(), start=1):
        im = Image.open(os.path.join(OUT, fname))
        ar = im.height / im.width
        wrapped = [textwrap.wrap(b, 108) for b in bullets] if with_text else []
        nlines = sum(len(w) for w in wrapped) + len(wrapped)
        text_h = nlines * 0.155 + 0.30 if with_text else 0.0

        avail_w = W - 2 * M
        max_img_h = H - 2 * M - text_h - (0.80 if with_text else 0.55)
        iw, ih = avail_w, avail_w * ar
        if ih > max_img_h:
            ih, iw = max_img_h, max_img_h / ar

        fig = plt.figure(figsize=(W, H))
        fig.text(M / W, 1 - (M - 0.12) / H, "Figure %d" % n, fontsize=15,
                 fontweight="bold", va="top", ha="left")
        fig.text(M / W, 1 - (M + 0.16) / H, title, fontsize=11.5, va="top", ha="left",
                 color="#333333")
        top = 1 - (M + 0.52) / H
        ax = fig.add_axes([(W - iw) / 2 / W, top - ih / H, iw / W, ih / H])
        ax.imshow(im)
        ax.axis("off")

        if with_text:
            y = top - ih / H - 0.42 / H
            for w in wrapped:
                for i, line in enumerate(w):
                    fig.text(M / W + (0.0 if i == 0 else 0.0155), y,
                             ("•  " if i == 0 else "") + line,
                             fontsize=9.3, va="top", ha="left", color="#1a1a1a")
                    y -= 0.155 / H
                y -= 0.075 / H
            if y < M / H - 1e-9:
                raise SystemExit(
                    f"figure {n} ({fname}): bullets overflow the page, last baseline at "
                    f"{y:.4f} against a bottom margin of {M / H:.4f}")
        pdf.savefig(fig)
        plt.close(fig)
    pdf.close()
    print(f"  wrote {path}  ({os.path.getsize(path) / 1e6:.1f} MB, "
          f"{len(FIGURES)} pages)")


def main():
    for i, (f, t, _) in enumerate(FIGURES, start=1):
        print(f"  Figure {i}  {t}\n            {f}")
    print()
    build(PLAIN, with_text=False)
    build(EXPLAINED, with_text=True)


if __name__ == "__main__":
    main()
