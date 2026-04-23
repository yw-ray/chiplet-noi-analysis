"""Sensitivity of RL-WS saving to express-link wire-delay scaling factor lambda.

We rerun BookSim with express-link latencies scaled by lambda in {1.0, 1.5, 2.0}
on the 4 best-budget K=32 cells (one per workload). The interposer wire-delay
model lat = max(2, hops*2) is scaled to lat = max(2, hops*2*lambda) only for
express links (hops >= 2); adjacent links (hops == 1, lat == 2) are left at the
baseline model.
"""
import json
import time
import subprocess
from pathlib import Path
from copy import deepcopy

import numpy as np

import ml_express_warmstart as mw
from ml_express_warmstart import CONFIG_DIR

RESULTS_DIR = Path('results/ml_placement')
OUT_FILE = RESULTS_DIR / 'lambda_sensitivity.json'
BOOKSIM = str(Path(__file__).parent / 'booksim2' / 'src' / 'booksim')

# 4 best-budget K=32 cells (one per workload, greatest saving)
CELLS = [
    ('tree_allreduce', 32, 8, 2),
    ('hybrid_tp_pp', 32, 8, 4),
    ('uniform_random', 32, 8, 4),
    ('moe', 32, 8, 4),
]
LAMBDAS = [1.0, 1.5, 2.0]


def scale_express_latency(src_anynet: Path, dst_anynet: Path, lam: float) -> None:
    """Copy anynet file, scaling latencies on inter-chiplet lines.

    In our generator (express_link_optimizer.gen_anynet_config) the intra-chiplet
    mesh is emitted as `router X node Y router Z 1` (lat=1 per hop), and the
    inter-chiplet connections as `router X router Y L` (lat = max(2, hops*2)).
    We scale only the inter-chiplet lines and only when the base latency is
    >= 4 (meaning express link at distance >= 2); adjacent inter-chiplet links
    with lat = 2 are left alone to isolate the express-scaling effect.
    """
    out_lines = []
    with open(src_anynet) as f:
        for line in f:
            tokens = line.strip().split()
            # inter-chiplet: `router X router Y L` (4 tokens)
            if len(tokens) == 5 and tokens[0] == 'router' and tokens[2] == 'router':
                try:
                    lat = int(tokens[4])
                except ValueError:
                    out_lines.append(line)
                    continue
                if lat >= 4:  # express
                    new_lat = max(2, round(lat * lam))
                    tokens[4] = str(new_lat)
                    out_lines.append(' '.join(tokens) + '\n')
                else:
                    out_lines.append(line)
            else:
                out_lines.append(line)
    with open(dst_anynet, 'w') as f:
        f.writelines(out_lines)


