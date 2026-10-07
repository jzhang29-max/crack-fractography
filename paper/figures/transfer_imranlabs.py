"""imranlabs/sem-microstructure-segmentation: the only published SEM/AM segmentation model
with RELEASED weights that I could find.

Why this one is the fair "newest tool out there" test. The fractography-specific papers --
Tsop's quantitative fractography U-Net, the SegFormer morphological-fractography work, the
DINOv2 fracture classifier -- publish numbers and no checkpoints (Tsop's repo ships a
weights/ directory holding a 57-byte .gitattributes and nothing else). This model does ship
one: UNet + ResNet-34, 1-channel SEM input, trained on additively manufactured Ni-WC, with
a Void class its card scores at IoU 0.976.

It is out of domain in ALLOY (Ni-WC, not 316L) and in domain in modality and process (SEM
of an AM metal). So the generous reading is what is reported: every one of its five classes
is scored against the hand label and the BEST is kept, per tile. That is an oracle choice
of output channel -- no user gets to pick the channel after seeing the answer -- so it is
an upper bound on this model's transfer, not an achievable score.
"""
import glob, json, os, sys, time, warnings
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths
warnings.filterwarnings("ignore")
from PIL import Image
import torch, segmentation_models_pytorch as smp

#: Through _paths like every other script here, not a hardcoded Desktop layout: the
#: directory README promises "Nothing here contains an absolute path", and these two
#: were the first files to break that promise.
SC = os.path.join(_paths.require(_paths.SEM_REPO, "the sem-crack-detector checkout",
                                 "SEM_REPO"), "crack_export", "analysis", "sam3")
HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ["Matrix", "Carbide", "Void", "Reprecipitate", "DilutionZone"]

net = smp.Unet(encoder_name="resnet34", encoder_weights=None,
               in_channels=1, classes=5)
#: Gitignored: 293 MB, downloaded, and not ours to vendor. Say where it comes from rather
#: than dying on a bare path -- a reader cloning this repo has everything EXCEPT this file.
CKPT = os.environ.get("IMRANLABS_CKPT", f"{HERE}/imranlabs/best_model.pth")
if not os.path.exists(CKPT):
    raise SystemExit(
        f"no checkpoint at {CKPT}\n"
        "  This arm scores a published third-party model that is not vendored here (293 MB).\n"
        "  Fetch it, then re-run:\n"
        "    mkdir -p imranlabs && curl -L -o imranlabs/best_model.pth \\\n"
        "      https://huggingface.co/imranlabs/sem-microstructure-segmentation/resolve/"
        "main/checkpoints/best_model.pth\n"
        "  Or point IMRANLABS_CKPT at a copy you already have.")
net.load_state_dict(torch.load(CKPT, map_location="cpu",
                               weights_only=False)["model_state"])
net.eval()

out = []
for f in sorted(glob.glob(f"{SC}/tiles/*_gray.png")):
    stem = os.path.basename(f)[:-9]
    g = np.array(Image.open(f).convert("L"))
    gt = np.array(Image.open(f[:-9] + "_gt.png").convert("L")) > 0

    t0 = time.time()
    x = torch.from_numpy((g.astype(np.float32) / 255.0))[None, None]
    with torch.no_grad():
        pr = torch.softmax(net(x), 1)[0].numpy()        # (5,H,W)
    dt = time.time() - t0
    am = pr.argmax(0)

    per = {}
    for c in range(5):
        m = am == c
        u = (m | gt).sum()
        per[NAMES[c]] = round(float((m & gt).sum() / u) if u else 0.0, 4)
    best = max(per, key=per.get)
    bi = NAMES.index(best)
    p = pr[bi]
    r = dict(tile=stem, sec=round(dt, 2), best_class=best,
             iou_best=per[best], iou_void=per["Void"], per_class=per,
             brier=round(float(np.mean((p - gt) ** 2)), 4),
             frac_void=round(float((am == 2).mean()), 4))
    out.append(r)
    print(f"  {stem:<44} best={best:<13} IoU={r['iou_best']:.4f} "
          f"(Void {r['iou_void']:.4f}, {100*r['frac_void']:.1f}% of tile)  {r['sec']:.1f}s",
          flush=True)

#: The name transfer_bench.py reads, so the documented chain runs without a hand rename.
json.dump(out, open(f"{HERE}/imranlabs_eval.json", "w"), indent=1)
md = lambda k: float(np.median([r[k] for r in out]))
print(f"\nn={len(out)}  median IoU(best-of-5, oracle channel)={md('iou_best'):.4f}  "
      f"median IoU(Void)={md('iou_void'):.4f}  median Brier={md('brier'):.4f}  "
      f"median s/tile={md('sec'):.2f}")
from collections import Counter
print("  best channel per tile:", dict(Counter(r["best_class"] for r in out)))
