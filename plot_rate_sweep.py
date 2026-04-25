"""Generate Fig 5: rate-vs-latency curves (4 cells × 4 methods)."""
import json
from pathlib import Path
import matplotlib.pyplot as plt

plt.rcParams.update({
    'font.size': 6,
    'axes.titlesize': 7,
    'axes.labelsize': 6,
    'xtick.labelsize': 5.5,
    'ytick.labelsize': 5.5,
    'legend.fontsize': 5.5,
    'font.family': 'serif',
})

R = Path('results/ml_placement')
d = json.load(open(R / 'rate_sweep.json'))

ORDER = {'tree_allreduce': 0, 'hybrid_tp_pp': 1, 'uniform_random': 2, 'moe': 3}
TITLE = {
    'tree_allreduce': 'Tree All-Reduce (NL 42%)',
    'hybrid_tp_pp': 'Hybrid TP+PP (NL 77%)',
    'uniform_random': 'Uniform Random (NL 89%)',
    'moe': 'MoE Skewed (NL 91%)',
}
METHODS = [
    ('adj_uniform', 'Adj Uniform', 'tab:gray', 's', '--'),
    ('greedy', 'Greedy', 'tab:blue', 'o', '-'),
    ('fbfly', 'FBfly', 'tab:orange', '^', '-.'),
    ('rl_ws', 'RL-WS (ours)', 'tab:red', 'D', '-'),
]

d_sorted = sorted(d, key=lambda r: ORDER[r['workload']])

fig, axes = plt.subplots(1, 4, figsize=(7.2, 1.8), sharey=False)

for ax, r in zip(axes, d_sorted):
    rates_mult = [1, 2, 3, 4]
    for key, label, color, marker, ls in METHODS:
        lat = r[key]['latency']
        ax.plot(rates_mult, lat, color=color, marker=marker, linestyle=ls,
                label=label, markersize=3.2, linewidth=1.0)
    ax.set_title(TITLE[r['workload']])
    ax.set_xlabel(r'Injection rate ($\times$ base)')
    ax.set_xticks([1, 2, 3, 4])
    ax.grid(True, alpha=0.3, which='both', linewidth=0.3)
    # MoE only uses log because range 55-440 is too wide for linear
    if r['workload'] == 'moe':
        ax.set_yscale('log')
        ax.set_ylim(50, 500)
        ax.set_ylabel('Latency (cycles, log)')
    else:
        ax.set_yscale('linear')
        # tight autoscale with small padding
        all_lat = [v for key, *_ in METHODS for v in r[key]['latency']]
        lo, hi = min(all_lat), max(all_lat)
        margin = (hi - lo) * 0.12
        ax.set_ylim(lo - margin, hi + margin)
        ax.set_ylabel('Latency (cycles)')

axes[0].legend(loc='center right', frameon=True, handlelength=2.0,
               borderpad=0.3, labelspacing=0.25)

plt.tight_layout(w_pad=0.3)

out = Path('paper/figures/fig_rate_sweep.pdf')
plt.savefig(out, bbox_inches='tight', dpi=300)
print(f'Saved: {out}')

# Also a PNG preview for quick view
png = Path('paper/figures/fig_rate_sweep.png')
plt.savefig(png, bbox_inches='tight', dpi=150)
print(f'Saved: {png}')
