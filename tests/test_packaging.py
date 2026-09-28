#!/usr/bin/env python3
"""What packaging can silently break, checked here rather than discovered in a build.

Each test corresponds to a way the app can look fine and be wrong:
  - the vendored measurement copy drifting from the repo it was copied from
  - a path that only resolves because a dev symlink happens to exist
  - the bundle missing a file that is loaded by path rather than imported
"""
import hashlib
import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "analysis"))

from app import paths as P            # noqa: E402


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def test_vendored_copy_matches_the_repo_it_came_from():
    """The bundled implementation must be byte-identical to the SEM repo's.

    If this fails the fix is `python3 packaging/vendor.py`, not editing _vendor by hand: the
    copy is a copy, and an edited one is the second implementation the whole design forbids.
    """
    sem = P.sem_repo()
    if not sem:
        pytest.skip("no SEM repo configured")
    man = json.load(open(os.path.join(REPO, "analysis", "_vendor", "MANIFEST.json")))
    for rel, recorded in man["files"].items():
        live = os.path.join(sem, *rel.split("/"))
        copy = os.path.join(REPO, "analysis", "_vendor", os.path.basename(rel))
        assert os.path.exists(copy), f"{copy} is missing -- run packaging/vendor.py"
        assert md5(live) == recorded, (
            f"{rel} changed since it was vendored -- run packaging/vendor.py")
        assert md5(copy) == recorded, f"{copy} was edited -- it must be a copy"


def test_measurement_falls_back_without_a_sem_repo():
    """A downloaded app has no checkout. It must still measure a mask."""
    code = (
        "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
        "from app import paths as P\n"
        "P.sem_repo = lambda: None\n"
        "import shared_impl\n"
        "print(shared_impl.provenance()['source'])\n"
    ) % (REPO, os.path.join(REPO, "analysis"))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd=REPO, env=dict(os.environ, FRACTOGRAPHY_DATA="/tmp/_frac_test"))
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip() == "bundled copy", r.stdout


def test_every_file_loaded_by_path_is_in_the_bundle():
    """Files read at runtime by path are invisible to PyInstaller's module graph, so the
    spec has to name them. Anything loaded by path and NOT under a datas entry ships
    missing and fails on first use."""
    spec = open(os.path.join(REPO, "packaging", "fractography.spec")).read()
    for needed in ("app/templates", "app/static", "analysis_files", "analysis/_vendor"):
        assert needed in spec, f"{needed} is not in the spec's datas"
    # And it must NOT sweep the whole analysis directory: that ships analysis/out.
    assert '(os.path.join(REPO, "analysis"), "analysis")' not in spec, (
        "the spec copies all of analysis/, which includes analysis/out")
    for f in ("analysis/_vendor/extended_features.py", "analysis/_vendor/MANIFEST.json",
              "analysis/detect_one.py", "app/templates/index.html", "app/static/app.js"):
        assert os.path.exists(os.path.join(REPO, f)), f


def test_data_dir_is_writable_and_outside_the_code():
    """A bundle's code directory is read-only and is replaced on update. Writing
    measurements there would either fail or be destroyed."""
    assert P.OUT == P.DATA
    assert P.UPLOADS.startswith(P.DATA)
    if P.FROZEN:
        assert not P.DATA.startswith(P.RES)


def test_no_module_hardcodes_a_sibling_repo_path():
    """The whole point of paths.py. A reintroduced data/sem join works in a checkout and is
    a dangling path in an app, which is the failure that is hardest to notice."""
    bad = []
    for sub in ("analysis", "app"):
        d = os.path.join(REPO, sub)
        for name in sorted(os.listdir(d)):
            if not name.endswith(".py") or name in ("paths.py", "detect_one.py"):
                continue
            src = open(os.path.join(d, name)).read()
            for i, line in enumerate(src.splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                if '"data", "sem"' in line or '"data", "txm' in line or "data/sem" in line:
                    bad.append(f"{sub}/{name}:{i}: {line.strip()}")
    assert not bad, "hardcoded sibling paths:\n  " + "\n  ".join(bad)


def test_configuring_a_repo_switches_the_implementation_without_a_restart():
    """The resolution is cached; a config change has to invalidate it.

    Before the fix, a mask uploaded before the SEM repo was set left the process pinned to
    the bundled copy for the rest of its life, while /api/health still reported the repo as
    configured.
    """
    sem = P.sem_repo()
    if not sem:
        pytest.skip("no SEM repo configured")
    code = (
        "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
        "from app import paths as P\n"
        "real = P.sem_repo\n"
        "P.sem_repo = lambda: None\n"
        "import shared_impl\n"
        "a = shared_impl.provenance()['source']\n"     # resolves with no repo
        "P.sem_repo = real\n"
        "b = shared_impl.provenance()['source']\n"     # still cached
        "shared_impl.reset()\n"
        "c = shared_impl.provenance()['source']\n"     # resolves again
        "print(a, '|', b, '|', c)\n"
    ) % (REPO, os.path.join(REPO, "analysis"))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd=REPO, env=dict(os.environ, FRACTOGRAPHY_DATA="/tmp/_frac_test"))
    assert r.returncode == 0, r.stderr[-2000:]
    a, b, c = [x.strip() for x in r.stdout.strip().split("|")]
    assert a == "bundled copy"
    assert b == "bundled copy", "cached, as designed"
    assert c == "sem repo", "reset() must re-resolve to the live repo"


