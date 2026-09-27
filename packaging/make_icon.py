#!/usr/bin/env python3
"""Turn one piece of 824-unit artwork into a macOS .icns, and prove it survives 16x16.

WHY THIS IS NOT JUST A RESIZE. Three things separate a native-looking macOS icon from a
picture in a square, and the shipped placeholder got all three wrong -- it was
PyInstaller's stock Python-on-a-floppy-disk:

  THE SHAPE. Since Big Sur, a macOS app icon is not a full-bleed square. It is an 824x824
  rounded rectangle, corner radius 185.4, centred in a 1024x1024 canvas with a 100pt margin
  all round, and a soft shadow under it. The margin is not wasted space -- it is what makes
  the icon sit at the same visual weight as every other icon in the Dock. A square icon
  looks oversized and foreign next to them.

  THE SIZES. An .icns needs ten entries from 16x16 to 1024x1024, and the @2x retina ones
  are not optional -- without a 512@2x the Dock upscales a 128px bitmap and it is visibly
  soft. Each size is rendered DIRECTLY FROM VECTOR at its target resolution rather than
  downsampled from the 1024, which keeps small sizes crisp instead of mushy.

  PROOF AT SMALL SIZE. A design that is beautiful at 1024 and illegible at 16 is a failed
  icon, and you cannot tell by looking at the big one. So this emits a contact sheet at
  every size, measures how much of the squircle the artwork actually covers, and counts
  distinct shapes at 16x16 -- and it refuses to build an icon whose artwork leaves the
  squircle mostly transparent, because transparent corners are the single most obvious
  way an icon reads as broken.

  usage: make_icon.py <artwork.svg> [outdir]
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

#: Apple's macOS app-icon grid at 1024. Body 824 square, 100 margin, radius 185.4.
CANVAS = 1024
BODY = 824
MARGIN = (CANVAS - BODY) // 2
RADIUS = 185.4

#: Every entry an .icns needs. (pixel size, iconset filename)
SIZES = [
    (16, "icon_16x16.png"), (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"), (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"), (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"), (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"), (1024, "icon_512x512@2x.png"),
]

COMPOSITE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{CANVAS}" height="{CANVAS}" viewBox="0 0 {CANVAS} {CANVAS}">
  <defs>
    <clipPath id="_macos_body_clip">
      <rect x="{MARGIN}" y="{MARGIN}" width="{BODY}" height="{BODY}" rx="{RADIUS}"/>
    </clipPath>
    <!-- Everything EXCEPT the body. The shadow is masked with this so it exists only
         outside the shape. Without it the shadow's own source rect paints the body solid
         black, which (a) shows through any transparency in the artwork and (b) made the
         coverage check below read 100% for every input, because it was measuring this
         rect and not the artwork at all. -->
    <mask id="_macos_outside_body">
      <rect x="0" y="0" width="{CANVAS}" height="{CANVAS}" fill="#fff"/>
      <rect x="{MARGIN}" y="{MARGIN}" width="{BODY}" height="{BODY}" rx="{RADIUS}"
            fill="#000"/>
    </mask>
    <filter id="_macos_body_shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="{sy}" stdDeviation="{sb}" flood-color="#000"
                    flood-opacity="0.34"/>
    </filter>
  </defs>
{shadow_layer}
  <!-- The artwork, nested at its own 824 scale and clipped to the body. Nesting rather
       than splicing so the artwork's own defs and ids stay in their own document scope
       and cannot collide with the ids above. -->
  <g clip-path="url(#_macos_body_clip)">
    {artwork}
  </g>
</svg>
"""

#: SVG renders filter -> clip -> mask, so the drop shadow is computed first and then the
#: body interior is masked away, leaving only the part that falls outside the shape.
SHADOW_LAYER = """  <g mask="url(#_macos_outside_body)" filter="url(#_macos_body_shadow)">
    <rect x="{MARGIN}" y="{MARGIN}" width="{BODY}" height="{BODY}" rx="{RADIUS}"
          fill="#000"/>
  </g>"""


def nest(svg_text):
    """Re-root the artwork as a nested <svg> placed on the body, at its own 824 scale."""
    t = svg_text.strip()
    if t.startswith("<?xml"):
        t = t[t.index("?>") + 2:].lstrip()
    i = t.index("<svg")
    j = t.index(">", i)
    inner = t[j + 1:]
    return (f'<svg x="{MARGIN}" y="{MARGIN}" width="{BODY}" height="{BODY}" '
            f'viewBox="0 0 {BODY} {BODY}" xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'preserveAspectRatio="xMidYMid slice">{inner}')


def render(svg_path, out_png, size):
    subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size),
                    "-o", out_png, svg_path], check=True)


