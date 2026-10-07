"""Paper figure: a published model's class list does not tell you which channel transfers.

THE RESULT IS THE ORDERING OF THE FIVE CHANNELS. The only published segmentation model for
SEM of an additively manufactured metal that ships weights emits five named phases, one of
which is Void. Void is what a reader picks for cracks from the class list, and it is the
channel that scores ZERO. The signal is in Carbide, which has no semantic relation to a
crack. So a channel cannot be chosen by name; it has to be measured.

PANEL B IS ABOUT THE DIFFERENCE BETWEEN A MEDIAN AND A PAIRED GAIN. Choosing the channel per
tile against the label raises the MEDIAN from 0.1914 to 0.2656, and that 0.0742 is what a
transfer table would report. The paired picture is not that: the fixed channel is already the
best of the five on 10 of the 15 tiles, so the median PAIRED difference is 0.0000 and the
whole effect lives in the other 5.

WHAT THIS FIGURE NO LONGER CLAIMS. Two earlier versions used micro-sam as a control for the
channel effect and both were wrong. The first unioned every proposal the label touches and
called it a best-instance oracle and an upper bound; the second took the genuinely best
single proposal and reported the two selection gains as being of a size. Neither works,
because micro-sam's unsupervised darkness rule is itself a UNION of proposals, and no
single-proposal quantity bounds a union: the best single proposal is BELOW the darkness rule
on 7 of the 15 tiles, at Wilcoxon p = 0.71. A selection oracle has to match the arity of the
rule it is differenced against. The three micro-sam rows are therefore drawn as what they
are, with no gain bracket and no claim that they parallel the channel effect.

Both arms run at a FIXED operating point with no leave-one-frame-out selection, so no number
here is comparable to Figure 3. The yardstick is the 3 px-trace ceiling of section 4.5, which
is a property of the labels and of neither arm.

EVERY STRING IS WIDTH-CHECKED BEFORE IT IS DRAWN, and every value range-checked. The first
version put its value labels to the right of the bars, where they ran under the second
panel's row labels and off the edge, and 0.1914 shipped as "0." followed by nothing; the
second shared the bars' clipping helper with the per-tile dot strip and drew 7 of 75 dots at
values they did not have. text() and bar_x() refuse instead.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
import json
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = _paths.FIG_DIR
st = json.load(open(os.path.join(HERE, "transfer_bench.json")))
A, M_, CEIL = st["imranlabs"], st["microsam"], st["iou_ceiling_3px"]
U, MU, MB = (st["selection"]["unet_channel"],
             st["selection"]["microsam_union"],
             st["selection"]["microsam_best_single"])
NT = st["n_tiles"]

#: Smallest type drawn, in pixels OF THE SAVED PNG. Nothing here is resized after drawing,
#: so this is simply the smallest font below. mkpdf enforces min_px * (487 pt / W) >= 6 pt,
#: i.e. W <= 81.21 * MIN_PX; at 1800 x 26 the plate sets 7.04 pt.
MIN_PX = 26
W, H = 1800, 1195
XMAX = 0.30                      # ONE axis for both panels, so the two are comparable.

INK, MUT, RULE = (24, 24, 26), (98, 98, 104), (214, 214, 210)
C_DEAD = (150, 152, 158)
C_LIVE = (38, 102, 190)
C_ORACLE = (196, 42, 42)
C_SEM = (214, 126, 20)
C_WEAK = (232, 150, 150)   # label-informed and still bad

def font(sz, b=False):
    p = ("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if b
         else "/System/Library/Fonts/Supplemental/Arial.ttf")
    try: return ImageFont.truetype(p, sz)
    except Exception: return ImageFont.load_default()
F_T, F_H, F_L, F_V, F_S = font(44, True), font(30, True), font(27), font(27, True), font(26)

img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
def tw(s, f): return d.textlength(s, font=f)

def text(xy, s, f, fill, limit=W - 12, why=""):
    """Draw, after refusing anything that would not fit inside `limit`."""
    end = xy[0] + tw(s, f)
    if end > limit:
        raise SystemExit(
            f"mk_transfer: {s!r} ends at x={end:.0f} but its zone stops at {limit} "
            f"({why}). Shorten the string or widen the zone -- do not ship a truncated "
            f"number.")
    d.text(xy, s, font=f, fill=fill)

text((44, 28), "What a published model's class list does not tell you", F_T, INK,
     why="title")

#: Two panels with explicit label / bar / value zones that nothing may cross. The BAR SPAN
#: IS IDENTICAL IN BOTH (340 px for 0.30 IoU): a shared axis is worthless if the same value
#: draws a different length on the left than on the right, and 0.1914 appears in both.
BAR = 340
PA = dict(x0=44,  lab=286, b0=292,  b1=292 + BAR,  val=646,  end=806)
PB = dict(x0=870, lab=1256, b0=1262, b1=1262 + BAR, val=1616, end=1792)
YA = [196, 288, 380, 472, 564]
YB_HEAD, YB_BAR = [196, 452], [262, 366, 518, 622, 714]
YBOT = 760

def xpos(p, v):
    """Position for a value. Clips, and the caller must know when it did.

    The first version of this returned min(v, XMAX) silently and was used for the per-tile
    dots as well as the bars, so seven tiles were drawn at values they did not have and five
    of Carbide's collapsed onto the 0.30 tick -- while the caption promised the distribution.
    Bars are asserted never to clip; dots are drawn as carets when they do, and counted.
    """
    return p["b0"] + BAR * min(v, XMAX) / XMAX

OFFSCALE = []            #: per-tile values that did not fit, so the footer can say so

def bar_x(p, v):
    if v > XMAX:
        raise SystemExit(f"mk_transfer: a BAR of {v:.4f} exceeds the axis maximum {XMAX}. "
                         f"Raise XMAX -- a clipped bar misstates the value it draws.")
    return xpos(p, v)

def axis(p):
    for t in (0.0, 0.1, 0.2, 0.3):
        x = xpos(p, t)
        d.line([(x, 156), (x, YBOT)], fill=RULE, width=2)
        d.text((x - tw(f"{t:.1f}", F_S) / 2, YBOT + 12), f"{t:.1f}", font=F_S, fill=MUT)
    xc = xpos(p, CEIL)
    for yy in range(156, YBOT, 16):
        d.line([(xc, yy), (xc, yy + 9)], fill=(120, 120, 126), width=3)

def row(p, y, label, val, col, tiles=None, indent=0):
    n_off = [0]
    text((p["x0"] + indent, y - 14), label, F_L, INK, p["lab"], "row label")
    x1 = bar_x(p, val)
    if val > 0:
        d.rounded_rectangle([p["b0"], y - 17, max(x1, p["b0"] + 5), y + 17], 5, fill=col)
    else:
        d.line([(p["b0"], y - 19), (p["b0"], y + 19)], fill=col, width=5)
    if tiles:
        for t in tiles:
            if t > XMAX:
                OFFSCALE.append(t)
                #: stepped, because five carets at one x read as a single caret
                xe = p["b1"] + 6 + 11 * n_off[0]
                n_off[0] += 1
                d.polygon([(xe, y + 20), (xe, y + 30), (xe + 9, y + 25)], fill=(70, 70, 76))
                continue
            tx = xpos(p, t)
            d.ellipse([tx - 4, y + 21, tx + 4, y + 29], fill=(70, 70, 76))
    text((p["val"], y - 14), f"{val:.4f}", F_V, col, p["end"], "value label")

# ---- panel A: the five channels -------------------------------------------------------
text((PA["x0"], 112), "A   Its five output channels, scored on the crack labels", F_H, INK,
     PB["x0"] - 10, "panel A head")
axis(PA)
order = sorted(A["per_channel_median_IoU"], key=lambda c: -A["per_channel_median_IoU"][c])
for i, c in enumerate(order):
    v = A["per_channel_median_IoU"][c]
    col = (C_LIVE if c == A["fixed_channel"]
           else C_SEM if c == A["semantic_channel"] else C_DEAD)
    row(PA, YA[i], "Dilution zone" if c == "DilutionZone" else c, v, col,
        A["per_channel_per_tile"][c])

# ---- panel B: what the label buys -----------------------------------------------------
text((PB["x0"], 112), "B   What choosing against the label buys", F_H, INK,
     W - 24, "panel B head")
axis(PB)
text((PB["x0"], YB_HEAD[0] - 14), "SEM/AM U-Net, choosing a channel", F_V, INK, PB["end"],
     "group head")
row(PB, YB_BAR[0], "one fixed channel", A["fixed_median"], C_LIVE, indent=26)
row(PB, YB_BAR[1], "chosen per tile", A["oracle_median"], C_ORACLE, indent=26)
text((PB["x0"], YB_HEAD[1] - 14), "micro-sam, choosing proposals", F_V, INK, PB["end"],
     "group head")
row(PB, YB_BAR[2], "darkness rule", M_["median_IoU"], C_LIVE, indent=26)
row(PB, YB_BAR[3], "label-touching, unioned", M_["median_IoU_union_touching"], C_ORACLE,
    indent=26)
row(PB, YB_BAR[4], "best single proposal", M_["median_IoU_best_instance"], C_WEAK, indent=26)

# ONE bracket, on the one pair where the comparison is sound. The micro-sam rows get none:
# its unsupervised arm is a union of proposals, so neither a pick-one oracle nor a
# union-of-touching rule is a bound on it, and drawing a gain there would assert a parallel
# that the paired numbers refuse.
_gy = (YB_BAR[0] + YB_BAR[1]) // 2
text((PB["b0"] + 10, _gy - 13),
     f"+{U['difference_of_medians']:.4f} on the median", F_V, C_ORACLE, PB["val"] - 10,
     "gain label")
d.line([(xpos(PB, A["fixed_median"]), _gy + 22),
        (xpos(PB, A["oracle_median"]), _gy + 22)], fill=C_ORACLE, width=4)
for _x in (xpos(PB, A["fixed_median"]), xpos(PB, A["oracle_median"])):
    d.line([(_x, _gy + 14), (_x, _gy + 30)], fill=C_ORACLE, width=4)

# ---- footers, below both panels -------------------------------------------------------
FY = YBOT + 58
for i, s_ in enumerate([
    f"Dashed rule: IoU {CEIL:.4f}, what a geometrically correct 3 px trace earns against "
    f"these labels. Dots in A are the {NT} tiles.",
    f"Orange is the channel the class list names for voids: 0.0000 to four decimals on "
    f"{A['void_exactly_zero_tiles']} of {NT} tiles. Blue is the one that transfers, best of "
    f"five on {A['fixed_channel_best_on_tiles']} of {NT}.",
    f"The bracket is a difference of MEDIANS. Per tile the chosen channel ties the fixed one",
    f"on {NT - U['n_strictly_greater']} of {NT} tiles, so the paired median is "
    f"{U['median_paired_difference']:+.4f} and the gain sits in the other "
    f"{U['n_strictly_greater']}.",
    f"micro-sam gets no bracket: its darkness rule is itself a union of proposals, so the best",
    f"single proposal does not bound it \u2014 it is lower on {MB['n_b_below_a']} of {NT} "
    f"tiles (p={MB['wilcoxon_p']}).",
    f"Both arms run at a fixed operating point with no leave-one-frame-out selection, so no "
    f"value here is comparable to Figure 3.",
    (f"Carets at the right edge of A are {len(OFFSCALE)} tiles beyond the axis, up to "
     f"{max(OFFSCALE):.4f}; the axis is held at {XMAX:.2f} so both panels share one scale."
     if OFFSCALE else f"Every tile value in A falls inside the {XMAX:.2f} axis."),
]):
    text((PA["x0"], FY + i * 38), s_, F_S, MUT, W - 24, f"footer {i}")

p_ = os.path.join(OUT, "4 - transfer, the class list does not say.png")
os.makedirs(OUT, exist_ok=True)
img.save(p_)

CAPTION = {
 "min_px": MIN_PX,
 "lead": ("The only published segmentation model for SEM of an additively manufactured metal "
          "that ships weights, transferred to these crack labels: the channel its own class "
          "list names for voids scores zero, the channel that carries the signal is the one "
          "named for a carbide phase, and letting the label pick the channel buys IoU no user "
          "can have."),
 "panel_key": (
     f"**A** The model's five output channels, each scored as a crack mask against the same "
     f"{NT} hand-labelled tiles from 9 SEM frames, median per-tile IoU, dots the {NT} tiles. "
     f"**Void** (orange) is what its class list offers for a crack-like feature and is the "
     f"lowest of the five at {A['semantic_median']:.4f}, 0.0000 to four decimals on "
     f"{A['void_exactly_zero_tiles']} of {NT} tiles. **Carbide** (blue) leads at "
     f"{A['fixed_median']:.4f}, best of the five on {A['fixed_channel_best_on_tiles']} of "
     f"{NT} tiles, and is the only one of the five to clear the dashed rule at IoU "
     f"{CEIL:.4f}, what a geometrically correct 3 px trace earns against these labels. "
     f"**B** The same arms with and without a selection step that consults the label, on two "
     f"different things: which of five output channels, and which of a median "
     f"{M_['median_instances']:.0f} class-agnostic proposals. Both gain a similar amount. "
     f"Pink is a third, label-informed rule that is nonetheless worse than the best single "
     f"proposal. Both arms run at a fixed operating point with no leave-one-frame-out "
     f"selection, so no value here is comparable to Figure 3."),
 "extended": [
  ["A class name is not evidence of transfer.",
   f"Scored on identical data, the five channels order Carbide {A['fixed_median']:.4f}, "
   f"Matrix {A['per_channel_median_IoU']['Matrix']:.4f}, Reprecipitate "
   f"{A['per_channel_median_IoU']['Reprecipitate']:.4f}, Dilution zone "
   f"{A['per_channel_median_IoU']['DilutionZone']:.4f}, Void {A['semantic_median']:.4f}. The "
   f"model's card reports Void at IoU 0.976 in its own domain, the highest of its five "
   f"classes there; here it is the lowest, and 0.0000 to four decimals on "
   f"{A['void_exactly_zero_tiles']} of the {NT} tiles. Only Carbide clears the {CEIL:.4f} a "
   f"correct 3 px trace earns. Transferring a published micrograph segmenter therefore "
   f"cannot be done by reading its class list."],
  ["A difference of medians is not a paired gain.",
   f"Choosing the best of the five channels per tile against that tile's own label raises the "
   f"median from {U['median_of_a']:.4f} to {U['median_of_b']:.4f}, and that "
   f"{U['difference_of_medians']:+.4f} is the number a transfer table would carry. Per tile "
   f"the picture is different: the oracle cannot be lower than the fixed channel, because it "
   f"is a maximum over five channels that includes it, but it is strictly higher on only "
   f"{U['n_strictly_greater']} of the {NT} tiles -- on the other "
   f"{NT - U['n_strictly_greater']} the fixed channel already is the best one -- so the "
   f"median paired difference is {U['median_paired_difference']:+.4f} and the mean is "
   f"{U['mean_paired_difference']:+.4f}. The reported median moves by "
   f"{U['difference_of_medians']:.4f}; most individual tiles do not move at all. Both "
   f"statements are needed, and a transfer figure that quotes neither the selection rule nor "
   f"the pairing cannot be read."],
  ["A selection oracle must match the arity of the rule it bounds.",
   f"micro-sam is drawn without a gain bracket because no construction here is a bound on its "
   f"unsupervised arm. That arm is the union of every proposal darker than the tile's 25th "
   f"percentile, so it is itself a union, and the best SINGLE proposal does not bound it: it "
   f"is lower on {MB['n_b_below_a']} of the {NT} tiles, by up to 0.3717, at Wilcoxon "
   f"p = {MB['wilcoxon_p']}, with a median paired difference of "
   f"{MB['median_paired_difference']:+.4f} and a mean of {MB['mean_paired_difference']:+.4f}. "
   f"Unioning every proposal the label touches does beat the darkness rule, on "
   f"{MU['n_b_at_least_a']} of {NT} tiles at p = {MU['wilcoxon_p']}, but by a median paired "
   f"{MU['median_paired_difference']:+.4f} and it moves the median score only from "
   f"{MU['median_of_a']:.4f} to {MU['median_of_b']:.4f}. Two earlier versions of this figure "
   f"reported one or the other of these as micro-sam's share of the channel effect; neither "
   f"is, and the reason is arity rather than arithmetic."],
  ["A checkpoint can refuse the task silently.",
   f"micro-sam's electron-microscopy generalist checkpoint, the one its name recommends for "
   f"this modality, proposed nothing at all: zero instances on "
   f"{M_['em_organelles']['tiles_with_zero_instances']} of "
   f"{M_['em_organelles']['tiles_run']} tiles, and "
   f"{M_['em_organelles']['instances_at_any_threshold']} instances summed over every "
   f"proposal threshold tried, in a run that exited cleanly and reported a per-tile IoU of "
   f"0.0000. A reader taking those zeros at face value would publish a score for a "
   f"checkpoint that had declined to segment. The plain {M_['checkpoint']} checkpoint on the "
   f"same tiles proposes a median of {M_['median_instances']:.0f} instances and is the arm "
   f"panel B reports."],
 ],
}
json.dump(CAPTION, open(p_.replace(".png", ".caption.json"), "w"), indent=1,
          ensure_ascii=False)
print("wrote", p_)
print(f"  {img.size[0]}x{img.size[1]} px, min type {MIN_PX} px -> "
      f"{MIN_PX * 487.28 / img.size[0]:.2f} pt at final width (floor 6.00)")
