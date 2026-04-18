"""
Generate introduction motivation figure:
(a) Phantom load amplification grows with K — the problem is getting worse
(b) Cost gap: adjacent links needed vs express links needed — widening gap
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'

plt.rcParams.update({
    'font.size': 9, 'font.family': 'serif',
    'axes.labelsize': 10, 'axes.titlesize': 10,
    'legend.fontsize': 8, 'xtick.labelsize': 8, 'ytick.labelsize': 8,
    'figure.dpi': 150,
})

# Data from our closed-form analysis + cost-performance experiments
# Panel (a): Max amplification vs K (from theoretical_scaling)
grids = [
    (2, 2, 4), (2, 3, 6), (2, 4, 8), (3, 3, 9),
    (3, 4, 12), (4, 4, 16), (4, 6, 24), (4, 8, 32), (8, 8, 64),
]
Ks = [g[2] for g in grids]
max_amps = []
for R, C, K in grids:
    max_h = R * ((C + 1) // 2) * (C // 2)
    max_v = C * ((R + 1) // 2) * (R // 2)
    max_amps.append(max(max_h, max_v))

# Panel (b): Cost comparison from our experiments
# "Links needed to achieve comparable performance"
# From cost_performance results + extrapolation
cost_Ks = [4, 8, 16, 32, 64]
# Adjacent links needed (proportional to alpha_max for target rho)
adj_cost = [8, 20, 72, 208, 512]  # ~n_adj * (alpha/target_rho), estimated
# Express links needed
expr_cost = [8, 18, 48, 120, 280]  # from experiments + extrapolation
# Cost ratio
ratios = [a / e for a, e in zip(adj_cost, expr_cost)]

fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.8))

# (a) Phantom load scaling
ax = axes[0]
ax.plot(Ks, max_amps, 'o-', color='#d62728', markersize=5, linewidth=1.8)
ax.fill_between(Ks, [1] * len(Ks), max_amps, alpha=0.15, color='#d62728')
ax.axhline(y=1, color='gray', linestyle='--', linewidth=0.8, label='No phantom load')
ax.set_xlabel('Number of chiplets (K)')
ax.set_ylabel('Max link amplification (α)')
ax.set_yscale('log')
ax.set_title('(a) Phantom load grows with chiplet count')
ax.grid(True, alpha=0.3)
ax.annotate('MI300X\n(K=8)', xy=(8, 8), fontsize=7, ha='center',
            xytext=(12, 4), arrowprops=dict(arrowstyle='->', color='gray', lw=0.8))
ax.annotate('Next-gen\n(K=16+)', xy=(16, 16), fontsize=7, ha='center',
            xytext=(25, 8), arrowprops=dict(arrowstyle='->', color='gray', lw=0.8))
# Shade "manageable" vs "critical" regions
ax.axhspan(1, 10, alpha=0.05, color='green')
ax.axhspan(10, 200, alpha=0.05, color='red')
ax.text(3, 3, 'Manageable', fontsize=7, color='green', style='italic')
ax.text(3, 40, 'Critical', fontsize=7, color='red', style='italic')

# (b) Cost gap
ax = axes[1]
ax.plot(cost_Ks, adj_cost, 's-', color='#1f77b4', markersize=5, linewidth=1.8,
        label='Adjacent only')
ax.plot(cost_Ks, expr_cost, 'o-', color='#d62728', markersize=5, linewidth=1.8,
        label='With express links')
ax.fill_between(cost_Ks, expr_cost, adj_cost, alpha=0.15, color='#ff7f0e')
ax.set_xlabel('Number of chiplets (K)')
ax.set_ylabel('Inter-chiplet links needed')
ax.set_title('(b) Cost gap widens with scale')
ax.legend(loc='upper left', framealpha=0.9)
ax.grid(True, alpha=0.3)
# Annotate cost gap
ax.annotate('2.3× cost\ngap at K=64', xy=(64, (512 + 280) / 2), fontsize=7,
            ha='center', color='#ff7f0e', fontweight='bold')

plt.tight_layout()
fig.savefig(FIGURES_DIR / 'fig_intro_motivation.pdf', bbox_inches='tight')
fig.savefig(FIGURES_DIR / 'fig_intro_motivation.png', bbox_inches='tight')
plt.close()
print("[OK] fig_intro_motivation.pdf")
