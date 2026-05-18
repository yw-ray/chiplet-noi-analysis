"""Extended-budget experiment: 5x, 6x with relaxed PHY cap (6 lanes/pair).
Tests whether phantom load can be overcome beyond standard PHY cap (4).
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
OUT_PATH = RESULTS_DIR / 'cost_perf_K_extbudget.json'

CHIP_N = 4
RELAXED_CAP = 6  # PHY relaxed cap for this thought experiment
K_GRIDS = [(4, 2, 2), (8, 2, 4), (16, 4, 4), (32, 4, 8), (64, 8, 8)]
EXTRA_MULTS = [5, 6]
RATES = [0.003, 0.005]
N_PARALLEL = 4


def setup_grid(K, R, C):
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
    for mult in EXTRA_MULTS:
        budget = n_adj * mult
        alloc = alloc_adjacent_uniform(grid, budget)
        capped = {p: min(n, RELAXED_CAP) for p, n in alloc.items()}
        cfg = f'cpK_{R}x{C}_n{CHIP_N}_adj_uniform_L{budget}_cap{RELAXED_CAP}'
        gen_anynet_config(cfg, grid, capped, chip_n=CHIP_N, outdir=CONFIG_DIR)
        cfgs[mult] = (cfg, traf_file, sum(capped.values()))
    return cfgs


def run_one(args):
    K, mult, rate, cfg, traf = args
    t0 = time.time()
    r = run_booksim(cfg, traf, rate, timeout=900)
    return (K, mult, rate, r.get('latency'), r.get('throughput'),
            time.time() - t0)


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.exists():
        existing = json.loads(OUT_PATH.read_text())
        print(f'Resuming with {len(existing)} entries')
    else:
        existing = {}

    cfgs_by_K = {}
    jobs = []
    for K, R, C in K_GRIDS:
        cfgs = setup_grid(K, R, C)
        cfgs_by_K[K] = cfgs
        for mult in EXTRA_MULTS:
            cfg, traf, total_links = cfgs[mult]
            for rate in RATES:
                key = f'K{K}|m{mult}|r{rate:.4f}'
                if key in existing:
                    continue
                jobs.append((K, mult, rate, cfg, traf))
        print(f'K={K} ({R}x{C}): 5x={cfgs[5][2]}, 6x={cfgs[6][2]} links',
              flush=True)

    print(f'\nTotal new BookSim runs: {len(jobs)} (cap={RELAXED_CAP})\n',
          flush=True)
    if not jobs:
        return

    t0 = time.time()
    with mp.Pool(N_PARALLEL) as pool:
        for i, (K, mult, rate, lat, thr, dt) in enumerate(
                pool.imap_unordered(run_one, jobs)):
            key = f'K{K}|m{mult}|r{rate:.4f}'
            existing[key] = {
                'K': K, 'budget_mult': mult, 'rate': rate,
                'phy_cap': RELAXED_CAP,
                'latency': lat, 'throughput': thr,
            }
            lat_s = f'{lat:.1f}' if lat else 'fail'
            eta = (time.time() - t0) / (i + 1) * (len(jobs) - i - 1) / 60
            print(f'  [{i+1:2d}/{len(jobs)}] K={K} m={mult}x r={rate}: '
                  f'lat={lat_s} thr={thr} ({dt:.0f}s) ETA={eta:.1f}m',
                  flush=True)
            if i % 3 == 0 or i == len(jobs) - 1:
                OUT_PATH.write_text(json.dumps(existing, indent=2))

    OUT_PATH.write_text(json.dumps(existing, indent=2))
    print(f'\nDone in {(time.time()-t0)/60:.1f}m. Saved: {OUT_PATH}')


if __name__ == '__main__':
    main()
