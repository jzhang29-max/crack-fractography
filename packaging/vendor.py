#!/usr/bin/env python3
"""Copy the SEM repo's shared measurement code into analysis/_vendor, and record its hash.

WHY A COPY EXISTS AT ALL. measure.py imports crack_shape_measurements from the SEM repo and
the header there says, correctly, never to reimplement it: a second implementation of mean
width or max width is a silent mismatch with every number that repo has published. That
argument is about REIMPLEMENTING. A downloadable app still has to be able to measure a mask
the user drops on it without a second repo installed, and it cannot import from a checkout
that is not there.

So: a byte copy, never an edit, with three things keeping it honest.

  1. The live repo WINS. measure.py imports from the SEM checkout whenever one is
     configured; the vendored copy is the fallback, so the developer workflow and every
     published number keep running on the original file.
  2. The hash is recorded here and checked at runtime. If the SEM repo's copy changes and
     this one is not re-vendored, the app says so instead of quietly measuring with an old
     implementation -- which is exactly the failure the "never copy" rule is guarding.
  3. tests/test_vendor.py fails on drift, so it is caught where it is introduced.

Run after any change to the upstream file:  python3 packaging/vendor.py
"""
import hashlib
import json
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
VENDOR = os.path.join(REPO, "analysis", "_vendor")
MANIFEST = os.path.join(VENDOR, "MANIFEST.json")

#: Files copied verbatim from the SEM repo, as <relative path in that repo>.
FILES = ["interior_active_learning/code/extended_features.py"]


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def main():
    # --if-available: succeed when there is no SEM repo instead of refusing.
    #
    # Exiting non-zero on a missing repo is right for a person running this by hand -- you
    # asked to re-vendor and there is nothing to vendor FROM. It is wrong for CI, which has
    # no SEM checkout on purpose, and that mismatch broke all three build jobs when this
    # was added to the workflow on the assumption that it would no-op. It does not; the
    # assumption was never checked.
    #
    # WHAT CI CAN AND CANNOT VERIFY, since the flag makes it easy to overclaim: with no SEM
    # repo present, nothing on a runner can detect that the vendored copy is stale, because
    # the copy is the only implementation there. The drift check is a LOCAL guarantee, made
    # by packaging/build.sh on a machine that has both. This step exists so the build path
    # re-vendors wherever a repo IS reachable, and so the bundle guards run against the
    # bundle that was just built.
    optional = "--if-available" in sys.argv
    sys.path.insert(0, REPO)
    from app import paths as P
    sem = P.sem_repo()
    if not sem:
        msg = "no SEM repo found -- vendoring needs the source of truth"
        if optional:
            print(msg + "; leaving the committed copy as-is (--if-available)")
            return 0
        sys.exit(msg)
    os.makedirs(VENDOR, exist_ok=True)
    man = {"source_repo": os.path.basename(sem), "files": {}}
    for rel in FILES:
        src = os.path.join(sem, rel)
        if not os.path.exists(src):
            sys.exit(f"missing upstream file: {src}")
        dst = os.path.join(VENDOR, os.path.basename(rel))
        shutil.copyfile(src, dst)
        man["files"][rel] = md5(src)
        print(f"  vendored {rel} -> analysis/_vendor/{os.path.basename(rel)}  {md5(src)}")
    with open(MANIFEST, "w") as fh:
        json.dump(man, fh, indent=2)
    open(os.path.join(VENDOR, "__init__.py"), "w").close()
    print(f"  wrote {MANIFEST}")


if __name__ == "__main__":
    main()
