"""Flattened Butterfly (FBfly) baseline for chiplet NoI.

FBfly augments the mesh with row- and column-wise all-to-all connectivity:
every pair of chiplets in the same row (and in the same column) has a
direct link. For a grid of R x C chiplets this contributes:
    - R * C(C-1)/2 row links
    - C * R(R-1)/2 column links
plus the mandatory adjacent links in the base mesh.

We compare FBfly against greedy express placement and our RL-WS+fallback on
the same 4 best-budget K=32 N=8 cells that the lambda-sensitivity experiment
uses. To make the comparison iso-budget, we allocate FBfly's non-adjacent
links within the same total budget L = bpp * n_adj. If FBfly's full
row/column plan exceeds the budget, we prune column links first (keeping
row links because row-first XY routing benefits from them); if the full
plan fits, remaining budget is distributed to adjacent pairs. This gives
FBfly the SAME total number of links as greedy/RL-WS, so the comparison
tests placement quality, not wire-count.
"""
import json
import time
from pathlib import Path
from collections import defaultdict

import numpy as np

import ml_express_warmstart as mw
from ml_express_warmstart import (
    ChipletGrid, WORKLOADS, alloc_express_greedy, gen_traffic_matrix,
    gen_anynet_config, run_booksim, CONFIG_DIR, TOTAL_LOAD_BASE,
)

RESULTS_DIR = Path('results/ml_placement')
OUT_FILE = RESULTS_DIR / 'butterfly_baseline.json'

# Same 4 best-budget cells as lambda_sensitivity
CELLS = [
    ('tree_allreduce', 32, 8, 2),
    ('hybrid_tp_pp', 32, 8, 4),
    ('uniform_random', 32, 8, 4),
    ('moe', 32, 8, 4),
]


def flattened_butterfly_alloc(grid: ChipletGrid, budget: int, per_pair_cap: int,
                              max_dist: int = 3):
    """Build a flattened-butterfly allocation capped at 'budget' total links.

    IMPORTANT: Non-adjacent pairs are restricted to Manhattan distance <= max_dist
    to match the same action space as the greedy express placer. Without this
    cap, FBfly would be allowed to use long-range links (e.g., distance 7 in a
    4x8 grid) that greedy is forbidden from placing, making the comparison
    unfair on action space rather than allocation policy.

    Priority order under tight budget:
        1. Mandatory adjacent: every hop-1 pair gets 1 link (connectivity).
        2. Row all-to-all: every (i,j) with same row, 2 <= hop <= max_dist.
        3. Column all-to-all: every (i,j) with same column, 2 <= hop <= max_dist.
        4. Remaining budget: add more capacity to existing links round-robin,
           respecting per-pair cap.
    """
    R, C = grid.rows, grid.cols
    alloc = defaultdict(int)

    # 1. Mandatory adjacent
    for (a, b) in grid.get_adj_pairs():
        alloc[(a, b)] += 1

    # 2. Row pairs (same row, 2 <= hop <= max_dist)
    row_pairs = []
    for r in range(R):
        row_chiplets = [r * C + c for c in range(C)]
        for i in range(len(row_chiplets)):
            for j in range(i + 1, len(row_chiplets)):
                a, b = row_chiplets[i], row_chiplets[j]
                h = grid.get_hops(a, b)
                if 2 <= h <= max_dist:
                    row_pairs.append((a, b))

    # 3. Column pairs (same col, 2 <= hop <= max_dist)
    col_pairs = []
    for c in range(C):
        col_chiplets = [r * C + c for r in range(R)]
        for i in range(len(col_chiplets)):
            for j in range(i + 1, len(col_chiplets)):
                a, b = col_chiplets[i], col_chiplets[j]
                h = grid.get_hops(a, b)
                if 2 <= h <= max_dist:
                    col_pairs.append((a, b))

    # Spend remaining budget: row first, then column, at 1 link each (capped)
    used = sum(alloc.values())
    for p in row_pairs + col_pairs:
        if used >= budget:
            break
        if alloc[p] < per_pair_cap:
            alloc[p] += 1
            used += 1

    # 4. Residual: distribute to remaining pairs round-robin, respecting cap
    all_touched = list(alloc.keys())
    idx = 0
    while used < budget and all_touched:
        p = all_touched[idx % len(all_touched)]
        if alloc[p] < per_pair_cap:
            alloc[p] += 1
            used += 1
        idx += 1
        # Safety: avoid infinite loop if everything capped
        if all(alloc[q] >= per_pair_cap for q in all_touched):
            break

    return dict(alloc)


