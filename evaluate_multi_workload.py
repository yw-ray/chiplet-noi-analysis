"""Evaluate any topology allocation against a multi-workload set.

Used by both V2 baselines (Mesh, Kite, GIA) and our framework. The same
surrogate-predicted latency function powers both, so comparisons are
apples-to-apples.

Run as a script: pilot comparison of 4 static baselines vs Ours
on K=16, N=4, W={moe, hybrid_tp_pp}, budget=2x.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_perf_6panel_workload import WORKLOADS
from ml_express_warmstart import (
    RESULTS_DIR, load_rate_aware_surrogate, surrogate_predict_ra,
)


def evaluate_alloc(alloc, K, N, R, C, workload_set, surrogate, rate_mult=4.0):
    """Predict latency of a fixed allocation under each workload in the set.

    alloc: dict {(i,j): n_links} or empty for mesh
    """
    grid = ChipletGrid(R, C)
    n_pairs = K * (K - 1) // 2
    all_pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}
    adj_set = set(grid.get_adj_pairs())
    n_adj = len(grid.get_adj_pairs())
    budget = sum(alloc.values()) if alloc else 0

    alloc_vec = np.zeros(n_pairs, dtype=np.float32)
    for p, n in alloc.items():
        if p in pair_to_idx:
            alloc_vec[pair_to_idx[p]] = n

    latencies = []
    for w_name in workload_set:
        traffic = WORKLOADS[w_name](K, grid)
        t_max = traffic.max()
        traffic_norm = traffic / t_max if t_max > 0 else traffic
        traffic_flat = traffic_norm[np.triu_indices(K, k=1)]
        lat = surrogate_predict_ra(
            surrogate, traffic_flat, alloc_vec,
            adj_set, all_pairs, K, N, max(budget, 1), n_adj,
            rate_mult=rate_mult,
        )
        latencies.append(lat)

    return {
        'workload_set': list(workload_set),
        'latencies': latencies,
        'avg': float(np.mean(latencies)),
        'worst': float(np.max(latencies)),
        'budget': budget,
    }


def main():
    from baselines import BASELINE_REGISTRY

    surrogate = load_rate_aware_surrogate()

    K, N, R, C = 16, 4, 4, 4
    workload_set = ['moe', 'hybrid_tp_pp']
    grid = ChipletGrid(R, C)
    n_adj = len(grid.get_adj_pairs())
    budget = n_adj * 2  # 2x adj budget

    print(f"\nEval: K={K} N={N} W={workload_set} budget={budget} (2x adj)")
    print(f"{'method':<12} | {'MoE':>9} | {'Hybrid':>9} | "
          f"{'avg':>8} | {'worst':>8} | {'links':>5}")
    print('-' * 72)

    results = {}
    for name, fn in BASELINE_REGISTRY.items():
        alloc = fn(grid, budget, N)
        res = evaluate_alloc(alloc, K, N, R, C, workload_set, surrogate)
        results[name] = res
        moe, hyb = res['latencies']
        print(f"{name:<12} | {moe:>9.1f} | {hyb:>9.1f} | "
              f"{res['avg']:>8.1f} | {res['worst']:>8.1f} | "
              f"{res['budget']:>5d}")

    pilot_path = RESULTS_DIR / 'pilot_multi_workload_normalized.json'
    pilot = json.loads(pilot_path.read_text())
    ours_alloc = {tuple(int(x) for x in k.split('-')): v
                  for k, v in pilot['superset_alloc'].items()}
    res = evaluate_alloc(ours_alloc, K, N, R, C, workload_set, surrogate)
    results['ours_superset'] = res
    moe, hyb = res['latencies']
    print(f"{'ours_superset':<12} | {moe:>9.1f} | {hyb:>9.1f} | "
          f"{res['avg']:>8.1f} | {res['worst']:>8.1f} | "
          f"{res['budget']:>5d}")

    out = {
        'K': K, 'N': N, 'workload_set': workload_set, 'budget': budget,
        'results': results,
    }
    out_path = RESULTS_DIR / 'baseline_compare_pilot.json'
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved: {out_path}")


if __name__ == '__main__':
    main()
