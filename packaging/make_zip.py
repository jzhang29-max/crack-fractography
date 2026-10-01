#!/usr/bin/env python3
"""Zip (or unzip) a directory with Python's zipfile, deflated.

WHY NOT A SHELL TOOL. Two have already been tried and each failed differently on the
Windows runner, which is the only place this matters:

  Compress-Archive / Expand-Archive -- wrote an archive its own matching cmdlet could not
  faithfully restore. dist/ started and served; the copy unpacked from the zip died with
  RecursionError before answering /api/health. A PyInstaller onedir tree is thousands of
  files deep inside _internal/, which is where those cmdlets are weakest.

  bsdtar `tar -a -c -f x.zip` -- correct, and apparently STORED rather than deflated on
  that runner: the published zip went from 71 MB to 160 MB on the switch, while the same
  command on macOS compresses 4,640 KB of JavaScript to 1,596 KB. Rather than keep
  bisecting another tool's defaults from 2,000 miles away, stop using one.

Python's zipfile is already installed wherever this runs, compresses explicitly because
the compression is an argument rather than a default, and behaves the same on all three
platforms. The archive it writes is an ordinary zip that Explorer opens.
"""
import os
import sys
import zipfile


def write(src_dir, out_path, root_name=None):
    root_name = root_name or os.path.basename(src_dir.rstrip(os.sep))
    n = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for base, _dirs, files in os.walk(src_dir):
            for f in files:
                full = os.path.join(base, f)
                # Store paths with the directory as the single top-level entry, so
                # unzipping anywhere produces "<root_name>/..." and not a scatter of files.
                rel = os.path.join(root_name, os.path.relpath(full, src_dir))
                z.write(full, rel.replace(os.sep, "/"))
                n += 1
    return n


def read(zip_path, dest):
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
        return len(z.namelist())


def main():
    if len(sys.argv) < 4:
        sys.exit("usage: make_zip.py write <dir> <out.zip> [root-name]\n"
                 "       make_zip.py read  <in.zip> <dest-dir>")
    mode, a, b = sys.argv[1], sys.argv[2], sys.argv[3]
    if mode == "write":
        root = sys.argv[4] if len(sys.argv) > 4 else None
        n = write(a, b, root)
        size = os.path.getsize(b) / 1048576
        raw = sum(os.path.getsize(os.path.join(p, f))
                  for p, _d, fs in os.walk(a) for f in fs) / 1048576
        print(f"wrote {b}: {n} files, {raw:.0f} MB -> {size:.0f} MB "
              f"({100 * size / raw:.0f}% of raw)")
        # A STORED ARCHIVE IS THE FAILURE THIS SCRIPT EXISTS TO PREVENT, so it is checked
        # rather than assumed. A PyInstaller tree is mostly compiled code and compresses
        # to roughly half; anything above 85% means the compression did not happen.
        if raw > 20 and size > 0.85 * raw:
            sys.exit(f"archive is {100 * size / raw:.0f}% of the raw tree -- not compressed")
    elif mode == "read":
        print(f"extracted {read(a, b)} entries to {b}")
    else:
        sys.exit(f"unknown mode {mode!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
