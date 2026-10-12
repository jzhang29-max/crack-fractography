#!/usr/bin/env python3
"""Randomly sampled tiles for hand labelling, and the one property that matters.

THE SAMPLING RULE IS THE EXPERIMENT. Positions are drawn uniformly over the total area of
the arm's frames, and nothing about the detector's output or any existing label is
consulted in choosing them. That is not the obvious choice and it is not what this
project did before: the 15 published SEM benchmark tiles were cut centred on the densest
painted region, and they came out pooled 97.31% unreviewed -- WORSE than the whole frames
at 91.25% -- because centring on a crack raises crack density without adding one
not-crack verdict. A crack-seeded sample measures the detector where it was always going
to look good.

Most of these tests therefore guard the sampler against learning anything about the
answer before it picks a position.
"""
import json
import os
import sys

import numpy as np
import pytest
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from app import paths as P  # noqa: E402

SEM = P.sem_repo()
_MACHINE = os.path.join(SEM or "", "crack_export", "derived", "machine_masks")
needs_sem = pytest.mark.skipif(
    not SEM or not os.path.isdir(_MACHINE),
    reason="no sem-crack-detector checkout with machine masks on this machine")


def _post(s, path, obj):
    st, raw = s.post(path, json.dumps(obj).encode(), "application/json")
    return st, (json.loads(raw) if raw else None)


@pytest.fixture
def seeded(tmp_path):
    """A server whose dataset is the real SEM records, with the user's uploads dropped."""
    d = tmp_path / "d"
    d.mkdir(parents=True, exist_ok=True)
    live = os.path.join(os.path.expanduser("~"), "Library", "Application Support",
                        "Crack Fractography", "frames.json")
    if not os.path.exists(live):
        pytest.skip("no measured corpus on this machine")
    rows = [r for r in json.load(open(live, encoding="utf-8"))
            if r.get("arm") == "sem/machine"]
    if not rows:
        pytest.skip("no sem/machine frames measured on this machine")
    with open(d / "frames.json", "w", encoding="utf-8") as fh:
        json.dump(rows, fh)
    return d


@pytest.mark.parametrize("bad", [{"n": 0}, {"n": 201}, {"n": -1}, {"size": 16},
                                 {"size": 4096}, {"n": "x"}, {"size": "y"},
                                 {"collection": "a/b"}])
def test_an_unusable_request_is_refused(seeded, bad):
    with Server(seeded) as s:
        st, _ = _post(s, "/api/sample_tiles", {"arm": "sem/machine", **bad})
        assert st == 400, f"{bad} was accepted"


@needs_sem
def test_the_same_seed_gives_the_same_tiles(seeded, tmp_path):
    """A sample you cannot reproduce is a sample nobody can check. The seed and the rule
    are both in the response for the same reason."""
    boxes = []
    for i in range(2):
        d = tmp_path / f"run{i}"
        d.mkdir()
        with open(d / "frames.json", "w", encoding="utf-8") as fh:
            json.dump(json.load(open(seeded / "frames.json", encoding="utf-8")), fh)
        with Server(d) as s:
            st, r = _post(s, "/api/sample_tiles",
                          {"arm": "sem/machine", "n": 5, "size": 512, "seed": 7})
            assert st == 200, r
            boxes.append([(t["parent"], tuple(t["box"])) for t in r["tiles"]])
    assert boxes[0] == boxes[1], "the same seed produced a different sample"


@needs_sem
def test_a_different_seed_gives_a_different_sample(seeded):
    with Server(seeded) as s:
        a = _post(s, "/api/sample_tiles",
                  {"arm": "sem/machine", "n": 6, "size": 512, "seed": 1})[1]
        b = _post(s, "/api/sample_tiles",
                  {"arm": "sem/machine", "n": 6, "size": 512, "seed": 2})[1]
    pa = [(t["parent"], tuple(t["box"])) for t in a["tiles"]]
    pb = [(t["parent"], tuple(t["box"])) for t in b["tiles"]]
    assert pa != pb


