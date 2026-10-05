#!/usr/bin/env bash
# Build the double-clickable app.   ./packaging/build.sh
#
# Output: dist/Crack Fractography.app  (macOS) or dist/Crack Fractography/ (elsewhere)
set -euo pipefail
cd "$(dirname "$0")/.."

VENV="${VENV:-.venv}"
PY="$PWD/$VENV/bin/python3"
[ -x "$PY" ] || { echo "no venv -- run ./run once first"; exit 1; }

echo "==> build dependencies"
"$PY" -m pip install --quiet -r packaging/requirements-build.txt

# Re-vendor before every build. The bundled copy of the shared measurement code is what a
# downloaded app measures with, so a build that skipped this would ship the previous
# version's implementation while the tests passed against the current one.
#
# --if-available, for the same reason the CI workflow passes it. Plain `vendor.py` exits 1
# when no SEM repo is reachable, which is right for a person who typed it deliberately and
# wrong here: this is the command the README tells a reader to run, and `set -e` turned
# that exit into "the documented build aborts at step two on any machine without a second
# checkout". That is every clone of this repository, and it is the only repository a user
# of the app needs.
#
# What is given up is nothing that was being enforced. The drift check is a LOCAL
# guarantee: where a repo IS reachable this still re-copies and rewrites the manifest, so
# the build keeps it; where none is, there is no second implementation to drift from and
# the committed copy is the only one there is. The hash is verified separately, at runtime
# and in the test suite, against whatever copy ships.
echo "==> vendoring the shared measurement code"
"$PY" packaging/vendor.py --if-available

echo "==> tests (a build from failing code is a build nobody can trust)"
"$PY" -m pytest -q tests/ || { echo "  tests failed -- not building"; exit 1; }

echo "==> pyinstaller"
rm -rf build dist
"$PY" -m PyInstaller --noconfirm --clean packaging/fractography.spec

APP="dist/Crack Fractography.app"
if [ -d "$APP" ]; then
  # Unsigned apps are quarantined on download and Gatekeeper refuses them with a message
  # that says the app is damaged, which is wrong and alarming. Strip it from our own build
  # and tell the user the one command that fixes a downloaded copy.
  xattr -cr "$APP" 2>/dev/null || true
  SIZE=$(du -sh "$APP" | cut -f1)
  echo
  echo "==> $APP  ($SIZE)"
  echo "    open \"$APP\"   to run it"
  echo
  echo "    This build is UNSIGNED. On another Mac, macOS will refuse to open it until:"
  echo "      xattr -dr com.apple.quarantine \"/Applications/Crack Fractography.app\""
  echo "    That is expected for an unsigned app and is documented in the README."
  echo
  # THE BUNDLE CHECKS RUN AGAIN, NOW THAT THERE IS A BUNDLE. The suite above ran before
  # `rm -rf dist`, so every test that asserts on what actually shipped -- the licence and
  # attribution files, the icon, the files loaded by path -- was either looking at the
  # PREVIOUS build or skipping. That is how three releases went out with no NOTICE inside
  # them while the guard reported green.
  echo "==> verifying the bundle that was just built"
  "$PY" -m pytest -q tests/test_packaging.py || {
    echo "  the BUILT BUNDLE failed its checks -- do not release this"; exit 1; }
else
  echo "==> dist/Crack Fractography/"
fi
