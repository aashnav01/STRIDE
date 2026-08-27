"""
koa_stgcn.py — the graph network, its confound-controlled variants, and a
disk cache so three models can share one set of trainings.

CPU BUDGET
----------
Colab CPU, not GPU. Three things make that viable:

  * The net is small on purpose — 16 base channels, four blocks, ~40k
    parameters per stream. At 64 development subjects the limit is the data,
    not the capacity; a bigger net buys nothing and costs minutes.
  * 458 samples of (3, 48, 25, 1). The whole dataset is under 7 MB, so it
    sits in RAM and every epoch is 15 small batches.
  * TRAININGS ARE CACHED. Models 5, 6 and 7 all need ST-GCN outputs. Training
    them three times over would triple the only expensive part of the
    notebook, so each (variant, seed) is trained once, and the out-of-fold
    probabilities AND embeddings are written to disk. Re-running a downstream
    model is then instant.

Expect roughly 1-2 minutes per variant per seed on a Colab CPU core.

CONFOUND CONTROL
----------------
Walking speed separates these groups almost perfectly, and a graph network
cannot be feature-filtered the way a handcrafted model can — it sees the
whole trajectory. The two variants here act on the REPRESENTATION instead,
which is the only place you can intervene in a GCN:

  'mdn'   Metadata Normalization (Lu et al., CVPR 2021). After global
          pooling, linearly regress speed out of the pooled features inside
          every batch: F <- F - S (S'S)^-1 S' F, with S = [1, speed]. No
          adversarial game, no instability, about fifteen lines.

  'cfnet' Confounder-free adversarial training (Zhao et al., Nature
          Communications 2020). An adversary predicts speed from the
          embedding; the encoder is penalised by the SQUARED CORRELATION
          between the adversary's prediction and true speed. Critically the
          adversarial term is computed on a Y-CONDITIONED COHORT (controls
          only), which strips the direct speed path while leaving the
          disease effect that speed MEDIATES — slow walking is a real knee-OA
          sign, and an adjustment that deletes it is over-adjustment, not
          rigour.

Both report corr(prediction, speed) before and after, so the claim is
measured rather than asserted.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from koa_skeleton import NTU_PARENTS, NUM_JOINTS

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
ON_GPU = DEVICE.type == "cuda"
torch.set_num_threads(max(1, (os.cpu_count() or 2)))

CFG = dict(
    epochs=45 if ON_GPU else 25,
    base=32 if ON_GPU else 16,
    batch=16 if ON_GPU else 32,
    lr=1e-3 if ON_GPU else 2e-3,
    weight_decay=1e-3,
    adv_lambda=2.0,        # CF-Net penalty weight on corr^2
)

CACHE = Path(os.environ.get("KOA_WORK", "koa_work")) / "stgcn_cache"
CACHE.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# network
# --------------------------------------------------------------------------
def adjacency():
    A = np.eye(NUM_JOINTS, dtype=np.float32)
    for c, p in enumerate(NTU_PARENTS):
        A[c, p] = A[p, c] = 1.0
    D = np.diag(1.0 / np.sqrt(A.sum(1)))
    return torch.tensor(D @ A @ D, dtype=torch.float32)


class Block(nn.Module):
    def __init__(self, cin, cout, A, stride=1, residual=True):
        super().__init__()
        self.register_buffer("A", A)
        self.gcn = nn.Conv2d(cin, cout, 1)
        self.tcn = nn.Sequential(nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                                 nn.Conv2d(cout, cout, (9, 1), (stride, 1), (4, 0)),
                                 nn.BatchNorm2d(cout), nn.Dropout(0.3))
        if not residual:
            self.res = lambda x: 0
        elif cin == cout and stride == 1:
            self.res = nn.Identity()
        else:
            self.res = nn.Sequential(nn.Conv2d(cin, cout, 1, (stride, 1)),
                                     nn.BatchNorm2d(cout))
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        r = self.res(x)
        x = torch.einsum("nctv,vw->nctw", self.gcn(x), self.A)
        return self.relu(self.tcn(x) + r)


class STGCN(nn.Module):
    def __init__(self, num_class=2, in_ch=3, base=None):
        super().__init__()
        base = base or CFG["base"]
        A = adjacency()
        self.embed_dim = base * 2
        self.bn = nn.BatchNorm1d(in_ch * NUM_JOINTS)
        self.blocks = nn.ModuleList([Block(in_ch, base, A, residual=False),
                                     Block(base, base, A),
                                     Block(base, base * 2, A, stride=2),
                                     Block(base * 2, base * 2, A, stride=2)])
        self.drop = nn.Dropout(0.5)
        self.fc = nn.Linear(base * 2, num_class)

    def embed(self, x):
        N, C, T, V, M = x.shape
        x = x.permute(0, 4, 3, 1, 2).reshape(N * M, V * C, T)
        x = self.bn(x).view(N * M, V, C, T).permute(0, 2, 3, 1).contiguous()
        for b in self.blocks:
            x = b(x)
        return x.mean(dim=(2, 3)).view(N, M, -1).mean(1)

    def forward(self, x, speed=None, mdn=False):
        f = self.embed(x)
        if mdn and speed is not None and f.shape[0] > 4:
            f = metadata_norm(f, speed)
        return self.fc(self.drop(f)), f


def metadata_norm(F: torch.Tensor, speed: torch.Tensor) -> torch.Tensor:
    """Remove the linear effect of `speed` from pooled features, per batch.

    F <- F - S (S'S)^-1 S' F, with S = [1, speed]. This is the Metadata
    Normalization layer: a closed-form projection, no parameters, no
    adversary. It removes exactly the part of every feature a linear
    predictor could reconstruct from speed.
    """
    S = torch.stack([torch.ones_like(speed), speed], dim=1)          # (N, 2)
    StS = S.t() @ S + 1e-4 * torch.eye(2, device=S.device)
    beta = torch.linalg.solve(StS, S.t() @ F)                        # (2, D)
    return F - S @ beta


class SpeedAdversary(nn.Module):
    """Predicts the confounder from the embedding. CF-Net's CP."""
    def __init__(self, dim):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(dim, 32), nn.ReLU(inplace=True),
                                 nn.Linear(32, 1))

    def forward(self, f):
        return self.net(f).squeeze(-1)


