"""V3 MCTS-only wire-scaling sweep.

Same as sweep_v3_wire_scaling.py but replaces RL+MCTS candidates
with MCTS-only (strong profile, 7 seeds, three warm-start types).

Per (cell, W): Stage-1a/1b/Stage-2 for the 4-workload ALL mix.

Output: results/ml_placement/sweep_v3_mctsonly_wirescaling_K{K}_N{N}.json
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from ml_express_warmstart import RESULTS_DIR, load_rate_aware_surrogate
from sweep_v2_iso_wire import alloc_wire_mm2
from sweep_v3_isowire import cap_alloc, stage2_per_workload, evaluate_baselines
from sweep_v3_mctsonly import (
    CELLS, PROFILE, MCTS_SEEDS,
    gen_candidates_mcts_only, evaluate_raw, evaluate_baselines,
)
from noi_topology_synthesis import ChipletGrid


SUBSET = ('moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all')

WIRE_GRIDS = {
    (16, 4): [60.0, 120.0, 240.0, 480.0, 960.0, 1920.0],
    (16, 8): [120.0, 240.0, 480.0, 960.0, 1920.0, 3840.0],
    (32, 4): [130.0, 260.0, 520.0, 1040.0, 2080.0, 4160.0],
    (32, 8): [260.0, 520.0, 1040.0, 2080.0, 4160.0, 8320.0],
}


def out_path_for(K, N):
    return RESULTS_DIR / f'sweep_v3_mctsonly_wirescaling_K{K}_N{N}.json'


def run_one_W(K, N, R, C, W, surrogate):
    grid = ChipletGrid(R, C)
    cands, _, bpp_eq = gen_candidates_mcts_only(SUBSET, K, N, R, C, W, surrogate)
    cand_eval = {}
    for name, alloc in cands.items():
        wire = alloc_wire_mm2(alloc, grid)
        n_links = sum(alloc.values())
        label = f'v3mows_K{K}_N{N}_W{int(W)}_{name}'
        per_wl, mean_lat = evaluate_raw(alloc, K, N, R, C, SUBSET, label)
        ml = f'{mean_lat:.1f}' if mean_lat is not None else 'FAIL'
        print(f'    [cand] {name:<20}: links={n_links:>3} '
              f'wire={wire:>6.1f} mean={ml}', flush=True)
        cand_eval[name] = {
            'alloc': {f'{p[0]}-{p[1]}': v for p, v in alloc.items()},
            'wire': wire, 'n_links': n_links,
            'raw_per_wl': per_wl, 'raw_mean_lat': mean_lat,
        }

    valid = {n: c for n, c in cand_eval.items()
             if c['raw_mean_lat'] is not None}
    if not valid:
        return {'W': W, 'bpp_eq': bpp_eq, 'candidates': cand_eval,
                'selected': None, 'stage2': None, 'baselines_at_W': None}

    selected = min(valid, key=lambda n: valid[n]['raw_mean_lat'])
    print(f'  => selected={selected} '
          f'mean={valid[selected]["raw_mean_lat"]:.1f}', flush=True)

    sel_alloc = {
        tuple(int(x) for x in k.split('-')): v
        for k, v in cand_eval[selected]['alloc'].items()
    }
    stage2 = stage2_per_workload(
        sel_alloc, K, N, R, C, SUBSET,
        label_prefix=f'v3mows_K{K}_N{N}_W{int(W)}_{selected}',
    )
    baselines = evaluate_baselines(
        K, N, R, C, W, SUBSET, grid,
        label_prefix=f'v3mows_K{K}_N{N}_W{int(W)}',
    )
    return {
        'W': W, 'bpp_eq': bpp_eq,
        'candidates': cand_eval,
        'selected': selected,
        'stage1_lat': valid[selected]['raw_per_wl'],
        'stage2': stage2,
        'baselines_at_W': baselines,
    }


def main():
    K_arg = None
    if len(sys.argv) > 1:
        K_arg = int(sys.argv[1])
        N_arg = int(sys.argv[2]) if len(sys.argv) > 2 else None

    surrogate = load_rate_aware_surrogate()
    overall_t0 = time.time()

    for K, N, R, C, _ in CELLS:
        if K_arg is not None and K != K_arg:
            continue
        if 'N_arg' in dir() and N_arg is not None and N != N_arg:
            continue
        wire_list = WIRE_GRIDS.get((K, N), [])
        out_path = out_path_for(K, N)
        if out_path.exists():
            try:
                results = json.loads(out_path.read_text())
            except Exception:
                results = {}
        else:
            results = {}

        for W in wire_list:
            wk = f'W{int(W)}'
            if (wk in results
                    and results[wk].get('stage2')
                    and results[wk].get('baselines_at_W')):
                print(f'[skip] K{K}_N{N} W={W:.0f}', flush=True)
                continue
            print(f'\n=== K{K}_N{N} W={W:.0f} ===', flush=True)
            t0 = time.time()
            entry = run_one_W(K, N, R, C, W, surrogate)
            results[wk] = entry
            out_path.write_text(json.dumps(results, indent=2))
            print(f'  Done in {(time.time() - t0) / 60:.1f} min', flush=True)

    print(f'\n=== ALL DONE in '
          f'{(time.time() - overall_t0) / 3600:.1f} h ===', flush=True)


if __name__ == '__main__':
    main()
