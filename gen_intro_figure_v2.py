"""
Introduction Figure v2: Show THE PROBLEM, not the solution.

(a) Phantom load amplification grows with K (closed-form, theoretical)
(b) Adjacent-only NoI performance degrades with K (BookSim, real data)

No express links in this figure — that comes in evaluation.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import json
from pathlib import Path

FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'
RESULTS_DIR = Path(__file__).parent / 'results' / 'cost_perf_K'

plt.rcParams.update({
    'font.size': 9, 'font.family': 'serif',
    'axes.labelsize': 10, 'axes.titlesize': 10,
    'legend.fontsize': 8, 'xtick.labelsize': 8, 'ytick.labelsize': 8,
    'figure.dpi': 150,
})

# Load real experiment data
with open(RESULTS_DIR / 'cost_perf_across_K.json') as f:
    data = json.load(f)

# Panel (a): Closed-form amplification
grids = [
    (2, 2, 4), (2, 3, 6), (2, 4, 8), (3, 3, 9),
    (3, 4, 12), (4, 4, 16), (4, 6, 24), (4, 8, 32), (8, 8, 64),
]
theo_Ks = [g[2] for g in grids]
theo_amps = []
for R, C, K in grids:
    max_h = R * ((C + 1) // 2) * (C // 2)
    max_v = C * ((R + 1) // 2) * (R // 2)
    theo_amps.append(max(max_h, max_v))

# Panel (b): Adjacent-only latency from BookSim (real data)
# Extract adj_uniform at budget 3x for each K
booksim_Ks = []
booksim_lats_005 = []
booksim_lats_01 = []

for grid_label in ['2x2', '2x4', '4x4', '4x8']:
    if grid_label not in data:
        continue
    K = data[grid_label]['K']
    # Get 3x budget adj_uniform
    entry = next((e for e in data[grid_label]['experiments']
                  if e['strategy'] == 'adj_uniform' and e['budget_mult'] == 3), None)
    if entry:
        lat_005 = next((r['latency'] for r in entry['rates']
                        if abs(r['rate'] - 0.005) < 0.001 and r['latency']), None)
        lat_01 = next((r['latency'] for r in entry['rates']
                       if abs(r['rate'] - 0.01) < 0.001 and r['latency']), None)
        if lat_005:
            booksim_Ks.append(K)
            booksim_lats_005.append(lat_005)
            booksim_lats_01.append(lat_01 if lat_01 else None)

fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.8))

# (a) Theoretical amplification
ax = axes[0]
ax.plot(theo_Ks, theo_amps, 'o-', color='#d62728', markersize=5, linewidth=1.8)
ax.fill_between(theo_Ks, [1] * len(theo_Ks), theo_amps, alpha=0.12, color='#d62728')
ax.axhline(y=1, color='gray', linestyle='--', linewidth=0.8)
ax.set_xlabel('Number of chiplets (K)')
ax.set_ylabel('Center link amplification (α)')
ax.set_yscale('log')
ax.set_title('(a) Phantom load grows with K')
ax.grid(True, alpha=0.3)

# Annotations
ax.annotate('MI300X\n(K=8)', xy=(8, 8), fontsize=7, ha='center',
            xytext=(14, 3.5), arrowprops=dict(arrowstyle='->', color='gray', lw=0.8))
ax.annotate('Next-gen\n(K≥16)', xy=(16, 16), fontsize=7, ha='center',
            xytext=(28, 7), arrowprops=dict(arrowstyle='->', color='gray', lw=0.8))
ax.axhspan(1, 10, alpha=0.04, color='green')
ax.axhspan(10, 200, alpha=0.04, color='red')
ax.text(3.5, 3, 'Manageable', fontsize=7, color='green', style='italic')
ax.text(3.5, 40, 'Critical', fontsize=7, color='red', style='italic')

# (b) BookSim adjacent-only latency degradation
ax = axes[1]
ax.plot(booksim_Ks, booksim_lats_005, 'o-', color='#1f77b4', markersize=6, linewidth=1.8,
        label='rate = 0.005')
valid_01 = [(k, l) for k, l in zip(booksim_Ks, booksim_lats_01) if l is not None]
if valid_01:
    ax.plot([x[0] for x in valid_01], [x[1] for x in valid_01],
            's--', color='#ff7f0e', markersize=5, linewidth=1.5, label='rate = 0.01')

ax.set_xlabel('Number of chiplets (K)')
ax.set_ylabel('Latency (cycles), adjacent-only')
ax.set_title('(b) Adjacent-only NoI degrades with K')
ax.legend(loc='upper left')
ax.grid(True, alpha=0.3)
ax.set_yscale('log')

# Annotate the degradation
ax.annotate(f'{booksim_lats_005[0]:.0f}', xy=(booksim_Ks[0], booksim_lats_005[0]),
            fontsize=7, ha='center', va='bottom', xytext=(0, 5),
            textcoords='offset points')
ax.annotate(f'{booksim_lats_005[-1]:.0f}', xy=(booksim_Ks[-1], booksim_lats_005[-1]),
            fontsize=7, ha='center', va='bottom', xytext=(0, 5),
            textcoords='offset points')

# Arrow showing degradation
ax.annotate(f'{booksim_lats_005[-1]/booksim_lats_005[0]:.0f}× worse',
            xy=(booksim_Ks[-1], booksim_lats_005[-1]),
            xytext=(booksim_Ks[-1] - 8, booksim_lats_005[-1] * 1.5),
            fontsize=8, color='#d62728', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#d62728', lw=1.2))

plt.tight_layout()
fig.savefig(FIGURES_DIR / 'fig_intro_motivation.pdf', bbox_inches='tight')
fig.savefig(FIGURES_DIR / 'fig_intro_motivation.png', bbox_inches='tight')
plt.close()
print("[OK] fig_intro_motivation.pdf")
