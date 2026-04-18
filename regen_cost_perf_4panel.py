"""Regenerate Fig 3 as 4-panel: K=8/32 x N=4/8.

Each panel: cost (links) vs latency at the *lowest* injection rate
(rate_multiplier=0.5 of base) to stay safely below saturation.
Rate normalization (rate * K * N^2 = 1.28) matches experiment script.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json
from pathlib import Path

FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'
RESULTS_DIR = Path(__file__).parent / 'results' / 'cost_perf_4panel'

plt.rcParams.update({
    'font.size': 6, 'font.family': 'serif',
    'axes.labelsize': 6, 'axes.titlesize': 7,
    'legend.fontsize': 5.5, 'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5,
    'figure.dpi': 150,
})

bbox_white = dict(boxstyle='round,pad=0.2', facecolor='white',
                  edgecolor='none', alpha=0.85)

with open(RESULTS_DIR / 'cost_perf_4panel.json') as f:
    all_results = json.load(f)

panels = [
    ('K8_N4',  'K=8, N=4'),
    ('K8_N8',  'K=8, N=8'),
    ('K32_N4', 'K=32, N=4'),
    ('K32_N8', 'K=32, N=8'),
]

fig, axes = plt.subplots(2, 2, figsize=(3.5, 3.2))


def interp_cost(points, target):
    """Linear interpolation: find cost where latency == target."""
    for i in range(len(points) - 1):
        c1, l1 = points[i]
        c2, l2 = points[i + 1]
        if l1 >= target >= l2:
            if l1 == l2:
                return c1
            t = (target - l1) / (l2 - l1)
            return c1 + t * (c2 - c1)
    return None


for idx, (key, title) in enumerate(panels):
    ax = axes[idx // 2][idx % 2]

    if key not in all_results:
        ax.text(0.5, 0.5, '(pending)', ha='center', va='center',
                transform=ax.transAxes, fontsize=7, color='gray')
        ax.set_title(f'({chr(97+idx)}) {title}')
        ax.set_xticks([])
        ax.set_yticks([])
        continue

    data = all_results[key]
    exps = data['experiments']
    # Use lowest rate (0.5x base) for "below saturation" comparison
    target_rate = data['rates'][0]

    series = {}
    for strategy, color, marker, label in [
        ('adj_uniform', '#1f77b4', 'o', 'Adjacent'),
        ('express_greedy', '#d62728', 's', 'Express'),
    ]:
        strat_exps = [e for e in exps if e['strategy'] == strategy]
        costs, lats = [], []
        for e in strat_exps:
            rate_data = [r for r in e['rates']
                         if abs(r['rate'] - target_rate)
                         < target_rate * 0.01]
            if rate_data and rate_data[0]['latency']:
                costs.append(e['total_links'])
                lats.append(rate_data[0]['latency'])

        if costs:
            ax.plot(costs, lats, f'{marker}-', color=color, label=label,
                    markersize=3.5, linewidth=1.2)
            series[strategy] = list(zip(costs, lats))

    # Cost saving annotation
    if 'adj_uniform' in series and 'express_greedy' in series:
        adj = sorted(series['adj_uniform'])
        expr = sorted(series['express_greedy'])
        target_lat = adj[-1][1] * 1.05
        adj_cost = interp_cost(adj, target_lat)
        expr_cost = interp_cost(expr, target_lat)

        if (adj_cost and expr_cost and adj_cost > expr_cost * 1.03):
            saving = adj_cost / expr_cost
            ax.axhline(y=target_lat, color='gray', linestyle='--',
                       linewidth=0.5, alpha=0.5)
            ax.annotate('', xy=(expr_cost, target_lat * 0.93),
                        xytext=(adj_cost, target_lat * 0.93),
                        arrowprops=dict(arrowstyle='<->',
                                        color='#ff7f0e', lw=0.9))
            mid_x = (adj_cost + expr_cost) / 2
            ax.text(mid_x, target_lat * 0.85,
                    f'{saving:.1f}x',
                    fontsize=5.5, ha='center', color='#ff7f0e',
                    fontweight='bold', bbox=bbox_white)

    ax.set_xlabel('Inter-chiplet links')
    ax.set_ylabel('Latency (cycles)')
    ax.set_title(f'({chr(97+idx)}) {title}')
    ax.legend(fontsize=5)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(FIGURES_DIR / 'fig_cost_performance.pdf', bbox_inches='tight')
fig.savefig(FIGURES_DIR / 'fig_cost_performance.png', bbox_inches='tight')
plt.close()
print('[OK] fig_cost_performance.pdf (4-panel: K=8/32 x N=4/8)')
