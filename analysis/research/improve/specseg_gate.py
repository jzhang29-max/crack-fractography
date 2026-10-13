"""PRIMARY GATE for ANGLE 2: does a specimen mask delete hand-painted crack?

Run FIRST, before any tile score. Four precision rules have already died here by scoring
well on 512 px tiles and then destroying wide-open main cracks on full frames, so a tile
number is not evidence for anything that removes area.

  masks   sem-crack-detector/interior_active_learning/paint/*_correction_mask.png
          1 = crack, 2 = not-crack, 3 = erased, 0 = UNREVIEWED.
          0 is excluded from BOTH numerator and denominator. 91% of the corpus is
          unreviewed; counting it as error invents a precision collapse and counting it
          as correct invents a win. READ ONLY -- these are irreplaceable hand labels.
  denom   hand-marked crack the SHIPPED path (classifier off, multi-scale union) keeps,
          i.e. crack & clean. Reported as "% of kept", the same denominator
          fullframe_lever4_safety.py used, so this is comparable to the four dead rules.
  PASS    < 1% of kept hand-marked crack deleted across all 48 frames, AND the damage is
          not concentrated (the count of frames individually losing > 1% is reported).

EXACTNESS. The specimen mask is computed on an 8x8 block grid and upsampled, so it is
constant inside every block. Every count this script reports is therefore obtained by
summing per-block pixel counts over the blocks the mask drops -- identical to the
full-resolution intersection, and cheap enough to sweep 40 variants over 48 frames.
_selfcheck() proves that identity against the real full-resolution AND on real frames
before any variant is scored.

Writes only to the scratchpad. Never writes to sem-crack-detector.
"""
import os, sys, json, itertools
import warnings; warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import numpy as np
import specseg_cache as FC
import specimen_mask as SM

OUT = os.path.join(FC.WORK, "gate.json")


def block_counts(m, b=SM.B):
    h, w = m.shape
    hh, ww = h // b * b, w // b * b
    return m[:hh, :ww].reshape(hh // b, b, ww // b, b).sum(axis=(1, 3)).astype(np.int64)


def frame_tables(d):
    """Per-block pixel counts of everything the gate needs, plus the frame totals.

    Totals are the TRUE full-resolution totals; the block tables cover only the part of
    the frame the 8x8 grid tiles. Any pixel in the ragged right/bottom strip is inside
    the specimen by construction (upsample() forces it True), so it can never be deleted
    and its absence from the tables cannot flatter a variant.
    """
    clean, crack, notc, erase = d["clean"], d["crack"], d["notc"], d["erase"]
    kept = clean & crack
    # 3 = "erase from candidacy" is also a human NOT-CRACK verdict, so it is refereed
    # evidence and is pooled with 2 wherever a precision gain is claimed. 0 is never used.
    nc = notc | erase
    return dict(
        kept=block_counts(kept), notc_in=block_counts(clean & nc),
        cand=block_counts(clean), crack_all=block_counts(crack),
        tot_kept=int(kept.sum()), tot_notc_in=int((clean & nc).sum()),
        tot_cand=int(clean.sum()), tot_crack=int(crack.sum()),
        tot_notc=int(nc.sum()), shape=d["shape"])


VARIANTS = SM.GRID


vkey = SM.vkey


def specimen_for(d, v):
    return SM.build(d["bmean"], d["bstd"], v)


def _selfcheck(names):
    """Block accounting == full-resolution intersection, on real frames."""
    ok = True
    for n in names[:3]:
        d = FC.load(n)
        tb = frame_tables(d)
        v = VARIANTS[4]
        S = specimen_for(d, v)
        Sf = SM.upsample(S, d["shape"])
        full = int(((d["clean"] & d["crack"]) & ~Sf).sum())
        blk = int(tb["kept"][~S].sum())
        print(f"  CONTROL {n:<34} block-sum {blk:>10,}  full-res {full:>10,}  "
              f"{'PASS' if blk == full else 'FAIL'}")
        ok &= blk == full
    # a specimen mask covering everything must delete exactly nothing
    d = FC.load(names[0]); tb = frame_tables(d)
    allS = np.ones_like(specimen_for(d, VARIANTS[0]))
    z = int(tb["kept"][~allS].sum())
    print(f"  CONTROL all-specimen mask deletes 0 kept crack: {'PASS' if z == 0 else 'FAIL'}")
    ok &= z == 0
    # and a mask covering nothing must delete every kept pixel the grid covers
    noneS = ~allS
    full = int(tb["kept"].sum())
    g = int(tb["kept"][~noneS].sum())
    print(f"  CONTROL empty specimen mask deletes all {full:,} gridded kept px: "
          f"{'PASS' if g == full else 'FAIL'}")
    ok &= g == full
    print(f"  CONTROL EDT closing == dilate+erode: {'PASS' if SM._selfcheck_close() else 'FAIL'}")
    ok &= SM._selfcheck_close()
    return ok


def main():
    names = FC.cached_names()
    print(f"INSTRUMENT CONTROLS ({len(names)} cached frames)")
    assert _selfcheck(names)
    rows = {vkey(v): [] for v in VARIANTS}
    for i, n in enumerate(names, 1):
        d = FC.load(n)
        tb = frame_tables(d)
        for v in VARIANTS:
            S = specimen_for(d, v)
            out = ~S
            rows[vkey(v)].append(dict(
                frame=n, kept=tb["tot_kept"], notc_in=tb["tot_notc_in"],
                cand=tb["tot_cand"], crack=tb["tot_crack"], notc=tb["tot_notc"],
                del_kept=int(tb["kept"][out].sum()),
                del_crack_all=int(tb["crack_all"][out].sum()),
                rm_notc=int(tb["notc_in"][out].sum()),
                rm_cand=int(tb["cand"][out].sum()),
                spec_frac=float(S.mean())))
        print(f"  [{i}/{len(names)}] {n}", flush=True)
    json.dump(rows, open(OUT, "w"))
    print(f"\nwrote {OUT}")
    report(rows)


def report(rows):
    print(f"\n{'variant':<34} {'%kept crack DELETED':>20} {'frames>1%':>10} "
          f"{'worst frame':>12} {'notc removed':>14} {'cand area rm':>14}")
    print("-" * 112)
    recs = []
    for k, rs in rows.items():
        kept = sum(r["kept"] for r in rs); dele = sum(r["del_kept"] for r in rs)
        notc = sum(r["notc_in"] for r in rs); rmn = sum(r["rm_notc"] for r in rs)
        cand = sum(r["cand"] for r in rs); rmc = sum(r["rm_cand"] for r in rs)
        worst = max((r["del_kept"] / max(r["kept"], 1) for r in rs), default=0)
        nbad = sum(1 for r in rs if r["del_kept"] / max(r["kept"], 1) > 0.01)
        recs.append((100 * dele / max(kept, 1), k, nbad, 100 * worst,
                     100 * rmn / max(notc, 1), 100 * rmc / max(cand, 1), dele, rmn, rmc))
    for pct, k, nbad, worst, pn, pc, dele, rmn, rmc in sorted(recs):
        flag = "PASS" if pct < 1.0 else "FAIL"
        print(f"{flag} {k:<29} {pct:>8.3f}% ({dele:>9,}) {nbad:>10} {worst:>11.2f}% "
              f"{pn:>7.2f}% ({rmn:>7,}) {pc:>7.2f}% ({rmc:>10,})")


if __name__ == "__main__":
    if "--report" in sys.argv:
        report(json.load(open(OUT)))
    else:
        main()
