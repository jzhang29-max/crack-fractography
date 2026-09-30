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


def test_the_app_ships_its_own_icon_and_not_pyinstaller_s():
    """Three releases went out wearing PyInstaller's stock Python-on-a-floppy, which tells a
    materials researcher that this is a Python script rather than what it is.

    Asserts on the BUNDLE when one exists, for the same reason the licence test does: the
    first version of that guard read the spec's text and reported green while the bundle in
    dist/ had neither file. Here the equivalent trap is real -- `icon=` can name a path that
    does not exist and PyInstaller falls back to its own default with a warning, so the
    spec mentioning the file proves nothing about what shipped.
    """
    icns = os.path.join(REPO, "packaging", "AppIcon.icns")
    assert os.path.exists(icns), "packaging/AppIcon.icns is missing, so the build has no icon"
    assert os.path.getsize(icns) > 50_000, "an .icns this small is missing its retina entries"
    with open(icns, "rb") as fh:
        assert fh.read(4) == b"icns", "not an .icns file"

    spec_path = os.path.join(REPO, "packaging", "fractography.spec")
    assert "AppIcon.icns" in open(spec_path).read(), "the spec does not point at an icon"

    app = os.path.join(REPO, "dist", "Crack Fractography.app", "Contents")
    if not os.path.isdir(app):
        return
    # A BUNDLE OLDER THAN THE ICON IS STALE, NOT WRONG, and the difference matters because
    # build.sh runs the suite BEFORE it rebuilds. The first version of this test asserted
    # on any bundle it found, so a stale bundle failed the gate that guards the rebuild
    # that would have fixed it -- the build refused to run at all. build.sh re-runs this
    # file after a successful build, which is where the assertions below actually bite.
    if os.path.getmtime(app) < os.path.getmtime(icns):
        return

    res = os.path.join(app, "Resources")
    shipped = [f for f in os.listdir(res) if f.endswith(".icns")]
    assert shipped, f"no .icns in the BUILT bundle at {res} -- rebuild before releasing"
    # And it must be OURS. PyInstaller's placeholder is a different file; comparing bytes is
    # the only check that distinguishes "an icon shipped" from "the icon we drew shipped".
    ours = open(icns, "rb").read()
    assert any(open(os.path.join(res, f), "rb").read() == ours for f in shipped), (
        f"the bundle's icon ({shipped}) is not packaging/AppIcon.icns -- PyInstaller fell "
        f"back to its own default, which it does silently when icon= cannot be read")


def test_no_test_spawns_a_hardcoded_venv_interpreter():
    """A subprocess spawned as `<repo>/.venv/bin/python3` passes locally and cannot work on
    CI, which pip-installs into the runner's own Python and never creates a repo venv.

    That is the worst shape a test bug can take: green on the machine where it was written,
    red everywhere else, and nothing in the local run can tell the difference. It took five
    tests down on every push for a day before anyone looked at the badge. sys.executable is
    correct by construction -- it is the interpreter already running the tests, so it has
    exactly the packages pytest was able to import.

    Parsed rather than grepped. The first version of this guard was a regex over every
    line, which flagged two module docstrings that merely SAY how to run the file by hand
    and its own pattern string -- three false positives and no true one. It now looks only
    where the defect can live: the argument list of a subprocess call.
    """
    import ast
    here = os.path.dirname(os.path.abspath(__file__))
    SPAWN = {"run", "Popen", "call", "check_call", "check_output"}
    bad = []
    for f in sorted(os.listdir(here)):
        if not f.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(here, f)).read(), filename=f)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name not in SPAWN:
                continue
            for lit in ast.walk(node.args[0]):
                if isinstance(lit, ast.Constant) and isinstance(lit.value, str) \
                        and ".venv" in lit.value:
                    bad.append(f"{f}:{node.lineno}: spawns {lit.value!r}")
    assert not bad, ("tests must spawn sys.executable, not a hardcoded venv "
                     "(CI has no repo venv):\n  " + "\n  ".join(bad))


# --- WHAT A PERSON ACTUALLY DOWNLOADS --------------------------------------------------
def _workflow():
    return open(os.path.join(REPO, ".github", "workflows", "build.yml")).read()


def test_every_platform_produces_a_single_downloadable_file():
    """dist/ was uploaded raw as a CI artifact: a folder, 14-day retention, reachable only
    by someone logged into GitHub who knows to open a workflow run. That is not a download.
    Each platform now gets the file its users expect."""
    w = _workflow()
    for token in (".dmg", "Windows-x64.zip", "Linux-x86_64.tar.gz"):
        assert token in w, f"no {token} is built"
    assert "make_dmg.sh" in w
    assert os.access(os.path.join(REPO, "packaging", "make_dmg.sh"), os.X_OK), (
        "make_dmg.sh is not executable, so the runner cannot invoke it")


def test_the_release_attaches_them_and_fails_if_one_is_missing():
    """A release carrying two of three platforms should fail loudly. Silently shipping a
    partial release is how a platform quietly stops being supported."""
    # NO YAML PARSER. pyyaml is not in requirements.txt, so importing it here would pass
    # on a machine that happens to have it and fail on CI with an ImportError -- the same
    # green-locally-red-on-CI shape as the hardcoded venv path this repo shipped once
    # before. The assertions are about text that must be present, so read the text.
    w = _workflow()
    rel = w[w.index("\n  release:"):]
    assert "needs: build" in rel
    assert "refs/tags/v" in rel, "the release job must only run on a version tag"
    assert "contents: write" in rel
    assert "fail_on_unmatched_files: true" in rel
    assert "all three platforms are present" in rel