@needs_sem
def test_the_sample_is_not_drawn_toward_the_detector(seeded):
    """THE PROPERTY THE WHOLE EXERCISE RESTS ON. If positions were chosen where the
    detector fired, precision would be measured only where it was going to look good.

    Checked against the corpus itself rather than by reading the code: the share of
    sampled tiles containing any predicted crack must sit near the share for ALL tile
    positions, which is about 72% at 512 px on this corpus. A crack-seeded sampler would
    come out at or near 100%."""
    with Server(seeded) as s:
        st, r = _post(s, "/api/sample_tiles",
                      {"arm": "sem/machine", "n": 60, "size": 512, "seed": 11})
        assert st == 200, r
    assert r["n_made"] >= 50, r["n_made"]
    # MEASURED HERE, FROM THE PARENT MASKS, not read off the server's own field. The
    # field is derived from the as-cut copy, so a sampler that stopped writing one would
    # report zero predictions and this test would "pass" the bias check for the wrong
    # reason -- which it did, until this was changed.
    cache, hits = {}, 0
    for t in r["tiles"]:
        par = cache.get(t["parent"])
        if par is None:
            par = np.array(Image.open(
                os.path.join(_MACHINE, f"{t['parent']}_machine.png")).convert("L")) < 128
            cache[t["parent"]] = par
        x, y, w, h = t["box"]
        hits += bool(par[y:y + h, x:x + w].any())
    share = hits / r["n_made"]
    assert share < 0.92, (
        f"{100*share:.0f}% of sampled tiles contain a prediction; a uniform sample of "
        f"this corpus is near 72%, so the sampler is being drawn to the detector")
    assert share > 0.35, (
        f"only {100*share:.0f}% contain a prediction, far below the ~72% a uniform "
        f"sample gives; the sampler is avoiding the detector, which biases it the other "
        f"way")


@needs_sem
def test_every_tile_carries_the_micrograph_it_will_be_labelled_against(seeded):
    """A tile with no micrograph cannot be hand-labelled at all -- you cannot judge a
    crack boundary against the binary mask whose boundary it is meant to be. The SEM
    originals are 6144x4376 against a 6144x4096 mask, so this only works because the
    databar is trimmed before the box is cut.

    The first version of this reported every tile as having no micrograph while all of
    them had one, because it read a `has_original` key the crop response does not carry.
    That is why the count is asserted from the FILES on disk and not from the field."""
    with Server(seeded) as s:
        st, r = _post(s, "/api/sample_tiles",
                      {"arm": "sem/machine", "n": 6, "size": 512, "seed": 3})
        assert st == 200, r
        assert r["n_without_micrograph"] == 0, r["without_micrograph"]
        up = os.path.join(str(seeded), "uploads")
        for t in r["tiles"]:
            o = os.path.join(up, f"{t['frame']}_original.png")
            assert os.path.exists(o), f"{t['frame']} has no micrograph on disk"
            a = np.array(Image.open(o))
            assert a.shape[:2] == (512, 512), a.shape
            assert float(a.std()) > 1.0, f"{t['frame']}'s micrograph is blank"


@needs_sem
def test_each_tile_keeps_the_pristine_detector_mask_it_was_cut_from(seeded):
    """Painting a tile overwrites its `_gated.png`. Without `_ascut.png` there would be
    no record of what the detector proposed, and the only file left to score the finished
    label against would be the one the human just edited -- precision 1 by construction.
    """
    with Server(seeded) as s:
        st, r = _post(s, "/api/sample_tiles",
                      {"arm": "sem/machine", "n": 4, "size": 512, "seed": 5})
        assert st == 200, r
        up = os.path.join(str(seeded), "uploads")
        for t in r["tiles"]:
            cut = os.path.join(up, f"{t['frame']}_ascut.png")
            assert os.path.exists(cut), f"{t['frame']} kept no as-cut copy"
            a = np.array(Image.open(cut).convert("L"))
            # it must equal the parent's machine mask over the same box, exactly
            x, y, w, h = t["box"]
            par = np.array(Image.open(
                os.path.join(_MACHINE, f"{t['parent']}_machine.png")).convert("L"))
            assert np.array_equal(a, par[y:y + h, x:x + w]), (
                f"{t['frame']}'s as-cut copy is not what the detector said there")


