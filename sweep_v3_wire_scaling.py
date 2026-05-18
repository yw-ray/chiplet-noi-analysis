"""V3 wire-scaling sweep — single subset per cell, varied W.

For the paper's "wire vs latency" plot. Shows that as wire grows:
  - Mesh, Kite-S/M/L, GIA plateau (their structure caps the benefit).
  - Ours keeps improving (RL exploits the extra budget).

Per (cell, W): runs the same Stage-1a/1b/Stage-2 pipeline as
sweep_v3_isowire.py, but only for ONE subset (the 4-workload "ALL" mix
which is the most demanding case in the main eval).

Output: results/ml_placement/sweep_v3_wire_scaling_K{K}_N{N}.json
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from ml_express_warmstart import (
    RESULTS_DIR, load_rate_aware_surrogate, load_surrogate_v3,
)
from sweep_v3_isowire import SURROGATE_VARIANT
from sweep_v3_isowire import (
    WIRE_AREA, alloc_wire_mm2,
    gen_candidates, evaluate_raw, stage2_per_workload,
    evaluate_baselines,
    cap_alloc, prune_to_wire,
)


# All 4 workloads — the hardest mix in the main eval.
SUBSET = ('moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all')

# Wire grids per cell. Span from mesh-only floor up to ~4× the main W.
# Includes the main eval W so the plot has the paper's reference point.
WIRE_GRIDS = {
    # (K, N, R, C, R_label): list of W in mm²
    (16, 4, 4, 4): [60.0, 120.0, 240.0, 480.0, 960.0, 1920.0],
    (16, 8, 4, 4): [120.0, 240.0, 480.0, 960.0, 1920.0, 3840.0],
    (32, 4, 4, 8): [130.0, 260.0, 520.0, 1040.0, 2080.0, 4160.0],
    (32, 8, 4, 8): [260.0, 520.0, 1040.0, 2080.0, 4160.0, 8320.0],
}


def out_path_for(K, N):
    suffix = '_v3surr' if SURROGATE_VARIANT == 'v3' else ''
    return RESULTS_DIR / f'sweep_v3_wire_scaling_K{K}_N{N}{suffix}.json'


def run_one_W(K, N, R, C, W, surrogate, label_prefix):
    grid = ChipletGrid(R, C)
    cands, _, bpp_eq = gen_candidates(SUBSET, K, N, R, C, W, surrogate)
    cand_eval = {}
    for name, alloc in cands.items():
        wire = alloc_wire_mm2(alloc, grid)
        n_links = sum(alloc.values())
        per_wl, mean_lat = evaluate_raw(
            alloc, K, N, R, C, SUBSET,
            f'{label_prefix}_{name}')
        cand_eval[name] = {
            'alloc': {f'{p[0]}-{p[1]}': v for p, v in alloc.items()},
            'wire': wire,
            'n_links': n_links,
            'raw_per_wl': per_wl,
            'raw_mean_lat': mean_lat,
        }
        ml_str = f'{mean_lat:.1f}' if mean_lat is not None else 'FAIL'
        print(f"    [cand] {name:<14}: links={n_links:>3} wire={wire:>7.1f} "
              f"mean_raw={ml_str}", flush=True)

    valid = {n: c for n, c in cand_eval.items()
             if c['raw_mean_lat'] is not None}
    if not valid:
        return None
    selected = min(valid.keys(),
                   key=lambda n: valid[n]['raw_mean_lat'])
    print(f"  Stage 1b: selected={selected} "
          f"(raw_mean={valid[selected]['raw_mean_lat']:.1f})",
          flush=True)

    sel_alloc = {tuple(int(x) for x in k.split('-')): v
                 for k, v in cand_eval[selected]['alloc'].items()}
    stage2 = stage2_per_workload(
        sel_alloc, K, N, R, C, SUBSET,
        label_prefix=f'{label_prefix}_{selected}_mask')
    baselines = evaluate_baselines(
        K, N, R, C, W, SUBSET, grid, label_prefix=label_prefix)

    return {
        'W': W, 'bpp_eq': bpp_eq,
        'candidates': cand_eval,
        'selected': selected,
        'stage2': stage2,
        'baselines_at_W': baselines,
    }


def main():
    if len(sys.argv) < 2:
        print('Usage: sweep_v3_wire_scaling.py <cell_idx>', flush=True)
        print('cell_idx: 0=K32_N8, 1=K16_N8, 2=K32_N4, 3=K16_N4', flush=True)
        sys.exit(1)
    cell_idx = int(sys.argv[1])
    cells = [(32, 8, 4, 8), (16, 8, 4, 4),
             (32, 4, 4, 8), (16, 4, 4, 4)]
    K, N, R, C = cells[cell_idx]
    Ws = WIRE_GRIDS[(K, N, R, C)]
    out_path = out_path_for(K, N)

    if out_path.exists():
        try:
            results = json.loads(out_path.read_text())
            print(f"Resuming from {out_path}", flush=True)
        except Exception:
            results = {}
    else:
        results = {}

    if SURROGATE_VARIANT == 'v3':
        surrogate = load_surrogate_v3()
    else:
        surrogate = load_rate_aware_surrogate()
    overall_t0 = time.time()

    for W in Ws:
        W_key = f'W{int(W)}'
        if W_key in results and results[W_key].get('stage2'):
            print(f"[skip] {W_key}", flush=True)
            continue
        t0 = time.time()
        print(f"\n=== K{K}_N{N} W={W} ===", flush=True)
        result = run_one_W(
            K, N, R, C, W, surrogate,
            label_prefix=f'wsc_K{K}_N{N}_W{int(W)}')
        if result is None:
            print(f"  [FAIL] all candidates failed at W={W}",
                  flush=True)
            continue
        results[W_key] = result
        out_path.write_text(json.dumps(results, indent=2))
        print(f"  W={W} done in "
              f"{(time.time() - t0) / 60:.1f} min", flush=True)

    print(f"\n=== ALL DONE in "
          f"{(time.time() - overall_t0) / 3600:.1f} h ===", flush=True)
    print(f"Saved: {out_path}", flush=True)


if __name__ == '__main__':
    main()
