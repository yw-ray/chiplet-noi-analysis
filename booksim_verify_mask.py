"""Stage 2 BookSim verify: per-workload masks (the real V2 evaluation).

Loads superset + per-workload masks from the pilot, runs BookSim on each
mask + the corresponding workload's traffic, and reports the avg/worst.
This is the head-to-head versus Kite-L (54.3 BookSim avg).
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
from ml_express_warmstart import RESULTS_DIR, CONFIG_DIR, TOTAL_LOAD_BASE


def parse_pair_str(s):
    a, b = s.split('-')
    return (int(a), int(b))


def run_one(label, alloc, K, N, R, C, w_name, rate_mult=4.0):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    rate = (TOTAL_LOAD_BASE / (K * npc)) * rate_mult

    capped = {p: min(n, N) for p, n in alloc.items()}

    cfg = f"v2mask_{label}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_v2mask_{label}_{w_name}_K{K}N{N}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    return run_booksim(cfg, traf_file, rate, timeout=600)


def main():
    K, N, R, C = 16, 4, 4, 4

    pilot = json.loads(
        (RESULTS_DIR / 'pilot_multi_workload_normalized.json').read_text())
    workload_set = pilot['workload_set']
    superset = {parse_pair_str(k): v
                for k, v in pilot['superset_alloc'].items()}

    # Re-derive masks with adj-preserving greedy_mask_per_workload.
    from run_rl_multi_workload import greedy_mask_per_workload
    grid = ChipletGrid(R, C)
    total_super = sum(superset.values())
    mask_budget = max(1, int(total_super * 0.7))
    masks = {}
    for w in workload_set:
        traffic = WORKLOADS[w](K, grid)
        masks[w] = greedy_mask_per_workload(
            superset, traffic, grid, mask_budget, max_lpp=N)
        n_active = sum(masks[w].values())
        print(f"  re-derived mask_{w}: {len(masks[w])} pairs, "
              f"{n_active} links (budget {mask_budget})", flush=True)

    print(f"Stage 2 BookSim verify: K={K} N={N} W={workload_set}", flush=True)
    print(f"Superset: {len(superset)} pairs, {sum(superset.values())} links",
          flush=True)
    print(f"{'config':<28} | {'workload':<14} | {'latency':>10} | "
          f"{'tput':>8} | {'links':>6}", flush=True)
    print('-' * 80, flush=True)

    results = {}
    t_start = time.time()

    res = run_one('superset_raw', superset, K, N, R, C, workload_set[0])
    print(f"{'superset_raw':<28} | {workload_set[0]:<14} | "
          f"{(res.get('latency') or 0):>10.2f} | "
          f"{(res.get('throughput') or 0):>8.3f} | "
          f"{sum(superset.values()):>6}", flush=True)
    results['superset_raw_' + workload_set[0]] = res
    res = run_one('superset_raw', superset, K, N, R, C, workload_set[1])
    print(f"{'superset_raw':<28} | {workload_set[1]:<14} | "
          f"{(res.get('latency') or 0):>10.2f} | "
          f"{(res.get('throughput') or 0):>8.3f} | "
          f"{sum(superset.values()):>6}", flush=True)
    results['superset_raw_' + workload_set[1]] = res

    print('-' * 80, flush=True)

    mask_lats = []
    for w in workload_set:
        m = masks[w]
        res = run_one(f'mask_{w}', m, K, N, R, C, w)
        lat = res.get('latency')
        results[f'mask_{w}'] = res
        mask_lats.append(lat)
        print(f"{'ours_mask_' + w:<28} | {w:<14} | "
              f"{(lat or 0):>10.2f} | "
              f"{(res.get('throughput') or 0):>8.3f} | "
              f"{sum(m.values()):>6}", flush=True)

    print('-' * 80, flush=True)
    if all(x is not None for x in mask_lats):
        avg = sum(mask_lats) / len(mask_lats)
        worst = max(mask_lats)
        print(f"\n  Stage 2 avg latency = {avg:.2f}", flush=True)
        print(f"  Stage 2 worst       = {worst:.2f}", flush=True)
        print(f"  Kite-L target       =  54.30 (BookSim avg)", flush=True)
        verdict = "✓ V2 wins" if avg < 54.3 else "✗ V2 loses"
        print(f"  Verdict: {verdict}", flush=True)

    print(f"\nTotal: {time.time() - t_start:.1f}s", flush=True)
    out_path = RESULTS_DIR / 'booksim_verify_mask.json'
    out_path.write_text(json.dumps(results, indent=2))
    print(f"Saved: {out_path}", flush=True)


if __name__ == '__main__':
    main()
