"""Run GA placement search per cell.

Uses surrogate v2 as fitness evaluator + BookSim to pick best among top-K.

Usage: .venv/bin/python3 run_ga.py <workload> <K> <N> <bpp>
"""
import json, sys, time
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn

import ml_express_warmstart as mw
from butterfly_baseline import flattened_butterfly_alloc
from ga_placement import ga_search

RESULTS_DIR = Path('results/ml_placement')
OUT_FILE = RESULTS_DIR / 'rl_ga.json'

RATE_WEIGHTS = {1.0: 1.0, 2.0: 1.0, 3.0: 1.0, 4.0: 2.0}
TOP_K_BOOKSIM = 8  # evaluate top-8 candidates with BookSim


def load_surrogate_v2():
    class RAv2(nn.Module):
        def __init__(self, input_dim=501, hidden=256):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, hidden), nn.ReLU(), nn.LayerNorm(hidden),
                nn.Linear(hidden, hidden), nn.ReLU(), nn.LayerNorm(hidden),
                nn.Linear(hidden, 64), nn.ReLU(), nn.Linear(64, 1))
        def forward(self, x): return self.net(x).squeeze(-1)
    m = RAv2(501).to(mw.DEVICE)
    m.load_state_dict(torch.load(RESULTS_DIR / 'surrogate_rate_aware_v2.pt', map_location=mw.DEVICE))
    m.eval(); return m


def main():
    wl = sys.argv[1]; K = int(sys.argv[2]); N = int(sys.argv[3]); bpp = int(sys.argv[4])
    print(f'>>> GA {wl} K{K}N{N} b{bpp}x', flush=True)
    t0 = time.time()
    R, C = (4, 4) if K == 16 else (4, 8)
    grid = mw.ChipletGrid(R, C); traffic = mw.WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs(); adj_set = set(adj_pairs)
    n_adj = len(adj_pairs); budget = int(n_adj * bpp)
    npc = N * N; base_rate = mw.TOTAL_LOAD_BASE / (K * npc)
    rates = [base_rate * (i + 1) for i in range(4)]
    all_pairs = [(i, j) for i in range(K) for j in range(i+1, K)]

    label = f'K{K}_N{N}_bpp{bpp}'
    traf = f'traffic_ga_{wl}_{label}.txt'
    mw.gen_traffic_matrix(grid, traffic, npc, mw.CONFIG_DIR / traf)

    # Baselines
    per = budget // n_adj; res = budget - per * n_adj
    adj_c = {p: min(per + (1 if i < res else 0), N) for i, p in enumerate(sorted(adj_pairs))}
    cfg_adj = f'ga_{wl}_{label}_adj'; mw.gen_anynet_config(cfg_adj, grid, adj_c, chip_n=N, outdir=mw.CONFIG_DIR)
    max_dist = max(2, min(3, max(R, C) - 1))
    g_alloc = mw.alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    g_c = {p: min(n, N) for p, n in g_alloc.items()}
    cfg_g = f'ga_{wl}_{label}_greedy'; mw.gen_anynet_config(cfg_g, grid, g_c, chip_n=N, outdir=mw.CONFIG_DIR)
    fb_alloc = flattened_butterfly_alloc(grid, budget, per_pair_cap=N, max_dist=max_dist)
    fb_c = {p: min(n, N) for p, n in fb_alloc.items()}
    cfg_fb = f'ga_{wl}_{label}_fbfly'; mw.gen_anynet_config(cfg_fb, grid, fb_c, chip_n=N, outdir=mw.CONFIG_DIR)

    # Traffic features
    t_max = traffic.max()
    t_norm = traffic / t_max if t_max > 0 else traffic
    traffic_flat = t_norm[np.triu_indices(K, k=1)].astype(np.float32)

    # GA search
    surrogate = load_surrogate_v2()
    print(f'    Running GA (5 seeds, 100 gens each)...', flush=True)
    all_results = []
    for seed in [42, 43, 44, 45, 46]:
        top = ga_search(surrogate, traffic_flat, g_c, fb_c,
                         adj_set, all_pairs, K, N, budget, n_adj,
                         rate_weights=RATE_WEIGHTS,
                         n_generations=100, pop_size=40, elitism=4,
                         mutation_prob=0.3, seed=seed,
                         surrogate_predict_ra_fn=mw.surrogate_predict_ra)
        for v, score in top[:TOP_K_BOOKSIM]:
            all_results.append((seed, v, score))

    print(f'    Generated {len(all_results)} GA candidates (5 seeds × top-{TOP_K_BOOKSIM})', flush=True)

    # Generate BookSim configs for all GA candidates
    candidates = []  # (tag, alloc_dict, cfg)
    for idx, (seed, v, score) in enumerate(all_results):
        alloc = {}
        for i, p in enumerate(all_pairs):
            if v[i] > 0:
                alloc[p] = min(int(v[i]), N)
        cfg = f'ga_{wl}_{label}_s{seed}_c{idx % TOP_K_BOOKSIM}'
        mw.gen_anynet_config(cfg, grid, alloc, chip_n=N, outdir=mw.CONFIG_DIR)
        candidates.append((f's{seed}_c{idx % TOP_K_BOOKSIM}', alloc, cfg, score))

    # Measure baselines
    result = {'workload': wl, 'K': K, 'N': N, 'budget_per_pair': bpp, 'rates': rates,
              'adj_uniform': {'latency': [], 'throughput': []},
              'greedy': {'latency': [], 'throughput': []},
              'fbfly': {'latency': [], 'throughput': []},
              'candidates': {}}
    for method, cfg in [('adj_uniform', cfg_adj), ('greedy', cfg_g), ('fbfly', cfg_fb)]:
        for rate in rates:
            r = mw.run_booksim(cfg, traf, rate, timeout=900)
            result[method]['latency'].append(r['latency'])
            result[method]['throughput'].append(r['throughput'])
        print(f'    {method}: max={max(result[method]["latency"]):.1f}', flush=True)

    # Measure GA candidates
    for tag, alloc, cfg, score in candidates:
        lats, tps = [], []
        for rate in rates:
            r = mw.run_booksim(cfg, traf, rate, timeout=900)
            lats.append(r['latency']); tps.append(r['throughput'])
        result['candidates'][tag] = {'latency': lats, 'throughput': tps, 'surrogate_score': float(score)}

    # Also include greedy and fbfly baselines as "candidates" for the final best-pick
    # (this guarantees ≤ min(greedy, fbfly) by construction)
    result['candidates']['baseline_greedy'] = result['greedy'].copy()
    result['candidates']['baseline_fbfly'] = result['fbfly'].copy()

    best_tag = min(result['candidates'].keys(),
                    key=lambda t: max(result['candidates'][t]['latency']))
    best = result['candidates'][best_tag]
    result['ours_ga'] = {'latency': best['latency'], 'throughput': best['throughput'], 'best_candidate': best_tag}
    dt = time.time() - t0
    print(f'    ours_ga: best={best_tag}, max={max(best["latency"]):.1f}, dt={dt:.0f}s', flush=True)

    existing = json.load(open(OUT_FILE)) if OUT_FILE.exists() else []
    existing = [r for r in existing if (r['workload'], r['K'], r['N'], r['budget_per_pair']) != (wl, K, N, bpp)]
    existing.append(result)
    with open(OUT_FILE, 'w') as f: json.dump(existing, f, indent=2)
    print(f'>>> DONE', flush=True)


if __name__ == '__main__':
    main()
