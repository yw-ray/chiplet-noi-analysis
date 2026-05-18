"""MCTS-only pilot on K16_N4 (all 11 subsets, W=240).

Plan validation: compare MCTS-only (strong profile, 7 seeds) against
the existing RL+MCTS combo results in sweep_v3_isowire_K16_N4.json.

Success criterion: MCTS-only ≤ RL+MCTS in ≥ 9/11 subsets (gap ≤ 5%)
on measured mean raw latency.

MCTS seed assignment (7 seeds total, no RL, no baseline copies):
  seeds 0-2: greedy_union warm-start
  seeds 3-4: random_hop3_spine warm-start
  seeds 5-6: random_uniform_sample warm-start

Stage 1b: BookSim-select best among 7 MCTS candidates.
Stage 2:  skipped (iso-wire comparison only; Stage-2 can be added later).

Output: results/ml_placement/pilot_mctsonly_k16n4.json
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
from ml_express_warmstart import RESULTS_DIR, load_surrogate_v3
from run_rl_multi_workload import gen_workload_traffic, warm_start_union_greedy
from sweep_v2_iso_wire import WIRE_AREA, alloc_wire_mm2
from sweep_v2_mask_greedy import run_booksim_alloc
from sweep_v3_isowire import cap_alloc, prune_to_wire, vec_to_dict
from mcts_search import mcts_search, MCTS_PROFILES
from gen_random_spine import random_hop3_spine, random_uniform_sample


ALL_WORKLOADS = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']
SUBSETS = []
for k in [2, 3, 4]:
    for combo in itertools.combinations(ALL_WORKLOADS, k):
        SUBSETS.append(combo)

K, N, R, C, W = 16, 4, 4, 4, 240.0

# Strong MCTS profile from plan
PROFILE = MCTS_PROFILES['strong']

# Seeds 0-2: greedy_union, 3-4: hop3_spine, 5-6: uniform_sample
MCTS_SEEDS = [201, 202, 203, 204, 205, 206, 207]

OUT_PATH = RESULTS_DIR / 'pilot_mctsonly_k16n4.json'
BASELINE_PATH = RESULTS_DIR / 'sweep_v3_isowire_K16_N4.json'


def evaluate_raw(alloc, subset, label):
    per_wl = {}
    for w in subset:
        try:
            res = run_booksim_alloc(f'{label}_{w}', alloc, K, N, R, C, w)
            per_wl[w] = res.get('latency')
        except Exception as exc:
            print(f'      [WARN] BookSim {label} {w}: {exc}', flush=True)
            per_wl[w] = None
    valid = [v for v in per_wl.values() if v is not None]
    return per_wl, (float(np.mean(valid)) if valid else None)


def run_subset(subset, surrogate, subset_key):
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

    # Greedy warm-start (shared across seeds 0-2)
    gv = warm_start_union_greedy(
        workload_traffics, grid, budget, max_dist=3,
        max_lpp=N, all_pairs=all_pairs, pair_to_idx=pair_to_idx,
    )

    cands = {}
    for seed_i, s in enumerate(MCTS_SEEDS):
        torch.manual_seed(s)
        np.random.seed(s)
        import random as _r
        rng = _r.Random(s)

        if seed_i < 3:
            initial_state = gv.copy()
            warm_label = 'greedy_union'
        elif seed_i < 5:
            initial_state = random_hop3_spine(
                grid, budget, N, all_pairs, pair_to_idx, adj_set,
                rng=rng)
            warm_label = 'hop3_spine'
        else:
            initial_state = random_uniform_sample(
                grid, budget, N, all_pairs, pair_to_idx, adj_set,
                max_dist=3, rng=rng)
            warm_label = 'uniform_sample'

        t0 = time.time()
        top = mcts_search(
            initial_state, surrogate, surrogate_args,
            hop_mask_np, mesh_protect_np, N,
            n_iters=PROFILE['n_iters'],
            rollout_depth=PROFILE['rollout_depth'],
            expansion_branch=PROFILE['expansion_branch'],
            rollout_branch=PROFILE['rollout_branch'],
            top_k=PROFILE['top_k'],
            seed=s, verbose=False,
            surrogate_version='v3',
        )
        elapsed = time.time() - t0
        cand_name = f'mcts_s{s}_{warm_label}'
        if top:
            best_state, pred_lat = top[0]
            a = cap_alloc(vec_to_dict(best_state, all_pairs), N)
            cands[cand_name] = {
                'alloc': prune_to_wire(a, grid, W),
                'pred_lat': pred_lat,
                'warm': warm_label,
                'mcts_time_s': elapsed,
            }
        print(f'    [{cand_name}] pred={top[0][1]:.1f} t={elapsed:.1f}s',
              flush=True)

    # Stage 1b: BookSim-select best
    cand_eval = {}
    for name, c in cands.items():
        alloc = c['alloc']
        wire = alloc_wire_mm2(alloc, grid)
        label = f'mctsonly_{subset_key}_s{name[-3:]}'
        per_wl, mean_lat = evaluate_raw(alloc, subset, label)
        ml = f'{mean_lat:.1f}' if mean_lat is not None else 'FAIL'
        print(f'    [booksim] {name}: wire={wire:.1f} mean={ml}', flush=True)
        cand_eval[name] = {
            'alloc': {f'{p[0]}-{p[1]}': v for p, v in alloc.items()},
            'wire': wire,
            'n_links': sum(alloc.values()),
            'pred_lat': c['pred_lat'],
            'warm': c['warm'],
            'raw_per_wl': per_wl,
            'raw_mean_lat': mean_lat,
        }

    valid = {n: c for n, c in cand_eval.items()
             if c['raw_mean_lat'] is not None}
    if not valid:
        return {'K16_N4': {'candidates': cand_eval, 'selected': None,
                           'raw_mean_lat': None}}
    selected = min(valid, key=lambda n: valid[n]['raw_mean_lat'])
    print(f'  => selected={selected} mean={valid[selected]["raw_mean_lat"]:.1f}',
          flush=True)
    return {'K16_N4': {
        'W': W, 'bpp_eq': bpp_eq,
        'candidates': cand_eval,
        'selected': selected,
        'raw_mean_lat': valid[selected]['raw_mean_lat'],
        'raw_per_wl': valid[selected]['raw_per_wl'],
    }}


def compare_vs_baseline(results, baseline):
    """Report comparison vs existing RL+MCTS for each subset."""
    wins = 0
    total = 0
    for subset_key, entry in results.items():
        our = entry.get('K16_N4', {})
        our_lat = our.get('raw_mean_lat')
        if our_lat is None:
            continue
        ref = baseline.get(subset_key, {}).get('K16_N4', {})
        ref_lat = ref.get('stage1_lat')
        if ref_lat is None:
            # fallback: use best candidate raw_mean_lat from baseline
            cands = ref.get('candidates', {})
            valid_lats = [c['raw_mean_lat'] for c in cands.values()
                          if c.get('raw_mean_lat') is not None]
            ref_lat = min(valid_lats) if valid_lats else None
        if ref_lat is None:
            continue
        # ref_lat may be a dict (per-workload), compute mean
        if isinstance(ref_lat, dict):
            valid = [v for v in ref_lat.values() if v is not None]
            ref_lat = float(np.mean(valid)) if valid else None
        if ref_lat is None:
            continue
        gap = our_lat - ref_lat
        gap_pct = 100.0 * gap / ref_lat
        within = gap_pct <= 5.0
        if within:
            wins += 1
        total += 1
        marker = '✓' if within else '✗'
        print(f'  {marker} {subset_key:40s}: ours={our_lat:.1f}  '
              f'ref={ref_lat:.1f}  gap={gap_pct:+.1f}%', flush=True)
    print(f'\nResult: {wins}/{total} within 5% of RL+MCTS combo '
          f'(need ≥9 to proceed)', flush=True)
    return wins, total


def main():
    if OUT_PATH.exists():
        try:
            results = json.loads(OUT_PATH.read_text())
            print(f'Resuming from {OUT_PATH}', flush=True)
        except Exception:
            results = {}
    else:
        results = {}

    baseline = {}
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text())
        except Exception:
            pass

    surrogate = load_surrogate_v3()
    overall_t0 = time.time()

    for subset in SUBSETS:
        subset_key = '+'.join(subset)
        if (subset_key in results
                and results[subset_key].get('K16_N4', {}).get('selected')):
            print(f'[skip] {subset_key}', flush=True)
            continue
        print(f'\n=== {subset_key} ===', flush=True)
        t0 = time.time()
        entry = run_subset(subset, surrogate, subset_key)
        results[subset_key] = entry
        OUT_PATH.write_text(json.dumps(results, indent=2))
        print(f'  Done in {(time.time() - t0) / 60:.1f} min', flush=True)

    elapsed_h = (time.time() - overall_t0) / 3600
    print(f'\n=== ALL SUBSETS DONE in {elapsed_h:.1f} h ===', flush=True)

    print('\n--- Comparison vs RL+MCTS baseline ---', flush=True)
    wins, total = compare_vs_baseline(results, baseline)

    if total > 0 and wins >= 9:
        print('\n*** PILOT PASSED: proceed with full sweep_v3_mctsonly ***',
              flush=True)
    else:
        print('\n*** PILOT FAILED: consider surrogate retraining (option 3b) ***',
              flush=True)


if __name__ == '__main__':
    main()
