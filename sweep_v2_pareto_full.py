"""V2 full wire-area Pareto sweep: 4 (K, N) cells x 4 wire budgets.

For each (K, N) cell × wire budget point:
  1. Train Stage 1 RL (joint multi-workload superset)
  2. Train Stage 2 RL per workload (4 masks)
  3. Run BookSim: 5 methods × 4 workloads = 20 runs at the same wire-area
     (baseline allocations are sized to match Ours' mask wire-area)

Output: results/ml_placement/sweep_v2_pareto_full.json (incrementally
saved after each (cell, bpp)).
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
from ml_express_warmstart import (
    RESULTS_DIR, CONFIG_DIR, TOTAL_LOAD_BASE,
    load_rate_aware_surrogate,
)
from run_rl_multi_workload import train_warmstart_rl_multi
from run_rl_mask import train_mask_rl
from sweep_v2_iso_wire import (
    alloc_wire_mm2, mesh_alloc_iso_wire, kite_alloc_iso_wire,
)


CELLS = [
    (16, 4, 4, 4),
    (16, 8, 4, 4),
    (32, 4, 4, 8),
    (32, 8, 4, 8),
]
BPP_POINTS = [1, 2, 3, 4]
WORKLOADS_LIST = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']


def run_one(label, alloc, K, N, R, C, w_name, rate_mult=4.0):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    rate = (TOTAL_LOAD_BASE / (K * npc)) * rate_mult
    capped = {p: min(n, N) for p, n in alloc.items()}
    cfg = f"v2parf_{label}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_v2parf_{label}_{w_name}_K{K}N{N}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    return run_booksim(cfg, traf_file, rate, timeout=900)


def main():
    surrogate = load_rate_aware_surrogate()
    out_path = RESULTS_DIR / 'sweep_v2_pareto_full.json'
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text())
            print(f"Resuming from existing {out_path}", flush=True)
        except Exception:
            results = {}
    else:
        results = {}

    overall_start = time.time()

    for K, N, R, C in CELLS:
        cell_key = f"K{K}_N{N}"
        results.setdefault(cell_key, {})
        grid = ChipletGrid(R, C)
        n_adj = len(grid.get_adj_pairs())

        for bpp in BPP_POINTS:
            bpp_key = f"bpp{bpp}"
            if bpp_key in results[cell_key] and results[cell_key][bpp_key].get('raw'):
                print(f"\n[skip] {cell_key} {bpp_key} already done", flush=True)
                continue

            link_budget = n_adj * bpp
            print(f"\n=== {cell_key} bpp={bpp} (link_budget={link_budget}) ===",
                  flush=True)

            t0 = time.time()
            rl_result = train_warmstart_rl_multi(
                surrogate, WORKLOADS_LIST, K, N, R, C, bpp,
                n_episodes=200, rate_mult=4.0,
                reward_type='normalized_avg', max_dist=3, verbose=False,
            )
            superset = rl_result['superset_alloc']
            super_wire = alloc_wire_mm2(superset, grid)
            print(f"  Stage 1 RL: {len(superset)} pairs, "
                  f"{sum(superset.values())} links, "
                  f"{super_wire:.1f} mm² ({time.time()-t0:.1f}s)",
                  flush=True)

            masks = {}
            mask_budget = max(1, int(sum(superset.values()) * 0.7))
            for w in WORKLOADS_LIST:
                t0 = time.time()
                mres = train_mask_rl(
                    surrogate, superset, w, K, N, R, C, mask_budget,
                    n_episodes=150, rate_mult=4.0, verbose=False,
                )
                masks[w] = mres['mask_alloc']
                mw = alloc_wire_mm2(masks[w], grid)
                print(f"  Stage 2 mask {w:<18}: {mw:>6.1f} mm² "
                      f"({sum(masks[w].values())} links, {time.time()-t0:.1f}s)",
                      flush=True)

            ours_wires = {w: alloc_wire_mm2(masks[w], grid)
                          for w in WORKLOADS_LIST}

            raw = {m: {} for m in
                   ['mesh', 'kite_s', 'kite_m', 'kite_l', 'ours']}
            wire_used = {m: {} for m in raw}

            for w in WORKLOADS_LIST:
                wb = ours_wires[w]
                per_method_alloc = {
                    'mesh': mesh_alloc_iso_wire(grid, wb, N),
                    'kite_s': kite_alloc_iso_wire(grid, wb, N, 'small'),
                    'kite_m': kite_alloc_iso_wire(grid, wb, N, 'medium'),
                    'kite_l': kite_alloc_iso_wire(grid, wb, N, 'large'),
                    'ours': masks[w],
                }
                for method, alloc in per_method_alloc.items():
                    t0 = time.time()
                    res = run_one(f'{cell_key}_bpp{bpp}_{method}',
                                  alloc, K, N, R, C, w)
                    elapsed = time.time() - t0
                    lat = res.get('latency')
                    wm = alloc_wire_mm2(alloc, grid)
                    raw[method][w] = lat
                    wire_used[method][w] = wm
                    lat_str = f"{lat:.2f}" if lat is not None else "FAIL"
                    print(f"    {method:<8} | {w:<18} | "
                          f"wire={wm:>6.1f} | "
                          f"links={sum(min(v,N) for v in alloc.values()):>3} | "
                          f"lat={lat_str:>10} | {elapsed:>5.1f}s",
                          flush=True)

            mix_avgs = {}
            for k in [2, 3, 4]:
                mix_avgs[k] = {}
                for combo in itertools.combinations(WORKLOADS_LIST, k):
                    lab = '+'.join(combo)
                    row = {}
                    for m in raw:
                        vals = [raw[m].get(ww) for ww in combo]
                        row[m] = (None if any(v is None for v in vals)
                                  else sum(vals) / len(vals))
                    mix_avgs[k][lab] = row

            results[cell_key][bpp_key] = {
                'super_wire': super_wire,
                'ours_wires': ours_wires,
                'wire_used': wire_used,
                'raw': raw,
                'mix_avgs': mix_avgs,
                'superset': {f"{p[0]}-{p[1]}": v
                             for p, v in superset.items()},
                'masks': {w: {f"{p[0]}-{p[1]}": v for p, v in m.items()}
                          for w, m in masks.items()},
            }

            out_path.write_text(json.dumps(results, indent=2))
            print(f"  Saved partial: {out_path}", flush=True)

    print(f"\n=== ALL DONE in {(time.time()-overall_start)/60:.1f} min ===",
          flush=True)


if __name__ == '__main__':
    main()
