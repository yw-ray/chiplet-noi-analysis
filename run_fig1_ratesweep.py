"""Rate sweep for Fig 1 fair comparison.

Run BookSim across K x budget x rate to enable:
- Option A: latency speedup at fixed LOW rate (all K non-saturated)
- Option B: saturation-rate speedup (max rate sustaining >=90% accept)

Reuses existing rate=0.005,0.01,0.015 data from cost_perf_across_K.json + K64 addon.
Adds rate=0.001, 0.002, 0.003 (low end) and 0.008, 0.012 (high end) per (K, budget).
"""

import json
import sys
import time
import multiprocessing as mp
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
OUT_PATH = RESULTS_DIR / 'cost_perf_K_ratesweep.json'

CHIP_N = 4
K_GRIDS = [(4, 2, 2), (8, 2, 4), (16, 4, 4), (32, 4, 8), (64, 8, 8)]
TARGET_RATES = [0.001, 0.002, 0.003, 0.005, 0.008, 0.012]
N_PARALLEL = 4  # share resources with v3 sweep + K=64 done


def setup_grid(K, R, C):
    """Create grid + traffic file + capped allocs for budgets 1..4x."""
    grid = ChipletGrid(R, C)
    n_adj = len(grid.get_adj_pairs())
    npc = CHIP_N * CHIP_N
    rng = np.random.RandomState(42)
    traffic = rng.rand(K, K) * 100.0
    np.fill_diagonal(traffic, 0)
    traffic = (traffic + traffic.T) / 2
    traf_file = f'traffic_cpK_{R}x{C}_n{CHIP_N}.txt'
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    cfgs = {}
    for mult in [1, 2, 3, 4]:
        budget = n_adj * mult
        alloc = alloc_adjacent_uniform(grid, budget)
        capped = {p: min(n, CHIP_N) for p, n in alloc.items()}
        cfg = f'cpK_{R}x{C}_n{CHIP_N}_adj_uniform_L{budget}'
        gen_anynet_config(cfg, grid, capped, chip_n=CHIP_N, outdir=CONFIG_DIR)
        cfgs[mult] = (cfg, traf_file)
    return cfgs, n_adj


def run_one(args):
    K, mult, rate, cfg, traf = args
    t0 = time.time()
    r = run_booksim(cfg, traf, rate, timeout=900)
    dt = time.time() - t0
    return (K, mult, rate, r.get('latency'), r.get('throughput'), dt)


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.exists():
        existing = json.loads(OUT_PATH.read_text())
        print(f'Resuming with {len(existing)} existing entries')
    else:
        existing = {}

    # Build job list
    jobs = []
    cfgs_by_K = {}
    for K, R, C in K_GRIDS:
        print(f'Setting up K={K} ({R}x{C})...', flush=True)
        cfgs, n_adj = setup_grid(K, R, C)
        cfgs_by_K[K] = cfgs
        for mult in [1, 2, 3, 4]:
            cfg, traf = cfgs[mult]
            for rate in TARGET_RATES:
                key = f'K{K}|m{mult}|r{rate:.4f}'
                if key in existing:
                    continue
                jobs.append((K, mult, rate, cfg, traf))

    print(f'\nTotal new BookSim runs: {len(jobs)}', flush=True)
    if not jobs:
        print('All data already collected.')
        return

    t0 = time.time()
    with mp.Pool(N_PARALLEL) as pool:
        for i, (K, mult, rate, lat, thr, dt) in enumerate(
                pool.imap_unordered(run_one, jobs)):
            key = f'K{K}|m{mult}|r{rate:.4f}'
            existing[key] = {
                'K': K, 'budget_mult': mult, 'rate': rate,
                'latency': lat, 'throughput': thr,
            }
            elapsed = time.time() - t0
            eta_min = (elapsed / (i + 1)) * (len(jobs) - i - 1) / 60
            lat_s = f'{lat:.1f}' if lat else 'fail'
            print(f'  [{i+1:3d}/{len(jobs)}] K={K} m={mult}x r={rate:.4f}: '
                  f'lat={lat_s} thr={thr} ({dt:.0f}s) ETA={eta_min:.0f}m',
                  flush=True)
            if i % 5 == 0 or i == len(jobs) - 1:
                OUT_PATH.write_text(json.dumps(existing, indent=2))

    OUT_PATH.write_text(json.dumps(existing, indent=2))
    print(f'\nDone in {(time.time()-t0)/60:.1f}m. Saved: {OUT_PATH}')


if __name__ == '__main__':
    main()