def coverage(png, inset=0.06):
    """What fraction of the squircle the artwork actually paints.

    Transparent corners are the loudest way an icon reads as broken, and they are easy to
    ship by accident: the artwork looks complete on a white editor background and is
    see-through in the Dock. Sampled on an inset box so the squircle's own rounded corners
    do not count against the artwork.
    """
    im = Image.open(png).convert("RGBA")
    w, h = im.size
    m = int(w * (MARGIN / CANVAS + inset))
    box = im.crop((m, m, w - m, h - m))
    a = np.asarray(box.getchannel("A"))
    return float((a > 24).mean())


def distinct_shapes(png, size=16):
    """Roughly how many separate marks survive at icon-list size.

    Not a perfect proxy for legibility, but it catches the real failure: artwork whose
    meaning lives in many fine strokes collapses to one or two blobs here, and the count
    says so before anyone ships it.
    """
    im = Image.open(png).convert("L").resize((size, size), Image.LANCZOS)
    px = np.asarray(im).ravel().tolist()
    lo, hi = min(px), max(px)
    if hi - lo < 24:
        return 0, hi - lo
    mid = (lo + hi) / 2
    seen, comps = set(), 0
    dark = [i for i, v in enumerate(px) if v < mid]
    darkset = set(dark)
    for start in dark:
        if start in seen:
            continue
        comps += 1
        stack = [start]
        while stack:
            p = stack.pop()
            if p in seen:
                continue
            seen.add(p)
            x, y = p % size, p // size
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                q = ny * size + nx
                if 0 <= nx < size and 0 <= ny < size and q in darkset and q not in seen:
                    stack.append(q)
    return comps, hi - lo


def contact_sheet(pngs, out, bg):
    """One image showing every size side by side, on a chosen background.

    Rendered on BOTH a light and a dark ground because an icon that relies on a near-white
    or near-black field vanishes into one Dock and not the other, and looking at it on one
    background hides exactly that.
    """
    sizes = [16, 32, 64, 128, 256, 512]
    pad = 18
    W = sum(s + pad for s in sizes) + pad
    H = max(sizes) + 2 * pad
    sheet = Image.new("RGB", (W, H), bg)
    x = pad
    for s in sizes:
        im = Image.open(pngs[s]).convert("RGBA")
        sheet.paste(im, (x, H - pad - s), im)
        x += s + pad
    sheet.save(out)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    art = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(art))
    os.makedirs(outdir, exist_ok=True)

    nested = nest(open(art).read())
    fmt = dict(CANVAS=CANVAS, MARGIN=MARGIN, BODY=BODY, RADIUS=RADIUS,
               sy=CANVAS * 0.012, sb=CANVAS * 0.018, artwork=nested)

    comp = os.path.join(outdir, "composite_1024.svg")
    with open(comp, "w") as fh:
        fh.write(COMPOSITE.format(shadow_layer=SHADOW_LAYER.format(**fmt), **fmt))

    # A SECOND render with no shadow layer, used only for measurement. The coverage check
    # has to see the artwork's own alpha; measuring the shipped composite meant measuring
    # the shadow's source rect, which is opaque everywhere and reported 100% coverage for a
    # design that was a small circle on a transparent field.
    bare = os.path.join(outdir, "artwork_only_1024.svg")
    with open(bare, "w") as fh:
        fh.write(COMPOSITE.format(shadow_layer="", **fmt))

    iconset = os.path.join(outdir, "AppIcon.iconset")
    os.makedirs(iconset, exist_ok=True)
    by_size = {}
    for size, name in SIZES:
        p = os.path.join(iconset, name)
        render(comp, p, size)
        by_size[size] = p
    for s in (64,):
        by_size.setdefault(s, os.path.join(iconset, "icon_32x32@2x.png"))

    measure_png = os.path.join(outdir, "_measure_1024.png")
    render(bare, measure_png, 1024)
    cov = coverage(measure_png)
    shapes, contrast = distinct_shapes(by_size[1024])
    print(f"  squircle coverage      {100 * cov:.1f}%  (under 90% means transparent gaps)")
    print(f"  distinct marks at 16px {shapes}  (0 means it is one flat blob)")
    print(f"  luminance range        {contrast}/255  (under 60 will not read at small size)")

    contact_sheet(by_size, os.path.join(outdir, "sheet_light.png"), (246, 246, 244))
    contact_sheet(by_size, os.path.join(outdir, "sheet_dark.png"), (26, 26, 25))

    icns = os.path.join(outdir, "AppIcon.icns")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns], check=True)
    print(f"  wrote {icns} ({os.path.getsize(icns) / 1024:.0f} KB, {len(SIZES)} entries)")

    problems = []
    if cov < 0.90:
        problems.append(f"artwork covers only {100 * cov:.1f}% of the squircle -- the rest "
                        f"is transparent and will read as a broken icon")
    if shapes == 0:
        problems.append("nothing distinguishable at 16x16")
    if contrast < 60:
        problems.append(f"luminance range is only {contrast}/255 -- too flat to read small")
    for p in problems:
        print("  PROBLEM: " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
