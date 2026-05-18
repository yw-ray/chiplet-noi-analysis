"""Collect (allocation, workload, latency) training data for surrogate v3.

Key difference from the original training data: includes the actual
alloc_flat vector (496-dim, normalized by N) in the feature, not just
bpp and express_frac. Generates diverse allocations from three methods:
  - warm_start_union_greedy (per single workload)
  - random_hop3_spine
  - random_uniform_sample

For each allocation, evaluates all 4 workloads via BookSim.

Usage (run in parallel by workload):
  python collect_surrogate_data_v2.py 0   # K16_N4
  python collect_surrogate_data_v2.py 1   # K16_N8
  python collect_surrogate_data_v2.py 2   # K32_N4
  python collect_surrogate_data_v2.py 3   # K32_N8

Output per cell:
  results/ml_placement/surrogate_data_v2_K{K}_N{N}.json
"""

import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from noi_topology_synthesis import ChipletGrid
from ml_express_warmstart import RESULTS_DIR, load_rate_aware_surrogate
from run_rl_multi_workload import gen_workload_traffic, warm_start_union_greedy
from sweep_v2_iso_wire import WIRE_AREA
from sweep_v2_mask_greedy import run_booksim_alloc
from sweep_v3_isowire import cap_alloc, prune_to_wire
from gen_random_spine import random_hop3_spine, random_uniform_sample
from cost_perf_6panel_workload import WORKLOADS

ALL_WORKLOADS = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']

# (K, N, R, C, W_main)
CELLS = [
    (16, 4, 4, 4, 240.0),
    (16, 8, 4, 4, 960.0),
    (32, 4, 4, 8, 520.0),
    (32, 8, 4, 8, 2080.0),
]

# Number of diverse allocations to generate per cell.
# K16 cells are faster (~15-20s/call); K32 are slower (~30-50s/call).
N_ALLOCS = {
    (16, 4): 500,
    (16, 8): 300,
    (32, 4): 300,
    (32, 8): 40,   # reduced: ~160s/call → 40×16=640 runs ≈ 25h at ~25/h
}

RATE_MULTS = [1.0, 2.0, 4.0, 8.0]


def vec_to_dict(vec, all_pairs):
    return {p: int(vec[i]) for i, p in enumerate(all_pairs) if vec[i] > 0}


def alloc_to_flat(alloc_dict, all_pairs, N):
    """Return normalized alloc vector (values / N), padded to 496."""
    n = len(all_pairs)
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}
    vec = np.zeros(n, dtype=np.float32)
    for p, v in alloc_dict.items():
        if p in pair_to_idx:
            vec[pair_to_idx[p]] = min(v, N) / N
    padded = vec.tolist() + [0.0] * (496 - n)
    return padded[:496]


def perturb_alloc(alloc_dict, grid, budget, N, all_pairs, adj_set, rng, n_swaps=5):
    """Randomly swap n_swaps links in an existing allocation."""
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}
    vec = np.zeros(len(all_pairs), dtype=np.float32)
    for p, v in alloc_dict.items():
        if p in pair_to_idx:
            vec[pair_to_idx[p]] = v

    for _ in range(n_swaps):
        removable = [i for i, p in enumerate(all_pairs)
                     if vec[i] > 0 and not (p in adj_set and vec[i] <= 1)]
        addable = [i for i, p in enumerate(all_pairs)
                   if grid.get_hops(p[0], p[1]) <= 3 and vec[i] < N]
        if not removable or not addable:
            break
        rem = rng.choice(removable)
        add = rng.choice(addable)
        if rem != add:
            vec[rem] -= 1
            vec[add] += 1
    return {all_pairs[i]: int(vec[i]) for i in range(len(all_pairs)) if vec[i] > 0}


