"""
Cost-Performance 4-Panel Experiment
=====================================

Four panels: (K=8, N=4), (K=8, N=8), (K=32, N=4), (K=32, N=8)

Rate normalization: rate * K * N^2 = 0.32 (constant total network load,
matching Fig 3's displayed baseline: 0.005 * 16 * 4 = 0.32 pkt/cycle).

Base rates (multiplier=1.0):
- K=8,  N=4: rate = 0.0025
- K=8,  N=8: rate = 0.000625
- K=32, N=4: rate = 0.000625
- K=32, N=8: rate = 0.00015625

Sweep multipliers: (1.0, 2.0, 3.0, 4.0) -- matches Fig 3's [0.005..0.02].

Resumable: saves after each panel, skips completed panels on re-run.

Goal: show that cost-saving (express vs adjacent) grows with K.
"""

import json
import time
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_performance_experiment import (
    gen_anynet_config, gen_traffic_matrix,
    alloc_adjacent_uniform, alloc_express_greedy,
    run_booksim,
)

CONFIG_DIR = Path(__file__).parent / 'booksim_configs'
RESULTS_DIR = Path(__file__).parent / 'results' / 'cost_perf_4panel'

# Fix total load: rate * K * N^2 = 0.32
# (Fig 3's displayed rate: 0.005 * 16 * 4 = 0.32 for K=16/N=2; also
#  0.00125 * 16 * 16 for K=16/N=4 and 0.0003125 * 16 * 64 for K=16/N=8)
TOTAL_LOAD_BASE = 0.32


def run_panel(R, C, K, N, panel_label, rate_multipliers=(1.0, 2.0, 3.0, 4.0)):
    """Run one (K, N) panel with full budget sweep."""
    grid = ChipletGrid(R, C)
    adj_pairs = grid.get_adj_pairs()
    n_adj = len(adj_pairs)
    npc = N * N
    max_links_per_pair = N

    base_rate = TOTAL_LOAD_BASE / (K * npc)
    rates = [base_rate * m for m in rate_multipliers]

    # Traffic matrix (uniform random, fixed seed for reproducibility)
    rng = np.random.RandomState(42)
    traffic = rng.rand(K, K) * 100
    np.fill_diagonal(traffic, 0)
    traffic = (traffic + traffic.T) / 2

    traf_file = f'traffic_cp4p_{panel_label}.txt'
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

    # Budget sweep: 1x ... N x n_adj (matches border capacity)
    budget_list = [n_adj * b for b in range(1, max_links_per_pair + 1)]

    print(f"\n{'='*60}", flush=True)
    print(f"  Panel: {panel_label}  K={K} ({R}x{C}), N={N} (npc={npc})",
          flush=True)
    print(f"  Total nodes: {K*npc}, base_rate: {base_rate:.6f}", flush=True)
    print(f"  n_adj={n_adj}, budgets={budget_list}", flush=True)
    print(f"  rates={[f'{r:.6f}' for r in rates]}", flush=True)
    print(f"{'='*60}", flush=True)

    panel_results = {'K': K, 'N': N, 'grid': f'{R}x{C}', 'n_adj': n_adj,
                     'total_nodes': K * npc, 'base_rate': base_rate,
                     'rates': rates, 'experiments': []}

    for budget in budget_list:
        bpp = budget / n_adj
        print(f"\n  --- Budget: {budget} links ({bpp:.0f}x per adj) ---",
              flush=True)

        for strategy in ['adj_uniform', 'express_greedy']:
            t0 = time.time()
            print(f"    {strategy}...", end=' ', flush=True)

            if strategy == 'adj_uniform':
                alloc = alloc_adjacent_uniform(grid, budget)
            else:
                max_dist = min(3, max(R, C) - 1)
                if max_dist < 2:
                    max_dist = 2
                alloc = alloc_express_greedy(grid, traffic, budget,
                                             max_dist=max_dist)

            capped = {p: min(n, max_links_per_pair) for p, n in alloc.items()}
            actual = sum(capped.values())
            n_expr = sum(1 for p in capped if p not in set(adj_pairs))

            cfg_name = f'cp4p_{panel_label}_{strategy}_L{budget}'
            gen_anynet_config(cfg_name, grid, capped, chip_n=N,
                              outdir=CONFIG_DIR)

            rate_results = []
            for rate in rates:
                r = run_booksim(cfg_name, traf_file, rate, timeout=900)
                rate_results.append({
                    'rate': rate,
                    'latency': r['latency'],
                    'throughput': r['throughput'],
                })
                lat_str = f"{r['latency']:.1f}" if r['latency'] else "FAIL"
                print(f"r={rate:.4f}:{lat_str}", end=' ', flush=True)

            t_total = time.time() - t0
            print(f"[{n_expr}expr, {actual}total, {t_total:.0f}s]",
                  flush=True)

            panel_results['experiments'].append({
                'budget': budget,
                'budget_per_pair': float(bpp),
                'strategy': strategy,
                'total_links': actual,
                'n_express': n_expr,
                'rates': rate_results,
                'run_time': t_total,
            })

    return panel_results


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    panels = [
        # (R, C, K, N, label) -- fastest first
        (2, 4, 8, 4, 'K8_N4'),
        (2, 4, 8, 8, 'K8_N8'),
        (4, 8, 32, 4, 'K32_N4'),
        (4, 8, 32, 8, 'K32_N8'),  # slowest, overnight
    ]

    results_file = RESULTS_DIR / 'cost_perf_4panel.json'
    all_results = {}
    if results_file.exists():
        with open(results_file) as f:
            all_results = json.load(f)
        print(f"Loaded existing results: {list(all_results.keys())}",
              flush=True)

    for R, C, K, N, label in panels:
        if label in all_results:
            print(f"\n  [SKIP] {label} already done", flush=True)
            continue
        t_panel = time.time()
        all_results[label] = run_panel(R, C, K, N, label)
        with open(results_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        elapsed = (time.time() - t_panel) / 60
        print(f"\n  [DONE] {label} in {elapsed:.1f} min", flush=True)

    print(f"\nAll 4 panels complete. Results: {results_file}", flush=True)


if __name__ == '__main__':
    main()
