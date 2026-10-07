"""Consolidate the two transfer arms into the one artifact Figure 4 and section 4.8 quote.

WHY THIS FILE EXISTS. Every number in that subsection and in that caption has to come from a
committed file, so that no quantity can appear in the paper without appearing here. The two
arm runners beside this script (transfer_imranlabs.py, transfer_microsam.py) need torch,
segmentation_models_pytorch and micro_sam; this one needs only numpy, so the figure can be
rebuilt in the paper's own build interpreter without them.

WHAT IS DELIBERATELY ABSENT. No arm of the eleven-method comparison is recomputed here and
no number from this file is comparable to one in Figure 3: both arms run at a FIXED
operating point with no leave-one-frame-out selection, while ten of those eleven fit their
decision parameter on the eight training frames. The yardstick used instead is the one the
paper already derives -- the IoU a geometrically correct 3 px trace earns against these
same hand-painted labels.
"""
import json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
#: Not FIG_CACHE. That variable is documented as the .npy cache and README.md tells a reader
#: to repoint it; doing so would redirect the lookup of these COMMITTED artifacts and the
#: generator would fail to find a file that is in git. These live beside the script.
L = lambda n: json.load(open(os.path.join(HERE, n)))

im, ms, eo = L("imranlabs_eval.json"), L("microsam_eval.json"), \
             L("microsam_em_organelles_eval.json")
K = lambda d: {r["tile"]: r for r in d}
IM, MS, EO = K(im), K(ms), K(eo)
T = sorted(set(IM) & set(MS))
assert len(T) == 15, f"expected 15 tiles, got {len(T)}"

#: The five channels the published model emits, in its own card's order. "Void" is the one a
#: reader would pick for cracks from the class list alone, which is the point of the figure.
CH = ["Matrix", "Carbide", "Void", "Reprecipitate", "DilutionZone"]
chan = {c: [IM[t]["per_class"][c] for t in T] for c in CH}
med = {c: float(np.median(v)) for c, v in chan.items()}
fixed = max(med, key=med.get)
oracle = [IM[t]["iou_best"] for t in T]

