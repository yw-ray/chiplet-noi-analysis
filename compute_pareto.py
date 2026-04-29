"""Latency vs Wire-mm² Pareto curve analysis.

Combines:
- bpp_extra.json: K32N8 budget sweep (bpp 3,5,6,7) + K32N4 bpp=3
- rl_v5.json: 28 cells (bpp=4 for all)
- BookSim anynet configs: parse for accurate wire-mm² per method

Output:
- results/ml_placement/pareto.json: structured data per (workload, K, N, bpp, method)
- paper/figures/fig_wire_pareto.pdf: 16-panel figure (4 K-N × 4 high-NL workloads)
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

sys.path.insert(0, '.')
import ml_express_warmstart as mw

mpl.rcParams.update({
    'font.size': 6, 'axes.titlesize': 7, 'axes.labelsize': 6,
    'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5, 'legend.fontsize': 5,
    'lines.linewidth': 0.8, 'lines.markersize': 4,
})

R = Path('results/ml_placement')
CONFIG_DIR = Path('booksim_configs')
OUT_JSON = R / 'pareto.json'

WIRE_AREA = {1: 2.0, 2: 4.1, 3: 6.1, 4: 8.2}


def parse_anynet(path: Path, npc: int):
    pair_hops = defaultdict(lambda: defaultdict(int))
    if not path.exists():
        return None
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if not parts or 'node' in parts:
                continue
            if len(parts) == 5 and parts[0] == 'router' and parts[2] == 'router':
                a, b = int(parts[1]), int(parts[3])
                latency = int(parts[4])
                hop = max(1, latency // 2)
                ci, cj = a // npc, b // npc
                if ci == cj:
                    continue
                pair_hops[(min(ci, cj), max(ci, cj))][hop] += 1
    return pair_hops


def hop_distribution(pair_hops):
    counts = defaultdict(int)
    for hops in pair_hops.values():
        for h, n in hops.items():
            counts[h] += n
    return dict(counts)


def wire_mm2(hop_counts):
    return sum(WIRE_AREA.get(h, h * 2.0) * n for h, n in hop_counts.items())


def collect():
    """Collect (workload, K, N, bpp, method) -> {wire, latency}"""
    rows = []

    # 1. From rl_v5.json (bpp=4 for 28 cells)
    v5 = json.load(open(R / 'rl_v5.json'))
    for cell in v5:
        wl, K, N, bpp = cell['workload'], cell['K'], cell['N'], cell['budget_per_pair']
        npc = N * N
        label = f'K{K}_N{N}_bpp{bpp}'
        prefix = 'v5_'
        # adj_uniform
        ay = CONFIG_DIR / f'{prefix}{wl}_{label}_adj.anynet'
        if ay.exists():
            ph = parse_anynet(ay, npc)
            wire = wire_mm2(hop_distribution(ph))
            lat = max(x for x in cell['adj_uniform']['latency'] if x is not None)
            rows.append({'workload': wl, 'K': K, 'N': N, 'bpp': bpp, 'method': 'adj_uniform', 'wire': wire, 'latency': lat})
        # greedy
        ay = CONFIG_DIR / f'{prefix}{wl}_{label}_greedy.anynet'
        if ay.exists():
            wire = wire_mm2(hop_distribution(parse_anynet(ay, npc)))
            lat = max(x for x in cell['greedy']['latency'] if x is not None)
            rows.append({'workload': wl, 'K': K, 'N': N, 'bpp': bpp, 'method': 'greedy', 'wire': wire, 'latency': lat})
        # fbfly
        ay = CONFIG_DIR / f'{prefix}{wl}_{label}_fbfly.anynet'
        if ay.exists():
            wire = wire_mm2(hop_distribution(parse_anynet(ay, npc)))
            lat = max(x for x in cell['fbfly']['latency'] if x is not None)
            rows.append({'workload': wl, 'K': K, 'N': N, 'bpp': bpp, 'method': 'fbfly', 'wire': wire, 'latency': lat})
        # rl-ws (best_candidate)
        bt = cell['ours_v5']['best_candidate']
        ay = CONFIG_DIR / f'{prefix}{wl}_{label}_{bt}.anynet'
        if ay.exists():
            wire = wire_mm2(hop_distribution(parse_anynet(ay, npc)))
            lat = max(x for x in cell['ours_v5']['latency'] if x is not None)
            rows.append({'workload': wl, 'K': K, 'N': N, 'bpp': bpp, 'method': 'rl_ws', 'wire': wire, 'latency': lat})

    # 2. From rl_ga.json (28 cells, GA Genetic Algorithm)
    if (R / 'rl_ga.json').exists():
        ga = json.load(open(R / 'rl_ga.json'))
        for cell in ga:
            wl, K, N, bpp = cell['workload'], cell['K'], cell['N'], cell['budget_per_pair']
            npc = N * N
            label = f'K{K}_N{N}_bpp{bpp}'
            if not cell.get('ours_ga'):
                continue
            bt = cell['ours_ga']['best_candidate']
            ay = CONFIG_DIR / f'ga_{wl}_{label}_{bt}.anynet'
            if not ay.exists():
                continue
            wire = wire_mm2(hop_distribution(parse_anynet(ay, npc)))
            lat = max(x for x in cell['ours_ga']['latency'] if x is not None)
            rows.append({'workload': wl, 'K': K, 'N': N, 'bpp': bpp, 'method': 'ga', 'wire': wire, 'latency': lat})

    # 3. From ml_generalization_finetuned.json (12 cells, GNN-FT for Ring/Pipeline/All-to-all)
    if (R / 'ml_generalization_finetuned.json').exists():
        gft = json.load(open(R / 'ml_generalization_finetuned.json'))
        for cell in gft:
            wl, K, N, bpp = cell['workload'], cell['K'], cell['N'], cell['budget_per_pair']
            npc = N * N
            label = f'K{K}_N{N}_bpp{bpp}'
            ay = CONFIG_DIR / f'ft_{wl}_{label}_gnnft.anynet'
            if not ay.exists():
                continue
            wire = wire_mm2(hop_distribution(parse_anynet(ay, npc)))
            lat = cell['L_gnn_ft']
            rows.append({'workload': wl, 'K': K, 'N': N, 'bpp': bpp, 'method': 'gnn_ft', 'wire': wire, 'latency': lat})

    # 5. From rl_random.json (random baseline) and rl_pure_fbfly.json
    for json_file, m_name, anynet_prefix in [
        ('rl_random.json', 'random', 'rand'),
        ('rl_pure_fbfly.json', 'pure_fbfly', 'purefb'),
    ]:
        if (R / json_file).exists():
            for cell in json.load(open(R / json_file)):
                wl, K, N, bpp = cell['workload'], cell['K'], cell['N'], cell['budget_per_pair']
                npc = N * N
                label = f'K{K}_N{N}_bpp{bpp}'
                ay = CONFIG_DIR / f'{anynet_prefix}_{wl}_{label}.anynet'
                if not ay.exists():
                    continue
                wire = wire_mm2(hop_distribution(parse_anynet(ay, npc)))
                lat = cell.get('max_latency')
                if lat is None or lat == float('inf'):
                    continue
                rows.append({'workload': wl, 'K': K, 'N': N, 'bpp': bpp, 'method': m_name, 'wire': wire, 'latency': lat})

    # 4. From bpp_extra.json (K32N8 bpp 3,5,6,7 + K32N4 bpp=3)
    extra = json.load(open(R / 'bpp_extra.json'))
    for r in extra:
        wl, K, N, bpp = r['workload'], r['K'], r['N'], r['budget_per_pair']
        npc = N * N
        label = f'K{K}_N{N}_bpp{bpp}'
        prefix = 'bpp_'
        # 4 methods
        for m_tag, m_name, lat_key in [
            ('adj', 'adj_uniform', 'L_adj'),
            ('greedy', 'greedy', 'L_greedy'),
            ('fbfly', 'fbfly', 'L_fbfly'),
            ('rl', 'rl_ws', 'L_rl_fb'),  # use fallback (= our final method)
        ]:
            ay = CONFIG_DIR / f'{prefix}{wl}_{label}_{m_tag}.anynet'
            if ay.exists():
                wire = wire_mm2(hop_distribution(parse_anynet(ay, npc)))
                lat = r[lat_key]
                rows.append({'workload': wl, 'K': K, 'N': N, 'bpp': bpp, 'method': m_name, 'wire': wire, 'latency': lat})

    return rows


def plot_pareto(rows):
    """16-panel: 4 K-N × 4 high-NL workloads"""
    by = defaultdict(list)
    for r in rows:
        by[(r['K'], r['N'], r['workload'])].append(r)

    HIGH_NL = ['moe', 'hybrid_tp_pp', 'uniform_random', 'all_to_all']
    KNS = [(16, 4), (16, 8), (32, 4), (32, 8)]
    METHODS = {
        'adj_uniform': ('o', '#7f7f7f', 'Adj-uniform'),
        'random':      ('x', '#bcbd22', 'Random'),
        'greedy':      ('s', '#1f77b4', 'Greedy'),
        'fbfly':       ('^', '#2ca02c', 'FBfly'),
        'pure_fbfly':  ('v', '#17becf', 'Pure-FBfly'),
        'ga':          ('p', '#9467bd', 'GA'),
        'gnn_ft':      ('h', '#e377c2', 'GNN-FT'),
        'rl_ws':       ('D', '#d62728', 'RL-WS'),
    }

    fig, axes = plt.subplots(4, 4, figsize=(8.8, 7.0), sharex=False, sharey=False)
    for i, (K, N) in enumerate(KNS):
        for j, wl in enumerate(HIGH_NL):
            ax = axes[i][j]
            data = by.get((K, N, wl), [])
            if not data:
                ax.text(0.5, 0.5, 'no data', transform=ax.transAxes, ha='center', va='center', fontsize=6, color='gray')
                ax.set_xticks([]); ax.set_yticks([])
                continue
            # Group by method
            by_m = defaultdict(list)
            for r in data:
                by_m[r['method']].append((r['wire'], r['latency'], r['bpp']))
            for m, (marker, color, name) in METHODS.items():
                pts = sorted(by_m.get(m, []), key=lambda x: x[0])
                if not pts:
                    continue
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                ax.plot(xs, ys, marker=marker, color=color, linewidth=0.8,
                        markersize=4, label=name if (i == 0 and j == 0) else None,
                        alpha=0.85, markeredgecolor='black', markeredgewidth=0.3)
            ax.set_yscale('log')
            ax.grid(True, alpha=0.3, linewidth=0.3)
            if i == 3:
                ax.set_xlabel(r'Wire area (mm²)')
            if j == 0:
                ax.set_ylabel(f'K={K}, N={N}\nLatency (cyc)')
            if i == 0:
                ax.set_title(wl)
    fig.legend(loc='upper center', bbox_to_anchor=(0.5, 0.99), ncol=4, frameon=False)
    plt.tight_layout()
    plt.subplots_adjust(top=0.93)
    out = Path('paper/figures/fig_wire_pareto.pdf')
    out.parent.mkdir(exist_ok=True, parents=True)
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.savefig(str(out).replace('.pdf', '.png'), dpi=200, bbox_inches='tight')
    print(f'Saved {out}')


def main():
    rows = collect()
    with open(OUT_JSON, 'w') as f:
        json.dump(rows, f, indent=2)
    print(f'Saved {len(rows)} entries to {OUT_JSON}')

    # Print summary
    by_kn = defaultdict(lambda: defaultdict(set))
    for r in rows:
        by_kn[(r['K'], r['N'], r['workload'])][r['method']].add(r['bpp'])
    print()
    print('Coverage per (K, N, workload):')
    for (K, N, wl), m_bpp in sorted(by_kn.items()):
        print(f'  K{K}N{N} {wl:<22s}: ' + ' '.join(f'{m}={sorted(b)}' for m, b in m_bpp.items()))

    plot_pareto(rows)


if __name__ == '__main__':
    main()
