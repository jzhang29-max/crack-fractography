#!/usr/bin/env python3
"""Segment ONE micrograph and write its crack mask. Run under the SEM repo's interpreter.

This is the detect half of the pipeline. It exists as a separate script, invoked as a
subprocess, for one reason: the detector needs pandas, cv2 and a model bundle that live in
the SEM repo's venv, and this app deliberately does not carry them -- its requirements.txt
is numpy/scipy/skimage/fastapi and nothing heavier. Importing across venvs is not possible;
shelling out with the right interpreter is.

Corrections are suppressed, matching the sem/machine arm: an uploaded image has no human
corrections, so applying any would be meaningless, and the mask this writes is the
detector's own answer.

Usage: <sem-venv>/bin/python3 detect_one.py <image.tif> <out_mask.png>
"""
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: detect_one.py <image> <out_mask.png> <sem_repo>")
    src, dst, sem_repo = sys.argv[1], sys.argv[2], sys.argv[3]
    sys.path.insert(0, os.path.join(sem_repo, "interior_active_learning", "code"))
    sys.path.insert(0, os.path.join(sem_repo, "code"))

    import unified_pipeline as up
    import common
    up.load_correction_mask = lambda *a, **k: None
    common.load_correction_mask = lambda *a, **k: None
    up.load_hard_overrides = lambda *a, **k: {}

    # run_unified_pipeline resolves its input from ORIGINAL_DIR by name, so the caller stages
    # the upload there under a temporary name and passes the stem.
    stem = os.path.splitext(os.path.basename(src))[0]
    st = up.run_unified_pipeline(stem)
    labeled, df = st["labeled"], st["df"]
    keep = set(df.loc[df["IsCrack"] == True, "Label"].tolist())      # noqa: E712
    m = np.isin(labeled, list(keep)) if keep else np.zeros(labeled.shape, bool)
    Image.fromarray(np.where(m, 0, 255).astype(np.uint8), "L").save(dst, optimize=True)
    print(f"{m.shape[1]}x{m.shape[0]} {100 * float(m.mean()):.4f}")


if __name__ == "__main__":
    main()
