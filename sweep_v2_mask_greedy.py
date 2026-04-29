"""BookSim-greedy mask sweep: 4 cells × bpp{2,3} × 4 workloads.

For each (cell, bpp, workload):
  Start mask = ours superset (Stage 1 RL output)
  Iteratively try removing one express link, pick the one with lowest
  resulting BookSim latency, stop when latency exceeds raw × tolerance
  or no candidate is acceptable.

Output: per (cell, bpp, workload), record raw_lat, final mask, mask
wire, mask power-saving %, full history.
"""

import json
import random
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
from sweep_v2_iso_wire import alloc_wire_mm2


CELLS = [
    (16, 4, 4, 4),
    (16, 8, 4, 4),
    (32, 4, 4, 8),
    (32, 8, 4, 8),
]
BPP_POINTS = [2, 3]
WORKLOADS_LIST = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']

LAT_TOLERANCE = 1.02
MAX_STEPS = 5
N_CANDIDATES = 10


def run_booksim_alloc(label, alloc, K, N, R, C, w_name, rate_mult=4.0):
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[w_name](K, grid)
    npc = N * N
    rate = (TOTAL_LOAD_BASE / (K * npc)) * rate_mult
    capped = {p: min(n, N) for p, n in alloc.items() if n > 0}
    cfg = f"v2mg_{label}_{w_name}_K{K}N{N}"
    traf_file = f"traffic_v2mg_{label}_{w_name}_K{K}N{N}.txt"
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)
    gen_anynet_config(cfg, grid, capped, chip_n=N, outdir=CONFIG_DIR)
    return run_booksim(cfg, traf_file, rate, timeout=900)


def booksim_greedy_mask(superset, K, N, R, C, w_name,
                         max_steps=MAX_STEPS,
                         max_candidates=N_CANDIDATES,
                         lat_tolerance=LAT_TOLERANCE,
                         label_prefix=''):
    grid = ChipletGrid(R, C)
    adj_set = set(grid.get_adj_pairs())

    mask = dict(superset)
    res = run_booksim_alloc(f'{label_prefix}_raw', mask, K, N, R, C, w_name)
    raw_lat = res.get('latency')
    if raw_lat is None:
        return mask, [], None
    target_lat = raw_lat * lat_tolerance
    raw_wire = alloc_wire_mm2(mask, grid)

    history = [{
        'step': 0, 'lat': raw_lat,
        'links': sum(mask.values()), 'wire': raw_wire,
        'wire_saved_pct': 0.0,
    }]

    rng = random.Random(42)
    for step in range(max_steps):
        express_eligible = [(p, n) for p, n in mask.items()
                            if p not in adj_set and n > 0]
        if not express_eligible:
            break
        n_cand = min(max_candidates, len(express_eligible))
        candidates = rng.sample(express_eligible, n_cand)

        best_lat = None
        best_pair = None
        for p, n in candidates:
            test_mask = dict(mask)
            if test_mask[p] == 1:
                del test_mask[p]
            else:
                test_mask[p] -= 1
            cfg_label = f'{label_prefix}_s{step+1}_off_{p[0]}_{p[1]}'
            cres = run_booksim_alloc(cfg_label, test_mask, K, N, R, C, w_name)
            lat = cres.get('latency')
            if lat is None:
                continue
            if best_lat is None or lat < best_lat:
                best_lat = lat
                best_pair = p

        if best_pair is None or best_lat > target_lat:
            break

        if mask[best_pair] == 1:
            del mask[best_pair]
        else:
            mask[best_pair] -= 1
        new_wire = alloc_wire_mm2(mask, grid)
        history.append({
            'step': step + 1, 'lat': best_lat,
            'links': sum(mask.values()), 'wire': new_wire,
            'wire_saved_pct': (1 - new_wire / raw_wire) * 100,
        })

    return mask, history, raw_lat


def main():
    out_path = RESULTS_DIR / 'sweep_v2_mask_greedy.json'
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text())
        except Exception:
            results = {}
    else:
        results = {}

    full = json.loads((RESULTS_DIR / 'sweep_v2_pareto_full.json').read_text())

    overall_t0 = time.time()

    for K, N, R, C in CELLS:
        cell_key = f"K{K}_N{N}"
        results.setdefault(cell_key, {})

        for bpp in BPP_POINTS:
            bpp_key = f"bpp{bpp}"
            if bpp_key in results[cell_key]:
                print(f"[skip] {cell_key} {bpp_key} already done", flush=True)
                continue

            cd = full.get(cell_key, {}).get(bpp_key, {})
            if not cd:
                print(f"[miss] {cell_key} {bpp_key} no Stage-1 superset",
                      flush=True)
                continue

            superset = {tuple(int(x) for x in k.split('-')): v
                        for k, v in cd['superset'].items()}
            super_wire = cd['super_wire']
            print(f"\n=== {cell_key} {bpp_key} (super_wire={super_wire:.1f}) ===",
                  flush=True)

            results[cell_key][bpp_key] = {
                'super_wire': super_wire,
                'workloads': {},
            }
            for w in WORKLOADS_LIST:
                t0 = time.time()
                final_mask, history, raw_lat = booksim_greedy_mask(
                    superset, K, N, R, C, w,
                    label_prefix=f'{cell_key}_{bpp_key}_{w}',
                )
                elapsed = time.time() - t0
                final_lat = history[-1]['lat'] if history else None
                final_wire = history[-1]['wire'] if history else None
                wire_saved = (history[-1]['wire_saved_pct']
                              if history else 0.0)
                final_lat_str = (f'{final_lat:.2f}'
                                 if final_lat is not None else 'FAIL')
                print(f"  {w:<18}: raw_lat={raw_lat:.2f} → "
                      f"mask_lat={final_lat_str} "
                      f"({len(history)-1} steps), "
                      f"wire_saved={wire_saved:.1f}%, {elapsed:.1f}s",
                      flush=True)
                results[cell_key][bpp_key]['workloads'][w] = {
                    'raw_lat': raw_lat,
                    'final_lat': final_lat,
                    'final_wire': final_wire,
                    'wire_saved_pct': wire_saved,
                    'history': history,
                    'final_mask': {f"{p[0]}-{p[1]}": v
                                   for p, v in final_mask.items()},
                }

            out_path.write_text(json.dumps(results, indent=2))
            print(f"  Saved partial: {out_path}", flush=True)

    print(f"\nTotal {(time.time()-overall_t0)/60:.1f} min", flush=True)
    print(f"Saved: {out_path}", flush=True)


if __name__ == '__main__':
    main()
