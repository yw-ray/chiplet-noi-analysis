"""Cross-Entropy Method for placement search.

Maintains per-pair probability over {0, 1, ..., N}. Samples N_pop placements
each generation, selects top-k elite, updates probabilities to match elite.
"""
import json, sys, time
from pathlib import Path
import numpy as np
import torch, torch.nn as nn
import random

import ml_express_warmstart as mw
from butterfly_baseline import flattened_butterfly_alloc
from ga_placement import _repair

RESULTS_DIR = Path('results/ml_placement')
OUT_FILE = RESULTS_DIR / 'rl_cem.json'
RATE_WEIGHTS = {1.0: 1.0, 2.0: 1.0, 3.0: 1.0, 4.0: 2.0}


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


def cem_search(surrogate, traffic_flat, greedy_vec, fbfly_vec, adj_set, all_pairs,
                K, N, budget, n_adj, rate_weights, n_gens=40, pop_size=50,
                elite_frac=0.2, seed=0):
    random.seed(seed); np.random.seed(seed)
    n_pairs = len(all_pairs)
    # Init probability: avg of greedy and fbfly, softmax
    init_mean = (greedy_vec + fbfly_vec) / 2
    # Sample standard deviation
    std = np.ones(n_pairs) * 0.5 + 0.3

    def obj(vec):
        s, w = 0.0, 0.0
        for r, weight in rate_weights.items():
            p = mw.surrogate_predict_ra(surrogate, traffic_flat, vec, adj_set,
                                         all_pairs, K, N, budget, n_adj, rate_mult=r)
            s += weight * p; w += weight
        return s / max(w, 1e-9)

    best_vec = greedy_vec.copy(); best_score = obj(best_vec)
    mean = init_mean.copy()

    for gen in range(n_gens):
        # Sample population
        pop = []
        for _ in range(pop_size):
            sample = mean + std * np.random.randn(n_pairs).astype(np.float32)
            sample = np.clip(np.round(sample), 0, N)
            sample = _repair(sample, adj_set, all_pairs, N, budget, n_adj)
            pop.append(sample)
        # Also inject greedy and fbfly to pop
        pop.append(greedy_vec.copy())
        pop.append(fbfly_vec.copy())
        scores = [obj(p) for p in pop]
        # Elite
        n_elite = max(2, int(pop_size * elite_frac))
        elite_idx = np.argsort(scores)[:n_elite]
        elite = [pop[i] for i in elite_idx]
        elite_vecs = np.stack(elite)
        # Update mean/std
        mean = elite_vecs.mean(axis=0)
        std = elite_vecs.std(axis=0) + 0.3
        # Track best
        for i, s in enumerate(scores):
            if s < best_score:
                best_score = s; best_vec = pop[i].copy()
        if (gen + 1) % 10 == 0:
            print(f'      CEM gen {gen+1}: best={best_score:.2f}', flush=True)

    # Build candidate set: last elites + best + greedy + fbfly
    final_pop = elite[:] + [best_vec, greedy_vec.copy(), fbfly_vec.copy()]
    seen = set(); out = []
    for v in final_pop:
        key = v.tobytes()
        if key in seen: continue
        seen.add(key)
        out.append((v, obj(v)))
    return sorted(out, key=lambda x: x[1])


