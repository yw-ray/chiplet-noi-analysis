"""Train SurrogateV3 on the seed dataset.

Input:
  results/ml_placement/surrogate_v3_seed_data.npz

Output:
  results/ml_placement/surrogate_v3.pt        (model weights)
  results/ml_placement/surrogate_v3_train.log (training log)

Architecture defined in ml_express_warmstart.SurrogateV3:
  995 → 512 → 512 → 256 → 64 → 1 (log-latency).
"""

import math
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

sys.path.insert(0, str(Path(__file__).parent))
from ml_express_warmstart import SurrogateV3, DEVICE


SEED_PATH = Path('results/ml_placement/surrogate_v3_seed_data.npz')
WEIGHTS_PATH = Path('results/ml_placement/surrogate_v3.pt')
LOG_PATH = Path('results/ml_placement/surrogate_v3_train.log')

EPOCHS = 200
BATCH = 256
LR = 1e-4
WD = 1e-4
VAL_FRAC = 0.1
SEED = 42


def build_features(alloc, traffic, K, N, rate):
    """alloc: (n,496), traffic: (n,496), K: (n,), N: (n,), rate: (n,).
    Returns (n,995) feature matrix."""
    log_rate = np.log(np.maximum(rate, 1e-6)) / np.log(8.0)
    cols = [
        traffic,            # 496
        alloc,              # 496
        (K / 32.0)[:, None],
        (N / 8.0)[:, None],
        log_rate[:, None],
    ]
    return np.concatenate(cols, axis=1).astype(np.float32)


def main():
    rng = np.random.RandomState(SEED)
    data = np.load(SEED_PATH)
    alloc = data['alloc']
    traffic = data['traffic']
    K = data['K'].astype(np.float32)
    N = data['N'].astype(np.float32)
    rate = data['rate'].astype(np.float32)
    lat = data['lat'].astype(np.float32)
    n = len(lat)
    print(f'Loaded {n} pairs from {SEED_PATH}', flush=True)

    # Filter outliers (lat > 2000)
    mask = (lat > 0) & (lat < 2000)
    alloc, traffic, K, N, rate, lat = (a[mask] for a in
                                       (alloc, traffic, K, N, rate, lat))
    print(f'After outlier filter: {len(lat)} pairs', flush=True)

    feats = build_features(alloc, traffic, K, N, rate)
    y = np.log(lat).astype(np.float32)

    # Train/val split
    idx = rng.permutation(len(lat))
    n_val = max(1, int(len(lat) * VAL_FRAC))
    val_idx = idx[:n_val]
    train_idx = idx[n_val:]
    x_tr = torch.tensor(feats[train_idx]).to(DEVICE)
    y_tr = torch.tensor(y[train_idx]).to(DEVICE)
    x_va = torch.tensor(feats[val_idx]).to(DEVICE)
    y_va = torch.tensor(y[val_idx]).to(DEVICE)

    print(f'Train: {len(train_idx)}, Val: {len(val_idx)}', flush=True)

    model = SurrogateV3(input_dim=995).to(DEVICE)
    opt = optim.Adam(model.parameters(), lr=LR, weight_decay=WD)
    loss_fn = nn.MSELoss()

    log_lines = []
    best_val = float('inf')
    best_epoch = -1

    for ep in range(1, EPOCHS + 1):
        model.train()
        perm = torch.randperm(len(x_tr), device=DEVICE)
        epoch_loss = 0.0
        n_batches = 0
        for s in range(0, len(perm), BATCH):
            batch = perm[s:s + BATCH]
            xb = x_tr[batch]
            yb = y_tr[batch]
            pred = model(xb)
            loss = loss_fn(pred, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            epoch_loss += loss.item()
            n_batches += 1
        train_loss = epoch_loss / max(n_batches, 1)

        model.eval()
        with torch.no_grad():
            pred_va = model(x_va)
            val_loss = loss_fn(pred_va, y_va).item()
            # MAE in latency space
            pred_lat = torch.exp(pred_va).cpu().numpy()
            true_lat = torch.exp(y_va).cpu().numpy()
            mae = np.mean(np.abs(pred_lat - true_lat))
            mape = np.mean(np.abs(pred_lat - true_lat) / true_lat) * 100

        line = (f'ep {ep:>3}: train_mse={train_loss:.4f} '
                f'val_mse={val_loss:.4f} val_mae={mae:.1f} val_mape={mape:.1f}%')
        log_lines.append(line)
        if ep % 10 == 0 or ep == 1:
            print('  ' + line, flush=True)

        if val_loss < best_val:
            best_val = val_loss
            best_epoch = ep
            torch.save(model.state_dict(), WEIGHTS_PATH)

    print(f'\nBest val_mse={best_val:.4f} at epoch {best_epoch}', flush=True)
    print(f'Weights saved to {WEIGHTS_PATH}', flush=True)
    LOG_PATH.write_text('\n'.join(log_lines))
    print(f'Log saved to {LOG_PATH}', flush=True)


if __name__ == '__main__':
    main()
