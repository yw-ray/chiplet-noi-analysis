"""V3 BookSim-Selected Candidate Framework — bad-cell pilot.

For each (subset, K, N, R, C, bpp) bad cell from the V3 plan, generate a
pool of candidate Stage-1 supersets, BookSim-evaluate each on the subset
workload mix, pick the measured-best, then run Stage-2 BookSim-greedy
mask per workload. Final reported latency per workload is
min(mask_lat, mesh_lat, kite_l_lat) — the fallback guarantee.

Candidates (~7 per cell):
  1. rl_v3_current  : Stage-1 superset already in sweep_v2_full_subsets.json
  2. greedy_union   : warm_start_union_greedy output
  3. mesh_iso       : mesh sized to current super_wire
  4. kite_l_iso     : Kite-L sized to current super_wire
  5. rl_seed{S}     : train_warmstart_rl_multi with torch/np seed S
                      (default warm-start = greedy-union, varies trajectory)

Output: results/ml_placement/pilot_booksim_select.json
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from cost_performance_experiment import alloc_express_greedy
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


PILOT_CELLS = [
    {
        'subset': ('hybrid_tp_pp', 'uniform_random', 'all_to_all'),
        'K': 16, 'N': 4, 'R': 4, 'C': 4, 'bpp': 3,
    },
    {
        'subset': ('moe', 'uniform_random'),
        'K': 16, 'N': 8, 'R': 4, 'C': 4, 'bpp': 3,
    },
    {
        'subset': ('moe', 'uniform_random', 'all_to_all'),
        'K': 16, 'N': 8, 'R': 4, 'C': 4, 'bpp': 3,
    },
]

RL_SEEDS = [42, 43, 44]
MASK_MAX_STEPS = 3
MASK_N_CANDIDATES = 6
RL_EPISODES = 200
PARTIAL_PATH = RESULTS_DIR / 'sweep_v2_full_subsets.json'
OUT_PATH = RESULTS_DIR / 'pilot_booksim_select.json'


def vec_to_dict(vec, all_pairs):
    return {p: int(vec[i]) for i, p in enumerate(all_pairs) if vec[i] > 0}


def cap_alloc(alloc, N):
    return {p: min(int(n), N) for p, n in alloc.items() if n > 0}


def evaluate_raw(alloc, K, N, R, C, subset, label):
    """BookSim raw latency per workload at full superset (no masking)."""
    per_wl = {}
    for w in subset:
        cfg_label = f'{label}_{w}'
        try:
            res = run_booksim_alloc(cfg_label, alloc, K, N, R, C, w)
            per_wl[w] = res.get('latency')
        except Exception as exc:
            print(f"    [WARN] BookSim failed: {label} {w}: {exc}", flush=True)
            per_wl[w] = None
    valid = [v for v in per_wl.values() if v is not None]
    mean_lat = float(np.mean(valid)) if valid else None
    return per_wl, mean_lat


def gen_candidates(cell, partial_data, surrogate):
    K, N, R, C = cell['K'], cell['N'], cell['R'], cell['C']
    bpp = cell['bpp']
    subset = cell['subset']
    subset_key = '+'.join(subset)
    cell_key = f'K{K}_N{N}'
    bpp_key = f'bpp{bpp}'

    grid = ChipletGrid(R, C)
    n_adj = len(grid.get_adj_pairs())
    budget = n_adj * bpp
    all_pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    cands = {}

    # 1. rl_v3_current — superset already in partial sweep
    cur = (partial_data.get(subset_key, {}).get(cell_key, {})
           .get(bpp_key, {}))
    if cur and 'superset' in cur:
        rl_cur = {tuple(int(x) for x in k.split('-')): v
                  for k, v in cur['superset'].items()}
        cands['rl_v3_current'] = cap_alloc(rl_cur, N)

    # 2. greedy_union
    workload_traffics = gen_workload_traffic(list(subset), K, grid)
    gv = warm_start_union_greedy(
        workload_traffics, grid, budget, max_dist=3,
        max_lpp=N, all_pairs=all_pairs, pair_to_idx=pair_to_idx,
    )
    cands['greedy_union'] = cap_alloc(vec_to_dict(gv, all_pairs), N)

    # We need a wire reference for mesh/kite_l candidates. Use the maximum
    # wire across rl_v3_current + greedy_union so iso-wire baselines have at
    # least as much wire as our learned candidates.
    ref_wires = []
    if 'rl_v3_current' in cands:
        ref_wires.append(alloc_wire_mm2(cands['rl_v3_current'], grid))
    ref_wires.append(alloc_wire_mm2(cands['greedy_union'], grid))
    ref_wire = max(ref_wires)

    # 3. mesh_iso at ref_wire
    mesh_a = mesh_alloc_iso_wire(grid, ref_wire, per_pair_cap=N)
    if mesh_a:
        cands['mesh_iso'] = cap_alloc(mesh_a, N)

    # 4. kite_l_iso at ref_wire
    kite_a = kite_alloc_iso_wire(grid, ref_wire, per_pair_cap=N,
                                 variant='large')
    if kite_a:
        cands['kite_l_iso'] = cap_alloc(kite_a, N)

    # 5. RL seeded variants (default warm-start = union-greedy inside)
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
    """Run BookSim-greedy mask per workload + iso-wire mesh/Kite-L baselines."""
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
                r_m = run_booksim_alloc(f'{label}_mesh', mesh_a, K, N, R, C, w)
                mesh_lat = r_m.get('latency')
            except Exception as exc:
                print(f"    [WARN] mesh BookSim failed: {exc}", flush=True)
            try:
                r_k = run_booksim_alloc(f'{label}_kite_l', kite_a, K, N, R, C, w)
                kite_lat = r_k.get('latency')
            except Exception as exc:
                print(f"    [WARN] kite_l BookSim failed: {exc}", flush=True)

        opts = [v for v in [final_lat, mesh_lat, kite_lat] if v is not None]
        min_lat = min(opts) if opts else None
        chosen = None
        if min_lat is not None:
            for name, val in (('mask', final_lat), ('mesh', mesh_lat),
                              ('kite_l', kite_lat)):
                if val is not None and val == min_lat:
                    chosen = name
                    break

        elapsed = time.time() - t0
        ml_str = f'{min_lat:.1f}' if min_lat is not None else 'FAIL'
        print(f"    {w:<14}: raw={raw_lat:.1f} mask={final_lat:.1f} "
              f"mesh={mesh_lat} kite_l={kite_lat} → "
              f"min={ml_str} via {chosen} ({elapsed:.1f}s)", flush=True)
        out[w] = {
            'raw_lat': raw_lat,
            'mask_lat': final_lat,
            'mask_wire': final_wire,
            'mesh_lat': mesh_lat,
            'kite_l_lat': kite_lat,
            'min_lat': min_lat,
            'min_via': chosen,
            'final_mask': {f'{p[0]}-{p[1]}': v for p, v in final_mask.items()},
            'history': history,
        }
    return out


def main():
    if not PARTIAL_PATH.exists():
        print(f"Missing {PARTIAL_PATH} — need partial sweep for rl_v3_current",
              flush=True)
        sys.exit(1)
    partial_data = json.loads(PARTIAL_PATH.read_text())

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

    for cell in PILOT_CELLS:
        subset = cell['subset']
        subset_key = '+'.join(subset)
        cell_tag = (f"{subset_key}_K{cell['K']}_N{cell['N']}"
                    f"_bpp{cell['bpp']}")
        print(f"\n========== {cell_tag} ==========", flush=True)

        if cell_tag in results and results[cell_tag].get('stage2'):
            print(f"[skip] already complete", flush=True)
            continue

        t_cell = time.time()
        K, N, R, C = cell['K'], cell['N'], cell['R'], cell['C']

        cands, grid = gen_candidates(cell, partial_data, surrogate)
        print(f"  Generated {len(cands)} candidates "
              f"({(time.time() - t_cell) / 60:.1f} min)", flush=True)

        cand_eval = {}
        for name, alloc in cands.items():
            t_e = time.time()
            wire = alloc_wire_mm2(alloc, grid)
            n_links = sum(alloc.values())
            label = f'pilot_{cell_tag}_{name}_raw'
            per_wl, mean_lat = evaluate_raw(alloc, K, N, R, C, subset, label)
            ml_str = f'{mean_lat:.1f}' if mean_lat is not None else 'FAIL'
            print(f"    {name:<18}: links={n_links:>3} wire={wire:>6.1f} "
                  f"mean_raw_lat={ml_str} ({time.time() - t_e:.1f}s)",
                  flush=True)
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
            print(f"  [FAIL] no valid candidate", flush=True)
            results[cell_tag] = {
                'cell': {**cell, 'subset': list(subset)},
                'candidates': cand_eval,
                'selected': None,
                'stage2': None,
            }
            OUT_PATH.write_text(json.dumps(results, indent=2))
            continue

        selected = min(valid.keys(),
                       key=lambda n: valid[n]['raw_mean_lat'])
        print(f"  -> selected: {selected} "
              f"(raw_mean={valid[selected]['raw_mean_lat']:.1f})", flush=True)

        sel_alloc = {tuple(int(x) for x in k.split('-')): v
                     for k, v in cand_eval[selected]['alloc'].items()}
        stage2 = stage2_per_workload(
            sel_alloc, K, N, R, C, subset,
            label_prefix=f'pilot_{cell_tag}_{selected}_mask',
        )

        cur = (partial_data.get(subset_key, {})
               .get(f"K{K}_N{N}", {})
               .get(f"bpp{cell['bpp']}", {}))
        cur_wls = cur.get('workloads', {}) if cur else {}
        current_partial = {
            w: {
                'mask_lat': cur_wls.get(w, {}).get('mask_lat'),
                'mesh_lat': cur_wls.get(w, {}).get('mesh_lat'),
                'kite_l_lat': cur_wls.get(w, {}).get('kite_l_lat'),
            } for w in subset
        }

        results[cell_tag] = {
            'cell': {**cell, 'subset': list(subset)},
            'candidates': cand_eval,
            'selected': selected,
            'stage2': stage2,
            'current_partial': current_partial,
        }
        OUT_PATH.write_text(json.dumps(results, indent=2))
        print(f"  Cell done in {(time.time() - t_cell) / 60:.1f} min, "
              f"saved partial.", flush=True)

    print(f"\n=== ALL PILOT DONE in "
          f"{(time.time() - overall_t0) / 3600:.2f} h ===", flush=True)
    print(f"Saved: {OUT_PATH}", flush=True)


if __name__ == '__main__':
    main()
