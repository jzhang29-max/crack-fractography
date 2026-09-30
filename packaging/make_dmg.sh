#!/usr/bin/env bash
# Build a drag-to-install .dmg from dist/Crack Fractography.app
#
# WHY A DMG AND NOT THE ZIP. The zip works, and it puts the .app wherever the browser
# unpacks it -- usually ~/Downloads, where it runs from, keeps running from, and quietly
# becomes the copy that gets deleted when someone tidies up. A dmg with an Applications
# symlink makes the install one drag and puts it where macOS expects it. It is also what a
# macOS user is looking for when they read "download".
#
# UDZO, not UDRW: read-only and zlib-compressed, so the image cannot be modified in place
# and the download is about the same size as the zip was.
#
# hdiutil only. No create-dmg, no node, nothing to install on the runner -- the dependency
# would be a build-time failure mode in exchange for a prettier background image.
set -euo pipefail

APP="${1:-dist/Crack Fractography.app}"
VERSION="${2:-0.0.0}"
OUT="${3:-dist/CrackFractography-${VERSION}-macOS-arm64.dmg}"
VOL="Crack Fractography ${VERSION}"

[ -d "$APP" ] || { echo "no app bundle at: $APP" >&2; exit 1; }

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

# The quarantine note has to reach the user, and a dmg has nowhere to put a README except
# the window itself -- so it goes in as a visible file rather than only in the release notes.
cat > "$STAGE/READ ME FIRST.txt" <<TXT
Crack Fractography ${VERSION}

INSTALL
  Drag "Crack Fractography" onto the Applications folder in this window.

FIRST LAUNCH
  This build is not signed by an Apple Developer account, so macOS will refuse to
  open it and say it is damaged. It is not damaged -- that is what macOS says about
  any unsigned app that arrived from the internet. Clear the quarantine flag once:

      xattr -dr com.apple.quarantine "/Applications/Crack Fractography.app"

  Then open it normally. You only have to do this once per install.

WHAT IT NEEDS
  Nothing. Python and every library are inside the app. It stores its own data in
  ~/Library/Application Support/Crack Fractography and does not write anywhere else
  unless you point it at a repository in Setup.
TXT

rm -f "$OUT"
mkdir -p "$(dirname "$OUT")"
hdiutil create -volname "$VOL" -srcfolder "$STAGE" -ov -quiet -format UDZO "$OUT"

echo "==> $OUT ($(du -h "$OUT" | cut -f1))"
