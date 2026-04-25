"""Simulated Annealing for express link placement.

Different algorithm from GA/RL. Start from warm-start, random swaps with
Metropolis acceptance, cooling schedule.

Usage: .venv/bin/python3 run_sa.py <workload> <K> <N> <bpp>
"""
import json, sys, time
from pathlib import Path
import numpy as np
import random
import math
import torch
import torch.nn as nn

import ml_express_warmstart as mw
from butterfly_baseline import flattened_butterfly_alloc
from ga_placement import _repair

RESULTS_DIR = Path('results/ml_placement')
OUT_FILE = RESULTS_DIR / 'rl_sa.json'

RATE_WEIGHTS = {1.0: 1.0, 2.0: 1.0, 3.0: 1.0, 4.0: 2.0}
N_STEPS = 3000
T_INIT = 5.0
T_FINAL = 0.01
COOLING = (T_FINAL / T_INIT) ** (1.0 / N_STEPS)


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


def sa_search(surrogate, traffic_flat, start_vec, adj_set, all_pairs, K, N, budget,
               n_adj, rate_weights, n_steps=3000, T_init=5.0, T_final=0.01, seed=0):
    random.seed(seed)
    np.random.seed(seed)
    n_pairs = len(all_pairs)
    cur = start_vec.copy()
    def obj(vec):
        s = 0.0; w = 0.0
        for r, weight in rate_weights.items():
            p = mw.surrogate_predict_ra(surrogate, traffic_flat, vec, adj_set,
                                         all_pairs, K, N, budget, n_adj, rate_mult=r)
            s += weight * p; w += weight
        return s / max(w, 1e-9)
    cur_s = obj(cur)
    best = cur.copy(); best_s = cur_s
    T = T_init; cooling = (T_final / T_init) ** (1.0 / n_steps)
    history = [(cur.copy(), cur_s)]
    for step in range(n_steps):
        # Random swap
        cand = cur.copy()
        src_c = np.where(cand > 0)[0]
        dst_c = np.where(cand < N)[0]
        if len(src_c) > 0 and len(dst_c) > 0:
            src = random.choice(src_c.tolist())
            dst = random.choice(dst_c.tolist())
            if src != dst:
                cand[src] -= 1; cand[dst] += 1
        cand = _repair(cand, adj_set, all_pairs, N, budget, n_adj)
        cand_s = obj(cand)
        delta = cand_s - cur_s
        if delta < 0 or random.random() < math.exp(-delta / max(T, 1e-9)):
            cur = cand; cur_s = cand_s
            if cur_s < best_s:
                best = cur.copy(); best_s = cur_s
                history.append((best.copy(), best_s))
        T *= cooling
        if (step + 1) % 500 == 0:
            print(f'      SA step {step+1}: T={T:.3f} cur={cur_s:.2f} best={best_s:.2f}', flush=True)
    return best, best_s, history


