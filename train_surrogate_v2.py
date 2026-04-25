"""Train surrogate v2: rate-aware with EXPANDED training data.

Sources:
  1) cost_perf_6panel_*/cost_perf_6panel.json (1152 original samples)
  2) results/ml_placement/rate_sweep.json (16 cells × 4 methods × 4 rates = 256 new)

Output: results/ml_placement/surrogate_rate_aware_v2.pt
"""
import json
import glob
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from scipy.stats import spearmanr

import ml_express_warmstart as mw
from butterfly_baseline import flattened_butterfly_alloc

RESULTS_DIR = Path('results/ml_placement')
DEVICE = torch.device('cpu')
WORKLOADS_OK = ['tree_allreduce', 'hybrid_tp_pp', 'moe', 'uniform_random']


class RateAwareSurrogate(nn.Module):
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


def _make_feat(traffic_flat_norm, bpp, n_express, total_links, K, N, rate, base_rate):
    padded = list(traffic_flat_norm) + [0.0] * (496 - len(traffic_flat_norm))
    express_frac = n_express / max(total_links, 1)
    rate_feat = np.log(rate / base_rate) / np.log(8.0)
    return padded + [bpp / 8.0, express_frac, K / 32.0, N / 8.0, rate_feat]


def collect_original():
    samples = []
    for wl in WORKLOADS_OK:
        fn = f'results/cost_perf_6panel_{wl}/cost_perf_6panel.json'
        try: data = json.load(open(fn))
        except FileNotFoundError: continue
        for panel_key, panel in data.items():
            K = panel['K']; N = panel['N']; base_rate = panel['base_rate']
            R, C = (4, 4) if K <= 16 else (4, 8)
            if K == 16: R, C = 4, 4
            elif K == 32: R, C = 4, 8
            elif K == 8: R, C = 2, 4
            elif K == 64: R, C = 8, 8
            grid = mw.ChipletGrid(R, C)
            traffic = mw.WORKLOADS[wl](K, grid)
            t_flat = traffic[np.triu_indices(K, k=1)].astype(np.float64)
            t_max = t_flat.max()
            t_norm = (t_flat / t_max) if t_max > 0 else t_flat
            for exp in panel['experiments']:
                total = exp['total_links']
                if total == 0: continue
                for rd in exp['rates']:
                    rate = rd['rate']; lat = rd.get('latency')
                    if lat is None or lat <= 0: continue
                    feat = _make_feat(t_norm, exp['budget_per_pair'], exp['n_express'],
                                       total, K, N, rate, base_rate)
                    samples.append((feat, lat))
    return samples


def collect_rate_sweep():
    """256 new samples from rate_sweep.json (16 cells × 4 methods × 4 rates)."""
    samples = []
    p = RESULTS_DIR / 'rate_sweep.json'
    if not p.exists(): return samples
    data = json.load(open(p))
    for r in data:
        wl, K, N, bpp = r['workload'], r['K'], r['N'], r['budget_per_pair']
        R, C = (4, 4) if K == 16 else (4, 8)
        grid = mw.ChipletGrid(R, C)
        traffic = mw.WORKLOADS[wl](K, grid)
        adj_pairs = grid.get_adj_pairs(); n_adj = len(adj_pairs)
        adj_set = set(adj_pairs)
        budget = int(n_adj * bpp)
        npc = N * N; base_rate = mw.TOTAL_LOAD_BASE / (K * npc)
        t_flat = traffic[np.triu_indices(K, k=1)].astype(np.float64)
        t_max = t_flat.max()
        t_norm = (t_flat / t_max) if t_max > 0 else t_flat

        # Reconstruct allocations for each method
        max_dist = max(2, min(3, max(R, C) - 1))
        # adj_uniform
        per = budget // n_adj; res = budget - per * n_adj
        adj_alloc = {p: per + (1 if i < res else 0) for i, p in enumerate(sorted(adj_pairs))}
        # greedy
        g_alloc = mw.alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
        # fbfly
        fb_alloc = flattened_butterfly_alloc(grid, budget, per_pair_cap=N, max_dist=max_dist)
        # rl_ws: skip (we don't have allocation here easily)

        for method_name, alloc_dict in [('adj_uniform', adj_alloc), ('greedy', g_alloc), ('fbfly', fb_alloc)]:
            n_exp = sum(1 for p, n in alloc_dict.items() if p not in adj_set and n > 0)
            total_links = sum(alloc_dict.values())
            for i, rate in enumerate(r['rates']):
                lat = r[method_name]['latency'][i]
                if lat is None or lat <= 0: continue
                feat = _make_feat(t_norm, bpp, n_exp, total_links, K, N, rate, base_rate)
                samples.append((feat, lat))
    return samples


def main():
    print('=== Collecting training data ===', flush=True)
    orig = collect_original()
    new = collect_rate_sweep()
    print(f'  original: {len(orig)}  new rate_sweep: {len(new)}  total: {len(orig)+len(new)}')
    samples = orig + new

    X = np.array([s[0] for s in samples], dtype=np.float32)
    y = np.array([s[1] for s in samples], dtype=np.float32)
    print(f'  X shape: {X.shape}, y range: {y.min():.1f}-{y.max():.1f}')

    np.random.seed(42)
    idx = np.random.permutation(len(X))
    n_tr = int(0.85 * len(X))
    Xt = torch.tensor(X[idx[:n_tr]]); yt = torch.tensor(y[idx[:n_tr]])
    Xv = torch.tensor(X[idx[n_tr:]]); yv = torch.tensor(y[idx[n_tr:]])

    model = RateAwareSurrogate(input_dim=X.shape[1]).to(DEVICE)
    opt = optim.Adam(model.parameters(), lr=1e-3)
    sched = optim.lr_scheduler.ReduceLROnPlateau(opt, patience=30)
    best = float('inf'); bs = None
    for ep in range(1000):
        model.train()
        p = model(Xt); loss = F.mse_loss(p, yt)
        opt.zero_grad(); loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            vp = model(Xv); vl = F.mse_loss(vp, yv).item()
            rho, _ = spearmanr(vp.numpy(), yv.numpy())
        sched.step(vl)
        if vl < best:
            best = vl; bs = {k: v.clone() for k, v in model.state_dict().items()}
        if (ep+1) % 100 == 0:
            print(f'  Ep{ep+1}: train={loss.item():.2f} val={vl:.2f} rho={rho:.3f}')

    model.load_state_dict(bs)
    print(f'Best val MSE: {best:.2f}')
    torch.save(model.state_dict(), RESULTS_DIR / 'surrogate_rate_aware_v2.pt')
    print(f'Saved to {RESULTS_DIR / "surrogate_rate_aware_v2.pt"}')


if __name__ == '__main__':
    main()
