"""Compare superset_raw vs Stage-2 mask in BookSim for K32_N4.

For each (bpp, workload), run BookSim on:
  - ours superset (all express links active)
  - ours mask (Stage-2 RL learned subset)

Goal: see if mask actually beats raw, or if mask is worse for some
workloads (suggesting mask policy needs rethinking).
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


def run_one(label, alloc, K, N, R, C, w_name, rate_mult=4.0):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    rate = (TOTAL_LOAD_BASE / (K * npc)) * rate_mult
    capped = {p: min(n, N) for p, n in alloc.items()}
    cfg = f"v2cmp_{label}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_v2cmp_{label}_{w_name}_K{K}N{N}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    return run_booksim(cfg, traf_file, rate, timeout=900)


def main():
    K, N, R, C = 32, 4, 4, 8
    workloads = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']

    data = json.loads(
        (RESULTS_DIR / 'sweep_v2_pareto_full.json').read_text())
    cd = data['K32_N4']

    print(f"K=32 N=4: superset_raw vs mask BookSim comparison\n")
    print(f"{'bpp':>4} | {'workload':<18} | {'raw lat':>8} | "
          f"{'mask lat':>8} | {'raw wire':>9} | {'mask wire':>9}")
    print('-' * 70)

    results = {}
    for bpp_key in sorted(cd.keys(), key=lambda k: int(k.replace('bpp', ''))):
        bd = cd[bpp_key]
        superset = {tuple(int(x) for x in k.split('-')): v
                    for k, v in bd['superset'].items()}
        masks = bd['masks']
        results[bpp_key] = {}
        for w in workloads:
            mask = {tuple(int(x) for x in k.split('-')): v
                    for k, v in masks[w].items()}
            t0 = time.time()
            r_raw = run_one(f'{bpp_key}_raw', superset, K, N, R, C, w)
            elapsed_raw = time.time() - t0
            t0 = time.time()
            r_mask = run_one(f'{bpp_key}_mask', mask, K, N, R, C, w)
            elapsed_mask = time.time() - t0

            raw_lat = r_raw.get('latency')
            mask_lat = r_mask.get('latency')

            from sweep_v2_iso_wire import alloc_wire_mm2
            grid = ChipletGrid(R, C)
            raw_wire = alloc_wire_mm2(superset, grid)
            mask_wire = alloc_wire_mm2(mask, grid)

            results[bpp_key][w] = {
                'raw_lat': raw_lat, 'mask_lat': mask_lat,
                'raw_wire': raw_wire, 'mask_wire': mask_wire,
            }
            raw_str = f"{raw_lat:.2f}" if raw_lat else "FAIL"
            mask_str = f"{mask_lat:.2f}" if mask_lat else "FAIL"
            print(f"{bpp_key:>4} | {w:<18} | {raw_str:>8} | "
                  f"{mask_str:>8} | {raw_wire:>9.1f} | {mask_wire:>9.1f}",
                  flush=True)

    out = RESULTS_DIR / 'booksim_verify_mask_vs_raw.json'
    out.write_text(json.dumps(results, indent=2))
    print(f"\nSaved: {out}", flush=True)


if __name__ == '__main__':
    main()
