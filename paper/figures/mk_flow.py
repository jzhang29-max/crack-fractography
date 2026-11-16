#!/usr/bin/env python3
"""Figure 1: TWO FLOW CHARTS -- one per microscopy -- not one filmstrip run twice.

WHAT THIS REPLACES AND WHY. The previous version of this plate was a 6 x 2 grid of
pictures: six columns of arrays, two rows of microscopy, the same six column headings
over both rows. Four things were wrong with it and all four are fixed here.

1. IT WAS A FILMSTRIP, NOT A FLOW CHART. A column heading names an ARRAY; it does not
   say what happened between two of them, and the plate carried no operation anywhere.
   Each arm is now a chart in its own right: named stage boxes, an arrow between every
   pair, and the OPERATION written on the arrow. A reader can follow either chain
   without the caption and without the text, which is the test this figure has to pass.

2. "PROPOSED" AND "CLEANED" DID NOT LOOK DIFFERENT, because they are not very different:
   on the window shown, the SEM cleaning step moves 5,594 pixels out of 1.6 million --
   0.3% of the panel, invisible at 18 mm. Each cleaning arrow now carries an INSET PAIR,
   the same crop before and after, placed on a connected component that step removes
   INSIDE the window shown. WHICH component: the largest one the OPERATOR DID NOT PAINT
   AS CRACK, so the panel illustrates what the step is for. Before that rule existed it
   was simply the largest, and both SEM insets landed on pieces of the operator's own
   painted crack -- the plate's illustration of cleaning was cleaning deleting real
   crack, twice. That is a true thing about these steps and the caption JSON still
   carries it per inset, `removed_in_window_painted_crack_px` against
   `removed_in_window_px`; it is not what an inset labelled "open and close" is for.
   Where every piece a step removes overlaps painted crack the rule falls back to the
   largest and `inset_placed_on` says so. The component is found with `ndi.label` and
   the window is six times its longest side; nothing is placed by eye. NO MASK IS
   DILATED ANYWHERE IN THIS FIGURE -- the insets are nearest-neighbour magnifications of
   the real arrays, and the pixels a step deletes are drawn in the second hue so the
   reader watches them go.

3. THE CHAIN LOOKED DISCONTINUOUS, because every mask panel was drawn over the ORIGINAL
   grey while the decision had been taken on a different array. Both arms now draw their
   mask panels over the array their own detector actually read: the flattened frame in
   the SEM arm, and -- see below -- the frame itself in the transmission arm.

4. THE TRANSMISSION ROW SHOWED THE WRONG DETECTOR, AND THAT WAS A REAL BUG.
   `both_modalities.stages()` applies `segment_dark_regions`, the SEM darkness rule, to
   whatever array it is handed, so the old row (j, k, l) was the SEM detector run on a
   TXM frame. On this frame that mask agrees with the operator at IoU 0.227 over
   refereed pixels. It is not what the application ships for transmission data and it is
   not what the paper reports: the TXM arm is a TRAINED PIXEL MODEL, and the same frame
   under it scores IoU 0.796. The lower chart is that model, loaded from the deployed
   joblibs through the application's own `app/core/pipeline.py`, every intermediate kept.

THE TWO CHARTS DO NOT HAVE THE SAME OPERATIONS, and forcing them to is what produced the
bug above. The arrays each chain builds happen to number the same, so the plate is still
a grid, but the five arrows of the SEM chart and the five of the TXM chart have nothing
in common except that both end in a mask:

  SEM   a threshold rule FOLLOWED BY a trained region classifier. Subtract a blurred
        copy of the frame at seven radii, keep what is darker than a robust cut, clean up
        the morphology -- and then score every surviving region with an 8-feature
        logistic model and keep the ones it calls crack. Three constants shape the
        candidates (`MAD_K`, `CLEAN_MIN_PX`, `MIN_AREA_PX`) and nine fitted numbers
        decide which of them survive.

        THIS FIGURE USED TO SAY "nothing trained", and that was true of the configuration
        it was drawn for: `USE_REGION_CLASSIFIER` was False, the classifier was scored and
        its verdict discarded, and no fitted weight reached the mask. The flag is now
        True. Every string this module writes about it is derived from the live flag
        below, not from a sentence someone remembered to update.

  TXM   a trained pixel model -- 17 hand-built image channels plus a 256-d frozen SAM
        ViT-H embedding, two fitted members whose probabilities are averaged, cut at
        0.60, then pruned and narrowed to what the image shows.

THERE IS NO BACKGROUND-SUBTRACTION STEP IN THE TRANSMISSION ARM, and the figure says so
rather than leaving a hole where the SEM arm has one. The model reads the frame
normalised 1-99% and nothing else; six of its seventeen channels are Gaussian-smoothed
copies at sigma 2 to 64 px, which is where the local background enters. The destitched,
flat-fielded view the operator paints on is a DISPLAY step -- `app/core/pipeline.ingest`
stores it as `display.npy` and feeds `img.npy` to the model -- and no mask in this figure
is drawn over it.

EVERY NUMBER IN THE PLATE AND IN ITS CAPTION JSON IS COMPUTED HERE OR READ FROM A RECORD.
The transmission model's held-out score is read from the gate record of the very joblibs
that get loaded -- `app_data/models/retrain_history.json`, recipe thincore_v5, stamp
20260824_225236 -- rather than retyped. (`docs/figures/txm_model_scores.json` carries
0.7921 for the v4 members and states that no v5 grouped-CV artefact exists in either
repository. It does, in that gate record; this script prints both so the gap is visible.)

THE SCALE BARS ARE DRAWN HERE instead of by `scalebar.scalebar`, and only because the
panels are 18 mm wide. That function sizes its opaque white patch to the BAR, and at this
panel size an 8 pt label is wider than any sensible bar: on the SEM detail panel "20 um"
overhung the patch by 4 mm and the leading digit was lost against the black crack. The
house conventions it exists to enforce -- black bar, black text, opaque white patch, a
round number about a fifth of the panel -- are kept, and its own `pick_length_nm` and
`fmt_nm` choose and format the number.

    <sem-crack-detector>/.venv/bin/python -B mk_flow.py
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np                                   # noqa: E402
import matplotlib                                    # noqa: E402
matplotlib.use("Agg")                                # noqa: E402
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Rectangle, FancyArrowPatch  # noqa: E402
from scipy import ndimage as ndi                     # noqa: E402

import _paths                                        # noqa: E402
import journal_style as J                            # noqa: E402
import both_modalities as BM                         # noqa: E402
import mk_workflow as WF                             # noqa: E402
import mk_stages as ST                               # noqa: E402
import scalebar as SB                                # noqa: E402

J.use()
OUT = _paths.FIG_DIR
NAME = "F1 - flow chart"

#: The transmission frame as the application filed it. It is the same field
#: `both_modalities` stages -- the figure set's TXM field -- reached by the id the app
#: gave it, because the deployed model's cached SAM embedding and its probability map
#: live under that id. The script checks the stored original is byte-identical to the
#: TIFF in the TXM repository before it uses anything else from that directory.
TXM_IID = ("Average_mosaic_260618_b2_335_31um_FRFR_idx00000_mosaictileAA_img001of010"
           "_xrm_bim__37d5f720")

#: Held-out score of the DEPLOYED transmission model, read from its own gate record.
TXM_GATE = os.path.join(_paths.TXM_REPO, "app_data", "models", "retrain_history.json")
TXM_STAMP = "20260824_225236"

#: Inset geometry. The window is six times the longest side of the component it is
#: centred on, floored at 80 px so a tiny component still has context around it, and
#: capped at a sixth of the detail window so an inset is always a magnification.
#: 6 put the removed piece in the middle of a field six times its own width, where a
#: 30 px speck is a dot. 4 fills the panel with the thing the inset is about.
INSET_SPAN, INSET_MIN_PX = 4, 80

#: WHAT MAKES A REMOVED PIECE FREE-STANDING. A cleaning step does two different things
#: and they look nothing alike: it drops free-standing specks, which is what it is for,
#: and it shreds a dark feature into crumbs it then drops, which is its side effect.
#: The SEM inset pair showed the second kind twice -- orange crumbs strung in a line
#: down a dark band -- and a reader sees the step eating a crack, because that is what
#: that picture is. A piece is free-standing when, after every removal in the window is
#: dilated by this radius, its blob holds NO OTHER removed piece and touches no mask
#: the step kept. Testing only the kept mask was not enough: the crumbs in that band
#: had no surviving mask near them either, and it was each other that gave them away.
#: The counts for both kinds go in the caption record whichever kind is drawn.
ISOLATION_PX = 10

PROB_CMAP = LinearSegmentedColormap.from_list("prob", ["#ffffff", J.ACCENT])

# ------------------------------------------------------------------ the transmission arm


def txm_arm():
    """The deployed transmission model, run on this frame, every intermediate kept.

    IMPORTED, NOT RETRANSCRIBED. `app/core/model.py` builds the feature stack and runs
    the two members; `app/core/pipeline.py` owns the threshold, the speck floor, the hole
    cap and the two narrowing steps. Re-typing any of them here is how the previous
    version of this figure came to show a different detector from the application.

    THE SAM ENCODER IS NOT DOWNLOADED. The 256-d embedding for this frame is cached in
    the store at the stride the deployed model requires, and `CrackModel.predict` takes
    it as an argument. If that cache is missing or stale the script stops and says so,
    rather than quietly pulling 2.4 GB or quietly falling back to the 17-feature member,
    which would be a different model shown under the same name.

    The staged chain is checked against `effective_mask(corrections="none", tight=True)`
    -- the application's own single entry point for "the model's own output", with the
    operator's paint excluded -- so the panels cannot drift from the mask the app serves.
    """
    sys.path.insert(0, os.path.join(_paths.TXM_REPO, "code"))
    sys.path.insert(0, os.path.join(_paths.TXM_REPO, "app", "core"))
    import store as S                                  # noqa: E402
    import model as M                                  # noqa: E402
    import pipeline as P                               # noqa: E402
    from txm_features import robust_normalize          # noqa: E402
    from skimage.morphology import remove_small_holes  # noqa: E402
    import tifffile                                    # noqa: E402

    tif = os.path.join(_paths.TXM_REPO, "images", BM.TXM_FIELD + ".tif")
    _paths.require(tif, f"TXM frame {BM.TXM_FIELD}", "TXM_REPO")
    stored = S.original_path(TXM_IID)
    if stored is None:
        raise SystemExit(
            f"the application's store has no entry {TXM_IID}.\n"
            f"  That entry holds the deployed model's cached SAM embedding for this "
            f"frame; without it this figure cannot show the transmission model.")
    raw = tifffile.imread(tif)
    if not np.array_equal(raw, tifffile.imread(stored)):
        raise SystemExit(
            "the TXM repository's TIFF and the copy in the application's store are not "
            "the same bytes, so the cached embedding does not belong to this frame.")

    #: What the model reads. `ingest` normalises 1-99% and hands THAT to the model; the
    #: destitched, flat-fielded array beside it is the human's view and the model never
    #: sees it. Recomputed here from the TIFF, then checked against the store's copy, so
    #: the chain starts at the image file rather than at a cached intermediate.
    img01 = robust_normalize(raw.astype(np.float64), 1.0, 99.0).astype(np.float32)
    kept = np.asarray(S.load_npy(TXM_IID, "img.npy"))
    if kept.shape != img01.shape or float(np.abs(kept - img01).max()) > 1e-6:
        raise SystemExit("recomputing the model's input from the TIFF does not reproduce "
                         "the array the application stored for it")

    embp = S.path(TXM_IID, "emb.npz")
    if not M.emb_is_current(embp):
        raise SystemExit(
            f"no usable SAM embedding cached at {embp}.\n"
            f"  The deployed model needs a 256-d ViT-H embedding at stride "
            f"{M.TILE_STRIDE}. Re-embedding would download the 2.4 GB encoder and this "
            f"figure will not do that silently. Run the application's ingest first.")
    coords, embs = M.read_emb(embp)

    mdl = P.get_model()
    prob = mdl.predict(img01, emb=(coords, embs))

    # The store's probability map is the one the application serves. Agreeing with it to
    # the bit is the check that this script loaded the deployed model and not a sibling.
    cached = S.load_npy(TXM_IID, "prob.npy")
    delta = None if cached is None else float(np.abs(np.asarray(cached) - prob).max())

    thr = P.DEFAULT_THRESHOLD
    over = prob > thr
    pruned = P.prune_specks(over)
    cleaned = remove_small_holes(
        pruned, **P._skimage_size_kw(remove_small_holes, P.FILL_HOLES_MAX_PX))
    final = P._narrow_to_image(TXM_IID, cleaned.copy(), True)

    shipped = P.effective_mask(TXM_IID, corrections="none", tight=True)
    if shipped is None or not np.array_equal(shipped, final):
        raise SystemExit("the staged chain does not reproduce effective_mask("
                         "corrections='none', tight=True), so the panels would show a "
                         "mask the application does not serve")

    corr = S.load_npy(TXM_IID, "correction.npy")
    corr = None if corr is None else np.asarray(corr)
    gate = next(r for r in json.load(open(TXM_GATE)) if r.get("stamp") == TXM_STAMP)
    return {"img": img01, "prob": prob, "over": over, "cleaned": cleaned, "final": final,
            "paint_crack": None if corr is None else (corr == 1),
            "paint_notcrack": None if corr is None else (corr == 2),
            "nm_per_px": BM.TXM_NM_PER_PX, "field": BM.TXM_FIELD,
            "describe": mdl.describe(), "threshold": float(thr),
            "min_blob_px": int(P.MIN_BLOB_PX), "fill_holes_px": int(P.FILL_HOLES_MAX_PX),
            "recipe": P.RECIPE, "prob_delta_vs_store": delta,
            "members": [os.path.basename(M.DEFAULT_17), os.path.basename(M.DEFAULT_HYBRID)],
            "gate": gate}


# ------------------------------------------------------------------ drawing helpers


def largest_removed(before, after, sl, painted=None, base=None):
    """Where to put one inset, and how big, by measurement only.

    `before & ~after` inside the window shown, labelled with 8-connectivity.

    WHICH PIECE IT LANDS ON, AND WHY THAT CHANGED. It used to be simply the biggest
    component. On this field that put both SEM insets on crumbs strung along a dark
    linear feature with surviving mask running straight through it -- the step eating a
    detection it otherwise kept, drawn twice as the illustration of what cleaning does.
    Two filters now apply, in this order, and both are measured rather than judged:

      1. the operator must not have painted the piece as crack; and
      2. the piece must be FREE-STANDING -- no surviving mask within ISOLATION_PX of
         it -- because dropping free-standing specks is what the step is for, while
         biting into a region it keeps is its side effect.

    THE SIDE EFFECT IS NOT DROPPED, IT MOVES TO THE RECORD. Every caller gets the
    window's removed-pixel total, how much of it the operator had painted crack, how
    many removed components there are, how many are free-standing, and how the removed
    AREA splits between free-standing pieces and pieces adjoining surviving mask. A
    reader who wants to know how much of this step is side effect reads it there. Where
    no piece passes both filters the rule relaxes -- first the isolation test, then the
    paint test -- and `chosen` says which rule actually placed the inset.

    Returns the piece's pixel count, the window totals above, the rule that chose it,
    and the square window to magnify.
    """
    gone = (before & ~after)[sl]
    lab, n = ndi.label(gone, np.ones((3, 3), bool))
    if not n:
        return None
    sz = np.bincount(lab.ravel())
    sz[0] = 0
    # FREE-STANDING, for every component at once and without a loop over 2,700 of them.
    # Dilate the whole removal set once and label the result: two removed pieces that
    # land in one blob are within reach of each other, and a blob that meets the
    # dilated kept mask is a bite rather than a speck.
    se = np.ones((2 * ISOLATION_PX + 1, 2 * ISOLATION_PX + 1), bool)
    blob, _nb = ndi.label(ndi.binary_dilation(gone, se), np.ones((3, 3), bool))
    pairs = np.unique(np.stack([lab[gone], blob[gone]]), axis=1)
    per_blob = np.bincount(pairs[1], minlength=blob.max() + 1)   # pieces in each blob
    crowded = np.zeros(sz.size, bool)
    crowded[pairs[0]] = per_blob[pairs[1]] > 1
    near = ndi.binary_dilation(after[sl], se)
    touch = np.bincount(lab[near].ravel(), minlength=sz.size)
    touch[0] = 0
    alone = (sz > 0) & (touch == 0) & ~crowded
    # painted or not, for every component at once
    painted_px, unpainted = None, (sz > 0)
    if painted is not None:
        pw = painted[sl]
        painted_px = int((gone & pw).sum())
        hit = np.bincount(lab[pw].ravel(), minlength=sz.size)
        hit[0] = 0
        unpainted = (sz > 0) & (hit == 0)

    # AND IT MUST NOT SIT IN A DARK FEATURE. Free-standing is about the MASK; this is
    # about the IMAGE. The piece can satisfy every mask test and still be a crumb at
    # the end of a dark streak, and that is what the inset kept showing: a reader sees
    # the step eating a crack whatever the mask says. Among the candidates, prefer one
    # whose own magnified window is no darker than the frame as a whole.
    med = float(np.median(base)) if base is not None else None

    def _window_of(idx):
        yy, xx = np.where(lab == idx)
        sp = max(int(yy.max() - yy.min()), int(xx.max() - xx.min())) + 1
        hh = sl[0].stop - sl[0].start
        sd = int(np.clip(INSET_SPAN * sp, INSET_MIN_PX, max(hh // 6, INSET_MIN_PX)))
        sd = min(max(sd, sp + 20), hh)
        cy0 = int(np.clip(int(round(yy.mean())) - sd // 2, 0, hh - sd)) + sl[0].start
        cx0 = int(np.clip(int(round(xx.mean())) - sd // 2, 0, hh - sd)) + sl[1].start
        return sd, cy0, cx0

    def _pick(ok):
        """Largest that also sits on ordinary matrix; largest outright if none does."""
        idx = np.flatnonzero(ok)
        if not idx.size:
            return None
        idx = idx[np.argsort(-sz[idx])]
        if med is not None:
            for i in idx[:25]:
                sd, y0, x0 = _window_of(int(i))
                if float(np.median(base[y0:y0 + sd, x0:x0 + sd])) >= med:
                    return int(i)
        return int(idx[0])

    for cand, why in ((unpainted & alone,
                       "the largest free-standing piece the step removes that the "
                       "operator did not paint as crack and whose magnified window is "
                       "no darker than the frame"),
                      (unpainted,
                       "the largest piece the step removes that the operator did not "
                       "paint as crack; no removed piece in this window is "
                       "free-standing"),
                      (sz > 0,
                       "the largest piece the step removes; none passes either "
                       "filter")):
        k = _pick(cand)
        if k is not None:
            chosen = why
            break
    ys, xs = np.where(lab == k)
    span = max(int(ys.max() - ys.min()), int(xs.max() - xs.min())) + 1
    H = sl[0].stop - sl[0].start
    side = int(np.clip(INSET_SPAN * span, INSET_MIN_PX, max(H // 6, INSET_MIN_PX)))
    side = min(max(side, span + 20), H)
    cy, cx = int(round(ys.mean())), int(round(xs.mean()))
    return {"comp_px": int(sz[k]), "window_px": int(gone.sum()), "side": side,
            "painted_crack_px": painted_px, "chosen": chosen,
            "n_components": int((sz > 0).sum()), "n_free_standing": int(alone.sum()),
            "free_standing_px": int(sz[alone].sum()),
            "adjoining_px": int(sz[(sz > 0) & ~alone].sum()),
            "isolation_px": ISOLATION_PX,
            "at": (int(np.clip(cy - side // 2, 0, H - side)) + sl[0].start,
                   int(np.clip(cx - side // 2, 0, H - side)) + sl[1].start)}


def tint(base, mask, colour):
    rgb = np.dstack([base] * 3)
    rgb[mask] = np.array(J.rgb(colour))
    return np.clip(rgb, 0, 1)


#: HOW A MICROGRAPH IS DRAWN, AND WHY IT IS TWO LAYERS AND NOT ONE.
#:
#: The author's PI read the transmission row of this plate and said it "looks very
#: pixelated". It did, and the cause is measurable rather than a matter of taste. The
#: transmission frame is 1688 x 1714 px against the electron frame's 4096 x 6144 -- 2.9
#: megapixels against 25.2 -- and the inset windows are MAGNIFIED: a 148 px window is
#: drawn into about 296 plate px, so one detector pixel becomes a 2 x 2 block at 600 dpi
#: and a bigger one again wherever a slide blows the plate up. Drawn with nearest
#: neighbour, every one of those blocks has a hard edge, and on transmission data, which
#: is smooth grey gradients rather than the electron row's high-contrast grain texture,
#: the blocks are the most conspicuous thing in the panel.
#:
#: THE PHOTOGRAPH IS RESAMPLED AND THE MASK IS NOT. These are different kinds of object
#: and they get different treatment:
#:
#:   the grey   is a photograph. Resampling it smoothly for display is what every
#:              viewer and every journal does, and it changes no measurement -- nothing
#:              in this paper is computed off the rendered plate.
#:   the masks  are the result. They keep nearest-neighbour, so no mask pixel is
#:              invented, softened or spread into a neighbour it never occupied. The
#:              module docstring's rule -- NO MASK IS EVER DILATED ANYWHERE IN THIS
#:              FIGURE -- is unchanged and is now enforced by construction rather than
#:              by every call remembering to pass the same keyword.
#:
#: Because the mask layer is drawn at the same extent with the same nearest-neighbour
#: sampling it had when it was burnt into the grey, the coloured pixels land on exactly
#: the output pixels they landed on before. CONTROL_mask_pixels_unchanged below renders
#: the plate both ways and checks that, so the claim is measured and not asserted.
GREY_INTERP = "bilinear"


def show(ax, base, *layers):
    """Draw a greyscale micrograph, then its mask overlays on top of it.

    `base` is a float image in 0..1. Each layer is (boolean mask, colour); later
    layers paint over earlier ones, which is the order the burnt-in version used.
    """
    ax.imshow(base, cmap="gray", vmin=0, vmax=1, interpolation=GREY_INTERP, zorder=1)
    for i, (mask, colour) in enumerate(layers):
        if mask is None or not mask.any():
            continue
        rgba = np.zeros(mask.shape + (4,), dtype=float)
        rgba[mask, :3] = np.array(J.rgb(colour))
        rgba[mask, 3] = 1.0
        ax.imshow(rgba, interpolation="nearest", zorder=2 + i)
    return ax


def boxed(ax, colour=J.G_DARK, lw=0.5):
    for s in ("top", "bottom", "left", "right"):
        ax.spines[s].set_visible(True)
        ax.spines[s].set_color(colour)
        ax.spines[s].set_linewidth(lw)
    ax.set_xticks([])
    ax.set_yticks([])


def bar(ax, nm_per_px, width_px, fontsize=J.TICK):
    """House-style scale bar whose white patch is sized to the LABEL, not to the bar.

    See the module docstring: at 18 mm a label is wider than any sensible bar, and
    `scalebar.scalebar` sizes its patch to the bar alone, so the label overhung the patch
    and was lost wherever the micrograph underneath was dark.
    """
    nm = SB.pick_length_nm(nm_per_px, width_px, target_frac=0.22)
    label = SB.fmt_nm(nm)
    fig = ax.figure
    rend = fig.canvas.get_renderer()
    probe = ax.text(0, 0, label, fontsize=fontsize)
    tw_in = probe.get_window_extent(renderer=rend).width / fig.dpi
    probe.remove()
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    DW, DH = abs(x1 - x0), abs(y1 - y0)
    ax_w = ax.get_position().width * fig.get_figwidth()
    ax_h = ax.get_position().height * fig.get_figheight()
    text_px = tw_in / ax_w * DW
    px = nm / nm_per_px
    th = fontsize / 72.0 / ax_h * DH                        # label height, data units
    inner = 0.30 * th
    bh = max(0.018 * DH, 1.0)
    boxw = max(px, text_px) + 2 * inner
    boxh = inner + bh + 0.55 * inner + th + 0.35 * inner
    bx = max(x0, x1) - 0.035 * DW - boxw
    by = max(y0, y1) - 0.035 * DH - boxh
    ax.add_patch(Rectangle((bx, by), boxw, boxh, facecolor="white", edgecolor="none",
                           zorder=20, clip_on=False))
    ax.add_patch(Rectangle((bx + (boxw - px) / 2.0, by + inner), px, bh,
                           facecolor="black", edgecolor="none", zorder=21, clip_on=False))
    ax.text(bx + boxw / 2.0, by + inner + bh + 0.55 * inner, label, fontsize=fontsize,
            ha="center", va="top", color="black", zorder=22, clip_on=False)
    return nm


def CONTROL_mask_pixels_unchanged():
    """Two-layer drawing must move no mask pixel. Rendered both ways and compared.

    The change this control guards is the one the PI's "very pixelated" note caused:
    the grey underneath a mask is now resampled smoothly instead of by nearest
    neighbour. That is a change to the PHOTOGRAPH. If it also moved, softened or
    spread the MASK, the plate would be reporting a different result, and the module
    docstring's promise that no mask is ever dilated here would be false.

    So: draw the same base and the same mask twice at the same axes geometry -- once
    burnt in with `tint` and nearest neighbour, which is what this file did before,
    once through `show` -- and require that the set of output pixels carrying the mask
    colour is IDENTICAL. Both a magnified case (an inset) and a minified one (a stage
    panel) are tested, because the two resample in opposite directions.
    """
    import io as _io
    import matplotlib.pyplot as _plt
    import matplotlib.image as _mpimg
    rng = np.random.default_rng(0)
    for name, src, out_in in (("magnified", 148, 0.50), ("minified", 879, 0.72)):
        base = rng.random((src, src))
        mask = np.zeros((src, src), bool)
        #: a shape with thin limbs and single-pixel specks, which is what a crack mask
        #: looks like and what a careless resample would eat first.
        yy, xx = np.mgrid[0:src, 0:src]
        mask[(np.abs(yy - xx) < max(1, src // 180))] = True
        mask[src // 3: src // 3 + 1, src // 4: 3 * src // 4] = True
        mask[rng.random((src, src)) > 0.999] = True
        got = {}
        for how in ("burnt", "layered"):
            fig = _plt.figure(figsize=(out_in, out_in), dpi=600)
            ax = fig.add_axes([0, 0, 1, 1])
            if how == "burnt":
                ax.imshow(tint(base, mask, J.MASK), interpolation="nearest")
            else:
                show(ax, base, (mask, J.MASK))
            ax.set_axis_off()
            buf = _io.BytesIO()
            fig.savefig(buf, dpi=600, facecolor="white")
            _plt.close(fig)
            buf.seek(0)
            px = _mpimg.imread(buf)[:, :, :3]
            hit = np.all(np.abs(px - np.array(J.rgb(J.MASK))) < 2.0 / 255.0, axis=-1)
            got[how] = hit
        a, b = got["burnt"], got["layered"]
        if a.shape != b.shape or not np.array_equal(a, b):
            d = int((a != b).sum()) if a.shape == b.shape else -1
            raise SystemExit(
                f"CONTROL_mask_pixels_unchanged FAILED ({name}): layering the mask over "
                f"a smoothly resampled grey moved {d} rendered mask pixels. The grey may "
                f"be resampled; the mask may not.")
        print(f"  CONTROL mask pixels unchanged, {name}: PASS "
              f"({int(a.sum()):,} mask px identical)")


def main():
    CONTROL_mask_pixels_unchanged()
    sem = BM.load("sem")
    txm = txm_arm()
    sem_nm, txm_nm = float(sem["nm_per_px"]), float(txm["nm_per_px"])

    # THE DETAIL WINDOWS. One rule, `mk_workflow.boundary_window`, applied to each arm's
    # OWN final mask -- for the transmission arm that is the trained model's mask, which
    # is the whole point of this revision.
    #
    # THE SIZE IS ONE FRACTION, NOT TWO CHOICES. The SEM window is the 90 um the
    # companion workflow figure records, so the two figures cut the same SEM crop; the
    # transmission window is the same fraction of ITS frame's shorter side, 52.1%. That
    # figure's 32 um for this field is 1094 px of a 1688 px frame -- 65%, so its "detail"
    # was very nearly the whole picture and the red box swallowed the field panel. Its
    # window was sized against the SEM darkness rule's sparse TXM mask; against the
    # trained model's, which marks 17.6% of this frame, the same fraction as the SEM arm
    # gives a window that is a magnification and still sits in the frame's interior.
    sy0, sx0, sH, _ = WF.detail_of(sem, "sem")
    ssl = (slice(sy0, sy0 + sH), slice(sx0, sx0 + sH))
    tH = int(round(sH / min(sem["img"].shape) * min(txm["img"].shape)))
    tH = min(tH, txm["img"].shape[0], txm["img"].shape[1])
    pc = txm["paint_crack"]
    ty0, tx0 = WF.boundary_window(txm["final"], tH,
                                  confirm=None if pc is None else (txm["final"] & pc))
    tsl = (slice(ty0, ty0 + tH), slice(tx0, tx0 + tH))

    sem_flat = ST.stretch(sem["flat"][ssl], sem["flat"])
    txm_base = ST.stretch(txm["img"][tsl], txm["img"])

    charts = [{
        "tag": "sem", "nm": sem_nm, "whole": sem["flat"], "field": sem["img"],
        "sl": ssl, "H": sH, "letters": "abcdef",
        #: THE ROW NAMES THE MICROSCOPY AND NOTHING ELSE, at the author's instruction.
        #: What each arm's detector IS belongs in the caption; a dash and a description
        #: on the title line is the same sub-line that was taken off the stage boxes.
        "title": "SEM",
        #: NO SUB-LINE. The author explains the model in the caption; the plate's job
        #: is the chain of arrays, and a second line of prose beside the title was
        #: competing with it.
        "sub": "",
        "stages": ["full field", "detail", "background\nremoved", "proposed",
                   "cleaned", "detected"],
        "panels": [("field", sem["img"], None),
                   ("grey", ST.stretch(sem["img"][ssl], sem["img"]), None),
                   ("grey", sem_flat, None),
                   ("mask", sem_flat, sem["proposed"]),
                   ("mask", sem_flat, sem["cleaned"]),
                   ("mask", sem_flat, sem["final"])],
        "ops": ["cut the\ndetail window",
                "subtract background,\nseven radii",
                "darker than\nmedian − 6 MAD",
                "drop specks,\nopen and close",
                ("keep regions the\nmodel calls crack"
                 if BM.DO.USE_REGION_CLASSIFIER else "keep regions\n≥ 40 px")],
        #: WHICH STEP IS THE LEARNED ONE. The author asked whether a reader of this
        #: plate can tell a model is employed at all. The words were there -- "keep
        #: regions the model calls crack" -- in the same grey as the four hand-written
        #: rules beside it, so five operations read as five rules and the one trained
        #: stage did not stand out. It is now set in the arm's own colour and in bold,
        #: and says "trained", so the learned step is visible at a glance rather than
        #: only to someone reading every label.
        "insets": {3: (sem["proposed"], sem["cleaned"], "proposed", "cleaned"),
                   4: (sem["cleaned"], sem["final"], "cleaned", "detected")},
        "painted": sem.get("paint_crack"),
    }, {
        "tag": "txm", "nm": txm_nm, "whole": txm["img"], "field": txm["img"],
        "sl": tsl, "H": tH, "letters": "ghijkl",
        "title": "TXM",
        "sub": "",
        "stages": ["full field", "detail", "crack\nprobability", "thresholded",
                   "cleaned", "detected"],
        "panels": [("field", txm["img"], None),
                   ("grey", txm_base, None),
                   ("prob", txm["prob"][tsl], None),
                   ("mask", txm_base, txm["over"]),
                   ("mask", txm_base, txm["cleaned"]),
                   ("mask", txm_base, txm["final"])],
        "ops": ["cut the\ndetail window",
                "17 channels + SAM,\nmean of two models",
                f"threshold {txm['threshold']:.2f}",
                #: "blobs" was the implementation's word for what this removes. The
                #: things it removes are imaging artefacts, and that is what a reader
                #: of the figure needs to be told.
                "drop imaging\nartifacts, fill holes",
                "narrow to the\nmeasured width"],
        "insets": {3: (txm["over"], txm["cleaned"], "thresholded", "cleaned"),
                   4: (txm["cleaned"], txm["final"], "cleaned", "detected")},
        "painted": txm["paint_crack"],
    }]

    # ---- geometry ------------------------------------------------------------------
    W, MX, NCOL, GAP = J.PAGEW, 0.05, 6, 0.40
    AVAIL = W - 2 * MX
    IMW = (AVAIL - (NCOL - 1) * GAP) / NCOL
    PITCH = IMW + GAP
    LINE = J.TICK / 72.0 * 1.22                     # one line of body text, inches

    HEAD, STAGEH, OPH = 0.235, 0.30, 2 * LINE + 0.07
    INSW = min(0.50, (PITCH - 0.11) / 2.0)
    INSH = INSW + 0.03 + LINE + 0.04 + 3 * LINE + 0.04
    CHARTH = HEAD + STAGEH + IMW + OPH + INSH
    TOP, CHARTGAP, LEGH, BOT = 0.05, 0.17, 0.33, 0.05
    Htot = TOP + 2 * CHARTH + CHARTGAP + LEGH + BOT

    fig = plt.figure(figsize=(W, Htot))
    guard = []

    def ax_at(xin, yin, win, hin):
        return fig.add_axes([xin / W, 1.0 - (yin + hin) / Htot, win / W, hin / Htot])

    def txt(xin, yin, s, maxw=None, **kw):
        kw.setdefault("fontsize", J.TICK)
        kw.setdefault("color", J.INK)
        t = fig.text(xin / W, 1.0 - yin / Htot, s, **kw)
        guard.append((t, maxw))
        return t

    xs = [MX + i * PITCH for i in range(NCOL)]
    rec = {}

    for ci, ch in enumerate(charts):
        top = TOP + ci * (CHARTH + CHARTGAP)
        sl, H, nm = ch["sl"], ch["H"], ch["nm"]
        y0w, x0w = sl[0].start, sl[1].start
        ytop = top + HEAD + STAGEH

        fig.add_artist(plt.Line2D([MX / W, (W - MX) / W], [1.0 - top / Htot] * 2,
                                  transform=fig.transFigure, color=J.INK, lw=0.9))
        txt(MX, top + 0.15, ch["title"], maxw=2.9, fontsize=J.LABEL,
            fontweight="bold", ha="left", va="baseline")
        if ch["sub"]:
            txt(W - MX, top + 0.15, ch["sub"], maxw=AVAIL - 3.0, ha="right",
                va="baseline", color=J.G_DARK)
        for c, name in enumerate(ch["stages"]):
            txt(xs[c] + IMW / 2.0, ytop - 0.045, name, maxw=PITCH - 0.06,
                fontweight="bold", ha="center", va="bottom", linespacing=1.15)

        # WHERE THE MAGNIFIED WINDOWS ARE, computed before the panels are drawn: a
        # marker that lands under the panel letter is a marker a reader cannot see, and
        # the letter is the thing that can move. Which corner it ends up in is recorded
        # in the caption JSON rather than left as an unexplained inconsistency.
        marks, corners = {}, {}
        for c, (before, after, _nb, _na) in ch["insets"].items():
            got = largest_removed(before, after, sl, painted=ch.get("painted"),
                                  base=ch["whole"])
            marks[c] = got
            if got is None:
                continue
            fx = (got["at"][1] - x0w) / H
            fy = (got["at"][0] - y0w) / H
            fs = got["side"] / H
            hits_left = fx < 0.30 and fy < 0.26
            corners[c] = "right" if hits_left and fx + fs < 0.70 else "left"

        # ---- the stage panels ------------------------------------------------------
        axes = []
        for c, (kind, arr, mask) in enumerate(ch["panels"]):
            if kind == "field":
                step = max(1, arr.shape[1] // 1400)
                thumb = ST.stretch(arr[::step, ::step], arr)
                fw, fh = IMW, IMW * thumb.shape[0] / thumb.shape[1]
                if fh > IMW:
                    fh, fw = IMW, IMW * thumb.shape[1] / thumb.shape[0]
                ax = ax_at(xs[c] + (IMW - fw) / 2.0, ytop + (IMW - fh) / 2.0, fw, fh)
                show(ax, thumb)
                ax.add_patch(Rectangle((x0w / step, y0w / step), H / step, H / step,
                                       fill=False, edgecolor=J.ROI, linewidth=1.0,
                                       zorder=20))
                bar(ax, nm * step, thumb.shape[1])
            else:
                ax = ax_at(xs[c], ytop, IMW, IMW)
                if kind == "prob":
                    #: a probability map is continuous data, not a mask, so it is
                    #: resampled like the photograph it is derived from.
                    ax.imshow(arr, cmap=PROB_CMAP, vmin=0, vmax=1,
                              interpolation=GREY_INTERP)
                elif kind == "mask":
                    show(ax, arr, (mask[sl], J.MASK))
                else:
                    show(ax, arr)
                if c == 1:
                    ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                                           fill=False, edgecolor=J.ROI, linewidth=1.0,
                                           zorder=30))
                    bar(ax, nm, H)
            boxed(ax)
            if corners.get(c) == "right":
                ax.text(0.98, 0.98, f"({ch['letters'][c]})", transform=ax.transAxes,
                        fontsize=J.PANEL, fontweight="bold", va="top", ha="right",
                        color=J.INK, bbox=dict(facecolor="white", edgecolor="none",
                                               boxstyle="square,pad=0.22"))
            else:
                J.panel_label(ax, ch["letters"][c], inside=True)
            axes.append(ax)

        # ---- the arrows, each carrying its operation --------------------------------
        ymid = 1.0 - (ytop + IMW / 2.0) / Htot
        for c in range(NCOL - 1):
            xa, xb = xs[c] + IMW, xs[c + 1]
            fig.add_artist(FancyArrowPatch(
                ((xa + 0.045) / W, ymid), ((xb - 0.025) / W, ymid),
                transform=fig.transFigure, arrowstyle="-|>", mutation_scale=7,
                lw=1.0, color=J.INK, zorder=1))
            txt((xa + xb) / 2.0, ytop + IMW + 0.055, ch["ops"][c], maxw=PITCH - 0.03,
                ha="center", va="top", linespacing=1.22, color=J.G_DARK)

        # ---- what each cleaning step removes, magnified ------------------------------
        yins = ytop + IMW + OPH
        steps = {}
        for c, (before, after, nb, na) in sorted(ch["insets"].items()):
            got = marks[c]
            xc = (xs[c] + IMW + xs[c + 1]) / 2.0
            if got is None:
                txt(xc, yins + 0.1, "this step removes nothing\ninside the window shown",
                    maxw=PITCH, ha="center", va="top", style="italic", color=J.G_MID)
                continue
            s, (iy, ix) = got["side"], got["at"]
            isl = (slice(iy, iy + s), slice(ix, ix + s))
            cut = ST.stretch(ch["whole"][isl], ch["whole"])
            for k in (0, 1):
                xl = xc - INSW - 0.025 + k * (INSW + 0.05)
                ax = ax_at(xl, yins, INSW, INSW)
                #: the removed pixels paint over the kept mask, which is the order
                #: the burnt-in version applied them in.
                show(ax, cut, ((before if k == 0 else after)[isl], J.MASK),
                     ((before & ~after)[isl] if k == 0 else None, J.ACCENT2))
                boxed(ax, colour=J.ROI if k == 0 else J.G_DARK, lw=0.9 if k == 0 else 0.5)
                txt(xl + INSW / 2.0, yins + INSW + 0.03, "before" if k == 0 else "after",
                    maxw=INSW + 0.04, ha="center", va="top", fontstyle="italic",
                    color=J.G_DARK)
            pad = 0.012 * H
            axes[c].add_patch(Rectangle((ix - x0w - pad, iy - y0w - pad),
                                        s + 2 * pad, s + 2 * pad, fill=False,
                                        edgecolor="white", linewidth=1.4, zorder=24))
            axes[c].add_patch(Rectangle((ix - x0w, iy - y0w), s, s, fill=False,
                                        edgecolor=J.ROI, linewidth=0.9, zorder=25))
            mag = (INSW / s) / (IMW / H)
            txt(xc, yins + INSW + 0.03 + LINE + 0.04,
                f"×{mag:.0f}",
                maxw=PITCH - 0.02, ha="center", va="top", linespacing=1.22)
            steps[f"{nb}_to_{na}"] = {
                "inset_at": [int(iy), int(ix)], "inset_side_px": int(s),
                "inset_um": round(s * nm / 1000.0, 3), "magnification": round(mag, 1),
                "largest_removed_component_px": got["comp_px"],
                "inset_placed_on": got["chosen"],
                "removed_in_window_px": got["window_px"],
                "removed_in_window_painted_crack_px": got["painted_crack_px"],
                "removed_components": got["n_components"],
                "removed_components_free_standing": got["n_free_standing"],
                "removed_px_free_standing": got["free_standing_px"],
                "removed_px_adjoining_kept_mask": got["adjoining_px"],
                "free_standing_means_no_kept_mask_within_px": got["isolation_px"],
                "removed_in_frame_px": int((before & ~after).sum()),
                "added_in_frame_px": int((after & ~before).sum()),
                "panel_letter_corner": corners.get(c, "left")}


        rec[ch["tag"]] = {
            "field": str(sem["field"]) if ch["tag"] == "sem" else txm["field"],
            "nm_per_px": nm, "scale_source": (BM.SEM_SCALE_SOURCE if ch["tag"] == "sem"
                                              else BM.TXM_SCALE_SOURCE),
            "frame_px": [int(ch["field"].shape[0]), int(ch["field"].shape[1])],
            "detail_px": int(H), "detail_um": round(H * nm / 1000.0, 2),
            "detail_at": [int(y0w), int(x0w)],
            "stages": [s.replace("\n", " ") for s in ch["stages"]],
            "operations": [o.replace("\n", " ") for o in ch["ops"]],
            "cleaning_steps": steps}

    # ---- the key, so the plate reads with no caption ---------------------------------
    ky = TOP + 2 * CHARTH + CHARTGAP + 0.09
    cells = [("swatch", J.MASK, "crack found at this stage"),
             ("swatch", J.ACCENT2, "pixels this step removes"),
             ("box", J.ROI, "window magnified below"),
             ("ramp", None, "crack probability, 0 to 1")]
    for i, (kind, colour, label) in enumerate(cells):
        cx = MX + i * (AVAIL / len(cells))
        ax = ax_at(cx, ky, 0.095, 0.085)
        if kind == "ramp":
            ax.imshow(np.linspace(0, 1, 64)[None, :], cmap=PROB_CMAP, aspect="auto",
                      vmin=0, vmax=1)
            boxed(ax, colour=J.G_DARK, lw=0.5)
        elif kind == "box":
            ax.imshow(np.ones((4, 4, 3)), interpolation="nearest")
            boxed(ax, colour=colour, lw=1.1)
        else:
            ax.imshow(np.array(J.rgb(colour), dtype=float)[None, None, :],
                      interpolation="nearest")
            boxed(ax, colour=J.G_DARK, lw=0.4)
        txt(cx + 0.14, ky + 0.065, label, maxw=AVAIL / len(cells) - 0.19, ha="left",
            va="baseline")

    # ---- nothing may overflow the box it was given, and the check says which ---------
    rend = fig.canvas.get_renderer()
    bad = []
    for t, maxw in guard:
        bb = t.get_window_extent(renderer=rend)
        w = bb.width / fig.dpi
        if maxw is not None and w > maxw + 0.004:
            bad.append(f"  {w:.2f} in > {maxw:.2f} in: {t.get_text()!r}")
        if bb.x0 / fig.dpi < -0.004 or bb.x1 / fig.dpi > W + 0.004:
            bad.append(f"  runs off the page: {t.get_text()!r}")
    if bad:
        raise SystemExit("mk_flow: text does not fit the layout --\n" + "\n".join(bad))

    J.save(fig, os.path.join(OUT, NAME + ".png"))

    g = txm["gate"]["heldout"]
    cap = {
        "figure": NAME + ".png",
        "what": "two flow charts, one per microscopy: the named array at each stage in a "
                "box, the operation that produces it written on the arrow into it, and "
                "an inset pair magnifying what each cleaning step removes",
        "the_two_arms_are_different_detectors": {
            "sem": (("a robust darkness cut over seven flattening radii, then an "
                     "8-feature logistic region classifier: detect_one.py keeps the "
                     "regions it calls crack and drops the rest, so fitted weights DO "
                     "reach this mask. Candidate constants mad_k=%g, clean_min_px=%d, "
                     "min_area_px=%d; scale ladder %s"
                     % (BM.MAD_K, BM.CLEAN_MIN_PX, BM.MIN_AREA_PX,
                        list(BM.DO.SCALE_LADDER)))
                    if BM.DO.USE_REGION_CLASSIFIER else
                    ("a threshold rule whose output no fitted weight reaches. A trained "
                     "8-feature classifier is loaded and scores every region, but "
                     "USE_REGION_CLASSIFIER is False so detect_one.py keeps all of them: "
                     "multiscale background subtraction then a robust darkness cut. "
                     "Constants mad_k=%g, clean_min_px=%d, min_area_px=%d; scale ladder %s"
                     % (BM.MAD_K, BM.CLEAN_MIN_PX, BM.MIN_AREA_PX,
                        list(BM.DO.SCALE_LADDER)))),
            "txm": "%s; recipe %s, threshold %.2f, speck floor %d px, hole cap %d px, "
                   "then tighten_to_image and clip_to_measured_width"
                   % (txm["describe"], txm["recipe"], txm["threshold"],
                      txm["min_blob_px"], txm["fill_holes_px"]),
            "what_was_wrong_before": "the previous version of this figure applied "
                                     "both_modalities.stages -- the SEM darkness rule -- "
                                     "to the transmission frame as well, so its lower "
                                     "row showed the SEM detector run on TXM and not the "
                                     "model the application ships for TXM",
        },
        "txm_model": {
            "members": txm["members"],
            "loaded_through": "app/core/pipeline.get_model(), from the store's model "
                              "registry; the SAM ViT-H embedding is the one cached in "
                              "the store, so the encoder is not re-run",
            "live_probability_matches_the_stored_prediction_to": txm["prob_delta_vs_store"],
            "mask_is": "effective_mask(corrections='none', tight=True) -- the model's "
                       "own output, with the operator's paint excluded",
            "held_out_score": {
                "convention": "%d-fold cross-validation grouped by %s over %d labelled "
                              "frames; %s" % (g["k"], g["grouped_by"],
                                              g["labelled_images_used"], g["label_source"]),
                "mean_iou": g["mean_iou"], "std_iou": g["std_iou"],
                "worst_fold_iou": g["min_iou"], "mean_precision": g["mean_precision"],
                "mean_recall": g["mean_recall"],
                "read_from": os.path.relpath(TXM_GATE, _paths.TXM_REPO)
                             + f", stamp {TXM_STAMP}, recipe {txm['recipe']}",
                "note": "docs/figures/txm_model_scores.json carries 0.7921 for the v4 "
                        "members and states that no v5 grouped-CV artefact exists in "
                        "either repository. It does -- the gate record quoted here -- "
                        "and the deployed joblibs are the v5 pair.",
            },
        },
        "display": "median +/- 3 robust standard deviations taken over the WHOLE frame "
                   "and applied to the windows cut from it, so a window is the field "
                   "magnified and not a differently rendered picture. Both detectors ran "
                   "on the unstretched arrays and every mask shown is that run.",
        "mask_panels_sit_on": {
            "sem": "the flattened array the darkness criterion was applied to",
            "txm": "the 1-99% normalised frame the model reads. The destitched, "
                   "flat-fielded array is a display view the model never sees and no "
                   "panel here is drawn over it; the transmission arm has no "
                   "background-subtraction stage at all.",
        },
        "panel_letters": "house style puts the letter inside the top-left corner of a "
                         "micrograph; on a panel where the magnified window would sit "
                         "under it the letter moves to the top-right instead, and the "
                         "corner used is recorded with that step below",
        "insets": "each is placed on a connected component (8-connectivity) of "
                  "before & ~after INSIDE the window shown -- the LARGEST such component "
                  "that the operator did not paint as crack, so the inset illustrates "
                  "what the step is for rather than what it costs. The cost is here "
                  "instead: per inset, removed_in_window_painted_crack_px against "
                  "removed_in_window_px, and inset_placed_on names the rule that chose "
                  "the piece, including the fallback used where every piece a step "
                  "removes overlaps painted crack. The window is six times the "
                  "component's longest side, magnified by nearest neighbour. No mask "
                  "is dilated anywhere in this figure.",
        "detail_window_rule": "mk_workflow.boundary_window applied to each arm's OWN "
                              "final mask. The SEM window is the %g um the companion "
                              "workflow figure records, and the transmission window is "
                              "the same fraction of its frame's shorter side (%.1f%%), "
                              "not that figure's %g um -- which, against the trained "
                              "model's mask, would have been 65%% of the frame"
                              % (WF.DETAIL_UM["sem"],
                                 100.0 * sH / min(sem["img"].shape),
                                 WF.DETAIL_UM["txm"]),
        "arms": rec,
    }
    if txm["paint_crack"] is not None:
        cr, nc = txm["paint_crack"], txm["paint_notcrack"]
        ref, out = int(cr.sum()), {}
        for key, m in (("trained TXM model (shown here)", txm["final"]),
                       ("SEM darkness rule (what this row used to show)",
                        BM.load("txm")["final"])):
            tp, fp = int((m & cr).sum()), int((m & nc).sum())
            out[key] = {"iou": round(tp / max(tp + fp + ref - tp, 1), 4),
                        "recall": round(tp / max(ref, 1), 4),
                        "precision": round(tp / max(tp + fp, 1), 4)}
        cap["txm_model"]["on_this_frame_in_sample"] = {
            "warning": "this frame is one of the 71 the model was fitted on, so these "
                       "are in-sample and the held-out score above is the one to quote",
            "referee": "the operator's correction for this frame in the application's "
                       "store; refereed pixels only",
            "refereed_px": {"crack": ref, "not_crack": int(nc.sum())},
            "scores": out}
    json.dump(cap, open(os.path.join(OUT, NAME + ".caption.json"), "w"), indent=1)

    print(f"  SEM  detail {sH} px ({sH * sem_nm / 1000:.0f} um) at ({sy0}, {sx0})")
    print(f"  TXM  detail {tH} px ({tH * txm_nm / 1000:.0f} um) at ({ty0}, {tx0})")
    print(f"  TXM  {txm['describe']}, {' + '.join(txm['members'])}")
    print(f"  TXM  held-out IoU {g['mean_iou']:.4f} +/- {g['std_iou']:.4f} "
          f"(worst fold {g['min_iou']:.4f}; {g['k']}-fold grouped by {g['grouped_by']} "
          f"over {g['labelled_images_used']} frames), and the live probability map "
          f"matches the stored one to {txm['prob_delta_vs_store']}")
    for k, v in cap["txm_model"].get("on_this_frame_in_sample", {}).get(
            "scores", {}).items():
        print(f"       on this frame, IN SAMPLE  {k:<46} IoU {v['iou']:.4f}  "
              f"recall {v['recall']:.4f}  precision {v['precision']:.4f}")
    for tag in ("sem", "txm"):
        for k, v in rec[tag]["cleaning_steps"].items():
            print(f"  {tag.upper()}  {k:<24} frame −{v['removed_in_frame_px']:>8,} "
                  f"+{v['added_in_frame_px']:>8,} px; inset x{v['magnification']:.0f} "
                  f"on its biggest {v['largest_removed_component_px']:,} px piece")


if __name__ == "__main__":
    main()
