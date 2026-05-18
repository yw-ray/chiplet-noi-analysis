"""V3 MCTS-only iso-wire sweep.

Replaces the RL+MCTS ensemble with MCTS-only (strong profile, 7 seeds),
using three warm-start types for diversity:
  seeds 0-2: greedy_union
  seeds 3-4: random_hop3_spine
  seeds 5-6: random_uniform_sample

No REINFORCE policy-gradient agents. greedy_union is still computed
internally as warm-start source, never as a direct candidate.

Stage 1a — 7 MCTS candidates (strong profile, top_k=1 each)
Stage 1b — BookSim-select best by mean raw latency
Stage 2  — per-workload booksim_greedy_mask (unchanged)
Baselines — mesh, kite_s, kite_m, kite_l, gia at iso-wire W

Output: results/ml_placement/sweep_v3_mctsonly_K{K}_N{N}.json

Usage:
  python sweep_v3_mctsonly.py          # all 4 cells
  python sweep_v3_mctsonly.py 0        # cell 0 = K32_N8 (hardest)
  python sweep_v3_mctsonly.py 1        # cell 1 = K16_N8
  python sweep_v3_mctsonly.py 2        # cell 2 = K32_N4
  python sweep_v3_mctsonly.py 3        # cell 3 = K16_N4
"""

import random as _random
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from ml_express_warmstart import RESULTS_DIR, load_rate_aware_surrogate
from run_rl_multi_workload import gen_workload_traffic, warm_start_union_greedy
from sweep_v2_iso_wire import WIRE_AREA, alloc_wire_mm2
from sweep_v2_mask_greedy import booksim_greedy_mask, run_booksim_alloc
from sweep_v3_isowire import (
    cap_alloc, prune_to_wire, vec_to_dict,
    stage2_per_workload, evaluate_baselines,
)
from baseline_gia import gia_alloc
from mcts_search import mcts_search, MCTS_PROFILES
from gen_random_spine import random_hop3_spine, random_uniform_sample


ALL_WORKLOADS = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']
SUBSETS = []
for k in [2, 3, 4]:
    for combo in itertools.combinations(ALL_WORKLOADS, k):
        SUBSETS.append(combo)

# Same cell ordering as sweep_v3_isowire.py
CELLS = [
    (32, 8, 4, 8, 2080.0),
    (16, 8, 4, 4, 960.0),
    (32, 4, 4, 8, 520.0),
    (16, 4, 4, 4, 240.0),
]

PROFILE = MCTS_PROFILES['strong']
# 7 seeds: 3 greedy, 2 hop3_spine, 2 uniform_sample
MCTS_SEEDS = [301, 302, 303, 304, 305, 306, 307]

MASK_MAX_STEPS = 3
MASK_N_CANDIDATES = 6


def out_path_for(cell_idx):
    if cell_idx is None:
        return RESULTS_DIR / 'sweep_v3_mctsonly.json'
    K, N, _, _, _ = CELLS[cell_idx]
    return RESULTS_DIR / f'sweep_v3_mctsonly_K{K}_N{N}.json'


def gen_candidates_mcts_only(subset, K, N, R, C, W, surrogate):
    grid = ChipletGrid(R, C)
    adj_set = set(grid.get_adj_pairs())
    n_adj = len(grid.get_adj_pairs())
    bpp_eq = max(2, int(W / (WIRE_AREA[1] * n_adj)) + 1)
    budget = n_adj * bpp_eq
    all_pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    hop_mask_np = np.array(
        [1 if grid.get_hops(p[0], p[1]) <= 3 else 0 for p in all_pairs],
        dtype=bool)
    mesh_protect_np = np.array(
        [1 if p in adj_set else 0 for p in all_pairs], dtype=bool)

    workload_traffics = gen_workload_traffic(list(subset), K, grid)
    surrogate_args = []
    for _, traffic_flat, _ in workload_traffics:
        surrogate_args.append({
            'traffic_flat': traffic_flat,
            'adj_set': adj_set, 'all_pairs': all_pairs,
            'K': K, 'N': N, 'budget': budget, 'n_adj': n_adj,
            'rate_mult': 4.0,
        })

    gv = warm_start_union_greedy(
        workload_traffics, grid, budget, max_dist=3,
        max_lpp=N, all_pairs=all_pairs, pair_to_idx=pair_to_idx,
    )

    cands = {}
    for seed_i, s in enumerate(MCTS_SEEDS):
        torch.manual_seed(s)
        np.random.seed(s)
        rng = _random.Random(s)

        if seed_i < 3:
            initial_state = gv.copy()
            warm_label = 'greedy'
        elif seed_i < 5:
            initial_state = random_hop3_spine(
                grid, budget, N, all_pairs, pair_to_idx, adj_set, rng=rng)
            warm_label = 'hop3'
        else:
            initial_state = random_uniform_sample(
                grid, budget, N, all_pairs, pair_to_idx, adj_set,
                max_dist=3, rng=rng)
            warm_label = 'uniform'

        top = mcts_search(
            initial_state, surrogate, surrogate_args,
            hop_mask_np, mesh_protect_np, N,
            n_iters=PROFILE['n_iters'],
            rollout_depth=PROFILE['rollout_depth'],
            expansion_branch=PROFILE['expansion_branch'],
            rollout_branch=PROFILE['rollout_branch'],
            top_k=PROFILE['top_k'],
            seed=s, verbose=False,
        )
        if top:
            best_state, pred_lat = top[0]
            a = cap_alloc(vec_to_dict(best_state, all_pairs), N)
            cands[f'mcts_s{s}_{warm_label}'] = prune_to_wire(a, grid, W)

    return cands, grid, bpp_eq


