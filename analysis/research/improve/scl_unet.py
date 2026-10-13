"""A small U-Net on the 26 precise tiles, trained with a WIDTH-INSENSITIVE objective.

THE ARGUMENT. Every method tried on this corpus is region-local: it looks at one blob's
own darkness, texture, thickness, elongation or vesselness and asks "is this a crack?".
Six such rules were built and all six failed. A crack is not a local property -- it is a
thin connected path through material -- so the opening is spatial context, which a
convolutional net has and none of the six had.

THE TRAP, and the whole reason the loss is the experiment. The labels are a PAINTBRUSH.
Trained with BCE or Dice against them a net learns to paint, lands on the same fat blobs
the one-line threshold already produces, and ties it again. Four targets/losses are run
head to head so the claim "the width-insensitive loss is what does it" is measured rather
than asserted:

    dice        soft-Dice against the painted label            (width-SENSITIVE control)
    cldice      0.5*soft-clDice + 0.5*soft-Dice, painted label (Shit et al., CVPR 2021)
    thin4       Dice+BCE against skel(label) dilated to  9 px  (thinned label)
    thin8       Dice+BCE against skel(label) dilated to 17 px  (thinned label)

Everything is leave-one-SPECIMEN-out: 13 folds, the net never sees a tile from the
specimen it is scored on, and the decision threshold is picked inside the fold too.

Nothing here writes outside the scratchpad and nothing touches sem-crack-detector.

WHAT IT MEASURED -- a TIE on the primary metric, and a gate failure. Do not re-propose
the standalone form without reading all four blocks below.

 1. THE SCORER REPRODUCES THE BRIEF'S TABLE EXACTLY. All six reference arms land on the
    published figures to four decimals (max |d| 0.0000), including clDice pooled as the
    MEDIAN of the 26 per-tile values, which is what the brief's 0.6405/0.6205 are.
    scl_baselines.py asserts it. 0 of 26 tile labels equal the shipped machine mask
    (median IoU(gt, machine) 0.3425, max 0.8341), so these labels are detector-free.

 2. HELD-OUT TILE SCORES (13 folds, nested threshold). Best arm is thin4 -- Dice+BCE
    against skel(label) dilated to 9 px:
                              prec  recall      F1     IoU   clDice   train-all    gap
        CURRENT (v1.49.1)   0.4182  0.6252  0.5012  0.3344   0.6405           -      -
        one-line threshold  0.4271  0.6027  0.4999  0.3332   0.6205           -      -
        thin4 standalone    0.5615  0.6262  0.5921  0.4206   0.7603      0.7647 +0.0044
        thin8 standalone    0.4296  0.6588  0.5200  0.3514   0.7274      0.7565 +0.0291
        soft-clDice stand.  0.5824  0.5871  0.5847  0.4131   0.5955      0.6381 +0.0426
        soft-Dice standal.  0.2517  0.7544  0.3774  0.2326   0.5484      0.6067 +0.0584
        mean-of-4 ensemble  0.5943  0.6745  0.6318  0.4618   0.6913      -      -
    The width-insensitive objective DOES beat the width-sensitive one: thin4 0.7603 and
    thin8 0.7274 against soft-Dice's 0.5484, and plain soft-Dice is the only arm that
    loses to the shipped model at p = 0.0105. That part of the brief's hypothesis holds.

 3. BUT IT IS A TIE PER SPECIMEN, WHICH IS THE TEST THAT COUNTS. The +0.1198 over the
    shipped model is specimen-WEIGHTED: it is a median over 26 tiles and MAR_H_AS and
    MAR_H_HIP own 11 of them. Paired over the 13 specimens:
        thin4 standalone vs one-line threshold  median +0.0341  8 up / 5 down  p=0.4548
        thin4 standalone vs CURRENT             median -0.0621  5 up / 8 down  p=0.4548
        mean-of-4        vs one-line threshold  median +0.0427  8 up / 5 down  p=0.2728
    Not one of the 24 arm/reference pairs reaches p < 0.05 in the method's favour. The
    design is not underpowered for a real effect: with n=13 it detects +0.10 to +0.15
    clDice at 80% power, and it detects the oracle arm (the label's own 3 px trace
    unioned in, +0.2213) at p = 0.0002. The observed effects are +0.000 to +0.059.
    The per-specimen spread is the story -- thin4 takes Cast_24hr 0.5361 -> 0.8076 and
    MAR_H_HIP 0.5346 -> 0.7438, and HIP_24hr 0.5879 -> 0.3386 and 260622_316_amb_b3
    0.3623 -> 0.0900. That is variance, not a method being right.

 4. THE FULL-FRAME PAINT GATE KILLS THE STANDALONE FORM, AND REJECTS THE CORRECT ANSWER
    TOO. On all 48 painted frames (20,903,694 kept hand-marked crack px):
        thin4 standalone @0.55   deletes 90.2203%   44 of 48 frames lose >1%   FAILS
        additive (| shipped)     deletes  0.0000%    0 of 48                    PASSES
    and the additive form keeps 1.73% MORE hand-marked crack than the shipped path. The
    standalone number is not a detection failure, though: on the same 6 frames where
    both were measured, the brief's own physically correct answer -- a 3 px trace of the
    human's paint -- deletes 94.63% where the net deletes 98.03%, because the paint is
    154 px wide at the median there. The 1%-deletion gate is a pixel-COVERAGE test, so
    it cannot admit any centreline method, including the right one. An additive union is
    the only admissible form -- and under sabotage the additive arm returns to the
    shipped model's own score (0.6208 / 0.6837 / 0.6815 against an intact 0.7051), so
    most of what it scores is the baseline, not the net.

 SABOTAGE, thin4 standalone on the 5 largest specimens: intact 0.7503, shuffled labels
 0.0860, labels rotated by one tile 0.0473, constant input 0.0000. The score comes from
 the image. CONTROLS at matched ADDED area on the 26 tiles (scl_controls.py): U-Net
 0.6974, darkest-first 0.3756, random blobs 0.3069, Frangi 0.2600 -- so clDice is not
 rewarding area, and the net's added pixels are placed far better than any no-learning
 alternative. It still does not move the paired test.

 NOT TESTED: extra input channels (flattened image + Frangi). The run was started and
 abandoned for compute; nothing here says whether they help.
"""
import os, sys, time, json, math
import numpy as np

