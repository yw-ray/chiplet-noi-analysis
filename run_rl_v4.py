"""RL v4: multi-warm-start + top-k candidates + entropy bonus + longer training.

For each cell:
  1) Compute greedy and FBfly warm-start allocations.
  2) Run RL 5 seeds × greedy-warm-start, 5 seeds × FBfly-warm-start = 10 seeds.
  3) Each RL run returns top-3 candidates by surrogate score (500 episodes, entropy 0.01).
  4) Total 10 × 3 = 30 candidate placements.
  5) BookSim measure all 30 + 3 baselines (adj/greedy/fbfly) at 4 rates each.
  6) Pick best candidate by max-across-rates latency.
  7) Save as 'ours_v4'.

Usage: .venv/bin/python3 run_rl_v4.py <workload> <K> <N> <bpp>
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
OUT_FILE = RESULTS_DIR / 'rl_v4.json'

RATE_WEIGHTS = {1.0: 1.0, 2.0: 1.0, 3.0: 1.0, 4.0: 2.0}
SEEDS_GREEDY = [42, 43, 44, 45, 46]
SEEDS_FBFLY = [47, 48, 49, 50, 51]
TOP_K = 3
N_EPISODES = 500
ENTROPY_COEF = 0.01


def main():
    wl = sys.argv[1]
    K = int(sys.argv[2])
    N = int(sys.argv[3])
    bpp = int(sys.argv[4])

    print(f'>>> {wl} K{K}N{N} b{bpp}x (RL v4: 10-seed multi-warm + top-{TOP_K})', flush=True)
    t0 = time.time()

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
    traf_file = f'traffic_v4_{wl}_{label}.txt'
    mw.gen_traffic_matrix(grid, traffic, npc, mw.CONFIG_DIR / traf_file)

    # --- baselines ---
    per_adj = budget // n_adj
    residual = budget - per_adj * n_adj
    adj_alloc = {p: per_adj + (1 if i < residual else 0)
                 for i, p in enumerate(sorted(adj_pairs))}
    adj_capped = {p: min(n, N) for p, n in adj_alloc.items()}
    cfg_adj = f'v4_{wl}_{label}_adj'
    mw.gen_anynet_config(cfg_adj, grid, adj_capped, chip_n=N, outdir=mw.CONFIG_DIR)

    max_dist = max(2, min(3, max(R, C) - 1))
    greedy_alloc = mw.alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}
    cfg_g = f'v4_{wl}_{label}_greedy'
    mw.gen_anynet_config(cfg_g, grid, greedy_capped, chip_n=N, outdir=mw.CONFIG_DIR)

    fb_alloc = flattened_butterfly_alloc(grid, budget, per_pair_cap=N, max_dist=max_dist)
    fb_capped = {p: min(n, N) for p, n in fb_alloc.items()}
    cfg_fb = f'v4_{wl}_{label}_fbfly'
    mw.gen_anynet_config(cfg_fb, grid, fb_capped, chip_n=N, outdir=mw.CONFIG_DIR)

    # --- 10 seeds × top-K candidates ---
    surrogate_ra = mw.load_rate_aware_surrogate()
    candidates = []  # list of (tag, alloc_dict, cfg_name)

    for warm_name, warm_alloc, seeds in [
            ('greedy', greedy_capped, SEEDS_GREEDY),
            ('fbfly', fb_capped, SEEDS_FBFLY)]:
        for seed in seeds:
            torch.manual_seed(seed); np.random.seed(seed)
            top_k_results = mw.train_warmstart_rl_ra(
                surrogate_ra, wl, K, N, R, C, bpp,
                n_episodes=N_EPISODES, rate_mult=4.0,
                rate_weights=RATE_WEIGHTS,
                warm_start_alloc=warm_alloc,
                entropy_coef=ENTROPY_COEF,
                top_k=TOP_K)
            for k_idx, (alloc, pred, _) in enumerate(top_k_results):
                rl_capped = {p: min(n, N) for p, n in alloc.items()}
                cfg = f'v4_{wl}_{label}_{warm_name}_s{seed}_k{k_idx}'
                mw.gen_anynet_config(cfg, grid, rl_capped, chip_n=N, outdir=mw.CONFIG_DIR)
                candidates.append((f'{warm_name}_s{seed}_k{k_idx}', rl_capped, cfg))

    print(f'    Generated {len(candidates)} candidates + 3 baselines', flush=True)

    # --- BookSim measure all methods + candidates at 4 rates ---
    result = {
        'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp,
        'rates': rates,
        'config': {
            'seeds_greedy': SEEDS_GREEDY, 'seeds_fbfly': SEEDS_FBFLY,
            'top_k': TOP_K, 'n_episodes': N_EPISODES,
            'entropy_coef': ENTROPY_COEF, 'rate_weights': RATE_WEIGHTS,
        },
        'adj_uniform': {'latency': [], 'throughput': []},
        'greedy': {'latency': [], 'throughput': []},
        'fbfly': {'latency': [], 'throughput': []},
        'candidates': {},  # tag -> {'latency': [...], 'throughput': [...]}
    }
    for method, cfg in [('adj_uniform', cfg_adj), ('greedy', cfg_g), ('fbfly', cfg_fb)]:
        for rate in rates:
            r = mw.run_booksim(cfg, traf_file, rate, timeout=900)
            result[method]['latency'].append(r['latency'])
            result[method]['throughput'].append(r['throughput'])
        print(f'    {method}: max={max(result[method]["latency"]):.1f}', flush=True)

    for tag, alloc, cfg in candidates:
        lats, tps = [], []
        for rate in rates:
            r = mw.run_booksim(cfg, traf_file, rate, timeout=900)
            lats.append(r['latency']); tps.append(r['throughput'])
        result['candidates'][tag] = {'latency': lats, 'throughput': tps}

    # --- Pick best candidate by lowest max-across-rates ---
    best_tag = min(result['candidates'].keys(),
                    key=lambda t: max(result['candidates'][t]['latency']))
    best = result['candidates'][best_tag]
    result['ours_v4'] = {
        'latency': best['latency'],
        'throughput': best['throughput'],
        'best_candidate': best_tag,
    }
    dt = time.time() - t0
    print(f'    ours_v4: best={best_tag}, max_lat={max(best["latency"]):.1f}, elapsed={dt:.0f}s', flush=True)

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
