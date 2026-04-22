"""
Find saturation throughput for each (workload, panel) combination.

Runs adj_uniform at max budget with progressively increasing injection rates
until throughput plateaus (accepted rate < 90% of offered rate).

Output: results/saturation_rates.json
"""

import os
import json
import time
import sys
import math
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_performance_experiment import (
    gen_anynet_config, gen_traffic_matrix,
    alloc_adjacent_uniform,
    run_booksim,
)
from cost_perf_6panel_workload import WORKLOADS

CONFIG_DIR = Path(__file__).parent / 'booksim_configs'
RESULTS_DIR = Path(__file__).parent / 'results'

TOTAL_LOAD_BASE = 0.32


def find_saturation(workload_name, R, C, K, N, panel_label):
    """Binary-search style: double rate until saturated, then bisect."""
    grid = ChipletGrid(R, C)
    adj_pairs = grid.get_adj_pairs()
    n_adj = len(adj_pairs)
    npc = N * N
    max_links_per_pair = N

    # Max budget adj_uniform
    budget = n_adj * max_links_per_pair
    alloc = alloc_adjacent_uniform(grid, budget)

    # Generate traffic
    traffic = WORKLOADS[workload_name](K, grid)
    traf_file = f'traffic_sat_{workload_name}_{panel_label}.txt'
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

    # Generate config
    cfg_name = f'sat_{workload_name}_{panel_label}'
    gen_anynet_config(cfg_name, grid, alloc, chip_n=N, outdir=CONFIG_DIR)

    base_rate = TOTAL_LOAD_BASE / (K * npc)

    # Phase 1: exponential sweep to find approximate saturation
    print(f"\n  [{panel_label}] Phase 1: exponential sweep (base={base_rate:.6f})")
    multipliers = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]
    results = []

    for mult in multipliers:
        rate = base_rate * mult
        r = run_booksim(cfg_name, traf_file, rate, timeout=120)
        lat = r['latency']
        tput = r['throughput']

        if lat is None:
            print(f"    {mult:>4d}x  rate={rate:.6f}  TIMEOUT (saturated)")
            results.append({'mult': mult, 'rate': rate, 'latency': None,
                            'throughput': None, 'saturated': True})
            break

        utilization = tput / rate if rate > 0 else 0
        saturated = utilization < 0.90
        flag = " <<< SATURATED" if saturated else ""
        print(f"    {mult:>4d}x  rate={rate:.6f}  lat={lat:.1f}  "
              f"tput={tput:.6f}  util={utilization:.3f}{flag}")

        results.append({'mult': mult, 'rate': rate, 'latency': lat,
                        'throughput': tput, 'utilization': utilization,
                        'saturated': saturated})

        if saturated:
            break

    # Find the transition point
    last_ok = None
    first_sat = None
    for r in results:
        if not r['saturated']:
            last_ok = r
        else:
            first_sat = r
            break

    if last_ok and first_sat:
        sat_rate = last_ok['rate']
        sat_mult = last_ok['mult']
        print(f"    => Saturation between {last_ok['mult']}x and {first_sat['mult']}x")
        print(f"    => Last stable: {sat_mult}x (rate={sat_rate:.6f})")
    elif last_ok:
        sat_rate = last_ok['rate']
        sat_mult = last_ok['mult']
        print(f"    => Not saturated even at {sat_mult}x")
    else:
        sat_rate = base_rate
        sat_mult = 1
        print(f"    => Saturated even at 1x!")

    return {
        'panel': panel_label,
        'workload': workload_name,
        'base_rate': base_rate,
        'saturation_mult': sat_mult,
        'saturation_rate': sat_rate,
        'sweep': results,
    }


def main():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    workloads = ['tree_allreduce', 'hybrid_tp_pp', 'moe', 'uniform_random']
    panels = [
        (4, 4, 16, 4, 'K16_N4'),
        (4, 4, 16, 8, 'K16_N8'),
        (4, 8, 32, 4, 'K32_N4'),
        (4, 8, 32, 8, 'K32_N8'),
    ]

    all_results = {}
    results_file = RESULTS_DIR / 'saturation_rates.json'

    for wl in workloads:
        print(f"\n{'='*60}")
        print(f"  Workload: {wl}")
        print(f"{'='*60}")
        all_results[wl] = {}

        for R, C, K, N, label in panels:
            result = find_saturation(wl, R, C, K, N, label)
            all_results[wl][label] = result

            # Save incrementally
            with open(results_file, 'w') as f:
                json.dump(all_results, f, indent=2)

    # Summary
    print(f"\n\n{'='*60}")
    print("  SUMMARY: Saturation multipliers")
    print(f"{'='*60}")
    print(f"{'workload':<18s} {'K16_N4':>8s} {'K16_N8':>8s} {'K32_N4':>8s} {'K32_N8':>8s}")
    for wl in workloads:
        vals = []
        for _, _, _, _, label in panels:
            m = all_results[wl][label]['saturation_mult']
            vals.append(f"{m}x")
        print(f"{wl:<18s} {vals[0]:>8s} {vals[1]:>8s} {vals[2]:>8s} {vals[3]:>8s}")

    print(f"\nSaved to {results_file}")


if __name__ == '__main__':
    main()
