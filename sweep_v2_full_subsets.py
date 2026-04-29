"""V2 full subsets sweep: 11 subsets × 4 cells × 2 bpps.

For each (subset, cell, bpp):
  1. Stage 1 RL with `subset` workloads → superset
  2. For each w in subset:
     a. BookSim-greedy mask (max_steps=3, candidates=6) → mask_w
     b. Baseline mesh + kite_l at mask_w wire → BookSim
  3. JSON save incrementally

Total: 88 (subset, cell, bpp) combinations, ~22h.
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
from sweep_v2_iso_wire import (
    alloc_wire_mm2, mesh_alloc_iso_wire, kite_alloc_iso_wire,
)
from sweep_v2_mask_greedy import booksim_greedy_mask, run_booksim_alloc


ALL_WORKLOADS = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']
SUBSETS = []
for k in [2, 3, 4]:
    for combo in itertools.combinations(ALL_WORKLOADS, k):
        SUBSETS.append(combo)

CELLS = [
    (16, 4, 4, 4),
    (16, 8, 4, 4),
    (32, 4, 4, 8),
    (32, 8, 4, 8),
]
BPP_POINTS = [2, 3]

MAX_STEPS = 3
N_CANDIDATES = 6
RL_EPISODES = 200


def main():
    out_path = RESULTS_DIR / 'sweep_v2_full_subsets.json'
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text())
            print(f"Resuming from {out_path}", flush=True)
        except Exception:
            results = {}
    else:
        results = {}

    surrogate = load_rate_aware_surrogate()

    overall_t0 = time.time()
    n_done = 0
    n_total = len(SUBSETS) * len(CELLS) * len(BPP_POINTS)

    for subset in SUBSETS:
        subset_key = '+'.join(subset)
        results.setdefault(subset_key, {})

        for K, N, R, C in CELLS:
            cell_key = f'K{K}_N{N}'
            results[subset_key].setdefault(cell_key, {})

            for bpp in BPP_POINTS:
                bpp_key = f'bpp{bpp}'

                if bpp_key in results[subset_key][cell_key] \
                   and results[subset_key][cell_key][bpp_key].get('workloads'):
                    n_done += 1
                    print(f"[skip {n_done}/{n_total}] "
                          f"{subset_key} | {cell_key} | {bpp_key}", flush=True)
                    continue

                t_combo = time.time()
                print(f"\n=== [{n_done+1}/{n_total}] "
                      f"{subset_key} | {cell_key} | {bpp_key} ===",
                      flush=True)

                rl_result = train_warmstart_rl_multi(
                    surrogate, list(subset), K, N, R, C, bpp,
                    n_episodes=RL_EPISODES, rate_mult=4.0,
                    reward_type='normalized_avg', max_dist=3, verbose=False,
                )
                superset = rl_result['superset_alloc']
                grid = ChipletGrid(R, C)
                super_wire = alloc_wire_mm2(superset, grid)
                print(f"  Stage 1 RL: {len(superset)} pairs, "
                      f"{sum(superset.values())} links, "
                      f"{super_wire:.1f} mm² ({time.time()-t_combo:.1f}s)",
                      flush=True)

                workloads_data = {}
                for w in subset:
                    t_w = time.time()
                    label = (f'sub_{subset_key}_{cell_key}_'
                             f'{bpp_key}_{w}')
                    final_mask, history, raw_lat = booksim_greedy_mask(
                        superset, K, N, R, C, w,
                        max_steps=MAX_STEPS,
                        max_candidates=N_CANDIDATES,
                        label_prefix=label,
                    )
                    final_lat = (history[-1]['lat']
                                 if history else None)
                    final_wire = (history[-1]['wire']
                                  if history else None)

                    if final_wire is not None:
                        mesh_a = mesh_alloc_iso_wire(grid, final_wire, N)
                        kite_l_a = kite_alloc_iso_wire(grid, final_wire, N,
                                                       'large')
                        r_mesh = run_booksim_alloc(
                            f'{label}_mesh', mesh_a, K, N, R, C, w)
                        r_kite = run_booksim_alloc(
                            f'{label}_kite_l', kite_l_a, K, N, R, C, w)
                        mesh_lat = r_mesh.get('latency')
                        kite_lat = r_kite.get('latency')
                    else:
                        mesh_lat = None
                        kite_lat = None

                    workloads_data[w] = {
                        'raw_lat': raw_lat,
                        'mask_lat': final_lat,
                        'mask_wire': final_wire,
                        'mesh_lat': mesh_lat,
                        'kite_l_lat': kite_lat,
                        'history': history,
                        'final_mask': {f"{p[0]}-{p[1]}": v
                                       for p, v in final_mask.items()},
                    }

                    raw_str = (f'{raw_lat:.1f}'
                               if raw_lat is not None else 'FAIL')
                    mask_str = (f'{final_lat:.1f}'
                                if final_lat is not None else 'FAIL')
                    mesh_str = (f'{mesh_lat:.1f}'
                                if mesh_lat is not None else 'FAIL')
                    kite_str = (f'{kite_lat:.1f}'
                                if kite_lat is not None else 'FAIL')
                    print(f"    {w:<14}: raw={raw_str:>7} "
                          f"mask={mask_str:>7} mesh={mesh_str:>7} "
                          f"kite_l={kite_str:>7} ({time.time()-t_w:.1f}s)",
                          flush=True)

                results[subset_key][cell_key][bpp_key] = {
                    'super_wire': super_wire,
                    'superset': {f"{p[0]}-{p[1]}": v
                                 for p, v in superset.items()},
                    'workloads': workloads_data,
                }

                out_path.write_text(json.dumps(results, indent=2))
                n_done += 1
                print(f"  Combo done in {(time.time()-t_combo)/60:.1f} min, "
                      f"saved partial ({n_done}/{n_total})", flush=True)

    print(f"\n=== ALL DONE in {(time.time()-overall_t0)/3600:.1f} h ===",
          flush=True)
    print(f"Saved: {out_path}", flush=True)


if __name__ == '__main__':
    main()
