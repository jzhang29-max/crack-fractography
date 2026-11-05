"""One figure per page with its numbered caption, plus the captions as text.

For dropping into a figures-and-captions document. Everything is read from the
manuscript build, so the numbers, the caption text and the image files cannot
drift from the paper.
"""
import os, re, sys
HERE = "/Users/jiamingzhang/Desktop/APP/crack-fractography/paper/manuscript"
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "figures"))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages
import build as B                       # runs the whole value resolution
import make_paper as MP

SECT = B.SECT
files = sorted(f for f in os.listdir(SECT) if f.endswith(".md"))
B.number_the_figures(files)
B.number_the_tables(files)

caps = []
for src in files:
    for raw in open(os.path.join(SECT, src), encoding="utf-8"):
        m = B.FIG_RE.match(raw.strip())
        if m:
            caps.append((m.group(1), MP.resolve(m.group(2).strip())))
print(f"{len(caps)} figures")

OUT = "/Users/jiamingzhang/Desktop/APP/crack-fractography/paper/figures/out"
pdf_path = os.path.join(OUT, "figure pack.pdf")
md_path = os.path.join(OUT, "figure pack captions.md")
W, H = 8.27, 11.69                                   # A4 portrait
ML = 0.75

with PdfPages(pdf_path) as pdf, open(md_path, "w", encoding="utf-8") as md:
    md.write("# Figures and captions\n\n"
             "Generated from the manuscript build, so the numbers and the text match the\n"
             "paper exactly. The image file for each is named under its heading.\n\n")
    for i, (key, cap) in enumerate(caps, 1):
        img_path = B.FIGS[key]
        img = mpimg.imread(img_path)
        fig = plt.figure(figsize=(W, H))
        tw = W - 2 * ML
        ih = min(tw * img.shape[0] / img.shape[1], 6.6)
        iw = ih * img.shape[1] / img.shape[0]
        ax = fig.add_axes([(W - iw) / 2 / W, 1 - (1.0 + ih) / H, iw / W, ih / H])
        ax.imshow(img); ax.axis("off")
        body = f"Figure {i}.  {cap}"
        fig.text(ML / W, 1 - (1.35 + ih) / H, "\n".join(
            __import__("textwrap").wrap(body, 108)),
            fontsize=8.5, va="top", ha="left", family="sans-serif", linespacing=1.45)
        fig.text(ML / W, 0.4 / H, os.path.basename(img_path), fontsize=7,
                 color="0.45", ha="left", family="sans-serif")
        pdf.savefig(fig); plt.close(fig)
        md.write(f"## Figure {i}\n\n`{os.path.basename(img_path)}`\n\n{body}\n\n")
        print(f"  Figure {i:>2}  {os.path.basename(img_path)}")
print("wrote", pdf_path)
print("wrote", md_path)
