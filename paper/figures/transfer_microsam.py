"""micro-sam arm: microscopy-specialised SAM, the comparator COMPETITIVE_POSITION.md concedes.

micro-sam's AutomaticMaskGenerator is CLASS-AGNOSTIC: it returns instances, not cracks, so
turning them into a crack mask needs a selection rule, and the rule and not the model can
decide the score. Three rules are therefore recorded per tile:

  darkness      -- keep an instance iff its mean intensity is below the tile's 25th
                   percentile. Unsupervised, and the only one a user could run.
  best_instance -- the SINGLE instance with the highest IoU against the hand label. This is
                   the genuine per-tile upper bound for any rule that picks one proposal.
  union_touching-- the union of EVERY instance the label touches.

THE THIRD IS NOT AN UPPER BOUND, AND AN EARLIER VERSION OF THIS FILE SAID IT WAS. Unioning
every label-touching proposal adds all of their false-positive area, so it can score BELOW
the unsupervised rule it was supposed to bound: on 260708_316_H_b2_front_CBS_001__t0 it
returns 0.0119 against darkness's 0.0592, with a mask 48.95x the label's own area. A bound
that lands under the thing it bounds is not a bound, and the figure built on it had the row
mislabelled "best instance per tile". best_instance is the quantity that claim needs.

proposal_coverage and n_inst_by_threshold are recorded because the paper asserted both -- a
coverage fraction and a threshold sweep -- and neither was deposited anywhere.

vit_b, NOT vit_b_em_organelles -- the EM-organelles finetune returns zero instances on every
one of these tiles at every pred_iou_thresh including 0.0, which is a finding about that
checkpoint and not a measurement of micro-sam.
"""
import glob, json, os, sys, time, warnings
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
warnings.filterwarnings("ignore")
from PIL import Image
from micro_sam import util
from micro_sam.instance_segmentation import AutomaticMaskGenerator

#: Through _paths like every other script here, not a hardcoded Desktop layout: the
#: directory README promises "Nothing here contains an absolute path", and these two
#: were the first files to break that promise.
SC = os.path.join(_paths.require(_paths.SEM_REPO, "the sem-crack-detector checkout",
                                 "SEM_REPO"), "crack_export", "analysis", "sam3")
MODEL = sys.argv[1] if len(sys.argv) > 1 else "vit_b"
out = []

pred = util.get_sam_model(model_type=MODEL, device="cpu")
amg = AutomaticMaskGenerator(pred)

for f in sorted(glob.glob(f"{SC}/tiles/*_gray.png")):
    stem = os.path.basename(f)[:-9]
    g = np.array(Image.open(f).convert("L"))
    gt = np.array(Image.open(f[:-9] + "_gt.png").convert("L")) > 0

    t0 = time.time()
    emb = util.precompute_image_embeddings(pred, g, ndim=2, verbose=False)
    amg.initialize(g, image_embeddings=emb, verbose=False)
    lab = np.asarray(amg.generate(pred_iou_thresh=0.75))
    # The prose claims a threshold sweep and a proposal coverage; deposit both
    # rather than asserting them. A claim with no field behind it is not a result.
    sweep = {}
    for _t in (0.0, 0.25, 0.5, 0.75, 0.9):
        sweep[str(_t)] = int(len([L for L in np.unique(
            np.asarray(amg.generate(pred_iou_thresh=_t))) if L != 0]))
    dt = time.time() - t0

    ids = [L for L in np.unique(lab) if L != 0]
    q25 = float(np.percentile(g, 25))
    m_or = np.zeros(gt.shape, bool)
    m_dk = np.zeros(gt.shape, bool)
    best_single, best_single_iou = None, 0.0
    for L in ids:
        seg = lab == L
        u1 = (seg | gt).sum()
        i1 = float((seg & gt).sum() / u1) if u1 else 0.0
        if i1 > best_single_iou:
            best_single_iou, best_single = i1, L
        if (seg & gt).any():
            m_or |= seg
        if g[seg].mean() < q25:
            m_dk |= seg

    def iou(m):
        u = (m | gt).sum()
        return float((m & gt).sum() / u) if u else 0.0
    r = dict(tile=stem, n_inst=len(ids), sec=round(dt, 2),
             proposal_coverage=round(float((lab > 0).mean()), 4),
             n_inst_by_threshold=sweep,
             iou_dark=round(iou(m_dk), 4),
             iou_best_instance=round(best_single_iou, 4),
             iou_union_touching=round(iou(m_or), 4),
             par_union_touching=round(float(m_or.sum() / max(gt.sum(), 1)), 3))
    out.append(r)
    print(f"  {stem:<44} inst={r['n_inst']:>3} cov={100*r['proposal_coverage']:>5.1f}% "
          f"dark={r['iou_dark']:.4f} best1={r['iou_best_instance']:.4f} "
          f"union={r['iou_union_touching']:.4f} {r['sec']:>6.1f}s", flush=True)

#: The name transfer_bench.py reads. An earlier round deposited these under hand-renamed
#: filenames, so the documented stage-1 -> stage-2 chain could not actually be run.
NAME = {"vit_b": "microsam_eval.json",
        "vit_b_em_organelles": "microsam_em_organelles_eval.json"}.get(
            MODEL, f"microsam_{MODEL}_eval.json")
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), NAME), "w"),
          indent=1)
print("wrote", NAME)
a = lambda k: float(np.median([r[k] for r in out]))
print(f"\n{MODEL}: n={len(out)}  median dark={a('iou_dark'):.4f}  "
      f"best_instance={a('iou_best_instance'):.4f}  union={a('iou_union_touching'):.4f}")
print(f"  median proposal coverage {100*a('proposal_coverage'):.1f}% of a tile, "
      f"median {a('n_inst'):.0f} instances, median {a('sec'):.2f} s/tile")
import collections
tot = collections.Counter()
for r in out:
    for k, v in r['n_inst_by_threshold'].items():
        tot[k] += v
print("  total instances over all tiles by pred_iou_thresh:", dict(sorted(tot.items())))
