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
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

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
             "multipart", "python_multipart",
             "objc", "Foundation", "AppKit", "WebKit", "Quartz", "Security",
             "UniformTypeIdentifiers"])

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
skimage_data = [(src, dst) for src, dst in collect_data_files("skimage")
                if os.sep + "data" + os.sep not in src
                or os.path.splitext(src)[1].lower() not in
                (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".npy", ".npz")]

datas = [
    (os.path.join(REPO, "app", "templates"), "app/templates"),
    (os.path.join(REPO, "app", "static"), "app/static"),
    (os.path.join(REPO, "docs"), "docs"),
    (os.path.join(REPO, "README.md"), "."),
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
    excludes=["matplotlib", "torch", "pandas", "tkinter.test", "pytest", "IPython",
              "notebook", "sklearn", "cv2"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Crack Fractography",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               name="Crack Fractography")

app = BUNDLE(coll, name="Crack Fractography.app",
             icon=None, bundle_identifier="edu.stanford.crack-fractography",
             info_plist={
                 "CFBundleShortVersionString": "1.0.0",
                 "NSHighResolutionCapable": True,
                 # It has a window, so it belongs in the Dock and can be quit like an app.
                 "LSBackgroundOnly": False,
                 "LSMinimumSystemVersion": "12.0",
             })
