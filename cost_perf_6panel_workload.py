"""
Cost-Performance 6-Panel — multi-workload variant with K=16 expansion and
multi-seed MoE.

Key changes vs cost_perf_4panel_workload.py:
  1. Adds K=16 panels (4x4 grid) — 6 panels total per workload.
  2. MoE uses multi-seed averaging (10 seeds) to approximate dynamic routing
     instead of a single static snapshot.
  3. Non-MoE workloads reuse existing 4-panel data (K=8, K=32) when present;
     only K=16 panels are computed fresh to save time.
  4. Results saved to results/cost_perf_6panel_<WORKLOAD>/ to avoid clobbering
     the 4-panel results.

Supported workloads (same as before):
  uniform_random, hybrid_tp_pp, tensor_parallel, moe, ring_allreduce,
  tree_allreduce, pipeline_parallel
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
RESULTS_DIR = Path(__file__).parent / 'results' / f'cost_perf_6panel_{WORKLOAD}'
LEGACY_4PANEL_DIR = Path(__file__).parent / 'results' / f'cost_perf_4panel_{WORKLOAD}'

TOTAL_LOAD_BASE = 0.32
MOE_N_SEEDS = 10  # multi-seed averaging for MoE


# ---------- Workload generators ----------

def gen_uniform_random(K, grid):
    rng = np.random.RandomState(42)
    T = rng.rand(K, K) * 100
    np.fill_diagonal(T, 0)
    return (T + T.T) / 2


def gen_hybrid_tp_pp(K, grid, tp_group=8, data_size=1000.0):
    T = np.zeros((K, K))
    n_groups = max(1, K // tp_group)
    for g in range(n_groups):
        start, end = g * tp_group, min((g + 1) * tp_group, K)
        for i in range(start, end):
            for j in range(start, end):
                if i != j:
                    T[i][j] += data_size / tp_group
    for g in range(n_groups - 1):
        src = min((g + 1) * tp_group - 1, K - 1)
        dst = min((g + 1) * tp_group, K - 1)
        if src != dst:
            T[src][dst] += data_size * 0.3
            T[dst][src] += data_size * 0.3
    return T


def gen_tensor_parallel(K, grid, group_size=4, data_size=1000.0):
    T = np.zeros((K, K))
    n_groups = max(1, K // group_size)
    for g in range(n_groups):
        start, end = g * group_size, min((g + 1) * group_size, K)
        for i in range(start, end):
            for j in range(start, end):
                if i != j:
                    T[i][j] = data_size / group_size
    for g in range(n_groups - 1):
        src = min((g + 1) * group_size - 1, K - 1)
        dst = min((g + 1) * group_size, K - 1)
        if src != dst:
            T[src][dst] += data_size * 0.1
            T[dst][src] += data_size * 0.1
    return T


def gen_moe(K, grid, top_k=2, data_size=1000.0, n_seeds=MOE_N_SEEDS,
            zipf_s=1.5):
    """Skewed multi-seed MoE with Zipf expert popularity.

    Models realistic MoE dispatch where some experts are "hot" (selected
    more frequently). Expert popularity follows Zipf(s) distribution,
    matching observed skew in DeepSeek-V3 and Mixtral.
    """
    T = np.zeros((K, K))
    # Expert popularity: rank r has probability proportional to 1/r^s
    ranks = np.arange(1, K + 1, dtype=float)
    base_probs = 1.0 / ranks ** zipf_s

    for seed in range(n_seeds):
        rng = np.random.RandomState(42 + seed)
        for i in range(K):
            p = base_probs.copy()
            p[i] = 0  # cannot dispatch to self
            p /= p.sum()
            experts = rng.choice(K, size=min(top_k, K - 1), replace=False,
                                 p=p)
            for e in experts:
                T[i][e] += data_size / top_k / n_seeds
                T[e][i] += data_size / top_k / n_seeds
    return T


def gen_ring_allreduce(K, grid, data_size=1000.0):
    T = np.zeros((K, K))
    chunk = data_size / K
    for i in range(K):
        j = (i + 1) % K
        T[i][j] = chunk * (K - 1)
        T[j][i] = chunk * (K - 1)
    return T


def gen_tree_allreduce(K, grid, data_size=1000.0):
    """Recursive halving-doubling (butterfly pattern)."""
    T = np.zeros((K, K))
    levels = int(math.ceil(math.log2(K)))
    for level in range(levels):
        stride = 2 ** level
        chunk = data_size / (2 ** (level + 1))
        for i in range(K):
            partner = i ^ stride
            if partner < K and i < partner:  # avoid double-count
                T[i][partner] += chunk
                T[partner][i] += chunk
    return T


def gen_pipeline_parallel(K, grid, data_size=1000.0):
    T = np.zeros((K, K))
    for stage in range(K - 1):
        T[stage][stage + 1] = data_size
        T[stage + 1][stage] = data_size * 0.1
    return T


def gen_all_to_all(K, grid, data_size=1000.0):
    """Full all-to-all: every chiplet sends equal data to every other.

    Represents sequence parallel or context parallel redistribution,
    where all chiplets must exchange activations/KV-cache equally.
    """
    T = np.zeros((K, K))
    chunk = data_size / (K - 1)
    for i in range(K):
        for j in range(K):
            if i != j:
                T[i][j] = chunk
    return T


WORKLOADS = {
    'uniform_random':    gen_uniform_random,
    'hybrid_tp_pp':      gen_hybrid_tp_pp,
    'tensor_parallel':   gen_tensor_parallel,
    'moe':               gen_moe,
    'ring_allreduce':    gen_ring_allreduce,
    'tree_allreduce':    gen_tree_allreduce,
    'pipeline_parallel': gen_pipeline_parallel,
    'all_to_all':        gen_all_to_all,
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

    traf_file = f'traffic_cp6p_{WORKLOAD}_{panel_label}.txt'
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

            cfg_name = f'cp6p_{WORKLOAD}_{panel_label}_{strategy}_L{budget}'
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


def seed_from_legacy():
    """If non-MoE workload and legacy 4-panel data exists, pre-seed the
    6-panel JSON with K=8 and K=32 panels so we only run K=16 fresh."""
    if WORKLOAD == 'moe':
        return {}  # MoE is fully re-run with multi-seed gen
    legacy_file = LEGACY_4PANEL_DIR / 'cost_perf_4panel.json'
    if not legacy_file.exists():
        return {}
    with open(legacy_file) as f:
        legacy = json.load(f)
    print(f"### Seeded from legacy 4-panel: {list(legacy.keys())}",
          flush=True)
    return legacy


def main():
    if WORKLOAD not in WORKLOADS:
        print(f"Unknown workload: {WORKLOAD}", file=sys.stderr)
        print(f"Choose from: {list(WORKLOADS.keys())}", file=sys.stderr)
        sys.exit(1)

    print(f"### WORKLOAD = {WORKLOAD}", flush=True)
    print(f"### RESULTS_DIR = {RESULTS_DIR}", flush=True)
    if WORKLOAD == 'moe':
        print(f"### MoE multi-seed averaging: {MOE_N_SEEDS} seeds", flush=True)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    panels = [
        (2, 4,  8, 4, 'K8_N4'),
        (2, 4,  8, 8, 'K8_N8'),
        (4, 4, 16, 4, 'K16_N4'),
        (4, 4, 16, 8, 'K16_N8'),
        (4, 8, 32, 4, 'K32_N4'),
        (4, 8, 32, 8, 'K32_N8'),
    ]

    results_file = RESULTS_DIR / 'cost_perf_6panel.json'
    all_results = {}
    if results_file.exists():
        with open(results_file) as f:
            all_results = json.load(f)
        print(f"Loaded existing: {list(all_results.keys())}", flush=True)
    else:
        # Seed from legacy 4-panel for non-MoE workloads
        all_results = seed_from_legacy()
        if all_results:
            with open(results_file, 'w') as f:
                json.dump(all_results, f, indent=2)

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
