"""The U-Net, the five supervision strategies, and leave-one-SPECIMEN-out training.

The whole point of this approach is that nothing here has seen a tile. Training is on
patches cut from the 48 hand-painted FULL frames; the 26 precise tiles are only ever
scored. Eight of the 26 tiles' parent micrographs ARE painted frames, so the fold is cut
by SPECIMEN, not by frame -- holding out a frame would leave the same specimen's texture,
and in those eight cases literally the same micrograph, in the training set.

THE SUPERVISION PROBLEM, and the five answers compared.

The paint is a region assertion, not a boundary: median brush width 192 px, 91.3% of the
corpus never reviewed at all. Two independent mistakes are available and the arms separate
them.

  naive        paint as the target, UNREVIEWED COUNTED AS BACKGROUND. The control that
               shows what the obvious thing costs: 91.3% of pixels are asserted to be
               not-crack on no evidence.
  pu_dice      paint as the target, unreviewed treated as UNLABELLED -- down-weighted to
               0.05 rather than ignored outright, because with only 0.56% hand-marked
               not-crack a loss with no negatives has a trivial optimum (mark everything).
  pu_cldice    same weights, but the region term is replaced by soft-clDice, which scores
               the prediction's centreline against the label and the label's centreline
               against the prediction. Indifferent to how thick the brush was. This is the
               width-insensitive loss the brief asks for.
  thin         the target is the paint's own medial axis (taken on the FRAME, never on a
               crop), and the REST of the brush stroke is set to IGNORE -- not background.
               We know a crack runs through that stroke; we do not know the stroke's
               shoulders are matrix, so they are not supervised either way.
  mil          the paint is used only as a region constraint: each painted region must
               contain SOME crack (top-k pooling over the region), and predicted area
               inside the region is penalised so the model satisfies it thinly. The
               closest thing here to "a thin connected path through material".

TEST TIME IS PARAMETER-FREE. The probability map is converted to a mask by taking the
same marked-area fraction the shipped detector takes on that tile, then through the same
clean_mask + 40 px filter every arm in the baseline table passes through. No threshold is
fitted anywhere, so there is no test-time knob to leak through. A fixed 0.5 cut is
reported alongside it as a second parameter-free readout.
"""
import os, sys, time, json
import numpy as np

sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
sys.dont_write_bytecode = True

import torch
import torch.nn as nn
import torch.nn.functional as F

import unetctx_base as B
import unetctx_patches as PB

ARMS = ("naive", "pu_dice", "pu_cldice", "thin", "mil")
# Sabotage: the same pipeline with the link between image and label broken. Each uses the
# pu_dice loss, so the only difference from a real arm is that the supervision is wrong.
#   sab_shuffle  every patch keeps its image and is given ANOTHER patch's paint
#   sab_rot      the paint is turned 90 degrees against its own image
#   sab_const    the image is replaced by zeros, so only the paint's shape is left
SABOTAGE = {"sab_shuffle": "pu_dice", "sab_rot": "pu_dice", "sab_const": "pu_dice"}
STEPS = 1200
BATCH = 8
LR = 2e-3
UNREV_W = 0.05
MODELS = os.path.join(B.MY, "models")
os.makedirs(MODELS, exist_ok=True)


# ------------------------------------------------------------------ the network
def _blk(i, o):
    return nn.Sequential(nn.Conv2d(i, o, 3, padding=1, bias=False), nn.BatchNorm2d(o),
                         nn.ReLU(True),
                         nn.Conv2d(o, o, 3, padding=1, bias=False), nn.BatchNorm2d(o),
                         nn.ReLU(True))


