"""Regenerate diminishing returns figure with matched font sizes."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'

plt.rcParams.update({
    'font.size': 6, 'font.family': 'serif',
    'axes.labelsize': 6, 'axes.titlesize': 7,
    'legend.fontsize': 5.5, 'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5,
    'figure.dpi': 150,
})

# Data from express_link_optimizer results (K=16, L=72)
n_express = [0, 1, 2, 3, 4, 5, 6, 7, 8]
rho_max = [62.8, 42.1, 32.5, 25.3, 22.1, 19.8, 17.5, 15.3, 15.3]

fig, ax = plt.subplots(1, 1, figsize=(3.5, 2.0))

ax.plot(n_express, rho_max, 'o-', color='#1f77b4', markersize=4, linewidth=1.5)
ax.fill_between(n_express, rho_max, alpha=0.1, color='#1f77b4')

# 60% improvement line
total_improvement = rho_max[0] - rho_max[-1]
threshold = rho_max[0] - 0.6 * total_improvement
ax.axhline(y=threshold, color='gray', linestyle='--', linewidth=0.7, alpha=0.6)
ax.text(6, threshold + 1.5, '60% of improvement', fontsize=5.5, color='gray',
        style='italic')

ax.set_xlabel('Number of express links added')
ax.set_ylabel('Max link utilization ($\\rho_{max}$)')
ax.set_title('Diminishing returns ($K$=16 chiplets, $L$=72)')
ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(FIGURES_DIR / 'fig_diminishing.pdf', bbox_inches='tight')
fig.savefig(FIGURES_DIR / 'fig_diminishing.png', bbox_inches='tight')
plt.close()
print("[OK] fig_diminishing.pdf")