def main():
    wl = sys.argv[1]; K = int(sys.argv[2]); N = int(sys.argv[3]); bpp = int(sys.argv[4])
    print(f'>>> CEM {wl} K{K}N{N} b{bpp}x', flush=True)
    t0 = time.time()
    R, C = (4, 4) if K == 16 else (4, 8)
    grid = mw.ChipletGrid(R, C); traffic = mw.WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs(); adj_set = set(adj_pairs)
    n_adj = len(adj_pairs); budget = int(n_adj * bpp)
    npc = N * N; base_rate = mw.TOTAL_LOAD_BASE / (K * npc)
    rates = [base_rate * (i + 1) for i in range(4)]
    all_pairs = [(i, j) for i in range(K) for j in range(i+1, K)]
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}
    label = f'K{K}_N{N}_bpp{bpp}'; traf = f'traffic_cem_{wl}_{label}.txt'
    mw.gen_traffic_matrix(grid, traffic, npc, mw.CONFIG_DIR / traf)

    per = budget // n_adj; res = budget - per * n_adj
    adj_c = {p: min(per + (1 if i < res else 0), N) for i, p in enumerate(sorted(adj_pairs))}
    cfg_adj = f'cem_{wl}_{label}_adj'; mw.gen_anynet_config(cfg_adj, grid, adj_c, chip_n=N, outdir=mw.CONFIG_DIR)
    max_dist = max(2, min(3, max(R, C) - 1))
    g_alloc = mw.alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    g_c = {p: min(n, N) for p, n in g_alloc.items()}
    cfg_g = f'cem_{wl}_{label}_greedy'; mw.gen_anynet_config(cfg_g, grid, g_c, chip_n=N, outdir=mw.CONFIG_DIR)
    fb_alloc = flattened_butterfly_alloc(grid, budget, per_pair_cap=N, max_dist=max_dist)
    fb_c = {p: min(n, N) for p, n in fb_alloc.items()}
    cfg_fb = f'cem_{wl}_{label}_fbfly'; mw.gen_anynet_config(cfg_fb, grid, fb_c, chip_n=N, outdir=mw.CONFIG_DIR)

    def dict_to_vec(d):
        v = np.zeros(len(all_pairs), dtype=np.float32)
        for p, n in d.items(): v[pair_to_idx[p]] = n
        return v
    g_vec = dict_to_vec(g_c); fb_vec = dict_to_vec(fb_c)

    t_max = traffic.max(); t_norm = traffic / t_max if t_max > 0 else traffic
    traffic_flat = t_norm[np.triu_indices(K, k=1)].astype(np.float32)

    surrogate = load_surrogate_v2()
    all_cands = []
    for seed in [42, 43, 44, 45, 46]:
        top = cem_search(surrogate, traffic_flat, g_vec, fb_vec, adj_set, all_pairs,
                          K, N, budget, n_adj, RATE_WEIGHTS,
                          n_gens=40, pop_size=50, elite_frac=0.2, seed=seed)
        for v, s in top[:6]:
            all_cands.append((seed, v, s))
    print(f'    Generated {len(all_cands)} CEM candidates', flush=True)

    candidates = []
    for idx, (seed, v, s) in enumerate(all_cands):
        alloc = {p: min(int(v[i]), N) for i, p in enumerate(all_pairs) if v[i] > 0}
        cfg = f'cem_{wl}_{label}_s{seed}_c{idx % 6}'
        mw.gen_anynet_config(cfg, grid, alloc, chip_n=N, outdir=mw.CONFIG_DIR)
        candidates.append((f's{seed}_c{idx % 6}', alloc, cfg, s))

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
    for tag, alloc, cfg, s in candidates:
        lats, tps = [], []
        for rate in rates:
            r = mw.run_booksim(cfg, traf, rate, timeout=900)
            lats.append(r['latency']); tps.append(r['throughput'])
        result['candidates'][tag] = {'latency': lats, 'throughput': tps, 'score': float(s)}
    result['candidates']['baseline_greedy'] = result['greedy'].copy()
    result['candidates']['baseline_fbfly'] = result['fbfly'].copy()

    best_tag = min(result['candidates'].keys(), key=lambda t: max(result['candidates'][t]['latency']))
    best = result['candidates'][best_tag]
    result['ours_cem'] = {'latency': best['latency'], 'throughput': best['throughput'], 'best_candidate': best_tag}
    print(f'    ours_cem: best={best_tag}, max={max(best["latency"]):.1f}, dt={time.time()-t0:.0f}s', flush=True)

    existing = json.load(open(OUT_FILE)) if OUT_FILE.exists() else []
    existing = [r for r in existing if (r['workload'], r['K'], r['N'], r['budget_per_pair']) != (wl, K, N, bpp)]
    existing.append(result)
    with open(OUT_FILE, 'w') as f: json.dump(existing, f, indent=2)
    print('>>> DONE', flush=True)


if __name__ == '__main__':
    main()
