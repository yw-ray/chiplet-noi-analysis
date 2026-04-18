"""Regenerate cost-performance figure with new normalized-rate data."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json
from pathlib import Path

FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'
RESULTS_DIR = Path(__file__).parent / 'results' / 'cost_perf'

plt.rcParams.update({
    'font.size': 6, 'font.family': 'serif',
    'axes.labelsize': 6, 'axes.titlesize': 7,
    'legend.fontsize': 5.5, 'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5,
    'figure.dpi': 150,
})

bbox_white = dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='none', alpha=0.85)

with open(RESULTS_DIR / 'cost_performance.json') as f:
    all_results = json.load(f)

# Rate to use for each mesh size (lowest = least saturation)
mesh_target_rate = {
    '4x4': 0.00125,   # base 0.005 scaled
    '8x8': 0.0003125, # base 0.005 scaled
}

show = ['4x4', '8x8']
fig, axes = plt.subplots(2, 1, figsize=(3.5, 3.5))

for idx, mesh_label in enumerate(show):
    data = all_results[mesh_label]
    ax = axes[idx]
    exps = data['experiments']
    target_rate = mesh_target_rate[mesh_label]

    series = {}
    for strategy, color, marker, label in [
        ('adj_uniform', '#1f77b4', 'o', 'Adjacent Uniform'),
        ('express_greedy', '#d62728', 's', 'Express Greedy'),
    ]:
        strat_exps = [e for e in exps if e['strategy'] == strategy]
        costs, lats = [], []
        for e in strat_exps:
            rate_data = [r for r in e['rates']
                         if abs(r['rate'] - target_rate) < target_rate * 0.01]
            if rate_data and rate_data[0]['latency']:
                costs.append(e['total_links'])
                lats.append(rate_data[0]['latency'])

        if costs:
            ax.plot(costs, lats, f'{marker}-', color=color, label=label,
                    markersize=4, linewidth=1.5)
            series[strategy] = list(zip(costs, lats))

    # Find target latency where both curves cross, and compute saving
    if 'adj_uniform' in series and 'express_greedy' in series:
        adj = sorted(series['adj_uniform'])
        expr = sorted(series['express_greedy'])
        # Use adj's best latency as target (where adj actually reaches)
        target_lat = adj[-1][1] * 1.05  # 5% above adj's best
        # Find adj's cost at this latency (interpolate)
        def interp_cost(points, target):
            for i in range(len(points) - 1):
                c1, l1 = points[i]
                c2, l2 = points[i + 1]
                if l1 >= target >= l2:
                    if l1 == l2:
                        return c1
                    t = (target - l1) / (l2 - l1)
                    return c1 + t * (c2 - c1)
            return None
        adj_cost = interp_cost(adj, target_lat)
        expr_cost = interp_cost(expr, target_lat)

        if adj_cost and expr_cost and adj_cost > expr_cost:
            saving = adj_cost / expr_cost
            ax.axhline(y=target_lat, color='gray', linestyle='--',
                       linewidth=0.7, alpha=0.6)
            ax.plot([adj_cost], [target_lat], 'v', color='#1f77b4',
                    markersize=5, zorder=5)
            ax.plot([expr_cost], [target_lat], 'v', color='#d62728',
                    markersize=5, zorder=5)
            ax.annotate('', xy=(expr_cost, target_lat * 0.95),
                        xytext=(adj_cost, target_lat * 0.95),
                        arrowprops=dict(arrowstyle='<->', color='#ff7f0e', lw=1.2))
            mid_x = (adj_cost + expr_cost) / 2
            ax.text(mid_x, target_lat * 0.87,
                    f'{saving:.1f}× fewer links',
                    fontsize=6, ha='center', color='#ff7f0e',
                    fontweight='bold', bbox=bbox_white)

    ax.set_xlabel('Total inter-chiplet links (cost)')
    ax.set_ylabel(f'Latency (cycles)')
    K = data.get('K', 16)
    ax.set_title(f'({chr(97+idx)}) {mesh_label} per-chiplet mesh (K=16)')
    ax.legend(fontsize=5.5)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(FIGURES_DIR / 'fig_cost_performance.pdf', bbox_inches='tight')
fig.savefig(FIGURES_DIR / 'fig_cost_performance.png', bbox_inches='tight')
plt.close()
print("[OK] fig_cost_performance.pdf")