@needs_sem
def test_a_frame_whose_micrograph_does_not_fit_is_excluded_and_named(seeded):
    """A tile with no micrograph behind it cannot be hand-labelled, so it is not a sample
    unit -- admitting one means handing over a tile that has to be skipped and a sample
    with a hole nobody recorded.

    Five frames in this corpus have masks of a different SHAPE from their micrographs
    (2952x2952, 3036x3037, 2970x2971, 3041x3042, 1490x1490 against 6144x4376 or
    3072x2188). They are not databar cases: the same box is a different region of the
    specimen in each file. Restricting the population to labellable frames is defensible;
    doing it silently is not, so every exclusion is named in the response."""
    with Server(seeded) as s:
        st, r = _post(s, "/api/sample_tiles",
                      {"arm": "sem/machine", "n": 30, "size": 512, "seed": 21})
        assert st == 200, r
        assert r["n_without_micrograph"] == 0, (
            f"{r['n_without_micrograph']} tiles cannot be labelled: "
            f"{r['without_micrograph']}")
        assert r["frames_excluded"] >= 1, (
            "no frame was excluded; this corpus has five whose micrograph does not fit")
        whys = " ".join(x["why"] for x in r["excluded"])
        assert "not the same region" in whys or "does not cover" in whys, whys
        # and the excluded ones must not appear as a parent
        excluded = {x["frame"] for x in r["excluded"]}
        assert not ({t["parent"] for t in r["tiles"]} & excluded)


@needs_sem
def test_the_tiles_land_in_the_collection_they_were_asked_for(seeded):
    with Server(seeded) as s:
        st, r = _post(s, "/api/sample_tiles",
                      {"arm": "sem/machine", "n": 4, "size": 512, "seed": 9,
                       "collection": "GT tiles"})
        assert st == 200, r
        st, rows = s.json("/api/frames?arm=uploads&collection=GT%20tiles")
        assert st == 200
        assert sorted(x["frame"] for x in rows) == sorted(t["frame"] for t in r["tiles"])
        assert "GT tiles" in [c["name"] for c in s.json("/api/collections")[1]["collections"]]


@needs_sem
def test_a_sampled_tile_is_scorable_end_to_end(seeded):
    """The whole point: cut a tile, correct it, mark it reviewed, get a precision with a
    real denominator -- and it must NOT be refused as circular, because the as-cut copy
    is a separate artifact from the edited mask."""
    with Server(seeded) as s:
        st, r = _post(s, "/api/sample_tiles",
                      {"arm": "sem/machine", "n": 3, "size": 512, "seed": 13})
        assert st == 200, r
        t = max(r["tiles"], key=lambda z: z["predicted_fraction"] or 0)
        if not (t["predicted_fraction"] or 0) > 0:
            pytest.skip("no sampled tile had a prediction to score")
        up = os.path.join(str(seeded), "uploads")
        m = np.array(Image.open(os.path.join(up, f"{t['frame']}_gated.png")).convert("L"))
        m[40:90, 40:140] = 0          # a crack the detector missed -> 5,000 FN
        import io as _io
        b = _io.BytesIO(); Image.fromarray(m, mode="L").save(b, "PNG")
        st, raw = s.upload(f"{t['frame']}.png", b.getvalue(),
                           path=f"/api/mask_edit?arm=uploads&frame={t['frame']}")
        assert st == 200, raw[:300]
        st, d = _post(s, "/api/review_region",
                      {"arm": "uploads", "frame": t["frame"], "box": [0, 0, 512, 512]})
        assert st == 200, d
        assert d["scorable"] is True, d.get("why_not")
        st, sc = s.json("/api/review_scores")
        assert sc["n_regions_refused_as_circular"] == 0, sc
        assert sc["n_scored"] == 1, sc
        reg = sc["regions"][0]
        assert reg["scored_against"] == "uploads/as-cut", reg
        assert reg["tp"] + reg["fp"] + reg["fn"] + reg["tn"] == 512 * 512
        assert reg["fn"] >= 4000, reg      # the block I painted, less any already marked