APP = "/Users/jiamingzhang/Desktop/APP/crack-fractography"
SEM = "/Users/jiamingzhang/Desktop/APP/sem-crack-detector"
for p in (APP + "/analysis/research", APP + "/analysis/research/improve", APP + "/analysis",
          SEM + "/code"):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True

import torch                      # noqa: E402
import torch.nn as nn             # noqa: E402
import torch.nn.functional as F   # noqa: E402

OUT = ("/private/tmp/claude-501/-Users-jiamingzhang-Desktop-APP/"
       "48e14b5c-6bee-4570-a55e-3f87da7069da/scratchpad/scl")
os.makedirs(OUT, exist_ok=True)


# --------------------------------------------------------------------------- model
class Block(nn.Module):
    def __init__(self, cin, cout):
        super().__init__()
        self.f = nn.Sequential(
            nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(True),
            nn.Conv2d(cout, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(True))

    def forward(self, x):
        return self.f(x)


class UNet(nn.Module):
    """4 levels, base 16. ~0.5 M parameters -- small enough that 24 tiles cannot be
    memorised, deep enough that the bottleneck sees ~150 px of context, which is the
    whole point of using a net here."""

    def __init__(self, cin=1, base=16, levels=4):
        super().__init__()
        ch = [base * 2 ** i for i in range(levels + 1)]
        self.down = nn.ModuleList([Block(cin if i == 0 else ch[i - 1], ch[i]) for i in range(levels)])
        self.bott = Block(ch[levels - 1], ch[levels])
        self.up = nn.ModuleList([nn.ConvTranspose2d(ch[i + 1], ch[i], 2, 2) for i in reversed(range(levels))])
        self.dec = nn.ModuleList([Block(2 * ch[i], ch[i]) for i in reversed(range(levels))])
        self.head = nn.Conv2d(ch[0], 1, 1)

    def forward(self, x):
        skips = []
        for d in self.down:
            x = d(x); skips.append(x); x = F.max_pool2d(x, 2)
        x = self.bott(x)
        for u, dc, s in zip(self.up, self.dec, reversed(skips)):
            x = u(x)
            x = dc(torch.cat([x, s], 1))
        return self.head(x)


# ---------------------------------------------------------------------------- loss
def soft_erode(x):
    return -F.max_pool2d(-x, 3, 1, 1)


def soft_dilate(x):
    return F.max_pool2d(x, 3, 1, 1)


def soft_skel(x, iters=12):
    """Shit et al.'s differentiable skeleton: repeated morphological thinning by
    min/max pooling. Used on the PREDICTION only -- the label's skeleton is computed
    exactly once with skimage, which is both cheaper and sharper."""
    x1 = soft_dilate(soft_erode(x))
    s = F.relu(x - x1)
    for _ in range(iters):
        x = soft_erode(x)
        x1 = soft_dilate(soft_erode(x))
        d = F.relu(x - x1)
        s = s + F.relu(d - s * d)
    return s


def soft_dice(p, y, eps=1.0):
    num = 2 * (p * y).sum((1, 2, 3)) + eps
    den = p.sum((1, 2, 3)) + y.sum((1, 2, 3)) + eps
    return 1 - (num / den).mean()


def soft_cldice(p, y, y_skel, iters=12, eps=1.0):
    sp = soft_skel(p, iters)
    tprec = ((sp * y).sum((1, 2, 3)) + eps) / (sp.sum((1, 2, 3)) + eps)
    tsens = ((y_skel * p).sum((1, 2, 3)) + eps) / (y_skel.sum((1, 2, 3)) + eps)
    return 1 - (2 * tprec * tsens / (tprec + tsens)).mean()


def make_loss(kind):
    """`frac` is the fraction of training done, used only to RAMP soft-clDice in.

    Shit et al. pre-train with Dice before switching soft-clDice on, and the first run
    here showed why: started cold, the soft skeleton of a near-uniform prediction is
    empty, Tprec is eps/eps = 1 whatever the net does, and the net collapses to a
    constant (held-out clDice 0.0000, precision 0.026 at recall 0.73). The ramp is that
    warm-up, written as a schedule rather than two training phases."""
    bce = nn.BCEWithLogitsLoss()

    def f(logit, y, y_skel, y_thin, frac=1.0):
        p = torch.sigmoid(logit)
        if kind == "dice":
            return soft_dice(p, y)
        if kind == "cldice":
            a = 0.5 * min(1.0, max(0.0, (frac - 0.3) / 0.2))
            return (1 - a) * soft_dice(p, y) + a * soft_cldice(p, y, y_skel)
        if kind.startswith("thin"):
            return 0.5 * soft_dice(p, y_thin) + 0.5 * bce(logit, y_thin)
        raise ValueError(kind)
    return f


# ----------------------------------------------------------------------- data prep
def thin_target(gt_skel, r):
    from scipy import ndimage as ndi
    if r <= 0:
        return gt_skel.astype(np.float32)
    st = ndi.generate_binary_structure(2, 2)
    return ndi.binary_dilation(gt_skel, st, iterations=r).astype(np.float32)


def prep(tiles, gt_skels, thin_r):
    """One float32 stack per tile: [img z-scored], label, label skeleton, thinned label."""
    X, Y, S, T = [], [], [], []
    for t, g in zip(tiles, gt_skels):
        a = t["img8"].astype(np.float32)
        a = (a - a.mean()) / max(a.std(), 1e-6)
        X.append(a[None])
        Y.append(t["gt"].astype(np.float32)[None])
        S.append(g.astype(np.float32)[None])
        T.append(thin_target(g, thin_r)[None])
    return (np.stack(X), np.stack(Y), np.stack(S), np.stack(T))


def augment(x, y, s, t, rng, crop=256):
    """Dihedral group + a random crop + intensity jitter. No elastic: on 14 CPU cores the
    warp costs more than the extra steps it would buy."""
    H, W = x.shape[-2:]
    i = rng.integers(0, H - crop + 1); j = rng.integers(0, W - crop + 1)
    sl = (Ellipsis, slice(i, i + crop), slice(j, j + crop))
    x, y, s, t = x[sl].copy(), y[sl].copy(), s[sl].copy(), t[sl].copy()
    k = int(rng.integers(0, 4))
    if k:
        x, y, s, t = [np.rot90(v, k, (-2, -1)).copy() for v in (x, y, s, t)]
    if rng.random() < 0.5:
        x, y, s, t = [v[..., ::-1].copy() for v in (x, y, s, t)]
    if rng.random() < 0.5:
        x, y, s, t = [v[..., ::-1, :].copy() for v in (x, y, s, t)]
    x = x * float(rng.uniform(0.8, 1.25)) + float(rng.normal(0, 0.25))
    if rng.random() < 0.5:
        x = x + rng.normal(0, 0.1, x.shape).astype(np.float32)
    return x, y, s, t


# ------------------------------------------------------------------------ training
def train_fold(Xtr, Ytr, Str, Ttr, kind, seed=0, steps=400, batch=8, crop=256,
               base=16, lr=3e-3, threads=None, log=None):
    if threads:
        torch.set_num_threads(threads)
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = UNet(cin=Xtr.shape[1], base=base)
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps)
    loss_fn = make_loss(kind)
    n = len(Xtr)
    net.train()
    for it in range(steps):
        idx = rng.integers(0, n, batch)
        bx, by, bs, bt = [], [], [], []
        for k in idx:
            a, b, c, d = augment(Xtr[k], Ytr[k], Str[k], Ttr[k], rng, crop)
            bx.append(a); by.append(b); bs.append(c); bt.append(d)
        bx = torch.from_numpy(np.stack(bx)); by = torch.from_numpy(np.stack(by))
        bs = torch.from_numpy(np.stack(bs)); bt = torch.from_numpy(np.stack(bt))
        opt.zero_grad()
        lo = loss_fn(net(bx), by, bs, bt, (it + 1) / steps)
        lo.backward(); opt.step(); sch.step()
        if log and (it + 1) % log == 0:
            print(f"      step {it+1}/{steps} loss {lo.item():.4f}", flush=True)
    net.eval()
    return net


@torch.no_grad()
def predict_prob(net, X):
    """Full 512 px tiles, test-time augmented over the dihedral group (8 transforms).
    TTA costs 8 forward passes and buys consistency the 24-tile training set cannot."""
    net.eval()
    acc = np.zeros(X.shape[-2:], np.float32)
    x0 = torch.from_numpy(X[None])
    for k in range(4):
        for fl in (False, True):
            x = torch.rot90(x0, k, (-2, -1))
            if fl:
                x = torch.flip(x, (-1,))
            p = torch.sigmoid(net(x))
            if fl:
                p = torch.flip(p, (-1,))
            p = torch.rot90(p, -k, (-2, -1))
            acc += p[0, 0].numpy()
    return acc / 8.0
