"""Run BookSim for Kite-S, Kite-M, GIA, PARL at the mask wire targets
saved in sweep_v2_full_subsets.json.

Designed to run in parallel with the main mask-greedy sweep — uses
distinct cfg/traffic file prefixes so there is no I/O collision.
Resumable via sweep_v2_extra_baselines.json.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_perf_6panel_workload import WORKLOADS
from cost_performance_experiment import (
    gen_anynet_config, gen_traffic_matrix, run_booksim,
)
from ml_express_warmstart import RESULTS_DIR, CONFIG_DIR, TOTAL_LOAD_BASE
from sweep_v2_iso_wire import alloc_wire_mm2, kite_alloc_iso_wire
from baseline_gia import gia_alloc
from baseline_parl_ppo import parl_ppo_alloc
from ml_express_warmstart import load_rate_aware_surrogate


CELL_SHAPE = {
    'K16_N4': (16, 4, 4, 4),
    'K16_N8': (16, 8, 4, 4),
    'K32_N4': (32, 4, 4, 8),
    'K32_N8': (32, 8, 4, 8),
}

BASELINES_PER_W = ['kite_s', 'kite_m', 'gia']  # wire-target per workload
PARL_ENABLED = False  # PARL excluded (code unavailable, reproduction uncertain)


def run_one(label, alloc, K, N, R, C, w_name, rate_mult=4.0):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    rate = (TOTAL_LOAD_BASE / (K * npc)) * rate_mult
    capped = {p: min(n, N) for p, n in alloc.items() if n > 0}
    cfg = f"v2xb_{label}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_v2xb_{label}_{w_name}_K{K}N{N}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    return run_booksim(cfg, traf_file, rate, timeout=900)


def alloc_for(method, grid, wire_target, per_pair_cap, traffic):
    if method == 'kite_s':
        return kite_alloc_iso_wire(grid, wire_target, per_pair_cap, 'small')
    if method == 'kite_m':
        return kite_alloc_iso_wire(grid, wire_target, per_pair_cap, 'medium')
    if method == 'gia':
        budget = max(1, int(wire_target // 2))
        return gia_alloc(grid, budget, per_pair_cap)
    raise ValueError(method)


def main():
    out_path = RESULTS_DIR / 'sweep_v2_extra_baselines.json'
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text())
        except Exception:
            results = {}
    else:
        results = {}

    full = json.loads(
        (RESULTS_DIR / 'sweep_v2_full_subsets.json').read_text())

    surrogate = load_rate_aware_surrogate()

    overall_t0 = time.time()
    n_runs = 0

    for subset_key, sd in full.items():
        results.setdefault(subset_key, {})
        subset = subset_key.split('+')
        for cell_key, cd in sd.items():
            results[subset_key].setdefault(cell_key, {})
            K, N, R, C = CELL_SHAPE[cell_key]
            grid = ChipletGrid(R, C)
            n_adj = len(grid.get_adj_pairs())
            for bpp_key, bd in cd.items():
                results[subset_key][cell_key].setdefault(bpp_key, {})
                wd = bd.get('workloads', {})
                bpp = int(bpp_key.replace('bpp', ''))
                link_budget = n_adj * bpp

                # PARL: train once per (subset, cell, bpp) using mix traffic
                parl_alloc_cached = None
                parl_done_for_subset_cell_bpp = all(
                    'parl' in results[subset_key][cell_key][bpp_key].get(w, {})
                    for w in wd.keys()
                )

                for w, w_data in wd.items():
                    results[subset_key][cell_key][bpp_key].setdefault(w, {})
                    cell_results = results[subset_key][cell_key][bpp_key][w]
                    wire_target = w_data.get('mask_wire')
                    if wire_target is None:
                        continue
                    traffic = WORKLOADS[w](K, grid)

                    for method in BASELINES_PER_W:
                        if method in cell_results:
                            continue
                        alloc = alloc_for(
                            method, grid, wire_target, N, traffic)
                        label = (f'{subset_key}_{cell_key}_{bpp_key}_'
                                 f'{method}_{w}')
                        t0 = time.time()
                        res = run_one(label, alloc, K, N, R, C, w)
                        elapsed = time.time() - t0
                        lat = res.get('latency')
                        cell_results[method] = {
                            'lat': lat,
                            'wire': alloc_wire_mm2(alloc, grid),
                            'links': sum(min(v, N) for v in alloc.values()),
                        }
                        n_runs += 1
                        lat_str = (f'{lat:.1f}' if lat is not None else 'FAIL')
                        print(f"  [{n_runs}] {subset_key:<25} {cell_key} "
                              f"{bpp_key} {w:<14} {method:<7}: "
                              f"lat={lat_str:>7} ({elapsed:.1f}s)",
                              flush=True)

                    out_path.write_text(json.dumps(results, indent=2))

    print(f"\nTotal {n_runs} extra baseline BookSims in "
          f"{(time.time()-overall_t0)/3600:.1f}h", flush=True)
    print(f"Saved: {out_path}", flush=True)


if __name__ == '__main__':
    main()
