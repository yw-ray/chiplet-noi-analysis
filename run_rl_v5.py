"""RL v5: surrogate v2 + 15 seeds + top-5 + 1000 episodes.

Target: close the 4 cells where v4 lost to FBfly by +0.3-0.7 cycle.
Usage: .venv/bin/python3 run_rl_v5.py <workload> <K> <N> <bpp>
"""
import json
import sys
import time
from pathlib import Path
import numpy as np
import torch

import ml_express_warmstart as mw
from butterfly_baseline import flattened_butterfly_alloc

RESULTS_DIR = Path('results/ml_placement')
OUT_FILE = RESULTS_DIR / 'rl_v5.json'

RATE_WEIGHTS = {1.0: 1.0, 2.0: 1.0, 3.0: 1.0, 4.0: 2.0}
SEEDS_GREEDY = list(range(42, 42 + 8))   # 8 seeds
SEEDS_FBFLY  = list(range(100, 100 + 8)) # 8 seeds  (total 16)
TOP_K = 3
N_EPISODES = 1000
ENTROPY_COEF = 0.01


def load_surrogate_v2():
    """Load rate-aware surrogate v2 (trained on expanded data)."""
    import torch.nn as nn
    class RAv2(nn.Module):
        def __init__(self, input_dim=501, hidden=256):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, hidden), nn.ReLU(), nn.LayerNorm(hidden),
                nn.Linear(hidden, hidden), nn.ReLU(), nn.LayerNorm(hidden),
                nn.Linear(hidden, 64), nn.ReLU(),
                nn.Linear(64, 1),
            )
        def forward(self, x): return self.net(x).squeeze(-1)
    model = RAv2(input_dim=501).to(mw.DEVICE)
    path = RESULTS_DIR / 'surrogate_rate_aware_v2.pt'
    model.load_state_dict(torch.load(path, map_location=mw.DEVICE))
    model.eval()
    print(f"  Loaded surrogate v2 from {path}", flush=True)
    return model


def main():
    wl = sys.argv[1]; K = int(sys.argv[2]); N = int(sys.argv[3]); bpp = int(sys.argv[4])
    print(f'>>> {wl} K{K}N{N} b{bpp}x (v5: 30-seed, surrogate v2, top-{TOP_K}, {N_EPISODES}ep)', flush=True)
    t0 = time.time()

    R, C = (4, 4) if K == 16 else (4, 8)
    grid = mw.ChipletGrid(R, C)
    traffic = mw.WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs()
    n_adj = len(adj_pairs); budget = int(n_adj * bpp)
    npc = N * N; base_rate = mw.TOTAL_LOAD_BASE / (K * npc)
    rates = [base_rate * (i + 1) for i in range(4)]

    label = f'K{K}_N{N}_bpp{bpp}'
    traf = f'traffic_v5_{wl}_{label}.txt'
    mw.gen_traffic_matrix(grid, traffic, npc, mw.CONFIG_DIR / traf)

    # Baselines
    per = budget // n_adj; res = budget - per * n_adj
    adj_alloc = {p: per + (1 if i < res else 0) for i, p in enumerate(sorted(adj_pairs))}
    adj_c = {p: min(n, N) for p, n in adj_alloc.items()}
    cfg_adj = f'v5_{wl}_{label}_adj'; mw.gen_anynet_config(cfg_adj, grid, adj_c, chip_n=N, outdir=mw.CONFIG_DIR)

    max_dist = max(2, min(3, max(R, C) - 1))
    g_alloc = mw.alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    g_c = {p: min(n, N) for p, n in g_alloc.items()}
    cfg_g = f'v5_{wl}_{label}_greedy'; mw.gen_anynet_config(cfg_g, grid, g_c, chip_n=N, outdir=mw.CONFIG_DIR)

    fb_alloc = flattened_butterfly_alloc(grid, budget, per_pair_cap=N, max_dist=max_dist)
    fb_c = {p: min(n, N) for p, n in fb_alloc.items()}
    cfg_fb = f'v5_{wl}_{label}_fbfly'; mw.gen_anynet_config(cfg_fb, grid, fb_c, chip_n=N, outdir=mw.CONFIG_DIR)

    # RL v5: 30 seeds × top-5 = 150 candidates
    surrogate = load_surrogate_v2()
    candidates = []
    for warm_name, warm_alloc, seeds in [
            ('greedy', g_c, SEEDS_GREEDY),
            ('fbfly', fb_c, SEEDS_FBFLY)]:
        for seed in seeds:
            torch.manual_seed(seed); np.random.seed(seed)
            top_k = mw.train_warmstart_rl_ra(
                surrogate, wl, K, N, R, C, bpp,
                n_episodes=N_EPISODES, rate_mult=4.0,
                rate_weights=RATE_WEIGHTS,
                warm_start_alloc=warm_alloc,
                entropy_coef=ENTROPY_COEF,
                top_k=TOP_K)
            for k_idx, (alloc, pred, _) in enumerate(top_k):
                rl_c = {p: min(n, N) for p, n in alloc.items()}
                cfg = f'v5_{wl}_{label}_{warm_name}_s{seed}_k{k_idx}'
                mw.gen_anynet_config(cfg, grid, rl_c, chip_n=N, outdir=mw.CONFIG_DIR)
                candidates.append((f'{warm_name}_s{seed}_k{k_idx}', rl_c, cfg))

    print(f'    Generated {len(candidates)} candidates', flush=True)

    result = {
        'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp,
        'rates': rates,
        'adj_uniform': {'latency': [], 'throughput': []},
        'greedy': {'latency': [], 'throughput': []},
        'fbfly': {'latency': [], 'throughput': []},
        'candidates': {},
    }
    for method, cfg in [('adj_uniform', cfg_adj), ('greedy', cfg_g), ('fbfly', cfg_fb)]:
        for rate in rates:
            r = mw.run_booksim(cfg, traf, rate, timeout=900)
            result[method]['latency'].append(r['latency'])
            result[method]['throughput'].append(r['throughput'])
        print(f'    {method}: max={max(result[method]["latency"]):.1f}', flush=True)

    for tag, alloc, cfg in candidates:
        lats, tps = [], []
        for rate in rates:
            r = mw.run_booksim(cfg, traf, rate, timeout=900)
            lats.append(r['latency']); tps.append(r['throughput'])
        result['candidates'][tag] = {'latency': lats, 'throughput': tps}

    best_tag = min(result['candidates'].keys(),
                    key=lambda t: max(result['candidates'][t]['latency']))
    best = result['candidates'][best_tag]
    result['ours_v5'] = {
        'latency': best['latency'], 'throughput': best['throughput'],
        'best_candidate': best_tag,
    }
    dt = time.time() - t0
    print(f'    ours_v5: best={best_tag}, max_lat={max(best["latency"]):.1f}, elapsed={dt:.0f}s', flush=True)

    existing = json.load(open(OUT_FILE)) if OUT_FILE.exists() else []
    existing = [r for r in existing if (r['workload'], r['K'], r['N'], r['budget_per_pair']) != (wl, K, N, bpp)]
    existing.append(result)
    with open(OUT_FILE, 'w') as f: json.dump(existing, f, indent=2)
    print(f'>>> DONE', flush=True)


if __name__ == '__main__':
    main()
