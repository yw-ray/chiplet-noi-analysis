"""V3 BookSim-Select main sweep: 4 cells × 11 subsets × bpp=3 = 44 runs.

Per (cell, subset):
  Stage 1a — generate candidate supersets:
    - greedy_union  (deterministic, per-W greedy + union)
    - rl_seed_{S}   (multi-seed RL warm-started from greedy-union)
  Stage 1b — BookSim raw evaluate each candidate on the workload mix,
              pick measured-best by mean raw latency over subset.
  Stage 2  — booksim_greedy_mask per workload from the selected superset.
  Report   — per-workload mask_lat + mask_wire + iso-wire mesh_lat /
              kite_l_lat baselines for paper comparison.

Mesh-iso and Kite-L-iso are NOT in the candidate pool. They appear
only as iso-wire baselines for the paper comparison columns.

Output: results/ml_placement/sweep_v3_booksim_select.json
"""

import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from ml_express_warmstart import (
    RESULTS_DIR,
    load_rate_aware_surrogate,
)
from run_rl_multi_workload import (
    train_warmstart_rl_multi,
    warm_start_union_greedy,
    gen_workload_traffic,
)
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
    (32, 8, 4, 8),  # K32_N8 first — most likely to expose surrogate fragility
    (16, 8, 4, 4),
    (32, 4, 4, 8),
    (16, 4, 4, 4),
]
BPP_POINTS = [3]

RL_SEEDS = [42, 43, 44, 45, 46]
RL_EPISODES = 200
MASK_MAX_STEPS = 3
MASK_N_CANDIDATES = 6

OUT_PATH = RESULTS_DIR / 'sweep_v3_booksim_select.json'


def vec_to_dict(vec, all_pairs):
    return {p: int(vec[i]) for i, p in enumerate(all_pairs) if vec[i] > 0}


def cap_alloc(alloc, N):
    return {p: min(int(n), N) for p, n in alloc.items() if n > 0}


def evaluate_raw(alloc, K, N, R, C, subset, label):
    per_wl = {}
    for w in subset:
        try:
            res = run_booksim_alloc(f'{label}_{w}', alloc, K, N, R, C, w)
            per_wl[w] = res.get('latency')
        except Exception as exc:
            print(f"      [WARN] BookSim failed: {label} {w}: {exc}",
                  flush=True)
            per_wl[w] = None
    valid = [v for v in per_wl.values() if v is not None]
    mean_lat = float(np.mean(valid)) if valid else None
    return per_wl, mean_lat


def gen_candidates(subset, K, N, R, C, bpp, surrogate):
    grid = ChipletGrid(R, C)
    n_adj = len(grid.get_adj_pairs())
    budget = n_adj * bpp
    all_pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    cands = {}

    workload_traffics = gen_workload_traffic(list(subset), K, grid)
    gv = warm_start_union_greedy(
        workload_traffics, grid, budget, max_dist=3,
        max_lpp=N, all_pairs=all_pairs, pair_to_idx=pair_to_idx,
    )
    cands['greedy_union'] = cap_alloc(vec_to_dict(gv, all_pairs), N)

    for s in RL_SEEDS:
        torch.manual_seed(s)
        np.random.seed(s)
        rl_res = train_warmstart_rl_multi(
            surrogate, list(subset), K, N, R, C, bpp,
            n_episodes=RL_EPISODES, rate_mult=4.0,
            reward_type='normalized_avg', max_dist=3, verbose=False,
        )
        cands[f'rl_seed{s}'] = cap_alloc(rl_res['superset_alloc'], N)

    return cands, grid


def stage2_per_workload(superset, K, N, R, C, subset, label_prefix):
    grid = ChipletGrid(R, C)
    out = {}
    for w in subset:
        label = f'{label_prefix}_{w}'
        t0 = time.time()
        final_mask, history, raw_lat = booksim_greedy_mask(
            superset, K, N, R, C, w,
            max_steps=MASK_MAX_STEPS,
            max_candidates=MASK_N_CANDIDATES,
            label_prefix=label,
        )
        final_lat = history[-1]['lat'] if history else None
        final_wire = history[-1]['wire'] if history else None

        mesh_lat = kite_lat = None
        if final_wire is not None:
            mesh_a = mesh_alloc_iso_wire(grid, final_wire, N)
            kite_a = kite_alloc_iso_wire(grid, final_wire, N, 'large')
            try:
                r_m = run_booksim_alloc(f'{label}_mesh',
                                        mesh_a, K, N, R, C, w)
                mesh_lat = r_m.get('latency')
            except Exception as exc:
                print(f"      [WARN] mesh BookSim failed: {exc}", flush=True)
            try:
                r_k = run_booksim_alloc(f'{label}_kite_l',
                                        kite_a, K, N, R, C, w)
                kite_lat = r_k.get('latency')
            except Exception as exc:
                print(f"      [WARN] kite_l BookSim failed: {exc}",
                      flush=True)

        elapsed = time.time() - t0
        ml_str = (f'{final_lat:.1f}'
                  if final_lat is not None else 'FAIL')
        ms_str = (f'{mesh_lat:.1f}'
                  if mesh_lat is not None else 'FAIL')
        ks_str = (f'{kite_lat:.1f}'
                  if kite_lat is not None else 'FAIL')
        print(f"    {w:<14}: raw={raw_lat:.1f} mask={ml_str} "
              f"mesh={ms_str} kite_l={ks_str} ({elapsed:.1f}s)",
              flush=True)
        out[w] = {
            'raw_lat': raw_lat,
            'mask_lat': final_lat,
            'mask_wire': final_wire,
            'mesh_lat': mesh_lat,
            'kite_l_lat': kite_lat,
            'final_mask': {f'{p[0]}-{p[1]}': v
                           for p, v in final_mask.items()},
            'history': history,
        }
    return out


