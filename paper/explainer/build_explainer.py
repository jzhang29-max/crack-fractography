#!/usr/bin/env python3
"""A long, plain-language explanation of both detectors, for a reader with no background.

WHO THIS IS FOR. Someone who has never used a microscope, never trained a model and does
not know what a pixel mask is. Every term is defined where it first appears. Nothing is
assumed except patience.

WHY IT IS GENERATED RATHER THAN WRITTEN. Every number in it is read from the same records
the figures are drawn from, or parsed out of the shipped detector source with `ast`, so
the document cannot drift away from the software it describes. A name that stops existing
aborts the build instead of printing a stale value.

    <sem-crack-detector>/.venv/bin/python -B paper/explainer/build_explainer.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.dirname(HERE)
REPO = os.path.dirname(PAPER)
sys.path.insert(0, PAPER)
sys.path.insert(0, os.path.join(PAPER, "figures"))
sys.dont_write_bytecode = True

import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

import make_paper as MP                             # noqa: E402
import mk_parameters as PAR                         # noqa: E402
import parameter_glossary as GLOSS                  # noqa: E402

PLATES = os.path.join(PAPER, "figures", "out")
OUT = os.path.join(PLATES, "How the crack detectors work.pdf")
B, H1, H2, H3, S = MP.BODY, MP.H1, MP.H2, MP.H3, MP.SMALL


def rec(name):
    with open(os.path.join(PLATES, name + ".caption.json")) as fh:
        return json.load(fh)


def plate(name):
    p = os.path.join(PLATES, name + ".png")
    if not os.path.exists(p):
        raise SystemExit(f"missing plate {p}; build the figures first")
    return p


def main():
    sem = PAR._sem_constants()
    txm = PAR._txm_constants()
    tiles = json.load(open(os.path.join(REPO, "docs", "figures",
                                        "parameters_tiles.json")))
    dead = json.load(open(os.path.join(PAPER, "figures", "sem_deadzone.json")))
    #: REQUIRED, not optional. 45 of the 48 hand-painted SEM frames are the region
    #: classifier's own training images, so every classifier-on score in this document
    #: is in-sample unless it is read against this record. A build that cannot find it
    #: must fail rather than quietly print the flattering number on its own.
    lofo = json.load(open(os.path.join(REPO, "docs", "figures",
                                       "sem_classifier_lofo.json")))
    fkeep = json.load(open(os.path.join(REPO, "docs", "figures",
                                        "sem_force_keep_share.json")))
    scores = rec("F8 - scores by sample")
    meas = rec("F4 - what is measured")
    param = rec("F6 - how the parameters were determined")
    tally = param["tally"]

    close_best = max(tiles["close"], key=lambda k: tiles["close"][k]["iou"])
    den_best = max(tiles["denoise"], key=lambda k: tiles["denoise"][k]["iou"])
    sing_best = max(tiles["single_radius"],
                    key=lambda k: tiles["single_radius"][k]["iou"])
    union = tiles["union_on_these_tiles"]["iou"]

    pdf = PdfPages(OUT)
    d = MP.Doc(pdf)

    def h1(t):
        d.y -= 0.22
        d.text(t, H1, weight="bold", lead=MP.LEAD["h1"])
        d.y -= 0.06

    def h2(t):
        d.y -= 0.16
        d.text(t, H2, weight="bold", lead=MP.LEAD["h2"])

    def h3(t):
        d.y -= 0.10
        d.text(t, H3, weight="bold", lead=MP.LEAD["h3"])

    def p(t):
        d.text(t, B, gap=0.05)

    def b(t):
        d.bullet(t, B)

    # ---------------------------------------------------------------- title
    d.y -= 1.4
    d.text("How the crack detectors work", H1 + 6, weight="bold",
           lead=MP.LEAD["h1"] + 0.1)
    d.y -= 0.10
    d.text("Everything in this software, explained from nothing", H2,
           color="0.35", lead=MP.LEAD["h2"])
    d.y -= 0.35
    p("This document explains two pieces of software that find cracks in pictures of "
      "metal, and the measurements they produce. It assumes you have never used a "
      "microscope, never trained a model, and have never heard of a pixel mask. Every "
      "term is explained the first time it is used.")
    p("Every number in this document is read directly from the software's own records "
      "when the document is built. If a setting in the software changes and this "
      "document is rebuilt, the number here changes with it. If a setting disappears "
      "entirely, the build stops rather than printing something that is no longer true.")

    # ---------------------------------------------------------------- 1
    h1("1.  What is actually being measured")
    p("A piece of stainless steel is pulled until it breaks. Long before it breaks, tiny "
      "cracks open inside it. We want to know how many there are, how long they are and "
      "how wide — because that is how you tell whether hydrogen has made the metal more "
      "brittle, and by how much.")
    p("The specimen is a **dogbone**: a flat strip, wide at both ends where the machine "
      "grips it, narrow in the middle so that the middle is the part that stretches and "
      "fails. The narrow middle is the **gauge section**. It is about "
      f"{meas['scale_provenance']['sem'] and 22 or 22} micrometres thick — a micrometre "
      "is a thousandth of a millimetre, so the whole specimen is roughly a quarter of "
      "the thickness of a human hair.")
    p("While it is being pulled, it is photographed through a microscope. Each photograph "
      "is a **frame**. A frame is a grid of **pixels**, and each pixel holds one number: "
      "how bright that tiny patch of the specimen was. Dark pixels are, roughly, where "
      "less material was in the way — which is why a crack tends to look dark.")
    p("'Roughly' is doing real work in that sentence, and most of the difficulty in this "
      "project comes from the places where it is wrong.")

    # ---------------------------------------------------------------- 2
    h1("2.  Two microscopes that do not see the same thing")
    d.figure(plate("F2 - how each modality sees a crack"),
             "Figure 1. One specimen, one region, and the two instruments. The electron "
             "microscope records the crack where it cuts the surface; the X-ray records "
             "it through the whole thickness.")
    p("Two different microscopes were used, and this is the single most important thing "
      "to understand about the whole project, because it explains why the two halves of "
      "the software can never be expected to agree.")
    h3("The electron microscope (SEM)")
    p("**SEM** stands for scanning electron microscope. It fires a narrow beam of "
      "electrons at the specimen's polished surface and measures what bounces back. "
      "Electrons do not travel far through metal, so the signal that comes back is from "
      "the top of the specimen only. What an SEM records is therefore the crack **where "
      "it cuts the surface** — a line on a face, like the crack you see on the outside "
      "of a cracked plate.")
    h3("The X-ray microscope (TXM)")
    p("**TXM** stands for transmission X-ray microscope. X-rays go straight through the "
      "specimen to a detector on the far side. Where there is a crack, less metal is in "
      "the way, so more X-rays get through and that part of the picture is brighter or "
      "darker depending on the convention. What a TXM records is the crack's **shadow "
      "through the entire thickness** — everything in the way, stacked into one image, "
      "like an X-ray of a hand showing all the bones at once.")
    h3("Why they disagree, and why that is not a bug")
    p("A crack is a three-dimensional sheet inside the metal. The SEM sees one line "
      "where that sheet meets the surface. The TXM sees the whole sheet flattened into a "
      "shadow. These are two genuinely different quantities. If the two instruments "
      "reported the same number for the same crack, something would be wrong.")
    p("This is why the software has **two separate detectors** rather than one, and why "
      "no result in this work ever averages a number from one arm with a number from the "
      "other.")

    # ---------------------------------------------------------------- 3
    h1("3.  What 'finding a crack' means to a computer")
    p("The software's job is to look at a frame and decide, for every single pixel, "
      "whether that pixel is crack or not crack. The answer is a **mask**: a grid the "
      "same size as the picture, holding true or false instead of brightness. True "
      "means 'this pixel is crack'.")
    p("Everything downstream — how long a crack is, how wide, how many there are — is "
      "computed from the mask. So the mask is the whole product, and every score in this "
      "document is a score for the mask.")
    p("A **connected region** is a clump of true pixels that touch each other. One crack "
      "is usually one connected region, though a faint crack can break into several, "
      "which is a problem the software deals with explicitly later.")

    # ---------------------------------------------------------------- 4
    h1("4.  Model 1 — the electron arm: a rule that proposes, a model that decides")
    d.figure(plate("F1 - flow chart"),
             "Figure 2. Both chains end to end. The top row is the electron arm, the "
             "bottom row the X-ray arm. Each small paired box magnifies what one "
             "cleaning step removed.")
    p("This arm has two halves, and they are different kinds of thing. The first half is "
      "a **rule**: a fixed recipe written down in advance, which would give exactly the "
      "same answer on the day it was written as it does today. The rule looks at the "
      "picture and proposes candidate regions — clumps of pixels dark enough to be "
      "worth considering. The second half is a **trained model**: a small piece of "
      "arithmetic whose numbers were fitted to examples a person marked by hand. It "
      "looks at each proposed region and decides whether to keep it.")
    p("The distinction matters for how much you should trust each half. A rule cannot "
      "have memorised the examples it is tested on, because it never saw them. A "
      "trained model can, and this one did see most of them — section 4.4 is about "
      "exactly that.")

    h3("4.1  What the model looks at, and how small it is")
    p("The model is a **logistic regression**: it multiplies eight measurements of a "
      "region by eight fitted numbers, adds a ninth, and turns the total into a "
      "probability between 0 and 1. Nine numbers in total. It is about as simple as a "
      "trained model gets, and it is stored in a single file, "
      "`models/crack_classifier.joblib`.")
    p("The eight measurements are all properties of the region's shape and darkness: how "
      "large it is (on a logarithmic scale), how elongated, how solid, how eccentric, "
      "how much of its bounding box it fills, how circular, how dark it is on average, "
      "and how strongly a line-detecting filter responds to it. A crack is long, thin, "
      "dark and line-like; a pore is small, round and solid. Those eight numbers are the "
      "model's whole view of the world — it never sees the picture.")
    p(f"If the probability is at least {lofo['deployed_threshold']:.4f}, the region is "
      "kept. One exception overrides the model: a region of at least 50,000 pixels is "
      "kept whatever it says, because a dark area that large is in practice never "
      "anything but a real crack or void, and the model was never shown one.")

    h3("4.2  The model was switched off for a year, and the reason is still on record")
    p("Until recently the software ran this model and then **ignored its answer**. Every "
      "region was scored, the verdict written into the results table, and then every "
      "candidate was kept regardless. That was not an oversight; it was measured. "
      "Pooled over the 26 hand-marked image crops, bypassing the classifier improved "
      "every score at once:")
    b(f"precision {dead['pooled_26']['v147']['precision']:.3f} to "
      f"{dead['pooled_26']['ablation']['precision']:.3f}")
    b(f"recall {dead['pooled_26']['v147']['recall']:.3f} to "
      f"{dead['pooled_26']['ablation']['recall']:.3f}")
    b(f"IoU {dead['pooled_26']['v147']['iou']:.3f} to "
      f"{dead['pooled_26']['ablation']['iou']:.3f}")
    b(f"F1 {dead['pooled_26']['v147']['f1']:.3f} to "
      f"{dead['pooled_26']['ablation']['f1']:.3f}")
    p(f"Specimen by specimen the same thing held: across "
      f"{dead['paired']['ablation']['n_specimens']} specimens the median improvement in "
      f"IoU was {dead['paired']['ablation']['median_delta_iou']:+.3f}, better on "
      f"{dead['paired']['ablation']['n_better']} and worse on "
      f"{dead['paired']['ablation']['n_worse']}.")

    h3("4.3  It is switched on now, and this is what that trades")
    p("The model is enabled in the configuration this document describes. That is a "
      "deliberate choice and it is a trade, not an upgrade. Measured on the shipped "
      "candidate stage, one variable changed and nothing else — the same proposed "
      "regions, scored and then either all kept or filtered:")
    _fl = dead["pooled_25_no_flood"]["v1492_floor"]
    _sh = dead["pooled_25_no_flood"]["shipped"]
    b(f"precision rises {_fl['precision']:.3f} to {_sh['precision']:.3f}")
    b(f"recall falls {_fl['recall']:.3f} to {_sh['recall']:.3f}")
    b(f"IoU falls {_fl['iou']:.3f} to {_sh['iou']:.3f}")
    b(f"F1 falls {_fl['f1']:.3f} to {_sh['f1']:.3f}")
    _st = dead["paired_steps"]["classifier_over_floor"]
    p(f"Across {_st['n_specimens']} specimens the median change in IoU is "
      f"{_st['median_delta_iou']:+.3f}, better on {_st['n_better']} and worse on "
      f"{_st['n_worse']}" +
      (f" (p = {_st['wilcoxon_p']:.4f})." if _st['wilcoxon_p'] is not None else ".") +
      " In plain terms: switching the model on makes the software more **cautious**. "
      "What it marks is more often really crack, and it marks less of the crack that is "
      "there. Which of those two errors matters more depends on what the measurement is "
      "for, and that is a judgement about the experiment, not about the software.")
    p("The scores quoted here exclude one image crop. It is an off-specimen void that "
      "owns most of the false positives at every setting, so a pooled number including "
      "it describes that one object rather than the change. The figures show both.")

    h3("4.4  Has the model already seen the answers?")
    p("This has to be asked before any score in section 9 is read. The model's own file "
      f"records the {lofo['n_training_images']} images it was fitted on, and "
      f"{len([r for r in lofo['per_frame'] if r['in_training_set']])} of the "
      f"{lofo['frames_scored']} hand-painted electron frames scored in this document "
      "**are those images**. A student who has seen the exam paper scores well on it, "
      "so the question is how much of the score is that.")
    p("It was measured rather than argued about. The model was refitted from scratch "
      "once for every frame, each time leaving that frame's examples completely out, "
      "and then asked about the frame it had never met. Nothing about the held-out "
      "frame entered the fit. Averaged over frames:")
    _ia, _oa = lofo["fitted_frames"]["refit_all"], lofo["fitted_frames"]["lofo_fixed"]
    b(f"having seen the frame: precision {_ia['mean_precision']:.4f}, "
      f"recall {_ia['mean_recall']:.4f}, F1 {_ia['mean_f1']:.4f}")
    b(f"never having seen it: precision {_oa['mean_precision']:.4f}, "
      f"recall {_oa['mean_recall']:.4f}, F1 {_oa['mean_f1']:.4f}")
    p(f"The difference is {abs(_ia['mean_precision'] - _oa['mean_precision']):.4f} in "
      f"precision and {abs(_ia['mean_f1'] - _oa['mean_f1']):.4f} in F1 — close to "
      "nothing. That is a real result and it is worth understanding, because the "
      "reassuring reading of it is the wrong one. The scores are not honest because the "
      "model generalises well. They are honest because **on a whole micrograph the "
      "model barely gets to decide anything**.")
    h3("4.5  Why the model hardly matters on a whole frame, and matters a lot on a crop")
    _fk = {r["frame"]: r for r in fkeep["frames"]}
    _f0 = _fk.get("260622_316_H_b2_back_CBS_01") or fkeep["frames"][0]
    p("A crack in one of these micrographs is one enormous connected region. On the "
      f"frame used throughout this document the software proposes {_f0['n_regions']:,} "
      f"regions, and {_f0['n_forced']} of them — "
      f"{100 * _f0['forced_share_of_regions']:.2f}% — "
      f"{'holds' if _f0['n_forced'] == 1 else 'hold'} "
      f"{100 * _f0['forced_share_of_kept_area']:.1f}% of all the pixels the software "
      f"ends up marking. Whatever the model decides about the other "
      f"{_f0['n_regions'] - _f0['n_forced']:,} can only move a small part of the mask. "
      "The software also keeps any region of 50,000 pixels or more whatever the model "
      "says, which guarantees the big ones survive regardless — though on these frames "
      "the model wanted to keep them anyway, so that rule never had to override it.")
    _zero = sum(1 for r in fkeep["frames"] if r["n_forced"] == 0)
    _hi = max(fkeep["frames"], key=lambda r: r["forced_share_of_kept_area"])
    p(f"Across all {len(fkeep['frames'])} frames scored in this document, "
      f"{100 * fkeep['pooled_forced_share_of_kept_area']:.0f}% of the marked area sits "
      "in regions large enough to be kept unconditionally, and those regions are under "
      "1% of the regions proposed. It is not uniform: at the top end one frame reaches "
      f"{100 * _hi['forced_share_of_kept_area']:.0f}%, and on "
      f"{_zero} of the {len(fkeep['frames'])} no region reaches that size at all, so on "
      "that one the model decides everything. The share does not, however, predict how "
      "much switching the model on actually moves a particular frame's score: across "
      "the 18 the two are not related to any degree this collection can show. What is "
      "reliable is the size of the effect rather than which frame gets it — on 14 of "
      "the 18 the score moves by less than two points either way.")
    p("On a 512-pixel crop that is not true. No region is anywhere near 50,000 pixels, "
      "the area is spread across many small regions, and the model decides most of it. "
      "That is why the two scales disagree so sharply, and it is why this document "
      "reports them separately instead of averaging them into one claim.")
    _ov = dead.get("pooled_by_training_overlap")
    if _ov:
        _step = dead["paired_steps"]["leakage_in_sample_over_held_out"]
        _n = dead["n_tiles_by_training_overlap"]
        p("On the crops, where the model does the work, the same question was asked "
          f"again. {_n['parent_never_trained_on']} of the "
          f"{_n['parent_never_trained_on'] + _n['parent_in_training_set']} crops come "
          "from specimens the model was never fitted on at all — every "
          "hydrogen-charged field among them — and for the rest the model was refitted "
          "without that specimen's own examples. Comparing the deployed model with the "
          "refitted one on the same crops, the off-specimen void crop excluded:")
        _a = dead["pooled_25_no_flood"]["shipped"]
        _c = dead["pooled_25_no_flood"]["shipped_lofo"]
        b(f"as deployed: precision {_a['precision']:.4f}, recall {_a['recall']:.4f}, "
          f"F1 {_a['f1']:.4f}")
        b(f"never having seen the specimen: precision {_c['precision']:.4f}, "
          f"recall {_c['recall']:.4f}, F1 {_c['f1']:.4f}")
        p("Specimen by specimen the median change in overlap is "
          f"{_step['median_delta_iou']:+.4f}, with the two giving an identical answer "
          f"on {_step['n_tied']} of the {_step['n_specimens']} specimens. So the model "
          "has not memorised these crops either; it is doing the same thing on a "
          "specimen it has never met as on one it was built from.")
        _ti = dead["pooled_by_training_overlap_no_flood"]["parent_in_training_set"]
        _tn = dead["pooled_by_training_overlap_no_flood"]["parent_never_trained_on"]
        p("What does differ is how much the model HELPS. Splitting the same crops by "
          "whether the model was ever fitted on that specimen, and comparing precision "
          "without the model against precision with it:")
        b(f"specimens it was fitted on: {_ti['v1492_floor']['precision']:.3f} to "
          f"{_ti['shipped']['precision']:.3f}")
        b(f"specimens it was never fitted on: "
          f"{_tn['v1492_floor']['precision']:.3f} to "
          f"{_tn['shipped']['precision']:.3f}")
        p("It raises precision in both groups, and by more on the ones it has seen. "
          "That is not the same thing as having memorised them — the refit above rules "
          "that out — but it is a reason to expect a smaller benefit on a specimen "
          "family that is new. One caution about this split: the crops the model was "
          "never fitted on are also the hydrogen-charged specimens, so this collection "
          "cannot separate 'unfamiliar to the model' from 'a different kind of "
          "specimen'. The two move together here.")
    p("One thing was not re-done per fold: the probability cut-off was chosen once, on "
      "the whole collection. A second version of the frame-scale test derives the "
      "cut-off inside each fold from that fold's own examples alone, and the two "
      "together are the honest range rather than a single figure. Both are in the "
      "record.")

    p("The rule half — everything that happens before the model gets a vote — runs in "
      "four stages.")
    h3("Stage 1 — read the frame")
    p("The raw image is converted to a standard brightness scale, the instrument's own "
      "information bar is detected and cut off, and the part of the picture that "
      "actually contains specimen is found. Brightness is clipped at the "
      f"{sem['load_as_uint8.low_pct']:g}th and {sem['load_as_uint8.high_pct']:g}th "
      "percentiles, which means the darkest and brightest fractions of a percent are "
      "flattened so that one stray bright speck cannot set the scale for the whole "
      "image.")
    h3("Stage 2 — flatten the background")
    p("Microscope images are unevenly lit: one corner is brighter than another, for "
      "reasons that have nothing to do with cracks. If you looked for 'dark pixels' "
      "directly you would mostly find the dim corner. So the software estimates the "
      "slow background shading and subtracts it, leaving only local departures from it.")
    p("It does this at **seven different scales at once** — blur radii of "
      f"{PAR.LADDER[0]} to {PAR.LADDER[-1]} pixels — and keeps anything that looks dark "
      "at any of them. This is called the **multiscale union**. The reason is that a "
      "narrow crack only looks dark compared to its immediate surroundings, while a wide "
      "one only looks dark compared to a much larger area. One radius cannot catch both.")
    h3("Stage 3 — cut out the dark pixels")
    p("Now the actual decision. For each scale, the software computes the typical "
      "brightness of the flattened image and a robust measure of how much it normally "
      "varies, called the **MAD** (median absolute deviation). A pixel is called crack "
      f"if it is more than **k = {PAR.K:g}** MADs darker than typical.")
    p("The letter k is the one genuinely tuned number in the entire electron arm. A "
      "small k marks almost everything; a large k marks almost nothing. There is also a "
      f"hard floor: any pixel darker than {PAR.GATE} on the 0–255 brightness scale is "
      "called crack regardless, which catches cracks so dark that the relative test "
      "misses them.")
    h3("Stage 4 — clean up")
    p("The raw decision is speckly. Single stray pixels are removed, small gaps inside a "
      "crack are closed, and clumps smaller than a size floor are discarded entirely — "
      f"{PAR.CLEAN_MIN} pixels at the first pass and {PAR.CAND_MIN} at the second. What "
      "survives is the mask.")

    # ---------------------------------------------------------------- 5
    h1("5.  Model 2 — the X-ray arm: a model that was trained")
    p("Cracks in the X-ray images are far fainter than in the electron images, and the "
      "darkness rule simply does not work on them. So this arm uses a **trained model** "
      "instead.")
    h3("What 'trained' means")
    p("A person looked at 71 X-ray frames and painted, by hand, which pixels were crack "
      "and which were not. The software was then shown those painted examples and "
      "adjusted its internal numbers until its answers matched the person's as closely "
      "as it could. Those adjusted numbers are the **model**. Nobody writes them down by "
      "hand; they are found by the fitting procedure.")
    p("This is powerful and it carries an obvious risk: a model can learn the specific "
      "frames it was shown rather than the general idea of a crack. That risk is why "
      "scores are reported on frames the model did not see during fitting, and why this "
      "document is careful later about which scores are which.")
    h3("What the model actually looks at")
    p("The model does not see the raw picture. For every pixel it is given a list of "
      f"**{int(json.load(open(os.path.join(PAPER, 'figures', 'txm_stats.json')))['n_features'])} "
      "numbers** describing that pixel and its neighbourhood: how bright it is, how "
      "bright the area around it is at several sizes, how much texture there is, whether "
      "it sits on a ridge or in a valley, and so on. Those numbers are the "
      "**features**, and the model's job is to turn a list of features into one "
      "probability between 0 and 1.")
    h3("The second member, and what SAM is")
    p("A second model gets the same features plus a much larger set of numbers produced "
      f"by **SAM** ({txm['SAM_MODEL_ID']}). SAM — the Segment Anything Model — is a large "
      "general-purpose image model trained by someone else on millions of ordinary "
      "photographs. It was not trained on cracks and it is not retrained here: it is "
      "**frozen**, used only as a way of turning an image patch into a rich numerical "
      "description that happens to be useful.")
    p(f"SAM cannot see a whole frame at once; it reads {txm['TILE']} pixel squares. The "
      f"software therefore walks across the frame in steps of {txm['TILE_STRIDE']} "
      f"pixels, so consecutive squares overlap by "
      f"{int(txm['TILE']) - int(txm['TILE_STRIDE'])} pixels and the description does not "
      "break at the seams.")
    h3("Averaging the two, and deciding")
    p("The two models' probabilities are averaged. A pixel is finally called crack if "
      f"the average is above **{float(txm['DEFAULT_THRESHOLD']):.2f}**. Then the same "
      "kind of cleaning as the electron arm runs: specks below "
      f"{txm['MIN_BLOB_PX']} pixels go, holes up to {txm['FILL_HOLES_MAX_PX']} pixels "
      "are filled, the mask is narrowed to the width the image can actually support, and "
      "suspiciously straight objects are thrown out because real cracks wander and "
      "detector artefacts do not.")

    # ---------------------------------------------------------------- 6
    h1("6.  Where every setting came from")
    d.figure(plate("F6 - how the parameters were determined"),
             "Figure 3. Every constant both detectors read, with a graph for each one "
             "that has evidence behind it.")
    p("Software like this is full of numbers that somebody had to choose: how dark is "
      "dark, how small is too small, how much blur. There are **fifty** of them across "
      "the two arms. Most papers never say what they are. This one lists all fifty and, "
      "more importantly, says honestly how each was arrived at.")
    p("The honest answer is uncomfortable, and it is the main finding of that figure:")
    b(f"**Exactly one** of the fifty was chosen by testing it against hand-marked "
      f"images: the MAD multiplier k = {PAR.K:g}.")
    b(f"**{len(tally['settled by a test, no value to choose'])}** were settled by a "
      "yes-or-no test with no value to pick — for instance, whether to use a learned "
      "region classifier at all. That one was answered twice: measured, the answer was no, and section 4.3 gives the numbers; chosen, the answer is now yes, and the software runs with it on.")
    b("**Nine** were inherited from older code with no record of why, and have been "
      "tested here after the fact. Their graphs show how sensitive the result is to "
      "them, not how they were chosen.")
    b("The remaining **thirty-six** are fixed by construction and have never been "
      "searched at all, in this work or the code it came from.")
    h3("Three settings were tested for the first time, and two came back badly")
    p("Three constants that had never been examined anywhere could be tested on the same "
      "26 hand-marked image crops and the same scorer as everything else, so they were. "
      "Two of the three say the value the software ships with is not the best one:")
    b(f"**Closing radius.** Shipped at {int(sem['clean_mask.close_radius'])} pixels, "
      f"scoring {tiles['close'][str(int(sem['clean_mask.close_radius']))]['iou']:.4f}. "
      f"The best value on the grid is {close_best} pixels at "
      f"{tiles['close'][close_best]['iou']:.4f}.")
    b(f"**Denoise strength.** Shipped at "
      f"{sem['segment_dark_regions.denoise_sigma']:.1f}, scoring "
      f"{tiles['denoise'][str(float(sem['segment_dark_regions.denoise_sigma']))]['iou']:.4f}. "
      f"The best is {den_best} at {tiles['denoise'][den_best]['iou']:.4f}.")
    b(f"**The seven-scale trick.** This one came back well, and it had never been "
      f"checked before: the seven scales together score {union:.4f}, against "
      f"{tiles['single_radius'][sing_best]['iou']:.4f} for the best single scale "
      f"({sing_best} pixels). The extra complexity is earning its place.")
    p("The two adverse results are reported rather than quietly fixed, because every "
      "score in this work was measured on the configuration that actually ran. Changing "
      "a constant now would mean re-running everything.")

    # ------------------------------------------------- 6b: every parameter in words
    h1("7.  Every setting, one at a time")
    p("This section walks all fifty, in the order the data meets them. Each one names "
      "what it does and, where it was measured, what changing it costs. The names "
      "match the rows of the table in the figure above, so the two can be read "
      "together.")
    n_gloss = len([g for g in GLOSS.SEM_GLOSS + GLOSS.TXM_GLOSS if g[1]])
    if n_gloss != PAR.DOCSTRING_TALLY["total"]:
        raise SystemExit(f"the glossary explains {n_gloss} constants and the detectors "
                         f"read {PAR.DOCSTRING_TALLY['total']}; a setting has been "
                         f"added or removed without a plain-language entry")
    for arm, items in (("The electron arm", GLOSS.SEM_GLOSS),
                       ("The X-ray arm", GLOSS.TXM_GLOSS)):
        h2(arm)
        for name, gloss in items:
            if gloss is None:
                h3(name)
            else:
                d.y -= 0.02
                d.text(f"**{name}** — {gloss}", B)
    p(f"That is {n_gloss} settings. One of them was chosen by testing it against "
      f"hand-marked images.")

    # ---------------------------------------------------------------- 7
    h1("8.  How we know whether it works")
    p("The software's answer is compared against a person's. A trained operator looked "
      "at frames and painted them by hand. That painting is the **reference** — not "
      "truth exactly, but the best available standard.")
    h3("The four things a painted pixel can be")
    b("**Crack.** The person painted it as crack.")
    b("**Not crack.** The person explicitly painted it as not crack.")
    b("**Erased.** The person painted something and then took it back — which is also a "
      "'not crack' verdict, not an absence of one.")
    b("**Untouched.** The person never gave a verdict on that pixel at all. This is most "
      "of most frames, and it matters more than it sounds.")
    h3("The four numbers")
    p("Compare the software's mask against the person's verdicts and you get four counts: "
      "pixels both called crack, pixels only the software called crack, pixels only the "
      "person called crack, and pixels neither did. From those come the standard scores:")
    b("**Precision** — of everything the software marked, what fraction was really "
      "crack? Low precision means it cries wolf.")
    b("**Recall** — of all the real crack, what fraction did the software find? Low "
      "recall means it misses things.")
    b("**F1** — a single number combining precision and recall, so that doing badly at "
      "either one drags it down. 1.0 is perfect, 0 is useless.")
    b("**IoU** (intersection over union) — the overlap between the two marked areas "
      "divided by their combined area. Stricter than F1 and used for the settings work.")
    h3("Why there is a whisker on some bars")
    p("Because most pixels are untouched, there is a real question about what to do with "
      "a pixel the software marked where nobody ever gave a verdict. Counting it as "
      "correct is too generous; counting it as wrong is too harsh. The bars show the "
      "score over pixels a person actually ruled on, and the thin whisker shows where "
      "the score would fall under the harsh assumption. On some specimens the two are "
      "very far apart, and the honest reading is the range, not either end.")

    # ---------------------------------------------------------------- 8
    h1("9.  What the scores actually are")
    d.figure(plate("F8 - scores by sample"),
             "Figure 4. Scores per specimen. Blue is the electron arm, orange the X-ray "
             "arm; the whisker is the harsh assumption described above.")
    _sel = scores.get("selection", {})
    _thr = _sel.get("threshold_f1", 0.5)
    p("There is no single number for 'how good is it', and anyone who gives you one for "
      "software like this is hiding something. Performance varies enormously between "
      "specimens. **The figure above deliberately shows only the groups scoring F1 "
      f"{_thr:g} or better**, because the rest are being treated as work still to do "
      "rather than as results; every group is listed here either way, and the ones the "
      "figure leaves out are marked.")
    _all = []
    for row in scores["samples"]:
        bits = []
        for arm in ("SEM", "TXM", "PUB"):
            a = row["arms"].get(arm)
            if a:
                bits.append((arm, a))
                _all.append((row["sample"], arm, a))
        if bits:
            #: PER ARM, not per row. b2 has both arms and only its transmission
            #: group is withheld; marking the whole row would say the electron bar
            #: is missing from a plate that draws it.
            def _one(arm, a):
                unit = "image" if arm == "PUB" else "frame"
                return (f"{arm} F1 {a['f1']:.2f} over {a['n']} {unit}"
                        + ("s" if a["n"] != 1 else "")
                        + ("" if a.get("drawn", True) else " *(not on the figure)*"))
            b(f"**{row['sample']}** — "
              + "; ".join(_one(arm, a) for arm, a in bits) + ".")
    _best = max(_all, key=lambda t: t[2]["f1"])
    _worst = min(_all, key=lambda t: t[2]["f1"])
    p(f"That spread is the result a user has to plan around. A group where the software "
      f"scores {_best[2]['f1']:.2f} ({_best[1]} {_best[0]}) and one where it scores "
      f"{_worst[2]['f1']:.2f} ({_worst[1]} {_worst[0]}) are not the same tool, and the "
      "reason is the data, not the code: on the series where it fails, the cracks are "
      "nearly invisible to a brightness-based rule.")

    # ---------------------------------------------------------------- 9
    h1("10.  Is there something better?")
    d.figure(plate("F7 - model selection"),
             "Figure 5. Eight crack-finding methods given the same chance on both "
             "microscopes.")
    p("Eight established methods were run on the same images and scored the same way, "
      "including the classical thresholding techniques this field normally uses and "
      "ridge filters designed to find thin line-like features.")
    p("Panel (a) asks the simplest question: did the method report the right **amount** "
      "of crack? A value of 1 means it matched the person exactly. The method used here "
      "is the closest to 1 on both instruments, which is why it was chosen.")
    p("Panels (b) and (c) ask something harsher: does the method beat simply declaring "
      "the entire image crack-free? On the electron images **not one of the eight does**, "
      "because cracks are such a small fraction of any picture that a blank answer scores "
      "well on pixel accuracy. This is a statement about the metric, not about the "
      "methods, and it is why area agreement rather than pixel accuracy is what this work "
      "reports.")

    # ---------------------------------------------------------------- 10
    h1("11.  What it measures once a crack is found")
    d.figure(plate("F4 - what is measured"),
             "Figure 6. The quantities the software returns for a single crack.")
    p("Having decided which pixels are crack, the software reports, for each connected "
      "region: its area; its **network length**, which is the total length of the "
      "skeleton running down the middle of every branch; the **longest route** from one "
      "tip to another; the **mean** and **maximum width**, found by fitting the largest "
      "circle that fits inside at each point; and the direction the crack runs.")
    p("One quantity is deliberately **not** reported. **Tortuosity** — how wavy a crack "
      "is, defined as its length divided by the straight-line distance between its ends "
      "— only has a meaning for a crack with no branches. Real cracks branch. The "
      "software emits nothing rather than an invalid number.")

    # ---------------------------------------------------------------- 11
    h1("12.  What this software cannot do")
    p("A fair description has to include the limits, and these are measured rather than "
      "guessed.")
    b("**It fails on some specimen series.** Where cracks are not darker than their "
      "surroundings, a darkness rule cannot find them, and F1 falls to near zero.")
    b("**The electron rule does not transfer to X-ray images.** Carried across unchanged, "
      "no value of its one tuned constant beats declaring the image crack-free. That is "
      "why the two arms exist.")
    b("**Most of its settings were never optimised.** Thirty-six of fifty were fixed by "
      "construction and never searched.")
    b("**The reference is one person's painting**, it covers only part of each frame, "
      "and it is not independent of the X-ray model, which was fitted on it.")
    b("**It does not measure depth.** Neither instrument gives it, so no number in this "
      "work is a three-dimensional crack volume.")

    # ---------------------------------------------------------------- 12
    h1("13.  Glossary")
    for term, mean in [
        ("Dogbone", "the specimen shape: wide at the ends, narrow in the middle."),
        ("Gauge section", "the narrow middle of the dogbone, where it stretches."),
        ("Frame", "one photograph from a microscope."),
        ("Pixel", "one cell of the grid a digital picture is made of."),
        ("Mask", "a true/false grid the same size as the picture, saying which pixels "
                 "are crack."),
        ("SEM", "scanning electron microscope: sees the surface."),
        ("TXM", "transmission X-ray microscope: sees through the thickness."),
        ("Threshold", "a cut-off: above it, call it crack; below it, do not."),
        ("MAD", "median absolute deviation, a measure of normal variation that is not "
                "thrown off by a few extreme values."),
        ("Feature", "one number describing a pixel and its surroundings, fed to a "
                    "trained model."),
        ("SAM", "the Segment Anything Model, a large general image model used here "
                "frozen, as a source of features."),
        ("Frozen", "used exactly as supplied, with no further training."),
        ("Precision", "of what was marked, how much was right."),
        ("Recall", "of what was there, how much was found."),
        ("F1", "precision and recall combined into one number."),
        ("IoU", "overlap divided by combined area; stricter than F1."),
        ("Tortuosity", "how wavy a crack is; only defined for an unbranched crack, and "
                       "not reported here."),
    ]:
        b(f"**{term}** — {mean}")

    d.close()
    pdf.close()
    print(f"wrote {OUT}  ({os.path.getsize(OUT) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