def sq_corr(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Squared Pearson correlation, differentiable. CF-Net's dependence measure."""
    a = a - a.mean()
    b = b - b.mean()
    denom = torch.sqrt((a * a).sum() * (b * b).sum()) + 1e-8
    return ((a * b).sum() / denom) ** 2


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------
class SkelDS(Dataset):
    """Domain randomisation, not SMOTE.

    At a 1.7:1 class ratio SMOTE is unnecessary, and interpolating between two
    patients' skeletons manufactures a person who is neither — blurring
    exactly the boundary the model has to learn. These four augmentations
    instead simulate the capture shift we actually expect from a phone.
    """
    def __init__(self, X, y, speed=None, train=False):
        self.X = X.astype(np.float32)
        self.y = y.astype(np.int64)
        self.s = (np.zeros(len(y), np.float32) if speed is None
                  else speed.astype(np.float32))
        self.train = train

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        x = self.X[i].copy()
        if self.train:
            if np.random.rand() < 0.5:                       # yaw
                a = np.random.uniform(-np.pi / 6, np.pi / 6)
                R = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0],
                              [-np.sin(a), 0, np.cos(a)]], np.float32)
                x = np.einsum("ij,jtvm->itvm", R, x)
            if np.random.rand() < 0.5:                       # depth-weighted noise
                for ch, sd in ((0, .010), (1, .010), (2, .035)):
                    x[ch] += np.random.normal(0, sd, x.shape[1:]).astype(np.float32)
            if np.random.rand() < 0.3:                       # joint dropout, in runs
                Tn = x.shape[1]
                for v in range(x.shape[2]):
                    if np.random.rand() < 0.10:
                        L = np.random.randint(2, max(3, Tn // 8))
                        st = np.random.randint(0, max(1, Tn - L))
                        x[:, st:st + L, v] = x[:, st:st + 1, v]
            if np.random.rand() < 0.3:                       # temporal shift
                x = np.roll(x, np.random.randint(-6, 7), axis=1)
        return torch.from_numpy(x), self.y[i], self.s[i]


# --------------------------------------------------------------------------
# training
# --------------------------------------------------------------------------
def train_stream(Xtr, ytr, Xte, seed, speed_tr=None, variant="plain",
                 epochs=None, log=None, num_class=2):
    """Train one stream.

    Returns (probs, embeddings, model, diag). `probs` is the positive-class
    probability when num_class == 2, and the full (n, num_class) matrix
    otherwise — the severity models need all three columns.
    """
    epochs = epochs or CFG["epochs"]
    torch.manual_seed(seed)
    np.random.seed(seed)

    m = STGCN(num_class=num_class, in_ch=Xtr.shape[1]).to(DEVICE)
    adv = SpeedAdversary(m.embed_dim).to(DEVICE) if variant == "cfnet" else None

    cw = np.array([len(ytr) / (num_class * max(1, (ytr == k).sum()))
                   for k in range(num_class)])
    crit = nn.CrossEntropyLoss(
        weight=torch.tensor(cw, dtype=torch.float32).to(DEVICE),
        label_smoothing=0.1)
    opt = torch.optim.AdamW(m.parameters(), lr=CFG["lr"],
                            weight_decay=CFG["weight_decay"])
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    opt_a = (torch.optim.Adam(adv.parameters(), lr=1e-3) if adv else None)

    # z-score speed so the adversary and the projection are well conditioned
    if speed_tr is None:
        speed_tr = np.zeros(len(ytr), np.float32)
    smu, ssd = float(np.mean(speed_tr)), float(np.std(speed_tr) + 1e-8)
    sz = ((speed_tr - smu) / ssd).astype(np.float32)

    dl = DataLoader(SkelDS(Xtr, ytr, sz, True), batch_size=CFG["batch"],
                    shuffle=True, drop_last=len(ytr) > CFG["batch"])
    last = {}
    for ep in range(epochs):
        m.train()
        tot = adv_tot = 0.0
        for xb, yb, sb in dl:
            xb, yb, sb = xb.to(DEVICE), yb.to(DEVICE), sb.to(DEVICE)

            if adv is not None:
                # (1) adversary learns to read speed off the current embedding
                with torch.no_grad():
                    f_det = m.embed(xb)
                opt_a.zero_grad()
                la = ((adv(f_det) - sb) ** 2).mean()
                la.backward()
                opt_a.step()
                adv_tot += float(la)

            opt.zero_grad()
            logits, f = m(xb, speed=sb, mdn=(variant == "mdn"))
            loss = crit(logits, yb)

            if adv is not None:
                # (2) encoder is penalised by how well the FROZEN adversary
                #     still recovers speed — computed on the y-conditioned
                #     cohort (the lowest class) so the mediated effect survives.
                ref = (yb == 0)
                if int(ref.sum()) >= 4:
                    for p in adv.parameters():
                        p.requires_grad_(False)
                    pen = sq_corr(adv(f[ref]), sb[ref])
                    for p in adv.parameters():
                        p.requires_grad_(True)
                    loss = loss + CFG["adv_lambda"] * pen
                    last["corr2"] = float(pen)

            loss.backward()
            nn.utils.clip_grad_norm_(m.parameters(), 1.0)
            opt.step()
            tot += float(loss)
        sch.step()
        if log and (ep + 1) % 10 == 0:
            msg = f"      {log} ep{ep+1:3d} loss {tot/max(1,len(dl)):.3f}"
            if adv is not None:
                msg += f"  adv_mse {adv_tot/max(1,len(dl)):.3f}  corr2 {last.get('corr2',0):.3f}"
            print(msg, flush=True)

    m.eval()
    probs, embs = [], []
    with torch.no_grad():
        for xb, _, _ in DataLoader(SkelDS(Xte, np.zeros(len(Xte)), None, False),
                                   batch_size=64):
            logits, f = m(xb.to(DEVICE))
            sm = torch.softmax(logits, 1).cpu().numpy()
            probs.append(sm[:, 1] if num_class == 2 else sm)
            embs.append(f.cpu().numpy())
    return (np.concatenate(probs), np.vstack(embs), m,
            dict(final_corr2=last.get("corr2")))


# --------------------------------------------------------------------------
# cached cross-validation
# --------------------------------------------------------------------------
def cv_cached(JOINT, BONE, y, groups, speed, folds, seed, variant="plain",
              force=False):
    """Out-of-fold probs and embeddings for one (variant, seed). Cached.

    folds: list of (train_idx, test_idx) arrays.
    """
    path = CACHE / f"{variant}_seed{seed}.npz"
    if path.exists() and not force:
        z = np.load(path)
        print(f"  cache hit: {path.name}")
        return {k: z[k] for k in z.files}

    n = len(y)
    out = dict(p_joint=np.zeros(n), p_bone=np.zeros(n))
    emb = None
    corrs = []
    t0 = time.time()
    for fi, (tr, te) in enumerate(folds):
        assert not set(groups[tr]) & set(groups[te]), "subject leaked across folds"
        parts = []
        for name, X, key in (("joint", JOINT, "p_joint"), ("bone", BONE, "p_bone")):
            p, e, _, diag = train_stream(X[tr], y[tr], X[te], seed + 17 * fi,
                                         speed_tr=speed[tr], variant=variant,
                                         log=f"f{fi}/{name}")
            out[key][te] = p
            parts.append(e)
            if diag.get("final_corr2") is not None:
                corrs.append(diag["final_corr2"])
        e_cat = np.hstack(parts)
        if emb is None:
            emb = np.zeros((n, e_cat.shape[1]), dtype=np.float32)
        emb[te] = e_cat
        print(f"    fold {fi+1}/{len(folds)} done ({time.time()-t0:.0f}s elapsed)",
              flush=True)

    out["emb"] = emb
    out["p_fused"] = (out["p_joint"] + out["p_bone"]) / 2.0
    out["adv_corr2"] = np.array(corrs if corrs else [np.nan])
    np.savez_compressed(path, **out)
    print(f"  cached -> {path.name}  ({time.time()-t0:.0f}s)")
    return out


def speed_leakage(probs, speed, groups):
    """How much of the model's output is just walking speed?"""
    import pandas as pd
    s = pd.DataFrame({"g": groups, "p": probs, "s": speed}).groupby("g").mean()
    return float(np.corrcoef(s.p, s.s)[0, 1])


# --------------------------------------------------------------------------
if __name__ == "__main__":
    print("self-test on random data — checks shapes and that all three "
          "variants take a step\n")
    rng = np.random.default_rng(0)
    X = rng.standard_normal((24, 3, 48, NUM_JOINTS, 1)).astype(np.float32)
    y = np.array([0, 1] * 12)
    sp = rng.standard_normal(24).astype(np.float32)
    for v in ("plain", "mdn", "cfnet"):
        t = time.time()
        p, e, m, d = train_stream(X, y, X[:6], 0, speed_tr=sp, variant=v,
                                  epochs=2)
        print(f"  {v:6s} probs {p.shape}  emb {e.shape}  "
              f"corr2 {d.get('final_corr2')}  {time.time()-t:.1f}s")
    print("\nOK")