def run_one(wl, K, N, bpp, lam, surrogate):
    """Run greedy + RL-WS for (wl, K, N, bpp) under express-latency scaling lam."""
    R, C = (4, 4) if K == 16 else (4, 8)
    grid = mw.ChipletGrid(R, C)
    traffic = mw.WORKLOADS[wl](K, grid)
    adj_pairs = grid.get_adj_pairs()
    adj_set = set(adj_pairs)
    budget = int(len(adj_pairs) * bpp)
    npc = N * N
    base_rate = mw.TOTAL_LOAD_BASE / (K * npc)

    label = f'K{K}_N{N}_bpp{bpp}_lam{lam:.1f}'
    traf_file = f'traffic_lam_{wl}_{label}.txt'
    mw.gen_traffic_matrix(grid, traffic, npc, CONFIG_DIR / traf_file)

    # Baseline greedy anynet (lam=1.0), we scale after.
    max_dist = max(2, min(3, max(R, C) - 1))
    greedy_alloc = mw.alloc_express_greedy(grid, traffic, budget, max_dist=max_dist)
    greedy_capped = {p: min(n, N) for p, n in greedy_alloc.items()}
    cfg_g = f'lam_{wl}_{label}_greedy'
    mw.gen_anynet_config(cfg_g, grid, greedy_capped, chip_n=N, outdir=CONFIG_DIR)
    if lam != 1.0:
        scale_express_latency(CONFIG_DIR / f'{cfg_g}.anynet',
                              CONFIG_DIR / f'{cfg_g}.anynet', lam)
    L_g = mw.run_booksim(cfg_g, traf_file, base_rate, timeout=900)['latency']

    # adj_uniform reference
    n_adj = len(adj_pairs)
    adj_alloc = {p: budget // n_adj for p in adj_pairs}
    extra = budget - sum(adj_alloc.values())
    sorted_pairs = sorted(adj_pairs)
    for i in range(extra):
        adj_alloc[sorted_pairs[i % len(sorted_pairs)]] += 1
    adj_capped = {p: min(n, N) for p, n in adj_alloc.items()}
    cfg_a = f'lam_{wl}_{label}_adj'
    mw.gen_anynet_config(cfg_a, grid, adj_capped, chip_n=N, outdir=CONFIG_DIR)
    # adj_uniform has NO express links, so lambda scaling is a no-op but we
    # still call scale_express_latency for parity (it will not find any
    # inter-chiplet lat >= 4 lines).
    if lam != 1.0:
        scale_express_latency(CONFIG_DIR / f'{cfg_a}.anynet',
                              CONFIG_DIR / f'{cfg_a}.anynet', lam)
    L_adj = mw.run_booksim(cfg_a, traf_file, base_rate, timeout=900)['latency']

    # RL-WS (single seed, reuses the main-experiment trained path)
    t0 = time.time()
    rl_alloc, _, _ = mw.train_warmstart_rl(
        surrogate, wl, K, N, R, C, bpp, n_episodes=200)
    rl_capped = {p: min(n, N) for p, n in rl_alloc.items()}
    cfg_rl = f'lam_{wl}_{label}_rl'
    mw.gen_anynet_config(cfg_rl, grid, rl_capped, chip_n=N, outdir=CONFIG_DIR)
    if lam != 1.0:
        scale_express_latency(CONFIG_DIR / f'{cfg_rl}.anynet',
                              CONFIG_DIR / f'{cfg_rl}.anynet', lam)
    L_rl = mw.run_booksim(cfg_rl, traf_file, base_rate, timeout=900)['latency']
    train_time = time.time() - t0

    return {
        'L_adj': L_adj, 'L_greedy': L_g, 'L_rl_raw': L_rl,
        'L_rl_fb': min(L_g, L_rl) if (L_g and L_rl) else (L_g or L_rl),
        'train_time': train_time,
    }


def main():
    print('=== lambda sensitivity sweep ===', flush=True)
    surrogate = mw.load_surrogate()

    existing = []
    if OUT_FILE.exists():
        existing = json.load(open(OUT_FILE))
    done = {(r['workload'], r['K'], r['N'], r['budget_per_pair'], r['lambda']) for r in existing}
    out = list(existing)

    for (wl, K, N, bpp) in CELLS:
        for lam in LAMBDAS:
            key = (wl, K, N, bpp, lam)
            if key in done:
                print(f'SKIP {wl} K{K}N{N} b{bpp}x lam={lam}', flush=True)
                continue
            print(f'\n>>> {wl} K{K}N{N} b{bpp}x lam={lam}', flush=True)
            try:
                res = run_one(wl, K, N, bpp, lam, surrogate)
                res.update({'workload': wl, 'K': K, 'N': N,
                            'budget_per_pair': bpp, 'lambda': lam})
                out.append(res)
                with open(OUT_FILE, 'w') as f:
                    json.dump(out, f, indent=2)
                sv_g = (res['L_adj'] - res['L_greedy']) / res['L_adj'] * 100
                sv_rl = (res['L_adj'] - res['L_rl_fb']) / res['L_adj'] * 100
                print(f'    L_adj={res["L_adj"]} L_g={res["L_greedy"]} L_rl_fb={res["L_rl_fb"]} '
                      f'greedy_sv={sv_g:+.2f}% rl_fb_sv={sv_rl:+.2f}%', flush=True)
            except Exception as e:
                print(f'    ERROR: {e}', flush=True)

    print(f'\nDone. Wrote {OUT_FILE}', flush=True)


if __name__ == '__main__':
    main()
