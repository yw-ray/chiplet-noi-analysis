"""V3 iso-wire main sweep.

Per (cell, subset) at fixed deployed wire W:
  Stage 1a — generate candidate supersets, all post-pruned to wire ≤ W:
              greedy_union, rl_seed{42,43,44,45,46}.
  Stage 1b — BookSim raw evaluate each candidate on the workload mix,
              pick measured-best by mean raw latency.
  Stage 2  — booksim_greedy_mask per workload from selected superset.
              Reinterpreted: deactivates a subset of already-deployed
              links → reduces active link count → power saving on the
              same deployed wire W.
  Baselines @ W — mesh, kite_s, kite_m, kite_l, gia (each iso-wire to W).

Output: results/ml_placement/sweep_v3_isowire.json

Single deployed W per cell (main eval): K=16 → 240 mm², K=32 → 520 mm².
PARL is excluded.
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
    WIRE_AREA, alloc_wire_mm2,
    mesh_alloc_iso_wire, kite_alloc_iso_wire,
)
from sweep_v2_mask_greedy import booksim_greedy_mask, run_booksim_alloc
from baseline_gia import gia_alloc


ALL_WORKLOADS = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']
SUBSETS = []
for k in [2, 3, 4]:
    for combo in itertools.combinations(ALL_WORKLOADS, k):
        SUBSETS.append(combo)

# (K, N, R, C, W_mm²) — single W per cell main eval.
# K32_N8 first (largest, most likely to expose surrogate fragility).
CELLS = [
    (32, 8, 4, 8, 520.0),
    (16, 8, 4, 4, 240.0),
    (32, 4, 4, 8, 520.0),
    (16, 4, 4, 4, 240.0),
]

RL_SEEDS = [42, 43, 44, 45, 46]
RL_EPISODES = 200
MASK_MAX_STEPS = 3
MASK_N_CANDIDATES = 6

OUT_PATH = RESULTS_DIR / 'sweep_v3_isowire.json'


def vec_to_dict(vec, all_pairs):
    return {p: int(vec[i]) for i, p in enumerate(all_pairs) if vec[i] > 0}


def cap_alloc(alloc, N):
    return {p: min(int(n), N) for p, n in alloc.items() if n > 0}


def prune_to_wire(alloc, grid, W):
    """Remove links until alloc_wire_mm2 ≤ W. Mesh-protect: keep ≥ 1 hop-1
    link per adj pair. Drop hop-3 first, then hop-2, then hop-1 over-stack.
    """
    alloc = dict(alloc)
    adj_set = set(grid.get_adj_pairs())
    while alloc_wire_mm2(alloc, grid) > W:
        candidates = []
        for p, n in alloc.items():
            if n <= 0:
                continue
            hops = grid.get_hops(p[0], p[1])
            is_adj = p in adj_set
            # mesh-protect: don't go below 1 on adj pairs
            if is_adj and n <= 1:
                continue
            candidates.append((hops, p))
        if not candidates:
            break
        # remove from highest hop first; ties broken by pair order
        candidates.sort(key=lambda x: (-x[0], x[1]))
        _, p = candidates[0]
        if alloc[p] == 1:
            del alloc[p]
        else:
            alloc[p] -= 1
    return alloc


def gia_iso_wire(grid, W, N, max_dist=3):
    """GIA Fat-Tree-spine alloc, post-pruned to wire ≤ W."""
    n_adj = len(grid.get_adj_pairs())
    # Generous link budget so wire is the binding constraint.
    link_budget = max(n_adj, int(W / WIRE_AREA[1]) + 1)
    alloc = gia_alloc(grid, link_budget, per_pair_cap=N, max_dist=max_dist)
    return prune_to_wire(alloc, grid, W)


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


def gen_candidates(subset, K, N, R, C, W, surrogate):
    grid = ChipletGrid(R, C)
    n_adj = len(grid.get_adj_pairs())
    # Generous link budget so wire is binding constraint for RL/greedy.
    bpp_eq = max(2, int(W / (WIRE_AREA[1] * n_adj)) + 1)
    budget = n_adj * bpp_eq
    all_pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    cands = {}

    workload_traffics = gen_workload_traffic(list(subset), K, grid)
    gv = warm_start_union_greedy(
        workload_traffics, grid, budget, max_dist=3,
        max_lpp=N, all_pairs=all_pairs, pair_to_idx=pair_to_idx,
    )
    g_alloc = cap_alloc(vec_to_dict(gv, all_pairs), N)
    cands['greedy_union'] = prune_to_wire(g_alloc, grid, W)

    for s in RL_SEEDS:
        torch.manual_seed(s)
        np.random.seed(s)
        rl_res = train_warmstart_rl_multi(
            surrogate, list(subset), K, N, R, C, bpp_eq,
            n_episodes=RL_EPISODES, rate_mult=4.0,
            reward_type='normalized_avg', max_dist=3, verbose=False,
        )
        a = cap_alloc(rl_res['superset_alloc'], N)
        cands[f'rl_seed{s}'] = prune_to_wire(a, grid, W)

    return cands, grid, bpp_eq


def stage2_per_workload(superset, K, N, R, C, subset, label_prefix):
    """Per-workload greedy mask with strict no-degradation guard.

    Mask must satisfy mask_lat ≤ raw_lat. We pass lat_tolerance=1.0 to
    booksim_greedy_mask, then add a hard fallback: if the returned mask
    is somehow worse than raw, revert to the full superset (= no masking,
    full active wire). This makes Stage-2 a strict latency-preserving
    power knob — never worsens latency, just deactivates links when safe.
    """
    out = {}
    super_links = sum(superset.values())
    for w in subset:
        label = f'{label_prefix}_{w}'
        t0 = time.time()
        final_mask, history, raw_lat = booksim_greedy_mask(
            superset, K, N, R, C, w,
            max_steps=MASK_MAX_STEPS,
            max_candidates=MASK_N_CANDIDATES,
            lat_tolerance=1.0,
            label_prefix=label,
        )
        final_lat = history[-1]['lat'] if history else None
        reverted = False
        if (final_lat is None or raw_lat is None
                or final_lat > raw_lat):
            final_mask = dict(superset)
            final_lat = raw_lat
            reverted = True
        active_links = sum(final_mask.values()) if final_mask else 0
        active_pct = (100.0 * active_links / super_links
                      if super_links > 0 else 100.0)
        elapsed = time.time() - t0
        ml_str = (f'{final_lat:.1f}'
                  if final_lat is not None else 'FAIL')
        rev_str = ' (REVERTED)' if reverted else ''
        print(f"    [mask] {w:<14}: raw={raw_lat:.1f} mask={ml_str}"
              f"{rev_str} active={active_links}/{super_links} "
              f"({active_pct:.1f}%) ({elapsed:.1f}s)", flush=True)
        out[w] = {
            'raw_lat': raw_lat,
            'mask_lat': final_lat,
            'mask_reverted_to_raw': reverted,
            'active_link_count': active_links,
            'super_link_count': super_links,
            'active_pct': active_pct,
            'final_mask': {f'{p[0]}-{p[1]}': v
                           for p, v in final_mask.items()},
            'history': history,
        }
    return out


def evaluate_baselines(K, N, R, C, W, subset, grid, label_prefix):
    """Evaluate Mesh, Kite-S/M/L, GIA at deployed wire W."""
    bases = {
        'mesh':   mesh_alloc_iso_wire(grid, W, N),
        'kite_s': kite_alloc_iso_wire(grid, W, N, 'small'),
        'kite_m': kite_alloc_iso_wire(grid, W, N, 'medium'),
        'kite_l': kite_alloc_iso_wire(grid, W, N, 'large'),
        'gia':    gia_iso_wire(grid, W, N),
    }
    out = {}
    for name, alloc in bases.items():
        if not alloc:
            print(f"    [base] {name}: empty alloc", flush=True)
            out[name] = {'alloc': {}, 'wire': 0.0, 'lat': {}}
            continue
        capped = cap_alloc(alloc, N)
        wire = alloc_wire_mm2(capped, grid)
        n_links = sum(capped.values())
        per_wl = {}
        for w in subset:
            try:
                res = run_booksim_alloc(
                    f'{label_prefix}_{name}_{w}', capped,
                    K, N, R, C, w)
                per_wl[w] = res.get('latency')
            except Exception as exc:
                print(f"      [WARN] {name} {w}: {exc}", flush=True)
                per_wl[w] = None
        lat_str = ' '.join(
            f'{w[:4]}={per_wl[w]:.1f}' if per_wl[w] is not None
            else f'{w[:4]}=FAIL' for w in subset)
        print(f"    [base] {name:<6}: links={n_links:>3} wire={wire:>6.1f} "
              f"{lat_str}", flush=True)
        out[name] = {
            'alloc': {f'{p[0]}-{p[1]}': v for p, v in capped.items()},
            'wire': wire,
            'n_links': n_links,
            'lat': per_wl,
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
    n_total = len(SUBSETS) * len(CELLS)

    for K, N, R, C, W in CELLS:
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

            cands, grid, bpp_eq = gen_candidates(
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
                label = (f'v3iso_{cell_key}_W{int(W)}_'
                         f'{subset_key}_{name}')
                per_wl, mean_lat = evaluate_raw(
                    alloc, K, N, R, C, subset, label)
                ml_str = (f'{mean_lat:.1f}'
                          if mean_lat is not None else 'FAIL')
                print(f"    [cand] {name:<14}: links={n_links:>3} "
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
                OUT_PATH.write_text(json.dumps(results, indent=2))
                n_done += 1
                continue

            selected = min(valid.keys(),
                           key=lambda n: valid[n]['raw_mean_lat'])
            print(f"  Stage 1b: selected={selected} "
                  f"(raw_mean={valid[selected]['raw_mean_lat']:.1f})",
                  flush=True)

            sel_alloc = {tuple(int(x) for x in k.split('-')): v
                         for k, v in cand_eval[selected]['alloc'].items()}
            stage2 = stage2_per_workload(
                sel_alloc, K, N, R, C, subset,
                label_prefix=(f'v3iso_{cell_key}_W{int(W)}_'
                              f'{subset_key}_{selected}'),
            )
            baselines = evaluate_baselines(
                K, N, R, C, W, subset, grid,
                label_prefix=f'v3iso_{cell_key}_W{int(W)}_{subset_key}',
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