class UNet(nn.Module):
    """Small on purpose: 579k parameters against 48 frames from 10 specimens. A big net
    would memorise the ten textures, and the held-out specimens are the whole test."""

    def __init__(self, base=8, depth=4):
        super().__init__()
        ch = [base * 2 ** i for i in range(depth + 1)]
        self.enc = nn.ModuleList([_blk(1 if i == 0 else ch[i - 1], ch[i]) for i in range(depth + 1)])
        self.up = nn.ModuleList([nn.ConvTranspose2d(ch[i + 1], ch[i + 1], 2, 2) for i in range(depth)])
        self.dec = nn.ModuleList([_blk(ch[i + 1] + ch[i], ch[i]) for i in range(depth)])
        self.out = nn.Conv2d(ch[0], 1, 1)
        self.pool = nn.MaxPool2d(2)
        self.depth = depth

    def forward(self, x):
        f = []
        for i in range(self.depth + 1):
            x = self.enc[i](x)
            f.append(x)
            if i < self.depth:
                x = self.pool(x)
        for i in range(self.depth - 1, -1, -1):
            x = self.dec[i](torch.cat([self.up[i](x), f[i]], 1))
        return self.out(x)


# ------------------------------------------------------------------ losses
def _soft_erode(x):
    return -F.max_pool2d(-x, 3, 1, 1)


def _soft_open(x):
    return F.max_pool2d(_soft_erode(x), 3, 1, 1)


def soft_skel(x, k=10):
    """Differentiable skeleton (Shit et al. 2021). k iterations reach a half-width of k,
    which is ample for a prediction; the LABEL's skeleton is never computed this way --
    it is precomputed exactly, on the full frame, in the patch bank."""
    x1 = _soft_open(x)
    s = F.relu(x - x1)
    for _ in range(k):
        x = _soft_erode(x)
        x1 = _soft_open(x)
        d = F.relu(x - x1)
        s = s + F.relu(d - s * d)
    return s


def w_bce(logit, tgt, w):
    l = F.binary_cross_entropy_with_logits(logit, tgt, reduction="none")
    return (l * w).sum() / w.sum().clamp(min=1.0)


def w_dice(prob, tgt, w, eps=1.0):
    num = 2 * (prob * tgt * w).sum() + eps
    den = (prob * w).sum() + (tgt * w).sum() + eps
    return 1 - num / den


def soft_cldice(prob, region, skel_lbl, eps=1e-6):
    sp = soft_skel(prob)
    tprec = (sp * region).sum() / (sp.sum() + eps)
    tsens = (skel_lbl * prob).sum() / (skel_lbl.sum() + eps)
    return 1 - 2 * tprec * tsens / (tprec + tsens + eps)


def mil_loss(prob, comps, paint, lam=0.5, eps=1e-6):
    """Each painted region must contain SOME crack, and as little as it can get away with.

    comps: int tensor of per-patch connected-component ids of the paint (0 = none).
    The positive term is -log(mean of the top-k probabilities in the region), with k set
    to 5% of the region's area: a region genuinely does contain a crack that crosses it,
    so a handful of confident pixels is the weakest honest reading of the label. The
    sparsity term then charges for every other pixel the model lights up inside it.
    """
    pos, n = prob.new_zeros(()), 0
    for b in range(prob.shape[0]):
        c = comps[b]
        mx = int(c.max().item())
        for j in range(1, mx + 1):
            m = (c == j)
            a = int(m.sum().item())
            if a < 200:                 # a clipped sliver at the patch edge need not
                continue                # contain the crack; only whole-ish regions do
            k = max(16, int(0.05 * a))
            v = torch.topk(prob[b, 0][m], k).values
            pos = pos + -(v.mean() + eps).log()
            n += 1
    if n:
        pos = pos / n
    sp = (prob * paint).sum() / paint.sum().clamp(min=1.0)
    return pos + lam * sp