def evaluate_raw(alloc, K, N, R, C, subset, label):
    per_wl = {}
    for w in subset:
        try:
            res = run_booksim_alloc(f'{label}_{w}', alloc, K, N, R, C, w)
            per_wl[w] = res.get('latency')
        except Exception as exc:
            print(f'      [WARN] BookSim failed: {label} {w}: {exc}',
                  flush=True)
            per_wl[w] = None
    valid = [v for v in per_wl.values() if v is not None]
    return per_wl, (float(np.mean(valid)) if valid else None)


def main():
    cell_idx = None
    if len(sys.argv) > 1:
        cell_idx = int(sys.argv[1])
        cells_to_run = [CELLS[cell_idx]]
        n_total_cells = 1
    else:
        cells_to_run = CELLS
        n_total_cells = len(CELLS)

    out_path = out_path_for(cell_idx)
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text())
            print(f'Resuming from {out_path}', flush=True)
        except Exception:
            results = {}
    else:
        results = {}

    surrogate = load_rate_aware_surrogate()
    overall_t0 = time.time()
    n_done = 0
    n_total = len(SUBSETS) * n_total_cells

    for K, N, R, C, W in cells_to_run:
        cell_key = f'K{K}_N{N}'
        for subset in SUBSETS:
            subset_key = '+'.join(subset)
            results.setdefault(subset_key, {})
            cell_entry = results[subset_key].get(cell_key)
            if (cell_entry and cell_entry.get('stage2')
                    and cell_entry.get('baselines_at_W')):
                n_done += 1
                print(f'[skip {n_done}/{n_total}] '
                      f'{subset_key} | {cell_key}', flush=True)
                continue

            t_combo = time.time()
            print(f'\n=== [{n_done+1}/{n_total}] '
                  f'{subset_key} | {cell_key} | W={W:.0f} ===', flush=True)

            cands, grid, bpp_eq = gen_candidates_mcts_only(
                subset, K, N, R, C, W, surrogate)
            print(f'  Stage 1a: {len(cands)} MCTS candidates '
                  f'({(time.time() - t_combo) / 60:.1f} min)', flush=True)

            cand_eval = {}
            for name, alloc in cands.items():
                wire = alloc_wire_mm2(alloc, grid)
                n_links = sum(alloc.values())
                label = f'v3mo_{cell_key}_W{int(W)}_{subset_key}_{name}'
                per_wl, mean_lat = evaluate_raw(alloc, K, N, R, C, subset, label)
                ml = f'{mean_lat:.1f}' if mean_lat is not None else 'FAIL'
                print(f'    [cand] {name:<20}: links={n_links:>3} '
                      f'wire={wire:>6.1f} mean={ml}', flush=True)
                cand_eval[name] = {
                    'alloc': {f'{p[0]}-{p[1]}': v for p, v in alloc.items()},
                    'wire': wire,
                    'n_links': n_links,
                    'raw_per_wl': per_wl,
                    'raw_mean_lat': mean_lat,
                }

            valid = {n: c for n, c in cand_eval.items()
                     if c['raw_mean_lat'] is not None}
            if not valid:
                print(f'  [FAIL] no valid candidate', flush=True)
                results[subset_key][cell_key] = {
                    'W': W, 'bpp_eq': bpp_eq,
                    'candidates': cand_eval,
                    'selected': None,
                    'stage2': None,
                    'baselines_at_W': None,
                }
                out_path.write_text(json.dumps(results, indent=2))
                n_done += 1
                continue

            selected = min(valid, key=lambda n: valid[n]['raw_mean_lat'])
            print(f'  Stage 1b: selected={selected} '
                  f'(mean={valid[selected]["raw_mean_lat"]:.1f})', flush=True)

            sel_alloc = {
                tuple(int(x) for x in k.split('-')): v
                for k, v in cand_eval[selected]['alloc'].items()
            }
            stage2 = stage2_per_workload(
                sel_alloc, K, N, R, C, subset,
                label_prefix=f'v3mo_{cell_key}_W{int(W)}_{subset_key}_{selected}',
            )
            baselines = evaluate_baselines(
                K, N, R, C, W, subset, grid,
                label_prefix=f'v3mo_{cell_key}_W{int(W)}_{subset_key}',
            )

            results[subset_key][cell_key] = {
                'W': W, 'bpp_eq': bpp_eq,
                'candidates': cand_eval,
                'selected': selected,
                'stage1_lat': valid[selected]['raw_per_wl'],
                'stage2': stage2,
                'baselines_at_W': baselines,
            }
            out_path.write_text(json.dumps(results, indent=2))
            n_done += 1
            print(f'  Combo done in '
                  f'{(time.time() - t_combo) / 60:.1f} min '
                  f'({n_done}/{n_total})', flush=True)

    print(f'\n=== ALL DONE in '
          f'{(time.time() - overall_t0) / 3600:.1f} h ===', flush=True)
    print(f'Saved: {out_path}', flush=True)


if __name__ == '__main__':
    main()
