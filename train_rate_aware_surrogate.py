"""Train rate-aware surrogate: input = (placement, rate) -> latency.

Collects (placement, rate, latency) triplets from cost_perf_6panel_* data
(1152 available) and trains an MLP with input_dim=501 (500 placement + 1 rate).

Saves model to results/ml_placement/surrogate_rate_aware.pt
"""
import json
import glob
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

RESULTS_DIR = Path('results/ml_placement')
DEVICE = torch.device('cpu')

WORKLOADS_OK = ['tree_allreduce', 'hybrid_tp_pp', 'moe', 'uniform_random']


class RateAwareSurrogate(nn.Module):
    """MLP: [traffic_496 + bpp + n_express_frac + K/32 + N/8 + log(rate)] -> latency"""
    def __init__(self, input_dim=501, hidden=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden), nn.ReLU(), nn.LayerNorm(hidden),
            nn.Linear(hidden, hidden), nn.ReLU(), nn.LayerNorm(hidden),
            nn.Linear(hidden, 64), nn.ReLU(),
            nn.Linear(64, 1),
        )
    def forward(self, x):
        return self.net(x).squeeze(-1)


def collect_rate_aware_data():
    """Return list of (feature_vec, latency) from all cost_perf runs, 4 rates each."""
    samples = []
    # Reference base_rate for normalizing 'rate multiplier'
    for wl in WORKLOADS_OK:
        fn = f'results/cost_perf_6panel_{wl}/cost_perf_6panel.json'
        try:
            data = json.load(open(fn))
        except FileNotFoundError:
            continue
        for panel_key, panel in data.items():
            K = panel['K']; N = panel['N']
            base_rate = panel['base_rate']
            # Traffic matrix available? use WORKLOADS to regenerate
            import ml_express_warmstart as mw
            R, C = {'K16_N4':(4,4),'K16_N8':(4,4),'K32_N4':(4,8),'K32_N8':(4,8),
                    'K8_N4':(2,4),'K8_N8':(2,4),'K64_N4':(8,8),'K64_N8':(8,8)}.get(
                        f'K{K}_N{N}', (4, 4 if K<=16 else 8))
            # Adjust: K=16 -> 4x4, K=32 -> 4x8
            if K == 16: R, C = 4, 4
            elif K == 32: R, C = 4, 8
            elif K == 8: R, C = 2, 4
            elif K == 64: R, C = 8, 8
            grid = mw.ChipletGrid(R, C)
            traffic = mw.WORKLOADS[wl](K, grid)
            traffic_flat = traffic[np.triu_indices(K, k=1)].astype(np.float64)
            t_max = traffic_flat.max()
            traffic_norm = (traffic_flat / t_max) if t_max > 0 else traffic_flat
            padded = list(traffic_norm) + [0.0] * (496 - len(traffic_norm))
            for exp in panel['experiments']:
                total_links = exp['total_links']
                if total_links == 0:
                    continue
                bpp = exp['budget_per_pair']
                n_express = exp['n_express']
                express_frac = n_express / total_links
                for rate_data in exp['rates']:
                    rate = rate_data['rate']
                    lat = rate_data.get('latency')
                    if lat is None or lat <= 0:
                        continue
                    # Feature: 500 (placement) + 1 (log rate / log base_rate)
                    rate_feature = np.log(rate / base_rate) / np.log(8.0)  # normalize 1x..8x to [0,1]
                    feat = padded + [
                        bpp / 8.0,
                        express_frac,
                        K / 32.0,
                        N / 8.0,
                        rate_feature,
                    ]
                    samples.append((feat, lat))
    return samples


def main():
    print("=== Collecting (placement, rate, latency) triplets ===")
    samples = collect_rate_aware_data()
    print(f"  Collected {len(samples)} samples")

    X = np.array([s[0] for s in samples], dtype=np.float32)
    y = np.array([s[1] for s in samples], dtype=np.float32)
    print(f"  X shape: {X.shape}, y range: {y.min():.1f}--{y.max():.1f}")

    # Train/val split
    np.random.seed(42)
    idx = np.random.permutation(len(X))
    n_train = int(0.85 * len(X))
    X_tr, y_tr = X[idx[:n_train]], y[idx[:n_train]]
    X_va, y_va = X[idx[n_train:]], y[idx[n_train:]]
    Xt_tr = torch.tensor(X_tr); yt_tr = torch.tensor(y_tr)
    Xt_va = torch.tensor(X_va); yt_va = torch.tensor(y_va)

    model = RateAwareSurrogate(input_dim=X.shape[1]).to(DEVICE)
    opt = optim.Adam(model.parameters(), lr=1e-3)
    sched = optim.lr_scheduler.ReduceLROnPlateau(opt, patience=30)

    best_val = float('inf'); best_state = None
    for epoch in range(800):
        model.train()
        pred = model(Xt_tr)
        loss = F.mse_loss(pred, yt_tr)
        opt.zero_grad(); loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            vp = model(Xt_va)
            vl = F.mse_loss(vp, yt_va).item()
            vmae = (vp - yt_va).abs().mean().item()
            # Correlation
            vpn = vp.numpy(); yvn = yt_va.numpy()
            from scipy.stats import spearmanr
            rho, _ = spearmanr(vpn, yvn)
        sched.step(vl)
        if vl < best_val:
            best_val = vl
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        if (epoch+1) % 100 == 0:
            print(f"  Ep{epoch+1}: train_mse={loss.item():.2f} val_mse={vl:.2f} val_mae={vmae:.2f} val_rho={rho:.3f}")

    model.load_state_dict(best_state)
    print(f"Best val MSE: {best_val:.2f}")

    # Save
    out = RESULTS_DIR / 'surrogate_rate_aware.pt'
    torch.save(model.state_dict(), out)
    print(f"Saved to {out}")

    # Also save metadata
    meta = {
        'input_dim': X.shape[1],
        'n_samples': len(samples),
        'n_train': len(X_tr),
        'n_val': len(X_va),
        'best_val_mse': float(best_val),
        'last_val_rho': float(rho),
    }
    with open(RESULTS_DIR / 'surrogate_rate_aware.meta.json', 'w') as f:
        json.dump(meta, f, indent=2)


if __name__ == '__main__':
    main()
