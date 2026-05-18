"""Test MCTS on cell 3 (K16_N8 W=240 moe+u+a2a) — the worst regression cell.

Target: kite_l mean lat ~61. Pilot RL ceiling was 82.8 (round 4 BookSim
in-loop). MCTS attempts to break that ceiling by exploring more diverse
trajectories from the same surrogate.

Sequence:
  1. Compute warm-start = greedy_union for the subset.
  2. Run MCTS (n_iters=2000, rollout_depth=15) → top 5 candidate states.
  3. BookSim-evaluate each candidate on the 3 workloads.
  4. Report mean and per-workload latencies.
"""

import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from ml_express_warmstart import (
    RESULTS_DIR, load_rate_aware_surrogate,
)
from run_rl_multi_workload import (
    gen_workload_traffic, warm_start_union_greedy,
)
from sweep_v2_mask_greedy import run_booksim_alloc
from sweep_v2_iso_wire import (
    WIRE_AREA, alloc_wire_mm2, kite_alloc_iso_wire,
)
from mcts_search import mcts_search


CELL = {
    'subset': ('moe', 'uniform_random', 'all_to_all'),
    'K': 16, 'N': 8, 'R': 4, 'C': 4,
    'W': 240.0,  # the W from main eval that gave ours 178 vs kite_l 61
}


def cap_alloc(alloc, N):
    return {p: min(int(n), N) for p, n in alloc.items() if n > 0}


def vec_to_dict(vec, all_pairs):
    return {p: int(vec[i]) for i, p in enumerate(all_pairs) if vec[i] > 0}


def evaluate_alloc_booksim(alloc, K, N, R, C, subset, label):
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
    return per_wl, (float(np.mean(valid)) if valid else None)


def main():
    K = CELL['K']
    N = CELL['N']
    R, C = CELL['R'], CELL['C']
    W = CELL['W']
    subset = CELL['subset']

    grid = ChipletGrid(R, C)
    n_adj = len(grid.get_adj_pairs())
    adj_set = set(grid.get_adj_pairs())
    all_pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    n_pairs = len(all_pairs)
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    bpp_eq = max(2, int(W / (WIRE_AREA[1] * n_adj)) + 1)
    budget = n_adj * bpp_eq

    hop_mask_np = np.array(
        [1 if grid.get_hops(p[0], p[1]) <= 3 else 0 for p in all_pairs],
        dtype=bool)
    mesh_protect_np = np.array(
        [1 if p in adj_set else 0 for p in all_pairs], dtype=bool)

    # Workload traffics for surrogate.
    workload_traffics = gen_workload_traffic(list(subset), K, grid)

    # Greedy_union as warm-start.
    print(">>> Computing greedy_union warm-start", flush=True)
    gv = warm_start_union_greedy(
        workload_traffics, grid, budget, max_dist=3,
        max_lpp=N, all_pairs=all_pairs, pair_to_idx=pair_to_idx,
    )
    initial_state = gv.copy()

    # Build surrogate args list (one per workload).
    surrogate = load_rate_aware_surrogate()
    surrogate_args = []
    for traffic, traffic_flat, _ in workload_traffics:
        surrogate_args.append({
            'traffic_flat': traffic_flat,
            'adj_set': adj_set,
            'all_pairs': all_pairs,
            'K': K, 'N': N, 'budget': budget, 'n_adj': n_adj,
            'rate_mult': 4.0,
        })

    # Verify warm-start in BookSim for reference.
    warm_alloc = cap_alloc(vec_to_dict(initial_state, all_pairs), N)
    print(f"\n>>> Warm-start (greedy_union) BookSim eval", flush=True)
    t0 = time.time()
    warm_per_wl, warm_mean = evaluate_alloc_booksim(
        warm_alloc, K, N, R, C, subset, 'mcts_warm')
    print(f"  greedy_union mean_raw_lat={warm_mean:.1f} "
          f"({(time.time() - t0):.1f}s)", flush=True)
    for w, v in warm_per_wl.items():
        print(f"    {w}: {v:.1f}", flush=True)

    # Reference Kite-L for context.
    kite_alloc = cap_alloc(kite_alloc_iso_wire(grid, W, N, 'large'), N)
    print(f"\n>>> Kite-L iso-wire reference", flush=True)
    kite_per_wl, kite_mean = evaluate_alloc_booksim(
        kite_alloc, K, N, R, C, subset, 'mcts_kite_l')
    print(f"  kite_l mean_raw_lat={kite_mean:.1f}", flush=True)
    for w, v in kite_per_wl.items():
        print(f"    {w}: {v:.1f}", flush=True)

    # Run MCTS.
    print(f"\n>>> MCTS search "
          f"(n_iters=2000, rollout_depth=15, top_k=5)", flush=True)
    torch.manual_seed(42)
    np.random.seed(42)
    t0 = time.time()
    top_states = mcts_search(
        initial_state, surrogate, surrogate_args,
        hop_mask_np, mesh_protect_np, N,
        n_iters=2000, rollout_depth=15,
        expansion_branch=30, rollout_branch=10,
        top_k=5, seed=42, verbose=True,
    )
    mcts_time = time.time() - t0
    print(f"  MCTS done in {mcts_time:.1f}s, "
          f"got {len(top_states)} candidates", flush=True)

    # BookSim-verify each candidate.
    print(f"\n>>> BookSim verification of top-{len(top_states)} candidates",
          flush=True)
    results = []
    for i, (state, pred_lat) in enumerate(top_states):
        alloc = cap_alloc(vec_to_dict(state, all_pairs), N)
        wire = alloc_wire_mm2(alloc, grid)
        n_links = sum(alloc.values())
        per_wl, mean_lat = evaluate_alloc_booksim(
            alloc, K, N, R, C, subset, f'mcts_top{i+1}')
        ml = f'{mean_lat:.1f}' if mean_lat is not None else 'FAIL'
        print(f"  top{i+1}: pred={pred_lat:.1f}, "
              f"links={n_links}, wire={wire:.1f}, "
              f"BookSim mean={ml}", flush=True)
        for w, v in per_wl.items():
            if v is not None:
                print(f"      {w}: {v:.1f}", flush=True)
        results.append({
            'rank': i + 1,
            'pred_lat': pred_lat,
            'n_links': n_links,
            'wire': wire,
            'per_wl': per_wl,
            'mean_lat': mean_lat,
        })

    # Summary.
    valid = [r for r in results if r['mean_lat'] is not None]
    print(f"\n=== Summary ===", flush=True)
    print(f"  warm-start (greedy_union): {warm_mean:.1f}", flush=True)
    print(f"  kite_l reference:           {kite_mean:.1f}", flush=True)
    if valid:
        best = min(valid, key=lambda r: r['mean_lat'])
        print(f"  MCTS best (top-{best['rank']}):  "
              f"{best['mean_lat']:.1f}", flush=True)
        delta_kite = best['mean_lat'] - kite_mean
        print(f"  vs kite_l: {delta_kite:+.1f} ({delta_kite / kite_mean * 100:+.0f}%)",
              flush=True)


if __name__ == '__main__':
    main()
