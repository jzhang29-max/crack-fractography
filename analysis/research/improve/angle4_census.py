"""ANGLE 4, stage 4: a BLIND, size-matched census of what the detector marks.

The question is "of the pixels the detector marks that the human did not, what fraction
are (a) off-specimen void, (b) plausibly real crack nobody painted, (c) a genuine mistake
-- porosity, a scratch, a polishing artefact?" An impression is not an answer, so this
builds an instrument with a key that is withheld until the calls are committed.

SAMPLING. The unit is a predicted connected component on a full frame. The quantity of
interest is a share of PIXEL MASS, so the target arm is drawn with probability
proportional to area (PPS): an unweighted proportion over a PPS sample estimates the mass
fraction directly, with no post-hoc weighting to get wrong.

ARMS -- one target and three controls, all rendered identically and shuffled into one
pool under random ids:
  UNREV   the target. Components that are >=90% UNREVIEWED (corr==0). This is the
          population the whole question is about: marked by the machine, never refereed.
  REFPOS  positive control. Components the human refereed and called CRACK (>=50% of
          their refereed pixels are state 1). If the adjudicator cannot call these crack,
          the adjudicator is the instrument that is broken, not the detector.
  REFNEG  negative control. Components the human refereed and called NOT-CRACK (state
          2/3). A call of "real crack" here is an adjudicator false positive, and its
          rate is the floor under any (b) estimate from the UNREV arm.
  VOID    positive control for class (a), from MAR_H_HIP_CBS_0002 -- the frame whose
          off-specimen void owns 78.6% of all false-positive pixels on the 26 tiles. It
          carries no correction mask, so it is invisible to every refereed number here
          and has to be brought in deliberately.
REFPOS/REFNEG/VOID are size-matched to the UNREV draws by nearest log-area, because a
big patch and a small patch do not look alike and size alone would give the game away.

BLINDING. Patches are written as patches/<random id>.png with the arm recorded only in
key.json. The adjudicator writes calls.json first and key.json is read only afterwards.
Each patch is two panels: the micrograph, and the same crop with the component outlined,
so the call is about THAT object and not about the crop in general. The human paint is
never drawn.

CLASS DEFINITIONS, fixed before any patch is seen:
  a  off-specimen: the outlined object is background beyond the edge of the sample -- the
     dark area runs off the field and the fracture texture stops at a continuous edge.
  b  plausibly real crack: an elongated dark channel, tortuous or branching, with walls
     that face each other; or an object contiguous with such a channel.
  c  genuine mistake: round or equiaxed pore, straight parallel-sided scratch, loose
     debris, an isolated dark patch with no channel, a shadow with no opening.
  u  cannot tell from the patch.

Run:
    python -B angle4_census.py build      # writes patches + key (key not to be read yet)
    python -B angle4_census.py unblind    # after calls.json exists
"""
import os, sys, json, random, warnings
warnings.filterwarnings("ignore")
OUT = os.environ.get("A4OUT", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                              "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/angle4")
os.environ.setdefault("MPLCONFIGDIR", OUT + "/mpl")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import numpy as np                                  # noqa: E402
from scipy import ndimage as ndi                    # noqa: E402
from PIL import Image                               # noqa: E402
Image.MAX_IMAGE_PIXELS = None
import angle4_shipped as S                          # noqa: E402
import angle4_fullframe as F                        # noqa: E402

SEED = 20261012
MIN_AREA = 800
N_UNREV, N_REFPOS, N_REFNEG, N_VOID = 24, 8, 8, 5
VOID_FRAME = "MAR_H_HIP_CBS_0002"
ST8 = np.ones((3, 3), bool)
PD = os.path.join(OUT, "patches")


def pick(rows, rng):
    """Build the sample. Returns [(arm, frame, comp)] with the four arms size-matched."""
    pool = [(r["frame"], c) for r in rows if "error" not in r for c in r["comps"]
            if c["area"] >= MIN_AREA]
    def ref(c):
        return c["c1"] + c["c2"] + c["c3"]
    unrev = [p for p in pool if p[1]["c0"] >= 0.90 * p[1]["area"]]
    refpos = [p for p in pool if ref(p[1]) >= 200 and p[1]["c1"] >= 0.5 * ref(p[1])]
    refneg = [p for p in pool if ref(p[1]) >= 200
              and (p[1]["c2"] + p[1]["c3"]) >= 0.5 * ref(p[1])]
    w = np.array([p[1]["area"] for p in unrev], float)
    idx = rng.choice(len(unrev), size=min(N_UNREV, len(unrev)), replace=False,
                     p=w / w.sum())                      # PPS, without replacement
    chosen = [("UNREV", *unrev[i]) for i in idx]
    targets = [unrev[i][1]["area"] for i in idx]

    def match(cands, n, arm):
        if not cands:
            return []
        la = np.log(np.array([c[1]["area"] for c in cands], float))
        out, used = [], set()
        for t in rng.permutation(targets)[:n]:
            d = np.abs(la - np.log(t))
            for j in np.argsort(d):
                if j not in used:
                    used.add(int(j)); out.append((arm, *cands[int(j)])); break
        return out

    chosen += match(refpos, N_REFPOS, "REFPOS") + match(refneg, N_REFNEG, "REFNEG")
    return chosen, targets


