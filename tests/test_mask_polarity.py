#!/usr/bin/env python3
"""An inverted mask must not measure silently.

This app's convention is CRACK = BLACK, which is how a crack looks in a micrograph and how
every mask in the corpus is stored. A mask saved the other way round is the likeliest
mistake a new user makes with a black-and-white image, and it has no other symptom: the
upload succeeds, every field is populated, "ok" is true, and the numbers are exactly
backwards. Measured on a 1400x1400 test mask with 1.46% of its pixels marked -- inverted,
it came back as 98.54% of the frame in ONE crack of mean width 102 px, and the two readings
summed to 1.000000.

The threshold is not a guess: over the 357 measured frames of the reference corpus the area
fraction runs to a maximum of 0.414 with a median of 0.028, so nothing real approaches half
a frame, and above 0.5 the "crack" is the majority phase and the background the minority one.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liveserver import Server, mask_png   # noqa: E402


def _up(s_, name, blob):
    """Server.upload returns (status, raw_bytes); give the tests the parsed body."""
    import json as _json
    st, raw = s_.upload(name, blob)
    assert st == 200, (st, raw[:300])
    return _json.loads(raw)


def _invert(png_bytes):
    """Flip a greyscale PNG's polarity, via the same stdlib path mask_png uses."""
    import io as _io
    from PIL import Image
    import numpy as np
    a = np.array(Image.open(_io.BytesIO(png_bytes)).convert("L"))
    out = _io.BytesIO()
    Image.fromarray(255 - a).save(out, format="PNG")
    return out.getvalue()


def test_a_normal_mask_is_not_flagged(tmp_path):
    with Server(tmp_path / "d") as s:
        d = _up(s, "plain.png", mask_png())
        assert d["ok"], d
        assert d["area_fraction"] < 0.5, d["area_fraction"]
        assert not d.get("polarity_warning"), d["polarity_warning"]


def test_an_inverted_mask_is_flagged_and_still_measured(tmp_path):
    with Server(tmp_path / "d") as s:
        d = _up(s, "flipped.png", _invert(mask_png()))
        assert d["ok"], d
        # Still measured -- it is not the app's place to refuse a mask a user insists on.
        assert d["area_fraction"] > 0.5, d["area_fraction"]
        w = d.get("polarity_warning")
        assert w, "an inverted mask measured over half the frame and said nothing"
        assert "CRACK = BLACK" in w, w
        assert "41.4" in w, "the warning should say what the corpus maximum actually is"


def test_the_two_polarities_are_complements(tmp_path):
    """The signature of the defect: the right answer and the wrong one sum to the frame."""
    with Server(tmp_path / "d") as s:
        a = _up(s, "a.png", mask_png())["area_fraction"]
        b = _up(s, "b.png", _invert(mask_png()))["area_fraction"]
    assert abs((a + b) - 1.0) < 1e-6, (a, b, a + b)


def test_the_threshold_sits_between_the_corpus_maximum_and_one_half():
    """A guard whose constant drifted above 0.5 or below the real data would be useless."""
    sys.path.insert(0, REPO)
    from app.server import POLARITY_WARN_ABOVE
    assert 0.414 < POLARITY_WARN_ABOVE <= 0.5, POLARITY_WARN_ABOVE
