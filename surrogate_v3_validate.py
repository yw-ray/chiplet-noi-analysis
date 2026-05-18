"""Compare RateAwareSurrogate (current) vs SurrogateV3 (new) on the seed
dataset. Decision: if V3 has lower MAPE, especially on dense workloads,
proceed to plug it into MCTS/RL.
"""

import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from ml_express_warmstart import (
    RateAwareSurrogate, SurrogateV3, DEVICE,
)


def load_v3():
    model = SurrogateV3(input_dim=995).to(DEVICE)
    model.load_state_dict(torch.load(
        'results/ml_placement/surrogate_v3.pt', map_location=DEVICE))
    model.eval()
    return model


def load_ra():
    model = RateAwareSurrogate(input_dim=501).to(DEVICE)
    model.load_state_dict(torch.load(
        'results/ml_placement/surrogate_rate_aware.pt', map_location=DEVICE))
    model.eval()
    return model


def predict_v3(model, alloc, traffic, K, N, rate):
    log_rate = np.log(np.maximum(rate, 1e-6)) / np.log(8.0)
    feats = np.concatenate([
        traffic, alloc,
        (K / 32.0)[:, None],
        (N / 8.0)[:, None],
        log_rate[:, None],
    ], axis=1).astype(np.float32)
    x = torch.tensor(feats).to(DEVICE)
    with torch.no_grad():
        log_pred = model(x).cpu().numpy()
    return np.exp(log_pred)


def predict_ra(model, alloc, traffic, K, N, rate, n_adj_lookup):
    """RA features: traffic_flat + [bpp, n_express_ratio, K/32, N/8, log_rate].
    alloc here is pre-normalized (alloc/N), so reconstruct counts.
    """
    log_rate = np.log(np.maximum(rate, 1e-6)) / np.log(8.0)
    # alloc was stored normalized by N. Recover counts:
    counts = alloc * N[:, None]  # (n, 496)
    total = counts.sum(axis=1)
    n_pairs = (counts > 0).sum(axis=1)
    # n_express needs to know which idx are non-adj. Approximate by total.
    # The RA surrogate trained on (bpp, n_express_ratio).
    n_adj = np.array([n_adj_lookup(int(k)) for k in K], dtype=np.float32)
    bpp = total / np.maximum(n_adj, 1)
    n_express_ratio = (n_pairs - n_adj) / np.maximum(total, 1)
    n_express_ratio = np.clip(n_express_ratio, 0, None)

    feats = np.concatenate([
        traffic,
        (bpp / 8.0)[:, None],
        n_express_ratio[:, None],
        (K / 32.0)[:, None],
        (N / 8.0)[:, None],
        log_rate[:, None],
    ], axis=1).astype(np.float32)
    x = torch.tensor(feats).to(DEVICE)
    with torch.no_grad():
        pred = model(x).cpu().numpy()
    return pred  # already in lat scale, not log


def n_adj_for(K):
    if K == 16: return 24
    if K == 32: return 52
    return 0


def main():
    data = np.load('results/ml_placement/surrogate_v3_seed_data.npz')
    alloc = data['alloc']
    traffic = data['traffic']
    K = data['K'].astype(np.float32)
    N = data['N'].astype(np.float32)
    rate = data['rate'].astype(np.float32)
    lat = data['lat'].astype(np.float32)

    mask = (lat > 0) & (lat < 2000)
    alloc, traffic, K, N, rate, lat = (a[mask] for a in
                                       (alloc, traffic, K, N, rate, lat))

    ra = load_ra()
    v3 = load_v3()
    pred_ra = predict_ra(ra, alloc, traffic, K, N, rate, n_adj_for)
    pred_v3 = predict_v3(v3, alloc, traffic, K, N, rate)

    abs_err_ra = np.abs(pred_ra - lat)
    abs_err_v3 = np.abs(pred_v3 - lat)
    pct_err_ra = abs_err_ra / lat * 100
    pct_err_v3 = abs_err_v3 / lat * 100

    print('=== Overall surrogate comparison (n='
          f'{len(lat)} pairs) ===')
    print(f'  RA  MAPE: {pct_err_ra.mean():.1f}% '
          f'(median {np.median(pct_err_ra):.1f}%)')
    print(f'  V3  MAPE: {pct_err_v3.mean():.1f}% '
          f'(median {np.median(pct_err_v3):.1f}%)')
    print(f'  RA  MAE: {abs_err_ra.mean():.1f}')
    print(f'  V3  MAE: {abs_err_v3.mean():.1f}')

    # Per-K split
    print('\n=== By K ===')
    for k in [16, 32]:
        m = (K == k)
        if m.sum() == 0: continue
        print(f'  K={k} (n={m.sum()}): '
              f'RA={pct_err_ra[m].mean():.1f}%, V3={pct_err_v3[m].mean():.1f}%')

    # Per-N split
    print('\n=== By N ===')
    for n_val in [4, 8]:
        m = (N == n_val)
        if m.sum() == 0: continue
        print(f'  N={n_val} (n={m.sum()}): '
              f'RA={pct_err_ra[m].mean():.1f}%, V3={pct_err_v3[m].mean():.1f}%')

    # Per latency bucket
    print('\n=== By lat bucket ===')
    buckets = [(0, 80), (80, 200), (200, 500), (500, 2000)]
    for lo, hi in buckets:
        m = (lat >= lo) & (lat < hi)
        if m.sum() == 0: continue
        print(f'  [{lo:>4},{hi:>4}) (n={m.sum():>4}): '
              f'RA={pct_err_ra[m].mean():.1f}%, V3={pct_err_v3[m].mean():.1f}%')


if __name__ == '__main__':
    main()