def main():
    if OUT_PATH.exists():
        try:
            results = json.loads(OUT_PATH.read_text())
            print(f"Resuming from {OUT_PATH}", flush=True)
        except Exception:
            results = {}
    else:
        results = {}

    surrogate = load_rate_aware_surrogate()

    overall_t0 = time.time()
    n_done = 0
    n_total = len(SUBSETS) * len(CELLS) * len(BPP_POINTS)

    for K, N, R, C in CELLS:
        cell_key = f'K{K}_N{N}'
        for subset in SUBSETS:
            subset_key = '+'.join(subset)
            results.setdefault(subset_key, {})
            results[subset_key].setdefault(cell_key, {})
            for bpp in BPP_POINTS:
                bpp_key = f'bpp{bpp}'
                if (bpp_key in results[subset_key][cell_key]
                        and results[subset_key][cell_key][bpp_key]
                        .get('stage2')):
                    n_done += 1
                    print(f"[skip {n_done}/{n_total}] "
                          f"{subset_key} | {cell_key} | {bpp_key}",
                          flush=True)
                    continue

                t_combo = time.time()
                print(f"\n=== [{n_done+1}/{n_total}] "
                      f"{subset_key} | {cell_key} | {bpp_key} ===",
                      flush=True)

                cands, grid = gen_candidates(
                    subset, K, N, R, C, bpp, surrogate)
                print(f"  Stage 1a: {len(cands)} candidates "
                      f"({(time.time() - t_combo) / 60:.1f} min)",
                      flush=True)

                cand_eval = {}
                for name, alloc in cands.items():
                    t_e = time.time()
                    wire = alloc_wire_mm2(alloc, grid)
                    n_links = sum(alloc.values())
                    label = f'v3sel_{cell_key}_{bpp_key}_{subset_key}_{name}'
                    per_wl, mean_lat = evaluate_raw(
                        alloc, K, N, R, C, subset, label)
                    ml_str = (f'{mean_lat:.1f}'
                              if mean_lat is not None else 'FAIL')
                    print(f"    {name:<15}: links={n_links:>3} "
                          f"wire={wire:>6.1f} mean_raw={ml_str} "
                          f"({time.time() - t_e:.1f}s)", flush=True)
                    cand_eval[name] = {
                        'alloc': {f'{p[0]}-{p[1]}': v
                                  for p, v in alloc.items()},
                        'wire': wire,
                        'n_links': n_links,
                        'raw_per_wl': per_wl,
                        'raw_mean_lat': mean_lat,
                    }

                valid = {n: c for n, c in cand_eval.items()
                         if c['raw_mean_lat'] is not None}
                if not valid:
                    print(f"  [FAIL] no valid candidate", flush=True)
                    results[subset_key][cell_key][bpp_key] = {
                        'candidates': cand_eval,
                        'selected': None,
                        'stage2': None,
                    }
                    OUT_PATH.write_text(json.dumps(results, indent=2))
                    n_done += 1
                    continue

                selected = min(valid.keys(),
                               key=lambda n: valid[n]['raw_mean_lat'])
                print(f"  Stage 1b: selected={selected} "
                      f"(raw_mean={valid[selected]['raw_mean_lat']:.1f})",
                      flush=True)

                sel_alloc = {tuple(int(x) for x in k.split('-')): v
                             for k, v in cand_eval[selected]['alloc']
                             .items()}
                stage2 = stage2_per_workload(
                    sel_alloc, K, N, R, C, subset,
                    label_prefix=(f'v3sel_{cell_key}_{bpp_key}_'
                                  f'{subset_key}_{selected}_mask'),
                )

                results[subset_key][cell_key][bpp_key] = {
                    'candidates': cand_eval,
                    'selected': selected,
                    'stage2': stage2,
                }
                OUT_PATH.write_text(json.dumps(results, indent=2))
                n_done += 1
                print(f"  Combo done in "
                      f"{(time.time() - t_combo) / 60:.1f} min "
                      f"({n_done}/{n_total})", flush=True)

    print(f"\n=== ALL DONE in "
          f"{(time.time() - overall_t0) / 3600:.1f} h ===", flush=True)
    print(f"Saved: {OUT_PATH}", flush=True)


if __name__ == '__main__':
    main()