def arm_loss(arm, logit, y, thin):
    """y: 0 unreviewed, 1 crack paint, 2 hand-marked not-crack. thin: medial-axis band."""
    prob = torch.sigmoid(logit)
    paint = (y == 1).float()
    notc = (y == 2).float()
    unrev = (y == 0).float()
    if arm == "naive":
        w = torch.ones_like(paint)
        return w_bce(logit, paint, w) + w_dice(prob, paint, w)
    w = paint + notc + UNREV_W * unrev
    if arm == "pu_dice":
        return w_bce(logit, paint, w) + w_dice(prob, paint, w)
    if arm == "pu_cldice":
        return 0.5 * w_bce(logit, paint, w) + 0.5 * soft_cldice(prob, paint, thin)
    if arm == "thin":
        # the stroke's shoulders are unknown, so they are supervised at weight 0
        w2 = thin + notc + UNREV_W * unrev * (1 - paint)
        return w_bce(logit, thin, w2) + w_dice(prob, thin, w2)
    if arm == "mil":
        wn = notc + UNREV_W * unrev
        comps = _components(paint)
        return w_bce(logit, torch.zeros_like(paint), wn) + mil_loss(prob, comps, paint)
    raise ValueError(arm)


def _components(paint):
    from scipy import ndimage as ndi
    out = np.zeros(paint.shape[0:1] + paint.shape[2:], np.int32)
    p = paint.detach().cpu().numpy()[:, 0] > 0.5
    for b in range(p.shape[0]):
        out[b], _ = ndi.label(p[b])
    return torch.from_numpy(out)


# ------------------------------------------------------------------ training
def train_fold(arm, holdout, seed=0, steps=STEPS, verbose=False):
    """holdout: specimen name to exclude from training, or None for the all-paint model."""
    tag = f"{arm}__{holdout or 'ALL'}__s{seed}"
    path = os.path.join(MODELS, tag + ".pt")
    if os.path.exists(path):
        return path
    X, Y, T, spec, _ = PB.load()
    keep = np.flatnonzero(spec != holdout) if holdout else np.arange(len(spec))
    assert len(keep) > 500, f"{tag}: only {len(keep)} training patches"
    torch.manual_seed(seed)
    rng = np.random.default_rng(1000 + seed)
    net = UNet()
    opt = torch.optim.Adam(net.parameters(), LR)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    net.train()
    t0 = time.time()
    for st in range(steps):
        idx = rng.choice(keep, BATCH, replace=False)
        idx.sort()
        x = np.asarray(X[idx]).astype(np.float32) / 16.0
        y = np.asarray(Y[idx]).astype(np.float32)
        th = np.asarray(T[idx]).astype(np.float32)
        k = rng.integers(0, 4); fl = rng.integers(0, 2)
        x, y, th = [np.rot90(a, k, (1, 2)) for a in (x, y, th)]
        if fl:
            x, y, th = [a[:, ::-1] for a in (x, y, th)]
        x = torch.from_numpy(np.ascontiguousarray(x))[:, None]
        y = torch.from_numpy(np.ascontiguousarray(y))[:, None]
        th = torch.from_numpy(np.ascontiguousarray(th))[:, None]
        if arm == "sab_shuffle":
            j = rng.permutation(BATCH)
            while BATCH > 1 and (j == np.arange(BATCH)).all():
                j = rng.permutation(BATCH)
            y, th = y[j], th[j]
        elif arm == "sab_rot":
            y, th = torch.rot90(y, 1, (2, 3)), torch.rot90(th, 1, (2, 3))
        elif arm == "sab_const":
            x = torch.zeros_like(x)
        opt.zero_grad()
        loss = arm_loss(SABOTAGE.get(arm, arm), net(x), y, th)
        loss.backward()
        opt.step()
        sched.step()
        if verbose and st % 200 == 0:
            print(f"    {tag} step {st:4d} loss {loss.item():.4f} "
                  f"({time.time()-t0:.0f}s)", flush=True)
    torch.save({"state": net.state_dict(), "arm": arm, "holdout": holdout,
                "seed": seed, "n_train": int(len(keep)), "steps": steps}, path)
    return path