def test_the_packaged_copy_is_started_not_just_the_build_directory():
    """The smoke test ran on dist/, not on the archive. Packaging can produce a file that
    unpacks to a broken tree -- a dropped permission bit, a missing symlink -- and that
    would have passed."""
    w = _workflow()
    assert "the packaged copy starts" in w
    i = w.index("the packaged copy starts")
    assert "smoke_check.py" in w[i:i + 2000], "the unpacked copy is never run"
    assert "_unpack" in w[i:i + 2000]


def test_the_dmg_carries_the_quarantine_instruction():
    """An unsigned app makes macOS say it is damaged. If the only place that is explained
    is the release notes, the person who downloaded the dmg a week ago has no way back to
    it -- so it ships inside the disk image."""
    sh = open(os.path.join(REPO, "packaging", "make_dmg.sh")).read()
    assert "com.apple.quarantine" in sh
    assert "READ ME FIRST" in sh
    assert "/Applications" in sh, "no Applications symlink, so it is not drag-to-install"


def test_the_readme_describes_the_files_that_are_actually_published():
    """The install section said "unzip" and treated Windows and Linux as build-it-yourself,
    which stopped being true the moment the release started carrying all three. Prose going
    stale under a change is a recurring defect here."""
    r = open(os.path.join(REPO, "README.md")).read()
    inst = r[r.index("## Install"):r.index("### What works without anything else installed")]
    for token in (".dmg", "-Windows-x64.zip", "-Linux-x86_64.tar.gz"):
        assert token in inst, f"the install section does not mention {token}"
    assert "com.apple.quarantine" in inst
    assert "unzip, drag" not in inst, "the old zip-only instruction survives"


def test_the_windows_exe_is_given_an_icon():
    """`icon=` was passed only inside BUNDLE(), which exists only on macOS, so the published
    .exe wore PyInstaller's placeholder in Explorer and on the taskbar. Nothing failed: the
    only icon assertion in this file looks inside the .app's Resources, which Windows has
    no equivalent of."""
    spec = open(os.path.join(REPO, "packaging", "fractography.spec")).read()
    exe = spec[spec.index("exe = EXE("):spec.index("coll = COLLECT(")]
    assert "AppIcon.ico" in exe, "EXE() is not given a Windows icon"
    ico = os.path.join(REPO, "packaging", "AppIcon.ico")
    assert os.path.exists(ico), "AppIcon.ico is not committed"
    from PIL import Image
    im = Image.open(ico)
    assert im.size[0] >= 256, f"the .ico's largest size is {im.size}; too small for the taskbar"


def test_the_job_that_publishes_also_revendors_and_runs_the_bundle_guards():
    """packaging/build.sh re-vendors and runs the suite before building; the CI job that
    produces the PUBLISHED artifacts ran pyinstaller directly -- no vendor.py, no pytest.
    The `test` job cannot cover it either: fresh ubuntu checkout, no SEM repo, so the drift
    check skips itself. A tag pushed after the sibling repo changed would publish installers
    measuring with the previous implementation, green, with /api/health reporting
    drift=False because there was nothing to compare against."""
    w = _workflow()
    build = w[w.index("\n  build:"):w.index("\n  release:")]
    assert "packaging/vendor.py" in build, "the build job never re-vendors"
    assert "tests/test_packaging.py" in build, "the build job never runs the bundle guards"
    # And in the right order: guards AFTER the build they are about.
    assert build.index("pyinstaller") < build.index("tests/test_packaging.py"), (
        "the bundle guards run before the bundle exists, which is how this repo once "
        "asserted on a stale bundle and deadlocked the build")


def test_make_dmg_reads_the_version_and_arch_from_the_bundle():
    """Run by hand with no arguments -- which the README now instructs -- it produced
    CrackFractography-0.0.0-macOS-arm64.dmg around an app whose Info.plist said 1.17.0,
    with a READ ME FIRST headed 0.0.0, and labelled an Intel build arm64."""
    sh = open(os.path.join(REPO, "packaging", "make_dmg.sh")).read()
    assert "CFBundleShortVersionString" in sh, "the version is still guessed"
    assert "lipo -archs" in sh or "uname -m" in sh, "the architecture is still a literal"
    assert "-macOS-arm64.dmg}" not in sh, "arm64 is still hardcoded in the default name"


def test_the_readme_does_not_document_the_deleted_mark_modes():
    """It described "two tools" with **Edit mask** and **Full tool** as things to pick
    between, and was the only place either label still appeared -- so a reader went looking
    for a control that no longer exists."""
    r = open(os.path.join(REPO, "README.md")).read()
    sec = r[r.index("## Marking happens in this window"):]
    sec = sec[:sec.index("\n## ")]
    assert "**Edit mask**" not in sec and "**Full tool**" not in sec, (
        "the README still presents the deleted segmented pair")
    assert "picks per frame" in sec or "per frame" in sec


def test_the_readme_covers_the_windows_first_launch_block_too():
    """The macOS quarantine note is prominent and ships inside the dmg; the Windows install
    row ended at "run Crack Fractography.exe", which is exactly where SmartScreen stops an
    unsigned binary."""
    r = open(os.path.join(REPO, "README.md")).read()
    assert "SmartScreen" in r
    assert "Run anyway" in r