def generate_diverse_allocs(K, N, R, C, W, n_allocs, rng):
    """Generate n_allocs diverse allocations for this cell.

    For K>=32, skips expensive joint-greedy warm-starts and uses only
    per-workload greedy + random methods to avoid O(n_pairs^2) slowness.
    """
    grid = ChipletGrid(R, C)
    adj_set = set(grid.get_adj_pairs())
    n_adj = len(grid.get_adj_pairs())
    bpp_eq = max(2, int(W / (WIRE_AREA[1] * n_adj)) + 1)
    budget = n_adj * bpp_eq
    all_pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    allocs = []

    # 1. Per-workload greedy warm-starts (fast, single workload)
    for wl in ALL_WORKLOADS:
        workload_traffics = gen_workload_traffic([wl], K, grid)
        gv = warm_start_union_greedy(
            workload_traffics, grid, budget, max_dist=3,
            max_lpp=N, all_pairs=all_pairs, pair_to_idx=pair_to_idx,
        )
        a = cap_alloc(vec_to_dict(gv, all_pairs), N)
        a = prune_to_wire(a, grid, W)
        allocs.append(a)

    # 2. Joint greedy warm-starts — only for K<=16 (expensive for K=32)
    if K <= 16:
        import itertools
        for k in [2, 3]:
            for combo in list(itertools.combinations(ALL_WORKLOADS, k))[:6]:
                workload_traffics = gen_workload_traffic(list(combo), K, grid)
                gv = warm_start_union_greedy(
                    workload_traffics, grid, budget, max_dist=3,
                    max_lpp=N, all_pairs=all_pairs, pair_to_idx=pair_to_idx,
                )
                a = cap_alloc(vec_to_dict(gv, all_pairs), N)
                a = prune_to_wire(a, grid, W)
                allocs.append(a)

    # 3. Random hop3 spine warm-starts
    n_rand = max(n_allocs // 2, n_allocs - len(allocs))
    for i in range(n_rand // 2):
        v = random_hop3_spine(grid, budget, N, all_pairs, pair_to_idx, adj_set,
                               seed=rng.randint(0, 99999))
        a = cap_alloc(vec_to_dict(v, all_pairs), N)
        a = prune_to_wire(a, grid, W)
        allocs.append(a)

    # 4. Random uniform sample warm-starts
    for i in range(n_rand - n_rand // 2):
        v = random_uniform_sample(grid, budget, N, all_pairs, pair_to_idx, adj_set,
                                   max_dist=3, seed=rng.randint(0, 99999))
        a = cap_alloc(vec_to_dict(v, all_pairs), N)
        a = prune_to_wire(a, grid, W)
        allocs.append(a)

    # 5. Perturbations to fill remainder (capped at 50 to avoid slowness)
    base_allocs = allocs.copy()
    n_perturb = min(n_allocs - len(allocs), 50)
    for _ in range(n_perturb):
        base = rng.choice(base_allocs)
        n_sw = rng.randint(1, 6)
        a = perturb_alloc(base, grid, budget, N, all_pairs, adj_set, rng, n_swaps=n_sw)
        a = prune_to_wire(a, grid, W)
        allocs.append(a)

    return allocs[:n_allocs], grid, all_pairs, adj_set, n_adj


def run_booksim_safe(label, alloc, K, N, R, C, workload, rate_mult):
    """BookSim with rate override. Returns latency or None."""
    try:
        res = run_booksim_alloc(f'{label}', alloc, K, N, R, C, workload,
                                 rate_mult=rate_mult)
        lat = res.get('latency')
        return float(lat) if lat is not None and lat > 0 else None
    except Exception:
        return None


def main():
    cell_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    K, N, R, C, W = CELLS[cell_idx]
    n_allocs = N_ALLOCS[(K, N)]
    out_path = RESULTS_DIR / f'surrogate_data_v2_K{K}_N{N}.json'

    if out_path.exists():
        try:
            data = json.loads(out_path.read_text())
            print(f'Resuming: {len(data)} samples already collected', flush=True)
        except Exception:
            data = []
    else:
        data = []

    rng = random.Random(12345)
    print(f'Generating {n_allocs} diverse allocations for K={K} N={N}',
          flush=True)
    allocs, grid, all_pairs, adj_set, n_adj = generate_diverse_allocs(
        K, N, R, C, W, n_allocs, rng)
    print(f'Generated {len(allocs)} allocations', flush=True)

    # Track which (alloc_hash, workload, rate) are already done.
    done_keys = set()
    for entry in data:
        done_keys.add((entry['alloc_hash'], entry['workload'], entry['rate_mult']))

    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}
    n_total = len(allocs) * len(ALL_WORKLOADS) * len(RATE_MULTS)
    n_done = len(data)
    t0_all = time.time()

    for alloc_i, alloc in enumerate(allocs):
        alloc_flat = alloc_to_flat(alloc, all_pairs, N)
        alloc_hash = hash(tuple(sorted(alloc.items())))

        for wl in ALL_WORKLOADS:
            traffic = WORKLOADS[wl](K, grid)
            traffic_flat_raw = traffic[np.triu_indices(K, k=1)]
            t_max = float(traffic_flat_raw.max())
            traffic_norm = (traffic_flat_raw / t_max).tolist() if t_max > 0 else traffic_flat_raw.tolist()
            traffic_padded = traffic_norm + [0.0] * (496 - len(traffic_norm))

            for rate_mult in RATE_MULTS:
                key = (alloc_hash, wl, rate_mult)
                if key in done_keys:
                    continue

                label = f'surv2_K{K}N{N}_a{alloc_i}_{wl}_r{rate_mult:.0f}'
                lat = run_booksim_safe(label, alloc, K, N, R, C, wl, rate_mult)

                entry = {
                    'K': K, 'N': N,
                    'workload': wl,
                    'rate_mult': rate_mult,
                    'alloc_hash': alloc_hash,
                    'alloc_flat_norm': alloc_flat,
                    'traffic_flat_norm': traffic_padded[:496],
                    'latency': lat,
                    'n_links': sum(alloc.values()),
                    'wire': sum(alloc.values()),  # proxy
                }
                data.append(entry)
                done_keys.add(key)
                n_done += 1

                elapsed = time.time() - t0_all
                rate_str = (f'{n_done / elapsed * 3600:.0f}/h'
                            if elapsed > 10 else '?/h')
                lat_str = f'{lat:.1f}' if lat is not None else 'FAIL'
                print(f'[{n_done}/{n_total}] a{alloc_i} {wl} r{rate_mult:.0f}x'
                      f' lat={lat_str} ({rate_str})', flush=True)

                # Save every 50 entries
                if n_done % 50 == 0:
                    out_path.write_text(json.dumps(data, indent=1))

    out_path.write_text(json.dumps(data, indent=1))
    valid = sum(1 for d in data if d['latency'] is not None)
    print(f'\nDone: {len(data)} total, {valid} valid latencies', flush=True)
    print(f'Saved to {out_path}', flush=True)


if __name__ == '__main__':
    main()
