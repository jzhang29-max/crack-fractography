"""Re-measure the two ALREADY-REJECTED precision rules on the same 48 frames, through the
same denominator, so lever 4 can be ranked against them rather than against a number from
a different unit set.

voidkiller_safety.py measured the texture veto at 43.46% and the thickness excision at
41.00%, but on FOUR frames and against "all hand-marked crack on those four frames".
This run uses all 48 frames and the denominator that isolates a region-rejecting rule:
hand-marked crack pixels the no-classifier path KEEPS, which is the only set such a rule
can take anything away from.
"""
import os, sys, json, time, warnings
warnings.filterwarnings("ignore")
MY = os.environ.get("MYSC", "/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
                            "35618087-5532-4f31-9699-5f1551304d41/scratchpad")
os.environ.setdefault("MPLCONFIGDIR", MY + "/mpl")
R = "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research"
sys.path.insert(0, R); sys.path.insert(0, R + "/improve")
sys.dont_write_bytecode = True
import numpy as np
from scipy import ndimage as ndi
import fullframe_lever4_safety as FF
from voidkiller_safety import kill_texture, kill_thick, STRUCT8

MK = float(os.environ.get("MK", "5.0"))
RULES = [("texture veto floor=1.0", lambda c, f: kill_texture(c, f, 1.0)),
         ("thickness excision r_big=50", lambda c, f: kill_thick(c, f, 50)),
         ("thickness excision r_big=100", lambda c, f: kill_thick(c, f, 100))]

names = sorted(f[:-len("_correction_mask.png")] for f in os.listdir(FF.PAINT)
               if f.endswith("_correction_mask.png"))
names = [n for n in names if os.path.exists(os.path.join(FF.SEM, "original", n + ".tif"))]
print(f"{len(names)} frames, mad_k={MK}. Deletion is measured against the SAME keepall "
      f"mask as lever 4.\n")
agg = {n: 0 for n, _ in RULES}
kept_tot = painted_tot = 0
rows, t0 = [], time.time()
for i, name in enumerate(names, 1):
    got = FF.load_frame(name)
    if got is None:
        print(f"[{i}/{len(names)}] {name} SKIPPED"); continue
    img8, raw, corr = got
    crack = corr == 1
    base = FF.frame_base(img8)
    st = FF.stages_at(base, MK)
    keepall = st["labeled"] > 0
    kept = int((keepall & crack).sum())
    kept_tot += kept; painted_tot += int(crack.sum())
    r = dict(frame=name, painted=int(crack.sum()), kept=kept)
    for nm, fn in RULES:
        d = int((fn(keepall, base["flat"]) & keepall & crack).sum())
        agg[nm] += d
        r[nm] = d
    rows.append(r)
    print(f"[{i}/{len(names)}] {name:<34} kept {kept:>10,} | "
          + " | ".join(f"{nm.split()[0][:4]} {r[nm]:>9,} {100*r[nm]/max(kept,1):5.1f}%"
                       for nm, _ in RULES) + f"  {time.time()-t0:5.0f}s", flush=True)
    json.dump(dict(mad_k=MK, rows=rows), open(MY + "/work/deadrules.json", "w"))
print("\n" + "=" * 100)
print(f"POOLED over {len(rows)} frames: {painted_tot:,} painted crack px, "
      f"{kept_tot:,} kept by the no-classifier path")
for nm, _ in RULES:
    print(f"  {nm:<32} deletes {agg[nm]:>12,}  = {100*agg[nm]/max(kept_tot,1):6.2f}% of kept"
          f"  ({100*agg[nm]/max(painted_tot,1):5.2f}% of painted)")
json.dump(dict(mad_k=MK, rows=rows, pooled=agg, kept=kept_tot, painted=painted_tot),
          open(MY + "/work/deadrules.json", "w"))
