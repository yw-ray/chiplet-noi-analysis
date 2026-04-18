"""
Cost-Performance 4-Panel — multi-workload variant.

Reads WORKLOAD env var to choose traffic pattern. Saves to
results/cost_perf_4panel_<WORKLOAD>/ for parallel runs.

Supported workloads:
  uniform_random    — rng.rand (same as original cost_perf_4panel.py)
  hybrid_tp_pp      — Tensor parallel within group + pipeline between groups
  tensor_parallel   — Group all-to-all (group_size=4)
  moe               — Sparse expert dispatch (top_k=2)
  ring_allreduce    — Ring topology
  tree_allreduce    — Recursive halving-doubling
  pipeline_parallel — Sequential stage-to-stage
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
    alloc_adjacent_uniform, alloc_express_greedy,
    run_booksim,
)

WORKLOAD = os.environ.get('WORKLOAD', 'uniform_random')

CONFIG_DIR = Path(__file__).parent / 'booksim_configs'
RESULTS_DIR = Path(__file__).parent / 'results' / f'cost_perf_4panel_{WORKLOAD}'

TOTAL_LOAD_BASE = 0.32


# ---------- Workload generators ----------

def gen_uniform_random(K, grid):
    rng = np.random.RandomState(42)
    T = rng.rand(K, K) * 100
    np.fill_diagonal(T, 0)
    return (T + T.T) / 2


def gen_hybrid_tp_pp(K, grid, tp_group=4, data_size=1000.0):
    """TP within groups + PP between groups."""
    T = np.zeros((K, K))
    n_groups = max(1, K // tp_group)
    # TP: all-to-all within each group
    for g in range(n_groups):
        start, end = g * tp_group, min((g + 1) * tp_group, K)
        for i in range(start, end):
            for j in range(start, end):
                if i != j:
                    T[i][j] += data_size / tp_group
    # PP: between adjacent groups
    for g in range(n_groups - 1):
        src = min((g + 1) * tp_group - 1, K - 1)
        dst = min((g + 1) * tp_group, K - 1)
        if src != dst:
            T[src][dst] += data_size * 0.3
            T[dst][src] += data_size * 0.3
    return T


def gen_tensor_parallel(K, grid, group_size=4, data_size=1000.0):
    """Group all-to-all."""
    T = np.zeros((K, K))
    n_groups = max(1, K // group_size)
    for g in range(n_groups):
        start, end = g * group_size, min((g + 1) * group_size, K)
        for i in range(start, end):
            for j in range(start, end):
                if i != j:
                    T[i][j] = data_size / group_size
    # Small inter-group bridging
    for g in range(n_groups - 1):
        src = min((g + 1) * group_size - 1, K - 1)
        dst = min((g + 1) * group_size, K - 1)
        if src != dst:
            T[src][dst] += data_size * 0.1
            T[dst][src] += data_size * 0.1
    return T


def gen_moe(K, grid, top_k=2, data_size=1000.0):
    """Sparse all-to-all: each chiplet sends to top_k random experts."""
    rng = np.random.RandomState(42)
    T = np.zeros((K, K))
    for i in range(K):
        experts = rng.choice([j for j in range(K) if j != i],
                             size=min(top_k, K - 1), replace=False)
        for e in experts:
            T[i][e] = data_size / top_k
            T[e][i] = data_size / top_k
    return T


def gen_ring_allreduce(K, grid, data_size=1000.0):
    """Each chiplet sends to next neighbor in a ring."""
    T = np.zeros((K, K))
    chunk = data_size / K
    for i in range(K):
        j = (i + 1) % K
        T[i][j] = chunk * (K - 1)
        T[j][i] = chunk * (K - 1)
    return T


def gen_tree_allreduce(K, grid, data_size=1000.0):
    """Recursive halving-doubling."""
    T = np.zeros((K, K))
    levels = int(math.ceil(math.log2(K)))
    for level in range(levels):
        stride = 2 ** level
        chunk = data_size / (2 ** (level + 1))
        for i in range(K):
            partner = i ^ stride
            if partner < K:
                T[i][partner] += chunk
                T[partner][i] += chunk
    return T


def gen_pipeline_parallel(K, grid, data_size=1000.0):
    """Sequential stage-to-stage."""
    T = np.zeros((K, K))
    for stage in range(K - 1):
        T[stage][stage + 1] = data_size
        T[stage + 1][stage] = data_size * 0.1  # gradients
    return T


WORKLOADS = {
    'uniform_random':    gen_uniform_random,
    'hybrid_tp_pp':      gen_hybrid_tp_pp,
    'tensor_parallel':   gen_tensor_parallel,
    'moe':               gen_moe,
    'ring_allreduce':    gen_ring_allreduce,
    'tree_allreduce':    gen_tree_allreduce,
    'pipeline_parallel': gen_pipeline_parallel,
}


# ---------- Experiment driver ----------

def run_panel(R, C, K, N, panel_label, rate_multipliers=(1.0, 2.0, 3.0, 4.0)):
    grid = ChipletGrid(R, C)
    adj_pairs = grid.get_adj_pairs()
    n_adj = len(adj_pairs)
    npc = N * N
    max_links_per_pair = N

    base_rate = TOTAL_LOAD_BASE / (K * npc)
    rates = [base_rate * m for m in rate_multipliers]

    traffic = WORKLOADS[WORKLOAD](K, grid)

    traf_file = f'traffic_cp4p_{WORKLOAD}_{panel_label}.txt'
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

    budget_list = [n_adj * b for b in range(1, max_links_per_pair + 1)]

    print(f"\n{'='*60}", flush=True)
    print(f"  [{WORKLOAD}] Panel: {panel_label}  K={K} ({R}x{C}), N={N}",
          flush=True)
    print(f"  Total nodes: {K*npc}, base_rate: {base_rate:.6f}", flush=True)
    print(f"  n_adj={n_adj}, budgets={budget_list}", flush=True)
    print(f"  rates={[f'{r:.6f}' for r in rates]}", flush=True)
    print(f"{'='*60}", flush=True)

    panel_results = {'K': K, 'N': N, 'grid': f'{R}x{C}', 'n_adj': n_adj,
                     'total_nodes': K * npc, 'base_rate': base_rate,
                     'rates': rates, 'workload': WORKLOAD,
                     'experiments': []}

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

            cfg_name = f'cp4p_{WORKLOAD}_{panel_label}_{strategy}_L{budget}'
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
    if WORKLOAD not in WORKLOADS:
        print(f"Unknown workload: {WORKLOAD}", file=sys.stderr)
        print(f"Choose from: {list(WORKLOADS.keys())}", file=sys.stderr)
        sys.exit(1)

    print(f"### WORKLOAD = {WORKLOAD}", flush=True)
    print(f"### RESULTS_DIR = {RESULTS_DIR}", flush=True)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    panels = [
        (2, 4, 8, 4, 'K8_N4'),
        (2, 4, 8, 8, 'K8_N8'),
        (4, 8, 32, 4, 'K32_N4'),
        (4, 8, 32, 8, 'K32_N8'),
    ]

    results_file = RESULTS_DIR / 'cost_perf_4panel.json'
    all_results = {}
    if results_file.exists():
        with open(results_file) as f:
            all_results = json.load(f)
        print(f"Loaded existing: {list(all_results.keys())}", flush=True)

    for R, C, K, N, label in panels:
        if label in all_results:
            print(f"\n  [SKIP] {label} done", flush=True)
            continue
        t_panel = time.time()
        all_results[label] = run_panel(R, C, K, N, label)
        with open(results_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"\n  [DONE] {label} in {(time.time()-t_panel)/60:.1f} min",
              flush=True)

    print(f"\nAll panels done for workload={WORKLOAD}: {results_file}",
          flush=True)


if __name__ == '__main__':
    main()
