"""Comprehensive V2 sweep: 4 workloads x 5 methods x 11 mixes (1 cell).

This is the actual V2 evaluation. For each method + workload pair we get
one BookSim latency. Then for each combination of workloads (size 2, 3,
or 4) we compute the average latency per method. The winner per mix is
the method our framework should beat.
"""

import itertools
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_perf_6panel_workload import WORKLOADS
from cost_performance_experiment import (
    gen_anynet_config, gen_traffic_matrix, run_booksim,
)
from baselines import BASELINE_REGISTRY
from ml_express_warmstart import (
    RESULTS_DIR, CONFIG_DIR, TOTAL_LOAD_BASE,
    load_rate_aware_surrogate,
)
from run_rl_multi_workload import (
    greedy_mask_per_workload,
    train_warmstart_rl_multi,
)


def run_one(label, alloc, K, N, R, C, w_name, rate_mult=4.0):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    rate = (TOTAL_LOAD_BASE / (K * npc)) * rate_mult
    capped = {p: min(n, N) for p, n in alloc.items()}
    cfg = f"v2sweep_{label}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_v2sweep_{label}_{w_name}_K{K}N{N}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    return run_booksim(cfg, traf_file, rate, timeout=600)


def main():
    K, N, R, C = 16, 4, 4, 4
    workloads = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']
    grid = ChipletGrid(R, C)
    n_adj = len(grid.get_adj_pairs())
    bpp = 2
    budget = n_adj * bpp

    surrogate = load_rate_aware_surrogate()
    print(f"Training Ours: |W|={len(workloads)} joint RL ({workloads})",
          flush=True)
    t0 = time.time()
    result = train_warmstart_rl_multi(
        surrogate, workloads, K, N, R, C, bpp,
        n_episodes=200, rate_mult=4.0,
        reward_type='normalized_avg', max_dist=3, verbose=False,
    )
    print(f"  RL done in {time.time() - t0:.1f}s, superset "
          f"{len(result['superset_alloc'])} pairs, "
          f"{sum(result['superset_alloc'].values())} links", flush=True)

    superset = result['superset_alloc']
    total_super = sum(superset.values())
    mask_budget = max(1, int(total_super * 0.7))
    masks = {}
    for w in workloads:
        traffic = WORKLOADS[w](K, grid)
        masks[w] = greedy_mask_per_workload(
            superset, traffic, grid, mask_budget, max_lpp=N)

    method_allocs = {name: fn(grid, budget, N)
                     for name, fn in BASELINE_REGISTRY.items()}

    print("\nRunning 5 methods x 4 workloads = 20 BookSim runs", flush=True)
    raw = {m: {} for m in list(method_allocs.keys()) + ['ours']}

    methods = list(method_allocs.keys()) + ['ours']
    for method in methods:
        for w in workloads:
            alloc = masks[w] if method == 'ours' else method_allocs[method]
            t0 = time.time()
            res = run_one(method, alloc, K, N, R, C, w)
            elapsed = time.time() - t0
            lat = res.get('latency')
            raw[method][w] = lat
            n_links = sum(min(n, N) for n in alloc.values())
            lat_str = f"{lat:.2f}" if lat is not None else "FAIL"
            print(f"  {method:<8} | {w:<18} | lat={lat_str:>10} | "
                  f"links={n_links:>3} | {elapsed:>5.1f}s", flush=True)

    print("\nMix-avg latency table:", flush=True)
    header = f"{'mix':<55} | " + " | ".join(f"{m:>9}" for m in methods)
    print(header, flush=True)
    print('-' * len(header), flush=True)
    mix_results = {}
    for k in [2, 3, 4]:
        for combo in itertools.combinations(workloads, k):
            mix_label = '+'.join(combo)
            row = {}
            for m in methods:
                vals = [raw[m].get(w) for w in combo]
                if any(v is None for v in vals):
                    row[m] = None
                else:
                    row[m] = sum(vals) / len(vals)
            mix_results[mix_label] = row
            cells = ' | '.join(f"{(v if v is not None else 0):>9.2f}"
                               for v in row.values())
            print(f"{mix_label:<55} | {cells}", flush=True)

    print('-' * len(header), flush=True)
    print('\nWinner per mix (lowest avg latency):', flush=True)
    win_count = {m: 0 for m in methods}
    for mix_label, row in mix_results.items():
        valid = [(m, v) for m, v in row.items() if v is not None]
        if not valid:
            continue
        winner, _ = min(valid, key=lambda x: x[1])
        win_count[winner] += 1
    for m, c in win_count.items():
        print(f"  {m:<10}: {c} / {len(mix_results)} mixes won", flush=True)

    out_path = RESULTS_DIR / 'sweep_v2_pilot.json'
    out_path.write_text(json.dumps({
        'K': K, 'N': N, 'workloads': workloads, 'budget': budget,
        'raw': raw, 'mix_results': mix_results, 'win_count': win_count,
        'superset': {f"{p[0]}-{p[1]}": v for p, v in superset.items()},
        'masks': {w: {f"{p[0]}-{p[1]}": v for p, v in m.items()}
                  for w, m in masks.items()},
    }, indent=2))
    print(f"\nSaved: {out_path}", flush=True)


if __name__ == '__main__':
    main()
