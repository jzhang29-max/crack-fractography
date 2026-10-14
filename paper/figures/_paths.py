"""Where these scripts look for the things they do not contain.

Every path here used to be an absolute path under one developer's home directory, which
made the scripts unrunnable anywhere else and would have published that directory in a
public repository. Each is now an environment variable with a default, and the defaults
assume the layout this project is developed in: the three repositories as siblings.

    <parent>/
      crack-fractography/            <- this repository
      sem-crack-detector/            <- SEM frames, masks, model bundles
      TXM_Crack_Detection_Pipeline/  <- TXM mosaics, labels, model bundles

Override any of them:

    SEM_REPO=/path/to/sem-crack-detector \\
    TXM_REPO=/path/to/TXM_Crack_Detection_Pipeline \\
    FIG_CACHE=/path/to/npy-cache \\
    PAPER_DIR=/path/to/paper \\
    FIG_DIR=/path/to/figures \\
        python mk_fig1.py

FIG_CACHE is where stage 1 writes its .npy intermediates and stages 2-3 read them; it
defaults to this directory, so a plain `python sem_fullframe.py && python mk_fig1.py`
works with no configuration. Those files are large and derived, and are not committed.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))          # .../crack-fractography
_SIBLINGS = os.path.dirname(REPO)


def _env(name, default):
    return os.path.abspath(os.path.expanduser(os.environ.get(name, default)))


SEM_REPO = _env("SEM_REPO", os.path.join(_SIBLINGS, "sem-crack-detector"))
TXM_REPO = _env("TXM_REPO", os.path.join(_SIBLINGS, "TXM_Crack_Detection_Pipeline"))
FIG_CACHE = _env("FIG_CACHE", HERE)
PAPER_DIR = _env("PAPER_DIR", os.path.join(REPO, "paper"))
FIG_DIR = _env("FIG_DIR", os.path.join(PAPER_DIR, "figures", "out"))


def require(path, what, env):
    """Fail with the variable to set, rather than with a FileNotFoundError 40 frames deep."""
    if not os.path.exists(path):
        raise SystemExit(
            f"{what} not found at {path}\n"
            f"  set {env} to its location, or place the repositories as siblings "
            f"(see the module docstring in {__file__})")
    return path


# --- the hand-labelled 512 px tiles -----------------------------------------------------
# analysis/research/tilebench.py is the ONE scorer in this project, and its own copies of
# these three locations are absolute. A figure runner repoints it at these instead, so a
# reader who sets the env vars gets the same instrument against their own checkout.
#
# TILE_LABELS is the only one with no sibling-repo default: the `*_gated.png` hand labels
# for the 512 px tiles live in the desktop app's upload store, outside all three
# repositories. Set it, or the tile cache cannot be built (an already-built cache under
# FIG_CACHE/tilecache needs no labels, which is the usual case).
TILE_META = os.path.join(HERE, "sem_tiles.json")
TILE_CACHE = _env("TILE_CACHE", os.path.join(FIG_CACHE, "tilecache"))
TILE_LABELS = _env("TILE_LABELS", os.path.join(
    "~", "Library", "Application Support", "Crack Fractography", "uploads"))
ANALYSIS = os.path.join(REPO, "analysis")


def tilebench():
    """Import analysis/research/tilebench.py with its three absolute paths repointed.

    It resolves `tiles_meta.json` from SC, its tile cache from CACHE and the hand labels
    from UP, all hard-coded to one machine. Rebinding them is the documented route in this
    codebase (analysis/detect_one.py rebinds pipeline stages the same way) and it leaves
    the archived repositories untouched. The scoring functions themselves are NOT touched:
    counts(), evaluate() and controls() are the instrument and stay as written.
    """
    import sys, shutil
    for d in (os.path.join(ANALYSIS, "research"), os.path.join(ANALYSIS, "research", "improve")):
        if d not in sys.path:
            sys.path.insert(0, d)
    import tilebench as TB
    os.makedirs(TILE_CACHE, exist_ok=True)
    # load() reads os.path.join(SC, "tiles_meta.json"); point SC at a directory holding the
    # committed manifest rather than editing the archived-by-convention analysis module.
    staged = os.path.join(TILE_CACHE, "tiles_meta.json")
    if not os.path.exists(staged) or os.path.getmtime(staged) < os.path.getmtime(TILE_META):
        shutil.copyfile(TILE_META, staged)
    TB.SC, TB.CACHE, TB.UP = TILE_CACHE, TILE_CACHE, TILE_LABELS
    return TB
