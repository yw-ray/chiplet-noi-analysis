"""Random and Pure-FBfly baselines on 28 cells × b=4×.

- Random: shuffle non-adj pairs (within max_dist=3), distribute budget randomly
  while respecting per-pair cap N. Mandatory adj 1 link first.
- Pure FBfly: row+col all-to-all, NO max_dist cap (long-range links allowed
  even at hop 4-7 for K=32 4×8 grid).
"""
import json
import random
import sys
import time
from pathlib import Path
from collections import defaultdict

import numpy as np

sys.path.insert(0, '.')
import ml_express_warmstart as mw

R_DIR = Path('results/ml_placement')
OUT_RANDOM = R_DIR / 'rl_random.json'
OUT_PUREFB = R_DIR / 'rl_pure_fbfly.json'


def random_alloc(grid, budget, per_pair_cap, max_dist=3, seed=42):
    rng = random.Random(seed)
    K = grid.K
    adj_pairs = list(grid.get_adj_pairs())
    alloc = defaultdict(int)
    # mandatory adj 1
    for p in adj_pairs:
        alloc[p] = 1
    used = len(adj_pairs)
    # candidate non-adj pairs
    cands = []
    for i in range(K):
        for j in range(i + 1, K):
            h = grid.get_hops(i, j)
            if 1 <= h <= max_dist:
                cands.append((i, j))
    rng.shuffle(cands)
    while used < budget:
        if not cands:
            break
        p = rng.choice(cands)
        if alloc[p] < per_pair_cap:
            alloc[p] += 1
            used += 1
        else:
            cands = [c for c in cands if alloc[c] < per_pair_cap]
            if not cands:
                break
    return dict(alloc)


def pure_fbfly_alloc(grid, budget, per_pair_cap):
    """Flattened Butterfly with NO distance cap — every pair within same
    row or column gets a link, however far."""
    R, C = grid.rows, grid.cols
    alloc = defaultdict(int)
    # mandatory adj
    for p in grid.get_adj_pairs():
        alloc[p] = 1
    used = sum(alloc.values())

    # Row pairs (any distance within same row)
    row_pairs = []
    for r in range(R):
        for ci in range(C):
            for cj in range(ci + 1, C):
                a, b = r * C + ci, r * C + cj
                if grid.get_hops(a, b) >= 2:
                    row_pairs.append((a, b))
    # Column pairs
    col_pairs = []
    for c in range(C):
        for ri in range(R):
            for rj in range(ri + 1, R):
                a, b = ri * C + c, rj * C + c
                if grid.get_hops(a, b) >= 2:
                    col_pairs.append((a, b))
    # Spend budget: row first, then col
    for p in row_pairs + col_pairs:
        if used >= budget:
            break
        if alloc[p] < per_pair_cap:
            alloc[p] += 1
            used += 1
    # Residual round-robin
    all_active = sorted(alloc.keys())
    idx = 0
    while used < budget and all_active:
        p = all_active[idx % len(all_active)]
        if alloc[p] < per_pair_cap:
            alloc[p] += 1
            used += 1
        idx += 1
        if idx > len(all_active) * per_pair_cap * 2:
            break
    return dict(alloc)


def evaluate_method(method_name, alloc_fn, out_file):
    cells = []
    cells_to_run = []
    for K in [16, 32]:
        for N in [4, 8]:
            for wl in ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all',
                       'tree_allreduce', 'ring_allreduce', 'pipeline_parallel']:
                cells_to_run.append((wl, K, N, 4))

    existing = json.load(open(out_file)) if out_file.exists() else []
    done_keys = set((r['workload'], r['K'], r['N'], r['budget_per_pair']) for r in existing)

    for wl, K, N, bpp in cells_to_run:
        if (wl, K, N, bpp) in done_keys:
            continue
        t0 = time.time()
        Rg, Cg = (4, 4) if K == 16 else (4, 8)
        grid = mw.ChipletGrid(Rg, Cg)
        traffic = mw.WORKLOADS[wl](K, grid)
        n_adj = len(grid.get_adj_pairs())
        budget = n_adj * bpp
        npc = N * N
        base_rate = mw.TOTAL_LOAD_BASE / (K * npc)
        rates = [base_rate * (i + 1) for i in range(4)]

        label = f'K{K}_N{N}_bpp{bpp}'
        traf = f'traffic_{method_name}_{wl}_{label}.txt'
        mw.gen_traffic_matrix(grid, traffic, npc, mw.CONFIG_DIR / traf)

        alloc = alloc_fn(grid, budget, N)
        alloc_capped = {p: min(n, N) for p, n in alloc.items() if n > 0}
        cfg = f'{method_name}_{wl}_{label}'
        mw.gen_anynet_config(cfg, grid, alloc_capped, chip_n=N, outdir=mw.CONFIG_DIR)

        lats, tps = [], []
        for rate in rates:
            r = mw.run_booksim(cfg, traf, rate, timeout=900)
            lats.append(r['latency']); tps.append(r['throughput'])

        max_lat = max((x for x in lats if x is not None), default=float('inf'))
        record = {
            'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp,
            'rates': rates, 'latency': lats, 'throughput': tps,
            'max_latency': max_lat,
            'elapsed_s': time.time() - t0,
        }
        existing.append(record)
        with open(out_file, 'w') as f:
            json.dump(existing, f, indent=2)
        print(f'  [{method_name}] {wl:<22s} K{K}N{N} b{bpp}: max_lat={max_lat:.1f} ({time.time()-t0:.0f}s)', flush=True)
        cells.append(record)
    return cells


def main():
    method = sys.argv[1] if len(sys.argv) > 1 else 'both'
    if method in ('random', 'both'):
        print(f'>>> Random baseline (max_dist=3)', flush=True)
        evaluate_method('rand', lambda g, b, n: random_alloc(g, b, n, max_dist=3, seed=42), OUT_RANDOM)
    if method in ('pure_fbfly', 'both'):
        print(f'>>> Pure FBfly (max_dist=infty)', flush=True)
        evaluate_method('purefb', pure_fbfly_alloc, OUT_PUREFB)


if __name__ == '__main__':
    main()
