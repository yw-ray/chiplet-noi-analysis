"""BookSim spot-check for V2 pilot: 5 methods x 2 workloads.

Why this exists: surrogate predicted Kite > Ours (suspected OOD). We need
real BookSim to confirm whether Kite genuinely beats us, or the surrogate
is mis-predicting on Kite-style allocations.
"""

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
from ml_express_warmstart import RESULTS_DIR, CONFIG_DIR, TOTAL_LOAD_BASE


def run_method_workload(method, alloc, K, N, R, C, w_name, rate_mult=4.0):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    base_rate = TOTAL_LOAD_BASE / (K * npc)
    rate = base_rate * rate_mult

    capped = {p: min(n, N) for p, n in alloc.items()}

    cfg = f"v2_{method}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_v2_{method}_{w_name}_K{K}N{N}.txt"

    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)

    res = run_booksim(cfg, traf_file, rate, timeout=600)
    return res


def main():
    K, N, R, C = 16, 4, 4, 4
    workload_set = ['moe', 'hybrid_tp_pp']
    grid = ChipletGrid(R, C)
    n_adj = len(grid.get_adj_pairs())
    budget = n_adj * 2

    methods = {name: fn(grid, budget, N)
               for name, fn in BASELINE_REGISTRY.items()}
    pilot = json.loads(
        (RESULTS_DIR / 'pilot_multi_workload_normalized.json').read_text())
    methods['ours_superset'] = {
        tuple(int(x) for x in k.split('-')): v
        for k, v in pilot['superset_alloc'].items()
    }

    print(f"V2 BookSim verify: K={K} N={N} W={workload_set} budget={budget}",
          flush=True)
    print(f"{'method':<14} | {'workload':<14} | {'latency':>10} | "
          f"{'tput':>8} | {'time':>6}", flush=True)
    print('-' * 72, flush=True)

    results = {}
    t_start = time.time()
    for method, alloc in methods.items():
        results[method] = {}
        for w in workload_set:
            t0 = time.time()
            res = run_method_workload(method, alloc, K, N, R, C, w)
            elapsed = time.time() - t0
            lat = res.get('latency')
            tput = res.get('throughput')
            lat_str = f"{lat:.2f}" if lat is not None else "FAIL"
            tput_str = f"{tput:.3f}" if tput is not None else "—"
            print(f"{method:<14} | {w:<14} | {lat_str:>10} | "
                  f"{tput_str:>8} | {elapsed:>5.1f}s", flush=True)
            results[method][w] = {
                'latency': lat,
                'throughput': tput,
                'elapsed': elapsed,
                'success': res.get('success', False),
            }
    print(f"\nTotal: {time.time() - t_start:.1f}s", flush=True)

    out_path = RESULTS_DIR / 'booksim_verify_pilot.json'
    out_path.write_text(json.dumps({
        'K': K, 'N': N, 'workload_set': workload_set, 'budget': budget,
        'rate_mult': 4.0,
        'results': results,
    }, indent=2))
    print(f"Saved: {out_path}", flush=True)


if __name__ == '__main__':
    main()
