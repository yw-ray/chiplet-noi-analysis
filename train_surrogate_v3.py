"""Train surrogate v3: full alloc_flat in features.

Key change vs. v2 (rate-aware):
  v2 feature: [traffic_496, bpp/8, express_frac, K/32, N/8, log_rate] = 501 dim
  v3 feature: [traffic_496, alloc_496, K/32, N/8, log_rate]           = 995 dim

Including alloc_flat lets the model distinguish different link placements
with the same budget (bpp/express_frac), fixing the OOD problem for
moe-containing joint workload allocations found during MCTS search.

Training data: surrogate_data_v2_K{K}_N{N}.json (collected by
collect_surrogate_data_v2.py). Falls back to including original
rate-aware data (re-encoded with alloc_flat=zeros, as it lacks actual
alloc vectors — these still help the model learn traffic→latency mapping).

Saves to: results/ml_placement/surrogate_v3.pt
          results/ml_placement/surrogate_v3.meta.json
"""

import json
import math
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from scipy.stats import spearmanr

RESULTS_DIR = Path('results/ml_placement')
DEVICE = torch.device('cpu')
INPUT_DIM = 995   # traffic_496 + alloc_496 + K/32 + N/8 + log_rate


class SurrogateV3(nn.Module):
    """MLP: [traffic_496, alloc_496, K/32, N/8, log_rate] -> latency."""
    def __init__(self, input_dim=INPUT_DIM, hidden=512):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden), nn.ReLU(), nn.LayerNorm(hidden),
            nn.Linear(hidden, hidden), nn.ReLU(), nn.LayerNorm(hidden),
            nn.Linear(hidden, 256),    nn.ReLU(), nn.LayerNorm(256),
            nn.Linear(256, 64),        nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def load_v2_data():
    """Load new data from collect_surrogate_data_v2.py output files."""
    samples = []
    for K in [16, 32]:
        for N in [4, 8]:
            p = RESULTS_DIR / f'surrogate_data_v2_K{K}_N{N}.json'
            if not p.exists():
                continue
            data = json.loads(p.read_text())
            for entry in data:
                if entry.get('latency') is None:
                    continue
                traffic = entry['traffic_flat_norm'][:496]
                alloc = entry['alloc_flat_norm'][:496]
                K_e = entry['K']
                N_e = entry['N']
                rate_mult = entry['rate_mult']
                lat = entry['latency']
                log_rate = math.log(max(rate_mult, 1e-6)) / math.log(8.0)
                feat = traffic + alloc + [K_e / 32.0, N_e / 8.0, log_rate]
                samples.append((feat, lat))
            print(f'  K{K}_N{N}: {len(data)} entries loaded '
                  f'({sum(1 for e in data if e.get("latency") is not None)} valid)')
    return samples


def load_original_data():
    """Load original rate-aware data, re-encoded with alloc_flat=zeros.

    These samples teach the model traffic→latency mapping even though
    we don't have the actual alloc_flat. Using zeros for the alloc
    portion is a conservative approximation (equivalent to treating
    these as 'unknown placement' examples).
    """
    samples = []
    workloads_ok = ['tree_allreduce', 'hybrid_tp_pp', 'moe', 'uniform_random']
    for wl in workloads_ok:
        fn = f'results/cost_perf_6panel_{wl}/cost_perf_6panel.json'
        try:
            import json as _j
            data = _j.load(open(fn))
        except FileNotFoundError:
            continue
        from ml_express_warmstart import WORKLOADS, ChipletGrid
        for panel_key, panel in data.items():
            K = panel['K']
            N = panel['N']
            if K == 16:
                R, C = 4, 4
            elif K == 32:
                R, C = 4, 8
            elif K == 8:
                R, C = 2, 4
            else:
                continue
            grid = ChipletGrid(R, C)
            traffic = WORKLOADS[wl](K, grid)
            traffic_flat = traffic[np.triu_indices(K, k=1)].astype(np.float32)
            t_max = float(traffic_flat.max())
            traffic_norm = (traffic_flat / t_max if t_max > 0
                            else traffic_flat).tolist()
            traffic_padded = traffic_norm + [0.0] * (496 - len(traffic_norm))
            alloc_zeros = [0.0] * 496
            base_rate = panel['base_rate']
            for exp in panel['experiments']:
                for rate_data in exp['rates']:
                    rate = rate_data['rate']
                    lat = rate_data.get('latency')
                    if lat is None or lat <= 0:
                        continue
                    rate_mult = rate / base_rate
                    log_rate = math.log(max(rate_mult, 1e-6)) / math.log(8.0)
                    feat = traffic_padded + alloc_zeros + [K / 32.0, N / 8.0, log_rate]
                    samples.append((feat, float(lat)))
    print(f'  Original data: {len(samples)} samples (alloc=zeros)')
    return samples