def test_the_native_window_backend_is_importable():
    """The app window is pywebview over WKWebView. If the backend is missing the launcher
    falls back to the system browser and still 'works', which is exactly the kind of
    downgrade that ships unnoticed -- so it is asserted rather than trusted."""
    import importlib
    try:
        importlib.import_module("webview")
    except ImportError:
        pytest.fail("pywebview is not installed; the packaged app would open a browser "
                    "instead of its own window")
    if sys.platform == "darwin":
        importlib.import_module("WebKit")      # the Cocoa backend pywebview loads by name


def test_downloads_do_not_rely_on_navigation():
    """WKWebView has no download manager, so `location.href = <a CSV url>` shows the CSV as
    text instead of saving it. Both download buttons must go through the bridge."""
    js = open(os.path.join(REPO, "app", "static", "app.js")).read()
    import re
    for m in re.finditer(r"location\.href\s*=\s*`?/?api/[^\n]*", js):
        pytest.fail(f"a download still navigates: {m.group(0)[:90]}")
    assert "window.pywebview.api.save" in js


def test_uploading_maintains_all_three_dataset_files():
    """The upload path writes frames.json and cracks.json. It used to skip specimens.json,
    so an upload added a frame and no specimen -- and the specimen card, the first card on
    the page, simply vanished for the uploads arm, which is the only arm a downloaded copy
    has until a SEM repo is configured."""
    import re
    src = open(os.path.join(REPO, "app", "server.py")).read()
    up = src[src.index("async def upload("):src.index("def _rebuild_uploads_specimen")]
    assert "_rebuild_uploads_specimen()" in up, "upload must maintain the specimen table"
    reb = src[src.index("def _rebuild_uploads_specimen"):]
    # And it must only ever touch the uploads arm: a web request that can rewrite the
    # measured arms' records would let an upload silently alter published numbers.
    assert 'r.get("arm") != "uploads"' in reb
    assert re.search(r'summarise\(\s*"uploads"', reb)


def test_the_licence_and_attribution_ship_with_the_binary():
    """The bundle is 118 MB of third-party scientific and web libraries distributed
    publicly. NOTICE names them and was missing from the spec's datas for three releases, so
    the only LICENSE files inside the app were the dependencies' own.

    THE FIRST VERSION OF THIS TEST CHECKED THE SPEC'S TEXT and nothing else, so it reported
    green while the built bundle sitting in dist/ had neither file -- the spec had been
    fixed three minutes after that build. A guard that measures the instruction rather than
    the result is a guard that passes in exactly the case it exists to catch. It now asserts
    on the BUNDLE whenever one is present, and falls back to the spec only when there is
    nothing built to look at.
    """
    for f in ("LICENSE", "NOTICE"):
        assert os.path.exists(os.path.join(REPO, f)), f"{f} missing from the repo"

    app = os.path.join(REPO, "dist", "Crack Fractography.app", "Contents", "Resources")
    if os.path.isdir(app):
        for f in ("LICENSE", "NOTICE"):
            assert os.path.exists(os.path.join(app, f)), (
                f"{f} is not in the BUILT bundle at {app} -- rebuild before releasing")
    else:
        spec = open(os.path.join(REPO, "packaging", "fractography.spec")).read()
        for f in ("LICENSE", "NOTICE"):
            assert f'"{f}"' in spec, f"{f} is not in the spec's datas, so it will not ship"


def test_the_internal_research_note_is_not_in_the_bundle():
    """docs/PRACTICE_AND_PRIOR_ART.md records which novelty framings died, which claims were
    withdrawn, and unpublished dataset statistics. It was the only file in the whole bundle
    carrying the owner's absolute home path. It belongs in the repo, not inside a public
    download."""
    app = os.path.join(REPO, "dist", "Crack Fractography.app", "Contents", "Resources")
    if not os.path.isdir(app):
        pytest.skip("nothing built")
    assert not os.path.exists(os.path.join(app, "docs", "PRACTICE_AND_PRIOR_ART.md")), (
        "the internal research note is inside the shipped bundle")


def test_no_owner_home_path_is_baked_into_the_bundle():
    """An absolute /Users/<name> path in a public binary leaks the build machine's layout.
    One file had it; this asserts none does."""
    import subprocess
    app = os.path.join(REPO, "dist", "Crack Fractography.app")
    if not os.path.isdir(app):
        pytest.skip("nothing built")
    home = os.path.expanduser("~")
    r = subprocess.run(["grep", "-rIl", home, app], capture_output=True, text=True)
    hits = [x for x in r.stdout.splitlines() if x.strip()]
    assert not hits, "owner path baked into:\n  " + "\n  ".join(hits[:6])
