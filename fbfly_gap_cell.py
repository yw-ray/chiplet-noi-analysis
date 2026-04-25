"""Per-cell: measure FBfly + adj + greedy at base_rate for missing K/N × bpp.

Fills gap so FBfly line exists in 16-panel bpp_sweep figure.
Usage: .venv/bin/python3 fbfly_gap_cell.py <workload> <K> <N> <bpp>
"""
import json, sys
from pathlib import Path
import numpy as np

import ml_express_warmstart as mw
from butterfly_baseline import flattened_butterfly_alloc

OUT = Path('results/ml_placement/fbfly_gap.json')

def main():
    wl = sys.argv[1]; K = int(sys.argv[2]); N = int(sys.argv[3]); bpp = int(sys.argv[4])
    print(f'>>> FBfly gap {wl} K{K}N{N} b{bpp}x', flush=True)

    R, C = (4, 4) if K == 16 else (4, 8)
    grid = mw.ChipletGrid(R, C)
    traffic = mw.WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs()
    n_adj = len(adj_pairs)
    budget = int(n_adj * bpp)
    npc = N * N
    base_rate = mw.TOTAL_LOAD_BASE / (K * npc)

    label = f'K{K}_N{N}_bpp{bpp}'
    traf = f'traffic_fbg_{wl}_{label}.txt'
    mw.gen_traffic_matrix(grid, traffic, npc, mw.CONFIG_DIR / traf)

    per = budget // n_adj; res = budget - per * n_adj
    adj_alloc = {p: per + (1 if i < res else 0) for i, p in enumerate(sorted(adj_pairs))}
    adj_c = {p: min(n, N) for p, n in adj_alloc.items()}
    cfg_adj = f'fbg_{wl}_{label}_adj'; mw.gen_anynet_config(cfg_adj, grid, adj_c, chip_n=N, outdir=mw.CONFIG_DIR)

    max_dist = max(2, min(3, max(R, C) - 1))
    g_alloc = mw.alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    g_c = {p: min(n, N) for p, n in g_alloc.items()}
    cfg_g = f'fbg_{wl}_{label}_greedy'; mw.gen_anynet_config(cfg_g, grid, g_c, chip_n=N, outdir=mw.CONFIG_DIR)

    fb_alloc = flattened_butterfly_alloc(grid, budget, per_pair_cap=N, max_dist=max_dist)
    fb_c = {p: min(n, N) for p, n in fb_alloc.items()}
    cfg_fb = f'fbg_{wl}_{label}_fbfly'; mw.gen_anynet_config(cfg_fb, grid, fb_c, chip_n=N, outdir=mw.CONFIG_DIR)

    L_adj = mw.run_booksim(cfg_adj, traf, base_rate, timeout=900)['latency']
    L_g = mw.run_booksim(cfg_g, traf, base_rate, timeout=900)['latency']
    L_fb = mw.run_booksim(cfg_fb, traf, base_rate, timeout=900)['latency']
    print(f'  L_adj={L_adj} L_greedy={L_g} L_fbfly={L_fb}', flush=True)

    result = {
        'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp,
        'L_adj': L_adj, 'L_greedy': L_g, 'L_fbfly': L_fb,
        'fbfly_n_express_pairs': sum(1 for p,n in fb_alloc.items() if p not in set(adj_pairs) and n > 0),
    }
    existing = json.load(open(OUT)) if OUT.exists() else []
    existing = [r for r in existing if (r['workload'], r['K'], r['N'], r['budget_per_pair']) != (wl, K, N, bpp)]
    existing.append(result)
    with open(OUT, 'w') as f: json.dump(existing, f, indent=2)
    print(f'>>> DONE', flush=True)

if __name__ == '__main__':
    main()