@needs_sem
def test_restricting_to_specimens_says_so_and_sticks_to_them(seeded):
    """A sample over named specimens estimates THOSE SPECIMENS, not the corpus, and the
    two must not be pooled without area weights. Used to top up what a uniform draw
    missed: at n=24 over 14 specimens, five got nothing and 10.1% of the corpus area was
    unrepresented. The restriction is echoed back in the response for the same reason the
    seed is -- a sample whose population nobody recorded cannot be interpreted later."""
    with Server(seeded) as s:
        st, all_r = _post(s, "/api/sample_tiles",
                          {"arm": "sem/machine", "n": 3, "size": 256, "seed": 31})
        assert st == 200, all_r
        pool_spec = sorted({f["specimen"] for f in json.load(
            open(os.path.join(str(seeded), "frames.json"), encoding="utf-8"))})
        pick = pool_spec[:2]
        st, r = _post(s, "/api/sample_tiles",
                      {"arm": "sem/machine", "n": 6, "size": 256, "seed": 31,
                       "specimens": pick})
        assert st == 200, r
        assert r["specimens_restricted_to"] == sorted(pick), r["specimens_restricted_to"]
        assert "RESTRICTED" in r["sampling_rule"], r["sampling_rule"]
        assert "must not be pooled" in r["sampling_rule"]
        # every tile's parent really is in one of the named specimens
        by_frame = {f["frame"]: f["specimen"] for f in json.load(
            open(os.path.join(str(seeded), "frames.json"), encoding="utf-8"))}
        got = {by_frame[t["parent"]] for t in r["tiles"]}
        assert got <= set(pick), f"sampled outside the restriction: {got - set(pick)}"


@needs_sem
@pytest.mark.parametrize("bad", [[], "MAR_H_AS", ["no such specimen"]])
def test_an_unusable_specimen_restriction_is_refused(seeded, bad):
    with Server(seeded) as s:
        st, _ = _post(s, "/api/sample_tiles",
                      {"arm": "sem/machine", "n": 2, "size": 256, "specimens": bad})
        assert st in (400, 404), f"{bad!r} was accepted"


@needs_sem
def test_a_blank_tile_keeps_the_detector_output_somewhere_else(seeded):
    """GROUND TRUTH THE DETECTOR HAD NO HAND IN.

    A tile cut from sem/machine arrives with the detector's output already drawn on it,
    and "labelling" then means editing that -- so what comes back is the prediction plus
    whatever the labeller felt moved to change, anchored to it and biased toward agreeing
    with it. The user asked for the samples "without any markings", which is also the
    better experiment.

    The two things that must both hold: the editable mask is empty, AND the detector's
    output survives in `_ascut.png`, because that is what the finished label is scored
    against. Blanking both would leave nothing to compare to.
    """
    with Server(seeded) as s:
        st, r = _post(s, "/api/sample_tiles",
                      {"arm": "sem/machine", "n": 4, "size": 512, "seed": 41,
                       "collection": "GT", "tag": "uniform", "blank_mask": True})
        assert st == 200, r
        assert r["blank_mask"] is True and r["tag"] == "uniform"
        up = os.path.join(str(seeded), "uploads")
        marked = 0
        for t in r["tiles"]:
            g = np.array(Image.open(os.path.join(up, f"{t['frame']}_gated.png")).convert("L"))
            assert (g == 255).all(), f"{t['frame']} opens with {int((g<128).sum())} marked px"
            a = np.array(Image.open(os.path.join(up, f"{t['frame']}_ascut.png")).convert("L"))
            x, y, w, h = t["box"]
            par = np.array(Image.open(
                os.path.join(_MACHINE, f"{t['parent']}_machine.png")).convert("L"))
            assert np.array_equal(a, par[y:y + h, x:x + w]), (
                f"{t['frame']}: blanking the mask also destroyed the detector's copy")
            marked += int((a < 128).sum())
        assert marked > 0, (
            "no sampled tile had any detector output at all; this test would pass "
            "trivially on a corpus where the detector predicts nothing")
        rows = [f for f in s.dataset("frames") if f.get("arm") == "uploads"]
        assert all(f.get("collection") == "GT" for f in rows), rows[0]
        assert all(f.get("sample") == "uniform" for f in rows)
        assert all(f.get("area_fraction") == 0 for f in rows), (
            "a blanked tile still measures crack in it")

        # AND THEY SURVIVE A LATER RE-MEASURE, which is the case that actually bites.
        # The stamp above is applied after the tiles are cut, so it passes whether or not
        # the fields are on remeasure's carry-through list -- I checked, by removing them
        # and watching this test stay green. The moment that matters is the FIRST TIME
        # THE LABELLER PAINTS: that re-measures the frame, and a field not carried across
        # is silently dropped, so the tile falls out of its own collection as soon as
        # someone starts work on it.
        t = r["tiles"][0]["frame"]
        m = np.array(Image.open(os.path.join(up, f"{t}_gated.png")).convert("L"))
        m[20:60, 20:120] = 0
        import io as _io
        b = _io.BytesIO(); Image.fromarray(m, mode="L").save(b, "PNG")
        st, raw = s.upload("x.png", b.getvalue(),
                           path=f"/api/mask_edit?arm=uploads&frame={t}")
        assert st == 200, raw[:300]
        rec = next(f for f in s.dataset("frames") if f.get("frame") == t)
        assert rec.get("collection") == "GT", (
            "painting a tile dropped it out of its collection")
        assert rec.get("sample") == "uniform", (
            "painting a tile lost which sample it belongs to, so the uniform draw and "
            "the top-up can no longer be told apart")