out = dict(
    _tiles=T, n_tiles=len(T),
    n_frames=len({t.rsplit("__t", 1)[0] for t in T}),
    #: From section 4.5: what a geometrically correct 3 px centreline trace scores against
    #: these labels. Quoted, not recomputed -- it is the archived repo's iou_ceiling.json.
    iou_ceiling_3px=0.1662,
    imranlabs=dict(
        per_channel_median_IoU=med,
        per_channel_per_tile={c: [float(x) for x in v] for c, v in chan.items()},
        fixed_channel=fixed, fixed_median=med[fixed],
        semantic_channel="Void", semantic_median=med["Void"],
        void_exactly_zero_tiles=sum(1 for t in T if IM[t]["per_class"]["Void"] == 0.0),
        fixed_channel_best_on_tiles=sum(
            1 for t in T if max(IM[t]["per_class"], key=IM[t]["per_class"].get) == fixed),
        oracle_median=float(np.median(oracle)),
        oracle_minus_fixed=float(np.median(oracle) - med[fixed]),
        median_sec=float(np.median([IM[t]["sec"] for t in T])),
        disk_mb=293.0,
    ),
    microsam=dict(
        checkpoint="vit_b",
        #: The unsupervised rule, the only one of the three a user could run.
        median_IoU=float(np.median([MS[t]["iou_dark"] for t in T])),
        #: The genuine per-tile ceiling for picking ONE proposal, chosen against the label.
        median_IoU_best_instance=float(np.median([MS[t]["iou_best_instance"] for t in T])),
        #: Unioning every proposal the label touches. NOT a bound -- it adds all of their
        #: false-positive area and lands BELOW the best single proposal.
        median_IoU_union_touching=float(np.median([MS[t]["iou_union_touching"] for t in T])),
        median_proposal_coverage=float(np.median([MS[t]["proposal_coverage"] for t in T])),
        median_instances=float(np.median([MS[t]["n_inst"] for t in T])),
        median_sec=float(np.median([MS[t]["sec"] for t in T])),
        disk_mb=375.0,
        em_organelles=dict(
            tiles_run=len(EO),
            tiles_with_zero_instances=sum(1 for t in EO if EO[t]["n_inst"] == 0),
            thresholds_tested=sorted({k for t in EO
                                      for k in EO[t].get("n_inst_by_threshold", {})},
                                     key=float),
            instances_at_any_threshold=sum(
                v for t in EO for v in EO[t].get("n_inst_by_threshold", {}).values()),
            median_sec=float(np.median([EO[t]["sec"] for t in EO])) if EO else None,
        ),
    ),
)
#: THE QUANTITY THE SUBSECTION IS ABOUT, WITH ITS PAIRED FORM BESIDE IT.
#:
#: A difference of medians is not a paired gain, and on this corpus they disagree sharply.
#: Choosing the channel per tile raises the MEDIAN from 0.1914 to 0.2656, but the median
#: PAIRED difference is 0.0000, because the fixed channel is already the best one on 10 of
#: the 15 tiles; the gain lives in the other 5. Two earlier versions of this file reported
#: only the difference of medians and then used it to claim that micro-sam showed the same
#: effect. It does not: the pick-one-proposal oracle is BELOW the unsupervised darkness rule
#: on 7 of 15 tiles, because that rule is itself a UNION of proposals and no single proposal
#: bounds a union. The arity of a selection oracle has to match the rule it bounds.
def paired(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    try:
        from scipy.stats import wilcoxon
        p_ = float(wilcoxon(a, b, zero_method="zsplit").pvalue) if np.any(d) else 1.0
    except Exception:
        p_ = None
    return dict(median_of_a=float(np.median(a)), median_of_b=float(np.median(b)),
                difference_of_medians=round(float(np.median(b) - np.median(a)), 6),
                median_paired_difference=round(float(np.median(d)), 6),
                mean_paired_difference=round(float(d.mean()), 6),
                n_b_at_least_a=int((d >= 0).sum()), n_b_below_a=int((d < 0).sum()),
                n=len(d), wilcoxon_p=None if p_ is None else round(p_, 4))

DK = [MS[t]["iou_dark"] for t in T]
out["selection"] = dict(
    #: >= on all 15 BY CONSTRUCTION: the oracle is a max over five channels that includes
    #: the fixed one, so it cannot come out lower. That is why its Wilcoxon is not the
    #: interesting quantity; the count of tiles where it is strictly greater is.
    unet_channel=paired([IM[t]["per_class"][fixed] for t in T],
                        [IM[t]["iou_best"] for t in T]),
    #: label-informed, and it does beat the unsupervised rule -- by very little.
    microsam_union=paired(DK, [MS[t]["iou_union_touching"] for t in T]),
    #: NOT a bound on the darkness rule, and reported so that the reason is on the record.
    microsam_best_single=paired(DK, [MS[t]["iou_best_instance"] for t in T]),
)
out["selection"]["unet_channel"]["n_strictly_greater"] = int(sum(
    1 for t in T if IM[t]["iou_best"] > IM[t]["per_class"][fixed]))

p = os.path.join(HERE, "transfer_bench.json")
json.dump(out, open(p, "w"), indent=1)
print("wrote", p)
print(f"  {out['n_tiles']} tiles / {out['n_frames']} frames; 3 px ceiling {out['iou_ceiling_3px']}")
for c in CH:
    print(f"    channel {c:<14} median IoU {med[c]:.4f}")
a = out["imranlabs"]
print(f"  semantic channel {a['semantic_channel']} = {a['semantic_median']:.4f} "
      f"(exactly zero on {a['void_exactly_zero_tiles']}/{len(T)} tiles)")
print(f"  fixed channel {a['fixed_channel']} = {a['fixed_median']:.4f} "
      f"(best on {a['fixed_channel_best_on_tiles']}/{len(T)})")
print(f"  oracle {a['oracle_median']:.4f}, unearned gap {a['oracle_minus_fixed']:+.4f}")
m = out["microsam"]
print(f"  micro-sam {m['checkpoint']}: darkness {m['median_IoU']:.4f}, best instance "
      f"{m['median_IoU_best_instance']:.4f}, union-of-touching "
      f"{m['median_IoU_union_touching']:.4f}")
print(f"    {m['median_instances']:.0f} proposals/tile covering "
      f"{100*m['median_proposal_coverage']:.1f}% of a tile")
e = m["em_organelles"]
print(f"    em_organelles: zero instances on {e['tiles_with_zero_instances']}/"
      f"{e['tiles_run']} tiles; {e['instances_at_any_threshold']} instances summed over "
      f"thresholds {e['thresholds_tested']}")
print("  SELECTION, difference of medians vs the PAIRED difference:")
for k, v in out["selection"].items():
    print(f"    {k:<21} medians {v['median_of_a']:.4f} -> {v['median_of_b']:.4f} "
          f"({v['difference_of_medians']:+.4f});  paired median "
          f"{v['median_paired_difference']:+.4f}, mean {v['mean_paired_difference']:+.4f}, "
          f"b>=a on {v['n_b_at_least_a']}/{v['n']}, p={v['wilcoxon_p']}")
print(f"    the channel oracle is strictly greater on only "
      f"{out['selection']['unet_channel']['n_strictly_greater']} of {len(T)} tiles")
