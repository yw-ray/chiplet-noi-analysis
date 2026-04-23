"""Run a single PARL seed (for parallel execution)."""
import json
import sys
import time
from pathlib import Path

import parl_baseline as pb
from ml_express_warmstart import (
    ChipletGrid, WORKLOADS, alloc_express_greedy, gen_traffic_matrix,
    gen_anynet_config, run_booksim, load_surrogate, CONFIG_DIR, TOTAL_LOAD_BASE,
)

RESULTS_DIR = Path('results/ml_placement')
OUT_FILE = RESULTS_DIR / 'parl_baseline.json'


def main():
    seed = int(sys.argv[1])

    wl, K, N, bpp = 'moe', 32, 8, 4
    R, C = (4, 8)
    print(f'>>> PARL seed={seed} ({wl} K{K}N{N} b{bpp}x)', flush=True)

    surrogate = load_surrogate()
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    n_adj = len(adj_pairs)
    budget = int(n_adj * bpp)
    npc = N * N
    base_rate = TOTAL_LOAD_BASE / (K * npc)

    label = f'K{K}_N{N}_bpp{bpp}_s{seed}'
    traf_file = f'traffic_parl_{wl}_{label}.txt'
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

    # Reference
    per_adj = budget // n_adj
    residual = budget - per_adj * n_adj
    adj_alloc = {p: per_adj + (1 if i < residual else 0)
                  for i, p in enumerate(sorted(adj_pairs))}
    adj_capped = {p: min(n, N) for p, n in adj_alloc.items()}
    cfg_adj = f'parl_{wl}_{label}_adj'
    gen_anynet_config(cfg_adj, grid, adj_capped, chip_n=N, outdir=CONFIG_DIR)
    L_adj = run_booksim(cfg_adj, traf_file, base_rate, timeout=900)['latency']

    max_dist = max(2, min(3, max(R, C) - 1))
    greedy_alloc = alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}
    cfg_g = f'parl_{wl}_{label}_greedy'
    gen_anynet_config(cfg_g, grid, greedy_capped, chip_n=N, outdir=CONFIG_DIR)
    L_g = run_booksim(cfg_g, traf_file, base_rate, timeout=900)['latency']

    print(f'Reference: L_adj={L_adj}, L_greedy={L_g}', flush=True)

    t0 = time.time()
    parl_alloc, _ = pb.train_parl_style(surrogate, wl, K, N, R, C, bpp, seed)
    parl_capped = {p: min(n, N) for p, n in parl_alloc.items()}
    cfg_parl = f'parl_{wl}_{label}'
    gen_anynet_config(cfg_parl, grid, parl_capped, chip_n=N, outdir=CONFIG_DIR)
    L_parl = run_booksim(cfg_parl, traf_file, base_rate, timeout=900)['latency']
    train_time = time.time() - t0
    print(f'    L_parl={L_parl}, train_time={train_time:.1f}s', flush=True)
    if L_adj and L_parl:
        print(f'    PARL saving vs adj = {(L_adj-L_parl)/L_adj*100:+.2f}%  '
              f'(greedy: {(L_adj-L_g)/L_adj*100:+.2f}%)', flush=True)

    # atomic append
    existing = []
    if OUT_FILE.exists():
        existing = json.load(open(OUT_FILE))
    existing = [r for r in existing if r['seed'] != seed]
    existing.append({
        'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp, 'seed': seed,
        'L_adj': L_adj, 'L_greedy': L_g, 'L_parl': L_parl,
        'L_parl_fb': min(L_g, L_parl) if (L_g and L_parl) else None,
        'train_time': train_time,
    })
    with open(OUT_FILE, 'w') as f:
        json.dump(existing, f, indent=2)


if __name__ == '__main__':
    main()
