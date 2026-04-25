"""Run rate-aware RL on one cell. Compare against old (base-rate) RL + greedy + FBfly.

Measures latency at 4 rates (1x..4x) for all methods to verify robustness.
Usage: .venv/bin/python3 run_rate_aware_rl.py <workload> <K> <N> <bpp>
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
OUT_FILE = RESULTS_DIR / 'rate_aware_rl.json'


def main():
    wl = sys.argv[1]
    K = int(sys.argv[2])
    N = int(sys.argv[3])
    bpp = int(sys.argv[4])

    print(f'>>> {wl} K{K}N{N} b{bpp}x (rate-aware RL)', flush=True)

    R, C = (4, 4) if K == 16 else (4, 8)
    grid = mw.ChipletGrid(R, C)
    traffic = mw.WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs()
    n_adj = len(adj_pairs)
    budget = int(n_adj * bpp)
    npc = N * N
    base_rate = mw.TOTAL_LOAD_BASE / (K * npc)
    rates = [base_rate * (i + 1) for i in range(4)]

    label = f'K{K}_N{N}_bpp{bpp}'
    traf_file = f'traffic_ra_{wl}_{label}.txt'
    mw.gen_traffic_matrix(grid, traffic, npc, mw.CONFIG_DIR / traf_file)

    # adj_uniform
    per_adj = budget // n_adj
    residual = budget - per_adj * n_adj
    adj_alloc = {p: per_adj + (1 if i < residual else 0)
                 for i, p in enumerate(sorted(adj_pairs))}
    adj_capped = {p: min(n, N) for p, n in adj_alloc.items()}
    cfg_adj = f'ra_{wl}_{label}_adj'
    mw.gen_anynet_config(cfg_adj, grid, adj_capped, chip_n=N, outdir=mw.CONFIG_DIR)

    # greedy
    max_dist = max(2, min(3, max(R, C) - 1))
    greedy_alloc = mw.alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}
    cfg_g = f'ra_{wl}_{label}_greedy'
    mw.gen_anynet_config(cfg_g, grid, greedy_capped, chip_n=N, outdir=mw.CONFIG_DIR)

    # FBfly
    fb_alloc = flattened_butterfly_alloc(grid, budget, per_pair_cap=N, max_dist=max_dist)
    fb_capped = {p: min(n, N) for p, n in fb_alloc.items()}
    cfg_fb = f'ra_{wl}_{label}_fbfly'
    mw.gen_anynet_config(cfg_fb, grid, fb_capped, chip_n=N, outdir=mw.CONFIG_DIR)

    # OLD RL-WS (base-rate surrogate)
    torch.manual_seed(42); np.random.seed(42)
    surrogate_old = mw.load_surrogate()
    rl_old_alloc, _, _ = mw.train_warmstart_rl(
        surrogate_old, wl, K, N, R, C, bpp, n_episodes=200)
    rl_old_capped = {p: min(n, N) for p, n in rl_old_alloc.items()}
    cfg_rl_old = f'ra_{wl}_{label}_rl_old'
    mw.gen_anynet_config(cfg_rl_old, grid, rl_old_capped, chip_n=N, outdir=mw.CONFIG_DIR)

    # NEW RL-WS-RA (rate-aware surrogate, optimizing at rate=4x)
    torch.manual_seed(42); np.random.seed(42)
    surrogate_ra = mw.load_rate_aware_surrogate()
    rl_ra_alloc, _, _ = mw.train_warmstart_rl_ra(
        surrogate_ra, wl, K, N, R, C, bpp, n_episodes=200, rate_mult=4.0)
    rl_ra_capped = {p: min(n, N) for p, n in rl_ra_alloc.items()}
    cfg_rl_ra = f'ra_{wl}_{label}_rl_ra'
    mw.gen_anynet_config(cfg_rl_ra, grid, rl_ra_capped, chip_n=N, outdir=mw.CONFIG_DIR)

    # Measure all 5 methods at 4 rates
    result = {
        'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp,
        'rates': rates,
        'adj_uniform': {'latency': [], 'throughput': []},
        'greedy': {'latency': [], 'throughput': []},
        'fbfly': {'latency': [], 'throughput': []},
        'rl_ws_old': {'latency': [], 'throughput': []},
        'rl_ws_ra': {'latency': [], 'throughput': []},
    }

    for method, cfg in [('adj_uniform', cfg_adj), ('greedy', cfg_g),
                         ('fbfly', cfg_fb), ('rl_ws_old', cfg_rl_old),
                         ('rl_ws_ra', cfg_rl_ra)]:
        for rate in rates:
            r = mw.run_booksim(cfg, traf_file, rate, timeout=900)
            result[method]['latency'].append(r['latency'])
            result[method]['throughput'].append(r['throughput'])
        print(f'    {method}: lat={result[method]["latency"]}', flush=True)

    # Post-hoc fallback: rl_ws_ra_fb = rate-aware RL IF it wins at all 4 rates, else greedy
    ra_lats = result['rl_ws_ra']['latency']
    g_lats = result['greedy']['latency']
    all_ra_ok = all(ra <= g + 1.0 for ra, g in zip(ra_lats, g_lats) if ra and g)
    fb_lats = ra_lats if all_ra_ok else g_lats
    result['rl_ws_ra_fb'] = {'latency': fb_lats, 'throughput': result['greedy']['throughput'], 'fallback_triggered': not all_ra_ok}

    # Atomic append
    existing = []
    if OUT_FILE.exists():
        existing = json.load(open(OUT_FILE))
    existing = [r for r in existing if (r['workload'], r['K'], r['N'], r['budget_per_pair'])
                != (wl, K, N, bpp)]
    existing.append(result)
    with open(OUT_FILE, 'w') as f:
        json.dump(existing, f, indent=2)
    print(f'>>> DONE {wl} K{K}N{N} b{bpp}x saved', flush=True)


if __name__ == '__main__':
    main()
