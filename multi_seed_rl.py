"""Run RL-WS with multiple seeds on 16 best-budget cells to produce CIs."""
import json
import time
from pathlib import Path

import numpy as np
import torch

import ml_express_warmstart as mw


RESULTS_DIR = Path('results/ml_placement')
CONFIG_DIR = Path('booksim_configs')
OUT_FILE = RESULTS_DIR / 'ml_comparison_multiseed.json'

SEEDS = [42, 123, 456]

# 16 best-budget cells from compute_stats (greedy best_budget per workload-K-N)
BEST_CELLS = [
    ('tree_allreduce', 16, 4, 4), ('tree_allreduce', 16, 8, 7),
    ('tree_allreduce', 32, 4, 2), ('tree_allreduce', 32, 8, 2),
    ('hybrid_tp_pp', 16, 4, 4), ('hybrid_tp_pp', 16, 8, 7),
    ('hybrid_tp_pp', 32, 4, 4), ('hybrid_tp_pp', 32, 8, 4),
    ('uniform_random', 16, 4, 4), ('uniform_random', 16, 8, 7),
    ('uniform_random', 32, 4, 4), ('uniform_random', 32, 8, 4),
    ('moe', 16, 4, 4), ('moe', 16, 8, 7),
    ('moe', 32, 4, 4), ('moe', 32, 8, 4),
]


def run_one(surrogate, wl, K, N, R, C, bpp, seed):
    torch.manual_seed(seed)
    np.random.seed(seed)

    grid = mw.ChipletGrid(R, C)
    traffic = mw.WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    n_adj = len(adj_pairs)
    budget = int(n_adj * bpp)
    npc = N * N
    base_rate = mw.TOTAL_LOAD_BASE / (K * npc)

    label = f'K{K}_N{N}_bpp{bpp}_s{seed}'
    traf_file = f'traffic_ms_{wl}_{label}.txt'
    mw.gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

    # Greedy
    max_dist = max(2, min(3, max(R, C) - 1))
    greedy_alloc = mw.alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}
    cfg_g = f'ms_{wl}_{label}_greedy'
    mw.gen_anynet_config(cfg_g, grid, greedy_capped, chip_n=N, outdir=CONFIG_DIR)
    r_g = mw.run_booksim(cfg_g, traf_file, base_rate, timeout=300)
    L_g = r_g['latency']

    # RL-WS with this seed
    t0 = time.time()
    rl_alloc, rl_pred, baseline_pred = mw.train_warmstart_rl(
        surrogate, wl, K, N, R, C, bpp, n_episodes=200)
    train_time = time.time() - t0
    rl_capped = {p: min(n, N) for p, n in rl_alloc.items()}
    cfg_rl = f'ms_{wl}_{label}_rl'
    mw.gen_anynet_config(cfg_rl, grid, rl_capped, chip_n=N, outdir=CONFIG_DIR)
    r_rl = mw.run_booksim(cfg_rl, traf_file, base_rate, timeout=300)
    L_rl = r_rl['latency']

    # adj uniform (for saving% base) — reuse from ml_comparison_fast
    return {
        'L_greedy': L_g,
        'L_rl_raw': L_rl,
        'L_rl_fb': min(L_g, L_rl) if (L_g and L_rl) else (L_g or L_rl),
        'train_time': train_time,
    }


def main():
    print('=== Multi-seed RL-WS ===', flush=True)
    surrogate = mw.load_surrogate()

    existing = []
    if OUT_FILE.exists():
        existing = json.load(open(OUT_FILE))
    done = {(r['workload'], r['K'], r['N'], r['budget_per_pair'], r['seed']) for r in existing}

    out = list(existing)
    for (wl, K, N, bpp) in BEST_CELLS:
        R, C = (4, 4) if K == 16 else (4, 8)
        for seed in SEEDS:
            key = (wl, K, N, bpp, seed)
            if key in done:
                print(f'SKIP {wl} K{K}N{N} b{bpp}x seed={seed}', flush=True)
                continue
            print(f'\n>>> {wl} K{K}N{N} b{bpp}x seed={seed}', flush=True)
            try:
                res = run_one(surrogate, wl, K, N, R, C, bpp, seed)
                res.update({'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp, 'seed': seed})
                out.append(res)
                with open(OUT_FILE, 'w') as f:
                    json.dump(out, f, indent=2)
                print(f'    greedy={res["L_greedy"]} rl_raw={res["L_rl_raw"]} rl_fb={res["L_rl_fb"]} t={res["train_time"]:.1f}s', flush=True)
            except Exception as e:
                print(f'    ERROR: {e}', flush=True)

    print(f'\nDone. {len(out)} runs saved to {OUT_FILE}', flush=True)


if __name__ == '__main__':
    main()