def run_one(wl, K, N, bpp):
    R, C = (4, 4) if K == 16 else (4, 8)
    grid = ChipletGrid(R, C)
    traffic = WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    n_adj = len(adj_pairs)
    budget = int(n_adj * bpp)
    npc = N * N
    base_rate = TOTAL_LOAD_BASE / (K * npc)

    label = f'K{K}_N{N}_bpp{bpp}'
    traf_file = f'traffic_fbfly_{wl}_{label}.txt'
    gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

    # adj_uniform (for saving% baseline)
    per_adj = budget // n_adj
    residual = budget - per_adj * n_adj
    adj_alloc = {p: per_adj + (1 if i < residual else 0)
                  for i, p in enumerate(sorted(adj_pairs))}
    adj_capped = {p: min(n, N) for p, n in adj_alloc.items()}
    cfg_adj = f'fbfly_{wl}_{label}_adj'
    gen_anynet_config(cfg_adj, grid, adj_capped, chip_n=N, outdir=CONFIG_DIR)
    L_adj = run_booksim(cfg_adj, traf_file, base_rate, timeout=900)['latency']

    # greedy express (reference)
    max_dist = max(2, min(3, max(R, C) - 1))
    greedy_alloc = alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}
    cfg_g = f'fbfly_{wl}_{label}_greedy'
    gen_anynet_config(cfg_g, grid, greedy_capped, chip_n=N, outdir=CONFIG_DIR)
    L_g = run_booksim(cfg_g, traf_file, base_rate, timeout=900)['latency']

    # Flattened Butterfly (iso-budget, iso-max_dist with greedy)
    fb_alloc = flattened_butterfly_alloc(grid, budget, per_pair_cap=N,
                                          max_dist=max_dist)
    fb_capped = {p: min(n, N) for p, n in fb_alloc.items()}
    cfg_fb = f'fbfly_{wl}_{label}_fbfly'
    gen_anynet_config(cfg_fb, grid, fb_capped, chip_n=N, outdir=CONFIG_DIR)
    L_fb = run_booksim(cfg_fb, traf_file, base_rate, timeout=900)['latency']

    n_adj_links = sum(n for p, n in fb_alloc.items() if p in adj_set)
    n_exp_links = sum(n for p, n in fb_alloc.items() if p not in adj_set)

    return {
        'L_adj': L_adj, 'L_greedy': L_g, 'L_fbfly': L_fb,
        'fbfly_n_adj_links': n_adj_links,
        'fbfly_n_express_links': n_exp_links,
        'fbfly_n_express_pairs': sum(1 for p, n in fb_alloc.items()
                                      if p not in adj_set and n > 0),
    }


def main():
    print('=== Flattened Butterfly baseline ===', flush=True)

    existing = []
    if OUT_FILE.exists():
        existing = json.load(open(OUT_FILE))
    done = {(r['workload'], r['K'], r['N'], r['budget_per_pair']) for r in existing}
    out = list(existing)

    for (wl, K, N, bpp) in CELLS:
        key = (wl, K, N, bpp)
        if key in done:
            print(f'SKIP {key}', flush=True)
            continue
        print(f'\n>>> {wl} K{K}N{N} b{bpp}x', flush=True)
        try:
            t0 = time.time()
            res = run_one(wl, K, N, bpp)
            dt = time.time() - t0
            res.update({'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp,
                         'run_time': dt})
            out.append(res)
            with open(OUT_FILE, 'w') as f:
                json.dump(out, f, indent=2)
            L_adj, L_g, L_fb = res['L_adj'], res['L_greedy'], res['L_fbfly']
            sv_g = (L_adj - L_g) / L_adj * 100 if L_adj and L_g else None
            sv_fb = (L_adj - L_fb) / L_adj * 100 if L_adj and L_fb else None
            print(f'    L_adj={L_adj} L_greedy={L_g} L_fbfly={L_fb}', flush=True)
            print(f'    greedy_sv={sv_g:+.2f}%  fbfly_sv={sv_fb:+.2f}%', flush=True)
            print(f'    FBfly uses n_adj={res["fbfly_n_adj_links"]} '
                  f'n_express={res["fbfly_n_express_links"]} '
                  f'n_express_pairs={res["fbfly_n_express_pairs"]}', flush=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f'    ERROR: {e}', flush=True)

    print(f'\nDone. Wrote {OUT_FILE}', flush=True)


if __name__ == '__main__':
    main()