@needs_sem
def test_a_blank_tile_is_still_scorable_against_what_the_detector_said(seeded):
    """The point of keeping the as-cut copy. Draw a crack on an empty tile, mark it
    reviewed, and the comparison is against the detector -- not against the drawing."""
    with Server(seeded) as s:
        st, r = _post(s, "/api/sample_tiles",
                      {"arm": "sem/machine", "n": 3, "size": 512, "seed": 43,
                       "blank_mask": True})
        assert st == 200, r
        t = max(r["tiles"], key=lambda z: z["predicted_fraction"] or 0)
        if not (t["predicted_fraction"] or 0) > 0:
            pytest.skip("no sampled tile had a prediction to score against")
        up = os.path.join(str(seeded), "uploads")
        m = np.array(Image.open(os.path.join(up, f"{t['frame']}_gated.png")).convert("L"))
        m[100:150, 100:300] = 0                      # the labeller draws one crack
        import io as _io
        b = _io.BytesIO(); Image.fromarray(m, mode="L").save(b, "PNG")
        st, raw = s.upload("x.png", b.getvalue(),
                           path=f"/api/mask_edit?arm=uploads&frame={t['frame']}")
        assert st == 200, raw[:300]
        st, d = _post(s, "/api/review_region",
                      {"arm": "uploads", "frame": t["frame"], "box": [0, 0, 512, 512]})
        assert st == 200 and d["scorable"] is True, d.get("why_not")
        st, sc = s.json("/api/review_scores")
        reg = next(x for x in sc["regions"] if x.get("frame") == t["frame"])
        assert reg["scored_against"] == "uploads/as-cut"
        assert reg["tp"] + reg["fp"] + reg["fn"] + reg["tn"] == 512 * 512
        assert reg["fp"] > 0, (
            "the detector marked pixels the labeller did not, and none were counted as "
            "false positives -- the comparison is not reaching the as-cut copy")


@needs_sem
def test_two_restrictions_with_the_same_seed_do_not_draw_the_same_positions(seeded):
    """MEASURED FAILING. Topping up four missing specimens with four calls, all seed 7,
    put all eight tiles on just TWO box coordinates -- (3853,3216,512,512) and
    (4695,807,512,512), each used four times across four different specimens. Each call
    builds its own default_rng(7) and replays one sequence, and with pools of similar
    dimensions it lands in the same places. Those tiles were not independent draws.

    Reproducibility is the other half: the SAME request with the same seed must still
    give the same sample, or no result can be checked later."""
    specs = sorted({f["specimen"] for f in json.load(
        open(os.path.join(str(seeded), "frames.json"), encoding="utf-8"))})
    if len(specs) < 3:
        pytest.skip("need at least three specimens")
    boxes = {}
    with Server(seeded) as s:
        for sp in specs[:3]:
            st, r = _post(s, "/api/sample_tiles",
                          {"arm": "sem/machine", "n": 2, "size": 512, "seed": 7,
                           "specimens": [sp]})
            assert st == 200, r
            boxes[sp] = [tuple(t["box"]) for t in r["tiles"]]
        flat = [b for v in boxes.values() for b in v]
        assert len(set(flat)) > len(flat) // 2, (
            f"three restrictions with one seed produced {len(set(flat))} distinct boxes "
            f"out of {len(flat)}: {boxes}")

        # and the same request twice is still identical
        again = {}
        for sp in specs[:2]:
            st, r = _post(s, "/api/sample_tiles",
                          {"arm": "sem/machine", "n": 2, "size": 512, "seed": 7,
                           "specimens": [sp]})
            assert st == 200, r
            again[sp] = [tuple(t["box"]) for t in r["tiles"]]
        for sp in again:
            assert again[sp] == boxes[sp], (
                f"the same request with the same seed changed: {sp}")
