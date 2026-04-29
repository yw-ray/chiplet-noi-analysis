"""Wire-mm² + Phantom-load coverage analysis from anynet config files.

For each (workload, K, N, bpp) cell, parse the BookSim configs of all 4
methods (adj_uniform, greedy, fbfly, RL-best) and compute:
  - hop-distribution (count of hop1 / hop2 / hop3 inter-chip links)
  - wire-mm² (using Table 8 per-link area: hop1=2.0, hop2=4.1, hop3=6.1)
  - express coverage (fraction of long-distance traffic on direct links)

Output: results/ml_placement/wire_phantom.json
"""
import json
import os
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np

sys.path.insert(0, '.')
import ml_express_warmstart as mw

R = Path('results/ml_placement')
CONFIG_DIR = Path('booksim_configs')
OUT = R / 'wire_phantom.json'

# Per-link wire area (mm²) — Table 8
WIRE_AREA = {1: 2.0, 2: 4.1, 3: 6.1, 4: 8.2}


def parse_anynet(path: Path, npc: int):
    """Parse BookSim anynet to get inter-chip link counts per (chip_pair, hop).

    Returns dict {(ci, cj): {hop: count}}.
    """
    pair_hops = defaultdict(lambda: defaultdict(int))
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            # Skip intra-chip mesh lines (have "node" keyword)
            if 'node' in parts:
                continue
            # Inter-chip link line: "router A router B latency"
            if len(parts) == 5 and parts[0] == 'router' and parts[2] == 'router':
                a, b = int(parts[1]), int(parts[3])
                latency = int(parts[4])
                hop = max(1, latency // 2)
                ci, cj = a // npc, b // npc
                if ci == cj:
                    continue
                key = (min(ci, cj), max(ci, cj))
                pair_hops[key][hop] += 1
    return pair_hops


def hop_distribution(pair_hops):
    """Aggregate to total counts per hop."""
    counts = defaultdict(int)
    for pair, hops in pair_hops.items():
        for h, n in hops.items():
            counts[h] += n
    return dict(counts)


def wire_mm2(hop_counts):
    return sum(WIRE_AREA.get(h, h * 2.0) * n for h, n in hop_counts.items())


def express_coverage(grid, traffic, pair_hops):
    """Fraction of long-distance traffic on pairs with at least one direct
    inter-chip link (i.e., non-adj pair with allocation > 0)."""
    K = grid.K
    long_dist_total = 0.0
    long_dist_covered = 0.0
    for i in range(K):
        for j in range(i + 1, K):
            h = grid.get_hops(i, j)
            if h >= 2:
                t = float(traffic[i][j] + traffic[j][i])
                long_dist_total += t
                if pair_hops.get((i, j)):
                    long_dist_covered += t
    return long_dist_covered / long_dist_total if long_dist_total > 0 else 0.0


def cell_metrics(wl, K, N, bpp):
    R_grid, C_grid = (4, 4) if K == 16 else (4, 8)
    grid = mw.ChipletGrid(R_grid, C_grid)
    traffic = mw.WORKLOADS[wl](K, grid)
    npc = N * N
    label = f'K{K}_N{N}_bpp{bpp}'

    # Find best_candidate tag from rl_v5.json
    v5 = json.load(open(R / 'rl_v5.json'))
    cell = next((r for r in v5 if (r['workload'], r['K'], r['N'], r['budget_per_pair']) == (wl, K, N, bpp)), None)
    if cell is None:
        return None
    best_tag = cell['ours_v5']['best_candidate']

    methods = {
        'adj_uniform': f'v5_{wl}_{label}_adj',
        'greedy':      f'v5_{wl}_{label}_greedy',
        'fbfly':       f'v5_{wl}_{label}_fbfly',
        'rl_ws':       f'v5_{wl}_{label}_{best_tag}',
    }

    out = {'workload': wl, 'K': K, 'N': N, 'bpp': bpp, 'methods': {}}
    for m, name in methods.items():
        anynet = CONFIG_DIR / f'{name}.anynet'
        if not anynet.exists():
            print(f'  MISSING: {anynet}', flush=True)
            continue
        pair_hops = parse_anynet(anynet, npc)
        hop_counts = hop_distribution(pair_hops)
        # Latency from rl_v5.json
        if m == 'rl_ws':
            lat = max(x for x in cell['ours_v5']['latency'] if x is not None)
        else:
            lat = max(x for x in cell[m]['latency'] if x is not None)
        out['methods'][m] = {
            'hop_counts': hop_counts,
            'total_links': sum(hop_counts.values()),
            'wire_mm2': wire_mm2(hop_counts),
            'express_coverage': express_coverage(grid, traffic, pair_hops),
            'latency': lat,
        }
    return out


def main():
    cells = []
    # 4 high-NL workloads at K=32, N=8, b=4× (most informative)
    for wl in ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all',
               'tree_allreduce', 'ring_allreduce', 'pipeline_parallel']:
        m = cell_metrics(wl, 32, 8, 4)
        if m: cells.append(m)
        m = cell_metrics(wl, 32, 4, 4)
        if m: cells.append(m)
        m = cell_metrics(wl, 16, 8, 4)
        if m: cells.append(m)
        m = cell_metrics(wl, 16, 4, 4)
        if m: cells.append(m)

    with open(OUT, 'w') as f:
        json.dump(cells, f, indent=2)
    print(f'Saved {len(cells)} cells to {OUT}', flush=True)

    # Print summary
    print()
    print(f'{"workload":<20s} K  N b | {"adj":>30s} | {"greedy":>30s} | {"fbfly":>30s} | {"RL-WS":>30s}')
    print('-' * 160)
    for c in cells:
        wl, K, N, bpp = c['workload'], c['K'], c['N'], c['bpp']
        ms = c['methods']
        cells_str = []
        for m in ['adj_uniform', 'greedy', 'fbfly', 'rl_ws']:
            md = ms.get(m, {})
            if md:
                ec = md.get('express_coverage', 0) * 100
                wm = md.get('wire_mm2', 0)
                lat = md.get('latency', 0)
                cells_str.append(f'lat={lat:5.1f} mm²={wm:5.0f} cov={ec:4.1f}%')
            else:
                cells_str.append('--')
        print(f'{wl:<20s} {K:2d} {N} {bpp} | {cells_str[0]:>30s} | {cells_str[1]:>30s} | {cells_str[2]:>30s} | {cells_str[3]:>30s}')


if __name__ == '__main__':
    main()
