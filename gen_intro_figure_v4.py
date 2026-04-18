"""
Introduction Figure v4: Problem only. No express links.

(a) Phantom load amplification grows with K
(b) Adjacent-only: adding more links barely helps (saturation)
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

# Panel (b): Adjacent-only budget sweep, multiple K values
# Real BookSim data from cost_perf_across_K experiment (4×4 internal mesh)
budgets = [1, 2, 3, 4]
budget_labels = ['1×', '2×', '3×', '4×']

# K=4: adj_uniform lat@0.005
k4_lats = [35.3, 31.5, 30.1, 29.8]
# K=8: adj_uniform lat@0.005
k8_lats = [52.4, 41.9, 39.5, 38.8]
# K=16: adj_uniform lat@0.005
k16_lats = [71.5, 52.3, 49.2, 48.5]
# K=32: adj_uniform lat@0.005
k32_lats = [401.1, 266.4, 169.7, 170.1]

# Normalize to 1× budget for each K (show relative improvement)
k4_norm = [k4_lats[0] / l for l in k4_lats]
k8_norm = [k8_lats[0] / l for l in k8_lats]
k16_norm = [k16_lats[0] / l for l in k16_lats]
k32_norm = [k32_lats[0] / l for l in k32_lats]

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

# (b) Diminishing returns of adding adjacent links
ax = axes[1]
ax.plot(budgets, k4_norm, 'v-', color='#2ca02c', markersize=5, linewidth=1.5,
        label='K=4', alpha=0.8)
ax.plot(budgets, k8_norm, '^-', color='#1f77b4', markersize=5, linewidth=1.5,
        label='K=8', alpha=0.8)
ax.plot(budgets, k16_norm, 's-', color='#ff7f0e', markersize=6, linewidth=2.0,
        label='K=16')
ax.plot(budgets, k32_norm, 'o-', color='#d62728', markersize=6, linewidth=2.0,
        label='K=32')

# Ideal line (linear scaling: 2× budget → 2× improvement)
ideal = [1, 2, 3, 4]
ax.plot(budgets, ideal, '--', color='gray', linewidth=1.0, alpha=0.5, label='Ideal (linear)')

ax.set_xlabel('Link budget (× per adjacent pair)')
ax.set_ylabel('Speedup vs 1× budget')
ax.set_xticks(budgets)
ax.set_xticklabels(budget_labels)
ax.set_title('(b) Adding adjacent links: diminishing returns')
ax.legend(loc='upper left', fontsize=7, framealpha=0.9)
ax.grid(True, alpha=0.3)
ax.set_ylim(0.8, 4.5)

# Annotate K=16 saturation
ax.annotate('K=16: 4× budget\n→ only 1.5× speedup',
            xy=(4, k16_norm[3]), fontsize=7, ha='left',
            xytext=(2.8, 3.2),
            arrowprops=dict(arrowstyle='->', color='#ff7f0e', lw=1.0),
            color='#ff7f0e', fontweight='bold')

plt.tight_layout()
fig.savefig(FIGURES_DIR / 'fig_intro_motivation.pdf', bbox_inches='tight')
fig.savefig(FIGURES_DIR / 'fig_intro_motivation.png', bbox_inches='tight')
plt.close()
print("[OK] fig_intro_motivation.pdf")
