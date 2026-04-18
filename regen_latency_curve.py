"""Latency curve for K=4, 8, 16, 32 in 2×2 grid layout."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json
from pathlib import Path

FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'
RESULTS_DIR = Path(__file__).parent / 'results' / 'cost_perf_K'

plt.rcParams.update({
    'font.size': 6, 'font.family': 'serif',
    'axes.labelsize': 6, 'axes.titlesize': 7,
    'legend.fontsize': 5.5, 'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5,
    'figure.dpi': 150,
})

with open(RESULTS_DIR / 'cost_perf_across_K.json') as f:
    data = json.load(f)

fig, axes = plt.subplots(2, 2, figsize=(3.5, 3.2))
grid_labels = ['2x2', '2x4', '4x4', '4x8']
K_labels = ['K=4', 'K=8', 'K=16', 'K=32']

for idx, (grid_label, k_label) in enumerate(zip(grid_labels, K_labels)):
    ax = axes[idx // 2][idx % 2]
    d = data[grid_label]

    # Use budget 3x for all
    for strategy, color, marker, label in [
        ('adj_uniform', '#1f77b4', 'o', 'Adjacent'),
        ('express_greedy', '#d62728', 's', 'Express'),
    ]:
        entry = next((e for e in d['experiments']
                      if e['strategy'] == strategy and e['budget_mult'] == 3), None)
        if entry:
            rates = [r['rate'] for r in entry['rates'] if r['latency']]
            lats = [r['latency'] for r in entry['rates'] if r['latency']]
            ax.plot(rates, lats, f'{marker}-', color=color, label=label,
                    markersize=3, linewidth=1.2)

    ax.set_xlabel('Injection rate')
    ax.set_ylabel('Latency (cycles)')
    ax.set_title(f'({chr(97+idx)}) {k_label} (3× budget)')
    ax.set_xticks([0.005, 0.01, 0.015])
    ax.legend(fontsize=5)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(FIGURES_DIR / 'fig_latency_curve.pdf', bbox_inches='tight')
fig.savefig(FIGURES_DIR / 'fig_latency_curve.png', bbox_inches='tight')
plt.close()
print("[OK] fig_latency_curve.pdf")
