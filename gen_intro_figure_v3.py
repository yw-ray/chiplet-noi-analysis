"""
Introduction Figure v3: Show the SATURATION problem.

(a) Phantom load amplification grows with K (closed-form)
(b) Adjacent-only saturates with budget; express doesn't
    → "Adding more adjacent links doesn't help"
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import json
from pathlib import Path

FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'

plt.rcParams.update({
    'font.size': 9, 'font.family': 'serif',
    'axes.labelsize': 10, 'axes.titlesize': 10,
    'legend.fontsize': 8, 'xtick.labelsize': 8, 'ytick.labelsize': 8,
    'figure.dpi': 150,
})

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

# Panel (b): Real BookSim data — budget sweep for K=16, 4×4 internal mesh
# From cost_perf_across_K experiment
budgets = [1, 2, 3, 4]
budget_labels = ['1×', '2×', '3×', '4×']
adj_lats = [71.5, 52.3, 49.2, 48.5]      # adj_uniform lat@0.005
expr_lats = [71.5, 44.2, 40.3, 38.4]     # express_greedy lat@0.005

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
ax.annotate('MI300X\n(K=8)', xy=(8, 8), fontsize=7, ha='center',
            xytext=(14, 3.5), arrowprops=dict(arrowstyle='->', color='gray', lw=0.8))
ax.annotate('Next-gen\n(K≥16)', xy=(16, 16), fontsize=7, ha='center',
            xytext=(28, 7), arrowprops=dict(arrowstyle='->', color='gray', lw=0.8))
ax.axhspan(1, 10, alpha=0.04, color='green')
ax.axhspan(10, 200, alpha=0.04, color='red')
ax.text(3.5, 3, 'Manageable', fontsize=7, color='green', style='italic')
ax.text(3.5, 40, 'Critical', fontsize=7, color='red', style='italic')

# (b) Budget sweep: adjacent saturates, express doesn't
ax = axes[1]
ax.plot(budgets, adj_lats, 's-', color='#1f77b4', markersize=7, linewidth=2.0,
        label='Adjacent only', zorder=3)
ax.plot(budgets, expr_lats, 'o-', color='#d62728', markersize=7, linewidth=2.0,
        label='With express links', zorder=3)

# Shade the saturation region for adjacent
ax.fill_between([2, 4], [adj_lats[1], adj_lats[3]], [adj_lats[1] + 5, adj_lats[3] + 5],
                alpha=0.0)  # invisible, just for spacing
ax.annotate('Saturated\n(+7% over 2× budget)',
            xy=(3.5, 48.8), fontsize=7.5, ha='center', color='#1f77b4',
            fontweight='bold', style='italic')

# Arrow showing the gap
ax.annotate('', xy=(4, expr_lats[3]), xytext=(4, adj_lats[3]),
            arrowprops=dict(arrowstyle='<->', color='#ff7f0e', lw=1.5))
ax.text(4.15, (adj_lats[3] + expr_lats[3]) / 2, '21%\ngap',
        fontsize=8, color='#ff7f0e', fontweight='bold', va='center')

ax.set_xlabel('Link budget (× per adjacent pair)')
ax.set_ylabel('Latency (cycles)')
ax.set_xticks(budgets)
ax.set_xticklabels(budget_labels)
ax.set_title('(b) Adjacent saturates; express does not (K=16)')
ax.legend(loc='upper right', framealpha=0.9)
ax.grid(True, alpha=0.3)
ax.set_ylim(30, 80)

plt.tight_layout()
fig.savefig(FIGURES_DIR / 'fig_intro_motivation.pdf', bbox_inches='tight')
fig.savefig(FIGURES_DIR / 'fig_intro_motivation.png', bbox_inches='tight')
plt.close()
print("[OK] fig_intro_motivation.pdf")