def main():
    print('=== Loading training data ===')
    v2_samples = load_v2_data()
    orig_samples = load_original_data()

    if not v2_samples:
        print('ERROR: no v2 data found. Run collect_surrogate_data_v2.py first.')
        return

    all_samples = v2_samples + orig_samples
    print(f'Total: {len(all_samples)} samples '
          f'({len(v2_samples)} v2 + {len(orig_samples)} orig)')

    X = np.array([s[0] for s in all_samples], dtype=np.float32)
    y = np.array([s[1] for s in all_samples], dtype=np.float32)
    print(f'X shape: {X.shape}, y range: {y.min():.1f}--{y.max():.1f}')

    # Log-scale latency helps with heavy-tailed distribution
    y_log = np.log1p(y)

    np.random.seed(42)
    idx = np.random.permutation(len(X))
    n_train = int(0.85 * len(X))
    X_tr, y_tr = X[idx[:n_train]], y_log[idx[:n_train]]
    X_va, y_va_log = X[idx[n_train:]], y_log[idx[n_train:]]
    y_va_raw = y[idx[n_train:]]

    Xt_tr = torch.tensor(X_tr)
    yt_tr = torch.tensor(y_tr)
    Xt_va = torch.tensor(X_va)
    yt_va = torch.tensor(y_va_log)

    model = SurrogateV3(input_dim=X.shape[1]).to(DEVICE)
    opt = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    sched = optim.lr_scheduler.ReduceLROnPlateau(opt, patience=40, factor=0.5)

    best_val = float('inf')
    best_state = None
    best_rho = 0.0

    for epoch in range(1000):
        model.train()
        perm = torch.randperm(len(Xt_tr))
        batch_size = 512
        for i in range(0, len(perm), batch_size):
            idx_b = perm[i:i + batch_size]
            pred = model(Xt_tr[idx_b])
            loss = F.mse_loss(pred, yt_tr[idx_b])
            opt.zero_grad()
            loss.backward()
            opt.step()

        model.eval()
        with torch.no_grad():
            vp = model(Xt_va)
            vl = F.mse_loss(vp, yt_va).item()
            # Evaluate on raw latency for interpretability
            vp_raw = np.expm1(vp.numpy())
            vmae = float(np.mean(np.abs(vp_raw - y_va_raw)))
            rho, _ = spearmanr(vp_raw, y_va_raw)

        sched.step(vl)
        if vl < best_val:
            best_val = vl
            best_rho = float(rho)
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

        if (epoch + 1) % 100 == 0:
            print(f'  Ep{epoch+1:>4}: val_mse={vl:.3f} '
                  f'val_mae={vmae:.1f} val_rho={rho:.3f}')

    model.load_state_dict(best_state)
    print(f'\nBest val MSE: {best_val:.3f}, best rho: {best_rho:.3f}')

    out_pt = RESULTS_DIR / 'surrogate_v3.pt'
    torch.save(model.state_dict(), out_pt)
    print(f'Saved model to {out_pt}')

    meta = {
        'input_dim': X.shape[1],
        'n_samples_v2': len(v2_samples),
        'n_samples_orig': len(orig_samples),
        'n_total': len(all_samples),
        'n_train': n_train,
        'n_val': len(X) - n_train,
        'best_val_mse_log': float(best_val),
        'best_val_rho': best_rho,
        'note': 'v3: traffic_496 + alloc_496 + K/32 + N/8 + log_rate = 995 dim',
    }
    (RESULTS_DIR / 'surrogate_v3.meta.json').write_text(
        json.dumps(meta, indent=2))
    print(f'Saved metadata to {RESULTS_DIR}/surrogate_v3.meta.json')


if __name__ == '__main__':
    main()
