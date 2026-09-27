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
echo "==> vendoring the shared measurement code"
"$PY" packaging/vendor.py

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
else
  echo "==> dist/Crack Fractography/"
fi