def load_net(path):
    d = torch.load(path, map_location="cpu", weights_only=False)
    net = UNet()
    net.load_state_dict(d["state"])
    net.eval()
    return net


# ------------------------------------------------------------------ inference
@torch.no_grad()
def predict_prob(net, flat_u8, P=PB.P, stride=80):
    """Overlapping 192 px windows, each standardised by its OWN median/MAD -- the same
    operator the training patches went through. Feeding a 512 px tile whole would change
    the normalisation window and so change the input distribution."""
    H, W = flat_u8.shape
    acc = np.zeros((H, W), np.float32)
    cnt = np.zeros((H, W), np.float32)
    ys = sorted(set(list(range(0, max(H - P, 0) + 1, stride)) + [max(H - P, 0)]))
    xs = sorted(set(list(range(0, max(W - P, 0) + 1, stride)) + [max(W - P, 0)]))
    for y0 in ys:
        for x0 in xs:
            win = flat_u8[y0:y0 + P, x0:x0 + P]
            z = PB.standardise(win).astype(np.float32) / 16.0
            p = torch.sigmoid(net(torch.from_numpy(z)[None, None])).numpy()[0, 0]
            acc[y0:y0 + win.shape[0], x0:x0 + win.shape[1]] += p[:win.shape[0], :win.shape[1]]
            cnt[y0:y0 + win.shape[0], x0:x0 + win.shape[1]] += 1
    return acc / np.maximum(cnt, 1)


@torch.no_grad()
def predict_prob_blended(net, flat_u8, P=PB.P, stride=48):
    """Same windows, denser and feathered.

    predict_prob averages hard-edged windows, and because each window is standardised by
    its OWN median and MAD the averaged map carries visible seams on the window lattice --
    they are plain in the probability images. A raised-cosine weight per window and a
    denser stride removes them. This is a defect in the inference, not a tuning knob:
    both readouts are reported, and the verdict does not rest on the choice.
    """
    H, W = flat_u8.shape
    w1 = np.hanning(P + 2)[1:-1].astype(np.float32)
    win_w = np.outer(w1, w1) + 1e-3
    acc = np.zeros((H, W), np.float32)
    cnt = np.zeros((H, W), np.float32)
    ys = sorted(set(list(range(0, max(H - P, 0) + 1, stride)) + [max(H - P, 0)]))
    xs = sorted(set(list(range(0, max(W - P, 0) + 1, stride)) + [max(W - P, 0)]))
    for y0 in ys:
        for x0 in xs:
            win = flat_u8[y0:y0 + P, x0:x0 + P]
            h, w = win.shape
            z = PB.standardise(win).astype(np.float32) / 16.0
            p = torch.sigmoid(net(torch.from_numpy(z)[None, None])).numpy()[0, 0][:h, :w]
            ww = win_w[:h, :w]
            acc[y0:y0 + h, x0:x0 + w] += p * ww
            cnt[y0:y0 + h, x0:x0 + w] += ww
    return acc / np.maximum(cnt, 1e-6)


def mask_from_prob(prob, area_frac=None, thr=0.5):
    """Parameter-free readout. area_frac given -> mark exactly that fraction of the frame,
    which is the shipped detector's own marked fraction on this tile, so the arms are
    compared at equal area. Otherwise a fixed 0.5 cut."""
    import ctx_core as CC
    if area_frac is not None and area_frac > 0:
        m = prob >= np.percentile(prob, 100 * (1 - area_frac))
    else:
        m = prob >= thr
    return CC.cand(m)


if __name__ == "__main__":
    arm = sys.argv[1]
    hold = None if len(sys.argv) < 3 or sys.argv[2] == "ALL" else sys.argv[2]
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    torch.set_num_threads(int(os.environ.get("NT", "2")))
    t = time.time()
    p = train_fold(arm, hold, seed, verbose=True)
    print(f"  done {os.path.basename(p)} in {time.time()-t:.0f}s", flush=True)
