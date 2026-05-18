"""K=64 (8x8) addon for Fig 1: adj_uniform BookSim sweep.

Matches existing cost_perf_across_K.json schema: budgets 1x..4x, rate 0.005.
"""

import json
import time
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_performance_experiment import (
    gen_anynet_config, gen_traffic_matrix,
    alloc_adjacent_uniform, run_booksim,
)

CONFIG_DIR = Path(__file__).parent / 'booksim_configs'
RESULTS_DIR = Path(__file__).parent / 'results' / 'cost_perf_K'
OUT_PATH = RESULTS_DIR / 'cost_perf_K64.json'

CHIP_N = 4
R, C = 8, 8
K = R * C
RATES = [0.005]


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    grid = ChipletGrid(R, C)
    n_adj = len(grid.get_adj_pairs())
    npc = CHIP_N * CHIP_N
    max_links_per_pair = CHIP_N

    print(f'K={K} ({R}x{C}), n_adj={n_adj}, npc={npc}')

    rng = np.random.RandomState(42)
    traffic = rng.rand(K, K) * 100.0
    np.fill_diagonal(traffic, 0)
    traffic = (traffic + traffic.T) / 2

    traf_file = f'traffic_cpK_{R}x{C}_n{CHIP_N}.txt'
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

    results = {
        'K': K, 'grid': f'{R}x{C}', 'n_adj': n_adj,
        'experiments': [],
    }

    for mult in [1, 2, 3, 4]:
        budget = n_adj * mult
        t0 = time.time()
        alloc = alloc_adjacent_uniform(grid, budget)
        capped = {p: min(n, max_links_per_pair) for p, n in alloc.items()}
        total_links = sum(capped.values())

        cfg = f'cpK_{R}x{C}_n{CHIP_N}_adj_uniform_L{budget}'
        gen_anynet_config(cfg, grid, capped, chip_n=CHIP_N, outdir=CONFIG_DIR)

        rate_results = []
        for rate in RATES:
            print(f'  budget={mult}x ({budget} links) rate={rate}...', end=' ', flush=True)
            t1 = time.time()
            r = run_booksim(cfg, traf_file, rate, timeout=900)
            dt = time.time() - t1
            rate_results.append({
                'rate': rate, 'latency': r.get('latency'),
                'throughput': r.get('throughput'),
            })
            lat_str = f"lat={r['latency']:.2f}" if r.get('latency') else 'fail'
            print(f'{lat_str} ({dt:.0f}s)', flush=True)

        results['experiments'].append({
            'budget': budget, 'budget_mult': mult,
            'strategy': 'adj_uniform',
            'total_links': total_links, 'n_express': 0,
            'algo_time': time.time() - t0, 'rates': rate_results,
        })

    OUT_PATH.write_text(json.dumps(results, indent=2))
    print(f'\nSaved: {OUT_PATH}')


if __name__ == '__main__':
    main()