def main():
    wl = sys.argv[1]; K = int(sys.argv[2]); N = int(sys.argv[3]); bpp = int(sys.argv[4])
    print(f'>>> SA {wl} K{K}N{N} b{bpp}x', flush=True)
    t0 = time.time()
    R, C = (4, 4) if K == 16 else (4, 8)
    grid = mw.ChipletGrid(R, C); traffic = mw.WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs(); adj_set = set(adj_pairs)
    n_adj = len(adj_pairs); budget = int(n_adj * bpp)
    npc = N * N; base_rate = mw.TOTAL_LOAD_BASE / (K * npc)
    rates = [base_rate * (i + 1) for i in range(4)]
    all_pairs = [(i, j) for i in range(K) for j in range(i+1, K)]
    pair_to_idx = {p: i for i, p in enumerate(all_pairs)}

    label = f'K{K}_N{N}_bpp{bpp}'
    traf = f'traffic_sa_{wl}_{label}.txt'
    mw.gen_traffic_matrix(grid, traffic, npc, mw.CONFIG_DIR / traf)

    per = budget // n_adj; res = budget - per * n_adj
    adj_c = {p: min(per + (1 if i < res else 0), N) for i, p in enumerate(sorted(adj_pairs))}
    cfg_adj = f'sa_{wl}_{label}_adj'; mw.gen_anynet_config(cfg_adj, grid, adj_c, chip_n=N, outdir=mw.CONFIG_DIR)
    max_dist = max(2, min(3, max(R, C) - 1))
    g_alloc = mw.alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    g_c = {p: min(n, N) for p, n in g_alloc.items()}
    cfg_g = f'sa_{wl}_{label}_greedy'; mw.gen_anynet_config(cfg_g, grid, g_c, chip_n=N, outdir=mw.CONFIG_DIR)
    fb_alloc = flattened_butterfly_alloc(grid, budget, per_pair_cap=N, max_dist=max_dist)
    fb_c = {p: min(n, N) for p, n in fb_alloc.items()}
    cfg_fb = f'sa_{wl}_{label}_fbfly'; mw.gen_anynet_config(cfg_fb, grid, fb_c, chip_n=N, outdir=mw.CONFIG_DIR)

    def dict_to_vec(d):
        v = np.zeros(len(all_pairs), dtype=np.float32)
        for p, n in d.items(): v[pair_to_idx[p]] = n
        return v

    t_max = traffic.max(); t_norm = traffic / t_max if t_max > 0 else traffic
    traffic_flat = t_norm[np.triu_indices(K, k=1)].astype(np.float32)

    surrogate = load_surrogate_v2()
    # Run SA with 6 different (start, seed) combos
    configs = [
        (g_c, 42), (g_c, 43), (g_c, 44),
        (fb_c, 50), (fb_c, 51), (fb_c, 52),
    ]
    all_cands = []
    for start_dict, seed in configs:
        start_vec = dict_to_vec(start_dict)
        best, best_s, _ = sa_search(surrogate, traffic_flat, start_vec, adj_set, all_pairs,
                                     K, N, budget, n_adj, RATE_WEIGHTS,
                                     n_steps=N_STEPS, T_init=T_INIT, T_final=T_FINAL, seed=seed)
        all_cands.append((f'start{"_g" if start_dict is g_c else "_fb"}_s{seed}', best, best_s))

    # Build configs
    candidates = []
    for tag, vec, score in all_cands:
        alloc = {p: min(int(vec[i]), N) for i, p in enumerate(all_pairs) if vec[i] > 0}
        cfg = f'sa_{wl}_{label}_{tag}'
        mw.gen_anynet_config(cfg, grid, alloc, chip_n=N, outdir=mw.CONFIG_DIR)
        candidates.append((tag, alloc, cfg, score))

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
    for tag, alloc, cfg, score in candidates:
        lats, tps = [], []
        for rate in rates:
            r = mw.run_booksim(cfg, traf, rate, timeout=900)
            lats.append(r['latency']); tps.append(r['throughput'])
        result['candidates'][tag] = {'latency': lats, 'throughput': tps, 'score': float(score)}
    # Include baselines in pool → guarantee ≤ min(greedy, fbfly)
    result['candidates']['baseline_greedy'] = result['greedy'].copy()
    result['candidates']['baseline_fbfly'] = result['fbfly'].copy()

    best_tag = min(result['candidates'].keys(), key=lambda t: max(result['candidates'][t]['latency']))
    best = result['candidates'][best_tag]
    result['ours_sa'] = {'latency': best['latency'], 'throughput': best['throughput'], 'best_candidate': best_tag}
    print(f'    ours_sa: best={best_tag}, max={max(best["latency"]):.1f}, dt={time.time()-t0:.0f}s', flush=True)

    existing = json.load(open(OUT_FILE)) if OUT_FILE.exists() else []
    existing = [r for r in existing if (r['workload'], r['K'], r['N'], r['budget_per_pair']) != (wl, K, N, bpp)]
    existing.append(result)
    with open(OUT_FILE, 'w') as f: json.dump(existing, f, indent=2)
    print('>>> DONE', flush=True)


if __name__ == '__main__':
    main()
