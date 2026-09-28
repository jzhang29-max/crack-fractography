# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec. Build with packaging/build.sh, not directly.

Three things here are not boilerplate and each one is a bug if dropped.

ANALYSIS IS SHIPPED AS FILES, NOT AS FROZEN MODULES. measure.py and its neighbours are
imported by inserting <resources>/analysis on sys.path at runtime, and detect_one.py is
executed as a SCRIPT by the SEM repo's interpreter -- a different Python than this bundle's.
A frozen module cannot be run by another interpreter, so the directory is copied in as data
and stays readable .py.

SKIMAGE AND SCIPY NEED HELP. Both resolve submodules lazily, so the module graph misses what
is only reached through a string. collect_submodules pulls them in; without it the app
starts and then fails on the first mask with a ModuleNotFoundError.

THE VENDORED COPY IS DATA. shared_impl loads it from a file path with importlib, so it has
to exist as a file, not as a frozen module.
"""
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

MACOS = sys.platform == "darwin"

REPO = os.path.abspath(os.path.join(SPECPATH, ".."))

# pywebview loads its macOS backend by name at runtime, so the module graph never sees it.
# Without these the app starts and falls back to the browser -- which looks like it works.
hidden = (collect_submodules("webview")
          + collect_submodules("skimage")
          + collect_submodules("scipy.ndimage")
          + collect_submodules("scipy.spatial")
          + ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.loops.asyncio",
             "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
             "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on",
             "multipart", "python_multipart"]
          # pyobjc exists only on macOS. Naming it unconditionally makes the Linux and
          # Windows builds fail at analysis rather than produce a working app.
          + (["objc", "Foundation", "AppKit", "WebKit", "Quartz", "Security",
              "UniformTypeIdentifiers"] if MACOS else []))

# analysis/ is listed FILE BY FILE, not as a directory. Copying the directory swept in
# analysis/out -- 30 MB of measured JSON plus every mask ever uploaded here -- which a
# frozen build never even reads, because output goes to the per-user data directory. It was
# 20% of the download and it was somebody's measurements travelling inside a code bundle.
analysis_files = [
    (os.path.join(REPO, "analysis", f), "analysis")
    for f in sorted(os.listdir(os.path.join(REPO, "analysis")))
    if f.endswith(".py")
] + [
    (os.path.join(REPO, "analysis", "_vendor", f), "analysis/_vendor")
    for f in ("extended_features.py", "MANIFEST.json", "__init__.py")
]

# skimage ships 7.4 MB of sample photographs (astronaut, coffee, chelsea...) behind
# skimage.data. Nothing here calls it: the imports are measure, morphology and filters. The
# MODULE stays -- only the pictures are dropped -- so an accidental import still resolves.
# skimage ships sample photographs and fixtures behind skimage.data. Nothing here calls it
# -- the imports are measure, morphology and filters -- so the payload goes and the MODULE
# stays, leaving an accidental import resolving.
#
# KEEP-LIST, not a block-list. Excluding known raster extensions left a 51 KB OpenCV
# face-detection cascade (.xml) and a 4 KB joke GIF in a crack-measurement app, because a
# block-list only stops what it was told about. Only the two .npy structuring-element
# tables morphology actually loads are kept.
_SKIMAGE_DATA_KEEP = ("ball.npy", "disk.npy")


def _skimage_keep(src):
    if os.sep + "data" + os.sep not in src:
        return True
    name = os.path.basename(src)
    return name in _SKIMAGE_DATA_KEEP or name.endswith(".pyi")


skimage_data = [(src, dst) for src, dst in collect_data_files("skimage")
                if _skimage_keep(src)]

datas = [
    (os.path.join(REPO, "app", "templates"), "app/templates"),
    (os.path.join(REPO, "app", "static"), "app/static"),
    # docs/ is NOT bundled. PRACTICE_AND_PRIOR_ART.md is an internal research and
    # novelty-strategy note -- withdrawn claims, which framings died, unpublished dataset
    # statistics -- and it was the only file in the whole 686-file bundle containing the
    # owner's absolute home path. It stays in the repo, where a reader who wants it can
    # find it, rather than inside a public download.
    (os.path.join(REPO, "README.md"), "."),
    # LICENCE AND ATTRIBUTION SHIP WITH THE BINARY, not just with the repo. The bundle is
    # 118 MB of numpy, scipy, scikit-image, Pillow, FastAPI, uvicorn, pywebview and pyobjc,
    # distributed publicly -- NOTICE exists to name them and was never in this list, so
    # three releases went out with no attribution inside the app at all. The only LICENSE
    # files in the bundle were the dependencies' own.
    (os.path.join(REPO, "LICENSE"), "."),
    (os.path.join(REPO, "NOTICE"), "."),
] + analysis_files + skimage_data

a = Analysis(
    [os.path.join(REPO, "packaging", "launcher.py")],
    pathex=[REPO],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    # Nothing here runs a model or plots server-side: the detector lives in the SEM repo and
    # the figures are hand-built SVG. Excluding these is ~300 MB off the bundle.
    # tkinter is excluded outright, not just its tests: the launcher used it for a control
    # window before pywebview replaced that, and it has zero references now. It was still
    # pulling 6.9 MB of Tcl/Tk runtime -- 5.9% of the download -- for a toolkit nothing
    # imports.
    excludes=["matplotlib", "torch", "pandas", "tkinter", "_tkinter", "tkinter.test",
              "pytest", "IPython", "notebook", "sklearn", "cv2"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Crack Fractography",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               name="Crack Fractography")

# BUNDLE is the .app wrapper and exists only on macOS. Elsewhere COLLECT's directory IS
# the deliverable, and naming BUNDLE there produces a warning and no bundle.
if MACOS:
    app = BUNDLE(coll, name="Crack Fractography.app",
                 icon=None, bundle_identifier="edu.stanford.crack-fractography",
                 info_plist={
                     "CFBundleShortVersionString": "1.3.0",
                     "NSHighResolutionCapable": True,
                     # It has a window, so it belongs in the Dock and quits like an app.
                     "LSBackgroundOnly": False,
                     "LSMinimumSystemVersion": "12.0",
                 })
