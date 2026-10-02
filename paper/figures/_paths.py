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