def void_comps(rng, targets, n=N_VOID):
    """The off-specimen void frame, which carries no correction mask."""
    import tifffile
    from skimage import exposure
    import detect_cracks as D
    raw = tifffile.imread(os.path.join(F.SEM, "original", VOID_FRAME + ".tif"))
    if raw.ndim == 3:
        raw = raw[..., 0]
    lo, hi = np.percentile(raw, [1.0, 99.5])
    img8 = exposure.rescale_intensity(raw.astype(np.float32), in_range=(lo, hi),
                                      out_range=(0, 255)).astype(np.uint8)
    x0, y0, x1, y1 = D.find_field_of_view(img8)
    img8 = img8[y0:y1, x0:x1]
    pred = S.shipped_clean(img8, min_area=15)
    lab, k = ndi.label(pred, structure=ST8)
    objs = ndi.find_objects(lab)
    sz = np.bincount(lab.ravel()); sz[0] = 0
    big = [i for i in np.argsort(-sz)[:40] if sz[i] >= MIN_AREA]
    la = np.log(sz[big].astype(float))
    out, used = [], set()
    for t in rng.permutation(targets)[:n]:
        d = np.abs(la - np.log(t))
        for j in np.argsort(d):
            if j not in used:
                used.add(int(j)); i = big[int(j)]
                sl = objs[i - 1]
                out.append(("VOID", VOID_FRAME,
                            dict(id=int(i), area=int(sz[i]),
                                 bbox=[int(sl[0].start), int(sl[1].start),
                                       int(sl[0].stop), int(sl[1].stop)],
                                 c0=int(sz[i]), c1=0, c2=0, c3=0)))
                break
    return out, img8, lab


def render(img8, lab, comp, path, maxdim=440):
    y0, x0, y1, x1 = comp["bbox"]
    h, w = y1 - y0, x1 - x0
    pad = int(0.6 * max(h, w)) + 40
    Y0, X0 = max(y0 - pad, 0), max(x0 - pad, 0)
    Y1, X1 = min(y1 + pad, img8.shape[0]), min(x1 + pad, img8.shape[1])
    crop = img8[Y0:Y1, X0:X1]
    m = (lab[Y0:Y1, X0:X1] == comp["id"])
    edge = m & ~ndi.binary_erosion(m, ST8, 2)
    rgb = np.dstack([crop] * 3).astype(np.uint8)
    rgb[edge] = (255, 40, 40)
    both = np.concatenate([np.dstack([crop] * 3).astype(np.uint8),
                           np.full((crop.shape[0], 8, 3), 255, np.uint8), rgb], 1)
    im = Image.fromarray(both)
    sc = maxdim * 2 / max(im.size)
    if sc < 1:
        im = im.resize((max(int(im.width * sc), 2), max(int(im.height * sc), 2)),
                       Image.LANCZOS)
    im.save(path)


def build():
    rows = json.load(open(os.path.join(OUT, "fullframe.json")))
    rng = np.random.default_rng(SEED)
    chosen, targets = pick(rows, rng)
    vd, vimg, vlab = void_comps(rng, targets)
    chosen += vd
    os.makedirs(PD, exist_ok=True)
    ids = [f"p{i:03d}" for i in rng.permutation(len(chosen))]
    key = []
    byframe = {}
    for (arm, frame, comp), rid in zip(chosen, ids):
        if frame == VOID_FRAME:
            img8, lab = vimg, vlab
        else:
            if frame not in byframe:
                img8 = F.load_frame(frame)[0]
                pred = S.shipped_clean(img8, min_area=15)
                lab, _ = ndi.label(pred, structure=ST8)
                byframe[frame] = (img8, lab)
                print(f"  loaded {frame}", flush=True)
            img8, lab = byframe[frame]
        render(img8, lab, comp, os.path.join(PD, rid + ".png"))
        key.append(dict(rid=rid, arm=arm, frame=frame, area=comp["area"],
                        c0=comp["c0"], c1=comp["c1"], c2=comp["c2"], c3=comp["c3"]))
    key.sort(key=lambda k: k["rid"])
    json.dump(key, open(os.path.join(OUT, "key.json"), "w"), indent=1)
    json.dump([k["rid"] for k in key], open(os.path.join(OUT, "rids.json"), "w"), indent=1)
    from collections import Counter
    print(f"\nwrote {len(key)} patches to {PD}")
    print("  arms:", dict(Counter(k["arm"] for k in key)))
    print("  DO NOT read key.json until calls.json is written.")


def unblind():
    key = {k["rid"]: k for k in json.load(open(os.path.join(OUT, "key.json")))}
    calls = json.load(open(os.path.join(OUT, "calls.json")))
    from collections import Counter, defaultdict
    by = defaultdict(Counter)
    mass = defaultdict(lambda: defaultdict(int))
    for rid, cl in calls.items():
        k = key[rid]
        by[k["arm"]][cl] += 1
        mass[k["arm"]][cl] += k["area"]
    print(f"{'arm':<8} {'n':>3}  " + "  ".join(f"{c:>6}" for c in "abcu"))
    for arm in ("UNREV", "REFPOS", "REFNEG", "VOID"):
        c = by[arm]; n = sum(c.values())
        if not n:
            continue
        print(f"{arm:<8} {n:>3}  " + "  ".join(f"{c[x]:>2} {100*c[x]/n:3.0f}%" for x in "abcu"))
    print("\nUNREV arm is PPS by area, so the unweighted share IS the mass share estimate.")
    for arm in ("UNREV", "REFPOS", "REFNEG", "VOID"):
        if by[arm]:
            n = sum(by[arm].values())
            p = by[arm]["b"] / n
            se = (p * (1 - p) / n) ** 0.5
            print(f"  {arm:<7} share called (b) real crack: {p:.3f} +- {se:.3f}  (n={n})")
    json.dump({a: dict(by[a]) for a in by}, open(os.path.join(OUT, "census.json"), "w"),
              indent=1)


if __name__ == "__main__":
    {"build": build, "unblind": unblind}[sys.argv[1]]()
