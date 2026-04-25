"""Per-cell measurement for missing bpp points.

Measures all 4 methods (adj_uniform, greedy, fbfly, rl_ws) at base_rate for
a given (workload, K, N, bpp) and appends result to bpp_extra.json.

Usage:  python3 bpp_cell.py <workload> <K> <N> <bpp>
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
OUT_FILE = RESULTS_DIR / 'bpp_extra.json'


def main():
    wl = sys.argv[1]
    K = int(sys.argv[2])
    N = int(sys.argv[3])
    bpp = int(sys.argv[4])

    print(f'>>> {wl} K{K}N{N} b{bpp}x (bpp extra)', flush=True)

    R, C = (4, 4) if K == 16 else (4, 8)
    grid = mw.ChipletGrid(R, C)
    traffic = mw.WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs()
    n_adj = len(adj_pairs)
    budget = int(n_adj * bpp)
    npc = N * N
    base_rate = mw.TOTAL_LOAD_BASE / (K * npc)

    label = f'K{K}_N{N}_bpp{bpp}'
    traf_file = f'traffic_bpp_{wl}_{label}.txt'
    mw.gen_traffic_matrix(grid, traffic, npc, mw.CONFIG_DIR / traf_file)

    # adj_uniform
    per_adj = budget // n_adj
    residual = budget - per_adj * n_adj
    adj_alloc = {p: per_adj + (1 if i < residual else 0)
                 for i, p in enumerate(sorted(adj_pairs))}
    adj_capped = {p: min(n, N) for p, n in adj_alloc.items()}
    cfg_adj = f'bpp_{wl}_{label}_adj'
    mw.gen_anynet_config(cfg_adj, grid, adj_capped, chip_n=N, outdir=mw.CONFIG_DIR)

    # greedy
    max_dist = max(2, min(3, max(R, C) - 1))
    greedy_alloc = mw.alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}
    cfg_g = f'bpp_{wl}_{label}_greedy'
    mw.gen_anynet_config(cfg_g, grid, greedy_capped, chip_n=N, outdir=mw.CONFIG_DIR)

    # FBfly (iso-budget, iso-max_dist)
    fb_alloc = flattened_butterfly_alloc(grid, budget, per_pair_cap=N, max_dist=max_dist)
    fb_capped = {p: min(n, N) for p, n in fb_alloc.items()}
    cfg_fb = f'bpp_{wl}_{label}_fbfly'
    mw.gen_anynet_config(cfg_fb, grid, fb_capped, chip_n=N, outdir=mw.CONFIG_DIR)

    # RL-WS (seed=42)
    torch.manual_seed(42)
    np.random.seed(42)
    surrogate = mw.load_surrogate()
    t_rl = time.time()
    rl_alloc, _, _ = mw.train_warmstart_rl(
        surrogate, wl, K, N, R, C, bpp, n_episodes=200)
    rl_capped = {p: min(n, N) for p, n in rl_alloc.items()}
    cfg_rl = f'bpp_{wl}_{label}_rl'
    mw.gen_anynet_config(cfg_rl, grid, rl_capped, chip_n=N, outdir=mw.CONFIG_DIR)
    train_time = time.time() - t_rl

    # Measure all 4 methods at base_rate
    L_adj = mw.run_booksim(cfg_adj, traf_file, base_rate, timeout=900)['latency']
    L_g = mw.run_booksim(cfg_g, traf_file, base_rate, timeout=900)['latency']
    L_fb = mw.run_booksim(cfg_fb, traf_file, base_rate, timeout=900)['latency']
    L_rl_raw = mw.run_booksim(cfg_rl, traf_file, base_rate, timeout=900)['latency']

    # Post-hoc fallback: RL <= greedy
    L_rl_fb = min(L_g, L_rl_raw) if (L_g and L_rl_raw) else (L_g or L_rl_raw)
    used_fb = (L_rl_raw is not None) and (L_g is not None) and (L_rl_raw > L_g)

    result = {
        'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp, 'budget': budget,
        'L_adj': L_adj, 'L_greedy': L_g, 'L_fbfly': L_fb,
        'L_rl_raw': L_rl_raw, 'L_rl_fb': L_rl_fb, 'used_fallback': used_fb,
        'train_time': train_time,
        'n_exp_greedy': sum(1 for p, n in greedy_alloc.items() if p not in set(adj_pairs) and n > 0),
        'n_exp_fbfly': sum(1 for p, n in fb_alloc.items() if p not in set(adj_pairs) and n > 0),
        'n_exp_rl': sum(1 for p, n in rl_alloc.items() if p not in set(adj_pairs) and n > 0),
    }

    sv_g = (L_adj - L_g)/L_adj*100 if (L_adj and L_g) else None
    sv_fb = (L_adj - L_fb)/L_adj*100 if (L_adj and L_fb) else None
    sv_rl = (L_adj - L_rl_fb)/L_adj*100 if (L_adj and L_rl_fb) else None
    print(f'    L_adj={L_adj} L_greedy={L_g} L_fbfly={L_fb} L_rl_fb={L_rl_fb}', flush=True)
    print(f'    sv_g={sv_g:+.2f}%  sv_fb={sv_fb:+.2f}%  sv_rl={sv_rl:+.2f}%', flush=True)

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
