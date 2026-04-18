"""
Introduction Figure v5: Vertical layout (a) over (b).
Font < body text (10pt). No text-graph overlap.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

FIGURES_DIR = Path(__file__).parent / 'paper' / 'figures'

plt.rcParams.update({
    'font.size': 6, 'font.family': 'serif',
    'axes.labelsize': 6, 'axes.titlesize': 7,
    'legend.fontsize': 5.5, 'xtick.labelsize': 5.5, 'ytick.labelsize': 5.5,
    'figure.dpi': 150,
})

bbox_white = dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='none', alpha=0.85)

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

# Panel (b): Adjacent-only budget sweep (4×4 internal mesh, BookSim data)
budgets = [1, 2, 3, 4]
budget_labels = ['1×', '2×', '3×', '4×']
k4_lats = [35.3, 31.5, 30.1, 29.8]
k8_lats = [52.4, 41.9, 39.5, 38.8]
k16_lats = [71.5, 52.3, 49.2, 48.5]
k32_lats = [401.1, 266.4, 169.7, 170.1]

k4_norm = [k4_lats[0] / l for l in k4_lats]
k8_norm = [k8_lats[0] / l for l in k8_lats]
k16_norm = [k16_lats[0] / l for l in k16_lats]
k32_norm = [k32_lats[0] / l for l in k32_lats]

fig, axes = plt.subplots(2, 1, figsize=(3.5, 3.5))

# (a) Theoretical amplification
ax = axes[0]
ax.plot(theo_Ks, theo_amps, 'o-', color='#d62728', markersize=4, linewidth=1.8, zorder=3)
ax.fill_between(theo_Ks, [1] * len(theo_Ks), theo_amps, alpha=0.10, color='#d62728')
ax.axhline(y=1, color='gray', linestyle='--', linewidth=0.8)
ax.set_xlabel('Number of chiplets (K)')
ax.set_ylabel('Center link amplification (α)')
ax.set_yscale('log')
ax.set_title('(a) Phantom load grows with chiplet count')
ax.grid(True, alpha=0.3)

# Annotations — positioned to avoid data points
ax.annotate('MI300X (K=8)', xy=(8, 8), fontsize=5.5, ha='left',
            xytext=(12, 3), arrowprops=dict(arrowstyle='->', color='gray', lw=0.7),
            bbox=bbox_white)
ax.annotate('Next-gen (K≥16)', xy=(16, 16), fontsize=5.5, ha='left',
            xytext=(25, 6), arrowprops=dict(arrowstyle='->', color='gray', lw=0.7),
            bbox=bbox_white)

# Region labels — positioned in empty space
ax.text(50, 4, 'Manageable', fontsize=5.5, color='green', style='italic',
        bbox=bbox_white, ha='center')
ax.text(50, 60, 'Critical', fontsize=5.5, color='red', style='italic',
        bbox=bbox_white, ha='center')

# (b) Diminishing returns
ax = axes[1]
ax.plot(budgets, k4_norm, 'v-', color='#2ca02c', markersize=4, linewidth=1.3,
        label='K=4', alpha=0.8, zorder=3)
ax.plot(budgets, k8_norm, '^-', color='#1f77b4', markersize=4, linewidth=1.3,
        label='K=8', alpha=0.8, zorder=3)
ax.plot(budgets, k16_norm, 's-', color='#ff7f0e', markersize=5, linewidth=1.8,
        label='K=16', zorder=3)
ax.plot(budgets, k32_norm, 'o-', color='#d62728', markersize=5, linewidth=1.8,
        label='K=32', zorder=3)
ideal = [1, 2, 3, 4]
ax.plot(budgets, ideal, '--', color='gray', linewidth=1.0, alpha=0.5, label='Ideal')

ax.set_xlabel('Link budget (× per adjacent pair)')
ax.set_ylabel('Speedup vs 1× budget')
ax.set_xticks(budgets)
ax.set_xticklabels(budget_labels)
ax.set_title('(b) Adding adjacent links: diminishing returns')
ax.legend(loc='upper left', fontsize=5.5, framealpha=0.9, ncol=2)
ax.grid(True, alpha=0.3)
ax.set_ylim(0.8, 4.5)

# Annotation — positioned in empty lower-right area, no overlap
ax.annotate('K=16: 4× budget\n→ only 1.5× speedup',
            xy=(3.9, k16_norm[3]), fontsize=5.5,
            ha='right', va='top',
            xytext=(3.8, 3.5),
            arrowprops=dict(arrowstyle='->', color='#ff7f0e', lw=0.8),
            color='#ff7f0e', fontweight='bold',
            bbox=bbox_white)

plt.tight_layout()
fig.savefig(FIGURES_DIR / 'fig_intro_motivation.pdf', bbox_inches='tight')
fig.savefig(FIGURES_DIR / 'fig_intro_motivation.png', bbox_inches='tight')
plt.close()
print("[OK] fig_intro_motivation.pdf")
