"""V3 iso-wire sweep with MCTS Seed Injection + Intersection Backbone.

Two algorithmic additions over V3.4 (RA-surrogate):

  Seed Injection (MCTS only):
    MCTS warm-starts from two baselines — greedy_union and kite_l.
    kite_l warm-start allows MCTS to find "super-kite" solutions via UCB
    exploration. Candidates identical to the kite_l warm-start are filtered.
    RL was tested but removed: surrogate gradient always reverts RL to kite_l,
    so RL provides no benefit over MCTS on symmetric-heavy mixes.

  Intersection Backbone:
    Links present in ALL per-workload greedy allocations form a frozen backbone.
    MCTS swaps cannot reduce backbone links below 1. For dense-only mixes the
    intersection converges to a uniform spine-like structure, guiding search
    toward kite-L territory without requiring explicit structural prior injection.

Output: results/ml_placement/sweep_v3_isowire_seedinject_K{K}_N{N}.json
Baseline (V3.4): results/ml_placement/sweep_v3_isowire_K{K}_N{N}.json
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
    warm_start_union_greedy,
    warm_start_intersection_backbone,
    alloc_dict_to_vec,
    gen_workload_traffic,
)
from sweep_v2_iso_wire import (
    WIRE_AREA, alloc_wire_mm2,
    mesh_alloc_iso_wire, kite_alloc_iso_wire,
)
from sweep_v2_mask_greedy import booksim_greedy_mask, run_booksim_alloc
from baseline_gia import gia_alloc
from mcts_search import mcts_search
# Re-use Stage-2 and baseline evaluation from the original sweep driver.
from sweep_v3_isowire import (
    CELLS, SUBSETS, CELL_MASK_PARAMS,
    cap_alloc, vec_to_dict, prune_to_wire,
    gia_iso_wire,
    evaluate_raw, stage2_per_workload, evaluate_baselines,
)


SURROGATE_VARIANT = 'v2'

# MCTS config — balanced for speed vs quality across 8 candidates per combo.
MCTS_N_ITERS = 1500
MCTS_ROLLOUT_DEPTH = 12
MCTS_EXPANSION_BRANCH = 25
MCTS_ROLLOUT_BRANCH = 8

# MCTS seeds: 3 from greedy_union + 2 from kite_l warm-start.
# RL removed: surrogate gradient always reverts RL to kite_l local optimum;
# MCTS can escape via UCB exploration. Total candidates: up to 6.
MCTS_SEEDS_GREEDY = [101, 102, 103]
MCTS_SEEDS_KITEL = [104, 105]


def out_path_for(cell_idx):
    if cell_idx is None:
        return RESULTS_DIR / 'sweep_v3_isowire_seedinject_v3.json'
    K, N, _, _, _ = CELLS[cell_idx]
    return RESULTS_DIR / f'sweep_v3_isowire_seedinject_v3_K{K}_N{N}.json'


def _allocs_equal(a, b):
    """Check whether two alloc dicts represent the same placement."""
    keys = set(a) | set(b)
    return all(a.get(k, 0) == b.get(k, 0) for k in keys)


def gen_candidates_seedinject(subset, K, N, R, C, W, surrogate):
    """Generate candidate supersets with Seed Injection + Intersection Backbone."""
    grid = ChipletGrid(R, C)
    n_adj = len(grid.get_adj_pairs())
    adj_set = set(grid.get_adj_pairs())
    bpp_eq = max(2, int(W / (WIRE_AREA[1] * n_adj)) + 1)
    budget = n_adj * bpp_eq
    all_pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    workload_traffics = gen_workload_traffic(list(subset), K, grid)

    # ── Greedy union warm-start ──────────────────────────────────────────────
    gv = warm_start_union_greedy(
        workload_traffics, grid, budget, max_dist=3,
        max_lpp=N, all_pairs=all_pairs, pair_to_idx=pair_to_idx,
    )
    g_alloc = cap_alloc(vec_to_dict(gv, all_pairs), N)
    greedy_union_pruned = prune_to_wire(g_alloc, grid, W)

    cands = {'greedy_union': greedy_union_pruned}

    # ── Intersection backbone mask ───────────────────────────────────────────
    backbone_mask = warm_start_intersection_backbone(
        workload_traffics, grid, budget, max_dist=3,
        max_lpp=N, all_pairs=all_pairs, pair_to_idx=pair_to_idx,
    )
    n_backbone = int(backbone_mask.sum())
    n_express_backbone = int((backbone_mask & ~np.array(
        [p in adj_set for p in all_pairs])).sum())
    print(f"    [backbone] {n_backbone} protected links "
          f"({n_express_backbone} express)", flush=True)

    # ── Baseline warm-start allocs (pruned to W) ─────────────────────────────
    kite_l_alloc = kite_alloc_iso_wire(grid, W, N, 'large')
    kite_l_pruned = prune_to_wire(dict(kite_l_alloc), grid, W)

    # ── MCTS shared args ─────────────────────────────────────────────────────
    hop_mask_np = np.array(
        [1 if grid.get_hops(p[0], p[1]) <= 3 else 0 for p in all_pairs],
        dtype=bool)
    mesh_protect_np = np.array(
        [1 if p in adj_set else 0 for p in all_pairs], dtype=bool)
    surrogate_args = []
    for _, traffic_flat, _ in workload_traffics:
        surrogate_args.append({
            'traffic_flat': traffic_flat,
            'adj_set': adj_set, 'all_pairs': all_pairs,
            'K': K, 'N': N, 'budget': budget, 'n_adj': n_adj,
            'rate_mult': 4.0,
        })

    # ── MCTS: greedy_union warm-start ────────────────────────────────────────
    for s in MCTS_SEEDS_GREEDY:
        torch.manual_seed(s)
        np.random.seed(s)
        top = mcts_search(
            gv.copy(), surrogate, surrogate_args,
            hop_mask_np, mesh_protect_np, N,
            n_iters=MCTS_N_ITERS,
            rollout_depth=MCTS_ROLLOUT_DEPTH,
            expansion_branch=MCTS_EXPANSION_BRANCH,
            rollout_branch=MCTS_ROLLOUT_BRANCH,
            top_k=1, seed=s, verbose=False,
            surrogate_version=SURROGATE_VARIANT,
            backbone_mask_np=backbone_mask,
        )
        if top:
            best_state, _ = top[0]
            a = cap_alloc(vec_to_dict(best_state, all_pairs), N)
            cands[f'mcts_greedy_s{s}'] = prune_to_wire(a, grid, W)

    # ── MCTS: per-workload warm-start (no backbone) ──────────────────────────
    # Each workload's independent greedy optimum is a different point on the
    # Pareto frontier. MCTS from these diverse starts explores toward the
    # multi-workload balanced optimum from directions greedy_union/kite_l miss.
    wl_names = list(subset)
    for wl_idx, single_wl_traffic in enumerate(
            [workload_traffics[i:i+1] for i in range(len(workload_traffics))]):
        wl_name = wl_names[wl_idx]
        seed = 200 + wl_idx
        torch.manual_seed(seed)
        np.random.seed(seed)
        # warm_start_union_greedy with single workload — budget-constrained vec
        per_wl_vec = warm_start_union_greedy(
            single_wl_traffic, grid, budget, max_dist=3,
            max_lpp=N, all_pairs=all_pairs, pair_to_idx=pair_to_idx,
        )
        top = mcts_search(
            per_wl_vec.copy(), surrogate, surrogate_args,
            hop_mask_np, mesh_protect_np, N,
            n_iters=MCTS_N_ITERS,
            rollout_depth=MCTS_ROLLOUT_DEPTH,
            expansion_branch=MCTS_EXPANSION_BRANCH,
            rollout_branch=MCTS_ROLLOUT_BRANCH,
            top_k=1, seed=seed, verbose=False,
            surrogate_version=SURROGATE_VARIANT,
            backbone_mask_np=None,
        )
        if top:
            best_state, _ = top[0]
            a = cap_alloc(vec_to_dict(best_state, all_pairs), N)
            cands[f'mcts_wl{wl_idx}_{wl_name[:4]}_s{seed}'] = prune_to_wire(a, grid, W)

    # ── MCTS: kite_l warm-start (no backbone — free to restructure from kite_l) ─
    # Backbone was derived from greedy allocs, not kite_l structure. Applying it
    # prevents MCTS from concentrating BPP on hotspot pairs, making results worse
    # than kite_l itself. Without backbone, MCTS can freely improve from kite_l.
    kite_l_vec = alloc_dict_to_vec(kite_l_alloc, all_pairs, pair_to_idx)
    for s in MCTS_SEEDS_KITEL:
        torch.manual_seed(s)
        np.random.seed(s)
        top = mcts_search(
            kite_l_vec.copy(), surrogate, surrogate_args,
            hop_mask_np, mesh_protect_np, N,
            n_iters=MCTS_N_ITERS,
            rollout_depth=MCTS_ROLLOUT_DEPTH,
            expansion_branch=MCTS_EXPANSION_BRANCH,
            rollout_branch=MCTS_ROLLOUT_BRANCH,
            top_k=1, seed=s, verbose=False,
            surrogate_version=SURROGATE_VARIANT,
            backbone_mask_np=None,
        )
        if top:
            best_state, _ = top[0]
            a = cap_alloc(vec_to_dict(best_state, all_pairs), N)
            pruned = prune_to_wire(a, grid, W)
            if _allocs_equal(pruned, kite_l_pruned):
                print(f"      [skip] mcts_kitel_s{s}: identical to kite_l warm-start",
                      flush=True)
                continue
            cands[f'mcts_kitel_s{s}'] = pruned

    return cands, grid, bpp_eq


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
            print(f"Resuming from {out_path}", flush=True)
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
                print(f"[skip {n_done}/{n_total}] "
                      f"{subset_key} | {cell_key} | W={W:.0f}", flush=True)
                continue

            t_combo = time.time()
            print(f"\n=== [{n_done+1}/{n_total}] "
                  f"{subset_key} | {cell_key} | W={W:.0f} ===", flush=True)

            cands, grid, bpp_eq = gen_candidates_seedinject(
                subset, K, N, R, C, W, surrogate)
            print(f"  Stage 1a: {len(cands)} candidates "
                  f"(bpp_eq={bpp_eq}, "
                  f"{(time.time() - t_combo) / 60:.1f} min)",
                  flush=True)

            cand_eval = {}
            for name, alloc in cands.items():
                t_e = time.time()
                wire = alloc_wire_mm2(alloc, grid)
                n_links = sum(alloc.values())
                label = (f'v3si_{cell_key}_W{int(W)}_'
                         f'{subset_key}_{name}')
                per_wl, mean_lat = evaluate_raw(
                    alloc, K, N, R, C, subset, label)
                ml_str = (f'{mean_lat:.1f}'
                          if mean_lat is not None else 'FAIL')
                print(f"    [cand] {name:<18}: links={n_links:>3} "
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

            selected = min(valid.keys(),
                           key=lambda n: valid[n]['raw_mean_lat'])
            print(f"  Stage 1b: selected={selected} "
                  f"(raw_mean={valid[selected]['raw_mean_lat']:.1f})",
                  flush=True)

            sel_alloc = {tuple(int(x) for x in k.split('-')): v
                         for k, v in cand_eval[selected]['alloc'].items()}
            mask_steps, mask_cands = CELL_MASK_PARAMS.get(
                cell_key, (20, 15))
            stage2 = stage2_per_workload(
                sel_alloc, K, N, R, C, subset,
                label_prefix=(f'v3si_{cell_key}_W{int(W)}_'
                              f'{subset_key}_{selected}'),
                mask_max_steps=mask_steps,
                mask_n_cands=mask_cands,
                n_parallel=8,
            )
            baselines = evaluate_baselines(
                K, N, R, C, W, subset, grid,
                label_prefix=f'v3si_{cell_key}_W{int(W)}_{subset_key}',
            )

            results[subset_key][cell_key] = {
                'W': W,
                'bpp_eq': bpp_eq,
                'candidates': cand_eval,
                'selected': selected,
                'stage1_lat': valid[selected]['raw_per_wl'],
                'stage2': stage2,
                'baselines_at_W': baselines,
            }
            out_path.write_text(json.dumps(results, indent=2))
            n_done += 1
            print(f"  Combo done in "
                  f"{(time.time() - t_combo) / 60:.1f} min "
                  f"({n_done}/{n_total})", flush=True)

    print(f"\n=== ALL DONE in "
          f"{(time.time() - overall_t0) / 3600:.1f} h ===", flush=True)
    print(f"Saved: {out_path}", flush=True)


if __name__ == '__main__':
    main()
